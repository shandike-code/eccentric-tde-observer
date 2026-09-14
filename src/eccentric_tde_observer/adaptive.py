"""Source-triangle quadrature with exact pointwise front-surface queries.

The uniform image rasterizer samples intensity at pixel centres.  This module
instead places quadrature points inside every projected source triangle and
uses an image-plane spatial index only to decide which triangle is frontmost.
It therefore resolves emitting triangles that are much smaller than a global
image pixel while retaining the same Newtonian surface and occultation model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .geometry import SurfaceMesh
from .observer import ObservedSED, Observer
from .radiation import planck_nu
from .raytrace import _mesh_fingerprint, observer_image_basis
from .source import PhysicalDomainError, ZOSourceGrid


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class OrthographicTriangleIndex:
    """Uniform-bin acceleration structure for projected triangle queries."""

    triangle_u_cm: NDArray[np.float64]
    triangle_v_cm: NDArray[np.float64]
    triangle_depth_cm: NDArray[np.float64]
    denominator_cm2: NDArray[np.float64]
    u_min_cm: float
    v_min_cm: float
    bin_size_cm: float
    u_bin_count: int
    v_bin_count: int
    bin_offsets: NDArray[np.int64]
    bin_face_indices: NDArray[np.int64]
    observer_direction: NDArray[np.float64]
    mesh_face_count: int
    mesh_fingerprint: str
    spatial_bins_long_axis: int


@dataclass(frozen=True)
class SourceSurfaceRayQuadrature:
    """Projected vertex weights after pointwise frontmost-surface selection."""

    subdivision_level: int
    samples_per_front_face: int
    front_facing_face_count: int
    ray_count: int
    emitting_ray_count: int
    visible_projected_area_cm2: float
    unobscured_projected_area_cm2: float
    vertex_projected_area_weights_cm2: NDArray[np.float64]
    observer_direction: NDArray[np.float64]
    mesh_face_count: int
    mesh_fingerprint: str
    spatial_bins_long_axis: int


def _subdivide_barycentric_triangles(
    triangles: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Split barycentric triangles into four equal-area children."""
    first = triangles[:, 0]
    second = triangles[:, 1]
    third = triangles[:, 2]
    midpoint_01 = 0.5 * (first + second)
    midpoint_12 = 0.5 * (second + third)
    midpoint_20 = 0.5 * (third + first)
    return np.stack(
        (
            np.stack((first, midpoint_01, midpoint_20), axis=1),
            np.stack((midpoint_01, second, midpoint_12), axis=1),
            np.stack((midpoint_20, midpoint_12, third), axis=1),
            np.stack((midpoint_01, midpoint_12, midpoint_20), axis=1),
        ),
        axis=1,
    )


def build_orthographic_triangle_index(
    mesh: SurfaceMesh,
    observer: Observer,
    *,
    bins_long_axis: int = 256,
) -> OrthographicTriangleIndex:
    """Index projected triangle bounding boxes in uniform square bins."""
    if not isinstance(bins_long_axis, (int, np.integer)) or isinstance(
        bins_long_axis, (bool, np.bool_)
    ):
        raise PhysicalDomainError("bins_long_axis must be an integer")
    bins_long_axis = int(bins_long_axis)
    if bins_long_axis < 8:
        raise PhysicalDomainError("bins_long_axis must be at least 8")

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

    triangle_u = projected_u[mesh.faces]
    triangle_v = projected_v[mesh.faces]
    triangle_depth = depth[mesh.faces]
    denominator = (
        (triangle_v[:, 1] - triangle_v[:, 2])
        * (triangle_u[:, 0] - triangle_u[:, 2])
        + (triangle_u[:, 2] - triangle_u[:, 1])
        * (triangle_v[:, 0] - triangle_v[:, 2])
    )
    if not np.all(np.isfinite(denominator)):
        index = int(np.argwhere(~np.isfinite(denominator))[0, 0])
        raise ArithmeticError(
            f"surface triangle {index} has non-finite projected area"
        )

    u_min = float(np.min(projected_u))
    u_max = float(np.max(projected_u))
    v_min = float(np.min(projected_v))
    v_max = float(np.max(projected_v))
    width = u_max - u_min
    height = v_max - v_min
    long_extent = max(width, height)
    if not np.isfinite(long_extent) or long_extent <= 0.0:
        raise PhysicalDomainError("projected mesh has zero or invalid extent")
    bin_size = long_extent / bins_long_axis
    u_bins = max(1, int(np.ceil(width / bin_size)))
    v_bins = max(1, int(np.ceil(height / bin_size)))

    nondegenerate = denominator != 0.0
    valid_faces = np.flatnonzero(nondegenerate)
    triangle_u_min = np.min(triangle_u[valid_faces], axis=1)
    triangle_u_max = np.max(triangle_u[valid_faces], axis=1)
    triangle_v_min = np.min(triangle_v[valid_faces], axis=1)
    triangle_v_max = np.max(triangle_v[valid_faces], axis=1)
    lower_u = np.floor((triangle_u_min - u_min) / bin_size).astype(np.int64)
    upper_u = np.floor((triangle_u_max - u_min) / bin_size).astype(np.int64)
    lower_v = np.floor((triangle_v_min - v_min) / bin_size).astype(np.int64)
    upper_v = np.floor((triangle_v_max - v_min) / bin_size).astype(np.int64)
    lower_u[lower_u < 0] = 0
    lower_v[lower_v < 0] = 0
    upper_u[upper_u >= u_bins] = u_bins - 1
    upper_v[upper_v >= v_bins] = v_bins - 1

    bin_lists: list[list[int]] = [[] for _ in range(u_bins * v_bins)]
    for local_index, face_index in enumerate(valid_faces):
        for v_bin in range(int(lower_v[local_index]), int(upper_v[local_index]) + 1):
            row_offset = v_bin * u_bins
            for u_bin in range(
                int(lower_u[local_index]), int(upper_u[local_index]) + 1
            ):
                bin_lists[row_offset + u_bin].append(int(face_index))
    counts = np.fromiter(
        (len(face_list) for face_list in bin_lists),
        dtype=np.int64,
        count=len(bin_lists),
    )
    offsets = np.empty(counts.size + 1, dtype=np.int64)
    offsets[0] = 0
    np.cumsum(counts, out=offsets[1:])
    flat_faces = np.empty(int(offsets[-1]), dtype=np.int64)
    for bin_index, face_list in enumerate(bin_lists):
        flat_faces[offsets[bin_index] : offsets[bin_index + 1]] = face_list

    return OrthographicTriangleIndex(
        triangle_u_cm=_readonly(triangle_u),
        triangle_v_cm=_readonly(triangle_v),
        triangle_depth_cm=_readonly(triangle_depth),
        denominator_cm2=_readonly(denominator),
        u_min_cm=u_min,
        v_min_cm=v_min,
        bin_size_cm=float(bin_size),
        u_bin_count=u_bins,
        v_bin_count=v_bins,
        bin_offsets=_readonly(offsets),
        bin_face_indices=_readonly(flat_faces),
        observer_direction=_readonly(np.array(direction, copy=True)),
        mesh_face_count=int(mesh.faces.shape[0]),
        mesh_fingerprint=_mesh_fingerprint(mesh),
        spatial_bins_long_axis=bins_long_axis,
    )


def trace_orthographic_points(
    index: OrthographicTriangleIndex,
    u_cm: ArrayLike,
    v_cm: ArrayLike,
    *,
    maximum_pair_count: int = 2_000_000,
) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
    """Return the frontmost face and depth at arbitrary image-plane points."""
    u = np.array(u_cm, dtype=np.float64, copy=True)
    v = np.array(v_cm, dtype=np.float64, copy=True)
    if u.ndim != 1 or v.ndim != 1 or u.shape != v.shape:
        raise PhysicalDomainError("u_cm and v_cm must be one-dimensional equal grids")
    if not np.all(np.isfinite(u)) or not np.all(np.isfinite(v)):
        raise PhysicalDomainError("image-plane query points must be finite")
    if not isinstance(maximum_pair_count, (int, np.integer)) or isinstance(
        maximum_pair_count, (bool, np.bool_)
    ):
        raise PhysicalDomainError("maximum_pair_count must be an integer")
    maximum_pair_count = int(maximum_pair_count)
    if maximum_pair_count < 1:
        raise PhysicalDomainError("maximum_pair_count must be positive")

    face_result = np.full(u.size, -1, dtype=np.int64)
    depth_result = np.zeros(u.size, dtype=np.float64)
    u_bin = np.floor((u - index.u_min_cm) / index.bin_size_cm).astype(np.int64)
    v_bin = np.floor((v - index.v_min_cm) / index.bin_size_cm).astype(np.int64)
    inside_index = (
        (u_bin >= 0)
        & (u_bin < index.u_bin_count)
        & (v_bin >= 0)
        & (v_bin < index.v_bin_count)
    )
    query_indices = np.flatnonzero(inside_index)
    if query_indices.size == 0:
        return _readonly(face_result), _readonly(depth_result)
    bin_index = v_bin[query_indices] * index.u_bin_count + u_bin[query_indices]
    order = np.argsort(bin_index, kind="stable")
    sorted_queries = query_indices[order]
    sorted_bins = bin_index[order]
    boundaries = np.concatenate(
        (
            np.array([0], dtype=np.int64),
            np.flatnonzero(np.diff(sorted_bins)) + 1,
            np.array([sorted_bins.size], dtype=np.int64),
        )
    )
    roundoff_tolerance = 64.0 * np.finfo(np.float64).eps

    for group_index in range(boundaries.size - 1):
        start = int(boundaries[group_index])
        stop = int(boundaries[group_index + 1])
        current_bin = int(sorted_bins[start])
        face_start = int(index.bin_offsets[current_bin])
        face_stop = int(index.bin_offsets[current_bin + 1])
        candidates = index.bin_face_indices[face_start:face_stop]
        if candidates.size == 0:
            continue
        chunk_size = max(1, maximum_pair_count // candidates.size)
        for chunk_start in range(start, stop, chunk_size):
            chunk_stop = min(stop, chunk_start + chunk_size)
            queries = sorted_queries[chunk_start:chunk_stop]
            local_u = u[queries, None]
            local_v = v[queries, None]
            face_u = index.triangle_u_cm[candidates]
            face_v = index.triangle_v_cm[candidates]
            denominator = index.denominator_cm2[candidates]
            weight_0 = (
                (face_v[None, :, 1] - face_v[None, :, 2])
                * (local_u - face_u[None, :, 2])
                + (face_u[None, :, 2] - face_u[None, :, 1])
                * (local_v - face_v[None, :, 2])
            ) / denominator[None, :]
            weight_1 = (
                (face_v[None, :, 2] - face_v[None, :, 0])
                * (local_u - face_u[None, :, 2])
                + (face_u[None, :, 0] - face_u[None, :, 2])
                * (local_v - face_v[None, :, 2])
            ) / denominator[None, :]
            weight_2 = 1.0 - weight_0 - weight_1
            contains = (
                (weight_0 >= -roundoff_tolerance)
                & (weight_1 >= -roundoff_tolerance)
                & (weight_2 >= -roundoff_tolerance)
            )
            any_hit = np.any(contains, axis=1)
            if not np.any(any_hit):
                continue
            local_depth = (
                weight_0 * index.triangle_depth_cm[candidates, 0][None, :]
                + weight_1 * index.triangle_depth_cm[candidates, 1][None, :]
                + weight_2 * index.triangle_depth_cm[candidates, 2][None, :]
            )
            masked_depth = np.where(contains, local_depth, -np.inf)
            winning_local = np.argmax(masked_depth, axis=1)
            hit_queries = queries[any_hit]
            hit_winners = winning_local[any_hit]
            face_result[hit_queries] = candidates[hit_winners]
            depth_result[hit_queries] = masked_depth[any_hit, hit_winners]

    return _readonly(face_result), _readonly(depth_result)


def recursive_triangle_centroids(
    subdivision_level: int,
) -> NDArray[np.float64]:
    """Return equal-area barycentric centroids after recursive 1-to-4 splits."""
    if not isinstance(subdivision_level, (int, np.integer)) or isinstance(
        subdivision_level, (bool, np.bool_)
    ):
        raise PhysicalDomainError("subdivision_level must be an integer")
    subdivision_level = int(subdivision_level)
    if subdivision_level < 0 or subdivision_level > 6:
        raise PhysicalDomainError("subdivision_level must satisfy 0 <= level <= 6")
    triangles = np.eye(3, dtype=np.float64)[None, :, :]
    for _ in range(subdivision_level):
        triangles = _subdivide_barycentric_triangles(triangles).reshape(-1, 3, 3)
    centroids = np.mean(triangles, axis=1)
    if not np.allclose(np.sum(centroids, axis=1), 1.0, atol=2.0e-16):
        raise ArithmeticError("recursive barycentric quadrature construction failed")
    return _readonly(centroids)


def render_source_surface_quadrature(
    mesh: SurfaceMesh,
    observer: Observer,
    *,
    subdivision_level: int = 0,
    bins_long_axis: int = 256,
    triangle_index: OrthographicTriangleIndex | None = None,
) -> SourceSurfaceRayQuadrature:
    """Integrate projected source faces using pointwise occultation queries."""
    barycentric_nodes = recursive_triangle_centroids(subdivision_level)
    if triangle_index is None:
        triangle_index = build_orthographic_triangle_index(
            mesh, observer, bins_long_axis=bins_long_axis
        )
    else:
        if triangle_index.mesh_face_count != mesh.faces.shape[0]:
            raise PhysicalDomainError("triangle index topology does not match mesh")
        if triangle_index.mesh_fingerprint != _mesh_fingerprint(mesh):
            raise PhysicalDomainError("triangle index geometry does not match mesh")
        if not np.array_equal(
            triangle_index.observer_direction, observer.direction_from_source
        ):
            raise PhysicalDomainError("triangle index observer does not match observer")
        bins_long_axis = triangle_index.spatial_bins_long_axis

    direction = observer.direction_from_source
    face_cosines = mesh.face_unit_normals @ direction
    front_faces = np.flatnonzero(face_cosines > 0.0)
    if front_faces.size == 0:
        raise PhysicalDomainError("surface has no front-facing triangles")
    projected_face_area = face_cosines[front_faces] * mesh.face_areas_cm2[front_faces]
    unobscured_area = float(np.sum(projected_face_area, dtype=np.float64))
    triangle_u = triangle_index.triangle_u_cm[front_faces]
    triangle_v = triangle_index.triangle_v_cm[front_faces]
    vertex_weights = np.zeros(mesh.vertices_cm.shape[0], dtype=np.float64)
    visible_area = 0.0
    emitting_count = 0
    node_area_factor = 1.0 / barycentric_nodes.shape[0]

    for barycentric in barycentric_nodes:
        query_u = triangle_u @ barycentric
        query_v = triangle_v @ barycentric
        frontmost_face, _ = trace_orthographic_points(
            triangle_index, query_u, query_v
        )
        visible = frontmost_face == front_faces
        if not np.any(visible):
            continue
        visible_faces = front_faces[visible]
        area_weights = projected_face_area[visible] * node_area_factor
        visible_area += float(np.sum(area_weights, dtype=np.float64))
        emitting_count += int(np.count_nonzero(visible))
        vertices = mesh.faces[visible_faces]
        for vertex_index in range(3):
            vertex_weights += np.bincount(
                vertices[:, vertex_index],
                weights=area_weights * barycentric[vertex_index],
                minlength=mesh.vertices_cm.shape[0],
            )

    if not np.all(np.isfinite(vertex_weights)):
        raise ArithmeticError("surface quadrature weights became non-finite")
    weight_area = float(np.sum(vertex_weights, dtype=np.float64))
    if not np.isclose(weight_area, visible_area, rtol=2.0e-13, atol=0.0):
        raise ArithmeticError("surface quadrature area and vertex weights disagree")
    return SourceSurfaceRayQuadrature(
        subdivision_level=int(subdivision_level),
        samples_per_front_face=int(barycentric_nodes.shape[0]),
        front_facing_face_count=int(front_faces.size),
        ray_count=int(front_faces.size * barycentric_nodes.shape[0]),
        emitting_ray_count=emitting_count,
        visible_projected_area_cm2=visible_area,
        unobscured_projected_area_cm2=unobscured_area,
        vertex_projected_area_weights_cm2=_readonly(vertex_weights),
        observer_direction=_readonly(np.array(direction, copy=True)),
        mesh_face_count=int(mesh.faces.shape[0]),
        mesh_fingerprint=_mesh_fingerprint(mesh),
        spatial_bins_long_axis=int(bins_long_axis),
    )


def render_adaptive_source_surface_quadrature(
    mesh: SurfaceMesh,
    observer: Observer,
    *,
    maximum_subdivision_depth: int,
    bins_long_axis: int = 256,
    triangle_index: OrthographicTriangleIndex | None = None,
    interior_vertex_fraction: float = 1.0e-4,
) -> SourceSurfaceRayQuadrature:
    """Refine only source subtriangles crossed by an occultation boundary.

    Each active cell is tested at the four child centroids and at three points
    just inside its vertices.  A cell terminates if every probe sees the target
    face, or if every internal probe is hidden.  Otherwise it is split into
    four equal-area children.  At the requested maximum depth,
    the four child-centroid samples define the reported quadrature.  Comparing
    successive depths is the required numerical error audit; the depth is not
    inferred from a hard-coded physical answer.
    """
    if not isinstance(maximum_subdivision_depth, (int, np.integer)) or isinstance(
        maximum_subdivision_depth, (bool, np.bool_)
    ):
        raise PhysicalDomainError("maximum_subdivision_depth must be an integer")
    maximum_subdivision_depth = int(maximum_subdivision_depth)
    if maximum_subdivision_depth < 1 or maximum_subdivision_depth > 14:
        raise PhysicalDomainError(
            "maximum_subdivision_depth must satisfy 1 <= depth <= 14"
        )
    interior_vertex_fraction = float(interior_vertex_fraction)
    if (
        not np.isfinite(interior_vertex_fraction)
        or interior_vertex_fraction <= 0.0
        or interior_vertex_fraction >= 1.0 / 3.0
    ):
        raise PhysicalDomainError(
            "interior_vertex_fraction must be finite and lie in (0, 1/3)"
        )
    if triangle_index is None:
        triangle_index = build_orthographic_triangle_index(
            mesh, observer, bins_long_axis=bins_long_axis
        )
    else:
        if triangle_index.mesh_face_count != mesh.faces.shape[0]:
            raise PhysicalDomainError("triangle index topology does not match mesh")
        if triangle_index.mesh_fingerprint != _mesh_fingerprint(mesh):
            raise PhysicalDomainError("triangle index geometry does not match mesh")
        if not np.array_equal(
            triangle_index.observer_direction, observer.direction_from_source
        ):
            raise PhysicalDomainError("triangle index observer does not match observer")
        bins_long_axis = triangle_index.spatial_bins_long_axis

    direction = observer.direction_from_source
    face_cosines = mesh.face_unit_normals @ direction
    front_faces = np.flatnonzero(face_cosines > 0.0)
    if front_faces.size == 0:
        raise PhysicalDomainError("surface has no front-facing triangles")
    projected_face_area = face_cosines[front_faces] * mesh.face_areas_cm2[front_faces]
    unobscured_area = float(np.sum(projected_face_area, dtype=np.float64))
    triangle_u = triangle_index.triangle_u_cm
    triangle_v = triangle_index.triangle_v_cm
    vertex_weights = np.zeros(mesh.vertices_cm.shape[0], dtype=np.float64)
    visible_area = 0.0
    emitting_terminal_count = 0
    query_count = 0

    active_faces = np.array(front_faces, copy=True)
    active_triangles = np.broadcast_to(
        np.eye(3, dtype=np.float64), (front_faces.size, 3, 3)
    ).copy()
    active_area_fraction = np.ones(front_faces.size, dtype=np.float64)
    epsilon = interior_vertex_fraction

    def add_visible_cells(
        face_indices: NDArray[np.int64],
        barycentric: NDArray[np.float64],
        area_fraction: NDArray[np.float64],
    ) -> None:
        nonlocal visible_area, emitting_terminal_count
        if face_indices.size == 0:
            return
        original_positions = np.searchsorted(front_faces, face_indices)
        area_weights = projected_face_area[original_positions] * area_fraction
        visible_area += float(np.sum(area_weights, dtype=np.float64))
        emitting_terminal_count += int(face_indices.size)
        vertices = mesh.faces[face_indices]
        for vertex_index in range(3):
            vertex_weights[:] += np.bincount(
                vertices[:, vertex_index],
                weights=area_weights * barycentric[:, vertex_index],
                minlength=mesh.vertices_cm.shape[0],
            )

    for depth in range(maximum_subdivision_depth):
        if active_faces.size == 0:
            break
        children = _subdivide_barycentric_triangles(active_triangles)
        child_centroids = np.mean(children, axis=2)
        cell_centroids = np.mean(active_triangles, axis=1)
        near_vertices = (
            (1.0 - 3.0 * epsilon) * active_triangles
            + 3.0 * epsilon * cell_centroids[:, None, :]
        )
        probes = np.concatenate((child_centroids, near_vertices), axis=1)
        flat_probes = probes.reshape(-1, 3)
        repeated_faces = np.repeat(active_faces, probes.shape[1])
        query_u = np.einsum(
            "ni,ni->n", triangle_u[repeated_faces], flat_probes
        )
        query_v = np.einsum(
            "ni,ni->n", triangle_v[repeated_faces], flat_probes
        )
        frontmost, _ = trace_orthographic_points(
            triangle_index, query_u, query_v
        )
        query_count += int(frontmost.size)
        if np.any(frontmost < 0):
            index = int(np.argwhere(frontmost < 0)[0, 0])
            raise ArithmeticError(
                "a source-cell interior probe missed its own projected triangle "
                f"at flattened probe {index}"
            )
        frontmost = frontmost.reshape(active_faces.size, probes.shape[1])
        visible_probe = frontmost == active_faces[:, None]
        all_visible = np.all(visible_probe, axis=1)
        all_hidden = ~np.any(visible_probe, axis=1)

        visible_indices = np.flatnonzero(all_visible)
        add_visible_cells(
            active_faces[visible_indices],
            cell_centroids[visible_indices],
            active_area_fraction[visible_indices],
        )
        unresolved = ~(all_visible | all_hidden)
        unresolved_indices = np.flatnonzero(unresolved)
        if unresolved_indices.size == 0:
            active_faces = np.empty(0, dtype=np.int64)
            break
        unresolved_children = children[unresolved_indices]

        if depth + 1 == maximum_subdivision_depth:
            child_visible = visible_probe[unresolved_indices, :4]
            unresolved_faces = active_faces[unresolved_indices]
            unresolved_area = active_area_fraction[unresolved_indices]
            selected_parent, selected_child = np.nonzero(child_visible)
            add_visible_cells(
                unresolved_faces[selected_parent],
                child_centroids[unresolved_indices][selected_parent, selected_child],
                unresolved_area[selected_parent] * 0.25,
            )
            active_faces = np.empty(0, dtype=np.int64)
            break

        active_faces = np.repeat(active_faces[unresolved_indices], 4)
        active_triangles = unresolved_children.reshape(-1, 3, 3)
        active_area_fraction = np.repeat(
            active_area_fraction[unresolved_indices] * 0.25, 4
        )

    if not np.all(np.isfinite(vertex_weights)):
        raise ArithmeticError("adaptive surface quadrature weights became non-finite")
    weight_area = float(np.sum(vertex_weights, dtype=np.float64))
    if not np.isclose(weight_area, visible_area, rtol=3.0e-13, atol=0.0):
        raise ArithmeticError(
            "adaptive surface quadrature area and vertex weights disagree"
        )
    return SourceSurfaceRayQuadrature(
        subdivision_level=maximum_subdivision_depth,
        samples_per_front_face=4**maximum_subdivision_depth,
        front_facing_face_count=int(front_faces.size),
        ray_count=query_count,
        emitting_ray_count=emitting_terminal_count,
        visible_projected_area_cm2=visible_area,
        unobscured_projected_area_cm2=unobscured_area,
        vertex_projected_area_weights_cm2=_readonly(vertex_weights),
        observer_direction=_readonly(np.array(direction, copy=True)),
        mesh_face_count=int(mesh.faces.shape[0]),
        mesh_fingerprint=_mesh_fingerprint(mesh),
        spatial_bins_long_axis=int(bins_long_axis),
    )


def source_surface_blackbody_sed(
    source: ZOSourceGrid,
    mesh: SurfaceMesh,
    observer: Observer,
    quadrature: SourceSurfaceRayQuadrature,
    frequency_hz: ArrayLike,
    *,
    frequency_shift_factor: ArrayLike | None = None,
    spectral_hardening_factor: ArrayLike | None = None,
) -> ObservedSED:
    """Integrate LTE intensity with source-triangle visibility weights.

    When ``frequency_shift_factor`` is supplied, it is the pointwise
    ``g = nu_observed / nu_emitted``.  Invariance of ``I_nu / nu**3`` and the
    Planck scaling identity give

    ``g**3 B_nu(nu_observed / g, T) = B_nu(nu_observed, g T)``.

    ``spectral_hardening_factor=f`` applies the local energy-conserving diluted
    blackbody ``f**-4 B_nu(f T_eff)``.  The caller remains responsible for
    constructing physically admissible ``g`` and ``f`` fields; this routine
    never clips or repairs either one.
    """
    if mesh.vertex_grid_shape != source.shape:
        raise PhysicalDomainError("mesh vertex grid does not match the source grid")
    if quadrature.mesh_face_count != mesh.faces.shape[0]:
        raise PhysicalDomainError("surface quadrature topology does not match mesh")
    if quadrature.mesh_fingerprint != _mesh_fingerprint(mesh):
        raise PhysicalDomainError("surface quadrature geometry does not match mesh")
    if not np.array_equal(
        quadrature.observer_direction, observer.direction_from_source
    ):
        raise PhysicalDomainError("surface quadrature observer does not match observer")
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    if frequency.ndim != 1 or frequency.size == 0:
        raise PhysicalDomainError("frequency_hz must be a non-empty one-dimensional grid")
    if not np.all(np.isfinite(frequency)) or np.any(frequency <= 0.0):
        raise PhysicalDomainError("frequency_hz must contain finite, positive values")
    if np.any(np.diff(frequency) <= 0.0):
        raise PhysicalDomainError("frequency_hz must be strictly increasing")

    temperature = source.effective_temperature_k.reshape(-1)
    if spectral_hardening_factor is None:
        hardening = np.ones(source.shape, dtype=np.float64)
    else:
        hardening = np.array(
            spectral_hardening_factor, dtype=np.float64, copy=True
        )
        if hardening.shape != source.shape:
            raise PhysicalDomainError(
                "spectral_hardening_factor must match the source grid; "
                f"expected {source.shape}, got {hardening.shape}"
            )
        invalid_hardening = (~np.isfinite(hardening)) | (hardening < 1.0)
        if np.any(invalid_hardening):
            index = tuple(int(i) for i in np.argwhere(invalid_hardening)[0])
            raise PhysicalDomainError(
                "spectral_hardening_factor must be finite and at least one; "
                f"got {hardening[index]!r} at index {index}"
            )

    if frequency_shift_factor is None:
        shift = np.ones(source.shape, dtype=np.float64)
    else:
        shift = np.array(frequency_shift_factor, dtype=np.float64, copy=True)
        if shift.shape != source.shape:
            raise PhysicalDomainError(
                "frequency_shift_factor must match the source grid; "
                f"expected {source.shape}, got {shift.shape}"
            )
        invalid_shift = (~np.isfinite(shift)) | (shift <= 0.0)
        if np.any(invalid_shift):
            index = tuple(int(i) for i in np.argwhere(invalid_shift)[0])
            raise PhysicalDomainError(
                "frequency_shift_factor must be finite and strictly positive; "
                f"got {shift[index]!r} at index {index}"
            )
    # 中文：g 负责源到观察者频移，f 负责局域谱硬化；两者都不回写 ZO 的 T_eff。
    observed_temperature = (
        temperature * shift.reshape(-1) * hardening.reshape(-1)
    )
    dilution = hardening.reshape(-1) ** (-4.0)
    if not np.all(np.isfinite(observed_temperature)):
        raise ArithmeticError("transferred color temperature became non-finite")
    if quadrature.vertex_projected_area_weights_cm2.shape != temperature.shape:
        raise PhysicalDomainError("surface quadrature weights do not match source grid")
    flux_density = np.empty_like(frequency)
    for frequency_index, nu in enumerate(frequency):
        intensity = dilution * planck_nu(nu, observed_temperature)
        flux_density[frequency_index] = (
            np.sum(
                intensity * quadrature.vertex_projected_area_weights_cm2,
                dtype=np.float64,
            )
            / observer.distance_cm**2
        )
    isotropic_equivalent = 4.0 * np.pi * observer.distance_cm**2 * flux_density
    for array in (frequency, flux_density, isotropic_equivalent):
        array.setflags(write=False)
    return ObservedSED(frequency, flux_density, isotropic_equivalent)
