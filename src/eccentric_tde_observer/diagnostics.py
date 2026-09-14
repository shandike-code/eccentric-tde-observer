"""Observable diagnostics derived from a frequency-resolved model spectrum."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike
from scipy.optimize import minimize_scalar

from .radiation import STEFAN_BOLTZMANN_ERG_S_CM2_K4, planck_nu
from .source import PhysicalDomainError


class BlackbodyFitBoundaryError(RuntimeError):
    """Raised when the best fit is pinned to an imposed temperature bound."""


@dataclass(frozen=True)
class BlackbodyFit:
    """Single-temperature fit to an isotropic-equivalent ``L_nu`` spectrum."""

    temperature_k: float
    radius_cm: float
    bolometric_luminosity_erg_s: float
    rms_log10_residual_dex: float
    frequency_min_max_hz: tuple[float, float]
    fitted_point_count: int


def fit_isotropic_blackbody_lnu(
    frequency_hz: ArrayLike,
    isotropic_equivalent_lnu_erg_s_hz: ArrayLike,
    fit_frequency_min_hz: float,
    fit_frequency_max_hz: float,
    *,
    temperature_bounds_k: tuple[float, float] = (1.0e3, 1.0e7),
) -> BlackbodyFit:
    """Fit ``L_nu=4*pi^2*R_bb^2*B_nu(T_bb)`` in logarithmic flux.

    Every selected frequency receives equal weight.  This is an explicit
    diagnostic convention, not an instrument-specific likelihood.
    """
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    luminosity = np.asarray(
        isotropic_equivalent_lnu_erg_s_hz, dtype=np.float64
    )
    if frequency.ndim != 1 or luminosity.shape != frequency.shape:
        raise PhysicalDomainError(
            "frequency and luminosity must be matching one-dimensional arrays"
        )
    if frequency.size < 3 or not np.all(np.isfinite(frequency)) or np.any(
        frequency <= 0.0
    ):
        raise PhysicalDomainError(
            "frequency must contain at least three finite positive values"
        )
    if np.any(np.diff(frequency) <= 0.0):
        raise PhysicalDomainError("frequency must be strictly increasing")
    if not np.all(np.isfinite(luminosity)) or np.any(luminosity < 0.0):
        raise PhysicalDomainError("luminosity must be finite and non-negative")
    fit_min = float(fit_frequency_min_hz)
    fit_max = float(fit_frequency_max_hz)
    if (
        not np.isfinite(fit_min)
        or not np.isfinite(fit_max)
        or fit_min <= 0.0
        or fit_max <= fit_min
    ):
        raise PhysicalDomainError(
            "fit-frequency bounds must be finite, positive, and increasing"
        )
    lower_temperature = float(temperature_bounds_k[0])
    upper_temperature = float(temperature_bounds_k[1])
    if (
        not np.isfinite(lower_temperature)
        or not np.isfinite(upper_temperature)
        or lower_temperature <= 0.0
        or upper_temperature <= lower_temperature
    ):
        raise PhysicalDomainError(
            "temperature bounds must be finite, positive, and increasing"
        )
    selected = (frequency >= fit_min) & (frequency <= fit_max)
    if np.count_nonzero(selected) < 3:
        raise PhysicalDomainError("fit band must contain at least three grid points")
    if np.any(luminosity[selected] <= 0.0):
        raise PhysicalDomainError(
            "luminosity must be strictly positive inside the fit band"
        )
    fit_frequency = frequency[selected]
    log_luminosity = np.log(luminosity[selected])

    def objective(log_temperature: float) -> float:
        temperature = np.exp(log_temperature)
        intensity = planck_nu(fit_frequency, temperature)
        if np.any(intensity <= 0.0):
            return np.inf
        log_shape = np.log(intensity)
        log_amplitude = float(np.mean(log_luminosity - log_shape))
        residual = log_luminosity - (log_amplitude + log_shape)
        return float(np.mean(residual**2))

    log_lower = np.log(lower_temperature)
    log_upper = np.log(upper_temperature)
    result = minimize_scalar(
        objective,
        method="bounded",
        bounds=(log_lower, log_upper),
        options={"xatol": 1.0e-12},
    )
    if not result.success or not np.isfinite(result.fun):
        raise RuntimeError("single-temperature blackbody fit did not converge")
    boundary_tolerance = 2.0e-6 * (log_upper - log_lower)
    if (
        result.x - log_lower <= boundary_tolerance
        or log_upper - result.x <= boundary_tolerance
    ):
        raise BlackbodyFitBoundaryError(
            "blackbody temperature fit is pinned to an imposed bound"
        )
    temperature = float(np.exp(result.x))
    log_shape = np.log(planck_nu(fit_frequency, temperature))
    log_amplitude = float(np.mean(log_luminosity - log_shape))
    amplitude = float(np.exp(log_amplitude))
    radius = float(np.sqrt(amplitude / (4.0 * np.pi**2)))
    residual_dex = (
        log_luminosity - (log_amplitude + log_shape)
    ) / np.log(10.0)
    bolometric_luminosity = (
        4.0
        * np.pi
        * radius**2
        * STEFAN_BOLTZMANN_ERG_S_CM2_K4
        * temperature**4
    )
    for name, value in (
        ("temperature", temperature),
        ("radius", radius),
        ("bolometric luminosity", bolometric_luminosity),
    ):
        if not np.isfinite(value) or value <= 0.0:
            raise ArithmeticError(f"fitted blackbody {name} is invalid")
    return BlackbodyFit(
        temperature_k=temperature,
        radius_cm=radius,
        bolometric_luminosity_erg_s=float(bolometric_luminosity),
        rms_log10_residual_dex=float(np.sqrt(np.mean(residual_dex**2))),
        frequency_min_max_hz=(float(fit_frequency[0]), float(fit_frequency[-1])),
        fitted_point_count=int(fit_frequency.size),
    )
