from __future__ import annotations

import ast
import csv
import hashlib
import json
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes


PROTOCOL = (
    PROJECT_ROOT / "outputs" / "phase7b5p_preregistered_resource_protocol.json"
)
SUMMARY = (
    PROJECT_ROOT / "outputs" / "phase7b5p_resource_profile_summary.json"
)
RUNS = PROJECT_ROOT / "outputs" / "phase7b5p_isolated_resource_runs.csv"
EXPECTED_PROTOCOL_SHA256 = (
    "3ccb468e24def10262489a2c02d8124a103ec1fd2aeae035b4b05e7cb164201c"
)
EXPECTED_CANDIDATE_EDGE_SHA256 = (
    "2f905d8ad0df879df3cba4311921a37233f082d5022e1630ace1934f8053bad7"
)


def _summary() -> dict[str, object]:
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_phase7b5p_ru_maxrss_unit_conversion_is_explicit() -> None:
    assert ru_maxrss_to_bytes(1024, "darwin") == 1024
    assert ru_maxrss_to_bytes(1024, "linux") == 1024**2
    assert ru_maxrss_to_bytes(1024, "freebsd13") == 1024**2
    with pytest.raises(RuntimeError, match="unsupported"):
        ru_maxrss_to_bytes(1024, "unknown")


def test_phase7b5p_protocol_remains_frozen_and_does_not_change_budget() -> None:
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == (
        EXPECTED_PROTOCOL_SHA256
    )
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["measurement"]["repeat_count_per_representation"] == 5
    assert protocol["measurement"]["worker_order"] == [
        "candidate",
        "master",
        "master",
        "candidate",
        "candidate",
        "master",
        "master",
        "candidate",
        "candidate",
        "master",
    ]
    assert protocol["representations"][0]["physical_group_count"] == 4816
    assert protocol["representations"][0]["active_edge_sha256"] == (
        EXPECTED_CANDIDATE_EDGE_SHA256
    )
    assert protocol["representations"][1]["physical_group_count"] == 9632
    assert all(value is False for value in protocol["authorization"].values())


def test_phase7b5p_all_fresh_workers_and_hash_controls_pass() -> None:
    report = _summary()
    decision = report["decision"]
    for key in (
        "frozen_protocol_hash_passed",
        "frozen_source_hashes_passed",
        "candidate_edge_hash_unchanged",
        "all_workers_exit_zero",
        "fresh_worker_pid_each_run",
        "deterministic_result_hash_within_representation",
        "returned_array_bytes_match_phase7b5o",
    ):
        assert decision[key] is True
    for key in (
        "frequency_budget_changed",
        "angle_or_radiation_subgrid_gate_authorized",
        "full_orbit_authorized",
        "matter_feedback_authorized",
        "phase4_replacement_authorized",
        "uvot_authorized",
    ):
        assert decision[key] is False

    with RUNS.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 10
    assert len({row["worker_pid"] for row in rows}) == 10
    assert sum(row["representation_key"] == "candidate" for row in rows) == 5
    assert sum(row["representation_key"] == "master" for row in rows) == 5
    for key in ("candidate", "master"):
        assert len(
            {
                row["result_sha256"]
                for row in rows
                if row["representation_key"] == key
            }
        ) == 1


def test_phase7b5p_measures_expected_resource_order_without_hiding_maxima() -> None:
    aggregate = _summary()["aggregate"]
    candidate = aggregate["candidate"]
    master = aggregate["master"]
    assert candidate["repeat_count"] == master["repeat_count"] == 5
    assert candidate["returned_array_mib"] == pytest.approx(2.1313095092773438)
    assert master["returned_array_mib"] == pytest.approx(4.262413024902344)
    assert aggregate["master_to_candidate_returned_array_ratio"] == pytest.approx(
        2.0, rel=1e-4
    )
    assert master["median_peak_process_rss_mib"] > candidate[
        "median_peak_process_rss_mib"
    ]
    assert master["median_operator_highwater_increase_mib"] > candidate[
        "median_operator_highwater_increase_mib"
    ]
    assert master["median_operator_runtime_s"] > candidate[
        "median_operator_runtime_s"
    ]
    assert candidate["maximum_peak_process_rss_mib"] >= candidate[
        "median_peak_process_rss_mib"
    ]
    assert master["maximum_peak_process_rss_mib"] >= master[
        "median_peak_process_rss_mib"
    ]


def test_phase7b5p_reference_is_converged_but_measured_map_is_one_step() -> None:
    report = _summary()
    control = report["reference_source_control"]
    assert control["fixed_point_converged"] is True
    assert control["global_coupled_residual"] < 1e-9
    assert control["total_energy_ledger_residual"] < 1e-9
    assert control["minimum_intensity"] == 0.0
    assert {run["fixed_point_iterations"] for run in report["runs"]} == {1}
    assert "one diagnostic fixed-point map" in report["interpretation"]
    assert "not a convergence gate" in report["interpretation"]


def test_phase7b5p_figure_is_referenced_and_forbidden_repairs_are_absent() -> None:
    figure = PROJECT_ROOT / "outputs" / _summary()["figure"]
    assert figure.is_file() and figure.stat().st_size > 0
    figure_name = figure.name
    for document in (
        PROJECT_ROOT / "docs" / "phase7b5p_isolated_resource_profile.md",
        PROJECT_ROOT / "lecture" / "项目整体讲义.md",
    ):
        text = document.read_text(encoding="utf-8")
        assert figure_name in text
        assert "怎么看" in text

    for source_name in (
        "phase7b5p_preregister_resource_protocol.py",
        "phase7b5p_isolated_resource_profile.py",
    ):
        source = (SCRIPTS / source_name).read_text(encoding="utf-8")
        tree = ast.parse(source)
        called_names = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        assert "nan_to_num" not in called_names
        assert "clip" not in called_names

