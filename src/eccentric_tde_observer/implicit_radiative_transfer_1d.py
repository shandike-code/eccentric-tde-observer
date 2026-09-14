"""一维移动网格上的隐式时间依赖离散纵标转移。

本模块在实验室系中守恒推进频率分辨比强度。网格边界可以随规定的
拉格朗日质量柱运动；物质源项当前保留静止介质形式，因此尚不包含
速度导致的频率和角度 Lorentz 耦合。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import bicgstab, gmres, splu

from .radiation import LIGHT_SPEED_CM_S
from .radiative_transfer_1d import (
    _boundary_array,
    _material_array,
    _mean_intensity,
    _validate_grid,
)
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class ImplicitALESlabStep:
    """一个后向 Euler ALE 辐射步及其逐频率守恒账本。"""

    final_intensity: NDArray[np.float64]
    mean_intensity: NDArray[np.float64]
    mesh_edge_velocity_cm_s: NDArray[np.float64]
    left_ale_face_intensity: NDArray[np.float64]
    right_ale_face_intensity: NDArray[np.float64]
    left_ale_energy_flux_nu_cgs: NDArray[np.float64]
    right_ale_energy_flux_nu_cgs: NDArray[np.float64]
    initial_radiation_energy_nu_erg_cm2_hz: NDArray[np.float64]
    final_radiation_energy_nu_erg_cm2_hz: NDArray[np.float64]
    material_heating_nu_erg_s_cm2_hz: NDArray[np.float64]
    energy_ledger_residual_nu_erg_cm2_hz: NDArray[np.float64]
    relative_energy_ledger_residual: NDArray[np.float64]
    relative_linear_system_residual: NDArray[np.float64]
    linear_iterations: NDArray[np.int64]
    duration_s: float
    maximum_mesh_speed_to_light: float
    minimum_intensity: float
    maximum_matrix_nonzeros: int
    linear_solver: str
    periodic_spatial_boundary: bool


def _positive_duration(duration_s: float) -> float:
    duration = float(duration_s)
    if not np.isfinite(duration) or duration <= 0.0:
        raise PhysicalDomainError("duration_s must be finite and positive")
    return duration


def _validated_old_edges(
    old_depth_edges_cm: ArrayLike, new_edges: NDArray[np.float64]
) -> NDArray[np.float64]:
    old_edges = np.array(old_depth_edges_cm, dtype=np.float64, copy=True)
    if old_edges.shape != new_edges.shape:
        raise PhysicalDomainError("old and new depth grids must have matching edges")
    if not np.all(np.isfinite(old_edges)) or np.any(np.diff(old_edges) <= 0.0):
        raise PhysicalDomainError(
            "old_depth_edges_cm must be finite and strictly increasing"
        )
    return old_edges


def _initial_intensity_array(
    values: ArrayLike, shape: tuple[int, int, int]
) -> NDArray[np.float64]:
    try:
        result = np.array(
            np.broadcast_to(np.asarray(values, dtype=np.float64), shape), copy=True
        )
    except ValueError as error:
        raise PhysicalDomainError(
            f"initial_intensity cannot broadcast to {shape}"
        ) from error
    if not np.all(np.isfinite(result)) or np.any(result < 0.0):
        raise PhysicalDomainError(
            "initial_intensity must be finite and non-negative"
        )
    return result


def _variable(depth: int, angle: int, angle_points: int) -> int:
    return depth * angle_points + angle


def _positive_source_iteration_one_frequency(
    initial: NDArray[np.float64],
    old_width: NDArray[np.float64],
    new_width: NDArray[np.float64],
    mu: NDArray[np.float64],
    weight: NDArray[np.float64],
    mesh_velocity: NDArray[np.float64],
    extinction: NDArray[np.float64],
    thermal_source: NDArray[np.float64],
    epsilon: NDArray[np.float64],
    left_exterior: NDArray[np.float64],
    right_exterior: NDArray[np.float64],
    duration: float,
    speed: float,
    periodic_spatial_boundary: bool,
    tolerance: float,
    maximum_iterations: int,
) -> tuple[NDArray[np.float64], int]:
    """用正性保持的对称格点 Gauss--Seidel 解静止介质散射耦合。"""
    angle_points, depth_points = initial.shape
    solution = np.array(initial.T, copy=True)
    diagonal = np.empty((depth_points, angle_points), dtype=np.float64)
    base_rhs = np.empty_like(diagonal)
    scattering_coefficient = speed * new_width * extinction * (1.0 - epsilon)
    for depth in range(depth_points):
        absorption = extinction[depth] * epsilon[depth]
        for angle, cosine in enumerate(mu):
            value = new_width[depth] / duration + speed * new_width[depth] * extinction[depth]
            rhs = (
                old_width[depth] / duration * initial[angle, depth]
                + speed * new_width[depth] * absorption * thermal_source[depth]
            )
            right_speed = speed * cosine - mesh_velocity[depth + 1]
            if right_speed >= 0.0:
                value += right_speed
            elif depth + 1 == depth_points and not periodic_spatial_boundary:
                rhs -= right_speed * right_exterior[angle]
            left_speed = speed * cosine - mesh_velocity[depth]
            if left_speed < 0.0:
                value -= left_speed
            elif depth == 0 and not periodic_spatial_boundary:
                rhs += left_speed * left_exterior[angle]
            diagonal[depth, angle] = value
            base_rhs[depth, angle] = rhs
    if np.any(diagonal <= 0.0):
        raise ArithmeticError("source iteration lost its positive local diagonal")

    iteration_count = 0
    for iteration_count in range(1, maximum_iterations + 1):
        previous = np.array(solution, copy=True)
        # 中文：前后各扫一次；所有入射邻居和局域散射系数均保持非负。
        for order in (range(depth_points), range(depth_points - 1, -1, -1)):
            for depth in order:
                rhs = np.array(base_rhs[depth], copy=True)
                for angle, cosine in enumerate(mu):
                    right_speed = speed * cosine - mesh_velocity[depth + 1]
                    if right_speed < 0.0:
                        if depth + 1 < depth_points:
                            rhs[angle] -= right_speed * solution[depth + 1, angle]
                        elif periodic_spatial_boundary:
                            rhs[angle] -= right_speed * solution[0, angle]
                    left_speed = speed * cosine - mesh_velocity[depth]
                    if left_speed >= 0.0:
                        if depth > 0:
                            rhs[angle] += left_speed * solution[depth - 1, angle]
                        elif periodic_spatial_boundary:
                            rhs[angle] += left_speed * solution[-1, angle]
                inverse_diagonal = 1.0 / diagonal[depth]
                lambda_diagonal = 0.5 * np.sum(weight * inverse_diagonal)
                denominator = 1.0 - scattering_coefficient[depth] * lambda_diagonal
                if not np.isfinite(denominator) or denominator <= 0.0:
                    raise ArithmeticError(
                        "source iteration local scattering denominator is not positive"
                    )
                mean = (
                    0.5 * np.sum(weight * rhs * inverse_diagonal) / denominator
                )
                solution[depth] = (
                    rhs + scattering_coefficient[depth] * mean
                ) * inverse_diagonal
        if not np.all(np.isfinite(solution)) or np.any(solution < 0.0):
            raise ArithmeticError("source iteration produced invalid intensity")
        scale = max(float(np.max(np.abs(solution))), float(np.max(np.abs(previous))))
        change = float(np.max(np.abs(solution - previous)))
        if (change / scale if scale > 0.0 else change) <= tolerance:
            break
    else:
        raise ArithmeticError(
            "implicit ALE source iteration did not converge: "
            f"iterations={maximum_iterations}"
        )
    return solution.T, iteration_count


def _positive_source_iteration_all_frequencies(
    initial: NDArray[np.float64],
    old_width: NDArray[np.float64],
    new_width: NDArray[np.float64],
    mu: NDArray[np.float64],
    weight: NDArray[np.float64],
    mesh_velocity: NDArray[np.float64],
    extinction: NDArray[np.float64],
    thermal_source: NDArray[np.float64],
    epsilon: NDArray[np.float64],
    left_exterior: NDArray[np.float64],
    right_exterior: NDArray[np.float64],
    duration: float,
    speed: float,
    periodic_spatial_boundary: bool,
    tolerance: float,
    maximum_iterations: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64], int, int]:
    """把全部频率批量推进，避免在 Python 中逐频率重复空间扫掠。"""
    frequency_points, angle_points, depth_points = initial.shape
    solution = np.transpose(initial, (0, 2, 1)).copy()
    diagonal = np.empty_like(solution)
    base_rhs = np.empty_like(solution)
    scattering_coefficient = speed * new_width[None, :] * extinction * (1.0 - epsilon)
    for depth in range(depth_points):
        absorption = extinction[:, depth] * epsilon[:, depth]
        for angle, cosine in enumerate(mu):
            value = (
                new_width[depth] / duration
                + speed * new_width[depth] * extinction[:, depth]
            )
            rhs = (
                old_width[depth] / duration * initial[:, angle, depth]
                + speed
                * new_width[depth]
                * absorption
                * thermal_source[:, depth]
            )
            right_speed = speed * cosine - mesh_velocity[depth + 1]
            if right_speed >= 0.0:
                value = value + right_speed
            elif depth + 1 == depth_points and not periodic_spatial_boundary:
                rhs = rhs - right_speed * right_exterior[:, angle]
            left_speed = speed * cosine - mesh_velocity[depth]
            if left_speed < 0.0:
                value = value - left_speed
            elif depth == 0 and not periodic_spatial_boundary:
                rhs = rhs + left_speed * left_exterior[:, angle]
            diagonal[:, depth, angle] = value
            base_rhs[:, depth, angle] = rhs
    if np.any(diagonal <= 0.0):
        raise ArithmeticError("source iteration lost its positive local diagonal")

    iteration_count = 0
    for iteration_count in range(1, maximum_iterations + 1):
        previous = np.array(solution, copy=True)
        for order in (range(depth_points), range(depth_points - 1, -1, -1)):
            for depth in order:
                rhs = np.array(base_rhs[:, depth, :], copy=True)
                right_speed = speed * mu - mesh_velocity[depth + 1]
                right_incoming = right_speed < 0.0
                if np.any(right_incoming):
                    if depth + 1 < depth_points:
                        rhs[:, right_incoming] -= (
                            right_speed[right_incoming][None, :]
                            * solution[:, depth + 1, right_incoming]
                        )
                    elif periodic_spatial_boundary:
                        rhs[:, right_incoming] -= (
                            right_speed[right_incoming][None, :]
                            * solution[:, 0, right_incoming]
                        )
                left_speed = speed * mu - mesh_velocity[depth]
                left_incoming = left_speed >= 0.0
                if np.any(left_incoming):
                    if depth > 0:
                        rhs[:, left_incoming] += (
                            left_speed[left_incoming][None, :]
                            * solution[:, depth - 1, left_incoming]
                        )
                    elif periodic_spatial_boundary:
                        rhs[:, left_incoming] += (
                            left_speed[left_incoming][None, :]
                            * solution[:, -1, left_incoming]
                        )
                inverse_diagonal = 1.0 / diagonal[:, depth, :]
                lambda_diagonal = 0.5 * np.sum(
                    weight[None, :] * inverse_diagonal, axis=1
                )
                denominator = 1.0 - (
                    scattering_coefficient[:, depth] * lambda_diagonal
                )
                if not np.all(np.isfinite(denominator)) or np.any(denominator <= 0.0):
                    raise ArithmeticError(
                        "source iteration local scattering denominator is not positive"
                    )
                mean = (
                    0.5
                    * np.sum(weight[None, :] * rhs * inverse_diagonal, axis=1)
                    / denominator
                )
                solution[:, depth, :] = (
                    rhs
                    + scattering_coefficient[:, depth, None] * mean[:, None]
                ) * inverse_diagonal
        if not np.all(np.isfinite(solution)) or np.any(solution < 0.0):
            raise ArithmeticError("source iteration produced invalid intensity")
        scale = np.maximum(
            np.max(np.abs(solution), axis=(1, 2)),
            np.max(np.abs(previous), axis=(1, 2)),
        )
        change = np.max(np.abs(solution - previous), axis=(1, 2))
        relative = np.array(change, copy=True)
        positive = scale > 0.0
        relative[positive] /= scale[positive]
        if np.all(relative <= tolerance):
            break
    else:
        raise ArithmeticError(
            "implicit ALE source iteration did not converge: "
            f"iterations={maximum_iterations}"
        )

    operator_value = diagonal * solution
    mean = 0.5 * np.einsum("m,fdm->fd", weight, solution)
    operator_value -= scattering_coefficient[:, :, None] * mean[:, :, None]
    for depth in range(depth_points):
        right_speed = speed * mu - mesh_velocity[depth + 1]
        right_incoming = right_speed < 0.0
        if depth + 1 < depth_points:
            operator_value[:, depth, right_incoming] += (
                right_speed[right_incoming][None, :]
                * solution[:, depth + 1, right_incoming]
            )
        elif periodic_spatial_boundary:
            operator_value[:, depth, right_incoming] += (
                right_speed[right_incoming][None, :]
                * solution[:, 0, right_incoming]
            )
        left_speed = speed * mu - mesh_velocity[depth]
        left_incoming = left_speed >= 0.0
        if depth > 0:
            operator_value[:, depth, left_incoming] -= (
                left_speed[left_incoming][None, :]
                * solution[:, depth - 1, left_incoming]
            )
        elif periodic_spatial_boundary:
            operator_value[:, depth, left_incoming] -= (
                left_speed[left_incoming][None, :]
                * solution[:, -1, left_incoming]
            )
    residual = operator_value - base_rhs
    residual_scale = np.maximum(
        np.max(np.abs(operator_value), axis=(1, 2)),
        np.max(np.abs(base_rhs), axis=(1, 2)),
    )
    relative_residual = np.max(np.abs(residual), axis=(1, 2))
    positive_scale = residual_scale > 0.0
    relative_residual[positive_scale] /= residual_scale[positive_scale]
    maximum_nonzeros = depth_points * angle_points * (angle_points + 2)
    return (
        np.transpose(solution, (0, 2, 1)),
        relative_residual,
        iteration_count,
        maximum_nonzeros,
    )


def _assemble_one_frequency(
    old_intensity: NDArray[np.float64],
    old_width: NDArray[np.float64],
    new_width: NDArray[np.float64],
    mu: NDArray[np.float64],
    weight: NDArray[np.float64],
    mesh_velocity: NDArray[np.float64],
    extinction: NDArray[np.float64],
    thermal_source: NDArray[np.float64],
    epsilon: NDArray[np.float64],
    left_exterior: NDArray[np.float64],
    right_exterior: NDArray[np.float64],
    duration: float,
    speed: float,
    periodic_spatial_boundary: bool,
    linear_solver: Literal["sparse_lu", "bicgstab", "gmres", "source_iteration"],
    iterative_tolerance: float,
    iterative_maximum_iterations: int,
):
    angle_points, depth_points = old_intensity.shape
    size = angle_points * depth_points
    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    right_hand_side = np.empty(size, dtype=np.float64)

    for depth in range(depth_points):
        absorption = float(extinction[depth] * epsilon[depth])
        scattering = float(extinction[depth] * (1.0 - epsilon[depth]))
        for angle, cosine in enumerate(mu):
            row = _variable(depth, angle, angle_points)
            diagonal = float(
                new_width[depth] / duration
                + speed * new_width[depth] * extinction[depth]
            )
            right_hand_side[row] = float(
                old_width[depth] / duration * old_intensity[angle, depth]
                + speed * new_width[depth] * absorption * thermal_source[depth]
            )

            # 中文：界面通量按相对网格速度 c*mu-w 做单调迎风。
            right_speed = float(speed * cosine - mesh_velocity[depth + 1])
            if right_speed >= 0.0:
                diagonal += right_speed
            elif depth + 1 < depth_points:
                rows.append(row)
                columns.append(_variable(depth + 1, angle, angle_points))
                values.append(right_speed)
            elif periodic_spatial_boundary:
                rows.append(row)
                columns.append(_variable(0, angle, angle_points))
                values.append(right_speed)
            else:
                right_hand_side[row] -= right_speed * right_exterior[angle]

            left_speed = float(speed * cosine - mesh_velocity[depth])
            if left_speed < 0.0:
                diagonal -= left_speed
            elif depth > 0:
                rows.append(row)
                columns.append(_variable(depth - 1, angle, angle_points))
                values.append(-left_speed)
            elif periodic_spatial_boundary:
                rows.append(row)
                columns.append(
                    _variable(depth_points - 1, angle, angle_points)
                )
                values.append(-left_speed)
            else:
                right_hand_side[row] += left_speed * left_exterior[angle]

            rows.append(row)
            columns.append(row)
            values.append(diagonal)
            if scattering > 0.0:
                coefficient = -0.5 * speed * new_width[depth] * scattering
                for coupled_angle in range(angle_points):
                    rows.append(row)
                    columns.append(
                        _variable(depth, coupled_angle, angle_points)
                    )
                    values.append(coefficient * float(weight[coupled_angle]))

    matrix = coo_matrix(
        (values, (rows, columns)), shape=(size, size), dtype=np.float64
    ).tocsc()
    diagonal = matrix.diagonal()
    if not np.all(np.isfinite(diagonal)) or np.any(diagonal <= 0.0):
        raise ArithmeticError("implicit ALE matrix lost its positive diagonal")
    # 中文：逐行除以正对角，避免光速输运项掩盖较小的储能与吸收项。
    inverse_diagonal = 1.0 / diagonal
    scaled_matrix = matrix.multiply(inverse_diagonal[:, None]).tocsc()
    scaled_right_hand_side = right_hand_side * inverse_diagonal
    if linear_solver == "source_iteration":
        intensity, iteration_count = _positive_source_iteration_one_frequency(
            old_intensity,
            old_width,
            new_width,
            mu,
            weight,
            mesh_velocity,
            extinction,
            thermal_source,
            epsilon,
            left_exterior,
            right_exterior,
            duration,
            speed,
            periodic_spatial_boundary,
            iterative_tolerance,
            iterative_maximum_iterations,
        )
        solution = intensity.T.reshape(size)
    elif linear_solver == "sparse_lu":
        factor = splu(scaled_matrix)
        solution = factor.solve(scaled_right_hand_side)
        iteration_count = 1
    elif linear_solver == "bicgstab":
        iteration_count = 0

        def count_iteration(_solution: NDArray[np.float64]) -> None:
            nonlocal iteration_count
            iteration_count += 1

        # 中文：按行缩放后主对角为一；BiCGSTAB 避免逐频率稀疏 LU 的填充。
        solution, information = bicgstab(
            scaled_matrix,
            scaled_right_hand_side,
            x0=old_intensity.T.reshape(size),
            rtol=iterative_tolerance,
            atol=0.0,
            maxiter=iterative_maximum_iterations,
            callback=count_iteration,
        )
        if information != 0:
            raise ArithmeticError(
                "implicit ALE BiCGSTAB did not converge: "
                f"info={information}, iterations={iteration_count}"
            )
    else:
        iteration_count = 0

        def count_gmres_iteration(_residual_norm: float) -> None:
            nonlocal iteration_count
            iteration_count += 1

        # 中文：重启 GMRES 每个频率独立工作，内存不随总频率数累积。
        solution, information = gmres(
            scaled_matrix,
            scaled_right_hand_side,
            x0=old_intensity.T.reshape(size),
            rtol=iterative_tolerance,
            atol=0.0,
            restart=min(32, iterative_maximum_iterations),
            maxiter=iterative_maximum_iterations,
            callback=count_gmres_iteration,
            callback_type="pr_norm",
        )
        if information != 0:
            raise ArithmeticError(
                "implicit ALE GMRES did not converge: "
                f"info={information}, iterations={iteration_count}"
            )
    residual = matrix @ solution - right_hand_side
    scale = max(
        float(np.max(np.abs(matrix @ solution))),
        float(np.max(np.abs(right_hand_side))),
    )
    relative_residual = (
        float(np.max(np.abs(residual))) / scale
        if scale > 0.0
        else float(np.max(np.abs(residual)))
    )
    intensity = solution.reshape(depth_points, angle_points).T
    if not np.all(np.isfinite(intensity)) or np.any(intensity < 0.0):
        raise ArithmeticError("implicit ALE transfer produced invalid intensity")
    return intensity, relative_residual, int(matrix.nnz), iteration_count


def _ale_boundary_face_intensity(
    intensity: NDArray[np.float64],
    exterior: NDArray[np.float64],
    relative_speed: NDArray[np.float64],
    *,
    left: bool,
) -> NDArray[np.float64]:
    if left:
        return np.where(relative_speed >= 0.0, exterior, intensity[:, 0])
    return np.where(relative_speed >= 0.0, intensity[:, -1], exterior)


def solve_implicit_ale_slab_step(
    frequency_hz: ArrayLike,
    old_depth_edges_cm: ArrayLike,
    new_depth_edges_cm: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    initial_intensity: ArrayLike,
    extinction_per_cm: ArrayLike,
    thermal_source_intensity: ArrayLike,
    absorption_probability: ArrayLike,
    duration_s: float,
    *,
    left_exterior_intensity: ArrayLike = 0.0,
    right_exterior_intensity: ArrayLike = 0.0,
    periodic_spatial_boundary: bool = False,
    propagation_speed_cm_s: float = LIGHT_SPEED_CM_S,
    linear_solver: Literal[
        "sparse_lu", "bicgstab", "gmres", "source_iteration"
    ] = "sparse_lu",
    iterative_tolerance: float = 1.0e-11,
    iterative_maximum_iterations: int = 4096,
) -> ImplicitALESlabStep:
    """在移动非均匀网格上推进一个全隐式离散纵标时间步。

    对每个频率求解

    ``d(Delta z I)/dt + [(c mu-w)I]_R-L = c Delta z chi(S-I)``，

    其中 ``S=epsilon*B+(1-epsilon)*J``。ALE 只处理移动控制体；
    物质源项的 Lorentz 变换和频率耦合尚未包含。
    """
    frequency, new_edges, mu, weight = _validate_grid(
        frequency_hz,
        new_depth_edges_cm,
        direction_cosine,
        angular_weight,
    )
    old_edges = _validated_old_edges(old_depth_edges_cm, new_edges)
    duration = _positive_duration(duration_s)
    speed = float(propagation_speed_cm_s)
    if not np.isfinite(speed) or speed <= 0.0:
        raise PhysicalDomainError(
            "propagation_speed_cm_s must be finite and positive"
        )
    if linear_solver not in (
        "sparse_lu",
        "bicgstab",
        "gmres",
        "source_iteration",
    ):
        raise PhysicalDomainError(
            "linear_solver must be 'sparse_lu', 'bicgstab', 'gmres' or 'source_iteration'"
        )
    tolerance = float(iterative_tolerance)
    if not np.isfinite(tolerance) or tolerance <= 0.0 or tolerance >= 1.0:
        raise PhysicalDomainError(
            "iterative_tolerance must be finite and lie strictly between zero and one"
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
    old_width = np.diff(old_edges)
    new_width = np.diff(new_edges)
    mesh_velocity = (new_edges - old_edges) / duration
    if not np.all(np.isfinite(mesh_velocity)):
        raise PhysicalDomainError("mesh edge velocity became non-finite")
    if periodic_spatial_boundary and not np.isclose(
        mesh_velocity[0],
        mesh_velocity[-1],
        rtol=2.0e-13,
        atol=2.0e-13 * speed,
    ):
        raise PhysicalDomainError(
            "periodic moving grids require equal velocities at both boundary faces"
        )

    frequency_points = frequency.size
    angle_points = mu.size
    depth_points = new_width.size
    material_shape = (frequency_points, depth_points)
    intensity_shape = (frequency_points, angle_points, depth_points)
    initial = _initial_intensity_array(initial_intensity, intensity_shape)
    extinction = _material_array(
        "extinction_per_cm", extinction_per_cm, material_shape, lower=0.0
    )
    thermal_source = _material_array(
        "thermal_source_intensity",
        thermal_source_intensity,
        material_shape,
        lower=0.0,
    )
    epsilon = _material_array(
        "absorption_probability",
        absorption_probability,
        material_shape,
        lower=0.0,
        upper=1.0,
    )
    left = _boundary_array(
        "left_exterior_intensity",
        left_exterior_intensity,
        (frequency_points, angle_points),
    )
    right = _boundary_array(
        "right_exterior_intensity",
        right_exterior_intensity,
        (frequency_points, angle_points),
    )
    if periodic_spatial_boundary and (np.any(left != 0.0) or np.any(right != 0.0)):
        raise PhysicalDomainError(
            "periodic spatial boundaries cannot also specify exterior intensity"
        )

    if linear_solver == "source_iteration":
        final, linear_residual, iteration_count, maximum_nonzeros = (
            _positive_source_iteration_all_frequencies(
                initial,
                old_width,
                new_width,
                mu,
                weight,
                mesh_velocity,
                extinction,
                thermal_source,
                epsilon,
                left,
                right,
                duration,
                speed,
                bool(periodic_spatial_boundary),
                tolerance,
                maximum_iterations,
            )
        )
        linear_iterations = np.full(
            frequency_points, iteration_count, dtype=np.int64
        )
    else:
        final = np.empty_like(initial)
        linear_residual = np.empty(frequency_points, dtype=np.float64)
        linear_iterations = np.empty(frequency_points, dtype=np.int64)
        maximum_nonzeros = 0
        for frequency_index in range(frequency_points):
            (
                final[frequency_index],
                linear_residual[frequency_index],
                nonzeros,
                linear_iterations[frequency_index],
            ) = (
                _assemble_one_frequency(
                    initial[frequency_index],
                    old_width,
                    new_width,
                    mu,
                    weight,
                    mesh_velocity,
                    extinction[frequency_index],
                    thermal_source[frequency_index],
                    epsilon[frequency_index],
                    left[frequency_index],
                    right[frequency_index],
                    duration,
                    speed,
                    bool(periodic_spatial_boundary),
                    linear_solver,
                    tolerance,
                    maximum_iterations,
                )
            )
            maximum_nonzeros = max(maximum_nonzeros, nonzeros)

    initial_mean = _mean_intensity(initial, weight)
    final_mean = _mean_intensity(final, weight)
    left_relative_speed = speed * mu - mesh_velocity[0]
    right_relative_speed = speed * mu - mesh_velocity[-1]
    left_face = np.empty((frequency_points, angle_points), dtype=np.float64)
    right_face = np.empty_like(left_face)
    for frequency_index in range(frequency_points):
        if periodic_spatial_boundary:
            periodic_face = np.where(
                left_relative_speed >= 0.0,
                final[frequency_index, :, -1],
                final[frequency_index, :, 0],
            )
            left_face[frequency_index] = periodic_face
            right_face[frequency_index] = periodic_face
        else:
            left_face[frequency_index] = _ale_boundary_face_intensity(
                final[frequency_index],
                left[frequency_index],
                left_relative_speed,
                left=True,
            )
            right_face[frequency_index] = _ale_boundary_face_intensity(
                final[frequency_index],
                right[frequency_index],
                right_relative_speed,
                left=False,
            )
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
        final_mean * new_width[None, :], axis=1
    )
    absorption = extinction * epsilon
    material_heating = 4.0 * np.pi * np.sum(
        absorption
        * (final_mean - thermal_source)
        * new_width[None, :],
        axis=1,
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
    positive_scale = ledger_scale > 0.0
    relative_ledger[positive_scale] /= ledger_scale[positive_scale]
    arrays = (
        final,
        final_mean,
        left_face,
        right_face,
        left_flux,
        right_flux,
        initial_energy,
        final_energy,
        material_heating,
        ledger,
        relative_ledger,
        linear_residual,
        linear_iterations,
    )
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ArithmeticError("implicit ALE diagnostics became non-finite")
    return ImplicitALESlabStep(
        final_intensity=_readonly(final),
        mean_intensity=_readonly(final_mean),
        mesh_edge_velocity_cm_s=_readonly(mesh_velocity),
        left_ale_face_intensity=_readonly(left_face),
        right_ale_face_intensity=_readonly(right_face),
        left_ale_energy_flux_nu_cgs=_readonly(left_flux),
        right_ale_energy_flux_nu_cgs=_readonly(right_flux),
        initial_radiation_energy_nu_erg_cm2_hz=_readonly(initial_energy),
        final_radiation_energy_nu_erg_cm2_hz=_readonly(final_energy),
        material_heating_nu_erg_s_cm2_hz=_readonly(material_heating),
        energy_ledger_residual_nu_erg_cm2_hz=_readonly(ledger),
        relative_energy_ledger_residual=_readonly(relative_ledger),
        relative_linear_system_residual=_readonly(linear_residual),
        linear_iterations=_readonly(linear_iterations),
        duration_s=duration,
        maximum_mesh_speed_to_light=float(np.max(np.abs(mesh_velocity)) / speed),
        minimum_intensity=float(np.min(final)),
        maximum_matrix_nonzeros=maximum_nonzeros,
        linear_solver=linear_solver,
        periodic_spatial_boundary=bool(periodic_spatial_boundary),
    )
