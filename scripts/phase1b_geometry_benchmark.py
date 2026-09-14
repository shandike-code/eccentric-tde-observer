"""Generate the Phase-1B eccentric-geometry and projection diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eccentric_tde_observer.fixtures import (
    constant_temperature_circular_annulus,
    constant_temperature_eccentric_annulus,
)
from eccentric_tde_observer.geometry import build_orbital_surface_mesh
from eccentric_tde_observer.observer import Observer, unobscured_projected_area_cm2
from eccentric_tde_observer.quadrature import (
    geometric_planar_area_weights,
    corrected_zo_area_weights,
)


PARSEC_CM = 3.0856775814913673e18


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    inner = 1.0e14
    outer = 2.0e14
    eccentricity = 0.8
    source = constant_temperature_eccentric_annulus(
        inner,
        outer,
        eccentricity,
        5.0e4,
        radial_points=9,
        anomaly_points=128,
    )
    mesh = build_orbital_surface_mesh(source)
    analytic_area = (
        np.pi * np.sqrt(1.0 - eccentricity**2) * (outer**2 - inner**2)
    )

    measure_ratio = (
        geometric_planar_area_weights(source) / corrected_zo_area_weights(source)
    )[0]
    distance = 100.0e6 * PARSEC_CM
    inclination_deg = np.linspace(0.0, 85.0, 86)
    azimuth_deg = np.array([0.0, 45.0, 90.0])
    projected_ratio = np.empty((azimuth_deg.size, inclination_deg.size))
    face_on_area = unobscured_projected_area_cm2(
        mesh, Observer(distance, 0.0, 0.0)
    )
    for azimuth_index, azimuth in enumerate(np.deg2rad(azimuth_deg)):
        for inclination_index, inclination in enumerate(np.deg2rad(inclination_deg)):
            observer = Observer(distance, inclination, azimuth)
            projected_ratio[azimuth_index, inclination_index] = (
                unobscured_projected_area_cm2(mesh, observer) / face_on_area
            )

    anomaly_counts = np.array([16, 32, 64, 128, 256])
    area_errors = np.empty(anomaly_counts.size)
    for index, anomaly_points in enumerate(anomaly_counts):
        convergence_source = constant_temperature_eccentric_annulus(
            inner,
            outer,
            eccentricity,
            5.0e4,
            radial_points=5,
            anomaly_points=int(anomaly_points),
        )
        convergence_mesh = build_orbital_surface_mesh(convergence_source)
        area_errors[index] = abs(convergence_mesh.total_area_cm2 / analytic_area - 1.0)
    convergence_orders = np.log2(area_errors[:-1] / area_errors[1:])

    circular = constant_temperature_circular_annulus(inner, outer, 5.0e4)
    circular_measure_difference = np.max(
        np.abs(
            geometric_planar_area_weights(circular)
            - corrected_zo_area_weights(circular)
        )
    )
    cosine_reference = np.cos(np.deg2rad(inclination_deg))
    maximum_projection_error = np.max(
        np.abs(projected_ratio - cosine_reference[None, :])
    )
    report = {
        "classification": "analytic geometry verification [L/A/V], not a TDE prediction",
        "eccentricity": eccentricity,
        "corrected_measure": "a*j*da*dE",
        "cartesian_measure": "a*j*(1-e*cos(E))*da*dE",
        "pericentre_measure_ratio": float(measure_ratio[0]),
        "apocentre_measure_ratio": float(
            measure_ratio[source.eccentric_anomaly_rad.size // 2]
        ),
        "analytic_planar_area_cm2": float(analytic_area),
        "mesh_planar_area_cm2": mesh.total_area_cm2,
        "mesh_relative_area_error": float(mesh.total_area_cm2 / analytic_area - 1.0),
        "maximum_absolute_projection_error": float(maximum_projection_error),
        "circular_measure_max_absolute_difference_cm2": float(
            circular_measure_difference
        ),
        "anomaly_grid_counts": anomaly_counts.tolist(),
        "area_convergence_relative_errors": area_errors.tolist(),
        "area_convergence_orders": convergence_orders.tolist(),
        "self_occultation_applied": False,
        "frequency_shift_applied": False,
    }
    (args.output_dir / "phase1b_geometry_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    projection_csv = np.column_stack(
        (inclination_deg, cosine_reference, projected_ratio.T)
    )
    np.savetxt(
        args.output_dir / "phase1b_projection.csv",
        projection_csv,
        delimiter=",",
        header="inclination_deg,cos_i,projection_phi0,projection_phi45,projection_phi90",
        comments="",
    )

    figure, axes = plt.subplots(2, 2, figsize=(9.0, 7.6))
    geometry_axis, measure_axis, projection_axis, convergence_axis = axes.ravel()

    vertices = mesh.vertices_cm.reshape(source.shape + (3,)) / outer
    for radial_index in range(source.shape[0]):
        closed_x = np.append(vertices[radial_index, :, 0], vertices[radial_index, 0, 0])
        closed_y = np.append(vertices[radial_index, :, 1], vertices[radial_index, 0, 1])
        geometry_axis.plot(closed_x, closed_y, color="#1f4e79", linewidth=0.8)
    for anomaly_index in range(0, source.shape[1], 16):
        geometry_axis.plot(
            vertices[:, anomaly_index, 0],
            vertices[:, anomaly_index, 1],
            color="#7895b2",
            linewidth=0.55,
        )
    geometry_axis.scatter([0.0], [0.0], color="black", s=20, zorder=4)
    geometry_axis.annotate(
        "periapsis",
        xy=((inner / outer) * (1.0 - eccentricity), 0.0),
        xytext=(0.35, 0.27),
        arrowprops={"arrowstyle": "->", "linewidth": 0.8},
        fontsize=8.5,
    )
    geometry_axis.set_aspect("equal")
    geometry_axis.set_xlabel(r"$x/a_{\rm out}$")
    geometry_axis.set_ylabel(r"$y/a_{\rm out}$")
    geometry_axis.set_title("Cartesian orbital mesh")
    geometry_axis.grid(alpha=0.18)

    measure_axis.plot(
        source.eccentric_anomaly_rad / np.pi,
        measure_ratio,
        color="#8c2d04",
        linewidth=2.0,
    )
    measure_axis.axhline(1.0, color="black", linestyle="--", linewidth=0.8)
    measure_axis.set_xlabel(r"eccentric anomaly $E/\pi$")
    measure_axis.set_ylabel(r"${\rm d}A_{xy}/{\rm d}A_{\rm corrected ZO}$")
    measure_axis.set_title(r"Kepler factor $1-e\cos E$")
    measure_axis.grid(alpha=0.18)

    line_styles = ("-", "--", ":")
    for index, azimuth in enumerate(azimuth_deg):
        projection_axis.plot(
            inclination_deg,
            projected_ratio[index],
            linestyle=line_styles[index],
            linewidth=1.7,
            label=rf"$\phi_{{\rm obs}}={azimuth:.0f}^\circ$",
        )
    projection_axis.plot(
        inclination_deg,
        cosine_reference,
        color="black",
        linewidth=0.9,
        marker="o",
        markevery=10,
        markersize=2.5,
        label=r"analytic $\cos i$",
    )
    projection_axis.set_xlabel(r"inclination $i$ [deg]")
    projection_axis.set_ylabel(r"$A_{\rm proj}/A_{\rm face}$")
    projection_axis.set_title("Flat-disc projection control")
    projection_axis.legend(frameon=False, fontsize=8)
    projection_axis.grid(alpha=0.18)

    convergence_axis.loglog(
        anomaly_counts,
        area_errors,
        marker="o",
        color="#3f6f3f",
        linewidth=1.7,
        label="triangular mesh",
    )
    reference = area_errors[0] * (anomaly_counts[0] / anomaly_counts) ** 2
    convergence_axis.loglog(
        anomaly_counts,
        reference,
        color="black",
        linestyle="--",
        linewidth=0.9,
        label=r"$N_E^{-2}$",
    )
    convergence_axis.set_xlabel(r"periodic resolution $N_E$")
    convergence_axis.set_ylabel("relative area error")
    convergence_axis.set_title("Geometric area convergence")
    convergence_axis.set_xscale("log", base=2)
    convergence_axis.set_xticks(anomaly_counts)
    convergence_axis.set_xticklabels([str(value) for value in anomaly_counts])
    convergence_axis.legend(frameon=False, fontsize=8)
    convergence_axis.grid(which="both", alpha=0.18)

    figure.suptitle("Phase 1B: eccentric geometry and unobscured projection", y=0.98)
    figure.text(
        0.5,
        0.012,
        "analytic validation only — no photosphere closure, occultation, or frequency shift",
        ha="center",
        fontsize=8.5,
        color="#4b5563",
    )
    figure.tight_layout(rect=(0.0, 0.035, 1.0, 0.96))
    figure.savefig(
        args.output_dir / "phase1b_geometry_projection.png",
        dpi=180,
        bbox_inches="tight",
    )
    plt.close(figure)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
