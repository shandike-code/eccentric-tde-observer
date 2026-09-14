from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.adaptive_subcell_refinement import (
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
    build_periodic_dynamic_half_column,
    solve_periodic_dynamic_column,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model
from eccentric_tde_observer.source import PhysicalDomainError
from eccentric_tde_observer.subcell_reconstruction import (
    coarsen_ground_state_subcells,
    conservative_ground_state_subcells,
    nested_mass_cell_offsets,
    restrict_periodic_dynamic_variable_subcells,
)


def _nested_edges(parent_edges: np.ndarray, children: int) -> np.ndarray:
    pieces = []
    for index, (left, right) in enumerate(
        zip(parent_edges[:-1], parent_edges[1:], strict=True)
    ):
        local = np.linspace(left, right, children + 1)
        pieces.append(local if index == 0 else local[1:])
    return np.concatenate(pieces)


def test_embedded_error_tracks_a_moving_front_and_builds_nested_budgets() -> None:
    parent_edges = np.linspace(0.0, 1.0, 9)
    pilot_edges = _nested_edges(parent_edges, 2)
    master_edges = _nested_edges(parent_edges, 4)
    centres = 0.5 * (pilot_edges[:-1] + pilot_edges[1:])
    fronts = np.linspace(0.28, 0.58, 17)
    he_iii = np.array(
        [0.5 * (1.0 - np.tanh((centres - front) / 0.055)) for front in fronts]
    )
    temperature = 2.5e4 * np.exp(0.18 * he_iii)
    opacity = 0.3 * np.exp(-0.12 * he_iii)
    h_ii = 0.92 + 0.04 * he_iii
    error = embedded_conservative_parent_error(
        parent_edges,
        pilot_edges,
        temperature,
        opacity,
        h_ii,
        he_iii,
    )
    assert error.maximum_parent_average_residual < 5.0e-16
    assert error.helium_iii_half_front_encountered[error.descending_parent_order[0]]
    assert np.all(error.normalized_indicator >= 0.0)

    budget = front_aware_variable_subcell_grid(error, master_edges, 3)
    assert budget.effective_depth_points == 22
    assert np.array_equal(
        np.flatnonzero(budget.refined_parent_mask),
        np.sort(error.descending_parent_order[:3]),
    )
    assert np.all(budget.child_cells_per_parent[budget.refined_parent_mask] == 4)
    assert np.all(budget.child_cells_per_parent[~budget.refined_parent_mask] == 2)
    nested_mass_cell_offsets(pilot_edges, budget.mass_fraction_edges)

    full = front_aware_variable_subcell_grid(error, master_edges, 8)
    assert np.array_equal(full.mass_fraction_edges, master_edges)
    with pytest.raises(PhysicalDomainError, match="between zero"):
        front_aware_variable_subcell_grid(error, master_edges, 9)


def test_nested_offsets_reject_a_missing_parent_edge() -> None:
    with pytest.raises(PhysicalDomainError, match="preserve every parent edge"):
        nested_mass_cell_offsets(
            np.array([0.0, 0.4, 1.0]),
            np.array([0.0, 0.2, 0.6, 1.0]),
        )


def test_variable_subcell_initial_state_and_dynamic_restriction_conserve() -> None:
    model = build_strict_domain_reference_model(17, 16)
    background = build_zo_periodic_column_background(model, 2)
    parent_edges = np.array([0.0, 0.12, 0.44, 1.0])
    master_edges = _nested_edges(parent_edges, 4)
    pilot_edges = master_edges[::2]
    variable_edges = np.concatenate(
        (master_edges[:5], pilot_edges[3:])
    )
    parent = build_periodic_dynamic_half_column(
        background,
        3,
        "uniform_specific",
        mass_fraction_edges=parent_edges,
    )
    master = build_periodic_dynamic_half_column(
        background,
        12,
        "uniform_specific",
        mass_fraction_edges=master_edges,
    )
    variable = build_periodic_dynamic_half_column(
        background,
        variable_edges.size - 1,
        "uniform_specific",
        mass_fraction_edges=variable_edges,
    )
    frequency = (
        edge_resolved_milne_energy_grid_ev(0.1, 5000.0, 17)
        * EV_ERG
        / PLANCK_ERG_S
    )
    column = build_zo_constrained_n3_column(
        float(background.one_sided_column_mass_g_cm2[0]),
        float(background.scale_height_cm[0]),
        float(background.pressure_gravity_coefficient_s2[0]),
        3,
        mass_fraction_edges=parent_edges,
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
        relative_tolerance=1.0e-5,
    )
    temperature = np.array(static.full_temperature_k[:3], copy=True)
    ionization = lte_hydrogen_helium_ionization(
        parent.density_g_cm3[0], temperature
    )
    hydrogen = np.column_stack(
        (ionization.hydrogen_neutral_fraction, ionization.hydrogen_ionized_fraction)
    )
    helium = np.column_stack(
        (
            ionization.helium_neutral_fraction,
            ionization.helium_singly_ionized_fraction,
            ionization.helium_doubly_ionized_fraction,
        )
    )
    master_state = conservative_ground_state_subcells(
        parent, master, temperature, hydrogen, helium, 4
    )
    variable_state = coarsen_ground_state_subcells(
        master, variable, master_state
    )
    assert np.array_equal(variable_state.source_cells_per_coarsened_cell, [1, 1, 1, 1, 2, 2, 2, 2])
    for residual in (
        variable_state.maximum_mass_residual,
        variable_state.maximum_hydrogen_particle_residual,
        variable_state.maximum_helium_particle_residual,
        variable_state.maximum_hydrogen_stage_absolute_residual,
        variable_state.maximum_helium_stage_absolute_residual,
        variable_state.maximum_charge_residual,
        variable_state.maximum_specific_energy_residual,
    ):
        assert residual < 4.0e-15

    solution = solve_periodic_dynamic_column(
        variable,
        frequency,
        variable_state.temperature_k,
        variable_state.hydrogen_fraction,
        variable_state.helium_fraction,
        minimum_temperature_k=2000.0,
        maximum_temperature_k=2.0e6,
        cycle_tolerance=1.0e-6,
        local_energy_tolerance=2.0e-6,
        maximum_cycles=8,
    )
    restricted = restrict_periodic_dynamic_variable_subcells(parent, solution)
    assert np.array_equal(restricted.child_cells_per_parent, [4, 2, 2])
    for residual in (
        restricted.maximum_parent_mass_residual,
        restricted.maximum_hydrogen_particle_residual,
        restricted.maximum_helium_particle_residual,
        restricted.maximum_hydrogen_stage_absolute_residual,
        restricted.maximum_helium_stage_absolute_residual,
        restricted.maximum_charge_residual,
        restricted.maximum_specific_energy_residual,
        restricted.maximum_optical_depth_residual,
        restricted.maximum_face_flux_divergence_residual,
    ):
        assert residual < 4.0e-15


def test_adaptive_subcell_code_uses_no_forbidden_repairs() -> None:
    source = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "src/eccentric_tde_observer/adaptive_subcell_refinement.py",
            "src/eccentric_tde_observer/subcell_reconstruction.py",
        )
    )
    for forbidden in ("nan_to_num", "np.clip", "numpy.clip"):
        assert forbidden not in source
