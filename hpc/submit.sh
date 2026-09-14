#!/usr/bin/env bash
# Submit from the repository root; overrides remain subject to account/QOS limits.
set -euo pipefail
cd "$(dirname "$0")/.."
mode="${1:-smoke}"
case "$mode" in
  smoke) default_time=00:30:00 ;;
  block-check) default_time=00:30:00 ;;
  verify) default_time=01:00:00 ;;
  resume) default_time=03:30:00 ;;
  pipeline) default_time=03:30:00; : "${TDE_RUN:?Set TDE_RUN=outputs/hpc/run-name}" ;;
  *) echo 'Usage: bash hpc/submit.sh smoke|block-check|verify|resume|pipeline' >&2; exit 2 ;;
esac
mkdir -p outputs/hpc/logs
exec sbatch --parsable --job-name="tde-${mode}" --nodes=1 --ntasks=1 \
  --partition="${TDE_PARTITION:-Students}" --qos="${TDE_QOS:-qos_stu_default}" \
  --cpus-per-task="${TDE_CPUS:-4}" --mem="${TDE_MEM:-16G}" \
  --time="${TDE_WALLTIME:-$default_time}" --signal=B:USR1@600 \
  --output='outputs/hpc/logs/%x-%j.out' --error='outputs/hpc/logs/%x-%j.err' \
  hpc/job.sbatch "$mode"
