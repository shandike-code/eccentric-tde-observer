#!/usr/bin/env bash
set -euo pipefail
: "${SLURM_JOB_ID:?Submit via sbatch; do not run heavy work in WebShell}"
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export MPLBACKEND=Agg PYTHONUNBUFFERED=1
export PYTHONPATH="$PWD:$PWD/src:$PWD/scripts${PYTHONPATH:+:$PYTHONPATH}"
python_bin="${TDE_PYTHON:-$PWD/.venv-hpc/bin/python}"
mkdir -p outputs/hpc/logs
export MPLCONFIGDIR="$PWD/outputs/hpc/matplotlib-${SLURM_JOB_ID}"
"$python_bin" hpc/preflight.py environment > "outputs/hpc/environment-${SLURM_JOB_ID}.json"
child=''
trap 'if [[ -n "$child" ]]; then kill -USR1 "$child" 2>/dev/null || true; fi' USR1
case "${1:-smoke}" in
  smoke) "$python_bin" hpc/smoke.py & ;;
  block-check) "$python_bin" hpc/check_block.py --run "${TDE_RUN:-outputs/hpc/block-check}" & ;;
  verify) "$python_bin" hpc/preflight.py snapshot --hash & ;;
  resume) "$python_bin" hpc/resume.py --maps "${TDE_MAPS:-1}" & ;;
  pipeline) "$python_bin" hpc/pipeline.py run --run "${TDE_RUN:?}" --maps-per-job "${TDE_MAPS:-8}" & ;;
  *) echo 'Unknown mode' >&2; exit 2 ;;
esac
child=$!
# wait may be interrupted by the warning signal; keep waiting for the map boundary.
set +e
while true; do
  wait "$child"
  result=$?
  if ! kill -0 "$child" 2>/dev/null; then break; fi
done
exit "$result"
