"""Weak-field straight-ray frequency shifts for the bare eccentric disc.

This module changes only the source-to-observer transfer.  It does not modify
the Zanazzi--Ogilvie thermodynamic source fields, bend rays, add a wind, or
claim a self-consistent relativistic atmosphere.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .observer import Observer
from .radiation import LIGHT_SPEED_CM_S
from .source import PhysicalDomainError, ZOSourceGrid
from .zo_reference import SOLAR_MASS_G


GRAVITATIONAL_CONSTANT_CGS = 6.67430e-8


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


def _black_hole_mass_g(black_hole_mass_msun: float) -> float:
    mass_msun = float(black_hole_mass_msun)
    if not np.isfinite(mass_msun) or mass_msun <= 0.0:
        raise PhysicalDomainError(
            "black_hole_mass_msun must be finite and strictly positive"
        )
    mass_g = mass_msun * SOLAR_MASS_G
    if not np.isfinite(mass_g):
        raise PhysicalDomainError("black-hole mass overflows cgs float64")
    return mass_g


def orbital_radius_cm(source: ZOSourceGrid) -> NDArray[np.float64]:
    """Return ``r = a (1 - e cos E)`` on the source grid."""
    radius = source.semimajor_axis_cm[:, None] * (
        1.0
        - source.eccentricity[:, None]
        * np.cos(source.eccentric_anomaly_rad[None, :])
    )
    if not np.all(np.isfinite(radius)) or np.any(radius <= 0.0):
        raise ArithmeticError("orbital-radius evaluation produced an invalid value")
    return _readonly(radius)


def keplerian_orbital_velocity_cm_s(
    source: ZOSourceGrid,
    black_hole_mass_msun: float,
) -> NDArray[np.float64]:
    """Return the Newtonian in-plane Kepler velocity at each ``(a, E)``.

    The eccentric anomaly is advanced with
    ``dE/dt = sqrt(GM/a**3) / (1 - e cos E)`` and the result is rotated by the
    source's global apsidal angle.  No post-Newtonian orbital correction is
    included in this first transfer layer.
    """
    if source.apsidal_gradient_per_cm is not None and np.any(
        source.apsidal_gradient_per_cm != 0.0
    ):
        raise PhysicalDomainError(
            "a twisted velocity field needs varpi(a), not only "
            "apsidal_gradient_per_cm"
        )
    mass_g = _black_hole_mass_g(black_hole_mass_msun)
    a = source.semimajor_axis_cm[:, None]
    eccentricity = source.eccentricity[:, None]
    anomaly = source.eccentric_anomaly_rad[None, :]
    # 中文：先按 Kepler 方程推进 E；这里没有偷偷加入 PN 轨道修正。
    mean_motion = np.sqrt(GRAVITATIONAL_CONSTANT_CGS * mass_g / a**3)
    denominator = 1.0 - eccentricity * np.cos(anomaly)
    velocity_x_periapsis = -a * mean_motion * np.sin(anomaly) / denominator
    velocity_y_periapsis = (
        a
        * mean_motion
        * np.sqrt(1.0 - eccentricity**2)
        * np.cos(anomaly)
        / denominator
    )

    cosine = np.cos(source.apsidal_angle_rad)
    sine = np.sin(source.apsidal_angle_rad)
    velocity_x = cosine * velocity_x_periapsis - sine * velocity_y_periapsis
    velocity_y = sine * velocity_x_periapsis + cosine * velocity_y_periapsis
    velocity_z = np.zeros(source.shape, dtype=np.float64)
    velocity = np.stack(
        np.broadcast_arrays(velocity_x, velocity_y, velocity_z), axis=-1
    )
    if not np.all(np.isfinite(velocity)):
        raise ArithmeticError("Keplerian velocity evaluation became non-finite")
    return _readonly(velocity)


def homologous_vertical_velocity_cm_s(
    source: ZOSourceGrid,
    surface_height_cm: ArrayLike,
    log_height_derivative_per_rad: ArrayLike,
    black_hole_mass_msun: float,
) -> NDArray[np.float64]:
    """Return the ZO homologous vertical velocity at an emitting height.

    For the ZO breathing solution ``q(E)=ln h(E)``, homologous vertical motion
    gives ``v_z = z dq/dt = z (dq/dE) (dE/dt)``.  This is usable only when the
    supplied derivative belongs to the same anomaly grid and source solution.
    """
    mass_g = _black_hole_mass_g(black_hole_mass_msun)
    height = np.array(surface_height_cm, dtype=np.float64, copy=True)
    if height.shape != source.shape or not np.all(np.isfinite(height)):
        raise PhysicalDomainError(
            f"surface_height_cm must be finite with shape {source.shape}"
        )
    derivative = np.array(
        log_height_derivative_per_rad, dtype=np.float64, copy=True
    )
    if derivative.shape != (source.shape[1],) or not np.all(np.isfinite(derivative)):
        raise PhysicalDomainError(
            "log_height_derivative_per_rad must be finite and match the anomaly grid"
        )

    a = source.semimajor_axis_cm[:, None]
    eccentricity = source.eccentricity[:, None]
    anomaly = source.eccentric_anomaly_rad[None, :]
    mean_motion = np.sqrt(GRAVITATIONAL_CONSTANT_CGS * mass_g / a**3)
    # 中文：ZO 呼吸是随流体轨道相位变化，需用 dE/dt 转成真实时间导数。
    anomaly_rate = mean_motion / (1.0 - eccentricity * np.cos(anomaly))
    velocity_z = height * derivative[None, :] * anomaly_rate
    if not np.all(np.isfinite(velocity_z)):
        raise ArithmeticError("homologous vertical velocity became non-finite")
    return _readonly(velocity_z)


@dataclass(frozen=True)
class StraightRayFrequencyShift:
    """Pointwise diagnostics for the adopted weak-field transfer factor."""

    velocity_cm_s: NDArray[np.float64]
    beta_squared: NDArray[np.float64]
    line_of_sight_beta: NDArray[np.float64]
    gravitational_lapse: NDArray[np.float64]
    lorentz_factor: NDArray[np.float64]
    special_relativistic_doppler: NDArray[np.float64]
    frequency_shift_factor: NDArray[np.float64]


def straight_ray_frequency_shift(
    source: ZOSourceGrid,
    observer: Observer,
    black_hole_mass_msun: float,
    *,
    vertical_velocity_cm_s: ArrayLike | None = None,
) -> StraightRayFrequencyShift:
    """Construct ``g`` for straight rays in a Schwarzschild weak-field layer.

    The adopted factor is

    ``g = sqrt(1 - 2GM/(r c**2)) / [gamma (1 - beta dot n)]``,

    where ``n`` points from source to observer.  It combines a Schwarzschild
    lapse with the local special-relativistic Doppler factor but neglects ray
    bending, light-travel delays, spin, frame dragging, and relativistic
    corrections to the Newtonian eccentric orbit.
    """
    mass_g = _black_hole_mass_g(black_hole_mass_msun)
    velocity = np.array(
        keplerian_orbital_velocity_cm_s(source, black_hole_mass_msun), copy=True
    )
    if vertical_velocity_cm_s is not None:
        vertical_velocity = np.array(
            vertical_velocity_cm_s, dtype=np.float64, copy=True
        )
        if vertical_velocity.shape != source.shape or not np.all(
            np.isfinite(vertical_velocity)
        ):
            raise PhysicalDomainError(
                f"vertical_velocity_cm_s must be finite with shape {source.shape}"
            )
        velocity[..., 2] = vertical_velocity

    # 中文：任何 beta>=1 都是闭合失效，必须报错而不是裁剪回亚光速。
    beta = velocity / LIGHT_SPEED_CM_S
    beta_squared = np.sum(beta**2, axis=-1)
    invalid_beta = (~np.isfinite(beta_squared)) | (beta_squared >= 1.0)
    if np.any(invalid_beta):
        index = tuple(int(i) for i in np.argwhere(invalid_beta)[0])
        raise PhysicalDomainError(
            "emitting velocity must remain subluminal; "
            f"beta_squared={beta_squared[index]!r} at index {index}"
        )
    line_of_sight_beta = beta @ observer.direction_from_source
    denominator = 1.0 - line_of_sight_beta
    if np.any(denominator <= 0.0) or not np.all(np.isfinite(denominator)):
        raise PhysicalDomainError("Doppler denominator must be finite and positive")
    lorentz_factor = 1.0 / np.sqrt(1.0 - beta_squared)
    special_relativistic_doppler = 1.0 / (lorentz_factor * denominator)

    radius = orbital_radius_cm(source)
    compactness_twice = (
        2.0 * GRAVITATIONAL_CONSTANT_CGS * mass_g
        / (radius * LIGHT_SPEED_CM_S**2)
    )
    outside_horizon = compactness_twice < 1.0
    if not np.all(outside_horizon):
        index = tuple(int(i) for i in np.argwhere(~outside_horizon)[0])
        raise PhysicalDomainError(
            "straight-ray Schwarzschild lapse requires r > 2GM/c^2; "
            f"failed at index {index}"
        )
    # 中文：这是直线射线上的弱场混合闭合，不等同于完整 GR transfer function。
    gravitational_lapse = np.sqrt(1.0 - compactness_twice)
    frequency_shift = gravitational_lapse * special_relativistic_doppler
    if not np.all(np.isfinite(frequency_shift)) or np.any(frequency_shift <= 0.0):
        raise ArithmeticError("frequency-shift factor became invalid")

    arrays = (
        velocity,
        beta_squared,
        line_of_sight_beta,
        gravitational_lapse,
        lorentz_factor,
        special_relativistic_doppler,
        frequency_shift,
    )
    return StraightRayFrequencyShift(*(_readonly(array) for array in arrays))
