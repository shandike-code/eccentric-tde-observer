#!/usr/bin/env bash
# Append one compact status line per tracked run, forever, to a log file.
#
# Read-only by construction: it opens state.json/config.json for reading and
# appends to its own log. It never submits, cancels or edits a run, and it makes
# no policy decision -- failures are recorded, not retried. Rationale: the
# observation channel (an SSH master socket on the user's laptop) can die at any
# time; with the logger running inside tmux on the login node, the record stays
# continuous across those gaps.
set -uo pipefail

INTERVAL_SECONDS="${TDE_STATUS_INTERVAL:-300}"
LOG="${TDE_STATUS_LOG:-outputs/hpc/logs/tde-status.log}"
PYTHON_BIN="${TDE_PYTHON:-$PWD/.venv-hpc/bin/python}"
RUNS_DEFAULT="small-step-a00390625-20260917 small-step-a078125-cont48-20260917 small-step-a15625-cont48-20260917"
RUNS="${TDE_STATUS_RUNS:-$RUNS_DEFAULT}"

mkdir -p "$(dirname "$LOG")"
while true; do
  stamp="$(date '+%F %T')"
  load="$(scontrol show node anode16 2>/dev/null | grep -oE 'CPUAlloc=[0-9]+|CPULoad=[0-9.]+' | tr '\n' ' ')"
  jobs="$(squeue -u "$USER" -h -o '%i:%t' 2>/dev/null | tr '\n' ' ')"
  "$PYTHON_BIN" - "$RUNS" "$stamp" "$load" "$jobs" <<'PY' >> "$LOG" 2>&1
import json
import os
import sys

runs, stamp, load, jobs = sys.argv[1:5]
parts = []
for run in runs.split():
    path = os.path.join("outputs/hpc", run, "state.json")
    try:
        with open(path) as handle:
            state = json.load(handle)
    except Exception as exc:                      # missing run is data, not a crash
        parts.append(f"{run}=unreadable({type(exc).__name__})")
        continue
    history = state.get("history", [])
    rounds = len(state.get("diagnostic", {}).get("rounds", []))
    residual = f"{history[-1]['residual']:.4e}" if history else "n/a"
    parts.append(f"{run}={state.get('status')}/maps{len(history)}/R{residual}/rounds{rounds}"
                 f"/pending{int(bool(state.get('pending_feedback')))}")
print(f"{stamp} | {' | '.join(parts)} | load[{load.strip()}] jobs[{jobs.strip()}]", flush=True)
PY
  sleep "$INTERVAL_SECONDS"
done
