"""Phase 7B9ba：执行固定物质辐射场的最终正 Picard 序列。"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts import phase7b9al_positive_picard_convergence as engine
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9al_positive_picard_convergence as engine  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "92506fb8ea9f3105b5ad9ce751733539cf0ea370f324c856c815d92bac2e7b8d"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "outputs/phase7b9ba_preregistered_final_positive_picard.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--stop-after-iteration", type=int)
    args = parser.parse_args()
    engine.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    if args.worker:
        if (
            args.iteration is None
            or args.block_index is None
            or args.input_state is None
            or args.input_sha256 is None
            or args.output_state is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires iteration, block and both states")
        engine._run_worker(
            args.protocol,
            args.iteration,
            args.block_index,
            args.input_state,
            args.input_sha256,
            args.output_state,
            args.worker_report,
        )
        return
    engine.run(args.protocol, stop_after_iteration=args.stop_after_iteration)


if __name__ == "__main__":
    main()
