"""Phase 7B9ae：执行第二次全局正 Picard 映射。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts import phase7b9ac_global_positive_picard_map as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ac_global_positive_picard_map as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "8435337ec5146d53ac0dd769ae4d72e84a1ff04aae001b55c489126659f77933"
)


def main() -> None:
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9ae_preregistered_second_positive_picard_map.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
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
    print(json.dumps(generic.run(args.protocol), indent=2))


if __name__ == "__main__":
    main()
