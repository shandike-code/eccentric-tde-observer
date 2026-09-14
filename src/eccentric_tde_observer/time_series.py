"""进动相位图谱到可观测光变和理想带通量的确定性映射。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .source import PhysicalDomainError


AB_ZERO_POINT_FNU_CGS = 3631.0e-23


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class Bandpass:
    """无量纲响应曲线；频率轴必须递增并完整位于模型谱内。"""

    name: str
    frequency_hz: ArrayLike
    response: ArrayLike

    def __post_init__(self) -> None:
        name = str(self.name).strip()
        frequency = np.array(self.frequency_hz, dtype=np.float64, copy=True)
        response = np.array(self.response, dtype=np.float64, copy=True)
        if not name:
            raise PhysicalDomainError("bandpass name must be non-empty")
        if frequency.ndim != 1 or frequency.size < 2:
            raise PhysicalDomainError("bandpass frequency must have at least two points")
        if response.shape != frequency.shape:
            raise PhysicalDomainError("bandpass response must match frequency axis")
        if not np.all(np.isfinite(frequency)) or np.any(frequency <= 0.0) or np.any(np.diff(frequency) <= 0.0):
            raise PhysicalDomainError("bandpass frequency must be finite, positive and increasing")
        if not np.all(np.isfinite(response)) or np.any(response < 0.0) or not np.any(response > 0.0):
            raise PhysicalDomainError("bandpass response must be finite, non-negative and nonzero")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "frequency_hz", _readonly(frequency))
        object.__setattr__(self, "response", _readonly(response))


def ideal_log_tophat_bandpass(name: str, lower_hz: float, upper_hz: float, points: int = 65) -> Bandpass:
    """Build an ideal diagnostic band, explicitly not an instrument response."""
    lower = float(lower_hz)
    upper = float(upper_hz)
    if not np.isfinite(lower) or not np.isfinite(upper) or lower <= 0.0 or upper <= lower:
        raise PhysicalDomainError("ideal band limits must satisfy 0 < lower < upper")
    if not isinstance(points, (int, np.integer)) or int(points) < 2:
        raise PhysicalDomainError("points must be an integer at least two")
    frequency = np.geomspace(lower, upper, int(points))
    return Bandpass(name, frequency, np.ones(int(points), dtype=np.float64))


def photon_counting_mean_fnu(
    spectrum_frequency_hz: ArrayLike,
    flux_density_cgs: ArrayLike,
    bandpass: Bandpass,
) -> NDArray[np.float64]:
    """Return the AB-compatible photon-counting mean ``f_nu``.

    For a response per detected photon,
    ``<f_nu> = integral f_nu R dnu/nu / integral R dnu/nu``.
    A constant ``f_nu`` is therefore recovered exactly.
    """
    frequency = np.asarray(spectrum_frequency_hz, dtype=np.float64)
    flux = np.asarray(flux_density_cgs, dtype=np.float64)
    if frequency.ndim != 1 or frequency.size < 2:
        raise PhysicalDomainError("spectrum frequency must be a 1D grid")
    if flux.shape[-1] != frequency.size:
        raise PhysicalDomainError("last flux axis must match spectrum frequency")
    if not np.all(np.isfinite(frequency)) or np.any(frequency <= 0.0) or np.any(np.diff(frequency) <= 0.0):
        raise PhysicalDomainError("spectrum frequency must be finite, positive and increasing")
    if not np.all(np.isfinite(flux)) or np.any(flux < 0.0):
        raise PhysicalDomainError("flux density must be finite and non-negative")
    if bandpass.frequency_hz[0] < frequency[0] or bandpass.frequency_hz[-1] > frequency[-1]:
        raise PhysicalDomainError("spectrum does not cover the complete bandpass")
    flattened = flux.reshape(-1, frequency.size)
    interpolated = np.empty((flattened.shape[0], bandpass.frequency_hz.size))
    for index, row in enumerate(flattened):
        interpolated[index] = np.interp(bandpass.frequency_hz, frequency, row)
    # 中文：光子计数响应的 AB 平均含 1/nu 权重，常数 f_nu 必须被严格回收。
    weight = bandpass.response / bandpass.frequency_hz
    denominator = float(np.trapezoid(weight, bandpass.frequency_hz))
    result = np.trapezoid(
        interpolated * weight[None, :], bandpass.frequency_hz, axis=1
    ) / denominator
    result = result.reshape(flux.shape[:-1])
    if not np.all(np.isfinite(result)) or np.any(result < 0.0):
        raise ArithmeticError("bandpass integration became invalid")
    return _readonly(result)


def ab_magnitude_from_fnu(flux_density_cgs: ArrayLike) -> NDArray[np.float64]:
    """Convert positive mean ``f_nu`` to AB magnitude."""
    flux = np.asarray(flux_density_cgs, dtype=np.float64)
    if not np.all(np.isfinite(flux)) or np.any(flux <= 0.0):
        raise PhysicalDomainError("AB magnitude requires finite, positive f_nu")
    magnitude = -2.5 * np.log10(flux / AB_ZERO_POINT_FNU_CGS)
    return _readonly(magnitude)


@dataclass(frozen=True)
class PeriodicPhaseSpectralAtlas:
    """端点不重复的周期相位—频率通量表。"""

    relative_phase_rad: ArrayLike
    frequency_hz: ArrayLike
    flux_density_cgs: ArrayLike

    def __post_init__(self) -> None:
        phase = np.array(self.relative_phase_rad, dtype=np.float64, copy=True)
        frequency = np.array(self.frequency_hz, dtype=np.float64, copy=True)
        flux = np.array(self.flux_density_cgs, dtype=np.float64, copy=True)
        if phase.ndim != 1 or phase.size < 4 or phase[0] < 0.0 or phase[-1] >= 2.0 * np.pi or np.any(np.diff(phase) <= 0.0):
            raise PhysicalDomainError("phase grid must be increasing in [0,2pi) with at least four points")
        if frequency.ndim != 1 or frequency.size < 2 or np.any(frequency <= 0.0) or np.any(np.diff(frequency) <= 0.0):
            raise PhysicalDomainError("frequency grid must be positive and increasing")
        if flux.shape != (phase.size, frequency.size):
            raise PhysicalDomainError("flux atlas shape must be (phase, frequency)")
        if not np.all(np.isfinite(flux)) or np.any(flux < 0.0):
            raise PhysicalDomainError("flux atlas must be finite and non-negative")
        object.__setattr__(self, "relative_phase_rad", _readonly(phase))
        object.__setattr__(self, "frequency_hz", _readonly(frequency))
        object.__setattr__(self, "flux_density_cgs", _readonly(flux))

    def sample(self, relative_phase_rad: ArrayLike) -> NDArray[np.float64]:
        """Periodically interpolate spectra without inferring a precession rate."""
        query = np.asarray(relative_phase_rad, dtype=np.float64)
        if not np.all(np.isfinite(query)):
            raise PhysicalDomainError("relative phase query must be finite")
        # 中文：补一个周期端点只为连续插值；存储网格仍保持 [0,2pi) 不重复。
        wrapped = np.mod(query, 2.0 * np.pi)
        phase_extended = np.concatenate(
            (self.relative_phase_rad, [self.relative_phase_rad[0] + 2.0 * np.pi])
        )
        flux_extended = np.concatenate(
            (self.flux_density_cgs, self.flux_density_cgs[:1]), axis=0
        )
        upper = np.searchsorted(phase_extended, wrapped.reshape(-1), side="right")
        lower = upper - 1
        interval = phase_extended[upper] - phase_extended[lower]
        fraction = (wrapped.reshape(-1) - phase_extended[lower]) / interval
        sampled = (
            (1.0 - fraction[:, None]) * flux_extended[lower]
            + fraction[:, None] * flux_extended[upper]
        )
        return _readonly(sampled.reshape(query.shape + (self.frequency_hz.size,)))


def uniform_precession_relative_phase(
    time_days: ArrayLike,
    precession_period_days: float,
    *,
    initial_relative_phase_rad: float = 0.0,
    prograde: bool = True,
) -> NDArray[np.float64]:
    """Map time to phase for an explicitly supplied uniform precession period."""
    time = np.asarray(time_days, dtype=np.float64)
    period = float(precession_period_days)
    initial = float(initial_relative_phase_rad)
    if not np.all(np.isfinite(time)) or not np.isfinite(period) or period <= 0.0 or not np.isfinite(initial):
        raise PhysicalDomainError("time, period and initial phase must be finite; period must be positive")
    # 中文：相对相位是 phi_obs-varpi；顺行进动时随时间递减。
    sign = -1.0 if prograde else 1.0
    phase = np.mod(initial + sign * 2.0 * np.pi * time / period, 2.0 * np.pi)
    return _readonly(phase)


@dataclass(frozen=True)
class PeriodicHarmonics:
    mean: float
    fractional_rms: float
    first_harmonic_fractional_semi_amplitude: float
    second_harmonic_fractional_semi_amplitude: float


def periodic_harmonics(values: ArrayLike) -> PeriodicHarmonics:
    """Summarize a uniformly sampled, endpoint-free periodic light curve."""
    signal = np.asarray(values, dtype=np.float64)
    if signal.ndim != 1 or signal.size < 4 or not np.all(np.isfinite(signal)) or np.any(signal < 0.0):
        raise PhysicalDomainError("periodic signal must be a finite, non-negative 1D array")
    mean = float(np.mean(signal))
    if mean <= 0.0:
        raise PhysicalDomainError("periodic signal mean must be positive")
    # 中文：端点不重复的均匀相位样本可直接做离散傅里叶分解。
    coefficients = np.fft.rfft(signal) / signal.size
    fractional_rms = float(np.std(signal) / mean)
    first = float(2.0 * np.abs(coefficients[1]) / mean)
    second = float(2.0 * np.abs(coefficients[2]) / mean)
    return PeriodicHarmonics(mean, fractional_rms, first, second)
