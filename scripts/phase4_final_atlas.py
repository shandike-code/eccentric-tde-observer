"""Phase 4：annulus 动态适用域与 observation-ready 倾角—进动图谱。"""

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
    render_source_surface_quadrature,
)
from eccentric_tde_observer.annulus_bridge import (
    compton_y_upper_bound,
    zo_annulus_atmosphere_coordinates,
)
from eccentric_tde_observer.atmosphere import solve_peak_thermalization_closure
from eccentric_tde_observer.diagnostics import fit_isotropic_blackbody_lnu
from eccentric_tde_observer.geometry import build_orbital_surface_mesh
from eccentric_tde_observer.gr_transfer import (
    beloborodov_schwarzschild_direct_image_transfer,
    gr_direct_image_sed,
)
from eccentric_tde_observer.observer import Observer
from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.polarization import surface_stokes_sed
from eccentric_tde_observer.quadrature import geometric_planar_area_weights
from eccentric_tde_observer.reference_case import (
    STRICT_CIRCULARIZATION_EFFICIENCY,
    STRICT_ECCENTRICITY,
    build_strict_domain_reference_model,
)
from eccentric_tde_observer.relativity import (
    homologous_vertical_velocity_cm_s,
    straight_ray_frequency_shift,
)
from eccentric_tde_observer.source import PhysicalDomainError
from eccentric_tde_observer.time_series import (
    PeriodicPhaseSpectralAtlas,
    ab_magnitude_from_fnu,
    ideal_log_tophat_bandpass,
    periodic_harmonics,
    photon_counting_mean_fnu,
    uniform_precession_relative_phase,
)
from eccentric_tde_observer.vertical import RADIATION_PRESSURE_POLYTROPE_PROFILE


PARSEC_CM = 3.0856775814913673e18
DISTANCE_CM = 100.0e6 * PARSEC_CM
INCLINATION_DEG = np.array([0.0, 15.0, 30.0, 45.0, 60.0, 70.0, 75.0])
PHASE_DEG = np.arange(0.0, 360.0, 15.0)
PROBE_FREQUENCY_HZ = np.array([5.0e14, 1.0e15, 2.0e15, 5.0e15, 1.0e16])


def _write_records(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def _weighted_fraction(mask: np.ndarray, weights: np.ndarray) -> float:
    if mask.shape != weights.shape:
        raise ValueError("weighted mask and weights must have the same shape")
    return float(np.sum(weights * mask, dtype=np.float64) / np.sum(weights, dtype=np.float64))


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


def _quadrature(mesh, observer, bins: int):
    index = build_orthographic_triangle_index(mesh, observer, bins_long_axis=bins)
    return render_source_surface_quadrature(
        mesh, observer, subdivision_level=0, triangle_index=index
    )


def _one_orientation(
    model,
    mesh,
    vertical_velocity,
    hardening,
    inclination_deg: float,
    phase_deg: float,
    frequency: np.ndarray,
    bins: int,
):
    observer = Observer(
        DISTANCE_CM, np.deg2rad(inclination_deg), np.deg2rad(phase_deg)
    )
    quadrature = _quadrature(mesh, observer, bins)
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
    transfer = beloborodov_schwarzschild_direct_image_transfer(
        model.source,
        mesh,
        observer,
        model.parameters.black_hole_mass_msun,
        vertical_velocity_cm_s=vertical_velocity,
    )
    spectrum = gr_direct_image_sed(
        model.source,
        mesh,
        observer,
        transfer,
        frequency,
        spectral_hardening_factor=hardening,
    )
    return quadrature, stokes, transfer, spectrum


def _annulus_domain_audit(output_dir: Path) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    model = build_strict_domain_reference_model(65, 1024)
    coordinates = zo_annulus_atmosphere_coordinates(model)
    weights = geometric_planar_area_weights(model.source)
    ratio = coordinates.quasi_static_ratio
    scattering_depth = (
        model.parameters.opacity_cm2_g
        * coordinates.midplane_column_mass_g_cm2
    )
    compton_upper = compton_y_upper_bound(
        coordinates.effective_temperature_k, scattering_depth
    )

    # Davis--Hubeny 2006 published table bounds; no extrapolation is allowed.
    dh_temperature = (1.0e5, 10.0**7.4)
    dh_midplane_column = (10.0**2.5, 1.0e6)
    dh_gravity = (1.0e-4, 1.0e9)
    within_dh = (
        (coordinates.effective_temperature_k >= dh_temperature[0])
        & (coordinates.effective_temperature_k <= dh_temperature[1])
        & (coordinates.midplane_column_mass_g_cm2 >= dh_midplane_column[0])
        & (coordinates.midplane_column_mass_g_cm2 <= dh_midplane_column[1])
        & (coordinates.comoving_pressure_gravity_coefficient_s2 >= dh_gravity[0])
        & (coordinates.comoving_pressure_gravity_coefficient_s2 <= dh_gravity[1])
    )
    fractions = {
        f"area_fraction_quasi_static_ratio_lt_{threshold:g}": _weighted_fraction(
            ratio < threshold, weights
        )
        for threshold in (0.1, 0.3, 0.5, 1.0)
    }
    fractions["area_fraction_inside_Davis_Hubeny_2006_table"] = _weighted_fraction(
        within_dh, weights
    )
    fractions["area_fraction_midplane_Compton_y_upper_gt_1"] = _weighted_fraction(
        compton_upper > 1.0, weights
    )

    np.savez_compressed(
        output_dir / "phase4_annulus_coordinates.npz",
        semimajor_axis_cm=model.source.semimajor_axis_cm,
        eccentric_anomaly_rad=model.source.eccentric_anomaly_rad,
        effective_temperature_k=coordinates.effective_temperature_k,
        midplane_column_mass_g_cm2=coordinates.midplane_column_mass_g_cm2,
        tidal_gravity_coefficient_s2=coordinates.tidal_gravity_coefficient_s2,
        comoving_pressure_gravity_coefficient_s2=coordinates.comoving_pressure_gravity_coefficient_s2,
        vertical_acceleration_coefficient_s2=coordinates.vertical_acceleration_coefficient_s2,
        logarithmic_breathing_rate_s1=coordinates.logarithmic_breathing_rate_s1,
        quasi_static_ratio=coordinates.quasi_static_ratio,
        midplane_compton_y_upper_bound=compton_upper,
    )
    anomaly_records = []
    for anomaly_index, anomaly in enumerate(model.source.eccentric_anomaly_rad):
        anomaly_records.append(
            {
                "eccentric_anomaly_rad": float(anomaly),
                "dimensionless_height": float(model.breathing.dimensionless_height[anomaly_index]),
                "log_height_derivative_per_rad": float(model.breathing.log_height_derivative_per_rad[anomaly_index]),
                "quasi_static_ratio": float(ratio[0, anomaly_index]),
                "pressure_Q_to_tidal_Q": float(
                    coordinates.comoving_pressure_gravity_coefficient_s2[0, anomaly_index]
                    / coordinates.tidal_gravity_coefficient_s2[0, anomaly_index]
                ),
            }
        )
    _write_records(output_dir / "phase4_annulus_anomaly_audit.csv", anomaly_records)

    report = {
        "classification": (
            "[L/A/V] ZO dynamic column to Davis-Hubeny static-annulus coordinates; "
            "no NLTE intensity table fabricated"
        ),
        "coordinate_ranges": {
            "T_eff_k": [float(np.min(coordinates.effective_temperature_k)), float(np.max(coordinates.effective_temperature_k))],
            "m0_g_cm2": [float(np.min(coordinates.midplane_column_mass_g_cm2)), float(np.max(coordinates.midplane_column_mass_g_cm2))],
            "Q_tidal_s2": [float(np.min(coordinates.tidal_gravity_coefficient_s2)), float(np.max(coordinates.tidal_gravity_coefficient_s2))],
            "Q_pressure_s2": [float(np.min(coordinates.comoving_pressure_gravity_coefficient_s2)), float(np.max(coordinates.comoving_pressure_gravity_coefficient_s2))],
            "Q_pressure_to_Q_tidal": [
                float(np.min(coordinates.comoving_pressure_gravity_coefficient_s2 / coordinates.tidal_gravity_coefficient_s2)),
                float(np.max(coordinates.comoving_pressure_gravity_coefficient_s2 / coordinates.tidal_gravity_coefficient_s2)),
            ],
            "quasi_static_ratio": [float(np.min(ratio)), float(np.max(ratio))],
            "midplane_Compton_y_upper_bound": [float(np.min(compton_upper)), float(np.max(compton_upper))],
        },
        "area_fractions": fractions,
        "Davis_Hubeny_2006_published_bounds": {
            "T_eff_k": list(dh_temperature),
            "m0_g_cm2": list(dh_midplane_column),
            "Q_s2": list(dh_gravity),
        },
        "decision": (
            "The published annulus table covers zero source area, and only the area recorded at small "
            "quasi-static ratio can be represented by a sequence of static annuli.  The remaining orbit "
            "requires a time-dependent irradiated atmosphere or an independently justified response model."
        ),
    }
    data = {
        "model": model,
        "coordinates": coordinates,
        "weights": weights,
        "compton_upper": compton_upper,
    }
    return report, data


def _prediction_atlas(output_dir: Path) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    frequency = np.unique(
        np.concatenate(
            (
                np.geomspace(1.0e14, 1.0e16, 161),
                PROBE_FREQUENCY_HZ,
                [4.0e14, 8.0e14, 1.5e15],
            )
        )
    )
    probe_indices = np.searchsorted(frequency, PROBE_FREQUENCY_HZ)
    model = build_strict_domain_reference_model(33, 512)
    _, mesh, vertical_velocity = _photosphere_mesh_velocity(model)
    hardening = solve_peak_thermalization_closure(
        model.source, vertical_points=257
    ).spectral_hardening_factor
    shape = (INCLINATION_DEG.size, PHASE_DEG.size, frequency.size)
    gr_flux = np.empty(shape)
    stokes_i = np.empty(shape)
    stokes_q = np.empty(shape)
    stokes_u = np.empty(shape)
    polarization = np.empty(shape)
    diagnostics: list[dict[str, object]] = []
    atlas_records: list[dict[str, object]] = []
    optical_band = ideal_log_tophat_bandpass("diagnostic_optical", 4.0e14, 8.0e14)
    near_uv_band = ideal_log_tophat_bandpass("diagnostic_near_uv", 8.0e14, 1.5e15)

    for inclination_index, inclination in enumerate(INCLINATION_DEG):
        for phase_index, phase in enumerate(PHASE_DEG):
            quadrature, stokes, transfer, spectrum = _one_orientation(
                model,
                mesh,
                vertical_velocity,
                hardening,
                float(inclination),
                float(phase),
                frequency,
                192,
            )
            gr_flux[inclination_index, phase_index] = spectrum.flux_density_erg_s_cm2_hz
            stokes_i[inclination_index, phase_index] = stokes.flux_i_erg_s_cm2_hz
            stokes_q[inclination_index, phase_index] = stokes.flux_q_erg_s_cm2_hz
            stokes_u[inclination_index, phase_index] = stokes.flux_u_erg_s_cm2_hz
            polarization[inclination_index, phase_index] = stokes.polarization_fraction
            fit = fit_isotropic_blackbody_lnu(
                frequency,
                spectrum.isotropic_equivalent_lnu_erg_s_hz,
                5.0e14,
                1.0e15,
            )
            optical_fnu = float(
                photon_counting_mean_fnu(
                    frequency, spectrum.flux_density_erg_s_cm2_hz, optical_band
                )
            )
            near_uv_fnu = float(
                photon_counting_mean_fnu(
                    frequency, spectrum.flux_density_erg_s_cm2_hz, near_uv_band
                )
            )
            record: dict[str, object] = {
                "inclination_deg": float(inclination),
                "relative_phase_deg": float(phase),
                "visible_to_unobscured_area": (
                    quadrature.visible_projected_area_cm2
                    / quadrature.unobscured_projected_area_cm2
                ),
                "GR_to_straight_image_area": (
                    transfer.direct_image_area_cm2
                    / quadrature.unobscured_projected_area_cm2
                ),
                "diagnostic_optical_mean_fnu_cgs": optical_fnu,
                "diagnostic_near_uv_mean_fnu_cgs": near_uv_fnu,
                "diagnostic_optical_AB_mag": float(ab_magnitude_from_fnu(optical_fnu)),
                "diagnostic_near_uv_AB_mag": float(ab_magnitude_from_fnu(near_uv_fnu)),
                "diagnostic_NUV_minus_optical_AB": float(
                    ab_magnitude_from_fnu(near_uv_fnu)
                    - ab_magnitude_from_fnu(optical_fnu)
                ),
                "conservative_T_bb_k": fit.temperature_k,
                "conservative_R_bb_cm": fit.radius_cm,
                "conservative_fit_rms_dex": fit.rms_log10_residual_dex,
            }
            for probe_index, probe in zip(probe_indices, PROBE_FREQUENCY_HZ, strict=True):
                suffix = f"{probe:.1e}_Hz"
                record[f"GR_Fnu_at_{suffix}"] = float(
                    spectrum.flux_density_erg_s_cm2_hz[probe_index]
                )
                record[f"polarization_fraction_at_{suffix}"] = float(
                    stokes.polarization_fraction[probe_index]
                )
            diagnostics.append(record)
            for frequency_index, nu in enumerate(frequency):
                atlas_records.append(
                    {
                        "inclination_deg": float(inclination),
                        "relative_phase_deg": float(phase),
                        "frequency_hz": float(nu),
                        "GR_Fnu_cgs": float(spectrum.flux_density_erg_s_cm2_hz[frequency_index]),
                        "straight_Stokes_I_cgs": float(stokes.flux_i_erg_s_cm2_hz[frequency_index]),
                        "straight_Stokes_Q_cgs": float(stokes.flux_q_erg_s_cm2_hz[frequency_index]),
                        "straight_Stokes_U_cgs": float(stokes.flux_u_erg_s_cm2_hz[frequency_index]),
                        "straight_polarization_fraction": float(stokes.polarization_fraction[frequency_index]),
                    }
                )
        print(f"Phase4 atlas i={inclination:.0f} deg complete", flush=True)
    _write_records(output_dir / "phase4_atlas_diagnostics.csv", diagnostics)
    _write_records(output_dir / "phase4_atlas_spectra.csv", atlas_records)

    harmonic_records = []
    for inclination_index, inclination in enumerate(INCLINATION_DEG):
        for probe_index, probe in zip(probe_indices, PROBE_FREQUENCY_HZ, strict=True):
            signal = gr_flux[inclination_index, :, probe_index]
            harmonics = periodic_harmonics(signal)
            harmonic_records.append(
                {
                    "inclination_deg": float(inclination),
                    "frequency_hz": float(probe),
                    "max_to_min": float(np.max(signal) / np.min(signal)),
                    "fractional_rms": harmonics.fractional_rms,
                    "first_harmonic_fractional_semi_amplitude": harmonics.first_harmonic_fractional_semi_amplitude,
                    "second_harmonic_fractional_semi_amplitude": harmonics.second_harmonic_fractional_semi_amplitude,
                }
            )
    _write_records(output_dir / "phase4_atlas_harmonics.csv", harmonic_records)

    # 中文：更高倾角不是自动延伸；若局域 mu<0，角闭合必须明确拒绝。
    high_inclination_rejection = None
    high_inclination_rejection_phase = None
    for phase in PHASE_DEG:
        try:
            _one_orientation(
                model,
                mesh,
                vertical_velocity,
                hardening,
                80.0,
                float(phase),
                PROBE_FREQUENCY_HZ,
                192,
            )
        except PhysicalDomainError as error:
            high_inclination_rejection = str(error)
            high_inclination_rejection_phase = float(phase)
            break
    if high_inclination_rejection is None:
        raise RuntimeError(
            "i=80 deg passed every phase; review before extending the validated atlas"
        )

    inclination_75_index = int(np.flatnonzero(INCLINATION_DEG == 75.0)[0])
    phase_atlas = PeriodicPhaseSpectralAtlas(
        np.deg2rad(PHASE_DEG), frequency, gr_flux[inclination_75_index]
    )
    dimensionless_time = np.linspace(0.0, 1.0, 97)
    relative_phase = uniform_precession_relative_phase(
        dimensionless_time, 1.0, initial_relative_phase_rad=0.0, prograde=True
    )
    time_spectra = phase_atlas.sample(relative_phase)
    time_optical = photon_counting_mean_fnu(frequency, time_spectra, optical_band)
    time_nuv = photon_counting_mean_fnu(frequency, time_spectra, near_uv_band)
    time_records = []
    for index, value in enumerate(dimensionless_time):
        time_records.append(
            {
                "time_over_precession_period": float(value),
                "relative_phase_rad": float(relative_phase[index]),
                "diagnostic_optical_mean_fnu_cgs": float(time_optical[index]),
                "diagnostic_near_uv_mean_fnu_cgs": float(time_nuv[index]),
                "diagnostic_optical_AB_mag": float(ab_magnitude_from_fnu(time_optical[index])),
                "diagnostic_near_uv_AB_mag": float(ab_magnitude_from_fnu(time_nuv[index])),
            }
        )
    _write_records(output_dir / "phase4_dimensionless_lightcurve.csv", time_records)

    # 源网格收敛：只在最强诊断方位复算高分辨率探针。
    high_model = build_strict_domain_reference_model(65, 1024)
    _, high_mesh, high_vertical_velocity = _photosphere_mesh_velocity(high_model)
    high_hardening = solve_peak_thermalization_closure(
        high_model.source, vertical_points=257
    ).spectral_hardening_factor
    _, _, _, high_spectrum = _one_orientation(
        high_model,
        high_mesh,
        high_vertical_velocity,
        high_hardening,
        75.0,
        90.0,
        PROBE_FREQUENCY_HZ,
        256,
    )
    coarse_phase_index = int(np.flatnonzero(PHASE_DEG == 90.0)[0])
    coarse_probe = gr_flux[inclination_75_index, coarse_phase_index, probe_indices]
    source_grid_change = np.abs(
        high_spectrum.flux_density_erg_s_cm2_hz / coarse_probe - 1.0
    )
    phase_resolution_change = []
    for probe_index in probe_indices:
        fine_harmonic = periodic_harmonics(gr_flux[inclination_75_index, :, probe_index])
        coarse_harmonic = periodic_harmonics(gr_flux[inclination_75_index, ::2, probe_index])
        phase_resolution_change.append(
            abs(
                coarse_harmonic.first_harmonic_fractional_semi_amplitude
                / fine_harmonic.first_harmonic_fractional_semi_amplitude
                - 1.0
            )
        )
    convergence_records = []
    for probe, source_change, phase_change in zip(
        PROBE_FREQUENCY_HZ, source_grid_change, phase_resolution_change, strict=True
    ):
        convergence_records.append(
            {
                "frequency_hz": float(probe),
                "source_grid_33x512_to_65x1024_relative_change": float(source_change),
                "phase_grid_12_to_24_first_harmonic_relative_change": float(phase_change),
            }
        )
    _write_records(output_dir / "phase4_atlas_convergence.csv", convergence_records)

    # e=0 控制：任何观察者方位变化都应消失。
    circular = build_strict_domain_reference_model(33, 512, eccentricity=0.0)
    _, circular_mesh, circular_vertical_velocity = _photosphere_mesh_velocity(circular)
    circular_hardening = solve_peak_thermalization_closure(
        circular.source, vertical_points=257
    ).spectral_hardening_factor
    circular_flux = []
    for phase in (0.0, 90.0):
        _, _, _, spectrum = _one_orientation(
            circular,
            circular_mesh,
            circular_vertical_velocity,
            circular_hardening,
            75.0,
            phase,
            PROBE_FREQUENCY_HZ,
            192,
        )
        circular_flux.append(spectrum.flux_density_erg_s_cm2_hz)
    circular_change = np.abs(circular_flux[1] / circular_flux[0] - 1.0)

    report = {
        "classification": (
            "[A/V] observation-ready conditional atlas using the Phase-3 bare-disc spectrum; "
            "diagnostic bands are ideal top hats, not instrument responses"
        ),
        "source": {
            "eccentricity": STRICT_ECCENTRICITY,
            "circularization_efficiency": STRICT_CIRCULARIZATION_EFFICIENCY,
            "atlas_grid": [33, 512],
            "verification_grid": [65, 1024],
            "distance_mpc": 100.0,
        },
        "observer_grid": {
            "inclination_deg": INCLINATION_DEG.tolist(),
            "relative_phase_deg": PHASE_DEG.tolist(),
            "frequency_range_hz": [float(frequency[0]), float(frequency[-1])],
        },
        "rejected_extension": {
            "inclination_deg": 80.0,
            "first_rejected_relative_phase_deg": high_inclination_rejection_phase,
            "reason": high_inclination_rejection,
            "action": (
                "no clipping; requires face-level angular transfer or a multi-valued photosphere treatment"
            ),
        },
        "diagnostic_band_definition": {
            "optical_hz": [4.0e14, 8.0e14],
            "near_uv_hz": [8.0e14, 1.5e15],
            "weighting": "photon-counting AB mean fnu; ideal unit response",
        },
        "ranges": {
            "T_bb_k": [float(min(row["conservative_T_bb_k"] for row in diagnostics)), float(max(row["conservative_T_bb_k"] for row in diagnostics))],
            "R_bb_cm": [float(min(row["conservative_R_bb_cm"] for row in diagnostics)), float(max(row["conservative_R_bb_cm"] for row in diagnostics))],
            "optical_AB_mag_at_100Mpc": [float(min(row["diagnostic_optical_AB_mag"] for row in diagnostics)), float(max(row["diagnostic_optical_AB_mag"] for row in diagnostics))],
            "NUV_minus_optical_AB": [float(min(row["diagnostic_NUV_minus_optical_AB"] for row in diagnostics)), float(max(row["diagnostic_NUV_minus_optical_AB"] for row in diagnostics))],
        },
        "validation": {
            "max_source_grid_relative_change": float(np.max(source_grid_change)),
            "max_phase_grid_first_harmonic_relative_change": float(np.max(phase_resolution_change)),
            "max_circular_phase_relative_change": float(np.max(circular_change)),
            "all_straight_visible_to_unobscured_area_are_one": bool(
                all(float(row["visible_to_unobscured_area"]) == 1.0 for row in diagnostics)
            ),
        },
        "time_axis": (
            "The light curve is tabulated against t/P_prec.  No absolute precession period is inferred; "
            "an externally supplied varpi(t) maps through the same periodic atlas."
        ),
    }
    data = {
        "frequency": frequency,
        "probe_indices": probe_indices,
        "gr_flux": gr_flux,
        "polarization": polarization,
        "diagnostics": diagnostics,
        "dimensionless_time": dimensionless_time,
        "time_optical": time_optical,
        "time_nuv": time_nuv,
    }
    return report, data


def _plot_summary(
    output_dir: Path,
    annulus: dict[str, np.ndarray],
    atlas: dict[str, np.ndarray],
) -> None:
    model = annulus["model"]
    coordinates = annulus["coordinates"]
    anomaly_deg = np.rad2deg(model.source.eccentric_anomaly_rad)
    ratio_q = (
        coordinates.comoving_pressure_gravity_coefficient_s2[0]
        / coordinates.tidal_gravity_coefficient_s2[0]
    )
    quasi = coordinates.quasi_static_ratio[0]
    frequency = atlas["frequency"]
    probe_indices = atlas["probe_indices"]
    gr_flux = atlas["gr_flux"]
    polarization = atlas["polarization"]
    diagnostics = atlas["diagnostics"]
    faceon_5e14 = gr_flux[0, 0, probe_indices[0]]

    def diagnostic_grid(key: str) -> np.ndarray:
        values = np.array([float(row[key]) for row in diagnostics])
        return values.reshape(INCLINATION_DEG.size, PHASE_DEG.size)

    figure, axes = plt.subplots(3, 3, figsize=(17.2, 13.2), constrained_layout=True)
    figure.suptitle(
        "Phase 4: dynamic annulus validity and observation-ready bare-disc atlas",
        fontsize=16,
    )

    axis = axes[0, 0]
    axis.semilogy(anomaly_deg, ratio_q)
    axis.axhline(1.0, color="black", linestyle="--", linewidth=1.0)
    axis.set_xlabel("eccentric anomaly E [deg]")
    axis.set_ylabel(r"$Q_{pressure}/Q_{tidal}$")
    axis.set_title("Breathing changes the static-annulus gravity coordinate")

    axis = axes[0, 1]
    axis.plot(anomaly_deg, quasi)
    for threshold in (0.1, 0.3, 1.0):
        axis.axhline(threshold, linestyle="--", linewidth=0.9, label=f"ratio={threshold:g}")
    axis.set_xlabel("eccentric anomaly E [deg]")
    axis.set_ylabel(r"$|d\ln H/dt|/\sqrt{Q_{pressure}}$")
    axis.set_title("Quasi-static annulus validity diagnostic")
    axis.legend(fontsize=8)

    axis = axes[0, 2]
    scatter = axis.scatter(
        np.log10(coordinates.midplane_column_mass_g_cm2.reshape(-1)),
        np.log10(coordinates.effective_temperature_k.reshape(-1)),
        c=np.log10(coordinates.comoving_pressure_gravity_coefficient_s2.reshape(-1)),
        s=2.0,
        cmap="viridis",
    )
    axis.axhline(5.0, color="red", linestyle="--", label="Davis-Hubeny min log Teff")
    axis.axvline(2.5, color="tab:orange", linestyle="--", label="published min log m0")
    axis.set_xlabel(r"$\log_{10} m_0$ [g cm$^{-2}$]")
    axis.set_ylabel(r"$\log_{10} T_{eff}$ [K]")
    axis.set_title("Source columns lie outside the published annulus table")
    figure.colorbar(scatter, ax=axis, label=r"$\log_{10}Q_{pressure}$ [s$^{-2}$]")
    axis.legend(fontsize=7)

    extent = [PHASE_DEG[0], PHASE_DEG[-1] + 15.0, INCLINATION_DEG[0], INCLINATION_DEG[-1]]
    axis = axes[1, 0]
    response = gr_flux[:, :, probe_indices[0]] / faceon_5e14
    image = axis.imshow(response, origin="lower", aspect="auto", extent=extent, cmap="magma")
    axis.set_title(r"$F_\nu/F_{\nu,face-on}$ at $5e14$ Hz")
    axis.set_xlabel(r"$\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel("inclination [deg]")
    figure.colorbar(image, ax=axis)

    axis = axes[1, 1]
    color = diagnostic_grid("diagnostic_NUV_minus_optical_AB")
    image = axis.imshow(color, origin="lower", aspect="auto", extent=extent, cmap="coolwarm")
    axis.set_title("Ideal NUV - optical AB color")
    axis.set_xlabel(r"$\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel("inclination [deg]")
    figure.colorbar(image, ax=axis, label="mag")

    axis = axes[1, 2]
    pol = 100.0 * polarization[:, :, probe_indices[0]]
    image = axis.imshow(pol, origin="lower", aspect="auto", extent=extent, cmap="cividis")
    axis.set_title("Conditional polarization at 5e14 Hz")
    axis.set_xlabel(r"$\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel("inclination [deg]")
    figure.colorbar(image, ax=axis, label="percent")

    axis = axes[2, 0]
    temperature = diagnostic_grid("conservative_T_bb_k")
    image = axis.imshow(temperature, origin="lower", aspect="auto", extent=extent, cmap="inferno")
    axis.set_title("Conservative optical blackbody temperature")
    axis.set_xlabel(r"$\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel("inclination [deg]")
    figure.colorbar(image, ax=axis, label="K")

    axis = axes[2, 1]
    radius = diagnostic_grid("conservative_R_bb_cm") / 1.0e14
    image = axis.imshow(radius, origin="lower", aspect="auto", extent=extent, cmap="viridis")
    axis.set_title("Conservative optical blackbody radius")
    axis.set_xlabel(r"$\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel("inclination [deg]")
    figure.colorbar(image, ax=axis, label=r"$10^{14}$ cm")

    axis = axes[2, 2]
    axis.plot(
        atlas["dimensionless_time"],
        atlas["time_optical"] / np.mean(atlas["time_optical"]),
        label="ideal optical",
    )
    axis.plot(
        atlas["dimensionless_time"],
        atlas["time_nuv"] / np.mean(atlas["time_nuv"]),
        label="ideal near-UV",
    )
    axis.set_xlabel(r"$t/P_{prec}$")
    axis.set_ylabel("band mean fnu / cycle mean")
    axis.set_title(r"Dimensionless light curve at $i=75$ deg")
    axis.legend(fontsize=8)

    figure.savefig(output_dir / "phase4_complete_summary.png", dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    annulus_report, annulus_data = _annulus_domain_audit(args.output_dir)
    print("Phase4 annulus-domain audit complete", flush=True)
    atlas_report, atlas_data = _prediction_atlas(args.output_dir)
    print("Phase4 observer atlas complete", flush=True)
    _plot_summary(args.output_dir, annulus_data, atlas_data)
    report = {
        "classification_legend": {
            "L": "literature result or formula",
            "A": "new adopted closure or diagnostic",
            "V": "verified by code/tests",
            "O": "open problem",
        },
        "phase4a_annulus_bridge": annulus_report,
        "phase4b_observer_atlas": atlas_report,
        "final_scientific_status": {
            "completed": (
                "The ZO source-to-observer bare-disc map is frequency, inclination, phase and dimensionless-time resolved, "
                "with strict interfaces for future angle-resolved atmosphere tables."
            ),
            "not_completed": (
                "A time-dependent irradiated NLTE atmosphere is not available and cannot be replaced by extrapolating "
                "Davis-Hubeny tables or selecting free wind parameters."
            ),
            "model_verdict": (
                "Use current optical/UV atlas as a falsifiable conditional prediction.  Do not publish a physical X-ray "
                "ratio until the dynamic-atmosphere problem is solved or an independently constrained high-energy source is supplied."
            ),
        },
        "runtime_seconds": time.perf_counter() - start,
    }
    with (args.output_dir / "phase4_complete_report.json").open(
        "w", encoding="utf-8"
    ) as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
    print(f"Phase4 complete in {report['runtime_seconds']:.1f} s", flush=True)


if __name__ == "__main__":
    main()
