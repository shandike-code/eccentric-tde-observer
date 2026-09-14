"""以 ``y=ln(nu)`` 为控制体坐标的守恒 P1 频率矩。

对谱密度 ``q_nu`` 保存 ``Q=nu*q_nu``，使物理频率积分严格写成
``integral q_nu dnu = integral Q dy``。Lorentz Doppler 搬移在 ``y`` 上是平移，
不再把组内多项式伸缩到另一套坐标。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .mixed_frame_frequency import (
    _piecewise_linear_integrals,
    frequency_group_p1_from_gauss_node_values,
    frequency_group_p1_gauss_node_values,
    limit_nonnegative_frequency_group_p1,
    lorentz_ray_transform,
)
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class LogFrequencyGroupP1Density:
    """每个对数频率控制体中 ``Q=nu*q_nu`` 的平均与一次矩。"""

    mean_density: NDArray[np.float64]
    first_moment_density: NDArray[np.float64]
    limited_group_count: int
    maximum_prelimit_realizability_ratio: float


@dataclass(frozen=True)
class ComovingLogFrequencyP1Radiation:
    """对数频率 P1 Lorentz 平移后的共动角强度与角平均。"""

    angle_mean_density: NDArray[np.float64]
    angle_first_moment_density: NDArray[np.float64]
    mean_intensity_density: NDArray[np.float64]
    mean_intensity_first_moment_density: NDArray[np.float64]
    comoving_angular_measure: NDArray[np.float64]
    limited_group_count: int
    maximum_prelimit_realizability_ratio: float


def _positive_frequency_edges(name: str, values: ArrayLike) -> NDArray[np.float64]:
    edge = np.asarray(values, dtype=np.float64)
    if (
        edge.ndim != 1
        or edge.size < 2
        or not np.all(np.isfinite(edge))
        or np.any(edge <= 0.0)
        or np.any(np.diff(edge) <= 0.0)
    ):
        raise PhysicalDomainError(
            f"{name} must be finite, positive and strictly increasing"
        )
    return edge


def log_frequency_group_edges(edge_hz: ArrayLike) -> NDArray[np.float64]:
    """返回严格递增的自然对数频率控制体边界。"""
    edge = _positive_frequency_edges("edge_hz", edge_hz)
    return _readonly(np.log(edge))


def _wrap_p1_state(state) -> LogFrequencyGroupP1Density:
    return LogFrequencyGroupP1Density(
        mean_density=state.mean_density,
        first_moment_density=state.first_moment_density,
        limited_group_count=state.limited_group_count,
        maximum_prelimit_realizability_ratio=(
            state.maximum_prelimit_realizability_ratio
        ),
    )


def limit_nonnegative_log_frequency_group_p1(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
) -> LogFrequencyGroupP1Density:
    """保持每组 ``integral Q dy`` 不变，只限制未解析的一次矩。"""
    return _wrap_p1_state(
        limit_nonnegative_frequency_group_p1(mean_density, first_moment_density)
    )


def log_frequency_group_p1_gauss_node_values(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
) -> NDArray[np.float64]:
    """在两个对数频率 Gauss 节点重构非负 ``Q``。"""
    return frequency_group_p1_gauss_node_values(mean_density, first_moment_density)


def log_frequency_group_p1_from_gauss_node_values(
    node_density: ArrayLike,
    *,
    enforce_realizability: bool = True,
) -> LogFrequencyGroupP1Density:
    """把两个对数频率 Gauss 节点投影回 P1 矩。"""
    state = frequency_group_p1_from_gauss_node_values(
        node_density, enforce_realizability=enforce_realizability
    )
    return _wrap_p1_state(state)


def _validated_log_group_inputs(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    source_edge_hz: ArrayLike,
    target_edge_hz: ArrayLike,
    doppler_factor: ArrayLike,
) -> tuple[NDArray[np.float64], ...]:
    source_edge = _positive_frequency_edges("source_edge_hz", source_edge_hz)
    target_edge = _positive_frequency_edges("target_edge_hz", target_edge_hz)
    source_y = np.log(source_edge)
    target_y = np.log(target_edge)
    mean = np.asarray(mean_density, dtype=np.float64)
    first = np.asarray(first_moment_density, dtype=np.float64)
    doppler = np.asarray(doppler_factor, dtype=np.float64)
    if (
        mean.ndim < 1
        or mean.shape[0] != source_edge.size - 1
        or first.shape != mean.shape
        or not np.all(np.isfinite(mean))
        or not np.all(np.isfinite(first))
        or np.any(mean < 0.0)
    ):
        raise PhysicalDomainError("log-frequency P1 moments do not match source groups")
    if (
        not np.all(np.isfinite(doppler))
        or np.any(doppler <= 0.0)
        or mean.shape[1:] != doppler.shape
    ):
        raise PhysicalDomainError(
            "doppler_factor must be positive and match non-frequency axes"
        )
    state = limit_nonnegative_frequency_group_p1(mean, first)
    if state.limited_group_count != 0:
        raise PhysicalDomainError("source log-frequency P1 state is not realizable")
    return mean, first, source_edge, target_edge, source_y, target_y, doppler


def lorentz_translate_log_frequency_group_p1_density(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    source_edge_hz: ArrayLike,
    target_edge_hz: ArrayLike,
    doppler_factor: ArrayLike,
    *,
    direction: str,
    lab_to_comoving_amplitude_power: float,
    enforce_realizability: bool = True,
) -> LogFrequencyGroupP1Density:
    """在 ``y=ln(nu)`` 上平移并守恒搬移 P1 的零阶和一次矩。

    若 ``Q_0=D**r Q``，则 ``lab_to_comoving_amplitude_power=r``。
    """
    (
        mean,
        first,
        source_edge,
        target_edge,
        source_y,
        target_y,
        doppler,
    ) = _validated_log_group_inputs(
        mean_density,
        first_moment_density,
        source_edge_hz,
        target_edge_hz,
        doppler_factor,
    )
    if direction not in ("lab_to_comoving", "comoving_to_lab"):
        raise PhysicalDomainError("invalid log-frequency Lorentz direction")
    power = float(lab_to_comoving_amplitude_power)
    if not np.isfinite(power):
        raise PhysicalDomainError("Lorentz amplitude power must be finite")
    if np.all(doppler == 1.0) and np.array_equal(source_edge, target_edge):
        return LogFrequencyGroupP1Density(
            mean_density=_readonly(np.array(mean, copy=True)),
            first_moment_density=_readonly(np.array(first, copy=True)),
            limited_group_count=0,
            maximum_prelimit_realizability_ratio=0.0,
        )

    target_width = np.diff(target_y)
    target_centre = 0.5 * (target_y[:-1] + target_y[1:])
    output_mean = np.empty((target_width.size, *doppler.shape), dtype=np.float64)
    output_first = np.empty_like(output_mean)
    flat_mean = mean.reshape(mean.shape[0], -1)
    flat_first = first.reshape(first.shape[0], -1)
    flat_doppler = doppler.reshape(-1)
    flat_output_mean = output_mean.reshape(output_mean.shape[0], -1)
    flat_output_first = output_first.reshape(output_first.shape[0], -1)
    for column, factor in enumerate(flat_doppler):
        shift = float(np.log(factor))
        if direction == "lab_to_comoving":
            lower = target_y[:-1] - shift
            upper = target_y[1:] - shift
            origin = target_centre - shift
            multiplier = factor**power
        else:
            lower = target_y[:-1] + shift
            upper = target_y[1:] + shift
            origin = target_centre + shift
            multiplier = factor**(-power)
        integral, centred = _piecewise_linear_integrals(
            flat_mean[:, column],
            flat_first[:, column],
            source_y,
            lower,
            upper,
            origin,
        )
        flat_output_mean[:, column] = multiplier * integral / target_width
        flat_output_first[:, column] = (
            2.0 * multiplier * centred / target_width**2
        )
    if not np.all(np.isfinite(output_mean)) or np.any(output_mean < 0.0):
        raise ArithmeticError("log-frequency Lorentz mean became invalid")
    if enforce_realizability:
        return limit_nonnegative_log_frequency_group_p1(output_mean, output_first)
    ratio = np.zeros_like(output_mean)
    positive = output_mean > 0.0
    ratio[positive] = 3.0 * np.abs(output_first[positive]) / output_mean[positive]
    return LogFrequencyGroupP1Density(
        mean_density=_readonly(output_mean),
        first_moment_density=_readonly(output_first),
        limited_group_count=0,
        maximum_prelimit_realizability_ratio=(
            float(np.max(ratio)) if ratio.size else 0.0
        ),
    )


def lorentz_translate_log_frequency_group_p1_intensity(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    source_edge_hz: ArrayLike,
    target_edge_hz: ArrayLike,
    doppler_factor: ArrayLike,
    *,
    direction: str,
) -> LogFrequencyGroupP1Density:
    """按 ``nu*I_nu`` 的四次 Doppler 振幅做守恒平移。"""
    return lorentz_translate_log_frequency_group_p1_density(
        mean_density,
        first_moment_density,
        source_edge_hz,
        target_edge_hz,
        doppler_factor,
        direction=direction,
        lab_to_comoving_amplitude_power=4.0,
    )


def lorentz_translate_comoving_log_p1_emissivity_to_lab(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    comoving_edge_hz: ArrayLike,
    lab_edge_hz: ArrayLike,
    doppler_lab_to_comoving: ArrayLike,
) -> LogFrequencyGroupP1Density:
    """按 ``nu*eta_nu`` 的三次 Doppler 振幅从共动系平移到实验室系。"""
    return lorentz_translate_log_frequency_group_p1_density(
        mean_density,
        first_moment_density,
        comoving_edge_hz,
        lab_edge_hz,
        doppler_lab_to_comoving,
        direction="comoving_to_lab",
        lab_to_comoving_amplitude_power=3.0,
    )


def lorentz_translate_comoving_log_p1_extinction_to_lab(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    comoving_edge_hz: ArrayLike,
    lab_edge_hz: ArrayLike,
    doppler_lab_to_comoving: ArrayLike,
) -> LogFrequencyGroupP1Density:
    """按 ``chi_0=chi/D`` 从共动系平移消光系数到实验室系。"""
    return lorentz_translate_log_frequency_group_p1_density(
        mean_density,
        first_moment_density,
        comoving_edge_hz,
        lab_edge_hz,
        doppler_lab_to_comoving,
        direction="comoving_to_lab",
        lab_to_comoving_amplitude_power=-1.0,
    )


def comoving_log_frequency_group_p1_radiation(
    lab_group_mean_intensity_density: ArrayLike,
    lab_group_first_moment_intensity_density: ArrayLike,
    lab_edge_hz: ArrayLike,
    comoving_edge_hz: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    velocity_beta: ArrayLike,
) -> ComovingLogFrequencyP1Radiation:
    """平移实验室系 ``nu*I_nu`` 并计算共动角平均的两个 P1 矩。"""
    transform = lorentz_ray_transform(
        direction_cosine, angular_weight, velocity_beta
    )
    mean = np.asarray(lab_group_mean_intensity_density, dtype=np.float64)
    first = np.asarray(lab_group_first_moment_intensity_density, dtype=np.float64)
    if (
        mean.ndim < 2
        or first.shape != mean.shape
        or mean.shape[1:] != transform.doppler_lab_to_comoving.shape
    ):
        raise PhysicalDomainError(
            "lab log-frequency P1 axes must match frequency, angle and depth"
        )
    remapped = lorentz_translate_log_frequency_group_p1_intensity(
        mean,
        first,
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
    limited = limit_nonnegative_log_frequency_group_p1(
        angular_mean, angular_first
    )
    measure = 0.5 * np.sum(transform.comoving_angular_weight, axis=0)
    return ComovingLogFrequencyP1Radiation(
        angle_mean_density=remapped.mean_density,
        angle_first_moment_density=remapped.first_moment_density,
        mean_intensity_density=limited.mean_density,
        mean_intensity_first_moment_density=limited.first_moment_density,
        comoving_angular_measure=_readonly(np.array(measure, copy=True)),
        limited_group_count=(
            remapped.limited_group_count + limited.limited_group_count
        ),
        maximum_prelimit_realizability_ratio=max(
            remapped.maximum_prelimit_realizability_ratio,
            limited.maximum_prelimit_realizability_ratio,
        ),
    )
