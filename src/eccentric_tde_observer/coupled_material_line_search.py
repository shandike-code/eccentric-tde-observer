"""用两个完整辐射反馈端点保护物质割线回溯。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .radiation_matter_feedback import (
    ground_state_material_specific_energy_erg_g,
    ground_state_material_temperature_from_specific_energy_k,
)
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class ProtectedResidualLineSearchMaterialStep:
    """离散回溯候选及其端点仿射残差预测。"""

    relaxation: float
    temperature_k: NDArray[np.float64]
    hydrogen_fraction: NDArray[np.float64]
    helium_fraction: NDArray[np.float64]
    specific_material_energy_erg_g: NDArray[np.float64]
    recovered_specific_material_energy_erg_g: NDArray[np.float64]
    predicted_signed_residual_erg_g: NDArray[np.float64]
    predicted_residual_scale_erg_g: NDArray[np.float64]
    current_mass_weighted_residual: float
    predicted_mass_weighted_residual: float
    predicted_mass_weighted_contraction: float
    current_maximum_cell_residual: float
    predicted_maximum_cell_residual: float
    predicted_maximum_cell_contraction: float
    current_limiting_cell: int
    predicted_limiting_cell_contraction: float
    maximum_relative_energy_residual: float
    maximum_particle_conservation_residual: float
    minimum_population_fraction: float


def protected_residual_line_search_material_step(
    current_temperature_k: ArrayLike,
    current_hydrogen_fraction: ArrayLike,
    current_helium_fraction: ArrayLike,
    endpoint_temperature_k: ArrayLike,
    endpoint_hydrogen_fraction: ArrayLike,
    endpoint_helium_fraction: ArrayLike,
    current_signed_residual_erg_g: ArrayLike,
    endpoint_signed_residual_erg_g: ArrayLike,
    current_residual_scale_erg_g: ArrayLike,
    endpoint_residual_scale_erg_g: ArrayLike,
    cell_mass_g_cm2: ArrayLike,
    *,
    candidate_relaxations: tuple[float, ...],
    maximum_predicted_mass_weighted_contraction: float,
    maximum_predicted_limiting_cell_contraction: float,
    maximum_predicted_maximum_cell_contraction: float,
) -> ProtectedResidualLineSearchMaterialStep:
    """在预声明离散步长中选择仿射残差最小且全部保护门通过者。"""
    current_temperature = np.asarray(current_temperature_k, dtype=np.float64)
    endpoint_temperature = np.asarray(endpoint_temperature_k, dtype=np.float64)
    current_hydrogen = np.asarray(current_hydrogen_fraction, dtype=np.float64)
    endpoint_hydrogen = np.asarray(endpoint_hydrogen_fraction, dtype=np.float64)
    current_helium = np.asarray(current_helium_fraction, dtype=np.float64)
    endpoint_helium = np.asarray(endpoint_helium_fraction, dtype=np.float64)
    cells = current_temperature.size
    vectors = tuple(
        np.asarray(value, dtype=np.float64)
        for value in (
            current_signed_residual_erg_g,
            endpoint_signed_residual_erg_g,
            current_residual_scale_erg_g,
            endpoint_residual_scale_erg_g,
            cell_mass_g_cm2,
        )
    )
    current_residual, endpoint_residual, current_scale, endpoint_scale, cell_mass = (
        vectors
    )
    if (
        endpoint_temperature.shape != (cells,)
        or current_hydrogen.shape != (cells, 2)
        or endpoint_hydrogen.shape != (cells, 2)
        or current_helium.shape != (cells, 3)
        or endpoint_helium.shape != (cells, 3)
        or any(value.shape != (cells,) for value in vectors)
        or not all(
            np.all(np.isfinite(value))
            for value in (
                current_temperature,
                endpoint_temperature,
                current_hydrogen,
                endpoint_hydrogen,
                current_helium,
                endpoint_helium,
                *vectors,
            )
        )
        or np.any(current_temperature <= 0.0)
        or np.any(endpoint_temperature <= 0.0)
        or np.any(current_hydrogen < 0.0)
        or np.any(endpoint_hydrogen < 0.0)
        or np.any(current_helium < 0.0)
        or np.any(endpoint_helium < 0.0)
        or np.any(current_scale <= 0.0)
        or np.any(endpoint_scale <= 0.0)
        or np.any(cell_mass <= 0.0)
    ):
        raise PhysicalDomainError("line-search endpoints must share one valid cell axis")
    simplex_residual = max(
        float(np.max(np.abs(np.sum(current_hydrogen, axis=1) - 1.0))),
        float(np.max(np.abs(np.sum(endpoint_hydrogen, axis=1) - 1.0))),
        float(np.max(np.abs(np.sum(current_helium, axis=1) - 1.0))),
        float(np.max(np.abs(np.sum(endpoint_helium, axis=1) - 1.0))),
    )
    if simplex_residual >= 1.0e-12:
        raise PhysicalDomainError("line-search endpoint violates the H/He simplex")
    candidates = tuple(float(value) for value in candidate_relaxations)
    gates = (
        float(maximum_predicted_mass_weighted_contraction),
        float(maximum_predicted_limiting_cell_contraction),
        float(maximum_predicted_maximum_cell_contraction),
    )
    if (
        not candidates
        or not all(np.isfinite(value) and 0.0 < value < 1.0 for value in candidates)
        or len(set(candidates)) != len(candidates)
        or not all(np.isfinite(value) and 0.0 < value < 1.0 for value in gates)
    ):
        raise PhysicalDomainError("line-search candidates or gates are invalid")
    current_relative = np.abs(current_residual) / current_scale
    current_weighted = float(np.sum(cell_mass * np.abs(current_residual))) / float(
        np.sum(cell_mass * current_scale)
    )
    current_maximum = float(np.max(current_relative))
    limiting_cell = int(np.argmax(current_relative))
    feasible: list[tuple[float, float, NDArray[np.float64], NDArray[np.float64], float, float]] = []
    for relaxation in candidates:
        # 中文：这里仅线性插值两个已完成全频映射的真残差，最终仍需新映射验证。
        residual = current_residual + relaxation * (
            endpoint_residual - current_residual
        )
        scale = current_scale + relaxation * (endpoint_scale - current_scale)
        relative = np.abs(residual) / scale
        weighted = float(np.sum(cell_mass * np.abs(residual))) / float(
            np.sum(cell_mass * scale)
        )
        weighted_contraction = weighted / current_weighted
        limiting_contraction = (
            float(relative[limiting_cell]) / float(current_relative[limiting_cell])
        )
        maximum_contraction = float(np.max(relative)) / current_maximum
        if (
            weighted_contraction < gates[0]
            and limiting_contraction < gates[1]
            and maximum_contraction < gates[2]
        ):
            feasible.append(
                (
                    weighted,
                    relaxation,
                    np.array(residual, copy=True),
                    np.array(scale, copy=True),
                    limiting_contraction,
                    maximum_contraction,
                )
            )
    if not feasible:
        raise PhysicalDomainError("no preregistered residual line-search candidate passed")
    weighted, relaxation, residual, scale, limiting_contraction, maximum_contraction = min(
        feasible, key=lambda item: (item[0], item[1])
    )
    current_energy = np.asarray(
        ground_state_material_specific_energy_erg_g(
            current_temperature, current_hydrogen, current_helium
        )
    )
    endpoint_energy = np.asarray(
        ground_state_material_specific_energy_erg_g(
            endpoint_temperature, endpoint_hydrogen, endpoint_helium
        )
    )
    energy = current_energy + relaxation * (endpoint_energy - current_energy)
    hydrogen = current_hydrogen + relaxation * (
        endpoint_hydrogen - current_hydrogen
    )
    helium = current_helium + relaxation * (endpoint_helium - current_helium)
    if np.any(energy <= 0.0) or np.any(hydrogen < 0.0) or np.any(helium < 0.0):
        raise PhysicalDomainError("selected convex line-search state left physical domain")
    temperature = ground_state_material_temperature_from_specific_energy_k(
        energy, hydrogen, helium
    )
    recovered_energy = np.asarray(
        ground_state_material_specific_energy_erg_g(temperature, hydrogen, helium)
    )
    energy_relative = np.abs(recovered_energy - energy) / np.maximum(
        np.abs(recovered_energy), np.abs(energy)
    )
    particle_residual = max(
        float(np.max(np.abs(np.sum(hydrogen, axis=1) - 1.0))),
        float(np.max(np.abs(np.sum(helium, axis=1) - 1.0))),
    )
    return ProtectedResidualLineSearchMaterialStep(
        relaxation=relaxation,
        temperature_k=_readonly(np.array(temperature, copy=True)),
        hydrogen_fraction=_readonly(np.array(hydrogen, copy=True)),
        helium_fraction=_readonly(np.array(helium, copy=True)),
        specific_material_energy_erg_g=_readonly(np.array(energy, copy=True)),
        recovered_specific_material_energy_erg_g=_readonly(
            np.array(recovered_energy, copy=True)
        ),
        predicted_signed_residual_erg_g=_readonly(residual),
        predicted_residual_scale_erg_g=_readonly(scale),
        current_mass_weighted_residual=current_weighted,
        predicted_mass_weighted_residual=weighted,
        predicted_mass_weighted_contraction=weighted / current_weighted,
        current_maximum_cell_residual=current_maximum,
        predicted_maximum_cell_residual=float(np.max(np.abs(residual) / scale)),
        predicted_maximum_cell_contraction=maximum_contraction,
        current_limiting_cell=limiting_cell,
        predicted_limiting_cell_contraction=limiting_contraction,
        maximum_relative_energy_residual=float(np.max(energy_relative)),
        maximum_particle_conservation_residual=particle_residual,
        minimum_population_fraction=float(min(np.min(hydrogen), np.min(helium))),
    )

