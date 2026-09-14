from __future__ import annotations

import ast
import csv
import hashlib
import json
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = (
    PROJECT_ROOT
    / "outputs"
    / "phase7b5r_preregistered_joint_convergence_protocol.json"
)
SUMMARY = PROJECT_ROOT / "outputs" / "phase7b5r_joint_convergence_summary.json"
RUNS = PROJECT_ROOT / "outputs" / "phase7b5r_joint_convergence_runs.csv"
ERRORS = PROJECT_ROOT / "outputs" / "phase7b5r_joint_convergence_errors.csv"
EXPECTED_PROTOCOL_SHA256 = (
    "ff7a39925d5819d0267594a4221467ed211a634f3e5761b0575698d2c6675c0f"
)


def _summary() -> dict[str, object]:
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_phase7b5r_protocol_is_frozen_and_authorization_is_narrow() -> None:
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == (
        EXPECTED_PROTOCOL_SHA256
    )
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    configurations = {
        (
            row["angular_direction_count"],
            row["radiation_subcells_per_parent"],
        )
        for row in protocol["configurations"]
    }
    assert configurations == {
        (8, 1),
        (16, 1),
        (24, 1),
        (16, 8),
        (16, 16),
        (16, 32),
        (24, 32),
    }
    authorization = protocol["authorization"]
    assert authorization["frequency_budget_changed"] is True
    assert authorization["frequency_group_budget"] == 9632
    assert authorization["frequency_budget_authorized_by_user"] is True
    assert authorization["angle_or_radiation_subgrid_gate_authorized"] is True
    for key in (
        "full_column_authorized",
        "full_orbit_authorized",
        "matter_feedback_authorized",
        "phase4_replacement_authorized",
        "uvot_authorized",
    ):
        assert authorization[key] is False


def test_phase7b5r_all_fixed_points_and_integrity_gates_pass() -> None:
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
    ):
        assert decision[key] is True
    assert len({row["pid"] for row in report["runs"].values()}) == 7


def test_phase7b5r_science_gate_failure_is_retained() -> None:
    report = _summary()
    decision = report["decision"]
    assert decision["angle_candidate_vs_reference_all_observables_passed"] is False
    assert decision["subgrid_candidate_vs_reference_all_observables_passed"] is False
    assert decision["joint_candidate_vs_reference_all_observables_passed"] is False
    assert decision["phase7b5r_gate_passed"] is False
    assert report["accepted_one_cell_configuration"] is None
    expected = {
        "angle8_vs24": 0.03147531219942819,
        "angle16_vs24": 0.0054481238697124575,
        "subcell8_vs32": 0.04322074510659498,
        "subcell16_vs32": 0.014821803477944151,
        "joint16x16_vs24x32": 0.00958934821958872,
    }
    for key, value in expected.items():
        comparison = report["comparisons"][key]
        assert comparison["maximum_error"] == pytest.approx(value)
        assert comparison["worst_observable"] == "h_i_photoionization_rate_s1"


def test_phase7b5r_baseline_reproduces_phase7b5q_exactly() -> None:
    report = _summary()
    phase7b5q = json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5q_fixed_point_resource_summary.json")
        .read_text(encoding="utf-8")
    )
    assert report["runs"]["angle8_subcell1"]["result_sha256"] == (
        phase7b5q["aggregate"]["master"]["default_initial"]["result_sha256"]
    )


def test_phase7b5r_tables_keep_every_run_and_error() -> None:
    with RUNS.open(newline="", encoding="utf-8") as stream:
        runs = list(csv.DictReader(stream))
    with ERRORS.open(newline="", encoding="utf-8") as stream:
        errors = list(csv.DictReader(stream))
    assert len(runs) == 7
    assert len(errors) == 5 * 8
    assert {row["configuration_key"] for row in runs} == {
        "angle8_subcell1",
        "angle16_subcell1",
        "angle24_subcell1",
        "angle16_subcell8",
        "angle16_subcell16",
        "angle16_subcell32",
        "angle24_subcell32",
    }
    assert max(float(row["peak_process_rss_mib"]) for row in runs) > 1000.0


def test_phase7b5r_figure_and_documents_are_complete() -> None:
    report = _summary()
    figure = PROJECT_ROOT / "outputs" / report["figures"][0]
    assert figure.is_file() and figure.stat().st_size > 0
    for document in (
        PROJECT_ROOT / "docs" / "phase7b5r_joint_convergence.md",
        PROJECT_ROOT / "lecture" / "项目整体讲义.md",
    ):
        text = document.read_text(encoding="utf-8")
        assert figure.name in text
        assert "怎么看" in text


def test_phase7b5r_uses_no_forbidden_numerical_repairs() -> None:
    for source_name in (
        "phase7b5r_preregister_joint_convergence_protocol.py",
        "phase7b5r_joint_convergence.py",
    ):
        source = (PROJECT_ROOT / "scripts" / source_name).read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        called_names = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        assert "nan_to_num" not in called_names
        assert "clip" not in called_names
