"""Phase 7B9bc：冻结慢模态三连态的第三轮融合 Anderson。"""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from scripts import phase7b9ay_preregister_fused_constrained_anderson as helper
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ay_preregister_fused_constrained_anderson as helper  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SHAPE = (9632, 32, 4096)


def main() -> None:
    sequence = json.loads(
        (OUTPUT / "phase7b9ba_final_positive_picard_summary.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (
            OUTPUT / "checkpoints/phase7b9ba_final_positive_picard/manifest.json"
        ).read_text(encoding="utf-8")
    )
    if (
        sequence["status"] != "running"
        or len(manifest["iterations"]) != 8
        or manifest["active_iteration"] is not None
        or sequence["decision"]["material_feedback_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9bc requires the paused eight-map sequence")
    previous = manifest["iterations"][6]
    latest = manifest["iterations"][7]
    if (
        previous["mapped_state_sha256"] != latest["input_state_sha256"]
        or previous["mapped_state_path"] != latest["input_state_path"]
        or previous["map_passed"] is not True
        or latest["map_passed"] is not True
    ):
        raise RuntimeError("Phase 7B9bc states are not consecutive")
    x1_relative = str(previous["input_state_path"])
    x2_relative = str(previous["mapped_state_path"])
    x3_relative = str(latest["mapped_state_path"])
    expected = {
        x1_relative: previous["input_state_sha256"],
        x2_relative: previous["mapped_state_sha256"],
        x3_relative: latest["mapped_state_sha256"],
    }
    for relative, digest in expected.items():
        if helper._sha256(ROOT / relative) != digest:
            raise RuntimeError(f"Phase 7B9bc state changed: {relative}")
    x1 = ROOT / x1_relative
    old_blocks = [
        helper._block_sha256(x1, start, min(start + 128, SHAPE[0]))
        for start in range(0, SHAPE[0], 128)
    ]
    payload = {
        "phase": "7B9bc third fused constrained Anderson on isolated slow mode",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] repeat the fused x4 map, residual Gram solve and at "
            "most ten normalized pointwise-positivity cutting-plane scans on the "
            "consecutive I9,I10,I11 slow-mode history; [V] recoverable storage, "
            "ownership, positivity, boundary and resources; [O] the constrained "
            "candidate still requires a fresh maximum-norm and mapped-positivity audit"
        ),
        "sources": {
            "phase7b9ba_summary": helper._source(
                "outputs/phase7b9ba_final_positive_picard_summary.json"
            ),
            "phase7b9ba_protocol": helper._source(
                "outputs/phase7b9ba_preregistered_final_positive_picard.json"
            ),
            "x2_state": helper._source(x2_relative),
            "x3_state": helper._source(x3_relative),
            "finite_trial_protocol": helper._source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": helper._source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": helper._source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "fused_anderson_engine": helper._source(
                "scripts/phase7b9ay_fused_constrained_anderson.py"
            ),
            "anderson_engine": helper._source(
                "scripts/phase7b9ar_global_anderson_coefficients.py"
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
            "phase_index": 1376,
            "physical_frequency_groups": SHAPE[0],
            "angular_direction_count": SHAPE[1],
            "radiation_depth_cell_count": SHAPE[2],
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "maximum_concurrent_processes": 2,
            "x1_state_path": x1_relative,
            "x1_state_sha256": previous["input_state_sha256"],
            "x1_old_block_sha256": old_blocks,
            "x2_state_path": x2_relative,
            "x2_state_sha256": previous["mapped_state_sha256"],
            "x3_state_path": x3_relative,
            "x3_state_sha256": latest["mapped_state_sha256"],
            "x4_output_path": x1_relative,
            "raw_float64_checkpoint_size_bytes": x1.stat().st_size,
            "report_directory": (
                "outputs/checkpoints/phase7b9bc_third_fused_anderson/reports"
            ),
            "manifest_path": (
                "outputs/checkpoints/phase7b9bc_third_fused_anderson/manifest.json"
            ),
            "summary_path": (
                "outputs/phase7b9bc_third_fused_anderson_summary.json"
            ),
            "runner_path": "scripts/phase7b9bc_third_fused_anderson.py",
            "maximum_cutting_plane_iterations": 10,
            "constraint_direction_duplicate_tolerance": 1.0e-12,
            "slsqp_function_tolerance": 1.0e-18,
            "slsqp_maximum_iterations": 2000,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "kkt_regularization": False,
            "matter_feedback": False,
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": SHAPE[0],
            "gram_condition_number_below": 1.0e12,
            "coefficient_sum_absolute_error_below": 1.0e-10,
            "minimum_x3_and_x4_intensity_at_least": 0.0,
            "final_negative_candidate_count_exactly": 0,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "worker_wall_time_strictly_below_s": 180.0,
            "map_wall_time_strictly_below_s": 1200.0,
            "constraint_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "overwrite_obsolete_x1_with_x4": True,
            "maximum_norm_and_mapped_positivity_candidate_audit_after_x4": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9bc_preregistered_third_fused_anderson.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
