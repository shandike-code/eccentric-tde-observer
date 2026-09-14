"""Phase 7B9at：执行正性约束 Anderson 候选审计。"""

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
EXPECTED_PROTOCOL_SHA256 = "e2bbf18a635a524ebb083c7e099c3e4e511692f01057d5ee08ba34c5ac4d9240"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            ROOT
            / "outputs/phase7b9at_preregistered_constrained_anderson_candidate.json"
        ),
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    # 复用已验证的仿射候选引擎，但绑定本阶段独立冻结的协议哈希。
    engine.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    if args.worker:
        if args.block_index is None or args.worker_report is None:
            raise ValueError("worker mode requires block and report")
        engine._run_worker(args.protocol, args.block_index, args.worker_report)
        return
    engine.run(args.protocol)


if __name__ == "__main__":
    main()
