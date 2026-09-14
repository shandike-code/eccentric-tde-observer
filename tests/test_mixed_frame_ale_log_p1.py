from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

from eccentric_tde_observer.implicit_radiative_transfer_1d import (
    solve_implicit_ale_slab_step,
)
from eccentric_tde_observer.log_frequency_moments import (
    log_frequency_group_p1_gauss_node_values,
)
from eccentric_tde_observer.mixed_frame_ale import mixed_frame_frequency_stencil
from eccentric_tde_observer.mixed_frame_ale_log_p1 import (
    solve_mixed_frame_ale_log_p1_group_step,
)
from eccentric_tde_observer.mixed_frame_frequency import lorentz_ray_transform
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
)


def test_zero_velocity_log_p1_matches_two_stationary_node_solves():
    stencil = mixed_frame_frequency_stencil(0.1, 5000.0, 8, 0.0)
    mu, weight = gauss_legendre_mu_weights(4)
    groups = stencil.physical_group_count
    depth_points = 3
    old_edge = np.linspace(0.0, 1.0, depth_points + 1)
    frequency_coordinate = np.linspace(0.0, 1.0, groups)[:, None, None]
    depth_coordinate = np.linspace(0.0, 1.0, depth_points)[None, None, :]
    mean = np.broadcast_to(
        1.2 + 0.1 * frequency_coordinate + 0.05 * depth_coordinate,
        (groups, mu.size, depth_points),
    ).copy()
    moment = mean * (0.03 + 0.005 * mu[None, :, None])
    absorption_mean = np.full((groups, depth_points), 0.7)
    absorption_moment = np.full((groups, depth_points), 0.012)
    thermal_mean = np.full((groups, depth_points), 0.9)
    thermal_moment = np.full((groups, depth_points), 0.018)
    left_mean = mean[:, :, 0] * 0.95
    left_moment = moment[:, :, 0] * 0.95
    right_mean = mean[:, :, -1] * 1.03
    right_moment = moment[:, :, -1] * 1.03
    observed_iterations = []
    observed_states = {}

    def observe(iteration, mean_state, moment_state):
        assert mean_state.flags.writeable is False
        assert moment_state.flags.writeable is False
        observed_iterations.append(iteration)
        if iteration == 1:
            observed_states[iteration] = (
                np.array(mean_state, copy=True),
                np.array(moment_state, copy=True),
            )

    result = solve_mixed_frame_ale_log_p1_group_step(
        stencil,
        old_edge,
        old_edge,
        mu,
        weight,
        mean,
        moment,
        mean,
        moment,
        absorption_mean,
        absorption_moment,
        thermal_mean,
        thermal_moment,
        0.0,
        0.0,
        np.zeros(depth_points),
        0.2,
        left_exterior_mean_intensity_energy=left_mean,
        left_exterior_first_moment_intensity_energy=left_moment,
        right_exterior_mean_intensity_energy=right_mean,
        right_exterior_first_moment_intensity_energy=right_moment,
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-13,
        iteration_observer=observe,
    )
    identity_control = solve_mixed_frame_ale_log_p1_group_step(
        stencil,
        old_edge,
        old_edge,
        mu,
        weight,
        mean,
        moment,
        mean,
        moment,
        absorption_mean,
        absorption_moment,
        thermal_mean,
        thermal_moment,
        0.0,
        0.0,
        np.zeros(depth_points),
        0.2,
        left_exterior_mean_intensity_energy=left_mean,
        left_exterior_first_moment_intensity_energy=left_moment,
        right_exterior_mean_intensity_energy=right_mean,
        right_exterior_first_moment_intensity_energy=right_moment,
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-13,
        apply_intensity_lorentz=False,
        apply_extinction_lorentz=False,
        apply_emissivity_lorentz=False,
    )
    one_iteration = solve_mixed_frame_ale_log_p1_group_step(
        stencil,
        old_edge,
        old_edge,
        mu,
        weight,
        mean,
        moment,
        mean,
        moment,
        absorption_mean,
        absorption_moment,
        thermal_mean,
        thermal_moment,
        0.0,
        0.0,
        np.zeros(depth_points),
        0.2,
        left_exterior_mean_intensity_energy=left_mean,
        left_exterior_first_moment_intensity_energy=left_moment,
        right_exterior_mean_intensity_energy=right_mean,
        right_exterior_first_moment_intensity_energy=right_moment,
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-13,
        diagnostic_fixed_iteration_count=1,
    )
    initial_nodes = log_frequency_group_p1_gauss_node_values(mean, moment)
    absorption_nodes = log_frequency_group_p1_gauss_node_values(
        absorption_mean, absorption_moment
    )
    thermal_nodes = log_frequency_group_p1_gauss_node_values(
        thermal_mean, thermal_moment
    )
    left_nodes = log_frequency_group_p1_gauss_node_values(left_mean, left_moment)
    right_nodes = log_frequency_group_p1_gauss_node_values(right_mean, right_moment)
    expected_nodes = np.empty_like(initial_nodes)
    for node in range(2):
        expected_nodes[:, node] = solve_implicit_ale_slab_step(
            np.sqrt(
                stencil.active_lab_edge_hz[:-1]
                * stencil.active_lab_edge_hz[1:]
            ),
            old_edge,
            old_edge,
            mu,
            weight,
            initial_nodes[:, node],
            absorption_nodes[:, node],
            thermal_nodes[:, node] / absorption_nodes[:, node],
            1.0,
            0.2,
            left_exterior_intensity=left_nodes[:, node],
            right_exterior_intensity=right_nodes[:, node],
            propagation_speed_cm_s=1.0,
            linear_solver="source_iteration",
            iterative_tolerance=2.0e-13,
        ).final_intensity
    actual_nodes = log_frequency_group_p1_gauss_node_values(
        result.final_lab_mean_intensity_energy_density,
        result.final_lab_first_moment_intensity_energy_density,
    )
    error = np.max(np.abs(actual_nodes - expected_nodes)) / np.max(expected_nodes)
    assert error < 3.0e-12
    assert result.global_scale_normalized_coupled_residual < 3.0e-12
    assert result.total_relative_energy_ledger_residual < 3.0e-12
    assert result.final_limiter_activation_count == 0
    assert result.minimum_reconstructed_intensity_energy_density > 0.0
    assert np.array_equal(
        identity_control.final_lab_mean_intensity_energy_density,
        result.final_lab_mean_intensity_energy_density,
    )
    assert np.array_equal(
        identity_control.final_lab_first_moment_intensity_energy_density,
        result.final_lab_first_moment_intensity_energy_density,
    )
    assert observed_iterations[0] == 0
    assert observed_iterations[-1] == result.fixed_point_iterations
    assert observed_iterations == list(range(result.fixed_point_iterations + 1))
    assert result.fixed_point_converged is True
    assert identity_control.fixed_point_converged is True
    assert one_iteration.fixed_point_converged is False
    assert np.array_equal(
        one_iteration.final_lab_mean_intensity_energy_density,
        observed_states[1][0],
    )
    assert np.array_equal(
        one_iteration.final_lab_first_moment_intensity_energy_density,
        observed_states[1][1],
    )


def test_rigid_translation_preserves_constant_comoving_log_energy_density():
    beta_value = 0.05
    stencil = mixed_frame_frequency_stencil(0.1, 5000.0, 32, beta_value)
    mu, weight = gauss_legendre_mu_weights(8)
    depth_points = 1
    beta = np.full(depth_points, beta_value)
    transform = lorentz_ray_transform(mu, weight, beta)
    # 中文：共动系常数 Q_0 在实验室系为 Q=D^{-4}Q_0。
    outer_mean = np.broadcast_to(
        2.0 * transform.doppler_lab_to_comoving[None, ...] ** -4.0,
        (stencil.outer_lab_group_count, mu.size, depth_points),
    ).copy()
    outer_moment = np.zeros_like(outer_mean)
    active_slice = slice(
        stencil.active_outer_group_start, stencil.active_outer_group_stop
    )
    active_mean = outer_mean[active_slice]
    active_moment = outer_moment[active_slice]
    collision_shape = (stencil.comoving_collision_group_count, depth_points)
    absorption = np.full(collision_shape, 0.7)
    scattering = np.full(collision_shape, 0.4)
    duration = 0.1
    old_edge = np.array([0.0, 2.0])
    new_edge = old_edge + beta_value * duration
    result = solve_mixed_frame_ale_log_p1_group_step(
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        active_mean,
        active_moment,
        outer_mean,
        outer_moment,
        absorption,
        0.0,
        2.0 * absorption,
        0.0,
        scattering,
        0.0,
        beta,
        duration,
        periodic_spatial_boundary=True,
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-12,
    )
    error = np.max(
        np.abs(result.final_lab_mean_intensity_energy_density - active_mean)
    ) / np.max(active_mean)
    assert error < 3.0e-12
    assert np.max(
        np.abs(result.final_lab_first_moment_intensity_energy_density)
    ) < 1.0e-12
    assert result.global_scale_normalized_coupled_residual < 2.0e-10
    assert result.total_relative_energy_ledger_residual < 2.0e-10
    assert result.final_limiter_activation_count == 0
    assert result.minimum_reconstructed_intensity_energy_density > 0.0


def test_mixed_frame_ale_log_p1_uses_no_forbidden_repairs():
    path = Path("src/eccentric_tde_observer/mixed_frame_ale_log_p1.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = {
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert "np.nan_to_num" not in calls
    assert "np.clip" not in calls
    assert "numpy.nan_to_num" not in calls
    assert "numpy.clip" not in calls
