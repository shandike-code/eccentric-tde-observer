from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b4z_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b4z_saved_gate_keeps_p2_unapproved() -> None:
    report = _report()
    decision = report["decision"]
    assert decision["p2_moving_equilibrium_passed"] is True
    assert decision["p2_operator_gate_passed"] is False
    assert decision["three_actual_state_frequency_gate_passed"] is False
    assert decision["efficiency_gate_passed"] is False
    assert decision["p2_frequency_component_gate_passed"] is False
    assert decision["selected_dynamic_physical_frequency_groups"] is None
    assert decision["angular_radiation_subgrid_time_gate_authorized"] is False
    assert decision["full_dynamic_orbit_authorized"] is False


def test_phase7b4z_p2_tradeoff_does_not_close_pressure_state() -> None:
    p2_rows = _report()["state_convergence"]
    p2_speed = next(
        row
        for row in p2_rows
        if row["case"] == "maximum cell speed"
        and row["physical_frequency_groups"] == 1604
    )
    p2_width = next(
        row
        for row in p2_rows
        if row["case"] == "maximum width change"
        and row["physical_frequency_groups"] == 1604
    )
    p1_rows = json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b4x_summary.json").read_text(
            encoding="utf-8"
        )
    )["state_convergence"]
    p1_width = next(
        row
        for row in p1_rows
        if row["case"] == "maximum width change"
        and row["physical_frequency_groups"] == 2408
    )
    assert p2_speed["maximum_error"] < 1.0e-3
    assert p2_width["maximum_error"] > 1.0e-3
    assert p2_width["maximum_error"] > p1_width["maximum_error"]
    assert p2_width["maximum_error"] == p2_width["photoionization_H_I_error"]
    assert p2_width["spectral_degrees_of_freedom"] <= 4816


def test_phase7b4z_uses_no_forbidden_repairs_or_hidden_approval() -> None:
    path = PROJECT_ROOT / "scripts" / "phase7b4z_p2_frequency_moments.py"
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
    assert '"full_dynamic_orbit_authorized": False' in source
    assert '"phase4_replacement_authorized": False' in source
