"""Phase 7B9dd：执行哈希锁定的有限物质试步判定。"""

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
EXPECTED_PROTOCOL_SHA256 = "ecd1bc47c996ddac9393ff48ab1d7faeb638e1dd57aa24f74266ed5a1c3234af"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "outputs/phase7b9dd_preregistered_material_trial_rejection.json",
    )
    args = parser.parse_args()
    adapter.run_pair(args.protocol, EXPECTED_PROTOCOL_SHA256)


if __name__ == "__main__":
    main()
