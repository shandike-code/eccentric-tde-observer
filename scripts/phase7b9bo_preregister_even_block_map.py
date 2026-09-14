"""Phase 7B9bo：预注册偶数红黑候选的全局原算子映射。"""

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
MAP_OUTPUT = "outputs/checkpoints/phase7b6j_line_search_residual14.dat"


def main() -> None:
    candidate = json.loads((OUTPUT / "phase7b9bn_even_block_candidate_summary.json").read_text(encoding="utf-8"))
    base = json.loads((OUTPUT / "phase7b9be_third_candidate_audit_summary.json").read_text(encoding="utf-8"))
    if candidate["decision"]["fresh_global_map_authorized"] is not True or base["decision"]["continue_positive_iteration_authorized"] is not True:
        raise RuntimeError("Phase 7B9bo requires the gated even-block candidate")
    input_path = ROOT / candidate["candidate_state_path"]
    output_path = ROOT / MAP_OUTPUT
    if helper._sha256(input_path) != candidate["candidate_state_sha256"] or output_path.stat().st_size != input_path.stat().st_size:
        raise RuntimeError("Phase 7B9bo input or output scratch changed")
    payload = {
        "phase": "7B9bo even-block global original-operator map",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] first red-black block Gauss-Seidel half-sweep; "
            "[V] one complete original fixed-matter map, positivity, strict global "
            "contraction, boundary and resources; [O] odd half-sweep and matter feedback"
        ),
        "sources": {
            "phase7b9bn_summary": helper._source("outputs/phase7b9bn_even_block_candidate_summary.json"),
            "phase7b9be_summary": helper._source("outputs/phase7b9be_third_candidate_audit_summary.json"),
            "input_state": helper._source(candidate["candidate_state_path"]),
            "finite_trial_protocol": helper._source("outputs/phase7b9i_preregistered_finite_trial_radiation.json"),
            "finite_trial_material": helper._source("outputs/phase7b9i_finite_trial_material_state.npz"),
            "phase7b5p_master_input": helper._source("outputs/phase7b5p_master_worker_input.npz"),
            "generic_map_runner": helper._source("scripts/phase7b9ac_global_positive_picard_map.py"),
            "phase7b7i_worker": helper._source("scripts/phase7b7i_second_radiation_map.py"),
            "phase7b9d_worker_helpers": helper._source("scripts/phase7b9d_inner_converged_base_radiation.py"),
            "mixed_frame_operator": helper._source("src/eccentric_tde_observer/mixed_frame_ale.py"),
            "mixed_frame_frequency": helper._source("src/eccentric_tde_observer/mixed_frame_frequency.py"),
        },
        "configuration": {
            "phase_index": 1388,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "maximum_concurrent_processes": 2,
            "input_state_path": candidate["candidate_state_path"],
            "input_state_sha256": candidate["candidate_state_sha256"],
            "output_state_path": MAP_OUTPUT,
            "output_state_previous_sha256": helper._sha256(output_path),
            "raw_float64_checkpoint_size_bytes": input_path.stat().st_size,
            "prior_best_global_residual": base["mapped_state_global_original_operator_residual"],
            "manifest_path": "outputs/checkpoints/phase7b9bo_even_block_map/manifest.json",
            "report_directory": "outputs/checkpoints/phase7b9bo_even_block_map/reports",
            "summary_path": "outputs/phase7b9bo_even_block_map_summary.json",
            "figure_path": "outputs/phase7b9bo_even_block_map.png",
            "runner_path": "scripts/phase7b9bo_even_block_map.py",
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback": False,
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "minimum_input_and_mapped_intensity_at_least": 0.0,
            "global_residual_strictly_below_prior_best": base["mapped_state_global_original_operator_residual"],
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "full_map_wall_time_strictly_below_s": 1200.0,
            "fixed_matter_convergence_target": 1.0e-4,
        },
        "authorization": {
            "accept_even_half_sweep_only_if_all_gates_pass": True,
            "construct_odd_half_sweep_if_accepted_and_above_target": True,
            "material_feedback_only_if_below_target": True,
        },
    }
    path = OUTPUT / "phase7b9bo_preregistered_even_block_map.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
