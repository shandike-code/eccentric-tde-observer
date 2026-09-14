"""Generate Phase-1F adaptive source-surface visibility diagnostics."""

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
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.zo_reference import (
    ZOConstantEParameters,
    build_zo_constant_e_reference_model,
)


PARSEC_CM = 3.0856775814913673e18
EV_ERG = 1.602176634e-12
CLUSTERING_POWER = 5.0
INCLINATION_DEG = 30.0
AZIMUTH_DEG = (0.0, 90.0, 180.0)
PROBE_FREQUENCY_HZ = np.array([5.0e14, 1.0e16, 5.0e16, 1.0e17])
ADAPTIVE_DEPTHS = (6, 8, 10)
SOURCE_GRIDS = ((33, 512), (65, 1024), (129, 2048))


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
    return float(np.trapezoid(luminosity_density[inside], frequency_hz[inside]))


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


def _build_model_and_mesh(radial_points: int, anomaly_points: int):
    model = build_zo_constant_e_reference_model(
        _parameters(),
        radial_points=radial_points,
        anomaly_points=anomaly_points,
        anomaly_sampling="pericentre_clustered",
        pericentre_clustering_power=CLUSTERING_POWER,
    )
    photosphere = solve_gray_photosphere(model.source, 0.34, 2.0 / 3.0)
    mesh = build_orbital_surface_mesh(model.source, photosphere.height_cm)
    return model, mesh


def _observer(azimuth_deg: float) -> Observer:
    return Observer(
        100.0e6 * PARSEC_CM,
        np.deg2rad(INCLINATION_DEG),
        np.deg2rad(azimuth_deg),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    start_time = time.perf_counter()

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

    base_model, base_mesh = _build_model_and_mesh(65, 1024)
    corrected_base = face_on_blackbody_sed(base_model.source, frequency)
    corrected_probe_base = face_on_blackbody_sed(
        base_model.source, PROBE_FREQUENCY_HZ
    ).isotropic_equivalent_lnu_erg_s_hz

    spectra = {}
    quadrature_by_case = {}
    depth_ratio = np.empty((len(ADAPTIVE_DEPTHS), PROBE_FREQUENCY_HZ.size))
    depth_rays = np.empty(len(ADAPTIVE_DEPTHS), dtype=np.int64)
    depth_area_ratio = np.empty(len(ADAPTIVE_DEPTHS))
    depth_seconds = np.empty(len(ADAPTIVE_DEPTHS))
    for azimuth_deg in AZIMUTH_DEG:
        observer = _observer(azimuth_deg)
        index = build_orthographic_triangle_index(
            base_mesh, observer, bins_long_axis=256
        )
        if azimuth_deg == 90.0:
            for depth_index, depth in enumerate(ADAPTIVE_DEPTHS):
                case_start = time.perf_counter()
                quadrature = render_adaptive_source_surface_quadrature(
                    base_mesh,
                    observer,
                    maximum_subdivision_depth=depth,
                    triangle_index=index,
                    interior_vertex_fraction=0.01,
                )
                probe_sed = source_surface_blackbody_sed(
                    base_model.source,
                    base_mesh,
                    observer,
                    quadrature,
                    PROBE_FREQUENCY_HZ,
                )
                depth_ratio[depth_index] = (
                    probe_sed.isotropic_equivalent_lnu_erg_s_hz
                    / corrected_probe_base
                )
                depth_rays[depth_index] = quadrature.ray_count
                depth_area_ratio[depth_index] = (
                    quadrature.visible_projected_area_cm2
                    / quadrature.unobscured_projected_area_cm2
                )
                depth_seconds[depth_index] = time.perf_counter() - case_start
                if depth == ADAPTIVE_DEPTHS[-1]:
                    quadrature_by_case[azimuth_deg] = quadrature
        else:
            quadrature_by_case[azimuth_deg] = render_source_surface_quadrature(
                base_mesh,
                observer,
                subdivision_level=0,
                triangle_index=index,
            )
        spectra[azimuth_deg] = source_surface_blackbody_sed(
            base_model.source,
            base_mesh,
            observer,
            quadrature_by_case[azimuth_deg],
            frequency,
        )

    depth_step_change = np.full_like(depth_ratio, -1.0)
    depth_step_change[1:] = np.abs(depth_ratio[1:] / depth_ratio[:-1] - 1.0)

    source_grid_ratio = np.empty(
        (len(SOURCE_GRIDS), len(AZIMUTH_DEG), PROBE_FREQUENCY_HZ.size)
    )
    source_grid_seconds = np.empty(len(SOURCE_GRIDS))
    for grid_index, (radial_points, anomaly_points) in enumerate(SOURCE_GRIDS):
        grid_start = time.perf_counter()
        if (radial_points, anomaly_points) == (65, 1024):
            model = base_model
            mesh = base_mesh
        else:
            model, mesh = _build_model_and_mesh(radial_points, anomaly_points)
        corrected_probe = face_on_blackbody_sed(
            model.source, PROBE_FREQUENCY_HZ
        ).isotropic_equivalent_lnu_erg_s_hz
        for azimuth_index, azimuth_deg in enumerate(AZIMUTH_DEG):
            if (radial_points, anomaly_points) == (65, 1024):
                if azimuth_deg == 90.0:
                    quadrature = render_adaptive_source_surface_quadrature(
                        mesh,
                        _observer(azimuth_deg),
                        maximum_subdivision_depth=8,
                        bins_long_axis=256,
                        interior_vertex_fraction=0.01,
                    )
                else:
                    quadrature = quadrature_by_case[azimuth_deg]
            else:
                observer = _observer(azimuth_deg)
                bins = 512 if anomaly_points >= 2048 else 256
                index = build_orthographic_triangle_index(
                    mesh, observer, bins_long_axis=bins
                )
                if azimuth_deg == 90.0:
                    quadrature = render_adaptive_source_surface_quadrature(
                        mesh,
                        observer,
                        maximum_subdivision_depth=8,
                        triangle_index=index,
                        interior_vertex_fraction=0.01,
                    )
                else:
                    quadrature = render_source_surface_quadrature(
                        mesh,
                        observer,
                        subdivision_level=0,
                        triangle_index=index,
                    )
            grid_sed = source_surface_blackbody_sed(
                model.source,
                mesh,
                _observer(azimuth_deg),
                quadrature,
                PROBE_FREQUENCY_HZ,
            )
            source_grid_ratio[grid_index, azimuth_index] = (
                grid_sed.isotropic_equivalent_lnu_erg_s_hz / corrected_probe
            )
        source_grid_seconds[grid_index] = time.perf_counter() - grid_start
    source_grid_step_change = np.full_like(source_grid_ratio, -1.0)
    source_grid_step_change[1:] = np.abs(
        source_grid_ratio[1:] / source_grid_ratio[:-1] - 1.0
    )

    uniform_4096 = np.full((len(AZIMUTH_DEG), PROBE_FREQUENCY_HZ.size), np.nan)
    uniform_path = args.output_dir / "phase1e_ray_failure_convergence.csv"
    if uniform_path.exists():
        uniform_table = np.genfromtxt(uniform_path, delimiter=",", names=True)
        for azimuth_index, azimuth_deg in enumerate(AZIMUTH_DEG):
            selected = (uniform_table["relative_azimuth_deg"] == azimuth_deg) & (
                uniform_table["pixels_long_axis"] == 4096
            )
            if np.count_nonzero(selected) == 1:
                row = uniform_table[selected]
                uniform_4096[azimuth_index] = np.array(
                    [
                        row["ray_to_corrected_5e14Hz"],
                        row["ray_to_corrected_1e16Hz"],
                        row["ray_to_corrected_5e16Hz"],
                        row["ray_to_corrected_1e17Hz"],
                    ]
                ).reshape(-1)

    spectrum_columns = [frequency, corrected_base.isotropic_equivalent_lnu_erg_s_hz]
    spectrum_header = ["frequency_hz", "corrected_Lnu_erg_s_hz"]
    for azimuth_deg in AZIMUTH_DEG:
        spectrum = spectra[azimuth_deg]
        spectrum_columns.extend(
            (
                spectrum.flux_density_erg_s_cm2_hz,
                spectrum.isotropic_equivalent_lnu_erg_s_hz,
            )
        )
        label = int(azimuth_deg)
        spectrum_header.extend(
            (f"phi{label}_Fnu_erg_s_cm2_hz", f"phi{label}_Lnu_iso_erg_s_hz")
        )
    np.savetxt(
        args.output_dir / "phase1f_adaptive_spectra.csv",
        np.column_stack(spectrum_columns),
        delimiter=",",
        header=",".join(spectrum_header),
        comments="",
    )
    depth_rows = []
    for depth_index, depth in enumerate(ADAPTIVE_DEPTHS):
        depth_rows.append(
            [
                depth,
                depth_rays[depth_index],
                depth_seconds[depth_index],
                depth_area_ratio[depth_index],
                *depth_ratio[depth_index],
                *depth_step_change[depth_index],
            ]
        )
    np.savetxt(
        args.output_dir / "phase1f_adaptive_depth_convergence.csv",
        np.array(depth_rows),
        delimiter=",",
        header=(
            "maximum_depth,ray_count,seconds,visible_to_unobscured_area,"
            "ratio_5e14Hz,ratio_1e16Hz,ratio_5e16Hz,ratio_1e17Hz,"
            "step_5e14Hz,step_1e16Hz,step_5e16Hz,step_1e17Hz"
        ),
        comments="",
    )
    grid_rows = []
    for grid_index, (radial_points, anomaly_points) in enumerate(SOURCE_GRIDS):
        for azimuth_index, azimuth_deg in enumerate(AZIMUTH_DEG):
            grid_rows.append(
                [
                    radial_points,
                    anomaly_points,
                    azimuth_deg,
                    source_grid_seconds[grid_index],
                    *source_grid_ratio[grid_index, azimuth_index],
                    *source_grid_step_change[grid_index, azimuth_index],
                ]
            )
    np.savetxt(
        args.output_dir / "phase1f_surface_grid_convergence.csv",
        np.array(grid_rows),
        delimiter=",",
        header=(
            "radial_points,anomaly_points,relative_azimuth_deg,grid_total_seconds,"
            "ratio_5e14Hz,ratio_1e16Hz,ratio_5e16Hz,ratio_1e17Hz,"
            "step_5e14Hz,step_1e16Hz,step_5e16Hz,step_1e17Hz"
        ),
        comments="",
    )

    band_report = {}
    for azimuth_deg in AZIMUTH_DEG:
        luminosity_density = spectra[
            azimuth_deg
        ].isotropic_equivalent_lnu_erg_s_hz
        uvopt = _integrate_band(
            frequency, luminosity_density, uvopt_lower, uvopt_upper
        )
        xray = _integrate_band(
            frequency, luminosity_density, xray_lower, xray_upper
        )
        band_report[str(int(azimuth_deg))] = {
            "uvopt_0p002_0p1keV_erg_s": uvopt,
            "xray_0p3_10keV_erg_s": xray,
            "xray_to_uvopt": xray / uvopt,
            "status": (
                "diagnostic only; high-frequency source-grid unconverged"
                if azimuth_deg == 90.0
                else "numerically converged conditional closure"
            ),
        }

    report = {
        "classification": (
            "adaptive occultation quadrature [V/A]; phi=90 high-frequency "
            "source-grid convergence failed [O/V]"
        ),
        "algorithm": {
            "integration_domain": "projected source triangles",
            "visibility": "frontmost exact point query over indexed projected triangles",
            "adaptive_rule": (
                "four child centroids plus three interior vertex probes; refine mixed "
                "visibility cells"
            ),
            "new_radiation_physics_added": False,
            "frequency_shift_applied": False,
            "disc_wind_applied": False,
        },
        "model": {
            "eccentricity": 0.8,
            "inclination_deg": INCLINATION_DEG,
            "relative_azimuth_deg": list(AZIMUTH_DEG),
            "base_source_grid": [65, 1024],
            "pericentre_clustering_power": CLUSTERING_POWER,
        },
        "adaptive_depth_audit_phi90": {
            "depths": list(ADAPTIVE_DEPTHS),
            "ray_counts": depth_rays.tolist(),
            "seconds": depth_seconds.tolist(),
            "probe_frequency_hz": PROBE_FREQUENCY_HZ.tolist(),
            "ray_to_corrected": depth_ratio.tolist(),
            "fractional_step_change": depth_step_change.tolist(),
            "depth8_to_depth10_below_1_percent_all_probes": bool(
                np.all(depth_step_change[-1] < 1.0e-2)
            ),
            "depth8_to_depth10_below_1e_minus_3_all_probes": bool(
                np.all(depth_step_change[-1] < 1.0e-3)
            ),
        },
        "source_surface_grid_audit_depth8": {
            "grids": [list(grid) for grid in SOURCE_GRIDS],
            "ray_to_corrected": source_grid_ratio.tolist(),
            "fractional_step_change": source_grid_step_change.tolist(),
            "65x1024_to_129x2048_phi90_change": source_grid_step_change[
                -1, 1
            ].tolist(),
            "phi90_below_1_percent_all_probes": bool(
                np.all(source_grid_step_change[-1, 1] < 1.0e-2)
            ),
        },
        "band_diagnostics": band_report,
        "observer_spectrum_csv_written": True,
        "observer_spectrum_publishable_at_all_frequencies": False,
        "reason_not_publishable": (
            "phi=90 high-frequency flux changes by order unity when the source "
            "surface grid is refined"
        ),
        "wall_time_seconds": time.perf_counter() - start_time,
    }
    with (args.output_dir / "phase1f_adaptive_report.json").open(
        "w", encoding="utf-8"
    ) as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")

    colors = {0.0: "tab:blue", 90.0: "tab:orange", 180.0: "tab:green"}
    figure, axes = plt.subplots(2, 3, figsize=(15.5, 9.0), constrained_layout=True)
    axis = axes[0, 0]
    axis.loglog(
        frequency,
        frequency * corrected_base.isotropic_equivalent_lnu_erg_s_hz,
        color="black",
        linewidth=2.0,
        label="ZO corrected ZO 2022 source",
    )
    for azimuth_deg in AZIMUTH_DEG:
        luminosity = spectra[azimuth_deg].isotropic_equivalent_lnu_erg_s_hz
        label = rf"$\phi_{{\rm obs}}-\varpi={azimuth_deg:.0f}^\circ$"
        if azimuth_deg == 90.0:
            axis.loglog(
                frequency,
                frequency * luminosity,
                color=colors[azimuth_deg],
                linestyle=":",
                linewidth=2.0,
                label=label + " (high-$\\nu$ unresolved)",
            )
            resolved = frequency <= 1.0e16
            axis.loglog(
                frequency[resolved],
                frequency[resolved] * luminosity[resolved],
                color=colors[azimuth_deg],
                linewidth=2.0,
            )
        else:
            axis.loglog(
                frequency,
                frequency * luminosity,
                color=colors[azimuth_deg],
                linewidth=1.7,
                label=label,
            )
    axis.axvspan(1.0e16, frequency[-1], color="tab:red", alpha=0.06)
    axis.set(xlabel=r"$\nu\ [{\rm Hz}]$", ylabel=r"$\nu L_\nu\ [{\rm erg\ s^{-1}}]$", title="Conditional observer spectra")
    axis.set_xlim(1.0e14, 2.5e18)
    axis.set_ylim(1.0e34, 3.0e45)
    axis.legend(fontsize=8)

    axis = axes[0, 1]
    for azimuth_deg in AZIMUTH_DEG:
        axis.loglog(
            frequency,
            spectra[azimuth_deg].isotropic_equivalent_lnu_erg_s_hz
            / corrected_base.isotropic_equivalent_lnu_erg_s_hz,
            color=colors[azimuth_deg],
            label=f"{azimuth_deg:.0f} deg",
        )
    axis.axvspan(1.0e16, frequency[-1], color="tab:red", alpha=0.06)
    axis.set(xlabel=r"$\nu\ [{\rm Hz}]$", ylabel="observer / corrected ZO 2022", title="Orientation transfer")
    axis.set_xlim(1.0e14, 2.5e18)
    axis.set_ylim(1.0e-12, 2.0)
    axis.legend(fontsize=8)

    axis = axes[0, 2]
    for frequency_index, probe in enumerate(PROBE_FREQUENCY_HZ):
        axis.semilogy(
            ADAPTIVE_DEPTHS,
            depth_ratio[:, frequency_index],
            marker="o",
            label=f"{probe:.1e} Hz",
        )
    axis.set(xlabel="maximum subdivision depth", ylabel="ray / corrected ZO 2022", title="phi=90 deg adaptive depth")
    axis.legend(fontsize=8)

    axis = axes[1, 0]
    for frequency_index, probe in enumerate(PROBE_FREQUENCY_HZ):
        axis.semilogy(
            ADAPTIVE_DEPTHS[1:],
            depth_step_change[1:, frequency_index],
            marker="o",
            label=f"{probe:.1e} Hz",
        )
    axis.axhline(1.0e-2, color="black", linestyle="--", linewidth=1.0)
    axis.axhline(1.0e-3, color="black", linestyle=":", linewidth=1.0)
    axis.set(xlabel="maximum subdivision depth", ylabel="fractional step change", title="Depth convergence")
    axis.legend(fontsize=8)

    axis = axes[1, 1]
    grid_labels = [f"{radial}x{anomaly}" for radial, anomaly in SOURCE_GRIDS]
    for frequency_index, probe in enumerate(PROBE_FREQUENCY_HZ):
        axis.semilogy(
            grid_labels,
            source_grid_ratio[:, 1, frequency_index],
            marker="o",
            label=f"{probe:.1e} Hz",
        )
    axis.set(xlabel="source surface grid", ylabel="ray / corrected ZO 2022", title="phi=90 deg source-grid audit")
    axis.legend(fontsize=8)

    axis = axes[1, 2]
    adaptive_probe = np.stack(
        (
            source_grid_ratio[1, 0],
            depth_ratio[-1],
            source_grid_ratio[1, 2],
        )
    )
    x = np.arange(PROBE_FREQUENCY_HZ.size)
    width = 0.12
    for case_index, azimuth_deg in enumerate(AZIMUTH_DEG):
        axis.bar(
            x + (case_index - 1.5) * width,
            adaptive_probe[case_index],
            width,
            color=colors[azimuth_deg],
            label=f"adaptive {azimuth_deg:.0f} deg",
        )
        if np.all(np.isfinite(uniform_4096[case_index])):
            axis.scatter(
                x + (case_index - 1.5) * width,
                uniform_4096[case_index],
                color="black",
                marker="x",
                s=24,
            )
    axis.set_yscale("log")
    axis.set_xticks(x, ["5e14", "1e16", "5e16", "1e17"])
    axis.set(xlabel=r"$\nu\ [{\rm Hz}]$", ylabel="ray / corrected ZO 2022", title="Adaptive bars; 4096-pixel crosses")
    axis.legend(fontsize=7)

    figure.suptitle(
        "Phase 1F: source-space adaptive occultation (no wind, no frequency shift)",
        fontsize=14,
    )
    figure.savefig(args.output_dir / "phase1f_adaptive_spectrum_audit.png", dpi=180)
    plt.close(figure)


if __name__ == "__main__":
    main()
