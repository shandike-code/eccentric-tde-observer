from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5j_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b5j_grid_projection_and_rate_controls_pass():
    report = _report()
    assert report["decision"]["all_grid_projection_and_rate_controls_passed"] is True
    for row in report["grid_audit"]:
        assert row["strictly_increasing"] is True
        assert row["H_I_threshold_exact"] is True
        if row["strategy"] == "doppler_image_anchors":
            assert row["H_I_doppler_upper_exact"] is True
    for row in report["state_checkpoint_errors"]:
        assert row["reference_one_step_reproduced_exactly"] is True
        assert row["projection_energy_error"] < 2.0e-13
        assert row["localization_quadrature_relative_error"] < 2.0e-10
        assert row["fixed_point_converged"] is False


def test_phase7b5j_no_strategy_passes_inside_efficiency_budget():
    decision = _report()["decision"]
    assert decision["budget_passing_level_by_strategy"] == {
        "uniform_log": False,
        "rate_kernel": False,
        "doppler_image_anchors": False,
    }
    assert decision["no_partition_passes_within_efficiency_budget"] is True
    assert decision["production_frequency_representation_selected"] is False


def test_phase7b5j_only_two_nonuniform_strategies_pass_at_9632_groups():
    decision = _report()["decision"]
    assert decision["passing_group_levels_by_strategy"] == {
        "uniform_log": [],
        "rate_kernel": [9632],
        "doppler_image_anchors": [9632],
    }
    assert decision["adjacent_passing_levels_by_strategy"] == {
        "uniform_log": False,
        "rate_kernel": False,
        "doppler_image_anchors": False,
    }
    assert decision["at_least_one_partition_passes_above_budget"] is True
    assert decision["frequency_compression_audit_authorized"] is True


def test_phase7b5j_doppler_anchors_are_not_robustly_preferred():
    report = _report()
    assert report["decision"]["doppler_anchor_partition_robustly_preferred"] is False
    convergence = report["convergence"]
    rate_kernel = next(
        row
        for row in convergence
        if row["strategy"] == "rate_kernel"
        and row["physical_frequency_groups"] == 9632
    )
    doppler = next(
        row
        for row in convergence
        if row["strategy"] == "doppler_image_anchors"
        and row["physical_frequency_groups"] == 9632
    )
    assert rate_kernel["maximum_all_state_checkpoint_error"] < 1.0e-3
    assert doppler["maximum_all_state_checkpoint_error"] < 1.0e-3


def test_phase7b5j_region_rows_form_complete_nonnegative_partitions():
    rows = _report()["region_evolution"]
    keys = sorted(
        {
            (
                row["case"],
                row["input_iteration"],
                row["strategy"],
                row["physical_frequency_groups"],
            )
            for row in rows
        }
    )
    for key in keys:
        selected = [
            row
            for row in rows
            if (
                row["case"],
                row["input_iteration"],
                row["strategy"],
                row["physical_frequency_groups"],
            )
            == key
        ]
        assert all(
            0.0 <= row["absolute_difference_fraction"] <= 1.0
            for row in selected
        )
        assert abs(
            sum(row["absolute_difference_fraction"] for row in selected)
            - 1.0
        ) < 2.0e-13


def test_phase7b5j_uses_no_forbidden_repairs_or_hidden_production_approval():
    path = PROJECT_ROOT / "scripts" / "phase7b5j_prescribed_partition_audit.py"
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
    assert '"production_frequency_representation_selected": False' in source
    assert '"targeted_operator_remediation_authorized": False' in source
    assert '"full_dynamic_orbit_authorized": False' in source
    assert '"phase4_replacement_authorized": False' in source
    assert '"uvot_authorized": False' in source
