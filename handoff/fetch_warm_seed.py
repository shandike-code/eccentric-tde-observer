"""Download verified GitHub Release parts and atomically assemble one warm seed.

Kept outside src/scripts/hpc so this transfer utility does not change the source
inventory of an already-prepared radiation run. Standard library only.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("warm_seed_github.json")
BUFFER = 8 * 1024**2


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BUFFER), b""):
            h.update(block)
    return h.hexdigest()


def safe_destination(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or path.parts[:2] != ("outputs", "checkpoints"):
        raise ValueError("Checkpoint must be under outputs/checkpoints")
    result = root / path
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError("Checkpoint path escapes project")
    return result


def validate_manifest(root: Path, manifest: dict) -> Path:
    final = safe_destination(root, manifest["checkpoint"]["path"])
    offset = 0
    names = set()
    for part in manifest["parts"]:
        name = part["name"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in names or name in {".", ".."}:
            raise ValueError("Invalid/duplicate part name")
        names.add(name)
        if part["offset_bytes"] != offset or part["size_bytes"] <= 0:
            raise ValueError("Parts must cover the checkpoint consecutively")
        if not re.fullmatch(r"[0-9a-f]{64}", part["sha256"]):
            raise ValueError("Invalid part digest")
        offset += part["size_bytes"]
    if not names or offset != manifest["checkpoint"]["size_bytes"]:
        raise ValueError("Part sizes do not match checkpoint")
    return final


def verify(path: Path, claim: dict):
    if path.stat().st_size != claim["size_bytes"] or digest(path) != claim["sha256"]:
        raise RuntimeError(f"Size/SHA mismatch: {path}")


def release_metadata(repo: str, tag: str):
    """Use existing gh credentials when available; public releases need no login."""
    gh = shutil.which("gh")
    endpoint = f"repos/{repo}/releases/tags/{urllib.parse.quote(tag, safe='')}"
    if gh:
        try:
            raw = subprocess.check_output([gh, "api", "--method", "GET", endpoint],
                                          text=True, stderr=subprocess.DEVNULL)
            return json.loads(raw), gh
        except subprocess.CalledProcessError:
            pass
    request = urllib.request.Request("https://api.github.com/" + endpoint,
        headers={"User-Agent": "tde-warm-seed-transfer", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response), None
    except urllib.error.HTTPError as error:
        if error.code in (401, 404):
            raise RuntimeError("Release unavailable; for a private repository install/authenticate gh") from error
        raise


def download(root: Path, manifest: dict, parts_dir: Path, manifest_path: Path):
    validate_manifest(root, manifest)
    repo, tag = manifest["repository"], manifest["release_tag"]
    release, gh = release_metadata(repo, tag)
    assets = {a["name"]: a for a in release["assets"]}
    marker = assets.get(manifest_path.name)
    if not marker or marker.get("digest") != "sha256:" + digest(manifest_path):
        raise RuntimeError("Release completion manifest missing/different; do not use an unfinished upload")
    for part in manifest["parts"]:
        a = assets.get(part["name"])
        if not a or a["state"] != "uploaded" or a["size"] != part["size_bytes"] or a.get("digest") != "sha256:" + part["sha256"]:
            raise RuntimeError("Release part metadata mismatch: " + part["name"])
    parts_dir.mkdir(parents=True, exist_ok=True)
    with (parts_dir / ".download.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        staging = parts_dir / ".partial"
        staging.mkdir(exist_ok=True)
        for index, part in enumerate(manifest["parts"]):
            final = parts_dir / part["name"]
            if final.exists():
                verify(final, part)
                print(f"Verified existing part {index + 1}/{len(manifest['parts'])}", flush=True)
                continue
            temporary = staging / part["name"]
            for attempt in range(3):
                if gh:
                    ok = subprocess.run([gh, "release", "download", tag, "--repo", repo,
                        "--pattern", part["name"], "--dir", str(staging), "--clobber"]).returncode == 0
                else:
                    url = (f"https://github.com/{repo}/releases/download/"
                           f"{urllib.parse.quote(tag, safe='')}/{urllib.parse.quote(part['name'], safe='')}")
                    try:
                        request = urllib.request.Request(url, headers={"User-Agent": "tde-warm-seed-transfer"})
                        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as out:
                            shutil.copyfileobj(response, out, length=BUFFER)
                        ok = True
                    except (OSError, urllib.error.URLError) as error:
                        print(f"Part download interrupted: {error}", flush=True)
                        ok = False
                if ok:
                    verify(temporary, part)
                    os.link(temporary, final)
                    temporary.unlink()
                    break
                if attempt == 2:
                    raise RuntimeError("Download failed; rerun to retain verified earlier parts")
                time.sleep(5)
            print(f"Downloaded and verified part {index + 1}/{len(manifest['parts'])}", flush=True)


def assemble(root: Path, manifest: dict, parts_dir: Path) -> Path:
    final = validate_manifest(root, manifest)
    final.parent.mkdir(parents=True, exist_ok=True)
    with (final.parent / ".warm_seed_github.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if final.exists():
            verify(final, manifest["checkpoint"])
            print("Existing checkpoint has the expected size and SHA-256.")
            return final
        for part in manifest["parts"]:
            path = parts_dir / part["name"]
            if not path.is_file() or path.stat().st_size != part["size_bytes"]:
                raise RuntimeError("Missing/wrong-size part: " + part["name"])
        temporary = final.with_name(final.name + ".github-assembling")
        reclaimable = temporary.stat().st_size if temporary.exists() else 0
        if shutil.disk_usage(final.parent).free + reclaimable < manifest["checkpoint"]["size_bytes"]:
            raise RuntimeError("Need space for the full checkpoint in addition to downloaded parts")
        whole = hashlib.sha256()
        total = 0
        with temporary.open("wb") as out:
            for index, part in enumerate(manifest["parts"]):
                h = hashlib.sha256()
                count = 0
                with (parts_dir / part["name"]).open("rb") as source:
                    for block in iter(lambda: source.read(BUFFER), b""):
                        h.update(block)
                        whole.update(block)
                        out.write(block)
                        count += len(block)
                if count != part["size_bytes"] or h.hexdigest() != part["sha256"]:
                    raise RuntimeError("Part changed/corrupted: " + part["name"])
                total += count
                print(f"Assembled and verified part {index + 1}/{len(manifest['parts'])}", flush=True)
            out.flush()
            os.fsync(out.fileno())
        if total != manifest["checkpoint"]["size_bytes"] or whole.hexdigest() != manifest["checkpoint"]["sha256"]:
            raise RuntimeError("Full checkpoint SHA-256 mismatch; final path was not created")
        # Same-filesystem, atomic no-overwrite commit. Incomplete output is never
        # published under the final name consumed by pipeline.prepare.
        os.link(temporary, final)
        temporary.unlink()
        print(f"Verified warm seed: {final}\nSHA-256: {whole.hexdigest()}")
        return final


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("download", "assemble", "verify"))
    p.add_argument("--parts-dir", type=Path, default=ROOT / "downloads/warm-seed")
    args = p.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    original = json.loads((ROOT / "handoff/restart_manifest.json").read_text())["checkpoints"][0]
    if manifest["checkpoint"] != original:
        raise RuntimeError("Warm seed does not match the original handoff snapshot")
    if args.command == "download":
        download(ROOT, manifest, args.parts_dir.resolve(), MANIFEST)
    elif args.command == "assemble":
        assemble(ROOT, manifest, args.parts_dir.resolve())
    else:
        final = validate_manifest(ROOT, manifest)
        verify(final, manifest["checkpoint"])
        print("Checkpoint size and full SHA-256 verified.")


if __name__ == "__main__":
    main()
