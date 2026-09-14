"""Phase 7B9t：冻结一次全频率完整源 Krylov 映射。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
BLOCK_COUNT = 76


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
        (OUTPUT / "phase7b9s_four_block_full_source_gate_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        manifest["status"] != "pilot_failed"
        or int(manifest["current_map"]) != 6
        or manifest["uncommitted_iteration"] is not None
        or prior["decision"]["full_source_krylov_four_block_gate_passed"] is not True
        or prior["decision"]["one_full_frequency_full_source_krylov_map_authorized"]
        is not True
    ):
        raise RuntimeError("Phase 7B9t requires the completed 7B9s pass state")
    current = ROOT / manifest["current_state_path"]
    if _sha256(current) != manifest["current_state_sha256"]:
        raise RuntimeError("Phase 7B9t current map-6 state changed")
    output_buffer = OUTPUT / "checkpoints/phase7b9i_work/state_a.dat"
    if (
        output_buffer.stat().st_size != current.stat().st_size
        or _sha256(output_buffer)
        != "00798c8eb68412dc9301e0a0f7f4ac0644575ce8d05ab940310e7c6c40ef7901"
    ):
        raise RuntimeError("Phase 7B9t reusable map-5 buffer changed before freezing")
    worker_sources = {
        f"map6_worker_block{index:02d}": _source(
            f"outputs/checkpoints/phase7b9i_work/reports/"
            f"block_aitken_map06_block{index:02d}.json"
        )
        for index in range(BLOCK_COUNT)
    }
    payload = {
        "phase": "7B9t one full-frequency full-source Krylov radiation map",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] apply the Phase 7B9s sixteen-step full mixed-frame "
            "source Krylov and exact affine line search independently to all 76 "
            "natural frequency blocks; [V] blockwise fresh original-operator and "
            "ownership audit; [O] material feedback and next global residual remain "
            "separate stages"
        ),
        "sources": {
            "phase7b9s_summary": _source(
                "outputs/phase7b9s_four_block_full_source_gate_summary.json"
            ),
            "phase7b9s_protocol": _source(
                "outputs/phase7b9s_preregistered_four_block_full_source_gate.json"
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
            "affine_line_search": _source(
                "src/eccentric_tde_observer/affine_krylov.py"
            ),
            "phase7b7i_worker": _source(
                "scripts/phase7b7i_second_radiation_map.py"
            ),
            "phase7b9r_worker_helpers": _source(
                "scripts/phase7b9r_full_source_krylov_line_search.py"
            ),
            **worker_sources,
        },
        "configuration": {
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": BLOCK_COUNT,
            "selected_blocks": [
                {"block_index": index, "role": "full-frequency production block"}
                for index in range(BLOCK_COUNT)
            ],
            "spatial_scheme": "hybrid_step_turning_upwind",
            "gmres_relative_tolerance": 1.0e-5,
            "gmres_restart": 8,
            "gmres_maximum_restart_cycles": 2,
            "maximum_gmres_iterations": 16,
            "incomplete_finite_krylov_candidate_allowed_for_diagnostic": True,
            "endpoint_exact_global_nonnegative_step": True,
            "line_search_interval": [0.0, 1.0],
            "maximum_concurrent_processes": 1,
            "current_state_path": manifest["current_state_path"],
            "current_state_sha256": manifest["current_state_sha256"],
            "output_state_path": "outputs/checkpoints/phase7b9i_work/state_a.dat",
            "output_state_previous_role": "completed map-5 alternating buffer",
            "output_state_previous_sha256": (
                "00798c8eb68412dc9301e0a0f7f4ac0644575ce8d05ab940310e7c6c40ef7901"
            ),
            "raw_float64_checkpoint_size_bytes": current.stat().st_size,
            "storage_strategy": (
                "overwrite only the previous map-5 alternating buffer block by block; "
                "preserve committed map 6, residual buffer and retained map 3"
            ),
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "block_count_exactly": BLOCK_COUNT,
            "owned_frequency_group_count_exactly": 9632,
            "each_frequency_group_owned_exactly_once": True,
            "each_gmres_iteration_count_at_most": 16,
            "each_endpoint_exact_nonnegative_step_at_least": 0.10,
            "each_selected_line_fraction_at_least": 0.02,
            "each_fresh_line_candidate_to_raw_residual_ratio_below": 0.50,
            "median_fresh_line_candidate_to_raw_residual_ratio_below": 0.25,
            "each_fresh_line_candidate_boundary_ratio_at_most": 1.0,
            "each_affine_prediction_to_fresh_residual_linf_below": 2.0e-8,
            "minimum_line_candidate_intensity_at_least": 0.0,
            "each_process_peak_rss_strictly_below_mib": 7168.0,
            "full_map_wall_time_strictly_below_s": 9000.0,
        },
        "authorization": {
            "commit_candidate_map_if_all_gates_pass": True,
            "evaluate_next_global_original_operator_residual_if_committed": True,
            "formal_trial_h_he_feedback": False,
            "trial_true_residual": False,
            "accept_trial_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9t_preregistered_full_frequency_krylov_map.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
