from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "outputs" / "phase7b5n_preregistered_protocol.json"
FAILURE = PROJECT_ROOT / "outputs" / "phase7b5n_protocol_feasibility_failure.json"
EXPECTED_PROTOCOL_SHA256 = (
    "e8d76f9603f0bbd153f0630abebade84da821d9eb79096e57d949306e19cef91"
)


def _protocol() -> dict[str, object]:
    return json.loads(OUTPUT.read_text(encoding="utf-8"))


def test_phase7b5n_protocol_file_is_frozen() -> None:
    assert hashlib.sha256(OUTPUT.read_bytes()).hexdigest() == EXPECTED_PROTOCOL_SHA256
    protocol = _protocol()
    assert protocol["protocol_version"] == 1
    assert protocol["candidate"]["parent_options"] == [1, 2, 4]
    assert protocol["candidate"]["leaf_group_budget"] == 4816
    assert protocol["candidate"]["validation_feedback_allowed"] is False


def test_phase7b5n_uses_new_geometry_only_holdouts() -> None:
    protocol = _protocol()
    development = protocol["development"]
    validation = protocol["validation"]
    assert development["source_iterations"] == [0, 1, 2, 4, 8]
    assert validation["source_iterations"] == [3, 6, 12]
    assert validation["state_count"] == 18
    expected = {
        (1280, 0),
        (1789, 0),
        (1226, 201),
        (821, 201),
        (1294, 53),
        (753, 57),
    }
    actual = {
        (case["phase_index"], case["full_depth_index"])
        for case in validation["cases"]
    }
    development_cells = {
        (case["phase_index"], case["full_depth_index"])
        for case in development["cases"]
    }
    assert actual == expected
    assert actual.isdisjoint(development_cells)


def test_phase7b5n_preregisters_joint_energy_and_h_he_gates() -> None:
    gates = _protocol()["gates"]
    assert gates["candidate_physical_group_count"] == 4816
    assert gates["candidate_and_master_energy_relative_error_strictly_below"] == 1e-3
    assert gates["candidate_and_master_rate_relative_error_strictly_below"] == 1e-3
    assert gates["rate_species"] == ["H_I", "He_I", "He_II"]
    assert gates["converged_operator_controls_required"] is True
    assert gates["no_failed_state_may_be_removed"] is True


def test_phase7b5n_preregistration_reads_no_validation_spectrum() -> None:
    source = (
        PROJECT_ROOT / "scripts" / "phase7b5n_preregister_protocol.py"
    ).read_text(encoding="utf-8")
    assert "_one_p0_map" not in source
    assert "_p0_actual_one_cell_run" not in source
    assert "nan_to_num" not in source
    assert "np.clip" not in source


def test_phase7b5n_records_protocol_feasibility_failure_without_recovery() -> None:
    failure = json.loads(FAILURE.read_text(encoding="utf-8"))
    assert failure["frozen_protocol_sha256"] == EXPECTED_PROTOCOL_SHA256
    assert failure["failed_case"] == "surface temperature q75"
    assert failure["requested_source_iteration"] == 12
    assert failure["last_available_source_iteration"] == 11
    assert failure["protocol_was_modified_after_failure"] is False
    assert failure["candidate_validation_completed"] is False
    assert failure["candidate_selected"] is False
    assert not (PROJECT_ROOT / "outputs" / "phase7b5n_summary.json").exists()
