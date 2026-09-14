"""Phase 7B9cf：执行第三段可恢复的正 Picard 延拓。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_seeded_picard as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_seeded_picard as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "a2f8ca630742db0451af725e1aa6cb07ebd851e9cd88202984f604560ab948bb"


def main() -> None:
    generic.run_cli(
        EXPECTED_PROTOCOL_SHA256,
        ROOT / "outputs/phase7b9cf_preregistered_third_accelerated_picard.json",
    )


if __name__ == "__main__":
    main()
