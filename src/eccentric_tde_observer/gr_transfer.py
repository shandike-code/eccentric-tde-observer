"""Cunningham 式像平面传递的 Schwarzschild 直接像弱场实现。

传递被拆成像平面面积权重与频移 ``g``，从而使用
``F_nu = D^-2 sum(dA_image * g^3 I_em(nu/g))``。当前光线方向采用
Beloborodov 直接像关系；不包含 Kerr 自旋、多像、时间延迟或曲线自遮挡。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .geometry import SurfaceMesh, area_weighted_vertex_unit_normals
from .observer import ObservedSED, Observer
from .polarization import eddington_limb_darkening_factor
from .radiation import LIGHT_SPEED_CM_S, planck_nu
from .raytrace import _mesh_fingerprint, observer_image_basis
from .relativity import (
    GRAVITATIONAL_CONSTANT_CGS,
    _black_hole_mass_g,
    keplerian_orbital_velocity_cm_s,
)
from .source import PhysicalDomainError, ZOSourceGrid


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class SchwarzschildDirectImageTransfer:
    """Per-vertex direct-image map and observer transfer factor."""

    image_u_cm: NDArray[np.float64]
    image_v_cm: NDArray[np.float64]
    photon_direction_at_emitter: NDArray[np.float64]
    compactness_2gm_rc2: NDArray[np.float64]
    gravitational_lapse: NDArray[np.float64]
    frequency_shift_factor: NDArray[np.float64]
    vertex_image_area_weights_cm2: NDArray[np.float64]
    direct_image_area_cm2: float
    front_facing_face_count: int
    observer_direction: NDArray[np.float64]
    mesh_face_count: int
    mesh_fingerprint: str
    approximation_label: str = (
        "Cunningham-style Schwarzschild direct image with Beloborodov ray map; "
        "no multiple images or curved-ray self-occultation"
    )


def beloborodov_schwarzschild_direct_image_transfer(
    source: ZOSourceGrid,
    mesh: SurfaceMesh,
    observer: Observer,
    black_hole_mass_msun: float,
    *,
    vertical_velocity_cm_s: ArrayLike | None = None,
) -> SchwarzschildDirectImageTransfer:
    """Map a photosphere to a distant Schwarzschild direct image.

    The adopted angular relation is
    ``1-cos(alpha)=(1-2GM/rc^2)*(1-cos(psi))``.  It is highly accurate in the
    present weak field, but the code deliberately labels it approximate and
    rejects horizons, superluminal matter and unresolved back-axis caustics.
    """
    if mesh.vertex_grid_shape != source.shape:
        raise PhysicalDomainError("mesh vertex grid does not match source")
    mass_g = _black_hole_mass_g(black_hole_mass_msun)
    position = mesh.vertices_cm
    radius = np.linalg.norm(position, axis=1)
    if not np.all(np.isfinite(radius)) or np.any(radius <= 0.0):
        raise PhysicalDomainError("emitting radius must be finite and positive")
    compactness = (
        2.0 * GRAVITATIONAL_CONSTANT_CGS * mass_g
        / (radius * LIGHT_SPEED_CM_S**2)
    )
    if np.any(compactness >= 1.0):
        index = int(np.argwhere(compactness >= 1.0)[0, 0])
        raise PhysicalDomainError(f"emitting vertex {index} lies on or inside horizon")

    direction = observer.direction_from_source
    radial_hat = position / radius[:, None]
    cos_psi = radial_hat @ direction
    if np.any((cos_psi < -1.0) | (cos_psi > 1.0)):
        raise ArithmeticError("source-observer angular cosine left [-1, 1]")
    cos_alpha = compactness + (1.0 - compactness) * cos_psi
    sin_alpha_squared = 1.0 - cos_alpha**2
    if np.any(sin_alpha_squared < 0.0):
        index = int(np.argwhere(sin_alpha_squared < 0.0)[0, 0])
        raise ArithmeticError(f"ray emission angle became invalid at vertex {index}")
    sin_alpha = np.sqrt(sin_alpha_squared)

    projected_radial = radial_hat - cos_psi[:, None] * direction
    sin_psi = np.linalg.norm(projected_radial, axis=1)
    image_radial_hat = np.zeros_like(position)
    non_axial = sin_psi > 0.0
    image_radial_hat[non_axial] = (
        projected_radial[non_axial] / sin_psi[non_axial, None]
    )
    unresolved_back_axis = (~non_axial) & (sin_alpha > 0.0)
    if np.any(unresolved_back_axis):
        index = int(np.argwhere(unresolved_back_axis)[0, 0])
        raise PhysicalDomainError(
            f"vertex {index} lies on an unresolved Schwarzschild back-axis caustic"
        )

    toward_observer_tangent = np.zeros_like(position)
    toward_observer_tangent[non_axial] = (
        direction - cos_psi[non_axial, None] * radial_hat[non_axial]
    ) / sin_psi[non_axial, None]
    photon_direction = (
        cos_alpha[:, None] * radial_hat
        + sin_alpha[:, None] * toward_observer_tangent
    )
    front_axis = (~non_axial) & (cos_alpha > 0.0)
    photon_direction[front_axis] = radial_hat[front_axis]
    photon_norm = np.linalg.norm(photon_direction, axis=1)
    if not np.allclose(photon_norm, 1.0, rtol=0.0, atol=5.0e-13):
        raise ArithmeticError("emitter photon direction is not unit normalized")

    # 中文：b 是远方像平面的冲量参数；其三角形面积直接给 dOmega*D^2。
    impact_parameter = radius * sin_alpha / np.sqrt(1.0 - compactness)
    basis_u, basis_v = observer_image_basis(observer)
    image_u = impact_parameter * (image_radial_hat @ basis_u)
    image_v = impact_parameter * (image_radial_hat @ basis_v)
    image_coordinates = np.column_stack((image_u, image_v))
    image_triangles = image_coordinates[mesh.faces]
    signed_double_area = (
        (image_triangles[:, 1, 0] - image_triangles[:, 0, 0])
        * (image_triangles[:, 2, 1] - image_triangles[:, 0, 1])
        - (image_triangles[:, 1, 1] - image_triangles[:, 0, 1])
        * (image_triangles[:, 2, 0] - image_triangles[:, 0, 0])
    )
    face_photon_direction = np.mean(photon_direction[mesh.faces], axis=1)
    face_emission_cosine = np.einsum(
        "ij,ij->i", mesh.face_unit_normals, face_photon_direction
    )
    front_faces = face_emission_cosine > 0.0
    if not np.any(front_faces):
        raise PhysicalDomainError("GR direct image has no front-facing faces")
    if np.any(signed_double_area[front_faces] <= 0.0):
        index = int(np.flatnonzero(front_faces & (signed_double_area <= 0.0))[0])
        raise PhysicalDomainError(
            f"direct-image face {index} has a fold or parity reversal; multiple-image transfer is required"
        )
    face_image_area = 0.5 * signed_double_area[front_faces]
    vertex_weights = np.zeros(position.shape[0], dtype=np.float64)
    for corner in range(3):
        vertex_weights += np.bincount(
            mesh.faces[front_faces, corner],
            weights=face_image_area / 3.0,
            minlength=position.shape[0],
        )
    direct_image_area = float(np.sum(face_image_area, dtype=np.float64))
    if not np.isclose(
        np.sum(vertex_weights, dtype=np.float64), direct_image_area, rtol=2.0e-14
    ):
        raise ArithmeticError("GR image face area and vertex weights disagree")

    velocity = np.array(
        keplerian_orbital_velocity_cm_s(source, black_hole_mass_msun), copy=True
    ).reshape(-1, 3)
    if vertical_velocity_cm_s is not None:
        vertical_velocity = np.asarray(vertical_velocity_cm_s, dtype=np.float64)
        if vertical_velocity.shape != source.shape or not np.all(np.isfinite(vertical_velocity)):
            raise PhysicalDomainError(
                f"vertical_velocity_cm_s must be finite with shape {source.shape}"
            )
        velocity[:, 2] = vertical_velocity.reshape(-1)
    beta = velocity / LIGHT_SPEED_CM_S
    beta_squared = np.sum(beta**2, axis=1)
    if np.any((~np.isfinite(beta_squared)) | (beta_squared >= 1.0)):
        index = int(np.argwhere((~np.isfinite(beta_squared)) | (beta_squared >= 1.0))[0, 0])
        raise PhysicalDomainError(f"emitting matter is superluminal at vertex {index}")
    line_of_sight_beta = np.einsum("ij,ij->i", beta, photon_direction)
    denominator = 1.0 - line_of_sight_beta
    if np.any(denominator <= 0.0):
        raise PhysicalDomainError("GR Doppler denominator must be positive")
    lapse = np.sqrt(1.0 - compactness)
    lorentz_factor = 1.0 / np.sqrt(1.0 - beta_squared)
    frequency_shift = lapse / (lorentz_factor * denominator)
    if not np.all(np.isfinite(frequency_shift)) or np.any(frequency_shift <= 0.0):
        raise ArithmeticError("GR direct-image frequency shift became invalid")

    return SchwarzschildDirectImageTransfer(
        image_u_cm=_readonly(image_u),
        image_v_cm=_readonly(image_v),
        photon_direction_at_emitter=_readonly(photon_direction.reshape(source.shape + (3,))),
        compactness_2gm_rc2=_readonly(compactness.reshape(source.shape)),
        gravitational_lapse=_readonly(lapse.reshape(source.shape)),
        frequency_shift_factor=_readonly(frequency_shift.reshape(source.shape)),
        vertex_image_area_weights_cm2=_readonly(vertex_weights),
        direct_image_area_cm2=direct_image_area,
        front_facing_face_count=int(np.count_nonzero(front_faces)),
        observer_direction=_readonly(np.array(direction, copy=True)),
        mesh_face_count=int(mesh.faces.shape[0]),
        mesh_fingerprint=_mesh_fingerprint(mesh),
    )


def gr_direct_image_sed(
    source: ZOSourceGrid,
    mesh: SurfaceMesh,
    observer: Observer,
    transfer: SchwarzschildDirectImageTransfer,
    frequency_hz: ArrayLike,
    *,
    spectral_hardening_factor: ArrayLike | None = None,
    apply_limb_darkening: bool = True,
) -> ObservedSED:
    """Integrate the direct-image spectrum with invariant ``I_nu/nu^3``."""
    if mesh.vertex_grid_shape != source.shape:
        raise PhysicalDomainError("mesh vertex grid does not match source")
    if transfer.mesh_fingerprint != _mesh_fingerprint(mesh):
        raise PhysicalDomainError("GR transfer geometry does not match mesh")
    if not np.array_equal(transfer.observer_direction, observer.direction_from_source):
        raise PhysicalDomainError("GR transfer observer does not match observer")
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    if frequency.ndim != 1 or frequency.size == 0:
        raise PhysicalDomainError("frequency_hz must be a non-empty 1D grid")
    if not np.all(np.isfinite(frequency)) or np.any(frequency <= 0.0):
        raise PhysicalDomainError("frequency_hz must be finite and positive")
    if np.any(np.diff(frequency) <= 0.0):
        raise PhysicalDomainError("frequency_hz must be strictly increasing")
    if spectral_hardening_factor is None:
        hardening = np.ones(source.shape, dtype=np.float64)
    else:
        hardening = np.array(spectral_hardening_factor, dtype=np.float64, copy=True)
        if hardening.shape != source.shape:
            raise PhysicalDomainError("spectral_hardening_factor must match source")
        if np.any((~np.isfinite(hardening)) | (hardening < 1.0)):
            raise PhysicalDomainError("spectral_hardening_factor must be finite and >=1")

    weights = transfer.vertex_image_area_weights_cm2
    active = weights > 0.0
    angular_factor = np.ones_like(weights)
    if apply_limb_darkening:
        normals = area_weighted_vertex_unit_normals(mesh)
        photon = transfer.photon_direction_at_emitter.reshape(-1, 3)
        mu = np.einsum("ij,ij->i", normals, photon)
        if np.any((mu[active] < 0.0) | (mu[active] > 1.0)):
            index = int(np.flatnonzero(active & ((mu < 0.0) | (mu > 1.0)))[0])
            raise PhysicalDomainError(f"active GR vertex {index} has invalid emission mu")
        angular_factor[active] = eddington_limb_darkening_factor(mu[active])
    observed_temperature = (
        source.effective_temperature_k
        * transfer.frequency_shift_factor
        * hardening
    ).reshape(-1)
    dilution = hardening.reshape(-1) ** (-4.0)
    flux = np.empty_like(frequency)
    for index, nu in enumerate(frequency):
        intensity = dilution * planck_nu(nu, observed_temperature)
        flux[index] = np.sum(
            intensity * weights * angular_factor, dtype=np.float64
        ) / observer.distance_cm**2
    isotropic = 4.0 * np.pi * observer.distance_cm**2 * flux
    if not np.all(np.isfinite(flux)) or np.any(flux < 0.0):
        raise ArithmeticError("GR direct-image spectrum became invalid")
    return ObservedSED(_readonly(frequency), _readonly(flux), _readonly(isotropic))
