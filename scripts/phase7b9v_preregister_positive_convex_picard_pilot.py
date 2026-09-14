"""Phase 7B9v：冻结正性保持的 Picard 历史凸组合试验。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SELECTED = [62, 65, 66, 73, 75]


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
    failure = json.loads(
        (OUTPUT / "phase7b9u_block73_failure_capture_summary.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (
            OUTPUT / "checkpoints/phase7b9t_full_frequency_manifest.json"
        ).read_text(encoding="utf-8")
    )
    t_protocol = json.loads(
        (
            OUTPUT / "phase7b9t_preregistered_full_frequency_krylov_map.json"
        ).read_text(encoding="utf-8")
    )
    completed = {int(row["block_index"]): row for row in manifest["completed_blocks"]}
    if (
        failure["failure_reproduced"] is not True
        or manifest["status"] != "running"
        or sorted(completed) != list(range(73))
        or completed[62]["fresh_line_candidate_to_raw_residual_ratio"] <= 0.5
        or completed[65]["endpoint_exact_nonnegative_step"] >= 0.1
        or completed[66]["line_selected_fraction"] != 0.0
    ):
        raise RuntimeError("Phase 7B9v requires the audited Phase 7B9t tail failure")
    current_source = t_protocol["sources"]["current_map6_state"]
    current = ROOT / current_source["path"]
    if (
        current.stat().st_size != int(current_source["size_bytes"])
        or _sha256(current) != current_source["sha256"]
    ):
        raise RuntimeError("Phase 7B9v current map-6 state changed")
    roles = {
        62: "finite-work residual failure at 394--477 eV",
        65: "positivity-limited Krylov direction at 700--848 eV",
        66: "zero affine line step at 848--1028 eV",
        73: "no positive affine Krylov step at 3.29--3.99 keV",
        75: "uncomputed terminal high-energy control block",
    }
    payload = {
        "phase": "7B9v positive-convex Picard-history pilot",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] sixteen exact positive Picard source maps followed "
            "by a non-negative, sum-one residual-minimizing history combination; "
            "[V] fresh original-operator, boundary, positivity and affine audits; "
            "[O] only five representative failed/unresolved blocks"
        ),
        "sources": {
            "phase7b9t_protocol": _source(
                "outputs/phase7b9t_preregistered_full_frequency_krylov_map.json"
            ),
            "phase7b9t_stopped_manifest": _source(
                "outputs/checkpoints/phase7b9t_full_frequency_manifest.json"
            ),
            "phase7b9u_failure_capture": _source(
                "outputs/phase7b9u_block73_failure_capture_summary.json"
            ),
            "current_map6_state": _source(current_source["path"]),
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
            "positive_simplex_solver": _source(
                "src/eccentric_tde_observer/affine_krylov.py"
            ),
            "phase7b7i_worker": _source(
                "scripts/phase7b7i_second_radiation_map.py"
            ),
            "phase7b9r_worker_helpers": _source(
                "scripts/phase7b9r_full_source_krylov_line_search.py"
            ),
        },
        "configuration": {
            "phase_index": 1369,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "selected_blocks": [
                {"block_index": index, "role": roles[index]} for index in SELECTED
            ],
            "spatial_scheme": "hybrid_step_turning_upwind",
            "picard_residual_history_count": 16,
            "simplex_optimizer_tolerance": 1.0e-12,
            "simplex_optimizer_maximum_iterations": 500,
            "maximum_concurrent_processes": 1,
            "current_state_path": current_source["path"],
            "current_state_sha256": current_source["sha256"],
            "temporary_full_precision_state_history": True,
            "temporary_full_precision_residual_history": True,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "selected_block_count_exactly": len(SELECTED),
            "minimum_history_intensity_at_least": 0.0,
            "minimum_candidate_intensity_at_least": 0.0,
            "minimum_simplex_coefficient_at_least": 0.0,
            "simplex_coefficient_sum_error_below": 1.0e-12,
            "each_fresh_candidate_to_raw_residual_ratio_below": 0.5,
            "each_fresh_candidate_boundary_ratio_at_most": 1.0,
            "each_affine_prediction_defect_to_physical_state_linf_below": 2.0e-12,
            "each_process_peak_rss_strictly_below_mib": 7168.0,
            "each_worker_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "repair_unresolved_phase7b9t_blocks_if_all_gates_pass": True,
            "global_candidate_residual": False,
            "formal_trial_h_he_feedback": False,
            "trial_true_residual": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9v_preregistered_positive_convex_picard_pilot.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
