"""Phase 5B3a 已发表分支反演审计的回归测试。"""

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


def test_phase5b3a_keeps_time_mapping_closed() -> None:
    report = json.loads(
        (
            OUTPUT / "phase5b3a_published_branch_inverse_audit_report.json"
        ).read_text()
    )
    assert report["continuation_state_count"] == 18
    assert report["node_free_branch_stays_finite_and_positive"]
    assert not report["published_branch_reproduced"]
    assert report["inverse_e_like_discrepancy_is_diagnostic_only"]
    assert not report["branch_tracking_explains_published_curve"]
    assert not report["phase_to_time_mapping_authorized"]
    assert report["minimum_three_dimensional_nonlinear_frequency"] > 1.0
    assert report["maximum_absolute_outer_boundary_residual"] < 1.0e-8
    assert (
        report["maximum_strong_galerkin_node_free_relative_difference"]
        < 1.0e-5
    )


def test_phase5b3a_continuation_retains_all_digitized_states() -> None:
    rows = read_csv("phase5b3a_published_frequency_continuation.csv")
    assert len(rows) == 18
    assert {float(row["radius_ratio"]) for row in rows} == {1.3, 2.0, 4.0}
    assert {float(row["inner_eccentricity"]) for row in rows} == {
        0.10,
        0.15,
        0.1918332609,
        0.20,
        0.25,
        0.30,
    }
    assert all(int(row["radial_node_count"]) == 0 for row in rows)
    assert all(
        float(row["three_dimensional_nonlinear_frequency"]) > 0.0
        for row in rows
    )
    assert any(float(row["published_frequency_digitized"]) < 0.0 for row in rows)


def test_phase5b3a_inverse_e_pattern_is_not_promoted_to_a_cause() -> None:
    rows = read_csv("phase5b3a_inverse_bias_fit.csv")
    assert len(rows) == 3
    assert min(float(row["r_squared"]) for row in rows) > 0.95
    assert max(
        float(row["scaled_discrepancy_coefficient_of_variation"])
        for row in rows
    ) > 0.15
    report = json.loads(
        (
            OUTPUT / "phase5b3a_published_branch_inverse_audit_report.json"
        ).read_text()
    )
    assert report["inverse_e_like_discrepancy_is_diagnostic_only"]


def test_phase5b3a_retains_rejected_frequency_guesses() -> None:
    rows = read_csv("phase5b3a_frequency_guess_robustness.csv")
    assert len(rows) == 10
    rejected = [row for row in rows if row["status"] == "rejected"]
    converged = [row for row in rows if row["status"] == "converged"]
    assert len(rejected) == 3
    assert all("outside the tabulated" in row["rejection_reason"] for row in rejected)
    assert len(converged) == 7
    for radius_ratio in (1.3, 4.0):
        frequencies = [
            float(row["converged_frequency"])
            for row in converged
            if float(row["radius_ratio"]) == radius_ratio
        ]
        assert max(frequencies) - min(frequencies) < 1.0e-6


def test_phase5b3a_linear_branch_node_topology() -> None:
    rows = read_csv("phase5b3a_linear_branch_spectrum.csv")
    assert len(rows) == 32
    strong = [row for row in rows if row["method"] == "strong_form"]
    galerkin = [row for row in rows if row["method"] == "galerkin"]
    assert len(strong) == 8
    assert len(galerkin) == 24
    assert all(int(row["radial_node_count"]) == 0 for row in strong)
    assert all(
        1.0 < float(row["dimensionless_frequency"]) < 3.0 for row in strong
    )
    higher = [row for row in galerkin if int(row["radial_node_count"]) > 0]
    assert all(float(row["dimensionless_frequency"]) < 0.0 for row in higher)
    node_one = sorted(
        (
            float(row["annulus_fractional_width"]),
            abs(float(row["dimensionless_frequency"])),
        )
        for row in higher
        if int(row["radial_node_count"]) == 1
    )
    assert node_one[0][1] > 1.0e6
    assert node_one[-1][1] < 2.0


def test_phase5b3a_figures_are_referenced_and_analyzed() -> None:
    filenames = (
        "phase5b3a_published_branch_inverse_audit.png",
        "phase5b3a_linear_branch_topology.png",
    )
    document = (
        ROOT / "docs/phase5b3a_published_branch_inverse_audit.md"
    ).read_text()
    lecture = (ROOT / "lecture/项目整体讲义.md").read_text()
    for filename in filenames:
        assert (OUTPUT / filename).stat().st_size > 0
        assert filename in document
        assert filename in lecture
    assert document.count("**怎么看。**") >= 2
    assert document.count("**不能证明什么。**") >= 2


def test_phase5b3a_script_contains_no_numerical_repairs() -> None:
    tree = ast.parse(
        (
            ROOT / "scripts/phase5b3a_published_branch_inverse_audit.py"
        ).read_text()
    )
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert {"clip", "nan_to_num"}.isdisjoint(calls)
