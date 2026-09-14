"""Phase 7B9s：冻结完整源 Krylov 的四块准入门。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
RETAINED_BLOCKS = {15: "optical exact-source control", 45: "He I slow-mode target"}
NEW_BLOCKS = {25: "H I threshold target", 60: "soft-X-ray positivity target"}


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
        (OUTPUT / "phase7b9r_full_source_krylov_line_search_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        manifest["status"] != "pilot_failed"
        or int(manifest["current_map"]) != 6
        or manifest["uncommitted_iteration"] is not None
        or prior["decision"]["full_source_krylov_line_search_feasibility_passed"]
        is not True
        or prior["decision"]["four_block_full_source_krylov_gate_authorized"]
        is not True
    ):
        raise RuntimeError("Phase 7B9s requires the completed 7B9r pass state")
    current = ROOT / manifest["current_state_path"]
    if _sha256(current) != manifest["current_state_sha256"]:
        raise RuntimeError("Phase 7B9s current map-6 state changed")
    worker_sources = {
        f"map6_worker_block{index:02d}": _source(
            f"outputs/checkpoints/phase7b9i_work/reports/"
            f"block_aitken_map06_block{index:02d}.json"
        )
        for index in (*RETAINED_BLOCKS, *NEW_BLOCKS)
    }
    retained_sources = {
        f"retained_phase7b9r_block{index:02d}": _source(
            f"outputs/phase7b9r_block{index:02d}_full_source_krylov.json"
        )
        for index in RETAINED_BLOCKS
    }
    payload = {
        "phase": "7B9s four-block full mixed-frame source Krylov gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] retain bitwise frozen Phase 7B9r optical and He I "
            "reports and apply the identical sixteen-step full-source Krylov plus "
            "affine line search to H I and soft X-ray blocks; [V] four-block fresh "
            "original-operator gate; [O] no full-frequency map before this gate"
        ),
        "sources": {
            "phase7b9r_summary": _source(
                "outputs/phase7b9r_full_source_krylov_line_search_summary.json"
            ),
            "phase7b9r_protocol": _source(
                "outputs/phase7b9r_preregistered_full_source_krylov_line_search.json"
            ),
            **retained_sources,
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
            "mixed_frame_frequency": _source(
                "src/eccentric_tde_observer/mixed_frame_frequency.py"
            ),
            "ali_preconditioner": _source(
                "src/eccentric_tde_observer/mixed_frame_ali.py"
            ),
            "affine_line_search": _source(
                "src/eccentric_tde_observer/affine_krylov.py"
            ),
            "ali_controls": _source("tests/test_mixed_frame_ali.py"),
            "affine_controls": _source("tests/test_affine_krylov.py"),
            "phase7b7i_worker": _source(
                "scripts/phase7b7i_second_radiation_map.py"
            ),
            "phase7b9r_worker_helpers": _source(
                "scripts/phase7b9r_full_source_krylov_line_search.py"
            ),
            **worker_sources,
        },
        "configuration": {
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "retained_blocks": [
                {"block_index": index, "role": role}
                for index, role in RETAINED_BLOCKS.items()
            ],
            "new_blocks": [
                {"block_index": index, "role": role}
                for index, role in NEW_BLOCKS.items()
            ],
            "spatial_scheme": "hybrid_step_turning_upwind",
            "krylov_operator": (
                "complete signed comoving scattering, two Lorentz frequency remaps "
                "and full-depth step-characteristic response at frozen matter"
            ),
            "gmres_relative_tolerance": 1.0e-5,
            "gmres_restart": 8,
            "gmres_maximum_restart_cycles": 2,
            "maximum_gmres_iterations": 16,
            "incomplete_finite_krylov_candidate_allowed_for_diagnostic": True,
            "endpoint_exact_global_nonnegative_step": True,
            "line_search_interval": [0.0, 1.0],
            "retained_report_recalculation": False,
            "fresh_new_block_original_operator_validation": True,
            "neighbor_guard_state": "frozen at committed finite-trial map 6",
            "matter_state": "frozen finite protected quasi-Newton trial",
            "maximum_concurrent_processes": 1,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "selected_block_count_exactly": 4,
            "each_gmres_iteration_count_at_most": 16,
            "each_endpoint_exact_nonnegative_step_at_least": 0.10,
            "each_selected_line_fraction_at_least": 0.02,
            "each_fresh_line_candidate_to_raw_residual_ratio_below": 0.50,
            "median_fresh_line_candidate_to_raw_residual_ratio_below": 0.25,
            "each_fresh_line_candidate_boundary_ratio_at_most": 1.0,
            "each_affine_prediction_to_fresh_residual_linf_below": 2.0e-8,
            "minimum_line_candidate_intensity_at_least": 0.0,
            "each_process_peak_rss_strictly_below_mib": 7168.0,
            "selected_runtime_multiplier_over_one_map_below": 25.0,
            "projected_full_map_wall_time_strictly_below_s": 9000.0,
        },
        "authorization": {
            "one_full_frequency_full_source_krylov_map_if_gate_passes": True,
            "formal_trial_h_he_feedback": False,
            "trial_true_residual": False,
            "accept_trial_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9s_preregistered_four_block_full_source_gate.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
