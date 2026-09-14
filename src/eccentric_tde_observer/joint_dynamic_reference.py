"""周期动态柱的联合深度--时间比较。

这里仅比较已经独立求解的有限分辨率轨道，不把高分辨率结果事后降采样
当作动力学收敛证据。温度、opacity 和通量使用相对误差，离子分数使用
绝对误差；移动 He III 半电离前沿另行保留状态与位置诊断。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class DynamicReferenceFields:
    """一个有限深度、有限相位周期解的准入字段。"""

    orbital_phase: NDArray[np.float64]
    mass_fraction_edges: NDArray[np.float64]
    cell_mass_g_cm2: NDArray[np.float64]
    temperature_k: NDArray[np.float64]
    rosseland_opacity_cm2_g: NDArray[np.float64]
    hydrogen_ionized_fraction: NDArray[np.float64]
    helium_doubly_ionized_fraction: NDArray[np.float64]
    surface_flux_erg_s_cm2: NDArray[np.float64]

    @property
    def phase_points(self) -> int:
        return int(self.orbital_phase.size)

    @property
    def depth_points(self) -> int:
        return int(self.mass_fraction_edges.size - 1)


@dataclass(frozen=True)
class JointDynamicError:
    """深度或时间轴上预先声明的联合误差指标。"""

    surface_flux_relative_error: float
    maximum_pointwise_temperature_or_opacity_relative_error: float
    maximum_pointwise_population_absolute_error: float
    maximum_column_mean_temperature_or_opacity_relative_error: float
    maximum_column_mean_population_absolute_error: float
    front_status_mismatch_phase_count: int
    joint_unique_front_phase_count: int
    maximum_he_iii_half_front_mass_fraction_error: float | None


def dynamic_reference_fields(
    orbital_phase: ArrayLike,
    mass_fraction_edges: ArrayLike,
    cell_mass_g_cm2: ArrayLike,
    temperature_k: ArrayLike,
    rosseland_opacity_cm2_g: ArrayLike,
    hydrogen_ionized_fraction: ArrayLike,
    helium_doubly_ionized_fraction: ArrayLike,
    surface_flux_erg_s_cm2: ArrayLike,
) -> DynamicReferenceFields:
    """验证并冻结联合准入所需字段。"""
    phase = np.array(orbital_phase, dtype=np.float64, copy=True)
    edges = np.array(mass_fraction_edges, dtype=np.float64, copy=True)
    cell_mass = np.array(cell_mass_g_cm2, dtype=np.float64, copy=True)
    temperature = np.array(temperature_k, dtype=np.float64, copy=True)
    opacity = np.array(rosseland_opacity_cm2_g, dtype=np.float64, copy=True)
    h_ii = np.array(hydrogen_ionized_fraction, dtype=np.float64, copy=True)
    he_iii = np.array(helium_doubly_ionized_fraction, dtype=np.float64, copy=True)
    flux = np.array(surface_flux_erg_s_cm2, dtype=np.float64, copy=True)
    if (
        phase.ndim != 1
        or phase.size < 2
        or not np.all(np.isfinite(phase))
        or phase[0] != 0.0
        or np.any(np.diff(phase) <= 0.0)
        or phase[-1] >= 1.0
    ):
        raise PhysicalDomainError(
            "orbital_phase must be finite, increasing and span one open periodic cycle"
        )
    if (
        edges.ndim != 1
        or edges.size < 2
        or not np.all(np.isfinite(edges))
        or edges[0] != 0.0
        or edges[-1] != 1.0
        or np.any(np.diff(edges) <= 0.0)
    ):
        raise PhysicalDomainError(
            "mass_fraction_edges must be finite, increasing and span [0, 1]"
        )
    shape = (phase.size, edges.size - 1)
    if cell_mass.shape != (edges.size - 1,):
        raise PhysicalDomainError("cell_mass_g_cm2 must match the depth grid")
    if any(field.shape != shape for field in (temperature, opacity, h_ii, he_iii)):
        raise PhysicalDomainError("dynamic fields must share the phase-depth grid")
    if flux.shape != (phase.size,):
        raise PhysicalDomainError("surface flux must match the phase grid")
    arrays = (cell_mass, temperature, opacity, h_ii, he_iii, flux)
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise PhysicalDomainError("dynamic reference fields must be finite")
    if (
        np.any(cell_mass <= 0.0)
        or np.any(temperature <= 0.0)
        or np.any(opacity <= 0.0)
        or np.any(flux <= 0.0)
        or np.any(h_ii < 0.0)
        or np.any(h_ii > 1.0)
        or np.any(he_iii < 0.0)
        or np.any(he_iii > 1.0)
    ):
        raise PhysicalDomainError("dynamic reference fields lie outside their domains")
    return DynamicReferenceFields(
        orbital_phase=_readonly(phase),
        mass_fraction_edges=_readonly(edges),
        cell_mass_g_cm2=_readonly(cell_mass),
        temperature_k=_readonly(temperature),
        rosseland_opacity_cm2_g=_readonly(opacity),
        hydrogen_ionized_fraction=_readonly(h_ii),
        helium_doubly_ionized_fraction=_readonly(he_iii),
        surface_flux_erg_s_cm2=_readonly(flux),
    )


def _periodic_interpolate(
    source_phase: NDArray[np.float64],
    target_phase: NDArray[np.float64],
    values: NDArray[np.float64],
) -> NDArray[np.float64]:
    if values.ndim == 1:
        return np.interp(target_phase, source_phase, values, period=1.0)
    result = np.empty((target_phase.size, values.shape[1]), dtype=np.float64)
    for depth in range(values.shape[1]):
        result[:, depth] = np.interp(
            target_phase, source_phase, values[:, depth], period=1.0
        )
    return result


def resample_periodic_dynamic_fields(
    fields: DynamicReferenceFields,
    target_orbital_phase: ArrayLike,
) -> DynamicReferenceFields:
    """以周期线性插值把一个独立解映射到指定比较相位。"""
    if not isinstance(fields, DynamicReferenceFields):
        raise TypeError("fields must be DynamicReferenceFields")
    target = np.array(target_orbital_phase, dtype=np.float64, copy=True)
    return dynamic_reference_fields(
        target,
        fields.mass_fraction_edges,
        fields.cell_mass_g_cm2,
        _periodic_interpolate(fields.orbital_phase, target, fields.temperature_k),
        _periodic_interpolate(
            fields.orbital_phase, target, fields.rosseland_opacity_cm2_g
        ),
        _periodic_interpolate(
            fields.orbital_phase, target, fields.hydrogen_ionized_fraction
        ),
        _periodic_interpolate(
            fields.orbital_phase,
            target,
            fields.helium_doubly_ionized_fraction,
        ),
        _periodic_interpolate(
            fields.orbital_phase, target, fields.surface_flux_erg_s_cm2
        ),
    )


def _front_locations(
    edges: NDArray[np.float64], he_iii: NDArray[np.float64]
) -> tuple[list[str], list[float | None]]:
    centres = 0.5 * (edges[:-1] + edges[1:])
    statuses: list[str] = []
    locations: list[float | None] = []
    for fraction in he_iii:
        residual = fraction - 0.5
        if np.all(residual > 0.0):
            statuses.append("all_above_half")
            locations.append(None)
            continue
        if np.all(residual < 0.0):
            statuses.append("all_below_half")
            locations.append(None)
            continue
        crossing = np.flatnonzero(residual[:-1] * residual[1:] <= 0.0)
        if crossing.size != 1:
            statuses.append("non_unique_crossing")
            locations.append(None)
            continue
        index = int(crossing[0])
        step = fraction[index + 1] - fraction[index]
        if step == 0.0:
            statuses.append("flat_half_plateau")
            locations.append(None)
            continue
        location = centres[index] + (
            (0.5 - fraction[index])
            / step
            * (centres[index + 1] - centres[index])
        )
        statuses.append("unique_crossing")
        locations.append(float(location))
    return statuses, locations


def _column_means(fields: DynamicReferenceFields) -> tuple[NDArray, ...]:
    weight = fields.cell_mass_g_cm2 / np.sum(fields.cell_mass_g_cm2)
    return tuple(
        np.sum(values * weight[None, :], axis=1)
        for values in (
            fields.temperature_k,
            fields.rosseland_opacity_cm2_g,
            fields.hydrogen_ionized_fraction,
            fields.helium_doubly_ionized_fraction,
        )
    )


def _shared_error(
    candidate: DynamicReferenceFields,
    reference: DynamicReferenceFields,
    pointwise_temperature_or_opacity_error: float,
    pointwise_population_error: float,
) -> JointDynamicError:
    candidate_means = _column_means(candidate)
    reference_means = _column_means(reference)
    mean_relative = max(
        float(np.max(np.abs(value - target) / np.abs(target)))
        for value, target in zip(
            candidate_means[:2], reference_means[:2], strict=True
        )
    )
    mean_population = max(
        float(np.max(np.abs(value - target)))
        for value, target in zip(
            candidate_means[2:], reference_means[2:], strict=True
        )
    )
    statuses, locations = _front_locations(
        candidate.mass_fraction_edges,
        candidate.helium_doubly_ionized_fraction,
    )
    reference_statuses, reference_locations = _front_locations(
        reference.mass_fraction_edges,
        reference.helium_doubly_ionized_fraction,
    )
    mismatch = sum(
        status != reference_status
        for status, reference_status in zip(
            statuses, reference_statuses, strict=True
        )
    )
    front_errors = [
        abs(float(location) - float(reference_location))
        for status, location, reference_status, reference_location in zip(
            statuses,
            locations,
            reference_statuses,
            reference_locations,
            strict=True,
        )
        if status == "unique_crossing"
        and reference_status == "unique_crossing"
        and location is not None
        and reference_location is not None
    ]
    return JointDynamicError(
        surface_flux_relative_error=float(
            np.max(
                np.abs(
                    candidate.surface_flux_erg_s_cm2
                    - reference.surface_flux_erg_s_cm2
                )
                / np.abs(reference.surface_flux_erg_s_cm2)
            )
        ),
        maximum_pointwise_temperature_or_opacity_relative_error=(
            pointwise_temperature_or_opacity_error
        ),
        maximum_pointwise_population_absolute_error=pointwise_population_error,
        maximum_column_mean_temperature_or_opacity_relative_error=mean_relative,
        maximum_column_mean_population_absolute_error=mean_population,
        front_status_mismatch_phase_count=mismatch,
        joint_unique_front_phase_count=len(front_errors),
        maximum_he_iii_half_front_mass_fraction_error=(
            max(front_errors) if front_errors else None
        ),
    )


def compare_periodic_time_resolution(
    candidate: DynamicReferenceFields,
    reference: DynamicReferenceFields,
) -> JointDynamicError:
    """比较相同深度网格上的两个独立时间分辨率解。"""
    if not isinstance(candidate, DynamicReferenceFields) or not isinstance(
        reference, DynamicReferenceFields
    ):
        raise TypeError("candidate and reference must be DynamicReferenceFields")
    if not np.array_equal(
        candidate.mass_fraction_edges, reference.mass_fraction_edges
    ):
        raise PhysicalDomainError("time comparison requires identical depth edges")
    aligned = resample_periodic_dynamic_fields(
        candidate, reference.orbital_phase
    )
    relative = max(
        float(np.max(np.abs(value - target) / np.abs(target)))
        for value, target in (
            (aligned.temperature_k, reference.temperature_k),
            (
                aligned.rosseland_opacity_cm2_g,
                reference.rosseland_opacity_cm2_g,
            ),
        )
    )
    population = max(
        float(np.max(np.abs(value - target)))
        for value, target in (
            (
                aligned.hydrogen_ionized_fraction,
                reference.hydrogen_ionized_fraction,
            ),
            (
                aligned.helium_doubly_ionized_fraction,
                reference.helium_doubly_ionized_fraction,
            ),
        )
    )
    return _shared_error(aligned, reference, relative, population)


def compare_nested_depth_resolution(
    candidate: DynamicReferenceFields,
    reference: DynamicReferenceFields,
    *,
    probe_points_per_parent: int = 65,
) -> JointDynamicError:
    """比较同一相位网格上的严格嵌套深度解。"""
    if not isinstance(candidate, DynamicReferenceFields) or not isinstance(
        reference, DynamicReferenceFields
    ):
        raise TypeError("candidate and reference must be DynamicReferenceFields")
    if not np.array_equal(candidate.orbital_phase, reference.orbital_phase):
        raise PhysicalDomainError("depth comparison requires identical phase points")
    if (
        not isinstance(probe_points_per_parent, (int, np.integer))
        or isinstance(probe_points_per_parent, (bool, np.bool_))
        or int(probe_points_per_parent) < 2
    ):
        raise PhysicalDomainError("probe_points_per_parent must be at least two")
    offsets = np.searchsorted(
        reference.mass_fraction_edges, candidate.mass_fraction_edges
    )
    if (
        offsets[0] != 0
        or offsets[-1] != reference.depth_points
        or not np.array_equal(
            reference.mass_fraction_edges[offsets],
            candidate.mass_fraction_edges,
        )
    ):
        raise PhysicalDomainError(
            "candidate depth edges must be a strict subset of reference edges"
        )
    candidate_mass = 0.5 * (
        candidate.mass_fraction_edges[:-1] + candidate.mass_fraction_edges[1:]
    )
    reference_mass = 0.5 * (
        reference.mass_fraction_edges[:-1] + reference.mass_fraction_edges[1:]
    )
    lower = max(float(candidate_mass[0]), float(reference_mass[0]))
    upper = min(float(candidate_mass[-1]), float(reference_mass[-1]))
    probe = np.linspace(
        lower,
        upper,
        candidate.depth_points * (int(probe_points_per_parent) - 1) + 1,
    )
    relative = 0.0
    population = 0.0
    for phase in range(reference.phase_points):
        for field_index, (value, target) in enumerate(
            zip(
                (
                    candidate.temperature_k,
                    candidate.rosseland_opacity_cm2_g,
                    candidate.hydrogen_ionized_fraction,
                    candidate.helium_doubly_ionized_fraction,
                ),
                (
                    reference.temperature_k,
                    reference.rosseland_opacity_cm2_g,
                    reference.hydrogen_ionized_fraction,
                    reference.helium_doubly_ionized_fraction,
                ),
                strict=True,
            )
        ):
            candidate_value = np.interp(probe, candidate_mass, value[phase])
            reference_value = np.interp(probe, reference_mass, target[phase])
            if field_index < 2:
                relative = max(
                    relative,
                    float(
                        np.max(
                            np.abs(candidate_value - reference_value)
                            / np.abs(reference_value)
                        )
                    ),
                )
            else:
                population = max(
                    population,
                    float(np.max(np.abs(candidate_value - reference_value))),
                )
    return _shared_error(candidate, reference, relative, population)


def joint_dynamic_error_meets_target(
    error: JointDynamicError,
    production_tolerance: float,
) -> bool:
    """按同一阈值审计全部连续指标，并要求前沿状态完全一致。"""
    if not isinstance(error, JointDynamicError):
        raise TypeError("error must be JointDynamicError")
    tolerance = float(production_tolerance)
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise PhysicalDomainError("production_tolerance must be finite and positive")
    values = (
        error.surface_flux_relative_error,
        error.maximum_pointwise_temperature_or_opacity_relative_error,
        error.maximum_pointwise_population_absolute_error,
        error.maximum_column_mean_temperature_or_opacity_relative_error,
        error.maximum_column_mean_population_absolute_error,
    )
    front_error = error.maximum_he_iii_half_front_mass_fraction_error
    return bool(
        all(value < tolerance for value in values)
        and error.front_status_mismatch_phase_count == 0
        and (front_error is None or front_error < tolerance)
    )
