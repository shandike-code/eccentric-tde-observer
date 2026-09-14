from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from eccentric_tde_observer import (
    mixed_frame_frequency_stencil_from_active_edges,
    threshold_excess_frequency_group_edges_ev,
)
from scripts.phase7b4w_threshold_frequency_groups import (
    _grid_control_rows,
    _irregular_moving_equilibrium_control,
)


def _saved_report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b4w_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b4w_threshold_grid_controls_preserve_exact_edges() -> None:
    maximum_beta = 0.008028600886554787
    rows = _grid_control_rows(maximum_beta)
    assert [row["physical_frequency_groups"] for row in rows] == [
        568,
        1134,
        2265,
        4527,
        9053,
        18105,
    ]
    assert all(bool(row["passed"]) for row in rows)
    assert callable(threshold_excess_frequency_group_edges_ev)
    assert callable(mixed_frame_frequency_stencil_from_active_edges)


def test_phase7b4w_irregular_grid_preserves_moving_equilibrium() -> None:
    control = _irregular_moving_equilibrium_control(0.008028600886554787)
    assert control["physical_frequency_groups"] == 2265
    assert control["equilibrium_error"] < 1.0e-10
    assert control["global_coupled_residual"] < 2.0e-8
    assert control["total_energy_ledger_residual"] < 2.0e-8
    assert control["minimum_intensity"] >= 0.0
    assert control["passed"] is True


def test_phase7b4w_saved_decision_separates_accuracy_from_efficiency() -> None:
    report = _saved_report()
    decision = report["decision"]
    assert decision["threshold_group_geometry_gate_passed"] is True
    assert decision["irregular_grid_moving_equilibrium_passed"] is True
    assert decision["threshold_excess_operator_gate_passed"] is True
    assert decision["three_actual_state_frequency_gate_passed"] is True
    assert (
        decision["minimum_frequency_passing_panels_per_transformed_decade"]
        == 2048
    )
    assert decision["minimum_frequency_passing_physical_frequency_groups"] == 18105
    assert decision["efficiency_gate_passed"] is False
    assert decision["threshold_local_component_gate_passed"] is False
    assert decision["selected_panels_per_transformed_decade"] is None
    assert decision["selected_candidate_physical_frequency_groups"] is None
    assert decision["p1_frequency_moment_required"] is True
    assert decision["angular_radiation_subgrid_time_gate_authorized"] is False
    assert decision["full_dynamic_orbit_authorized"] is False
    assert decision["matter_temperature_population_feedback_authorized"] is False
    assert decision["phase4_replacement_authorized"] is False
    assert decision["uvot_authorized"] is False


def test_phase7b4w_code_uses_no_forbidden_repairs_or_hidden_approval() -> None:
    paths = (
        PROJECT_ROOT
        / "src"
        / "eccentric_tde_observer"
        / "frequency_quadrature.py",
        PROJECT_ROOT / "src" / "eccentric_tde_observer" / "mixed_frame_ale.py",
        PROJECT_ROOT / "scripts" / "phase7b4w_threshold_frequency_groups.py",
    )
    calls: set[str] = set()
    script_source = paths[-1].read_text(encoding="utf-8")
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls.update(
            ast.unparse(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        )
    assert "np.nan_to_num" not in calls
    assert "np.clip" not in calls
    assert "numpy.nan_to_num" not in calls
    assert "numpy.clip" not in calls
    assert '"full_dynamic_orbit_authorized": False' in script_source
    assert '"phase4_replacement_authorized": False' in script_source
    assert '"uvot_authorized": False' in script_source
