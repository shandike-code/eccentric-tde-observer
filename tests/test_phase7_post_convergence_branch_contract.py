"""Phase 7 收敛后分支合同回归测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase7_post_convergence_branch_contract import (
    CONTINUUM_THRESHOLDS,
    STATIC_THRESHOLDS,
    build_contract,
    evaluate_branch,
)


ROOT = Path(__file__).resolve().parents[1]


def _complete_metrics() -> dict[str, object]:
    return {
        "complete_radial_and_orbital_domain_audited": True,
        "frequency_angle_depth_convergence_passed": True,
        "surface_energy_closure_passed": True,
        "history_dependence_test_completed": True,
        "physical_static_root_fraction": 1.0,
        "maximum_quasi_static_ratio": 0.1,
        "maximum_thermal_time_over_orbital_period": 0.1,
        "maximum_history_hysteresis_l1": 0.1,
        "coupled_material_radiation_solution_converged": True,
        "angle_frequency_intensity_field_available": True,
        "comparison_uses_identical_zo_geometry_and_observer_grid": True,
        "bolometric_flux_fractional_difference": 0.01,
        "normalized_shape_l1_distance": 0.1,
        "maximum_diagnostic_band_flux_fractional_difference": 0.1,
        "ionizing_photon_rate_log10_difference_dex": -0.1,
        "nu_fnu_peak_energy_log10_difference_dex": CONTINUUM_THRESHOLDS[
            "nu_fnu_peak_energy_log10_difference_dex"
        ]["value"],
    }


def test_contract_does_not_select_a_branch() -> None:
    contract = build_contract()
    assert contract["current_decision"] == {
        "status": "not_ready",
        "selected_branch": None,
        "reason": "The contract records routing criteria only; current Phase 7 evidence is incomplete.",
    }
    assert contract["forbidden_shortcuts"]["run_phase4_atlas_during_contract_generation"] is False
    assert all(
        threshold["evidence"] == "[A-classification]"
        for threshold in (*STATIC_THRESHOLDS.values(), *CONTINUUM_THRESHOLDS.values())
    )
    chain = contract["formal_feedback_to_observer_dependency_chain"]
    assert [node["id"] for node in chain] == [
        "fixed_material_radiation_pair",
        "formal_h_he_feedback_pair",
        "full_domain_continuum_closure",
        "phase4_local_intensity_adapter",
        "observer_frame_continuum",
        "swift_uvot_instrument_and_sampling",
    ]
    assert chain[1]["observer_ready"] is False
    assert chain[2]["status"] == "missing"


def test_missing_evidence_is_not_misclassified_as_static_failure() -> None:
    result = evaluate_branch({})
    assert result["status"] == "not_ready"
    assert result["selected_branch"] is None
    assert "complete_radial_and_orbital_domain_audited" in result["missing_evidence"]


def test_small_difference_selects_uvot_route_at_inclusive_boundaries() -> None:
    result = evaluate_branch(_complete_metrics())
    assert result["selected_branch"] == "uvot_instrument_and_observation_sampling"
    assert all(result["static_checks"].values())
    assert all(result["continuum_checks"].values())


@pytest.mark.parametrize("metric", list(CONTINUUM_THRESHOLDS))
def test_each_large_continuum_metric_selects_finite_atmosphere(metric: str) -> None:
    metrics = _complete_metrics()
    threshold = CONTINUUM_THRESHOLDS[metric]
    metrics[metric] = float(threshold["value"]) * 1.01 + 1.0e-15
    result = evaluate_branch(metrics)
    assert result["selected_branch"] == "finite_atmosphere_table_then_phase4_replacement"
    assert metric in result["failed_metrics"]


@pytest.mark.parametrize("metric", list(STATIC_THRESHOLDS))
def test_each_failed_static_metric_selects_dynamic_route(metric: str) -> None:
    metrics = _complete_metrics()
    threshold = STATIC_THRESHOLDS[metric]
    if threshold["operator"] == "greater_than_or_equal":
        metrics[metric] = float(threshold["value"]) - 0.01
    else:
        metrics[metric] = float(threshold["value"]) + 0.01
    result = evaluate_branch(metrics)
    assert result["selected_branch"] == "periodic_dynamic_nlte_column"
    assert metric in result["failed_metrics"]


def test_unqualified_numerics_return_not_ready() -> None:
    metrics = _complete_metrics()
    metrics["frequency_angle_depth_convergence_passed"] = False
    result = evaluate_branch(metrics)
    assert result["status"] == "not_ready"
    assert result["selected_branch"] is None


def test_nonfinite_metrics_are_rejected_without_repair() -> None:
    metrics = _complete_metrics()
    metrics["maximum_quasi_static_ratio"] = float("nan")
    with pytest.raises(ValueError, match="must be finite"):
        evaluate_branch(metrics)


def test_written_contract_matches_builder() -> None:
    artifact = json.loads(
        (ROOT / "outputs/phase7_post_convergence_branch_contract.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact == build_contract()
    assert artifact["current_candidate_context"]["material_relaxation"] == 0.0625
    assert len(artifact["branches"]) == 3
