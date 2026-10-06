#!/usr/bin/env bash
#SBATCH --job-name=tde-x20-relaxed10
#SBATCH --partition=Students
#SBATCH --exclude=anode01
#SBATCH --qos=qos_stu_cpu_long
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#SBATCH --signal=B:USR1@900
#SBATCH --output=outputs/hpc/logs/%x-%j.out
#SBATCH --error=outputs/hpc/logs/%x-%j.err
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export NUMPY_MADVISE_HUGEPAGE=0 MPLBACKEND=Agg PYTHONUNBUFFERED=1
export PYTHONPATH="$PWD:$PWD/src:$PWD/scripts"
export MPLCONFIGDIR="$PWD/outputs/hpc/matplotlib-${SLURM_JOB_ID}"
TDE_RUN="${TDE_RUN:-outputs/hpc/x20-85889-relaxed-feedback-20261007}"
child=''
trap 'if [[ -n "$child" ]]; then kill -USR1 "$child" 2>/dev/null || true; fi' USR1 TERM
"${TDE_PYTHON:-$PWD/.venv-hpc/bin/python}" operations/x20_85889_relaxed_feedback.py --run "$TDE_RUN" &
child=$!
set +e
while true; do
  wait "$child"
  result=$?
  if ! kill -0 "$child" 2>/dev/null; then break; fi
done
set -e
if [[ -d "$TDE_RUN" ]]; then scontrol show job -o "$SLURM_JOB_ID" > "$TDE_RUN/scheduler-before-exit.txt" 2>&1 || true; fi
export TDE_CHILD_EXIT_STATUS="$result" TDE_RUN
.venv-hpc/bin/python - <<'PYEXIT'
import json,os,time
from pathlib import Path
p=Path(os.environ['TDE_RUN'])/'batch-exit.json'
x=dict(job_id=os.environ['SLURM_JOB_ID'],child_exit_status=int(os.environ['TDE_CHILD_EXIT_STATUS']),recorded_unix=time.time(),scheduler_terminal_verified=False,meaning='shell wait status of Python child; not Slurm terminal state')
p.write_text(json.dumps(x,indent=2)+'\n')
PYEXIT
exit "$result"
