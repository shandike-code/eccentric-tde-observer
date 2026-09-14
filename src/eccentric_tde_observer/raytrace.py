"""Orthographic Newtonian ray tracing and frontmost-surface selection."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .geometry import SurfaceMesh
from .observer import ObservedSED, Observer
from .radiation import planck_nu
from .source import PhysicalDomainError, ZOSourceGrid


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


def _mesh_fingerprint(mesh: SurfaceMesh) -> str:
    digest = hashlib.sha256()
    digest.update(np.ascontiguousarray(mesh.vertices_cm).tobytes())
    digest.update(np.ascontiguousarray(mesh.faces).tobytes())
    return digest.hexdigest()


def observer_image_basis(
    observer: Observer,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return right-handed image-plane basis vectors ``(u, v)``.

    Together with the source-to-observer direction ``n``, the convention is
    ``u cross v = n``.  Image depth is therefore ``r dot n`` and the observer
    sees the largest depth first.
    """
    inclination = observer.inclination_rad
    azimuth = observer.azimuth_rad
    basis_u = np.array(
        [-np.sin(azimuth), np.cos(azimuth), 0.0], dtype=np.float64
    )
    basis_v = np.array(
        [
            -np.cos(inclination) * np.cos(azimuth),
            -np.cos(inclination) * np.sin(azimuth),
            np.sin(inclination),
        ],
        dtype=np.float64,
    )
    return _readonly(basis_u), _readonly(basis_v)


@dataclass(frozen=True)
class RayImage:
    """Rasterized frontmost intersection for an orthographic observer."""

    u_centers_cm: NDArray[np.float64]
    v_centers_cm: NDArray[np.float64]
    pixel_area_cm2: float
    frontmost_face_index: NDArray[np.int64]
    frontmost_barycentric: NDArray[np.float64]
    frontmost_depth_cm: NDArray[np.float64]
    hit_mask: NDArray[np.bool_]
    emitting_mask: NDArray[np.bool_]
    observer_direction: NDArray[np.float64]
    mesh_face_count: int
    mesh_fingerprint: str
    vertex_projected_area_weights_cm2: NDArray[np.float64]

    @property
    def shape(self) -> tuple[int, int]:
        return self.frontmost_face_index.shape

    @property
    def ray_count(self) -> int:
        return int(self.frontmost_face_index.size)

    @property
    def hit_count(self) -> int:
        return int(np.count_nonzero(self.hit_mask))

    @property
    def emitting_count(self) -> int:
        return int(np.count_nonzero(self.emitting_mask))

    @property
    def visible_projected_area_cm2(self) -> float:
        return float(self.emitting_count * self.pixel_area_cm2)


def render_orthographic_surface(
    mesh: SurfaceMesh,
    observer: Observer,
    pixels_long_axis: int,
) -> RayImage:
    """Rasterize a triangular surface with a deterministic depth buffer.

    Every image-plane pixel represents one parallel ray.  All triangles can
    block a ray, but only a selected front-facing triangle emits from the upper
    surface in this first-stage model.
    """
    if not isinstance(pixels_long_axis, (int, np.integer)) or isinstance(
        pixels_long_axis, (bool, np.bool_)
    ):
        raise PhysicalDomainError("pixels_long_axis must be an integer")
    pixels_long_axis = int(pixels_long_axis)
    if pixels_long_axis < 8:
        raise PhysicalDomainError("pixels_long_axis must be at least 8")

    direction = observer.direction_from_source
    basis_u, basis_v = observer_image_basis(observer)
    projected_u = mesh.vertices_cm @ basis_u
    projected_v = mesh.vertices_cm @ basis_v
    depth = mesh.vertices_cm @ direction
    if not (
        np.all(np.isfinite(projected_u))
        and np.all(np.isfinite(projected_v))
        and np.all(np.isfinite(depth))
    ):
        raise ArithmeticError("observer projection produced a non-finite coordinate")

    u_min = float(np.min(projected_u))
    u_max = float(np.max(projected_u))
    v_min = float(np.min(projected_v))
    v_max = float(np.max(projected_v))
    width = u_max - u_min
    height = v_max - v_min
    long_extent = max(width, height)
    if not np.isfinite(long_extent) or long_extent <= 0.0:
        raise PhysicalDomainError("projected mesh has zero or invalid extent")
    pixel_size = long_extent / pixels_long_axis
    u_pixels = max(1, int(np.ceil(width / pixel_size)))
    v_pixels = max(1, int(np.ceil(height / pixel_size)))
    u_centers = u_min + (np.arange(u_pixels, dtype=np.float64) + 0.5) * pixel_size
    v_centers = v_min + (np.arange(v_pixels, dtype=np.float64) + 0.5) * pixel_size

    image_shape = (v_pixels, u_pixels)
    face_buffer = np.full(image_shape, -1, dtype=np.int64)
    barycentric_buffer = np.zeros(image_shape + (3,), dtype=np.float64)
    depth_buffer = np.zeros(image_shape, dtype=np.float64)
    hit_mask = np.zeros(image_shape, dtype=np.bool_)
    triangle_u = projected_u[mesh.faces]
    triangle_v = projected_v[mesh.faces]
    triangle_depth = depth[mesh.faces]
    roundoff_tolerance = 64.0 * np.finfo(np.float64).eps

    for face_index in range(mesh.faces.shape[0]):
        face_u = triangle_u[face_index]
        face_v = triangle_v[face_index]
        lower_u = max(0, int(np.ceil((float(np.min(face_u)) - u_min) / pixel_size - 0.5)))
        upper_u = min(
            u_pixels - 1,
            int(np.floor((float(np.max(face_u)) - u_min) / pixel_size - 0.5)),
        )
        lower_v = max(0, int(np.ceil((float(np.min(face_v)) - v_min) / pixel_size - 0.5)))
        upper_v = min(
            v_pixels - 1,
            int(np.floor((float(np.max(face_v)) - v_min) / pixel_size - 0.5)),
        )
        if lower_u > upper_u or lower_v > upper_v:
            continue

        denominator = (face_v[1] - face_v[2]) * (face_u[0] - face_u[2]) + (
            face_u[2] - face_u[1]
        ) * (face_v[0] - face_v[2])
        if not np.isfinite(denominator):
            raise ArithmeticError(
                f"surface triangle {face_index} has non-finite projected area"
            )
        if denominator == 0.0:
            continue
        local_u = u_centers[lower_u : upper_u + 1][None, :]
        local_v = v_centers[lower_v : upper_v + 1][:, None]
        weight_0 = (
            (face_v[1] - face_v[2]) * (local_u - face_u[2])
            + (face_u[2] - face_u[1]) * (local_v - face_v[2])
        ) / denominator
        weight_1 = (
            (face_v[2] - face_v[0]) * (local_u - face_u[2])
            + (face_u[0] - face_u[2]) * (local_v - face_v[2])
        ) / denominator
        weight_2 = 1.0 - weight_0 - weight_1
        inside = (
            (weight_0 >= -roundoff_tolerance)
            & (weight_1 >= -roundoff_tolerance)
            & (weight_2 >= -roundoff_tolerance)
        )
        if not np.any(inside):
            continue

        local_depth = (
            weight_0 * triangle_depth[face_index, 0]
            + weight_1 * triangle_depth[face_index, 1]
            + weight_2 * triangle_depth[face_index, 2]
        )
        row_slice = slice(lower_v, upper_v + 1)
        column_slice = slice(lower_u, upper_u + 1)
        current_hit = hit_mask[row_slice, column_slice]
        current_depth = depth_buffer[row_slice, column_slice]
        replace = inside & ((~current_hit) | (local_depth > current_depth))
        if not np.any(replace):
            continue
        current_hit[replace] = True
        current_depth[replace] = local_depth[replace]
        local_faces = face_buffer[row_slice, column_slice]
        local_faces[replace] = face_index
        local_barycentric = barycentric_buffer[row_slice, column_slice]
        local_barycentric[..., 0][replace] = weight_0[replace]
        local_barycentric[..., 1][replace] = weight_1[replace]
        local_barycentric[..., 2][replace] = weight_2[replace]

    emitting_mask = np.zeros(image_shape, dtype=np.bool_)
    if np.any(hit_mask):
        face_cosines = mesh.face_unit_normals @ direction
        emitting_mask[hit_mask] = face_cosines[face_buffer[hit_mask]] > 0.0

    pixel_area = float(pixel_size**2)
    visible_face_indices = face_buffer[emitting_mask]
    visible_barycentric = barycentric_buffer[emitting_mask]
    visible_vertices = mesh.faces[visible_face_indices]
    vertex_projected_area_weights = np.bincount(
        visible_vertices.reshape(-1),
        weights=visible_barycentric.reshape(-1),
        minlength=mesh.vertices_cm.shape[0],
    ).astype(np.float64, copy=False)
    vertex_projected_area_weights *= pixel_area
    if not np.all(np.isfinite(vertex_projected_area_weights)):
        raise ArithmeticError("ray integration weights became non-finite")
    return RayImage(
        u_centers_cm=_readonly(u_centers),
        v_centers_cm=_readonly(v_centers),
        pixel_area_cm2=pixel_area,
        frontmost_face_index=_readonly(face_buffer),
        frontmost_barycentric=_readonly(barycentric_buffer),
        frontmost_depth_cm=_readonly(depth_buffer),
        hit_mask=_readonly(hit_mask),
        emitting_mask=_readonly(emitting_mask),
        observer_direction=_readonly(np.array(direction, copy=True)),
        mesh_face_count=int(mesh.faces.shape[0]),
        mesh_fingerprint=_mesh_fingerprint(mesh),
        vertex_projected_area_weights_cm2=_readonly(
            vertex_projected_area_weights
        ),
    )


def raytraced_blackbody_sed(
    source: ZOSourceGrid,
    mesh: SurfaceMesh,
    observer: Observer,
    image: RayImage,
    frequency_hz: ArrayLike,
) -> ObservedSED:
    """Integrate LTE intensity over the visible frontmost image pixels."""
    if mesh.vertex_grid_shape != source.shape:
        raise PhysicalDomainError("mesh vertex grid does not match the source grid")
    if image.mesh_face_count != mesh.faces.shape[0]:
        raise PhysicalDomainError("ray image was not rendered from this mesh topology")
    if image.mesh_fingerprint != _mesh_fingerprint(mesh):
        raise PhysicalDomainError("ray image was not rendered from this mesh geometry")
    if not np.array_equal(image.observer_direction, observer.direction_from_source):
        raise PhysicalDomainError("ray image observer direction does not match observer")
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    if frequency.ndim != 1 or frequency.size == 0:
        raise PhysicalDomainError("frequency_hz must be a non-empty one-dimensional grid")
    if not np.all(np.isfinite(frequency)) or np.any(frequency <= 0.0):
        raise PhysicalDomainError("frequency_hz must contain finite, positive values")
    if np.any(np.diff(frequency) <= 0.0):
        raise PhysicalDomainError("frequency_hz must be strictly increasing")

    vertex_temperature = source.effective_temperature_k.reshape(-1)
    if image.vertex_projected_area_weights_cm2.shape != vertex_temperature.shape:
        raise PhysicalDomainError("ray image vertex weights do not match source grid")
    flux_density = np.empty_like(frequency)
    for index, nu in enumerate(frequency):
        vertex_intensity = planck_nu(nu, vertex_temperature)
        flux_density[index] = (
            np.sum(
                vertex_intensity * image.vertex_projected_area_weights_cm2,
                dtype=np.float64,
            )
            / observer.distance_cm**2
        )
    isotropic_equivalent = 4.0 * np.pi * observer.distance_cm**2 * flux_density
    for array in (frequency, flux_density, isotropic_equivalent):
        array.setflags(write=False)
    return ObservedSED(frequency, flux_density, isotropic_equivalent)
