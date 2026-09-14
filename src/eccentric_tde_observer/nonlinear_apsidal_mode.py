"""ZO Eq. (38) 的无扭曲非线性拱点本征模射击求解器。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.integrate import solve_bvp, solve_ivp
from scipy.optimize import brentq

from .hamiltonian_table import ZOHamiltonianSplineTable
from .source import PhysicalDomainError


@dataclass(frozen=True)
class NonlinearApsidalMode:
    """按给定内边界偏心率归一的 ZO 非线性无节点模。"""

    dimensionless_semimajor_axis: NDArray[np.float64]
    eccentricity: NDArray[np.float64]
    eccentricity_plus_gradient: NDArray[np.float64]
    orbital_nonlinearity: NDArray[np.float64]
    dimensionless_frequency: float
    inner_boundary_nonlinearity: float
    inner_boundary_residual: float
    outer_boundary_residual: float
    radial_node_count: int
    ivp_function_evaluations: int


def _readonly(values: ArrayLike) -> NDArray[np.float64]:
    array = np.array(values, dtype=np.float64, copy=True)
    array.setflags(write=False)
    return array


def zo_free_boundary_nonlinearity(
    table: ZOHamiltonianSplineTable,
    eccentricity: float,
) -> float:
    """求解 ZO Eq. (43)；在 ``(e,q)`` 坐标中它等价于 ``G_q=0``。"""
    if not isinstance(table, ZOHamiltonianSplineTable):
        raise TypeError("table must be a ZOHamiltonianSplineTable")
    eccentricity = float(eccentricity)
    q_nodes = table.nonlinearity_nodes
    derivative = np.array(
        [
            table.evaluate_e_q(
                eccentricity,
                float(q_value),
                nonlinearity_derivative_order=1,
            )
            for q_value in q_nodes
        ]
    )
    roots: list[float] = []
    for index in range(q_nodes.size - 1):
        left = float(q_nodes[index])
        right = float(q_nodes[index + 1])
        left_value = float(derivative[index])
        right_value = float(derivative[index + 1])
        if left_value == 0.0:
            roots.append(left)
        if left_value * right_value < 0.0:
            roots.append(
                float(
                    brentq(
                        lambda q_value: table.evaluate_e_q(
                            eccentricity,
                            q_value,
                            nonlinearity_derivative_order=1,
                        ),
                        left,
                        right,
                        xtol=1.0e-13,
                        rtol=1.0e-14,
                    )
                )
            )
    if derivative[-1] == 0.0:
        roots.append(float(q_nodes[-1]))
    local_minima = [
        root
        for root in roots
        if table.evaluate_e_q(
            eccentricity,
            root,
            nonlinearity_derivative_order=2,
        )
        > 0.0
    ]
    if not local_minima:
        raise PhysicalDomainError(
            "tabulated q domain does not contain a convex free-boundary root"
        )
    return min(
        local_minima,
        key=lambda root: table.evaluate_e_q(eccentricity, root),
    )


def solve_zo_nonlinear_apsidal_mode(
    table: ZOHamiltonianSplineTable,
    *,
    inner_eccentricity: float,
    outer_to_inner_semimajor_axis: float,
    delta_gr: float,
    frequency_bracket: tuple[float, float],
    radial_points: int = 512,
    relative_tolerance: float = 2.0e-9,
    absolute_tolerance: float = 2.0e-11,
) -> NonlinearApsidalMode:
    """射击求解 ZO Eq. (38) 与双端自由边界 Eq. (43)。"""
    if not isinstance(table, ZOHamiltonianSplineTable):
        raise TypeError("table must be a ZOHamiltonianSplineTable")
    inner_eccentricity = float(inner_eccentricity)
    radius_ratio = float(outer_to_inner_semimajor_axis)
    delta_gr = float(delta_gr)
    if (
        not np.isfinite(inner_eccentricity)
        or inner_eccentricity <= 0.0
        or not np.isfinite(radius_ratio)
        or radius_ratio <= 1.0
        or not np.isfinite(delta_gr)
        or delta_gr < 0.0
    ):
        raise PhysicalDomainError(
            "mode inputs require 0 < e_in, a_out/a_in > 1, and delta_gr >= 0"
        )
    if (
        not isinstance(radial_points, (int, np.integer))
        or isinstance(radial_points, (bool, np.bool_))
        or int(radial_points) < 16
    ):
        raise PhysicalDomainError("radial_points must be an integer at least 16")
    lower_frequency, upper_frequency = map(float, frequency_bracket)
    if (
        not np.isfinite(lower_frequency)
        or not np.isfinite(upper_frequency)
        or lower_frequency >= upper_frequency
    ):
        raise PhysicalDomainError("frequency_bracket must be finite and increasing")
    inner_q = zo_free_boundary_nonlinearity(table, inner_eccentricity)
    inner_f = (inner_eccentricity + inner_q) / (
        1.0 + inner_eccentricity * inner_q
    )

    def integrate(dimensionless_frequency: float, *, output: bool):
        def equation(
            scaled_semimajor_axis: float,
            state: NDArray[np.float64],
        ) -> tuple[float, float]:
            eccentricity = float(state[0])
            f_value = float(state[1])
            derivatives = table.evaluate_e_f(eccentricity, f_value)
            if derivatives.second_derivative_ff <= 0.0:
                raise PhysicalDomainError(
                    "Hamiltonian loses convexity in the radial-gradient direction"
                )
            eccentricity_gradient = f_value - eccentricity
            one_minus_e_squared = 1.0 - eccentricity**2
            if one_minus_e_squared <= 0.0:
                raise PhysicalDomainError("mode reached |e| >= 1")
            relativistic_term = (
                delta_gr
                / scaled_semimajor_axis
                * eccentricity
                / one_minus_e_squared**1.5
            )
            # 中文：因 x f_x=2x e_x+x^2 e_xx，Eq. (38) 可直接化为此一阶系统。
            f_gradient = (
                derivatives.derivative_e_at_fixed_f
                - eccentricity_gradient * derivatives.second_derivative_ef
                + 3.0 * derivatives.derivative_f_at_fixed_e
                - relativistic_term
                + dimensionless_frequency
                * scaled_semimajor_axis**1.5
                * eccentricity
                / np.sqrt(one_minus_e_squared)
            ) / (
                scaled_semimajor_axis * derivatives.second_derivative_ff
            )
            return eccentricity_gradient / scaled_semimajor_axis, f_gradient

        evaluation_grid = (
            np.linspace(1.0, radius_ratio, int(radial_points))
            if output
            else None
        )
        solution = solve_ivp(
            equation,
            (1.0, radius_ratio),
            (inner_eccentricity, inner_f),
            method="DOP853",
            rtol=relative_tolerance,
            atol=absolute_tolerance,
            t_eval=evaluation_grid,
            max_step=(radius_ratio - 1.0) / 128.0,
        )
        if not solution.success or not np.all(np.isfinite(solution.y)):
            raise PhysicalDomainError("nonlinear apsidal-mode integration failed")
        outer_derivatives = table.evaluate_e_f(
            float(solution.y[0, -1]),
            float(solution.y[1, -1]),
        )
        return float(outer_derivatives.derivative_f_at_fixed_e), solution

    def residual(dimensionless_frequency: float) -> float:
        value, _ = integrate(dimensionless_frequency, output=False)
        return value

    lower_residual = residual(lower_frequency)
    upper_residual = residual(upper_frequency)
    if lower_residual * upper_residual >= 0.0:
        raise PhysicalDomainError(
            "frequency bracket does not contain a simple outer-boundary root"
        )
    frequency = float(
        brentq(
            residual,
            lower_frequency,
            upper_frequency,
            xtol=2.0e-11,
            rtol=2.0e-11,
        )
    )
    outer_residual, solution = integrate(frequency, output=True)
    eccentricity = np.asarray(solution.y[0], dtype=np.float64)
    f_values = np.asarray(solution.y[1], dtype=np.float64)
    if np.any(eccentricity <= 0.0):
        raise PhysicalDomainError(
            "selected nonlinear apsidal branch is not the requested node-free mode"
        )
    denominator = 1.0 - eccentricity * f_values
    if np.any(denominator <= 0.0):
        raise PhysicalDomainError("mode reached a non-positive mean Jacobian")
    nonlinearity = (f_values - eccentricity) / denominator
    inner_derivatives = table.evaluate_e_f(inner_eccentricity, inner_f)
    return NonlinearApsidalMode(
        dimensionless_semimajor_axis=_readonly(solution.t),
        eccentricity=_readonly(eccentricity),
        eccentricity_plus_gradient=_readonly(f_values),
        orbital_nonlinearity=_readonly(nonlinearity),
        dimensionless_frequency=frequency,
        inner_boundary_nonlinearity=float(inner_q),
        inner_boundary_residual=float(
            inner_derivatives.derivative_f_at_fixed_e
        ),
        outer_boundary_residual=float(outer_residual),
        radial_node_count=0,
        ivp_function_evaluations=int(solution.nfev),
    )


def solve_zo_nonlinear_apsidal_mode_bvp(
    table: ZOHamiltonianSplineTable,
    *,
    inner_eccentricity: float,
    outer_to_inner_semimajor_axis: float,
    delta_gr: float,
    frequency_guess: float,
    radial_points: int = 128,
    relative_tolerance: float = 2.0e-6,
    maximum_nodes: int = 4096,
) -> NonlinearApsidalMode:
    """以配点 BVP 独立求解 Eq. (38)，避免无效射击端点遮蔽物理解。"""
    if not isinstance(table, ZOHamiltonianSplineTable):
        raise TypeError("table must be a ZOHamiltonianSplineTable")
    inner_eccentricity = float(inner_eccentricity)
    radius_ratio = float(outer_to_inner_semimajor_axis)
    delta_gr = float(delta_gr)
    frequency_guess = float(frequency_guess)
    if (
        not np.isfinite(inner_eccentricity)
        or inner_eccentricity <= 0.0
        or not np.isfinite(radius_ratio)
        or radius_ratio <= 1.0
        or not np.isfinite(delta_gr)
        or delta_gr < 0.0
        or not np.isfinite(frequency_guess)
    ):
        raise PhysicalDomainError("invalid nonlinear BVP mode inputs")
    if (
        not isinstance(radial_points, (int, np.integer))
        or isinstance(radial_points, (bool, np.bool_))
        or int(radial_points) < 16
        or not isinstance(maximum_nodes, (int, np.integer))
        or isinstance(maximum_nodes, (bool, np.bool_))
        or int(maximum_nodes) < int(radial_points)
    ):
        raise PhysicalDomainError(
            "radial_points and maximum_nodes must be valid increasing integer limits"
        )
    if not np.isfinite(relative_tolerance) or relative_tolerance <= 0.0:
        raise PhysicalDomainError("relative_tolerance must be finite and positive")
    inner_q = zo_free_boundary_nonlinearity(table, inner_eccentricity)
    inner_f = (inner_eccentricity + inner_q) / (
        1.0 + inner_eccentricity * inner_q
    )
    logarithmic_slope = (inner_eccentricity - inner_f) / inner_eccentricity
    initial_radius = np.geomspace(1.0, radius_ratio, int(radial_points))
    initial_eccentricity = inner_eccentricity * initial_radius ** (
        -logarithmic_slope
    )
    initial_f = (1.0 - logarithmic_slope) * initial_eccentricity
    initial_state = np.vstack((initial_eccentricity, initial_f))

    def equation(
        scaled_semimajor_axis: NDArray[np.float64],
        state: NDArray[np.float64],
        parameter: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        frequency = float(parameter[0])
        derivative = np.empty_like(state)
        for index, radius_value in enumerate(scaled_semimajor_axis):
            eccentricity = float(state[0, index])
            f_value = float(state[1, index])
            hamiltonian = table.evaluate_e_f(eccentricity, f_value)
            if hamiltonian.second_derivative_ff <= 0.0:
                raise PhysicalDomainError(
                    "Hamiltonian loses convexity in the radial-gradient direction"
                )
            one_minus_e_squared = 1.0 - eccentricity**2
            if one_minus_e_squared <= 0.0:
                raise PhysicalDomainError("mode reached |e| >= 1")
            eccentricity_gradient = f_value - eccentricity
            relativistic_term = (
                delta_gr
                / radius_value
                * eccentricity
                / one_minus_e_squared**1.5
            )
            derivative[0, index] = eccentricity_gradient / radius_value
            derivative[1, index] = (
                hamiltonian.derivative_e_at_fixed_f
                - eccentricity_gradient * hamiltonian.second_derivative_ef
                + 3.0 * hamiltonian.derivative_f_at_fixed_e
                - relativistic_term
                + frequency
                * radius_value**1.5
                * eccentricity
                / np.sqrt(one_minus_e_squared)
            ) / (radius_value * hamiltonian.second_derivative_ff)
        return derivative

    def boundary_residual(
        inner_state: NDArray[np.float64],
        outer_state: NDArray[np.float64],
        parameter: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        del parameter
        inner_hamiltonian = table.evaluate_e_f(
            float(inner_state[0]), float(inner_state[1])
        )
        outer_hamiltonian = table.evaluate_e_f(
            float(outer_state[0]), float(outer_state[1])
        )
        return np.array(
            (
                inner_state[0] - inner_eccentricity,
                inner_hamiltonian.derivative_f_at_fixed_e,
                outer_hamiltonian.derivative_f_at_fixed_e,
            )
        )

    solution = solve_bvp(
        equation,
        boundary_residual,
        initial_radius,
        initial_state,
        p=np.array((frequency_guess,)),
        tol=relative_tolerance,
        max_nodes=int(maximum_nodes),
        verbose=0,
    )
    if not solution.success or not np.all(np.isfinite(solution.y)):
        raise PhysicalDomainError(
            f"nonlinear apsidal BVP failed: {solution.message}"
        )
    output_radius = np.linspace(1.0, radius_ratio, int(radial_points))
    output_state = solution.sol(output_radius)
    eccentricity = np.asarray(output_state[0], dtype=np.float64)
    f_values = np.asarray(output_state[1], dtype=np.float64)
    if np.any(eccentricity <= 0.0):
        raise PhysicalDomainError(
            "selected nonlinear apsidal BVP branch is not node-free"
        )
    denominator = 1.0 - eccentricity * f_values
    if np.any(denominator <= 0.0):
        raise PhysicalDomainError("mode reached a non-positive mean Jacobian")
    nonlinearity = (f_values - eccentricity) / denominator
    final_boundary = boundary_residual(
        output_state[:, 0], output_state[:, -1], solution.p
    )
    return NonlinearApsidalMode(
        dimensionless_semimajor_axis=_readonly(output_radius),
        eccentricity=_readonly(eccentricity),
        eccentricity_plus_gradient=_readonly(f_values),
        orbital_nonlinearity=_readonly(nonlinearity),
        dimensionless_frequency=float(solution.p[0]),
        inner_boundary_nonlinearity=float(inner_q),
        inner_boundary_residual=float(final_boundary[1]),
        outer_boundary_residual=float(final_boundary[2]),
        radial_node_count=0,
        ivp_function_evaluations=0,
    )
