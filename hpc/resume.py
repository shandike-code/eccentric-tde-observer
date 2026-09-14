"""Bounded Slurm wrapper around the unchanged, hash-pinned 7B9du runner.

It retains the ORIGINAL 1e-4 gate; a relaxed-gate science branch is future work.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts")]
PROTOCOL = "outputs/phase7b9du_preregistered_exhausted_dp_picard_continuation.json"
PROTOCOL_SHA256 = "51a670f53f9bb7be7abc312e31b01d5f6d3102dc633fcab328c9c01bba78b15b"
MANIFEST = "outputs/checkpoints/phase7b9du_exhausted_dp_picard_continuation/manifest.json"
stop_requested = False


def request_stop(_signum, _frame):
    global stop_requested
    stop_requested = True
    print("Slurm warning: stop after the current complete map.", flush=True)


def next_iteration(manifest: dict) -> int:
    if not manifest.get("iterations"):
        raise ValueError("missing committed iteration history")
    # iteration is a stage-local map index, not an orbital phase index.
    return int(manifest["iterations"][-1]["iteration"]) + 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--maps", type=int, default=1)
    args = parser.parse_args()
    if args.maps < 1 or args.maps > 20:
        parser.error("choose a bounded batch of 1..20 maps")
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("Run through sbatch; no full-column work on a login node.")
    cpus = int(os.environ.get("SLURM_CPUS_PER_TASK", "0"))
    if cpus < 2:
        raise SystemExit("The frozen runner requires two worker CPUs.")
    if not (ROOT / MANIFEST).is_file():
        raise SystemExit("Restore the artifact snapshot and restart data first; do not recreate its manifest.")
    lock_path = ROOT / "outputs/hpc/phase7b9du.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGUSR1, request_stop)
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Another job owns these two buffers; use a separate run directory.")
        from scripts import phase7b9du_exhausted_dp_picard_continuation as continuation
        for _ in range(args.maps):
            if stop_requested:
                break
            manifest = json.loads((ROOT / MANIFEST).read_text())
            if manifest["status"] != "running":
                print(json.dumps({"status": manifest["status"], "action": "no further maps"}))
                break
            target = next_iteration(manifest)
            print(json.dumps({"job": os.environ["SLURM_JOB_ID"], "target_iteration": target,
                              "strict_original_gate": 1e-4}), flush=True)
            summary = continuation.run_continuation(
                ROOT, ROOT / PROTOCOL, PROTOCOL_SHA256, stop_after_iteration=target,
            )
            current = json.loads((ROOT / MANIFEST).read_text())
            print(json.dumps({"completed_iteration": current["iterations"][-1]["iteration"],
                              "active_iteration": current.get("active_iteration"),
                              "decision": summary.get("decision")}), flush=True)


if __name__ == "__main__":
    main()
