"""Phase 7B9ce：保存第二次 Anderson 映射态的字节一致锚点。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_checkpoint_copy as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_checkpoint_copy as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "4c136e49eca029c7db8f54b89f196117bbb79a07f8a6f31037cd9c1468675bc3"


def main() -> None:
    generic.run(
        ROOT / "outputs/phase7b9ce_preregistered_second_map_anchor.json",
        EXPECTED_PROTOCOL_SHA256,
    )


if __name__ == "__main__":
    main()
