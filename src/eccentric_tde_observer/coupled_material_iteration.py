"""固定物理时间层上的辐射--物质 Picard 迭代阻尼。

完整候选始终由物理旧时间层和当前辐射系数构造；阻尼更新则从当前非线性迭代态
指向该候选，避免把同一个物理步长重复累加。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .radiation_matter_feedback import (
    FrozenRadiationMaterialResponse,
    ground_state_material_specific_energy_erg_g,
    ground_state_material_temperature_from_specific_energy_k,
)
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class DampedCoupledMaterialIteration:
    """从当前迭代态指向固定时间层完整候选的一次阻尼更新。"""

    relaxation: float
    temperature_k: NDArray[np.float64]
    hydrogen_fraction: NDArray[np.float64]
    helium_fraction: NDArray[np.float64]
    current_specific_material_energy_erg_g: NDArray[np.float64]
    candidate_specific_material_energy_erg_g: NDArray[np.float64]
    updated_specific_material_energy_erg_g: NDArray[np.float64]
    recovered_specific_material_energy_erg_g: NDArray[np.float64]
    maximum_relative_temperature_change: float
    maximum_absolute_material_energy_increment_fraction: float
    maximum_population_fraction_change: float
    maximum_relative_energy_residual: float
    minimum_population_fraction: float
    maximum_particle_conservation_residual: float


def damped_coupled_material_iteration(
    current_temperature_k: ArrayLike,
    current_hydrogen_fraction: ArrayLike,
    current_helium_fraction: ArrayLike,
    fixed_time_level_candidate: FrozenRadiationMaterialResponse,
    *,
    maximum_relative_temperature_change: float,
    maximum_absolute_material_energy_increment_fraction: float,
    bisection_iterations: int = 96,
) -> DampedCoupledMaterialIteration:
    """在温度和物质能信赖域内取最大的当前态到候选态阻尼步。"""
    if not isinstance(
        fixed_time_level_candidate, FrozenRadiationMaterialResponse
    ):
        raise TypeError(
            "fixed_time_level_candidate must be a FrozenRadiationMaterialResponse"
        )
    temperature = np.asarray(current_temperature_k, dtype=np.float64)
    hydrogen = np.asarray(current_hydrogen_fraction, dtype=np.float64)
    helium = np.asarray(current_helium_fraction, dtype=np.float64)
    cells = temperature.size
    if (
        temperature.ndim != 1
        or hydrogen.shape != (cells, 2)
        or helium.shape != (cells, 3)
        or fixed_time_level_candidate.temperature_k.shape != (cells,)
        or not np.all(np.isfinite(temperature))
        or np.any(temperature <= 0.0)
    ):
        raise PhysicalDomainError(
            "current and fixed-time-level candidate states must share one axis"
        )
    temperature_limit = float(maximum_relative_temperature_change)
    energy_limit = float(maximum_absolute_material_energy_increment_fraction)
    if (
        not np.isfinite(temperature_limit)
        or not np.isfinite(energy_limit)
        or temperature_limit <= 0.0
        or energy_limit <= 0.0
        or temperature_limit >= 1.0
        or energy_limit >= 1.0
        or not isinstance(bisection_iterations, (int, np.integer))
        or int(bisection_iterations) < 1
    ):
        raise PhysicalDomainError("coupled-iteration trust limits are invalid")
    current_energy = np.asarray(
        ground_state_material_specific_energy_erg_g(
            temperature, hydrogen, helium
        )
    )
    candidate_energy = np.asarray(
        fixed_time_level_candidate.target_specific_material_energy_erg_g
    )
    energy_direction = candidate_energy - current_energy
    maximum_full_energy_fraction = float(
        np.max(np.abs(energy_direction) / current_energy)
    )
    energy_upper = (
        min(1.0, energy_limit / maximum_full_energy_fraction)
        if maximum_full_energy_fraction > 0.0
        else 1.0
    )
    candidate_hydrogen = np.asarray(
        fixed_time_level_candidate.hydrogen_fraction
    )
    candidate_helium = np.asarray(
        fixed_time_level_candidate.helium_fraction
    )

    def state(relaxation: float):
        updated_hydrogen = hydrogen + relaxation * (
            candidate_hydrogen - hydrogen
        )
        updated_helium = helium + relaxation * (
            candidate_helium - helium
        )
        updated_energy = current_energy + relaxation * energy_direction
        updated_temperature = ground_state_material_temperature_from_specific_energy_k(
            updated_energy, updated_hydrogen, updated_helium
        )
        relative_temperature = float(
            np.max(np.abs(updated_temperature - temperature) / temperature)
        )
        return (
            updated_temperature,
            updated_hydrogen,
            updated_helium,
            updated_energy,
            relative_temperature,
        )

    upper_state = state(energy_upper)
    if upper_state[-1] <= temperature_limit:
        relaxation = energy_upper
        selected = upper_state
    else:
        lower = 0.0
        upper = energy_upper
        selected = state(lower)
        for _ in range(int(bisection_iterations)):
            trial = 0.5 * (lower + upper)
            evaluated = state(trial)
            if evaluated[-1] <= temperature_limit:
                lower = trial
                selected = evaluated
            else:
                upper = trial
        relaxation = lower
    (
        updated_temperature,
        updated_hydrogen,
        updated_helium,
        updated_energy,
        relative_temperature,
    ) = selected
    recovered_energy = np.asarray(
        ground_state_material_specific_energy_erg_g(
            updated_temperature, updated_hydrogen, updated_helium
        )
    )
    absolute_residual = np.abs(recovered_energy - updated_energy)
    scale = np.maximum(np.abs(recovered_energy), np.abs(updated_energy))
    relative_residual = np.array(absolute_residual, copy=True)
    np.divide(
        absolute_residual,
        scale,
        out=relative_residual,
        where=scale > 0.0,
    )
    population_change = max(
        float(np.max(np.abs(updated_hydrogen - hydrogen))),
        float(np.max(np.abs(updated_helium - helium))),
    )
    particle_residual = max(
        float(np.max(np.abs(np.sum(updated_hydrogen, axis=1) - 1.0))),
        float(np.max(np.abs(np.sum(updated_helium, axis=1) - 1.0))),
    )
    return DampedCoupledMaterialIteration(
        relaxation=float(relaxation),
        temperature_k=_readonly(np.array(updated_temperature, copy=True)),
        hydrogen_fraction=_readonly(np.array(updated_hydrogen, copy=True)),
        helium_fraction=_readonly(np.array(updated_helium, copy=True)),
        current_specific_material_energy_erg_g=_readonly(
            np.array(current_energy, copy=True)
        ),
        candidate_specific_material_energy_erg_g=_readonly(
            np.array(candidate_energy, copy=True)
        ),
        updated_specific_material_energy_erg_g=_readonly(
            np.array(updated_energy, copy=True)
        ),
        recovered_specific_material_energy_erg_g=_readonly(
            np.array(recovered_energy, copy=True)
        ),
        maximum_relative_temperature_change=relative_temperature,
        maximum_absolute_material_energy_increment_fraction=float(
            relaxation * maximum_full_energy_fraction
        ),
        maximum_population_fraction_change=population_change,
        maximum_relative_energy_residual=float(np.max(relative_residual)),
        minimum_population_fraction=float(
            min(np.min(updated_hydrogen), np.min(updated_helium))
        ),
        maximum_particle_conservation_residual=particle_residual,
    )
