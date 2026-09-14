from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5f_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b5f_single_pass_transform_passes_without_selecting_production():
    decision = _report()["decision"]
    assert decision["single_pass_intensity_transform_passed"] is True
    assert decision["intensity_transform_discretization_identified_as_primary"] is False
    assert decision["implicit_collision_feedback_accumulation_audit_authorized"] is True
    assert decision["targeted_operator_remediation_authorized"] is False
    assert decision["production_frequency_representation_selected"] is False
    assert decision["full_dynamic_orbit_authorized"] is False
    assert decision["phase4_replacement_authorized"] is False
    assert decision["uvot_authorized"] is False


def test_phase7b5f_all_three_states_close_energy_and_hydrogen_rate_gate():
    for row in _report()["states"]:
        assert row["passed"] is True
        assert row["input_energy_relative_difference"] < 1.0e-4
        assert row["output_energy_relative_difference"] < 1.0e-3
        assert row["candidate_reference_rate_error"] < 1.0e-3
        assert row["reference_analytic_rate_error"] < 2.0e-5


def test_phase7b5f_independent_rates_and_analytic_reference_converge():
    for row in _report()["states"]:
        assert row["candidate_native_rate_reconciliation_relative"] < 2.0e-8
        assert row["reference_native_rate_reconciliation_relative"] < 2.0e-8
        assert row["analytic_rate_quadrature_convergence"] < 2.0e-8


def test_phase7b5f_one_pass_error_is_far_below_full_dynamic_error():
    report = _report()
    dynamic = json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5e_summary.json").read_text(
            encoding="utf-8"
        )
    )
    full_by_case = {
        row["case"]: row["absolute_relative_error"]
        for row in dynamic["component_controls"]
        if row["control"] == "full Lorentz operator"
    }
    for row in report["states"]:
        assert row["candidate_reference_rate_error"] < 0.02 * full_by_case[
            row["case"]
        ]


def test_phase7b5f_uses_no_forbidden_repairs_or_hidden_approval():
    path = (
        PROJECT_ROOT
        / "scripts"
        / "phase7b5f_single_pass_intensity_transform.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = {
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    source = path.read_text(encoding="utf-8")
    assert "np.nan_to_num" not in calls
    assert "np.clip" not in calls
    assert "numpy.nan_to_num" not in calls
    assert "numpy.clip" not in calls
    assert '"targeted_operator_remediation_authorized": False' in source
    assert '"production_frequency_representation_selected": False' in source
    assert '"full_dynamic_orbit_authorized": False' in source
    assert '"phase4_replacement_authorized": False' in source
    assert '"uvot_authorized": False' in source
