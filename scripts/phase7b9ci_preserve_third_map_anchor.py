"""Phase 7B9ci：保存第三次 Anderson 映射态的字节一致锚点。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_checkpoint_copy as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_checkpoint_copy as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "bb1e862f932600315f0d2f45282ff563b7f316bf97b790cb01a69b7d00fb6578"


def main() -> None:
    generic.run(
        ROOT / "outputs/phase7b9ci_preregistered_third_map_anchor.json",
        EXPECTED_PROTOCOL_SHA256,
    )


if __name__ == "__main__":
    main()
