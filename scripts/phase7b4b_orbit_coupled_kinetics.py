"""生成 Phase 7B4b 无辐照、轨道耦合 H/He 基态动力学证据。"""

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
    collisional_photoionization_equilibrium,
    detailed_balance_three_body_recombination_coefficient_cm6_s,
)
from eccentric_tde_observer.atmosphere import (
    PROTON_MASS_G,
    SOLAR_FULLY_IONIZED_H_HE,
)
from eccentric_tde_observer.dynamic_column import build_zo_periodic_column_background
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.orbital_kinetics import (
    HHeRateOrbit,
    charge_neutral_backward_euler_step,
    solve_periodic_h_he_kinetics,
)
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model


IONIZATION_ENERGIES_EV = (13.59843449, 24.587389, 54.417765)
ANALYTIC_TIME_STEPS = (32, 64, 128, 256, 512, 1024)
TIME_SUBDIVISIONS = (1, 2, 4, 8)
TIME_REFERENCE_SUBDIVISION = 16
SOURCE_PHASE_POINTS = (256, 512, 1024)
SOURCE_REFERENCE_POINTS = 2048


def _write_csv(path: Path, records: list[dict[str, object]]) -> None:
    if not records:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def _rate_arrays(temperature_k: np.ndarray):
    collision = np.column_stack(
        [fit.coefficient_cm3_s(temperature_k) for fit in H_HE_COLLISIONAL_IONIZATION_FITS]
    )
    saha = np.column_stack(
        [
            ground_state_saha_factor_cm3(temperature_k, energy)
            for energy in IONIZATION_ENERGIES_EV
        ]
    )
    three_body = np.column_stack(
        [
            detailed_balance_three_body_recombination_coefficient_cm6_s(
                collision[:, index], saha[:, index]
            )
            for index in range(3)
        ]
    )
    radiative = np.column_stack(
        [
            H_I_RECOMBINATION_FIT.coefficient_cm3_s(temperature_k),
            HE_I_RECOMBINATION_FIT.coefficient_cm3_s(temperature_k),
            HE_II_RECOMBINATION_FIT.coefficient_cm3_s(temperature_k),
        ]
    )
    return collision, radiative, three_body


def _background_fields(anomaly_points: int):
    model = build_strict_domain_reference_model(65, int(anomaly_points))
    background = build_zo_periodic_column_background(model, 8)
    density = (
        background.surface_density_g_cm2
        / background.scale_height_cm
        * background.vertical_profile.density_shape(np.asarray(0.0))
    )
    gray_midplane_depth = 0.5 * model.parameters.opacity_cm2_g * background.surface_density_g_cm2
    temperature = background.effective_temperature_k * (
        0.75 * (gray_midplane_depth + 2.0 / 3.0)
    ) ** 0.25
    composition = SOLAR_FULLY_IONIZED_H_HE
    hydrogen = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium = composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    return {
        "background": background,
        "phase": background.time_since_pericentre_s / background.orbital_period_s,
        "step_duration_s": background.step_duration_s,
        "density_g_cm3": density,
        "temperature_k": temperature,
        "hydrogen_nuclei_cm3": hydrogen,
        "helium_nuclei_cm3": helium,
    }


def _solve_fields(fields, *, alternative_initial_condition: bool = False):
    temperature = fields["temperature_k"]
    hydrogen = fields["hydrogen_nuclei_cm3"]
    helium = fields["helium_nuclei_cm3"]
    collision, radiative, three_body = _rate_arrays(temperature)
    instantaneous = collisional_photoionization_equilibrium(
        hydrogen,
        helium,
        0.0,
        0.0,
        0.0,
        collision[:, 0],
        collision[:, 1],
        collision[:, 2],
        radiative[:, 0],
        radiative[:, 1],
        radiative[:, 2],
        three_body[:, 0],
        three_body[:, 1],
        three_body[:, 2],
    )
    orbit = HHeRateOrbit(
        hydrogen,
        helium,
        fields["step_duration_s"],
        np.zeros((temperature.size, 3)),
        collision,
        radiative,
        three_body,
    )
    if alternative_initial_condition:
        initial_hydrogen = np.array([0.8, 0.2])
        initial_helium = np.array([0.6, 0.3, 0.1])
    else:
        initial_hydrogen = np.array(
            [
                instantaneous.hydrogen_neutral_fraction[0],
                instantaneous.hydrogen_ionized_fraction[0],
            ]
        )
        initial_helium = np.array(
            [
                instantaneous.helium_neutral_fraction[0],
                instantaneous.helium_singly_ionized_fraction[0],
                instantaneous.helium_doubly_ionized_fraction[0],
            ]
        )
    solution = solve_periodic_h_he_kinetics(
        orbit,
        initial_hydrogen,
        initial_helium,
        cycle_tolerance=1.0e-12,
        bisection_iterations=64,
    )
    lte = lte_hydrogen_helium_ionization(
        fields["density_g_cm3"], temperature, SOLAR_FULLY_IONIZED_H_HE
    )
    return {
        **fields,
        "collision": collision,
        "radiative": radiative,
        "three_body": three_body,
        "instantaneous": instantaneous,
        "lte": lte,
        "solution": solution,
    }


def _fraction_arrays(case):
    solution = case["solution"]
    instantaneous = case["instantaneous"]
    lte = case["lte"]
    dynamic = np.column_stack(
        (
            solution.hydrogen_fraction[:, 1],
            solution.helium_fraction[:, 0],
            solution.helium_fraction[:, 1],
            solution.helium_fraction[:, 2],
        )
    )
    steady = np.column_stack(
        (
            instantaneous.hydrogen_ionized_fraction,
            instantaneous.helium_neutral_fraction,
            instantaneous.helium_singly_ionized_fraction,
            instantaneous.helium_doubly_ionized_fraction,
        )
    )
    lte_fraction = np.column_stack(
        (
            lte.hydrogen_ionized_fraction,
            lte.helium_neutral_fraction,
            lte.helium_singly_ionized_fraction,
            lte.helium_doubly_ionized_fraction,
        )
    )
    return dynamic, steady, lte_fraction


def _periodic_records(case):
    dynamic, steady, lte = _fraction_arrays(case)
    solution = case["solution"]
    records = []
    for index, phase in enumerate(case["phase"]):
        records.append(
            {
                "phase_index": index,
                "orbital_time_phase": float(phase),
                "eccentric_anomaly_rad": float(
                    case["background"].eccentric_anomaly_rad[index]
                ),
                "midplane_density_g_cm3": float(case["density_g_cm3"][index]),
                "gray_eddington_midplane_temperature_k": float(
                    case["temperature_k"][index]
                ),
                "dynamic_electron_density_cm3": float(
                    solution.electron_density_cm3[index]
                ),
                "instantaneous_electron_density_cm3": float(
                    case["instantaneous"].electron_density_cm3[index]
                ),
                "lte_electron_density_cm3": float(case["lte"].electron_density_cm3[index]),
                "dynamic_h_ii_fraction": float(dynamic[index, 0]),
                "dynamic_he_i_fraction": float(dynamic[index, 1]),
                "dynamic_he_ii_fraction": float(dynamic[index, 2]),
                "dynamic_he_iii_fraction": float(dynamic[index, 3]),
                "instantaneous_h_ii_fraction": float(steady[index, 0]),
                "instantaneous_he_i_fraction": float(steady[index, 1]),
                "instantaneous_he_ii_fraction": float(steady[index, 2]),
                "instantaneous_he_iii_fraction": float(steady[index, 3]),
                "lte_h_ii_fraction": float(lte[index, 0]),
                "lte_he_i_fraction": float(lte[index, 1]),
                "lte_he_ii_fraction": float(lte[index, 2]),
                "lte_he_iii_fraction": float(lte[index, 3]),
            }
        )
    return records


def _hydrogen_photo_rr_analytic(
    time_s: float,
    initial_ionized: float,
    gamma_s1: float,
    nuclei_cm3: float,
    alpha_cm3_s: float,
) -> float:
    coefficient = nuclei_cm3 * alpha_cm3_s
    discriminant = np.sqrt(gamma_s1**2 + 4.0 * coefficient * gamma_s1)
    positive_root = (-gamma_s1 + discriminant) / (2.0 * coefficient)
    negative_root = (-gamma_s1 - discriminant) / (2.0 * coefficient)
    ratio = (initial_ionized - positive_root) / (initial_ionized - negative_root)
    evolved_ratio = ratio * np.exp(
        -coefficient * (positive_root - negative_root) * time_s
    )
    return float(
        (positive_root - evolved_ratio * negative_root) / (1.0 - evolved_ratio)
    )


def _analytic_convergence_records():
    total_time = 2.0
    gamma = 1.0
    hydrogen = 2.0
    alpha = 1.0
    initial_hydrogen = np.array([0.8, 0.2])
    initial_helium = np.array([1.0, 0.0, 0.0])
    analytic = _hydrogen_photo_rr_analytic(
        total_time, initial_hydrogen[1], gamma, hydrogen, alpha
    )
    records = []
    for steps in ANALYTIC_TIME_STEPS:
        state_h = initial_hydrogen.copy()
        state_he = initial_helium.copy()
        maximum_charge = 0.0
        maximum_particle = 0.0
        for _ in range(steps):
            result = charge_neutral_backward_euler_step(
                state_h,
                state_he,
                hydrogen,
                0.0,
                total_time / steps,
                np.array([gamma, 0.0, 0.0]),
                np.zeros(3),
                np.array([alpha, 0.0, 0.0]),
                np.zeros(3),
                bisection_iterations=64,
            )
            state_h = np.array(result.hydrogen_fraction)
            state_he = np.array(result.helium_fraction)
            maximum_charge = max(maximum_charge, result.relative_charge_residual)
            maximum_particle = max(
                maximum_particle, result.particle_conservation_residual
            )
        records.append(
            {
                "control": "analytic_hydrogen_photo_rr",
                "resolution": steps,
                "observable": "final_h_ii_absolute_error",
                "error": abs(float(state_h[1]) - analytic),
                "maximum_relative_charge_residual": maximum_charge,
                "maximum_particle_conservation_residual": maximum_particle,
            }
        )
    return records


def _subdivide_fields(base, subdivision: int):
    fraction = np.arange(subdivision, dtype=np.float64) / subdivision
    values = {}
    for name in (
        "density_g_cm3",
        "temperature_k",
        "hydrogen_nuclei_cm3",
        "helium_nuclei_cm3",
    ):
        current = base[name]
        following = np.roll(current, -1)
        interpolated = (
            (1.0 - fraction[:, None]) * current[None, :]
            + fraction[:, None] * following[None, :]
        )
        values[name] = interpolated.T.reshape(-1)
    values["step_duration_s"] = np.repeat(
        base["step_duration_s"] / subdivision, subdivision
    )
    phase_start = base["phase"]
    phase_end = np.roll(phase_start, -1)
    phase_end[-1] = 1.0
    values["phase"] = (
        (1.0 - fraction[:, None]) * phase_start[None, :]
        + fraction[:, None] * phase_end[None, :]
    ).T.reshape(-1)
    return values


def _time_subdivision_convergence_records():
    base = _background_fields(256)
    reference = _solve_fields(
        _subdivide_fields(base, TIME_REFERENCE_SUBDIVISION)
    )
    reference_dynamic, _, _ = _fraction_arrays(reference)
    reference_at_base = reference_dynamic[::TIME_REFERENCE_SUBDIVISION]
    records = []
    for subdivision in TIME_SUBDIVISIONS:
        case = _solve_fields(_subdivide_fields(base, subdivision))
        dynamic, _, _ = _fraction_arrays(case)
        at_base = dynamic[::subdivision]
        error = float(np.max(np.abs(at_base - reference_at_base)))
        records.append(
            {
                "control": "orbit_time_subdivision",
                "resolution": 256 * subdivision,
                "observable": "maximum_ion_fraction_absolute_error",
                "error": error,
                "maximum_relative_charge_residual": case[
                    "solution"
                ].maximum_relative_charge_residual,
                "maximum_particle_conservation_residual": case[
                    "solution"
                ].maximum_particle_conservation_residual,
            }
        )
    return records


def _source_grid_convergence_records(cases):
    reference = cases[SOURCE_REFERENCE_POINTS]
    reference_dynamic, _, _ = _fraction_arrays(reference)
    reference_phase = reference["phase"]
    records = []
    for points in SOURCE_PHASE_POINTS:
        case = cases[points]
        dynamic, _, _ = _fraction_arrays(case)
        errors = []
        for field in range(dynamic.shape[1]):
            interpolated = np.interp(
                reference_phase, case["phase"], dynamic[:, field], period=1.0
            )
            errors.append(
                float(np.sqrt(np.mean((interpolated - reference_dynamic[:, field]) ** 2)))
            )
        records.append(
            {
                "control": "zo_source_phase_grid",
                "resolution": points,
                "observable": "maximum_ion_fraction_rms_error",
                "error": max(errors),
                "maximum_relative_charge_residual": case[
                    "solution"
                ].maximum_relative_charge_residual,
                "maximum_particle_conservation_residual": case[
                    "solution"
                ].maximum_particle_conservation_residual,
            }
        )
    return records


def _plot_main(path: Path, case) -> None:
    dynamic, steady, lte = _fraction_arrays(case)
    phase = case["phase"]
    figure, axes = plt.subplots(2, 2, figsize=(11.7, 8.2), constrained_layout=True)
    temperature_axis = axes[0, 0]
    density_axis = temperature_axis.twinx()
    temperature_axis.plot(phase, case["temperature_k"], color="tab:red", label="Temperature")
    density_axis.semilogy(
        phase, case["density_g_cm3"], color="tab:blue", label="Density"
    )
    temperature_axis.set(
        xlabel="Orbital time phase",
        ylabel="Gray-Eddington midplane temperature (K)",
        title="(a) Prescribed ZO midplane background",
    )
    density_axis.set_ylabel(r"Midplane density (g cm$^{-3}$)")
    lines = temperature_axis.lines + density_axis.lines
    temperature_axis.legend(lines, [line.get_label() for line in lines], fontsize=8)

    axes[0, 1].plot(phase, dynamic[:, 0], label="Dynamic H II")
    axes[0, 1].plot(phase, steady[:, 0], "--", label="Instantaneous kinetic steady state")
    axes[0, 1].plot(phase, lte[:, 0], ":", label="LTE Saha control")
    axes[0, 1].set(
        xlabel="Orbital time phase",
        ylabel="H II fraction",
        title="(b) Orbit-coupled hydrogen response",
    )
    axes[0, 1].legend(fontsize=8)

    colors = ("tab:orange", "tab:green", "tab:purple")
    labels = ("He I", "He II", "He III")
    for index, (color, label) in enumerate(zip(colors, labels, strict=True), start=1):
        axes[1, 0].plot(phase, dynamic[:, index], color=color, label=f"Dynamic {label}")
        axes[1, 0].plot(
            phase,
            steady[:, index],
            "--",
            color=color,
            linewidth=1.0,
            label=f"Instantaneous {label}",
        )
    axes[1, 0].set(
        xlabel="Orbital time phase",
        ylabel="Helium ion fraction",
        title="(c) Orbit-coupled helium response",
        ylim=(-0.03, 1.03),
    )
    axes[1, 0].legend(fontsize=7, ncol=2)

    kinetic_lag = np.max(np.abs(dynamic - steady), axis=1)
    missing_radiation_gap = np.max(np.abs(steady - lte), axis=1)
    positive_lag = kinetic_lag > 0.0
    positive_gap = missing_radiation_gap > 0.0
    axes[1, 1].semilogy(
        phase[positive_lag],
        kinetic_lag[positive_lag],
        label="Dynamic minus instantaneous kinetic state",
    )
    axes[1, 1].semilogy(
        phase[positive_gap],
        missing_radiation_gap[positive_gap],
        label="Instantaneous kinetic state minus LTE",
    )
    axes[1, 1].set(
        xlabel="Orbital time phase",
        ylabel="Maximum absolute ion-fraction difference",
        title="(d) Numerical lag versus missing-radiation gap",
    )
    axes[1, 1].legend(fontsize=8)
    for axis in axes.flat:
        axis.grid(alpha=0.25)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_convergence(path: Path, records) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(14.2, 4.2), constrained_layout=True)
    controls = (
        ("analytic_hydrogen_photo_rr", "(a) Analytic nonlinear H control", "Backward-Euler steps"),
        ("orbit_time_subdivision", "(b) Orbit time-step convergence", "Time points per orbit"),
        ("zo_source_phase_grid", "(c) ZO source-grid convergence", "Source phase points"),
    )
    for axis, (control, title, xlabel) in zip(axes, controls, strict=True):
        selected = [record for record in records if record["control"] == control]
        axis.loglog(
            [record["resolution"] for record in selected],
            [record["error"] for record in selected],
            "o-",
        )
        axis.set(xlabel=xlabel, ylabel="Absolute fraction error", title=title)
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

    cases = {
        points: _solve_fields(_background_fields(points))
        for points in sorted(set((*SOURCE_PHASE_POINTS, SOURCE_REFERENCE_POINTS)))
    }
    production = cases[int(arguments.anomaly_points)] if int(arguments.anomaly_points) in cases else _solve_fields(
        _background_fields(int(arguments.anomaly_points))
    )
    alternative = _solve_fields(
        _background_fields(int(arguments.anomaly_points)),
        alternative_initial_condition=True,
    )
    production_dynamic, production_steady, production_lte = _fraction_arrays(production)
    alternative_dynamic, _, _ = _fraction_arrays(alternative)
    initial_condition_difference = float(
        np.max(np.abs(production_dynamic - alternative_dynamic))
    )
    kinetic_lag = np.abs(production_dynamic - production_steady)
    lte_gap = np.abs(production_steady - production_lte)
    electron_lag = np.abs(
        production["solution"].electron_density_cm3
        / production["instantaneous"].electron_density_cm3
        - 1.0
    )
    electron_lte_gap = np.abs(
        production["instantaneous"].electron_density_cm3
        / production["lte"].electron_density_cm3
        - 1.0
    )

    convergence = []
    convergence.extend(_analytic_convergence_records())
    convergence.extend(_time_subdivision_convergence_records())
    convergence.extend(_source_grid_convergence_records(cases))
    analytic_1024 = next(
        record["error"]
        for record in convergence
        if record["control"] == "analytic_hydrogen_photo_rr"
        and record["resolution"] == 1024
    )
    subdivision_8 = next(
        record["error"]
        for record in convergence
        if record["control"] == "orbit_time_subdivision"
        and record["resolution"] == 2048
    )
    source_1024 = next(
        record["error"]
        for record in convergence
        if record["control"] == "zo_source_phase_grid"
        and record["resolution"] == 1024
    )
    report = {
        "phase": "7B4b",
        "classification": "[A-control/V/O] charge-neutral orbit-coupled ground-state H/He kinetics",
        "physical_inputs": {
            "zo_source_modified": False,
            "radial_index": 8,
            "anomaly_points": int(arguments.anomaly_points),
            "temperature_closure": "[A] gray-Eddington midplane temperature",
            "density_closure": "[A] n=3 vertical profile evaluated at the midplane",
            "external_photoionization_rates_s1": [0.0, 0.0, 0.0],
            "collisional_ionization": "Voronov 1997 H I, He I and He II fits",
            "radiative_recombination": "Verner and Ferland 1996 total RR fits",
            "three_body_recombination": "[A-control] collision coefficient divided by the same ground-state Saha factor",
        },
        "solver": {
            "method": "charge-neutral backward Euler with a scalar electron-density bisection",
            "bisection_iterations": 64,
            "cycle_tolerance": 1.0e-12,
            "production_cycles": production["solution"].cycles,
            "alternative_positive_initial_condition_cycles": alternative["solution"].cycles,
            "production_cycle_residual": production["solution"].cycle_residual,
            "maximum_relative_charge_residual": production[
                "solution"
            ].maximum_relative_charge_residual,
            "maximum_particle_conservation_residual": production[
                "solution"
            ].maximum_particle_conservation_residual,
            "minimum_ion_fraction": production["solution"].minimum_fraction,
            "maximum_periodic_solution_difference_between_two_positive_initial_conditions": initial_condition_difference,
            "exactly_neutral_collision_only_branch": "absorbing; verified separately and not used as the production initial state",
        },
        "periodic_response": {
            "h_ii_fraction_range": [
                float(np.min(production_dynamic[:, 0])),
                float(np.max(production_dynamic[:, 0])),
            ],
            "he_i_fraction_range": [
                float(np.min(production_dynamic[:, 1])),
                float(np.max(production_dynamic[:, 1])),
            ],
            "he_ii_fraction_range": [
                float(np.min(production_dynamic[:, 2])),
                float(np.max(production_dynamic[:, 2])),
            ],
            "he_iii_fraction_range": [
                float(np.min(production_dynamic[:, 3])),
                float(np.max(production_dynamic[:, 3])),
            ],
            "maximum_dynamic_minus_instantaneous_kinetic_fraction": float(
                np.max(kinetic_lag)
            ),
            "maximum_dynamic_electron_density_relative_lag": float(
                np.max(electron_lag)
            ),
            "maximum_instantaneous_kinetic_minus_lte_fraction": float(
                np.max(lte_gap)
            ),
            "maximum_instantaneous_electron_density_relative_difference_from_lte": float(
                np.max(electron_lte_gap)
            ),
        },
        "acceptance": {
            "analytic_hydrogen_error_at_1024_steps": analytic_1024,
            "orbit_time_subdivision_2048_vs_4096_maximum_fraction_error": subdivision_8,
            "source_phase_grid_1024_vs_2048_maximum_fraction_rms_error": source_1024,
            "periodic_cycle_residual": production["solution"].cycle_residual,
            "maximum_relative_charge_residual": production[
                "solution"
            ].maximum_relative_charge_residual,
            "maximum_particle_conservation_residual": production[
                "solution"
            ].maximum_particle_conservation_residual,
            "positive_initial_condition_independence_error": initial_condition_difference,
        },
        "scientific_boundary": {
            "physical_nlte_spectrum_produced": False,
            "radiation_population_iteration_solved": False,
            "gas_energy_equation_solved": False,
            "excited_levels_included": False,
            "velocity_frequency_coupling_included": False,
            "interpretation": "the no-irradiation ground-state kinetic orbit is a control, not a physical midplane or surface spectrum",
            "next_stage": "Phase 7B4c prescribed-radiation population coupling before self-consistent J_nu iteration",
        },
    }

    _write_csv(
        output_dir / "phase7b4b_periodic_kinetics.csv", _periodic_records(production)
    )
    _write_csv(output_dir / "phase7b4b_convergence.csv", convergence)
    (output_dir / "phase7b4b_orbit_coupled_kinetics_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _plot_main(output_dir / "phase7b4b_orbit_coupled_kinetics.png", production)
    _plot_convergence(
        output_dir / "phase7b4b_orbit_coupled_kinetics_convergence.png",
        convergence,
    )


if __name__ == "__main__":
    main()
