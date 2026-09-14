import numpy as np
import pytest

from eccentric_tde_observer.dynamic_column import (
    DepthDissipationProfile,
    build_zo_periodic_column_background,
    periodic_first_harmonic,
    solve_periodic_rate_network,
    two_state_periodic_control,
    validate_rate_generators,
)
from eccentric_tde_observer.reference_case import (
    build_strict_domain_reference_model,
    strict_domain_parameters,
)
from eccentric_tde_observer.source import PhysicalDomainError
from eccentric_tde_observer.zo_reference import build_zo_constant_e_reference_model


def test_periodic_column_kepler_time_map_and_period_closure():
    model = build_strict_domain_reference_model(9, 128)
    background = build_zo_periodic_column_background(model, 3)
    eccentricity = background.eccentricity
    expected_mean_anomaly = (
        background.eccentric_anomaly_rad
        - eccentricity * np.sin(background.eccentric_anomaly_rad)
    )

    assert np.array_equal(background.mean_anomaly_rad, expected_mean_anomaly)
    assert np.isclose(
        np.sum(background.step_duration_s),
        background.orbital_period_s,
        rtol=2.0e-15,
        atol=0.0,
    )
    assert np.all(background.step_duration_s > 0.0)


def test_circular_column_has_mean_anomaly_equal_to_eccentric_anomaly():
    model = build_zo_constant_e_reference_model(
        strict_domain_parameters(eccentricity=0.0),
        radial_points=5,
        anomaly_points=64,
    )
    background = build_zo_periodic_column_background(model, 2)

    assert np.array_equal(
        background.mean_anomaly_rad, background.eccentric_anomaly_rad
    )


def test_polytrope_column_mass_and_homologous_velocity_are_recovered():
    model = build_strict_domain_reference_model(5, 64)
    background = build_zo_periodic_column_background(model, 1)
    zeta = np.linspace(-3.0, 3.0, 4001)
    density = background.density_g_cm3(zeta)
    recovered_surface_density = np.trapezoid(
        density,
        background.scale_height_cm[:, None] * zeta[None, :],
        axis=1,
    )
    velocity = background.homologous_vertical_velocity_cm_s(
        np.array([-1.0, 0.0, 1.0])
    )

    assert np.allclose(
        recovered_surface_density,
        background.surface_density_g_cm2,
        rtol=2.0e-13,
        atol=0.0,
    )
    assert np.array_equal(velocity[:, 1], np.zeros(background.phase_points))
    assert np.array_equal(
        velocity[:, 2],
        background.scale_height_cm * background.logarithmic_breathing_rate_s1,
    )


def test_depth_dissipation_interface_rejects_post_hoc_normalization():
    valid = DepthDissipationProfile(
        mass_fraction=np.linspace(0.0, 1.0, 9),
        differential_power_fraction=np.ones(9),
        provenance="uniform numerical control [A-control]",
    )
    assert np.isclose(
        np.trapezoid(valid.differential_power_fraction, valid.mass_fraction),
        1.0,
        rtol=0.0,
        atol=2.0e-15,
    )
    with pytest.raises(PhysicalDomainError, match="integral must equal one"):
        DepthDissipationProfile(
            mass_fraction=np.linspace(0.0, 1.0, 9),
            differential_power_fraction=np.full(9, 0.9),
            provenance="invalid control",
        )


def test_rate_generator_rejects_negative_transition_and_nonconservation():
    with pytest.raises(PhysicalDomainError, match="off-diagonal"):
        validate_rate_generators([[-1.0, -0.1], [1.0, 0.1]])
    with pytest.raises(PhysicalDomainError, match="columns must sum to zero"):
        validate_rate_generators([[-1.0, 0.2], [0.9, -0.2]])


def test_periodic_two_state_control_is_positive_conservative_and_analytic():
    phase_points = 256
    phase = np.linspace(0.0, 2.0 * np.pi, phase_points, endpoint=False)
    duration = np.full(phase_points, 1.0 / phase_points)
    control = two_state_periodic_control(phase, 1.0, 0.1)
    solution = solve_periodic_rate_network(
        control.rate_matrices_s1,
        duration,
        [0.5, 0.5],
    )
    mean, amplitude, lag = periodic_first_harmonic(
        solution.population[:, 1], phase, duration
    )

    assert solution.minimum_population > 0.0
    assert solution.maximum_particle_conservation_residual < 1.0e-12
    assert solution.cycle_residual < 1.0e-11
    assert np.max(
        np.abs(solution.population[:, 1] - control.analytic_excited_fraction)
    ) < 3.3e-5
    assert np.isclose(mean, 0.5, rtol=0.0, atol=3.0e-6)
    assert np.isclose(
        amplitude / 0.4,
        control.analytic_amplitude_ratio,
        rtol=4.0e-4,
        atol=0.0,
    )
    assert np.isclose(lag, control.analytic_phase_lag_rad, rtol=4.0e-4, atol=0.0)


def test_two_state_time_grid_has_second_order_convergence():
    errors = []
    for phase_points in (32, 64, 128):
        phase = np.linspace(0.0, 2.0 * np.pi, phase_points, endpoint=False)
        duration = np.full(phase_points, 1.0 / phase_points)
        control = two_state_periodic_control(phase, 1.0, 0.1)
        solution = solve_periodic_rate_network(
            control.rate_matrices_s1, duration, [0.5, 0.5]
        )
        errors.append(
            float(
                np.max(
                    np.abs(
                        solution.population[:, 1]
                        - control.analytic_excited_fraction
                    )
                )
            )
        )

    assert errors[0] / errors[1] > 3.9
    assert errors[1] / errors[2] > 3.9


def test_periodic_solution_loses_initial_condition_memory():
    phase_points = 64
    phase = np.linspace(0.0, 2.0 * np.pi, phase_points, endpoint=False)
    duration = np.full(phase_points, 2.0 / phase_points)
    control = two_state_periodic_control(phase, 2.0, 0.3)
    neutral_start = solve_periodic_rate_network(
        control.rate_matrices_s1, duration, [1.0, 0.0]
    )
    excited_start = solve_periodic_rate_network(
        control.rate_matrices_s1, duration, [0.0, 1.0]
    )

    assert np.allclose(
        neutral_start.population,
        excited_start.population,
        rtol=0.0,
        atol=2.0e-11,
    )
