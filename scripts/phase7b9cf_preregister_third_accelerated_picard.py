"""Phase 7B9cf：冻结第二次 Anderson 映射后的两步 Picard 延拓。"""

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
    mapped = json.loads(
        (OUTPUT / "phase7b9cd_second_candidate_map_summary.json").read_text(
            encoding="utf-8"
        )
    )
    anchor = json.loads(
        (OUTPUT / "phase7b9ce_second_map_anchor_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        mapped["decision"]["global_positive_picard_map_passed"] is not True
        or anchor["decision"]["third_accelerated_picard_continuation_authorized"]
        is not True
        or anchor["anchor_state_sha256"] != mapped["output_state_sha256"]
    ):
        raise RuntimeError("Phase 7B9cf requires the audited second map and anchor")
    immutable_relative = str(anchor["anchor_state_path"])
    initial_relative = str(mapped["output_state_path"])
    scratch_relative = "outputs/checkpoints/phase7b6j_line_search_iteration14.dat"
    immutable = ROOT / immutable_relative
    initial = ROOT / initial_relative
    scratch = ROOT / scratch_relative
    if (
        helper._sha256(immutable) != anchor["anchor_state_sha256"]
        or helper._sha256(initial) != mapped["output_state_sha256"]
        or immutable.stat().st_size != initial.stat().st_size
        or immutable.stat().st_size != scratch.stat().st_size
    ):
        raise RuntimeError("Phase 7B9cf checkpoint chain changed")
    scratch_sha = helper._sha256(scratch)
    payload = {
        "phase": "7B9cf third accelerated fixed-matter positive Picard continuation",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] import the independently audited Phase 7B9cd map, "
            "then apply exactly two unrelaxed original source maps with three "
            "workers; [V] audit positivity, contraction, boundary, ownership and "
            "resources for both maps; [O] material feedback remains closed above "
            "the 1e-4 fixed-matter residual gate"
        ),
        "sources": {
            "phase7b9cd_summary": helper._source(
                "outputs/phase7b9cd_second_candidate_map_summary.json"
            ),
            "phase7b9cd_protocol": helper._source(
                "outputs/phase7b9cd_preregistered_second_candidate_map.json"
            ),
            "phase7b9ce_summary": helper._source(
                "outputs/phase7b9ce_second_map_anchor_summary.json"
            ),
            "phase7b9ce_protocol": helper._source(
                "outputs/phase7b9ce_preregistered_second_map_anchor.json"
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
            "seeded_picard_runner": helper._source(
                "scripts/phase7b9_seeded_picard.py"
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
            "phase_index": 1407,
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
            "stop_after_iteration": 2,
            "seed_summary_source_key": "phase7b9cd_summary",
            "seed_summary_format": "global_map",
            "seed_iteration_count": 1,
            "immutable_anchor_path": immutable_relative,
            "immutable_anchor_sha256": anchor["anchor_state_sha256"],
            "initial_state_path": initial_relative,
            "initial_state_sha256": mapped["output_state_sha256"],
            "scratch_state_path": scratch_relative,
            "scratch_state_initial_sha256": scratch_sha,
            "raw_float64_checkpoint_size_bytes": initial.stat().st_size,
            "manifest_path": (
                "outputs/checkpoints/phase7b9cf_third_accelerated_picard/manifest.json"
            ),
            "report_directory": (
                "outputs/checkpoints/phase7b9cf_third_accelerated_picard/reports"
            ),
            "summary_path": "outputs/phase7b9cf_third_accelerated_picard_summary.json",
            "figure_path": "outputs/phase7b9cf_third_accelerated_picard.png",
            "runner_path": "scripts/phase7b9cf_third_accelerated_picard.py",
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
            "run_exactly_two_new_picard_maps": True,
            "third_slow_mode_test_after_pause": True,
            "material_feedback_only_after_convergence": True,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9cf_preregistered_third_accelerated_picard.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
