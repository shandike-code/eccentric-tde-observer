"""有限沉积柱静态门所需的受控附加能量项。

这里仅加入两类可以单独关闭的边界项：Thomson 极限 Compton 能量交换，
以及 H I/He II 碰撞激发线在“全部逃逸”极限下的冷却。后者不是多能级
NLTE 线转移；零逃逸与全部逃逸只用于夹住缺失线物理的影响。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .atmosphere import (
    PROTON_MASS_G,
    SOLAR_FULLY_IONIZED_H_HE,
    THOMSON_CROSS_SECTION_CM2,
    FullyIonizedHydrogenHeliumComposition,
)
from .continuum_emission import EmissiveCoupledSlab
from .non_gray import ELECTRON_MASS_G
from .radiation import BOLTZMANN_ERG_K, LIGHT_SPEED_CM_S, PLANCK_ERG_S
from .source import PhysicalDomainError


LineCoolingBoundary = Literal["disabled", "full_escape"]


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class SupplementalEnergyControls:
    """静态门的可关闭微物理控制，不把边界项伪装成完整大气。"""

    include_compton_exchange: bool = False
    line_cooling_boundary: LineCoolingBoundary = "disabled"

    def __post_init__(self) -> None:
        if not isinstance(self.include_compton_exchange, (bool, np.bool_)):
            raise PhysicalDomainError("include_compton_exchange must be boolean")
        if self.line_cooling_boundary not in ("disabled", "full_escape"):
            raise PhysicalDomainError(
                "line_cooling_boundary must be 'disabled' or 'full_escape'"
            )


@dataclass(frozen=True)
class SupplementalEnergyTerms:
    """逐深度 Compton、碰撞激发线与两者的净气体加热。"""

    compton_heating_erg_s_cm3: NDArray[np.float64]
    line_cooling_erg_s_cm3: NDArray[np.float64]
    net_heating_erg_s_cm3: NDArray[np.float64]
    maximum_photon_energy_over_electron_rest_energy: float
    controls: SupplementalEnergyControls


def top_hat_mass_column_heating_erg_s_cm3(
    one_face_heating_flux_erg_s_cm2: float,
    density_g_cm3: float,
    depth_edges_cm: ArrayLike,
    deposition_column_g_cm2: float,
) -> NDArray[np.float64]:
    """把总通量均匀沉积在表面以下有限质量柱中。

    对跨越沉积边界的单元使用解析重叠比例，因此离散积分严格保留输入面
    通量；函数不在计算后重新归一化。
    """
    flux = float(one_face_heating_flux_erg_s_cm2)
    density = float(density_g_cm3)
    deposition = float(deposition_column_g_cm2)
    edges = np.asarray(depth_edges_cm, dtype=np.float64)
    if not np.isfinite(flux) or flux < 0.0:
        raise PhysicalDomainError(
            "one_face_heating_flux_erg_s_cm2 must be finite and non-negative"
        )
    if not np.isfinite(density) or density <= 0.0:
        raise PhysicalDomainError("density_g_cm3 must be finite and strictly positive")
    if (
        edges.ndim != 1
        or edges.size < 2
        or not np.all(np.isfinite(edges))
        or np.any(np.diff(edges) <= 0.0)
    ):
        raise PhysicalDomainError(
            "depth_edges_cm must be finite and strictly increasing"
        )
    mass_edges = density * (edges - edges[0])
    total_column = float(mass_edges[-1])
    if (
        not np.isfinite(deposition)
        or deposition <= 0.0
        or deposition > total_column
    ):
        raise PhysicalDomainError(
            "deposition_column_g_cm2 must lie in (0, total slab column]"
        )
    overlap = np.minimum(mass_edges[1:], deposition) - np.minimum(
        mass_edges[:-1], deposition
    )
    if np.any(overlap < 0.0):
        raise ArithmeticError("mass-column overlap became negative")
    cell_mass = np.diff(mass_edges)
    # 中文：F/m_dep 是单位质量柱加热；乘 rho 和单元重叠比例得到体积平均。
    heating = density * flux / deposition * overlap / cell_mass
    if not np.all(np.isfinite(heating)) or np.any(heating < 0.0):
        raise ArithmeticError("finite-column deposition produced invalid heating")
    return _readonly(heating)


def thomson_compton_heating_erg_s_cm3(
    frequency_hz: ArrayLike,
    mean_intensity_cgs: ArrayLike,
    electron_density_cm3: ArrayLike,
    electron_temperature_k: ArrayLike,
) -> NDArray[np.float64]:
    """返回稀薄 Thomson 极限下辐射对热电子的 Compton 净加热。

    正值表示气体受热。当前静态转移仍按相干 Thomson 散射求 ``J_nu``，
    所以本项只是一阶能量门，不是 Kompaneets 频率重分布求解器。
    """
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    mean = np.asarray(mean_intensity_cgs, dtype=np.float64)
    electron = np.asarray(electron_density_cm3, dtype=np.float64)
    temperature = np.asarray(electron_temperature_k, dtype=np.float64)
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
    if mean.ndim != 2 or mean.shape[0] != frequency.size:
        raise PhysicalDomainError(
            "mean_intensity_cgs must have shape (frequency, depth)"
        )
    depth_points = mean.shape[1]
    try:
        electron = np.array(
            np.broadcast_to(electron, (depth_points,)), dtype=np.float64, copy=True
        )
        temperature = np.array(
            np.broadcast_to(temperature, (depth_points,)), dtype=np.float64, copy=True
        )
    except ValueError as error:
        raise PhysicalDomainError(
            "electron density and temperature must be scalar or depth-resolved"
        ) from error
    if not np.all(np.isfinite(mean)) or np.any(mean < 0.0):
        raise PhysicalDomainError("mean_intensity_cgs must be finite and non-negative")
    if not np.all(np.isfinite(electron)) or np.any(electron < 0.0):
        raise PhysicalDomainError("electron_density_cm3 must be finite and non-negative")
    if not np.all(np.isfinite(temperature)) or np.any(temperature <= 0.0):
        raise PhysicalDomainError(
            "electron_temperature_k must be finite and strictly positive"
        )
    exchange_energy = (
        PLANCK_ERG_S * frequency[:, None]
        - 4.0 * BOLTZMANN_ERG_K * temperature[None, :]
    )
    moment = 4.0 * np.pi * np.trapezoid(
        mean * exchange_energy, frequency, axis=0
    )
    heating = (
        electron
        * THOMSON_CROSS_SECTION_CM2
        / (ELECTRON_MASS_G * LIGHT_SPEED_CM_S**2)
        * moment
    )
    if not np.all(np.isfinite(heating)):
        raise ArithmeticError("Compton energy exchange became non-finite")
    return _readonly(heating)


def full_escape_hydrogen_helium_line_cooling_erg_s_cm3(
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    electron_density_cm3: ArrayLike,
    hydrogen_neutral_fraction: ArrayLike,
    helium_singly_ionized_fraction: ArrayLike,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> NDArray[np.float64]:
    """返回 H I 与 He II 碰撞激发线全部逃逸时的冷却上边界。

    采用 Cen 类常用拟合。没有激发态统计平衡、碰撞退激或线逃逸转移，
    因而只能与零线冷却控制共同构成边界，不能解释为真实线光度。
    """
    density, temperature, electron, neutral_h, singly_he = np.broadcast_arrays(
        np.asarray(density_g_cm3, dtype=np.float64),
        np.asarray(temperature_k, dtype=np.float64),
        np.asarray(electron_density_cm3, dtype=np.float64),
        np.asarray(hydrogen_neutral_fraction, dtype=np.float64),
        np.asarray(helium_singly_ionized_fraction, dtype=np.float64),
    )
    if not np.all(np.isfinite(density)) or np.any(density <= 0.0):
        raise PhysicalDomainError(
            "density_g_cm3 must be finite and strictly positive"
        )
    if not np.all(np.isfinite(temperature)) or np.any(temperature <= 0.0):
        raise PhysicalDomainError("temperature_k must be finite and strictly positive")
    if not np.all(np.isfinite(electron)) or np.any(electron < 0.0):
        raise PhysicalDomainError("electron_density_cm3 must be finite and non-negative")
    for name, fraction in (
        ("hydrogen_neutral_fraction", neutral_h),
        ("helium_singly_ionized_fraction", singly_he),
    ):
        if (
            not np.all(np.isfinite(fraction))
            or np.any(fraction < 0.0)
            or np.any(fraction > 1.0)
        ):
            raise PhysicalDomainError(f"{name} must lie in [0, 1]")
    hydrogen_nuclei = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium_nuclei = composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    denominator = 1.0 + np.sqrt(temperature / 1.0e5)
    hydrogen_coefficient = (
        7.5e-19 * np.exp(-118348.0 / temperature) / denominator
    )
    helium_ii_coefficient = (
        5.54e-17
        * temperature ** (-0.397)
        * np.exp(-473638.0 / temperature)
        / denominator
    )
    cooling = electron * (
        hydrogen_nuclei * neutral_h * hydrogen_coefficient
        + helium_nuclei * singly_he * helium_ii_coefficient
    )
    if not np.all(np.isfinite(cooling)) or np.any(cooling < 0.0):
        raise ArithmeticError("full-escape line cooling became invalid")
    return _readonly(cooling)


def supplemental_static_energy_terms(
    slab: EmissiveCoupledSlab,
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    controls: SupplementalEnergyControls,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> SupplementalEnergyTerms:
    """按控制开关计算静态板层的附加能量项。"""
    if not isinstance(slab, EmissiveCoupledSlab):
        raise TypeError("slab must be an EmissiveCoupledSlab")
    if not isinstance(controls, SupplementalEnergyControls):
        raise TypeError("controls must be SupplementalEnergyControls")
    depth_points = slab.temperature_k.size
    temperature = np.asarray(temperature_k, dtype=np.float64)
    try:
        temperature = np.array(
            np.broadcast_to(temperature, (depth_points,)), dtype=np.float64, copy=True
        )
    except ValueError as error:
        raise PhysicalDomainError(
            "temperature_k must be scalar or depth-resolved"
        ) from error
    if not np.all(np.isfinite(temperature)) or np.any(temperature <= 0.0):
        raise PhysicalDomainError("temperature_k must be finite and strictly positive")

    if controls.include_compton_exchange:
        compton = thomson_compton_heating_erg_s_cm3(
            slab.transfer.frequency_hz,
            slab.transfer.mean_intensity,
            slab.population.electron_density_cm3,
            temperature,
        )
    else:
        compton = _readonly(np.zeros(depth_points, dtype=np.float64))

    if controls.line_cooling_boundary == "full_escape":
        line = full_escape_hydrogen_helium_line_cooling_erg_s_cm3(
            density_g_cm3,
            temperature,
            slab.population.electron_density_cm3,
            slab.population.hydrogen_neutral_fraction,
            slab.population.helium_singly_ionized_fraction,
            composition=composition,
        )
    else:
        line = _readonly(np.zeros(depth_points, dtype=np.float64))
    net = np.asarray(compton) - np.asarray(line)
    if not np.all(np.isfinite(net)):
        raise ArithmeticError("supplemental static energy balance became non-finite")
    recoil = float(
        PLANCK_ERG_S
        * slab.transfer.frequency_hz[-1]
        / (ELECTRON_MASS_G * LIGHT_SPEED_CM_S**2)
    )
    return SupplementalEnergyTerms(
        compton_heating_erg_s_cm3=_readonly(np.array(compton, copy=True)),
        line_cooling_erg_s_cm3=_readonly(np.array(line, copy=True)),
        net_heating_erg_s_cm3=_readonly(np.array(net, copy=True)),
        maximum_photon_energy_over_electron_rest_energy=recoil,
        controls=controls,
    )
