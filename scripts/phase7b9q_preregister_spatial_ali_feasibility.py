"""Phase 7B9q：冻结全深度静态频率 ALI 的两块可行性门。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SELECTED_BLOCKS = {
    15: "optical fast-mode control",
    45: "He I spatial slow-mode target",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _source(relative: str) -> dict[str, object]:
    path = ROOT / relative
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def main() -> None:
    manifest = json.loads(
        (
            OUTPUT / "checkpoints/phase7b9i_work/block_aitken_manifest.json"
        ).read_text(encoding="utf-8")
    )
    prior = json.loads(
        (OUTPUT / "phase7b9p_doppler_coupled_ali_pilot_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        manifest["status"] != "pilot_failed"
        or int(manifest["current_map"]) != 6
        or manifest["uncommitted_iteration"] is not None
        or prior["decision"]["doppler_coupled_local_ali_pilot_passed"] is not False
        or prior["decision"]["spatially_nonlocal_preconditioner_required"] is not True
    ):
        raise RuntimeError("Phase 7B9q requires the completed 7B9p failure state")
    current = ROOT / manifest["current_state_path"]
    if _sha256(current) != manifest["current_state_sha256"]:
        raise RuntimeError("Phase 7B9q current map-6 state changed")
    worker_sources = {
        f"map6_worker_block{index:02d}": _source(
            f"outputs/checkpoints/phase7b9i_work/reports/"
            f"block_aitken_map06_block{index:02d}.json"
        )
        for index in SELECTED_BLOCKS
    }
    payload = {
        "phase": "7B9q two-block static-frequency full-spatial ALI feasibility",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] matrix-free GMRES inverse of the exact signed "
            "step-characteristic depth response at fixed lab frequency, with the "
            "positive local Lambda diagonal as left preconditioner; [V] fresh "
            "mixed-frame original-operator residual; [O] only two blocks and no "
            "full-frequency authorization"
        ),
        "sources": {
            "phase7b9p_summary": _source(
                "outputs/phase7b9p_doppler_coupled_ali_pilot_summary.json"
            ),
            "phase7b9p_protocol": _source(
                "outputs/phase7b9p_preregistered_doppler_coupled_ali_pilot.json"
            ),
            "phase7b9k_manifest": _source(
                "outputs/checkpoints/phase7b9i_work/block_aitken_manifest.json"
            ),
            "current_map6_state": _source(manifest["current_state_path"]),
            "finite_trial_protocol": _source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": _source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "mixed_frame_operator": _source(
                "src/eccentric_tde_observer/mixed_frame_ale.py"
            ),
            "mixed_frame_frequency": _source(
                "src/eccentric_tde_observer/mixed_frame_frequency.py"
            ),
            "ali_preconditioner": _source(
                "src/eccentric_tde_observer/mixed_frame_ali.py"
            ),
            "exact_positive_step": _source(
                "src/eccentric_tde_observer/affine_krylov.py"
            ),
            "ali_controls": _source("tests/test_mixed_frame_ali.py"),
            "phase7b7i_worker": _source(
                "scripts/phase7b7i_second_radiation_map.py"
            ),
            "phase7b9p_worker_helpers": _source(
                "scripts/phase7b9p_doppler_coupled_ali_pilot.py"
            ),
            **worker_sources,
        },
        "configuration": {
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "selected_blocks": [
                {"block_index": index, "role": role}
                for index, role in SELECTED_BLOCKS.items()
            ],
            "spatial_scheme": "hybrid_step_turning_upwind",
            "spatial_lambda": (
                "exact signed full-depth step-characteristic response within each "
                "lab frequency; turning rays use the same conservative upwind solve"
            ),
            "frequency_coupling_inside_preconditioner": False,
            "gmres_relative_tolerance": 1.0e-5,
            "gmres_restart": 8,
            "gmres_maximum_restart_cycles": 4,
            "maximum_gmres_iterations": 32,
            "local_lambda_left_preconditioner": True,
            "fresh_original_operator_validation": True,
            "exact_global_nonnegative_affine_step": True,
            "neighbor_guard_state": "frozen at committed finite-trial map 6",
            "matter_state": "frozen finite protected quasi-Newton trial",
            "maximum_concurrent_processes": 1,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "selected_block_count_exactly": 2,
            "each_spatial_inverse_converged": True,
            "each_spatial_inverse_scaled_linf_residual_at_most": 1.0e-4,
            "each_spatial_inverse_mean_consistency_at_most": 1.0e-4,
            "each_gmres_iteration_count_at_most": 32,
            "each_exact_nonnegative_step_at_least": 0.10,
            "each_fresh_candidate_to_raw_residual_ratio_below": 0.50,
            "median_fresh_candidate_to_raw_residual_ratio_below": 0.25,
            "each_candidate_boundary_residual_ratio_at_most": 1.0,
            "minimum_candidate_intensity_at_least": 0.0,
            "each_process_peak_rss_strictly_below_mib": 7168.0,
            "selected_runtime_multiplier_over_one_map_below": 20.0,
            "projected_full_map_wall_time_strictly_below_s": 7200.0,
        },
        "authorization": {
            "four_block_spatial_ali_gate_if_feasibility_passes": True,
            "one_full_frequency_spatial_ali_map": False,
            "formal_trial_h_he_feedback": False,
            "trial_true_residual": False,
            "accept_trial_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9q_preregistered_spatial_ali_feasibility.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
