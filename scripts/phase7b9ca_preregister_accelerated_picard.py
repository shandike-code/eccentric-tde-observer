"""Phase 7B9ca：冻结慢模候选之后的可恢复正 Picard 延拓。"""

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
    candidate = json.loads(
        (OUTPUT / "phase7b9bx_slow_mode_anderson_summary.json").read_text(
            encoding="utf-8"
        )
    )
    mapped = json.loads(
        (OUTPUT / "phase7b9by_slow_mode_candidate_map_summary.json").read_text(
            encoding="utf-8"
        )
    )
    anchor = json.loads(
        (OUTPUT / "phase7b9bz_accelerated_anchor_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        candidate["decision"]["protected_slow_mode_candidate_passed"] is not True
        or mapped["decision"]["global_positive_picard_map_passed"] is not True
        or anchor["decision"]["accelerated_positive_picard_continuation_authorized"]
        is not True
        or mapped["input_state_sha256"] != candidate["candidate_state_sha256"]
        or anchor["anchor_state_sha256"] != mapped["output_state_sha256"]
    ):
        raise RuntimeError("Phase 7B9ca requires the audited candidate/map/anchor chain")
    initial_relative = str(mapped["output_state_path"])
    scratch_relative = str(candidate["candidate_state_path"])
    immutable_relative = str(anchor["anchor_state_path"])
    initial = ROOT / initial_relative
    scratch = ROOT / scratch_relative
    immutable = ROOT / immutable_relative
    if (
        helper._sha256(initial) != mapped["output_state_sha256"]
        or helper._sha256(scratch) != candidate["candidate_state_sha256"]
        or helper._sha256(immutable) != anchor["anchor_state_sha256"]
        or initial.stat().st_size != scratch.stat().st_size
        or initial.stat().st_size != immutable.stat().st_size
    ):
        raise RuntimeError("Phase 7B9ca checkpoint chain changed")
    payload = {
        "phase": "7B9ca accelerated fixed-matter positive Picard continuation",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] import the independently audited Phase 7B9by map as "
            "sequence record zero, then alternate its two generated buffers for at "
            "most 31 further unrelaxed original source maps; [V] audit positivity, "
            "contraction, boundary, ownership and resources on every new map; [O] "
            "material feedback opens only below 1e-4"
        ),
        "sources": {
            "phase7b9bx_summary": helper._source(
                "outputs/phase7b9bx_slow_mode_anderson_summary.json"
            ),
            "phase7b9by_summary": helper._source(
                "outputs/phase7b9by_slow_mode_candidate_map_summary.json"
            ),
            "phase7b9bz_summary": helper._source(
                "outputs/phase7b9bz_accelerated_anchor_summary.json"
            ),
            "immutable_mapped_anchor": helper._source(immutable_relative),
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
            "phase_index": 1402,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_picard_maps": 32,
            "maximum_concurrent_processes": 2,
            "immutable_anchor_path": immutable_relative,
            "immutable_anchor_sha256": anchor["anchor_state_sha256"],
            "initial_state_path": initial_relative,
            "initial_state_sha256": mapped["output_state_sha256"],
            "scratch_state_path": scratch_relative,
            "scratch_state_initial_sha256": candidate["candidate_state_sha256"],
            "raw_float64_checkpoint_size_bytes": initial.stat().st_size,
            "manifest_path": (
                "outputs/checkpoints/phase7b9ca_accelerated_picard/manifest.json"
            ),
            "report_directory": (
                "outputs/checkpoints/phase7b9ca_accelerated_picard/reports"
            ),
            "summary_path": "outputs/phase7b9ca_accelerated_picard_summary.json",
            "figure_path": "outputs/phase7b9ca_accelerated_picard.png",
            "runner_path": "scripts/phase7b9ca_accelerated_picard.py",
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback_during_sequence": False,
        },
        "reference": {
            "initial_global_residual": mapped[
                "input_global_original_operator_residual"
            ],
            "initial_boundary_spectrum_l1": mapped["input_boundary_spectrum_l1"],
            "initial_boundary_bolometric_fraction": mapped[
                "input_boundary_bolometric_fraction"
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
            "seed_manifest_from_independently_audited_map": True,
            "alternate_only_named_generated_buffers": True,
            "pause_after_one_new_map_for_second_slow_mode_test": True,
            "material_feedback_only_after_convergence": True,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9ca_preregistered_accelerated_picard.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
