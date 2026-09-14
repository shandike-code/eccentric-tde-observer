"""Phase 7B9cp：执行 Anderson 被拒后的长正 Picard 延拓。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_seeded_picard as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_seeded_picard as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "f48a77f20faaae0acc53965446a1cdbec7a8d9e47416660379530b81278f4efa"


def main() -> None:
    generic.run_cli(
        EXPECTED_PROTOCOL_SHA256,
        ROOT / "outputs/phase7b9cp_preregistered_long_positive_picard.json",
    )


if __name__ == "__main__":
    main()
