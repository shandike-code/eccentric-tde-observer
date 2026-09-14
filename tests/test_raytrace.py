from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.fixtures import constant_temperature_circular_annulus
from eccentric_tde_observer.geometry import (
    build_orbital_surface_mesh,
    build_surface_mesh_from_vertices_faces,
)
from eccentric_tde_observer.observer import (
    Observer,
    unobscured_blackbody_sed,
    unobscured_projected_area_cm2,
)
from eccentric_tde_observer.raytrace import (
    observer_image_basis,
    raytraced_blackbody_sed,
    render_orthographic_surface,
)
from eccentric_tde_observer.radiation import STEFAN_BOLTZMANN_ERG_S_CM2_K4
from eccentric_tde_observer.source import PhysicalDomainError


PARSEC_CM = 3.0856775814913673e18


def _unit_square_mesh(z_cm: float = 0.0):
    vertices = np.array(
        [
            [-0.5, -0.5, z_cm],
            [0.5, -0.5, z_cm],
            [0.5, 0.5, z_cm],
            [-0.5, 0.5, z_cm],
        ]
    )
    faces = np.array([[0, 1, 2], [0, 2, 3]])
    return build_surface_mesh_from_vertices_faces(vertices, faces)


def test_observer_image_basis_is_orthonormal_and_right_handed() -> None:
    observer = Observer(1.0, np.deg2rad(63.0), 1.7)
    basis_u, basis_v = observer_image_basis(observer)
    direction = observer.direction_from_source
    basis = np.stack((basis_u, basis_v, direction))
    assert np.allclose(basis @ basis.T, np.eye(3), atol=3.0e-16)
    assert np.allclose(np.cross(basis_u, basis_v), direction, atol=3.0e-16)


def test_face_on_annulus_projected_area_converges_to_analytic_area() -> None:
    inner = 1.0e14
    outer = 2.0e14
    source = constant_temperature_circular_annulus(
        inner,
        outer,
        5.0e4,
        radial_points=17,
        anomaly_points=128,
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(100.0e6 * PARSEC_CM, 0.0, 0.0)
    analytic_area = np.pi * (outer**2 - inner**2)
    errors = []
    for pixels in (64, 128, 256):
        image = render_orthographic_surface(mesh, observer, pixels)
        errors.append(abs(image.visible_projected_area_cm2 / analytic_area - 1.0))
    assert errors[-1] < 8.0e-3
    assert errors[-1] < errors[0]


def test_tilted_square_recovers_analytic_projected_area() -> None:
    mesh = _unit_square_mesh()
    inclination = np.deg2rad(57.0)
    observer = Observer(1.0, inclination, 0.0)
    image = render_orthographic_surface(mesh, observer, 256)
    expected = np.cos(inclination)
    assert np.isclose(
        image.visible_projected_area_cm2, expected, rtol=8.0e-3
    )


def test_front_layer_completely_occults_identical_back_layer() -> None:
    vertices = np.array(
        [
            [-0.5, -0.5, 0.0],
            [0.5, -0.5, 0.0],
            [0.5, 0.5, 0.0],
            [-0.5, 0.5, 0.0],
            [-0.5, -0.5, 1.0],
            [0.5, -0.5, 1.0],
            [0.5, 0.5, 1.0],
            [-0.5, 0.5, 1.0],
        ]
    )
    faces = np.array([[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7]])
    mesh = build_surface_mesh_from_vertices_faces(vertices, faces)
    observer = Observer(1.0, 0.0, 0.0)
    image = render_orthographic_surface(mesh, observer, 128)
    assert image.hit_count == image.ray_count
    assert image.emitting_count == image.ray_count
    assert set(np.unique(image.frontmost_face_index)) == {2, 3}
    assert image.visible_projected_area_cm2 == 1.0
    assert unobscured_projected_area_cm2(mesh, observer) == 2.0


def test_raytraced_constant_temperature_sed_has_geometric_normalization() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14,
        2.0e14,
        5.0e4,
        radial_points=17,
        anomaly_points=64,
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(100.0e6 * PARSEC_CM, np.deg2rad(61.0), 0.7)
    image = render_orthographic_surface(mesh, observer, 192)
    frequency = np.geomspace(1.0e14, 1.0e17, 21)
    raytraced = raytraced_blackbody_sed(
        source, mesh, observer, image, frequency
    )
    unobscured = unobscured_blackbody_sed(source, mesh, observer, frequency)
    expected_ratio = image.visible_projected_area_cm2 / unobscured_projected_area_cm2(
        mesh, observer
    )
    assert np.allclose(
        raytraced.flux_density_erg_s_cm2_hz
        / unobscured.flux_density_erg_s_cm2_hz,
        expected_ratio,
        rtol=3.0e-15,
    )


def test_raytraced_frequency_integral_recovers_blackbody_energy_flux() -> None:
    temperature = 5.0e4
    source = constant_temperature_circular_annulus(
        1.0e14,
        2.0e14,
        temperature,
        radial_points=5,
        anomaly_points=32,
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(100.0e6 * PARSEC_CM, np.deg2rad(50.0), 0.3)
    image = render_orthographic_surface(mesh, observer, 64)
    frequency = np.geomspace(1.0e10, 1.0e20, 4001)
    spectrum = raytraced_blackbody_sed(
        source, mesh, observer, image, frequency
    )
    numerical_flux = np.trapezoid(
        spectrum.flux_density_erg_s_cm2_hz, frequency
    )
    analytic_flux = (
        STEFAN_BOLTZMANN_ERG_S_CM2_K4
        * temperature**4
        / np.pi
        * image.visible_projected_area_cm2
        / observer.distance_cm**2
    )
    assert np.isclose(numerical_flux, analytic_flux, rtol=1.0e-5)


def test_ray_image_has_finite_buffers_without_masking_invalid_values() -> None:
    mesh = _unit_square_mesh()
    observer = Observer(1.0, np.deg2rad(40.0), 0.4)
    image = render_orthographic_surface(mesh, observer, 64)
    assert np.all(np.isfinite(image.frontmost_depth_cm))
    assert np.all(np.isfinite(image.frontmost_barycentric))
    assert np.all(image.frontmost_face_index[~image.hit_mask] == -1)
    assert np.all(image.frontmost_face_index[image.hit_mask] >= 0)
    weights = image.frontmost_barycentric[image.hit_mask]
    assert np.allclose(np.sum(weights, axis=1), 1.0, atol=3.0e-15)
    assert np.isclose(
        np.sum(image.vertex_projected_area_weights_cm2),
        image.visible_projected_area_cm2,
        rtol=3.0e-15,
    )


def test_sed_rejects_ray_image_from_different_mesh_geometry() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=5, anomaly_points=16
    )
    planar_mesh = build_orbital_surface_mesh(source)
    elevated_mesh = build_orbital_surface_mesh(source, source.scale_height_cm)
    observer = Observer(100.0e6 * PARSEC_CM, np.deg2rad(50.0), 0.3)
    planar_image = render_orthographic_surface(planar_mesh, observer, 64)
    with pytest.raises(PhysicalDomainError, match="mesh geometry"):
        raytraced_blackbody_sed(
            source,
            elevated_mesh,
            observer,
            planar_image,
            np.array([1.0e15]),
        )
