"""Generate Phase-1C Gaussian vertical-closure diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eccentric_tde_observer.fixtures import constant_temperature_eccentric_annulus
from eccentric_tde_observer.geometry import build_orbital_surface_mesh
from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.vertical import GAUSSIAN_VERTICAL_PROFILE


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
    source = constant_temperature_eccentric_annulus(
        inner,
        outer,
        eccentricity,
        5.0e4,
        radial_points=17,
        anomaly_points=128,
    )
    photosphere = solve_gray_photosphere(source, opacity, target_depth)
    planar_mesh = build_orbital_surface_mesh(source)
    photosphere_mesh = build_orbital_surface_mesh(source, photosphere.height_cm)

    zeta = np.linspace(0.0, 6.0, 401)
    density_shape = GAUSSIAN_VERTICAL_PROFILE.density_shape(zeta)
    upper_fraction = GAUSSIAN_VERTICAL_PROFILE.upper_column_fraction(zeta)
    total_depth_grid = np.geomspace(2.0 * target_depth, 1.0e8, 401)
    photosphere_zeta_grid = GAUSSIAN_VERTICAL_PROFILE.inverse_upper_column_fraction(
        target_depth / total_depth_grid
    )

    integration_grid = np.linspace(-10.0, 10.0, 40001)
    normalization = np.trapezoid(
        GAUSSIAN_VERTICAL_PROFILE.density_shape(integration_grid),
        integration_grid,
    )
    reconstructed_depth = (
        photosphere.total_vertical_optical_depth
        * GAUSSIAN_VERTICAL_PROFILE.upper_column_fraction(
            photosphere.scaled_height
        )
    )
    maximum_depth_error = np.max(
        np.abs(reconstructed_depth / target_depth - 1.0)
    )
    sigma_value = float(source.surface_density_g_cm2[0, 0])
    optically_thick_sigma_threshold = 2.0 * target_depth / opacity
    report = {
        "classification": "vertical-closure verification [A/V], not a TDE prediction",
        "profile": photosphere.profile_name,
        "opacity_cm2_g": opacity,
        "opacity_role": "electron-scattering benchmark only; not a thermalization model",
        "surface_density_g_cm2": sigma_value,
        "target_optical_depth": target_depth,
        "total_vertical_optical_depth": float(
            photosphere.total_vertical_optical_depth[0, 0]
        ),
        "midplane_optical_depth": float(
            photosphere.midplane_to_surface_optical_depth[0, 0]
        ),
        "photosphere_scaled_height": float(photosphere.scaled_height[0, 0]),
        "photosphere_height_min_cm": float(np.min(photosphere.height_cm)),
        "photosphere_height_max_cm": float(np.max(photosphere.height_cm)),
        "optically_thick_sigma_threshold_g_cm2": float(
            optically_thick_sigma_threshold
        ),
        "density_normalization": float(normalization),
        "density_normalization_error": float(normalization - 1.0),
        "maximum_optical_depth_reconstruction_error": float(
            maximum_depth_error
        ),
        "planar_mesh_area_cm2": planar_mesh.total_area_cm2,
        "photosphere_mesh_area_cm2": photosphere_mesh.total_area_cm2,
        "photosphere_to_planar_area_ratio": float(
            photosphere_mesh.total_area_cm2 / planar_mesh.total_area_cm2
        ),
        "self_occultation_applied": False,
        "thermalization_depth_solved": False,
    }
    (args.output_dir / "phase1c_vertical_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    np.savetxt(
        args.output_dir / "phase1c_photosphere_curve.csv",
        np.column_stack((total_depth_grid, photosphere_zeta_grid)),
        delimiter=",",
        header="total_kappa_sigma,photosphere_z_over_H_for_tau_2over3",
        comments="",
    )

    figure = plt.figure(figsize=(9.2, 7.8))
    profile_axis = figure.add_subplot(2, 2, 1)
    depth_axis = figure.add_subplot(2, 2, 2)
    orbit_axis = figure.add_subplot(2, 2, 3)
    surface_axis = figure.add_subplot(2, 2, 4, projection="3d")

    profile_axis.semilogy(
        zeta, density_shape, color="#1f4e79", linewidth=2.0, label=r"$f(\zeta)$"
    )
    profile_axis.semilogy(
        zeta,
        upper_fraction,
        color="#a63d40",
        linestyle="--",
        linewidth=1.8,
        label=r"$\int_\zeta^\infty f(u)\,du$",
    )
    profile_axis.set_xlabel(r"scaled height $\zeta=z/H$")
    profile_axis.set_ylabel("dimensionless density / column")
    profile_axis.set_title("Normalized Gaussian closure")
    profile_axis.legend(frameon=False, fontsize=8)
    profile_axis.grid(which="both", alpha=0.18)

    depth_axis.semilogx(
        total_depth_grid,
        photosphere_zeta_grid,
        color="#6a4c93",
        linewidth=2.0,
    )
    benchmark_depth = opacity * sigma_value
    depth_axis.scatter(
        [benchmark_depth],
        [photosphere.scaled_height[0, 0]],
        color="black",
        s=25,
        zorder=3,
        label=rf"benchmark $\kappa\Sigma={benchmark_depth:.0f}$",
    )
    depth_axis.set_xlabel(r"total gray depth $\kappa\Sigma$")
    depth_axis.set_ylabel(r"photosphere height $z_{\rm ph}/H$")
    depth_axis.set_title(r"Upper $\tau_\star=2/3$ surface")
    depth_axis.legend(frameon=False, fontsize=8)
    depth_axis.grid(which="both", alpha=0.18)

    anomaly = source.eccentric_anomaly_rad
    inner_index = 0
    orbit_axis.plot(
        anomaly / np.pi,
        source.scale_height_cm[inner_index] / inner,
        color="#2a9d8f",
        linewidth=1.8,
        label=r"$H/a_{\rm in}$",
    )
    orbit_axis.plot(
        anomaly / np.pi,
        photosphere.height_cm[inner_index] / inner,
        color="#e76f51",
        linewidth=2.0,
        label=r"$z_{\rm ph}/a_{\rm in}$",
    )
    orbit_axis.set_xlabel(r"eccentric anomaly $E/\pi$")
    orbit_axis.set_ylabel("normalized height")
    orbit_axis.set_title("Fixture height around an eccentric orbit")
    orbit_axis.legend(frameon=False, fontsize=8)
    orbit_axis.grid(alpha=0.18)

    vertices = photosphere_mesh.vertices_cm.reshape(source.shape + (3,)) / outer
    for radial_index in range(0, source.shape[0], 2):
        closed = np.concatenate(
            (vertices[radial_index], vertices[radial_index, :1]), axis=0
        )
        surface_axis.plot(
            closed[:, 0], closed[:, 1], closed[:, 2], color="#264653", linewidth=0.8
        )
    for anomaly_index in range(0, source.shape[1], 16):
        surface_axis.plot(
            vertices[:, anomaly_index, 0],
            vertices[:, anomaly_index, 1],
            vertices[:, anomaly_index, 2],
            color="#8ab0ab",
            linewidth=0.6,
        )
    surface_axis.set_xlabel(r"$x/a_{\rm out}$", labelpad=3)
    surface_axis.set_ylabel(r"$y/a_{\rm out}$", labelpad=3)
    surface_axis.set_zlabel(r"$z_{\rm ph}/a_{\rm out}$", labelpad=3)
    surface_axis.set_title("Upper photosphere mesh")
    surface_axis.view_init(elev=21.0, azim=-65.0)

    figure.suptitle("Phase 1C: Gaussian vertical closure and gray photosphere", y=0.98)
    figure.text(
        0.5,
        0.012,
        "closure benchmark only — scattering photosphere is not a thermalization depth",
        ha="center",
        fontsize=8.5,
        color="#4b5563",
    )
    figure.tight_layout(rect=(0.0, 0.04, 1.0, 0.96))
    figure.savefig(
        args.output_dir / "phase1c_vertical_closure.png",
        dpi=180,
        bbox_inches="tight",
    )
    plt.close(figure)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
