import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
PROTOCOL = OUTPUT / "phase7b5x_preregistered_full_depth_block_probe.json"
SUMMARY = OUTPUT / "phase7b5x_full_depth_block_probe_summary.json"
EXPECTED_PROTOCOL_SHA256 = (
    "6343427638c3109463ab6b92218848636675207147f186fb895bedf1f64919bb"
)


def _summary():
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_phase7b5x_protocol_is_frozen_and_scoped_to_one_source_map():
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == (
        EXPECTED_PROTOCOL_SHA256
    )
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["configuration"]["source_iterations"] == 1
    assert protocol["configuration"]["physical_frequency_groups"] == 9632
    assert protocol["authorization"]["full_column_fixed_point_authorized_if_gate_passes"] is False
    assert protocol["authorization"]["full_orbit_authorized"] is False


def test_phase7b5x_selected_the_frozen_worst_phase_and_block():
    worker = _summary()["worker"]
    assert worker["phase_index"] == 1367
    assert worker["core_group_start"] == 3456
    assert worker["core_group_stop"] == 3584
    assert worker["collision_group_count"] == 263
    assert worker["outer_group_count"] == 397
    assert worker["radiation_depth_cell_count"] == 4096
    assert worker["turning_direction_count"] == 2


def test_phase7b5x_parent_microphysics_replication_is_exact():
    control = _summary()["parent_microphysics_replication_control"]
    assert control["maximum_relative_error"] == 0.0
    assert all(value == 0.0 for value in control["relative_errors"].values())


def test_phase7b5x_measured_resources_pass_without_claiming_convergence():
    report = _summary()
    worker = report["worker"]
    assert worker["peak_process_rss_mib"] == pytest.approx(2863.140625)
    assert worker["peak_process_rss_mib"] < 6144.0
    assert worker["total_runtime_s"] < 900.0
    assert worker["minimum_intensity"] > 0.0
    assert worker["all_reported_diagnostics_finite"] is True
    assert worker["one_iteration_fixed_point_converged"] is False
    decision = report["decision"]
    assert decision["phase7b5x_gate_passed"] is True
    assert decision["performance_architecture_decision_authorized"] is True
    assert decision["full_column_fixed_point_authorized"] is False
    assert decision["full_orbit_authorized"] is False


def test_phase7b5x_outputs_exist():
    for name in (
        "phase7b5x_full_depth_block_worker.json",
        "phase7b5x_full_depth_block_probe_summary.json",
        "phase7b5x_full_depth_block_probe.png",
    ):
        path = OUTPUT / name
        assert path.exists() and path.stat().st_size > 0
