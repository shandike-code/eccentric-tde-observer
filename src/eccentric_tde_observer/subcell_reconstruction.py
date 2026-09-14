"""周期动态柱的保守拉格朗日子单元表示。

父单元只用于组织误差与守恒账本；实际子单元状态在完成初始延拓后由
周期动态求解器独立保存和推进。这里不把子单元自由度冒充为高阶闭合，
也不以裁剪或事后重归一化修复越界人口。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import brentq

from .atmosphere import (
    PROTON_MASS_G,
    SOLAR_FULLY_IONIZED_H_HE,
    FullyIonizedHydrogenHeliumComposition,
)
from .non_gray import (
    HELIUM_II_IONIZATION_ERG,
    HELIUM_I_IONIZATION_ERG,
    HYDROGEN_IONIZATION_ERG,
)
from .periodic_dynamic_atmosphere import (
    PeriodicDynamicColumnSolution,
    PeriodicDynamicHalfColumn,
    ground_state_thermodynamics,
)
from .radiation import (
    BOLTZMANN_ERG_K,
    LIGHT_SPEED_CM_S,
    STEFAN_BOLTZMANN_ERG_S_CM2_K4,
)
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class ConservativeLinearSubcells:
    """一个或多个父单元平均量的受限线性子单元表示。"""

    parent_mass_fraction_edges: NDArray[np.float64]
    subcell_mass_fraction_edges: NDArray[np.float64]
    subcell_mass_fraction_centres: NDArray[np.float64]
    subcells_per_parent: int
    values: NDArray[np.float64]
    limiter_fraction: NDArray[np.float64]
    maximum_parent_average_residual: float


@dataclass(frozen=True)
class ConservativeGroundStateSubcells:
    """守恒总比能与 H/He 粒子数的物理子单元初态。"""

    parent_mass_fraction_edges: NDArray[np.float64]
    subcell_mass_fraction_edges: NDArray[np.float64]
    subcells_per_parent: int
    temperature_k: NDArray[np.float64]
    hydrogen_fraction: NDArray[np.float64]
    helium_fraction: NDArray[np.float64]
    specific_total_energy_erg_g: NDArray[np.float64]
    limiter_fraction: NDArray[np.float64]
    maximum_parent_mass_residual: float
    maximum_hydrogen_particle_residual: float
    maximum_helium_particle_residual: float
    maximum_hydrogen_stage_absolute_residual: float
    maximum_helium_stage_absolute_residual: float
    maximum_charge_residual: float
    maximum_specific_energy_residual: float


@dataclass(frozen=True)
class ConservativeSubcellRestriction:
    """把完整周期子单元解限制回父单元后的守恒诊断。"""

    parent_temperature_k: NDArray[np.float64]
    parent_hydrogen_fraction: NDArray[np.float64]
    parent_helium_fraction: NDArray[np.float64]
    parent_specific_total_energy_erg_g: NDArray[np.float64]
    parent_rosseland_opacity_cm2_g: NDArray[np.float64]
    parent_outward_flux_edges_erg_s_cm2: NDArray[np.float64]
    maximum_parent_mass_residual: float
    maximum_hydrogen_particle_residual: float
    maximum_helium_particle_residual: float
    maximum_hydrogen_stage_absolute_residual: float
    maximum_helium_stage_absolute_residual: float
    maximum_charge_residual: float
    maximum_specific_energy_residual: float
    maximum_optical_depth_residual: float
    maximum_face_flux_divergence_residual: float


@dataclass(frozen=True)
class ConservativeCoarsenedGroundState:
    """把细子单元初态合并到任意严格嵌套粗网格后的守恒状态。"""

    source_mass_fraction_edges: NDArray[np.float64]
    coarsened_mass_fraction_edges: NDArray[np.float64]
    source_cells_per_coarsened_cell: NDArray[np.int64]
    temperature_k: NDArray[np.float64]
    hydrogen_fraction: NDArray[np.float64]
    helium_fraction: NDArray[np.float64]
    specific_total_energy_erg_g: NDArray[np.float64]
    maximum_mass_residual: float
    maximum_hydrogen_particle_residual: float
    maximum_helium_particle_residual: float
    maximum_hydrogen_stage_absolute_residual: float
    maximum_helium_stage_absolute_residual: float
    maximum_charge_residual: float
    maximum_specific_energy_residual: float


@dataclass(frozen=True)
class ConservativeVariableSubcellRestriction:
    """把每个父单元含不同子单元数的周期解限制回父网格。"""

    child_cells_per_parent: NDArray[np.int64]
    parent_temperature_k: NDArray[np.float64]
    parent_hydrogen_fraction: NDArray[np.float64]
    parent_helium_fraction: NDArray[np.float64]
    parent_specific_total_energy_erg_g: NDArray[np.float64]
    parent_rosseland_opacity_cm2_g: NDArray[np.float64]
    parent_outward_flux_edges_erg_s_cm2: NDArray[np.float64]
    maximum_parent_mass_residual: float
    maximum_hydrogen_particle_residual: float
    maximum_helium_particle_residual: float
    maximum_hydrogen_stage_absolute_residual: float
    maximum_helium_stage_absolute_residual: float
    maximum_charge_residual: float
    maximum_specific_energy_residual: float
    maximum_optical_depth_residual: float
    maximum_face_flux_divergence_residual: float


def _validated_parent_edges(edges: ArrayLike) -> NDArray[np.float64]:
    result = np.array(edges, dtype=np.float64, copy=True)
    if (
        result.ndim != 1
        or result.size < 2
        or not np.all(np.isfinite(result))
        or result[0] != 0.0
        or result[-1] != 1.0
        or np.any(np.diff(result) <= 0.0)
    ):
        raise PhysicalDomainError(
            "parent mass-fraction edges must be finite, increasing and span [0, 1]"
        )
    return result


def _validated_subcell_count(subcells_per_parent: int) -> int:
    if (
        not isinstance(subcells_per_parent, (int, np.integer))
        or isinstance(subcells_per_parent, (bool, np.bool_))
        or int(subcells_per_parent) < 2
    ):
        raise PhysicalDomainError("subcells_per_parent must be an integer of at least two")
    return int(subcells_per_parent)


def nested_mass_cell_offsets(
    parent_mass_fraction_edges: ArrayLike,
    child_mass_fraction_edges: ArrayLike,
) -> NDArray[np.int64]:
    """返回每条父边界在严格嵌套子边界中的索引。"""
    parent = _validated_parent_edges(parent_mass_fraction_edges)
    child = _validated_parent_edges(child_mass_fraction_edges)
    offsets = np.searchsorted(child, parent).astype(np.int64)
    if (
        offsets[0] != 0
        or offsets[-1] != child.size - 1
        or not np.array_equal(child[offsets], parent)
        or np.any(np.diff(offsets) < 1)
    ):
        raise PhysicalDomainError(
            "child mass-fraction edges must preserve every parent edge exactly"
        )
    return _readonly(offsets)


def uniform_mass_subcell_edges(
    parent_mass_fraction_edges: ArrayLike,
    subcells_per_parent: int,
) -> NDArray[np.float64]:
    """在每个父单元内按质量等分，且逐位保留全部父边界。"""
    parent = _validated_parent_edges(parent_mass_fraction_edges)
    count = _validated_subcell_count(subcells_per_parent)
    pieces: list[NDArray[np.float64]] = []
    for index, (left, right) in enumerate(
        zip(parent[:-1], parent[1:], strict=True)
    ):
        local = left + (right - left) * np.arange(count + 1, dtype=np.float64) / count
        pieces.append(local if index == 0 else local[1:])
    edges = np.concatenate(pieces)
    edges[0] = 0.0
    edges[-1] = 1.0
    if np.any(np.diff(edges) <= 0.0):
        raise ArithmeticError("uniform mass subcell edges became non-increasing")
    return _readonly(edges)


def _validated_nested_subcell_edges(
    parent_edges: NDArray[np.float64],
    subcell_edges: ArrayLike,
    subcells_per_parent: int,
) -> NDArray[np.float64]:
    child = _validated_parent_edges(subcell_edges)
    parent_count = parent_edges.size - 1
    if child.size != parent_count * subcells_per_parent + 1:
        raise PhysicalDomainError(
            "subcell edges must provide the declared count inside every parent"
        )
    if not np.array_equal(child[::subcells_per_parent], parent_edges):
        raise PhysicalDomainError("subcell edges must preserve every parent edge exactly")
    return child


def _minmod(left: NDArray[np.float64], right: NDArray[np.float64]) -> NDArray[np.float64]:
    result = np.zeros_like(left)
    same_sign = ((left > 0.0) & (right > 0.0)) | (
        (left < 0.0) & (right < 0.0)
    )
    result[same_sign] = np.sign(left[same_sign]) * np.minimum(
        np.abs(left[same_sign]), np.abs(right[same_sign])
    )
    return result


def _linear_subcell_increments(
    parent_values: NDArray[np.float64],
    parent_edges: NDArray[np.float64],
    subcells_per_parent: int,
    subcell_edges: NDArray[np.float64] | None = None,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    parent_centres = 0.5 * (parent_edges[:-1] + parent_edges[1:])
    if subcell_edges is None:
        subcell_edges = uniform_mass_subcell_edges(parent_edges, subcells_per_parent)
    else:
        subcell_edges = _validated_nested_subcell_edges(
            parent_edges, subcell_edges, subcells_per_parent
        )
    subcell_centres = 0.5 * (subcell_edges[:-1] + subcell_edges[1:])
    parent_count, component_count = parent_values.shape
    slopes = np.zeros((parent_count, component_count), dtype=np.float64)
    if parent_count > 1:
        slopes[0] = (parent_values[1] - parent_values[0]) / (
            parent_centres[1] - parent_centres[0]
        )
        slopes[-1] = (parent_values[-1] - parent_values[-2]) / (
            parent_centres[-1] - parent_centres[-2]
        )
    if parent_count > 2:
        backward = (parent_values[1:-1] - parent_values[:-2]) / (
            parent_centres[1:-1, None] - parent_centres[:-2, None]
        )
        forward = (parent_values[2:] - parent_values[1:-1]) / (
            parent_centres[2:, None] - parent_centres[1:-1, None]
        )
        slopes[1:-1] = _minmod(backward, forward)
    child_centres = subcell_centres.reshape(parent_count, subcells_per_parent)
    increments = (
        child_centres[:, :, None] - parent_centres[:, None, None]
    ) * slopes[:, None, :]
    return subcell_edges, subcell_centres, increments


def _limited_fraction(
    base: float,
    increment: float,
    current: float,
    *,
    strictly_positive: bool,
) -> float:
    """返回保持 ``base + theta*increment`` 非负的最大可用 theta。"""
    candidate = base + current * increment
    invalid = candidate <= 0.0 if strictly_positive else candidate < 0.0
    if not invalid:
        return current
    if base < 0.0 or (strictly_positive and base <= 0.0):
        raise PhysicalDomainError("parent state lies outside a reconstruction domain")
    if increment >= 0.0:
        raise ArithmeticError("subcell limiter could not restore a physical state")
    bound = base / (-increment)
    if bound <= 0.0:
        return 0.0
    # 中文：只退一个浮点数间隔以留在解析凸域内部；这不是物理 floor。
    usable = np.nextafter(bound, 0.0)
    return min(current, float(usable))


def conservative_linear_subcell_values(
    parent_values: ArrayLike,
    parent_mass_fraction_edges: ArrayLike,
    subcells_per_parent: int,
    *,
    subcell_mass_fraction_edges: ArrayLike | None = None,
    lower_bound: float | None = None,
    upper_bound: float | None = None,
) -> ConservativeLinearSubcells:
    """以公共凸限制器延拓父单元平均量，并逐父单元严格回收平均。"""
    parent_edges = _validated_parent_edges(parent_mass_fraction_edges)
    count = _validated_subcell_count(subcells_per_parent)
    values = np.asarray(parent_values, dtype=np.float64)
    scalar = values.ndim == 1
    if scalar:
        values = values[:, None]
    if (
        values.ndim != 2
        or values.shape[0] != parent_edges.size - 1
        or not np.all(np.isfinite(values))
    ):
        raise PhysicalDomainError("parent_values must be finite and share the parent cells")
    lower = None if lower_bound is None else float(lower_bound)
    upper = None if upper_bound is None else float(upper_bound)
    if lower is not None and (not np.isfinite(lower) or np.any(values < lower)):
        raise PhysicalDomainError("parent values violate the declared lower bound")
    if upper is not None and (not np.isfinite(upper) or np.any(values > upper)):
        raise PhysicalDomainError("parent values violate the declared upper bound")
    if lower is not None and upper is not None and upper <= lower:
        raise PhysicalDomainError("upper_bound must exceed lower_bound")

    explicit_child_edges = (
        None
        if subcell_mass_fraction_edges is None
        else _validated_nested_subcell_edges(
            parent_edges, subcell_mass_fraction_edges, count
        )
    )
    child_edges, child_centres, increments = _linear_subcell_increments(
        values, parent_edges, count, explicit_child_edges
    )
    theta = np.ones(values.shape[0], dtype=np.float64)
    for parent in range(values.shape[0]):
        for child in range(count):
            for component in range(values.shape[1]):
                base = float(values[parent, component])
                delta = float(increments[parent, child, component])
                if lower is not None:
                    theta[parent] = _limited_fraction(
                        base - lower,
                        delta,
                        float(theta[parent]),
                        strictly_positive=False,
                    )
                if upper is not None:
                    theta[parent] = _limited_fraction(
                        upper - base,
                        -delta,
                        float(theta[parent]),
                        strictly_positive=False,
                    )
    reconstructed = values[:, None, :] + theta[:, None, None] * increments
    if lower is not None and np.any(reconstructed < lower):
        raise ArithmeticError("limited subcell value fell below its lower bound")
    if upper is not None and np.any(reconstructed > upper):
        raise ArithmeticError("limited subcell value exceeded its upper bound")
    child_width = np.diff(child_edges).reshape(values.shape[0], count)
    parent_width = np.diff(parent_edges)
    weight = child_width / parent_width[:, None]
    recovered = np.sum(reconstructed * weight[:, :, None], axis=1)
    difference = np.abs(recovered - values)
    scale = np.abs(recovered) + np.abs(values)
    residual = np.zeros_like(difference)
    nonzero = scale > 0.0
    residual[nonzero] = 2.0 * difference[nonzero] / scale[nonzero]
    if np.any(~nonzero & (difference != 0.0)):
        raise ArithmeticError("zero parent average was not recovered exactly")
    flattened = reconstructed.reshape(-1, reconstructed.shape[-1])
    if scalar:
        flattened = flattened[:, 0]
    return ConservativeLinearSubcells(
        parent_mass_fraction_edges=_readonly(parent_edges),
        subcell_mass_fraction_edges=child_edges,
        subcell_mass_fraction_centres=_readonly(child_centres),
        subcells_per_parent=count,
        values=_readonly(np.array(flattened, copy=True)),
        limiter_fraction=_readonly(theta),
        maximum_parent_average_residual=float(np.max(residual)),
    )


def _composition_coefficients(
    composition: FullyIonizedHydrogenHeliumComposition,
) -> tuple[float, float, float]:
    hydrogen_per_gram = composition.hydrogen_mass_fraction / PROTON_MASS_G
    helium_per_gram = composition.helium_mass_fraction / (4.0 * PROTON_MASS_G)
    return hydrogen_per_gram, helium_per_gram, hydrogen_per_gram + helium_per_gram


def _specific_ionization_energy_erg_g(
    hydrogen_ionized: NDArray[np.float64],
    helium_singly_ionized: NDArray[np.float64],
    helium_doubly_ionized: NDArray[np.float64],
    composition: FullyIonizedHydrogenHeliumComposition,
) -> NDArray[np.float64]:
    hydrogen_per_gram, helium_per_gram, _ = _composition_coefficients(composition)
    return (
        hydrogen_per_gram * hydrogen_ionized * HYDROGEN_IONIZATION_ERG
        + helium_per_gram
        * (
            helium_singly_ionized * HELIUM_I_IONIZATION_ERG
            + helium_doubly_ionized
            * (HELIUM_I_IONIZATION_ERG + HELIUM_II_IONIZATION_ERG)
        )
    )


def ground_state_temperature_from_specific_energy_k(
    density_g_cm3: ArrayLike,
    specific_total_energy_erg_g: ArrayLike,
    hydrogen_fraction: ArrayLike,
    helium_fraction: ArrayLike,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> NDArray[np.float64]:
    """反演单调的气体、辐射与基态电离总比能，不设置温度 floor。"""
    density = np.asarray(density_g_cm3, dtype=np.float64)
    energy = np.asarray(specific_total_energy_erg_g, dtype=np.float64)
    hydrogen = np.asarray(hydrogen_fraction, dtype=np.float64)
    helium = np.asarray(helium_fraction, dtype=np.float64)
    if (
        density.ndim != 1
        or energy.shape != density.shape
        or hydrogen.shape != (density.size, 2)
        or helium.shape != (density.size, 3)
        or not np.all(np.isfinite(density))
        or np.any(density <= 0.0)
        or not np.all(np.isfinite(energy))
    ):
        raise PhysicalDomainError("energy inversion arrays must share a finite depth axis")
    tolerance = 128.0 * np.finfo(np.float64).eps
    if (
        not np.all(np.isfinite(hydrogen))
        or not np.all(np.isfinite(helium))
        or np.any(hydrogen < 0.0)
        or np.any(helium < 0.0)
        or np.any(np.abs(np.sum(hydrogen, axis=1) - 1.0) > tolerance)
        or np.any(np.abs(np.sum(helium, axis=1) - 1.0) > tolerance)
    ):
        raise PhysicalDomainError("energy inversion requires physical H/He fractions")
    ionization = _specific_ionization_energy_erg_g(
        hydrogen[:, 1], helium[:, 1], helium[:, 2], composition
    )
    thermal = energy - ionization
    if np.any(thermal <= 0.0):
        raise PhysicalDomainError("specific energy leaves no positive thermal energy")
    hydrogen_per_gram, helium_per_gram, nuclei_per_gram = _composition_coefficients(
        composition
    )
    electron_per_gram = hydrogen_per_gram * hydrogen[:, 1] + helium_per_gram * (
        helium[:, 1] + 2.0 * helium[:, 2]
    )
    gas_coefficient = 1.5 * BOLTZMANN_ERG_K * (
        nuclei_per_gram + electron_per_gram
    )
    radiation_constant = 4.0 * STEFAN_BOLTZMANN_ERG_S_CM2_K4 / LIGHT_SPEED_CM_S
    radiation_coefficient = radiation_constant / density
    temperature = np.empty_like(density)
    for index in range(density.size):
        gas_upper = thermal[index] / gas_coefficient[index]
        radiation_upper = (thermal[index] / radiation_coefficient[index]) ** 0.25
        upper = float(min(gas_upper, radiation_upper))
        if not np.isfinite(upper) or upper <= 0.0:
            raise ArithmeticError("specific-energy temperature bracket became invalid")
        temperature[index] = brentq(
            lambda trial: (
                gas_coefficient[index] * trial
                + radiation_coefficient[index] * trial**4
                - thermal[index]
            ),
            0.0,
            upper,
            rtol=8.0 * np.finfo(np.float64).eps,
        )
    if not np.all(np.isfinite(temperature)) or np.any(temperature <= 0.0):
        raise ArithmeticError("specific-energy temperature inversion became invalid")
    return _readonly(temperature)


def _maximum_symmetric_residual(
    recovered: NDArray[np.float64], target: NDArray[np.float64]
) -> float:
    difference = np.abs(recovered - target)
    scale = np.abs(recovered) + np.abs(target)
    residual = np.zeros_like(difference)
    nonzero = scale > 0.0
    residual[nonzero] = 2.0 * difference[nonzero] / scale[nonzero]
    if np.any(~nonzero & (difference != 0.0)):
        raise ArithmeticError("a zero conserved quantity was not recovered exactly")
    return float(np.max(residual))


def conservative_ground_state_subcells(
    parent_grid: PeriodicDynamicHalfColumn,
    subcell_grid: PeriodicDynamicHalfColumn,
    parent_temperature_k: ArrayLike,
    parent_hydrogen_fraction: ArrayLike,
    parent_helium_fraction: ArrayLike,
    subcells_per_parent: int,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> ConservativeGroundStateSubcells:
    """把父初态延拓为真实子单元自由度，并守恒能量与物种数。"""
    if not isinstance(parent_grid, PeriodicDynamicHalfColumn) or not isinstance(
        subcell_grid, PeriodicDynamicHalfColumn
    ):
        raise TypeError("parent_grid and subcell_grid must be periodic dynamic grids")
    count = _validated_subcell_count(subcells_per_parent)
    _validated_nested_subcell_edges(
        parent_grid.mass_fraction_edges,
        subcell_grid.mass_fraction_edges,
        count,
    )
    if (
        parent_grid.phase_points != subcell_grid.phase_points
        or not np.array_equal(
            parent_grid.background.time_since_pericentre_s,
            subcell_grid.background.time_since_pericentre_s,
        )
    ):
        raise PhysicalDomainError("parent and subcell grids must share the orbital grid")
    parent_count = parent_grid.half_depth_points
    temperature = np.asarray(parent_temperature_k, dtype=np.float64)
    hydrogen = np.asarray(parent_hydrogen_fraction, dtype=np.float64)
    helium = np.asarray(parent_helium_fraction, dtype=np.float64)
    parent_thermodynamics = ground_state_thermodynamics(
        parent_grid.density_g_cm3[0],
        temperature,
        hydrogen,
        helium,
        composition=composition,
    )
    fields = np.column_stack(
        (
            parent_thermodynamics.specific_total_energy_erg_g,
            hydrogen[:, 1],
            helium[:, 1],
            helium[:, 2],
        )
    )
    child_edges, _, increments = _linear_subcell_increments(
        fields,
        parent_grid.mass_fraction_edges,
        count,
        subcell_grid.mass_fraction_edges,
    )
    theta = np.ones(parent_count, dtype=np.float64)
    parent_ionization = _specific_ionization_energy_erg_g(
        fields[:, 1], fields[:, 2], fields[:, 3], composition
    )
    for parent in range(parent_count):
        for child in range(count):
            delta_energy, delta_h_ii, delta_he_ii, delta_he_iii = increments[
                parent, child
            ]
            constraints = (
                (fields[parent, 1], delta_h_ii, False),
                (1.0 - fields[parent, 1], -delta_h_ii, False),
                (fields[parent, 2], delta_he_ii, False),
                (fields[parent, 3], delta_he_iii, False),
                (
                    1.0 - fields[parent, 2] - fields[parent, 3],
                    -delta_he_ii - delta_he_iii,
                    False,
                ),
            )
            for base, delta, strict in constraints:
                theta[parent] = _limited_fraction(
                    float(base),
                    float(delta),
                    float(theta[parent]),
                    strictly_positive=strict,
                )
            delta_ionization = float(
                _specific_ionization_energy_erg_g(
                    np.array([delta_h_ii]),
                    np.array([delta_he_ii]),
                    np.array([delta_he_iii]),
                    composition,
                )[0]
            )
            theta[parent] = _limited_fraction(
                float(fields[parent, 0] - parent_ionization[parent]),
                float(delta_energy - delta_ionization),
                float(theta[parent]),
                strictly_positive=True,
            )
    reconstructed = fields[:, None, :] + theta[:, None, None] * increments
    reconstructed = reconstructed.reshape(parent_count * count, 4)
    child_hydrogen = np.column_stack(
        (1.0 - reconstructed[:, 1], reconstructed[:, 1])
    )
    child_helium = np.column_stack(
        (
            1.0 - reconstructed[:, 2] - reconstructed[:, 3],
            reconstructed[:, 2],
            reconstructed[:, 3],
        )
    )
    if np.any(child_hydrogen < 0.0) or np.any(child_helium < 0.0):
        raise ArithmeticError("ground-state subcell limiter left the population simplex")
    child_temperature = ground_state_temperature_from_specific_energy_k(
        subcell_grid.density_g_cm3[0],
        reconstructed[:, 0],
        child_hydrogen,
        child_helium,
        composition=composition,
    )
    actual = ground_state_thermodynamics(
        subcell_grid.density_g_cm3[0],
        child_temperature,
        child_hydrogen,
        child_helium,
        composition=composition,
    )
    parent_mass = parent_grid.cell_mass_g_cm2
    child_mass = subcell_grid.cell_mass_g_cm2.reshape(parent_count, count)
    mass_sum = np.sum(child_mass, axis=1)
    weight = child_mass / parent_mass[:, None]

    def restrict(values: NDArray[np.float64]) -> NDArray[np.float64]:
        reshaped = values.reshape(parent_count, count, *values.shape[1:])
        expanded_weight = weight[(...,) + (None,) * (values.ndim - 1)]
        return np.sum(reshaped * expanded_weight, axis=1)

    restricted_hydrogen = restrict(child_hydrogen)
    restricted_helium = restrict(child_helium)
    restricted_energy = restrict(actual.specific_total_energy_erg_g)
    hydrogen_per_gram, helium_per_gram, _ = _composition_coefficients(composition)
    parent_charge = hydrogen_per_gram * hydrogen[:, 1] + helium_per_gram * (
        helium[:, 1] + 2.0 * helium[:, 2]
    )
    child_charge = hydrogen_per_gram * child_hydrogen[:, 1] + helium_per_gram * (
        child_helium[:, 1] + 2.0 * child_helium[:, 2]
    )
    return ConservativeGroundStateSubcells(
        parent_mass_fraction_edges=_readonly(
            np.array(parent_grid.mass_fraction_edges, copy=True)
        ),
        subcell_mass_fraction_edges=child_edges,
        subcells_per_parent=count,
        temperature_k=child_temperature,
        hydrogen_fraction=_readonly(child_hydrogen),
        helium_fraction=_readonly(child_helium),
        specific_total_energy_erg_g=actual.specific_total_energy_erg_g,
        limiter_fraction=_readonly(theta),
        maximum_parent_mass_residual=_maximum_symmetric_residual(
            mass_sum, parent_mass
        ),
        maximum_hydrogen_particle_residual=_maximum_symmetric_residual(
            np.sum(restricted_hydrogen, axis=1), np.sum(hydrogen, axis=1)
        ),
        maximum_helium_particle_residual=_maximum_symmetric_residual(
            np.sum(restricted_helium, axis=1), np.sum(helium, axis=1)
        ),
        maximum_hydrogen_stage_absolute_residual=float(
            np.max(np.abs(restricted_hydrogen - hydrogen))
        ),
        maximum_helium_stage_absolute_residual=float(
            np.max(np.abs(restricted_helium - helium))
        ),
        maximum_charge_residual=_maximum_symmetric_residual(
            restrict(child_charge), parent_charge
        ),
        maximum_specific_energy_residual=_maximum_symmetric_residual(
            restricted_energy,
            parent_thermodynamics.specific_total_energy_erg_g,
        ),
    )


def restrict_periodic_dynamic_subcells(
    parent_grid: PeriodicDynamicHalfColumn,
    subcell_solution: PeriodicDynamicColumnSolution,
    subcells_per_parent: int,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> ConservativeSubcellRestriction:
    """质量加权限制周期子单元解；内部面通量只通过望远镜相消。"""
    if not isinstance(parent_grid, PeriodicDynamicHalfColumn):
        raise TypeError("parent_grid must be a PeriodicDynamicHalfColumn")
    if not isinstance(subcell_solution, PeriodicDynamicColumnSolution):
        raise TypeError("subcell_solution must be a PeriodicDynamicColumnSolution")
    count = _validated_subcell_count(subcells_per_parent)
    subcell_grid = subcell_solution.grid
    _validated_nested_subcell_edges(
        parent_grid.mass_fraction_edges,
        subcell_grid.mass_fraction_edges,
        count,
    )
    if parent_grid.phase_points != subcell_grid.phase_points:
        raise PhysicalDomainError("parent and subcell solutions must share orbital phases")
    phases = parent_grid.phase_points
    parents = parent_grid.half_depth_points
    child_mass = subcell_grid.cell_mass_g_cm2.reshape(parents, count)
    parent_mass = parent_grid.cell_mass_g_cm2
    weight = child_mass / parent_mass[:, None]
    child_thermodynamics = ground_state_thermodynamics(
        subcell_grid.density_g_cm3.reshape(-1),
        subcell_solution.temperature_k.reshape(-1),
        subcell_solution.hydrogen_fraction.reshape(-1, 2),
        subcell_solution.helium_fraction.reshape(-1, 3),
        composition=composition,
    )

    def restrict(values: NDArray[np.float64]) -> NDArray[np.float64]:
        tail = values.shape[2:]
        reshaped = values.reshape(phases, parents, count, *tail)
        expanded_weight = weight[(None, ...,) + (None,) * len(tail)]
        return np.sum(reshaped * expanded_weight, axis=2)

    child_hydrogen = subcell_solution.hydrogen_fraction
    child_helium = subcell_solution.helium_fraction
    parent_hydrogen = restrict(child_hydrogen)
    parent_helium = restrict(child_helium)
    child_energy = child_thermodynamics.specific_total_energy_erg_g.reshape(
        phases, parents * count
    )
    parent_energy = restrict(child_energy)
    parent_temperature = ground_state_temperature_from_specific_energy_k(
        parent_grid.density_g_cm3.reshape(-1),
        parent_energy.reshape(-1),
        parent_hydrogen.reshape(-1, 2),
        parent_helium.reshape(-1, 3),
        composition=composition,
    ).reshape(phases, parents)
    recovered_parent_thermodynamics = ground_state_thermodynamics(
        parent_grid.density_g_cm3.reshape(-1),
        parent_temperature.reshape(-1),
        parent_hydrogen.reshape(-1, 2),
        parent_helium.reshape(-1, 3),
        composition=composition,
    )
    parent_opacity = restrict(subcell_solution.rosseland_opacity_cm2_g)
    parent_flux = np.array(
        subcell_solution.outward_flux_edges_erg_s_cm2[:, ::count], copy=True
    )
    if parent_flux.shape != (phases, parents + 1):
        raise ArithmeticError("subcell face-flux restriction lost a parent face")
    child_divergence = np.diff(
        subcell_solution.outward_flux_edges_erg_s_cm2, axis=1
    ).reshape(phases, parents, count)
    parent_divergence = np.diff(parent_flux, axis=1)
    hydrogen_per_gram, helium_per_gram, _ = _composition_coefficients(composition)
    child_charge = hydrogen_per_gram * child_hydrogen[:, :, 1] + helium_per_gram * (
        child_helium[:, :, 1] + 2.0 * child_helium[:, :, 2]
    )
    parent_charge = hydrogen_per_gram * parent_hydrogen[:, :, 1] + helium_per_gram * (
        parent_helium[:, :, 1] + 2.0 * parent_helium[:, :, 2]
    )
    mass_sum = np.sum(child_mass, axis=1)
    opacity_integral = np.sum(
        subcell_solution.rosseland_opacity_cm2_g.reshape(
            phases, parents, count
        )
        * child_mass[None, :, :],
        axis=2,
    )
    return ConservativeSubcellRestriction(
        parent_temperature_k=_readonly(parent_temperature),
        parent_hydrogen_fraction=_readonly(parent_hydrogen),
        parent_helium_fraction=_readonly(parent_helium),
        parent_specific_total_energy_erg_g=_readonly(parent_energy),
        parent_rosseland_opacity_cm2_g=_readonly(parent_opacity),
        parent_outward_flux_edges_erg_s_cm2=_readonly(parent_flux),
        maximum_parent_mass_residual=_maximum_symmetric_residual(
            mass_sum, parent_mass
        ),
        maximum_hydrogen_particle_residual=_maximum_symmetric_residual(
            np.sum(parent_hydrogen, axis=2) * parent_mass[None, :],
            np.sum(
                np.sum(
                    child_hydrogen.reshape(phases, parents, count, 2), axis=3
                )
                * child_mass[None, :, :],
                axis=2,
            ),
        ),
        maximum_helium_particle_residual=_maximum_symmetric_residual(
            np.sum(parent_helium, axis=2) * parent_mass[None, :],
            np.sum(
                np.sum(
                    child_helium.reshape(phases, parents, count, 3), axis=3
                )
                * child_mass[None, :, :],
                axis=2,
            ),
        ),
        maximum_hydrogen_stage_absolute_residual=float(
            np.max(
                np.abs(
                    parent_hydrogen * parent_mass[None, :, None]
                    - np.sum(
                        child_hydrogen.reshape(phases, parents, count, 2)
                        * child_mass[None, :, :, None],
                        axis=2,
                    )
                )
                / parent_mass[None, :, None]
            )
        ),
        maximum_helium_stage_absolute_residual=float(
            np.max(
                np.abs(
                    parent_helium * parent_mass[None, :, None]
                    - np.sum(
                        child_helium.reshape(phases, parents, count, 3)
                        * child_mass[None, :, :, None],
                        axis=2,
                    )
                )
                / parent_mass[None, :, None]
            )
        ),
        maximum_charge_residual=_maximum_symmetric_residual(
            parent_charge * parent_mass[None, :],
            np.sum(
                child_charge.reshape(phases, parents, count)
                * child_mass[None, :, :],
                axis=2,
            ),
        ),
        maximum_specific_energy_residual=_maximum_symmetric_residual(
            recovered_parent_thermodynamics.specific_total_energy_erg_g.reshape(
                phases, parents
            )
            * parent_mass[None, :],
            parent_energy * parent_mass[None, :],
        ),
        maximum_optical_depth_residual=_maximum_symmetric_residual(
            parent_opacity * parent_mass[None, :], opacity_integral
        ),
        maximum_face_flux_divergence_residual=_maximum_symmetric_residual(
            parent_divergence, np.sum(child_divergence, axis=2)
        ),
    )


def coarsen_ground_state_subcells(
    source_grid: PeriodicDynamicHalfColumn,
    coarsened_grid: PeriodicDynamicHalfColumn,
    source_state: ConservativeGroundStateSubcells,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> ConservativeCoarsenedGroundState:
    """把已守恒延拓的细初态合并到其任意嵌套子集网格。"""
    if not isinstance(source_grid, PeriodicDynamicHalfColumn) or not isinstance(
        coarsened_grid, PeriodicDynamicHalfColumn
    ):
        raise TypeError("source_grid and coarsened_grid must be periodic dynamic grids")
    if not isinstance(source_state, ConservativeGroundStateSubcells):
        raise TypeError("source_state must be a ConservativeGroundStateSubcells")
    if not np.array_equal(
        source_state.subcell_mass_fraction_edges,
        source_grid.mass_fraction_edges,
    ):
        raise PhysicalDomainError("source state does not belong to source_grid")
    if (
        source_grid.phase_points != coarsened_grid.phase_points
        or not np.array_equal(
            source_grid.background.time_since_pericentre_s,
            coarsened_grid.background.time_since_pericentre_s,
        )
    ):
        raise PhysicalDomainError("source and coarsened grids must share the orbit")
    offsets = nested_mass_cell_offsets(
        coarsened_grid.mass_fraction_edges,
        source_grid.mass_fraction_edges,
    )
    counts = np.diff(offsets)
    source_mass = source_grid.cell_mass_g_cm2
    coarsened_mass = coarsened_grid.cell_mass_g_cm2

    def mass_average(values: NDArray[np.float64]) -> NDArray[np.float64]:
        result = np.empty((counts.size, *values.shape[1:]), dtype=np.float64)
        for parent, (left, right) in enumerate(
            zip(offsets[:-1], offsets[1:], strict=True)
        ):
            weight_shape = (right - left,) + (1,) * (values.ndim - 1)
            weight = source_mass[left:right].reshape(weight_shape)
            result[parent] = np.sum(values[left:right] * weight, axis=0) / (
                coarsened_mass[parent]
            )
        return result

    # 中文：先合并守恒变量，再由总比能反演温度，禁止直接平均温度。
    hydrogen = mass_average(source_state.hydrogen_fraction)
    helium = mass_average(source_state.helium_fraction)
    energy = mass_average(source_state.specific_total_energy_erg_g)
    temperature = ground_state_temperature_from_specific_energy_k(
        coarsened_grid.density_g_cm3[0],
        energy,
        hydrogen,
        helium,
        composition=composition,
    )
    recovered = ground_state_thermodynamics(
        coarsened_grid.density_g_cm3[0],
        temperature,
        hydrogen,
        helium,
        composition=composition,
    )
    hydrogen_per_gram, helium_per_gram, _ = _composition_coefficients(composition)
    source_charge = hydrogen_per_gram * source_state.hydrogen_fraction[:, 1] + (
        helium_per_gram
        * (
            source_state.helium_fraction[:, 1]
            + 2.0 * source_state.helium_fraction[:, 2]
        )
    )
    coarsened_charge = hydrogen_per_gram * hydrogen[:, 1] + helium_per_gram * (
        helium[:, 1] + 2.0 * helium[:, 2]
    )

    def mass_sum(values: NDArray[np.float64]) -> NDArray[np.float64]:
        result = np.empty((counts.size, *values.shape[1:]), dtype=np.float64)
        for parent, (left, right) in enumerate(
            zip(offsets[:-1], offsets[1:], strict=True)
        ):
            weight_shape = (right - left,) + (1,) * (values.ndim - 1)
            result[parent] = np.sum(
                values[left:right]
                * source_mass[left:right].reshape(weight_shape),
                axis=0,
            )
        return result

    source_hydrogen_sum = mass_sum(source_state.hydrogen_fraction)
    source_helium_sum = mass_sum(source_state.helium_fraction)
    return ConservativeCoarsenedGroundState(
        source_mass_fraction_edges=_readonly(
            np.array(source_grid.mass_fraction_edges, copy=True)
        ),
        coarsened_mass_fraction_edges=_readonly(
            np.array(coarsened_grid.mass_fraction_edges, copy=True)
        ),
        source_cells_per_coarsened_cell=_readonly(np.array(counts, copy=True)),
        temperature_k=temperature,
        hydrogen_fraction=_readonly(hydrogen),
        helium_fraction=_readonly(helium),
        specific_total_energy_erg_g=recovered.specific_total_energy_erg_g,
        maximum_mass_residual=_maximum_symmetric_residual(
            mass_sum(np.ones(source_grid.half_depth_points)), coarsened_mass
        ),
        maximum_hydrogen_particle_residual=_maximum_symmetric_residual(
            np.sum(hydrogen, axis=1) * coarsened_mass,
            np.sum(source_hydrogen_sum, axis=1),
        ),
        maximum_helium_particle_residual=_maximum_symmetric_residual(
            np.sum(helium, axis=1) * coarsened_mass,
            np.sum(source_helium_sum, axis=1),
        ),
        maximum_hydrogen_stage_absolute_residual=float(
            np.max(
                np.abs(hydrogen * coarsened_mass[:, None] - source_hydrogen_sum)
                / coarsened_mass[:, None]
            )
        ),
        maximum_helium_stage_absolute_residual=float(
            np.max(
                np.abs(helium * coarsened_mass[:, None] - source_helium_sum)
                / coarsened_mass[:, None]
            )
        ),
        maximum_charge_residual=_maximum_symmetric_residual(
            coarsened_charge * coarsened_mass,
            mass_sum(source_charge),
        ),
        maximum_specific_energy_residual=_maximum_symmetric_residual(
            recovered.specific_total_energy_erg_g * coarsened_mass,
            mass_sum(source_state.specific_total_energy_erg_g),
        ),
    )


def restrict_periodic_dynamic_variable_subcells(
    parent_grid: PeriodicDynamicHalfColumn,
    child_solution: PeriodicDynamicColumnSolution,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> ConservativeVariableSubcellRestriction:
    """守恒限制任意严格嵌套的可变子单元周期解。"""
    if not isinstance(parent_grid, PeriodicDynamicHalfColumn):
        raise TypeError("parent_grid must be a PeriodicDynamicHalfColumn")
    if not isinstance(child_solution, PeriodicDynamicColumnSolution):
        raise TypeError("child_solution must be a PeriodicDynamicColumnSolution")
    child_grid = child_solution.grid
    if (
        parent_grid.phase_points != child_grid.phase_points
        or not np.array_equal(
            parent_grid.background.time_since_pericentre_s,
            child_grid.background.time_since_pericentre_s,
        )
    ):
        raise PhysicalDomainError("parent and child solutions must share the orbit")
    offsets = nested_mass_cell_offsets(
        parent_grid.mass_fraction_edges,
        child_grid.mass_fraction_edges,
    )
    counts = np.diff(offsets)
    phases = parent_grid.phase_points
    parents = parent_grid.half_depth_points
    child_mass = child_grid.cell_mass_g_cm2
    parent_mass = parent_grid.cell_mass_g_cm2

    def mass_average(values: NDArray[np.float64]) -> NDArray[np.float64]:
        result = np.empty((phases, parents, *values.shape[2:]), dtype=np.float64)
        for parent, (left, right) in enumerate(
            zip(offsets[:-1], offsets[1:], strict=True)
        ):
            weight_shape = (1, right - left) + (1,) * (values.ndim - 2)
            result[:, parent] = np.sum(
                values[:, left:right]
                * child_mass[left:right].reshape(weight_shape),
                axis=1,
            ) / parent_mass[parent]
        return result

    def mass_sum(values: NDArray[np.float64]) -> NDArray[np.float64]:
        result = np.empty((phases, parents, *values.shape[2:]), dtype=np.float64)
        for parent, (left, right) in enumerate(
            zip(offsets[:-1], offsets[1:], strict=True)
        ):
            weight_shape = (1, right - left) + (1,) * (values.ndim - 2)
            result[:, parent] = np.sum(
                values[:, left:right]
                * child_mass[left:right].reshape(weight_shape),
                axis=1,
            )
        return result

    hydrogen = mass_average(child_solution.hydrogen_fraction)
    helium = mass_average(child_solution.helium_fraction)
    child_thermodynamics = ground_state_thermodynamics(
        child_grid.density_g_cm3.reshape(-1),
        child_solution.temperature_k.reshape(-1),
        child_solution.hydrogen_fraction.reshape(-1, 2),
        child_solution.helium_fraction.reshape(-1, 3),
        composition=composition,
    )
    child_energy = child_thermodynamics.specific_total_energy_erg_g.reshape(
        phases, child_grid.half_depth_points
    )
    energy = mass_average(child_energy)
    temperature = ground_state_temperature_from_specific_energy_k(
        parent_grid.density_g_cm3.reshape(-1),
        energy.reshape(-1),
        hydrogen.reshape(-1, 2),
        helium.reshape(-1, 3),
        composition=composition,
    ).reshape(phases, parents)
    recovered = ground_state_thermodynamics(
        parent_grid.density_g_cm3.reshape(-1),
        temperature.reshape(-1),
        hydrogen.reshape(-1, 2),
        helium.reshape(-1, 3),
        composition=composition,
    )
    opacity = mass_average(child_solution.rosseland_opacity_cm2_g)
    # 中文：父面通量来自严格嵌套的子面，通量散度因而可望远镜求和。
    flux = _readonly(
        np.array(child_solution.outward_flux_edges_erg_s_cm2[:, offsets], copy=True)
    )
    child_divergence = np.diff(
        child_solution.outward_flux_edges_erg_s_cm2, axis=1
    )
    grouped_divergence = np.empty((phases, parents), dtype=np.float64)
    for parent, (left, right) in enumerate(
        zip(offsets[:-1], offsets[1:], strict=True)
    ):
        grouped_divergence[:, parent] = np.sum(
            child_divergence[:, left:right], axis=1
        )
    parent_divergence = np.diff(flux, axis=1)
    hydrogen_per_gram, helium_per_gram, _ = _composition_coefficients(composition)
    child_charge = (
        hydrogen_per_gram * child_solution.hydrogen_fraction[:, :, 1]
        + helium_per_gram
        * (
            child_solution.helium_fraction[:, :, 1]
            + 2.0 * child_solution.helium_fraction[:, :, 2]
        )
    )
    parent_charge = hydrogen_per_gram * hydrogen[:, :, 1] + helium_per_gram * (
        helium[:, :, 1] + 2.0 * helium[:, :, 2]
    )
    hydrogen_sum = mass_sum(child_solution.hydrogen_fraction)
    helium_sum = mass_sum(child_solution.helium_fraction)
    return ConservativeVariableSubcellRestriction(
        child_cells_per_parent=_readonly(np.array(counts, copy=True)),
        parent_temperature_k=_readonly(temperature),
        parent_hydrogen_fraction=_readonly(hydrogen),
        parent_helium_fraction=_readonly(helium),
        parent_specific_total_energy_erg_g=_readonly(energy),
        parent_rosseland_opacity_cm2_g=_readonly(opacity),
        parent_outward_flux_edges_erg_s_cm2=flux,
        maximum_parent_mass_residual=_maximum_symmetric_residual(
            np.array(
                [np.sum(child_mass[left:right]) for left, right in zip(offsets[:-1], offsets[1:], strict=True)]
            ),
            parent_mass,
        ),
        maximum_hydrogen_particle_residual=_maximum_symmetric_residual(
            np.sum(hydrogen, axis=2) * parent_mass[None, :],
            np.sum(hydrogen_sum, axis=2),
        ),
        maximum_helium_particle_residual=_maximum_symmetric_residual(
            np.sum(helium, axis=2) * parent_mass[None, :],
            np.sum(helium_sum, axis=2),
        ),
        maximum_hydrogen_stage_absolute_residual=float(
            np.max(
                np.abs(hydrogen * parent_mass[None, :, None] - hydrogen_sum)
                / parent_mass[None, :, None]
            )
        ),
        maximum_helium_stage_absolute_residual=float(
            np.max(
                np.abs(helium * parent_mass[None, :, None] - helium_sum)
                / parent_mass[None, :, None]
            )
        ),
        maximum_charge_residual=_maximum_symmetric_residual(
            parent_charge * parent_mass[None, :], mass_sum(child_charge)
        ),
        maximum_specific_energy_residual=_maximum_symmetric_residual(
            recovered.specific_total_energy_erg_g.reshape(phases, parents)
            * parent_mass[None, :],
            energy * parent_mass[None, :],
        ),
        maximum_optical_depth_residual=_maximum_symmetric_residual(
            opacity * parent_mass[None, :],
            mass_sum(child_solution.rosseland_opacity_cm2_g),
        ),
        maximum_face_flux_divergence_residual=_maximum_symmetric_residual(
            parent_divergence, grouped_divergence
        ),
    )
