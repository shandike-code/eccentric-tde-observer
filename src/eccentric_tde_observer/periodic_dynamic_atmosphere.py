"""ZO 规定呼吸背景上的周期动态 H/He 基态热柱。

本模块把固定分数质量坐标上的压缩功、规定耗散、Rosseland 扩散、
辐射能和 H/He 基态电离能放入同一隐式时间步。局域辐射率暂以
``J_nu=B_nu(T)`` 的受困 Planck 场闭合；因此它是周期动态连续谱的
第一道能量门，不是多能级 NLTE 大气或真实线谱。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import least_squares

from .atmosphere import (
    PROTON_MASS_G,
    SOLAR_FULLY_IONIZED_H_HE,
    FullyIonizedHydrogenHeliumComposition,
)
from .atomic_continuum import ground_state_saha_factor_cm3
from .atomic_kinetics import (
    H_HE_COLLISIONAL_IONIZATION_FITS,
    detailed_balance_three_body_recombination_coefficient_cm6_s,
)
from .continuum_emission import (
    IONIZATION_ENERGIES_EV,
    ground_state_milne_continuum,
    ground_state_milne_radiative_rates,
)
from .dynamic_column import PeriodicColumnBackground
from .hydrostatic_atmosphere import (
    DissipationLaw,
    build_zo_constrained_n3_column,
    symmetric_dissipation_profile,
)
from .non_gray import (
    HELIUM_II_IONIZATION_ERG,
    HELIUM_I_IONIZATION_ERG,
    HYDROGEN_IONIZATION_ERG,
)
from .orbital_kinetics import charge_neutral_backward_euler_step
from .radiation import (
    BOLTZMANN_ERG_K,
    LIGHT_SPEED_CM_S,
    PLANCK_ERG_S,
    STEFAN_BOLTZMANN_ERG_S_CM2_K4,
    planck_nu,
)
from .source import PhysicalDomainError


DynamicRadiationClosure = Literal["local_planck_milne"]


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class PeriodicDynamicHalfColumn:
    """固定分数质量坐标上的一周 ZO 半柱背景。"""

    background: PeriodicColumnBackground
    dissipation_law: DissipationLaw
    mass_fraction_edges: NDArray[np.float64]
    cell_mass_g_cm2: NDArray[np.float64]
    density_g_cm3: NDArray[np.float64]
    specific_dissipation_erg_s_g: NDArray[np.float64]
    one_face_target_flux_erg_s_cm2: NDArray[np.float64]
    maximum_relative_column_mass_variation: float

    @property
    def phase_points(self) -> int:
        return int(self.density_g_cm3.shape[0])

    @property
    def half_depth_points(self) -> int:
        return int(self.density_g_cm3.shape[1])


@dataclass(frozen=True)
class GroundStateThermodynamics:
    """气体、辐射和基态电离能组成的局域热力学状态。"""

    specific_gas_energy_erg_g: NDArray[np.float64]
    specific_radiation_energy_erg_g: NDArray[np.float64]
    specific_ionization_energy_erg_g: NDArray[np.float64]
    specific_total_energy_erg_g: NDArray[np.float64]
    gas_pressure_erg_cm3: NDArray[np.float64]
    radiation_pressure_erg_cm3: NDArray[np.float64]
    total_pressure_erg_cm3: NDArray[np.float64]
    electron_density_cm3: NDArray[np.float64]


@dataclass(frozen=True)
class PeriodicDynamicColumnSolution:
    """周期动态柱的相位轨道、通量和逐周期能量账本。"""

    grid: PeriodicDynamicHalfColumn
    frequency_hz: NDArray[np.float64]
    radiation_closure: DynamicRadiationClosure
    includes_collisional_kinetics: bool
    temperature_k: NDArray[np.float64]
    hydrogen_fraction: NDArray[np.float64]
    helium_fraction: NDArray[np.float64]
    electron_density_cm3: NDArray[np.float64]
    rosseland_opacity_cm2_g: NDArray[np.float64]
    outward_flux_edges_erg_s_cm2: NDArray[np.float64]
    interval_compression_work_erg_cm2: NDArray[np.float64]
    interval_dissipation_energy_erg_cm2: NDArray[np.float64]
    interval_emergent_energy_erg_cm2: NDArray[np.float64]
    cycle_count: int
    cycle_residual: float
    maximum_relative_local_energy_residual: float
    maximum_relative_charge_residual: float
    maximum_particle_conservation_residual: float
    minimum_population_fraction: float
    cycle_internal_energy_change_erg_cm2: float
    cycle_compression_work_erg_cm2: float
    cycle_dissipation_energy_erg_cm2: float
    cycle_emergent_energy_erg_cm2: float
    relative_cycle_energy_ledger_residual: float
    minimum_temperature_k: float
    maximum_temperature_k: float
    used_colored_tridiagonal_jacobian: bool


@dataclass(frozen=True)
class PeriodicDynamicCycleCheckpoint:
    """一个完整轨道周期末端的可恢复状态。"""

    cycle_count: int
    cycle_residual: float
    temperature_k: NDArray[np.float64]
    hydrogen_fraction: NDArray[np.float64]
    helium_fraction: NDArray[np.float64]


@dataclass(frozen=True)
class AdaptiveLagrangianMassGrid:
    """由完整周期热结构等分监视函数得到的共享质量网格。"""

    mass_fraction_edges: NDArray[np.float64]
    sampled_mass_fraction: NDArray[np.float64]
    normalized_monitor: NDArray[np.float64]
    log_temperature_component: NDArray[np.float64]
    log_opacity_component: NDArray[np.float64]
    helium_iii_component: NDArray[np.float64]
    minimum_cell_mass_fraction: float
    maximum_cell_mass_fraction: float
    maximum_equidistribution_residual: float


@dataclass(frozen=True)
class TwoGridErrorLagrangianMassGrid:
    """由嵌套粗细解误差等分得到的共享主质量网格。"""

    coarse_mass_fraction_edges: NDArray[np.float64]
    component_names: tuple[str, ...]
    normalized_error_components: NDArray[np.float64]
    normalized_baseline_density: NDArray[np.float64]
    normalized_monitor_density: NDArray[np.float64]
    baseline_monitor_fraction: float
    baseline_mass_spacing_power: float
    master_mass_fraction_edges: NDArray[np.float64]
    minimum_master_cell_mass_fraction: float
    maximum_master_cell_mass_fraction: float
    maximum_equidistribution_residual: float


def build_periodic_dynamic_half_column(
    background: PeriodicColumnBackground,
    half_depth_points: int,
    dissipation_law: DissipationLaw,
    *,
    mass_spacing_power: float = 2.0,
    mass_fraction_edges: ArrayLike | None = None,
    column_mass_relative_tolerance: float = 2.0e-13,
) -> PeriodicDynamicHalfColumn:
    """把 ZO 一周背景映射到共享拉格朗日质量网格。

    当前实现要求单面柱质量沿轨道保持常数。这样每个质量单元才是同一批
    物质；若未来处理随相位变化的柱质量，必须显式加入水平会聚项，不能
    把不同质量网格直接拼接成时间轨道。
    """
    if not isinstance(background, PeriodicColumnBackground):
        raise TypeError("background must be a PeriodicColumnBackground")
    tolerance = float(column_mass_relative_tolerance)
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise PhysicalDomainError(
            "column_mass_relative_tolerance must be finite and positive"
        )
    column_mass = np.asarray(
        background.one_sided_column_mass_g_cm2, dtype=np.float64
    )
    reference_mass = float(column_mass[0])
    relative_variation = float(
        np.max(np.abs(column_mass - reference_mass)) / reference_mass
    )
    if relative_variation > tolerance:
        raise PhysicalDomainError(
            "periodic dynamic Lagrangian grid currently requires phase-invariant "
            "one-sided column mass"
        )

    density = np.empty((background.phase_points, int(half_depth_points)))
    dissipation = np.empty_like(density)
    mass_edges = None
    for phase in range(background.phase_points):
        column = build_zo_constrained_n3_column(
            reference_mass,
            float(background.scale_height_cm[phase]),
            float(background.pressure_gravity_coefficient_s2[phase]),
            half_depth_points,
            mass_spacing_power=mass_spacing_power,
            mass_fraction_edges=mass_fraction_edges,
        )
        profile = symmetric_dissipation_profile(
            column,
            float(background.one_face_surface_flux_erg_s_cm2[phase]),
            dissipation_law,
        )
        if mass_edges is None:
            mass_edges = np.array(column.half_mass_edges_g_cm2, copy=True)
        elif not np.array_equal(mass_edges, column.half_mass_edges_g_cm2):
            raise ArithmeticError("periodic half-column mass grid changed with phase")
        density[phase] = column.full_density_g_cm3[: int(half_depth_points)]
        dissipation[phase] = profile.half_specific_heating_erg_s_g

    if mass_edges is None:
        raise ArithmeticError("periodic half-column construction produced no grid")
    cell_mass = np.diff(mass_edges)
    recovered = np.sum(dissipation * cell_mass[None, :], axis=1)
    target = np.asarray(background.one_face_surface_flux_erg_s_cm2)
    relative_flux_residual = np.max(np.abs(recovered - target) / target)
    if relative_flux_residual > 2.0e-13:
        raise ArithmeticError("periodic dissipation did not recover the ZO face flux")
    if (
        not np.all(np.isfinite(density))
        or np.any(density <= 0.0)
        or not np.all(np.isfinite(dissipation))
        or np.any(dissipation < 0.0)
    ):
        raise ArithmeticError("periodic dynamic half-column became invalid")
    return PeriodicDynamicHalfColumn(
        background=background,
        dissipation_law=dissipation_law,
        mass_fraction_edges=_readonly(mass_edges / reference_mass),
        cell_mass_g_cm2=_readonly(cell_mass),
        density_g_cm3=_readonly(density),
        specific_dissipation_erg_s_g=_readonly(dissipation),
        one_face_target_flux_erg_s_cm2=_readonly(np.array(target, copy=True)),
        maximum_relative_column_mass_variation=relative_variation,
    )


def cyclic_log_density_increments(
    density_g_cm3: ArrayLike,
) -> NDArray[np.float64]:
    """返回每一时间区间的精确 ``Delta ln(rho)``，包含末端回绕。"""
    density = np.asarray(density_g_cm3, dtype=np.float64)
    if density.ndim != 2 or density.shape[0] < 2 or density.shape[1] < 1:
        raise PhysicalDomainError("density_g_cm3 must have shape (phase, depth)")
    if not np.all(np.isfinite(density)) or np.any(density <= 0.0):
        raise PhysicalDomainError("density_g_cm3 must be finite and positive")
    increment = np.log(np.roll(density, -1, axis=0) / density)
    if not np.all(np.isfinite(increment)):
        raise ArithmeticError("cyclic logarithmic density increment became invalid")
    return _readonly(increment)


def ideal_gas_adiabatic_temperature_k(
    density_g_cm3: ArrayLike,
    reference_temperature_k: float,
    *,
    adiabatic_index: float = 5.0 / 3.0,
) -> NDArray[np.float64]:
    """回收解析理想气体绝热关系 ``T/T0=(rho/rho0)^(gamma-1)``。"""
    density = np.asarray(density_g_cm3, dtype=np.float64)
    temperature = float(reference_temperature_k)
    gamma = float(adiabatic_index)
    if density.ndim != 1 or density.size < 2:
        raise PhysicalDomainError("density_g_cm3 must be a 1D trajectory")
    if not np.all(np.isfinite(density)) or np.any(density <= 0.0):
        raise PhysicalDomainError("density_g_cm3 must be finite and positive")
    if not np.isfinite(temperature) or temperature <= 0.0:
        raise PhysicalDomainError("reference_temperature_k must be finite and positive")
    if not np.isfinite(gamma) or gamma <= 1.0:
        raise PhysicalDomainError("adiabatic_index must be finite and greater than one")
    result = temperature * (density / density[0]) ** (gamma - 1.0)
    return _readonly(result)


def ground_state_thermodynamics(
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    hydrogen_fraction: ArrayLike,
    helium_fraction: ArrayLike,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> GroundStateThermodynamics:
    """计算含电离势能的 H/He 基态气体加辐射热力学量。"""
    density, temperature = np.broadcast_arrays(
        np.asarray(density_g_cm3, dtype=np.float64),
        np.asarray(temperature_k, dtype=np.float64),
    )
    hydrogen = np.asarray(hydrogen_fraction, dtype=np.float64)
    helium = np.asarray(helium_fraction, dtype=np.float64)
    if density.ndim != 1 or hydrogen.shape != (density.size, 2) or helium.shape != (
        density.size,
        3,
    ):
        raise PhysicalDomainError("thermodynamic arrays must share one depth axis")
    if (
        not np.all(np.isfinite(density))
        or np.any(density <= 0.0)
        or not np.all(np.isfinite(temperature))
        or np.any(temperature <= 0.0)
    ):
        raise PhysicalDomainError("density and temperature must be finite and positive")
    if (
        not np.all(np.isfinite(hydrogen))
        or not np.all(np.isfinite(helium))
        or np.any(hydrogen < 0.0)
        or np.any(helium < 0.0)
    ):
        raise PhysicalDomainError("population fractions must be finite and non-negative")
    tolerance = 128.0 * np.finfo(np.float64).eps
    if np.any(np.abs(np.sum(hydrogen, axis=1) - 1.0) > tolerance):
        raise PhysicalDomainError("hydrogen fractions must sum to one")
    if np.any(np.abs(np.sum(helium, axis=1) - 1.0) > tolerance):
        raise PhysicalDomainError("helium fractions must sum to one")

    hydrogen_per_gram = composition.hydrogen_mass_fraction / PROTON_MASS_G
    helium_per_gram = composition.helium_mass_fraction / (4.0 * PROTON_MASS_G)
    electron_per_gram = hydrogen_per_gram * hydrogen[:, 1] + helium_per_gram * (
        helium[:, 1] + 2.0 * helium[:, 2]
    )
    nuclei_per_gram = hydrogen_per_gram + helium_per_gram
    specific_gas = 1.5 * BOLTZMANN_ERG_K * temperature * (
        nuclei_per_gram + electron_per_gram
    )
    radiation_constant = 4.0 * STEFAN_BOLTZMANN_ERG_S_CM2_K4 / LIGHT_SPEED_CM_S
    specific_radiation = radiation_constant * temperature**4 / density
    specific_ionization = (
        hydrogen_per_gram * hydrogen[:, 1] * HYDROGEN_IONIZATION_ERG
        + helium_per_gram
        * (
            helium[:, 1] * HELIUM_I_IONIZATION_ERG
            + helium[:, 2]
            * (HELIUM_I_IONIZATION_ERG + HELIUM_II_IONIZATION_ERG)
        )
    )
    gas_pressure = BOLTZMANN_ERG_K * temperature * density * (
        nuclei_per_gram + electron_per_gram
    )
    radiation_pressure = radiation_constant * temperature**4 / 3.0
    total_energy = specific_gas + specific_radiation + specific_ionization
    total_pressure = gas_pressure + radiation_pressure
    electron_density = density * electron_per_gram
    arrays = (
        specific_gas,
        specific_radiation,
        specific_ionization,
        total_energy,
        gas_pressure,
        radiation_pressure,
        total_pressure,
        electron_density,
    )
    if not all(np.all(np.isfinite(array)) and np.all(array >= 0.0) for array in arrays):
        raise ArithmeticError("ground-state thermodynamics became invalid")
    if np.any(total_energy <= 0.0) or np.any(total_pressure <= 0.0):
        raise ArithmeticError("total energy and pressure must be positive")
    return GroundStateThermodynamics(
        *(_readonly(np.array(array, copy=True)) for array in arrays)
    )


def local_planck_ground_state_rates(
    temperature_k: ArrayLike,
    frequency_hz: ArrayLike,
    *,
    include_collisional_kinetics: bool = False,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
]:
    """返回局域 Planck--Milne 辐射率和碰撞/三体率。"""
    temperature = np.asarray(temperature_k, dtype=np.float64)
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    if temperature.ndim != 1 or temperature.size < 1:
        raise PhysicalDomainError("temperature_k must be a non-empty 1D array")
    mean = planck_nu(frequency[:, None], temperature[None, :])
    radiative = ground_state_milne_radiative_rates(
        temperature, frequency, mean
    )
    if not isinstance(include_collisional_kinetics, (bool, np.bool_)):
        raise PhysicalDomainError("include_collisional_kinetics must be boolean")
    if include_collisional_kinetics:
        collision = np.column_stack(
            [
                fit.coefficient_cm3_s(temperature)
                for fit in H_HE_COLLISIONAL_IONIZATION_FITS
            ]
        )
        saha = np.column_stack(
            [
                ground_state_saha_factor_cm3(temperature, energy)
                for energy in IONIZATION_ENERGIES_EV
            ]
        )
        three_body = np.column_stack(
            [
                detailed_balance_three_body_recombination_coefficient_cm6_s(
                    collision[:, species], saha[:, species]
                )
                for species in range(3)
            ]
        )
    else:
        # 中文：7B4i 主门只推进 Milne 辐射率；碰撞网络留作独立敏感性开关。
        collision = np.zeros((temperature.size, 3), dtype=np.float64)
        three_body = np.zeros_like(collision)
    return (
        radiative.photoionization_s1,
        collision,
        radiative.total_recombination_cm3_s,
        three_body,
    )


def ground_state_rosseland_mean_opacity_cm2_g(
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    frequency_hz: ArrayLike,
    hydrogen_fraction: ArrayLike,
    helium_fraction: ArrayLike,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> NDArray[np.float64]:
    """由时间依赖基态分数计算 Milne 连续谱 Rosseland 平均。"""
    density = np.asarray(density_g_cm3, dtype=np.float64)
    temperature = np.asarray(temperature_k, dtype=np.float64)
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    hydrogen = np.asarray(hydrogen_fraction, dtype=np.float64)
    helium = np.asarray(helium_fraction, dtype=np.float64)
    continuum = ground_state_milne_continuum(
        density,
        temperature,
        frequency,
        hydrogen[:, 0],
        hydrogen[:, 1],
        helium[:, 0],
        helium[:, 1],
        helium[:, 2],
        composition=composition,
        include_electron_scattering=True,
    )
    opacity = continuum.extinction_total_per_cm / density[None, :]
    if np.any(opacity <= 0.0):
        raise PhysicalDomainError(
            "Rosseland mean is undefined because a frequency has zero opacity"
        )
    exponent = PLANCK_ERG_S * frequency[:, None] / (
        BOLTZMANN_ERG_K * temperature[None, :]
    )
    derivative = (
        planck_nu(frequency[:, None], temperature[None, :])
        * exponent
        / temperature[None, :]
        / (-np.expm1(-exponent))
    )
    numerator = np.trapezoid(derivative, frequency, axis=0)
    denominator = np.trapezoid(derivative / opacity, frequency, axis=0)
    rosseland = numerator / denominator
    if not np.all(np.isfinite(rosseland)) or np.any(rosseland <= 0.0):
        raise ArithmeticError("dynamic H/He Rosseland mean became invalid")
    return _readonly(np.array(rosseland, copy=True))


def diffusion_outward_flux_edges_erg_s_cm2(
    temperature_k: ArrayLike,
    rosseland_opacity_cm2_g: ArrayLike,
    cell_mass_g_cm2: ArrayLike,
) -> NDArray[np.float64]:
    """计算表面向外为正、并在中面严格为零的灰扩散通量。"""
    temperature = np.asarray(temperature_k, dtype=np.float64)
    opacity = np.asarray(rosseland_opacity_cm2_g, dtype=np.float64)
    cell_mass = np.asarray(cell_mass_g_cm2, dtype=np.float64)
    if (
        temperature.ndim != 1
        or opacity.shape != temperature.shape
        or cell_mass.shape != temperature.shape
    ):
        raise PhysicalDomainError("temperature, opacity and cell mass must share one axis")
    if (
        not np.all(np.isfinite(temperature))
        or np.any(temperature <= 0.0)
        or not np.all(np.isfinite(opacity))
        or np.any(opacity <= 0.0)
        or not np.all(np.isfinite(cell_mass))
        or np.any(cell_mass <= 0.0)
    ):
        raise PhysicalDomainError("diffusion inputs must be finite and positive")
    count = temperature.size
    flux = np.empty(count + 1, dtype=np.float64)
    surface_optical_depth = 0.5 * opacity[0] * cell_mass[0]
    flux[0] = (
        STEFAN_BOLTZMANN_ERG_S_CM2_K4
        * temperature[0] ** 4
        / (0.5 + 0.75 * surface_optical_depth)
    )
    for edge in range(1, count):
        optical_separation = 0.5 * (
            opacity[edge - 1] * cell_mass[edge - 1]
            + opacity[edge] * cell_mass[edge]
        )
        flux[edge] = (
            4.0
            * STEFAN_BOLTZMANN_ERG_S_CM2_K4
            / 3.0
            * (temperature[edge] ** 4 - temperature[edge - 1] ** 4)
            / optical_separation
        )
    # 中文：半柱中面使用镜像对称边界，不以数值小量近似零通量。
    flux[-1] = 0.0
    if not np.all(np.isfinite(flux)) or flux[0] <= 0.0:
        raise ArithmeticError("dynamic diffusion flux became invalid")
    return _readonly(flux)


@dataclass(frozen=True)
class _StepEvaluation:
    temperature_k: NDArray[np.float64]
    hydrogen_fraction: NDArray[np.float64]
    helium_fraction: NDArray[np.float64]
    thermodynamics: GroundStateThermodynamics
    rosseland_opacity_cm2_g: NDArray[np.float64]
    outward_flux_edges_erg_s_cm2: NDArray[np.float64]
    residual: NDArray[np.float64]
    compression_work_erg_g: NDArray[np.float64]
    relative_charge_residual: float
    particle_conservation_residual: float
    minimum_population_fraction: float


def _advance_populations(
    previous_hydrogen: NDArray[np.float64],
    previous_helium: NDArray[np.float64],
    density: NDArray[np.float64],
    temperature: NDArray[np.float64],
    duration_s: float,
    frequency: NDArray[np.float64],
    composition: FullyIonizedHydrogenHeliumComposition,
    include_collisional_kinetics: bool,
) -> tuple[NDArray[np.float64], NDArray[np.float64], float, float, float]:
    photo, collision, radiative, three_body = local_planck_ground_state_rates(
        temperature,
        frequency,
        include_collisional_kinetics=include_collisional_kinetics,
    )
    hydrogen_nuclei = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium_nuclei = composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    hydrogen = np.empty_like(previous_hydrogen)
    helium = np.empty_like(previous_helium)
    maximum_charge = 0.0
    maximum_particle = 0.0
    minimum_population = 1.0
    for depth in range(density.size):
        step = charge_neutral_backward_euler_step(
            previous_hydrogen[depth],
            previous_helium[depth],
            float(hydrogen_nuclei[depth]),
            float(helium_nuclei[depth]),
            duration_s,
            photo[depth],
            collision[depth],
            radiative[depth],
            three_body[depth],
            bisection_iterations=64,
        )
        hydrogen[depth] = step.hydrogen_fraction
        helium[depth] = step.helium_fraction
        maximum_charge = max(maximum_charge, step.relative_charge_residual)
        maximum_particle = max(maximum_particle, step.particle_conservation_residual)
        minimum_population = min(minimum_population, step.minimum_fraction)
    return hydrogen, helium, maximum_charge, maximum_particle, minimum_population


def _evaluate_step(
    log_temperature: NDArray[np.float64],
    previous_temperature: NDArray[np.float64],
    previous_hydrogen: NDArray[np.float64],
    previous_helium: NDArray[np.float64],
    previous_density: NDArray[np.float64],
    new_density: NDArray[np.float64],
    new_specific_dissipation: NDArray[np.float64],
    cell_mass: NDArray[np.float64],
    duration_s: float,
    frequency: NDArray[np.float64],
    composition: FullyIonizedHydrogenHeliumComposition,
    include_collisional_kinetics: bool,
) -> _StepEvaluation:
    temperature = np.exp(log_temperature)
    hydrogen, helium, charge, particle, minimum = _advance_populations(
        previous_hydrogen,
        previous_helium,
        new_density,
        temperature,
        duration_s,
        frequency,
        composition,
        include_collisional_kinetics,
    )
    old_thermodynamics = ground_state_thermodynamics(
        previous_density,
        previous_temperature,
        previous_hydrogen,
        previous_helium,
        composition=composition,
    )
    new_thermodynamics = ground_state_thermodynamics(
        new_density,
        temperature,
        hydrogen,
        helium,
        composition=composition,
    )
    opacity = ground_state_rosseland_mean_opacity_cm2_g(
        new_density,
        temperature,
        frequency,
        hydrogen,
        helium,
        composition=composition,
    )
    flux = diffusion_outward_flux_edges_erg_s_cm2(
        temperature, opacity, cell_mass
    )
    specific_volume_change = 1.0 / new_density - 1.0 / previous_density
    # 中文：梯形压力功直接使用相邻物理态，不以 dlnH/dt 的点值替代有限步压缩。
    work = -0.5 * (
        old_thermodynamics.total_pressure_erg_cm3
        + new_thermodynamics.total_pressure_erg_cm3
    ) * specific_volume_change
    radiative_rate = (flux[1:] - flux[:-1]) / cell_mass
    energy_change = (
        new_thermodynamics.specific_total_energy_erg_g
        - old_thermodynamics.specific_total_energy_erg_g
    )
    right_hand_side = work + duration_s * (
        new_specific_dissipation + radiative_rate
    )
    scale = (
        np.abs(new_thermodynamics.specific_total_energy_erg_g)
        + np.abs(old_thermodynamics.specific_total_energy_erg_g)
        + np.abs(work)
        + duration_s
        * (
            new_specific_dissipation
            + (np.abs(flux[1:]) + np.abs(flux[:-1])) / cell_mass
        )
    )
    if np.any(scale <= 0.0):
        raise ArithmeticError("dynamic energy residual has no positive scale")
    residual = (energy_change - right_hand_side) / scale
    if not np.all(np.isfinite(residual)):
        raise ArithmeticError("dynamic energy residual became non-finite")
    return _StepEvaluation(
        temperature_k=_readonly(np.array(temperature, copy=True)),
        hydrogen_fraction=_readonly(hydrogen),
        helium_fraction=_readonly(helium),
        thermodynamics=new_thermodynamics,
        rosseland_opacity_cm2_g=opacity,
        outward_flux_edges_erg_s_cm2=flux,
        residual=_readonly(np.array(residual, copy=True)),
        compression_work_erg_g=_readonly(np.array(work, copy=True)),
        relative_charge_residual=charge,
        particle_conservation_residual=particle,
        minimum_population_fraction=minimum,
    )


@dataclass(frozen=True)
class _CycleResult:
    temperature_k: NDArray[np.float64]
    hydrogen_fraction: NDArray[np.float64]
    helium_fraction: NDArray[np.float64]
    electron_density_cm3: NDArray[np.float64]
    opacity_cm2_g: NDArray[np.float64]
    flux_edges_erg_s_cm2: NDArray[np.float64]
    work_erg_cm2: NDArray[np.float64]
    dissipation_erg_cm2: NDArray[np.float64]
    emergent_erg_cm2: NDArray[np.float64]
    end_temperature_k: NDArray[np.float64]
    end_hydrogen_fraction: NDArray[np.float64]
    end_helium_fraction: NDArray[np.float64]
    maximum_energy_residual: float
    maximum_charge_residual: float
    maximum_particle_residual: float
    minimum_population: float


def _run_cycle(
    grid: PeriodicDynamicHalfColumn,
    frequency: NDArray[np.float64],
    initial_temperature: NDArray[np.float64],
    initial_hydrogen: NDArray[np.float64],
    initial_helium: NDArray[np.float64],
    *,
    minimum_temperature_k: float,
    maximum_temperature_k: float,
    local_energy_tolerance: float,
    optimizer_tolerance: float,
    maximum_function_evaluations: int,
    composition: FullyIonizedHydrogenHeliumComposition,
    include_collisional_kinetics: bool,
    use_colored_tridiagonal_jacobian: bool,
) -> _CycleResult:
    phases = grid.phase_points
    depth_points = grid.half_depth_points
    temperatures = np.empty((phases, depth_points))
    hydrogen = np.empty((phases, depth_points, 2))
    helium = np.empty((phases, depth_points, 3))
    electron = np.empty((phases, depth_points))
    opacity = np.empty((phases, depth_points))
    flux = np.empty((phases, depth_points + 1))
    work = np.empty(phases)
    dissipation = np.empty(phases)
    emergent = np.empty(phases)
    temperatures[0] = initial_temperature
    hydrogen[0] = initial_hydrogen
    helium[0] = initial_helium
    initial_thermodynamics = ground_state_thermodynamics(
        grid.density_g_cm3[0],
        initial_temperature,
        initial_hydrogen,
        initial_helium,
        composition=composition,
    )
    electron[0] = initial_thermodynamics.electron_density_cm3
    opacity[0] = ground_state_rosseland_mean_opacity_cm2_g(
        grid.density_g_cm3[0],
        initial_temperature,
        frequency,
        initial_hydrogen,
        initial_helium,
        composition=composition,
    )
    flux[0] = diffusion_outward_flux_edges_erg_s_cm2(
        initial_temperature, opacity[0], grid.cell_mass_g_cm2
    )
    current_temperature = np.array(initial_temperature, copy=True)
    current_hydrogen = np.array(initial_hydrogen, copy=True)
    current_helium = np.array(initial_helium, copy=True)
    maximum_energy_residual = 0.0
    maximum_charge_residual = 0.0
    maximum_particle_residual = 0.0
    minimum_population = float(
        min(np.min(initial_hydrogen), np.min(initial_helium))
    )

    lower = np.full(depth_points, np.log(minimum_temperature_k))
    upper = np.full(depth_points, np.log(maximum_temperature_k))
    for phase in range(phases):
        following = (phase + 1) % phases
        duration = float(grid.background.step_duration_s[phase])

        def objective(log_temperature: NDArray[np.float64]) -> NDArray[np.float64]:
            return _evaluate_step(
                log_temperature,
                current_temperature,
                current_hydrogen,
                current_helium,
                grid.density_g_cm3[phase],
                grid.density_g_cm3[following],
                grid.specific_dissipation_erg_s_g[following],
                grid.cell_mass_g_cm2,
                duration,
                frequency,
                composition,
                include_collisional_kinetics,
            ).residual

        jacobian: str | Callable[[NDArray[np.float64]], NDArray[np.float64]] = (
            "2-point"
        )
        if use_colored_tridiagonal_jacobian:
            # 中文：三种列颜色没有共享残差行，用四次函数值回收完整三对角 Jacobian。
            def colored_jacobian(
                log_temperature: NDArray[np.float64],
            ) -> NDArray[np.float64]:
                base = objective(log_temperature)
                step = np.sqrt(np.finfo(np.float64).eps) * np.maximum(
                    1.0, np.abs(log_temperature)
                )
                forward = log_temperature + step <= upper
                step[~forward] = -step[~forward]
                if np.any(log_temperature + step < lower):
                    raise ArithmeticError(
                        "colored finite-difference step left the temperature bounds"
                    )
                result = np.zeros((depth_points, depth_points), dtype=np.float64)
                for color in range(3):
                    columns = np.arange(color, depth_points, 3)
                    trial = np.array(log_temperature, copy=True)
                    trial[columns] += step[columns]
                    difference = objective(trial) - base
                    for column in columns:
                        row_slice = slice(
                            max(0, int(column) - 1),
                            min(depth_points, int(column) + 2),
                        )
                        result[row_slice, column] = (
                            difference[row_slice] / step[column]
                        )
                return result

            jacobian = colored_jacobian

        result = least_squares(
            objective,
            np.log(current_temperature),
            jac=jacobian,
            bounds=(lower, upper),
            xtol=optimizer_tolerance,
            ftol=optimizer_tolerance,
            gtol=optimizer_tolerance,
            max_nfev=maximum_function_evaluations,
        )
        if not result.success:
            raise RuntimeError(
                f"dynamic energy solve failed at phase {phase}: {result.message}"
            )
        if np.any(result.active_mask != 0):
            raise PhysicalDomainError(
                f"dynamic energy root reached a microphysics temperature bound at phase {phase}"
            )
        evaluated = _evaluate_step(
            result.x,
            current_temperature,
            current_hydrogen,
            current_helium,
            grid.density_g_cm3[phase],
            grid.density_g_cm3[following],
            grid.specific_dissipation_erg_s_g[following],
            grid.cell_mass_g_cm2,
            duration,
            frequency,
            composition,
            include_collisional_kinetics,
        )
        step_residual = float(np.max(np.abs(evaluated.residual)))
        if step_residual > local_energy_tolerance:
            raise RuntimeError(
                f"dynamic energy residual {step_residual:.3e} exceeds tolerance "
                f"at phase {phase}"
            )
        work[phase] = float(
            np.sum(evaluated.compression_work_erg_g * grid.cell_mass_g_cm2)
        )
        dissipation[phase] = float(
            duration
            * np.sum(
                grid.specific_dissipation_erg_s_g[following]
                * grid.cell_mass_g_cm2
            )
        )
        emergent[phase] = duration * float(
            evaluated.outward_flux_edges_erg_s_cm2[0]
        )
        # work 仍是逐步比能积分，持续时间已包含在有限体积变化中。
        maximum_energy_residual = max(maximum_energy_residual, step_residual)
        maximum_charge_residual = max(
            maximum_charge_residual, evaluated.relative_charge_residual
        )
        maximum_particle_residual = max(
            maximum_particle_residual, evaluated.particle_conservation_residual
        )
        minimum_population = min(
            minimum_population, evaluated.minimum_population_fraction
        )
        current_temperature = np.array(evaluated.temperature_k, copy=True)
        current_hydrogen = np.array(evaluated.hydrogen_fraction, copy=True)
        current_helium = np.array(evaluated.helium_fraction, copy=True)
        if following != 0:
            temperatures[following] = current_temperature
            hydrogen[following] = current_hydrogen
            helium[following] = current_helium
            electron[following] = evaluated.thermodynamics.electron_density_cm3
            opacity[following] = evaluated.rosseland_opacity_cm2_g
            flux[following] = evaluated.outward_flux_edges_erg_s_cm2

    return _CycleResult(
        temperature_k=_readonly(temperatures),
        hydrogen_fraction=_readonly(hydrogen),
        helium_fraction=_readonly(helium),
        electron_density_cm3=_readonly(electron),
        opacity_cm2_g=_readonly(opacity),
        flux_edges_erg_s_cm2=_readonly(flux),
        work_erg_cm2=_readonly(work),
        dissipation_erg_cm2=_readonly(dissipation),
        emergent_erg_cm2=_readonly(emergent),
        end_temperature_k=_readonly(current_temperature),
        end_hydrogen_fraction=_readonly(current_hydrogen),
        end_helium_fraction=_readonly(current_helium),
        maximum_energy_residual=maximum_energy_residual,
        maximum_charge_residual=maximum_charge_residual,
        maximum_particle_residual=maximum_particle_residual,
        minimum_population=minimum_population,
    )


def solve_periodic_dynamic_column(
    grid: PeriodicDynamicHalfColumn,
    frequency_hz: ArrayLike,
    initial_temperature_k: ArrayLike,
    initial_hydrogen_fraction: ArrayLike,
    initial_helium_fraction: ArrayLike,
    *,
    radiation_closure: DynamicRadiationClosure = "local_planck_milne",
    include_collisional_kinetics: bool = False,
    minimum_temperature_k: float | None = None,
    maximum_temperature_k: float = 1.0e8,
    cycle_tolerance: float = 1.0e-8,
    local_energy_tolerance: float = 2.0e-8,
    optimizer_tolerance: float = 1.0e-10,
    maximum_function_evaluations: int = 96,
    maximum_cycles: int = 16,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
    use_colored_tridiagonal_jacobian: bool = False,
    cycle_callback: Callable[[PeriodicDynamicCycleCheckpoint], None] | None = None,
) -> PeriodicDynamicColumnSolution:
    """迭代完整轨道，直到温度与 H/He 分数失去初态记忆。"""
    if not isinstance(grid, PeriodicDynamicHalfColumn):
        raise TypeError("grid must be a PeriodicDynamicHalfColumn")
    if radiation_closure != "local_planck_milne":
        raise PhysicalDomainError("unsupported dynamic radiation closure")
    if not isinstance(include_collisional_kinetics, (bool, np.bool_)):
        raise PhysicalDomainError("include_collisional_kinetics must be boolean")
    if not isinstance(use_colored_tridiagonal_jacobian, (bool, np.bool_)):
        raise PhysicalDomainError(
            "use_colored_tridiagonal_jacobian must be boolean"
        )
    if cycle_callback is not None and not callable(cycle_callback):
        raise PhysicalDomainError("cycle_callback must be callable or None")
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    if (
        frequency.ndim != 1
        or frequency.size < 2
        or not np.all(np.isfinite(frequency))
        or np.any(frequency <= 0.0)
        or np.any(np.diff(frequency) <= 0.0)
    ):
        raise PhysicalDomainError("frequency_hz must be finite, positive and increasing")
    depth_points = grid.half_depth_points
    temperature = np.array(initial_temperature_k, dtype=np.float64, copy=True)
    hydrogen = np.array(initial_hydrogen_fraction, dtype=np.float64, copy=True)
    helium = np.array(initial_helium_fraction, dtype=np.float64, copy=True)
    if temperature.shape != (depth_points,):
        raise PhysicalDomainError("initial_temperature_k must match the depth grid")
    ground_state_thermodynamics(
        grid.density_g_cm3[0],
        temperature,
        hydrogen,
        helium,
        composition=composition,
    )
    fit_minimum = (
        max(fit.minimum_temperature_k for fit in H_HE_COLLISIONAL_IONIZATION_FITS)
        if include_collisional_kinetics
        else 0.0
    )
    minimum = (
        1.001 * fit_minimum
        if minimum_temperature_k is None and include_collisional_kinetics
        else 1.0e3
        if minimum_temperature_k is None
        else float(minimum_temperature_k)
    )
    maximum = float(maximum_temperature_k)
    if (
        not np.isfinite(minimum)
        or not np.isfinite(maximum)
        or minimum <= fit_minimum
        or maximum <= minimum
    ):
        raise PhysicalDomainError(
            "temperature bounds must lie inside the declared atomic-fit domain"
        )
    if np.any(temperature <= minimum) or np.any(temperature >= maximum):
        raise PhysicalDomainError("initial temperature lies outside solver bounds")
    for name, value in (
        ("cycle_tolerance", cycle_tolerance),
        ("local_energy_tolerance", local_energy_tolerance),
        ("optimizer_tolerance", optimizer_tolerance),
    ):
        if not np.isfinite(value) or value <= 0.0:
            raise PhysicalDomainError(f"{name} must be finite and positive")
    for name, value in (
        ("maximum_function_evaluations", maximum_function_evaluations),
        ("maximum_cycles", maximum_cycles),
    ):
        if (
            not isinstance(value, (int, np.integer))
            or isinstance(value, (bool, np.bool_))
            or int(value) < 1
        ):
            raise PhysicalDomainError(f"{name} must be a positive integer")

    cycle = None
    residual = np.inf
    for cycle_count in range(1, int(maximum_cycles) + 1):
        cycle = _run_cycle(
            grid,
            frequency,
            temperature,
            hydrogen,
            helium,
            minimum_temperature_k=minimum,
            maximum_temperature_k=maximum,
            local_energy_tolerance=float(local_energy_tolerance),
            optimizer_tolerance=float(optimizer_tolerance),
            maximum_function_evaluations=int(maximum_function_evaluations),
            composition=composition,
            include_collisional_kinetics=bool(include_collisional_kinetics),
            use_colored_tridiagonal_jacobian=bool(
                use_colored_tridiagonal_jacobian
            ),
        )
        temperature_residual = float(
            np.max(
                2.0
                * np.abs(cycle.end_temperature_k - temperature)
                / (np.abs(cycle.end_temperature_k) + np.abs(temperature))
            )
        )
        population_residual = float(
            max(
                np.max(np.abs(cycle.end_hydrogen_fraction - hydrogen)),
                np.max(np.abs(cycle.end_helium_fraction - helium)),
            )
        )
        residual = max(temperature_residual, population_residual)
        if cycle_callback is not None:
            # 中文：只在完整周期结束后暴露状态，检查点不会截断单个物理轨道。
            cycle_callback(
                PeriodicDynamicCycleCheckpoint(
                    cycle_count=cycle_count,
                    cycle_residual=residual,
                    temperature_k=_readonly(
                        np.array(cycle.end_temperature_k, copy=True)
                    ),
                    hydrogen_fraction=_readonly(
                        np.array(cycle.end_hydrogen_fraction, copy=True)
                    ),
                    helium_fraction=_readonly(
                        np.array(cycle.end_helium_fraction, copy=True)
                    ),
                )
            )
        if residual <= cycle_tolerance:
            break
        temperature = np.array(cycle.end_temperature_k, copy=True)
        hydrogen = np.array(cycle.end_hydrogen_fraction, copy=True)
        helium = np.array(cycle.end_helium_fraction, copy=True)
    else:
        raise RuntimeError("periodic dynamic column did not converge within maximum_cycles")
    if cycle is None:
        raise ArithmeticError("periodic dynamic solver produced no cycle")

    initial_thermodynamics = ground_state_thermodynamics(
        grid.density_g_cm3[0],
        cycle.temperature_k[0],
        cycle.hydrogen_fraction[0],
        cycle.helium_fraction[0],
        composition=composition,
    )
    final_thermodynamics = ground_state_thermodynamics(
        grid.density_g_cm3[0],
        cycle.end_temperature_k,
        cycle.end_hydrogen_fraction,
        cycle.end_helium_fraction,
        composition=composition,
    )
    internal_change = float(
        np.sum(
            (
                final_thermodynamics.specific_total_energy_erg_g
                - initial_thermodynamics.specific_total_energy_erg_g
            )
            * grid.cell_mass_g_cm2
        )
    )
    total_work = float(np.sum(cycle.work_erg_cm2))
    total_dissipation = float(np.sum(cycle.dissipation_erg_cm2))
    total_emergent = float(np.sum(cycle.emergent_erg_cm2))
    ledger_difference = internal_change - (
        total_work + total_dissipation - total_emergent
    )
    ledger_scale = (
        abs(internal_change)
        + abs(total_work)
        + abs(total_dissipation)
        + abs(total_emergent)
    )
    if ledger_scale <= 0.0:
        raise ArithmeticError("cycle energy ledger has no positive scale")
    ledger_residual = abs(ledger_difference) / ledger_scale
    arrays = (
        cycle.temperature_k,
        cycle.hydrogen_fraction,
        cycle.helium_fraction,
        cycle.electron_density_cm3,
        cycle.opacity_cm2_g,
        cycle.flux_edges_erg_s_cm2,
    )
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ArithmeticError("periodic dynamic solution became non-finite")
    return PeriodicDynamicColumnSolution(
        grid=grid,
        frequency_hz=_readonly(frequency),
        radiation_closure=radiation_closure,
        includes_collisional_kinetics=bool(include_collisional_kinetics),
        temperature_k=cycle.temperature_k,
        hydrogen_fraction=cycle.hydrogen_fraction,
        helium_fraction=cycle.helium_fraction,
        electron_density_cm3=cycle.electron_density_cm3,
        rosseland_opacity_cm2_g=cycle.opacity_cm2_g,
        outward_flux_edges_erg_s_cm2=cycle.flux_edges_erg_s_cm2,
        interval_compression_work_erg_cm2=cycle.work_erg_cm2,
        interval_dissipation_energy_erg_cm2=cycle.dissipation_erg_cm2,
        interval_emergent_energy_erg_cm2=cycle.emergent_erg_cm2,
        cycle_count=cycle_count,
        cycle_residual=residual,
        maximum_relative_local_energy_residual=cycle.maximum_energy_residual,
        maximum_relative_charge_residual=cycle.maximum_charge_residual,
        maximum_particle_conservation_residual=cycle.maximum_particle_residual,
        minimum_population_fraction=cycle.minimum_population,
        cycle_internal_energy_change_erg_cm2=internal_change,
        cycle_compression_work_erg_cm2=total_work,
        cycle_dissipation_energy_erg_cm2=total_dissipation,
        cycle_emergent_energy_erg_cm2=total_emergent,
        relative_cycle_energy_ledger_residual=ledger_residual,
        minimum_temperature_k=float(np.min(cycle.temperature_k)),
        maximum_temperature_k=float(np.max(cycle.temperature_k)),
        used_colored_tridiagonal_jacobian=bool(
            use_colored_tridiagonal_jacobian
        ),
    )


def adaptive_lagrangian_mass_grid(
    pilot: PeriodicDynamicColumnSolution,
    target_half_depth_points: int,
    *,
    monitor_sample_points: int = 4097,
) -> AdaptiveLagrangianMassGrid:
    """对温度、Rosseland opacity 和 He III 前沿等权等分。

    三个梯度分量各自按质量坐标积分归一，因此没有可调的发射率式权重；
    常数背景项与每个物理分量贡献相同的总监视量，防止网格只覆盖电离前沿。
    同一组边界用于全部轨道相位，保持拉格朗日单元身份。
    """
    if not isinstance(pilot, PeriodicDynamicColumnSolution):
        raise TypeError("pilot must be a PeriodicDynamicColumnSolution")
    if (
        not isinstance(target_half_depth_points, (int, np.integer))
        or isinstance(target_half_depth_points, (bool, np.bool_))
        or int(target_half_depth_points) < 4
    ):
        raise PhysicalDomainError(
            "target_half_depth_points must be an integer of at least four"
        )
    if (
        not isinstance(monitor_sample_points, (int, np.integer))
        or isinstance(monitor_sample_points, (bool, np.bool_))
        or int(monitor_sample_points) < 257
    ):
        raise PhysicalDomainError(
            "monitor_sample_points must be an integer of at least 257"
        )
    target = int(target_half_depth_points)
    samples = int(monitor_sample_points)
    centres = 0.5 * (
        pilot.grid.mass_fraction_edges[:-1]
        + pilot.grid.mass_fraction_edges[1:]
    )
    if centres.size < 3:
        raise PhysicalDomainError("pilot mass grid needs at least three cells")
    sampled_mass = np.linspace(0.0, 1.0, samples)

    def component(field: NDArray[np.float64]) -> NDArray[np.float64]:
        gradient = np.gradient(field, centres, axis=1, edge_order=2)
        envelope = np.max(np.abs(gradient), axis=0)
        sampled = np.interp(sampled_mass, centres, envelope)
        integral = float(np.trapezoid(sampled, sampled_mass))
        if not np.isfinite(integral) or integral <= 0.0:
            raise PhysicalDomainError(
                "adaptive monitor component has no positive orbital variation"
            )
        normalized = sampled / integral
        if not np.all(np.isfinite(normalized)) or np.any(normalized < 0.0):
            raise ArithmeticError("adaptive monitor component became invalid")
        return normalized

    temperature_component = component(np.log(pilot.temperature_k))
    opacity_component = component(np.log(pilot.rosseland_opacity_cm2_g))
    helium_component = component(pilot.helium_fraction[:, :, 2])
    monitor = (
        np.ones(samples, dtype=np.float64)
        + temperature_component
        + opacity_component
        + helium_component
    )
    interval = np.diff(sampled_mass)
    cumulative = np.empty(samples, dtype=np.float64)
    cumulative[0] = 0.0
    cumulative[1:] = np.cumsum(
        0.5 * (monitor[:-1] + monitor[1:]) * interval
    )
    total = float(cumulative[-1])
    if not np.isfinite(total) or total <= 0.0:
        raise ArithmeticError("adaptive monitor integral became invalid")
    normalized_cumulative = cumulative / total
    quantile = np.arange(target + 1, dtype=np.float64) / target
    edges = np.interp(quantile, normalized_cumulative, sampled_mass)
    edges[0] = 0.0
    edges[-1] = 1.0
    width = np.diff(edges)
    if (
        not np.all(np.isfinite(edges))
        or np.any(width <= 0.0)
        or edges[0] != 0.0
        or edges[-1] != 1.0
    ):
        raise ArithmeticError("adaptive Lagrangian mass grid became invalid")
    recovered_quantile = np.interp(edges, sampled_mass, normalized_cumulative)
    residual = float(np.max(np.abs(recovered_quantile - quantile)))
    return AdaptiveLagrangianMassGrid(
        mass_fraction_edges=_readonly(edges),
        sampled_mass_fraction=_readonly(sampled_mass),
        normalized_monitor=_readonly(monitor / total),
        log_temperature_component=_readonly(temperature_component),
        log_opacity_component=_readonly(opacity_component),
        helium_iii_component=_readonly(helium_component),
        minimum_cell_mass_fraction=float(np.min(width)),
        maximum_cell_mass_fraction=float(np.max(width)),
        maximum_equidistribution_residual=residual,
    )


def two_grid_error_lagrangian_mass_grid(
    coarse: PeriodicDynamicColumnSolution,
    refined: PeriodicDynamicColumnSolution,
    master_half_depth_points: int,
    *,
    baseline_monitor_fraction: float = 0.5,
    baseline_mass_spacing_power: float = 2.0,
) -> TwoGridErrorLagrangianMassGrid:
    """由嵌套粗细周期解构造兼顾局部与柱平均误差的主网格。

    每个粗单元内同时估计热力学量与人口的子单元逐点误差和质量平均
    误差。四个非零分量分别按质量坐标归一；均匀监视量占总积分的声明
    比例。基线严格回收 ``x_j=(j/N)^p`` 的解析几何分辨率，而不是
    均匀质量网格；主网格可再按整数因子抽取，得到严格嵌套序列。
    """
    if not isinstance(coarse, PeriodicDynamicColumnSolution) or not isinstance(
        refined, PeriodicDynamicColumnSolution
    ):
        raise TypeError("coarse and refined must be periodic dynamic solutions")
    if coarse.grid.phase_points != refined.grid.phase_points:
        raise PhysicalDomainError("two-grid estimator requires a shared phase grid")
    if not np.array_equal(
        coarse.grid.background.time_since_pericentre_s,
        refined.grid.background.time_since_pericentre_s,
    ):
        raise PhysicalDomainError("two-grid estimator requires identical orbital times")
    if (
        not isinstance(master_half_depth_points, (int, np.integer))
        or isinstance(master_half_depth_points, (bool, np.bool_))
        or int(master_half_depth_points) < coarse.grid.half_depth_points
    ):
        raise PhysicalDomainError(
            "master_half_depth_points must be an integer no smaller than the coarse grid"
        )
    master_points = int(master_half_depth_points)
    baseline_fraction = float(baseline_monitor_fraction)
    if (
        not np.isfinite(baseline_fraction)
        or baseline_fraction <= 0.0
        or baseline_fraction >= 1.0
    ):
        raise PhysicalDomainError(
            "baseline_monitor_fraction must lie strictly between zero and one"
        )
    spacing_power = float(baseline_mass_spacing_power)
    if not np.isfinite(spacing_power) or spacing_power <= 0.0:
        raise PhysicalDomainError(
            "baseline_mass_spacing_power must be finite and positive"
        )

    coarse_edges = coarse.grid.mass_fraction_edges
    refined_edges = refined.grid.mass_fraction_edges
    if refined.grid.half_depth_points <= coarse.grid.half_depth_points:
        raise PhysicalDomainError("refined solution must have more depth cells")
    edge_indices: list[int] = []
    for edge in coarse_edges:
        matches = np.flatnonzero(refined_edges == edge)
        if matches.size != 1:
            raise PhysicalDomainError(
                "refined mass grid must contain every coarse edge exactly"
            )
        edge_indices.append(int(matches[0]))
    if any(
        following <= current
        for current, following in zip(edge_indices[:-1], edge_indices[1:], strict=True)
    ):
        raise PhysicalDomainError("nested mass-edge mapping lost its ordering")

    coarse_width = np.diff(coarse_edges)
    component = {
        "pointwise_thermodynamic": np.zeros(coarse.grid.half_depth_points),
        "pointwise_population": np.zeros(coarse.grid.half_depth_points),
        "cell_average_thermodynamic": np.zeros(coarse.grid.half_depth_points),
        "cell_average_population": np.zeros(coarse.grid.half_depth_points),
    }
    field_pairs = (
        (
            "thermodynamic",
            coarse.temperature_k,
            refined.temperature_k,
            True,
        ),
        (
            "thermodynamic",
            coarse.rosseland_opacity_cm2_g,
            refined.rosseland_opacity_cm2_g,
            True,
        ),
        (
            "population",
            coarse.hydrogen_fraction[:, :, 1],
            refined.hydrogen_fraction[:, :, 1],
            False,
        ),
        (
            "population",
            coarse.helium_fraction[:, :, 2],
            refined.helium_fraction[:, :, 2],
            False,
        ),
    )
    for coarse_index, (start, stop) in enumerate(
        zip(edge_indices[:-1], edge_indices[1:], strict=True)
    ):
        fine_width = np.diff(refined_edges)[start:stop]
        if not np.isclose(
            np.sum(fine_width), coarse_width[coarse_index], rtol=8.0e-15, atol=0.0
        ):
            raise ArithmeticError("nested fine-cell masses do not recover a coarse cell")
        weight = fine_width / coarse_width[coarse_index]
        for family, coarse_field, refined_field, relative in field_pairs:
            parent = coarse_field[:, coarse_index]
            children = refined_field[:, start:stop]
            fine_average = np.sum(children * weight[None, :], axis=1)
            if relative:
                point_denominator = np.abs(children) + np.abs(parent[:, None])
                average_denominator = np.abs(fine_average) + np.abs(parent)
                if np.any(point_denominator <= 0.0) or np.any(
                    average_denominator <= 0.0
                ):
                    raise ArithmeticError(
                        "relative two-grid estimator encountered a zero scale"
                    )
                point_error = 2.0 * np.abs(children - parent[:, None]) / point_denominator
                average_error = 2.0 * np.abs(fine_average - parent) / average_denominator
            else:
                point_error = np.abs(children - parent[:, None])
                average_error = np.abs(fine_average - parent)
            component[f"pointwise_{family}"][coarse_index] = max(
                component[f"pointwise_{family}"][coarse_index],
                float(np.max(point_error)),
            )
            component[f"cell_average_{family}"][coarse_index] = max(
                component[f"cell_average_{family}"][coarse_index],
                float(np.max(average_error)),
            )

    names: list[str] = []
    normalized: list[NDArray[np.float64]] = []
    for name, values in component.items():
        integral = float(np.sum(values * coarse_width))
        if not np.isfinite(integral) or integral < 0.0:
            raise ArithmeticError("two-grid error component became invalid")
        if integral == 0.0:
            continue
        density = values / integral
        if not np.all(np.isfinite(density)) or np.any(density < 0.0):
            raise ArithmeticError("normalized two-grid error became invalid")
        names.append(name)
        normalized.append(density)

    baseline_cdf = coarse_edges ** (1.0 / spacing_power)
    baseline_density = np.diff(baseline_cdf) / coarse_width
    if (
        not np.all(np.isfinite(baseline_density))
        or np.any(baseline_density <= 0.0)
        or not np.isclose(
            np.sum(baseline_density * coarse_width), 1.0, rtol=8.0e-15, atol=0.0
        )
    ):
        raise ArithmeticError("analytic baseline monitor became invalid")

    if normalized:
        component_density = np.vstack(normalized)
        count = component_density.shape[0]
        # 中文：解析 x^p 基线与全部误差分量按声明的积分比例分配。
        baseline = baseline_fraction / (1.0 - baseline_fraction) * count
        raw_monitor = baseline * baseline_density + np.sum(component_density, axis=0)
        total_monitor = baseline + count
        monitor = raw_monitor / total_monitor
        actual_baseline_fraction = baseline_fraction
    else:
        component_density = np.empty((0, coarse.grid.half_depth_points))
        monitor = baseline_density
        actual_baseline_fraction = 1.0
    monitor_integral = float(np.sum(monitor * coarse_width))
    if not np.isclose(monitor_integral, 1.0, rtol=8.0e-15, atol=0.0):
        raise ArithmeticError("two-grid monitor did not integrate to one")

    cumulative = np.concatenate(
        (np.array([0.0]), np.cumsum(monitor * coarse_width))
    )
    cumulative[-1] = 1.0
    quantile = np.arange(master_points + 1, dtype=np.float64) / master_points
    master_edges = np.interp(quantile, cumulative, coarse_edges)
    master_edges[0] = 0.0
    master_edges[-1] = 1.0
    width = np.diff(master_edges)
    if not np.all(np.isfinite(master_edges)) or np.any(width <= 0.0):
        raise ArithmeticError("two-grid master mass grid became invalid")
    recovered = np.interp(master_edges, coarse_edges, cumulative)
    residual = float(np.max(np.abs(recovered - quantile)))
    return TwoGridErrorLagrangianMassGrid(
        coarse_mass_fraction_edges=_readonly(np.array(coarse_edges, copy=True)),
        component_names=tuple(names),
        normalized_error_components=_readonly(component_density),
        normalized_baseline_density=_readonly(baseline_density),
        normalized_monitor_density=_readonly(monitor),
        baseline_monitor_fraction=actual_baseline_fraction,
        baseline_mass_spacing_power=spacing_power,
        master_mass_fraction_edges=_readonly(master_edges),
        minimum_master_cell_mass_fraction=float(np.min(width)),
        maximum_master_cell_mass_fraction=float(np.max(width)),
        maximum_equidistribution_residual=residual,
    )


def nested_mass_fraction_edges(
    master: TwoGridErrorLagrangianMassGrid,
    target_half_depth_points: int,
) -> NDArray[np.float64]:
    """按整数因子抽取主网格，返回严格嵌套的共享质量边界。"""
    if not isinstance(master, TwoGridErrorLagrangianMassGrid):
        raise TypeError("master must be a TwoGridErrorLagrangianMassGrid")
    if (
        not isinstance(target_half_depth_points, (int, np.integer))
        or isinstance(target_half_depth_points, (bool, np.bool_))
        or int(target_half_depth_points) < 2
    ):
        raise PhysicalDomainError(
            "target_half_depth_points must be an integer of at least two"
        )
    target = int(target_half_depth_points)
    master_points = master.master_mass_fraction_edges.size - 1
    if master_points % target != 0:
        raise PhysicalDomainError(
            "target_half_depth_points must divide the master grid exactly"
        )
    stride = master_points // target
    edges = np.array(master.master_mass_fraction_edges[::stride], copy=True)
    if edges.size != target + 1 or edges[-1] != 1.0:
        raise ArithmeticError("nested mass-grid extraction lost an endpoint")
    return _readonly(edges)
