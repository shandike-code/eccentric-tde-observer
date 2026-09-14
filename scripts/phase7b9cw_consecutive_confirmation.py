"""Phase 7B9cw：执行哈希锁定的连续低残差确认。"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts import phase7b9bv_consecutive_picard_confirmation as confirmation
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9bv_consecutive_picard_confirmation as confirmation  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "32e40f6b5ab33ad74f143d0e422df8d95b620e518cd8581eeb9c701c6b31816c"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "outputs/phase7b9cw_preregistered_consecutive_confirmation.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    confirmation.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    confirmation.generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    if args.worker:
        if (
            args.block_index is None
            or args.output_state is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires block, output state and report")
        confirmation.generic._run_worker(
            args.protocol,
            args.block_index,
            args.output_state,
            args.worker_report,
        )
        return
    confirmation.run(args.protocol)


if __name__ == "__main__":
    main()
