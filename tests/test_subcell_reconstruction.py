from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

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
    ground_state_thermodynamics,
    solve_periodic_dynamic_column,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model
from eccentric_tde_observer.source import PhysicalDomainError
from eccentric_tde_observer.subcell_reconstruction import (
    conservative_ground_state_subcells,
    conservative_linear_subcell_values,
    ground_state_temperature_from_specific_energy_k,
    restrict_periodic_dynamic_subcells,
    uniform_mass_subcell_edges,
)


def _small_parent_and_subcell_grids(parent_points: int = 3):
    model = build_strict_domain_reference_model(17, 16)
    background = build_zo_periodic_column_background(model, 2)
    parent = build_periodic_dynamic_half_column(
        background, parent_points, "uniform_specific"
    )
    subcell_edges = uniform_mass_subcell_edges(parent.mass_fraction_edges, 2)
    subcell = build_periodic_dynamic_half_column(
        background,
        2 * parent_points,
        "uniform_specific",
        mass_fraction_edges=subcell_edges,
    )
    return background, parent, subcell


def _lte_parent_initial_state(background, parent, frequency):
    column = build_zo_constrained_n3_column(
        float(background.one_sided_column_mass_g_cm2[0]),
        float(background.scale_height_cm[0]),
        float(background.pressure_gravity_coefficient_s2[0]),
        parent.half_depth_points,
        mass_fraction_edges=parent.mass_fraction_edges,
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
    temperature = np.array(
        static.full_temperature_k[: parent.half_depth_points], copy=True
    )
    lte = lte_hydrogen_helium_ionization(
        parent.density_g_cm3[0], temperature
    )
    hydrogen = np.column_stack(
        (lte.hydrogen_neutral_fraction, lte.hydrogen_ionized_fraction)
    )
    helium = np.column_stack(
        (
            lte.helium_neutral_fraction,
            lte.helium_singly_ionized_fraction,
            lte.helium_doubly_ionized_fraction,
        )
    )
    return temperature, hydrogen, helium


def test_linear_subcells_recover_parent_averages_and_a_linear_field() -> None:
    edges = np.array([0.0, 0.08, 0.25, 0.55, 1.0])
    centres = 0.5 * (edges[:-1] + edges[1:])
    parent = np.column_stack((2.0 + 3.0 * centres, 0.2 + 0.4 * centres))
    local_fraction = np.array([0.0, 0.15, 0.55, 0.85, 1.0])
    pieces = []
    for index, (left, right) in enumerate(zip(edges[:-1], edges[1:], strict=True)):
        local = left + (right - left) * local_fraction
        local[0] = left
        local[-1] = right
        pieces.append(local if index == 0 else local[1:])
    subcell_edges = np.concatenate(pieces)
    reconstructed = conservative_linear_subcell_values(
        parent,
        edges,
        4,
        subcell_mass_fraction_edges=subcell_edges,
        lower_bound=0.0,
    )
    expected = np.column_stack(
        (
            2.0 + 3.0 * reconstructed.subcell_mass_fraction_centres,
            0.2 + 0.4 * reconstructed.subcell_mass_fraction_centres,
        )
    )
    assert np.allclose(reconstructed.values, expected, rtol=6.0e-16)
    assert reconstructed.maximum_parent_average_residual < 3.0e-16
    assert np.all(reconstructed.limiter_fraction == 1.0)
    assert np.array_equal(
        reconstructed.subcell_mass_fraction_edges[::4], edges
    )


def test_limited_subcells_improve_a_manufactured_moving_ionization_front() -> None:
    edges = np.linspace(0.0, 1.0, 9)
    constant_error: list[float] = []
    reconstructed_error: list[float] = []
    for front in np.linspace(0.15, 0.85, 8):
        width = 0.08

        def antiderivative(x):
            return 0.5 * (
                x - width * np.log(np.cosh((x - front) / width))
            )

        parent_average = (
            antiderivative(edges[1:]) - antiderivative(edges[:-1])
        ) / np.diff(edges)
        reconstructed = conservative_linear_subcell_values(
            parent_average, edges, 4, lower_bound=0.0, upper_bound=1.0
        )
        exact = 0.5 * (
            1.0
            - np.tanh(
                (reconstructed.subcell_mass_fraction_centres - front) / width
            )
        )
        constant_error.extend(np.abs(np.repeat(parent_average, 4) - exact))
        reconstructed_error.extend(np.abs(reconstructed.values - exact))
        assert reconstructed.maximum_parent_average_residual < 4.0e-16
        assert np.all(reconstructed.values >= 0.0)
        assert np.all(reconstructed.values <= 1.0)
    assert np.mean(reconstructed_error) < 0.55 * np.mean(constant_error)
    assert np.max(reconstructed_error) < 0.55 * np.max(constant_error)


def test_ground_state_specific_energy_temperature_inversion_round_trip() -> None:
    density = np.array([1.0e-10, 5.0e-9, 2.0e-7])
    temperature = np.array([1.2e4, 4.0e4, 1.1e5])
    hydrogen = np.array([[0.9, 0.1], [0.3, 0.7], [0.01, 0.99]])
    helium = np.array(
        [[0.85, 0.1, 0.05], [0.2, 0.5, 0.3], [0.01, 0.09, 0.9]]
    )
    energy = ground_state_thermodynamics(
        density, temperature, hydrogen, helium
    ).specific_total_energy_erg_g
    recovered = ground_state_temperature_from_specific_energy_k(
        density, energy, hydrogen, helium
    )
    assert np.allclose(recovered, temperature, rtol=2.0e-15)
    with pytest.raises(PhysicalDomainError, match="thermal energy"):
        ground_state_temperature_from_specific_energy_k(
            density,
            np.zeros_like(energy),
            hydrogen,
            helium,
        )


def test_ground_state_subcell_prolongation_conserves_all_parent_totals() -> None:
    _, parent, subcell = _small_parent_and_subcell_grids(4)
    temperature = np.array([2.0e4, 3.0e4, 5.0e4, 8.0e4])
    h_ii = np.array([0.1, 0.3, 0.7, 0.9])
    hydrogen = np.column_stack((1.0 - h_ii, h_ii))
    he_ii = np.array([0.1, 0.2, 0.25, 0.15])
    he_iii = np.array([0.05, 0.2, 0.5, 0.8])
    helium = np.column_stack((1.0 - he_ii - he_iii, he_ii, he_iii))
    state = conservative_ground_state_subcells(
        parent, subcell, temperature, hydrogen, helium, 2
    )
    assert state.maximum_parent_mass_residual == 0.0
    assert state.maximum_hydrogen_particle_residual < 4.0e-15
    assert state.maximum_helium_particle_residual < 4.0e-15
    assert state.maximum_hydrogen_stage_absolute_residual < 4.0e-15
    assert state.maximum_helium_stage_absolute_residual < 4.0e-15
    assert state.maximum_charge_residual < 4.0e-15
    assert state.maximum_specific_energy_residual < 4.0e-15
    assert np.all(state.temperature_k > 0.0)
    assert np.all(state.hydrogen_fraction >= 0.0)
    assert np.all(state.helium_fraction >= 0.0)
    assert np.allclose(np.sum(state.hydrogen_fraction, axis=1), 1.0)
    assert np.allclose(np.sum(state.helium_fraction, axis=1), 1.0)


def test_dynamic_subcell_restriction_preserves_particles_energy_and_fluxes() -> None:
    background, parent, subcell = _small_parent_and_subcell_grids(3)
    frequency = (
        edge_resolved_milne_energy_grid_ev(0.1, 5000.0, 17)
        * EV_ERG
        / PLANCK_ERG_S
    )
    parent_initial = _lte_parent_initial_state(background, parent, frequency)
    initial = conservative_ground_state_subcells(
        parent, subcell, *parent_initial, 2
    )
    solution = solve_periodic_dynamic_column(
        subcell,
        frequency,
        initial.temperature_k,
        initial.hydrogen_fraction,
        initial.helium_fraction,
        minimum_temperature_k=2000.0,
        maximum_temperature_k=2.0e6,
        cycle_tolerance=1.0e-6,
        local_energy_tolerance=2.0e-6,
        maximum_cycles=8,
    )
    restricted = restrict_periodic_dynamic_subcells(parent, solution, 2)
    assert solution.relative_cycle_energy_ledger_residual < 3.0e-10
    assert restricted.maximum_parent_mass_residual == 0.0
    assert restricted.maximum_hydrogen_particle_residual < 4.0e-15
    assert restricted.maximum_helium_particle_residual < 4.0e-15
    assert restricted.maximum_hydrogen_stage_absolute_residual < 4.0e-15
    assert restricted.maximum_helium_stage_absolute_residual < 4.0e-15
    assert restricted.maximum_charge_residual < 4.0e-15
    assert restricted.maximum_specific_energy_residual < 4.0e-15
    assert restricted.maximum_optical_depth_residual < 4.0e-15
    assert restricted.maximum_face_flux_divergence_residual < 4.0e-15
    assert np.all(
        restricted.parent_outward_flux_edges_erg_s_cm2[:, -1] == 0.0
    )


def test_subcell_module_uses_no_forbidden_numerical_repairs() -> None:
    source = Path(
        "src/eccentric_tde_observer/subcell_reconstruction.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("nan_to_num", "np.clip", "numpy.clip"):
        assert forbidden not in source
