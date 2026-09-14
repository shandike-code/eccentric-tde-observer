"""Phase 7B9ct：执行冻结的两次低内存 Picard 延拓。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_seeded_picard as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_seeded_picard as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = (
    "31948e1a1c0ac5ae4b344bfba1c475e7555bc999e34b41b1d5c4966dbf658729"
)


def main() -> None:
    generic.run_cli(
        EXPECTED_PROTOCOL_SHA256,
        ROOT / "outputs/phase7b9ct_preregistered_two_map_tail.json",
    )


if __name__ == "__main__":
    main()
