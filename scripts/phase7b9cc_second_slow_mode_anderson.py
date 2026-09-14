"""Phase 7B9cc：执行第二次受保护 Anderson(1) 慢模外推。"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts import phase7b9bx_slow_mode_anderson as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9bx_slow_mode_anderson as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "0525aa74d3a46b9d77f9b563c827d704fe81595dfd6508d158fdf57e8fc92a6c"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            ROOT / "outputs/phase7b9cc_preregistered_second_slow_mode_anderson.json"
        ),
    )
    args = parser.parse_args()
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    generic.run(args.protocol)


if __name__ == "__main__":
    main()
