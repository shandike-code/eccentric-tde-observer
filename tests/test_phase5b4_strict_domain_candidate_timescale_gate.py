"""Phase 5B4 严格域候选进动时标与模形兼容门回归。"""

from __future__ import annotations

import ast
import csv
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def read_csv(filename: str) -> list[dict[str, str]]:
    with (OUTPUT / filename).open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_phase5b4_computes_candidate_but_keeps_atlas_time_gate_closed() -> None:
    report = json.loads(
        (
            OUTPUT / "phase5b4_strict_domain_candidate_timescale_report.json"
        ).read_text()
    )
    assert report["high_e_equation_internal_gate"]
    assert report["equation_self_consistent_candidate_timescale_computed"]
    assert not report["published_benchmark_gate"]
    assert not report["constant_e_atlas_shape_compatibility_gate"]
    assert not report["existing_atlas_phase_to_time_mapping_authorized"]
    assert report["maximum_relative_frequency_table_change"] < 1.0e-4
    assert report["maximum_relative_derivative_holdout_error"] < 1.0e-3
    assert not report["intermediate_31x61_derivative_gate_passed"]
    assert report["final_41x81_derivative_gate_passed"]
    assert report["maximum_relative_shape_difference_from_constant_e"] > 0.60


def test_phase5b4_candidate_periods_keep_both_normalizations_explicit() -> None:
    rows = read_csv("phase5b4_candidate_timescales.csv")
    assert len(rows) == 2
    assert {float(row["inner_eccentricity"]) for row in rows} == {0.60, 0.65}
    for row in rows:
        direct_period = float(row["direct_eq39_period_days"])
        printed_period = float(row["printed_eq48_period_days"])
        assert 1.4e4 < direct_period < 1.7e4
        assert 1.4e3 < printed_period < 1.7e3
        assert abs(
            float(row["printed_to_direct_frequency_ratio"])
            - 10.000861517298945
        ) < 1.0e-12
        assert float(row["outer_to_inner_eccentricity_ratio"]) < 0.40
        assert (
            float(row["maximum_relative_shape_difference_from_constant_e"])
            > 0.60
        )


def test_phase5b4_three_table_levels_and_solver_crosscheck_pass() -> None:
    table_rows = read_csv("phase5b4_high_e_table_convergence.csv")
    shooting_rows = read_csv("phase5b4_shooting_collocation.csv")
    derivative_rows = read_csv("phase5b4_high_e_derivative_holdout.csv")
    assert len(table_rows) == 6
    assert {
        (
            int(row["eccentricity_points"]),
            int(row["nonlinearity_points"]),
            int(row["anomaly_points"]),
        )
        for row in table_rows
    } == {(21, 41, 128), (31, 61, 192), (41, 81, 192)}
    assert len(shooting_rows) == 2
    assert max(
        float(row["relative_frequency_difference"]) for row in shooting_rows
    ) < 2.0e-8
    assert len(derivative_rows) == 6
    assert {row["location"] for row in derivative_rows} == {
        "inner",
        "middle",
        "outer",
    }
    assert max(
        float(row["relative_derivative_vector_error"])
        for row in derivative_rows
    ) < 1.0e-3
    resolution_rows = read_csv("phase5b4_derivative_resolution_audit.csv")
    assert len(resolution_rows) == 3
    assert [int(row["derivative_gate_passed"]) for row in resolution_rows] == [
        0,
        0,
        1,
    ]


def test_phase5b4_shape_threshold_sensitivity_all_fails() -> None:
    rows = read_csv("phase5b4_shape_threshold_sensitivity.csv")
    assert len(rows) == 6
    assert {float(row["relative_shape_threshold"]) for row in rows} == {
        0.02,
        0.05,
        0.10,
    }
    assert all(int(row["constant_e_atlas_shape_compatible"]) == 0 for row in rows)


def test_phase5b4_hamiltonian_caches_match_declared_grids() -> None:
    for eccentricity_points, nonlinearity_points, anomaly_points in (
        (21, 41, 128),
        (31, 61, 192),
        (41, 81, 192),
    ):
        path = OUTPUT / (
            f"phase5b4_hamiltonian_table_{eccentricity_points}x"
            f"{nonlinearity_points}_a{anomaly_points}.npz"
        )
        with np.load(path) as cache:
            assert cache["eccentricity_nodes"].shape == (eccentricity_points,)
            assert cache["nonlinearity_nodes"].shape == (nonlinearity_points,)
            assert cache["dimensionless_hamiltonian"].shape == (
                eccentricity_points,
                nonlinearity_points,
            )
            assert np.all(np.isfinite(cache["dimensionless_hamiltonian"]))


def test_phase5b4_figures_are_referenced_and_analyzed() -> None:
    filenames = (
        "phase5b4_mode_shape_compatibility.png",
        "phase5b4_candidate_timescale_ledger.png",
    )
    document = (
        ROOT / "docs/phase5b4_strict_domain_candidate_timescale_gate.md"
    ).read_text()
    lecture = (ROOT / "lecture/项目整体讲义.md").read_text()
    for filename in filenames:
        assert (OUTPUT / filename).stat().st_size > 0
        assert filename in document
        assert filename in lecture
    assert document.count("**怎么看。**") >= 2
    assert document.count("**不能证明什么。**") >= 2


def test_phase5b4_script_contains_no_numerical_repairs() -> None:
    tree = ast.parse(
        (
            ROOT / "scripts/phase5b4_strict_domain_candidate_timescale_gate.py"
        ).read_text()
    )
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert {"clip", "nan_to_num"}.isdisjoint(calls)
