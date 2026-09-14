from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.annulus_bridge import (
    AngleResolvedAnnulusTable,
    AnnulusTableDomainError,
    compton_y_upper_bound,
    zo_annulus_atmosphere_coordinates,
)
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model
from eccentric_tde_observer.relativity import GRAVITATIONAL_CONSTANT_CGS
from eccentric_tde_observer.source import PhysicalDomainError
from eccentric_tde_observer.zo_reference import SOLAR_MASS_G


def test_circular_limit_recovers_static_vertical_gravity_and_zero_breathing() -> None:
    model = build_strict_domain_reference_model(5, 64, eccentricity=0.0)
    coordinates = zo_annulus_atmosphere_coordinates(model)
    expected = (
        GRAVITATIONAL_CONSTANT_CGS
        * model.parameters.black_hole_mass_msun
        * SOLAR_MASS_G
        / model.source.semimajor_axis_cm[:, None] ** 3
    )
    assert np.allclose(coordinates.tidal_gravity_coefficient_s2, expected, rtol=2.0e-16)
    assert np.allclose(coordinates.comoving_pressure_gravity_coefficient_s2, expected, rtol=2.0e-16)
    assert np.all(coordinates.vertical_acceleration_coefficient_s2 == 0.0)
    assert np.all(coordinates.quasi_static_ratio == 0.0)
    assert np.array_equal(
        coordinates.midplane_column_mass_g_cm2,
        0.5 * model.source.surface_density_g_cm2,
    )


def test_eccentric_pressure_gravity_is_positive_and_dynamic() -> None:
    model = build_strict_domain_reference_model(9, 128)
    coordinates = zo_annulus_atmosphere_coordinates(model)
    assert np.all(coordinates.comoving_pressure_gravity_coefficient_s2 > 0.0)
    assert np.max(coordinates.quasi_static_ratio) > 1.0
    assert np.any(coordinates.vertical_acceleration_coefficient_s2 < 0.0)
    assert np.any(coordinates.vertical_acceleration_coefficient_s2 > 0.0)


def _power_law_table() -> AngleResolvedAnnulusTable:
    temperature = np.array([1.0e4, 1.0e5])
    column = np.array([1.0e2, 1.0e4])
    gravity = np.array([1.0e-8, 1.0e-4])
    cosine = np.array([0.2, 1.0])
    frequency = np.array([1.0e14, 1.0e16])
    t, m, q, mu, nu = np.meshgrid(
        temperature, column, gravity, cosine, frequency, indexing="ij"
    )
    intensity = t**1.5 * m**0.2 * q**0.1 * np.exp(mu) * nu ** (-0.7)
    return AngleResolvedAnnulusTable(
        temperature,
        column,
        gravity,
        cosine,
        frequency,
        intensity,
        provenance="analytic power-law interpolation fixture",
    )


def test_log_table_interpolation_is_exact_for_power_law_fixture() -> None:
    table = _power_law_table()
    t, m, q, mu, nu = 3.0e4, 8.0e2, 2.0e-6, 0.6, 8.0e14
    result = table.interpolate_specific_intensity(t, m, q, mu, nu)
    expected = t**1.5 * m**0.2 * q**0.1 * np.exp(mu) * nu ** (-0.7)
    assert np.isclose(result, expected, rtol=2.0e-14)


def test_table_rejects_extrapolation_and_invalid_intensity() -> None:
    table = _power_law_table()
    with pytest.raises(AnnulusTableDomainError, match="outside"):
        table.interpolate_specific_intensity(9.0e3, 1.0e3, 1.0e-6, 0.5, 1.0e15)
    with pytest.raises(PhysicalDomainError, match="strictly positive"):
        AngleResolvedAnnulusTable(
            [1.0e4, 1.0e5],
            [1.0e2, 1.0e4],
            [1.0e-8, 1.0e-4],
            [0.2, 1.0],
            [1.0e14, 1.0e16],
            np.zeros((2, 2, 2, 2, 2)),
            provenance="invalid fixture",
        )


def test_compton_y_has_thin_and_thick_optical_depth_branches() -> None:
    y = compton_y_upper_bound(1.0e6, np.array([0.1, 10.0]))
    assert np.isclose(y[1] / y[0], 1000.0, rtol=2.0e-16)


def test_annulus_bridge_source_does_not_use_forbidden_masking_helpers() -> None:
    from eccentric_tde_observer import annulus_bridge

    source_text = open(annulus_bridge.__file__, encoding="utf-8").read()
    assert "nan_to_num" not in source_text
    assert "np.clip" not in source_text
