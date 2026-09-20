#!/usr/bin/env bash
#SBATCH --job-name=tde-recent-subspace
#SBATCH --partition=Students
#SBATCH --qos=qos_stu_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --exclude=anode01
#SBATCH --output=outputs/hpc/logs/%x-%j.out
#SBATCH --error=outputs/hpc/logs/%x-%j.err
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export NUMPY_MADVISE_HUGEPAGE=0 MPLBACKEND=Agg
export MPLCONFIGDIR="$PWD/outputs/hpc/matplotlib-${SLURM_JOB_ID}"
export PYTHONPATH="$PWD:$PWD/src:$PWD/scripts" PYTHONUNBUFFERED=1
exec "${TDE_PYTHON:-$PWD/.venv-hpc/bin/python}" operations/scan_recent_positive_subspace.py --run "${TDE_SCAN_RUN:?}"
