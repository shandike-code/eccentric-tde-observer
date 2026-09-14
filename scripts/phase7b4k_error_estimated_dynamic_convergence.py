"""生成 Phase 7B4k 两网格误差估计深度与 2048 相位时间审计。"""

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
    PeriodicDynamicColumnSolution,
    TwoGridErrorLagrangianMassGrid,
    adaptive_lagrangian_mass_grid,
    build_periodic_dynamic_half_column,
    nested_mass_fraction_edges,
    solve_periodic_dynamic_column,
    two_grid_error_lagrangian_mass_grid,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model


RADIAL_POINTS = 65
RADIAL_INDEX = 8
ENERGY_RANGE_EV = (0.1, 5000.0)
FREQUENCY_BASE_POINTS = 65
DEPTH_PHASE_POINTS = 64
ESTIMATOR_COARSE_POINTS = 12
ESTIMATOR_REFINED_POINTS = 24
MASTER_DEPTH_POINTS = 32
NESTED_DEPTH_POINTS = (8, 16, 32)
SENSITIVITY_BASELINE_FRACTIONS = (1.0 / 3.0, 0.5, 2.0 / 3.0)
TIME_PHASE_POINTS = (512, 1024, 2048)
TIME_HALF_DEPTH_POINTS = 4
MINIMUM_TEMPERATURE_K = 5000.0
MAXIMUM_TEMPERATURE_K = 2.0e6
CYCLE_TOLERANCE = 2.0e-7
PRODUCTION_TOLERANCE = 1.0e-3


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
    weight = solution.grid.cell_mass_g_cm2 / np.sum(solution.grid.cell_mass_g_cm2)
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


def _front_locations(
    solution: PeriodicDynamicColumnSolution,
) -> tuple[list[str], list[float | None]]:
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
        step = fraction[index + 1] - fraction[index]
        if step == 0.0:
            statuses.append("flat_half_plateau")
            locations.append(None)
            continue
        location = centres[index] + (
            (0.5 - fraction[index])
            / step
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
    probe = np.linspace(lower, upper, 513)
    surface_flux_error = float(
        np.max(
            np.abs(
                solution.outward_flux_edges_erg_s_cm2[:, 0]
                - reference.outward_flux_edges_erg_s_cm2[:, 0]
            )
            / np.abs(reference.outward_flux_edges_erg_s_cm2[:, 0])
        )
    )
    pointwise_relative = 0.0
    pointwise_population = 0.0
    for phase_index in range(solution.grid.phase_points):
        for field, reference_field in (
            (solution.temperature_k, reference.temperature_k),
            (solution.rosseland_opacity_cm2_g, reference.rosseland_opacity_cm2_g),
        ):
            candidate = np.interp(probe, mass, field[phase_index])
            target = np.interp(probe, reference_mass, reference_field[phase_index])
            pointwise_relative = max(
                pointwise_relative,
                float(np.max(np.abs(candidate - target) / np.abs(target))),
            )
        for field, reference_field in (
            (solution.hydrogen_fraction[:, :, 1], reference.hydrogen_fraction[:, :, 1]),
            (solution.helium_fraction[:, :, 2], reference.helium_fraction[:, :, 2]),
        ):
            candidate = np.interp(probe, mass, field[phase_index])
            target = np.interp(probe, reference_mass, reference_field[phase_index])
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


def _monitor_rows(grid: TwoGridErrorLagrangianMassGrid) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, (left, right, monitor) in enumerate(
        zip(
            grid.coarse_mass_fraction_edges[:-1],
            grid.coarse_mass_fraction_edges[1:],
            grid.normalized_monitor_density,
            strict=True,
        )
    ):
        row: dict[str, object] = {
            "coarse_cell": index,
            "mass_fraction_left": float(left),
            "mass_fraction_right": float(right),
            "normalized_monitor_density": float(monitor),
        }
        for name, values in zip(
            grid.component_names,
            grid.normalized_error_components,
            strict=True,
        ):
            row[name] = float(values[index])
        rows.append(row)
    return rows


def _edge_rows(
    grids: dict[str, tuple[float, np.ndarray]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name, (baseline_fraction, edges) in grids.items():
        for index, edge in enumerate(edges):
            rows.append(
                {
                    "grid_name": name,
                    "baseline_monitor_fraction": baseline_fraction,
                    "half_depth_points": edges.size - 1,
                    "edge_index": index,
                    "mass_fraction_edge": float(edge),
                    "minimum_cell_mass_fraction": float(np.min(np.diff(edges))),
                    "maximum_cell_mass_fraction": float(np.max(np.diff(edges))),
                }
            )
    return rows


def _plot_depth(
    path: Path,
    monitor: TwoGridErrorLagrangianMassGrid,
    edge_sets: dict[str, tuple[float, np.ndarray]],
    rows: list[dict[str, object]],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.4), constrained_layout=True)
    centres = 0.5 * (
        monitor.coarse_mass_fraction_edges[:-1]
        + monitor.coarse_mass_fraction_edges[1:]
    )
    for name, values in zip(
        monitor.component_names,
        monitor.normalized_error_components,
        strict=True,
    ):
        axes[0, 0].semilogy(centres, values, marker="o", label=name.replace("_", " "))
    axes[0, 0].semilogy(
        centres,
        monitor.normalized_baseline_density,
        color="0.5",
        linestyle="--",
        label="analytic x-squared baseline",
    )
    axes[0, 0].semilogy(
        centres,
        monitor.normalized_monitor_density,
        color="black",
        linewidth=1.4,
        label="balanced total monitor",
    )
    axes[0, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Normalized density",
        title="(a) Nested two-grid error monitor",
    )
    axes[0, 0].legend(fontsize=7)

    shown = [
        name
        for name in edge_sets
        if name in ("nested_8", "nested_16", "nested_32", "fraction_0.667_16")
    ]
    for row_index, name in enumerate(shown):
        edges = edge_sets[name][1]
        axes[0, 1].vlines(edges, row_index - 0.35, row_index + 0.35, linewidth=0.9)
    axes[0, 1].set(
        xlabel="Mass fraction from surface",
        ylabel="Grid configuration",
        yticks=np.arange(len(shown)),
        yticklabels=shown,
        title="(b) Nested edges and baseline-fraction control",
    )

    labels = [row["case"] for row in rows if row["case"] != "nested_32_reference"]
    x = np.arange(len(labels))
    point_relative = np.array(
        [
            row["maximum_pointwise_temperature_or_opacity_relative_error"]
            for row in rows
            if row["case"] != "nested_32_reference"
        ],
        dtype=float,
    )
    point_population = np.array(
        [
            row["maximum_pointwise_population_absolute_error"]
            for row in rows
            if row["case"] != "nested_32_reference"
        ],
        dtype=float,
    )
    axes[1, 0].semilogy(x, point_relative, marker="o", label="T / opacity")
    axes[1, 0].semilogy(x, point_population, marker="s", label="H II / He III")
    axes[1, 0].axhline(PRODUCTION_TOLERANCE, color="black", linestyle=":", label="target")
    axes[1, 0].set(
        ylabel="Maximum pointwise error",
        xticks=x,
        xticklabels=labels,
        title="(c) Pointwise multi-physics error",
    )
    axes[1, 0].tick_params(axis="x", rotation=35, labelsize=7)
    axes[1, 0].legend(fontsize=8)

    mean_relative = np.array(
        [
            row["maximum_column_mean_temperature_or_opacity_relative_error"]
            for row in rows
            if row["case"] != "nested_32_reference"
        ],
        dtype=float,
    )
    mean_population = np.array(
        [
            row["maximum_column_mean_population_absolute_error"]
            for row in rows
            if row["case"] != "nested_32_reference"
        ],
        dtype=float,
    )
    axes[1, 1].semilogy(x, mean_relative, marker="o", label="T / opacity")
    axes[1, 1].semilogy(x, mean_population, marker="s", label="H II / He III")
    axes[1, 1].axhline(PRODUCTION_TOLERANCE, color="black", linestyle=":", label="target")
    axes[1, 1].set(
        ylabel="Maximum column-mean error",
        xticks=x,
        xticklabels=labels,
        title="(d) Column-integrated multi-physics error",
    )
    axes[1, 1].tick_params(axis="x", rotation=35, labelsize=7)
    axes[1, 1].legend(fontsize=8)
    figure.suptitle("Phase 7B4k: nested two-grid depth audit", fontsize=14)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_time(
    path: Path,
    cases: dict[int, PeriodicDynamicColumnSolution],
    rows: list[dict[str, object]],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.4), constrained_layout=True)
    for points, solution in cases.items():
        phase = _phase(solution)
        axes[0, 0].plot(
            phase,
            solution.outward_flux_edges_erg_s_cm2[:, 0]
            / solution.grid.one_face_target_flux_erg_s_cm2,
            label=f"N_phase={points}",
        )
        axes[0, 1].plot(
            phase,
            _column_means(solution)["he_iii"],
            label=f"N_phase={points}",
        )
    axes[0, 0].set(
        xlabel="Orbital time phase",
        ylabel="Emergent / instantaneous ZO flux",
        title="(a) Pericentre time-step structure",
    )
    axes[0, 1].set(
        xlabel="Orbital time phase",
        ylabel="Column-mean He III fraction",
        title="(b) Ionization response through 2048 phases",
    )
    axes[0, 0].legend(fontsize=8)
    axes[0, 1].legend(fontsize=8)
    active_rows = [row for row in rows if row["phase_points"] != 2048]
    points = np.array([row["phase_points"] for row in active_rows], dtype=float)
    relative = np.array(
        [row["maximum_temperature_or_flux_relative_error"] for row in active_rows],
        dtype=float,
    )
    population = np.array(
        [row["maximum_population_absolute_error"] for row in active_rows],
        dtype=float,
    )
    axes[1, 0].loglog(points, relative, marker="o")
    axes[1, 0].axhline(PRODUCTION_TOLERANCE, color="black", linestyle=":")
    axes[1, 0].set(
        xlabel="Orbital phase points",
        ylabel="Maximum relative error",
        title="(c) Temperature and flux convergence",
    )
    axes[1, 1].loglog(points, population, marker="o")
    axes[1, 1].axhline(PRODUCTION_TOLERANCE, color="black", linestyle=":")
    axes[1, 1].set(
        xlabel="Orbital phase points",
        ylabel="Maximum ion-fraction error",
        title="(d) Population convergence",
    )
    figure.suptitle("Phase 7B4k: 2048-phase orbital-time audit", fontsize=14)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_depth(output_dir: Path, frequency: np.ndarray) -> None:
    coarse, coarse_seconds = _solve(
        DEPTH_PHASE_POINTS, ESTIMATOR_COARSE_POINTS, frequency
    )
    print(f"estimator fixed {ESTIMATOR_COARSE_POINTS}: {coarse_seconds:.1f} s", flush=True)
    refined, refined_seconds = _solve(
        DEPTH_PHASE_POINTS, ESTIMATOR_REFINED_POINTS, frequency
    )
    print(f"estimator fixed {ESTIMATOR_REFINED_POINTS}: {refined_seconds:.1f} s", flush=True)

    monitors = {
        fraction: two_grid_error_lagrangian_mass_grid(
            coarse,
            refined,
            MASTER_DEPTH_POINTS,
            baseline_monitor_fraction=fraction,
        )
        for fraction in SENSITIVITY_BASELINE_FRACTIONS
    }
    main_monitor = monitors[0.5]
    cases: dict[str, PeriodicDynamicColumnSolution] = {
        "estimator_fixed_12": coarse,
        "estimator_fixed_24": refined,
    }
    runtimes = {
        "estimator_fixed_12": coarse_seconds,
        "estimator_fixed_24": refined_seconds,
    }
    edge_sets: dict[str, tuple[float, np.ndarray]] = {}
    for points in NESTED_DEPTH_POINTS:
        edges = nested_mass_fraction_edges(main_monitor, points)
        name = f"nested_{points}"
        edge_sets[name] = (0.5, edges)
        solution, elapsed = _solve(
            DEPTH_PHASE_POINTS, points, frequency, mass_fraction_edges=edges
        )
        cases[name] = solution
        runtimes[name] = elapsed
        print(f"{name}: {elapsed:.1f} s", flush=True)

    for fraction, monitor in monitors.items():
        if fraction == 0.5:
            continue
        edges = nested_mass_fraction_edges(monitor, 16)
        name = f"fraction_{fraction:.3f}_16"
        edge_sets[name] = (fraction, edges)
        solution, elapsed = _solve(
            DEPTH_PHASE_POINTS, 16, frequency, mass_fraction_edges=edges
        )
        cases[name] = solution
        runtimes[name] = elapsed
        print(f"{name}: {elapsed:.1f} s", flush=True)

    gradient_edges = adaptive_lagrangian_mass_grid(coarse, 16).mass_fraction_edges
    edge_sets["gradient_16"] = (-1.0, gradient_edges)
    gradient, elapsed = _solve(
        DEPTH_PHASE_POINTS, 16, frequency, mass_fraction_edges=gradient_edges
    )
    cases["gradient_16"] = gradient
    runtimes["gradient_16"] = elapsed
    print(f"gradient_16: {elapsed:.1f} s", flush=True)

    fixed, elapsed = _solve(DEPTH_PHASE_POINTS, 16, frequency)
    cases["fixed_16"] = fixed
    runtimes["fixed_16"] = elapsed
    edge_sets["fixed_16"] = (-2.0, fixed.grid.mass_fraction_edges)
    print(f"fixed_16: {elapsed:.1f} s", flush=True)

    reference = cases["nested_32"]
    order = (
        "estimator_fixed_12",
        "estimator_fixed_24",
        "fixed_16",
        "gradient_16",
        "fraction_0.333_16",
        "nested_8",
        "nested_16",
        "fraction_0.667_16",
        "nested_32",
    )
    rows: list[dict[str, object]] = []
    for name in order:
        rows.append(
            {
                "case": "nested_32_reference" if name == "nested_32" else name,
                "half_depth_points": cases[name].grid.half_depth_points,
                "runtime_s": runtimes[name],
                **_depth_comparison(cases[name], reference),
                "cycle_residual": cases[name].cycle_residual,
                "energy_ledger_residual": cases[
                    name
                ].relative_cycle_energy_ledger_residual,
            }
        )
    _write_csv(output_dir / "phase7b4k_two_grid_monitor.csv", _monitor_rows(main_monitor))
    _write_csv(output_dir / "phase7b4k_nested_mass_edges.csv", _edge_rows(edge_sets))
    _write_csv(output_dir / "phase7b4k_depth_convergence.csv", rows)
    _plot_depth(
        output_dir / "phase7b4k_two_grid_depth.png",
        main_monitor,
        edge_sets,
        rows,
    )
    main_16 = next(row for row in rows if row["case"] == "nested_16")
    fixed_16 = next(row for row in rows if row["case"] == "fixed_16")
    gradient_16 = next(row for row in rows if row["case"] == "gradient_16")
    depth_pass = bool(
        float(main_16["surface_flux_relative_error"]) < PRODUCTION_TOLERANCE
        and float(
            main_16["maximum_pointwise_temperature_or_opacity_relative_error"]
        )
        < PRODUCTION_TOLERANCE
        and float(main_16["maximum_pointwise_population_absolute_error"])
        < PRODUCTION_TOLERANCE
        and float(
            main_16[
                "maximum_column_mean_temperature_or_opacity_relative_error"
            ]
        )
        < PRODUCTION_TOLERANCE
        and float(main_16["maximum_column_mean_population_absolute_error"])
        < PRODUCTION_TOLERANCE
    )
    report = {
        "phase": "7B4k-depth",
        "classification": "[A/V/O] nested two-grid error-estimated depth audit",
        "configuration": {
            "depth_phase_points": DEPTH_PHASE_POINTS,
            "estimator_coarse_points": ESTIMATOR_COARSE_POINTS,
            "estimator_refined_points": ESTIMATOR_REFINED_POINTS,
            "master_depth_points": MASTER_DEPTH_POINTS,
            "nested_depth_points": NESTED_DEPTH_POINTS,
            "baseline_monitor_fraction_sensitivity": SENSITIVITY_BASELINE_FRACTIONS,
            "production_tolerance": PRODUCTION_TOLERANCE,
            "actual_frequency_points": int(frequency.size),
        },
        "monitor": {
            "component_names": main_monitor.component_names,
            "baseline_monitor_fraction": main_monitor.baseline_monitor_fraction,
            "baseline_mass_spacing_power": main_monitor.baseline_mass_spacing_power,
            "minimum_master_cell_mass_fraction": main_monitor.minimum_master_cell_mass_fraction,
            "maximum_master_cell_mass_fraction": main_monitor.maximum_master_cell_mass_fraction,
            "maximum_equidistribution_residual": main_monitor.maximum_equidistribution_residual,
        },
        "depth_convergence": rows,
        "decision": {
            "two_grid_monitor_construction_passed": bool(
                main_monitor.maximum_equidistribution_residual < 1.0e-12
            ),
            "nested_16_improves_all_reported_errors_over_fixed_16": bool(
                all(
                    float(main_16[key]) < float(fixed_16[key])
                    for key in (
                        "surface_flux_relative_error",
                        "maximum_pointwise_temperature_or_opacity_relative_error",
                        "maximum_pointwise_population_absolute_error",
                        "maximum_column_mean_temperature_or_opacity_relative_error",
                        "maximum_column_mean_population_absolute_error",
                    )
                )
            ),
            "nested_16_improves_all_reported_errors_over_gradient_16": bool(
                all(
                    float(main_16[key]) < float(gradient_16[key])
                    for key in (
                        "surface_flux_relative_error",
                        "maximum_pointwise_temperature_or_opacity_relative_error",
                        "maximum_pointwise_population_absolute_error",
                        "maximum_column_mean_temperature_or_opacity_relative_error",
                        "maximum_column_mean_population_absolute_error",
                    )
                )
            ),
            "depth_production_converged": depth_pass,
            "combined_depth_time_reference_authorized": depth_pass,
            "nonlocal_dynamic_transfer_authorized": False,
            "next_microphase": (
                "replace single-value depth cells by a conservative subcell "
                "microphysics reconstruction that resolves the moving He front "
                "without sacrificing column integrals"
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
    (output_dir / "phase7b4k_depth_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["decision"], indent=2), flush=True)


def run_time(output_dir: Path, frequency: np.ndarray) -> None:
    cases: dict[int, PeriodicDynamicColumnSolution] = {}
    runtimes: dict[int, float] = {}
    for points in TIME_PHASE_POINTS:
        solution, elapsed = _solve(points, TIME_HALF_DEPTH_POINTS, frequency)
        cases[points] = solution
        runtimes[points] = elapsed
        print(f"time phases {points}: {elapsed:.1f} s", flush=True)
    reference = cases[2048]
    rows: list[dict[str, object]] = []
    for points in TIME_PHASE_POINTS:
        rows.append(
            {
                "phase_points": points,
                "half_depth_points": TIME_HALF_DEPTH_POINTS,
                "runtime_s": runtimes[points],
                **_time_comparison(cases[points], reference),
                "cycle_residual": cases[points].cycle_residual,
                "energy_ledger_residual": cases[
                    points
                ].relative_cycle_energy_ledger_residual,
            }
        )
    _write_csv(output_dir / "phase7b4k_time_convergence.csv", rows)
    _plot_time(output_dir / "phase7b4k_time_2048.png", cases, rows)
    time_1024 = next(row for row in rows if row["phase_points"] == 1024)
    time_pass = bool(
        float(time_1024["maximum_temperature_or_flux_relative_error"])
        < PRODUCTION_TOLERANCE
        and float(time_1024["maximum_population_absolute_error"])
        < PRODUCTION_TOLERANCE
    )
    report = {
        "phase": "7B4k-time",
        "classification": "[A/V/O] 2048-phase backward-Euler time audit",
        "configuration": {
            "time_phase_points": TIME_PHASE_POINTS,
            "time_half_depth_points": TIME_HALF_DEPTH_POINTS,
            "production_tolerance": PRODUCTION_TOLERANCE,
            "actual_frequency_points": int(frequency.size),
        },
        "time_convergence": rows,
        "decision": {
            "time_1024_production_converged_against_2048": time_pass,
            "combined_depth_time_reference_authorized": False,
            "nonlocal_dynamic_transfer_authorized": False,
            "next_microphase": (
                "retain 1024 orbital phases as the validated time target while "
                "repairing the independent spatial representation"
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
    (output_dir / "phase7b4k_time_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["decision"], indent=2), flush=True)


def write_combined_report(output_dir: Path) -> None:
    depth_path = output_dir / "phase7b4k_depth_report.json"
    time_path = output_dir / "phase7b4k_time_report.json"
    if not depth_path.exists() or not time_path.exists():
        raise FileNotFoundError(
            "both Phase 7B4k depth and time reports are required for the summary"
        )
    depth = json.loads(depth_path.read_text(encoding="utf-8"))
    time_report = json.loads(time_path.read_text(encoding="utf-8"))
    depth_pass = bool(depth["decision"]["depth_production_converged"])
    time_pass = bool(
        time_report["decision"]["time_1024_production_converged_against_2048"]
    )
    combined = {
        "phase": "7B4k",
        "classification": "[A/V/O] error-estimated depth and 2048-phase audit",
        "depth_report": depth_path.name,
        "time_report": time_path.name,
        "decision": {
            "depth_production_converged": depth_pass,
            "time_1024_production_converged_against_2048": time_pass,
            "combined_depth_time_reference_authorized": depth_pass and time_pass,
            "nonlocal_dynamic_transfer_authorized": False,
            "phase4_atmosphere_replacement_authorized": False,
            "next_microphase": (
                "conservative subcell microphysics reconstruction on the validated "
                "1024-phase time grid; no further monitor-weight tuning"
            ),
        },
    }
    (output_dir / "phase7b4k_error_estimated_convergence_report.json").write_text(
        json.dumps(combined, indent=2), encoding="utf-8"
    )
    print(json.dumps(combined["decision"], indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--stage", choices=("depth", "time", "summary", "all"), default="all"
    )
    arguments = parser.parse_args()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    frequency = _frequency()
    if arguments.stage in ("depth", "all"):
        run_depth(arguments.output_dir, frequency)
    if arguments.stage in ("time", "all"):
        run_time(arguments.output_dir, frequency)
    if arguments.stage in ("summary", "all"):
        write_combined_report(arguments.output_dir)


if __name__ == "__main__":
    main()
