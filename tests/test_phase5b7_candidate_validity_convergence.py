from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from eccentric_tde_observer.apsidal_time_mapping import (
    apsidal_mode_profile_fingerprint,
)
from eccentric_tde_observer.zo_candidate_source import (
    ZOCandidateSourceParameters,
    build_zo_equation_self_consistent_candidate_source,
    candidate_dynamics_profile_fingerprint,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/phase5b7_candidate_validity_convergence.py"
SPEC = importlib.util.spec_from_file_location("phase5b7_candidate_validity", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load Phase 5B7 convergence script")
phase5b7 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = phase5b7
SPEC.loader.exec_module(phase5b7)


def test_native_radial_subsample_uses_only_original_endpoint_complete_nodes() -> None:
    indices = phase5b7.native_radial_indices(256, 65)
    assert indices.size == 65
    assert indices[0] == 0
    assert indices[-1] == 255
    assert np.all(np.diff(indices) > 0)
    assert np.all((indices >= 0) & (indices < 256))
    with pytest.raises(ValueError):
        phase5b7.native_radial_indices(10, 11)


def test_radial_source_subsample_preserves_exact_candidate_nodes() -> None:
    scaled_a = np.linspace(1.0, 2.0, 5)
    eccentricity = np.linspace(0.5, 0.3, 5)
    nonlinearity = np.linspace(-0.3, -0.1, 5)
    model = build_zo_equation_self_consistent_candidate_source(
        ZOCandidateSourceParameters(
            black_hole_mass_msun=1.0e6,
            stellar_mass_msun=1.0,
            stellar_radius_rsun=1.0,
            circularization_efficiency=0.01,
            opacity_cm2_g=0.34,
        ),
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
        anomaly_points=32,
    )
    indices = np.array([0, 2, 4])
    subset = phase5b7.subsample_radial_source(
        model.source, indices, label="unit-test subset"
    )
    assert np.array_equal(
        subset.semimajor_axis_cm, model.source.semimajor_axis_cm[indices]
    )
    assert np.array_equal(subset.jacobian, model.source.jacobian[indices])
    assert np.array_equal(
        subset.eccentricity_gradient_per_cm,
        model.source.eccentricity_gradient_per_cm[indices],
    )
    assert subset.label.startswith("[A-convergence]")


def test_change_ledger_reports_absolute_and_relative_values() -> None:
    change = phase5b7._absolute_or_relative_change(
        {"metric": 0.008}, {"metric": 0.0084}, "metric"
    )
    assert np.isclose(change["absolute_change"], 4.0e-4)
    assert np.isclose(change["relative_change"], 4.0e-4 / 0.0084)
    zero = phase5b7._absolute_or_relative_change(
        {"metric": 0.0}, {"metric": 0.0}, "metric"
    )
    assert zero["relative_change"] == 0.0


def test_generated_phase5b7_report_closes_only_explicit_candidate_gate() -> None:
    report_path = (
        ROOT / "outputs/phase5b7_candidate_validity_convergence_report.json"
    )
    if not report_path.exists():
        pytest.skip("Phase 5B7 numerical outputs have not been generated yet")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["gate_checks"]["all_finest_working_thresholds_passed"]
    assert report["gate_checks"]["all_conservative_stability_gates_passed"]
    assert report["gate_checks"]["candidate_validity_convergence_closed"]
    assert not report["gate_checks"]["published_benchmark_gate"]
    assert report["scan"]["radial_interpolation"] is False
    assert report["scan"]["separate_adaptive_triangle_subdivision"] is False
