from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b4x_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b4x_saved_gate_retains_failed_uniform_p1_candidate() -> None:
    report = _report()
    decision = report["decision"]
    assert decision["p1_moving_equilibrium_passed"] is True
    assert decision["p1_operator_gate_passed"] is False
    assert decision["three_actual_state_frequency_gate_passed"] is False
    assert decision["efficiency_gate_passed"] is False
    assert decision["p1_frequency_component_gate_passed"] is False
    assert decision["selected_dynamic_physical_frequency_groups"] is None
    assert decision["angular_radiation_subgrid_time_gate_authorized"] is False
    assert decision["full_dynamic_orbit_authorized"] is False
    assert decision["matter_temperature_population_feedback_authorized"] is False


def test_phase7b4x_maximum_width_change_remains_above_precision_gate() -> None:
    rows = _report()["state_convergence"]
    finest = next(
        row
        for row in rows
        if row["case"] == "maximum width change"
        and row["physical_frequency_groups"] == 2408
    )
    assert finest["maximum_error"] == finest["photoionization_H_I_error"]
    assert finest["maximum_error"] > 1.0e-3


def test_phase7b4x_uses_no_forbidden_repairs_or_hidden_approval() -> None:
    paths = (
        PROJECT_ROOT / "src" / "eccentric_tde_observer" / "mixed_frame_frequency.py",
        PROJECT_ROOT / "src" / "eccentric_tde_observer" / "mixed_frame_ale_p1.py",
        PROJECT_ROOT / "scripts" / "phase7b4x_p1_frequency_moments.py",
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
    assert '"full_dynamic_orbit_authorized": False' in source
    assert '"phase4_replacement_authorized": False' in source

