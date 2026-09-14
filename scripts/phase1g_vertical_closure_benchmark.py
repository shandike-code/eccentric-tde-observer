"""Compare Gaussian and literature n=3 finite vertical closures."""

from __future__ import annotations

import argparse
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
from eccentric_tde_observer.faceon import face_on_blackbody_sed
from eccentric_tde_observer.geometry import build_orbital_surface_mesh
from eccentric_tde_observer.observer import Observer
from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.quadrature import (
    geometric_planar_area_weights,
    corrected_zo_area_weights,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.vertical import (
    GAUSSIAN_VERTICAL_PROFILE,
    RADIATION_PRESSURE_POLYTROPE_PROFILE,
)
from eccentric_tde_observer.zo_reference import (
    ZOConstantEParameters,
    build_zo_constant_e_reference_model,
)


PARSEC_CM = 3.0856775814913673e18
EV_ERG = 1.602176634e-12
CLUSTERING_POWER = 5.0
PROBE_FREQUENCY_HZ = np.array([5.0e14, 1.0e16, 5.0e16, 1.0e17])
AZIMUTH_DEG = (0.0, 90.0, 180.0)


def _energy_kev_to_frequency_hz(energy_kev: float) -> float:
    return energy_kev * 1.0e3 * EV_ERG / PLANCK_ERG_S


def _integrate_band(
    frequency_hz: np.ndarray,
    luminosity_density: np.ndarray,
    lower_hz: float,
    upper_hz: float,
) -> float:
    selected = (frequency_hz >= lower_hz) & (frequency_hz <= upper_hz)
    if np.count_nonzero(selected) < 2:
        raise RuntimeError("frequency grid does not resolve the requested band")
    return float(np.trapezoid(luminosity_density[selected], frequency_hz[selected]))


def _parameters() -> ZOConstantEParameters:
    return ZOConstantEParameters(
        black_hole_mass_msun=1.0e6,
        stellar_mass_msun=1.0,
        stellar_radius_rsun=1.0,
        circularization_efficiency=1.0,
        outer_to_inner_semimajor_axis=2.0,
        eccentricity=0.8,
        opacity_cm2_g=0.34,
    )


def _model(radial_points: int, anomaly_points: int):
    return build_zo_constant_e_reference_model(
        _parameters(),
        radial_points=radial_points,
        anomaly_points=anomaly_points,
        anomaly_sampling="pericentre_clustered",
        pericentre_clustering_power=CLUSTERING_POWER,
    )


def _observer(azimuth_deg: float) -> Observer:
    return Observer(
        100.0e6 * PARSEC_CM,
        np.deg2rad(30.0),
        np.deg2rad(azimuth_deg),
    )


def _geometry_metrics(source, photosphere):
    semimajor_axis = source.semimajor_axis_cm[:, None]
    radius = semimajor_axis * (
        1.0
        - source.eccentricity[:, None]
        * np.cos(source.eccentric_anomaly_rad)[None, :]
    )
    ratio = photosphere.height_cm / radius
    corrected_weight = corrected_zo_area_weights(source)
    cartesian_weight = geometric_planar_area_weights(source)

    def fractions(weight):
        total = np.sum(weight, dtype=np.float64)
        return {
            str(threshold): float(
                np.sum(weight[ratio >= threshold], dtype=np.float64) / total
            )
            for threshold in (0.3, 1.0, 2.0)
        }

    return {
        "scaled_height_min_max": [
            float(np.min(photosphere.scaled_height)),
            float(np.max(photosphere.scaled_height)),
        ],
        "photosphere_over_radius_min_max": [
            float(np.min(ratio)),
            float(np.max(ratio)),
        ],
        "corrected_area_fraction_above_threshold": fractions(corrected_weight),
        "cartesian_area_fraction_above_threshold": fractions(cartesian_weight),
        "corrected_area_mean_scaled_height": float(
            np.sum(photosphere.scaled_height * corrected_weight, dtype=np.float64)
            / np.sum(corrected_weight, dtype=np.float64)
        ),
        "photosphere_over_radius": ratio,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

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

    reference = _model(129, 2048)
    gaussian_photosphere = solve_gray_photosphere(
        reference.source, 0.34, 2.0 / 3.0, GAUSSIAN_VERTICAL_PROFILE
    )
    polytrope_photosphere = solve_gray_photosphere(
        reference.source,
        0.34,
        2.0 / 3.0,
        RADIATION_PRESSURE_POLYTROPE_PROFILE,
    )
    gaussian_geometry = _geometry_metrics(reference.source, gaussian_photosphere)
    polytrope_geometry = _geometry_metrics(reference.source, polytrope_photosphere)

    scaled_height = np.linspace(-5.0, 5.0, 2001)
    gaussian_density = GAUSSIAN_VERTICAL_PROFILE.density_shape(scaled_height)
    polytrope_density = RADIATION_PRESSURE_POLYTROPE_PROFILE.density_shape(
        scaled_height
    )
    gaussian_column = GAUSSIAN_VERTICAL_PROFILE.upper_column_fraction(scaled_height)
    polytrope_column = RADIATION_PRESSURE_POLYTROPE_PROFILE.upper_column_fraction(
        scaled_height
    )
    np.savetxt(
        args.output_dir / "phase1g_vertical_profiles.csv",
        np.column_stack(
            (
                scaled_height,
                gaussian_density,
                polytrope_density,
                gaussian_column,
                polytrope_column,
            )
        ),
        delimiter=",",
        header=(
            "z_over_H,gaussian_density_shape,polytrope_n3_density_shape,"
            "gaussian_upper_column_fraction,polytrope_n3_upper_column_fraction"
        ),
        comments="",
    )

    np.savetxt(
        args.output_dir / "phase1g_inner_orbit_photospheres.csv",
        np.column_stack(
            (
                reference.source.eccentric_anomaly_rad,
                gaussian_photosphere.scaled_height[0],
                polytrope_photosphere.scaled_height[0],
                gaussian_geometry["photosphere_over_radius"][0],
                polytrope_geometry["photosphere_over_radius"][0],
            )
        ),
        delimiter=",",
        header=(
            "eccentric_anomaly_rad,gaussian_zph_over_H,polytrope_zph_over_H,"
            "gaussian_zph_over_r,polytrope_zph_over_r"
        ),
        comments="",
    )

    base = _model(65, 1024)
    base_photosphere = solve_gray_photosphere(
        base.source,
        0.34,
        2.0 / 3.0,
        RADIATION_PRESSURE_POLYTROPE_PROFILE,
    )
    base_mesh = build_orbital_surface_mesh(base.source, base_photosphere.height_cm)
    corrected_spectrum = face_on_blackbody_sed(base.source, frequency)
    corrected_probe = face_on_blackbody_sed(
        base.source, PROBE_FREQUENCY_HZ
    ).isotropic_equivalent_lnu_erg_s_hz
    polytrope_spectra = {}
    polytrope_probe_ratio = {}
    depth_ratio = np.empty((2, PROBE_FREQUENCY_HZ.size))
    depth_rays = np.empty(2, dtype=np.int64)
    depth_seconds = np.empty(2)
    depth_values = (6, 8)

    for azimuth_deg in AZIMUTH_DEG:
        observer = _observer(azimuth_deg)
        triangle_index = build_orthographic_triangle_index(
            base_mesh, observer, bins_long_axis=256
        )
        if azimuth_deg == 90.0:
            final_quadrature = None
            for depth_index, depth in enumerate(depth_values):
                depth_start = time.perf_counter()
                quadrature = render_adaptive_source_surface_quadrature(
                    base_mesh,
                    observer,
                    maximum_subdivision_depth=depth,
                    triangle_index=triangle_index,
                    interior_vertex_fraction=0.01,
                )
                probe_sed = source_surface_blackbody_sed(
                    base.source,
                    base_mesh,
                    observer,
                    quadrature,
                    PROBE_FREQUENCY_HZ,
                )
                depth_ratio[depth_index] = (
                    probe_sed.isotropic_equivalent_lnu_erg_s_hz / corrected_probe
                )
                depth_rays[depth_index] = quadrature.ray_count
                depth_seconds[depth_index] = time.perf_counter() - depth_start
                final_quadrature = quadrature
            if final_quadrature is None:
                raise RuntimeError("polytrope adaptive integration produced no result")
            quadrature = final_quadrature
        else:
            quadrature = render_source_surface_quadrature(
                base_mesh,
                observer,
                subdivision_level=0,
                triangle_index=triangle_index,
            )
        spectrum = source_surface_blackbody_sed(
            base.source, base_mesh, observer, quadrature, frequency
        )
        polytrope_spectra[azimuth_deg] = spectrum
        probe = source_surface_blackbody_sed(
            base.source,
            base_mesh,
            observer,
            quadrature,
            PROBE_FREQUENCY_HZ,
        )
        polytrope_probe_ratio[azimuth_deg] = (
            probe.isotropic_equivalent_lnu_erg_s_hz / corrected_probe
        )
    depth_change = np.abs(depth_ratio[-1] / depth_ratio[-2] - 1.0)

    source_grids = ((33, 512), (65, 1024), (129, 2048))
    grid_ratio = np.empty((len(source_grids), PROBE_FREQUENCY_HZ.size))
    grid_seconds = np.empty(len(source_grids))
    for grid_index, (radial_points, anomaly_points) in enumerate(source_grids):
        grid_start = time.perf_counter()
        if (radial_points, anomaly_points) == (65, 1024):
            model = base
            mesh = base_mesh
        else:
            model = _model(radial_points, anomaly_points)
            photosphere = solve_gray_photosphere(
                model.source,
                0.34,
                2.0 / 3.0,
                RADIATION_PRESSURE_POLYTROPE_PROFILE,
            )
            mesh = build_orbital_surface_mesh(model.source, photosphere.height_cm)
        observer = _observer(90.0)
        bins = 512 if anomaly_points >= 2048 else 256
        triangle_index = build_orthographic_triangle_index(
            mesh, observer, bins_long_axis=bins
        )
        quadrature = render_adaptive_source_surface_quadrature(
            mesh,
            observer,
            maximum_subdivision_depth=6,
            triangle_index=triangle_index,
            interior_vertex_fraction=0.01,
        )
        spectrum = source_surface_blackbody_sed(
            model.source,
            mesh,
            observer,
            quadrature,
            PROBE_FREQUENCY_HZ,
        )
        grid_reference = face_on_blackbody_sed(
            model.source, PROBE_FREQUENCY_HZ
        ).isotropic_equivalent_lnu_erg_s_hz
        grid_ratio[grid_index] = (
            spectrum.isotropic_equivalent_lnu_erg_s_hz / grid_reference
        )
        grid_seconds[grid_index] = time.perf_counter() - grid_start
        print(
            f"source grid {radial_points}x{anomaly_points} completed in "
            f"{grid_seconds[grid_index]:.1f} s",
            flush=True,
        )
    grid_change = np.full_like(grid_ratio, -1.0)
    grid_change[1:] = np.abs(grid_ratio[1:] / grid_ratio[:-1] - 1.0)

    gaussian_table = np.genfromtxt(
        args.output_dir / "phase1f_adaptive_spectra.csv",
        delimiter=",",
        names=True,
    )
    if not np.array_equal(gaussian_table["frequency_hz"], frequency):
        raise RuntimeError("Phase-1F Gaussian frequency grid does not match Phase 1G")
    gaussian_phi90_lnu = gaussian_table["phi90_Lnu_iso_erg_s_hz"]
    with (args.output_dir / "phase1f_adaptive_report.json").open(
        "r", encoding="utf-8"
    ) as stream:
        phase1f_report = json.load(stream)
    gaussian_probe_ratio = np.asarray(
        phase1f_report["adaptive_depth_audit_phi90"]["ray_to_corrected"][-1],
        dtype=np.float64,
    )

    spectrum_columns = [frequency, corrected_spectrum.isotropic_equivalent_lnu_erg_s_hz]
    spectrum_header = ["frequency_hz", "corrected_Lnu_erg_s_hz"]
    for azimuth_deg in AZIMUTH_DEG:
        spectrum = polytrope_spectra[azimuth_deg]
        label = int(azimuth_deg)
        spectrum_columns.extend(
            (
                spectrum.flux_density_erg_s_cm2_hz,
                spectrum.isotropic_equivalent_lnu_erg_s_hz,
            )
        )
        spectrum_header.extend(
            (
                f"polytrope_phi{label}_Fnu_erg_s_cm2_hz",
                f"polytrope_phi{label}_Lnu_iso_erg_s_hz",
            )
        )
    np.savetxt(
        args.output_dir / "phase1g_polytrope_spectra.csv",
        np.column_stack(spectrum_columns),
        delimiter=",",
        header=",".join(spectrum_header),
        comments="",
    )
    np.savetxt(
        args.output_dir / "phase1g_polytrope_depth_convergence.csv",
        np.column_stack(
            (
                np.array(depth_values),
                depth_rays,
                depth_seconds,
                depth_ratio,
            )
        ),
        delimiter=",",
        header=(
            "maximum_depth,ray_count,seconds,ratio_5e14Hz,ratio_1e16Hz,"
            "ratio_5e16Hz,ratio_1e17Hz"
        ),
        comments="",
    )
    grid_rows = []
    for grid_index, (radial_points, anomaly_points) in enumerate(source_grids):
        grid_rows.append(
            [
                radial_points,
                anomaly_points,
                grid_seconds[grid_index],
                *grid_ratio[grid_index],
                *grid_change[grid_index],
            ]
        )
    np.savetxt(
        args.output_dir / "phase1g_polytrope_grid_convergence.csv",
        np.array(grid_rows),
        delimiter=",",
        header=(
            "radial_points,anomaly_points,seconds,ratio_5e14Hz,ratio_1e16Hz,"
            "ratio_5e16Hz,ratio_1e17Hz,step_5e14Hz,step_1e16Hz,"
            "step_5e16Hz,step_1e17Hz"
        ),
        comments="",
    )

    band_report = {}
    for azimuth_deg in AZIMUTH_DEG:
        luminosity_density = polytrope_spectra[
            azimuth_deg
        ].isotropic_equivalent_lnu_erg_s_hz
        uvopt = _integrate_band(
            frequency, luminosity_density, uvopt_lower, uvopt_upper
        )
        xray = _integrate_band(
            frequency, luminosity_density, xray_lower, xray_upper
        )
        band_report[str(int(azimuth_deg))] = {
            "uvopt_erg_s": uvopt,
            "xray_erg_s": xray,
            "xray_to_uvopt": xray / uvopt,
            "status": (
                "diagnostic only; depth and source-grid convergence failed"
                if azimuth_deg == 90.0
                else "conditional closure; source-grid converged"
            ),
        }

    report_geometry = {}
    for name, metrics in (
        ("gaussian", gaussian_geometry),
        ("polytrope_n3", polytrope_geometry),
    ):
        report_geometry[name] = {
            key: value
            for key, value in metrics.items()
            if key != "photosphere_over_radius"
        }
    report = {
        "classification": (
            "vertical closure sensitivity [L/A/V]; neither closure restores the "
            "local thin-column domain [O/V]"
        ),
        "literature_basis": {
            "source_H": "ZO 2020 Eq. 18 and Eq. 35",
            "finite_profile": "Lynch & Ogilvie 2021 Appendix A Eqs. A5 and A8",
            "polytrope_index": 3,
            "surface_scaled_height": 3.0,
            "central_density_shape": 35.0 / 96.0,
            "unit_column": True,
            "unit_second_moment": True,
        },
        "geometry": report_geometry,
        "polytrope_phi90_adaptive_depth": {
            "depths": list(depth_values),
            "ray_to_corrected": depth_ratio.tolist(),
            "depth6_to_depth8_fractional_change": depth_change.tolist(),
            "below_1_percent_all_probes": bool(np.all(depth_change < 1.0e-2)),
        },
        "polytrope_phi90_source_grid_depth6": {
            "grids": [list(grid) for grid in source_grids],
            "ray_to_corrected": grid_ratio.tolist(),
            "fractional_step_change": grid_change.tolist(),
            "65x1024_to_129x2048": grid_change[-1].tolist(),
            "below_1_percent_all_probes": bool(np.all(grid_change[-1] < 1.0e-2)),
        },
        "phi90_closure_probe_ratio_base_grid": {
            "frequency_hz": PROBE_FREQUENCY_HZ.tolist(),
            "gaussian_depth10": gaussian_probe_ratio.tolist(),
            "polytrope_depth8": polytrope_probe_ratio[90.0].tolist(),
            "polytrope_to_gaussian": (
                polytrope_probe_ratio[90.0] / gaussian_probe_ratio
            ).tolist(),
        },
        "polytrope_band_diagnostics": band_report,
        "disc_wind_applied": False,
        "frequency_shift_applied": False,
        "observer_spectrum_publishable_at_all_frequencies": False,
        "wall_time_seconds": time.perf_counter() - start,
    }
    with (args.output_dir / "phase1g_vertical_closure_report.json").open(
        "w", encoding="utf-8"
    ) as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")

    figure, axes = plt.subplots(2, 3, figsize=(15.5, 9.0), constrained_layout=True)
    axis = axes[0, 0]
    axis.plot(scaled_height, gaussian_density, label="Gaussian [A]")
    axis.plot(scaled_height, polytrope_density, label="n=3 polytrope [L/A]")
    axis.axvline(-3.0, color="gray", linestyle=":", linewidth=1)
    axis.axvline(3.0, color="gray", linestyle=":", linewidth=1)
    axis.set(xlim=(-5, 5), xlabel=r"$z/H$", ylabel=r"$f(z/H)$", title="Unit-column, unit-variance profiles")
    axis.legend(fontsize=8)

    axis = axes[0, 1]
    positive = scaled_height >= 0.0
    axis.semilogy(scaled_height[positive], gaussian_column[positive], label="Gaussian")
    nonzero = positive & (polytrope_column > 0.0)
    axis.semilogy(scaled_height[nonzero], polytrope_column[nonzero], label="n=3 polytrope")
    axis.set(xlim=(0, 5), ylim=(1.0e-8, 0.6), xlabel=r"$z/H$", ylabel="upper column fraction", title="Finite edge versus Gaussian tail")
    axis.legend(fontsize=8)

    axis = axes[0, 2]
    optical_depth = np.geomspace(4.0 / 3.0 * (1.0 + 1.0e-12), 1.0e5, 500)
    required_fraction = (2.0 / 3.0) / optical_depth
    axis.semilogx(
        optical_depth,
        GAUSSIAN_VERTICAL_PROFILE.inverse_upper_column_fraction(required_fraction),
        label="Gaussian",
    )
    axis.semilogx(
        optical_depth,
        RADIATION_PRESSURE_POLYTROPE_PROFILE.inverse_upper_column_fraction(
            required_fraction
        ),
        label="n=3 polytrope",
    )
    axis.axhline(3.0, color="gray", linestyle=":", linewidth=1)
    axis.set(xlabel=r"total $\kappa\Sigma$", ylabel=r"$z_{\rm ph}/H$", title=r"Gray $\tau=2/3$ surface")
    axis.legend(fontsize=8)

    axis = axes[1, 0]
    anomaly = reference.source.eccentric_anomaly_rad
    axis.semilogy(anomaly, gaussian_geometry["photosphere_over_radius"][0], label="Gaussian")
    axis.semilogy(anomaly, polytrope_geometry["photosphere_over_radius"][0], label="n=3 polytrope")
    axis.axhline(1.0, color="black", linestyle="--", linewidth=1)
    axis.set(xlabel=r"eccentric anomaly $E$", ylabel=r"$z_{\rm ph}/r$ at $a_{\rm in}$", title="Local-column domain audit")
    axis.legend(fontsize=8)

    axis = axes[1, 1]
    axis.loglog(
        frequency,
        frequency * corrected_spectrum.isotropic_equivalent_lnu_erg_s_hz,
        color="black",
        linewidth=2,
        label="ZO corrected ZO 2022 source",
    )
    axis.loglog(
        frequency,
        frequency * gaussian_phi90_lnu,
        color="tab:blue",
        linestyle=":",
        linewidth=2,
        label="Gaussian phi=90 deg [O]",
    )
    axis.loglog(
        frequency,
        frequency
        * polytrope_spectra[90.0].isotropic_equivalent_lnu_erg_s_hz,
        color="tab:orange",
        linestyle=":",
        linewidth=2,
        label="n=3 polytrope phi=90 deg [O]",
    )
    axis.set(xlim=(1.0e14, 2.5e18), ylim=(1.0e34, 3.0e45), xlabel=r"$\nu\ [{\rm Hz}]$", ylabel=r"$\nu L_\nu\ [{\rm erg\ s^{-1}}]$", title="Closure-sensitive diagnostic spectra")
    axis.legend(fontsize=8)

    axis = axes[1, 2]
    grid_labels = [f"{radial}x{anomaly_count}" for radial, anomaly_count in source_grids]
    for frequency_index, probe in enumerate(PROBE_FREQUENCY_HZ):
        axis.semilogy(
            grid_labels,
            grid_ratio[:, frequency_index],
            marker="o",
            label=f"{probe:.1e} Hz",
        )
    axis.axhline(1.0e-2, color="black", linestyle="--", linewidth=1)
    axis.set(xlabel="source surface grid", ylabel="polytrope ray / corrected ZO 2022", title="phi=90 deg, adaptive depth 6")
    axis.legend(fontsize=8)

    figure.suptitle(
        "Phase 1G: vertical-closure audit at fixed Zanazzi--Ogilvie source",
        fontsize=14,
    )
    figure.savefig(args.output_dir / "phase1g_vertical_closure_audit.png", dpi=180)
    plt.close(figure)


if __name__ == "__main__":
    main()
