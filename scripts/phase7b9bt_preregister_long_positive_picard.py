"""Phase 7B9bt：冻结可恢复的长正 Picard 收敛协议。"""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from scripts import phase7b9al_preregister_positive_picard_convergence as helper
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9al_preregister_positive_picard_convergence as helper  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
INITIAL_BUFFER = "outputs/checkpoints/phase7b6h_full_frequency_residual8.dat"
SCRATCH_BUFFER = "outputs/checkpoints/phase7b6h_full_frequency_iteration8.dat"


def main() -> None:
    audit = json.loads(
        (OUTPUT / "phase7b9be_third_candidate_audit_summary.json").read_text(
            encoding="utf-8"
        )
    )
    mapped = json.loads(
        (OUTPUT / "phase7b9bf_candidate_affine_map_summary.json").read_text(
            encoding="utf-8"
        )
    )
    red_black = json.loads(
        (OUTPUT / "phase7b9bq_red_black_cycle_audit_summary.json").read_text(
            encoding="utf-8"
        )
    )
    damped = json.loads(
        (OUTPUT / "phase7b9bs_damped_red_black_line_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        audit["decision"]["continue_positive_iteration_authorized"] is not True
        or audit["decision"]["material_feedback_authorized"] is not False
        or mapped["gate_checks"]["positive_map_pass"] is not True
        or red_black["decision"]["positive_picard_contraction_audit_passed"]
        is not False
        or damped["decision"]["fresh_global_original_operator_audit_authorized"]
        is not False
    ):
        raise RuntimeError("Phase 7B9bt requires the audited positive control")

    source_relative = str(audit["input_state_path"])
    source = ROOT / source_relative
    initial = ROOT / INITIAL_BUFFER
    scratch = ROOT / SCRATCH_BUFFER
    source_sha = helper._sha256(source)
    if source_sha != audit["input_state_sha256"]:
        raise RuntimeError("Phase 7B9bt audited source state changed")
    if source.stat().st_size != initial.stat().st_size or source.stat().st_size != scratch.stat().st_size:
        raise RuntimeError("Phase 7B9bt double-buffer sizes differ")

    payload = {
        "phase": "7B9bt long fixed-matter positive Picard convergence",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] copy the audited positive state into one named "
            "superseded checkpoint, then alternate two existing full-frequency "
            "buffers for at most 96 unrelaxed original source maps; [V] every map "
            "audits its input residual, positivity, boundary, contraction, ownership "
            "and resources; [O] matter feedback opens only below 1e-4"
        ),
        "sources": {
            "phase7b9be_summary": helper._source(
                "outputs/phase7b9be_third_candidate_audit_summary.json"
            ),
            "phase7b9bf_summary": helper._source(
                "outputs/phase7b9bf_candidate_affine_map_summary.json"
            ),
            "phase7b9bq_summary": helper._source(
                "outputs/phase7b9bq_red_black_cycle_audit_summary.json"
            ),
            "phase7b9bs_summary": helper._source(
                "outputs/phase7b9bs_damped_red_black_line_summary.json"
            ),
            "audited_initial_state": helper._source(source_relative),
            "finite_trial_protocol": helper._source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": helper._source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": helper._source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "generic_positive_picard_runner": helper._source(
                "scripts/phase7b9ac_global_positive_picard_map.py"
            ),
            "positive_sequence_engine": helper._source(
                "scripts/phase7b9al_positive_picard_convergence.py"
            ),
            "phase7b7i_worker": helper._source(
                "scripts/phase7b7i_second_radiation_map.py"
            ),
            "phase7b9d_worker_helpers": helper._source(
                "scripts/phase7b9d_inner_converged_base_radiation.py"
            ),
            "mixed_frame_operator": helper._source(
                "src/eccentric_tde_observer/mixed_frame_ale.py"
            ),
            "mixed_frame_frequency": helper._source(
                "src/eccentric_tde_observer/mixed_frame_frequency.py"
            ),
        },
        "configuration": {
            "phase_index": 1393,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_picard_maps": 96,
            "maximum_concurrent_processes": 2,
            "preparation_source_path": source_relative,
            "preparation_source_sha256": source_sha,
            "initial_state_path": INITIAL_BUFFER,
            "initial_state_sha256": source_sha,
            "initial_state_previous_sha256": helper._sha256(initial),
            "scratch_state_path": SCRATCH_BUFFER,
            "scratch_state_initial_sha256": helper._sha256(scratch),
            "raw_float64_checkpoint_size_bytes": source.stat().st_size,
            "preparation_status_path": (
                "outputs/checkpoints/phase7b9bt_long_positive_picard/preparation.json"
            ),
            "manifest_path": (
                "outputs/checkpoints/phase7b9bt_long_positive_picard/manifest.json"
            ),
            "report_directory": (
                "outputs/checkpoints/phase7b9bt_long_positive_picard/reports"
            ),
            "summary_path": (
                "outputs/phase7b9bt_long_positive_picard_summary.json"
            ),
            "figure_path": "outputs/phase7b9bt_long_positive_picard.png",
            "runner_path": "scripts/phase7b9bt_long_positive_picard.py",
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback_during_sequence": False,
        },
        "reference": {
            "initial_global_residual": audit[
                "mapped_state_global_original_operator_residual"
            ],
            "initial_boundary_spectrum_l1": audit[
                "mapped_state_boundary_spectrum_l1"
            ],
            "initial_boundary_bolometric_fraction": audit[
                "mapped_state_boundary_bolometric_fraction"
            ],
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "minimum_input_and_mapped_intensity_at_least": 0.0,
            "initial_audit_absolute_tolerance": 2.0e-12,
            "global_original_operator_residual_below": 1.0e-4,
            "subsequent_residual_contraction_ratio_below": 0.999,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_worker_wall_time_strictly_below_s": 60.0,
            "each_full_map_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "overwrite_only_named_superseded_initial_buffer": True,
            "alternate_existing_buffers_if_each_map_gate_passes": True,
            "accept_audited_radiation_state_if_residual_gate_passes": True,
            "material_feedback_only_after_convergence": True,
            "accept_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9bt_preregistered_long_positive_picard.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
