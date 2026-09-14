"""生成 Phase 7B4c 规定热辐射场--H/He 基态周期耦合证据。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import NullFormatter

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
from eccentric_tde_observer.orbital_kinetics import HHeRateOrbit, solve_periodic_h_he_kinetics
from eccentric_tde_observer.prescribed_radiation import (
    edge_resolved_photoionization_energy_grid_ev,
    prescribed_planck_photoionization_rates_s1,
)
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model


IONIZATION_ENERGIES_EV = (13.59843449, 24.587389, 54.417765)
DILUTION_SCAN = np.concatenate((np.array([0.0]), np.geomspace(1.0e-10, 1.0, 11)))
PLOT_DILUTIONS = (0.0, 1.0e-6, 1.0e-4, 1.0e-2, 1.0)
CONVERGENCE_DILUTION = 1.0e-4
FREQUENCY_GRID_POINTS = (257, 513, 1025, 2049, 4097)
FREQUENCY_REFERENCE_POINTS = 8193
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


def _background_fields(anomaly_points: int) -> dict[str, object]:
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


def _atomic_fields(fields: dict[str, object], energy_points: int) -> dict[str, object]:
    temperature = np.asarray(fields["temperature_k"])
    energy = edge_resolved_photoionization_energy_grid_ev(1.0, 5000.0, energy_points)
    prescribed = prescribed_planck_photoionization_rates_s1(
        temperature, np.ones(temperature.size), energy
    )
    collision = np.column_stack(
        [fit.coefficient_cm3_s(temperature) for fit in H_HE_COLLISIONAL_IONIZATION_FITS]
    )
    radiative_physical = np.column_stack(
        (
            H_I_RECOMBINATION_FIT.coefficient_cm3_s(temperature),
            HE_I_RECOMBINATION_FIT.coefficient_cm3_s(temperature),
            HE_II_RECOMBINATION_FIT.coefficient_cm3_s(temperature),
        )
    )
    saha = np.column_stack(
        [
            ground_state_saha_factor_cm3(temperature, energy_ev)
            for energy_ev in IONIZATION_ENERGIES_EV
        ]
    )
    three_body = np.column_stack(
        [
            detailed_balance_three_body_recombination_coefficient_cm6_s(
                collision[:, species], saha[:, species]
            )
            for species in range(3)
        ]
    )
    radiative_detailed_balance = prescribed.photoionization_s1 / saha
    return {
        **fields,
        "energy_ev": energy,
        "unit_photoionization_s1": prescribed.photoionization_s1,
        "collision_cm3_s": collision,
        "radiative_physical_cm3_s": radiative_physical,
        "radiative_detailed_balance_cm3_s": radiative_detailed_balance,
        "three_body_cm6_s": three_body,
        "saha_cm3": saha,
    }


def _instantaneous_state(
    fields: dict[str, object],
    photoionization: np.ndarray,
    radiative: np.ndarray,
):
    return collisional_photoionization_equilibrium(
        fields["hydrogen_nuclei_cm3"],
        fields["helium_nuclei_cm3"],
        photoionization[:, 0],
        photoionization[:, 1],
        photoionization[:, 2],
        fields["collision_cm3_s"][:, 0],
        fields["collision_cm3_s"][:, 1],
        fields["collision_cm3_s"][:, 2],
        radiative[:, 0],
        radiative[:, 1],
        radiative[:, 2],
        fields["three_body_cm6_s"][:, 0],
        fields["three_body_cm6_s"][:, 1],
        fields["three_body_cm6_s"][:, 2],
    )


def _solve_case(
    fields: dict[str, object],
    dilution: float,
    *,
    detailed_balance: bool = False,
    alternative_initial_condition: bool = False,
    explicit_photoionization: np.ndarray | None = None,
) -> dict[str, object]:
    photoionization = (
        float(dilution) * fields["unit_photoionization_s1"]
        if explicit_photoionization is None
        else np.asarray(explicit_photoionization, dtype=np.float64)
    )
    radiative = (
        fields["radiative_detailed_balance_cm3_s"]
        if detailed_balance
        else fields["radiative_physical_cm3_s"]
    )
    instantaneous = _instantaneous_state(fields, photoionization, radiative)
    rate_orbit = HHeRateOrbit(
        fields["hydrogen_nuclei_cm3"],
        fields["helium_nuclei_cm3"],
        fields["step_duration_s"],
        photoionization,
        fields["collision_cm3_s"],
        radiative,
        fields["three_body_cm6_s"],
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
        rate_orbit,
        initial_hydrogen,
        initial_helium,
        cycle_tolerance=1.0e-12,
        bisection_iterations=64,
    )
    lte = lte_hydrogen_helium_ionization(
        fields["density_g_cm3"],
        fields["temperature_k"],
        SOLAR_FULLY_IONIZED_H_HE,
    )
    return {
        **fields,
        "dilution": float(dilution),
        "detailed_balance": bool(detailed_balance),
        "photoionization_s1": photoionization,
        "radiative_cm3_s": radiative,
        "instantaneous": instantaneous,
        "solution": solution,
        "lte": lte,
    }


def _fraction_arrays(case: dict[str, object]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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


def _subdivide_fields(base: dict[str, object], subdivision: int) -> dict[str, object]:
    fraction = np.arange(subdivision, dtype=np.float64) / subdivision
    values: dict[str, object] = {}
    for name in (
        "density_g_cm3",
        "temperature_k",
        "hydrogen_nuclei_cm3",
        "helium_nuclei_cm3",
    ):
        current = np.asarray(base[name])
        following = np.roll(current, -1)
        interpolated = (
            (1.0 - fraction[:, None]) * current[None, :]
            + fraction[:, None] * following[None, :]
        )
        values[name] = interpolated.T.reshape(-1)
    values["step_duration_s"] = np.repeat(
        np.asarray(base["step_duration_s"]) / subdivision, subdivision
    )
    phase_start = np.asarray(base["phase"])
    phase_end = np.roll(phase_start, -1)
    phase_end[-1] = 1.0
    values["phase"] = (
        (1.0 - fraction[:, None]) * phase_start[None, :]
        + fraction[:, None] * phase_end[None, :]
    ).T.reshape(-1)
    return values


def _frequency_convergence_records(fields: dict[str, object]) -> list[dict[str, object]]:
    sample_indices = np.unique(
        np.linspace(0, np.asarray(fields["temperature_k"]).size - 1, 64, dtype=int)
    )
    temperature = np.asarray(fields["temperature_k"])[sample_indices]
    reference_energy = edge_resolved_photoionization_energy_grid_ev(
        1.0, 5000.0, FREQUENCY_REFERENCE_POINTS
    )
    reference = prescribed_planck_photoionization_rates_s1(
        temperature, np.ones(temperature.size), reference_energy
    ).photoionization_s1
    records: list[dict[str, object]] = []
    for points in FREQUENCY_GRID_POINTS:
        energy = edge_resolved_photoionization_energy_grid_ev(1.0, 5000.0, points)
        rates = prescribed_planck_photoionization_rates_s1(
            temperature, np.ones(temperature.size), energy
        ).photoionization_s1
        for species, label in enumerate(("H I", "He I", "He II")):
            error = float(np.max(np.abs(rates[:, species] / reference[:, species] - 1.0)))
            records.append(
                {
                    "control": "photoionization_frequency_grid",
                    "species": label,
                    "resolution": int(points),
                    "observable": "maximum_relative_rate_error",
                    "error": error,
                }
            )
    return records


def _time_convergence_records(energy_points: int) -> list[dict[str, object]]:
    base = _background_fields(128)
    reference_fields = _atomic_fields(
        _subdivide_fields(base, TIME_REFERENCE_SUBDIVISION), energy_points
    )
    reference = _solve_case(reference_fields, CONVERGENCE_DILUTION)
    reference_dynamic, _, _ = _fraction_arrays(reference)
    reference_at_base = reference_dynamic[::TIME_REFERENCE_SUBDIVISION]
    records: list[dict[str, object]] = []
    for subdivision in TIME_SUBDIVISIONS:
        fields = _atomic_fields(_subdivide_fields(base, subdivision), energy_points)
        case = _solve_case(fields, CONVERGENCE_DILUTION)
        dynamic, _, _ = _fraction_arrays(case)
        error = float(np.max(np.abs(dynamic[::subdivision] - reference_at_base)))
        records.append(
            {
                "control": "orbit_time_subdivision",
                "species": "H/He fractions",
                "resolution": 128 * subdivision,
                "observable": "maximum_absolute_fraction_error",
                "error": error,
            }
        )
    return records


def _source_convergence_records(energy_points: int) -> list[dict[str, object]]:
    cases = {
        points: _solve_case(
            _atomic_fields(_background_fields(points), energy_points),
            CONVERGENCE_DILUTION,
        )
        for points in (*SOURCE_PHASE_POINTS, SOURCE_REFERENCE_POINTS)
    }
    reference = cases[SOURCE_REFERENCE_POINTS]
    reference_dynamic, _, _ = _fraction_arrays(reference)
    reference_phase = np.asarray(reference["phase"])
    records: list[dict[str, object]] = []
    for points in SOURCE_PHASE_POINTS:
        case = cases[points]
        dynamic, _, _ = _fraction_arrays(case)
        errors = []
        for species in range(dynamic.shape[1]):
            interpolated = np.interp(
                reference_phase,
                case["phase"],
                dynamic[:, species],
                period=1.0,
            )
            errors.append(
                float(np.sqrt(np.mean((interpolated - reference_dynamic[:, species]) ** 2)))
            )
        records.append(
            {
                "control": "zo_source_phase_grid",
                "species": "H/He fractions",
                "resolution": int(points),
                "observable": "maximum_fraction_rms_error",
                "error": max(errors),
            }
        )
    return records


def _orbit_records(cases: dict[float, dict[str, object]]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for dilution, case in cases.items():
        dynamic, steady, lte = _fraction_arrays(case)
        for index, phase in enumerate(case["phase"]):
            records.append(
                {
                    "dilution_factor": dilution,
                    "phase_index": index,
                    "orbital_time_phase": float(phase),
                    "gamma_h_i_s1": float(case["photoionization_s1"][index, 0]),
                    "gamma_he_i_s1": float(case["photoionization_s1"][index, 1]),
                    "gamma_he_ii_s1": float(case["photoionization_s1"][index, 2]),
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


def _sensitivity_records(
    cases: dict[float, dict[str, object]], zero_dynamic: np.ndarray
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for dilution, case in cases.items():
        dynamic, steady, lte = _fraction_arrays(case)
        records.append(
            {
                "dilution_factor": dilution,
                "maximum_dynamic_minus_instantaneous_fraction": float(
                    np.max(np.abs(dynamic - steady))
                ),
                "maximum_dynamic_change_from_zero_field": float(
                    np.max(np.abs(dynamic - zero_dynamic))
                ),
                "maximum_instantaneous_minus_lte_fraction": float(
                    np.max(np.abs(steady - lte))
                ),
                "orbit_mean_h_ii_fraction": float(np.mean(dynamic[:, 0])),
                "orbit_mean_he_i_fraction": float(np.mean(dynamic[:, 1])),
                "orbit_mean_he_ii_fraction": float(np.mean(dynamic[:, 2])),
                "orbit_mean_he_iii_fraction": float(np.mean(dynamic[:, 3])),
                "cycles": case["solution"].cycles,
                "cycle_residual": case["solution"].cycle_residual,
                "maximum_relative_charge_residual": case[
                    "solution"
                ].maximum_relative_charge_residual,
            }
        )
    return records


def _plot_main(
    path: Path,
    fields: dict[str, object],
    detailed_balance_case: dict[str, object],
    cases: dict[float, dict[str, object]],
    sensitivity: list[dict[str, object]],
) -> None:
    phase = np.asarray(fields["phase"])
    figure, axes = plt.subplots(2, 2, figsize=(11.7, 8.2), constrained_layout=True)
    for species, label in enumerate(("H I", "He I", "He II")):
        axes[0, 0].semilogy(
            phase,
            fields["unit_photoionization_s1"][:, species],
            label=label,
        )
    axes[0, 0].set(
        xlabel="Orbital time phase",
        ylabel=r"Undiluted photoionization rate (s$^{-1}$)",
        title="(a) Prescribed same-temperature Planck field",
    )
    axes[0, 0].legend(fontsize=8)

    dynamic_db, steady_db, lte_db = _fraction_arrays(detailed_balance_case)
    instantaneous_gap = np.max(np.abs(steady_db - lte_db), axis=1)
    dynamic_gap = np.max(np.abs(dynamic_db - lte_db), axis=1)
    positive_instantaneous = instantaneous_gap > 0.0
    positive_dynamic = dynamic_gap > 0.0
    axes[0, 1].semilogy(
        phase[positive_instantaneous],
        instantaneous_gap[positive_instantaneous],
        label="Instantaneous detailed balance minus LTE",
    )
    axes[0, 1].semilogy(
        phase[positive_dynamic],
        dynamic_gap[positive_dynamic],
        label="Dynamic detailed balance minus LTE",
    )
    axes[0, 1].set(
        xlabel="Orbital time phase",
        ylabel="Maximum absolute ion-fraction difference",
        title="(b) Thermal detailed-balance control",
    )
    axes[0, 1].legend(fontsize=8)

    for dilution in PLOT_DILUTIONS:
        dynamic, _, _ = _fraction_arrays(cases[dilution])
        axes[1, 0].plot(
            phase,
            dynamic[:, 3],
            label=f"W = {dilution:g}",
        )
    axes[1, 0].set(
        xlabel="Orbital time phase",
        ylabel="Dynamic He III fraction",
        title="(c) Prescribed-field dilution sensitivity",
        ylim=(-0.03, 1.03),
    )
    axes[1, 0].legend(fontsize=8)

    positive = [record for record in sensitivity if record["dilution_factor"] > 0.0]
    axes[1, 1].loglog(
        [record["dilution_factor"] for record in positive],
        [record["maximum_dynamic_change_from_zero_field"] for record in positive],
        "o-",
        label="Change from zero-field orbit",
    )
    axes[1, 1].loglog(
        [record["dilution_factor"] for record in positive],
        [record["maximum_dynamic_minus_instantaneous_fraction"] for record in positive],
        "s--",
        label="Dynamic lag",
    )
    axes[1, 1].set(
        xlabel="Dilution factor W",
        ylabel="Maximum absolute ion-fraction difference",
        title="(d) Radiation sensitivity versus kinetic lag",
    )
    axes[1, 1].legend(fontsize=8)
    for axis in axes.flat:
        axis.grid(alpha=0.25)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_convergence(path: Path, records: list[dict[str, object]]) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(14.2, 4.2), constrained_layout=True)
    frequency = [
        record
        for record in records
        if record["control"] == "photoionization_frequency_grid"
    ]
    for label in ("H I", "He I", "He II"):
        selected = [record for record in frequency if record["species"] == label]
        axes[0].loglog(
            [record["resolution"] for record in selected],
            [record["error"] for record in selected],
            "o-",
            label=label,
        )
    axes[0].set(
        xlabel="Base energy-grid points",
        ylabel="Maximum relative rate error",
        title="(a) Photoionization frequency convergence",
    )
    axes[0].set_xticks(
        FREQUENCY_GRID_POINTS,
        labels=[str(value) for value in FREQUENCY_GRID_POINTS],
        rotation=30,
    )
    axes[0].xaxis.set_minor_formatter(NullFormatter())
    axes[0].legend(fontsize=8)
    controls = (
        ("orbit_time_subdivision", axes[1], "(b) Orbit time-step convergence", "Time points per orbit"),
        ("zo_source_phase_grid", axes[2], "(c) ZO source-grid convergence", "Source phase points"),
    )
    for control, axis, title, xlabel in controls:
        selected = [record for record in records if record["control"] == control]
        axis.loglog(
            [record["resolution"] for record in selected],
            [record["error"] for record in selected],
            "o-",
        )
        axis.set(xlabel=xlabel, ylabel="Absolute fraction error", title=title)
        ticks = [record["resolution"] for record in selected]
        axis.set_xticks(ticks, labels=[str(value) for value in ticks])
        axis.xaxis.set_minor_formatter(NullFormatter())
    for axis in axes:
        axis.grid(alpha=0.25)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--anomaly-points", type=int, default=1024)
    parser.add_argument("--energy-points", type=int, default=2049)
    arguments = parser.parse_args()
    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    fields = _atomic_fields(
        _background_fields(int(arguments.anomaly_points)), int(arguments.energy_points)
    )
    cases = {
        float(dilution): _solve_case(fields, float(dilution))
        for dilution in DILUTION_SCAN
    }
    zero_dynamic, _, _ = _fraction_arrays(cases[0.0])
    sensitivity = _sensitivity_records(cases, zero_dynamic)

    detailed_balance_case = _solve_case(fields, 1.0, detailed_balance=True)
    dynamic_db, steady_db, lte_db = _fraction_arrays(detailed_balance_case)
    alternative = _solve_case(
        fields,
        CONVERGENCE_DILUTION,
        alternative_initial_condition=True,
    )
    alternative_dynamic, _, _ = _fraction_arrays(alternative)
    reference_dynamic, _, _ = _fraction_arrays(cases[CONVERGENCE_DILUTION])
    initial_condition_difference = float(
        np.max(np.abs(alternative_dynamic - reference_dynamic))
    )

    explicit_zero = _solve_case(
        fields,
        0.0,
        explicit_photoionization=np.zeros_like(fields["unit_photoionization_s1"]),
    )
    explicit_zero_dynamic, _, _ = _fraction_arrays(explicit_zero)
    zero_field_equivalence = float(np.max(np.abs(explicit_zero_dynamic - zero_dynamic)))

    convergence: list[dict[str, object]] = []
    convergence.extend(_frequency_convergence_records(fields))
    convergence.extend(_time_convergence_records(int(arguments.energy_points)))
    convergence.extend(_source_convergence_records(int(arguments.energy_points)))
    frequency_2049 = max(
        record["error"]
        for record in convergence
        if record["control"] == "photoionization_frequency_grid"
        and record["resolution"] == 2049
    )
    time_1024 = next(
        record["error"]
        for record in convergence
        if record["control"] == "orbit_time_subdivision"
        and record["resolution"] == 1024
    )
    source_1024 = next(
        record["error"]
        for record in convergence
        if record["control"] == "zo_source_phase_grid"
        and record["resolution"] == 1024
    )

    report = {
        "phase": "7B4c",
        "classification": "[A-control/A-sensitivity/V/O] prescribed-radiation ground-state H/He kinetics",
        "physical_inputs": {
            "zo_source_modified": False,
            "radial_index": 8,
            "anomaly_points": int(arguments.anomaly_points),
            "radiation_field": "[A-control] J_nu(t) = W B_nu[T_gray_midplane(t)]",
            "dilution_scan": [float(value) for value in DILUTION_SCAN],
            "energy_range_ev": [1.0, 5000.0],
            "base_energy_points": int(arguments.energy_points),
            "photoionization": "Verner et al. 1996 H I, He I and He II ground-state fits",
            "physical_recombination_sensitivity": "Verner and Ferland 1996 total RR fits",
            "thermal_detailed_balance_inverse": "[A-control] alpha_i = Gamma_i / S_i(T)",
        },
        "validation": {
            "zero_field_maximum_fraction_difference_from_explicit_zero_rates": zero_field_equivalence,
            "thermal_detailed_balance_instantaneous_maximum_fraction_error_from_lte": float(
                np.max(np.abs(steady_db - lte_db))
            ),
            "thermal_detailed_balance_dynamic_maximum_fraction_difference_from_lte": float(
                np.max(np.abs(dynamic_db - lte_db))
            ),
            "positive_initial_condition_independence_error_at_w_1e-4": initial_condition_difference,
            "maximum_relative_charge_residual": max(
                case["solution"].maximum_relative_charge_residual
                for case in (*cases.values(), detailed_balance_case, alternative)
            ),
            "maximum_particle_conservation_residual": max(
                case["solution"].maximum_particle_conservation_residual
                for case in (*cases.values(), detailed_balance_case, alternative)
            ),
        },
        "prescribed_field_response": {
            "maximum_dynamic_change_between_w_0_and_w_1": float(
                np.max(np.abs(_fraction_arrays(cases[1.0])[0] - zero_dynamic))
            ),
            "orbit_mean_fractions_by_dilution": sensitivity,
            "maximum_alpha_detailed_balance_to_physical_rr_ratio": float(
                np.max(
                    fields["radiative_detailed_balance_cm3_s"]
                    / fields["radiative_physical_cm3_s"]
                )
            ),
            "minimum_alpha_detailed_balance_to_physical_rr_ratio": float(
                np.min(
                    fields["radiative_detailed_balance_cm3_s"]
                    / fields["radiative_physical_cm3_s"]
                )
            ),
        },
        "convergence": {
            "photoionization_2049_vs_8193_maximum_relative_rate_error": frequency_2049,
            "orbit_time_1024_vs_2048_maximum_fraction_error": time_1024,
            "source_phase_1024_vs_2048_maximum_fraction_rms_error": source_1024,
        },
        "scientific_boundary": {
            "radiation_population_coupling": "prescribed, not self-consistent",
            "physical_nlte_spectrum_produced": False,
            "radiative_transfer_solution_used_as_j_nu": False,
            "gas_energy_equation_solved": False,
            "excited_levels_included": False,
            "interpretation": "dilution dependence is a controlled sensitivity, not a physical irradiation prediction",
            "next_stage": "Phase 7B4d self-consistent J_nu-population iteration control before any energy equation or spectrum",
        },
    }

    _write_csv(output_dir / "phase7b4c_prescribed_radiation_orbits.csv", _orbit_records(cases))
    _write_csv(output_dir / "phase7b4c_dilution_sensitivity.csv", sensitivity)
    _write_csv(output_dir / "phase7b4c_convergence.csv", convergence)
    (output_dir / "phase7b4c_prescribed_radiation_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _plot_main(
        output_dir / "phase7b4c_prescribed_radiation_kinetics.png",
        fields,
        detailed_balance_case,
        cases,
        sensitivity,
    )
    _plot_convergence(
        output_dir / "phase7b4c_prescribed_radiation_convergence.png",
        convergence,
    )


if __name__ == "__main__":
    main()
