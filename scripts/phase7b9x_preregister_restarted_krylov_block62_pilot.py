"""Phase 7B9x：冻结块 62 的两段物理重启 Krylov 试验。"""

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
    deep = json.loads(
        (
            OUTPUT / "phase7b9w_deep_krylov_block62_pilot_summary.json"
        ).read_text(encoding="utf-8")
    )
    if (
        deep["decision"]["deep_krylov_block62_pilot_passed"] is not False
        or deep["report"]["gmres_iteration_count"] != 32
        or deep["report"]["fresh_line_candidate_to_raw_residual_ratio"]
        <= deep["report"]["phase7b9t_sixteen_step_residual_ratio"]
    ):
        raise RuntimeError("Phase 7B9x requires the failed continuous 32-step pilot")
    current_source = t_protocol["sources"]["current_map6_state"]
    current = ROOT / current_source["path"]
    if (
        current.stat().st_size != int(current_source["size_bytes"])
        or _sha256(current) != current_source["sha256"]
    ):
        raise RuntimeError("Phase 7B9x current map-6 state changed")
    payload = {
        "phase": "7B9x two-stage physically restarted full-source Krylov block-62 pilot",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] two consecutive sixteen-step full mixed-frame source "
            "Krylov corrections, each accepted only after exact non-negative and "
            "fresh original-operator line validation; [V] restart consistency, "
            "boundary and resource audits; [O] block 62 only"
        ),
        "sources": {
            "phase7b9t_protocol": _source(
                "outputs/phase7b9t_preregistered_full_frequency_krylov_map.json"
            ),
            "phase7b9w_summary": _source(
                "outputs/phase7b9w_deep_krylov_block62_pilot_summary.json"
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
        },
        "configuration": {
            "phase_index": 1371,
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
            "physical_restart_count": 2,
            "gmres_relative_tolerance": 1.0e-5,
            "gmres_restart": 8,
            "gmres_maximum_restart_cycles_per_stage": 2,
            "maximum_gmres_iterations_per_stage": 16,
            "incomplete_finite_krylov_candidate_allowed_for_diagnostic": True,
            "endpoint_exact_global_nonnegative_step": True,
            "line_search_interval_each_stage": [0.0, 1.0],
            "current_state_path": current_source["path"],
            "current_state_sha256": current_source["sha256"],
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "physical_restart_count_exactly": 2,
            "each_stage_gmres_iteration_count_at_most": 16,
            "each_stage_endpoint_nonnegative_step_at_least": 0.1,
            "each_stage_line_fraction_at_least": 0.02,
            "each_stage_original_residual_ratio_below": 1.0,
            "final_to_initial_raw_residual_ratio_below": 0.5,
            "final_to_initial_raw_boundary_ratio_at_most": 1.0,
            "restart_consistency_error_below": 2.0e-12,
            "each_affine_prediction_to_fresh_residual_linf_below": 2.0e-8,
            "minimum_final_candidate_intensity_at_least": 0.0,
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
    path = OUTPUT / "phase7b9x_preregistered_restarted_krylov_block62_pilot.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
