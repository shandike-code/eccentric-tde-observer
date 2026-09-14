"""Phase 5B8 候选源相对物理时间产物回归。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
REPORT = OUTPUT / "phase5b8_candidate_source_time_mapping_report.json"


def _load_report() -> dict[str, object]:
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_phase5b8_closes_candidate_lineage_without_published_claim() -> None:
    report = _load_report()
    assert all(
        value is True
        for key, value in report["gate_checks"].items()
        if key != "published_benchmark_gate"
    )
    assert report["gate_checks"]["published_benchmark_gate"] is False
    assert report["decision"]["candidate_source_phi_to_relative_physical_time_authorized"] is True
    assert report["decision"]["existing_constant_e_atlas_phi_to_time_authorized"] is False
    assert report["decision"]["absolute_calendar_time_authorized"] is False
    assert report["decision"]["published_zo_benchmark_claim_authorized"] is False


def test_phase5b8_periods_and_rates_are_self_consistent() -> None:
    report = _load_report()
    rows = {row["case"]: row for row in report["case_results"]}
    assert rows["atlas_reference"]["candidate_period_days"] == pytest.approx(
        14907.294246269026
    )
    assert rows["strict_boundary_sensitivity"]["candidate_period_days"] == pytest.approx(
        15679.464460101226
    )
    for row in rows.values():
        assert row["signed_degrees_per_day"] * row["candidate_period_days"] == pytest.approx(360.0)
        assert row["time_per_15_deg_days"] * 24.0 == pytest.approx(row["candidate_period_days"])
        assert row["candidate_validity_convergence_closed"] is True
        assert row["published_benchmark"] is False


def test_phase5b8_schedule_has_observer_grid_and_exact_output_hashes() -> None:
    report = _load_report()
    schedule = ROOT / report["outputs"]["schedule"]["path"]
    figure = ROOT / report["outputs"]["figure"]["path"]
    with schedule.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 48
    assert {float(row["phase_deg"]) for row in rows} == set(range(0, 360, 15))
    assert all(row["published_benchmark"] == "False" for row in rows)
    for path, entry in ((schedule, report["outputs"]["schedule"]), (figure, report["outputs"]["figure"])):
        assert path.stat().st_size == entry["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]


def test_phase5b8_records_complete_scale_and_relative_origin() -> None:
    report = _load_report()
    normalization = report["physical_normalization"]
    for key in (
        "black_hole_mass_msun",
        "stellar_mass_msun",
        "stellar_radius_rsun",
        "circularization_efficiency",
        "inner_semimajor_axis_cm",
        "eccentric_communication_time_s",
        "delta_gr",
        "dimensionless_angular_frequency_unit_s1",
    ):
        assert normalization[key] > 0.0
    assert report["time_origin"]["absolute_calendar_epoch"] is None
    assert report["time_origin"]["reference_relative_time_days"] == 0.0
