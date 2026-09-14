"""Phase 7B9ac：冻结一次全频率正 Picard 映射协议。"""

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
        (OUTPUT / "phase7b9ab_global_trial_residual_audit_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        audit["decision"]["global_trial_residual_audit_passed"] is not False
        or audit["gate_checks"]["global_boundary_spectrum_pass"] is not True
        or audit["gate_checks"]["global_boundary_bolometric_pass"] is not True
    ):
        raise RuntimeError("Phase 7B9ac requires the frozen 7B9ab residual-only failure")
    trial_relative = str(audit["trial_state_path"])
    trial = ROOT / trial_relative
    if _sha256(trial) != audit["trial_state_sha256"]:
        raise RuntimeError("Phase 7B9ab trial state changed")
    output_relative = "outputs/checkpoints/phase7b9i_work/state_a.dat"
    output_state = ROOT / output_relative
    payload = {
        "phase": "7B9ac globally coupled positive Picard radiation map",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] apply exactly one unrelaxed original source map to "
            "all 76 natural-frequency blocks with one common frozen trial state as "
            "the neighboring-frequency guard; [V] recoverable ownership, positivity, "
            "boundary and resource audit; [O] the mapped state's self-guard residual "
            "and all material feedback remain separate stages"
        ),
        "sources": {
            "phase7b9ab_summary": _source(
                "outputs/phase7b9ab_global_trial_residual_audit_summary.json"
            ),
            "phase7b9ab_protocol": _source(
                "outputs/phase7b9ab_preregistered_global_trial_residual_audit.json"
            ),
            "input_trial_state": _source(trial_relative),
            "finite_trial_protocol": _source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": _source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
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
            "ali_preconditioner": _source(
                "src/eccentric_tde_observer/mixed_frame_ali.py"
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
            "input_state_path": trial_relative,
            "input_state_sha256": audit["trial_state_sha256"],
            "output_state_path": output_relative,
            "output_state_previous_sha256": _sha256(output_state),
            "raw_float64_checkpoint_size_bytes": trial.stat().st_size,
            "manifest_path": (
                "outputs/checkpoints/phase7b9ac_global_positive_picard/manifest.json"
            ),
            "report_directory": (
                "outputs/checkpoints/phase7b9ac_global_positive_picard/reports"
            ),
            "storage_strategy": (
                "overwrite only the failed Phase 7B9t partial state_a buffer; preserve "
                "the map-6 state_b and Phase 7B9ab trial state"
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
            "commit_recoverable_mapped_state_if_all_map_gates_pass": True,
            "evaluate_mapped_state_self_guard_residual_if_map_passes": True,
            "material_feedback": False,
            "accept_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9ac_preregistered_global_positive_picard_map.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
