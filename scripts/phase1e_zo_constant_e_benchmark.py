"""Generate Phase-1E ZO source reconstruction and ray-failure diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eccentric_tde_observer.faceon import (
    face_on_blackbody_sed,
    pre_erratum_face_on_blackbody_sed,
)
from eccentric_tde_observer.geometry import build_orbital_surface_mesh
from eccentric_tde_observer.observer import Observer, unobscured_projected_area_cm2
from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.quadrature import (
    corrected_zo_area_weights,
    geometric_planar_area_weights,
    pre_erratum_zo2020_area_weights,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.raytrace import (
    raytraced_blackbody_sed,
    render_orthographic_surface,
)
from eccentric_tde_observer.zo_reference import (
    SOLAR_MASS_G,
    ZOConstantEParameters,
    build_zo_constant_e_reference_model,
)


PARSEC_CM = 3.0856775814913673e18
EV_ERG = 1.602176634e-12
CLUSTERING_POWER = 5.0


def _energy_kev_to_frequency_hz(energy_kev: float) -> float:
    return energy_kev * 1.0e3 * EV_ERG / PLANCK_ERG_S


def _integrate_band(
    frequency_hz: np.ndarray,
    luminosity_density: np.ndarray,
    lower_hz: float,
    upper_hz: float,
) -> float:
    inside = (frequency_hz >= lower_hz) & (frequency_hz <= upper_hz)
    if np.count_nonzero(inside) < 2:
        raise RuntimeError("frequency grid does not resolve a diagnostic band")
    return float(
        np.trapezoid(luminosity_density[inside], frequency_hz[inside])
    )


def _base_parameters(eccentricity: float) -> ZOConstantEParameters:
    return ZOConstantEParameters(
        black_hole_mass_msun=1.0e6,
        stellar_mass_msun=1.0,
        stellar_radius_rsun=1.0,
        circularization_efficiency=1.0,
        outer_to_inner_semimajor_axis=2.0,
        eccentricity=eccentricity,
        opacity_cm2_g=0.34,
    )


def _build_clustered_model(
    eccentricity: float, radial_points: int, anomaly_points: int
):
    return build_zo_constant_e_reference_model(
        _base_parameters(eccentricity),
        radial_points=radial_points,
        anomaly_points=anomaly_points,
        anomaly_sampling="pericentre_clustered",
        pericentre_clustering_power=CLUSTERING_POWER,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    uvopt_lower = _energy_kev_to_frequency_hz(0.002)
    uvopt_upper = _energy_kev_to_frequency_hz(0.1)
    xray_lower = _energy_kev_to_frequency_hz(0.3)
    xray_upper = _energy_kev_to_frequency_hz(10.0)
    frequency = np.unique(
        np.concatenate(
            (
                np.geomspace(1.0e14, 2.5e18, 401),
                [uvopt_lower, uvopt_upper, xray_lower, xray_upper],
            )
        )
    )
    probe_frequency = np.array([5.0e14, 1.0e16, 5.0e16, 1.0e17])
    eccentricities = (0.0, 0.4, 0.8)

    reference_models = {
        eccentricity: _build_clustered_model(
            eccentricity, radial_points=129, anomaly_points=2048
        )
        for eccentricity in eccentricities
    }
    corrected_spectra = {
        eccentricity: face_on_blackbody_sed(model.source, frequency)
        for eccentricity, model in reference_models.items()
    }
    reference_e08 = reference_models[0.8]
    corrected_e08 = corrected_spectra[0.8]
    pre_erratum_e08 = pre_erratum_face_on_blackbody_sed(
        reference_e08.source, frequency
    )
    corrected_probe = face_on_blackbody_sed(
        reference_e08.source, probe_frequency
    )
    pre_erratum_probe = pre_erratum_face_on_blackbody_sed(
        reference_e08.source, probe_frequency
    )

    anomaly_counts = np.array([256, 512, 1024, 2048])
    anomaly_probe_spectra = np.empty(
        (anomaly_counts.size, probe_frequency.size)
    )
    for index, anomaly_points in enumerate(anomaly_counts):
        model = _build_clustered_model(
            0.8, radial_points=129, anomaly_points=int(anomaly_points)
        )
        anomaly_probe_spectra[index] = face_on_blackbody_sed(
            model.source, probe_frequency
        ).isotropic_equivalent_lnu_erg_s_hz
    anomaly_last_change = np.abs(
        anomaly_probe_spectra[-1] / anomaly_probe_spectra[-2] - 1.0
    )

    radial_counts = np.array([33, 65, 129, 257])
    radial_probe_spectra = np.empty((radial_counts.size, probe_frequency.size))
    for index, radial_points in enumerate(radial_counts):
        model = _build_clustered_model(
            0.8, radial_points=int(radial_points), anomaly_points=2048
        )
        radial_probe_spectra[index] = face_on_blackbody_sed(
            model.source, probe_frequency
        ).isotropic_equivalent_lnu_erg_s_hz
    radial_last_change = np.abs(
        radial_probe_spectra[-1] / radial_probe_spectra[-2] - 1.0
    )

    ray_model = _build_clustered_model(
        0.8, radial_points=65, anomaly_points=1024
    )
    source = ray_model.source
    photosphere = solve_gray_photosphere(
        source, ray_model.parameters.opacity_cm2_g, 2.0 / 3.0
    )
    mesh = build_orbital_surface_mesh(source, photosphere.height_cm)
    semimajor_axis = source.semimajor_axis_cm[:, None]
    cylindrical_radius = semimajor_axis * (
        1.0
        - source.eccentricity[:, None]
        * np.cos(source.eccentric_anomaly_rad)[None, :]
    )
    h_over_radius = source.scale_height_cm / cylindrical_radius
    photosphere_over_radius = photosphere.height_cm / cylindrical_radius

    distance = 100.0e6 * PARSEC_CM
    case_specs = (
        ("relative_phi_0", 0.0),
        ("relative_phi_90", 90.0),
        ("relative_phi_180", 180.0),
    )
    ray_pixels = np.array([512, 1024, 2048, 4096])
    ray_probe_ratio = np.empty(
        (len(case_specs), ray_pixels.size, probe_frequency.size)
    )
    ray_step_change = np.full_like(ray_probe_ratio, -1.0)
    ray_counts = np.empty((len(case_specs), ray_pixels.size), dtype=np.int64)
    case_reports: dict[str, dict[str, object]] = {}
    for case_index, (name, azimuth_deg) in enumerate(case_specs):
        observer = Observer(distance, np.deg2rad(30.0), np.deg2rad(azimuth_deg))
        final_image = None
        for pixel_index, pixels in enumerate(ray_pixels):
            image = render_orthographic_surface(mesh, observer, int(pixels))
            ray_sed = raytraced_blackbody_sed(
                source, mesh, observer, image, probe_frequency
            )
            ray_probe_ratio[case_index, pixel_index] = (
                ray_sed.isotropic_equivalent_lnu_erg_s_hz
                / face_on_blackbody_sed(
                    source, probe_frequency
                ).isotropic_equivalent_lnu_erg_s_hz
            )
            ray_counts[case_index, pixel_index] = image.ray_count
            if pixel_index > 0:
                ray_step_change[case_index, pixel_index] = np.abs(
                    ray_probe_ratio[case_index, pixel_index]
                    / ray_probe_ratio[case_index, pixel_index - 1]
                    - 1.0
                )
            final_image = image
        if final_image is None:
            raise RuntimeError("ray convergence produced no image")
        final_step = ray_step_change[case_index, -1]
        case_reports[name] = {
            "inclination_deg": 30.0,
            "relative_apsidal_azimuth_deg": azimuth_deg,
            "final_pixels_long_axis": int(ray_pixels[-1]),
            "final_image_shape": list(final_image.shape),
            "emitting_to_hit_pixel_fraction": (
                final_image.emitting_count / final_image.hit_count
            ),
            "visible_to_unobscured_projected_area": (
                final_image.visible_projected_area_cm2
                / unobscured_projected_area_cm2(mesh, observer)
            ),
            "final_ray_to_corrected_probe_spectrum": (
                ray_probe_ratio[case_index, -1].tolist()
            ),
            "last_ray_step_fractional_change": final_step.tolist(),
            "optical_5e14Hz_converged_below_1e_minus_3": bool(
                final_step[0] < 1.0e-3
            ),
            "all_probe_frequencies_converged_below_1e_minus_3": bool(
                np.all(final_step < 1.0e-3)
            ),
        }

    phase_deg = np.linspace(0.0, 360.0, 24, endpoint=False)
    optical_frequency = np.array([probe_frequency[0]])
    optical_reference = face_on_blackbody_sed(
        source, optical_frequency
    ).isotropic_equivalent_lnu_erg_s_hz[0]
    phase_optical_ratio = np.empty(phase_deg.size)
    phase_pixels = 2048
    for index, relative_phase_deg in enumerate(phase_deg):
        observer = Observer(
            distance, np.deg2rad(30.0), np.deg2rad(relative_phase_deg)
        )
        image = render_orthographic_surface(mesh, observer, phase_pixels)
        spectrum = raytraced_blackbody_sed(
            source, mesh, observer, image, optical_frequency
        )
        phase_optical_ratio[index] = (
            spectrum.isotropic_equivalent_lnu_erg_s_hz[0] / optical_reference
        )

    pre_erratum_canonical_mass = float(
        np.sum(
            reference_e08.source.surface_density_g_cm2
            * pre_erratum_zo2020_area_weights(reference_e08.source),
            dtype=np.float64,
        )
    )
    expected_mass = (
        0.5
        * reference_e08.parameters.stellar_mass_msun
        * SOLAR_MASS_G
        * (
            1.0
            - 1.0 / reference_e08.parameters.outer_to_inner_semimajor_axis
        )
    )
    corrected_uvopt = _integrate_band(
        frequency,
        corrected_e08.isotropic_equivalent_lnu_erg_s_hz,
        uvopt_lower,
        uvopt_upper,
    )
    corrected_xray = _integrate_band(
        frequency,
        corrected_e08.isotropic_equivalent_lnu_erg_s_hz,
        xray_lower,
        xray_upper,
    )
    measure_ratio_probe = (
        corrected_probe.isotropic_equivalent_lnu_erg_s_hz
        / pre_erratum_probe.isotropic_equivalent_lnu_erg_s_hz
    )
    invalid_vertical_geometry = photosphere_over_radius >= 1.0
    corrected_weights = corrected_zo_area_weights(source)
    cartesian_weights = geometric_planar_area_weights(source)
    corrected_vertical_failure_fraction = float(
        np.sum(corrected_weights[invalid_vertical_geometry], dtype=np.float64)
        / np.sum(corrected_weights, dtype=np.float64)
    )
    cartesian_vertical_failure_fraction = float(
        np.sum(cartesian_weights[invalid_vertical_geometry], dtype=np.float64)
        / np.sum(cartesian_weights, dtype=np.float64)
    )
    final_ray_changes = ray_step_change[:, -1]
    report = {
        "classification": "ZO constant-e reconstruction [L/V]; optical observer result [A/V]; high-frequency ray result failed convergence [O/V]",
        "local_paper_source": "../markdown_papers/2009.06636v2.md",
        "author_numerical_snapshot_found_locally": False,
        "implemented_zo2020_source_equations": [10, 16, 18, 31, 35, 55],
        "formal_radiative_area_equation": "ZO 2022 Erratum Eq. (5)",
        "historical_area_equation": (
            "ZO 2020 Eq. (56), retained only for explicit pre-Erratum regression"
        ),
        "model_parameters": {
            "black_hole_mass_msun": 1.0e6,
            "stellar_mass_msun": 1.0,
            "stellar_radius_rsun": 1.0,
            "circularization_efficiency": 1.0,
            "outer_to_inner_semimajor_axis": 2.0,
            "eccentricity_for_observer_mapping": 0.8,
            "opacity_cm2_g": 0.34,
        },
        "source_quadrature": {
            "anomaly_sampling": "symmetric pericentre-clustered",
            "clustering_power": CLUSTERING_POWER,
            "reference_radial_points": 129,
            "reference_anomaly_points": 2048,
            "anomaly_counts": anomaly_counts.tolist(),
            "anomaly_last_fractional_change": anomaly_last_change.tolist(),
            "radial_counts": radial_counts.tolist(),
            "radial_last_fractional_change": radial_last_change.tolist(),
            "all_probe_frequencies_below_1e_minus_3": bool(
                np.all(anomaly_last_change < 1.0e-3)
                and np.all(radial_last_change < 1.0e-3)
            ),
        },
        "inner_semimajor_axis_cm": reference_e08.inner_semimajor_axis_cm,
        "eq35_pericentre_h": float(
            reference_e08.breathing.dimensionless_height[0]
        ),
        "eq35_apoapsis_h": float(
            reference_e08.breathing.dimensionless_height[
                reference_e08.breathing.dimensionless_height.size // 2
            ]
        ),
        "eq35_apoapsis_boundary_residual": (
            reference_e08.breathing.apoapsis_boundary_residual
        ),
        "pre_erratum_canonical_mass_g": pre_erratum_canonical_mass,
        "expected_fallback_mass_g": expected_mass,
        "pre_erratum_canonical_mass_relative_error": (
            pre_erratum_canonical_mass / expected_mass - 1.0
        ),
        "effective_temperature_min_max_k": [
            float(np.min(reference_e08.source.effective_temperature_k)),
            float(np.max(reference_e08.source.effective_temperature_k)),
        ],
        "total_optical_depth_min_max": [
            float(np.min(photosphere.total_vertical_optical_depth)),
            float(np.max(photosphere.total_vertical_optical_depth)),
        ],
        "H_over_local_radius_min_max": [
            float(np.min(h_over_radius)),
            float(np.max(h_over_radius)),
        ],
        "photosphere_over_local_radius_min_max": [
            float(np.min(photosphere_over_radius)),
            float(np.max(photosphere_over_radius)),
        ],
        "corrected_area_fraction_with_photosphere_over_radius_ge_1": (
            corrected_vertical_failure_fraction
        ),
        "cartesian_area_fraction_with_photosphere_over_radius_ge_1": (
            cartesian_vertical_failure_fraction
        ),
        "local_vertical_column_geometry_self_consistent_everywhere": False,
        "corrected_band_luminosities": {
            "uvopt_0p002_0p1keV_erg_s": corrected_uvopt,
            "xray_0p3_10keV_erg_s": corrected_xray,
            "xray_to_uvopt_ratio": corrected_xray / corrected_uvopt,
        },
        "faceon_corrected_to_pre_erratum_at_probe_frequencies": (
            measure_ratio_probe.tolist()
        ),
        "ray_probe_frequency_hz": probe_frequency.tolist(),
        "ray_source_grid": {
            "radial_points": 65,
            "anomaly_points": 1024,
            "clustering_power": CLUSTERING_POWER,
        },
        "ray_pixels_long_axis": ray_pixels.tolist(),
        "maximum_last_ray_step_fractional_change": float(
            np.max(final_ray_changes)
        ),
        "ray_convergence_below_1e_minus_3_at_all_probe_frequencies": bool(
            np.all(final_ray_changes < 1.0e-3)
        ),
        "optical_ray_convergence_below_1e_minus_3_for_all_cases": bool(
            np.all(final_ray_changes[:, 0] < 1.0e-3)
        ),
        "observer_cases": case_reports,
        "precession_scan": {
            "inclination_deg": 30.0,
            "relative_phase_definition": "phi_obs - varpi(t)",
            "frequency_hz": float(optical_frequency[0]),
            "phase_count": int(phase_deg.size),
            "pixels_long_axis": phase_pixels,
            "classification": "optical-only converged observer diagnostic",
            "ray_to_corrected_min_max": [
                float(np.min(phase_optical_ratio)),
                float(np.max(phase_optical_ratio)),
            ],
        },
        "observer_xray_spectrum_delivered": False,
        "frequency_shift_applied": False,
        "disc_wind_applied": False,
    }
    (args.output_dir / "phase1e_zo_constant_e_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )

    spectrum_columns = [frequency]
    spectrum_header = ["frequency_hz"]
    for eccentricity in eccentricities:
        spectrum_columns.append(
            corrected_spectra[eccentricity].isotropic_equivalent_lnu_erg_s_hz
        )
        spectrum_header.append(f"corrected_e{eccentricity:.1f}_Lnu_iso")
    spectrum_columns.append(
        pre_erratum_e08.isotropic_equivalent_lnu_erg_s_hz
    )
    spectrum_header.append("pre_erratum_faceon_e0.8_Lnu_iso")
    np.savetxt(
        args.output_dir / "phase1e_zo_source_spectra.csv",
        np.column_stack(spectrum_columns),
        delimiter=",",
        header=",".join(spectrum_header),
        comments="",
    )
    np.savetxt(
        args.output_dir / "phase1e_optical_precession_scan.csv",
        np.column_stack((phase_deg, phase_optical_ratio)),
        delimiter=",",
        header="relative_phase_deg,ray_to_corrected_at_5e14Hz",
        comments="",
    )
    ray_rows = []
    for case_index, (_, azimuth_deg) in enumerate(case_specs):
        for pixel_index, pixels in enumerate(ray_pixels):
            ray_rows.append(
                [
                    azimuth_deg,
                    pixels,
                    ray_counts[case_index, pixel_index],
                    *ray_probe_ratio[case_index, pixel_index].tolist(),
                    *ray_step_change[case_index, pixel_index].tolist(),
                ]
            )
    np.savetxt(
        args.output_dir / "phase1e_ray_failure_convergence.csv",
        np.asarray(ray_rows),
        delimiter=",",
        header=(
            "relative_azimuth_deg,pixels_long_axis,ray_count,"
            "ray_to_corrected_5e14Hz,ray_to_corrected_1e16Hz,"
            "ray_to_corrected_5e16Hz,ray_to_corrected_1e17Hz,"
            "step_5e14Hz,step_1e16Hz,step_5e16Hz,step_1e17Hz"
        ),
        comments="",
    )
    np.savetxt(
        args.output_dir / "phase1e_source_convergence.csv",
        np.column_stack(
            (
                anomaly_counts,
                anomaly_probe_spectra,
            )
        ),
        delimiter=",",
        header=(
            "clustered_anomaly_points,Lnu_5e14Hz,Lnu_1e16Hz,"
            "Lnu_5e16Hz,Lnu_1e17Hz"
        ),
        comments="",
    )

    figure, axes = plt.subplots(3, 2, figsize=(10.5, 11.0))
    height_axis, closure_axis, corrected_axis, measure_axis, ray_axis, phase_axis = (
        axes.ravel()
    )
    colors = {0.0: "#1f4e79", 0.4: "#2a9d8f", 0.8: "#a63d40"}
    for eccentricity, model in reference_models.items():
        height_axis.semilogy(
            model.source.eccentric_anomaly_rad / np.pi,
            model.breathing.dimensionless_height,
            color=colors[eccentricity],
            linewidth=1.7,
            label=rf"$e={eccentricity:.1f}$",
        )
    height_axis.set_xlabel(r"eccentric anomaly $E/\pi$")
    height_axis.set_ylabel(r"dimensionless height $h(E)$")
    height_axis.set_title("ZO Eq. (35) vertical breathing")
    height_axis.legend(frameon=False, fontsize=8)
    height_axis.grid(which="both", alpha=0.18)

    closure_axis.semilogy(
        source.eccentric_anomaly_rad / np.pi,
        h_over_radius[0],
        color="#264653",
        linewidth=1.6,
        label=r"$H/r$",
    )
    closure_axis.semilogy(
        source.eccentric_anomaly_rad / np.pi,
        photosphere_over_radius[0],
        color="#e76f51",
        linewidth=1.8,
        label=r"$z_{\rm ph}/r$",
    )
    closure_axis.axhline(1.0, color="black", linestyle="--", linewidth=0.9)
    closure_axis.set_xlabel(r"eccentric anomaly $E/\pi$")
    closure_axis.set_ylabel("local vertical-to-radial ratio")
    closure_axis.set_title("Gaussian photosphere validity audit")
    closure_axis.legend(frameon=False, fontsize=8)
    closure_axis.grid(which="both", alpha=0.18)

    for eccentricity, spectrum in corrected_spectra.items():
        positive = spectrum.nu_lnu_isotropic_erg_s > 0.0
        corrected_axis.loglog(
            frequency[positive],
            spectrum.nu_lnu_isotropic_erg_s[positive],
            color=colors[eccentricity],
            linewidth=1.7,
            label=rf"$e={eccentricity:.1f}$",
        )
    corrected_axis.axvspan(
        uvopt_lower, uvopt_upper, color="#f4a261", alpha=0.12, linewidth=0
    )
    corrected_axis.axvspan(
        xray_lower, xray_upper, color="#457b9d", alpha=0.09, linewidth=0
    )
    corrected_axis.set_xlabel(r"frequency $\nu$ [Hz]")
    corrected_axis.set_ylabel(r"corrected ZO 2022 $\nu L_{\nu,\rm iso}$ [erg s$^{-1}$]")
    corrected_axis.set_title("Converged ZO constant-e source SED")
    corrected_axis.set_xlim(1.0e14, 1.0e18)
    corrected_axis.set_ylim(1.0e38, 3.0e45)
    corrected_axis.legend(frameon=False, fontsize=8)
    corrected_axis.grid(which="both", alpha=0.18)

    measure_ratio = (
        corrected_e08.isotropic_equivalent_lnu_erg_s_hz
        / pre_erratum_e08.isotropic_equivalent_lnu_erg_s_hz
    )
    positive_measure = np.isfinite(measure_ratio) & (measure_ratio > 0.0)
    measure_axis.semilogx(
        frequency[positive_measure],
        measure_ratio[positive_measure],
        color="#6a4c93",
        linewidth=1.8,
    )
    measure_axis.axhline(
        0.2,
        color="black",
        linestyle="--",
        linewidth=0.9,
        label=r"hot-pericentre limit $1-e$",
    )
    measure_axis.set_xlabel(r"frequency $\nu$ [Hz]")
    measure_axis.set_ylabel("corrected / pre-Erratum face-on")
    measure_axis.set_title("Erratum radiative-area correction")
    measure_axis.legend(frameon=False, fontsize=8)
    measure_axis.grid(which="both", alpha=0.18)

    probe_labels = ("optical", "EUV", "0.21 keV", "0.41 keV")
    probe_colors = ("#f4a261", "#2a9d8f", "#457b9d", "#9b2226")
    hardest_case = 1
    for frequency_index, label in enumerate(probe_labels):
        ray_axis.loglog(
            ray_pixels,
            ray_probe_ratio[hardest_case, :, frequency_index],
            marker="o",
            color=probe_colors[frequency_index],
            linewidth=1.4,
            label=label,
        )
    ray_axis.set_xlabel("pixels on long image axis")
    ray_axis.set_ylabel("ray / corrected ZO 2022 specific luminosity")
    ray_axis.set_title(r"Failed high-frequency ray convergence: $i=30^\circ,\phi=90^\circ$")
    ray_axis.legend(frameon=False, fontsize=7.5, ncol=2)
    ray_axis.grid(which="both", alpha=0.18)

    phase_axis.plot(
        phase_deg,
        phase_optical_ratio,
        color="#1f4e79",
        marker="o",
        markersize=3.2,
        linewidth=1.5,
    )
    phase_axis.set_xlabel(r"relative precession phase $\phi_{\rm obs}-\varpi$ [deg]")
    phase_axis.set_ylabel(r"ray / corrected ZO 2022 at $5\times10^{14}$ Hz")
    phase_axis.set_title(r"Converged optical precession response at $i=30^\circ$")
    phase_axis.grid(alpha=0.18)

    figure.suptitle(
        "Phase 1E: ZO constant-e source and observer-validity audit",
        y=0.992,
    )
    figure.text(
        0.5,
        0.008,
        "source SED and optical phase curve are converged; observer EUV/X-ray spectrum is withheld",
        ha="center",
        fontsize=8.3,
        color="#4b5563",
    )
    figure.tight_layout(rect=(0.0, 0.025, 1.0, 0.98))
    figure.savefig(
        args.output_dir / "phase1e_zo_source_and_ray_audit.png",
        dpi=180,
        bbox_inches="tight",
    )
    plt.close(figure)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
