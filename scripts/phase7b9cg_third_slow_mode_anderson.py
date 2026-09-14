"""Phase 7B9cg：执行第三次受保护 Anderson(1) 慢模外推。"""

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
EXPECTED_PROTOCOL_SHA256 = "589859c5f633a3cc0f9e313e6879d9a77d7d595a0636eb8703d7ea3b96aafe5c"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            ROOT / "outputs/phase7b9cg_preregistered_third_slow_mode_anderson.json"
        ),
    )
    args = parser.parse_args()
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    generic.run(args.protocol)


if __name__ == "__main__":
    main()
