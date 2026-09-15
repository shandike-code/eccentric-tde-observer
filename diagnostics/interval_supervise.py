"""Submit bounded sequential diagnostic jobs and persist the job being watched.

Deliberately a thin sibling of `hpc/supervise.py`: it imports that module's
`scontrol_state`, `job_id` and `CONTINUE` so the cluster-specific terminal-state
handling (sacct is empty here, scontrol answers only inside MinJobAge) is shared
rather than re-derived. The only difference is which sbatch line is submitted --
`diagnostics/interval.sbatch` instead of `bash hpc/submit.sh pipeline`.

Like its sibling it never runs the solver itself, stopping it does not cancel a
submitted job, and it never resubmits on an unknown exit.
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
from supervise import CONTINUE, job_id, scontrol_state  # noqa: E402
from pipeline import read, safe_path, write_json  # noqa: E402


def submit(run_relative: str, env: dict) -> str:
    command = [
        "sbatch", "--parsable", "--job-name=tde-interval",
        "--nodes=1", "--ntasks=1",
        "--partition=" + env.get("TDE_PARTITION", "Students"),
        "--qos=" + env.get("TDE_QOS", "qos_stu_default"),
        "--cpus-per-task=" + env.get("TDE_CPUS", "4"),
        "--mem=" + env.get("TDE_MEM", "16G"),
        "--time=" + env.get("TDE_WALLTIME", "04:00:00"),
        "--signal=B:USR1@600",
        "--output=outputs/hpc/logs/%x-%j.out",
        "--error=outputs/hpc/logs/%x-%j.err",
        "diagnostics/interval.sbatch",
    ]
    return subprocess.check_output(command, cwd=ROOT, env=env, text=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--max-jobs", type=int, default=8)
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
                    print(json.dumps({"status": state["status"],
                                      "action": "stop for scientific review"}), flush=True)
                    return
                receipt["active_job"] = job_id(submit(args.run, env))
                write_json(path, receipt)
            current = receipt["active_job"]
            print(json.dumps({"watching_job": current, "run": args.run}), flush=True)
            while subprocess.check_output(["squeue", "-h", "-j", current, "-o", "%i"],
                                          text=True).strip():
                time.sleep(args.poll_seconds)
            source, accounting = "", ""
            for attempt in range(10):
                found = scontrol_state(current)
                if found is not None:
                    accounting, source = "|".join(found), "scontrol"
                    break
                accounting = subprocess.check_output(
                    ["sacct", "-X", "-n", "-P", "-j", current, "--format=State,ExitCode"],
                    text=True).strip()
                if accounting:
                    source = "sacct"
                    break
                if attempt < 9:
                    time.sleep(args.poll_seconds)
            if not accounting:
                raise RuntimeError(f"No Slurm result for {current}; inspect it before another submission")
            state_name, exit_code, *_ = accounting.splitlines()[0].split("|")
            receipt["finished_jobs"].append({"job_id": current, "state": state_name,
                                             "exit_code": exit_code, "state_source": source})
            receipt["active_job"] = None
            write_json(path, receipt)
            if state_name != "COMPLETED" or exit_code != "0:0":
                raise RuntimeError(f"Job {current}: {state_name}/{exit_code}; inspect logs, do not blindly retry")
        print("Sequential job budget exhausted; inspect progress before extending it.")


if __name__ == "__main__":
    main()
