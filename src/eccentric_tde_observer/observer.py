"""Unobscured Newtonian projection from a triangular surface to an observer."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .geometry import SurfaceMesh
from .radiation import planck_nu
from .source import PhysicalDomainError, ZOSourceGrid


@dataclass(frozen=True)
class Observer:
    """A distant observer above the disc plane.

    ``inclination_rad`` is measured from the positive disc normal and
    ``azimuth_rad`` from the inertial positive x-axis toward positive y.
    """

    distance_cm: float
    inclination_rad: float
    azimuth_rad: float

    def __post_init__(self) -> None:
        distance = float(self.distance_cm)
        inclination = float(self.inclination_rad)
        azimuth = float(self.azimuth_rad)
        if not np.isfinite(distance) or distance <= 0.0:
            raise PhysicalDomainError("observer distance_cm must be finite and positive")
        if (
            not np.isfinite(inclination)
            or inclination < 0.0
            or inclination >= 0.5 * np.pi
        ):
            raise PhysicalDomainError(
                "inclination_rad must satisfy 0 <= i < pi/2 for the upper surface"
            )
        if not np.isfinite(azimuth):
            raise PhysicalDomainError("azimuth_rad must be finite")
        object.__setattr__(self, "distance_cm", distance)
        object.__setattr__(self, "inclination_rad", inclination)
        object.__setattr__(self, "azimuth_rad", azimuth)

    @property
    def direction_from_source(self) -> NDArray[np.float64]:
        sine = np.sin(self.inclination_rad)
        direction = np.array(
            [
                sine * np.cos(self.azimuth_rad),
                sine * np.sin(self.azimuth_rad),
                np.cos(self.inclination_rad),
            ],
            dtype=np.float64,
        )
        direction.setflags(write=False)
        return direction


@dataclass(frozen=True)
class ObservedSED:
    frequency_hz: NDArray[np.float64]
    flux_density_erg_s_cm2_hz: NDArray[np.float64]
    isotropic_equivalent_lnu_erg_s_hz: NDArray[np.float64]


def face_projection_cosines(
    mesh: SurfaceMesh, observer: Observer
) -> NDArray[np.float64]:
    cosines = mesh.face_unit_normals @ observer.direction_from_source
    if not np.all(np.isfinite(cosines)):
        raise ArithmeticError("surface projection produced a non-finite cosine")
    cosines.setflags(write=False)
    return cosines


def unobscured_projected_area_cm2(mesh: SurfaceMesh, observer: Observer) -> float:
    """Projected area of front-facing triangles, without self-occultation."""
    cosines = face_projection_cosines(mesh, observer)
    front_facing = cosines > 0.0
    return float(
        np.sum(
            cosines[front_facing] * mesh.face_areas_cm2[front_facing],
            dtype=np.float64,
        )
    )


def unobscured_blackbody_sed(
    source: ZOSourceGrid,
    mesh: SurfaceMesh,
    observer: Observer,
    frequency_hz: ArrayLike,
) -> ObservedSED:
    """Integrate LTE intensity over front-facing triangles without occultation.

    Vertex intensities are averaged over each triangle.  This is a numerical
    surface quadrature, not a new atmosphere closure and not a ray tracer.
    """
    if mesh.vertex_grid_shape != source.shape:
        raise PhysicalDomainError("mesh vertex grid does not match the source grid")
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    if frequency.ndim != 1 or frequency.size == 0:
        raise PhysicalDomainError("frequency_hz must be a non-empty one-dimensional grid")
    if not np.all(np.isfinite(frequency)) or np.any(frequency <= 0.0):
        raise PhysicalDomainError("frequency_hz must contain finite, positive values")
    if np.any(np.diff(frequency) <= 0.0):
        raise PhysicalDomainError("frequency_hz must be strictly increasing")

    cosines = face_projection_cosines(mesh, observer)
    front_facing = cosines > 0.0
    projected_face_areas = (
        cosines[front_facing] * mesh.face_areas_cm2[front_facing]
    )
    visible_faces = mesh.faces[front_facing]
    vertex_temperature = source.effective_temperature_k.reshape(-1)
    flux_density = np.empty_like(frequency)
    for index, nu in enumerate(frequency):
        vertex_intensity = planck_nu(nu, vertex_temperature)
        face_intensity = np.mean(vertex_intensity[visible_faces], axis=1)
        flux_density[index] = np.sum(
            face_intensity * projected_face_areas, dtype=np.float64
        ) / observer.distance_cm**2

    isotropic_equivalent = 4.0 * np.pi * observer.distance_cm**2 * flux_density
    for array in (frequency, flux_density, isotropic_equivalent):
        array.setflags(write=False)
    return ObservedSED(frequency, flux_density, isotropic_equivalent)
