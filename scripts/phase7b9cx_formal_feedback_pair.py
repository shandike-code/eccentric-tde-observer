"""Phase 7B9cx：执行哈希锁定的正式 H/He feedback pair。"""

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
EXPECTED_PROTOCOL_SHA256 = "c5c7d8b7485c339e778ecf8190956dcf69130233ec997c01fd3c86eb4d9ab117"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "outputs/phase7b9cx_preregistered_formal_feedback_pair.json",
    )
    args = parser.parse_args()
    adapter.run_pair(args.protocol, EXPECTED_PROTOCOL_SHA256)


if __name__ == "__main__":
    main()
