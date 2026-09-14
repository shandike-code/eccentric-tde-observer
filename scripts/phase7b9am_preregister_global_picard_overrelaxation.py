"""Phase 7B9am：冻结最新全局 Picard 方向的超松弛审计。"""

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
    summary = json.loads(
        (OUTPUT / "phase7b9al_positive_picard_convergence_summary.json").read_text(
            encoding="utf-8"
        )
    )
    manifest_path = OUTPUT / "checkpoints/phase7b9al_positive_picard/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        summary["status"] != "running"
        or summary["completed_picard_maps"] != 4
        or summary["decision"]["material_feedback_authorized"] is not False
        or manifest["active_iteration"] is not None
        or len(manifest["iterations"]) != 4
    ):
        raise RuntimeError("Phase 7B9am requires the paused four-map Picard sequence")
    latest = manifest["iterations"][-1]
    lower_relative = str(latest["input_state_path"])
    upper_relative = str(latest["mapped_state_path"])
    lower_sha = _sha256(ROOT / lower_relative)
    upper_sha = _sha256(ROOT / upper_relative)
    if (
        lower_sha != latest["input_state_sha256"]
        or upper_sha != latest["mapped_state_sha256"]
        or manifest["current_input_path"] != upper_relative
        or manifest["current_input_sha256"] != upper_sha
        or manifest["next_output_path"] != lower_relative
    ):
        raise RuntimeError("Phase 7B9am adjacent Picard endpoints changed")
    payload = {
        "phase": "7B9am global Picard-direction overrelaxation audit",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] form x(theta)=x5+theta*(x6-x5), derive the global "
            "unweighted-L2 residual minimizer from one fresh F(x6), and compare it "
            "with fixed positive overrelaxation controls; [V] repeat F(x6) for an "
            "independent candidate audit with exact global maximum residual, boundary, "
            "positivity and resource gates; [O] no state is written in this phase"
        ),
        "sources": {
            "phase7b9al_summary": _source(
                "outputs/phase7b9al_positive_picard_convergence_summary.json"
            ),
            "phase7b9al_manifest": _source(
                "outputs/checkpoints/phase7b9al_positive_picard/manifest.json"
            ),
            "lower_picard_state": _source(lower_relative),
            "upper_picard_state": _source(upper_relative),
            "finite_trial_protocol": _source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": _source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "phase7b9ak_affine_evaluator": _source(
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
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "maximum_concurrent_processes": 2,
            "lower_state_path": lower_relative,
            "lower_state_sha256": lower_sha,
            "upper_state_path": upper_relative,
            "upper_state_sha256": upper_sha,
            "fixed_theta_candidates": [0.0, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0],
            "l2_theta_multipliers": [0.5, 0.75, 1.0, 1.25],
            "coefficient_report_directory": (
                "outputs/checkpoints/phase7b9am_overrelaxation/coefficient_reports"
            ),
            "candidate_report_directory": (
                "outputs/checkpoints/phase7b9am_overrelaxation/candidate_reports"
            ),
            "derived_grid_path": (
                "outputs/checkpoints/phase7b9am_overrelaxation/derived_grid.json"
            ),
            "summary_path": (
                "outputs/phase7b9am_global_picard_overrelaxation_summary.json"
            ),
            "figure_path": "outputs/phase7b9am_global_picard_overrelaxation.png",
            "runner_path": (
                "scripts/phase7b9am_global_picard_overrelaxation.py"
            ),
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback": False,
        },
        "reference": {
            "theta_zero_global_residual": latest[
                "global_original_operator_residual"
            ],
            "theta_zero_boundary_spectrum_l1": latest["boundary_spectrum_l1"],
            "theta_zero_boundary_bolometric_fraction": latest[
                "boundary_bolometric_fraction"
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
            "coefficient_worker_wall_time_strictly_below_s": 60.0,
            "candidate_worker_wall_time_strictly_below_s": 180.0,
        },
        "authorization": {
            "write_selected_overrelaxed_state_if_all_gates_pass": True,
            "fresh_global_candidate_audit_after_write": True,
            "resume_positive_picard_if_gate_fails": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9am_preregistered_global_picard_overrelaxation.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
