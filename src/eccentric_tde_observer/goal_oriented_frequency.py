"""按已知原子率核分配固定频率控制体的目标导向网格。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .atomic_continuum import (
    EV_ERG,
    H_HE_GROUND_STATE_PHOTOIONIZATION_FITS,
    H_I_VERNER_FIT,
)
from .radiation import PLANCK_ERG_S
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class HydrogenPhotoionizationMonitorGrid:
    """均分均匀基线与 H I 光致电离率核监视测度的固定网格。"""

    group_edge_ev: NDArray[np.float64]
    group_edge_hz: NDArray[np.float64]
    anchor_energy_ev: NDArray[np.float64]
    segment_group_count: NDArray[np.int64]
    segment_monitor_integral: NDArray[np.float64]
    focus_fraction: float
    group_count: int
    integration_panels_per_segment: int
    hydrogen_rate_kernel_integral_log_hz: float


def _positive_configuration(
    minimum_energy_ev: float,
    maximum_energy_ev: float,
    group_count: int,
    focus_fraction: float,
    integration_panels_per_segment: int,
) -> tuple[float, float, int, float, int]:
    minimum = float(minimum_energy_ev)
    maximum = float(maximum_energy_ev)
    fraction = float(focus_fraction)
    if (
        not np.isfinite(minimum)
        or not np.isfinite(maximum)
        or minimum <= 0.0
        or maximum <= minimum
    ):
        raise PhysicalDomainError("energy bounds must be finite, positive and ordered")
    if maximum > H_I_VERNER_FIT.maximum_energy_ev:
        raise PhysicalDomainError("H I monitor exceeds the Verner fit domain")
    for name, value, lower in (
        ("group_count", group_count, 4),
        ("integration_panels_per_segment", integration_panels_per_segment, 16),
    ):
        if (
            not isinstance(value, (int, np.integer))
            or isinstance(value, (bool, np.bool_))
            or int(value) < lower
        ):
            raise PhysicalDomainError(f"{name} must be an integer of at least {lower}")
    if not np.isfinite(fraction) or fraction < 0.0 or fraction >= 1.0:
        raise PhysicalDomainError("focus_fraction must lie in [0,1)")
    return minimum, maximum, int(group_count), fraction, int(
        integration_panels_per_segment
    )


def _hydrogen_rate_kernel_log_measure(
    energy_ev: NDArray[np.float64],
) -> NDArray[np.float64]:
    """返回 ``Gamma_HI/(4*pi)=integral Q*k_HI*dln(nu)`` 中的核。"""
    frequency_hz = energy_ev * EV_ERG / PLANCK_ERG_S
    cross_section = H_I_VERNER_FIT.cross_section_cm2(energy_ev)
    kernel = cross_section / (PLANCK_ERG_S * frequency_hz)
    if not np.all(np.isfinite(kernel)) or np.any(kernel < 0.0):
        raise ArithmeticError("H I photoionization monitor became invalid")
    return kernel


def hydrogen_photoionization_monitor_group_grid(
    minimum_energy_ev: float,
    maximum_energy_ev: float,
    group_count: int,
    focus_fraction: float,
    *,
    integration_panels_per_segment: int = 32768,
) -> HydrogenPhotoionizationMonitorGrid:
    """构造固定组数的 H I 率核等监视测度网格。

    ``focus_fraction`` 是分配给归一化 H I 率核的监视测度比例；其余比例保持
    ``ln(nu)`` 均匀基线。H/He 三个阈值始终作为精确控制体边界。
    """
    minimum, maximum, count, fraction, panels = _positive_configuration(
        minimum_energy_ev,
        maximum_energy_ev,
        group_count,
        focus_fraction,
        integration_panels_per_segment,
    )
    thresholds = np.array(
        [fit.threshold_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS],
        dtype=np.float64,
    )
    anchors = np.concatenate(
        (
            [minimum],
            thresholds[(thresholds > minimum) & (thresholds < maximum)],
            [maximum],
        )
    )
    if count < anchors.size - 1:
        raise PhysicalDomainError("group_count cannot preserve all threshold segments")
    segment_samples: list[tuple[NDArray[np.float64], NDArray[np.float64]]] = []
    kernel_integrals: list[float] = []
    hydrogen_threshold = H_I_VERNER_FIT.threshold_energy_ev
    for left, right in zip(anchors[:-1], anchors[1:], strict=True):
        log_energy = np.linspace(np.log(left), np.log(right), panels + 1)
        energy = np.exp(log_energy)
        energy[0] = left
        energy[-1] = right
        kernel = _hydrogen_rate_kernel_log_measure(energy)
        if right == hydrogen_threshold:
            # 中文：阈值以下分段取左极限，不能给端点跳变虚构半个单元面积。
            kernel[-1] = 0.0
        integral = float(np.trapezoid(kernel, log_energy))
        segment_samples.append((log_energy, kernel))
        kernel_integrals.append(integral)
    kernel_integral = float(np.sum(kernel_integrals))
    total_log_width = float(np.log(maximum / minimum))
    if not np.isfinite(kernel_integral) or kernel_integral <= 0.0:
        raise PhysicalDomainError("energy range must include positive H I rate support")
    mean_kernel = kernel_integral / total_log_width

    cumulative_monitor: list[NDArray[np.float64]] = []
    monitor_integrals: list[float] = []
    for log_energy, kernel in segment_samples:
        monitor = (1.0 - fraction) + fraction * kernel / mean_kernel
        if not np.all(np.isfinite(monitor)) or np.any(monitor <= 0.0):
            raise ArithmeticError("rate-kernel monitor must remain finite and positive")
        cell_integral = (
            0.5
            * np.diff(log_energy)
            * (monitor[:-1] + monitor[1:])
        )
        cumulative = np.concatenate(([0.0], np.cumsum(cell_integral)))
        if np.any(np.diff(cumulative) <= 0.0):
            raise ArithmeticError("rate-kernel cumulative monitor is not increasing")
        cumulative_monitor.append(cumulative)
        monitor_integrals.append(float(cumulative[-1]))

    raw_count = count * np.asarray(monitor_integrals) / np.sum(monitor_integrals)
    segment_count = np.floor(raw_count).astype(np.int64)
    if np.any(segment_count < 1):
        raise PhysicalDomainError(
            "group_count is too small for this focus fraction and threshold anchors"
        )
    remaining = count - int(np.sum(segment_count))
    remainder_order = np.argsort(
        -(raw_count - segment_count), kind="stable"
    )
    segment_count[remainder_order[:remaining]] += 1
    if int(np.sum(segment_count)) != count:
        raise ArithmeticError("integer monitor apportionment lost the group count")

    edges: list[float] = [minimum]
    for (log_energy, _), cumulative, local_count in zip(
        segment_samples,
        cumulative_monitor,
        segment_count,
        strict=True,
    ):
        target = np.linspace(0.0, cumulative[-1], int(local_count) + 1)[1:]
        if target[0] <= cumulative[0] or target[-1] > cumulative[-1]:
            raise ArithmeticError("monitor inversion target left its segment")
        edges.extend(np.exp(np.interp(target, cumulative, log_energy)))
    edge_ev = np.asarray(edges, dtype=np.float64)
    # 中文：用解析锚点消除 exp(log(E_edge)) 的舍入漂移，不移动任何内部物理结果。
    edge_ev[np.cumsum(segment_count)] = anchors[1:]
    if (
        edge_ev.size != count + 1
        or not np.all(np.isfinite(edge_ev))
        or np.any(np.diff(edge_ev) <= 0.0)
    ):
        raise ArithmeticError("rate-kernel frequency edges became invalid")
    return HydrogenPhotoionizationMonitorGrid(
        group_edge_ev=_readonly(edge_ev),
        group_edge_hz=_readonly(edge_ev * EV_ERG / PLANCK_ERG_S),
        anchor_energy_ev=_readonly(np.array(anchors, copy=True)),
        segment_group_count=_readonly(segment_count),
        segment_monitor_integral=_readonly(
            np.asarray(monitor_integrals, dtype=np.float64)
        ),
        focus_fraction=fraction,
        group_count=count,
        integration_panels_per_segment=panels,
        hydrogen_rate_kernel_integral_log_hz=kernel_integral,
    )
