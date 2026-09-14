"""周期动态柱冻结物质状态上的非局域频率--角度转移审计。

本模块把 ZO 动态半柱按中面对称镜像为完整双面柱，并在两侧真空边界上
求静态离散纵标形式解。它用于检验局域 ``J_nu=B_nu`` 闭合和准静态辐射
假设，不把逐相位静态形式解冒充含辐射记忆的动态 NLTE 解。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .continuum_emission import (
    GroundStateMilneRadiativeRates,
    ground_state_milne_continuum,
    ground_state_milne_radiative_rates,
)
from .frequency_quadrature import (
    integrate_frequency,
    validate_frequency_weights_hz,
)
from .radiation import LIGHT_SPEED_CM_S, planck_nu
from .radiative_transfer_1d import (
    gauss_legendre_half_range_mu_weights,
    solve_static_slab_transfer,
)
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class SymmetricFullColumn:
    """由一个表面到中面的半柱镜像得到的完整平面平行柱。"""

    depth_edges_cm: NDArray[np.float64]
    cell_width_cm: NDArray[np.float64]
    density_g_cm3: NDArray[np.float64]
    temperature_k: NDArray[np.float64]
    hydrogen_fraction: NDArray[np.float64]
    helium_fraction: NDArray[np.float64]
    half_depth_points: int
    half_thickness_cm: float
    one_sided_column_mass_g_cm2: float
    maximum_mirror_residual: float


@dataclass(frozen=True)
class FrozenNonlocalTransferPhase:
    """一个冻结动态相位的频率分辨非局域辐射诊断。"""

    frequency_hz: NDArray[np.float64]
    frequency_weight_hz: NDArray[np.float64]
    mean_intensity_top_half_cgs: NDArray[np.float64]
    top_outward_flux_nu_cgs: NDArray[np.float64]
    bottom_outward_flux_nu_cgs: NDArray[np.float64]
    radiative_heating_top_half_erg_s_cm3: NDArray[np.float64]
    nonlocal_rates: GroundStateMilneRadiativeRates
    local_planck_rates: GroundStateMilneRadiativeRates
    extinction_optical_depth_full: NDArray[np.float64]
    true_absorption_optical_depth_full: NDArray[np.float64]
    top_outward_bolometric_flux_erg_s_cm2: float
    bottom_outward_bolometric_flux_erg_s_cm2: float
    integrated_full_column_heating_erg_s_cm2: float
    relative_integrated_energy_residual: float
    maximum_source_equation_residual: float
    maximum_lambda_system_condition_number: float
    maximum_mean_intensity_mirror_residual: float
    maximum_boundary_spectrum_mirror_residual: float
    minimum_intensity_cgs: float
    minimum_source_function_cgs: float
    material_half_depth_points: int
    transfer_half_depth_points: int
    transfer_subcells_per_material_cell: int
    scattering_linear_solver: str


@dataclass(frozen=True)
class RadiationTimescaleAudit:
    """全轨道光行时与 Rosseland 扩散时标。"""

    half_thickness_cm: NDArray[np.float64]
    half_rosseland_optical_depth: NDArray[np.float64]
    light_crossing_time_s: NDArray[np.float64]
    diffusion_time_s: NDArray[np.float64]
    orbital_period_s: float
    maximum_light_crossing_to_orbit: float
    maximum_diffusion_to_orbit: float
    phase_fraction_diffusion_to_orbit_above_003: float
    phase_fraction_diffusion_to_orbit_above_01: float
    phase_fraction_diffusion_to_orbit_above_03: float


def _positive_profile(name: str, values: ArrayLike) -> NDArray[np.float64]:
    result = np.array(values, dtype=np.float64, copy=True)
    if result.ndim != 1 or result.size < 1:
        raise PhysicalDomainError(f"{name} must be a non-empty one-dimensional array")
    if not np.all(np.isfinite(result)) or np.any(result <= 0.0):
        raise PhysicalDomainError(f"{name} must be finite and strictly positive")
    return result


def _population_array(
    name: str, values: ArrayLike, shape: tuple[int, int]
) -> NDArray[np.float64]:
    result = np.array(values, dtype=np.float64, copy=True)
    if result.shape != shape:
        raise PhysicalDomainError(f"{name} must have shape {shape}")
    if not np.all(np.isfinite(result)) or np.any(result < 0.0) or np.any(result > 1.0):
        raise PhysicalDomainError(f"{name} must be finite and lie in [0, 1]")
    return result


def symmetric_full_column_from_half(
    cell_mass_g_cm2: ArrayLike,
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    hydrogen_fraction: ArrayLike,
    helium_fraction: ArrayLike,
) -> SymmetricFullColumn:
    """镜像一个表面到中面的拉格朗日半柱，不改写其物质状态。"""
    cell_mass = _positive_profile("cell_mass_g_cm2", cell_mass_g_cm2)
    density = _positive_profile("density_g_cm3", density_g_cm3)
    temperature = _positive_profile("temperature_k", temperature_k)
    if density.shape != cell_mass.shape or temperature.shape != cell_mass.shape:
        raise PhysicalDomainError("half-column mass, density and temperature must match")
    depth_points = cell_mass.size
    hydrogen = _population_array(
        "hydrogen_fraction", hydrogen_fraction, (depth_points, 2)
    )
    helium = _population_array(
        "helium_fraction", helium_fraction, (depth_points, 3)
    )
    tolerance = 64.0 * np.finfo(np.float64).eps
    if np.any(np.abs(np.sum(hydrogen, axis=1) - 1.0) > tolerance):
        raise PhysicalDomainError("hydrogen fractions must sum to one")
    if np.any(np.abs(np.sum(helium, axis=1) - 1.0) > tolerance):
        raise PhysicalDomainError("helium fractions must sum to one")

    half_width = cell_mass / density
    full_width = np.concatenate((half_width, half_width[::-1]))
    full_density = np.concatenate((density, density[::-1]))
    full_temperature = np.concatenate((temperature, temperature[::-1]))
    full_hydrogen = np.concatenate((hydrogen, hydrogen[::-1]), axis=0)
    full_helium = np.concatenate((helium, helium[::-1]), axis=0)
    edges = np.concatenate(([0.0], np.cumsum(full_width)))
    mass_recovered = full_density * full_width
    full_mass = np.concatenate((cell_mass, cell_mass[::-1]))
    mirror_residual = max(
        _normalized_maximum_difference(full_width, full_width[::-1]),
        _normalized_maximum_difference(full_density, full_density[::-1]),
        _normalized_maximum_difference(full_temperature, full_temperature[::-1]),
        _normalized_maximum_difference(full_hydrogen, full_hydrogen[::-1]),
        _normalized_maximum_difference(full_helium, full_helium[::-1]),
        _normalized_maximum_difference(mass_recovered, full_mass),
    )
    if mirror_residual > 16.0 * np.finfo(np.float64).eps:
        raise ArithmeticError("symmetric full-column construction lost exact mirroring")
    return SymmetricFullColumn(
        depth_edges_cm=_readonly(edges),
        cell_width_cm=_readonly(full_width),
        density_g_cm3=_readonly(full_density),
        temperature_k=_readonly(full_temperature),
        hydrogen_fraction=_readonly(full_hydrogen),
        helium_fraction=_readonly(full_helium),
        half_depth_points=depth_points,
        half_thickness_cm=float(np.sum(half_width)),
        one_sided_column_mass_g_cm2=float(np.sum(cell_mass)),
        maximum_mirror_residual=mirror_residual,
    )


def _normalized_maximum_difference(
    first: NDArray[np.float64], second: NDArray[np.float64]
) -> float:
    scale = max(float(np.max(np.abs(first))), float(np.max(np.abs(second))))
    absolute = float(np.max(np.abs(first - second)))
    return absolute / scale if scale > 0.0 else absolute


def solve_frozen_nonlocal_transfer_phase(
    frequency_hz: ArrayLike,
    cell_mass_g_cm2: ArrayLike,
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    hydrogen_fraction: ArrayLike,
    helium_fraction: ArrayLike,
    *,
    angular_order: int = 4,
    include_electron_scattering: bool = True,
    frequency_weight_hz: ArrayLike | None = None,
    transfer_subcells_per_material_cell: int = 1,
    scattering_linear_solver: Literal["dense_lambda", "sparse_interface"] = (
        "dense_lambda"
    ),
) -> FrozenNonlocalTransferPhase:
    """求一个冻结动态相位的完整对称柱非局域形式解。"""
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    if (
        frequency.ndim != 1
        or frequency.size < 2
        or not np.all(np.isfinite(frequency))
        or np.any(frequency <= 0.0)
        or np.any(np.diff(frequency) <= 0.0)
    ):
        raise PhysicalDomainError(
            "frequency_hz must be finite, positive and strictly increasing"
        )
    frequency, quadrature_weight = validate_frequency_weights_hz(
        frequency, frequency_weight_hz
    )
    material_column = symmetric_full_column_from_half(
        cell_mass_g_cm2,
        density_g_cm3,
        temperature_k,
        hydrogen_fraction,
        helium_fraction,
    )
    if (
        not isinstance(transfer_subcells_per_material_cell, (int, np.integer))
        or isinstance(transfer_subcells_per_material_cell, (bool, np.bool_))
        or int(transfer_subcells_per_material_cell) < 1
    ):
        raise PhysicalDomainError(
            "transfer_subcells_per_material_cell must be a positive integer"
        )
    transfer_subcells = int(transfer_subcells_per_material_cell)
    material_half = material_column.half_depth_points
    material_mass = (
        material_column.density_g_cm3[:material_half]
        * material_column.cell_width_cm[:material_half]
    )
    if transfer_subcells == 1:
        column = material_column
    else:
        # 中文：辐射子单元仅解析源函数梯度；父单元物性保持逐位不变。
        column = symmetric_full_column_from_half(
            np.repeat(material_mass / transfer_subcells, transfer_subcells),
            np.repeat(
                material_column.density_g_cm3[:material_half], transfer_subcells
            ),
            np.repeat(
                material_column.temperature_k[:material_half], transfer_subcells
            ),
            np.repeat(
                material_column.hydrogen_fraction[:material_half],
                transfer_subcells,
                axis=0,
            ),
            np.repeat(
                material_column.helium_fraction[:material_half],
                transfer_subcells,
                axis=0,
            ),
        )
    continuum = ground_state_milne_continuum(
        column.density_g_cm3,
        column.temperature_k,
        frequency,
        column.hydrogen_fraction[:, 0],
        column.hydrogen_fraction[:, 1],
        column.helium_fraction[:, 0],
        column.helium_fraction[:, 1],
        column.helium_fraction[:, 2],
        include_electron_scattering=include_electron_scattering,
    )
    mu, weight = gauss_legendre_half_range_mu_weights(angular_order)
    transfer = solve_static_slab_transfer(
        frequency,
        column.depth_edges_cm,
        mu,
        weight,
        continuum.extinction_total_per_cm,
        continuum.thermal_source_intensity,
        continuum.absorption_probability,
        scattering_linear_solver=scattering_linear_solver,
    )
    transfer_half = column.half_depth_points
    refined_mean_top = np.array(
        transfer.mean_intensity[:, :transfer_half], copy=True
    )
    mean_bottom_mirrored = transfer.mean_intensity[:, transfer_half:][:, ::-1]
    top_outward = -np.array(transfer.top_net_flux, copy=True)
    bottom_outward = np.array(transfer.bottom_net_flux, copy=True)
    if np.any(top_outward < 0.0) or np.any(bottom_outward < 0.0):
        raise ArithmeticError("vacuum-boundary outward spectrum became negative")

    # 中文：正值表示物质从非局域辐射场吸热，负值表示物质净辐射冷却。
    heating_full = 4.0 * np.pi * integrate_frequency(
        continuum.true_absorption_total_per_cm * transfer.mean_intensity
        - continuum.thermal_emissivity_total_cgs,
        quadrature_weight,
        axis=0,
    )
    refined_heating_top = np.array(heating_full[:transfer_half], copy=True)
    if transfer_subcells == 1:
        mean_top = refined_mean_top
        heating_top = refined_heating_top
    else:
        mean_top = np.mean(
            refined_mean_top.reshape(
                frequency.size, material_half, transfer_subcells
            ),
            axis=2,
        )
        heating_top = np.mean(
            refined_heating_top.reshape(material_half, transfer_subcells), axis=1
        )
    top_flux = float(integrate_frequency(top_outward, quadrature_weight))
    bottom_flux = float(integrate_frequency(bottom_outward, quadrature_weight))
    integrated_heating = float(np.sum(heating_full * column.cell_width_cm))
    energy_residual = top_flux + bottom_flux + integrated_heating
    energy_scale = max(top_flux + bottom_flux, abs(integrated_heating))
    relative_energy = (
        abs(energy_residual) / energy_scale
        if energy_scale > 0.0
        else abs(energy_residual)
    )
    extinction_depth = np.sum(
        continuum.extinction_total_per_cm * column.cell_width_cm[None, :],
        axis=1,
    )
    absorption_depth = np.sum(
        continuum.true_absorption_total_per_cm * column.cell_width_cm[None, :],
        axis=1,
    )
    nonlocal_rates = ground_state_milne_radiative_rates(
        material_column.temperature_k[:material_half],
        frequency,
        mean_top,
        frequency_weight_hz=quadrature_weight,
    )
    local_planck = planck_nu(
        frequency[:, None],
        material_column.temperature_k[None, :material_half],
    )
    local_rates = ground_state_milne_radiative_rates(
        material_column.temperature_k[:material_half],
        frequency,
        local_planck,
        frequency_weight_hz=quadrature_weight,
    )
    outputs = (
        mean_top,
        top_outward,
        bottom_outward,
        heating_top,
        extinction_depth,
        absorption_depth,
    )
    if not all(np.all(np.isfinite(value)) for value in outputs):
        raise ArithmeticError("frozen nonlocal transfer diagnostic became non-finite")
    if relative_energy > 2.0e-8:
        raise ArithmeticError(
            "integrated frozen transfer energy ledger exceeded 2e-8"
        )
    return FrozenNonlocalTransferPhase(
        frequency_hz=_readonly(frequency),
        frequency_weight_hz=_readonly(np.array(quadrature_weight, copy=True)),
        mean_intensity_top_half_cgs=_readonly(mean_top),
        top_outward_flux_nu_cgs=_readonly(top_outward),
        bottom_outward_flux_nu_cgs=_readonly(bottom_outward),
        radiative_heating_top_half_erg_s_cm3=_readonly(
            np.array(heating_top, copy=True)
        ),
        nonlocal_rates=nonlocal_rates,
        local_planck_rates=local_rates,
        extinction_optical_depth_full=_readonly(extinction_depth),
        true_absorption_optical_depth_full=_readonly(absorption_depth),
        top_outward_bolometric_flux_erg_s_cm2=top_flux,
        bottom_outward_bolometric_flux_erg_s_cm2=bottom_flux,
        integrated_full_column_heating_erg_s_cm2=integrated_heating,
        relative_integrated_energy_residual=relative_energy,
        maximum_source_equation_residual=float(
            np.max(transfer.source_equation_residual)
        ),
        maximum_lambda_system_condition_number=float(
            np.max(transfer.lambda_system_condition_number)
        ),
        maximum_mean_intensity_mirror_residual=(
            _normalized_maximum_difference(
                refined_mean_top, mean_bottom_mirrored
            )
        ),
        maximum_boundary_spectrum_mirror_residual=(
            _normalized_maximum_difference(top_outward, bottom_outward)
        ),
        minimum_intensity_cgs=float(np.min(transfer.intensity_cell_average)),
        minimum_source_function_cgs=float(np.min(transfer.source_function)),
        material_half_depth_points=material_half,
        transfer_half_depth_points=transfer_half,
        transfer_subcells_per_material_cell=transfer_subcells,
        scattering_linear_solver=transfer.scattering_linear_solver,
    )


def radiation_timescale_audit(
    cell_mass_g_cm2: ArrayLike,
    density_g_cm3: ArrayLike,
    rosseland_opacity_cm2_g: ArrayLike,
    orbital_period_s: float,
) -> RadiationTimescaleAudit:
    """按 ``3 tau_R H/c`` 审计逐相位稳态辐射场的准静态条件。"""
    cell_mass = _positive_profile("cell_mass_g_cm2", cell_mass_g_cm2)
    density = np.array(density_g_cm3, dtype=np.float64, copy=True)
    opacity = np.array(rosseland_opacity_cm2_g, dtype=np.float64, copy=True)
    shape = (density.shape[0], cell_mass.size) if density.ndim == 2 else None
    if shape is None or density.shape != shape or opacity.shape != shape:
        raise PhysicalDomainError(
            "density and Rosseland opacity must share a phase-depth grid"
        )
    if (
        not np.all(np.isfinite(density))
        or not np.all(np.isfinite(opacity))
        or np.any(density <= 0.0)
        or np.any(opacity <= 0.0)
    ):
        raise PhysicalDomainError(
            "density and Rosseland opacity must be finite and positive"
        )
    period = float(orbital_period_s)
    if not np.isfinite(period) or period <= 0.0:
        raise PhysicalDomainError("orbital_period_s must be finite and positive")
    thickness = np.sum(cell_mass[None, :] / density, axis=1)
    optical_depth = np.sum(opacity * cell_mass[None, :], axis=1)
    light_time = thickness / LIGHT_SPEED_CM_S
    diffusion_time = 3.0 * optical_depth * light_time
    ratio = diffusion_time / period
    return RadiationTimescaleAudit(
        half_thickness_cm=_readonly(thickness),
        half_rosseland_optical_depth=_readonly(optical_depth),
        light_crossing_time_s=_readonly(light_time),
        diffusion_time_s=_readonly(diffusion_time),
        orbital_period_s=period,
        maximum_light_crossing_to_orbit=float(np.max(light_time / period)),
        maximum_diffusion_to_orbit=float(np.max(ratio)),
        phase_fraction_diffusion_to_orbit_above_003=float(np.mean(ratio > 0.03)),
        phase_fraction_diffusion_to_orbit_above_01=float(np.mean(ratio > 0.1)),
        phase_fraction_diffusion_to_orbit_above_03=float(np.mean(ratio > 0.3)),
    )
