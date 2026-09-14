"""Phase 7B9bv：冻结有限试步辐射的第二个连续收敛态确认。"""

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
CONFIRMATION_OUTPUT = "outputs/checkpoints/phase7b6f_full_frequency_iteration4.dat"


def main() -> None:
    summary = json.loads(
        (OUTPUT / "phase7b9bt_long_positive_picard_summary.json").read_text(
            encoding="utf-8"
        )
    )
    manifest_path = (
        OUTPUT / "checkpoints/phase7b9bt_long_positive_picard/manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    acceptance = json.loads(
        (OUTPUT / "phase7b9bu_preregistered_trial_residual_acceptance.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        summary["status"] != "complete"
        or summary["decision"]["positive_picard_sequence_converged"] is not True
        or summary["decision"]["material_feedback_authorized"] is not True
        or manifest["status"] != "complete"
        or acceptance["authorization"][
            "accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass"
        ]
        is not True
    ):
        raise RuntimeError("Phase 7B9bv requires completed Phase 7B9bt")
    final_record = manifest["iterations"][-1]
    if (
        final_record["input_state_path"] != manifest["accepted_state_path"]
        or final_record["input_state_sha256"] != manifest["accepted_state_sha256"]
        or final_record["global_original_operator_residual"] >= 1.0e-4
        or final_record["map_passed"] is not True
    ):
        raise RuntimeError("Phase 7B9bv first converged state lineage changed")
    input_relative = str(final_record["mapped_state_path"])
    input_state = ROOT / input_relative
    output_state = ROOT / CONFIRMATION_OUTPUT
    if helper._sha256(input_state) != final_record["mapped_state_sha256"]:
        raise RuntimeError("Phase 7B9bv mapped input changed")
    if input_state.stat().st_size != output_state.stat().st_size:
        raise RuntimeError("Phase 7B9bv confirmation buffer size changed")

    payload = {
        "phase": "7B9bv second consecutive fixed-matter convergence confirmation",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] audit the mapped successor of the first accepted "
            "below-1e-4 state with one fresh unrelaxed original source map; [V] "
            "require a second consecutive residual and both boundary guards; [O] "
            "formal material feedback remains a separate stage"
        ),
        "sources": {
            "phase7b9bt_summary": helper._source(
                "outputs/phase7b9bt_long_positive_picard_summary.json"
            ),
            "phase7b9bt_manifest": helper._source(
                "outputs/checkpoints/phase7b9bt_long_positive_picard/manifest.json"
            ),
            "phase7b9bt_protocol": helper._source(
                "outputs/phase7b9bt_preregistered_long_positive_picard.json"
            ),
            "phase7b9bu_acceptance": helper._source(
                "outputs/phase7b9bu_preregistered_trial_residual_acceptance.json"
            ),
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
            "phase_index": 1395,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "accepted_source_relaxation_exactly": 1.0,
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "maximum_concurrent_processes": 2,
            "previous_converged_state_path": final_record["input_state_path"],
            "previous_converged_state_sha256": final_record["input_state_sha256"],
            "previous_global_original_operator_residual": final_record[
                "global_original_operator_residual"
            ],
            "previous_boundary_spectrum_l1": final_record["boundary_spectrum_l1"],
            "previous_boundary_bolometric_fraction": final_record[
                "boundary_bolometric_fraction"
            ],
            "input_state_path": input_relative,
            "input_state_sha256": final_record["mapped_state_sha256"],
            "output_state_path": CONFIRMATION_OUTPUT,
            "output_state_previous_sha256": helper._sha256(output_state),
            "raw_float64_checkpoint_size_bytes": input_state.stat().st_size,
            "manifest_path": (
                "outputs/checkpoints/phase7b9bv_consecutive_confirmation/manifest.json"
            ),
            "report_directory": (
                "outputs/checkpoints/phase7b9bv_consecutive_confirmation/reports"
            ),
            "summary_path": (
                "outputs/phase7b9bv_consecutive_picard_confirmation_summary.json"
            ),
            "figure_path": (
                "outputs/phase7b9bv_consecutive_picard_confirmation.png"
            ),
            "block_report_prefix": "phase7b9bv",
            "runner_path": "scripts/phase7b9bv_consecutive_picard_confirmation.py",
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
            "both_global_original_operator_residuals_below": 1.0e-4,
            "both_boundary_spectrum_l1_below": 1.0e-3,
            "both_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "full_map_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "assemble_formal_h_he_feedback_pair_only_if_all_gates_pass": True,
            "accept_finite_trial_as_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
            "full_orbit": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9bv_preregistered_consecutive_picard_confirmation.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
