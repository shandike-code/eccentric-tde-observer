"""生成 Phase 7B4d 固定温度板层辐射--布居反馈控制证据。"""

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
    HE_I_RECOMBINATION_FIT,
    HE_II_RECOMBINATION_FIT,
    H_I_RECOMBINATION_FIT,
    ground_state_saha_factor_cm3,
)
from eccentric_tde_observer.atomic_kinetics import H_HE_COLLISIONAL_IONIZATION_FITS
from eccentric_tde_observer.atmosphere import SOLAR_FULLY_IONIZED_H_HE
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.prescribed_radiation import (
    edge_resolved_photoionization_energy_grid_ev,
    prescribed_planck_photoionization_rates_s1,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S, planck_nu
from eccentric_tde_observer.radiation_population_coupling import (
    CoupledRadiationPopulationSlab,
    solve_coupled_radiation_population_slab,
)
from eccentric_tde_observer.radiative_transfer_1d import gauss_legendre_mu_weights


GAS_TEMPERATURE_K = 4.0e4
RADIATION_TEMPERATURE_K = 1.5e5
DENSITY_G_CM3 = 1.0e-10
MASS_COLUMN_G_CM2 = 1.0e-4
INCIDENT_DILUTION = 1.0e-6
IONIZATION_ENERGIES_EV = (13.59843449, 24.587389, 54.417765)
PLOT_EDGE_ENERGIES_EV = (13.60, 24.59, 54.42)
BASE_FREQUENCY_POINTS = 513
BASE_DEPTH_POINTS = 16
BASE_ANGULAR_ORDER = 16
CONVERGENCE_FREQUENCY_POINTS = (65, 129, 257, 513, 1025, 2049)
CONVERGENCE_DEPTH_POINTS = (4, 8, 16, 32, 64)
CONVERGENCE_ANGULAR_ORDER = (2, 4, 8, 16, 32)
RELAXATION_SCAN = (0.3, 0.5, 0.7, 1.0)
OPACITY_SCALE_SCAN = (0.0, 0.1, 0.3, 1.0, 3.0)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _grid(base_points: int) -> tuple[np.ndarray, np.ndarray]:
    energy = edge_resolved_photoionization_energy_grid_ev(
        PLOT_EDGE_ENERGIES_EV[0], 5000.0, int(base_points)
    )
    return energy, energy * EV_ERG / PLANCK_ERG_S


def _atomic_rates() -> dict[str, np.ndarray]:
    collision = np.array(
        [fit.coefficient_cm3_s(GAS_TEMPERATURE_K) for fit in H_HE_COLLISIONAL_IONIZATION_FITS]
    )
    radiative = np.array(
        [
            H_I_RECOMBINATION_FIT.coefficient_cm3_s(GAS_TEMPERATURE_K),
            HE_I_RECOMBINATION_FIT.coefficient_cm3_s(GAS_TEMPERATURE_K),
            HE_II_RECOMBINATION_FIT.coefficient_cm3_s(GAS_TEMPERATURE_K),
        ]
    )
    saha = np.array(
        [
            ground_state_saha_factor_cm3(GAS_TEMPERATURE_K, energy)
            for energy in IONIZATION_ENERGIES_EV
        ]
    )
    return {
        "collision": collision,
        "radiative": radiative,
        "three_body": collision / saha,
        "saha": saha,
    }


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
    opacity_scale: float = 1.0,
    relaxation: float = 1.0,
    tolerance: float = 1.0e-10,
    include_electron_scattering: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, CoupledRadiationPopulationSlab]:
    energy, frequency = _grid(frequency_points)
    mu, weight = gauss_legendre_mu_weights(angular_order)
    incident, top, bottom = _one_sided_boundaries(frequency, mu)
    rates = _atomic_rates()
    if initial == "neutral":
        hydrogen = [1.0, 0.0]
        helium = [1.0, 0.0, 0.0]
    elif initial == "ionized":
        hydrogen = [0.0, 1.0]
        helium = [0.0, 0.0, 1.0]
    else:
        raise ValueError(f"unknown initial state: {initial}")
    thickness = MASS_COLUMN_G_CM2 / DENSITY_G_CM3
    result = solve_coupled_radiation_population_slab(
        frequency,
        np.linspace(0.0, thickness, depth_points + 1),
        mu,
        weight,
        DENSITY_G_CM3,
        0.0,
        top,
        bottom,
        hydrogen,
        helium,
        rates["collision"],
        rates["radiative"],
        rates["three_body"],
        include_electron_scattering=include_electron_scattering,
        opacity_scale=opacity_scale,
        relaxation=relaxation,
        tolerance=tolerance,
        maximum_iterations=512,
    )
    return energy, incident, mu, result


def _incident_energy_flux(
    frequency: np.ndarray,
    incident: np.ndarray,
    mu: np.ndarray,
    weight: np.ndarray,
) -> float:
    angular_factor = 2.0 * np.pi * np.sum(weight[mu > 0.0] * mu[mu > 0.0])
    return float(np.trapezoid(angular_factor * incident, frequency))


def _solution_metrics(
    energy: np.ndarray,
    incident: np.ndarray,
    mu: np.ndarray,
    result: CoupledRadiationPopulationSlab,
) -> dict[str, float]:
    weight = result.transfer.angular_weight
    incident_flux = _incident_energy_flux(
        result.transfer.frequency_hz, incident, mu, weight
    )
    transmitted = float(
        np.trapezoid(result.transfer.bottom_net_flux, result.transfer.frequency_hz)
    )
    reflected = incident_flux - float(
        np.trapezoid(result.transfer.top_net_flux, result.transfer.frequency_hz)
    )
    he3 = result.population.helium_doubly_ionized_fraction
    h2 = result.population.hydrogen_ionized_fraction
    centers = 0.5 * (
        result.transfer.depth_edges_cm[:-1] + result.transfer.depth_edges_cm[1:]
    )
    normalized_depth = centers / result.transfer.depth_edges_cm[-1]
    sample_depths = (0.2, 0.5, 0.8)
    total_optical_depth = np.sum(
        result.opacity.extinction_total_per_cm
        * np.diff(result.transfer.depth_edges_cm)[None, :],
        axis=1,
    )
    edge_depths = {}
    for label, edge in zip(("h_i", "he_i", "he_ii"), PLOT_EDGE_ENERGIES_EV, strict=True):
        index = int(np.flatnonzero(energy == edge)[0])
        edge_depths[f"tau_{label}_edge"] = float(total_optical_depth[index])
    return {
        **{
            f"h_ii_x{str(sample).replace('.', 'p')}": float(
                np.interp(sample, normalized_depth, h2)
            )
            for sample in sample_depths
        },
        **{
            f"he_iii_x{str(sample).replace('.', 'p')}": float(
                np.interp(sample, normalized_depth, he3)
            )
            for sample in sample_depths
        },
        "transmitted_energy_fraction": transmitted / incident_flux,
        "reflected_energy_fraction": reflected / incident_flux,
        "maximum_transfer_energy_residual": float(
            np.max(result.transfer.relative_energy_balance_residual)
        ),
        "maximum_population_fixed_point_residual": float(
            result.maximum_population_fixed_point_residual
        ),
        "maximum_relative_charge_residual": float(
            result.maximum_relative_charge_residual
        ),
        **edge_depths,
    }


def _lte_fixed_point_control() -> dict[str, float]:
    energy, frequency = _grid(257)
    mu, weight = gauss_legendre_mu_weights(4)
    planck = planck_nu(frequency, GAS_TEMPERATURE_K)
    top, bottom = _isotropic_boundaries(planck, mu)
    rates = _atomic_rates()
    gamma = prescribed_planck_photoionization_rates_s1(
        [GAS_TEMPERATURE_K], [1.0], energy
    ).photoionization_s1[0]
    radiative_detailed_balance = gamma / rates["saha"]
    lte = lte_hydrogen_helium_ionization(
        DENSITY_G_CM3, GAS_TEMPERATURE_K, SOLAR_FULLY_IONIZED_H_HE
    )
    result = solve_coupled_radiation_population_slab(
        frequency,
        np.linspace(0.0, MASS_COLUMN_G_CM2 / DENSITY_G_CM3, 9),
        mu,
        weight,
        DENSITY_G_CM3,
        planck[:, None],
        top,
        bottom,
        [lte.hydrogen_neutral_fraction, lte.hydrogen_ionized_fraction],
        [
            lte.helium_neutral_fraction,
            lte.helium_singly_ionized_fraction,
            lte.helium_doubly_ionized_fraction,
        ],
        rates["collision"],
        radiative_detailed_balance,
        rates["three_body"],
        tolerance=1.0e-12,
    )
    actual = np.column_stack(
        (
            result.population.hydrogen_neutral_fraction,
            result.population.hydrogen_ionized_fraction,
            result.population.helium_neutral_fraction,
            result.population.helium_singly_ionized_fraction,
            result.population.helium_doubly_ionized_fraction,
        )
    )
    expected = np.array(
        [
            lte.hydrogen_neutral_fraction,
            lte.hydrogen_ionized_fraction,
            lte.helium_neutral_fraction,
            lte.helium_singly_ionized_fraction,
            lte.helium_doubly_ionized_fraction,
        ]
    )
    positive_planck = planck > 0.0
    return {
        "iteration_count": result.iteration_count,
        "maximum_jnu_relative_error": float(
            np.max(
                np.abs(
                    result.transfer.mean_intensity[positive_planck]
                    / planck[positive_planck, None]
                    - 1.0
                )
            )
        ),
        "maximum_population_absolute_error": float(np.max(np.abs(actual - expected))),
        "maximum_population_fixed_point_residual": result.maximum_population_fixed_point_residual,
    }


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
    for family, cases in configurations.items():
        family_results = []
        for frequency_points, depth_points, angular_order, relaxation in cases:
            energy, incident, mu, solution = _solve(
                frequency_points,
                depth_points,
                angular_order,
                relaxation=relaxation,
                tolerance=1.0e-10,
            )
            metrics = _solution_metrics(energy, incident, mu, solution)
            family_results.append((frequency_points, depth_points, angular_order, relaxation, solution, metrics))
        reference_metrics = family_results[-1][-1]
        references[family] = reference_metrics
        population_names = (
            "h_ii_x0p2",
            "h_ii_x0p5",
            "h_ii_x0p8",
            "he_iii_x0p2",
            "he_iii_x0p5",
            "he_iii_x0p8",
        )
        for frequency_points, depth_points, angular_order, relaxation, solution, metrics in family_results:
            rows.append(
                {
                    "scan": family,
                    "frequency_base_points": frequency_points,
                    "depth_points": depth_points,
                    "angular_order": angular_order,
                    "relaxation": relaxation,
                    "iteration_count": solution.iteration_count,
                    "maximum_population_metric_absolute_error": max(
                        abs(metrics[name] - reference_metrics[name]) for name in population_names
                    ),
                    "transmitted_energy_fraction": metrics["transmitted_energy_fraction"],
                    "transmitted_energy_fraction_relative_error": abs(
                        metrics["transmitted_energy_fraction"]
                        / reference_metrics["transmitted_energy_fraction"]
                        - 1.0
                    ),
                    "maximum_population_fixed_point_residual": metrics[
                        "maximum_population_fixed_point_residual"
                    ],
                }
            )
    return rows, references


def _plot_main(
    output: Path,
    energy: np.ndarray,
    incident: np.ndarray,
    neutral: CoupledRadiationPopulationSlab,
    ionized: CoupledRadiationPopulationSlab,
) -> None:
    centers = 0.5 * (
        neutral.transfer.depth_edges_cm[:-1] + neutral.transfer.depth_edges_cm[1:]
    )
    normalized_depth = centers / neutral.transfer.depth_edges_cm[-1]
    widths = np.diff(neutral.transfer.depth_edges_cm)
    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.6), constrained_layout=True)
    edge_colors = ("#1f77b4", "#ff7f0e", "#2ca02c")
    for edge, color in zip(PLOT_EDGE_ENERGIES_EV, edge_colors, strict=True):
        index = int(np.flatnonzero(energy == edge)[0])
        axes[0, 0].plot(
            normalized_depth,
            neutral.transfer.mean_intensity[index] / incident[index],
            color=color,
            label=f"{edge:.2f} eV",
        )
        cell_depth = neutral.opacity.extinction_total_per_cm[index] * widths
        cumulative = np.cumsum(cell_depth) - 0.5 * cell_depth
        axes[1, 0].plot(normalized_depth, cumulative, color=color, label=f"{edge:.2f} eV")
    axes[0, 0].set(
        xlabel="Normalized depth from illuminated surface",
        ylabel="Mean intensity / incident intensity",
        title="Radiation attenuation",
    )
    axes[0, 0].set_yscale("log")
    axes[0, 0].legend(frameon=False)
    axes[0, 0].grid(alpha=0.25)

    population = neutral.population
    axes[0, 1].plot(normalized_depth, population.hydrogen_ionized_fraction, label="H II")
    axes[0, 1].plot(normalized_depth, population.helium_neutral_fraction, label="He I")
    axes[0, 1].plot(normalized_depth, population.helium_singly_ionized_fraction, label="He II")
    axes[0, 1].plot(normalized_depth, population.helium_doubly_ionized_fraction, label="He III")
    axes[0, 1].set(
        xlabel="Normalized depth from illuminated surface",
        ylabel="Ion fraction",
        title="Self-consistent ground-state populations",
        ylim=(-0.03, 1.03),
    )
    axes[0, 1].legend(frameon=False, ncol=2)
    axes[0, 1].grid(alpha=0.25)

    axes[1, 0].set(
        xlabel="Normalized depth from illuminated surface",
        ylabel="Cumulative extinction optical depth",
        title="Population-dependent optical depth",
    )
    axes[1, 0].set_yscale("log")
    axes[1, 0].grid(alpha=0.25)

    axes[1, 1].semilogy(
        np.arange(1, neutral.iteration_count + 1),
        neutral.iteration_residual_history,
        marker="o",
        ms=3,
        label="Initially neutral",
    )
    axes[1, 1].semilogy(
        np.arange(1, ionized.iteration_count + 1),
        ionized.iteration_residual_history,
        marker="s",
        ms=3,
        label="Initially ionized",
    )
    axes[1, 1].axhline(neutral.tolerance, color="black", ls="--", lw=1, label="Tolerance")
    axes[1, 1].set(
        xlabel="Picard iteration",
        ylabel="Maximum population update",
        title="Initial-state convergence",
    )
    axes[1, 1].legend(frameon=False)
    axes[1, 1].grid(alpha=0.25)
    figure.suptitle("Phase 7B4d: fixed-temperature radiation-population feedback", fontsize=14)
    figure.savefig(output, dpi=180)
    plt.close(figure)


def _plot_convergence(
    output: Path,
    rows: list[dict[str, object]],
    sensitivity: list[dict[str, object]],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.6), constrained_layout=True)
    family_style = {
        "frequency": ("frequency_base_points", "Frequency base points", "o"),
        "depth": ("depth_points", "Depth cells", "s"),
        "angle": ("angular_order", "Angular order", "^"),
    }
    for family, (field, label, marker) in family_style.items():
        selected = [row for row in rows if row["scan"] == family]
        population_selected = [
            row
            for row in selected
            if float(row["maximum_population_metric_absolute_error"]) > 0.0
        ]
        transfer_selected = [
            row
            for row in selected
            if float(row["transmitted_energy_fraction_relative_error"]) > 0.0
        ]
        axes[0, 0].loglog(
            [float(row[field]) for row in population_selected],
            [
                float(row["maximum_population_metric_absolute_error"])
                for row in population_selected
            ],
            marker=marker,
            label=label,
        )
        axes[0, 1].loglog(
            [float(row[field]) for row in transfer_selected],
            [
                float(row["transmitted_energy_fraction_relative_error"])
                for row in transfer_selected
            ],
            marker=marker,
            label=label,
        )
    axes[0, 0].set(
        xlabel="Resolution parameter",
        ylabel="Maximum absolute population-metric error",
        title="Population convergence",
    )
    axes[0, 1].set(
        xlabel="Resolution parameter",
        ylabel="Relative transmitted-flux error",
        title="Transfer convergence",
    )
    for axis in axes[0]:
        axis.legend(frameon=False)
        axis.grid(alpha=0.25, which="both")

    relaxation = [row for row in rows if row["scan"] == "relaxation"]
    axes[1, 0].plot(
        [float(row["relaxation"]) for row in relaxation],
        [int(row["iteration_count"]) for row in relaxation],
        marker="o",
    )
    axes[1, 0].set(
        xlabel="Under-relaxation factor",
        ylabel="Iterations to tolerance",
        title="Numerical relaxation sensitivity",
    )
    axes[1, 0].grid(alpha=0.25)

    scale = np.array([float(row["opacity_scale"]) for row in sensitivity])
    axes[1, 1].plot(
        scale,
        [float(row["he_iii_x0p2"]) for row in sensitivity],
        marker="o",
        label="He III at x = 0.2",
    )
    axes[1, 1].plot(
        scale,
        [float(row["he_iii_x0p8"]) for row in sensitivity],
        marker="s",
        label="He III at x = 0.8",
    )
    axes[1, 1].plot(
        scale,
        [float(row["transmitted_energy_fraction"]) for row in sensitivity],
        marker="^",
        label="Transmitted energy fraction",
    )
    axes[1, 1].set_xscale("symlog", linthresh=0.05)
    axes[1, 1].set(
        xlabel="Opacity feedback scale (control)",
        ylabel="Fraction",
        title="Transparent-to-opaque control",
    )
    axes[1, 1].legend(frameon=False)
    axes[1, 1].grid(alpha=0.25)
    figure.suptitle("Phase 7B4d: convergence and feedback controls", fontsize=14)
    figure.savefig(output, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    arguments = parser.parse_args()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)

    energy, incident, mu, neutral = _solve(
        BASE_FREQUENCY_POINTS,
        BASE_DEPTH_POINTS,
        BASE_ANGULAR_ORDER,
        initial="neutral",
    )
    _, _, _, ionized = _solve(
        BASE_FREQUENCY_POINTS,
        BASE_DEPTH_POINTS,
        BASE_ANGULAR_ORDER,
        initial="ionized",
    )
    metrics = _solution_metrics(energy, incident, mu, neutral)
    population_difference = max(
        float(
            np.max(
                np.abs(getattr(neutral.population, name) - getattr(ionized.population, name))
            )
        )
        for name in (
            "hydrogen_neutral_fraction",
            "hydrogen_ionized_fraction",
            "helium_neutral_fraction",
            "helium_singly_ionized_fraction",
            "helium_doubly_ionized_fraction",
        )
    )
    _, _, _, pure_absorption = _solve(
        129,
        8,
        4,
        include_electron_scattering=False,
    )
    lte_control = _lte_fixed_point_control()

    centers = 0.5 * (
        neutral.transfer.depth_edges_cm[:-1] + neutral.transfer.depth_edges_cm[1:]
    )
    depth_rows: list[dict[str, object]] = []
    for depth in range(centers.size):
        depth_rows.append(
            {
                "normalized_depth": centers[depth] / neutral.transfer.depth_edges_cm[-1],
                "hydrogen_i_fraction": neutral.population.hydrogen_neutral_fraction[depth],
                "hydrogen_ii_fraction": neutral.population.hydrogen_ionized_fraction[depth],
                "helium_i_fraction": neutral.population.helium_neutral_fraction[depth],
                "helium_ii_fraction": neutral.population.helium_singly_ionized_fraction[depth],
                "helium_iii_fraction": neutral.population.helium_doubly_ionized_fraction[depth],
                "electron_density_cm3": neutral.population.electron_density_cm3[depth],
                "gamma_h_i_s1": neutral.photoionization_rate_s1[depth, 0],
                "gamma_he_i_s1": neutral.photoionization_rate_s1[depth, 1],
                "gamma_he_ii_s1": neutral.photoionization_rate_s1[depth, 2],
            }
        )

    sensitivity: list[dict[str, object]] = []
    for scale in OPACITY_SCALE_SCAN:
        current_energy, current_incident, current_mu, solution = _solve(
            129, 8, 4, opacity_scale=scale
        )
        sensitivity.append(
            {
                "opacity_scale": scale,
                "iteration_count": solution.iteration_count,
                **_solution_metrics(current_energy, current_incident, current_mu, solution),
            }
        )
    convergence, convergence_references = _convergence_rows()

    _write_csv(arguments.output_dir / "phase7b4d_coupled_slab_depth.csv", depth_rows)
    _write_csv(arguments.output_dir / "phase7b4d_opacity_feedback_sensitivity.csv", sensitivity)
    _write_csv(arguments.output_dir / "phase7b4d_coupled_slab_convergence.csv", convergence)
    _plot_main(
        arguments.output_dir / "phase7b4d_coupled_slab.png",
        energy,
        incident,
        neutral,
        ionized,
    )
    _plot_convergence(
        arguments.output_dir / "phase7b4d_coupled_slab_convergence.png",
        convergence,
        sensitivity,
    )

    report = {
        "phase": "7B4d",
        "evidence_classification": {
            "fixed_temperature_density_slab": "[A-control]",
            "ground_state_population_opacity_feedback": "[V]",
            "physical_radiative_recombination_fit": "[L]",
            "missing_recombination_emissivity_excited_states_energy_equation": "[O]",
        },
        "parameters": {
            "gas_temperature_k": GAS_TEMPERATURE_K,
            "radiation_temperature_k": RADIATION_TEMPERATURE_K,
            "density_g_cm3": DENSITY_G_CM3,
            "mass_column_g_cm2": MASS_COLUMN_G_CM2,
            "incident_dilution": INCIDENT_DILUTION,
            "base_frequency_points_after_edges": int(energy.size),
            "base_depth_points": BASE_DEPTH_POINTS,
            "base_angular_order": BASE_ANGULAR_ORDER,
            "internal_thermal_source": "zero in illuminated control",
        },
        "baseline": {
            "neutral_initial_iterations": neutral.iteration_count,
            "ionized_initial_iterations": ionized.iteration_count,
            "maximum_initial_state_population_difference": population_difference,
            **metrics,
        },
        "controls": {
            "lte_planck_detailed_balance_fixed_point": lte_control,
            "pure_absorption_maximum_transfer_energy_residual": float(
                np.max(pure_absorption.transfer.relative_energy_balance_residual)
            ),
            "transparent_transmitted_energy_fraction": sensitivity[0][
                "transmitted_energy_fraction"
            ],
        },
        "convergence_reference_metrics": convergence_references,
        "scope_boundary": (
            "No recombination continuum emissivity, excited levels, bound-bound transfer, "
            "gas energy equation, orbit coupling, or final atmosphere spectrum is solved."
        ),
    }
    with (arguments.output_dir / "phase7b4d_coupled_slab_report.json").open(
        "w", encoding="utf-8"
    ) as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
