"""Phase 7B9cx：冻结连续收敛辐射态的正式 H/He feedback pair。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_formal_feedback_pair_adapter as adapter
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_formal_feedback_pair_adapter as adapter  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "outputs/phase7b9cx_preregistered_formal_feedback_pair.json"


def main() -> None:
    payload = adapter.build_formal_feedback_pair_protocol(
        ROOT,
        adapter.FormalFeedbackPairProtocolSpec(
            phase="7B9cx formal H/He feedback pair from converged X/Y radiation",
            phase_index=1425,
            classification=(
                "[A-preregistered]+[V]+[O]：在冻结试步物质态上比较两个连续"
                "低残差辐射态的正式 H/He 率与加热；本阶段不接受动态 NLTE 解。"
            ),
            confirmation_summary_path=(
                "outputs/phase7b9cw_consecutive_confirmation_summary.json"
            ),
            confirmation_protocol_path=(
                "outputs/phase7b9cw_preregistered_consecutive_confirmation.json"
            ),
            trial_residual_acceptance_path=(
                "outputs/phase7b9bu_preregistered_trial_residual_acceptance.json"
            ),
            trial_material_summary_path=(
                "outputs/phase7b9i_finite_trial_material_summary.json"
            ),
            trial_material_path="outputs/phase7b9i_finite_trial_material_state.npz",
            base_feedback_summary_path=(
                "outputs/phase7b9f_converged_feedback_residual_summary.json"
            ),
            base_residual_path="outputs/phase7b9f_base_material_residual.npy",
            physical_old_time_level_path="outputs/phase7b4r_depth128_phase2048.npz",
            phase7b7j_protocol_path=(
                "outputs/phase7b7j_preregistered_second_assembled_feedback.json"
            ),
            phase7b7j_runner_path=(
                "scripts/phase7b7j_second_assembled_feedback.py"
            ),
            adapter_runner_path=(
                "scripts/phase7b9_formal_feedback_pair_adapter.py"
            ),
            feedback_work_directory=(
                "outputs/checkpoints/phase7b9cx_formal_feedback_pair"
            ),
            previous_feedback_output="outputs/phase7b9cx_previous_feedback.npz",
            final_feedback_output="outputs/phase7b9cx_final_feedback.npz",
            target_material_output="outputs/phase7b9cx_target_material_state.npz",
            encoded_residual_output="outputs/phase7b9cx_encoded_residual.npy",
            summary_path="outputs/phase7b9cx_formal_feedback_pair_summary.json",
            figure_path="outputs/phase7b9cx_formal_feedback_pair.png",
        ),
    )
    adapter._write_json_atomic(PROTOCOL_PATH, payload)
    print(adapter.sha256(PROTOCOL_PATH))


if __name__ == "__main__":
    main()
