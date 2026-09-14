"""ZO 动态偏心柱到静态 annulus-atmosphere 输入坐标的桥梁。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.interpolate import RegularGridInterpolator

from .radiation import LIGHT_SPEED_CM_S
from .relativity import GRAVITATIONAL_CONSTANT_CGS
from .source import PhysicalDomainError
from .zo_reference import (
    ADIABATIC_INDEX,
    SOLAR_MASS_G,
    ZOConstantEReferenceModel,
)


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class AnnulusAtmosphereCoordinates:
    """每个 ``(a,E)`` 柱的静态大气输入及动态失效指标。"""

    effective_temperature_k: NDArray[np.float64]
    midplane_column_mass_g_cm2: NDArray[np.float64]
    tidal_gravity_coefficient_s2: NDArray[np.float64]
    comoving_pressure_gravity_coefficient_s2: NDArray[np.float64]
    vertical_acceleration_coefficient_s2: NDArray[np.float64]
    logarithmic_breathing_rate_s1: NDArray[np.float64]
    quasi_static_ratio: NDArray[np.float64]


def zo_annulus_atmosphere_coordinates(
    model: ZOConstantEReferenceModel,
) -> AnnulusAtmosphereCoordinates:
    """Construct ``(T_eff, m0, Q)`` and a quasi-static validity ratio.

    Davis--Hubeny uses ``m0=Sigma/2`` and a static gravity ``g=Q*z``.  A ZO
    column is accelerating vertically, so the pressure gradient balances the
    comoving coefficient

    ``Q_pressure = GM/r^3 + Hddot/H``.

    ZO Eq. (35) reduces this without numerical differentiation to

    ``Q_pressure=n^2*j^(-(gamma-1))*h^(-(gamma+1))``.

    ``|d ln H/dt|/sqrt(Q_pressure)`` measures whether a sequence of static
    annuli can respond faster than the breathing motion.  It is a validity
    diagnostic, not an automatic correction to an atmosphere table.
    """
    if not isinstance(model, ZOConstantEReferenceModel):
        raise TypeError("model must be a ZOConstantEReferenceModel")
    source = model.source
    if not np.array_equal(
        source.eccentric_anomaly_rad, model.breathing.eccentric_anomaly_rad
    ):
        raise PhysicalDomainError("source and breathing anomaly grids do not match")
    mass_g = model.parameters.black_hole_mass_msun * SOLAR_MASS_G
    a = source.semimajor_axis_cm[:, None]
    eccentricity = source.eccentricity[:, None]
    anomaly = source.eccentric_anomaly_rad[None, :]
    orbital_factor = 1.0 - eccentricity * np.cos(anomaly)
    mean_motion_squared = GRAVITATIONAL_CONSTANT_CGS * mass_g / a**3
    tidal_q = mean_motion_squared / orbital_factor**3
    height = model.breathing.dimensionless_height[None, :]
    # 中文：用 ZO 呼吸方程直接求压力所需的瞬时 Q，避免对离散 H(E) 二次求导。
    pressure_q = (
        mean_motion_squared
        * source.jacobian ** (-(ADIABATIC_INDEX - 1.0))
        * height ** (-(ADIABATIC_INDEX + 1.0))
    )
    anomaly_rate = np.sqrt(mean_motion_squared) / orbital_factor
    breathing_rate = (
        model.breathing.log_height_derivative_per_rad[None, :] * anomaly_rate
    )
    vertical_acceleration = pressure_q - tidal_q
    # 中文：该比率只判断静态环带是否来得及响应，不把动态柱强行修正成静态柱。
    quasi_static = np.abs(breathing_rate) / np.sqrt(pressure_q)
    midplane_column = 0.5 * source.surface_density_g_cm2
    arrays = (
        source.effective_temperature_k,
        midplane_column,
        tidal_q,
        pressure_q,
        vertical_acceleration,
        breathing_rate,
        quasi_static,
    )
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ArithmeticError("annulus-atmosphere coordinates became non-finite")
    if np.any(midplane_column <= 0.0) or np.any(tidal_q <= 0.0) or np.any(pressure_q <= 0.0):
        raise PhysicalDomainError("annulus coordinates require positive m0 and Q")
    return AnnulusAtmosphereCoordinates(
        *(_readonly(np.asarray(array)) for array in arrays)
    )


class AnnulusTableDomainError(PhysicalDomainError):
    """查询点位于 annulus table 严格定义域之外。"""


@dataclass(frozen=True)
class AngleResolvedAnnulusTable:
    """严格不外推的 ``I_nu(T_eff,m0,Q,mu,nu)`` 表接口。

    该类不自带任何 NLTE 原子数据。只有外部大气求解器提供了正、有限的强度表后，
    才能替换当前 modified-blackbody 局域谱。
    """

    effective_temperature_k: ArrayLike
    midplane_column_mass_g_cm2: ArrayLike
    gravity_coefficient_s2: ArrayLike
    emission_cosine: ArrayLike
    frequency_hz: ArrayLike
    specific_intensity_cgs: ArrayLike
    provenance: str

    def __post_init__(self) -> None:
        axes = []
        names = (
            "effective_temperature_k",
            "midplane_column_mass_g_cm2",
            "gravity_coefficient_s2",
            "emission_cosine",
            "frequency_hz",
        )
        for name in names:
            axis = np.array(getattr(self, name), dtype=np.float64, copy=True)
            if axis.ndim != 1 or axis.size < 2:
                raise PhysicalDomainError(f"{name} must be a 1D axis with at least two points")
            if not np.all(np.isfinite(axis)) or np.any(np.diff(axis) <= 0.0):
                raise PhysicalDomainError(f"{name} must be finite and strictly increasing")
            axes.append(axis)
        temperature, column, gravity, cosine, frequency = axes
        if np.any(temperature <= 0.0) or np.any(column <= 0.0) or np.any(gravity <= 0.0) or np.any(frequency <= 0.0):
            raise PhysicalDomainError("temperature, column, gravity and frequency axes must be positive")
        if cosine[0] < 0.0 or cosine[-1] > 1.0:
            raise PhysicalDomainError("emission_cosine axis must lie in [0, 1]")
        intensity = np.array(self.specific_intensity_cgs, dtype=np.float64, copy=True)
        expected = tuple(axis.size for axis in axes)
        if intensity.shape != expected:
            raise PhysicalDomainError(
                f"specific_intensity_cgs must have shape {expected}; got {intensity.shape}"
            )
        if not np.all(np.isfinite(intensity)) or np.any(intensity <= 0.0):
            raise PhysicalDomainError("annulus intensities must be finite and strictly positive")
        provenance = str(self.provenance).strip()
        if not provenance:
            raise PhysicalDomainError("annulus table requires non-empty provenance")
        for name, axis in zip(names, axes, strict=True):
            object.__setattr__(self, name, _readonly(axis))
        object.__setattr__(self, "specific_intensity_cgs", _readonly(intensity))
        object.__setattr__(self, "provenance", provenance)

    def interpolate_specific_intensity(
        self,
        effective_temperature_k: ArrayLike,
        midplane_column_mass_g_cm2: ArrayLike,
        gravity_coefficient_s2: ArrayLike,
        emission_cosine: ArrayLike,
        frequency_hz: ArrayLike,
    ) -> NDArray[np.float64]:
        """Log-interpolate intensity while rejecting every extrapolation."""
        query_arrays = np.broadcast_arrays(
            np.asarray(effective_temperature_k, dtype=np.float64),
            np.asarray(midplane_column_mass_g_cm2, dtype=np.float64),
            np.asarray(gravity_coefficient_s2, dtype=np.float64),
            np.asarray(emission_cosine, dtype=np.float64),
            np.asarray(frequency_hz, dtype=np.float64),
        )
        names = ("T_eff", "m0", "Q", "mu", "frequency")
        axes = (
            self.effective_temperature_k,
            self.midplane_column_mass_g_cm2,
            self.gravity_coefficient_s2,
            self.emission_cosine,
            self.frequency_hz,
        )
        for name, values, axis in zip(names, query_arrays, axes, strict=True):
            if not np.all(np.isfinite(values)):
                raise AnnulusTableDomainError(f"{name} query contains non-finite values")
            outside = (values < axis[0]) | (values > axis[-1])
            if np.any(outside):
                index = tuple(int(i) for i in np.argwhere(outside)[0])
                raise AnnulusTableDomainError(
                    f"{name} query at index {index} lies outside [{axis[0]}, {axis[-1]}]"
                )
        transformed_axes = (
            np.log(self.effective_temperature_k),
            np.log(self.midplane_column_mass_g_cm2),
            np.log(self.gravity_coefficient_s2),
            self.emission_cosine,
            np.log(self.frequency_hz),
        )
        # 中文：正量在对数空间插值；定义域外已在上方拒绝，绝不夹到表边界。
        transformed_query = np.column_stack(
            (
                np.log(query_arrays[0].reshape(-1)),
                np.log(query_arrays[1].reshape(-1)),
                np.log(query_arrays[2].reshape(-1)),
                query_arrays[3].reshape(-1),
                np.log(query_arrays[4].reshape(-1)),
            )
        )
        interpolator = RegularGridInterpolator(
            transformed_axes,
            np.log(self.specific_intensity_cgs),
            method="linear",
            bounds_error=True,
        )
        result = np.exp(interpolator(transformed_query)).reshape(query_arrays[0].shape)
        if not np.all(np.isfinite(result)) or np.any(result <= 0.0):
            raise ArithmeticError("annulus-table interpolation became invalid")
        return _readonly(result)


def compton_y_upper_bound(
    temperature_k: ArrayLike,
    scattering_optical_depth: ArrayLike,
) -> NDArray[np.float64]:
    """Return the non-relativistic thermal Compton ``y`` diagnostic.

    ``y = 4 kT/(m_e c^2) * max(tau, tau^2)`` is only a regime flag; it does not
    replace a Kompaneets or NLTE transfer solution.
    """
    from .non_gray import ELECTRON_MASS_G
    from .radiation import BOLTZMANN_ERG_K

    temperature, depth = np.broadcast_arrays(
        np.asarray(temperature_k, dtype=np.float64),
        np.asarray(scattering_optical_depth, dtype=np.float64),
    )
    if not np.all(np.isfinite(temperature)) or np.any(temperature <= 0.0):
        raise PhysicalDomainError("temperature_k must be finite and positive")
    if not np.all(np.isfinite(depth)) or np.any(depth < 0.0):
        raise PhysicalDomainError("scattering_optical_depth must be finite and non-negative")
    # 中文：max(tau,tau^2) 是标准薄/厚散射次数估计，不是数值裁剪。
    y = (
        4.0
        * BOLTZMANN_ERG_K
        * temperature
        / (ELECTRON_MASS_G * LIGHT_SPEED_CM_S**2)
        * np.maximum(depth, depth**2)
    )
    if not np.all(np.isfinite(y)):
        raise ArithmeticError("Compton y diagnostic became non-finite")
    return _readonly(y)
