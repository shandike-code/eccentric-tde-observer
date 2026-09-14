"""Phase 7B9bd：执行第三轮正性约束 Anderson 候选审计。"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts import phase7b9as_damped_anderson_candidate as engine
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9as_damped_anderson_candidate as engine  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "ffc4f97f2603e194fdbfdb9b3d8d105fb6bfc4f88c687506ab31a057169ffd54"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            ROOT
            / "outputs/phase7b9bd_preregistered_third_constrained_candidate.json"
        ),
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    engine.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    if args.worker:
        if args.block_index is None or args.worker_report is None:
            raise ValueError("worker mode requires block and report")
        engine._run_worker(args.protocol, args.block_index, args.worker_report)
        return
    engine.run(args.protocol)


if __name__ == "__main__":
    main()
