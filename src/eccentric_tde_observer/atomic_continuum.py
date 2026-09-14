"""可追溯的基态 H/He 连续谱原子率与 LTE opacity 控制。

本模块提供 Verner 等（1996）的基态光致电离截面、Verner & Ferland
（1996）的总辐射复合率，以及固定辐射场下的最小电离平衡。它不含激发
能级、碰撞过程、线跃迁或能量方程，因此不是完整 NLTE 原子模型。
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
from .non_gray import ELECTRON_MASS_G, lte_hydrogen_helium_ionization
from .radiation import BOLTZMANN_ERG_K, PLANCK_ERG_S
from .source import PhysicalDomainError


EV_ERG = 1.602176634e-12
MEGABARN_CM2 = 1.0e-18


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class VernerPhotoionizationFit:
    """Verner 等（1996）基态总光致电离截面拟合参数。"""

    ion_label: str
    atomic_number: int
    electron_number: int
    threshold_energy_ev: float
    maximum_energy_ev: float
    energy_scale_ev: float
    cross_section_scale_mb: float
    y_a: float
    exponent_p: float
    y_w: float
    y_0: float
    y_1: float

    def cross_section_cm2(self, photon_energy_ev: ArrayLike) -> NDArray[np.float64]:
        """返回拟合有效域内的基态光致电离截面。"""
        energy = np.asarray(photon_energy_ev, dtype=np.float64)
        if not np.all(np.isfinite(energy)) or np.any(energy <= 0.0):
            raise PhysicalDomainError(
                "photon_energy_ev must be finite and strictly positive"
            )
        if np.any(energy > self.maximum_energy_ev):
            raise PhysicalDomainError(
                f"{self.ion_label} Verner fit is tabulated only through "
                f"{self.maximum_energy_ev:g} eV"
            )
        result = np.zeros_like(energy)
        active = energy >= self.threshold_energy_ev
        x = energy[active] / self.energy_scale_ev - self.y_0
        y = np.sqrt(x**2 + self.y_1**2)
        shape = (
            ((x - 1.0) ** 2 + self.y_w**2)
            * y ** (0.5 * self.exponent_p - 5.5)
            * (1.0 + np.sqrt(y / self.y_a)) ** (-self.exponent_p)
        )
        result[active] = self.cross_section_scale_mb * MEGABARN_CM2 * shape
        if not np.all(np.isfinite(result)) or np.any(result < 0.0):
            raise ArithmeticError(
                f"{self.ion_label} photoionization cross section became invalid"
            )
        return _readonly(result)


# 中文：参数逐项抄录自作者发布的 photo.dat 前三行，不再用 He I 的氢样近似。
H_I_VERNER_FIT = VernerPhotoionizationFit(
    "H I", 1, 1, 13.60, 5.0e4, 0.4298, 5.475e4, 32.88, 2.963, 0.0, 0.0, 0.0
)
HE_I_VERNER_FIT = VernerPhotoionizationFit(
    "He I", 2, 2, 24.59, 5.0e4, 13.61, 949.2, 1.469, 3.188, 2.039, 0.4434, 2.136
)
HE_II_VERNER_FIT = VernerPhotoionizationFit(
    "He II", 2, 1, 54.42, 5.0e4, 1.720, 1.369e4, 32.88, 2.963, 0.0, 0.0, 0.0
)
H_HE_GROUND_STATE_PHOTOIONIZATION_FITS = (
    H_I_VERNER_FIT,
    HE_I_VERNER_FIT,
    HE_II_VERNER_FIT,
)


@dataclass(frozen=True)
class VernerFerlandRecombinationFit:
    """Verner & Ferland（1996）总辐射复合率拟合。"""

    product_ion_label: str
    coefficient_a_cm3_s: float
    exponent_b: float
    temperature_0_k: float
    temperature_1_k: float
    minimum_temperature_k: float
    maximum_temperature_k: float
    fit_note: str

    def coefficient_cm3_s(self, temperature_k: ArrayLike) -> NDArray[np.float64]:
        temperature = np.asarray(temperature_k, dtype=np.float64)
        if not np.all(np.isfinite(temperature)) or np.any(temperature <= 0.0):
            raise PhysicalDomainError(
                "temperature_k must be finite and strictly positive"
            )
        if np.any(temperature < self.minimum_temperature_k) or np.any(
            temperature > self.maximum_temperature_k
        ):
            raise PhysicalDomainError(
                f"{self.product_ion_label} recombination fit is valid only over "
                f"[{self.minimum_temperature_k:g}, {self.maximum_temperature_k:g}] K"
            )
        root_0 = np.sqrt(temperature / self.temperature_0_k)
        root_1 = np.sqrt(temperature / self.temperature_1_k)
        denominator = (
            root_0
            * (1.0 + root_0) ** (1.0 - self.exponent_b)
            * (1.0 + root_1) ** (1.0 + self.exponent_b)
        )
        coefficient = self.coefficient_a_cm3_s / denominator
        if not np.all(np.isfinite(coefficient)) or np.any(coefficient <= 0.0):
            raise ArithmeticError(
                f"{self.product_ion_label} recombination coefficient became invalid"
            )
        return _readonly(coefficient)


H_I_RECOMBINATION_FIT = VernerFerlandRecombinationFit(
    "H I", 7.982e-11, 0.7480, 3.148, 7.036e5, 3.0, 1.0e9,
    "total radiative recombination H II -> H I",
)
HE_I_RECOMBINATION_FIT = VernerFerlandRecombinationFit(
    "He I", 3.294e-11, 0.6910, 15.54, 3.676e7, 3.0, 1.0e6,
    "low-temperature He I branch; rms fit error 2.5 percent",
)
HE_I_WIDE_RECOMBINATION_FIT = VernerFerlandRecombinationFit(
    "He I wide", 9.356e-10, 0.7892, 0.04266, 4.677e6, 3.0, 1.0e9,
    "wide-temperature He I branch; rms fit error 4.7 percent",
)
HE_II_RECOMBINATION_FIT = VernerFerlandRecombinationFit(
    "He II", 1.891e-10, 0.7524, 9.370, 2.774e6, 3.0, 1.0e9,
    "total radiative recombination He III -> He II",
)


def integrate_photoionization_rate_s1(
    frequency_hz: ArrayLike,
    mean_intensity_cgs: ArrayLike,
    cross_section_cm2: ArrayLike,
) -> float:
    """计算每个靶粒子的光致电离率 ``4*pi*int sigma*J/(h*nu)dnu``。"""
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    intensity = np.asarray(mean_intensity_cgs, dtype=np.float64)
    cross_section = np.asarray(cross_section_cm2, dtype=np.float64)
    if frequency.ndim != 1 or frequency.size < 2:
        raise PhysicalDomainError("frequency_hz must be a 1D grid with at least two points")
    if intensity.shape != frequency.shape or cross_section.shape != frequency.shape:
        raise PhysicalDomainError(
            "mean_intensity_cgs and cross_section_cm2 must match frequency_hz"
        )
    if (
        not np.all(np.isfinite(frequency))
        or np.any(frequency <= 0.0)
        or np.any(np.diff(frequency) <= 0.0)
    ):
        raise PhysicalDomainError(
            "frequency_hz must be finite, positive and strictly increasing"
        )
    for name, values in (
        ("mean_intensity_cgs", intensity),
        ("cross_section_cm2", cross_section),
    ):
        if not np.all(np.isfinite(values)) or np.any(values < 0.0):
            raise PhysicalDomainError(f"{name} must be finite and non-negative")
    integrand = 4.0 * np.pi * cross_section * intensity / (PLANCK_ERG_S * frequency)
    rate = float(np.trapezoid(integrand, frequency))
    if not np.isfinite(rate) or rate < 0.0:
        raise ArithmeticError("photoionization-rate integral became invalid")
    return rate


def photoionization_rate_from_fit_s1(
    frequency_hz: ArrayLike,
    mean_intensity_cgs: ArrayLike,
    fit: VernerPhotoionizationFit,
) -> float:
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    intensity = np.asarray(mean_intensity_cgs, dtype=np.float64)
    if frequency.ndim != 1 or intensity.shape != frequency.shape:
        raise PhysicalDomainError(
            "frequency_hz and mean_intensity_cgs must be matching 1D arrays"
        )
    threshold_hz = fit.threshold_energy_ev * EV_ERG / PLANCK_ERG_S
    active = frequency >= threshold_hz
    if np.count_nonzero(active) < 2:
        raise PhysicalDomainError(
            f"frequency grid needs at least two points at or above the {fit.ion_label} edge"
        )
    active_frequency = frequency[active]
    energy_ev = PLANCK_ERG_S * active_frequency / EV_ERG
    # 中文：乘除回算可能把解析阈值降一个舍入单位；仅把同一阈值频率恢复为表值。
    exact_edge = active_frequency == threshold_hz
    energy_ev[exact_edge] = fit.threshold_energy_ev
    cross_section = fit.cross_section_cm2(energy_ev)
    return integrate_photoionization_rate_s1(
        active_frequency, intensity[active], cross_section
    )


def ground_state_saha_factor_cm3(
    temperature_k: ArrayLike,
    ionization_energy_ev: float,
    *,
    statistical_weight_ratio: float = 2.0,
) -> NDArray[np.float64]:
    """返回指定统计权重比的基态 Saha 因子。"""
    temperature = np.asarray(temperature_k, dtype=np.float64)
    energy = float(ionization_energy_ev)
    weight = float(statistical_weight_ratio)
    if not np.all(np.isfinite(temperature)) or np.any(temperature <= 0.0):
        raise PhysicalDomainError("temperature_k must be finite and strictly positive")
    if not np.isfinite(energy) or energy <= 0.0 or not np.isfinite(weight) or weight <= 0.0:
        raise PhysicalDomainError("ionization energy and statistical weight ratio must be positive")
    factor = weight * (
        2.0 * np.pi * ELECTRON_MASS_G * BOLTZMANN_ERG_K * temperature
        / PLANCK_ERG_S**2
    ) ** 1.5 * np.exp(-energy * EV_ERG / (BOLTZMANN_ERG_K * temperature))
    if not np.all(np.isfinite(factor)) or np.any(factor < 0.0):
        raise ArithmeticError("Saha factor became invalid")
    return _readonly(factor)


def detailed_balance_recombination_coefficient_cm3_s(
    photoionization_rate_s1: ArrayLike,
    saha_factor_cm3: ArrayLike,
) -> NDArray[np.float64]:
    """构造仅用于 LTE 详细平衡控制的逆率，不替代文献复合率。"""
    rate, saha = np.broadcast_arrays(
        np.asarray(photoionization_rate_s1, dtype=np.float64),
        np.asarray(saha_factor_cm3, dtype=np.float64),
    )
    if not np.all(np.isfinite(rate)) or np.any(rate < 0.0):
        raise PhysicalDomainError("photoionization_rate_s1 must be finite and non-negative")
    if not np.all(np.isfinite(saha)) or np.any(saha <= 0.0):
        raise PhysicalDomainError("saha_factor_cm3 must be finite and strictly positive")
    coefficient = rate / saha
    return _readonly(coefficient)


@dataclass(frozen=True)
class PhotoionizationEquilibriumState:
    """仅含光致电离与辐射复合的 H/He 稳态。"""

    electron_density_cm3: NDArray[np.float64]
    hydrogen_neutral_fraction: NDArray[np.float64]
    hydrogen_ionized_fraction: NDArray[np.float64]
    helium_neutral_fraction: NDArray[np.float64]
    helium_singly_ionized_fraction: NDArray[np.float64]
    helium_doubly_ionized_fraction: NDArray[np.float64]
    maximum_charge_residual_cm3: float


def photoionization_recombination_equilibrium(
    hydrogen_nuclei_cm3: ArrayLike,
    helium_nuclei_cm3: ArrayLike,
    hydrogen_i_photoionization_rate_s1: ArrayLike,
    helium_i_photoionization_rate_s1: ArrayLike,
    helium_ii_photoionization_rate_s1: ArrayLike,
    hydrogen_i_recombination_cm3_s: ArrayLike,
    helium_i_recombination_cm3_s: ArrayLike,
    helium_ii_recombination_cm3_s: ArrayLike,
) -> PhotoionizationEquilibriumState:
    """解电荷中性 H I/H II 与 He I/He II/He III 稳态。"""
    arrays = np.broadcast_arrays(
        *(
            np.asarray(value, dtype=np.float64)
            for value in (
                hydrogen_nuclei_cm3,
                helium_nuclei_cm3,
                hydrogen_i_photoionization_rate_s1,
                helium_i_photoionization_rate_s1,
                helium_ii_photoionization_rate_s1,
                hydrogen_i_recombination_cm3_s,
                helium_i_recombination_cm3_s,
                helium_ii_recombination_cm3_s,
            )
        )
    )
    hydrogen, helium, gamma_h, gamma_he1, gamma_he2, alpha_h, alpha_he1, alpha_he2 = arrays
    if any(not np.all(np.isfinite(value)) for value in arrays):
        raise PhysicalDomainError("photoionization-equilibrium inputs must be finite")
    if np.any(hydrogen < 0.0) or np.any(helium < 0.0) or np.any(hydrogen + helium <= 0.0):
        raise PhysicalDomainError("H/He nuclei densities must be non-negative with positive total")
    if any(np.any(value < 0.0) for value in (gamma_h, gamma_he1, gamma_he2)):
        raise PhysicalDomainError("photoionization rates must be non-negative")
    if any(np.any(value <= 0.0) for value in (alpha_h, alpha_he1, alpha_he2)):
        raise PhysicalDomainError("recombination coefficients must be strictly positive")

    all_neutral = (gamma_h == 0.0) & (gamma_he1 == 0.0)
    maximum_electrons = hydrogen + 2.0 * helium
    lower = np.zeros_like(maximum_electrons)
    upper = maximum_electrons.copy()

    def fractions(electron: NDArray[np.float64]):
        h_ionized = gamma_h / (gamma_h + electron * alpha_h)
        he_rec1 = electron * alpha_he1
        he_rec2 = electron * alpha_he2
        scale = np.maximum.reduce((he_rec1, he_rec2, gamma_he1, gamma_he2))
        safe_scale = np.where(scale == 0.0, 1.0, scale)
        a = he_rec1 / safe_scale
        b = he_rec2 / safe_scale
        g1 = gamma_he1 / safe_scale
        g2 = gamma_he2 / safe_scale
        denominator = a * b + g1 * b + g1 * g2
        safe_denominator = np.where(denominator == 0.0, 1.0, denominator)
        he_neutral = a * b / safe_denominator
        he_singly = g1 * b / safe_denominator
        he_doubly = g1 * g2 / safe_denominator
        neutral_branch = denominator == 0.0
        he_neutral = np.where(neutral_branch, 1.0, he_neutral)
        he_singly = np.where(neutral_branch, 0.0, he_singly)
        he_doubly = np.where(neutral_branch, 0.0, he_doubly)
        return h_ionized, he_neutral, he_singly, he_doubly

    # 中文：电荷残差单调；解析全中性分支之外始终在物理解区间内二分。
    for _ in range(128):
        electron = 0.5 * (lower + upper)
        h_ionized, _, he_singly, he_doubly = fractions(electron)
        charge = hydrogen * h_ionized + helium * (he_singly + 2.0 * he_doubly)
        positive = electron > charge
        upper = np.where(positive, electron, upper)
        lower = np.where(positive, lower, electron)
    electron = np.where(all_neutral, 0.0, 0.5 * (lower + upper))
    safe_electron = np.where(all_neutral, 1.0, electron)
    h_ionized, he_neutral, he_singly, he_doubly = fractions(safe_electron)
    h_ionized = np.where(all_neutral, 0.0, h_ionized)
    he_neutral = np.where(all_neutral, 1.0, he_neutral)
    he_singly = np.where(all_neutral, 0.0, he_singly)
    he_doubly = np.where(all_neutral, 0.0, he_doubly)
    h_neutral = 1.0 - h_ionized
    charge = hydrogen * h_ionized + helium * (he_singly + 2.0 * he_doubly)
    residual = float(np.max(np.abs(electron - charge)))
    output = (electron, h_neutral, h_ionized, he_neutral, he_singly, he_doubly)
    if not all(np.all(np.isfinite(value)) for value in output):
        raise ArithmeticError("photoionization equilibrium became non-finite")
    if any(np.any(value < 0.0) or np.any(value > 1.0) for value in output[1:]):
        raise ArithmeticError("photoionization equilibrium produced invalid fractions")
    return PhotoionizationEquilibriumState(
        *(_readonly(np.asarray(value)) for value in output),
        maximum_charge_residual_cm3=residual,
    )


@dataclass(frozen=True)
class TraceableLTEContinuumOpacity:
    """采用 Verner 基态截面的 H/He LTE 连续谱质量不透明度。"""

    free_free_cm2_g: NDArray[np.float64]
    hydrogen_i_bound_free_cm2_g: NDArray[np.float64]
    helium_i_bound_free_cm2_g: NDArray[np.float64]
    helium_ii_bound_free_cm2_g: NDArray[np.float64]
    absorption_total_cm2_g: NDArray[np.float64]
    electron_scattering_cm2_g: NDArray[np.float64]


def traceable_lte_h_he_continuum_opacity_cm2_g(
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    frequency_hz: ArrayLike,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> TraceableLTEContinuumOpacity:
    """计算带 Verner H I、He I、He II 基态截面的 LTE 连续 opacity。"""
    density, temperature, frequency = np.broadcast_arrays(
        np.asarray(density_g_cm3, dtype=np.float64),
        np.asarray(temperature_k, dtype=np.float64),
        np.asarray(frequency_hz, dtype=np.float64),
    )
    if not np.all(np.isfinite(density)) or np.any(density <= 0.0):
        raise PhysicalDomainError("density_g_cm3 must be finite and strictly positive")
    for name, value in (("temperature_k", temperature), ("frequency_hz", frequency)):
        if not np.all(np.isfinite(value)) or np.any(value <= 0.0):
            raise PhysicalDomainError(f"{name} must be finite and strictly positive")
    energy_ev = PLANCK_ERG_S * frequency / EV_ERG
    if np.any(energy_ev > H_I_VERNER_FIT.maximum_energy_ev):
        raise PhysicalDomainError("frequency grid exceeds the 50 keV H/He fit limit")
    ionization = lte_hydrogen_helium_ionization(density, temperature, composition)
    hydrogen_nuclei = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium_nuclei = composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    hydrogen_neutral = hydrogen_nuclei * ionization.hydrogen_neutral_fraction
    hydrogen_ionized = hydrogen_nuclei * ionization.hydrogen_ionized_fraction
    helium_neutral = helium_nuclei * ionization.helium_neutral_fraction
    helium_singly = helium_nuclei * ionization.helium_singly_ionized_fraction
    helium_doubly = helium_nuclei * ionization.helium_doubly_ionized_fraction
    stimulated = -np.expm1(
        -PLANCK_ERG_S * frequency / (BOLTZMANN_ERG_K * temperature)
    )
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
    hydrogen_i = hydrogen_neutral * H_I_VERNER_FIT.cross_section_cm2(energy_ev) * stimulated / density
    helium_i = helium_neutral * HE_I_VERNER_FIT.cross_section_cm2(energy_ev) * stimulated / density
    helium_ii = helium_singly * HE_II_VERNER_FIT.cross_section_cm2(energy_ev) * stimulated / density
    absorption = free_free + hydrogen_i + helium_i + helium_ii
    scattering = THOMSON_CROSS_SECTION_CM2 * ionization.electron_density_cm3 / density
    output = (free_free, hydrogen_i, helium_i, helium_ii, absorption, scattering)
    if not all(np.all(np.isfinite(value)) and np.all(value >= 0.0) for value in output):
        raise ArithmeticError("traceable LTE continuum opacity became invalid")
    return TraceableLTEContinuumOpacity(
        *(_readonly(np.asarray(value)) for value in output)
    )
