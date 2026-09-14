"""Phase 7B9cs：执行冻结的 APFS clone 并验证锚点字节哈希。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_new_checkpoint_copy as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_new_checkpoint_copy as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = (
    "2a2c27df9ebd6433b4566e7cce15e8925db22a7053fedfa253e71e7dd416a4b3"
)


def main() -> None:
    generic.run(
        ROOT / "outputs/phase7b9cs_preregistered_resource_tail_anchor.json",
        EXPECTED_PROTOCOL_SHA256,
    )


if __name__ == "__main__":
    main()
