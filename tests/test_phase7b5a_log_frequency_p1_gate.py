from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5a_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b5a_saved_gate_keeps_log_p1_unapproved() -> None:
    decision = _report()["decision"]
    assert decision["log_p1_moving_equilibrium_passed"] is True
    assert decision["log_p1_operator_gate_passed"] is False
    assert decision["three_actual_state_frequency_gate_passed"] is False
    assert decision["efficiency_gate_passed"] is False
    assert decision["log_p1_frequency_component_gate_passed"] is False
    assert decision["selected_dynamic_physical_frequency_groups"] is None
    assert decision["angular_radiation_subgrid_time_gate_authorized"] is False
    assert decision["full_dynamic_orbit_authorized"] is False
    assert decision["matter_temperature_population_feedback_authorized"] is False


def test_phase7b5a_translation_control_and_actual_state_split() -> None:
    report = _report()
    control = report["control"]
    assert control["equilibrium_error"] < 2.0e-13
    assert control["global_coupled_residual"] < 2.0e-13
    assert control["total_energy_ledger_residual"] < 2.0e-13
    rows = report["state_convergence"]
    speed = next(
        row
        for row in rows
        if row["case"] == "maximum cell speed"
        and row["physical_frequency_groups"] == 2408
    )
    width = next(
        row
        for row in rows
        if row["case"] == "maximum width change"
        and row["physical_frequency_groups"] == 2408
    )
    assert speed["maximum_error"] < 1.0e-3
    assert width["maximum_error"] > 1.0e-3
    assert width["maximum_error"] == width["photoionization_H_I_error"]
    assert width["spectral_degrees_of_freedom"] == 4816


def test_phase7b5a_coordinate_change_does_not_resolve_width_state() -> None:
    log_rows = _report()["state_convergence"]
    linear_rows = json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b4x_summary.json").read_text(
            encoding="utf-8"
        )
    )["state_convergence"]
    log_width = next(
        row
        for row in log_rows
        if row["case"] == "maximum width change"
        and row["physical_frequency_groups"] == 2408
    )
    linear_width = next(
        row
        for row in linear_rows
        if row["case"] == "maximum width change"
        and row["physical_frequency_groups"] == 2408
    )
    relative_change = abs(
        log_width["maximum_error"] - linear_width["maximum_error"]
    ) / linear_width["maximum_error"]
    assert relative_change < 1.0e-2


def test_phase7b5a_retains_coarse_operator_failure() -> None:
    row = next(
        row
        for row in _report()["actual_states"]
        if row["case"] == "cold coefficient surface"
        and row["physical_frequency_groups"] == 153
    )
    assert row["global_coupled_residual"] > 2.0e-8
    assert row["solver_final_limiter_count"] > 0


def test_phase7b5a_uses_no_forbidden_repairs_or_hidden_approval() -> None:
    paths = (
        PROJECT_ROOT
        / "src"
        / "eccentric_tde_observer"
        / "log_frequency_moments.py",
        PROJECT_ROOT
        / "src"
        / "eccentric_tde_observer"
        / "log_multigroup_continuum.py",
        PROJECT_ROOT
        / "src"
        / "eccentric_tde_observer"
        / "mixed_frame_ale_log_p1.py",
        PROJECT_ROOT / "scripts" / "phase7b5a_log_frequency_p1_gate.py",
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
