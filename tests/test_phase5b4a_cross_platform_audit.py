"""Phase 5B4a 跨平台复算审计回归。"""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def report() -> dict[str, object]:
    return json.loads(
        (OUTPUT / "phase5b4a_cross_platform_audit.json").read_text()
    )


def test_phase5b4a_cross_platform_reproduction_gate_passes() -> None:
    data = report()
    assert data["overall_cross_platform_reproduction_gate"]
    assert all(data["reproduction_gates"].values())
    assert len(data["source_manifest"]) == 20
    assert len(data["remote_source_copy_integrity"]) == 10
    assert all(
        entry["matches"]
        for entry in data["remote_source_copy_integrity"].values()
    )


def test_phase5b4a_reproduces_primary_quantities() -> None:
    data = report()
    b3c = data["phase5b3c"]
    b4 = data["phase5b4"]
    assert b3c["maximum_primary_solution_relative_difference"] < 1.0e-9
    assert b3c["maximum_vector_tangent_relative_difference"] < 1.0e-8
    assert b4["maximum_candidate_table_relative_difference"] < 1.0e-10
    assert b4["maximum_table_solution_relative_difference"] < 1.0e-10
    assert b4["maximum_shooting_solution_relative_difference"] < 1.0e-7
    assert b4["derivative_resolution_gate_pattern"]["macos"] == [
        False,
        False,
        True,
    ]
    assert b4["derivative_resolution_gate_pattern"]["windows"] == [
        False,
        False,
        True,
    ]


def test_phase5b4a_does_not_relabel_candidate_as_published_benchmark() -> None:
    boundary = report()["scientific_boundary"]
    assert boundary["equation_self_consistent_candidate_is_reproduced"]
    assert not boundary["published_zo_benchmark_is_recovered"]
    assert not boundary["constant_e_atlas_shape_is_compatible"]
    assert not boundary["existing_atlas_phase_to_time_mapping_authorized"]
    assert not boundary["arbitrary_sign_or_boundary_scan_performed"]


def test_phase5b4a_document_keeps_evidence_boundary_explicit() -> None:
    document = (ROOT / "docs/phase5b4a_cross_platform_audit.md").read_text()
    assert "phase5b4a_cross_platform_audit.json" in document
    assert "[V]" in document
    assert "[A-audit]" in document
    assert "[O]" in document
    assert "published benchmark" in document
    assert "不替代 Phase 5B3c/B4 原有科学门" in document


def test_phase5b4a_script_contains_no_numerical_repairs() -> None:
    tree = ast.parse(
        (ROOT / "scripts/phase5b4a_cross_platform_audit.py").read_text()
    )
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert {"clip", "nan_to_num"}.isdisjoint(calls)
