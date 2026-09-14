"""Phase 7B9dc：执行哈希锁定的正式 feedback 材料续算。"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts import phase7b9_formal_feedback_pair_adapter as adapter
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_formal_feedback_pair_adapter as adapter  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "081bf198a27b69f942b586e60b32e5069661d9617fcdbed5371d385eb501db0e"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            ROOT
            / "outputs/phase7b9dc_preregistered_formal_material_continuation.json"
        ),
    )
    args = parser.parse_args()
    adapter.run_pair(args.protocol, EXPECTED_PROTOCOL_SHA256)


if __name__ == "__main__":
    main()
