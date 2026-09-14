"""生成 Phase 7B1 周期柱背景、守恒布居控制和收敛证据。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eccentric_tde_observer.dynamic_column import (
    build_zo_periodic_column_background,
    periodic_first_harmonic,
    solve_periodic_rate_network,
    two_state_periodic_control,
)
from eccentric_tde_observer.phase7a import select_quasi_static_representative_annuli
from eccentric_tde_observer.reference_case import (
    STRICT_CIRCULARIZATION_EFFICIENCY,
    STRICT_ECCENTRICITY,
    build_strict_domain_reference_model,
)


RELAXATION_RATIOS = (0.01, 0.1, 1.0, 10.0)
TIME_GRID_POINTS = (128, 256, 512, 1024, 2048)
VERTICAL_GRID_POINTS = (17, 33, 65, 129, 257)


def _write_csv(path: Path, records: list[dict[str, object]]) -> None:
    if not records:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def _cyclic_time_average(values: np.ndarray, duration: np.ndarray, period: float) -> float:
    following = np.roll(values, -1)
    return float(np.sum(0.5 * (values + following) * duration) / period)


def _background_records(background) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for phase in range(background.phase_points):
        records.append(
            {
                "phase_index": phase,
                "eccentric_anomaly_rad": float(background.eccentric_anomaly_rad[phase]),
                "mean_anomaly_rad": float(background.mean_anomaly_rad[phase]),
                "time_over_period": float(
                    background.time_since_pericentre_s[phase]
                    / background.orbital_period_s
                ),
                "step_duration_over_period": float(
                    background.step_duration_s[phase] / background.orbital_period_s
                ),
                "orbital_radius_cm": float(background.orbital_radius_cm[phase]),
                "surface_density_g_cm2": float(background.surface_density_g_cm2[phase]),
                "scale_height_cm": float(background.scale_height_cm[phase]),
                "effective_temperature_k": float(background.effective_temperature_k[phase]),
                "one_sided_column_mass_g_cm2": float(
                    background.one_sided_column_mass_g_cm2[phase]
                ),
                "pressure_gravity_coefficient_s2": float(
                    background.pressure_gravity_coefficient_s2[phase]
                ),
                "tidal_gravity_coefficient_s2": float(
                    background.tidal_gravity_coefficient_s2[phase]
                ),
                "logarithmic_breathing_rate_s1": float(
                    background.logarithmic_breathing_rate_s1[phase]
                ),
                "quasi_static_ratio": float(background.quasi_static_ratio[phase]),
                "one_face_surface_flux_erg_s_cm2": float(
                    background.one_face_surface_flux_erg_s_cm2[phase]
                ),
                "electron_scattering_depth_to_midplane": float(
                    background.electron_scattering_depth_to_midplane[phase]
                ),
                "scale_height_light_crossing_s": float(
                    background.scale_height_light_crossing_s[phase]
                ),
                "scattering_transport_time_proxy_s": float(
                    background.scattering_transport_time_proxy_s[phase]
                ),
                "vertical_response_time_s": float(
                    background.vertical_response_time_s[phase]
                ),
            }
        )
    return records


def _kinetics_records_and_summary(background):
    records: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    solutions = {}
    for ratio in RELAXATION_RATIOS:
        control = two_state_periodic_control(
            background.mean_anomaly_rad,
            background.orbital_period_s,
            ratio,
        )
        solution = solve_periodic_rate_network(
            control.rate_matrices_s1,
            background.step_duration_s,
            [0.5, 0.5],
        )
        excited = solution.population[:, 1]
        mean, amplitude, lag = periodic_first_harmonic(
            excited,
            background.mean_anomaly_rad,
            background.step_duration_s,
        )
        residual = excited - control.analytic_excited_fraction
        rms = float(
            np.sqrt(
                np.sum(residual**2 * background.step_duration_s)
                / background.orbital_period_s
            )
        )
        summaries.append(
            {
                "relaxation_time_over_period": ratio,
                "cycles": solution.cycles,
                "cycle_residual": solution.cycle_residual,
                "maximum_particle_conservation_residual": (
                    solution.maximum_particle_conservation_residual
                ),
                "minimum_population": solution.minimum_population,
                "maximum_absolute_analytic_error": float(np.max(np.abs(residual))),
                "time_weighted_rms_analytic_error": rms,
                "fitted_mean_excited_fraction": mean,
                "fitted_amplitude_ratio": amplitude / 0.4,
                "analytic_amplitude_ratio": control.analytic_amplitude_ratio,
                "fitted_phase_lag_rad": lag,
                "analytic_phase_lag_rad": control.analytic_phase_lag_rad,
            }
        )
        for phase in range(background.phase_points):
            records.append(
                {
                    "relaxation_time_over_period": ratio,
                    "phase_index": phase,
                    "mean_anomaly_rad": float(background.mean_anomaly_rad[phase]),
                    "time_over_period": float(
                        background.time_since_pericentre_s[phase]
                        / background.orbital_period_s
                    ),
                    "instantaneous_equilibrium_excited_fraction": float(
                        control.equilibrium_excited_fraction[phase]
                    ),
                    "numerical_periodic_excited_fraction": float(excited[phase]),
                    "analytic_periodic_excited_fraction": float(
                        control.analytic_excited_fraction[phase]
                    ),
                    "numerical_minus_analytic": float(residual[phase]),
                }
            )
        solutions[ratio] = (control, solution)
    return records, summaries, solutions


def _time_grid_convergence(radial_index: int):
    raw: list[dict[str, object]] = []
    for phase_points in TIME_GRID_POINTS:
        model = build_strict_domain_reference_model(65, phase_points)
        background = build_zo_periodic_column_background(model, radial_index)
        mean_height = _cyclic_time_average(
            background.scale_height_cm,
            background.step_duration_s,
            background.orbital_period_s,
        )
        mean_flux = _cyclic_time_average(
            background.one_face_surface_flux_erg_s_cm2,
            background.step_duration_s,
            background.orbital_period_s,
        )
        control = two_state_periodic_control(
            background.mean_anomaly_rad,
            background.orbital_period_s,
            0.01,
        )
        solution = solve_periodic_rate_network(
            control.rate_matrices_s1,
            background.step_duration_s,
            [0.5, 0.5],
        )
        _, amplitude, lag = periodic_first_harmonic(
            solution.population[:, 1],
            background.mean_anomaly_rad,
            background.step_duration_s,
        )
        raw.append(
            {
                "grid_kind": "orbital_time",
                "grid_points": phase_points,
                "maximum_step_over_period": float(
                    np.max(background.step_duration_s) / background.orbital_period_s
                ),
                "time_mean_scale_height_cm": mean_height,
                "time_mean_surface_flux_erg_s_cm2": mean_flux,
                "fast_control_maximum_absolute_error": float(
                    np.max(
                        np.abs(
                            solution.population[:, 1]
                            - control.analytic_excited_fraction
                        )
                    )
                ),
                "fast_control_fitted_amplitude_ratio": amplitude / 0.4,
                "fast_control_fitted_phase_lag_rad": lag,
            }
        )
    reference = raw[-1]
    records: list[dict[str, object]] = []
    for record in raw:
        record = dict(record)
        record["relative_height_error_vs_2048"] = abs(
            float(record["time_mean_scale_height_cm"])
            / float(reference["time_mean_scale_height_cm"])
            - 1.0
        )
        record["relative_flux_error_vs_2048"] = abs(
            float(record["time_mean_surface_flux_erg_s_cm2"])
            / float(reference["time_mean_surface_flux_erg_s_cm2"])
            - 1.0
        )
        records.append(record)
    return records


def _vertical_grid_convergence(background):
    records: list[dict[str, object]] = []
    for grid_points in VERTICAL_GRID_POINTS:
        zeta = np.linspace(-3.0, 3.0, grid_points)
        density = background.density_g_cm3(zeta)
        recovered = np.trapezoid(
            density,
            background.scale_height_cm[:, None] * zeta[None, :],
            axis=1,
        )
        relative_error = np.abs(
            recovered / background.surface_density_g_cm2 - 1.0
        )
        records.append(
            {
                "grid_kind": "vertical_scaled_height",
                "grid_points": grid_points,
                "zeta_min": -3.0,
                "zeta_max": 3.0,
                "maximum_surface_density_relative_error": float(
                    np.max(relative_error)
                ),
                "time_weighted_mean_surface_density_relative_error": float(
                    np.sum(relative_error * background.step_duration_s)
                    / background.orbital_period_s
                ),
            }
        )
    return records


def _plot(path: Path, background, solutions, summaries) -> None:
    phase = background.time_since_pericentre_s / background.orbital_period_s
    mean_height = _cyclic_time_average(
        background.scale_height_cm,
        background.step_duration_s,
        background.orbital_period_s,
    )
    mean_temperature = _cyclic_time_average(
        background.effective_temperature_k,
        background.step_duration_s,
        background.orbital_period_s,
    )
    mean_flux = _cyclic_time_average(
        background.one_face_surface_flux_erg_s_cm2,
        background.step_duration_s,
        background.orbital_period_s,
    )
    figure, axes = plt.subplots(2, 2, figsize=(13.2, 9.2), constrained_layout=True)

    axes[0, 0].plot(phase, background.scale_height_cm / mean_height, label=r"$H/\langle H\rangle_t$")
    axes[0, 0].plot(
        phase,
        background.effective_temperature_k / mean_temperature,
        label=r"$T_{\rm eff}/\langle T_{\rm eff}\rangle_t$",
    )
    axes[0, 0].plot(
        phase,
        background.one_face_surface_flux_erg_s_cm2 / mean_flux,
        label=r"$F_{\rm surf}/\langle F_{\rm surf}\rangle_t$",
    )
    axes[0, 0].set_xlabel(r"$t/P$")
    axes[0, 0].set_ylabel("Time-normalized prescribed field")
    axes[0, 0].set_title("(a) Actual prescribed ZO column over one orbit")
    axes[0, 0].legend(frameon=False)

    axes[0, 1].semilogy(
        phase,
        background.scale_height_light_crossing_s / background.orbital_period_s,
        label=r"$H/(cP)$",
    )
    axes[0, 1].semilogy(
        phase,
        background.scattering_transport_time_proxy_s / background.orbital_period_s,
        label=r"$\tau_{\rm es}H/(cP)$ [A-proxy]",
    )
    axes[0, 1].semilogy(
        phase,
        background.vertical_response_time_s / background.orbital_period_s,
        label=r"$1/(P\sqrt{Q_{\rm pressure}})$",
    )
    axes[0, 1].set_xlabel(r"$t/P$")
    axes[0, 1].set_ylabel("Timescale / orbital period")
    axes[0, 1].set_title("(b) Transport and vertical-response diagnostics")
    axes[0, 1].legend(frameon=False, fontsize=9)

    control_reference, _ = solutions[RELAXATION_RATIOS[0]]
    axes[1, 0].plot(
        phase,
        control_reference.equilibrium_excited_fraction,
        color="black",
        linestyle="--",
        linewidth=1.2,
        label="instantaneous equilibrium control",
    )
    for ratio in RELAXATION_RATIOS:
        _, solution = solutions[ratio]
        axes[1, 0].plot(
            phase,
            solution.population[:, 1],
            label=rf"$\tau_{{\rm rel}}/P={ratio:g}$",
        )
    axes[1, 0].set_xlabel(r"$t/P$")
    axes[1, 0].set_ylabel("Excited-state fraction [A-control]")
    axes[1, 0].set_title("(c) Periodic following and phase lag")
    axes[1, 0].legend(frameon=False, fontsize=8)

    ratio = np.geomspace(0.005, 20.0, 300)
    analytic_amplitude = 1.0 / np.sqrt(1.0 + (2.0 * np.pi * ratio) ** 2)
    analytic_lag = np.arctan(2.0 * np.pi * ratio)
    axes[1, 1].semilogx(ratio, analytic_amplitude, color="tab:blue", label="analytic amplitude")
    axes[1, 1].plot(
        [record["relaxation_time_over_period"] for record in summaries],
        [record["fitted_amplitude_ratio"] for record in summaries],
        "o",
        color="tab:blue",
        label="numerical amplitude",
    )
    axes[1, 1].set_xlabel(r"$\tau_{\rm rel}/P$")
    axes[1, 1].set_ylabel("Response amplitude / forcing amplitude", color="tab:blue")
    twin = axes[1, 1].twinx()
    twin.semilogx(ratio, np.degrees(analytic_lag), color="tab:red", label="analytic lag")
    twin.plot(
        [record["relaxation_time_over_period"] for record in summaries],
        [np.degrees(record["fitted_phase_lag_rad"]) for record in summaries],
        "s",
        color="tab:red",
        label="numerical lag",
    )
    twin.set_ylabel("Phase lag (deg)", color="tab:red")
    axes[1, 1].set_title("(d) Analytic control recovered across timescales")
    handles_a, labels_a = axes[1, 1].get_legend_handles_labels()
    handles_b, labels_b = twin.get_legend_handles_labels()
    axes[1, 1].legend(handles_a + handles_b, labels_a + labels_b, frameon=False, fontsize=8)

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
    model = build_strict_domain_reference_model(
        arguments.radial_points, arguments.anomaly_points
    )
    selection = select_quasi_static_representative_annuli(model, count=12)
    representative_index = int(arguments.representative_index)
    if representative_index < 0 or representative_index >= selection.count:
        raise ValueError("representative-index lies outside the Phase 7A selection")
    radial_index = int(selection.radial_index[representative_index])
    background = build_zo_periodic_column_background(model, radial_index)

    background_records = _background_records(background)
    kinetics_records, kinetics_summaries, solutions = _kinetics_records_and_summary(
        background
    )
    time_convergence = _time_grid_convergence(radial_index)
    vertical_convergence = _vertical_grid_convergence(background)

    zeta_audit = np.linspace(-3.0, 3.0, 4001)
    density = background.density_g_cm3(zeta_audit)
    recovered_sigma = np.trapezoid(
        density,
        background.scale_height_cm[:, None] * zeta_audit[None, :],
        axis=1,
    )
    density_mass_residual = float(
        np.max(np.abs(recovered_sigma / background.surface_density_g_cm2 - 1.0))
    )
    period_residual = abs(
        float(np.sum(background.step_duration_s)) / background.orbital_period_s
        - 1.0
    )
    report = {
        "phase": "7B1",
        "classification": "[L/A/V/O] prescribed-background periodic-column foundation",
        "model": {
            "eccentricity": STRICT_ECCENTRICITY,
            "circularization_efficiency": STRICT_CIRCULARIZATION_EFFICIENCY,
            "radial_points": arguments.radial_points,
            "anomaly_points": arguments.anomaly_points,
            "phase7a_representative_index": representative_index,
            "radial_index": radial_index,
            "phase7a_selection_anomaly_index": int(
                selection.anomaly_index[representative_index]
            ),
            "semimajor_axis_cm": background.semimajor_axis_cm,
            "orbital_period_s": background.orbital_period_s,
            "vertical_profile": background.vertical_profile.name,
        },
        "background_ranges": {
            "surface_density_g_cm2": [
                float(np.min(background.surface_density_g_cm2)),
                float(np.max(background.surface_density_g_cm2)),
            ],
            "scale_height_cm": [
                float(np.min(background.scale_height_cm)),
                float(np.max(background.scale_height_cm)),
            ],
            "effective_temperature_k": [
                float(np.min(background.effective_temperature_k)),
                float(np.max(background.effective_temperature_k)),
            ],
            "pressure_gravity_coefficient_s2": [
                float(np.min(background.pressure_gravity_coefficient_s2)),
                float(np.max(background.pressure_gravity_coefficient_s2)),
            ],
            "quasi_static_ratio": [
                float(np.min(background.quasi_static_ratio)),
                float(np.max(background.quasi_static_ratio)),
            ],
            "electron_scattering_depth_to_midplane": [
                float(np.min(background.electron_scattering_depth_to_midplane)),
                float(np.max(background.electron_scattering_depth_to_midplane)),
            ],
            "scale_height_light_crossing_over_period": [
                float(np.min(background.scale_height_light_crossing_s) / background.orbital_period_s),
                float(np.max(background.scale_height_light_crossing_s) / background.orbital_period_s),
            ],
            "scattering_transport_proxy_over_period": [
                float(np.min(background.scattering_transport_time_proxy_s) / background.orbital_period_s),
                float(np.max(background.scattering_transport_time_proxy_s) / background.orbital_period_s),
            ],
        },
        "acceptance": {
            "cyclic_time_sum_relative_residual": period_residual,
            "polytrope_surface_density_relative_residual_4001_points": density_mass_residual,
            "maximum_cycle_residual": max(
                float(record["cycle_residual"]) for record in kinetics_summaries
            ),
            "maximum_particle_conservation_residual": max(
                float(record["maximum_particle_conservation_residual"])
                for record in kinetics_summaries
            ),
            "minimum_population": min(
                float(record["minimum_population"]) for record in kinetics_summaries
            ),
            "maximum_two_state_analytic_error": max(
                float(record["maximum_absolute_analytic_error"])
                for record in kinetics_summaries
            ),
            "no_population_clipping": True,
            "no_population_floor": True,
            "no_stepwise_renormalization": True,
        },
        "two_state_controls": kinetics_summaries,
        "orbital_time_grid_convergence": time_convergence,
        "vertical_grid_convergence": vertical_convergence,
        "physics_status": {
            "zo_background_is_prescribed": True,
            "zo_source_fields_modified": False,
            "corrected_area_used_for_phase7a_representative_selection": True,
            "pre_erratum_area_used": False,
            "time_dependent_population_integrator": "verified numerical control only",
            "physical_atomic_rates_supplied": False,
            "frequency_angle_radiative_transfer_solved": False,
            "physical_depth_dissipation_profile_supplied": False,
            "upper_boundary": "vacuum/no-incident-radiation contract; transfer not yet solved",
            "energy_feedback_solved": False,
            "nlte_spectrum_produced": False,
        },
        "decision": (
            "[V] Phase 7B1 establishes the exact Kepler time map, prescribed ZO vertical "
            "background, conservative positive periodic rate-network kernel and analytic two-state "
            "controls. [O] It does not yet provide atomic rates, a depth-dependent dissipation "
            "closure, time-dependent radiative transfer, or an NLTE spectrum."
        ),
    }

    _write_csv(output_dir / "phase7b_periodic_column_background.csv", background_records)
    _write_csv(output_dir / "phase7b_kinetics_sensitivity.csv", kinetics_records)
    _write_csv(output_dir / "phase7b_time_grid_convergence.csv", time_convergence)
    _write_csv(output_dir / "phase7b_vertical_grid_convergence.csv", vertical_convergence)
    (output_dir / "phase7b_periodic_column_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _plot(
        output_dir / "phase7b_periodic_column_control.png",
        background,
        solutions,
        kinetics_summaries,
    )


if __name__ == "__main__":
    main()
