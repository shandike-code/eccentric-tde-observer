"""混合参考系源迭代的局域对角 ALI 预条件器。

这里不替换正式 Lorentz--ALE 辐射算子，只近似求逆其最刚性的局域散射
反馈。空间 Lambda 对角元来自正式 step-characteristics 单元平均强度对
局域实验室系发射率的解析导数；频率搬移和非局域空间传播仍留给原算子。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.sparse.linalg import LinearOperator, gmres

from .mixed_frame_ale import _solve_step_characteristics_ray_transport
from .mixed_frame_frequency import (
    lorentz_ray_transform,
    lorentz_remap_signed_comoving_group_emissivity_perturbation_to_lab,
    lorentz_remap_signed_group_intensity_perturbation,
)
from .radiation import LIGHT_SPEED_CM_S
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class StepCharacteristicLambdaDiagonal:
    """局域发射率到单元平均实验室系强度的近似 Lambda 对角元。"""

    response_cm: NDArray[np.float64]
    turning_angle_count: int
    turning_ray_uses_raw_upwind_diagonal: bool
    minimum_response_cm: float
    maximum_response_cm: float


@dataclass(frozen=True)
class StaticDiagonalALICorrection:
    """静态同频散射近似下的局域 ALI 残差修正。"""

    correction: NDArray[np.float64]
    residual_mean_intensity: NDArray[np.float64]
    corrected_mean_intensity: NDArray[np.float64]
    lambda_mean_diagonal_cm: NDArray[np.float64]
    scattering_feedback_fraction: NDArray[np.float64]
    scattering_denominator: NDArray[np.float64]
    turning_angle_count: int
    turning_ray_uses_raw_upwind_diagonal: bool
    minimum_scattering_denominator: float
    maximum_scattering_feedback_fraction: float


@dataclass(frozen=True)
class DopplerCoupledLocalALICorrection:
    """含完整局域 Doppler 频率串扰的 ALI 残差修正。"""

    correction: NDArray[np.float64]
    final_comoving_mean_correction: NDArray[np.float64]
    iteration_count: int
    final_relative_linear_residual: float
    maximum_iteration_contraction: float
    minimum_iteration_contraction: float
    fixed_point_converged: bool


@dataclass(frozen=True)
class StaticFrequencySpatialALICorrection:
    """静态同频、全深度短特征 Lambda 近似逆给出的 ALI 修正。"""

    correction: NDArray[np.float64]
    corrected_mean_intensity: NDArray[np.float64]
    gmres_iteration_count: int
    gmres_reported_info: int
    final_scaled_linf_linear_residual: float
    final_mean_consistency_linf: float
    minimum_local_preconditioner_denominator: float
    maximum_local_preconditioner_feedback: float
    fixed_point_converged: bool


@dataclass(frozen=True)
class MixedFrameSpatialSourceCorrection:
    """完整局域频率搬移与全深度传播下的固定物质源修正。"""

    correction: NDArray[np.float64]
    corrected_comoving_mean_intensity: NDArray[np.float64]
    gmres_iteration_count: int
    gmres_reported_info: int
    final_scaled_linf_linear_residual: float
    final_comoving_mean_consistency_linf: float
    fixed_point_converged: bool


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


def _validated_angular_quadrature(
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
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
    return mu, weight


def _broadcast_nonnegative(
    name: str,
    values: ArrayLike,
    shape: tuple[int, ...],
) -> NDArray[np.float64]:
    try:
        result = np.array(
            np.broadcast_to(np.asarray(values, dtype=np.float64), shape), copy=True
        )
    except ValueError as error:
        raise PhysicalDomainError(f"{name} cannot broadcast to {shape}") from error
    if not np.all(np.isfinite(result)) or np.any(result < 0.0):
        raise PhysicalDomainError(f"{name} must be finite and non-negative")
    return result


def step_characteristic_local_lambda_diagonal(
    old_depth_edges_cm: ArrayLike,
    new_depth_edges_cm: ArrayLike,
    direction_cosine: ArrayLike,
    lab_extinction_per_cm: ArrayLike,
    duration_s: float,
    *,
    propagation_speed_cm_s: float = LIGHT_SPEED_CM_S,
    allow_turning_ray_upwind: bool = False,
) -> StepCharacteristicLambdaDiagonal:
    """返回单元平均强度对局域实验室系发射率的解析响应。

    对不变号特征线，该响应与正式单元常源特征积分逐项相同，只把入射面
    强度保持不变。柱内变号的掠射方向若被允许，则使用正式迎风矩阵未经
    消元的正对角作为局域近似；非局域三对角耦合仍由正式算子恢复。
    """
    old_edge = _positive_edges("old_depth_edges_cm", old_depth_edges_cm)
    new_edge = _positive_edges("new_depth_edges_cm", new_depth_edges_cm)
    if old_edge.shape != new_edge.shape:
        raise PhysicalDomainError("old and new depth grids must share their size")
    mu = np.asarray(direction_cosine, dtype=np.float64)
    if (
        mu.ndim != 1
        or mu.size < 2
        or not np.all(np.isfinite(mu))
        or np.any(mu <= -1.0)
        or np.any(mu >= 1.0)
    ):
        raise PhysicalDomainError("direction_cosine must be finite on (-1,1)")
    duration = float(duration_s)
    speed_of_light = float(propagation_speed_cm_s)
    if not np.isfinite(duration) or duration <= 0.0:
        raise PhysicalDomainError("duration_s must be finite and positive")
    if not np.isfinite(speed_of_light) or speed_of_light <= 0.0:
        raise PhysicalDomainError(
            "propagation_speed_cm_s must be finite and positive"
        )
    old_width = np.diff(old_edge)
    new_width = np.diff(new_edge)
    depth_points = new_width.size
    extinction = np.asarray(lab_extinction_per_cm, dtype=np.float64)
    if extinction.ndim != 3 or extinction.shape[1:] != (mu.size, depth_points):
        raise PhysicalDomainError(
            "lab_extinction_per_cm must have shape (frequency, angle, depth)"
        )
    if not np.all(np.isfinite(extinction)) or np.any(extinction < 0.0):
        raise PhysicalDomainError(
            "lab_extinction_per_cm must be finite and non-negative"
        )
    mesh_velocity = (new_edge - old_edge) / duration
    if (
        not np.all(np.isfinite(mesh_velocity))
        or np.any(np.abs(mesh_velocity) >= speed_of_light)
    ):
        raise PhysicalDomainError("ALE mesh velocity must be finite and subluminal")

    frequency_points = extinction.shape[0]
    response = np.empty_like(extinction)
    relative_speed = speed_of_light * mu[:, None] - mesh_velocity[None, :]
    turning_count = 0
    for angle in range(mu.size):
        ray_speed = relative_speed[angle]
        if np.all(ray_speed > 0.0):
            order = range(depth_points)
        elif np.all(ray_speed < 0.0):
            order = range(depth_points - 1, -1, -1)
        else:
            if not allow_turning_ray_upwind:
                raise PhysicalDomainError(
                    "a step-characteristic reversed direction inside the column"
                )
            turning_count += 1
            # 中文：掠射线只取正式迎风 M 矩阵的原始正对角，不伪装成精确逆。
            diagonal = (
                new_width[None, :] / duration
                + speed_of_light * new_width[None, :] * extinction[:, angle, :]
                + np.maximum(ray_speed[1:], 0.0)[None, :]
                - np.minimum(ray_speed[:-1], 0.0)[None, :]
            )
            if not np.all(np.isfinite(diagonal)) or np.any(diagonal <= 0.0):
                raise ArithmeticError("turning-ray ALI diagonal lost positivity")
            response[:, angle, :] = speed_of_light * new_width[None, :] / diagonal
            continue
        for depth in order:
            left_speed = float(ray_speed[depth])
            right_speed = float(ray_speed[depth + 1])
            speed_slope = right_speed - left_speed
            incoming_speed = left_speed if left_speed > 0.0 else right_speed
            outgoing_speed = right_speed if left_speed > 0.0 else left_speed
            coefficient = (
                new_width[depth] / duration
                + speed_of_light
                * new_width[depth]
                * extinction[:, angle, depth]
            )
            equilibrium_denominator = coefficient + speed_slope
            if (
                not np.all(np.isfinite(coefficient))
                or np.any(coefficient <= 0.0)
                or np.any(equilibrium_denominator <= 0.0)
            ):
                raise ArithmeticError("step-characteristic ALI coefficients lost positivity")
            speed_scale = max(abs(incoming_speed), abs(outgoing_speed))
            if abs(speed_slope) <= 64.0 * np.finfo(np.float64).eps * speed_scale:
                optical_distance = coefficient / abs(incoming_speed)
                average_factor = -np.expm1(-optical_distance) / optical_distance
            else:
                log_speed_ratio = np.log(abs(outgoing_speed) / abs(incoming_speed))
                average_exponent = -(
                    coefficient / speed_slope
                ) * log_speed_ratio
                average_factor = (
                    abs(incoming_speed)
                    / coefficient
                    * -np.expm1(average_exponent)
                )
            local_fraction = 1.0 - average_factor
            local_response = (
                speed_of_light
                * new_width[depth]
                / equilibrium_denominator
                * local_fraction
            )
            if (
                not np.all(np.isfinite(local_response))
                or np.any(local_response < 0.0)
            ):
                raise ArithmeticError(
                    "step-characteristic ALI response left its positive domain"
                )
            response[:, angle, depth] = local_response
    if response.shape != (frequency_points, mu.size, depth_points):
        raise ArithmeticError("step-characteristic ALI response shape changed")
    if not np.all(np.isfinite(response)) or np.any(response < 0.0):
        raise ArithmeticError("step-characteristic ALI response became invalid")
    return StepCharacteristicLambdaDiagonal(
        response_cm=_readonly(response),
        turning_angle_count=turning_count,
        turning_ray_uses_raw_upwind_diagonal=turning_count > 0,
        minimum_response_cm=float(np.min(response)),
        maximum_response_cm=float(np.max(response)),
    )


def static_diagonal_ali_residual_correction(
    residual_lab_intensity_density: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    local_lambda_response_cm: ArrayLike,
    static_lab_scattering_per_cm: ArrayLike,
    *,
    turning_angle_count: int = 0,
    turning_ray_uses_raw_upwind_diagonal: bool = False,
) -> StaticDiagonalALICorrection:
    """近似求解局域散射方程 ``delta I = r + Lambda sigma delta J``。

    该预条件只把同一实验室频率、同一深度的各向同性散射秩一耦合隐式化。
    Doppler 频率串扰和空间非局域传播不在近似逆中，候选必须重新交给原始
    混合参考系算子验证。
    """
    mu, weight = _validated_angular_quadrature(direction_cosine, angular_weight)
    residual = np.asarray(residual_lab_intensity_density, dtype=np.float64)
    if (
        residual.ndim != 3
        or residual.shape[1] != mu.size
        or not np.all(np.isfinite(residual))
    ):
        raise PhysicalDomainError(
            "residual_lab_intensity_density must be finite with shape "
            "(frequency, angle, depth)"
        )
    response = _broadcast_nonnegative(
        "local_lambda_response_cm", local_lambda_response_cm, residual.shape
    )
    scattering = _broadcast_nonnegative(
        "static_lab_scattering_per_cm", static_lab_scattering_per_cm, residual.shape
    )
    if (
        not isinstance(turning_angle_count, (int, np.integer))
        or isinstance(turning_angle_count, (bool, np.bool_))
        or int(turning_angle_count) < 0
        or int(turning_angle_count) > mu.size
    ):
        raise PhysicalDomainError("turning_angle_count must be a valid integer count")
    if not isinstance(
        turning_ray_uses_raw_upwind_diagonal, (bool, np.bool_)
    ):
        raise PhysicalDomainError(
            "turning_ray_uses_raw_upwind_diagonal must be boolean"
        )
    local_feedback = response * scattering
    feedback = 0.5 * np.einsum("m,fmd->fd", weight, local_feedback)
    denominator = 1.0 - feedback
    if not np.all(np.isfinite(denominator)) or np.any(denominator <= 0.0):
        raise ArithmeticError("local ALI scattering denominator is not positive")
    residual_mean = 0.5 * np.einsum("m,fmd->fd", weight, residual)
    corrected_mean = residual_mean / denominator
    correction = residual + local_feedback * corrected_mean[:, None, :]
    if not np.all(np.isfinite(correction)):
        raise ArithmeticError("local ALI correction became non-finite")
    lambda_mean = 0.5 * np.einsum("m,fmd->fd", weight, response)
    return StaticDiagonalALICorrection(
        correction=_readonly(correction),
        residual_mean_intensity=_readonly(residual_mean),
        corrected_mean_intensity=_readonly(corrected_mean),
        lambda_mean_diagonal_cm=_readonly(lambda_mean),
        scattering_feedback_fraction=_readonly(feedback),
        scattering_denominator=_readonly(denominator),
        turning_angle_count=int(turning_angle_count),
        turning_ray_uses_raw_upwind_diagonal=bool(
            turning_ray_uses_raw_upwind_diagonal
        ),
        minimum_scattering_denominator=float(np.min(denominator)),
        maximum_scattering_feedback_fraction=float(np.max(feedback)),
    )


def doppler_coupled_local_ali_residual_correction(
    residual_lab_intensity_density: ArrayLike,
    outer_lab_edge_hz: ArrayLike,
    comoving_collision_edge_hz: ArrayLike,
    active_lab_edge_hz: ArrayLike,
    active_outer_group_start: int,
    active_outer_group_stop: int,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    material_velocity_beta: ArrayLike,
    local_lambda_response_cm: ArrayLike,
    comoving_scattering_per_cm: ArrayLike,
    *,
    iterative_tolerance: float = 1.0e-10,
    iterative_maximum_iterations: int = 64,
) -> DopplerCoupledLocalALICorrection:
    """迭代求逆局域 ``Lambda*`` 与完整 Lorentz 频率散射耦合。

    空间传播只保留已经解析得到的局域 ``Lambda*``；实验室系扰动到共动
    ``delta J_0``、共动散射发射率再回实验室系的两次频率搬移则完全保留。
    这是预条件器的线性方程，最终候选仍需正式混合系原算子复核。
    """
    mu, weight = _validated_angular_quadrature(direction_cosine, angular_weight)
    residual = np.asarray(residual_lab_intensity_density, dtype=np.float64)
    if (
        residual.ndim != 3
        or residual.shape[1] != mu.size
        or not np.all(np.isfinite(residual))
    ):
        raise PhysicalDomainError(
            "residual_lab_intensity_density must be finite with shape "
            "(frequency, angle, depth)"
        )
    active_edge = _positive_edges("active_lab_edge_hz", active_lab_edge_hz)
    outer_edge = _positive_edges("outer_lab_edge_hz", outer_lab_edge_hz)
    collision_edge = _positive_edges(
        "comoving_collision_edge_hz", comoving_collision_edge_hz
    )
    frequency_points, angle_points, depth_points = residual.shape
    if active_edge.size != frequency_points + 1:
        raise PhysicalDomainError(
            "active_lab_edge_hz must match the residual frequency axis"
        )
    if (
        not isinstance(active_outer_group_start, (int, np.integer))
        or isinstance(active_outer_group_start, (bool, np.bool_))
        or not isinstance(active_outer_group_stop, (int, np.integer))
        or isinstance(active_outer_group_stop, (bool, np.bool_))
    ):
        raise PhysicalDomainError("active outer group bounds must be integers")
    active_start = int(active_outer_group_start)
    active_stop = int(active_outer_group_stop)
    if (
        active_start < 0
        or active_stop <= active_start
        or active_stop > outer_edge.size - 1
        or active_stop - active_start != frequency_points
        or not np.array_equal(outer_edge[active_start : active_stop + 1], active_edge)
    ):
        raise PhysicalDomainError(
            "active outer group slice must exactly embed the active frequency edges"
        )
    beta = np.asarray(material_velocity_beta, dtype=np.float64)
    if (
        beta.shape != (depth_points,)
        or not np.all(np.isfinite(beta))
        or np.any(np.abs(beta) >= 1.0)
    ):
        raise PhysicalDomainError(
            "material_velocity_beta must match depth and remain subluminal"
        )
    response = _broadcast_nonnegative(
        "local_lambda_response_cm", local_lambda_response_cm, residual.shape
    )
    scattering = _broadcast_nonnegative(
        "comoving_scattering_per_cm",
        comoving_scattering_per_cm,
        (collision_edge.size - 1, depth_points),
    )
    tolerance = float(iterative_tolerance)
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
    transform = lorentz_ray_transform(mu, weight, beta)
    outer = np.zeros(
        (outer_edge.size - 1, angle_points, depth_points), dtype=np.float64
    )

    def local_map(
        current: NDArray[np.float64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        outer[active_start:active_stop] = current
        comoving_angle = lorentz_remap_signed_group_intensity_perturbation(
            outer,
            outer_edge,
            collision_edge,
            transform.doppler_lab_to_comoving,
            direction="lab_to_comoving",
        )
        comoving_mean = 0.5 * np.sum(
            transform.comoving_angular_weight[None, ...] * comoving_angle,
            axis=1,
        )
        comoving_emissivity = scattering * comoving_mean
        lab_emissivity = (
            lorentz_remap_signed_comoving_group_emissivity_perturbation_to_lab(
                np.broadcast_to(
                    comoving_emissivity[:, None, :],
                    (collision_edge.size - 1, angle_points, depth_points),
                ),
                collision_edge,
                active_edge,
                transform.doppler_lab_to_comoving,
            )
        )
        updated = residual + response * lab_emissivity
        if (
            not np.all(np.isfinite(comoving_mean))
            or not np.all(np.isfinite(updated))
        ):
            raise ArithmeticError("Doppler-coupled local ALI map became non-finite")
        return updated, comoving_mean

    current = np.array(residual, copy=True)
    changes: list[float] = []
    final_comoving_mean: NDArray[np.float64] | None = None
    for iteration in range(1, maximum_iterations + 1):
        updated, final_comoving_mean = local_map(current)
        scale = max(
            float(np.max(np.abs(updated))), float(np.max(np.abs(current)))
        )
        change = float(np.max(np.abs(updated - current)))
        relative_change = change / scale if scale > 0.0 else change
        changes.append(relative_change)
        current = updated
        if relative_change <= tolerance:
            break
    else:
        raise ArithmeticError(
            "Doppler-coupled local ALI iteration did not converge: "
            f"iterations={maximum_iterations}"
        )
    audited, audited_comoving_mean = local_map(current)
    audit_scale = max(
        float(np.max(np.abs(audited))), float(np.max(np.abs(current)))
    )
    audit_change = float(np.max(np.abs(audited - current)))
    relative_residual = audit_change / audit_scale if audit_scale > 0.0 else audit_change
    if relative_residual > tolerance:
        raise ArithmeticError(
            "Doppler-coupled local ALI audit did not meet its declared tolerance"
        )
    contractions = [
        current_change / previous_change
        for previous_change, current_change in zip(changes[:-1], changes[1:])
        if previous_change > 0.0
    ]
    return DopplerCoupledLocalALICorrection(
        correction=_readonly(current),
        final_comoving_mean_correction=_readonly(audited_comoving_mean),
        iteration_count=iteration,
        final_relative_linear_residual=relative_residual,
        maximum_iteration_contraction=(
            float(max(contractions)) if contractions else 0.0
        ),
        minimum_iteration_contraction=(
            float(min(contractions)) if contractions else 0.0
        ),
        fixed_point_converged=True,
    )


def static_frequency_spatial_ali_residual_correction(
    residual_lab_intensity_density: ArrayLike,
    old_depth_edges_cm: ArrayLike,
    new_depth_edges_cm: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    lab_extinction_per_cm: ArrayLike,
    static_lab_scattering_per_cm: ArrayLike,
    duration_s: float,
    *,
    propagation_speed_cm_s: float = LIGHT_SPEED_CM_S,
    gmres_relative_tolerance: float = 1.0e-6,
    gmres_restart: int = 12,
    gmres_maximum_restart_cycles: int = 4,
    allow_turning_ray_upwind: bool = False,
) -> StaticFrequencySpatialALICorrection:
    """矩阵自由求逆静态同频但空间非局域的散射修正方程。

    未知量降为逐频率、逐深度的 ``delta J``。每个 Krylov 矩阵向量积都
    调用正式 step-characteristics 的完整深度响应；局域 Lambda 对角元只
    用作左预条件，不替代原空间算子。频率间 Doppler 串扰仍留给外层正式
    混合参考系算子验证。
    """
    mu, weight = _validated_angular_quadrature(direction_cosine, angular_weight)
    residual = np.asarray(residual_lab_intensity_density, dtype=np.float64)
    if (
        residual.ndim != 3
        or residual.shape[1] != mu.size
        or not np.all(np.isfinite(residual))
    ):
        raise PhysicalDomainError(
            "residual_lab_intensity_density must be finite with shape "
            "(frequency, angle, depth)"
        )
    old_edge = _positive_edges("old_depth_edges_cm", old_depth_edges_cm)
    new_edge = _positive_edges("new_depth_edges_cm", new_depth_edges_cm)
    if old_edge.shape != new_edge.shape or old_edge.size != residual.shape[2] + 1:
        raise PhysicalDomainError(
            "old and new depth edges must match the residual depth axis"
        )
    duration = float(duration_s)
    speed = float(propagation_speed_cm_s)
    if not np.isfinite(duration) or duration <= 0.0:
        raise PhysicalDomainError("duration_s must be finite and positive")
    if not np.isfinite(speed) or speed <= 0.0:
        raise PhysicalDomainError(
            "propagation_speed_cm_s must be finite and positive"
        )
    extinction = _broadcast_nonnegative(
        "lab_extinction_per_cm", lab_extinction_per_cm, residual.shape
    )
    scattering = _broadcast_nonnegative(
        "static_lab_scattering_per_cm",
        static_lab_scattering_per_cm,
        residual.shape,
    )
    tolerance = float(gmres_relative_tolerance)
    if not np.isfinite(tolerance) or tolerance <= 0.0 or tolerance >= 1.0:
        raise PhysicalDomainError(
            "gmres_relative_tolerance must lie strictly between zero and one"
        )
    for name, value in (
        ("gmres_restart", gmres_restart),
        ("gmres_maximum_restart_cycles", gmres_maximum_restart_cycles),
    ):
        if (
            not isinstance(value, (int, np.integer))
            or isinstance(value, (bool, np.bool_))
            or int(value) < 1
        ):
            raise PhysicalDomainError(f"{name} must be a positive integer")
    restart = int(gmres_restart)
    maximum_cycles = int(gmres_maximum_restart_cycles)
    if not isinstance(allow_turning_ray_upwind, (bool, np.bool_)):
        raise PhysicalDomainError("allow_turning_ray_upwind must be boolean")

    frequency_points, angle_points, depth_points = residual.shape
    old_width = np.diff(old_edge)
    new_width = np.diff(new_edge)
    mesh_velocity = (new_edge - old_edge) / duration
    zero_initial = np.zeros_like(residual)
    zero_left = np.zeros((frequency_points, angle_points), dtype=np.float64)
    zero_right = np.zeros_like(zero_left)

    def transport_response(
        emissivity: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        intensity, _ = _solve_step_characteristics_ray_transport(
            zero_initial,
            old_width,
            new_width,
            mu,
            mesh_velocity,
            extinction,
            emissivity,
            zero_left,
            zero_right,
            duration,
            speed,
            allow_turning_ray_upwind=bool(allow_turning_ray_upwind),
            allow_signed_fields=True,
        )
        return intensity

    residual_mean = 0.5 * np.einsum("m,fmd->fd", weight, residual)
    frequency_scale = np.max(np.abs(residual_mean), axis=1)
    inactive = frequency_scale == 0.0
    frequency_scale[inactive] = 1.0
    scaled_rhs = residual_mean / frequency_scale[:, None]

    def apply_mean_operator(mean_value: NDArray[np.float64]) -> NDArray[np.float64]:
        emissivity = scattering * mean_value[:, None, :]
        response = transport_response(emissivity)
        response_mean = 0.5 * np.einsum("m,fmd->fd", weight, response)
        result = mean_value - response_mean
        if not np.all(np.isfinite(result)):
            raise ArithmeticError("static spatial ALI operator became non-finite")
        return result

    size = frequency_points * depth_points
    operator = LinearOperator(
        (size, size),
        matvec=lambda vector: apply_mean_operator(
            np.asarray(vector).reshape(frequency_points, depth_points)
        ).reshape(-1),
        dtype=np.float64,
    )
    local = step_characteristic_local_lambda_diagonal(
        old_edge,
        new_edge,
        mu,
        extinction,
        duration,
        propagation_speed_cm_s=speed,
        allow_turning_ray_upwind=bool(allow_turning_ray_upwind),
    )
    feedback = 0.5 * np.einsum(
        "m,fmd->fd", weight, local.response_cm * scattering
    )
    denominator = 1.0 - feedback
    if not np.all(np.isfinite(denominator)) or np.any(denominator <= 0.0):
        raise ArithmeticError(
            "static spatial ALI local preconditioner denominator is not positive"
        )
    preconditioner = LinearOperator(
        (size, size),
        matvec=lambda vector: (
            np.asarray(vector).reshape(frequency_points, depth_points) / denominator
        ).reshape(-1),
        dtype=np.float64,
    )
    callback_residuals: list[float] = []
    scaled_solution, info = gmres(
        operator,
        scaled_rhs.reshape(-1),
        M=preconditioner,
        rtol=tolerance,
        atol=0.0,
        restart=restart,
        maxiter=maximum_cycles,
        callback=lambda value: callback_residuals.append(float(value)),
        callback_type="pr_norm",
    )
    corrected_mean = scaled_solution.reshape(
        frequency_points, depth_points
    ) * frequency_scale[:, None]
    corrected_mean[inactive] = 0.0
    correction = residual + transport_response(
        scattering * corrected_mean[:, None, :]
    )
    scaled_audit = apply_mean_operator(
        corrected_mean / frequency_scale[:, None]
    ) - scaled_rhs
    final_scaled_linf = float(np.max(np.abs(scaled_audit)))
    correction_mean = 0.5 * np.einsum("m,fmd->fd", weight, correction)
    mean_scale = max(
        float(np.max(np.abs(correction_mean))),
        float(np.max(np.abs(corrected_mean))),
    )
    mean_difference = float(np.max(np.abs(correction_mean - corrected_mean)))
    mean_consistency = mean_difference / mean_scale if mean_scale > 0.0 else mean_difference
    if (
        int(info) != 0
        or not np.all(np.isfinite(correction))
        or final_scaled_linf > 10.0 * tolerance
        or mean_consistency > 10.0 * tolerance
    ):
        raise ArithmeticError(
            "static spatial ALI GMRES did not satisfy its declared linear audit: "
            f"info={int(info)}, scaled_linf={final_scaled_linf:.6e}, "
            f"mean_consistency={mean_consistency:.6e}"
        )
    return StaticFrequencySpatialALICorrection(
        correction=_readonly(correction),
        corrected_mean_intensity=_readonly(corrected_mean),
        gmres_iteration_count=len(callback_residuals),
        gmres_reported_info=int(info),
        final_scaled_linf_linear_residual=final_scaled_linf,
        final_mean_consistency_linf=mean_consistency,
        minimum_local_preconditioner_denominator=float(np.min(denominator)),
        maximum_local_preconditioner_feedback=float(np.max(feedback)),
        fixed_point_converged=True,
    )


def mixed_frame_spatial_source_residual_correction(
    residual_lab_intensity_density: ArrayLike,
    old_depth_edges_cm: ArrayLike,
    new_depth_edges_cm: ArrayLike,
    outer_lab_edge_hz: ArrayLike,
    comoving_collision_edge_hz: ArrayLike,
    active_lab_edge_hz: ArrayLike,
    active_outer_group_start: int,
    active_outer_group_stop: int,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    material_velocity_beta: ArrayLike,
    lab_extinction_per_cm: ArrayLike,
    comoving_scattering_per_cm: ArrayLike,
    duration_s: float,
    *,
    propagation_speed_cm_s: float = LIGHT_SPEED_CM_S,
    gmres_relative_tolerance: float = 1.0e-5,
    gmres_restart: int = 12,
    gmres_maximum_restart_cycles: int = 3,
    allow_turning_ray_upwind: bool = False,
    allow_incomplete_krylov: bool = False,
) -> MixedFrameSpatialSourceCorrection:
    """求解固定物质时完整混合参考系源映射的线性残差方程。

    未知量是共动碰撞网格上的 ``delta J_0``。每个矩阵向量积依次执行
    共动散射发射、发射率 Lorentz 搬移、全深度短特征传播、强度 Lorentz
    回搬和共动角平均，因此没有丢弃 Doppler 频率串扰或空间非局域耦合。
    ``allow_incomplete_krylov`` 只允许诊断固定工作量候选；正式接受仍必须
    检查返回的 ``fixed_point_converged`` 并交回原始正性算子验证。
    """
    mu, weight = _validated_angular_quadrature(direction_cosine, angular_weight)
    residual = np.asarray(residual_lab_intensity_density, dtype=np.float64)
    if (
        residual.ndim != 3
        or residual.shape[1] != mu.size
        or not np.all(np.isfinite(residual))
    ):
        raise PhysicalDomainError(
            "residual_lab_intensity_density must be finite with shape "
            "(frequency, angle, depth)"
        )
    old_edge = _positive_edges("old_depth_edges_cm", old_depth_edges_cm)
    new_edge = _positive_edges("new_depth_edges_cm", new_depth_edges_cm)
    if old_edge.shape != new_edge.shape or old_edge.size != residual.shape[2] + 1:
        raise PhysicalDomainError(
            "old and new depth edges must match the residual depth axis"
        )
    outer_edge = _positive_edges("outer_lab_edge_hz", outer_lab_edge_hz)
    collision_edge = _positive_edges(
        "comoving_collision_edge_hz", comoving_collision_edge_hz
    )
    active_edge = _positive_edges("active_lab_edge_hz", active_lab_edge_hz)
    frequency_points, angle_points, depth_points = residual.shape
    if active_edge.size != frequency_points + 1:
        raise PhysicalDomainError(
            "active_lab_edge_hz must match the residual frequency axis"
        )
    if (
        not isinstance(active_outer_group_start, (int, np.integer))
        or isinstance(active_outer_group_start, (bool, np.bool_))
        or not isinstance(active_outer_group_stop, (int, np.integer))
        or isinstance(active_outer_group_stop, (bool, np.bool_))
    ):
        raise PhysicalDomainError("active outer group bounds must be integers")
    active_start = int(active_outer_group_start)
    active_stop = int(active_outer_group_stop)
    if (
        active_start < 0
        or active_stop <= active_start
        or active_stop > outer_edge.size - 1
        or active_stop - active_start != frequency_points
        or not np.array_equal(outer_edge[active_start : active_stop + 1], active_edge)
    ):
        raise PhysicalDomainError(
            "active outer group slice must exactly embed the active frequency edges"
        )
    beta = np.asarray(material_velocity_beta, dtype=np.float64)
    if (
        beta.shape != (depth_points,)
        or not np.all(np.isfinite(beta))
        or np.any(np.abs(beta) >= 1.0)
    ):
        raise PhysicalDomainError(
            "material_velocity_beta must match depth and remain subluminal"
        )
    extinction = _broadcast_nonnegative(
        "lab_extinction_per_cm", lab_extinction_per_cm, residual.shape
    )
    collision_groups = collision_edge.size - 1
    scattering = _broadcast_nonnegative(
        "comoving_scattering_per_cm",
        comoving_scattering_per_cm,
        (collision_groups, depth_points),
    )
    duration = float(duration_s)
    speed = float(propagation_speed_cm_s)
    tolerance = float(gmres_relative_tolerance)
    if not np.isfinite(duration) or duration <= 0.0:
        raise PhysicalDomainError("duration_s must be finite and positive")
    if not np.isfinite(speed) or speed <= 0.0:
        raise PhysicalDomainError(
            "propagation_speed_cm_s must be finite and positive"
        )
    if not np.isfinite(tolerance) or tolerance <= 0.0 or tolerance >= 1.0:
        raise PhysicalDomainError(
            "gmres_relative_tolerance must lie strictly between zero and one"
        )
    for name, value in (
        ("gmres_restart", gmres_restart),
        ("gmres_maximum_restart_cycles", gmres_maximum_restart_cycles),
    ):
        if (
            not isinstance(value, (int, np.integer))
            or isinstance(value, (bool, np.bool_))
            or int(value) < 1
        ):
            raise PhysicalDomainError(f"{name} must be a positive integer")
    if not isinstance(allow_turning_ray_upwind, (bool, np.bool_)):
        raise PhysicalDomainError("allow_turning_ray_upwind must be boolean")
    if not isinstance(allow_incomplete_krylov, (bool, np.bool_)):
        raise PhysicalDomainError("allow_incomplete_krylov must be boolean")
    restart = int(gmres_restart)
    maximum_cycles = int(gmres_maximum_restart_cycles)
    transform = lorentz_ray_transform(mu, weight, beta)
    old_width = np.diff(old_edge)
    new_width = np.diff(new_edge)
    mesh_velocity = (new_edge - old_edge) / duration
    zero_initial = np.zeros_like(residual)
    zero_left = np.zeros((frequency_points, angle_points), dtype=np.float64)
    zero_right = np.zeros_like(zero_left)
    outer = np.zeros(
        (outer_edge.size - 1, angle_points, depth_points), dtype=np.float64
    )

    def comoving_mean_from_active(
        active_intensity: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        outer.fill(0.0)
        outer[active_start:active_stop] = active_intensity
        comoving_angle = lorentz_remap_signed_group_intensity_perturbation(
            outer,
            outer_edge,
            collision_edge,
            transform.doppler_lab_to_comoving,
            direction="lab_to_comoving",
        )
        mean = 0.5 * np.sum(
            transform.comoving_angular_weight[None, ...] * comoving_angle,
            axis=1,
        )
        if not np.all(np.isfinite(mean)):
            raise ArithmeticError("mixed-frame ALI comoving mean became non-finite")
        return mean

    def active_response_from_comoving_mean(
        comoving_mean: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        comoving_emissivity = scattering * comoving_mean
        lab_emissivity = (
            lorentz_remap_signed_comoving_group_emissivity_perturbation_to_lab(
                np.broadcast_to(
                    comoving_emissivity[:, None, :],
                    (collision_groups, angle_points, depth_points),
                ),
                collision_edge,
                active_edge,
                transform.doppler_lab_to_comoving,
            )
        )
        response, _ = _solve_step_characteristics_ray_transport(
            zero_initial,
            old_width,
            new_width,
            mu,
            mesh_velocity,
            extinction,
            lab_emissivity,
            zero_left,
            zero_right,
            duration,
            speed,
            allow_turning_ray_upwind=bool(allow_turning_ray_upwind),
            allow_signed_fields=True,
        )
        return response

    right_hand_side = comoving_mean_from_active(residual)
    frequency_scale = np.max(np.abs(right_hand_side), axis=1)
    inactive = frequency_scale == 0.0
    frequency_scale[inactive] = 1.0
    scaled_rhs = right_hand_side / frequency_scale[:, None]

    def apply_operator(mean_value: NDArray[np.float64]) -> NDArray[np.float64]:
        active_response = active_response_from_comoving_mean(mean_value)
        result = mean_value - comoving_mean_from_active(active_response)
        if not np.all(np.isfinite(result)):
            raise ArithmeticError("mixed-frame spatial ALI operator became non-finite")
        return result

    def apply_scaled_operator(
        scaled_mean_value: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        # 中文：Doppler 会跨频率耦合，故必须显式做相似缩放，不能把尺度提出算子。
        physical_mean = scaled_mean_value * frequency_scale[:, None]
        return apply_operator(physical_mean) / frequency_scale[:, None]

    size = collision_groups * depth_points
    operator = LinearOperator(
        (size, size),
        matvec=lambda vector: apply_scaled_operator(
            np.asarray(vector).reshape(collision_groups, depth_points)
        ).reshape(-1),
        dtype=np.float64,
    )
    callback_residuals: list[float] = []
    scaled_solution, info = gmres(
        operator,
        scaled_rhs.reshape(-1),
        rtol=tolerance,
        atol=0.0,
        restart=restart,
        maxiter=maximum_cycles,
        callback=lambda value: callback_residuals.append(float(value)),
        callback_type="pr_norm",
    )
    corrected_mean = scaled_solution.reshape(
        collision_groups, depth_points
    ) * frequency_scale[:, None]
    corrected_mean[inactive] = 0.0
    correction = residual + active_response_from_comoving_mean(corrected_mean)
    scaled_audit = apply_scaled_operator(
        corrected_mean / frequency_scale[:, None]
    ) - scaled_rhs
    final_scaled_linf = float(np.max(np.abs(scaled_audit)))
    correction_mean = comoving_mean_from_active(correction)
    mean_scale = max(
        float(np.max(np.abs(correction_mean))),
        float(np.max(np.abs(corrected_mean))),
    )
    mean_difference = float(np.max(np.abs(correction_mean - corrected_mean)))
    mean_consistency = mean_difference / mean_scale if mean_scale > 0.0 else mean_difference
    converged = (
        int(info) == 0
        and final_scaled_linf <= 10.0 * tolerance
        and mean_consistency <= 10.0 * tolerance
    )
    if not np.all(np.isfinite(correction)):
        raise ArithmeticError("mixed-frame spatial ALI correction became non-finite")
    if not converged and not bool(allow_incomplete_krylov):
        raise ArithmeticError(
            "mixed-frame spatial ALI GMRES did not satisfy its declared audit: "
            f"info={int(info)}, scaled_linf={final_scaled_linf:.6e}, "
            f"mean_consistency={mean_consistency:.6e}"
        )
    return MixedFrameSpatialSourceCorrection(
        correction=_readonly(correction),
        corrected_comoving_mean_intensity=_readonly(corrected_mean),
        gmres_iteration_count=len(callback_residuals),
        gmres_reported_info=int(info),
        final_scaled_linf_linear_residual=final_scaled_linf,
        final_comoving_mean_consistency_linf=mean_consistency,
        fixed_point_converged=converged,
    )
