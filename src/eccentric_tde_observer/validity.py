"""Audits for the local vertical-column domain of a bare eccentric disc."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .geometry import build_orbital_surface_mesh
from .photosphere import GrayPhotosphere
from .quadrature import (
    corrected_zo_area_weights,
    geometric_planar_area_cm2,
    geometric_planar_area_weights,
)
from .source import PhysicalDomainError, ZOSourceGrid


def _readonly(array: NDArray[np.float64]) -> NDArray[np.float64]:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class LocalVerticalDomainAudit:
    """Dimensionless source and photosphere geometry diagnostics.

    Fractions are node-quadrature area fractions.  Surface-slope quantities
    use the projected areas of the explicit triangular Cartesian surface.
    None of the thresholds is silently promoted to a physical theorem.
    """

    ratio_thresholds: NDArray[np.float64]
    corrected_h_over_radius_fraction_above: NDArray[np.float64]
    corrected_photosphere_over_radius_fraction_above: NDArray[np.float64]
    cartesian_h_over_radius_fraction_above: NDArray[np.float64]
    cartesian_photosphere_over_radius_fraction_above: NDArray[np.float64]
    h_over_radius_min_max: tuple[float, float]
    photosphere_over_radius_min_max: tuple[float, float]
    corrected_mean_h_over_radius: float
    corrected_mean_photosphere_over_radius: float
    minimum_total_vertical_optical_depth: float
    surface_area_to_projected_mesh_area: float
    projected_mesh_to_cartesian_quadrature_area: float
    projected_area_fraction_with_surface_slope_ge_1: float
    maximum_surface_slope: float
    minimum_face_normal_z: float
    oriented_single_valued_surface_graph: bool


def local_orbital_radius_cm(source: ZOSourceGrid) -> NDArray[np.float64]:
    """Return ``r=a*(1-e*cos(E))`` on a validated source grid."""
    radius = source.semimajor_axis_cm[:, None] * (
        1.0
        - source.eccentricity[:, None]
        * np.cos(source.eccentric_anomaly_rad)[None, :]
    )
    if not np.all(np.isfinite(radius)) or np.any(radius <= 0.0):
        raise PhysicalDomainError("local orbital radius must be finite and positive")
    return _readonly(radius)


def _weighted_fractions_above(
    ratio: NDArray[np.float64],
    weights: NDArray[np.float64],
    thresholds: NDArray[np.float64],
) -> NDArray[np.float64]:
    total = float(np.sum(weights, dtype=np.float64))
    if not np.isfinite(total) or total <= 0.0:
        raise ArithmeticError("area-weight sum must be finite and positive")
    fractions = np.array(
        [
            np.sum(weights[ratio >= threshold], dtype=np.float64) / total
            for threshold in thresholds
        ],
        dtype=np.float64,
    )
    if not np.all(np.isfinite(fractions)) or np.any(
        (fractions < 0.0) | (fractions > 1.0)
    ):
        raise ArithmeticError("weighted area fraction is invalid")
    return _readonly(fractions)


def audit_local_vertical_domain(
    source: ZOSourceGrid,
    photosphere: GrayPhotosphere,
    ratio_thresholds: ArrayLike = (0.1, 0.3, 1.0, 2.0),
) -> LocalVerticalDomainAudit:
    """Audit thin-column ratios and the explicit photosphere graph geometry."""
    if photosphere.height_cm.shape != source.shape:
        raise PhysicalDomainError(
            "photosphere height must have the same shape as the source"
        )
    thresholds = np.array(ratio_thresholds, dtype=np.float64, copy=True)
    if (
        thresholds.ndim != 1
        or thresholds.size == 0
        or not np.all(np.isfinite(thresholds))
        or np.any(thresholds <= 0.0)
        or np.any(np.diff(thresholds) <= 0.0)
    ):
        raise PhysicalDomainError(
            "ratio_thresholds must be finite, positive, and strictly increasing"
        )

    radius = local_orbital_radius_cm(source)
    h_over_radius = source.scale_height_cm / radius
    photosphere_over_radius = photosphere.height_cm / radius
    for name, ratio in (
        ("H/r", h_over_radius),
        ("z_ph/r", photosphere_over_radius),
    ):
        if not np.all(np.isfinite(ratio)) or np.any(ratio < 0.0):
            raise ArithmeticError(f"{name} contains an invalid value")

    corrected_weights = corrected_zo_area_weights(source)
    cartesian_weights = geometric_planar_area_weights(source)
    corrected_weight_sum = float(np.sum(corrected_weights, dtype=np.float64))
    mesh = build_orbital_surface_mesh(source, photosphere.height_cm)
    normal_z = mesh.face_unit_normals[:, 2]
    if not np.all(np.isfinite(normal_z)) or np.any(normal_z <= 0.0):
        raise ArithmeticError(
            "photosphere is not an upward-oriented single-valued mesh graph"
        )
    projected_face_area = mesh.face_areas_cm2 * normal_z
    projected_mesh_area = float(
        np.sum(projected_face_area, dtype=np.float64)
    )
    surface_area = float(np.sum(mesh.face_areas_cm2, dtype=np.float64))
    cartesian_quadrature_area = geometric_planar_area_cm2(source)
    surface_slope = np.sqrt(
        mesh.face_unit_normals[:, 0] ** 2
        + mesh.face_unit_normals[:, 1] ** 2
    ) / normal_z
    if not np.all(np.isfinite(surface_slope)) or np.any(surface_slope < 0.0):
        raise ArithmeticError("photosphere surface slope is invalid")
    steep_fraction = float(
        np.sum(projected_face_area[surface_slope >= 1.0], dtype=np.float64)
        / projected_mesh_area
    )

    return LocalVerticalDomainAudit(
        ratio_thresholds=_readonly(thresholds),
        corrected_h_over_radius_fraction_above=_weighted_fractions_above(
            h_over_radius, corrected_weights, thresholds
        ),
        corrected_photosphere_over_radius_fraction_above=_weighted_fractions_above(
            photosphere_over_radius, corrected_weights, thresholds
        ),
        cartesian_h_over_radius_fraction_above=_weighted_fractions_above(
            h_over_radius, cartesian_weights, thresholds
        ),
        cartesian_photosphere_over_radius_fraction_above=_weighted_fractions_above(
            photosphere_over_radius, cartesian_weights, thresholds
        ),
        h_over_radius_min_max=(
            float(np.min(h_over_radius)),
            float(np.max(h_over_radius)),
        ),
        photosphere_over_radius_min_max=(
            float(np.min(photosphere_over_radius)),
            float(np.max(photosphere_over_radius)),
        ),
        corrected_mean_h_over_radius=float(
            np.sum(h_over_radius * corrected_weights, dtype=np.float64)
            / corrected_weight_sum
        ),
        corrected_mean_photosphere_over_radius=float(
            np.sum(photosphere_over_radius * corrected_weights, dtype=np.float64)
            / corrected_weight_sum
        ),
        minimum_total_vertical_optical_depth=float(
            np.min(photosphere.total_vertical_optical_depth)
        ),
        surface_area_to_projected_mesh_area=surface_area / projected_mesh_area,
        projected_mesh_to_cartesian_quadrature_area=(
            projected_mesh_area / cartesian_quadrature_area
        ),
        projected_area_fraction_with_surface_slope_ge_1=steep_fraction,
        maximum_surface_slope=float(np.max(surface_slope)),
        minimum_face_normal_z=float(np.min(normal_z)),
        oriented_single_valued_surface_graph=True,
    )
