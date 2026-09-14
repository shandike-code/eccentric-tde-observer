"""Phase 7B9bc：执行慢模态三连态的第三轮融合 Anderson。"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts import phase7b9ay_fused_constrained_anderson as engine
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ay_fused_constrained_anderson as engine  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "4d4804b5c349c3c088a1c4dc1ec7e2b2f19e488c3bf1f3de7bb946d93272d174"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "outputs/phase7b9bc_preregistered_third_fused_anderson.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    engine.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    if args.worker:
        if args.block_index is None or args.output_state is None or args.worker_report is None:
            raise ValueError("worker mode requires block, output and report")
        engine._run_worker(args.protocol, args.block_index, args.output_state, args.worker_report)
        return
    engine.run(args.protocol)


if __name__ == "__main__":
    main()
