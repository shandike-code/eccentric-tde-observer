"""Phase 7B9w：冻结块 62 的 32 步完整源 Krylov 试验。"""

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
    t_report = json.loads(
        (
            OUTPUT
            / "checkpoints/phase7b9i_work/reports_phase7b9t/phase7b9t_block62.json"
        ).read_text(encoding="utf-8")
    )
    convex = json.loads(
        (
            OUTPUT / "phase7b9v_positive_convex_picard_pilot_summary.json"
        ).read_text(encoding="utf-8")
    )
    if (
        t_report["fresh_line_candidate_to_raw_residual_ratio"] <= 0.5
        or t_report["endpoint_exact_nonnegative_step"] < 0.1
        or convex["decision"]["positive_convex_picard_pilot_passed"] is not False
        or convex["reports"][0]["block_index"] != 62
        or convex["reports"][0]["fresh_candidate_to_raw_residual_ratio"] <= 0.5
    ):
        raise RuntimeError("Phase 7B9w requires the isolated block-62 slow solve")
    current_source = t_protocol["sources"]["current_map6_state"]
    current = ROOT / current_source["path"]
    if (
        current.stat().st_size != int(current_source["size_bytes"])
        or _sha256(current) != current_source["sha256"]
    ):
        raise RuntimeError("Phase 7B9w current map-6 state changed")
    payload = {
        "phase": "7B9w deep full-source Krylov pilot for block 62",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] double only the finite full mixed-frame source "
            "Krylov work from 16 to 32 iterations for block 62; retain exact "
            "non-negative endpoint and affine original-operator validation; "
            "[O] no candidate-map repair before this gate"
        ),
        "sources": {
            "phase7b9t_protocol": _source(
                "outputs/phase7b9t_preregistered_full_frequency_krylov_map.json"
            ),
            "phase7b9t_block62_report": _source(
                "outputs/checkpoints/phase7b9i_work/reports_phase7b9t/phase7b9t_block62.json"
            ),
            "phase7b9v_summary": _source(
                "outputs/phase7b9v_positive_convex_picard_pilot_summary.json"
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
            "map6_worker_block62": _source(
                "outputs/checkpoints/phase7b9i_work/reports/"
                "block_aitken_map06_block62.json"
            ),
        },
        "configuration": {
            "phase_index": 1370,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "selected_blocks": [
                {
                    "block_index": 62,
                    "role": "394--477 eV slow-residual block",
                }
            ],
            "spatial_scheme": "hybrid_step_turning_upwind",
            "gmres_relative_tolerance": 1.0e-5,
            "gmres_restart": 8,
            "gmres_maximum_restart_cycles": 4,
            "maximum_gmres_iterations": 32,
            "incomplete_finite_krylov_candidate_allowed_for_diagnostic": True,
            "endpoint_exact_global_nonnegative_step": True,
            "line_search_interval": [0.0, 1.0],
            "current_state_path": current_source["path"],
            "current_state_sha256": current_source["sha256"],
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "gmres_iteration_count_at_most": 32,
            "endpoint_exact_nonnegative_step_at_least": 0.1,
            "selected_line_fraction_at_least": 0.02,
            "fresh_line_candidate_to_raw_residual_ratio_below": 0.5,
            "fresh_line_candidate_boundary_ratio_at_most": 1.0,
            "affine_prediction_to_fresh_residual_linf_below": 2.0e-8,
            "minimum_line_candidate_intensity_at_least": 0.0,
            "process_peak_rss_strictly_below_mib": 7168.0,
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
    path = OUTPUT / "phase7b9w_preregistered_deep_krylov_block62_pilot.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
