import numpy as np
import pytest

from eccentric_tde_observer.mixed_frame_ali import (
    doppler_coupled_local_ali_residual_correction,
    static_frequency_spatial_ali_residual_correction,
    mixed_frame_spatial_source_residual_correction,
    static_diagonal_ali_residual_correction,
    step_characteristic_local_lambda_diagonal,
)
from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil_from_active_edges,
)
from eccentric_tde_observer.mixed_frame_frequency import (
    lorentz_ray_transform,
    lorentz_remap_signed_comoving_group_emissivity_perturbation_to_lab,
    lorentz_remap_signed_group_intensity_perturbation,
)


def test_zero_scattering_ali_is_exact_identity_on_signed_residual():
    mu = np.array([-0.6, 0.2, 0.8])
    weight = np.array([0.5, 0.8, 0.7])
    residual = np.array(
        [
            [[-2.0, 1.0], [0.5, -0.2], [1.5, 0.7]],
            [[0.3, -0.4], [1.2, 0.6], [-0.8, 0.9]],
        ]
    )
    result = static_diagonal_ali_residual_correction(
        residual,
        mu,
        weight,
        np.ones_like(residual),
        np.zeros_like(residual),
    )
    assert np.array_equal(result.correction, residual)
    assert np.all(result.scattering_feedback_fraction == 0.0)
    assert np.all(result.scattering_denominator == 1.0)


def test_static_rank_one_ali_matches_direct_local_linear_solve():
    mu = np.array([-0.7, -0.1, 0.4, 0.9])
    weight = np.array([0.3, 0.6, 0.7, 0.4])
    residual = np.array([[[0.4], [-0.7], [1.1], [0.2]]])
    response = np.array([[[0.3], [0.5], [0.4], [0.2]]])
    scattering = np.array([[[0.8], [0.8], [0.8], [0.8]]])
    result = static_diagonal_ali_residual_correction(
        residual, mu, weight, response, scattering
    )
    local_feedback = (response * scattering)[0, :, 0]
    matrix = np.eye(mu.size) - np.outer(local_feedback, 0.5 * weight)
    direct = np.linalg.solve(matrix, residual[0, :, 0])
    assert result.correction[0, :, 0] == pytest.approx(direct, rel=2.0e-15)
    assert result.corrected_mean_intensity[0, 0] == pytest.approx(
        0.5 * weight @ direct, rel=2.0e-15
    )


def test_step_characteristic_lambda_matches_finite_difference_local_source():
    mu = np.array([-0.65, 0.65])
    old_edge = np.array([0.0, 0.4, 1.0])
    new_edge = np.array(old_edge, copy=True)
    extinction = np.array(
        [
            [[0.7, 1.1], [0.8, 1.3]],
            [[0.2, 0.4], [0.3, 0.5]],
        ]
    )
    duration = 0.9
    speed = 1.0
    result = step_characteristic_local_lambda_diagonal(
        old_edge,
        new_edge,
        mu,
        extinction,
        duration,
        propagation_speed_cm_s=speed,
    )
    # 静态特征线上，局域源导数可由常系数解析式独立复算。
    width = np.diff(new_edge)
    for frequency in range(extinction.shape[0]):
        for angle, cosine in enumerate(mu):
            for depth in range(width.size):
                coefficient = width[depth] / duration + speed * width[depth] * extinction[
                    frequency, angle, depth
                ]
                optical_distance = coefficient / abs(speed * cosine)
                average_factor = -np.expm1(-optical_distance) / optical_distance
                expected = speed * width[depth] / coefficient * (1.0 - average_factor)
                assert result.response_cm[frequency, angle, depth] == pytest.approx(
                    expected, rel=3.0e-15
                )
    assert result.turning_angle_count == 0
    assert result.turning_ray_uses_raw_upwind_diagonal is False


def test_turning_ray_requires_explicit_upwind_approximation_and_stays_positive():
    mu = np.array([-0.2, 0.2])
    old_edge = np.array([0.0, 0.5, 1.0])
    duration = 1.0
    new_edge = old_edge + np.array([0.0, 0.3, 0.0])
    extinction = np.full((1, 2, 2), 0.4)
    with pytest.raises(Exception, match="reversed direction"):
        step_characteristic_local_lambda_diagonal(
            old_edge,
            new_edge,
            mu,
            extinction,
            duration,
            propagation_speed_cm_s=1.0,
        )
    result = step_characteristic_local_lambda_diagonal(
        old_edge,
        new_edge,
        mu,
        extinction,
        duration,
        propagation_speed_cm_s=1.0,
        allow_turning_ray_upwind=True,
    )
    assert result.turning_angle_count == 1
    assert result.turning_ray_uses_raw_upwind_diagonal is True
    assert np.all(result.response_cm > 0.0)


def test_nonpositive_scattering_denominator_is_rejected_without_floor():
    mu = np.array([-0.5, 0.5])
    weight = np.array([1.0, 1.0])
    with pytest.raises(ArithmeticError, match="denominator is not positive"):
        static_diagonal_ali_residual_correction(
            np.ones((1, 2, 1)),
            mu,
            weight,
            np.ones((1, 2, 1)),
            np.ones((1, 2, 1)),
        )


def test_zero_velocity_doppler_coupled_ali_recovers_static_rank_one_inverse():
    edge = np.array([1.0, 2.0, 4.0])
    mu = np.array([-0.6, 0.6])
    weight = np.array([1.0, 1.0])
    residual = np.array(
        [
            [[0.4, -0.2], [0.7, 0.3]],
            [[-0.5, 0.1], [0.2, 0.8]],
        ]
    )
    response = np.array(
        [
            [[0.2, 0.3], [0.4, 0.25]],
            [[0.1, 0.35], [0.3, 0.2]],
        ]
    )
    scattering = np.array([[0.7, 0.6], [0.5, 0.8]])
    static = static_diagonal_ali_residual_correction(
        residual, mu, weight, response, scattering[:, None, :]
    )
    coupled = doppler_coupled_local_ali_residual_correction(
        residual,
        edge,
        edge,
        edge,
        0,
        2,
        mu,
        weight,
        np.zeros(2),
        response,
        scattering,
        iterative_tolerance=2.0e-14,
    )
    assert coupled.correction == pytest.approx(static.correction, rel=4.0e-14)
    assert coupled.final_relative_linear_residual <= 2.0e-14


def test_moving_doppler_coupled_ali_matches_independent_dense_linear_solve():
    active_edge = np.array([1.0, 2.0, 4.0])
    stencil = mixed_frame_frequency_stencil_from_active_edges(active_edge, 0.08)
    mu = np.array([-0.55, 0.55])
    weight = np.array([1.0, 1.0])
    beta = np.array([0.05])
    residual = np.array([[[0.4], [-0.2]], [[0.7], [0.3]]])
    response = np.array([[[0.25], [0.35]], [[0.2], [0.3]]])
    scattering = np.linspace(
        0.25, 0.4, stencil.comoving_collision_group_count
    )[:, None]
    result = doppler_coupled_local_ali_residual_correction(
        residual,
        stencil.outer_lab_edge_hz,
        stencil.comoving_collision_edge_hz,
        stencil.active_lab_edge_hz,
        stencil.active_outer_group_start,
        stencil.active_outer_group_stop,
        mu,
        weight,
        beta,
        response,
        scattering,
        iterative_tolerance=2.0e-14,
    )
    transform = lorentz_ray_transform(mu, weight, beta)
    size = residual.size
    local_operator = np.empty((size, size))
    for column in range(size):
        basis = np.zeros_like(residual)
        basis.reshape(-1)[column] = 1.0
        outer = np.zeros(
            (
                stencil.outer_lab_group_count,
                mu.size,
                beta.size,
            )
        )
        outer[
            stencil.active_outer_group_start : stencil.active_outer_group_stop
        ] = basis
        comoving_angle = lorentz_remap_signed_group_intensity_perturbation(
            outer,
            stencil.outer_lab_edge_hz,
            stencil.comoving_collision_edge_hz,
            transform.doppler_lab_to_comoving,
            direction="lab_to_comoving",
        )
        comoving_mean = 0.5 * np.sum(
            transform.comoving_angular_weight[None, ...] * comoving_angle,
            axis=1,
        )
        lab_emissivity = (
            lorentz_remap_signed_comoving_group_emissivity_perturbation_to_lab(
                np.broadcast_to(
                    (scattering * comoving_mean)[:, None, :],
                    (
                        stencil.comoving_collision_group_count,
                        mu.size,
                        beta.size,
                    ),
                ),
                stencil.comoving_collision_edge_hz,
                stencil.active_lab_edge_hz,
                transform.doppler_lab_to_comoving,
            )
        )
        local_operator[:, column] = (response * lab_emissivity).reshape(-1)
    direct = np.linalg.solve(
        np.eye(size) - local_operator, residual.reshape(-1)
    ).reshape(residual.shape)
    assert result.correction == pytest.approx(direct, rel=5.0e-14, abs=5.0e-15)
    assert result.final_relative_linear_residual <= 2.0e-14


def test_static_frequency_spatial_ali_matches_dense_full_intensity_solve():
    mu = np.array([-0.6, 0.6])
    weight = np.array([1.0, 1.0])
    old_edge = np.array([0.0, 0.3, 0.7, 1.0])
    new_edge = np.array(old_edge, copy=True)
    residual = np.array([[[0.4, -0.2, 0.3], [-0.1, 0.6, 0.2]]])
    extinction = np.array([[[0.8, 1.1, 0.9], [1.0, 0.7, 1.2]]])
    scattering = np.array([[[0.35, 0.4, 0.3], [0.35, 0.4, 0.3]]])
    result = static_frequency_spatial_ali_residual_correction(
        residual,
        old_edge,
        new_edge,
        mu,
        weight,
        extinction,
        scattering,
        0.8,
        propagation_speed_cm_s=1.0,
        gmres_relative_tolerance=2.0e-13,
        gmres_restart=6,
        gmres_maximum_restart_cycles=4,
    )
    # 独立构造完整强度固定点矩阵，避免只比较降维平均强度方程。
    from eccentric_tde_observer.mixed_frame_ale import (
        _solve_step_characteristics_ray_transport,
    )

    size = residual.size
    matrix = np.empty((size, size))
    old_width = np.diff(old_edge)
    zero = np.zeros_like(residual)
    boundary = np.zeros((1, mu.size))
    for column in range(size):
        basis = np.zeros_like(residual)
        basis.reshape(-1)[column] = 1.0
        mean = 0.5 * np.einsum("m,fmd->fd", weight, basis)
        response, _ = _solve_step_characteristics_ray_transport(
            zero,
            old_width,
            old_width,
            mu,
            np.zeros(old_edge.size),
            extinction,
            scattering * mean[:, None, :],
            boundary,
            boundary,
            0.8,
            1.0,
            allow_signed_fields=True,
        )
        matrix[:, column] = response.reshape(-1)
    direct = np.linalg.solve(np.eye(size) - matrix, residual.reshape(-1)).reshape(
        residual.shape
    )
    assert result.correction == pytest.approx(direct, rel=2.0e-12, abs=2.0e-13)
    assert result.gmres_reported_info == 0
    assert result.final_scaled_linf_linear_residual <= 2.0e-12
    assert result.final_mean_consistency_linf <= 2.0e-12


def test_static_frequency_spatial_ali_zero_scattering_returns_raw_residual():
    mu = np.array([-0.5, 0.5])
    weight = np.array([1.0, 1.0])
    edge = np.array([0.0, 0.5, 1.0])
    residual = np.array([[[0.4, -0.2], [0.1, 0.3]]])
    result = static_frequency_spatial_ali_residual_correction(
        residual,
        edge,
        edge,
        mu,
        weight,
        np.ones_like(residual),
        np.zeros_like(residual),
        1.0,
        propagation_speed_cm_s=1.0,
        gmres_relative_tolerance=1.0e-13,
    )
    assert result.correction == pytest.approx(residual, rel=2.0e-15)


def test_full_mixed_frame_spatial_correction_matches_dense_intensity_solve():
    active_edge = np.array([1.0, 2.0, 4.0])
    stencil = mixed_frame_frequency_stencil_from_active_edges(active_edge, 0.08)
    mu = np.array([-0.55, 0.55])
    weight = np.array([1.0, 1.0])
    beta = np.array([0.03, -0.02])
    edge = np.array([0.0, 0.4, 1.0])
    residual = np.array(
        [
            [[0.4, -0.2], [0.1, 0.3]],
            [[-0.15, 0.25], [0.35, -0.1]],
        ]
    )
    extinction = np.array(
        [
            [[0.8, 1.0], [0.7, 1.1]],
            [[0.5, 0.6], [0.55, 0.65]],
        ]
    )
    scattering = np.linspace(
        0.18, 0.28, stencil.comoving_collision_group_count
    )[:, None] * np.array([[1.0, 1.1]])
    result = mixed_frame_spatial_source_residual_correction(
        residual,
        edge,
        edge,
        stencil.outer_lab_edge_hz,
        stencil.comoving_collision_edge_hz,
        stencil.active_lab_edge_hz,
        stencil.active_outer_group_start,
        stencil.active_outer_group_stop,
        mu,
        weight,
        beta,
        extinction,
        scattering,
        0.9,
        propagation_speed_cm_s=1.0,
        gmres_relative_tolerance=2.0e-13,
        gmres_restart=8,
        gmres_maximum_restart_cycles=2,
    )
    transform = lorentz_ray_transform(mu, weight, beta)
    from eccentric_tde_observer.mixed_frame_ale import (
        _solve_step_characteristics_ray_transport,
    )

    size = residual.size
    matrix = np.empty((size, size))
    zero = np.zeros_like(residual)
    boundary = np.zeros((active_edge.size - 1, mu.size))
    width = np.diff(edge)
    for column in range(size):
        basis = np.zeros_like(residual)
        basis.reshape(-1)[column] = 1.0
        outer = np.zeros(
            (stencil.outer_lab_group_count, mu.size, beta.size)
        )
        outer[
            stencil.active_outer_group_start : stencil.active_outer_group_stop
        ] = basis
        comoving_angle = lorentz_remap_signed_group_intensity_perturbation(
            outer,
            stencil.outer_lab_edge_hz,
            stencil.comoving_collision_edge_hz,
            transform.doppler_lab_to_comoving,
            direction="lab_to_comoving",
        )
        comoving_mean = 0.5 * np.sum(
            transform.comoving_angular_weight[None, ...] * comoving_angle,
            axis=1,
        )
        lab_emissivity = (
            lorentz_remap_signed_comoving_group_emissivity_perturbation_to_lab(
                np.broadcast_to(
                    (scattering * comoving_mean)[:, None, :],
                    (
                        stencil.comoving_collision_group_count,
                        mu.size,
                        beta.size,
                    ),
                ),
                stencil.comoving_collision_edge_hz,
                stencil.active_lab_edge_hz,
                transform.doppler_lab_to_comoving,
            )
        )
        response, _ = _solve_step_characteristics_ray_transport(
            zero,
            width,
            width,
            mu,
            np.zeros(edge.size),
            extinction,
            lab_emissivity,
            boundary,
            boundary,
            0.9,
            1.0,
            allow_signed_fields=True,
        )
        matrix[:, column] = response.reshape(-1)
    direct = np.linalg.solve(np.eye(size) - matrix, residual.reshape(-1)).reshape(
        residual.shape
    )
    assert result.correction == pytest.approx(direct, rel=3.0e-12, abs=3.0e-13)
    assert result.fixed_point_converged is True
    assert result.final_scaled_linf_linear_residual <= 2.0e-12
    assert result.final_comoving_mean_consistency_linf <= 2.0e-12
