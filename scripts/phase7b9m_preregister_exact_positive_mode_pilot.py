"""Phase 7B9m：冻结无经验上界的逐块精确正性 Aitken 审计。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SELECTED_BLOCKS = {
    15: "optical continuum control",
    25: "largest map-6 residual and H I threshold crossing",
    26: "immediately above the H I threshold",
    45: "He I threshold",
    51: "He II threshold",
    60: "soft-X-ray continuum",
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
    manifest_path = OUTPUT / "checkpoints/phase7b9i_work/block_aitken_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    phase7b9k = json.loads(
        (OUTPUT / "phase7b9k_block_aitken_pilot_summary.json").read_text(
            encoding="utf-8"
        )
    )
    phase7b9l = json.loads(
        (OUTPUT / "phase7b9l_block_implicit_pilot_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        manifest["status"] != "pilot_failed"
        or int(manifest["current_map"]) != 6
        or manifest["uncommitted_iteration"] is not None
        or len(manifest["previous_weights_by_block"]) != 76
        or phase7b9k["decision"]["continue_block_aitken_authorized"] is not False
        or phase7b9l["decision"][
            "one_full_frequency_block_implicit_map_authorized"
        ]
        is not False
    ):
        raise RuntimeError("Phase 7B9m requires the exact completed 7B9k/7B9l state")
    current = ROOT / manifest["current_state_path"]
    residual = ROOT / manifest["residual_buffer_path"]
    if _sha256(current) != manifest["current_state_sha256"]:
        raise RuntimeError("Phase 7B9m current map-6 state changed")
    worker_sources = {
        f"map6_worker_block{index:02d}": _source(
            f"outputs/checkpoints/phase7b9i_work/reports/"
            f"block_aitken_map06_block{index:02d}.json"
        )
        for index in SELECTED_BLOCKS
    }
    payload = {
        "phase": "7B9m exact-positive block dominant-mode pilot",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] one unconstrained vector-Aitken mode per selected "
            "natural block, limited only by exact whole-block positivity; [V] a fresh "
            "original-operator residual at every candidate; [O] no full-frequency map"
        ),
        "sources": {
            "phase7b9k_summary": _source(
                "outputs/phase7b9k_block_aitken_pilot_summary.json"
            ),
            "phase7b9l_summary": _source(
                "outputs/phase7b9l_block_implicit_pilot_summary.json"
            ),
            "phase7b9k_manifest": _source(
                "outputs/checkpoints/phase7b9i_work/block_aitken_manifest.json"
            ),
            "current_map6_state": _source(manifest["current_state_path"]),
            "previous_raw_residual": _source(manifest["residual_buffer_path"]),
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
            "maximum_concurrent_processes": 2,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "neighbor_guard_state": "frozen at committed finite-trial map 6",
            "matter_state": "frozen finite protected quasi-Newton trial",
            "aitken_formula": (
                "omega=-omega_previous<r_previous,r_new-r_previous>/"
                "||r_new-r_previous||^2"
            ),
            "positivity_boundary": (
                "min(I_k/(-r_new)) over negative residual entries; if active, use "
                "the adjacent lower floating-point value"
            ),
            "historical_weight_cap_applied": False,
            "cellwise_weight_tuning": False,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "selected_block_count_exactly": 6,
            "raw_unconstrained_weights_above_historical_5p87095_at_least": 2,
            "each_candidate_original_residual_ratio_below": 0.80,
            "median_candidate_original_residual_ratio_below": 0.35,
            "worst_map6_block25_candidate_residual_ratio_below": 0.50,
            "each_candidate_boundary_residual_ratio_at_most": 1.0,
            "minimum_candidate_intensity_at_least": 0.0,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "selected_runtime_multiplier_over_one_map_below": 3.5,
            "projected_full_map_wall_time_strictly_below_s": 1800.0,
        },
        "authorization": {
            "one_full_frequency_exact_positive_mode_map_if_gate_passes": True,
            "continue_bounded_block_aitken": False,
            "continue_block_internal_picard": False,
            "resume_plain_omega1": False,
            "formal_trial_h_he_feedback": False,
            "trial_true_residual": False,
            "accept_trial_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9m_preregistered_exact_positive_mode_pilot.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
