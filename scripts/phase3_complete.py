"""Phase 3：非灰失效门、角分辨 Stokes、弱场 GR 像平面与再处理约束。"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eccentric_tde_observer.adaptive import (
    build_orthographic_triangle_index,
    render_adaptive_source_surface_quadrature,
    render_source_surface_quadrature,
    source_surface_blackbody_sed,
)
from eccentric_tde_observer.atmosphere import solve_peak_thermalization_closure
from eccentric_tde_observer.diagnostics import fit_isotropic_blackbody_lnu
from eccentric_tde_observer.faceon import (
    face_on_bolometric_luminosities,
    pre_erratum_face_on_bolometric_luminosities,
)
from eccentric_tde_observer.geometry import build_orbital_surface_mesh
from eccentric_tde_observer.gr_transfer import (
    beloborodov_schwarzschild_direct_image_transfer,
    gr_direct_image_sed,
)
from eccentric_tde_observer.non_gray import (
    HELIUM_I_IONIZATION_ERG,
    HELIUM_II_IONIZATION_ERG,
    HYDROGEN_IONIZATION_ERG,
    lte_non_gray_effective_optical_depth_to_midplane,
)
from eccentric_tde_observer.observer import Observer
from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.polarization import surface_stokes_sed
from eccentric_tde_observer.quadrature import geometric_planar_area_weights
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.reference_case import (
    STRICT_CIRCULARIZATION_EFFICIENCY,
    STRICT_ECCENTRICITY,
    build_strict_domain_reference_model,
)
from eccentric_tde_observer.relativity import (
    homologous_vertical_velocity_cm_s,
    straight_ray_frequency_shift,
)
from eccentric_tde_observer.reprocessing import (
    minimum_seed_luminosity_erg_s,
    minimum_thermalizing_layer_requirement,
    momentum_limited_mass_loss_rate_g_s,
)
from eccentric_tde_observer.vertical import RADIATION_PRESSURE_POLYTROPE_PROFILE
from eccentric_tde_observer.zo_reference import SOLAR_MASS_G


PARSEC_CM = 3.0856775814913673e18
DISTANCE_CM = 100.0e6 * PARSEC_CM
EV_ERG = 1.602176634e-12
SECONDS_PER_DAY = 86400.0
SECONDS_PER_YEAR = 365.25 * SECONDS_PER_DAY
PROBE_FREQUENCY_HZ = np.array([5.0e14, 1.0e15, 2.0e15, 5.0e15, 1.0e16])
PHASE_DEG = tuple(float(value) for value in np.arange(0.0, 360.0, 30.0))
ORIENTATION_CASES = (
    (0.0, 0.0),
    (30.0, 0.0),
    (60.0, 0.0),
    *((75.0, phase) for phase in PHASE_DEG),
)


def _energy_kev_to_frequency_hz(energy_kev: float) -> float:
    return energy_kev * 1.0e3 * EV_ERG / PLANCK_ERG_S


def _write_records(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def _case_label(inclination_deg: float, phase_deg: float) -> str:
    return f"i{int(inclination_deg):02d}_phi{int(phase_deg):03d}"


def _weighted_quantile(
    values: np.ndarray, weights: np.ndarray, quantile: float
) -> float:
    flat_values = np.asarray(values, dtype=np.float64).reshape(-1)
    flat_weights = np.asarray(weights, dtype=np.float64).reshape(-1)
    if flat_values.shape != flat_weights.shape:
        raise ValueError("weighted quantile arrays must have the same shape")
    ordering = np.argsort(flat_values)
    sorted_values = flat_values[ordering]
    cumulative = np.cumsum(flat_weights[ordering])
    target = quantile * cumulative[-1]
    return float(sorted_values[np.searchsorted(cumulative, target, side="left")])


def _integrate_band(
    frequency_hz: np.ndarray,
    luminosity_density: np.ndarray,
    lower_hz: float,
    upper_hz: float,
) -> float:
    selected = (frequency_hz >= lower_hz) & (frequency_hz <= upper_hz)
    if np.count_nonzero(selected) < 2:
        raise RuntimeError("frequency grid does not resolve the requested band")
    result = float(np.trapezoid(luminosity_density[selected], frequency_hz[selected]))
    if not np.isfinite(result) or result < 0.0:
        raise ArithmeticError("band integration produced an invalid luminosity")
    return result


def _photosphere_mesh_velocity(model):
    photosphere = solve_gray_photosphere(
        model.source,
        model.parameters.opacity_cm2_g,
        2.0 / 3.0,
        RADIATION_PRESSURE_POLYTROPE_PROFILE,
    )
    mesh = build_orbital_surface_mesh(model.source, photosphere.height_cm)
    vertical_velocity = homologous_vertical_velocity_cm_s(
        model.source,
        photosphere.height_cm,
        model.breathing.log_height_derivative_per_rad,
        model.parameters.black_hole_mass_msun,
    )
    return photosphere, mesh, vertical_velocity


def _surface_quadrature(mesh, observer, bins_long_axis: int = 256):
    index = build_orthographic_triangle_index(
        mesh, observer, bins_long_axis=bins_long_axis
    )
    quadrature = render_source_surface_quadrature(
        mesh, observer, subdivision_level=0, triangle_index=index
    )
    return index, quadrature


def _non_gray_audit(output_dir: Path) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    threshold_frequency = {
        "H_I": HYDROGEN_IONIZATION_ERG / PLANCK_ERG_S,
        "He_I_approx": HELIUM_I_IONIZATION_ERG / PLANCK_ERG_S,
        "He_II": HELIUM_II_IONIZATION_ERG / PLANCK_ERG_S,
    }
    xray_03 = _energy_kev_to_frequency_hz(0.3)
    frequency = np.unique(
        np.concatenate(
            (
                np.geomspace(1.0e14, 3.0e18, 121),
                [xray_03],
                [factor * value for value in threshold_frequency.values() for factor in (0.999, 1.001)],
            )
        )
    )
    model = build_strict_domain_reference_model(17, 128)
    area_weight = geometric_planar_area_weights(model.source)
    baseline = lte_non_gray_effective_optical_depth_to_midplane(
        model.source,
        frequency,
        vertical_points=65,
        include_helium_i_approximation=False,
    )
    helium_i = lte_non_gray_effective_optical_depth_to_midplane(
        model.source,
        frequency,
        vertical_points=65,
        include_helium_i_approximation=True,
    )

    records: list[dict[str, object]] = []
    diagnostics: dict[str, np.ndarray] = {"frequency_hz": frequency}
    for name, audit in (("H_I_plus_He_II", baseline), ("with_He_I_approx", helium_i)):
        tau = audit.midplane_effective_optical_depth
        weighted_measure = area_weight[..., None] * np.ones_like(tau)
        thick_fraction = np.sum(
            area_weight[..., None] * (tau >= 1.0), axis=(0, 1)
        ) / np.sum(weighted_measure, axis=(0, 1))
        median = np.array(
            [_weighted_quantile(tau[..., i], area_weight, 0.5) for i in range(frequency.size)]
        )
        tenth = np.array(
            [_weighted_quantile(tau[..., i], area_weight, 0.1) for i in range(frequency.size)]
        )
        ninetieth = np.array(
            [_weighted_quantile(tau[..., i], area_weight, 0.9) for i in range(frequency.size)]
        )
        diagnostics[f"{name}_thick_fraction"] = thick_fraction
        diagnostics[f"{name}_tau_p10"] = tenth
        diagnostics[f"{name}_tau_p50"] = median
        diagnostics[f"{name}_tau_p90"] = ninetieth
        for i, nu in enumerate(frequency):
            records.append(
                {
                    "closure": name,
                    "frequency_hz": float(nu),
                    "area_fraction_tau_eff_ge_1": float(thick_fraction[i]),
                    "tau_eff_area_p10": float(tenth[i]),
                    "tau_eff_area_p50": float(median[i]),
                    "tau_eff_area_p90": float(ninetieth[i]),
                }
            )
    _write_records(output_dir / "phase3_non_gray_thermalization.csv", records)

    convergence_frequency = np.unique(
        np.concatenate(
            (
                PROBE_FREQUENCY_HZ,
                [1.001 * value for value in threshold_frequency.values()],
                [xray_03],
            )
        )
    )
    vertical_fine = lte_non_gray_effective_optical_depth_to_midplane(
        model.source,
        convergence_frequency,
        vertical_points=129,
        include_helium_i_approximation=False,
    )
    source_fine_model = build_strict_domain_reference_model(33, 256)
    source_fine = lte_non_gray_effective_optical_depth_to_midplane(
        source_fine_model.source,
        convergence_frequency,
        vertical_points=65,
        include_helium_i_approximation=False,
    )
    coarse_at_probe = lte_non_gray_effective_optical_depth_to_midplane(
        model.source,
        convergence_frequency,
        vertical_points=65,
        include_helium_i_approximation=False,
    )
    fine_area = geometric_planar_area_weights(source_fine_model.source)
    convergence_records = []
    vertical_relative = []
    source_relative = []
    for i, nu in enumerate(convergence_frequency):
        coarse_median = _weighted_quantile(
            coarse_at_probe.midplane_effective_optical_depth[..., i], area_weight, 0.5
        )
        vertical_median = _weighted_quantile(
            vertical_fine.midplane_effective_optical_depth[..., i], area_weight, 0.5
        )
        source_median = _weighted_quantile(
            source_fine.midplane_effective_optical_depth[..., i], fine_area, 0.5
        )
        vertical_change = abs(vertical_median / coarse_median - 1.0)
        source_change = abs(source_median / coarse_median - 1.0)
        vertical_relative.append(vertical_change)
        source_relative.append(source_change)
        convergence_records.append(
            {
                "frequency_hz": float(nu),
                "coarse_tau_p50_17x128_z65": coarse_median,
                "vertical_tau_p50_17x128_z129": vertical_median,
                "source_tau_p50_33x256_z65": source_median,
                "vertical_relative_change": vertical_change,
                "source_relative_change": source_change,
            }
        )
    _write_records(output_dir / "phase3_non_gray_convergence.csv", convergence_records)

    def _fraction_at(audit_key: str, target: float) -> float:
        index = int(np.argmin(np.abs(frequency - target)))
        return float(diagnostics[audit_key][index])

    report = {
        "classification": "[A/V] LTE H/He non-gray opacity audit; not an NLTE atmosphere spectrum",
        "source_grid": [17, 128],
        "vertical_points": 65,
        "frequency_range_hz": [float(frequency[0]), float(frequency[-1])],
        "threshold_frequency_hz": threshold_frequency,
        "area_fraction_thermalized": {
            "baseline_at_1e15Hz": _fraction_at("H_I_plus_He_II_thick_fraction", 1.0e15),
            "baseline_at_HI_edge_above": _fraction_at("H_I_plus_He_II_thick_fraction", 1.001 * threshold_frequency["H_I"]),
            "baseline_at_0p3keV": _fraction_at("H_I_plus_He_II_thick_fraction", xray_03),
            "with_HeI_approx_at_0p3keV": _fraction_at("with_He_I_approx_thick_fraction", xray_03),
        },
        "convergence": {
            "max_vertical_p50_relative_change": float(np.max(vertical_relative)),
            "max_source_grid_p50_relative_change": float(np.max(source_relative)),
            "warning": "edge-adjacent LTE optical depths can be non-monotonic; convergence is diagnostic, not NLTE accuracy",
        },
        "failure_gate": (
            "Davis-Hubeny annulus tables start above this reference source's low-Teff domain; "
            "irradiated H/He populations and metals require NLTE statistical equilibrium. "
            "Therefore this audit may validate opacity sensitivity but cannot validate an X-ray SED."
        ),
    }
    return report, diagnostics


def _observer_transfer_audit(
    output_dir: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    frequency = np.unique(
        np.concatenate((np.geomspace(1.0e14, 1.0e17, 401), PROBE_FREQUENCY_HZ))
    )
    probe_indices = np.searchsorted(frequency, PROBE_FREQUENCY_HZ)
    model = build_strict_domain_reference_model(65, 1024)
    photosphere, mesh, vertical_velocity = _photosphere_mesh_velocity(model)
    hardening = solve_peak_thermalization_closure(
        model.source, vertical_points=257
    ).spectral_hardening_factor
    spectra: dict[tuple[float, float], object] = {}
    straight_spectra: dict[tuple[float, float], object] = {}
    isotropic_spectra: dict[tuple[float, float], object] = {}
    diagnostics: list[dict[str, object]] = []
    audit_objects = None

    for inclination_deg, phase_deg in ORIENTATION_CASES:
        observer = Observer(
            DISTANCE_CM, np.deg2rad(inclination_deg), np.deg2rad(phase_deg)
        )
        index, quadrature = _surface_quadrature(mesh, observer)
        shift = straight_ray_frequency_shift(
            model.source,
            observer,
            model.parameters.black_hole_mass_msun,
            vertical_velocity_cm_s=vertical_velocity,
        )
        stokes = surface_stokes_sed(
            model.source,
            mesh,
            observer,
            quadrature,
            frequency,
            frequency_shift_factor=shift.frequency_shift_factor,
            spectral_hardening_factor=hardening,
        )
        isotropic = source_surface_blackbody_sed(
            model.source,
            mesh,
            observer,
            quadrature,
            frequency,
            frequency_shift_factor=shift.frequency_shift_factor,
            spectral_hardening_factor=hardening,
        )
        transfer = beloborodov_schwarzschild_direct_image_transfer(
            model.source,
            mesh,
            observer,
            model.parameters.black_hole_mass_msun,
            vertical_velocity_cm_s=vertical_velocity,
        )
        gr_spectrum = gr_direct_image_sed(
            model.source,
            mesh,
            observer,
            transfer,
            frequency,
            spectral_hardening_factor=hardening,
        )
        spectra[(inclination_deg, phase_deg)] = gr_spectrum
        straight_spectra[(inclination_deg, phase_deg)] = stokes
        isotropic_spectra[(inclination_deg, phase_deg)] = isotropic

        conservative_fit = fit_isotropic_blackbody_lnu(
            frequency,
            gr_spectrum.isotropic_equivalent_lnu_erg_s_hz,
            5.0e14,
            1.0e15,
        )
        record: dict[str, object] = {
            "inclination_deg": inclination_deg,
            "relative_phase_deg": phase_deg,
            "straight_visible_to_unobscured_area": (
                quadrature.visible_projected_area_cm2
                / quadrature.unobscured_projected_area_cm2
            ),
            "gr_to_straight_image_area": (
                transfer.direct_image_area_cm2
                / quadrature.unobscured_projected_area_cm2
            ),
            "g_min": float(np.min(transfer.frequency_shift_factor)),
            "g_max": float(np.max(transfer.frequency_shift_factor)),
            "conservative_T_bb_k": conservative_fit.temperature_k,
            "conservative_R_bb_cm": conservative_fit.radius_cm,
            "conservative_fit_rms_dex": conservative_fit.rms_log10_residual_dex,
        }
        for probe_index, nu in zip(probe_indices, PROBE_FREQUENCY_HZ, strict=True):
            suffix = f"{nu:.1e}_Hz"
            record[f"GR_Fnu_at_{suffix}"] = float(
                gr_spectrum.flux_density_erg_s_cm2_hz[probe_index]
            )
            record[f"polarization_fraction_at_{suffix}"] = float(
                stokes.polarization_fraction[probe_index]
            )
            record[f"polarization_angle_deg_at_{suffix}"] = float(
                np.rad2deg(stokes.polarization_angle_rad[probe_index])
            )
            record[f"GR_to_straight_limb_at_{suffix}"] = float(
                gr_spectrum.flux_density_erg_s_cm2_hz[probe_index]
                / stokes.flux_i_erg_s_cm2_hz[probe_index]
            )
            record[f"limb_to_isotropic_at_{suffix}"] = float(
                stokes.flux_i_erg_s_cm2_hz[probe_index]
                / isotropic.flux_density_erg_s_cm2_hz[probe_index]
            )
        diagnostics.append(record)
        if inclination_deg == 75.0 and phase_deg == 90.0:
            audit_objects = (observer, index, quadrature, shift, transfer, gr_spectrum)
        print(f"Phase3 observer {_case_label(inclination_deg, phase_deg)} complete", flush=True)

    _write_records(output_dir / "phase3_orientation_diagnostics.csv", diagnostics)
    columns = [frequency]
    header = ["frequency_hz"]
    for inclination_deg, phase_deg in ORIENTATION_CASES:
        label = _case_label(inclination_deg, phase_deg)
        gr_spectrum = spectra[(inclination_deg, phase_deg)]
        stokes = straight_spectra[(inclination_deg, phase_deg)]
        columns.extend(
            (
                gr_spectrum.flux_density_erg_s_cm2_hz,
                stokes.flux_i_erg_s_cm2_hz,
                stokes.flux_q_erg_s_cm2_hz,
                stokes.flux_u_erg_s_cm2_hz,
                stokes.polarization_fraction,
            )
        )
        header.extend(
            (
                f"GR_limb_{label}_Fnu_cgs",
                f"straight_limb_{label}_I_cgs",
                f"straight_limb_{label}_Q_cgs",
                f"straight_limb_{label}_U_cgs",
                f"straight_{label}_polarization_fraction",
            )
        )
    np.savetxt(
        output_dir / "phase3_observer_spectra.csv",
        np.column_stack(columns),
        delimiter=",",
        header=",".join(header),
        comments="",
    )

    if audit_objects is None:
        raise RuntimeError("observer audit orientation was not generated")
    audit_observer, audit_index, audit_quadrature, audit_shift, _, audit_spectrum = audit_objects
    deep_quadrature = render_adaptive_source_surface_quadrature(
        mesh,
        audit_observer,
        maximum_subdivision_depth=2,
        triangle_index=audit_index,
        interior_vertex_fraction=0.01,
    )
    deep_stokes = surface_stokes_sed(
        model.source,
        mesh,
        audit_observer,
        deep_quadrature,
        PROBE_FREQUENCY_HZ,
        frequency_shift_factor=audit_shift.frequency_shift_factor,
        spectral_hardening_factor=hardening,
    )
    main_probe = straight_spectra[(75.0, 90.0)].flux_i_erg_s_cm2_hz[probe_indices]
    depth_change = np.abs(deep_stokes.flux_i_erg_s_cm2_hz / main_probe - 1.0)

    coarse_model = build_strict_domain_reference_model(33, 512)
    _, coarse_mesh, coarse_vertical_velocity = _photosphere_mesh_velocity(coarse_model)
    coarse_hardening = solve_peak_thermalization_closure(
        coarse_model.source, vertical_points=257
    ).spectral_hardening_factor
    coarse_observer = Observer(DISTANCE_CM, np.deg2rad(75.0), np.deg2rad(90.0))
    _, coarse_quadrature = _surface_quadrature(coarse_mesh, coarse_observer, 192)
    coarse_shift = straight_ray_frequency_shift(
        coarse_model.source,
        coarse_observer,
        coarse_model.parameters.black_hole_mass_msun,
        vertical_velocity_cm_s=coarse_vertical_velocity,
    )
    coarse_transfer = beloborodov_schwarzschild_direct_image_transfer(
        coarse_model.source,
        coarse_mesh,
        coarse_observer,
        coarse_model.parameters.black_hole_mass_msun,
        vertical_velocity_cm_s=coarse_vertical_velocity,
    )
    coarse_gr = gr_direct_image_sed(
        coarse_model.source,
        coarse_mesh,
        coarse_observer,
        coarse_transfer,
        PROBE_FREQUENCY_HZ,
        spectral_hardening_factor=coarse_hardening,
    )
    grid_change = np.abs(
        audit_spectrum.flux_density_erg_s_cm2_hz[probe_indices]
        / coarse_gr.flux_density_erg_s_cm2_hz
        - 1.0
    )
    convergence_records = []
    for nu, ray_change, source_change in zip(
        PROBE_FREQUENCY_HZ, depth_change, grid_change, strict=True
    ):
        convergence_records.append(
            {
                "frequency_hz": float(nu),
                "adaptive_depth_0_to_2_relative_change": float(ray_change),
                "source_grid_33x512_to_65x1024_relative_change": float(source_change),
            }
        )
    _write_records(output_dir / "phase3_transfer_convergence.csv", convergence_records)

    i75_records = [record for record in diagnostics if record["inclination_deg"] == 75.0]
    phase_modulation = {}
    for nu in PROBE_FREQUENCY_HZ:
        key = f"GR_Fnu_at_{nu:.1e}_Hz"
        values = np.array([float(record[key]) for record in i75_records])
        phase_modulation[f"{nu:.1e}_Hz"] = float(np.max(values) / np.min(values))
    report = {
        "classification": (
            "[A/V] energy-conserving modified blackbody + Eddington limb law + "
            "straight-ray Chandrasekhar polarization + Cunningham-style weak-field direct image"
        ),
        "source": {
            "eccentricity": STRICT_ECCENTRICITY,
            "circularization_efficiency": STRICT_CIRCULARIZATION_EFFICIENCY,
            "grid": [65, 1024],
            "distance_mpc": 100.0,
        },
        "observer_ranges": {
            "conservative_T_bb_k": [
                float(min(record["conservative_T_bb_k"] for record in diagnostics)),
                float(max(record["conservative_T_bb_k"] for record in diagnostics)),
            ],
            "conservative_R_bb_cm": [
                float(min(record["conservative_R_bb_cm"] for record in diagnostics)),
                float(max(record["conservative_R_bb_cm"] for record in diagnostics)),
            ],
            "polarization_fraction_at_5e14Hz": [
                float(min(record["polarization_fraction_at_5.0e+14_Hz"] for record in diagnostics)),
                float(max(record["polarization_fraction_at_5.0e+14_Hz"] for record in diagnostics)),
            ],
            "gr_to_straight_image_area": [
                float(min(record["gr_to_straight_image_area"] for record in diagnostics)),
                float(max(record["gr_to_straight_image_area"] for record in diagnostics)),
            ],
        },
        "i75_phase_max_to_min": phase_modulation,
        "convergence": {
            "max_adaptive_depth_relative_change": float(np.max(depth_change)),
            "max_source_grid_relative_change": float(np.max(grid_change)),
        },
        "limitations": [
            "polarization uses a conservative scattering atmosphere fit and straight-ray sky orientation",
            "GR direct image uses an approximate Schwarzschild ray map and omits multiple images",
            "curved-ray self-occultation is not implemented; the strict reference source has no straight-ray self-occultation",
            "the plotted local spectrum remains the Phase-2 peak-thermalization modified blackbody, not an NLTE annulus spectrum",
        ],
    }
    plot_data = {
        "frequency": frequency,
        "spectra": spectra,
        "stokes": straight_spectra,
        "diagnostics": diagnostics,
        "probe_indices": probe_indices,
    }
    return report, plot_data


def _reprocessing_audit(
    output_dir: Path, observer_data: dict[str, object]
) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    radius = np.geomspace(1.0e14, 1.0e15, 61)
    epsilon_values = np.array([1.0e-6, 1.0e-5, 1.0e-4, 1.0e-3, 1.0e-2])
    records: list[dict[str, object]] = []
    masses = []
    diffusion = []
    for epsilon in epsilon_values:
        requirement = minimum_thermalizing_layer_requirement(radius, epsilon)
        masses.append(requirement.full_coverage_mass_g / SOLAR_MASS_G)
        diffusion.append(
            requirement.diffusion_time_per_fractional_thickness_s / SECONDS_PER_DAY
        )
        for i, value in enumerate(radius):
            records.append(
                {
                    "radius_cm": float(value),
                    "absorption_fraction_epsilon": float(epsilon),
                    "tau_total_min": float(requirement.total_optical_depth[i]),
                    "surface_density_min_g_cm2": float(requirement.surface_density_g_cm2[i]),
                    "mass_full_coverage_msun": float(requirement.full_coverage_mass_g[i] / SOLAR_MASS_G),
                    "diffusion_days_per_DeltaR_over_R": float(requirement.diffusion_time_per_fractional_thickness_s[i] / SECONDS_PER_DAY),
                }
            )
    _write_records(output_dir / "phase3_reprocessing_constraints.csv", records)

    frequency = observer_data["frequency"]
    spectra = observer_data["spectra"]
    optical_luminosities = []
    for case in ORIENTATION_CASES:
        optical_luminosities.append(
            _integrate_band(
                frequency,
                spectra[case].isotropic_equivalent_lnu_erg_s_hz,
                5.0e14,
                1.0e15,
            )
        )
    hypothetical_reprocessed = float(np.max(optical_luminosities))
    seed_full = float(minimum_seed_luminosity_erg_s(hypothetical_reprocessed, 1.0))
    seed_half = float(minimum_seed_luminosity_erg_s(hypothetical_reprocessed, 0.5))
    momentum_rate = float(
        momentum_limited_mass_loss_rate_g_s(seed_full, 1.0e9)
        * SECONDS_PER_YEAR
        / SOLAR_MASS_G
    )
    report = {
        "classification": "[V/O] constraint map only; no wind or reprocessing layer added",
        "epsilon_grid": epsilon_values.tolist(),
        "radius_range_cm": [float(radius[0]), float(radius[-1])],
        "mass_and_time_scaling": (
            "reported mass is for covering fraction C=1 and scales as C; "
            "reported diffusion time is per fractional thickness DeltaR/R"
        ),
        "hypothetical_energy_bound": {
            "target_optical_luminosity_erg_s": hypothetical_reprocessed,
            "minimum_seed_C1_erg_s": seed_full,
            "minimum_seed_C0p5_erg_s": seed_half,
            "status": "cannot be tested because the bare-disc model has no validated X-ray seed spectrum",
        },
        "momentum_scaling": {
            "Mdot_max_msun_per_year_for_tau_mom1_v1e9": momentum_rate,
            "formula": "Mdot_max scales as tau_mom*(1e9 cm/s / v)*L_seed",
        },
        "decision": (
            "Do not instantiate a reprocessing layer.  First supply a physically validated inner high-energy source "
            "and ionization-dependent opacity; otherwise mass, energy and momentum cannot close simultaneously."
        ),
    }
    plot_data = {
        "radius": radius,
        "epsilon": epsilon_values,
        "mass_msun": np.array(masses),
        "diffusion_days": np.array(diffusion),
    }
    return report, plot_data


def _make_summary_figure(
    output_dir: Path,
    non_gray: dict[str, np.ndarray],
    observer: dict[str, object],
    reprocessing: dict[str, np.ndarray],
) -> None:
    frequency = observer["frequency"]
    spectra = observer["spectra"]
    stokes = observer["stokes"]
    probe_indices = observer["probe_indices"]
    figure, axes = plt.subplots(3, 3, figsize=(17.2, 13.2), constrained_layout=True)
    figure.suptitle(
        "Phase 3: non-gray validity gate, angle-resolved bare disc, and weak-field image transfer",
        fontsize=16,
    )

    axis = axes[0, 0]
    visible_spectral_range = frequency <= 3.0e16
    for inclination in (0.0, 30.0, 60.0, 75.0):
        spectrum = spectra[(inclination, 0.0)]
        axis.loglog(
            frequency[visible_spectral_range],
            frequency[visible_spectral_range]
            * spectrum.flux_density_erg_s_cm2_hz[visible_spectral_range],
            label=f"i={inclination:.0f} deg",
        )
    axis.axvline(1.0e15, color="black", linestyle=":", linewidth=1.0)
    axis.set_xlim(1.0e14, 3.0e16)
    axis.set_title(r"Conditional GR direct-image $\nu F_\nu$ at 100 Mpc")
    axis.set_xlabel(r"$\nu_{obs}$ [Hz]")
    axis.set_ylabel(r"$\nu F_\nu$ [erg s$^{-1}$ cm$^{-2}$]")
    axis.legend(fontsize=8)

    axis = axes[0, 1]
    for phase in (0.0, 60.0, 120.0, 180.0):
        spectrum = spectra[(75.0, phase)]
        axis.loglog(
            frequency[visible_spectral_range],
            frequency[visible_spectral_range]
            * spectrum.flux_density_erg_s_cm2_hz[visible_spectral_range],
            label=f"phase={phase:.0f} deg",
        )
    axis.axvline(1.0e15, color="black", linestyle=":", linewidth=1.0)
    axis.set_xlim(1.0e14, 3.0e16)
    axis.set_title(r"Precession-phase spectra at $i=75$ deg")
    axis.set_xlabel(r"$\nu_{obs}$ [Hz]")
    axis.set_ylabel(r"$\nu F_\nu$ [erg s$^{-1}$ cm$^{-2}$]")
    axis.legend(fontsize=8)

    axis = axes[0, 2]
    faceon = spectra[(0.0, 0.0)].flux_density_erg_s_cm2_hz[probe_indices]
    for index, nu in enumerate(PROBE_FREQUENCY_HZ[:4]):
        values = np.array([spectra[(75.0, phase)].flux_density_erg_s_cm2_hz[probe_indices[index]] for phase in PHASE_DEG])
        axis.plot(PHASE_DEG, values / faceon[index], marker="o", label=f"{nu:.1e} Hz")
    axis.set_title("Precession response of observed flux")
    axis.set_xlabel(r"$\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel(r"$F_\nu/F_{\nu,face-on}$")
    axis.legend(fontsize=8)

    axis = axes[1, 0]
    for inclination in (0.0, 30.0, 60.0, 75.0):
        stokes_spectrum = stokes[(inclination, 0.0)]
        axis.semilogx(frequency, 100.0 * stokes_spectrum.polarization_fraction, label=f"i={inclination:.0f} deg")
    axis.set_xlim(1.0e14, 1.0e16)
    axis.set_title("Straight-ray scattering-atmosphere polarization")
    axis.set_xlabel(r"$\nu_{obs}$ [Hz]")
    axis.set_ylabel("polarization [%]")
    axis.legend(fontsize=8)

    axis = axes[1, 1]
    for index, nu in enumerate(PROBE_FREQUENCY_HZ[:3]):
        values = np.array([100.0 * stokes[(75.0, phase)].polarization_fraction[probe_indices[index]] for phase in PHASE_DEG])
        axis.plot(PHASE_DEG, values, marker="o", label=f"{nu:.1e} Hz")
    axis.set_title(r"Polarization phase response at $i=75$ deg")
    axis.set_xlabel(r"$\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel("polarization [%]")
    axis.legend(fontsize=8)

    axis = axes[1, 2]
    for phase in (0.0, 90.0, 180.0, 270.0):
        ratio = spectra[(75.0, phase)].flux_density_erg_s_cm2_hz / stokes[(75.0, phase)].flux_i_erg_s_cm2_hz
        axis.semilogx(frequency, ratio, label=f"phase={phase:.0f} deg")
    axis.axhline(1.0, color="black", linestyle="--", linewidth=1.0)
    axis.set_xlim(1.0e14, 1.0e16)
    axis.set_title("Weak-field curved image / straight-ray limb spectrum")
    axis.set_xlabel(r"$\nu_{obs}$ [Hz]")
    axis.set_ylabel("flux ratio")
    axis.legend(fontsize=8)

    axis = axes[2, 0]
    ng_frequency = non_gray["frequency_hz"]
    axis.semilogx(ng_frequency, non_gray["H_I_plus_He_II_thick_fraction"], label="H I + He II")
    axis.semilogx(ng_frequency, non_gray["with_He_I_approx_thick_fraction"], linestyle="--", label="+ approximate He I")
    for energy, label in ((HYDROGEN_IONIZATION_ERG, "H I"), (HELIUM_I_IONIZATION_ERG, "He I"), (HELIUM_II_IONIZATION_ERG, "He II")):
        axis.axvline(energy / PLANCK_ERG_S, linewidth=0.8, alpha=0.5)
    axis.set_ylim(-0.03, 1.03)
    axis.set_title("LTE area fraction with tau_eff >= 1 (validity audit)")
    axis.set_xlabel(r"$\nu$ [Hz]")
    axis.set_ylabel("area fraction")
    axis.legend(fontsize=8)

    axis = axes[2, 1]
    axis.loglog(ng_frequency, non_gray["H_I_plus_He_II_tau_p50"], label="median")
    axis.fill_between(ng_frequency, non_gray["H_I_plus_He_II_tau_p10"], non_gray["H_I_plus_He_II_tau_p90"], alpha=0.25, label="10--90 percentile")
    axis.axhline(1.0, color="black", linestyle="--", linewidth=1.0)
    axis.set_title("LTE non-gray effective-depth distribution")
    axis.set_xlabel(r"$\nu$ [Hz]")
    axis.set_ylabel(r"$\tau_{eff}$ to midplane")
    axis.legend(fontsize=8)

    axis = axes[2, 2]
    for i, epsilon in enumerate(reprocessing["epsilon"]):
        axis.loglog(reprocessing["radius"], reprocessing["mass_msun"][i], label=rf"$\epsilon={epsilon:.0e}$")
    axis.set_title("Minimum full-coverage thermalizing mass (constraint only)")
    axis.set_xlabel("layer radius [cm]")
    axis.set_ylabel(r"$M_{min}(C=1)$ [$M_\odot$]")
    axis.legend(fontsize=7)

    figure.savefig(output_dir / "phase3_complete_summary.png", dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    non_gray_report, non_gray_data = _non_gray_audit(args.output_dir)
    print("Phase3A non-gray audit complete", flush=True)
    observer_report, observer_data = _observer_transfer_audit(args.output_dir)
    print("Phase3B/C observer transfer complete", flush=True)
    reprocessing_report, reprocessing_data = _reprocessing_audit(
        args.output_dir, observer_data
    )
    print("Phase3D reprocessing constraints complete", flush=True)
    _make_summary_figure(
        args.output_dir, non_gray_data, observer_data, reprocessing_data
    )

    model = build_strict_domain_reference_model(65, 1024)
    corrected_bolometric, corrected_two_sided = face_on_bolometric_luminosities(
        model.source
    )
    pre_erratum_bolometric, _ = pre_erratum_face_on_bolometric_luminosities(
        model.source
    )
    report = {
        "classification_legend": {
            "L": "literature result or formula",
            "A": "new adopted closure or approximation",
            "V": "verified by this code and recorded tests",
            "O": "open problem; not self-consistent",
        },
        "source_contract": (
            "[L] ZO e(a), varpi, Sigma, j, H, T_eff retained; no hydrodynamic output, wind, or fitted reprocessing layer"
        ),
        "phase3a_non_gray": non_gray_report,
        "phase3bc_observer_transfer": observer_report,
        "phase3d_reprocessing": reprocessing_report,
        "energy_reference": {
            "corrected_faceon_isotropic_equivalent_bolometric_erg_s": (
                corrected_bolometric
            ),
            "corrected_intrinsic_two_sided_bolometric_erg_s": corrected_two_sided,
            "pre_erratum_faceon_isotropic_equivalent_bolometric_erg_s": (
                pre_erratum_bolometric
            ),
            "local_modified_blackbody_energy_conservation": "covered by analytic test in tests/test_atmosphere.py",
            "angular_law_energy_conservation": "covered by analytic test in tests/test_polarization.py",
        },
        "scientific_decision": {
            "bare_disc_optical_uv": (
                "conditional spectra, T_bb, R_bb, phase modulation and polarization are now frequency-resolved predictions "
                "within the LTE modified-blackbody and angle-law domain"
            ),
            "bare_disc_xray": (
                "not a validated prediction: LTE bound-free sensitivity is strongly population-dependent and no NLTE inner atmosphere exists"
            ),
            "reprocessing": (
                "not activated; any future layer must meet the recorded mass, diffusion, energy and momentum bounds"
            ),
        },
        "runtime_seconds": time.perf_counter() - start,
    }
    with (args.output_dir / "phase3_complete_report.json").open(
        "w", encoding="utf-8"
    ) as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
    print(f"Phase3 complete in {report['runtime_seconds']:.1f} s", flush=True)


if __name__ == "__main__":
    main()
