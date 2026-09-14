"""固定物理时间层物质--辐射反馈的受保护逐单元割线方向。"""

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
class ProtectedDiagonalSecantMaterialStep:
    """两个已验证反馈点构造的逐单元割线目标和全局保护步。"""

    relaxation: float
    secant_alpha: NDArray[np.float64]
    secant_target_temperature_k: NDArray[np.float64]
    secant_target_hydrogen_fraction: NDArray[np.float64]
    secant_target_helium_fraction: NDArray[np.float64]
    secant_target_specific_material_energy_erg_g: NDArray[np.float64]
    temperature_k: NDArray[np.float64]
    hydrogen_fraction: NDArray[np.float64]
    helium_fraction: NDArray[np.float64]
    specific_material_energy_erg_g: NDArray[np.float64]
    recovered_specific_material_energy_erg_g: NDArray[np.float64]
    maximum_relative_temperature_change: float
    maximum_absolute_material_energy_increment_fraction: float
    maximum_population_fraction_change: float
    maximum_relative_energy_residual: float
    maximum_particle_conservation_residual: float
    minimum_population_fraction: float
    maximum_secant_identity_relative_residual: float
    affine_secant_predicted_residual_contraction: float


def protected_diagonal_secant_material_step(
    previous_temperature_k: ArrayLike,
    previous_hydrogen_fraction: ArrayLike,
    previous_helium_fraction: ArrayLike,
    current_temperature_k: ArrayLike,
    current_hydrogen_fraction: ArrayLike,
    current_helium_fraction: ArrayLike,
    previous_fixed_time_level_candidate: FrozenRadiationMaterialResponse,
    current_fixed_time_level_candidate: FrozenRadiationMaterialResponse,
    *,
    maximum_relative_temperature_change: float,
    maximum_absolute_material_energy_increment_fraction: float,
    maximum_population_fraction_change: float,
    bisection_iterations: int = 96,
) -> ProtectedDiagonalSecantMaterialStep:
    """在物理域和全局信赖域内取最大的逐单元割线步。"""
    if not isinstance(
        previous_fixed_time_level_candidate, FrozenRadiationMaterialResponse
    ) or not isinstance(
        current_fixed_time_level_candidate, FrozenRadiationMaterialResponse
    ):
        raise TypeError("secant candidates must be FrozenRadiationMaterialResponse")
    previous_temperature = np.asarray(previous_temperature_k, dtype=np.float64)
    current_temperature = np.asarray(current_temperature_k, dtype=np.float64)
    previous_hydrogen = np.asarray(previous_hydrogen_fraction, dtype=np.float64)
    current_hydrogen = np.asarray(current_hydrogen_fraction, dtype=np.float64)
    previous_helium = np.asarray(previous_helium_fraction, dtype=np.float64)
    current_helium = np.asarray(current_helium_fraction, dtype=np.float64)
    cells = current_temperature.size
    if (
        previous_temperature.shape != (cells,)
        or previous_hydrogen.shape != (cells, 2)
        or current_hydrogen.shape != (cells, 2)
        or previous_helium.shape != (cells, 3)
        or current_helium.shape != (cells, 3)
        or np.any(previous_temperature <= 0.0)
        or np.any(current_temperature <= 0.0)
        or not all(
            np.all(np.isfinite(value))
            for value in (
                previous_temperature,
                current_temperature,
                previous_hydrogen,
                current_hydrogen,
                previous_helium,
                current_helium,
            )
        )
    ):
        raise PhysicalDomainError("two material iterates must share one valid axis")
    temperature_limit = float(maximum_relative_temperature_change)
    energy_limit = float(maximum_absolute_material_energy_increment_fraction)
    population_limit = float(maximum_population_fraction_change)
    if (
        not all(
            np.isfinite(value)
            for value in (temperature_limit, energy_limit, population_limit)
        )
        or not (0.0 < temperature_limit <= 1.0)
        or not (0.0 < energy_limit < 1.0)
        or not (0.0 < population_limit < 1.0)
        or not isinstance(bisection_iterations, (int, np.integer))
        or int(bisection_iterations) < 1
    ):
        raise PhysicalDomainError("secant trust limits are invalid")
    previous_energy = np.asarray(
        ground_state_material_specific_energy_erg_g(
            previous_temperature, previous_hydrogen, previous_helium
        )
    )
    current_energy = np.asarray(
        ground_state_material_specific_energy_erg_g(
            current_temperature, current_hydrogen, current_helium
        )
    )
    previous_image_energy = np.asarray(
        previous_fixed_time_level_candidate.target_specific_material_energy_erg_g
    )
    current_image_energy = np.asarray(
        current_fixed_time_level_candidate.target_specific_material_energy_erg_g
    )
    if previous_image_energy.shape != (cells,) or current_image_energy.shape != (cells,):
        raise PhysicalDomainError("secant candidate energy shape changed")
    previous_residual = previous_image_energy - previous_energy
    current_residual = current_image_energy - current_energy
    residual_difference = current_residual - previous_residual
    # 中文：分母为零时拒绝方向，不加 floor 或逐点裁剪。
    if np.any(residual_difference == 0.0):
        raise PhysicalDomainError("diagonal secant denominator is exactly zero")
    alpha = -previous_residual / residual_difference
    previous_candidate_hydrogen = np.asarray(
        previous_fixed_time_level_candidate.hydrogen_fraction
    )
    current_candidate_hydrogen = np.asarray(
        current_fixed_time_level_candidate.hydrogen_fraction
    )
    previous_candidate_helium = np.asarray(
        previous_fixed_time_level_candidate.helium_fraction
    )
    current_candidate_helium = np.asarray(
        current_fixed_time_level_candidate.helium_fraction
    )
    target_energy = (1.0 - alpha) * previous_image_energy + alpha * current_image_energy
    target_hydrogen = (
        (1.0 - alpha[:, None]) * previous_candidate_hydrogen
        + alpha[:, None] * current_candidate_hydrogen
    )
    target_helium = (
        (1.0 - alpha[:, None]) * previous_candidate_helium
        + alpha[:, None] * current_candidate_helium
    )
    if (
        not all(
            np.all(np.isfinite(value))
            for value in (alpha, target_energy, target_hydrogen, target_helium)
        )
        or np.any(target_energy <= 0.0)
        or np.any(target_hydrogen < 0.0)
        or np.any(target_helium < 0.0)
    ):
        raise PhysicalDomainError("unprotected diagonal secant target leaves domain")
    target_particle_residual = max(
        float(np.max(np.abs(np.sum(target_hydrogen, axis=1) - 1.0))),
        float(np.max(np.abs(np.sum(target_helium, axis=1) - 1.0))),
    )
    if target_particle_residual >= 1.0e-12:
        raise PhysicalDomainError("secant target violates the H/He simplex")
    target_temperature = ground_state_material_temperature_from_specific_energy_k(
        target_energy, target_hydrogen, target_helium
    )
    secant_state_energy = (1.0 - alpha) * previous_energy + alpha * current_energy
    identity_difference = np.abs(target_energy - secant_state_energy)
    identity_scale = np.maximum(np.abs(target_energy), np.abs(secant_state_energy))
    identity_relative = np.array(identity_difference, copy=True)
    np.divide(
        identity_difference,
        identity_scale,
        out=identity_relative,
        where=identity_scale > 0.0,
    )
    energy_direction = target_energy - current_energy
    maximum_full_energy_fraction = float(
        np.max(np.abs(energy_direction) / current_energy)
    )
    maximum_full_population_change = max(
        float(np.max(np.abs(target_hydrogen - current_hydrogen))),
        float(np.max(np.abs(target_helium - current_helium))),
    )
    upper = 1.0
    if maximum_full_energy_fraction > 0.0:
        upper = min(upper, energy_limit / maximum_full_energy_fraction)
    if maximum_full_population_change > 0.0:
        upper = min(upper, population_limit / maximum_full_population_change)

    def state(relaxation: float):
        hydrogen = current_hydrogen + relaxation * (
            target_hydrogen - current_hydrogen
        )
        helium = current_helium + relaxation * (target_helium - current_helium)
        energy = current_energy + relaxation * energy_direction
        temperature = ground_state_material_temperature_from_specific_energy_k(
            energy, hydrogen, helium
        )
        relative_temperature = float(
            np.max(np.abs(temperature - current_temperature) / current_temperature)
        )
        return temperature, hydrogen, helium, energy, relative_temperature

    selected = state(0.0)
    upper_state = state(upper)
    if upper_state[-1] <= temperature_limit:
        relaxation = upper
        selected = upper_state
    else:
        lower = 0.0
        for _ in range(int(bisection_iterations)):
            trial = 0.5 * (lower + upper)
            evaluated = state(trial)
            if evaluated[-1] <= temperature_limit:
                lower = trial
                selected = evaluated
            else:
                upper = trial
        relaxation = lower
    temperature, hydrogen, helium, energy, relative_temperature = selected
    recovered_energy = np.asarray(
        ground_state_material_specific_energy_erg_g(temperature, hydrogen, helium)
    )
    energy_difference = np.abs(recovered_energy - energy)
    recovered_scale = np.maximum(np.abs(recovered_energy), np.abs(energy))
    energy_relative = np.array(energy_difference, copy=True)
    np.divide(
        energy_difference,
        recovered_scale,
        out=energy_relative,
        where=recovered_scale > 0.0,
    )
    population_change = max(
        float(np.max(np.abs(hydrogen - current_hydrogen))),
        float(np.max(np.abs(helium - current_helium))),
    )
    particle_residual = max(
        float(np.max(np.abs(np.sum(hydrogen, axis=1) - 1.0))),
        float(np.max(np.abs(np.sum(helium, axis=1) - 1.0))),
    )
    return ProtectedDiagonalSecantMaterialStep(
        relaxation=float(relaxation),
        secant_alpha=_readonly(np.array(alpha, copy=True)),
        secant_target_temperature_k=_readonly(np.array(target_temperature, copy=True)),
        secant_target_hydrogen_fraction=_readonly(
            np.array(target_hydrogen, copy=True)
        ),
        secant_target_helium_fraction=_readonly(np.array(target_helium, copy=True)),
        secant_target_specific_material_energy_erg_g=_readonly(
            np.array(target_energy, copy=True)
        ),
        temperature_k=_readonly(np.array(temperature, copy=True)),
        hydrogen_fraction=_readonly(np.array(hydrogen, copy=True)),
        helium_fraction=_readonly(np.array(helium, copy=True)),
        specific_material_energy_erg_g=_readonly(np.array(energy, copy=True)),
        recovered_specific_material_energy_erg_g=_readonly(
            np.array(recovered_energy, copy=True)
        ),
        maximum_relative_temperature_change=relative_temperature,
        maximum_absolute_material_energy_increment_fraction=float(
            relaxation * maximum_full_energy_fraction
        ),
        maximum_population_fraction_change=population_change,
        maximum_relative_energy_residual=float(np.max(energy_relative)),
        maximum_particle_conservation_residual=particle_residual,
        minimum_population_fraction=float(min(np.min(hydrogen), np.min(helium))),
        maximum_secant_identity_relative_residual=float(np.max(identity_relative)),
        affine_secant_predicted_residual_contraction=float(1.0 - relaxation),
    )
