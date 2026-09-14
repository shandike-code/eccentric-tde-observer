"""Phase 7B9bq：执行完整红黑周期的全局原算子审计。"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts import phase7b9ad_picard_contraction_audit as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ad_picard_contraction_audit as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "27528331dd1dc5ce290fcf61e52e02b9da2b626da061557e16bdc5c7dc6b2acb"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=ROOT / "outputs/phase7b9bq_preregistered_red_black_cycle_audit.json")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    if args.worker:
        if args.block_index is None or args.input_state is None or args.input_sha256 is None or args.worker_report is None:
            raise ValueError("worker mode requires block, state/hash and report")
        generic._run_worker(args.protocol, args.block_index, args.input_state, args.input_sha256, args.worker_report)
    else:
        generic.run(args.protocol)


if __name__ == "__main__":
    main()
