#!/usr/bin/env bash
#SBATCH --job-name=tde-localize
#SBATCH --partition=Students
#SBATCH --qos=qos_stu_default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:20:00
#SBATCH --output=outputs/hpc/logs/%x-%j.out
#SBATCH --error=outputs/hpc/logs/%x-%j.err
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export MPLBACKEND=Agg PYTHONUNBUFFERED=1 PYTHONPATH="$PWD:$PWD/src:$PWD/scripts"
"${TDE_PYTHON:-$PWD/.venv-hpc/bin/python}" operations/localize_confirmation.py \
 --run "${TDE_AUDIT_RUN:?}" --source-run "${TDE_SOURCE_RUN:?}"
