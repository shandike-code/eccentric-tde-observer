"""生成 Phase 7B4j 自适应拉格朗日深度与高时间分辨率审计。"""

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

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.continuum_emission import edge_resolved_milne_energy_grid_ev
from eccentric_tde_observer.dynamic_column import build_zo_periodic_column_background
from eccentric_tde_observer.hydrostatic_atmosphere import (
    build_zo_constrained_n3_column,
    solve_lte_rosseland_diffusion_column,
    symmetric_dissipation_profile,
)
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.periodic_dynamic_atmosphere import (
    AdaptiveLagrangianMassGrid,
    PeriodicDynamicColumnSolution,
    adaptive_lagrangian_mass_grid,
    build_periodic_dynamic_half_column,
    solve_periodic_dynamic_column,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model


RADIAL_POINTS = 65
RADIAL_INDEX = 8
ENERGY_RANGE_EV = (0.1, 5000.0)
FREQUENCY_BASE_POINTS = 65
DEPTH_PHASE_POINTS = 64
PILOT_DEPTH_POINTS = 12
ADAPTIVE_DEPTH_POINTS = (8, 12, 16, 24)
FIXED_DEPTH_POINTS = (8, 12, 16)
TIME_PHASE_POINTS = (128, 256, 512, 1024)
TIME_HALF_DEPTH_POINTS = 4
MINIMUM_TEMPERATURE_K = 5000.0
MAXIMUM_TEMPERATURE_K = 2.0e6
CYCLE_TOLERANCE = 2.0e-7


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _frequency() -> np.ndarray:
    energy = edge_resolved_milne_energy_grid_ev(
        ENERGY_RANGE_EV[0], ENERGY_RANGE_EV[1], FREQUENCY_BASE_POINTS
    )
    return energy * EV_ERG / PLANCK_ERG_S


def _background(phase_points: int):
    model = build_strict_domain_reference_model(RADIAL_POINTS, int(phase_points))
    return build_zo_periodic_column_background(model, RADIAL_INDEX)


def _initial_state(background, grid, frequency):
    column = build_zo_constrained_n3_column(
        float(background.one_sided_column_mass_g_cm2[0]),
        float(background.scale_height_cm[0]),
        float(background.pressure_gravity_coefficient_s2[0]),
        grid.half_depth_points,
        mass_fraction_edges=grid.mass_fraction_edges,
    )
    dissipation = symmetric_dissipation_profile(
        column,
        float(background.one_face_surface_flux_erg_s_cm2[0]),
        "uniform_specific",
    )
    static = solve_lte_rosseland_diffusion_column(
        column,
        dissipation,
        float(background.effective_temperature_k[0]),
        frequency,
        relative_tolerance=1.0e-6,
    )
    temperature = np.array(
        static.full_temperature_k[: grid.half_depth_points], copy=True
    )
    ionization = lte_hydrogen_helium_ionization(
        grid.density_g_cm3[0], temperature
    )
    hydrogen = np.column_stack(
        (
            ionization.hydrogen_neutral_fraction,
            ionization.hydrogen_ionized_fraction,
        )
    )
    helium = np.column_stack(
        (
            ionization.helium_neutral_fraction,
            ionization.helium_singly_ionized_fraction,
            ionization.helium_doubly_ionized_fraction,
        )
    )
    return temperature, hydrogen, helium


def _solve(
    phase_points: int,
    depth_points: int,
    frequency: np.ndarray,
    *,
    mass_fraction_edges: np.ndarray | None = None,
) -> tuple[PeriodicDynamicColumnSolution, float]:
    background = _background(phase_points)
    grid = build_periodic_dynamic_half_column(
        background,
        depth_points,
        "uniform_specific",
        mass_fraction_edges=mass_fraction_edges,
    )
    initial = _initial_state(background, grid, frequency)
    started = time.perf_counter()
    solution = solve_periodic_dynamic_column(
        grid,
        frequency,
        *initial,
        include_collisional_kinetics=False,
        minimum_temperature_k=MINIMUM_TEMPERATURE_K,
        maximum_temperature_k=MAXIMUM_TEMPERATURE_K,
        cycle_tolerance=CYCLE_TOLERANCE,
        local_energy_tolerance=2.0e-8,
        optimizer_tolerance=1.0e-10,
        maximum_function_evaluations=96,
        maximum_cycles=16,
    )
    return solution, time.perf_counter() - started


def _phase(solution: PeriodicDynamicColumnSolution) -> np.ndarray:
    return (
        solution.grid.background.time_since_pericentre_s
        / solution.grid.background.orbital_period_s
    )


def _mass_centres(solution: PeriodicDynamicColumnSolution) -> np.ndarray:
    return 0.5 * (
        solution.grid.mass_fraction_edges[:-1]
        + solution.grid.mass_fraction_edges[1:]
    )


def _column_means(solution: PeriodicDynamicColumnSolution) -> dict[str, np.ndarray]:
    weight = solution.grid.cell_mass_g_cm2 / np.sum(
        solution.grid.cell_mass_g_cm2
    )
    return {
        "temperature": np.sum(solution.temperature_k * weight[None, :], axis=1),
        "opacity": np.sum(
            solution.rosseland_opacity_cm2_g * weight[None, :], axis=1
        ),
        "h_ii": np.sum(
            solution.hydrogen_fraction[:, :, 1] * weight[None, :], axis=1
        ),
        "he_iii": np.sum(
            solution.helium_fraction[:, :, 2] * weight[None, :], axis=1
        ),
    }


def _front_locations(solution: PeriodicDynamicColumnSolution) -> tuple[list[str], list[float | None]]:
    centres = _mass_centres(solution)
    statuses: list[str] = []
    locations: list[float | None] = []
    for fraction in solution.helium_fraction[:, :, 2]:
        residual = fraction - 0.5
        if np.all(residual > 0.0):
            statuses.append("all_above_half")
            locations.append(None)
            continue
        if np.all(residual < 0.0):
            statuses.append("all_below_half")
            locations.append(None)
            continue
        crossing = np.flatnonzero(residual[:-1] * residual[1:] <= 0.0)
        if crossing.size != 1:
            statuses.append("non_unique_crossing")
            locations.append(None)
            continue
        index = int(crossing[0])
        fraction_step = fraction[index + 1] - fraction[index]
        if fraction_step == 0.0:
            statuses.append("flat_half_plateau")
            locations.append(None)
            continue
        location = centres[index] + (
            (0.5 - fraction[index])
            / fraction_step
            * (centres[index + 1] - centres[index])
        )
        statuses.append("unique_crossing")
        locations.append(float(location))
    return statuses, locations


def _depth_comparison(
    solution: PeriodicDynamicColumnSolution,
    reference: PeriodicDynamicColumnSolution,
) -> dict[str, object]:
    if solution.grid.phase_points != reference.grid.phase_points:
        raise ValueError("depth comparison requires a shared phase grid")
    mass = _mass_centres(solution)
    reference_mass = _mass_centres(reference)
    lower = max(float(mass[0]), float(reference_mass[0]))
    upper = min(float(mass[-1]), float(reference_mass[-1]))
    probe = np.linspace(lower, upper, 257)
    surface_flux_error = float(
        np.max(
            np.abs(
                solution.outward_flux_edges_erg_s_cm2[:, 0]
                - reference.outward_flux_edges_erg_s_cm2[:, 0]
            )
            / np.abs(reference.outward_flux_edges_erg_s_cm2[:, 0])
        )
    )
    pointwise_relative = surface_flux_error
    pointwise_population = 0.0
    for phase in range(solution.grid.phase_points):
        for field, reference_field in (
            (solution.temperature_k, reference.temperature_k),
            (solution.rosseland_opacity_cm2_g, reference.rosseland_opacity_cm2_g),
        ):
            candidate = np.interp(probe, mass, field[phase])
            target = np.interp(probe, reference_mass, reference_field[phase])
            pointwise_relative = max(
                pointwise_relative,
                float(np.max(np.abs(candidate - target) / np.abs(target))),
            )
        for field, reference_field in (
            (solution.hydrogen_fraction[:, :, 1], reference.hydrogen_fraction[:, :, 1]),
            (solution.helium_fraction[:, :, 2], reference.helium_fraction[:, :, 2]),
        ):
            candidate = np.interp(probe, mass, field[phase])
            target = np.interp(probe, reference_mass, reference_field[phase])
            pointwise_population = max(
                pointwise_population,
                float(np.max(np.abs(candidate - target))),
            )
    means = _column_means(solution)
    reference_means = _column_means(reference)
    mean_relative = max(
        float(
            np.max(
                np.abs(means[name] - reference_means[name])
                / np.abs(reference_means[name])
            )
        )
        for name in ("temperature", "opacity")
    )
    mean_population = max(
        float(np.max(np.abs(means[name] - reference_means[name])))
        for name in ("h_ii", "he_iii")
    )
    statuses, locations = _front_locations(solution)
    reference_statuses, reference_locations = _front_locations(reference)
    mismatch = sum(
        status != reference_status
        for status, reference_status in zip(
            statuses, reference_statuses, strict=True
        )
    )
    front_errors = [
        abs(float(location) - float(reference_location))
        for status, location, reference_status, reference_location in zip(
            statuses,
            locations,
            reference_statuses,
            reference_locations,
            strict=True,
        )
        if status == "unique_crossing"
        and reference_status == "unique_crossing"
        and location is not None
        and reference_location is not None
    ]
    return {
        "surface_flux_relative_error": surface_flux_error,
        "maximum_pointwise_temperature_or_opacity_relative_error": pointwise_relative,
        "maximum_pointwise_population_absolute_error": pointwise_population,
        "maximum_column_mean_temperature_or_opacity_relative_error": mean_relative,
        "maximum_column_mean_population_absolute_error": mean_population,
        "front_status_mismatch_phase_count": mismatch,
        "joint_unique_front_phase_count": len(front_errors),
        "maximum_he_iii_half_front_mass_fraction_error": (
            max(front_errors) if front_errors else None
        ),
    }


def _time_comparison(
    solution: PeriodicDynamicColumnSolution,
    reference: PeriodicDynamicColumnSolution,
) -> dict[str, float]:
    phase = _phase(solution)
    reference_phase = _phase(reference)
    maximum_relative = 0.0
    maximum_population = 0.0
    for field, reference_field in (
        (solution.temperature_k[:, 0], reference.temperature_k[:, 0]),
        (solution.temperature_k[:, -1], reference.temperature_k[:, -1]),
        (
            solution.outward_flux_edges_erg_s_cm2[:, 0],
            reference.outward_flux_edges_erg_s_cm2[:, 0],
        ),
    ):
        candidate = np.interp(reference_phase, phase, field, period=1.0)
        maximum_relative = max(
            maximum_relative,
            float(np.max(np.abs(candidate - reference_field) / np.abs(reference_field))),
        )
    for field, reference_field in (
        (solution.hydrogen_fraction[:, 0, 1], reference.hydrogen_fraction[:, 0, 1]),
        (solution.helium_fraction[:, 0, 2], reference.helium_fraction[:, 0, 2]),
    ):
        candidate = np.interp(reference_phase, phase, field, period=1.0)
        maximum_population = max(
            maximum_population,
            float(np.max(np.abs(candidate - reference_field))),
        )
    return {
        "maximum_temperature_or_flux_relative_error": maximum_relative,
        "maximum_population_absolute_error": maximum_population,
    }


def _mesh_rows(meshes: dict[int, AdaptiveLagrangianMassGrid]) -> list[dict[str, object]]:
    rows = []
    for points, mesh in meshes.items():
        for edge_index, edge in enumerate(mesh.mass_fraction_edges):
            rows.append(
                {
                    "half_depth_points": points,
                    "edge_index": edge_index,
                    "mass_fraction_edge": float(edge),
                    "minimum_cell_mass_fraction": mesh.minimum_cell_mass_fraction,
                    "maximum_cell_mass_fraction": mesh.maximum_cell_mass_fraction,
                    "maximum_equidistribution_residual": mesh.maximum_equidistribution_residual,
                }
            )
    return rows


def _monitor_rows(mesh: AdaptiveLagrangianMassGrid) -> list[dict[str, object]]:
    return [
        {
            "mass_fraction": float(mass),
            "normalized_total_monitor": float(total),
            "normalized_log_temperature_gradient": float(temperature),
            "normalized_log_opacity_gradient": float(opacity),
            "normalized_he_iii_gradient": float(helium),
        }
        for mass, total, temperature, opacity, helium in zip(
            mesh.sampled_mass_fraction,
            mesh.normalized_monitor,
            mesh.log_temperature_component,
            mesh.log_opacity_component,
            mesh.helium_iii_component,
            strict=True,
        )
    ]


def _plot_depth(
    path: Path,
    monitor: AdaptiveLagrangianMassGrid,
    meshes: dict[int, AdaptiveLagrangianMassGrid],
    rows: list[dict[str, object]],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.4), constrained_layout=True)
    axes[0, 0].semilogy(
        monitor.sampled_mass_fraction,
        monitor.log_temperature_component,
        label="log-temperature gradient",
    )
    axes[0, 0].semilogy(
        monitor.sampled_mass_fraction,
        monitor.log_opacity_component,
        label="log-opacity gradient",
    )
    axes[0, 0].semilogy(
        monitor.sampled_mass_fraction,
        monitor.helium_iii_component,
        label="He III gradient",
    )
    axes[0, 0].semilogy(
        monitor.sampled_mass_fraction,
        monitor.normalized_monitor,
        color="black",
        linewidth=1.2,
        label="total monitor",
    )
    axes[0, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Normalized monitor density",
        title="(a) Orbit-wide refinement monitor",
    )
    axes[0, 0].legend(fontsize=8)

    for row_index, (points, mesh) in enumerate(meshes.items()):
        axes[0, 1].vlines(
            mesh.mass_fraction_edges,
            row_index - 0.35,
            row_index + 0.35,
            linewidth=0.9,
            label=f"adaptive N={points}",
        )
    axes[0, 1].set(
        xlabel="Mass fraction from surface",
        ylabel="Adaptive grid",
        yticks=np.arange(len(meshes)),
        yticklabels=[str(points) for points in meshes],
        title="(b) Shared Lagrangian cell edges",
    )

    for grid_type, linestyle in (("fixed", "--"), ("adaptive", "-")):
        selected = [row for row in rows if row["grid_type"] == grid_type]
        points = np.array(
            [row["half_depth_points"] for row in selected], dtype=float
        )
        mean_error = np.array(
            [
                row["maximum_column_mean_temperature_or_opacity_relative_error"]
                for row in selected
            ],
            dtype=float,
        )
        point_error = np.array(
            [
                row["maximum_pointwise_temperature_or_opacity_relative_error"]
                for row in selected
            ],
            dtype=float,
        )
        active = mean_error > 0.0
        axes[1, 0].loglog(
            points[active],
            mean_error[active],
            marker="o",
            linestyle=linestyle,
            label=f"{grid_type}: column mean",
        )
        active = point_error > 0.0
        axes[1, 0].loglog(
            points[active],
            point_error[active],
            marker="s",
            linestyle=linestyle,
            label=f"{grid_type}: pointwise",
        )
    axes[1, 0].set(
        xlabel="Half-column cells",
        ylabel="Maximum relative error",
        title="(c) Temperature, opacity and flux",
    )
    axes[1, 0].legend(fontsize=8)

    for grid_type, linestyle in (("fixed", "--"), ("adaptive", "-")):
        selected = [row for row in rows if row["grid_type"] == grid_type]
        points = np.array(
            [row["half_depth_points"] for row in selected], dtype=float
        )
        mean_error = np.array(
            [row["maximum_column_mean_population_absolute_error"] for row in selected],
            dtype=float,
        )
        point_error = np.array(
            [row["maximum_pointwise_population_absolute_error"] for row in selected],
            dtype=float,
        )
        active = mean_error > 0.0
        axes[1, 1].loglog(
            points[active],
            mean_error[active],
            marker="o",
            linestyle=linestyle,
            label=f"{grid_type}: column mean",
        )
        active = point_error > 0.0
        axes[1, 1].loglog(
            points[active],
            point_error[active],
            marker="s",
            linestyle=linestyle,
            label=f"{grid_type}: pointwise",
        )
    axes[1, 1].set(
        xlabel="Half-column cells",
        ylabel="Maximum ion-fraction error",
        title="(d) H II and He III convergence",
    )
    axes[1, 1].legend(fontsize=8)
    figure.suptitle("Phase 7B4j: adaptive Lagrangian depth audit", fontsize=14)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_time(
    path: Path,
    cases: dict[int, PeriodicDynamicColumnSolution],
    rows: list[dict[str, object]],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.4), constrained_layout=True)
    for points, solution in cases.items():
        if points not in (128, 512, 1024):
            continue
        phase = _phase(solution)
        axes[0, 0].plot(
            phase,
            solution.outward_flux_edges_erg_s_cm2[:, 0]
            / solution.grid.one_face_target_flux_erg_s_cm2,
            label=f"N_phase={points}",
        )
        means = _column_means(solution)
        axes[0, 1].plot(
            phase, means["he_iii"], label=f"N_phase={points}"
        )
    axes[0, 0].set(
        xlabel="Orbital time phase",
        ylabel="Emergent / instantaneous ZO flux",
        title="(a) Pericentre time-step structure",
    )
    axes[0, 0].legend(fontsize=8)
    axes[0, 1].set(
        xlabel="Orbital time phase",
        ylabel="Column-mean He III fraction",
        title="(b) Time-resolved ionization response",
    )
    axes[0, 1].legend(fontsize=8)

    points = np.array([row["phase_points"] for row in rows], dtype=float)
    relative = np.array(
        [row["maximum_temperature_or_flux_relative_error"] for row in rows],
        dtype=float,
    )
    population = np.array(
        [row["maximum_population_absolute_error"] for row in rows],
        dtype=float,
    )
    active = relative > 0.0
    axes[1, 0].loglog(points[active], relative[active], marker="o")
    axes[1, 0].set(
        xlabel="Orbital phase points",
        ylabel="Maximum relative error",
        title="(c) Temperature and flux convergence",
    )
    active = population > 0.0
    axes[1, 1].loglog(points[active], population[active], marker="o")
    axes[1, 1].set(
        xlabel="Orbital phase points",
        ylabel="Maximum ion-fraction error",
        title="(d) Population convergence",
    )
    figure.suptitle("Phase 7B4j: high-resolution orbital-time audit", fontsize=14)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    arguments = parser.parse_args()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    frequency = _frequency()

    pilot, pilot_seconds = _solve(
        DEPTH_PHASE_POINTS, PILOT_DEPTH_POINTS, frequency
    )
    print(f"pilot depth solve: {pilot_seconds:.1f} s", flush=True)
    meshes = {
        points: adaptive_lagrangian_mass_grid(pilot, points)
        for points in ADAPTIVE_DEPTH_POINTS
    }
    adaptive_cases: dict[int, PeriodicDynamicColumnSolution] = {}
    adaptive_runtime: dict[int, float] = {}
    for points, mesh in meshes.items():
        solution, elapsed = _solve(
            DEPTH_PHASE_POINTS,
            points,
            frequency,
            mass_fraction_edges=mesh.mass_fraction_edges,
        )
        adaptive_cases[points] = solution
        adaptive_runtime[points] = elapsed
        print(f"adaptive depth {points}: {elapsed:.1f} s", flush=True)
    fixed_cases: dict[int, PeriodicDynamicColumnSolution] = {
        PILOT_DEPTH_POINTS: pilot
    }
    fixed_runtime: dict[int, float] = {PILOT_DEPTH_POINTS: pilot_seconds}
    for points in FIXED_DEPTH_POINTS:
        if points == PILOT_DEPTH_POINTS:
            continue
        solution, elapsed = _solve(DEPTH_PHASE_POINTS, points, frequency)
        fixed_cases[points] = solution
        fixed_runtime[points] = elapsed
        print(f"fixed depth {points}: {elapsed:.1f} s", flush=True)

    depth_reference = adaptive_cases[ADAPTIVE_DEPTH_POINTS[-1]]
    depth_rows: list[dict[str, object]] = []
    for grid_type, cases, runtimes in (
        ("fixed", fixed_cases, fixed_runtime),
        ("adaptive", adaptive_cases, adaptive_runtime),
    ):
        for points in sorted(cases):
            comparison = _depth_comparison(cases[points], depth_reference)
            depth_rows.append(
                {
                    "grid_type": grid_type,
                    "half_depth_points": points,
                    "runtime_s": runtimes[points],
                    **comparison,
                    "cycle_residual": cases[points].cycle_residual,
                    "energy_ledger_residual": cases[
                        points
                    ].relative_cycle_energy_ledger_residual,
                }
            )

    time_cases: dict[int, PeriodicDynamicColumnSolution] = {}
    time_runtime: dict[int, float] = {}
    for points in TIME_PHASE_POINTS:
        solution, elapsed = _solve(
            points, TIME_HALF_DEPTH_POINTS, frequency
        )
        time_cases[points] = solution
        time_runtime[points] = elapsed
        print(f"time phases {points}: {elapsed:.1f} s", flush=True)
    time_reference = time_cases[TIME_PHASE_POINTS[-1]]
    time_rows: list[dict[str, object]] = []
    for points in TIME_PHASE_POINTS:
        comparison = _time_comparison(time_cases[points], time_reference)
        time_rows.append(
            {
                "phase_points": points,
                "half_depth_points": TIME_HALF_DEPTH_POINTS,
                "runtime_s": time_runtime[points],
                **comparison,
                "cycle_residual": time_cases[points].cycle_residual,
                "energy_ledger_residual": time_cases[
                    points
                ].relative_cycle_energy_ledger_residual,
            }
        )

    _write_csv(
        arguments.output_dir / "phase7b4j_adaptive_mass_edges.csv",
        _mesh_rows(meshes),
    )
    _write_csv(
        arguments.output_dir / "phase7b4j_adaptive_monitor.csv",
        _monitor_rows(meshes[ADAPTIVE_DEPTH_POINTS[-1]]),
    )
    _write_csv(
        arguments.output_dir / "phase7b4j_depth_convergence.csv", depth_rows
    )
    _write_csv(
        arguments.output_dir / "phase7b4j_time_convergence.csv", time_rows
    )
    _plot_depth(
        arguments.output_dir / "phase7b4j_adaptive_depth.png",
        meshes[ADAPTIVE_DEPTH_POINTS[-1]],
        meshes,
        depth_rows,
    )
    _plot_time(
        arguments.output_dir / "phase7b4j_time_convergence.png",
        time_cases,
        time_rows,
    )

    adaptive_16 = next(
        row
        for row in depth_rows
        if row["grid_type"] == "adaptive" and row["half_depth_points"] == 16
    )
    fixed_16 = next(
        row
        for row in depth_rows
        if row["grid_type"] == "fixed" and row["half_depth_points"] == 16
    )
    time_512 = next(
        row for row in time_rows if row["phase_points"] == 512
    )
    common_depth_points = sorted(set(adaptive_cases) & set(fixed_cases))
    adaptive_improves_both_pointwise_metrics = all(
        float(
            next(
                row
                for row in depth_rows
                if row["grid_type"] == "adaptive"
                and row["half_depth_points"] == points
            )["maximum_pointwise_temperature_or_opacity_relative_error"]
        )
        < float(
            next(
                row
                for row in depth_rows
                if row["grid_type"] == "fixed"
                and row["half_depth_points"] == points
            )["maximum_pointwise_temperature_or_opacity_relative_error"]
        )
        and float(
            next(
                row
                for row in depth_rows
                if row["grid_type"] == "adaptive"
                and row["half_depth_points"] == points
            )["maximum_pointwise_population_absolute_error"]
        )
        < float(
            next(
                row
                for row in depth_rows
                if row["grid_type"] == "fixed"
                and row["half_depth_points"] == points
            )["maximum_pointwise_population_absolute_error"]
        )
        for points in common_depth_points
    )
    report = {
        "phase": "7B4j",
        "classification": "[A/V/O] adaptive Lagrangian depth and high-resolution time audit",
        "configuration": {
            "radial_index": RADIAL_INDEX,
            "depth_phase_points": DEPTH_PHASE_POINTS,
            "pilot_depth_points": PILOT_DEPTH_POINTS,
            "adaptive_depth_points": ADAPTIVE_DEPTH_POINTS,
            "fixed_depth_points": FIXED_DEPTH_POINTS,
            "time_phase_points": TIME_PHASE_POINTS,
            "time_half_depth_points": TIME_HALF_DEPTH_POINTS,
            "frequency_base_points": FREQUENCY_BASE_POINTS,
            "actual_frequency_points": int(frequency.size),
            "monitor": (
                "unit baseline plus separately unit-integral orbit-maximum gradients "
                "of log temperature, log Rosseland opacity and He III fraction"
            ),
            "shared_mesh_for_all_orbital_phases": True,
        },
        "mesh_controls": {
            "adaptive_24_minimum_cell_mass_fraction": meshes[
                24
            ].minimum_cell_mass_fraction,
            "adaptive_24_maximum_cell_mass_fraction": meshes[
                24
            ].maximum_cell_mass_fraction,
            "adaptive_24_equidistribution_residual": meshes[
                24
            ].maximum_equidistribution_residual,
        },
        "depth_convergence": depth_rows,
        "time_convergence": time_rows,
        "comparison_at_16_cells": {
            "adaptive": adaptive_16,
            "fixed": fixed_16,
            "adaptive_pointwise_population_error_over_fixed": (
                float(adaptive_16["maximum_pointwise_population_absolute_error"])
                / float(fixed_16["maximum_pointwise_population_absolute_error"])
            ),
        },
        "decision": {
            "adaptive_mesh_construction_passed": bool(
                meshes[24].maximum_equidistribution_residual < 1.0e-5
            ),
            "adaptive_mesh_improves_both_pointwise_metrics_at_every_common_resolution": bool(
                adaptive_improves_both_pointwise_metrics
            ),
            "adaptive_mesh_improves_both_column_mean_metrics_at_every_common_resolution": bool(
                all(
                    float(
                        next(
                            row
                            for row in depth_rows
                            if row["grid_type"] == "adaptive"
                            and row["half_depth_points"] == points
                        )[
                            "maximum_column_mean_temperature_or_opacity_relative_error"
                        ]
                    )
                    < float(
                        next(
                            row
                            for row in depth_rows
                            if row["grid_type"] == "fixed"
                            and row["half_depth_points"] == points
                        )[
                            "maximum_column_mean_temperature_or_opacity_relative_error"
                        ]
                    )
                    and float(
                        next(
                            row
                            for row in depth_rows
                            if row["grid_type"] == "adaptive"
                            and row["half_depth_points"] == points
                        )["maximum_column_mean_population_absolute_error"]
                    )
                    < float(
                        next(
                            row
                            for row in depth_rows
                            if row["grid_type"] == "fixed"
                            and row["half_depth_points"] == points
                        )["maximum_column_mean_population_absolute_error"]
                    )
                    for points in common_depth_points
                )
            ),
            "depth_production_converged": bool(
                float(adaptive_16["maximum_pointwise_population_absolute_error"])
                < 1.0e-3
                and float(
                    adaptive_16[
                        "maximum_pointwise_temperature_or_opacity_relative_error"
                    ]
                )
                < 1.0e-3
            ),
            "time_512_production_converged_against_1024": bool(
                float(time_512["maximum_temperature_or_flux_relative_error"])
                < 1.0e-3
                and float(time_512["maximum_population_absolute_error"])
                < 1.0e-3
            ),
            "phase4_atmosphere_replacement_authorized": False,
            "nonlocal_dynamic_transfer_authorized": False,
            "next_microphase": (
                "replace the single global gradient monitor by an error-estimating "
                "front-aware refinement and establish a combined depth-time reference"
            ),
        },
        "forbidden_repairs": {
            "nan_to_num": False,
            "arbitrary_clip": False,
            "arbitrary_floor": False,
            "failed_phase_deletion": False,
            "post_hoc_physical_renormalization": False,
        },
    }
    (arguments.output_dir / "phase7b4j_adaptive_convergence_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["decision"], indent=2), flush=True)


if __name__ == "__main__":
    main()
