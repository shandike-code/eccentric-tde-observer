from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5m_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b5m_split_is_predeclared_disjoint_and_grid_is_frozen():
    report = _report()
    assert report["configuration"]["training_iterations"] == [0, 2, 4]
    assert report["configuration"]["validation_iterations"] == [1, 8]
    assert report["configuration"]["training_state_count"] == 9
    assert report["configuration"]["validation_state_count"] == 6
    decision = report["decision"]
    assert decision["training_validation_split_predeclared_and_disjoint"] is True
    assert decision["validation_spectra_used_for_grid_construction"] is False
    assert decision["frozen_grid_hash_unchanged_through_validation"] is True
    assert report["frozen_grid"]["sha256_before_validation"] == report[
        "frozen_grid"
    ]["sha256_after_validation"]


def test_phase7b5m_one_step_and_converged_operator_controls_pass():
    report = _report()
    decision = report["decision"]
    assert decision["all_one_step_mapping_and_rate_controls_passed"] is True
    assert decision[
        "all_converged_operator_energy_and_residual_controls_passed"
    ] is True
    assert decision["all_mapping_rate_energy_and_residual_controls_passed"] is True
    for row in report["converged_operator_controls"]:
        assert row["fixed_point_converged"] is True
        assert row["global_coupled_residual"] < 2.0e-8
        assert row["total_relative_energy_ledger_residual"] < 2.0e-8
        assert row["minimum_intensity"] >= 0.0


def test_phase7b5m_nested_master_passes_but_holdout_variable_fails_once():
    report = _report()
    decision = report["decision"]
    assert decision["nested_master_reference_gate_passed"] is True
    assert decision["training_H_I_rate_gate_passed"] is True
    assert decision["holdout_validation_H_I_rate_gate_passed"] is False
    failed = {
        (row["case"], row["input_iteration"])
        for row in report["state_results"]
        if row["split"] == "validation"
        and row["variable_absolute_H_I_rate_error"] >= 1.0e-3
    }
    assert failed == {("maximum width change", 8)}
    assert report["aggregate"]["maximum_validation_variable_error"] == (
        0.0010034682103447629
    )


def test_phase7b5m_budget_is_met_but_complete_efficiency_gate_fails():
    report = _report()
    decision = report["decision"]
    assert report["configuration"]["variable_leaf_group_count"] == 4814
    assert report["configuration"]["efficiency_group_limit"] == 4816
    assert decision["original_4816_group_budget_satisfied"] is True
    assert decision["original_4816_efficiency_gate_passed"] is False
    assert decision["one_cell_production_frequency_candidate_selected"] is False
    assert decision["production_frequency_representation_selected"] is False


def test_phase7b5m_resource_scope_is_smaller_but_not_peak_memory():
    report = _report()
    aggregate = report["aggregate"]
    assert aggregate["median_variable_one_cell_solve_runtime_s"] > 0.0
    assert aggregate["variable_returned_array_footprint_mib"] > 0.0
    assert aggregate["variable_N128_linear_returned_array_estimate_gib"] > 0.0
    assert any("not process peak memory" in item for item in report["open_items"])


def test_phase7b5m_keeps_all_downstream_gates_closed_after_holdout_failure():
    decision = _report()["decision"]
    assert decision["angular_radiation_subgrid_time_gate_authorized"] is False
    assert decision["full_dynamic_orbit_authorized"] is False
    assert decision["matter_temperature_population_feedback_authorized"] is False
    assert decision["phase4_replacement_authorized"] is False
    assert decision["uvot_authorized"] is False


def test_phase7b5m_uses_no_forbidden_repairs_or_validation_retraining():
    path = (
        PROJECT_ROOT
        / "scripts"
        / "phase7b5m_actual_multiresolution_validation.py"
    )
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = {
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert "np.nan_to_num" not in calls
    assert "np.clip" not in calls
    assert "numpy.nan_to_num" not in calls
    assert "numpy.clip" not in calls
    assert "TRAINING_ITERATIONS = (0, 2, 4)" in source
    assert "VALIDATION_ITERATIONS = (1, 8)" in source
    assert '"validation_spectra_used_for_grid_construction": False' in source
