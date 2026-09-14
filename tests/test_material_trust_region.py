import numpy as np

from eccentric_tde_observer.material_trust_region import (
    damped_material_picard_step,
)
from eccentric_tde_observer.radiation_matter_feedback import (
    frozen_radiation_material_response,
)


def _full_candidate():
    density = np.array([1.0e-10, 2.0e-10])
    temperature = np.array([2.0e4, 3.0e4])
    hydrogen = np.tile([0.2, 0.8], (2, 1))
    helium = np.tile([0.1, 0.3, 0.6], (2, 1))
    candidate = frozen_radiation_material_response(
        density,
        temperature,
        hydrogen,
        helium,
        100.0,
        np.zeros((2, 3)),
        np.zeros((2, 3)),
        np.array([1.0, 0.2]),
    )
    return temperature, hydrogen, helium, candidate


def test_damped_picard_step_hits_a_trust_boundary_and_preserves_energy():
    temperature, hydrogen, helium, candidate = _full_candidate()
    result = damped_material_picard_step(
        temperature,
        hydrogen,
        helium,
        candidate,
        maximum_relative_temperature_change=0.05,
        maximum_absolute_material_energy_increment_fraction=0.05,
    )
    assert 0.0 < result.relaxation < 1.0
    assert result.maximum_relative_temperature_change <= 0.05
    assert result.maximum_absolute_material_energy_increment_fraction <= 0.05
    assert max(
        result.maximum_relative_temperature_change / 0.05,
        result.maximum_absolute_material_energy_increment_fraction / 0.05,
    ) > 0.999
    assert result.maximum_relative_energy_residual < 3.0e-15
    assert result.maximum_particle_conservation_residual < 3.0e-15
    assert result.minimum_population_fraction >= 0.0


def test_damped_picard_step_accepts_full_candidate_when_already_bounded():
    temperature, hydrogen, helium, candidate = _full_candidate()
    result = damped_material_picard_step(
        temperature,
        hydrogen,
        helium,
        candidate,
        maximum_relative_temperature_change=0.99,
        maximum_absolute_material_energy_increment_fraction=0.99,
    )
    assert 0.0 < result.relaxation <= 1.0
    assert result.maximum_relative_temperature_change <= 0.99
    assert result.maximum_absolute_material_energy_increment_fraction <= 0.99
