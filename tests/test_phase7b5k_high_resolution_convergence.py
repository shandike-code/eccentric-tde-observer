from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5k_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b5k_mapping_rate_and_reference_controls_pass():
    report = _report()
    decision = report["decision"]
    assert decision["all_projection_mapping_and_rate_controls_passed"] is True
    assert decision["phase7b5j_9632_reproduced"] is True
    assert (
        report["phase7b5j_9632_reproduction_maximum_absolute_difference"]
        < 5.0e-14
    )
    assert len(report["state_checkpoint_errors"]) == 60
    for row in report["state_checkpoint_errors"]:
        assert row["reference_one_step_reproduced_exactly"] is True
        assert row["projection_energy_error"] < 2.0e-13
        assert row["localization_quadrature_relative_error"] < 2.0e-10
        assert row["fixed_point_converged"] is False


def test_phase7b5k_both_predeclared_partitions_pass_adjacent_levels():
    report = _report()
    decision = report["decision"]
    assert decision["adjacent_passing_levels_by_strategy"] == {
        "rate_kernel": True,
        "doppler_image_anchors": True,
    }
    assert decision["high_resolution_finite_reference_confirmed"] is True
    for row in report["convergence"]:
        assert row["all_state_checkpoint_rate_gate_passed"] is True
        assert row["maximum_all_state_checkpoint_error"] < 1.0e-3


def test_phase7b5k_resource_scope_and_scaling_are_explicit():
    report = _report()
    assert "excludes transient and process peak memory" in report[
        "configuration"
    ]["resource_scope"]
    assert report["configuration"]["N128_linear_estimate_depth_cells"] == 128
    aggregate = report["resource_aggregate"]
    for strategy in ("rate_kernel", "doppler_image_anchors"):
        low = next(
            row
            for row in aggregate
            if row["strategy"] == strategy
            and row["physical_frequency_groups"] == 9632
        )
        high = next(
            row
            for row in aggregate
            if row["strategy"] == strategy
            and row["physical_frequency_groups"] == 19264
        )
        assert low["sample_count"] == high["sample_count"] == 15
        assert low["median_solve_runtime_s"] > 0.0
        assert high["median_solve_runtime_s"] > 0.0
        assert high["returned_array_footprint_bytes"] > low[
            "returned_array_footprint_bytes"
        ]
        assert high["N128_linear_returned_array_estimate_gib"] > low[
            "N128_linear_returned_array_estimate_gib"
        ]


def test_phase7b5k_does_not_revise_efficiency_or_open_downstream_gates():
    decision = _report()["decision"]
    assert decision["original_4816_efficiency_gate_passed"] is False
    assert decision["efficiency_budget_revision_authorized"] is False
    assert decision["closed_frequency_compression_design_authorized"] is True
    assert decision["production_frequency_representation_selected"] is False
    assert decision["targeted_operator_remediation_authorized"] is False
    assert decision["angular_radiation_subgrid_time_gate_authorized"] is False
    assert decision["full_dynamic_orbit_authorized"] is False
    assert decision["matter_temperature_population_feedback_authorized"] is False
    assert decision["phase4_replacement_authorized"] is False
    assert decision["uvot_authorized"] is False


def test_phase7b5k_uses_no_forbidden_repairs_or_hidden_budget_threshold():
    path = (
        PROJECT_ROOT
        / "scripts"
        / "phase7b5k_high_resolution_convergence.py"
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
    assert "RUNTIME_TARGET" not in source
    assert "MEMORY_TARGET" not in source
    assert '"efficiency_budget_revision_authorized": False' in source
    assert '"production_frequency_representation_selected": False' in source
