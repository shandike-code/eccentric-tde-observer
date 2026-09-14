"""Formal-pair reuse of a provisional previous artifact: small-file tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import phase7b9_formal_feedback_pair_adapter as adapter
from scripts import phase7b9_formal_pair_from_provisional as pair


def _write(root: Path, relative: str, payload: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_json(root: Path, relative: str, payload: dict[str, object]) -> None:
    _write(root, relative, json.dumps(payload, indent=2).encode())


def _acceptance() -> dict[str, object]:
    return {
        "gates": {
            "consecutive_inner_radiation_state_count_at_least": 2,
            "each_global_original_operator_residual_below": 1.0e-4,
            "each_boundary_spectrum_l1_below": 1.0e-3,
            "each_boundary_bolometric_fraction_below": 1.0e-3,
            "each_formal_feedback_state_gate_passed": True,
            "maximum_last_two_photoionization_volume_l1_below": 1.0e-3,
            "maximum_last_two_total_recombination_volume_l1_below": 1.0e-3,
            "last_two_atomic_heating_volume_l1_below": 1.0e-3,
            "last_two_direct_heating_volume_l1_below": 1.0e-3,
            "last_two_formal_heating_volume_l1_below": 1.0e-3,
            "inner_noise_to_trial_signal_l2_ratio_below": 0.1,
            "candidate_to_base_residual_l2_ratio_below": 1.0,
            "candidate_to_base_mass_weighted_norm_ratio_below": 1.0,
            "candidate_to_base_maximum_cell_norm_ratio_below": 1.0,
            "candidate_state_must_match_frozen_phase7b9i_bytes": True,
            "minimum_population_fraction_at_least": 0.0,
            "all_residual_components_finite": True,
        },
        "authorization": {
            "accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass": True,
            "reject_this_trial_if_any_gate_fails": True,
            "accept_dynamic_nlte_solution": False,
        },
    }


def _fixture(root: Path) -> pair.FormalPairFromProvisionalSpec:
    previous = "outputs/checkpoints/overwritten_x.dat"
    final = "outputs/checkpoints/final_y.dat"
    _write(root, previous, b"new-z-bytes-now")
    _write(root, final, b"audited-y-bytes")
    previous_old_hash = "2" * 64
    final_hash = adapter.sha256(root / final)
    confirmation_protocol = "outputs/confirmation_protocol.json"
    _write_json(root, confirmation_protocol, {"phase": "confirmation"})
    confirmation_summary = "outputs/confirmation_summary.json"
    checks = {
        "first_residual_pass": True,
        "fresh_residual_pass": True,
        "first_boundary_pass": True,
        "fresh_boundary_pass": True,
        "fresh_map_gates_pass": True,
        "provisional_feedback_cached_pass": True,
    }
    _write_json(
        root,
        confirmation_summary,
        {
            "protocol_sha256": adapter.sha256(root / confirmation_protocol),
            "status": "complete",
            "previous_converged_state_path": previous,
            "previous_converged_state_sha256": previous_old_hash,
            "previous_state_bytes_retained": False,
            "previous_global_original_operator_residual": 8.0e-5,
            "previous_boundary_spectrum_l1": 7.0e-4,
            "previous_boundary_bolometric_fraction": 6.0e-4,
            "input_state_path": final,
            "input_state_sha256": final_hash,
            "input_global_original_operator_residual": 9.0e-5,
            "input_boundary_spectrum_l1": 8.0e-4,
            "input_boundary_bolometric_fraction": 7.0e-4,
            "gate_checks": checks,
            "decision": {
                "two_consecutive_fixed_matter_states_converged": True,
                "provisional_previous_feedback_valid_for_pair": True,
                "final_feedback_extraction_authorized": True,
                "formal_h_he_feedback_pair_authorized": True,
                "material_feedback_evaluated": False,
            },
        },
    )
    provisional_protocol = "outputs/provisional_protocol.json"
    _write_json(root, provisional_protocol, {"phase": "provisional"})
    previous_artifact = "outputs/previous_feedback.npz"
    previous_manifest = "outputs/previous_feedback_manifest.json"
    _write(root, previous_artifact, b"cached-previous-feedback")
    artifact_hash = adapter.sha256(root / previous_artifact)
    _write_json(
        root,
        previous_manifest,
        {
            "status": "complete",
            "state_gate_passed": True,
            "state_path": previous,
            "state_sha256": previous_old_hash,
            "feedback_artifact_path": previous_artifact,
            "feedback_artifact_sha256": artifact_hash,
        },
    )
    provisional_summary = "outputs/provisional_summary.json"
    _write_json(
        root,
        provisional_summary,
        {
            "protocol_sha256": adapter.sha256(root / provisional_protocol),
            "status": "complete",
            "radiation_state_path": previous,
            "radiation_state_sha256": previous_old_hash,
            "feedback_manifest_path": previous_manifest,
            "feedback_artifact_path": previous_artifact,
            "feedback_artifact_sha256": artifact_hash,
            "formal_state_gate_passed": True,
            "decision": {
                "provisional_feedback_extraction_complete": True,
                "provisional_feedback_is_acceptance_authority": False,
                "formal_h_he_feedback_pair_authorized": False,
            },
        },
    )
    acceptance = "outputs/acceptance.json"
    _write_json(root, acceptance, _acceptance())
    material = "outputs/material.npz"
    material_protocol = "outputs/material_protocol.json"
    material_summary = "outputs/material_summary.json"
    _write(root, material, b"half-material")
    _write_json(
        root,
        material_protocol,
        {"configuration": {"candidate_absolute_relaxation": 0.0625}},
    )
    _write_json(
        root,
        material_summary,
        {
            "protocol_sha256": adapter.sha256(root / material_protocol),
            "candidate_absolute_relaxation": 0.0625,
            "candidate_path": material,
            "candidate_sha256": adapter.sha256(root / material),
            "decision": {
                "material_candidate_gate_passed": True,
                "candidate_accepted_as_nonlinear_step": False,
            },
        },
    )
    base_residual = "outputs/base_residual.npy"
    base_summary = "outputs/base_summary.json"
    _write(root, base_residual, b"base-residual")
    _write_json(
        root,
        base_summary,
        {
            "encoded_residual_path": base_residual,
            "encoded_residual_sha256": adapter.sha256(root / base_residual),
            "decision": {"phase7b9f_gate_passed": True},
        },
    )
    old = "outputs/old.npz"
    template = "outputs/feedback_template.json"
    adapter_runner = "scripts/formal_adapter.py"
    runner = pair.RUNNER_RELATIVE_PATH
    for path, content in (
        (old, b"old"),
        (template, b"{}"),
        (adapter_runner, b"adapter"),
        (runner, b"pair-runner"),
    ):
        _write(root, path, content)
    return pair.FormalPairFromProvisionalSpec(
        phase="7B9 formal pair provisional test",
        phase_index=1503,
        classification="[A-preregistered]+[V]+[O]",
        confirmation_protocol_path=confirmation_protocol,
        confirmation_summary_path=confirmation_summary,
        provisional_protocol_path=provisional_protocol,
        provisional_summary_path=provisional_summary,
        trial_acceptance_path=acceptance,
        material_protocol_path=material_protocol,
        material_summary_path=material_summary,
        material_path=material,
        base_feedback_summary_path=base_summary,
        base_residual_path=base_residual,
        physical_old_time_level_path=old,
        phase7b7j_protocol_path=template,
        adapter_runner_path=adapter_runner,
        pair_runner_path=runner,
        feedback_work_directory="outputs/checkpoints/formal_pair_provisional_test",
        final_feedback_output="outputs/final_feedback.npz",
        target_material_output="outputs/target_material.npz",
        encoded_residual_output="outputs/encoded_residual.npy",
        summary_path="outputs/pair_summary.json",
        figure_path="outputs/pair.png",
    )


def _bundle(
    root: Path,
) -> tuple[pair.FormalPairFromProvisionalSpec, Path, dict[str, object], str]:
    spec = _fixture(root)
    protocol = pair.build_formal_pair_from_provisional_protocol(root, spec)
    path = root / "outputs/pair_protocol.json"
    path.write_text(json.dumps(protocol, indent=2))
    return spec, path, protocol, adapter.sha256(path)


def test_builder_reuses_only_cached_previous_and_audits_live_final(
    tmp_path: Path,
) -> None:
    _, _, protocol, _ = _bundle(tmp_path)
    assert "previous_radiation" not in protocol["sources"]
    assert protocol["overwritten_previous_radiation_claim"] == {
        "path": "outputs/checkpoints/overwritten_x.dat",
        "sha256": "2" * 64,
        "full_state_retained": False,
        "formal_feedback_cached_and_state_gate_passed": True,
    }
    assert protocol["sources"]["final_radiation"]["path"] == (
        "outputs/checkpoints/final_y.dat"
    )
    assert protocol["configuration"]["maximum_concurrent_processes"] == 2
    assert protocol["configuration"]["reuse_provisional_previous_feedback"]
    gates = protocol["acceptance_gates"]
    assert "candidate_state_must_match_frozen_phase7b9i_bytes" not in gates
    assert gates["candidate_state_must_match_frozen_phase7b9de_bytes"] is True
    assert gates["each_global_original_operator_residual_below"] == 1.0e-4


@pytest.mark.parametrize("failure", ("confirmation", "provisional", "final"))
def test_builder_rejects_broken_pair_lineage(tmp_path: Path, failure: str) -> None:
    spec = _fixture(tmp_path)
    if failure == "confirmation":
        path = tmp_path / spec.confirmation_summary_path
        summary = json.loads(path.read_text())
        summary["gate_checks"]["fresh_residual_pass"] = False
        path.write_text(json.dumps(summary))
    elif failure == "provisional":
        path = tmp_path / spec.provisional_summary_path
        summary = json.loads(path.read_text())
        summary["formal_state_gate_passed"] = False
        path.write_text(json.dumps(summary))
    else:
        (tmp_path / "outputs/checkpoints/final_y.dat").write_bytes(b"drift")
    with pytest.raises(RuntimeError):
        pair.build_formal_pair_from_provisional_protocol(tmp_path, spec)


def test_runner_injects_cached_previous_only_for_pair_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, protocol_path, protocol, digest = _bundle(tmp_path)
    final_artifact = tmp_path / protocol["configuration"]["final_feedback_output"]
    final_artifact.write_bytes(b"final-feedback")
    final_manifest = {
        "status": "complete",
        "state_gate_passed": True,
        "state_path": protocol["sources"]["final_radiation"]["path"],
        "state_sha256": protocol["sources"]["final_radiation"]["sha256"],
        "feedback_artifact_path": protocol["configuration"]["final_feedback_output"],
        "feedback_artifact_sha256": adapter.sha256(final_artifact),
    }
    monkeypatch.setattr(pair, "ROOT", tmp_path)
    monkeypatch.setattr(adapter, "ROOT", tmp_path)
    monkeypatch.setattr(adapter, "_validate_worker_template_sources", lambda _p: {})
    monkeypatch.setattr(adapter, "_run_feedback_state", lambda *_args: final_manifest)
    observed: dict[str, object] = {}

    def fake_run_pair(_path: Path, _hash: str) -> dict[str, object]:
        loaded = adapter.load_frozen_pair_protocol(
            _path, _hash, validate_sources=True
        )
        previous = adapter._load_reused_feedback_manifest(loaded, "previous")
        final = adapter._load_reused_feedback_manifest(loaded, "final")
        observed["previous"] = previous
        observed["final"] = final
        return {"decision": {"formal_pair_evaluated": True}}

    monkeypatch.setattr(adapter, "run_pair", fake_run_pair)
    original_protocol_loader = adapter.load_frozen_pair_protocol
    original_manifest_loader = adapter._load_reused_feedback_manifest
    result = pair.run_formal_pair(protocol_path, digest)
    assert result["decision"]["formal_pair_evaluated"] is True
    assert observed["previous"]["state_sha256"] == "2" * 64
    assert observed["final"] is final_manifest
    assert adapter.load_frozen_pair_protocol is original_protocol_loader
    assert adapter._load_reused_feedback_manifest is original_manifest_loader
