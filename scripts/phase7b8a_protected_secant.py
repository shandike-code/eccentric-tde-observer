"""Phase 7B8a：两个已验证反馈点的受保护逐单元割线提案。"""

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

from eccentric_tde_observer.coupled_material_acceleration import (
    protected_diagonal_secant_material_step,
)
from eccentric_tde_observer.radiation_matter_feedback import (
    frozen_radiation_material_response,
    ground_state_material_specific_energy_erg_g,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "9a2ad8fb0b5612191998033bfcd273dba4c223a153ae559ce373d5552e967bf2"
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
        raise RuntimeError(f"frozen Phase 7B8a protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B8a source changed: {source['path']}")
    return protocol


def _fixed_point_relative_residual(
    old_energy: np.ndarray,
    state_energy: np.ndarray,
    duration: float,
    heating: np.ndarray,
    density: np.ndarray,
    cell_mass: np.ndarray,
) -> tuple[np.ndarray, float]:
    increment = duration * heating / density
    residual = state_energy - old_energy - increment
    scale = np.maximum.reduce(
        (np.abs(state_energy), np.abs(old_energy), np.abs(increment))
    )
    relative = np.array(np.abs(residual), copy=True)
    np.divide(np.abs(residual), scale, out=relative, where=scale > 0.0)
    weighted = float(np.sum(cell_mass * np.abs(residual))) / float(
        np.sum(cell_mass * scale)
    )
    return relative, weighted


def _plot(
    path: Path,
    mass_centre: np.ndarray,
    old_temperature: np.ndarray,
    previous_temperature: np.ndarray,
    current_temperature: np.ndarray,
    target_temperature: np.ndarray,
    trial_temperature: np.ndarray,
    alpha: np.ndarray,
    current_residual: np.ndarray,
    trial_residual: np.ndarray,
    relaxation: float,
    frozen_contraction: float,
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].semilogy(mass_centre, old_temperature, label="Physical old time level")
    axes[0, 0].semilogy(mass_centre, previous_temperature, label="First iterate")
    axes[0, 0].semilogy(mass_centre, current_temperature, label="Second iterate")
    axes[0, 0].semilogy(
        mass_centre, target_temperature, ls=":", label="Unprotected secant target"
    )
    axes[0, 0].semilogy(
        mass_centre, trial_temperature, ls="--", label="Protected secant trial"
    )
    axes[0, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Temperature (K)",
        title="(a) Accelerated material proposal",
    )
    axes[0, 0].legend(frameon=False, fontsize=9)
    axes[0, 1].plot(mass_centre, alpha)
    axes[0, 1].axhline(0.0, color="0.25", ls="--")
    axes[0, 1].set(
        xlabel="Mass fraction from surface",
        ylabel="Per-cell secant coefficient",
        title="(b) Diagonal secant extrapolation",
    )
    axes[1, 0].semilogy(mass_centre, current_residual, label="Second iterate")
    axes[1, 0].semilogy(
        mass_centre,
        trial_residual,
        ls="--",
        label="Trial with frozen current radiation",
    )
    axes[1, 0].axhline(1.0e-3, color="0.25", ls=":", label="Fixed-point target")
    axes[1, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Cellwise fixed-time-level residual",
        title="(c) Cheap pre-map residual control",
    )
    axes[1, 0].legend(frameon=False)
    axes[1, 1].axis("off")
    axes[1, 1].text(
        0.05,
        0.9,
        "(d) Proposal scope\n\n"
        f"Global trust relaxation = {relaxation:.6f}\n"
        f"Affine-secant predicted contraction = {1.0 - relaxation:.6f}\n"
        f"Frozen-current-radiation contraction = {frozen_contraction:.6f}\n\n"
        "Physical time accumulated again: false\n"
        "New radiation map performed: false\n"
        "Coupled fixed point claimed: false",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=11,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    started = time.perf_counter()
    with np.load(
        ROOT / protocol["sources"]["previous_material_iterate"]["path"]
    ) as previous:
        phase = int(previous["phase_index"])
        duration = float(previous["step_duration_s"])
        density = np.array(previous["density_g_cm3"], copy=True)
        previous_temperature = np.array(previous["temperature_k"], copy=True)
        previous_hydrogen = np.array(previous["hydrogen_fraction"], copy=True)
        previous_helium = np.array(previous["helium_fraction"], copy=True)
    with np.load(
        ROOT / protocol["sources"]["current_material_iterate"]["path"]
    ) as current:
        if (
            int(current["phase_index"]) != phase
            or float(current["step_duration_s"]) != duration
            or not np.array_equal(current["density_g_cm3"], density)
        ):
            raise RuntimeError("Phase 7B8a material iteration time base changed")
        current_temperature = np.array(current["temperature_k"], copy=True)
        current_hydrogen = np.array(current["hydrogen_fraction"], copy=True)
        current_helium = np.array(current["helium_fraction"], copy=True)
    with np.load(
        ROOT / protocol["sources"]["physical_old_time_level"]["path"]
    ) as old:
        old_temperature = np.array(old["temperature_k"][phase], copy=True)
        old_hydrogen = np.array(old["hydrogen_fraction"][phase], copy=True)
        old_helium = np.array(old["helium_fraction"][phase], copy=True)
        old_density = np.array(old["density_g_cm3"][phase], copy=True)
        physical_duration = float(old["step_duration_s"][phase])
        cell_mass = np.array(old["cell_mass_g_cm2"], copy=True)
        mass_edge = np.array(old["mass_fraction_edges"], copy=True)
    if not np.array_equal(density, old_density) or duration != physical_duration:
        raise RuntimeError("Phase 7B8a physical old time level changed")
    with np.load(
        ROOT / protocol["sources"]["previous_assembled_rates"]["path"]
    ) as rates:
        previous_photoionization = np.array(rates["half_photoionization_s1"], copy=True)
        previous_recombination = np.array(
            rates["half_total_recombination_cm3_s"], copy=True
        )
        previous_heating = np.array(
            rates["half_rate_material_heating_erg_s_cm3"], copy=True
        )
    with np.load(
        ROOT / protocol["sources"]["current_assembled_rates"]["path"]
    ) as rates:
        current_photoionization = np.array(rates["half_photoionization_s1"], copy=True)
        current_recombination = np.array(
            rates["half_total_recombination_cm3_s"], copy=True
        )
        current_heating = np.array(
            rates["half_atomic_rate_heating_erg_s_cm3"], copy=True
        )
    previous_candidate = frozen_radiation_material_response(
        density,
        old_temperature,
        old_hydrogen,
        old_helium,
        duration,
        previous_photoionization,
        previous_recombination,
        previous_heating,
        bisection_iterations=int(configuration["bisection_iterations"]),
    )
    current_candidate = frozen_radiation_material_response(
        density,
        old_temperature,
        old_hydrogen,
        old_helium,
        duration,
        current_photoionization,
        current_recombination,
        current_heating,
        bisection_iterations=int(configuration["bisection_iterations"]),
    )
    step = protected_diagonal_secant_material_step(
        previous_temperature,
        previous_hydrogen,
        previous_helium,
        current_temperature,
        current_hydrogen,
        current_helium,
        previous_candidate,
        current_candidate,
        maximum_relative_temperature_change=float(
            configuration["maximum_relative_temperature_change"]
        ),
        maximum_absolute_material_energy_increment_fraction=float(
            configuration["maximum_absolute_material_energy_increment_fraction"]
        ),
        maximum_population_fraction_change=float(
            configuration["maximum_population_fraction_change"]
        ),
        bisection_iterations=int(configuration["bisection_iterations"]),
    )
    old_energy = np.asarray(
        ground_state_material_specific_energy_erg_g(
            old_temperature, old_hydrogen, old_helium
        )
    )
    current_energy = np.asarray(
        ground_state_material_specific_energy_erg_g(
            current_temperature, current_hydrogen, current_helium
        )
    )
    current_residual, current_weighted = _fixed_point_relative_residual(
        old_energy,
        current_energy,
        duration,
        current_heating,
        density,
        cell_mass,
    )
    trial_residual, trial_weighted = _fixed_point_relative_residual(
        old_energy,
        np.asarray(step.specific_material_energy_erg_g),
        duration,
        current_heating,
        density,
        cell_mass,
    )
    frozen_contraction = trial_weighted / current_weighted
    target_particle_residual = max(
        float(
            np.max(
                np.abs(np.sum(step.secant_target_hydrogen_fraction, axis=1) - 1.0)
            )
        ),
        float(
            np.max(
                np.abs(np.sum(step.secant_target_helium_fraction, axis=1) - 1.0)
            )
        ),
    )
    temperature_limit = float(configuration["maximum_relative_temperature_change"])
    energy_limit = float(
        configuration["maximum_absolute_material_energy_increment_fraction"]
    )
    population_limit = float(configuration["maximum_population_fraction_change"])
    utilization = max(
        step.maximum_relative_temperature_change / temperature_limit,
        step.maximum_absolute_material_energy_increment_fraction / energy_limit,
        step.maximum_population_fraction_change / population_limit,
    )
    wall_runtime = time.perf_counter() - started
    gates = protocol["gates"]
    decision = {
        "frozen_protocol_sources_and_time_base_passed": True,
        "secant_target_domain_and_identity_passed": bool(
            current_temperature.size == gates["cell_count_exactly"]
            and float(np.max(np.abs(step.secant_alpha)))
            < gates["maximum_absolute_secant_alpha_below"]
            and min(
                float(np.min(step.secant_target_hydrogen_fraction)),
                float(np.min(step.secant_target_helium_fraction)),
            )
            >= gates["minimum_secant_target_population_at_least"]
            and target_particle_residual
            < gates["maximum_secant_target_particle_residual_below"]
            and step.maximum_secant_identity_relative_residual
            < gates["maximum_secant_identity_relative_residual_below"]
        ),
        "global_trust_and_material_conservation_passed": bool(
            step.relaxation > gates["relaxation_strictly_above"]
            and step.relaxation <= gates["relaxation_at_most"]
            and step.maximum_relative_temperature_change
            <= gates["maximum_relative_temperature_change_at_most"]
            and step.maximum_absolute_material_energy_increment_fraction
            <= gates[
                "maximum_absolute_material_energy_increment_fraction_at_most"
            ]
            and step.maximum_population_fraction_change
            <= gates["maximum_population_fraction_change_at_most"]
            and utilization >= gates["maximum_trust_boundary_utilization_at_least"]
            and step.maximum_relative_energy_residual
            < gates["maximum_relative_energy_residual_below"]
            and step.maximum_particle_conservation_residual
            < gates["maximum_particle_conservation_residual_below"]
            and step.minimum_population_fraction
            >= gates["minimum_population_fraction_at_least"]
        ),
        "cheap_residual_direction_passed": bool(
            step.affine_secant_predicted_residual_contraction
            < gates["affine_secant_predicted_residual_contraction_below"]
            and frozen_contraction
            < gates["frozen_current_radiation_residual_contraction_below"]
        ),
        "runtime_gate_passed": wall_runtime < gates["wall_time_strictly_below_s"],
        "physical_step_duration_changed": False,
        "physical_step_accumulated_again": False,
        "radiation_validation_map_performed": False,
        "accepted_as_coupled_fixed_point": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b8a_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_sources_and_time_base_passed",
            "secant_target_domain_and_identity_passed",
            "global_trust_and_material_conservation_passed",
            "cheap_residual_direction_passed",
            "runtime_gate_passed",
        )
    )
    decision["one_full_frequency_radiation_validation_map_authorized"] = bool(
        decision["phase7b8a_gate_passed"]
    )
    state_path = OUTPUT / "phase7b8a_protected_secant_material_trial.npz"
    _write_npz_atomic(
        state_path,
        phase_index=np.array(phase),
        nonlinear_iteration_index=np.array(3),
        step_duration_s=np.array(duration),
        physical_step_duration_changed=np.array(False),
        physical_step_accumulated_again=np.array(False),
        solver_method=np.array("protected diagonal secant"),
        solver_relaxation=np.array(step.relaxation),
        density_g_cm3=density,
        temperature_k=np.asarray(step.temperature_k),
        hydrogen_fraction=np.asarray(step.hydrogen_fraction),
        helium_fraction=np.asarray(step.helium_fraction),
        specific_material_energy_erg_g=np.asarray(
            step.specific_material_energy_erg_g
        ),
        secant_alpha=np.asarray(step.secant_alpha),
        secant_target_temperature_k=np.asarray(step.secant_target_temperature_k),
        secant_target_hydrogen_fraction=np.asarray(
            step.secant_target_hydrogen_fraction
        ),
        secant_target_helium_fraction=np.asarray(step.secant_target_helium_fraction),
        secant_target_specific_material_energy_erg_g=np.asarray(
            step.secant_target_specific_material_energy_erg_g
        ),
        frozen_current_radiation_relative_residual=trial_residual,
    )
    figure_path = OUTPUT / "phase7b8a_protected_secant.png"
    _plot(
        figure_path,
        0.5 * (mass_edge[:-1] + mass_edge[1:]),
        old_temperature,
        previous_temperature,
        current_temperature,
        np.asarray(step.secant_target_temperature_k),
        np.asarray(step.temperature_k),
        np.asarray(step.secant_alpha),
        current_residual,
        trial_residual,
        step.relaxation,
        frozen_contraction,
    )
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "phase_index": phase,
        "physical_step_duration_s": duration,
        "physical_step_duration_changed": False,
        "physical_step_accumulated_again": False,
        "minimum_secant_alpha": float(np.min(step.secant_alpha)),
        "maximum_secant_alpha": float(np.max(step.secant_alpha)),
        "maximum_absolute_secant_alpha": float(np.max(np.abs(step.secant_alpha))),
        "solver_relaxation": step.relaxation,
        "maximum_relative_temperature_change": step.maximum_relative_temperature_change,
        "maximum_absolute_material_energy_increment_fraction": (
            step.maximum_absolute_material_energy_increment_fraction
        ),
        "maximum_population_fraction_change": step.maximum_population_fraction_change,
        "maximum_relative_material_energy_residual": (
            step.maximum_relative_energy_residual
        ),
        "maximum_particle_conservation_residual": (
            step.maximum_particle_conservation_residual
        ),
        "minimum_population_fraction": step.minimum_population_fraction,
        "maximum_secant_identity_relative_residual": (
            step.maximum_secant_identity_relative_residual
        ),
        "maximum_trust_boundary_utilization": utilization,
        "affine_secant_predicted_residual_contraction": (
            step.affine_secant_predicted_residual_contraction
        ),
        "current_mass_weighted_fixed_point_residual": current_weighted,
        "frozen_current_radiation_trial_mass_weighted_residual": trial_weighted,
        "frozen_current_radiation_residual_contraction": frozen_contraction,
        "wall_runtime_s": wall_runtime,
        "state_path": str(state_path.relative_to(ROOT)),
        "state_sha256": _sha256(state_path),
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(OUTPUT / "phase7b8a_protected_secant_summary.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b8a_preregistered_protected_secant.json",
    )
    args = parser.parse_args()
    print(json.dumps(run(args.protocol), indent=2))


if __name__ == "__main__":
    main()
