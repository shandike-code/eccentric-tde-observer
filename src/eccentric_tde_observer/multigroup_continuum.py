"""阈值对齐频率组上的 H/He 基态连续系数与辐射交换。

频率组表示假定组内谱强度为常数，但连续系数仍在每个真实频率控制体内做
Gauss--Legendre 积分。这样频率组既可参与守恒 Doppler 搬移，也不会把中心
频率值冒充组平均。本模块只建立多群连续系数，不推进物质状态。
"""

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
from .mixed_frame_frequency import (
    limit_nonnegative_frequency_group_p1,
    limit_nonnegative_frequency_group_p2,
)
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class FrequencyGroupQuadrature:
    """每个有限体积频率组内部的正权 Gauss--Legendre 节点。"""

    group_edge_hz: NDArray[np.float64]
    group_centre_hz: NDArray[np.float64]
    group_width_hz: NDArray[np.float64]
    node_hz: NDArray[np.float64]
    node_weight_hz: NDArray[np.float64]
    order_per_group: int


@dataclass(frozen=True)
class GroundStateMilneMultigroup:
    """组平均连续系数、组内一致辐射率和能量交换。"""

    quadrature: FrequencyGroupQuadrature
    continuum: GroundStateMilneContinuum
    radiative_rates: GroundStateMilneRadiativeRates
    mean_intensity_cgs: NDArray[np.float64]
    absorbed_power_erg_s_cm3: NDArray[np.float64]
    emitted_power_erg_s_cm3: NDArray[np.float64]
    radiative_heating_erg_s_cm3: NDArray[np.float64]


@dataclass(frozen=True)
class GroundStateMilneP1Multigroup:
    """P1 强度一致的组平均连续系数、一阶矩与辐射交换。"""

    quadrature: FrequencyGroupQuadrature
    continuum: GroundStateMilneContinuum
    true_absorption_first_moment_per_cm: NDArray[np.float64]
    thermal_emissivity_first_moment_cgs: NDArray[np.float64]
    electron_scattering_first_moment_per_cm: NDArray[np.float64]
    radiative_rates: GroundStateMilneRadiativeRates
    mean_intensity_cgs: NDArray[np.float64]
    mean_intensity_first_moment_cgs: NDArray[np.float64]
    absorbed_power_erg_s_cm3: NDArray[np.float64]
    emitted_power_erg_s_cm3: NDArray[np.float64]
    radiative_heating_erg_s_cm3: NDArray[np.float64]
    continuum_limited_group_count: int
    maximum_continuum_prelimit_realizability_ratio: float


@dataclass(frozen=True)
class GroundStateMilneP2Multigroup:
    """P2 强度一致的组平均连续系数、两个高阶矩和辐射交换。"""

    quadrature: FrequencyGroupQuadrature
    continuum: GroundStateMilneContinuum
    true_absorption_first_moment_per_cm: NDArray[np.float64]
    true_absorption_second_moment_per_cm: NDArray[np.float64]
    thermal_emissivity_first_moment_cgs: NDArray[np.float64]
    thermal_emissivity_second_moment_cgs: NDArray[np.float64]
    electron_scattering_first_moment_per_cm: NDArray[np.float64]
    electron_scattering_second_moment_per_cm: NDArray[np.float64]
    radiative_rates: GroundStateMilneRadiativeRates
    mean_intensity_cgs: NDArray[np.float64]
    mean_intensity_first_moment_cgs: NDArray[np.float64]
    mean_intensity_second_moment_cgs: NDArray[np.float64]
    absorbed_power_erg_s_cm3: NDArray[np.float64]
    emitted_power_erg_s_cm3: NDArray[np.float64]
    radiative_heating_erg_s_cm3: NDArray[np.float64]
    continuum_limited_group_count: int
    maximum_continuum_prelimit_negativity_ratio: float


def gauss_legendre_frequency_group_quadrature(
    group_edge_hz: ArrayLike,
    *,
    order_per_group: int = 16,
) -> FrequencyGroupQuadrature:
    """在每个真实频率控制体内构造正权线性频率求积。"""
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
    left = edge[:-1]
    right = edge[1:]
    centre = 0.5 * (left + right)
    half_width = 0.5 * (right - left)
    node_hz = centre[:, None] + half_width[:, None] * node[None, :]
    node_weight_hz = half_width[:, None] * weight[None, :]
    width = right - left
    if (
        not np.all(np.isfinite(node_hz))
        or not np.all(np.isfinite(node_weight_hz))
        or np.any(node_weight_hz <= 0.0)
        or not np.allclose(
            np.sum(node_weight_hz, axis=1),
            width,
            rtol=8.0 * np.finfo(np.float64).eps,
            atol=0.0,
        )
    ):
        raise ArithmeticError("frequency-group quadrature became invalid")
    return FrequencyGroupQuadrature(
        group_edge_hz=_readonly(np.array(edge, copy=True)),
        group_centre_hz=_readonly(np.array(centre, copy=True)),
        group_width_hz=_readonly(np.array(width, copy=True)),
        node_hz=_readonly(node_hz),
        node_weight_hz=_readonly(node_weight_hz),
        order_per_group=int(order_per_group),
    )


def group_average_from_quadrature_nodes(
    values: ArrayLike,
    quadrature: FrequencyGroupQuadrature,
) -> NDArray[np.float64]:
    """把形如 ``(group, node, ...)`` 的节点量积分为频率密度组平均。"""
    array = np.asarray(values, dtype=np.float64)
    expected = quadrature.node_hz.shape
    if array.ndim < 2 or array.shape[:2] != expected:
        raise PhysicalDomainError(
            "values first two axes must match the frequency-group quadrature"
        )
    if not np.all(np.isfinite(array)):
        raise PhysicalDomainError("frequency-group node values must be finite")
    trailing = (1,) * (array.ndim - 2)
    weight = quadrature.node_weight_hz.reshape((*expected, *trailing))
    width = quadrature.group_width_hz.reshape((expected[0], *trailing))
    average = np.sum(weight * array, axis=1) / width
    if not np.all(np.isfinite(average)):
        raise ArithmeticError("frequency-group average became non-finite")
    return _readonly(average)


def group_p1_moment_from_quadrature_nodes(
    values: ArrayLike,
    quadrature: FrequencyGroupQuadrature,
) -> NDArray[np.float64]:
    """投影归一化一阶矩 ``Delta_nu^-1 int q_nu x dnu``。"""
    array = np.asarray(values, dtype=np.float64)
    expected = quadrature.node_hz.shape
    if array.ndim < 2 or array.shape[:2] != expected:
        raise PhysicalDomainError(
            "values first two axes must match the frequency-group quadrature"
        )
    if not np.all(np.isfinite(array)):
        raise PhysicalDomainError("frequency-group node values must be finite")
    trailing = (1,) * (array.ndim - 2)
    weight = quadrature.node_weight_hz.reshape((*expected, *trailing))
    width = quadrature.group_width_hz.reshape((expected[0], *trailing))
    centre = quadrature.group_centre_hz[:, None]
    coordinate = 2.0 * (
        quadrature.node_hz - centre
    ) / quadrature.group_width_hz[:, None]
    coordinate = coordinate.reshape((*expected, *trailing))
    moment = np.sum(weight * array * coordinate, axis=1) / width
    if not np.all(np.isfinite(moment)):
        raise ArithmeticError("frequency-group P1 moment became non-finite")
    return _readonly(moment)


def group_p1_values_at_quadrature_nodes(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    quadrature: FrequencyGroupQuadrature,
) -> NDArray[np.float64]:
    """在任意组内正权节点重建整组非负的线性频率密度。"""
    mean = np.asarray(mean_density, dtype=np.float64)
    moment = np.asarray(first_moment_density, dtype=np.float64)
    if (
        mean.ndim < 1
        or moment.shape != mean.shape
        or mean.shape[0] != quadrature.group_width_hz.size
    ):
        raise PhysicalDomainError("P1 mean/moment must match the quadrature groups")
    limited = limit_nonnegative_frequency_group_p1(mean, moment)
    if limited.limited_group_count != 0:
        raise PhysicalDomainError("P1 input lies outside the non-negative domain")
    trailing = (1,) * (mean.ndim - 1)
    coordinate = 2.0 * (
        quadrature.node_hz - quadrature.group_centre_hz[:, None]
    ) / quadrature.group_width_hz[:, None]
    node = mean[:, None, ...] + 3.0 * moment[:, None, ...] * coordinate.reshape(
        (*coordinate.shape, *trailing)
    )
    if not np.all(np.isfinite(node)) or np.any(node < 0.0):
        raise ArithmeticError("P1 quadrature-node reconstruction became invalid")
    return _readonly(node)


def group_p2_second_moment_from_quadrature_nodes(
    values: ArrayLike,
    quadrature: FrequencyGroupQuadrature,
) -> NDArray[np.float64]:
    """投影归一化二阶矩 ``Delta_nu^-1 int q_nu P2(x) dnu``。"""
    array = np.asarray(values, dtype=np.float64)
    expected = quadrature.node_hz.shape
    if array.ndim < 2 or array.shape[:2] != expected:
        raise PhysicalDomainError(
            "values first two axes must match the frequency-group quadrature"
        )
    if not np.all(np.isfinite(array)):
        raise PhysicalDomainError("frequency-group node values must be finite")
    trailing = (1,) * (array.ndim - 2)
    weight = quadrature.node_weight_hz.reshape((*expected, *trailing))
    width = quadrature.group_width_hz.reshape((expected[0], *trailing))
    coordinate = 2.0 * (
        quadrature.node_hz - quadrature.group_centre_hz[:, None]
    ) / quadrature.group_width_hz[:, None]
    legendre = 0.5 * (3.0 * coordinate**2 - 1.0)
    legendre = legendre.reshape((*expected, *trailing))
    moment = np.sum(weight * array * legendre, axis=1) / width
    if not np.all(np.isfinite(moment)):
        raise ArithmeticError("frequency-group P2 moment became non-finite")
    return _readonly(moment)


def group_p2_values_at_quadrature_nodes(
    mean_density: ArrayLike,
    first_moment_density: ArrayLike,
    second_moment_density: ArrayLike,
    quadrature: FrequencyGroupQuadrature,
) -> NDArray[np.float64]:
    """在任意组内正权节点重建整组非负的二次频率密度。"""
    mean = np.asarray(mean_density, dtype=np.float64)
    first = np.asarray(first_moment_density, dtype=np.float64)
    second = np.asarray(second_moment_density, dtype=np.float64)
    if (
        mean.ndim < 1
        or first.shape != mean.shape
        or second.shape != mean.shape
        or mean.shape[0] != quadrature.group_width_hz.size
    ):
        raise PhysicalDomainError("P2 moments must match the quadrature groups")
    limited = limit_nonnegative_frequency_group_p2(mean, first, second)
    if limited.limited_group_count != 0:
        raise PhysicalDomainError("P2 input lies outside the non-negative domain")
    trailing = (1,) * (mean.ndim - 1)
    coordinate = 2.0 * (
        quadrature.node_hz - quadrature.group_centre_hz[:, None]
    ) / quadrature.group_width_hz[:, None]
    x = coordinate.reshape((*coordinate.shape, *trailing))
    positive = mean > 0.0
    first_ratio = np.zeros_like(mean)
    second_ratio = np.zeros_like(mean)
    first_ratio[positive] = first[positive] / mean[positive]
    second_ratio[positive] = second[positive] / mean[positive]
    node = mean[:, None, ...] * (
        1.0
        + 3.0 * first_ratio[:, None, ...] * x
        + 2.5 * second_ratio[:, None, ...] * (3.0 * x**2 - 1.0)
    )
    if not np.all(np.isfinite(node)) or np.any(node < 0.0):
        raise ArithmeticError("P2 quadrature-node reconstruction became invalid")
    return _readonly(node)


def _group_continuum(
    node_continuum: GroundStateMilneContinuum,
    quadrature: FrequencyGroupQuadrature,
) -> GroundStateMilneContinuum:
    group_count, node_count = quadrature.node_hz.shape

    def average(field: NDArray[np.float64]) -> NDArray[np.float64]:
        reshaped = np.asarray(field).reshape(group_count, node_count, *field.shape[1:])
        return group_average_from_quadrature_nodes(reshaped, quadrature)

    # 先积分真实连续系数再构造组量，不能用组中心 opacity 代替控制体平均。
    hydrogen_absorption = average(
        node_continuum.hydrogen_i_bound_free_absorption_per_cm
    )
    helium_i_absorption = average(
        node_continuum.helium_i_bound_free_absorption_per_cm
    )
    helium_ii_absorption = average(
        node_continuum.helium_ii_bound_free_absorption_per_cm
    )
    bound_free_absorption = (
        hydrogen_absorption + helium_i_absorption + helium_ii_absorption
    )
    hydrogen_emissivity = average(
        node_continuum.hydrogen_i_bound_free_emissivity_cgs
    )
    helium_i_emissivity = average(
        node_continuum.helium_i_bound_free_emissivity_cgs
    )
    helium_ii_emissivity = average(
        node_continuum.helium_ii_bound_free_emissivity_cgs
    )
    bound_free_emissivity = (
        hydrogen_emissivity + helium_i_emissivity + helium_ii_emissivity
    )
    free_free_absorption = average(node_continuum.free_free_absorption_per_cm)
    free_free_emissivity = average(node_continuum.free_free_emissivity_cgs)
    true_absorption = bound_free_absorption + free_free_absorption
    thermal_emissivity = bound_free_emissivity + free_free_emissivity
    scattering = average(node_continuum.electron_scattering_per_cm)
    extinction = true_absorption + scattering
    # epsilon 与热源函数必须由组平均系数组合，保持同一有限体积表示。
    epsilon = np.ones_like(extinction)
    np.divide(true_absorption, extinction, out=epsilon, where=extinction > 0.0)
    thermal_source = np.zeros_like(true_absorption)
    np.divide(
        thermal_emissivity,
        true_absorption,
        out=thermal_source,
        where=true_absorption > 0.0,
    )
    if np.any((true_absorption == 0.0) & (thermal_emissivity != 0.0)):
        raise ArithmeticError(
            "group emissivity is non-zero where group true absorption vanishes"
        )
    output = (
        hydrogen_absorption,
        helium_i_absorption,
        helium_ii_absorption,
        bound_free_absorption,
        hydrogen_emissivity,
        helium_i_emissivity,
        helium_ii_emissivity,
        bound_free_emissivity,
        free_free_absorption,
        free_free_emissivity,
        true_absorption,
        thermal_emissivity,
        scattering,
        extinction,
        epsilon,
        thermal_source,
        node_continuum.electron_density_cm3,
    )
    if not all(np.all(np.isfinite(field)) for field in output):
        raise ArithmeticError("multigroup continuum became non-finite")
    if any(np.any(field < 0.0) for field in output):
        raise ArithmeticError("multigroup continuum became negative")
    if np.any(epsilon > 1.0):
        raise ArithmeticError("multigroup absorption probability exceeded unity")
    return GroundStateMilneContinuum(
        *(_readonly(np.array(field, copy=True)) for field in output)
    )


def ground_state_milne_multigroup(
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    group_edge_hz: ArrayLike,
    group_mean_intensity_cgs: ArrayLike,
    hydrogen_neutral_fraction: ArrayLike,
    hydrogen_ionized_fraction: ArrayLike,
    helium_neutral_fraction: ArrayLike,
    helium_singly_ionized_fraction: ArrayLike,
    helium_doubly_ionized_fraction: ArrayLike,
    *,
    order_per_group: int = 16,
    include_electron_scattering: bool = True,
) -> GroundStateMilneMultigroup:
    """计算与组内常强度表示严格一致的 H/He 多群连续量。"""
    quadrature = gauss_legendre_frequency_group_quadrature(
        group_edge_hz, order_per_group=order_per_group
    )
    mean = np.asarray(group_mean_intensity_cgs, dtype=np.float64)
    group_count = quadrature.group_width_hz.size
    if mean.ndim != 2 or mean.shape[0] != group_count:
        raise PhysicalDomainError(
            "group_mean_intensity_cgs must have shape (frequency_group, depth)"
        )
    if not np.all(np.isfinite(mean)) or np.any(mean < 0.0):
        raise PhysicalDomainError(
            "group_mean_intensity_cgs must be finite and non-negative"
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
        raise PhysicalDomainError(
            "group mean-intensity depth axis must match the material profiles"
        )
    continuum = _group_continuum(node_continuum, quadrature)
    # 组内常强度只描述辐射自由度；原子截面仍在正权节点上逐点积分。
    node_mean = np.broadcast_to(
        mean[:, None, :],
        (group_count, quadrature.order_per_group, mean.shape[1]),
    ).reshape(node_frequency.size, mean.shape[1])
    rates = ground_state_milne_radiative_rates(
        temperature_k,
        node_frequency,
        node_mean,
        frequency_weight_hz=quadrature.node_weight_hz.reshape(-1),
    )
    width = quadrature.group_width_hz[:, None]
    # 频率积分的吸收与发射功率使用同一组宽，净加热不做事后平衡修补。
    absorbed = 4.0 * np.pi * np.sum(
        width * continuum.true_absorption_total_per_cm * mean,
        axis=0,
    )
    emitted = 4.0 * np.pi * np.sum(
        width * continuum.thermal_emissivity_total_cgs,
        axis=0,
    )
    heating = absorbed - emitted
    if not all(np.all(np.isfinite(field)) for field in (absorbed, emitted, heating)):
        raise ArithmeticError("multigroup radiative exchange became non-finite")
    if np.any(absorbed < 0.0) or np.any(emitted < 0.0):
        raise ArithmeticError("multigroup absorbed/emitted power became negative")
    return GroundStateMilneMultigroup(
        quadrature=quadrature,
        continuum=continuum,
        radiative_rates=rates,
        mean_intensity_cgs=_readonly(np.array(mean, copy=True)),
        absorbed_power_erg_s_cm3=_readonly(np.array(absorbed, copy=True)),
        emitted_power_erg_s_cm3=_readonly(np.array(emitted, copy=True)),
        radiative_heating_erg_s_cm3=_readonly(np.array(heating, copy=True)),
    )


def ground_state_milne_p1_multigroup(
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    group_edge_hz: ArrayLike,
    group_mean_intensity_cgs: ArrayLike,
    group_first_moment_intensity_cgs: ArrayLike,
    hydrogen_neutral_fraction: ArrayLike,
    hydrogen_ionized_fraction: ArrayLike,
    helium_neutral_fraction: ArrayLike,
    helium_singly_ionized_fraction: ArrayLike,
    helium_doubly_ionized_fraction: ArrayLike,
    *,
    order_per_group: int = 16,
    include_electron_scattering: bool = True,
) -> GroundStateMilneP1Multigroup:
    """计算与组内线性强度一致的 H/He 连续系数、率和能量交换。"""
    quadrature = gauss_legendre_frequency_group_quadrature(
        group_edge_hz, order_per_group=order_per_group
    )
    mean = np.asarray(group_mean_intensity_cgs, dtype=np.float64)
    moment = np.asarray(group_first_moment_intensity_cgs, dtype=np.float64)
    group_count = quadrature.group_width_hz.size
    if (
        mean.ndim != 2
        or moment.shape != mean.shape
        or mean.shape[0] != group_count
    ):
        raise PhysicalDomainError(
            "P1 group intensity must have matching (frequency_group,depth) moments"
        )
    input_state = limit_nonnegative_frequency_group_p1(mean, moment)
    if input_state.limited_group_count != 0:
        raise PhysicalDomainError("P1 radiation input is not non-negative realizable")
    node_mean_grouped = group_p1_values_at_quadrature_nodes(
        mean, moment, quadrature
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
        raise PhysicalDomainError(
            "P1 group intensity depth axis must match the material profiles"
        )
    continuum = _group_continuum(node_continuum, quadrature)

    def grouped(field: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.asarray(field).reshape(
            group_count, quadrature.order_per_group, *field.shape[1:]
        )

    absorption_moment_raw = group_p1_moment_from_quadrature_nodes(
        grouped(node_continuum.true_absorption_total_per_cm), quadrature
    )
    emissivity_moment_raw = group_p1_moment_from_quadrature_nodes(
        grouped(node_continuum.thermal_emissivity_total_cgs), quadrature
    )
    scattering_moment_raw = group_p1_moment_from_quadrature_nodes(
        grouped(node_continuum.electron_scattering_per_cm), quadrature
    )
    absorption_state = limit_nonnegative_frequency_group_p1(
        continuum.true_absorption_total_per_cm, absorption_moment_raw
    )
    emissivity_state = limit_nonnegative_frequency_group_p1(
        continuum.thermal_emissivity_total_cgs, emissivity_moment_raw
    )
    scattering_state = limit_nonnegative_frequency_group_p1(
        continuum.electron_scattering_per_cm, scattering_moment_raw
    )
    node_mean = node_mean_grouped.reshape(node_frequency.size, mean.shape[1])
    rates = ground_state_milne_radiative_rates(
        temperature_k,
        node_frequency,
        node_mean,
        frequency_weight_hz=quadrature.node_weight_hz.reshape(-1),
    )
    node_absorption = grouped(node_continuum.true_absorption_total_per_cm)
    node_emissivity = grouped(node_continuum.thermal_emissivity_total_cgs)
    weight_shape = (
        group_count,
        quadrature.order_per_group,
        *([1] * (node_mean_grouped.ndim - 2)),
    )
    node_weight = quadrature.node_weight_hz.reshape(weight_shape)
    absorbed = 4.0 * np.pi * np.sum(
        node_weight * node_absorption * node_mean_grouped,
        axis=(0, 1),
    )
    emitted = 4.0 * np.pi * np.sum(
        node_weight * node_emissivity,
        axis=(0, 1),
    )
    heating = absorbed - emitted
    fields = (absorbed, emitted, heating)
    if not all(np.all(np.isfinite(field)) for field in fields):
        raise ArithmeticError("P1 multigroup radiative exchange became non-finite")
    if np.any(absorbed < 0.0) or np.any(emitted < 0.0):
        raise ArithmeticError("P1 multigroup absorbed/emitted power became negative")
    return GroundStateMilneP1Multigroup(
        quadrature=quadrature,
        continuum=continuum,
        true_absorption_first_moment_per_cm=absorption_state.first_moment_density,
        thermal_emissivity_first_moment_cgs=emissivity_state.first_moment_density,
        electron_scattering_first_moment_per_cm=scattering_state.first_moment_density,
        radiative_rates=rates,
        mean_intensity_cgs=_readonly(np.array(mean, copy=True)),
        mean_intensity_first_moment_cgs=_readonly(np.array(moment, copy=True)),
        absorbed_power_erg_s_cm3=_readonly(np.array(absorbed, copy=True)),
        emitted_power_erg_s_cm3=_readonly(np.array(emitted, copy=True)),
        radiative_heating_erg_s_cm3=_readonly(np.array(heating, copy=True)),
        continuum_limited_group_count=(
            absorption_state.limited_group_count
            + emissivity_state.limited_group_count
            + scattering_state.limited_group_count
        ),
        maximum_continuum_prelimit_realizability_ratio=max(
            absorption_state.maximum_prelimit_realizability_ratio,
            emissivity_state.maximum_prelimit_realizability_ratio,
            scattering_state.maximum_prelimit_realizability_ratio,
        ),
    )


def ground_state_milne_p2_multigroup(
    density_g_cm3: ArrayLike,
    temperature_k: ArrayLike,
    group_edge_hz: ArrayLike,
    group_mean_intensity_cgs: ArrayLike,
    group_first_moment_intensity_cgs: ArrayLike,
    group_second_moment_intensity_cgs: ArrayLike,
    hydrogen_neutral_fraction: ArrayLike,
    hydrogen_ionized_fraction: ArrayLike,
    helium_neutral_fraction: ArrayLike,
    helium_singly_ionized_fraction: ArrayLike,
    helium_doubly_ionized_fraction: ArrayLike,
    *,
    order_per_group: int = 16,
    include_electron_scattering: bool = True,
) -> GroundStateMilneP2Multigroup:
    """计算与组内二次强度一致的 H/He 连续系数、率和能量交换。"""
    quadrature = gauss_legendre_frequency_group_quadrature(
        group_edge_hz, order_per_group=order_per_group
    )
    mean = np.asarray(group_mean_intensity_cgs, dtype=np.float64)
    first = np.asarray(group_first_moment_intensity_cgs, dtype=np.float64)
    second = np.asarray(group_second_moment_intensity_cgs, dtype=np.float64)
    group_count = quadrature.group_width_hz.size
    if (
        mean.ndim != 2
        or first.shape != mean.shape
        or second.shape != mean.shape
        or mean.shape[0] != group_count
    ):
        raise PhysicalDomainError(
            "P2 group intensity must have matching frequency and depth moments"
        )
    input_state = limit_nonnegative_frequency_group_p2(mean, first, second)
    if input_state.limited_group_count != 0:
        raise PhysicalDomainError("P2 radiation input is not realizable")
    node_mean_grouped = group_p2_values_at_quadrature_nodes(
        mean, first, second, quadrature
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
        raise PhysicalDomainError(
            "P2 group intensity depth axis must match the material profiles"
        )
    continuum = _group_continuum(node_continuum, quadrature)

    def grouped(field: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.asarray(field).reshape(
            group_count, quadrature.order_per_group, *field.shape[1:]
        )

    def moments(field: NDArray[np.float64]):
        values = grouped(field)
        return (
            group_p1_moment_from_quadrature_nodes(values, quadrature),
            group_p2_second_moment_from_quadrature_nodes(values, quadrature),
        )

    absorption_first, absorption_second = moments(
        node_continuum.true_absorption_total_per_cm
    )
    emissivity_first, emissivity_second = moments(
        node_continuum.thermal_emissivity_total_cgs
    )
    scattering_first, scattering_second = moments(
        node_continuum.electron_scattering_per_cm
    )
    absorption_state = limit_nonnegative_frequency_group_p2(
        continuum.true_absorption_total_per_cm,
        absorption_first,
        absorption_second,
    )
    emissivity_state = limit_nonnegative_frequency_group_p2(
        continuum.thermal_emissivity_total_cgs,
        emissivity_first,
        emissivity_second,
    )
    scattering_state = limit_nonnegative_frequency_group_p2(
        continuum.electron_scattering_per_cm,
        scattering_first,
        scattering_second,
    )
    node_mean = node_mean_grouped.reshape(node_frequency.size, mean.shape[1])
    rates = ground_state_milne_radiative_rates(
        temperature_k,
        node_frequency,
        node_mean,
        frequency_weight_hz=quadrature.node_weight_hz.reshape(-1),
    )
    node_absorption = grouped(node_continuum.true_absorption_total_per_cm)
    node_emissivity = grouped(node_continuum.thermal_emissivity_total_cgs)
    weight_shape = (
        group_count,
        quadrature.order_per_group,
        *([1] * (node_mean_grouped.ndim - 2)),
    )
    node_weight = quadrature.node_weight_hz.reshape(weight_shape)
    absorbed = 4.0 * np.pi * np.sum(
        node_weight * node_absorption * node_mean_grouped,
        axis=(0, 1),
    )
    emitted = 4.0 * np.pi * np.sum(
        node_weight * node_emissivity,
        axis=(0, 1),
    )
    heating = absorbed - emitted
    if not all(
        np.all(np.isfinite(field)) for field in (absorbed, emitted, heating)
    ):
        raise ArithmeticError("P2 multigroup radiative exchange became non-finite")
    if np.any(absorbed < 0.0) or np.any(emitted < 0.0):
        raise ArithmeticError("P2 multigroup absorbed/emitted power became negative")
    return GroundStateMilneP2Multigroup(
        quadrature=quadrature,
        continuum=continuum,
        true_absorption_first_moment_per_cm=(
            absorption_state.first_moment_density
        ),
        true_absorption_second_moment_per_cm=(
            absorption_state.second_moment_density
        ),
        thermal_emissivity_first_moment_cgs=(
            emissivity_state.first_moment_density
        ),
        thermal_emissivity_second_moment_cgs=(
            emissivity_state.second_moment_density
        ),
        electron_scattering_first_moment_per_cm=(
            scattering_state.first_moment_density
        ),
        electron_scattering_second_moment_per_cm=(
            scattering_state.second_moment_density
        ),
        radiative_rates=rates,
        mean_intensity_cgs=_readonly(np.array(mean, copy=True)),
        mean_intensity_first_moment_cgs=_readonly(np.array(first, copy=True)),
        mean_intensity_second_moment_cgs=_readonly(np.array(second, copy=True)),
        absorbed_power_erg_s_cm3=_readonly(np.array(absorbed, copy=True)),
        emitted_power_erg_s_cm3=_readonly(np.array(emitted, copy=True)),
        radiative_heating_erg_s_cm3=_readonly(np.array(heating, copy=True)),
        continuum_limited_group_count=(
            absorption_state.limited_group_count
            + emissivity_state.limited_group_count
            + scattering_state.limited_group_count
        ),
        maximum_continuum_prelimit_negativity_ratio=max(
            absorption_state.maximum_prelimit_negativity_ratio,
            emissivity_state.maximum_prelimit_negativity_ratio,
            scattering_state.maximum_prelimit_negativity_ratio,
        ),
    )
