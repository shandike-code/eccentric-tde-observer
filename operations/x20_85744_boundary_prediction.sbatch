#!/usr/bin/env bash
#SBATCH --job-name=tde-x20-bpred
#SBATCH --partition=Students
#SBATCH --qos=qos_stu_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --signal=B:USR1@120
#SBATCH --output=outputs/hpc/logs/%x-%j.out
#SBATCH --error=outputs/hpc/logs/%x-%j.err
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export NUMPY_MADVISE_HUGEPAGE=0 PYTHONUNBUFFERED=1 MPLBACKEND=Agg
export PYTHONPATH="$PWD:$PWD/src:$PWD/scripts"
child=''
trap 'if [[ -n "$child" ]]; then kill -USR1 "$child" 2>/dev/null || true; fi' USR1 TERM
.venv-hpc/bin/python operations/x20_85744_boundary_prediction.py --run outputs/hpc/x20-85744-boundary-prediction-20261005 &
child=$!
set +e
while true; do
  wait "$child"
  result=$?
  if ! kill -0 "$child" 2>/dev/null; then break; fi
done
export TDE_CHILD_EXIT_STATUS="$result"
.venv-hpc/bin/python - <<'PYEXIT'
import json,os,time
from pathlib import Path
p=Path('outputs/hpc/x20-85744-boundary-prediction-20261005/batch-exit.json')
x=dict(job_id=os.environ['SLURM_JOB_ID'],child_exit_status=int(os.environ['TDE_CHILD_EXIT_STATUS']),recorded_unix=time.time(),scheduler_terminal_verified=False,meaning='shell wait status of Python child; not Slurm terminal state')
p.write_text(json.dumps(x,indent=2)+'\n')
PYEXIT
exit "$result"
