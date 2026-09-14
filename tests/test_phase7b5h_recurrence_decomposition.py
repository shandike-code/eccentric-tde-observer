from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5h_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b5h_reproduces_maps_and_closes_scalar_ledger():
    report = _report()
    decision = report["decision"]
    assert decision["all_one_step_maps_reproduced_exactly"] is True
    assert decision["all_scalar_decompositions_closed"] is True
    for row in report["recurrence_decomposition"]:
        assert row["reference_one_step_reproduced_exactly"] is True
        assert row["candidate_one_step_reproduced_exactly"] is True
        assert row["decomposition_ledger_relative"] < 2.0e-12
        assert row["common_input_projection_energy_error"] < 2.0e-13
        assert row["localization_quadrature_relative_error"] < 2.0e-10
        fraction_sum = (
            row["absolute_injection_fraction_of_component_sum"]
            + row["absolute_propagation_fraction_of_component_sum"]
        )
        assert abs(fraction_sum - 1.0) < 2.0e-15


def test_phase7b5h_common_input_injection_dominates_both_moving_cases():
    report = _report()
    decision = report["decision"]
    assert decision["dominant_contribution_by_moving_case"] == {
        "maximum cell speed": "injection",
        "maximum width change": "injection",
    }
    assert decision["same_dominant_contribution_in_both_moving_cases"] is True
    moving = [
        row
        for row in report["recurrence_decomposition"]
        if row["case"] in {"maximum cell speed", "maximum width change"}
    ]
    assert min(
        row["absolute_injection_fraction_of_component_sum"] for row in moving
    ) > 0.90
    assert decision["common_input_injection_audit_authorized"] is True
    assert decision["propagation_jacobian_vector_audit_authorized"] is False
    assert decision["mixed_recurrence_audit_required"] is False


def test_phase7b5h_diagnostic_one_step_outputs_are_not_mislabelled_converged():
    for row in _report()["recurrence_decomposition"]:
        assert row["common_candidate_fixed_point_converged"] is False
        assert row["actual_candidate_fixed_point_converged"] is False
        assert row["reference_fixed_point_converged"] is False


def test_phase7b5h_injection_localization_is_a_complete_nonnegative_partition():
    rows = _report()["injection_region_evolution"]
    keys = sorted({(row["case"], row["input_iteration"]) for row in rows})
    for key in keys:
        selected = [
            row
            for row in rows
            if (row["case"], row["input_iteration"]) == key
        ]
        assert all(
            0.0 <= row["absolute_injection_difference_fraction"] <= 1.0
            for row in selected
        )
        assert abs(
            sum(row["absolute_injection_difference_fraction"] for row in selected)
            - 1.0
        ) < 2.0e-13


def test_phase7b5h_uses_no_forbidden_repairs_or_hidden_production_approval():
    paths = (
        PROJECT_ROOT / "src" / "eccentric_tde_observer" / "mixed_frame_ale.py",
        PROJECT_ROOT
        / "src"
        / "eccentric_tde_observer"
        / "mixed_frame_ale_log_p1.py",
        PROJECT_ROOT / "scripts" / "phase7b5h_recurrence_decomposition.py",
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
