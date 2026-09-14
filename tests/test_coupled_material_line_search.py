import numpy as np
import pytest

from eccentric_tde_observer.coupled_material_line_search import (
    protected_residual_line_search_material_step,
)
from eccentric_tde_observer.source import PhysicalDomainError


def _states():
    current_temperature = np.array([1.0e4, 2.0e4])
    endpoint_temperature = np.array([1.2e4, 2.4e4])
    current_hydrogen = np.array([[0.8, 0.2], [0.6, 0.4]])
    endpoint_hydrogen = np.array([[0.7, 0.3], [0.5, 0.5]])
    current_helium = np.array([[0.7, 0.2, 0.1], [0.5, 0.3, 0.2]])
    endpoint_helium = np.array([[0.6, 0.25, 0.15], [0.4, 0.35, 0.25]])
    return (
        current_temperature,
        current_hydrogen,
        current_helium,
        endpoint_temperature,
        endpoint_hydrogen,
        endpoint_helium,
    )


def test_residual_line_search_selects_best_preregistered_feasible_candidate():
    step = protected_residual_line_search_material_step(
        *_states(),
        np.array([-1.0, 0.5]),
        np.array([1.0, 0.1]),
        np.ones(2),
        np.ones(2),
        np.ones(2),
        candidate_relaxations=(0.25, 0.5, 0.75),
        maximum_predicted_mass_weighted_contraction=0.8,
        maximum_predicted_limiting_cell_contraction=0.8,
        maximum_predicted_maximum_cell_contraction=0.8,
    )
    assert step.relaxation == 0.5
    assert step.predicted_mass_weighted_contraction < 0.8
    assert step.predicted_limiting_cell_contraction < 0.8
    assert step.predicted_maximum_cell_contraction < 0.8
    assert step.maximum_relative_energy_residual < 1.0e-14


def test_residual_line_search_convex_state_preserves_simplexes_without_clipping():
    step = protected_residual_line_search_material_step(
        *_states(),
        np.array([-1.0, 0.5]),
        np.array([1.0, 0.1]),
        np.ones(2),
        np.ones(2),
        np.ones(2),
        candidate_relaxations=(0.5,),
        maximum_predicted_mass_weighted_contraction=0.8,
        maximum_predicted_limiting_cell_contraction=0.8,
        maximum_predicted_maximum_cell_contraction=0.8,
    )
    np.testing.assert_allclose(np.sum(step.hydrogen_fraction, axis=1), 1.0)
    np.testing.assert_allclose(np.sum(step.helium_fraction, axis=1), 1.0)
    assert step.minimum_population_fraction >= 0.0
    assert step.maximum_particle_conservation_residual < 1.0e-14


def test_residual_line_search_rejects_when_no_fixed_candidate_passes():
    with pytest.raises(PhysicalDomainError, match="no preregistered"):
        protected_residual_line_search_material_step(
            *_states(),
            np.array([-1.0, 0.5]),
            np.array([-2.0, 1.0]),
            np.ones(2),
            np.ones(2),
            np.ones(2),
            candidate_relaxations=(0.25, 0.5, 0.75),
            maximum_predicted_mass_weighted_contraction=0.9,
            maximum_predicted_limiting_cell_contraction=0.9,
            maximum_predicted_maximum_cell_contraction=0.9,
        )
