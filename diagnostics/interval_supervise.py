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
from supervise import job_id, scontrol_state  # noqa: E402  (cluster-specific terminal states)
from pipeline import read, safe_path, write_json  # noqa: E402

# `supervise.CONTINUE` covers the stock pipeline's states. This driver adds
# `diagnosis_incomplete`: the physics of a round finished but its ledger did not,
# and only that step still has to be redone. It is a resumable state, not a stop.
CONTINUE = {"initializing", "radiation", "diagnosis_incomplete",
            "feedback_ready", "feedback_running"}


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


def recovery_refusal(run: Path, state: dict, root: Path = ROOT):
    """Why `diagnosis_incomplete` must NOT be resubmitted blindly.

    The status only says "the physics of a round finished but its ledger did not".
    Before another job is submitted, the persisted pending record has to actually
    describe a resumable round: the directory must be the registered one, and the
    artifacts its stage depends on must be present. Anything else is a condition
    to inspect, not to retry -- in particular a previous job's non-zero exit is a
    different situation from a recorded ledger failure.
    """
    pending = state.get("pending_feedback")
    if not pending:
        return "diagnosis_incomplete but no pending round is registered"
    # Both fields are project-root relative, not run relative.
    round_dir = root / pending["round_dir"]
    if not round_dir.is_dir():
        return f"registered round directory missing: {pending['round_dir']}"
    stage = pending.get("stage")
    if stage == "feedback":
        protocol = root / pending.get("protocol_path", "")
        if not protocol.is_file():
            return f"round protocol missing: {pending.get('protocol_path')}"
    elif stage == "ledger":
        if not (round_dir / "feedback_summary.json").is_file():
            return "stage is 'ledger' but the round has no feedback summary"
    elif stage != "protocol":
        return f"unknown round stage: {stage!r}"
    return None


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
                if state["status"] == "diagnosis_incomplete":
                    refusal = recovery_refusal(run, state)
                    if refusal:
                        print(json.dumps({"status": state["status"],
                                          "action": "stop: recovery condition not met",
                                          "reason": refusal}), flush=True)
                        return
                    print(json.dumps({"status": state["status"],
                                      "action": "resume the recorded round"}), flush=True)
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
