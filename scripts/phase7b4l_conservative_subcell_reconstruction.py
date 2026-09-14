"""生成 Phase 7B4l 保守子单元控制、空间收敛与路线判据。"""

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
    PeriodicDynamicHalfColumn,
    build_periodic_dynamic_half_column,
    ground_state_thermodynamics,
    solve_periodic_dynamic_column,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model
from eccentric_tde_observer.subcell_reconstruction import (
    ConservativeGroundStateSubcells,
    ConservativeSubcellRestriction,
    conservative_ground_state_subcells,
    conservative_linear_subcell_values,
    ground_state_temperature_from_specific_energy_k,
    restrict_periodic_dynamic_subcells,
)


RADIAL_POINTS = 65
RADIAL_INDEX = 8
DEPTH_PHASE_POINTS = 64
MASTER_DEPTH_POINTS = 64
PARENT_DEPTH_POINTS = (8, 16, 32)
SUBCELLS_PER_PARENT = 2
EFFECTIVE_DEPTH_POINTS = tuple(
    SUBCELLS_PER_PARENT * points for points in PARENT_DEPTH_POINTS
)
ENERGY_RANGE_EV = (0.1, 5000.0)
FREQUENCY_BASE_POINTS = 65
MINIMUM_TEMPERATURE_K = 5000.0
MAXIMUM_TEMPERATURE_K = 2.0e6
CYCLE_TOLERANCE = 2.0e-7
PRODUCTION_TOLERANCE = 1.0e-3
CONSERVATION_TOLERANCE = 2.0e-12


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


def _master_edges_from_monitor(path: Path) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(
            "Phase 7B4k monitor CSV is required before Phase 7B4l"
        )
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("Phase 7B4k monitor table is empty")
    left = np.array([float(row["mass_fraction_left"]) for row in rows])
    right = np.array([float(row["mass_fraction_right"]) for row in rows])
    monitor = np.array([float(row["normalized_monitor_density"]) for row in rows])
    if (
        left[0] != 0.0
        or right[-1] != 1.0
        or not np.array_equal(left[1:], right[:-1])
        or np.any(monitor <= 0.0)
    ):
        raise ValueError("Phase 7B4k monitor table is not a contiguous physical grid")
    coarse_edges = np.concatenate((left[:1], right))
    cumulative = np.concatenate(
        (np.array([0.0]), np.cumsum(monitor * np.diff(coarse_edges)))
    )
    if not np.isclose(cumulative[-1], 1.0, rtol=8.0e-15, atol=0.0):
        raise ValueError("Phase 7B4k monitor no longer integrates to one")
    cumulative[-1] = 1.0
    quantile = np.arange(MASTER_DEPTH_POINTS + 1) / MASTER_DEPTH_POINTS
    edges = np.interp(quantile, cumulative, coarse_edges)
    edges[0] = 0.0
    edges[-1] = 1.0
    if np.any(np.diff(edges) <= 0.0):
        raise ArithmeticError("Phase 7B4l master edges became non-increasing")
    return edges


def _nested_edges(master: np.ndarray, points: int) -> np.ndarray:
    master_points = master.size - 1
    if master_points % points != 0:
        raise ValueError("requested grid must divide the Phase 7B4l master grid")
    edges = np.array(master[:: master_points // points], copy=True)
    if edges.size != points + 1 or edges[-1] != 1.0:
        raise ArithmeticError("nested Phase 7B4l grid lost an endpoint")
    return edges


def _initial_state(
    background,
    grid: PeriodicDynamicHalfColumn,
    frequency: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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


def _solve_subcell_case(
    background,
    frequency: np.ndarray,
    master_edges: np.ndarray,
    parent_points: int,
) -> tuple[
    PeriodicDynamicHalfColumn,
    ConservativeGroundStateSubcells,
    PeriodicDynamicColumnSolution,
    ConservativeSubcellRestriction,
    float,
]:
    effective_points = parent_points * SUBCELLS_PER_PARENT
    parent_edges = _nested_edges(master_edges, parent_points)
    subcell_edges = _nested_edges(master_edges, effective_points)
    parent_grid = build_periodic_dynamic_half_column(
        background,
        parent_points,
        "uniform_specific",
        mass_fraction_edges=parent_edges,
    )
    subcell_grid = build_periodic_dynamic_half_column(
        background,
        effective_points,
        "uniform_specific",
        mass_fraction_edges=subcell_edges,
    )
    parent_initial = _initial_state(background, parent_grid, frequency)
    subcell_initial = conservative_ground_state_subcells(
        parent_grid,
        subcell_grid,
        *parent_initial,
        SUBCELLS_PER_PARENT,
    )
    started = time.perf_counter()
    solution = solve_periodic_dynamic_column(
        subcell_grid,
        frequency,
        subcell_initial.temperature_k,
        subcell_initial.hydrogen_fraction,
        subcell_initial.helium_fraction,
        include_collisional_kinetics=False,
        minimum_temperature_k=MINIMUM_TEMPERATURE_K,
        maximum_temperature_k=MAXIMUM_TEMPERATURE_K,
        cycle_tolerance=CYCLE_TOLERANCE,
        local_energy_tolerance=2.0e-8,
        optimizer_tolerance=1.0e-10,
        maximum_function_evaluations=96,
        maximum_cycles=16,
    )
    elapsed = time.perf_counter() - started
    restriction = restrict_periodic_dynamic_subcells(
        parent_grid, solution, SUBCELLS_PER_PARENT
    )
    return parent_grid, subcell_initial, solution, restriction, elapsed


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
    mass = _mass_centres(solution)
    reference_mass = _mass_centres(reference)
    lower = max(float(mass[0]), float(reference_mass[0]))
    upper = min(float(mass[-1]), float(reference_mass[-1]))
    probe = np.linspace(lower, upper, 1025)
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
            (
                solution.hydrogen_fraction[:, :, 1],
                reference.hydrogen_fraction[:, :, 1],
            ),
            (
                solution.helium_fraction[:, :, 2],
                reference.helium_fraction[:, :, 2],
            ),
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


def _conservation_metrics(
    initial: ConservativeGroundStateSubcells,
    restriction: ConservativeSubcellRestriction,
) -> dict[str, float]:
    return {
        "minimum_initial_limiter_fraction": float(np.min(initial.limiter_fraction)),
        "initial_mass_residual": initial.maximum_parent_mass_residual,
        "initial_hydrogen_particle_residual": (
            initial.maximum_hydrogen_particle_residual
        ),
        "initial_helium_particle_residual": initial.maximum_helium_particle_residual,
        "initial_hydrogen_stage_absolute_residual": (
            initial.maximum_hydrogen_stage_absolute_residual
        ),
        "initial_helium_stage_absolute_residual": (
            initial.maximum_helium_stage_absolute_residual
        ),
        "initial_charge_residual": initial.maximum_charge_residual,
        "initial_energy_residual": initial.maximum_specific_energy_residual,
        "restricted_mass_residual": restriction.maximum_parent_mass_residual,
        "restricted_hydrogen_particle_residual_upper_bound": (
            restriction.maximum_hydrogen_particle_residual
        ),
        "restricted_helium_particle_residual_upper_bound": (
            restriction.maximum_helium_particle_residual
        ),
        "restricted_hydrogen_stage_absolute_residual_upper_bound": (
            restriction.maximum_hydrogen_stage_absolute_residual
        ),
        "restricted_helium_stage_absolute_residual_upper_bound": (
            restriction.maximum_helium_stage_absolute_residual
        ),
        "restricted_charge_residual": restriction.maximum_charge_residual,
        "restricted_energy_residual": restriction.maximum_specific_energy_residual,
        "restricted_optical_depth_residual": restriction.maximum_optical_depth_residual,
        "restricted_flux_divergence_residual": (
            restriction.maximum_face_flux_divergence_residual
        ),
    }


CONSERVATION_ROW_KEYS = (
    "initial_mass_residual",
    "initial_hydrogen_particle_residual",
    "initial_helium_particle_residual",
    "initial_hydrogen_stage_absolute_residual",
    "initial_helium_stage_absolute_residual",
    "initial_charge_residual",
    "initial_energy_residual",
    "restricted_mass_residual",
    "restricted_hydrogen_particle_residual_upper_bound",
    "restricted_helium_particle_residual_upper_bound",
    "restricted_hydrogen_stage_absolute_residual_upper_bound",
    "restricted_helium_stage_absolute_residual_upper_bound",
    "restricted_charge_residual",
    "restricted_energy_residual",
    "restricted_optical_depth_residual",
    "restricted_flux_divergence_residual",
)


def _conservation_pass(rows: list[dict[str, object]]) -> bool:
    return bool(
        all(
            float(row[key]) < CONSERVATION_TOLERANCE
            for row in rows
            for key in CONSERVATION_ROW_KEYS
        )
    )


def run_controls(output_dir: Path) -> None:
    edges = np.linspace(0.0, 1.0, 9)
    rows: list[dict[str, object]] = []
    selected = None
    for front in np.linspace(0.15, 0.85, 16):
        width = 0.08

        def antiderivative(x):
            return 0.5 * (
                x - width * np.log(np.cosh((x - front) / width))
            )

        parent_average = (
            antiderivative(edges[1:]) - antiderivative(edges[:-1])
        ) / np.diff(edges)
        reconstructed = conservative_linear_subcell_values(
            parent_average,
            edges,
            4,
            lower_bound=0.0,
            upper_bound=1.0,
        )
        exact = 0.5 * (
            1.0
            - np.tanh(
                (reconstructed.subcell_mass_fraction_centres - front) / width
            )
        )
        constant = np.repeat(parent_average, 4)
        for x, exact_value, constant_value, reconstructed_value in zip(
            reconstructed.subcell_mass_fraction_centres,
            exact,
            constant,
            reconstructed.values,
            strict=True,
        ):
            rows.append(
                {
                    "front_mass_fraction": float(front),
                    "subcell_mass_fraction": float(x),
                    "exact_he_iii_fraction": float(exact_value),
                    "piecewise_constant_he_iii_fraction": float(constant_value),
                    "reconstructed_he_iii_fraction": float(reconstructed_value),
                    "parent_average_residual": (
                        reconstructed.maximum_parent_average_residual
                    ),
                }
            )
        if selected is None or abs(front - 0.5) < abs(selected[0] - 0.5):
            selected = (front, reconstructed, exact, constant)
    _write_csv(output_dir / "phase7b4l_manufactured_front.csv", rows)

    exact_values = np.array([row["exact_he_iii_fraction"] for row in rows])
    constant_values = np.array(
        [row["piecewise_constant_he_iii_fraction"] for row in rows]
    )
    reconstructed_values = np.array(
        [row["reconstructed_he_iii_fraction"] for row in rows]
    )
    constant_l1 = float(np.mean(np.abs(constant_values - exact_values)))
    reconstructed_l1 = float(
        np.mean(np.abs(reconstructed_values - exact_values))
    )
    constant_linf = float(np.max(np.abs(constant_values - exact_values)))
    reconstructed_linf = float(
        np.max(np.abs(reconstructed_values - exact_values))
    )

    density = np.array([1.0e-10, 5.0e-9, 2.0e-7])
    temperature = np.array([1.2e4, 4.0e4, 1.1e5])
    hydrogen = np.array([[0.9, 0.1], [0.3, 0.7], [0.01, 0.99]])
    helium = np.array(
        [[0.85, 0.1, 0.05], [0.2, 0.5, 0.3], [0.01, 0.09, 0.9]]
    )
    energy = ground_state_thermodynamics(
        density, temperature, hydrogen, helium
    ).specific_total_energy_erg_g
    recovered_temperature = ground_state_temperature_from_specific_energy_k(
        density, energy, hydrogen, helium
    )
    temperature_error = float(
        np.max(np.abs(recovered_temperature - temperature) / temperature)
    )

    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.4), constrained_layout=True)
    if selected is None:
        raise ArithmeticError("manufactured front control produced no selected phase")
    front, reconstructed, exact, constant = selected
    x = reconstructed.subcell_mass_fraction_centres
    axes[0, 0].plot(x, exact, color="black", label="Exact front")
    axes[0, 0].step(
        x,
        constant,
        where="mid",
        color="#d62728",
        label="Parent constant",
    )
    axes[0, 0].plot(
        x,
        reconstructed.values,
        marker="o",
        color="#1f77b4",
        label="Limited subcells",
    )
    axes[0, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="He III fraction",
        title=f"(a) Manufactured front at x={front:.3f}",
    )
    axes[0, 0].legend(fontsize=8)

    front_values = sorted({float(row["front_mass_fraction"]) for row in rows})
    constant_by_front = []
    reconstructed_by_front = []
    for value in front_values:
        subset = [row for row in rows if row["front_mass_fraction"] == value]
        exact_subset = np.array([row["exact_he_iii_fraction"] for row in subset])
        constant_subset = np.array(
            [row["piecewise_constant_he_iii_fraction"] for row in subset]
        )
        reconstructed_subset = np.array(
            [row["reconstructed_he_iii_fraction"] for row in subset]
        )
        constant_by_front.append(float(np.mean(np.abs(constant_subset - exact_subset))))
        reconstructed_by_front.append(
            float(np.mean(np.abs(reconstructed_subset - exact_subset)))
        )
    axes[0, 1].plot(front_values, constant_by_front, marker="s", label="Parent constant")
    axes[0, 1].plot(
        front_values,
        reconstructed_by_front,
        marker="o",
        label="Limited subcells",
    )
    axes[0, 1].set(
        xlabel="Front mass fraction",
        ylabel="Mean absolute error",
        title="(b) Moving-front error through one sweep",
    )
    axes[0, 1].legend(fontsize=8)

    axes[1, 0].plot(
        0.5 * (edges[:-1] + edges[1:]),
        reconstructed.limiter_fraction,
        marker="o",
    )
    axes[1, 0].set(
        xlabel="Parent-cell mass fraction",
        ylabel="Limiter fraction",
        ylim=(-0.03, 1.03),
        title="(c) Convex physical-domain limiter",
    )
    labels = ["Parent average", "Energy inversion"]
    values = [
        max(float(row["parent_average_residual"]) for row in rows),
        temperature_error,
    ]
    axes[1, 1].bar(labels, values, color=["#1f77b4", "#ff7f0e"])
    axes[1, 1].set_yscale("log")
    axes[1, 1].set(
        ylabel="Maximum relative residual",
        title="(d) Analytic conservation controls",
    )
    figure.suptitle("Phase 7B4l: conservative subcell controls", fontsize=14)
    figure.savefig(output_dir / "phase7b4l_subcell_controls.png", dpi=180)
    plt.close(figure)

    report = {
        "phase": "7B4l-control",
        "classification": "[A/V] conservative subcell analytic controls",
        "configuration": {
            "manufactured_parent_cells": 8,
            "manufactured_subcells_per_parent": 4,
            "front_width_mass_fraction": 0.08,
            "front_positions": front_values,
        },
        "manufactured_front": {
            "piecewise_constant_mean_absolute_error": constant_l1,
            "reconstructed_mean_absolute_error": reconstructed_l1,
            "piecewise_constant_maximum_absolute_error": constant_linf,
            "reconstructed_maximum_absolute_error": reconstructed_linf,
            "mean_error_improvement_factor": constant_l1 / reconstructed_l1,
            "maximum_error_improvement_factor": constant_linf / reconstructed_linf,
        },
        "energy_inversion": {
            "maximum_temperature_relative_error": temperature_error
        },
        "decision": {
            "manufactured_front_improved": bool(
                reconstructed_l1 < constant_l1
                and reconstructed_linf < constant_linf
            ),
            "parent_average_conservation_passed": bool(
                max(float(row["parent_average_residual"]) for row in rows)
                < CONSERVATION_TOLERANCE
            ),
            "energy_inversion_passed": temperature_error < CONSERVATION_TOLERANCE,
        },
        "forbidden_repairs": {
            "nan_to_num": False,
            "arbitrary_clip": False,
            "arbitrary_floor": False,
            "failed_phase_deletion": False,
            "post_hoc_physical_renormalization": False,
        },
    }
    (output_dir / "phase7b4l_control_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["decision"], indent=2), flush=True)


def _profile_rows(cases: dict[int, PeriodicDynamicColumnSolution]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for effective_points, solution in cases.items():
        phase = _phase(solution)
        mass = _mass_centres(solution)
        for phase_index, phase_value in enumerate(phase):
            for depth_index, mass_value in enumerate(mass):
                rows.append(
                    {
                        "effective_depth_points": effective_points,
                        "phase_index": phase_index,
                        "orbital_time_phase": float(phase_value),
                        "depth_index": depth_index,
                        "mass_fraction_centre": float(mass_value),
                        "temperature_k": float(solution.temperature_k[phase_index, depth_index]),
                        "rosseland_opacity_cm2_g": float(
                            solution.rosseland_opacity_cm2_g[phase_index, depth_index]
                        ),
                        "hydrogen_ionized_fraction": float(
                            solution.hydrogen_fraction[phase_index, depth_index, 1]
                        ),
                        "helium_doubly_ionized_fraction": float(
                            solution.helium_fraction[phase_index, depth_index, 2]
                        ),
                    }
                )
    return rows


def _plot_depth(
    path: Path,
    cases: dict[int, PeriodicDynamicColumnSolution],
    rows: list[dict[str, object]],
) -> int:
    reference = cases[max(cases)]
    reference_mass = _mass_centres(reference)
    unique_status, _ = _front_locations(reference)
    candidates = [
        index for index, status in enumerate(unique_status) if status == "unique_crossing"
    ]
    if not candidates:
        raise RuntimeError("reference subcell solution has no unique He III front")
    gradients = [
        float(
            np.max(
                np.abs(
                    np.gradient(
                        reference.helium_fraction[index, :, 2], reference_mass
                    )
                )
            )
        )
        for index in candidates
    ]
    selected_phase = candidates[int(np.argmax(gradients))]

    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.4), constrained_layout=True)
    for effective_points, solution in cases.items():
        axes[0, 0].plot(
            _mass_centres(solution),
            solution.helium_fraction[selected_phase, :, 2],
            marker="o" if effective_points < max(cases) else None,
            markersize=3,
            label=f"N_eff={effective_points}",
        )
    axes[0, 0].axhline(0.5, color="black", linestyle=":", linewidth=1.0)
    axes[0, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="He III fraction",
        title=f"(a) Resolved front at phase index {selected_phase}",
    )
    axes[0, 0].legend(fontsize=8)

    for effective_points, solution in cases.items():
        axes[0, 1].plot(
            _phase(solution),
            solution.outward_flux_edges_erg_s_cm2[:, 0]
            / solution.grid.one_face_target_flux_erg_s_cm2,
            label=f"N_eff={effective_points}",
        )
    axes[0, 1].set(
        xlabel="Orbital time phase",
        ylabel="Emergent / instantaneous ZO flux",
        title="(b) Surface-flux response",
    )
    axes[0, 1].legend(fontsize=8)

    finite_rows = [row for row in rows if not bool(row["is_reference"])]
    x = np.array([row["effective_depth_points"] for row in finite_rows])
    axes[1, 0].loglog(
        x,
        [
            row["maximum_pointwise_temperature_or_opacity_relative_error"]
            for row in finite_rows
        ],
        marker="o",
        label="T / opacity",
    )
    axes[1, 0].loglog(
        x,
        [row["maximum_pointwise_population_absolute_error"] for row in finite_rows],
        marker="s",
        label="H II / He III",
    )
    axes[1, 0].axhline(PRODUCTION_TOLERANCE, color="black", linestyle=":", label="target")
    axes[1, 0].set(
        xlabel="Effective subcell depth points",
        ylabel="Maximum pointwise error",
        title="(c) Pointwise convergence",
    )
    axes[1, 0].legend(fontsize=8)

    axes[1, 1].loglog(
        x,
        [
            row["maximum_column_mean_temperature_or_opacity_relative_error"]
            for row in finite_rows
        ],
        marker="o",
        label="Column T / opacity",
    )
    axes[1, 1].loglog(
        x,
        [row["maximum_column_mean_population_absolute_error"] for row in finite_rows],
        marker="s",
        label="Column H II / He III",
    )
    axes[1, 1].loglog(
        x,
        [row["maximum_he_iii_half_front_mass_fraction_error"] for row in finite_rows],
        marker="^",
        label="He III front",
    )
    axes[1, 1].axhline(PRODUCTION_TOLERANCE, color="black", linestyle=":", label="target")
    axes[1, 1].set(
        xlabel="Effective subcell depth points",
        ylabel="Maximum error",
        title="(d) Integrated and front convergence",
    )
    axes[1, 1].legend(fontsize=8)
    figure.suptitle("Phase 7B4l: retained subcell depth convergence", fontsize=14)
    figure.savefig(path, dpi=180)
    plt.close(figure)
    return selected_phase


def run_depth(output_dir: Path, monitor_csv: Path) -> None:
    frequency = _frequency()
    background = _background(DEPTH_PHASE_POINTS)
    master_edges = _master_edges_from_monitor(monitor_csv)
    cases: dict[int, PeriodicDynamicColumnSolution] = {}
    initials: dict[int, ConservativeGroundStateSubcells] = {}
    restrictions: dict[int, ConservativeSubcellRestriction] = {}
    parent_grids: dict[int, PeriodicDynamicHalfColumn] = {}
    runtimes: dict[int, float] = {}
    for parent_points in PARENT_DEPTH_POINTS:
        effective_points = parent_points * SUBCELLS_PER_PARENT
        parent, initial, solution, restriction, elapsed = _solve_subcell_case(
            background, frequency, master_edges, parent_points
        )
        parent_grids[effective_points] = parent
        initials[effective_points] = initial
        cases[effective_points] = solution
        restrictions[effective_points] = restriction
        runtimes[effective_points] = elapsed
        print(
            f"parent {parent_points}, effective subcells {effective_points}: {elapsed:.1f} s",
            flush=True,
        )
    reference_points = max(cases)
    reference = cases[reference_points]
    rows: list[dict[str, object]] = []
    for effective_points in sorted(cases):
        initial = initials[effective_points]
        restriction = restrictions[effective_points]
        comparison = (
            {
                "surface_flux_relative_error": 0.0,
                "maximum_pointwise_temperature_or_opacity_relative_error": 0.0,
                "maximum_pointwise_population_absolute_error": 0.0,
                "maximum_column_mean_temperature_or_opacity_relative_error": 0.0,
                "maximum_column_mean_population_absolute_error": 0.0,
                "front_status_mismatch_phase_count": 0,
                "joint_unique_front_phase_count": sum(
                    status == "unique_crossing"
                    for status in _front_locations(reference)[0]
                ),
                "maximum_he_iii_half_front_mass_fraction_error": 0.0,
            }
            if effective_points == reference_points
            else _depth_comparison(cases[effective_points], reference)
        )
        rows.append(
            {
                "case": f"parent_{effective_points // SUBCELLS_PER_PARENT}_subcell_{SUBCELLS_PER_PARENT}",
                "parent_depth_points": effective_points // SUBCELLS_PER_PARENT,
                "subcells_per_parent": SUBCELLS_PER_PARENT,
                "effective_depth_points": effective_points,
                "is_reference": effective_points == reference_points,
                "runtime_s": runtimes[effective_points],
                **comparison,
                **_conservation_metrics(initial, restriction),
                "cycle_residual": cases[effective_points].cycle_residual,
                "energy_ledger_residual": cases[
                    effective_points
                ].relative_cycle_energy_ledger_residual,
            }
        )
    _write_csv(output_dir / "phase7b4l_subcell_convergence.csv", rows)
    _write_csv(output_dir / "phase7b4l_subcell_profiles.csv", _profile_rows(cases))
    edge_rows: list[dict[str, object]] = []
    for effective_points in sorted(cases):
        parent = parent_grids[effective_points].mass_fraction_edges
        child = cases[effective_points].grid.mass_fraction_edges
        for index, edge in enumerate(child):
            edge_rows.append(
                {
                    "effective_depth_points": effective_points,
                    "edge_index": index,
                    "mass_fraction_edge": float(edge),
                    "is_parent_edge": bool(index % SUBCELLS_PER_PARENT == 0),
                    "parent_edge_value": (
                        float(parent[index // SUBCELLS_PER_PARENT])
                        if index % SUBCELLS_PER_PARENT == 0
                        else ""
                    ),
                }
            )
    _write_csv(output_dir / "phase7b4l_subcell_edges.csv", edge_rows)
    selected_phase = _plot_depth(
        output_dir / "phase7b4l_subcell_convergence.png", cases, rows
    )

    candidate = next(row for row in rows if row["effective_depth_points"] == 32)
    key_errors = (
        "surface_flux_relative_error",
        "maximum_pointwise_temperature_or_opacity_relative_error",
        "maximum_pointwise_population_absolute_error",
        "maximum_column_mean_temperature_or_opacity_relative_error",
        "maximum_column_mean_population_absolute_error",
        "maximum_he_iii_half_front_mass_fraction_error",
    )
    depth_pass = bool(
        all(float(candidate[key]) < PRODUCTION_TOLERANCE for key in key_errors)
        and int(candidate["front_status_mismatch_phase_count"]) == 0
    )
    conservation_pass = _conservation_pass(rows)
    time_report_path = output_dir / "phase7b4k_time_report.json"
    if not time_report_path.exists():
        raise FileNotFoundError("Phase 7B4k time report is required for the combined gate")
    time_report = json.loads(time_report_path.read_text(encoding="utf-8"))
    time_pass = bool(
        time_report["decision"]["time_1024_production_converged_against_2048"]
    )
    report = {
        "phase": "7B4l",
        "classification": "[A/V/O] retained conservative subcell depth audit",
        "provenance": {
            "phase7b4k_monitor_csv": monitor_csv.name,
            "phase7b4k_time_report": time_report_path.name,
        },
        "configuration": {
            "depth_phase_points": DEPTH_PHASE_POINTS,
            "master_depth_points": MASTER_DEPTH_POINTS,
            "parent_depth_points": PARENT_DEPTH_POINTS,
            "subcells_per_parent": SUBCELLS_PER_PARENT,
            "effective_depth_points": EFFECTIVE_DEPTH_POINTS,
            "production_tolerance": PRODUCTION_TOLERANCE,
            "conservation_tolerance": CONSERVATION_TOLERANCE,
            "actual_frequency_points": int(frequency.size),
            "selected_front_phase_index": selected_phase,
            "subcell_interpretation": (
                "subcells are retained finite-volume degrees of freedom; they are not "
                "a cost-free high-order closure"
            ),
        },
        "depth_convergence": rows,
        "decision": {
            "subcell_conservation_passed": conservation_pass,
            "effective_32_depth_converged_against_64": depth_pass,
            "time_1024_production_converged_against_2048": time_pass,
            "combined_depth_time_reference_authorized": depth_pass and time_pass,
            "nonlocal_dynamic_transfer_authorized": depth_pass and time_pass,
            "phase4_atmosphere_replacement_authorized": False,
            "next_microphase_if_depth_fails": (
                "front-aware variable subcell refinement with an embedded conservative "
                "error estimator; retain the validated 1024-phase time target"
            ),
            "next_microphase_if_depth_passes": (
                "joint 1024-phase reference followed by nonlocal frequency-dependent "
                "dynamic transfer"
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
    (output_dir / "phase7b4l_subcell_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["decision"], indent=2), flush=True)


def refresh_saved_depth_conservation(output_dir: Path, monitor_csv: Path) -> None:
    """更正近零离化级的诊断归一化，不重算已保存的动力学解。"""
    report_path = output_dir / "phase7b4l_subcell_report.json"
    if not report_path.exists():
        raise FileNotFoundError("Phase 7B4l depth report is required for refresh")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if "diagnostic_correction" in report:
        print(json.dumps(report["decision"], indent=2), flush=True)
        return
    rows: list[dict[str, object]] = report["depth_convergence"]
    frequency = _frequency()
    background = _background(DEPTH_PHASE_POINTS)
    master_edges = _master_edges_from_monitor(monitor_csv)
    for row in rows:
        parent_points = int(row["parent_depth_points"])
        effective_points = int(row["effective_depth_points"])
        parent_grid = build_periodic_dynamic_half_column(
            background,
            parent_points,
            "uniform_specific",
            mass_fraction_edges=_nested_edges(master_edges, parent_points),
        )
        subcell_grid = build_periodic_dynamic_half_column(
            background,
            effective_points,
            "uniform_specific",
            mass_fraction_edges=_nested_edges(master_edges, effective_points),
        )
        initial = conservative_ground_state_subcells(
            parent_grid,
            subcell_grid,
            *_initial_state(background, parent_grid, frequency),
            SUBCELLS_PER_PARENT,
        )
        old_restricted_hydrogen = float(row.pop("restricted_hydrogen_residual"))
        old_restricted_helium = float(row.pop("restricted_helium_residual"))
        row.pop("initial_hydrogen_residual")
        row.pop("initial_helium_residual")
        row["initial_hydrogen_particle_residual"] = (
            initial.maximum_hydrogen_particle_residual
        )
        row["initial_helium_particle_residual"] = (
            initial.maximum_helium_particle_residual
        )
        row["initial_hydrogen_stage_absolute_residual"] = (
            initial.maximum_hydrogen_stage_absolute_residual
        )
        row["initial_helium_stage_absolute_residual"] = (
            initial.maximum_helium_stage_absolute_residual
        )
        # 中文：旧对称相对残差上界单级绝对差；级数倍数再上界总粒子差。
        row["restricted_hydrogen_particle_residual_upper_bound"] = (
            2.0 * old_restricted_hydrogen
        )
        row["restricted_helium_particle_residual_upper_bound"] = (
            3.0 * old_restricted_helium
        )
        row["restricted_hydrogen_stage_absolute_residual_upper_bound"] = (
            old_restricted_hydrogen
        )
        row["restricted_helium_stage_absolute_residual_upper_bound"] = (
            old_restricted_helium
        )
    report["decision"]["subcell_conservation_passed"] = _conservation_pass(rows)
    report["diagnostic_correction"] = {
        "reason": (
            "the first report used symmetric relative errors for nearly zero ion "
            "stages; total element particles now use a relative residual and ion "
            "stages use an absolute residual"
        ),
        "dynamics_recomputed": False,
        "initial_states_reconstructed_from_declared_inputs": True,
        "saved_restriction_relative_residuals_used_as_rigorous_absolute_upper_bounds": True,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_csv(output_dir / "phase7b4l_subcell_convergence.csv", rows)
    print(json.dumps(report["decision"], indent=2), flush=True)


def write_summary(output_dir: Path) -> None:
    control_path = output_dir / "phase7b4l_control_report.json"
    depth_path = output_dir / "phase7b4l_subcell_report.json"
    if not control_path.exists() or not depth_path.exists():
        raise FileNotFoundError("Phase 7B4l control and depth reports are both required")
    control = json.loads(control_path.read_text(encoding="utf-8"))
    depth = json.loads(depth_path.read_text(encoding="utf-8"))
    decision = {
        **control["decision"],
        **depth["decision"],
    }
    report = {
        "phase": "7B4l-complete",
        "classification": "[A/V/O] conservative subcell reconstruction gate",
        "control_report": control_path.name,
        "depth_report": depth_path.name,
        "decision": decision,
    }
    (output_dir / "phase7b4l_complete_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(decision, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--monitor-csv",
        type=Path,
        default=Path("outputs/phase7b4k_two_grid_monitor.csv"),
    )
    parser.add_argument(
        "--stage",
        choices=("control", "depth", "refresh", "summary", "all"),
        default="all",
    )
    arguments = parser.parse_args()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if arguments.stage in ("control", "all"):
        run_controls(arguments.output_dir)
    if arguments.stage in ("depth", "all"):
        run_depth(arguments.output_dir, arguments.monitor_csv)
    if arguments.stage == "refresh":
        refresh_saved_depth_conservation(arguments.output_dir, arguments.monitor_csv)
    if arguments.stage in ("summary", "all"):
        write_summary(arguments.output_dir)


if __name__ == "__main__":
    main()
