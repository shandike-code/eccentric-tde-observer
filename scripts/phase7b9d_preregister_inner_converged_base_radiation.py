"""冻结 Phase 7B9d 可恢复基点辐射内迭代。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

from eccentric_tde_observer.coupled_material_newton_krylov import (
    GroundStateLogSimplexCodec,
)


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
        "sha256": _sha256(absolute),
        "size_bytes": absolute.stat().st_size,
    }


def _write_npy_atomic(path: Path, value: np.ndarray) -> None:
    temporary = path.with_name(f"{path.stem}.tmp.npy")
    np.save(temporary, value)
    os.replace(temporary, path)


def main() -> None:
    material_path = OUTPUT / "phase7b7h_second_material_iterate.npz"
    with np.load(material_path) as material:
        temperature = np.array(material["temperature_k"], copy=True)
        hydrogen = np.array(material["hydrogen_fraction"], copy=True)
        helium = np.array(material["helium_fraction"], copy=True)
    codec = GroundStateLogSimplexCodec(temperature.size)
    encoded = np.asarray(codec.encode(temperature, hydrogen, helium))
    encoded_path = OUTPUT / "phase7b9d_encoded_base_material_state.npy"
    _write_npy_atomic(encoded_path, encoded)
    decoded = codec.decode(encoded)
    if (
        np.max(np.abs(decoded.temperature_k - temperature) / temperature) >= 1.0e-12
        or np.max(np.abs(decoded.hydrogen_fraction - hydrogen)) >= 1.0e-12
        or np.max(np.abs(decoded.helium_fraction - helium)) >= 1.0e-12
    ):
        raise ArithmeticError("Phase 7B9d encoded base material round trip failed")

    sources = {
        "phase7b9c_summary": "outputs/phase7b9c_low_rank_preconditioner_summary.json",
        "recoverable_residual_module": "src/eccentric_tde_observer/full_frequency_residual_evaluation.py",
        "material_codec_module": "src/eccentric_tde_observer/coupled_material_newton_krylov.py",
        "phase7b7i_template_protocol": "outputs/phase7b7i_preregistered_second_radiation_map.json",
        "phase7b7i_worker": "scripts/phase7b7i_second_radiation_map.py",
        "phase7b7e_worker": "scripts/phase7b7e_radiation_direction.py",
        "phase7b5x_context": "scripts/phase7b5x_full_depth_block_probe.py",
        "current_material_state": "outputs/phase7b7h_second_material_iterate.npz",
        "encoded_material_state": "outputs/phase7b9d_encoded_base_material_state.npy",
        "physical_old_time_level": "outputs/phase7b4r_depth128_phase2048.npz",
        "initial_radiation_checkpoint": "outputs/checkpoints/phase7b7i_second_radiation_map.dat",
        "phase7b5p_master_input": "outputs/phase7b5p_master_worker_input.npz",
    }
    protocol = {
        "phase": "7B9d recoverable inner-converged base radiation solve",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] omega=1 inexact inner tolerance and two-consecutive-map gate; "
            "[V] full 9632x32x4096 fixed-material radiation maps; "
            "[O] formal feedback and encoded Newton residual deferred to Phase 7B9e"
        ),
        "sources": {name: _source(path) for name, path in sources.items()},
        "configuration": {
            "phase_index": 1367,
            "encoded_unknown_count": 512,
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "raw_float64_checkpoint_size_bytes": 10099884032,
            "initial_source_maps_at_current_material": 1,
            "maximum_additional_source_maps": 8,
            "minimum_consecutive_converged_maps": 2,
            "stop_only_after_even_additional_map": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_concurrent_processes": 2,
            "work_directory": "outputs/checkpoints/phase7b9d_work",
            "inner_manifest": "outputs/checkpoints/phase7b9d_work/inner_manifest.json",
            "residual_manifest": "outputs/checkpoints/phase7b9d_work/residual_manifest.json",
            "final_radiation_output": "outputs/checkpoints/phase7b9d_work/state_b.dat",
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback_during_inner_solve": False,
        },
        "gates": {
            "raw_source_map_residual_below": 1.0e-4,
            "boundary_flux_spectrum_l1_below": 1.0e-3,
            "boundary_flux_bolometric_fraction_below": 1.0e-3,
            "maximum_internal_energy_ledger_residual_below": 1.0e-8,
            "minimum_intensity_at_least": 0.0,
            "each_iteration_block_count_exactly": 76,
            "each_iteration_owned_frequency_groups_exactly": 9632,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_iteration_wall_time_strictly_below_s": 900.0,
            "minimum_free_bytes_after_allocations": 8589934592,
            "encoded_material_roundtrip_below": 1.0e-12,
        },
        "authorization": {
            "formal_feedback_and_encoded_residual_if_passes": True,
            "full_frequency_jv": False,
            "newton_step": False,
            "accept_dynamic_NLTE_solution": False,
            "full_orbit": False,
            "phase4_replacement": False,
            "uvot": False,
        },
    }
    path = OUTPUT / "phase7b9d_preregistered_inner_converged_base_radiation.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(json.dumps({"path": str(path), "sha256": _sha256(path)}, indent=2))


if __name__ == "__main__":
    main()
