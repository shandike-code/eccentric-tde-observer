"""Phase 7B9ai：冻结主导能段的 Krylov 候选态生成。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SELECTED = tuple(range(13, 51))


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
    pilot16 = json.loads(
        (OUTPUT / "phase7b9ag_current_state_krylov_pilot_summary.json").read_text(
            encoding="utf-8"
        )
    )
    pilot8 = json.loads(
        (OUTPUT / "phase7b9ah_eight_step_krylov_pilot_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        audit["decision"]["continue_positive_picard_maps_authorized"] is not True
        or pilot16["decision"]["current_state_krylov_pilot_passed"] is not True
        or pilot8["decision"]["current_state_krylov_pilot_passed"] is not True
    ):
        raise RuntimeError("Phase 7B9ai requires the passed contraction and Krylov pilots")
    current_relative = str(audit["input_state_path"])
    current = ROOT / current_relative
    if _sha256(current) != audit["input_state_sha256"]:
        raise RuntimeError("Phase 7B9af current state changed")
    output_relative = "outputs/checkpoints/phase7b9i_work/state_a.dat"
    output_state = ROOT / output_relative
    worker_sources = {
        f"map6_worker_block{index:02d}": _source(
            "outputs/checkpoints/phase7b9i_work/reports/"
            f"block_aitken_map06_block{index:02d}.json"
        )
        for index in SELECTED
    }
    payload = {
        "phase": "7B9ai dominant-band full-source Krylov candidate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] replace only natural-frequency blocks 13 through 50, "
            "which were selected before production because their fresh absolute "
            "source-map changes exceed the frozen 1e-4 global target; use the passed "
            "sixteen-step full-source Krylov and exact nonnegative line search; [V] "
            "recoverable block hashes, fresh residual, boundary, positivity and "
            "resource gates; [O] candidate self-guard residual remains separate"
        ),
        "sources": {
            "phase7b9af_summary": _source(
                "outputs/phase7b9af_second_picard_contraction_audit_summary.json"
            ),
            "phase7b9ag_summary": _source(
                "outputs/phase7b9ag_current_state_krylov_pilot_summary.json"
            ),
            "phase7b9ah_summary": _source(
                "outputs/phase7b9ah_eight_step_krylov_pilot_summary.json"
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
                {"block_index": index, "role": "absolute-residual dominant band"}
                for index in SELECTED
            ],
            "spatial_scheme": "hybrid_step_turning_upwind",
            "gmres_relative_tolerance": 1.0e-5,
            "gmres_restart": 8,
            "gmres_maximum_restart_cycles": 2,
            "maximum_gmres_iterations": 16,
            "endpoint_exact_global_nonnegative_step": True,
            "line_search_interval": [0.0, 1.0],
            "maximum_concurrent_processes": 1,
            "current_state_path": current_relative,
            "current_state_sha256": audit["input_state_sha256"],
            "output_state_path": output_relative,
            "output_state_previous_sha256": _sha256(output_state),
            "raw_float64_checkpoint_size_bytes": current.stat().st_size,
            "manifest_path": (
                "outputs/checkpoints/phase7b9ai_dominant_band_krylov/manifest.json"
            ),
            "report_directory": (
                "outputs/checkpoints/phase7b9ai_dominant_band_krylov/reports"
            ),
            "storage_strategy": (
                "copy the current second-Picard state into the former first-Picard "
                "state_a buffer, then replace only frozen blocks 13-50; preserve the "
                "current source state and map-6 state"
            ),
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
            "full_candidate_wall_time_strictly_below_s": 7200.0,
        },
        "authorization": {
            "commit_candidate_if_all_generation_gates_pass": True,
            "evaluate_candidate_self_guard_residual_if_committed": True,
            "material_feedback": False,
            "accept_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9ai_preregistered_dominant_band_krylov_candidate.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
