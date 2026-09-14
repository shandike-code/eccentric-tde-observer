"""Phase 7B9bf：执行当前受约束候选的仿射 Krylov 映射。"""

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
EXPECTED_PROTOCOL_SHA256 = "4566d3ed2808f45253e5c94a765eda81f934b5ab92ee73748e4ba312ba65c261"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "outputs/phase7b9bf_preregistered_candidate_affine_map.json",
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
