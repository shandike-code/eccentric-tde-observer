"""Submit bounded sequential Slurm jobs and persist the job being watched.

This lightweight login-shell process never runs the numerical solver itself.
Stopping this supervisor does not cancel a submitted batch job.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

from pipeline import ROOT, read, safe_path, write_json

CONTINUE = {"initializing", "radiation", "feedback_ready", "feedback_running"}


def job_id(output: str) -> str:
    value = output.strip().split(";")[0]
    if not value.isdigit():
        raise ValueError(f"Unexpected sbatch result: {output!r}")
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--max-jobs", type=int, default=32)
    parser.add_argument("--poll-seconds", type=int, default=60)
    args = parser.parse_args()
    if args.max_jobs < 1 or args.poll_seconds < 10:
        parser.error("positive job budget and polling interval >=10 s required")
    run = safe_path(ROOT, args.run)
    path = run / "supervisor.json"
    env = os.environ.copy()
    env["TDE_RUN"] = args.run
    with (run / "supervisor.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt = read(path) if path.exists() else {"active_job": None, "finished_jobs": []}
        while len(receipt["finished_jobs"]) < args.max_jobs:
            state = read(run / "state.json")
            if receipt["active_job"] is None:
                if state["status"] not in CONTINUE:
                    print(json.dumps({"status": state["status"], "action": "stop for scientific review"}))
                    return
                result = subprocess.check_output(["bash", "hpc/submit.sh", "pipeline"], cwd=ROOT, env=env, text=True)
                receipt["active_job"] = job_id(result)
                write_json(path, receipt)
            current = receipt["active_job"]
            print(json.dumps({"watching_job": current, "run": args.run}), flush=True)
            while subprocess.check_output(["squeue", "-h", "-j", current, "-o", "%i"], text=True).strip():
                time.sleep(args.poll_seconds)
            # Accounting may lag briefly behind squeue. Never silently submit on an unknown exit.
            accounting = ""
            for _ in range(10):
                accounting = subprocess.check_output(["sacct", "-X", "-n", "-P", "-j", current,
                               "--format=State,ExitCode"], text=True).strip()
                if accounting: break
                time.sleep(args.poll_seconds)
            if not accounting:
                raise RuntimeError(f"No sacct result for {current}; inspect it before another submission")
            state_name, exit_code, *_ = accounting.splitlines()[0].split("|")
            receipt["finished_jobs"].append({"job_id": current, "state": state_name, "exit_code": exit_code})
            receipt["active_job"] = None
            write_json(path, receipt)
            if state_name != "COMPLETED" or exit_code != "0:0":
                raise RuntimeError(f"Job {current}: {state_name}/{exit_code}; inspect logs, do not blindly retry")
        print("Sequential job budget exhausted; inspect progress before extending it.")


if __name__ == "__main__":
    main()
