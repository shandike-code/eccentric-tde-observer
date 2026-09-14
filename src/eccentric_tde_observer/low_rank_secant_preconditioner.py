"""少量真实割线约束下的稠密低秩逆 Jacobian 预条件器。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.sparse.linalg import LinearOperator

from .source import PhysicalDomainError


def _readonly(array: NDArray[np.float64]) -> NDArray[np.float64]:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class LowRankInverseSecantPreconditioner:
    """满足多个割线恒等式的最小 Frobenius 低秩逆更新。"""

    dimension: int
    secant_count: int
    base_inverse_scale: float
    normalized_state_secants: NDArray[np.float64]
    normalized_residual_secants: NDArray[np.float64]
    residual_gram: NDArray[np.float64]
    correction_left: NDArray[np.float64]
    residual_secant_norms: NDArray[np.float64]
    gram_condition_number: float
    maximum_relative_secant_residual: float

    @classmethod
    def from_secants(
        cls,
        state_secants: ArrayLike,
        residual_secants: ArrayLike,
        *,
        base_inverse_scale: float,
        maximum_gram_condition_number: float,
    ) -> LowRankInverseSecantPreconditioner:
        """构造 $H Y=S$；列相关或零割线直接拒绝。"""
        state = np.asarray(state_secants, dtype=np.float64)
        residual = np.asarray(residual_secants, dtype=np.float64)
        base = float(base_inverse_scale)
        condition_limit = float(maximum_gram_condition_number)
        if (
            state.ndim != 2
            or residual.shape != state.shape
            or state.shape[0] < 1
            or state.shape[1] < 1
            or state.shape[1] > state.shape[0]
            or not np.all(np.isfinite(state))
            or not np.all(np.isfinite(residual))
            or not np.isfinite(base)
            or base == 0.0
            or not np.isfinite(condition_limit)
            or condition_limit <= 1.0
        ):
            raise PhysicalDomainError("inverse-secant preconditioner inputs are invalid")
        norms = np.linalg.norm(residual, axis=0)
        if not np.all(np.isfinite(norms)) or np.any(norms <= 0.0):
            # 中文：零割线不含导数信息，不能用任意 floor 制造方向。
            raise PhysicalDomainError("inverse-secant residual direction is zero")
        normalized_residual = residual / norms[None, :]
        normalized_state = state / norms[None, :]
        gram = normalized_residual.T @ normalized_residual
        condition = float(np.linalg.cond(gram))
        if not np.isfinite(condition) or condition > condition_limit:
            raise PhysicalDomainError("inverse-secant residual Gram matrix is rank deficient")
        correction = normalized_state - base * normalized_residual
        # 先构造对象需要的全部只读量，再用同一稳定求解检查割线恒等式。
        solved_projection = np.linalg.solve(gram, normalized_residual.T @ residual)
        recovered = base * residual + correction @ solved_projection
        absolute = np.linalg.norm(recovered - state, axis=0)
        scale = np.maximum(np.linalg.norm(recovered, axis=0), np.linalg.norm(state, axis=0))
        relative = np.divide(
            absolute,
            scale,
            out=np.array(absolute, copy=True),
            where=scale > 0.0,
        )
        maximum_relative = float(np.max(relative))
        if not np.isfinite(maximum_relative):
            raise ArithmeticError("inverse-secant identity became non-finite")
        return cls(
            dimension=int(state.shape[0]),
            secant_count=int(state.shape[1]),
            base_inverse_scale=base,
            normalized_state_secants=_readonly(np.array(normalized_state, copy=True)),
            normalized_residual_secants=_readonly(
                np.array(normalized_residual, copy=True)
            ),
            residual_gram=_readonly(np.array(gram, copy=True)),
            correction_left=_readonly(np.array(correction, copy=True)),
            residual_secant_norms=_readonly(np.array(norms, copy=True)),
            gram_condition_number=condition,
            maximum_relative_secant_residual=maximum_relative,
        )

    def apply(self, vector: ArrayLike) -> NDArray[np.float64]:
        """应用稠密低秩逆更新；不显式形成 $N\times N$ 矩阵。"""
        value = np.asarray(vector, dtype=np.float64)
        if value.shape != (self.dimension,) or not np.all(np.isfinite(value)):
            raise PhysicalDomainError("inverse-secant preconditioner vector is invalid")
        coefficient = np.linalg.solve(
            self.residual_gram,
            self.normalized_residual_secants.T @ value,
        )
        result = self.base_inverse_scale * value + self.correction_left @ coefficient
        if not np.all(np.isfinite(result)):
            raise ArithmeticError("inverse-secant preconditioner produced non-finite values")
        return np.array(result, copy=True)

    def as_linear_operator(self) -> LinearOperator:
        """返回可直接交给 GMRES 的可写 matvec 线性算子。"""
        return LinearOperator(
            shape=(self.dimension, self.dimension),
            matvec=self.apply,
            dtype=np.float64,
        )
