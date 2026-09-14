import numpy as np
import pytest

from eccentric_tde_observer.radiation_matter_feedback import (
    frozen_radiation_material_response,
    ground_state_material_specific_energy_erg_g,
    ground_state_material_temperature_from_specific_energy_k,
)
from eccentric_tde_observer.source import PhysicalDomainError


def _state(cells: int = 3):
    temperature = np.linspace(1.5e4, 3.0e4, cells)
    hydrogen = np.tile([0.25, 0.75], (cells, 1))
    helium = np.tile([0.1, 0.35, 0.55], (cells, 1))
    return temperature, hydrogen, helium


def test_material_energy_temperature_round_trip_excludes_explicit_radiation():
    temperature, hydrogen, helium = _state()
    energy = ground_state_material_specific_energy_erg_g(
        temperature, hydrogen, helium
    )
    recovered = ground_state_material_temperature_from_specific_energy_k(
        energy, hydrogen, helium
    )
    np.testing.assert_allclose(recovered, temperature, rtol=3.0e-15, atol=0.0)


def test_zero_rate_zero_heating_response_is_identity():
    temperature, hydrogen, helium = _state()
    result = frozen_radiation_material_response(
        np.full(3, 2.0e-10),
        temperature,
        hydrogen,
        helium,
        20.0,
        np.zeros((3, 3)),
        np.zeros((3, 3)),
        np.zeros(3),
    )
    np.testing.assert_allclose(result.temperature_k, temperature, rtol=3.0e-15)
    np.testing.assert_allclose(result.hydrogen_fraction, hydrogen, atol=3.0e-15)
    np.testing.assert_allclose(result.helium_fraction, helium, atol=3.0e-15)
    assert result.maximum_relative_energy_residual < 3.0e-15
    assert result.maximum_particle_conservation_residual < 3.0e-15


def test_heating_response_closes_material_energy_without_floor_or_renormalization():
    temperature, hydrogen, helium = _state(1)
    density = np.array([1.0e-10])
    heating = np.array([2.0e-2])
    duration = 3.0
    initial = ground_state_material_specific_energy_erg_g(
        temperature, hydrogen, helium
    )
    result = frozen_radiation_material_response(
        density,
        temperature,
        hydrogen,
        helium,
        duration,
        np.zeros((1, 3)),
        np.zeros((1, 3)),
        heating,
    )
    np.testing.assert_allclose(
        result.recovered_specific_material_energy_erg_g,
        initial + duration * heating / density,
        rtol=3.0e-15,
    )
    assert result.temperature_k[0] > temperature[0]


def test_impossible_cooling_is_rejected_instead_of_clipped():
    temperature, hydrogen, helium = _state(1)
    with pytest.raises(PhysicalDomainError):
        frozen_radiation_material_response(
            np.array([1.0e-10]),
            temperature,
            hydrogen,
            helium,
            1.0,
            np.zeros((1, 3)),
            np.zeros((1, 3)),
            np.array([-1.0e20]),
        )
