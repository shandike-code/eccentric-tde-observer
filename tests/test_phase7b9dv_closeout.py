"""Phase 7B9dv clean-boundary closeout 的小型回归测试。"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import phase7b9dv_closeout as closeout


ROOT = Path(__file__).resolve().parents[1]


def _sources() -> dict[str, dict[str, object]]:
    return {
        name: json.loads((ROOT / path).read_text(encoding="utf-8"))
        for name, path in closeout.SOURCE_PATHS.items()
    }


def test_current_sources_form_a_clean_unconverged_closeout() -> None:
    report = closeout.build_report(ROOT)
    audit = report["du_closeout_audit"]
    assert audit["retained_record_count"] == 9
    assert audit["last_iteration"] == 8
    assert audit["last_block_report_count"] == 76
    assert audit["last_progression_passed"] is True
    assert audit["last_convergence_passed"] is False
    assert report["stop_provenance"]["manifest_active_iteration_is_null"] is True
    assert report["post_convergence_branch_decision"] == {
        "status": "not_ready",
        "selected_branch": None,
        "reason": "Strict convergence, a formal feedback pair, and full-domain continuum evidence are absent.",
    }


def test_merged_history_removes_the_duplicate_du_seed() -> None:
    sources = _sources()
    history = closeout._merged_history(sources["dp_summary"], sources["du_summary"])
    assert len(history) == 49
    assert [row["combined_iteration"] for row in history] == list(range(49))
    assert history[40]["stage"] == "7B9dp"
    assert history[41]["stage"] == "7B9du"
    assert history[-1]["stage_iteration"] == 8


def test_active_partial_iteration_is_rejected() -> None:
    sources = _sources()
    altered = copy.deepcopy(sources)
    altered["du_manifest"]["active_iteration"] = {"iteration": 9}
    with pytest.raises(RuntimeError, match="clean iteration boundary"):
        closeout._validate_sources(altered)


def test_incomplete_final_block_ownership_is_rejected() -> None:
    sources = _sources()
    altered = copy.deepcopy(sources)
    altered["du_manifest"]["iterations"][-1]["block_report_audit"]["block_indices"] = list(range(75))
    altered["du_summary"]["iterations"][-1]["block_report_audit"]["block_indices"] = list(range(75))
    with pytest.raises(RuntimeError, match="block ownership"):
        closeout._validate_sources(altered)


def test_branch_selection_is_rejected() -> None:
    sources = _sources()
    altered = copy.deepcopy(sources)
    altered["branch_contract"]["current_decision"]["status"] = "decided"
    altered["branch_contract"]["current_decision"]["selected_branch"] = "uvot"
    with pytest.raises(RuntimeError, match="must remain not_ready"):
        closeout._validate_sources(altered)


def test_machine_artifact_matches_current_endpoint() -> None:
    artifact = json.loads((ROOT / "outputs/phase7b9dv_closeout.json").read_text(encoding="utf-8"))
    assert artifact["combined_progress"]["unique_state_count"] == 49
    assert artifact["combined_progress"]["strict_convergence_reached"] is False
    assert artifact["du_closeout_audit"]["last_original_operator_residual"] == pytest.approx(
        2.1041349752068736e-4, rel=0.0, abs=0.0
    )
    figure = ROOT / artifact["figure"]["path"]
    assert figure.is_file()
    assert closeout.sha256(figure) == artifact["figure"]["sha256"]
