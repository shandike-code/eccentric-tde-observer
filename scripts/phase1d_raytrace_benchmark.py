"""Generate Phase-1D orthographic ray-tracing diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np

from eccentric_tde_observer.fixtures import (
    radius_power_law_temperature_eccentric_annulus,
)
from eccentric_tde_observer.geometry import build_orbital_surface_mesh
from eccentric_tde_observer.observer import (
    Observer,
    unobscured_blackbody_sed,
    unobscured_projected_area_cm2,
)
from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S, PLANCK_ERG_S
from eccentric_tde_observer.raytrace import (
    RayImage,
    raytraced_blackbody_sed,
    render_orthographic_surface,
)


PARSEC_CM = 3.0856775814913673e18
EV_ERG = 1.602176634e-12


def _integrate_band(
    frequency_hz: np.ndarray,
    flux_density: np.ndarray,
    lower_hz: float,
    upper_hz: float,
) -> float:
    inside = (frequency_hz >= lower_hz) & (frequency_hz <= upper_hz)
    if np.count_nonzero(inside) < 2:
        raise RuntimeError("frequency grid does not resolve the requested band")
    return float(np.trapezoid(flux_density[inside], frequency_hz[inside]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    inner = 1.0e14
    outer = 2.0e14
    eccentricity = 0.8
    opacity = 0.34
    target_depth = 2.0 / 3.0
    distance = 100.0e6 * PARSEC_CM
    source = radius_power_law_temperature_eccentric_annulus(
        inner,
        outer,
        eccentricity,
        inner_pericentre_temperature_k=3.0e5,
        temperature_index=0.75,
        radial_points=33,
        anomaly_points=256,
    )
    photosphere = solve_gray_photosphere(source, opacity, target_depth)
    mesh = build_orbital_surface_mesh(source, photosphere.height_cm)

    optical_lower = LIGHT_SPEED_CM_S / (8000.0e-8)
    optical_upper = LIGHT_SPEED_CM_S / (3000.0e-8)
    soft_x_lower = 0.2e3 * EV_ERG / PLANCK_ERG_S
    soft_x_upper = 0.4e3 * EV_ERG / PLANCK_ERG_S
    base_frequency = np.geomspace(1.0e14, 1.0e17, 301)
    frequency = np.unique(
        np.concatenate(
            (
                base_frequency,
                [optical_lower, optical_upper, soft_x_lower, soft_x_upper],
            )
        )
    )

    convergence_pixels = np.array([1024, 2048, 4096, 6144, 8192, 12288])
    convergence_probe_frequency = np.array([5.0e14, 1.0e16, 5.0e16, 1.0e17])
    convergence_observer = Observer(distance, np.deg2rad(89.0), np.pi)
    convergence_unobscured = unobscured_blackbody_sed(
        source, mesh, convergence_observer, convergence_probe_frequency
    )
    convergence_area_ratio = np.empty(convergence_pixels.size)
    convergence_transmission = np.empty(
        (convergence_pixels.size, convergence_probe_frequency.size)
    )
    convergence_ray_count = np.empty(convergence_pixels.size, dtype=np.int64)
    final_convergence_image: RayImage | None = None
    for index, pixels in enumerate(convergence_pixels):
        image = render_orthographic_surface(
            mesh, convergence_observer, int(pixels)
        )
        traced = raytraced_blackbody_sed(
            source,
            mesh,
            convergence_observer,
            image,
            convergence_probe_frequency,
        )
        convergence_area_ratio[index] = (
            image.visible_projected_area_cm2
            / unobscured_projected_area_cm2(mesh, convergence_observer)
        )
        convergence_transmission[index] = (
            traced.flux_density_erg_s_cm2_hz
            / convergence_unobscured.flux_density_erg_s_cm2_hz
        )
        convergence_ray_count[index] = image.ray_count
        if pixels == convergence_pixels[-1]:
            final_convergence_image = image
    if final_convergence_image is None:
        raise RuntimeError("final convergence image was not retained")

    mesh_resolution_pairs = np.array(
        [[17, 128], [33, 256], [65, 512], [97, 768]], dtype=np.int64
    )
    mesh_area_ratio = np.empty(mesh_resolution_pairs.shape[0])
    mesh_transmission = np.empty(
        (mesh_resolution_pairs.shape[0], convergence_probe_frequency.size)
    )
    for index, (radial_points, anomaly_points) in enumerate(mesh_resolution_pairs):
        grid_source = radius_power_law_temperature_eccentric_annulus(
            inner,
            outer,
            eccentricity,
            inner_pericentre_temperature_k=3.0e5,
            temperature_index=0.75,
            radial_points=int(radial_points),
            anomaly_points=int(anomaly_points),
        )
        grid_photosphere = solve_gray_photosphere(
            grid_source, opacity, target_depth
        )
        grid_mesh = build_orbital_surface_mesh(
            grid_source, grid_photosphere.height_cm
        )
        grid_unobscured = unobscured_blackbody_sed(
            grid_source,
            grid_mesh,
            convergence_observer,
            convergence_probe_frequency,
        )
        grid_image = render_orthographic_surface(
            grid_mesh, convergence_observer, int(convergence_pixels[-1])
        )
        grid_traced = raytraced_blackbody_sed(
            grid_source,
            grid_mesh,
            convergence_observer,
            grid_image,
            convergence_probe_frequency,
        )
        mesh_area_ratio[index] = (
            grid_image.visible_projected_area_cm2
            / unobscured_projected_area_cm2(grid_mesh, convergence_observer)
        )
        mesh_transmission[index] = (
            grid_traced.flux_density_erg_s_cm2_hz
            / grid_unobscured.flux_density_erg_s_cm2_hz
        )

    case_specs = (
        ("face_on", 0.0, 0.0, 2048),
        ("pericentre_near", 89.0, 0.0, 12288),
        ("apocentre_near", 89.0, 180.0, 12288),
    )
    spectra: dict[str, np.ndarray] = {}
    transmissions: dict[str, np.ndarray] = {}
    case_reports: dict[str, dict[str, float | int | list[int]]] = {}
    visibility_image = final_convergence_image
    for name, inclination_deg, azimuth_deg, pixels in case_specs:
        observer = Observer(
            distance, np.deg2rad(inclination_deg), np.deg2rad(azimuth_deg)
        )
        if name == "apocentre_near":
            image = final_convergence_image
        else:
            image = render_orthographic_surface(mesh, observer, pixels)
        traced = raytraced_blackbody_sed(source, mesh, observer, image, frequency)
        unobscured = unobscured_blackbody_sed(source, mesh, observer, frequency)
        ray_flux = traced.flux_density_erg_s_cm2_hz
        spectra[name] = ray_flux
        transmissions[name] = ray_flux / unobscured.flux_density_erg_s_cm2_hz
        optical_flux = _integrate_band(
            frequency, ray_flux, optical_lower, optical_upper
        )
        soft_x_flux = _integrate_band(
            frequency, ray_flux, soft_x_lower, soft_x_upper
        )
        case_reports[name] = {
            "inclination_deg": inclination_deg,
            "azimuth_deg": azimuth_deg,
            "pixels_long_axis": pixels,
            "image_shape": list(image.shape),
            "ray_count": image.ray_count,
            "hit_count": image.hit_count,
            "emitting_count": image.emitting_count,
            "visible_to_unobscured_projected_area": float(
                image.visible_projected_area_cm2
                / unobscured_projected_area_cm2(mesh, observer)
            ),
            "optical_3000_8000A_flux_erg_s_cm2": optical_flux,
            "soft_x_0p2_0p4keV_flux_erg_s_cm2": soft_x_flux,
            "soft_x_to_optical_flux_ratio": soft_x_flux / optical_flux,
        }

    last_step_change = np.abs(
        convergence_transmission[-1] / convergence_transmission[-2] - 1.0
    )
    mesh_last_step_change = np.abs(
        mesh_transmission[-1] / mesh_transmission[-2] - 1.0
    )
    report = {
        "classification": "orthographic ray-tracing stress test [A/V], not a TDE prediction",
        "source_temperature_from_ZO": False,
        "temperature_fixture": "T_eff proportional to r^-3/4, normalized to 3e5 K at the inner pericentre",
        "eccentricity": eccentricity,
        "scale_height_fixture": "H/r = 0.01",
        "opacity_cm2_g": opacity,
        "photosphere_scaled_height": float(photosphere.scaled_height[0, 0]),
        "ray_method": "Newtonian orthographic triangle rasterization with frontmost-depth selection",
        "observer_distance_mpc": 100.0,
        "frequency_range_hz": [float(frequency[0]), float(frequency[-1])],
        "optical_band_angstrom": [3000.0, 8000.0],
        "soft_x_diagnostic_band_keV": [0.2, 0.4],
        "cases": case_reports,
        "convergence_observer": {"inclination_deg": 89.0, "azimuth_deg": 180.0},
        "convergence_pixels_long_axis": convergence_pixels.tolist(),
        "convergence_ray_counts": convergence_ray_count.tolist(),
        "convergence_visible_to_unobscured_area": convergence_area_ratio.tolist(),
        "convergence_probe_frequency_hz": convergence_probe_frequency.tolist(),
        "convergence_transmission": convergence_transmission.tolist(),
        "last_step_fractional_transmission_change": last_step_change.tolist(),
        "mesh_convergence_radial_anomaly_points": mesh_resolution_pairs.tolist(),
        "mesh_convergence_visible_to_unobscured_area": mesh_area_ratio.tolist(),
        "mesh_convergence_transmission": mesh_transmission.tolist(),
        "mesh_last_step_fractional_transmission_change": (
            mesh_last_step_change.tolist()
        ),
        "self_occultation_applied": True,
        "lte_blackbody_intensity_applied": True,
        "absorption_transfer_applied": False,
        "scattering_transfer_applied": False,
        "frequency_shift_applied": False,
        "side_walls_included": False,
    }
    (args.output_dir / "phase1d_raytrace_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )

    spectrum_columns = [frequency]
    spectrum_header = ["frequency_hz"]
    for name, *_ in case_specs:
        spectrum_columns.extend((spectra[name], transmissions[name]))
        spectrum_header.extend((f"{name}_Fnu", f"{name}_ray_to_unobscured"))
    np.savetxt(
        args.output_dir / "phase1d_ray_spectra.csv",
        np.column_stack(spectrum_columns),
        delimiter=",",
        header=",".join(spectrum_header),
        comments="",
    )
    convergence_columns = [
        convergence_pixels,
        convergence_ray_count,
        convergence_area_ratio,
        *[convergence_transmission[:, index] for index in range(4)],
    ]
    np.savetxt(
        args.output_dir / "phase1d_ray_convergence.csv",
        np.column_stack(convergence_columns),
        delimiter=",",
        header=(
            "pixels_long_axis,ray_count,visible_to_unobscured_area,"
            "transmission_5e14Hz,transmission_1e16Hz,"
            "transmission_5e16Hz,transmission_1e17Hz"
        ),
        comments="",
    )
    np.savetxt(
        args.output_dir / "phase1d_mesh_convergence.csv",
        np.column_stack(
            (
                mesh_resolution_pairs,
                mesh_area_ratio,
                *[mesh_transmission[:, index] for index in range(4)],
            )
        ),
        delimiter=",",
        header=(
            "radial_points,anomaly_points,visible_to_unobscured_area,"
            "transmission_5e14Hz,transmission_1e16Hz,"
            "transmission_5e16Hz,transmission_1e17Hz"
        ),
        comments="",
    )

    figure, axes = plt.subplots(2, 2, figsize=(10.2, 7.8))
    visibility_axis, convergence_axis, spectrum_axis, transmission_axis = axes.ravel()

    visibility_category = np.zeros(visibility_image.shape, dtype=np.int8)
    visibility_category[visibility_image.hit_mask] = 2
    visibility_category[visibility_image.emitting_mask] = 1
    extent = [
        visibility_image.u_centers_cm[0] / outer,
        visibility_image.u_centers_cm[-1] / outer,
        visibility_image.v_centers_cm[0] / outer,
        visibility_image.v_centers_cm[-1] / outer,
    ]
    visibility_axis.imshow(
        visibility_category,
        origin="lower",
        extent=extent,
        interpolation="nearest",
        aspect="auto",
        cmap=ListedColormap(["#f7f7f7", "#2a9d8f", "#8c2d04"]),
        vmin=0,
        vmax=2,
    )
    visibility_axis.set_xlabel(r"image coordinate $u/a_{\rm out}$")
    visibility_axis.set_ylabel(r"image coordinate $v/a_{\rm out}$")
    visibility_axis.set_title(r"Frontmost pixels: $i=89^\circ,\ \phi=180^\circ$")
    visibility_axis.text(
        0.02,
        0.96,
        "green: emitting\nred: opaque back-facing blocker",
        transform=visibility_axis.transAxes,
        ha="left",
        va="top",
        fontsize=7.5,
        bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
    )

    convergence_axis.semilogx(
        convergence_pixels,
        convergence_area_ratio,
        marker="o",
        linewidth=1.5,
        label="projected area",
    )
    probe_labels = ("optical", "EUV", "0.21 keV", "0.41 keV")
    line_styles = ("--", "-.", ":", (0, (3, 1, 1, 1)))
    for index, label in enumerate(probe_labels):
        convergence_axis.semilogx(
            convergence_pixels,
            convergence_transmission[:, index],
            linestyle=line_styles[index],
            marker=".",
            linewidth=1.1,
            label=label,
        )
    convergence_axis.set_xlabel("pixels on long image axis")
    convergence_axis.set_ylabel("ray / unobscured result")
    convergence_axis.set_title("Frequency-dependent ray convergence")
    convergence_axis.legend(frameon=False, fontsize=7, ncol=2)
    convergence_axis.grid(which="both", alpha=0.18)

    colors = {
        "face_on": "#1f4e79",
        "pericentre_near": "#e76f51",
        "apocentre_near": "#6a4c93",
    }
    labels = {
        "face_on": r"$i=0^\circ$",
        "pericentre_near": r"$i=89^\circ,\ \phi=0^\circ$",
        "apocentre_near": r"$i=89^\circ,\ \phi=180^\circ$",
    }
    for name in spectra:
        isotropic_nu_lnu = 4.0 * np.pi * distance**2 * frequency * spectra[name]
        spectrum_axis.loglog(
            frequency,
            isotropic_nu_lnu,
            color=colors[name],
            linewidth=1.7,
            label=labels[name],
        )
    spectrum_axis.axvspan(
        optical_lower, optical_upper, color="#f4a261", alpha=0.12, linewidth=0
    )
    spectrum_axis.axvspan(
        soft_x_lower, soft_x_upper, color="#457b9d", alpha=0.10, linewidth=0
    )
    spectrum_axis.set_xlabel(r"frequency $\nu$ [Hz]")
    spectrum_axis.set_ylabel(r"isotropic-equivalent $\nu L_\nu$ [erg s$^{-1}$]")
    spectrum_axis.set_title("First ray-integrated fixture spectrum")
    spectrum_axis.legend(frameon=False, fontsize=7.5)
    spectrum_axis.grid(which="both", alpha=0.18)

    for name in transmissions:
        transmission_axis.semilogx(
            frequency,
            transmissions[name],
            color=colors[name],
            linewidth=1.6,
            label=labels[name],
        )
    transmission_axis.axhline(1.0, color="black", linewidth=0.8, linestyle="--")
    transmission_axis.set_xlabel(r"frequency $\nu$ [Hz]")
    transmission_axis.set_ylabel("ray / unobscured spectrum")
    transmission_axis.set_title("Occultation plus pixel-quadrature response")
    transmission_axis.legend(frameon=False, fontsize=7.5)
    transmission_axis.grid(which="both", alpha=0.18)

    figure.suptitle("Phase 1D: orthographic visibility and LTE ray spectrum", y=0.98)
    figure.text(
        0.5,
        0.012,
        "stress-test fixture only — imposed T(r), no absorption/scattering, frequency shift, or disc wind",
        ha="center",
        fontsize=8.2,
        color="#4b5563",
    )
    figure.tight_layout(rect=(0.0, 0.04, 1.0, 0.96))
    figure.savefig(
        args.output_dir / "phase1d_raytrace_spectrum.png",
        dpi=180,
        bbox_inches="tight",
    )
    plt.close(figure)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
