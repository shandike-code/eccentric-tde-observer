"""Phase 7B7b：执行一次实际相位时长的冻结辐射物质响应。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.radiation_matter_feedback import (
    frozen_radiation_material_response,
)

try:
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "36a070257f684cd7bbbf05b9378b317f325886610f0b81d40f9759e630e371ac"
)
MIB = 1024**2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_npz_atomic(path: Path, **arrays: np.ndarray) -> None:
    temporary = path.with_name(f"{path.stem}.tmp.npz")
    np.savez(temporary, **arrays)
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B7b protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B7b source changed: {source['path']}")
    if (
        protocol["sources"]["feedback_coefficients"]["sha256"]
        != protocol["upstream_coefficient_sha256"]
    ):
        raise RuntimeError("Phase 7B7b coefficient digest disagrees with its summary")
    return protocol


def _plot(
    path: Path,
    initial_temperature: np.ndarray,
    updated_temperature: np.ndarray,
    initial_hydrogen: np.ndarray,
    updated_hydrogen: np.ndarray,
    initial_helium: np.ndarray,
    updated_helium: np.ndarray,
    energy_fraction: np.ndarray,
) -> None:
    cell = np.arange(initial_temperature.size)
    relative_temperature = updated_temperature / initial_temperature - 1.0
    population_change = np.maximum.reduce(
        (
            np.max(np.abs(updated_hydrogen - initial_hydrogen), axis=1),
            np.max(np.abs(updated_helium - initial_helium), axis=1),
        )
    )
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].semilogy(cell, initial_temperature, label="Initial material")
    axes[0, 0].semilogy(cell, updated_temperature, ls="--", label="Unaccepted candidate")
    axes[0, 0].set(
        xlabel="Half-column parent cell",
        ylabel="Temperature (K)",
        title="(a) Full-duration frozen-radiation response",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].plot(cell, relative_temperature, color="#e45756")
    axes[0, 1].axhline(0.1, color="0.25", ls="--", label="Positive trust bound")
    axes[0, 1].axhline(-0.1, color="0.25", ls="--")
    axes[0, 1].set(
        xlabel="Half-column parent cell",
        ylabel="Relative temperature change",
        title="(b) Temperature trust-region test",
    )
    axes[0, 1].legend(frameon=False)
    axes[1, 0].semilogy(cell, population_change, color="#72b7b2")
    axes[1, 0].axhline(0.1, color="0.25", ls="--", label="Trust bound")
    axes[1, 0].set(
        xlabel="Half-column parent cell",
        ylabel="Maximum fraction change",
        title="(c) H/He population response",
    )
    axes[1, 0].legend(frameon=False)
    axes[1, 1].plot(cell, energy_fraction, color="#f58518")
    axes[1, 1].axhline(0.1, color="0.25", ls="--", label="Positive trust bound")
    axes[1, 1].axhline(-0.1, color="0.25", ls="--")
    axes[1, 1].set(
        xlabel="Half-column parent cell",
        ylabel="Radiative increment / initial material energy",
        title="(d) Local material-energy forcing",
    )
    axes[1, 1].legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    started = time.perf_counter()
    with np.load(ROOT / protocol["sources"]["feedback_coefficients"]["path"]) as coefficient:
        phase = int(coefficient["phase_index"])
        duration = float(coefficient["step_duration_s"])
        photoionization = np.array(coefficient["half_photoionization_s1"], copy=True)
        recombination = np.array(
            coefficient["half_total_recombination_cm3_s"], copy=True
        )
        heating = np.array(
            coefficient["half_rate_material_heating_erg_s_cm3"], copy=True
        )
    with np.load(ROOT / protocol["sources"]["phase7b4r_material"]["path"]) as material:
        density = np.array(material["density_g_cm3"][phase], copy=True)
        initial_temperature = np.array(material["temperature_k"][phase], copy=True)
        initial_hydrogen = np.array(material["hydrogen_fraction"][phase], copy=True)
        initial_helium = np.array(material["helium_fraction"][phase], copy=True)
    response = frozen_radiation_material_response(
        density,
        initial_temperature,
        initial_hydrogen,
        initial_helium,
        duration,
        photoionization,
        recombination,
        heating,
        bisection_iterations=int(configuration["bisection_iterations"]),
    )
    energy_increment = duration * heating / density
    energy_fraction = energy_increment / response.initial_specific_material_energy_erg_g
    maximum_energy_fraction = float(np.max(np.abs(energy_fraction)))
    nonzero_heating = np.abs(heating) > 0.0
    ten_percent_time = float(
        np.min(
            0.1
            * response.initial_specific_material_energy_erg_g[nonzero_heating]
            * density[nonzero_heating]
            / np.abs(heating[nonzero_heating])
        )
    )
    limiting_cell = int(np.argmax(np.abs(energy_fraction)))
    wall_runtime = time.perf_counter() - started
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    ) / MIB
    gates = protocol["gates"]
    decision = {
        "frozen_protocol_source_and_input_hashes_passed": True,
        "cell_count_and_arrays_valid": bool(
            density.size == gates["cell_count_exactly"]
            and all(
                np.all(np.isfinite(array))
                for array in (
                    response.temperature_k,
                    response.hydrogen_fraction,
                    response.helium_fraction,
                    response.electron_density_cm3,
                )
            )
        ),
        "charge_particle_and_material_energy_closure_passed": bool(
            response.maximum_relative_charge_residual
            < gates["maximum_relative_charge_residual_below"]
            and response.maximum_particle_conservation_residual
            < gates["maximum_particle_conservation_residual_below"]
            and response.maximum_relative_energy_residual
            < gates["maximum_relative_material_energy_residual_below"]
            and response.minimum_population_fraction
            >= gates["minimum_population_fraction_at_least"]
        ),
        "frozen_radiation_trust_region_passed": bool(
            response.maximum_population_fraction_change
            < gates["maximum_population_fraction_change_below"]
            and response.maximum_relative_temperature_change
            < gates["maximum_relative_temperature_change_below"]
            and maximum_energy_fraction
            < gates[
                "maximum_absolute_local_material_energy_increment_fraction_below"
            ]
        ),
        "runtime_gate_passed": wall_runtime < gates["wall_time_strictly_below_s"],
        "fully_coupled_iteration_authorized": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b7b_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_source_and_input_hashes_passed",
            "cell_count_and_arrays_valid",
            "charge_particle_and_material_energy_closure_passed",
            "frozen_radiation_trust_region_passed",
            "runtime_gate_passed",
        )
    )
    decision["radiation_remap_with_updated_matter_authorized"] = bool(
        decision["phase7b7b_gate_passed"]
    )
    decision["timescale_diagnosis_only_authorized"] = bool(
        not decision["frozen_radiation_trust_region_passed"]
        and decision["charge_particle_and_material_energy_closure_passed"]
    )
    candidate_path = OUTPUT / "phase7b7b_unaccepted_material_candidate.npz"
    _write_npz_atomic(
        candidate_path,
        phase_index=np.array(phase),
        step_duration_s=np.array(duration),
        density_g_cm3=density,
        initial_temperature_k=initial_temperature,
        candidate_temperature_k=np.asarray(response.temperature_k),
        initial_hydrogen_fraction=initial_hydrogen,
        candidate_hydrogen_fraction=np.asarray(response.hydrogen_fraction),
        initial_helium_fraction=initial_helium,
        candidate_helium_fraction=np.asarray(response.helium_fraction),
        candidate_electron_density_cm3=np.asarray(response.electron_density_cm3),
        radiative_material_heating_erg_s_cm3=heating,
        local_material_energy_increment_fraction=energy_fraction,
    )
    figure_path = OUTPUT / "phase7b7b_material_response.png"
    _plot(
        figure_path,
        initial_temperature,
        np.asarray(response.temperature_k),
        initial_hydrogen,
        np.asarray(response.hydrogen_fraction),
        initial_helium,
        np.asarray(response.helium_fraction),
        energy_fraction,
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "phase_index": phase,
        "actual_step_duration_s": duration,
        "maximum_relative_temperature_change": (
            response.maximum_relative_temperature_change
        ),
        "maximum_population_fraction_change": (
            response.maximum_population_fraction_change
        ),
        "maximum_absolute_local_material_energy_increment_fraction": (
            maximum_energy_fraction
        ),
        "maximum_relative_charge_residual": (
            response.maximum_relative_charge_residual
        ),
        "maximum_particle_conservation_residual": (
            response.maximum_particle_conservation_residual
        ),
        "maximum_relative_material_energy_residual": (
            response.maximum_relative_energy_residual
        ),
        "minimum_population_fraction": response.minimum_population_fraction,
        "minimum_candidate_temperature_k": float(np.min(response.temperature_k)),
        "maximum_candidate_temperature_k": float(np.max(response.temperature_k)),
        "limiting_half_column_cell": limiting_cell,
        "ten_percent_material_energy_response_time_s": ten_percent_time,
        "candidate_path": str(candidate_path.relative_to(ROOT)),
        "candidate_sha256": _sha256(candidate_path),
        "wall_runtime_s": wall_runtime,
        "peak_process_rss_mib": peak_rss,
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(OUTPUT / "phase7b7b_material_response_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b7b_preregistered_material_response.json",
    )
    args = parser.parse_args()
    summary = run(args.protocol)
    print(json.dumps(summary["decision"], indent=2))


if __name__ == "__main__":
    main()
