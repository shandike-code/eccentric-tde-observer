"""Phase 7B9i：冻结有限准 Newton 试步的全频辐射收敛协议。"""

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


def _source(path: str) -> dict[str, object]:
    absolute = ROOT / path
    return {
        "path": path,
        "size_bytes": absolute.stat().st_size,
        "sha256": _sha256(absolute),
    }


def main() -> None:
    trial_path = OUTPUT / "phase7b9i_finite_trial_material_summary.json"
    base_path = OUTPUT / "phase7b9e2_science_functional_extension_summary.json"
    trial = json.loads(trial_path.read_text(encoding="utf-8"))
    base = json.loads(base_path.read_text(encoding="utf-8"))
    if (
        trial["decision"]["trial_full_frequency_radiation_authorized"] is not True
        or trial["decision"]["finite_trial_may_be_called_jv"] is not False
        or base["decision"]["phase7b9e2_gate_passed"] is not True
    ):
        raise RuntimeError("Phase 7B9i radiation requires passed trial and base gates")
    payload = {
        "phase": "7B9i finite protected quasi-Newton trial radiation",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] unchanged 9632x32x4096 fixed-material source iteration, "
            "two consecutive 1e-4 global passes and even-map stop; [V] recoverable "
            "global source and boundary functionals; [O] trial feedback not yet assembled"
        ),
        "sources": {
            "phase7b9i_trial_summary": _source(
                "outputs/phase7b9i_finite_trial_material_summary.json"
            ),
            "phase7b9g_decision": _source(
                "outputs/phase7b9g_jv_fidelity_decision_summary.json"
            ),
            "phase7b9e2_summary": _source(
                "outputs/phase7b9e2_science_functional_extension_summary.json"
            ),
            "current_material_state": _source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "initial_radiation_checkpoint": _source(
                str(base["final_radiation_path"])
            ),
            "phase7b7i_template_protocol": _source(
                "outputs/phase7b7i_preregistered_second_radiation_map.json"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "physical_old_time_level": _source(
                "outputs/phase7b4r_depth128_phase2048.npz"
            ),
            "phase7b9d_runner": _source(
                "scripts/phase7b9d_inner_converged_base_radiation.py"
            ),
            "phase7b7i_runner": _source(
                "scripts/phase7b7i_second_radiation_map.py"
            ),
        },
        "configuration": {
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "raw_float64_checkpoint_size_bytes": 10099884032,
            "initial_source_maps_at_current_material": 0,
            "starting_additional_map": 0,
            "maximum_total_additional_maps": 12,
            "minimum_consecutive_converged_maps": 2,
            "stop_only_after_even_additional_map": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_concurrent_processes": 2,
            "work_directory": "outputs/checkpoints/phase7b9i_work",
            "manifest": "outputs/checkpoints/phase7b9i_work/manifest.json",
            "minimum_free_bytes_after_allocations": 8589934592,
            "one_map_internal_ledger_is_admission_gate": False,
            "one_map_internal_ledger_is_recorded": True,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback_during_radiation_continuation": False,
        },
        "gates": {
            "global_source_map_residual_below": 1.0e-4,
            "boundary_flux_spectrum_l1_below": 1.0e-3,
            "boundary_flux_bolometric_fraction_below": 1.0e-3,
            "minimum_intensity_at_least": 0.0,
            "each_iteration_block_count_exactly": 76,
            "each_iteration_owned_frequency_groups_exactly": 9632,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_iteration_wall_time_strictly_below_s": 900.0,
        },
        "authorization": {
            "assemble_trial_formal_h_he_feedback_if_passes": True,
            "accept_trial_as_nonlinear_step": False,
            "call_trial_a_jv": False,
            "newton_step": False,
            "accept_dynamic_NLTE_solution": False,
            "full_orbit": False,
            "phase4_replacement": False,
            "uvot": False,
        },
    }
    path = OUTPUT / "phase7b9i_preregistered_finite_trial_radiation.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
