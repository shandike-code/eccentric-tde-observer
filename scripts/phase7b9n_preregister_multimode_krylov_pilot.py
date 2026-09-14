"""Phase 7B9n：冻结代表块的多模最小残差 Krylov 准入门。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SELECTED_BLOCKS = {
    15: "optical fast-mode control",
    25: "largest map-6 residual and H I threshold crossing",
    45: "He I slow threshold block",
    60: "soft-X-ray positivity-limited block",
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
        (OUTPUT / "phase7b9m_exact_positive_mode_pilot_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        manifest["status"] != "pilot_failed"
        or int(manifest["current_map"]) != 6
        or manifest["uncommitted_iteration"] is not None
        or prior["decision"]["exact_positive_dominant_mode_pilot_passed"] is not False
        or prior["decision"][
            "one_full_frequency_exact_positive_mode_map_authorized"
        ]
        is not False
    ):
        raise RuntimeError("Phase 7B9n requires the exact completed 7B9m failure state")
    current = ROOT / manifest["current_state_path"]
    if _sha256(current) != manifest["current_state_sha256"]:
        raise RuntimeError("Phase 7B9n current map-6 state changed")
    worker_sources = {
        f"map6_worker_block{index:02d}": _source(
            f"outputs/checkpoints/phase7b9i_work/reports/"
            f"block_aitken_map06_block{index:02d}.json"
        )
        for index in SELECTED_BLOCKS
    }
    payload = {
        "phase": "7B9n representative-block multimode minimum-residual pilot",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] affine residual subspaces of sizes 3, 5 and 7, "
            "unregularized normalized Gram systems and one exact-positive selected "
            "candidate; [V] fresh original-operator residual; [O] no full map"
        ),
        "sources": {
            "phase7b9m_summary": _source(
                "outputs/phase7b9m_exact_positive_mode_pilot_summary.json"
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
            "affine_krylov_module": _source(
                "src/eccentric_tde_observer/affine_krylov.py"
            ),
            "phase7b7i_worker": _source(
                "scripts/phase7b7i_second_radiation_map.py"
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
            "source_residual_history_count_exactly": 7,
            "candidate_subspace_sizes": [3, 5, 7],
            "candidate_selection": (
                "lowest predicted max-norm original residual among finite subspaces "
                "passing the condition gate and exact nonnegative affine step"
            ),
            "maximum_normalized_gram_condition": 1.0e12,
            "maximum_concurrent_processes": 1,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "neighbor_guard_state": "frozen at committed finite-trial map 6",
            "matter_state": "frozen finite protected quasi-Newton trial",
            "gram_regularization": False,
            "singular_value_truncation": False,
            "coefficient_clipping": False,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "selected_block_count_exactly": 4,
            "each_selected_subspace_exists": True,
            "each_exact_nonnegative_step_at_least": 0.10,
            "each_fresh_candidate_to_raw_residual_ratio_below": 0.50,
            "median_fresh_candidate_to_raw_residual_ratio_below": 0.25,
            "each_prediction_to_fresh_residual_linf_below": 2.0e-10,
            "each_candidate_boundary_residual_ratio_at_most": 1.0,
            "minimum_candidate_intensity_at_least": 0.0,
            "each_process_peak_rss_strictly_below_mib": 7168.0,
            "selected_runtime_multiplier_over_one_map_below": 6.0,
            "projected_full_map_wall_time_strictly_below_s": 2700.0,
        },
        "authorization": {
            "one_full_frequency_multimode_map_if_gate_passes": True,
            "any_scalar_acceleration": False,
            "block_internal_picard": False,
            "formal_trial_h_he_feedback": False,
            "trial_true_residual": False,
            "accept_trial_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9n_preregistered_multimode_krylov_pilot.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
