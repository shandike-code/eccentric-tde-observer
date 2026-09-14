"""ZO 三维无扭曲偏心盘的非线性局域 Hamiltonian 核。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from .source import PhysicalDomainError
from .zo_reference import ADIABATIC_INDEX, VerticalBreathingConvergenceError


@dataclass(frozen=True)
class UntwistedHamiltonianState:
    """给定 ``e`` 和 ``f=e+a de/da`` 时的周期呼吸解与 ZO Eq. (34)。"""

    eccentricity: float
    eccentricity_plus_gradient: float
    orbital_nonlinearity: float
    eccentric_anomaly_rad: NDArray[np.float64]
    dimensionless_height: NDArray[np.float64]
    log_height_derivative_per_rad: NDArray[np.float64]
    log_pericentre_height: float
    apoapsis_boundary_residual: float
    dimensionless_hamiltonian: float
    ivp_function_evaluations: int


@dataclass(frozen=True)
class ZOHamiltonianDerivatives:
    """ZO Eq. (38) 所需的局域 Hamiltonian 一、二阶偏导。"""

    dimensionless_hamiltonian: float
    derivative_e_at_fixed_f: float
    derivative_f_at_fixed_e: float
    second_derivative_ee: float
    second_derivative_ef: float
    second_derivative_ff: float
    eccentricity_step: float
    eccentricity_plus_gradient_step: float
    evaluated_state_count: int


def _readonly(values: ArrayLike) -> NDArray[np.float64]:
    array = np.array(values, dtype=np.float64, copy=True)
    array.setflags(write=False)
    return array


def _validated_untwisted_state(
    eccentricity: float,
    eccentricity_plus_gradient: float,
) -> tuple[float, float, float]:
    eccentricity = float(eccentricity)
    eccentricity_plus_gradient = float(eccentricity_plus_gradient)
    if (
        not np.isfinite(eccentricity)
        or abs(eccentricity) >= 0.99
        or not np.isfinite(eccentricity_plus_gradient)
    ):
        raise PhysicalDomainError(
            "untwisted Hamiltonian requires finite e and f with |e| < 0.99"
        )
    jacobian_mean = 1.0 - eccentricity * eccentricity_plus_gradient
    if jacobian_mean <= 0.0:
        raise PhysicalDomainError(
            "untwisted orbit has non-positive mean coordinate Jacobian"
        )
    orbital_nonlinearity = (
        eccentricity_plus_gradient - eccentricity
    ) / jacobian_mean
    if abs(orbital_nonlinearity) >= 1.0:
        raise PhysicalDomainError(
            "untwisted orbit intersects because the nonlinearity satisfies |q| >= 1"
        )
    return eccentricity, eccentricity_plus_gradient, orbital_nonlinearity


def zo_untwisted_orbital_jacobian(
    eccentricity: float,
    eccentricity_plus_gradient: float,
    eccentric_anomaly_rad: ArrayLike,
) -> NDArray[np.float64]:
    """返回 ZO Eq. (31) 在无扭曲变量 ``f=e+a de/da`` 下的 ``j``。"""
    eccentricity, eccentricity_plus_gradient, _ = _validated_untwisted_state(
        eccentricity, eccentricity_plus_gradient
    )
    anomaly = np.asarray(eccentric_anomaly_rad, dtype=np.float64)
    if not np.all(np.isfinite(anomaly)):
        raise PhysicalDomainError("eccentric anomaly must be finite")
    gradient = eccentricity_plus_gradient - eccentricity
    jacobian = (
        1.0
        - eccentricity * eccentricity_plus_gradient
        - gradient * np.cos(anomaly)
    ) / np.sqrt(1.0 - eccentricity**2)
    if not np.all(np.isfinite(jacobian)) or np.any(jacobian <= 0.0):
        raise PhysicalDomainError(
            "untwisted orbital Jacobian must remain finite and positive"
        )
    return _readonly(jacobian)


def solve_zo_untwisted_hamiltonian(
    eccentricity: float,
    eccentricity_plus_gradient: float,
    *,
    anomaly_points: int = 256,
    relative_tolerance: float = 2.0e-11,
    absolute_tolerance: float = 2.0e-13,
) -> UntwistedHamiltonianState:
    """联立求解 ZO Eqs. (34)--(35) 的正、偶、周期三维呼吸支。"""
    eccentricity, eccentricity_plus_gradient, nonlinearity = (
        _validated_untwisted_state(
            eccentricity, eccentricity_plus_gradient
        )
    )
    if (
        not isinstance(anomaly_points, (int, np.integer))
        or isinstance(anomaly_points, (bool, np.bool_))
        or int(anomaly_points) < 16
        or int(anomaly_points) % 2 != 0
    ):
        raise PhysicalDomainError(
            "anomaly_points must be an even integer at least 16"
        )
    anomaly_points = int(anomaly_points)
    for name, value in (
        ("relative_tolerance", relative_tolerance),
        ("absolute_tolerance", absolute_tolerance),
    ):
        if not np.isfinite(value) or value <= 0.0:
            raise PhysicalDomainError(f"{name} must be finite and positive")
    anomaly = np.linspace(0.0, 2.0 * np.pi, anomaly_points, endpoint=False)
    gamma = ADIABATIC_INDEX

    if eccentricity < 0.0:
        # 中文：利用 F(-e,-f)=F(e,f) 的精确半轨道平移，避开反向射击的不稳定支。
        mapped = solve_zo_untwisted_hamiltonian(
            -eccentricity,
            -eccentricity_plus_gradient,
            anomaly_points=anomaly_points,
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        )
        half_orbit = anomaly_points // 2
        height = np.roll(mapped.dimensionless_height, -half_orbit)
        derivative = np.roll(
            mapped.log_height_derivative_per_rad, -half_orbit
        )
        return UntwistedHamiltonianState(
            eccentricity=eccentricity,
            eccentricity_plus_gradient=eccentricity_plus_gradient,
            orbital_nonlinearity=nonlinearity,
            eccentric_anomaly_rad=_readonly(anomaly),
            dimensionless_height=_readonly(height),
            log_height_derivative_per_rad=_readonly(derivative),
            log_pericentre_height=float(np.log(height[0])),
            apoapsis_boundary_residual=float(derivative[half_orbit]),
            dimensionless_hamiltonian=mapped.dimensionless_hamiltonian,
            ivp_function_evaluations=mapped.ivp_function_evaluations,
        )

    if eccentricity == 0.0 and eccentricity_plus_gradient == 0.0:
        return UntwistedHamiltonianState(
            eccentricity=0.0,
            eccentricity_plus_gradient=0.0,
            orbital_nonlinearity=0.0,
            eccentric_anomaly_rad=_readonly(anomaly),
            dimensionless_height=_readonly(np.ones(anomaly_points)),
            log_height_derivative_per_rad=_readonly(
                np.zeros(anomaly_points)
            ),
            log_pericentre_height=0.0,
            apoapsis_boundary_residual=0.0,
            dimensionless_hamiltonian=float(
                (gamma + 1.0) / (2.0 * (gamma - 1.0))
            ),
            ivp_function_evaluations=0,
        )

    def local_factors(eccentric_anomaly: float) -> tuple[float, float]:
        orbital_factor = 1.0 - eccentricity * np.cos(eccentric_anomaly)
        jacobian = (
            1.0
            - eccentricity * eccentricity_plus_gradient
            - (eccentricity_plus_gradient - eccentricity)
            * np.cos(eccentric_anomaly)
        ) / np.sqrt(1.0 - eccentricity**2)
        if orbital_factor <= 0.0 or jacobian <= 0.0:
            raise PhysicalDomainError(
                "non-positive orbital factor or Jacobian in vertical solve"
            )
        return orbital_factor, jacobian

    def differential_equation(
        eccentric_anomaly: float,
        state: NDArray[np.float64],
    ) -> tuple[float, float]:
        log_height, log_height_derivative = state
        orbital_factor, jacobian = local_factors(eccentric_anomaly)
        second_derivative = (
            eccentricity
            * np.sin(eccentric_anomaly)
            / orbital_factor
            * log_height_derivative
            - log_height_derivative**2
            - 1.0 / orbital_factor
            + orbital_factor**2
            * jacobian ** (-(gamma - 1.0))
            * np.exp(-(gamma + 1.0) * log_height)
        )
        return log_height_derivative, second_derivative

    function_evaluations = 0

    def integrate(log_pericentre_height: float, *, dense_output: bool):
        nonlocal function_evaluations
        solution = solve_ivp(
            differential_equation,
            (0.0, np.pi),
            (log_pericentre_height, 0.0),
            method="DOP853",
            rtol=relative_tolerance,
            atol=absolute_tolerance,
            dense_output=dense_output,
            max_step=np.pi / 64.0,
        )
        function_evaluations += int(solution.nfev)
        if not solution.success:
            raise VerticalBreathingConvergenceError(solution.message)
        if not np.all(np.isfinite(solution.y)):
            raise VerticalBreathingConvergenceError(
                "nonlinear Eq. (35) integration produced a non-finite state"
            )
        return solution

    def boundary_residual(log_pericentre_height: float) -> float:
        return float(
            integrate(log_pericentre_height, dense_output=False).y[1, -1]
        )

    central_residual = boundary_residual(0.0)
    if central_residual == 0.0:
        lower_log_height = -1.0
        upper_log_height = 1.0
    elif central_residual > 0.0:
        upper_log_height = 0.0
        lower_log_height = -1.0
        while lower_log_height >= -64.0:
            lower_residual = boundary_residual(lower_log_height)
            if lower_residual < 0.0:
                break
            lower_log_height -= 1.0
        else:
            raise VerticalBreathingConvergenceError(
                "failed to establish the lower nonlinear shooting bracket"
            )
    else:
        lower_log_height = 0.0
        upper_log_height = 1.0
        while upper_log_height <= 64.0:
            upper_residual = boundary_residual(upper_log_height)
            if upper_residual > 0.0:
                break
            upper_log_height += 1.0
        else:
            raise VerticalBreathingConvergenceError(
                "failed to establish the upper nonlinear shooting bracket"
            )

    log_pericentre_height = float(
        brentq(
            boundary_residual,
            lower_log_height,
            upper_log_height,
            xtol=1.0e-12,
            rtol=1.0e-14,
        )
    )
    def differential_equation_with_hamiltonian(
        eccentric_anomaly: float,
        state: NDArray[np.float64],
    ) -> tuple[float, float, float]:
        derivative, second_derivative = differential_equation(
            eccentric_anomaly, state[:2]
        )
        orbital_factor, jacobian = local_factors(eccentric_anomaly)
        integrand = orbital_factor / (
            jacobian * np.exp(state[0])
        ) ** (gamma - 1.0)
        return derivative, second_derivative, integrand

    # 中文：把 Eq. (34) 积分量作为 ODE 状态自适应推进，解析极窄近心点贡献。
    solution = solve_ivp(
        differential_equation_with_hamiltonian,
        (0.0, np.pi),
        (log_pericentre_height, 0.0, 0.0),
        method="DOP853",
        rtol=relative_tolerance,
        atol=absolute_tolerance,
        dense_output=True,
        max_step=np.pi / 64.0,
    )
    function_evaluations += int(solution.nfev)
    if not solution.success or not np.all(np.isfinite(solution.y)):
        raise VerticalBreathingConvergenceError(
            "nonlinear Eq. (34)--(35) integration failed"
        )
    if solution.sol is None:
        raise VerticalBreathingConvergenceError(
            "nonlinear Eq. (35) dense solution was not constructed"
        )
    reflected_anomaly = np.where(
        anomaly <= np.pi, anomaly, 2.0 * np.pi - anomaly
    )
    half_orbit_state = solution.sol(reflected_anomaly)
    log_height = half_orbit_state[0]
    derivative_sign = np.where(anomaly <= np.pi, 1.0, -1.0)
    log_height_derivative = derivative_sign * half_orbit_state[1]
    height = np.exp(log_height)
    if not np.all(np.isfinite(height)) or np.any(height <= 0.0):
        raise VerticalBreathingConvergenceError(
            "nonlinear Eq. (35) produced an invalid positive height"
        )
    boundary_residual_value = float(solution.y[1, -1])
    if abs(boundary_residual_value) > 1.0e-8:
        raise VerticalBreathingConvergenceError(
            "nonlinear Eq. (35) apoapsis boundary residual exceeds tolerance"
        )
    hamiltonian_integral = 2.0 * float(solution.y[2, -1])
    hamiltonian = (
        (gamma + 1.0)
        / (4.0 * np.pi * (gamma - 1.0))
        * hamiltonian_integral
    )
    return UntwistedHamiltonianState(
        eccentricity=eccentricity,
        eccentricity_plus_gradient=eccentricity_plus_gradient,
        orbital_nonlinearity=nonlinearity,
        eccentric_anomaly_rad=_readonly(anomaly),
        dimensionless_height=_readonly(height),
        log_height_derivative_per_rad=_readonly(log_height_derivative),
        log_pericentre_height=log_pericentre_height,
        apoapsis_boundary_residual=boundary_residual_value,
        dimensionless_hamiltonian=float(hamiltonian),
        ivp_function_evaluations=function_evaluations,
    )


def zo_untwisted_dimensionless_hamiltonian(
    eccentricity: float,
    eccentricity_plus_gradient: float,
    *,
    anomaly_points: int = 256,
    relative_tolerance: float = 2.0e-11,
    absolute_tolerance: float = 2.0e-13,
) -> float:
    """只返回 ZO Eq. (34) 的无量纲三维 Hamiltonian。"""
    return solve_zo_untwisted_hamiltonian(
        eccentricity,
        eccentricity_plus_gradient,
        anomaly_points=anomaly_points,
        relative_tolerance=relative_tolerance,
        absolute_tolerance=absolute_tolerance,
    ).dimensionless_hamiltonian


def zo_linearized_dimensionless_hamiltonian(
    eccentricity: float,
    eccentricity_plus_gradient: float,
) -> float:
    """返回与 OL Eq. (44) 相容的三维二次 Hamiltonian。"""
    eccentricity = float(eccentricity)
    eccentricity_plus_gradient = float(eccentricity_plus_gradient)
    if not np.isfinite(eccentricity) or not np.isfinite(
        eccentricity_plus_gradient
    ):
        raise PhysicalDomainError("linearized Hamiltonian inputs must be finite")
    gamma = ADIABATIC_INDEX
    gradient = eccentricity_plus_gradient - eccentricity
    quadratic = (
        (5.0 * gamma - 9.0) * eccentricity**2
        + 2.0
        * (4.0 * gamma - 3.0)
        * eccentricity
        * gradient
        + (2.0 * gamma - 1.0) * gradient**2
    ) / (4.0 * gamma)
    return float((gamma + 1.0) / (2.0 * (gamma - 1.0)) + quadratic)


def finite_difference_zo_hamiltonian_derivatives(
    eccentricity: float,
    eccentricity_plus_gradient: float,
    *,
    eccentricity_step: float,
    eccentricity_plus_gradient_step: float,
    anomaly_points: int = 512,
) -> ZOHamiltonianDerivatives:
    """用显式五点中心模板计算 Eq. (38) 所需偏导，越域即拒绝。"""
    eccentricity, eccentricity_plus_gradient, _ = _validated_untwisted_state(
        eccentricity, eccentricity_plus_gradient
    )
    step_e = float(eccentricity_step)
    step_f = float(eccentricity_plus_gradient_step)
    if (
        not np.isfinite(step_e)
        or step_e <= 0.0
        or not np.isfinite(step_f)
        or step_f <= 0.0
    ):
        raise PhysicalDomainError("finite-difference steps must be finite and positive")
    offsets = (-2, -1, 0, 1, 2)
    values: dict[tuple[int, int], float] = {}

    def evaluate(offset_e: int, offset_f: int) -> float:
        key = (offset_e, offset_f)
        if key not in values:
            values[key] = zo_untwisted_dimensionless_hamiltonian(
                eccentricity + offset_e * step_e,
                eccentricity_plus_gradient + offset_f * step_f,
                anomaly_points=anomaly_points,
            )
        return values[key]

    for offset in offsets:
        evaluate(offset, 0)
        evaluate(0, offset)
    first_weights = {offset: weight for offset, weight in zip(
        (-2, -1, 1, 2), (1.0, -8.0, 8.0, -1.0), strict=True
    )}
    derivative_e = sum(
        weight * evaluate(offset, 0)
        for offset, weight in first_weights.items()
    ) / (12.0 * step_e)
    derivative_f = sum(
        weight * evaluate(0, offset)
        for offset, weight in first_weights.items()
    ) / (12.0 * step_f)
    second_e = (
        -evaluate(2, 0)
        + 16.0 * evaluate(1, 0)
        - 30.0 * evaluate(0, 0)
        + 16.0 * evaluate(-1, 0)
        - evaluate(-2, 0)
    ) / (12.0 * step_e**2)
    second_f = (
        -evaluate(0, 2)
        + 16.0 * evaluate(0, 1)
        - 30.0 * evaluate(0, 0)
        + 16.0 * evaluate(0, -1)
        - evaluate(0, -2)
    ) / (12.0 * step_f**2)
    mixed = 0.0
    for offset_e, weight_e in first_weights.items():
        for offset_f, weight_f in first_weights.items():
            mixed += weight_e * weight_f * evaluate(offset_e, offset_f)
    mixed /= 144.0 * step_e * step_f
    return ZOHamiltonianDerivatives(
        dimensionless_hamiltonian=evaluate(0, 0),
        derivative_e_at_fixed_f=float(derivative_e),
        derivative_f_at_fixed_e=float(derivative_f),
        second_derivative_ee=float(second_e),
        second_derivative_ef=float(mixed),
        second_derivative_ff=float(second_f),
        eccentricity_step=step_e,
        eccentricity_plus_gradient_step=step_f,
        evaluated_state_count=len(values),
    )
