"""规定加热下给定密度 H/He 连续谱板层的温度平衡。

本模块把 Phase 7B4e 的逐深度辐射净加热接入气体能量方程。它只处理
给定的标量或逐深度密度、静态、基态连续过程；碰撞电离/三体复合可作为
显式控制启用。不含激发态、线冷却、Compton 交换、压缩功或 ZO 轨道
时间推进，因此仍是温度闭合控制而不是完整 NLTE 大气。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import brentq, least_squares

from .atmosphere import (
    PROTON_MASS_G,
    SOLAR_FULLY_IONIZED_H_HE,
    FullyIonizedHydrogenHeliumComposition,
)
from .continuum_emission import (
    EmissiveCoupledSlab,
    _density_profile_g_cm3,
    solve_emissive_ground_state_slab,
)
from .radiation import BOLTZMANN_ERG_K, STEFAN_BOLTZMANN_ERG_S_CM2_K4
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


class TemperatureBalanceConvergenceError(RuntimeError):
    """温度方程未得到内部、守恒且达到容差的根。"""


@dataclass(frozen=True)
class IsothermalTemperatureRoot:
    """等温板层总能量方程的一条根及其局部稳定性。"""

    temperature_k: float
    radiative_heating_flux_erg_s_cm2: float
    supplemental_heating_flux_erg_s_cm2: float
    prescribed_heating_flux_erg_s_cm2: float
    net_heating_flux_erg_s_cm2: float
    relative_energy_residual: float
    net_heating_derivative_erg_s_cm2_k: float
    thermally_stable: bool
    slab: EmissiveCoupledSlab


@dataclass(frozen=True)
class IsothermalTemperatureScan:
    """等温温度扫描、显式失败点和全部括区间根。"""

    temperature_grid_k: NDArray[np.float64]
    radiative_heating_flux_erg_s_cm2: NDArray[np.float64]
    supplemental_heating_flux_erg_s_cm2: NDArray[np.float64]
    net_heating_flux_erg_s_cm2: NDArray[np.float64]
    valid_evaluation: NDArray[np.bool_]
    failure_messages: tuple[str | None, ...]
    roots: tuple[IsothermalTemperatureRoot, ...]


@dataclass(frozen=True)
class ThermalEquilibriumSlab:
    """逐深度温度、辐射、布居和规定加热的联立平衡。"""

    temperature_k: NDArray[np.float64]
    prescribed_heating_erg_s_cm3: NDArray[np.float64]
    supplemental_heating_erg_s_cm3: NDArray[np.float64]
    net_heating_erg_s_cm3: NDArray[np.float64]
    slab: EmissiveCoupledSlab
    maximum_relative_local_energy_residual: float
    integrated_prescribed_heating_flux_erg_s_cm2: float
    integrated_radiative_heating_flux_erg_s_cm2: float
    integrated_supplemental_heating_flux_erg_s_cm2: float
    integrated_net_heating_flux_erg_s_cm2: float
    relative_global_energy_residual: float
    temperature_jacobian_erg_s_cm3_k: NDArray[np.float64] | None
    thermal_growth_eigenvalues_s1: NDArray[np.complex128] | None
    maximum_thermal_growth_rate_s1: float | None
    thermally_stable: bool | None
    optimizer_function_evaluations: int
    optimizer_optimality: float
    temperature_bounds_k: tuple[float, float]
    mirror_symmetric_temperature: bool


SupplementalHeatingEvaluator = Callable[
    [EmissiveCoupledSlab, NDArray[np.float64]], ArrayLike
]


def one_face_blackbody_dissipation_flux_erg_s_cm2(
    effective_temperature_k: float,
) -> float:
    """把一面有效温度转换为可追溯的 Stefan--Boltzmann 耗散通量。"""
    temperature = float(effective_temperature_k)
    if not np.isfinite(temperature) or temperature <= 0.0:
        raise PhysicalDomainError(
            "effective_temperature_k must be finite and strictly positive"
        )
    return STEFAN_BOLTZMANN_ERG_S_CM2_K4 * temperature**4


def uniform_fixed_density_heating_erg_s_cm3(
    one_face_heating_flux_erg_s_cm2: float,
    depth_edges_cm: ArrayLike,
) -> NDArray[np.float64]:
    """把一面总耗散均匀分配到固定密度板层的几何厚度。"""
    flux = float(one_face_heating_flux_erg_s_cm2)
    edges = np.asarray(depth_edges_cm, dtype=np.float64)
    if not np.isfinite(flux) or flux < 0.0:
        raise PhysicalDomainError(
            "one_face_heating_flux_erg_s_cm2 must be finite and non-negative"
        )
    if (
        edges.ndim != 1
        or edges.size < 2
        or not np.all(np.isfinite(edges))
        or np.any(np.diff(edges) <= 0.0)
    ):
        raise PhysicalDomainError(
            "depth_edges_cm must be finite and strictly increasing"
        )
    heating = np.full(edges.size - 1, flux / (edges[-1] - edges[0]))
    return _readonly(heating)


def sampled_temperature_root_intervals(
    temperature_k: ArrayLike,
    net_heating: ArrayLike,
) -> tuple[tuple[float, float], ...]:
    """返回采样曲线的精确零点或相邻异号括区间，不跨越缺失点。"""
    temperature = np.asarray(temperature_k, dtype=np.float64)
    residual = np.asarray(net_heating, dtype=np.float64)
    if (
        temperature.ndim != 1
        or residual.shape != temperature.shape
        or temperature.size < 2
        or not np.all(np.isfinite(temperature))
        or not np.all(np.isfinite(residual))
        or np.any(temperature <= 0.0)
        or np.any(np.diff(temperature) <= 0.0)
    ):
        raise PhysicalDomainError(
            "temperature and net-heating samples must be finite ordered 1D arrays"
        )
    intervals: list[tuple[float, float]] = []
    for index, value in enumerate(residual):
        if value == 0.0:
            intervals.append((float(temperature[index]), float(temperature[index])))
        if index + 1 < residual.size and value * residual[index + 1] < 0.0:
            intervals.append(
                (float(temperature[index]), float(temperature[index + 1]))
            )
    return tuple(intervals)


def _validate_heating_profile(
    prescribed_heating_erg_s_cm3: ArrayLike,
    depth_points: int,
) -> NDArray[np.float64]:
    heating = np.asarray(prescribed_heating_erg_s_cm3, dtype=np.float64)
    try:
        profile = np.array(
            np.broadcast_to(heating, (depth_points,)), dtype=np.float64, copy=True
        )
    except ValueError as error:
        raise PhysicalDomainError(
            "prescribed_heating_erg_s_cm3 must be scalar or depth-resolved"
        ) from error
    if not np.all(np.isfinite(profile)) or np.any(profile < 0.0):
        raise PhysicalDomainError(
            "prescribed_heating_erg_s_cm3 must be finite and non-negative"
        )
    return _readonly(profile)


def _evaluate_supplemental_heating(
    evaluator: SupplementalHeatingEvaluator | None,
    slab: EmissiveCoupledSlab,
    temperature_k: NDArray[np.float64],
    depth_points: int,
) -> NDArray[np.float64]:
    """计算可选附加能量项；允许加热或冷却，但拒绝非有限输出。"""
    if evaluator is None:
        return _readonly(np.zeros(depth_points, dtype=np.float64))
    values = np.asarray(evaluator(slab, temperature_k), dtype=np.float64)
    try:
        profile = np.array(
            np.broadcast_to(values, (depth_points,)), dtype=np.float64, copy=True
        )
    except ValueError as error:
        raise PhysicalDomainError(
            "supplemental heating evaluator must return scalar or depth-resolved values"
        ) from error
    if not np.all(np.isfinite(profile)):
        raise PhysicalDomainError(
            "supplemental heating evaluator returned non-finite values"
        )
    return _readonly(profile)


def _gross_boundary_energy_scale_erg_s_cm2(slab: EmissiveCoupledSlab) -> float:
    """返回两侧边界中较大的总方向能流，用作守恒残差尺度。"""
    transfer = slab.transfer
    mu = transfer.direction_cosine
    weight = transfer.angular_weight
    top_frequency = 2.0 * np.pi * np.einsum(
        "m,fm,m->f", weight, transfer.top_boundary_intensity, np.abs(mu)
    )
    bottom_frequency = 2.0 * np.pi * np.einsum(
        "m,fm,m->f", weight, transfer.bottom_boundary_intensity, np.abs(mu)
    )
    top = float(np.trapezoid(top_frequency, transfer.frequency_hz))
    bottom = float(np.trapezoid(bottom_frequency, transfer.frequency_hz))
    return max(top, bottom)


def scan_isothermal_temperature_balance(
    temperature_grid_k: ArrayLike,
    frequency_hz: ArrayLike,
    depth_edges_cm: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    density_g_cm3: ArrayLike,
    top_incoming_intensity: ArrayLike,
    bottom_incoming_intensity: ArrayLike,
    prescribed_heating_erg_s_cm3: ArrayLike,
    initial_hydrogen_fraction: ArrayLike,
    initial_helium_fraction: ArrayLike,
    *,
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
    include_electron_scattering: bool = True,
    include_collisional_kinetics: bool = False,
    initialize_collisional_population_from_lte: bool = False,
    population_relaxation: float = 1.0,
    population_tolerance: float = 1.0e-9,
    population_maximum_iterations: int = 512,
    root_relative_temperature_tolerance: float = 1.0e-9,
    stability_relative_step: float = 1.0e-3,
    supplemental_heating_evaluator: SupplementalHeatingEvaluator | None = None,
) -> IsothermalTemperatureScan:
    """扫描等温能量曲线并在每个连续有效括区间中独立精化根。"""
    temperature = np.asarray(temperature_grid_k, dtype=np.float64)
    if (
        temperature.ndim != 1
        or temperature.size < 2
        or not np.all(np.isfinite(temperature))
        or np.any(temperature <= 0.0)
        or np.any(np.diff(temperature) <= 0.0)
    ):
        raise PhysicalDomainError(
            "temperature_grid_k must be finite, positive and strictly increasing"
        )
    edges = np.asarray(depth_edges_cm, dtype=np.float64)
    if (
        edges.ndim != 1
        or edges.size < 2
        or not np.all(np.isfinite(edges))
        or np.any(np.diff(edges) <= 0.0)
    ):
        raise PhysicalDomainError(
            "depth_edges_cm must be finite and strictly increasing"
        )
    heating = _validate_heating_profile(
        prescribed_heating_erg_s_cm3, edges.size - 1
    )
    heating_flux = float(np.sum(heating * np.diff(edges)))
    if (
        not np.isfinite(root_relative_temperature_tolerance)
        or root_relative_temperature_tolerance <= 0.0
        or not np.isfinite(stability_relative_step)
        or stability_relative_step <= 0.0
    ):
        raise PhysicalDomainError("root and stability tolerances must be positive")

    cache: dict[float, tuple[float, EmissiveCoupledSlab, float]] = {}

    def evaluate(value: float) -> tuple[float, EmissiveCoupledSlab, float]:
        key = float(value)
        if key not in cache:
            slab = solve_emissive_ground_state_slab(
                frequency_hz,
                edges,
                direction_cosine,
                angular_weight,
                density_g_cm3,
                key,
                top_incoming_intensity,
                bottom_incoming_intensity,
                initial_hydrogen_fraction,
                initial_helium_fraction,
                composition=composition,
                include_electron_scattering=include_electron_scattering,
                include_collisional_kinetics=include_collisional_kinetics,
                initialize_collisional_population_from_lte=(
                    initialize_collisional_population_from_lte
                ),
                relaxation=population_relaxation,
                tolerance=population_tolerance,
                maximum_iterations=population_maximum_iterations,
            )
            radiative_flux = float(
                np.sum(slab.radiative_heating_erg_s_cm3 * np.diff(edges))
            )
            supplemental = _evaluate_supplemental_heating(
                supplemental_heating_evaluator,
                slab,
                np.full(edges.size - 1, key),
                edges.size - 1,
            )
            supplemental_flux = float(np.sum(supplemental * np.diff(edges)))
            cache[key] = (
                heating_flux + radiative_flux + supplemental_flux,
                slab,
                supplemental_flux,
            )
        return cache[key]

    net = np.empty(temperature.size, dtype=np.float64)
    radiative = np.empty_like(net)
    supplemental = np.empty_like(net)
    valid = np.zeros(temperature.size, dtype=np.bool_)
    failures: list[str | None] = []
    for index, value in enumerate(temperature):
        try:
            net[index], slab, supplemental[index] = evaluate(float(value))
        except (PhysicalDomainError, RuntimeError, ArithmeticError) as error:
            net[index] = 0.0
            radiative[index] = 0.0
            supplemental[index] = 0.0
            failures.append(f"{type(error).__name__}: {error}")
            continue
        radiative[index] = net[index] - heating_flux - supplemental[index]
        valid[index] = True
        failures.append(None)

    intervals: list[tuple[float, float]] = []
    for index in range(temperature.size):
        if not valid[index]:
            continue
        if net[index] == 0.0:
            intervals.append((float(temperature[index]), float(temperature[index])))
        if (
            index + 1 < temperature.size
            and valid[index + 1]
            and net[index] * net[index + 1] < 0.0
        ):
            intervals.append((float(temperature[index]), float(temperature[index + 1])))

    roots: list[IsothermalTemperatureRoot] = []
    for lower, upper in intervals:
        if lower == upper:
            root_temperature = lower
        else:
            root_temperature = float(
                brentq(
                    lambda trial: evaluate(float(trial))[0],
                    lower,
                    upper,
                    xtol=root_relative_temperature_tolerance * lower,
                    rtol=root_relative_temperature_tolerance,
                )
            )
        if roots and abs(root_temperature - roots[-1].temperature_k) <= (
            root_relative_temperature_tolerance * root_temperature
        ):
            continue
        root_net, slab, root_supplemental = evaluate(root_temperature)
        root_radiative = root_net - heating_flux - root_supplemental
        step = stability_relative_step * root_temperature
        if root_temperature - step <= temperature[0] or root_temperature + step >= temperature[-1]:
            raise TemperatureBalanceConvergenceError(
                "a temperature root lies too close to the scan boundary for stability analysis"
            )
        lower_net, _, _ = evaluate(root_temperature - step)
        upper_net, _, _ = evaluate(root_temperature + step)
        derivative = (upper_net - lower_net) / (2.0 * step)
        scale = max(
            abs(heating_flux),
            abs(root_radiative),
            abs(root_supplemental),
            _gross_boundary_energy_scale_erg_s_cm2(slab),
        )
        relative = abs(root_net) / scale if scale > 0.0 else abs(root_net)
        roots.append(
            IsothermalTemperatureRoot(
                temperature_k=root_temperature,
                radiative_heating_flux_erg_s_cm2=root_radiative,
                supplemental_heating_flux_erg_s_cm2=root_supplemental,
                prescribed_heating_flux_erg_s_cm2=heating_flux,
                net_heating_flux_erg_s_cm2=root_net,
                relative_energy_residual=relative,
                net_heating_derivative_erg_s_cm2_k=derivative,
                thermally_stable=bool(derivative < 0.0),
                slab=slab,
            )
        )
    return IsothermalTemperatureScan(
        temperature_grid_k=_readonly(np.array(temperature, copy=True)),
        radiative_heating_flux_erg_s_cm2=_readonly(radiative),
        supplemental_heating_flux_erg_s_cm2=_readonly(supplemental),
        net_heating_flux_erg_s_cm2=_readonly(net),
        valid_evaluation=_readonly(valid),
        failure_messages=tuple(failures),
        roots=tuple(roots),
    )


def solve_prescribed_heating_temperature_profile(
    frequency_hz: ArrayLike,
    depth_edges_cm: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    density_g_cm3: ArrayLike,
    top_incoming_intensity: ArrayLike,
    bottom_incoming_intensity: ArrayLike,
    prescribed_heating_erg_s_cm3: ArrayLike,
    initial_temperature_k: ArrayLike,
    initial_hydrogen_fraction: ArrayLike,
    initial_helium_fraction: ArrayLike,
    *,
    temperature_bounds_k: tuple[float, float],
    composition: FullyIonizedHydrogenHeliumComposition = SOLAR_FULLY_IONIZED_H_HE,
    include_electron_scattering: bool = True,
    include_collisional_kinetics: bool = False,
    initialize_collisional_population_from_lte: bool = False,
    population_relaxation: float = 1.0,
    population_tolerance: float = 1.0e-9,
    population_maximum_iterations: int = 512,
    local_energy_tolerance: float = 1.0e-6,
    optimizer_tolerance: float = 1.0e-8,
    maximum_function_evaluations: int = 512,
    stability_relative_step: float = 1.0e-3,
    analyze_stability: bool = True,
    mirror_symmetric_temperature: bool = False,
    supplemental_heating_evaluator: SupplementalHeatingEvaluator | None = None,
) -> ThermalEquilibriumSlab:
    """在声明的温度域内联立逐深度温度与基态连续转移。

    温度采用对数变量并由有界最小二乘寻找根。边界只定义原子闭合的声明域；
    若解停在边界或只有非零最小残差，本函数明确失败，不把边界值当成答案。
    """
    edges = np.asarray(depth_edges_cm, dtype=np.float64)
    if (
        edges.ndim != 1
        or edges.size < 2
        or not np.all(np.isfinite(edges))
        or np.any(np.diff(edges) <= 0.0)
    ):
        raise PhysicalDomainError(
            "depth_edges_cm must be finite and strictly increasing"
        )
    depth_points = edges.size - 1
    heating = _validate_heating_profile(prescribed_heating_erg_s_cm3, depth_points)
    initial = np.asarray(initial_temperature_k, dtype=np.float64)
    try:
        initial = np.array(
            np.broadcast_to(initial, (depth_points,)), dtype=np.float64, copy=True
        )
    except ValueError as error:
        raise PhysicalDomainError(
            "initial_temperature_k must be scalar or depth-resolved"
        ) from error
    lower, upper = (float(value) for value in temperature_bounds_k)
    if (
        not np.isfinite(lower)
        or not np.isfinite(upper)
        or lower <= 0.0
        or upper <= lower
        or not np.all(np.isfinite(initial))
        or np.any(initial <= lower)
        or np.any(initial >= upper)
    ):
        raise PhysicalDomainError(
            "initial temperatures must lie strictly inside finite positive bounds"
        )
    controls = (
        local_energy_tolerance,
        optimizer_tolerance,
        stability_relative_step,
    )
    if any(not np.isfinite(value) or value <= 0.0 for value in controls):
        raise PhysicalDomainError("thermal solver tolerances must be finite and positive")
    if maximum_function_evaluations < 1:
        raise PhysicalDomainError("maximum_function_evaluations must be positive")
    if not isinstance(analyze_stability, (bool, np.bool_)):
        raise PhysicalDomainError("analyze_stability must be boolean")
    if not isinstance(mirror_symmetric_temperature, (bool, np.bool_)):
        raise PhysicalDomainError("mirror_symmetric_temperature must be boolean")
    if mirror_symmetric_temperature:
        if depth_points % 2 != 0:
            raise PhysicalDomainError(
                "mirror-symmetric temperature solve requires an even depth count"
            )
        if not np.array_equal(heating, heating[::-1]):
            raise PhysicalDomainError(
                "mirror-symmetric temperature solve requires symmetric heating"
            )
        density_profile = _density_profile_g_cm3(density_g_cm3, depth_points)
        if not np.array_equal(density_profile, density_profile[::-1]):
            raise PhysicalDomainError(
                "mirror-symmetric temperature solve requires symmetric density"
            )
        if not np.array_equal(initial, initial[::-1]):
            raise PhysicalDomainError(
                "mirror-symmetric temperature solve requires a symmetric initial profile"
            )

    def evaluate(
        temperature: NDArray[np.float64],
    ) -> tuple[EmissiveCoupledSlab, NDArray[np.float64]]:
        slab = solve_emissive_ground_state_slab(
            frequency_hz,
            edges,
            direction_cosine,
            angular_weight,
            density_g_cm3,
            temperature,
            top_incoming_intensity,
            bottom_incoming_intensity,
            initial_hydrogen_fraction,
            initial_helium_fraction,
            composition=composition,
            include_electron_scattering=include_electron_scattering,
            include_collisional_kinetics=include_collisional_kinetics,
            initialize_collisional_population_from_lte=(
                initialize_collisional_population_from_lte
            ),
            relaxation=population_relaxation,
            tolerance=population_tolerance,
            maximum_iterations=population_maximum_iterations,
        )
        supplemental = _evaluate_supplemental_heating(
            supplemental_heating_evaluator,
            slab,
            temperature,
            depth_points,
        )
        return slab, supplemental

    initial_slab, initial_supplemental = evaluate(initial)
    energy_scale = max(
        float(np.max(np.abs(heating))),
        float(np.max(np.abs(initial_slab.radiative_heating_erg_s_cm3))),
        float(np.max(np.abs(initial_supplemental))),
    )
    if energy_scale == 0.0:
        raise PhysicalDomainError(
            "an identically zero initial energy scale cannot normalize the thermal solve"
        )

    half_depth_points = depth_points // 2

    def expanded_temperature(log_temperature: NDArray[np.float64]) -> NDArray[np.float64]:
        half_temperature = np.exp(log_temperature)
        if mirror_symmetric_temperature:
            return np.concatenate((half_temperature, half_temperature[::-1]))
        return half_temperature

    def normalized_residual(log_temperature: NDArray[np.float64]) -> NDArray[np.float64]:
        trial_temperature = expanded_temperature(log_temperature)
        slab, supplemental = evaluate(trial_temperature)
        residual = (
            heating + slab.radiative_heating_erg_s_cm3 + supplemental
        ) / energy_scale
        if mirror_symmetric_temperature:
            return 0.5 * (
                residual[:half_depth_points]
                + residual[: half_depth_points - 1 : -1]
            )
        return residual

    initial_optimizer_temperature = (
        initial[:half_depth_points] if mirror_symmetric_temperature else initial
    )
    optimizer_depth_points = initial_optimizer_temperature.size

    optimization = least_squares(
        normalized_residual,
        np.log(initial_optimizer_temperature),
        bounds=(
            np.full(optimizer_depth_points, np.log(lower)),
            np.full(optimizer_depth_points, np.log(upper)),
        ),
        ftol=optimizer_tolerance,
        xtol=optimizer_tolerance,
        gtol=optimizer_tolerance,
        max_nfev=int(maximum_function_evaluations),
    )
    temperature = expanded_temperature(optimization.x)
    slab, supplemental = evaluate(temperature)
    net = heating + slab.radiative_heating_erg_s_cm3 + supplemental
    maximum_relative = float(np.max(np.abs(net)) / energy_scale)
    boundary_distance = np.minimum(temperature / lower - 1.0, upper / temperature - 1.0)
    if (
        not optimization.success
        or maximum_relative > local_energy_tolerance
        or np.any(boundary_distance <= np.sqrt(np.finfo(np.float64).eps))
    ):
        raise TemperatureBalanceConvergenceError(
            "temperature solve found no accepted interior root: "
            f"success={optimization.success}, max_relative_residual={maximum_relative:.6e}, "
            f"minimum_relative_boundary_distance={float(np.min(boundary_distance)):.6e}"
        )

    jacobian: NDArray[np.float64] | None = None
    eigenvalues: NDArray[np.complex128] | None = None
    maximum_growth: float | None = None
    thermally_stable: bool | None = None
    if analyze_stability:
        # 中文：完整重算辐射--布居固定点，有限差分温度耦合矩阵，不冻结 J_nu 或布居。
        jacobian = np.empty((depth_points, depth_points), dtype=np.float64)
        for column in range(depth_points):
            downward = np.array(temperature, copy=True)
            upward = np.array(temperature, copy=True)
            downward[column] *= np.exp(-stability_relative_step)
            upward[column] *= np.exp(stability_relative_step)
            if downward[column] <= lower or upward[column] >= upper:
                raise TemperatureBalanceConvergenceError(
                    "accepted root is too close to a temperature bound for stability analysis"
                )
            downward_slab, downward_supplemental = evaluate(downward)
            upward_slab, upward_supplemental = evaluate(upward)
            downward_net = (
                heating
                + downward_slab.radiative_heating_erg_s_cm3
                + downward_supplemental
            )
            upward_net = (
                heating
                + upward_slab.radiative_heating_erg_s_cm3
                + upward_supplemental
            )
            jacobian[:, column] = (upward_net - downward_net) / (
                upward[column] - downward[column]
            )

        density = _density_profile_g_cm3(density_g_cm3, depth_points)
        hydrogen_nuclei = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
        helium_nuclei = composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
        # 中文：稳定性控制只用正的单原子平动热容；激发/电离内能仍属开放物理。
        heat_capacity = 1.5 * BOLTZMANN_ERG_K * (
            hydrogen_nuclei + helium_nuclei + slab.population.electron_density_cm3
        )
        growth_matrix = jacobian / heat_capacity[:, None]
        eigenvalues = np.asarray(np.linalg.eigvals(growth_matrix), dtype=np.complex128)
        maximum_growth = float(np.max(eigenvalues.real))
        thermally_stable = bool(maximum_growth < 0.0)

    widths = np.diff(edges)
    heating_flux = float(np.sum(heating * widths))
    radiative_flux = float(np.sum(slab.radiative_heating_erg_s_cm3 * widths))
    supplemental_flux = float(np.sum(supplemental * widths))
    net_flux = heating_flux + radiative_flux + supplemental_flux
    global_scale = max(
        abs(heating_flux),
        abs(radiative_flux),
        abs(supplemental_flux),
        _gross_boundary_energy_scale_erg_s_cm2(slab),
    )
    relative_global = abs(net_flux) / global_scale if global_scale > 0.0 else abs(net_flux)
    return ThermalEquilibriumSlab(
        temperature_k=_readonly(np.array(temperature, copy=True)),
        prescribed_heating_erg_s_cm3=_readonly(np.array(heating, copy=True)),
        supplemental_heating_erg_s_cm3=_readonly(
            np.array(supplemental, copy=True)
        ),
        net_heating_erg_s_cm3=_readonly(np.array(net, copy=True)),
        slab=slab,
        maximum_relative_local_energy_residual=maximum_relative,
        integrated_prescribed_heating_flux_erg_s_cm2=heating_flux,
        integrated_radiative_heating_flux_erg_s_cm2=radiative_flux,
        integrated_supplemental_heating_flux_erg_s_cm2=supplemental_flux,
        integrated_net_heating_flux_erg_s_cm2=net_flux,
        relative_global_energy_residual=relative_global,
        temperature_jacobian_erg_s_cm3_k=(
            _readonly(jacobian) if jacobian is not None else None
        ),
        thermal_growth_eigenvalues_s1=(
            _readonly(eigenvalues) if eigenvalues is not None else None
        ),
        maximum_thermal_growth_rate_s1=maximum_growth,
        thermally_stable=thermally_stable,
        optimizer_function_evaluations=int(optimization.nfev),
        optimizer_optimality=float(optimization.optimality),
        temperature_bounds_k=(lower, upper),
        mirror_symmetric_temperature=bool(mirror_symmetric_temperature),
    )
