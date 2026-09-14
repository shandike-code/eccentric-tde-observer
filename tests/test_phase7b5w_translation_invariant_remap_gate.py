import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
PROTOCOL = OUTPUT / "phase7b5w_preregistered_translation_invariant_remap.json"
SUMMARY = OUTPUT / "phase7b5w_translation_invariant_remap_summary.json"
EXPECTED_PROTOCOL_SHA256 = (
    "8bc2abc306eee0797934395d42b4b23a4fa1ff18ac4674acd4b05c79afdec6cb"
)


def _summary():
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_phase7b5w_protocol_is_frozen_and_retains_old_failure():
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == (
        EXPECTED_PROTOCOL_SHA256
    )
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["retained_failure"]["maximum_relative_intensity_error"] == (
        pytest.approx(3.937747943835367e-12)
    )
    assert protocol["candidate"]["global_frequency_edges_changed"] is False
    assert protocol["candidate"]["posthoc_tolerance_change"] is False
    assert protocol["authorization"]["full_orbit_authorized"] is False


def test_phase7b5w_translation_invariance_and_actual_one_map_are_exact():
    report = _summary()
    assert report["synthetic_slice_invariance"]["maximum_relative_error"] == 0.0
    assert report["synthetic_slice_invariance"]["bitwise_equal"] is True
    assert report["actual_one_iteration_error"] == 0.0


def test_phase7b5w_streamed_fixed_point_is_bitwise_equivalent():
    report = _summary()
    mono = report["runs"]["monolithic"]
    stream = report["runs"]["stream256"]
    assert mono["fixed_point_iterations"] == stream["fixed_point_iterations"] == 35
    assert mono["fixed_point_converged"] and stream["fixed_point_converged"]
    assert mono["final_intensity_sha256"] == stream["final_intensity_sha256"]
    comparison = report["streamed_fixed_point_comparison"]
    assert comparison["maximum_error"] == 0.0
    assert all(value == 0.0 for value in comparison["errors"].values())


def test_phase7b5w_resources_and_authorization_are_bounded():
    report = _summary()
    assert report["runs"]["stream256"]["peak_process_rss_mib"] < 6144.0
    assert report["runs"]["stream256"]["peak_process_rss_mib"] < (
        report["runs"]["monolithic"]["peak_process_rss_mib"]
    )
    decision = report["decision"]
    assert decision["phase7b5w_gate_passed"] is True
    assert decision["full_depth_block_resource_probe_authorized"] is True
    assert decision["full_orbit_authorized"] is False
    assert decision["matter_feedback_authorized"] is False
    assert decision["phase4_replacement_authorized"] is False


def test_phase7b5w_historical_science_is_unchanged_and_outputs_exist():
    report = _summary()
    assert max(report["new_monolithic_vs_phase7b5v_scalar_errors"].values()) < 5.0e-9
    for name in (
        "phase7b5w_monolithic_state.npz",
        "phase7b5w_stream256_state.npz",
        "phase7b5w_stream256_iterations.csv",
        "phase7b5w_translation_invariant_remap_gate.png",
    ):
        path = OUTPUT / name
        assert path.exists() and path.stat().st_size > 0
