"""Phase 7B7h：从当前迭代态走向固定物理时间层的第二个完整候选。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.coupled_material_iteration import (
    damped_coupled_material_iteration,
)
from eccentric_tde_observer.radiation_matter_feedback import (
    frozen_radiation_material_response,
    ground_state_material_specific_energy_erg_g,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "8c47eaa33e1016a3479f5b564e61464a70b83e7799816d5d488ddf114a11cad9"
)


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
        raise RuntimeError(f"frozen Phase 7B7h protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B7h source changed: {source['path']}")
    return protocol


def _relative_residual(value: np.ndarray, reference: np.ndarray) -> float:
    difference = np.abs(value - reference)
    scale = np.maximum(np.abs(value), np.abs(reference))
    residual = np.array(difference, copy=True)
    np.divide(difference, scale, out=residual, where=scale > 0.0)
    return float(np.max(residual))


def _plot(
    path: Path,
    old_temperature: np.ndarray,
    current_temperature: np.ndarray,
    candidate_temperature: np.ndarray,
    updated_temperature: np.ndarray,
    current_energy: np.ndarray,
    candidate_energy: np.ndarray,
    updated_energy: np.ndarray,
    temperature_limit: float,
    energy_limit: float,
    relaxation: float,
    old_base_residual: float,
    target_residual: float,
) -> None:
    cell = np.arange(old_temperature.size)
    temperature_change = updated_temperature / current_temperature - 1.0
    full_energy_direction = candidate_energy / current_energy - 1.0
    updated_energy_direction = updated_energy / current_energy - 1.0
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].semilogy(cell, old_temperature, label="Physical old time level")
    axes[0, 0].semilogy(cell, current_temperature, label="Current nonlinear iterate")
    axes[0, 0].semilogy(
        cell, candidate_temperature, ls=":", label="New full Picard candidate"
    )
    axes[0, 0].semilogy(
        cell, updated_temperature, ls="--", label="Second damped iterate"
    )
    axes[0, 0].set(
        xlabel="Half-column parent cell",
        ylabel="Temperature (K)",
        title=f"(a) Solver relaxation = {relaxation:.3e}",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].plot(cell, temperature_change, color="#e45756")
    axes[0, 1].axhline(temperature_limit, color="0.25", ls="--", label="Trust boundary")
    axes[0, 1].axhline(-temperature_limit, color="0.25", ls="--")
    axes[0, 1].set(
        xlabel="Half-column parent cell",
        ylabel="Relative change from current iterate",
        title="(b) Temperature trust region",
    )
    axes[0, 1].legend(frameon=False)
    axes[1, 0].plot(cell, full_energy_direction, label="Full candidate direction")
    axes[1, 0].plot(
        cell, updated_energy_direction, ls="--", label="Accepted damped direction"
    )
    axes[1, 0].axhline(energy_limit, color="0.25", ls=":", label="Energy trust boundary")
    axes[1, 0].axhline(-energy_limit, color="0.25", ls=":")
    axes[1, 0].set_yscale("symlog", linthresh=0.01)
    axes[1, 0].set(
        xlabel="Half-column parent cell",
        ylabel="Material-energy direction / current energy",
        title="(c) Fixed-time-level Picard direction",
    )
    axes[1, 0].legend(frameon=False)
    axes[1, 1].axis("off")
    axes[1, 1].text(
        0.05,
        0.88,
        "(d) Time-base validation\n\n"
        f"Old-energy base residual = {old_base_residual:.3e}\n"
        f"Old + dt Q/rho target residual = {target_residual:.3e}\n"
        "Physical step duration changed = false\n"
        "Physical step accumulated again = false",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=12,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    started = time.perf_counter()
    with np.load(ROOT / protocol["sources"]["phase7b7g_rates"]["path"]) as rates:
        photoionization = np.array(rates["half_photoionization_s1"], copy=True)
        recombination = np.array(
            rates["half_total_recombination_cm3_s"], copy=True
        )
        heating = np.array(
            rates["half_rate_material_heating_erg_s_cm3"], copy=True
        )
    with np.load(
        ROOT / protocol["sources"]["current_material_iterate"]["path"]
    ) as current:
        phase = int(current["phase_index"])
        duration = float(current["step_duration_s"])
        density = np.array(current["density_g_cm3"], copy=True)
        current_temperature = np.array(current["temperature_k"], copy=True)
        current_hydrogen = np.array(current["hydrogen_fraction"], copy=True)
        current_helium = np.array(current["helium_fraction"], copy=True)
    with np.load(
        ROOT / protocol["sources"]["physical_old_time_level"]["path"]
    ) as material:
        old_temperature = np.array(material["temperature_k"][phase], copy=True)
        old_hydrogen = np.array(material["hydrogen_fraction"][phase], copy=True)
        old_helium = np.array(material["helium_fraction"][phase], copy=True)
        old_density = np.array(material["density_g_cm3"][phase], copy=True)
        physical_duration = float(material["step_duration_s"][phase])
    if not np.array_equal(density, old_density) or duration != physical_duration:
        raise RuntimeError("Phase 7B7h physical old time base changed")
    candidate = frozen_radiation_material_response(
        density,
        old_temperature,
        old_hydrogen,
        old_helium,
        duration,
        photoionization,
        recombination,
        heating,
        bisection_iterations=int(configuration["bisection_iterations"]),
    )
    step = damped_coupled_material_iteration(
        current_temperature,
        current_hydrogen,
        current_helium,
        candidate,
        maximum_relative_temperature_change=float(
            configuration["maximum_relative_temperature_change"]
        ),
        maximum_absolute_material_energy_increment_fraction=float(
            configuration[
                "maximum_absolute_material_energy_increment_fraction"
            ]
        ),
        bisection_iterations=int(configuration["bisection_iterations"]),
    )
    old_energy = np.asarray(
        ground_state_material_specific_energy_erg_g(
            old_temperature, old_hydrogen, old_helium
        )
    )
    expected_target = old_energy + duration * heating / density
    old_base_residual = _relative_residual(
        np.asarray(candidate.initial_specific_material_energy_erg_g), old_energy
    )
    target_residual = _relative_residual(
        np.asarray(candidate.target_specific_material_energy_erg_g),
        expected_target,
    )
    temperature_limit = float(configuration["maximum_relative_temperature_change"])
    energy_limit = float(
        configuration["maximum_absolute_material_energy_increment_fraction"]
    )
    utilization = max(
        step.maximum_relative_temperature_change / temperature_limit,
        step.maximum_absolute_material_energy_increment_fraction / energy_limit,
    )
    wall_runtime = time.perf_counter() - started
    gates = protocol["gates"]
    decision = {
        "frozen_protocol_sources_and_rates_passed": True,
        "physical_old_time_level_base_passed": bool(
            old_base_residual
            < gates["physical_old_energy_base_relative_residual_below"]
            and target_residual
            < gates["fixed_time_level_target_energy_relative_residual_below"]
        ),
        "relaxation_and_trust_boundaries_passed": bool(
            step.relaxation > gates["relaxation_strictly_above"]
            and step.relaxation <= gates["relaxation_at_most"]
            and step.maximum_relative_temperature_change
            <= gates["maximum_relative_temperature_change_at_most"]
            and step.maximum_absolute_material_energy_increment_fraction
            <= gates[
                "maximum_absolute_material_energy_increment_fraction_at_most"
            ]
            and utilization
            >= gates["maximum_trust_boundary_utilization_at_least"]
        ),
        "simplex_and_material_energy_gates_passed": bool(
            step.maximum_population_fraction_change
            <= gates["maximum_population_fraction_change_at_most"]
            and step.maximum_relative_energy_residual
            < gates["maximum_relative_energy_residual_below"]
            and step.maximum_particle_conservation_residual
            < gates["maximum_particle_conservation_residual_below"]
            and step.minimum_population_fraction
            >= gates["minimum_population_fraction_at_least"]
        ),
        "runtime_gate_passed": wall_runtime < gates["wall_time_strictly_below_s"],
        "physical_step_duration_changed": False,
        "physical_step_accumulated_again": False,
        "accepted_as_coupled_fixed_point": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b7h_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_sources_and_rates_passed",
            "physical_old_time_level_base_passed",
            "relaxation_and_trust_boundaries_passed",
            "simplex_and_material_energy_gates_passed",
            "runtime_gate_passed",
        )
    )
    decision["one_full_frequency_radiation_directional_map_authorized"] = bool(
        decision["phase7b7h_gate_passed"]
    )
    state_path = OUTPUT / "phase7b7h_second_material_iterate.npz"
    _write_npz_atomic(
        state_path,
        phase_index=np.array(phase),
        nonlinear_iteration_index=np.array(2),
        step_duration_s=np.array(duration),
        physical_step_duration_changed=np.array(False),
        physical_step_accumulated_again=np.array(False),
        solver_relaxation=np.array(step.relaxation),
        density_g_cm3=density,
        temperature_k=np.asarray(step.temperature_k),
        hydrogen_fraction=np.asarray(step.hydrogen_fraction),
        helium_fraction=np.asarray(step.helium_fraction),
        current_specific_material_energy_erg_g=np.asarray(
            step.current_specific_material_energy_erg_g
        ),
        candidate_specific_material_energy_erg_g=np.asarray(
            step.candidate_specific_material_energy_erg_g
        ),
        updated_specific_material_energy_erg_g=np.asarray(
            step.updated_specific_material_energy_erg_g
        ),
    )
    figure_path = OUTPUT / "phase7b7h_second_picard_direction.png"
    _plot(
        figure_path,
        old_temperature,
        current_temperature,
        np.asarray(candidate.temperature_k),
        np.asarray(step.temperature_k),
        np.asarray(step.current_specific_material_energy_erg_g),
        np.asarray(step.candidate_specific_material_energy_erg_g),
        np.asarray(step.updated_specific_material_energy_erg_g),
        temperature_limit,
        energy_limit,
        step.relaxation,
        old_base_residual,
        target_residual,
    )
    report = {
        "phase": "7B7h second fixed-time-level material Picard direction",
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": _sha256(protocol_path),
        "phase_index": phase,
        "physical_step_duration_s": duration,
        "physical_step_duration_changed": False,
        "physical_step_accumulated_again": False,
        "solver_relaxation": step.relaxation,
        "physical_old_energy_base_relative_residual": old_base_residual,
        "fixed_time_level_target_energy_relative_residual": target_residual,
        "maximum_relative_temperature_change": step.maximum_relative_temperature_change,
        "maximum_absolute_material_energy_increment_fraction": (
            step.maximum_absolute_material_energy_increment_fraction
        ),
        "maximum_population_fraction_change": step.maximum_population_fraction_change,
        "maximum_relative_material_energy_residual": step.maximum_relative_energy_residual,
        "maximum_particle_conservation_residual": (
            step.maximum_particle_conservation_residual
        ),
        "minimum_population_fraction": step.minimum_population_fraction,
        "maximum_trust_boundary_utilization": utilization,
        "state_path": str(state_path.relative_to(ROOT)),
        "state_sha256": _sha256(state_path),
        "wall_runtime_s": wall_runtime,
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b7h_second_picard_direction_summary.json", report
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b7h_preregistered_second_picard_direction.json",
    )
    args = parser.parse_args()
    print(json.dumps(run(args.protocol), indent=2))


if __name__ == "__main__":
    main()
