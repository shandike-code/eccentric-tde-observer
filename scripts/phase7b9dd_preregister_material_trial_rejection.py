"""Phase 7B9dd：冻结结构化物理域拒绝报告的材料续算。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_formal_feedback_pair_adapter as adapter
    from scripts import phase7b9dc_preregister_formal_material_continuation as base
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_formal_feedback_pair_adapter as adapter  # type: ignore[no-redef]
    import phase7b9dc_preregister_formal_material_continuation as base  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "outputs/phase7b9dd_preregistered_material_trial_rejection.json"


def main() -> None:
    payload = base.build_payload()
    payload["phase"] = (
        "7B9dd structured physical-domain decision for the finite material trial"
    )
    payload["classification"] = (
        "[A-preregistered]+[V-reproduction]+[V-physical-domain]+[O]："
        "复用已通过并复现的正式 feedback pair；物质响应若离开物理域则"
        "结构化拒绝，不写 target/residual，不接受动态 NLTE。"
    )
    payload["configuration"].update(
        {
            "phase_index": 1431,
            "feedback_work_directory": (
                "outputs/checkpoints/phase7b9dd_material_trial_rejection"
            ),
            "target_material_output": "outputs/phase7b9dd_target_material_state.npz",
            "encoded_residual_output": "outputs/phase7b9dd_encoded_residual.npy",
            "summary_path": "outputs/phase7b9dd_material_trial_rejection_summary.json",
            "figure_path": "outputs/phase7b9dd_material_trial_rejection.png",
        }
    )
    adapter._write_json_atomic(PROTOCOL_PATH, payload)
    print(adapter.sha256(PROTOCOL_PATH))


if __name__ == "__main__":
    main()
