from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.observer_frame import (
    MPC_CM,
    attenuate_flux_by_extinction,
    fitzpatrick_1998_a_over_ebv,
    flat_lcdm_luminosity_distance_cm,
    frequency_fnu_to_wavelength_flambda,
    redshift_reference_fnu,
    reference_fnu_to_observer_flambda,
)
from eccentric_tde_observer.source import PhysicalDomainError


def _reference_spectrum() -> tuple[np.ndarray, np.ndarray]:
    frequency = np.geomspace(1.0e14, 1.0e16, 2001)
    flux = 2.0e-28 * (frequency / 1.0e15) ** (-0.4)
    return frequency, flux


def test_fnu_flambda_jacobian_preserves_energy_and_nu_fnu() -> None:
    frequency, fnu = _reference_spectrum()
    wavelength, flambda = frequency_fnu_to_wavelength_flambda(frequency, fnu)
    energy_nu = np.trapezoid(fnu, frequency)
    energy_lambda = np.trapezoid(flambda, wavelength)
    assert np.isclose(energy_lambda, energy_nu, rtol=2.0e-6)
    assert np.allclose(
        wavelength * flambda,
        frequency[::-1] * fnu[::-1],
        rtol=3.0e-16,
    )


def test_hogg_redshift_mapping_recovers_bolometric_distance_relation() -> None:
    frequency, reference_fnu = _reference_spectrum()
    redshift = 0.2
    reference_distance = 100.0 * MPC_CM
    luminosity_distance = 900.0 * MPC_CM
    observed_frequency, observed_fnu = redshift_reference_fnu(
        frequency,
        reference_fnu,
        reference_distance_cm=reference_distance,
        redshift=redshift,
        luminosity_distance_cm=luminosity_distance,
    )
    expected_ratio = (reference_distance / luminosity_distance) ** 2
    assert np.isclose(
        np.trapezoid(observed_fnu, observed_frequency)
        / np.trapezoid(reference_fnu, frequency),
        expected_ratio,
        rtol=4.0e-16,
    )


def test_zero_redshift_and_equal_distance_are_identity() -> None:
    frequency, reference_fnu = _reference_spectrum()
    observed_frequency, observed_fnu = redshift_reference_fnu(
        frequency,
        reference_fnu,
        reference_distance_cm=100.0 * MPC_CM,
        redshift=0.0,
        luminosity_distance_cm=100.0 * MPC_CM,
    )
    assert np.array_equal(observed_frequency, frequency)
    assert np.array_equal(observed_fnu, reference_fnu)


def test_fitzpatrick_rv31_recovers_published_optical_ir_anchors() -> None:
    wavelength = np.array([26500.0, 12200.0, 6000.0, 5470.0, 4670.0, 4110.0])
    expected = np.array([0.265, 0.829, 2.688, 3.055, 3.806, 4.315])
    actual = fitzpatrick_1998_a_over_ebv(wavelength, r_v=3.1)
    assert np.allclose(actual, expected, rtol=0.0, atol=4.0e-4)


def test_fitzpatrick_uv_optical_join_is_continuous() -> None:
    wavelength = np.array([2699.999, 2700.0, 2700.001])
    actual = fitzpatrick_1998_a_over_ebv(wavelength, r_v=3.1)
    assert np.max(np.abs(np.diff(actual))) < 2.0e-5


def test_zero_extinction_is_exact_identity() -> None:
    flux = np.array([1.0e-15, 2.0e-15])
    assert np.array_equal(attenuate_flux_by_extinction(flux, 0.0), flux)


def test_observer_frame_rejects_extinction_outside_literature_domain() -> None:
    frequency, reference_fnu = _reference_spectrum()
    with pytest.raises(PhysicalDomainError, match="1000--60000"):
        reference_fnu_to_observer_flambda(
            frequency,
            reference_fnu,
            reference_distance_cm=100.0 * MPC_CM,
            redshift=0.05,
            luminosity_distance_cm=flat_lcdm_luminosity_distance_cm(0.05),
            wavelength_min_angstrom=500.0,
            wavelength_max_angstrom=20000.0,
            ebv_magnitude=0.03,
        )


@pytest.mark.parametrize(
    ("frequency", "flux"),
    [
        ([1.0e14, 1.0e14], [1.0, 1.0]),
        ([1.0e14, np.nan], [1.0, 1.0]),
        ([1.0e14, 2.0e14], [1.0, -1.0]),
    ],
)
def test_invalid_spectra_are_rejected(frequency, flux) -> None:
    with pytest.raises(PhysicalDomainError):
        frequency_fnu_to_wavelength_flambda(frequency, flux)


def test_observer_frame_source_has_no_forbidden_masking_helpers() -> None:
    from eccentric_tde_observer import observer_frame

    source_text = open(observer_frame.__file__, encoding="utf-8").read()
    assert "nan_to_num" not in source_text
    assert "np.clip" not in source_text
