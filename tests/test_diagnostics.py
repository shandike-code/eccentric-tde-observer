from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.diagnostics import fit_isotropic_blackbody_lnu
from eccentric_tde_observer.radiation import (
    STEFAN_BOLTZMANN_ERG_S_CM2_K4,
    planck_nu,
)
from eccentric_tde_observer.source import PhysicalDomainError


def test_exact_isotropic_blackbody_recovers_temperature_and_radius() -> None:
    frequency = np.geomspace(3.0e14, 3.0e16, 201)
    temperature = 4.7e4
    radius = 2.3e14
    luminosity = 4.0 * np.pi**2 * radius**2 * planck_nu(
        frequency, temperature
    )
    fit = fit_isotropic_blackbody_lnu(
        frequency, luminosity, 5.0e14, 2.0e16
    )
    assert np.isclose(fit.temperature_k, temperature, rtol=2.0e-8)
    assert np.isclose(fit.radius_cm, radius, rtol=5.0e-8)
    expected_bolometric = (
        4.0
        * np.pi
        * radius**2
        * STEFAN_BOLTZMANN_ERG_S_CM2_K4
        * temperature**4
    )
    assert np.isclose(
        fit.bolometric_luminosity_erg_s,
        expected_bolometric,
        rtol=8.0e-8,
    )
    assert fit.rms_log10_residual_dex < 3.0e-8


def test_multitemperature_spectrum_reports_nonzero_fit_residual() -> None:
    frequency = np.geomspace(3.0e14, 3.0e16, 201)
    luminosity = 4.0 * np.pi**2 * (
        (2.0e14) ** 2 * planck_nu(frequency, 2.0e4)
        + (0.7e14) ** 2 * planck_nu(frequency, 8.0e4)
    )
    fit = fit_isotropic_blackbody_lnu(
        frequency, luminosity, 5.0e14, 2.0e16
    )
    assert fit.rms_log10_residual_dex > 0.01


def test_zero_wien_tail_outside_fit_band_is_allowed_without_replacement() -> None:
    frequency = np.geomspace(1.0e14, 1.0e18, 201)
    luminosity = 4.0 * np.pi**2 * (1.0e14) ** 2 * planck_nu(
        frequency, 3.0e4
    )
    luminosity[-5:] = 0.0
    fit = fit_isotropic_blackbody_lnu(
        frequency, luminosity, 5.0e14, 2.0e16
    )
    assert np.isclose(fit.temperature_k, 3.0e4, rtol=5.0e-8)


@pytest.mark.parametrize(
    "luminosity",
    [np.ones((3, 1)), np.array([1.0, 0.0, 1.0]), np.array([1.0, np.nan, 1.0])],
)
def test_invalid_blackbody_fit_luminosity_is_rejected(
    luminosity: np.ndarray,
) -> None:
    frequency = np.array([1.0e14, 2.0e14, 3.0e14])
    with pytest.raises(PhysicalDomainError):
        fit_isotropic_blackbody_lnu(
            frequency, luminosity, 1.0e14, 3.0e14
        )
