"""Freeze the Phase 7B9de fixed-material radiation continuation bundle."""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_half_trial_radiation_continuation as continuation
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_half_trial_radiation_continuation as continuation  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "outputs/phase7b9dh_preregistered_half_trial_radiation.json"


def main() -> None:
    spec = continuation.HalfTrialRadiationContinuationSpec(
        phase="7B9dh 0.0625 fixed-material radiation continuation",
        phase_index=1432,
        classification=(
            "[A-preregistered]+[A-initialization]+[V-lineage]+[O]：固定 0.0625 "
            "物质候选，只做原始全频率 Picard 内迭代；首个低残差态仅允许 "
            "provisional feedback extraction，下一连续 fresh residual 通过前不作正式判决。"
        ),
        material_protocol_path=(
            "outputs/phase7b9de_preregistered_half_trial_material.json"
        ),
        material_summary_path="outputs/phase7b9de_half_trial_material_summary.json",
        storage_authorization_path=(
            "outputs/phase7b9dg_preregistered_storage_reuse.json"
        ),
        initial_radiation_claim_protocol_path=(
            "outputs/phase7b9dd_preregistered_material_trial_rejection.json"
        ),
        finite_radiation_template_path=(
            "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
        ),
        fixed_material_worker_template_path=(
            "outputs/phase7b9dh_fixed_material_radiation_worker_template.json"
        ),
        runner_path=continuation.RUNNER_RELATIVE_PATH,
        initialization_receipt_path=(
            "outputs/checkpoints/phase7b9dh_half_trial_radiation/"
            "initialization_receipt.json"
        ),
        manifest_path=(
            "outputs/checkpoints/phase7b9dh_half_trial_radiation/manifest.json"
        ),
        transient_report_directory=(
            "outputs/checkpoints/phase7b9dh_transient_reports"
        ),
        summary_path="outputs/phase7b9dh_half_trial_radiation_summary.json",
        figure_path="outputs/phase7b9dh_half_trial_radiation.png",
    )
    _, digest = continuation.write_protocol_bundle(ROOT, spec, PROTOCOL_PATH)
    print(digest)


if __name__ == "__main__":
    main()
