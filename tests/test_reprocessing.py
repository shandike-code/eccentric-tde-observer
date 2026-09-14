from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S
from eccentric_tde_observer.reprocessing import (
    minimum_seed_luminosity_erg_s,
    minimum_thermalizing_layer_requirement,
    momentum_limited_mass_loss_rate_g_s,
)
from eccentric_tde_observer.source import PhysicalDomainError


def test_thermalization_requirement_recovers_analytic_optical_depth() -> None:
    epsilon = np.array([1.0e-5, 1.0e-3])
    result = minimum_thermalizing_layer_requirement(1.0e14, epsilon)
    reconstructed = np.sqrt(3.0 * epsilon) * result.total_optical_depth
    assert np.allclose(reconstructed, 1.0, rtol=2.0e-16)
    expected_sigma = result.total_optical_depth * (1.0 - epsilon) / 0.34
    assert np.array_equal(result.surface_density_g_cm2, expected_sigma)


def test_required_mass_scales_as_radius_squared_without_hidden_geometry() -> None:
    result = minimum_thermalizing_layer_requirement(
        np.array([1.0e14, 2.0e14]), 1.0e-5
    )
    assert result.full_coverage_mass_g[1] == 4.0 * result.full_coverage_mass_g[0]
    assert result.diffusion_time_per_fractional_thickness_s[1] == 2.0 * result.diffusion_time_per_fractional_thickness_s[0]


def test_energy_and_momentum_bounds_close_exactly() -> None:
    reprocessed = 2.0e44
    seed = minimum_seed_luminosity_erg_s(reprocessed, 0.5, absorbed_fraction_of_intercepted_power=0.8)
    assert np.isclose(seed, 5.0e44, rtol=2.0e-16)
    speed = 1.0e9
    rate = momentum_limited_mass_loss_rate_g_s(seed, speed, momentum_optical_depth=3.0)
    assert np.isclose(rate * speed, 3.0 * seed / LIGHT_SPEED_CM_S, rtol=2.0e-16)


@pytest.mark.parametrize(
    ("radius", "epsilon"),
    [(0.0, 1.0e-3), (1.0e14, 0.0), (1.0e14, 1.0), (1.0e14, np.nan)],
)
def test_invalid_layer_parameters_are_rejected(radius, epsilon) -> None:
    with pytest.raises(PhysicalDomainError):
        minimum_thermalizing_layer_requirement(radius, epsilon)


def test_reprocessing_source_does_not_use_forbidden_masking_helpers() -> None:
    from eccentric_tde_observer import reprocessing

    source_text = open(reprocessing.__file__, encoding="utf-8").read()
    assert "nan_to_num" not in source_text
    assert "np.clip" not in source_text
