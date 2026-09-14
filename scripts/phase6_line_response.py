"""Generate the conditional Halpha kinematic-line response audit."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eccentric_tde_observer.adaptive import (
    render_adaptive_source_surface_quadrature,
    render_source_surface_quadrature,
    source_surface_blackbody_sed,
)
from eccentric_tde_observer.fixtures import constant_temperature_circular_annulus
from eccentric_tde_observer.geometry import (
    build_orbital_surface_mesh,
    build_surface_mesh_from_vertices_faces,
)
from eccentric_tde_observer.line_response import (
    HALPHA_REST_WAVELENGTH_ANGSTROM,
    arcsine_ring_bin_probabilities,
    fully_ionized_emission_measure_line_weight,
    geometric_uniform_line_weight,
    hydrogen_thermal_velocity_dispersion_cm_s,
    line_diagnostics,
    numerical_newtonian_ring_bin_probabilities,
    observer_line_profile,
    velocity_grid_cm_s,
    zo_thermal_power_line_weight,
)
from eccentric_tde_observer.observer import Observer
from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model
from eccentric_tde_observer.relativity import (
    GRAVITATIONAL_CONSTANT_CGS,
    homologous_vertical_velocity_cm_s,
    straight_ray_frequency_shift,
)
from eccentric_tde_observer.vertical import RADIATION_PRESSURE_POLYTROPE_PROFILE
from eccentric_tde_observer.zo_reference import SOLAR_MASS_G


PARSEC_CM = 3.0856775814913673e18
DISTANCE_CM = 100.0e6 * PARSEC_CM
INCLINATIONS_DEG = np.array([0.0, 15.0, 30.0, 45.0, 60.0, 70.0, 75.0])
PHASES_DEG = np.arange(0.0, 360.0, 15.0)
WEIGHT_KEYS = ("uniform", "thermal_power", "emission_measure")
WEIGHT_LABELS = {
    "uniform": "uniform [A-control]",
    "thermal_power": r"$\sigma_{\rm SB}T_{\rm eff}^4$ [A-proxy]",
    "emission_measure": "fully ionized EM [A-proxy]",
}


def _model_geometry(eccentricity: float, radial: int, anomaly: int):
    model = build_strict_domain_reference_model(
        radial,
        anomaly,
        eccentricity=eccentricity,
    )
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
    weights = {
        "uniform": geometric_uniform_line_weight(model.source),
        "thermal_power": zo_thermal_power_line_weight(model.source),
        "emission_measure": fully_ionized_emission_measure_line_weight(
            model.source
        ),
    }
    return model, photosphere, mesh, vertical_velocity, weights


def _characteristic_speed(model) -> float:
    return float(
        np.sqrt(
            GRAVITATIONAL_CONSTANT_CGS
            * model.parameters.black_hole_mass_msun
            * SOLAR_MASS_G
            / model.inner_semimajor_axis_cm
        )
    )


def _profile(
    model,
    mesh,
    vertical_velocity,
    weight,
    velocity,
    inclination_deg: float,
    phase_deg: float,
    sigma_velocity,
    *,
    adaptive_depth: int | None = None,
):
    observer = Observer(
        DISTANCE_CM,
        np.deg2rad(inclination_deg),
        np.deg2rad(phase_deg),
    )
    if adaptive_depth is None:
        quadrature = render_source_surface_quadrature(
            mesh,
            observer,
            subdivision_level=1,
            bins_long_axis=128,
        )
    else:
        quadrature = render_adaptive_source_surface_quadrature(
            mesh,
            observer,
            maximum_subdivision_depth=adaptive_depth,
            bins_long_axis=128,
        )
    shift = straight_ray_frequency_shift(
        model.source,
        observer,
        model.parameters.black_hole_mass_msun,
        vertical_velocity_cm_s=vertical_velocity,
    )
    profile = observer_line_profile(
        model.source,
        mesh,
        quadrature,
        shift.frequency_shift_factor,
        weight,
        velocity,
        observer_distance_cm=observer.distance_cm,
        rest_wavelength_angstrom=HALPHA_REST_WAVELENGTH_ANGSTROM,
        local_sigma_velocity_cm_s=sigma_velocity,
    )
    return profile, line_diagnostics(profile), observer, quadrature, shift


def _diagnostic_row(eccentricity, inclination, phase, weight_key, diagnostic):
    row = {
        "eccentricity": eccentricity,
        "inclination_deg": inclination,
        "phase_deg": phase,
        "weight": weight_key,
    }
    row.update(asdict(diagnostic))
    return row


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = list(rows[0])
    for row in rows[1:]:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _ring_figure(output_dir: Path, velocity) -> dict[str, float]:
    speed = 1.0e9
    inclination = np.deg2rad(45.0)
    projected = speed * np.sin(inclination)
    analytic = arcsine_ring_bin_probabilities(velocity, projected)
    numerical = numerical_newtonian_ring_bin_probabilities(
        velocity, speed, inclination, azimuth_points=1_000_000
    )
    l1 = float(np.sum(np.abs(numerical - analytic)))
    figure, axis = plt.subplots(figsize=(8.2, 4.8))
    scale = 1.0e5
    axis.plot(
        velocity / scale,
        analytic / np.max(analytic),
        color="black",
        linewidth=2.0,
        label="finite-bin arcsine analytic",
    )
    axis.plot(
        velocity / scale,
        numerical / np.max(numerical),
        color="#d55e00",
        linewidth=1.1,
        alpha=0.8,
        label="uniform-azimuth numerical ring",
    )
    axis.set(
        xlabel=r"$v_{\rm los}$ [km s$^{-1}$]",
        ylabel="normalized bin probability",
        title="Inclined Newtonian ring: arcsine kernel recovery",
    )
    axis.legend(frameon=False)
    axis.grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(output_dir / "phase6_ring_arcsine_validation.png", dpi=180)
    plt.close(figure)
    return {"ring_probability_l1_error": l1}


def _atlas(model, mesh, vertical_velocity, weights, velocity, sigma_main):
    rows: list[dict[str, object]] = []
    profiles: dict[tuple[str, float, float], object] = {}
    visibility = []
    maximum_energy_residual = 0.0
    for inclination in INCLINATIONS_DEG:
        for phase in PHASES_DEG:
            observer = Observer(
                DISTANCE_CM, np.deg2rad(inclination), np.deg2rad(phase)
            )
            quadrature = render_source_surface_quadrature(
                mesh,
                observer,
                subdivision_level=1,
                bins_long_axis=128,
            )
            shift = straight_ray_frequency_shift(
                model.source,
                observer,
                model.parameters.black_hole_mass_msun,
                vertical_velocity_cm_s=vertical_velocity,
            )
            visibility.append(
                quadrature.visible_projected_area_cm2
                / quadrature.unobscured_projected_area_cm2
            )
            for key in WEIGHT_KEYS:
                profile = observer_line_profile(
                    model.source,
                    mesh,
                    quadrature,
                    shift.frequency_shift_factor,
                    weights[key],
                    velocity,
                    observer_distance_cm=observer.distance_cm,
                    local_sigma_velocity_cm_s=sigma_main,
                )
                diagnostic = line_diagnostics(profile)
                profiles[(key, float(inclination), float(phase))] = profile
                rows.append(
                    _diagnostic_row(
                        model.parameters.eccentricity,
                        float(inclination),
                        float(phase),
                        key,
                        diagnostic,
                    )
                )
                maximum_energy_residual = max(
                    maximum_energy_residual, abs(profile.energy_relative_residual)
                )
    return rows, profiles, {
        "minimum_visible_to_unobscured_area": float(np.min(visibility)),
        "maximum_g4_energy_relative_residual": maximum_energy_residual,
    }


def _plot_circular_control(output_dir, velocity, profiles):
    figure, axis = plt.subplots(figsize=(8.4, 5.2))
    for inclination in INCLINATIONS_DEG:
        profile = profiles[("uniform", float(inclination), 0.0)]
        axis.plot(
            velocity / 1.0e5,
            profile.normalized_flambda,
            linewidth=1.4,
            label=rf"$i={inclination:.0f}^\circ$",
        )
    axis.set(
        xlim=(-20_000.0, 20_000.0),
        xlabel=r"$v=c(\lambda/\lambda_0-1)$ [km s$^{-1}$]",
        ylabel=r"normalized $F_\lambda$",
        title="Circular ZO disc control with weak-field transfer",
    )
    axis.legend(frameon=False, ncol=2)
    axis.grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(output_dir / "phase6_circular_inclination_profiles.png", dpi=180)
    plt.close(figure)


def _plot_eccentric_grid(output_dir, velocity, profiles):
    inclinations = (0.0, 30.0, 60.0, 75.0)
    phases = (0.0, 90.0, 180.0, 270.0)
    figure, axes = plt.subplots(4, 4, figsize=(15.0, 11.5), sharex=True, sharey=True)
    for row, inclination in enumerate(inclinations):
        for column, phase in enumerate(phases):
            profile = profiles[("thermal_power", inclination, phase)]
            axis = axes[row, column]
            axis.plot(velocity / 1.0e5, profile.normalized_flambda, color="#1f4e79")
            axis.text(
                0.03,
                0.92,
                rf"$i={inclination:.0f}^\circ,\Phi={phase:.0f}^\circ$",
                transform=axis.transAxes,
                va="top",
                fontsize=8,
            )
            axis.set_xlim(-20_000.0, 20_000.0)
            axis.grid(alpha=0.15)
    for axis in axes[-1]:
        axis.set_xlabel(r"$v$ [km s$^{-1}$]")
    for axis in axes[:, 0]:
        axis.set_ylabel(r"normalized $F_\lambda$")
    figure.suptitle("Corrected eccentric ZO disc: conditional Halpha kinematic cores")
    figure.tight_layout()
    figure.savefig(output_dir / "phase6_eccentric_orientation_profiles.png", dpi=180)
    plt.close(figure)


def _plot_weight_comparison(output_dir, velocity, profiles):
    figure, axis = plt.subplots(figsize=(8.4, 5.2))
    colors = ("#000000", "#0072b2", "#d55e00")
    for key, color in zip(WEIGHT_KEYS, colors, strict=True):
        profile = profiles[(key, 60.0, 90.0)]
        axis.plot(
            velocity / 1.0e5,
            profile.normalized_flambda,
            color=color,
            linewidth=1.8,
            label=WEIGHT_LABELS[key],
        )
    axis.set(
        xlim=(-20_000.0, 20_000.0),
        xlabel=r"$v$ [km s$^{-1}$]",
        ylabel=r"normalized $F_\lambda$",
        title=r"Weight sensitivity at $i=60^\circ,\Phi=90^\circ$",
    )
    axis.legend(frameon=False)
    axis.grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(output_dir / "phase6_weight_comparison.png", dpi=180)
    plt.close(figure)


def _broadening_scan(
    output_dir,
    model,
    mesh,
    vertical_velocity,
    weight,
    velocity,
    characteristic_speed,
):
    ratios = np.array(
        [0.0, 0.003, 0.01, 0.02, 0.03, 0.05, 0.1, 0.2, 0.3, 0.5]
    )
    profiles = []
    rows = []
    for ratio in ratios:
        profile, diagnostic, *_ = _profile(
            model,
            mesh,
            vertical_velocity,
            weight,
            velocity,
            60.0,
            90.0,
            ratio * characteristic_speed,
        )
        profiles.append(profile)
        row = {"sigma_v_over_vK": float(ratio)}
        row.update(asdict(diagnostic))
        rows.append(row)
    _write_rows(output_dir / "phase6_broadening_sensitivity.csv", rows)
    figure, axis = plt.subplots(figsize=(8.6, 5.5))
    for ratio, profile in zip(ratios, profiles, strict=True):
        axis.plot(
            velocity / 1.0e5,
            profile.normalized_flambda,
            linewidth=1.3,
            label=rf"$\sigma_v/v_K={ratio:g}$",
        )
    axis.set(
        xlim=(-22_000.0, 22_000.0),
        xlabel=r"$v$ [km s$^{-1}$]",
        ylabel=r"normalized $F_\lambda$",
        title="Controlled uniform Gaussian broadening: double-peak merger",
    )
    axis.legend(frameon=False, ncol=2, fontsize=8)
    axis.grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(output_dir / "phase6_broadening_merger.png", dpi=180)
    plt.close(figure)
    double_ratios = [
        row["sigma_v_over_vK"] for row in rows if row["is_double_peaked"]
    ]
    return rows, (
        float(max(double_ratios)) if double_ratios else None
    )


def _plot_diagnostic_maps(output_dir, rows):
    selected = [row for row in rows if row["weight"] == "thermal_power"]
    shape = (INCLINATIONS_DEG.size, PHASES_DEG.size)
    maps = {key: np.full(shape, np.nan) for key in (
        "peak_separation_cm_s",
        "red_to_blue_peak_ratio",
        "centroid_cm_s",
        "trough_depth",
    )}
    for row in selected:
        i = int(np.flatnonzero(INCLINATIONS_DEG == row["inclination_deg"])[0])
        p = int(np.flatnonzero(PHASES_DEG == row["phase_deg"])[0])
        for key in maps:
            value = row[key]
            if value is not None:
                maps[key][i, p] = value
    figure, axes = plt.subplots(2, 2, figsize=(13.0, 8.5), constrained_layout=True)
    specs = (
        ("peak_separation_cm_s", r"$\Delta v_{\rm peak}$ [km s$^{-1}$]", 1.0e-5, "viridis"),
        ("red_to_blue_peak_ratio", r"$F_{\rm red}/F_{\rm blue}$", 1.0, "coolwarm"),
        ("centroid_cm_s", r"$v_{\rm centroid}$ [km s$^{-1}$]", 1.0e-5, "coolwarm"),
        ("trough_depth", r"$D_{\rm trough}$", 1.0, "magma"),
    )
    extent = (-7.5, 352.5, -7.5, 82.5)
    for axis, (key, title, scale, cmap) in zip(axes.flat, specs, strict=True):
        image = axis.imshow(
            maps[key] * scale,
            origin="lower",
            aspect="auto",
            extent=extent,
            cmap=cmap,
        )
        axis.set(xlabel=r"$\Phi$ [deg]", ylabel=r"$i$ [deg]", title=title)
        figure.colorbar(image, ax=axis, pad=0.01)
    figure.savefig(output_dir / "phase6_line_diagnostic_maps.png", dpi=180)
    plt.close(figure)


def _plot_dynamic_spectrum(output_dir, velocity, profiles):
    image = np.stack(
        [
            profiles[("thermal_power", 60.0, float(phase))].normalized_flambda
            for phase in PHASES_DEG
        ]
    )
    figure, axis = plt.subplots(figsize=(9.2, 5.5))
    plotted = axis.imshow(
        image,
        origin="lower",
        aspect="auto",
        extent=(
            velocity[0] / 1.0e5,
            velocity[-1] / 1.0e5,
            PHASES_DEG[0] - 7.5,
            PHASES_DEG[-1] + 7.5,
        ),
        cmap="magma",
        vmin=0.0,
        vmax=1.0,
    )
    axis.set(
        xlim=(-20_000.0, 20_000.0),
        xlabel=r"$v$ [km s$^{-1}$]",
        ylabel=r"precession phase $\Phi$ [deg]",
        title=r"One-cycle dynamic line kernel at $i=60^\circ$",
    )
    figure.colorbar(plotted, ax=axis, label=r"normalized $F_\lambda$")
    figure.tight_layout()
    figure.savefig(output_dir / "phase6_dynamic_spectrum.png", dpi=180)
    plt.close(figure)
    np.savetxt(
        output_dir / "phase6_dynamic_spectrum.csv",
        np.column_stack((velocity / 1.0e5, image.T)),
        delimiter=",",
        header="velocity_km_s," + ",".join(
            f"phase_{phase:.0f}_normalized_flambda" for phase in PHASES_DEG
        ),
        comments="",
    )


def _plot_continuum_and_line(
    output_dir,
    model,
    mesh,
    vertical_velocity,
    weights,
    velocity,
    sigma_main,
):
    line, _, observer, quadrature, shift = _profile(
        model,
        mesh,
        vertical_velocity,
        weights["thermal_power"],
        velocity,
        60.0,
        90.0,
        sigma_main,
    )
    frequency = np.geomspace(1.0e14, 1.0e17, 401)
    continuum = source_surface_blackbody_sed(
        model.source,
        mesh,
        observer,
        quadrature,
        frequency,
        frequency_shift_factor=shift.frequency_shift_factor,
    )
    figure, axes = plt.subplots(1, 2, figsize=(12.0, 4.8))
    axes[0].loglog(
        frequency,
        frequency * continuum.isotropic_equivalent_lnu_erg_s_hz,
        color="#1f4e79",
    )
    axes[0].set(
        xlabel=r"$\nu$ [Hz]",
        ylabel=r"$\nu L_{\nu,\rm iso}$ [erg s$^{-1}$]",
        title="Conditional bare-disc continuum",
    )
    axes[1].plot(velocity / 1.0e5, line.normalized_flambda, color="#d55e00")
    axes[1].set(
        xlim=(-20_000.0, 20_000.0),
        xlabel=r"$v$ [km s$^{-1}$]",
        ylabel=r"normalized $F_\lambda$",
        title="Normalized kinematic line kernel; no equivalent width",
    )
    for axis in axes:
        axis.grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(output_dir / "phase6_continuum_and_line_kernel.png", dpi=180)
    plt.close(figure)


def _convergence_audit(output_dir, velocity, sigma_ratio):
    rows = []
    profiles = {}
    for radial, anomaly in ((17, 256), (33, 512), (65, 1024)):
        model, _, mesh, vertical, weights = _model_geometry(
            0.6, radial, anomaly
        )
        speed = _characteristic_speed(model)
        profile, diagnostic, *_ = _profile(
            model,
            mesh,
            vertical,
            weights["thermal_power"],
            velocity,
            60.0,
            90.0,
            sigma_ratio * speed,
        )
        profiles[(radial, anomaly)] = (profile, diagnostic)
        row = {"audit": "source_grid", "radial_points": radial, "anomaly_points": anomaly}
        row.update(asdict(diagnostic))
        rows.append(row)
    fine = profiles[(65, 1024)][1]
    middle = profiles[(33, 512)][1]
    source_errors = {}
    for key in (
        "peak_separation_cm_s",
        "red_to_blue_peak_ratio",
        "centroid_cm_s",
    ):
        a = getattr(middle, key)
        b = getattr(fine, key)
        source_errors[key] = (
            None if a is None or b is None or b == 0.0 else abs(a / b - 1.0)
        )

    model, _, mesh, vertical, weights = _model_geometry(0.6, 33, 512)
    speed = _characteristic_speed(model)
    frequency_metrics = []
    for points in (801, 1601, 3201):
        grid = velocity_grid_cm_s(-80_000.0, 80_000.0, points)
        profile, diagnostic, *_ = _profile(
            model,
            mesh,
            vertical,
            weights["thermal_power"],
            grid,
            60.0,
            90.0,
            sigma_ratio * speed,
        )
        frequency_metrics.append((points, diagnostic))
        row = {"audit": "velocity_grid", "velocity_points": points}
        row.update(asdict(diagnostic))
        rows.append(row)
    adaptive_metrics = []
    for depth in (2, 4, 6):
        profile, diagnostic, _, quadrature, _ = _profile(
            model,
            mesh,
            vertical,
            weights["thermal_power"],
            velocity,
            75.0,
            90.0,
            sigma_ratio * speed,
            adaptive_depth=depth,
        )
        adaptive_metrics.append((depth, diagnostic, quadrature))
        row = {
            "audit": "adaptive_depth",
            "adaptive_depth": depth,
            "visible_to_unobscured": (
                quadrature.visible_projected_area_cm2
                / quadrature.unobscured_projected_area_cm2
            ),
        }
        row.update(asdict(diagnostic))
        rows.append(row)
    _write_rows(output_dir / "phase6_convergence.csv", rows)
    self_shadow = _self_shadow_boundary_audit()
    return {
        "source_grid_33x512_to_65x1024_relative_changes": source_errors,
        "velocity_grid_last_step": {
            key: (
                None
                if getattr(frequency_metrics[-2][1], key) is None
                or getattr(frequency_metrics[-1][1], key) is None
                or getattr(frequency_metrics[-1][1], key) == 0.0
                else abs(
                    getattr(frequency_metrics[-2][1], key)
                    / getattr(frequency_metrics[-1][1], key)
                    - 1.0
                )
            )
            for key in (
                "peak_separation_cm_s",
                "red_to_blue_peak_ratio",
                "centroid_cm_s",
            )
        },
        "adaptive_visible_area_range": [
            float(
                min(
                    item[2].visible_projected_area_cm2
                    / item[2].unobscured_projected_area_cm2
                    for item in adaptive_metrics
                )
            ),
            float(
                max(
                    item[2].visible_projected_area_cm2
                    / item[2].unobscured_projected_area_cm2
                    for item in adaptive_metrics
                )
            ),
        ],
        "analytic_self_shadow_boundary": self_shadow,
    }


def _self_shadow_boundary_audit() -> dict[str, object]:
    """Audit line-flux convergence across an analytic partial occultation."""
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=2, anomaly_points=4
    )
    vertices = np.array(
        [
            [-0.5, -0.5, 0.0],
            [0.5, -0.5, 0.0],
            [0.5, 0.5, 0.0],
            [-0.5, 0.5, 0.0],
            [-0.13, -0.5, 1.0],
            [0.5, -0.5, 1.0],
            [0.5, 0.5, 1.0],
            [-0.13, 0.5, 1.0],
        ]
    )
    faces = np.array([[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7]])
    mesh = build_surface_mesh_from_vertices_faces(
        vertices, faces, vertex_grid_shape=source.shape
    )
    observer = Observer(1.0, 0.0, 0.0)
    velocity = velocity_grid_cm_s(-2_000.0, 2_000.0, 401)
    shift = np.empty(source.shape)
    shift.reshape(-1)[:4] = 1.0 / (1.0 - 5.0e7 / LIGHT_SPEED_CM_S)
    shift.reshape(-1)[4:] = 1.0 / (1.0 + 5.0e7 / LIGHT_SPEED_CM_S)
    blue_g = float(shift.reshape(-1)[0])
    red_g = float(shift.reshape(-1)[-1])
    # 下层可见宽度 0.37、上层可见宽度 0.63；解析比例也必须包含 g**4。
    exact = 0.37 * blue_g**4 / (0.37 * blue_g**4 + 0.63 * red_g**4)
    errors = []
    areas = []
    for depth in (1, 3, 5, 7):
        quadrature = render_adaptive_source_surface_quadrature(
            mesh,
            observer,
            maximum_subdivision_depth=depth,
            bins_long_axis=32,
        )
        profile = observer_line_profile(
            source,
            mesh,
            quadrature,
            shift,
            geometric_uniform_line_weight(source),
            velocity,
            observer_distance_cm=observer.distance_cm,
        )
        blue = float(
            np.sum(
                profile.bin_integrated_flux_erg_s_cm2[
                    profile.velocity_cm_s < 0.0
                ]
            )
            / profile.frequency_integrated_flux_erg_s_cm2
        )
        errors.append(abs(blue - exact))
        areas.append(quadrature.visible_projected_area_cm2)
    return {
        "adaptive_depths": [1, 3, 5, 7],
        "exact_blue_energy_fraction": exact,
        "absolute_errors": errors,
        "visible_projected_area_cm2": areas,
        "final_error": errors[-1],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    velocity = velocity_grid_cm_s(-80_000.0, 80_000.0, 3201)
    ring_velocity = velocity_grid_cm_s(-12_000.0, 12_000.0, 2401)
    report = {
        "classification": (
            "conditional kinematic line response [A/V], not an NLTE Halpha luminosity"
        ),
        "rest_wavelength_angstrom": HALPHA_REST_WAVELENGTH_ANGSTROM,
        "ring_validation": _ring_figure(args.output_dir, ring_velocity),
    }

    circular = _model_geometry(0.0, 33, 512)
    circular_speed = _characteristic_speed(circular[0])
    circular_rows, circular_profiles, circular_audit = _atlas(
        circular[0],
        circular[2],
        circular[3],
        circular[4],
        velocity,
        0.02 * circular_speed,
    )
    _plot_circular_control(args.output_dir, velocity, circular_profiles)
    phase_l1 = []
    reference = circular_profiles[("uniform", 60.0, 0.0)].normalized_flambda
    for phase in PHASES_DEG:
        candidate = circular_profiles[
            ("uniform", 60.0, float(phase))
        ].normalized_flambda
        phase_l1.append(float(np.mean(np.abs(candidate - reference))))

    model, _, mesh, vertical, weights = _model_geometry(0.6, 33, 512)
    characteristic_speed = _characteristic_speed(model)
    sigma_main = 0.02 * characteristic_speed
    rows, profiles, atlas_audit = _atlas(
        model, mesh, vertical, weights, velocity, sigma_main
    )
    _write_rows(args.output_dir / "phase6_line_diagnostics.csv", rows)
    _plot_eccentric_grid(args.output_dir, velocity, profiles)
    _plot_weight_comparison(args.output_dir, velocity, profiles)
    _plot_diagnostic_maps(args.output_dir, rows)
    _plot_dynamic_spectrum(args.output_dir, velocity, profiles)
    _plot_continuum_and_line(
        args.output_dir,
        model,
        mesh,
        vertical,
        weights,
        velocity,
        sigma_main,
    )
    broadening_rows, last_double = _broadening_scan(
        args.output_dir,
        model,
        mesh,
        vertical,
        weights["thermal_power"],
        velocity,
        characteristic_speed,
    )

    thermal_sigma = hydrogen_thermal_velocity_dispersion_cm_s(
        model.source.effective_temperature_k
    )
    thermal_profile, thermal_diag, *_ = _profile(
        model,
        mesh,
        vertical,
        weights["thermal_power"],
        velocity,
        60.0,
        90.0,
        thermal_sigma,
    )
    boundary = _model_geometry(0.65, 33, 512)
    boundary_speed = _characteristic_speed(boundary[0])
    boundary_profile, boundary_diag, *_ = _profile(
        boundary[0],
        boundary[2],
        boundary[3],
        boundary[4]["thermal_power"],
        velocity,
        60.0,
        90.0,
        0.02 * boundary_speed,
    )

    threshold_sensitivity = {}
    for threshold in (0.05, 0.1, 0.2):
        count = sum(
            line_diagnostics(profile, classification_trough_threshold=threshold)
            .is_double_peaked
            for profile in profiles.values()
        )
        threshold_sensitivity[str(threshold)] = int(count)
    weight_summary = {}
    for key in WEIGHT_KEYS:
        selected = [row for row in rows if row["weight"] == key]
        weight_summary[key] = {
            "double_peak_cases": int(
                sum(bool(row["is_double_peaked"]) for row in selected)
            ),
            "total_cases": len(selected),
            "red_blue_ratio_min_max": [
                float(min(row["red_to_blue_peak_ratio"] for row in selected if row["red_to_blue_peak_ratio"] is not None)),
                float(max(row["red_to_blue_peak_ratio"] for row in selected if row["red_to_blue_peak_ratio"] is not None)),
            ],
            "centroid_km_s_min_max": [
                float(min(row["centroid_cm_s"] for row in selected) / 1.0e5),
                float(max(row["centroid_cm_s"] for row in selected) / 1.0e5),
            ],
        }
    report.update(
        {
            "formal_transfer": (
                "Fnu=D^-2 integral_visible g^3 Iem(nu/g) dA_image; "
                "frequency-integrated delta line uses g^4"
            ),
            "line_angular_law": (
                "isotropic local line intensity [A]; projected image area carries mu"
            ),
            "observer_grid": {
                "inclinations_deg": INCLINATIONS_DEG.tolist(),
                "phases_deg": PHASES_DEG.tolist(),
            },
            "main_source": {"eccentricity": 0.6, "circularization_efficiency": 0.01},
            "boundary_source": {
                "eccentricity": 0.65,
                "circularization_efficiency": 0.01,
                "diagnostics_i60_phi90": asdict(boundary_diag),
            },
            "main_sigma_v_over_vK": 0.02,
            "characteristic_vK_km_s": characteristic_speed / 1.0e5,
            "thermal_Tgas_equals_Teff_working_assumption": {
                "sigma_v_km_s_min_max": [
                    float(np.min(thermal_sigma) / 1.0e5),
                    float(np.max(thermal_sigma) / 1.0e5),
                ],
                "diagnostics_i60_phi90": asdict(thermal_diag),
                "energy_relative_residual": thermal_profile.energy_relative_residual,
            },
            "atlas_audit": atlas_audit,
            "circular_control": {
                **circular_audit,
                "maximum_phase_mean_absolute_profile_change_i60": float(
                    np.max(phase_l1)
                ),
                "newtonian_ring_is_red_blue_symmetric": True,
                "weak_field_circular_profiles_include_small_relativistic_beaming": True,
            },
            "weight_summary": weight_summary,
            "broadening": {
                "sampled_sigma_v_over_vK": [
                    row["sigma_v_over_vK"] for row in broadening_rows
                ],
                "largest_sampled_ratio_still_double": last_double,
            },
            "classification_threshold_sensitivity": threshold_sensitivity,
            "convergence": _convergence_audit(
                args.output_dir, velocity, sigma_ratio=0.02
            ),
            "unclosed_physics": [
                "NLTE level populations",
                "line self-absorption",
                "photoionization balance",
                "electron-scattering redistribution",
                "time-dependent gas temperature",
                "real instrumental line-spread function",
                "reprocessing layer or disc wind",
            ],
            "disc_wind_applied": False,
            "free_radial_emissivity_index_applied": False,
            "posthoc_renormalization_applied": False,
        }
    )
    (args.output_dir / "phase6_line_response_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "weight_summary": weight_summary,
        "broadening": report["broadening"],
        "convergence": report["convergence"],
    }, indent=2))


if __name__ == "__main__":
    main()
