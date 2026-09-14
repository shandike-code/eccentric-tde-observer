"""前沿感知的嵌入式误差估计与可变子单元网格。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .source import PhysicalDomainError
from .subcell_reconstruction import (
    conservative_linear_subcell_values,
    nested_mass_cell_offsets,
)


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class EmbeddedConservativeParentError:
    """细网格相对保守限制--再延拓表示的逐父单元缺陷。"""

    parent_mass_fraction_edges: NDArray[np.float64]
    pilot_mass_fraction_edges: NDArray[np.float64]
    pilot_cells_per_parent: NDArray[np.int64]
    log_temperature_error: NDArray[np.float64]
    log_opacity_error: NDArray[np.float64]
    hydrogen_ionized_error: NDArray[np.float64]
    helium_doubly_ionized_error: NDArray[np.float64]
    normalized_indicator: NDArray[np.float64]
    descending_parent_order: NDArray[np.int64]
    helium_iii_half_front_encountered: NDArray[np.bool_]
    production_tolerance: float
    maximum_parent_average_residual: float


@dataclass(frozen=True)
class FrontAwareVariableSubcellGrid:
    """按嵌入式缺陷排序选择父单元后的严格嵌套可变网格。"""

    parent_mass_fraction_edges: NDArray[np.float64]
    pilot_mass_fraction_edges: NDArray[np.float64]
    master_mass_fraction_edges: NDArray[np.float64]
    mass_fraction_edges: NDArray[np.float64]
    child_cells_per_parent: NDArray[np.int64]
    refined_parent_mask: NDArray[np.bool_]
    descending_parent_order: NDArray[np.int64]
    refined_parent_count: int
    effective_depth_points: int
    maximum_unrefined_indicator: float
    minimum_refined_indicator: float | None


def embedded_conservative_parent_error(
    parent_mass_fraction_edges: ArrayLike,
    pilot_mass_fraction_edges: ArrayLike,
    temperature_k: ArrayLike,
    rosseland_opacity_cm2_g: ArrayLike,
    hydrogen_ionized_fraction: ArrayLike,
    helium_doubly_ionized_fraction: ArrayLike,
    *,
    production_tolerance: float = 1.0e-3,
) -> EmbeddedConservativeParentError:
    """比较 pilot 与其父平均的受限线性再延拓，构造无拟合排序量。"""
    parent = np.asarray(parent_mass_fraction_edges, dtype=np.float64)
    pilot = np.asarray(pilot_mass_fraction_edges, dtype=np.float64)
    offsets = nested_mass_cell_offsets(parent, pilot)
    counts = np.diff(offsets)
    if np.any(counts != counts[0]) or counts[0] < 2:
        raise PhysicalDomainError(
            "embedded estimator requires a uniform pilot count of at least two"
        )
    tolerance = float(production_tolerance)
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise PhysicalDomainError("production_tolerance must be finite and positive")
    arrays = tuple(
        np.asarray(values, dtype=np.float64)
        for values in (
            temperature_k,
            rosseland_opacity_cm2_g,
            hydrogen_ionized_fraction,
            helium_doubly_ionized_fraction,
        )
    )
    expected_depth = pilot.size - 1
    if (
        any(array.ndim != 2 or array.shape[1] != expected_depth for array in arrays)
        or len({array.shape[0] for array in arrays}) != 1
        or any(not np.all(np.isfinite(array)) for array in arrays)
        or np.any(arrays[0] <= 0.0)
        or np.any(arrays[1] <= 0.0)
        or np.any(arrays[2] < 0.0)
        or np.any(arrays[2] > 1.0)
        or np.any(arrays[3] < 0.0)
        or np.any(arrays[3] > 1.0)
    ):
        raise PhysicalDomainError(
            "embedded estimator fields must be finite physical phase-depth arrays"
        )
    # 中文：正定热力学量用对数缺陷近似相对误差，人口仍用绝对缺陷。
    fields = (np.log(arrays[0]), np.log(arrays[1]), arrays[2], arrays[3])
    child_width = np.diff(pilot)
    parent_width = np.diff(parent)
    component_errors: list[NDArray[np.float64]] = []
    maximum_average_residual = 0.0
    for field in fields:
        # 中文：先严格限制到父平均，再用同一守恒延拓返回 pilot 网格。
        parent_average = np.empty((field.shape[0], counts.size), dtype=np.float64)
        for parent_index, (left, right) in enumerate(
            zip(offsets[:-1], offsets[1:], strict=True)
        ):
            parent_average[:, parent_index] = np.sum(
                field[:, left:right] * child_width[None, left:right], axis=1
            ) / parent_width[parent_index]
        reconstructed = conservative_linear_subcell_values(
            parent_average.T,
            parent,
            int(counts[0]),
            subcell_mass_fraction_edges=pilot,
        )
        maximum_average_residual = max(
            maximum_average_residual,
            reconstructed.maximum_parent_average_residual,
        )
        prolonged = reconstructed.values.T
        error = np.empty(counts.size, dtype=np.float64)
        for parent_index, (left, right) in enumerate(
            zip(offsets[:-1], offsets[1:], strict=True)
        ):
            error[parent_index] = np.max(
                np.abs(field[:, left:right] - prolonged[:, left:right])
            )
        component_errors.append(error)
    stacked = np.stack(component_errors)
    indicator = np.max(stacked / tolerance, axis=0)
    # 中文：稳定排序使相同缺陷的网格选择可复现，不引入后验权重拟合。
    order = np.argsort(-indicator, kind="stable")
    front = np.zeros(counts.size, dtype=np.bool_)
    he_iii = arrays[3]
    for parent_index, (left, right) in enumerate(
        zip(offsets[:-1], offsets[1:], strict=True)
    ):
        local = he_iii[:, left:right]
        front[parent_index] = bool(np.min(local) <= 0.5 <= np.max(local))
    return EmbeddedConservativeParentError(
        parent_mass_fraction_edges=_readonly(np.array(parent, copy=True)),
        pilot_mass_fraction_edges=_readonly(np.array(pilot, copy=True)),
        pilot_cells_per_parent=_readonly(np.array(counts, copy=True)),
        log_temperature_error=_readonly(component_errors[0]),
        log_opacity_error=_readonly(component_errors[1]),
        hydrogen_ionized_error=_readonly(component_errors[2]),
        helium_doubly_ionized_error=_readonly(component_errors[3]),
        normalized_indicator=_readonly(indicator),
        descending_parent_order=_readonly(order),
        helium_iii_half_front_encountered=_readonly(front),
        production_tolerance=tolerance,
        maximum_parent_average_residual=maximum_average_residual,
    )


def front_aware_variable_subcell_grid(
    error: EmbeddedConservativeParentError,
    master_mass_fraction_edges: ArrayLike,
    refined_parent_count: int,
) -> FrontAwareVariableSubcellGrid:
    """按误差排序细化指定数量的父单元，并保留全部 pilot 边界。"""
    if not isinstance(error, EmbeddedConservativeParentError):
        raise TypeError("error must be an EmbeddedConservativeParentError")
    if (
        not isinstance(refined_parent_count, (int, np.integer))
        or isinstance(refined_parent_count, (bool, np.bool_))
    ):
        raise PhysicalDomainError("refined_parent_count must be an integer")
    parent_count = error.pilot_cells_per_parent.size
    refined_count = int(refined_parent_count)
    if refined_count < 0 or refined_count > parent_count:
        raise PhysicalDomainError(
            "refined_parent_count must lie between zero and the parent count"
        )
    master = np.asarray(master_mass_fraction_edges, dtype=np.float64)
    master_offsets = nested_mass_cell_offsets(
        error.parent_mass_fraction_edges, master
    )
    master_counts = np.diff(master_offsets)
    if (
        np.any(error.pilot_cells_per_parent != 2)
        or np.any(master_counts != 4)
        or not np.array_equal(
            master[::2], error.pilot_mass_fraction_edges
        )
    ):
        raise PhysicalDomainError(
            "front-aware refinement requires nested two-cell pilot and four-cell master"
        )
    # 中文：被选父单元取 master 的四个真实自由度，其余保留 pilot 的两个。
    refined = np.zeros(parent_count, dtype=np.bool_)
    refined[error.descending_parent_order[:refined_count]] = True
    pieces: list[NDArray[np.float64]] = []
    counts = np.empty(parent_count, dtype=np.int64)
    pilot_offsets = nested_mass_cell_offsets(
        error.parent_mass_fraction_edges,
        error.pilot_mass_fraction_edges,
    )
    for parent_index in range(parent_count):
        if refined[parent_index]:
            left = int(master_offsets[parent_index])
            right = int(master_offsets[parent_index + 1])
            local = master[left : right + 1]
            counts[parent_index] = 4
        else:
            left = int(pilot_offsets[parent_index])
            right = int(pilot_offsets[parent_index + 1])
            local = error.pilot_mass_fraction_edges[left : right + 1]
            counts[parent_index] = 2
        pieces.append(local if parent_index == 0 else local[1:])
    edges = np.concatenate(pieces)
    if (
        not np.all(np.isfinite(edges))
        or np.any(np.diff(edges) <= 0.0)
    ):
        raise ArithmeticError("front-aware variable grid became invalid")
    nested_mass_cell_offsets(error.pilot_mass_fraction_edges, edges)
    unrefined = error.normalized_indicator[~refined]
    refined_values = error.normalized_indicator[refined]
    return FrontAwareVariableSubcellGrid(
        parent_mass_fraction_edges=_readonly(
            np.array(error.parent_mass_fraction_edges, copy=True)
        ),
        pilot_mass_fraction_edges=_readonly(
            np.array(error.pilot_mass_fraction_edges, copy=True)
        ),
        master_mass_fraction_edges=_readonly(np.array(master, copy=True)),
        mass_fraction_edges=_readonly(edges),
        child_cells_per_parent=_readonly(counts),
        refined_parent_mask=_readonly(refined),
        descending_parent_order=_readonly(
            np.array(error.descending_parent_order, copy=True)
        ),
        refined_parent_count=refined_count,
        effective_depth_points=int(np.sum(counts)),
        maximum_unrefined_indicator=(
            float(np.max(unrefined)) if unrefined.size else 0.0
        ),
        minimum_refined_indicator=(
            float(np.min(refined_values)) if refined_values.size else None
        ),
    )
