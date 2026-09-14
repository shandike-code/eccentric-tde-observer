"""Phase 7B9dc：冻结已复现正式 feedback artifact 的材料续算。"""

from __future__ import annotations

import json
from pathlib import Path

try:
    from scripts import phase7b9_formal_feedback_pair_adapter as adapter
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_formal_feedback_pair_adapter as adapter  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = (
    ROOT / "outputs/phase7b9dc_preregistered_formal_material_continuation.json"
)
CZ_PROTOCOL = "outputs/phase7b9cz_preregistered_formal_feedback_pair.json"
CZ_PREVIOUS_MANIFEST = (
    "outputs/checkpoints/phase7b9cz_formal_feedback_pair/previous_manifest.json"
)
CZ_FINAL_MANIFEST = (
    "outputs/checkpoints/phase7b9cz_formal_feedback_pair/final_manifest.json"
)
REPRODUCTION_AUDIT = "outputs/phase7b9db_feedback_block_reproduction_audit.json"


def _manifest(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def build_payload() -> dict[str, object]:
    audit = _manifest(REPRODUCTION_AUDIT)
    previous = _manifest(CZ_PREVIOUS_MANIFEST)
    final = _manifest(CZ_FINAL_MANIFEST)
    cz_sha = adapter.sha256(ROOT / CZ_PROTOCOL)
    if (
        audit.get("decision", {}).get(
            "phase7b9cz_formal_feedback_artifacts_reusable"
        )
        is not True
        or previous.get("protocol_sha256") != cz_sha
        or final.get("protocol_sha256") != cz_sha
        or any(
            manifest.get("status") != "complete"
            or manifest.get("state_gate_passed") is not True
            for manifest in (previous, final)
        )
    ):
        raise RuntimeError("Phase 7B9dc requires reproduced, passed feedback artifacts")
    payload = adapter.build_formal_feedback_pair_protocol(
        ROOT,
        adapter.FormalFeedbackPairProtocolSpec(
            phase="7B9dc material continuation from reproduced formal feedback pair",
            phase_index=1430,
            classification=(
                "[A-preregistered]+[V-reproduction]+[V]+[O]：复用逐字冻结且"
                "状态门通过的 7B9cz feedback artifacts，仅续算有限物质试步判据。"
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
                "outputs/phase7b9cy_refreshed_feedback_worker_template.json"
            ),
            phase7b7j_runner_path=(
                "scripts/phase7b7j_second_assembled_feedback.py"
            ),
            adapter_runner_path=(
                "scripts/phase7b9_formal_feedback_pair_adapter.py"
            ),
            feedback_work_directory=(
                "outputs/checkpoints/phase7b9dc_formal_material_continuation"
            ),
            previous_feedback_output="outputs/phase7b9dc_unused_previous_feedback.npz",
            final_feedback_output="outputs/phase7b9dc_unused_final_feedback.npz",
            target_material_output="outputs/phase7b9dc_target_material_state.npz",
            encoded_residual_output="outputs/phase7b9dc_encoded_residual.npy",
            summary_path=(
                "outputs/phase7b9dc_formal_material_continuation_summary.json"
            ),
            figure_path="outputs/phase7b9dc_formal_material_continuation.png",
        ),
    )
    previous_artifact = str(previous["feedback_artifact_path"])
    final_artifact = str(final["feedback_artifact_path"])
    payload["sources"].update(
        {
            "phase7b9cz_protocol": adapter._source(ROOT, CZ_PROTOCOL),
            "previous_feedback_manifest": adapter._source(
                ROOT, CZ_PREVIOUS_MANIFEST
            ),
            "final_feedback_manifest": adapter._source(ROOT, CZ_FINAL_MANIFEST),
            "previous_feedback_artifact": adapter._source(
                ROOT, previous_artifact
            ),
            "final_feedback_artifact": adapter._source(ROOT, final_artifact),
            "phase7b9db_reproduction_audit": adapter._source(
                ROOT, REPRODUCTION_AUDIT
            ),
            "phase7b9db_independent_block49": adapter._source(
                ROOT,
                "outputs/checkpoints/phase7b9db_block49_reproduction/previous_block49.npz",
            ),
        }
    )
    payload["configuration"].update(
        {
            "reuse_completed_feedback_manifests": True,
            "feedback_origin_protocol_sha256": cz_sha,
        }
    )
    payload["authorization"].update(
        {
            "evaluate_exactly_two_formal_feedback_states": False,
            "reuse_exactly_two_completed_formal_feedback_states": True,
            "reuse_only_after_bytewise_reproduction_audit": True,
        }
    )
    return payload


def main() -> None:
    adapter._write_json_atomic(PROTOCOL_PATH, build_payload())
    print(adapter.sha256(PROTOCOL_PATH))


if __name__ == "__main__":
    main()
