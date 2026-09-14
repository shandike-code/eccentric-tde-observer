"""冻结 Phase 7B9e 以科学泛函为准的基点辐射续算。"""

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


def _source(path: str) -> dict[str, str | int]:
    absolute = ROOT / path
    return {
        "path": path,
        "size_bytes": absolute.stat().st_size,
        "sha256": _sha256(absolute),
    }


def main() -> None:
    audit = json.loads(
        (OUTPUT / "phase7b9d_inner_gate_audit_summary.json").read_text()
    )
    if not audit["decision"][
        "corrected_science_functional_continuation_design_authorized"
    ]:
        raise RuntimeError("Phase 7B9d did not authorize corrected continuation")
    sources = {
        "phase7b9d_audit": "outputs/phase7b9d_inner_gate_audit_summary.json",
        "phase7b9d_snapshot": "outputs/phase7b9d_inner_gate_audit_snapshot.json",
        "phase7b9d_original_protocol": "outputs/phase7b9d_preregistered_inner_converged_base_radiation.json",
        "phase7b9d_runner": "scripts/phase7b9d_inner_converged_base_radiation.py",
        "phase7b6p_formal_flux": "outputs/phase7b6p_final_formal_flux_summary.json",
        "current_committed_radiation": "outputs/checkpoints/phase7b9d_work/state_a.dat",
        "phase7b5p_master_input": "outputs/phase7b5p_master_worker_input.npz",
        "current_material_state": "outputs/phase7b7h_second_material_iterate.npz",
        "physical_old_time_level": "outputs/phase7b4r_depth128_phase2048.npz",
    }
    protocol = {
        "phase": "7B9e corrected science-functional base-radiation continuation",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] retain omega=1, map budget and two-consecutive-state rule; "
            "[V] resume the committed full-frequency map and gate global source change plus boundary flux; "
            "[O] H/He rate and heating convergence deferred to the next formal-feedback gate"
        ),
        "sources": {name: _source(path) for name, path in sources.items()},
        "configuration": {
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "raw_float64_checkpoint_size_bytes": 10099884032,
            "starting_additional_map": 1,
            "starting_total_source_maps_at_current_material": 2,
            "maximum_total_additional_maps": 8,
            "minimum_consecutive_converged_maps": 2,
            "stop_only_after_even_additional_map": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_concurrent_processes": 2,
            "work_directory": "outputs/checkpoints/phase7b9d_work",
            "corrected_manifest": "outputs/checkpoints/phase7b9d_work/science_functional_manifest.json",
            "final_radiation_output": "outputs/checkpoints/phase7b9d_work/state_b.dat",
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
            "committed_start_sha256_exactly": audit["committed_radiation_sha256"],
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
    path = OUTPUT / "phase7b9e_preregistered_science_functional_continuation.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(json.dumps({"path": str(path), "sha256": _sha256(path)}, indent=2))


if __name__ == "__main__":
    main()
