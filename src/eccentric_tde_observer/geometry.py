"""Reusable triangular geometry for an eccentric orbital surface."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .source import PhysicalDomainError, ZOSourceGrid


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class SurfaceMesh:
    """Triangular surface with reusable vertices, topology and face geometry."""

    vertices_cm: NDArray[np.float64]
    faces: NDArray[np.int64]
    face_centroids_cm: NDArray[np.float64]
    face_unit_normals: NDArray[np.float64]
    face_areas_cm2: NDArray[np.float64]
    vertex_grid_shape: tuple[int, int]

    @property
    def total_area_cm2(self) -> float:
        return float(np.sum(self.face_areas_cm2, dtype=np.float64))


def area_weighted_vertex_unit_normals(
    mesh: SurfaceMesh,
) -> NDArray[np.float64]:
    """Return area-weighted unit normals at mesh vertices.

    The interpolation is geometric only; it does not smooth or alter the
    photosphere.  A zero vector is rejected because it would leave the local
    emission angle undefined.
    """
    area_vectors = mesh.face_unit_normals * mesh.face_areas_cm2[:, None]
    accumulated = np.zeros_like(mesh.vertices_cm)
    for corner in range(3):
        np.add.at(accumulated, mesh.faces[:, corner], area_vectors)
    magnitudes = np.linalg.norm(accumulated, axis=1)
    invalid = (~np.isfinite(magnitudes)) | (magnitudes <= 0.0)
    if np.any(invalid):
        index = int(np.argwhere(invalid)[0, 0])
        raise PhysicalDomainError(
            f"vertex {index} has no finite, nonzero area-weighted normal"
        )
    normals = accumulated / magnitudes[:, None]
    return _readonly(normals)


def build_surface_mesh_from_vertices_faces(
    vertices_cm: ArrayLike,
    faces: ArrayLike,
    *,
    vertex_grid_shape: tuple[int, int] | None = None,
    require_positive_z_orientation: bool = False,
) -> SurfaceMesh:
    """Build and validate reusable face geometry from explicit topology.

    This constructor is also used by analytic ray-tracing fixtures that are
    not orbital grids.  Requiring positive z orientation remains optional for
    those fixtures, while orbital surfaces enforce it below.
    """
    vertices = np.array(vertices_cm, dtype=np.float64, copy=True)
    topology = np.array(faces, dtype=np.int64, copy=True)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or vertices.shape[0] < 3:
        raise PhysicalDomainError("vertices_cm must have shape (N>=3, 3)")
    if not np.all(np.isfinite(vertices)):
        index = tuple(int(i) for i in np.argwhere(~np.isfinite(vertices))[0])
        raise PhysicalDomainError(
            f"vertices_cm contains a non-finite value at index {index}"
        )
    if topology.ndim != 2 or topology.shape[1] != 3 or topology.shape[0] == 0:
        raise PhysicalDomainError("faces must have shape (M>=1, 3)")
    if np.any(topology < 0) or np.any(topology >= vertices.shape[0]):
        raise PhysicalDomainError("faces contain an out-of-range vertex index")
    if np.any(
        (topology[:, 0] == topology[:, 1])
        | (topology[:, 1] == topology[:, 2])
        | (topology[:, 2] == topology[:, 0])
    ):
        raise PhysicalDomainError("faces contain a repeated vertex index")

    if vertex_grid_shape is None:
        grid_shape = (vertices.shape[0], 1)
    else:
        grid_shape = tuple(int(value) for value in vertex_grid_shape)
        if (
            len(grid_shape) != 2
            or grid_shape[0] <= 0
            or grid_shape[1] <= 0
            or grid_shape[0] * grid_shape[1] != vertices.shape[0]
        ):
            raise PhysicalDomainError(
                "vertex_grid_shape must be two positive dimensions whose product "
                "equals the vertex count"
            )

    triangle_vertices = vertices[topology]
    first_edge = triangle_vertices[:, 1] - triangle_vertices[:, 0]
    second_edge = triangle_vertices[:, 2] - triangle_vertices[:, 0]
    area_vectors_twice = np.cross(first_edge, second_edge)
    magnitude_twice = np.linalg.norm(area_vectors_twice, axis=1)
    invalid_area = (~np.isfinite(magnitude_twice)) | (magnitude_twice <= 0.0)
    if np.any(invalid_area):
        index = int(np.argwhere(invalid_area)[0, 0])
        raise PhysicalDomainError(f"surface triangle {index} has invalid area")
    if require_positive_z_orientation:
        invalid_orientation = area_vectors_twice[:, 2] <= 0.0
        if np.any(invalid_orientation):
            index = int(np.argwhere(invalid_orientation)[0, 0])
            raise PhysicalDomainError(
                f"surface triangle {index} is inverted or the grid is under-resolved"
            )

    areas = 0.5 * magnitude_twice
    normals = area_vectors_twice / magnitude_twice[:, None]
    centroids = np.mean(triangle_vertices, axis=1)
    return SurfaceMesh(
        vertices_cm=_readonly(vertices),
        faces=_readonly(topology),
        face_centroids_cm=_readonly(centroids),
        face_unit_normals=_readonly(normals),
        face_areas_cm2=_readonly(areas),
        vertex_grid_shape=grid_shape,
    )


def orbital_vertices_cm(
    source: ZOSourceGrid, surface_height_cm: ArrayLike | None = None
) -> NDArray[np.float64]:
    """Map ``(a, E)`` nodes to Cartesian coordinates.

    The current source contract contains one global apsidal angle.  A nonzero
    radial twist is therefore rejected rather than reconstructed by integrating
    a gradient with an arbitrary boundary condition.
    """
    if source.apsidal_gradient_per_cm is not None and np.any(
        source.apsidal_gradient_per_cm != 0.0
    ):
        raise PhysicalDomainError(
            "a twisted surface needs varpi(a), not only apsidal_gradient_per_cm"
        )

    if surface_height_cm is None:
        height = np.zeros(source.shape, dtype=np.float64)
    else:
        height = np.array(surface_height_cm, dtype=np.float64, copy=True)
        if height.shape != source.shape:
            raise PhysicalDomainError(
                f"surface_height_cm must have shape {source.shape}; got {height.shape}"
            )
        if not np.all(np.isfinite(height)):
            index = tuple(int(i) for i in np.argwhere(~np.isfinite(height))[0])
            raise PhysicalDomainError(
                f"surface_height_cm contains a non-finite value at index {index}"
            )

    a = source.semimajor_axis_cm[:, None]
    anomaly = source.eccentric_anomaly_rad[None, :]
    eccentricity = source.eccentricity[:, None]
    x_periapsis = a * (np.cos(anomaly) - eccentricity)
    y_periapsis = a * np.sqrt(1.0 - eccentricity**2) * np.sin(anomaly)

    cosine = np.cos(source.apsidal_angle_rad)
    sine = np.sin(source.apsidal_angle_rad)
    x = cosine * x_periapsis - sine * y_periapsis
    y = sine * x_periapsis + cosine * y_periapsis
    vertices = np.stack((x, y, height), axis=-1).reshape(-1, 3)
    if not np.all(np.isfinite(vertices)):
        raise ArithmeticError("orbital coordinate mapping produced a non-finite vertex")
    return _readonly(vertices)


def structured_periodic_faces(radial_points: int, anomaly_points: int) -> NDArray[np.int64]:
    """Triangulate every periodic ``(a, E)`` quad with upward orientation."""
    if radial_points < 2 or anomaly_points < 3:
        raise PhysicalDomainError("surface topology needs at least 2x3 vertices")
    radial = np.arange(radial_points - 1, dtype=np.int64)[:, None]
    anomaly = np.arange(anomaly_points, dtype=np.int64)[None, :]
    following = (anomaly + 1) % anomaly_points

    inner_current = radial * anomaly_points + anomaly
    outer_current = (radial + 1) * anomaly_points + anomaly
    outer_following = (radial + 1) * anomaly_points + following
    inner_following = radial * anomaly_points + following
    first = np.stack(
        np.broadcast_arrays(inner_current, outer_current, outer_following), axis=-1
    ).reshape(-1, 3)
    second = np.stack(
        np.broadcast_arrays(inner_current, outer_following, inner_following), axis=-1
    ).reshape(-1, 3)
    faces = np.concatenate((first, second), axis=0)
    return _readonly(faces)


def build_orbital_surface_mesh(
    source: ZOSourceGrid, surface_height_cm: ArrayLike | None = None
) -> SurfaceMesh:
    """Build a periodic triangular surface; no visibility tracing is performed."""
    vertices = orbital_vertices_cm(source, surface_height_cm)
    faces = structured_periodic_faces(*source.shape)
    return build_surface_mesh_from_vertices_faces(
        vertices,
        faces,
        vertex_grid_shape=source.shape,
        require_positive_z_orientation=True,
    )
