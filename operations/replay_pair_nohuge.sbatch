#!/usr/bin/env bash
#SBATCH --job-name=tde-pair-nohuge
#SBATCH --partition=Students
#SBATCH --qos=qos_stu_cpu_long
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=128G
#SBATCH --exclude=anode01
#SBATCH --time=00:30:00
#SBATCH --output=outputs/hpc/logs/%x-%j.out
#SBATCH --error=outputs/hpc/logs/%x-%j.err
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export NUMPY_MADVISE_HUGEPAGE=0
export PYTHONPATH="$PWD:$PWD/src:$PWD/scripts" PYTHONUNBUFFERED=1 MPLBACKEND=Agg
export MPLCONFIGDIR="$PWD/outputs/hpc/matplotlib-${SLURM_JOB_ID}"
exec "${TDE_PYTHON:-$PWD/.venv-hpc/bin/python}" operations/replay_pair_nohuge.py --run "${TDE_REPLAY_RUN:?}"
