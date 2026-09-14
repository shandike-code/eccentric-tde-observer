"""Phase 7B9ax：执行约束候选后的第二次正 Picard 映射。"""

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
EXPECTED_PROTOCOL_SHA256 = "fa54fe170fdad674c37fa2aba7b32b14ad00dad673e9702c2c58dc466a617c02"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            ROOT
            / "outputs/phase7b9ax_preregistered_second_candidate_picard_map.json"
        ),
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    if args.worker:
        if (
            args.block_index is None
            or args.output_state is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires block, output state and report")
        generic._run_worker(
            args.protocol, args.block_index, args.output_state, args.worker_report
        )
        return
    generic.run(args.protocol)


if __name__ == "__main__":
    main()
