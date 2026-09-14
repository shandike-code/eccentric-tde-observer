from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5i_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b5i_closes_partition_representation_ledger():
    report = _report()
    assert report["decision"][
        "all_projection_mapping_and_ledger_controls_passed"
    ] is True
    for row in report["partition_representation_decomposition"]:
        assert row["reference_one_step_reproduced_exactly"] is True
        assert row["decomposition_ledger_relative"] < 2.0e-12
        assert row["partition_p0_projection_energy_error"] < 2.0e-13
        assert row["same_cost_p0_projection_energy_error"] < 2.0e-13
        assert row["log_p1_projection_energy_error"] < 2.0e-13
        assert row["localization_quadrature_relative_error"] < 2.0e-10
        fraction_sum = (
            row["absolute_partition_fraction"]
            + row["absolute_representation_fraction"]
        )
        assert abs(fraction_sum - 1.0) < 2.0e-15


def test_phase7b5i_reproduces_phase7b5h_common_input_injection():
    current = _report()["partition_representation_decomposition"]
    previous = json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5h_summary.json").read_text(
            encoding="utf-8"
        )
    )["recurrence_decomposition"]
    for row in current:
        reference = next(
            old
            for old in previous
            if old["case"] == row["case"]
            and old["input_iteration"] == row["input_iteration"]
        )
        difference = abs(
            row["total_log_p1_signed_error"]
            - reference["common_input_injection_signed"]
        )
        assert difference < 2.0e-14


def test_phase7b5i_frequency_partition_is_shared_dominant_component():
    report = _report()
    decision = report["decision"]
    assert decision["dominant_component_by_moving_case"] == {
        "maximum cell speed": "frequency_partition",
        "maximum width change": "frequency_partition",
    }
    assert decision["same_dominant_component_in_both_moving_cases"] is True
    moving = [
        row
        for row in report["partition_representation_decomposition"]
        if row["case"] in {"maximum cell speed", "maximum width change"}
    ]
    assert min(row["absolute_partition_fraction"] for row in moving) > 0.5
    assert decision["frequency_partition_audit_authorized"] is True
    assert decision["within_partition_representation_audit_authorized"] is False
    assert decision["joint_partition_representation_audit_required"] is False


def test_phase7b5i_same_cost_p0_retains_two_width_change_failures():
    report = _report()
    assert report["decision"]["same_cost_p0_one_step_rate_gate_passed"] is False
    failed = {
        (row["case"], row["input_iteration"])
        for row in report["partition_representation_decomposition"]
        if abs(row["same_cost_p0_signed_error"])
        >= report["configuration"]["H_I_rate_target"]
    }
    assert failed == {
        ("maximum width change", 4),
        ("maximum width change", 8),
    }


def test_phase7b5i_component_regions_form_complete_nonnegative_partitions():
    rows = _report()["component_region_evolution"]
    keys = sorted(
        {
            (row["case"], row["input_iteration"], row["component"])
            for row in rows
        }
    )
    for key in keys:
        selected = [
            row
            for row in rows
            if (row["case"], row["input_iteration"], row["component"])
            == key
        ]
        assert all(
            0.0 <= row["absolute_difference_fraction"] <= 1.0
            for row in selected
        )
        assert abs(
            sum(row["absolute_difference_fraction"] for row in selected)
            - 1.0
        ) < 2.0e-13


def test_phase7b5i_uses_no_forbidden_repairs_or_hidden_production_approval():
    paths = (
        PROJECT_ROOT
        / "src"
        / "eccentric_tde_observer"
        / "rate_error_localization.py",
        PROJECT_ROOT / "scripts" / "phase7b5i_partition_representation_split.py",
    )
    calls: set[str] = set()
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls.update(
            ast.unparse(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        )
    source = paths[-1].read_text(encoding="utf-8")
    assert "np.nan_to_num" not in calls
    assert "np.clip" not in calls
    assert "numpy.nan_to_num" not in calls
    assert "numpy.clip" not in calls
    assert '"targeted_operator_remediation_authorized": False' in source
    assert '"production_frequency_representation_selected": False' in source
    assert '"full_dynamic_orbit_authorized": False' in source
    assert '"phase4_replacement_authorized": False' in source
    assert '"uvot_authorized": False' in source
