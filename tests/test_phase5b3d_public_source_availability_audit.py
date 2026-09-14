"""Phase 5B3d 公开来源审计回归。"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
sys.path.insert(0, str(ROOT / "scripts"))

from phase5b3d_public_source_availability_audit import (  # noqa: E402
    classify_arxiv_members,
)


def load_report() -> dict[str, object]:
    return json.loads(
        (
            OUTPUT / "phase5b3d_public_source_availability_report.json"
        ).read_text()
    )


def test_phase5b3d_classifies_manuscript_and_code_separately() -> None:
    code, manuscript, figures = classify_arxiv_members(
        ["paper.tex", "solver.py", "Makefile", "figure.pdf", "notes.txt"]
    )
    assert code == ["solver.py", "Makefile"]
    assert manuscript == ["paper.tex"]
    assert figures == ["figure.pdf"]


def test_phase5b3d_finds_no_public_published_solver() -> None:
    report = load_report()
    assert not report["public_published_solver_or_raw_dataset_found"]
    assert report["corresponding_author_request_required"]
    assert not report["external_request_sent"]
    assert not report["formal_zo_source_model_changed"]
    assert not report["phase_to_time_mapping_authorized"]


def test_phase5b3d_records_machine_auditable_portals() -> None:
    report = load_report()
    publisher = report["publisher"]
    crossref = report["crossref"]
    arxiv = report["arxiv_source"]
    zenodo = report["zenodo"]
    github = report["github"]
    assert publisher["reasonable_request_statement_present"]
    assert not publisher["github_link_present"]
    assert not publisher["zenodo_link_present"]
    assert crossref["doi"].lower() == "10.1093/mnras/staa3127"
    assert crossref["relations"] == {}
    assert crossref["dataset_links"] == []
    assert arxiv["member_count"] > 10
    assert arxiv["numerical_code_members"] == []
    assert any("EccDiskSolsPlot" in name for name in arxiv["figure_members"])
    assert int(zenodo["total_count"]) == 0
    assert int(github["paper_query_total_count"]) == 0


def test_phase5b3d_document_preserves_authority_boundary() -> None:
    document = (
        ROOT / "docs/phase5b3d_public_source_availability_audit.md"
    ).read_text()
    request = (ROOT / "docs/zo2020_author_source_request_draft.md").read_text()
    receipt = json.loads(
        (OUTPUT / "phase5b3e_author_request_receipt.json").read_text()
    )
    # Phase 5B3d 机器报告保持当时未发送的历史事实；后续发送另留回执。
    assert "没有发送" in document
    assert "后续状态" in document
    assert "正式时间映射" in document
    assert "Fig. 6/7" in request
    assert "sent / 已发送" in request.lower()
    assert receipt["status"] == "sent_and_found_in_sent_mail"
    assert receipt["authorized_by_user"] is True
    assert receipt["attachments"] == []
    assert all(receipt["verification"].values())


def test_phase5b3d_script_contains_no_numerical_repairs() -> None:
    tree = ast.parse(
        (
            ROOT
            / "scripts/phase5b3d_public_source_availability_audit.py"
        ).read_text()
    )
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert {"clip", "nan_to_num"}.isdisjoint(calls)
