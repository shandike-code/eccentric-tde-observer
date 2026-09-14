"""Small-file-only provisional-feedback preregistration tests."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from scripts import phase7b9_formal_feedback_pair_adapter as feedback
from scripts import phase7b9_provisional_feedback as provisional
from scripts import phase7b9dq_preregister_provisional_feedback as prereg
from scripts import phase7b9dq_provisional_feedback_adapter as claim_adapter


def _write(root: Path, relative: str, payload: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_json(root: Path, relative: str, payload: dict[str, object]) -> None:
    _write(root, relative, json.dumps(payload, indent=2).encode("utf-8"))


def _source(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": feedback.sha256(path),
    }


def _fixture(root: Path) -> provisional.PausedProvisionalFeedbackProtocolSpec:
    helper = "scripts/upstream_helper.py"
    _write(root, helper, b"helper\n")
    continuation_protocol = "outputs/dp_protocol.json"
    protocol = {
        "sources": {"upstream_helper": _source(root, helper)},
        "configuration": {
            "maximum_concurrent_processes": 2,
            "raw_float64_checkpoint_size_bytes": 9_000_000_000,
        },
        "gates": {
            "global_original_operator_residual_below": 1.0e-4,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
        },
        "authorization": {
            "pause_at_first_low_residual_and_boundary_input": True,
            "provisional_feedback_extraction_at_pause": True,
            "formal_pair_requires_next_consecutive_fresh_residual": True,
        },
    }
    _write_json(root, continuation_protocol, protocol)
    protocol_sha = feedback.sha256(root / continuation_protocol)

    accepted_path = "outputs/checkpoints/accepted.dat"
    next_path = "outputs/checkpoints/next.dat"
    accepted_sha = "a" * 64
    next_sha = "b" * 64
    rows = [
        {
            "iteration": 0,
            "input_state_path": "outputs/checkpoints/seed.dat",
            "input_state_sha256": "c" * 64,
            "mapped_state_path": accepted_path,
            "mapped_state_sha256": accepted_sha,
            "global_original_operator_residual": 2.0e-4,
            "boundary_spectrum_l1": 8.0e-4,
            "boundary_bolometric_fraction": 7.0e-4,
            "convergence_passed": False,
            "map_passed": False,
        },
        {
            "iteration": 1,
            "input_state_path": accepted_path,
            "input_state_sha256": accepted_sha,
            "mapped_state_path": next_path,
            "mapped_state_sha256": next_sha,
            "global_original_operator_residual": 8.0e-5,
            "boundary_spectrum_l1": 7.0e-4,
            "boundary_bolometric_fraction": 6.0e-4,
            "convergence_passed": True,
            "map_passed": True,
        },
    ]
    manifest = "outputs/dp_manifest.json"
    _write_json(
        root,
        manifest,
        {
            "protocol_sha256": protocol_sha,
            "status": "provisional_pause",
            "current_input_path": accepted_path,
            "current_input_sha256": accepted_sha,
            "next_output_path": next_path,
            "next_output_sha256": next_sha,
            "accepted_state_path": accepted_path,
            "accepted_state_sha256": accepted_sha,
            "iterations": rows,
            "active_iteration": None,
        },
    )
    summary = "outputs/dp_summary.json"
    _write_json(
        root,
        summary,
        {
            "protocol_sha256": protocol_sha,
            "status": "provisional_pause",
            "accepted_state_path": accepted_path,
            "accepted_state_sha256": accepted_sha,
            "first_low_residual_input_path": accepted_path,
            "first_low_residual_input_sha256": accepted_sha,
            "next_consecutive_input_path": next_path,
            "next_consecutive_input_sha256": next_sha,
            "iterations": rows,
            "decision": {
                "first_low_residual_and_boundary_input_audited": True,
                "provisional_feedback_extraction_authorized": True,
                "provisional_feedback_is_formal_pair_authority": False,
                "next_consecutive_fresh_residual_required": True,
                "formal_h_he_feedback_pair_authorized": False,
                "material_feedback_authorized": False,
                "dynamic_nlte_solution_accepted": False,
            },
        },
    )

    material = "outputs/material.npz"
    _write(root, material, b"small material")
    material_protocol = "outputs/material_protocol.json"
    _write_json(
        root,
        material_protocol,
        {
            "sources": {},
            "configuration": {"candidate_absolute_relaxation": 0.0625},
        },
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
    supporting = {
        "outputs/old.npz": b"old",
        "outputs/phase7b7j_protocol.json": b"{}",
        provisional.PAUSED_ADAPTER_RELATIVE_PATH: b"claim adapter",
        provisional.RUNNER_RELATIVE_PATH: b"provisional",
        provisional.PAUSED_PREREGISTER_RELATIVE_PATH: b"preregister",
    }
    for relative, payload in supporting.items():
        _write(root, relative, payload)

    return provisional.PausedProvisionalFeedbackProtocolSpec(
        phase="7B9dq test",
        phase_index=1704,
        classification="[A-preregistered]+[V]+[O]",
        continuation_protocol_path=continuation_protocol,
        continuation_manifest_path=manifest,
        continuation_summary_path=summary,
        material_protocol_path=material_protocol,
        material_summary_path=material_summary,
        material_path=material,
        physical_old_time_level_path="outputs/old.npz",
        phase7b7j_protocol_path="outputs/phase7b7j_protocol.json",
        adapter_runner_path=provisional.PAUSED_ADAPTER_RELATIVE_PATH,
        provisional_runner_path=provisional.RUNNER_RELATIVE_PATH,
        preregister_runner_path=provisional.PAUSED_PREREGISTER_RELATIVE_PATH,
        feedback_work_directory="outputs/checkpoints/phase7b9dq_provisional",
        feedback_output="outputs/phase7b9dq_provisional_feedback.npz",
        summary_path="outputs/phase7b9dq_provisional_feedback_summary.json",
    )


def _rewrite_protocol_hash(root: Path, spec: provisional.PausedProvisionalFeedbackProtocolSpec) -> None:
    digest = feedback.sha256(root / spec.continuation_protocol_path)
    for relative in (spec.continuation_manifest_path, spec.continuation_summary_path):
        value = json.loads((root / relative).read_text(encoding="utf-8"))
        value["protocol_sha256"] = digest
        _write_json(root, relative, value)


def test_builder_pins_only_small_sources_and_keeps_full_states_as_claims(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _fixture(tmp_path)
    original_sha = feedback.sha256

    def guarded_sha(path: Path) -> str:
        assert path.suffix.lower() != ".dat"
        return original_sha(path)

    monkeypatch.setattr(feedback, "sha256", guarded_sha)
    payload = provisional.build_paused_provisional_feedback_protocol(tmp_path, spec)
    assert all(not source["path"].endswith(".dat") for source in payload["sources"].values())
    assert payload["full_state_claims"]["previous_radiation"]["path"].endswith("accepted.dat")
    assert payload["full_state_claims"]["next_consecutive_radiation"]["path"].endswith("next.dat")
    runtime = claim_adapter._runtime_pair_protocol(payload)
    assert runtime["sources"]["previous_radiation"] == payload[
        "full_state_claims"
    ]["previous_radiation"]
    assert not (tmp_path / "outputs/checkpoints/accepted.dat").exists()
    assert payload["configuration"]["maximum_concurrent_processes"] == 2
    assert payload["formal_state_gates"] == feedback._formal_state_gates()
    assert payload["upstream_lineage"]["full_state_bytes_read_by_builder"] is False
    assert payload["upstream_lineage"]["full_state_bytes_hashed_by_builder"] is False


@pytest.mark.parametrize("bad_status", ["running", "maximum_maps_exhausted"])
def test_builder_rejects_wrong_pause_status(tmp_path: Path, bad_status: str) -> None:
    spec = _fixture(tmp_path)
    path = tmp_path / spec.continuation_summary_path
    value = json.loads(path.read_text(encoding="utf-8"))
    value["status"] = bad_status
    _write_json(tmp_path, spec.continuation_summary_path, value)
    with pytest.raises(RuntimeError, match="provisional_pause"):
        provisional.build_paused_provisional_feedback_protocol(tmp_path, spec)


def test_builder_rejects_manifest_summary_iteration_mismatch(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    path = tmp_path / spec.continuation_summary_path
    value = json.loads(path.read_text(encoding="utf-8"))
    value["iterations"][0]["global_original_operator_residual"] = 3.0e-4
    _write_json(tmp_path, spec.continuation_summary_path, value)
    with pytest.raises(RuntimeError, match="atomic provisional_pause"):
        provisional.build_paused_provisional_feedback_protocol(tmp_path, spec)


def test_builder_rejects_protocol_sha_and_source_pin_drift(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    manifest = tmp_path / spec.continuation_manifest_path
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["protocol_sha256"] = "f" * 64
    _write_json(tmp_path, spec.continuation_manifest_path, value)
    with pytest.raises(RuntimeError, match="protocol SHA"):
        provisional.build_paused_provisional_feedback_protocol(tmp_path, spec)

    spec = _fixture(tmp_path)
    _write(tmp_path, "scripts/upstream_helper.py", b"drifted helper\n")
    with pytest.raises(RuntimeError, match="source pin changed"):
        provisional.build_paused_provisional_feedback_protocol(tmp_path, spec)


def test_builder_requires_first_convergence_only_at_last_map(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    for relative in (spec.continuation_manifest_path, spec.continuation_summary_path):
        path = tmp_path / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        value["iterations"][0]["convergence_passed"] = True
        _write_json(tmp_path, relative, value)
    with pytest.raises(RuntimeError, match="first and only converged"):
        provisional.build_paused_provisional_feedback_protocol(tmp_path, spec)


def test_builder_rejects_formal_pair_authority_drift(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    path = tmp_path / spec.continuation_summary_path
    value = json.loads(path.read_text(encoding="utf-8"))
    value["decision"]["provisional_feedback_is_formal_pair_authority"] = True
    _write_json(tmp_path, spec.continuation_summary_path, value)
    with pytest.raises(RuntimeError, match="feedback decision"):
        provisional.build_paused_provisional_feedback_protocol(tmp_path, spec)


def test_builder_rejects_accepted_and_next_lineage_drift(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    path = tmp_path / spec.continuation_summary_path
    value = json.loads(path.read_text(encoding="utf-8"))
    value["next_consecutive_input_sha256"] = "d" * 64
    _write_json(tmp_path, spec.continuation_summary_path, value)
    with pytest.raises(RuntimeError, match="next-consecutive"):
        provisional.build_paused_provisional_feedback_protocol(tmp_path, spec)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("global_original_operator_residual", 1.0e-4),
        ("boundary_spectrum_l1", 1.0e-3),
        ("boundary_bolometric_fraction", 1.0e-3),
    ],
)
def test_builder_rejects_threshold_equality(
    tmp_path: Path, key: str, value: float
) -> None:
    spec = _fixture(tmp_path)
    for relative in (spec.continuation_manifest_path, spec.continuation_summary_path):
        path = tmp_path / relative
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["iterations"][-1][key] = value
        _write_json(tmp_path, relative, payload)
    with pytest.raises(RuntimeError, match="threshold"):
        provisional.build_paused_provisional_feedback_protocol(tmp_path, spec)


def test_builder_rejects_inherited_key_collision(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    collision = "scripts/collision.py"
    _write(tmp_path, collision, b"collision")
    path = tmp_path / spec.continuation_protocol_path
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["sources"]["paused_continuation_protocol"] = _source(tmp_path, collision)
    _write_json(tmp_path, spec.continuation_protocol_path, payload)
    _rewrite_protocol_hash(tmp_path, spec)
    with pytest.raises(RuntimeError, match="source-key collision"):
        provisional.build_paused_provisional_feedback_protocol(tmp_path, spec)


def test_builder_rejects_dat_in_upstream_source_set_without_hashing_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _fixture(tmp_path)
    forbidden = "outputs/checkpoints/forbidden.dat"
    _write(tmp_path, forbidden, b"must not be hashed")
    path = tmp_path / spec.continuation_protocol_path
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["sources"]["forbidden"] = {
        "path": forbidden,
        "size_bytes": len(b"must not be hashed"),
        "sha256": "e" * 64,
    }
    _write_json(tmp_path, spec.continuation_protocol_path, payload)
    _rewrite_protocol_hash(tmp_path, spec)
    original_sha = feedback.sha256

    def guarded_sha(path: Path) -> str:
        assert path.suffix.lower() != ".dat"
        return original_sha(path)

    monkeypatch.setattr(feedback, "sha256", guarded_sha)
    with pytest.raises(RuntimeError, match=r"refuses any \.dat source"):
        provisional.build_paused_provisional_feedback_protocol(tmp_path, spec)


def test_cli_atomically_writes_protocol_and_returns_file_hash(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    argv = [
        "--phase", spec.phase,
        "--phase-index", str(spec.phase_index),
        "--classification", spec.classification,
        "--continuation-protocol", spec.continuation_protocol_path,
        "--continuation-manifest", spec.continuation_manifest_path,
        "--continuation-summary", spec.continuation_summary_path,
        "--material-protocol", spec.material_protocol_path,
        "--material-summary", spec.material_summary_path,
        "--material", spec.material_path,
        "--physical-old-time-level", spec.physical_old_time_level_path,
        "--phase7b7j-protocol", spec.phase7b7j_protocol_path,
        "--feedback-work-directory", spec.feedback_work_directory,
        "--feedback-output", spec.feedback_output,
        "--summary", spec.summary_path,
        "--output", "outputs/frozen_dq_protocol.json",
    ]
    payload, digest = prereg.main(argv, root=tmp_path)
    output = tmp_path / "outputs/frozen_dq_protocol.json"
    assert digest == feedback.sha256(output)
    assert json.loads(output.read_text(encoding="utf-8")) == payload
    assert not output.with_name(f"{output.name}.tmp").exists()


def test_cli_refuses_dat_argument_and_writes_nothing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"\.json"):
        prereg.main(
            [
                "--phase", "bad",
                "--phase-index", "1",
                "--classification", "[O]",
                "--continuation-protocol", "outputs/bad.dat",
                "--continuation-manifest", "outputs/m.json",
                "--continuation-summary", "outputs/s.json",
                "--material-protocol", "outputs/mp.json",
                "--material-summary", "outputs/ms.json",
                "--material", "outputs/m.npz",
                "--physical-old-time-level", "outputs/o.npz",
                "--phase7b7j-protocol", "outputs/t.json",
                "--feedback-work-directory", "outputs/checkpoints/test_provisional",
                "--feedback-output", "outputs/f.npz",
                "--summary", "outputs/f.json",
                "--output", "outputs/should_not_exist.json",
            ],
            root=tmp_path,
        )
    assert not (tmp_path / "outputs/should_not_exist.json").exists()
