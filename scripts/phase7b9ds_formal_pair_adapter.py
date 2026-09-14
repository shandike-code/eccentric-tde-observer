"""Phase 7B9ds：把冻结 final-radiation claim 注入既有 formal worker。"""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path

try:
    from scripts import phase7b9_formal_feedback_pair_adapter as adapter
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_formal_feedback_pair_adapter as adapter  # type: ignore[no-redef]


def _runtime_pair_protocol(protocol: dict[str, object]) -> dict[str, object]:
    claim = protocol.get("full_state_claims", {}).get("final_radiation")
    if not isinstance(claim, dict):
        raise RuntimeError("7B9ds final-radiation claim is missing")
    if "final_radiation" in protocol.get("sources", {}):
        raise RuntimeError("7B9ds protocol mixed source and claim state identities")
    runtime = deepcopy(protocol)
    runtime["sources"]["final_radiation"] = dict(claim)
    return runtime


def run_worker_adapter(
    protocol_path: Path,
    expected_sha256: str,
    state_label: str,
    block_index: int,
    partial_path: Path,
    report_path: Path,
) -> None:
    if state_label != "final":
        raise ValueError("7B9ds recomputes exactly the final feedback state")
    frozen = adapter.load_frozen_pair_protocol(
        protocol_path, expected_sha256, validate_sources=False
    )
    runtime = _runtime_pair_protocol(frozen)
    original_loader = adapter.load_frozen_pair_protocol
    try:
        # 中文：只给旧 worker 一个内存兼容视图，不改冻结协议字节。
        adapter.load_frozen_pair_protocol = lambda *_args, **_kwargs: runtime
        adapter.run_worker_adapter(
            protocol_path,
            expected_sha256,
            state_label,
            block_index,
            partial_path,
            report_path,
        )
    finally:
        adapter.load_frozen_pair_protocol = original_loader


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--state-label", choices=("previous", "final"), required=True)
    parser.add_argument("--block-index", type=int, required=True)
    parser.add_argument("--partial", type=Path, required=True)
    parser.add_argument("--worker-report", type=Path, required=True)
    args = parser.parse_args()
    if not args.worker:
        parser.error("7B9ds adapter only supports worker mode")
    run_worker_adapter(
        args.protocol,
        args.expected_protocol_sha256,
        args.state_label,
        args.block_index,
        args.partial,
        args.worker_report,
    )


if __name__ == "__main__":
    main()
