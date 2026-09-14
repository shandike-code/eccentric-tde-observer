"""Phase 7B9co：执行第五次受保护 Anderson(1) 慢模外推。"""

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
EXPECTED_PROTOCOL_SHA256 = "15ec9d8f57e15e4414cfc1de51d181351c8c2bc211d5410f6d8b56d67386c616"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            ROOT / "outputs/phase7b9co_preregistered_fifth_slow_mode_anderson.json"
        ),
    )
    args = parser.parse_args()
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    generic.run(args.protocol)


if __name__ == "__main__":
    main()
