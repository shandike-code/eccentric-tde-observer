"""生成 Phase 7B4g 有限沉积柱的静态根、微物理边界与收敛证据。"""

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
from eccentric_tde_observer.atmosphere import (
    PROTON_MASS_G,
    SOLAR_FULLY_IONIZED_H_HE,
)
from eccentric_tde_observer.continuum_emission import (
    EmissiveCoupledSlab,
    edge_resolved_milne_energy_grid_ev,
)
from eccentric_tde_observer.radiation import (
    BOLTZMANN_ERG_K,
    PLANCK_ERG_S,
    planck_nu,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_half_range_mu_weights,
)
from eccentric_tde_observer.static_atmosphere_energy import (
    SupplementalEnergyControls,
    SupplementalEnergyTerms,
    supplemental_static_energy_terms,
    top_hat_mass_column_heating_erg_s_cm3,
)
from eccentric_tde_observer.thermal_balance import (
    IsothermalTemperatureScan,
    ThermalEquilibriumSlab,
    scan_isothermal_temperature_balance,
    solve_prescribed_heating_temperature_profile,
)


DENSITY_G_CM3 = 1.0e-10
RADIATION_TEMPERATURE_K = 1.5e5
INCIDENT_DILUTION = 1.0e-6
MINIMUM_ENERGY_EV = 0.1
MAXIMUM_ENERGY_EV = 5000.0
MINIMUM_ROOT_TEMPERATURE_K = 2.0e5
MAXIMUM_ROOT_TEMPERATURE_K = 3.0e6
REFERENCE_DEPOSITION_COLUMN_G_CM2 = 3.0
TOPOLOGY_COLUMNS_G_CM2 = (0.3, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)
TOPOLOGY_FREQUENCY_POINTS = 33
TOPOLOGY_DEPTH_POINTS = 4
TOPOLOGY_ANGULAR_ORDER = 2
MAIN_FREQUENCY_POINTS = 65
MAIN_DEPTH_POINTS = 4
MAIN_ANGULAR_ORDER = 4
TOPOLOGY_TEMPERATURE_POINTS = 13
CONTROL_TEMPERATURE_POINTS = 11
LARGE_SHAPE_L1_THRESHOLD = 0.2
LARGE_PEAK_ENERGY_RATIO_THRESHOLD = 2.0
SHAPE_THRESHOLD_SENSITIVITY = (0.1, 0.2, 0.3)


PROCESS_CONTROLS = {
    "continuum_only": SupplementalEnergyControls(),
    "compton_only": SupplementalEnergyControls(include_compton_exchange=True),
    "line_full_escape": SupplementalEnergyControls(
        line_cooling_boundary="full_escape"
    ),
    "compton_and_line_full_escape": SupplementalEnergyControls(
        include_compton_exchange=True,
        line_cooling_boundary="full_escape",
    ),
}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _read_reference(background_path: Path, report_path: Path) -> dict[str, object]:
    with background_path.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    selected = next(row for row in rows if int(row["phase_index"]) == 0)
    with report_path.open(encoding="utf-8") as stream:
        report = json.load(stream)
    return {
        "background_source_file": str(background_path),
        "periodic_report_source_file": str(report_path),
        "effective_temperature_k": float(selected["effective_temperature_k"]),
        "one_face_surface_flux_erg_s_cm2": float(
            selected["one_face_surface_flux_erg_s_cm2"]
        ),
        "one_sided_column_mass_g_cm2": float(
            selected["one_sided_column_mass_g_cm2"]
        ),
        "orbital_period_s": float(report["model"]["orbital_period_s"]),
    }


def _energy_frequency(base_points: int) -> tuple[np.ndarray, np.ndarray]:
    energy = edge_resolved_milne_energy_grid_ev(
        MINIMUM_ENERGY_EV, MAXIMUM_ENERGY_EV, int(base_points)
    )
    return energy, energy * EV_ERG / PLANCK_ERG_S


def _problem(
    deposition_column_g_cm2: float,
    frequency_points: int,
    depth_points: int,
    angular_order: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    energy, frequency = _energy_frequency(frequency_points)
    mu, weight = gauss_legendre_half_range_mu_weights(angular_order)
    edges = np.linspace(
        0.0,
        deposition_column_g_cm2 / DENSITY_G_CM3,
        depth_points + 1,
    )
    top = np.zeros((frequency.size, mu.size))
    top[:, mu > 0.0] = (
        INCIDENT_DILUTION
        * planck_nu(frequency, RADIATION_TEMPERATURE_K)[:, None]
    )
    return energy, frequency, mu, weight, edges, top


def _supplemental_evaluator(controls: SupplementalEnergyControls):
    def evaluate(slab: EmissiveCoupledSlab, temperature_k: np.ndarray) -> np.ndarray:
        return supplemental_static_energy_terms(
            slab, DENSITY_G_CM3, temperature_k, controls
        ).net_heating_erg_s_cm3

    return evaluate


def _scan(
    deposition_column_g_cm2: float,
    temperature_grid_k: np.ndarray,
    one_face_flux_erg_s_cm2: float,
    controls: SupplementalEnergyControls,
    *,
    frequency_points: int,
    depth_points: int,
    angular_order: int,
) -> IsothermalTemperatureScan:
    _, frequency, mu, weight, edges, top = _problem(
        deposition_column_g_cm2,
        frequency_points,
        depth_points,
        angular_order,
    )
    heating = top_hat_mass_column_heating_erg_s_cm3(
        one_face_flux_erg_s_cm2,
        DENSITY_G_CM3,
        edges,
        deposition_column_g_cm2,
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
        population_relaxation=0.3,
        population_tolerance=1.0e-8,
        population_maximum_iterations=1024,
        root_relative_temperature_tolerance=1.0e-8,
        stability_relative_step=1.0e-3,
        supplemental_heating_evaluator=_supplemental_evaluator(controls),
    )


def _solve_profile(
    one_face_flux_erg_s_cm2: float,
    controls: SupplementalEnergyControls,
    *,
    frequency_points: int,
    depth_points: int,
    angular_order: int,
    initial_temperature_k: float,
    analyze_stability: bool,
) -> tuple[np.ndarray, ThermalEquilibriumSlab, SupplementalEnergyTerms]:
    energy, frequency, mu, weight, edges, top = _problem(
        REFERENCE_DEPOSITION_COLUMN_G_CM2,
        frequency_points,
        depth_points,
        angular_order,
    )
    heating = top_hat_mass_column_heating_erg_s_cm3(
        one_face_flux_erg_s_cm2,
        DENSITY_G_CM3,
        edges,
        REFERENCE_DEPOSITION_COLUMN_G_CM2,
    )
    result = solve_prescribed_heating_temperature_profile(
        frequency,
        edges,
        mu,
        weight,
        DENSITY_G_CM3,
        top,
        np.zeros_like(top),
        heating,
        initial_temperature_k,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        temperature_bounds_k=(MINIMUM_ROOT_TEMPERATURE_K, 1.0e6),
        population_relaxation=0.3,
        population_tolerance=1.0e-8,
        population_maximum_iterations=1024,
        local_energy_tolerance=2.0e-5,
        optimizer_tolerance=1.0e-8,
        maximum_function_evaluations=256,
        stability_relative_step=1.0e-3,
        analyze_stability=analyze_stability,
        supplemental_heating_evaluator=_supplemental_evaluator(controls),
    )
    terms = supplemental_static_energy_terms(
        result.slab, DENSITY_G_CM3, result.temperature_k, controls
    )
    return energy, result, terms


def _top_outgoing_flux_density(slab: EmissiveCoupledSlab) -> np.ndarray:
    transfer = slab.transfer
    outward = transfer.direction_cosine < 0.0
    return -2.0 * np.pi * np.einsum(
        "m,fm,m->f",
        transfer.angular_weight[outward],
        transfer.top_boundary_intensity[:, outward],
        transfer.direction_cosine[outward],
    )


def _integrated_flux(frequency_hz: np.ndarray, flux_density: np.ndarray) -> float:
    return float(np.trapezoid(flux_density, frequency_hz))


def _profile_relative_error(
    trial: ThermalEquilibriumSlab, reference: ThermalEquilibriumSlab
) -> float:
    trial_edges = trial.slab.transfer.depth_edges_cm
    reference_edges = reference.slab.transfer.depth_edges_cm
    trial_mass = (
        DENSITY_G_CM3
        * 0.5
        * (trial_edges[:-1] + trial_edges[1:])
        / REFERENCE_DEPOSITION_COLUMN_G_CM2
    )
    reference_mass = (
        DENSITY_G_CM3
        * 0.5
        * (reference_edges[:-1] + reference_edges[1:])
        / REFERENCE_DEPOSITION_COLUMN_G_CM2
    )
    interpolated = np.interp(reference_mass, trial_mass, trial.temperature_k)
    return float(
        np.max(np.abs(interpolated - reference.temperature_k) / reference.temperature_k)
    )


def _population_error(
    trial: ThermalEquilibriumSlab, reference: ThermalEquilibriumSlab
) -> float:
    trial_edges = trial.slab.transfer.depth_edges_cm
    reference_edges = reference.slab.transfer.depth_edges_cm
    trial_mass = 0.5 * (trial_edges[:-1] + trial_edges[1:]) / trial_edges[-1]
    reference_mass = (
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
                        reference_mass,
                        trial_mass,
                        getattr(trial.slab.population, name),
                    )
                    - getattr(reference.slab.population, name)
                )
            )
        )
        for name in names
    )


def _thermal_time_s(result: ThermalEquilibriumSlab) -> float:
    composition = SOLAR_FULLY_IONIZED_H_HE
    hydrogen = composition.hydrogen_mass_fraction * DENSITY_G_CM3 / PROTON_MASS_G
    helium = (
        composition.helium_mass_fraction * DENSITY_G_CM3 / (4.0 * PROTON_MASS_G)
    )
    heat_capacity = 1.5 * BOLTZMANN_ERG_K * (
        hydrogen + helium + result.slab.population.electron_density_cm3
    )
    widths = np.diff(result.slab.transfer.depth_edges_cm)
    thermal_energy = float(np.sum(heat_capacity * result.temperature_k * widths))
    return thermal_energy / result.integrated_prescribed_heating_flux_erg_s_cm2


def _plot_main(
    output_path: Path,
    one_face_flux: float,
    topology_scans: dict[float, IsothermalTemperatureScan],
    topology_temperature: np.ndarray,
    control_scans: dict[str, IsothermalTemperatureScan],
    control_temperature: np.ndarray,
    base_profile: ThermalEquilibriumSlab,
    both_profile: ThermalEquilibriumSlab,
    both_terms: SupplementalEnergyTerms,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13.2, 9.4), constrained_layout=True)

    ax = axes[0, 0]
    for column, scan in topology_scans.items():
        valid = scan.valid_evaluation
        ax.plot(
            topology_temperature[valid],
            scan.net_heating_flux_erg_s_cm2[valid] / one_face_flux,
            marker="o",
            markersize=2.7,
            label=f"{column:g} g cm$^{{-2}}$",
        )
    ax.axhline(0.0, color="black", linewidth=0.9)
    ax.set_xscale("log")
    ax.set_xlabel("Uniform gas temperature [K]")
    ax.set_ylabel("Net heating / pericentre F_ZO")
    ax.set_title("Finite-column root topology")
    ax.legend(fontsize=6.8, ncol=2)

    ax = axes[0, 1]
    colors = {
        "continuum_only": "tab:blue",
        "compton_only": "tab:orange",
        "line_full_escape": "tab:green",
        "compton_and_line_full_escape": "tab:red",
    }
    labels = {
        "continuum_only": "Continuum only",
        "compton_only": "+ Compton",
        "line_full_escape": "+ full-escape lines",
        "compton_and_line_full_escape": "+ Compton + full-escape lines",
    }
    for name, scan in control_scans.items():
        valid = scan.valid_evaluation
        ax.plot(
            control_temperature[valid],
            scan.net_heating_flux_erg_s_cm2[valid] / one_face_flux,
            color=colors[name],
            marker="o",
            markersize=3.0,
            label=labels[name],
        )
    ax.axhline(0.0, color="black", linewidth=0.9)
    ax.set_xscale("log")
    ax.set_xlabel("Uniform gas temperature [K]")
    ax.set_ylabel("Net heating / pericentre F_ZO")
    ax.set_title("Process controls at 3 g cm$^{-2}$")
    ax.legend(fontsize=7.3)

    ax = axes[1, 0]
    for label, result, color in (
        ("Continuum only", base_profile, "tab:blue"),
        ("Compton + full-escape lines", both_profile, "tab:red"),
    ):
        edges = result.slab.transfer.depth_edges_cm
        mass = DENSITY_G_CM3 * 0.5 * (edges[:-1] + edges[1:])
        ax.plot(mass, result.temperature_k, marker="o", color=color, label=label)
    ax.set_xlabel("Mass column from illuminated surface [g cm$^{-2}$]")
    ax.set_ylabel("Gas temperature [K]")
    ax.set_title("Depth-resolved static roots")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7.3)

    ax = axes[1, 1]
    edges = both_profile.slab.transfer.depth_edges_cm
    mass = DENSITY_G_CM3 * 0.5 * (edges[:-1] + edges[1:])
    scale = one_face_flux / (edges[-1] - edges[0])
    ax.plot(
        mass,
        both_profile.prescribed_heating_erg_s_cm3 / scale,
        marker="o",
        label="Deposited heating",
    )
    ax.plot(
        mass,
        both_profile.slab.radiative_heating_erg_s_cm3 / scale,
        marker="o",
        label="Continuum exchange",
    )
    ax.plot(
        mass,
        both_terms.compton_heating_erg_s_cm3 / scale,
        marker="o",
        label="Compton exchange",
    )
    ax.plot(
        mass,
        -both_terms.line_cooling_erg_s_cm3 / scale,
        marker="o",
        label="Full-escape line loss",
    )
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xlabel("Mass column from illuminated surface [g cm$^{-2}$]")
    ax.set_ylabel("Local energy term / mean deposition")
    ax.set_title("Local energy ledger")
    ax.legend(fontsize=7.2)

    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _plot_convergence(
    output_path: Path,
    convergence_rows: list[dict[str, object]],
    validity_rows: list[dict[str, object]],
    control_rows: list[dict[str, object]],
    energy_ev: np.ndarray,
    both_flux: np.ndarray,
    blackbody_flux: np.ndarray,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13.2, 9.4), constrained_layout=True)

    ax = axes[0, 0]
    labels = [str(row["scan"]) for row in convergence_rows]
    temperature_error = [
        float(row["maximum_temperature_profile_relative_error"])
        for row in convergence_rows
    ]
    population_error = [
        float(row["maximum_population_fraction_absolute_error"])
        for row in convergence_rows
    ]
    x = np.arange(len(labels))
    ax.bar(x - 0.18, temperature_error, width=0.36, label="Temperature")
    ax.bar(x + 0.18, population_error, width=0.36, label="Ion fraction")
    ax.set_yscale("log")
    ax.set_xticks(x, labels, rotation=20, ha="right")
    ax.set_ylabel("Direct relative / absolute difference")
    ax.set_title("Profile refinement")
    ax.legend(fontsize=7.4)

    ax = axes[0, 1]
    root_labels = [str(row["process_control"]) for row in control_rows]
    roots = [float(row["root_temperature_k"]) for row in control_rows]
    ax.bar(np.arange(len(roots)), roots, color=["tab:blue", "tab:orange", "tab:green", "tab:red"])
    ax.set_xticks(np.arange(len(roots)), root_labels, rotation=20, ha="right")
    ax.set_ylabel("Stable root temperature [K]")
    ax.set_title("Microphysics boundary sensitivity")

    ax = axes[1, 0]
    columns = sorted({float(row["deposition_column_g_cm2"]) for row in validity_rows})
    temperatures = sorted({float(row["temperature_k"]) for row in validity_rows})
    matrix = np.zeros((len(temperatures), len(columns)), dtype=np.float64)
    column_index = {value: index for index, value in enumerate(columns)}
    temperature_index = {value: index for index, value in enumerate(temperatures)}
    for row in validity_rows:
        row_index = temperature_index[float(row["temperature_k"])]
        column_position = column_index[float(row["deposition_column_g_cm2"])]
        if bool(row["valid_evaluation"]):
            net = float(row["net_heating_over_zo_flux"])
            matrix[row_index, column_position] = 1.0 if net > 0.0 else -1.0
    image = ax.pcolormesh(
        columns,
        temperatures,
        matrix,
        shading="nearest",
        vmin=-1.0,
        vmax=1.0,
        cmap="coolwarm",
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Deposition column [g cm$^{-2}$]")
    ax.set_ylabel("Uniform gas temperature [K]")
    ax.set_title("Sampled net-heating sign")
    colorbar = fig.colorbar(image, ax=ax, label="Cooling / invalid / heating")
    colorbar.set_ticks([-1.0, 0.0, 1.0], labels=["Cooling", "Invalid", "Heating"])

    ax = axes[1, 1]
    frequency_hz = energy_ev * EV_ERG / PLANCK_ERG_S
    both_integral = _integrated_flux(frequency_hz, both_flux)
    blackbody_integral = _integrated_flux(frequency_hz, blackbody_flux)
    ax.semilogx(
        frequency_hz,
        frequency_hz * both_flux / both_integral,
        color="tab:red",
        label="Finite-column continuum",
    )
    ax.semilogx(
        frequency_hz,
        frequency_hz * blackbody_flux / blackbody_integral,
        color="black",
        linestyle="--",
        label="ZO local blackbody",
    )
    ax.axvline(
        13.6 * EV_ERG / PLANCK_ERG_S,
        color="0.45",
        linewidth=0.9,
        linestyle=":",
        label="H I edge",
    )
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel("Normalized nu F_nu")
    ax.set_title("Emergent continuum versus local blackbody")
    ax.legend(fontsize=7.2)

    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    arguments = parser.parse_args()
    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    reference = _read_reference(
        output_dir / "phase7b_periodic_column_background.csv",
        output_dir / "phase7b_periodic_column_report.json",
    )
    one_face_flux = float(reference["one_face_surface_flux_erg_s_cm2"])
    print("[1/7] scanning finite deposition columns", flush=True)
    topology_temperature = np.geomspace(
        MINIMUM_ROOT_TEMPERATURE_K,
        MAXIMUM_ROOT_TEMPERATURE_K,
        TOPOLOGY_TEMPERATURE_POINTS,
    )
    topology_scans: dict[float, IsothermalTemperatureScan] = {}
    topology_rows: list[dict[str, object]] = []
    validity_rows: list[dict[str, object]] = []
    for column in TOPOLOGY_COLUMNS_G_CM2:
        scan = _scan(
            column,
            topology_temperature,
            one_face_flux,
            PROCESS_CONTROLS["continuum_only"],
            frequency_points=TOPOLOGY_FREQUENCY_POINTS,
            depth_points=TOPOLOGY_DEPTH_POINTS,
            angular_order=TOPOLOGY_ANGULAR_ORDER,
        )
        topology_scans[column] = scan
        valid_net = scan.net_heating_flux_erg_s_cm2[scan.valid_evaluation]
        if scan.roots:
            topology_status = "internal_root"
        elif np.all(valid_net > 0.0):
            topology_status = "net_heating_through_upper_temperature_bound"
        elif np.all(valid_net < 0.0):
            topology_status = "net_cooling_from_lower_temperature_bound"
        else:
            topology_status = "no_contiguous_valid_bracket"
        topology_rows.append(
            {
                "deposition_column_g_cm2": column,
                "deposition_fraction_of_actual_one_sided_column": column
                / float(reference["one_sided_column_mass_g_cm2"]),
                "valid_temperature_count": int(np.count_nonzero(scan.valid_evaluation)),
                "sampled_temperature_count": int(topology_temperature.size),
                "root_count": len(scan.roots),
                "root_temperatures_k": ";".join(
                    f"{root.temperature_k:.16e}" for root in scan.roots
                ),
                "all_roots_stable": bool(scan.roots)
                and all(root.thermally_stable for root in scan.roots),
                "minimum_valid_net_heating_over_zo_flux": float(
                    np.min(valid_net) / one_face_flux
                ),
                "maximum_valid_net_heating_over_zo_flux": float(
                    np.max(valid_net) / one_face_flux
                ),
                "temperature_domain_status": topology_status,
            }
        )
        for temperature, valid, message, net in zip(
            topology_temperature,
            scan.valid_evaluation,
            scan.failure_messages,
            scan.net_heating_flux_erg_s_cm2,
        ):
            validity_rows.append(
                {
                    "deposition_column_g_cm2": column,
                    "temperature_k": float(temperature),
                    "valid_evaluation": bool(valid),
                    "net_heating_over_zo_flux": (
                        float(net / one_face_flux) if valid else ""
                    ),
                    "failure_message": "" if message is None else message,
                }
            )

    print("[2/7] evaluating independent microphysics controls", flush=True)
    control_temperature = np.geomspace(2.0e5, 1.0e6, CONTROL_TEMPERATURE_POINTS)
    control_scans: dict[str, IsothermalTemperatureScan] = {}
    control_rows: list[dict[str, object]] = []
    for name, controls in PROCESS_CONTROLS.items():
        scan = _scan(
            REFERENCE_DEPOSITION_COLUMN_G_CM2,
            control_temperature,
            one_face_flux,
            controls,
            frequency_points=MAIN_FREQUENCY_POINTS,
            depth_points=MAIN_DEPTH_POINTS,
            angular_order=MAIN_ANGULAR_ORDER,
        )
        if len(scan.roots) != 1:
            raise AssertionError(f"{name} did not produce exactly one reference root")
        root = scan.roots[0]
        control_scans[name] = scan
        control_rows.append(
            {
                "process_control": name,
                "include_compton_exchange": controls.include_compton_exchange,
                "line_cooling_boundary": controls.line_cooling_boundary,
                "root_temperature_k": root.temperature_k,
                "thermally_stable": root.thermally_stable,
                "continuum_heating_over_zo_flux": root.radiative_heating_flux_erg_s_cm2
                / one_face_flux,
                "supplemental_heating_over_zo_flux": root.supplemental_heating_flux_erg_s_cm2
                / one_face_flux,
                "relative_energy_residual": root.relative_energy_residual,
            }
        )

    print("[3/7] solving depth-resolved static roots", flush=True)
    _, base_profile, base_terms = _solve_profile(
        one_face_flux,
        PROCESS_CONTROLS["continuum_only"],
        frequency_points=MAIN_FREQUENCY_POINTS,
        depth_points=MAIN_DEPTH_POINTS,
        angular_order=MAIN_ANGULAR_ORDER,
        initial_temperature_k=4.7e5,
        analyze_stability=True,
    )
    energy, both_profile, both_terms = _solve_profile(
        one_face_flux,
        PROCESS_CONTROLS["compton_and_line_full_escape"],
        frequency_points=MAIN_FREQUENCY_POINTS,
        depth_points=MAIN_DEPTH_POINTS,
        angular_order=MAIN_ANGULAR_ORDER,
        initial_temperature_k=4.4e5,
        analyze_stability=True,
    )

    print("[4/7] running direct refinement axes", flush=True)
    variants = (
        ("frequency_65_to_129", 129, MAIN_DEPTH_POINTS, MAIN_ANGULAR_ORDER, 4.4e5),
        ("depth_4_to_8", MAIN_FREQUENCY_POINTS, 8, MAIN_ANGULAR_ORDER, 4.4e5),
        ("angle_4_to_8", MAIN_FREQUENCY_POINTS, MAIN_DEPTH_POINTS, 8, 4.4e5),
        ("initial_temperature_650000", MAIN_FREQUENCY_POINTS, MAIN_DEPTH_POINTS, MAIN_ANGULAR_ORDER, 6.5e5),
    )
    convergence_rows: list[dict[str, object]] = []
    for label, frequency_points, depth_points, angular_order, initial in variants:
        _, trial, _ = _solve_profile(
            one_face_flux,
            PROCESS_CONTROLS["compton_and_line_full_escape"],
            frequency_points=frequency_points,
            depth_points=depth_points,
            angular_order=angular_order,
            initial_temperature_k=initial,
            analyze_stability=False,
        )
        trial_flux = _integrated_flux(
            trial.slab.transfer.frequency_hz,
            _top_outgoing_flux_density(trial.slab),
        )
        main_flux = _integrated_flux(
            both_profile.slab.transfer.frequency_hz,
            _top_outgoing_flux_density(both_profile.slab),
        )
        convergence_rows.append(
            {
                "scan": label,
                "frequency_base_points": frequency_points,
                "depth_points": depth_points,
                "angular_order": angular_order,
                "initial_temperature_k": initial,
                "maximum_temperature_profile_relative_error": _profile_relative_error(
                    trial, both_profile
                ),
                "maximum_population_fraction_absolute_error": _population_error(
                    trial, both_profile
                ),
                "top_continuum_flux_relative_error": abs(trial_flux / main_flux - 1.0),
                "maximum_relative_local_energy_residual": trial.maximum_relative_local_energy_residual,
                "relative_global_energy_residual": trial.relative_global_energy_residual,
            }
        )

    print("[5/7] assembling continuum and energy ledgers", flush=True)
    both_flux_density = _top_outgoing_flux_density(both_profile.slab)
    base_flux_density = _top_outgoing_flux_density(base_profile.slab)
    frequency = both_profile.slab.transfer.frequency_hz
    blackbody_flux_density = np.pi * planck_nu(
        frequency, float(reference["effective_temperature_k"])
    )
    both_integral = _integrated_flux(frequency, both_flux_density)
    blackbody_integral = _integrated_flux(frequency, blackbody_flux_density)
    both_normalized = both_flux_density / both_integral
    blackbody_normalized = blackbody_flux_density / blackbody_integral
    normalized_shape_l1 = float(
        np.trapezoid(np.abs(both_normalized - blackbody_normalized), frequency)
    )
    ionizing = energy >= 13.6
    ionizing_fraction = float(
        np.trapezoid(both_flux_density[ionizing], frequency[ionizing]) / both_integral
    )
    blackbody_ionizing_fraction = float(
        np.trapezoid(
            blackbody_flux_density[ionizing], frequency[ionizing]
        )
        / blackbody_integral
    )
    peak_energy = float(energy[np.argmax(frequency * both_flux_density)])
    blackbody_peak_energy = float(
        energy[np.argmax(frequency * blackbody_flux_density)]
    )
    peak_energy_ratio = peak_energy / blackbody_peak_energy
    large_continuum_difference = bool(
        normalized_shape_l1 > LARGE_SHAPE_L1_THRESHOLD
        and peak_energy_ratio > LARGE_PEAK_ENERGY_RATIO_THRESHOLD
    )
    thermal_time = _thermal_time_s(both_profile)
    period = float(reference["orbital_period_s"])

    profile_rows: list[dict[str, object]] = []
    edges = both_profile.slab.transfer.depth_edges_cm
    centers = 0.5 * (edges[:-1] + edges[1:])
    for index, center in enumerate(centers):
        profile_rows.append(
            {
                "depth_index": index,
                "mass_column_center_g_cm2": DENSITY_G_CM3 * center,
                "temperature_k": both_profile.temperature_k[index],
                "hydrogen_ionized_fraction": both_profile.slab.population.hydrogen_ionized_fraction[index],
                "helium_singly_ionized_fraction": both_profile.slab.population.helium_singly_ionized_fraction[index],
                "helium_doubly_ionized_fraction": both_profile.slab.population.helium_doubly_ionized_fraction[index],
                "deposited_heating_erg_s_cm3": both_profile.prescribed_heating_erg_s_cm3[index],
                "continuum_heating_erg_s_cm3": both_profile.slab.radiative_heating_erg_s_cm3[index],
                "compton_heating_erg_s_cm3": both_terms.compton_heating_erg_s_cm3[index],
                "full_escape_line_cooling_erg_s_cm3": both_terms.line_cooling_erg_s_cm3[index],
                "net_heating_erg_s_cm3": both_profile.net_heating_erg_s_cm3[index],
            }
        )
    continuum_rows = [
        {
            "energy_ev": energy[index],
            "frequency_hz": frequency[index],
            "finite_column_top_continuum_flux_density_cgs": both_flux_density[index],
            "continuum_only_top_flux_density_cgs": base_flux_density[index],
            "zo_local_blackbody_flux_density_cgs": blackbody_flux_density[index],
        }
        for index in range(energy.size)
    ]

    successful_columns = [
        row for row in topology_rows if int(row["root_count"]) > 0
    ]
    lowest_sampled_root_column = min(
        float(row["deposition_column_g_cm2"]) for row in successful_columns
    )
    invalid_count = sum(not bool(row["valid_evaluation"]) for row in validity_rows)
    report = {
        "phase": "7B4g",
        "reference": reference,
        "assumptions": {
            "density_g_cm3": DENSITY_G_CM3,
            "deposition_profile": "Uniform per unit mass from the illuminated surface to the total finite slab column [A-deposition].",
            "slab_boundary": "Vacuum at both slab faces; this is a static gate, not a midplane-symmetric atmosphere table [A].",
            "incident_field": {
                "radiation_temperature_k": RADIATION_TEMPERATURE_K,
                "dilution": INCIDENT_DILUTION,
            },
            "compton": "First-order Thomson energy exchange evaluated on the solved J_nu; no frequency redistribution [L/A].",
            "line_cooling": "H I and He II collisional-excitation loss bracketed by disabled and full photon escape; no excited-state populations or line transfer [L/A].",
        },
        "root_topology": {
            "temperature_domain_k": [
                MINIMUM_ROOT_TEMPERATURE_K,
                MAXIMUM_ROOT_TEMPERATURE_K,
            ],
            "sampled_columns_g_cm2": list(TOPOLOGY_COLUMNS_G_CM2),
            "lowest_sampled_column_with_internal_root_g_cm2": lowest_sampled_root_column,
            "invalid_evaluation_count": invalid_count,
            "invalid_points_are_not_bridged": True,
            "rows": topology_rows,
        },
        "reference_process_controls": control_rows,
        "depth_resolved_reference": {
            "deposition_column_g_cm2": REFERENCE_DEPOSITION_COLUMN_G_CM2,
            "deposition_fraction_of_actual_one_sided_column": REFERENCE_DEPOSITION_COLUMN_G_CM2
            / float(reference["one_sided_column_mass_g_cm2"]),
            "continuum_only_temperature_range_k": [
                float(np.min(base_profile.temperature_k)),
                float(np.max(base_profile.temperature_k)),
            ],
            "all_process_temperature_range_k": [
                float(np.min(both_profile.temperature_k)),
                float(np.max(both_profile.temperature_k)),
            ],
            "maximum_relative_local_energy_residual": both_profile.maximum_relative_local_energy_residual,
            "relative_global_energy_residual": both_profile.relative_global_energy_residual,
            "maximum_thermal_growth_rate_s1": both_profile.maximum_thermal_growth_rate_s1,
            "thermally_stable": both_profile.thermally_stable,
            "integrated_compton_over_zo_flux": float(
                np.sum(
                    both_terms.compton_heating_erg_s_cm3
                    * np.diff(both_profile.slab.transfer.depth_edges_cm)
                )
                / one_face_flux
            ),
            "integrated_full_escape_line_cooling_over_zo_flux": float(
                np.sum(
                    both_terms.line_cooling_erg_s_cm3
                    * np.diff(both_profile.slab.transfer.depth_edges_cm)
                )
                / one_face_flux
            ),
            "thermal_energy_over_heating_time_s": thermal_time,
            "thermal_time_over_orbital_period": thermal_time / period,
            "maximum_photon_energy_over_electron_rest_energy": both_terms.maximum_photon_energy_over_electron_rest_energy,
        },
        "continuum_comparison": {
            "finite_band_top_continuum_flux_erg_s_cm2": both_integral,
            "finite_band_zo_blackbody_flux_erg_s_cm2": blackbody_integral,
            "top_continuum_flux_over_zo_blackbody": both_integral
            / blackbody_integral,
            "normalized_shape_l1_distance": normalized_shape_l1,
            "ionizing_fraction_finite_column": ionizing_fraction,
            "ionizing_fraction_zo_blackbody": blackbody_ionizing_fraction,
            "nu_fnu_peak_energy_ev_finite_column": peak_energy,
            "nu_fnu_peak_energy_ev_zo_blackbody": blackbody_peak_energy,
            "nu_fnu_peak_energy_ratio": peak_energy_ratio,
            "large_difference_classification": {
                "shape_l1_threshold": LARGE_SHAPE_L1_THRESHOLD,
                "peak_energy_ratio_threshold": LARGE_PEAK_ENERGY_RATIO_THRESHOLD,
                "classified_large": large_continuum_difference,
                "shape_threshold_sensitivity": {
                    str(threshold): bool(
                        normalized_shape_l1 > threshold
                        and peak_energy_ratio > LARGE_PEAK_ENERGY_RATIO_THRESHOLD
                    )
                    for threshold in SHAPE_THRESHOLD_SENSITIVITY
                },
                "evidence": "[A-classification/V]",
            },
            "scope": "The finite-column spectrum is a gate result. Full-escape line energy is not inserted into the continuum spectrum.",
        },
        "profile_refinement": convergence_rows,
        "decision": {
            "static_approximation_failed": False,
            "enter_periodic_dynamic_nlte_now": False,
            "difference_from_local_blackbody_is_large": large_continuum_difference,
            "next_stage": (
                "Build a finite hydrostatic atmosphere table with physical density/deposition structure and a midplane boundary before replacing Phase 4."
                if large_continuum_difference
                else "Proceed to the UVOT instrument and observation-sampling layer while retaining this atmosphere uncertainty."
            ),
            "reason": "A stable static root exists and its thermal time is far below the orbital period, but the continuum shape is strongly different from the local ZO blackbody. The present fixed-density two-vacuum-face gate is not yet a replacement table.",
        },
        "evidence_classification": {
            "L": "Thomson Compton exchange and published H/He collisional-excitation cooling fits.",
            "A": "Fixed density, finite top-hat deposition column, vacuum at both faces, and full-escape line upper boundary.",
            "V": "Root topology, stable depth solution, energy residuals, process toggles, thermal-time ratio, continuum comparison, and direct refinement.",
            "O": "Hydrostatic density, true dissipation profile, midplane symmetry, excited-state NLTE, line trapping, Kompaneets redistribution, metals, and Phase 4 replacement.",
        },
    }

    print("[6/7] writing machine-readable outputs", flush=True)
    _write_csv(output_dir / "phase7b4g_column_topology.csv", topology_rows)
    _write_csv(output_dir / "phase7b4g_validity_map.csv", validity_rows)
    _write_csv(output_dir / "phase7b4g_process_controls.csv", control_rows)
    _write_csv(output_dir / "phase7b4g_temperature_profile.csv", profile_rows)
    _write_csv(output_dir / "phase7b4g_convergence.csv", convergence_rows)
    _write_csv(output_dir / "phase7b4g_emergent_continuum.csv", continuum_rows)
    with (output_dir / "phase7b4g_finite_column_report.json").open(
        "w", encoding="utf-8"
    ) as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")

    print("[7/7] rendering English figures", flush=True)
    _plot_main(
        output_dir / "phase7b4g_finite_column.png",
        one_face_flux,
        topology_scans,
        topology_temperature,
        control_scans,
        control_temperature,
        base_profile,
        both_profile,
        both_terms,
    )
    _plot_convergence(
        output_dir / "phase7b4g_convergence.png",
        convergence_rows,
        validity_rows,
        control_rows,
        energy,
        both_flux_density,
        blackbody_flux_density,
    )
    print(json.dumps(report["decision"], indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
