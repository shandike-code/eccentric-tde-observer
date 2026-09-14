"""Phase 7B9bq：预注册完整红黑 Krylov 周期的全局审计。"""

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
    candidate = json.loads((OUTPUT / "phase7b9bp_odd_block_krylov_summary.json").read_text(encoding="utf-8"))
    prior = json.loads((OUTPUT / "phase7b9be_third_candidate_audit_summary.json").read_text(encoding="utf-8"))
    if candidate["decision"]["full_red_black_cycle_global_audit_authorized"] is not True or prior["decision"]["continue_positive_iteration_authorized"] is not True:
        raise RuntimeError("Phase 7B9bq requires the completed red-black cycle")
    state_relative = str(candidate["candidate_state_path"])
    if helper._sha256(ROOT / state_relative) != candidate["candidate_state_sha256"]:
        raise RuntimeError("Phase 7B9bq candidate changed")
    payload = {
        "phase": "7B9bq full red-black cycle global original-operator audit",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] one fresh full-frequency original fixed-matter map "
            "after both red-black half-sweeps; [V] positivity, maximum-norm "
            "contraction, boundary and resources; [O] matter feedback only below 1e-4"
        ),
        "sources": {
            "phase7b9bp_summary": helper._source("outputs/phase7b9bp_odd_block_krylov_summary.json"),
            "phase7b9bp_protocol": helper._source("outputs/phase7b9bp_preregistered_odd_block_krylov.json"),
            "phase7b9be_summary": helper._source("outputs/phase7b9be_third_candidate_audit_summary.json"),
            "candidate_state": helper._source(state_relative),
            "finite_trial_protocol": helper._source("outputs/phase7b9i_preregistered_finite_trial_radiation.json"),
            "finite_trial_material": helper._source("outputs/phase7b9i_finite_trial_material_state.npz"),
            "phase7b5p_master_input": helper._source("outputs/phase7b5p_master_worker_input.npz"),
            "generic_audit_runner": helper._source("scripts/phase7b9ad_picard_contraction_audit.py"),
            "phase7b9ab_audit_worker": helper._source("scripts/phase7b9ab_global_trial_residual_audit.py"),
            "mixed_frame_operator": helper._source("src/eccentric_tde_observer/mixed_frame_ale.py"),
            "mixed_frame_frequency": helper._source("src/eccentric_tde_observer/mixed_frame_frequency.py"),
        },
        "configuration": {
            "phase_index": 1390,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "maximum_concurrent_processes": 2,
            "input_state_path": state_relative,
            "input_state_sha256": candidate["candidate_state_sha256"],
            "report_directory": "outputs/checkpoints/phase7b9bq_red_black_cycle_audit/reports",
            "summary_path": "outputs/phase7b9bq_red_black_cycle_audit_summary.json",
            "figure_path": "outputs/phase7b9bq_red_black_cycle_audit.png",
            "block_report_prefix": "phase7b9bq",
            "runner_path": "scripts/phase7b9bq_red_black_cycle_audit.py",
            "prior_map_summary_source_key": "phase7b9be_summary",
            "prior_global_residual_key": "mapped_state_global_original_operator_residual",
            "prior_report_residual_key": "block_relative_original_operator_residual",
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
            "minimum_intensity_at_least": 0.0,
            "global_original_operator_residual_below": 1.0e-4,
            "residual_contraction_ratio_below": 0.90,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_worker_wall_time_strictly_below_s": 30.0,
        },
        "authorization": {
            "repeat_red_black_cycle_if_mapping_valid_but_above_target": True,
            "material_feedback_only_if_global_residual_gate_passes": True,
        },
    }
    path = OUTPUT / "phase7b9bq_preregistered_red_black_cycle_audit.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
