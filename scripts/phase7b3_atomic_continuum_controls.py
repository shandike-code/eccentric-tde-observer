"""生成 Phase 7B3 最小 H/He 原子率与静态频率耦合证据。"""

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
    H_HE_GROUND_STATE_PHOTOIONIZATION_FITS,
    HE_I_RECOMBINATION_FIT,
    HE_I_VERNER_FIT,
    HE_II_RECOMBINATION_FIT,
    HE_II_VERNER_FIT,
    H_I_RECOMBINATION_FIT,
    H_I_VERNER_FIT,
    detailed_balance_recombination_coefficient_cm3_s,
    ground_state_saha_factor_cm3,
    photoionization_rate_from_fit_s1,
    photoionization_recombination_equilibrium,
    traceable_lte_h_he_continuum_opacity_cm2_g,
)
from eccentric_tde_observer.atmosphere import PROTON_MASS_G, SOLAR_FULLY_IONIZED_H_HE
from eccentric_tde_observer.dynamic_column import build_zo_periodic_column_background
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.phase7a import select_quasi_static_representative_annuli
from eccentric_tde_observer.radiation import PLANCK_ERG_S, planck_nu
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
    isothermal_absorption_top_flux,
    solve_static_slab_transfer,
)
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model


PHOTO_GRID_POINTS = (129, 257, 513, 1025, 2049)
ANGLE_ORDERS = (8, 16, 32, 64)
VERTICAL_POINTS = (33, 65, 129, 257)


def _write_csv(path: Path, records: list[dict[str, object]]) -> None:
    if not records:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def _energy_grid(minimum_ev: float, maximum_ev: float, points: int) -> np.ndarray:
    base = np.geomspace(minimum_ev, maximum_ev, int(points))
    thresholds = np.array(
        [fit.threshold_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS]
    )
    within = thresholds[(thresholds >= minimum_ev) & (thresholds <= maximum_ev)]
    # 中文：把离化边精确插入网格，避免用跨越不连续点的梯形近似掩盖网格误差。
    return np.unique(np.concatenate((base, within)))


def _cross_section_records() -> tuple[list[dict[str, object]], dict[str, np.ndarray]]:
    energy = _energy_grid(1.0, 1000.0, 801)
    records: list[dict[str, object]] = []
    values: dict[str, np.ndarray] = {"energy_ev": energy}
    cross_sections = {
        fit.ion_label: fit.cross_section_cm2(energy)
        for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
    }
    values.update(cross_sections)
    for index, photon_energy in enumerate(energy):
        records.append(
            {
                "photon_energy_ev": float(photon_energy),
                "h_i_cross_section_cm2": float(cross_sections["H I"][index]),
                "he_i_cross_section_cm2": float(cross_sections["He I"][index]),
                "he_ii_cross_section_cm2": float(cross_sections["He II"][index]),
            }
        )
    return records, values


def _recombination_records() -> tuple[list[dict[str, object]], dict[str, np.ndarray]]:
    temperature = np.geomspace(3.0, 1.0e6, 401)
    values = {
        "temperature_k": temperature,
        "H I": H_I_RECOMBINATION_FIT.coefficient_cm3_s(temperature),
        "He I": HE_I_RECOMBINATION_FIT.coefficient_cm3_s(temperature),
        "He II": HE_II_RECOMBINATION_FIT.coefficient_cm3_s(temperature),
    }
    records = [
        {
            "temperature_k": float(temperature[index]),
            "h_ii_to_h_i_cm3_s": float(values["H I"][index]),
            "he_ii_to_he_i_cm3_s": float(values["He I"][index]),
            "he_iii_to_he_ii_cm3_s": float(values["He II"][index]),
        }
        for index in range(temperature.size)
    ]
    return records, values


def _physical_photoequilibrium() -> tuple[list[dict[str, object]], dict[str, object]]:
    radiation_temperature = 6.0e4
    gas_temperature = 2.0e4
    hydrogen = 1.0e10
    helium = 1.0e9
    energy = _energy_grid(1.0, 5000.0, 4097)
    frequency = energy * EV_ERG / PLANCK_ERG_S
    planck = planck_nu(frequency, radiation_temperature)
    base_rates = {
        fit.ion_label: photoionization_rate_from_fit_s1(frequency, planck, fit)
        for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
    }
    alpha_h = float(H_I_RECOMBINATION_FIT.coefficient_cm3_s(gas_temperature))
    alpha_he1 = float(HE_I_RECOMBINATION_FIT.coefficient_cm3_s(gas_temperature))
    alpha_he2 = float(HE_II_RECOMBINATION_FIT.coefficient_cm3_s(gas_temperature))
    dilution = np.geomspace(1.0e-10, 1.0, 121)
    records: list[dict[str, object]] = []
    for value in dilution:
        state = photoionization_recombination_equilibrium(
            hydrogen,
            helium,
            value * base_rates["H I"],
            value * base_rates["He I"],
            value * base_rates["He II"],
            alpha_h,
            alpha_he1,
            alpha_he2,
        )
        records.append(
            {
                "dilution_factor": float(value),
                "electron_density_cm3": float(state.electron_density_cm3),
                "h_i_fraction": float(state.hydrogen_neutral_fraction),
                "h_ii_fraction": float(state.hydrogen_ionized_fraction),
                "he_i_fraction": float(state.helium_neutral_fraction),
                "he_ii_fraction": float(state.helium_singly_ionized_fraction),
                "he_iii_fraction": float(state.helium_doubly_ionized_fraction),
                "charge_residual_cm3": state.maximum_charge_residual_cm3,
            }
        )
    summary = {
        "classification": "[A-control/L/V] diluted-Planck fixed-field photoionization equilibrium",
        "radiation_temperature_k": radiation_temperature,
        "gas_temperature_k": gas_temperature,
        "hydrogen_nuclei_cm3": hydrogen,
        "helium_nuclei_cm3": helium,
        "undiluted_photoionization_rates_s1": base_rates,
        "recombination_coefficients_cm3_s": {
            "H II to H I": alpha_h,
            "He II to He I": alpha_he1,
            "He III to He II": alpha_he2,
        },
        "maximum_charge_residual_relative_to_maximum_electron_density": max(
            record["charge_residual_cm3"] for record in records
        ) / (hydrogen + 2.0 * helium),
    }
    return records, summary


def _detailed_balance_control() -> dict[str, float | str]:
    density = 1.0e-10
    temperature = 1.5e4
    composition = SOLAR_FULLY_IONIZED_H_HE
    hydrogen = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium = composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    gamma = (0.7, 1.1, 0.9)
    saha_factors = (
        ground_state_saha_factor_cm3(temperature, 13.59843449),
        ground_state_saha_factor_cm3(temperature, 24.587389),
        ground_state_saha_factor_cm3(temperature, 54.417765),
    )
    state = photoionization_recombination_equilibrium(
        hydrogen,
        helium,
        *gamma,
        *(
            detailed_balance_recombination_coefficient_cm3_s(rate, factor)
            for rate, factor in zip(gamma, saha_factors)
        ),
    )
    saha = lte_hydrogen_helium_ionization(density, temperature, composition)
    fields = (
        "electron_density_cm3",
        "hydrogen_neutral_fraction",
        "hydrogen_ionized_fraction",
        "helium_neutral_fraction",
        "helium_singly_ionized_fraction",
        "helium_doubly_ionized_fraction",
    )
    differences = [
        float(np.max(np.abs(getattr(state, field) - getattr(saha, field))))
        for field in fields
    ]
    electron_relative = abs(
        float(state.electron_density_cm3 / saha.electron_density_cm3 - 1.0)
    )
    return {
        "classification": "[A-control/V] reverse rates constructed from the same Saha factors",
        "temperature_k": temperature,
        "density_g_cm3": density,
        "maximum_fraction_absolute_error": max(differences[1:]),
        "electron_density_relative_error": electron_relative,
        "warning": "constructed detailed-balance rates are a control, not the Verner-Ferland physical RR coefficients",
    }


def _static_transfer_control(
    angular_order: int = 64,
) -> tuple[list[dict[str, object]], dict[str, object], dict[str, np.ndarray]]:
    temperature = 2.0e4
    density = 1.0e-10
    column_mass = 1.0e-3
    thickness = column_mass / density
    energy = _energy_grid(0.5, 300.0, 513)
    frequency = energy * EV_ERG / PLANCK_ERG_S
    opacity = traceable_lte_h_he_continuum_opacity_cm2_g(
        density, temperature, frequency
    )
    extinction = density * opacity.absorption_total_cm2_g
    source = planck_nu(frequency, temperature)
    mu, weight = gauss_legendre_mu_weights(angular_order)
    result = solve_static_slab_transfer(
        frequency,
        np.linspace(0.0, thickness, 17),
        mu,
        weight,
        extinction[:, None],
        source[:, None],
        1.0,
    )
    numerical = -result.top_net_flux
    analytic = np.array(
        [
            isothermal_absorption_top_flux(
                source[index], extinction[index] * thickness
            )
            for index in range(energy.size)
        ]
    )
    records = [
        {
            "photon_energy_ev": float(energy[index]),
            "frequency_hz": float(frequency[index]),
            "absorption_opacity_cm2_g": float(opacity.absorption_total_cm2_g[index]),
            "total_absorption_depth": float(extinction[index] * thickness),
            "numerical_top_flux_cgs_per_hz": float(numerical[index]),
            "analytic_top_flux_cgs_per_hz": float(analytic[index]),
            "normalized_numerical_flux": float(numerical[index] / (np.pi * source[index])),
            "normalized_analytic_flux": float(analytic[index] / (np.pi * source[index])),
            "relative_energy_balance_residual": float(
                result.relative_energy_balance_residual[index]
            ),
        }
        for index in range(energy.size)
    ]
    summary = {
        "classification": "[A-control/L/V] isothermal LTE pure-absorption slab with traceable H/He opacity",
        "temperature_k": temperature,
        "density_g_cm3": density,
        "column_mass_g_cm2": column_mass,
        "angular_order": angular_order,
        "maximum_relative_flux_error": float(
            np.max(np.abs(numerical / analytic - 1.0))
        ),
        "maximum_relative_energy_balance_residual": float(
            np.max(result.relative_energy_balance_residual)
        ),
        "is_output_spectrum": False,
    }
    values = {
        "energy_ev": energy,
        "numerical_normalized": numerical / (np.pi * source),
        "analytic_normalized": analytic / (np.pi * source),
    }
    return records, summary, values


def _zo_effective_depth(
    model,
    representative_index: int,
    energy_ev: np.ndarray,
    vertical_points: int,
) -> tuple[np.ndarray, dict[str, object]]:
    selection = select_quasi_static_representative_annuli(model, count=12)
    radial_index = int(selection.radial_index[representative_index])
    anomaly_index = int(selection.anomaly_index[representative_index])
    background = build_zo_periodic_column_background(model, radial_index)
    sigma = float(background.surface_density_g_cm2[anomaly_index])
    height = float(background.scale_height_cm[anomaly_index])
    effective_temperature = float(background.effective_temperature_k[anomaly_index])
    profile = background.vertical_profile
    scaled_height = np.linspace(profile.surface_scaled_height, 0.0, vertical_points)
    density = sigma / height * profile.density_shape(scaled_height)
    upper_fraction = profile.upper_column_fraction(scaled_height)
    gray_depth = model.parameters.opacity_cm2_g * sigma * upper_fraction
    temperature = effective_temperature * (0.75 * (gray_depth + 2.0 / 3.0)) ** 0.25
    frequency = energy_ev * EV_ERG / PLANCK_ERG_S
    opacity = traceable_lte_h_he_continuum_opacity_cm2_g(
        density[1:, None], temperature[1:, None], frequency[None, :]
    )
    integrand = np.zeros((vertical_points, energy_ev.size), dtype=np.float64)
    integrand[1:] = (
        height
        * density[1:, None]
        * np.sqrt(
            3.0
            * opacity.absorption_total_cm2_g
            * (opacity.absorption_total_cm2_g + opacity.electron_scattering_cm2_g)
        )
    )
    effective_depth = np.trapezoid(integrand, -scaled_height, axis=0)
    if not np.all(np.isfinite(effective_depth)) or np.any(effective_depth < 0.0):
        raise ArithmeticError("ZO traceable effective-depth integration became invalid")
    metadata = {
        "phase7a_representative_index": representative_index,
        "radial_index": radial_index,
        "anomaly_index": anomaly_index,
        "eccentric_anomaly_rad": float(background.eccentric_anomaly_rad[anomaly_index]),
        "surface_density_g_cm2": sigma,
        "scale_height_cm": height,
        "effective_temperature_k": effective_temperature,
        "vertical_points": vertical_points,
        "temperature_closure": "[A] gray Eddington profile retained only for opacity audit",
    }
    return effective_depth, metadata


def _convergence_controls(model, representative_index: int) -> tuple[list[dict[str, object]], dict[str, object]]:
    records: list[dict[str, object]] = []
    radiation_temperature = 6.0e4
    reference_energy = _energy_grid(1.0, 5000.0, 8193)
    reference_frequency = reference_energy * EV_ERG / PLANCK_ERG_S
    reference_planck = planck_nu(reference_frequency, radiation_temperature)
    reference_rates = {
        fit.ion_label: photoionization_rate_from_fit_s1(
            reference_frequency, reference_planck, fit
        )
        for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
    }
    for points in PHOTO_GRID_POINTS:
        energy = _energy_grid(1.0, 5000.0, points)
        frequency = energy * EV_ERG / PLANCK_ERG_S
        intensity = planck_nu(frequency, radiation_temperature)
        for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS:
            rate = photoionization_rate_from_fit_s1(frequency, intensity, fit)
            records.append(
                {
                    "control": "photoionization_frequency_grid",
                    "species": fit.ion_label,
                    "grid_points": points,
                    "observable": "photoionization_rate_s1",
                    "value": rate,
                    "relative_error": abs(rate / reference_rates[fit.ion_label] - 1.0),
                }
            )

    _, _, baseline = _static_transfer_control(64)
    analytic = baseline["analytic_normalized"]
    for order in ANGLE_ORDERS:
        _, _, values = _static_transfer_control(order)
        error = float(
            np.max(np.abs(values["numerical_normalized"] - analytic))
        )
        records.append(
            {
                "control": "physical_opacity_transfer_angle",
                "species": "H/He LTE continuum",
                "grid_points": order,
                "observable": "maximum_normalized_flux_absolute_error",
                "value": error,
                "relative_error": error,
            }
        )

    zo_energy = _energy_grid(1.0, 1000.0, 513)
    reference_depth, metadata = _zo_effective_depth(
        model, representative_index, zo_energy, 513
    )
    reference_norm = float(np.linalg.norm(reference_depth))
    for points in VERTICAL_POINTS:
        depth, _ = _zo_effective_depth(model, representative_index, zo_energy, points)
        error = float(np.linalg.norm(depth - reference_depth) / reference_norm)
        records.append(
            {
                "control": "zo_effective_depth_vertical_grid",
                "species": "H/He LTE continuum",
                "grid_points": points,
                "observable": "full_spectrum_l2_relative_error",
                "value": float(np.linalg.norm(depth)),
                "relative_error": error,
            }
        )
    return records, {"zo_energy_ev": zo_energy, "zo_effective_depth": reference_depth, **metadata}


def _plot(
    path: Path,
    cross_sections: dict[str, np.ndarray],
    recombination: dict[str, np.ndarray],
    equilibrium_records: list[dict[str, object]],
    transfer: dict[str, np.ndarray],
    zo_data: dict[str, object],
    convergence: list[dict[str, object]],
) -> None:
    figure, axes = plt.subplots(2, 3, figsize=(15.0, 8.7), constrained_layout=True)
    for species in ("H I", "He I", "He II"):
        sigma = cross_sections[species]
        positive = sigma > 0.0
        axes[0, 0].loglog(cross_sections["energy_ev"][positive], sigma[positive], label=species)
    axes[0, 0].set(
        xlabel="Photon energy (eV)",
        ylabel=r"Photoionization cross section (cm$^2$)",
        title="(a) Verner ground-state photoionization fits",
    )
    axes[0, 0].legend()

    for species in ("H I", "He I", "He II"):
        axes[0, 1].loglog(
            recombination["temperature_k"], recombination[species], label=species
        )
    axes[0, 1].set(
        xlabel="Gas temperature (K)",
        ylabel=r"Radiative recombination coefficient (cm$^3$ s$^{-1}$)",
        title="(b) Verner--Ferland total recombination fits",
    )
    axes[0, 1].legend()

    dilution = np.array([record["dilution_factor"] for record in equilibrium_records])
    for key, label in (
        ("h_ii_fraction", "H II"),
        ("he_i_fraction", "He I"),
        ("he_ii_fraction", "He II"),
        ("he_iii_fraction", "He III"),
    ):
        axes[0, 2].semilogx(
            dilution, [record[key] for record in equilibrium_records], label=label
        )
    axes[0, 2].set(
        xlabel="Dilution factor W",
        ylabel="Ion fraction",
        title="(c) Fixed-field photoionization equilibrium control",
        ylim=(-0.03, 1.03),
    )
    axes[0, 2].legend()

    axes[1, 0].semilogx(
        transfer["energy_ev"], transfer["numerical_normalized"], label="Numerical"
    )
    axes[1, 0].semilogx(
        transfer["energy_ev"], transfer["analytic_normalized"], "--", label="Analytic"
    )
    axes[1, 0].set(
        xlabel="Photon energy (eV)",
        ylabel=r"Emergent flux / ($\pi B_\nu$)",
        title="(d) LTE pure-absorption slab control",
        ylim=(-0.03, 1.03),
    )
    axes[1, 0].legend()

    axes[1, 1].loglog(
        zo_data["zo_energy_ev"], zo_data["zo_effective_depth"], color="tab:purple"
    )
    axes[1, 1].axhline(1.0, color="black", linestyle="--", linewidth=1.0, label=r"$\tau_{\rm eff}=1$")
    axes[1, 1].set(
        xlabel="Photon energy (eV)",
        ylabel="Effective optical depth to midplane",
        title="(e) Prescribed ZO column opacity audit",
    )
    axes[1, 1].legend()

    styles = {
        "photoionization_frequency_grid": ("o-", "Photoionization frequency grid"),
        "physical_opacity_transfer_angle": ("s-", "Transfer angular quadrature"),
        "zo_effective_depth_vertical_grid": ("^-", "ZO vertical grid"),
    }
    for control, (style, label) in styles.items():
        selected = [record for record in convergence if record["control"] == control]
        if control == "photoionization_frequency_grid":
            selected = [record for record in selected if record["species"] == "He I"]
        axes[1, 2].loglog(
            [record["grid_points"] for record in selected],
            [record["relative_error"] for record in selected],
            style,
            label=label,
        )
    axes[1, 2].set(
        xlabel="Grid points / angular order",
        ylabel="Relative or absolute error",
        title="(f) Independent convergence controls",
    )
    axes[1, 2].legend(fontsize=8)

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

    model = build_strict_domain_reference_model(
        arguments.radial_points, arguments.anomaly_points
    )
    cross_section_records, cross_sections = _cross_section_records()
    recombination_records, recombination = _recombination_records()
    equilibrium_records, equilibrium_summary = _physical_photoequilibrium()
    detailed_balance = _detailed_balance_control()
    transfer_records, transfer_summary, transfer = _static_transfer_control()
    convergence, zo_data = _convergence_controls(
        model, int(arguments.representative_index)
    )
    zo_records = [
        {
            "photon_energy_ev": float(zo_data["zo_energy_ev"][index]),
            "effective_optical_depth_to_midplane": float(
                zo_data["zo_effective_depth"][index]
            ),
        }
        for index in range(len(zo_data["zo_energy_ev"]))
    ]

    acceptance = {
        "detailed_balance_maximum_fraction_absolute_error": detailed_balance[
            "maximum_fraction_absolute_error"
        ],
        "detailed_balance_electron_density_relative_error": detailed_balance[
            "electron_density_relative_error"
        ],
        "photoionization_rate_maximum_relative_error_at_2049_points": max(
            record["relative_error"]
            for record in convergence
            if record["control"] == "photoionization_frequency_grid"
            and record["grid_points"] == 2049
        ),
        "transfer_maximum_normalized_flux_error_order64": next(
            record["relative_error"]
            for record in convergence
            if record["control"] == "physical_opacity_transfer_angle"
            and record["grid_points"] == 64
        ),
        "zo_effective_depth_l2_relative_error_257_vs_513": next(
            record["relative_error"]
            for record in convergence
            if record["control"] == "zo_effective_depth_vertical_grid"
            and record["grid_points"] == 257
        ),
        "maximum_photoequilibrium_charge_relative_residual": equilibrium_summary[
            "maximum_charge_residual_relative_to_maximum_electron_density"
        ],
        "maximum_transfer_energy_residual": transfer_summary[
            "maximum_relative_energy_balance_residual"
        ],
    }
    report = {
        "phase": "7B3",
        "classification": "[L/A/V/O] traceable H/He continuum atomic rates and static coupling controls",
        "atomic_data": {
            "photoionization": "Verner et al. 1996 ground-state fits; official photo.dat H I, He I, He II rows",
            "radiative_recombination": "Verner and Ferland 1996 total RR fits; low-temperature He I branch",
            "included": [
                "H I, He I and He II ground-state photoionization",
                "H II->H I, He II->He I and He III->He II total radiative recombination",
                "LTE free-free and electron scattering",
            ],
            "not_included": [
                "excited levels and bound-bound transitions",
                "collisional ionization and three-body recombination",
                "line transfer and line blanketing",
                "metal opacity",
                "Compton redistribution",
            ],
        },
        "detailed_balance_control": detailed_balance,
        "fixed_field_photoequilibrium": equilibrium_summary,
        "static_transfer_control": transfer_summary,
        "zo_representative_opacity_audit": {
            key: value
            for key, value in zo_data.items()
            if key not in ("zo_energy_ev", "zo_effective_depth")
        },
        "acceptance": acceptance,
        "scientific_boundary": {
            "physical_nlte_spectrum_produced": False,
            "zo_heating_depth_profile_solved": False,
            "gas_energy_equation_solved": False,
            "orbital_time_dependent_rates_coupled": False,
            "next_stage": "Phase 7B4 only after reviewing the unresolved heating and dynamic closures",
        },
    }

    _write_csv(output_dir / "phase7b3_photoionization_cross_sections.csv", cross_section_records)
    _write_csv(output_dir / "phase7b3_recombination_rates.csv", recombination_records)
    _write_csv(output_dir / "phase7b3_photoionization_equilibrium.csv", equilibrium_records)
    _write_csv(output_dir / "phase7b3_static_transfer_spectrum.csv", transfer_records)
    _write_csv(output_dir / "phase7b3_zo_effective_depth.csv", zo_records)
    _write_csv(output_dir / "phase7b3_convergence.csv", convergence)
    (output_dir / "phase7b3_atomic_continuum_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _plot(
        output_dir / "phase7b3_atomic_continuum_controls.png",
        cross_sections,
        recombination,
        equilibrium_records,
        transfer,
        zo_data,
        convergence,
    )


if __name__ == "__main__":
    main()
