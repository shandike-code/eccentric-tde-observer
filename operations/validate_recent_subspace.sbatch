#!/usr/bin/env bash
#SBATCH --job-name=tde-subspace-map-check
#SBATCH --partition=Students
#SBATCH --exclude=anode01
#SBATCH --time=01:00:00
#SBATCH --signal=B:USR1@180
#SBATCH --output=outputs/hpc/logs/%x-%j.out
#SBATCH --error=outputs/hpc/logs/%x-%j.err
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export NUMPY_MADVISE_HUGEPAGE=0 MPLBACKEND=Agg
export MPLCONFIGDIR="$PWD/outputs/hpc/matplotlib-${SLURM_JOB_ID}"
export PYTHONPATH="$PWD:$PWD/src:$PWD/scripts" PYTHONUNBUFFERED=1
exec "${TDE_PYTHON:-$PWD/.venv-hpc/bin/python}" operations/validate_recent_subspace.py \
  --run "${TDE_VALIDATE_RUN:?}" --workers "${TDE_WORKERS:?}"
