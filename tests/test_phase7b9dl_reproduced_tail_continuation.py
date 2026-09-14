"""7B9dl valid-history replacement、maps21..23 与 streaming 接线测试。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT, ROOT / "scripts"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from scripts import phase7b9di_streaming_anderson_tail as streaming
from scripts import phase7b9dl_preregister_reproduced_tail as preregistration
from scripts import phase7b9dl_reproduced_tail_continuation as continuation


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _source(root: Path, relative: str) -> dict[str, object]:
    data = (root / relative).read_bytes()
    return {"path": relative, "size_bytes": len(data), "sha256": _sha(data)}


def _record(
    index: int,
    input_path: str,
    input_sha: str,
    output_path: str,
    output_sha: str,
    residual: float,
    *,
    progression: bool = True,
) -> dict[str, object]:
    return {
        "iteration": index,
        "input_state_path": input_path,
        "input_state_sha256": input_sha,
        "mapped_state_path": output_path,
        "mapped_state_sha256": output_sha,
        "global_original_operator_residual": residual,
        "contraction_ratio": 0.95 if progression else 7.0,
        "boundary_spectrum_l1": 5.0e-4,
        "boundary_bolometric_fraction": 4.0e-4,
        "progression_gate_checks": {
            "frequency_ownership_pass": True,
            "positive_map_pass": True,
            "contraction_pass": progression,
            "resources_pass": True,
        },
        "progression_passed": progression,
        "convergence_gate_checks": {
            "residual_pass": False,
            "boundary_spectrum_pass": True,
            "boundary_bolometric_pass": True,
        },
        "convergence_passed": False,
        "map_passed": False,
    }


def _fixture(
    root: Path,
) -> tuple[continuation.ReproducedTailContinuationSpec, Path, Path]:
    _write(root / continuation.RUNNER_RELATIVE_PATH, b"dl runner")
    _write(root / "outputs/material.npz", b"material")
    material = _source(root, "outputs/material.npz")
    _write(root / "outputs/master.npz", b"master")
    _write(root / "outputs/fixed.json", {"sources": {"current_material_state": material}})
    a_path = root / "outputs/checkpoints/A.dat"
    b_path = root / "outputs/checkpoints/B.dat"
    a_path.parent.mkdir(parents=True, exist_ok=True)
    np.full((76, 1, 1), 0.9, dtype=np.float64).tofile(a_path)
    np.ones((76, 1, 1), dtype=np.float64).tofile(b_path)
    a_sha = _sha(a_path.read_bytes())
    fresh_b_sha = _sha(b_path.read_bytes())
    gates = {
        "block_count_exactly": 76,
        "owned_frequency_group_count_exactly": 76,
        "minimum_input_and_mapped_intensity_at_least": 0.0,
        "global_original_operator_residual_below": 1.0e-4,
        "subsequent_residual_contraction_ratio_below": 1.01,
        "global_boundary_spectrum_l1_below": 1.0e-3,
        "global_boundary_bolometric_fraction_below": 1.0e-3,
        "each_process_peak_rss_strictly_below_mib": 6144.0,
        "each_worker_wall_time_strictly_below_s": 60.0,
        "each_full_map_wall_time_strictly_below_s": 1800.0,
    }
    di_protocol = {
        "phase": "di",
        "sources": {
            "finite_trial_protocol": _source(root, "outputs/fixed.json"),
            "finite_trial_material": material,
            "phase7b5p_master_input": _source(root, "outputs/master.npz"),
        },
        "configuration": {
            "physical_frequency_groups": 76,
            "angular_direction_count": 1,
            "radiation_depth_cell_count": 1,
            "raw_float64_checkpoint_size_bytes": 76 * 8,
            "diagnostic_fixed_iteration_count": 1,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "source_map_only": True,
            "material_candidate_absolute_relaxation": 0.0625,
            "maximum_picard_maps": 24,
            "maximum_concurrent_processes": 2,
        },
        "gates": gates,
    }
    _write(root / "outputs/di_protocol.json", di_protocol)
    di_sha = _sha((root / "outputs/di_protocol.json").read_bytes())
    paths = [
        "outputs/checkpoints/A.dat" if index % 2 == 0 else "outputs/checkpoints/B.dat"
        for index in range(21)
    ]
    hashes = [_sha(f"historical-{index}".encode()) for index in range(20)] + [a_sha]
    valid = [
        _record(
            index,
            paths[index],
            hashes[index],
            paths[index + 1],
            hashes[index + 1],
            0.01 / (index + 1),
        )
        for index in range(20)
    ]
    failed_b_sha = _sha(b"failed nonreproducible B")
    rejected = _record(
        20,
        "outputs/checkpoints/A.dat",
        a_sha,
        "outputs/checkpoints/B.dat",
        failed_b_sha,
        0.0135,
        progression=False,
    )
    di_manifest = {
        "protocol_sha256": di_sha,
        "status": "gate_failed",
        "active_iteration": None,
        "iterations": [*valid, rejected],
    }
    _write(root / "outputs/di_manifest.json", di_manifest)
    _write(root / "outputs/di_summary.json", di_manifest)
    _write(root / "outputs/dk_protocol.json", {"phase": "dk"})
    dk_sha = _sha((root / "outputs/dk_protocol.json").read_bytes())
    metrics = {
        "frequency_ownership_count": 76,
        "frequency_ownership_exact": True,
        "global_original_operator_residual": 1.6842474096e-3,
        "boundary_spectrum_l1": 5.16182e-4,
        "boundary_bolometric_fraction": 5.14153e-4,
        "minimum_input_intensity": 0.0,
        "minimum_mapped_intensity": 0.0,
        "maximum_process_peak_rss_mib": 3000.0,
        "maximum_worker_wall_runtime_s": 12.0,
        "block_report_count": 76,
        "full_map_wall_runtime_s": 300.0,
        "contraction_ratio": 0.9473781281,
    }
    progression = {
        "frequency_ownership_pass": True,
        "positive_map_pass": True,
        "contraction_pass": True,
        "resources_pass": True,
    }
    convergence = {
        "residual_pass": False,
        "boundary_spectrum_pass": True,
        "boundary_bolometric_pass": True,
    }
    dk_manifest = {
        "protocol_sha256": dk_sha,
        "status": "reproduction_passed",
        "reproduction_passed": True,
    }
    dk_summary = {
        "protocol_sha256": dk_sha,
        "status": "reproduction_passed",
        "immutable_input_path": "outputs/checkpoints/A.dat",
        "immutable_input_sha256": a_sha,
        "fresh_output_path": "outputs/checkpoints/B.dat",
        "fresh_output_sha256": fresh_b_sha,
        "failed_output_previous_sha256": failed_b_sha,
        "block_report_count": 76,
        "metrics": metrics,
        "progression_gate_checks": progression,
        "convergence_gate_checks": convergence,
        "decision": {
            "full_76_block_reproduction_passed": True,
            "fresh_state_authorized_as_continuation_input": True,
        },
    }
    _write(root / "outputs/dk_manifest.json", dk_manifest)
    _write(root / "outputs/dk_summary.json", dk_summary)
    return (
        continuation.ReproducedTailContinuationSpec(
            phase="dl",
            phase_index=2000,
            classification="[A-preregistered]+[V]+[O]",
            di_protocol_path="outputs/di_protocol.json",
            di_manifest_path="outputs/di_manifest.json",
            di_summary_path="outputs/di_summary.json",
            dk_protocol_path="outputs/dk_protocol.json",
            dk_manifest_path="outputs/dk_manifest.json",
            dk_summary_path="outputs/dk_summary.json",
            runner_path=continuation.RUNNER_RELATIVE_PATH,
            manifest_path="outputs/checkpoints/dl/manifest.json",
            transient_report_directory="outputs/checkpoints/dl_transient_reports",
            summary_path="outputs/dl_summary.json",
            figure_path="outputs/dl.png",
            fresh_current_sha256=fresh_b_sha,
            immutable_scratch_sha256=a_sha,
        ),
        a_path,
        b_path,
    )


def _executor(protocol_hash: str):
    deltas = {21: 1.5e-3, 22: 1.4e-3, 23: 1.3e-3}

    def execute(
        iteration: int,
        indices: list[int],
        input_path: Path,
        input_sha: str,
        output_path: Path,
        report_paths: list[Path],
    ) -> list[dict[str, object]]:
        source = np.memmap(input_path, mode="r", dtype=np.float64, shape=(76, 1, 1))
        target = np.memmap(output_path, mode="r+", dtype=np.float64, shape=(76, 1, 1))
        rows = []
        delta = deltas[iteration]
        for index in indices:
            mapped = float(source[index, 0, 0]) + delta
            target[index, 0, 0] = mapped
            rows.append(
                {
                    "protocol_sha256": protocol_hash,
                    "input_state_sha256": input_sha,
                    "picard_iteration": iteration,
                    "block_index": index,
                    "core_group_start": index,
                    "core_group_stop": index + 1,
                    "maximum_absolute_radiation_change": delta,
                    "maximum_radiation_scale": mapped,
                    "block_relative_radiation_change": delta / mapped,
                    "boundary_spectrum_l1_numerator": 1.0e-9,
                    "current_boundary_absolute_scale": 1.0,
                    "mapped_boundary_absolute_scale": 1.0,
                    "current_boundary_bolometric": 1.0,
                    "mapped_boundary_bolometric": 1.0,
                    "minimum_input_intensity": float(source[index, 0, 0]),
                    "minimum_mapped_intensity": mapped,
                    "peak_process_rss_mib": 100.0,
                    "wall_runtime_s": 0.01,
                }
            )
        target.flush()
        del source, target
        return rows

    return execute


def test_builder_replaces_rejected_di20_with_fresh_dk20(tmp_path: Path) -> None:
    spec, _, _ = _fixture(tmp_path)
    protocol = continuation.build_reproduced_tail_protocol(tmp_path, spec)
    assert len(protocol["seed_valid_iterations"]) == 21
    fresh = protocol["seed_valid_iterations"][-1]
    rejected = protocol["rejected_evidence"]["record"]
    assert fresh["reproduction_classification"] == "fresh_full_76_block_reproduction"
    assert fresh["mapped_state_sha256"] == spec.fresh_current_sha256
    assert rejected["progression_passed"] is False
    assert protocol["rejected_evidence"]["may_enter_valid_history"] is False
    assert protocol["configuration"]["first_runtime_iteration"] == 21
    assert protocol["configuration"]["last_runtime_iteration"] == 23


def test_prereg_builder_does_not_hash_dat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec, a_path, b_path = _fixture(tmp_path)
    original = continuation._sha256

    def guard(path: Path) -> str:
        if path.suffix == ".dat":
            raise AssertionError("builder touched dat")
        return original(path)

    monkeypatch.setattr(continuation, "_sha256", guard)
    payload, digest = preregistration.preregister(
        tmp_path, spec=spec, output_path="outputs/dl_protocol.json"
    )
    assert len(digest) == 64
    assert payload["configuration"]["seed_completed_picard_maps"] == 21
    assert a_path.exists() and b_path.exists()


def test_runtime_only_runs_21_to_23_and_exposes_streaming_schema(tmp_path: Path) -> None:
    spec, _, _ = _fixture(tmp_path)
    protocol_path = tmp_path / "outputs/dl_protocol.json"
    _, digest = continuation.write_protocol(tmp_path, spec, protocol_path)
    summary = continuation.run_continuation(
        tmp_path,
        protocol_path,
        digest,
        batch_executor=_executor(digest),
    )
    assert summary["status"] == "maximum_maps_exhausted"
    assert [row["iteration"] for row in summary["iterations"][-4:]] == [20, 21, 22, 23]
    assert summary["iterations"][20]["reproduction_classification"].startswith("fresh")
    assert summary["rejected_evidence"]["record"]["progression_passed"] is False
    manifest = json.loads((tmp_path / spec.manifest_path).read_text())
    assert len(manifest["iterations"]) == 24
    assert all(row["progression_passed"] for row in manifest["iterations"])

    for path in (
        streaming.RUNNER_RELATIVE_PATH,
        streaming.ORCHESTRATOR_RELATIVE_PATH,
        streaming.PREREGISTER_BUILDER_RELATIVE_PATH,
        streaming.DRY_PASS_PARENT_RELATIVE_PATH,
    ):
        _write(tmp_path / path, f"dummy {path}".encode())
    stream_spec = streaming.StreamingAndersonTailSpec(
        phase="stream",
        phase_index=2100,
        classification="[A-preregistered]+[V]+[O]",
        di_protocol_path="outputs/dl_protocol.json",
        di_manifest_path=spec.manifest_path,
        di_summary_path=spec.summary_path,
        worker_path=streaming.RUNNER_RELATIVE_PATH,
        coefficient_report_directory="outputs/checkpoints/stream/pass1",
        evaluation_report_directory="outputs/checkpoints/stream/pass2",
        coefficient_manifest_path="outputs/checkpoints/stream/coefficient.json",
        evaluation_manifest_path="outputs/checkpoints/stream/evaluation.json",
        candidate_summary_path="outputs/stream_summary.json",
        candidate_figure_path="outputs/stream.png",
    )
    stream_protocol = streaming.build_streaming_anderson_tail_protocol(
        tmp_path, stream_spec
    )
    assert stream_protocol["sources"]["exhausted_tail_protocol"] == _source(
        tmp_path, "outputs/dl_protocol.json"
    )
    assert stream_protocol["sources"]["exhausted_tail_manifest"] == _source(
        tmp_path, spec.manifest_path
    )
    assert stream_protocol["sources"]["exhausted_tail_summary"] == _source(
        tmp_path, spec.summary_path
    )
    assert stream_protocol["sources"]["phase7b9di_protocol"]["path"] == (
        spec.di_protocol_path
    )
    assert stream_protocol["sources"]["phase7b9di_manifest"]["path"] == (
        spec.di_manifest_path
    )
    assert stream_protocol["sources"]["phase7b9di_summary"]["path"] == (
        spec.di_summary_path
    )
    assert stream_protocol["full_state_claims"][
        "x24_retained_through_both_dry_maps"
    ]["sha256"] == manifest["iterations"][-1]["mapped_state_sha256"]


def test_dk_fresh_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    spec, _, _ = _fixture(tmp_path)
    path = tmp_path / spec.dk_summary_path
    payload = json.loads(path.read_text())
    payload["fresh_output_sha256"] = "0" * 64
    _write(path, payload)
    with pytest.raises(RuntimeError, match="A/B lineage changed"):
        continuation.build_reproduced_tail_protocol(tmp_path, spec)
