"""Phase 7B9cu：冻结资源调整尾段的受保护 Anderson(1) 候选。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts.phase7b9_protocol_builders import (
        ProtectedAndersonTailProtocolSpec,
        build_protected_anderson_tail_protocol,
        freeze_protocol,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b9_protocol_builders import (  # type: ignore[no-redef]
        ProtectedAndersonTailProtocolSpec,
        build_protected_anderson_tail_protocol,
        freeze_protocol,
    )


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = "outputs/phase7b9cu_preregistered_protected_anderson_tail.json"


def main() -> None:
    payload = build_protected_anderson_tail_protocol(
        ROOT,
        ProtectedAndersonTailProtocolSpec(
            phase="7B9cu protected Anderson(1) after memory-safe two-map tail",
            phase_index=1422,
            classification=(
                "[A-informed]+[A-preregistered]+[V]+[O]：仅用冻结锚点与两次"
                "连续 fresh Picard map 估计慢模；候选仍须一次完整原算子映射确认。"
            ),
            continuation_summary_path=(
                "outputs/phase7b9ct_two_map_tail_summary.json"
            ),
            continuation_protocol_path=(
                "outputs/phase7b9ct_preregistered_two_map_tail.json"
            ),
            anchor_summary_path=(
                "outputs/phase7b9cs_resource_tail_anchor_summary.json"
            ),
            anchor_protocol_path=(
                "outputs/phase7b9cs_preregistered_resource_tail_anchor.json"
            ),
            anchor_continuation_decision_key=(
                "phase7b9ct_two_map_tail_authorized"
            ),
            # 中文：复用已被 cs 独立锚点取代的命名缓冲区，避免再分配 10 GiB。
            candidate_output_path=(
                "outputs/checkpoints/phase7b6f_full_frequency_iteration4.dat"
            ),
            summary_path=(
                "outputs/phase7b9cu_protected_anderson_tail_summary.json"
            ),
            figure_path="outputs/phase7b9cu_protected_anderson_tail.png",
        ),
    )
    print(freeze_protocol(ROOT, PROTOCOL_PATH, payload))


if __name__ == "__main__":
    main()
