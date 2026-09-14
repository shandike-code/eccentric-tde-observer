"""Phase 7B9ae：冻结第二次全局正 Picard 映射。"""

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
        (OUTPUT / "phase7b9ad_picard_contraction_audit_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        audit["decision"]["positive_picard_contraction_audit_passed"] is not True
        or audit["decision"]["continue_positive_picard_maps_authorized"] is not True
        or audit["decision"]["material_feedback_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9ae requires the contracted but unconverged 7B9ad state")
    input_relative = str(audit["input_state_path"])
    input_state = ROOT / input_relative
    if _sha256(input_state) != audit["input_state_sha256"]:
        raise RuntimeError("Phase 7B9ad input state changed")
    output_relative = (
        "outputs/checkpoints/phase7b9i_work/block_aitken_residual.dat"
    )
    output_state = ROOT / output_relative
    payload = {
        "phase": "7B9ae second globally coupled positive Picard radiation map",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] one further unrelaxed positive original source map "
            "after the measured 9.264e-2 contraction; [V] recoverable full-frequency "
            "ownership, positivity, boundary and resource audit; [O] the next "
            "self-guard residual and material feedback remain separate"
        ),
        "sources": {
            "phase7b9ad_summary": _source(
                "outputs/phase7b9ad_picard_contraction_audit_summary.json"
            ),
            "phase7b9ad_protocol": _source(
                "outputs/phase7b9ad_preregistered_picard_contraction_audit.json"
            ),
            "input_radiation_state": _source(input_relative),
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
            "accepted_source_relaxation_exactly": 1.0,
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "maximum_concurrent_processes": 2,
            "input_state_path": input_relative,
            "input_state_sha256": audit["input_state_sha256"],
            "output_state_path": output_relative,
            "output_state_previous_sha256": _sha256(output_state),
            "raw_float64_checkpoint_size_bytes": input_state.stat().st_size,
            "manifest_path": (
                "outputs/checkpoints/phase7b9ae_second_positive_picard/manifest.json"
            ),
            "report_directory": (
                "outputs/checkpoints/phase7b9ae_second_positive_picard/reports"
            ),
            "summary_path": (
                "outputs/phase7b9ae_second_positive_picard_map_summary.json"
            ),
            "figure_path": "outputs/phase7b9ae_second_positive_picard_map.png",
            "block_report_prefix": "phase7b9ae",
            "runner_path": "scripts/phase7b9ae_second_positive_picard_map.py",
            "input_audit_source_key": "phase7b9ad_summary",
            "input_audit_residual_key": (
                "mapped_state_global_original_operator_residual"
            ),
            "input_audit_boundary_l1_key": "mapped_state_boundary_spectrum_l1",
            "input_audit_bolometric_key": (
                "mapped_state_boundary_bolometric_fraction"
            ),
            "storage_strategy": (
                "overwrite only the reproducible historical block-Aitken residual "
                "work buffer; preserve the Phase 7B9ac current state and map-6 state"
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
            "minimum_input_and_mapped_intensity_at_least": 0.0,
            "input_global_residual_matches_phase7b9ab_absolute_tolerance": 2.0e-12,
            "input_boundary_metrics_match_phase7b9ab_absolute_tolerance": 2.0e-12,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "full_map_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "commit_recoverable_mapped_state_if_all_map_gates_pass": True,
            "evaluate_mapped_state_self_guard_residual_if_map_passes": True,
            "material_feedback": False,
            "accept_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9ae_preregistered_second_positive_picard_map.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
