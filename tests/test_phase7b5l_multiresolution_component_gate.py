from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5l_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b5l_hierarchy_transfer_and_indicator_controls_pass():
    report = _report()
    decision = report["decision"]
    assert decision["strict_nested_hierarchy_passed"] is True
    assert decision["conservative_transfer_controls_passed"] is True
    assert decision["embedded_indicator_quadrature_passed"] is True
    assert decision["leaf_budget_bookkeeping_passed"] is True
    assert decision["multiresolution_component_gate_passed"] is True
    assert decision["actual_state_multiresolution_audit_authorized"] is True


def test_phase7b5l_uses_strict_2408_4816_9632_hierarchy():
    configuration = _report()["configuration"]
    assert configuration["base_group_count"] == 2408
    assert configuration["pilot_group_count"] == 4816
    assert configuration["master_group_count"] == 9632
    assert configuration["leaf_group_budget"] == 4816
    assert configuration["fixed_rate_kernel_focus_fraction"] == 0.25
    assert configuration["control_spectrum_count"] == 24
    assert "no fitted bandwidth" in configuration["variable_grid_rule"]


def test_phase7b5l_budget_is_closed_in_complete_four_child_blocks():
    budget = _report()["budgeted_grid"]
    assert budget["refined_parent_count"] == 802
    assert budget["leaf_group_count"] == 4814
    assert budget["leaf_group_budget"] == 4816
    assert budget["unused_leaf_budget"] == 2
    assert budget["minimum_refined_indicator"] > budget[
        "maximum_unrefined_indicator"
    ]


def test_phase7b5l_controls_remain_below_predeclared_targets():
    report = _report()
    controls = {
        row["control"]: row["value"]
        for row in report["transfer_and_quadrature_controls"]
    }
    for name, value in controls.items():
        target = 2.0e-10 if name == "8/16 indicator quadrature" else 2.0e-13
        assert value < target
    assert report["indicator"]["maximum_normalized_indicator"] < 1.0


def test_phase7b5l_does_not_promote_component_controls_to_production():
    decision = _report()["decision"]
    assert decision["production_frequency_representation_selected"] is False
    assert decision["angular_radiation_subgrid_time_gate_authorized"] is False
    assert decision["full_dynamic_orbit_authorized"] is False
    assert decision["matter_temperature_population_feedback_authorized"] is False
    assert decision["phase4_replacement_authorized"] is False
    assert decision["uvot_authorized"] is False


def test_phase7b5l_uses_no_forbidden_repairs_or_hidden_approval():
    paths = (
        PROJECT_ROOT
        / "src"
        / "eccentric_tde_observer"
        / "multiresolution_frequency.py",
        PROJECT_ROOT
        / "scripts"
        / "phase7b5l_multiresolution_component_gate.py",
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
    assert '"production_frequency_representation_selected": False' in source
    assert '"phase4_replacement_authorized": False' in source
