from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.implicit_radiative_transfer_1d import (
    solve_implicit_ale_slab_step,
)
from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil,
    mixed_frame_frequency_stencil_from_active_edges,
    solve_mixed_frame_ale_group_step,
)
from eccentric_tde_observer.mixed_frame_frequency import lorentz_ray_transform
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.radiative_transfer_1d import gauss_legendre_mu_weights


def test_irregular_frequency_stencil_preserves_active_edges_and_guard_coverage():
    active = np.array([1.0, 1.3, 2.1, 4.8, 10.0])
    beta = 0.08
    stencil = mixed_frame_frequency_stencil_from_active_edges(active, beta)
    gamma = 1.0 / np.sqrt(1.0 - beta**2)
    minimum_doppler = gamma * (1.0 - beta)
    maximum_doppler = gamma * (1.0 + beta)
    physical = slice(
        stencil.active_outer_group_start,
        stencil.active_outer_group_stop + 1,
    )
    assert np.array_equal(stencil.active_lab_edge_hz, active)
    assert np.array_equal(stencil.outer_lab_edge_hz[physical], active)
    assert stencil.comoving_collision_group_count == 6
    assert stencil.outer_lab_group_count == 8
    assert stencil.groups_per_decade is None
    assert stencil.comoving_collision_edge_hz[0] < minimum_doppler * active[0]
    assert stencil.comoving_collision_edge_hz[-1] > maximum_doppler * active[-1]
    assert (
        stencil.outer_lab_edge_hz[0]
        < stencil.comoving_collision_edge_hz[0] / maximum_doppler
    )
    assert (
        stencil.outer_lab_edge_hz[-1]
        > stencil.comoving_collision_edge_hz[-1] / minimum_doppler
    )


def test_irregular_frequency_stencil_zero_velocity_needs_no_guards():
    active = np.array([1.0, 1.3, 2.1, 4.8, 10.0])
    stencil = mixed_frame_frequency_stencil_from_active_edges(active, 0.0)
    assert np.array_equal(stencil.active_lab_edge_hz, active)
    assert np.array_equal(stencil.comoving_collision_edge_hz, active)
    assert np.array_equal(stencil.outer_lab_edge_hz, active)
    assert stencil.active_outer_group_start == 0
    assert stencil.active_outer_group_stop == active.size - 1
    assert stencil.physical_group_count == active.size - 1
    assert stencil.comoving_collision_group_count == active.size - 1
    assert stencil.outer_lab_group_count == active.size - 1


def test_source_map_only_is_bitwise_equal_to_full_diagnostic_map():
    stencil = mixed_frame_frequency_stencil_from_active_edges(
        np.array([1.0, 2.0, 4.0]), 0.0
    )
    mu, weight = gauss_legendre_mu_weights(2)
    initial = np.array(
        [
            [[1.0, 1.2], [0.9, 1.1]],
            [[0.7, 0.8], [0.6, 0.75]],
        ]
    )
    absorption = np.array([[0.2, 0.3], [0.4, 0.5]])
    emissivity = np.array([[0.1, 0.2], [0.3, 0.4]])
    scattering = np.array([[0.05, 0.06], [0.07, 0.08]])
    arguments = (
        stencil,
        np.array([0.0, 0.4, 1.0]),
        np.array([0.0, 0.4, 1.0]),
        mu,
        weight,
        initial,
        initial,
        absorption,
        emissivity,
        scattering,
        np.zeros(2),
        0.3,
    )
    full = solve_mixed_frame_ale_group_step(
        *arguments,
        propagation_speed_cm_s=1.0,
        source_iteration_initial_guess=initial,
        diagnostic_fixed_iteration_count=1,
        spatial_scheme="step_characteristics",
    )
    lean = solve_mixed_frame_ale_group_step(
        *arguments,
        propagation_speed_cm_s=1.0,
        source_iteration_initial_guess=initial,
        diagnostic_fixed_iteration_count=1,
        spatial_scheme="step_characteristics",
        source_map_only=True,
    )
    assert np.array_equal(
        lean.final_lab_intensity_density, full.final_lab_intensity_density
    )
    assert lean.fixed_point_iterations == full.fixed_point_iterations == 1
    assert lean.final_fixed_point_change == full.final_fixed_point_change
    assert lean.minimum_intensity == full.minimum_intensity
    assert lean.maximum_mesh_speed_to_light == full.maximum_mesh_speed_to_light
    assert lean.fixed_point_converged == full.fixed_point_converged


def test_zero_velocity_mixed_frame_step_matches_stationary_ale_solver():
    stencil = mixed_frame_frequency_stencil(0.1, 5000.0, 8, 0.0)
    mu, weight = gauss_legendre_mu_weights(4)
    depth_points = 3
    frequency_points = stencil.physical_group_count
    old_edges = np.linspace(0.0, 1.0, depth_points + 1)
    new_edges = np.array(old_edges, copy=True)
    frequency_coordinate = np.linspace(0.0, 1.0, frequency_points)[:, None]
    depth_coordinate = np.linspace(0.0, 1.0, depth_points)[None, :]
    absorption = 0.3 + 0.1 * frequency_coordinate + 0.05 * depth_coordinate
    scattering = 0.4 + 0.03 * depth_coordinate + 0.0 * frequency_coordinate
    source = 1.2 + 0.15 * frequency_coordinate + 0.08 * depth_coordinate
    emissivity = absorption * source
    initial = np.broadcast_to(
        source[:, None, :] * (1.0 + 0.04 * mu[None, :, None]),
        (frequency_points, mu.size, depth_points),
    ).copy()
    left = 0.9 + 0.02 * mu[None, :] + np.zeros((frequency_points, 1))
    right = 1.1 - 0.03 * mu[None, :] + np.zeros((frequency_points, 1))
    observed_iterations = []
    observed_states = {}

    def observe(iteration, state):
        assert state.flags.writeable is False
        observed_iterations.append(iteration)
        if iteration == 1:
            observed_states[iteration] = np.array(state, copy=True)

    mixed = solve_mixed_frame_ale_group_step(
        stencil,
        old_edges,
        new_edges,
        mu,
        weight,
        initial,
        initial,
        absorption,
        emissivity,
        scattering,
        np.zeros(depth_points),
        0.2,
        left_exterior_intensity=left,
        right_exterior_intensity=right,
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-13,
        iteration_observer=observe,
    )
    identity_control = solve_mixed_frame_ale_group_step(
        stencil,
        old_edges,
        new_edges,
        mu,
        weight,
        initial,
        initial,
        absorption,
        emissivity,
        scattering,
        np.zeros(depth_points),
        0.2,
        left_exterior_intensity=left,
        right_exterior_intensity=right,
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-13,
        apply_intensity_lorentz=False,
        apply_extinction_lorentz=False,
        apply_emissivity_lorentz=False,
    )
    one_iteration = solve_mixed_frame_ale_group_step(
        stencil,
        old_edges,
        new_edges,
        mu,
        weight,
        initial,
        initial,
        absorption,
        emissivity,
        scattering,
        np.zeros(depth_points),
        0.2,
        left_exterior_intensity=left,
        right_exterior_intensity=right,
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-13,
        diagnostic_fixed_iteration_count=1,
    )
    stationary = solve_implicit_ale_slab_step(
        0.5 * (stencil.active_lab_edge_hz[:-1] + stencil.active_lab_edge_hz[1:]),
        old_edges,
        new_edges,
        mu,
        weight,
        initial,
        absorption + scattering,
        source,
        absorption / (absorption + scattering),
        0.2,
        left_exterior_intensity=left,
        right_exterior_intensity=right,
        propagation_speed_cm_s=1.0,
        linear_solver="source_iteration",
        iterative_tolerance=2.0e-13,
    )
    scale = np.max(np.abs(stationary.final_intensity))
    error = np.max(
        np.abs(mixed.final_lab_intensity_density - stationary.final_intensity)
    ) / scale
    assert error < 3.0e-12
    assert mixed.global_scale_normalized_coupled_residual < 3.0e-12
    assert mixed.total_relative_energy_ledger_residual < 3.0e-12
    assert np.array_equal(
        identity_control.final_lab_intensity_density,
        mixed.final_lab_intensity_density,
    )
    assert observed_iterations[0] == 0
    assert observed_iterations[-1] == mixed.fixed_point_iterations
    assert observed_iterations == list(range(mixed.fixed_point_iterations + 1))
    assert mixed.fixed_point_converged is True
    assert identity_control.fixed_point_converged is True
    assert one_iteration.fixed_point_converged is False
    assert np.array_equal(
        one_iteration.final_lab_intensity_density, observed_states[1]
    )


def test_step_characteristics_recovers_exact_backward_euler_absorption_slab():
    stencil = mixed_frame_frequency_stencil_from_active_edges([1.0, 2.0], 0.0)
    mu, weight = gauss_legendre_mu_weights(4)
    depth_points = 4
    edges = np.linspace(0.0, 1.0, depth_points + 1)
    duration = 0.4
    absorption_value = 2.0
    thermal_source = 1.3
    initial_value = 0.2
    left_value = 0.7
    right_value = 0.9
    shape = (1, mu.size, depth_points)
    initial = np.full(shape, initial_value)
    absorption = np.full((1, depth_points), absorption_value)
    emissivity = absorption * thermal_source
    left = np.full((1, mu.size), left_value)
    right = np.full((1, mu.size), right_value)
    result = solve_mixed_frame_ale_group_step(
        stencil,
        edges,
        edges,
        mu,
        weight,
        initial,
        initial,
        absorption,
        emissivity,
        0.0,
        np.zeros(depth_points),
        duration,
        left_exterior_intensity=left,
        right_exterior_intensity=right,
        propagation_speed_cm_s=1.0,
        spatial_scheme="step_characteristics",
        iterative_tolerance=2.0e-13,
    )
    effective_extinction = absorption_value + 1.0 / duration
    effective_source = (
        initial_value / duration + absorption_value * thermal_source
    ) / effective_extinction
    expected = np.empty_like(result.final_lab_intensity_density)
    for angle, cosine in enumerate(mu):
        incoming = left_value if cosine > 0.0 else right_value
        for depth in range(depth_points):
            left_edge = edges[depth]
            right_edge = edges[depth + 1]
            if cosine > 0.0:
                start = left_edge
                stop = right_edge
            else:
                start = 1.0 - right_edge
                stop = 1.0 - left_edge
            optical_start = effective_extinction * start / abs(cosine)
            optical_stop = effective_extinction * stop / abs(cosine)
            attenuation_average = (
                np.exp(-optical_start) - np.exp(-optical_stop)
            ) / (optical_stop - optical_start)
            expected[0, angle, depth] = (
                effective_source
                + (incoming - effective_source) * attenuation_average
            )
    assert np.max(np.abs(result.final_lab_intensity_density - expected)) < 2.0e-14
    assert result.global_scale_normalized_coupled_residual < 2.0e-14
    assert result.total_relative_energy_ledger_residual < 2.0e-14
    assert result.minimum_intensity > 0.0


def test_step_characteristics_moving_grid_closes_face_ledger_without_clipping():
    stencil = mixed_frame_frequency_stencil_from_active_edges([1.0, 2.0], 0.0)
    mu, weight = gauss_legendre_mu_weights(4)
    depth_points = 5
    old_edges = np.linspace(0.0, 1.0, depth_points + 1)
    new_edges = 0.01 + 1.02 * old_edges
    initial = np.full((1, mu.size, depth_points), 0.3)
    absorption = np.full((1, depth_points), 1.7)
    result = solve_mixed_frame_ale_group_step(
        stencil,
        old_edges,
        new_edges,
        mu,
        weight,
        initial,
        initial,
        absorption,
        1.1 * absorption,
        0.0,
        np.zeros(depth_points),
        1.0,
        left_exterior_intensity=0.4,
        right_exterior_intensity=0.6,
        propagation_speed_cm_s=1.0,
        spatial_scheme="step_characteristics",
        iterative_tolerance=2.0e-13,
    )
    assert result.global_scale_normalized_coupled_residual < 3.0e-14
    assert result.total_relative_energy_ledger_residual < 3.0e-14
    assert result.minimum_intensity > 0.0


def test_step_characteristics_rejects_unimplemented_periodic_path():
    stencil = mixed_frame_frequency_stencil_from_active_edges([1.0, 2.0], 0.0)
    mu, weight = gauss_legendre_mu_weights(2)
    with pytest.raises(
        ValueError, match="do not support periodic spatial boundaries"
    ):
        solve_mixed_frame_ale_group_step(
            stencil,
            [0.0, 1.0],
            [0.0, 1.0],
            mu,
            weight,
            0.0,
            0.0,
            1.0,
            1.0,
            0.0,
            [0.0],
            1.0,
            periodic_spatial_boundary=True,
            propagation_speed_cm_s=1.0,
            spatial_scheme="step_characteristics",
        )


def test_hybrid_turning_ray_matches_independent_dense_upwind_system():
    stencil = mixed_frame_frequency_stencil_from_active_edges([1.0, 2.0], 0.0)
    mu, weight = gauss_legendre_mu_weights(2)
    old_edges = np.array([0.0, 1.0, 2.0, 3.0])
    face_velocity = np.array([-0.8, -0.25, 0.25, 0.8])
    new_edges = old_edges + face_velocity
    duration = 1.0
    initial = np.array([[[0.3, 0.4, 0.5], [0.6, 0.5, 0.4]]])
    absorption = np.array([[0.2, 0.4, 0.6]])
    emissivity = np.array([[0.7, 0.8, 0.9]])
    left = np.array([[0.25, 0.35]])
    right = np.array([[0.45, 0.55]])
    with pytest.raises(ValueError, match="reversed direction"):
        solve_mixed_frame_ale_group_step(
            stencil,
            old_edges,
            new_edges,
            mu,
            weight,
            initial,
            initial,
            absorption,
            emissivity,
            0.0,
            np.zeros(3),
            duration,
            left_exterior_intensity=left,
            right_exterior_intensity=right,
            propagation_speed_cm_s=1.0,
            spatial_scheme="step_characteristics",
        )
    result = solve_mixed_frame_ale_group_step(
        stencil,
        old_edges,
        new_edges,
        mu,
        weight,
        initial,
        initial,
        absorption,
        emissivity,
        0.0,
        np.zeros(3),
        duration,
        left_exterior_intensity=left,
        right_exterior_intensity=right,
        propagation_speed_cm_s=1.0,
        spatial_scheme="hybrid_step_turning_upwind",
        iterative_tolerance=2.0e-13,
    )
    old_width = np.diff(old_edges)
    new_width = np.diff(new_edges)
    expected = np.empty_like(initial)
    for angle, cosine in enumerate(mu):
        speed = cosine - face_velocity
        matrix = np.zeros((3, 3))
        rhs = (
            old_width / duration * initial[0, angle]
            + new_width * emissivity[0]
        )
        for depth in range(3):
            matrix[depth, depth] = (
                new_width[depth] / duration
                + new_width[depth] * absorption[0, depth]
                + max(speed[depth + 1], 0.0)
                - min(speed[depth], 0.0)
            )
            if depth > 0:
                matrix[depth, depth - 1] = -max(speed[depth], 0.0)
            if depth < 2:
                matrix[depth, depth + 1] = min(speed[depth + 1], 0.0)
        if speed[0] > 0.0:
            rhs[0] += speed[0] * left[0, angle]
        if speed[-1] < 0.0:
            rhs[-1] -= speed[-1] * right[0, angle]
        expected[0, angle] = np.linalg.solve(matrix, rhs)
    assert np.max(np.abs(result.final_lab_intensity_density - expected)) < 3.0e-15
    assert result.global_scale_normalized_coupled_residual < 3.0e-15
    assert result.total_relative_energy_ledger_residual < 3.0e-15
    assert result.minimum_intensity > 0.0


def test_hybrid_nonturning_rays_are_identical_to_step_characteristics():
    stencil = mixed_frame_frequency_stencil_from_active_edges([1.0, 2.0], 0.0)
    mu, weight = gauss_legendre_mu_weights(4)
    edges = np.linspace(0.0, 1.0, 6)
    initial = np.full((1, mu.size, 5), 0.4)
    absorption = np.full((1, 5), 0.7)
    common = dict(
        left_exterior_intensity=0.2,
        right_exterior_intensity=0.8,
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-13,
    )
    step = solve_mixed_frame_ale_group_step(
        stencil,
        edges,
        edges,
        mu,
        weight,
        initial,
        initial,
        absorption,
        1.3 * absorption,
        0.0,
        np.zeros(5),
        0.5,
        spatial_scheme="step_characteristics",
        **common,
    )
    hybrid = solve_mixed_frame_ale_group_step(
        stencil,
        edges,
        edges,
        mu,
        weight,
        initial,
        initial,
        absorption,
        1.3 * absorption,
        0.0,
        np.zeros(5),
        0.5,
        spatial_scheme="hybrid_step_turning_upwind",
        **common,
    )
    assert np.array_equal(
        hybrid.final_lab_intensity_density,
        step.final_lab_intensity_density,
    )
    assert np.array_equal(hybrid.left_ale_face_intensity, step.left_ale_face_intensity)
    assert np.array_equal(hybrid.right_ale_face_intensity, step.right_ale_face_intensity)


def _boosted_constant_intensity(stencil, mu, weight, beta, value):
    transform = lorentz_ray_transform(mu, weight, beta)
    lab = value * transform.doppler_lab_to_comoving[None, ...] ** -3.0
    return np.broadcast_to(
        lab, (stencil.outer_lab_group_count, *lab.shape[1:])
    ).copy()


def test_rigid_translation_preserves_comoving_isotropic_equilibrium():
    beta = 0.05
    stencil = mixed_frame_frequency_stencil(0.1, 5000.0, 32, beta)
    mu, weight = gauss_legendre_mu_weights(8)
    depth_points = 2
    duration = 0.1
    old_edges = np.linspace(0.0, 2.0, depth_points + 1)
    new_edges = old_edges + beta * duration
    material_beta = np.full(depth_points, beta)
    outer = _boosted_constant_intensity(
        stencil, mu, weight, material_beta, 2.0
    )
    active = outer[
        stencil.active_outer_group_start : stencil.active_outer_group_stop
    ]
    collision_shape = (stencil.comoving_collision_group_count, depth_points)
    absorption = np.full(collision_shape, 0.7)
    scattering = np.full(collision_shape, 0.4)
    emissivity = 2.0 * absorption
    result = solve_mixed_frame_ale_group_step(
        stencil,
        old_edges,
        new_edges,
        mu,
        weight,
        active,
        outer,
        absorption,
        emissivity,
        scattering,
        material_beta,
        duration,
        left_exterior_intensity=active[:, :, 0],
        right_exterior_intensity=active[:, :, -1],
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-12,
    )
    error = np.max(np.abs(result.final_lab_intensity_density - active)) / np.max(active)
    assert error < 7.0e-4
    assert result.global_scale_normalized_coupled_residual < 2.0e-10
    assert result.minimum_intensity > 0.0


def test_one_cell_homologous_breathing_preserves_manufactured_equilibrium():
    maximum_beta = 0.06
    stencil = mixed_frame_frequency_stencil(0.1, 5000.0, 32, maximum_beta)
    mu, weight = gauss_legendre_mu_weights(8)
    old_edges = np.array([1.0, 2.0])
    new_edges = np.array([1.02, 2.04])
    duration = 1.0
    material_beta = np.array([0.03])
    outer = _boosted_constant_intensity(
        stencil, mu, weight, material_beta, 1.7
    )
    active = outer[
        stencil.active_outer_group_start : stencil.active_outer_group_stop
    ]
    collision_shape = (stencil.comoving_collision_group_count, 1)
    absorption = np.full(collision_shape, 0.5)
    scattering = np.full(collision_shape, 0.2)
    result = solve_mixed_frame_ale_group_step(
        stencil,
        old_edges,
        new_edges,
        mu,
        weight,
        active,
        outer,
        absorption,
        1.7 * absorption,
        scattering,
        material_beta,
        duration,
        left_exterior_intensity=active[:, :, 0],
        right_exterior_intensity=active[:, :, 0],
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-12,
    )
    error = np.max(np.abs(result.final_lab_intensity_density - active)) / np.max(active)
    assert error < 8.0e-4
    assert result.total_relative_energy_ledger_residual < 2.0e-9
    assert result.maximum_mesh_speed_to_light == pytest.approx(0.04)


def test_optically_thick_moving_scattering_closes_four_force_and_energy():
    beta = 0.05
    stencil = mixed_frame_frequency_stencil(0.1, 5000.0, 64, beta)
    mu, weight = gauss_legendre_mu_weights(8)
    transform = lorentz_ray_transform(mu, weight, np.array([beta]))
    doppler = transform.doppler_lab_to_comoving[:, 0]
    comoving_edge = stencil.comoving_collision_edge_hz
    energy_edge = comoving_edge * PLANCK_ERG_S / EV_ERG
    lower_index = int(np.searchsorted(energy_edge, 10.0, side="right") - 1)
    upper_index = int(np.searchsorted(energy_edge, 100.0, side="left"))
    support_lower = comoving_edge[lower_index]
    support_upper = comoving_edge[upper_index]
    comoving_angle = 1.0 + 0.6 * transform.comoving_direction_cosine[:, 0]
    outer_edge = stencil.outer_lab_edge_hz
    outer_width = np.diff(outer_edge)
    outer = np.empty((stencil.outer_lab_group_count, mu.size, 1))
    for angle, factor in enumerate(doppler):
        query_left = factor * outer_edge[:-1]
        query_right = factor * outer_edge[1:]
        # 几何交叠长度精确构造紧支撑谱，不是数值裁剪或强度 floor。
        overlap = np.maximum(
            0.0,
            np.minimum(query_right, support_upper)
            - np.maximum(query_left, support_lower),
        )
        outer[:, angle, 0] = (
            factor**-4 * comoving_angle[angle] * overlap / outer_width
        )
    active = outer[
        stencil.active_outer_group_start : stencil.active_outer_group_stop
    ]
    support = (comoving_edge[:-1] >= support_lower) & (
        comoving_edge[1:] <= support_upper
    )
    scattering = np.zeros((stencil.comoving_collision_group_count, 1))
    scattering[support, 0] = 40.0
    result = solve_mixed_frame_ale_group_step(
        stencil,
        [0.0, 1.0],
        [0.0, 1.0],
        mu,
        weight,
        active,
        outer,
        0.0,
        0.0,
        scattering,
        [beta],
        1.0,
        periodic_spatial_boundary=True,
        propagation_speed_cm_s=1.0,
        iterative_tolerance=1.0e-10,
        iterative_maximum_iterations=8192,
    )
    gamma = 1.0 / np.sqrt(1.0 - beta**2)
    expected_energy = gamma * (
        result.radiation_source_energy_comoving_erg_s_cm3
        + beta * result.radiation_source_momentum_comoving_dyn_cm3
    )
    expected_momentum = gamma * (
        result.radiation_source_momentum_comoving_dyn_cm3
        + beta * result.radiation_source_energy_comoving_erg_s_cm3
    )
    energy_scale = max(
        float(np.max(np.abs(result.radiation_source_energy_lab_erg_s_cm3))),
        float(np.max(np.abs(expected_energy))),
    )
    momentum_scale = max(
        float(np.max(np.abs(result.radiation_source_momentum_lab_dyn_cm3))),
        float(np.max(np.abs(expected_momentum))),
    )
    assert beta * 40.0 > 1.0
    assert np.max(np.abs(result.four_force_energy_residual_erg_s_cm3)) / energy_scale < 1.0e-9
    assert np.max(np.abs(result.four_force_momentum_residual_dyn_cm3)) / momentum_scale < 1.0e-9
    assert result.global_scale_normalized_coupled_residual < 2.0e-9
    assert result.total_relative_energy_ledger_residual < 2.0e-8
    assert result.minimum_intensity >= 0.0


def test_mixed_frame_ale_uses_no_forbidden_repairs():
    path = Path("src/eccentric_tde_observer/mixed_frame_ale.py")
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
