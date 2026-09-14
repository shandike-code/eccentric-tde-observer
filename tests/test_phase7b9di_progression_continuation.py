"""Phase 7B9di progression/convergence separation on tiny files only."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts import phase7b9di_progression_continuation as continuation


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _source(path: Path, relative: str) -> dict[str, object]:
    data = (path / relative).read_bytes()
    return {"path": relative, "size_bytes": len(data), "sha256": _sha(data)}


def _fixture(root: Path) -> continuation.ProgressionContinuationSpec:
    runner = continuation.RUNNER_RELATIVE_PATH
    _write(root / runner, b"independent progression runner\n")
    _write(root / "outputs/fixed_material.npz", b"material")
    fixed = {
        "sources": {
            "current_material_state": _source(root, "outputs/fixed_material.npz")
        }
    }
    _write(root / "outputs/fixed_worker.json", fixed)
    gates = {
        "block_count_exactly": 76,
        "owned_frequency_group_count_exactly": 9632,
        "minimum_input_and_mapped_intensity_at_least": 0.0,
        "initial_audit_absolute_tolerance": 2.0e-12,
        "global_original_operator_residual_below": 1.0e-4,
        "subsequent_residual_contraction_ratio_below": 1.01,
        "global_boundary_spectrum_l1_below": 1.0e-3,
        "global_boundary_bolometric_fraction_below": 1.0e-3,
        "each_process_peak_rss_strictly_below_mib": 6144.0,
        "each_worker_wall_time_strictly_below_s": 60.0,
        "each_full_map_wall_time_strictly_below_s": 1800.0,
    }
    a = b"AAAA"
    old_b = b"BBBB"
    mapped_b = b"CCCC"
    a_path = "outputs/checkpoints/a.dat"
    b_path = "outputs/checkpoints/b.dat"
    _write(root / a_path, a)
    # 模拟 dh map0 已覆盖 B；builder 不应要求旧的 pre-map B 仍存在。
    _write(root / b_path, mapped_b)
    dh = {
        "phase": "dh",
        "sources": {
            "finite_trial_protocol": _source(root, "outputs/fixed_worker.json"),
            "finite_trial_material": _source(root, "outputs/fixed_material.npz"),
        },
        "configuration": {
            "phase_index": 1,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "raw_float64_checkpoint_size_bytes": 4,
            "material_candidate_absolute_relaxation": 0.0625,
            "maximum_picard_maps": 24,
            "maximum_concurrent_processes": 2,
            "initial_state_path": a_path,
            "initial_state_sha256": _sha(a),
            "scratch_state_path": b_path,
            "scratch_state_initial_sha256": _sha(old_b),
            "report_directory": "outputs/checkpoints/dh_transient_reports",
            "manifest_path": "outputs/checkpoints/dh/manifest.json",
            "summary_path": "outputs/dh_summary.json",
            "figure_path": "outputs/dh.png",
            "runner_path": "scripts/frozen_dh.py",
        },
        "reference": {"initial_global_residual": None},
        "gates": gates,
    }
    dh_path = "outputs/dh_protocol.json"
    _write(root / dh_path, dh)
    dh_hash = _sha((root / dh_path).read_bytes())
    record = {
        "iteration": 0,
        "input_state_path": a_path,
        "input_state_sha256": _sha(a),
        "mapped_state_path": b_path,
        "mapped_state_sha256": _sha(mapped_b),
        "frequency_ownership_count": 9632,
        "frequency_ownership_exact": True,
        "global_original_operator_residual": 0.0057,
        "boundary_spectrum_l1": 0.003,
        "boundary_bolometric_fraction": 0.0018,
        "minimum_input_intensity": 0.0,
        "minimum_mapped_intensity": 0.0,
        "maximum_process_peak_rss_mib": 2888.0,
        "maximum_worker_wall_runtime_s": 12.0,
        "contraction_ratio": None,
        "full_map_wall_runtime_s": 327.0,
        "initial_reproduction_applicable": False,
        "gate_checks": {
            "frequency_ownership_pass": True,
            "positive_map_pass": True,
            "initial_reproduction_pass": True,
            "contraction_pass": True,
            "boundary_pass": False,
            "resources_pass": True,
        },
        "map_passed": False,
    }
    manifest_path = "outputs/checkpoints/dh/manifest.json"
    summary_path = "outputs/dh_summary.json"
    receipt_path = "outputs/checkpoints/dh/receipt.json"
    _write(
        root / manifest_path,
        {
            "phase": "dh",
            "protocol_sha256": dh_hash,
            "status": "gate_failed",
            "iterations": [record],
        },
    )
    _write(
        root / summary_path,
        {
            "phase": "dh",
            "protocol_sha256": dh_hash,
            "status": "gate_failed",
            "iterations": [record],
        },
    )
    _write(
        root / receipt_path,
        {
            "protocol_sha256": dh_hash,
            "status": "complete",
            "buffer_a_path": a_path,
            "buffer_a_postcopy_sha256": _sha(a),
            "buffer_b_path": b_path,
            "buffer_b_unchanged_sha256": _sha(old_b),
            "protected_source_modified": False,
        },
    )
    return continuation.ProgressionContinuationSpec(
        phase="di",
        phase_index=2,
        classification="[A-preregistered]+[V]+[O]",
        dh_protocol_path=dh_path,
        dh_manifest_path=manifest_path,
        dh_summary_path=summary_path,
        dh_initialization_receipt_path=receipt_path,
        runner_path=runner,
        manifest_path="outputs/checkpoints/di/manifest.json",
        transient_report_directory="outputs/checkpoints/di_transient_reports",
        summary_path="outputs/di_summary.json",
        figure_path="outputs/di.png",
    )


def test_boundary_only_failed_seed_is_progression_eligible(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    protocol = continuation.build_progression_continuation_protocol(tmp_path, spec)
    seed = protocol["seed_iteration"]
    assert seed["map_passed"] is False
    assert seed["original_map_passed"] is False
    assert seed["gate_checks"]["boundary_pass"] is False
    assert seed["progression_passed"] is True
    assert seed["convergence_passed"] is False
    assert seed["progression_classification"] == (
        "bootstrap_nonconverged/progression_eligible"
    )


@pytest.mark.parametrize(
    "failed_gate",
    [
        "frequency_ownership_pass",
        "positive_map_pass",
        "initial_reproduction_pass",
        "contraction_pass",
        "resources_pass",
    ],
)
def test_any_nonboundary_seed_gate_failure_is_rejected(
    tmp_path: Path, failed_gate: str
) -> None:
    spec = _fixture(tmp_path)
    manifest_path = tmp_path / spec.dh_manifest_path
    summary_path = tmp_path / spec.dh_summary_path
    manifest = json.loads(manifest_path.read_text())
    manifest["iterations"][0]["gate_checks"][failed_gate] = False
    _write(manifest_path, manifest)
    summary = json.loads(summary_path.read_text())
    summary["iterations"] = manifest["iterations"]
    _write(summary_path, summary)
    with pytest.raises(RuntimeError, match="boundary-only"):
        continuation.build_progression_continuation_protocol(tmp_path, spec)


def test_runtime_seeds_from_changed_b_to_untouched_a_without_recopy(
    tmp_path: Path,
) -> None:
    spec = _fixture(tmp_path)
    protocol_path = tmp_path / "outputs/di_protocol.json"
    protocol, digest = continuation.write_protocol(tmp_path, spec, protocol_path)
    a_path = tmp_path / protocol["configuration"]["scratch_state_path"]
    b_path = tmp_path / protocol["configuration"]["initial_state_path"]
    a_before = a_path.read_bytes()
    b_before = b_path.read_bytes()
    manifest = continuation.initialize_progression_manifest(
        tmp_path, protocol_path, digest
    )
    assert manifest["current_input_path"].endswith("b.dat")
    assert manifest["next_output_path"].endswith("a.dat")
    assert manifest["iterations"][0]["progression_passed"] is True
    assert a_path.read_bytes() == a_before
    assert b_path.read_bytes() == b_before


def test_recovery_accepts_committed_ping_pong_hashes(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    protocol_path = tmp_path / "outputs/di_protocol.json"
    protocol, digest = continuation.write_protocol(tmp_path, spec, protocol_path)
    manifest = continuation.initialize_progression_manifest(
        tmp_path, protocol_path, digest
    )
    a_path = tmp_path / protocol["configuration"]["scratch_state_path"]
    b_path = tmp_path / protocol["configuration"]["initial_state_path"]
    new_a = b"DDDD"
    a_path.write_bytes(new_a)
    # 模拟一次 B->A 已完整 commit 后的 ping-pong 交换。
    manifest.update(
        {
            "current_input_path": protocol["configuration"]["scratch_state_path"],
            "current_input_sha256": _sha(new_a),
            "next_output_path": protocol["configuration"]["initial_state_path"],
            "next_output_sha256": _sha(b_path.read_bytes()),
            "active_iteration": None,
        }
    )
    _write(tmp_path / spec.manifest_path, manifest)
    resumed = continuation.initialize_progression_manifest(
        tmp_path, protocol_path, digest
    )
    assert resumed["current_input_sha256"] == _sha(new_a)


def test_progression_and_convergence_gates_are_independent(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    protocol = continuation.build_progression_continuation_protocol(tmp_path, spec)
    gates = protocol["gates"]
    metrics = {
        "block_report_count": 76,
        "frequency_ownership_count": 9632,
        "frequency_ownership_exact": True,
        "minimum_input_intensity": 0.0,
        "minimum_mapped_intensity": 0.0,
        "maximum_process_peak_rss_mib": 3000.0,
        "maximum_worker_wall_runtime_s": 15.0,
        "full_map_wall_runtime_s": 350.0,
        "global_original_operator_residual": 5.0e-3,
        "boundary_spectrum_l1": 3.0e-3,
        "boundary_bolometric_fraction": 2.0e-3,
    }
    assert all(continuation._progression_checks(gates, metrics, 0.9).values())
    assert not all(continuation._convergence_checks(gates, metrics).values())
    metrics["maximum_process_peak_rss_mib"] = 7000.0
    assert continuation._progression_checks(gates, metrics, 0.9)[
        "resources_pass"
    ] is False


def test_science_resource_horizon_and_storage_gates_are_unchanged(
    tmp_path: Path,
) -> None:
    spec = _fixture(tmp_path)
    dh = json.loads((tmp_path / spec.dh_protocol_path).read_text())
    protocol = continuation.build_progression_continuation_protocol(tmp_path, spec)
    assert protocol["gates"] == dh["gates"]
    assert protocol["configuration"]["maximum_picard_maps"] == 24
    assert protocol["configuration"]["maximum_concurrent_processes"] == 2
    assert protocol["gates"]["each_full_map_wall_time_strictly_below_s"] == 1800.0
    assert protocol["storage_plan"]["additional_full_state_allocation_count"] == 0
    assert protocol["authorization"]["recopy_protected_initial_source"] is False


def test_builder_rejects_wrong_runner_without_touching_full_states(
    tmp_path: Path,
) -> None:
    spec = replace(_fixture(tmp_path), runner_path="scripts/wrong.py")
    with pytest.raises(RuntimeError, match="runner path"):
        continuation.build_progression_continuation_protocol(tmp_path, spec)


def test_runner_contains_no_recopy_or_numerical_repair() -> None:
    source = Path(continuation.__file__).read_text(encoding="utf-8")
    forbidden = (
        "shutil.copyfile(",
        "np.clip(",
        "nan_to_num(",
        "renormalize(",
    )
    assert all(token not in source for token in forbidden)
