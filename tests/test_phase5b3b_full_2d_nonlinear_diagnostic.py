"""Phase 5B3b 完整二维非线性分支诊断回归。"""

from __future__ import annotations

import ast
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def read_csv(filename: str) -> list[dict[str, str]]:
    with (OUTPUT / filename).open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_phase5b3b_internal_gate_passes_but_published_gate_fails() -> None:
    report = json.loads(
        (
            OUTPUT / "phase5b3b_full_2d_nonlinear_report.json"
        ).read_text()
    )
    assert report["equation_internal_gate"]
    assert not report["published_frequency_gate"]
    assert not report["published_profile_gate"]
    assert not report["full_2d_nonlinearity_explains_published_branch"]
    assert not report["formal_zo_source_model_changed"]
    assert not report["phase_to_time_mapping_authorized"]
    assert report["maximum_relative_quadratic_hessian_error"] < 1.0e-5
    assert report["maximum_relative_frequency_table_change"] < 1.0e-4
    assert report["maximum_relative_derivative_holdout_error"] < 1.0e-3


def test_phase5b3b_full_2d_stays_close_to_linear_control() -> None:
    rows = read_csv("phase5b3b_published_comparison.csv")
    assert len(rows) == 4
    assert {float(row["radius_ratio"]) for row in rows} == {
        1.3,
        2.0,
        3.0,
        4.0,
    }
    assert max(
        abs(float(row["nonlinear_minus_linear_frequency"]))
        for row in rows
    ) < 3.0e-3
    assert min(
        float(row["absolute_published_frequency_error"]) for row in rows
    ) > 0.20
    assert all(
        float(row["two_dimensional_nonlinear_frequency"]) < 0.0
        for row in rows
    )


def test_phase5b3b_retains_both_table_levels_and_holdouts() -> None:
    convergence = read_csv("phase5b3b_2d_table_convergence.csv")
    derivatives = read_csv("phase5b3b_2d_derivative_holdout.csv")
    assert len(convergence) == 8
    assert {
        (
            int(row["eccentricity_points"]),
            int(row["nonlinearity_points"]),
            int(row["anomaly_points"]),
        )
        for row in convergence
    } == {(21, 41, 256), (29, 65, 512)}
    assert max(
        abs(float(row["outer_boundary_residual"])) for row in convergence
    ) < 1.0e-8
    assert len(derivatives) == 6
    assert {row["location"] for row in derivatives} == {
        "inner",
        "middle",
        "outer",
    }
    assert max(
        float(row["relative_derivative_vector_error"])
        for row in derivatives
    ) < 1.0e-3


def test_phase5b3b_formula_limits_are_retained() -> None:
    quadratic = read_csv("phase5b3b_quadratic_limit.csv")
    quadrature = read_csv("phase5b3b_orbit_quadrature.csv")
    assert len(quadratic) == 4
    assert float(quadratic[-1]["relative_hessian_error"]) < 1.0e-7
    assert len(quadrature) == 12
    changes = [
        float(row["relative_change_from_previous"])
        for row in quadrature
        if row["relative_change_from_previous"]
    ]
    assert max(changes) < 1.0e-10


def test_phase5b3b_figure_is_referenced_and_analyzed() -> None:
    filename = "phase5b3b_full_2d_nonlinear_diagnostic.png"
    document = (
        ROOT / "docs/phase5b3b_full_2d_nonlinear_diagnostic.md"
    ).read_text()
    lecture = (ROOT / "lecture/项目整体讲义.md").read_text()
    assert (OUTPUT / filename).stat().st_size > 0
    assert filename in document
    assert filename in lecture
    assert "**怎么看。**" in document
    assert "**不能证明什么。**" in document


def test_phase5b3b_script_contains_no_numerical_repairs() -> None:
    tree = ast.parse(
        (
            ROOT / "scripts/phase5b3b_full_2d_nonlinear_diagnostic.py"
        ).read_text()
    )
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert {"clip", "nan_to_num"}.isdisjoint(calls)
