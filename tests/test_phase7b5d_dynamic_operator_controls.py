from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5d_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b5d_saved_gate_identifies_an_interaction_not_a_unique_operator():
    decision = _report()["decision"]
    assert decision["baseline_reproduction_passed"] is True
    assert decision["all_control_operators_passed"] is True
    assert decision["stable_moving_error_reduction_controls"] == [
        "D = 1 control",
        "no true absorption/emission control",
    ]
    assert decision["unique_stable_dynamic_operator_identified"] is False
    assert decision["targeted_operator_remediation_authorized"] is False
    assert decision["production_frequency_representation_selected"] is False
    assert decision["full_dynamic_orbit_authorized"] is False
    assert decision["phase4_replacement_authorized"] is False
    assert decision["uvot_authorized"] is False


def test_phase7b5d_lorentz_and_true_continuum_removals_reduce_moving_errors():
    rows = _report()["operator_controls"]
    moving = ("maximum cell speed", "maximum width change")
    for case in moving:
        for control in ("D = 1 control", "no true absorption/emission control"):
            row = next(
                row
                for row in rows
                if row["case"] == case and row["control"] == control
            )
            assert row["error_reduction_relative_to_full"] > 0.99


def test_phase7b5d_ale_width_and_scattering_are_not_stable_reductions():
    rows = _report()["operator_controls"]
    for case in ("maximum cell speed", "maximum width change"):
        rigid = next(
            row
            for row in rows
            if row["case"] == case and row["control"] == "rigid ALE width control"
        )
        assert 0.99 < rigid["error_ratio_to_full_operator"] < 1.02
    scattering = [
        row
        for row in rows
        if row["control"] == "no scattering control"
        and row["case"] in ("maximum cell speed", "maximum width change")
    ]
    assert any(row["error_reduction_relative_to_full"] < 0.5 for row in scattering)


def test_phase7b5d_all_matched_control_runs_close_their_operators_and_rates():
    for row in _report()["operator_controls"]:
        assert row["candidate_rate_reconciliation_relative"] < 2.0e-8
        assert row["reference_rate_reconciliation_relative"] < 2.0e-8
        assert row["candidate_global_coupled_residual"] < 2.0e-8
        assert row["candidate_energy_ledger_residual"] < 2.0e-8
        assert row["reference_global_coupled_residual"] < 2.0e-8
        assert row["reference_energy_ledger_residual"] < 2.0e-8
        assert row["candidate_minimum_intensity"] >= 0.0
        assert row["reference_minimum_intensity"] >= 0.0


def test_phase7b5d_uses_no_forbidden_repairs_or_hidden_approval():
    paths = (
        PROJECT_ROOT / "scripts" / "phase7b4v_mixed_frame_ale_gate.py",
        PROJECT_ROOT / "scripts" / "phase7b5a_log_frequency_p1_gate.py",
        PROJECT_ROOT / "scripts" / "phase7b5d_dynamic_operator_controls.py",
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
    assert '"targeted_operator_remediation_authorized"' in source
    assert '"production_frequency_representation_selected": False' in source
    assert '"full_dynamic_orbit_authorized": False' in source
    assert '"phase4_replacement_authorized": False' in source
    assert '"uvot_authorized": False' in source
