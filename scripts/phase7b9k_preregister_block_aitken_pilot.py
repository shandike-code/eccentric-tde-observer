"""Phase 7B9k：冻结有限候选的频率块 Aitken 三映射试验。"""

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
    pause = json.loads(
        (OUTPUT / "phase7b9j_finite_trial_pause_snapshot.json").read_text(
            encoding="utf-8"
        )
    )
    cost = json.loads(
        (OUTPUT / "phase7b9j_finite_trial_cost_decision_summary.json").read_text(
            encoding="utf-8"
        )
    )
    historical = json.loads(
        (OUTPUT / "phase7b6h_full_frequency_aitken_summary.json").read_text(
            encoding="utf-8"
        )
    )
    retained = OUTPUT / "checkpoints/phase7b9k_retained_trial_map3.dat"
    if (
        pause["status"] != "running"
        or int(pause["current_additional_map"]) != 3
        or int(pause["uncommitted_iteration"]["additional_map"]) != 4
        or len(pause["uncommitted_iteration"]["completed_blocks"]) != 4
        or cost["decision"]["redesign_inner_radiation_acceleration_authorized"]
        is not True
        or _sha256(retained) != pause["current_state_sha256"]
    ):
        raise RuntimeError("Phase 7B9k requires the exact cost-paused finite trial")
    historical_maximum = max(
        float(row["accepted_weight"])
        for row in historical["history"]
        if row["accepted_method"] == "vector Aitken"
    )
    payload = {
        "phase": "7B9k natural-frequency-block Aitken pilot",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] natural 128-group transport blocks and historical "
            "full-frequency Aitken weight bound; [V] three new full maps and true "
            "science functionals; [O] formal trial feedback remains closed"
        ),
        "sources": {
            "pause_snapshot": _source(
                "outputs/phase7b9j_finite_trial_pause_snapshot.json"
            ),
            "cost_decision": _source(
                "outputs/phase7b9j_finite_trial_cost_decision_summary.json"
            ),
            "retained_trial_map3": _source(
                "outputs/checkpoints/phase7b9k_retained_trial_map3.dat"
            ),
            "finite_trial_protocol": _source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_worker": _source(
                "scripts/phase7b9i_finite_trial_radiation.py"
            ),
            "historical_aitken_summary": _source(
                "outputs/phase7b6h_full_frequency_aitken_summary.json"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "storage_audit": _source(
                "outputs/phase7b9k_storage_reclamation_audit.json"
            ),
        },
        "configuration": {
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "natural_frequency_block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "raw_float64_checkpoint_size_bytes": 10099884032,
            "starting_completed_map": 3,
            "pilot_map_indices_exactly": [4, 5, 6],
            "first_accelerated_update": (
                "largest whole-block finite nonnegative fallback in frozen order"
            ),
            "later_accelerated_update": (
                "block Aitken if positive finite, within historical accepted bound, "
                "and whole block is finite nonnegative; otherwise frozen fallback"
            ),
            "aitken_formula": (
                "omega_b(n)=-omega_b(n-1)<r_b(n-1),r_b(n)-r_b(n-1)>/"
                "||r_b(n)-r_b(n-1)||^2"
            ),
            "maximum_aitken_weight_from_historical_accepted_full_map": historical_maximum,
            "fallback_weights_in_order": [2.0, 1.8, 1.5, 1.2, 1.0],
            "maximum_concurrent_processes": 2,
            "work_directory": "outputs/checkpoints/phase7b9i_work",
            "acceleration_manifest": (
                "outputs/checkpoints/phase7b9i_work/block_aitken_manifest.json"
            ),
            "single_previous_residual_buffer": (
                "outputs/checkpoints/phase7b9i_work/block_aitken_residual.dat"
            ),
            "minimum_free_bytes_after_residual_allocation": 8589934592,
            "cellwise_weight_tuning": False,
            "frequency_block_boundaries_changed": False,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback_during_pilot": False,
        },
        "gates": {
            "map5_to_map4_raw_residual_ratio_below": 0.95,
            "map6_to_map5_raw_residual_ratio_below": 0.80,
            "map6_to_map4_raw_residual_ratio_below": 0.75,
            "map6_to_map4_boundary_spectrum_ratio_below": 1.0,
            "map6_to_map4_boundary_bolometric_ratio_below": 1.0,
            "block_aitken_weights_above_two_at_least": 1,
            "minimum_accepted_intensity_at_least": 0.0,
            "each_map_block_count_exactly": 76,
            "each_map_owned_frequency_groups_exactly": 9632,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_map_wall_time_strictly_below_s": 900.0,
            "projected_stop_map_at_most_if_constant_latest_contraction": 28,
        },
        "authorization": {
            "continue_block_aitken_if_pilot_passes": True,
            "resume_plain_omega1": False,
            "strict_full_frequency_jv": False,
            "formal_trial_h_he_feedback": False,
            "trial_true_residual": False,
            "accept_trial_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
            "full_orbit": False,
            "phase4_replacement": False,
            "uvot": False,
        },
    }
    path = OUTPUT / "phase7b9k_preregistered_block_aitken_pilot.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
