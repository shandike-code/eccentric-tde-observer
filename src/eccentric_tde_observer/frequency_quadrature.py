"""跨 H/He 离化边的显式正权频率求积。

普通梯形网格适合画连续谱，但跨越束缚--自由阈值时，能量矩和光子数矩的
收敛速度可以完全不同。本模块在每个离化边显式分段，在对数能量面板内用
Gauss--Legendre 求积；节点不落在跃迁边上，左右极限由相邻分段分别承担。
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
class ThresholdLogFrequencyQuadrature:
    """阈值分段的复合对数 Gauss--Legendre 频率求积。"""

    photon_energy_ev: NDArray[np.float64]
    energy_weight_ev: NDArray[np.float64]
    frequency_hz: NDArray[np.float64]
    frequency_weight_hz: NDArray[np.float64]
    threshold_segment_edges_ev: NDArray[np.float64]
    logarithmic_panel_edges_ev: NDArray[np.float64]
    panels_per_decade: int
    order_per_panel: int


@dataclass(frozen=True)
class ThresholdExcessFrequencyQuadrature:
    """按超阈值能量聚点的复合 Gauss--Legendre 频率求积。"""

    photon_energy_ev: NDArray[np.float64]
    energy_weight_ev: NDArray[np.float64]
    frequency_hz: NDArray[np.float64]
    frequency_weight_hz: NDArray[np.float64]
    threshold_segment_edges_ev: NDArray[np.float64]
    transformed_panel_edges_ev: NDArray[np.float64]
    threshold_scale_ev: float
    panels_per_transformed_decade: int
    order_per_panel: int


def threshold_excess_frequency_group_edges_ev(
    minimum_energy_ev: float,
    maximum_energy_ev: float,
    groups_per_transformed_decade: int,
    *,
    threshold_scale_ev: float,
) -> NDArray[np.float64]:
    """返回按超阈值坐标均匀分面、并显式包含 H/He 离化边的物理组边界。

    该接口复用同一阈值超额面板定义，但只返回有限体积边界；两点 Gauss
    节点仅用于构造面板，节点本身不进入频率组输运。
    """
    quadrature = threshold_excess_gauss_legendre_quadrature(
        minimum_energy_ev,
        maximum_energy_ev,
        groups_per_transformed_decade,
        threshold_scale_ev=threshold_scale_ev,
        order_per_panel=2,
    )
    edge = np.array(quadrature.transformed_panel_edges_ev, copy=True)
    edge[0] = float(minimum_energy_ev)
    edge[-1] = float(maximum_energy_ev)
    for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS:
        threshold = fit.threshold_energy_ev
        if edge[0] < threshold < edge[-1]:
            index = int(np.argmin(np.abs(edge - threshold)))
            if not np.isclose(edge[index], threshold, rtol=2.0e-13, atol=0.0):
                raise ArithmeticError("threshold-excess panel lost an ionization edge")
            # 中文：有限体积边界使用表中精确阈值，避免频率换算后落到错误一侧。
            edge[index] = threshold
    if np.any(np.diff(edge) <= 0.0):
        raise ArithmeticError("threshold-excess group edges lost monotonicity")
    return _readonly(edge)


def threshold_log_gauss_legendre_quadrature(
    minimum_energy_ev: float,
    maximum_energy_ev: float,
    panels_per_decade: int,
    *,
    order_per_panel: int = 8,
) -> ThresholdLogFrequencyQuadrature:
    """构造离化边分段、对数面板内正权的频率求积。"""
    minimum = float(minimum_energy_ev)
    maximum = float(maximum_energy_ev)
    if (
        not np.isfinite(minimum)
        or not np.isfinite(maximum)
        or minimum <= 0.0
        or maximum <= minimum
    ):
        raise PhysicalDomainError(
            "frequency quadrature energy bounds must be finite, positive and ordered"
        )
    if (
        not isinstance(panels_per_decade, (int, np.integer))
        or isinstance(panels_per_decade, (bool, np.bool_))
        or int(panels_per_decade) < 1
    ):
        raise PhysicalDomainError("panels_per_decade must be a positive integer")
    if (
        not isinstance(order_per_panel, (int, np.integer))
        or isinstance(order_per_panel, (bool, np.bool_))
        or int(order_per_panel) < 2
    ):
        raise PhysicalDomainError("order_per_panel must be an integer of at least two")
    maximum_fit_energy = min(
        fit.maximum_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
    )
    if maximum > maximum_fit_energy:
        raise PhysicalDomainError(
            "frequency quadrature exceeds the common Verner fit domain"
        )

    thresholds = np.array(
        [fit.threshold_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS],
        dtype=np.float64,
    )
    active = thresholds[(thresholds > minimum) & (thresholds < maximum)]
    segment_edges = np.concatenate(([minimum], active, [maximum]))
    legendre_node, legendre_weight = np.polynomial.legendre.leggauss(
        int(order_per_panel)
    )
    nodes: list[np.ndarray] = []
    weights: list[np.ndarray] = []
    panel_edges: list[float] = [minimum]
    for left, right in zip(segment_edges[:-1], segment_edges[1:], strict=True):
        decades = np.log10(right / left)
        panel_count = max(1, int(np.ceil(int(panels_per_decade) * decades)))
        log_edges = np.linspace(np.log(left), np.log(right), panel_count + 1)
        for log_left, log_right in zip(
            log_edges[:-1], log_edges[1:], strict=True
        ):
            centre = 0.5 * (log_left + log_right)
            half_width = 0.5 * (log_right - log_left)
            log_energy = centre + half_width * legendre_node
            energy = np.exp(log_energy)
            # 中文：dE=E d(log E)，所以正权需包含当前 Gauss 节点的 E。
            energy_weight = half_width * legendre_weight * energy
            nodes.append(energy)
            weights.append(energy_weight)
            panel_edges.append(float(np.exp(log_right)))

    energy = np.concatenate(nodes)
    energy_weight = np.concatenate(weights)
    frequency = energy * EV_ERG / PLANCK_ERG_S
    frequency_weight = energy_weight * EV_ERG / PLANCK_ERG_S
    panel_edge_array = np.asarray(panel_edges, dtype=np.float64)
    arrays = (energy, energy_weight, frequency, frequency_weight, panel_edge_array)
    if (
        not all(np.all(np.isfinite(array)) for array in arrays)
        or np.any(np.diff(energy) <= 0.0)
        or np.any(energy_weight <= 0.0)
        or np.any(frequency_weight <= 0.0)
        or np.any(np.diff(panel_edge_array) <= 0.0)
    ):
        raise ArithmeticError("threshold frequency quadrature became invalid")
    return ThresholdLogFrequencyQuadrature(
        photon_energy_ev=_readonly(energy),
        energy_weight_ev=_readonly(energy_weight),
        frequency_hz=_readonly(frequency),
        frequency_weight_hz=_readonly(frequency_weight),
        threshold_segment_edges_ev=_readonly(segment_edges),
        logarithmic_panel_edges_ev=_readonly(panel_edge_array),
        panels_per_decade=int(panels_per_decade),
        order_per_panel=int(order_per_panel),
    )


def threshold_excess_gauss_legendre_quadrature(
    minimum_energy_ev: float,
    maximum_energy_ev: float,
    panels_per_transformed_decade: int,
    *,
    threshold_scale_ev: float,
    order_per_panel: int = 8,
) -> ThresholdExcessFrequencyQuadrature:
    """以 ``log10[1+(E-E_edge)/scale]`` 在每个阈值右侧聚点。"""
    minimum = float(minimum_energy_ev)
    maximum = float(maximum_energy_ev)
    scale = float(threshold_scale_ev)
    if (
        not np.isfinite(minimum)
        or not np.isfinite(maximum)
        or not np.isfinite(scale)
        or minimum <= 0.0
        or maximum <= minimum
        or scale <= 0.0
    ):
        raise PhysicalDomainError(
            "threshold-excess quadrature bounds and scale must be finite and positive"
        )
    if (
        not isinstance(panels_per_transformed_decade, (int, np.integer))
        or isinstance(panels_per_transformed_decade, (bool, np.bool_))
        or int(panels_per_transformed_decade) < 1
    ):
        raise PhysicalDomainError(
            "panels_per_transformed_decade must be a positive integer"
        )
    if (
        not isinstance(order_per_panel, (int, np.integer))
        or isinstance(order_per_panel, (bool, np.bool_))
        or int(order_per_panel) < 2
    ):
        raise PhysicalDomainError("order_per_panel must be an integer of at least two")
    maximum_fit_energy = min(
        fit.maximum_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
    )
    if maximum > maximum_fit_energy:
        raise PhysicalDomainError(
            "threshold-excess quadrature exceeds the common Verner fit domain"
        )

    thresholds = np.array(
        [fit.threshold_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS],
        dtype=np.float64,
    )
    active = thresholds[(thresholds > minimum) & (thresholds < maximum)]
    segment_edges = np.concatenate(([minimum], active, [maximum]))
    legendre_node, legendre_weight = np.polynomial.legendre.leggauss(
        int(order_per_panel)
    )
    nodes: list[np.ndarray] = []
    weights: list[np.ndarray] = []
    panel_edges: list[float] = [minimum]
    logarithm_base_factor = np.log(10.0)
    for left, right in zip(segment_edges[:-1], segment_edges[1:], strict=True):
        transformed_right = np.log10(1.0 + (right - left) / scale)
        panel_count = max(
            1,
            int(
                np.ceil(
                    int(panels_per_transformed_decade) * transformed_right
                )
            ),
        )
        transformed_edges = np.linspace(0.0, transformed_right, panel_count + 1)
        for transformed_left, transformed_upper in zip(
            transformed_edges[:-1], transformed_edges[1:], strict=True
        ):
            centre = 0.5 * (transformed_left + transformed_upper)
            half_width = 0.5 * (transformed_upper - transformed_left)
            coordinate = centre + half_width * legendre_node
            factor = 10.0**coordinate
            energy = left + scale * (factor - 1.0)
            # 中文：dE=scale ln(10) 10^u du，权重保持严格为正。
            energy_weight = (
                half_width
                * legendre_weight
                * scale
                * logarithm_base_factor
                * factor
            )
            nodes.append(energy)
            weights.append(energy_weight)
            panel_edges.append(
                float(left + scale * (10.0**transformed_upper - 1.0))
            )

    energy = np.concatenate(nodes)
    energy_weight = np.concatenate(weights)
    frequency = energy * EV_ERG / PLANCK_ERG_S
    frequency_weight = energy_weight * EV_ERG / PLANCK_ERG_S
    panel_edge_array = np.asarray(panel_edges, dtype=np.float64)
    arrays = (energy, energy_weight, frequency, frequency_weight, panel_edge_array)
    if (
        not all(np.all(np.isfinite(array)) for array in arrays)
        or np.any(np.diff(energy) <= 0.0)
        or np.any(energy_weight <= 0.0)
        or np.any(frequency_weight <= 0.0)
        or np.any(np.diff(panel_edge_array) <= 0.0)
    ):
        raise ArithmeticError("threshold-excess frequency quadrature became invalid")
    return ThresholdExcessFrequencyQuadrature(
        photon_energy_ev=_readonly(energy),
        energy_weight_ev=_readonly(energy_weight),
        frequency_hz=_readonly(frequency),
        frequency_weight_hz=_readonly(frequency_weight),
        threshold_segment_edges_ev=_readonly(segment_edges),
        transformed_panel_edges_ev=_readonly(panel_edge_array),
        threshold_scale_ev=scale,
        panels_per_transformed_decade=int(panels_per_transformed_decade),
        order_per_panel=int(order_per_panel),
    )


def trapezoid_frequency_weights_hz(frequency_hz: ArrayLike) -> NDArray[np.float64]:
    """把非均匀频率网格的梯形积分写成显式节点权重。"""
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    if (
        frequency.ndim != 1
        or frequency.size < 2
        or not np.all(np.isfinite(frequency))
        or np.any(frequency <= 0.0)
        or np.any(np.diff(frequency) <= 0.0)
    ):
        raise PhysicalDomainError(
            "frequency_hz must be finite, positive and strictly increasing"
        )
    interval = np.diff(frequency)
    weight = np.empty_like(frequency)
    weight[0] = 0.5 * interval[0]
    weight[-1] = 0.5 * interval[-1]
    weight[1:-1] = 0.5 * (interval[:-1] + interval[1:])
    return _readonly(weight)


def validate_frequency_weights_hz(
    frequency_hz: ArrayLike,
    frequency_weight_hz: ArrayLike | None,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """验证节点和权重；未给权重时严格回到非均匀梯形公式。"""
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    trapezoid = trapezoid_frequency_weights_hz(frequency)
    if frequency_weight_hz is None:
        return _readonly(frequency), trapezoid
    weight = np.array(frequency_weight_hz, dtype=np.float64, copy=True)
    if (
        weight.shape != frequency.shape
        or not np.all(np.isfinite(weight))
        or np.any(weight <= 0.0)
    ):
        raise PhysicalDomainError(
            "frequency_weight_hz must match frequency_hz and be finite and positive"
        )
    return _readonly(frequency), _readonly(weight)


def integrate_frequency(
    values: ArrayLike,
    frequency_weight_hz: ArrayLike,
    *,
    axis: int = 0,
) -> NDArray[np.float64] | np.float64:
    """用显式正权沿指定频率轴积分，不推断或重构被积函数。"""
    array = np.asarray(values, dtype=np.float64)
    weight = np.asarray(frequency_weight_hz, dtype=np.float64)
    if array.ndim < 1 or weight.ndim != 1:
        raise PhysicalDomainError("frequency integral requires an array and 1D weights")
    normalized_axis = int(axis) % array.ndim
    if array.shape[normalized_axis] != weight.size:
        raise PhysicalDomainError("frequency weights do not match the integration axis")
    if (
        not np.all(np.isfinite(array))
        or not np.all(np.isfinite(weight))
        or np.any(weight <= 0.0)
    ):
        raise PhysicalDomainError("frequency integral inputs must be finite with positive weights")
    result = np.tensordot(weight, np.moveaxis(array, normalized_axis, 0), axes=(0, 0))
    if not np.all(np.isfinite(result)):
        raise ArithmeticError("frequency integral became non-finite")
    return result
