"""生成 Phase 7B4m 前沿感知可变子单元控制、正式解与准入判据。"""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr

from eccentric_tde_observer.adaptive_subcell_refinement import (
    EmbeddedConservativeParentError,
    FrontAwareVariableSubcellGrid,
    embedded_conservative_parent_error,
    front_aware_variable_subcell_grid,
)
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
    PeriodicDynamicHalfColumn,
    build_periodic_dynamic_half_column,
    diffusion_outward_flux_edges_erg_s_cm2,
    solve_periodic_dynamic_column,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model
from eccentric_tde_observer.subcell_reconstruction import (
    ConservativeCoarsenedGroundState,
    ConservativeVariableSubcellRestriction,
    coarsen_ground_state_subcells,
    conservative_ground_state_subcells,
    nested_mass_cell_offsets,
    restrict_periodic_dynamic_variable_subcells,
)


RADIAL_POINTS = 65
RADIAL_INDEX = 8
PHASE_POINTS = 64
PARENT_DEPTH_POINTS = 16
PILOT_DEPTH_POINTS = 32
MASTER_DEPTH_POINTS = 64
FORMAL_REFINED_PARENT_COUNTS = (12, 14, 15)
CONTROL_REFINED_PARENT_COUNTS = (0, 4, 8, 12, 14, 15, 16)
ENERGY_RANGE_EV = (0.1, 5000.0)
FREQUENCY_BASE_POINTS = 65
MINIMUM_TEMPERATURE_K = 5000.0
MAXIMUM_TEMPERATURE_K = 2.0e6
CYCLE_TOLERANCE = 2.0e-7
PRODUCTION_TOLERANCE = 1.0e-3
CONSERVATION_TOLERANCE = 2.0e-12
SPATIAL_GATE_KEYS = (
    "surface_flux_relative_error",
    "maximum_pointwise_temperature_or_opacity_relative_error",
    "maximum_pointwise_population_absolute_error",
    "maximum_column_mean_temperature_or_opacity_relative_error",
    "maximum_column_mean_population_absolute_error",
    "maximum_he_iii_half_front_mass_fraction_error",
)


@dataclass(frozen=True)
class SavedProfiles:
    edges: np.ndarray
    orbital_phase: np.ndarray
    temperature_k: np.ndarray
    opacity_cm2_g: np.ndarray
    h_ii: np.ndarray
    he_iii: np.ndarray
    surface_flux_erg_s_cm2: np.ndarray
    cell_mass_g_cm2: np.ndarray


@dataclass(frozen=True)
class CandidateProfiles:
    refined_parent_count: int
    edges: np.ndarray
    orbital_phase: np.ndarray
    temperature_k: np.ndarray
    opacity_cm2_g: np.ndarray
    hydrogen_fraction: np.ndarray
    helium_fraction: np.ndarray
    surface_flux_erg_s_cm2: np.ndarray
    cell_mass_g_cm2: np.ndarray
    report: dict[str, object]


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


def _background():
    model = build_strict_domain_reference_model(RADIAL_POINTS, PHASE_POINTS)
    return build_zo_periodic_column_background(model, RADIAL_INDEX)


def _saved_edges(path: Path) -> dict[int, np.ndarray]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    grouped: dict[int, list[tuple[int, float]]] = {}
    for row in rows:
        points = int(row["effective_depth_points"])
        grouped.setdefault(points, []).append(
            (int(row["edge_index"]), float(row["mass_fraction_edge"]))
        )
    result = {
        points: np.array([value for _, value in sorted(values)])
        for points, values in grouped.items()
    }
    if set(result) != {16, 32, 64}:
        raise ValueError("Phase 7B4l edge table must contain 16, 32 and 64 cells")
    if (
        not np.array_equal(result[64][::2], result[32])
        or not np.array_equal(result[64][::4], result[16])
    ):
        raise ValueError("Phase 7B4l saved grids are no longer strictly nested")
    return result


def _saved_field_rows(path: Path) -> dict[int, list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    grouped: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(int(row["effective_depth_points"]), []).append(row)
    for depth_points, values in grouped.items():
        values.sort(
            key=lambda row: (int(row["phase_index"]), int(row["depth_index"]))
        )
        actual_indices = [
            (int(row["phase_index"]), int(row["depth_index"]))
            for row in values
        ]
        expected_indices = [
            (phase, depth)
            for phase in range(PHASE_POINTS)
            for depth in range(depth_points)
        ]
        if actual_indices != expected_indices:
            raise ValueError(
                f"Phase 7B4l saved field grid is incomplete for N={depth_points}"
            )
    return grouped


def _reference_runtime_s(report_path: Path) -> float:
    if not report_path.exists():
        raise FileNotFoundError("Phase 7B4l reference report is required")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    references = [
        row
        for row in report["depth_convergence"]
        if bool(row["is_reference"])
        and int(row["effective_depth_points"]) == MASTER_DEPTH_POINTS
    ]
    if len(references) != 1:
        raise ValueError("Phase 7B4l report must contain one finite N=64 reference")
    runtime = float(references[0]["runtime_s"])
    if not np.isfinite(runtime) or runtime <= 0.0:
        raise ValueError("Phase 7B4l reference runtime must be positive and finite")
    return runtime


def _profile_array(
    rows: list[dict[str, str]], key: str, depth_points: int
) -> np.ndarray:
    result = np.array([float(row[key]) for row in rows]).reshape(
        PHASE_POINTS, depth_points
    )
    if not np.all(np.isfinite(result)):
        raise ValueError(f"saved Phase 7B4l field {key} became non-finite")
    return result


def _estimator(
    edges: dict[int, np.ndarray],
    rows: dict[int, list[dict[str, str]]],
) -> EmbeddedConservativeParentError:
    pilot = rows[PILOT_DEPTH_POINTS]
    return embedded_conservative_parent_error(
        edges[PARENT_DEPTH_POINTS],
        edges[PILOT_DEPTH_POINTS],
        _profile_array(pilot, "temperature_k", PILOT_DEPTH_POINTS),
        _profile_array(pilot, "rosseland_opacity_cm2_g", PILOT_DEPTH_POINTS),
        _profile_array(pilot, "hydrogen_ionized_fraction", PILOT_DEPTH_POINTS),
        _profile_array(
            pilot, "helium_doubly_ionized_fraction", PILOT_DEPTH_POINTS
        ),
        production_tolerance=PRODUCTION_TOLERANCE,
    )


def _variable_grid(
    error: EmbeddedConservativeParentError,
    master_edges: np.ndarray,
    refined_parent_count: int,
) -> FrontAwareVariableSubcellGrid:
    return front_aware_variable_subcell_grid(
        error, master_edges, refined_parent_count
    )


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


def _reference_profiles(
    background,
    edges: dict[int, np.ndarray],
    rows: dict[int, list[dict[str, str]]],
) -> SavedProfiles:
    reference_edges = edges[MASTER_DEPTH_POINTS]
    grid = build_periodic_dynamic_half_column(
        background,
        MASTER_DEPTH_POINTS,
        "uniform_specific",
        mass_fraction_edges=reference_edges,
    )
    saved = rows[MASTER_DEPTH_POINTS]
    centres = _profile_array(saved, "mass_fraction_centre", MASTER_DEPTH_POINTS)[0]
    expected_centres = 0.5 * (reference_edges[:-1] + reference_edges[1:])
    if not np.array_equal(centres, expected_centres):
        raise ValueError("saved Phase 7B4l profiles no longer match their grid")
    temperature = _profile_array(saved, "temperature_k", MASTER_DEPTH_POINTS)
    opacity = _profile_array(
        saved, "rosseland_opacity_cm2_g", MASTER_DEPTH_POINTS
    )
    surface_flux = np.array(
        [
            diffusion_outward_flux_edges_erg_s_cm2(
                temperature[index], opacity[index], grid.cell_mass_g_cm2
            )[0]
            for index in range(PHASE_POINTS)
        ]
    )
    return SavedProfiles(
        edges=reference_edges,
        orbital_phase=(
            background.time_since_pericentre_s / background.orbital_period_s
        ),
        temperature_k=temperature,
        opacity_cm2_g=opacity,
        h_ii=_profile_array(
            saved, "hydrogen_ionized_fraction", MASTER_DEPTH_POINTS
        ),
        he_iii=_profile_array(
            saved, "helium_doubly_ionized_fraction", MASTER_DEPTH_POINTS
        ),
        surface_flux_erg_s_cm2=surface_flux,
        cell_mass_g_cm2=grid.cell_mass_g_cm2,
    )


def _coarsened_reference_field(
    reference: SavedProfiles,
    candidate_edges: np.ndarray,
    values: np.ndarray,
) -> np.ndarray:
    offsets = nested_mass_cell_offsets(candidate_edges, reference.edges)
    result = np.empty((PHASE_POINTS, candidate_edges.size - 1))
    for parent, (left, right) in enumerate(
        zip(offsets[:-1], offsets[1:], strict=True)
    ):
        result[:, parent] = np.sum(
            values[:, left:right]
            * reference.cell_mass_g_cm2[None, left:right],
            axis=1,
        ) / np.sum(reference.cell_mass_g_cm2[left:right])
    return result


def _pointwise_errors(
    candidate_edges: np.ndarray,
    candidate_fields: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    reference: SavedProfiles,
) -> tuple[float, float]:
    candidate_mass = 0.5 * (candidate_edges[:-1] + candidate_edges[1:])
    reference_mass = 0.5 * (reference.edges[:-1] + reference.edges[1:])
    lower = max(float(candidate_mass[0]), float(reference_mass[0]))
    upper = min(float(candidate_mass[-1]), float(reference_mass[-1]))
    probe = np.linspace(lower, upper, 1025)
    relative = 0.0
    population = 0.0
    reference_fields = (
        reference.temperature_k,
        reference.opacity_cm2_g,
        reference.h_ii,
        reference.he_iii,
    )
    for phase in range(PHASE_POINTS):
        for field_index, (candidate, target) in enumerate(
            zip(candidate_fields, reference_fields, strict=True)
        ):
            candidate_value = np.interp(probe, candidate_mass, candidate[phase])
            target_value = np.interp(probe, reference_mass, target[phase])
            if field_index < 2:
                relative = max(
                    relative,
                    float(
                        np.max(
                            np.abs(candidate_value - target_value)
                            / np.abs(target_value)
                        )
                    ),
                )
            else:
                population = max(
                    population,
                    float(np.max(np.abs(candidate_value - target_value))),
                )
    return relative, population


def _front_locations(
    edges: np.ndarray, he_iii: np.ndarray
) -> tuple[list[str], list[float | None]]:
    centres = 0.5 * (edges[:-1] + edges[1:])
    statuses: list[str] = []
    locations: list[float | None] = []
    for fraction in he_iii:
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


def _comparison(
    candidate: CandidateProfiles,
    reference: SavedProfiles,
) -> dict[str, object]:
    h_ii = candidate.hydrogen_fraction[:, :, 1]
    he_iii = candidate.helium_fraction[:, :, 2]
    relative, population = _pointwise_errors(
        candidate.edges,
        (
            candidate.temperature_k,
            candidate.opacity_cm2_g,
            h_ii,
            he_iii,
        ),
        reference,
    )
    weight = candidate.cell_mass_g_cm2 / np.sum(candidate.cell_mass_g_cm2)
    reference_weight = reference.cell_mass_g_cm2 / np.sum(
        reference.cell_mass_g_cm2
    )
    candidate_means = (
        np.sum(candidate.temperature_k * weight[None, :], axis=1),
        np.sum(candidate.opacity_cm2_g * weight[None, :], axis=1),
        np.sum(h_ii * weight[None, :], axis=1),
        np.sum(he_iii * weight[None, :], axis=1),
    )
    reference_means = (
        np.sum(reference.temperature_k * reference_weight[None, :], axis=1),
        np.sum(reference.opacity_cm2_g * reference_weight[None, :], axis=1),
        np.sum(reference.h_ii * reference_weight[None, :], axis=1),
        np.sum(reference.he_iii * reference_weight[None, :], axis=1),
    )
    mean_relative = max(
        float(np.max(np.abs(value - target) / np.abs(target)))
        for value, target in zip(
            candidate_means[:2], reference_means[:2], strict=True
        )
    )
    mean_population = max(
        float(np.max(np.abs(value - target)))
        for value, target in zip(
            candidate_means[2:], reference_means[2:], strict=True
        )
    )
    statuses, locations = _front_locations(candidate.edges, he_iii)
    reference_statuses, reference_locations = _front_locations(
        reference.edges, reference.he_iii
    )
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
        "surface_flux_relative_error": float(
            np.max(
                np.abs(
                    candidate.surface_flux_erg_s_cm2
                    - reference.surface_flux_erg_s_cm2
                )
                / np.abs(reference.surface_flux_erg_s_cm2)
            )
        ),
        "maximum_pointwise_temperature_or_opacity_relative_error": relative,
        "maximum_pointwise_population_absolute_error": population,
        "maximum_column_mean_temperature_or_opacity_relative_error": mean_relative,
        "maximum_column_mean_population_absolute_error": mean_population,
        "front_status_mismatch_phase_count": mismatch,
        "joint_unique_front_phase_count": len(front_errors),
        "maximum_he_iii_half_front_mass_fraction_error": (
            max(front_errors) if front_errors else None
        ),
    }


def _parent_field_errors(
    candidate_edges: np.ndarray,
    fields: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    reference: SavedProfiles,
    parent_edges: np.ndarray,
) -> np.ndarray:
    candidate_mass = 0.5 * (candidate_edges[:-1] + candidate_edges[1:])
    reference_mass = 0.5 * (reference.edges[:-1] + reference.edges[1:])
    reference_fields = (
        reference.temperature_k,
        reference.opacity_cm2_g,
        reference.h_ii,
        reference.he_iii,
    )
    result = np.zeros(parent_edges.size - 1)
    for parent, (left, right) in enumerate(
        zip(parent_edges[:-1], parent_edges[1:], strict=True)
    ):
        lower = max(left, float(candidate_mass[0]), float(reference_mass[0]))
        upper = min(right, float(candidate_mass[-1]), float(reference_mass[-1]))
        if upper <= lower:
            raise ArithmeticError("a parent interval has no shared comparison domain")
        probe = np.linspace(lower, upper, 65)
        for phase in range(PHASE_POINTS):
            for field_index, (values, targets) in enumerate(
                zip(fields, reference_fields, strict=True)
            ):
                value = np.interp(probe, candidate_mass, values[phase])
                target = np.interp(probe, reference_mass, targets[phase])
                error = (
                    np.abs(value - target) / np.abs(target)
                    if field_index < 2
                    else np.abs(value - target)
                )
                result[parent] = max(result[parent], float(np.max(error)))
    return result / PRODUCTION_TOLERANCE


def _parent_actual_errors(
    candidate: CandidateProfiles,
    reference: SavedProfiles,
    parent_edges: np.ndarray,
) -> np.ndarray:
    return _parent_field_errors(
        candidate.edges,
        (
            candidate.temperature_k,
            candidate.opacity_cm2_g,
            candidate.hydrogen_fraction[:, :, 1],
            candidate.helium_fraction[:, :, 2],
        ),
        reference,
        parent_edges,
    )


def _control_representation_errors(
    grid: FrontAwareVariableSubcellGrid,
    reference: SavedProfiles,
) -> tuple[float, float]:
    candidate_fields = tuple(
        _coarsened_reference_field(reference, grid.mass_fraction_edges, values)
        for values in (
            reference.temperature_k,
            reference.opacity_cm2_g,
            reference.h_ii,
            reference.he_iii,
        )
    )
    return _pointwise_errors(grid.mass_fraction_edges, candidate_fields, reference)


def run_control(
    output_dir: Path,
    profiles_path: Path,
    edges_path: Path,
) -> None:
    edges = _saved_edges(edges_path)
    rows = _saved_field_rows(profiles_path)
    error = _estimator(edges, rows)
    background = _background()
    reference = _reference_profiles(background, edges, rows)
    rank = np.empty(PARENT_DEPTH_POINTS, dtype=np.int64)
    rank[error.descending_parent_order] = np.arange(1, PARENT_DEPTH_POINTS + 1)
    indicator_rows = []
    for parent in range(PARENT_DEPTH_POINTS):
        indicator_rows.append(
            {
                "parent_index": parent,
                "mass_fraction_left": float(edges[16][parent]),
                "mass_fraction_right": float(edges[16][parent + 1]),
                "log_temperature_error": float(error.log_temperature_error[parent]),
                "log_opacity_error": float(error.log_opacity_error[parent]),
                "hydrogen_ionized_error": float(
                    error.hydrogen_ionized_error[parent]
                ),
                "helium_doubly_ionized_error": float(
                    error.helium_doubly_ionized_error[parent]
                ),
                "normalized_indicator": float(error.normalized_indicator[parent]),
                "descending_error_rank": int(rank[parent]),
                "helium_iii_half_front_encountered": bool(
                    error.helium_iii_half_front_encountered[parent]
                ),
            }
        )
    _write_csv(output_dir / "phase7b4m_embedded_indicator.csv", indicator_rows)

    budget_rows = []
    grids = {}
    for count in CONTROL_REFINED_PARENT_COUNTS:
        grid = _variable_grid(error, edges[64], count)
        grids[count] = grid
        relative, population = _control_representation_errors(grid, reference)
        budget_rows.append(
            {
                "refined_parent_count": count,
                "effective_depth_points": grid.effective_depth_points,
                "maximum_unrefined_indicator": grid.maximum_unrefined_indicator,
                "minimum_refined_indicator": (
                    ""
                    if grid.minimum_refined_indicator is None
                    else grid.minimum_refined_indicator
                ),
                "reference_assisted_representation_temperature_or_opacity_error": relative,
                "reference_assisted_representation_population_error": population,
            }
        )
    _write_csv(output_dir / "phase7b4m_refinement_budgets.csv", budget_rows)

    edge_rows = []
    for count, grid in grids.items():
        offsets = nested_mass_cell_offsets(
            grid.parent_mass_fraction_edges, grid.mass_fraction_edges
        )
        for edge_index, value in enumerate(grid.mass_fraction_edges):
            edge_rows.append(
                {
                    "refined_parent_count": count,
                    "effective_depth_points": grid.effective_depth_points,
                    "edge_index": edge_index,
                    "mass_fraction_edge": float(value),
                    "is_parent_edge": bool(edge_index in set(offsets.tolist())),
                }
            )
    _write_csv(output_dir / "phase7b4m_variable_edges.csv", edge_rows)

    centres = 0.5 * (edges[16][:-1] + edges[16][1:])
    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.4), constrained_layout=True)
    for values, label in (
        (error.log_temperature_error, "log T"),
        (error.log_opacity_error, "log opacity"),
        (error.hydrogen_ionized_error, "H II"),
        (error.helium_doubly_ionized_error, "He III"),
    ):
        axes[0, 0].semilogy(centres, values / PRODUCTION_TOLERANCE, marker="o", label=label)
    axes[0, 0].axhline(1.0, color="black", linestyle=":", label="target scale")
    axes[0, 0].set(
        xlabel="Parent-cell mass fraction",
        ylabel="Embedded defect / target",
        title="(a) Conservative restrict-prolong defect",
    )
    axes[0, 0].legend(fontsize=8)

    colors = np.where(error.helium_iii_half_front_encountered, "#d62728", "#1f77b4")
    axes[0, 1].bar(np.arange(PARENT_DEPTH_POINTS), error.normalized_indicator, color=colors)
    axes[0, 1].set_yscale("log")
    axes[0, 1].set(
        xlabel="Parent-cell index",
        ylabel="Maximum normalized defect",
        title="(b) Front-aware refinement ranking",
    )

    for level, count in enumerate((12, 14, 15, 16)):
        grid = grids[count]
        axes[1, 0].scatter(
            grid.mass_fraction_edges,
            np.full(grid.mass_fraction_edges.size, level),
            marker="|",
            s=90,
            label=f"N={grid.effective_depth_points}",
        )
    axes[1, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Refinement level",
        yticks=[],
        title="(c) Strictly nested variable grids",
    )
    axes[1, 0].legend(fontsize=8)

    effective = np.array([row["effective_depth_points"] for row in budget_rows])
    axes[1, 1].semilogy(
        effective,
        [
            row[
                "reference_assisted_representation_temperature_or_opacity_error"
            ]
            for row in budget_rows
        ],
        marker="o",
        label="T / opacity",
    )
    axes[1, 1].semilogy(
        effective,
        [row["reference_assisted_representation_population_error"] for row in budget_rows],
        marker="s",
        label="H II / He III",
    )
    axes[1, 1].axhline(PRODUCTION_TOLERANCE, color="black", linestyle=":", label="target")
    axes[1, 1].set(
        xlabel="Effective depth points",
        ylabel="Representation-only error",
        title="(d) Reference-assisted control only",
    )
    axes[1, 1].legend(fontsize=8)
    figure.suptitle("Phase 7B4m: embedded front-aware refinement", fontsize=14)
    figure.savefig(output_dir / "phase7b4m_embedded_refinement.png", dpi=180)
    plt.close(figure)

    report = {
        "phase": "7B4m-control",
        "classification": "[A/V] embedded conservative front-aware controls",
        "provenance": {
            "phase7b4l_profiles": profiles_path.name,
            "phase7b4l_edges": edges_path.name,
            "pilot_depth_points": PILOT_DEPTH_POINTS,
            "master_depth_points": MASTER_DEPTH_POINTS,
        },
        "configuration": {
            "parent_depth_points": PARENT_DEPTH_POINTS,
            "pilot_cells_per_parent": 2,
            "master_cells_per_parent": 4,
            "production_tolerance": PRODUCTION_TOLERANCE,
            "formal_refined_parent_counts": FORMAL_REFINED_PARENT_COUNTS,
            "selection_rule": (
                "refine the requested count of parent cells in descending embedded "
                "restrict-prolong defect; the count is the explicit resolution axis"
            ),
        },
        "diagnostics": {
            "maximum_parent_average_residual": error.maximum_parent_average_residual,
            "front_encountered_parent_count": int(
                np.sum(error.helium_iii_half_front_encountered)
            ),
            "highest_indicator_parent": int(error.descending_parent_order[0]),
            "highest_indicator": float(
                error.normalized_indicator[error.descending_parent_order[0]]
            ),
        },
        "decision": {
            "embedded_estimator_conservative": bool(
                error.maximum_parent_average_residual < CONSERVATION_TOLERANCE
            ),
            "all_formal_grids_preserve_pilot_edges": True,
            "reference_assisted_representation_is_a_control_not_a_gate": True,
            "dynamic_cases_required_before_spatial_decision": True,
        },
        "forbidden_repairs": {
            "nan_to_num": False,
            "arbitrary_clip": False,
            "arbitrary_floor": False,
            "failed_phase_deletion": False,
            "post_hoc_physical_renormalization": False,
        },
    }
    (output_dir / "phase7b4m_control_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["decision"], indent=2), flush=True)


def _coarsening_residuals(
    state: ConservativeCoarsenedGroundState,
) -> dict[str, float]:
    return {
        "initial_mass_residual": state.maximum_mass_residual,
        "initial_hydrogen_particle_residual": (
            state.maximum_hydrogen_particle_residual
        ),
        "initial_helium_particle_residual": state.maximum_helium_particle_residual,
        "initial_hydrogen_stage_absolute_residual": (
            state.maximum_hydrogen_stage_absolute_residual
        ),
        "initial_helium_stage_absolute_residual": (
            state.maximum_helium_stage_absolute_residual
        ),
        "initial_charge_residual": state.maximum_charge_residual,
        "initial_energy_residual": state.maximum_specific_energy_residual,
    }


def _restriction_residuals(
    restriction: ConservativeVariableSubcellRestriction,
) -> dict[str, float]:
    return {
        "restricted_mass_residual": restriction.maximum_parent_mass_residual,
        "restricted_hydrogen_particle_residual": (
            restriction.maximum_hydrogen_particle_residual
        ),
        "restricted_helium_particle_residual": (
            restriction.maximum_helium_particle_residual
        ),
        "restricted_hydrogen_stage_absolute_residual": (
            restriction.maximum_hydrogen_stage_absolute_residual
        ),
        "restricted_helium_stage_absolute_residual": (
            restriction.maximum_helium_stage_absolute_residual
        ),
        "restricted_charge_residual": restriction.maximum_charge_residual,
        "restricted_energy_residual": restriction.maximum_specific_energy_residual,
        "restricted_optical_depth_residual": (
            restriction.maximum_optical_depth_residual
        ),
        "restricted_flux_divergence_residual": (
            restriction.maximum_face_flux_divergence_residual
        ),
    }


def _case_paths(output_dir: Path, refined_parent_count: int) -> tuple[Path, Path]:
    stem = f"phase7b4m_case_refine{refined_parent_count:02d}"
    return output_dir / f"{stem}.npz", output_dir / f"{stem}.json"


def run_case(
    output_dir: Path,
    profiles_path: Path,
    edges_path: Path,
    refined_parent_count: int,
    *,
    force: bool,
) -> None:
    if refined_parent_count not in FORMAL_REFINED_PARENT_COUNTS:
        raise ValueError(
            f"formal refined_parent_count must be one of {FORMAL_REFINED_PARENT_COUNTS}"
        )
    npz_path, report_path = _case_paths(output_dir, refined_parent_count)
    if npz_path.exists() or report_path.exists():
        if not force:
            if not npz_path.exists() or not report_path.exists():
                raise FileExistsError("a partial Phase 7B4m case output already exists")
            print(f"reusing {report_path.name}", flush=True)
            return
        npz_path.unlink(missing_ok=True)
        report_path.unlink(missing_ok=True)
    edges = _saved_edges(edges_path)
    rows = _saved_field_rows(profiles_path)
    error = _estimator(edges, rows)
    variable = _variable_grid(error, edges[64], refined_parent_count)
    background = _background()
    frequency = _frequency()
    parent_grid = build_periodic_dynamic_half_column(
        background,
        PARENT_DEPTH_POINTS,
        "uniform_specific",
        mass_fraction_edges=edges[16],
    )
    master_grid = build_periodic_dynamic_half_column(
        background,
        MASTER_DEPTH_POINTS,
        "uniform_specific",
        mass_fraction_edges=edges[64],
    )
    variable_grid = build_periodic_dynamic_half_column(
        background,
        variable.effective_depth_points,
        "uniform_specific",
        mass_fraction_edges=variable.mass_fraction_edges,
    )
    parent_initial = _initial_state(background, parent_grid, frequency)
    master_initial = conservative_ground_state_subcells(
        parent_grid,
        master_grid,
        *parent_initial,
        4,
    )
    variable_initial = coarsen_ground_state_subcells(
        master_grid, variable_grid, master_initial
    )
    started = time.perf_counter()
    solution = solve_periodic_dynamic_column(
        variable_grid,
        frequency,
        variable_initial.temperature_k,
        variable_initial.hydrogen_fraction,
        variable_initial.helium_fraction,
        include_collisional_kinetics=False,
        minimum_temperature_k=MINIMUM_TEMPERATURE_K,
        maximum_temperature_k=MAXIMUM_TEMPERATURE_K,
        cycle_tolerance=CYCLE_TOLERANCE,
        local_energy_tolerance=2.0e-8,
        optimizer_tolerance=1.0e-10,
        maximum_function_evaluations=96,
        maximum_cycles=16,
    )
    runtime = time.perf_counter() - started
    restriction = restrict_periodic_dynamic_variable_subcells(
        parent_grid, solution
    )
    np.savez_compressed(
        npz_path,
        refined_parent_count=np.array(refined_parent_count),
        edges=variable.mass_fraction_edges,
        child_cells_per_parent=variable.child_cells_per_parent,
        refined_parent_mask=variable.refined_parent_mask,
        orbital_phase=(
            background.time_since_pericentre_s / background.orbital_period_s
        ),
        cell_mass_g_cm2=variable_grid.cell_mass_g_cm2,
        temperature_k=solution.temperature_k,
        opacity_cm2_g=solution.rosseland_opacity_cm2_g,
        hydrogen_fraction=solution.hydrogen_fraction,
        helium_fraction=solution.helium_fraction,
        surface_flux_erg_s_cm2=solution.outward_flux_edges_erg_s_cm2[:, 0],
    )
    residuals = {
        **_coarsening_residuals(variable_initial),
        **_restriction_residuals(restriction),
    }
    report = {
        "phase": "7B4m-case",
        "classification": "[A/V] front-aware variable-subcell dynamic case",
        "configuration": {
            "refined_parent_count": refined_parent_count,
            "effective_depth_points": variable.effective_depth_points,
            "phase_points": PHASE_POINTS,
            "frequency_points": int(frequency.size),
            "maximum_unrefined_indicator": variable.maximum_unrefined_indicator,
            "minimum_refined_indicator": variable.minimum_refined_indicator,
        },
        "runtime_s": runtime,
        "conservation": residuals,
        "solver": {
            "cycle_count": solution.cycle_count,
            "cycle_residual": solution.cycle_residual,
            "maximum_relative_local_energy_residual": (
                solution.maximum_relative_local_energy_residual
            ),
            "maximum_relative_charge_residual": (
                solution.maximum_relative_charge_residual
            ),
            "maximum_particle_conservation_residual": (
                solution.maximum_particle_conservation_residual
            ),
            "relative_cycle_energy_ledger_residual": (
                solution.relative_cycle_energy_ledger_residual
            ),
        },
        "decision": {
            "initial_and_restriction_conservation_passed": bool(
                max(residuals.values()) < CONSERVATION_TOLERANCE
            ),
            "case_is_not_a_spatial_reference_by_itself": True,
        },
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "refined_parent_count": refined_parent_count,
                "effective_depth_points": variable.effective_depth_points,
                "runtime_s": runtime,
                **report["decision"],
            },
            indent=2,
        ),
        flush=True,
    )


def _load_candidate(output_dir: Path, refined_parent_count: int) -> CandidateProfiles:
    npz_path, report_path = _case_paths(output_dir, refined_parent_count)
    if not npz_path.exists() or not report_path.exists():
        raise FileNotFoundError(
            f"Phase 7B4m case {refined_parent_count} must be completed before summary"
        )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    with np.load(npz_path) as data:
        return CandidateProfiles(
            refined_parent_count=refined_parent_count,
            edges=np.array(data["edges"], copy=True),
            orbital_phase=np.array(data["orbital_phase"], copy=True),
            temperature_k=np.array(data["temperature_k"], copy=True),
            opacity_cm2_g=np.array(data["opacity_cm2_g"], copy=True),
            hydrogen_fraction=np.array(data["hydrogen_fraction"], copy=True),
            helium_fraction=np.array(data["helium_fraction"], copy=True),
            surface_flux_erg_s_cm2=np.array(
                data["surface_flux_erg_s_cm2"], copy=True
            ),
            cell_mass_g_cm2=np.array(data["cell_mass_g_cm2"], copy=True),
            report=report,
        )


def _profile_rows(
    candidates: list[CandidateProfiles], reference: SavedProfiles
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    cases = [
        (
            f"adaptive_refine{candidate.refined_parent_count:02d}",
            candidate.edges,
            candidate.temperature_k,
            candidate.opacity_cm2_g,
            candidate.hydrogen_fraction[:, :, 1],
            candidate.helium_fraction[:, :, 2],
        )
        for candidate in candidates
    ]
    cases.append(
        (
            "phase7b4l_reference64",
            reference.edges,
            reference.temperature_k,
            reference.opacity_cm2_g,
            reference.h_ii,
            reference.he_iii,
        )
    )
    for name, edges, temperature, opacity, h_ii, he_iii in cases:
        centres = 0.5 * (edges[:-1] + edges[1:])
        for phase in range(PHASE_POINTS):
            for depth, mass in enumerate(centres):
                rows.append(
                    {
                        "case": name,
                        "effective_depth_points": centres.size,
                        "phase_index": phase,
                        "orbital_phase": float(reference.orbital_phase[phase]),
                        "depth_index": depth,
                        "mass_fraction_centre": float(mass),
                        "temperature_k": float(temperature[phase, depth]),
                        "rosseland_opacity_cm2_g": float(opacity[phase, depth]),
                        "hydrogen_ionized_fraction": float(h_ii[phase, depth]),
                        "helium_doubly_ionized_fraction": float(
                            he_iii[phase, depth]
                        ),
                    }
                )
    return rows


def _plot_summary(
    path: Path,
    candidates: list[CandidateProfiles],
    reference: SavedProfiles,
    convergence_rows: list[dict[str, object]],
    target_flux: np.ndarray,
) -> int:
    reference_mass = 0.5 * (reference.edges[:-1] + reference.edges[1:])
    gradients = np.max(
        np.abs(np.gradient(reference.he_iii, reference_mass, axis=1)), axis=1
    )
    selected_phase = int(np.argmax(gradients))
    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.4), constrained_layout=True)
    for candidate in candidates:
        mass = 0.5 * (candidate.edges[:-1] + candidate.edges[1:])
        axes[0, 0].plot(
            mass,
            candidate.helium_fraction[selected_phase, :, 2],
            marker="o",
            markersize=2.5,
            label=f"N={mass.size}",
        )
    axes[0, 0].plot(
        reference_mass,
        reference.he_iii[selected_phase],
        color="black",
        linewidth=1.5,
        label="N=64 reference",
    )
    axes[0, 0].axhline(0.5, color="gray", linestyle=":")
    axes[0, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="He III fraction",
        title=f"(a) Strongest front at phase index {selected_phase}",
    )
    axes[0, 0].legend(fontsize=8)

    for candidate in candidates:
        axes[0, 1].plot(
            candidate.orbital_phase,
            candidate.surface_flux_erg_s_cm2 / target_flux,
            label=f"N={candidate.edges.size - 1}",
        )
    axes[0, 1].plot(
        reference.orbital_phase,
        reference.surface_flux_erg_s_cm2 / target_flux,
        color="black",
        linewidth=1.5,
        label="N=64 reference",
    )
    axes[0, 1].set(
        xlabel="Orbital time phase",
        ylabel="Emergent / instantaneous ZO flux",
        title="(b) Surface-flux response",
    )
    axes[0, 1].legend(fontsize=8)

    x = np.array([row["effective_depth_points"] for row in convergence_rows])
    axes[1, 0].semilogy(
        x,
        [
            row["maximum_pointwise_temperature_or_opacity_relative_error"]
            for row in convergence_rows
        ],
        marker="o",
        label="T / opacity",
    )
    axes[1, 0].semilogy(
        x,
        [row["maximum_pointwise_population_absolute_error"] for row in convergence_rows],
        marker="s",
        label="H II / He III",
    )
    axes[1, 0].axhline(PRODUCTION_TOLERANCE, color="black", linestyle=":", label="target")
    axes[1, 0].set(
        xlabel="Effective depth points",
        ylabel="Maximum pointwise error",
        title="(c) Local-state convergence",
    )
    axes[1, 0].legend(fontsize=8)

    for key, label, marker in (
        (
            "surface_flux_relative_error",
            "Surface flux",
            "D",
        ),
        (
            "maximum_column_mean_temperature_or_opacity_relative_error",
            "Column T / opacity",
            "o",
        ),
        (
            "maximum_column_mean_population_absolute_error",
            "Column H II / He III",
            "s",
        ),
        (
            "maximum_he_iii_half_front_mass_fraction_error",
            "He III front",
            "^",
        ),
    ):
        axes[1, 1].semilogy(
            x,
            [row[key] for row in convergence_rows],
            marker=marker,
            label=label,
        )
    axes[1, 1].axhline(PRODUCTION_TOLERANCE, color="black", linestyle=":", label="target")
    axes[1, 1].set(
        xlabel="Effective depth points",
        ylabel="Maximum error",
        title="(d) Integrated and front convergence",
    )
    axes[1, 1].legend(fontsize=8)
    figure.suptitle("Phase 7B4m: front-aware variable-depth convergence", fontsize=14)
    figure.savefig(path, dpi=180)
    plt.close(figure)
    return selected_phase


def run_summary(
    output_dir: Path,
    profiles_path: Path,
    edges_path: Path,
) -> None:
    control_path = output_dir / "phase7b4m_control_report.json"
    if not control_path.exists():
        raise FileNotFoundError("Phase 7B4m control stage must run before summary")
    edges = _saved_edges(edges_path)
    rows = _saved_field_rows(profiles_path)
    error = _estimator(edges, rows)
    background = _background()
    reference = _reference_profiles(background, edges, rows)
    reference_report_path = output_dir / "phase7b4l_subcell_report.json"
    reference_runtime_s = _reference_runtime_s(reference_report_path)
    candidates = [
        _load_candidate(output_dir, count)
        for count in FORMAL_REFINED_PARENT_COUNTS
    ]
    convergence_rows = []
    candidate_residual_rows = []
    for candidate in candidates:
        comparison = _comparison(candidate, reference)
        case_report = candidate.report
        conservation_passed = bool(
            case_report["decision"][
                "initial_and_restriction_conservation_passed"
            ]
        )
        meets_spatial_target = bool(
            all(
                float(comparison[key]) < PRODUCTION_TOLERANCE
                for key in SPATIAL_GATE_KEYS
            )
            and int(comparison["front_status_mismatch_phase_count"]) == 0
            and conservation_passed
        )
        convergence_rows.append(
            {
                "case": f"adaptive_refine{candidate.refined_parent_count:02d}",
                "refined_parent_count": candidate.refined_parent_count,
                "effective_depth_points": candidate.edges.size - 1,
                "runtime_s": case_report["runtime_s"],
                "reference_runtime_s": reference_runtime_s,
                "reference_runtime_over_candidate": (
                    reference_runtime_s / float(case_report["runtime_s"])
                ),
                **comparison,
                "cycle_residual": case_report["solver"]["cycle_residual"],
                "energy_ledger_residual": case_report["solver"][
                    "relative_cycle_energy_ledger_residual"
                ],
                "conservation_passed": conservation_passed,
                "meets_spatial_target": meets_spatial_target,
            }
        )
        actual = _parent_actual_errors(candidate, reference, edges[16])
        for parent in range(PARENT_DEPTH_POINTS):
            candidate_residual_rows.append(
                {
                    "refined_parent_count": candidate.refined_parent_count,
                    "effective_depth_points": candidate.edges.size - 1,
                    "parent_index": parent,
                    "embedded_normalized_indicator": float(
                        error.normalized_indicator[parent]
                    ),
                    "actual_normalized_error_against_reference64": float(
                        actual[parent]
                    ),
                    "refined": bool(
                        parent
                        in error.descending_parent_order[
                            : candidate.refined_parent_count
                        ]
                    ),
                }
            )
    pilot = rows[PILOT_DEPTH_POINTS]
    pilot_actual = _parent_field_errors(
        edges[PILOT_DEPTH_POINTS],
        (
            _profile_array(pilot, "temperature_k", PILOT_DEPTH_POINTS),
            _profile_array(
                pilot, "rosseland_opacity_cm2_g", PILOT_DEPTH_POINTS
            ),
            _profile_array(
                pilot, "hydrogen_ionized_fraction", PILOT_DEPTH_POINTS
            ),
            _profile_array(
                pilot,
                "helium_doubly_ionized_fraction",
                PILOT_DEPTH_POINTS,
            ),
        ),
        reference,
        edges[PARENT_DEPTH_POINTS],
    )
    embedded_rank = np.empty(PARENT_DEPTH_POINTS, dtype=np.int64)
    embedded_rank[error.descending_parent_order] = np.arange(
        1, PARENT_DEPTH_POINTS + 1
    )
    pilot_order = np.argsort(-pilot_actual, kind="stable")
    pilot_rank = np.empty(PARENT_DEPTH_POINTS, dtype=np.int64)
    pilot_rank[pilot_order] = np.arange(1, PARENT_DEPTH_POINTS + 1)
    validation_rows = [
        {
            "parent_index": parent,
            "embedded_normalized_indicator": float(
                error.normalized_indicator[parent]
            ),
            "embedded_descending_rank": int(embedded_rank[parent]),
            "pilot32_actual_normalized_error_against_reference64": float(
                pilot_actual[parent]
            ),
            "pilot_actual_descending_rank": int(pilot_rank[parent]),
        }
        for parent in range(PARENT_DEPTH_POINTS)
    ]
    _write_csv(output_dir / "phase7b4m_convergence.csv", convergence_rows)
    _write_csv(
        output_dir / "phase7b4m_estimator_validation.csv", validation_rows
    )
    _write_csv(
        output_dir / "phase7b4m_candidate_parent_residuals.csv",
        candidate_residual_rows,
    )
    _write_csv(
        output_dir / "phase7b4m_profiles.csv",
        _profile_rows(candidates, reference),
    )
    target_flux = background.one_face_surface_flux_erg_s_cm2
    selected_phase = _plot_summary(
        output_dir / "phase7b4m_variable_convergence.png",
        candidates,
        reference,
        convergence_rows,
        target_flux,
    )
    highest = convergence_rows[-1]
    spatial_pass = bool(highest["meets_spatial_target"])
    first_passing = next(
        (
            int(row["effective_depth_points"])
            for row in convergence_rows
            if bool(row["meets_spatial_target"])
        ),
        None,
    )
    all_metrics_monotone = all(
        all(
            float(right[key]) <= float(left[key])
            for left, right in zip(
                convergence_rows[:-1], convergence_rows[1:], strict=True
            )
        )
        for key in SPATIAL_GATE_KEYS
    )
    time_report_path = output_dir / "phase7b4k_time_report.json"
    if not time_report_path.exists():
        raise FileNotFoundError("Phase 7B4k time report is required")
    time_report = json.loads(time_report_path.read_text(encoding="utf-8"))
    time_pass = bool(
        time_report["decision"]["time_1024_production_converged_against_2048"]
    )
    pilot_correlation = spearmanr(error.normalized_indicator, pilot_actual)
    report = {
        "phase": "7B4m-complete",
        "classification": "[A/V/O] front-aware variable-subcell spatial gate",
        "provenance": {
            "phase7b4l_profiles": profiles_path.name,
            "phase7b4l_edges": edges_path.name,
            "phase7b4l_reference_report": reference_report_path.name,
            "phase7b4k_time_report": time_report_path.name,
            "reference_64_is_a_finite_resolution_reference": True,
        },
        "configuration": {
            "parent_depth_points": PARENT_DEPTH_POINTS,
            "pilot_depth_points": PILOT_DEPTH_POINTS,
            "master_depth_points": MASTER_DEPTH_POINTS,
            "formal_refined_parent_counts": FORMAL_REFINED_PARENT_COUNTS,
            "production_tolerance": PRODUCTION_TOLERANCE,
            "selected_front_phase_index": selected_phase,
        },
        "convergence": convergence_rows,
        "estimator_rank_validation": {
            "pilot32_against_finite_reference64": {
                "spearman_r": float(pilot_correlation.statistic),
                "p_value": float(pilot_correlation.pvalue),
            },
            "post_refinement_candidate_residuals_are_not_used_for_rank_validation": True,
        },
        "decision": {
            "embedded_estimator_control_passed": True,
            "all_variable_cases_conserve": all(
                bool(row["conservation_passed"]) for row in convergence_rows
            ),
            "first_tested_passing_effective_depth_points": first_passing,
            "all_gate_metrics_monotone_nonincreasing": all_metrics_monotone,
            "adaptive_62_converged_against_reference_64": spatial_pass,
            "time_1024_production_converged_against_2048": time_pass,
            "joint_64_depth_1024_phase_run_authorized": spatial_pass and time_pass,
            "joint_depth_time_reference_completed": False,
            "nonlocal_dynamic_transfer_authorized": False,
            "phase4_atmosphere_replacement_authorized": False,
            "uvot_authorized": False,
            "next_microphase_if_spatial_passes": (
                "joint 64-depth, 1024-phase periodic dynamic run with a coupled "
                "depth-time convergence audit"
            ),
            "next_microphase_if_spatial_fails": (
                "raise the master spatial reference or add a higher-order conservative "
                "front representation before any nonlocal transfer"
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
    (output_dir / "phase7b4m_complete_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["decision"], indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--profiles",
        type=Path,
        default=Path("outputs/phase7b4l_subcell_profiles.csv"),
    )
    parser.add_argument(
        "--edges",
        type=Path,
        default=Path("outputs/phase7b4l_subcell_edges.csv"),
    )
    parser.add_argument(
        "--stage",
        choices=("control", "case", "cases", "summary", "all"),
        default="all",
    )
    parser.add_argument("--refined-parent-count", type=int)
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if arguments.stage in ("control", "all"):
        run_control(arguments.output_dir, arguments.profiles, arguments.edges)
    if arguments.stage == "case":
        if arguments.refined_parent_count is None:
            parser.error("--stage case requires --refined-parent-count")
        run_case(
            arguments.output_dir,
            arguments.profiles,
            arguments.edges,
            arguments.refined_parent_count,
            force=arguments.force,
        )
    if arguments.stage in ("cases", "all"):
        for count in FORMAL_REFINED_PARENT_COUNTS:
            run_case(
                arguments.output_dir,
                arguments.profiles,
                arguments.edges,
                count,
                force=arguments.force,
            )
    if arguments.stage in ("summary", "all"):
        run_summary(arguments.output_dir, arguments.profiles, arguments.edges)


if __name__ == "__main__":
    main()
