#!/usr/bin/env bash
#SBATCH --job-name=tde-confirm
#SBATCH --partition=Students
#SBATCH --qos=qos_stu_cpu_long
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=128G
#SBATCH --time=02:00:00
#SBATCH --signal=B:USR1@600
#SBATCH --output=outputs/hpc/logs/%x-%j.out
#SBATCH --error=outputs/hpc/logs/%x-%j.err
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export MPLBACKEND=Agg PYTHONUNBUFFERED=1
export PYTHONPATH="$PWD:$PWD/src:$PWD/scripts"
export MPLCONFIGDIR="$PWD/outputs/hpc/matplotlib-${SLURM_JOB_ID}"
python_bin="${TDE_PYTHON:-$PWD/.venv-hpc/bin/python}"
child=''
stopping=0
trap 'stopping=1; if [[ -n "$child" ]]; then kill -USR1 "$child" 2>/dev/null || true; fi' USR1
run_step() {
  if (( stopping )); then exit 0; fi
  "$@" &
  child=$!
  set +e
  while true; do
    wait "$child"
    result=$?
    if ! kill -0 "$child" 2>/dev/null; then break; fi
  done
  set -e
  child=''
  if (( result )); then exit "$result"; fi
}
run_step "$python_bin" operations/confirm_inner_threshold.py \
  --run "${TDE_RUN:?}" --source-run "${TDE_SOURCE_RUN:?}"
# Existing trial_material.npz is owned and hashed by the new declaration;
# pipeline initialization consumes it without invoking the old 0.0625 migration.
run_step "$python_bin" operations/prepare_encoded_backtrack.py --run "$TDE_RUN" \
  --source-run "$TDE_SOURCE_RUN" --initialize-only
run_step "$python_bin" diagnostics/interval_diagnostic.py --run "$TDE_RUN" \
  --maps-per-job 8 --feedback-every 4
