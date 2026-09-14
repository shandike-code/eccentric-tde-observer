"""Phase 7B9ah：执行八步 Krylov 成本缩减小样。"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts import phase7b9ag_current_state_krylov_pilot as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ag_current_state_krylov_pilot as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "70301ea91532fa78cf9b82c16b0ab342989519b8db8b18c64bce4cc123a3a6cf"
)


def main() -> None:
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9ah_preregistered_eight_step_krylov_pilot.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.block_index is None or args.worker_report is None:
            raise ValueError("worker mode requires block and report")
        generic._run_worker(args.protocol, args.block_index, args.worker_report)
        return
    generic.run(args.protocol)


if __name__ == "__main__":
    main()
