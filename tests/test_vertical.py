from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.fixtures import (
    constant_temperature_circular_annulus,
    constant_temperature_eccentric_annulus,
)
from eccentric_tde_observer.geometry import build_orbital_surface_mesh
from eccentric_tde_observer.photosphere import (
    OpticallyThinColumnError,
    solve_gray_photosphere,
)
from eccentric_tde_observer.source import PhysicalDomainError
from eccentric_tde_observer.vertical import (
    FiniteSupportTailResolutionError,
    GAUSSIAN_VERTICAL_PROFILE,
    RADIATION_PRESSURE_POLYTROPE_PROFILE,
    density_on_scaled_height_grid_g_cm3,
    upper_column_density_g_cm2,
)


def test_gaussian_density_shape_is_normalized() -> None:
    scaled_height = np.linspace(-10.0, 10.0, 40001)
    shape = GAUSSIAN_VERTICAL_PROFILE.density_shape(scaled_height)
    assert np.isclose(np.trapezoid(shape, scaled_height), 1.0, rtol=2.0e-15)
    assert GAUSSIAN_VERTICAL_PROFILE.upper_column_fraction(0.0) == 0.5


def test_n3_polytrope_has_literature_normalization_and_unit_second_moment() -> None:
    scaled_height = np.linspace(-3.0, 3.0, 60001)
    shape = RADIATION_PRESSURE_POLYTROPE_PROFILE.density_shape(scaled_height)
    assert np.isclose(np.trapezoid(shape, scaled_height), 1.0, rtol=3.0e-15)
    assert np.isclose(
        np.trapezoid(shape * scaled_height**2, scaled_height),
        1.0,
        rtol=3.0e-15,
    )
    assert RADIATION_PRESSURE_POLYTROPE_PROFILE.upper_column_fraction(0.0) == 0.5
    assert RADIATION_PRESSURE_POLYTROPE_PROFILE.density_shape(0.0) == 35.0 / 96.0


def test_n3_polytrope_column_and_inverse_round_trip() -> None:
    profile = RADIATION_PRESSURE_POLYTROPE_PROFILE
    scaled_height = np.array([0.0, 0.3, 1.0, 2.0, 2.9])
    fraction = profile.upper_column_fraction(scaled_height)
    reconstructed = profile.inverse_upper_column_fraction(fraction)
    assert np.allclose(reconstructed, scaled_height, rtol=2.0e-12, atol=2.0e-14)
    assert profile.upper_column_fraction(-3.0) == 1.0
    assert profile.upper_column_fraction(3.0) == 0.0
    assert profile.density_shape(np.array([-4.0, 3.0, 4.0])).tolist() == [
        0.0,
        0.0,
        0.0,
    ]


def test_n3_polytrope_column_remains_accurate_near_finite_edge() -> None:
    profile = RADIATION_PRESSURE_POLYTROPE_PROFILE
    upper_fraction = np.geomspace(1.0e-12, 0.5, 101)
    scaled_height = profile.inverse_upper_column_fraction(upper_fraction)
    reconstructed = profile.upper_column_fraction(scaled_height)
    assert np.allclose(reconstructed, upper_fraction, rtol=2.0e-13)


def test_n3_polytrope_rejects_unrepresentable_finite_edge_tail() -> None:
    with pytest.raises(FiniteSupportTailResolutionError, match="float64"):
        RADIATION_PRESSURE_POLYTROPE_PROFILE.inverse_upper_column_fraction(1.0e-246)


def test_vertical_density_integrates_back_to_surface_density() -> None:
    source = constant_temperature_eccentric_annulus(
        1.0e14,
        2.0e14,
        0.8,
        5.0e4,
        radial_points=5,
        anomaly_points=16,
    )
    scaled_height = np.linspace(-10.0, 10.0, 20001)
    density = density_on_scaled_height_grid_g_cm3(source, scaled_height)
    recovered_sigma = (
        np.trapezoid(density, scaled_height, axis=-1) * source.scale_height_cm
    )
    assert np.allclose(
        recovered_sigma, source.surface_density_g_cm2, rtol=3.0e-15
    )


def test_polytrope_density_integrates_back_to_surface_density() -> None:
    source = constant_temperature_eccentric_annulus(
        1.0e14,
        2.0e14,
        0.8,
        5.0e4,
        radial_points=5,
        anomaly_points=16,
    )
    scaled_height = np.linspace(-3.0, 3.0, 30001)
    density = density_on_scaled_height_grid_g_cm3(
        source, scaled_height, RADIATION_PRESSURE_POLYTROPE_PROFILE
    )
    recovered_sigma = (
        np.trapezoid(density, scaled_height, axis=-1) * source.scale_height_cm
    )
    assert np.allclose(
        recovered_sigma, source.surface_density_g_cm2, rtol=4.0e-15
    )


def test_upper_column_matches_gaussian_tail() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=3, anomaly_points=8
    )
    scaled_height = np.full(source.shape, 2.0)
    column = upper_column_density_g_cm2(source, scaled_height)
    expected = (
        source.surface_density_g_cm2
        * GAUSSIAN_VERTICAL_PROFILE.upper_column_fraction(2.0)
    )
    assert np.array_equal(column, expected)


def test_gray_photosphere_reconstructs_target_optical_depth() -> None:
    source = constant_temperature_eccentric_annulus(
        1.0e14, 2.0e14, 0.8, 5.0e4, radial_points=5, anomaly_points=16
    )
    opacity = 0.34
    photosphere = solve_gray_photosphere(source, opacity)
    column_above = upper_column_density_g_cm2(source, photosphere.scaled_height)
    assert np.allclose(opacity * column_above, 2.0 / 3.0, rtol=2.0e-13)
    assert np.allclose(
        photosphere.height_cm / source.scale_height_cm,
        photosphere.scaled_height,
        rtol=2.0e-15,
    )
    assert np.all(photosphere.scaled_height > 0.0)


def test_polytrope_gray_photosphere_reconstructs_target_optical_depth() -> None:
    source = constant_temperature_eccentric_annulus(
        1.0e14, 2.0e14, 0.8, 5.0e4, radial_points=5, anomaly_points=16
    )
    opacity = 0.34
    photosphere = solve_gray_photosphere(
        source,
        opacity,
        profile=RADIATION_PRESSURE_POLYTROPE_PROFILE,
    )
    column_above = upper_column_density_g_cm2(
        source,
        photosphere.scaled_height,
        RADIATION_PRESSURE_POLYTROPE_PROFILE,
    )
    assert np.allclose(opacity * column_above, 2.0 / 3.0, rtol=2.0e-12)
    assert np.all(photosphere.scaled_height < 3.0)


def test_marginally_thick_column_places_photosphere_at_midplane() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=3, anomaly_points=8
    )
    target = 2.0 / 3.0
    opacity = 2.0 * target / source.surface_density_g_cm2[0, 0]
    photosphere = solve_gray_photosphere(source, opacity, target)
    assert np.array_equal(photosphere.scaled_height, np.zeros(source.shape))
    assert np.array_equal(photosphere.height_cm, np.zeros(source.shape))


def test_optically_thin_column_is_rejected_without_clipping() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=3, anomaly_points=8
    )
    target = 2.0 / 3.0
    opacity = 0.9 * 2.0 * target / source.surface_density_g_cm2[0, 0]
    with pytest.raises(OpticallyThinColumnError, match="no upper"):
        solve_gray_photosphere(source, opacity, target)


@pytest.mark.parametrize("opacity", [0.0, -1.0, np.nan, np.inf])
def test_invalid_opacity_is_rejected(opacity: float) -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=3, anomaly_points=8
    )
    with pytest.raises(PhysicalDomainError, match="opacity_cm2_g"):
        solve_gray_photosphere(source, opacity)


def test_log_tail_inverse_remains_finite_at_extreme_optical_depth() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=3, anomaly_points=8
    )
    photosphere = solve_gray_photosphere(source, 1.0e246)
    assert np.all(np.isfinite(photosphere.scaled_height))
    assert np.all(photosphere.scaled_height > 30.0)


def test_photosphere_height_builds_a_valid_nonplanar_mesh() -> None:
    source = constant_temperature_eccentric_annulus(
        1.0e14, 2.0e14, 0.8, 5.0e4, radial_points=9, anomaly_points=64
    )
    photosphere = solve_gray_photosphere(source, 0.34)
    planar_mesh = build_orbital_surface_mesh(source)
    photosphere_mesh = build_orbital_surface_mesh(source, photosphere.height_cm)
    assert photosphere_mesh.total_area_cm2 > planar_mesh.total_area_cm2
    assert np.all(np.isfinite(photosphere_mesh.face_unit_normals))
