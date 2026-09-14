"""ZO 约束的有限静力柱坐标、耗散控制与压力审计。

本模块不重定义 ZO 的 ``H(a,E)``。它把已有单边柱质量、尺度高度和
共动压力重力映射到 Lynch--Ogilvie 的归一化 n=3 垂向闭合，并用镜像
完整柱精确实现中面对称辐射边界。温度与辐射场仍由连续谱求解器给出；
压力审计决定该规定 ZO 密度是否可作为静态大气表，而不是预先宣告通过。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import brentq

from .atmosphere import (
    PROTON_MASS_G,
    SOLAR_FULLY_IONIZED_H_HE,
    THOMSON_CROSS_SECTION_CM2,
    FullyIonizedHydrogenHeliumComposition,
)
from .continuum_emission import EmissiveCoupledSlab, ground_state_milne_continuum
from .non_gray import lte_hydrogen_helium_ionization
from .radiation import (
    BOLTZMANN_ERG_K,
    LIGHT_SPEED_CM_S,
    PLANCK_ERG_S,
    STEFAN_BOLTZMANN_ERG_S_CM2_K4,
    planck_nu,
)
from .source import PhysicalDomainError
from .vertical import RADIATION_PRESSURE_POLYTROPE_PROFILE


DissipationLaw = Literal["uniform_specific", "alpha_support_pressure"]


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class ZOConstrainedN3Column:
    """由 ZO 的 ``(m0,H,Q)`` 唯一确定的镜像 n=3 有限柱。"""

    midplane_column_mass_g_cm2: float
    scale_height_cm: float
    gravity_coefficient_s2: float
    half_mass_edges_g_cm2: NDArray[np.float64]
    half_height_edges_cm: NDArray[np.float64]
    full_depth_edges_cm: NDArray[np.float64]
    full_signed_height_cm: NDArray[np.float64]
    full_density_g_cm3: NDArray[np.float64]
    required_support_pressure_erg_cm3: NDArray[np.float64]
    central_density_g_cm3: float
    central_support_pressure_erg_cm3: float
    surface_height_cm: float
    mass_spacing_power: float
    relative_mass_reconstruction_residual: float

    @property
    def half_depth_points(self) -> int:
        return self.half_mass_edges_g_cm2.size - 1

    @property
    def full_depth_points(self) -> int:
        return self.full_density_g_cm3.size

    @property
    def full_cell_mass_g_cm2(self) -> NDArray[np.float64]:
        mass = self.full_density_g_cm3 * np.diff(self.full_depth_edges_cm)
        return _readonly(np.array(mass, copy=True))


@dataclass(frozen=True)
class SymmetricDissipationProfile:
    """预先声明的耗散律及其逐体积加热。"""

    law: DissipationLaw
    full_heating_erg_s_cm3: NDArray[np.float64]
    half_specific_heating_erg_s_g: NDArray[np.float64]
    one_face_target_flux_erg_s_cm2: float
    recovered_one_face_flux_erg_s_cm2: float
    relative_flux_residual: float


@dataclass(frozen=True)
class HydrostaticPressureAudit:
    """温度--辐射解相对 ZO n=3 支撑压力的独立验收量。"""

    gas_pressure_erg_cm3: NDArray[np.float64]
    radiation_pressure_erg_cm3: NDArray[np.float64]
    total_pressure_erg_cm3: NDArray[np.float64]
    required_support_pressure_erg_cm3: NDArray[np.float64]
    mass_weighted_relative_l1_pressure_residual: float
    mass_weighted_relative_rms_pressure_residual: float
    maximum_pressure_residual_over_central_support: float
    top_half_maximum_radiative_to_gravity_acceleration: float
    top_surface_flux_erg_s_cm2: float
    bottom_surface_flux_erg_s_cm2: float
    relative_surface_flux_asymmetry: float
    maximum_temperature_mirror_residual: float
    maximum_density_mirror_residual: float


@dataclass(frozen=True)
class GreyDiffusionColumn:
    """电子散射灰控制下的半柱通量和镜像温度结构。"""

    half_flux_edges_erg_s_cm2: NDArray[np.float64]
    half_temperature_edges_k: NDArray[np.float64]
    full_temperature_k: NDArray[np.float64]
    half_grey_opacity_cm2_g: NDArray[np.float64]
    surface_temperature_fourth_factor: float
    midplane_flux_residual_over_one_face_flux: float
    dissipation_law: DissipationLaw
    opacity_closure: str
    opacity_iteration_count: int
    maximum_relative_opacity_temperature_residual: float


@dataclass(frozen=True)
class GreyDiffusionSupportAudit:
    """灰扩散温度对 ZO n=3 支撑压力的静力门。"""

    gas_pressure_erg_cm3: NDArray[np.float64]
    radiation_pressure_erg_cm3: NDArray[np.float64]
    total_pressure_erg_cm3: NDArray[np.float64]
    required_support_pressure_erg_cm3: NDArray[np.float64]
    mass_weighted_relative_l1_pressure_residual: float
    mass_weighted_relative_rms_pressure_residual: float
    maximum_pressure_residual_over_central_support: float
    top_half_maximum_radiative_to_gravity_acceleration: float
    deepest_cell_total_to_required_pressure: float
    deepest_cell_radiation_pressure_fraction: float


@dataclass(frozen=True)
class GreyScaleHeightDiagnostic:
    """以最深单元压力匹配定义的静力尺度高度诊断。"""

    reference_scale_height_cm: float
    matched_scale_height_cm: float
    matched_to_reference_scale_height: float
    lower_bracket_factor: float
    upper_bracket_factor: float
    root_function_evaluations: int
    column: ZOConstrainedN3Column
    dissipation: SymmetricDissipationProfile
    diffusion: GreyDiffusionColumn
    support_audit: GreyDiffusionSupportAudit


def build_zo_constrained_n3_column(
    midplane_column_mass_g_cm2: float,
    scale_height_cm: float,
    gravity_coefficient_s2: float,
    half_depth_points: int,
    *,
    mass_spacing_power: float = 2.0,
    mass_fraction_edges: ArrayLike | None = None,
) -> ZOConstrainedN3Column:
    """在质量柱上离散 ZO 已有的有限 n=3 垂向闭合。

    ``m=0`` 的有限支撑表面直接放在 ``z=3H``；内部边界由解析反柱函数
    取得。单元密度定义为 ``Delta m / Delta z``，所以无需事后重归一化
    就逐浮点精度回收输入柱质量。
    """
    m0 = float(midplane_column_mass_g_cm2)
    height = float(scale_height_cm)
    gravity = float(gravity_coefficient_s2)
    spacing = float(mass_spacing_power)
    if any(not np.isfinite(value) or value <= 0.0 for value in (m0, height, gravity)):
        raise PhysicalDomainError("m0, H and Q must be finite and strictly positive")
    if (
        not isinstance(half_depth_points, (int, np.integer))
        or isinstance(half_depth_points, (bool, np.bool_))
        or int(half_depth_points) < 2
    ):
        raise PhysicalDomainError("half_depth_points must be an integer >= 2")
    if not np.isfinite(spacing) or spacing <= 0.0:
        raise PhysicalDomainError("mass_spacing_power must be finite and positive")
    count = int(half_depth_points)
    if mass_fraction_edges is None:
        fractional_edge = (
            np.arange(count + 1, dtype=np.float64) / count
        ) ** spacing
    else:
        fractional_edge = np.array(
            mass_fraction_edges, dtype=np.float64, copy=True
        )
        if fractional_edge.shape != (count + 1,):
            raise PhysicalDomainError(
                "mass_fraction_edges must have half_depth_points + 1 entries"
            )
        if (
            not np.all(np.isfinite(fractional_edge))
            or fractional_edge[0] != 0.0
            or fractional_edge[-1] != 1.0
            or np.any(np.diff(fractional_edge) <= 0.0)
        ):
            raise PhysicalDomainError(
                "mass_fraction_edges must be finite, strictly increasing and span [0, 1]"
            )
    mass_edge = m0 * fractional_edge
    upper_fraction = mass_edge / (2.0 * m0)
    scaled_height = np.empty_like(upper_fraction)
    scaled_height[0] = RADIATION_PRESSURE_POLYTROPE_PROFILE.surface_scaled_height
    scaled_height[1:] = (
        RADIATION_PRESSURE_POLYTROPE_PROFILE.inverse_upper_column_fraction(
            upper_fraction[1:]
        )
    )
    if np.any(np.diff(scaled_height) >= 0.0) or scaled_height[-1] != 0.0:
        raise ArithmeticError("n=3 mass-to-height inversion lost its ordering")
    surface_height = (
        RADIATION_PRESSURE_POLYTROPE_PROFILE.surface_scaled_height * height
    )
    half_height_edge = scaled_height * height
    half_depth_edge = surface_height - half_height_edge
    half_width = np.diff(half_depth_edge)
    half_cell_mass = np.diff(mass_edge)
    half_density = half_cell_mass / half_width
    if np.any(half_width <= 0.0) or np.any(half_density <= 0.0):
        raise ArithmeticError("finite n=3 column produced a non-positive cell")

    # 中文：镜像上半柱；中心只出现一次，因此辐射边界等价于中面反射对称。
    lower_depth_edge = 2.0 * surface_height - half_depth_edge[-2::-1]
    full_depth_edge = np.concatenate((half_depth_edge, lower_depth_edge))
    full_density = np.concatenate((half_density, half_density[::-1]))
    cell_center = 0.5 * (full_depth_edge[:-1] + full_depth_edge[1:])
    signed_height = surface_height - cell_center

    total_surface_density = 2.0 * m0
    central_density = (
        total_surface_density
        / height
        * RADIATION_PRESSURE_POLYTROPE_PROFILE.central_density_shape
    )
    central_pressure = central_density * gravity * surface_height**2 / 8.0
    half_cell_height = 0.5 * (half_height_edge[:-1] + half_height_edge[1:])
    half_pressure_factor = 1.0 - (half_cell_height / surface_height) ** 2
    if np.any(half_pressure_factor <= 0.0):
        raise ArithmeticError("cell centre reached the zero-pressure finite surface")
    half_required_pressure = central_pressure * half_pressure_factor**4
    required_pressure = np.concatenate(
        (half_required_pressure, half_required_pressure[::-1])
    )
    recovered_mass = float(np.sum(full_density * np.diff(full_depth_edge)))
    mass_residual = abs(recovered_mass / total_surface_density - 1.0)
    arrays = (
        mass_edge,
        half_height_edge,
        full_depth_edge,
        signed_height,
        full_density,
        required_pressure,
    )
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ArithmeticError("finite n=3 column became non-finite")
    return ZOConstrainedN3Column(
        midplane_column_mass_g_cm2=m0,
        scale_height_cm=height,
        gravity_coefficient_s2=gravity,
        half_mass_edges_g_cm2=_readonly(np.array(mass_edge, copy=True)),
        half_height_edges_cm=_readonly(np.array(half_height_edge, copy=True)),
        full_depth_edges_cm=_readonly(np.array(full_depth_edge, copy=True)),
        full_signed_height_cm=_readonly(np.array(signed_height, copy=True)),
        full_density_g_cm3=_readonly(np.array(full_density, copy=True)),
        required_support_pressure_erg_cm3=_readonly(
            np.array(required_pressure, copy=True)
        ),
        central_density_g_cm3=float(central_density),
        central_support_pressure_erg_cm3=float(central_pressure),
        surface_height_cm=float(surface_height),
        mass_spacing_power=spacing,
        relative_mass_reconstruction_residual=float(mass_residual),
    )


def symmetric_dissipation_profile(
    column: ZOConstrainedN3Column,
    one_face_flux_erg_s_cm2: float,
    law: DissipationLaw,
) -> SymmetricDissipationProfile:
    """构造单位质量均匀或局域支撑压力 α 控制耗散。

    ``uniform_specific`` 对应每克相同加热。``alpha_support_pressure``
    采用局域体积耗散正比于 n=3 支撑压力，即单位质量形状为 ``P/rho``。
    两者的系数都在求解前由给定单面通量唯一决定，不根据输出谱调节。
    """
    if not isinstance(column, ZOConstrainedN3Column):
        raise TypeError("column must be a ZOConstrainedN3Column")
    flux = float(one_face_flux_erg_s_cm2)
    if not np.isfinite(flux) or flux < 0.0:
        raise PhysicalDomainError("one_face_flux_erg_s_cm2 must be finite and non-negative")
    if law not in ("uniform_specific", "alpha_support_pressure"):
        raise PhysicalDomainError("unknown dissipation law")
    count = column.half_depth_points
    half_density = column.full_density_g_cm3[:count]
    half_pressure = column.required_support_pressure_erg_cm3[:count]
    half_cell_mass = np.diff(column.half_mass_edges_g_cm2)
    if law == "uniform_specific":
        specific = np.full(count, flux / column.midplane_column_mass_g_cm2)
    else:
        shape = half_pressure / half_density
        normalization = float(np.sum(shape * half_cell_mass))
        if not np.isfinite(normalization) or normalization <= 0.0:
            raise ArithmeticError("alpha-pressure dissipation normalization failed")
        specific = flux * shape / normalization
    half_heating = specific * half_density
    full_heating = np.concatenate((half_heating, half_heating[::-1]))
    recovered = float(np.sum(half_heating * np.diff(column.full_depth_edges_cm)[:count]))
    scale = flux if flux > 0.0 else 1.0
    residual = abs(recovered - flux) / scale
    if not np.all(np.isfinite(full_heating)) or np.any(full_heating < 0.0):
        raise ArithmeticError("symmetric dissipation became invalid")
    return SymmetricDissipationProfile(
        law=law,
        full_heating_erg_s_cm3=_readonly(np.array(full_heating, copy=True)),
        half_specific_heating_erg_s_g=_readonly(np.array(specific, copy=True)),
        one_face_target_flux_erg_s_cm2=flux,
        recovered_one_face_flux_erg_s_cm2=recovered,
        relative_flux_residual=float(residual),
    )


def grey_surface_to_midplane_temperature_seed_k(
    column: ZOConstrainedN3Column,
    effective_temperature_k: float,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> NDArray[np.float64]:
    """返回只用于非线性初值的灰 Eddington 镜像温度剖面。"""
    temperature = float(effective_temperature_k)
    if not np.isfinite(temperature) or temperature <= 0.0:
        raise PhysicalDomainError("effective_temperature_k must be finite and positive")
    electron_per_gram = (
        composition.hydrogen_mass_fraction
        + 0.5 * composition.helium_mass_fraction
    ) / PROTON_MASS_G
    scattering_opacity = THOMSON_CROSS_SECTION_CM2 * electron_per_gram
    half_mass_center = 0.5 * (
        column.half_mass_edges_g_cm2[:-1]
        + column.half_mass_edges_g_cm2[1:]
    )
    optical_depth = scattering_opacity * half_mass_center
    half_temperature = temperature * (0.75 * (optical_depth + 2.0 / 3.0)) ** 0.25
    full_temperature = np.concatenate((half_temperature, half_temperature[::-1]))
    if not np.all(np.isfinite(full_temperature)) or np.any(full_temperature <= 0.0):
        raise ArithmeticError("grey temperature seed became invalid")
    return _readonly(full_temperature)


def fully_ionized_electron_scattering_opacity_cm2_g(
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> float:
    """返回给定 H/He 组成的完全电离 Thomson 质量不透明度。"""
    electron_per_gram = (
        composition.hydrogen_mass_fraction
        + 0.5 * composition.helium_mass_fraction
    ) / PROTON_MASS_G
    opacity = THOMSON_CROSS_SECTION_CM2 * electron_per_gram
    if not np.isfinite(opacity) or opacity <= 0.0:
        raise ArithmeticError("electron-scattering opacity became invalid")
    return float(opacity)


def solve_grey_diffusion_column(
    column: ZOConstrainedN3Column,
    dissipation: SymmetricDissipationProfile,
    effective_temperature_k: float,
    *,
    grey_opacity_cm2_g: float | None = None,
    surface_temperature_fourth_factor: float = 0.5,
) -> GreyDiffusionColumn:
    """积分有限盘半柱的灰扩散方程。

    质量坐标从表面指向中面。通量由 ``dF/dm=-q_m`` 精确逐单元积分，
    温度满足 ``dT^4/dm=3*kappa*F/(4*sigma_SB)``。表面常数默认采用
    Eddington 真空边界 ``T^4(0)=T_eff^4/2``；它是灰控制，不是最终
    非灰大气边界。
    """
    if not isinstance(column, ZOConstrainedN3Column):
        raise TypeError("column must be a ZOConstrainedN3Column")
    if not isinstance(dissipation, SymmetricDissipationProfile):
        raise TypeError("dissipation must be a SymmetricDissipationProfile")
    if dissipation.full_heating_erg_s_cm3.size != column.full_depth_points:
        raise PhysicalDomainError("dissipation and column depth grids do not match")
    temperature = float(effective_temperature_k)
    boundary_factor = float(surface_temperature_fourth_factor)
    if not np.isfinite(temperature) or temperature <= 0.0:
        raise PhysicalDomainError("effective_temperature_k must be finite and positive")
    if not np.isfinite(boundary_factor) or boundary_factor <= 0.0:
        raise PhysicalDomainError(
            "surface_temperature_fourth_factor must be finite and positive"
        )
    opacity_scalar = (
        fully_ionized_electron_scattering_opacity_cm2_g()
        if grey_opacity_cm2_g is None
        else float(grey_opacity_cm2_g)
    )
    if not np.isfinite(opacity_scalar) or opacity_scalar <= 0.0:
        raise PhysicalDomainError("grey_opacity_cm2_g must be finite and positive")
    cell_mass = np.diff(column.half_mass_edges_g_cm2)
    opacity = np.full(cell_mass.size, opacity_scalar)
    specific = dissipation.half_specific_heating_erg_s_g
    flux = np.empty(cell_mass.size + 1, dtype=np.float64)
    flux[0] = dissipation.one_face_target_flux_erg_s_cm2
    for index in range(cell_mass.size):
        flux[index + 1] = flux[index] - specific[index] * cell_mass[index]
    flux_scale = (
        dissipation.one_face_target_flux_erg_s_cm2
        if dissipation.one_face_target_flux_erg_s_cm2 > 0.0
        else 1.0
    )
    roundoff = 64.0 * np.finfo(np.float64).eps * flux_scale
    if np.any(flux < -roundoff):
        raise ArithmeticError("grey diffusion flux became physically negative")
    temperature_fourth = np.empty_like(flux)
    temperature_fourth[0] = boundary_factor * temperature**4
    for index in range(cell_mass.size):
        integrated_flux = 0.5 * (flux[index] + flux[index + 1]) * cell_mass[index]
        temperature_fourth[index + 1] = (
            temperature_fourth[index]
            + 3.0
            * opacity[index]
            * integrated_flux
            / (4.0 * STEFAN_BOLTZMANN_ERG_S_CM2_K4)
        )
    half_cell_temperature = (
        0.5 * (temperature_fourth[:-1] + temperature_fourth[1:])
    ) ** 0.25
    full_temperature = np.concatenate(
        (half_cell_temperature, half_cell_temperature[::-1])
    )
    if (
        not np.all(np.isfinite(flux))
        or not np.all(np.isfinite(full_temperature))
        or np.any(full_temperature <= 0.0)
    ):
        raise ArithmeticError("grey diffusion structure became invalid")
    return GreyDiffusionColumn(
        half_flux_edges_erg_s_cm2=_readonly(np.array(flux, copy=True)),
        half_temperature_edges_k=_readonly(temperature_fourth**0.25),
        full_temperature_k=_readonly(np.array(full_temperature, copy=True)),
        half_grey_opacity_cm2_g=_readonly(np.array(opacity, copy=True)),
        surface_temperature_fourth_factor=boundary_factor,
        midplane_flux_residual_over_one_face_flux=float(abs(flux[-1]) / flux_scale),
        dissipation_law=dissipation.law,
        opacity_closure="fully ionized electron-scattering grey control [A]",
        opacity_iteration_count=0,
        maximum_relative_opacity_temperature_residual=0.0,
    )


def lte_ground_state_h_he_rosseland_mean_opacity_cm2_g(
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    frequency_hz: ArrayLike,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> NDArray[np.float64]:
    """计算基态 H/He Milne 连续谱的 LTE Rosseland 平均不透明度。"""
    density, temperature = np.broadcast_arrays(
        np.asarray(density_g_cm3, dtype=np.float64),
        np.asarray(temperature_k, dtype=np.float64),
    )
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    if density.ndim != 1 or temperature.ndim != 1:
        raise PhysicalDomainError("density and temperature must be one-dimensional")
    if (
        frequency.ndim != 1
        or frequency.size < 2
        or not np.all(np.isfinite(frequency))
        or np.any(frequency <= 0.0)
        or np.any(np.diff(frequency) <= 0.0)
    ):
        raise PhysicalDomainError("frequency_hz must be finite, positive and increasing")
    ionization = lte_hydrogen_helium_ionization(density, temperature, composition)
    continuum = ground_state_milne_continuum(
        density,
        temperature,
        frequency,
        ionization.hydrogen_neutral_fraction,
        ionization.hydrogen_ionized_fraction,
        ionization.helium_neutral_fraction,
        ionization.helium_singly_ionized_fraction,
        ionization.helium_doubly_ionized_fraction,
        composition=composition,
        include_electron_scattering=True,
    )
    total_opacity = continuum.extinction_total_per_cm / density[None, :]
    exponent = (
        PLANCK_ERG_S * frequency[:, None]
        / (BOLTZMANN_ERG_K * temperature[None, :])
    )
    derivative = (
        planck_nu(frequency[:, None], temperature[None, :])
        * exponent
        / temperature[None, :]
        / (-np.expm1(-exponent))
    )
    numerator = np.trapezoid(derivative, frequency, axis=0)
    denominator = np.trapezoid(derivative / total_opacity, frequency, axis=0)
    rosseland = numerator / denominator
    if not np.all(np.isfinite(rosseland)) or np.any(rosseland <= 0.0):
        raise ArithmeticError("LTE H/He Rosseland mean became invalid")
    return _readonly(np.array(rosseland, copy=True))


def solve_lte_rosseland_diffusion_column(
    column: ZOConstrainedN3Column,
    dissipation: SymmetricDissipationProfile,
    effective_temperature_k: float,
    frequency_hz: ArrayLike,
    *,
    surface_temperature_fourth_factor: float = 0.5,
    relative_tolerance: float = 1.0e-7,
    maximum_iterations: int = 128,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> GreyDiffusionColumn:
    """自洽迭代 LTE 基态 H/He Rosseland 平均的深部灰扩散结构。"""
    tolerance = float(relative_tolerance)
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise PhysicalDomainError("relative_tolerance must be finite and positive")
    if (
        not isinstance(maximum_iterations, (int, np.integer))
        or isinstance(maximum_iterations, (bool, np.bool_))
        or int(maximum_iterations) < 1
    ):
        raise PhysicalDomainError("maximum_iterations must be a positive integer")
    control = solve_grey_diffusion_column(
        column,
        dissipation,
        effective_temperature_k,
        surface_temperature_fourth_factor=surface_temperature_fourth_factor,
    )
    flux = control.half_flux_edges_erg_s_cm2
    cell_mass = np.diff(column.half_mass_edges_g_cm2)
    density = column.full_density_g_cm3[: column.half_depth_points]
    temperature_fourth = control.half_temperature_edges_k**4
    residual = np.inf
    opacity = control.half_grey_opacity_cm2_g
    for iteration in range(1, int(maximum_iterations) + 1):
        cell_temperature = (
            0.5 * (temperature_fourth[:-1] + temperature_fourth[1:])
        ) ** 0.25
        opacity = lte_ground_state_h_he_rosseland_mean_opacity_cm2_g(
            density,
            cell_temperature,
            frequency_hz,
            composition=composition,
        )
        updated_fourth = np.empty_like(temperature_fourth)
        updated_fourth[0] = (
            surface_temperature_fourth_factor * float(effective_temperature_k) ** 4
        )
        for index in range(cell_mass.size):
            integrated_flux = 0.5 * (flux[index] + flux[index + 1]) * cell_mass[index]
            updated_fourth[index + 1] = (
                updated_fourth[index]
                + 3.0
                * opacity[index]
                * integrated_flux
                / (4.0 * STEFAN_BOLTZMANN_ERG_S_CM2_K4)
            )
        updated_temperature = updated_fourth**0.25
        previous_temperature = temperature_fourth**0.25
        residual = float(
            np.max(np.abs(updated_temperature - previous_temperature) / updated_temperature)
        )
        temperature_fourth = updated_fourth
        if residual <= tolerance:
            break
    else:
        raise RuntimeError(
            "LTE Rosseland diffusion iteration did not reach its declared tolerance"
        )
    half_cell_temperature = (
        0.5 * (temperature_fourth[:-1] + temperature_fourth[1:])
    ) ** 0.25
    full_temperature = np.concatenate(
        (half_cell_temperature, half_cell_temperature[::-1])
    )
    return GreyDiffusionColumn(
        half_flux_edges_erg_s_cm2=_readonly(np.array(flux, copy=True)),
        half_temperature_edges_k=_readonly(temperature_fourth**0.25),
        full_temperature_k=_readonly(full_temperature),
        half_grey_opacity_cm2_g=_readonly(np.array(opacity, copy=True)),
        surface_temperature_fourth_factor=float(surface_temperature_fourth_factor),
        midplane_flux_residual_over_one_face_flux=control.midplane_flux_residual_over_one_face_flux,
        dissipation_law=dissipation.law,
        opacity_closure="LTE ground-state H/He Milne Rosseland mean [A/V]",
        opacity_iteration_count=iteration,
        maximum_relative_opacity_temperature_residual=residual,
    )


def audit_grey_diffusion_support(
    column: ZOConstrainedN3Column,
    diffusion: GreyDiffusionColumn,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> GreyDiffusionSupportAudit:
    """把灰扩散气体加辐射压力与 ZO 所需支撑逐质量柱比较。"""
    if diffusion.full_temperature_k.shape != (column.full_depth_points,):
        raise PhysicalDomainError("diffusion depth does not match the column")
    density = column.full_density_g_cm3
    temperature = diffusion.full_temperature_k
    ionization = lte_hydrogen_helium_ionization(density, temperature, composition)
    hydrogen_nuclei = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium_nuclei = composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    gas = BOLTZMANN_ERG_K * temperature * (
        hydrogen_nuclei + helium_nuclei + ionization.electron_density_cm3
    )
    radiation_constant = 4.0 * STEFAN_BOLTZMANN_ERG_S_CM2_K4 / LIGHT_SPEED_CM_S
    radiation = radiation_constant * temperature**4 / 3.0
    total = gas + radiation
    required = column.required_support_pressure_erg_cm3
    cell_mass = column.full_cell_mass_g_cm2
    difference = total - required
    l1 = float(np.sum(cell_mass * np.abs(difference)) / np.sum(cell_mass * required))
    rms = float(
        np.sqrt(
            np.sum(cell_mass * difference**2)
            / np.sum(cell_mass * required**2)
        )
    )
    maximum = float(np.max(np.abs(difference)) / column.central_support_pressure_erg_cm3)
    count = column.half_depth_points
    half_flux_center = 0.5 * (
        diffusion.half_flux_edges_erg_s_cm2[:-1]
        + diffusion.half_flux_edges_erg_s_cm2[1:]
    )
    radiative_acceleration = (
        diffusion.half_grey_opacity_cm2_g
        * half_flux_center
        / LIGHT_SPEED_CM_S
    )
    gravity = column.gravity_coefficient_s2 * column.full_signed_height_cm[:count]
    acceleration_ratio = float(np.max(radiative_acceleration / gravity))
    deepest = count - 1
    deepest_ratio = float(total[deepest] / required[deepest])
    radiation_fraction = float(radiation[deepest] / total[deepest])
    arrays = (gas, radiation, total, required)
    if not all(np.all(np.isfinite(array)) and np.all(array > 0.0) for array in arrays):
        raise ArithmeticError("grey support audit became invalid")
    return GreyDiffusionSupportAudit(
        gas_pressure_erg_cm3=_readonly(np.array(gas, copy=True)),
        radiation_pressure_erg_cm3=_readonly(np.array(radiation, copy=True)),
        total_pressure_erg_cm3=_readonly(np.array(total, copy=True)),
        required_support_pressure_erg_cm3=_readonly(np.array(required, copy=True)),
        mass_weighted_relative_l1_pressure_residual=l1,
        mass_weighted_relative_rms_pressure_residual=rms,
        maximum_pressure_residual_over_central_support=maximum,
        top_half_maximum_radiative_to_gravity_acceleration=acceleration_ratio,
        deepest_cell_total_to_required_pressure=deepest_ratio,
        deepest_cell_radiation_pressure_fraction=radiation_fraction,
    )


def diagnose_lte_rosseland_scale_height(
    midplane_column_mass_g_cm2: float,
    reference_scale_height_cm: float,
    gravity_coefficient_s2: float,
    effective_temperature_k: float,
    frequency_hz: ArrayLike,
    dissipation_law: DissipationLaw,
    *,
    half_depth_points: int = 64,
    scale_height_factor_bracket: tuple[float, float] = (0.02, 3.0),
    diffusion_relative_tolerance: float = 1.0e-7,
    root_relative_tolerance: float = 1.0e-8,
) -> GreyScaleHeightDiagnostic:
    """反求灰静力柱的尺度高度，并保留与 ZO ``H`` 的比值。

    根条件只匹配最靠近中面的单元总压力与 n=3 所需支撑压力。完整剖面
    残差仍由 ``support_audit`` 独立报告，不能用根条件代替全柱验收。
    """
    reference = float(reference_scale_height_cm)
    lower_factor, upper_factor = (
        float(value) for value in scale_height_factor_bracket
    )
    root_tolerance = float(root_relative_tolerance)
    if not np.isfinite(reference) or reference <= 0.0:
        raise PhysicalDomainError("reference_scale_height_cm must be finite and positive")
    if (
        not np.isfinite(lower_factor)
        or not np.isfinite(upper_factor)
        or lower_factor <= 0.0
        or upper_factor <= lower_factor
    ):
        raise PhysicalDomainError("scale-height factor bracket must be positive and ordered")
    if not np.isfinite(root_tolerance) or root_tolerance <= 0.0:
        raise PhysicalDomainError("root_relative_tolerance must be finite and positive")
    one_face_flux = one_face_flux_from_effective_temperature_erg_s_cm2(
        effective_temperature_k
    )
    cache: dict[
        float,
        tuple[
            ZOConstrainedN3Column,
            SymmetricDissipationProfile,
            GreyDiffusionColumn,
            GreyDiffusionSupportAudit,
        ],
    ] = {}

    def evaluate(factor: float):
        key = float(factor)
        if key not in cache:
            column = build_zo_constrained_n3_column(
                midplane_column_mass_g_cm2,
                reference * key,
                gravity_coefficient_s2,
                half_depth_points,
            )
            dissipation = symmetric_dissipation_profile(
                column, one_face_flux, dissipation_law
            )
            diffusion = solve_lte_rosseland_diffusion_column(
                column,
                dissipation,
                effective_temperature_k,
                frequency_hz,
                relative_tolerance=diffusion_relative_tolerance,
            )
            audit = audit_grey_diffusion_support(column, diffusion)
            cache[key] = (column, dissipation, diffusion, audit)
        return cache[key]

    lower_value = evaluate(lower_factor)[3].deepest_cell_total_to_required_pressure - 1.0
    upper_value = evaluate(upper_factor)[3].deepest_cell_total_to_required_pressure - 1.0
    if lower_value == 0.0:
        root_factor = lower_factor
    elif upper_value == 0.0:
        root_factor = upper_factor
    elif lower_value * upper_value > 0.0:
        raise PhysicalDomainError(
            "declared scale-height bracket does not contain a pressure-matching root"
        )
    else:
        root_factor = float(
            brentq(
                lambda factor: (
                    evaluate(float(factor))[3].deepest_cell_total_to_required_pressure
                    - 1.0
                ),
                lower_factor,
                upper_factor,
                xtol=root_tolerance * lower_factor,
                rtol=root_tolerance,
            )
        )
    column, dissipation, diffusion, audit = evaluate(root_factor)
    return GreyScaleHeightDiagnostic(
        reference_scale_height_cm=reference,
        matched_scale_height_cm=reference * root_factor,
        matched_to_reference_scale_height=root_factor,
        lower_bracket_factor=lower_factor,
        upper_bracket_factor=upper_factor,
        root_function_evaluations=len(cache),
        column=column,
        dissipation=dissipation,
        diffusion=diffusion,
        support_audit=audit,
    )


def _outward_surface_fluxes_erg_s_cm2(
    slab: EmissiveCoupledSlab,
) -> tuple[float, float]:
    transfer = slab.transfer
    mu = transfer.direction_cosine
    weight = transfer.angular_weight
    top_outward = mu < 0.0
    bottom_outward = mu > 0.0
    top_fnu = -2.0 * np.pi * np.einsum(
        "m,fm,m->f",
        weight[top_outward],
        transfer.top_boundary_intensity[:, top_outward],
        mu[top_outward],
    )
    bottom_fnu = 2.0 * np.pi * np.einsum(
        "m,fm,m->f",
        weight[bottom_outward],
        transfer.bottom_boundary_intensity[:, bottom_outward],
        mu[bottom_outward],
    )
    return (
        float(np.trapezoid(top_fnu, transfer.frequency_hz)),
        float(np.trapezoid(bottom_fnu, transfer.frequency_hz)),
    )


def audit_zo_n3_hydrostatic_pressure(
    column: ZOConstrainedN3Column,
    slab: EmissiveCoupledSlab,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> HydrostaticPressureAudit:
    """比较求解后的气体加辐射压力与 ZO n=3 所需支撑压力。"""
    if slab.temperature_k.shape != (column.full_depth_points,):
        raise PhysicalDomainError("slab depth does not match the hydrostatic column")
    density = column.full_density_g_cm3
    hydrogen_nuclei = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium_nuclei = composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    gas = BOLTZMANN_ERG_K * slab.temperature_k * (
        hydrogen_nuclei + helium_nuclei + slab.population.electron_density_cm3
    )
    transfer = slab.transfer
    radiation_nu = 2.0 * np.pi / LIGHT_SPEED_CM_S * np.einsum(
        "m,fmz,m->fz",
        transfer.angular_weight,
        transfer.intensity_cell_average,
        transfer.direction_cosine**2,
    )
    radiation = np.trapezoid(radiation_nu, transfer.frequency_hz, axis=0)
    total = gas + radiation
    required = column.required_support_pressure_erg_cm3
    cell_mass = column.full_cell_mass_g_cm2
    difference = total - required
    l1 = float(np.sum(cell_mass * np.abs(difference)) / np.sum(cell_mass * required))
    rms = float(
        np.sqrt(
            np.sum(cell_mass * difference**2)
            / np.sum(cell_mass * required**2)
        )
    )
    maximum = float(np.max(np.abs(difference)) / column.central_support_pressure_erg_cm3)

    flux_nu = 2.0 * np.pi * np.einsum(
        "m,fmz,m->fz",
        transfer.angular_weight,
        transfer.intensity_cell_average,
        transfer.direction_cosine,
    )
    force_per_volume = np.trapezoid(
        slab.continuum.extinction_total_per_cm * flux_nu,
        transfer.frequency_hz,
        axis=0,
    ) / LIGHT_SPEED_CM_S
    count = column.half_depth_points
    outward_radiative_acceleration = -force_per_volume[:count] / density[:count]
    gravity_acceleration = (
        column.gravity_coefficient_s2 * column.full_signed_height_cm[:count]
    )
    acceleration_ratio = float(
        np.max(outward_radiative_acceleration / gravity_acceleration)
    )
    top_flux, bottom_flux = _outward_surface_fluxes_erg_s_cm2(slab)
    flux_scale = max(abs(top_flux), abs(bottom_flux))
    flux_asymmetry = (
        abs(top_flux - bottom_flux) / flux_scale
        if flux_scale > 0.0
        else abs(top_flux - bottom_flux)
    )
    temperature_mirror = float(
        np.max(
            np.abs(slab.temperature_k[:count] - slab.temperature_k[: count - 1 : -1])
            / slab.temperature_k[:count]
        )
    )
    density_mirror = float(
        np.max(
            np.abs(density[:count] - density[: count - 1 : -1])
            / density[:count]
        )
    )
    arrays = (gas, radiation, total, required)
    if not all(np.all(np.isfinite(array)) and np.all(array >= 0.0) for array in arrays):
        raise ArithmeticError("hydrostatic pressure audit became invalid")
    return HydrostaticPressureAudit(
        gas_pressure_erg_cm3=_readonly(np.array(gas, copy=True)),
        radiation_pressure_erg_cm3=_readonly(np.array(radiation, copy=True)),
        total_pressure_erg_cm3=_readonly(np.array(total, copy=True)),
        required_support_pressure_erg_cm3=_readonly(np.array(required, copy=True)),
        mass_weighted_relative_l1_pressure_residual=l1,
        mass_weighted_relative_rms_pressure_residual=rms,
        maximum_pressure_residual_over_central_support=maximum,
        top_half_maximum_radiative_to_gravity_acceleration=acceleration_ratio,
        top_surface_flux_erg_s_cm2=top_flux,
        bottom_surface_flux_erg_s_cm2=bottom_flux,
        relative_surface_flux_asymmetry=float(flux_asymmetry),
        maximum_temperature_mirror_residual=temperature_mirror,
        maximum_density_mirror_residual=density_mirror,
    )


def one_face_flux_from_effective_temperature_erg_s_cm2(
    effective_temperature_k: float,
) -> float:
    """返回单面 ``sigma_SB T_eff^4``，供大气耗散控制使用。"""
    temperature = float(effective_temperature_k)
    if not np.isfinite(temperature) or temperature <= 0.0:
        raise PhysicalDomainError("effective_temperature_k must be finite and positive")
    return float(STEFAN_BOLTZMANN_ERG_S_CM2_K4 * temperature**4)
