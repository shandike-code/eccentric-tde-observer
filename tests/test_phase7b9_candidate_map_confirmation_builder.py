"""Candidate-map consecutive-confirmation builder small-file tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/phase7b9_candidate_map_confirmation_builder.py"
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("candidate_map_confirmation_builder", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not import candidate-map confirmation builder")
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)
common = builder.common


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
        },
        "authorization": {
            "accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass": True,
            "accept_dynamic_nlte_solution": False,
        },
    }


def _fixture(root: Path) -> builder.CandidateMapConsecutiveConfirmationSpec:
    for index, relative in enumerate(
        (
            common.FINITE_TRIAL_PROTOCOL,
            common.FINITE_TRIAL_MATERIAL,
            common.MASTER_INPUT,
            common.GENERIC_MAP_RUNNER,
            common.MAP_WORKER,
            common.WORKER_HELPERS,
            common.MIXED_FRAME_OPERATOR,
            common.MIXED_FRAME_FREQUENCY,
        )
    ):
        _write(root, relative, f"source-{index}".encode())
    previous = "outputs/checkpoints/candidate_input.dat"
    mapped = "outputs/checkpoints/candidate_output.dat"
    scratch = "outputs/checkpoints/confirmation_output.dat"
    _write(root, previous, b"previous")
    _write(root, mapped, b"mapped00")
    _write(root, scratch, b"scratch0")
    candidate_protocol_path = "outputs/candidate_protocol.json"
    candidate_protocol = {
        "configuration": {
            "input_state_path": previous,
            "input_state_sha256": common.sha256(root / previous),
            "output_state_path": mapped,
            "accepted_source_relaxation_exactly": 1.0,
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            **common.numerical_repair_prohibitions(sequence=False),
        },
        "gates": {
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "full_map_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "commit_recoverable_mapped_state_if_all_map_gates_pass": True,
            "second_consecutive_original_residual_required_if_below_target": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    _write_json(root, candidate_protocol_path, candidate_protocol)
    candidate_summary_path = "outputs/candidate_summary.json"
    _write_json(
        root,
        candidate_summary_path,
        {
            "protocol_sha256": common.sha256(root / candidate_protocol_path),
            "input_state_path": previous,
            "input_state_sha256": common.sha256(root / previous),
            "output_state_path": mapped,
            "output_state_sha256": common.sha256(root / mapped),
            "input_global_original_operator_residual": 9.8e-5,
            "input_boundary_spectrum_l1": 2.0e-6,
            "input_boundary_bolometric_fraction": 8.0e-7,
            "maximum_process_peak_rss_mib": 3000.0,
            "wall_runtime_s": 200.0,
            "gate_checks": {
                "frequency_ownership_pass": True,
                "positive_map_pass": True,
                "input_residual_reproduction_pass": True,
                "input_boundary_reproduction_pass": True,
                "worker_resources_pass": True,
            },
            "decision": {
                "global_positive_picard_map_passed": True,
                "mapped_state_committed_as_diagnostic_candidate": True,
                "mapped_state_self_guard_residual_audit_authorized": True,
                "material_feedback_authorized": False,
            },
        },
    )
    acceptance_path = "outputs/acceptance.json"
    _write_json(root, acceptance_path, _acceptance())
    return builder.CandidateMapConsecutiveConfirmationSpec(
        phase="7B9 candidate-map consecutive confirmation test",
        phase_index=1501,
        classification="[A-preregistered]+[V]+[O]",
        candidate_map_summary_path=candidate_summary_path,
        candidate_map_protocol_path=candidate_protocol_path,
        trial_residual_acceptance_path=acceptance_path,
        output_state_path=scratch,
        manifest_path="outputs/checkpoints/confirm/manifest.json",
        report_directory="outputs/checkpoints/confirm/reports",
        summary_path="outputs/confirm_summary.json",
        figure_path="outputs/confirm.png",
        block_report_prefix="confirm",
        runner_path="scripts/phase7b9bv_consecutive_picard_confirmation.py",
    )


def test_candidate_map_builder_is_bv_runner_compatible(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    protocol = builder.build_candidate_map_consecutive_confirmation_protocol(
        tmp_path, spec
    )
    cfg = protocol["configuration"]
    assert cfg["previous_converged_state_path"].endswith("candidate_input.dat")
    assert cfg["input_state_path"].endswith("candidate_output.dat")
    assert cfg["output_state_path"].endswith("confirmation_output.dat")
    assert cfg["previous_global_original_operator_residual"] == 9.8e-5
    assert cfg["maximum_concurrent_processes"] == 2
    assert protocol["gates"] == common.consecutive_confirmation_gates()
    assert protocol["gates"]["both_global_original_operator_residuals_below"] == 1.0e-4
    assert protocol["gates"]["both_boundary_spectrum_l1_below"] == 1.0e-3
    assert protocol["authorization"][
        "assemble_formal_h_he_feedback_pair_only_if_all_gates_pass"
    ]
    assert all(
        cfg[name] is False
        for name in (
            "cellwise_clipping",
            "nan_to_num",
            "intensity_floor",
            "point_deletion",
            "posthoc_renormalization",
            "matter_feedback_during_map",
        )
    )


@pytest.mark.parametrize(
    "failure",
    ("residual", "positive", "resource", "hash", "shared_output", "acceptance"),
)
def test_candidate_map_builder_rejects_failed_or_broken_inputs(
    tmp_path: Path, failure: str
) -> None:
    root = tmp_path / failure
    spec = _fixture(root)
    summary_path = root / spec.candidate_map_summary_path
    summary = json.loads(summary_path.read_text())
    if failure == "residual":
        summary["input_global_original_operator_residual"] = 1.0e-4
        _write_json(root, spec.candidate_map_summary_path, summary)
    elif failure == "positive":
        summary["gate_checks"]["positive_map_pass"] = False
        _write_json(root, spec.candidate_map_summary_path, summary)
    elif failure == "resource":
        summary["maximum_process_peak_rss_mib"] = 6144.0
        _write_json(root, spec.candidate_map_summary_path, summary)
    elif failure == "hash":
        _write(root, "outputs/checkpoints/candidate_output.dat", b"changed0")
    elif failure == "shared_output":
        spec = builder.CandidateMapConsecutiveConfirmationSpec(
            **{
                **spec.__dict__,
                "output_state_path": "outputs/checkpoints/candidate_output.dat",
            }
        )
    else:
        acceptance = json.loads((root / spec.trial_residual_acceptance_path).read_text())
        acceptance["gates"]["each_global_original_operator_residual_below"] = 2.0e-4
        _write_json(root, spec.trial_residual_acceptance_path, acceptance)
    with pytest.raises(RuntimeError):
        builder.build_candidate_map_consecutive_confirmation_protocol(root, spec)
