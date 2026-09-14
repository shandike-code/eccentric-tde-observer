"""Phase 7B9bd：冻结第三轮正性约束 Anderson 候选审计。"""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from scripts import phase7b9at_preregister_constrained_anderson_candidate as helper
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9at_preregister_constrained_anderson_candidate as helper  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SHAPE = (9632, 32, 4096)


def main() -> None:
    source = json.loads(
        (OUTPUT / "phase7b9bc_third_fused_anderson_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        source["decision"]["fused_constrained_anderson_passed"] is not True
        or source["decision"][
            "maximum_norm_and_mapped_positivity_candidate_audit_authorized"
        ]
        is not True
        or source["decision"]["material_feedback_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9bd requires the constrained third basis")
    for label in ("x2", "x3", "x4"):
        if helper._sha256(ROOT / source[f"{label}_state_path"]) != source[
            f"{label}_state_sha256"
        ]:
            raise RuntimeError(f"Phase 7B9bd {label} state changed")
    x2 = ROOT / source["x2_state_path"]
    old_blocks = [
        helper._block_sha256(x2, start, min(start + 128, SHAPE[0]))
        for start in range(0, SHAPE[0], 128)
    ]
    payload = {
        "phase": "7B9bd third constrained Anderson candidate audit and write",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] audit the frozen third cutting-plane coefficient "
            "against the original maximum-norm operator, mapped-state positivity "
            "and boundary functionals, with x4 as the control; [V] one fresh F(x4), "
            "recoverable candidate write only after at least 20 percent improvement; "
            "[O] a written candidate still requires an independent global self audit"
        ),
        "sources": {
            "phase7b9bc_summary": helper._source(
                "outputs/phase7b9bc_third_fused_anderson_summary.json"
            ),
            "phase7b9bc_protocol": helper._source(
                "outputs/phase7b9bc_preregistered_third_fused_anderson.json"
            ),
            "x3_state": helper._source(source["x3_state_path"]),
            "x4_state": helper._source(source["x4_state_path"]),
            "finite_trial_protocol": helper._source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": helper._source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": helper._source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "candidate_engine": helper._source(
                "scripts/phase7b9as_damped_anderson_candidate.py"
            ),
            "affine_evaluator": helper._source(
                "scripts/phase7b9ak_global_convex_krylov_line.py"
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
            "phase_index": 1377,
            "physical_frequency_groups": SHAPE[0],
            "angular_direction_count": SHAPE[1],
            "radiation_depth_cell_count": SHAPE[2],
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "maximum_concurrent_processes": 2,
            "anderson_alpha": source["constrained_anderson_alpha"],
            "eta_grid": [0.0, 1.0],
            "x2_state_path": source["x2_state_path"],
            "x2_state_sha256": source["x2_state_sha256"],
            "x2_old_block_sha256": old_blocks,
            "x3_state_path": source["x3_state_path"],
            "x3_state_sha256": source["x3_state_sha256"],
            "x4_state_path": source["x4_state_path"],
            "x4_state_sha256": source["x4_state_sha256"],
            "candidate_output_path": source["x2_state_path"],
            "raw_float64_checkpoint_size_bytes": x2.stat().st_size,
            "audit_report_directory": (
                "outputs/checkpoints/phase7b9bd_third_candidate/audit_reports"
            ),
            "manifest_path": (
                "outputs/checkpoints/phase7b9bd_third_candidate/manifest.json"
            ),
            "summary_path": (
                "outputs/phase7b9bd_third_constrained_candidate_summary.json"
            ),
            "figure_path": "outputs/phase7b9bd_third_constrained_candidate.png",
            "runner_path": "scripts/phase7b9bd_third_constrained_candidate.py",
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback": False,
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": SHAPE[0],
            "coefficient_sum_absolute_error_below": 1.0e-12,
            "minimum_candidate_and_mapped_intensity_at_least": 0.0,
            "selected_residual_ratio_to_x4_below": 0.80,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_worker_wall_time_strictly_below_s": 180.0,
            "audit_wall_time_strictly_below_s": 1200.0,
            "write_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "write_selected_candidate_if_all_gates_pass": True,
            "fresh_global_self_audit_after_write": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9bd_preregistered_third_constrained_candidate.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
