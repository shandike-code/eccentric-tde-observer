"""Corrected and historical face-on blackbody source integrals."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .quadrature import (
    corrected_zo_area_weights,
    pre_erratum_zo2020_area_weights,
)
from .radiation import STEFAN_BOLTZMANN_ERG_S_CM2_K4, planck_nu
from .source import PhysicalDomainError, ZOSourceGrid


@dataclass(frozen=True)
class FaceOnSED:
    frequency_hz: NDArray[np.float64]
    isotropic_equivalent_lnu_erg_s_hz: NDArray[np.float64]
    intrinsic_two_sided_lnu_erg_s_hz: NDArray[np.float64]

    @property
    def nu_lnu_isotropic_erg_s(self) -> NDArray[np.float64]:
        return self.frequency_hz * self.isotropic_equivalent_lnu_erg_s_hz


@dataclass(frozen=True)
class PreErratumFaceOnSED:
    frequency_hz: NDArray[np.float64]
    isotropic_equivalent_lnu_erg_s_hz: NDArray[np.float64]
    pre_erratum_two_sided_lnu_erg_s_hz: NDArray[np.float64]

    @property
    def nu_lnu_isotropic_erg_s(self) -> NDArray[np.float64]:
        return self.frequency_hz * self.isotropic_equivalent_lnu_erg_s_hz


def face_on_blackbody_sed(source: ZOSourceGrid, frequency_hz: ArrayLike) -> FaceOnSED:
    """Integrate the corrected face-on LTE source with no self-occultation.

    ``L_nu,iso = 4*pi*int B_nu dA_corr`` is the distant face-on
    isotropic-equivalent luminosity.  ``L_nu,2face = 2*pi*int B_nu dA_corr``
    is the intrinsic luminosity radiated by both disc faces.
    """
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    if frequency.ndim != 1 or frequency.size == 0:
        raise PhysicalDomainError("frequency_hz must be a non-empty one-dimensional grid")
    if not np.all(np.isfinite(frequency)) or np.any(frequency <= 0.0):
        raise PhysicalDomainError("frequency_hz must contain finite, strictly positive values")
    if np.any(np.diff(frequency) <= 0.0):
        raise PhysicalDomainError("frequency_hz must be strictly increasing")

    area_weights = corrected_zo_area_weights(source)
    integrated_intensity = np.empty_like(frequency)
    for index, nu in enumerate(frequency):
        local_intensity = planck_nu(nu, source.effective_temperature_k)
        integrated_intensity[index] = np.sum(
            local_intensity * area_weights, dtype=np.float64
        )

    isotropic = 4.0 * np.pi * integrated_intensity
    intrinsic_two_sided = 2.0 * np.pi * integrated_intensity
    frequency.setflags(write=False)
    isotropic.setflags(write=False)
    intrinsic_two_sided.setflags(write=False)
    return FaceOnSED(frequency, isotropic, intrinsic_two_sided)


def pre_erratum_face_on_blackbody_sed(
    source: ZOSourceGrid, frequency_hz: ArrayLike
) -> PreErratumFaceOnSED:
    """Integrate the same LTE field with the incorrect 2020 area measure."""
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    if frequency.ndim != 1 or frequency.size == 0:
        raise PhysicalDomainError("frequency_hz must be a non-empty one-dimensional grid")
    if not np.all(np.isfinite(frequency)) or np.any(frequency <= 0.0):
        raise PhysicalDomainError("frequency_hz must contain finite, strictly positive values")
    if np.any(np.diff(frequency) <= 0.0):
        raise PhysicalDomainError("frequency_hz must be strictly increasing")

    area_weights = pre_erratum_zo2020_area_weights(source)
    integrated_intensity = np.empty_like(frequency)
    for index, nu in enumerate(frequency):
        local_intensity = planck_nu(nu, source.effective_temperature_k)
        integrated_intensity[index] = np.sum(
            local_intensity * area_weights, dtype=np.float64
        )
    isotropic = 4.0 * np.pi * integrated_intensity
    two_sided = 2.0 * np.pi * integrated_intensity
    for array in (frequency, isotropic, two_sided):
        array.setflags(write=False)
    return PreErratumFaceOnSED(frequency, isotropic, two_sided)


def face_on_bolometric_luminosities(source: ZOSourceGrid) -> tuple[float, float]:
    """Return corrected ``(L_iso, L_intrinsic_two_sided)`` in erg s^-1."""
    emitted_flux = (
        STEFAN_BOLTZMANN_ERG_S_CM2_K4 * source.effective_temperature_k**4
    )
    one_face = float(
        np.sum(emitted_flux * corrected_zo_area_weights(source), dtype=np.float64)
    )
    return 4.0 * one_face, 2.0 * one_face


def pre_erratum_face_on_bolometric_luminosities(
    source: ZOSourceGrid,
) -> tuple[float, float]:
    """Return historical 2020 ``(L_iso, L_two_sided)`` for regression only."""
    emitted_flux = (
        STEFAN_BOLTZMANN_ERG_S_CM2_K4 * source.effective_temperature_k**4
    )
    one_face = float(
        np.sum(
            emitted_flux * pre_erratum_zo2020_area_weights(source),
            dtype=np.float64,
        )
    )
    return 4.0 * one_face, 2.0 * one_face
