"""Candidate commit/fresh-map recovery tests using only tiny tmp_path states."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts import phase7b9di_streaming_anderson_orchestrator as orchestrator
from scripts import phase7b9di_streaming_anderson_tail as streaming


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    return {"path": relative, "size_bytes": path.stat().st_size, "sha256": _sha(path)}


def _fixture(root: Path) -> tuple[Path, str, np.ndarray, np.ndarray, np.ndarray]:
    groups = 76
    x23 = 1.0 + np.arange(groups, dtype=np.float64) * 1.0e-3
    f0 = 0.02 + np.arange(groups, dtype=np.float64) * 1.0e-5
    x24 = x23 + f0
    x25 = x24 + 0.8 * f0
    x23_path = "outputs/checkpoints/a.dat"
    x24_path = "outputs/checkpoints/b.dat"
    (root / x23_path).parent.mkdir(parents=True, exist_ok=True)
    (root / x23_path).write_bytes(x23.tobytes())
    (root / x24_path).write_bytes(x24.tobytes())
    for relative, data in (
        (streaming.RUNNER_RELATIVE_PATH, b"dry-worker"),
        (streaming.ORCHESTRATOR_RELATIVE_PATH, b"orchestrator"),
        ("outputs/fixed.json", b"{}"),
        ("outputs/material.npz", b"material"),
        ("outputs/master.npz", b"master"),
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    coefficient_path = "outputs/checkpoints/stream/coefficient.json"
    evaluation_path = "outputs/checkpoints/stream/evaluation.json"
    protocol_path = root / "outputs/stream_protocol.json"
    algebraic = {
        **streaming.frozen.protected_anderson_tail_gates(),
        "predicted_boundary_spectrum_ratio_to_x24_below": 1.0,
        "predicted_boundary_bolometric_ratio_to_x24_below": 1.0,
        "pass1_pass2_each_mapped_block_sha256_must_match": True,
        "pass1_pass2_block_ownership_exactly_once": True,
        "each_dry_process_peak_rss_strictly_below_mib": 6144.0,
        "each_dry_worker_wall_time_strictly_below_s": 60.0,
        "each_dry_full_map_wall_time_strictly_below_s": 1800.0,
    }
    fresh = {
        "block_count_exactly": groups,
        "owned_frequency_group_count_exactly": groups,
        "minimum_input_and_mapped_intensity_at_least": 0.0,
        "each_process_peak_rss_strictly_below_mib": 6144.0,
        "each_worker_wall_time_strictly_below_s": 60.0,
        "full_map_wall_time_strictly_below_s": 1800.0,
        "input_global_residual_matches_phase7b9ab_absolute_tolerance": 2.0e-12,
        "input_boundary_metrics_match_phase7b9ab_absolute_tolerance": 2.0e-12,
    }
    protocol = {
        "phase": "test streaming commit",
        "sources": {
            "streaming_worker": _source(root, streaming.RUNNER_RELATIVE_PATH),
            "streaming_orchestrator": _source(
                root, streaming.ORCHESTRATOR_RELATIVE_PATH
            ),
            "finite_trial_protocol": _source(root, "outputs/fixed.json"),
            "finite_trial_material": _source(root, "outputs/material.npz"),
            "phase7b5p_master_input": _source(root, "outputs/master.npz"),
        },
        "configuration": {
            "orchestrator_path": streaming.ORCHESTRATOR_RELATIVE_PATH,
            "physical_frequency_groups": groups,
            "angular_direction_count": 1,
            "radiation_depth_cell_count": 1,
            "natural_frequency_block_count": groups,
            "diagnostic_frequency_block": 1,
            "minimum_forward_picard_fraction": 1.0,
            "maximum_forward_picard_fraction": 96.0,
            "maximum_concurrent_processes": 2,
            "x23_state_path": x23_path,
            "x23_state_sha256": _sha(root / x23_path),
            "x24_state_path": x24_path,
            "x24_state_sha256": _sha(root / x24_path),
            "candidate_output_path": x23_path,
            "fresh_map_output_path": x24_path,
            "raw_float64_checkpoint_size_bytes": groups * 8,
            "coefficient_manifest_path": coefficient_path,
            "evaluation_manifest_path": evaluation_path,
            "candidate_commit_manifest_path": (
                "outputs/checkpoints/stream/candidate_commit.json"
            ),
            "candidate_transient_backup_path": (
                "outputs/checkpoints/stream/candidate_transient_active.backup"
            ),
            "fresh_map_manifest_path": (
                "outputs/checkpoints/stream/fresh_manifest.json"
            ),
            "fresh_map_report_directory": (
                "outputs/checkpoints/stream/fresh_reports"
            ),
            "fresh_map_summary_path": "outputs/stream_fresh_summary.json",
        },
        "algebraic_gates": algebraic,
        "fresh_map_gates": fresh,
    }
    _write_json(protocol_path, protocol)
    protocol_hash = _sha(protocol_path)
    mu = np.asarray([0.5])
    weight = np.asarray([1.0])
    width = np.asarray([1.0])
    pass1 = []
    for index in range(groups):
        row = streaming.coefficient_block_statistics(
            x23[index : index + 1, None, None],
            x24[index : index + 1, None, None],
            x25[index : index + 1, None, None],
            global_group_start=index,
            mu=mu,
            weight=weight,
            frequency_width=width,
        )
        row.update(
            {
                "protocol_sha256": protocol_hash,
                "pass_index": 1,
                "block_index": index,
                "core_group_start": index,
                "core_group_stop": index + 1,
                "x23_state_sha256": protocol["configuration"]["x23_state_sha256"],
                "x24_state_sha256": protocol["configuration"]["x24_state_sha256"],
                "peak_process_rss_mib": 10.0,
                "wall_runtime_s": 1.0,
                "full_state_write_performed": False,
            }
        )
        pass1.append(row)
    coefficient = streaming.aggregate_coefficient_statistics(pass1)
    coefficient_manifest = {
        "protocol_sha256": protocol_hash,
        "status": "complete",
        "pass_index": 1,
        "full_state_write_performed": False,
        "full_map_wall_runtime_s": 100.0,
        "reports": pass1,
        "aggregate": coefficient,
    }
    _write_json(root / coefficient_path, coefficient_manifest)
    selected = float(coefficient["selected_forward_fraction"])
    pass2 = []
    for index in range(groups):
        row = streaming.evaluation_block_statistics(
            x23[index : index + 1, None, None],
            x24[index : index + 1, None, None],
            x25[index : index + 1, None, None],
            selected,
            mu,
            weight,
            width,
        )
        row.update(
            {
                "protocol_sha256": protocol_hash,
                "pass_index": 2,
                "block_index": index,
                "core_group_start": index,
                "core_group_stop": index + 1,
                "x23_state_sha256": protocol["configuration"]["x23_state_sha256"],
                "x24_state_sha256": protocol["configuration"]["x24_state_sha256"],
                "peak_process_rss_mib": 10.0,
                "wall_runtime_s": 1.0,
                "full_state_write_performed": False,
            }
        )
        pass2.append(row)
    evaluation = streaming.aggregate_evaluation_statistics(pass2, pass1)
    checks = streaming.algebraic_gate_checks(protocol, coefficient, evaluation)
    checks.update(
        {
            "pass1_resources_pass": True,
            "pass2_resources_pass": True,
            "block_ownership_pass": True,
        }
    )
    evaluation_manifest = {
        "protocol_sha256": protocol_hash,
        "status": "complete",
        "pass_index": 2,
        "coefficient_manifest_sha256": _sha(root / coefficient_path),
        "selected_forward_fraction": selected,
        "full_state_write_performed": False,
        "full_map_wall_runtime_s": 100.0,
        "reports": pass2,
        "aggregate": evaluation,
        "gate_checks": checks,
    }
    assert all(checks.values())
    _write_json(root / evaluation_path, evaluation_manifest)
    return protocol_path, protocol_hash, x23, x24, x25


def test_candidate_commit_requires_all_dry_gates(tmp_path: Path) -> None:
    protocol_path, digest, x23, _, _ = _fixture(tmp_path)
    protocol = json.loads(protocol_path.read_text())
    evaluation_path = tmp_path / protocol["configuration"]["evaluation_manifest_path"]
    evidence = json.loads(evaluation_path.read_text())
    evidence["gate_checks"]["boundary_improvement_pass"] = False
    _write_json(evaluation_path, evidence)
    before = (tmp_path / protocol["configuration"]["x23_state_path"]).read_bytes()
    with pytest.raises(RuntimeError, match="algebraic gate failed"):
        orchestrator.commit_candidate(tmp_path, protocol_path, digest)
    assert (tmp_path / protocol["configuration"]["x23_state_path"]).read_bytes() == before
    assert np.array_equal(np.frombuffer(before, dtype=np.float64), x23)


def test_candidate_commit_recovers_after_write_before_manifest(
    tmp_path: Path,
) -> None:
    protocol_path, digest, x23, x24, _ = _fixture(tmp_path)
    protocol = json.loads(protocol_path.read_text())
    selected = json.loads(
        (tmp_path / protocol["configuration"]["coefficient_manifest_path"]).read_text()
    )["aggregate"]["selected_forward_fraction"]
    unrelated = tmp_path / "outputs/checkpoints/unrelated.keep"
    unrelated.write_bytes(b"untouched")

    def fail(stage: str, index: int) -> None:
        if stage == "after_write_before_commit" and index == 0:
            raise RuntimeError("simulated crash")

    with pytest.raises(RuntimeError, match="simulated crash"):
        orchestrator.commit_candidate(
            tmp_path, protocol_path, digest, failure_hook=fail
        )
    result = orchestrator.commit_candidate(tmp_path, protocol_path, digest)
    expected = x24 + (float(selected) - 1.0) * (x24 - x23)
    candidate = np.frombuffer(
        (tmp_path / protocol["configuration"]["x23_state_path"]).read_bytes(),
        dtype=np.float64,
    )
    assert result["status"] == "complete"
    assert len(result["completed_blocks"]) == 76
    assert np.array_equal(candidate, expected)
    assert unrelated.read_bytes() == b"untouched"


def test_completed_candidate_is_idempotent(tmp_path: Path) -> None:
    protocol_path, digest, _, _, _ = _fixture(tmp_path)
    protocol = json.loads(protocol_path.read_text())
    first = orchestrator.commit_candidate(tmp_path, protocol_path, digest)
    candidate_path = tmp_path / protocol["configuration"]["x23_state_path"]
    content = candidate_path.read_bytes()
    second = orchestrator.commit_candidate(tmp_path, protocol_path, digest)
    assert second == first
    assert candidate_path.read_bytes() == content


def _fake_fresh_launcher(
    root: Path,
    protocol_path: Path,
    expected_hash: str,
    batch: list[int],
    output_state: Path,
    report_paths: list[Path],
) -> None:
    protocol = json.loads(protocol_path.read_text())
    candidate = np.frombuffer(
        (root / protocol["configuration"]["candidate_output_path"]).read_bytes(),
        dtype=np.float64,
    )
    output = np.memmap(output_state, mode="r+", dtype=np.float64, shape=(76,))
    for index, report_path in zip(batch, report_paths, strict=True):
        mapped = candidate[index]
        output[index] = mapped
        output.flush()
        change = abs(mapped - candidate[index])
        scale = max(abs(mapped), abs(candidate[index]))
        _write_json(
            report_path,
            {
                "protocol_sha256": expected_hash,
                "block_index": index,
                "core_group_start": index,
                "core_group_stop": index + 1,
                "maximum_absolute_radiation_change": change,
                "maximum_radiation_scale": scale,
                "boundary_spectrum_l1_numerator": change,
                "current_boundary_absolute_scale": abs(candidate[index]),
                "mapped_boundary_absolute_scale": abs(mapped),
                "current_boundary_bolometric": candidate[index],
                "mapped_boundary_bolometric": mapped,
                "minimum_input_intensity": candidate[index],
                "minimum_mapped_intensity": mapped,
                "peak_process_rss_mib": 10.0,
                "wall_runtime_s": 1.0,
            },
        )
    del output


def test_fresh_map_uses_two_workers_and_separates_prediction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol_path, digest, _, _, _ = _fixture(tmp_path)
    orchestrator.commit_candidate(tmp_path, protocol_path, digest)
    batches: list[list[int]] = []

    def launch(*args: object) -> None:
        batch = args[3]
        assert isinstance(batch, list)
        batches.append(list(batch))
        _fake_fresh_launcher(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(orchestrator, "_launch_fresh_workers", launch)
    summary = orchestrator.run_fresh_map(tmp_path, protocol_path, digest)
    assert all(len(batch) <= 2 for batch in batches)
    assert summary["status"] == "complete"
    assert "algebraic_prediction" in summary
    assert "fresh_input_global_original_operator_residual" in summary
    assert summary["decision"]["prediction_used_as_fresh_residual"] is False
    assert summary["decision"]["fresh_residual_measured_from_candidate_map"] is True
    assert summary["full_map_wall_runtime_s"] < 1800.0


def test_fresh_map_recovers_uncommitted_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol_path, digest, _, _, _ = _fixture(tmp_path)
    orchestrator.commit_candidate(tmp_path, protocol_path, digest)
    calls = 0

    def crash_once(*args: object) -> None:
        nonlocal calls
        calls += 1
        _fake_fresh_launcher(*args)  # type: ignore[arg-type]
        if calls == 1:
            raise RuntimeError("fresh crash before manifest commit")

    monkeypatch.setattr(orchestrator, "_launch_fresh_workers", crash_once)
    with pytest.raises(RuntimeError, match="fresh crash"):
        orchestrator.run_fresh_map(tmp_path, protocol_path, digest)
    monkeypatch.setattr(orchestrator, "_launch_fresh_workers", _fake_fresh_launcher)
    summary = orchestrator.run_fresh_map(tmp_path, protocol_path, digest)
    assert summary["status"] == "complete"
    assert summary["decision"]["fresh_original_operator_map_completed"] is True


def test_pass_hash_mismatch_blocks_commit_before_overwrite(tmp_path: Path) -> None:
    protocol_path, digest, _, _, _ = _fixture(tmp_path)
    protocol = json.loads(protocol_path.read_text())
    evaluation_path = tmp_path / protocol["configuration"]["evaluation_manifest_path"]
    evidence = json.loads(evaluation_path.read_text())
    evidence["reports"][-1]["mapped_block_sha256"] = "0" * 64
    _write_json(evaluation_path, evidence)
    evaluation = streaming.aggregate_evaluation_statistics
    before = (tmp_path / protocol["configuration"]["x23_state_path"]).read_bytes()
    with pytest.raises(RuntimeError):
        orchestrator.commit_candidate(tmp_path, protocol_path, digest)
    assert (tmp_path / protocol["configuration"]["x23_state_path"]).read_bytes() == before
    assert callable(evaluation)
