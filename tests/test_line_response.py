from __future__ import annotations

import numpy as np

from eccentric_tde_observer.adaptive import (
    render_adaptive_source_surface_quadrature,
    render_source_surface_quadrature,
)
from eccentric_tde_observer.fixtures import constant_temperature_circular_annulus
from eccentric_tde_observer.geometry import (
    build_orbital_surface_mesh,
    build_surface_mesh_from_vertices_faces,
)
from eccentric_tde_observer.line_response import (
    arcsine_ring_bin_probabilities,
    fully_ionized_emission_measure_line_weight,
    geometric_uniform_line_weight,
    hydrogen_thermal_velocity_dispersion_cm_s,
    line_diagnostics,
    numerical_newtonian_ring_bin_probabilities,
    observer_line_profile,
    velocity_grid_cm_s,
    zo_thermal_power_line_weight,
)
from eccentric_tde_observer.observer import Observer
from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model
from eccentric_tde_observer.relativity import (
    homologous_vertical_velocity_cm_s,
    straight_ray_frequency_shift,
)
from eccentric_tde_observer.vertical import RADIATION_PRESSURE_POLYTROPE_PROFILE


PARSEC_CM = 3.0856775814913673e18


def test_face_on_newtonian_ring_collapses_to_one_bin() -> None:
    velocity = velocity_grid_cm_s(-100.0, 100.0, 201)
    numerical = numerical_newtonian_ring_bin_probabilities(
        velocity, 1.0e9, 0.0, azimuth_points=4096
    )
    assert np.count_nonzero(numerical) == 1
    assert velocity[np.argmax(numerical)] == 0.0
    assert np.sum(numerical) == 1.0


def test_inclined_newtonian_ring_recovers_finite_bin_arcsine_kernel() -> None:
    velocity = velocity_grid_cm_s(-12_000.0, 12_000.0, 2401)
    projected_speed = 1.0e9
    analytic = arcsine_ring_bin_probabilities(velocity, projected_speed)
    numerical = numerical_newtonian_ring_bin_probabilities(
        velocity,
        projected_speed / np.sin(np.deg2rad(45.0)),
        np.deg2rad(45.0),
        azimuth_points=1_000_000,
    )
    assert np.sum(np.abs(numerical - analytic)) < 3.0e-3
    assert np.array_equal(numerical, numerical[::-1])


def _line_fixture():
    source = constant_temperature_circular_annulus(
        1.0e14,
        2.0e14,
        5.0e4,
        radial_points=9,
        anomaly_points=64,
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(100.0e6 * PARSEC_CM, 0.0, 0.0)
    quadrature = render_source_surface_quadrature(
        mesh, observer, subdivision_level=1, bins_long_axis=64
    )
    los_velocity = (
        3.0e8 * np.cos(source.eccentric_anomaly_rad)[None, :]
        * np.ones((source.shape[0], 1))
    )
    shift = 1.0 / (1.0 + los_velocity / LIGHT_SPEED_CM_S)
    return source, mesh, observer, quadrature, shift


def test_delta_line_frequency_integral_recovers_direct_g4_weight() -> None:
    source, mesh, observer, quadrature, shift = _line_fixture()
    profile = observer_line_profile(
        source,
        mesh,
        quadrature,
        shift,
        geometric_uniform_line_weight(source),
        velocity_grid_cm_s(-20_000.0, 20_000.0, 4001),
        observer_distance_cm=observer.distance_cm,
    )
    assert abs(profile.energy_relative_residual) < 3.0e-15
    assert np.isclose(
        profile.frequency_integrated_flux_erg_s_cm2,
        profile.direct_g4_integrated_flux_erg_s_cm2,
        rtol=3.0e-15,
    )


def test_frequency_wavelength_density_jacobian_is_exact() -> None:
    source, mesh, observer, quadrature, shift = _line_fixture()
    profile = observer_line_profile(
        source,
        mesh,
        quadrature,
        shift,
        geometric_uniform_line_weight(source),
        velocity_grid_cm_s(-20_000.0, 20_000.0, 4001),
        observer_distance_cm=observer.distance_cm,
    )
    left = (
        profile.wavelength_angstrom
        * profile.flux_density_flambda_erg_s_cm2_angstrom
    )
    right = profile.frequency_hz * profile.flux_density_fnu_erg_s_cm2_hz
    assert np.allclose(left, right, rtol=3.0e-15, atol=0.0)


def test_three_controlled_weights_and_local_thermal_width_are_physical() -> None:
    source, mesh, observer, quadrature, shift = _line_fixture()
    uniform = geometric_uniform_line_weight(source)
    thermal_power = zo_thermal_power_line_weight(source)
    emission_measure = fully_ionized_emission_measure_line_weight(source)
    for weight in (uniform, thermal_power, emission_measure):
        assert weight.shape == source.shape
        assert np.all(np.isfinite(weight))
        assert np.all(weight > 0.0)
    sigma = hydrogen_thermal_velocity_dispersion_cm_s(
        source.effective_temperature_k
    )
    profile = observer_line_profile(
        source,
        mesh,
        quadrature,
        shift,
        emission_measure,
        velocity_grid_cm_s(-20_000.0, 20_000.0, 4001),
        observer_distance_cm=observer.distance_cm,
        local_sigma_velocity_cm_s=sigma,
    )
    assert abs(profile.energy_relative_residual) < 1.0e-12


def _small_eccentricity_profile(eccentricity: float):
    model = build_strict_domain_reference_model(
        9, 128, eccentricity=eccentricity
    )
    photosphere = solve_gray_photosphere(
        model.source,
        model.parameters.opacity_cm2_g,
        2.0 / 3.0,
        RADIATION_PRESSURE_POLYTROPE_PROFILE,
    )
    mesh = build_orbital_surface_mesh(model.source, photosphere.height_cm)
    vertical_velocity = homologous_vertical_velocity_cm_s(
        model.source,
        photosphere.height_cm,
        model.breathing.log_height_derivative_per_rad,
        model.parameters.black_hole_mass_msun,
    )
    observer = Observer(100.0e6 * PARSEC_CM, np.deg2rad(45.0), 0.0)
    quadrature = render_source_surface_quadrature(
        mesh, observer, subdivision_level=1, bins_long_axis=64
    )
    shift = straight_ray_frequency_shift(
        model.source,
        observer,
        model.parameters.black_hole_mass_msun,
        vertical_velocity_cm_s=vertical_velocity,
    )
    return observer_line_profile(
        model.source,
        mesh,
        quadrature,
        shift.frequency_shift_factor,
        geometric_uniform_line_weight(model.source),
        velocity_grid_cm_s(-30_000.0, 30_000.0, 1201),
        observer_distance_cm=observer.distance_cm,
        local_sigma_velocity_cm_s=2.0e7,
    )


def test_full_zo_line_kernel_is_continuous_as_eccentricity_tends_to_zero() -> None:
    circular = _small_eccentricity_profile(0.0)
    nearly_circular = _small_eccentricity_profile(1.0e-5)
    difference = np.mean(
        np.abs(
            circular.normalized_flux_per_velocity
            - nearly_circular.normalized_flux_per_velocity
        )
    )
    assert difference < 1.0e-4


def test_line_flux_converges_across_an_analytic_self_shadow_boundary() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14,
        2.0e14,
        5.0e4,
        radial_points=2,
        anomaly_points=4,
    )
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
    mesh = build_surface_mesh_from_vertices_faces(
        vertices, faces, vertex_grid_shape=source.shape
    )
    observer = Observer(1.0, 0.0, 0.0)
    velocity = velocity_grid_cm_s(-2_000.0, 2_000.0, 401)
    shift = np.empty(source.shape)
    shift.reshape(-1)[:4] = 1.0 / (1.0 - 5.0e7 / LIGHT_SPEED_CM_S)
    shift.reshape(-1)[4:] = 1.0 / (1.0 + 5.0e7 / LIGHT_SPEED_CM_S)
    blue_fraction_errors = []
    for depth in (1, 3, 5, 7):
        quadrature = render_adaptive_source_surface_quadrature(
            mesh,
            observer,
            maximum_subdivision_depth=depth,
            bins_long_axis=32,
        )
        profile = observer_line_profile(
            source,
            mesh,
            quadrature,
            shift,
            geometric_uniform_line_weight(source),
            velocity,
            observer_distance_cm=observer.distance_cm,
        )
        blue_fraction = float(
            np.sum(
                profile.bin_integrated_flux_erg_s_cm2[
                    profile.velocity_cm_s < 0.0
                ]
            )
            / profile.frequency_integrated_flux_erg_s_cm2
        )
        blue_g = shift.reshape(-1)[0]
        red_g = shift.reshape(-1)[-1]
        exact_blue_fraction = 0.37 * blue_g**4 / (
            0.37 * blue_g**4 + 0.63 * red_g**4
        )
        blue_fraction_errors.append(abs(blue_fraction - exact_blue_fraction))
    assert blue_fraction_errors[-1] < 1.0e-3
    assert blue_fraction_errors[-1] < blue_fraction_errors[0]


def test_emitter_frame_local_width_maps_to_observer_velocity_with_one_over_g() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14,
        2.0e14,
        5.0e4,
        radial_points=5,
        anomaly_points=32,
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(100.0e6 * PARSEC_CM, 0.0, 0.0)
    quadrature = render_source_surface_quadrature(
        mesh, observer, subdivision_level=1, bins_long_axis=64
    )
    shift_value = 1.02
    emitted_sigma = 3.0e7
    profile = observer_line_profile(
        source,
        mesh,
        quadrature,
        np.full(source.shape, shift_value),
        geometric_uniform_line_weight(source),
        velocity_grid_cm_s(-20_000.0, 20_000.0, 4001),
        observer_distance_cm=observer.distance_cm,
        local_sigma_velocity_cm_s=np.full(source.shape, emitted_sigma),
    )
    measured = line_diagnostics(profile).width_cm_s
    assert np.isclose(measured, emitted_sigma / shift_value, rtol=2.0e-4)
