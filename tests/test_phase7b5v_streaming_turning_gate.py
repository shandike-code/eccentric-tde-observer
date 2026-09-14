import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
PROTOCOL = OUTPUT / "phase7b5v_preregistered_streaming_turning_protocol.json"
SUMMARY = OUTPUT / "phase7b5v_streaming_turning_summary.json"
EXPECTED_PROTOCOL_SHA256 = (
    "3eb84c561d28ad9bfd9867b11ceb05ebbc33e7b1479eadda3053e02c09c81b92"
)


def _summary():
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_phase7b5v_protocol_is_frozen_and_does_not_authorize_full_orbit():
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == (
        EXPECTED_PROTOCOL_SHA256
    )
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["streaming_method"]["global_frequency_edges_changed"] is False
    assert protocol["turning_ray_method"]["direction_deletion"] is False
    assert protocol["turning_ray_method"]["angular_weight_renormalization"] is False
    assert protocol["authorization"]["full_orbit_authorized"] is False


def test_phase7b5v_turning_ray_controls_pass_without_repairs():
    control = _summary()["turning_controls"]
    assert control["turning_dense_system_maximum_absolute_error"] == pytest.approx(
        1.1102230246251565e-16
    )
    assert control["turning_global_coupled_residual"] < 1.0e-12
    assert control["turning_energy_ledger_residual"] == 0.0
    assert control["turning_minimum_intensity"] > 0.0
    assert control["nonturning_hybrid_equals_step_exactly"] is True


def test_phase7b5v_actual_fixed_points_are_scientifically_equivalent():
    report = _summary()
    assert all(run["fixed_point_iterations"] == 35 for run in report["runs"].values())
    assert all(run["fixed_point_converged"] for run in report["runs"].values())
    assert report["comparisons"]["stream256"]["maximum_error"] == pytest.approx(
        3.384901285047592e-12
    )
    assert report["comparisons"]["stream512"]["maximum_error"] == pytest.approx(
        3.5349026724873667e-12
    )
    assert max(
        run["peak_process_rss_mib"] for run in report["runs"].values()
    ) < 6144.0


def test_phase7b5v_retains_strict_one_iteration_failure():
    report = _summary()
    error = report["one_iteration_streaming_control"][
        "maximum_relative_intensity_error"
    ]
    assert error == pytest.approx(3.937747943835367e-12)
    assert error > 1.0e-12
    decision = report["decision"]
    assert decision["small_one_iteration_equivalence_passed"] is False
    assert decision["phase7b5v_gate_passed"] is False
    assert decision["full_depth_block_resource_probe_authorized"] is False


def test_phase7b5v_full_column_plan_and_outputs_are_complete():
    report = _summary()
    rows = report["full_column_block_planning"]["rows"]
    assert [row["core_frequency_groups"] for row in rows] == [128, 256, 512]
    assert [row["maximum_outer_groups"] for row in rows] == [397, 505, 749]
    assert rows[1]["identified_live_array_gib"] == pytest.approx(
        2.85748291015625
    )
    for name in (
        "phase7b5v_equivalence_errors.csv",
        "phase7b5v_full_column_block_plan.csv",
        "phase7b5v_streaming_turning_gate.png",
        "phase7b5v_monolithic_state.npz",
        "phase7b5v_stream256_state.npz",
        "phase7b5v_stream512_state.npz",
    ):
        path = OUTPUT / name
        assert path.exists() and path.stat().st_size > 0
