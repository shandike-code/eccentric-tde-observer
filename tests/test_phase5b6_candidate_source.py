from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def test_phase5b6_report_keeps_candidate_and_benchmark_status_distinct() -> None:
    report = json.loads(
        (OUTPUT / "phase5b6_candidate_source_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["authorization"] == {
        "candidate_source_rebuild_authorized_by_user": True,
        "authorization_date": "2026-09-02",
        "published_benchmark_claim": False,
        "constant_e_control_replaced": False,
    }
    assert report["gate_checks"]["all_eccentricity_fingerprints_match"]
    assert report["gate_checks"]["all_dynamics_fingerprints_match"]
    assert report["gate_checks"]["all_sources_are_nested_and_positive"]
    assert report["gate_checks"]["generic_validity_interface_executed"]
    assert not report["gate_checks"]["formal_candidate_validity_convergence_closed"]
    assert not report["gate_checks"]["published_benchmark_gate"]
    assert all(not row["published_benchmark"] for row in report["case_results"])


def test_phase5b6_profiles_remain_native_and_positive() -> None:
    with (OUTPUT / "phase5b6_candidate_source_radial_diagnostics.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 512
    cases = {row["case"] for row in rows}
    assert cases == {"atlas_reference", "strict_boundary_sensitivity"}
    for case in cases:
        selected = [row for row in rows if row["case"] == case]
        assert len(selected) == 256
        assert float(selected[0]["scaled_semimajor_axis"]) == 1.0
        assert float(selected[-1]["scaled_semimajor_axis"]) == 2.0
        assert all(float(row["jacobian_min"]) > 0.0 for row in selected)
        assert all(
            float(row["dimensionless_height_min"]) > 0.0 for row in selected
        )
        assert all(
            float(row["effective_temperature_min_k"]) > 0.0
            for row in selected
        )
