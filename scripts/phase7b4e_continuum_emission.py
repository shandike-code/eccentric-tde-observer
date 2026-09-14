"""生成 Phase 7B4e 基态 Milne 连续发射与能量账本证据。"""

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
    EV_ERG,
    ground_state_saha_factor_cm3,
)
from eccentric_tde_observer.continuum_emission import (
    IONIZATION_ENERGIES_EV,
    ContinuumPopulationInversionError,
    EmissiveCoupledSlab,
    edge_resolved_milne_energy_grid_ev,
    ground_state_milne_continuum,
    ground_state_milne_radiative_rates,
    solve_emissive_ground_state_slab,
)
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.radiation import PLANCK_ERG_S, planck_nu
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_half_range_mu_weights,
)


GAS_TEMPERATURE_K = 4.0e4
RADIATION_TEMPERATURE_K = 1.5e5
DENSITY_G_CM3 = 1.0e-10
MASS_COLUMN_G_CM2 = 1.0e-4
INCIDENT_DILUTION = 1.0e-6
MINIMUM_ENERGY_EV = 0.1
MAXIMUM_ENERGY_EV = 5000.0
BASE_FREQUENCY_POINTS = 1025
BASE_DEPTH_POINTS = 16
BASE_ANGULAR_ORDER = 16
CONVERGENCE_FREQUENCY_POINTS = (129, 257, 513, 1025, 2049, 4097)
CONVERGENCE_DEPTH_POINTS = (4, 8, 16, 32)
CONVERGENCE_ANGULAR_ORDER = (2, 4, 8, 16, 32)
RELAXATION_SCAN = (0.3, 0.5, 0.7, 1.0)
SAMPLE_DEPTHS = (0.2, 0.5, 0.8)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _grid(base_points: int) -> tuple[np.ndarray, np.ndarray]:
    energy = edge_resolved_milne_energy_grid_ev(
        MINIMUM_ENERGY_EV, MAXIMUM_ENERGY_EV, int(base_points)
    )
    return energy, energy * EV_ERG / PLANCK_ERG_S


def _lte_initial_fractions() -> tuple[list[float], list[float]]:
    state = lte_hydrogen_helium_ionization(
        DENSITY_G_CM3, GAS_TEMPERATURE_K
    )
    electron = float(state.electron_density_cm3)
    saha = np.array(
        [
            ground_state_saha_factor_cm3(GAS_TEMPERATURE_K, energy)
            for energy in IONIZATION_ENERGIES_EV
        ]
    )
    # 中文：直接由电子密度和 Saha 比重建极小中性分数，避免 1-x 的消减误差。
    hydrogen_denominator = electron + saha[0]
    hydrogen = [
        electron / hydrogen_denominator,
        saha[0] / hydrogen_denominator,
    ]
    helium_ratio_1 = saha[1] / electron
    helium_ratio_2 = saha[2] / electron
    helium_denominator = 1.0 + helium_ratio_1 + helium_ratio_1 * helium_ratio_2
    helium = [
        1.0 / helium_denominator,
        helium_ratio_1 / helium_denominator,
        helium_ratio_1 * helium_ratio_2 / helium_denominator,
    ]
    return hydrogen, helium


def _one_sided_boundaries(
    frequency_hz: np.ndarray, mu: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    incident = INCIDENT_DILUTION * planck_nu(
        frequency_hz, RADIATION_TEMPERATURE_K
    )
    top = np.zeros((frequency_hz.size, mu.size))
    top[:, mu > 0.0] = incident[:, None]
    return incident, top, np.zeros_like(top)


def _isotropic_boundaries(
    intensity: np.ndarray, mu: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    top = np.zeros((intensity.size, mu.size))
    bottom = np.zeros_like(top)
    top[:, mu > 0.0] = intensity[:, None]
    bottom[:, mu < 0.0] = intensity[:, None]
    return top, bottom


def _solve(
    frequency_points: int,
    depth_points: int,
    angular_order: int,
    *,
    initial: str = "neutral",
    relaxation: float = 1.0,
    tolerance: float = 1.0e-10,
) -> tuple[np.ndarray, np.ndarray, EmissiveCoupledSlab]:
    energy, frequency = _grid(frequency_points)
    mu, weight = gauss_legendre_half_range_mu_weights(angular_order)
    incident, top, bottom = _one_sided_boundaries(frequency, mu)
    if initial == "neutral":
        hydrogen = [1.0, 0.0]
        helium = [1.0, 0.0, 0.0]
    elif initial == "lte":
        hydrogen, helium = _lte_initial_fractions()
    else:
        raise ValueError(f"unknown admissible initial state: {initial}")
    thickness = MASS_COLUMN_G_CM2 / DENSITY_G_CM3
    result = solve_emissive_ground_state_slab(
        frequency,
        np.linspace(0.0, thickness, depth_points + 1),
        mu,
        weight,
        DENSITY_G_CM3,
        GAS_TEMPERATURE_K,
        top,
        bottom,
        hydrogen,
        helium,
        relaxation=relaxation,
        tolerance=tolerance,
        maximum_iterations=512,
    )
    return energy, incident, result


def _directional_fluxes(
    result: EmissiveCoupledSlab,
) -> dict[str, np.ndarray]:
    transfer = result.transfer
    mu = transfer.direction_cosine
    weight = transfer.angular_weight
    top = transfer.top_boundary_intensity
    bottom = transfer.bottom_boundary_intensity
    # 中文：四个方向分量均定义为正数；净通量的正方向仍是由顶面指向底面。
    return {
        "top_incoming": 2.0
        * np.pi
        * np.einsum("m,fm,m->f", weight[mu > 0.0], top[:, mu > 0.0], mu[mu > 0.0]),
        "top_outgoing": -2.0
        * np.pi
        * np.einsum("m,fm,m->f", weight[mu < 0.0], top[:, mu < 0.0], mu[mu < 0.0]),
        "bottom_incoming": -2.0
        * np.pi
        * np.einsum(
            "m,fm,m->f", weight[mu < 0.0], bottom[:, mu < 0.0], mu[mu < 0.0]
        ),
        "bottom_outgoing": 2.0
        * np.pi
        * np.einsum(
            "m,fm,m->f", weight[mu > 0.0], bottom[:, mu > 0.0], mu[mu > 0.0]
        ),
    }


def _integrate_spectrum(frequency: np.ndarray, spectrum: np.ndarray) -> float:
    return float(np.trapezoid(spectrum, frequency))


def _solution_metrics(result: EmissiveCoupledSlab) -> dict[str, float]:
    frequency = result.transfer.frequency_hz
    fluxes = _directional_fluxes(result)
    incident_flux = _integrate_spectrum(frequency, fluxes["top_incoming"])
    top_outgoing = _integrate_spectrum(frequency, fluxes["top_outgoing"])
    bottom_outgoing = _integrate_spectrum(frequency, fluxes["bottom_outgoing"])
    widths = np.diff(result.transfer.depth_edges_cm)
    radiative_heating = float(
        np.sum(result.radiative_heating_erg_s_cm3 * widths)
    )
    thermostat_heating = float(
        np.sum(result.required_thermostat_heating_erg_s_cm3 * widths)
    )
    centers = 0.5 * (
        result.transfer.depth_edges_cm[:-1] + result.transfer.depth_edges_cm[1:]
    )
    normalized_depth = centers / result.transfer.depth_edges_cm[-1]
    h_ii = result.population.hydrogen_ionized_fraction
    he_iii = result.population.helium_doubly_ionized_fraction
    metrics: dict[str, float] = {
        "incident_energy_flux_erg_s_cm2": incident_flux,
        "top_outgoing_energy_flux_erg_s_cm2": top_outgoing,
        "bottom_outgoing_energy_flux_erg_s_cm2": bottom_outgoing,
        "top_outgoing_energy_fraction": top_outgoing / incident_flux,
        "bottom_outgoing_energy_fraction": bottom_outgoing / incident_flux,
        "gas_radiative_heating_energy_fraction": radiative_heating / incident_flux,
        "required_thermostat_heating_energy_fraction": thermostat_heating
        / incident_flux,
        "radiative_partition_residual": abs(
            incident_flux - top_outgoing - bottom_outgoing - radiative_heating
        )
        / incident_flux,
        "relative_boundary_energy_balance_residual": result.relative_boundary_energy_balance_residual,
        "maximum_relative_photon_rate_identity_residual": result.maximum_relative_photon_rate_identity_residual,
        "maximum_population_fixed_point_residual": result.maximum_population_fixed_point_residual,
        "maximum_relative_charge_residual": result.maximum_relative_charge_residual,
    }
    for sample in SAMPLE_DEPTHS:
        suffix = str(sample).replace(".", "p")
        metrics[f"h_ii_x{suffix}"] = float(
            np.interp(sample, normalized_depth, h_ii)
        )
        metrics[f"he_iii_x{suffix}"] = float(
            np.interp(sample, normalized_depth, he_iii)
        )
    return metrics


def _population_difference(
    first: EmissiveCoupledSlab, second: EmissiveCoupledSlab
) -> float:
    names = (
        "hydrogen_neutral_fraction",
        "hydrogen_ionized_fraction",
        "helium_neutral_fraction",
        "helium_singly_ionized_fraction",
        "helium_doubly_ionized_fraction",
    )
    return max(
        float(np.max(np.abs(getattr(first.population, name) - getattr(second.population, name))))
        for name in names
    )


def _lte_control() -> tuple[dict[str, float], dict[str, np.ndarray]]:
    energy, frequency = _grid(513)
    mu, weight = gauss_legendre_half_range_mu_weights(8)
    planck = planck_nu(frequency, GAS_TEMPERATURE_K)
    top, bottom = _isotropic_boundaries(planck, mu)
    hydrogen, helium = _lte_initial_fractions()
    continuum = ground_state_milne_continuum(
        DENSITY_G_CM3,
        GAS_TEMPERATURE_K,
        frequency,
        hydrogen[0],
        hydrogen[1],
        helium[0],
        helium[1],
        helium[2],
    )
    rates = ground_state_milne_radiative_rates(
        GAS_TEMPERATURE_K, frequency, planck[:, None]
    )
    saha = np.array(
        [
            ground_state_saha_factor_cm3(GAS_TEMPERATURE_K, threshold)
            for threshold in IONIZATION_ENERGIES_EV
        ]
    )
    expected_recombination = rates.photoionization_s1[0] / saha
    result = solve_emissive_ground_state_slab(
        frequency,
        np.linspace(
            0.0, MASS_COLUMN_G_CM2 / DENSITY_G_CM3, BASE_DEPTH_POINTS + 1
        ),
        mu,
        weight,
        DENSITY_G_CM3,
        GAS_TEMPERATURE_K,
        top,
        bottom,
        hydrogen,
        helium,
        relaxation=1.0,
        tolerance=1.0e-12,
    )
    source_error = float(
        np.max(np.abs(continuum.thermal_source_intensity[:, 0] - planck))
        / np.max(planck)
    )
    jnu_error = float(
        np.max(np.abs(result.transfer.mean_intensity - planck[:, None]))
        / np.max(planck)
    )
    gross_absorption = 4.0 * np.pi * np.max(
        np.trapezoid(
            result.continuum.true_absorption_total_per_cm * planck[:, None],
            frequency,
            axis=0,
        )
    )
    metrics = {
        "iteration_count": result.iteration_count,
        "maximum_kirchhoff_source_error_normalized_by_peak_planck": source_error,
        "maximum_jnu_error_normalized_by_peak_planck": jnu_error,
        "maximum_radiative_heating_relative_to_gross_absorption": float(
            np.max(np.abs(result.radiative_heating_erg_s_cm3)) / gross_absorption
        ),
        "maximum_rate_detailed_balance_relative_error": float(
            np.max(np.abs(rates.total_recombination_cm3_s[0] / expected_recombination - 1.0))
        ),
        "relative_boundary_energy_balance_residual": result.relative_boundary_energy_balance_residual,
        "maximum_relative_photon_rate_identity_residual": result.maximum_relative_photon_rate_identity_residual,
    }
    arrays = {
        "energy_ev": energy,
        "planck": planck,
        "thermal_source": continuum.thermal_source_intensity[:, 0],
        "expected_recombination": expected_recombination,
        "actual_recombination": rates.total_recombination_cm3_s[0],
    }
    return metrics, arrays


def _inversion_control() -> dict[str, object]:
    _, frequency = _grid(65)
    try:
        ground_state_milne_continuum(
            DENSITY_G_CM3,
            GAS_TEMPERATURE_K,
            frequency,
            0.0,
            1.0,
            0.0,
            0.0,
            1.0,
        )
    except ContinuumPopulationInversionError as error:
        return {
            "rejected": True,
            "exception": type(error).__name__,
            "message": str(error),
        }
    raise AssertionError("population-inverted control was not rejected")


def _convergence_rows() -> tuple[list[dict[str, object]], dict[str, dict[str, float]]]:
    rows: list[dict[str, object]] = []
    references: dict[str, dict[str, float]] = {}
    configurations = {
        "frequency": [
            (points, 8, 4, 1.0) for points in CONVERGENCE_FREQUENCY_POINTS
        ],
        "depth": [(129, points, 4, 1.0) for points in CONVERGENCE_DEPTH_POINTS],
        "angle": [(129, 8, order, 1.0) for order in CONVERGENCE_ANGULAR_ORDER],
        "relaxation": [(129, 8, 4, value) for value in RELAXATION_SCAN],
    }
    population_names = tuple(
        f"{species}_x{str(sample).replace('.', 'p')}"
        for species in ("h_ii", "he_iii")
        for sample in SAMPLE_DEPTHS
    )
    for family, cases in configurations.items():
        family_results: list[tuple[tuple[int, int, int, float], EmissiveCoupledSlab, dict[str, float]]] = []
        for frequency_points, depth_points, angular_order, relaxation in cases:
            _, _, solution = _solve(
                frequency_points,
                depth_points,
                angular_order,
                relaxation=relaxation,
                tolerance=1.0e-10,
            )
            family_results.append(
                (
                    (frequency_points, depth_points, angular_order, relaxation),
                    solution,
                    _solution_metrics(solution),
                )
            )
        reference_metrics = family_results[-1][2]
        references[family] = reference_metrics
        for configuration, solution, metrics in family_results:
            frequency_points, depth_points, angular_order, relaxation = configuration
            top_error = abs(
                metrics["top_outgoing_energy_fraction"]
                / reference_metrics["top_outgoing_energy_fraction"]
                - 1.0
            )
            bottom_error = abs(
                metrics["bottom_outgoing_energy_fraction"]
                / reference_metrics["bottom_outgoing_energy_fraction"]
                - 1.0
            )
            heating_error = abs(
                metrics["gas_radiative_heating_energy_fraction"]
                / reference_metrics["gas_radiative_heating_energy_fraction"]
                - 1.0
            )
            rows.append(
                {
                    "scan": family,
                    "frequency_base_points": frequency_points,
                    "frequency_points_after_edges": solution.transfer.frequency_hz.size,
                    "depth_points": depth_points,
                    "angular_order": angular_order,
                    "relaxation": relaxation,
                    "iteration_count": solution.iteration_count,
                    "maximum_population_metric_absolute_error": max(
                        abs(metrics[name] - reference_metrics[name])
                        for name in population_names
                    ),
                    "top_outgoing_flux_relative_error": top_error,
                    "bottom_outgoing_flux_relative_error": bottom_error,
                    "gas_heating_relative_error": heating_error,
                    "maximum_flux_or_heating_relative_error": max(
                        top_error, bottom_error, heating_error
                    ),
                    "relative_boundary_energy_balance_residual": metrics[
                        "relative_boundary_energy_balance_residual"
                    ],
                    "maximum_relative_photon_rate_identity_residual": metrics[
                        "maximum_relative_photon_rate_identity_residual"
                    ],
                    "maximum_population_fixed_point_residual": metrics[
                        "maximum_population_fixed_point_residual"
                    ],
                }
            )
    return rows, references


def _baseline_refinement_rows(
    baseline_metrics: dict[str, float],
) -> tuple[
    list[dict[str, object]],
    dict[str, dict[str, float]],
    dict[str, EmissiveCoupledSlab],
]:
    rows: list[dict[str, object]] = []
    references: dict[str, dict[str, float]] = {}
    solutions: dict[str, EmissiveCoupledSlab] = {}
    cases = {
        "baseline_frequency": (
            2 * BASE_FREQUENCY_POINTS - 1,
            BASE_DEPTH_POINTS,
            BASE_ANGULAR_ORDER,
        ),
        "baseline_depth": (
            BASE_FREQUENCY_POINTS,
            2 * BASE_DEPTH_POINTS,
            BASE_ANGULAR_ORDER,
        ),
        "baseline_angle": (
            BASE_FREQUENCY_POINTS,
            BASE_DEPTH_POINTS,
            2 * BASE_ANGULAR_ORDER,
        ),
    }
    population_names = tuple(
        f"{species}_x{str(sample).replace('.', 'p')}"
        for species in ("h_ii", "he_iii")
        for sample in SAMPLE_DEPTHS
    )
    for scan, configuration in cases.items():
        frequency_points, depth_points, angular_order = configuration
        _, _, solution = _solve(
            frequency_points,
            depth_points,
            angular_order,
            relaxation=1.0,
            tolerance=1.0e-10,
        )
        reference = _solution_metrics(solution)
        references[scan] = reference
        solutions[scan] = solution
        top_error = abs(
            baseline_metrics["top_outgoing_energy_fraction"]
            / reference["top_outgoing_energy_fraction"]
            - 1.0
        )
        bottom_error = abs(
            baseline_metrics["bottom_outgoing_energy_fraction"]
            / reference["bottom_outgoing_energy_fraction"]
            - 1.0
        )
        heating_error = abs(
            baseline_metrics["gas_radiative_heating_energy_fraction"]
            / reference["gas_radiative_heating_energy_fraction"]
            - 1.0
        )
        rows.append(
            {
                "scan": scan,
                "frequency_base_points": frequency_points,
                "frequency_points_after_edges": solution.transfer.frequency_hz.size,
                "depth_points": depth_points,
                "angular_order": angular_order,
                "relaxation": 1.0,
                "iteration_count": solution.iteration_count,
                "maximum_population_metric_absolute_error": max(
                    abs(baseline_metrics[name] - reference[name])
                    for name in population_names
                ),
                "top_outgoing_flux_relative_error": top_error,
                "bottom_outgoing_flux_relative_error": bottom_error,
                "gas_heating_relative_error": heating_error,
                "maximum_flux_or_heating_relative_error": max(
                    top_error, bottom_error, heating_error
                ),
                "relative_boundary_energy_balance_residual": reference[
                    "relative_boundary_energy_balance_residual"
                ],
                "maximum_relative_photon_rate_identity_residual": reference[
                    "maximum_relative_photon_rate_identity_residual"
                ],
                "maximum_population_fixed_point_residual": reference[
                    "maximum_population_fixed_point_residual"
                ],
            }
        )
    return rows, references, solutions


def _plot_positive_log(axis, x: np.ndarray, y: np.ndarray, **kwargs) -> None:
    positive = y > 0.0
    axis.loglog(x[positive], y[positive], **kwargs)


def _plot_main(
    output: Path,
    energy: np.ndarray,
    presentation: EmissiveCoupledSlab,
    neutral_initial_control: EmissiveCoupledSlab,
    lte_initial: EmissiveCoupledSlab,
) -> None:
    frequency = presentation.transfer.frequency_hz
    fluxes = _directional_fluxes(presentation)
    incident_flux = _integrate_spectrum(frequency, fluxes["top_incoming"])
    centers = 0.5 * (
        presentation.transfer.depth_edges_cm[:-1]
        + presentation.transfer.depth_edges_cm[1:]
    )
    normalized_depth = centers / presentation.transfer.depth_edges_cm[-1]
    figure, axes = plt.subplots(2, 2, figsize=(12.2, 8.8), constrained_layout=True)

    for label, field, color in (
        ("Incident", "top_incoming", "black"),
        ("Top outward", "top_outgoing", "#1f77b4"),
        ("Bottom outward", "bottom_outgoing", "#d62728"),
    ):
        _plot_positive_log(
            axes[0, 0],
            energy,
            frequency * fluxes[field] / incident_flux,
            label=label,
            color=color,
        )
    for edge in IONIZATION_ENERGIES_EV:
        axes[0, 0].axvline(edge, color="0.75", lw=0.8, ls=":")
    axes[0, 0].set(
        xlabel="Photon energy (eV)",
        ylabel="Energy per logarithmic interval / incident flux",
        title="Finite-band continuum energy flow",
        xlim=(MINIMUM_ENERGY_EV, MAXIMUM_ENERGY_EV),
        ylim=(1.0e-8, 2.0),
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 0].grid(alpha=0.25, which="both")

    population = presentation.population
    axes[0, 1].plot(normalized_depth, population.hydrogen_ionized_fraction, label="H II")
    axes[0, 1].plot(normalized_depth, population.helium_neutral_fraction, label="He I")
    axes[0, 1].plot(
        normalized_depth, population.helium_singly_ionized_fraction, label="He II"
    )
    axes[0, 1].plot(
        normalized_depth, population.helium_doubly_ionized_fraction, label="He III"
    )
    axes[0, 1].set(
        xlabel="Normalized depth from illuminated surface",
        ylabel="Ion fraction",
        title="Self-consistent ground-state populations",
        ylim=(-0.03, 1.03),
    )
    axes[0, 1].legend(frameon=False, ncol=2)
    axes[0, 1].grid(alpha=0.25)

    axes[1, 0].plot(
        normalized_depth,
        presentation.radiative_heating_erg_s_cm3,
        label="Radiative heating",
    )
    axes[1, 0].plot(
        normalized_depth,
        presentation.required_thermostat_heating_erg_s_cm3,
        label="Required thermostat term",
    )
    axes[1, 0].axhline(0.0, color="black", lw=0.8)
    axes[1, 0].set(
        xlabel="Normalized depth from illuminated surface",
        ylabel="Volumetric power (erg s$^{-1}$ cm$^{-3}$)",
        title="Fixed-temperature energy ledger",
    )
    axes[1, 0].legend(frameon=False)
    axes[1, 0].grid(alpha=0.25)

    axes[1, 1].semilogy(
        np.arange(1, neutral_initial_control.iteration_count + 1),
        neutral_initial_control.iteration_residual_history,
        marker="o",
        ms=3,
        label="Initially neutral",
    )
    axes[1, 1].semilogy(
        np.arange(1, lte_initial.iteration_count + 1),
        lte_initial.iteration_residual_history,
        marker="s",
        ms=3,
        label="Initially LTE",
    )
    axes[1, 1].axhline(
        neutral_initial_control.tolerance,
        color="black",
        ls="--",
        lw=1,
        label="Tolerance",
    )
    axes[1, 1].set(
        xlabel="Picard iteration",
        ylabel="Maximum population update",
        title="Admissible initial-state convergence",
    )
    axes[1, 1].legend(frameon=False)
    axes[1, 1].grid(alpha=0.25, which="both")
    figure.suptitle(
        "Phase 7B4e: ground-state Milne continuum emission", fontsize=14
    )
    figure.savefig(output, dpi=180)
    plt.close(figure)


def _plot_controls(
    output: Path,
    lte_metrics: dict[str, float],
    lte_arrays: dict[str, np.ndarray],
    convergence: list[dict[str, object]],
    baseline_metrics: dict[str, float],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.2, 8.8), constrained_layout=True)
    energy = lte_arrays["energy_ev"]
    planck = lte_arrays["planck"]
    source = lte_arrays["thermal_source"]
    normalization = np.max(planck)
    _plot_positive_log(
        axes[0, 0], energy, planck / normalization, color="black", label="Planck function"
    )
    _plot_positive_log(
        axes[0, 0], energy, source / normalization, color="#d62728", ls="--", label="Milne source"
    )
    axes[0, 0].set(
        xlabel="Photon energy (eV)",
        ylabel="Intensity / peak Planck intensity",
        title="LTE Kirchhoff control",
        xlim=(MINIMUM_ENERGY_EV, MAXIMUM_ENERGY_EV),
        ylim=(1.0e-8, 2.0),
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 0].grid(alpha=0.25, which="both")

    species = np.arange(3)
    width = 0.36
    axes[0, 1].bar(
        species - width / 2,
        lte_arrays["expected_recombination"],
        width,
        label="Photoionization / Saha",
    )
    axes[0, 1].bar(
        species + width / 2,
        lte_arrays["actual_recombination"],
        width,
        label="Milne recombination",
    )
    axes[0, 1].set_xticks(species, ("H I", "He I", "He II"))
    axes[0, 1].set_yscale("log")
    axes[0, 1].set(
        ylabel="Rate coefficient (cm$^3$ s$^{-1}$)",
        title="Ground-state detailed balance",
    )
    axes[0, 1].legend(frameon=False)
    axes[0, 1].grid(alpha=0.25, axis="y", which="both")

    styles = {
        "frequency": ("frequency_base_points", "Frequency base points", "o"),
        "depth": ("depth_points", "Depth cells", "s"),
        "angle": ("angular_order", "Angular order", "^"),
    }
    for family, (field, label, marker) in styles.items():
        selected = [row for row in convergence if row["scan"] == family]
        x = np.array([float(row[field]) for row in selected])
        population_error = np.array(
            [float(row["maximum_population_metric_absolute_error"]) for row in selected]
        )
        flux_error = np.array(
            [float(row["maximum_flux_or_heating_relative_error"]) for row in selected]
        )
        _plot_positive_log(
            axes[1, 0], x, population_error, marker=marker, label=f"{label}: populations"
        )
        _plot_positive_log(
            axes[1, 0], x, flux_error, marker=marker, ls="--", label=f"{label}: energy"
        )
    axes[1, 0].set(
        xlabel="Resolution parameter",
        ylabel="Error relative to family reference",
        title="Separated numerical convergence",
    )
    axes[1, 0].legend(frameon=False, fontsize=8)
    axes[1, 0].grid(alpha=0.25, which="both")

    partition_labels = ("Top outward", "Bottom outward", "Gas heating", "Thermostat")
    partition = np.array(
        [
            baseline_metrics["top_outgoing_energy_fraction"],
            baseline_metrics["bottom_outgoing_energy_fraction"],
            baseline_metrics["gas_radiative_heating_energy_fraction"],
            baseline_metrics["required_thermostat_heating_energy_fraction"],
        ]
    )
    colors = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd")
    bars = axes[1, 1].bar(np.arange(4), partition, color=colors)
    axes[1, 1].bar_label(
        bars,
        labels=[f"{value:.4g}" for value in partition],
        padding=3,
        fontsize=8,
    )
    axes[1, 1].axhline(0.0, color="black", lw=0.8)
    axes[1, 1].set_xticks(np.arange(4), partition_labels, rotation=15)
    axes[1, 1].set(
        ylabel="Energy / incident energy",
        title="Finite-band energy partition",
    )
    axes[1, 1].grid(alpha=0.25, axis="y")
    axes[1, 1].text(
        0.03,
        0.96,
        "LTE source error = "
        f"{lte_metrics['maximum_kirchhoff_source_error_normalized_by_peak_planck']:.2e}",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=9,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85},
    )
    figure.suptitle(
        "Phase 7B4e: detailed-balance and convergence controls", fontsize=14
    )
    figure.savefig(output, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    arguments = parser.parse_args()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)

    energy, _, neutral = _solve(
        BASE_FREQUENCY_POINTS,
        BASE_DEPTH_POINTS,
        BASE_ANGULAR_ORDER,
        initial="neutral",
    )
    _, _, lte_initial = _solve(
        BASE_FREQUENCY_POINTS,
        BASE_DEPTH_POINTS,
        BASE_ANGULAR_ORDER,
        initial="lte",
    )
    control_metrics = _solution_metrics(neutral)
    initial_state_difference = _population_difference(neutral, lte_initial)
    lte_metrics, lte_arrays = _lte_control()
    inversion_control = _inversion_control()
    convergence, convergence_references = _convergence_rows()
    (
        baseline_refinement,
        baseline_refinement_references,
        baseline_refinement_solutions,
    ) = _baseline_refinement_rows(control_metrics)
    # 中文：正式展示采用已完成的双倍频率解；初态和逐轴加密仍使用 1025 点控制。
    presentation = baseline_refinement_solutions["baseline_frequency"]
    presentation_energy = presentation.transfer.frequency_hz * PLANCK_ERG_S / EV_ERG
    metrics = _solution_metrics(presentation)

    centers = 0.5 * (
        presentation.transfer.depth_edges_cm[:-1]
        + presentation.transfer.depth_edges_cm[1:]
    )
    normalized_depth = centers / presentation.transfer.depth_edges_cm[-1]
    depth_rows: list[dict[str, object]] = []
    for depth, normalized in enumerate(normalized_depth):
        depth_rows.append(
            {
                "normalized_depth": normalized,
                "hydrogen_i_fraction": presentation.population.hydrogen_neutral_fraction[depth],
                "hydrogen_ii_fraction": presentation.population.hydrogen_ionized_fraction[depth],
                "helium_i_fraction": presentation.population.helium_neutral_fraction[depth],
                "helium_ii_fraction": presentation.population.helium_singly_ionized_fraction[depth],
                "helium_iii_fraction": presentation.population.helium_doubly_ionized_fraction[depth],
                "electron_density_cm3": presentation.population.electron_density_cm3[depth],
                "radiative_heating_erg_s_cm3": presentation.radiative_heating_erg_s_cm3[depth],
                "required_thermostat_heating_erg_s_cm3": presentation.required_thermostat_heating_erg_s_cm3[depth],
                "gamma_h_i_s1": presentation.radiative_rates.photoionization_s1[depth, 0],
                "gamma_he_i_s1": presentation.radiative_rates.photoionization_s1[depth, 1],
                "gamma_he_ii_s1": presentation.radiative_rates.photoionization_s1[depth, 2],
                "alpha_h_i_cm3_s": presentation.radiative_rates.total_recombination_cm3_s[depth, 0],
                "alpha_he_i_cm3_s": presentation.radiative_rates.total_recombination_cm3_s[depth, 1],
                "alpha_he_ii_cm3_s": presentation.radiative_rates.total_recombination_cm3_s[depth, 2],
            }
        )

    fluxes = _directional_fluxes(presentation)
    incident_flux = metrics["incident_energy_flux_erg_s_cm2"]
    continuum_rows: list[dict[str, object]] = []
    for index, photon_energy in enumerate(presentation_energy):
        continuum_rows.append(
            {
                "photon_energy_ev": photon_energy,
                "frequency_hz": presentation.transfer.frequency_hz[index],
                "top_incoming_fnu_erg_s_cm2_hz": fluxes["top_incoming"][index],
                "top_outgoing_fnu_erg_s_cm2_hz": fluxes["top_outgoing"][index],
                "bottom_outgoing_fnu_erg_s_cm2_hz": fluxes["bottom_outgoing"][index],
                "top_incoming_log_energy_fraction": presentation.transfer.frequency_hz[index]
                * fluxes["top_incoming"][index]
                / incident_flux,
                "top_outgoing_log_energy_fraction": presentation.transfer.frequency_hz[index]
                * fluxes["top_outgoing"][index]
                / incident_flux,
                "bottom_outgoing_log_energy_fraction": presentation.transfer.frequency_hz[index]
                * fluxes["bottom_outgoing"][index]
                / incident_flux,
            }
        )

    _write_csv(
        arguments.output_dir / "phase7b4e_emissive_slab_depth.csv", depth_rows
    )
    _write_csv(
        arguments.output_dir / "phase7b4e_emergent_continuum.csv", continuum_rows
    )
    _write_csv(
        arguments.output_dir / "phase7b4e_continuum_convergence.csv",
        convergence + baseline_refinement,
    )
    _plot_main(
        arguments.output_dir / "phase7b4e_continuum_emission.png",
        presentation_energy,
        presentation,
        neutral,
        lte_initial,
    )
    _plot_controls(
        arguments.output_dir / "phase7b4e_continuum_convergence.png",
        lte_metrics,
        lte_arrays,
        convergence,
        metrics,
    )

    report = {
        "phase": "7B4e",
        "evidence_classification": {
            "fixed_temperature_density_ground_state_slab": "[A-control]",
            "milne_kirchhoff_relations": "[L/V]",
            "same_cross_section_photon_rate_identity": "[V]",
            "emergent_continuum_is_not_a_zo_atmosphere_prediction": "[A/O]",
            "missing_excited_levels_total_recombination_reconciliation_and_energy_equation": "[O]",
        },
        "parameters": {
            "gas_temperature_k": GAS_TEMPERATURE_K,
            "radiation_temperature_k": RADIATION_TEMPERATURE_K,
            "density_g_cm3": DENSITY_G_CM3,
            "mass_column_g_cm2": MASS_COLUMN_G_CM2,
            "incident_dilution": INCIDENT_DILUTION,
            "minimum_photon_energy_ev": MINIMUM_ENERGY_EV,
            "maximum_photon_energy_ev": MAXIMUM_ENERGY_EV,
            "control_frequency_base_points": BASE_FREQUENCY_POINTS,
            "presentation_frequency_base_points": 2 * BASE_FREQUENCY_POINTS - 1,
            "presentation_frequency_points_after_edges": int(
                presentation_energy.size
            ),
            "base_depth_points": BASE_DEPTH_POINTS,
            "base_angular_order": BASE_ANGULAR_ORDER,
            "temperature_treatment": "fixed; the reported thermostat term is diagnostic",
        },
        "baseline": {
            "presentation_iterations": presentation.iteration_count,
            **metrics,
        },
        "controls": {
            "admissible_initial_state_control": {
                "frequency_base_points": BASE_FREQUENCY_POINTS,
                "neutral_initial_iterations": neutral.iteration_count,
                "lte_initial_iterations": lte_initial.iteration_count,
                "maximum_population_difference": initial_state_difference,
                **control_metrics,
            },
            "lte_planck_control": lte_metrics,
            "population_inversion_control": inversion_control,
        },
        "convergence_reference_metrics": convergence_references,
        "baseline_direct_refinement": {
            row["scan"]: row for row in baseline_refinement
        },
        "baseline_direct_refinement_reference_metrics": baseline_refinement_references,
        "scope_boundary": (
            "The plotted continuum is a finite-band, fixed-temperature, ground-state "
            "Milne control. It is not a ZO atmosphere spectrum. Excited levels, total "
            "radiative recombination consistency, bound-bound transfer, a solved gas "
            "energy equation, velocity-frequency coupling, and orbit coupling remain open."
        ),
        "next_stage": (
            "Phase 7B4f should solve a prescribed-heating fixed-density slab temperature "
            "balance before any orbit-coupled atmosphere spectrum."
        ),
    }
    with (arguments.output_dir / "phase7b4e_continuum_emission_report.json").open(
        "w", encoding="utf-8"
    ) as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
