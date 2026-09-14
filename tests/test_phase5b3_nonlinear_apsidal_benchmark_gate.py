"""Phase 5B3 全局非线性拱点模与文献基准门。"""

from __future__ import annotations

import ast
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def test_phase5b3_internal_gate_passes_but_literature_gate_stays_closed() -> None:
    report = json.loads(
        (OUTPUT / "phase5b3_nonlinear_apsidal_report.json").read_text()
    )
    assert report["equation_internal_gate"]
    assert not report["published_fig6_frequency_gate"]
    assert not report["published_fig6_profile_gate"]
    assert not report["published_fig7_circular_continuity_gate"]
    assert not report["phase5b3_literature_benchmark_gate"]
    assert report["max_relative_frequency_table_change"] < 1.0e-5
    assert report["max_relative_outer_eccentricity_table_change"] < 1.0e-5
    assert report["max_relative_derivative_holdout_error"] < 1.0e-3
    assert report["max_absolute_outer_boundary_residual"] < 1.0e-8


def test_phase5b3_converged_branch_is_continuous_with_linear_limit() -> None:
    with (OUTPUT / "phase5b3_zo2020_fig6_comparison.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    for row in rows:
        nonlinear = float(row["three_dimensional_nonlinear_frequency"])
        linear = float(row["three_dimensional_linear_frequency"])
        published = float(row["published_frequency"])
        assert nonlinear > 0.0
        assert linear > 0.0
        assert abs(nonlinear / linear - 1.0) < 0.05
        assert abs(nonlinear - published) > 1.0


def test_phase5b3_outputs_and_documented_figures_exist() -> None:
    required = (
        "phase5b3_fig6_profile_audit.png",
        "phase5b3_frequency_benchmark.png",
        "zo2020_original_fig7_reference.png",
        "phase5b3_hamiltonian_derivative_holdout.csv",
    )
    for filename in required:
        assert (OUTPUT / filename).stat().st_size > 0
    document = (
        ROOT / "docs/phase5b3_nonlinear_apsidal_benchmark_gate.md"
    ).read_text()
    lecture = (ROOT / "lecture/项目整体讲义.md").read_text()
    for filename in required[:3]:
        assert filename in document
        assert filename in lecture


def test_phase5b3_scientific_sources_contain_no_numerical_repairs() -> None:
    forbidden = {"clip", "nan_to_num"}
    for relative in (
        "src/eccentric_tde_observer/hamiltonian_table.py",
        "src/eccentric_tde_observer/nonlinear_apsidal_mode.py",
        "scripts/phase5b3_nonlinear_apsidal_benchmark_gate.py",
    ):
        tree = ast.parse((ROOT / relative).read_text())
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert forbidden.isdisjoint(calls)


def test_phase5b3_holdout_locations_cover_both_modes() -> None:
    with (OUTPUT / "phase5b3_hamiltonian_derivative_holdout.csv").open(
        newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    assert {float(row["radius_ratio"]) for row in rows} == {1.3, 3.0}
    assert {row["location"] for row in rows} == {"inner", "middle", "outer"}
    assert max(float(row["relative_derivative_vector_error"]) for row in rows) < 1.0e-3
