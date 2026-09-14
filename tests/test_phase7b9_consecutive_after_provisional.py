"""Fresh consecutive-map adapter small-file tests."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts import phase7b9_consecutive_after_provisional as consecutive
from scripts import phase7b9_protocol_builders as common


def _write(root: Path, relative: str, payload: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_json(root: Path, relative: str, payload: dict[str, object]) -> None:
    _write(root, relative, json.dumps(payload, indent=2).encode())


def _fixture(root: Path) -> consecutive.ConsecutiveAfterProvisionalSpec:
    previous = "outputs/checkpoints/state_x.dat"
    current = "outputs/checkpoints/state_y.dat"
    _write(root, previous, b"audited-state-x")
    _write(root, current, b"audited-state-y")
    previous_hash = common.sha256(root / previous)
    current_hash = common.sha256(root / current)
    continuation_protocol_path = "outputs/continuation_protocol.json"
    continuation_manifest = "outputs/checkpoints/continuation_manifest.json"
    _write_json(
        root,
        continuation_protocol_path,
        {
            "configuration": {"manifest_path": continuation_manifest},
            "gates": common.memory_safe_seeded_two_map_gates(),
        },
    )
    first = {
        "iteration": 6,
        "input_state_path": previous,
        "input_state_sha256": previous_hash,
        "mapped_state_path": current,
        "mapped_state_sha256": current_hash,
        "global_original_operator_residual": 8.0e-5,
        "boundary_spectrum_l1": 7.0e-4,
        "boundary_bolometric_fraction": 6.0e-4,
        "map_passed": True,
    }
    continuation_summary_path = "outputs/continuation_summary.json"
    _write_json(
        root,
        continuation_summary_path,
        {
            "protocol_sha256": common.sha256(root / continuation_protocol_path),
            "status": "complete",
            "first_low_residual_input_path": previous,
            "first_low_residual_input_sha256": previous_hash,
            "next_consecutive_input_path": current,
            "next_consecutive_input_sha256": current_hash,
            "iterations": [first],
            "decision": {
                "first_low_residual_and_boundary_input_audited": True,
                "provisional_feedback_extraction_authorized": True,
                "formal_h_he_feedback_pair_authorized": False,
            },
        },
    )
    _write_json(
        root,
        continuation_manifest,
        {
            "protocol_sha256": common.sha256(root / continuation_protocol_path),
            "status": "complete",
            "current_input_path": previous,
            "current_input_sha256": previous_hash,
            "next_output_path": current,
            "iterations": [first],
            "active_iteration": None,
            "accepted_state_path": previous,
            "accepted_state_sha256": previous_hash,
        },
    )
    provisional_protocol_path = "outputs/provisional_protocol.json"
    _write_json(root, provisional_protocol_path, {"phase": "provisional"})
    artifact = "outputs/provisional_feedback.npz"
    feedback_manifest = "outputs/provisional_feedback_manifest.json"
    _write(root, artifact, b"small-feedback")
    _write_json(
        root,
        feedback_manifest,
        {
            "status": "complete",
            "state_gate_passed": True,
            "state_path": previous,
            "state_sha256": previous_hash,
            "feedback_artifact_path": artifact,
            "feedback_artifact_sha256": common.sha256(root / artifact),
        },
    )
    provisional_summary_path = "outputs/provisional_summary.json"
    _write_json(
        root,
        provisional_summary_path,
        {
            "protocol_sha256": common.sha256(root / provisional_protocol_path),
            "status": "complete",
            "radiation_state_path": previous,
            "radiation_state_sha256": previous_hash,
            "feedback_manifest_path": feedback_manifest,
            "feedback_artifact_path": artifact,
            "feedback_artifact_sha256": common.sha256(root / artifact),
            "formal_state_gate_passed": True,
            "decision": {
                "provisional_feedback_extraction_complete": True,
                "provisional_feedback_is_acceptance_authority": False,
                "next_consecutive_fresh_residual_authorized": True,
                "formal_h_he_feedback_pair_authorized": False,
            },
        },
    )
    _write(root, consecutive.RUNNER_RELATIVE_PATH, b"runner")
    return consecutive.ConsecutiveAfterProvisionalSpec(
        phase="7B9 consecutive-after-provisional test",
        phase_index=1502,
        classification="[A-preregistered]+[V]+[O]",
        continuation_protocol_path=continuation_protocol_path,
        continuation_summary_path=continuation_summary_path,
        provisional_protocol_path=provisional_protocol_path,
        provisional_summary_path=provisional_summary_path,
        runner_path=consecutive.RUNNER_RELATIVE_PATH,
        transition_receipt_path="outputs/consecutive_transition_receipt.json",
        summary_path="outputs/consecutive_summary.json",
    )


def _bundle(
    root: Path,
) -> tuple[
    consecutive.ConsecutiveAfterProvisionalSpec,
    Path,
    dict[str, object],
    str,
]:
    spec = _fixture(root)
    protocol = consecutive.build_consecutive_after_provisional_protocol(root, spec)
    path = root / "outputs/consecutive_protocol.json"
    consecutive._write_json_atomic(path, protocol)
    return spec, path, protocol, common.sha256(path)


def test_builder_preserves_all_gates_and_uses_no_third_state(tmp_path: Path) -> None:
    _, _, protocol, _ = _bundle(tmp_path)
    cfg = protocol["configuration"]
    assert protocol["gates"] == common.memory_safe_seeded_two_map_gates()
    assert cfg["maximum_concurrent_processes"] == 2
    assert cfg["execute_exactly_one_fresh_map"] is True
    assert cfg["output_path"] == cfg["previous_audited_input_path"]
    assert protocol["overwritten_full_state_claim"][
        "feedback_cached_before_overwrite"
    ]
    assert set(
        source["path"]
        for source in protocol["sources"].values()
        if source["path"].endswith(".dat")
    ) == {cfg["current_input_path"]}
    assert protocol["authorization"][
        "formal_pair_only_if_both_consecutive_residuals_pass"
    ]


@pytest.mark.parametrize("failure", ("feedback", "first_residual", "state"))
def test_builder_rejects_invalid_provisional_or_radiation_lineage(
    tmp_path: Path,
    failure: str,
) -> None:
    spec = _fixture(tmp_path)
    if failure == "feedback":
        path = tmp_path / spec.provisional_summary_path
        summary = json.loads(path.read_text())
        summary["formal_state_gate_passed"] = False
        path.write_text(json.dumps(summary))
    elif failure == "first_residual":
        path = tmp_path / spec.continuation_summary_path
        summary = json.loads(path.read_text())
        summary["iterations"][-1]["global_original_operator_residual"] = 1.0e-4
        path.write_text(json.dumps(summary))
    else:
        (tmp_path / "outputs/checkpoints/state_y.dat").write_bytes(b"drift")
    with pytest.raises(RuntimeError):
        consecutive.build_consecutive_after_provisional_protocol(tmp_path, spec)


def test_transition_swaps_y_to_input_and_x_to_output_only_after_cached_feedback(
    tmp_path: Path,
) -> None:
    _, path, protocol, digest = _bundle(tmp_path)
    cfg = protocol["configuration"]
    artifact = tmp_path / protocol["sources"]["provisional_feedback_artifact"][
        "path"
    ]
    artifact_before = artifact.read_bytes()
    manifest = consecutive.prepare_transition(tmp_path, path, digest)
    assert manifest["status"] == "running"
    assert manifest["current_input_path"] == cfg["current_input_path"]
    assert manifest["current_input_sha256"] == cfg["current_input_sha256"]
    assert manifest["next_output_path"] == cfg["output_path"]
    assert "accepted_state_path" not in manifest
    assert artifact.read_bytes() == artifact_before
    receipt = tmp_path / cfg["transition_receipt_path"]
    assert receipt.is_file()
    (tmp_path / cfg["output_path"]).write_bytes(b"partially-overwritten-x")
    resumed = consecutive.prepare_transition(tmp_path, path, digest)
    assert resumed["pending_consecutive_confirmation_protocol_sha256"] == digest


@pytest.mark.parametrize(
    ("fresh_residual", "expected_pass"),
    ((9.0e-5, True), (1.1e-4, False)),
)
def test_confirmation_requires_two_consecutive_residuals(
    tmp_path: Path,
    fresh_residual: float,
    expected_pass: bool,
) -> None:
    _, _, protocol, digest = _bundle(tmp_path)
    first = json.loads(
        (tmp_path / "outputs/checkpoints/continuation_manifest.json").read_text()
    )["iterations"][0]
    fresh = {
        "iteration": 7,
        "input_state_path": first["mapped_state_path"],
        "input_state_sha256": first["mapped_state_sha256"],
        "mapped_state_path": first["input_state_path"],
        "mapped_state_sha256": "9" * 64,
        "global_original_operator_residual": fresh_residual,
        "boundary_spectrum_l1": 8.0e-4,
        "boundary_bolometric_fraction": 7.0e-4,
        "map_passed": True,
    }
    summary = consecutive._confirmation_summary(
        protocol,
        {"iterations": [first, fresh]},
        digest,
    )
    assert summary["decision"][
        "two_consecutive_fixed_matter_states_converged"
    ] is expected_pass
    assert summary["decision"][
        "formal_h_he_feedback_pair_authorized"
    ] is expected_pass
    assert summary["decision"]["material_feedback_evaluated"] is False
    assert summary["status"] == ("complete" if expected_pass else "continue_required")
