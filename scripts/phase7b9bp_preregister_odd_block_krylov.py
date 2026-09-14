"""Phase 7B9bp：预注册红黑周期的奇数块 Krylov 半扫。"""

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
OUTPUT_STATE = "outputs/checkpoints/phase7b6h_full_frequency_residual8.dat"
ODD_BLOCKS = [19, 21, 23, 25, 27, 29, 31, 33, 35, 37, 39, 43, 45, 47, 49]


def main() -> None:
    even = json.loads((OUTPUT / "phase7b9bn_even_block_candidate_summary.json").read_text(encoding="utf-8"))
    audit = json.loads((OUTPUT / "phase7b9bo_even_block_map_summary.json").read_text(encoding="utf-8"))
    if even["decision"]["fresh_global_map_authorized"] is not True or audit["decision"]["even_half_sweep_accepted"] is not False:
        raise RuntimeError("Phase 7B9bp requires the diagnosed even red-black intermediate")
    even_reports = {int(row["block_index"]): row for row in audit["reports"]}
    if not all(even_reports[index]["maximum_absolute_radiation_change"] < 0.25 * json.loads((OUTPUT / "phase7b9be_third_candidate_audit_summary.json").read_text(encoding="utf-8"))["reports"][index]["maximum_absolute_original_operator_change"] for index in even["selected_even_blocks"]):
        raise RuntimeError("Phase 7B9bp even-block local contraction diagnosis changed")
    current = ROOT / even["candidate_state_path"]
    output = ROOT / OUTPUT_STATE
    if helper._sha256(current) != even["candidate_state_sha256"] or output.stat().st_size != current.stat().st_size:
        raise RuntimeError("Phase 7B9bp current or output scratch changed")
    selected = [{"block_index": index, "role": "odd red-black neighbor recomputed against the frozen even half-sweep"} for index in ODD_BLOCKS]
    worker_sources = {f"map6_worker_block{index:02d}": helper._source(f"outputs/checkpoints/phase7b9i_work/reports/block_aitken_map06_block{index:02d}.json") for index in ODD_BLOCKS}
    payload = {
        "phase": "7B9bp odd-block full-source Krylov half-sweep",
        "protocol_version": 1,
        "classification": (
            "[A-solver] complete the red-black cycle by recomputing every selected "
            "odd block against the frozen even intermediate; [A-preregistered] local "
            "original-operator, positivity, affine-prediction and boundary gates; "
            "[V] disjoint block ownership; [O] full-cycle global audit required"
        ),
        "sources": {
            "phase7b9bn_summary": helper._source("outputs/phase7b9bn_even_block_candidate_summary.json"),
            "phase7b9bo_summary": helper._source("outputs/phase7b9bo_even_block_map_summary.json"),
            "current_map6_state": helper._source(even["candidate_state_path"]),
            "finite_trial_protocol": helper._source("outputs/phase7b9i_preregistered_finite_trial_radiation.json"),
            "finite_trial_material": helper._source("outputs/phase7b9i_finite_trial_material_state.npz"),
            "phase7b5p_master_input": helper._source("outputs/phase7b5p_master_worker_input.npz"),
            "mixed_frame_operator": helper._source("src/eccentric_tde_observer/mixed_frame_ale.py"),
            "mixed_frame_frequency": helper._source("src/eccentric_tde_observer/mixed_frame_frequency.py"),
            "ali_preconditioner": helper._source("src/eccentric_tde_observer/mixed_frame_ali.py"),
            "affine_line_search": helper._source("src/eccentric_tde_observer/affine_krylov.py"),
            "phase7b7i_worker": helper._source("scripts/phase7b7i_second_radiation_map.py"),
            "phase7b9r_worker_helpers": helper._source("scripts/phase7b9r_full_source_krylov_line_search.py"),
            **worker_sources,
        },
        "configuration": {
            "phase_index": 1389,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "selected_blocks": selected,
            "selection_rule": {"red_black_color": "odd", "selected_block_count": len(selected), "even_intermediate_is_not_an_accepted_global_solution": True},
            "spatial_scheme": "hybrid_step_turning_upwind",
            "gmres_relative_tolerance": 1.0e-5,
            "gmres_restart": 8,
            "gmres_maximum_restart_cycles": 2,
            "maximum_gmres_iterations": 16,
            "incomplete_finite_krylov_candidate_allowed_for_diagnostic": True,
            "endpoint_exact_global_nonnegative_step": True,
            "line_search_interval": [0.0, 1.0],
            "neighbor_guard_state": "frozen even red-black intermediate",
            "unselected_block_state": "unchanged even red-black intermediate",
            "current_state_path": even["candidate_state_path"],
            "current_state_sha256": even["candidate_state_sha256"],
            "output_state_path": OUTPUT_STATE,
            "output_state_previous_sha256": helper._sha256(output),
            "raw_float64_checkpoint_size_bytes": current.stat().st_size,
            "copy_frequency_chunk": 32,
            "maximum_concurrent_processes": 2,
            "manifest_path": "outputs/checkpoints/phase7b9bp_odd_krylov/manifest.json",
            "report_directory": "outputs/checkpoints/phase7b9bp_odd_krylov/reports",
            "summary_path": "outputs/phase7b9bp_odd_block_krylov_summary.json",
            "figure_path": "outputs/phase7b9bp_odd_block_krylov.png",
            "runner_path": "scripts/phase7b9bp_odd_block_krylov.py",
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
            "initialize_output_with_even_intermediate": True,
            "write_only_disjoint_odd_blocks": True,
            "fresh_global_original_operator_audit_only_after_all_local_gates_pass": True,
            "material_feedback": False,
        },
    }
    path = OUTPUT / "phase7b9bp_preregistered_odd_block_krylov.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
