"""对数频率守恒 P1 表示下的 H/He 基态连续微物理。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .continuum_emission import (
    GroundStateMilneContinuum,
    GroundStateMilneRadiativeRates,
    ground_state_milne_continuum,
    ground_state_milne_radiative_rates,
)
from .log_frequency_moments import (
    limit_nonnegative_log_frequency_group_p1,
    log_frequency_group_p1_gauss_node_values,
)
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class LogFrequencyGroupQuadrature:
    """每个 ``ln(nu)`` 控制体中的正权 Gauss--Legendre 节点。"""

    group_edge_hz: NDArray[np.float64]
    group_edge_log_hz: NDArray[np.float64]
    group_centre_log_hz: NDArray[np.float64]
    group_width_log_hz: NDArray[np.float64]
    node_log_hz: NDArray[np.float64]
    node_hz: NDArray[np.float64]
    node_weight_log_hz: NDArray[np.float64]
    node_weight_hz: NDArray[np.float64]
    order_per_group: int


@dataclass(frozen=True)
class GroundStateMilneLogP1Multigroup:
    """对数频率 P1 强度、连续系数、原子率和能量交换。"""

    quadrature: LogFrequencyGroupQuadrature
    node_continuum: GroundStateMilneContinuum
    true_absorption_mean_per_cm: NDArray[np.float64]
    true_absorption_first_moment_per_cm: NDArray[np.float64]
    thermal_emissivity_energy_mean_cgs: NDArray[np.float64]
    thermal_emissivity_energy_first_moment_cgs: NDArray[np.float64]
    electron_scattering_mean_per_cm: NDArray[np.float64]
    electron_scattering_first_moment_per_cm: NDArray[np.float64]
    extinction_mean_per_cm: NDArray[np.float64]
    extinction_first_moment_per_cm: NDArray[np.float64]
    radiative_rates: GroundStateMilneRadiativeRates
    mean_intensity_energy_cgs: NDArray[np.float64]
    mean_intensity_energy_first_moment_cgs: NDArray[np.float64]
    absorbed_power_erg_s_cm3: NDArray[np.float64]
    emitted_power_erg_s_cm3: NDArray[np.float64]
    radiative_heating_erg_s_cm3: NDArray[np.float64]
    continuum_limited_group_count: int
    maximum_continuum_prelimit_realizability_ratio: float


def gauss_legendre_log_frequency_group_quadrature(
    group_edge_hz: ArrayLike,
    *,
    order_per_group: int = 16,
) -> LogFrequencyGroupQuadrature:
    """在每个自然对数频率控制体中构造正权 Gauss 节点。"""
    edge = np.asarray(group_edge_hz, dtype=np.float64)
    if (
        edge.ndim != 1
        or edge.size < 2
        or not np.all(np.isfinite(edge))
        or np.any(edge <= 0.0)
        or np.any(np.diff(edge) <= 0.0)
    ):
        raise PhysicalDomainError(
            "group_edge_hz must be finite, positive and strictly increasing"
        )
    if (
        not isinstance(order_per_group, (int, np.integer))
        or isinstance(order_per_group, (bool, np.bool_))
        or int(order_per_group) < 2
    ):
        raise PhysicalDomainError("order_per_group must be an integer of at least two")
    node, weight = np.polynomial.legendre.leggauss(int(order_per_group))
    edge_y = np.log(edge)
    centre_y = 0.5 * (edge_y[:-1] + edge_y[1:])
    half_width_y = 0.5 * np.diff(edge_y)
    node_y = centre_y[:, None] + half_width_y[:, None] * node[None, :]
    node_hz = np.exp(node_y)
    weight_y = half_width_y[:, None] * weight[None, :]
    weight_hz = weight_y * node_hz
    width_y = np.diff(edge_y)
    if (
        not np.all(np.isfinite(node_hz))
        or not np.all(np.isfinite(weight_y))
        or np.any(weight_y <= 0.0)
        or not np.allclose(
            np.sum(weight_y, axis=1),
            width_y,
            rtol=8.0 * np.finfo(np.float64).eps,
            atol=0.0,
        )
    ):
        raise ArithmeticError("log-frequency quadrature became invalid")
    return LogFrequencyGroupQuadrature(
        group_edge_hz=_readonly(np.array(edge, copy=True)),
        group_edge_log_hz=_readonly(edge_y),
        group_centre_log_hz=_readonly(centre_y),
        group_width_log_hz=_readonly(width_y),
        node_log_hz=_readonly(node_y),
        node_hz=_readonly(node_hz),
        node_weight_log_hz=_readonly(weight_y),
        node_weight_hz=_readonly(weight_hz),
        order_per_group=int(order_per_group),
    )


def log_group_average_from_quadrature_nodes(
    values: ArrayLike,
    quadrature: LogFrequencyGroupQuadrature,
) -> NDArray[np.float64]:
    """计算 ``Delta y`` 归一化的正权组平均。"""
    array = np.asarray(values, dtype=np.float64)
    expected = quadrature.node_hz.shape
    if array.ndim < 2 or array.shape[:2] != expected:
        raise PhysicalDomainError("node values must match log-frequency quadrature")
    if not np.all(np.isfinite(array)):
        raise PhysicalDomainError("log-frequency node values must be finite")
    trailing = (1,) * (array.ndim - 2)
    weight = quadrature.node_weight_log_hz.reshape((*expected, *trailing))
    width = quadrature.group_width_log_hz.reshape((expected[0], *trailing))
    mean = np.sum(weight * array, axis=1) / width
    if not np.all(np.isfinite(mean)):
        raise ArithmeticError("log-frequency group average became non-finite")
    return _readonly(mean)


def log_group_p1_moment_from_quadrature_nodes(
    values: ArrayLike,
    quadrature: LogFrequencyGroupQuadrature,
) -> NDArray[np.float64]:
    """计算 ``Delta y^-1 integral Q x dy``。"""
    array = np.asarray(values, dtype=np.float64)
    expected = quadrature.node_hz.shape
    if array.ndim < 2 or array.shape[:2] != expected:
        raise PhysicalDomainError("node values must match log-frequency quadrature")
    if not np.all(np.isfinite(array)):
        raise PhysicalDomainError("log-frequency node values must be finite")
    trailing = (1,) * (array.ndim - 2)
    weight = quadrature.node_weight_log_hz.reshape((*expected, *trailing))
    width = quadrature.group_width_log_hz.reshape((expected[0], *trailing))
    coordinate = 2.0 * (
        quadrature.node_log_hz - quadrature.group_centre_log_hz[:, None]
    ) / quadrature.group_width_log_hz[:, None]
    coordinate = coordinate.reshape((*expected, *trailing))
    moment = np.sum(weight * array * coordinate, axis=1) / width
    if not np.all(np.isfinite(moment)):
        raise ArithmeticError("log-frequency P1 moment became non-finite")
    return _readonly(moment)


def log_group_p1_values_at_quadrature_nodes(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    quadrature: LogFrequencyGroupQuadrature,
) -> NDArray[np.float64]:
    """在任意对数频率节点重构整组非负的线性 ``Q``。"""
    mean = np.asarray(mean_density, dtype=np.float64)
    first = np.asarray(first_moment_density, dtype=np.float64)
    if (
        mean.ndim < 1
        or first.shape != mean.shape
        or mean.shape[0] != quadrature.group_width_log_hz.size
    ):
        raise PhysicalDomainError("log-frequency P1 moments do not match groups")
    state = limit_nonnegative_log_frequency_group_p1(mean, first)
    if state.limited_group_count != 0:
        raise PhysicalDomainError("log-frequency P1 state is not realizable")
    trailing = (1,) * (mean.ndim - 1)
    coordinate = 2.0 * (
        quadrature.node_log_hz - quadrature.group_centre_log_hz[:, None]
    ) / quadrature.group_width_log_hz[:, None]
    node = mean[:, None, ...] + 3.0 * first[:, None, ...] * coordinate.reshape(
        (*coordinate.shape, *trailing)
    )
    if not np.all(np.isfinite(node)) or np.any(node < 0.0):
        raise ArithmeticError("log-frequency P1 reconstruction became invalid")
    return _readonly(node)


def ground_state_milne_log_p1_multigroup(
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    group_edge_hz: ArrayLike,
    group_mean_intensity_energy_cgs: ArrayLike,
    group_first_moment_intensity_energy_cgs: ArrayLike,
    hydrogen_neutral_fraction: ArrayLike,
    hydrogen_ionized_fraction: ArrayLike,
    helium_neutral_fraction: ArrayLike,
    helium_singly_ionized_fraction: ArrayLike,
    helium_doubly_ionized_fraction: ArrayLike,
    *,
    order_per_group: int = 16,
    include_electron_scattering: bool = True,
) -> GroundStateMilneLogP1Multigroup:
    """计算与 ``Q=nu*J_nu`` P1 表示一致的 H/He 连续交换。"""
    quadrature = gauss_legendre_log_frequency_group_quadrature(
        group_edge_hz, order_per_group=order_per_group
    )
    mean = np.asarray(group_mean_intensity_energy_cgs, dtype=np.float64)
    first = np.asarray(
        group_first_moment_intensity_energy_cgs, dtype=np.float64
    )
    group_count = quadrature.group_width_log_hz.size
    if mean.ndim != 2 or first.shape != mean.shape or mean.shape[0] != group_count:
        raise PhysicalDomainError(
            "log-frequency intensity moments must have shape (group, depth)"
        )
    state = limit_nonnegative_log_frequency_group_p1(mean, first)
    if state.limited_group_count != 0:
        raise PhysicalDomainError("log-frequency radiation input is not realizable")
    node_energy_grouped = log_group_p1_values_at_quadrature_nodes(
        mean, first, quadrature
    )
    node_frequency = quadrature.node_hz.reshape(-1)
    node_continuum = ground_state_milne_continuum(
        density_g_cm3,
        temperature_k,
        node_frequency,
        hydrogen_neutral_fraction,
        hydrogen_ionized_fraction,
        helium_neutral_fraction,
        helium_singly_ionized_fraction,
        helium_doubly_ionized_fraction,
        include_electron_scattering=include_electron_scattering,
    )
    if node_continuum.extinction_total_per_cm.shape[1] != mean.shape[1]:
        raise PhysicalDomainError("material depth does not match log-frequency intensity")

    def grouped(field: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.asarray(field).reshape(
            group_count, quadrature.order_per_group, *field.shape[1:]
        )

    def project(field: NDArray[np.float64]):
        values = grouped(field)
        return limit_nonnegative_log_frequency_group_p1(
            log_group_average_from_quadrature_nodes(values, quadrature),
            log_group_p1_moment_from_quadrature_nodes(values, quadrature),
        )

    absorption = project(node_continuum.true_absorption_total_per_cm)
    scattering = project(node_continuum.electron_scattering_per_cm)
    node_emissivity_energy = (
        node_frequency[:, None] * node_continuum.thermal_emissivity_total_cgs
    )
    emissivity = project(node_emissivity_energy)
    extinction = limit_nonnegative_log_frequency_group_p1(
        absorption.mean_density + scattering.mean_density,
        absorption.first_moment_density + scattering.first_moment_density,
    )
    if extinction.limited_group_count != 0:
        raise ArithmeticError("sum of log-frequency extinctions lost realizability")

    node_energy = node_energy_grouped.reshape(node_frequency.size, mean.shape[1])
    node_intensity = node_energy / node_frequency[:, None]
    rates = ground_state_milne_radiative_rates(
        temperature_k,
        node_frequency,
        node_intensity,
        frequency_weight_hz=quadrature.node_weight_hz.reshape(-1),
    )
    node_absorption = grouped(node_continuum.true_absorption_total_per_cm)
    node_emissivity_energy_grouped = grouped(node_emissivity_energy)
    weight_shape = (
        group_count,
        quadrature.order_per_group,
        *([1] * (node_energy_grouped.ndim - 2)),
    )
    weight_y = quadrature.node_weight_log_hz.reshape(weight_shape)
    absorbed = 4.0 * np.pi * np.sum(
        weight_y * node_absorption * node_energy_grouped,
        axis=(0, 1),
    )
    emitted = 4.0 * np.pi * np.sum(
        weight_y * node_emissivity_energy_grouped,
        axis=(0, 1),
    )
    heating = absorbed - emitted
    if not all(
        np.all(np.isfinite(field)) for field in (absorbed, emitted, heating)
    ):
        raise ArithmeticError("log-frequency radiative exchange became non-finite")
    if np.any(absorbed < 0.0) or np.any(emitted < 0.0):
        raise ArithmeticError("log-frequency radiative power became negative")
    return GroundStateMilneLogP1Multigroup(
        quadrature=quadrature,
        node_continuum=node_continuum,
        true_absorption_mean_per_cm=absorption.mean_density,
        true_absorption_first_moment_per_cm=absorption.first_moment_density,
        thermal_emissivity_energy_mean_cgs=emissivity.mean_density,
        thermal_emissivity_energy_first_moment_cgs=(
            emissivity.first_moment_density
        ),
        electron_scattering_mean_per_cm=scattering.mean_density,
        electron_scattering_first_moment_per_cm=(
            scattering.first_moment_density
        ),
        extinction_mean_per_cm=extinction.mean_density,
        extinction_first_moment_per_cm=extinction.first_moment_density,
        radiative_rates=rates,
        mean_intensity_energy_cgs=_readonly(np.array(mean, copy=True)),
        mean_intensity_energy_first_moment_cgs=_readonly(
            np.array(first, copy=True)
        ),
        absorbed_power_erg_s_cm3=_readonly(np.array(absorbed, copy=True)),
        emitted_power_erg_s_cm3=_readonly(np.array(emitted, copy=True)),
        radiative_heating_erg_s_cm3=_readonly(np.array(heating, copy=True)),
        continuum_limited_group_count=(
            absorption.limited_group_count
            + emissivity.limited_group_count
            + scattering.limited_group_count
        ),
        maximum_continuum_prelimit_realizability_ratio=max(
            absorption.maximum_prelimit_realizability_ratio,
            emissivity.maximum_prelimit_realizability_ratio,
            scattering.maximum_prelimit_realizability_ratio,
        ),
    )
