"""守恒 P0 频率层级、嵌入式目标误差排序与预算内可变叶网格。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .atomic_continuum import (
    EV_ERG,
    H_HE_GROUND_STATE_PHOTOIONIZATION_FITS,
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


def _nested_offsets(
    coarse_edge: NDArray[np.float64], fine_edge: NDArray[np.float64]
) -> NDArray[np.int64]:
    index = np.searchsorted(fine_edge, coarse_edge)
    if (
        index[0] != 0
        or index[-1] != fine_edge.size - 1
        or np.any(index >= fine_edge.size)
        or not np.array_equal(fine_edge[index], coarse_edge)
    ):
        raise PhysicalDomainError("fine frequency edges must preserve every coarse edge")
    return index.astype(np.int64)


@dataclass(frozen=True)
class NestedLogFrequencyHierarchy:
    """每个基组含 2 个 pilot 子组和 4 个 master 子组的严格嵌套层级。"""

    base_edge_hz: NDArray[np.float64]
    pilot_edge_hz: NDArray[np.float64]
    master_edge_hz: NDArray[np.float64]
    pilot_children_per_base: int
    master_children_per_base: int


@dataclass(frozen=True)
class P0FrequencyTransferAudit:
    """P0 延拓或限制后的频带积分守恒审计。"""

    group_edge_hz: NDArray[np.float64]
    mean_intensity_density: NDArray[np.float64]
    source_integral: NDArray[np.float64]
    target_integral: NDArray[np.float64]
    maximum_relative_integral_residual: float


@dataclass(frozen=True)
class EmbeddedP0FrequencyError:
    """master P0 相对基组平均表示的能量与 H/He 原子率缺陷。"""

    base_edge_hz: NDArray[np.float64]
    fine_edge_hz: NDArray[np.float64]
    fine_children_per_base: NDArray[np.int64]
    energy_l1_defect_fraction: NDArray[np.float64]
    rate_defect_fraction_by_species: NDArray[np.float64]
    positive_rate_sample_count_by_species: NDArray[np.int64]
    normalized_indicator: NDArray[np.float64]
    descending_parent_order: NDArray[np.int64]
    production_tolerance: float
    maximum_restriction_integral_residual: float
    quadrature_order_per_fine_group: int


@dataclass(frozen=True)
class BudgetedVariableFrequencyGrid:
    """按嵌入式缺陷排序，在叶自由度预算内选取 1 或 4 子组。"""

    base_edge_hz: NDArray[np.float64]
    master_edge_hz: NDArray[np.float64]
    group_edge_hz: NDArray[np.float64]
    child_groups_per_base: NDArray[np.int64]
    refined_parent_mask: NDArray[np.bool_]
    descending_parent_order: NDArray[np.int64]
    refined_parent_count: int
    leaf_group_count: int
    leaf_group_budget: int
    unused_leaf_budget: int
    maximum_unrefined_indicator: float
    minimum_refined_indicator: float | None


@dataclass(frozen=True)
class HierarchicalP0OptionError:
    """每个父带采用 1、2 或 4 个 P0 叶时的联合局域缺陷。"""

    base_edge_hz: NDArray[np.float64]
    pilot_edge_hz: NDArray[np.float64]
    master_edge_hz: NDArray[np.float64]
    option_leaf_counts: NDArray[np.int64]
    energy_defect_fraction_by_option: NDArray[np.float64]
    rate_defect_fraction_by_species_and_option: NDArray[np.float64]
    positive_rate_sample_count_by_species: NDArray[np.int64]
    normalized_score_by_option: NDArray[np.float64]
    production_tolerance: float
    quadrature_order_per_master_group: int


@dataclass(frozen=True)
class BudgetedHierarchicalP0Grid:
    """整数动态规划选出的严格 1--2--4 P0 叶网格。"""

    base_edge_hz: NDArray[np.float64]
    pilot_edge_hz: NDArray[np.float64]
    master_edge_hz: NDArray[np.float64]
    group_edge_hz: NDArray[np.float64]
    leaf_count_by_parent: NDArray[np.int64]
    option_index_by_parent: NDArray[np.int64]
    leaf_group_count: int
    leaf_group_budget: int
    option_parent_counts: NDArray[np.int64]
    objective_sum_normalized_local_defect: float
    maximum_selected_parent_score: float


def nested_log_frequency_hierarchy(
    base_group_edge_hz: ArrayLike,
) -> NestedLogFrequencyHierarchy:
    """在每个基组内按 ``ln(nu)`` 等距二分，构造 1--2--4 严格嵌套层。"""
    base = _positive_edges("base_group_edge_hz", base_group_edge_hz)
    master_pieces: list[NDArray[np.float64]] = []
    for index, (left, right) in enumerate(
        zip(base[:-1], base[1:], strict=True)
    ):
        local = np.exp(np.linspace(np.log(left), np.log(right), 5))
        local[0] = left
        local[-1] = right
        master_pieces.append(local if index == 0 else local[1:])
    master = np.concatenate(master_pieces)
    pilot = np.array(master[::2], copy=True)
    pilot[::2] = base
    master[::4] = base
    if (
        master.size != 4 * (base.size - 1) + 1
        or pilot.size != 2 * (base.size - 1) + 1
        or np.any(np.diff(master) <= 0.0)
        or np.any(np.diff(pilot) <= 0.0)
        or not np.array_equal(pilot[::2], base)
        or not np.array_equal(master[::2], pilot)
    ):
        raise ArithmeticError("nested log-frequency hierarchy became invalid")
    return NestedLogFrequencyHierarchy(
        base_edge_hz=_readonly(np.array(base, copy=True)),
        pilot_edge_hz=_readonly(pilot),
        master_edge_hz=_readonly(master),
        pilot_children_per_base=2,
        master_children_per_base=4,
    )


def _frequency_field(
    name: str, values: ArrayLike, group_count: int
) -> NDArray[np.float64]:
    field = np.asarray(values, dtype=np.float64)
    if (
        field.ndim < 1
        or field.shape[0] != group_count
        or not np.all(np.isfinite(field))
        or np.any(field < 0.0)
    ):
        raise PhysicalDomainError(
            f"{name} must be finite, non-negative and frequency-first"
        )
    return field


def _maximum_relative_residual(
    target: NDArray[np.float64], source: NDArray[np.float64]
) -> float:
    difference = np.abs(target - source)
    relative = np.empty_like(difference)
    nonzero = source != 0.0
    relative[nonzero] = difference[nonzero] / np.abs(source[nonzero])
    relative[~nonzero] = difference[~nonzero]
    return float(np.max(relative)) if relative.size else float(relative)


def prolong_piecewise_constant_frequency(
    coarse_group_edge_hz: ArrayLike,
    fine_group_edge_hz: ArrayLike,
    coarse_mean_intensity_density: ArrayLike,
) -> P0FrequencyTransferAudit:
    """把基组 P0 常数值复制到严格嵌套子组，并审计频带积分。"""
    coarse_edge = _positive_edges("coarse_group_edge_hz", coarse_group_edge_hz)
    fine_edge = _positive_edges("fine_group_edge_hz", fine_group_edge_hz)
    offsets = _nested_offsets(coarse_edge, fine_edge)
    coarse = _frequency_field(
        "coarse_mean_intensity_density",
        coarse_mean_intensity_density,
        coarse_edge.size - 1,
    )
    counts = np.diff(offsets)
    fine = np.repeat(coarse, counts, axis=0)
    trailing = (1,) * (fine.ndim - 1)
    source_integral = np.sum(
        coarse * np.diff(coarse_edge).reshape((-1, *trailing)), axis=0
    )
    target_integral = np.sum(
        fine * np.diff(fine_edge).reshape((-1, *trailing)), axis=0
    )
    return P0FrequencyTransferAudit(
        group_edge_hz=_readonly(np.array(fine_edge, copy=True)),
        mean_intensity_density=_readonly(fine),
        source_integral=_readonly(np.asarray(source_integral)),
        target_integral=_readonly(np.asarray(target_integral)),
        maximum_relative_integral_residual=_maximum_relative_residual(
            np.asarray(target_integral), np.asarray(source_integral)
        ),
    )


def restrict_piecewise_constant_frequency(
    fine_group_edge_hz: ArrayLike,
    coarse_group_edge_hz: ArrayLike,
    fine_mean_intensity_density: ArrayLike,
) -> P0FrequencyTransferAudit:
    """按真实 ``dnu`` 权重把严格嵌套细 P0 限制为基组平均。"""
    fine_edge = _positive_edges("fine_group_edge_hz", fine_group_edge_hz)
    coarse_edge = _positive_edges("coarse_group_edge_hz", coarse_group_edge_hz)
    offsets = _nested_offsets(coarse_edge, fine_edge)
    fine = _frequency_field(
        "fine_mean_intensity_density",
        fine_mean_intensity_density,
        fine_edge.size - 1,
    )
    trailing = (1,) * (fine.ndim - 1)
    fine_width = np.diff(fine_edge).reshape((-1, *trailing))
    coarse = np.empty((coarse_edge.size - 1, *fine.shape[1:]))
    for parent, (left, right) in enumerate(
        zip(offsets[:-1], offsets[1:], strict=True)
    ):
        coarse[parent] = np.sum(
            fine[left:right] * fine_width[left:right], axis=0
        ) / (coarse_edge[parent + 1] - coarse_edge[parent])
    source_integral = np.sum(fine * fine_width, axis=0)
    target_integral = np.sum(
        coarse
        * np.diff(coarse_edge).reshape((-1, *trailing)),
        axis=0,
    )
    return P0FrequencyTransferAudit(
        group_edge_hz=_readonly(np.array(coarse_edge, copy=True)),
        mean_intensity_density=_readonly(coarse),
        source_integral=_readonly(np.asarray(source_integral)),
        target_integral=_readonly(np.asarray(target_integral)),
        maximum_relative_integral_residual=_maximum_relative_residual(
            np.asarray(target_integral), np.asarray(source_integral)
        ),
    )


def _rate_coefficient_per_group(
    fine_edge_hz: NDArray[np.float64], quadrature_order: int, fit
) -> NDArray[np.float64]:
    node, weight = np.polynomial.legendre.leggauss(quadrature_order)
    log_edge = np.log(fine_edge_hz)
    centre = 0.5 * (log_edge[:-1] + log_edge[1:])
    half_width = 0.5 * np.diff(log_edge)
    log_node = centre[:, None] + half_width[:, None] * node[None, :]
    energy_ev = np.exp(log_node) * PLANCK_ERG_S / EV_ERG
    # 中文：在 dln(nu) 中率核为 4*pi*sigma/h；强度仍是每 Hz 的 P0 值。
    integrand = 4.0 * np.pi * fit.cross_section_cm2(energy_ev) / PLANCK_ERG_S
    coefficient = np.sum(half_width[:, None] * weight[None, :] * integrand, axis=1)
    if not np.all(np.isfinite(coefficient)) or np.any(coefficient < 0.0):
        raise ArithmeticError("photoionization rate coefficients became invalid")
    return coefficient


def piecewise_constant_photoionization_rates_s1(
    group_edge_hz: ArrayLike,
    mean_intensity_density: ArrayLike,
    *,
    quadrature_order_per_group: int = 8,
) -> NDArray[np.float64]:
    """直接积分 P0 ``J_nu`` 的 H I、He I、He II 光致电离率。"""
    edge = _positive_edges("group_edge_hz", group_edge_hz)
    if (
        not isinstance(quadrature_order_per_group, (int, np.integer))
        or isinstance(quadrature_order_per_group, (bool, np.bool_))
        or int(quadrature_order_per_group) < 2
    ):
        raise PhysicalDomainError("quadrature order must be an integer of at least two")
    intensity = _frequency_field(
        "mean_intensity_density", mean_intensity_density, edge.size - 1
    )
    coefficient = np.stack(
        [
            _rate_coefficient_per_group(
                edge, int(quadrature_order_per_group), fit
            )
            for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
        ]
    )
    rates = np.tensordot(coefficient, intensity, axes=(1, 0))
    if not np.all(np.isfinite(rates)) or np.any(rates < 0.0):
        raise ArithmeticError("piecewise-constant photoionization rates became invalid")
    return _readonly(np.asarray(rates))


def embedded_p0_frequency_error(
    base_group_edge_hz: ArrayLike,
    fine_group_edge_hz: ArrayLike,
    fine_mean_intensity_density: ArrayLike,
    *,
    production_tolerance: float = 1.0e-3,
    quadrature_order_per_fine_group: int = 8,
) -> EmbeddedP0FrequencyError:
    """由细 P0 与其基组平均的差构造无拟合能量/H/He 排序量。"""
    base_edge = _positive_edges("base_group_edge_hz", base_group_edge_hz)
    fine_edge = _positive_edges("fine_group_edge_hz", fine_group_edge_hz)
    offsets = _nested_offsets(base_edge, fine_edge)
    tolerance = float(production_tolerance)
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise PhysicalDomainError("production_tolerance must be finite and positive")
    if (
        not isinstance(quadrature_order_per_fine_group, (int, np.integer))
        or isinstance(quadrature_order_per_fine_group, (bool, np.bool_))
        or int(quadrature_order_per_fine_group) < 2
    ):
        raise PhysicalDomainError("quadrature order must be an integer of at least two")
    order = int(quadrature_order_per_fine_group)
    fine = _frequency_field(
        "fine_mean_intensity_density",
        fine_mean_intensity_density,
        fine_edge.size - 1,
    )
    restriction = restrict_piecewise_constant_frequency(
        fine_edge, base_edge, fine
    )
    prolongation = prolong_piecewise_constant_frequency(
        base_edge, fine_edge, restriction.mean_intensity_density
    )
    reconstructed = prolongation.mean_intensity_density
    sample_shape = fine.shape[1:]
    sample_count = int(np.prod(sample_shape)) if sample_shape else 1
    fine_flat = fine.reshape((fine.shape[0], sample_count))
    reconstructed_flat = reconstructed.reshape((fine.shape[0], sample_count))
    fine_width = np.diff(fine_edge)
    total_energy = np.sum(fine_flat * fine_width[:, None], axis=0)
    if np.any(total_energy <= 0.0):
        raise PhysicalDomainError("each embedded-error sample must have positive energy")
    parent_count = base_edge.size - 1
    energy_defect = np.empty(parent_count)
    for parent, (left, right) in enumerate(
        zip(offsets[:-1], offsets[1:], strict=True)
    ):
        local = np.sum(
            np.abs(fine_flat[left:right] - reconstructed_flat[left:right])
            * fine_width[left:right, None],
            axis=0,
        ) / total_energy
        energy_defect[parent] = float(np.max(local))

    rate_defect = np.empty(
        (len(H_HE_GROUND_STATE_PHOTOIONIZATION_FITS), parent_count)
    )
    positive_rate_count = np.empty(
        len(H_HE_GROUND_STATE_PHOTOIONIZATION_FITS), dtype=np.int64
    )
    for species, fit in enumerate(H_HE_GROUND_STATE_PHOTOIONIZATION_FITS):
        coefficient = _rate_coefficient_per_group(fine_edge, order, fit)
        total_rate = np.sum(coefficient[:, None] * fine_flat, axis=0)
        positive = total_rate > 0.0
        positive_rate_count[species] = int(np.count_nonzero(positive))
        for parent, (left, right) in enumerate(
            zip(offsets[:-1], offsets[1:], strict=True)
        ):
            signed = np.sum(
                coefficient[left:right, None]
                * (fine_flat[left:right] - reconstructed_flat[left:right]),
                axis=0,
            )
            # 中文：零参考率不加 floor；只有零率且零差才可从相对率指标中退出。
            if np.any(signed[~positive] != 0.0):
                raise PhysicalDomainError(
                    "zero reference rate has a non-zero reconstruction defect"
                )
            rate_defect[species, parent] = (
                float(np.max(np.abs(signed[positive]) / total_rate[positive]))
                if np.any(positive)
                else 0.0
            )
    indicator = np.maximum(energy_defect, np.max(rate_defect, axis=0)) / tolerance
    descending = np.argsort(-indicator, kind="stable")
    return EmbeddedP0FrequencyError(
        base_edge_hz=_readonly(np.array(base_edge, copy=True)),
        fine_edge_hz=_readonly(np.array(fine_edge, copy=True)),
        fine_children_per_base=_readonly(np.diff(offsets)),
        energy_l1_defect_fraction=_readonly(energy_defect),
        rate_defect_fraction_by_species=_readonly(rate_defect),
        positive_rate_sample_count_by_species=_readonly(positive_rate_count),
        normalized_indicator=_readonly(indicator),
        descending_parent_order=_readonly(descending),
        production_tolerance=tolerance,
        maximum_restriction_integral_residual=(
            restriction.maximum_relative_integral_residual
        ),
        quadrature_order_per_fine_group=order,
    )


def budgeted_variable_frequency_grid(
    error: EmbeddedP0FrequencyError,
    master_group_edge_hz: ArrayLike,
    leaf_group_budget: int,
) -> BudgetedVariableFrequencyGrid:
    """在 1/4 子组二选一的闭合层级中，按排序用尽可用完整细化块。"""
    if not isinstance(error, EmbeddedP0FrequencyError):
        raise TypeError("error must be an EmbeddedP0FrequencyError")
    if (
        not isinstance(leaf_group_budget, (int, np.integer))
        or isinstance(leaf_group_budget, (bool, np.bool_))
    ):
        raise PhysicalDomainError("leaf_group_budget must be an integer")
    budget = int(leaf_group_budget)
    base = error.base_edge_hz
    master = _positive_edges("master_group_edge_hz", master_group_edge_hz)
    offsets = _nested_offsets(base, master)
    counts = np.diff(offsets)
    if np.any(counts != 4):
        raise PhysicalDomainError("budgeted grid requires four master children per base")
    parent_count = base.size - 1
    if budget < parent_count or budget > 4 * parent_count:
        raise PhysicalDomainError(
            "leaf_group_budget must lie between base and master group counts"
        )
    refined_count = min(parent_count, (budget - parent_count) // 3)
    refined = np.zeros(parent_count, dtype=np.bool_)
    refined[error.descending_parent_order[:refined_count]] = True
    pieces: list[NDArray[np.float64]] = []
    child_count = np.ones(parent_count, dtype=np.int64)
    for parent in range(parent_count):
        if refined[parent]:
            left = int(offsets[parent])
            right = int(offsets[parent + 1])
            local = master[left : right + 1]
            child_count[parent] = 4
        else:
            local = base[parent : parent + 2]
        pieces.append(local if parent == 0 else local[1:])
    edge = np.concatenate(pieces)
    leaf_count = edge.size - 1
    if (
        leaf_count > budget
        or not np.array_equal(edge[np.searchsorted(edge, base)], base)
        or np.any(np.diff(edge) <= 0.0)
    ):
        raise ArithmeticError("budgeted variable frequency grid became invalid")
    unrefined = error.normalized_indicator[~refined]
    refined_value = error.normalized_indicator[refined]
    return BudgetedVariableFrequencyGrid(
        base_edge_hz=_readonly(np.array(base, copy=True)),
        master_edge_hz=_readonly(np.array(master, copy=True)),
        group_edge_hz=_readonly(edge),
        child_groups_per_base=_readonly(child_count),
        refined_parent_mask=_readonly(refined),
        descending_parent_order=_readonly(
            np.array(error.descending_parent_order, copy=True)
        ),
        refined_parent_count=refined_count,
        leaf_group_count=leaf_count,
        leaf_group_budget=budget,
        unused_leaf_budget=budget - leaf_count,
        maximum_unrefined_indicator=(
            float(np.max(unrefined)) if unrefined.size else 0.0
        ),
        minimum_refined_indicator=(
            float(np.min(refined_value)) if refined_value.size else None
        ),
    )


def hierarchical_p0_option_error(
    hierarchy: NestedLogFrequencyHierarchy,
    master_mean_intensity_density: ArrayLike,
    *,
    production_tolerance: float = 1.0e-3,
    quadrature_order_per_master_group: int = 8,
) -> HierarchicalP0OptionError:
    """计算 1、2、4 叶表示相对 master P0 的能量与 H/He 局域缺陷。"""
    if not isinstance(hierarchy, NestedLogFrequencyHierarchy):
        raise TypeError("hierarchy must be a NestedLogFrequencyHierarchy")
    tolerance = float(production_tolerance)
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise PhysicalDomainError("production_tolerance must be finite and positive")
    if (
        not isinstance(quadrature_order_per_master_group, (int, np.integer))
        or isinstance(quadrature_order_per_master_group, (bool, np.bool_))
        or int(quadrature_order_per_master_group) < 2
    ):
        raise PhysicalDomainError("quadrature order must be an integer of at least two")
    order = int(quadrature_order_per_master_group)
    base = _positive_edges("base_edge_hz", hierarchy.base_edge_hz)
    pilot = _positive_edges("pilot_edge_hz", hierarchy.pilot_edge_hz)
    master = _positive_edges("master_edge_hz", hierarchy.master_edge_hz)
    pilot_offsets = _nested_offsets(base, pilot)
    master_offsets = _nested_offsets(base, master)
    if np.any(np.diff(pilot_offsets) != 2) or np.any(
        np.diff(master_offsets) != 4
    ):
        raise PhysicalDomainError("hierarchy must provide two and four children")
    fine = _frequency_field(
        "master_mean_intensity_density",
        master_mean_intensity_density,
        master.size - 1,
    )
    sample_shape = fine.shape[1:]
    sample_count = int(np.prod(sample_shape)) if sample_shape else 1
    fine_flat = fine.reshape((fine.shape[0], sample_count))
    master_width = np.diff(master)
    total_energy = np.sum(fine_flat * master_width[:, None], axis=0)
    if np.any(total_energy <= 0.0):
        raise PhysicalDomainError("every training spectrum must have positive energy")

    fits = H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
    rate_coefficients = np.stack(
        [_rate_coefficient_per_group(master, order, fit) for fit in fits]
    )
    total_rates = np.einsum("fg,gs->fs", rate_coefficients, fine_flat)
    positive_rates = total_rates > 0.0
    positive_count = np.count_nonzero(positive_rates, axis=1).astype(np.int64)
    parent_count = base.size - 1
    option_leaf_counts = np.array([1, 2, 4], dtype=np.int64)
    energy_defect = np.empty((parent_count, 3), dtype=np.float64)
    rate_defect = np.empty((len(fits), parent_count, 3), dtype=np.float64)

    for parent, (left, right) in enumerate(
        zip(master_offsets[:-1], master_offsets[1:], strict=True)
    ):
        local = fine_flat[left:right]
        width = master_width[left:right]
        base_mean = np.sum(local * width[:, None], axis=0) / np.sum(width)
        reconstructed_base = np.broadcast_to(base_mean, local.shape)
        reconstructed_pilot = np.empty_like(local)
        for child_left, child_right in ((0, 2), (2, 4)):
            child_width = width[child_left:child_right]
            child_mean = np.sum(
                local[child_left:child_right] * child_width[:, None], axis=0
            ) / np.sum(child_width)
            reconstructed_pilot[child_left:child_right] = child_mean
        reconstructions = (reconstructed_base, reconstructed_pilot, local)
        for option, reconstructed in enumerate(reconstructions):
            difference = local - reconstructed
            local_energy = np.sum(
                np.abs(difference) * width[:, None], axis=0
            ) / total_energy
            energy_defect[parent, option] = float(np.max(local_energy))
            for species in range(len(fits)):
                signed = np.sum(
                    rate_coefficients[species, left:right, None] * difference,
                    axis=0,
                )
                if np.any(signed[~positive_rates[species]] != 0.0):
                    raise PhysicalDomainError(
                        "zero reference rate has a non-zero hierarchical defect"
                    )
                rate_defect[species, parent, option] = (
                    float(
                        np.max(
                            np.abs(signed[positive_rates[species]])
                            / total_rates[species, positive_rates[species]]
                        )
                    )
                    if np.any(positive_rates[species])
                    else 0.0
                )
    combined_rate = np.max(rate_defect, axis=0)
    score = np.maximum(energy_defect, combined_rate) / tolerance
    if (
        not np.all(np.isfinite(score))
        or np.any(score < 0.0)
        or np.any(score[:, 2] != 0.0)
    ):
        raise ArithmeticError("hierarchical option defects became invalid")
    return HierarchicalP0OptionError(
        base_edge_hz=_readonly(np.array(base, copy=True)),
        pilot_edge_hz=_readonly(np.array(pilot, copy=True)),
        master_edge_hz=_readonly(np.array(master, copy=True)),
        option_leaf_counts=_readonly(option_leaf_counts),
        energy_defect_fraction_by_option=_readonly(energy_defect),
        rate_defect_fraction_by_species_and_option=_readonly(rate_defect),
        positive_rate_sample_count_by_species=_readonly(positive_count),
        normalized_score_by_option=_readonly(score),
        production_tolerance=tolerance,
        quadrature_order_per_master_group=order,
    )


def budgeted_hierarchical_p0_grid(
    error: HierarchicalP0OptionError,
    leaf_group_budget: int,
) -> BudgetedHierarchicalP0Grid:
    """在精确叶预算下最小化 1--2--4 层级的联合局域缺陷和。"""
    if not isinstance(error, HierarchicalP0OptionError):
        raise TypeError("error must be a HierarchicalP0OptionError")
    if (
        not isinstance(leaf_group_budget, (int, np.integer))
        or isinstance(leaf_group_budget, (bool, np.bool_))
    ):
        raise PhysicalDomainError("leaf_group_budget must be an integer")
    budget = int(leaf_group_budget)
    parent_count = error.base_edge_hz.size - 1
    if budget < parent_count or budget > 4 * parent_count:
        raise PhysicalDomainError(
            "leaf_group_budget must lie between base and master group counts"
        )
    costs = error.option_leaf_counts
    score = error.normalized_score_by_option
    previous = np.full(budget + 1, np.inf)
    previous[0] = 0.0
    back_pointer = np.full((parent_count, budget + 1), -1, dtype=np.int8)
    for parent in range(parent_count):
        current = np.full(budget + 1, np.inf)
        for option, cost_value in enumerate(costs):
            cost = int(cost_value)
            candidate = previous[:-cost] + score[parent, option]
            target = current[cost:]
            better = candidate < target
            target[better] = candidate[better]
            back_pointer[parent, cost:][better] = option
        previous = current
    if not np.isfinite(previous[budget]):
        raise PhysicalDomainError("leaf_group_budget is not representable by 1-2-4 choices")

    option_index = np.empty(parent_count, dtype=np.int64)
    remaining = budget
    for parent in range(parent_count - 1, -1, -1):
        option = int(back_pointer[parent, remaining])
        if option < 0:
            raise ArithmeticError("hierarchical budget backtracking failed")
        option_index[parent] = option
        remaining -= int(costs[option])
    if remaining != 0:
        raise ArithmeticError("hierarchical budget did not backtrack to zero")
    leaf_count = costs[option_index]

    pilot_offsets = _nested_offsets(error.base_edge_hz, error.pilot_edge_hz)
    master_offsets = _nested_offsets(error.base_edge_hz, error.master_edge_hz)
    pieces: list[NDArray[np.float64]] = []
    for parent, leaves in enumerate(leaf_count):
        if leaves == 1:
            local = error.base_edge_hz[parent : parent + 2]
        elif leaves == 2:
            left = int(pilot_offsets[parent])
            right = int(pilot_offsets[parent + 1])
            local = error.pilot_edge_hz[left : right + 1]
        elif leaves == 4:
            left = int(master_offsets[parent])
            right = int(master_offsets[parent + 1])
            local = error.master_edge_hz[left : right + 1]
        else:
            raise ArithmeticError("hierarchical option has an invalid leaf count")
        pieces.append(local if parent == 0 else local[1:])
    edge = np.concatenate(pieces)
    if edge.size - 1 != budget or np.any(np.diff(edge) <= 0.0):
        raise ArithmeticError("hierarchical output grid violates its exact budget")
    selected_score = score[np.arange(parent_count), option_index]
    option_parent_counts = np.array(
        [np.count_nonzero(leaf_count == value) for value in costs],
        dtype=np.int64,
    )
    return BudgetedHierarchicalP0Grid(
        base_edge_hz=_readonly(np.array(error.base_edge_hz, copy=True)),
        pilot_edge_hz=_readonly(np.array(error.pilot_edge_hz, copy=True)),
        master_edge_hz=_readonly(np.array(error.master_edge_hz, copy=True)),
        group_edge_hz=_readonly(edge),
        leaf_count_by_parent=_readonly(np.array(leaf_count, copy=True)),
        option_index_by_parent=_readonly(option_index),
        leaf_group_count=int(edge.size - 1),
        leaf_group_budget=budget,
        option_parent_counts=_readonly(option_parent_counts),
        objective_sum_normalized_local_defect=float(previous[budget]),
        maximum_selected_parent_score=float(np.max(selected_score)),
    )
