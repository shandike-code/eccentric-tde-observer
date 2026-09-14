"""移动介质辐射的 Lorentz 几何与守恒频率组搬移。

本模块只处理运动学变换，不求解物质能量方程。频率搬移以组积分为守恒量，
因此输入必须是有真实边界的频率控制体；Gauss 求积节点不能冒充频率组。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .atomic_continuum import EV_ERG, H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
from .radiation import PLANCK_ERG_S
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class LorentzRayTransform:
    """实验室射线到共动系射线的完整 Lorentz 变换。"""

    doppler_lab_to_comoving: NDArray[np.float64]
    comoving_direction_cosine: NDArray[np.float64]
    comoving_angular_weight: NDArray[np.float64]
    angular_measure_relative_error: NDArray[np.float64]


@dataclass(frozen=True)
class ThresholdFrequencyGroupGrid:
    """显式对齐 H/He 阈值、带 Doppler 守护带的对数频率组。"""

    edge_hz: NDArray[np.float64]
    centre_hz: NDArray[np.float64]
    width_hz: NDArray[np.float64]
    physical_group_mask: NDArray[np.bool_]
    physical_minimum_energy_ev: float
    physical_maximum_energy_ev: float
    extended_minimum_energy_ev: float
    extended_maximum_energy_ev: float
    groups_per_decade: int
    maximum_velocity_beta: float
    guard_transform_count: int


@dataclass(frozen=True)
class ComovingGroupRadiation:
    """由实验室频率组和射线变换得到的共动角强度与平均强度。"""

    angle_intensity_density: NDArray[np.float64]
    mean_intensity_density: NDArray[np.float64]
    comoving_angular_measure: NDArray[np.float64]


@dataclass(frozen=True)
class FrequencyGroupP1Density:
    """有限体积组平均与归一化一阶频率矩。"""

    mean_density: NDArray[np.float64]
    first_moment_density: NDArray[np.float64]
    limited_group_count: int
    maximum_prelimit_realizability_ratio: float


@dataclass(frozen=True)
class ComovingGroupP1Radiation:
    """P1 Lorentz 搬移后的共动角强度、角平均及一阶频率矩。"""

    angle_mean_density: NDArray[np.float64]
    angle_first_moment_density: NDArray[np.float64]
    mean_intensity_density: NDArray[np.float64]
    mean_intensity_first_moment_density: NDArray[np.float64]
    comoving_angular_measure: NDArray[np.float64]
    limited_group_count: int
    maximum_prelimit_realizability_ratio: float


@dataclass(frozen=True)
class FrequencyGroupP2Density:
    """有限体积组平均与两个归一化 Legendre 频率矩。"""

    mean_density: NDArray[np.float64]
    first_moment_density: NDArray[np.float64]
    second_moment_density: NDArray[np.float64]
    limited_group_count: int
    maximum_prelimit_negativity_ratio: float


@dataclass(frozen=True)
class ComovingGroupP2Radiation:
    """P2 Lorentz 搬移后的共动角强度和三个频率矩。"""

    angle_mean_density: NDArray[np.float64]
    angle_first_moment_density: NDArray[np.float64]
    angle_second_moment_density: NDArray[np.float64]
    mean_intensity_density: NDArray[np.float64]
    mean_intensity_first_moment_density: NDArray[np.float64]
    mean_intensity_second_moment_density: NDArray[np.float64]
    comoving_angular_measure: NDArray[np.float64]
    limited_group_count: int
    maximum_prelimit_negativity_ratio: float


def lorentz_ray_transform(
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    velocity_beta: ArrayLike,
) -> LorentzRayTransform:
    """返回一维平行速度下的 Doppler 因子、像差和共动角测度。

    定义 ``D=nu_0/nu=gamma*(1-beta*mu)``。角测度严格使用
    ``dmu_0=dmu/D^2``；不对有限阶求积权重做事后归一化，而是显式报告
    其对常数角积分的截断误差。
    """
    mu = np.asarray(direction_cosine, dtype=np.float64)
    weight = np.asarray(angular_weight, dtype=np.float64)
    beta = np.asarray(velocity_beta, dtype=np.float64)
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
        raise PhysicalDomainError(
            "direction_cosine and angular_weight must define a positive quadrature on (-1,1)"
        )
    if not np.all(np.isfinite(beta)) or np.any(np.abs(beta) >= 1.0):
        raise PhysicalDomainError("velocity_beta must be finite and subluminal")
    gamma = 1.0 / np.sqrt(1.0 - beta**2)
    reshape = (mu.size,) + (1,) * beta.ndim
    mu_view = mu.reshape(reshape)
    weight_view = weight.reshape(reshape)
    doppler = gamma[None, ...] * (1.0 - mu_view * beta[None, ...])
    denominator = 1.0 - mu_view * beta[None, ...]
    comoving_mu = (mu_view - beta[None, ...]) / denominator
    comoving_weight = weight_view / doppler**2
    measure = 0.5 * np.sum(comoving_weight, axis=0)
    relative_error = np.abs(measure - 1.0)
    arrays = (doppler, comoving_mu, comoving_weight, relative_error)
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ArithmeticError("Lorentz ray transform became non-finite")
    if np.any(doppler <= 0.0) or np.any(np.abs(comoving_mu) >= 1.0):
        raise ArithmeticError("Lorentz ray transform left its physical domain")
    return LorentzRayTransform(
        *(_readonly(np.array(array, copy=True)) for array in arrays)
    )


def threshold_log_frequency_groups(
    minimum_energy_ev: float,
    maximum_energy_ev: float,
    groups_per_decade: int,
    *,
    maximum_velocity_beta: float = 0.0,
    guard_transform_count: int = 2,
) -> ThresholdFrequencyGroupGrid:
    """构造可做守恒 Doppler 搬移的阈值对齐频率控制体。

    守护带只保证物理频带内的指定次数 Lorentz 查询仍落在扩展网格内；
    最外层组本身不是无穷频域边界，不能作为正式积分频带。
    """
    minimum = float(minimum_energy_ev)
    maximum = float(maximum_energy_ev)
    beta = float(maximum_velocity_beta)
    if (
        not np.isfinite(minimum)
        or not np.isfinite(maximum)
        or minimum <= 0.0
        or maximum <= minimum
    ):
        raise PhysicalDomainError(
            "frequency-group energy bounds must be finite, positive and ordered"
        )
    if (
        not isinstance(groups_per_decade, (int, np.integer))
        or isinstance(groups_per_decade, (bool, np.bool_))
        or int(groups_per_decade) < 1
    ):
        raise PhysicalDomainError("groups_per_decade must be a positive integer")
    if not np.isfinite(beta) or beta < 0.0 or beta >= 1.0:
        raise PhysicalDomainError(
            "maximum_velocity_beta must be finite and lie in [0,1)"
        )
    if (
        not isinstance(guard_transform_count, (int, np.integer))
        or isinstance(guard_transform_count, (bool, np.bool_))
        or int(guard_transform_count) < 1
    ):
        raise PhysicalDomainError("guard_transform_count must be a positive integer")
    guard_count = int(guard_transform_count)
    gamma = 1.0 / np.sqrt(1.0 - beta**2)
    maximum_doppler = gamma * (1.0 + beta)
    guard_factor = maximum_doppler**guard_count
    extended_minimum = minimum / guard_factor
    extended_maximum = maximum * guard_factor
    fit_maximum = min(
        fit.maximum_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
    )
    if extended_maximum > fit_maximum:
        raise PhysicalDomainError(
            "Doppler guard band exceeds the common Verner fit domain"
        )

    thresholds = np.array(
        [fit.threshold_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS],
        dtype=np.float64,
    )
    anchors = np.concatenate(
        (
            [extended_minimum, minimum],
            thresholds[
                (thresholds > extended_minimum) & (thresholds < extended_maximum)
            ],
            [maximum, extended_maximum],
        )
    )
    anchors = np.unique(anchors)
    edges: list[float] = [float(anchors[0])]
    for left, right in zip(anchors[:-1], anchors[1:], strict=True):
        count = max(
            1,
            int(np.ceil(int(groups_per_decade) * np.log10(right / left))),
        )
        segment = np.geomspace(left, right, count + 1)
        edges.extend(float(value) for value in segment[1:])
    energy_edges = np.asarray(edges, dtype=np.float64)
    centre_energy = np.sqrt(energy_edges[:-1] * energy_edges[1:])
    physical_mask = (energy_edges[:-1] >= minimum) & (
        energy_edges[1:] <= maximum
    )
    frequency_edges = energy_edges * EV_ERG / PLANCK_ERG_S
    frequency_centre = centre_energy * EV_ERG / PLANCK_ERG_S
    frequency_width = np.diff(frequency_edges)
    arrays = (frequency_edges, frequency_centre, frequency_width)
    if (
        not all(np.all(np.isfinite(array)) for array in arrays)
        or np.any(frequency_width <= 0.0)
        or not np.any(physical_mask)
    ):
        raise ArithmeticError("threshold frequency groups became invalid")
    return ThresholdFrequencyGroupGrid(
        edge_hz=_readonly(frequency_edges),
        centre_hz=_readonly(frequency_centre),
        width_hz=_readonly(frequency_width),
        physical_group_mask=_readonly(physical_mask),
        physical_minimum_energy_ev=minimum,
        physical_maximum_energy_ev=maximum,
        extended_minimum_energy_ev=extended_minimum,
        extended_maximum_energy_ev=extended_maximum,
        groups_per_decade=int(groups_per_decade),
        maximum_velocity_beta=beta,
        guard_transform_count=guard_count,
    )


def _validated_group_inputs(
    group_intensity_density: ArrayLike,
    source_edge_hz: ArrayLike,
    target_edge_hz: ArrayLike,
    doppler_factor: ArrayLike,
    *,
    allow_signed_density: bool = False,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
]:
    intensity = np.asarray(group_intensity_density, dtype=np.float64)
    source_edge = np.asarray(source_edge_hz, dtype=np.float64)
    target_edge = np.asarray(target_edge_hz, dtype=np.float64)
    doppler = np.asarray(doppler_factor, dtype=np.float64)
    if (
        source_edge.ndim != 1
        or source_edge.size < 2
        or not np.all(np.isfinite(source_edge))
        or np.any(source_edge <= 0.0)
        or np.any(np.diff(source_edge) <= 0.0)
    ):
        raise PhysicalDomainError(
            "source_edge_hz must be finite, positive and strictly increasing"
        )
    if (
        target_edge.ndim != 1
        or target_edge.size < 2
        or not np.all(np.isfinite(target_edge))
        or np.any(target_edge <= 0.0)
        or np.any(np.diff(target_edge) <= 0.0)
    ):
        raise PhysicalDomainError(
            "target_edge_hz must be finite, positive and strictly increasing"
        )
    if intensity.ndim < 1 or intensity.shape[0] != source_edge.size - 1:
        raise PhysicalDomainError(
            "group_intensity_density first axis must match the source groups"
        )
    if intensity.shape[1:] != doppler.shape:
        raise PhysicalDomainError(
            "doppler_factor shape must match all non-frequency intensity axes"
        )
    if (
        not np.all(np.isfinite(intensity))
        or (not allow_signed_density and np.any(intensity < 0.0))
        or not np.all(np.isfinite(doppler))
        or np.any(doppler <= 0.0)
    ):
        raise PhysicalDomainError(
            "group intensity and Doppler factors must be finite and non-negative/positive"
        )
    return intensity, source_edge, target_edge, doppler


def _lorentz_remap_group_density(
    group_density: ArrayLike,
    source_edge_hz: ArrayLike,
    target_edge_hz: ArrayLike,
    doppler_factor: ArrayLike,
    *,
    direction: str,
    invariant_frequency_power: float,
    allow_signed_density: bool = False,
) -> NDArray[np.float64]:
    """按 ``q_nu/nu^k`` 不变量守恒搬移一个分段常数频率密度。"""
    density, source_edge, target_edge, doppler = _validated_group_inputs(
        group_density,
        source_edge_hz,
        target_edge_hz,
        doppler_factor,
        allow_signed_density=allow_signed_density,
    )
    if direction not in ("lab_to_comoving", "comoving_to_lab"):
        raise PhysicalDomainError(
            "direction must be 'lab_to_comoving' or 'comoving_to_lab'"
        )
    power = float(invariant_frequency_power)
    if not np.isfinite(power):
        raise PhysicalDomainError("invariant_frequency_power must be finite")
    if (
        np.all(doppler == 1.0)
        and np.array_equal(source_edge, target_edge)
    ):
        return _readonly(np.array(density, copy=True))
    target_width = np.diff(target_edge)
    output = np.empty((target_width.size, *doppler.shape), dtype=np.float64)
    flattened_input = density.reshape(density.shape[0], -1)
    flattened_doppler = doppler.reshape(-1)
    flattened_output = output.reshape(output.shape[0], -1)
    # 中文：按列批量守恒积分，避免完整柱的十万级 Python 列循环。
    element_budget = 2_000_000
    batch_size = max(
        1,
        element_budget // max(source_edge.size - 1, target_width.size),
    )
    source_width = np.diff(source_edge)
    for column_start in range(0, flattened_doppler.size, batch_size):
        column_stop = min(column_start + batch_size, flattened_doppler.size)
        batch_density = flattened_input[:, column_start:column_stop]
        factor = flattened_doppler[column_start:column_stop]
        if direction == "lab_to_comoving":
            lower = target_edge[:-1, None] / factor[None, :]
            upper = target_edge[1:, None] / factor[None, :]
            multiplier = factor ** (power + 1.0)
        else:
            lower = target_edge[:-1, None] * factor[None, :]
            upper = target_edge[1:, None] * factor[None, :]
            multiplier = factor ** (-(power + 1.0))
        integral = _piecewise_constant_overlap_integral_columns(
            batch_density,
            source_edge,
            source_width,
            lower,
            upper,
            allow_signed_density=allow_signed_density,
        )
        flattened_output[:, column_start:column_stop] = (
            multiplier[None, :] * integral / target_width[:, None]
        )
    if not np.all(np.isfinite(output)) or (
        not allow_signed_density and np.any(output < 0.0)
    ):
        raise ArithmeticError("Lorentz group-density remap produced invalid values")
    return _readonly(output)


def _piecewise_constant_overlap_integral_columns(
    density: NDArray[np.float64],
    edge: NDArray[np.float64],
    width: NDArray[np.float64],
    lower: NDArray[np.float64],
    upper: NDArray[np.float64],
    *,
    allow_signed_density: bool = False,
) -> NDArray[np.float64]:
    """按局域交叠顺序批量积分，不依赖源频率切片的累计起点。"""
    if np.any(lower < edge[0]) or np.any(upper > edge[-1]):
        raise PhysicalDomainError(
            "Lorentz frequency query left the supplied source-group domain"
        )
    if np.any(upper <= lower):
        raise PhysicalDomainError("frequency remap intervals must have positive width")
    first = np.searchsorted(edge, lower, side="right") - 1
    last = np.searchsorted(edge, upper, side="left") - 1
    if (
        np.any(first < 0)
        or np.any(first >= density.shape[0])
        or np.any(last < first)
        or np.any(last >= density.shape[0])
    ):
        raise ArithmeticError("local-overlap remap index left the source groups")
    column = np.arange(density.shape[1], dtype=np.intp)[None, :]
    first_upper = np.minimum(upper, edge[first + 1])
    result = density[first, column] * (first_upper - lower)
    maximum_span = int(np.max(last - first))
    for offset in range(1, maximum_span + 1):
        index = first + offset
        active = index <= last
        safe_index = np.where(active, index, first)
        segment_upper = np.minimum(upper, edge[safe_index + 1])
        contribution = density[safe_index, column] * (
            segment_upper - edge[safe_index]
        )
        result += np.where(active, contribution, 0.0)
    if not np.all(np.isfinite(result)) or (
        not allow_signed_density and np.any(result < 0.0)
    ):
        raise ArithmeticError("local-overlap frequency integral became invalid")
    return result


def _piecewise_constant_integral_columns(
    density: NDArray[np.float64],
    edge: NDArray[np.float64],
    width: NDArray[np.float64],
    lower: NDArray[np.float64],
    upper: NDArray[np.float64],
) -> NDArray[np.float64]:
    """批量积分多列分段常数谱，保持每列原有频率累加次序。"""
    if np.any(lower < edge[0]) or np.any(upper > edge[-1]):
        raise PhysicalDomainError(
            "Lorentz frequency query left the supplied source-group domain"
        )
    if np.any(upper <= lower):
        raise PhysicalDomainError("frequency remap intervals must have positive width")
    cumulative = np.concatenate(
        (
            np.zeros((1, density.shape[1]), dtype=np.float64),
            np.cumsum(density * width[:, None], axis=0, dtype=np.float64),
        ),
        axis=0,
    )
    column = np.arange(density.shape[1], dtype=np.intp)[None, :]

    def antiderivative(query: NDArray[np.float64]) -> NDArray[np.float64]:
        index = np.searchsorted(edge, query, side="right") - 1
        at_upper = query == edge[-1]
        safe_index = np.where(at_upper, edge.size - 2, index)
        if np.any(safe_index < 0) or np.any(safe_index >= density.shape[0]):
            raise ArithmeticError("frequency remap index left the source groups")
        return (
            cumulative[safe_index, column]
            + density[safe_index, column]
            * (query - edge[safe_index])
        )

    return antiderivative(upper) - antiderivative(lower)


def _piecewise_constant_integral(
    density: NDArray[np.float64],
    edge: NDArray[np.float64],
    lower: NDArray[np.float64],
    upper: NDArray[np.float64],
) -> NDArray[np.float64]:
    if np.any(lower < edge[0]) or np.any(upper > edge[-1]):
        raise PhysicalDomainError(
            "Lorentz frequency query left the supplied source-group domain"
        )
    if np.any(upper <= lower):
        raise PhysicalDomainError("frequency remap intervals must have positive width")
    cumulative = np.concatenate(
        ([0.0], np.cumsum(density * np.diff(edge), dtype=np.float64))
    )

    def antiderivative(query: NDArray[np.float64]) -> NDArray[np.float64]:
        result = np.empty_like(query)
        at_upper = query == edge[-1]
        result[at_upper] = cumulative[-1]
        interior = ~at_upper
        index = np.searchsorted(edge, query[interior], side="right") - 1
        result[interior] = cumulative[index] + density[index] * (
            query[interior] - edge[index]
        )
        return result

    return antiderivative(upper) - antiderivative(lower)


def limit_nonnegative_frequency_group_p1(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
) -> FrequencyGroupP1Density:
    """保持组积分不变，把 P1 斜率限制在整组非负的可实现域内。

    采用组内坐标 ``x=2(nu-nu_c)/Delta_nu``，表示
    ``q(x)=qbar+3*m*x``。整组非负等价于 ``3*abs(m)<=qbar``；
    这里只缩放一阶矩，不逐点裁剪谱值，也不改变零阶组积分。
    """
    mean = np.asarray(mean_density, dtype=np.float64)
    moment = np.asarray(first_moment_density, dtype=np.float64)
    if (
        mean.shape != moment.shape
        or not np.all(np.isfinite(mean))
        or not np.all(np.isfinite(moment))
        or np.any(mean < 0.0)
    ):
        raise PhysicalDomainError(
            "P1 mean/moment must share a finite shape and the mean must be non-negative"
        )
    # 中文：向可实现域内部移动一个浮点间距，避免边界乘回 3 时越界。
    allowed = np.nextafter(mean / 3.0, 0.0)
    absolute = np.abs(moment)
    violating = absolute > allowed
    limited = np.array(moment, copy=True)
    if np.any(violating):
        sign = np.sign(moment[violating])
        limited[violating] = sign * allowed[violating]
    positive_mean = mean > 0.0
    ratio = np.zeros_like(mean)
    ratio[positive_mean] = 3.0 * absolute[positive_mean] / mean[positive_mean]
    zero_mean_nonzero_moment = (~positive_mean) & (absolute > 0.0)
    maximum_ratio = (
        float("inf")
        if np.any(zero_mean_nonzero_moment)
        else float(np.max(ratio)) if ratio.size else 0.0
    )
    return FrequencyGroupP1Density(
        mean_density=_readonly(np.array(mean, copy=True)),
        first_moment_density=_readonly(limited),
        limited_group_count=int(np.count_nonzero(violating)),
        maximum_prelimit_realizability_ratio=maximum_ratio,
    )


def frequency_group_p1_gauss_node_values(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
) -> NDArray[np.float64]:
    """在两点 Gauss 节点返回可实现 P1 频率密度。"""
    limited = limit_nonnegative_frequency_group_p1(
        mean_density, first_moment_density
    )
    if limited.limited_group_count != 0:
        raise PhysicalDomainError(
            "P1 state is outside the non-negative realizability domain"
        )
    root_three = np.sqrt(3.0)
    node = np.stack(
        (
            limited.mean_density - root_three * limited.first_moment_density,
            limited.mean_density + root_three * limited.first_moment_density,
        ),
        axis=1,
    )
    if not np.all(np.isfinite(node)) or np.any(node < 0.0):
        raise ArithmeticError("realizable P1 Gauss values became invalid")
    return _readonly(node)


def frequency_group_p1_from_gauss_node_values(
    node_density: ArrayLike,
    *,
    enforce_realizability: bool = True,
) -> FrequencyGroupP1Density:
    """把两点 Gauss 值投影为组平均和归一化一阶矩。"""
    node = np.asarray(node_density, dtype=np.float64)
    if (
        node.ndim < 2
        or node.shape[1] != 2
        or not np.all(np.isfinite(node))
        or np.any(node < 0.0)
    ):
        raise PhysicalDomainError(
            "P1 Gauss node density must have shape (group,2,...) and be non-negative"
        )
    mean = 0.5 * (node[:, 0] + node[:, 1])
    moment = (node[:, 1] - node[:, 0]) / (2.0 * np.sqrt(3.0))
    if enforce_realizability:
        return limit_nonnegative_frequency_group_p1(mean, moment)
    return FrequencyGroupP1Density(
        mean_density=_readonly(np.array(mean, copy=True)),
        first_moment_density=_readonly(np.array(moment, copy=True)),
        limited_group_count=0,
        maximum_prelimit_realizability_ratio=float(
            np.max(np.divide(3.0 * np.abs(moment), mean, out=np.zeros_like(mean), where=mean > 0.0))
        ),
    )


def _piecewise_linear_integrals(
    mean_density: NDArray[np.float64],
    first_moment_density: NDArray[np.float64],
    edge: NDArray[np.float64],
    lower: NDArray[np.float64],
    upper: NDArray[np.float64],
    origin: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """精确积分 P1 密度及其相对给定原点的一阶原始矩。"""
    if (
        lower.shape != upper.shape
        or lower.shape != origin.shape
        or np.any(lower < edge[0])
        or np.any(upper > edge[-1])
        or np.any(upper <= lower)
    ):
        raise PhysicalDomainError("P1 remap query left its ordered source domain")
    width = np.diff(edge)
    centre = 0.5 * (edge[:-1] + edge[1:])
    integral = np.empty_like(lower)
    centred = np.empty_like(lower)
    for target in range(lower.size):
        left_query = float(lower[target])
        right_query = float(upper[target])
        reference = float(origin[target])
        group = int(np.searchsorted(edge, left_query, side="right") - 1)
        if left_query == edge[-1]:
            group = edge.size - 2
        total = 0.0
        first = 0.0
        position = left_query
        while position < right_query:
            stop = min(right_query, float(edge[group + 1]))
            normalized_left = 2.0 * (position - centre[group]) / width[group]
            normalized_right = 2.0 * (stop - centre[group]) / width[group]
            q_left = mean_density[group] + 3.0 * first_moment_density[group] * normalized_left
            q_right = mean_density[group] + 3.0 * first_moment_density[group] * normalized_right
            # 中文：正端点的梯形积分避免 Wien 尾中大数相减产生负的次正规数。
            local_zero = (
                0.25
                * width[group]
                * (normalized_right - normalized_left)
                * (q_left + q_right)
            )
            local_first = (
                (centre[group] - reference) * local_zero
                + width[group] ** 2
                / 4.0
                * (
                    0.5
                    * mean_density[group]
                    * (normalized_right**2 - normalized_left**2)
                    + first_moment_density[group]
                    * (normalized_right**3 - normalized_left**3)
                )
            )
            total += local_zero
            first += local_first
            position = stop
            if position < right_query:
                group += 1
        integral[target] = total
        centred[target] = first
    return integral, centred


def lorentz_remap_group_p1_density(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    source_edge_hz: ArrayLike,
    target_edge_hz: ArrayLike,
    doppler_factor: ArrayLike,
    *,
    direction: str,
    invariant_frequency_power: float,
    enforce_realizability: bool = True,
) -> FrequencyGroupP1Density:
    """守恒搬移 P1 零阶/一阶频率矩，并可保持整组非负可实现性。"""
    mean, source_edge, target_edge, doppler = _validated_group_inputs(
        mean_density,
        source_edge_hz,
        target_edge_hz,
        doppler_factor,
    )
    moment = np.asarray(first_moment_density, dtype=np.float64)
    if moment.shape != mean.shape or not np.all(np.isfinite(moment)):
        raise PhysicalDomainError("P1 first moment must match the group mean")
    source_state = limit_nonnegative_frequency_group_p1(mean, moment)
    if source_state.limited_group_count != 0:
        raise PhysicalDomainError("source P1 state is not non-negative realizable")
    if direction not in ("lab_to_comoving", "comoving_to_lab"):
        raise PhysicalDomainError(
            "direction must be 'lab_to_comoving' or 'comoving_to_lab'"
        )
    power = float(invariant_frequency_power)
    if not np.isfinite(power):
        raise PhysicalDomainError("invariant_frequency_power must be finite")
    if np.all(doppler == 1.0) and np.array_equal(source_edge, target_edge):
        return FrequencyGroupP1Density(
            mean_density=_readonly(np.array(mean, copy=True)),
            first_moment_density=_readonly(np.array(moment, copy=True)),
            limited_group_count=0,
            maximum_prelimit_realizability_ratio=source_state.maximum_prelimit_realizability_ratio,
        )
    target_width = np.diff(target_edge)
    target_centre = 0.5 * (target_edge[:-1] + target_edge[1:])
    output_mean = np.empty((target_width.size, *doppler.shape), dtype=np.float64)
    output_moment = np.empty_like(output_mean)
    flattened_mean = mean.reshape(mean.shape[0], -1)
    flattened_moment = moment.reshape(moment.shape[0], -1)
    flattened_doppler = doppler.reshape(-1)
    flattened_output_mean = output_mean.reshape(output_mean.shape[0], -1)
    flattened_output_moment = output_moment.reshape(output_moment.shape[0], -1)
    for column, factor in enumerate(flattened_doppler):
        if direction == "lab_to_comoving":
            lower = target_edge[:-1] / factor
            upper = target_edge[1:] / factor
            origin = target_centre / factor
            multiplier_zero = factor ** (power + 1.0)
            multiplier_first = 2.0 * factor ** (power + 2.0) / target_width**2
        else:
            lower = target_edge[:-1] * factor
            upper = target_edge[1:] * factor
            origin = target_centre * factor
            multiplier_zero = factor ** (-(power + 1.0))
            multiplier_first = 2.0 * factor ** (-(power + 2.0)) / target_width**2
        integral, centred = _piecewise_linear_integrals(
            flattened_mean[:, column],
            flattened_moment[:, column],
            source_edge,
            lower,
            upper,
            origin,
        )
        flattened_output_mean[:, column] = (
            multiplier_zero * integral / target_width
        )
        flattened_output_moment[:, column] = multiplier_first * centred
    if not np.all(np.isfinite(output_mean)) or np.any(output_mean < 0.0):
        minimum_index = np.unravel_index(
            int(np.argmin(output_mean)), output_mean.shape
        )
        raise ArithmeticError(
            "Lorentz P1 mean remap produced invalid values: "
            f"minimum={output_mean[minimum_index]:.17e}, index={minimum_index}"
        )
    if enforce_realizability:
        return limit_nonnegative_frequency_group_p1(output_mean, output_moment)
    return FrequencyGroupP1Density(
        mean_density=_readonly(output_mean),
        first_moment_density=_readonly(output_moment),
        limited_group_count=0,
        maximum_prelimit_realizability_ratio=float(
            np.max(
                np.divide(
                    3.0 * np.abs(output_moment),
                    output_mean,
                    out=np.zeros_like(output_mean),
                    where=output_mean > 0.0,
                )
            )
        ),
    )


def lorentz_remap_group_p1_intensity(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    source_edge_hz: ArrayLike,
    target_edge_hz: ArrayLike,
    doppler_factor: ArrayLike,
    *,
    direction: str,
) -> FrequencyGroupP1Density:
    """按 ``I_nu/nu^3`` 不变量搬移 P1 强度。"""
    return lorentz_remap_group_p1_density(
        mean_density,
        first_moment_density,
        source_edge_hz,
        target_edge_hz,
        doppler_factor,
        direction=direction,
        invariant_frequency_power=3.0,
    )


def lorentz_remap_comoving_group_p1_emissivity_to_lab(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    comoving_edge_hz: ArrayLike,
    lab_edge_hz: ArrayLike,
    doppler_lab_to_comoving: ArrayLike,
) -> FrequencyGroupP1Density:
    """按 ``eta_nu/nu^2`` 不变量搬移 P1 发射率。"""
    return lorentz_remap_group_p1_density(
        mean_density,
        first_moment_density,
        comoving_edge_hz,
        lab_edge_hz,
        doppler_lab_to_comoving,
        direction="comoving_to_lab",
        invariant_frequency_power=2.0,
    )


def lorentz_remap_comoving_group_p1_extinction_to_lab(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    comoving_edge_hz: ArrayLike,
    lab_edge_hz: ArrayLike,
    doppler_lab_to_comoving: ArrayLike,
) -> FrequencyGroupP1Density:
    """按 ``chi_nu*nu`` 不变量搬移 P1 消光。"""
    return lorentz_remap_group_p1_density(
        mean_density,
        first_moment_density,
        comoving_edge_hz,
        lab_edge_hz,
        doppler_lab_to_comoving,
        direction="comoving_to_lab",
        invariant_frequency_power=-1.0,
    )


def lorentz_remap_group_intensity(
    group_intensity_density: ArrayLike,
    source_edge_hz: ArrayLike,
    target_edge_hz: ArrayLike,
    doppler_factor: ArrayLike,
    *,
    direction: str,
) -> NDArray[np.float64]:
    """在实验室系与共动系间正性、组积分守恒地搬移 ``I_nu``。

    ``direction='lab_to_comoving'`` 使用 ``I_0/nu_0^3=I/nu^3``；
    ``direction='comoving_to_lab'`` 执行逆变换。查询越出源频带时直接拒绝，
    不做端点延拓、裁剪或任意 floor。
    """
    return _lorentz_remap_group_density(
        group_intensity_density,
        source_edge_hz,
        target_edge_hz,
        doppler_factor,
        direction=direction,
        invariant_frequency_power=3.0,
    )


def lorentz_remap_signed_group_intensity_perturbation(
    group_intensity_density: ArrayLike,
    source_edge_hz: ArrayLike,
    target_edge_hz: ArrayLike,
    doppler_factor: ArrayLike,
    *,
    direction: str,
) -> NDArray[np.float64]:
    """线性化 ALI 中搬移可带符号的 ``delta I_nu`` 扰动。

    该入口只放宽扰动量的符号；频率边界、Doppler 因子与有限性检查和正式
    正强度路径完全相同，不对物理强度开放负值。
    """
    return _lorentz_remap_group_density(
        group_intensity_density,
        source_edge_hz,
        target_edge_hz,
        doppler_factor,
        direction=direction,
        invariant_frequency_power=3.0,
        allow_signed_density=True,
    )


def lorentz_remap_comoving_group_emissivity_to_lab(
    comoving_emissivity_density: ArrayLike,
    comoving_edge_hz: ArrayLike,
    lab_edge_hz: ArrayLike,
    doppler_lab_to_comoving: ArrayLike,
) -> NDArray[np.float64]:
    """按 ``eta_nu/nu^2`` 不变量把共动系组发射率搬到实验室系。"""
    return _lorentz_remap_group_density(
        comoving_emissivity_density,
        comoving_edge_hz,
        lab_edge_hz,
        doppler_lab_to_comoving,
        direction="comoving_to_lab",
        invariant_frequency_power=2.0,
    )


def lorentz_remap_signed_comoving_group_emissivity_perturbation_to_lab(
    comoving_emissivity_density: ArrayLike,
    comoving_edge_hz: ArrayLike,
    lab_edge_hz: ArrayLike,
    doppler_lab_to_comoving: ArrayLike,
) -> NDArray[np.float64]:
    """按 ``delta eta_nu/nu^2`` 不变量搬移可带符号的发射率扰动。"""
    return _lorentz_remap_group_density(
        comoving_emissivity_density,
        comoving_edge_hz,
        lab_edge_hz,
        doppler_lab_to_comoving,
        direction="comoving_to_lab",
        invariant_frequency_power=2.0,
        allow_signed_density=True,
    )


def lorentz_remap_comoving_group_extinction_to_lab(
    comoving_extinction_per_cm: ArrayLike,
    comoving_edge_hz: ArrayLike,
    lab_edge_hz: ArrayLike,
    doppler_lab_to_comoving: ArrayLike,
) -> NDArray[np.float64]:
    """按 ``chi_nu*nu`` 不变量把共动系组消光搬到实验室系。"""
    return _lorentz_remap_group_density(
        comoving_extinction_per_cm,
        comoving_edge_hz,
        lab_edge_hz,
        doppler_lab_to_comoving,
        direction="comoving_to_lab",
        invariant_frequency_power=-1.0,
    )


def comoving_group_radiation(
    lab_group_intensity_density: ArrayLike,
    lab_edge_hz: ArrayLike,
    comoving_edge_hz: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    velocity_beta: ArrayLike,
) -> ComovingGroupRadiation:
    """把实验室频率--角度强度守恒搬移后计算共动 ``J_nu``。"""
    transform = lorentz_ray_transform(
        direction_cosine, angular_weight, velocity_beta
    )
    intensity = np.asarray(lab_group_intensity_density, dtype=np.float64)
    if intensity.ndim < 2 or intensity.shape[1:] != transform.doppler_lab_to_comoving.shape:
        raise PhysicalDomainError(
            "lab intensity non-frequency axes must match (angle, velocity-grid)"
        )
    comoving_angle = lorentz_remap_group_intensity(
        intensity,
        lab_edge_hz,
        comoving_edge_hz,
        transform.doppler_lab_to_comoving,
        direction="lab_to_comoving",
    )
    mean = 0.5 * np.sum(
        transform.comoving_angular_weight[None, ...] * comoving_angle,
        axis=1,
    )
    measure = 0.5 * np.sum(transform.comoving_angular_weight, axis=0)
    if not np.all(np.isfinite(mean)) or np.any(mean < 0.0):
        raise ArithmeticError("comoving group mean intensity became invalid")
    return ComovingGroupRadiation(
        angle_intensity_density=comoving_angle,
        mean_intensity_density=_readonly(mean),
        comoving_angular_measure=_readonly(np.array(measure, copy=True)),
    )


def comoving_group_p1_radiation(
    lab_group_mean_intensity_density: ArrayLike,
    lab_group_first_moment_intensity_density: ArrayLike,
    lab_edge_hz: ArrayLike,
    comoving_edge_hz: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    velocity_beta: ArrayLike,
) -> ComovingGroupP1Radiation:
    """守恒搬移实验室系 P1 强度并计算共动系角平均的两个频率矩。"""
    transform = lorentz_ray_transform(
        direction_cosine, angular_weight, velocity_beta
    )
    mean = np.asarray(lab_group_mean_intensity_density, dtype=np.float64)
    moment = np.asarray(
        lab_group_first_moment_intensity_density, dtype=np.float64
    )
    if (
        mean.ndim < 2
        or moment.shape != mean.shape
        or mean.shape[1:] != transform.doppler_lab_to_comoving.shape
    ):
        raise PhysicalDomainError(
            "lab P1 intensity axes must match (frequency,angle,velocity-grid)"
        )
    remapped = lorentz_remap_group_p1_intensity(
        mean,
        moment,
        lab_edge_hz,
        comoving_edge_hz,
        transform.doppler_lab_to_comoving,
        direction="lab_to_comoving",
    )
    angular_mean = 0.5 * np.sum(
        transform.comoving_angular_weight[None, ...]
        * remapped.mean_density,
        axis=1,
    )
    angular_moment = 0.5 * np.sum(
        transform.comoving_angular_weight[None, ...]
        * remapped.first_moment_density,
        axis=1,
    )
    limited_mean = limit_nonnegative_frequency_group_p1(
        angular_mean, angular_moment
    )
    measure = 0.5 * np.sum(transform.comoving_angular_weight, axis=0)
    return ComovingGroupP1Radiation(
        angle_mean_density=remapped.mean_density,
        angle_first_moment_density=remapped.first_moment_density,
        mean_intensity_density=limited_mean.mean_density,
        mean_intensity_first_moment_density=limited_mean.first_moment_density,
        comoving_angular_measure=_readonly(np.array(measure, copy=True)),
        limited_group_count=(
            remapped.limited_group_count + limited_mean.limited_group_count
        ),
        maximum_prelimit_realizability_ratio=max(
            remapped.maximum_prelimit_realizability_ratio,
            limited_mean.maximum_prelimit_realizability_ratio,
        ),
    )


def _frequency_group_p2_minimum(
    mean_density: NDArray[np.float64],
    first_moment_density: NDArray[np.float64],
    second_moment_density: NDArray[np.float64],
) -> NDArray[np.float64]:
    """返回二次 Legendre 重构在闭区间 ``[-1,1]`` 上的解析最小值。"""
    mean = np.asarray(mean_density, dtype=np.float64)
    first_ratio = np.zeros_like(mean)
    second_ratio = np.zeros_like(mean)
    positive = mean > 0.0
    first_ratio[positive] = first_moment_density[positive] / mean[positive]
    second_ratio[positive] = second_moment_density[positive] / mean[positive]
    normalized = _frequency_group_p2_normalized_minimum(
        first_ratio, second_ratio
    )
    minimum = mean * normalized
    zero_mean_nonzero = (~positive) & (
        (first_moment_density != 0.0) | (second_moment_density != 0.0)
    )
    minimum[zero_mean_nonzero] = -np.inf
    return minimum


def _frequency_group_p2_normalized_minimum(
    first_ratio: NDArray[np.float64],
    second_ratio: NDArray[np.float64],
) -> NDArray[np.float64]:
    """以组平均归一化后求最小值，避免 Wien 尾次正规数的相消下溢。"""
    quadratic = 7.5 * second_ratio
    linear = 3.0 * first_ratio
    constant = 1.0 - 2.5 * second_ratio
    minimum = np.minimum(
        quadratic - linear + constant,
        quadratic + linear + constant,
    )
    vertex = np.zeros_like(first_ratio)
    positive_quadratic = quadratic > 0.0
    vertex[positive_quadratic] = (
        -linear[positive_quadratic] / (2.0 * quadratic[positive_quadratic])
    )
    interior_vertex = positive_quadratic & (np.abs(vertex) < 1.0)
    vertex_value = (
        quadratic * vertex**2 + linear * vertex + constant
    )
    return np.where(
        interior_vertex,
        np.minimum(minimum, vertex_value),
        minimum,
    )


def limit_nonnegative_frequency_group_p2(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    second_moment_density: ArrayLike,
) -> FrequencyGroupP2Density:
    """保持组平均不变，统一缩放 P2 高阶矩直到整组非负。"""
    mean = np.asarray(mean_density, dtype=np.float64)
    first = np.asarray(first_moment_density, dtype=np.float64)
    second = np.asarray(second_moment_density, dtype=np.float64)
    if (
        mean.shape != first.shape
        or mean.shape != second.shape
        or not np.all(np.isfinite(mean))
        or not np.all(np.isfinite(first))
        or not np.all(np.isfinite(second))
        or np.any(mean < 0.0)
    ):
        raise PhysicalDomainError(
            "P2 mean and moments must share a finite shape with non-negative mean"
        )
    positive_mean = mean > 0.0
    normalized_first = np.zeros_like(mean)
    normalized_second = np.zeros_like(mean)
    normalized_first[positive_mean] = first[positive_mean] / mean[positive_mean]
    normalized_second[positive_mean] = second[positive_mean] / mean[positive_mean]
    normalized_minimum = _frequency_group_p2_normalized_minimum(
        normalized_first, normalized_second
    )
    zero_mean_nonzero = (~positive_mean) & ((first != 0.0) | (second != 0.0))
    violating = (positive_mean & (normalized_minimum < 0.0)) | zero_mean_nonzero
    limited_first = np.array(first, copy=True)
    limited_second = np.array(second, copy=True)
    positive_violation = positive_mean & (normalized_minimum < 0.0)
    if np.any(positive_violation):
        theta = 1.0 / (1.0 - normalized_minimum[positive_violation])
        # 中文：向可实现域内退一个浮点间距，不设置物理强度 floor。
        theta = np.nextafter(theta, 0.0)
        limited_first[positive_violation] = mean[positive_violation] * (
            normalized_first[positive_violation] * theta
        )
        limited_second[positive_violation] = mean[positive_violation] * (
            normalized_second[positive_violation] * theta
        )
    limited_first[zero_mean_nonzero] = 0.0
    limited_second[zero_mean_nonzero] = 0.0
    for _ in range(8):
        limited_first_ratio = np.zeros_like(mean)
        limited_second_ratio = np.zeros_like(mean)
        limited_first_ratio[positive_mean] = (
            limited_first[positive_mean] / mean[positive_mean]
        )
        limited_second_ratio[positive_mean] = (
            limited_second[positive_mean] / mean[positive_mean]
        )
        limited_normalized_minimum = _frequency_group_p2_normalized_minimum(
            limited_first_ratio, limited_second_ratio
        )
        roundoff_negative = positive_mean & (limited_normalized_minimum < 0.0)
        if not np.any(roundoff_negative):
            break
        selected_mean = mean[roundoff_negative]
        selected_first = limited_first[roundoff_negative]
        selected_second = limited_second[roundoff_negative]
        # 中文：安全退量由两个矩的浮点间距推导，不设置强度或矩的物理 floor。
        representability_margin = 4.0 * (
            3.0 * np.abs(np.spacing(selected_first)) / selected_mean
            + 5.0 * np.abs(np.spacing(selected_second)) / selected_mean
            + 16.0 * np.finfo(np.float64).eps
        )
        roundoff_theta = (
            1.0 / (1.0 - limited_normalized_minimum[roundoff_negative])
        ) * (1.0 - representability_margin)
        nonpositive_theta = roundoff_theta <= 0.0
        roundoff_theta[nonpositive_theta] = 0.0
        roundoff_theta = np.nextafter(roundoff_theta, 0.0)
        limited_first[roundoff_negative] = selected_first * roundoff_theta
        limited_second[roundoff_negative] = selected_second * roundoff_theta
    if np.any(roundoff_negative):
        worst = float(np.min(limited_normalized_minimum[roundoff_negative]))
        raise ArithmeticError(
            "P2 realizability limiter failed at floating precision: "
            f"minimum normalized reconstruction={worst:.17e}"
        )
    negativity = np.zeros_like(mean)
    negativity[positive_mean] = np.maximum(
        0.0, -normalized_minimum[positive_mean]
    )
    maximum_ratio = (
        float("inf")
        if np.any(zero_mean_nonzero)
        else float(np.max(negativity)) if negativity.size else 0.0
    )
    return FrequencyGroupP2Density(
        mean_density=_readonly(np.array(mean, copy=True)),
        first_moment_density=_readonly(limited_first),
        second_moment_density=_readonly(limited_second),
        limited_group_count=int(np.count_nonzero(violating)),
        maximum_prelimit_negativity_ratio=maximum_ratio,
    )


def frequency_group_p2_values_at_normalized_nodes(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    second_moment_density: ArrayLike,
    normalized_nodes: ArrayLike,
) -> NDArray[np.float64]:
    """在给定组内归一化坐标上求值整组非负的 P2 密度。"""
    state = limit_nonnegative_frequency_group_p2(
        mean_density, first_moment_density, second_moment_density
    )
    if state.limited_group_count != 0:
        raise PhysicalDomainError("P2 state is outside the realizability domain")
    node = np.asarray(normalized_nodes, dtype=np.float64)
    if (
        node.ndim != 1
        or node.size < 1
        or not np.all(np.isfinite(node))
        or np.any(node < -1.0)
        or np.any(node > 1.0)
    ):
        raise PhysicalDomainError("normalized P2 nodes must lie in [-1,1]")
    view = (1, node.size) + (1,) * (state.mean_density.ndim - 1)
    x = node.reshape(view)
    positive = state.mean_density > 0.0
    first_ratio = np.zeros_like(state.mean_density)
    second_ratio = np.zeros_like(state.mean_density)
    first_ratio[positive] = (
        state.first_moment_density[positive] / state.mean_density[positive]
    )
    second_ratio[positive] = (
        state.second_moment_density[positive] / state.mean_density[positive]
    )
    normalized_values = (
        1.0
        + 3.0 * first_ratio[:, None, ...] * x
        + 2.5 * second_ratio[:, None, ...] * (3.0 * x**2 - 1.0)
    )
    values = state.mean_density[:, None, ...] * normalized_values
    if not np.all(np.isfinite(values)) or np.any(values < 0.0):
        raise ArithmeticError("realizable P2 node values became invalid")
    return _readonly(values)


def frequency_group_p2_gauss_node_values(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    second_moment_density: ArrayLike,
) -> NDArray[np.float64]:
    """在三点 Gauss--Legendre 节点返回 P2 频率密度。"""
    root = np.sqrt(3.0 / 5.0)
    return frequency_group_p2_values_at_normalized_nodes(
        mean_density,
        first_moment_density,
        second_moment_density,
        np.array([-root, 0.0, root]),
    )


def frequency_group_p2_from_gauss_node_values(
    node_density: ArrayLike,
    *,
    enforce_realizability: bool = True,
) -> FrequencyGroupP2Density:
    """把三点 Gauss 值投影成组平均和两个 Legendre 矩。"""
    node = np.asarray(node_density, dtype=np.float64)
    if (
        node.ndim < 2
        or node.shape[1] != 3
        or not np.all(np.isfinite(node))
        or np.any(node < 0.0)
    ):
        raise PhysicalDomainError(
            "P2 Gauss density must have shape (group,3,...) and be non-negative"
        )
    x = np.array([-np.sqrt(3.0 / 5.0), 0.0, np.sqrt(3.0 / 5.0)])
    weight = np.array([5.0 / 18.0, 4.0 / 9.0, 5.0 / 18.0])
    shape = (1, 3) + (1,) * (node.ndim - 2)
    x_view = x.reshape(shape)
    weight_view = weight.reshape(shape)
    mean = np.sum(weight_view * node, axis=1)
    first = np.sum(weight_view * node * x_view, axis=1)
    second = np.sum(
        weight_view * node * 0.5 * (3.0 * x_view**2 - 1.0), axis=1
    )
    if enforce_realizability:
        return limit_nonnegative_frequency_group_p2(mean, first, second)
    return FrequencyGroupP2Density(
        mean_density=_readonly(mean),
        first_moment_density=_readonly(first),
        second_moment_density=_readonly(second),
        limited_group_count=0,
        maximum_prelimit_negativity_ratio=0.0,
    )


def _piecewise_quadratic_integrals(
    mean_density: NDArray[np.float64],
    first_moment_density: NDArray[np.float64],
    second_moment_density: NDArray[np.float64],
    edge: NDArray[np.float64],
    lower: NDArray[np.float64],
    upper: NDArray[np.float64],
    origin: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """精确正权积分 P2 密度及相对目标原点的前两个原始矩。"""
    if (
        lower.shape != upper.shape
        or lower.shape != origin.shape
        or np.any(lower < edge[0])
        or np.any(upper > edge[-1])
        or np.any(upper <= lower)
    ):
        raise PhysicalDomainError("P2 remap query left its source domain")
    width = np.diff(edge)
    centre = 0.5 * (edge[:-1] + edge[1:])
    base_node = np.array(
        [-np.sqrt(3.0 / 5.0), 0.0, np.sqrt(3.0 / 5.0)]
    )
    base_weight = np.array([5.0 / 9.0, 8.0 / 9.0, 5.0 / 9.0])
    zero = np.empty_like(lower)
    first = np.empty_like(lower)
    second = np.empty_like(lower)
    for target in range(lower.size):
        left_query = float(lower[target])
        right_query = float(upper[target])
        reference = float(origin[target])
        group = int(np.searchsorted(edge, left_query, side="right") - 1)
        if left_query == edge[-1]:
            group = edge.size - 2
        total_zero = 0.0
        total_first = 0.0
        total_second = 0.0
        position = left_query
        while position < right_query:
            stop = min(right_query, float(edge[group + 1]))
            x_left = 2.0 * (position - centre[group]) / width[group]
            x_right = 2.0 * (stop - centre[group]) / width[group]
            x_mid = 0.5 * (x_left + x_right)
            x_half = 0.5 * (x_right - x_left)
            x = x_mid + x_half * base_node
            group_mean = mean_density[group]
            if group_mean > 0.0:
                first_ratio = first_moment_density[group] / group_mean
                second_ratio = second_moment_density[group] / group_mean
                q = group_mean * (
                    1.0
                    + 3.0 * first_ratio * x
                    + 2.5 * second_ratio * (3.0 * x**2 - 1.0)
                )
            else:
                q = np.zeros_like(x)
            if np.any(q < 0.0):
                raise ArithmeticError("realizable P2 remap sampled a negative density")
            frequency = centre[group] + 0.5 * width[group] * x
            displacement = frequency - reference
            node_weight = 0.5 * width[group] * x_half * base_weight
            local_zero = float(np.sum(node_weight * q))
            total_zero += local_zero
            total_first += float(np.sum(node_weight * displacement * q))
            total_second += float(
                np.sum(node_weight * displacement**2 * q)
            )
            position = stop
            if position < right_query:
                group += 1
        zero[target] = total_zero
        first[target] = total_first
        second[target] = total_second
    return zero, first, second


def lorentz_remap_group_p2_density(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    second_moment_density: ArrayLike,
    source_edge_hz: ArrayLike,
    target_edge_hz: ArrayLike,
    doppler_factor: ArrayLike,
    *,
    direction: str,
    invariant_frequency_power: float,
    enforce_realizability: bool = True,
) -> FrequencyGroupP2Density:
    """守恒搬移 P2 的零阶、一次和二次 Legendre 频率矩。"""
    mean, source_edge, target_edge, doppler = _validated_group_inputs(
        mean_density,
        source_edge_hz,
        target_edge_hz,
        doppler_factor,
    )
    first = np.asarray(first_moment_density, dtype=np.float64)
    second = np.asarray(second_moment_density, dtype=np.float64)
    if (
        first.shape != mean.shape
        or second.shape != mean.shape
        or not np.all(np.isfinite(first))
        or not np.all(np.isfinite(second))
    ):
        raise PhysicalDomainError("P2 moments must match the group mean")
    source_state = limit_nonnegative_frequency_group_p2(mean, first, second)
    if source_state.limited_group_count != 0:
        raise PhysicalDomainError("source P2 state is not realizable")
    if direction not in ("lab_to_comoving", "comoving_to_lab"):
        raise PhysicalDomainError("invalid P2 Lorentz remap direction")
    power = float(invariant_frequency_power)
    if not np.isfinite(power):
        raise PhysicalDomainError("invariant_frequency_power must be finite")
    if np.all(doppler == 1.0) and np.array_equal(source_edge, target_edge):
        return FrequencyGroupP2Density(
            mean_density=_readonly(np.array(mean, copy=True)),
            first_moment_density=_readonly(np.array(first, copy=True)),
            second_moment_density=_readonly(np.array(second, copy=True)),
            limited_group_count=0,
            maximum_prelimit_negativity_ratio=(
                source_state.maximum_prelimit_negativity_ratio
            ),
        )
    target_width = np.diff(target_edge)
    target_centre = 0.5 * (target_edge[:-1] + target_edge[1:])
    output_shape = (target_width.size, *doppler.shape)
    output_mean = np.empty(output_shape, dtype=np.float64)
    output_first = np.empty(output_shape, dtype=np.float64)
    output_second = np.empty(output_shape, dtype=np.float64)
    flat_mean = mean.reshape(mean.shape[0], -1)
    flat_first = first.reshape(first.shape[0], -1)
    flat_second = second.reshape(second.shape[0], -1)
    flat_doppler = doppler.reshape(-1)
    flat_output_mean = output_mean.reshape(output_mean.shape[0], -1)
    flat_output_first = output_first.reshape(output_first.shape[0], -1)
    flat_output_second = output_second.reshape(output_second.shape[0], -1)
    for column, factor in enumerate(flat_doppler):
        if direction == "lab_to_comoving":
            lower = target_edge[:-1] / factor
            upper = target_edge[1:] / factor
            origin = target_centre / factor
            multiplier_zero = factor ** (power + 1.0)
            multiplier_first = factor ** (power + 2.0)
            multiplier_second = factor ** (power + 3.0)
        else:
            lower = target_edge[:-1] * factor
            upper = target_edge[1:] * factor
            origin = target_centre * factor
            multiplier_zero = factor ** (-(power + 1.0))
            multiplier_first = factor ** (-(power + 2.0))
            multiplier_second = factor ** (-(power + 3.0))
        zero, centred_first, centred_second = _piecewise_quadratic_integrals(
            flat_mean[:, column],
            flat_first[:, column],
            flat_second[:, column],
            source_edge,
            lower,
            upper,
            origin,
        )
        remapped_mean = multiplier_zero * zero / target_width
        flat_output_mean[:, column] = remapped_mean
        flat_output_first[:, column] = (
            2.0 * multiplier_first * centred_first / target_width**2
        )
        flat_output_second[:, column] = (
            6.0 * multiplier_second * centred_second / target_width**3
            - 0.5 * remapped_mean
        )
    if not np.all(np.isfinite(output_mean)) or np.any(output_mean < 0.0):
        raise ArithmeticError("Lorentz P2 mean remap produced invalid values")
    if enforce_realizability:
        return limit_nonnegative_frequency_group_p2(
            output_mean, output_first, output_second
        )
    return FrequencyGroupP2Density(
        mean_density=_readonly(output_mean),
        first_moment_density=_readonly(output_first),
        second_moment_density=_readonly(output_second),
        limited_group_count=0,
        maximum_prelimit_negativity_ratio=0.0,
    )


def lorentz_remap_group_p2_intensity(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    second_moment_density: ArrayLike,
    source_edge_hz: ArrayLike,
    target_edge_hz: ArrayLike,
    doppler_factor: ArrayLike,
    *,
    direction: str,
) -> FrequencyGroupP2Density:
    """按 ``I_nu/nu^3`` 不变量搬移 P2 强度。"""
    return lorentz_remap_group_p2_density(
        mean_density,
        first_moment_density,
        second_moment_density,
        source_edge_hz,
        target_edge_hz,
        doppler_factor,
        direction=direction,
        invariant_frequency_power=3.0,
    )


def lorentz_remap_comoving_group_p2_emissivity_to_lab(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    second_moment_density: ArrayLike,
    comoving_edge_hz: ArrayLike,
    lab_edge_hz: ArrayLike,
    doppler_lab_to_comoving: ArrayLike,
) -> FrequencyGroupP2Density:
    """按 ``eta_nu/nu^2`` 不变量搬移 P2 发射率。"""
    return lorentz_remap_group_p2_density(
        mean_density,
        first_moment_density,
        second_moment_density,
        comoving_edge_hz,
        lab_edge_hz,
        doppler_lab_to_comoving,
        direction="comoving_to_lab",
        invariant_frequency_power=2.0,
    )


def lorentz_remap_comoving_group_p2_extinction_to_lab(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    second_moment_density: ArrayLike,
    comoving_edge_hz: ArrayLike,
    lab_edge_hz: ArrayLike,
    doppler_lab_to_comoving: ArrayLike,
) -> FrequencyGroupP2Density:
    """按 ``chi_nu*nu`` 不变量搬移 P2 消光。"""
    return lorentz_remap_group_p2_density(
        mean_density,
        first_moment_density,
        second_moment_density,
        comoving_edge_hz,
        lab_edge_hz,
        doppler_lab_to_comoving,
        direction="comoving_to_lab",
        invariant_frequency_power=-1.0,
    )


def comoving_group_p2_radiation(
    lab_group_mean_intensity_density: ArrayLike,
    lab_group_first_moment_intensity_density: ArrayLike,
    lab_group_second_moment_intensity_density: ArrayLike,
    lab_edge_hz: ArrayLike,
    comoving_edge_hz: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    velocity_beta: ArrayLike,
) -> ComovingGroupP2Radiation:
    """守恒搬移实验室 P2 强度并计算共动角平均的三个频率矩。"""
    transform = lorentz_ray_transform(
        direction_cosine, angular_weight, velocity_beta
    )
    mean = np.asarray(lab_group_mean_intensity_density, dtype=np.float64)
    first = np.asarray(
        lab_group_first_moment_intensity_density, dtype=np.float64
    )
    second = np.asarray(
        lab_group_second_moment_intensity_density, dtype=np.float64
    )
    if (
        mean.ndim < 2
        or first.shape != mean.shape
        or second.shape != mean.shape
        or mean.shape[1:] != transform.doppler_lab_to_comoving.shape
    ):
        raise PhysicalDomainError(
            "lab P2 intensity axes must match frequency, angle and velocity grid"
        )
    remapped = lorentz_remap_group_p2_intensity(
        mean,
        first,
        second,
        lab_edge_hz,
        comoving_edge_hz,
        transform.doppler_lab_to_comoving,
        direction="lab_to_comoving",
    )
    angular_mean = 0.5 * np.sum(
        transform.comoving_angular_weight[None, ...] * remapped.mean_density,
        axis=1,
    )
    angular_first = 0.5 * np.sum(
        transform.comoving_angular_weight[None, ...]
        * remapped.first_moment_density,
        axis=1,
    )
    angular_second = 0.5 * np.sum(
        transform.comoving_angular_weight[None, ...]
        * remapped.second_moment_density,
        axis=1,
    )
    limited_mean = limit_nonnegative_frequency_group_p2(
        angular_mean, angular_first, angular_second
    )
    measure = 0.5 * np.sum(transform.comoving_angular_weight, axis=0)
    return ComovingGroupP2Radiation(
        angle_mean_density=remapped.mean_density,
        angle_first_moment_density=remapped.first_moment_density,
        angle_second_moment_density=remapped.second_moment_density,
        mean_intensity_density=limited_mean.mean_density,
        mean_intensity_first_moment_density=limited_mean.first_moment_density,
        mean_intensity_second_moment_density=limited_mean.second_moment_density,
        comoving_angular_measure=_readonly(np.array(measure, copy=True)),
        limited_group_count=(
            remapped.limited_group_count + limited_mean.limited_group_count
        ),
        maximum_prelimit_negativity_ratio=max(
            remapped.maximum_prelimit_negativity_ratio,
            limited_mean.maximum_prelimit_negativity_ratio,
        ),
    )
