"""Phase 7B9cv：冻结 7B9cu 候选的一次完整 fresh map。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_protocol_builders as builder
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_protocol_builders as builder  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = "outputs/phase7b9cv_preregistered_candidate_fresh_map.json"


def main() -> None:
    payload = builder.build_memory_safe_candidate_map_protocol(
        ROOT,
        builder.MemorySafeCandidateMapProtocolSpec(
            phase="7B9cv fresh original-operator map of 7B9cu candidate",
            phase_index=1423,
            classification=(
                "[A-preregistered]+[V]+[O]：对通过代数门的 7B9cu 候选执行"
                "一次完整、无松弛的固定物质原算子映射；预测值不替代实际残差。"
            ),
            candidate_summary_path=(
                "outputs/phase7b9cu_protected_anderson_tail_summary.json"
            ),
            candidate_protocol_path=(
                "outputs/phase7b9cu_preregistered_protected_anderson_tail.json"
            ),
            candidate_summary_source_key="phase7b9cu_summary",
            candidate_protocol_source_key="phase7b9cu_protocol",
            # 中文：覆盖已被 cu 冻结谱系取代的旧 x10 缓冲，不增加 10 GiB 文件。
            output_state_path=(
                "outputs/checkpoints/phase7b6h_full_frequency_iteration8.dat"
            ),
            manifest_path=(
                "outputs/checkpoints/phase7b9cv_candidate_fresh_map/manifest.json"
            ),
            report_directory=(
                "outputs/checkpoints/phase7b9cv_candidate_fresh_map/reports"
            ),
            summary_path="outputs/phase7b9cv_candidate_fresh_map_summary.json",
            figure_path="outputs/phase7b9cv_candidate_fresh_map.png",
            block_report_prefix="phase7b9cv",
            runner_path="scripts/phase7b9cv_candidate_fresh_map.py",
        ),
    )
    print(builder.freeze_protocol(ROOT, PROTOCOL_PATH, payload))


if __name__ == "__main__":
    main()
