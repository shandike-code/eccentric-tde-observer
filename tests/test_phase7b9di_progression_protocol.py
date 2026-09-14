"""Read-only audit of the frozen Phase 7B9di protocol; no full-state access."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "outputs/phase7b9di_preregistered_progression_continuation.json"


def _protocol() -> dict[str, object]:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def test_phase7b9di_pins_dh_small_artifacts_and_no_dat_sources() -> None:
    protocol = _protocol()
    sources = protocol["sources"]
    assert {
        "phase7b9dh_protocol",
        "phase7b9dh_manifest",
        "phase7b9dh_summary",
        "phase7b9dh_initialization_receipt",
    } <= set(sources)
    assert all(not row["path"].endswith(".dat") for row in sources.values())


def test_phase7b9di_starts_from_dh_mapped_b_toward_untouched_a() -> None:
    protocol = _protocol()
    cfg = protocol["configuration"]
    claims = protocol["full_state_claims"]
    assert cfg["initial_state_path"] == (
        "outputs/checkpoints/phase7b9cs_resource_adjusted_tail_anchor.dat"
    )
    assert cfg["initial_state_sha256"] == (
        "a213008647dec28ebd7d97da62b562cf15b4519d120ea1bd6b8886fa742ce97b"
    )
    assert cfg["scratch_state_path"] == (
        "outputs/checkpoints/phase7b9k_retained_trial_map3.dat"
    )
    assert claims["buffer_a_next_output"]["sha256"] == (
        "192bce63a94ecd45e88be7538414d063e4e54fa0931a70ca356aeb218af8bd08"
    )
    assert protocol["storage_plan"]["copy_initial_source"] is False


def test_phase7b9di_preserves_bootstrap_failure_but_allows_progression() -> None:
    seed = _protocol()["seed_iteration"]
    assert seed["original_map_passed"] is False
    assert seed["map_passed"] is False
    assert seed["gate_checks"]["boundary_pass"] is False
    assert seed["progression_passed"] is True
    assert seed["convergence_passed"] is False
    assert seed["progression_classification"] == (
        "bootstrap_nonconverged/progression_eligible"
    )


def test_phase7b9di_keeps_horizon_workers_and_science_gates() -> None:
    protocol = _protocol()
    cfg = protocol["configuration"]
    gates = protocol["gates"]
    assert cfg["seed_completed_picard_maps"] == 1
    assert cfg["maximum_picard_maps"] == 24
    assert cfg["maximum_concurrent_processes"] == 2
    assert gates["global_original_operator_residual_below"] == 1.0e-4
    assert gates["global_boundary_spectrum_l1_below"] == 1.0e-3
    assert gates["global_boundary_bolometric_fraction_below"] == 1.0e-3
    assert gates["subsequent_residual_contraction_ratio_below"] == 1.01
    assert gates["each_full_map_wall_time_strictly_below_s"] == 1800.0


def test_phase7b9di_formal_feedback_still_requires_fresh_pair() -> None:
    authorization = _protocol()["authorization"]
    assert authorization["provisional_feedback_is_acceptance_authority"] is False
    assert authorization["formal_pair_only_after_next_consecutive_fresh_residual"]
    assert authorization["material_feedback_before_formal_pair"] is False
