"""Phase 7B9l：冻结代表频率块的块内多次散射准入门。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SELECTED_BLOCKS = {
    15: "optical continuum",
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
    manifest = json.loads(
        (
            OUTPUT
            / "checkpoints/phase7b9i_work/block_aitken_manifest.json"
        ).read_text(encoding="utf-8")
    )
    summary = json.loads(
        (OUTPUT / "phase7b9k_block_aitken_pilot_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        manifest["status"] != "pilot_failed"
        or int(manifest["current_map"]) != 6
        or manifest["uncommitted_iteration"] is not None
        or summary["decision"]["natural_block_aitken_pilot_passed"] is not False
        or summary["decision"]["continue_block_aitken_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9l requires the exact completed 7B9k failure state")
    current = ROOT / manifest["current_state_path"]
    if _sha256(current) != manifest["current_state_sha256"]:
        raise RuntimeError("Phase 7B9k committed map-6 state changed")
    worker_sources = {
        f"map6_worker_block{index:02d}": _source(
            f"outputs/checkpoints/phase7b9i_work/reports/"
            f"block_aitken_map06_block{index:02d}.json"
        )
        for index in SELECTED_BLOCKS
    }
    payload = {
        "phase": "7B9l representative-block implicit-scattering pilot",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] six physics-selected natural blocks and eight "
            "fixed block-internal source updates; [V] local contraction, boundary "
            "functionals, positivity and cost; [O] no full-frequency accelerated map"
        ),
        "sources": {
            "phase7b9k_summary": _source(
                "outputs/phase7b9k_block_aitken_pilot_summary.json"
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
            "block_internal_source_updates_exactly": 8,
            "reported_iterations": [1, 2, 4, 8],
            "maximum_concurrent_processes": 2,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "neighbor_guard_state": "frozen at committed finite-trial map 6",
            "matter_state": "frozen finite protected quasi-Newton trial",
            "block_relaxation": False,
            "cellwise_tuning": False,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "selected_block_count_exactly": 6,
            "each_iteration_count_exactly": 8,
            "each_final_to_first_local_update_ratio_below": 0.55,
            "median_final_to_first_local_update_ratio_below": 0.35,
            "worst_map6_block25_final_to_first_ratio_below": 0.50,
            "each_final_to_first_boundary_spectrum_ratio_below": 0.75,
            "minimum_intensity_at_least": 0.0,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "selected_runtime_multiplier_over_one_map_below": 5.0,
            "projected_full_map_wall_time_strictly_below_s": 2700.0,
        },
        "authorization": {
            "one_full_frequency_block_implicit_map_if_gate_passes": True,
            "continue_natural_block_aitken": False,
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
    path = OUTPUT / "phase7b9l_preregistered_block_implicit_pilot.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
