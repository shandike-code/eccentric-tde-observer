"""Phase 7B9bg：冻结 I12 连续态的仿射 Krylov 映射。"""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from scripts import phase7b9av_preregister_candidate_picard_map as helper
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9av_preregister_candidate_picard_map as helper  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SCRATCH = "outputs/checkpoints/phase7b6h_full_frequency_iteration8.dat"
REFERENCE = "outputs/phase7b9bg_i12_map_reference.json"


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    audit = json.loads(
        (OUTPUT / "phase7b9bd_third_constrained_candidate_summary.json").read_text(
            encoding="utf-8"
        )
    )
    basis = json.loads(
        (OUTPUT / "phase7b9bc_third_fused_anderson_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        audit["decision"]["candidate_written"] is not True
        or audit["decision"]["fresh_global_self_audit_authorized"] is not True
        or audit["decision"]["material_feedback_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9bg requires the accepted third candidate audit")
    input_relative = str(basis["x4_state_path"])
    input_state = ROOT / input_relative
    output_state = ROOT / SCRATCH
    if helper._sha256(input_state) != basis["x4_state_sha256"]:
        raise RuntimeError("Phase 7B9bg I12 input state changed")
    if output_state.stat().st_size != input_state.stat().st_size:
        raise RuntimeError("Phase 7B9bg scratch checkpoint has the wrong size")
    eta_zero = next(row for row in audit["grid"] if float(row["eta"]) == 0.0)
    reference = {
        "phase": "7B9bg frozen I12 input-map reference",
        "classification": "[V] values copied from the frozen Phase 7B9bd eta=0 control",
        "global_original_operator_residual": audit["x4_control_global_residual"],
        "global_boundary_spectrum_l1": eta_zero["boundary_spectrum_l1"],
        "global_boundary_bolometric_fraction": eta_zero[
            "boundary_bolometric_fraction"
        ],
        "input_state_path": input_relative,
        "input_state_sha256": basis["x4_state_sha256"],
    }
    _write_json_atomic(ROOT / REFERENCE, reference)
    payload = {
        "phase": "7B9bg I12 affine Krylov map",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] apply one unrelaxed fixed-matter source map to I12 "
            "and reuse one explicitly superseded generated checkpoint as scratch; "
            "[V] ownership, positivity, residual reproduction, boundary and resources; "
            "[O] no matter feedback"
        ),
        "sources": {
            "phase7b9bd_summary": helper._source(
                "outputs/phase7b9bd_third_constrained_candidate_summary.json"
            ),
            "phase7b9bd_protocol": helper._source(
                "outputs/phase7b9bd_preregistered_third_constrained_candidate.json"
            ),
            "phase7b9bc_summary": helper._source(
                "outputs/phase7b9bc_third_fused_anderson_summary.json"
            ),
            "phase7b9bg_reference": helper._source(REFERENCE),
            "input_state": helper._source(input_relative),
            "finite_trial_protocol": helper._source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": helper._source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": helper._source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "generic_map_runner": helper._source(
                "scripts/phase7b9ac_global_positive_picard_map.py"
            ),
            "phase7b7i_worker": helper._source(
                "scripts/phase7b7i_second_radiation_map.py"
            ),
            "phase7b9d_worker_helpers": helper._source(
                "scripts/phase7b9d_inner_converged_base_radiation.py"
            ),
            "mixed_frame_operator": helper._source(
                "src/eccentric_tde_observer/mixed_frame_ale.py"
            ),
            "mixed_frame_frequency": helper._source(
                "src/eccentric_tde_observer/mixed_frame_frequency.py"
            ),
        },
        "configuration": {
            "phase_index": 1380,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "accepted_source_relaxation_exactly": 1.0,
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "maximum_concurrent_processes": 2,
            "input_state_path": input_relative,
            "input_state_sha256": basis["x4_state_sha256"],
            "output_state_path": SCRATCH,
            "output_state_previous_sha256": helper._sha256(output_state),
            "raw_float64_checkpoint_size_bytes": input_state.stat().st_size,
            "manifest_path": "outputs/checkpoints/phase7b9bg_i12_affine_map/manifest.json",
            "report_directory": "outputs/checkpoints/phase7b9bg_i12_affine_map/reports",
            "summary_path": "outputs/phase7b9bg_i12_affine_map_summary.json",
            "figure_path": "outputs/phase7b9bg_i12_affine_map.png",
            "block_report_prefix": "phase7b9bg",
            "runner_path": "scripts/phase7b9bg_i12_affine_map.py",
            "input_audit_source_key": "phase7b9bg_reference",
            "input_audit_residual_key": "global_original_operator_residual",
            "input_audit_boundary_l1_key": "global_boundary_spectrum_l1",
            "input_audit_bolometric_key": "global_boundary_bolometric_fraction",
            "scratch_reuse_note": (
                "Phase 7B6h iteration-8 raw checkpoint is superseded by later audited "
                "states; its path is reused without deleting any unrelated file"
            ),
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback_during_map": False,
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "each_frequency_group_owned_exactly_once": True,
            "minimum_input_and_mapped_intensity_at_least": 0.0,
            "input_global_residual_matches_phase7b9ab_absolute_tolerance": 2.0e-12,
            "input_boundary_metrics_match_phase7b9ab_absolute_tolerance": 2.0e-12,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "full_map_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "overwrite_only_named_superseded_checkpoint": True,
            "commit_recoverable_mapped_state_if_all_map_gates_pass": True,
            "construct_positive_affine_krylov_basis_if_map_passes": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9bg_preregistered_i12_affine_map.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
