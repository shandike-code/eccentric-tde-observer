"""Phase 7B9cw：冻结两个连续低残差辐射态的确认映射。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts.phase7b9_candidate_map_confirmation_builder import (
        CandidateMapConsecutiveConfirmationSpec,
        build_candidate_map_consecutive_confirmation_protocol,
    )
    from scripts.phase7b9_protocol_builders import freeze_protocol
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b9_candidate_map_confirmation_builder import (  # type: ignore[no-redef]
        CandidateMapConsecutiveConfirmationSpec,
        build_candidate_map_consecutive_confirmation_protocol,
    )
    from phase7b9_protocol_builders import freeze_protocol  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = "outputs/phase7b9cw_preregistered_consecutive_confirmation.json"


def main() -> None:
    payload = build_candidate_map_consecutive_confirmation_protocol(
        ROOT,
        CandidateMapConsecutiveConfirmationSpec(
            phase="7B9cw second consecutive fixed-matter convergence confirmation",
            phase_index=1424,
            classification=(
                "[A-preregistered]+[V]+[O]：用一次 fresh、无松弛原算子映射"
                "审计 7B9cv 的后继态；两态均低于 1e-4 才开放正式 H/He 反馈。"
            ),
            candidate_map_summary_path=(
                "outputs/phase7b9cv_candidate_fresh_map_summary.json"
            ),
            candidate_map_protocol_path=(
                "outputs/phase7b9cv_preregistered_candidate_fresh_map.json"
            ),
            trial_residual_acceptance_path=(
                "outputs/phase7b9bu_preregistered_trial_residual_acceptance.json"
            ),
            # 中文：Z 只审计 Y 的残差；正式反馈使用协议冻结的 X/Y，而不是 Z。
            output_state_path=(
                "outputs/checkpoints/phase7b6h_full_frequency_residual8.dat"
            ),
            manifest_path=(
                "outputs/checkpoints/phase7b9cw_consecutive_confirmation/manifest.json"
            ),
            report_directory=(
                "outputs/checkpoints/phase7b9cw_consecutive_confirmation/reports"
            ),
            summary_path=(
                "outputs/phase7b9cw_consecutive_confirmation_summary.json"
            ),
            figure_path="outputs/phase7b9cw_consecutive_confirmation.png",
            block_report_prefix="phase7b9cw",
            runner_path="scripts/phase7b9cw_consecutive_confirmation.py",
        ),
    )
    print(freeze_protocol(ROOT, PROTOCOL_PATH, payload))


if __name__ == "__main__":
    main()
