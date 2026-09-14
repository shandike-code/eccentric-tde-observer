from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b4y_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b4y_saved_gate_separates_operator_from_frequency_failure() -> None:
    decision = _report()["decision"]
    assert decision["threshold_grid_geometry_gate_passed"] is True
    assert decision["threshold_p1_moving_equilibrium_passed"] is True
    assert decision["threshold_p1_operator_gate_passed"] is True
    assert decision["three_actual_state_frequency_gate_passed"] is False
    assert decision["efficiency_gate_passed"] is False
    assert decision["threshold_p1_component_gate_passed"] is False
    assert decision["selected_panels_per_transformed_decade"] is None
    assert decision["selected_dynamic_physical_frequency_groups"] is None
    assert decision["angular_radiation_subgrid_time_gate_authorized"] is False
    assert decision["full_dynamic_orbit_authorized"] is False


def test_phase7b4y_threshold_local_p1_does_not_beat_uniform_p1_pressure_point() -> None:
    rows = _report()["state_convergence"]
    finest = next(
        row
        for row in rows
        if row["case"] == "maximum width change"
        and row["physical_frequency_groups"] == 2265
    )
    uniform = json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b4x_summary.json").read_text(
            encoding="utf-8"
        )
    )["state_convergence"]
    uniform_finest = next(
        row
        for row in uniform
        if row["case"] == "maximum width change"
        and row["physical_frequency_groups"] == 2408
    )
    assert finest["maximum_error"] > uniform_finest["maximum_error"]
    assert finest["maximum_error"] == finest["photoionization_H_I_error"]


def test_phase7b4y_uses_no_forbidden_repairs_or_hidden_approval() -> None:
    path = PROJECT_ROOT / "scripts" / "phase7b4y_threshold_p1_gate.py"
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
