from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5b_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b5b_saved_gate_keeps_rate_monitor_grid_unapproved() -> None:
    decision = _report()["decision"]
    assert decision["monitor_grid_convergence_passed"] is True
    assert decision["all_moving_equilibria_passed"] is True
    assert decision["all_candidate_operator_gate_passed"] is True
    assert decision["passing_focus_fractions"] == []
    assert decision["adjacent_focus_robust_frequency_gate_passed"] is False
    assert decision["efficiency_gate_passed"] is False
    assert decision["rate_kernel_grid_component_gate_passed"] is False
    assert decision["selected_dynamic_physical_frequency_groups"] is None
    assert decision["angular_radiation_subgrid_time_gate_authorized"] is False
    assert decision["full_dynamic_orbit_authorized"] is False
    assert decision["matter_temperature_population_feedback_authorized"] is False
    assert decision["phase4_replacement_authorized"] is False
    assert decision["uvot_authorized"] is False


def test_phase7b5b_grid_and_moving_controls_pass_without_repairs() -> None:
    report = _report()
    assert all(row["all_thresholds_exact"] for row in report["grid_controls"])
    assert all(row["strictly_positive_widths"] for row in report["grid_controls"])
    finest = [
        row
        for row in report["grid_controls"]
        if row["physical_frequency_groups"] == 2408
    ]
    assert len(finest) == 3
    assert all(
        row["monitor_edge_convergence_relative"] < 5.0e-9 for row in finest
    )
    assert all(row["monitor_segment_count_stable"] for row in finest)
    for row in report["moving_equilibrium_controls"]:
        assert row["passed"] is True
        assert row["equilibrium_error"] < 1.0e-12
        assert row["global_coupled_residual"] < 2.0e-8
        assert row["total_energy_ledger_residual"] < 2.0e-8
        assert row["final_limiter_count"] == 0


def test_phase7b5b_every_predeclared_focus_fails_the_same_width_state() -> None:
    rows = [
        row
        for row in _report()["state_convergence"]
        if row["case"] == "maximum width change"
        and row["physical_frequency_groups"] == 2408
    ]
    assert [row["focus_fraction"] for row in rows] == [0.25, 0.5, 0.75]
    assert all(row["maximum_error"] > 1.0e-3 for row in rows)
    assert all(
        row["maximum_error"] == row["photoionization_H_I_error"] for row in rows
    )
    assert all(row["spectral_degrees_of_freedom"] == 4816 for row in rows)


def test_phase7b5b_best_observed_focus_is_not_promoted() -> None:
    report = _report()
    decision = report["decision"]
    errors = decision["highest_budget_worst_error_by_focus"]
    assert decision["best_observed_focus_fraction_not_selected"] == 0.25
    assert errors["0.25"] == min(errors.values())
    uniform = json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5a_summary.json").read_text(
            encoding="utf-8"
        )
    )
    uniform_width = next(
        row
        for row in uniform["state_convergence"]
        if row["case"] == "maximum width change"
        and row["physical_frequency_groups"] == 2408
    )
    assert errors["0.25"] < uniform_width["maximum_error"]
    assert errors["0.25"] > 1.0e-3


def test_phase7b5b_actual_operators_pass_but_use_limiters() -> None:
    report = _report()
    for row in report["actual_states"]:
        assert row["global_coupled_residual"] < 2.0e-8
        assert row["total_energy_ledger_residual"] < 2.0e-8
        assert row["solver_final_limiter_count"] > 0
        assert row["solver_cumulative_limiter_count"] >= row[
            "solver_final_limiter_count"
        ]


def test_phase7b5b_uses_no_forbidden_repairs_or_hidden_approval() -> None:
    paths = (
        PROJECT_ROOT
        / "src"
        / "eccentric_tde_observer"
        / "goal_oriented_frequency.py",
        PROJECT_ROOT / "scripts" / "phase7b5b_rate_kernel_grid_gate.py",
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
    assert '"uvot_authorized": False' in source
