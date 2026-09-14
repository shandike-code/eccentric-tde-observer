"""Phase 5B5 模形绑定时间轴产物回归。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def test_phase5b5_reproduces_direct_candidate_periods() -> None:
    summary = json.loads(
        (OUTPUT / "phase5b5_mode_matched_time_axis_summary.json").read_text()
    )
    assert all(summary["gate_checks"].values())
    periods = {row["case"]: row["candidate_period_days"] for row in summary["case_results"]}
    assert periods["atlas_reference"] == pytest.approx(14907.294246269026)
    assert periods["strict_boundary_sensitivity"] == pytest.approx(
        15679.464460101226
    )


def test_phase5b5_schedule_is_conditional_relative_time() -> None:
    with (OUTPUT / "phase5b5_mode_matched_phase_schedule.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 48
    assert {float(row["phase_deg"]) for row in rows} == set(range(0, 360, 15))
    assert all(row["source_profile_match_required"] == "True" for row in rows)
    assert all(row["existing_constant_e_atlas_row"] == "False" for row in rows)
    summary = json.loads(
        (OUTPUT / "phase5b5_mode_matched_time_axis_summary.json").read_text()
    )
    decision = summary["decision"]
    assert decision["candidate_schedule_is_relative_time_only"] is True
    assert decision["absolute_calendar_epoch_supplied"] is False
    assert decision["printed_eq48_normalization_adopted"] is False
    assert decision["existing_constant_e_atlas_phase_to_time_mapping_authorized"] is False
    assert decision["candidate_mode_source_rebuild_authorized"] is False


def test_phase5b5_figure_and_sources_exist() -> None:
    summary = json.loads(
        (OUTPUT / "phase5b5_mode_matched_time_axis_summary.json").read_text()
    )
    assert (ROOT / summary["outputs"]["figure"]).stat().st_size > 0
    for row in summary["sources"].values():
        assert (ROOT / row["path"]).is_file()
