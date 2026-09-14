"""模形绑定拱点时间钟解析测试。"""

from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.apsidal_time_mapping import (
    SECONDS_PER_DAY,
    apsidal_mode_profile_fingerprint,
    build_mode_matched_apsidal_clock,
)
from eccentric_tde_observer.source import PhysicalDomainError


def profile() -> tuple[np.ndarray, np.ndarray]:
    return np.array([1.0, 1.5, 2.0]), np.array([0.6, 0.4, 0.2])


def test_mode_matched_clock_roundtrips_one_cycle() -> None:
    a, e = profile()
    fingerprint = apsidal_mode_profile_fingerprint(a, e)
    clock = build_mode_matched_apsidal_clock(
        dimensionless_angular_frequency=2.0,
        communication_time_s=100.0,
        eigenmode_profile_fingerprint=fingerprint,
        source_profile_fingerprint=fingerprint,
        reference_time_s=7.0,
        reference_phase_rad=0.3,
    )
    one_cycle_time = 7.0 + 2.0 * np.pi / clock.angular_frequency_s1
    assert clock.wrapped_phase_rad(one_cycle_time) == pytest.approx(0.3)
    phases = np.array([0.3, 1.0, 2.0 * np.pi + 0.3])
    times = clock.time_s_for_unwrapped_phase(phases)
    assert np.allclose(clock.unwrapped_phase_rad(times), phases, rtol=0.0, atol=1e-15)


def test_clock_preserves_frequency_sign() -> None:
    a, e = profile()
    fingerprint = apsidal_mode_profile_fingerprint(a, e)
    clock = build_mode_matched_apsidal_clock(
        dimensionless_angular_frequency=-1.0,
        communication_time_s=SECONDS_PER_DAY,
        eigenmode_profile_fingerprint=fingerprint,
        source_profile_fingerprint=fingerprint,
    )
    assert clock.cycles_per_day == pytest.approx(-1.0 / (2.0 * np.pi))
    assert clock.period_days == pytest.approx(2.0 * np.pi)
    assert clock.unwrapped_phase_rad(SECONDS_PER_DAY) == pytest.approx(-1.0)


def test_constant_e_atlas_profile_is_rejected() -> None:
    a, e = profile()
    mode = apsidal_mode_profile_fingerprint(a, e)
    atlas = apsidal_mode_profile_fingerprint(a, np.full_like(e, e[0]))
    with pytest.raises(PhysicalDomainError, match="different source profile"):
        build_mode_matched_apsidal_clock(
            dimensionless_angular_frequency=1.0,
            communication_time_s=1.0,
            eigenmode_profile_fingerprint=mode,
            source_profile_fingerprint=atlas,
        )


@pytest.mark.parametrize(
    "a,e",
    [
        ([1.0], [0.5]),
        ([1.0, 0.9], [0.5, 0.4]),
        ([1.0, 2.0], [0.5, 1.0]),
        ([1.0, 2.0], [0.5, np.nan]),
    ],
)
def test_invalid_profiles_are_rejected(a: list[float], e: list[float]) -> None:
    with pytest.raises(PhysicalDomainError):
        apsidal_mode_profile_fingerprint(a, e)
