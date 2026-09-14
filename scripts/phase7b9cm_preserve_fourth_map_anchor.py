"""Phase 7B9cm：保存第四次 Anderson 映射态的字节一致锚点。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_checkpoint_copy as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_checkpoint_copy as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "069530b0340fb8bf326046594450ed99198b92bf2ab83d7ba79d149efc7427dd"


def main() -> None:
    generic.run(
        ROOT / "outputs/phase7b9cm_preregistered_fourth_map_anchor.json",
        EXPECTED_PROTOCOL_SHA256,
    )


if __name__ == "__main__":
    main()
