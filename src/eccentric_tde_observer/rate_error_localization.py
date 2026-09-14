"""H I 光致电离率的有符号频段误差定位。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .atomic_continuum import EV_ERG, H_I_VERNER_FIT
from .log_frequency_moments import (
    limit_nonnegative_log_frequency_group_p1,
)
from .radiation import PLANCK_ERG_S
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


def _positive_edges(name: str, values: ArrayLike) -> NDArray[np.float64]:
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


@dataclass(frozen=True)
class LogP1ProjectionAudit:
    """把 P0 参考谱压缩到 log-P1 网格后的守恒与可实现性审计。"""

    group_edge_hz: NDArray[np.float64]
    mean_energy_density: NDArray[np.float64]
    prelimit_first_moment_energy_density: NDArray[np.float64]
    realizable_first_moment_energy_density: NDArray[np.float64]
    limited_group_count: int
    maximum_prelimit_realizability_ratio: float
    minimum_prelimit_endpoint_energy_density: float
    reference_energy_integral: float
    projected_energy_integral: float
    relative_energy_integral_error: float


@dataclass(frozen=True)
class PiecewiseConstantProjectionAudit:
    """把 P0 参考谱守恒投影到另一组边界后的能量审计。"""

    group_edge_hz: NDArray[np.float64]
    mean_intensity_density: NDArray[np.float64]
    reference_energy_integral: float
    projected_energy_integral: float
    relative_energy_integral_error: float


@dataclass(frozen=True)
class HydrogenRateLocalization:
    """候选 log-P1 与 P0 参考的逐能段 H I 率差。"""

    analysis_edge_ev: NDArray[np.float64]
    candidate_rate_bin_s1: NDArray[np.float64]
    reference_rate_bin_s1: NDArray[np.float64]
    signed_error_bin_s1: NDArray[np.float64]
    absolute_integrand_difference_bin_s1: NDArray[np.float64]
    candidate_total_rate_s1: float
    reference_total_rate_s1: float
    signed_relative_error: float
    absolute_integrand_difference_relative: float
    saturated_candidate_group_count: int
    saturated_candidate_absolute_difference_s1: float
    saturated_candidate_absolute_difference_fraction: float
    quadrature_order_per_native_overlap: int


def project_piecewise_constant_intensity(
    source_group_edge_hz: ArrayLike,
    source_mean_intensity_cgs: ArrayLike,
    target_group_edge_hz: ArrayLike,
) -> PiecewiseConstantProjectionAudit:
    """按频率交叠积分把分片常数 ``J_nu`` 守恒投影到目标 P0 网格。"""
    source_edge = _positive_edges("source_group_edge_hz", source_group_edge_hz)
    target_edge = _positive_edges("target_group_edge_hz", target_group_edge_hz)
    source = np.asarray(source_mean_intensity_cgs, dtype=np.float64)
    if (
        source.shape != (source_edge.size - 1,)
        or not np.all(np.isfinite(source))
        or np.any(source < 0.0)
    ):
        raise PhysicalDomainError(
            "source_mean_intensity_cgs must be finite and non-negative per group"
        )
    if source_edge[0] != target_edge[0] or source_edge[-1] != target_edge[-1]:
        raise PhysicalDomainError("source and target frequency bands must match exactly")

    mean = np.empty(target_edge.size - 1, dtype=np.float64)
    source_group = 0
    for group, (left, right) in enumerate(
        zip(target_edge[:-1], target_edge[1:], strict=True)
    ):
        while source_edge[source_group + 1] <= left:
            source_group += 1
        integral = 0.0
        local_source = source_group
        position = left
        while position < right:
            upper = min(right, source_edge[local_source + 1])
            integral += source[local_source] * (upper - position)
            position = upper
            if position < right:
                local_source += 1
        mean[group] = integral / (right - left)

    if not np.all(np.isfinite(mean)) or np.any(mean < 0.0):
        raise ArithmeticError("P0 projection became invalid")
    reference_integral = float(np.sum(source * np.diff(source_edge)))
    projected_integral = float(np.sum(mean * np.diff(target_edge)))
    difference = abs(projected_integral - reference_integral)
    relative = (
        difference / abs(reference_integral)
        if reference_integral != 0.0
        else difference
    )
    return PiecewiseConstantProjectionAudit(
        group_edge_hz=_readonly(np.array(target_edge, copy=True)),
        mean_intensity_density=_readonly(mean),
        reference_energy_integral=reference_integral,
        projected_energy_integral=projected_integral,
        relative_energy_integral_error=relative,
    )


def project_piecewise_constant_intensity_to_log_p1(
    source_group_edge_hz: ArrayLike,
    source_mean_intensity_cgs: ArrayLike,
    target_group_edge_hz: ArrayLike,
) -> LogP1ProjectionAudit:
    """把分片常数 ``J_nu`` 精确投影为目标网格中的 ``Q=nu*J_nu`` P1。"""
    source_edge = _positive_edges("source_group_edge_hz", source_group_edge_hz)
    target_edge = _positive_edges("target_group_edge_hz", target_group_edge_hz)
    source = np.asarray(source_mean_intensity_cgs, dtype=np.float64)
    if (
        source.shape != (source_edge.size - 1,)
        or not np.all(np.isfinite(source))
        or np.any(source < 0.0)
    ):
        raise PhysicalDomainError(
            "source_mean_intensity_cgs must be finite and non-negative per group"
        )
    if source_edge[0] != target_edge[0] or source_edge[-1] != target_edge[-1]:
        raise PhysicalDomainError("source and target frequency bands must match exactly")

    target_y = np.log(target_edge)
    width = np.diff(target_y)
    centre = 0.5 * (target_y[:-1] + target_y[1:])
    mean = np.empty(width.size, dtype=np.float64)
    first = np.empty_like(mean)
    source_group = 0
    for group, (left, right) in enumerate(
        zip(target_edge[:-1], target_edge[1:], strict=True)
    ):
        while source_edge[source_group + 1] <= left:
            source_group += 1
        integral = 0.0
        centred_integral = 0.0
        local_source = source_group
        position = left
        while position < right:
            upper = min(right, source_edge[local_source + 1])
            value = source[local_source]
            integral += value * (upper - position)
            # 中文：积分 exp(y)*(y-y_c)，不插值也不重归一化参考谱。
            centred_integral += value * (
                upper * (np.log(upper) - centre[group] - 1.0)
                - position * (np.log(position) - centre[group] - 1.0)
            )
            position = upper
            if position < right:
                local_source += 1
        mean[group] = integral / width[group]
        first[group] = 2.0 * centred_integral / width[group] ** 2

    if not np.all(np.isfinite(mean)) or np.any(mean < 0.0):
        raise ArithmeticError("log-P1 projection mean became invalid")
    limited = limit_nonnegative_log_frequency_group_p1(mean, first)
    reference_integral = float(np.sum(source * np.diff(source_edge)))
    projected_integral = float(np.sum(mean * width))
    difference = abs(projected_integral - reference_integral)
    relative = (
        difference / abs(reference_integral)
        if reference_integral != 0.0
        else difference
    )
    minimum_endpoint = float(np.min(mean - 3.0 * np.abs(first)))
    return LogP1ProjectionAudit(
        group_edge_hz=_readonly(np.array(target_edge, copy=True)),
        mean_energy_density=_readonly(mean),
        prelimit_first_moment_energy_density=_readonly(first),
        realizable_first_moment_energy_density=limited.first_moment_density,
        limited_group_count=limited.limited_group_count,
        maximum_prelimit_realizability_ratio=(
            limited.maximum_prelimit_realizability_ratio
        ),
        minimum_prelimit_endpoint_energy_density=minimum_endpoint,
        reference_energy_integral=reference_integral,
        projected_energy_integral=projected_integral,
        relative_energy_integral_error=relative,
    )


def localize_hydrogen_photoionization_rate_error(
    candidate_group_edge_hz: ArrayLike,
    candidate_mean_energy_density: ArrayLike,
    candidate_first_moment_energy_density: ArrayLike,
    reference_group_edge_hz: ArrayLike,
    reference_mean_intensity_cgs: ArrayLike,
    analysis_edge_ev: ArrayLike,
    *,
    quadrature_order_per_native_overlap: int = 8,
    require_nonnegative_candidate: bool = True,
) -> HydrogenRateLocalization:
    """在原生网格边界的并集上积分逐能段有符号 H I 率误差。"""
    candidate_edge = _positive_edges(
        "candidate_group_edge_hz", candidate_group_edge_hz
    )
    reference_edge = _positive_edges(
        "reference_group_edge_hz", reference_group_edge_hz
    )
    analysis_ev = _positive_edges("analysis_edge_ev", analysis_edge_ev)
    mean = np.asarray(candidate_mean_energy_density, dtype=np.float64)
    first = np.asarray(candidate_first_moment_energy_density, dtype=np.float64)
    reference = np.asarray(reference_mean_intensity_cgs, dtype=np.float64)
    if (
        mean.shape != (candidate_edge.size - 1,)
        or first.shape != mean.shape
        or not np.all(np.isfinite(mean))
        or not np.all(np.isfinite(first))
        or np.any(mean < 0.0)
    ):
        raise PhysicalDomainError("candidate log-P1 moments do not match its grid")
    if (
        reference.shape != (reference_edge.size - 1,)
        or not np.all(np.isfinite(reference))
        or np.any(reference < 0.0)
    ):
        raise PhysicalDomainError("reference P0 intensity does not match its grid")
    if (
        not isinstance(quadrature_order_per_native_overlap, (int, np.integer))
        or isinstance(quadrature_order_per_native_overlap, (bool, np.bool_))
        or int(quadrature_order_per_native_overlap) < 2
    ):
        raise PhysicalDomainError("quadrature order must be an integer of at least two")
    analysis_hz = analysis_ev * EV_ERG / PLANCK_ERG_S
    if not (
        candidate_edge[0] == reference_edge[0] == analysis_hz[0]
        and candidate_edge[-1] == reference_edge[-1] == analysis_hz[-1]
    ):
        raise PhysicalDomainError("candidate, reference and analysis bands must match")
    if require_nonnegative_candidate and np.any(mean - 3.0 * np.abs(first) < 0.0):
        raise PhysicalDomainError("candidate log-P1 reconstruction is not non-negative")

    # 中文：把两套原生边界和分析边界全部并入，Gauss 面板不会跨越谱重构跳点。
    integration_edge = np.unique(
        np.concatenate((candidate_edge, reference_edge, analysis_hz))
    )
    integration_y = np.log(integration_edge)
    centre_y = 0.5 * (integration_y[:-1] + integration_y[1:])
    half_width_y = 0.5 * np.diff(integration_y)
    node, weight = np.polynomial.legendre.leggauss(
        int(quadrature_order_per_native_overlap)
    )
    node_y = centre_y[:, None] + half_width_y[:, None] * node[None, :]
    node_hz = np.exp(node_y)
    node_weight_y = half_width_y[:, None] * weight[None, :]

    candidate_index = np.searchsorted(candidate_edge, node_hz, side="right") - 1
    reference_index = np.searchsorted(reference_edge, node_hz, side="right") - 1
    candidate_edge_y = np.log(candidate_edge)
    candidate_width_y = np.diff(candidate_edge_y)
    candidate_centre_y = 0.5 * (
        candidate_edge_y[:-1] + candidate_edge_y[1:]
    )
    coordinate = 2.0 * (
        node_y - candidate_centre_y[candidate_index]
    ) / candidate_width_y[candidate_index]
    candidate_q = (
        mean[candidate_index] + 3.0 * first[candidate_index] * coordinate
    )
    reference_q = node_hz * reference[reference_index]
    if (
        not np.all(np.isfinite(candidate_q))
        or not np.all(np.isfinite(reference_q))
        or np.any(reference_q < 0.0)
        or (require_nonnegative_candidate and np.any(candidate_q < 0.0))
    ):
        raise ArithmeticError("rate-localization spectra became invalid")

    energy_ev = node_hz * PLANCK_ERG_S / EV_ERG
    cross_section = H_I_VERNER_FIT.cross_section_cm2(energy_ev)
    kernel = cross_section / (PLANCK_ERG_S * node_hz)
    candidate_integrand = 4.0 * np.pi * candidate_q * kernel
    reference_integrand = 4.0 * np.pi * reference_q * kernel
    candidate_segment = np.sum(node_weight_y * candidate_integrand, axis=1)
    reference_segment = np.sum(node_weight_y * reference_integrand, axis=1)
    absolute_segment = np.sum(
        node_weight_y * np.abs(candidate_integrand - reference_integrand), axis=1
    )
    saturated_group = (mean > 0.0) & (
        np.abs(first) == np.nextafter(mean / 3.0, 0.0)
    )
    saturated_segment = np.sum(
        node_weight_y
        * np.abs(candidate_integrand - reference_integrand)
        * saturated_group[candidate_index],
        axis=1,
    )
    segment_mid_ev = np.sqrt(integration_edge[:-1] * integration_edge[1:])
    segment_mid_ev *= PLANCK_ERG_S / EV_ERG
    analysis_index = np.searchsorted(analysis_ev, segment_mid_ev, side="right") - 1
    bin_count = analysis_ev.size - 1
    candidate_bin = np.zeros(bin_count, dtype=np.float64)
    reference_bin = np.zeros(bin_count, dtype=np.float64)
    absolute_bin = np.zeros(bin_count, dtype=np.float64)
    np.add.at(candidate_bin, analysis_index, candidate_segment)
    np.add.at(reference_bin, analysis_index, reference_segment)
    np.add.at(absolute_bin, analysis_index, absolute_segment)
    signed_bin = candidate_bin - reference_bin
    candidate_total = float(np.sum(candidate_bin))
    reference_total = float(np.sum(reference_bin))
    signed_relative = (
        (candidate_total - reference_total) / reference_total
        if reference_total != 0.0
        else candidate_total - reference_total
    )
    absolute_relative = (
        float(np.sum(absolute_bin)) / abs(reference_total)
        if reference_total != 0.0
        else float(np.sum(absolute_bin))
    )
    saturated_absolute = float(np.sum(saturated_segment))
    absolute_total = float(np.sum(absolute_bin))
    saturated_fraction = (
        saturated_absolute / absolute_total if absolute_total > 0.0 else 0.0
    )
    arrays = (candidate_bin, reference_bin, signed_bin, absolute_bin)
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ArithmeticError("rate-localization bins became non-finite")
    return HydrogenRateLocalization(
        analysis_edge_ev=_readonly(np.array(analysis_ev, copy=True)),
        candidate_rate_bin_s1=_readonly(candidate_bin),
        reference_rate_bin_s1=_readonly(reference_bin),
        signed_error_bin_s1=_readonly(signed_bin),
        absolute_integrand_difference_bin_s1=_readonly(absolute_bin),
        candidate_total_rate_s1=candidate_total,
        reference_total_rate_s1=reference_total,
        signed_relative_error=signed_relative,
        absolute_integrand_difference_relative=absolute_relative,
        saturated_candidate_group_count=int(np.count_nonzero(saturated_group)),
        saturated_candidate_absolute_difference_s1=saturated_absolute,
        saturated_candidate_absolute_difference_fraction=saturated_fraction,
        quadrature_order_per_native_overlap=int(
            quadrature_order_per_native_overlap
        ),
    )
