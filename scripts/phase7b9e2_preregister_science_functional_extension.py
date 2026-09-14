"""Phase 7B9e2：冻结两轮最小科学泛函续算扩展。"""

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
    summary_path = OUTPUT / "phase7b9e_science_functional_continuation_summary.json"
    manifest_path = OUTPUT / "checkpoints/phase7b9d_work/science_functional_manifest.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        summary["decision"]["phase7b9e_gate_passed"] is not False
        or int(summary["final_additional_map"]) != 8
        or int(summary["consecutive_converged_maps"]) != 1
        or not float(summary["final_global_source_map_residual"]) < 1.0e-4
        or manifest["status"] != "gate_failed"
        or int(manifest["current_additional_map"]) != 8
        or manifest["current_state_sha256"] != summary["final_radiation_sha256"]
    ):
        raise RuntimeError("Phase 7B9e2 requires the specific one-pass Phase 7B9e budget exhaustion")
    payload = {
        "phase": "7B9e2 minimal two-map science-functional extension",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] preserve all Phase 7B9e physics and gates, add only "
            "maps 9--10; [V] global source and boundary science functionals; "
            "[O] formal H/He rates remain unevaluated"
        ),
        "sources": {
            "phase7b9e_summary": _source(
                "outputs/phase7b9e_science_functional_continuation_summary.json"
            ),
            "phase7b9e_manifest": _source(
                "outputs/checkpoints/phase7b9d_work/science_functional_manifest.json"
            ),
            "phase7b9e_protocol": _source(
                "outputs/phase7b9e_preregistered_science_functional_continuation.json"
            ),
            "phase7b9e_runner": _source(
                "scripts/phase7b9e_science_functional_continuation.py"
            ),
            "phase7b9d_original_protocol": _source(
                "outputs/phase7b9d_preregistered_inner_converged_base_radiation.json"
            ),
            "phase7b9d_runner": _source(
                "scripts/phase7b9d_inner_converged_base_radiation.py"
            ),
            "current_committed_radiation": _source(
                str(summary["final_radiation_path"])
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "current_material_state": _source(
                "outputs/phase7b7h_second_material_iterate.npz"
            ),
            "physical_old_time_level": _source(
                "outputs/phase7b4r_depth128_phase2048.npz"
            ),
        },
        "configuration": {
            "phase_index": int(summary["phase_index"]),
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "raw_float64_checkpoint_size_bytes": 10099884032,
            "initial_source_maps_at_current_material": 1,
            "starting_additional_map": 8,
            "maximum_total_additional_maps": 10,
            "minimum_consecutive_converged_maps": 2,
            "stop_only_after_even_additional_map": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_concurrent_processes": 2,
            "work_directory": "outputs/checkpoints/phase7b9e2_work",
            "extension_manifest": (
                "outputs/checkpoints/phase7b9e2_work/science_functional_manifest.json"
            ),
            "separate_output_buffers_preserve_phase7b9e_states": True,
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
            "committed_start_sha256_exactly": summary["final_radiation_sha256"],
        },
        "authorization": {
            "compare_formal_h_he_rates_and_heating_on_last_two_states_if_passes": True,
            "complete_recoverable_newton_residual": False,
            "full_frequency_jv": False,
            "newton_step": False,
            "accept_dynamic_NLTE_solution": False,
            "full_orbit": False,
            "phase4_replacement": False,
            "uvot": False,
        },
    }
    path = OUTPUT / "phase7b9e2_preregistered_science_functional_extension.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
