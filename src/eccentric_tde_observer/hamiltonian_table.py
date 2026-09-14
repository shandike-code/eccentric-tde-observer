"""ZO 非线性 Hamiltonian 的非外推二维插值与偏导坐标变换。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.interpolate import RectBivariateSpline

from .source import PhysicalDomainError
from .nonlinear_hamiltonian import zo_untwisted_dimensionless_hamiltonian


@dataclass(frozen=True)
class InterpolatedZOHamiltonianDerivatives:
    """从 ``G(e,q)`` 表转换到 ZO Eq. (38) 的 ``F(e,f)`` 偏导。"""

    eccentricity: float
    eccentricity_plus_gradient: float
    orbital_nonlinearity: float
    dimensionless_hamiltonian: float
    derivative_e_at_fixed_f: float
    derivative_f_at_fixed_e: float
    second_derivative_ee: float
    second_derivative_ef: float
    second_derivative_ff: float


def _readonly(values: ArrayLike) -> NDArray[np.float64]:
    array = np.array(values, dtype=np.float64, copy=True)
    array.setflags(write=False)
    return array


class ZOHamiltonianSplineTable:
    """严格拒绝定义域外查询的双三次 ``G(e,q)`` 表。"""

    def __init__(
        self,
        eccentricity_nodes: ArrayLike,
        nonlinearity_nodes: ArrayLike,
        dimensionless_hamiltonian: ArrayLike,
    ) -> None:
        eccentricity = np.array(
            eccentricity_nodes, dtype=np.float64, copy=True
        )
        nonlinearity = np.array(
            nonlinearity_nodes, dtype=np.float64, copy=True
        )
        values = np.array(
            dimensionless_hamiltonian, dtype=np.float64, copy=True
        )
        for name, nodes in (
            ("eccentricity_nodes", eccentricity),
            ("nonlinearity_nodes", nonlinearity),
        ):
            if (
                nodes.ndim != 1
                or nodes.size < 4
                or not np.all(np.isfinite(nodes))
                or np.any(np.diff(nodes) <= 0.0)
            ):
                raise PhysicalDomainError(
                    f"{name} must be finite, strictly increasing, and contain at least four nodes"
                )
        if eccentricity[0] < 0.0 or eccentricity[-1] >= 0.99:
            raise PhysicalDomainError(
                "Hamiltonian-table eccentricity nodes must lie in [0, 0.99)"
            )
        if nonlinearity[0] <= -1.0 or nonlinearity[-1] >= 1.0:
            raise PhysicalDomainError(
                "Hamiltonian-table nonlinearity nodes must lie in (-1, 1)"
            )
        if values.shape != (eccentricity.size, nonlinearity.size):
            raise PhysicalDomainError(
                "Hamiltonian-table value shape must match the two node axes"
            )
        if not np.all(np.isfinite(values)):
            raise PhysicalDomainError("Hamiltonian-table values must be finite")
        self._eccentricity = _readonly(eccentricity)
        self._nonlinearity = _readonly(nonlinearity)
        self._hamiltonian = _readonly(values)
        self._spline = RectBivariateSpline(
            eccentricity,
            nonlinearity,
            values,
            kx=3,
            ky=3,
            s=0.0,
        )

    @property
    def eccentricity_nodes(self) -> NDArray[np.float64]:
        return self._eccentricity

    @property
    def nonlinearity_nodes(self) -> NDArray[np.float64]:
        return self._nonlinearity

    @property
    def dimensionless_hamiltonian(self) -> NDArray[np.float64]:
        return self._hamiltonian

    def _validate_e_q(self, eccentricity: float, nonlinearity: float) -> None:
        if (
            not np.isfinite(eccentricity)
            or not np.isfinite(nonlinearity)
            or eccentricity < self._eccentricity[0]
            or eccentricity > self._eccentricity[-1]
            or nonlinearity < self._nonlinearity[0]
            or nonlinearity > self._nonlinearity[-1]
        ):
            raise PhysicalDomainError(
                "Hamiltonian query lies outside the tabulated (e, q) domain"
            )

    def evaluate_e_q(
        self,
        eccentricity: float,
        nonlinearity: float,
        *,
        eccentricity_derivative_order: int = 0,
        nonlinearity_derivative_order: int = 0,
    ) -> float:
        """返回 ``G(e,q)`` 或指定偏导；定义域外不外推。"""
        eccentricity = float(eccentricity)
        nonlinearity = float(nonlinearity)
        self._validate_e_q(eccentricity, nonlinearity)
        for name, order in (
            ("eccentricity_derivative_order", eccentricity_derivative_order),
            ("nonlinearity_derivative_order", nonlinearity_derivative_order),
        ):
            if (
                not isinstance(order, (int, np.integer))
                or isinstance(order, (bool, np.bool_))
                or int(order) < 0
                or int(order) > 2
            ):
                raise PhysicalDomainError(f"{name} must be an integer from zero to two")
        if int(eccentricity_derivative_order) + int(
            nonlinearity_derivative_order
        ) > 2:
            raise PhysicalDomainError(
                "Hamiltonian table exposes derivatives only through total order two"
            )
        return float(
            self._spline.ev(
                eccentricity,
                nonlinearity,
                dx=int(eccentricity_derivative_order),
                dy=int(nonlinearity_derivative_order),
            )
        )

    def evaluate_e_f(
        self,
        eccentricity: float,
        eccentricity_plus_gradient: float,
    ) -> InterpolatedZOHamiltonianDerivatives:
        """将样条偏导严格变换到固定 ``f`` 或固定 ``e`` 的偏导。"""
        eccentricity = float(eccentricity)
        f_value = float(eccentricity_plus_gradient)
        if not np.isfinite(eccentricity) or not np.isfinite(f_value):
            raise PhysicalDomainError("Hamiltonian query inputs must be finite")
        denominator = 1.0 - eccentricity * f_value
        if denominator <= 0.0:
            raise PhysicalDomainError(
                "Hamiltonian query has non-positive mean Jacobian"
            )
        nonlinearity = (f_value - eccentricity) / denominator
        self._validate_e_q(eccentricity, nonlinearity)
        g = self.evaluate_e_q(eccentricity, nonlinearity)
        g_e = self.evaluate_e_q(
            eccentricity,
            nonlinearity,
            eccentricity_derivative_order=1,
        )
        g_q = self.evaluate_e_q(
            eccentricity,
            nonlinearity,
            nonlinearity_derivative_order=1,
        )
        g_ee = self.evaluate_e_q(
            eccentricity,
            nonlinearity,
            eccentricity_derivative_order=2,
        )
        g_eq = self.evaluate_e_q(
            eccentricity,
            nonlinearity,
            eccentricity_derivative_order=1,
            nonlinearity_derivative_order=1,
        )
        g_qq = self.evaluate_e_q(
            eccentricity,
            nonlinearity,
            nonlinearity_derivative_order=2,
        )
        # 中文：以下链式法则全部在固定 f 或固定 e 下求导，不混淆表坐标 q。
        q_e = (f_value**2 - 1.0) / denominator**2
        q_f = (1.0 - eccentricity**2) / denominator**2
        q_ee = 2.0 * f_value * (f_value**2 - 1.0) / denominator**3
        q_ff = (
            2.0
            * eccentricity
            * (1.0 - eccentricity**2)
            / denominator**3
        )
        q_ef = (
            -2.0 * eccentricity / denominator**2
            + 2.0
            * f_value
            * (1.0 - eccentricity**2)
            / denominator**3
        )
        derivative_e = g_e + g_q * q_e
        derivative_f = g_q * q_f
        second_ee = g_ee + 2.0 * g_eq * q_e + g_qq * q_e**2 + g_q * q_ee
        second_ef = (
            (g_eq + g_qq * q_e) * q_f
            + g_q * q_ef
        )
        second_ff = g_qq * q_f**2 + g_q * q_ff
        return InterpolatedZOHamiltonianDerivatives(
            eccentricity=eccentricity,
            eccentricity_plus_gradient=f_value,
            orbital_nonlinearity=float(nonlinearity),
            dimensionless_hamiltonian=g,
            derivative_e_at_fixed_f=float(derivative_e),
            derivative_f_at_fixed_e=float(derivative_f),
            second_derivative_ee=float(second_ee),
            second_derivative_ef=float(second_ef),
            second_derivative_ff=float(second_ff),
        )


def build_zo_hamiltonian_spline_table(
    eccentricity_nodes: ArrayLike,
    nonlinearity_nodes: ArrayLike,
    *,
    anomaly_points: int = 256,
    relative_tolerance: float = 2.0e-11,
    absolute_tolerance: float = 2.0e-13,
) -> ZOHamiltonianSplineTable:
    """逐点求解 ZO Eqs. (34)--(35)，构造不外推的 ``G(e,q)`` 表。"""
    eccentricity = np.asarray(eccentricity_nodes, dtype=np.float64)
    nonlinearity = np.asarray(nonlinearity_nodes, dtype=np.float64)
    if eccentricity.ndim != 1 or nonlinearity.ndim != 1:
        raise PhysicalDomainError("Hamiltonian-table node axes must be one-dimensional")
    values = np.empty((eccentricity.size, nonlinearity.size), dtype=np.float64)
    for eccentricity_index, eccentricity_value in enumerate(eccentricity):
        for nonlinearity_index, nonlinearity_value in enumerate(nonlinearity):
            denominator = 1.0 + eccentricity_value * nonlinearity_value
            if denominator <= 0.0:
                raise PhysicalDomainError(
                    "Hamiltonian-table nodes imply a non-positive e-q coordinate denominator"
                )
            f_value = (
                eccentricity_value + nonlinearity_value
            ) / denominator
            # 中文：表值来自原始垂向呼吸方程，不以拟合函数或后验归一化替代。
            values[eccentricity_index, nonlinearity_index] = (
                zo_untwisted_dimensionless_hamiltonian(
                    float(eccentricity_value),
                    float(f_value),
                    anomaly_points=anomaly_points,
                    relative_tolerance=relative_tolerance,
                    absolute_tolerance=absolute_tolerance,
                )
            )
    return ZOHamiltonianSplineTable(eccentricity, nonlinearity, values)
