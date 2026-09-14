"""生成 Phase 7B4f 规定加热温度平衡、无根门与稳定性证据。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.continuum_emission import (
    EmissiveCoupledSlab,
    edge_resolved_milne_energy_grid_ev,
    solve_emissive_ground_state_slab,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S, planck_nu
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_half_range_mu_weights,
)
from eccentric_tde_observer.thermal_balance import (
    IsothermalTemperatureScan,
    ThermalEquilibriumSlab,
    one_face_blackbody_dissipation_flux_erg_s_cm2,
    sampled_temperature_root_intervals,
    scan_isothermal_temperature_balance,
    solve_prescribed_heating_temperature_profile,
    uniform_fixed_density_heating_erg_s_cm3,
)


DENSITY_G_CM3 = 1.0e-10
MASS_COLUMN_G_CM2 = 1.0e-4
RADIATION_TEMPERATURE_K = 1.5e5
INCIDENT_DILUTION = 1.0e-6
MINIMUM_ENERGY_EV = 0.1
MAXIMUM_ENERGY_EV = 5000.0
MINIMUM_TEMPERATURE_K = 1.0e4
MAXIMUM_TEMPERATURE_K = 3.0e6
PRESENTATION_FREQUENCY_POINTS = 257
PRESENTATION_DEPTH_POINTS = 8
PRESENTATION_ANGULAR_ORDER = 8
ISOTHERMAL_SCAN_POINTS = 25
HEATING_FRACTIONS = (0.0, 1.0e-6, 1.0e-5, 3.0e-5, 1.0e-4, 1.0)
STABILITY_STEPS = (5.0e-4, 1.0e-3, 2.0e-3)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _read_pericentre_heating_reference(path: Path) -> dict[str, float | str]:
    with path.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    selected = next(row for row in rows if int(row["phase_index"]) == 0)
    temperature = float(selected["effective_temperature_k"])
    tabulated_flux = float(selected["one_face_surface_flux_erg_s_cm2"])
    stefan_flux = one_face_blackbody_dissipation_flux_erg_s_cm2(temperature)
    relative = abs(stefan_flux / tabulated_flux - 1.0)
    if relative > 2.0e-12:
        raise AssertionError("Phase 7B1 one-face flux does not match Stefan--Boltzmann")
    return {
        "source_file": str(path),
        "phase_index": 0,
        "effective_temperature_k": temperature,
        "one_face_surface_flux_erg_s_cm2": tabulated_flux,
        "one_sided_column_mass_g_cm2": float(
            selected["one_sided_column_mass_g_cm2"]
        ),
        "stefan_boltzmann_relative_residual": relative,
    }


def _grid(base_points: int) -> tuple[np.ndarray, np.ndarray]:
    energy = edge_resolved_milne_energy_grid_ev(
        MINIMUM_ENERGY_EV, MAXIMUM_ENERGY_EV, int(base_points)
    )
    return energy, energy * EV_ERG / PLANCK_ERG_S


def _problem(
    frequency_points: int,
    depth_points: int,
    angular_order: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    energy, frequency = _grid(frequency_points)
    mu, weight = gauss_legendre_half_range_mu_weights(angular_order)
    edges = np.linspace(
        0.0, MASS_COLUMN_G_CM2 / DENSITY_G_CM3, depth_points + 1
    )
    top = np.zeros((frequency.size, mu.size))
    top[:, mu > 0.0] = (
        INCIDENT_DILUTION
        * planck_nu(frequency, RADIATION_TEMPERATURE_K)[:, None]
    )
    return energy, frequency, mu, weight, edges, top


def _solve_profile(
    frequency_points: int,
    depth_points: int,
    angular_order: int,
    *,
    initial_temperature_k: float = 4.5e4,
    stability_relative_step: float = 1.0e-3,
    analyze_stability: bool = True,
) -> tuple[np.ndarray, ThermalEquilibriumSlab]:
    energy, frequency, mu, weight, edges, top = _problem(
        frequency_points, depth_points, angular_order
    )
    result = solve_prescribed_heating_temperature_profile(
        frequency,
        edges,
        mu,
        weight,
        DENSITY_G_CM3,
        top,
        np.zeros_like(top),
        0.0,
        initial_temperature_k,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        temperature_bounds_k=(MINIMUM_TEMPERATURE_K, 3.0e5),
        population_relaxation=1.0,
        population_tolerance=1.0e-9,
        local_energy_tolerance=2.0e-5,
        optimizer_tolerance=1.0e-8,
        maximum_function_evaluations=512,
        stability_relative_step=stability_relative_step,
        analyze_stability=analyze_stability,
    )
    return energy, result


def _isothermal_scan(
    frequency_points: int,
    depth_points: int,
    angular_order: int,
    temperature_grid_k: np.ndarray,
    heating_flux_erg_s_cm2: float,
) -> IsothermalTemperatureScan:
    _, frequency, mu, weight, edges, top = _problem(
        frequency_points, depth_points, angular_order
    )
    heating = uniform_fixed_density_heating_erg_s_cm3(
        heating_flux_erg_s_cm2, edges
    )
    return scan_isothermal_temperature_balance(
        temperature_grid_k,
        frequency,
        edges,
        mu,
        weight,
        DENSITY_G_CM3,
        top,
        np.zeros_like(top),
        heating,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        population_relaxation=1.0,
        population_tolerance=1.0e-9,
        root_relative_temperature_tolerance=1.0e-9,
        stability_relative_step=1.0e-3,
    )


def _directional_fluxes(slab: EmissiveCoupledSlab) -> dict[str, np.ndarray]:
    transfer = slab.transfer
    mu = transfer.direction_cosine
    weight = transfer.angular_weight
    top = transfer.top_boundary_intensity
    bottom = transfer.bottom_boundary_intensity
    return {
        "top_incoming": 2.0
        * np.pi
        * np.einsum(
            "m,fm,m->f", weight[mu > 0.0], top[:, mu > 0.0], mu[mu > 0.0]
        ),
        "top_outgoing": -2.0
        * np.pi
        * np.einsum(
            "m,fm,m->f", weight[mu < 0.0], top[:, mu < 0.0], mu[mu < 0.0]
        ),
        "bottom_outgoing": 2.0
        * np.pi
        * np.einsum(
            "m,fm,m->f",
            weight[mu > 0.0],
            bottom[:, mu > 0.0],
            mu[mu > 0.0],
        ),
    }


def _integrated_flux(frequency: np.ndarray, spectrum: np.ndarray) -> float:
    return float(np.trapezoid(spectrum, frequency))


def _population_error(
    trial: ThermalEquilibriumSlab,
    reference: ThermalEquilibriumSlab,
) -> float:
    trial_edges = trial.slab.transfer.depth_edges_cm
    reference_edges = reference.slab.transfer.depth_edges_cm
    trial_depth = 0.5 * (trial_edges[:-1] + trial_edges[1:]) / trial_edges[-1]
    reference_depth = (
        0.5 * (reference_edges[:-1] + reference_edges[1:]) / reference_edges[-1]
    )
    names = (
        "hydrogen_ionized_fraction",
        "helium_singly_ionized_fraction",
        "helium_doubly_ionized_fraction",
    )
    return max(
        float(
            np.max(
                np.abs(
                    np.interp(
                        reference_depth,
                        trial_depth,
                        getattr(trial.slab.population, name),
                    )
                    - getattr(reference.slab.population, name)
                )
            )
        )
        for name in names
    )


def _profile_comparison(
    label: str,
    frequency_points: int,
    depth_points: int,
    angular_order: int,
    initial_temperature_k: float,
    trial: ThermalEquilibriumSlab,
    reference: ThermalEquilibriumSlab,
) -> dict[str, object]:
    trial_edges = trial.slab.transfer.depth_edges_cm
    reference_edges = reference.slab.transfer.depth_edges_cm
    trial_depth = 0.5 * (trial_edges[:-1] + trial_edges[1:]) / trial_edges[-1]
    reference_depth = (
        0.5 * (reference_edges[:-1] + reference_edges[1:]) / reference_edges[-1]
    )
    interpolated_temperature = np.interp(
        reference_depth, trial_depth, trial.temperature_k
    )
    temperature_error = float(
        np.max(
            np.abs(interpolated_temperature - reference.temperature_k)
            / reference.temperature_k
        )
    )
    trial_flux = _directional_fluxes(trial.slab)
    reference_flux = _directional_fluxes(reference.slab)
    trial_top = _integrated_flux(
        trial.slab.transfer.frequency_hz, trial_flux["top_outgoing"]
    )
    reference_top = _integrated_flux(
        reference.slab.transfer.frequency_hz, reference_flux["top_outgoing"]
    )
    trial_bottom = _integrated_flux(
        trial.slab.transfer.frequency_hz, trial_flux["bottom_outgoing"]
    )
    reference_bottom = _integrated_flux(
        reference.slab.transfer.frequency_hz, reference_flux["bottom_outgoing"]
    )
    return {
        "scan": label,
        "frequency_base_points": frequency_points,
        "depth_points": depth_points,
        "angular_order": angular_order,
        "initial_temperature_k": initial_temperature_k,
        "maximum_temperature_profile_relative_error": temperature_error,
        "maximum_population_fraction_absolute_error": _population_error(
            trial, reference
        ),
        "top_outgoing_flux_relative_error": abs(trial_top / reference_top - 1.0),
        "bottom_outgoing_flux_relative_error": abs(
            trial_bottom / reference_bottom - 1.0
        ),
        "maximum_relative_local_energy_residual": (
            trial.maximum_relative_local_energy_residual
        ),
        "relative_global_energy_residual": trial.relative_global_energy_residual,
    }


def _root_summary(
    fraction: float,
    net_curve: np.ndarray,
    temperature: np.ndarray,
    refined: IsothermalTemperatureScan | None,
) -> dict[str, object]:
    intervals = sampled_temperature_root_intervals(temperature, net_curve)
    roots = () if refined is None else refined.roots
    return {
        "heating_fraction_of_zo_pericentre_flux": fraction,
        "sampled_root_interval_count": len(intervals),
        "sampled_root_intervals_k": [list(interval) for interval in intervals],
        "refined_root_count": len(roots),
        "refined_root_temperatures_k": [root.temperature_k for root in roots],
        "refined_root_stability": [root.thermally_stable for root in roots],
        "minimum_sampled_net_heating_flux_erg_s_cm2": float(np.min(net_curve)),
        "maximum_sampled_net_heating_flux_erg_s_cm2": float(np.max(net_curve)),
    }


def _plot_main(
    output_path: Path,
    zo_flux: float,
    temperature_scan: np.ndarray,
    radiative_flux: np.ndarray,
    heating_curves: dict[float, np.ndarray],
    main: ThermalEquilibriumSlab,
    fixed: EmissiveCoupledSlab,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13.0, 9.2), constrained_layout=True)
    ax = axes[0, 0]
    for fraction in HEATING_FRACTIONS:
        label = "No mechanical heating" if fraction == 0.0 else f"Heating = {fraction:g} F_ZO"
        ax.plot(
            temperature_scan,
            heating_curves[fraction] / zo_flux,
            marker="o",
            markersize=2.8,
            label=label,
        )
    ax.axhline(0.0, color="black", linewidth=0.9)
    ax.set_xscale("log")
    ax.set_yscale("symlog", linthresh=1.0e-7)
    ax.set_xlabel("Uniform gas temperature [K]")
    ax.set_ylabel("Integrated net heating / pericentre F_ZO")
    ax.set_title("Isothermal root topology")
    ax.legend(fontsize=7.4, ncol=2)

    edges = main.slab.transfer.depth_edges_cm
    depth = 0.5 * (edges[:-1] + edges[1:]) / edges[-1]
    ax = axes[0, 1]
    ax.plot(depth, main.temperature_k, marker="o", color="tab:red")
    ax.set_xlabel("Normalized depth from illuminated face")
    ax.set_ylabel("Gas temperature [K]")
    ax.set_title("Depth-resolved radiative equilibrium")
    ax.grid(alpha=0.25)

    ax = axes[1, 0]
    population = main.slab.population
    ax.plot(depth, population.hydrogen_ionized_fraction, label="H II")
    ax.plot(depth, population.helium_singly_ionized_fraction, label="He II")
    ax.plot(depth, population.helium_doubly_ionized_fraction, label="He III")
    ax.set_xlabel("Normalized depth from illuminated face")
    ax.set_ylabel("Ion fraction")
    ax.set_ylim(0.0, 1.04)
    ax.set_title("Ground-state ionization at equilibrium")
    ax.legend()
    ax.grid(alpha=0.25)

    ax = axes[1, 1]
    main_flux = _directional_fluxes(main.slab)
    fixed_flux = _directional_fluxes(fixed)
    frequency = main.slab.transfer.frequency_hz
    energy = PLANCK_ERG_S * frequency / EV_ERG
    incident = _integrated_flux(frequency, main_flux["top_incoming"])
    main_outgoing = main_flux["top_outgoing"] + main_flux["bottom_outgoing"]
    fixed_outgoing = fixed_flux["top_outgoing"] + fixed_flux["bottom_outgoing"]
    ax.plot(
        energy,
        frequency * main_outgoing / incident,
        label="Solved T(z), zero mechanical heating",
    )
    ax.plot(
        energy,
        frequency * fixed_outgoing / incident,
        linestyle="--",
        label="Fixed T = 40,000 K",
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_ylim(1.0e-8, 2.0)
    ax.set_xlabel("Photon energy [eV]")
    ax.set_ylabel("nu F_nu,out / incident flux")
    ax.set_title("Continuum response to the temperature closure")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25, which="both")
    fig.suptitle("Phase 7B4f: prescribed-heating temperature balance", fontsize=15)
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def _plot_convergence(
    output_path: Path,
    convergence_rows: list[dict[str, object]],
    stability_rows: list[dict[str, object]],
    root_rows: list[dict[str, object]],
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8.8), constrained_layout=True)
    labels = [str(row["scan"]) for row in convergence_rows]
    positions = np.arange(len(labels))
    ax = axes[0, 0]
    ax.bar(
        positions,
        [float(row["maximum_temperature_profile_relative_error"]) for row in convergence_rows],
        color="tab:red",
    )
    ax.set_yscale("log")
    ax.set_xticks(positions, labels, rotation=20, ha="right")
    ax.set_ylabel("Maximum relative error")
    ax.set_title("Temperature-profile refinement")
    ax.grid(axis="y", alpha=0.25)

    ax = axes[0, 1]
    width = 0.38
    ax.bar(
        positions - width / 2.0,
        [float(row["top_outgoing_flux_relative_error"]) for row in convergence_rows],
        width,
        label="Top outgoing flux",
    )
    ax.bar(
        positions + width / 2.0,
        [float(row["bottom_outgoing_flux_relative_error"]) for row in convergence_rows],
        width,
        label="Bottom outgoing flux",
    )
    ax.set_yscale("log")
    ax.set_xticks(positions, labels, rotation=20, ha="right")
    ax.set_ylabel("Relative error")
    ax.set_title("Emergent-flux refinement")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 0]
    steps = [float(row["stability_relative_step"]) for row in stability_rows]
    signed_rates = np.array(
        [float(row["maximum_thermal_growth_rate_s1"]) for row in stability_rows]
    )
    reference_rate = signed_rates[int(np.argmin(np.abs(np.asarray(steps) - 1.0e-3)))]
    rate_difference_ppm = (signed_rates / reference_rate - 1.0) * 1.0e6
    ax.plot(steps, rate_difference_ppm, marker="o")
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xscale("log")
    ax.set_xlabel("Relative finite-difference step")
    ax.set_ylabel("Growth-rate deviation from h=1e-3 [ppm]")
    ax.set_title("Thermal-stability derivative sensitivity")
    ax.grid(alpha=0.25, which="both")

    ax = axes[1, 1]
    fractions = [float(row["heating_fraction_of_zo_pericentre_flux"]) for row in root_rows]
    counts = [int(row["sampled_root_interval_count"]) for row in root_rows]
    display_fraction = [value if value > 0.0 else 1.0e-7 for value in fractions]
    ax.step(display_fraction, counts, where="mid")
    ax.scatter(display_fraction, counts)
    ax.set_xscale("log")
    ax.set_xlabel("Deposited fraction of pericentre F_ZO")
    ax.set_ylabel("Sampled root count")
    ax.set_yticks((0, 1, 2))
    ax.set_title("Root survival under prescribed heating")
    ax.grid(alpha=0.25, which="both")
    fig.suptitle("Phase 7B4f: convergence and failure gates", fontsize=15)
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    arguments = parser.parse_args()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    zo_reference = _read_pericentre_heating_reference(
        arguments.output_dir / "phase7b_periodic_column_background.csv"
    )
    zo_flux = float(zo_reference["one_face_surface_flux_erg_s_cm2"])

    print("[1/7] Solving the presentation temperature profile", flush=True)
    energy, main = _solve_profile(
        PRESENTATION_FREQUENCY_POINTS,
        PRESENTATION_DEPTH_POINTS,
        PRESENTATION_ANGULAR_ORDER,
    )
    _, frequency, mu, weight, edges, top = _problem(
        PRESENTATION_FREQUENCY_POINTS,
        PRESENTATION_DEPTH_POINTS,
        PRESENTATION_ANGULAR_ORDER,
    )
    fixed = solve_emissive_ground_state_slab(
        frequency,
        edges,
        mu,
        weight,
        DENSITY_G_CM3,
        4.0e4,
        top,
        np.zeros_like(top),
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        relaxation=1.0,
        tolerance=1.0e-9,
    )

    print("[2/7] Scanning the isothermal energy curve", flush=True)
    temperature_scan = np.geomspace(
        MINIMUM_TEMPERATURE_K, MAXIMUM_TEMPERATURE_K, ISOTHERMAL_SCAN_POINTS
    )
    zero_heating_scan = _isothermal_scan(
        PRESENTATION_FREQUENCY_POINTS,
        PRESENTATION_DEPTH_POINTS,
        PRESENTATION_ANGULAR_ORDER,
        temperature_scan,
        0.0,
    )
    if not np.all(zero_heating_scan.valid_evaluation):
        raise RuntimeError("presentation isothermal scan contains failed points")
    radiative_flux = zero_heating_scan.radiative_heating_flux_erg_s_cm2
    heating_curves = {
        fraction: radiative_flux + fraction * zo_flux
        for fraction in HEATING_FRACTIONS
    }
    monotonic_radiative_cooling = bool(np.all(np.diff(radiative_flux) < 0.0))

    print("[3/7] Refining prescribed-heating roots", flush=True)
    refined_cases: dict[float, IsothermalTemperatureScan] = {
        0.0: zero_heating_scan
    }
    for fraction in (1.0e-6, 1.0e-5, 3.0e-5):
        intervals = sampled_temperature_root_intervals(
            temperature_scan, heating_curves[fraction]
        )
        if len(intervals) == 1:
            lower, upper = intervals[0]
            mini_grid = np.array(
                [MINIMUM_TEMPERATURE_K, lower, upper, MAXIMUM_TEMPERATURE_K]
            )
            mini_grid = np.unique(mini_grid)
            refined_cases[fraction] = _isothermal_scan(
                PRESENTATION_FREQUENCY_POINTS,
                PRESENTATION_DEPTH_POINTS,
                PRESENTATION_ANGULAR_ORDER,
                mini_grid,
                fraction * zo_flux,
            )

    root_rows = [
        _root_summary(
            fraction,
            heating_curves[fraction],
            temperature_scan,
            refined_cases.get(fraction),
        )
        for fraction in HEATING_FRACTIONS
    ]

    trial_configurations = (
        ("frequency 257->513", 513, 8, 8, 4.5e4),
        ("depth 8->16", 257, 16, 8, 4.5e4),
        ("angle 8->16", 257, 8, 16, 4.5e4),
        ("initial T 80k", 257, 8, 8, 8.0e4),
    )
    print("[4/7] Running direct profile refinements", flush=True)
    convergence_rows: list[dict[str, object]] = []
    for label, frequency_points, depth_points, angular_order, initial_temperature in trial_configurations:
        print(f"      {label}", flush=True)
        _, trial = _solve_profile(
            frequency_points,
            depth_points,
            angular_order,
            initial_temperature_k=initial_temperature,
            analyze_stability=False,
        )
        convergence_rows.append(
            _profile_comparison(
                label,
                frequency_points,
                depth_points,
                angular_order,
                initial_temperature,
                trial,
                main,
            )
        )

    print("[5/7] Checking thermal-stability step sensitivity", flush=True)
    stability_rows: list[dict[str, object]] = []
    for step in STABILITY_STEPS:
        print(f"      h={step:g}", flush=True)
        _, stability = _solve_profile(
            129,
            4,
            4,
            stability_relative_step=step,
            analyze_stability=True,
        )
        if stability.maximum_thermal_growth_rate_s1 is None:
            raise AssertionError("stability control did not return a growth rate")
        stability_rows.append(
            {
                "stability_relative_step": step,
                "maximum_thermal_growth_rate_s1": (
                    stability.maximum_thermal_growth_rate_s1
                ),
                "thermally_stable": stability.thermally_stable,
                "maximum_relative_local_energy_residual": (
                    stability.maximum_relative_local_energy_residual
                ),
            }
        )

    print("[6/7] Running direct isothermal-root refinements", flush=True)
    root_convergence_rows: list[dict[str, object]] = []
    root_temperature_grid = np.array([2.0e4, 3.0e4, 4.0e4, 5.0e4, 7.0e4])
    root_reference = zero_heating_scan.roots[0].temperature_k
    for label, frequency_points, depth_points, angular_order in (
        ("frequency", 513, 8, 8),
        ("depth", 257, 16, 8),
        ("angle", 257, 8, 16),
    ):
        print(f"      {label}", flush=True)
        scan = _isothermal_scan(
            frequency_points,
            depth_points,
            angular_order,
            root_temperature_grid,
            0.0,
        )
        if len(scan.roots) != 1:
            raise RuntimeError(f"{label} root convergence did not find exactly one root")
        root_convergence_rows.append(
            {
                "scan": label,
                "frequency_base_points": frequency_points,
                "depth_points": depth_points,
                "angular_order": angular_order,
                "root_temperature_k": scan.roots[0].temperature_k,
                "root_temperature_relative_error": abs(
                    scan.roots[0].temperature_k / root_reference - 1.0
                ),
                "thermally_stable": scan.roots[0].thermally_stable,
            }
        )

    centers = 0.5 * (edges[:-1] + edges[1:])
    normalized_depth = centers / edges[-1]
    profile_rows = []
    population = main.slab.population
    for index, depth in enumerate(normalized_depth):
        profile_rows.append(
            {
                "normalized_depth": depth,
                "temperature_k": main.temperature_k[index],
                "hydrogen_i_fraction": population.hydrogen_neutral_fraction[index],
                "hydrogen_ii_fraction": population.hydrogen_ionized_fraction[index],
                "helium_i_fraction": population.helium_neutral_fraction[index],
                "helium_ii_fraction": population.helium_singly_ionized_fraction[index],
                "helium_iii_fraction": population.helium_doubly_ionized_fraction[index],
                "electron_density_cm3": population.electron_density_cm3[index],
                "prescribed_heating_erg_s_cm3": main.prescribed_heating_erg_s_cm3[index],
                "radiative_heating_erg_s_cm3": main.slab.radiative_heating_erg_s_cm3[index],
                "net_heating_erg_s_cm3": main.net_heating_erg_s_cm3[index],
            }
        )
    scan_rows = []
    for index, temperature in enumerate(temperature_scan):
        row: dict[str, object] = {
            "temperature_k": temperature,
            "radiative_heating_flux_erg_s_cm2": radiative_flux[index],
        }
        for fraction in HEATING_FRACTIONS:
            label = str(fraction).replace(".", "p").replace("-", "m")
            row[f"net_heating_fraction_{label}_erg_s_cm2"] = heating_curves[
                fraction
            ][index]
        scan_rows.append(row)

    main_flux = _directional_fluxes(main.slab)
    fixed_flux = _directional_fluxes(fixed)
    continuum_rows = []
    for index, photon_energy in enumerate(energy):
        continuum_rows.append(
            {
                "photon_energy_ev": photon_energy,
                "frequency_hz": frequency[index],
                "top_incoming_fnu": main_flux["top_incoming"][index],
                "equilibrium_top_outgoing_fnu": main_flux["top_outgoing"][index],
                "equilibrium_bottom_outgoing_fnu": main_flux["bottom_outgoing"][index],
                "fixed_40000k_top_outgoing_fnu": fixed_flux["top_outgoing"][index],
                "fixed_40000k_bottom_outgoing_fnu": fixed_flux["bottom_outgoing"][index],
            }
        )

    if main.maximum_thermal_growth_rate_s1 is None:
        raise AssertionError("presentation solution lacks thermal stability analysis")
    root_fractions_with_multiple = [
        row["heating_fraction_of_zo_pericentre_flux"]
        for row in root_rows
        if int(row["sampled_root_interval_count"]) > 1
    ]
    full_heating_row = root_rows[-1]
    report = {
        "phase": "7B4f",
        "evidence_classification": {
            "L": "Stefan--Boltzmann one-face flux and the local radiative-equilibrium equation.",
            "A": "Fixed-density slab, uniform-per-depth deposition, finite temperature domain and ground-state-only cooling.",
            "V": "Root topology, depth temperature, stability matrix, energy residuals and numerical refinements.",
            "O": "Excited levels, total recombination cascades, line cooling, Compton exchange, compression work, dissipation depth and orbit coupling.",
        },
        "parameters": {
            "density_g_cm3": DENSITY_G_CM3,
            "mass_column_g_cm2": MASS_COLUMN_G_CM2,
            "radiation_temperature_k": RADIATION_TEMPERATURE_K,
            "incident_dilution": INCIDENT_DILUTION,
            "energy_domain_ev": [MINIMUM_ENERGY_EV, MAXIMUM_ENERGY_EV],
            "temperature_scan_domain_k": [
                MINIMUM_TEMPERATURE_K,
                MAXIMUM_TEMPERATURE_K,
            ],
            "presentation_frequency_base_points": PRESENTATION_FREQUENCY_POINTS,
            "presentation_frequency_points_after_edges": int(frequency.size),
            "presentation_depth_points": PRESENTATION_DEPTH_POINTS,
            "presentation_half_range_angular_order": PRESENTATION_ANGULAR_ORDER,
        },
        "zo_pericentre_heating_reference": zo_reference,
        "zero_mechanical_heating_profile": {
            "minimum_temperature_k": float(np.min(main.temperature_k)),
            "maximum_temperature_k": float(np.max(main.temperature_k)),
            "maximum_relative_local_energy_residual": (
                main.maximum_relative_local_energy_residual
            ),
            "relative_global_energy_residual": main.relative_global_energy_residual,
            "maximum_thermal_growth_rate_s1": main.maximum_thermal_growth_rate_s1,
            "thermally_stable": main.thermally_stable,
            "optimizer_function_evaluations": main.optimizer_function_evaluations,
            "population_fixed_point_residual": (
                main.slab.maximum_population_fixed_point_residual
            ),
            "boundary_energy_residual": (
                main.slab.relative_boundary_energy_balance_residual
            ),
        },
        "isothermal_temperature_scan": {
            "radiative_heating_strictly_decreases_on_sampled_grid": (
                monotonic_radiative_cooling
            ),
            "root_cases": root_rows,
            "fractions_with_multiple_sampled_roots": root_fractions_with_multiple,
            "full_zo_flux_has_no_root_in_declared_temperature_domain": bool(
                int(full_heating_row["sampled_root_interval_count"]) == 0
                and float(full_heating_row["minimum_sampled_net_heating_flux_erg_s_cm2"])
                > 0.0
            ),
            "maximum_supported_sampled_heating_fraction_at_upper_temperature_bound": float(
                -np.min(radiative_flux) / zo_flux
            ),
        },
        "profile_refinement": convergence_rows,
        "isothermal_root_refinement": root_convergence_rows,
        "stability_step_sensitivity": stability_rows,
        "scope_boundary": (
            "This is a fixed-density, externally illuminated, ground-state H/He continuum "
            "temperature-balance control. The zero-heating profile is radiative equilibrium, "
            "not a dissipative ZO atmosphere. The full-flux no-root result applies only to "
            "depositing the Phase 7B1 pericentre one-face flux inside the stated 1e-4 g cm^-2 "
            "control slab and temperature/frequency domain."
        ),
        "next_stage": (
            "Use the no-root stress test to constrain a finite deposition-column atmosphere "
            "table before replacing Phase 4; add orbit coupling only after the static energy "
            "and atomic-physics gates close."
        ),
    }

    print("[7/7] Writing tables, report and figures", flush=True)
    _write_csv(
        arguments.output_dir / "phase7b4f_temperature_profile.csv", profile_rows
    )
    _write_csv(arguments.output_dir / "phase7b4f_isothermal_scan.csv", scan_rows)
    _write_csv(
        arguments.output_dir / "phase7b4f_temperature_convergence.csv",
        convergence_rows,
    )
    _write_csv(
        arguments.output_dir / "phase7b4f_isothermal_root_convergence.csv",
        root_convergence_rows,
    )
    _write_csv(
        arguments.output_dir / "phase7b4f_stability_sensitivity.csv",
        stability_rows,
    )
    _write_csv(
        arguments.output_dir / "phase7b4f_emergent_continuum.csv",
        continuum_rows,
    )
    _plot_main(
        arguments.output_dir / "phase7b4f_temperature_balance.png",
        zo_flux,
        temperature_scan,
        radiative_flux,
        heating_curves,
        main,
        fixed,
    )
    _plot_convergence(
        arguments.output_dir / "phase7b4f_temperature_convergence.png",
        convergence_rows,
        stability_rows,
        root_rows,
    )
    with (
        arguments.output_dir / "phase7b4f_temperature_balance_report.json"
    ).open("w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
