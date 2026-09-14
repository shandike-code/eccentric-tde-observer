"""Mode-shape-bound apsidal phase-to-time mapping."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .source import PhysicalDomainError


SECONDS_PER_DAY = 86400.0


def apsidal_mode_profile_fingerprint(
    scaled_semimajor_axis: ArrayLike,
    eccentricity: ArrayLike,
) -> str:
    """Return an exact binary64 fingerprint for one radial eccentricity profile."""
    semimajor = np.asarray(scaled_semimajor_axis, dtype=np.float64)
    ecc = np.asarray(eccentricity, dtype=np.float64)
    if (
        semimajor.ndim != 1
        or ecc.ndim != 1
        or semimajor.shape != ecc.shape
        or semimajor.size < 2
        or np.any(~np.isfinite(semimajor))
        or np.any(~np.isfinite(ecc))
        or np.any(np.diff(semimajor) <= 0.0)
        or np.any(ecc < 0.0)
        or np.any(ecc >= 1.0)
    ):
        raise PhysicalDomainError("apsidal mode profile is invalid")
    digest = hashlib.sha256()
    digest.update(np.asarray([semimajor.size], dtype="<i8").tobytes())
    digest.update(np.asarray(semimajor, dtype="<f8").tobytes())
    digest.update(np.asarray(ecc, dtype="<f8").tobytes())
    return digest.hexdigest()


@dataclass(frozen=True)
class ModeMatchedApsidalClock:
    """A physical clock tied to one exact eccentricity-mode profile."""

    dimensionless_angular_frequency: float
    communication_time_s: float
    profile_fingerprint: str
    reference_time_s: float = 0.0
    reference_phase_rad: float = 0.0

    def __post_init__(self) -> None:
        frequency = float(self.dimensionless_angular_frequency)
        communication = float(self.communication_time_s)
        reference_time = float(self.reference_time_s)
        reference_phase = float(self.reference_phase_rad)
        if (
            not np.isfinite(frequency)
            or frequency == 0.0
            or not np.isfinite(communication)
            or communication <= 0.0
            or not np.isfinite(reference_time)
            or not np.isfinite(reference_phase)
            or len(self.profile_fingerprint) != 64
        ):
            raise PhysicalDomainError("apsidal clock parameters are invalid")

    @property
    def angular_frequency_s1(self) -> float:
        return self.dimensionless_angular_frequency / self.communication_time_s

    @property
    def cycles_per_day(self) -> float:
        return self.angular_frequency_s1 * SECONDS_PER_DAY / (2.0 * np.pi)

    @property
    def period_days(self) -> float:
        return 1.0 / abs(self.cycles_per_day)

    def unwrapped_phase_rad(self, time_s: ArrayLike) -> NDArray[np.float64]:
        time = np.asarray(time_s, dtype=np.float64)
        if np.any(~np.isfinite(time)):
            raise PhysicalDomainError("apsidal evaluation time is invalid")
        return np.asarray(
            self.reference_phase_rad
            + self.angular_frequency_s1 * (time - self.reference_time_s),
            dtype=np.float64,
        )

    def wrapped_phase_rad(self, time_s: ArrayLike) -> NDArray[np.float64]:
        return np.mod(self.unwrapped_phase_rad(time_s), 2.0 * np.pi)

    def time_s_for_unwrapped_phase(self, phase_rad: ArrayLike) -> NDArray[np.float64]:
        phase = np.asarray(phase_rad, dtype=np.float64)
        if np.any(~np.isfinite(phase)):
            raise PhysicalDomainError("apsidal target phase is invalid")
        return np.asarray(
            self.reference_time_s
            + (phase - self.reference_phase_rad) / self.angular_frequency_s1,
            dtype=np.float64,
        )


def build_mode_matched_apsidal_clock(
    *,
    dimensionless_angular_frequency: float,
    communication_time_s: float,
    eigenmode_profile_fingerprint: str,
    source_profile_fingerprint: str,
    reference_time_s: float = 0.0,
    reference_phase_rad: float = 0.0,
) -> ModeMatchedApsidalClock:
    """Build a clock only when the source and eigenmode radial profiles match exactly."""
    # 中文：时间频率必须与生成观察者源的同一条 e(a) 模形绑定。
    if source_profile_fingerprint != eigenmode_profile_fingerprint:
        raise PhysicalDomainError(
            "apsidal eigenfrequency cannot time-label a different source profile"
        )
    return ModeMatchedApsidalClock(
        dimensionless_angular_frequency=dimensionless_angular_frequency,
        communication_time_s=communication_time_s,
        profile_fingerprint=eigenmode_profile_fingerprint,
        reference_time_s=reference_time_s,
        reference_phase_rad=reference_phase_rad,
    )
