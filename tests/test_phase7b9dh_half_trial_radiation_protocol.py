"""Frozen Phase 7B9dh protocol audit without opening full-state checkpoints."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def _protocol() -> dict[str, object]:
    return json.loads(
        (OUTPUT / "phase7b9dh_preregistered_half_trial_radiation.json").read_text()
    )


def test_phase7b9dh_pins_authorized_two_buffer_scope_and_protected_start() -> None:
    protocol = _protocol()
    claims = protocol["full_state_claims"]
    assert claims["protected_initial_radiation"] == {
        "path": "outputs/checkpoints/phase7b6h_full_frequency_iteration8.dat",
        "size_bytes": 10_099_884_032,
        "sha256": "192bce63a94ecd45e88be7538414d063e4e54fa0931a70ca356aeb218af8bd08",
    }
    assert claims["authorized_buffer_a_precopy"]["path"] == (
        "outputs/checkpoints/phase7b9k_retained_trial_map3.dat"
    )
    assert claims["authorized_buffer_b_precopy"]["path"] == (
        "outputs/checkpoints/phase7b9cs_resource_adjusted_tail_anchor.dat"
    )
    assert all(
        not source["path"].endswith(".dat")
        for source in protocol["sources"].values()
    )


def test_phase7b9dh_keeps_science_and_resource_gates_separate() -> None:
    protocol = _protocol()
    cfg = protocol["configuration"]
    gates = protocol["gates"]
    assert cfg["material_candidate_absolute_relaxation"] == 0.0625
    assert cfg["maximum_concurrent_processes"] == 2
    assert cfg["maximum_picard_maps"] == 24
    assert gates["global_original_operator_residual_below"] == 1.0e-4
    assert gates["global_boundary_spectrum_l1_below"] == 1.0e-3
    assert gates["global_boundary_bolometric_fraction_below"] == 1.0e-3
    assert gates["subsequent_residual_contraction_ratio_below"] == 1.01
    assert gates["each_process_peak_rss_strictly_below_mib"] == 6144.0
    assert gates["each_worker_wall_time_strictly_below_s"] == 60.0
    assert gates["each_full_map_wall_time_strictly_below_s"] == 1800.0
    assert protocol["storage_plan"]["additional_full_state_allocation_count"] == 0


def test_phase7b9dh_cannot_authorize_feedback_after_only_one_low_residual() -> None:
    protocol = _protocol()
    cfg = protocol["configuration"]
    authorization = protocol["authorization"]
    assert cfg["material_feedback_authorization_mode"] == (
        "after_two_consecutive_and_formal_pair"
    )
    assert authorization["evaluate_provisional_feedback_after_first_low_residual"]
    assert authorization["provisional_feedback_is_acceptance_authority"] is False
    assert authorization["formal_pair_only_after_next_consecutive_fresh_residual"]
    assert authorization["material_feedback_before_formal_pair"] is False


def test_phase7b9dh_runner_contains_no_numerical_repair_call() -> None:
    source = (
        ROOT / "scripts/phase7b9_half_trial_radiation_continuation.py"
    ).read_text()
    forbidden = ("np.clip(", "nan_to_num(", "np.maximum(mapped", "renormalize(")
    assert all(token not in source for token in forbidden)
