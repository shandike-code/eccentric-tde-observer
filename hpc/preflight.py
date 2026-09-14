"""Read-only environment and external restart integrity checks."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "handoff/restart_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe relative path: {relative}")
    result = root / path
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"path escapes root: {relative}")
    return result


def verify_claims(root: Path, claims: list[dict], *, hash_files: bool) -> list[dict]:
    failures = []
    for claim in claims:
        path = safe_path(root, claim["path"])
        if not path.is_file():
            failures.append({"path": claim["path"], "reason": "missing"})
        elif path.stat().st_size != claim["size_bytes"]:
            failures.append({"path": claim["path"], "reason": "size mismatch"})
        elif hash_files and sha256(path) != claim["sha256"]:
            failures.append({"path": claim["path"], "reason": "SHA-256 mismatch"})
    return failures


def environment() -> dict:
    def git_output(*args):
        result = subprocess.run(["git", *args], cwd=ROOT, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return result.stdout.strip() if result.returncode == 0 else None
    try:
        commit = git_output("rev-parse", "HEAD")
        dirty = git_output("status", "--porcelain", "--untracked-files=no")
    except FileNotFoundError:
        commit, dirty = None, None
    packages = {}
    for name in ("numpy", "scipy", "matplotlib", "pytest"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    scheduler = {key: os.environ[key] for key in (
        "SLURM_JOB_ID", "SLURM_JOB_PARTITION", "SLURM_JOB_QOS", "SLURM_CPUS_PER_TASK",
        "SLURM_MEM_PER_NODE", "SLURM_MEM_PER_CPU", "SLURM_JOB_NODELIST",
    ) if key in os.environ}
    quota = {}
    for name in ("memory.max", "memory.current", "cpu.max"):
        path = Path("/sys/fs/cgroup") / name
        if path.exists():
            quota[name] = path.read_text().strip()
    return {"git_commit": commit, "tracked_worktree_dirty": bool(dirty) if dirty is not None else None,
            "python": sys.version, "platform": platform.platform(),
            "machine": platform.machine(), "logical_host_cpus": os.cpu_count(),
            "cpu_affinity_count": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "scheduler": scheduler, "cgroup_v2": quota, "packages": packages,
            "project_free_bytes": shutil.disk_usage(ROOT).free,
            "warning": "Host resources are not necessarily this job's allocation."}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("environment", "snapshot"))
    parser.add_argument("--hash", action="store_true", help="Read and hash the external checkpoint bytes")
    args = parser.parse_args()
    if args.mode == "environment":
        print(json.dumps(environment(), indent=2))
        return 0
    data = json.loads(MANIFEST.read_text())
    failures = verify_claims(ROOT, data["small_runtime_inputs"] + data["checkpoints"], hash_files=args.hash)
    print(json.dumps({"scope": "original Mac handoff snapshot, before further mutation",
                      "hashes_checked": args.hash, "failures": failures,
                      "snapshot_valid": not failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
