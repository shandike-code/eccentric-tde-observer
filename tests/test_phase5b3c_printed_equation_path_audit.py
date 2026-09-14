"""Phase 5B3c 印刷方程路径与边界审计回归。"""

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


def test_phase5b3c_rejects_printed_appendix_sign_as_explanation() -> None:
    report = json.loads(
        (
            OUTPUT / "phase5b3c_printed_equation_path_report.json"
        ).read_text()
    )
    assert report["equation_variant_internal_gate"]
    assert not report["printed_appendix_sign_explains_published_branch"]
    assert not report[
        "published_vector_all_inner_tangents_satisfy_declared_3d_free_boundary"
    ]
    assert not report["formal_zo_source_model_changed"]
    assert not report["phase_to_time_mapping_authorized"]
    assert report["maximum_relative_frequency_table_change"] < 1.0e-4
    assert (
        report[
            "appendix_path_maximum_absolute_published_frequency_error"
        ]
        > 1.0
    )


def test_phase5b3c_keeps_both_printed_paths_and_table_levels() -> None:
    rows = read_csv("phase5b3c_equation_variant_convergence.csv")
    assert len(rows) == 8
    assert {row["printed_equation_path"] for row in rows} == {
        "main_plus",
        "appendix_minus",
    }
    assert {
        (int(row["eccentricity_points"]), int(row["nonlinearity_points"]))
        for row in rows
    } == {(31, 61), (41, 81)}
    fine = [row for row in rows if int(row["eccentricity_points"]) == 41]
    assert all(
        float(row["dimensionless_frequency"]) > 0.0
        for row in fine
        if row["printed_equation_path"] == "main_plus"
    )
    assert all(
        float(row["dimensionless_frequency"]) < 0.0
        for row in fine
        if row["printed_equation_path"] == "appendix_minus"
    )
    assert max(
        float(row["profile_max_error_over_inner_e"])
        for row in fine
        if row["printed_equation_path"] == "appendix_minus"
    ) > 0.30


def test_phase5b3c_source_ledger_retains_literal_inconsistencies() -> None:
    rows = read_csv("phase5b3c_printed_equation_ledger.csv")
    assert len(rows) == 5
    classification = {row["audit_classification"] for row in rows}
    assert "internal sign mismatch" in classification
    assert "reciprocal caption typo" in classification
    assert "normalization mismatch retained from Phase 5B4" in classification


def test_phase5b3c_vector_tangent_audit_separates_inner_and_outer() -> None:
    rows = read_csv("phase5b3c_published_boundary_tangents.csv")
    assert len(rows) == 12
    inner = [row for row in rows if row["boundary"] == "inner"]
    assert all(
        abs(
            float(row["inferred_orbital_nonlinearity"])
            - float(row["required_three_dimensional_free_q"])
        )
        > 0.10
        for row in inner
    )
    outer_two_point = [
        row
        for row in rows
        if row["boundary"] == "outer"
        and int(row["linear_fit_point_count"]) == 2
    ]
    assert len(outer_two_point) == 2
    assert all(
        abs(
            float(row["inferred_orbital_nonlinearity"])
            - float(row["required_three_dimensional_free_q"])
        )
        < 3.0e-3
        for row in outer_two_point
    )


def test_phase5b3c_figure_is_referenced_and_analyzed() -> None:
    filename = "phase5b3c_printed_equation_path_audit.png"
    document = (
        ROOT / "docs/phase5b3c_printed_equation_path_audit.md"
    ).read_text()
    lecture = (ROOT / "lecture/项目整体讲义.md").read_text()
    assert (OUTPUT / filename).stat().st_size > 0
    assert filename in document
    assert filename in lecture
    assert "**怎么看。**" in document
    assert "**不能证明什么。**" in document


def test_phase5b3c_script_contains_no_numerical_repairs() -> None:
    tree = ast.parse(
        (
            ROOT / "scripts/phase5b3c_printed_equation_path_audit.py"
        ).read_text()
    )
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert {"clip", "nan_to_num"}.isdisjoint(calls)
