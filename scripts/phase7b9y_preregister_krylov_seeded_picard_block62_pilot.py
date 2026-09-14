"""Phase 7B9y：冻结块 62 的 Krylov 种子加正 Picard 微循环。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


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
    t_protocol = json.loads(
        (
            OUTPUT / "phase7b9t_preregistered_full_frequency_krylov_map.json"
        ).read_text(encoding="utf-8")
    )
    t_manifest = json.loads(
        (
            OUTPUT / "checkpoints/phase7b9t_full_frequency_manifest.json"
        ).read_text(encoding="utf-8")
    )
    t_report = json.loads(
        (
            OUTPUT
            / "checkpoints/phase7b9i_work/reports_phase7b9t/phase7b9t_block62.json"
        ).read_text(encoding="utf-8")
    )
    restarted = json.loads(
        (
            OUTPUT / "phase7b9x_restarted_krylov_block62_pilot_summary.json"
        ).read_text(encoding="utf-8")
    )
    completed = {int(row["block_index"]): row for row in t_manifest["completed_blocks"]}
    if (
        restarted["decision"]["restarted_krylov_block62_pilot_passed"] is not False
        or restarted["report"]["stages"][1]["line_selected_fraction"] != 0.0
        or sorted(completed) != list(range(73))
        or completed[62]["fresh_line_candidate_original_operator_residual"]
        != t_report["fresh_line_candidate_original_operator_residual"]
        or t_report["fresh_line_candidate_to_raw_residual_ratio"] >= 1.0
    ):
        raise RuntimeError("Phase 7B9y requires the verified non-negative block-62 seed")
    current_source = t_protocol["sources"]["current_map6_state"]
    current = ROOT / current_source["path"]
    if (
        current.stat().st_size != int(current_source["size_bytes"])
        or _sha256(current) != current_source["sha256"]
    ):
        raise RuntimeError("Phase 7B9y current map-6 state changed")
    payload = {
        "phase": "7B9y Krylov-seeded positive Picard microcycle for block 62",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] start from the Phase 7B9t fresh, non-negative "
            "sixteen-step Krylov block-62 candidate and apply exactly thirty-two "
            "positive original source maps with map-6 neighbor guards; [V] fresh "
            "residual, boundary, seed-restart, positivity and resource audits; "
            "[O] block 62 only"
        ),
        "sources": {
            "phase7b9t_protocol": _source(
                "outputs/phase7b9t_preregistered_full_frequency_krylov_map.json"
            ),
            "phase7b9t_stopped_manifest": _source(
                "outputs/checkpoints/phase7b9t_full_frequency_manifest.json"
            ),
            "phase7b9t_block62_report": _source(
                "outputs/checkpoints/phase7b9i_work/reports_phase7b9t/phase7b9t_block62.json"
            ),
            "phase7b9x_summary": _source(
                "outputs/phase7b9x_restarted_krylov_block62_pilot_summary.json"
            ),
            "current_map6_state": _source(current_source["path"]),
            "phase7b9t_partial_candidate_state": _source(
                "outputs/checkpoints/phase7b9i_work/state_a.dat"
            ),
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
            "phase7b7i_worker": _source(
                "scripts/phase7b7i_second_radiation_map.py"
            ),
            "phase7b9r_worker_helpers": _source(
                "scripts/phase7b9r_full_source_krylov_line_search.py"
            ),
        },
        "configuration": {
            "phase_index": 1372,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "selected_blocks": [
                {
                    "block_index": 62,
                    "role": "394--477 eV positive-microcycle repair pilot",
                }
            ],
            "spatial_scheme": "hybrid_step_turning_upwind",
            "positive_picard_update_count": 32,
            "neighbor_guard_state": "frozen map 6",
            "initial_core_state": "Phase 7B9t fresh non-negative Krylov candidate",
            "current_state_path": current_source["path"],
            "current_state_sha256": current_source["sha256"],
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "positive_picard_update_count_exactly": 32,
            "seed_restart_relative_difference_below": 2.0e-12,
            "minimum_history_intensity_at_least": 0.0,
            "minimum_final_candidate_intensity_at_least": 0.0,
            "final_to_map6_raw_residual_ratio_below": 0.5,
            "final_to_map6_raw_boundary_ratio_at_most": 1.0,
            "process_peak_rss_strictly_below_mib": 7168.0,
            "worker_wall_time_strictly_below_s": 600.0,
        },
        "authorization": {
            "hybrid_frequency_solver_repair_if_gate_passes": True,
            "global_candidate_residual": False,
            "formal_trial_h_he_feedback": False,
            "trial_true_residual": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9y_preregistered_krylov_seeded_picard_block62_pilot.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
