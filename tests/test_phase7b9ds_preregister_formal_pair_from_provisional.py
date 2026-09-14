"""7B9ds cached-previous/fresh-final formal-pair preregistration tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts import phase7b9_formal_feedback_pair_adapter as adapter
from scripts import phase7b9_formal_pair_from_provisional as pair
from scripts import phase7b9_protocol_builders as common
from scripts import phase7b9ds_formal_pair_adapter as claim_adapter
from scripts import phase7b9ds_preregister_formal_pair_from_provisional as prereg


FINAL_BYTES = b"final-state"


def _hash_bytes(payload: bytes) -> str:
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
        "sha256": adapter.sha256(path),
    }


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


def _fixture(root: Path) -> pair.PausedFormalPairFromProvisionalSpec:
    previous = "outputs/checkpoints/previous-overwritten.dat"
    final = "outputs/checkpoints/final.dat"
    previous_sha = "a" * 64
    final_sha = _hash_bytes(FINAL_BYTES)

    dr_helper = "scripts/dr_helper.py"
    _write(root, dr_helper, b"dr helper")
    dr_protocol_path = "outputs/dr_protocol.json"
    dr_protocol = {
        "sources": {"dr_helper": _source(root, dr_helper)},
        "full_state_claims": {
            "previous_audited_input": {
                "path": previous,
                "size_bytes": len(FINAL_BYTES),
                "sha256": previous_sha,
                "provisional_feedback_cached_before_overwrite": True,
            },
            "current_next_consecutive_input": {
                "path": final,
                "size_bytes": len(FINAL_BYTES),
                "sha256": final_sha,
            },
        },
        "configuration": {
            "maximum_concurrent_processes": 2,
            "natural_frequency_block_count": 76,
            "owned_frequency_group_count": 9632,
            "execute_exactly_one_fresh_map": True,
            "fresh_map_iteration": 7,
            "previous_audited_input_path": previous,
            "previous_audited_input_sha256": previous_sha,
            "current_input_path": final,
            "current_input_sha256": final_sha,
            "output_path": previous,
            **common.numerical_repair_prohibitions(sequence=True),
        },
        "gates": common.memory_safe_seeded_two_map_gates(),
        "authorization": {
            "execute_exactly_one_fresh_map": True,
            "material_feedback_during_confirmation": False,
            "formal_pair_authorized_before_fresh_map": False,
        },
    }
    _write_json(root, dr_protocol_path, dr_protocol)
    dr_sha = adapter.sha256(root / dr_protocol_path)
    dr_summary_path = "outputs/dr_summary.json"
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
        dr_summary_path,
        {
            "protocol_sha256": dr_sha,
            "status": "complete",
            "executed_fresh_map_count": 1,
            "fresh_map_iteration": 7,
            "previous_converged_state_path": previous,
            "previous_converged_state_sha256": previous_sha,
            "previous_state_bytes_retained": False,
            "previous_global_original_operator_residual": 8.0e-5,
            "previous_boundary_spectrum_l1": 7.0e-4,
            "previous_boundary_bolometric_fraction": 6.0e-4,
            "input_state_path": final,
            "input_state_sha256": final_sha,
            "input_global_original_operator_residual": 9.0e-5,
            "input_boundary_spectrum_l1": 8.0e-4,
            "input_boundary_bolometric_fraction": 7.0e-4,
            "output_state_path": previous,
            "output_state_sha256": "b" * 64,
            "gate_checks": checks,
            "decision": {
                "two_consecutive_fixed_matter_states_converged": True,
                "provisional_previous_feedback_valid_for_pair": True,
                "final_feedback_extraction_authorized": True,
                "formal_h_he_feedback_pair_authorized": True,
                "material_feedback_evaluated": False,
                "dynamic_nlte_solution_accepted": False,
            },
        },
    )

    material = "outputs/material.npz"
    material_protocol = "outputs/material_protocol.json"
    material_summary = "outputs/material_summary.json"
    physical_old = "outputs/old.npz"
    template = "outputs/phase7b7j_protocol.json"
    _write(root, material, b"material")
    _write(root, physical_old, b"old")
    _write_json(root, template, {})
    _write_json(
        root,
        material_protocol,
        {
            "sources": {},
            "configuration": {"candidate_absolute_relaxation": 0.0625},
        },
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
    artifact = "outputs/dq_feedback.npz"
    _write(root, artifact, b"cached previous feedback")
    artifact_sha = adapter.sha256(root / artifact)
    dq_helper = "scripts/dq_helper.py"
    _write(root, dq_helper, b"dq helper")
    dq_protocol_path = "outputs/dq_protocol.json"
    _write_json(
        root,
        dq_protocol_path,
        {
            "sources": {
                "dq_helper": _source(root, dq_helper),
                "trial_material_protocol": _source(root, material_protocol),
                "trial_material_summary": _source(root, material_summary),
                "trial_material": _source(root, material),
                "physical_old_time_level": _source(root, physical_old),
                "phase7b7j_protocol": _source(root, template),
            },
            "full_state_claims": {
                "previous_radiation": {
                    "path": previous,
                    "size_bytes": len(FINAL_BYTES),
                    "sha256": previous_sha,
                },
                "next_consecutive_radiation": {
                    "path": final,
                    "size_bytes": len(FINAL_BYTES),
                    "sha256": final_sha,
                },
            },
            "configuration": {
                "maximum_concurrent_processes": 2,
                "material_candidate_absolute_relaxation": 0.0625,
            },
            "formal_state_gates": adapter._formal_state_gates(),
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
    dq_sha = adapter.sha256(root / dq_protocol_path)
    dq_manifest_path = "outputs/dq_manifest.json"
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

    acceptance = "outputs/acceptance.json"
    _write_json(root, acceptance, _acceptance())
    base_residual = "outputs/base_residual.npy"
    base_summary = "outputs/base_summary.json"
    _write(root, base_residual, b"base residual")
    _write_json(
        root,
        base_summary,
        {
            "encoded_residual_path": base_residual,
            "encoded_residual_sha256": adapter.sha256(root / base_residual),
            "decision": {"phase7b9f_gate_passed": True},
        },
    )
    _write(root, pair.PAUSED_ADAPTER_RELATIVE_PATH, b"claim adapter")
    _write(root, pair.RUNNER_RELATIVE_PATH, b"pair runner")
    _write(root, pair.PAUSED_PREREGISTER_RELATIVE_PATH, b"preregister")
    return pair.PausedFormalPairFromProvisionalSpec(
        phase="7B9ds test",
        phase_index=1706,
        classification="[A-preregistered]+[V]+[O]",
        confirmation_protocol_path=dr_protocol_path,
        confirmation_summary_path=dr_summary_path,
        provisional_protocol_path=dq_protocol_path,
        provisional_summary_path=dq_summary_path,
        provisional_manifest_path=dq_manifest_path,
        provisional_artifact_path=artifact,
        trial_acceptance_path=acceptance,
        base_feedback_summary_path=base_summary,
        base_residual_path=base_residual,
        adapter_runner_path=pair.PAUSED_ADAPTER_RELATIVE_PATH,
        pair_runner_path=pair.RUNNER_RELATIVE_PATH,
        preregister_runner_path=pair.PAUSED_PREREGISTER_RELATIVE_PATH,
        feedback_work_directory="outputs/checkpoints/phase7b9ds_formal_pair",
        final_feedback_output="outputs/ds_final_feedback.npz",
        target_material_output="outputs/ds_target_material.npz",
        encoded_residual_output="outputs/ds_residual.npy",
        summary_path="outputs/ds_summary.json",
        figure_path="outputs/ds_summary.png",
    )


def _rewrite_dr_hash(root: Path, spec: pair.PausedFormalPairFromProvisionalSpec) -> None:
    value = json.loads((root / spec.confirmation_summary_path).read_text(encoding="utf-8"))
    value["protocol_sha256"] = adapter.sha256(root / spec.confirmation_protocol_path)
    _write_json(root, spec.confirmation_summary_path, value)


def test_builder_reuses_previous_and_claims_only_final(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _fixture(tmp_path)
    original_sha = adapter.sha256

    def guarded_sha(path: Path) -> str:
        assert path.suffix.lower() != ".dat"
        return original_sha(path)

    monkeypatch.setattr(adapter, "sha256", guarded_sha)
    protocol = pair.build_paused_formal_pair_from_provisional_protocol(tmp_path, spec)
    assert all(not source["path"].endswith(".dat") for source in protocol["sources"].values())
    assert set(protocol["full_state_claims"]) == {"final_radiation"}
    assert not (tmp_path / "outputs/checkpoints/final.dat").exists()
    assert claim_adapter._runtime_pair_protocol(protocol)["sources"]["final_radiation"] == protocol["full_state_claims"]["final_radiation"]
    assert protocol["configuration"]["maximum_concurrent_processes"] == 2
    assert protocol["formal_state_gates"] == adapter._formal_state_gates()
    assert protocol["authorization"]["evaluate_exactly_one_new_final_feedback_state"] is True
    assert protocol["authorization"]["material_update_during_pair"] is False
    assert "candidate_state_must_match_frozen_phase7b9i_bytes" not in protocol["acceptance_gates"]
    assert protocol["acceptance_gates"]["candidate_state_must_match_frozen_phase7b9de_bytes"] is True


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("previous_global_original_operator_residual", 1.0e-4),
        ("input_global_original_operator_residual", 1.0e-4),
        ("previous_boundary_spectrum_l1", 1.0e-3),
        ("input_boundary_bolometric_fraction", 1.0e-3),
    ],
)
def test_builder_rejects_two_state_threshold_equality(
    tmp_path: Path, key: str, value: float
) -> None:
    spec = _fixture(tmp_path)
    path = tmp_path / spec.confirmation_summary_path
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary[key] = value
    _write_json(tmp_path, spec.confirmation_summary_path, summary)
    with pytest.raises(RuntimeError, match="threshold"):
        pair.build_paused_formal_pair_from_provisional_protocol(tmp_path, spec)


def test_builder_rejects_nonconsecutive_lineage(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    path = tmp_path / spec.confirmation_summary_path
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["input_state_sha256"] = "f" * 64
    _write_json(tmp_path, spec.confirmation_summary_path, summary)
    with pytest.raises(RuntimeError, match="lineage"):
        pair.build_paused_formal_pair_from_provisional_protocol(tmp_path, spec)


def test_builder_rejects_artifact_drift_and_wrong_authority(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    _write(tmp_path, spec.provisional_artifact_path, b"artifact drift")
    with pytest.raises(RuntimeError, match="summary authorization"):
        pair.build_paused_formal_pair_from_provisional_protocol(tmp_path, spec)

    spec = _fixture(tmp_path)
    path = tmp_path / spec.confirmation_summary_path
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["decision"]["final_feedback_extraction_authorized"] = False
    _write_json(tmp_path, spec.confirmation_summary_path, summary)
    with pytest.raises(RuntimeError, match="passed 7B9dr fresh map"):
        pair.build_paused_formal_pair_from_provisional_protocol(tmp_path, spec)


def test_builder_rejects_source_collision_and_dat_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _fixture(tmp_path)
    collision = "scripts/collision.py"
    _write(tmp_path, collision, b"collision")
    path = tmp_path / spec.confirmation_protocol_path
    protocol = json.loads(path.read_text(encoding="utf-8"))
    protocol["sources"]["pair_runner"] = _source(tmp_path, collision)
    _write_json(tmp_path, spec.confirmation_protocol_path, protocol)
    _rewrite_dr_hash(tmp_path, spec)
    with pytest.raises(RuntimeError, match="source-key collision"):
        pair.build_paused_formal_pair_from_provisional_protocol(tmp_path, spec)

    spec = _fixture(tmp_path)
    path = tmp_path / spec.confirmation_protocol_path
    protocol = json.loads(path.read_text(encoding="utf-8"))
    protocol["sources"]["forbidden"] = {
        "path": "outputs/checkpoints/forbidden.dat",
        "size_bytes": 1,
        "sha256": "d" * 64,
    }
    _write_json(tmp_path, spec.confirmation_protocol_path, protocol)
    _rewrite_dr_hash(tmp_path, spec)
    original_sha = adapter.sha256

    def guarded_sha(path: Path) -> str:
        assert path.suffix.lower() != ".dat"
        return original_sha(path)

    monkeypatch.setattr(adapter, "sha256", guarded_sha)
    with pytest.raises(RuntimeError, match=r"refuses any \.dat source"):
        pair.build_paused_formal_pair_from_provisional_protocol(tmp_path, spec)


def test_existing_runner_consumes_claim_protocol_and_reuses_previous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _fixture(tmp_path)
    protocol = pair.build_paused_formal_pair_from_provisional_protocol(tmp_path, spec)
    protocol_path = tmp_path / "outputs/ds_protocol.json"
    pair._write_json_atomic(protocol_path, protocol)
    digest = adapter.sha256(protocol_path)
    _write(tmp_path, "outputs/checkpoints/final.dat", FINAL_BYTES)
    final_artifact = tmp_path / protocol["configuration"]["final_feedback_output"]
    final_artifact.write_bytes(b"final feedback")
    final_manifest = {
        "status": "complete",
        "state_gate_passed": True,
        "state_path": protocol["full_state_claims"]["final_radiation"]["path"],
        "state_sha256": protocol["full_state_claims"]["final_radiation"]["sha256"],
        "feedback_artifact_path": protocol["configuration"]["final_feedback_output"],
        "feedback_artifact_sha256": adapter.sha256(final_artifact),
    }
    monkeypatch.setattr(pair, "ROOT", tmp_path)
    monkeypatch.setattr(adapter, "ROOT", tmp_path)
    monkeypatch.setattr(adapter, "_validate_worker_template_sources", lambda _p: {})
    monkeypatch.setattr(adapter, "_run_feedback_state", lambda *_args: final_manifest)
    observed: dict[str, object] = {}

    def fake_pair(_path: Path, _hash: str) -> dict[str, object]:
        loaded = adapter.load_frozen_pair_protocol(_path, _hash, validate_sources=True)
        observed["previous"] = adapter._load_reused_feedback_manifest(loaded, "previous")
        observed["final"] = adapter._load_reused_feedback_manifest(loaded, "final")
        return {"status": "complete"}

    monkeypatch.setattr(adapter, "run_pair", fake_pair)
    result = pair.run_formal_pair(protocol_path, digest)
    assert result["status"] == "complete"
    assert observed["previous"]["feedback_artifact_path"] == spec.provisional_artifact_path
    assert observed["final"] == final_manifest


def test_cli_atomically_writes_protocol(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    argv = [
        "--phase", spec.phase,
        "--phase-index", str(spec.phase_index),
        "--classification", spec.classification,
        "--confirmation-protocol", spec.confirmation_protocol_path,
        "--confirmation-summary", spec.confirmation_summary_path,
        "--provisional-protocol", spec.provisional_protocol_path,
        "--provisional-summary", spec.provisional_summary_path,
        "--provisional-manifest", spec.provisional_manifest_path,
        "--provisional-artifact", spec.provisional_artifact_path,
        "--trial-acceptance", spec.trial_acceptance_path,
        "--base-feedback-summary", spec.base_feedback_summary_path,
        "--base-residual", spec.base_residual_path,
        "--feedback-work-directory", spec.feedback_work_directory,
        "--final-feedback-output", spec.final_feedback_output,
        "--target-material-output", spec.target_material_output,
        "--encoded-residual-output", spec.encoded_residual_output,
        "--summary", spec.summary_path,
        "--figure", spec.figure_path,
        "--output", "outputs/ds_protocol.json",
    ]
    payload, digest = prereg.main(argv, root=tmp_path)
    output = tmp_path / "outputs/ds_protocol.json"
    assert digest == adapter.sha256(output)
    assert json.loads(output.read_text(encoding="utf-8")) == payload
    assert not output.with_name(f"{output.name}.tmp").exists()
