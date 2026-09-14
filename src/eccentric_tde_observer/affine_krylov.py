"""仿射固定点残差的低存储多模组合与物理域步长。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import minimize

from .source import PhysicalDomainError


def _readonly(array: NDArray[np.float64]) -> NDArray[np.float64]:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class ConstrainedResidualCombination:
    """满足系数和为一的最小二乘残差组合。"""

    coefficients: NDArray[np.float64]
    normalized_gram_condition: float
    coefficient_sum_error: float
    predicted_squared_norm: float


@dataclass(frozen=True)
class ConstrainedAffineResidualLineMinimum:
    """冻结仿射残差直线上区间约束的二范数最小点。"""

    unconstrained_fraction: float
    selected_fraction: float
    predicted_squared_norm: float
    selected_lower_boundary: bool
    selected_upper_boundary: bool


@dataclass(frozen=True)
class PositiveSimplexResidualCombination:
    """正系数、系数和为一的最小残差凸组合。"""

    coefficients: NDArray[np.float64]
    coefficient_sum_error: float
    predicted_squared_norm: float
    best_input_squared_norm: float
    active_coefficient_count: int
    optimizer_iteration_count: int
    maximum_active_gradient_spread: float
    minimum_inactive_gradient_margin: float


def constrained_minimum_residual_coefficients(
    residual_gram_matrix: ArrayLike,
    *,
    maximum_normalized_condition: float,
) -> ConstrainedResidualCombination:
    """解 ``min alpha.T G alpha``，约束 ``sum(alpha)=1``。

    先按每条残差的二范数缩放 Gram 矩阵，再直接求解带一个约束的 KKT
    系统。这里不加正则项，也不截断奇异值；病态子空间由调用方冻结的条件数门拒绝。
    """
    gram = np.asarray(residual_gram_matrix, dtype=np.float64)
    limit = float(maximum_normalized_condition)
    if (
        gram.ndim != 2
        or gram.shape[0] != gram.shape[1]
        or gram.shape[0] < 2
        or not np.all(np.isfinite(gram))
        or not np.isfinite(limit)
        or limit <= 1.0
    ):
        raise PhysicalDomainError("residual Gram system is invalid")
    if not np.allclose(gram, gram.T, rtol=2.0e-12, atol=0.0):
        raise PhysicalDomainError("residual Gram matrix must be symmetric")
    diagonal = np.diag(gram)
    if np.any(diagonal <= 0.0):
        raise PhysicalDomainError("every residual history vector must be non-zero")
    norm = np.sqrt(diagonal)
    normalized = gram / (norm[:, None] * norm[None, :])
    condition = float(np.linalg.cond(normalized))
    if not np.isfinite(condition) or condition >= limit:
        raise PhysicalDomainError(
            "normalized residual Gram system exceeds the frozen condition gate"
        )
    constraint = 1.0 / norm
    size = gram.shape[0]
    kkt = np.empty((size + 1, size + 1), dtype=np.float64)
    kkt[:size, :size] = normalized
    kkt[:size, size] = constraint
    kkt[size, :size] = constraint
    kkt[size, size] = 0.0
    right = np.zeros(size + 1, dtype=np.float64)
    right[size] = 1.0
    solution = np.linalg.solve(kkt, right)
    coefficients = solution[:size] / norm
    sum_error = abs(float(np.sum(coefficients)) - 1.0)
    predicted = float(coefficients @ gram @ coefficients)
    if (
        not np.all(np.isfinite(coefficients))
        or not np.isfinite(predicted)
        or predicted < 0.0
    ):
        raise ArithmeticError("constrained residual combination became invalid")
    return ConstrainedResidualCombination(
        coefficients=np.array(coefficients, copy=True),
        normalized_gram_condition=condition,
        coefficient_sum_error=sum_error,
        predicted_squared_norm=predicted,
    )


def positive_simplex_minimum_residual_coefficients(
    residual_gram_matrix: ArrayLike,
    *,
    optimizer_tolerance: float = 1.0e-12,
    maximum_iterations: int = 500,
) -> PositiveSimplexResidualCombination:
    """在 ``alpha>=0``、``sum(alpha)=1`` 上最小化残差二范数。

    该约束使对应物理状态保持在已验证非负状态的凸包内，不需要逐点裁剪、
    强度 floor 或事后重归一化。这里只对整个 Gram 矩阵使用一个公共尺度，
    因而不会改变不同历史残差之间的物理权重。
    """
    gram = np.asarray(residual_gram_matrix, dtype=np.float64)
    tolerance = float(optimizer_tolerance)
    if (
        gram.ndim != 2
        or gram.shape[0] != gram.shape[1]
        or gram.shape[0] < 2
        or not np.all(np.isfinite(gram))
        or not np.isfinite(tolerance)
        or tolerance <= 0.0
        or tolerance >= 1.0
        or not isinstance(maximum_iterations, (int, np.integer))
        or isinstance(maximum_iterations, (bool, np.bool_))
        or int(maximum_iterations) < 1
    ):
        raise PhysicalDomainError("positive-simplex residual system is invalid")
    if not np.allclose(gram, gram.T, rtol=2.0e-12, atol=0.0):
        raise PhysicalDomainError("residual Gram matrix must be symmetric")
    diagonal = np.diag(gram)
    if np.any(diagonal < 0.0) or not np.any(diagonal > 0.0):
        raise PhysicalDomainError("residual Gram diagonal must be non-negative")
    scale = float(np.max(diagonal))
    scaled = gram / scale
    symmetric = 0.5 * (scaled + scaled.T)
    eigenvalue = float(np.min(np.linalg.eigvalsh(symmetric)))
    if eigenvalue < -128.0 * np.finfo(np.float64).eps * gram.shape[0]:
        raise PhysicalDomainError("residual Gram matrix is not positive semidefinite")
    size = gram.shape[0]
    initial = np.zeros(size, dtype=np.float64)
    initial[int(np.argmin(diagonal))] = 1.0
    result = minimize(
        fun=lambda coefficient: 0.5 * float(
            coefficient @ symmetric @ coefficient
        ),
        x0=initial,
        jac=lambda coefficient: symmetric @ coefficient,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * size,
        constraints={
            "type": "eq",
            "fun": lambda coefficient: float(np.sum(coefficient) - 1.0),
            "jac": lambda coefficient: np.ones_like(coefficient),
        },
        options={
            "ftol": tolerance,
            "maxiter": int(maximum_iterations),
            "disp": False,
        },
    )
    coefficient = np.asarray(result.x, dtype=np.float64)
    sum_error = abs(float(np.sum(coefficient)) - 1.0)
    feasibility_tolerance = max(32.0 * tolerance, 512.0 * np.finfo(np.float64).eps)
    if (
        not result.success
        or not np.all(np.isfinite(coefficient))
        or np.any(coefficient < -feasibility_tolerance)
        or np.any(coefficient > 1.0 + feasibility_tolerance)
        or sum_error > feasibility_tolerance
    ):
        raise ArithmeticError(
            "positive-simplex residual optimization did not satisfy its constraints: "
            f"success={result.success}, sum_error={sum_error:.6e}, "
            f"minimum={float(np.min(coefficient)):.6e}"
        )
    # 中文：只清除优化器约束容差内的负零；这不是对物理场做逐点裁剪。
    coefficient = np.maximum(coefficient, 0.0)
    coefficient /= float(np.sum(coefficient))
    predicted = float(coefficient @ gram @ coefficient)
    best_input = float(np.min(diagonal))
    if (
        not np.isfinite(predicted)
        or predicted < -feasibility_tolerance * scale
        or predicted > best_input * (1.0 + 128.0 * tolerance)
    ):
        raise ArithmeticError("positive-simplex solution did not improve its seed")
    predicted = max(predicted, 0.0)
    gradient = symmetric @ coefficient
    active = coefficient > feasibility_tolerance
    inactive = ~active
    active_gradient = gradient[active]
    active_spread = (
        float(np.max(active_gradient) - np.min(active_gradient))
        if active_gradient.size > 1
        else 0.0
    )
    reference_gradient = float(np.mean(active_gradient))
    inactive_margin = (
        float(np.min(gradient[inactive] - reference_gradient))
        if np.any(inactive)
        else np.inf
    )
    return PositiveSimplexResidualCombination(
        coefficients=_readonly(np.array(coefficient, copy=True)),
        coefficient_sum_error=abs(float(np.sum(coefficient)) - 1.0),
        predicted_squared_norm=predicted,
        best_input_squared_norm=best_input,
        active_coefficient_count=int(np.count_nonzero(active)),
        optimizer_iteration_count=int(result.nit),
        maximum_active_gradient_spread=active_spread,
        minimum_inactive_gradient_margin=inactive_margin,
    )


def exact_nonnegative_affine_step(
    state: ArrayLike,
    direction: ArrayLike,
) -> float:
    """返回 ``state + eta*direction >= 0`` 的最大安全 ``eta<=1``。

    若完整方向可接受就返回 1；否则返回严格低于精确正性边界的相邻浮点数。
    这个函数只缩短一个全局标量，不修改任何单元值。
    """
    current = np.asarray(state, dtype=np.float64)
    update = np.asarray(direction, dtype=np.float64)
    if (
        current.shape != update.shape
        or current.size == 0
        or not np.all(np.isfinite(current))
        or not np.all(np.isfinite(update))
        or np.any(current < 0.0)
    ):
        raise PhysicalDomainError("state and affine direction are invalid")
    negative = update < 0.0
    if not np.any(negative):
        return 1.0
    boundary = float(np.min(current[negative] / (-update[negative])))
    if not np.isfinite(boundary) or boundary <= 0.0:
        raise PhysicalDomainError("no positive affine step preserves non-negativity")
    if boundary > 1.0:
        return 1.0
    return float(np.nextafter(boundary, 0.0))


def constrained_affine_residual_line_minimum(
    raw_residual: ArrayLike,
    endpoint_residual: ArrayLike,
) -> ConstrainedAffineResidualLineMinimum:
    """在 ``R(t)=(1-t)R0+tR1``、``0<=t<=1`` 上精确最小化二范数。"""
    raw = np.asarray(raw_residual, dtype=np.float64)
    endpoint = np.asarray(endpoint_residual, dtype=np.float64)
    if (
        raw.shape != endpoint.shape
        or raw.size == 0
        or not np.all(np.isfinite(raw))
        or not np.all(np.isfinite(endpoint))
    ):
        raise PhysicalDomainError(
            "affine residual endpoints must be finite arrays with matching nonzero shape"
        )
    difference = endpoint - raw
    curvature = float(np.dot(difference.ravel(), difference.ravel()))
    raw_norm = float(np.dot(raw.ravel(), raw.ravel()))
    if not np.isfinite(curvature) or not np.isfinite(raw_norm):
        raise ArithmeticError("affine residual line norm overflowed")
    if curvature == 0.0:
        if raw_norm == 0.0:
            return ConstrainedAffineResidualLineMinimum(
                unconstrained_fraction=0.0,
                selected_fraction=0.0,
                predicted_squared_norm=0.0,
                selected_lower_boundary=True,
                selected_upper_boundary=False,
            )
        raise PhysicalDomainError("affine residual endpoint supplies no search direction")
    slope = float(np.dot(raw.ravel(), difference.ravel()))
    unconstrained = -slope / curvature
    if not np.isfinite(unconstrained):
        raise ArithmeticError("affine residual line minimum became non-finite")
    if unconstrained <= 0.0:
        selected = 0.0
        lower = True
        upper = False
    elif unconstrained >= 1.0:
        selected = 1.0
        lower = False
        upper = True
    else:
        selected = unconstrained
        lower = False
        upper = False
    predicted = raw + selected * difference
    squared_norm = float(np.dot(predicted.ravel(), predicted.ravel()))
    if not np.isfinite(squared_norm):
        raise ArithmeticError("affine residual line prediction overflowed")
    return ConstrainedAffineResidualLineMinimum(
        unconstrained_fraction=float(unconstrained),
        selected_fraction=float(selected),
        predicted_squared_norm=squared_norm,
        selected_lower_boundary=lower,
        selected_upper_boundary=upper,
    )
