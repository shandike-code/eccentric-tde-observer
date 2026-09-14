import numpy as np
import pytest

from eccentric_tde_observer.coupled_material_acceleration import (
    protected_diagonal_secant_material_step,
)
from eccentric_tde_observer.radiation_matter_feedback import (
    FrozenRadiationMaterialResponse,
    ground_state_material_specific_energy_erg_g,
)
from eccentric_tde_observer.source import PhysicalDomainError


def _candidate(temperature, hydrogen, helium, target_energy):
    target = np.asarray(target_energy, dtype=np.float64)
    return FrozenRadiationMaterialResponse(
        temperature_k=np.asarray(temperature, dtype=np.float64),
        hydrogen_fraction=np.asarray(hydrogen, dtype=np.float64),
        helium_fraction=np.asarray(helium, dtype=np.float64),
        electron_density_cm3=np.ones(len(temperature)),
        initial_specific_material_energy_erg_g=np.asarray(target),
        target_specific_material_energy_erg_g=np.asarray(target),
        recovered_specific_material_energy_erg_g=np.asarray(target),
        maximum_relative_temperature_change=0.0,
        maximum_population_fraction_change=0.0,
        maximum_relative_energy_residual=0.0,
        maximum_relative_charge_residual=0.0,
        maximum_particle_conservation_residual=0.0,
        minimum_population_fraction=0.0,
    )


def test_diagonal_secant_recovers_affine_scalar_root_without_clipping():
    previous_temperature = np.array([1.0e4])
    current_temperature = np.array([1.1e4])
    hydrogen = np.array([[0.7, 0.3]])
    helium = np.array([[0.6, 0.3, 0.1]])
    previous_energy = ground_state_material_specific_energy_erg_g(
        previous_temperature, hydrogen, helium
    )
    current_energy = ground_state_material_specific_energy_erg_g(
        current_temperature, hydrogen, helium
    )
    residual = 0.02 * previous_energy
    previous_candidate = _candidate(
        previous_temperature, hydrogen, helium, previous_energy + residual
    )
    current_candidate = _candidate(
        current_temperature, hydrogen, helium, current_energy - residual
    )
    step = protected_diagonal_secant_material_step(
        previous_temperature,
        hydrogen,
        helium,
        current_temperature,
        hydrogen,
        helium,
        previous_candidate,
        current_candidate,
        maximum_relative_temperature_change=1.0,
        maximum_absolute_material_energy_increment_fraction=0.9,
        maximum_population_fraction_change=0.9,
    )
    assert step.relaxation == 1.0
    assert step.maximum_secant_identity_relative_residual < 1.0e-14
    assert step.affine_secant_predicted_residual_contraction == 0.0
    assert step.maximum_relative_energy_residual < 1.0e-14


def test_diagonal_secant_uses_one_global_temperature_trust_step():
    previous_temperature = np.array([1.0e4, 2.0e4])
    current_temperature = np.array([1.05e4, 2.1e4])
    hydrogen = np.array([[0.8, 0.2], [0.6, 0.4]])
    helium = np.array([[0.7, 0.2, 0.1], [0.5, 0.3, 0.2]])
    previous_energy = ground_state_material_specific_energy_erg_g(
        previous_temperature, hydrogen, helium
    )
    current_energy = ground_state_material_specific_energy_erg_g(
        current_temperature, hydrogen, helium
    )
    previous_candidate = _candidate(
        previous_temperature, hydrogen, helium, 3.0 * previous_energy
    )
    current_candidate = _candidate(
        current_temperature, hydrogen, helium, 2.8 * current_energy
    )
    step = protected_diagonal_secant_material_step(
        previous_temperature,
        hydrogen,
        helium,
        current_temperature,
        hydrogen,
        helium,
        previous_candidate,
        current_candidate,
        maximum_relative_temperature_change=0.1,
        maximum_absolute_material_energy_increment_fraction=0.5,
        maximum_population_fraction_change=0.1,
    )
    assert 0.0 < step.relaxation < 1.0
    assert step.maximum_relative_temperature_change <= 0.1
    assert step.maximum_absolute_material_energy_increment_fraction <= 0.5
    assert step.maximum_relative_energy_residual < 1.0e-14


def test_diagonal_secant_preserves_hydrogen_and_helium_simplexes():
    previous_temperature = np.array([1.0e4])
    current_temperature = np.array([1.1e4])
    previous_hydrogen = np.array([[0.8, 0.2]])
    current_hydrogen = np.array([[0.7, 0.3]])
    previous_helium = np.array([[0.7, 0.2, 0.1]])
    current_helium = np.array([[0.6, 0.25, 0.15]])
    previous_energy = ground_state_material_specific_energy_erg_g(
        previous_temperature, previous_hydrogen, previous_helium
    )
    current_energy = ground_state_material_specific_energy_erg_g(
        current_temperature, current_hydrogen, current_helium
    )
    previous_candidate = _candidate(
        previous_temperature,
        np.array([[0.75, 0.25]]),
        np.array([[0.65, 0.23, 0.12]]),
        1.2 * previous_energy,
    )
    current_candidate = _candidate(
        current_temperature,
        np.array([[0.72, 0.28]]),
        np.array([[0.62, 0.24, 0.14]]),
        1.1 * current_energy,
    )
    step = protected_diagonal_secant_material_step(
        previous_temperature,
        previous_hydrogen,
        previous_helium,
        current_temperature,
        current_hydrogen,
        current_helium,
        previous_candidate,
        current_candidate,
        maximum_relative_temperature_change=0.5,
        maximum_absolute_material_energy_increment_fraction=0.5,
        maximum_population_fraction_change=0.2,
    )
    np.testing.assert_allclose(np.sum(step.hydrogen_fraction, axis=1), 1.0)
    np.testing.assert_allclose(np.sum(step.helium_fraction, axis=1), 1.0)
    assert step.minimum_population_fraction >= 0.0
    assert step.maximum_particle_conservation_residual < 1.0e-14


def test_diagonal_secant_rejects_exactly_zero_denominator_without_floor():
    previous_temperature = np.array([1.0e4])
    current_temperature = np.array([1.1e4])
    hydrogen = np.array([[0.7, 0.3]])
    helium = np.array([[0.6, 0.3, 0.1]])
    previous_energy = ground_state_material_specific_energy_erg_g(
        previous_temperature, hydrogen, helium
    )
    current_energy = ground_state_material_specific_energy_erg_g(
        current_temperature, hydrogen, helium
    )
    residual = np.array([1.0e10])
    previous_candidate = _candidate(
        previous_temperature, hydrogen, helium, previous_energy + residual
    )
    current_candidate = _candidate(
        current_temperature, hydrogen, helium, current_energy + residual
    )
    with pytest.raises(PhysicalDomainError, match="exactly zero"):
        protected_diagonal_secant_material_step(
            previous_temperature,
            hydrogen,
            helium,
            current_temperature,
            hydrogen,
            helium,
            previous_candidate,
            current_candidate,
            maximum_relative_temperature_change=0.5,
            maximum_absolute_material_energy_increment_fraction=0.5,
            maximum_population_fraction_change=0.2,
        )
