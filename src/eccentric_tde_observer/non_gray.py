"""低温 H/He LTE 非灰连续吸收审计。

本模块只回答“给定 ZO 柱在某频率能否热化”。它不求解辐射平衡、
NLTE 统计平衡或金属线空白，因此不能单独生成可信的 X-ray 光谱。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .atmosphere import (
    FREE_FREE_COEFFICIENT_CGS,
    PROTON_MASS_G,
    SOLAR_FULLY_IONIZED_H_HE,
    THOMSON_CROSS_SECTION_CM2,
    FullyIonizedHydrogenHeliumComposition,
)
from .radiation import BOLTZMANN_ERG_K, PLANCK_ERG_S
from .source import PhysicalDomainError, ZOSourceGrid
from .vertical import (
    RADIATION_PRESSURE_POLYTROPE_PROFILE,
    RadiationPressurePolytropeProfile,
)


ELECTRON_MASS_G = 9.1093837139e-28
EV_ERG = 1.602176634e-12
HYDROGEN_IONIZATION_ERG = 13.59843449 * EV_ERG
HELIUM_I_IONIZATION_ERG = 24.587389 * EV_ERG
HELIUM_II_IONIZATION_ERG = 54.417765 * EV_ERG
HYDROGEN_THRESHOLD_CROSS_SECTION_CM2 = 6.30e-18
HELIUM_I_APPROX_THRESHOLD_CROSS_SECTION_CM2 = 7.83e-18
HELIUM_II_THRESHOLD_CROSS_SECTION_CM2 = (
    HYDROGEN_THRESHOLD_CROSS_SECTION_CM2 / 4.0
)


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


def _validate_thermodynamic_arrays(
    density_g_cm3: ArrayLike, temperature_k: ArrayLike
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    density, temperature = np.broadcast_arrays(
        np.asarray(density_g_cm3, dtype=np.float64),
        np.asarray(temperature_k, dtype=np.float64),
    )
    if not np.all(np.isfinite(density)) or np.any(density <= 0.0):
        raise PhysicalDomainError("density_g_cm3 must be finite and strictly positive")
    if not np.all(np.isfinite(temperature)) or np.any(temperature <= 0.0):
        raise PhysicalDomainError("temperature_k must be finite and strictly positive")
    return density, temperature


@dataclass(frozen=True)
class LTEIonizationState:
    """Saha 平衡下的 H/He 数密度与电离分数。"""

    electron_density_cm3: NDArray[np.float64]
    hydrogen_neutral_fraction: NDArray[np.float64]
    hydrogen_ionized_fraction: NDArray[np.float64]
    helium_neutral_fraction: NDArray[np.float64]
    helium_singly_ionized_fraction: NDArray[np.float64]
    helium_doubly_ionized_fraction: NDArray[np.float64]


def _saha_factor_cm3(temperature_k: NDArray[np.float64], energy_erg: float) -> NDArray[np.float64]:
    # 中文：统计权重统一取 2；这是基态连续谱近似，不是完整配分函数。
    prefactor = 2.0 * (
        2.0 * np.pi * ELECTRON_MASS_G * BOLTZMANN_ERG_K * temperature_k
        / PLANCK_ERG_S**2
    ) ** 1.5
    return prefactor * np.exp(-energy_erg / (BOLTZMANN_ERG_K * temperature_k))


def lte_hydrogen_helium_ionization(
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> LTEIonizationState:
    """Solve charge-neutral H/He Saha equilibrium by bracketed bisection.

    The root is never repaired with a floor.  A completely neutral analytic
    branch is used only when every Saha factor underflows exactly to zero.
    """
    density, temperature = _validate_thermodynamic_arrays(
        density_g_cm3, temperature_k
    )
    hydrogen_nuclei = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium_nuclei = (
        composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    )
    maximum_electrons = hydrogen_nuclei + 2.0 * helium_nuclei
    if np.any(maximum_electrons <= 0.0):
        raise PhysicalDomainError("H/He composition must contain ionizable material")

    saha_h = _saha_factor_cm3(temperature, HYDROGEN_IONIZATION_ERG)
    saha_he1 = _saha_factor_cm3(temperature, HELIUM_I_IONIZATION_ERG)
    saha_he2 = _saha_factor_cm3(temperature, HELIUM_II_IONIZATION_ERG)
    all_neutral = (saha_h == 0.0) & (saha_he1 == 0.0) & (saha_he2 == 0.0)

    lower = np.zeros_like(maximum_electrons)
    upper = np.array(maximum_electrons, copy=True)
    # 中文：电荷守恒方程单调，固定 96 次二分给出远优于双精度需求的括区间。
    for _ in range(96):
        electron = 0.5 * (lower + upper)
        ratio_h = saha_h / electron
        hydrogen_ionized = ratio_h / (1.0 + ratio_h)
        ratio_he1 = saha_he1 / electron
        ratio_he2 = saha_he2 / electron
        helium_denominator = 1.0 + ratio_he1 + ratio_he1 * ratio_he2
        helium_singly = ratio_he1 / helium_denominator
        helium_doubly = ratio_he1 * ratio_he2 / helium_denominator
        charge = hydrogen_nuclei * hydrogen_ionized + helium_nuclei * (
            helium_singly + 2.0 * helium_doubly
        )
        positive_residual = electron > charge
        upper = np.where(positive_residual, electron, upper)
        lower = np.where(positive_residual, lower, electron)

    electron = 0.5 * (lower + upper)
    electron = np.where(all_neutral, 0.0, electron)
    safe_electron = np.where(all_neutral, 1.0, electron)
    ratio_h = saha_h / safe_electron
    hydrogen_ionized = ratio_h / (1.0 + ratio_h)
    ratio_he1 = saha_he1 / safe_electron
    ratio_he2 = saha_he2 / safe_electron
    helium_denominator = 1.0 + ratio_he1 + ratio_he1 * ratio_he2
    helium_neutral = 1.0 / helium_denominator
    helium_singly = ratio_he1 / helium_denominator
    helium_doubly = ratio_he1 * ratio_he2 / helium_denominator
    hydrogen_ionized = np.where(all_neutral, 0.0, hydrogen_ionized)
    helium_neutral = np.where(all_neutral, 1.0, helium_neutral)
    helium_singly = np.where(all_neutral, 0.0, helium_singly)
    helium_doubly = np.where(all_neutral, 0.0, helium_doubly)

    hydrogen_neutral = 1.0 - hydrogen_ionized
    arrays = (
        electron,
        hydrogen_neutral,
        hydrogen_ionized,
        helium_neutral,
        helium_singly,
        helium_doubly,
    )
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ArithmeticError("Saha ionization solution became non-finite")
    return LTEIonizationState(*(_readonly(np.asarray(array)) for array in arrays))


@dataclass(frozen=True)
class LTENonGrayOpacity:
    """H/He LTE 连续谱的质量不透明度分解。"""

    free_free_cm2_g: NDArray[np.float64]
    hydrogen_i_bound_free_cm2_g: NDArray[np.float64]
    helium_i_bound_free_approx_cm2_g: NDArray[np.float64]
    helium_ii_bound_free_cm2_g: NDArray[np.float64]
    absorption_total_cm2_g: NDArray[np.float64]
    electron_scattering_cm2_g: NDArray[np.float64]
    includes_helium_i_approximation: bool


def _threshold_cross_section(
    frequency_hz: NDArray[np.float64], threshold_erg: float, cross_section_cm2: float
) -> NDArray[np.float64]:
    threshold_hz = threshold_erg / PLANCK_ERG_S
    above = frequency_hz >= threshold_hz
    result = np.zeros_like(frequency_hz)
    result[above] = cross_section_cm2 * (threshold_hz / frequency_hz[above]) ** 3
    return result


def lte_non_gray_continuum_opacity_cm2_g(
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    frequency_hz: ArrayLike,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
    include_helium_i_approximation: bool = False,
) -> LTENonGrayOpacity:
    """Evaluate LTE free-free, bound-free and electron-scattering opacity.

    H I and He II use hydrogenic threshold cross sections proportional to
    ``nu^-3``.  He I is non-hydrogenic and is disabled by default; enabling it
    is an explicit sensitivity calculation, not an atomic-data replacement.
    """
    density, temperature = _validate_thermodynamic_arrays(
        density_g_cm3, temperature_k
    )
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    if not np.all(np.isfinite(frequency)) or np.any(frequency <= 0.0):
        raise PhysicalDomainError("frequency_hz must be finite and strictly positive")
    density, temperature, frequency = np.broadcast_arrays(
        density, temperature, frequency
    )
    ionization = lte_hydrogen_helium_ionization(density, temperature, composition)
    hydrogen_nuclei = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium_nuclei = (
        composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    )
    hydrogen_neutral = hydrogen_nuclei * ionization.hydrogen_neutral_fraction
    hydrogen_ionized = hydrogen_nuclei * ionization.hydrogen_ionized_fraction
    helium_neutral = helium_nuclei * ionization.helium_neutral_fraction
    helium_singly = helium_nuclei * ionization.helium_singly_ionized_fraction
    helium_doubly = helium_nuclei * ionization.helium_doubly_ionized_fraction

    exponent = PLANCK_ERG_S * frequency / (BOLTZMANN_ERG_K * temperature)
    stimulated = -np.expm1(-exponent)
    charge_squared_ions = hydrogen_ionized + helium_singly + 4.0 * helium_doubly
    free_free = (
        FREE_FREE_COEFFICIENT_CGS
        * composition.free_free_gaunt_factor
        * temperature ** (-0.5)
        * ionization.electron_density_cm3
        * charge_squared_ions
        * frequency ** (-3.0)
        * stimulated
        / density
    )
    hydrogen_i = (
        hydrogen_neutral
        * _threshold_cross_section(
            frequency, HYDROGEN_IONIZATION_ERG, HYDROGEN_THRESHOLD_CROSS_SECTION_CM2
        )
        * stimulated
        / density
    )
    helium_ii = (
        helium_singly
        * _threshold_cross_section(
            frequency, HELIUM_II_IONIZATION_ERG, HELIUM_II_THRESHOLD_CROSS_SECTION_CM2
        )
        * stimulated
        / density
    )
    if include_helium_i_approximation:
        helium_i = (
            helium_neutral
            * _threshold_cross_section(
                frequency,
                HELIUM_I_IONIZATION_ERG,
                HELIUM_I_APPROX_THRESHOLD_CROSS_SECTION_CM2,
            )
            * stimulated
            / density
        )
    else:
        helium_i = np.zeros_like(frequency)
    scattering = THOMSON_CROSS_SECTION_CM2 * ionization.electron_density_cm3 / density
    total = free_free + hydrogen_i + helium_i + helium_ii
    arrays = (free_free, hydrogen_i, helium_i, helium_ii, total, scattering)
    if not all(np.all(np.isfinite(array)) and np.all(array >= 0.0) for array in arrays):
        raise ArithmeticError("LTE non-gray opacity evaluation became invalid")
    return LTENonGrayOpacity(
        *(_readonly(np.asarray(array)) for array in arrays),
        includes_helium_i_approximation=bool(include_helium_i_approximation),
    )


@dataclass(frozen=True)
class LTENonGrayOpticalDepthAudit:
    """从上表面到中面的频率分辨有效光深。"""

    frequency_hz: NDArray[np.float64]
    midplane_effective_optical_depth: NDArray[np.float64]
    target_effective_optical_depth: float
    vertical_points: int
    includes_helium_i_approximation: bool
    closure_label: str = "LTE H/He continuum audit; not NLTE atmosphere"

    @property
    def effectively_thick_mask(self) -> NDArray[np.bool_]:
        return _readonly(
            self.midplane_effective_optical_depth
            >= self.target_effective_optical_depth
        )


def lte_non_gray_effective_optical_depth_to_midplane(
    source: ZOSourceGrid,
    frequency_hz: ArrayLike,
    *,
    target_effective_optical_depth: float = 1.0,
    reference_gray_scattering_opacity_cm2_g: float = 0.34,
    profile: RadiationPressurePolytropeProfile = RADIATION_PRESSURE_POLYTROPE_PROFILE,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
    include_helium_i_approximation: bool = False,
    vertical_points: int = 129,
    chunk_size: int = 128,
) -> LTENonGrayOpticalDepthAudit:
    """Audit non-gray thermalization while retaining the Phase-2 gray T(z).

    The gray Eddington temperature is deliberately retained as an input
    closure.  Replacing it requires solving non-gray radiative equilibrium and
    is therefore outside this LTE opacity audit.
    """
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    if frequency.ndim != 1 or frequency.size == 0:
        raise PhysicalDomainError("frequency_hz must be a non-empty 1D grid")
    if not np.all(np.isfinite(frequency)) or np.any(frequency <= 0.0):
        raise PhysicalDomainError("frequency_hz must be finite and positive")
    if np.any(np.diff(frequency) <= 0.0):
        raise PhysicalDomainError("frequency_hz must be strictly increasing")
    target = float(target_effective_optical_depth)
    reference_scattering = float(reference_gray_scattering_opacity_cm2_g)
    if not np.isfinite(target) or target <= 0.0:
        raise PhysicalDomainError("target_effective_optical_depth must be positive")
    if not np.isfinite(reference_scattering) or reference_scattering <= 0.0:
        raise PhysicalDomainError("reference gray opacity must be positive")
    if not isinstance(vertical_points, (int, np.integer)) or int(vertical_points) < 33:
        raise PhysicalDomainError("vertical_points must be an integer at least 33")
    if not isinstance(chunk_size, (int, np.integer)) or int(chunk_size) < 1:
        raise PhysicalDomainError("chunk_size must be a positive integer")

    scaled_height = np.linspace(float(profile.surface_scaled_height), 0.0, int(vertical_points))
    density_shape = profile.density_shape(scaled_height)
    upper_fraction = profile.upper_column_fraction(scaled_height)
    flat_sigma = source.surface_density_g_cm2.reshape(-1)
    flat_height = source.scale_height_cm.reshape(-1)
    flat_teff = source.effective_temperature_k.reshape(-1)
    result = np.empty((flat_sigma.size, frequency.size), dtype=np.float64)

    for start in range(0, flat_sigma.size, int(chunk_size)):
        stop = min(flat_sigma.size, start + int(chunk_size))
        sigma = flat_sigma[start:stop, None]
        height = flat_height[start:stop, None]
        density = sigma / height * density_shape[None, :]
        gray_scattering_depth = (
            reference_scattering * sigma * upper_fraction[None, :]
        )
        # 中文：这里只审计 opacity；温度结构仍是阶段 2 的灰 Eddington 新闭合。
        temperature = flat_teff[start:stop, None] * (
            0.75 * (gray_scattering_depth + 2.0 / 3.0)
        ) ** 0.25
        # 中文：有限支撑多项式表面恰有 rho=0；该端点的体消光严格为 0，
        # 只在正密度内点计算质量不透明度，避免给真空指定无定义的 kappa。
        opacity = lte_non_gray_continuum_opacity_cm2_g(
            density[:, 1:, None],
            temperature[:, 1:, None],
            frequency[None, None, :],
            composition=composition,
            include_helium_i_approximation=include_helium_i_approximation,
        )
        interior_integrand = (
            height[:, :, None]
            * density[:, 1:, None]
            * np.sqrt(
                3.0
                * opacity.absorption_total_cm2_g
                * (
                    opacity.absorption_total_cm2_g
                    + opacity.electron_scattering_cm2_g
                )
            )
        )
        integrand = np.zeros(
            (stop - start, int(vertical_points), frequency.size), dtype=np.float64
        )
        integrand[:, 1:, :] = interior_integrand
        result[start:stop] = np.trapezoid(integrand, -scaled_height, axis=1)

    if not np.all(np.isfinite(result)) or np.any(result < 0.0):
        raise ArithmeticError("LTE non-gray optical-depth integration failed")
    return LTENonGrayOpticalDepthAudit(
        frequency_hz=_readonly(frequency),
        midplane_effective_optical_depth=_readonly(
            result.reshape(source.shape + (frequency.size,))
        ),
        target_effective_optical_depth=target,
        vertical_points=int(vertical_points),
        includes_helium_i_approximation=bool(include_helium_i_approximation),
    )
