from __future__ import annotations

import ast
import csv
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = (
    ROOT
    / "outputs"
    / "phase7b5t_preregistered_characteristic_transport_protocol.json"
)
SUMMARY = ROOT / "outputs" / "phase7b5t_characteristic_transport_summary.json"
RUNS = ROOT / "outputs" / "phase7b5t_characteristic_transport_runs.csv"
ERRORS = ROOT / "outputs" / "phase7b5t_characteristic_transport_errors.csv"
ANALYTIC = ROOT / "outputs" / "phase7b5t_analytic_spatial_convergence.csv"
EXPECTED_PROTOCOL_SHA256 = (
    "bd07fa6bc3007f3dd668baa2e205cb655364f6fa7e2af1959046f0c5cefc8400"
)


def _summary() -> dict[str, object]:
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_phase7b5t_protocol_is_frozen_and_scope_is_narrow() -> None:
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == (
        EXPECTED_PROTOCOL_SHA256
    )
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert len(protocol["configurations"]) == 7
    assert protocol["candidate_if_all_gates_pass"] == {
        "physical_frequency_groups": 9632,
        "angular_quadrature": "characteristic_split",
        "angular_direction_count": 32,
        "spatial_scheme": "step_characteristics",
        "radiation_subcells_per_parent": 16,
    }
    for key in (
        "full_column_authorized",
        "full_orbit_authorized",
        "matter_feedback_authorized",
        "phase4_replacement_authorized",
        "uvot_authorized",
    ):
        assert protocol["authorization"][key] is False


def test_phase7b5t_analytic_orders_and_exact_controls_pass() -> None:
    report = _summary()
    decision = report["decision"]
    assert decision["upwind_analytic_order_passed"] is True
    assert decision["step_analytic_order_passed"] is True
    assert decision["constant_source_analytic_passed"] is True
    assert decision["moving_grid_ledger_passed"] is True
    rows = report["analytic_spatial_convergence"]
    upwind = [
        row["observed_order_to_next"]
        for row in rows
        if row["spatial_scheme"] == "upwind_finite_volume"
        and row["observed_order_to_next"] is not None
    ]
    step = [
        row["observed_order_to_next"]
        for row in rows
        if row["spatial_scheme"] == "step_characteristics"
        and row["observed_order_to_next"] is not None
    ]
    assert upwind == pytest.approx([0.9999922209990582, 0.999999747035656])
    assert step == pytest.approx([1.9449944958368244, 1.9856128638717097])
    assert report["analytic_controls"][
        "constant_source_maximum_absolute_error"
    ] == 0.0


def test_phase7b5t_integrity_conservation_and_resources_pass() -> None:
    report = _summary()
    decision = report["decision"]
    for key in (
        "frozen_protocol_hash_passed",
        "frozen_source_hashes_passed",
        "all_workers_exit_zero",
        "fresh_worker_pid_each_configuration",
        "all_fixed_points_converged",
        "all_global_coupled_residuals_passed",
        "all_energy_ledger_residuals_passed",
        "all_intensities_nonnegative",
        "physical_group_count_exact",
        "edge_hash_unchanged",
        "resource_cap_passed",
        "characteristics_do_not_reverse_at_quadrature_nodes",
    ):
        assert decision[key] is True
    assert max(
        row["peak_process_rss_mib"] for row in report["runs"].values()
    ) == pytest.approx(2409.296875)


def test_phase7b5t_science_gate_accepts_declared_candidate() -> None:
    report = _summary()
    expected = {
        "split_angle_upwind": 1.7075683120254535e-05,
        "split_angle_step": 1.7275898123963078e-05,
        "upwind_depth": 0.007658839056691641,
        "step_depth_candidate": 0.00016496046060503295,
        "step_depth_confirmation": 4.388486261916119e-05,
        "joint_candidate": 0.0001738112856712297,
    }
    for key, value in expected.items():
        assert report["comparisons"][key]["maximum_error"] == pytest.approx(value)
    assert report["decision"]["required_science_comparisons_passed"] is True
    assert report["decision"]["phase7b5t_gate_passed"] is True
    assert report["accepted_one_cell_configuration"] == {
        "physical_frequency_groups": 9632,
        "angular_quadrature": "characteristic_split",
        "angular_direction_count": 32,
        "spatial_scheme": "step_characteristics",
        "radiation_subcells_per_parent": 16,
    }


def test_phase7b5t_tables_and_figure_are_complete() -> None:
    with RUNS.open(newline="", encoding="utf-8") as stream:
        assert len(list(csv.DictReader(stream))) == 7
    with ERRORS.open(newline="", encoding="utf-8") as stream:
        assert len(list(csv.DictReader(stream))) == 6 * 8
    with ANALYTIC.open(newline="", encoding="utf-8") as stream:
        assert len(list(csv.DictReader(stream))) == 6
    report = _summary()
    figure = ROOT / "outputs" / report["figures"][0]
    assert figure.is_file() and figure.stat().st_size > 0
    for document in (
        ROOT / "docs" / "phase7b5t_characteristic_transport_gate.md",
        ROOT / "lecture" / "项目整体讲义.md",
    ):
        text = document.read_text(encoding="utf-8")
        assert figure.name in text
        assert "怎么看" in text


def test_phase7b5t_uses_no_forbidden_numerical_repairs() -> None:
    for path in (
        ROOT / "src/eccentric_tde_observer/mixed_frame_ale.py",
        ROOT / "scripts/phase7b5t_characteristic_transport_gate.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        called_names = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        assert "nan_to_num" not in called_names
        assert "clip" not in called_names
