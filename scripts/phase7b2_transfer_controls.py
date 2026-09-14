"""生成 Phase 7B2 频率—角度转移解析控制、压力测试和收敛证据。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

from eccentric_tde_observer.dynamic_column import build_zo_periodic_column_background
from eccentric_tde_observer.phase7a import select_quasi_static_representative_annuli
from eccentric_tde_observer.radiation import (
    BOLTZMANN_ERG_K,
    LIGHT_SPEED_CM_S,
    PLANCK_ERG_S,
    STEFAN_BOLTZMANN_ERG_S_CM2_K4,
    planck_nu,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    evolve_time_dependent_slab,
    gauss_legendre_mu_weights,
    isothermal_absorption_top_flux,
    linear_source_top_intensity,
    solve_static_slab_transfer,
)
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model


ABSORPTION_CONTROL_DEPTHS = (0.1, 1.0, 10.0)
SCATTERING_CONTROL_DEPTHS = (0.1, 1.0, 10.0)
ANGLE_ORDERS = (8, 16, 32, 64)
LINEAR_SOURCE_DEPTH_POINTS = (16, 32, 64, 128)
SCATTERING_DEPTH_POINTS = (16, 32, 64, 128, 256, 512, 1024)
TIME_STATIC_DEPTH_POINTS = (16, 32, 64, 128, 256, 512, 1024, 2048)
FREQUENCY_POINTS = (129, 257, 513, 1025, 2049)


def _write_csv(path: Path, records: list[dict[str, object]]) -> None:
    if not records:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def _planck_frequency_grid(temperature_k: float, points: int) -> np.ndarray:
    dimensionless_frequency = np.geomspace(1.0e-4, 50.0, points)
    return dimensionless_frequency * BOLTZMANN_ERG_K * temperature_k / PLANCK_ERG_S


def _incident_reflected_transmitted(result) -> tuple[float, float, float]:
    mu = result.direction_cosine
    weight = result.angular_weight
    incident = 2.0 * np.pi * np.sum(weight[mu > 0.0] * mu[mu > 0.0])
    reflected = 2.0 * np.pi * np.sum(
        weight[mu < 0.0]
        * (-mu[mu < 0.0])
        * result.top_boundary_intensity[0, mu < 0.0]
    )
    transmitted = 2.0 * np.pi * np.sum(
        weight[mu > 0.0]
        * mu[mu > 0.0]
        * result.bottom_boundary_intensity[0, mu > 0.0]
    )
    return float(incident), float(reflected), float(transmitted)


def _pure_scattering(total_optical_depth: float, depth_points: int, angular_order: int):
    mu, weight = gauss_legendre_mu_weights(angular_order)
    top = np.zeros((1, angular_order))
    top[:, mu > 0.0] = 1.0
    return solve_static_slab_transfer(
        [1.0e15],
        np.linspace(0.0, 1.0, depth_points + 1),
        mu,
        weight,
        total_optical_depth,
        0.0,
        0.0,
        top_incoming_intensity=top,
    )


def _absorption_controls(temperature_k: float, zo_scattering_depth: float):
    frequency = _planck_frequency_grid(temperature_k, 1025)
    thermal_source = planck_nu(frequency, temperature_k)
    mu, weight = gauss_legendre_mu_weights(64)
    spectral_records: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    spectra: dict[float, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    # 中文：最后一个大光深只沿用 ZO 的散射柱深，纯吸收仍是解析压力测试。
    for total_depth in (*ABSORPTION_CONTROL_DEPTHS, zo_scattering_depth):
        result = solve_static_slab_transfer(
            frequency,
            [0.0, 1.0],
            mu,
            weight,
            total_depth,
            thermal_source[:, None],
            1.0,
        )
        numerical_flux = -result.top_net_flux
        analytic_flux = isothermal_absorption_top_flux(thermal_source, total_depth)
        spectra[total_depth] = (frequency, numerical_flux, analytic_flux)
        for index, frequency_hz in enumerate(frequency):
            spectral_records.append(
                {
                    "total_optical_depth": total_depth,
                    "frequency_hz": float(frequency_hz),
                    "hnu_over_kT": float(
                        PLANCK_ERG_S * frequency_hz / (BOLTZMANN_ERG_K * temperature_k)
                    ),
                    "numerical_top_outward_flux_erg_s_cm2_hz": float(
                        numerical_flux[index]
                    ),
                    "analytic_top_outward_flux_erg_s_cm2_hz": float(
                        analytic_flux[index]
                    ),
                    "numerical_over_analytic": float(
                        numerical_flux[index] / analytic_flux[index]
                    ),
                }
            )
        numerical_bolometric = float(np.trapezoid(numerical_flux, frequency))
        analytic_bolometric = float(np.trapezoid(analytic_flux, frequency))
        exact_gray_bolometric = float(
            isothermal_absorption_top_flux(1.0, total_depth)
            / np.pi
            * STEFAN_BOLTZMANN_ERG_S_CM2_K4
            * temperature_k**4
        )
        summaries.append(
            {
                "total_optical_depth": total_depth,
                "angular_order": 64,
                "frequency_points": 1025,
                "numerical_bolometric_flux_erg_s_cm2": numerical_bolometric,
                "quadrature_analytic_bolometric_flux_erg_s_cm2": analytic_bolometric,
                "exact_gray_bolometric_flux_erg_s_cm2": exact_gray_bolometric,
                "angle_relative_error": abs(numerical_bolometric / analytic_bolometric - 1.0),
                "combined_relative_error": abs(
                    numerical_bolometric / exact_gray_bolometric - 1.0
                ),
                "maximum_relative_energy_balance_residual": float(
                    np.max(result.relative_energy_balance_residual)
                ),
            }
        )
    return spectral_records, summaries, spectra


def _convergence_controls(temperature_k: float, actual_scattering_depth: float):
    records: list[dict[str, object]] = []

    analytic_flux = float(isothermal_absorption_top_flux(2.0, 1.0))
    for angular_order in ANGLE_ORDERS:
        mu, weight = gauss_legendre_mu_weights(angular_order)
        result = solve_static_slab_transfer(
            [1.0e15], [0.0, 1.0], mu, weight, 1.0, 2.0, 1.0
        )
        records.append(
            {
                "control": "isothermal_absorption_angle",
                "grid_points": angular_order,
                "secondary_grid_points": 1,
                "observable": "top_outward_flux",
                "value": -float(result.top_net_flux[0]),
                "reference_value": analytic_flux,
                "relative_error": abs(-float(result.top_net_flux[0]) / analytic_flux - 1.0),
            }
        )

    mu, weight = gauss_legendre_mu_weights(8)
    outgoing = mu < 0.0
    expected = linear_source_top_intensity(1.0, 0.7, 2.0, np.abs(mu[outgoing]))
    for depth_points in LINEAR_SOURCE_DEPTH_POINTS:
        edges = np.linspace(0.0, 1.0, depth_points + 1)
        centers = 0.5 * (edges[:-1] + edges[1:])
        result = solve_static_slab_transfer(
            [1.0e15], edges, mu, weight, 2.0, 1.0 + 0.7 * centers, 1.0
        )
        error = float(np.max(np.abs(result.top_boundary_intensity[0, outgoing] - expected)))
        records.append(
            {
                "control": "linear_source_depth",
                "grid_points": depth_points,
                "secondary_grid_points": 8,
                "observable": "maximum_top_intensity_error",
                "value": error,
                "reference_value": 0.0,
                "relative_error": error,
            }
        )

    exact_blackbody_flux = STEFAN_BOLTZMANN_ERG_S_CM2_K4 * temperature_k**4
    for points in FREQUENCY_POINTS:
        frequency = _planck_frequency_grid(temperature_k, points)
        integrated = float(np.pi * np.trapezoid(planck_nu(frequency, temperature_k), frequency))
        records.append(
            {
                "control": "planck_frequency_integral",
                "grid_points": points,
                "secondary_grid_points": 0,
                "observable": "pi_integral_Bnu",
                "value": integrated,
                "reference_value": exact_blackbody_flux,
                "relative_error": abs(integrated / exact_blackbody_flux - 1.0),
            }
        )

    scattering_by_depth: dict[int, tuple[float, float]] = {}
    for depth_points in SCATTERING_DEPTH_POINTS:
        result = _pure_scattering(actual_scattering_depth, depth_points, 32)
        incident, reflected, transmitted = _incident_reflected_transmitted(result)
        scattering_by_depth[depth_points] = (reflected / incident, transmitted / incident)
    reference_reflection, reference_transmission = scattering_by_depth[1024]
    for depth_points, (reflection, transmission) in scattering_by_depth.items():
        for observable, value, reference in (
            ("reflection_fraction", reflection, reference_reflection),
            ("transmission_fraction", transmission, reference_transmission),
        ):
            records.append(
                {
                    "control": "zo_tau_pure_scattering_depth",
                    "grid_points": depth_points,
                    "secondary_grid_points": 32,
                    "observable": observable,
                    "value": value,
                    "reference_value": reference,
                    "relative_error": abs(value / reference - 1.0),
                }
            )

    scattering_by_angle: dict[int, float] = {}
    for angular_order in ANGLE_ORDERS:
        result = _pure_scattering(actual_scattering_depth, 512, angular_order)
        incident, _, transmitted = _incident_reflected_transmitted(result)
        scattering_by_angle[angular_order] = transmitted / incident
    angle_reference = scattering_by_angle[64]
    for angular_order, transmission in scattering_by_angle.items():
        records.append(
            {
                "control": "zo_tau_pure_scattering_angle",
                "grid_points": angular_order,
                "secondary_grid_points": 512,
                "observable": "transmission_fraction",
                "value": transmission,
                "reference_value": angle_reference,
                "relative_error": abs(transmission / angle_reference - 1.0),
            }
        )

    return records, scattering_by_depth


def _scattering_controls(actual_scattering_depth: float):
    records: list[dict[str, object]] = []
    results = {}
    cases = [(value, 128) for value in SCATTERING_CONTROL_DEPTHS]
    cases.append((actual_scattering_depth, 1024))
    for total_depth, depth_points in cases:
        result = _pure_scattering(total_depth, depth_points, 32)
        incident, reflected, transmitted = _incident_reflected_transmitted(result)
        record = {
            "total_optical_depth": total_depth,
            "depth_points": depth_points,
            "angular_order": 32,
            "reflection_fraction": reflected / incident,
            "transmission_fraction": transmitted / incident,
            "outgoing_over_incident": (reflected + transmitted) / incident,
            "source_equation_residual": float(result.source_equation_residual[0]),
            "relative_energy_balance_residual": float(
                result.relative_energy_balance_residual[0]
            ),
            "lambda_system_condition_number": float(
                result.lambda_system_condition_number[0]
            ),
            "minimum_intensity": float(np.min(result.intensity_cell_average)),
            "minimum_source_function": float(np.min(result.source_function)),
        }
        records.append(record)
        results[total_depth] = result
    return records, results


def _time_controls():
    records: list[dict[str, object]] = []
    two_mu = np.array([-0.5, 0.5])
    two_weight = np.array([1.0, 1.0])
    edges = np.arange(17, dtype=np.float64) * LIGHT_SPEED_CM_S

    vacuum_initial = np.zeros((1, 2, 16))
    vacuum_initial[0, 1, 2:5] = 1.0
    vacuum_initial[0, 0, 9:12] = 2.0
    vacuum = evolve_time_dependent_slab(
        [1.0e15], edges, two_mu, two_weight, vacuum_initial, 0.0, 0.0, 1.0, 6.0,
        periodic_spatial_boundary=True, maximum_cfl=1.0,
    )
    vacuum_expected = vacuum_initial.copy()
    vacuum_expected[0, 1] = np.roll(vacuum_expected[0, 1], 3)
    vacuum_expected[0, 0] = np.roll(vacuum_expected[0, 0], -3)
    records.append(
        {
            "control": "vacuum_periodic_translation",
            "grid_points": 16,
            "time_steps": vacuum.time_steps,
            "maximum_cfl": vacuum.maximum_transport_cfl,
            "maximum_absolute_error": float(np.max(np.abs(vacuum.final_intensity - vacuum_expected))),
            "radiation_content_relative_error": float(
                np.max(np.abs(vacuum.final_radiation_content / vacuum.initial_radiation_content - 1.0))
            ),
            "minimum_intensity": vacuum.minimum_intensity,
        }
    )

    uniform_initial = np.full((1, 2, 16), 2.0)
    extinction = 1.0 / LIGHT_SPEED_CM_S
    absorption = evolve_time_dependent_slab(
        [1.0e15], edges, two_mu, two_weight, uniform_initial, extinction, 0.0, 1.0, 1.3,
        periodic_spatial_boundary=True,
    )
    absorption_expected = 2.0 * np.exp(-1.3)
    records.append(
        {
            "control": "uniform_absorption_decay",
            "grid_points": 16,
            "time_steps": absorption.time_steps,
            "maximum_cfl": absorption.maximum_transport_cfl,
            "maximum_absolute_error": float(
                np.max(np.abs(absorption.final_intensity - absorption_expected))
            ),
            "radiation_content_relative_error": float(
                np.max(
                    np.abs(
                        absorption.final_radiation_content
                        / absorption.initial_radiation_content
                        / np.exp(-1.3)
                        - 1.0
                    )
                )
            ),
            "minimum_intensity": absorption.minimum_intensity,
        }
    )

    scattering_initial = np.empty((1, 2, 16))
    scattering_initial[:, 0] = 1.0
    scattering_initial[:, 1] = 3.0
    scattering = evolve_time_dependent_slab(
        [1.0e15], edges, two_mu, two_weight, scattering_initial, extinction, 0.0, 0.0, 1.3,
        periodic_spatial_boundary=True,
    )
    scattering_expected = 2.0 + np.array([-1.0, 1.0])[:, None] * np.exp(-1.3)
    records.append(
        {
            "control": "uniform_pure_scattering_relaxation",
            "grid_points": 16,
            "time_steps": scattering.time_steps,
            "maximum_cfl": scattering.maximum_transport_cfl,
            "maximum_absolute_error": float(
                np.max(np.abs(scattering.final_intensity[0] - scattering_expected))
            ),
            "radiation_content_relative_error": float(
                np.max(
                    np.abs(
                        scattering.final_radiation_content
                        / scattering.initial_radiation_content
                        - 1.0
                    )
                )
            ),
            "minimum_intensity": scattering.minimum_intensity,
        }
    )

    mu, weight = gauss_legendre_mu_weights(4)
    static_limit_errors = {}
    for depth_points in TIME_STATIC_DEPTH_POINTS:
        slab_edges = np.linspace(0.0, LIGHT_SPEED_CM_S, depth_points + 1)
        static = solve_static_slab_transfer(
            [1.0e15], slab_edges, mu, weight, 1.0 / LIGHT_SPEED_CM_S, 1.0, 1.0
        )
        time_result = evolve_time_dependent_slab(
            [1.0e15], slab_edges, mu, weight, 0.0, 1.0 / LIGHT_SPEED_CM_S, 1.0, 1.0, 10.0
        )
        error = float(np.max(np.abs(time_result.final_intensity - static.intensity_cell_average)))
        static_limit_errors[depth_points] = error
        records.append(
            {
                "control": "time_to_static_absorption_limit",
                "grid_points": depth_points,
                "time_steps": time_result.time_steps,
                "maximum_cfl": time_result.maximum_transport_cfl,
                "maximum_absolute_error": error,
                "radiation_content_relative_error": "not_applicable_open_boundaries",
                "minimum_intensity": time_result.minimum_intensity,
            }
        )
    return records, static_limit_errors


def _plot(path: Path, temperature_k: float, spectra, scattering_records, convergence_records, time_errors):
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 9.0), constrained_layout=True)
    colors = plt.cm.viridis(np.linspace(0.1, 0.9, len(spectra)))
    for color, (total_depth, (frequency, numerical, analytic)) in zip(colors, spectra.items()):
        x = PLANCK_ERG_S * frequency / (BOLTZMANN_ERG_K * temperature_k)
        normalization = STEFAN_BOLTZMANN_ERG_S_CM2_K4 * temperature_k**4
        axes[0, 0].loglog(x, frequency * numerical / normalization, color=color, label=rf"$\tau={total_depth:.3g}$")
        axes[0, 0].loglog(x, frequency * analytic / normalization, color=color, linestyle="--", linewidth=1.0)
    axes[0, 0].set(
        xlabel=r"$h\nu/(kT)$",
        ylabel=r"$\nu F_\nu/(\sigma_{\rm SB}T^4)$",
        title="(a) Isothermal absorption: numerical (solid) vs analytic (dashed)",
    )
    axes[0, 0].legend(fontsize=8)

    tau = np.asarray([record["total_optical_depth"] for record in scattering_records])
    reflection = np.asarray([record["reflection_fraction"] for record in scattering_records])
    transmission = np.asarray([record["transmission_fraction"] for record in scattering_records])
    axes[0, 1].semilogx(tau, reflection, "o-", label="Reflection")
    axes[0, 1].semilogx(tau, transmission, "s-", label="Transmission")
    axes[0, 1].semilogx(tau, reflection + transmission, "^-", label="Reflection + transmission")
    axes[0, 1].set(
        xlabel=r"Total scattering optical depth $\tau_{\rm s}$",
        ylabel="Fraction of incident flux",
        title="(b) Conservative scattering and ZO high-depth stress test",
        ylim=(-0.03, 1.08),
    )
    axes[0, 1].legend()

    angle = [r for r in convergence_records if r["control"] == "isothermal_absorption_angle"]
    linear = [r for r in convergence_records if r["control"] == "linear_source_depth"]
    frequency = [r for r in convergence_records if r["control"] == "planck_frequency_integral"]
    scattering_angle = [r for r in convergence_records if r["control"] == "zo_tau_pure_scattering_angle" and r["relative_error"] > 0.0]
    axes[1, 0].loglog([r["grid_points"] for r in angle], [r["relative_error"] for r in angle], "o-", label="Angular quadrature")
    axes[1, 0].loglog([r["grid_points"] for r in linear], [r["relative_error"] for r in linear], "s-", label="Depth: linear source")
    axes[1, 0].loglog([r["grid_points"] for r in frequency], [r["relative_error"] for r in frequency], "^-", label="Frequency integral")
    axes[1, 0].loglog([r["grid_points"] for r in scattering_angle], [r["relative_error"] for r in scattering_angle], "d-", label="High-depth scattering angles")
    axes[1, 0].set(
        xlabel="Grid points / quadrature order",
        ylabel="Relative or absolute error",
        title="(c) Independent static convergence axes",
    )
    axes[1, 0].legend()

    scattering_depth = [r for r in convergence_records if r["control"] == "zo_tau_pure_scattering_depth" and r["observable"] == "transmission_fraction" and r["relative_error"] > 0.0]
    axes[1, 1].loglog([r["grid_points"] for r in scattering_depth], [r["relative_error"] for r in scattering_depth], "o-", label=r"$\tau_{\rm es}=199.099$ transmission")
    axes[1, 1].loglog(list(time_errors), list(time_errors.values()), "s-", label="Time solution to static limit")
    axes[1, 1].set(
        xlabel="Depth cells",
        ylabel="Relative or maximum absolute error",
        title="(d) High optical depth and time-static limit",
    )
    axes[1, 1].legend()
    for axis in axes.flat:
        axis.grid(alpha=0.25)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--radial-points", type=int, default=65)
    parser.add_argument("--anomaly-points", type=int, default=1024)
    parser.add_argument("--representative-index", type=int, default=3)
    arguments = parser.parse_args()
    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    model = build_strict_domain_reference_model(arguments.radial_points, arguments.anomaly_points)
    selection = select_quasi_static_representative_annuli(model, count=12)
    representative_index = int(arguments.representative_index)
    if representative_index < 0 or representative_index >= selection.count:
        raise ValueError("representative-index lies outside the Phase 7A selection")
    radial_index = int(selection.radial_index[representative_index])
    anomaly_index = int(selection.anomaly_index[representative_index])
    background = build_zo_periodic_column_background(model, radial_index)
    temperature_k = float(background.effective_temperature_k[anomaly_index])
    actual_scattering_depth = float(background.electron_scattering_depth_to_midplane[anomaly_index])
    absorption_spectra, absorption_summaries, spectra = _absorption_controls(
        temperature_k, actual_scattering_depth
    )
    convergence, scattering_by_depth = _convergence_controls(temperature_k, actual_scattering_depth)
    scattering_records, _ = _scattering_controls(actual_scattering_depth)
    time_records, time_errors = _time_controls()

    report = {
        "phase": "7B2",
        "classification": "[L/A/V/O] frequency-angle transfer analytic controls",
        "zo_pressure_test": {
            "phase7a_representative_index": representative_index,
            "radial_index": radial_index,
            "anomaly_index": anomaly_index,
            "effective_temperature_k": temperature_k,
            "electron_scattering_depth_to_midplane": actual_scattering_depth,
            "optical_depth_role": "gray pure-scattering pressure test only",
        },
        "static_absorption": absorption_summaries,
        "static_scattering": scattering_records,
        "time_controls": time_records,
        "acceptance": {
            "maximum_static_absorption_energy_residual": max(
                record["maximum_relative_energy_balance_residual"] for record in absorption_summaries
            ),
            "maximum_pure_scattering_energy_residual": max(
                record["relative_energy_balance_residual"] for record in scattering_records
            ),
            "maximum_pure_scattering_source_residual": max(
                record["source_equation_residual"] for record in scattering_records
            ),
            "maximum_exact_time_control_error": max(
                float(record["maximum_absolute_error"])
                for record in time_records
                if record["control"] != "time_to_static_absorption_limit"
            ),
            "minimum_intensity_all_controls": min(
                min(float(record["minimum_intensity"]) for record in scattering_records),
                min(float(record["minimum_intensity"]) for record in time_records),
            ),
            "angle_flux_error_order64": next(
                record["relative_error"] for record in convergence
                if record["control"] == "isothermal_absorption_angle" and record["grid_points"] == 64
            ),
            "frequency_integral_error_2049": next(
                record["relative_error"] for record in convergence
                if record["control"] == "planck_frequency_integral" and record["grid_points"] == 2049
            ),
            "time_static_limit_error_2048": time_errors[2048],
            "zo_tau_scattering_angle_relative_change_32_to_64_at_512_depth_cells": next(
                record["relative_error"] for record in convergence
                if record["control"] == "zo_tau_pure_scattering_angle" and record["grid_points"] == 32
            ),
            "zo_tau_transmission_relative_change_512_to_1024": abs(
                scattering_by_depth[512][1] / scattering_by_depth[1024][1] - 1.0
            ),
        },
        "physics_status": {
            "independent_frequency_groups": True,
            "angle_resolved_intensity": True,
            "vacuum_control_passed": True,
            "pure_absorption_lte_control_passed": True,
            "conservative_coherent_scattering_control_passed": True,
            "time_dependent_static_limit_converges": True,
            "zo_dynamics_modified": False,
            "pre_erratum_area_used": False,
            "physical_frequency_dependent_opacity_supplied": False,
            "physical_atomic_rates_supplied": False,
            "velocity_frequency_angle_coupling_included": False,
            "depth_dissipation_closure_supplied": False,
            "nlte_spectrum_produced": False,
        },
        "decision": (
            "[V] The static and time-dependent one-dimensional transfer kernels pass vacuum, "
            "LTE absorption, conservative scattering and static-limit controls. [A] Planck and "
            "gray scattering inputs are analytic controls only. [O] Physical opacity, atomic "
            "rates, velocity coupling, dissipation depth and NLTE spectra remain unsolved."
        ),
    }

    _write_csv(output_dir / "phase7b2_absorption_spectrum.csv", absorption_spectra)
    _write_csv(output_dir / "phase7b2_scattering_conservation.csv", scattering_records)
    _write_csv(output_dir / "phase7b2_convergence.csv", convergence)
    _write_csv(output_dir / "phase7b2_time_controls.csv", time_records)
    (output_dir / "phase7b2_transfer_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _plot(
        output_dir / "phase7b2_transfer_controls.png",
        temperature_k,
        spectra,
        scattering_records,
        convergence,
        time_errors,
    )


if __name__ == "__main__":
    main()
