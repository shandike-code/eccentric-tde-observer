"""Formal feedback-pair protocol and pure diagnostic regression tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from eccentric_tde_observer.formal_feedback_pair import (
    encoded_residual_norms,
    trial_feedback_pair_diagnostics,
    trial_feedback_pair_gate_checks,
    weighted_volume_l1,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/phase7b9_formal_feedback_pair_adapter.py"
SPEC = importlib.util.spec_from_file_location("phase7b9_feedback_pair_adapter", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not import formal feedback-pair adapter")
adapter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = adapter
SPEC.loader.exec_module(adapter)


def _write(root: Path, relative: str, content: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


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


def _fixture(root: Path) -> adapter.FormalFeedbackPairProtocolSpec:
    paths = {
        "previous": "outputs/checkpoints/previous.dat",
        "final": "outputs/checkpoints/final.dat",
        "trial": "outputs/trial.npz",
        "base": "outputs/base.npy",
        "old": "outputs/old.npz",
        "worker_protocol": "outputs/worker_protocol.json",
        "worker_runner": "scripts/worker.py",
        "adapter_runner": "scripts/adapter.py",
    }
    for name, path in paths.items():
        _write(root, path, f"small-{name}".encode())
    acceptance_path = "outputs/acceptance.json"
    _write_json(root, acceptance_path, _acceptance())
    confirmation_protocol_path = "outputs/confirmation_protocol.json"
    confirmation_protocol = {
        "configuration": {
            "previous_converged_state_path": paths["previous"],
            "previous_converged_state_sha256": adapter.sha256(root / paths["previous"]),
            "previous_global_original_operator_residual": 9.8e-5,
            "previous_boundary_spectrum_l1": 2.0e-6,
            "previous_boundary_bolometric_fraction": 8.0e-7,
            "input_state_path": paths["final"],
            "input_state_sha256": adapter.sha256(root / paths["final"]),
        }
    }
    _write_json(root, confirmation_protocol_path, confirmation_protocol)
    confirmation_summary_path = "outputs/confirmation_summary.json"
    _write_json(
        root,
        confirmation_summary_path,
        {
            "protocol_sha256": adapter.sha256(root / confirmation_protocol_path),
            "previous_converged_state_path": paths["previous"],
            "previous_converged_state_sha256": adapter.sha256(root / paths["previous"]),
            "input_state_path": paths["final"],
            "input_state_sha256": adapter.sha256(root / paths["final"]),
            "input_global_original_operator_residual": 9.7e-5,
            "input_boundary_spectrum_l1": 1.9e-6,
            "input_boundary_bolometric_fraction": 7.5e-7,
            "gate_checks": {"a": True, "b": True},
            "decision": {
                "two_consecutive_fixed_matter_states_converged": True,
                "formal_h_he_feedback_pair_authorized": True,
                "material_feedback_evaluated": False,
                "dynamic_nlte_solution_accepted": False,
            },
        },
    )
    trial_summary_path = "outputs/trial_summary.json"
    _write_json(
        root,
        trial_summary_path,
        {
            "trial_material_path": paths["trial"],
            "trial_material_sha256": adapter.sha256(root / paths["trial"]),
            "decision": {
                "phase7b9i_material_gate_passed": True,
                "accepted_as_nonlinear_step": False,
            },
        },
    )
    base_summary_path = "outputs/base_summary.json"
    _write_json(
        root,
        base_summary_path,
        {
            "encoded_residual_path": paths["base"],
            "encoded_residual_sha256": adapter.sha256(root / paths["base"]),
            "decision": {"phase7b9f_gate_passed": True},
        },
    )
    return adapter.FormalFeedbackPairProtocolSpec(
        phase="7B9 test formal feedback pair",
        phase_index=1418,
        classification="[A-preregistered]+[V]+[O]",
        confirmation_summary_path=confirmation_summary_path,
        confirmation_protocol_path=confirmation_protocol_path,
        trial_residual_acceptance_path=acceptance_path,
        trial_material_summary_path=trial_summary_path,
        trial_material_path=paths["trial"],
        base_feedback_summary_path=base_summary_path,
        base_residual_path=paths["base"],
        physical_old_time_level_path=paths["old"],
        phase7b7j_protocol_path=paths["worker_protocol"],
        phase7b7j_runner_path=paths["worker_runner"],
        adapter_runner_path=paths["adapter_runner"],
        feedback_work_directory="outputs/checkpoints/pair",
        previous_feedback_output="outputs/previous_feedback.npz",
        final_feedback_output="outputs/final_feedback.npz",
        target_material_output="outputs/target.npz",
        encoded_residual_output="outputs/residual.npy",
        summary_path="outputs/summary.json",
        figure_path="outputs/figure.png",
    )


def test_feedback_pair_builder_uses_the_two_residual_audited_states(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    protocol = adapter.build_formal_feedback_pair_protocol(tmp_path, spec)
    assert protocol["sources"]["previous_radiation"]["path"].endswith("previous.dat")
    assert protocol["sources"]["final_radiation"]["path"].endswith("final.dat")
    assert protocol["configuration"]["previous_global_original_operator_residual"] == 9.8e-5
    assert protocol["configuration"]["final_global_original_operator_residual"] == 9.7e-5
    assert protocol["acceptance_gates"] == _acceptance()["gates"]
    assert protocol["formal_state_gates"] == adapter._formal_state_gates()
    assert not protocol["authorization"]["material_update_during_feedback_pair"]
    assert not protocol["authorization"]["accept_dynamic_nlte_solution"]


def test_adapter_thresholds_match_phase7b9f_and_phase7b9bu() -> None:
    phase7b9f = json.loads(
        (ROOT / "outputs/phase7b9f_preregistered_converged_feedback_residual.json").read_text()
    )
    phase7b9bu = json.loads(
        (ROOT / "outputs/phase7b9bu_preregistered_trial_residual_acceptance.json").read_text()
    )
    for name, value in adapter._formal_state_gates().items():
        assert phase7b9f["gates"][name] == value
    adapter._require_exact_acceptance_gates(phase7b9bu)
    assert phase7b9bu["gates"] == _acceptance()["gates"]


@pytest.mark.parametrize("failure", ("threshold", "hash", "authorization"))
def test_feedback_pair_builder_rejects_broken_lineage(tmp_path: Path, failure: str) -> None:
    spec = _fixture(tmp_path)
    if failure == "threshold":
        summary = json.loads((tmp_path / spec.confirmation_summary_path).read_text())
        summary["input_global_original_operator_residual"] = 1.0e-4
        _write_json(tmp_path, spec.confirmation_summary_path, summary)
    elif failure == "hash":
        _write(tmp_path, "outputs/checkpoints/final.dat", b"changed")
    else:
        acceptance = json.loads((tmp_path / spec.trial_residual_acceptance_path).read_text())
        acceptance["authorization"]["accept_dynamic_nlte_solution"] = True
        _write_json(tmp_path, spec.trial_residual_acceptance_path, acceptance)
    with pytest.raises(RuntimeError):
        adapter.build_formal_feedback_pair_protocol(tmp_path, spec)


def test_worker_adapter_replaces_both_radiation_and_material() -> None:
    pair = {
        "sources": {
            "previous_radiation": {"path": "previous.dat", "sha256": "p"},
            "final_radiation": {"path": "final.dat", "sha256": "f"},
            "trial_material": {"path": "trial.npz", "sha256": "t"},
            "physical_old_time_level": {"path": "old.npz", "sha256": "o"},
        },
        "configuration": {
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "rate_quadrature_order_per_group": 16,
            "maximum_concurrent_processes": 2,
        },
    }
    template = {
        "sources": {
            "mapped_radiation_state": {"path": "old-radiation"},
            "second_material_iterate": {"path": "old-material"},
            "physical_old_time_level": {"path": "old-time"},
        },
        "configuration": {"material_update": True, "radiation_update": True},
    }
    adapted = adapter.adapt_phase7b7j_worker_protocol(pair, template, "final")
    assert adapted["sources"]["mapped_radiation_state"]["path"] == "final.dat"
    assert adapted["sources"]["second_material_iterate"]["path"] == "trial.npz"
    assert adapted["sources"]["physical_old_time_level"]["path"] == "old.npz"
    assert not adapted["configuration"]["material_update"]
    assert not adapted["configuration"]["radiation_update"]
    assert template["sources"]["mapped_radiation_state"]["path"] == "old-radiation"


def test_frozen_trial_gate_validates_exact_decode_not_noninvertible_reencode() -> None:
    codec = adapter.GroundStateLogSimplexCodec(2)
    frozen = np.array(
        [40.0, 16.633786872604382, -2.0, -1.7,
         41.0, 15.529368375956215, -1.2, -2.4],
        dtype=np.float64,
    )
    state = codec.decode(frozen)
    reencoded = np.asarray(
        codec.encode(
            state.temperature_k,
            state.hydrogen_fraction,
            state.helium_fraction,
        )
    )
    assert not np.array_equal(reencoded, frozen)
    validated = adapter._validated_frozen_trial_encoding(
        codec,
        state.temperature_k,
        state.hydrogen_fraction,
        state.helium_fraction,
        frozen,
    )
    assert np.array_equal(validated, frozen)


def test_frozen_trial_gate_rejects_changed_decoded_physical_array() -> None:
    codec = adapter.GroundStateLogSimplexCodec(1)
    frozen = np.array([40.0, 8.0, -2.0, -1.0], dtype=np.float64)
    state = codec.decode(frozen)
    changed_temperature = np.array(state.temperature_k, copy=True)
    changed_temperature[0] = np.nextafter(changed_temperature[0], np.inf)
    with pytest.raises(RuntimeError, match="decoded state changed"):
        adapter._validated_frozen_trial_encoding(
            codec,
            changed_temperature,
            state.hydrogen_fraction,
            state.helium_fraction,
            frozen,
        )


def test_reused_feedback_manifest_requires_exact_origin_state_and_artifact(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "outputs/previous_feedback.npz"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"feedback")
    manifest = tmp_path / "outputs/previous_manifest.json"
    origin = "a" * 64
    state_sha = "b" * 64
    artifact_sha = adapter.sha256(artifact)
    _write_json(
        tmp_path,
        "outputs/previous_manifest.json",
        {
            "protocol_sha256": origin,
            "status": "complete",
            "state_gate_passed": True,
            "state_path": "outputs/previous.dat",
            "state_sha256": state_sha,
            "feedback_artifact_path": "outputs/previous_feedback.npz",
            "feedback_artifact_sha256": artifact_sha,
        },
    )
    protocol = {
        "sources": {
            "previous_feedback_manifest": {"path": "outputs/previous_manifest.json"},
            "previous_feedback_artifact": {
                "path": "outputs/previous_feedback.npz",
                "sha256": artifact_sha,
            },
            "previous_radiation": {
                "path": "outputs/previous.dat",
                "sha256": state_sha,
            },
        },
        "configuration": {
            "reuse_completed_feedback_manifests": True,
            "feedback_origin_protocol_sha256": origin,
        },
        "authorization": {"reuse_only_after_bytewise_reproduction_audit": True},
    }
    loaded = adapter._load_reused_feedback_manifest(
        protocol, "previous", root=tmp_path
    )
    assert loaded["feedback_artifact_sha256"] == artifact_sha
    protocol["sources"]["previous_radiation"]["sha256"] = "c" * 64
    with pytest.raises(RuntimeError, match="lineage changed"):
        adapter._load_reused_feedback_manifest(
            protocol, "previous", root=tmp_path
        )


def test_feedback_stability_remains_available_without_material_residual() -> None:
    width = np.array([1.0, 2.0])
    previous = {
        "subcell_width_cm": width,
        "photoionization_s1": np.ones((2, 3)),
        "total_recombination_cm3_s": np.ones((2, 3)) * 2.0,
        "atomic_rate_heating_erg_s_cm3": np.array([3.0, 4.0]),
        "source_direct_heating_erg_s_cm3": np.array([3.0, 4.0]),
        "source_formal_heating_erg_s_cm3": np.array([3.0, 4.0]),
    }
    final = {
        name: (value if name == "subcell_width_cm" else value * (1.0 + 1.0e-5))
        for name, value in previous.items()
    }
    comparison = adapter._feedback_stability_comparison(previous, final)
    checks = adapter._feedback_stability_gate_checks(comparison, _acceptance()["gates"])
    assert all(checks.values())
    assert max(comparison["photoionization_volume_l1"]) < 1.0e-3


def test_pure_feedback_metrics_preserve_frozen_acceptance_rules() -> None:
    width = np.array([1.0, 2.0])
    mass = np.array([2.0, 1.0])
    previous = {
        "photoionization_s1": np.ones((2, 3)),
        "total_recombination_cm3_s": np.ones((2, 3)) * 2.0,
        "atomic_rate_heating_erg_s_cm3": np.array([3.0, 4.0]),
        "source_direct_heating_erg_s_cm3": np.array([3.0, 4.0]),
        "source_formal_heating_erg_s_cm3": np.array([3.0, 4.0]),
    }
    final = {name: value * (1.0 + 1.0e-5) for name, value in previous.items()}
    base_residual = np.ones(8)
    previous_residual = np.ones(8) * 0.51
    final_residual = np.ones(8) * 0.5
    diagnostics = trial_feedback_pair_diagnostics(
        previous_feedback=previous,
        final_feedback=final,
        previous_encoded_residual=previous_residual,
        final_encoded_residual=final_residual,
        base_encoded_residual=base_residual,
        cell_width=width,
        cell_mass=mass,
    )
    gates = _acceptance()["gates"]
    checks = trial_feedback_pair_gate_checks(diagnostics, gates)
    assert all(checks.values())
    assert diagnostics.candidate_norms.l2 < diagnostics.base_norms.l2
    assert encoded_residual_norms(final_residual, mass).maximum_cell == 1.0
    assert np.all(weighted_volume_l1(np.zeros((2, 3)), np.zeros((2, 3)), width) == 0.0)


def test_pure_feedback_metrics_reject_nonphysical_inputs() -> None:
    with pytest.raises(ValueError):
        encoded_residual_norms(np.zeros((2, 4)), np.array([1.0, 0.0]))
    with pytest.raises(ValueError):
        weighted_volume_l1(np.zeros(2), np.zeros(2), np.array([1.0, -1.0]))
