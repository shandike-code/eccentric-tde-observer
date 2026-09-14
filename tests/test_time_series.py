from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.source import PhysicalDomainError
from eccentric_tde_observer.time_series import (
    AB_ZERO_POINT_FNU_CGS,
    Bandpass,
    PeriodicPhaseSpectralAtlas,
    ab_magnitude_from_fnu,
    ideal_log_tophat_bandpass,
    periodic_harmonics,
    photon_counting_mean_fnu,
    uniform_precession_relative_phase,
)


def test_constant_fnu_has_exact_ab_zero_point_in_any_band() -> None:
    frequency = np.geomspace(1.0e14, 1.0e16, 501)
    flux = np.full(frequency.size, AB_ZERO_POINT_FNU_CGS)
    band = ideal_log_tophat_bandpass("test", 3.0e14, 3.0e15)
    mean = photon_counting_mean_fnu(frequency, flux, band)
    assert np.isclose(mean, AB_ZERO_POINT_FNU_CGS, rtol=2.0e-16)
    assert np.isclose(ab_magnitude_from_fnu(mean), 0.0, atol=3.0e-16)


def test_bandpass_rejects_incomplete_spectrum_coverage() -> None:
    band = Bandpass("wide", [1.0e14, 1.0e16], [1.0, 1.0])
    with pytest.raises(PhysicalDomainError, match="complete bandpass"):
        photon_counting_mean_fnu(
            np.geomspace(2.0e14, 1.0e16, 20), np.ones(20), band
        )


def _atlas() -> PeriodicPhaseSpectralAtlas:
    phase = np.linspace(0.0, 2.0 * np.pi, 8, endpoint=False)
    frequency = np.array([1.0e14, 2.0e14])
    flux = (2.0 + np.cos(phase))[:, None] * np.array([1.0, 3.0])[None, :]
    return PeriodicPhaseSpectralAtlas(phase, frequency, flux)


def test_phase_atlas_recovers_nodes_and_periodic_wrapping() -> None:
    atlas = _atlas()
    assert np.array_equal(atlas.sample(atlas.relative_phase_rad), atlas.flux_density_cgs)
    assert np.allclose(atlas.sample(0.3), atlas.sample(0.3 + 4.0 * np.pi), rtol=3.0e-16)


def test_uniform_precession_uses_supplied_period_and_direction() -> None:
    time = np.array([0.0, 0.25, 0.5, 1.0])
    prograde = uniform_precession_relative_phase(time, 1.0)
    retrograde = uniform_precession_relative_phase(time, 1.0, prograde=False)
    assert np.allclose(prograde, np.mod(-2.0 * np.pi * time, 2.0 * np.pi))
    assert np.allclose(retrograde, np.mod(2.0 * np.pi * time, 2.0 * np.pi))


def test_harmonics_recovers_pure_first_harmonic_amplitude() -> None:
    phase = np.linspace(0.0, 2.0 * np.pi, 32, endpoint=False)
    result = periodic_harmonics(2.0 * (1.0 + 0.3 * np.cos(phase)))
    assert np.isclose(result.first_harmonic_fractional_semi_amplitude, 0.3, rtol=2.0e-16)
    assert result.second_harmonic_fractional_semi_amplitude < 2.0e-16
    assert np.isclose(result.fractional_rms, 0.3 / np.sqrt(2.0), rtol=2.0e-16)


def test_time_series_source_does_not_use_forbidden_masking_helpers() -> None:
    from eccentric_tde_observer import time_series

    source_text = open(time_series.__file__, encoding="utf-8").read()
    assert "nan_to_num" not in source_text
    assert "np.clip" not in source_text
