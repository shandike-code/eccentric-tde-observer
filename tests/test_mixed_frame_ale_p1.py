from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

from eccentric_tde_observer.implicit_radiative_transfer_1d import (
    solve_implicit_ale_slab_step,
)
from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil,
)
from eccentric_tde_observer.mixed_frame_ale_p1 import (
    solve_mixed_frame_ale_p1_group_step,
)
from eccentric_tde_observer.mixed_frame_frequency import (
    frequency_group_p1_gauss_node_values,
    lorentz_ray_transform,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
)


def test_zero_velocity_p1_step_matches_two_stationary_gauss_node_solves():
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
    absorption = np.full((groups, depth_points), 0.7)
    thermal = np.full((groups, depth_points), 0.9)
    left_mean = mean[:, :, 0] * 0.95
    left_moment = moment[:, :, 0] * 0.95
    right_mean = mean[:, :, -1] * 1.03
    right_moment = moment[:, :, -1] * 1.03
    result = solve_mixed_frame_ale_p1_group_step(
        stencil,
        old_edge,
        old_edge,
        mu,
        weight,
        mean,
        moment,
        mean,
        moment,
        absorption,
        0.0,
        thermal,
        0.0,
        0.0,
        0.0,
        np.zeros(depth_points),
        0.2,
        left_exterior_mean_intensity=left_mean,
        left_exterior_first_moment_intensity=left_moment,
        right_exterior_mean_intensity=right_mean,
        right_exterior_first_moment_intensity=right_moment,
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-13,
    )
    initial_nodes = frequency_group_p1_gauss_node_values(mean, moment)
    left_nodes = frequency_group_p1_gauss_node_values(left_mean, left_moment)
    right_nodes = frequency_group_p1_gauss_node_values(right_mean, right_moment)
    expected_nodes = np.empty_like(initial_nodes)
    for node in range(2):
        expected_nodes[:, node] = solve_implicit_ale_slab_step(
            0.5
            * (
                stencil.active_lab_edge_hz[:-1]
                + stencil.active_lab_edge_hz[1:]
            ),
            old_edge,
            old_edge,
            mu,
            weight,
            initial_nodes[:, node],
            absorption,
            thermal / absorption,
            1.0,
            0.2,
            left_exterior_intensity=left_nodes[:, node],
            right_exterior_intensity=right_nodes[:, node],
            propagation_speed_cm_s=1.0,
            linear_solver="source_iteration",
            iterative_tolerance=2.0e-13,
        ).final_intensity
    actual_nodes = frequency_group_p1_gauss_node_values(
        result.final_lab_mean_intensity_density,
        result.final_lab_first_moment_intensity_density,
    )
    error = np.max(np.abs(actual_nodes - expected_nodes)) / np.max(expected_nodes)
    assert error < 3.0e-12
    assert result.global_scale_normalized_coupled_residual < 3.0e-12
    assert result.total_relative_energy_ledger_residual < 3.0e-12
    assert result.final_limiter_activation_count == 0
    assert result.minimum_reconstructed_intensity > 0.0


def test_rigid_translation_preserves_frequency_constant_p1_equilibrium():
    beta_value = 0.05
    stencil = mixed_frame_frequency_stencil(0.1, 5000.0, 32, beta_value)
    mu, weight = gauss_legendre_mu_weights(8)
    depth_points = 2
    beta = np.full(depth_points, beta_value)
    transform = lorentz_ray_transform(mu, weight, beta)
    outer_mean = np.broadcast_to(
        2.0 * transform.doppler_lab_to_comoving[None, ...] ** -3.0,
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
    old_edge = np.linspace(0.0, 2.0, depth_points + 1)
    new_edge = old_edge + beta_value * duration
    result = solve_mixed_frame_ale_p1_group_step(
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
        left_exterior_mean_intensity=active_mean[:, :, 0],
        right_exterior_mean_intensity=active_mean[:, :, -1],
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-12,
    )
    error = np.max(
        np.abs(result.final_lab_mean_intensity_density - active_mean)
    ) / np.max(active_mean)
    assert error < 7.0e-4
    assert np.max(np.abs(result.final_lab_first_moment_intensity_density)) < 1.0e-12
    assert result.global_scale_normalized_coupled_residual < 2.0e-10
    assert result.minimum_reconstructed_intensity > 0.0


def test_mixed_frame_ale_p1_uses_no_forbidden_repairs():
    path = Path("src/eccentric_tde_observer/mixed_frame_ale_p1.py")
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
