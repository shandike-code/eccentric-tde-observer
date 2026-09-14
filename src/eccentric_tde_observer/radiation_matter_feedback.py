"""显式辐射场驱动的一次 H/He 物质响应。

辐射能由输运状态显式保存，因此这里的物质能量只包含理想气体热能和
H/He 基态电离势能，不再加入局域 ``a T^4 / rho`` 项。该模块只执行一次
冻结辐射 Picard 响应，不构造完整辐射--物质固定点。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

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
from .orbital_kinetics import charge_neutral_backward_euler_step
from .radiation import BOLTZMANN_ERG_K
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


def _population_arrays(
    hydrogen_fraction: ArrayLike,
    helium_fraction: ArrayLike,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    hydrogen = np.asarray(hydrogen_fraction, dtype=np.float64)
    helium = np.asarray(helium_fraction, dtype=np.float64)
    if hydrogen.ndim != 2 or hydrogen.shape[1] != 2 or helium.shape != (
        hydrogen.shape[0],
        3,
    ):
        raise PhysicalDomainError("H/He population arrays must share one cell axis")
    tolerance = 128.0 * np.finfo(np.float64).eps
    if (
        not np.all(np.isfinite(hydrogen))
        or not np.all(np.isfinite(helium))
        or np.any(hydrogen < 0.0)
        or np.any(helium < 0.0)
        or np.any(np.abs(np.sum(hydrogen, axis=1) - 1.0) > tolerance)
        or np.any(np.abs(np.sum(helium, axis=1) - 1.0) > tolerance)
    ):
        raise PhysicalDomainError("H/He populations must lie in their simplices")
    return hydrogen, helium


def _composition_per_gram(
    composition: FullyIonizedHydrogenHeliumComposition,
) -> tuple[float, float, float]:
    hydrogen = composition.hydrogen_mass_fraction / PROTON_MASS_G
    helium = composition.helium_mass_fraction / (4.0 * PROTON_MASS_G)
    return hydrogen, helium, hydrogen + helium


def ground_state_material_specific_energy_erg_g(
    temperature_k: ArrayLike,
    hydrogen_fraction: ArrayLike,
    helium_fraction: ArrayLike,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> NDArray[np.float64]:
    """返回不重复计入显式辐射能的气体热能加基态电离比能。"""
    hydrogen, helium = _population_arrays(hydrogen_fraction, helium_fraction)
    temperature = np.asarray(temperature_k, dtype=np.float64)
    if (
        temperature.shape != (hydrogen.shape[0],)
        or not np.all(np.isfinite(temperature))
        or np.any(temperature <= 0.0)
    ):
        raise PhysicalDomainError("temperature must be finite, positive and cellwise")
    hydrogen_per_gram, helium_per_gram, nuclei_per_gram = _composition_per_gram(
        composition
    )
    electron_per_gram = hydrogen_per_gram * hydrogen[:, 1] + helium_per_gram * (
        helium[:, 1] + 2.0 * helium[:, 2]
    )
    gas = 1.5 * BOLTZMANN_ERG_K * temperature * (
        nuclei_per_gram + electron_per_gram
    )
    ionization = (
        hydrogen_per_gram * hydrogen[:, 1] * HYDROGEN_IONIZATION_ERG
        + helium_per_gram
        * (
            helium[:, 1] * HELIUM_I_IONIZATION_ERG
            + helium[:, 2]
            * (HELIUM_I_IONIZATION_ERG + HELIUM_II_IONIZATION_ERG)
        )
    )
    total = gas + ionization
    if not np.all(np.isfinite(total)) or np.any(total <= 0.0):
        raise ArithmeticError("ground-state material specific energy became invalid")
    return _readonly(np.array(total, copy=True))


def ground_state_material_temperature_from_specific_energy_k(
    specific_material_energy_erg_g: ArrayLike,
    hydrogen_fraction: ArrayLike,
    helium_fraction: ArrayLike,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> NDArray[np.float64]:
    """由气体加电离比能直接反演温度；不设置温度 floor。"""
    hydrogen, helium = _population_arrays(hydrogen_fraction, helium_fraction)
    energy = np.asarray(specific_material_energy_erg_g, dtype=np.float64)
    if energy.shape != (hydrogen.shape[0],) or not np.all(np.isfinite(energy)):
        raise PhysicalDomainError("specific material energy must be finite and cellwise")
    hydrogen_per_gram, helium_per_gram, nuclei_per_gram = _composition_per_gram(
        composition
    )
    ionization = (
        hydrogen_per_gram * hydrogen[:, 1] * HYDROGEN_IONIZATION_ERG
        + helium_per_gram
        * (
            helium[:, 1] * HELIUM_I_IONIZATION_ERG
            + helium[:, 2]
            * (HELIUM_I_IONIZATION_ERG + HELIUM_II_IONIZATION_ERG)
        )
    )
    thermal = energy - ionization
    if np.any(thermal <= 0.0):
        raise PhysicalDomainError("specific material energy leaves no positive gas heat")
    electron_per_gram = hydrogen_per_gram * hydrogen[:, 1] + helium_per_gram * (
        helium[:, 1] + 2.0 * helium[:, 2]
    )
    coefficient = 1.5 * BOLTZMANN_ERG_K * (
        nuclei_per_gram + electron_per_gram
    )
    temperature = thermal / coefficient
    if not np.all(np.isfinite(temperature)) or np.any(temperature <= 0.0):
        raise ArithmeticError("material-energy temperature inversion became invalid")
    return _readonly(np.array(temperature, copy=True))


@dataclass(frozen=True)
class FrozenRadiationMaterialResponse:
    """一个冻结共动辐射场上的电荷自洽物质响应。"""

    temperature_k: NDArray[np.float64]
    hydrogen_fraction: NDArray[np.float64]
    helium_fraction: NDArray[np.float64]
    electron_density_cm3: NDArray[np.float64]
    initial_specific_material_energy_erg_g: NDArray[np.float64]
    target_specific_material_energy_erg_g: NDArray[np.float64]
    recovered_specific_material_energy_erg_g: NDArray[np.float64]
    maximum_relative_temperature_change: float
    maximum_population_fraction_change: float
    maximum_relative_energy_residual: float
    maximum_relative_charge_residual: float
    maximum_particle_conservation_residual: float
    minimum_population_fraction: float


def frozen_radiation_material_response(
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    hydrogen_fraction: ArrayLike,
    helium_fraction: ArrayLike,
    step_duration_s: float,
    photoionization_s1: ArrayLike,
    radiative_recombination_cm3_s: ArrayLike,
    radiative_material_heating_erg_s_cm3: ArrayLike,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
    bisection_iterations: int = 96,
) -> FrozenRadiationMaterialResponse:
    """用同一冻结辐射场推进一次布居和物质能量，不作裁剪或限幅。"""
    hydrogen, helium = _population_arrays(hydrogen_fraction, helium_fraction)
    cells = hydrogen.shape[0]
    density = np.asarray(density_g_cm3, dtype=np.float64)
    temperature = np.asarray(temperature_k, dtype=np.float64)
    photoionization = np.asarray(photoionization_s1, dtype=np.float64)
    recombination = np.asarray(radiative_recombination_cm3_s, dtype=np.float64)
    heating = np.asarray(radiative_material_heating_erg_s_cm3, dtype=np.float64)
    duration = float(step_duration_s)
    if (
        density.shape != (cells,)
        or temperature.shape != (cells,)
        or heating.shape != (cells,)
        or photoionization.shape != (cells, 3)
        or recombination.shape != (cells, 3)
        or not np.all(np.isfinite(density))
        or np.any(density <= 0.0)
        or not np.all(np.isfinite(temperature))
        or np.any(temperature <= 0.0)
        or not np.all(np.isfinite(heating))
        or not np.all(np.isfinite(photoionization))
        or np.any(photoionization < 0.0)
        or not np.all(np.isfinite(recombination))
        or np.any(recombination < 0.0)
        or not np.isfinite(duration)
        or duration <= 0.0
    ):
        raise PhysicalDomainError("frozen-radiation response inputs are invalid")
    hydrogen_nuclei = (
        composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    )
    helium_nuclei = (
        composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    )
    updated_hydrogen = np.empty_like(hydrogen)
    updated_helium = np.empty_like(helium)
    electron = np.empty(cells)
    maximum_charge = 0.0
    maximum_particle = 0.0
    minimum_population = 1.0
    zeros = np.zeros(3)
    for cell in range(cells):
        step = charge_neutral_backward_euler_step(
            hydrogen[cell],
            helium[cell],
            float(hydrogen_nuclei[cell]),
            float(helium_nuclei[cell]),
            duration,
            photoionization[cell],
            zeros,
            recombination[cell],
            zeros,
            bisection_iterations=bisection_iterations,
        )
        updated_hydrogen[cell] = step.hydrogen_fraction
        updated_helium[cell] = step.helium_fraction
        electron[cell] = step.electron_density_cm3
        maximum_charge = max(maximum_charge, step.relative_charge_residual)
        maximum_particle = max(
            maximum_particle, step.particle_conservation_residual
        )
        minimum_population = min(minimum_population, step.minimum_fraction)
    initial_energy = ground_state_material_specific_energy_erg_g(
        temperature, hydrogen, helium, composition=composition
    )
    target_energy = initial_energy + duration * heating / density
    updated_temperature = ground_state_material_temperature_from_specific_energy_k(
        target_energy, updated_hydrogen, updated_helium, composition=composition
    )
    recovered_energy = ground_state_material_specific_energy_erg_g(
        updated_temperature,
        updated_hydrogen,
        updated_helium,
        composition=composition,
    )
    absolute_energy_residual = np.abs(recovered_energy - target_energy)
    energy_scale = np.maximum(np.abs(recovered_energy), np.abs(target_energy))
    relative_energy_residual = np.array(absolute_energy_residual, copy=True)
    np.divide(
        absolute_energy_residual,
        energy_scale,
        out=relative_energy_residual,
        where=energy_scale > 0.0,
    )
    temperature_change = np.abs(updated_temperature - temperature) / temperature
    population_change = max(
        float(np.max(np.abs(updated_hydrogen - hydrogen))),
        float(np.max(np.abs(updated_helium - helium))),
    )
    return FrozenRadiationMaterialResponse(
        temperature_k=_readonly(np.array(updated_temperature, copy=True)),
        hydrogen_fraction=_readonly(updated_hydrogen),
        helium_fraction=_readonly(updated_helium),
        electron_density_cm3=_readonly(electron),
        initial_specific_material_energy_erg_g=_readonly(np.array(initial_energy)),
        target_specific_material_energy_erg_g=_readonly(np.array(target_energy)),
        recovered_specific_material_energy_erg_g=_readonly(
            np.array(recovered_energy)
        ),
        maximum_relative_temperature_change=float(np.max(temperature_change)),
        maximum_population_fraction_change=population_change,
        maximum_relative_energy_residual=float(np.max(relative_energy_residual)),
        maximum_relative_charge_residual=maximum_charge,
        maximum_particle_conservation_residual=maximum_particle,
        minimum_population_fraction=minimum_population,
    )
