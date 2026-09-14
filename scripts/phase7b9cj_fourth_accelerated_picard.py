"""Phase 7B9cj：执行第四段可恢复的正 Picard 延拓。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_seeded_picard as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_seeded_picard as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "e9be80b7503985fbaa5226db5bf5886c8b1f34193f340e56f94cbbb885035190"


def main() -> None:
    generic.run_cli(
        EXPECTED_PROTOCOL_SHA256,
        ROOT / "outputs/phase7b9cj_preregistered_fourth_accelerated_picard.json",
    )


if __name__ == "__main__":
    main()
