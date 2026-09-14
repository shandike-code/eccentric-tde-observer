from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5g_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b5g_identifies_iterative_not_first_update_amplification():
    decision = _report()["decision"]
    assert decision["iteration_zero_reproduces_phase7b5f"] is True
    assert decision["converged_reproduces_phase7b5e"] is True
    assert decision["all_localization_controls_passed"] is True
    assert decision["earliest_half_final_error_checkpoint_by_moving_case"] == {
        "maximum cell speed": "2",
        "maximum width change": "8",
    }
    assert decision["first_collision_update_dominates_both_moving_cases"] is False
    assert decision["first_update_collision_split_audit_authorized"] is False
    assert decision["iterative_recurrence_amplification_audit_authorized"] is True
    assert decision["targeted_operator_remediation_authorized"] is False
    assert decision["production_frequency_representation_selected"] is False


def test_phase7b5g_saved_endpoints_reproduce_previous_phases_exactly():
    report = _report()
    assert report["iteration_zero_reproduction_relative"] == 0.0
    assert report["converged_reproduction_relative"] == 0.0


def test_phase7b5g_moving_errors_grow_by_many_orders_during_iteration():
    rows = _report()["iteration_history"]
    minimum_amplification = {
        "maximum cell speed": 1.0e4,
        "maximum width change": 2.0e4,
    }
    for case, threshold in minimum_amplification.items():
        final = next(
            row
            for row in rows
            if row["case"] == case and row["checkpoint"] == "converged"
        )
        assert final["absolute_error_amplification_from_iteration_zero"] > threshold


def test_phase7b5g_all_checkpoint_localizations_converge_without_invalid_energy():
    for row in _report()["iteration_history"]:
        assert row["localization_quadrature_relative_error"] < 2.0e-10
        assert row["candidate_reference_energy_relative_error"] >= 0.0
        assert row["candidate_lab_saturated_group_count"] >= 0
        assert row["candidate_comoving_saturated_group_count"] >= 0
        assert row["candidate_comoving_transform_limiter_count"] >= 0


def test_phase7b5g_uses_no_forbidden_repairs_or_hidden_approval():
    paths = (
        PROJECT_ROOT / "src" / "eccentric_tde_observer" / "mixed_frame_ale.py",
        PROJECT_ROOT
        / "src"
        / "eccentric_tde_observer"
        / "mixed_frame_ale_log_p1.py",
        PROJECT_ROOT / "scripts" / "phase7b5g_fixed_point_feedback_audit.py",
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
