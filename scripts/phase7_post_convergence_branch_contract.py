"""生成并校验 Phase 7 收敛后的三分支决策合同。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "outputs/phase7_post_convergence_branch_contract.json"


STATIC_THRESHOLDS = {
    "physical_static_root_fraction": {
        "operator": "greater_than_or_equal",
        "value": 1.0,
        "evidence": "[A-classification]",
        "source": "Complete source-domain coverage is required; one failed physical column rejects a single-valued static closure.",
    },
    "maximum_quasi_static_ratio": {
        "operator": "less_than_or_equal",
        "value": 0.1,
        "evidence": "[A-classification]",
        "source": "Existing Phase 7A timescale gate in phase7a.select_quasi_static_representative_annuli.",
    },
    "maximum_thermal_time_over_orbital_period": {
        "operator": "less_than_or_equal",
        "value": 0.1,
        "evidence": "[A-classification]",
        "source": "A decade of timescale separation is adopted as the static-response gate; this is not a literature theorem.",
    },
    "maximum_history_hysteresis_l1": {
        "operator": "less_than_or_equal",
        "value": 0.1,
        "evidence": "[A-classification]",
        "source": "A ten-percent normalized loop mismatch is the preregistered single-valued-closure test.",
    },
}


CONTINUUM_THRESHOLDS = {
    "bolometric_flux_fractional_difference": {
        "operator": "less_than_or_equal",
        "value": 0.01,
        "evidence": "[A-classification]",
        "source": "One-percent energy-flux agreement is required before comparing spectral shape.",
    },
    "normalized_shape_l1_distance": {
        "operator": "less_than_or_equal",
        "value": 0.1,
        "evidence": "[A-classification]",
        "source": "Ten-percent normalized spectral-shape distance defines the small-difference route.",
    },
    "maximum_diagnostic_band_flux_fractional_difference": {
        "operator": "less_than_or_equal",
        "value": 0.1,
        "evidence": "[A-classification]",
        "source": "Ten-percent change in any fixed observer diagnostic band blocks the small-difference route.",
    },
    "ionizing_photon_rate_log10_difference_dex": {
        "operator": "absolute_less_than_or_equal",
        "value": 0.1,
        "evidence": "[A-classification]",
        "source": "A 0.1 dex ionizing-seed tolerance is adopted before later line formation.",
    },
    "nu_fnu_peak_energy_log10_difference_dex": {
        "operator": "absolute_less_than_or_equal",
        "value": math.log10(1.25),
        "evidence": "[A-classification]",
        "source": "A peak-energy ratio within 1/1.25 to 1.25 defines a small shift.",
    },
}


QUALIFICATION_FLAGS = (
    "complete_radial_and_orbital_domain_audited",
    "frequency_angle_depth_convergence_passed",
    "surface_energy_closure_passed",
    "history_dependence_test_completed",
)


CONTINUUM_FLAGS = (
    "coupled_material_radiation_solution_converged",
    "angle_frequency_intensity_field_available",
    "comparison_uses_identical_zo_geometry_and_observer_grid",
)


def _passes(value: float, threshold: Mapping[str, Any]) -> bool:
    """严格按合同运算符评价有限数值，不修补非法输入。"""
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("branch metrics must be finite")
    limit = float(threshold["value"])
    operator = threshold["operator"]
    if operator == "less_than_or_equal":
        return number <= limit
    if operator == "greater_than_or_equal":
        return number >= limit
    if operator == "absolute_less_than_or_equal":
        return abs(number) <= limit
    raise ValueError(f"unsupported operator: {operator}")


def evaluate_branch(metrics: Mapping[str, Any]) -> dict[str, Any]:
    """评价三分支；证据不全时返回 ``not_ready``，不猜测缺失量。"""
    missing_flags = [name for name in QUALIFICATION_FLAGS if name not in metrics]
    missing_static = [name for name in STATIC_THRESHOLDS if name not in metrics]
    if missing_flags or missing_static:
        return {
            "status": "not_ready",
            "selected_branch": None,
            "missing_evidence": missing_flags + missing_static,
        }
    failed_qualification = [name for name in QUALIFICATION_FLAGS if metrics[name] is not True]
    if failed_qualification:
        return {
            "status": "not_ready",
            "selected_branch": None,
            "missing_evidence": failed_qualification,
        }
    static_checks = {
        name: _passes(metrics[name], threshold)
        for name, threshold in STATIC_THRESHOLDS.items()
    }
    if not all(static_checks.values()):
        return {
            "status": "decided",
            "selected_branch": "periodic_dynamic_nlte_column",
            "static_checks": static_checks,
            "failed_metrics": [name for name, passed in static_checks.items() if not passed],
        }
    missing_continuum_flags = [name for name in CONTINUUM_FLAGS if name not in metrics]
    missing_continuum = [name for name in CONTINUUM_THRESHOLDS if name not in metrics]
    if missing_continuum_flags or missing_continuum:
        return {
            "status": "not_ready",
            "selected_branch": None,
            "static_checks": static_checks,
            "missing_evidence": missing_continuum_flags + missing_continuum,
        }
    failed_continuum_flags = [
        name for name in CONTINUUM_FLAGS if metrics[name] is not True
    ]
    if failed_continuum_flags:
        return {
            "status": "not_ready",
            "selected_branch": None,
            "static_checks": static_checks,
            "missing_evidence": failed_continuum_flags,
        }
    continuum_checks = {
        name: _passes(metrics[name], threshold)
        for name, threshold in CONTINUUM_THRESHOLDS.items()
    }
    branch = (
        "uvot_instrument_and_observation_sampling"
        if all(continuum_checks.values())
        else "finite_atmosphere_table_then_phase4_replacement"
    )
    return {
        "status": "decided",
        "selected_branch": branch,
        "static_checks": static_checks,
        "continuum_checks": continuum_checks,
        "failed_metrics": [
            name for name, passed in continuum_checks.items() if not passed
        ],
    }


def build_contract() -> dict[str, Any]:
    """返回不含当前科学判决的 machine-readable 合同。"""
    return {
        "contract_version": 1,
        "phase": "Phase 7 post-convergence branch decision",
        "classification": "[A-classification/V-code-path/O]",
        "current_candidate_context": {
            "material_relaxation": 0.0625,
            "phase_index": 1433,
            "spatial_scope": "one phase of one representative annulus",
            "formal_pair_required_first": True,
            "formal_pair_accepts_at_most_one_nonlinear_material_step": True,
            "formal_pair_does_not_select_a_post_convergence_branch": True,
        },
        "upstream_inventory": "outputs/phase7_material_feedback_to_observer_dependency_inventory.json",
        "formal_feedback_to_observer_dependency_chain": [
            {
                "id": "fixed_material_radiation_pair",
                "status": "running_or_pending_current_evidence",
                "run": [
                    "scripts/phase7b9du_exhausted_dp_picard_continuation.py",
                    "scripts/phase7b9_provisional_feedback.py",
                    "scripts/phase7b9_consecutive_after_provisional.py",
                ],
                "gates": {
                    "two_consecutive_original_operator_residuals_below": 1.0e-4,
                    "each_boundary_spectrum_l1_below": 1.0e-3,
                    "each_boundary_bolometric_fraction_below": 1.0e-3,
                    "evidence": "[A-preregistered/V]",
                },
                "output": "Two converged radiation states for the same frozen 0.0625 material bytes.",
            },
            {
                "id": "formal_h_he_feedback_pair",
                "status": "implemented_but_not_yet_run_on_the_current_converged_pair",
                "run": [
                    "scripts/phase7b9_formal_pair_from_provisional.py",
                    "scripts/phase7b9_formal_feedback_pair_adapter.py",
                ],
                "gates": {
                    "last_two_rate_and_heating_volume_l1_below": 1.0e-3,
                    "inner_noise_to_trial_signal_l2_ratio_below": 0.1,
                    "each_candidate_to_base_residual_norm_ratio_below": 1.0,
                    "minimum_population_fraction_at_least": 0.0,
                    "all_residual_components_finite": True,
                    "evidence": "[A-preregistered/V]",
                },
                "output": "At most one accepted nonlinear material step at one annulus phase.",
                "observer_ready": False,
            },
            {
                "id": "full_domain_continuum_closure",
                "status": "missing",
                "run_or_implement": [
                    "repeat coupled material-radiation convergence over the radial and orbital source domain",
                    "produce angle-resolved surface I_nu and all branch metrics in this contract",
                ],
                "output": "Validated static table or history-aware dynamic intensity provider.",
                "observer_ready": False,
            },
            {
                "id": "phase4_local_intensity_adapter",
                "status": "missing",
                "existing_interface": "src/eccentric_tde_observer/annulus_bridge.py:AngleResolvedAnnulusTable",
                "consumer": "scripts/phase4_final_atlas.py",
                "observer_ready": False,
            },
            {
                "id": "observer_frame_continuum",
                "status": "existing_for_the_current_conditional_closure_only",
                "run_after_phase4": "scripts/phase5a_observer_frame_flambda.py",
                "output": "Observer-frame F_lambda with redshift, distance and foreground extinction.",
                "instrument_ready": False,
            },
            {
                "id": "swift_uvot_instrument_and_sampling",
                "status": "missing",
                "required_output": "Calibrated count rates or flux observables on an explicit observation cadence.",
            },
        ],
        "decision_order": [
            "not_ready_if_required_evidence_is_missing_or_unqualified",
            "periodic_dynamic_nlte_column_if_any_static_metric_fails",
            "uvot_instrument_and_observation_sampling_if_all_continuum_metrics_are_small",
            "finite_atmosphere_table_then_phase4_replacement_otherwise",
        ],
        "qualification_flags": list(QUALIFICATION_FLAGS),
        "continuum_comparison_flags": list(CONTINUUM_FLAGS),
        "static_failure_thresholds": STATIC_THRESHOLDS,
        "small_continuum_difference_thresholds": CONTINUUM_THRESHOLDS,
        "threshold_sensitivity_required": {
            "maximum_quasi_static_ratio": [0.05, 0.1, 0.2],
            "maximum_thermal_time_over_orbital_period": [0.03, 0.1, 0.3],
            "maximum_history_hysteresis_l1": [0.05, 0.1, 0.2],
            "normalized_shape_l1_distance": [0.05, 0.1, 0.2],
            "maximum_diagnostic_band_flux_fractional_difference": [0.05, 0.1, 0.2],
            "ionizing_photon_rate_log10_difference_dex": [0.05, 0.1, 0.3],
            "nu_fnu_peak_energy_ratio": [1.1, 1.25, 2.0],
            "evidence": "[A-classification]",
        },
        "branches": {
            "uvot_instrument_and_observation_sampling": {
                "meaning": "Static closure passes and every continuum-impact metric is within its small-difference threshold.",
                "run_or_implement": [
                    "scripts/phase4_final_atlas.py with the validated closure provenance frozen",
                    "scripts/phase5a_observer_frame_flambda.py",
                    "missing: a Swift/UVOT effective-area, calibration, count-rate, cadence, and upper-limit layer",
                ],
                "must_not_claim": "A formal feedback pair alone validates the current modified-blackbody closure.",
            },
            "finite_atmosphere_table_then_phase4_replacement": {
                "meaning": "Static closure passes but at least one continuum-impact metric is not small.",
                "run_or_implement": [
                    "src/eccentric_tde_observer/annulus_bridge.py:AngleResolvedAnnulusTable",
                    "missing: populate I_nu(T_eff,m0,Q,mu,nu) over the full source domain without extrapolation",
                    "missing: Phase 4 local-intensity-provider adapter",
                    "scripts/phase4_final_atlas.py after adapter validation",
                    "scripts/phase5a_observer_frame_flambda.py after the Phase 4 rerun",
                ],
                "must_not_claim": "The existing Phase 7 one-column intensity is already a production atmosphere table.",
            },
            "periodic_dynamic_nlte_column": {
                "meaning": "At least one converged full-domain static-validity metric fails.",
                "run_or_implement": [
                    "src/eccentric_tde_observer/periodic_dynamic_atmosphere.py",
                    "src/eccentric_tde_observer/nonlocal_dynamic_transfer.py",
                    "src/eccentric_tde_observer/mixed_frame_ale_log_p1.py",
                    "missing: converged full-orbit history-aware I_nu(a,E,mu) provider",
                    "missing: Phase 4 adapter with phase/history provenance",
                ],
                "must_not_claim": "Failure of one nonlinear step or one numerical solver proves that the static approximation fails.",
            },
        },
        "missing_evidence_now": [
            "The 0.0625 fixed-material radiation pair has not yet completed the formal H/He feedback decision.",
            "One phase and one annulus do not cover the radial and orbital source domain.",
            "No converged coupled material-radiation solution is available over that full domain.",
            "No forward/backward or repeated-orbit hysteresis metric has been produced.",
            "No validated angle-resolved Phase 7 intensity table is connected to Phase 4.",
            "No fixed diagnostic-band comparison or ionizing-photon comparison has been run on a production table.",
            "The Swift/UVOT instrument and observation-sampling layer is not implemented.",
        ],
        "historical_non_authoritative_context": {
            "phase7b4g_shape_l1_large_threshold": 0.2,
            "phase7b4g_peak_energy_ratio_large_threshold": 2.0,
            "use_in_this_contract": False,
            "reason": "That fixed-density two-vacuum-face gate was not a production full-disc atmosphere table.",
        },
        "forbidden_shortcuts": {
            "select_branch_now": False,
            "infer_static_failure_from_one_rejected_step": False,
            "run_phase4_atlas_during_contract_generation": False,
            "extrapolate_atmosphere_table": False,
            "nan_to_num": False,
            "arbitrary_clip": False,
            "arbitrary_floor": False,
            "failed_point_deletion": False,
            "posthoc_renormalization": False,
        },
        "current_decision": {
            "status": "not_ready",
            "selected_branch": None,
            "reason": "The contract records routing criteria only; current Phase 7 evidence is incomplete.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = build_contract()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["current_decision"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
