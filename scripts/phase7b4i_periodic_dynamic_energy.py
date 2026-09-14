"""生成 Phase 7B4i 周期动态 H/He 基态热柱的正式证据。"""

from __future__ import annotations

import argparse
import csv
import json
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
    build_periodic_dynamic_half_column,
    cyclic_log_density_increments,
    solve_periodic_dynamic_column,
)
from eccentric_tde_observer.radiation import (
    PLANCK_ERG_S,
    STEFAN_BOLTZMANN_ERG_S_CM2_K4,
)
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model


RADIAL_POINTS = 65
RADIAL_INDEX = 8
MAIN_PHASE_POINTS = 128
MAIN_DEPTH_POINTS = 8
MAIN_FREQUENCY_POINTS = 65
ENERGY_RANGE_EV = (0.1, 5000.0)
TIME_REFINEMENTS = (64, 128, 256)
DEPTH_REFINEMENTS = (4, 6, 8, 12)
FREQUENCY_REFINEMENTS = (33, 65, 129, 257)
SOLVER_MINIMUM_TEMPERATURE_K = 5000.0
SOLVER_MAXIMUM_TEMPERATURE_K = 2.0e6


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _frequency(base_points: int) -> np.ndarray:
    energy = edge_resolved_milne_energy_grid_ev(
        ENERGY_RANGE_EV[0], ENERGY_RANGE_EV[1], int(base_points)
    )
    return energy * EV_ERG / PLANCK_ERG_S


def _background(phase_points: int):
    model = build_strict_domain_reference_model(RADIAL_POINTS, int(phase_points))
    return build_zo_periodic_column_background(model, RADIAL_INDEX)


def _initial_state(background, grid, frequency, law: str, *, alternative: bool = False):
    column = build_zo_constrained_n3_column(
        float(background.one_sided_column_mass_g_cm2[0]),
        float(background.scale_height_cm[0]),
        float(background.pressure_gravity_coefficient_s2[0]),
        grid.half_depth_points,
    )
    dissipation = symmetric_dissipation_profile(
        column,
        float(background.one_face_surface_flux_erg_s_cm2[0]),
        law,
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
    if alternative:
        temperature *= 1.15
        hydrogen = np.broadcast_to(
            np.array([0.35, 0.65]), hydrogen.shape
        ).copy()
        helium = np.broadcast_to(
            np.array([0.25, 0.45, 0.30]), helium.shape
        ).copy()
    return temperature, hydrogen, helium


def _solve(
    phase_points: int,
    depth_points: int,
    frequency_points: int,
    law: str = "uniform_specific",
    *,
    alternative: bool = False,
    cycle_tolerance: float = 1.0e-8,
) -> PeriodicDynamicColumnSolution:
    background = _background(phase_points)
    grid = build_periodic_dynamic_half_column(background, depth_points, law)
    frequency = _frequency(frequency_points)
    initial = _initial_state(
        background, grid, frequency, law, alternative=alternative
    )
    return solve_periodic_dynamic_column(
        grid,
        frequency,
        *initial,
        include_collisional_kinetics=False,
        minimum_temperature_k=SOLVER_MINIMUM_TEMPERATURE_K,
        maximum_temperature_k=SOLVER_MAXIMUM_TEMPERATURE_K,
        cycle_tolerance=cycle_tolerance,
        local_energy_tolerance=2.0e-8,
        optimizer_tolerance=1.0e-10,
        maximum_function_evaluations=96,
        maximum_cycles=16,
    )


def _phase(solution: PeriodicDynamicColumnSolution) -> np.ndarray:
    return (
        solution.grid.background.time_since_pericentre_s
        / solution.grid.background.orbital_period_s
    )


def _observable_fields(solution: PeriodicDynamicColumnSolution) -> dict[str, np.ndarray]:
    return {
        "surface_temperature_k": solution.temperature_k[:, 0],
        "deep_temperature_k": solution.temperature_k[:, -1],
        "surface_flux_erg_s_cm2": solution.outward_flux_edges_erg_s_cm2[:, 0],
        "surface_h_ii_fraction": solution.hydrogen_fraction[:, 0, 1],
        "surface_he_iii_fraction": solution.helium_fraction[:, 0, 2],
    }


def _compare_to_reference(
    solution: PeriodicDynamicColumnSolution,
    reference: PeriodicDynamicColumnSolution,
) -> tuple[float, float]:
    phase = _phase(solution)
    reference_phase = _phase(reference)
    fields = _observable_fields(solution)
    reference_fields = _observable_fields(reference)
    maximum_relative = 0.0
    maximum_population = 0.0
    for name in ("surface_temperature_k", "deep_temperature_k", "surface_flux_erg_s_cm2"):
        interpolated = np.interp(
            reference_phase, phase, fields[name], period=1.0
        )
        error = np.max(
            np.abs(interpolated - reference_fields[name])
            / np.abs(reference_fields[name])
        )
        maximum_relative = max(maximum_relative, float(error))
    for name in ("surface_h_ii_fraction", "surface_he_iii_fraction"):
        interpolated = np.interp(
            reference_phase, phase, fields[name], period=1.0
        )
        maximum_population = max(
            maximum_population,
            float(np.max(np.abs(interpolated - reference_fields[name]))),
        )
    return maximum_relative, maximum_population


def _compare_depth_to_reference(
    solution: PeriodicDynamicColumnSolution,
    reference: PeriodicDynamicColumnSolution,
) -> tuple[float, float]:
    """在共同拉格朗日质量坐标上比较不同深度网格。"""
    if solution.grid.phase_points != reference.grid.phase_points:
        raise ValueError("depth convergence requires a shared phase grid")
    mass = 0.5 * (
        solution.grid.mass_fraction_edges[:-1]
        + solution.grid.mass_fraction_edges[1:]
    )
    reference_mass = 0.5 * (
        reference.grid.mass_fraction_edges[:-1]
        + reference.grid.mass_fraction_edges[1:]
    )
    lower = max(float(mass[0]), float(reference_mass[0]))
    upper = min(float(mass[-1]), float(reference_mass[-1]))
    if upper <= lower:
        raise ArithmeticError("depth grids have no common cell-centre mass interval")
    probe = np.linspace(lower, upper, 9)
    maximum_relative = float(
        np.max(
            np.abs(
                solution.outward_flux_edges_erg_s_cm2[:, 0]
                - reference.outward_flux_edges_erg_s_cm2[:, 0]
            )
            / np.abs(reference.outward_flux_edges_erg_s_cm2[:, 0])
        )
    )
    maximum_population = 0.0
    for phase in range(solution.grid.phase_points):
        for field, reference_field in (
            (solution.temperature_k, reference.temperature_k),
            (solution.rosseland_opacity_cm2_g, reference.rosseland_opacity_cm2_g),
        ):
            interpolated = np.interp(probe, mass, field[phase])
            reference_interpolated = np.interp(
                probe, reference_mass, reference_field[phase]
            )
            maximum_relative = max(
                maximum_relative,
                float(
                    np.max(
                        np.abs(interpolated - reference_interpolated)
                        / np.abs(reference_interpolated)
                    )
                ),
            )
        for field, reference_field in (
            (solution.hydrogen_fraction[:, :, 1], reference.hydrogen_fraction[:, :, 1]),
            (solution.helium_fraction[:, :, 2], reference.helium_fraction[:, :, 2]),
        ):
            interpolated = np.interp(probe, mass, field[phase])
            reference_interpolated = np.interp(
                probe, reference_mass, reference_field[phase]
            )
            maximum_population = max(
                maximum_population,
                float(np.max(np.abs(interpolated - reference_interpolated))),
            )
    return maximum_relative, maximum_population


def _convergence() -> tuple[list[dict[str, object]], dict[str, list[PeriodicDynamicColumnSolution]]]:
    cases: dict[str, list[PeriodicDynamicColumnSolution]] = {}
    rows: list[dict[str, object]] = []
    time_cases = [
        _solve(points, 4, 33, cycle_tolerance=2.0e-7)
        for points in TIME_REFINEMENTS
    ]
    cases["time"] = time_cases
    for resolution, solution in zip(TIME_REFINEMENTS, time_cases, strict=True):
        relative, population = _compare_to_reference(solution, time_cases[-1])
        rows.append(
            {
                "refinement": "orbital_time",
                "resolution": resolution,
                "maximum_temperature_or_flux_relative_error": relative,
                "maximum_population_absolute_error": population,
                "cycle_residual": solution.cycle_residual,
                "energy_ledger_residual": solution.relative_cycle_energy_ledger_residual,
            }
        )
    depth_cases = [
        _solve(64, points, 33, cycle_tolerance=2.0e-7)
        for points in DEPTH_REFINEMENTS
    ]
    cases["depth"] = depth_cases
    for resolution, solution in zip(DEPTH_REFINEMENTS, depth_cases, strict=True):
        relative, population = _compare_depth_to_reference(solution, depth_cases[-1])
        rows.append(
            {
                "refinement": "half_column_depth",
                "resolution": resolution,
                "maximum_temperature_or_flux_relative_error": relative,
                "maximum_population_absolute_error": population,
                "cycle_residual": solution.cycle_residual,
                "energy_ledger_residual": solution.relative_cycle_energy_ledger_residual,
            }
        )
    frequency_cases = [
        _solve(64, 4, points, cycle_tolerance=2.0e-7)
        for points in FREQUENCY_REFINEMENTS
    ]
    cases["frequency"] = frequency_cases
    for resolution, solution in zip(
        FREQUENCY_REFINEMENTS, frequency_cases, strict=True
    ):
        relative, population = _compare_to_reference(solution, frequency_cases[-1])
        rows.append(
            {
                "refinement": "rosseland_frequency",
                "resolution": resolution,
                "maximum_temperature_or_flux_relative_error": relative,
                "maximum_population_absolute_error": population,
                "cycle_residual": solution.cycle_residual,
                "energy_ledger_residual": solution.relative_cycle_energy_ledger_residual,
            }
        )
    return rows, cases


def _phase_rows(
    solution: PeriodicDynamicColumnSolution, law: str
) -> list[dict[str, object]]:
    background = solution.grid.background
    phase = _phase(solution)
    rows = []
    for index in range(solution.grid.phase_points):
        rows.append(
            {
                "dissipation_law": law,
                "phase_index": index,
                "orbital_time_phase": float(phase[index]),
                "eccentric_anomaly_rad": float(background.eccentric_anomaly_rad[index]),
                "scale_height_cm": float(background.scale_height_cm[index]),
                "surface_density_cell_g_cm3": float(solution.grid.density_g_cm3[index, 0]),
                "deep_density_cell_g_cm3": float(solution.grid.density_g_cm3[index, -1]),
                "zo_effective_temperature_k": float(background.effective_temperature_k[index]),
                "surface_cell_temperature_k": float(solution.temperature_k[index, 0]),
                "deep_cell_temperature_k": float(solution.temperature_k[index, -1]),
                "zo_target_face_flux_erg_s_cm2": float(
                    solution.grid.one_face_target_flux_erg_s_cm2[index]
                ),
                "dynamic_emergent_flux_erg_s_cm2": float(
                    solution.outward_flux_edges_erg_s_cm2[index, 0]
                ),
                "surface_h_ii_fraction": float(solution.hydrogen_fraction[index, 0, 1]),
                "deep_h_ii_fraction": float(solution.hydrogen_fraction[index, -1, 1]),
                "surface_he_iii_fraction": float(solution.helium_fraction[index, 0, 2]),
                "deep_he_iii_fraction": float(solution.helium_fraction[index, -1, 2]),
                "surface_rosseland_opacity_cm2_g": float(
                    solution.rosseland_opacity_cm2_g[index, 0]
                ),
                "deep_rosseland_opacity_cm2_g": float(
                    solution.rosseland_opacity_cm2_g[index, -1]
                ),
                "following_interval_compression_work_erg_cm2": float(
                    solution.interval_compression_work_erg_cm2[index]
                ),
                "following_interval_dissipation_energy_erg_cm2": float(
                    solution.interval_dissipation_energy_erg_cm2[index]
                ),
                "following_interval_emergent_energy_erg_cm2": float(
                    solution.interval_emergent_energy_erg_cm2[index]
                ),
            }
        )
    return rows


def _profile_rows(solution: PeriodicDynamicColumnSolution) -> list[dict[str, object]]:
    phase = _phase(solution)
    mass_centres = 0.5 * (
        solution.grid.mass_fraction_edges[:-1]
        + solution.grid.mass_fraction_edges[1:]
    )
    rows = []
    for phase_index in range(solution.grid.phase_points):
        for depth_index in range(solution.grid.half_depth_points):
            rows.append(
                {
                    "phase_index": phase_index,
                    "orbital_time_phase": float(phase[phase_index]),
                    "depth_index": depth_index,
                    "mass_fraction_to_midplane": float(mass_centres[depth_index]),
                    "density_g_cm3": float(
                        solution.grid.density_g_cm3[phase_index, depth_index]
                    ),
                    "temperature_k": float(
                        solution.temperature_k[phase_index, depth_index]
                    ),
                    "h_i_fraction": float(
                        solution.hydrogen_fraction[phase_index, depth_index, 0]
                    ),
                    "h_ii_fraction": float(
                        solution.hydrogen_fraction[phase_index, depth_index, 1]
                    ),
                    "he_i_fraction": float(
                        solution.helium_fraction[phase_index, depth_index, 0]
                    ),
                    "he_ii_fraction": float(
                        solution.helium_fraction[phase_index, depth_index, 1]
                    ),
                    "he_iii_fraction": float(
                        solution.helium_fraction[phase_index, depth_index, 2]
                    ),
                    "electron_density_cm3": float(
                        solution.electron_density_cm3[phase_index, depth_index]
                    ),
                    "rosseland_opacity_cm2_g": float(
                        solution.rosseland_opacity_cm2_g[phase_index, depth_index]
                    ),
                }
            )
    return rows


def _plot_main(
    path: Path,
    uniform: PeriodicDynamicColumnSolution,
    alpha: PeriodicDynamicColumnSolution,
) -> None:
    phase = _phase(uniform)
    background = uniform.grid.background
    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.4), constrained_layout=True)
    height_axis = axes[0, 0]
    density_axis = height_axis.twinx()
    height_axis.semilogy(
        phase,
        background.scale_height_cm / np.min(background.scale_height_cm),
        color="tab:blue",
        label="Scale height / minimum",
    )
    density_axis.semilogy(
        phase,
        uniform.grid.density_g_cm3[:, -1],
        color="tab:orange",
        label="Deep-cell density",
    )
    height_axis.set(
        xlabel="Orbital time phase",
        ylabel="Normalized scale height",
        title="(a) Prescribed ZO breathing background",
    )
    density_axis.set_ylabel(r"Density (g cm$^{-3}$)")
    lines = height_axis.lines + density_axis.lines
    height_axis.legend(lines, [line.get_label() for line in lines], fontsize=8)

    axes[0, 1].plot(
        phase, background.effective_temperature_k, color="black", label="ZO effective"
    )
    axes[0, 1].plot(
        phase, uniform.temperature_k[:, 0], label="Dynamic surface cell"
    )
    axes[0, 1].plot(
        phase, uniform.temperature_k[:, -1], label="Dynamic deep cell"
    )
    axes[0, 1].set(
        xlabel="Orbital time phase",
        ylabel="Temperature (K)",
        title="(b) Time-dependent thermal response",
    )
    axes[0, 1].legend(fontsize=8)

    axes[1, 0].semilogy(
        phase,
        uniform.grid.one_face_target_flux_erg_s_cm2,
        color="black",
        label="ZO dissipation input",
    )
    axes[1, 0].semilogy(
        phase,
        uniform.outward_flux_edges_erg_s_cm2[:, 0],
        label="Uniform-specific emergent",
    )
    axes[1, 0].semilogy(
        phase,
        alpha.outward_flux_edges_erg_s_cm2[:, 0],
        linestyle="--",
        label="Pressure-weighted emergent",
    )
    axes[1, 0].set(
        xlabel="Orbital time phase",
        ylabel=r"One-face flux (erg s$^{-1}$ cm$^{-2}$)",
        title="(c) Dissipation, storage and delayed escape",
    )
    axes[1, 0].legend(fontsize=8)

    axes[1, 1].plot(
        phase, uniform.hydrogen_fraction[:, 0, 1], label="Surface H II"
    )
    axes[1, 1].plot(
        phase, uniform.hydrogen_fraction[:, -1, 1], label="Deep H II"
    )
    axes[1, 1].plot(
        phase, uniform.helium_fraction[:, 0, 2], label="Surface He III"
    )
    axes[1, 1].plot(
        phase, uniform.helium_fraction[:, -1, 2], label="Deep He III"
    )
    axes[1, 1].set(
        xlabel="Orbital time phase",
        ylabel="Ion fraction",
        title="(d) Time-dependent ground-state populations",
        ylim=(-0.03, 1.03),
    )
    axes[1, 1].legend(fontsize=8, ncol=2)
    figure.suptitle("Phase 7B4i: periodic dynamic H/He energy column", fontsize=14)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_energy_convergence(
    path: Path,
    uniform: PeriodicDynamicColumnSolution,
    alpha: PeriodicDynamicColumnSolution,
    convergence_rows: list[dict[str, object]],
) -> None:
    phase = _phase(uniform)
    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.4), constrained_layout=True)
    cumulative_dissipation = np.cumsum(uniform.interval_dissipation_energy_erg_cm2)
    normalization = cumulative_dissipation[-1]
    axes[0, 0].plot(
        phase,
        cumulative_dissipation / normalization,
        label="Dissipation",
    )
    axes[0, 0].plot(
        phase,
        np.cumsum(uniform.interval_emergent_energy_erg_cm2) / normalization,
        label="Emergent",
    )
    axes[0, 0].plot(
        phase,
        np.cumsum(uniform.interval_compression_work_erg_cm2) / normalization,
        label="Compression work",
    )
    axes[0, 0].set(
        xlabel="Orbital time phase",
        ylabel="Cumulative energy / orbit dissipation",
        title="(a) One-orbit energy ledger",
    )
    axes[0, 0].legend(fontsize=8)

    target = uniform.grid.one_face_target_flux_erg_s_cm2
    axes[0, 1].plot(
        phase,
        uniform.outward_flux_edges_erg_s_cm2[:, 0] / target,
        label="Uniform-specific",
    )
    axes[0, 1].plot(
        phase,
        alpha.outward_flux_edges_erg_s_cm2[:, 0] / target,
        linestyle="--",
        label="Pressure-weighted",
    )
    axes[0, 1].axhline(1.0, color="black", linewidth=0.8)
    axes[0, 1].set(
        xlabel="Orbital time phase",
        ylabel="Emergent / instantaneous ZO flux",
        title="(b) Thermal memory by dissipation law",
    )
    axes[0, 1].legend(fontsize=8)

    colors = {
        "orbital_time": "tab:blue",
        "half_column_depth": "tab:orange",
        "rosseland_frequency": "tab:green",
    }
    for refinement, color in colors.items():
        selected = [row for row in convergence_rows if row["refinement"] == refinement]
        resolution = np.array([row["resolution"] for row in selected], dtype=float)
        error = np.array(
            [row["maximum_temperature_or_flux_relative_error"] for row in selected],
            dtype=float,
        )
        active = error > 0.0
        axes[1, 0].loglog(
            resolution[active], error[active], marker="o", color=color, label=refinement
        )
    axes[1, 0].set(
        xlabel="Resolution",
        ylabel="Maximum relative error",
        title="(c) Temperature and flux convergence",
    )
    axes[1, 0].legend(fontsize=8)

    for refinement, color in colors.items():
        selected = [row for row in convergence_rows if row["refinement"] == refinement]
        resolution = np.array([row["resolution"] for row in selected], dtype=float)
        error = np.array(
            [row["maximum_population_absolute_error"] for row in selected], dtype=float
        )
        active = error > 0.0
        axes[1, 1].loglog(
            resolution[active], error[active], marker="o", color=color, label=refinement
        )
    axes[1, 1].set(
        xlabel="Resolution",
        ylabel="Maximum ion-fraction error",
        title="(d) Population convergence",
    )
    axes[1, 1].legend(fontsize=8)
    figure.suptitle("Phase 7B4i: energy closure and numerical convergence", fontsize=14)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _solution_summary(solution: PeriodicDynamicColumnSolution) -> dict[str, object]:
    target = solution.grid.one_face_target_flux_erg_s_cm2
    emergent = solution.outward_flux_edges_erg_s_cm2[:, 0]
    return {
        "cycle_count": solution.cycle_count,
        "cycle_residual": solution.cycle_residual,
        "minimum_temperature_k": solution.minimum_temperature_k,
        "maximum_temperature_k": solution.maximum_temperature_k,
        "minimum_population_fraction": solution.minimum_population_fraction,
        "maximum_relative_local_energy_residual": solution.maximum_relative_local_energy_residual,
        "maximum_relative_charge_residual": solution.maximum_relative_charge_residual,
        "maximum_particle_conservation_residual": solution.maximum_particle_conservation_residual,
        "relative_cycle_energy_ledger_residual": solution.relative_cycle_energy_ledger_residual,
        "cycle_internal_energy_change_erg_cm2": solution.cycle_internal_energy_change_erg_cm2,
        "cycle_compression_work_erg_cm2": solution.cycle_compression_work_erg_cm2,
        "cycle_dissipation_energy_erg_cm2": solution.cycle_dissipation_energy_erg_cm2,
        "cycle_emergent_energy_erg_cm2": solution.cycle_emergent_energy_erg_cm2,
        "minimum_emergent_to_target_flux": float(np.min(emergent / target)),
        "maximum_emergent_to_target_flux": float(np.max(emergent / target)),
        "phase_of_maximum_emergent_flux": float(_phase(solution)[np.argmax(emergent)]),
        "phase_of_maximum_target_flux": float(_phase(solution)[np.argmax(target)]),
        "maximum_surface_h_ii_fraction": float(
            np.max(solution.hydrogen_fraction[:, 0, 1])
        ),
        "minimum_surface_h_ii_fraction": float(
            np.min(solution.hydrogen_fraction[:, 0, 1])
        ),
        "maximum_surface_he_iii_fraction": float(
            np.max(solution.helium_fraction[:, 0, 2])
        ),
        "minimum_surface_he_iii_fraction": float(
            np.min(solution.helium_fraction[:, 0, 2])
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    arguments = parser.parse_args()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)

    uniform = _solve(
        MAIN_PHASE_POINTS,
        MAIN_DEPTH_POINTS,
        MAIN_FREQUENCY_POINTS,
        "uniform_specific",
    )
    alternative = _solve(
        MAIN_PHASE_POINTS,
        MAIN_DEPTH_POINTS,
        MAIN_FREQUENCY_POINTS,
        "uniform_specific",
        alternative=True,
    )
    alpha = _solve(
        MAIN_PHASE_POINTS,
        MAIN_DEPTH_POINTS,
        MAIN_FREQUENCY_POINTS,
        "alpha_support_pressure",
    )
    initial_temperature_difference = float(
        np.max(
            np.abs(uniform.temperature_k - alternative.temperature_k)
            / uniform.temperature_k
        )
    )
    initial_population_difference = float(
        max(
            np.max(
                np.abs(
                    uniform.hydrogen_fraction - alternative.hydrogen_fraction
                )
            ),
            np.max(
                np.abs(uniform.helium_fraction - alternative.helium_fraction)
            ),
        )
    )
    log_density = cyclic_log_density_increments(uniform.grid.density_g_cm3)
    maximum_log_density_closure = float(
        np.max(np.abs(np.sum(log_density, axis=0)))
    )
    convergence_rows, _ = _convergence()
    main_relative_to_reference, main_population_to_reference = _compare_to_reference(
        uniform,
        _solve(256, MAIN_DEPTH_POINTS, MAIN_FREQUENCY_POINTS, cycle_tolerance=2.0e-7),
    )

    _write_csv(
        arguments.output_dir / "phase7b4i_periodic_dynamic_phase.csv",
        _phase_rows(uniform, "uniform_specific")
        + _phase_rows(alpha, "alpha_support_pressure"),
    )
    _write_csv(
        arguments.output_dir / "phase7b4i_periodic_dynamic_profile.csv",
        _profile_rows(uniform),
    )
    _write_csv(
        arguments.output_dir / "phase7b4i_periodic_dynamic_convergence.csv",
        convergence_rows,
    )
    _plot_main(
        arguments.output_dir / "phase7b4i_periodic_dynamic_column.png",
        uniform,
        alpha,
    )
    _plot_energy_convergence(
        arguments.output_dir / "phase7b4i_energy_convergence.png",
        uniform,
        alpha,
        convergence_rows,
    )

    report = {
        "phase": "7B4i",
        "classification": "[A/V/O] periodic dynamic ground-state H/He energy foundation",
        "scope": {
            "implemented": [
                "Lagrangian half-column on the prescribed ZO breathing background",
                "finite-step compression work",
                "prescribed ZO dissipation",
                "ground-state H/He ionization energy and time-dependent populations",
                "local trapped Planck-Milne radiative rates",
                "Rosseland diffusion with vacuum surface and zero-flux midplane",
            ],
            "not_implemented": [
                "non-local frequency-dependent time-dependent transfer",
                "multi-level NLTE statistical equilibrium",
                "bound-bound line transfer and line blanketing",
                "Compton frequency redistribution",
                "variable-column-mass horizontal convergence",
                "observer-frame atmosphere replacement",
            ],
            "collision_decision": (
                "Voronov collisional kinetics disabled in the formal run because the "
                "dynamic surface temperature crosses below the declared He II fit domain; "
                "no extrapolation, clipping or floor was used"
            ),
        },
        "configuration": {
            "radial_index": RADIAL_INDEX,
            "semimajor_axis_cm": uniform.grid.background.semimajor_axis_cm,
            "eccentricity": uniform.grid.background.eccentricity,
            "orbital_period_s": uniform.grid.background.orbital_period_s,
            "phase_points": MAIN_PHASE_POINTS,
            "half_depth_points": MAIN_DEPTH_POINTS,
            "frequency_base_points": MAIN_FREQUENCY_POINTS,
            "actual_frequency_points": int(uniform.frequency_hz.size),
            "energy_range_ev": ENERGY_RANGE_EV,
            "radiation_closure": uniform.radiation_closure,
            "includes_collisional_kinetics": uniform.includes_collisional_kinetics,
            "solver_temperature_bounds_k": [
                SOLVER_MINIMUM_TEMPERATURE_K,
                SOLVER_MAXIMUM_TEMPERATURE_K,
            ],
            "maximum_relative_column_mass_variation": uniform.grid.maximum_relative_column_mass_variation,
        },
        "analytic_and_conservation_controls": {
            "maximum_absolute_cyclic_log_density_closure": maximum_log_density_closure,
            "midplane_flux_is_exactly_zero": bool(
                np.all(uniform.outward_flux_edges_erg_s_cm2[:, -1] == 0.0)
            ),
            "minimum_density_g_cm3": float(np.min(uniform.grid.density_g_cm3)),
            "maximum_density_g_cm3": float(np.max(uniform.grid.density_g_cm3)),
            "initial_condition_temperature_relative_difference": initial_temperature_difference,
            "initial_condition_population_absolute_difference": initial_population_difference,
        },
        "uniform_specific": _solution_summary(uniform),
        "alpha_support_pressure": _solution_summary(alpha),
        "main_grid_against_256_phase_reference": {
            "maximum_temperature_or_flux_relative_error": main_relative_to_reference,
            "maximum_population_absolute_error": main_population_to_reference,
        },
        "convergence": convergence_rows,
        "decision": {
            "periodic_energy_and_population_foundation_passed": bool(
                uniform.relative_cycle_energy_ledger_residual < 1.0e-8
                and uniform.maximum_relative_local_energy_residual < 1.0e-7
                and initial_temperature_difference < 1.0e-6
                and initial_population_difference < 1.0e-6
            ),
            "production_resolution_converged": bool(
                main_relative_to_reference < 1.0e-3
                and main_population_to_reference < 1.0e-3
            ),
            "phase4_atmosphere_replacement_authorized": False,
            "uvot_count_prediction_authorized": False,
            "complete_nlte_spectrum_claim_authorized": False,
            "next_microphase": (
                "establish adaptive Lagrangian depth and higher-resolution orbital-time "
                "convergence, then replace local Planck diffusion by non-local "
                "frequency-dependent radiation-energy coupling"
            ),
        },
        "forbidden_repairs": {
            "nan_to_num": False,
            "arbitrary_clip": False,
            "arbitrary_floor": False,
            "failed_point_deletion": False,
            "post_hoc_renormalization": False,
        },
    }
    (arguments.output_dir / "phase7b4i_periodic_dynamic_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["decision"], indent=2))


if __name__ == "__main__":
    main()
