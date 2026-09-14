"""裸盘连续谱的最小吸收、散射与热化深度闭合。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .radiation import BOLTZMANN_ERG_K, PLANCK_ERG_S
from .source import PhysicalDomainError, ZOSourceGrid
from .vertical import (
    RADIATION_PRESSURE_POLYTROPE_PROFILE,
    RadiationPressurePolytropeProfile,
)


PROTON_MASS_G = 1.67262192369e-24
THOMSON_CROSS_SECTION_CM2 = 6.6524587321e-25
FREE_FREE_COEFFICIENT_CGS = 3.7e8
PLANCK_BNU_PEAK_X = 2.8214393721220787


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class FullyIonizedHydrogenHeliumComposition:
    """完全电离 H/He 连续谱审计组成；金属和束缚态不在本闭合内。"""

    hydrogen_mass_fraction: float = 0.70
    helium_mass_fraction: float = 0.28
    free_free_gaunt_factor: float = 1.0

    def __post_init__(self) -> None:
        hydrogen = float(self.hydrogen_mass_fraction)
        helium = float(self.helium_mass_fraction)
        gaunt = float(self.free_free_gaunt_factor)
        if (
            not np.isfinite(hydrogen)
            or not np.isfinite(helium)
            or hydrogen < 0.0
            or helium < 0.0
            or hydrogen + helium > 1.0
        ):
            raise PhysicalDomainError(
                "hydrogen and helium mass fractions must be finite, non-negative, "
                "and sum to at most one"
            )
        if not np.isfinite(gaunt) or gaunt <= 0.0:
            raise PhysicalDomainError(
                "free_free_gaunt_factor must be finite and strictly positive"
            )
        object.__setattr__(self, "hydrogen_mass_fraction", hydrogen)
        object.__setattr__(self, "helium_mass_fraction", helium)
        object.__setattr__(self, "free_free_gaunt_factor", gaunt)

    @property
    def electrons_per_baryon_mass(self) -> float:
        return self.hydrogen_mass_fraction + 0.5 * self.helium_mass_fraction

    @property
    def charge_squared_ions_per_baryon_mass(self) -> float:
        return self.hydrogen_mass_fraction + self.helium_mass_fraction

    @property
    def thomson_opacity_cm2_g(self) -> float:
        return (
            THOMSON_CROSS_SECTION_CM2
            / PROTON_MASS_G
            * self.electrons_per_baryon_mass
        )


SOLAR_FULLY_IONIZED_H_HE = FullyIonizedHydrogenHeliumComposition()


def free_free_absorption_opacity_cm2_g(
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    frequency_hz: ArrayLike,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
) -> NDArray[np.float64]:
    """返回含受激辐射修正的热自由-自由质量吸收系数。

    使用 Rybicki--Lightman 形式
    ``alpha_ff=3.7e8*T^-1/2*n_e*sum(Z_i^2 n_i)*nu^-3*(1-exp(-hnu/kT))*gff``。
    完全电离和 ``gff=1`` 是明确工作假设，不代表 NLTE 原子不透明度。
    """
    density, temperature, frequency = np.broadcast_arrays(
        np.asarray(density_g_cm3, dtype=np.float64),
        np.asarray(temperature_k, dtype=np.float64),
        np.asarray(frequency_hz, dtype=np.float64),
    )
    if not np.all(np.isfinite(density)) or np.any(density < 0.0):
        raise PhysicalDomainError("density_g_cm3 must be finite and non-negative")
    for name, values in (("temperature_k", temperature), ("frequency_hz", frequency)):
        if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
            raise PhysicalDomainError(
                f"{name} must contain finite, strictly positive values"
            )

    exponent = PLANCK_ERG_S * frequency / (BOLTZMANN_ERG_K * temperature)
    stimulated_emission = -np.expm1(-exponent)
    number_factor = (
        composition.electrons_per_baryon_mass
        * composition.charge_squared_ions_per_baryon_mass
        / PROTON_MASS_G**2
    )
    # 中文：直接写成 kappa_ff 正比于 rho，可让真空极限严格回到 0，避免 0/0。
    opacity = (
        FREE_FREE_COEFFICIENT_CGS
        * composition.free_free_gaunt_factor
        * number_factor
        * density
        * temperature ** (-0.5)
        * frequency ** (-3.0)
        * stimulated_emission
    )
    if not np.all(np.isfinite(opacity)) or np.any(opacity < 0.0):
        raise ArithmeticError("free-free opacity evaluation produced an invalid value")
    return opacity


@dataclass(frozen=True)
class EffectiveOpticalDepthAudit:
    """各频率从上表面到中面的有效吸收光深。"""

    frequency_hz: NDArray[np.float64]
    midplane_effective_optical_depth: NDArray[np.float64]
    target_effective_optical_depth: float
    electron_scattering_opacity_cm2_g: float
    vertical_points: int

    @property
    def effectively_thick_mask(self) -> NDArray[np.bool_]:
        mask = self.midplane_effective_optical_depth >= self.target_effective_optical_depth
        mask.setflags(write=False)
        return mask


class EffectiveOpticallyThinError(PhysicalDomainError):
    """局域柱在指定频率没有达到所需热化光深。"""


@dataclass(frozen=True)
class PeakThermalizationClosure:
    """在局域 B_nu 峰频处求得的热化层与颜色修正。"""

    peak_frequency_hz: NDArray[np.float64]
    midplane_effective_optical_depth: NDArray[np.float64]
    thermalization_scaled_height: NDArray[np.float64]
    thermalization_scattering_optical_depth: NDArray[np.float64]
    thermalization_temperature_k: NDArray[np.float64]
    spectral_hardening_factor: NDArray[np.float64]
    target_effective_optical_depth: float
    electron_scattering_opacity_cm2_g: float
    vertical_points: int
    profile_name: str


def _validate_transfer_inputs(
    electron_scattering_opacity_cm2_g: float,
    target_effective_optical_depth: float,
    vertical_points: int,
) -> tuple[float, float, int]:
    scattering = float(electron_scattering_opacity_cm2_g)
    target = float(target_effective_optical_depth)
    if not np.isfinite(scattering) or scattering <= 0.0:
        raise PhysicalDomainError(
            "electron_scattering_opacity_cm2_g must be finite and positive"
        )
    if not np.isfinite(target) or target <= 0.0:
        raise PhysicalDomainError(
            "target_effective_optical_depth must be finite and positive"
        )
    if not isinstance(vertical_points, (int, np.integer)) or isinstance(
        vertical_points, (bool, np.bool_)
    ):
        raise PhysicalDomainError("vertical_points must be an integer")
    points = int(vertical_points)
    if points < 33:
        raise PhysicalDomainError("vertical_points must be at least 33")
    return scattering, target, points


def _vertical_grid(
    profile: RadiationPressurePolytropeProfile, vertical_points: int
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    surface = float(profile.surface_scaled_height)
    scaled_height = np.linspace(surface, 0.0, vertical_points)
    density_shape = profile.density_shape(scaled_height)
    upper_fraction = profile.upper_column_fraction(scaled_height)
    return scaled_height, density_shape, upper_fraction


def effective_optical_depth_to_midplane(
    source: ZOSourceGrid,
    frequency_hz: ArrayLike,
    *,
    electron_scattering_opacity_cm2_g: float = 0.34,
    target_effective_optical_depth: float = 1.0,
    profile: RadiationPressurePolytropeProfile = RADIATION_PRESSURE_POLYTROPE_PROFILE,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
    vertical_points: int = 257,
    chunk_size: int = 256,
) -> EffectiveOpticalDepthAudit:
    """审计 ``tau_eff=integral rho*sqrt(3*kabs*(kabs+kes))*dz``。"""
    scattering, target, points = _validate_transfer_inputs(
        electron_scattering_opacity_cm2_g,
        target_effective_optical_depth,
        vertical_points,
    )
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    if frequency.ndim != 1 or frequency.size == 0:
        raise PhysicalDomainError("frequency_hz must be a non-empty one-dimensional grid")
    if not np.all(np.isfinite(frequency)) or np.any(frequency <= 0.0):
        raise PhysicalDomainError("frequency_hz must contain finite, positive values")
    if np.any(np.diff(frequency) <= 0.0):
        raise PhysicalDomainError("frequency_hz must be strictly increasing")
    if not isinstance(chunk_size, (int, np.integer)) or int(chunk_size) < 1:
        raise PhysicalDomainError("chunk_size must be a positive integer")

    scaled_height, density_shape, upper_fraction = _vertical_grid(profile, points)
    flat_sigma = source.surface_density_g_cm2.reshape(-1)
    flat_height = source.scale_height_cm.reshape(-1)
    flat_teff = source.effective_temperature_k.reshape(-1)
    result = np.empty((flat_sigma.size, frequency.size), dtype=np.float64)

    for start in range(0, flat_sigma.size, int(chunk_size)):
        stop = min(flat_sigma.size, start + int(chunk_size))
        sigma = flat_sigma[start:stop, None]
        height = flat_height[start:stop, None]
        teff = flat_teff[start:stop, None]
        density = sigma / height * density_shape[None, :]
        scattering_depth = scattering * sigma * upper_fraction[None, :]
        # 中文：灰 Eddington 温度只负责给 opacity 一个受约束的深度温度，不声称已解非灰平衡。
        temperature = teff * (
            0.75 * (scattering_depth + 2.0 / 3.0)
        ) ** 0.25
        absorption = free_free_absorption_opacity_cm2_g(
            density[:, :, None],
            temperature[:, :, None],
            frequency[None, None, :],
            composition,
        )
        integrand = (
            height[:, :, None]
            * density[:, :, None]
            * np.sqrt(3.0 * absorption * (absorption + scattering))
        )
        result[start:stop] = np.trapezoid(integrand, -scaled_height, axis=1)

    if not np.all(np.isfinite(result)) or np.any(result < 0.0):
        raise ArithmeticError("effective optical-depth integration failed")
    shaped = result.reshape(source.shape + (frequency.size,))
    return EffectiveOpticalDepthAudit(
        frequency_hz=_readonly(frequency),
        midplane_effective_optical_depth=_readonly(shaped),
        target_effective_optical_depth=target,
        electron_scattering_opacity_cm2_g=scattering,
        vertical_points=points,
    )


def solve_peak_thermalization_closure(
    source: ZOSourceGrid,
    *,
    electron_scattering_opacity_cm2_g: float = 0.34,
    target_effective_optical_depth: float = 1.0,
    profile: RadiationPressurePolytropeProfile = RADIATION_PRESSURE_POLYTROPE_PROFILE,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
    vertical_points: int = 257,
    chunk_size: int = 512,
) -> PeakThermalizationClosure:
    """在每个表面元的局域 ``B_nu`` 峰频处求有效热化层。

    若任一局域柱在中面前仍达不到 ``tau_eff`` 目标，本函数直接拒绝整个闭合；
    不会把热化层钉在中面或人为限制颜色修正。
    """
    scattering, target, points = _validate_transfer_inputs(
        electron_scattering_opacity_cm2_g,
        target_effective_optical_depth,
        vertical_points,
    )
    if not isinstance(chunk_size, (int, np.integer)) or int(chunk_size) < 1:
        raise PhysicalDomainError("chunk_size must be a positive integer")
    scaled_height, density_shape, upper_fraction = _vertical_grid(profile, points)
    delta_scaled_height = scaled_height[:-1] - scaled_height[1:]
    flat_sigma = source.surface_density_g_cm2.reshape(-1)
    flat_height = source.scale_height_cm.reshape(-1)
    flat_teff = source.effective_temperature_k.reshape(-1)
    peak_frequency = (
        PLANCK_BNU_PEAK_X * BOLTZMANN_ERG_K / PLANCK_ERG_S * flat_teff
    )
    output_midplane = np.empty(flat_sigma.size, dtype=np.float64)
    output_zeta = np.empty(flat_sigma.size, dtype=np.float64)
    output_scattering_depth = np.empty(flat_sigma.size, dtype=np.float64)
    output_temperature = np.empty(flat_sigma.size, dtype=np.float64)

    for start in range(0, flat_sigma.size, int(chunk_size)):
        stop = min(flat_sigma.size, start + int(chunk_size))
        sigma = flat_sigma[start:stop, None]
        height = flat_height[start:stop, None]
        teff = flat_teff[start:stop, None]
        density = sigma / height * density_shape[None, :]
        scattering_depth = scattering * sigma * upper_fraction[None, :]
        temperature = teff * (
            0.75 * (scattering_depth + 2.0 / 3.0)
        ) ** 0.25
        absorption = free_free_absorption_opacity_cm2_g(
            density,
            temperature,
            peak_frequency[start:stop, None],
            composition,
        )
        integrand = height * density * np.sqrt(
            3.0 * absorption * (absorption + scattering)
        )
        increments = (
            0.5
            * (integrand[:, :-1] + integrand[:, 1:])
            * delta_scaled_height[None, :]
        )
        cumulative = np.empty((stop - start, points), dtype=np.float64)
        cumulative[:, 0] = 0.0
        np.cumsum(increments, axis=1, out=cumulative[:, 1:])
        midplane = cumulative[:, -1]
        output_midplane[start:stop] = midplane
        crossed = midplane >= target
        if not np.all(crossed):
            local = int(np.argwhere(~crossed)[0, 0])
            flat_index = start + local
            source_index = np.unravel_index(flat_index, source.shape)
            raise EffectiveOpticallyThinError(
                "no peak-frequency thermalization layer above the midplane: "
                f"tau_eff={midplane[local]!r} < {target!r} at index {source_index}"
            )

        upper_index = np.argmax(cumulative >= target, axis=1)
        lower_index = upper_index - 1
        row = np.arange(stop - start)
        lower_tau = cumulative[row, lower_index]
        upper_tau = cumulative[row, upper_index]
        interval = upper_tau - lower_tau
        if np.any(interval <= 0.0) or not np.all(np.isfinite(interval)):
            raise ArithmeticError("thermalization crossing has an invalid interval")
        fraction = (target - lower_tau) / interval
        # 中文：只在线性积分单元内插值，不把越界解裁回网格。
        zeta = (
            scaled_height[lower_index]
            + fraction * (scaled_height[upper_index] - scaled_height[lower_index])
        )
        tau_scattering = (
            scattering_depth[row, lower_index]
            + fraction
            * (
                scattering_depth[row, upper_index]
                - scattering_depth[row, lower_index]
            )
        )
        # 中文：温度直接由已插值得到的散射光深重算，严格保留灰温度关系。
        thermal_temperature = teff[:, 0] * (
            0.75 * (tau_scattering + 2.0 / 3.0)
        ) ** 0.25
        output_zeta[start:stop] = zeta
        output_scattering_depth[start:stop] = tau_scattering
        output_temperature[start:stop] = thermal_temperature

    hardening = output_temperature / flat_teff
    invalid_hardening = (~np.isfinite(hardening)) | (hardening < 1.0)
    if np.any(invalid_hardening):
        flat_index = int(np.argwhere(invalid_hardening)[0, 0])
        source_index = np.unravel_index(flat_index, source.shape)
        raise PhysicalDomainError(
            "peak thermalization does not define a hardening factor >= 1; "
            f"got {hardening[flat_index]!r} at index {source_index}"
        )

    def shaped(values: NDArray[np.float64]) -> NDArray[np.float64]:
        return _readonly(values.reshape(source.shape))

    return PeakThermalizationClosure(
        peak_frequency_hz=shaped(peak_frequency),
        midplane_effective_optical_depth=shaped(output_midplane),
        thermalization_scaled_height=shaped(output_zeta),
        thermalization_scattering_optical_depth=shaped(output_scattering_depth),
        thermalization_temperature_k=shaped(output_temperature),
        spectral_hardening_factor=shaped(hardening),
        target_effective_optical_depth=target,
        electron_scattering_opacity_cm2_g=scattering,
        vertical_points=points,
        profile_name=profile.name,
    )
