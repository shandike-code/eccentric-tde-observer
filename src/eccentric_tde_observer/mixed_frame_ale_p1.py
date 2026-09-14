"""组内线性频谱的完整 Lorentz 源项与一维 ALE 守恒推进。

每个频率控制体保存组平均和归一化一次矩。两个 Gauss 节点只用于精确积分
P1 乘积；所有 Lorentz 搬移仍在真实频率组边界上守恒进行。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .mixed_frame_ale import (
    MixedFrameFrequencyStencil,
    _boundary_faces,
    _broadcast_nonnegative,
    _coupled_residual,
    _positive_edges,
    _solve_positive_ray_transport,
)
from .mixed_frame_frequency import (
    comoving_group_p1_radiation,
    frequency_group_p1_from_gauss_node_values,
    frequency_group_p1_gauss_node_values,
    limit_nonnegative_frequency_group_p1,
    lorentz_ray_transform,
    lorentz_remap_comoving_group_p1_emissivity_to_lab,
    lorentz_remap_comoving_group_p1_extinction_to_lab,
)
from .radiation import LIGHT_SPEED_CM_S
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class MixedFrameALEP1Step:
    """一个组内 P1 频谱的后向 Euler 混合系 ALE 辐射步。"""

    final_lab_mean_intensity_density: NDArray[np.float64]
    final_lab_first_moment_intensity_density: NDArray[np.float64]
    final_lab_mean_intensity_angle_average: NDArray[np.float64]
    final_lab_first_moment_intensity_angle_average: NDArray[np.float64]
    final_comoving_angle_mean_intensity_density: NDArray[np.float64]
    final_comoving_angle_first_moment_intensity_density: NDArray[np.float64]
    final_comoving_mean_intensity_density: NDArray[np.float64]
    final_comoving_mean_first_moment_intensity_density: NDArray[np.float64]
    lab_extinction_mean_per_cm: NDArray[np.float64]
    lab_extinction_first_moment_per_cm: NDArray[np.float64]
    lab_emissivity_mean_cgs: NDArray[np.float64]
    lab_emissivity_first_moment_cgs: NDArray[np.float64]
    left_ale_face_mean_intensity: NDArray[np.float64]
    left_ale_face_first_moment_intensity: NDArray[np.float64]
    right_ale_face_mean_intensity: NDArray[np.float64]
    right_ale_face_first_moment_intensity: NDArray[np.float64]
    initial_radiation_energy_group_erg_cm2_hz: NDArray[np.float64]
    final_radiation_energy_group_erg_cm2_hz: NDArray[np.float64]
    left_ale_energy_flux_group_cgs: NDArray[np.float64]
    right_ale_energy_flux_group_cgs: NDArray[np.float64]
    material_heating_group_erg_s_cm2_hz: NDArray[np.float64]
    energy_ledger_residual_group_erg_cm2_hz: NDArray[np.float64]
    relative_energy_ledger_residual_group: NDArray[np.float64]
    radiation_source_energy_lab_erg_s_cm3: NDArray[np.float64]
    radiation_source_momentum_lab_dyn_cm3: NDArray[np.float64]
    radiation_source_energy_comoving_erg_s_cm3: NDArray[np.float64]
    radiation_source_momentum_comoving_dyn_cm3: NDArray[np.float64]
    four_force_energy_residual_erg_s_cm3: NDArray[np.float64]
    four_force_momentum_residual_dyn_cm3: NDArray[np.float64]
    relative_coupled_residual_group: NDArray[np.float64]
    mesh_edge_velocity_cm_s: NDArray[np.float64]
    material_velocity_beta: NDArray[np.float64]
    fixed_point_iterations: int
    final_fixed_point_change: float
    total_relative_energy_ledger_residual: float
    global_scale_normalized_coupled_residual: float
    maximum_group_relative_coupled_residual: float
    minimum_reconstructed_intensity: float
    maximum_mesh_speed_to_light: float
    cumulative_limiter_activation_count: int
    final_limiter_activation_count: int
    maximum_prelimit_realizability_ratio: float


def _broadcast_realizable_p1(
    name: str,
    mean_values: ArrayLike,
    moment_values: ArrayLike,
    shape: tuple[int, ...],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    mean = _broadcast_nonnegative(f"{name}_mean", mean_values, shape)
    try:
        moment = np.array(
            np.broadcast_to(np.asarray(moment_values, dtype=np.float64), shape),
            copy=True,
        )
    except ValueError as error:
        raise PhysicalDomainError(f"{name}_first_moment cannot broadcast to {shape}") from error
    if not np.all(np.isfinite(moment)):
        raise PhysicalDomainError(f"{name}_first_moment must be finite")
    state = limit_nonnegative_frequency_group_p1(mean, moment)
    if state.limited_group_count != 0:
        raise PhysicalDomainError(f"{name} must be non-negative realizable")
    return mean, moment


def _node_view(values: NDArray[np.float64]) -> NDArray[np.float64]:
    """把 ``(group,2,angle,depth)`` 合并成旧空间扫掠器的频率轴。"""
    return values.reshape(values.shape[0] * 2, *values.shape[2:])


def _record_limiter(
    count: int,
    ratio: float,
    state,
) -> tuple[int, float]:
    return (
        count + int(state.limited_group_count),
        max(ratio, float(state.maximum_prelimit_realizability_ratio)),
    )


def solve_mixed_frame_ale_p1_group_step(
    stencil: MixedFrameFrequencyStencil,
    old_depth_edges_cm: ArrayLike,
    new_depth_edges_cm: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    initial_active_lab_mean_intensity_density: ArrayLike,
    initial_active_lab_first_moment_intensity_density: ArrayLike,
    outer_lab_guard_mean_intensity_density: ArrayLike,
    outer_lab_guard_first_moment_intensity_density: ArrayLike,
    comoving_true_absorption_mean_per_cm: ArrayLike,
    comoving_true_absorption_first_moment_per_cm: ArrayLike,
    comoving_thermal_emissivity_mean_cgs: ArrayLike,
    comoving_thermal_emissivity_first_moment_cgs: ArrayLike,
    comoving_scattering_mean_per_cm: ArrayLike,
    comoving_scattering_first_moment_per_cm: ArrayLike,
    material_velocity_beta: ArrayLike,
    duration_s: float,
    *,
    left_exterior_mean_intensity: ArrayLike = 0.0,
    left_exterior_first_moment_intensity: ArrayLike = 0.0,
    right_exterior_mean_intensity: ArrayLike = 0.0,
    right_exterior_first_moment_intensity: ArrayLike = 0.0,
    periodic_spatial_boundary: bool = False,
    propagation_speed_cm_s: float = LIGHT_SPEED_CM_S,
    iterative_tolerance: float = 1.0e-10,
    iterative_maximum_iterations: int = 4096,
) -> MixedFrameALEP1Step:
    """联立求解 P1 频谱的 Lorentz 碰撞源、ALE 储能和空间通量。"""
    old_edge = _positive_edges("old_depth_edges_cm", old_depth_edges_cm)
    new_edge = _positive_edges("new_depth_edges_cm", new_depth_edges_cm)
    if old_edge.shape != new_edge.shape:
        raise PhysicalDomainError("old and new depth grids must share their size")
    duration = float(duration_s)
    speed = float(propagation_speed_cm_s)
    tolerance = float(iterative_tolerance)
    if not np.isfinite(duration) or duration <= 0.0:
        raise PhysicalDomainError("duration_s must be finite and positive")
    if not np.isfinite(speed) or speed <= 0.0:
        raise PhysicalDomainError("propagation_speed_cm_s must be finite and positive")
    if not np.isfinite(tolerance) or tolerance <= 0.0 or tolerance >= 1.0:
        raise PhysicalDomainError("iterative_tolerance must lie between zero and one")
    if (
        not isinstance(iterative_maximum_iterations, (int, np.integer))
        or isinstance(iterative_maximum_iterations, (bool, np.bool_))
        or int(iterative_maximum_iterations) < 1
    ):
        raise PhysicalDomainError("iterative_maximum_iterations must be positive")
    maximum_iterations = int(iterative_maximum_iterations)

    mu = np.asarray(direction_cosine, dtype=np.float64)
    weight = np.asarray(angular_weight, dtype=np.float64)
    if (
        mu.ndim != 1
        or weight.shape != mu.shape
        or mu.size < 2
        or not np.all(np.isfinite(mu))
        or not np.all(np.isfinite(weight))
        or np.any(mu <= -1.0)
        or np.any(mu >= 1.0)
        or np.any(weight <= 0.0)
        or not np.isclose(np.sum(weight), 2.0, rtol=2.0e-13, atol=2.0e-15)
    ):
        raise PhysicalDomainError("angular quadrature must be positive on (-1,1)")

    old_width = np.diff(old_edge)
    new_width = np.diff(new_edge)
    depth_points = new_width.size
    active_groups = stencil.physical_group_count
    collision_groups = stencil.comoving_collision_group_count
    outer_groups = stencil.outer_lab_group_count
    angle_points = mu.size
    active_shape = (active_groups, angle_points, depth_points)
    outer_shape = (outer_groups, angle_points, depth_points)
    collision_shape = (collision_groups, depth_points)
    initial_mean, initial_moment = _broadcast_realizable_p1(
        "initial_active_lab_intensity",
        initial_active_lab_mean_intensity_density,
        initial_active_lab_first_moment_intensity_density,
        active_shape,
    )
    outer_template_mean, outer_template_moment = _broadcast_realizable_p1(
        "outer_lab_guard_intensity",
        outer_lab_guard_mean_intensity_density,
        outer_lab_guard_first_moment_intensity_density,
        outer_shape,
    )
    absorption_mean, absorption_moment = _broadcast_realizable_p1(
        "comoving_true_absorption",
        comoving_true_absorption_mean_per_cm,
        comoving_true_absorption_first_moment_per_cm,
        collision_shape,
    )
    thermal_mean, thermal_moment = _broadcast_realizable_p1(
        "comoving_thermal_emissivity",
        comoving_thermal_emissivity_mean_cgs,
        comoving_thermal_emissivity_first_moment_cgs,
        collision_shape,
    )
    scattering_mean, scattering_moment = _broadcast_realizable_p1(
        "comoving_scattering",
        comoving_scattering_mean_per_cm,
        comoving_scattering_first_moment_per_cm,
        collision_shape,
    )
    if np.any((absorption_mean == 0.0) & (thermal_mean != 0.0)):
        raise PhysicalDomainError(
            "thermal emissivity cannot be non-zero where true absorption vanishes"
        )
    beta = np.asarray(material_velocity_beta, dtype=np.float64)
    if (
        beta.shape != (depth_points,)
        or not np.all(np.isfinite(beta))
        or np.any(np.abs(beta) >= 1.0)
        or np.any(np.abs(beta) > stencil.maximum_velocity_beta)
    ):
        raise PhysicalDomainError(
            "material_velocity_beta must match depth and remain inside the stencil bound"
        )
    left_mean, left_moment = _broadcast_realizable_p1(
        "left_exterior_intensity",
        left_exterior_mean_intensity,
        left_exterior_first_moment_intensity,
        (active_groups, angle_points),
    )
    right_mean, right_moment = _broadcast_realizable_p1(
        "right_exterior_intensity",
        right_exterior_mean_intensity,
        right_exterior_first_moment_intensity,
        (active_groups, angle_points),
    )
    if periodic_spatial_boundary and (
        np.any(left_mean != 0.0)
        or np.any(left_moment != 0.0)
        or np.any(right_mean != 0.0)
        or np.any(right_moment != 0.0)
    ):
        raise PhysicalDomainError(
            "periodic spatial boundaries cannot specify exterior intensities"
        )
    mesh_velocity = (new_edge - old_edge) / duration
    if not np.all(np.isfinite(mesh_velocity)) or np.any(np.abs(mesh_velocity) >= speed):
        raise PhysicalDomainError("ALE mesh velocity must be finite and subluminal")

    transform = lorentz_ray_transform(mu, weight, beta)
    extinction_mean_comoving = absorption_mean + scattering_mean
    extinction_moment_comoving = absorption_moment + scattering_moment
    extinction_angle_mean = np.broadcast_to(
        extinction_mean_comoving[:, None, :],
        (collision_groups, angle_points, depth_points),
    )
    extinction_angle_moment = np.broadcast_to(
        extinction_moment_comoving[:, None, :],
        (collision_groups, angle_points, depth_points),
    )
    lab_extinction = lorentz_remap_comoving_group_p1_extinction_to_lab(
        extinction_angle_mean,
        extinction_angle_moment,
        stencil.comoving_collision_edge_hz,
        stencil.active_lab_edge_hz,
        transform.doppler_lab_to_comoving,
    )
    cumulative_limiter = 0
    maximum_ratio = 0.0
    cumulative_limiter, maximum_ratio = _record_limiter(
        cumulative_limiter, maximum_ratio, lab_extinction
    )
    active_slice = slice(
        stencil.active_outer_group_start, stencil.active_outer_group_stop
    )
    initial_nodes = frequency_group_p1_gauss_node_values(
        initial_mean, initial_moment
    )
    left_nodes = frequency_group_p1_gauss_node_values(left_mean, left_moment)
    right_nodes = frequency_group_p1_gauss_node_values(right_mean, right_moment)
    lab_extinction_nodes = frequency_group_p1_gauss_node_values(
        lab_extinction.mean_density, lab_extinction.first_moment_density
    )

    current_mean = np.array(initial_mean, copy=True)
    current_moment = np.array(initial_moment, copy=True)
    final_change = np.inf
    for iteration in range(1, maximum_iterations + 1):
        iteration_limiter = 0
        outer_mean = np.array(outer_template_mean, copy=True)
        outer_moment = np.array(outer_template_moment, copy=True)
        outer_mean[active_slice] = current_mean
        outer_moment[active_slice] = current_moment
        comoving = comoving_group_p1_radiation(
            outer_mean,
            outer_moment,
            stencil.outer_lab_edge_hz,
            stencil.comoving_collision_edge_hz,
            mu,
            weight,
            beta,
        )
        iteration_limiter, maximum_ratio = _record_limiter(
            iteration_limiter, maximum_ratio, comoving
        )
        thermal_nodes = frequency_group_p1_gauss_node_values(
            thermal_mean, thermal_moment
        )
        scattering_nodes = frequency_group_p1_gauss_node_values(
            scattering_mean, scattering_moment
        )
        comoving_mean_nodes = frequency_group_p1_gauss_node_values(
            comoving.mean_intensity_density,
            comoving.mean_intensity_first_moment_density,
        )
        # 中文：两点 Gauss 规则精确积分两个 P1 函数的乘积。
        comoving_emissivity_nodes = (
            thermal_nodes + scattering_nodes * comoving_mean_nodes
        )
        comoving_emissivity = frequency_group_p1_from_gauss_node_values(
            comoving_emissivity_nodes
        )
        iteration_limiter, maximum_ratio = _record_limiter(
            iteration_limiter, maximum_ratio, comoving_emissivity
        )
        lab_emissivity = lorentz_remap_comoving_group_p1_emissivity_to_lab(
            np.broadcast_to(
                comoving_emissivity.mean_density[:, None, :],
                (collision_groups, angle_points, depth_points),
            ),
            np.broadcast_to(
                comoving_emissivity.first_moment_density[:, None, :],
                (collision_groups, angle_points, depth_points),
            ),
            stencil.comoving_collision_edge_hz,
            stencil.active_lab_edge_hz,
            transform.doppler_lab_to_comoving,
        )
        iteration_limiter, maximum_ratio = _record_limiter(
            iteration_limiter, maximum_ratio, lab_emissivity
        )
        lab_emissivity_nodes = frequency_group_p1_gauss_node_values(
            lab_emissivity.mean_density, lab_emissivity.first_moment_density
        )
        updated_nodes = _solve_positive_ray_transport(
            _node_view(initial_nodes),
            old_width,
            new_width,
            mu,
            mesh_velocity,
            _node_view(lab_extinction_nodes),
            _node_view(lab_emissivity_nodes),
            _node_view(left_nodes),
            _node_view(right_nodes),
            duration,
            speed,
            bool(periodic_spatial_boundary),
        ).reshape(active_groups, 2, angle_points, depth_points)
        updated = frequency_group_p1_from_gauss_node_values(updated_nodes)
        iteration_limiter, maximum_ratio = _record_limiter(
            iteration_limiter, maximum_ratio, updated
        )
        scale = max(
            float(np.max(np.abs(updated.mean_density))),
            float(np.max(np.abs(current_mean))),
            float(np.max(np.abs(updated.first_moment_density))),
            float(np.max(np.abs(current_moment))),
        )
        change = max(
            float(np.max(np.abs(updated.mean_density - current_mean))),
            float(
                np.max(
                    np.abs(updated.first_moment_density - current_moment)
                )
            ),
        )
        final_change = change / scale if scale > 0.0 else change
        current_mean = np.array(updated.mean_density, copy=True)
        current_moment = np.array(updated.first_moment_density, copy=True)
        cumulative_limiter += iteration_limiter
        if final_change <= tolerance:
            break
    else:
        raise ArithmeticError(
            "mixed-frame P1 ALE source iteration did not converge: "
            f"iterations={maximum_iterations}"
        )

    # 在最终状态重新构造源项，确保残差和能量账本使用同一状态。
    final_limiter = int(lab_extinction.limited_group_count)
    outer_mean = np.array(outer_template_mean, copy=True)
    outer_moment = np.array(outer_template_moment, copy=True)
    outer_mean[active_slice] = current_mean
    outer_moment[active_slice] = current_moment
    comoving = comoving_group_p1_radiation(
        outer_mean,
        outer_moment,
        stencil.outer_lab_edge_hz,
        stencil.comoving_collision_edge_hz,
        mu,
        weight,
        beta,
    )
    final_limiter, maximum_ratio = _record_limiter(
        final_limiter, maximum_ratio, comoving
    )
    thermal_nodes = frequency_group_p1_gauss_node_values(thermal_mean, thermal_moment)
    scattering_nodes = frequency_group_p1_gauss_node_values(
        scattering_mean, scattering_moment
    )
    comoving_mean_nodes = frequency_group_p1_gauss_node_values(
        comoving.mean_intensity_density,
        comoving.mean_intensity_first_moment_density,
    )
    comoving_emissivity_nodes = thermal_nodes + scattering_nodes * comoving_mean_nodes
    comoving_emissivity = frequency_group_p1_from_gauss_node_values(
        comoving_emissivity_nodes
    )
    final_limiter, maximum_ratio = _record_limiter(
        final_limiter, maximum_ratio, comoving_emissivity
    )
    lab_emissivity = lorentz_remap_comoving_group_p1_emissivity_to_lab(
        np.broadcast_to(
            comoving_emissivity.mean_density[:, None, :],
            (collision_groups, angle_points, depth_points),
        ),
        np.broadcast_to(
            comoving_emissivity.first_moment_density[:, None, :],
            (collision_groups, angle_points, depth_points),
        ),
        stencil.comoving_collision_edge_hz,
        stencil.active_lab_edge_hz,
        transform.doppler_lab_to_comoving,
    )
    final_limiter, maximum_ratio = _record_limiter(
        final_limiter, maximum_ratio, lab_emissivity
    )
    cumulative_limiter += final_limiter
    final_nodes = frequency_group_p1_gauss_node_values(current_mean, current_moment)
    lab_emissivity_nodes = frequency_group_p1_gauss_node_values(
        lab_emissivity.mean_density, lab_emissivity.first_moment_density
    )
    _, relative_node_residual, global_relative_residual = _coupled_residual(
        _node_view(final_nodes),
        _node_view(initial_nodes),
        old_width,
        new_width,
        mu,
        mesh_velocity,
        _node_view(lab_extinction_nodes),
        _node_view(lab_emissivity_nodes),
        _node_view(left_nodes),
        _node_view(right_nodes),
        duration,
        speed,
        bool(periodic_spatial_boundary),
    )
    relative_residual = np.max(
        relative_node_residual.reshape(active_groups, 2), axis=1
    )

    lab_angle_mean = 0.5 * np.einsum("m,fmd->fd", weight, current_mean)
    lab_angle_moment = 0.5 * np.einsum("m,fmd->fd", weight, current_moment)
    initial_angle_mean = 0.5 * np.einsum("m,fmd->fd", weight, initial_mean)
    left_face_nodes, right_face_nodes = _boundary_faces(
        _node_view(final_nodes),
        _node_view(left_nodes),
        _node_view(right_nodes),
        mu,
        mesh_velocity,
        speed,
        bool(periodic_spatial_boundary),
    )
    left_face_nodes = left_face_nodes.reshape(active_groups, 2, angle_points)
    right_face_nodes = right_face_nodes.reshape(active_groups, 2, angle_points)
    left_face = frequency_group_p1_from_gauss_node_values(left_face_nodes)
    right_face = frequency_group_p1_from_gauss_node_values(right_face_nodes)
    final_limiter, maximum_ratio = _record_limiter(
        final_limiter, maximum_ratio, left_face
    )
    final_limiter, maximum_ratio = _record_limiter(
        final_limiter, maximum_ratio, right_face
    )
    cumulative_limiter += (
        left_face.limited_group_count + right_face.limited_group_count
    )
    left_relative_speed = speed * mu - mesh_velocity[0]
    right_relative_speed = speed * mu - mesh_velocity[-1]
    left_flux = np.pi / speed * np.einsum(
        "m,fgm,m->f", weight, left_face_nodes, left_relative_speed
    )
    right_flux = np.pi / speed * np.einsum(
        "m,fgm,m->f", weight, right_face_nodes, right_relative_speed
    )
    initial_energy = 4.0 * np.pi / speed * np.sum(
        initial_angle_mean * old_width[None, :], axis=1
    )
    final_energy = 4.0 * np.pi / speed * np.sum(
        lab_angle_mean * new_width[None, :], axis=1
    )
    lab_collision_nodes = lab_emissivity_nodes - lab_extinction_nodes * final_nodes
    material_heating = -np.pi * np.sum(
        weight[None, None, :, None]
        * lab_collision_nodes
        * new_width[None, None, None, :],
        axis=(1, 2, 3),
    )
    ledger = final_energy - initial_energy + duration * (
        right_flux - left_flux + material_heating
    )
    ledger_scale = np.maximum.reduce(
        (
            np.abs(initial_energy),
            np.abs(final_energy),
            np.abs(final_energy - initial_energy),
            duration * np.abs(right_flux - left_flux),
            duration * np.abs(material_heating),
        )
    )
    relative_ledger = np.abs(ledger)
    active_scale = ledger_scale > 0.0
    relative_ledger[active_scale] /= ledger_scale[active_scale]
    active_frequency_width = np.diff(stencil.active_lab_edge_hz)
    total_ledger = float(np.sum(active_frequency_width * ledger))
    total_ledger_scale = max(
        float(np.sum(active_frequency_width * np.abs(initial_energy))),
        float(np.sum(active_frequency_width * np.abs(final_energy))),
        float(duration * np.sum(active_frequency_width * np.abs(right_flux - left_flux))),
        float(duration * np.sum(active_frequency_width * np.abs(material_heating))),
    )
    total_relative_ledger = (
        abs(total_ledger) / total_ledger_scale
        if total_ledger_scale > 0.0
        else abs(total_ledger)
    )

    comoving_angle_nodes = frequency_group_p1_gauss_node_values(
        comoving.angle_mean_density, comoving.angle_first_moment_density
    )
    extinction_comoving_nodes = frequency_group_p1_gauss_node_values(
        extinction_mean_comoving, extinction_moment_comoving
    )
    comoving_collision_nodes = (
        comoving_emissivity_nodes[:, :, None, :]
        - extinction_comoving_nodes[:, :, None, :] * comoving_angle_nodes
    )
    lab_source_energy = np.pi * np.einsum(
        "f,m,fgmd->d", active_frequency_width, weight, lab_collision_nodes
    )
    lab_source_momentum = np.pi / speed * np.einsum(
        "f,m,m,fgmd->d",
        active_frequency_width,
        weight,
        mu,
        lab_collision_nodes,
    )
    collision_frequency_width = np.diff(stencil.comoving_collision_edge_hz)
    comoving_source_energy = np.pi * np.einsum(
        "f,md,fgmd->d",
        collision_frequency_width,
        transform.comoving_angular_weight,
        comoving_collision_nodes,
    )
    comoving_source_momentum = np.pi / speed * np.einsum(
        "f,md,md,fgmd->d",
        collision_frequency_width,
        transform.comoving_angular_weight,
        transform.comoving_direction_cosine,
        comoving_collision_nodes,
    )
    gamma = 1.0 / np.sqrt(1.0 - beta**2)
    expected_lab_energy = gamma * (
        comoving_source_energy + beta * speed * comoving_source_momentum
    )
    expected_lab_momentum = gamma * (
        comoving_source_momentum + beta * comoving_source_energy / speed
    )
    four_energy_residual = lab_source_energy - expected_lab_energy
    four_momentum_residual = lab_source_momentum - expected_lab_momentum
    minimum_reconstructed = float(np.min(current_mean - 3.0 * np.abs(current_moment)))

    arrays = (
        current_mean,
        current_moment,
        lab_angle_mean,
        lab_angle_moment,
        comoving.angle_mean_density,
        comoving.angle_first_moment_density,
        comoving.mean_intensity_density,
        comoving.mean_intensity_first_moment_density,
        lab_extinction.mean_density,
        lab_extinction.first_moment_density,
        lab_emissivity.mean_density,
        lab_emissivity.first_moment_density,
        left_face.mean_density,
        left_face.first_moment_density,
        right_face.mean_density,
        right_face.first_moment_density,
        initial_energy,
        final_energy,
        left_flux,
        right_flux,
        material_heating,
        ledger,
        relative_ledger,
        lab_source_energy,
        lab_source_momentum,
        comoving_source_energy,
        comoving_source_momentum,
        four_energy_residual,
        four_momentum_residual,
        relative_residual,
    )
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ArithmeticError("mixed-frame P1 ALE diagnostics became non-finite")
    return MixedFrameALEP1Step(
        final_lab_mean_intensity_density=_readonly(current_mean),
        final_lab_first_moment_intensity_density=_readonly(current_moment),
        final_lab_mean_intensity_angle_average=_readonly(lab_angle_mean),
        final_lab_first_moment_intensity_angle_average=_readonly(lab_angle_moment),
        final_comoving_angle_mean_intensity_density=comoving.angle_mean_density,
        final_comoving_angle_first_moment_intensity_density=(
            comoving.angle_first_moment_density
        ),
        final_comoving_mean_intensity_density=comoving.mean_intensity_density,
        final_comoving_mean_first_moment_intensity_density=(
            comoving.mean_intensity_first_moment_density
        ),
        lab_extinction_mean_per_cm=lab_extinction.mean_density,
        lab_extinction_first_moment_per_cm=lab_extinction.first_moment_density,
        lab_emissivity_mean_cgs=lab_emissivity.mean_density,
        lab_emissivity_first_moment_cgs=lab_emissivity.first_moment_density,
        left_ale_face_mean_intensity=left_face.mean_density,
        left_ale_face_first_moment_intensity=left_face.first_moment_density,
        right_ale_face_mean_intensity=right_face.mean_density,
        right_ale_face_first_moment_intensity=right_face.first_moment_density,
        initial_radiation_energy_group_erg_cm2_hz=_readonly(initial_energy),
        final_radiation_energy_group_erg_cm2_hz=_readonly(final_energy),
        left_ale_energy_flux_group_cgs=_readonly(left_flux),
        right_ale_energy_flux_group_cgs=_readonly(right_flux),
        material_heating_group_erg_s_cm2_hz=_readonly(material_heating),
        energy_ledger_residual_group_erg_cm2_hz=_readonly(ledger),
        relative_energy_ledger_residual_group=_readonly(relative_ledger),
        radiation_source_energy_lab_erg_s_cm3=_readonly(lab_source_energy),
        radiation_source_momentum_lab_dyn_cm3=_readonly(lab_source_momentum),
        radiation_source_energy_comoving_erg_s_cm3=_readonly(
            comoving_source_energy
        ),
        radiation_source_momentum_comoving_dyn_cm3=_readonly(
            comoving_source_momentum
        ),
        four_force_energy_residual_erg_s_cm3=_readonly(four_energy_residual),
        four_force_momentum_residual_dyn_cm3=_readonly(four_momentum_residual),
        relative_coupled_residual_group=_readonly(relative_residual),
        mesh_edge_velocity_cm_s=_readonly(mesh_velocity),
        material_velocity_beta=_readonly(np.array(beta, copy=True)),
        fixed_point_iterations=iteration,
        final_fixed_point_change=final_change,
        total_relative_energy_ledger_residual=total_relative_ledger,
        global_scale_normalized_coupled_residual=global_relative_residual,
        maximum_group_relative_coupled_residual=float(np.max(relative_residual)),
        minimum_reconstructed_intensity=minimum_reconstructed,
        maximum_mesh_speed_to_light=float(np.max(np.abs(mesh_velocity)) / speed),
        cumulative_limiter_activation_count=cumulative_limiter,
        final_limiter_activation_count=final_limiter,
        maximum_prelimit_realizability_ratio=maximum_ratio,
    )
