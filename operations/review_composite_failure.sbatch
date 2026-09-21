#!/usr/bin/env bash
#SBATCH --job-name=tde-hybrid-failure-audit
#SBATCH --partition=Students
#SBATCH --qos=qos_stu_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=outputs/hpc/logs/%x-%j.out
#SBATCH --error=outputs/hpc/logs/%x-%j.err
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export NUMPY_MADVISE_HUGEPAGE=0 MPLBACKEND=Agg PYTHONUNBUFFERED=1
export PYTHONPATH="$PWD:$PWD/src:$PWD/scripts" MPLCONFIGDIR="$PWD/outputs/hpc/matplotlib-${SLURM_JOB_ID}"
exec "${TDE_PYTHON:-$PWD/.venv-hpc/bin/python}" operations/review_composite_failure.py --run "${TDE_RUN:?}"
