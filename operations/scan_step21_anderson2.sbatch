#!/usr/bin/env bash
#SBATCH --job-name=tde-step21-a2scan
#SBATCH --partition=Students
#SBATCH --qos=qos_stu_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --signal=B:USR1@120
#SBATCH --exclude=anode01
#SBATCH --output=outputs/hpc/logs/%x-%j.out
#SBATCH --error=outputs/hpc/logs/%x-%j.err
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export NUMPY_MADVISE_HUGEPAGE=0 MPLBACKEND=Agg PYTHONUNBUFFERED=1
export MPLCONFIGDIR="$PWD/outputs/hpc/matplotlib-${SLURM_JOB_ID}"
export PYTHONPATH="$PWD:$PWD/src:$PWD/scripts"
exec "${TDE_PYTHON:-$PWD/.venv-hpc/bin/python}" operations/scan_step21_anderson2.py --run outputs/hpc/step21-anderson2-scan-20260925
