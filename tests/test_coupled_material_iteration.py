import numpy as np

from eccentric_tde_observer.coupled_material_iteration import (
    damped_coupled_material_iteration,
)
from eccentric_tde_observer.radiation_matter_feedback import (
    FrozenRadiationMaterialResponse,
    ground_state_material_specific_energy_erg_g,
)


def _candidate(
    initial_temperature,
    initial_hydrogen,
    initial_helium,
    candidate_temperature,
    candidate_hydrogen,
    candidate_helium,
):
    initial_energy = ground_state_material_specific_energy_erg_g(
        initial_temperature, initial_hydrogen, initial_helium
    )
    candidate_energy = ground_state_material_specific_energy_erg_g(
        candidate_temperature, candidate_hydrogen, candidate_helium
    )
    return FrozenRadiationMaterialResponse(
        temperature_k=np.asarray(candidate_temperature),
        hydrogen_fraction=np.asarray(candidate_hydrogen),
        helium_fraction=np.asarray(candidate_helium),
        electron_density_cm3=np.ones(len(initial_temperature)),
        initial_specific_material_energy_erg_g=np.asarray(initial_energy),
        target_specific_material_energy_erg_g=np.asarray(candidate_energy),
        recovered_specific_material_energy_erg_g=np.asarray(candidate_energy),
        maximum_relative_temperature_change=0.0,
        maximum_population_fraction_change=0.0,
        maximum_relative_energy_residual=0.0,
        maximum_relative_charge_residual=0.0,
        maximum_particle_conservation_residual=0.0,
        minimum_population_fraction=0.0,
    )


def test_coupled_iteration_uses_current_iterate_not_physical_old_energy():
    old_temperature = np.array([1.0e4])
    current_temperature = np.array([1.2e4])
    candidate_temperature = np.array([1.25e4])
    hydrogen = np.array([[0.7, 0.3]])
    helium = np.array([[0.6, 0.3, 0.1]])
    candidate = _candidate(
        old_temperature,
        hydrogen,
        helium,
        candidate_temperature,
        hydrogen,
        helium,
    )
    step = damped_coupled_material_iteration(
        current_temperature,
        hydrogen,
        helium,
        candidate,
        maximum_relative_temperature_change=0.1,
        maximum_absolute_material_energy_increment_fraction=0.1,
    )
    assert step.relaxation == 1.0
    np.testing.assert_allclose(step.temperature_k, candidate_temperature)
    current_energy = ground_state_material_specific_energy_erg_g(
        current_temperature, hydrogen, helium
    )
    np.testing.assert_allclose(
        step.current_specific_material_energy_erg_g, current_energy
    )


def test_coupled_iteration_respects_energy_trust_without_clipping():
    temperature = np.array([1.0e4, 2.0e4])
    hydrogen = np.array([[0.8, 0.2], [0.6, 0.4]])
    helium = np.array([[0.7, 0.2, 0.1], [0.5, 0.3, 0.2]])
    candidate = _candidate(
        temperature,
        hydrogen,
        helium,
        2.0 * temperature,
        hydrogen,
        helium,
    )
    step = damped_coupled_material_iteration(
        temperature,
        hydrogen,
        helium,
        candidate,
        maximum_relative_temperature_change=0.2,
        maximum_absolute_material_energy_increment_fraction=0.05,
    )
    assert 0.0 < step.relaxation < 1.0
    assert step.maximum_absolute_material_energy_increment_fraction <= 0.05
    assert step.maximum_relative_temperature_change <= 0.2
    assert step.maximum_relative_energy_residual < 1.0e-14


def test_coupled_iteration_preserves_population_simplex():
    temperature = np.array([1.0e4])
    hydrogen = np.array([[0.9, 0.1]])
    helium = np.array([[0.8, 0.15, 0.05]])
    candidate_hydrogen = np.array([[0.2, 0.8]])
    candidate_helium = np.array([[0.1, 0.3, 0.6]])
    candidate = _candidate(
        temperature,
        hydrogen,
        helium,
        np.array([1.1e4]),
        candidate_hydrogen,
        candidate_helium,
    )
    step = damped_coupled_material_iteration(
        temperature,
        hydrogen,
        helium,
        candidate,
        maximum_relative_temperature_change=0.2,
        maximum_absolute_material_energy_increment_fraction=0.2,
    )
    np.testing.assert_allclose(np.sum(step.hydrogen_fraction, axis=1), 1.0)
    np.testing.assert_allclose(np.sum(step.helium_fraction, axis=1), 1.0)
    assert step.minimum_population_fraction >= 0.0
    assert step.maximum_particle_conservation_residual < 1.0e-15
