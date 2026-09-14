"""规定热辐射场到 H/He 基态光致电离率的受控接口。

本模块只把给定的 ``J_nu = W B_nu(T_rad)`` 映射为 H I、He I、He II
光致电离率。它不求辐射转移、不更新气体温度，也不把规定场称为自洽 NLTE 辐射场。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .atomic_continuum import (
    EV_ERG,
    H_HE_GROUND_STATE_PHOTOIONIZATION_FITS,
    photoionization_rate_from_fit_s1,
)
from .radiation import PLANCK_ERG_S, planck_nu
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


def edge_resolved_photoionization_energy_grid_ev(
    minimum_energy_ev: float,
    maximum_energy_ev: float,
    base_points: int,
) -> NDArray[np.float64]:
    """构造显式包含三条 H/He 电离边的对数能量网格。"""
    minimum = float(minimum_energy_ev)
    maximum = float(maximum_energy_ev)
    if (
        not np.isfinite(minimum)
        or not np.isfinite(maximum)
        or minimum <= 0.0
        or maximum <= minimum
    ):
        raise PhysicalDomainError(
            "photoionization energy bounds must be finite, positive and ordered"
        )
    if not isinstance(base_points, (int, np.integer)) or int(base_points) < 2:
        raise PhysicalDomainError("base_points must be an integer of at least two")
    maximum_fit_energy = min(
        fit.maximum_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
    )
    if maximum > maximum_fit_energy:
        raise PhysicalDomainError(
            "photoionization energy grid exceeds the common Verner fit domain"
        )
    base = np.geomspace(minimum, maximum, int(base_points))
    thresholds = np.array(
        [fit.threshold_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS],
        dtype=np.float64,
    )
    active = thresholds[(thresholds >= minimum) & (thresholds <= maximum)]
    # 中文：离化边必须作为精确节点，不能让梯形积分跨越截面不连续点。
    energy = np.unique(np.concatenate((base, active)))
    return _readonly(energy)


@dataclass(frozen=True)
class PrescribedPlanckPhotoionizationRates:
    """逐相位规定 Planck 场及其三条基态光致电离率。"""

    radiation_temperature_k: NDArray[np.float64]
    dilution_factor: NDArray[np.float64]
    energy_ev: NDArray[np.float64]
    frequency_hz: NDArray[np.float64]
    photoionization_s1: NDArray[np.float64]


def prescribed_planck_photoionization_rates_s1(
    radiation_temperature_k: ArrayLike,
    dilution_factor: ArrayLike,
    energy_ev: ArrayLike,
) -> PrescribedPlanckPhotoionizationRates:
    """计算 ``J_nu=W B_nu(T_rad)`` 对应的 H/He 基态光致电离率。"""
    temperature, dilution = np.broadcast_arrays(
        np.asarray(radiation_temperature_k, dtype=np.float64),
        np.asarray(dilution_factor, dtype=np.float64),
    )
    if temperature.ndim != 1 or temperature.size < 1:
        raise PhysicalDomainError("prescribed radiation orbit must be a non-empty 1D array")
    if not np.all(np.isfinite(temperature)) or np.any(temperature <= 0.0):
        raise PhysicalDomainError(
            "radiation_temperature_k must be finite and strictly positive"
        )
    if not np.all(np.isfinite(dilution)) or np.any(dilution < 0.0):
        raise PhysicalDomainError("dilution_factor must be finite and non-negative")
    energy = np.array(energy_ev, dtype=np.float64, copy=True)
    if (
        energy.ndim != 1
        or energy.size < 2
        or not np.all(np.isfinite(energy))
        or np.any(energy <= 0.0)
        or np.any(np.diff(energy) <= 0.0)
    ):
        raise PhysicalDomainError(
            "energy_ev must be a finite, positive and strictly increasing 1D grid"
        )
    maximum_fit_energy = min(
        fit.maximum_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
    )
    if energy[-1] > maximum_fit_energy:
        raise PhysicalDomainError("energy_ev exceeds the common Verner fit domain")
    for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS:
        if np.count_nonzero(energy >= fit.threshold_energy_ev) < 2:
            raise PhysicalDomainError(
                f"energy_ev needs at least two points at or above the {fit.ion_label} edge"
            )

    frequency = energy * EV_ERG / PLANCK_ERG_S
    rates = np.empty((temperature.size, 3), dtype=np.float64)
    for phase, (radiation_temperature, weight) in enumerate(
        zip(temperature, dilution, strict=True)
    ):
        planck = planck_nu(frequency, radiation_temperature)
        # 中文：W 只线性缩放规定平均强度；零场因此严格给出零光致电离率。
        for species, fit in enumerate(H_HE_GROUND_STATE_PHOTOIONIZATION_FITS):
            rates[phase, species] = weight * photoionization_rate_from_fit_s1(
                frequency, planck, fit
            )
    if not np.all(np.isfinite(rates)) or np.any(rates < 0.0):
        raise ArithmeticError("prescribed photoionization rates became invalid")
    return PrescribedPlanckPhotoionizationRates(
        radiation_temperature_k=_readonly(np.array(temperature, copy=True)),
        dilution_factor=_readonly(np.array(dilution, copy=True)),
        energy_ev=_readonly(energy),
        frequency_hz=_readonly(frequency),
        photoionization_s1=_readonly(rates),
    )
