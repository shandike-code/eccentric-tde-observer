"""Sequential interval-job supervisor that survives expired Slurm records.

Why this exists: `diagnostics/interval_supervise.py` (and `hpc/supervise.py`)
poll with

    subprocess.check_output(["squeue", "-h", "-j", job, "-o", "%i"])

which raises `CalledProcessError` as soon as the job's record expires
(MinJobAge). Three chains died that way on 2026-09-17 — once on restart with a
stale receipt, once mid-poll — so unattended operation was not actually possible.

Both pinned modules are hashed by existing runs and must not be edited. This file
reuses their verified semantics by import and replaces only the two queries that
can raise, with "not listed" treated as a normal answer.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "hpc")]
from pipeline import read, safe_path, write_json  # noqa: E402
from diagnostics.interval_supervise import (  # noqa: E402
    CONTINUE, acknowledge_failed_job, recovery_refusal, submit)


def queue_state(job: str, runner=subprocess.run) -> str | None:
    """Slurm state while queued, or None once the record is gone.

    `squeue -j <id>` exits non-zero for a job whose record has expired; that is
    "no longer queued", not a failure to observe. An empty listing also means the
    job has left the queue.
    """
    done = runner(["squeue", "-h", "-j", job, "-o", "%t"], text=True,
                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if done.returncode != 0:
        return None
    text = (done.stdout or "").strip()
    if not text:
        return None
    return text.splitlines()[0].strip() or None


def terminal_accounting(job: str, runner=subprocess.run):
    """(state, exit_code, source) for a finished job, or None if never recorded.

    scontrol is authoritative while the record survives MinJobAge; sacct may lag
    or be empty on this cluster. Neither query may raise: an unknown job is an
    answer we must be able to report, not an exception.
    """
    done = runner(["scontrol", "show", "job", job], text=True,
                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if done.returncode == 0:
        import re
        state = re.search(r"\bJobState=(\S+)", done.stdout or "")
        terminal = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY",
                    "NODE_FAIL", "BOOT_FAIL", "DEADLINE", "PREEMPTED"}
        if state is not None and state.group(1) in terminal:
            code = re.search(r"\bExitCode=(\S+)", done.stdout or "")
            return state.group(1), (code.group(1) if code else ""), "scontrol"
    done = runner(["sacct", "-X", "-n", "-P", "-j", job, "--format=State,ExitCode"],
                  text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if done.returncode != 0:
        return None
    text = (done.stdout or "").strip()
    if not text:
        return None
    state_name, exit_code, *_ = text.splitlines()[0].split("|")
    return state_name, exit_code, "sacct"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--max-jobs", type=int, default=6)
    parser.add_argument("--poll-seconds", type=int, default=120)
    parser.add_argument("--receipt", default="supervisor-robust.json",
                        help="receipt name inside the run directory")
    parser.add_argument("--retry-failed-job")
    parser.add_argument("--dry-run", action="store_true",
                        help="report the decision for the current receipt without submitting")
    args = parser.parse_args()
    if args.max_jobs < 1 or args.poll_seconds < 10:
        parser.error("positive job budget and polling interval >= 10 s required")
    run = safe_path(ROOT, args.run)
    path = run / args.receipt
    env = os.environ.copy()
    env["TDE_RUN"] = args.run
    with (run / "supervisor.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt = read(path) if path.exists() else {"active_job": None, "finished_jobs": []}
        acknowledge_failed_job(receipt, args.retry_failed_job)
        write_json(path, receipt)
        if args.dry_run:
            state = read(run / "state.json")
            print(json.dumps({"dry_run": True, "run": args.run, "receipt": receipt,
                              "run_status": state["status"],
                              "maps": len(state.get("history", [])),
                              "would_submit": (receipt["active_job"] is None
                                               and state["status"] in CONTINUE)}, indent=2))
            return
        while len(receipt["finished_jobs"]) < args.max_jobs:
            state = read(run / "state.json")
            if receipt["active_job"] is None:
                if state["status"] not in CONTINUE:
                    print(json.dumps({"status": state["status"],
                                      "action": "stop for scientific review"}), flush=True)
                    return
                if state["status"] == "diagnosis_incomplete":
                    refusal = recovery_refusal(run, state)
                    if refusal:
                        print(json.dumps({"status": state["status"],
                                          "action": "stop: recovery condition not met",
                                          "reason": refusal}), flush=True)
                        return
                    print(json.dumps({"status": state["status"],
                                      "action": "resume the recorded round"}), flush=True)
                receipt["active_job"] = _job_id(submit(args.run, env))
                write_json(path, receipt)
            current = receipt["active_job"]
            print(json.dumps({"watching_job": current, "run": args.run}), flush=True)
            while queue_state(current) is not None:
                time.sleep(args.poll_seconds)
            accounting = None
            for attempt in range(10):
                accounting = terminal_accounting(current)
                if accounting is not None:
                    break
                if attempt < 9:
                    time.sleep(args.poll_seconds)
            if accounting is None:
                raise RuntimeError(
                    f"No Slurm result for {current}; inspect it before another submission")
            state_name, exit_code, source = accounting
            receipt["finished_jobs"].append({"job_id": current, "state": state_name,
                                             "exit_code": exit_code, "state_source": source})
            receipt["active_job"] = None
            write_json(path, receipt)
            if state_name != "COMPLETED" or exit_code != "0:0":
                raise RuntimeError(
                    f"Job {current}: {state_name}/{exit_code}; inspect logs, do not blindly retry")
        print("Sequential job budget exhausted; inspect progress before extending it.")


def _job_id(output: str) -> str:
    value = (output or "").strip().split(";")[0]
    if not value.isdigit():
        raise ValueError(f"Unexpected sbatch result: {output!r}")
    return value


if __name__ == "__main__":
    main()
