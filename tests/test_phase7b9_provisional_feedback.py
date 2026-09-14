"""Provisional formal-feedback small-file protocol and runner tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import phase7b9_formal_feedback_pair_adapter as feedback
from scripts import phase7b9_provisional_feedback as provisional


def _write(root: Path, relative: str, payload: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_json(root: Path, relative: str, payload: dict[str, object]) -> None:
    _write(root, relative, json.dumps(payload, indent=2).encode())


def _fixture(root: Path) -> provisional.ProvisionalFeedbackProtocolSpec:
    state = "outputs/checkpoints/low_state.dat"
    _write(root, state, b"small-low-state")
    continuation_protocol = "outputs/continuation_protocol.json"
    _write_json(
        root,
        continuation_protocol,
        {
            "gates": {
                "global_original_operator_residual_below": 1.0e-4,
                "global_boundary_spectrum_l1_below": 1.0e-3,
                "global_boundary_bolometric_fraction_below": 1.0e-3,
            }
        },
    )
    continuation_summary = "outputs/continuation_summary.json"
    state_hash = feedback.sha256(root / state)
    row = {
        "input_state_path": state,
        "input_state_sha256": state_hash,
        "mapped_state_path": "outputs/checkpoints/next_state.dat",
        "mapped_state_sha256": "1" * 64,
        "global_original_operator_residual": 8.0e-5,
        "boundary_spectrum_l1": 7.0e-4,
        "boundary_bolometric_fraction": 6.0e-4,
        "map_passed": True,
    }
    _write_json(
        root,
        continuation_summary,
        {
            "protocol_sha256": feedback.sha256(root / continuation_protocol),
            "status": "complete",
            "first_low_residual_input_path": state,
            "first_low_residual_input_sha256": state_hash,
            "iterations": [row],
            "decision": {
                "first_low_residual_and_boundary_input_audited": True,
                "provisional_feedback_extraction_authorized": True,
                "provisional_feedback_is_formal_pair_authority": False,
                "formal_h_he_feedback_pair_authorized": False,
            },
        },
    )
    material = "outputs/material.npz"
    _write(root, material, b"material")
    material_protocol = "outputs/material_protocol.json"
    _write_json(
        root,
        material_protocol,
        {"configuration": {"candidate_absolute_relaxation": 0.0625}},
    )
    material_summary = "outputs/material_summary.json"
    _write_json(
        root,
        material_summary,
        {
            "protocol_sha256": feedback.sha256(root / material_protocol),
            "candidate_absolute_relaxation": 0.0625,
            "candidate_path": material,
            "candidate_sha256": feedback.sha256(root / material),
            "decision": {
                "material_candidate_gate_passed": True,
                "candidate_accepted_as_nonlinear_step": False,
            },
        },
    )
    old = "outputs/old.npz"
    template = "outputs/feedback_template.json"
    adapter = "scripts/formal_adapter.py"
    runner = provisional.RUNNER_RELATIVE_PATH
    for path, payload in (
        (old, b"old"),
        (template, b"{}"),
        (adapter, b"adapter"),
        (runner, b"provisional"),
    ):
        _write(root, path, payload)
    return provisional.ProvisionalFeedbackProtocolSpec(
        phase="7B9 provisional test",
        phase_index=1501,
        classification="[A-provisional]+[V]+[O]",
        continuation_protocol_path=continuation_protocol,
        continuation_summary_path=continuation_summary,
        material_protocol_path=material_protocol,
        material_summary_path=material_summary,
        material_path=material,
        physical_old_time_level_path=old,
        phase7b7j_protocol_path=template,
        adapter_runner_path=adapter,
        provisional_runner_path=runner,
        feedback_work_directory=(
            "outputs/checkpoints/phase7b9_provisional_feedback_test"
        ),
        feedback_output="outputs/provisional_feedback.npz",
        summary_path="outputs/provisional_summary.json",
    )


def test_builder_freezes_one_unauthorized_feedback_state(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    protocol = provisional.build_provisional_feedback_protocol(tmp_path, spec)
    cfg = protocol["configuration"]
    assert cfg["material_candidate_absolute_relaxation"] == 0.0625
    assert cfg["maximum_concurrent_processes"] == 2
    assert cfg["transport_or_source_iteration"] is False
    assert cfg["material_update"] is False
    assert cfg["radiation_update"] is False
    assert protocol["formal_state_gates"] == feedback._formal_state_gates()
    assert protocol["authorization"] == {
        "evaluate_exactly_one_provisional_feedback_state": True,
        "cache_only_small_assembled_feedback_artifact": True,
        "provisional_feedback_is_acceptance_authority": False,
        "next_consecutive_fresh_residual_required": True,
        "formal_pair_authorized": False,
        "material_update": False,
        "radiation_update": False,
        "accept_dynamic_nlte_solution": False,
    }


@pytest.mark.parametrize("failure", ("residual", "decision", "material", "bytes"))
def test_builder_rejects_missing_first_state_gate(tmp_path: Path, failure: str) -> None:
    spec = _fixture(tmp_path)
    if failure in {"residual", "decision"}:
        path = tmp_path / spec.continuation_summary_path
        summary = json.loads(path.read_text())
        if failure == "residual":
            summary["iterations"][-1]["global_original_operator_residual"] = 1.0e-4
        else:
            summary["decision"]["provisional_feedback_extraction_authorized"] = False
        path.write_text(json.dumps(summary))
    elif failure == "material":
        path = tmp_path / spec.material_summary_path
        summary = json.loads(path.read_text())
        summary["candidate_absolute_relaxation"] = 0.125
        path.write_text(json.dumps(summary))
    else:
        (tmp_path / "outputs/checkpoints/low_state.dat").write_bytes(b"drifted")
    with pytest.raises(RuntimeError):
        provisional.build_provisional_feedback_protocol(tmp_path, spec)


def test_runner_caches_artifact_but_keeps_pair_unauthorized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _fixture(tmp_path)
    protocol = provisional.build_provisional_feedback_protocol(tmp_path, spec)
    protocol_path = tmp_path / "outputs/provisional_protocol.json"
    provisional._write_json_atomic(protocol_path, protocol)
    digest = feedback.sha256(protocol_path)
    artifact = tmp_path / spec.feedback_output
    artifact.write_bytes(b"assembled-small-feedback")
    work = tmp_path / spec.feedback_work_directory / "previous"
    work.mkdir(parents=True)
    (work / "block00.npz").write_bytes(b"partial")
    manifest_path = tmp_path / spec.feedback_work_directory / "previous_manifest.json"
    manifest = {
        "status": "complete",
        "state_path": protocol["sources"]["previous_radiation"]["path"],
        "state_sha256": protocol["sources"]["previous_radiation"]["sha256"],
        "feedback_artifact_path": spec.feedback_output,
        "feedback_artifact_sha256": feedback.sha256(artifact),
        "state_gate_passed": True,
    }
    monkeypatch.setattr(provisional, "ROOT", tmp_path)
    monkeypatch.setattr(
        feedback,
        "load_frozen_pair_protocol",
        lambda *_args, **_kwargs: protocol,
    )
    monkeypatch.setattr(feedback, "_validate_worker_template_sources", lambda _p: {})
    monkeypatch.setattr(feedback, "_run_feedback_state", lambda *_args: manifest)
    monkeypatch.setattr(
        feedback,
        "_feedback_manifest_path",
        lambda _protocol, _label: manifest_path,
    )
    summary = provisional.run_provisional_feedback(protocol_path, digest)
    assert summary["status"] == "complete"
    assert summary["decision"]["provisional_feedback_extraction_complete"] is True
    assert summary["decision"]["provisional_feedback_is_acceptance_authority"] is False
    assert summary["decision"]["formal_h_he_feedback_pair_authorized"] is False
    assert summary["decision"]["material_feedback_authorized"] is False
    assert artifact.read_bytes() == b"assembled-small-feedback"
    assert not (work / "block00.npz").exists()
