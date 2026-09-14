"""Validated relative-time ephemeris for one equation-consistent ZO candidate."""

from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .apsidal_time_mapping import (
    SECONDS_PER_DAY,
    ModeMatchedApsidalClock,
    build_mode_matched_apsidal_clock,
)
from .source import PhysicalDomainError


_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def _require_sha256(name: str, value: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise PhysicalDomainError(f"{name} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True)
class ValidatedCandidateApsidalEphemeris:
    """A relative physical clock bound to one valid candidate dynamics profile.

    The clock is an ``[A-candidate]`` result.  It is deliberately not an
    absolute calendar ephemeris and not a published ZO benchmark.
    """

    clock: ModeMatchedApsidalClock
    dynamics_profile_fingerprint: str
    candidate_validity_convergence_closed: bool
    published_benchmark: bool = False
    classification: str = "[A-candidate]+[V]+[O]"

    def __post_init__(self) -> None:
        if not isinstance(self.clock, ModeMatchedApsidalClock):
            raise TypeError("clock must be a ModeMatchedApsidalClock")
        _require_sha256(
            "dynamics_profile_fingerprint", self.dynamics_profile_fingerprint
        )
        if self.candidate_validity_convergence_closed is not True:
            raise PhysicalDomainError(
                "candidate validity convergence must be closed before time mapping"
            )
        if self.published_benchmark is not False:
            raise PhysicalDomainError(
                "equation-consistent candidate cannot be relabelled as a published benchmark"
            )

    @property
    def period_days(self) -> float:
        return self.clock.period_days

    @property
    def signed_cycles_per_day(self) -> float:
        return self.clock.cycles_per_day

    @property
    def signed_degrees_per_day(self) -> float:
        return 360.0 * self.signed_cycles_per_day

    def relative_time_days_for_unwrapped_phase(
        self, phase_rad: ArrayLike
    ) -> NDArray[np.float64]:
        """Return time relative to the clock reference epoch in days."""
        absolute_time_s = self.clock.time_s_for_unwrapped_phase(phase_rad)
        return np.asarray(
            (absolute_time_s - self.clock.reference_time_s) / SECONDS_PER_DAY,
            dtype=np.float64,
        )

    def unwrapped_phase_rad_for_relative_time_days(
        self, relative_time_days: ArrayLike
    ) -> NDArray[np.float64]:
        """Return unwrapped phase for a relative elapsed time in days."""
        elapsed_days = np.asarray(relative_time_days, dtype=np.float64)
        if np.any(~np.isfinite(elapsed_days)):
            raise PhysicalDomainError("candidate relative time is invalid")
        absolute_time_s = (
            self.clock.reference_time_s + elapsed_days * SECONDS_PER_DAY
        )
        return self.clock.unwrapped_phase_rad(absolute_time_s)


def build_validated_candidate_apsidal_ephemeris(
    *,
    dimensionless_angular_frequency: float,
    communication_time_s: float,
    eigenmode_eccentricity_profile_fingerprint: str,
    source_eccentricity_profile_fingerprint: str,
    eigenmode_dynamics_profile_fingerprint: str,
    source_dynamics_profile_fingerprint: str,
    candidate_validity_convergence_closed: bool,
    published_benchmark_claim: bool = False,
    reference_time_s: float = 0.0,
    reference_phase_rad: float = 0.0,
) -> ValidatedCandidateApsidalEphemeris:
    """Build a candidate clock only after exact source and validity gates close."""
    expected_dynamics = _require_sha256(
        "eigenmode_dynamics_profile_fingerprint",
        eigenmode_dynamics_profile_fingerprint,
    )
    actual_dynamics = _require_sha256(
        "source_dynamics_profile_fingerprint",
        source_dynamics_profile_fingerprint,
    )
    # 中文：频率不仅绑定 e(a)，也绑定决定几何与呼吸解的 q(a)。
    if actual_dynamics != expected_dynamics:
        raise PhysicalDomainError(
            "apsidal eigenfrequency cannot time-label a different dynamics profile"
        )
    if candidate_validity_convergence_closed is not True:
        raise PhysicalDomainError(
            "candidate validity convergence must be closed before time mapping"
        )
    if published_benchmark_claim is not False:
        raise PhysicalDomainError(
            "published benchmark claim is not authorized for this candidate"
        )
    clock = build_mode_matched_apsidal_clock(
        dimensionless_angular_frequency=dimensionless_angular_frequency,
        communication_time_s=communication_time_s,
        eigenmode_profile_fingerprint=eigenmode_eccentricity_profile_fingerprint,
        source_profile_fingerprint=source_eccentricity_profile_fingerprint,
        reference_time_s=reference_time_s,
        reference_phase_rad=reference_phase_rad,
    )
    return ValidatedCandidateApsidalEphemeris(
        clock=clock,
        dynamics_profile_fingerprint=expected_dynamics,
        candidate_validity_convergence_closed=True,
        published_benchmark=False,
    )
