"""Ogilvie--Lynch 二维非线性 Hamiltonian 的受控诊断实现。"""

from __future__ import annotations

import numpy as np

from .hamiltonian_table import ZOHamiltonianSplineTable
from .source import PhysicalDomainError
from .zo_reference import ADIABATIC_INDEX


def ol_untwisted_2d_dimensionless_hamiltonian(
    eccentricity: float,
    eccentricity_plus_gradient: float,
    *,
    anomaly_points: int = 512,
) -> float:
    """返回 OL 2019 Eqs. (33)/(B4) 的无扭曲二维几何 Hamiltonian。

    这是定位已发表拱点模差异的 ``[A-diagnostic]`` 对照，不替换
    正式的 ZO 三维源模型。轨道平均使用平均异常角。
    ``1-e cos(E)``；这里不做裁剪、floor 或事后归一化。
    """
    eccentricity = float(eccentricity)
    f_value = float(eccentricity_plus_gradient)
    if (
        not np.isfinite(eccentricity)
        or abs(eccentricity) >= 0.99
        or not np.isfinite(f_value)
    ):
        raise PhysicalDomainError(
            "2D Hamiltonian requires finite e and f with |e| < 0.99"
        )
    denominator = 1.0 - eccentricity * f_value
    if denominator <= 0.0:
        raise PhysicalDomainError(
            "2D Hamiltonian has a non-positive mean coordinate Jacobian"
        )
    nonlinearity = (f_value - eccentricity) / denominator
    if abs(nonlinearity) >= 1.0:
        raise PhysicalDomainError(
            "2D Hamiltonian orbit intersects because |q| >= 1"
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
    anomaly = (
        2.0
        * np.pi
        * np.arange(int(anomaly_points), dtype=np.float64)
        / int(anomaly_points)
    )
    cosine = np.cos(anomaly)
    jacobian = (
        denominator - (f_value - eccentricity) * cosine
    ) / np.sqrt(1.0 - eccentricity**2)
    if not np.all(np.isfinite(jacobian)) or np.any(jacobian <= 0.0):
        raise PhysicalDomainError(
            "2D Hamiltonian orbital Jacobian must remain finite and positive"
        )
    gamma = ADIABATIC_INDEX
    # 中文：周期梯形积分等价于离散轨道平均。
    # 中文：这里显式保留平均异常角 Jacobian。
    orbit_average = np.mean(
        (1.0 - eccentricity * cosine)
        * jacobian ** (-(gamma - 1.0))
    )
    if not np.isfinite(orbit_average) or orbit_average <= 0.0:
        raise PhysicalDomainError(
            "2D Hamiltonian orbit average must be finite and positive"
        )
    return float(orbit_average / (gamma - 1.0))


def ol_linearized_2d_dimensionless_hamiltonian(
    eccentricity: float,
    eccentricity_plus_gradient: float,
) -> float:
    """返回 OL 2019 Eq. (40) 的无扭曲二维二次极限。"""
    eccentricity = float(eccentricity)
    f_value = float(eccentricity_plus_gradient)
    if not np.isfinite(eccentricity) or not np.isfinite(f_value):
        raise PhysicalDomainError(
            "linearized 2D Hamiltonian inputs must be finite"
        )
    gamma = ADIABATIC_INDEX
    gradient = f_value - eccentricity
    return float(
        1.0 / (gamma - 1.0)
        + 0.5 * eccentricity * f_value
        + 0.25 * gamma * gradient**2
    )


def build_ol_2d_hamiltonian_spline_table(
    eccentricity_nodes: np.ndarray,
    nonlinearity_nodes: np.ndarray,
    *,
    anomaly_points: int = 512,
) -> ZOHamiltonianSplineTable:
    """构造不外推的 OL 二维 ``G(e,q)`` 诊断表。"""
    eccentricity = np.asarray(eccentricity_nodes, dtype=np.float64)
    nonlinearity = np.asarray(nonlinearity_nodes, dtype=np.float64)
    if eccentricity.ndim != 1 or nonlinearity.ndim != 1:
        raise PhysicalDomainError(
            "2D Hamiltonian-table axes must be one-dimensional"
        )
    values = np.empty(
        (eccentricity.size, nonlinearity.size), dtype=np.float64
    )
    for eccentricity_index, eccentricity_value in enumerate(eccentricity):
        for nonlinearity_index, nonlinearity_value in enumerate(
            nonlinearity
        ):
            coordinate_denominator = (
                1.0 + eccentricity_value * nonlinearity_value
            )
            if coordinate_denominator <= 0.0:
                raise PhysicalDomainError(
                    "2D table node has a non-positive e-q denominator"
                )
            f_value = (
                eccentricity_value + nonlinearity_value
            ) / coordinate_denominator
            values[eccentricity_index, nonlinearity_index] = (
                ol_untwisted_2d_dimensionless_hamiltonian(
                    float(eccentricity_value),
                    float(f_value),
                    anomaly_points=anomaly_points,
                )
            )
    return ZOHamiltonianSplineTable(
        eccentricity, nonlinearity, values
    )
