"""规定 ZO 背景上的一维周期柱与守恒布居控制核。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.linalg import expm

from .annulus_bridge import zo_annulus_atmosphere_coordinates
from .radiation import LIGHT_SPEED_CM_S, STEFAN_BOLTZMANN_ERG_S_CM2_K4
from .relativity import GRAVITATIONAL_CONSTANT_CGS
from .source import PhysicalDomainError
from .vertical import (
    RADIATION_PRESSURE_POLYTROPE_PROFILE,
    VerticalDensityProfile,
)
from .zo_reference import SOLAR_MASS_G, ZOConstantEReferenceModel


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class PeriodicColumnBackground:
    """一个固定半长轴 ZO 柱在完整轨道上的规定背景。"""

    radial_index: int
    semimajor_axis_cm: float
    eccentricity: float
    orbital_period_s: float
    eccentric_anomaly_rad: NDArray[np.float64]
    mean_anomaly_rad: NDArray[np.float64]
    time_since_pericentre_s: NDArray[np.float64]
    step_duration_s: NDArray[np.float64]
    orbital_radius_cm: NDArray[np.float64]
    surface_density_g_cm2: NDArray[np.float64]
    scale_height_cm: NDArray[np.float64]
    effective_temperature_k: NDArray[np.float64]
    one_sided_column_mass_g_cm2: NDArray[np.float64]
    pressure_gravity_coefficient_s2: NDArray[np.float64]
    tidal_gravity_coefficient_s2: NDArray[np.float64]
    logarithmic_breathing_rate_s1: NDArray[np.float64]
    quasi_static_ratio: NDArray[np.float64]
    one_face_surface_flux_erg_s_cm2: NDArray[np.float64]
    electron_scattering_depth_to_midplane: NDArray[np.float64]
    scale_height_light_crossing_s: NDArray[np.float64]
    scattering_transport_time_proxy_s: NDArray[np.float64]
    vertical_response_time_s: NDArray[np.float64]
    vertical_profile: VerticalDensityProfile

    @property
    def phase_points(self) -> int:
        return int(self.eccentric_anomaly_rad.size)

    def density_g_cm3(self, scaled_height: ArrayLike) -> NDArray[np.float64]:
        """在固定同源坐标 ``zeta=z/H`` 上返回密度。"""
        zeta = np.asarray(scaled_height, dtype=np.float64)
        if zeta.ndim != 1 or zeta.size < 2:
            raise PhysicalDomainError("scaled_height must be a 1D array with at least two points")
        if not np.all(np.isfinite(zeta)) or np.any(np.diff(zeta) <= 0.0):
            raise PhysicalDomainError("scaled_height must be finite and strictly increasing")
        # 中文：rho=Sigma/H*f(zeta) 保留 ZO 的 Sigma(E) 与 H(E)，不重定义源场。
        density = (
            self.surface_density_g_cm2[:, None]
            / self.scale_height_cm[:, None]
            * self.vertical_profile.density_shape(zeta)[None, :]
        )
        if not np.all(np.isfinite(density)) or np.any(density < 0.0):
            raise ArithmeticError("periodic-column density became invalid")
        return _readonly(density)

    def homologous_vertical_velocity_cm_s(
        self, scaled_height: ArrayLike
    ) -> NDArray[np.float64]:
        """返回固定 ``zeta`` 流体元的 ``v_z=zeta*H*dlnH/dt``。"""
        zeta = np.asarray(scaled_height, dtype=np.float64)
        if zeta.ndim != 1 or not np.all(np.isfinite(zeta)):
            raise PhysicalDomainError("scaled_height must be a finite 1D array")
        velocity = (
            self.scale_height_cm[:, None]
            * self.logarithmic_breathing_rate_s1[:, None]
            * zeta[None, :]
        )
        if not np.all(np.isfinite(velocity)):
            raise ArithmeticError("homologous vertical velocity became invalid")
        return _readonly(velocity)


def build_zo_periodic_column_background(
    model: ZOConstantEReferenceModel,
    radial_index: int,
    *,
    vertical_profile: VerticalDensityProfile = RADIATION_PRESSURE_POLYTROPE_PROFILE,
) -> PeriodicColumnBackground:
    """把一个实际 ZO 径向网格点展开成完整周期背景。

    时间映射严格使用开普勒关系 ``M=E-e*sin(E)``。这里没有静态化
    ``Q``，也没有调用旧面积元；这是一个局域柱的拉格朗日轨道。
    """
    if not isinstance(model, ZOConstantEReferenceModel):
        raise TypeError("model must be a ZOConstantEReferenceModel")
    if not isinstance(radial_index, (int, np.integer)) or isinstance(
        radial_index, (bool, np.bool_)
    ):
        raise PhysicalDomainError("radial_index must be an integer")
    radial_index = int(radial_index)
    source = model.source
    if radial_index < 0 or radial_index >= source.shape[0]:
        raise PhysicalDomainError("radial_index lies outside the source grid")
    anomaly = np.asarray(source.eccentric_anomaly_rad, dtype=np.float64)
    if anomaly[0] != 0.0:
        raise PhysicalDomainError("periodic ZO column requires an anomaly grid starting at E=0")

    semimajor_axis = float(source.semimajor_axis_cm[radial_index])
    eccentricity = float(source.eccentricity[radial_index])
    mass_g = model.parameters.black_hole_mass_msun * SOLAR_MASS_G
    mean_motion = np.sqrt(
        GRAVITATIONAL_CONSTANT_CGS * mass_g / semimajor_axis**3
    )
    orbital_period = 2.0 * np.pi / mean_motion
    mean_anomaly = anomaly - eccentricity * np.sin(anomaly)
    time = mean_anomaly / mean_motion
    step_duration = np.diff(np.concatenate((time, [orbital_period])))
    if np.any(step_duration <= 0.0):
        raise PhysicalDomainError("orbital time steps must be strictly positive")
    if not np.isclose(
        np.sum(step_duration, dtype=np.float64),
        orbital_period,
        rtol=2.0e-15,
        atol=0.0,
    ):
        raise ArithmeticError("cyclic orbital time steps do not sum to one period")

    atmosphere = zo_annulus_atmosphere_coordinates(model)
    sigma = np.asarray(source.surface_density_g_cm2[radial_index], dtype=np.float64)
    height = np.asarray(source.scale_height_cm[radial_index], dtype=np.float64)
    temperature = np.asarray(source.effective_temperature_k[radial_index], dtype=np.float64)
    one_sided_column = np.asarray(
        atmosphere.midplane_column_mass_g_cm2[radial_index], dtype=np.float64
    )
    pressure_q = np.asarray(
        atmosphere.comoving_pressure_gravity_coefficient_s2[radial_index],
        dtype=np.float64,
    )
    tidal_q = np.asarray(
        atmosphere.tidal_gravity_coefficient_s2[radial_index], dtype=np.float64
    )
    breathing_rate = np.asarray(
        atmosphere.logarithmic_breathing_rate_s1[radial_index], dtype=np.float64
    )
    quasi_static = np.asarray(
        atmosphere.quasi_static_ratio[radial_index], dtype=np.float64
    )
    surface_flux = STEFAN_BOLTZMANN_ERG_S_CM2_K4 * temperature**4
    scattering_depth = model.parameters.opacity_cm2_g * one_sided_column
    light_crossing = height / LIGHT_SPEED_CM_S
    # 中文：tau_es*H/c 只作散射输运时标代理，不代替频率依赖转移。
    scattering_transport = scattering_depth * light_crossing
    vertical_response = 1.0 / np.sqrt(pressure_q)
    radius = semimajor_axis * (1.0 - eccentricity * np.cos(anomaly))

    arrays = (
        anomaly,
        mean_anomaly,
        time,
        step_duration,
        radius,
        sigma,
        height,
        temperature,
        one_sided_column,
        pressure_q,
        tidal_q,
        breathing_rate,
        quasi_static,
        surface_flux,
        scattering_depth,
        light_crossing,
        scattering_transport,
        vertical_response,
    )
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ArithmeticError("periodic-column background contains a non-finite value")
    positive_arrays = (
        radius,
        sigma,
        height,
        temperature,
        one_sided_column,
        pressure_q,
        tidal_q,
        surface_flux,
        scattering_depth,
        light_crossing,
        scattering_transport,
        vertical_response,
    )
    if any(np.any(array <= 0.0) for array in positive_arrays):
        raise PhysicalDomainError("periodic-column positive field became non-positive")

    return PeriodicColumnBackground(
        radial_index=radial_index,
        semimajor_axis_cm=semimajor_axis,
        eccentricity=eccentricity,
        orbital_period_s=float(orbital_period),
        eccentric_anomaly_rad=_readonly(anomaly.copy()),
        mean_anomaly_rad=_readonly(mean_anomaly),
        time_since_pericentre_s=_readonly(time),
        step_duration_s=_readonly(step_duration),
        orbital_radius_cm=_readonly(radius),
        surface_density_g_cm2=_readonly(sigma.copy()),
        scale_height_cm=_readonly(height.copy()),
        effective_temperature_k=_readonly(temperature.copy()),
        one_sided_column_mass_g_cm2=_readonly(one_sided_column.copy()),
        pressure_gravity_coefficient_s2=_readonly(pressure_q.copy()),
        tidal_gravity_coefficient_s2=_readonly(tidal_q.copy()),
        logarithmic_breathing_rate_s1=_readonly(breathing_rate.copy()),
        quasi_static_ratio=_readonly(quasi_static.copy()),
        one_face_surface_flux_erg_s_cm2=_readonly(surface_flux),
        electron_scattering_depth_to_midplane=_readonly(scattering_depth),
        scale_height_light_crossing_s=_readonly(light_crossing),
        scattering_transport_time_proxy_s=_readonly(scattering_transport),
        vertical_response_time_s=_readonly(vertical_response),
        vertical_profile=vertical_profile,
    )


@dataclass(frozen=True)
class DepthDissipationProfile:
    """外部耗散闭合必须满足的单位积分接口；本模块不选择物理形状。"""

    mass_fraction: ArrayLike
    differential_power_fraction: ArrayLike
    provenance: str
    normalization_tolerance: float = 1.0e-10

    def __post_init__(self) -> None:
        coordinate = np.array(self.mass_fraction, dtype=np.float64, copy=True)
        density = np.array(self.differential_power_fraction, dtype=np.float64, copy=True)
        if coordinate.ndim != 1 or coordinate.size < 2 or density.shape != coordinate.shape:
            raise PhysicalDomainError("dissipation profile arrays must be matching 1D arrays")
        if not np.all(np.isfinite(coordinate)) or np.any(np.diff(coordinate) <= 0.0):
            raise PhysicalDomainError("mass_fraction must be finite and strictly increasing")
        if coordinate[0] != 0.0 or coordinate[-1] != 1.0:
            raise PhysicalDomainError("mass_fraction must span exactly [0, 1]")
        if not np.all(np.isfinite(density)) or np.any(density < 0.0):
            raise PhysicalDomainError("differential_power_fraction must be finite and non-negative")
        tolerance = float(self.normalization_tolerance)
        if not np.isfinite(tolerance) or tolerance <= 0.0:
            raise PhysicalDomainError("normalization_tolerance must be finite and positive")
        integral = float(np.trapezoid(density, coordinate))
        # 中文：不在这里事后重归一化；未闭合的耗散输入直接拒绝。
        if not np.isclose(integral, 1.0, rtol=tolerance, atol=tolerance):
            raise PhysicalDomainError(
                f"dissipation profile integral must equal one; got {integral:.16g}"
            )
        provenance = str(self.provenance).strip()
        if not provenance:
            raise PhysicalDomainError("dissipation profile requires non-empty provenance")
        object.__setattr__(self, "mass_fraction", _readonly(coordinate))
        object.__setattr__(self, "differential_power_fraction", _readonly(density))
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "normalization_tolerance", tolerance)


def validate_rate_generators(rate_matrices_s1: ArrayLike) -> NDArray[np.float64]:
    """验证列向量约定 ``dn/dt=R@n`` 的守恒率矩阵。"""
    rates = np.array(rate_matrices_s1, dtype=np.float64, copy=True)
    if rates.ndim not in (2, 3) or rates.shape[-1] != rates.shape[-2] or rates.shape[-1] < 2:
        raise PhysicalDomainError("rate generators must have shape (n,n) or (phase,n,n), n>=2")
    if not np.all(np.isfinite(rates)):
        raise PhysicalDomainError("rate generators must be finite")
    species = rates.shape[-1]
    diagonal_mask = np.eye(species, dtype=bool)
    off_diagonal = rates[..., ~diagonal_mask]
    diagonal = np.diagonal(rates, axis1=-2, axis2=-1)
    if np.any(off_diagonal < 0.0):
        raise PhysicalDomainError("off-diagonal transition rates must be non-negative")
    if np.any(diagonal > 0.0):
        raise PhysicalDomainError("diagonal loss rates must be non-positive")
    column_sum = np.sum(rates, axis=-2)
    scale = np.max(np.abs(rates), axis=(-2, -1))
    allowed = 32.0 * np.finfo(np.float64).eps * species * scale
    if np.any(np.max(np.abs(column_sum), axis=-1) > allowed):
        raise PhysicalDomainError("rate-generator columns must sum to zero")
    return _readonly(rates)


@dataclass(frozen=True)
class PeriodicRateSolution:
    """一个守恒率网络的离散周期稳定态。"""

    population: NDArray[np.float64]
    end_population: NDArray[np.float64]
    cycles: int
    cycle_residual: float
    maximum_particle_conservation_residual: float
    minimum_population: float


def _propagate_one_cycle(
    rates: NDArray[np.float64],
    step_duration_s: NDArray[np.float64],
    initial_population: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64], float, float]:
    phase_points, species, _ = rates.shape
    state = initial_population.copy()
    trajectory = np.empty((phase_points, species), dtype=np.float64)
    total = float(np.sum(initial_population))
    maximum_conservation_residual = 0.0
    minimum_population = float(np.min(initial_population))
    for phase in range(phase_points):
        trajectory[phase] = state
        following = (phase + 1) % phase_points
        # 中文：线性插值率矩阵的一阶 Magnus 步保持生成元结构；不裁剪或重归一化。
        interval_generator = 0.5 * (rates[phase] + rates[following])
        state = expm(step_duration_s[phase] * interval_generator) @ state
        if not np.all(np.isfinite(state)):
            raise ArithmeticError("rate-network population became non-finite")
        if np.any(state < 0.0):
            raise ArithmeticError("rate-network population became negative")
        conservation = abs(float(np.sum(state)) - total) / total
        maximum_conservation_residual = max(maximum_conservation_residual, conservation)
        minimum_population = min(minimum_population, float(np.min(state)))
    return trajectory, state, maximum_conservation_residual, minimum_population


def solve_periodic_rate_network(
    rate_matrices_s1: ArrayLike,
    step_duration_s: ArrayLike,
    initial_population: ArrayLike,
    *,
    cycle_tolerance: float = 1.0e-11,
    conservation_tolerance: float = 1.0e-10,
    maximum_cycles: int = 2000,
) -> PeriodicRateSolution:
    """用整轨道迭代寻找周期布居，不施加 floor 或重归一化。"""
    rates = validate_rate_generators(rate_matrices_s1)
    if rates.ndim != 3:
        raise PhysicalDomainError("periodic rate solve requires one generator per phase interval")
    duration = np.array(step_duration_s, dtype=np.float64, copy=True)
    if duration.ndim != 1 or duration.shape[0] != rates.shape[0]:
        raise PhysicalDomainError("step_duration_s must match the rate phase axis")
    if not np.all(np.isfinite(duration)) or np.any(duration <= 0.0):
        raise PhysicalDomainError("step durations must be finite and positive")
    state = np.array(initial_population, dtype=np.float64, copy=True)
    if state.ndim != 1 or state.shape[0] != rates.shape[-1]:
        raise PhysicalDomainError("initial_population must match the species axis")
    if not np.all(np.isfinite(state)) or np.any(state < 0.0):
        raise PhysicalDomainError("initial_population must be finite and non-negative")
    total = float(np.sum(state))
    if total <= 0.0:
        raise PhysicalDomainError("initial_population must have positive total abundance")
    cycle_tolerance = float(cycle_tolerance)
    conservation_tolerance = float(conservation_tolerance)
    if (
        not np.isfinite(cycle_tolerance)
        or cycle_tolerance <= 0.0
        or not np.isfinite(conservation_tolerance)
        or conservation_tolerance <= 0.0
    ):
        raise PhysicalDomainError("solver tolerances must be finite and positive")
    if not isinstance(maximum_cycles, (int, np.integer)) or int(maximum_cycles) < 1:
        raise PhysicalDomainError("maximum_cycles must be a positive integer")

    maximum_conservation = 0.0
    minimum_population = float(np.min(state))
    for cycle in range(1, int(maximum_cycles) + 1):
        trajectory, end_state, conservation, minimum = _propagate_one_cycle(
            rates, duration, state
        )
        maximum_conservation = max(maximum_conservation, conservation)
        minimum_population = min(minimum_population, minimum)
        residual = float(np.max(np.abs(end_state - state)) / total)
        if maximum_conservation > conservation_tolerance:
            raise ArithmeticError(
                "rate-network particle conservation exceeded the requested tolerance"
            )
        if residual < cycle_tolerance:
            return PeriodicRateSolution(
                population=_readonly(trajectory),
                end_population=_readonly(end_state),
                cycles=cycle,
                cycle_residual=residual,
                maximum_particle_conservation_residual=maximum_conservation,
                minimum_population=minimum_population,
            )
        state = end_state
    raise RuntimeError("periodic rate network did not converge within maximum_cycles")


@dataclass(frozen=True)
class TwoStatePeriodicControl:
    """有连续解析周期解的两态数值控制问题。"""

    rate_matrices_s1: NDArray[np.float64]
    equilibrium_excited_fraction: NDArray[np.float64]
    analytic_excited_fraction: NDArray[np.float64]
    relaxation_time_over_period: float
    analytic_amplitude_ratio: float
    analytic_phase_lag_rad: float


def two_state_periodic_control(
    mean_anomaly_rad: ArrayLike,
    orbital_period_s: float,
    relaxation_time_over_period: float,
    *,
    equilibrium_mean: float = 0.5,
    equilibrium_amplitude: float = 0.4,
) -> TwoStatePeriodicControl:
    """构造 ``dx/dt=k[x_eq(t)-x]`` 的周期两态控制。

    这里的两个状态与跃迁率都不对应具体原子，只用于验证时间推进、相位滞后、
    周期边界、非负性和粒子守恒。
    """
    phase = np.asarray(mean_anomaly_rad, dtype=np.float64)
    if phase.ndim != 1 or phase.size < 4 or not np.all(np.isfinite(phase)):
        raise PhysicalDomainError("mean_anomaly_rad must be a finite 1D phase grid")
    period = float(orbital_period_s)
    ratio = float(relaxation_time_over_period)
    mean = float(equilibrium_mean)
    amplitude = float(equilibrium_amplitude)
    if not np.isfinite(period) or period <= 0.0 or not np.isfinite(ratio) or ratio <= 0.0:
        raise PhysicalDomainError("period and relaxation ratio must be finite and positive")
    if (
        not np.isfinite(mean)
        or not np.isfinite(amplitude)
        or amplitude <= 0.0
        or mean - amplitude <= 0.0
        or mean + amplitude >= 1.0
    ):
        raise PhysicalDomainError("equilibrium control must remain strictly between zero and one")
    equilibrium = mean + amplitude * np.cos(phase)
    relaxation_rate = 1.0 / (ratio * period)
    upward = relaxation_rate * equilibrium
    downward = relaxation_rate * (1.0 - equilibrium)
    rates = np.empty((phase.size, 2, 2), dtype=np.float64)
    rates[:, 0, 0] = -upward
    rates[:, 1, 0] = upward
    rates[:, 0, 1] = downward
    rates[:, 1, 1] = -downward
    rates = validate_rate_generators(rates)
    angular_frequency = 2.0 * np.pi / period
    lag = float(np.arctan(angular_frequency / relaxation_rate))
    response_amplitude_ratio = float(
        relaxation_rate / np.sqrt(relaxation_rate**2 + angular_frequency**2)
    )
    analytic = mean + amplitude * response_amplitude_ratio * np.cos(phase - lag)
    return TwoStatePeriodicControl(
        rate_matrices_s1=rates,
        equilibrium_excited_fraction=_readonly(equilibrium),
        analytic_excited_fraction=_readonly(analytic),
        relaxation_time_over_period=ratio,
        analytic_amplitude_ratio=response_amplitude_ratio,
        analytic_phase_lag_rad=lag,
    )


def periodic_first_harmonic(
    values: ArrayLike,
    phase_rad: ArrayLike,
    step_duration_s: ArrayLike,
) -> tuple[float, float, float]:
    """按真实轨道时间权重拟合 ``mean+A*cos(phase-lag)``。"""
    value = np.asarray(values, dtype=np.float64)
    phase = np.asarray(phase_rad, dtype=np.float64)
    duration = np.asarray(step_duration_s, dtype=np.float64)
    if value.ndim != 1 or phase.shape != value.shape or duration.shape != value.shape:
        raise PhysicalDomainError("harmonic inputs must be matching 1D arrays")
    if (
        not np.all(np.isfinite(value))
        or not np.all(np.isfinite(phase))
        or not np.all(np.isfinite(duration))
        or np.any(duration <= 0.0)
    ):
        raise PhysicalDomainError("harmonic inputs must be finite with positive durations")
    design = np.column_stack((np.ones_like(phase), np.cos(phase), np.sin(phase)))
    weighted_design = design * np.sqrt(duration)[:, None]
    weighted_value = value * np.sqrt(duration)
    coefficients, _, rank, _ = np.linalg.lstsq(weighted_design, weighted_value, rcond=None)
    if rank != 3:
        raise ArithmeticError("periodic harmonic design is rank deficient")
    amplitude = float(np.hypot(coefficients[1], coefficients[2]))
    lag = float(np.arctan2(coefficients[2], coefficients[1]))
    return float(coefficients[0]), amplitude, lag
