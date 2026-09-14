"""Phase 7B9p：冻结含 Doppler 频率串扰的局域 ALI 代表块准入门。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SELECTED_BLOCKS = {
    15: "optical fast-mode control",
    25: "H I threshold and largest map-6 residual",
    45: "He I slow threshold block",
    60: "soft-X-ray positivity control",
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
        (OUTPUT / "phase7b9o_static_diagonal_ali_pilot_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        manifest["status"] != "pilot_failed"
        or int(manifest["current_map"]) != 6
        or manifest["uncommitted_iteration"] is not None
        or prior["decision"]["static_diagonal_ali_pilot_passed"] is not False
        or prior["decision"]["one_full_frequency_static_diagonal_ali_map_authorized"]
        is not False
        or prior["decision"]["doppler_frequency_coupled_preconditioner_required"]
        is not True
    ):
        raise RuntimeError("Phase 7B9p requires the completed 7B9o failure state")
    current = ROOT / manifest["current_state_path"]
    if _sha256(current) != manifest["current_state_sha256"]:
        raise RuntimeError("Phase 7B9p current map-6 state changed")
    worker_sources = {
        f"map6_worker_block{index:02d}": _source(
            f"outputs/checkpoints/phase7b9i_work/reports/"
            f"block_aitken_map06_block{index:02d}.json"
        )
        for index in SELECTED_BLOCKS
    }
    payload = {
        "phase": "7B9p Doppler-frequency-coupled local ALI pilot",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] exact non-turning step-characteristic Lambda diagonal, "
            "raw positive turning-ray upwind diagonal and an iteratively converged "
            "local Lorentz frequency-scattering inverse; [V] fresh original-operator "
            "residual; [O] spatially nonlocal Lambda coupling remains outside the inverse"
        ),
        "sources": {
            "phase7b9o_summary": _source(
                "outputs/phase7b9o_static_diagonal_ali_pilot_summary.json"
            ),
            "phase7b9o_protocol": _source(
                "outputs/phase7b9o_preregistered_static_diagonal_ali_pilot.json"
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
            "signed_remap_controls": _source(
                "tests/test_mixed_frame_frequency.py"
            ),
            "phase7b7i_worker": _source(
                "scripts/phase7b7i_second_radiation_map.py"
            ),
            "phase7b9o_worker_helpers": _source(
                "scripts/phase7b9o_static_diagonal_ali_pilot.py"
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
            "lambda_diagonal": (
                "exact cell-average response for non-turning step characteristics; "
                "raw positive upwind matrix diagonal for turning grazing rays"
            ),
            "local_inverse": (
                "full signed lab-to-comoving intensity remap, comoving isotropic "
                "scattering and signed comoving-to-lab emissivity remap"
            ),
            "local_inverse_tolerance": 1.0e-10,
            "local_inverse_maximum_iterations": 32,
            "spatially_nonlocal_lambda_inside_preconditioner": False,
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
            "selected_block_count_exactly": 4,
            "each_local_inverse_converged": True,
            "each_local_inverse_relative_residual_at_most": 1.0e-10,
            "each_local_inverse_iteration_count_at_most": 32,
            "each_local_inverse_maximum_contraction_below": 0.90,
            "each_exact_nonnegative_step_at_least": 0.10,
            "each_fresh_candidate_to_raw_residual_ratio_below": 0.50,
            "median_fresh_candidate_to_raw_residual_ratio_below": 0.25,
            "each_candidate_boundary_residual_ratio_at_most": 1.0,
            "minimum_candidate_intensity_at_least": 0.0,
            "each_process_peak_rss_strictly_below_mib": 7168.0,
            "selected_runtime_multiplier_over_one_map_below": 6.0,
            "projected_full_map_wall_time_strictly_below_s": 2700.0,
        },
        "authorization": {
            "one_full_frequency_doppler_coupled_ali_map_if_gate_passes": True,
            "formal_trial_h_he_feedback": False,
            "trial_true_residual": False,
            "accept_trial_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9p_preregistered_doppler_coupled_ali_pilot.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
