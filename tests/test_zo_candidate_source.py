from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.apsidal_time_mapping import (
    apsidal_mode_profile_fingerprint,
)
from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.source import PhysicalDomainError
from eccentric_tde_observer.validity import audit_local_vertical_domain
from eccentric_tde_observer.zo_candidate_source import (
    ZOCandidateSourceParameters,
    build_zo_equation_self_consistent_candidate_source,
    candidate_dynamics_profile_fingerprint,
)
from eccentric_tde_observer.zo_reference import (
    ZOConstantEParameters,
    build_zo_constant_e_reference_model,
)


def _parameters() -> ZOCandidateSourceParameters:
    return ZOCandidateSourceParameters(
        black_hole_mass_msun=1.0e6,
        stellar_mass_msun=1.0,
        stellar_radius_rsun=1.0,
        circularization_efficiency=0.01,
        opacity_cm2_g=0.34,
    )


def _build(
    scaled_a: np.ndarray,
    eccentricity: np.ndarray,
    nonlinearity: np.ndarray,
    *,
    anomaly_points: int = 32,
):
    return build_zo_equation_self_consistent_candidate_source(
        _parameters(),
        scaled_semimajor_axis=scaled_a,
        eccentricity=eccentricity,
        orbital_nonlinearity=nonlinearity,
        expected_eccentricity_profile_fingerprint=(
            apsidal_mode_profile_fingerprint(scaled_a, eccentricity)
        ),
        expected_dynamics_profile_fingerprint=(
            candidate_dynamics_profile_fingerprint(
                scaled_a, eccentricity, nonlinearity
            )
        ),
        anomaly_points=anomaly_points,
        candidate_label="unit-test candidate",
    )


def test_candidate_builder_binds_both_eccentricity_and_dynamics_profiles() -> None:
    scaled_a = np.array([1.0, 1.5, 2.0])
    eccentricity = np.array([0.6, 0.45, 0.3])
    nonlinearity = np.array([-0.4, -0.3, -0.2])
    e_digest = apsidal_mode_profile_fingerprint(scaled_a, eccentricity)
    dynamics_digest = candidate_dynamics_profile_fingerprint(
        scaled_a, eccentricity, nonlinearity
    )
    changed_e = eccentricity.copy()
    changed_e[1] = np.nextafter(changed_e[1], np.inf)
    with pytest.raises(PhysicalDomainError, match="eccentricity profile"):
        build_zo_equation_self_consistent_candidate_source(
            _parameters(),
            scaled_semimajor_axis=scaled_a,
            eccentricity=changed_e,
            orbital_nonlinearity=nonlinearity,
            expected_eccentricity_profile_fingerprint=e_digest,
            expected_dynamics_profile_fingerprint=dynamics_digest,
            anomaly_points=32,
        )
    changed_q = nonlinearity.copy()
    changed_q[1] = np.nextafter(changed_q[1], np.inf)
    with pytest.raises(PhysicalDomainError, match="dynamics profile"):
        build_zo_equation_self_consistent_candidate_source(
            _parameters(),
            scaled_semimajor_axis=scaled_a,
            eccentricity=eccentricity,
            orbital_nonlinearity=changed_q,
            expected_eccentricity_profile_fingerprint=e_digest,
            expected_dynamics_profile_fingerprint=dynamics_digest,
            anomaly_points=32,
        )


def test_candidate_builder_recovers_f_and_eq31_without_differentiation() -> None:
    scaled_a = np.array([1.0, 1.5, 2.0])
    eccentricity = np.array([0.6, 0.45, 0.3])
    nonlinearity = np.array([-0.4, -0.3, -0.2])
    model = _build(scaled_a, eccentricity, nonlinearity)
    expected_f = (nonlinearity + eccentricity) / (
        1.0 + nonlinearity * eccentricity
    )
    assert np.array_equal(model.eccentricity_plus_gradient, expected_f)
    reconstructed_q = (expected_f - eccentricity) / (
        1.0 - eccentricity * expected_f
    )
    assert np.allclose(reconstructed_q, nonlinearity, rtol=2.0e-15)
    expected_j_at_pericentre = (
        1.0
        - eccentricity * expected_f
        - (expected_f - eccentricity)
    ) / np.sqrt(1.0 - eccentricity**2)
    assert np.allclose(
        model.source.jacobian[:, 0], expected_j_at_pericentre, rtol=2.0e-15
    )
    assert model.source.has_independent_nesting_check


def test_constant_e_limit_matches_unchanged_reference_control() -> None:
    scaled_a = np.array([1.0, 2.0])
    eccentricity = np.full(2, 0.6)
    nonlinearity = np.zeros(2)
    candidate = _build(scaled_a, eccentricity, nonlinearity, anomaly_points=64)
    control = build_zo_constant_e_reference_model(
        ZOConstantEParameters(
            black_hole_mass_msun=1.0e6,
            stellar_mass_msun=1.0,
            stellar_radius_rsun=1.0,
            circularization_efficiency=0.01,
            outer_to_inner_semimajor_axis=2.0,
            eccentricity=0.6,
            opacity_cm2_g=0.34,
        ),
        radial_points=2,
        anomaly_points=64,
    )
    for candidate_field, control_field in (
        (candidate.source.jacobian, control.source.jacobian),
        (
            candidate.source.surface_density_g_cm2,
            control.source.surface_density_g_cm2,
        ),
        (candidate.source.scale_height_cm, control.source.scale_height_cm),
        (
            candidate.source.effective_temperature_k,
            control.source.effective_temperature_k,
        ),
    ):
        assert np.allclose(candidate_field, control_field, rtol=3.0e-11)
    assert control.source.label == "ZO 2020 constant-e reference model"
    assert candidate.published_benchmark is False
    assert candidate.classification == "[A-candidate]+[V]+[O]"


def test_candidate_runs_through_generic_validity_interface() -> None:
    model = _build(
        np.array([1.0, 1.5, 2.0]),
        np.array([0.6, 0.45, 0.3]),
        np.array([-0.4, -0.3, -0.2]),
        anomaly_points=64,
    )
    photosphere = solve_gray_photosphere(
        model.source, model.parameters.opacity_cm2_g
    )
    audit = audit_local_vertical_domain(
        model.source, photosphere, ratio_thresholds=(0.3, 1.0)
    )
    assert audit.oriented_single_valued_surface_graph
    assert np.all(
        (audit.corrected_photosphere_over_radius_fraction_above >= 0.0)
        & (audit.corrected_photosphere_over_radius_fraction_above <= 1.0)
    )


def test_candidate_rejects_non_nested_profile_without_repair() -> None:
    scaled_a = np.array([1.0, 2.0])
    eccentricity = np.array([0.6, 0.5])
    nonlinearity = np.array([1.0, 0.0])
    with pytest.raises(PhysicalDomainError, match=r"\|q\| < 1"):
        candidate_dynamics_profile_fingerprint(
            scaled_a, eccentricity, nonlinearity
        )
