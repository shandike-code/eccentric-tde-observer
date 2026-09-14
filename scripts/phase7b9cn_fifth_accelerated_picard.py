"""Phase 7B9cn：执行第五段可恢复的正 Picard 延拓。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_seeded_picard as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_seeded_picard as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "3c1c9bfdf7cae64f126a73aa6ef1a539a97ad1d834116acb29fb93f0ee581567"


def main() -> None:
    generic.run_cli(
        EXPECTED_PROTOCOL_SHA256,
        ROOT / "outputs/phase7b9cn_preregistered_fifth_accelerated_picard.json",
    )


if __name__ == "__main__":
    main()
