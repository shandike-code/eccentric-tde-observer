from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5e_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b5e_saved_gate_keeps_invalid_component_controls_out_of_causality():
    decision = _report()["decision"]
    assert decision["baseline_reproduction_passed"] is True
    assert decision["all_controlled_equations_passed"] is False
    assert decision["admissible_controls"] == [
        "full Lorentz operator",
        "no intensity Lorentz",
    ]
    assert decision["stable_moving_error_reduction_controls"] == [
        "no intensity Lorentz"
    ]
    assert decision["unique_stable_lorentz_component_identified"] is False
    assert decision["intensity_branch_single_pass_audit_authorized"] is True
    assert decision["targeted_component_analytic_audit_authorized"] is False
    assert decision["targeted_operator_remediation_authorized"] is False
    assert decision["production_frequency_representation_selected"] is False
    assert decision["full_dynamic_orbit_authorized"] is False
    assert decision["phase4_replacement_authorized"] is False
    assert decision["uvot_authorized"] is False


def test_phase7b5e_valid_intensity_control_reduces_both_moving_errors():
    rows = _report()["component_controls"]
    for case in ("maximum cell speed", "maximum width change"):
        row = next(
            row
            for row in rows
            if row["case"] == case and row["control"] == "no intensity Lorentz"
        )
        assert row["controlled_equation_passed"] is True
        assert row["error_reduction_relative_to_full"] > 0.98


def test_phase7b5e_failed_controls_are_explicitly_retained():
    rows = _report()["component_controls"]
    failed = [row for row in rows if not row["controlled_equation_passed"]]
    assert failed
    assert {row["control"] for row in failed} == {
        "no extinction Lorentz",
        "no emissivity Lorentz",
    }
    assert any(
        row["candidate_global_coupled_residual"] >= 2.0e-8 for row in failed
    )


def test_phase7b5e_all_native_rates_reconcile_and_valid_controls_close():
    for row in _report()["component_controls"]:
        assert row["candidate_rate_reconciliation_relative"] < 2.0e-8
        assert row["reference_rate_reconciliation_relative"] < 2.0e-8
        assert row["candidate_minimum_intensity"] >= 0.0
        assert row["reference_minimum_intensity"] >= 0.0
        if row["controlled_equation_passed"]:
            assert row["candidate_global_coupled_residual"] < 2.0e-8
            assert row["candidate_energy_ledger_residual"] < 2.0e-8
            assert row["reference_global_coupled_residual"] < 2.0e-8
            assert row["reference_energy_ledger_residual"] < 2.0e-8


def test_phase7b5e_uses_no_forbidden_repairs_or_hidden_approval():
    paths = (
        PROJECT_ROOT
        / "src"
        / "eccentric_tde_observer"
        / "mixed_frame_ale.py",
        PROJECT_ROOT
        / "src"
        / "eccentric_tde_observer"
        / "mixed_frame_ale_log_p1.py",
        PROJECT_ROOT / "scripts" / "phase7b5e_lorentz_component_controls.py",
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
