#!/usr/bin/env bash
# Slurm wrapper for diagnostics/interval_diagnostic.py.
#
# Mirrors hpc/job.sbatch's environment and SIGUSR1 forwarding so the diagnostic
# driver runs under the same allocation rules, but dispatches to the diagnostic
# driver instead of hpc/pipeline.py. hpc/job.sbatch itself is left untouched.
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
"$python_bin" diagnostics/interval_diagnostic.py \
  --run "${TDE_RUN:?}" \
  --maps-per-job "${TDE_MAPS:-1}" \
  --feedback-every "${TDE_FEEDBACK_EVERY:-4}" &
child=$!
set +e
while true; do
  wait "$child"
  result=$?
  if ! kill -0 "$child" 2>/dev/null; then break; fi
done
exit "$result"
