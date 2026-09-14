"""7B9du exhausted-dp pure-Picard continuation 的纯 tmp_path 测试。"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from scripts import phase7b9_half_trial_positive_sequence_engine as engine
from scripts import phase7b9_half_trial_radiation_continuation as storage
from scripts import phase7b9di_progression_continuation as progression
from scripts import phase7b9dp_post_streaming_picard as dp
from scripts import phase7b9du_exhausted_dp_picard_continuation as continuation
from scripts import phase7b9du_preregister_exhausted_dp_picard_continuation as prereg


def _write(root: Path, relative: str, payload: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_json(root: Path, relative: str, payload: dict[str, object]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": _sha(path),
    }


def _identity(index: int) -> str:
    return hashlib.sha256(f"state-{index}".encode()).hexdigest()


def _metrics(residual: float, contraction: float) -> dict[str, object]:
    return {
        "block_report_count": 76,
        "frequency_ownership_count": 9632,
        "frequency_ownership_exact": True,
        "global_original_operator_residual": residual,
        "boundary_spectrum_l1": 2.0e-3,
        "boundary_bolometric_fraction": 2.0e-3,
        "minimum_input_intensity": 0.5,
        "minimum_mapped_intensity": 0.5,
        "maximum_process_peak_rss_mib": 100.0,
        "maximum_worker_wall_runtime_s": 20.0,
        "full_map_wall_runtime_s": 1000.0,
        "contraction_ratio": contraction,
    }


def _record(index: int, gates: dict[str, object]) -> dict[str, object]:
    residual = 1.0e-2 * (0.99**index)
    metrics = _metrics(residual, 0.99)
    progression_checks = progression._progression_checks(gates, metrics, 0.99)
    convergence_checks = progression._convergence_checks(gates, metrics)
    boundary_pass = bool(
        convergence_checks["boundary_spectrum_pass"]
        and convergence_checks["boundary_bolometric_pass"]
    )
    input_path = (
        "outputs/checkpoints/buffer_a.dat"
        if index % 2 == 0
        else "outputs/checkpoints/buffer_b.dat"
    )
    mapped_path = (
        "outputs/checkpoints/buffer_b.dat"
        if index % 2 == 0
        else "outputs/checkpoints/buffer_a.dat"
    )
    return {
        "iteration": index,
        "input_state_path": input_path,
        "input_state_sha256": _identity(index),
        "mapped_state_path": mapped_path,
        "mapped_state_sha256": _identity(index + 1),
        **metrics,
        "contraction_applicable": True,
        "initial_reproduction_applicable": False,
        "gate_checks": {
            "frequency_ownership_pass": True,
            "positive_map_pass": True,
            "initial_reproduction_pass": True,
            "contraction_pass": True,
            "boundary_pass": boundary_pass,
            "resources_pass": True,
        },
        "original_map_passed": boundary_pass,
        "progression_gate_checks": progression_checks,
        "progression_passed": True,
        "convergence_gate_checks": convergence_checks,
        "convergence_passed": False,
        "map_passed": False,
        "block_report_audit": {
            "record_count": 76,
            "block_indices": list(range(76)),
            "sha256": _identity(1000 + index),
            "full_reports_retained": False,
        },
    }


def _fixture(
    root: Path, *, horizon: int = 7
) -> continuation.ExhaustedDpPicardContinuationSpec:
    for relative in (
        dp.RUNNER_RELATIVE_PATH,
        storage.SEQUENCE_ENGINE_RELATIVE_PATH,
        storage.RUNNER_RELATIVE_PATH,
        progression.RUNNER_RELATIVE_PATH,
        continuation.RUNNER_RELATIVE_PATH,
        continuation.PREREGISTER_RELATIVE_PATH,
    ):
        _write(root, relative, (PROJECT_ROOT / relative).read_bytes())
    _write(root, "outputs/fixed_material.npz", b"small fixed material")
    material = _source(root, "outputs/fixed_material.npz")
    _write_json(
        root,
        "outputs/fixed_protocol.json",
        {"sources": {"current_material_state": material}},
    )
    _write(root, "outputs/master.npz", b"small master")
    sources = {
        "finite_trial_protocol": _source(root, "outputs/fixed_protocol.json"),
        "finite_trial_material": material,
        "phase7b5p_master_input": _source(root, "outputs/master.npz"),
        "post_streaming_picard_runner": _source(root, dp.RUNNER_RELATIVE_PATH),
        "post_streaming_sequence_engine": _source(
            root, storage.SEQUENCE_ENGINE_RELATIVE_PATH
        ),
        "post_streaming_storage_helper": _source(root, storage.RUNNER_RELATIVE_PATH),
        "post_streaming_progression_gate_helper": _source(
            root, progression.RUNNER_RELATIVE_PATH
        ),
    }
    gates = storage.common.memory_safe_seeded_two_map_gates()
    rows = [_record(index, gates) for index in range(41)]
    # seed 的 contraction 在 dp 中不适用；7B9du 只严格审计后续 40 张图。
    rows[0]["contraction_ratio"] = None
    rows[0]["contraction_applicable"] = False
    dp_protocol_path = "outputs/dp_protocol.json"
    dp_manifest_path = "outputs/dp_manifest.json"
    dp_summary_path = "outputs/dp_summary.json"
    dp_protocol = {
        "phase": "7B9dp test",
        "sources": sources,
        "configuration": {
            "phase_index": 100,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 1,
            "radiation_depth_cell_count": 1,
            "raw_float64_checkpoint_size_bytes": 9632 * 8,
            "core_frequency_groups": 128,
            "diagnostic_frequency_block": 128,
            "natural_frequency_block_count": 76,
            "maximum_picard_maps": 41,
            "maximum_additional_picard_maps": 40,
            "seed_completed_picard_maps": 1,
            "first_runtime_iteration": 1,
            "last_runtime_iteration": 40,
            "maximum_concurrent_processes": 2,
            "runner_path": dp.RUNNER_RELATIVE_PATH,
            "transient_report_budget_bytes": storage.TRANSIENT_REPORT_BUDGET_BYTES,
            "material_feedback_authorization_mode": (
                "after_two_consecutive_and_formal_pair"
            ),
        },
        "gates": gates,
        "progression_gate_definition": continuation._expected_progression_definition(
            gates
        ),
        "convergence_gate_definition": continuation._expected_convergence_definition(
            gates
        ),
        "authorization": {
            "pure_picard_only": True,
            "anderson_after_seed": False,
            "continue_only_if_progression_gate_passes": True,
            "pause_at_first_low_residual_and_boundary_input": True,
            "provisional_feedback_extraction_at_pause": True,
            "provisional_feedback_is_formal_pair_authority": False,
            "material_feedback_authorized": False,
            "formal_pair_requires_next_consecutive_fresh_residual": True,
            "overwrite_only_two_claimed_buffers": True,
            "start_every_map_from_block_zero": True,
            "delete_only_stage_owned_transient_reports": True,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    _write_json(root, dp_protocol_path, dp_protocol)
    dp_digest = _sha(root / dp_protocol_path)
    last = rows[-1]
    manifest = {
        "protocol_sha256": dp_digest,
        "status": "maximum_maps_exhausted",
        "current_input_path": last["input_state_path"],
        "current_input_sha256": last["input_state_sha256"],
        "next_output_path": last["mapped_state_path"],
        "next_output_sha256": last["mapped_state_sha256"],
        "iterations": rows,
        "active_iteration": None,
    }
    summary = {
        "protocol_sha256": dp_digest,
        "status": "maximum_maps_exhausted",
        "completed_picard_maps": 41,
        "completed_additional_picard_maps": 40,
        "iterations": rows,
        "decision": {
            "positive_picard_sequence_reached_first_low_residual": False,
            "provisional_feedback_extraction_authorized": False,
            "formal_h_he_feedback_pair_authorized": False,
            "material_feedback_authorized": False,
            "anderson_used_after_seed": False,
            "dynamic_nlte_solution_accepted": False,
        },
    }
    _write_json(root, dp_manifest_path, manifest)
    _write_json(root, dp_summary_path, summary)
    return continuation.ExhaustedDpPicardContinuationSpec(
        phase="7B9du test",
        phase_index=210,
        classification="[A-preregistered]+[V]+[O]",
        dp_protocol_path=dp_protocol_path,
        dp_manifest_path=dp_manifest_path,
        dp_summary_path=dp_summary_path,
        additional_map_horizon=horizon,
        runner_path=continuation.RUNNER_RELATIVE_PATH,
        preregister_path=continuation.PREREGISTER_RELATIVE_PATH,
        manifest_path="outputs/checkpoints/du/manifest.json",
        transient_report_directory="outputs/checkpoints/phase7b9du_transient_reports",
        summary_path="outputs/du_summary.json",
        figure_path="outputs/du.png",
    )


def _refresh_dp_lineage(root: Path, spec: continuation.ExhaustedDpPicardContinuationSpec) -> None:
    digest = _sha(root / spec.dp_protocol_path)
    for relative in (spec.dp_manifest_path, spec.dp_summary_path):
        payload = json.loads((root / relative).read_text(encoding="utf-8"))
        payload["protocol_sha256"] = digest
        _write_json(root, relative, payload)


def test_builder_reuses_terminal_two_buffers_and_explicit_horizon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _fixture(tmp_path, horizon=9)
    original_sha = continuation._sha256

    def guarded_sha(path: Path) -> str:
        assert path.suffix.lower() != ".dat"
        return original_sha(path)

    monkeypatch.setattr(continuation, "_sha256", guarded_sha)
    protocol = continuation.build_exhausted_dp_picard_continuation_protocol(
        tmp_path, spec
    )
    cfg = protocol["configuration"]
    assert cfg["maximum_additional_picard_maps"] == 9
    assert cfg["maximum_picard_maps"] == 10
    assert (cfg["first_runtime_iteration"], cfg["last_runtime_iteration"]) == (1, 9)
    assert cfg["maximum_concurrent_processes"] == 2
    assert cfg["initial_state_path"] == "outputs/checkpoints/buffer_b.dat"
    assert cfg["scratch_state_path"] == "outputs/checkpoints/buffer_a.dat"
    assert protocol["gates"] == storage.common.memory_safe_seeded_two_map_gates()
    assert protocol["gates"]["each_full_map_wall_time_strictly_below_s"] == 1800.0
    assert all(not source["path"].endswith(".dat") for source in protocol["sources"].values())
    assert protocol["seed_iteration"]["upstream_dp_iteration"] == 40
    assert "block_report_audit" not in protocol["seed_iteration"]
    assert protocol["seed_iteration"]["failed_upstream_points_retained"] is False
    assert protocol["storage_plan"]["additional_full_state_allocation_count"] == 0


@pytest.mark.parametrize("horizon", [0, -1, True])
def test_builder_requires_positive_explicit_horizon(tmp_path: Path, horizon: object) -> None:
    spec = replace(_fixture(tmp_path), additional_map_horizon=horizon)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="positive integer"):
        continuation.build_exhausted_dp_picard_continuation_protocol(tmp_path, spec)


@pytest.mark.parametrize("failure", ["status", "progression", "convergence", "chain"])
def test_builder_rejects_noneligible_dp_history(tmp_path: Path, failure: str) -> None:
    spec = _fixture(tmp_path)
    manifest_path = tmp_path / spec.dp_manifest_path
    summary_path = tmp_path / spec.dp_summary_path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if failure == "status":
        manifest["status"] = summary["status"] = "running"
    elif failure == "progression":
        manifest["iterations"][12]["progression_passed"] = False
        summary["iterations"] = manifest["iterations"]
    elif failure == "convergence":
        row = manifest["iterations"][12]
        row["global_original_operator_residual"] = 5.0e-5
        row["boundary_spectrum_l1"] = 5.0e-4
        row["boundary_bolometric_fraction"] = 5.0e-4
        row["convergence_gate_checks"] = {
            "residual_pass": True,
            "boundary_spectrum_pass": True,
            "boundary_bolometric_pass": True,
        }
        row["convergence_passed"] = True
        row["map_passed"] = True
        summary["iterations"] = manifest["iterations"]
    else:
        manifest["iterations"][12]["input_state_sha256"] = "f" * 64
        summary["iterations"] = manifest["iterations"]
    _write_json(tmp_path, spec.dp_manifest_path, manifest)
    _write_json(tmp_path, spec.dp_summary_path, summary)
    match = "exhausted 40-map" if failure == "status" else (
        "chain is discontinuous" if failure == "chain" else "all pass progression"
    )
    with pytest.raises(RuntimeError, match=match):
        continuation.build_exhausted_dp_picard_continuation_protocol(tmp_path, spec)


def test_builder_rejects_dat_source_without_hashing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _fixture(tmp_path)
    path = tmp_path / spec.dp_protocol_path
    protocol = json.loads(path.read_text(encoding="utf-8"))
    protocol["sources"]["forbidden"] = {
        "path": "outputs/checkpoints/forbidden.dat",
        "size_bytes": 8,
        "sha256": "d" * 64,
    }
    _write_json(tmp_path, spec.dp_protocol_path, protocol)
    _refresh_dp_lineage(tmp_path, spec)
    original_sha = continuation._sha256

    def guarded_sha(candidate: Path) -> str:
        assert candidate.suffix.lower() != ".dat"
        return original_sha(candidate)

    monkeypatch.setattr(continuation, "_sha256", guarded_sha)
    with pytest.raises(RuntimeError, match="small sources cannot contain .dat"):
        continuation.build_exhausted_dp_picard_continuation_protocol(tmp_path, spec)


def _executor(
    protocol_hash: str,
    metrics_by_iteration: dict[int, tuple[float, float, float]],
):
    def execute(
        iteration: int,
        indices: list[int],
        input_path: Path,
        input_hash: str,
        output_path: Path,
        report_paths: list[Path],
    ) -> list[dict[str, object]]:
        residual, boundary, bolometric = metrics_by_iteration[iteration]
        source = np.memmap(input_path, mode="r", dtype=np.float64, shape=(9632,))
        output = np.memmap(output_path, mode="r+", dtype=np.float64, shape=(9632,))
        rows = []
        for index in indices:
            start = index * 128
            stop = min(start + 128, 9632)
            output[start:stop] = source[start:stop] + 0.01
            output.flush()
            rows.append(
                {
                    "protocol_sha256": protocol_hash,
                    "input_state_sha256": input_hash,
                    "picard_iteration": iteration,
                    "block_index": index,
                    "core_group_start": start,
                    "core_group_stop": stop,
                    "maximum_absolute_radiation_change": residual,
                    "maximum_radiation_scale": 1.0,
                    "boundary_spectrum_l1_numerator": boundary,
                    "current_boundary_absolute_scale": 1.0,
                    "mapped_boundary_absolute_scale": 1.0,
                    "current_boundary_bolometric": 1.0,
                    "mapped_boundary_bolometric": 1.0 / (1.0 - bolometric),
                    "minimum_input_intensity": 0.5,
                    "minimum_mapped_intensity": 0.5,
                    "peak_process_rss_mib": 100.0,
                    "wall_runtime_s": 1.0,
                }
            )
        del output, source
        return rows

    return execute


def test_runner_continues_with_same_buffers_and_pauses_on_convergence(
    tmp_path: Path,
) -> None:
    spec = _fixture(tmp_path, horizon=2)
    protocol = continuation.build_exhausted_dp_picard_continuation_protocol(
        tmp_path, spec
    )
    current = np.ones(9632, dtype=np.float64)
    scratch = np.full(9632, 0.9, dtype=np.float64)
    current_path = tmp_path / protocol["configuration"]["initial_state_path"]
    scratch_path = tmp_path / protocol["configuration"]["scratch_state_path"]
    _write(tmp_path, protocol["configuration"]["initial_state_path"], current.tobytes())
    _write(tmp_path, protocol["configuration"]["scratch_state_path"], scratch.tobytes())
    current_sha = _sha(current_path)
    scratch_sha = _sha(scratch_path)
    cfg = protocol["configuration"]
    cfg["initial_state_sha256"] = current_sha
    cfg["scratch_state_initial_sha256"] = scratch_sha
    protocol["full_state_claims"]["current_initial_is_dp_terminal_mapped"]["sha256"] = current_sha
    protocol["full_state_claims"]["scratch_initial_is_dp_terminal_input"]["sha256"] = scratch_sha
    protocol["seed_iteration"]["mapped_state_sha256"] = current_sha
    protocol["seed_iteration"]["input_state_sha256"] = scratch_sha
    protocol["seed_iteration"]["global_original_operator_residual"] = 1.0e-2
    protocol_path = tmp_path / "outputs/du_protocol.json"
    _write_json(tmp_path, "outputs/du_protocol.json", protocol)
    digest = _sha(protocol_path)
    first = continuation.run_continuation(
        tmp_path,
        protocol_path,
        digest,
        batch_executor=_executor(digest, {1: (5.0e-3, 2.0e-3, 2.0e-3)}),
        stop_after_iteration=1,
    )
    assert first["status"] == "running"
    assert first["completed_additional_picard_maps"] == 1
    second = continuation.run_continuation(
        tmp_path,
        protocol_path,
        digest,
        batch_executor=_executor(digest, {2: (5.0e-5, 5.0e-4, 5.0e-4)}),
    )
    assert second["status"] == "provisional_pause"
    assert second["completed_additional_picard_maps"] == 2
    assert second["decision"]["provisional_feedback_extraction_authorized"] is True
    assert second["decision"]["formal_h_he_feedback_pair_authorized"] is False
    assert {
        row["input_state_path"] for row in second["iterations"]
    } <= {
        "outputs/checkpoints/buffer_a.dat",
        "outputs/checkpoints/buffer_b.dat",
    }


def test_preregister_cli_is_atomic_and_does_not_choose_horizon(tmp_path: Path) -> None:
    spec = _fixture(tmp_path, horizon=6)
    argv = [
        "--phase", spec.phase,
        "--phase-index", str(spec.phase_index),
        "--classification", spec.classification,
        "--dp-protocol", spec.dp_protocol_path,
        "--dp-manifest", spec.dp_manifest_path,
        "--dp-summary", spec.dp_summary_path,
        "--additional-map-horizon", "6",
        "--manifest", spec.manifest_path,
        "--transient-report-directory", spec.transient_report_directory,
        "--summary", spec.summary_path,
        "--figure", spec.figure_path,
        "--output", "outputs/du_protocol.json",
    ]
    protocol, digest = prereg.main(argv, root=tmp_path)
    output = tmp_path / "outputs/du_protocol.json"
    assert digest == _sha(output)
    assert protocol["configuration"]["maximum_additional_picard_maps"] == 6
    assert protocol["builder_audit"]["additional_map_horizon_selected_by_builder"] is False
    assert not output.with_name(f"{output.name}.tmp").exists()


def test_existing_dp_and_engine_bytes_remain_unchanged(tmp_path: Path) -> None:
    protected = [
        PROJECT_ROOT / dp.RUNNER_RELATIVE_PATH,
        PROJECT_ROOT / storage.SEQUENCE_ENGINE_RELATIVE_PATH,
    ]
    before = [_sha(path) for path in protected]
    spec = _fixture(tmp_path)
    continuation.build_exhausted_dp_picard_continuation_protocol(tmp_path, spec)
    assert [_sha(path) for path in protected] == before
