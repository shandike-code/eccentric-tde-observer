"""Phase 7B9al：冻结可恢复的全频率正 Picard 收敛协议。"""

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
    stable = json.loads(
        (OUTPUT / "phase7b9af_second_picard_contraction_audit_summary.json").read_text(
            encoding="utf-8"
        )
    )
    rejected = json.loads(
        (OUTPUT / "phase7b9ak_global_convex_krylov_line_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        stable["decision"]["continue_positive_picard_maps_authorized"] is not True
        or stable["decision"]["material_feedback_authorized"] is not False
        or rejected["decision"]["global_convex_line_search_passed"] is not False
        or rejected["decision"]["write_selected_blend_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9al requires the stable Picard state and rejected line")
    initial_relative = str(stable["input_state_path"])
    initial_path = ROOT / initial_relative
    initial_sha = _sha256(initial_path)
    if initial_sha != stable["input_state_sha256"]:
        raise RuntimeError("Phase 7B9af stable state changed")
    rejected_candidate = json.loads(
        (OUTPUT / "phase7b9ai_dominant_band_krylov_candidate_summary.json").read_text(
            encoding="utf-8"
        )
    )
    scratch_relative = str(rejected_candidate["candidate_state_path"])
    scratch_path = ROOT / scratch_relative
    scratch_sha = _sha256(scratch_path)
    if scratch_sha != rejected_candidate["candidate_state_sha256"]:
        raise RuntimeError("Phase 7B9ai rejected scratch buffer changed")
    if initial_path.stat().st_size != scratch_path.stat().st_size:
        raise RuntimeError("Phase 7B9al two buffers have different sizes")
    payload = {
        "phase": "7B9al recoverable positive Picard convergence sequence",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] alternate two existing full-frequency buffers for at "
            "most 24 unrelaxed positive original source maps; [V] every map is also "
            "the fresh self-guard audit of its input, with ownership, positivity, "
            "boundary, contraction and resource gates; [O] material feedback opens "
            "only after an audited input residual below 1e-4"
        ),
        "sources": {
            "phase7b9af_summary": _source(
                "outputs/phase7b9af_second_picard_contraction_audit_summary.json"
            ),
            "phase7b9ak_summary": _source(
                "outputs/phase7b9ak_global_convex_krylov_line_summary.json"
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
            "maximum_picard_maps": 24,
            "maximum_concurrent_processes": 2,
            "initial_state_path": initial_relative,
            "initial_state_sha256": initial_sha,
            "scratch_state_path": scratch_relative,
            "scratch_state_initial_sha256": scratch_sha,
            "raw_float64_checkpoint_size_bytes": initial_path.stat().st_size,
            "manifest_path": (
                "outputs/checkpoints/phase7b9al_positive_picard/manifest.json"
            ),
            "report_directory": (
                "outputs/checkpoints/phase7b9al_positive_picard/reports"
            ),
            "summary_path": (
                "outputs/phase7b9al_positive_picard_convergence_summary.json"
            ),
            "figure_path": "outputs/phase7b9al_positive_picard_convergence.png",
            "runner_path": (
                "scripts/phase7b9al_positive_picard_convergence.py"
            ),
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback_during_sequence": False,
        },
        "reference": {
            "initial_global_residual": stable[
                "mapped_state_global_original_operator_residual"
            ],
            "initial_boundary_spectrum_l1": stable[
                "mapped_state_boundary_spectrum_l1"
            ],
            "initial_boundary_bolometric_fraction": stable[
                "mapped_state_boundary_bolometric_fraction"
            ],
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "minimum_input_and_mapped_intensity_at_least": 0.0,
            "initial_audit_absolute_tolerance": 2.0e-12,
            "global_original_operator_residual_below": 1.0e-4,
            "subsequent_residual_contraction_ratio_below": 0.99,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_worker_wall_time_strictly_below_s": 60.0,
            "each_full_map_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "alternate_existing_buffers_if_each_map_gate_passes": True,
            "accept_audited_radiation_state_if_residual_gate_passes": True,
            "material_feedback_only_after_convergence": True,
            "accept_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9al_preregistered_positive_picard_convergence.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
