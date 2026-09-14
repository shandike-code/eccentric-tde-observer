"""Restore the versioned small-artifact bundle; reject changed existing files."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import tarfile
import tempfile

from preflight import ROOT, safe_path, sha256


def validate_member(root: Path, member: tarfile.TarInfo) -> Path:
    path = safe_path(root, member.name)
    if not member.isfile() or Path(member.name).parts[0] != "outputs":
        raise ValueError(f"unexpected archive member: {member.name}")
    if "checkpoints" in Path(member.name).parts and path.suffix == ".dat":
        raise ValueError("large checkpoints must be transferred separately")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--profile", choices=("historical", "runtime"), default="runtime")
    args = parser.parse_args()
    name = "runtime_bundle.json" if args.profile == "runtime" else "artifact_bundle.json"
    manifest = json.loads((ROOT / "handoff" / name).read_text())
    if args.archive.stat().st_size != manifest["size_bytes"] or sha256(args.archive) != manifest["sha256"]:
        raise SystemExit("Artifact archive size/hash mismatch; do not extract a partial download.")
    with tarfile.open(args.archive, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) != len(manifest["files"]):
            raise SystemExit("Archive inventory mismatch")
        seen = set()
        # Audit EVERY destination before writing anything; preserve changed live results.
        for member in members:
            path = validate_member(ROOT, member)
            if member.name in seen or member.name not in manifest["files"]:
                raise SystemExit("Duplicate/unlisted archive member")
            seen.add(member.name)
            claim = manifest["files"][member.name]
            if member.size != claim["size_bytes"]:
                raise SystemExit(f"Member size mismatch: {member.name}")
            if path.exists() and (not path.is_file() or sha256(path) != claim["sha256"]):
                raise SystemExit(f"Existing file differs: {member.name}; use a fresh checkout.")
        for member in members:
            path = validate_member(ROOT, member)
            if path.exists():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
                temporary = Path(out.name)
                with archive.extractfile(member) as source:
                    shutil.copyfileobj(source, out)
            if sha256(temporary) != manifest["files"][member.name]["sha256"]:
                temporary.unlink()
                raise SystemExit(f"Extracted member hash mismatch: {member.name}")
            temporary.replace(path)
    print(f"Restored/verified {len(members)} files. Large radiation checkpoints are still external.")


if __name__ == "__main__":
    main()
