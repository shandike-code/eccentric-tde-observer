"""Phase 7B9ax：冻结约束候选后的第二次正 Picard 映射。"""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from scripts import phase7b9av_preregister_candidate_picard_map as helper
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9av_preregister_candidate_picard_map as helper  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def main() -> None:
    scan = json.loads(
        (OUTPUT / "phase7b9aw_fixed_overrelaxation_scan_summary.json").read_text(
            encoding="utf-8"
        )
    )
    history = json.loads(
        (OUTPUT / "phase7b9ar_global_anderson_coefficients_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        scan["selected_theta"] != 1.0
        or scan["decision"]["resume_positive_picard_authorized"] is not True
        or scan["decision"]["material_feedback_authorized"] is not False
        or scan["gate_checks"]["theta_zero_reproduction_pass"] is not True
        or scan["gate_checks"]["selected_positive_pass"] is not True
    ):
        raise RuntimeError("Phase 7B9ax requires the positive theta=1 continuation")
    input_relative = str(scan["upper_state_path"])
    output_relative = str(history["x4_state_path"])
    input_state = ROOT / input_relative
    output_state = ROOT / output_relative
    if helper._sha256(input_state) != scan["upper_state_sha256"]:
        raise RuntimeError("Phase 7B9ax input state changed")
    if helper._sha256(output_state) != history["x4_state_sha256"]:
        raise RuntimeError("Phase 7B9ax reusable x4 buffer changed")
    payload = {
        "phase": "7B9ax second post-Anderson positive Picard map",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] apply one unrelaxed original source map to the theta=1 "
            "positive continuation selected by Phase 7B9aw; [V] recoverable ownership, "
            "positivity, residual reproduction, boundary and resource audit; [O] the "
            "new state remains fixed-matter radiation only"
        ),
        "sources": {
            "phase7b9aw_summary": helper._source(
                "outputs/phase7b9aw_fixed_overrelaxation_scan_summary.json"
            ),
            "phase7b9aw_protocol": helper._source(
                "outputs/phase7b9aw_preregistered_fixed_overrelaxation_scan.json"
            ),
            "input_state": helper._source(input_relative),
            "finite_trial_protocol": helper._source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": helper._source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": helper._source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "generic_map_runner": helper._source(
                "scripts/phase7b9ac_global_positive_picard_map.py"
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
            "phase_index": 1372,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "accepted_source_relaxation_exactly": 1.0,
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "maximum_concurrent_processes": 2,
            "input_state_path": input_relative,
            "input_state_sha256": scan["upper_state_sha256"],
            "output_state_path": output_relative,
            "output_state_previous_sha256": history["x4_state_sha256"],
            "raw_float64_checkpoint_size_bytes": input_state.stat().st_size,
            "manifest_path": (
                "outputs/checkpoints/phase7b9ax_second_candidate_picard/manifest.json"
            ),
            "report_directory": (
                "outputs/checkpoints/phase7b9ax_second_candidate_picard/reports"
            ),
            "summary_path": (
                "outputs/phase7b9ax_second_candidate_picard_map_summary.json"
            ),
            "figure_path": (
                "outputs/phase7b9ax_second_candidate_picard_map.png"
            ),
            "block_report_prefix": "phase7b9ax",
            "runner_path": "scripts/phase7b9ax_second_candidate_picard_map.py",
            "input_audit_source_key": "phase7b9aw_summary",
            "input_audit_residual_key": "selected_global_residual",
            "input_audit_boundary_l1_key": "selected_boundary_spectrum_l1",
            "input_audit_bolometric_key": (
                "selected_boundary_bolometric_fraction"
            ),
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback_during_map": False,
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "each_frequency_group_owned_exactly_once": True,
            "minimum_input_and_mapped_intensity_at_least": 0.0,
            "input_global_residual_matches_phase7b9ab_absolute_tolerance": 2.0e-12,
            "input_boundary_metrics_match_phase7b9ab_absolute_tolerance": 2.0e-12,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "full_map_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "commit_recoverable_mapped_state_if_all_map_gates_pass": True,
            "construct_depth_two_anderson_if_map_passes": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9ax_preregistered_second_candidate_picard_map.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
