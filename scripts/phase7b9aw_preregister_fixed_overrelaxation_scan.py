"""Phase 7B9aw：冻结新 Picard 方向的一遍式超松弛扫描。"""

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
    audit = json.loads(
        (OUTPUT / "phase7b9au_constrained_anderson_audit_summary.json").read_text(
            encoding="utf-8"
        )
    )
    mapped = json.loads(
        (OUTPUT / "phase7b9av_candidate_picard_map_summary.json").read_text(
            encoding="utf-8"
        )
    )
    history = json.loads(
        (OUTPUT / "phase7b9ar_global_anderson_coefficients_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        mapped["decision"]["global_positive_picard_map_passed"] is not True
        or mapped["decision"]["material_feedback_authorized"] is not False
        or mapped["input_state_sha256"] != audit["input_state_sha256"]
    ):
        raise RuntimeError("Phase 7B9aw requires the passed adjacent Picard states")
    lower_relative = str(mapped["input_state_path"])
    upper_relative = str(mapped["output_state_path"])
    if (
        _sha256(ROOT / lower_relative) != mapped["input_state_sha256"]
        or _sha256(ROOT / upper_relative) != mapped["output_state_sha256"]
    ):
        raise RuntimeError("Phase 7B9aw adjacent states changed")
    output_relative = str(history["x4_state_path"])
    if _sha256(ROOT / output_relative) != history["x4_state_sha256"]:
        raise RuntimeError("Phase 7B9aw reusable x4 buffer changed")
    payload = {
        "phase": "7B9aw one-pass fixed Picard overrelaxation scan",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] scan theta in a fixed broad grid using one fresh "
            "F(upper), select only a current-and-mapped nonnegative candidate, and "
            "require at least 20 percent maximum-norm improvement; [V] exact affine "
            "residual, boundary and positivity audit; [O] no candidate is written here"
        ),
        "sources": {
            "phase7b9au_summary": _source(
                "outputs/phase7b9au_constrained_anderson_audit_summary.json"
            ),
            "phase7b9av_summary": _source(
                "outputs/phase7b9av_candidate_picard_map_summary.json"
            ),
            "phase7b9av_protocol": _source(
                "outputs/phase7b9av_preregistered_candidate_picard_map.json"
            ),
            "lower_state": _source(lower_relative),
            "upper_state": _source(upper_relative),
            "finite_trial_protocol": _source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": _source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "overrelaxation_engine": _source(
                "scripts/phase7b9am_global_picard_overrelaxation.py"
            ),
            "affine_evaluator": _source(
                "scripts/phase7b9ak_global_convex_krylov_line.py"
            ),
            "phase7b7i_worker": _source(
                "scripts/phase7b7i_second_radiation_map.py"
            ),
            "phase7b9d_worker_helpers": _source(
                "scripts/phase7b9d_inner_converged_base_radiation.py"
            ),
            "mixed_frame_operator": _source(
                "src/eccentric_tde_observer/mixed_frame_ale.py"
            ),
            "mixed_frame_frequency": _source(
                "src/eccentric_tde_observer/mixed_frame_frequency.py"
            ),
        },
        "configuration": {
            "phase_index": 1371,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "maximum_concurrent_processes": 2,
            "lower_state_path": lower_relative,
            "lower_state_sha256": mapped["input_state_sha256"],
            "upper_state_path": upper_relative,
            "upper_state_sha256": mapped["output_state_sha256"],
            "fixed_theta_candidates": [
                0.0,
                0.5,
                1.0,
                1.5,
                2.0,
                3.0,
                4.0,
                6.0,
                8.0,
                10.0,
                12.0,
                16.0,
                20.0,
                24.0
            ],
            "candidate_report_directory": (
                "outputs/checkpoints/phase7b9aw_fixed_overrelaxation/reports"
            ),
            "derived_grid_path": (
                "outputs/checkpoints/phase7b9aw_fixed_overrelaxation/grid.json"
            ),
            "summary_path": (
                "outputs/phase7b9aw_fixed_overrelaxation_scan_summary.json"
            ),
            "figure_path": "outputs/phase7b9aw_fixed_overrelaxation_scan.png",
            "runner_path": "scripts/phase7b9aw_fixed_overrelaxation_scan.py",
            "candidate_output_path": output_relative,
            "candidate_output_previous_sha256": history["x4_state_sha256"],
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback": False,
        },
        "reference": {
            "theta_zero_global_residual": audit[
                "mapped_state_global_original_operator_residual"
            ],
            "theta_zero_boundary_spectrum_l1": audit[
                "mapped_state_boundary_spectrum_l1"
            ],
            "theta_zero_boundary_bolometric_fraction": audit[
                "mapped_state_boundary_bolometric_fraction"
            ],
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "minimum_current_and_mapped_intensity_at_least": 0.0,
            "theta_zero_endpoint_absolute_tolerance": 2.0e-12,
            "selected_residual_ratio_to_theta_zero_below": 0.80,
            "selected_boundary_spectrum_l1_below": 1.0e-3,
            "selected_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "candidate_worker_wall_time_strictly_below_s": 180.0,
        },
        "authorization": {
            "write_selected_candidate_if_all_gates_pass": True,
            "fresh_global_candidate_audit_after_write": True,
            "resume_positive_picard_if_gate_fails": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9aw_preregistered_fixed_overrelaxation_scan.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
