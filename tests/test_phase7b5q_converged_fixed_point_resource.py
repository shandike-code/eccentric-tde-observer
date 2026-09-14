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
    / "phase7b5q_preregistered_fixed_point_resource_protocol.json"
)
SUMMARY = (
    PROJECT_ROOT / "outputs" / "phase7b5q_fixed_point_resource_summary.json"
)
RUNS = PROJECT_ROOT / "outputs" / "phase7b5q_fixed_point_resource_runs.csv"
EXPECTED_PROTOCOL_SHA256 = (
    "055005e2d3285744be531c06a0f08cea02f22de6af9979fce3dbc2d754b04143"
)


def _summary() -> dict[str, object]:
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_phase7b5q_protocol_is_frozen_and_balanced() -> None:
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == (
        EXPECTED_PROTOCOL_SHA256
    )
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["measurement"][
        "repeat_count_per_representation_and_start"
    ] == 5
    order = protocol["measurement"]["worker_order"]
    assert len(order) == 20
    configurations = [
        (row["representation"], row["start_mode"]) for row in order
    ]
    assert {
        configuration: configurations.count(configuration)
        for configuration in set(configurations)
    } == {
        ("candidate", "projected_converged"): 5,
        ("candidate", "default_initial"): 5,
        ("master", "projected_converged"): 5,
        ("master", "default_initial"): 5,
    }
    assert protocol["gates"][
        "cross_start_final_intensity_relative_difference_strictly_below"
    ] == 1e-8
    assert all(value is False for value in protocol["authorization"].values())


def test_phase7b5q_all_workers_and_fixed_point_gates_pass() -> None:
    report = _summary()
    decision = report["decision"]
    for key in (
        "frozen_protocol_hash_passed",
        "frozen_source_hashes_passed",
        "all_workers_exit_zero",
        "fresh_worker_pid_each_run",
        "all_fixed_points_converged",
        "all_global_coupled_residuals_passed",
        "all_energy_ledger_residuals_passed",
        "all_intensities_nonnegative",
        "cross_start_final_intensity_passed",
        "deterministic_result_hash_within_configuration",
        "edge_hashes_unchanged",
    ):
        assert decision[key] is True
    for key in (
        "frequency_budget_changed",
        "angle_or_radiation_subgrid_gate_authorized",
        "full_column_authorized",
        "full_orbit_authorized",
        "matter_feedback_authorized",
        "phase4_replacement_authorized",
        "uvot_authorized",
    ):
        assert decision[key] is False


def test_phase7b5q_fresh_process_ledger_is_complete_and_deterministic() -> None:
    with RUNS.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 20
    assert len({row["worker_pid"] for row in rows}) == 20
    for representation in ("candidate", "master"):
        for start_mode in ("projected_converged", "default_initial"):
            selected = [
                row
                for row in rows
                if row["representation_key"] == representation
                and row["start_mode"] == start_mode
            ]
            assert len(selected) == 5
            assert len({row["result_sha256"] for row in selected}) == 1
            assert {row["fixed_point_converged"] for row in selected} == {
                "True"
            }


def test_phase7b5q_two_starts_reach_same_fixed_point() -> None:
    report = _summary()
    cross_start = report["cross_start_final_intensity_relative_difference"]
    assert cross_start["candidate"] == pytest.approx(2.0807233134843543e-10)
    assert cross_start["master"] == pytest.approx(1.9852085665051816e-10)
    for representation in ("candidate", "master"):
        aggregate = report["aggregate"][representation]
        assert aggregate["projected_converged"]["fixed_point_iterations"] == [
            29
        ]
        assert aggregate["default_initial"]["fixed_point_iterations"] == [43]
        for start_mode in ("projected_converged", "default_initial"):
            result = aggregate[start_mode]
            assert result["maximum_global_coupled_residual"] < 1e-9
            assert result["maximum_absolute_energy_ledger_residual"] < 1e-9
            assert result["minimum_intensity"] == 0.0


def test_phase7b5q_resource_order_and_all_maxima_are_retained() -> None:
    report = _summary()
    for start_mode in ("projected_converged", "default_initial"):
        candidate = report["aggregate"]["candidate"][start_mode]
        master = report["aggregate"]["master"][start_mode]
        assert master["median_peak_process_rss_mib"] > candidate[
            "median_peak_process_rss_mib"
        ]
        assert master["median_operator_highwater_increase_mib"] > candidate[
            "median_operator_highwater_increase_mib"
        ]
        assert master["median_operator_runtime_s"] > candidate[
            "median_operator_runtime_s"
        ]
        for result in (candidate, master):
            assert result["maximum_peak_process_rss_mib"] >= result[
                "median_peak_process_rss_mib"
            ]
            assert result["maximum_operator_runtime_s"] >= result[
                "median_operator_runtime_s"
            ]
    assert report["aggregate"]["master"]["projected_converged"][
        "maximum_peak_process_rss_mib"
    ] == 209.4375


def test_phase7b5q_figure_and_documents_are_complete() -> None:
    report = _summary()
    figure = PROJECT_ROOT / "outputs" / report["figure"]
    assert figure.is_file() and figure.stat().st_size > 0
    for document in (
        PROJECT_ROOT / "docs" / "phase7b5q_converged_fixed_point_resource.md",
        PROJECT_ROOT / "lecture" / "项目整体讲义.md",
    ):
        text = document.read_text(encoding="utf-8")
        assert figure.name in text
        assert "怎么看" in text


def test_phase7b5q_uses_no_forbidden_numerical_repairs() -> None:
    for source_name in (
        "phase7b5q_preregister_fixed_point_resource_protocol.py",
        "phase7b5q_converged_fixed_point_resource.py",
    ):
        source = (
            PROJECT_ROOT / "scripts" / source_name
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        called_names = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        assert "nan_to_num" not in called_names
        assert "clip" not in called_names

