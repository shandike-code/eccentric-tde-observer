from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.fixtures import constant_temperature_circular_annulus
from eccentric_tde_observer.observer import Observer
from eccentric_tde_observer.radiation import (
    LIGHT_SPEED_CM_S,
    STEFAN_BOLTZMANN_ERG_S_CM2_K4,
    planck_nu,
)
from eccentric_tde_observer.relativity import (
    GRAVITATIONAL_CONSTANT_CGS,
    homologous_vertical_velocity_cm_s,
    keplerian_orbital_velocity_cm_s,
    orbital_radius_cm,
    straight_ray_frequency_shift,
)
from eccentric_tde_observer.source import PhysicalDomainError, ZOSourceGrid
from eccentric_tde_observer.zo_reference import SOLAR_MASS_G


def _constant_e_source(eccentricity: float = 0.6) -> ZOSourceGrid:
    source = constant_temperature_circular_annulus(
        1.0e14,
        2.0e14,
        4.0e4,
        radial_points=5,
        anomaly_points=64,
    )
    return ZOSourceGrid(
        semimajor_axis_cm=source.semimajor_axis_cm,
        eccentric_anomaly_rad=source.eccentric_anomaly_rad,
        eccentricity=np.full(source.shape[0], eccentricity),
        jacobian=np.full(source.shape, np.sqrt(1.0 - eccentricity**2)),
        surface_density_g_cm2=source.surface_density_g_cm2,
        scale_height_cm=source.scale_height_cm,
        effective_temperature_k=source.effective_temperature_k,
        eccentricity_gradient_per_cm=np.zeros(source.shape[0]),
        apsidal_gradient_per_cm=np.zeros(source.shape[0]),
        label="constant-e frequency-shift fixture",
        provenance="analytic relativity fixture [A/V]",
    )


def test_keplerian_eccentric_velocity_satisfies_vis_viva() -> None:
    source = _constant_e_source(0.6)
    mass_msun = 1.0e6
    velocity = keplerian_orbital_velocity_cm_s(source, mass_msun)
    speed_squared = np.sum(velocity**2, axis=-1)
    radius = orbital_radius_cm(source)
    expected = (
        GRAVITATIONAL_CONSTANT_CGS
        * mass_msun
        * SOLAR_MASS_G
        * (2.0 / radius - 1.0 / source.semimajor_axis_cm[:, None])
    )
    assert np.allclose(speed_squared, expected, rtol=8.0e-15)


def test_circular_velocity_has_constant_speed_and_no_radial_component() -> None:
    source = _constant_e_source(0.0)
    mass_msun = 1.0e6
    velocity = keplerian_orbital_velocity_cm_s(source, mass_msun)
    position_angle = source.eccentric_anomaly_rad
    radial_hat = np.stack(
        (np.cos(position_angle), np.sin(position_angle)), axis=-1
    )
    radial_velocity = np.sum(velocity[..., :2] * radial_hat[None, :, :], axis=-1)
    expected_speed = np.sqrt(
        GRAVITATIONAL_CONSTANT_CGS
        * mass_msun
        * SOLAR_MASS_G
        / source.semimajor_axis_cm
    )
    assert np.allclose(radial_velocity, 0.0, atol=2.0e-6)
    assert np.allclose(
        np.linalg.norm(velocity[..., :2], axis=-1),
        expected_speed[:, None],
        rtol=5.0e-16,
    )


def test_face_on_in_plane_shift_is_lapse_over_gamma() -> None:
    source = _constant_e_source(0.6)
    observer = Observer(1.0e26, 0.0, 0.0)
    shift = straight_ray_frequency_shift(source, observer, 1.0e6)
    assert np.array_equal(shift.line_of_sight_beta, np.zeros(source.shape))
    assert np.allclose(
        shift.frequency_shift_factor,
        shift.gravitational_lapse / shift.lorentz_factor,
        rtol=2.0e-16,
    )
    assert np.all(shift.frequency_shift_factor < 1.0)


def test_approaching_quadrature_is_bluer_than_receding_quadrature() -> None:
    source = _constant_e_source(0.6)
    observer = Observer(1.0e26, np.deg2rad(75.0), 0.0)
    shift = straight_ray_frequency_shift(source, observer, 1.0e6)
    receding = 16
    approaching = 48
    assert np.isclose(source.eccentric_anomaly_rad[receding], 0.5 * np.pi)
    assert np.isclose(source.eccentric_anomaly_rad[approaching], 1.5 * np.pi)
    assert np.all(
        shift.frequency_shift_factor[:, approaching]
        > shift.frequency_shift_factor[:, receding]
    )


def test_homologous_vertical_velocity_uses_breathing_derivative_without_clipping() -> None:
    source = _constant_e_source(0.6)
    height = np.full(source.shape, 1.0e13)
    derivative = np.sin(source.eccentric_anomaly_rad)
    velocity = homologous_vertical_velocity_cm_s(
        source, height, derivative, 1.0e6
    )
    assert np.allclose(velocity[:, 0], 0.0, atol=0.0)
    assert np.all(velocity[:, 16] > 0.0)
    assert np.all(velocity[:, 48] < 0.0)
    zero = homologous_vertical_velocity_cm_s(
        source, height, np.zeros(source.shape[1]), 1.0e6
    )
    assert np.array_equal(zero, np.zeros(source.shape))


def test_planck_transfer_identity_is_exact_to_roundoff() -> None:
    frequency = np.geomspace(1.0e14, 1.0e18, 31)
    temperature = 5.0e4
    shift = 1.037
    invariant_form = shift**3 * planck_nu(frequency / shift, temperature)
    shifted_temperature_form = planck_nu(frequency, shift * temperature)
    assert np.allclose(invariant_form, shifted_temperature_form, rtol=3.0e-15)


def test_frequency_integrated_shifted_planck_intensity_has_g_four_scaling() -> None:
    frequency = np.geomspace(1.0e9, 1.0e20, 30001)
    temperature = 5.0e4
    shift = 0.97
    integrated_intensity = np.trapezoid(
        planck_nu(frequency, shift * temperature), frequency
    )
    expected = (
        STEFAN_BOLTZMANN_ERG_S_CM2_K4
        / np.pi
        * (shift * temperature) ** 4
    )
    assert np.isclose(integrated_intensity, expected, rtol=1.3e-7)


def test_invalid_relativity_states_are_rejected() -> None:
    source = _constant_e_source(0.6)
    observer = Observer(1.0e26, 0.0, 0.0)
    with pytest.raises(PhysicalDomainError, match="black_hole_mass"):
        straight_ray_frequency_shift(source, observer, -1.0)

    horizon_mass_msun = (
        source.semimajor_axis_cm[0]
        * (1.0 - source.eccentricity[0])
        * LIGHT_SPEED_CM_S**2
        / (2.0 * GRAVITATIONAL_CONSTANT_CGS * SOLAR_MASS_G)
    )
    with pytest.raises(PhysicalDomainError, match="r > 2GM"):
        straight_ray_frequency_shift(source, observer, 1.01 * horizon_mass_msun)

    invalid_vertical = np.zeros(source.shape)
    invalid_vertical[0, 0] = np.inf
    with pytest.raises(PhysicalDomainError, match="vertical_velocity"):
        straight_ray_frequency_shift(
            source,
            observer,
            1.0e6,
            vertical_velocity_cm_s=invalid_vertical,
        )

    twisted = ZOSourceGrid(
        semimajor_axis_cm=source.semimajor_axis_cm,
        eccentric_anomaly_rad=source.eccentric_anomaly_rad,
        eccentricity=np.full(source.shape[0], 0.1),
        jacobian=np.full(source.shape, np.sqrt(1.0 - 0.1**2)),
        surface_density_g_cm2=source.surface_density_g_cm2,
        scale_height_cm=source.scale_height_cm,
        effective_temperature_k=source.effective_temperature_k,
        eccentricity_gradient_per_cm=np.zeros(source.shape[0]),
        apsidal_gradient_per_cm=np.full(source.shape[0], 1.0e-16),
    )
    with pytest.raises(PhysicalDomainError, match=r"varpi\(a\)"):
        keplerian_orbital_velocity_cm_s(twisted, 1.0e6)
