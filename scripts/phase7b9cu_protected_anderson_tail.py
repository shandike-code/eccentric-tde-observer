"""Phase 7B9cu：执行哈希锁定的受保护 Anderson(1) 尾段候选。"""

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
EXPECTED_PROTOCOL_SHA256 = "318c1213c38d6bd25c3d03c634a3d8c8fa2d1a31d7a45ff8545e223452f3d2cf"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            ROOT
            / "outputs/phase7b9cu_preregistered_protected_anderson_tail.json"
        ),
    )
    args = parser.parse_args()
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    generic.run(args.protocol)


if __name__ == "__main__":
    main()
