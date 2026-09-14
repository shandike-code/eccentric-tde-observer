"""Phase 7A 的准静态代表柱选择与局域谱比较工具。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .annulus_bridge import zo_annulus_atmosphere_coordinates
from .quadrature import corrected_zo_area_weights
from .radiation import STEFAN_BOLTZMANN_ERG_S_CM2_K4, planck_nu
from .source import PhysicalDomainError
from .zo_reference import ZOConstantEReferenceModel


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class RepresentativeAnnulusSelection:
    """严格准静态域内的一组实际 ``(a,E)`` 代表柱。"""

    radial_index: NDArray[np.int64]
    anomaly_index: NDArray[np.int64]
    semimajor_axis_cm: NDArray[np.float64]
    eccentric_anomaly_rad: NDArray[np.float64]
    effective_temperature_k: NDArray[np.float64]
    midplane_column_mass_g_cm2: NDArray[np.float64]
    gravity_coefficient_s2: NDArray[np.float64]
    quasi_static_ratio: NDArray[np.float64]
    cluster_area_fraction: NDArray[np.float64]
    cluster_bolometric_fraction: NDArray[np.float64]
    cluster_optical_fraction: NDArray[np.float64]
    cluster_mixture_fraction: NDArray[np.float64]
    cluster_covering_radius: NDArray[np.float64]
    quasi_static_threshold: float
    valid_cell_count: int
    excluded_cell_count: int
    valid_area_fraction: float
    valid_bolometric_fraction: float
    valid_optical_fraction: float
    weighted_rms_distance: float
    maximum_distance: float
    optical_band_hz: tuple[float, float]

    @property
    def count(self) -> int:
        return int(self.radial_index.size)


def _blackbody_band_flux(
    temperature_k: NDArray[np.float64],
    lower_frequency_hz: float,
    upper_frequency_hz: float,
    frequency_points: int,
) -> NDArray[np.float64]:
    """返回黑体单面频带通量，仅用于代表柱抽样的重要性权重。"""
    frequency = np.geomspace(lower_frequency_hz, upper_frequency_hz, frequency_points)
    intensity = planck_nu(frequency[None, :], temperature_k[:, None])
    flux = np.pi * np.trapezoid(intensity, frequency, axis=1)
    if not np.all(np.isfinite(flux)) or np.any(flux <= 0.0):
        raise ArithmeticError("blackbody band-flux weight became invalid")
    return flux


def _deterministic_weighted_medoids(
    coordinates: NDArray[np.float64],
    weights: NDArray[np.float64],
    count: int,
    maximum_iterations: int,
) -> tuple[NDArray[np.int64], NDArray[np.int64], NDArray[np.float64]]:
    """确定性加权聚类，并把每个中心限制为一个真实网格点。"""
    point_count = coordinates.shape[0]
    selected = [int(np.argmax(weights))]
    minimum_distance_squared = np.sum(
        (coordinates - coordinates[selected[0]]) ** 2, axis=1
    )
    while len(selected) < count:
        score = weights * minimum_distance_squared
        score[np.asarray(selected, dtype=np.int64)] = -1.0
        next_index = int(np.argmax(score))
        if score[next_index] < 0.0:
            raise RuntimeError("representative-column initialization exhausted points")
        selected.append(next_index)
        distance_squared = np.sum(
            (coordinates - coordinates[next_index]) ** 2, axis=1
        )
        minimum_distance_squared = np.minimum(
            minimum_distance_squared, distance_squared
        )

    centers = np.asarray(selected, dtype=np.int64)
    assignments = np.zeros(point_count, dtype=np.int64)
    for _ in range(maximum_iterations):
        distance_squared = np.sum(
            (coordinates[:, None, :] - coordinates[centers][None, :, :]) ** 2,
            axis=2,
        )
        assignments = np.argmin(distance_squared, axis=1)
        updated = centers.copy()
        occupied: set[int] = set()
        for cluster in range(count):
            members = np.flatnonzero(assignments == cluster)
            if members.size == 0:
                raise RuntimeError("representative-column clustering produced an empty cluster")
            member_weights = weights[members]
            centroid = np.sum(
                coordinates[members] * member_weights[:, None], axis=0
            ) / np.sum(member_weights)
            distance_to_centroid = np.sum(
                (coordinates[members] - centroid) ** 2, axis=1
            )
            order = members[np.argsort(distance_to_centroid, kind="stable")]
            available = [int(index) for index in order if int(index) not in occupied]
            if not available:
                raise RuntimeError("representative-column medoids are not unique")
            updated[cluster] = available[0]
            occupied.add(available[0])
        if np.array_equal(updated, centers):
            break
        centers = updated
    else:
        raise RuntimeError("representative-column clustering did not converge")

    distance_squared = np.sum(
        (coordinates[:, None, :] - coordinates[centers][None, :, :]) ** 2,
        axis=2,
    )
    assignments = np.argmin(distance_squared, axis=1)
    minimum_distance = np.sqrt(distance_squared[np.arange(point_count), assignments])
    return centers, assignments, minimum_distance


def select_quasi_static_representative_annuli(
    model: ZOConstantEReferenceModel,
    *,
    count: int = 12,
    quasi_static_threshold: float = 0.1,
    optical_band_hz: tuple[float, float] = (5.0e14, 1.0e15),
    optical_frequency_points: int = 65,
    maximum_iterations: int = 100,
) -> RepresentativeAnnulusSelection:
    """从 corrected 面积加权的准静态域选择可复现的代表柱。

    聚类权重等量混合 corrected 面积、局域玻尔兹曼功率和保守光学带
    黑体功率。光学黑体项只负责抽样覆盖，不是 Phase 7A 的大气解。
    """
    if not isinstance(model, ZOConstantEReferenceModel):
        raise TypeError("model must be a ZOConstantEReferenceModel")
    if not isinstance(count, (int, np.integer)) or isinstance(count, (bool, np.bool_)):
        raise PhysicalDomainError("count must be an integer")
    count = int(count)
    if count < 1:
        raise PhysicalDomainError("count must be positive")
    threshold = float(quasi_static_threshold)
    if not np.isfinite(threshold) or threshold <= 0.0:
        raise PhysicalDomainError("quasi_static_threshold must be finite and positive")
    lower_frequency, upper_frequency = (float(value) for value in optical_band_hz)
    if (
        not np.isfinite(lower_frequency)
        or not np.isfinite(upper_frequency)
        or lower_frequency <= 0.0
        or upper_frequency <= lower_frequency
    ):
        raise PhysicalDomainError("optical_band_hz must be finite, positive and increasing")
    if (
        not isinstance(optical_frequency_points, (int, np.integer))
        or int(optical_frequency_points) < 17
    ):
        raise PhysicalDomainError("optical_frequency_points must be an integer >= 17")
    if (
        not isinstance(maximum_iterations, (int, np.integer))
        or int(maximum_iterations) < 1
    ):
        raise PhysicalDomainError("maximum_iterations must be a positive integer")

    atmosphere = zo_annulus_atmosphere_coordinates(model)
    source = model.source
    area = corrected_zo_area_weights(source)
    bolometric = (
        area
        * STEFAN_BOLTZMANN_ERG_S_CM2_K4
        * source.effective_temperature_k**4
    )
    optical_surface_flux = _blackbody_band_flux(
        source.effective_temperature_k.reshape(-1),
        lower_frequency,
        upper_frequency,
        int(optical_frequency_points),
    ).reshape(source.shape)
    optical = area * optical_surface_flux
    valid = atmosphere.quasi_static_ratio < threshold
    valid_count = int(np.count_nonzero(valid))
    if valid_count < count:
        raise PhysicalDomainError(
            f"quasi-static domain contains {valid_count} cells, fewer than count={count}"
        )

    valid_area = area[valid]
    valid_bolometric = bolometric[valid]
    valid_optical = optical[valid]
    normalized_area = valid_area / np.sum(valid_area)
    normalized_bolometric = valid_bolometric / np.sum(valid_bolometric)
    normalized_optical = valid_optical / np.sum(valid_optical)
    mixture = (normalized_area + normalized_bolometric + normalized_optical) / 3.0

    raw_coordinates = np.column_stack(
        (
            np.log10(source.effective_temperature_k[valid]),
            np.log10(atmosphere.midplane_column_mass_g_cm2[valid]),
            np.log10(atmosphere.comoving_pressure_gravity_coefficient_s2[valid]),
        )
    )
    coordinate_minimum = np.min(raw_coordinates, axis=0)
    coordinate_span = np.max(raw_coordinates, axis=0) - coordinate_minimum
    if np.any(coordinate_span <= 0.0):
        raise PhysicalDomainError("quasi-static annulus coordinates do not span 3D space")
    # 中文：三个对数坐标各缩放到单位区间，避免量纲或数量级主导聚类。
    coordinates = (raw_coordinates - coordinate_minimum) / coordinate_span
    centers, assignments, minimum_distance = _deterministic_weighted_medoids(
        coordinates, mixture, count, int(maximum_iterations)
    )

    valid_flat_indices = np.flatnonzero(valid.reshape(-1))
    representative_flat_indices = valid_flat_indices[centers]
    radial_index, anomaly_index = np.unravel_index(
        representative_flat_indices, source.shape
    )
    cluster_area = np.bincount(
        assignments, weights=normalized_area, minlength=count
    )
    cluster_bolometric = np.bincount(
        assignments, weights=normalized_bolometric, minlength=count
    )
    cluster_optical = np.bincount(
        assignments, weights=normalized_optical, minlength=count
    )
    cluster_mixture = np.bincount(assignments, weights=mixture, minlength=count)
    cluster_radius = np.asarray(
        [np.max(minimum_distance[assignments == cluster]) for cluster in range(count)]
    )
    weighted_rms = float(np.sqrt(np.sum(mixture * minimum_distance**2)))

    arrays = (
        np.asarray(radial_index, dtype=np.int64),
        np.asarray(anomaly_index, dtype=np.int64),
        source.semimajor_axis_cm[radial_index],
        source.eccentric_anomaly_rad[anomaly_index],
        source.effective_temperature_k[radial_index, anomaly_index],
        atmosphere.midplane_column_mass_g_cm2[radial_index, anomaly_index],
        atmosphere.comoving_pressure_gravity_coefficient_s2[
            radial_index, anomaly_index
        ],
        atmosphere.quasi_static_ratio[radial_index, anomaly_index],
        cluster_area,
        cluster_bolometric,
        cluster_optical,
        cluster_mixture,
        cluster_radius,
    )
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ArithmeticError("representative-column selection became non-finite")
    return RepresentativeAnnulusSelection(
        *(_readonly(np.asarray(array)) for array in arrays),
        quasi_static_threshold=threshold,
        valid_cell_count=valid_count,
        excluded_cell_count=int(valid.size - valid_count),
        valid_area_fraction=float(np.sum(area[valid]) / np.sum(area)),
        valid_bolometric_fraction=float(
            np.sum(bolometric[valid]) / np.sum(bolometric)
        ),
        valid_optical_fraction=float(np.sum(optical[valid]) / np.sum(optical)),
        weighted_rms_distance=weighted_rms,
        maximum_distance=float(np.max(minimum_distance)),
        optical_band_hz=(lower_frequency, upper_frequency),
    )
