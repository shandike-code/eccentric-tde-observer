#!/usr/bin/env bash
#SBATCH --job-name=tde-x20-chord-diagonal-resource
#SBATCH --partition=Students
#SBATCH --qos=qos_stu_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --signal=B:USR1@300
#SBATCH --output=outputs/hpc/logs/%x-%j.out
#SBATCH --error=outputs/hpc/logs/%x-%j.err
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
: "${CHORD_EXPECTED_COMMIT:?}" "${CHORD_RUN:?}" "${CHORD_INVENTORY:?}" "${CHORD_SOURCE_REVIEW:?}" "${CHORD_HISTORY:?}" "${CHORD_CODE_FREEZE:?}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export NUMPY_MADVISE_HUGEPAGE=0 PYTHONUNBUFFERED=1
export PYTHONPATH="$PWD:$PWD/src:$PWD/scripts"
child=''
trap 'if [[ -n "$child" ]]; then kill -USR1 "$child" 2>/dev/null || true; fi' USR1
trap 'if [[ -n "$child" ]]; then kill -TERM "$child" 2>/dev/null || true; fi' TERM
trap 'if [[ -n "$child" ]]; then kill -INT "$child" 2>/dev/null || true; fi' INT
.venv-hpc/bin/python operations/x20_85889_chord_diagonal_resource.py \
  --expected-commit "$CHORD_EXPECTED_COMMIT" --run "$CHORD_RUN" \
  --inventory "$CHORD_INVENTORY" --source-review "$CHORD_SOURCE_REVIEW" --history "$CHORD_HISTORY" --code-freeze "$CHORD_CODE_FREEZE" &
child=$!
set +e
while true; do
  wait "$child"
  result=$?
  if ! kill -0 "$child" 2>/dev/null; then break; fi
done
export CHORD_CHILD_EXIT_STATUS="$result"
.venv-hpc/bin/python - <<'PYEXIT'
import json,os,time
from pathlib import Path
p=Path('outputs/hpc/logs')/('chord-diagonal-resource-'+os.environ['SLURM_JOB_ID']+'-batch-exit.json')
with p.open('x') as f:
    json.dump(dict(job_id=os.environ['SLURM_JOB_ID'],child_exit_status=int(os.environ['CHORD_CHILD_EXIT_STATUS']),
        recorded_unix=time.time(),scheduler_terminal_verified=False,
        meaning='Python child shell wait status, not Slurm terminal'),f,indent=2)
    f.write('\n')
PYEXIT
exit "$result"
