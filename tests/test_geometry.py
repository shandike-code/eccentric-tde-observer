from __future__ import annotations

import numpy as np

from eccentric_tde_observer.fixtures import (
    constant_temperature_circular_annulus,
    constant_temperature_eccentric_annulus,
)
from eccentric_tde_observer.geometry import build_orbital_surface_mesh
from eccentric_tde_observer.faceon import (
    face_on_blackbody_sed,
    pre_erratum_face_on_blackbody_sed,
)
from eccentric_tde_observer.observer import (
    Observer,
    unobscured_blackbody_sed,
    unobscured_projected_area_cm2,
)
from eccentric_tde_observer.quadrature import (
    geometric_planar_area_cm2,
    geometric_planar_area_weights,
    corrected_zo_area_cm2,
    corrected_zo_area_weights,
    pre_erratum_zo2020_area_cm2,
    pre_erratum_zo2020_area_weights,
)


PARSEC_CM = 3.0856775814913673e18


def test_e_zero_makes_corrected_and_pre_erratum_measures_identical() -> None:
    source = constant_temperature_circular_annulus(1.0e14, 2.0e14, 5.0e4)
    assert np.array_equal(
        corrected_zo_area_weights(source), pre_erratum_zo2020_area_weights(source)
    )
    frequency = np.geomspace(1.0e14, 1.0e17, 17)
    corrected = face_on_blackbody_sed(source, frequency)
    historical = pre_erratum_face_on_blackbody_sed(source, frequency)
    assert np.array_equal(
        corrected.isotropic_equivalent_lnu_erg_s_hz,
        historical.isotropic_equivalent_lnu_erg_s_hz,
    )


def test_corrected_measure_contains_erratum_factor() -> None:
    eccentricity = 0.8
    source = constant_temperature_eccentric_annulus(
        1.0e14, 2.0e14, eccentricity, 5.0e4
    )
    ratio = corrected_zo_area_weights(source) / pre_erratum_zo2020_area_weights(source)
    expected = 1.0 - eccentricity * np.cos(source.eccentric_anomaly_rad)
    assert np.allclose(ratio, expected[None, :], rtol=2.0e-15)


def test_corrected_and_historical_total_areas_match_for_constant_e() -> None:
    inner = 1.0e14
    outer = 2.0e14
    eccentricity = 0.8
    source = constant_temperature_eccentric_annulus(
        inner, outer, eccentricity, 5.0e4, radial_points=33, anomaly_points=128
    )
    analytic_area = (
        np.pi * np.sqrt(1.0 - eccentricity**2) * (outer**2 - inner**2)
    )
    assert np.isclose(pre_erratum_zo2020_area_cm2(source), analytic_area, rtol=2.0e-15)
    assert np.isclose(geometric_planar_area_cm2(source), analytic_area, rtol=2.0e-15)


def test_eccentric_surface_mesh_area_converges_at_second_order() -> None:
    inner = 1.0e14
    outer = 2.0e14
    eccentricity = 0.8
    analytic_area = (
        np.pi * np.sqrt(1.0 - eccentricity**2) * (outer**2 - inner**2)
    )
    errors = []
    for anomaly_points in (16, 32, 64, 128):
        source = constant_temperature_eccentric_annulus(
            inner,
            outer,
            eccentricity,
            5.0e4,
            radial_points=5,
            anomaly_points=anomaly_points,
        )
        mesh = build_orbital_surface_mesh(source)
        errors.append(abs(mesh.total_area_cm2 / analytic_area - 1.0))

    assert np.all(np.diff(errors) < 0.0)
    observed_orders = np.log2(np.asarray(errors[:-1]) / np.asarray(errors[1:]))
    assert np.all(observed_orders > 1.9)
    assert errors[-1] < 5.0e-4


def test_rigid_precession_preserves_surface_area() -> None:
    sources = [
        constant_temperature_eccentric_annulus(
            1.0e14,
            2.0e14,
            0.8,
            5.0e4,
            anomaly_points=128,
            apsidal_angle_rad=angle,
        )
        for angle in (0.0, 0.7, 2.4)
    ]
    areas = np.array(
        [build_orbital_surface_mesh(source).total_area_cm2 for source in sources]
    )
    assert np.allclose(areas, areas[0], rtol=2.0e-15)


def test_flat_surface_projection_recovers_cosine_and_has_no_azimuth_dependence() -> None:
    source = constant_temperature_eccentric_annulus(
        1.0e14, 2.0e14, 0.8, 5.0e4, anomaly_points=128
    )
    mesh = build_orbital_surface_mesh(source)
    face_on = Observer(100.0e6 * PARSEC_CM, 0.0, 0.0)
    face_on_area = unobscured_projected_area_cm2(mesh, face_on)
    inclination = np.deg2rad(67.0)
    for azimuth in (0.0, 0.5, 2.0, 5.0):
        observer = Observer(100.0e6 * PARSEC_CM, inclination, azimuth)
        ratio = unobscured_projected_area_cm2(mesh, observer) / face_on_area
        assert np.isclose(ratio, np.cos(inclination), rtol=2.0e-15)


def test_unobscured_flat_blackbody_sed_recovers_cosine_law() -> None:
    source = constant_temperature_eccentric_annulus(
        1.0e14, 2.0e14, 0.8, 5.0e4, anomaly_points=128
    )
    mesh = build_orbital_surface_mesh(source)
    frequency = np.geomspace(1.0e14, 1.0e17, 31)
    distance = 100.0e6 * PARSEC_CM
    face_on = unobscured_blackbody_sed(
        source, mesh, Observer(distance, 0.0, 0.0), frequency
    )
    inclination = np.deg2rad(60.0)
    inclined = unobscured_blackbody_sed(
        source, mesh, Observer(distance, inclination, 1.3), frequency
    )
    assert np.allclose(
        inclined.flux_density_erg_s_cm2_hz
        / face_on.flux_density_erg_s_cm2_hz,
        np.cos(inclination),
        rtol=3.0e-15,
    )
    assert np.allclose(
        face_on.isotropic_equivalent_lnu_erg_s_hz,
        4.0 * np.pi * distance**2 * face_on.flux_density_erg_s_cm2_hz,
        rtol=2.0e-15,
    )
