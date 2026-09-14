"""生成 Phase 7B4a H/He 碰撞动力学与固定背景松弛证据。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eccentric_tde_observer.atomic_continuum import (
    HE_I_RECOMBINATION_FIT,
    HE_II_RECOMBINATION_FIT,
    H_I_RECOMBINATION_FIT,
    ground_state_saha_factor_cm3,
)
from eccentric_tde_observer.atomic_kinetics import (
    H_HE_COLLISIONAL_IONIZATION_FITS,
    HE_II_VORONOV_FIT,
    collisional_photoionization_equilibrium,
    detailed_balance_three_body_recombination_coefficient_cm6_s,
    h_he_rate_generators_s1,
    solve_constant_rate_network,
)
from eccentric_tde_observer.atmosphere import SOLAR_FULLY_IONIZED_H_HE
from eccentric_tde_observer.dynamic_column import build_zo_periodic_column_background
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model


IONIZATION_ENERGIES_EV = (13.59843449, 24.587389, 54.417765)
BISECTION_ITERATIONS = (8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52)
PHASE_GRID_POINTS = (256, 512, 1024)
PHASE_REFERENCE_POINTS = 2048


def _write_csv(path: Path, records: list[dict[str, object]]) -> None:
    if not records:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def _atomic_coefficients(temperature_k):
    collision = tuple(
        fit.coefficient_cm3_s(temperature_k)
        for fit in H_HE_COLLISIONAL_IONIZATION_FITS
    )
    saha = tuple(
        ground_state_saha_factor_cm3(temperature_k, energy)
        for energy in IONIZATION_ENERGIES_EV
    )
    three_body = tuple(
        detailed_balance_three_body_recombination_coefficient_cm6_s(rate, factor)
        for rate, factor in zip(collision, saha, strict=True)
    )
    return collision, saha, three_body


def _radiative_recombination_coefficients(temperature_k):
    return (
        H_I_RECOMBINATION_FIT.coefficient_cm3_s(temperature_k),
        HE_I_RECOMBINATION_FIT.coefficient_cm3_s(temperature_k),
        HE_II_RECOMBINATION_FIT.coefficient_cm3_s(temperature_k),
    )


def _rate_table():
    temperature = np.geomspace(
        HE_II_VORONOV_FIT.minimum_temperature_k,
        HE_II_VORONOV_FIT.maximum_temperature_k,
        601,
    )
    collision, saha, three_body = _atomic_coefficients(temperature)
    records = []
    for index, value in enumerate(temperature):
        records.append(
            {
                "temperature_k": float(value),
                "h_i_collisional_ionization_cm3_s": float(collision[0][index]),
                "he_i_collisional_ionization_cm3_s": float(collision[1][index]),
                "he_ii_collisional_ionization_cm3_s": float(collision[2][index]),
                "h_i_detailed_balance_three_body_cm6_s": float(three_body[0][index]),
                "he_i_detailed_balance_three_body_cm6_s": float(three_body[1][index]),
                "he_ii_detailed_balance_three_body_cm6_s": float(three_body[2][index]),
            }
        )
    values = {
        "temperature_k": temperature,
        "collision": collision,
        "saha": saha,
        "three_body": three_body,
    }
    return records, values


def _density_equilibrium_control():
    temperature = 1.0e5
    hydrogen = np.geomspace(1.0e8, 1.0e30, 161)
    helium = 0.1 * hydrogen
    collision, saha, three_body = _atomic_coefficients(temperature)
    radiative = _radiative_recombination_coefficients(temperature)
    saha_state = collisional_photoionization_equilibrium(
        hydrogen,
        helium,
        0.0,
        0.0,
        0.0,
        *collision,
        0.0,
        0.0,
        0.0,
        *three_body,
    )
    physical_state = collisional_photoionization_equilibrium(
        hydrogen,
        helium,
        0.0,
        0.0,
        0.0,
        *collision,
        *radiative,
        *three_body,
    )
    fraction_fields = (
        "hydrogen_neutral_fraction",
        "hydrogen_ionized_fraction",
        "helium_neutral_fraction",
        "helium_singly_ionized_fraction",
        "helium_doubly_ionized_fraction",
    )
    maximum_fraction_difference = np.max(
        np.stack(
            [
                np.abs(getattr(physical_state, field) - getattr(saha_state, field))
                for field in fraction_fields
            ]
        ),
        axis=0,
    )
    electron_difference = np.abs(
        physical_state.electron_density_cm3 / saha_state.electron_density_cm3 - 1.0
    )
    saha_ratio_errors = (
        np.abs(
            saha_state.electron_density_cm3
            * saha_state.hydrogen_ionized_fraction
            / saha_state.hydrogen_neutral_fraction
            / saha[0]
            - 1.0
        ),
        np.abs(
            saha_state.electron_density_cm3
            * saha_state.helium_singly_ionized_fraction
            / saha_state.helium_neutral_fraction
            / saha[1]
            - 1.0
        ),
        np.abs(
            saha_state.electron_density_cm3
            * saha_state.helium_doubly_ionized_fraction
            / saha_state.helium_singly_ionized_fraction
            / saha[2]
            - 1.0
        ),
    )
    records = []
    for index, density in enumerate(hydrogen):
        records.append(
            {
                "hydrogen_nuclei_cm3": float(density),
                "helium_nuclei_cm3": float(helium[index]),
                "electron_density_cm3": float(physical_state.electron_density_cm3[index]),
                "h_i_fraction": float(physical_state.hydrogen_neutral_fraction[index]),
                "h_ii_fraction": float(physical_state.hydrogen_ionized_fraction[index]),
                "he_i_fraction": float(physical_state.helium_neutral_fraction[index]),
                "he_ii_fraction": float(
                    physical_state.helium_singly_ionized_fraction[index]
                ),
                "he_iii_fraction": float(
                    physical_state.helium_doubly_ionized_fraction[index]
                ),
                "maximum_fraction_difference_from_collision_three_body_saha": float(
                    maximum_fraction_difference[index]
                ),
                "electron_density_relative_difference_from_saha": float(
                    electron_difference[index]
                ),
            }
        )
    detailed_balance_error = max(
        abs(float(rate / (inverse * factor) - 1.0))
        for rate, inverse, factor in zip(collision, three_body, saha, strict=True)
    )
    summary = {
        "classification": "[L/A-control/V] collision, RR and detailed-balance three-body equilibrium",
        "temperature_k": temperature,
        "helium_to_hydrogen_nuclei_ratio": 0.1,
        "radiative_recombination_coefficients_cm3_s": {
            fit.ion_label: float(value)
            for fit, value in zip(
                H_HE_COLLISIONAL_IONIZATION_FITS, radiative, strict=True
            )
        },
        "radiative_three_body_crossover_electron_density_cm3": {
            fit.ion_label: float(alpha / beta)
            for fit, alpha, beta in zip(
                H_HE_COLLISIONAL_IONIZATION_FITS,
                radiative,
                three_body,
                strict=True,
            )
        },
        "maximum_detailed_balance_relative_error": detailed_balance_error,
        "maximum_saha_ratio_relative_error": float(
            max(np.max(error) for error in saha_ratio_errors)
        ),
        "maximum_relative_charge_residual": physical_state.maximum_relative_charge_residual,
        "maximum_fraction_difference_at_lowest_density": float(
            maximum_fraction_difference[0]
        ),
        "maximum_fraction_difference_at_highest_density": float(
            maximum_fraction_difference[-1]
        ),
    }
    values = {
        "hydrogen_nuclei_cm3": hydrogen,
        "physical_state": physical_state,
        "saha_state": saha_state,
        "maximum_fraction_difference": maximum_fraction_difference,
        "electron_difference": electron_difference,
    }
    return records, summary, values


def _slow_helium_relaxation_time_s(rate_matrices: np.ndarray) -> np.ndarray:
    matrices = np.asarray(rate_matrices, dtype=np.float64)
    flat = matrices.reshape((-1, 3, 3))
    result = np.empty(flat.shape[0], dtype=np.float64)
    for index, matrix in enumerate(flat):
        decay_rates = np.sort(np.abs(np.linalg.eigvals(matrix)))
        slow_rate = float(np.real(decay_rates[1]))
        if not np.isfinite(slow_rate) or slow_rate <= 0.0:
            raise ArithmeticError("helium rate matrix has no positive relaxation rate")
        result[index] = 1.0 / slow_rate
    return result.reshape(matrices.shape[:-2])


def _fixed_relaxation_control():
    temperature = 1.0e5
    hydrogen = 1.0e12
    helium = 1.0e11
    collision, _, three_body = _atomic_coefficients(temperature)
    radiative = _radiative_recombination_coefficients(temperature)
    equilibrium = collisional_photoionization_equilibrium(
        hydrogen,
        helium,
        0.0,
        0.0,
        0.0,
        *collision,
        *radiative,
        *three_body,
    )
    generators = h_he_rate_generators_s1(
        equilibrium.electron_density_cm3,
        0.0,
        0.0,
        0.0,
        *collision,
        *radiative,
        *three_body,
    )
    slow_time = float(_slow_helium_relaxation_time_s(generators.helium_s1))
    time = np.linspace(0.0, 10.0 * slow_time, 301)
    hydrogen_solution = solve_constant_rate_network(
        generators.hydrogen_s1, time, np.array([1.0, 0.0])
    )
    helium_solution = solve_constant_rate_network(
        generators.helium_s1, time, np.array([1.0, 0.0, 0.0])
    )
    target_h = np.array(
        [equilibrium.hydrogen_neutral_fraction, equilibrium.hydrogen_ionized_fraction],
        dtype=np.float64,
    )
    target_he = np.array(
        [
            equilibrium.helium_neutral_fraction,
            equilibrium.helium_singly_ionized_fraction,
            equilibrium.helium_doubly_ionized_fraction,
        ],
        dtype=np.float64,
    )
    upward_h = float(generators.hydrogen_s1[1, 0])
    downward_h = float(generators.hydrogen_s1[0, 1])
    analytic_h_ionized = target_h[1] * (
        1.0 - np.exp(-(upward_h + downward_h) * time)
    )
    records = []
    for index, elapsed in enumerate(time):
        records.append(
            {
                "time_s": float(elapsed),
                "time_over_slowest_helium_relaxation": float(elapsed / slow_time),
                "h_i_fraction": float(hydrogen_solution.population[index, 0]),
                "h_ii_fraction": float(hydrogen_solution.population[index, 1]),
                "he_i_fraction": float(helium_solution.population[index, 0]),
                "he_ii_fraction": float(helium_solution.population[index, 1]),
                "he_iii_fraction": float(helium_solution.population[index, 2]),
            }
        )
    summary = {
        "classification": "[A-control/V] fixed-electron-density matrix-exponential relaxation",
        "temperature_k": temperature,
        "hydrogen_nuclei_cm3": hydrogen,
        "helium_nuclei_cm3": helium,
        "fixed_electron_density_cm3": float(equilibrium.electron_density_cm3),
        "slowest_helium_relaxation_time_s": slow_time,
        "hydrogen_analytic_maximum_absolute_error": float(
            np.max(np.abs(hydrogen_solution.population[:, 1] - analytic_h_ionized))
        ),
        "hydrogen_final_maximum_absolute_equilibrium_error": float(
            np.max(np.abs(hydrogen_solution.population[-1] - target_h))
        ),
        "helium_final_maximum_absolute_equilibrium_error": float(
            np.max(np.abs(helium_solution.population[-1] - target_he))
        ),
        "maximum_particle_conservation_residual": max(
            hydrogen_solution.maximum_particle_conservation_residual,
            helium_solution.maximum_particle_conservation_residual,
        ),
        "minimum_population": min(
            hydrogen_solution.minimum_population, helium_solution.minimum_population
        ),
        "warning": "electron density is held at its final equilibrium value during the transient",
    }
    values = {
        "time_over_slow": time / slow_time,
        "hydrogen": hydrogen_solution.population,
        "helium": helium_solution.population,
    }
    return records, summary, values


def _zo_midplane_timescales(anomaly_points: int):
    model = build_strict_domain_reference_model(65, int(anomaly_points))
    radial_index = 8
    background = build_zo_periodic_column_background(model, radial_index)
    profile = background.vertical_profile
    density = (
        background.surface_density_g_cm2
        / background.scale_height_cm
        * profile.density_shape(np.asarray(0.0))
    )
    gray_midplane_depth = 0.5 * model.parameters.opacity_cm2_g * background.surface_density_g_cm2
    temperature = background.effective_temperature_k * (
        0.75 * (gray_midplane_depth + 2.0 / 3.0)
    ) ** 0.25
    lte = lte_hydrogen_helium_ionization(
        density, temperature, SOLAR_FULLY_IONIZED_H_HE
    )
    collision, _, three_body = _atomic_coefficients(temperature)
    radiative = _radiative_recombination_coefficients(temperature)
    generators = h_he_rate_generators_s1(
        lte.electron_density_cm3,
        0.0,
        0.0,
        0.0,
        *collision,
        *radiative,
        *three_body,
    )
    hydrogen_decay_rate = -np.trace(
        generators.hydrogen_s1, axis1=-2, axis2=-1
    )
    if np.any(hydrogen_decay_rate <= 0.0):
        raise ArithmeticError("hydrogen rate matrix has no positive relaxation rate")
    hydrogen_time = 1.0 / hydrogen_decay_rate
    helium_time = _slow_helium_relaxation_time_s(generators.helium_s1)
    phase = background.time_since_pericentre_s / background.orbital_period_s
    return {
        "phase": phase,
        "eccentric_anomaly_rad": background.eccentric_anomaly_rad,
        "density_g_cm3": density,
        "temperature_k": temperature,
        "electron_density_cm3": lte.electron_density_cm3,
        "hydrogen_relaxation_time_s": hydrogen_time,
        "helium_relaxation_time_s": helium_time,
        "orbital_period_s": background.orbital_period_s,
        "radial_index": radial_index,
    }


def _zo_timescale_records(values):
    records = []
    period = values["orbital_period_s"]
    for index, phase in enumerate(values["phase"]):
        records.append(
            {
                "orbital_phase_t_over_p": float(phase),
                "eccentric_anomaly_rad": float(values["eccentric_anomaly_rad"][index]),
                "midplane_density_g_cm3": float(values["density_g_cm3"][index]),
                "gray_eddington_midplane_temperature_k": float(
                    values["temperature_k"][index]
                ),
                "lte_electron_density_cm3": float(
                    values["electron_density_cm3"][index]
                ),
                "hydrogen_relaxation_time_s": float(
                    values["hydrogen_relaxation_time_s"][index]
                ),
                "helium_slowest_relaxation_time_s": float(
                    values["helium_relaxation_time_s"][index]
                ),
                "hydrogen_relaxation_over_orbital_period": float(
                    values["hydrogen_relaxation_time_s"][index] / period
                ),
                "helium_relaxation_over_orbital_period": float(
                    values["helium_relaxation_time_s"][index] / period
                ),
            }
        )
    return records


def _convergence_controls():
    records = []
    temperature = 1.0e5
    collision, _, three_body = _atomic_coefficients(temperature)
    radiative = _radiative_recombination_coefficients(temperature)
    reference = collisional_photoionization_equilibrium(
        1.0e18,
        1.0e17,
        0.0,
        0.0,
        0.0,
        *collision,
        *radiative,
        *three_body,
        bisection_iterations=128,
    )
    for iterations in BISECTION_ITERATIONS:
        state = collisional_photoionization_equilibrium(
            1.0e18,
            1.0e17,
            0.0,
            0.0,
            0.0,
            *collision,
            *radiative,
            *three_body,
            bisection_iterations=iterations,
        )
        records.append(
            {
                "control": "charge_neutrality_bisection",
                "grid_points_or_iterations": iterations,
                "observable": "electron_density_relative_error",
                "error": abs(
                    float(
                        state.electron_density_cm3
                        / reference.electron_density_cm3
                        - 1.0
                    )
                ),
            }
        )

    phase_reference = _zo_midplane_timescales(PHASE_REFERENCE_POINTS)
    for points in PHASE_GRID_POINTS:
        values = _zo_midplane_timescales(points)
        for species, field in (
            ("H", "hydrogen_relaxation_time_s"),
            ("He", "helium_relaxation_time_s"),
        ):
            interpolated = np.interp(
                phase_reference["phase"],
                values["phase"],
                np.log10(values[field]),
                period=1.0,
            )
            reference_log = np.log10(phase_reference[field])
            error_dex = float(
                np.linalg.norm(interpolated - reference_log)
                / np.sqrt(reference_log.size)
            )
            records.append(
                {
                    "control": "zo_source_phase_grid",
                    "grid_points_or_iterations": points,
                    "observable": f"{species}_log10_timescale_l2_error_dex",
                    "error": error_dex,
                }
            )
    return records


def _plot_controls(path, rates, density, relaxation, zo):
    figure, axes = plt.subplots(2, 3, figsize=(15.2, 8.8), constrained_layout=True)
    labels = ("H I", "He I", "He II")
    for label, coefficient in zip(labels, rates["collision"], strict=True):
        axes[0, 0].loglog(rates["temperature_k"], coefficient, label=label)
    axes[0, 0].set(
        xlabel="Electron temperature (K)",
        ylabel=r"Collisional ionization coefficient (cm$^3$ s$^{-1}$)",
        title="(a) Voronov collisional ionization fits",
    )
    axes[0, 0].legend()

    for label, coefficient in zip(labels, rates["three_body"], strict=True):
        axes[0, 1].loglog(rates["temperature_k"], coefficient, label=label)
    axes[0, 1].set(
        xlabel="Electron temperature (K)",
        ylabel=r"Detailed-balance coefficient (cm$^6$ s$^{-1}$)",
        title="(b) Constructed three-body inverse rates",
    )
    axes[0, 1].legend()

    state = density["physical_state"]
    nuclei = density["hydrogen_nuclei_cm3"]
    for values, label in (
        (state.hydrogen_ionized_fraction, "H II"),
        (state.helium_neutral_fraction, "He I"),
        (state.helium_singly_ionized_fraction, "He II"),
        (state.helium_doubly_ionized_fraction, "He III"),
    ):
        axes[0, 2].semilogx(nuclei, values, label=label)
    axes[0, 2].set(
        xlabel=r"Hydrogen nuclei density (cm$^{-3}$)",
        ylabel="Ion fraction",
        title="(c) Collision + RR + three-body equilibrium",
        ylim=(-0.03, 1.03),
    )
    axes[0, 2].legend()

    axes[1, 0].loglog(
        nuclei,
        density["maximum_fraction_difference"],
        label="Maximum ion-fraction difference",
    )
    axes[1, 0].loglog(
        nuclei,
        density["electron_difference"],
        "--",
        label="Electron-density relative difference",
    )
    axes[1, 0].set(
        xlabel=r"Hydrogen nuclei density (cm$^{-3}$)",
        ylabel="Difference from collision--three-body Saha control",
        title="(d) High-density LTE asymptote",
    )
    axes[1, 0].legend(fontsize=8)

    time = relaxation["time_over_slow"]
    axes[1, 1].plot(time, relaxation["hydrogen"][:, 1], label="H II")
    axes[1, 1].plot(time, relaxation["helium"][:, 0], label="He I")
    axes[1, 1].plot(time, relaxation["helium"][:, 1], label="He II")
    axes[1, 1].plot(time, relaxation["helium"][:, 2], label="He III")
    axes[1, 1].set(
        xlabel="Time / slowest helium relaxation time",
        ylabel="Ion fraction",
        title="(e) Fixed-state rate-network relaxation",
        ylim=(-0.03, 1.03),
    )
    axes[1, 1].legend(fontsize=8)

    period = zo["orbital_period_s"]
    axes[1, 2].semilogy(
        zo["phase"], zo["hydrogen_relaxation_time_s"] / period, label="Hydrogen"
    )
    axes[1, 2].semilogy(
        zo["phase"], zo["helium_relaxation_time_s"] / period, label="Helium (slow)"
    )
    axes[1, 2].set(
        xlabel="Orbital time phase",
        ylabel="Local relaxation time / orbital period",
        title="(f) Prescribed ZO midplane timescale audit",
    )
    axes[1, 2].legend()
    for axis in axes.flat:
        axis.grid(alpha=0.25)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_convergence(path, records):
    figure, axes = plt.subplots(1, 2, figsize=(10.8, 4.2), constrained_layout=True)
    root = [record for record in records if record["control"] == "charge_neutrality_bisection"]
    positive = [record for record in root if record["error"] > 0.0]
    axes[0].semilogy(
        [record["grid_points_or_iterations"] for record in positive],
        [record["error"] for record in positive],
        "o-",
    )
    axes[0].set(
        xlabel="Bisection iterations",
        ylabel="Electron-density relative error",
        title="(a) Charge-neutrality root convergence",
    )
    for species in ("H", "He"):
        selected = [
            record
            for record in records
            if record["control"] == "zo_source_phase_grid"
            and record["observable"].startswith(species + "_")
        ]
        axes[1].loglog(
            [record["grid_points_or_iterations"] for record in selected],
            [record["error"] for record in selected],
            "o-",
            label=species,
        )
    axes[1].set(
        xlabel="Orbital source phase points",
        ylabel="RMS log-timescale error (dex)",
        title="(b) Prescribed ZO background convergence",
    )
    axes[1].legend()
    for axis in axes:
        axis.grid(alpha=0.25)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--anomaly-points", type=int, default=1024)
    arguments = parser.parse_args()
    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rate_records, rate_values = _rate_table()
    density_records, density_summary, density_values = _density_equilibrium_control()
    relaxation_records, relaxation_summary, relaxation_values = _fixed_relaxation_control()
    zo_values = _zo_midplane_timescales(int(arguments.anomaly_points))
    zo_records = _zo_timescale_records(zo_values)
    convergence = _convergence_controls()

    collision_at_1e5, _, _ = _atomic_coefficients(1.0e5)
    bisection_48 = next(
        record["error"]
        for record in convergence
        if record["control"] == "charge_neutrality_bisection"
        and record["grid_points_or_iterations"] == 48
    )
    phase_1024 = {
        record["observable"]: record["error"]
        for record in convergence
        if record["control"] == "zo_source_phase_grid"
        and record["grid_points_or_iterations"] == 1024
    }
    report = {
        "phase": "7B4a",
        "classification": "[L/A/V/O] H/He collisional kinetics and fixed-background relaxation controls",
        "atomic_data": {
            "collisional_ionization": "Voronov 1997; official cfit.dat H I, He I and He II rows",
            "three_body_recombination": "[A-control] C(T)/S(T), constructed from the same ground-state Saha factors",
            "radiative_recombination": "Verner and Ferland 1996 total RR fits retained from Phase 7B3",
            "collisional_ionization_coefficients_at_1e5_k_cm3_s": {
                fit.ion_label: float(value)
                for fit, value in zip(
                    H_HE_COLLISIONAL_IONIZATION_FITS,
                    collision_at_1e5,
                    strict=True,
                )
            },
        },
        "density_equilibrium_control": density_summary,
        "fixed_relaxation_control": relaxation_summary,
        "zo_midplane_timescale_audit": {
            "classification": "[A/V] gray-Eddington and LTE midplane state on the prescribed ZO orbit",
            "radial_index": zo_values["radial_index"],
            "anomaly_points": int(arguments.anomaly_points),
            "orbital_period_s": zo_values["orbital_period_s"],
            "temperature_range_k": [
                float(np.min(zo_values["temperature_k"])),
                float(np.max(zo_values["temperature_k"])),
            ],
            "electron_density_range_cm3": [
                float(np.min(zo_values["electron_density_cm3"])),
                float(np.max(zo_values["electron_density_cm3"])),
            ],
            "hydrogen_relaxation_over_orbit_range": [
                float(np.min(zo_values["hydrogen_relaxation_time_s"] / zo_values["orbital_period_s"])),
                float(np.max(zo_values["hydrogen_relaxation_time_s"] / zo_values["orbital_period_s"])),
            ],
            "helium_relaxation_over_orbit_range": [
                float(np.min(zo_values["helium_relaxation_time_s"] / zo_values["orbital_period_s"])),
                float(np.max(zo_values["helium_relaxation_time_s"] / zo_values["orbital_period_s"])),
            ],
            "warning": "fast midplane local rates do not establish surface LTE or solve orbit-coupled radiation hydrodynamics",
        },
        "acceptance": {
            "detailed_balance_relative_error": density_summary[
                "maximum_detailed_balance_relative_error"
            ],
            "collision_three_body_saha_ratio_relative_error": density_summary[
                "maximum_saha_ratio_relative_error"
            ],
            "maximum_relative_charge_residual": density_summary[
                "maximum_relative_charge_residual"
            ],
            "high_density_maximum_fraction_difference_from_saha": density_summary[
                "maximum_fraction_difference_at_highest_density"
            ],
            "fixed_hydrogen_analytic_maximum_absolute_error": relaxation_summary[
                "hydrogen_analytic_maximum_absolute_error"
            ],
            "fixed_helium_final_maximum_absolute_equilibrium_error": relaxation_summary[
                "helium_final_maximum_absolute_equilibrium_error"
            ],
            "fixed_network_maximum_particle_conservation_residual": relaxation_summary[
                "maximum_particle_conservation_residual"
            ],
            "bisection_48_iteration_electron_density_relative_error": bisection_48,
            "zo_phase_grid_1024_vs_2048": phase_1024,
        },
        "scientific_boundary": {
            "physical_nlte_spectrum_produced": False,
            "excited_levels_included": False,
            "gas_energy_equation_solved": False,
            "radiation_population_iteration_solved": False,
            "orbit_time_dependent_rates_coupled": False,
            "velocity_frequency_coupling_included": False,
            "next_stage": "Phase 7B4b orbit-coupled H/He ground-state kinetics after reviewing this control",
        },
    }

    _write_csv(output_dir / "phase7b4a_collisional_rates.csv", rate_records)
    _write_csv(output_dir / "phase7b4a_density_equilibrium.csv", density_records)
    _write_csv(output_dir / "phase7b4a_fixed_relaxation.csv", relaxation_records)
    _write_csv(output_dir / "phase7b4a_zo_midplane_timescales.csv", zo_records)
    _write_csv(output_dir / "phase7b4a_convergence.csv", convergence)
    (output_dir / "phase7b4a_collisional_kinetics_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _plot_controls(
        output_dir / "phase7b4a_collisional_kinetics_controls.png",
        rate_values,
        density_values,
        relaxation_values,
        zo_values,
    )
    _plot_convergence(
        output_dir / "phase7b4a_collisional_kinetics_convergence.png",
        convergence,
    )


if __name__ == "__main__":
    main()
