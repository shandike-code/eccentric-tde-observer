"""Quadrature rules for the corrected and pre-Erratum ZO area measures.

Zanazzi & Ogilvie (2022, MNRAS 516, 3234) correct the radiative area element
to ``a*j*(1-e*cos(E))*da*dE``.  The 2020 ``a*j*da*dE`` expression is retained
only as an explicitly named historical regression path.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .source import PhysicalDomainError, ZOSourceGrid


def trapezoid_weights(coordinate: ArrayLike) -> NDArray[np.float64]:
    x = np.asarray(coordinate, dtype=np.float64)
    if x.ndim != 1 or x.size < 2 or np.any(np.diff(x) <= 0.0):
        raise PhysicalDomainError("trapezoid coordinate must be one-dimensional and increasing")
    weights = np.empty_like(x)
    weights[0] = 0.5 * (x[1] - x[0])
    weights[-1] = 0.5 * (x[-1] - x[-2])
    weights[1:-1] = 0.5 * (x[2:] - x[:-2])
    return weights


def periodic_weights(
    angle_rad: ArrayLike, period: float = 2.0 * np.pi
) -> NDArray[np.float64]:
    angle = np.asarray(angle_rad, dtype=np.float64)
    if angle.ndim != 1 or angle.size < 3 or np.any(np.diff(angle) <= 0.0):
        raise PhysicalDomainError("periodic coordinate must be one-dimensional and increasing")
    previous = np.roll(angle, 1)
    following = np.roll(angle, -1)
    previous[0] -= period
    following[-1] += period
    weights = 0.5 * (following - previous)
    if np.any(weights <= 0.0):
        raise PhysicalDomainError("periodic quadrature produced a non-positive weight")
    return weights


def pre_erratum_zo2020_area_weights(
    source: ZOSourceGrid,
) -> NDArray[np.float64]:
    """Return the incorrect 2020 ``a*j*da*dE`` weights for history tests."""
    radial = trapezoid_weights(source.semimajor_axis_cm)
    azimuthal = periodic_weights(source.eccentric_anomaly_rad)
    weights = (
        source.semimajor_axis_cm[:, None]
        * source.jacobian
        * radial[:, None]
        * azimuthal[None, :]
    )
    if not np.all(np.isfinite(weights)) or np.any(weights <= 0.0):
        raise PhysicalDomainError("pre-Erratum ZO 2020 quadrature produced invalid weights")
    return weights


def corrected_zo_area_weights(source: ZOSourceGrid) -> NDArray[np.float64]:
    """Return the formal corrected ZO 2022 radiative-area weights.

    The physical in-plane element is
    ``dA_corr = a*j*(1-e*cos(E))*da*dE``.
    """
    orbital_time_factor = 1.0 - (
        source.eccentricity[:, None]
        * np.cos(source.eccentric_anomaly_rad)[None, :]
    )
    if not np.all(np.isfinite(orbital_time_factor)) or np.any(
        orbital_time_factor <= 0.0
    ):
        raise PhysicalDomainError("dM/dE = 1 - e*cos(E) must be positive")
    # 中文：Erratum 的额外因子属于辐射面积元，不改写任何 ZO 源场。
    weights = pre_erratum_zo2020_area_weights(source) * orbital_time_factor
    if not np.all(np.isfinite(weights)) or np.any(weights <= 0.0):
        raise PhysicalDomainError("corrected ZO quadrature produced invalid weights")
    return weights


def corrected_zo_area_cm2(source: ZOSourceGrid) -> float:
    """Return the corrected one-face planar area in cm^2."""
    return float(np.sum(corrected_zo_area_weights(source), dtype=np.float64))


def pre_erratum_zo2020_area_cm2(source: ZOSourceGrid) -> float:
    """Return the historical 2020 quadrature area in cm^2."""
    return float(
        np.sum(pre_erratum_zo2020_area_weights(source), dtype=np.float64)
    )


def geometric_planar_area_weights(source: ZOSourceGrid) -> NDArray[np.float64]:
    """Independent Cartesian name for the same corrected planar element."""
    return corrected_zo_area_weights(source)


def geometric_planar_area_cm2(source: ZOSourceGrid) -> float:
    return corrected_zo_area_cm2(source)
