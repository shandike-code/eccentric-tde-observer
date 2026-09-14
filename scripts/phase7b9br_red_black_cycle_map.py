"""Phase 7B9br：执行失败红黑周期态的一次完整算子映射。"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts import phase7b9ac_global_positive_picard_map as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ac_global_positive_picard_map as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "18ddf8649d08be3c1b2f148328dd59de6964433f2e1555c9d8ff05c8a5a1cbce"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=ROOT / "outputs/phase7b9br_preregistered_red_black_cycle_map.json")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    if args.worker:
        if args.block_index is None or args.output_state is None or args.worker_report is None:
            raise ValueError("worker mode requires block, output and report")
        generic._run_worker(args.protocol, args.block_index, args.output_state, args.worker_report)
    else:
        generic.run(args.protocol)


if __name__ == "__main__":
    main()
