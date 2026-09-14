"""Phase 7B9bi：冻结由最大绝对残差选择的 full-source Krylov 块。"""

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
SHAPE = (9632, 32, 4096)
OUTPUT_STATE = "outputs/checkpoints/phase7b6h_full_frequency_residual8.dat"
SELECTION_MARGIN = 0.5
TARGET_RESIDUAL = 1.0e-4


def main() -> None:
    audit = json.loads(
        (OUTPUT / "phase7b9be_third_candidate_audit_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        audit["decision"]["constrained_anderson_candidate_global_audit_passed"]
        is not True
        or audit["decision"]["continue_positive_iteration_authorized"] is not True
        or audit["decision"]["material_feedback_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9bi requires the audited positive current state")
    current_relative = str(audit["input_state_path"])
    current = ROOT / current_relative
    if helper._sha256(current) != audit["input_state_sha256"]:
        raise RuntimeError("Phase 7B9bi current state changed")
    reports = audit["reports"]
    global_scale = max(float(row["maximum_original_operator_scale"]) for row in reports)
    target_absolute_change = TARGET_RESIDUAL * global_scale
    selection_threshold = SELECTION_MARGIN * target_absolute_change
    selected = [
        {
            "block_index": int(row["block_index"]),
            "role": "baseline absolute residual exceeds half the 1e-4 global target",
            "baseline_maximum_absolute_change": float(
                row["maximum_absolute_original_operator_change"]
            ),
            "baseline_absolute_change_over_target": float(
                row["maximum_absolute_original_operator_change"]
            )
            / target_absolute_change,
        }
        for row in reports
        if float(row["maximum_absolute_original_operator_change"])
        >= selection_threshold
    ]
    indices = [row["block_index"] for row in selected]
    if indices != [19, *range(20, 41), 43, 44, 45, 46, 47, 48, 49]:
        raise RuntimeError(f"Phase 7B9bi selection changed: {indices}")
    output = ROOT / OUTPUT_STATE
    if output.stat().st_size != current.stat().st_size:
        raise RuntimeError("Phase 7B9bi scratch output has the wrong size")
    worker_sources = {
        f"map6_worker_block{index:02d}": helper._source(
            f"outputs/checkpoints/phase7b9i_work/reports/"
            f"block_aitken_map06_block{index:02d}.json"
        )
        for index in indices
    }
    payload = {
        "phase": "7B9bi targeted full-source Krylov block-Jacobi candidate",
        "protocol_version": 1,
        "classification": (
            "[A-solver] retain the complete audited positive current state and apply "
            "the already validated full mixed-frame source Krylov correction only to "
            "blocks whose baseline maximum absolute change exceeds half the absolute "
            "1e-4 global target; [A-preregistered] exact selection, local positivity, "
            "fresh block residual and boundary gates; [V] recoverable block ownership; "
            "[O] the assembled cross-block state requires one fresh global source map"
        ),
        "sources": {
            "phase7b9be_summary": helper._source(
                "outputs/phase7b9be_third_candidate_audit_summary.json"
            ),
            "phase7b9be_protocol": helper._source(
                "outputs/phase7b9be_preregistered_third_candidate_audit.json"
            ),
            "current_map6_state": helper._source(current_relative),
            "finite_trial_protocol": helper._source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": helper._source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": helper._source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "mixed_frame_operator": helper._source(
                "src/eccentric_tde_observer/mixed_frame_ale.py"
            ),
            "mixed_frame_frequency": helper._source(
                "src/eccentric_tde_observer/mixed_frame_frequency.py"
            ),
            "ali_preconditioner": helper._source(
                "src/eccentric_tde_observer/mixed_frame_ali.py"
            ),
            "affine_line_search": helper._source(
                "src/eccentric_tde_observer/affine_krylov.py"
            ),
            "phase7b7i_worker": helper._source(
                "scripts/phase7b7i_second_radiation_map.py"
            ),
            "phase7b9r_worker_helpers": helper._source(
                "scripts/phase7b9r_full_source_krylov_line_search.py"
            ),
            **worker_sources,
        },
        "configuration": {
            "phase_index": 1382,
            "physical_frequency_groups": SHAPE[0],
            "angular_direction_count": SHAPE[1],
            "radiation_depth_cell_count": SHAPE[2],
            "natural_frequency_block_count": 76,
            "selected_blocks": selected,
            "selection_rule": {
                "baseline_source": (
                    "outputs/phase7b9be_third_candidate_audit_summary.json"
                ),
                "global_intensity_scale": global_scale,
                "target_global_relative_residual": TARGET_RESIDUAL,
                "target_absolute_change": target_absolute_change,
                "selection_margin": SELECTION_MARGIN,
                "selected_if_maximum_absolute_change_at_least": selection_threshold,
                "selected_block_count": len(selected),
            },
            "spatial_scheme": "hybrid_step_turning_upwind",
            "gmres_relative_tolerance": 1.0e-5,
            "gmres_restart": 8,
            "gmres_maximum_restart_cycles": 2,
            "maximum_gmres_iterations": 16,
            "incomplete_finite_krylov_candidate_allowed_for_diagnostic": True,
            "endpoint_exact_global_nonnegative_step": True,
            "line_search_interval": [0.0, 1.0],
            "neighbor_guard_state": "frozen audited current state",
            "unselected_block_state": "unchanged audited current state",
            "current_state_path": current_relative,
            "current_state_sha256": audit["input_state_sha256"],
            "output_state_path": OUTPUT_STATE,
            "output_state_previous_sha256": helper._sha256(output),
            "raw_float64_checkpoint_size_bytes": current.stat().st_size,
            "copy_frequency_chunk": 32,
            "manifest_path": (
                "outputs/checkpoints/phase7b9bi_targeted_krylov/manifest.json"
            ),
            "report_directory": (
                "outputs/checkpoints/phase7b9bi_targeted_krylov/reports"
            ),
            "summary_path": (
                "outputs/phase7b9bi_targeted_full_source_krylov_summary.json"
            ),
            "figure_path": (
                "outputs/phase7b9bi_targeted_full_source_krylov.png"
            ),
            "runner_path": "scripts/phase7b9bi_targeted_full_source_krylov.py",
            "scratch_reuse_note": (
                "Only the named superseded Phase 7B6h residual-8 generated checkpoint "
                "may be overwritten; the audited current state remains unchanged"
            ),
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback": False,
        },
        "gates": {
            "selected_block_count_exactly": len(selected),
            "each_gmres_iteration_count_at_most": 16,
            "each_endpoint_exact_nonnegative_step_at_least": 0.10,
            "each_selected_line_fraction_at_least": 0.02,
            "each_fresh_line_candidate_to_raw_residual_ratio_below": 0.75,
            "each_fresh_line_candidate_boundary_ratio_at_most": 1.0,
            "each_affine_prediction_to_fresh_residual_linf_below": 2.0e-8,
            "minimum_line_candidate_intensity_at_least": 0.0,
            "each_process_peak_rss_strictly_below_mib": 7168.0,
            "targeted_map_wall_time_strictly_below_s": 6000.0,
        },
        "authorization": {
            "initialize_named_scratch_with_complete_current_state": True,
            "write_only_preregistered_target_blocks_as_diagnostic_candidate": True,
            "commit_candidate_only_if_every_local_gate_passes": True,
            "fresh_global_original_operator_audit_if_committed": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9bi_preregistered_targeted_full_source_krylov.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
