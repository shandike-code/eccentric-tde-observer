"""再处理层的守恒约束；本模块不向裸盘模型加入盘风。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .radiation import LIGHT_SPEED_CM_S
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


def _positive_array(name: str, values: ArrayLike) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(array)) or np.any(array <= 0.0):
        raise PhysicalDomainError(f"{name} must be finite and strictly positive")
    return array


@dataclass(frozen=True)
class ThermalizingLayerRequirement:
    """A static column requirement parameterized by absorption fraction."""

    radius_cm: NDArray[np.float64]
    absorption_fraction: NDArray[np.float64]
    total_optical_depth: NDArray[np.float64]
    surface_density_g_cm2: NDArray[np.float64]
    full_coverage_mass_g: NDArray[np.float64]
    diffusion_time_per_fractional_thickness_s: NDArray[np.float64]
    target_effective_optical_depth: float
    electron_scattering_opacity_cm2_g: float


def minimum_thermalizing_layer_requirement(
    radius_cm: ArrayLike,
    absorption_fraction: ArrayLike,
    *,
    target_effective_optical_depth: float = 1.0,
    electron_scattering_opacity_cm2_g: float = 0.34,
) -> ThermalizingLayerRequirement:
    """Return the minimum column from ``tau_eff=sqrt(3 epsilon)*tau_tot``.

    ``epsilon=kappa_abs/kappa_tot`` is an axis of the constraint map, not a
    fitted wind parameter.  The reported mass assumes unit covering fraction;
    other covering fractions multiply it linearly.  The diffusion time is
    reported per ``Delta R/R`` so no shell thickness is silently chosen.
    """
    radius = _positive_array("radius_cm", radius_cm)
    epsilon = np.asarray(absorption_fraction, dtype=np.float64)
    if not np.all(np.isfinite(epsilon)) or np.any((epsilon <= 0.0) | (epsilon >= 1.0)):
        raise PhysicalDomainError("absorption_fraction must lie strictly in (0, 1)")
    radius, epsilon = np.broadcast_arrays(radius, epsilon)
    target = float(target_effective_optical_depth)
    scattering = float(electron_scattering_opacity_cm2_g)
    if not np.isfinite(target) or target <= 0.0:
        raise PhysicalDomainError("target_effective_optical_depth must be positive")
    if not np.isfinite(scattering) or scattering <= 0.0:
        raise PhysicalDomainError("electron_scattering_opacity_cm2_g must be positive")

    # 中文：先由有效光深求总光深，再用 kappa_tot=kappa_es/(1-epsilon) 求柱密度。
    total_depth = target / np.sqrt(3.0 * epsilon)
    total_opacity = scattering / (1.0 - epsilon)
    surface_density = total_depth / total_opacity
    mass = 4.0 * np.pi * radius**2 * surface_density
    diffusion_per_fractional_thickness = total_depth * radius / LIGHT_SPEED_CM_S
    arrays = (
        radius,
        epsilon,
        total_depth,
        surface_density,
        mass,
        diffusion_per_fractional_thickness,
    )
    if not all(np.all(np.isfinite(array)) and np.all(array > 0.0) for array in arrays):
        raise ArithmeticError("thermalizing-layer requirement became invalid")
    return ThermalizingLayerRequirement(
        *(_readonly(np.asarray(array)) for array in arrays),
        target_effective_optical_depth=target,
        electron_scattering_opacity_cm2_g=scattering,
    )


def minimum_seed_luminosity_erg_s(
    reprocessed_luminosity_erg_s: ArrayLike,
    covering_fraction: ArrayLike,
    *,
    absorbed_fraction_of_intercepted_power: ArrayLike = 1.0,
) -> NDArray[np.float64]:
    """Energy-conservation lower bound ``L_seed=L_rep/(C*f_abs)``."""
    luminosity = _positive_array("reprocessed_luminosity_erg_s", reprocessed_luminosity_erg_s)
    covering = np.asarray(covering_fraction, dtype=np.float64)
    absorbed = np.asarray(absorbed_fraction_of_intercepted_power, dtype=np.float64)
    for name, value in (("covering_fraction", covering), ("absorbed fraction", absorbed)):
        if not np.all(np.isfinite(value)) or np.any((value <= 0.0) | (value > 1.0)):
            raise PhysicalDomainError(f"{name} must lie in (0, 1]")
    luminosity, covering, absorbed = np.broadcast_arrays(luminosity, covering, absorbed)
    result = luminosity / (covering * absorbed)
    if not np.all(np.isfinite(result)):
        raise ArithmeticError("minimum seed luminosity became non-finite")
    return _readonly(result)


def momentum_limited_mass_loss_rate_g_s(
    seed_luminosity_erg_s: ArrayLike,
    outflow_speed_cm_s: ArrayLike,
    *,
    momentum_optical_depth: ArrayLike = 1.0,
) -> NDArray[np.float64]:
    """Maximum steady ``Mdot`` allowed by ``Mdot*v <= tau_mom*L/c``.

    This is a diagnostic bound only.  Calling it does not add an outflow to
    the source-to-observer calculation.
    """
    luminosity = _positive_array("seed_luminosity_erg_s", seed_luminosity_erg_s)
    speed = _positive_array("outflow_speed_cm_s", outflow_speed_cm_s)
    optical_depth = _positive_array("momentum_optical_depth", momentum_optical_depth)
    luminosity, speed, optical_depth = np.broadcast_arrays(luminosity, speed, optical_depth)
    if np.any(speed >= LIGHT_SPEED_CM_S):
        raise PhysicalDomainError("outflow_speed_cm_s must remain subluminal")
    result = optical_depth * luminosity / (LIGHT_SPEED_CM_S * speed)
    if not np.all(np.isfinite(result)):
        raise ArithmeticError("momentum-limited mass-loss rate became non-finite")
    return _readonly(result)
