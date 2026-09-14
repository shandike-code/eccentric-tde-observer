"""一维平面平行频率—角度辐射转移的解析控制求解器。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import LinearOperator, onenormest, splu
from scipy.special import expn

from .radiation import LIGHT_SPEED_CM_S
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


def gauss_legendre_mu_weights(order: int) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """返回覆盖 ``[-1,1]`` 的偶数阶 Gauss--Legendre 角求积。"""
    if not isinstance(order, (int, np.integer)) or isinstance(order, (bool, np.bool_)):
        raise PhysicalDomainError("angular order must be an integer")
    order = int(order)
    if order < 2 or order % 2 != 0:
        raise PhysicalDomainError("angular order must be an even integer >= 2")
    mu, weight = np.polynomial.legendre.leggauss(order)
    return _readonly(mu), _readonly(weight)


def gauss_legendre_half_range_mu_weights(
    order: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """返回分别在两个半球求积的偶数阶 Gauss--Legendre 节点。

    单侧入射边界在 ``mu=0`` 处不连续。半区间求积分别映射 ``[0,1]``
    和 ``[-1,0]``，可精确积分每个半球上的低阶角矩，同时避开掠射零点。
    ``order`` 是两个半球合计的方向数。
    """
    if not isinstance(order, (int, np.integer)) or isinstance(order, (bool, np.bool_)):
        raise PhysicalDomainError("angular order must be an integer")
    order = int(order)
    if order < 2 or order % 2 != 0:
        raise PhysicalDomainError("angular order must be an even integer >= 2")
    positive_node, positive_weight = np.polynomial.legendre.leggauss(order // 2)
    positive_mu = 0.5 * (positive_node + 1.0)
    positive_weight = 0.5 * positive_weight
    mu = np.concatenate((-positive_mu[::-1], positive_mu))
    weight = np.concatenate((positive_weight[::-1], positive_weight))
    return _readonly(mu), _readonly(weight)


def gauss_legendre_split_mu_weights(
    order: int, split_mu: float
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """在指定特征分界两侧分别构造 Gauss--Legendre 角求积。

    ``order`` 是两个区间合计的偶数方向数。该求积用于入射边界在
    ``split_mu`` 处不光滑的移动网格，不改变总角域 ``[-1,1]``。
    """
    if not isinstance(order, (int, np.integer)) or isinstance(order, (bool, np.bool_)):
        raise PhysicalDomainError("angular order must be an integer")
    order = int(order)
    split = float(split_mu)
    if order < 2 or order % 2 != 0:
        raise PhysicalDomainError("angular order must be an even integer >= 2")
    if not np.isfinite(split) or split <= -1.0 or split >= 1.0:
        raise PhysicalDomainError("split_mu must be finite and lie in (-1,1)")
    node, base_weight = np.polynomial.legendre.leggauss(order // 2)
    left_mu = 0.5 * ((split + 1.0) * node + split - 1.0)
    left_weight = 0.5 * (split + 1.0) * base_weight
    right_mu = 0.5 * ((1.0 - split) * node + split + 1.0)
    right_weight = 0.5 * (1.0 - split) * base_weight
    mu = np.concatenate((left_mu, right_mu))
    weight = np.concatenate((left_weight, right_weight))
    return _readonly(mu), _readonly(weight)


def _validate_grid(
    frequency_hz: ArrayLike,
    depth_edges_cm: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    edges = np.array(depth_edges_cm, dtype=np.float64, copy=True)
    mu = np.array(direction_cosine, dtype=np.float64, copy=True)
    weight = np.array(angular_weight, dtype=np.float64, copy=True)
    if frequency.ndim != 1 or frequency.size < 1:
        raise PhysicalDomainError("frequency_hz must be a non-empty 1D array")
    if not np.all(np.isfinite(frequency)) or np.any(frequency <= 0.0) or np.any(np.diff(frequency) <= 0.0):
        raise PhysicalDomainError("frequency_hz must be finite, positive and strictly increasing")
    if edges.ndim != 1 or edges.size < 2:
        raise PhysicalDomainError("depth_edges_cm must be a 1D array with at least two entries")
    if not np.all(np.isfinite(edges)) or np.any(np.diff(edges) <= 0.0):
        raise PhysicalDomainError("depth_edges_cm must be finite and strictly increasing")
    if mu.ndim != 1 or weight.shape != mu.shape or mu.size < 2:
        raise PhysicalDomainError("direction_cosine and angular_weight must be matching 1D arrays")
    if (
        not np.all(np.isfinite(mu))
        or not np.all(np.isfinite(weight))
        or np.any(mu <= -1.0)
        or np.any(mu >= 1.0)
        or np.any(mu == 0.0)
        or np.any(weight <= 0.0)
        or not np.any(mu < 0.0)
        or not np.any(mu > 0.0)
    ):
        raise PhysicalDomainError("angular grid requires finite nonzero mu in (-1,1) and positive weights")
    if not np.isclose(np.sum(weight), 2.0, rtol=2.0e-13, atol=2.0e-15):
        raise PhysicalDomainError("angular weights must integrate unity over solid-angle cosine")
    return frequency, edges, mu, weight


def _material_array(
    name: str,
    values: ArrayLike,
    shape: tuple[int, int],
    *,
    lower: float,
    upper: float | None = None,
) -> NDArray[np.float64]:
    try:
        result = np.array(np.broadcast_to(np.asarray(values, dtype=np.float64), shape), copy=True)
    except ValueError as error:
        raise PhysicalDomainError(f"{name} cannot broadcast to {shape}") from error
    invalid = (~np.isfinite(result)) | (result < lower)
    if upper is not None:
        invalid |= result > upper
    if np.any(invalid):
        raise PhysicalDomainError(f"{name} lies outside its allowed finite range")
    return result


def _boundary_array(
    name: str,
    values: ArrayLike,
    shape: tuple[int, int],
) -> NDArray[np.float64]:
    try:
        result = np.array(np.broadcast_to(np.asarray(values, dtype=np.float64), shape), copy=True)
    except ValueError as error:
        raise PhysicalDomainError(f"{name} cannot broadcast to {shape}") from error
    if not np.all(np.isfinite(result)) or np.any(result < 0.0):
        raise PhysicalDomainError(f"{name} must be finite and non-negative")
    return result


def _validate_incoming_boundaries(
    top: NDArray[np.float64],
    bottom: NDArray[np.float64],
    mu: NDArray[np.float64],
) -> None:
    if np.any(top[:, mu < 0.0] != 0.0):
        raise PhysicalDomainError("top boundary may specify only downward incoming directions")
    if np.any(bottom[:, mu > 0.0] != 0.0):
        raise PhysicalDomainError("bottom boundary may specify only upward incoming directions")


def _attenuation_average_factor(optical_path: float) -> float:
    if optical_path == 0.0:
        return 1.0
    return float(-np.expm1(-optical_path) / optical_path)


def _formal_sweep_one_frequency(
    source: NDArray[np.float64],
    cell_optical_depth: NDArray[np.float64],
    mu: NDArray[np.float64],
    top_incoming: NDArray[np.float64],
    bottom_incoming: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    angle_points = mu.size
    depth_points = source.size
    cell_average = np.empty((angle_points, depth_points), dtype=np.float64)
    top_boundary = np.empty(angle_points, dtype=np.float64)
    bottom_boundary = np.empty(angle_points, dtype=np.float64)
    for angle, cosine in enumerate(mu):
        absolute_cosine = abs(float(cosine))
        if cosine > 0.0:
            incoming = float(top_incoming[angle])
            top_boundary[angle] = incoming
            indices = range(depth_points)
        else:
            incoming = float(bottom_incoming[angle])
            bottom_boundary[angle] = incoming
            indices = range(depth_points - 1, -1, -1)
        for depth in indices:
            optical_path = float(cell_optical_depth[depth] / absolute_cosine)
            attenuation = float(np.exp(-optical_path))
            average_factor = _attenuation_average_factor(optical_path)
            local_source = float(source[depth])
            # 中文：分层内源函数取常数，沿特征线精确积分，不把大光深裁到上限。
            cell_average[angle, depth] = (
                local_source + (incoming - local_source) * average_factor
            )
            incoming = local_source + (incoming - local_source) * attenuation
        if cosine > 0.0:
            bottom_boundary[angle] = incoming
        else:
            top_boundary[angle] = incoming
    arrays = (cell_average, top_boundary, bottom_boundary)
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ArithmeticError("formal transfer sweep became non-finite")
    if any(np.any(array < 0.0) for array in arrays):
        raise ArithmeticError("formal transfer sweep produced negative intensity")
    return arrays


def _mean_intensity(
    intensity: NDArray[np.float64], weight: NDArray[np.float64]
) -> NDArray[np.float64]:
    return 0.5 * np.einsum("m,fmz->fz", weight, intensity)


def _boundary_flux(
    boundary_intensity: NDArray[np.float64],
    mu: NDArray[np.float64],
    weight: NDArray[np.float64],
) -> NDArray[np.float64]:
    return 2.0 * np.pi * np.einsum("m,fm,m->f", weight, boundary_intensity, mu)


def _sparse_interface_scattering_solution_one_frequency(
    thermal_source: NDArray[np.float64],
    absorption_probability: NDArray[np.float64],
    cell_optical_depth: NDArray[np.float64],
    mu: NDArray[np.float64],
    weight: NDArray[np.float64],
    top_incoming: NDArray[np.float64],
    bottom_incoming: NDArray[np.float64],
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    float,
]:
    """用稀疏界面强度方程求同一分层常源函数离散问题。"""
    depth_points = thermal_source.size
    angle_points = mu.size
    size = depth_points * angle_points
    attenuation = np.empty((depth_points, angle_points), dtype=np.float64)
    average_factor = np.empty_like(attenuation)
    for depth in range(depth_points):
        for angle, cosine in enumerate(mu):
            optical_path = float(cell_optical_depth[depth] / abs(float(cosine)))
            attenuation[depth, angle] = np.exp(-optical_path)
            average_factor[depth, angle] = _attenuation_average_factor(
                optical_path
            )

    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    right_hand_side = np.empty(size, dtype=np.float64)

    def variable(depth: int, angle: int) -> int:
        # 每个未知量是该方向离开当前单元的界面强度；按深度分块保持带状稀疏性。
        return depth * angle_points + angle

    for depth in range(depth_points):
        epsilon = float(absorption_probability[depth])
        scattering = 1.0 - epsilon
        source_denominator = 1.0 - scattering * 0.5 * float(
            np.sum(weight * (1.0 - average_factor[depth]))
        )
        if not np.isfinite(source_denominator) or source_denominator <= 0.0:
            raise ArithmeticError(
                "sparse scattering source denominator became non-positive"
            )
        source_constant = epsilon * float(thermal_source[depth]) / source_denominator
        source_coefficient = (
            scattering
            * 0.5
            * weight
            * average_factor[depth]
            / source_denominator
        )
        incoming_boundary = np.empty(angle_points, dtype=np.float64)
        incoming_variable = np.full(angle_points, -1, dtype=np.int64)
        for angle, cosine in enumerate(mu):
            if cosine > 0.0:
                if depth == 0:
                    incoming_boundary[angle] = top_incoming[angle]
                else:
                    incoming_boundary[angle] = 0.0
                    incoming_variable[angle] = variable(depth - 1, angle)
            else:
                if depth == depth_points - 1:
                    incoming_boundary[angle] = bottom_incoming[angle]
                else:
                    incoming_boundary[angle] = 0.0
                    incoming_variable[angle] = variable(depth + 1, angle)

        for angle in range(angle_points):
            row = variable(depth, angle)
            rows.append(row)
            columns.append(row)
            values.append(1.0)
            one_minus_attenuation = 1.0 - attenuation[depth, angle]
            right_hand_side[row] = one_minus_attenuation * source_constant
            for coupled_angle in range(angle_points):
                coefficient = one_minus_attenuation * source_coefficient[
                    coupled_angle
                ]
                if coupled_angle == angle:
                    coefficient += attenuation[depth, angle]
                coupled_variable = int(incoming_variable[coupled_angle])
                if coupled_variable >= 0:
                    rows.append(row)
                    columns.append(coupled_variable)
                    values.append(-coefficient)
                else:
                    right_hand_side[row] += (
                        coefficient * incoming_boundary[coupled_angle]
                    )

    matrix = coo_matrix(
        (values, (rows, columns)), shape=(size, size), dtype=np.float64
    ).tocsc()
    factor = splu(matrix)
    outgoing = factor.solve(right_hand_side).reshape(depth_points, angle_points)
    inverse = LinearOperator(
        matrix.shape,
        matvec=lambda vector: factor.solve(vector),
        rmatvec=lambda vector: factor.solve(vector, trans="T"),
        matmat=lambda array: factor.solve(array),
        rmatmat=lambda array: factor.solve(array, trans="T"),
        dtype=np.float64,
    )
    condition_number = float(onenormest(matrix) * onenormest(inverse))

    incoming = np.empty_like(outgoing)
    for depth in range(depth_points):
        for angle, cosine in enumerate(mu):
            if cosine > 0.0:
                incoming[depth, angle] = (
                    top_incoming[angle]
                    if depth == 0
                    else outgoing[depth - 1, angle]
                )
            else:
                incoming[depth, angle] = (
                    bottom_incoming[angle]
                    if depth == depth_points - 1
                    else outgoing[depth + 1, angle]
                )
    source = np.empty(depth_points, dtype=np.float64)
    cell_average = np.empty((angle_points, depth_points), dtype=np.float64)
    for depth in range(depth_points):
        epsilon = float(absorption_probability[depth])
        scattering = 1.0 - epsilon
        denominator = 1.0 - scattering * 0.5 * float(
            np.sum(weight * (1.0 - average_factor[depth]))
        )
        coefficient = (
            scattering
            * 0.5
            * weight
            * average_factor[depth]
            / denominator
        )
        source[depth] = (
            epsilon * thermal_source[depth] / denominator
            + float(np.sum(coefficient * incoming[depth]))
        )
        cell_average[:, depth] = source[depth] + average_factor[depth] * (
            incoming[depth] - source[depth]
        )
    top_boundary = np.empty(angle_points, dtype=np.float64)
    bottom_boundary = np.empty(angle_points, dtype=np.float64)
    for angle, cosine in enumerate(mu):
        if cosine > 0.0:
            top_boundary[angle] = top_incoming[angle]
            bottom_boundary[angle] = outgoing[-1, angle]
        else:
            top_boundary[angle] = outgoing[0, angle]
            bottom_boundary[angle] = bottom_incoming[angle]
    arrays = (source, cell_average, top_boundary, bottom_boundary)
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ArithmeticError("sparse interface scattering solve became non-finite")
    if any(np.any(array < 0.0) for array in arrays):
        raise ArithmeticError("sparse interface scattering solve became negative")
    if not np.isfinite(condition_number) or condition_number <= 0.0:
        raise ArithmeticError("sparse interface condition estimate became invalid")
    return source, cell_average, top_boundary, bottom_boundary, condition_number


@dataclass(frozen=True)
class StaticSlabTransfer:
    """静态平面平行板的频率—角度离散纵标解。"""

    frequency_hz: NDArray[np.float64]
    depth_edges_cm: NDArray[np.float64]
    direction_cosine: NDArray[np.float64]
    angular_weight: NDArray[np.float64]
    intensity_cell_average: NDArray[np.float64]
    source_function: NDArray[np.float64]
    mean_intensity: NDArray[np.float64]
    top_boundary_intensity: NDArray[np.float64]
    bottom_boundary_intensity: NDArray[np.float64]
    top_net_flux: NDArray[np.float64]
    bottom_net_flux: NDArray[np.float64]
    source_equation_residual: NDArray[np.float64]
    energy_balance_residual: NDArray[np.float64]
    relative_energy_balance_residual: NDArray[np.float64]
    lambda_system_condition_number: NDArray[np.float64]
    scattering_linear_solver: str


def solve_static_slab_transfer(
    frequency_hz: ArrayLike,
    depth_edges_cm: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    extinction_per_cm: ArrayLike,
    thermal_source_intensity: ArrayLike,
    absorption_probability: ArrayLike,
    *,
    top_incoming_intensity: ArrayLike = 0.0,
    bottom_incoming_intensity: ArrayLike = 0.0,
    scattering_linear_solver: Literal["dense_lambda", "sparse_interface"] = (
        "dense_lambda"
    ),
) -> StaticSlabTransfer:
    """求解各向同性相干散射的静态板层转移。

    源函数为 ``S=epsilon*B+(1-epsilon)*J``。对含散射问题，代码显式
    构造分层平均强度的离散 Lambda 算子并解线性方程，不用失败迭代外推。
    """
    frequency, edges, mu, weight = _validate_grid(
        frequency_hz, depth_edges_cm, direction_cosine, angular_weight
    )
    frequency_points = frequency.size
    depth_points = edges.size - 1
    angle_points = mu.size
    shape = (frequency_points, depth_points)
    extinction = _material_array("extinction_per_cm", extinction_per_cm, shape, lower=0.0)
    thermal_source = _material_array(
        "thermal_source_intensity", thermal_source_intensity, shape, lower=0.0
    )
    epsilon = _material_array(
        "absorption_probability", absorption_probability, shape, lower=0.0, upper=1.0
    )
    top = _boundary_array(
        "top_incoming_intensity", top_incoming_intensity, (frequency_points, angle_points)
    )
    bottom = _boundary_array(
        "bottom_incoming_intensity", bottom_incoming_intensity, (frequency_points, angle_points)
    )
    _validate_incoming_boundaries(top, bottom, mu)
    if scattering_linear_solver not in ("dense_lambda", "sparse_interface"):
        raise PhysicalDomainError("unsupported scattering linear solver")
    width = np.diff(edges)
    optical_depth = extinction * width[None, :]

    intensity = np.empty((frequency_points, angle_points, depth_points), dtype=np.float64)
    source = np.empty(shape, dtype=np.float64)
    top_boundary = np.empty((frequency_points, angle_points), dtype=np.float64)
    bottom_boundary = np.empty((frequency_points, angle_points), dtype=np.float64)
    condition_number = np.ones(frequency_points, dtype=np.float64)

    zero_source = np.zeros(depth_points, dtype=np.float64)
    zero_boundary = np.zeros(angle_points, dtype=np.float64)
    for frequency_index in range(frequency_points):
        if np.all(epsilon[frequency_index] == 1.0):
            source[frequency_index] = thermal_source[frequency_index]
        elif scattering_linear_solver == "sparse_interface":
            (
                source[frequency_index],
                intensity[frequency_index],
                top_boundary[frequency_index],
                bottom_boundary[frequency_index],
                condition_number[frequency_index],
            ) = _sparse_interface_scattering_solution_one_frequency(
                thermal_source[frequency_index],
                epsilon[frequency_index],
                optical_depth[frequency_index],
                mu,
                weight,
                top[frequency_index],
                bottom[frequency_index],
            )
            continue
        else:
            boundary_only, _, _ = _formal_sweep_one_frequency(
                zero_source,
                optical_depth[frequency_index],
                mu,
                top[frequency_index],
                bottom[frequency_index],
            )
            boundary_mean = 0.5 * np.einsum("m,mz->z", weight, boundary_only)
            lambda_operator = np.empty((depth_points, depth_points), dtype=np.float64)
            for source_depth in range(depth_points):
                basis = np.zeros(depth_points, dtype=np.float64)
                basis[source_depth] = 1.0
                response, _, _ = _formal_sweep_one_frequency(
                    basis,
                    optical_depth[frequency_index],
                    mu,
                    zero_boundary,
                    zero_boundary,
                )
                lambda_operator[:, source_depth] = 0.5 * np.einsum(
                    "m,mz->z", weight, response
                )
            scattering_fraction = 1.0 - epsilon[frequency_index]
            system = np.eye(depth_points) - scattering_fraction[:, None] * lambda_operator
            right_hand_side = (
                scattering_fraction * boundary_mean
                + epsilon[frequency_index] * thermal_source[frequency_index]
            )
            condition_number[frequency_index] = float(np.linalg.cond(system))
            source[frequency_index] = np.linalg.solve(system, right_hand_side)
            if np.any(source[frequency_index] < 0.0):
                raise ArithmeticError("static scattering solve produced negative source function")
        (
            intensity[frequency_index],
            top_boundary[frequency_index],
            bottom_boundary[frequency_index],
        ) = _formal_sweep_one_frequency(
            source[frequency_index],
            optical_depth[frequency_index],
            mu,
            top[frequency_index],
            bottom[frequency_index],
        )

    mean = _mean_intensity(intensity, weight)
    source_target = epsilon * thermal_source + (1.0 - epsilon) * mean
    source_absolute_residual = np.max(np.abs(source - source_target), axis=1)
    source_scale = np.max(
        np.concatenate((np.abs(source), np.abs(source_target)), axis=1), axis=1
    )
    source_residual = source_absolute_residual.copy()
    positive_source_scale = source_scale > 0.0
    source_residual[positive_source_scale] /= source_scale[positive_source_scale]
    top_flux = _boundary_flux(top_boundary, mu, weight)
    bottom_flux = _boundary_flux(bottom_boundary, mu, weight)
    material_exchange = np.sum(
        4.0
        * np.pi
        * extinction
        * epsilon
        * (thermal_source - mean)
        * width[None, :],
        axis=1,
    )
    energy_residual = bottom_flux - top_flux - material_exchange
    energy_scale = np.max(
        np.column_stack((np.abs(top_flux), np.abs(bottom_flux), np.abs(material_exchange))),
        axis=1,
    )
    relative_energy_residual = np.abs(energy_residual)
    positive_energy_scale = energy_scale > 0.0
    relative_energy_residual[positive_energy_scale] /= energy_scale[positive_energy_scale]
    arrays = (
        intensity,
        source,
        mean,
        top_boundary,
        bottom_boundary,
        top_flux,
        bottom_flux,
        source_residual,
        energy_residual,
        relative_energy_residual,
        condition_number,
    )
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ArithmeticError("static slab transfer produced a non-finite result")
    if np.any(intensity < 0.0) or np.any(source < 0.0) or np.any(mean < 0.0):
        raise ArithmeticError("static slab transfer produced a negative radiation field")
    return StaticSlabTransfer(
        frequency_hz=_readonly(frequency),
        depth_edges_cm=_readonly(edges),
        direction_cosine=_readonly(mu),
        angular_weight=_readonly(weight),
        intensity_cell_average=_readonly(intensity),
        source_function=_readonly(source),
        mean_intensity=_readonly(mean),
        top_boundary_intensity=_readonly(top_boundary),
        bottom_boundary_intensity=_readonly(bottom_boundary),
        top_net_flux=_readonly(top_flux),
        bottom_net_flux=_readonly(bottom_flux),
        source_equation_residual=_readonly(source_residual),
        energy_balance_residual=_readonly(energy_residual),
        relative_energy_balance_residual=_readonly(relative_energy_residual),
        lambda_system_condition_number=_readonly(condition_number),
        scattering_linear_solver=scattering_linear_solver,
    )


def isothermal_absorption_top_intensity(
    source_intensity: ArrayLike,
    total_optical_depth: float,
    outward_cosine: ArrayLike,
) -> NDArray[np.float64]:
    """真空边界、等温纯吸收板层的顶部出射解析强度。"""
    source, cosine = np.broadcast_arrays(
        np.asarray(source_intensity, dtype=np.float64),
        np.asarray(outward_cosine, dtype=np.float64),
    )
    depth = float(total_optical_depth)
    if not np.isfinite(depth) or depth < 0.0:
        raise PhysicalDomainError("total_optical_depth must be finite and non-negative")
    if not np.all(np.isfinite(source)) or np.any(source < 0.0):
        raise PhysicalDomainError("source_intensity must be finite and non-negative")
    if not np.all(np.isfinite(cosine)) or np.any(cosine <= 0.0) or np.any(cosine > 1.0):
        raise PhysicalDomainError("outward_cosine must lie in (0, 1]")
    result = source * (-np.expm1(-depth / cosine))
    if not np.all(np.isfinite(result)) or np.any(result < 0.0):
        raise ArithmeticError("analytic absorption intensity became invalid")
    return result


def isothermal_absorption_top_flux(
    source_intensity: ArrayLike, total_optical_depth: float
) -> NDArray[np.float64]:
    """返回 ``2*pi*S*(1/2-E_3(tau))``。"""
    source = np.asarray(source_intensity, dtype=np.float64)
    depth = float(total_optical_depth)
    if not np.isfinite(depth) or depth < 0.0:
        raise PhysicalDomainError("total_optical_depth must be finite and non-negative")
    if not np.all(np.isfinite(source)) or np.any(source < 0.0):
        raise PhysicalDomainError("source_intensity must be finite and non-negative")
    result = 2.0 * np.pi * source * (0.5 - expn(3, depth))
    if not np.all(np.isfinite(result)) or np.any(result < 0.0):
        raise ArithmeticError("analytic absorption flux became invalid")
    return result


def linear_source_top_intensity(
    surface_source_intensity: float,
    source_increase_to_bottom: float,
    total_optical_depth: float,
    outward_cosine: ArrayLike,
) -> NDArray[np.float64]:
    """解析积分 ``S(tau)=S0+DeltaS*tau/tau_tot`` 的顶部强度。"""
    surface = float(surface_source_intensity)
    increase = float(source_increase_to_bottom)
    depth = float(total_optical_depth)
    cosine = np.asarray(outward_cosine, dtype=np.float64)
    if (
        not np.isfinite(surface)
        or not np.isfinite(increase)
        or surface < 0.0
        or surface + increase < 0.0
        or not np.isfinite(depth)
        or depth <= 0.0
    ):
        raise PhysicalDomainError("linear source parameters are outside the physical domain")
    if not np.all(np.isfinite(cosine)) or np.any(cosine <= 0.0) or np.any(cosine > 1.0):
        raise PhysicalDomainError("outward_cosine must lie in (0, 1]")
    attenuation = np.exp(-depth / cosine)
    constant_term = surface * (1.0 - attenuation)
    linear_integral = cosine - (depth + cosine) * attenuation
    result = constant_term + increase * linear_integral / depth
    if not np.all(np.isfinite(result)) or np.any(result < 0.0):
        raise ArithmeticError("linear-source analytic intensity became invalid")
    return result


@dataclass(frozen=True)
class TimeDependentSlabTransfer:
    """固定板层上的时间依赖离散纵标控制结果。"""

    final_intensity: NDArray[np.float64]
    elapsed_time_s: float
    time_steps: int
    maximum_transport_cfl: float
    minimum_intensity: float
    initial_radiation_content: NDArray[np.float64]
    final_radiation_content: NDArray[np.float64]


def _collision_step(
    intensity: NDArray[np.float64],
    extinction: NDArray[np.float64],
    epsilon: NDArray[np.float64],
    thermal_source: NDArray[np.float64],
    weight: NDArray[np.float64],
    duration_s: float,
    propagation_speed_cm_s: float,
) -> NDArray[np.float64]:
    mean = _mean_intensity(intensity, weight)
    mean_attenuation = np.exp(
        -propagation_speed_cm_s * extinction * epsilon * duration_s
    )
    anisotropy_attenuation = np.exp(
        -propagation_speed_cm_s * extinction * duration_s
    )
    next_mean = thermal_source + (mean - thermal_source) * mean_attenuation
    result = next_mean[:, None, :] + (
        intensity - mean[:, None, :]
    ) * anisotropy_attenuation[:, None, :]
    if not np.all(np.isfinite(result)):
        raise ArithmeticError("radiation collision step became non-finite")
    if np.any(result < 0.0):
        raise ArithmeticError("radiation collision step produced negative intensity")
    return result


def _transport_step(
    intensity: NDArray[np.float64],
    mu: NDArray[np.float64],
    top: NDArray[np.float64],
    bottom: NDArray[np.float64],
    cell_width_cm: float,
    duration_s: float,
    propagation_speed_cm_s: float,
    periodic_spatial_boundary: bool,
) -> tuple[NDArray[np.float64], float]:
    result = np.empty_like(intensity)
    maximum_cfl = 0.0
    for angle, cosine in enumerate(mu):
        cfl = propagation_speed_cm_s * abs(float(cosine)) * duration_s / cell_width_cm
        maximum_cfl = max(maximum_cfl, cfl)
        if cfl > 1.0 + 32.0 * np.finfo(np.float64).eps:
            raise PhysicalDomainError("transport CFL exceeds unity")
        current = intensity[:, angle, :]
        if cosine > 0.0:
            if periodic_spatial_boundary:
                upstream = np.roll(current, 1, axis=1)
            else:
                upstream = np.concatenate((top[:, angle, None], current[:, :-1]), axis=1)
        else:
            if periodic_spatial_boundary:
                upstream = np.roll(current, -1, axis=1)
            else:
                upstream = np.concatenate((current[:, 1:], bottom[:, angle, None]), axis=1)
        # 中文：CFL<=1 时迎风步是两个非负强度的凸组合，不需要数值裁剪。
        result[:, angle, :] = (1.0 - cfl) * current + cfl * upstream
    if not np.all(np.isfinite(result)) or np.any(result < 0.0):
        raise ArithmeticError("radiation transport step produced an invalid intensity")
    return result, maximum_cfl


def _radiation_content(
    intensity: NDArray[np.float64],
    weight: NDArray[np.float64],
    cell_width_cm: float,
) -> NDArray[np.float64]:
    mean = _mean_intensity(intensity, weight)
    return np.sum(mean * cell_width_cm, axis=1)


def evolve_time_dependent_slab(
    frequency_hz: ArrayLike,
    depth_edges_cm: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    initial_intensity: ArrayLike,
    extinction_per_cm: ArrayLike,
    thermal_source_intensity: ArrayLike,
    absorption_probability: ArrayLike,
    end_time_s: float,
    *,
    top_incoming_intensity: ArrayLike = 0.0,
    bottom_incoming_intensity: ArrayLike = 0.0,
    periodic_spatial_boundary: bool = False,
    maximum_cfl: float = 0.8,
    propagation_speed_cm_s: float = LIGHT_SPEED_CM_S,
) -> TimeDependentSlabTransfer:
    """用碰撞—迎风—碰撞分裂推进静止介质转移方程。

    碰撞步对各向同性相干散射和热吸收精确；空间步为一阶单调迎风。
    当前不含速度导致的角度/频率耦合项。
    """
    frequency, edges, mu, weight = _validate_grid(
        frequency_hz, depth_edges_cm, direction_cosine, angular_weight
    )
    widths = np.diff(edges)
    if not np.allclose(widths, widths[0], rtol=2.0e-13, atol=0.0):
        raise PhysicalDomainError("time-dependent control currently requires uniform depth cells")
    frequency_points = frequency.size
    depth_points = widths.size
    angle_points = mu.size
    material_shape = (frequency_points, depth_points)
    intensity_shape = (frequency_points, angle_points, depth_points)
    try:
        intensity = np.array(
            np.broadcast_to(np.asarray(initial_intensity, dtype=np.float64), intensity_shape),
            copy=True,
        )
    except ValueError as error:
        raise PhysicalDomainError(f"initial_intensity cannot broadcast to {intensity_shape}") from error
    if not np.all(np.isfinite(intensity)) or np.any(intensity < 0.0):
        raise PhysicalDomainError("initial_intensity must be finite and non-negative")
    extinction = _material_array("extinction_per_cm", extinction_per_cm, material_shape, lower=0.0)
    thermal_source = _material_array(
        "thermal_source_intensity", thermal_source_intensity, material_shape, lower=0.0
    )
    epsilon = _material_array(
        "absorption_probability", absorption_probability, material_shape, lower=0.0, upper=1.0
    )
    top = _boundary_array(
        "top_incoming_intensity", top_incoming_intensity, (frequency_points, angle_points)
    )
    bottom = _boundary_array(
        "bottom_incoming_intensity", bottom_incoming_intensity, (frequency_points, angle_points)
    )
    if periodic_spatial_boundary:
        if np.any(top != 0.0) or np.any(bottom != 0.0):
            raise PhysicalDomainError("periodic spatial controls cannot also specify incident boundaries")
    else:
        _validate_incoming_boundaries(top, bottom, mu)
    end_time = float(end_time_s)
    cfl_limit = float(maximum_cfl)
    speed = float(propagation_speed_cm_s)
    if not np.isfinite(end_time) or end_time <= 0.0:
        raise PhysicalDomainError("end_time_s must be finite and positive")
    if not np.isfinite(cfl_limit) or cfl_limit <= 0.0 or cfl_limit > 1.0:
        raise PhysicalDomainError("maximum_cfl must lie in (0, 1]")
    if not np.isfinite(speed) or speed <= 0.0:
        raise PhysicalDomainError("propagation_speed_cm_s must be finite and positive")

    initial_content = _radiation_content(intensity, weight, float(widths[0]))
    maximum_step = cfl_limit * float(widths[0]) / (speed * float(np.max(np.abs(mu))))
    elapsed = 0.0
    steps = 0
    actual_maximum_cfl = 0.0
    minimum_intensity = float(np.min(intensity))
    while elapsed < end_time:
        duration = min(maximum_step, end_time - elapsed)
        intensity = _collision_step(
            intensity, extinction, epsilon, thermal_source, weight, 0.5 * duration, speed
        )
        intensity, step_cfl = _transport_step(
            intensity,
            mu,
            top,
            bottom,
            float(widths[0]),
            duration,
            speed,
            bool(periodic_spatial_boundary),
        )
        intensity = _collision_step(
            intensity, extinction, epsilon, thermal_source, weight, 0.5 * duration, speed
        )
        elapsed += duration
        steps += 1
        actual_maximum_cfl = max(actual_maximum_cfl, step_cfl)
        minimum_intensity = min(minimum_intensity, float(np.min(intensity)))
    final_content = _radiation_content(intensity, weight, float(widths[0]))
    if not np.isclose(elapsed, end_time, rtol=2.0e-15, atol=0.0):
        raise ArithmeticError("time-dependent transfer did not reach the requested final time")
    return TimeDependentSlabTransfer(
        final_intensity=_readonly(intensity),
        elapsed_time_s=elapsed,
        time_steps=steps,
        maximum_transport_cfl=actual_maximum_cfl,
        minimum_intensity=minimum_intensity,
        initial_radiation_content=_readonly(initial_content),
        final_radiation_content=_readonly(final_content),
    )
