"""LTE blackbody primitives in cgs units."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .source import PhysicalDomainError

PLANCK_ERG_S = 6.62607015e-27
BOLTZMANN_ERG_K = 1.380649e-16
LIGHT_SPEED_CM_S = 2.99792458e10
STEFAN_BOLTZMANN_ERG_S_CM2_K4 = 5.670374419e-5


def planck_nu(
    frequency_hz: ArrayLike, temperature_k: ArrayLike
) -> NDArray[np.float64]:
    """Planck specific intensity ``B_nu`` in erg s^-1 cm^-2 sr^-1 Hz^-1."""
    frequency, temperature = np.broadcast_arrays(
        np.asarray(frequency_hz, dtype=np.float64),
        np.asarray(temperature_k, dtype=np.float64),
    )
    for name, values in (("frequency_hz", frequency), ("temperature_k", temperature)):
        if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
            raise PhysicalDomainError(f"{name} must contain finite, strictly positive values")

    exponent = PLANCK_ERG_S * frequency / (BOLTZMANN_ERG_K * temperature)
    inverse_occupation = np.empty_like(exponent)
    moderate = exponent <= 50.0
    inverse_occupation[moderate] = 1.0 / np.expm1(exponent[moderate])
    wien_factor = np.exp(-exponent[~moderate])
    inverse_occupation[~moderate] = wien_factor / (1.0 - wien_factor)

    intensity = (
        2.0
        * PLANCK_ERG_S
        * frequency**3
        / LIGHT_SPEED_CM_S**2
        * inverse_occupation
    )
    if not np.all(np.isfinite(intensity)) or np.any(intensity < 0.0):
        raise ArithmeticError("Planck evaluation produced an invalid intensity")
    return intensity
