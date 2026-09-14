"""角分辨局域强度与半无限电子散射大气的线偏振近似。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .adaptive import SourceSurfaceRayQuadrature
from .geometry import SurfaceMesh, area_weighted_vertex_unit_normals
from .observer import Observer
from .radiation import planck_nu
from .raytrace import _mesh_fingerprint, observer_image_basis
from .source import PhysicalDomainError, ZOSourceGrid


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


def eddington_limb_darkening_factor(mu: ArrayLike) -> NDArray[np.float64]:
    """Return ``I(mu)/B = 3/4 (mu + 2/3)`` for ``0 <= mu <= 1``.

    The normalization obeys ``2 integral_0^1 factor*mu*dmu = 1``, so an
    isotropic Planck flux is redistributed in angle without changing the
    hemispheric energy flux.
    """
    cosine = np.asarray(mu, dtype=np.float64)
    if not np.all(np.isfinite(cosine)) or np.any((cosine < 0.0) | (cosine > 1.0)):
        raise PhysicalDomainError("mu must be finite and lie in [0, 1]")
    return 0.75 * (cosine + 2.0 / 3.0)


def chandrasekhar_polarization_fraction(mu: ArrayLike) -> NDArray[np.float64]:
    """Analytic fit to the conservative electron-scattering atmosphere.

    ``p=0.1171*(1-mu)/(1+3.582*mu)`` has the Chandrasekhar 11.71 percent
    limb limit and vanishes along the normal.  It is an atmosphere fit, not a
    solution for absorption-dominated or externally irradiated annuli.
    """
    cosine = np.asarray(mu, dtype=np.float64)
    if not np.all(np.isfinite(cosine)) or np.any((cosine < 0.0) | (cosine > 1.0)):
        raise PhysicalDomainError("mu must be finite and lie in [0, 1]")
    return 0.1171 * (1.0 - cosine) / (1.0 + 3.582 * cosine)


@dataclass(frozen=True)
class ObservedStokesSED:
    """Unresolved observer-frame Stokes spectrum; +Q is along image ``u``."""

    frequency_hz: NDArray[np.float64]
    flux_i_erg_s_cm2_hz: NDArray[np.float64]
    flux_q_erg_s_cm2_hz: NDArray[np.float64]
    flux_u_erg_s_cm2_hz: NDArray[np.float64]
    isotropic_equivalent_lnu_erg_s_hz: NDArray[np.float64]
    polarization_fraction: NDArray[np.float64]
    polarization_angle_rad: NDArray[np.float64]


def _validated_grid_field(
    name: str,
    values: ArrayLike | None,
    source: ZOSourceGrid,
    *,
    minimum: float,
) -> NDArray[np.float64]:
    if values is None:
        result = np.ones(source.shape, dtype=np.float64)
    else:
        result = np.array(values, dtype=np.float64, copy=True)
        if result.shape != source.shape:
            raise PhysicalDomainError(f"{name} must match source shape {source.shape}")
        invalid = (~np.isfinite(result)) | (result < minimum)
        if np.any(invalid):
            index = tuple(int(i) for i in np.argwhere(invalid)[0])
            raise PhysicalDomainError(f"{name} is invalid at index {index}")
    return result


def surface_stokes_sed(
    source: ZOSourceGrid,
    mesh: SurfaceMesh,
    observer: Observer,
    quadrature: SourceSurfaceRayQuadrature,
    frequency_hz: ArrayLike,
    *,
    frequency_shift_factor: ArrayLike | None = None,
    spectral_hardening_factor: ArrayLike | None = None,
    apply_limb_darkening: bool = True,
    apply_scattering_polarization: bool = True,
) -> ObservedStokesSED:
    """Integrate angle-resolved ``I,Q,U`` over the visible photosphere.

    Self-occultation remains encoded in the existing source-surface
    quadrature.  Polarization is computed locally and then added as Stokes
    vectors; Faraday rotation, returning radiation and GR parallel transport
    are outside this layer.
    """
    if mesh.vertex_grid_shape != source.shape:
        raise PhysicalDomainError("mesh vertex grid does not match source")
    if quadrature.mesh_face_count != mesh.faces.shape[0]:
        raise PhysicalDomainError("surface quadrature topology does not match mesh")
    if quadrature.mesh_fingerprint != _mesh_fingerprint(mesh):
        raise PhysicalDomainError("surface quadrature geometry does not match mesh")
    if not np.array_equal(quadrature.observer_direction, observer.direction_from_source):
        raise PhysicalDomainError("surface quadrature observer does not match observer")
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    if frequency.ndim != 1 or frequency.size == 0:
        raise PhysicalDomainError("frequency_hz must be a non-empty 1D grid")
    if not np.all(np.isfinite(frequency)) or np.any(frequency <= 0.0):
        raise PhysicalDomainError("frequency_hz must be finite and positive")
    if np.any(np.diff(frequency) <= 0.0):
        raise PhysicalDomainError("frequency_hz must be strictly increasing")

    shift = _validated_grid_field(
        "frequency_shift_factor", frequency_shift_factor, source, minimum=np.nextafter(0.0, 1.0)
    )
    hardening = _validated_grid_field(
        "spectral_hardening_factor", spectral_hardening_factor, source, minimum=1.0
    )
    vertex_normals = area_weighted_vertex_unit_normals(mesh)
    direction = observer.direction_from_source
    mu = vertex_normals @ direction
    weights = quadrature.vertex_projected_area_weights_cm2
    active = weights > 0.0
    if np.any((mu[active] < 0.0) | (mu[active] > 1.0)):
        index = int(np.flatnonzero(active & ((mu < 0.0) | (mu > 1.0)))[0])
        raise PhysicalDomainError(
            f"active vertex {index} has an invalid upper-surface emission cosine"
        )
    active_mu = mu[active]
    limb = np.ones_like(mu)
    if apply_limb_darkening:
        limb[active] = eddington_limb_darkening_factor(active_mu)
    polarization = np.zeros_like(mu)
    if apply_scattering_polarization:
        polarization[active] = chandrasekhar_polarization_fraction(active_mu)

    basis_u, basis_v = observer_image_basis(observer)
    electric = np.cross(np.broadcast_to(direction, vertex_normals.shape), vertex_normals)
    electric_u = electric @ basis_u
    electric_v = electric @ basis_v
    electric_norm_squared = electric_u**2 + electric_v**2
    cos_two_chi = np.ones_like(mu)
    sin_two_chi = np.zeros_like(mu)
    oriented = electric_norm_squared > 0.0
    # 中文：Stokes 角用二倍角，电矢量反号不会改变 Q/U；正视点因 p=0 无方向奇点。
    cos_two_chi[oriented] = (
        electric_u[oriented] ** 2 - electric_v[oriented] ** 2
    ) / electric_norm_squared[oriented]
    sin_two_chi[oriented] = (
        2.0 * electric_u[oriented] * electric_v[oriented]
    ) / electric_norm_squared[oriented]

    observed_temperature = (
        source.effective_temperature_k.reshape(-1)
        * shift.reshape(-1)
        * hardening.reshape(-1)
    )
    dilution = hardening.reshape(-1) ** (-4.0)
    flux_i = np.empty_like(frequency)
    flux_q = np.empty_like(frequency)
    flux_u = np.empty_like(frequency)
    geometric_i = weights * limb
    geometric_q = geometric_i * polarization * cos_two_chi
    geometric_u = geometric_i * polarization * sin_two_chi
    distance_squared = observer.distance_cm**2
    for index, nu in enumerate(frequency):
        intensity = dilution * planck_nu(nu, observed_temperature)
        flux_i[index] = np.sum(intensity * geometric_i, dtype=np.float64) / distance_squared
        flux_q[index] = np.sum(intensity * geometric_q, dtype=np.float64) / distance_squared
        flux_u[index] = np.sum(intensity * geometric_u, dtype=np.float64) / distance_squared
    polarized_flux = np.sqrt(flux_q**2 + flux_u**2)
    if np.any(flux_i <= 0.0):
        index = int(np.argwhere(flux_i <= 0.0)[0, 0])
        raise PhysicalDomainError(
            "polarization is undefined where total flux is zero; "
            f"failed at frequency index {index}"
        )
    if np.any(polarized_flux > flux_i * (1.0 + 2.0e-14)):
        raise ArithmeticError("integrated polarized flux exceeds Stokes I")
    fraction = polarized_flux / flux_i
    angle = 0.5 * np.arctan2(flux_u, flux_q)
    isotropic = 4.0 * np.pi * distance_squared * flux_i
    arrays = (frequency, flux_i, flux_q, flux_u, isotropic, fraction, angle)
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ArithmeticError("Stokes spectrum became non-finite")
    return ObservedStokesSED(*(_readonly(array) for array in arrays))
