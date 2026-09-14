"""规定温度剖面板层的基态 Milne 连续发射与能量控制。

本模块用同一组 H I、He I、He II 基态光致截面构造光致电离、自然/受激
复合、净束缚--自由消光和连续发射，并加入满足 Kirchhoff 关系的自由--自由
连续过程。它接受标量或逐深度密度与温度；碰撞电离/三体复合是显式可选的
受控闭合。本模块不自行求温度演化，仍不能替代完整 NLTE 大气。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .atomic_continuum import (
    EV_ERG,
    H_HE_GROUND_STATE_PHOTOIONIZATION_FITS,
    ground_state_saha_factor_cm3,
)
from .atomic_kinetics import (
    H_HE_COLLISIONAL_IONIZATION_FITS,
    collisional_photoionization_equilibrium,
    detailed_balance_three_body_recombination_coefficient_cm6_s,
)
from .atmosphere import (
    FREE_FREE_COEFFICIENT_CGS,
    PROTON_MASS_G,
    SOLAR_FULLY_IONIZED_H_HE,
    THOMSON_CROSS_SECTION_CM2,
    FullyIonizedHydrogenHeliumComposition,
)
from .non_gray import (
    HELIUM_II_IONIZATION_ERG,
    HELIUM_I_IONIZATION_ERG,
    HYDROGEN_IONIZATION_ERG,
)
from .radiation import (
    BOLTZMANN_ERG_K,
    LIGHT_SPEED_CM_S,
    PLANCK_ERG_S,
    planck_nu,
)
from .radiation_population_coupling import CoupledSlabPopulationState
from .radiative_transfer_1d import StaticSlabTransfer, solve_static_slab_transfer
from .frequency_quadrature import (
    integrate_frequency,
    validate_frequency_weights_hz,
)
from .source import PhysicalDomainError


IONIZATION_ENERGIES_EV = (
    HYDROGEN_IONIZATION_ERG / EV_ERG,
    HELIUM_I_IONIZATION_ERG / EV_ERG,
    HELIUM_II_IONIZATION_ERG / EV_ERG,
)


def edge_resolved_milne_energy_grid_ev(
    minimum_energy_ev: float,
    maximum_energy_ev: float,
    base_points: int,
) -> NDArray[np.float64]:
    """构造同时解析基态光致截面左右极限的对数能量网格。"""
    minimum = float(minimum_energy_ev)
    maximum = float(maximum_energy_ev)
    if (
        not np.isfinite(minimum)
        or not np.isfinite(maximum)
        or minimum <= 0.0
        or maximum <= minimum
    ):
        raise PhysicalDomainError(
            "Milne energy bounds must be finite, positive and ordered"
        )
    if not isinstance(base_points, (int, np.integer)) or isinstance(
        base_points, (bool, np.bool_)
    ):
        raise PhysicalDomainError("base_points must be an integer of at least two")
    if int(base_points) < 2:
        raise PhysicalDomainError("base_points must be an integer of at least two")
    maximum_fit_energy = min(
        fit.maximum_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
    )
    if maximum > maximum_fit_energy:
        raise PhysicalDomainError("Milne energy grid exceeds the common Verner fit domain")
    base = np.geomspace(minimum, maximum, int(base_points))
    thresholds = np.array(
        [fit.threshold_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS],
        dtype=np.float64,
    )
    active = thresholds[(thresholds >= minimum) & (thresholds <= maximum)]
    # 中文：向左移动到频率换算后仍可区分的最近浮点点，避免两节点数值合并。
    left_limits = np.array(active, copy=True)
    for index, threshold in enumerate(active):
        threshold_frequency = threshold * EV_ERG / PLANCK_ERG_S
        while left_limits[index] * EV_ERG / PLANCK_ERG_S >= threshold_frequency:
            left_limits[index] = np.nextafter(left_limits[index], -np.inf)
    left_limits = left_limits[left_limits >= minimum]
    return _readonly(np.unique(np.concatenate((base, left_limits, active))))


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


class ContinuumPopulationInversionError(PhysicalDomainError):
    """基态 Milne 净消光为负，当前非 maser 转移核不适用。"""


class EmissiveSlabConvergenceError(RuntimeError):
    """连续发射--布居固定点未达到指定容差。"""


@dataclass(frozen=True)
class GroundStateMilneContinuum:
    """基态束缚--自由、自由--自由与 Thomson 连续系数。"""

    hydrogen_i_bound_free_absorption_per_cm: NDArray[np.float64]
    helium_i_bound_free_absorption_per_cm: NDArray[np.float64]
    helium_ii_bound_free_absorption_per_cm: NDArray[np.float64]
    bound_free_absorption_total_per_cm: NDArray[np.float64]
    hydrogen_i_bound_free_emissivity_cgs: NDArray[np.float64]
    helium_i_bound_free_emissivity_cgs: NDArray[np.float64]
    helium_ii_bound_free_emissivity_cgs: NDArray[np.float64]
    bound_free_emissivity_total_cgs: NDArray[np.float64]
    free_free_absorption_per_cm: NDArray[np.float64]
    free_free_emissivity_cgs: NDArray[np.float64]
    true_absorption_total_per_cm: NDArray[np.float64]
    thermal_emissivity_total_cgs: NDArray[np.float64]
    electron_scattering_per_cm: NDArray[np.float64]
    extinction_total_per_cm: NDArray[np.float64]
    absorption_probability: NDArray[np.float64]
    thermal_source_intensity: NDArray[np.float64]
    electron_density_cm3: NDArray[np.float64]


@dataclass(frozen=True)
class GroundStateMilneRadiativeRates:
    """与同一基态连续截面配对的辐射跃迁率。"""

    photoionization_s1: NDArray[np.float64]
    spontaneous_recombination_cm3_s: NDArray[np.float64]
    stimulated_recombination_cm3_s: NDArray[np.float64]
    total_recombination_cm3_s: NDArray[np.float64]


@dataclass(frozen=True)
class EmissiveCoupledSlab:
    """规定温度剖面的基态 Milne 连续发射--布居固定点。"""

    temperature_k: NDArray[np.float64]
    population: CoupledSlabPopulationState
    continuum: GroundStateMilneContinuum
    radiative_rates: GroundStateMilneRadiativeRates
    transfer: StaticSlabTransfer
    radiative_heating_erg_s_cm3: NDArray[np.float64]
    required_thermostat_heating_erg_s_cm3: NDArray[np.float64]
    boundary_energy_balance_residual_erg_s_cm2: float
    relative_boundary_energy_balance_residual: float
    maximum_photon_rate_identity_residual_cm3_s1: float
    maximum_relative_photon_rate_identity_residual: float
    maximum_population_fixed_point_residual: float
    maximum_relative_charge_residual: float
    iteration_count: int
    iteration_residual_history: NDArray[np.float64]
    relaxation: float
    tolerance: float
    includes_collisional_kinetics: bool


def _validate_frequency(frequency_hz: ArrayLike) -> NDArray[np.float64]:
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
    maximum_energy = min(
        fit.maximum_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
    )
    if PLANCK_ERG_S * frequency[-1] / EV_ERG > maximum_energy:
        raise PhysicalDomainError("frequency grid exceeds the common Verner fit domain")
    return frequency


def _validate_population(
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


def _cross_sections_cm2(frequency: NDArray[np.float64]) -> NDArray[np.float64]:
    energy = PLANCK_ERG_S * frequency / EV_ERG
    cross_sections = np.empty((frequency.size, 3), dtype=np.float64)
    for species, fit in enumerate(H_HE_GROUND_STATE_PHOTOIONIZATION_FITS):
        fit_energy = np.array(energy, copy=True)
        threshold_hz = fit.threshold_energy_ev * EV_ERG / PLANCK_ERG_S
        # 中文：精确离化边在频率往返换算后恢复为拟合表阈值。
        fit_energy[frequency == threshold_hz] = fit.threshold_energy_ev
        cross_sections[:, species] = fit.cross_section_cm2(fit_energy)
    return cross_sections


def _temperature_profile_k(
    temperature_k: ArrayLike, depth_points: int
) -> NDArray[np.float64]:
    """把标量或逐深度温度整理为只读一维剖面。"""
    temperature = np.asarray(temperature_k, dtype=np.float64)
    try:
        profile = np.array(
            np.broadcast_to(temperature, (depth_points,)), dtype=np.float64, copy=True
        )
    except ValueError as error:
        raise PhysicalDomainError(
            "temperature_k must be scalar or have one value per depth cell"
        ) from error
    if not np.all(np.isfinite(profile)) or np.any(profile <= 0.0):
        raise PhysicalDomainError(
            "temperature_k must contain finite, strictly positive values"
        )
    return _readonly(profile)


def _saha_factors_cm3(temperature_k: ArrayLike) -> NDArray[np.float64]:
    return np.stack(
        tuple(
            ground_state_saha_factor_cm3(temperature_k, energy_ev)
            for energy_ev in IONIZATION_ENERGIES_EV
        ),
        axis=-1,
    )


def _density_profile_g_cm3(
    density_g_cm3: ArrayLike, depth_points: int
) -> NDArray[np.float64]:
    """把标量或逐深度质量密度整理为只读剖面。"""
    density = np.asarray(density_g_cm3, dtype=np.float64)
    try:
        profile = np.array(
            np.broadcast_to(density, (depth_points,)), dtype=np.float64, copy=True
        )
    except ValueError as error:
        raise PhysicalDomainError(
            "density_g_cm3 must be scalar or have one value per depth cell"
        ) from error
    if not np.all(np.isfinite(profile)) or np.any(profile <= 0.0):
        raise PhysicalDomainError(
            "density_g_cm3 must contain finite, strictly positive values"
        )
    return _readonly(profile)


def ground_state_milne_continuum(
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    frequency_hz: ArrayLike,
    hydrogen_neutral_fraction: ArrayLike,
    hydrogen_ionized_fraction: ArrayLike,
    helium_neutral_fraction: ArrayLike,
    helium_singly_ionized_fraction: ArrayLike,
    helium_doubly_ionized_fraction: ArrayLike,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
    include_electron_scattering: bool = True,
) -> GroundStateMilneContinuum:
    """构造与基态 Milne 关系一致的净消光和自发连续发射。"""
    frequency = _validate_frequency(frequency_hz)
    candidates = (
        hydrogen_neutral_fraction,
        hydrogen_ionized_fraction,
        helium_neutral_fraction,
        helium_singly_ionized_fraction,
        helium_doubly_ionized_fraction,
    )
    depth_points = max(
        np.asarray(density_g_cm3).size,
        *(np.asarray(value).size for value in candidates),
    )
    density = _density_profile_g_cm3(density_g_cm3, depth_points)
    fractions = _validate_population(*candidates, depth_points)
    temperature = _temperature_profile_k(temperature_k, depth_points)
    hydrogen_nuclei = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium_nuclei = composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    electron = (
        hydrogen_nuclei * fractions[:, 1]
        + helium_nuclei * (fractions[:, 3] + 2.0 * fractions[:, 4])
    )
    lower_density = np.column_stack(
        (
            hydrogen_nuclei * fractions[:, 0],
            helium_nuclei * fractions[:, 2],
            helium_nuclei * fractions[:, 3],
        )
    )
    upper_density = np.column_stack(
        (
            hydrogen_nuclei * fractions[:, 1],
            helium_nuclei * fractions[:, 3],
            helium_nuclei * fractions[:, 4],
        )
    )
    saha = _saha_factors_cm3(temperature)
    cross_section = _cross_sections_cm2(frequency)
    exponent = (
        PLANCK_ERG_S
        * frequency[:, None]
        / (BOLTZMANN_ERG_K * temperature[None, :])
    )
    boltzmann = np.exp(-exponent)
    continuum_upper_equivalent = upper_density * electron[:, None] / saha
    net_lower = (
        lower_density[None, :, :]
        - continuum_upper_equivalent[None, :, :] * boltzmann[:, :, None]
    )
    bound_free_absorption = cross_section[:, None, :] * net_lower
    if np.any(bound_free_absorption < 0.0):
        minimum = float(np.min(bound_free_absorption))
        raise ContinuumPopulationInversionError(
            f"ground-state bound-free net extinction became negative: {minimum:.6e} cm^-1"
        )
    vacuum_intensity = 2.0 * PLANCK_ERG_S * frequency**3 / LIGHT_SPEED_CM_S**2
    bound_free_emissivity = (
        cross_section[:, None, :]
        * continuum_upper_equivalent[None, :, :]
        * vacuum_intensity[:, None, None]
        * boltzmann[:, :, None]
    )
    bound_free_total = np.sum(bound_free_absorption, axis=2)
    bound_free_emissivity_total = np.sum(bound_free_emissivity, axis=2)

    charge_squared_ions = hydrogen_nuclei * fractions[:, 1] + helium_nuclei * (
        fractions[:, 3] + 4.0 * fractions[:, 4]
    )
    stimulated = -np.expm1(-exponent)
    free_free_absorption = (
        FREE_FREE_COEFFICIENT_CGS
        * composition.free_free_gaunt_factor
        * temperature[None, :] ** (-0.5)
        * electron[None, :]
        * charge_squared_ions[None, :]
        * frequency[:, None] ** (-3.0)
        * stimulated
    )
    planck = planck_nu(frequency[:, None], temperature[None, :])
    free_free_emissivity = free_free_absorption * planck
    true_absorption = bound_free_total + free_free_absorption
    thermal_emissivity = bound_free_emissivity_total + free_free_emissivity
    scattering_depth = (
        THOMSON_CROSS_SECTION_CM2 * electron
        if include_electron_scattering
        else np.zeros(depth_points, dtype=np.float64)
    )
    scattering = np.broadcast_to(scattering_depth[None, :], true_absorption.shape).copy()
    extinction = true_absorption + scattering
    epsilon = np.ones_like(extinction)
    np.divide(true_absorption, extinction, out=epsilon, where=extinction > 0.0)
    thermal_source = np.zeros_like(true_absorption)
    np.divide(
        thermal_emissivity,
        true_absorption,
        out=thermal_source,
        where=true_absorption > 0.0,
    )
    if np.any((true_absorption == 0.0) & (thermal_emissivity != 0.0)):
        raise ArithmeticError("continuum emissivity is non-zero where true absorption vanishes")

    components = tuple(bound_free_absorption[:, :, index] for index in range(3))
    emissivities = tuple(bound_free_emissivity[:, :, index] for index in range(3))
    output = (
        *components,
        bound_free_total,
        *emissivities,
        bound_free_emissivity_total,
        free_free_absorption,
        free_free_emissivity,
        true_absorption,
        thermal_emissivity,
        scattering,
        extinction,
        epsilon,
        thermal_source,
        electron,
    )
    if not all(np.all(np.isfinite(array)) for array in output):
        raise ArithmeticError("ground-state Milne continuum became non-finite")
    if any(np.any(array < 0.0) for array in output):
        raise ArithmeticError("ground-state Milne continuum became negative")
    if np.any(epsilon > 1.0):
        raise ArithmeticError("continuum absorption probability exceeded unity")
    return GroundStateMilneContinuum(
        *(_readonly(np.array(array, copy=True)) for array in output)
    )


def ground_state_milne_radiative_rates(
    temperature_k: ArrayLike,
    frequency_hz: ArrayLike,
    mean_intensity_cgs: ArrayLike,
    *,
    frequency_weight_hz: ArrayLike | None = None,
) -> GroundStateMilneRadiativeRates:
    """计算同一基态截面的光致电离与自然/受激复合率。"""
    frequency = _validate_frequency(frequency_hz)
    _, quadrature_weight = validate_frequency_weights_hz(
        frequency, frequency_weight_hz
    )
    mean = np.asarray(mean_intensity_cgs, dtype=np.float64)
    if mean.ndim != 2 or mean.shape[0] != frequency.size:
        raise PhysicalDomainError("mean_intensity_cgs must have shape (frequency, depth)")
    if not np.all(np.isfinite(mean)) or np.any(mean < 0.0):
        raise PhysicalDomainError("mean_intensity_cgs must be finite and non-negative")
    temperature = _temperature_profile_k(temperature_k, mean.shape[1])
    cross_section = _cross_sections_cm2(frequency)
    saha = _saha_factors_cm3(temperature)
    exponent = (
        PLANCK_ERG_S
        * frequency[:, None]
        / (BOLTZMANN_ERG_K * temperature[None, :])
    )
    boltzmann = np.exp(-exponent)
    photon_weight = 4.0 * np.pi / (PLANCK_ERG_S * frequency)
    photoionization = np.empty((mean.shape[1], 3), dtype=np.float64)
    stimulated = np.empty_like(photoionization)
    spontaneous = np.empty_like(photoionization)
    for species in range(3):
        sigma = cross_section[:, species]
        photoionization[:, species] = integrate_frequency(
            photon_weight[:, None] * sigma[:, None] * mean,
            quadrature_weight,
            axis=0,
        )
        spontaneous[:, species] = integrate_frequency(
            8.0
            * np.pi
            * frequency[:, None] ** 2
            / LIGHT_SPEED_CM_S**2
            * sigma[:, None]
            * boltzmann
            / saha[None, :, species],
            quadrature_weight,
            axis=0,
        )
        stimulated[:, species] = integrate_frequency(
            photon_weight[:, None]
            * sigma[:, None]
            * boltzmann
            * mean
            / saha[None, :, species],
            quadrature_weight,
            axis=0,
        )
    total = spontaneous + stimulated
    output = (photoionization, spontaneous, stimulated, total)
    if not all(np.all(np.isfinite(array)) and np.all(array >= 0.0) for array in output):
        raise ArithmeticError("ground-state Milne radiative rates became invalid")
    return GroundStateMilneRadiativeRates(
        *(_readonly(np.array(array, copy=True)) for array in output)
    )


def _population_state(
    fractions: NDArray[np.float64],
    hydrogen_nuclei_cm3: ArrayLike,
    helium_nuclei_cm3: ArrayLike,
) -> CoupledSlabPopulationState:
    electron = (
        hydrogen_nuclei_cm3 * fractions[:, 1]
        + helium_nuclei_cm3 * (fractions[:, 3] + 2.0 * fractions[:, 4])
    )
    return CoupledSlabPopulationState(
        *(
            _readonly(np.array(fractions[:, index], copy=True))
            for index in range(5)
        ),
        electron_density_cm3=_readonly(np.array(electron, copy=True)),
    )


def _photon_rate_identity_residual(
    frequency: NDArray[np.float64],
    mean: NDArray[np.float64],
    continuum: GroundStateMilneContinuum,
    rates: GroundStateMilneRadiativeRates,
    fractions: NDArray[np.float64],
    hydrogen_nuclei_cm3: ArrayLike,
    helium_nuclei_cm3: ArrayLike,
) -> tuple[float, float]:
    lower = np.column_stack(
        (
            hydrogen_nuclei_cm3 * fractions[:, 0],
            helium_nuclei_cm3 * fractions[:, 2],
            helium_nuclei_cm3 * fractions[:, 3],
        )
    )
    upper = np.column_stack(
        (
            hydrogen_nuclei_cm3 * fractions[:, 1],
            helium_nuclei_cm3 * fractions[:, 3],
            helium_nuclei_cm3 * fractions[:, 4],
        )
    )
    electron = continuum.electron_density_cm3
    absorptions = (
        continuum.hydrogen_i_bound_free_absorption_per_cm,
        continuum.helium_i_bound_free_absorption_per_cm,
        continuum.helium_ii_bound_free_absorption_per_cm,
    )
    emissivities = (
        continuum.hydrogen_i_bound_free_emissivity_cgs,
        continuum.helium_i_bound_free_emissivity_cgs,
        continuum.helium_ii_bound_free_emissivity_cgs,
    )
    photon_weight = 4.0 * np.pi / (PLANCK_ERG_S * frequency)
    maximum = 0.0
    maximum_relative = 0.0
    for species, (absorption, emissivity) in enumerate(
        zip(absorptions, emissivities, strict=True)
    ):
        transfer_exchange = np.trapezoid(
            photon_weight[:, None] * (absorption * mean - emissivity),
            frequency,
            axis=0,
        )
        rate_exchange = (
            lower[:, species] * rates.photoionization_s1[:, species]
            - upper[:, species]
            * electron
            * rates.total_recombination_cm3_s[:, species]
        )
        absolute = np.abs(transfer_exchange - rate_exchange)
        scale = np.maximum(
            lower[:, species] * rates.photoionization_s1[:, species],
            upper[:, species]
            * electron
            * rates.total_recombination_cm3_s[:, species],
        )
        relative = np.array(absolute, copy=True)
        np.divide(absolute, scale, out=relative, where=scale > 0.0)
        maximum = max(maximum, float(np.max(absolute)))
        maximum_relative = max(maximum_relative, float(np.max(relative)))
    return maximum, maximum_relative


def solve_emissive_ground_state_slab(
    frequency_hz: ArrayLike,
    depth_edges_cm: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    top_incoming_intensity: ArrayLike,
    bottom_incoming_intensity: ArrayLike,
    initial_hydrogen_fraction: ArrayLike,
    initial_helium_fraction: ArrayLike,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
    include_electron_scattering: bool = True,
    include_collisional_kinetics: bool = False,
    initialize_collisional_population_from_lte: bool = False,
    relaxation: float = 0.5,
    tolerance: float = 1.0e-10,
    maximum_iterations: int = 512,
) -> EmissiveCoupledSlab:
    """求规定温度剖面下纯辐射基态 Milne 网络与连续转移固定点。"""
    frequency = _validate_frequency(frequency_hz)
    edges = np.array(depth_edges_cm, dtype=np.float64, copy=True)
    if (
        edges.ndim != 1
        or edges.size < 2
        or not np.all(np.isfinite(edges))
        or np.any(np.diff(edges) <= 0.0)
    ):
        raise PhysicalDomainError("depth_edges_cm must be finite and strictly increasing")
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
    fractions = _validate_population(
        initial_hydrogen[:, 0],
        initial_hydrogen[:, 1],
        initial_helium[:, 0],
        initial_helium[:, 1],
        initial_helium[:, 2],
        depth_points,
    )
    density = _density_profile_g_cm3(density_g_cm3, depth_points)
    temperature = _temperature_profile_k(temperature_k, depth_points)
    relax = float(relaxation)
    threshold = float(tolerance)
    if not np.isfinite(relax) or relax <= 0.0 or relax > 1.0:
        raise PhysicalDomainError("relaxation must lie in (0, 1]")
    if not np.isfinite(threshold) or threshold <= 0.0:
        raise PhysicalDomainError("tolerance must be finite and strictly positive")
    if not isinstance(maximum_iterations, (int, np.integer)) or maximum_iterations < 1:
        raise PhysicalDomainError("maximum_iterations must be a positive integer")
    hydrogen_nuclei = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium_nuclei = composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    zeros = np.zeros((depth_points, 3), dtype=np.float64)
    for name, value in (
        ("include_collisional_kinetics", include_collisional_kinetics),
        (
            "initialize_collisional_population_from_lte",
            initialize_collisional_population_from_lte,
        ),
    ):
        if not isinstance(value, (bool, np.bool_)):
            raise PhysicalDomainError(f"{name} must be boolean")
    if initialize_collisional_population_from_lte and not include_collisional_kinetics:
        raise PhysicalDomainError(
            "LTE collisional initialization requires collisional kinetics"
        )
    if include_collisional_kinetics:
        collision = np.column_stack(
            tuple(
                fit.coefficient_cm3_s(temperature)
                for fit in H_HE_COLLISIONAL_IONIZATION_FITS
            )
        )
        saha = _saha_factors_cm3(temperature)
        three_body = detailed_balance_three_body_recombination_coefficient_cm6_s(
            collision, saha
        )
    else:
        collision = zeros
        three_body = zeros
    if initialize_collisional_population_from_lte:
        # 中文：用同一 C(T)/S(T) 详细平衡网络构造初值；这不是强制 LTE 终解。
        collisional_lte = collisional_photoionization_equilibrium(
            hydrogen_nuclei,
            helium_nuclei,
            zeros[:, 0],
            zeros[:, 1],
            zeros[:, 2],
            collision[:, 0],
            collision[:, 1],
            collision[:, 2],
            zeros[:, 0],
            zeros[:, 1],
            zeros[:, 2],
            three_body[:, 0],
            three_body[:, 1],
            three_body[:, 2],
        )
        fractions = np.column_stack(
            (
                collisional_lte.hydrogen_neutral_fraction,
                collisional_lte.hydrogen_ionized_fraction,
                collisional_lte.helium_neutral_fraction,
                collisional_lte.helium_singly_ionized_fraction,
                collisional_lte.helium_doubly_ionized_fraction,
            )
        )
    residual_history: list[float] = []

    def fixed_point_map(current: NDArray[np.float64]):
        continuum = ground_state_milne_continuum(
            density,
            temperature,
            frequency,
            current[:, 0],
            current[:, 1],
            current[:, 2],
            current[:, 3],
            current[:, 4],
            composition=composition,
            include_electron_scattering=include_electron_scattering,
        )
        transfer = solve_static_slab_transfer(
            frequency,
            edges,
            direction_cosine,
            angular_weight,
            continuum.extinction_total_per_cm,
            continuum.thermal_source_intensity,
            continuum.absorption_probability,
            top_incoming_intensity=top_incoming_intensity,
            bottom_incoming_intensity=bottom_incoming_intensity,
        )
        rates = ground_state_milne_radiative_rates(
            temperature, frequency, transfer.mean_intensity
        )
        equilibrium = collisional_photoionization_equilibrium(
            hydrogen_nuclei,
            helium_nuclei,
            rates.photoionization_s1[:, 0],
            rates.photoionization_s1[:, 1],
            rates.photoionization_s1[:, 2],
            collision[:, 0],
            collision[:, 1],
            collision[:, 2],
            rates.total_recombination_cm3_s[:, 0],
            rates.total_recombination_cm3_s[:, 1],
            rates.total_recombination_cm3_s[:, 2],
            three_body[:, 0],
            three_body[:, 1],
            three_body[:, 2],
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
        return target, continuum, transfer, rates, equilibrium

    for iteration in range(1, int(maximum_iterations) + 1):
        target, _, _, _, _ = fixed_point_map(fractions)
        residual = float(np.max(np.abs(target - fractions)))
        residual_history.append(residual)
        if residual <= threshold:
            fractions = target
            break
        # 中文：凸组合只控制 Picard 收敛；不裁剪、不加 floor、不事后归一化。
        fractions = (1.0 - relax) * fractions + relax * target
    else:
        raise EmissiveSlabConvergenceError(
            f"emissive slab iteration did not reach {threshold:.3e} in "
            f"{int(maximum_iterations)} iterations; final residual={residual_history[-1]:.3e}"
        )

    final_target, continuum, transfer, rates, equilibrium = fixed_point_map(fractions)
    fixed_point_residual = float(np.max(np.abs(final_target - fractions)))
    absorption_heating = 4.0 * np.pi * np.trapezoid(
        continuum.true_absorption_total_per_cm * transfer.mean_intensity
        - continuum.thermal_emissivity_total_cgs,
        frequency,
        axis=0,
    )
    widths = np.diff(edges)
    top_flux = float(np.trapezoid(transfer.top_net_flux, frequency))
    bottom_flux = float(np.trapezoid(transfer.bottom_net_flux, frequency))
    integrated_heating = float(np.sum(absorption_heating * widths))
    energy_residual = bottom_flux - top_flux + integrated_heating
    mu = transfer.direction_cosine
    weight = transfer.angular_weight
    top_gross_frequency = 2.0 * np.pi * np.einsum(
        "m,fm,m->f", weight, transfer.top_boundary_intensity, np.abs(mu)
    )
    bottom_gross_frequency = 2.0 * np.pi * np.einsum(
        "m,fm,m->f", weight, transfer.bottom_boundary_intensity, np.abs(mu)
    )
    top_gross = float(np.trapezoid(top_gross_frequency, frequency))
    bottom_gross = float(np.trapezoid(bottom_gross_frequency, frequency))
    energy_scale = max(top_gross, bottom_gross, abs(integrated_heating))
    relative_energy_residual = (
        abs(energy_residual) / energy_scale if energy_scale > 0.0 else abs(energy_residual)
    )
    photon_identity, relative_photon_identity = _photon_rate_identity_residual(
        frequency,
        transfer.mean_intensity,
        continuum,
        rates,
        fractions,
        hydrogen_nuclei,
        helium_nuclei,
    )
    return EmissiveCoupledSlab(
        temperature_k=_readonly(np.array(temperature, copy=True)),
        population=_population_state(fractions, hydrogen_nuclei, helium_nuclei),
        continuum=continuum,
        radiative_rates=rates,
        transfer=transfer,
        radiative_heating_erg_s_cm3=_readonly(np.array(absorption_heating, copy=True)),
        required_thermostat_heating_erg_s_cm3=_readonly(
            np.array(-absorption_heating, copy=True)
        ),
        boundary_energy_balance_residual_erg_s_cm2=energy_residual,
        relative_boundary_energy_balance_residual=relative_energy_residual,
        maximum_photon_rate_identity_residual_cm3_s1=photon_identity,
        maximum_relative_photon_rate_identity_residual=relative_photon_identity,
        maximum_population_fixed_point_residual=fixed_point_residual,
        maximum_relative_charge_residual=equilibrium.maximum_relative_charge_residual,
        iteration_count=iteration,
        iteration_residual_history=_readonly(np.asarray(residual_history, dtype=np.float64)),
        relaxation=relax,
        tolerance=threshold,
        includes_collisional_kinetics=bool(include_collisional_kinetics),
    )
