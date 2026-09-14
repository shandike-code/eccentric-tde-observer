"""Phase 7B9ag：冻结当前全局态的五块 Krylov 小样。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SELECTED = {
    22: "low-energy slow-mode shoulder",
    26: "maximum absolute residual",
    30: "hydrogen-edge slow-mode interior",
    34: "high-energy slow-mode shoulder",
    45: "helium-region secondary residual",
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
    audit = json.loads(
        (OUTPUT / "phase7b9af_second_picard_contraction_audit_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        audit["decision"]["continue_positive_picard_maps_authorized"] is not True
        or audit["decision"]["mapped_state_globally_converged"] is not False
    ):
        raise RuntimeError("Phase 7B9ag requires the slow but contracting Phase 7B9af state")
    current_relative = str(audit["input_state_path"])
    current = ROOT / current_relative
    if _sha256(current) != audit["input_state_sha256"]:
        raise RuntimeError("Phase 7B9af current state changed")
    worker_sources = {
        f"map6_worker_block{index:02d}": _source(
            "outputs/checkpoints/phase7b9i_work/reports/"
            f"block_aitken_map06_block{index:02d}.json"
        )
        for index in SELECTED
    }
    payload = {
        "phase": "7B9ag current-state five-block full-source Krylov pilot",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] apply the existing sixteen-step full mixed-frame "
            "source Krylov plus exact nonnegative affine line search to five blocks "
            "selected before evaluation from the current global residual map; [V] "
            "fresh original-operator, boundary, positivity and resource tests; [O] "
            "no candidate state is written in this pilot"
        ),
        "sources": {
            "phase7b9af_summary": _source(
                "outputs/phase7b9af_second_picard_contraction_audit_summary.json"
            ),
            "phase7b9af_protocol": _source(
                "outputs/phase7b9af_preregistered_second_picard_contraction_audit.json"
            ),
            "current_map6_state": _source(current_relative),
            "finite_trial_protocol": _source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": _source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "full_source_krylov_runner": _source(
                "scripts/phase7b9r_full_source_krylov_line_search.py"
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
            **worker_sources,
        },
        "configuration": {
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "selected_blocks": [
                {"block_index": index, "role": role}
                for index, role in SELECTED.items()
            ],
            "spatial_scheme": "hybrid_step_turning_upwind",
            "gmres_relative_tolerance": 1.0e-5,
            "gmres_restart": 8,
            "gmres_maximum_restart_cycles": 2,
            "maximum_gmres_iterations": 16,
            "endpoint_exact_global_nonnegative_step": True,
            "line_search_interval": [0.0, 1.0],
            "maximum_concurrent_processes": 1,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "selected_block_count_exactly": len(SELECTED),
            "each_gmres_iteration_count_at_most": 16,
            "each_endpoint_exact_nonnegative_step_at_least": 0.10,
            "each_selected_line_fraction_at_least": 0.02,
            "each_fresh_line_candidate_to_raw_residual_ratio_below": 0.50,
            "median_fresh_line_candidate_to_raw_residual_ratio_below": 0.25,
            "each_fresh_line_candidate_boundary_ratio_at_most": 1.0,
            "each_affine_prediction_to_fresh_residual_linf_below": 2.0e-8,
            "minimum_line_candidate_intensity_at_least": 0.0,
            "each_process_peak_rss_strictly_below_mib": 7168.0,
            "each_worker_wall_time_strictly_below_s": 300.0,
        },
        "authorization": {
            "accelerated_dominant_block_candidate_if_all_gates_pass": True,
            "write_candidate_state_in_pilot": False,
            "material_feedback": False,
            "accept_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9ag_preregistered_current_state_krylov_pilot.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
