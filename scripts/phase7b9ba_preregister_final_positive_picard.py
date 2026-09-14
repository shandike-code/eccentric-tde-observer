"""Phase 7B9ba：冻结固定物质辐射场的最终正 Picard 收敛序列。"""

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


def main() -> None:
    basis = json.loads(
        (OUTPUT / "phase7b9ay_fused_constrained_anderson_summary.json").read_text(
            encoding="utf-8"
        )
    )
    audit = json.loads(
        (OUTPUT / "phase7b9az_second_constrained_candidate_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        basis["decision"]["fused_constrained_anderson_passed"] is not True
        or audit["decision"]["candidate_written"] is not False
        or audit["gate_checks"]["frequency_ownership_pass"] is not True
        or audit["gate_checks"]["selected_positive_pass"] is not True
        or audit["decision"]["material_feedback_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9ba requires the audited I3 Picard control")
    initial_relative = str(basis["x4_state_path"])
    scratch_relative = str(basis["x2_state_path"])
    initial = ROOT / initial_relative
    scratch = ROOT / scratch_relative
    if helper._sha256(initial) != basis["x4_state_sha256"]:
        raise RuntimeError("Phase 7B9ba initial I3 state changed")
    if helper._sha256(scratch) != basis["x2_state_sha256"]:
        raise RuntimeError("Phase 7B9ba scratch state changed")
    if initial.stat().st_size != scratch.stat().st_size:
        raise RuntimeError("Phase 7B9ba buffers have different sizes")
    control = next(row for row in audit["grid"] if row["eta"] == 0.0)
    payload = {
        "phase": "7B9ba final fixed-matter positive Picard convergence",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] alternate two existing full-frequency buffers for at "
            "most 24 unrelaxed original source maps starting from the audited I3 "
            "control; [V] every map audits its input residual, positivity, boundary, "
            "contraction, ownership and resources; [O] material feedback opens only "
            "after an audited input residual below 1e-4"
        ),
        "sources": {
            "phase7b9ay_summary": helper._source(
                "outputs/phase7b9ay_fused_constrained_anderson_summary.json"
            ),
            "phase7b9az_summary": helper._source(
                "outputs/phase7b9az_second_constrained_candidate_summary.json"
            ),
            "phase7b9az_protocol": helper._source(
                "outputs/phase7b9az_preregistered_second_constrained_candidate.json"
            ),
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
            "phase_index": 1375,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_picard_maps": 24,
            "maximum_concurrent_processes": 2,
            "initial_state_path": initial_relative,
            "initial_state_sha256": basis["x4_state_sha256"],
            "scratch_state_path": scratch_relative,
            "scratch_state_initial_sha256": basis["x2_state_sha256"],
            "raw_float64_checkpoint_size_bytes": initial.stat().st_size,
            "manifest_path": (
                "outputs/checkpoints/phase7b9ba_final_positive_picard/manifest.json"
            ),
            "report_directory": (
                "outputs/checkpoints/phase7b9ba_final_positive_picard/reports"
            ),
            "summary_path": (
                "outputs/phase7b9ba_final_positive_picard_summary.json"
            ),
            "figure_path": "outputs/phase7b9ba_final_positive_picard.png",
            "runner_path": "scripts/phase7b9ba_final_positive_picard.py",
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback_during_sequence": False,
        },
        "reference": {
            "initial_global_residual": control["global_residual"],
            "initial_boundary_spectrum_l1": control["boundary_spectrum_l1"],
            "initial_boundary_bolometric_fraction": control[
                "boundary_bolometric_fraction"
            ],
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "minimum_input_and_mapped_intensity_at_least": 0.0,
            "initial_audit_absolute_tolerance": 2.0e-12,
            "global_original_operator_residual_below": 1.0e-4,
            "subsequent_residual_contraction_ratio_below": 0.99,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_worker_wall_time_strictly_below_s": 60.0,
            "each_full_map_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "alternate_existing_buffers_if_each_map_gate_passes": True,
            "accept_audited_radiation_state_if_residual_gate_passes": True,
            "material_feedback_only_after_convergence": True,
            "accept_dynamic_nlte_solution": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9ba_preregistered_final_positive_picard.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
