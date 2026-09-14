"""Phase 7B9bm：执行加入目标块方向的正性约束仿射 Krylov 组合。"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts import phase7b9bh_positive_affine_krylov as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9bh_positive_affine_krylov as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "6b5ca6d77b0c7e658d60991b661e1a67b35b1c0152daac5947e17726770bbf11"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=ROOT / "outputs/phase7b9bm_preregistered_augmented_affine_krylov.json")
    args = parser.parse_args()
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    generic.run(args.protocol)


if __name__ == "__main__":
    main()
