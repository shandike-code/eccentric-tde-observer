"""完整 Lorentz 物质源与一维 ALE 辐射储能的联立组件。

实验室系负责守恒推进强度、移动控制体和空间通量；局域吸收、Milne 热发射
与相干各向同性散射在物质共动系计算，再按各自 Lorentz 不变量回到实验室系。
本模块固定物质温度与 H/He 布居，只关闭混合系辐射组件门，不推进物质状态。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .mixed_frame_frequency import (
    comoving_group_radiation,
    lorentz_ray_transform,
    lorentz_remap_comoving_group_emissivity_to_lab,
    lorentz_remap_comoving_group_extinction_to_lab,
    threshold_log_frequency_groups,
)
from .radiation import LIGHT_SPEED_CM_S
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class MixedFrameFrequencyStencil:
    """物理实验室组、一次变换共动组与两次变换守护组。"""

    outer_lab_edge_hz: NDArray[np.float64]
    comoving_collision_edge_hz: NDArray[np.float64]
    active_lab_edge_hz: NDArray[np.float64]
    active_outer_group_start: int
    active_outer_group_stop: int
    physical_group_count: int
    comoving_collision_group_count: int
    outer_lab_group_count: int
    groups_per_decade: int | None
    maximum_velocity_beta: float


@dataclass(frozen=True)
class MixedFrameALEStep:
    """一个完整 Lorentz 物质源与 ALE 联立的后向 Euler 辐射步。"""

    final_lab_intensity_density: NDArray[np.float64]
    final_lab_mean_intensity_density: NDArray[np.float64]
    final_comoving_angle_intensity_density: NDArray[np.float64]
    final_comoving_mean_intensity_density: NDArray[np.float64]
    lab_extinction_per_cm: NDArray[np.float64]
    lab_emissivity_cgs: NDArray[np.float64]
    mesh_edge_velocity_cm_s: NDArray[np.float64]
    material_velocity_beta: NDArray[np.float64]
    left_ale_face_intensity: NDArray[np.float64]
    right_ale_face_intensity: NDArray[np.float64]
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
    fixed_point_iterations: int
    final_fixed_point_change: float
    total_relative_energy_ledger_residual: float
    global_scale_normalized_coupled_residual: float
    maximum_group_relative_coupled_residual: float
    minimum_intensity: float
    maximum_mesh_speed_to_light: float
    fixed_point_converged: bool


@dataclass(frozen=True)
class MixedFrameALESourceMap:
    """只返回一次或多次源映射更新，不重复构造末态科学诊断。"""

    final_lab_intensity_density: NDArray[np.float64]
    fixed_point_iterations: int
    final_fixed_point_change: float
    minimum_intensity: float
    maximum_mesh_speed_to_light: float
    fixed_point_converged: bool


def _physical_edges_and_slice(grid) -> tuple[NDArray[np.float64], int, int]:
    active = np.flatnonzero(grid.physical_group_mask)
    if active.size == 0 or np.any(np.diff(active) != 1):
        raise ArithmeticError("physical frequency groups must be contiguous")
    start = int(active[0])
    stop = int(active[-1] + 1)
    return np.array(grid.edge_hz[start : stop + 1], copy=True), start, stop


def mixed_frame_frequency_stencil(
    minimum_energy_ev: float,
    maximum_energy_ev: float,
    groups_per_decade: int,
    maximum_velocity_beta: float,
) -> MixedFrameFrequencyStencil:
    """构造一次碰撞往返所需的两层显式 Doppler 守护频率网格。"""
    outer = threshold_log_frequency_groups(
        minimum_energy_ev,
        maximum_energy_ev,
        groups_per_decade,
        maximum_velocity_beta=maximum_velocity_beta,
        guard_transform_count=2,
    )
    collision = threshold_log_frequency_groups(
        minimum_energy_ev,
        maximum_energy_ev,
        groups_per_decade,
        maximum_velocity_beta=maximum_velocity_beta,
        guard_transform_count=1,
    )
    active_edge, start, stop = _physical_edges_and_slice(outer)
    beta = float(maximum_velocity_beta)
    gamma = 1.0 / np.sqrt(1.0 - beta**2)
    minimum_doppler = gamma * (1.0 - beta)
    maximum_doppler = gamma * (1.0 + beta)
    tolerance = 32.0 * np.finfo(np.float64).eps
    coverage = (
        collision.edge_hz[0]
        <= minimum_doppler * active_edge[0] * (1.0 + tolerance)
        and collision.edge_hz[-1]
        >= maximum_doppler * active_edge[-1] * (1.0 - tolerance)
        and outer.edge_hz[0]
        <= collision.edge_hz[0] / maximum_doppler * (1.0 + tolerance)
        and outer.edge_hz[-1]
        >= collision.edge_hz[-1] / minimum_doppler * (1.0 - tolerance)
    )
    if not coverage:
        raise ArithmeticError("mixed-frame Doppler guard stencil is insufficient")
    return MixedFrameFrequencyStencil(
        outer_lab_edge_hz=_readonly(np.array(outer.edge_hz, copy=True)),
        comoving_collision_edge_hz=_readonly(
            np.array(collision.edge_hz, copy=True)
        ),
        active_lab_edge_hz=_readonly(active_edge),
        active_outer_group_start=start,
        active_outer_group_stop=stop,
        physical_group_count=stop - start,
        comoving_collision_group_count=collision.centre_hz.size,
        outer_lab_group_count=outer.centre_hz.size,
        groups_per_decade=int(groups_per_decade),
        maximum_velocity_beta=beta,
    )


def mixed_frame_frequency_stencil_from_active_edges(
    active_lab_edge_hz: ArrayLike,
    maximum_velocity_beta: float,
) -> MixedFrameFrequencyStencil:
    """为任意严格递增物理组边界构造两次 Lorentz 往返守护带。

    物理边界会原样嵌入共动碰撞网格和外层实验室网格；守护组只扩展
    Doppler 查询定义域，不进入正式频带积分。
    """
    active = _positive_edges("active_lab_edge_hz", active_lab_edge_hz)
    beta = float(maximum_velocity_beta)
    if not np.isfinite(beta) or beta < 0.0 or beta >= 1.0:
        raise PhysicalDomainError(
            "maximum_velocity_beta must be finite and lie in [0, 1)"
        )
    if beta == 0.0:
        collision = np.array(active, copy=True)
        outer = np.array(active, copy=True)
        start = 0
    else:
        gamma = 1.0 / np.sqrt(1.0 - beta**2)
        minimum_doppler = gamma * (1.0 - beta)
        maximum_doppler = gamma * (1.0 + beta)
        margin = 128.0 * np.finfo(np.float64).eps
        # 中文：一次变换守护共动碰撞查询，两次变换守护返回实验室系的源项查询。
        collision_low = minimum_doppler * active[0] * (1.0 - margin)
        collision_high = maximum_doppler * active[-1] * (1.0 + margin)
        outer_low = collision_low / maximum_doppler * (1.0 - margin)
        outer_high = collision_high / minimum_doppler * (1.0 + margin)
        collision = np.concatenate(
            ([collision_low], np.array(active, copy=True), [collision_high])
        )
        outer = np.concatenate(
            (
                [outer_low, collision_low],
                np.array(active, copy=True),
                [collision_high, outer_high],
            )
        )
        start = 2
    if np.any(np.diff(collision) <= 0.0) or np.any(np.diff(outer) <= 0.0):
        raise ArithmeticError("custom mixed-frame guard edges lost monotonicity")
    physical_groups = active.size - 1
    return MixedFrameFrequencyStencil(
        outer_lab_edge_hz=_readonly(np.array(outer, copy=True)),
        comoving_collision_edge_hz=_readonly(np.array(collision, copy=True)),
        active_lab_edge_hz=_readonly(np.array(active, copy=True)),
        active_outer_group_start=start,
        active_outer_group_stop=start + physical_groups,
        physical_group_count=physical_groups,
        comoving_collision_group_count=collision.size - 1,
        outer_lab_group_count=outer.size - 1,
        groups_per_decade=None,
        maximum_velocity_beta=beta,
    )


def _positive_edges(name: str, values: ArrayLike) -> NDArray[np.float64]:
    edge = np.asarray(values, dtype=np.float64)
    if (
        edge.ndim != 1
        or edge.size < 2
        or not np.all(np.isfinite(edge))
        or np.any(np.diff(edge) <= 0.0)
    ):
        raise PhysicalDomainError(f"{name} must be finite and strictly increasing")
    return edge


def _broadcast_nonnegative(
    name: str, values: ArrayLike, shape: tuple[int, ...]
) -> NDArray[np.float64]:
    try:
        array = np.array(
            np.broadcast_to(np.asarray(values, dtype=np.float64), shape), copy=True
        )
    except ValueError as error:
        raise PhysicalDomainError(f"{name} cannot broadcast to {shape}") from error
    if not np.all(np.isfinite(array)) or np.any(array < 0.0):
        raise PhysicalDomainError(f"{name} must be finite and non-negative")
    return array


def _solve_positive_ray_transport(
    initial: NDArray[np.float64],
    old_width: NDArray[np.float64],
    new_width: NDArray[np.float64],
    direction_cosine: NDArray[np.float64],
    mesh_velocity_cm_s: NDArray[np.float64],
    lab_extinction_per_cm: NDArray[np.float64],
    lab_emissivity_cgs: NDArray[np.float64],
    left_exterior: NDArray[np.float64],
    right_exterior: NDArray[np.float64],
    duration_s: float,
    propagation_speed_cm_s: float,
    periodic_spatial_boundary: bool,
) -> NDArray[np.float64]:
    """在给定逐射线实验室碰撞源时做正性单调隐式空间扫掠。"""
    frequency_points, angle_points, depth_points = initial.shape
    solution = np.empty_like(initial)
    time_rhs = old_width[None, None, :] / duration_s * initial
    collision_rhs = (
        propagation_speed_cm_s
        * new_width[None, None, :]
        * lab_emissivity_cgs
    )
    relative_speed = (
        propagation_speed_cm_s * direction_cosine[:, None]
        - mesh_velocity_cm_s[None, :]
    )
    if periodic_spatial_boundary:
        if depth_points != 1:
            raise PhysicalDomainError(
                "mixed-frame periodic control currently requires exactly one cell"
            )
        if not np.allclose(
            relative_speed[:, 0],
            relative_speed[:, 1],
            rtol=2.0e-13,
            atol=2.0e-13 * propagation_speed_cm_s,
        ):
            raise PhysicalDomainError(
                "one-cell periodic control requires equal face velocities"
            )
        diagonal = (
            new_width[0] / duration_s
            + propagation_speed_cm_s
            * new_width[0]
            * lab_extinction_per_cm[:, :, 0]
        )
        solution[:, :, 0] = (
            time_rhs[:, :, 0] + collision_rhs[:, :, 0]
        ) / diagonal
    else:
        for angle in range(angle_points):
            speed = relative_speed[angle]
            if np.all(speed > 0.0):
                for depth in range(depth_points):
                    diagonal = (
                        new_width[depth] / duration_s
                        + propagation_speed_cm_s
                        * new_width[depth]
                        * lab_extinction_per_cm[:, angle, depth]
                        + speed[depth + 1]
                    )
                    incoming = (
                        left_exterior[:, angle]
                        if depth == 0
                        else solution[:, angle, depth - 1]
                    )
                    solution[:, angle, depth] = (
                        time_rhs[:, angle, depth]
                        + collision_rhs[:, angle, depth]
                        + speed[depth] * incoming
                    ) / diagonal
            elif np.all(speed < 0.0):
                for depth in range(depth_points - 1, -1, -1):
                    diagonal = (
                        new_width[depth] / duration_s
                        + propagation_speed_cm_s
                        * new_width[depth]
                        * lab_extinction_per_cm[:, angle, depth]
                        - speed[depth]
                    )
                    incoming = (
                        right_exterior[:, angle]
                        if depth == depth_points - 1
                        else solution[:, angle, depth + 1]
                    )
                    solution[:, angle, depth] = (
                        time_rhs[:, angle, depth]
                        + collision_rhs[:, angle, depth]
                        - speed[depth + 1] * incoming
                    ) / diagonal
            else:
                raise PhysicalDomainError(
                    "an ALE characteristic reversed direction inside the column"
                )
    if not np.all(np.isfinite(solution)) or np.any(solution < 0.0):
        raise ArithmeticError("mixed-frame transport produced invalid intensity")
    return solution


def _solve_step_characteristics_ray_transport(
    initial: NDArray[np.float64],
    old_width: NDArray[np.float64],
    new_width: NDArray[np.float64],
    direction_cosine: NDArray[np.float64],
    mesh_velocity_cm_s: NDArray[np.float64],
    lab_extinction_per_cm: NDArray[np.float64],
    lab_emissivity_cgs: NDArray[np.float64],
    left_exterior: NDArray[np.float64],
    right_exterior: NDArray[np.float64],
    duration_s: float,
    propagation_speed_cm_s: float,
    allow_turning_ray_upwind: bool = False,
    allow_signed_fields: bool = False,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """用单元常源精确特征积分推进一个后向 Euler ALE 步。

    每个单元内网格速度为线性函数，碰撞系数和发射率为常数。返回量是
    单元体平均强度及唯一共享的界面强度，因此离散能量账本仍严格守恒。
    """
    frequency_points, angle_points, depth_points = initial.shape
    solution = np.empty_like(initial)
    face_intensity = np.empty(
        (frequency_points, angle_points, depth_points + 1), dtype=np.float64
    )
    relative_speed = (
        propagation_speed_cm_s * direction_cosine[:, None]
        - mesh_velocity_cm_s[None, :]
    )
    for angle in range(angle_points):
        speed = relative_speed[angle]
        if np.all(speed > 0.0):
            order = range(depth_points)
            face_intensity[:, angle, 0] = left_exterior[:, angle]
            incoming_face = 0
            outgoing_offset = 1
        elif np.all(speed < 0.0):
            order = range(depth_points - 1, -1, -1)
            face_intensity[:, angle, -1] = right_exterior[:, angle]
            incoming_face = 1
            outgoing_offset = 0
        else:
            if not allow_turning_ray_upwind:
                raise PhysicalDomainError(
                    "a step-characteristic reversed direction inside the column"
                )
            # 中文：只把真实变号的掠射方向交给守恒隐式迎风三对角系统。
            turning_solution, turning_faces = _solve_turning_ray_upwind(
                initial[:, angle],
                old_width,
                new_width,
                speed,
                propagation_speed_cm_s,
                lab_extinction_per_cm[:, angle],
                lab_emissivity_cgs[:, angle],
                left_exterior[:, angle],
                right_exterior[:, angle],
                duration_s,
                allow_signed_fields=allow_signed_fields,
            )
            solution[:, angle] = turning_solution
            face_intensity[:, angle] = turning_faces
            continue
        for depth in order:
            left_speed = float(speed[depth])
            right_speed = float(speed[depth + 1])
            speed_slope = right_speed - left_speed
            incoming_index = depth + incoming_face
            outgoing_index = depth + outgoing_offset
            incoming = face_intensity[:, angle, incoming_index]
            incoming_speed = (
                left_speed if left_speed > 0.0 else right_speed
            )
            outgoing_speed = (
                right_speed if left_speed > 0.0 else left_speed
            )
            coefficient = (
                new_width[depth] / duration_s
                + propagation_speed_cm_s
                * new_width[depth]
                * lab_extinction_per_cm[:, angle, depth]
            )
            right_hand_side = (
                old_width[depth] / duration_s * initial[:, angle, depth]
                + propagation_speed_cm_s
                * new_width[depth]
                * lab_emissivity_cgs[:, angle, depth]
            )
            equilibrium_denominator = coefficient + speed_slope
            if (
                not np.all(np.isfinite(coefficient))
                or np.any(coefficient <= 0.0)
                or np.any(equilibrium_denominator <= 0.0)
            ):
                raise ArithmeticError(
                    "step-characteristic coefficients lost positivity"
                )
            equilibrium = right_hand_side / equilibrium_denominator
            speed_scale = max(abs(incoming_speed), abs(outgoing_speed))
            if abs(speed_slope) <= 64.0 * np.finfo(np.float64).eps * speed_scale:
                optical_distance = coefficient / abs(incoming_speed)
                attenuation = np.exp(-optical_distance)
                average_factor = -np.expm1(-optical_distance) / optical_distance
            else:
                log_speed_ratio = np.log(
                    abs(outgoing_speed) / abs(incoming_speed)
                )
                attenuation_exponent = -(
                    1.0 + coefficient / speed_slope
                ) * log_speed_ratio
                average_exponent = -(
                    coefficient / speed_slope
                ) * log_speed_ratio
                attenuation = np.exp(attenuation_exponent)
                average_factor = (
                    abs(incoming_speed)
                    / coefficient
                    * -np.expm1(average_exponent)
                )
            if (
                not np.all(np.isfinite(attenuation))
                or not np.all(np.isfinite(average_factor))
                or np.any(attenuation < 0.0)
                or np.any(attenuation > 1.0 + 2.0e-12)
                or np.any(average_factor < 0.0)
                or np.any(average_factor > 1.0 + 2.0e-12)
            ):
                raise ArithmeticError(
                    "step-characteristic attenuation left its positive domain"
                )
            outgoing = equilibrium + (incoming - equilibrium) * attenuation
            average = equilibrium + (incoming - equilibrium) * average_factor
            face_intensity[:, angle, outgoing_index] = outgoing
            solution[:, angle, depth] = average
    if (
        not np.all(np.isfinite(solution))
        or not np.all(np.isfinite(face_intensity))
        or (not allow_signed_fields and np.any(solution < 0.0))
        or (not allow_signed_fields and np.any(face_intensity < 0.0))
    ):
        raise ArithmeticError(
            "step-characteristic transport produced invalid intensity"
        )
    return solution, face_intensity


def _solve_turning_ray_upwind(
    initial: NDArray[np.float64],
    old_width: NDArray[np.float64],
    new_width: NDArray[np.float64],
    relative_face_speed_cm_s: NDArray[np.float64],
    propagation_speed_cm_s: float,
    lab_extinction_per_cm: NDArray[np.float64],
    lab_emissivity_cgs: NDArray[np.float64],
    left_exterior: NDArray[np.float64],
    right_exterior: NDArray[np.float64],
    duration_s: float,
    *,
    allow_signed_fields: bool = False,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """守恒求解一个在柱内变号的 ALE 掠射方向。"""
    frequency_points, depth_points = initial.shape
    speed = np.asarray(relative_face_speed_cm_s, dtype=np.float64)
    if speed.shape != (depth_points + 1,):
        raise PhysicalDomainError("turning-ray face speed does not match the grid")
    diagonal = (
        new_width[None, :] / duration_s
        + propagation_speed_cm_s
        * new_width[None, :]
        * lab_extinction_per_cm
        + np.maximum(speed[1:], 0.0)[None, :]
        - np.minimum(speed[:-1], 0.0)[None, :]
    )
    right_hand_side = (
        old_width[None, :] / duration_s * initial
        + propagation_speed_cm_s * new_width[None, :] * lab_emissivity_cgs
    )
    if speed[0] > 0.0:
        right_hand_side[:, 0] += speed[0] * left_exterior
    if speed[-1] < 0.0:
        right_hand_side[:, -1] -= speed[-1] * right_exterior
    lower = -np.maximum(speed[1:-1], 0.0)
    upper = np.minimum(speed[1:-1], 0.0)
    if (
        not np.all(np.isfinite(diagonal))
        or not np.all(np.isfinite(right_hand_side))
        or np.any(diagonal <= 0.0)
        or (not allow_signed_fields and np.any(right_hand_side < 0.0))
    ):
        raise ArithmeticError("turning-ray upwind system lost positivity")

    # 中文：Thomas 消元沿频率向量化；矩阵是严格对角占优的 M 矩阵。
    modified_upper = np.empty((frequency_points, max(depth_points - 1, 0)))
    solution = np.empty_like(initial)
    denominator = diagonal[:, 0]
    if depth_points > 1:
        modified_upper[:, 0] = upper[0] / denominator
    solution[:, 0] = right_hand_side[:, 0] / denominator
    for depth in range(1, depth_points):
        denominator = diagonal[:, depth] - lower[depth - 1] * modified_upper[:, depth - 1]
        if not np.all(np.isfinite(denominator)) or np.any(denominator <= 0.0):
            raise ArithmeticError("turning-ray Thomas denominator lost positivity")
        if depth < depth_points - 1:
            modified_upper[:, depth] = upper[depth] / denominator
        solution[:, depth] = (
            right_hand_side[:, depth]
            - lower[depth - 1] * solution[:, depth - 1]
        ) / denominator
    for depth in range(depth_points - 2, -1, -1):
        solution[:, depth] -= modified_upper[:, depth] * solution[:, depth + 1]

    face = np.empty((frequency_points, depth_points + 1), dtype=np.float64)
    face[:, 0] = left_exterior if speed[0] >= 0.0 else solution[:, 0]
    for index in range(1, depth_points):
        face[:, index] = (
            solution[:, index - 1] if speed[index] >= 0.0 else solution[:, index]
        )
    face[:, -1] = solution[:, -1] if speed[-1] >= 0.0 else right_exterior
    if (
        not np.all(np.isfinite(solution))
        or not np.all(np.isfinite(face))
        or (not allow_signed_fields and np.any(solution < 0.0))
        or (not allow_signed_fields and np.any(face < 0.0))
    ):
        raise ArithmeticError("turning-ray upwind solve produced invalid intensity")
    return solution, face


def _boundary_faces(
    intensity: NDArray[np.float64],
    left_exterior: NDArray[np.float64],
    right_exterior: NDArray[np.float64],
    direction_cosine: NDArray[np.float64],
    mesh_velocity_cm_s: NDArray[np.float64],
    propagation_speed_cm_s: float,
    periodic_spatial_boundary: bool,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    left_speed = propagation_speed_cm_s * direction_cosine - mesh_velocity_cm_s[0]
    right_speed = propagation_speed_cm_s * direction_cosine - mesh_velocity_cm_s[-1]
    if periodic_spatial_boundary:
        face = np.array(intensity[:, :, 0], copy=True)
        return face, np.array(face, copy=True)
    left = np.where(
        left_speed[None, :] >= 0.0,
        left_exterior,
        intensity[:, :, 0],
    )
    right = np.where(
        right_speed[None, :] >= 0.0,
        intensity[:, :, -1],
        right_exterior,
    )
    return left, right


def _coupled_residual(
    final: NDArray[np.float64],
    initial: NDArray[np.float64],
    old_width: NDArray[np.float64],
    new_width: NDArray[np.float64],
    direction_cosine: NDArray[np.float64],
    mesh_velocity_cm_s: NDArray[np.float64],
    extinction: NDArray[np.float64],
    emissivity: NDArray[np.float64],
    left_exterior: NDArray[np.float64],
    right_exterior: NDArray[np.float64],
    duration_s: float,
    propagation_speed_cm_s: float,
    periodic_spatial_boundary: bool,
    transport_face_intensity: NDArray[np.float64] | None = None,
) -> tuple[NDArray[np.float64], NDArray[np.float64], float]:
    frequency_points, angle_points, depth_points = final.shape
    storage = (
        new_width[None, None, :] * final
        - old_width[None, None, :] * initial
    ) / duration_s
    collision = propagation_speed_cm_s * new_width[None, None, :] * (
        emissivity - extinction * final
    )
    flux_divergence = np.empty_like(final)
    face_term_scale = np.zeros(frequency_points)
    if periodic_spatial_boundary:
        flux_divergence.fill(0.0)
        face_term_scale = np.max(
            np.abs(
                (propagation_speed_cm_s * direction_cosine)[None, :, None]
                * final
            ),
            axis=(1, 2),
        )
    elif transport_face_intensity is not None:
        expected_shape = (frequency_points, angle_points, depth_points + 1)
        if transport_face_intensity.shape != expected_shape:
            raise PhysicalDomainError(
                "transport face intensity does not match the coupled residual"
            )
        for angle, cosine in enumerate(direction_cosine):
            face_speed = propagation_speed_cm_s * cosine - mesh_velocity_cm_s
            face_intensity = transport_face_intensity[:, angle]
            flux_divergence[:, angle] = np.diff(
                face_speed[None, :] * face_intensity, axis=1
            )
            face_term_scale = np.maximum(
                face_term_scale,
                np.max(
                    np.abs(face_speed[None, :] * face_intensity), axis=1
                ),
            )
    else:
        for angle, cosine in enumerate(direction_cosine):
            face_speed = propagation_speed_cm_s * cosine - mesh_velocity_cm_s
            face_intensity = np.empty((frequency_points, depth_points + 1))
            face_intensity[:, 0] = np.where(
                face_speed[0] >= 0.0,
                left_exterior[:, angle],
                final[:, angle, 0],
            )
            for face in range(1, depth_points):
                face_intensity[:, face] = np.where(
                    face_speed[face] >= 0.0,
                    final[:, angle, face - 1],
                    final[:, angle, face],
                )
            face_intensity[:, -1] = np.where(
                face_speed[-1] >= 0.0,
                final[:, angle, -1],
                right_exterior[:, angle],
            )
            flux_divergence[:, angle] = np.diff(
                face_speed[None, :] * face_intensity, axis=1
            )
            face_term_scale = np.maximum(
                face_term_scale,
                np.max(
                    np.abs(face_speed[None, :] * face_intensity), axis=1
                ),
            )
    residual = storage + flux_divergence - collision
    scale = np.maximum.reduce(
        (
            np.max(
                np.abs(new_width[None, None, :] / duration_s * final),
                axis=(1, 2),
            ),
            np.max(
                np.abs(old_width[None, None, :] / duration_s * initial),
                axis=(1, 2),
            ),
            np.max(
                np.abs(
                    propagation_speed_cm_s
                    * new_width[None, None, :]
                    * emissivity
                ),
                axis=(1, 2),
            ),
            np.max(
                np.abs(
                    propagation_speed_cm_s
                    * new_width[None, None, :]
                    * extinction
                    * final
                ),
                axis=(1, 2),
            ),
            face_term_scale,
        )
    )
    relative = np.max(np.abs(residual), axis=(1, 2))
    active = scale > 0.0
    relative[active] /= scale[active]
    global_scale = float(np.max(scale))
    global_relative = (
        float(np.max(np.abs(residual))) / global_scale
        if global_scale > 0.0
        else float(np.max(np.abs(residual)))
    )
    return residual, relative, global_relative


def solve_mixed_frame_ale_group_step(
    stencil: MixedFrameFrequencyStencil,
    old_depth_edges_cm: ArrayLike,
    new_depth_edges_cm: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    initial_active_lab_intensity_density: ArrayLike,
    outer_lab_guard_intensity_density: ArrayLike,
    comoving_true_absorption_per_cm: ArrayLike,
    comoving_thermal_emissivity_cgs: ArrayLike,
    comoving_scattering_per_cm: ArrayLike,
    material_velocity_beta: ArrayLike,
    duration_s: float,
    *,
    left_exterior_intensity: ArrayLike = 0.0,
    right_exterior_intensity: ArrayLike = 0.0,
    periodic_spatial_boundary: bool = False,
    propagation_speed_cm_s: float = LIGHT_SPEED_CM_S,
    iterative_tolerance: float = 1.0e-10,
    iterative_maximum_iterations: int = 4096,
    apply_intensity_lorentz: bool = True,
    apply_extinction_lorentz: bool = True,
    apply_emissivity_lorentz: bool = True,
    iteration_observer: Callable[[int, NDArray[np.float64]], None] | None = None,
    source_iteration_initial_guess: ArrayLike | None = None,
    diagnostic_fixed_iteration_count: int | None = None,
    spatial_scheme: str = "upwind_finite_volume",
    source_map_only: bool = False,
) -> MixedFrameALEStep | MixedFrameALESourceMap:
    """把完整 Lorentz 物质碰撞算子与 ALE 储能/输运写入同一隐式残差。

    三个 ``apply_*_lorentz`` 参数只供分量级诊断；正式物理路径必须保持默认值。
    ``source_iteration_initial_guess`` 与 ``diagnostic_fixed_iteration_count``
    只用于复现固定点映射截面。指定固定次数时允许返回未收敛状态，调用方必须检查
    ``fixed_point_converged``，不得把诊断结果当成正式谱。
    ``spatial_scheme='step_characteristics'`` 使用线性 ALE 网格速度下的单元常源
    精确特征积分；``hybrid_step_turning_upwind`` 只把柱内变号方向交给守恒隐式迎风
    三对角系统。默认一阶迎风路径保持历史回归不变。
    ``source_map_only=True`` 只供外层 block-Jacobi 中间迭代：它返回同一个强度更新，
    但不重复构造末态共动场、残差和能量账本；全局收敛后仍必须运行完整诊断路径。
    """
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
        raise PhysicalDomainError(
            "iterative_tolerance must lie strictly between zero and one"
        )
    if (
        not isinstance(iterative_maximum_iterations, (int, np.integer))
        or isinstance(iterative_maximum_iterations, (bool, np.bool_))
        or int(iterative_maximum_iterations) < 1
    ):
        raise PhysicalDomainError(
            "iterative_maximum_iterations must be a positive integer"
        )
    maximum_iterations = int(iterative_maximum_iterations)
    if diagnostic_fixed_iteration_count is not None and (
        not isinstance(diagnostic_fixed_iteration_count, (int, np.integer))
        or isinstance(diagnostic_fixed_iteration_count, (bool, np.bool_))
        or int(diagnostic_fixed_iteration_count) < 1
    ):
        raise PhysicalDomainError(
            "diagnostic_fixed_iteration_count must be a positive integer"
        )
    iteration_limit = (
        maximum_iterations
        if diagnostic_fixed_iteration_count is None
        else int(diagnostic_fixed_iteration_count)
    )
    if spatial_scheme not in (
        "upwind_finite_volume",
        "step_characteristics",
        "hybrid_step_turning_upwind",
    ):
        raise PhysicalDomainError(
            "spatial_scheme must be upwind_finite_volume, step_characteristics "
            "or hybrid_step_turning_upwind"
        )
    if not isinstance(source_map_only, (bool, np.bool_)):
        raise PhysicalDomainError("source_map_only must be boolean")
    if periodic_spatial_boundary and spatial_scheme in (
        "step_characteristics",
        "hybrid_step_turning_upwind",
    ):
        raise PhysicalDomainError(
            "step characteristics do not support periodic spatial boundaries"
        )

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
    collision_shape = (collision_groups, depth_points)
    outer_shape = (outer_groups, angle_points, depth_points)
    initial = _broadcast_nonnegative(
        "initial_active_lab_intensity_density",
        initial_active_lab_intensity_density,
        active_shape,
    )
    outer_template = _broadcast_nonnegative(
        "outer_lab_guard_intensity_density",
        outer_lab_guard_intensity_density,
        outer_shape,
    )
    true_absorption = _broadcast_nonnegative(
        "comoving_true_absorption_per_cm",
        comoving_true_absorption_per_cm,
        collision_shape,
    )
    thermal_emissivity = _broadcast_nonnegative(
        "comoving_thermal_emissivity_cgs",
        comoving_thermal_emissivity_cgs,
        collision_shape,
    )
    scattering = _broadcast_nonnegative(
        "comoving_scattering_per_cm",
        comoving_scattering_per_cm,
        collision_shape,
    )
    if np.any((true_absorption == 0.0) & (thermal_emissivity != 0.0)):
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
    left = _broadcast_nonnegative(
        "left_exterior_intensity",
        left_exterior_intensity,
        (active_groups, angle_points),
    )
    right = _broadcast_nonnegative(
        "right_exterior_intensity",
        right_exterior_intensity,
        (active_groups, angle_points),
    )
    if periodic_spatial_boundary and (np.any(left != 0.0) or np.any(right != 0.0)):
        raise PhysicalDomainError(
            "periodic spatial boundaries cannot specify exterior intensities"
        )
    mesh_velocity = (new_edge - old_edge) / duration
    if not np.all(np.isfinite(mesh_velocity)) or np.any(np.abs(mesh_velocity) >= speed):
        raise PhysicalDomainError("ALE mesh velocity must be finite and subluminal")

    transform = lorentz_ray_transform(mu, weight, beta)
    # 中文：分量关闭只用于误差定位，不代表一个协变的物理混合系模型。
    identity_doppler = np.ones_like(transform.doppler_lab_to_comoving)
    extinction_doppler = (
        transform.doppler_lab_to_comoving
        if bool(apply_extinction_lorentz)
        else identity_doppler
    )
    emissivity_doppler = (
        transform.doppler_lab_to_comoving
        if bool(apply_emissivity_lorentz)
        else identity_doppler
    )
    intensity_beta = beta if bool(apply_intensity_lorentz) else np.zeros_like(beta)
    extinction_comoving_angle = np.broadcast_to(
        (true_absorption + scattering)[:, None, :],
        (collision_groups, angle_points, depth_points),
    )
    lab_extinction = lorentz_remap_comoving_group_extinction_to_lab(
        extinction_comoving_angle,
        stencil.comoving_collision_edge_hz,
        stencil.active_lab_edge_hz,
        extinction_doppler,
    )
    active_slice = slice(
        stencil.active_outer_group_start, stencil.active_outer_group_stop
    )

    current = (
        np.array(initial, copy=True)
        if source_iteration_initial_guess is None
        else _broadcast_nonnegative(
            "source_iteration_initial_guess",
            source_iteration_initial_guess,
            active_shape,
        )
    )
    if iteration_observer is not None:
        iteration_observer(0, _readonly(current.view()))
    final_change = np.inf
    fixed_point_converged = False
    transport_faces: NDArray[np.float64] | None = None
    for iteration in range(1, iteration_limit + 1):
        outer = np.array(outer_template, copy=True)
        outer[active_slice] = current
        comoving = comoving_group_radiation(
            outer,
            stencil.outer_lab_edge_hz,
            stencil.comoving_collision_edge_hz,
            mu,
            weight,
            intensity_beta,
        )
        # 中文：热发射和共动系各向同性散射共享同一正性发射率入口。
        comoving_emissivity = (
            thermal_emissivity
            + scattering * comoving.mean_intensity_density
        )
        lab_emissivity = lorentz_remap_comoving_group_emissivity_to_lab(
            np.broadcast_to(
                comoving_emissivity[:, None, :],
                (collision_groups, angle_points, depth_points),
            ),
            stencil.comoving_collision_edge_hz,
            stencil.active_lab_edge_hz,
            emissivity_doppler,
        )
        if spatial_scheme == "upwind_finite_volume":
            updated = _solve_positive_ray_transport(
                initial,
                old_width,
                new_width,
                mu,
                mesh_velocity,
                lab_extinction,
                lab_emissivity,
                left,
                right,
                duration,
                speed,
                bool(periodic_spatial_boundary),
            )
            updated_faces = None
        else:
            updated, updated_faces = _solve_step_characteristics_ray_transport(
                initial,
                old_width,
                new_width,
                mu,
                mesh_velocity,
                lab_extinction,
                lab_emissivity,
                left,
                right,
                duration,
                speed,
                allow_turning_ray_upwind=(
                    spatial_scheme == "hybrid_step_turning_upwind"
                ),
            )
        scale = max(
            float(np.max(np.abs(updated))),
            float(np.max(np.abs(current))),
        )
        change = float(np.max(np.abs(updated - current)))
        final_change = change / scale if scale > 0.0 else change
        current = updated
        transport_faces = updated_faces
        if iteration_observer is not None:
            iteration_observer(iteration, _readonly(current.view()))
        if diagnostic_fixed_iteration_count is None and final_change <= tolerance:
            fixed_point_converged = True
            break
    else:
        if diagnostic_fixed_iteration_count is None:
            raise ArithmeticError(
                "mixed-frame ALE source iteration did not converge: "
                f"iterations={maximum_iterations}"
            )
        fixed_point_converged = final_change <= tolerance

    if bool(source_map_only):
        # 中文：强度更新已经完成；只省略随后不会反馈到该更新的重复科学诊断。
        return MixedFrameALESourceMap(
            final_lab_intensity_density=_readonly(current),
            fixed_point_iterations=iteration,
            final_fixed_point_change=final_change,
            minimum_intensity=float(np.min(current)),
            maximum_mesh_speed_to_light=float(
                np.max(np.abs(mesh_velocity)) / speed
            ),
            fixed_point_converged=fixed_point_converged,
        )

    outer = np.array(outer_template, copy=True)
    outer[active_slice] = current
    comoving = comoving_group_radiation(
        outer,
        stencil.outer_lab_edge_hz,
        stencil.comoving_collision_edge_hz,
        mu,
        weight,
        intensity_beta,
    )
    comoving_emissivity = thermal_emissivity + scattering * comoving.mean_intensity_density
    lab_emissivity = lorentz_remap_comoving_group_emissivity_to_lab(
        np.broadcast_to(
            comoving_emissivity[:, None, :],
            (collision_groups, angle_points, depth_points),
        ),
        stencil.comoving_collision_edge_hz,
        stencil.active_lab_edge_hz,
        emissivity_doppler,
    )
    _, relative_residual, global_relative_residual = _coupled_residual(
        current,
        initial,
        old_width,
        new_width,
        mu,
        mesh_velocity,
        lab_extinction,
        lab_emissivity,
        left,
        right,
        duration,
        speed,
        bool(periodic_spatial_boundary),
        transport_faces,
    )

    lab_mean = 0.5 * np.einsum("m,fmd->fd", weight, current)
    initial_mean = 0.5 * np.einsum("m,fmd->fd", weight, initial)
    if transport_faces is None:
        left_face, right_face = _boundary_faces(
            current,
            left,
            right,
            mu,
            mesh_velocity,
            speed,
            bool(periodic_spatial_boundary),
        )
    else:
        left_face = np.array(transport_faces[:, :, 0], copy=True)
        right_face = np.array(transport_faces[:, :, -1], copy=True)
    left_relative_speed = speed * mu - mesh_velocity[0]
    right_relative_speed = speed * mu - mesh_velocity[-1]
    left_flux = 2.0 * np.pi / speed * np.einsum(
        "m,fm,m->f", weight, left_face, left_relative_speed
    )
    right_flux = 2.0 * np.pi / speed * np.einsum(
        "m,fm,m->f", weight, right_face, right_relative_speed
    )
    initial_energy = 4.0 * np.pi / speed * np.sum(
        initial_mean * old_width[None, :], axis=1
    )
    final_energy = 4.0 * np.pi / speed * np.sum(
        lab_mean * new_width[None, :], axis=1
    )
    lab_collision = lab_emissivity - lab_extinction * current
    material_heating = -2.0 * np.pi * np.sum(
        weight[None, :, None] * lab_collision * new_width[None, None, :],
        axis=(1, 2),
    )
    ledger = (
        final_energy
        - initial_energy
        + duration * (right_flux - left_flux + material_heating)
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

    active_width = np.diff(stencil.active_lab_edge_hz)
    total_ledger = float(np.sum(active_width * ledger))
    total_ledger_scale = max(
        float(np.sum(active_width * np.abs(initial_energy))),
        float(np.sum(active_width * np.abs(final_energy))),
        float(duration * np.sum(active_width * np.abs(right_flux - left_flux))),
        float(duration * np.sum(active_width * np.abs(material_heating))),
    )
    total_relative_ledger = (
        abs(total_ledger) / total_ledger_scale
        if total_ledger_scale > 0.0
        else abs(total_ledger)
    )

    collision_width = np.diff(stencil.comoving_collision_edge_hz)
    comoving_collision = (
        comoving_emissivity[:, None, :]
        - extinction_comoving_angle * comoving.angle_intensity_density
    )
    lab_source_energy = 2.0 * np.pi * np.einsum(
        "f,m,fmd->d", active_width, weight, lab_collision
    )
    lab_source_momentum = 2.0 * np.pi / speed * np.einsum(
        "f,m,m,fmd->d", active_width, weight, mu, lab_collision
    )
    comoving_source_energy = 2.0 * np.pi * np.einsum(
        "f,md,fmd->d",
        collision_width,
        transform.comoving_angular_weight,
        comoving_collision,
    )
    comoving_source_momentum = 2.0 * np.pi / speed * np.einsum(
        "f,md,md,fmd->d",
        collision_width,
        transform.comoving_angular_weight,
        transform.comoving_direction_cosine,
        comoving_collision,
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

    arrays = (
        current,
        lab_mean,
        comoving.angle_intensity_density,
        comoving.mean_intensity_density,
        lab_extinction,
        lab_emissivity,
        mesh_velocity,
        left_face,
        right_face,
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
        raise ArithmeticError("mixed-frame ALE diagnostics became non-finite")
    return MixedFrameALEStep(
        final_lab_intensity_density=_readonly(current),
        final_lab_mean_intensity_density=_readonly(lab_mean),
        final_comoving_angle_intensity_density=comoving.angle_intensity_density,
        final_comoving_mean_intensity_density=comoving.mean_intensity_density,
        lab_extinction_per_cm=lab_extinction,
        lab_emissivity_cgs=lab_emissivity,
        mesh_edge_velocity_cm_s=_readonly(mesh_velocity),
        material_velocity_beta=_readonly(np.array(beta, copy=True)),
        left_ale_face_intensity=_readonly(left_face),
        right_ale_face_intensity=_readonly(right_face),
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
        fixed_point_iterations=iteration,
        final_fixed_point_change=final_change,
        total_relative_energy_ledger_residual=total_relative_ledger,
        global_scale_normalized_coupled_residual=global_relative_residual,
        maximum_group_relative_coupled_residual=float(np.max(relative_residual)),
        minimum_intensity=float(np.min(current)),
        maximum_mesh_speed_to_light=float(np.max(np.abs(mesh_velocity)) / speed),
        fixed_point_converged=fixed_point_converged,
    )
