#!/usr/bin/env bash
#SBATCH --job-name=tde-cpu-scale
#SBATCH --partition=Students
#SBATCH --qos=qos_stu_cpu_long
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=52G
#SBATCH --time=02:00:00
#SBATCH --signal=B:USR1@120
#SBATCH --output=outputs/hpc/logs/%x-%j.out
#SBATCH --error=outputs/hpc/logs/%x-%j.err
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export MPLBACKEND=Agg PYTHONUNBUFFERED=1
export PYTHONPATH="$PWD:$PWD/src:$PWD/scripts"
export MPLCONFIGDIR="$PWD/outputs/hpc/matplotlib-${SLURM_JOB_ID}"
child=''
trap 'if [[ -n "$child" ]]; then kill -USR1 "$child" 2>/dev/null || true; fi' USR1
"${TDE_PYTHON:-$PWD/.venv-hpc/bin/python}" operations/cpu_scaling_benchmark.py \
  --run "${TDE_BENCHMARK_RUN:?}" --template "${TDE_BENCHMARK_TEMPLATE:?}" \
  --seed-run "${TDE_BENCHMARK_SEED_RUN:?}" &
child=$!
set +e
while true; do
  wait "$child"
  result=$?
  if ! kill -0 "$child" 2>/dev/null; then break; fi
done
exit "$result"
