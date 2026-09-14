from __future__ import annotations

import numpy as np

from eccentric_tde_observer.faceon import (
    face_on_blackbody_sed,
    face_on_bolometric_luminosities,
)
from eccentric_tde_observer.fixtures import (
    constant_temperature_circular_annulus,
    power_law_temperature_circular_annulus,
)
from eccentric_tde_observer.quadrature import periodic_weights, corrected_zo_area_cm2
from eccentric_tde_observer.radiation import (
    STEFAN_BOLTZMANN_ERG_S_CM2_K4,
    planck_nu,
)


def test_periodic_quadrature_integrates_constant_exactly() -> None:
    anomaly = np.linspace(0.0, 2.0 * np.pi, 17, endpoint=False)
    assert np.isclose(np.sum(periodic_weights(anomaly)), 2.0 * np.pi)


def test_circular_annulus_area_matches_analytic_result() -> None:
    inner = 1.0e14
    outer = 2.0e14
    source = constant_temperature_circular_annulus(inner, outer, 5.0e4)
    analytic_area = np.pi * (outer**2 - inner**2)
    assert np.isclose(corrected_zo_area_cm2(source), analytic_area, rtol=2.0e-15)


def test_face_on_sed_matches_isothermal_annulus_solution() -> None:
    inner = 1.0e14
    outer = 2.0e14
    temperature = 5.0e4
    source = constant_temperature_circular_annulus(inner, outer, temperature)
    frequency = np.geomspace(1.0e13, 1.0e18, 101)
    result = face_on_blackbody_sed(source, frequency)
    analytic_area = np.pi * (outer**2 - inner**2)
    analytic_lnu = 4.0 * np.pi * analytic_area * planck_nu(frequency, temperature)
    assert np.allclose(
        result.isotropic_equivalent_lnu_erg_s_hz, analytic_lnu, rtol=5.0e-15
    )
    assert np.array_equal(
        result.isotropic_equivalent_lnu_erg_s_hz,
        2.0 * result.intrinsic_two_sided_lnu_erg_s_hz,
    )


def test_frequency_integral_matches_stefan_boltzmann_limit() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=33, anomaly_points=64
    )
    frequency = np.geomspace(1.0e10, 1.0e20, 4001)
    result = face_on_blackbody_sed(source, frequency)
    spectral_integral = np.trapezoid(
        result.isotropic_equivalent_lnu_erg_s_hz, frequency
    )
    bolometric_isotropic, bolometric_true = face_on_bolometric_luminosities(source)
    assert np.isclose(spectral_integral, bolometric_isotropic, rtol=1.0e-5)
    assert bolometric_isotropic == 2.0 * bolometric_true


def test_radial_grid_converges_for_power_law_temperature() -> None:
    inner = 1.0e14
    outer = 4.0e14
    inner_temperature = 1.0e5
    index = 0.75
    analytic_one_face = (
        2.0
        * np.pi
        * STEFAN_BOLTZMANN_ERG_S_CM2_K4
        * inner_temperature**4
        * inner**3
        * (1.0 / inner - 1.0 / outer)
    )
    analytic_isotropic = 4.0 * analytic_one_face

    errors = []
    for radial_points in (9, 17, 33, 65, 129):
        source = power_law_temperature_circular_annulus(
            inner,
            outer,
            inner_temperature,
            temperature_index=index,
            radial_points=radial_points,
            anomaly_points=32,
        )
        numerical_isotropic, _ = face_on_bolometric_luminosities(source)
        errors.append(abs(numerical_isotropic / analytic_isotropic - 1.0))

    assert np.all(np.diff(errors) < 0.0)
    assert errors[-1] < 1.3e-4
    observed_orders = np.log2(np.asarray(errors[:-1]) / np.asarray(errors[1:]))
    assert np.all(observed_orders > 1.8)
