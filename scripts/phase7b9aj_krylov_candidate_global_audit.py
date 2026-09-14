"""Phase 7B9aj：执行主导能段 Krylov 候选的全局审计。"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts import phase7b9ad_picard_contraction_audit as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ad_picard_contraction_audit as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "5131d5ccd25be2639e9916a63687edc806c89c65c5dcfa29c8aac9cbe2cae92e"
)


def main() -> None:
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            OUTPUT / "phase7b9aj_preregistered_krylov_candidate_global_audit.json"
        ),
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if (
            args.block_index is None
            or args.input_state is None
            or args.input_sha256 is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires block, input state/hash and report")
        generic._run_worker(
            args.protocol,
            args.block_index,
            args.input_state,
            args.input_sha256,
            args.worker_report,
        )
        return
    generic.run(args.protocol)


if __name__ == "__main__":
    main()
