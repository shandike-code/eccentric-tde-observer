"""Phase 7B7d：对完整相位物质残差执行一次整态信赖域阻尼。"""

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

from eccentric_tde_observer.material_trust_region import (
    damped_material_picard_step,
)
from eccentric_tde_observer.radiation_matter_feedback import (
    frozen_radiation_material_response,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "3015077d122f7a598400eeb66ba7d29e897f360fcdd93783537142714bd208e4"
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
        raise RuntimeError(f"frozen Phase 7B7d protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B7d source changed: {source['path']}")
    return protocol


def _plot(
    path: Path,
    initial_temperature: np.ndarray,
    full_temperature: np.ndarray,
    damped_temperature: np.ndarray,
    initial_hydrogen: np.ndarray,
    damped_hydrogen: np.ndarray,
    initial_helium: np.ndarray,
    damped_helium: np.ndarray,
    energy_fraction: np.ndarray,
    relaxation: float,
) -> None:
    cell = np.arange(initial_temperature.size)
    temperature_change = damped_temperature / initial_temperature - 1.0
    population_change = np.maximum(
        np.max(np.abs(damped_hydrogen - initial_hydrogen), axis=1),
        np.max(np.abs(damped_helium - initial_helium), axis=1),
    )
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].semilogy(cell, initial_temperature, label="Initial")
    axes[0, 0].semilogy(cell, full_temperature, ls=":", label="Rejected full candidate")
    axes[0, 0].semilogy(cell, damped_temperature, ls="--", label="Damped Picard state")
    axes[0, 0].set(
        xlabel="Half-column parent cell",
        ylabel="Temperature (K)",
        title=f"(a) Solver under-relaxation = {relaxation:.3e}",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].plot(cell, temperature_change, color="#e45756")
    axes[0, 1].axhline(0.05, color="0.25", ls="--", label="Trust boundary")
    axes[0, 1].axhline(-0.05, color="0.25", ls="--")
    axes[0, 1].set(
        xlabel="Half-column parent cell",
        ylabel="Relative temperature change",
        title="(b) Temperature trust region",
    )
    axes[0, 1].legend(frameon=False)
    axes[1, 0].plot(cell, energy_fraction, color="#f58518")
    axes[1, 0].axhline(0.05, color="0.25", ls="--", label="Trust boundary")
    axes[1, 0].axhline(-0.05, color="0.25", ls="--")
    axes[1, 0].set(
        xlabel="Half-column parent cell",
        ylabel="Damped energy increment fraction",
        title="(c) Material-energy residual direction",
    )
    axes[1, 0].legend(frameon=False)
    axes[1, 1].semilogy(cell, population_change, color="#72b7b2")
    axes[1, 1].axhline(0.05, color="0.25", ls="--", label="Trust boundary")
    axes[1, 1].set(
        xlabel="Half-column parent cell",
        ylabel="Maximum population fraction change",
        title="(d) Simplex-preserving population damping",
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
    full_candidate = frozen_radiation_material_response(
        density,
        initial_temperature,
        initial_hydrogen,
        initial_helium,
        duration,
        photoionization,
        recombination,
        heating,
        bisection_iterations=96,
    )
    step = damped_material_picard_step(
        initial_temperature,
        initial_hydrogen,
        initial_helium,
        full_candidate,
        maximum_relative_temperature_change=float(
            configuration["maximum_relative_temperature_change"]
        ),
        maximum_absolute_material_energy_increment_fraction=float(
            configuration["maximum_absolute_material_energy_increment_fraction"]
        ),
        bisection_iterations=int(configuration["bisection_iterations"]),
    )
    full_summary = json.loads(
        (OUTPUT / "phase7b7b_material_response_summary.json").read_text(
            encoding="utf-8"
        )
    )
    full_candidate_reproduced = bool(
        full_candidate.maximum_relative_temperature_change
        == full_summary["maximum_relative_temperature_change"]
        and full_candidate.maximum_population_fraction_change
        == full_summary["maximum_population_fraction_change"]
    )
    initial_energy = np.asarray(
        full_candidate.initial_specific_material_energy_erg_g
    )
    damped_energy_fraction = (
        np.asarray(step.target_specific_material_energy_erg_g) - initial_energy
    ) / initial_energy
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
        "frozen_protocol_source_and_full_candidate_reproduction_passed": bool(
            full_candidate_reproduced
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
        "accepted_as_coupled_fixed_point": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b7d_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_source_and_full_candidate_reproduction_passed",
            "relaxation_and_trust_boundaries_passed",
            "simplex_and_material_energy_gates_passed",
            "runtime_gate_passed",
        )
    )
    decision["one_full_duration_radiation_directional_map_authorized"] = bool(
        decision["phase7b7d_gate_passed"]
    )
    state_path = OUTPUT / "phase7b7d_damped_material_state.npz"
    _write_npz_atomic(
        state_path,
        phase_index=np.array(phase),
        step_duration_s=np.array(duration),
        solver_relaxation=np.array(step.relaxation),
        density_g_cm3=density,
        temperature_k=np.asarray(step.temperature_k),
        hydrogen_fraction=np.asarray(step.hydrogen_fraction),
        helium_fraction=np.asarray(step.helium_fraction),
        target_specific_material_energy_erg_g=np.asarray(
            step.target_specific_material_energy_erg_g
        ),
        damped_material_energy_increment_fraction=damped_energy_fraction,
    )
    figure_path = OUTPUT / "phase7b7d_trust_region_picard.png"
    _plot(
        figure_path,
        initial_temperature,
        np.asarray(full_candidate.temperature_k),
        np.asarray(step.temperature_k),
        initial_hydrogen,
        np.asarray(step.hydrogen_fraction),
        initial_helium,
        np.asarray(step.helium_fraction),
        damped_energy_fraction,
        step.relaxation,
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "phase_index": phase,
        "physical_step_duration_s": duration,
        "physical_step_duration_changed": False,
        "solver_relaxation": step.relaxation,
        "maximum_relative_temperature_change": (
            step.maximum_relative_temperature_change
        ),
        "maximum_absolute_material_energy_increment_fraction": (
            step.maximum_absolute_material_energy_increment_fraction
        ),
        "maximum_population_fraction_change": (
            step.maximum_population_fraction_change
        ),
        "maximum_relative_material_energy_residual": (
            step.maximum_relative_energy_residual
        ),
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
    _write_json_atomic(OUTPUT / "phase7b7d_trust_region_picard_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b7d_preregistered_trust_region_picard.json",
    )
    args = parser.parse_args()
    summary = run(args.protocol)
    print(json.dumps(summary["decision"], indent=2))


if __name__ == "__main__":
    main()
