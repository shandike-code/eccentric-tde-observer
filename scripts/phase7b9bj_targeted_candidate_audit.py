"""Phase 7B9bj：执行目标块 Krylov 候选的全频原算子审计。"""

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
EXPECTED_PROTOCOL_SHA256 = "c9a3b49559ce2f38037342e66839bf99a927a22028e0c9a43c40f148899f3cac"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "outputs/phase7b9bj_preregistered_targeted_candidate_audit.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    if args.worker:
        if (
            args.block_index is None
            or args.input_state is None
            or args.input_sha256 is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires block, state/hash and report")
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
