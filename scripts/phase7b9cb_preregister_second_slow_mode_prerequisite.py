"""Phase 7B9cb：冻结第二次慢模外推所需的唯一补充 Picard 映射。"""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from scripts import phase7b9al_preregister_positive_picard_convergence as helper
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9al_preregister_positive_picard_convergence as helper  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def main() -> None:
    continuation = json.loads(
        (OUTPUT / "phase7b9ca_accelerated_picard_summary.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (
            OUTPUT / "checkpoints/phase7b9ca_accelerated_picard/manifest.json"
        ).read_text(encoding="utf-8")
    )
    anchor = json.loads(
        (OUTPUT / "phase7b9bz_accelerated_anchor_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        continuation["status"] != "running"
        or continuation["completed_picard_maps"] != 2
        or len(continuation["iterations"]) != 2
        or manifest["status"] != "running"
        or manifest["active_iteration"] is not None
        or manifest["iterations"][-1]["map_passed"] is not True
        or anchor["decision"]["accelerated_positive_picard_continuation_authorized"]
        is not True
    ):
        raise RuntimeError("Phase 7B9cb requires the paused two-record continuation")
    latest = continuation["iterations"][-1]
    initial_relative = str(manifest["current_input_path"])
    scratch_relative = str(manifest["next_output_path"])
    anchor_relative = str(anchor["anchor_state_path"])
    initial = ROOT / initial_relative
    scratch = ROOT / scratch_relative
    immutable = ROOT / anchor_relative
    if (
        manifest["current_input_sha256"] != latest["mapped_state_sha256"]
        or helper._sha256(initial) != latest["mapped_state_sha256"]
        or helper._sha256(scratch) != anchor["anchor_state_sha256"]
        or helper._sha256(immutable) != anchor["anchor_state_sha256"]
        or initial.stat().st_size != scratch.stat().st_size
    ):
        raise RuntimeError("Phase 7B9cb three-state storage chain changed")
    payload = {
        "phase": "7B9cb second slow-mode prerequisite Picard map",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] import the two audited Phase 7B9ca records and apply "
            "exactly one additional unrelaxed original source map; the immutable "
            "Phase 7B9bz anchor then supplies three consecutive states for a second "
            "Anderson(1) test; [V] all map guards remain active; [O] this is not a "
            "material-feedback authorization"
        ),
        "sources": {
            "phase7b9ca_summary": helper._source(
                "outputs/phase7b9ca_accelerated_picard_summary.json"
            ),
            "phase7b9ca_protocol": helper._source(
                "outputs/phase7b9ca_preregistered_accelerated_picard.json"
            ),
            "phase7b9bz_summary": helper._source(
                "outputs/phase7b9bz_accelerated_anchor_summary.json"
            ),
            "immutable_first_state": helper._source(anchor_relative),
            "finite_trial_protocol": helper._source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": helper._source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": helper._source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "generic_positive_picard_runner": helper._source(
                "scripts/phase7b9ac_global_positive_picard_map.py"
            ),
            "positive_sequence_engine": helper._source(
                "scripts/phase7b9al_positive_picard_convergence.py"
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
            "phase_index": 1403,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_picard_maps": 3,
            "maximum_concurrent_processes": 3,
            "immutable_first_state_path": anchor_relative,
            "immutable_first_state_sha256": anchor["anchor_state_sha256"],
            "initial_state_path": initial_relative,
            "initial_state_sha256": latest["mapped_state_sha256"],
            "scratch_state_path": scratch_relative,
            "scratch_state_initial_sha256": anchor["anchor_state_sha256"],
            "raw_float64_checkpoint_size_bytes": initial.stat().st_size,
            "manifest_path": (
                "outputs/checkpoints/phase7b9cb_second_slow_mode/manifest.json"
            ),
            "report_directory": (
                "outputs/checkpoints/phase7b9cb_second_slow_mode/reports"
            ),
            "summary_path": "outputs/phase7b9cb_second_slow_mode_summary.json",
            "figure_path": "outputs/phase7b9cb_second_slow_mode.png",
            "runner_path": "scripts/phase7b9cb_second_slow_mode_prerequisite.py",
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback_during_sequence": False,
        },
        "reference": {
            "initial_global_residual": continuation["iterations"][0][
                "global_original_operator_residual"
            ],
            "initial_boundary_spectrum_l1": continuation["iterations"][0][
                "boundary_spectrum_l1"
            ],
            "initial_boundary_bolometric_fraction": continuation["iterations"][0][
                "boundary_bolometric_fraction"
            ],
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "minimum_input_and_mapped_intensity_at_least": 0.0,
            "initial_audit_absolute_tolerance": 2.0e-12,
            "global_original_operator_residual_below": 1.0e-4,
            "subsequent_residual_contraction_ratio_below": 1.01,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_worker_wall_time_strictly_below_s": 60.0,
            "each_full_map_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "seed_manifest_from_phase7b9ca": True,
            "apply_exactly_one_additional_map": True,
            "construct_second_slow_mode_candidate_if_map_passes": True,
            "material_feedback_only_after_convergence": True,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9cb_preregistered_second_slow_mode.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
