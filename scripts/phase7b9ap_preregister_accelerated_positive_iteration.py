"""Phase 7B9ap：冻结全局正 Picard 方向超松弛收敛循环。"""

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
        (OUTPUT / "phase7b9ao_overrelaxed_candidate_audit_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        audit["decision"]["overrelaxed_candidate_global_audit_passed"] is not True
        or audit["decision"]["prediction_reproduced"] is not True
        or audit["decision"]["continue_positive_iteration_authorized"] is not True
        or audit["decision"]["material_feedback_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9ap requires the audited unconverged theta=8 state")
    current_relative = str(audit["input_state_path"])
    current_sha = _sha256(ROOT / current_relative)
    if current_sha != audit["input_state_sha256"]:
        raise RuntimeError("Phase 7B9ao current state changed")
    line = json.loads(
        (OUTPUT / "phase7b9am_global_picard_overrelaxation_summary.json").read_text(
            encoding="utf-8"
        )
    )
    scratch_relative = str(line["upper_state_path"])
    scratch_sha = _sha256(ROOT / scratch_relative)
    if scratch_sha != line["upper_state_sha256"]:
        raise RuntimeError("Phase 7B9ap scratch endpoint changed")
    current = ROOT / current_relative
    scratch = ROOT / scratch_relative
    if current.stat().st_size != scratch.stat().st_size:
        raise RuntimeError("Phase 7B9ap buffers have different sizes")
    payload = {
        "phase": "7B9ap accelerated globally positive radiation iteration",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] repeat at most 16 cycles of one full positive Picard "
            "map followed by a fixed global theta grid [0,1,2,4,6,8] along that "
            "Picard direction; [V] each next map independently reproduces the prior "
            "affine prediction, while every cycle audits ownership, positivity, "
            "boundary and resources; [O] material feedback opens only after a freshly "
            "mapped input residual below 1e-4"
        ),
        "sources": {
            "phase7b9ao_summary": _source(
                "outputs/phase7b9ao_overrelaxed_candidate_audit_summary.json"
            ),
            "phase7b9ao_protocol": _source(
                "outputs/phase7b9ao_preregistered_overrelaxed_candidate_audit.json"
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
            "generic_positive_picard_runner": _source(
                "scripts/phase7b9ac_global_positive_picard_map.py"
            ),
            "global_line_evaluator": _source(
                "scripts/phase7b9am_global_picard_overrelaxation.py"
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
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_cycles": 16,
            "maximum_concurrent_processes": 2,
            "theta_candidates": [0.0, 1.0, 2.0, 4.0, 6.0, 8.0],
            "initial_current_state_path": current_relative,
            "initial_current_state_sha256": current_sha,
            "scratch_state_path": scratch_relative,
            "scratch_state_initial_sha256": scratch_sha,
            "raw_float64_checkpoint_size_bytes": current.stat().st_size,
            "manifest_path": (
                "outputs/checkpoints/phase7b9ap_accelerated_positive/manifest.json"
            ),
            "report_directory": (
                "outputs/checkpoints/phase7b9ap_accelerated_positive/reports"
            ),
            "grid_path": (
                "outputs/checkpoints/phase7b9ap_accelerated_positive/fixed_grid.json"
            ),
            "summary_path": (
                "outputs/phase7b9ap_accelerated_positive_iteration_summary.json"
            ),
            "figure_path": (
                "outputs/phase7b9ap_accelerated_positive_iteration.png"
            ),
            "runner_path": (
                "scripts/phase7b9ap_accelerated_positive_iteration.py"
            ),
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback_during_cycles": False,
        },
        "reference": {
            "initial_global_residual": audit[
                "mapped_state_global_original_operator_residual"
            ],
            "initial_boundary_spectrum_l1": audit[
                "mapped_state_boundary_spectrum_l1"
            ],
            "initial_boundary_bolometric_fraction": audit[
                "mapped_state_boundary_bolometric_fraction"
            ],
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "minimum_intensity_at_least": 0.0,
            "prediction_reproduction_absolute_tolerance": 2.0e-12,
            "global_original_operator_residual_below": 1.0e-4,
            "selected_residual_ratio_to_current_below": 0.95,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "map_worker_wall_time_strictly_below_s": 30.0,
            "line_worker_wall_time_strictly_below_s": 120.0,
            "each_stage_wall_time_strictly_below_s": 1200.0,
            "write_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "run_recoverable_accelerated_cycles": True,
            "accept_freshly_audited_state_if_residual_gate_passes": True,
            "material_feedback_only_after_convergence": True,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9ap_preregistered_accelerated_positive_iteration.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
