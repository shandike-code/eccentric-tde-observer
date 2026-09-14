"""完整相位隐式方程的一次物质 Picard 信赖域阻尼。

这里的阻尼系数是非线性求解器参数，不是缩短后的物理时间步。新布居取旧态与完整
冻结辐射候选的凸组合；新物质能沿完整辐射残差方向阻尼，再由气体加电离能反演温度。
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
class DampedMaterialPicardStep:
    """一次保持 H/He 单纯形和物质能残差方向的阻尼更新。"""

    relaxation: float
    temperature_k: NDArray[np.float64]
    hydrogen_fraction: NDArray[np.float64]
    helium_fraction: NDArray[np.float64]
    target_specific_material_energy_erg_g: NDArray[np.float64]
    recovered_specific_material_energy_erg_g: NDArray[np.float64]
    maximum_relative_temperature_change: float
    maximum_absolute_material_energy_increment_fraction: float
    maximum_population_fraction_change: float
    maximum_relative_energy_residual: float
    minimum_population_fraction: float
    maximum_particle_conservation_residual: float


def damped_material_picard_step(
    initial_temperature_k: ArrayLike,
    initial_hydrogen_fraction: ArrayLike,
    initial_helium_fraction: ArrayLike,
    full_candidate: FrozenRadiationMaterialResponse,
    *,
    maximum_relative_temperature_change: float,
    maximum_absolute_material_energy_increment_fraction: float,
    bisection_iterations: int = 96,
) -> DampedMaterialPicardStep:
    """求同时满足温度和物质能信赖域的最大整态阻尼系数。"""
    if not isinstance(full_candidate, FrozenRadiationMaterialResponse):
        raise TypeError("full_candidate must be a FrozenRadiationMaterialResponse")
    temperature = np.asarray(initial_temperature_k, dtype=np.float64)
    hydrogen = np.asarray(initial_hydrogen_fraction, dtype=np.float64)
    helium = np.asarray(initial_helium_fraction, dtype=np.float64)
    cells = temperature.size
    if (
        temperature.ndim != 1
        or hydrogen.shape != (cells, 2)
        or helium.shape != (cells, 3)
        or full_candidate.temperature_k.shape != (cells,)
        or not np.all(np.isfinite(temperature))
        or np.any(temperature <= 0.0)
    ):
        raise PhysicalDomainError("trust-region material states do not share one axis")
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
        raise PhysicalDomainError("trust limits and bisection count are invalid")
    initial_energy = np.asarray(
        full_candidate.initial_specific_material_energy_erg_g
    )
    full_energy_increment = (
        np.asarray(full_candidate.target_specific_material_energy_erg_g)
        - initial_energy
    )
    full_energy_fraction = np.abs(full_energy_increment) / initial_energy
    maximum_full_energy_fraction = float(np.max(full_energy_fraction))
    energy_upper = (
        min(1.0, energy_limit / maximum_full_energy_fraction)
        if maximum_full_energy_fraction > 0.0
        else 1.0
    )

    def state(relaxation: float):
        updated_hydrogen = hydrogen + relaxation * (
            np.asarray(full_candidate.hydrogen_fraction) - hydrogen
        )
        updated_helium = helium + relaxation * (
            np.asarray(full_candidate.helium_fraction) - helium
        )
        target_energy = initial_energy + relaxation * full_energy_increment
        updated_temperature = ground_state_material_temperature_from_specific_energy_k(
            target_energy, updated_hydrogen, updated_helium
        )
        relative_temperature = float(
            np.max(np.abs(updated_temperature - temperature) / temperature)
        )
        return (
            updated_temperature,
            updated_hydrogen,
            updated_helium,
            target_energy,
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
        target_energy,
        relative_temperature,
    ) = selected
    recovered_energy = ground_state_material_specific_energy_erg_g(
        updated_temperature, updated_hydrogen, updated_helium
    )
    absolute_residual = np.abs(recovered_energy - target_energy)
    scale = np.maximum(np.abs(recovered_energy), np.abs(target_energy))
    relative_residual = np.array(absolute_residual, copy=True)
    np.divide(absolute_residual, scale, out=relative_residual, where=scale > 0.0)
    population_change = max(
        float(np.max(np.abs(updated_hydrogen - hydrogen))),
        float(np.max(np.abs(updated_helium - helium))),
    )
    particle_residual = max(
        float(np.max(np.abs(np.sum(updated_hydrogen, axis=1) - 1.0))),
        float(np.max(np.abs(np.sum(updated_helium, axis=1) - 1.0))),
    )
    return DampedMaterialPicardStep(
        relaxation=float(relaxation),
        temperature_k=_readonly(np.array(updated_temperature, copy=True)),
        hydrogen_fraction=_readonly(np.array(updated_hydrogen, copy=True)),
        helium_fraction=_readonly(np.array(updated_helium, copy=True)),
        target_specific_material_energy_erg_g=_readonly(
            np.array(target_energy, copy=True)
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
