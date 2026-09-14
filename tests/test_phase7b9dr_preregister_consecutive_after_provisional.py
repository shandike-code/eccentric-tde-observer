"""7B9dr claim-only consecutive-map preregistration tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts import phase7b9_consecutive_after_provisional as consecutive
from scripts import phase7b9_protocol_builders as common
from scripts import phase7b9_provisional_feedback as provisional
from scripts import phase7b9dr_preregister_consecutive_after_provisional as prereg


PREVIOUS_BYTES = b"previous"
CURRENT_BYTES = b"current!"


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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
        "sha256": common.sha256(path),
    }


def _fixture(root: Path) -> consecutive.PausedConsecutiveAfterProvisionalSpec:
    previous = "outputs/checkpoints/previous.dat"
    current = "outputs/checkpoints/current.dat"
    previous_sha = _digest(PREVIOUS_BYTES)
    current_sha = _digest(CURRENT_BYTES)
    helper = "scripts/dp_helper.py"
    _write(root, helper, b"helper")

    dp_protocol_path = "outputs/dp_protocol.json"
    dp_manifest_path = "outputs/checkpoints/dp_manifest.json"
    dp_summary_path = "outputs/dp_summary.json"
    dp_protocol = {
        "sources": {"dp_helper": _source(root, helper)},
        "configuration": {
            "manifest_path": dp_manifest_path,
            "maximum_concurrent_processes": 2,
            "natural_frequency_block_count": 76,
            "physical_frequency_groups": 9632,
            "raw_float64_checkpoint_size_bytes": len(PREVIOUS_BYTES),
        },
        "gates": common.memory_safe_seeded_two_map_gates(),
        "authorization": {
            "pause_at_first_low_residual_and_boundary_input": True,
            "provisional_feedback_extraction_at_pause": True,
            "formal_pair_requires_next_consecutive_fresh_residual": True,
        },
    }
    _write_json(root, dp_protocol_path, dp_protocol)
    dp_sha = common.sha256(root / dp_protocol_path)
    rows = [
        {
            "iteration": 0,
            "input_state_path": "outputs/checkpoints/seed.dat",
            "input_state_sha256": "c" * 64,
            "mapped_state_path": previous,
            "mapped_state_sha256": previous_sha,
            "global_original_operator_residual": 2.0e-4,
            "boundary_spectrum_l1": 8.0e-4,
            "boundary_bolometric_fraction": 7.0e-4,
            "convergence_passed": False,
            "map_passed": False,
        },
        {
            "iteration": 1,
            "input_state_path": previous,
            "input_state_sha256": previous_sha,
            "mapped_state_path": current,
            "mapped_state_sha256": current_sha,
            "global_original_operator_residual": 8.0e-5,
            "boundary_spectrum_l1": 7.0e-4,
            "boundary_bolometric_fraction": 6.0e-4,
            "convergence_passed": True,
            "map_passed": True,
        },
    ]
    _write_json(
        root,
        dp_manifest_path,
        {
            "protocol_sha256": dp_sha,
            "status": "provisional_pause",
            "current_input_path": previous,
            "current_input_sha256": previous_sha,
            "next_output_path": current,
            "next_output_sha256": current_sha,
            "accepted_state_path": previous,
            "accepted_state_sha256": previous_sha,
            "iterations": rows,
            "active_iteration": None,
        },
    )
    _write_json(
        root,
        dp_summary_path,
        {
            "protocol_sha256": dp_sha,
            "status": "provisional_pause",
            "accepted_state_path": previous,
            "accepted_state_sha256": previous_sha,
            "first_low_residual_input_path": previous,
            "first_low_residual_input_sha256": previous_sha,
            "next_consecutive_input_path": current,
            "next_consecutive_input_sha256": current_sha,
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

    dq_helper = "scripts/dq_helper.py"
    _write(root, dq_helper, b"dq helper")
    artifact = "outputs/dq_feedback.npz"
    _write(root, artifact, b"cached feedback")
    artifact_sha = common.sha256(root / artifact)
    dq_protocol_path = "outputs/dq_protocol.json"
    _write_json(
        root,
        dq_protocol_path,
        {
            "sources": {"dq_helper": _source(root, dq_helper)},
            "full_state_claims": {
                "previous_radiation": {
                    "path": previous,
                    "size_bytes": len(PREVIOUS_BYTES),
                    "sha256": previous_sha,
                },
                "next_consecutive_radiation": {
                    "path": current,
                    "size_bytes": len(CURRENT_BYTES),
                    "sha256": current_sha,
                },
            },
            "configuration": {"maximum_concurrent_processes": 2},
            "formal_state_gates": provisional.feedback._formal_state_gates(),
            "radiation_gates": {
                "global_original_operator_residual_below": 1.0e-4,
                "boundary_spectrum_l1_below": 1.0e-3,
                "boundary_bolometric_fraction_below": 1.0e-3,
            },
            "authorization": {
                "evaluate_exactly_one_provisional_feedback_state": True,
                "provisional_feedback_is_acceptance_authority": False,
                "next_consecutive_fresh_residual_required": True,
                "formal_pair_authorized": False,
                "material_update": False,
                "radiation_update": False,
            },
        },
    )
    dq_sha = common.sha256(root / dq_protocol_path)
    dq_manifest_path = "outputs/dq_feedback_manifest.json"
    _write_json(
        root,
        dq_manifest_path,
        {
            "protocol_sha256": dq_sha,
            "status": "complete",
            "state_gate_passed": True,
            "state_path": previous,
            "state_sha256": previous_sha,
            "feedback_artifact_path": artifact,
            "feedback_artifact_sha256": artifact_sha,
        },
    )
    dq_summary_path = "outputs/dq_summary.json"
    _write_json(
        root,
        dq_summary_path,
        {
            "protocol_sha256": dq_sha,
            "status": "complete",
            "radiation_state_path": previous,
            "radiation_state_sha256": previous_sha,
            "feedback_manifest_path": dq_manifest_path,
            "feedback_artifact_path": artifact,
            "feedback_artifact_sha256": artifact_sha,
            "formal_state_gate_passed": True,
            "decision": {
                "provisional_feedback_extraction_complete": True,
                "provisional_feedback_is_acceptance_authority": False,
                "next_consecutive_fresh_residual_authorized": True,
                "formal_h_he_feedback_pair_authorized": False,
                "material_feedback_authorized": False,
                "dynamic_nlte_solution_accepted": False,
            },
        },
    )
    _write(root, consecutive.RUNNER_RELATIVE_PATH, b"runner")
    _write(root, consecutive.PAUSED_PREREGISTER_RELATIVE_PATH, b"preregister")
    return consecutive.PausedConsecutiveAfterProvisionalSpec(
        phase="7B9dr test",
        phase_index=1705,
        classification="[A-preregistered]+[V]+[O]",
        continuation_protocol_path=dp_protocol_path,
        continuation_manifest_path=dp_manifest_path,
        continuation_summary_path=dp_summary_path,
        provisional_protocol_path=dq_protocol_path,
        provisional_manifest_path=dq_manifest_path,
        provisional_summary_path=dq_summary_path,
        provisional_artifact_path=artifact,
        runner_path=consecutive.RUNNER_RELATIVE_PATH,
        preregister_runner_path=consecutive.PAUSED_PREREGISTER_RELATIVE_PATH,
        transition_receipt_path="outputs/dr_transition.json",
        summary_path="outputs/dr_summary.json",
    )


def _rewrite_dp_hash(root: Path, spec: consecutive.PausedConsecutiveAfterProvisionalSpec) -> None:
    digest = common.sha256(root / spec.continuation_protocol_path)
    for relative in (spec.continuation_manifest_path, spec.continuation_summary_path):
        value = json.loads((root / relative).read_text(encoding="utf-8"))
        value["protocol_sha256"] = digest
        _write_json(root, relative, value)


def test_builder_freezes_one_claim_only_fresh_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _fixture(tmp_path)
    original_sha = common.sha256

    def guarded_sha(path: Path) -> str:
        assert path.suffix.lower() != ".dat"
        return original_sha(path)

    monkeypatch.setattr(common, "sha256", guarded_sha)
    protocol = consecutive.build_paused_consecutive_after_provisional_protocol(
        tmp_path, spec
    )
    assert all(not source["path"].endswith(".dat") for source in protocol["sources"].values())
    assert set(protocol["full_state_claims"]) == {
        "previous_audited_input",
        "current_next_consecutive_input",
    }
    assert not (tmp_path / "outputs/checkpoints/previous.dat").exists()
    assert protocol["configuration"]["current_input_path"].endswith("current.dat")
    assert protocol["configuration"]["output_path"].endswith("previous.dat")
    assert protocol["configuration"]["maximum_concurrent_processes"] == 2
    assert protocol["gates"]["each_full_map_wall_time_strictly_below_s"] == 1800.0
    assert protocol["gates"]["block_count_exactly"] == 76
    assert protocol["authorization"]["execute_exactly_one_fresh_map"] is True
    assert protocol["authorization"]["formal_pair_authorized_before_fresh_map"] is False


def test_builder_rejects_pause_lineage_and_threshold_drift(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    summary_path = tmp_path / spec.continuation_summary_path
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["next_consecutive_input_sha256"] = "f" * 64
    _write_json(tmp_path, spec.continuation_summary_path, summary)
    with pytest.raises(RuntimeError, match="next-consecutive"):
        consecutive.build_paused_consecutive_after_provisional_protocol(tmp_path, spec)

    spec = _fixture(tmp_path)
    for relative in (spec.continuation_manifest_path, spec.continuation_summary_path):
        path = tmp_path / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        value["iterations"][-1]["global_original_operator_residual"] = 1.0e-4
        _write_json(tmp_path, relative, value)
    with pytest.raises(RuntimeError, match="threshold"):
        consecutive.build_paused_consecutive_after_provisional_protocol(tmp_path, spec)


def test_builder_rejects_artifact_drift_and_wrong_authority(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    _write(tmp_path, spec.provisional_artifact_path, b"drifted artifact")
    with pytest.raises(RuntimeError, match="summary authorization"):
        consecutive.build_paused_consecutive_after_provisional_protocol(tmp_path, spec)

    spec = _fixture(tmp_path)
    path = tmp_path / spec.provisional_summary_path
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["decision"]["provisional_feedback_is_acceptance_authority"] = True
    _write_json(tmp_path, spec.provisional_summary_path, summary)
    with pytest.raises(RuntimeError, match="summary authorization"):
        consecutive.build_paused_consecutive_after_provisional_protocol(tmp_path, spec)


def test_builder_rejects_dat_in_inherited_source_without_hashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _fixture(tmp_path)
    path = tmp_path / spec.continuation_protocol_path
    protocol = json.loads(path.read_text(encoding="utf-8"))
    protocol["sources"]["forbidden"] = {
        "path": "outputs/checkpoints/forbidden.dat",
        "size_bytes": 12,
        "sha256": "d" * 64,
    }
    _write_json(tmp_path, spec.continuation_protocol_path, protocol)
    _rewrite_dp_hash(tmp_path, spec)
    original_sha = common.sha256

    def guarded_sha(path: Path) -> str:
        assert path.suffix.lower() != ".dat"
        return original_sha(path)

    monkeypatch.setattr(common, "sha256", guarded_sha)
    with pytest.raises(RuntimeError, match=r"refuses any \.dat source"):
        consecutive.build_paused_consecutive_after_provisional_protocol(tmp_path, spec)


def test_protocol_is_consumed_by_existing_runner_with_one_claim_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _fixture(tmp_path)
    protocol = consecutive.build_paused_consecutive_after_provisional_protocol(
        tmp_path, spec
    )
    protocol_path = tmp_path / "outputs/dr_protocol.json"
    consecutive._write_json_atomic(protocol_path, protocol)
    digest = common.sha256(protocol_path)
    _write(tmp_path, "outputs/checkpoints/previous.dat", PREVIOUS_BYTES)
    _write(tmp_path, "outputs/checkpoints/current.dat", CURRENT_BYTES)

    seen: list[tuple[str, str]] = []

    def fake_dp_run(
        root: Path,
        _protocol_path: Path,
        _expected_hash: str,
        *,
        stop_after_iteration: int,
    ) -> dict[str, object]:
        manifest_path = root / spec.continuation_manifest_path
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        seen.append((manifest["current_input_path"], manifest["next_output_path"]))
        previous = manifest["iterations"][-1]
        manifest["iterations"].append(
            {
                "iteration": int(previous["iteration"]) + 1,
                "input_state_path": manifest["current_input_path"],
                "input_state_sha256": manifest["current_input_sha256"],
                "mapped_state_path": manifest["next_output_path"],
                "mapped_state_sha256": "9" * 64,
                "global_original_operator_residual": 9.0e-5,
                "boundary_spectrum_l1": 8.0e-4,
                "boundary_bolometric_fraction": 7.0e-4,
                "map_passed": True,
            }
        )
        assert len(manifest["iterations"]) - 1 == stop_after_iteration
        manifest["status"] = "provisional_pause"
        _write_json(root, spec.continuation_manifest_path, manifest)
        return {"status": "provisional_pause"}

    monkeypatch.setattr(consecutive, "ROOT", tmp_path)
    monkeypatch.setattr(consecutive.dp, "run_continuation", fake_dp_run)
    summary = consecutive.run_one_fresh_map(protocol_path, digest)
    assert seen == [
        (
            "outputs/checkpoints/current.dat",
            "outputs/checkpoints/previous.dat",
        )
    ]
    assert summary["decision"]["two_consecutive_fixed_matter_states_converged"] is True
    assert summary["decision"]["formal_h_he_feedback_pair_authorized"] is True


def test_cli_atomically_writes_claim_only_protocol(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    argv = [
        "--phase", spec.phase,
        "--phase-index", str(spec.phase_index),
        "--classification", spec.classification,
        "--continuation-protocol", spec.continuation_protocol_path,
        "--continuation-manifest", spec.continuation_manifest_path,
        "--continuation-summary", spec.continuation_summary_path,
        "--provisional-protocol", spec.provisional_protocol_path,
        "--provisional-manifest", spec.provisional_manifest_path,
        "--provisional-summary", spec.provisional_summary_path,
        "--provisional-artifact", spec.provisional_artifact_path,
        "--transition-receipt", spec.transition_receipt_path,
        "--summary", spec.summary_path,
        "--output", "outputs/dr_protocol.json",
    ]
    payload, digest = prereg.main(argv, root=tmp_path)
    output = tmp_path / "outputs/dr_protocol.json"
    assert digest == common.sha256(output)
    assert json.loads(output.read_text(encoding="utf-8")) == payload
    assert not output.with_name(f"{output.name}.tmp").exists()
