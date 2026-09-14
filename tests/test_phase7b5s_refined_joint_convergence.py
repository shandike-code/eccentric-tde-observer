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
    / "phase7b5s_preregistered_refined_joint_protocol.json"
)
SUMMARY = PROJECT_ROOT / "outputs" / "phase7b5s_refined_joint_summary.json"
RUNS = PROJECT_ROOT / "outputs" / "phase7b5s_refined_joint_runs.csv"
ERRORS = PROJECT_ROOT / "outputs" / "phase7b5s_refined_joint_errors.csv"
EXPECTED_PROTOCOL_SHA256 = (
    "ac1d65d0d7b66b03545dd7cfc3e93e6e43bd3aa9fe66af71f9853eae7cbd75a2"
)


def _summary() -> dict[str, object]:
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_phase7b5s_protocol_is_frozen_and_authorization_is_narrow() -> None:
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
        (24, 32),
        (32, 32),
        (48, 32),
        (32, 64),
        (48, 64),
    }
    assert protocol["gates"]["fresh_process_peak_rss_strictly_below_mib"] == (
        6144.0
    )
    authorization = protocol["authorization"]
    assert authorization["frequency_group_budget"] == 9632
    assert authorization["frequency_budget_authorized_by_user"] is True
    assert authorization["refined_angle_or_radiation_subgrid_gate_authorized"] is True
    for key in (
        "full_column_authorized",
        "full_orbit_authorized",
        "matter_feedback_authorized",
        "phase4_replacement_authorized",
        "uvot_authorized",
    ):
        assert authorization[key] is False


def test_phase7b5s_fixed_points_integrity_and_resource_gates_pass() -> None:
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
    ):
        assert decision[key] is True
    assert len({row["pid"] for row in report["runs"].values()}) == 5
    assert max(
        row["peak_process_rss_mib"] for row in report["runs"].values()
    ) == pytest.approx(2876.0)


def test_phase7b5s_science_gate_failure_is_retained() -> None:
    report = _summary()
    decision = report["decision"]
    assert decision["angle_candidate_vs_reference_all_observables_passed"] is False
    assert decision["subgrid_candidate_vs_reference_all_observables_passed"] is False
    assert decision["joint_candidate_vs_reference_all_observables_passed"] is False
    assert decision["phase7b5s_gate_passed"] is False
    assert report["accepted_one_cell_configuration"] is None
    expected = {
        "angle24_vs48": 0.002944850025359245,
        "angle32_vs48": 0.0012213897742264274,
        "subcell32_vs64": 0.007625752966055371,
        "joint32x32_vs48x64": 0.006428363798583168,
    }
    for key, value in expected.items():
        comparison = report["comparisons"][key]
        assert comparison["maximum_error"] == pytest.approx(value)
        assert comparison["worst_observable"] == "h_i_photoionization_rate_s1"


def test_phase7b5s_coarse_control_reproduces_phase7b5r_exactly() -> None:
    report = _summary()
    phase7b5r = json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5r_joint_convergence_summary.json")
        .read_text(encoding="utf-8")
    )
    assert report["runs"]["angle24_subcell32"]["result_sha256"] == (
        phase7b5r["runs"]["angle24_subcell32"]["result_sha256"]
    )


def test_phase7b5s_tables_keep_every_run_and_error() -> None:
    with RUNS.open(newline="", encoding="utf-8") as stream:
        runs = list(csv.DictReader(stream))
    with ERRORS.open(newline="", encoding="utf-8") as stream:
        errors = list(csv.DictReader(stream))
    assert len(runs) == 5
    assert len(errors) == 4 * 8
    assert {row["configuration_key"] for row in runs} == {
        "angle24_subcell32",
        "angle32_subcell32",
        "angle48_subcell32",
        "angle32_subcell64",
        "angle48_subcell64",
    }


def test_phase7b5s_figure_and_documents_are_complete() -> None:
    report = _summary()
    figure = PROJECT_ROOT / "outputs" / report["figures"][0]
    assert figure.is_file() and figure.stat().st_size > 0
    for document in (
        PROJECT_ROOT / "docs" / "phase7b5s_refined_joint_convergence.md",
        PROJECT_ROOT / "lecture" / "项目整体讲义.md",
    ):
        text = document.read_text(encoding="utf-8")
        assert figure.name in text
        assert "怎么看" in text


def test_phase7b5s_uses_no_forbidden_numerical_repairs() -> None:
    for source_name in (
        "phase7b5s_preregister_refined_joint_protocol.py",
        "phase7b5s_refined_joint_convergence.py",
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
