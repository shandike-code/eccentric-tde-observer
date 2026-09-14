"""固定温度板层中的基态 H/He 辐射--布居反馈控制。

本模块只闭合 ``J_nu ->`` 基态光致电离率 ``->`` 稳态布居 ``->``
光致吸收与电子散射 ``-> J_nu``。复合连续发射、激发态、线跃迁与气体
能量方程均不在此闭合内，因此输出是迭代控制，不是完整 NLTE 大气谱。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .atomic_continuum import (
    EV_ERG,
    H_HE_GROUND_STATE_PHOTOIONIZATION_FITS,
    photoionization_rate_from_fit_s1,
)
from .atomic_kinetics import collisional_photoionization_equilibrium
from .atmosphere import (
    PROTON_MASS_G,
    SOLAR_FULLY_IONIZED_H_HE,
    THOMSON_CROSS_SECTION_CM2,
    FullyIonizedHydrogenHeliumComposition,
)
from .radiation import PLANCK_ERG_S
from .radiative_transfer_1d import StaticSlabTransfer, solve_static_slab_transfer
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


class CoupledSlabConvergenceError(RuntimeError):
    """辐射--布居 Picard 迭代未达到给定固定点容差。"""


@dataclass(frozen=True)
class GroundStateHHeSlabOpacity:
    """由显式基态布居构造的 H/He 板层体积消光系数。"""

    hydrogen_i_photoabsorption_per_cm: NDArray[np.float64]
    helium_i_photoabsorption_per_cm: NDArray[np.float64]
    helium_ii_photoabsorption_per_cm: NDArray[np.float64]
    photoabsorption_total_per_cm: NDArray[np.float64]
    electron_scattering_per_cm: NDArray[np.float64]
    extinction_total_per_cm: NDArray[np.float64]
    absorption_probability: NDArray[np.float64]


@dataclass(frozen=True)
class CoupledSlabPopulationState:
    """深度网格上的 H/He 基态布居与电子密度。"""

    hydrogen_neutral_fraction: NDArray[np.float64]
    hydrogen_ionized_fraction: NDArray[np.float64]
    helium_neutral_fraction: NDArray[np.float64]
    helium_singly_ionized_fraction: NDArray[np.float64]
    helium_doubly_ionized_fraction: NDArray[np.float64]
    electron_density_cm3: NDArray[np.float64]


@dataclass(frozen=True)
class CoupledRadiationPopulationSlab:
    """固定温度、固定密度板层的辐射--布居固定点。"""

    population: CoupledSlabPopulationState
    photoionization_rate_s1: NDArray[np.float64]
    opacity: GroundStateHHeSlabOpacity
    transfer: StaticSlabTransfer
    iteration_count: int
    iteration_residual_history: NDArray[np.float64]
    maximum_population_fixed_point_residual: float
    maximum_relative_charge_residual: float
    relaxation: float
    tolerance: float
    opacity_scale: float


def _validate_population_fractions(
    hydrogen_neutral_fraction: ArrayLike,
    hydrogen_ionized_fraction: ArrayLike,
    helium_neutral_fraction: ArrayLike,
    helium_singly_ionized_fraction: ArrayLike,
    helium_doubly_ionized_fraction: ArrayLike,
    depth_points: int,
) -> NDArray[np.float64]:
    values = np.column_stack(
        tuple(
            np.broadcast_to(np.asarray(value, dtype=np.float64), (depth_points,))
            for value in (
                hydrogen_neutral_fraction,
                hydrogen_ionized_fraction,
                helium_neutral_fraction,
                helium_singly_ionized_fraction,
                helium_doubly_ionized_fraction,
            )
        )
    )
    if not np.all(np.isfinite(values)) or np.any(values < 0.0) or np.any(values > 1.0):
        raise PhysicalDomainError("population fractions must be finite and lie in [0, 1]")
    tolerance = 64.0 * np.finfo(np.float64).eps
    if np.any(np.abs(np.sum(values[:, :2], axis=1) - 1.0) > tolerance):
        raise PhysicalDomainError("hydrogen fractions must sum to one")
    if np.any(np.abs(np.sum(values[:, 2:], axis=1) - 1.0) > tolerance):
        raise PhysicalDomainError("helium fractions must sum to one")
    return values


def _population_state(
    fractions: NDArray[np.float64],
    hydrogen_nuclei_cm3: float,
    helium_nuclei_cm3: float,
) -> CoupledSlabPopulationState:
    electron = (
        hydrogen_nuclei_cm3 * fractions[:, 1]
        + helium_nuclei_cm3 * (fractions[:, 3] + 2.0 * fractions[:, 4])
    )
    arrays = tuple(_readonly(np.array(fractions[:, index], copy=True)) for index in range(5))
    return CoupledSlabPopulationState(
        *arrays,
        electron_density_cm3=_readonly(np.array(electron, copy=True)),
    )


def ground_state_h_he_slab_opacity_per_cm(
    density_g_cm3: float,
    frequency_hz: ArrayLike,
    hydrogen_neutral_fraction: ArrayLike,
    hydrogen_ionized_fraction: ArrayLike,
    helium_neutral_fraction: ArrayLike,
    helium_singly_ionized_fraction: ArrayLike,
    helium_doubly_ionized_fraction: ArrayLike,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
    include_electron_scattering: bool = True,
    opacity_scale: float = 1.0,
) -> GroundStateHHeSlabOpacity:
    """由非 LTE 基态分数构造光致吸收和 Thomson 散射体积系数。

    这里的束缚--自由项是靶粒子数密度乘基态光致电离截面；尚未加入由
    激发态与复合连续发射决定的非 LTE 修正。
    """
    density = float(density_g_cm3)
    scale = float(opacity_scale)
    if not np.isfinite(density) or density <= 0.0:
        raise PhysicalDomainError("density_g_cm3 must be finite and strictly positive")
    if not np.isfinite(scale) or scale < 0.0:
        raise PhysicalDomainError("opacity_scale must be finite and non-negative")
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    if (
        frequency.ndim != 1
        or frequency.size < 2
        or not np.all(np.isfinite(frequency))
        or np.any(frequency <= 0.0)
        or np.any(np.diff(frequency) <= 0.0)
    ):
        raise PhysicalDomainError(
            "frequency_hz must be a finite, positive and strictly increasing 1D grid"
        )
    energy_ev = PLANCK_ERG_S * frequency / EV_ERG
    maximum_energy = min(
        fit.maximum_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
    )
    if energy_ev[-1] > maximum_energy:
        raise PhysicalDomainError("frequency grid exceeds the common Verner fit domain")

    candidates = (
        hydrogen_neutral_fraction,
        hydrogen_ionized_fraction,
        helium_neutral_fraction,
        helium_singly_ionized_fraction,
        helium_doubly_ionized_fraction,
    )
    depth_points = max(np.asarray(value).size for value in candidates)
    fractions = _validate_population_fractions(*candidates, depth_points)
    hydrogen_nuclei = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium_nuclei = composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    cross_sections = []
    for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS:
        fit_energy = np.array(energy_ev, copy=True)
        threshold_hz = fit.threshold_energy_ev * EV_ERG / PLANCK_ERG_S
        # 中文：频率乘除回算可能跨过阈值一个舍入单位，精确边节点恢复为表值。
        fit_energy[frequency == threshold_hz] = fit.threshold_energy_ev
        cross_sections.append(fit.cross_section_cm2(fit_energy))
    hydrogen_i = (
        scale * hydrogen_nuclei * fractions[:, 0][None, :] * cross_sections[0][:, None]
    )
    helium_i = (
        scale * helium_nuclei * fractions[:, 2][None, :] * cross_sections[1][:, None]
    )
    helium_ii = (
        scale * helium_nuclei * fractions[:, 3][None, :] * cross_sections[2][:, None]
    )
    photoabsorption = hydrogen_i + helium_i + helium_ii
    electron = (
        hydrogen_nuclei * fractions[:, 1]
        + helium_nuclei * (fractions[:, 3] + 2.0 * fractions[:, 4])
    )
    if include_electron_scattering:
        scattering_depth = scale * THOMSON_CROSS_SECTION_CM2 * electron
    else:
        scattering_depth = np.zeros(depth_points, dtype=np.float64)
    scattering = np.broadcast_to(scattering_depth[None, :], photoabsorption.shape).copy()
    extinction = photoabsorption + scattering
    # 中文：真空单元中源函数不影响形式解；显式取 epsilon=1，避免无定义的 0/0。
    epsilon = np.ones_like(extinction)
    np.divide(photoabsorption, extinction, out=epsilon, where=extinction > 0.0)
    output = (
        hydrogen_i,
        helium_i,
        helium_ii,
        photoabsorption,
        scattering,
        extinction,
        epsilon,
    )
    if not all(np.all(np.isfinite(array)) and np.all(array >= 0.0) for array in output):
        raise ArithmeticError("ground-state H/He slab opacity became invalid")
    if np.any(epsilon > 1.0):
        raise ArithmeticError("absorption probability exceeded unity")
    return GroundStateHHeSlabOpacity(
        *(_readonly(np.array(array, copy=True)) for array in output)
    )


def photoionization_rates_from_mean_intensity_s1(
    frequency_hz: ArrayLike,
    mean_intensity_cgs: ArrayLike,
) -> NDArray[np.float64]:
    """把深度相关 ``J_nu`` 积分为 H I、He I、He II 光致电离率。"""
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    mean = np.asarray(mean_intensity_cgs, dtype=np.float64)
    if frequency.ndim != 1 or mean.ndim != 2 or mean.shape[0] != frequency.size:
        raise PhysicalDomainError(
            "mean_intensity_cgs must have shape (frequency, depth)"
        )
    if not np.all(np.isfinite(mean)) or np.any(mean < 0.0):
        raise PhysicalDomainError("mean_intensity_cgs must be finite and non-negative")
    rates = np.empty((mean.shape[1], 3), dtype=np.float64)
    for depth in range(mean.shape[1]):
        for species, fit in enumerate(H_HE_GROUND_STATE_PHOTOIONIZATION_FITS):
            rates[depth, species] = photoionization_rate_from_fit_s1(
                frequency, mean[:, depth], fit
            )
    if not np.all(np.isfinite(rates)) or np.any(rates < 0.0):
        raise ArithmeticError("depth-dependent photoionization rates became invalid")
    return _readonly(rates)


def solve_coupled_radiation_population_slab(
    frequency_hz: ArrayLike,
    depth_edges_cm: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    density_g_cm3: float,
    thermal_source_intensity: ArrayLike,
    top_incoming_intensity: ArrayLike,
    bottom_incoming_intensity: ArrayLike,
    initial_hydrogen_fraction: ArrayLike,
    initial_helium_fraction: ArrayLike,
    collisional_ionization_cm3_s: ArrayLike,
    radiative_recombination_cm3_s: ArrayLike,
    three_body_recombination_cm6_s: ArrayLike,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
    include_electron_scattering: bool = True,
    opacity_scale: float = 1.0,
    relaxation: float = 1.0,
    tolerance: float = 1.0e-10,
    maximum_iterations: int = 256,
) -> CoupledRadiationPopulationSlab:
    """求固定温度率系数下的 ``J_nu``--基态布居--opacity 固定点。"""
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    edges = np.array(depth_edges_cm, dtype=np.float64, copy=True)
    if edges.ndim != 1 or edges.size < 2:
        raise PhysicalDomainError("depth_edges_cm must contain at least one cell")
    depth_points = edges.size - 1
    initial_hydrogen = np.asarray(initial_hydrogen_fraction, dtype=np.float64)
    initial_helium = np.asarray(initial_helium_fraction, dtype=np.float64)
    if initial_hydrogen.shape == (2,):
        initial_hydrogen = np.broadcast_to(initial_hydrogen, (depth_points, 2))
    if initial_helium.shape == (3,):
        initial_helium = np.broadcast_to(initial_helium, (depth_points, 3))
    if initial_hydrogen.shape != (depth_points, 2):
        raise PhysicalDomainError(
            "initial_hydrogen_fraction must have shape (2,) or (depth, 2)"
        )
    if initial_helium.shape != (depth_points, 3):
        raise PhysicalDomainError(
            "initial_helium_fraction must have shape (3,) or (depth, 3)"
        )
    fractions = _validate_population_fractions(
        initial_hydrogen[:, 0],
        initial_hydrogen[:, 1],
        initial_helium[:, 0],
        initial_helium[:, 1],
        initial_helium[:, 2],
        depth_points,
    )
    rates = tuple(
        np.broadcast_to(np.asarray(value, dtype=np.float64), (depth_points, 3)).copy()
        for value in (
            collisional_ionization_cm3_s,
            radiative_recombination_cm3_s,
            three_body_recombination_cm6_s,
        )
    )
    if any(not np.all(np.isfinite(value)) or np.any(value < 0.0) for value in rates):
        raise PhysicalDomainError("atomic rate coefficients must be finite and non-negative")
    relax = float(relaxation)
    threshold = float(tolerance)
    if not np.isfinite(relax) or relax <= 0.0 or relax > 1.0:
        raise PhysicalDomainError("relaxation must lie in (0, 1]")
    if not np.isfinite(threshold) or threshold <= 0.0:
        raise PhysicalDomainError("tolerance must be finite and strictly positive")
    if (
        not isinstance(maximum_iterations, (int, np.integer))
        or int(maximum_iterations) < 1
    ):
        raise PhysicalDomainError("maximum_iterations must be a positive integer")

    density = float(density_g_cm3)
    if not np.isfinite(density) or density <= 0.0:
        raise PhysicalDomainError("density_g_cm3 must be finite and strictly positive")
    hydrogen_nuclei = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium_nuclei = composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    residual_history: list[float] = []

    def fixed_point_map(current: NDArray[np.float64]):
        opacity = ground_state_h_he_slab_opacity_per_cm(
            density,
            frequency,
            current[:, 0],
            current[:, 1],
            current[:, 2],
            current[:, 3],
            current[:, 4],
            composition=composition,
            include_electron_scattering=include_electron_scattering,
            opacity_scale=opacity_scale,
        )
        transfer = solve_static_slab_transfer(
            frequency,
            edges,
            direction_cosine,
            angular_weight,
            opacity.extinction_total_per_cm,
            thermal_source_intensity,
            opacity.absorption_probability,
            top_incoming_intensity=top_incoming_intensity,
            bottom_incoming_intensity=bottom_incoming_intensity,
        )
        photoionization = photoionization_rates_from_mean_intensity_s1(
            frequency, transfer.mean_intensity
        )
        equilibrium = collisional_photoionization_equilibrium(
            hydrogen_nuclei,
            helium_nuclei,
            photoionization[:, 0],
            photoionization[:, 1],
            photoionization[:, 2],
            rates[0][:, 0],
            rates[0][:, 1],
            rates[0][:, 2],
            rates[1][:, 0],
            rates[1][:, 1],
            rates[1][:, 2],
            rates[2][:, 0],
            rates[2][:, 1],
            rates[2][:, 2],
        )
        target = np.column_stack(
            (
                equilibrium.hydrogen_neutral_fraction,
                equilibrium.hydrogen_ionized_fraction,
                equilibrium.helium_neutral_fraction,
                equilibrium.helium_singly_ionized_fraction,
                equilibrium.helium_doubly_ionized_fraction,
            )
        )
        return target, opacity, transfer, photoionization, equilibrium

    for iteration in range(1, int(maximum_iterations) + 1):
        target, _, _, _, _ = fixed_point_map(fractions)
        residual = float(np.max(np.abs(target - fractions)))
        residual_history.append(residual)
        if residual <= threshold:
            fractions = target
            break
        # 中文：欠松弛只是固定点数值控制；凸组合保持粒子数，不事后重归一化。
        fractions = (1.0 - relax) * fractions + relax * target
    else:
        raise CoupledSlabConvergenceError(
            f"radiation-population iteration did not reach {threshold:.3e} in "
            f"{int(maximum_iterations)} iterations; final residual={residual_history[-1]:.3e}"
        )

    final_target, opacity, transfer, photoionization, equilibrium = fixed_point_map(fractions)
    fixed_point_residual = float(np.max(np.abs(final_target - fractions)))
    return CoupledRadiationPopulationSlab(
        population=_population_state(fractions, hydrogen_nuclei, helium_nuclei),
        photoionization_rate_s1=_readonly(np.array(photoionization, copy=True)),
        opacity=opacity,
        transfer=transfer,
        iteration_count=iteration,
        iteration_residual_history=_readonly(np.asarray(residual_history, dtype=np.float64)),
        maximum_population_fixed_point_residual=fixed_point_residual,
        maximum_relative_charge_residual=equilibrium.maximum_relative_charge_residual,
        relaxation=relax,
        tolerance=threshold,
        opacity_scale=float(opacity_scale),
    )
