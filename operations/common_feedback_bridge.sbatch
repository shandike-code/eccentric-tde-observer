#!/usr/bin/env bash
#SBATCH --job-name=tde-common-feedback
#SBATCH --partition=Students
#SBATCH --qos=qos_stu_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:15:00
#SBATCH --output=outputs/hpc/logs/%x-%j.out
#SBATCH --error=outputs/hpc/logs/%x-%j.err
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export NUMPY_MADVISE_HUGEPAGE=0 MPLBACKEND=Agg PYTHONUNBUFFERED=1
export PYTHONPATH="$PWD:$PWD/src:$PWD/scripts"
exec "${TDE_PYTHON:-$PWD/.venv-hpc/bin/python}" operations/native_worker_relay.py \
 --receipt outputs/hpc/common-feedback-bridge-20260923.process.json -- \
 "${TDE_PYTHON:-$PWD/.venv-hpc/bin/python}" operations/common_feedback_bridge.py \
 --run outputs/hpc/common-feedback-bridge-20260923
