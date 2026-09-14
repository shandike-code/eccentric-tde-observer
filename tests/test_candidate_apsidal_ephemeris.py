"""方程自洽候选拱点历表的解析与拒绝门测试。"""

from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.apsidal_time_mapping import (
    SECONDS_PER_DAY,
    apsidal_mode_profile_fingerprint,
)
from eccentric_tde_observer.candidate_apsidal_ephemeris import (
    build_validated_candidate_apsidal_ephemeris,
)
from eccentric_tde_observer.source import PhysicalDomainError
from eccentric_tde_observer.zo_candidate_source import (
    candidate_dynamics_profile_fingerprint,
)


def _profiles() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.array([1.0, 1.5, 2.0]),
        np.array([0.6, 0.4, 0.2]),
        np.array([-0.5, -0.4, -0.3]),
    )


def _build():
    semimajor, eccentricity, nonlinearity = _profiles()
    e_digest = apsidal_mode_profile_fingerprint(semimajor, eccentricity)
    dynamics_digest = candidate_dynamics_profile_fingerprint(
        semimajor, eccentricity, nonlinearity
    )
    return build_validated_candidate_apsidal_ephemeris(
        dimensionless_angular_frequency=2.0,
        communication_time_s=100.0 * SECONDS_PER_DAY,
        eigenmode_eccentricity_profile_fingerprint=e_digest,
        source_eccentricity_profile_fingerprint=e_digest,
        eigenmode_dynamics_profile_fingerprint=dynamics_digest,
        source_dynamics_profile_fingerprint=dynamics_digest,
        candidate_validity_convergence_closed=True,
    )


def test_candidate_ephemeris_roundtrips_relative_time_and_phase() -> None:
    ephemeris = _build()
    phases = np.array([0.0, 0.5, 2.0 * np.pi])
    days = ephemeris.relative_time_days_for_unwrapped_phase(phases)
    recovered = ephemeris.unwrapped_phase_rad_for_relative_time_days(days)
    assert np.allclose(recovered, phases, rtol=0.0, atol=1.0e-15)
    assert ephemeris.period_days == pytest.approx(100.0 * np.pi)
    assert ephemeris.signed_degrees_per_day == pytest.approx(360.0 / (100.0 * np.pi))
    assert ephemeris.published_benchmark is False


def test_candidate_ephemeris_rejects_different_q_profile() -> None:
    semimajor, eccentricity, nonlinearity = _profiles()
    e_digest = apsidal_mode_profile_fingerprint(semimajor, eccentricity)
    dynamics_digest = candidate_dynamics_profile_fingerprint(
        semimajor, eccentricity, nonlinearity
    )
    changed_q = nonlinearity.copy()
    changed_q[1] = np.nextafter(changed_q[1], np.inf)
    changed_digest = candidate_dynamics_profile_fingerprint(
        semimajor, eccentricity, changed_q
    )
    with pytest.raises(PhysicalDomainError, match="different dynamics profile"):
        build_validated_candidate_apsidal_ephemeris(
            dimensionless_angular_frequency=1.0,
            communication_time_s=SECONDS_PER_DAY,
            eigenmode_eccentricity_profile_fingerprint=e_digest,
            source_eccentricity_profile_fingerprint=e_digest,
            eigenmode_dynamics_profile_fingerprint=dynamics_digest,
            source_dynamics_profile_fingerprint=changed_digest,
            candidate_validity_convergence_closed=True,
        )


@pytest.mark.parametrize(
    "validity_closed,published_claim,match",
    [
        (False, False, "validity convergence"),
        (True, True, "published benchmark"),
    ],
)
def test_candidate_ephemeris_rejects_unclosed_claims(
    validity_closed: bool, published_claim: bool, match: str
) -> None:
    semimajor, eccentricity, nonlinearity = _profiles()
    e_digest = apsidal_mode_profile_fingerprint(semimajor, eccentricity)
    dynamics_digest = candidate_dynamics_profile_fingerprint(
        semimajor, eccentricity, nonlinearity
    )
    with pytest.raises(PhysicalDomainError, match=match):
        build_validated_candidate_apsidal_ephemeris(
            dimensionless_angular_frequency=1.0,
            communication_time_s=SECONDS_PER_DAY,
            eigenmode_eccentricity_profile_fingerprint=e_digest,
            source_eccentricity_profile_fingerprint=e_digest,
            eigenmode_dynamics_profile_fingerprint=dynamics_digest,
            source_dynamics_profile_fingerprint=dynamics_digest,
            candidate_validity_convergence_closed=validity_closed,
            published_benchmark_claim=published_claim,
        )
