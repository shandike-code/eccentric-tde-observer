from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.adaptive import (
    build_orthographic_triangle_index,
    recursive_triangle_centroids,
    render_adaptive_source_surface_quadrature,
    render_source_surface_quadrature,
    source_surface_blackbody_sed,
    trace_orthographic_points,
)
from eccentric_tde_observer.fixtures import constant_temperature_circular_annulus
from eccentric_tde_observer.faceon import face_on_blackbody_sed
from eccentric_tde_observer.geometry import (
    build_orbital_surface_mesh,
    build_surface_mesh_from_vertices_faces,
)
from eccentric_tde_observer.observer import Observer, unobscured_blackbody_sed
from eccentric_tde_observer.source import PhysicalDomainError
from eccentric_tde_observer.source import ZOSourceGrid


PARSEC_CM = 3.0856775814913673e18


def _layered_square_mesh():
    vertices = np.array(
        [
            [-0.5, -0.5, 0.0],
            [0.5, -0.5, 0.0],
            [0.5, 0.5, 0.0],
            [-0.5, 0.5, 0.0],
            [-0.13, -0.5, 1.0],
            [0.5, -0.5, 1.0],
            [0.5, 0.5, 1.0],
            [-0.13, 0.5, 1.0],
        ]
    )
    faces = np.array([[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7]])
    return build_surface_mesh_from_vertices_faces(vertices, faces)


def test_recursive_triangle_centroids_are_equal_area_barycentric_nodes() -> None:
    for level in range(4):
        nodes = recursive_triangle_centroids(level)
        assert nodes.shape == (4**level, 3)
        assert np.all(nodes > 0.0)
        assert np.allclose(np.sum(nodes, axis=1), 1.0, atol=2.0e-16)
        assert np.allclose(np.mean(nodes, axis=0), 1.0 / 3.0)
    with pytest.raises(PhysicalDomainError, match="subdivision_level"):
        recursive_triangle_centroids(-1)


def test_point_query_selects_front_layer_and_explicitly_marks_misses() -> None:
    mesh = _layered_square_mesh()
    observer = Observer(1.0, 0.0, 0.0)
    index = build_orthographic_triangle_index(mesh, observer, bins_long_axis=16)
    faces, depths = trace_orthographic_points(
        index,
        np.array([0.0, 0.0, 0.0, 0.0]),
        np.array([0.4, 0.0, -0.4, -2.0]),
    )
    assert faces[0] in (0, 1)
    assert faces[1] in (2, 3)
    assert faces[2] in (2, 3)
    assert faces[3] == -1
    assert depths[0] == 0.0
    assert depths[1] == 1.0
    assert depths[2] == 1.0
    assert depths[3] == 0.0


def test_surface_quadrature_recovers_union_area_with_partial_occultation() -> None:
    mesh = _layered_square_mesh()
    observer = Observer(1.0, 0.0, 0.0)
    errors = []
    for level in range(4):
        quadrature = render_source_surface_quadrature(
            mesh, observer, subdivision_level=level, bins_long_axis=32
        )
        errors.append(abs(quadrature.visible_projected_area_cm2 - 1.0))
        assert np.isclose(
            np.sum(quadrature.vertex_projected_area_weights_cm2),
            quadrature.visible_projected_area_cm2,
            rtol=2.0e-14,
        )
    assert errors[-1] < 1.0e-2
    assert errors[-1] < errors[0]


def test_adaptive_boundary_refinement_converges_partial_occultation_area() -> None:
    mesh = _layered_square_mesh()
    observer = Observer(1.0, 0.0, 0.0)
    index = build_orthographic_triangle_index(mesh, observer, bins_long_axis=32)
    errors = []
    ray_counts = []
    for depth in range(1, 6):
        quadrature = render_adaptive_source_surface_quadrature(
            mesh,
            observer,
            maximum_subdivision_depth=depth,
            triangle_index=index,
        )
        errors.append(abs(quadrature.visible_projected_area_cm2 - 1.0))
        ray_counts.append(quadrature.ray_count)
    assert errors[-1] < 6.0e-3
    assert errors[-1] < errors[0]
    assert ray_counts[-1] < mesh.faces.shape[0] * 7 * 4**4


def test_unobscured_nonuniform_temperature_sed_is_resolved_in_source_space() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14,
        2.0e14,
        5.0e4,
        radial_points=5,
        anomaly_points=32,
    )
    temperature = np.array(source.effective_temperature_k, copy=True)
    temperature[0, 0] = 5.0e6
    source = ZOSourceGrid(
        semimajor_axis_cm=source.semimajor_axis_cm,
        eccentric_anomaly_rad=source.eccentric_anomaly_rad,
        eccentricity=source.eccentricity,
        jacobian=source.jacobian,
        surface_density_g_cm2=source.surface_density_g_cm2,
        scale_height_cm=source.scale_height_cm,
        effective_temperature_k=temperature,
        apsidal_angle_rad=source.apsidal_angle_rad,
        eccentricity_gradient_per_cm=source.eccentricity_gradient_per_cm,
        apsidal_gradient_per_cm=source.apsidal_gradient_per_cm,
        label="single-hot-vertex source-space quadrature fixture",
        provenance="analytic source-space quadrature fixture [A/V]",
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(100.0e6 * PARSEC_CM, 0.0, 0.0)
    quadrature = render_source_surface_quadrature(
        mesh, observer, subdivision_level=0, bins_long_axis=32
    )
    frequency = np.array([5.0e14, 1.0e17])
    adaptive = source_surface_blackbody_sed(
        source, mesh, observer, quadrature, frequency
    )
    unobscured = unobscured_blackbody_sed(source, mesh, observer, frequency)
    assert np.allclose(
        adaptive.flux_density_erg_s_cm2_hz,
        unobscured.flux_density_erg_s_cm2_hz,
        rtol=3.0e-14,
    )


def test_face_on_circular_limit_recovers_corrected_source_spectrum() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14,
        2.0e14,
        5.0e4,
        radial_points=17,
        anomaly_points=256,
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(100.0e6 * PARSEC_CM, 0.0, 0.0)
    quadrature = render_adaptive_source_surface_quadrature(
        mesh,
        observer,
        maximum_subdivision_depth=2,
        bins_long_axis=64,
    )
    frequency = np.array([5.0e14, 1.0e16, 1.0e17])
    adaptive = source_surface_blackbody_sed(
        source, mesh, observer, quadrature, frequency
    )
    corrected = face_on_blackbody_sed(source, frequency)
    assert np.allclose(
        adaptive.isotropic_equivalent_lnu_erg_s_hz,
        corrected.isotropic_equivalent_lnu_erg_s_hz,
        rtol=1.1e-4,
    )


def test_surface_quadrature_rejects_mismatched_observer_index() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=5, anomaly_points=16
    )
    mesh = build_orbital_surface_mesh(source)
    first = Observer(1.0, 0.1, 0.2)
    second = Observer(1.0, 0.2, 0.2)
    index = build_orthographic_triangle_index(mesh, first, bins_long_axis=16)
    with pytest.raises(PhysicalDomainError, match="observer"):
        render_source_surface_quadrature(
            mesh,
            second,
            subdivision_level=0,
            triangle_index=index,
        )


def test_frequency_shift_factor_one_preserves_surface_sed_exactly() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=5, anomaly_points=32
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(100.0e6 * PARSEC_CM, 0.3, 0.4)
    quadrature = render_source_surface_quadrature(
        mesh, observer, subdivision_level=0, bins_long_axis=32
    )
    frequency = np.geomspace(1.0e14, 1.0e18, 21)
    baseline = source_surface_blackbody_sed(
        source, mesh, observer, quadrature, frequency
    )
    shifted = source_surface_blackbody_sed(
        source,
        mesh,
        observer,
        quadrature,
        frequency,
        frequency_shift_factor=np.ones(source.shape),
    )
    assert np.array_equal(
        shifted.flux_density_erg_s_cm2_hz,
        baseline.flux_density_erg_s_cm2_hz,
    )


def test_constant_frequency_shift_rescales_blackbody_temperature() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=5, anomaly_points=32
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(100.0e6 * PARSEC_CM, 0.0, 0.0)
    quadrature = render_source_surface_quadrature(
        mesh, observer, subdivision_level=0, bins_long_axis=32
    )
    frequency = np.geomspace(1.0e14, 1.0e18, 21)
    shift_value = 1.05
    shifted = source_surface_blackbody_sed(
        source,
        mesh,
        observer,
        quadrature,
        frequency,
        frequency_shift_factor=np.full(source.shape, shift_value),
    )
    hotter_source = ZOSourceGrid(
        semimajor_axis_cm=source.semimajor_axis_cm,
        eccentric_anomaly_rad=source.eccentric_anomaly_rad,
        eccentricity=source.eccentricity,
        jacobian=source.jacobian,
        surface_density_g_cm2=source.surface_density_g_cm2,
        scale_height_cm=source.scale_height_cm,
        effective_temperature_k=shift_value * source.effective_temperature_k,
        eccentricity_gradient_per_cm=source.eccentricity_gradient_per_cm,
        apsidal_gradient_per_cm=source.apsidal_gradient_per_cm,
    )
    expected = source_surface_blackbody_sed(
        hotter_source, mesh, observer, quadrature, frequency
    )
    assert np.allclose(
        shifted.flux_density_erg_s_cm2_hz,
        expected.flux_density_erg_s_cm2_hz,
        rtol=2.0e-15,
    )


def test_invalid_frequency_shift_factor_is_rejected_without_repair() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=5, anomaly_points=32
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(1.0e26, 0.0, 0.0)
    quadrature = render_source_surface_quadrature(
        mesh, observer, subdivision_level=0, bins_long_axis=32
    )
    invalid = np.ones(source.shape)
    invalid[0, 0] = np.nan
    with pytest.raises(PhysicalDomainError, match="finite and strictly positive"):
        source_surface_blackbody_sed(
            source,
            mesh,
            observer,
            quadrature,
            np.array([1.0e15]),
            frequency_shift_factor=invalid,
        )
    with pytest.raises(PhysicalDomainError, match="match the source grid"):
        source_surface_blackbody_sed(
            source,
            mesh,
            observer,
            quadrature,
            np.array([1.0e15]),
            frequency_shift_factor=np.ones(3),
        )


def test_spectral_hardening_one_preserves_surface_sed_exactly() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=5, anomaly_points=32
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(100.0e6 * PARSEC_CM, 0.2, 0.3)
    quadrature = render_source_surface_quadrature(
        mesh, observer, subdivision_level=0, bins_long_axis=32
    )
    frequency = np.geomspace(1.0e14, 1.0e18, 21)
    baseline = source_surface_blackbody_sed(
        source, mesh, observer, quadrature, frequency
    )
    hardened = source_surface_blackbody_sed(
        source,
        mesh,
        observer,
        quadrature,
        frequency,
        spectral_hardening_factor=np.ones(source.shape),
    )
    assert np.array_equal(
        hardened.flux_density_erg_s_cm2_hz,
        baseline.flux_density_erg_s_cm2_hz,
    )


def test_constant_spectral_hardening_is_a_diluted_hotter_blackbody() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=5, anomaly_points=32
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(100.0e6 * PARSEC_CM, 0.0, 0.0)
    quadrature = render_source_surface_quadrature(
        mesh, observer, subdivision_level=0, bins_long_axis=32
    )
    frequency = np.geomspace(1.0e14, 1.0e18, 21)
    hardening_value = 1.6
    hardened = source_surface_blackbody_sed(
        source,
        mesh,
        observer,
        quadrature,
        frequency,
        spectral_hardening_factor=np.full(source.shape, hardening_value),
    )
    hotter_source = ZOSourceGrid(
        semimajor_axis_cm=source.semimajor_axis_cm,
        eccentric_anomaly_rad=source.eccentric_anomaly_rad,
        eccentricity=source.eccentricity,
        jacobian=source.jacobian,
        surface_density_g_cm2=source.surface_density_g_cm2,
        scale_height_cm=source.scale_height_cm,
        effective_temperature_k=hardening_value * source.effective_temperature_k,
        eccentricity_gradient_per_cm=source.eccentricity_gradient_per_cm,
        apsidal_gradient_per_cm=source.apsidal_gradient_per_cm,
    )
    expected = source_surface_blackbody_sed(
        hotter_source, mesh, observer, quadrature, frequency
    )
    assert np.allclose(
        hardened.flux_density_erg_s_cm2_hz,
        expected.flux_density_erg_s_cm2_hz / hardening_value**4,
        rtol=2.0e-15,
    )


def test_invalid_spectral_hardening_is_rejected_without_clipping() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=5, anomaly_points=32
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(1.0e26, 0.0, 0.0)
    quadrature = render_source_surface_quadrature(
        mesh, observer, subdivision_level=0, bins_long_axis=32
    )
    hardening = np.ones(source.shape)
    hardening[0, 0] = 0.99
    with pytest.raises(PhysicalDomainError, match="at least one"):
        source_surface_blackbody_sed(
            source,
            mesh,
            observer,
            quadrature,
            np.array([1.0e15]),
            spectral_hardening_factor=hardening,
        )
