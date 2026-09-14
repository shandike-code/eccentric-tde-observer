from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = PROJECT_ROOT / "outputs" / "phase7b5o_preregistered_protocol.json"
REPORT = PROJECT_ROOT / "outputs" / "phase7b5o_summary.json"
EXPECTED_PROTOCOL_SHA256 = (
    "ff63f6f46cd71c96089c714a600f8ef7a31d71bf92afd306aec743a89e94a176"
)


def _report() -> dict[str, object]:
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_phase7b5o_protocol_and_grid_remain_frozen() -> None:
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == EXPECTED_PROTOCOL_SHA256
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["validation"]["source_state_labels"] == [
        "initial",
        "converged",
    ]
    assert {
        (case["phase_index"], case["full_depth_index"])
        for case in protocol["validation"]["cases"]
    } == {
        (1433, 0),
        (1637, 0),
        (1307, 144),
        (740, 144),
        (1560, 7),
        (487, 29),
    }
    report = _report()
    decision = report["decision"]
    assert decision["frozen_protocol_hash_passed"] is True
    assert decision["frozen_material_hash_passed"] is True
    assert decision["prior_holdout_exclusion_hash_passed"] is True
    assert decision["validation_spectra_used_for_grid_construction"] is False
    assert decision["frozen_grid_hash_unchanged_through_validation"] is True
    assert report["grid"]["sha256_before_validation"] == report["grid"][
        "sha256_after_validation"
    ]


def test_phase7b5o_uses_exact_budget_and_all_hierarchy_options() -> None:
    grid = _report()["grid"]
    assert grid["base_parent_count"] == 2408
    assert grid["pilot_group_count"] == 4816
    assert grid["master_group_count"] == 9632
    assert grid["candidate_leaf_group_count"] == 4816
    assert grid["option_parent_counts_1_2_4"] == [1408, 296, 704]
    one, two, four = grid["option_parent_counts_1_2_4"]
    assert one + two + four == grid["base_parent_count"]
    assert one + 2 * two + 4 * four == grid["candidate_leaf_group_count"]


def test_phase7b5o_new_initial_and_converged_holdouts_are_complete() -> None:
    report = _report()
    rows = report["validation_results"]
    assert len(rows) == 12
    assert len({row["case"] for row in rows}) == 6
    assert {row["source_state_label"] for row in rows} == {
        "initial",
        "converged",
    }
    assert all(control["fixed_point_converged"] for control in report[
        "reference_source_controls"
    ])
    assert all(
        row["initial_reference_next_state_reproduced_exactly"]
        for row in rows
        if row["source_state_label"] == "initial"
    )


def test_phase7b5o_master_passes_but_candidate_he_ii_fails_strictly() -> None:
    report = _report()
    aggregate = report["aggregate"]
    for metric in ("energy", "H_I", "He_I", "He_II"):
        assert aggregate[f"maximum_master_{metric}_absolute_relative_error"] < 1e-3
    for metric in ("energy", "H_I", "He_I"):
        assert aggregate[f"maximum_candidate_{metric}_absolute_relative_error"] < 1e-3
    assert aggregate["maximum_candidate_He_II_absolute_relative_error"] == (
        0.0010005463143231768
    )
    worst = max(
        report["validation_results"],
        key=lambda row: row["candidate_He_II_absolute_relative_error"],
    )
    assert worst["case"] == "signed width change q80"
    assert worst["source_state_label"] == "converged"
    decision = report["decision"]
    assert decision[
        "nested_master_joint_energy_and_H_He_rate_gate_passed"
    ] is True
    assert decision[
        "hierarchical_candidate_joint_energy_and_H_He_rate_gate_passed"
    ] is False
    assert decision["one_cell_production_frequency_candidate_selected"] is False
    assert decision["angular_radiation_subgrid_one_cell_gate_authorized"] is False


def test_phase7b5o_controls_and_figures_are_complete() -> None:
    report = _report()
    decision = report["decision"]
    assert decision["all_reference_source_solves_passed"] is True
    assert decision[
        "all_mapping_projection_and_quadrature_controls_passed"
    ] is True
    assert decision["all_converged_operator_controls_passed"] is True
    assert len(report["converged_operator_controls"]) == 12
    for filename in report["figures"].values():
        assert (PROJECT_ROOT / "outputs" / filename).is_file()


def test_phase7b5o_uses_no_forbidden_repairs_or_holdout_retraining() -> None:
    source = (
        PROJECT_ROOT / "scripts" / "phase7b5o_initial_converged_validation.py"
    ).read_text(encoding="utf-8")
    assert "nan_to_num" not in source
    assert "np.clip" not in source
    assert "validation_feedback_allowed\"] is not False" in source
    preregistration = (
        PROJECT_ROOT / "scripts" / "phase7b5o_preregister_protocol.py"
    ).read_text(encoding="utf-8")
    assert "_p0_actual_one_cell_run" not in preregistration
    assert "_one_p0_map" not in preregistration
