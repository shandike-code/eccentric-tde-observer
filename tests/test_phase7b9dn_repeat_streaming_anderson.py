"""7B9dn repeat-cycle preregistration 的纯 tmp_path 回归。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT, ROOT / "scripts"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from scripts import phase7b9_streaming_dry_pass_parent as dry_parent
from scripts import phase7b9di_streaming_anderson_orchestrator as orchestrator
from scripts import phase7b9di_streaming_anderson_tail as streaming
from scripts import phase7b9dn_repeat_streaming_anderson as repeat


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _source(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": streaming._sha256(path),
    }


def _ranges() -> list[tuple[int, int]]:
    return [
        (index * 128, min((index + 1) * 128, 9632))
        for index in range(76)
    ]


def _report_claim(root: Path, relative: str, index: int) -> dict[str, object]:
    return {"block_index": index, **_source(root, relative)}


def _fixture(
    root: Path,
    *,
    source_collision: bool | str = False,
    dat_source: bool = False,
) -> dict[str, str]:
    paths = {
        "protocol": "outputs/prior_streaming_protocol.json",
        "pass1": "outputs/checkpoints/prior_work/pass1_manifest.json",
        "pass2": "outputs/checkpoints/prior_work/pass2_manifest.json",
        "commit": "outputs/checkpoints/prior_work/candidate_commit.json",
        "fresh": "outputs/checkpoints/prior_work/fresh_manifest.json",
        "summary": "outputs/prior_fresh_summary.json",
    }
    for relative in (
        streaming.RUNNER_RELATIVE_PATH,
        streaming.ORCHESTRATOR_RELATIVE_PATH,
        streaming.DRY_PASS_PARENT_RELATIVE_PATH,
        streaming.PREREGISTER_BUILDER_RELATIVE_PATH,
        repeat.BUILDER_RELATIVE_PATH,
        "outputs/material.npz",
        "outputs/master.npz",
    ):
        _write(root / relative, f"small source: {relative}".encode())
    _write(
        root / "outputs/fixed.json",
        {
            "sources": {
                "current_material_state": _source(root, "outputs/material.npz")
            }
        },
    )
    sources = {
        "streaming_anderson_worker": _source(
            root, streaming.RUNNER_RELATIVE_PATH
        ),
        "streaming_anderson_orchestrator": _source(
            root, streaming.ORCHESTRATOR_RELATIVE_PATH
        ),
        "streaming_anderson_dry_pass_parent": _source(
            root, streaming.DRY_PASS_PARENT_RELATIVE_PATH
        ),
        "streaming_anderson_preregister_builder": _source(
            root, streaming.PREREGISTER_BUILDER_RELATIVE_PATH
        ),
        "finite_trial_protocol": _source(root, "outputs/fixed.json"),
        "finite_trial_material": _source(root, "outputs/material.npz"),
        "phase7b5p_master_input": _source(root, "outputs/master.npz"),
    }
    if source_collision:
        collision_key = (
            source_collision
            if isinstance(source_collision, str)
            else "prior_streaming_protocol"
        )
        sources[collision_key] = _source(
            root, "outputs/fixed.json"
        )
    if dat_source:
        sources["forbidden_full_state"] = {
            "path": "outputs/checkpoints/forbidden.dat",
            "size_bytes": 123,
            "sha256": "a" * 64,
        }
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
    fresh_gates = streaming.frozen.memory_safe_candidate_map_gates()
    fresh_gates["each_worker_wall_time_strictly_below_s"] = 60.0
    old_x23 = _hash_bytes(b"old x23")
    old_x24 = _hash_bytes(b"old x24")
    protocol = {
        "phase": "prior complete streaming cycle",
        "protocol_version": 1,
        "classification": "[A]+[V]+[O]",
        "sources": sources,
        "full_state_claims": {},
        "configuration": {
            "phase_index": 1433,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "scan_frequency_chunk": 16,
            "diagnostic_frequency_block": 128,
            "minimum_forward_picard_fraction": 1.0,
            "maximum_forward_picard_fraction": 96.0,
            "maximum_concurrent_processes": 2,
            "diagnostic_fixed_iteration_count": 1,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "source_map_only": True,
            "x23_state_path": "outputs/checkpoints/a.dat",
            "x23_state_sha256": old_x23,
            "x24_state_path": "outputs/checkpoints/b.dat",
            "x24_state_sha256": old_x24,
            "x23_global_original_operator_residual": 1.0e-3,
            "x23_boundary_spectrum_l1": 5.0e-4,
            "x23_boundary_bolometric_fraction": 4.0e-4,
            "raw_float64_checkpoint_size_bytes": 10_099_884_032,
            "coefficient_report_directory": (
                "outputs/checkpoints/prior_work/pass1_reports"
            ),
            "evaluation_report_directory": (
                "outputs/checkpoints/prior_work/pass2_reports"
            ),
            "coefficient_manifest_path": paths["pass1"],
            "evaluation_manifest_path": paths["pass2"],
            "candidate_summary_path": "outputs/prior_candidate.json",
            "candidate_figure_path": "outputs/prior_candidate.png",
            "runner_path": streaming.RUNNER_RELATIVE_PATH,
            "orchestrator_path": streaming.ORCHESTRATOR_RELATIVE_PATH,
            "dry_pass_parent_path": streaming.DRY_PASS_PARENT_RELATIVE_PATH,
            "candidate_commit_manifest_path": paths["commit"],
            "candidate_transient_backup_path": (
                "outputs/checkpoints/prior_work/candidate_transient.backup"
            ),
            "fresh_map_manifest_path": paths["fresh"],
            "fresh_map_report_directory": (
                "outputs/checkpoints/prior_work/fresh_reports"
            ),
            "fresh_map_summary_path": paths["summary"],
            "candidate_output_path": "outputs/checkpoints/a.dat",
            "fresh_map_output_path": "outputs/checkpoints/b.dat",
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "kkt_regularization": False,
            "matter_feedback": False,
        },
        "coefficient_formula": {},
        "algebraic_gates": algebraic,
        "fresh_map_gates": fresh_gates,
        "resource_gate_provenance": {},
        "execution_plan": {
            "additional_full_state_count": 0,
            "transport_equivalent_full_map_count": 3,
            "dry_map_count": 2,
            "fresh_residual_map_count": 1,
            "candidate_algebraic_full_state_write_count": 1,
            "dry_maps_count_as_fresh_residuals": False,
        },
        "authorization": {
            "pass1_may_write_full_state": False,
            "pass2_may_write_full_state": False,
            "fresh_full_original_operator_map_required": True,
            "fresh_map_maximum_concurrent_processes": 2,
            "fresh_map_wall_time_strictly_below_s": 1800.0,
            "each_dry_map_maximum_concurrent_processes": 2,
            "each_dry_map_wall_time_strictly_below_s": 1800.0,
            "predicted_metrics_are_acceptance_authority": False,
            "material_feedback_authorized": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    _write(root / paths["protocol"], protocol)
    protocol_hash = streaming._sha256(root / paths["protocol"])
    pass1_reports = []
    pass2_reports = []
    pass1_files = []
    pass2_files = []
    for index, (start, stop) in enumerate(_ranges()):
        mapped_hash = _hash_bytes(f"mapped block {index}".encode())
        first = {
            "protocol_sha256": protocol_hash,
            "pass_index": 1,
            "block_index": index,
            "core_group_start": start,
            "core_group_stop": stop,
            "x23_state_sha256": old_x23,
            "x24_state_sha256": old_x24,
            "peak_process_rss_mib": 100.0,
            "wall_runtime_s": 1.0,
            "full_state_write_performed": False,
            "scan_chunks": [
                {
                    "group_start": start,
                    "group_stop": stop,
                    "g00": 1.0,
                    "g01": 0.8,
                    "g11": 0.65,
                    "difference_squared": 0.05,
                }
            ],
            "minimum_basis_intensities": [1.0, 1.0, 1.0],
            "candidate_positive_upper": 100.0,
            "mapped_positive_upper": 100.0,
            "mapped_block_sha256": mapped_hash,
            "x24_maximum_absolute_change": 1.0e-3,
            "x24_maximum_intensity_scale": 1.0,
            "x24_boundary_spectrum_l1_numerator": 5.0e-4,
            "x24_boundary_current_absolute_scale": 1.0,
            "x24_boundary_mapped_absolute_scale": 1.0,
            "x24_boundary_current_bolometric": 1.0,
            "x24_boundary_mapped_bolometric": 1.0004,
        }
        second = {
            "protocol_sha256": protocol_hash,
            "pass_index": 2,
            "block_index": index,
            "core_group_start": start,
            "core_group_stop": stop,
            "x23_state_sha256": old_x23,
            "x24_state_sha256": old_x24,
            "peak_process_rss_mib": 100.0,
            "wall_runtime_s": 1.0,
            "full_state_write_performed": False,
            "maximum_absolute_change": 5.0e-4,
            "maximum_intensity_scale": 1.0,
            "minimum_candidate_intensity": 1.0,
            "minimum_predicted_map_intensity": 1.0,
            "candidate_negative_count": 0,
            "predicted_map_negative_count": 0,
            "boundary_spectrum_l1_numerator": 2.5e-4,
            "candidate_boundary_absolute_scale": 1.0,
            "predicted_boundary_absolute_scale": 1.0,
            "candidate_boundary_bolometric": 1.0,
            "predicted_boundary_bolometric": 1.0002,
            "mapped_block_sha256": mapped_hash,
        }
        pass1_reports.append(first)
        pass2_reports.append(second)
        first_path = (
            f"outputs/checkpoints/prior_work/pass1_reports/pass1_block{index:02d}.json"
        )
        second_path = (
            f"outputs/checkpoints/prior_work/pass2_reports/pass2_block{index:02d}.json"
        )
        _write(root / first_path, first)
        _write(root / second_path, second)
        pass1_files.append(_report_claim(root, first_path, index))
        pass2_files.append(_report_claim(root, second_path, index))
    coefficient = streaming.aggregate_coefficient_statistics(pass1_reports)
    pass1 = {
        "protocol_sha256": protocol_hash,
        "status": "complete",
        "pass_index": 1,
        "x23_state_sha256": old_x23,
        "x24_state_sha256": old_x24,
        "full_state_write_performed": False,
        "reports": pass1_reports,
        "report_files": pass1_files,
        "active_blocks": [],
        "full_map_wall_runtime_s": 100.0,
        "aggregate": coefficient,
        "resource_gate_checks": {
            "worker_reports_pass": True,
            "full_map_wall_runtime_pass": True,
        },
    }
    _write(root / paths["pass1"], pass1)
    evaluation = streaming.aggregate_evaluation_statistics(
        pass2_reports, pass1_reports
    )
    checks = streaming.algebraic_gate_checks(protocol, coefficient, evaluation)
    checks.update(
        {
            "pass1_resources_pass": True,
            "pass2_resources_pass": True,
            "block_ownership_pass": True,
        }
    )
    assert all(checks.values())
    pass2 = {
        "protocol_sha256": protocol_hash,
        "status": "complete",
        "pass_index": 2,
        "x23_state_sha256": old_x23,
        "x24_state_sha256": old_x24,
        "full_state_write_performed": False,
        "reports": pass2_reports,
        "report_files": pass2_files,
        "active_blocks": [],
        "full_map_wall_runtime_s": 100.0,
        "coefficient_manifest_sha256": streaming._sha256(root / paths["pass1"]),
        "selected_forward_fraction": coefficient["selected_forward_fraction"],
        "aggregate": evaluation,
        "gate_checks": checks,
    }
    _write(root / paths["pass2"], pass2)
    candidate_hash = _hash_bytes(b"prior candidate")
    mapped_hash = _hash_bytes(b"prior fresh mapped")
    commit = {
        "phase": protocol["phase"],
        "protocol_sha256": protocol_hash,
        "status": "complete",
        "selected_forward_fraction": coefficient["selected_forward_fraction"],
        "algebraic_prediction": evaluation,
        "algebraic_gate_checks": checks,
        "original_x23_block_sha256": [
            _hash_bytes(f"original {index}".encode()) for index in range(76)
        ],
        "frozen_x24_block_sha256": [
            _hash_bytes(f"frozen {index}".encode()) for index in range(76)
        ],
        "completed_blocks": [
            {
                "block_index": index,
                "core_group_start": start,
                "core_group_stop": stop,
                "candidate_block_sha256": _hash_bytes(
                    f"candidate {index}".encode()
                ),
            }
            for index, (start, stop) in enumerate(_ranges())
        ],
        "active_block": None,
        "accumulated_write_wall_runtime_s": 1.0,
        "candidate_state_path": protocol["configuration"]["candidate_output_path"],
        "candidate_state_sha256": candidate_hash,
        "candidate_write_resources_pass": True,
        "fresh_original_operator_map_authorized": True,
        "prediction_used_as_fresh_residual": False,
    }
    _write(root / paths["commit"], commit)
    fresh_reports = [
        {
            "protocol_sha256": protocol_hash,
            "input_state_sha256": candidate_hash,
            "block_index": index,
            "core_group_start": start,
            "core_group_stop": stop,
            "maximum_absolute_radiation_change": 5.0e-4,
            "maximum_radiation_scale": 1.0,
            "boundary_spectrum_l1_numerator": 2.5e-4,
            "current_boundary_absolute_scale": 1.0,
            "mapped_boundary_absolute_scale": 1.0,
            "current_boundary_bolometric": 1.0,
            "mapped_boundary_bolometric": 1.0002,
            "minimum_input_intensity": 1.0,
            "minimum_mapped_intensity": 1.0,
            "peak_process_rss_mib": 100.0,
            "wall_runtime_s": 1.0,
            "output_block_sha256": _hash_bytes(f"fresh {index}".encode()),
        }
        for index, (start, stop) in enumerate(_ranges())
    ]
    fresh_checks = {
        "frequency_ownership_pass": True,
        "positive_map_pass": True,
        "resources_pass": True,
        "prediction_reproduction_pass": True,
    }
    fresh = {
        "phase": protocol["phase"],
        "protocol_sha256": protocol_hash,
        "status": "complete",
        "candidate_state_path": commit["candidate_state_path"],
        "candidate_state_sha256": candidate_hash,
        "output_state_path": protocol["configuration"]["fresh_map_output_path"],
        "completed_blocks": fresh_reports,
        "accumulated_wall_runtime_s": 100.0,
        "output_state_sha256": mapped_hash,
        "fresh_gate_checks": fresh_checks,
    }
    _write(root / paths["fresh"], fresh)
    metrics = repeat._fresh_metrics(fresh_reports)
    assert metrics["global_original_operator_residual"] == evaluation[
        "predicted_global_original_operator_residual"
    ]
    assert metrics["boundary_spectrum_l1"] == evaluation[
        "predicted_boundary_spectrum_l1"
    ]
    assert metrics["boundary_bolometric_fraction"] == evaluation[
        "predicted_boundary_bolometric_fraction"
    ]
    summary = {
        "phase": protocol["phase"],
        "classification": "[A]+[V]+[O]",
        "protocol_sha256": protocol_hash,
        "status": "complete",
        "candidate_state_path": commit["candidate_state_path"],
        "candidate_state_sha256": candidate_hash,
        "mapped_state_path": fresh["output_state_path"],
        "mapped_state_sha256": mapped_hash,
        "algebraic_prediction": evaluation,
        "fresh_input_global_original_operator_residual": metrics[
            "global_original_operator_residual"
        ],
        "fresh_input_boundary_spectrum_l1": metrics["boundary_spectrum_l1"],
        "fresh_input_boundary_bolometric_fraction": metrics[
            "boundary_bolometric_fraction"
        ],
        "maximum_process_peak_rss_mib": metrics[
            "maximum_process_peak_rss_mib"
        ],
        "maximum_worker_wall_runtime_s": metrics[
            "maximum_worker_wall_runtime_s"
        ],
        "full_map_wall_runtime_s": fresh["accumulated_wall_runtime_s"],
        "gate_checks": fresh_checks,
        "decision": {
            "fresh_original_operator_map_completed": True,
            "prediction_used_as_fresh_residual": False,
            "fresh_residual_measured_from_candidate_map": True,
            "material_feedback_authorized": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    _write(root / paths["summary"], summary)
    return paths


def _spec(paths: dict[str, str]) -> repeat.RepeatStreamingCycleSpec:
    return repeat.RepeatStreamingCycleSpec(
        phase="7B9dn test repeat cycle",
        phase_index=1434,
        classification="[A]+[V]+[O]",
        prior_protocol_path=paths["protocol"],
        prior_pass1_manifest_path=paths["pass1"],
        prior_pass2_manifest_path=paths["pass2"],
        prior_candidate_commit_manifest_path=paths["commit"],
        prior_fresh_manifest_path=paths["fresh"],
        prior_fresh_summary_path=paths["summary"],
        coefficient_report_directory="outputs/checkpoints/next/pass1_reports",
        evaluation_report_directory="outputs/checkpoints/next/pass2_reports",
        coefficient_manifest_path="outputs/checkpoints/next/pass1.json",
        evaluation_manifest_path="outputs/checkpoints/next/pass2.json",
        candidate_summary_path="outputs/next_candidate.json",
        candidate_figure_path="outputs/next_candidate.png",
    )


def test_builder_rotates_prior_candidate_and_mapped_buffers(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    payload = repeat.build_repeat_streaming_protocol(tmp_path, _spec(paths))
    prior_summary = json.loads((tmp_path / paths["summary"]).read_text())
    cfg = payload["configuration"]
    assert cfg["x23_state_path"] == prior_summary["candidate_state_path"]
    assert cfg["x23_state_sha256"] == prior_summary["candidate_state_sha256"]
    assert cfg["x24_state_path"] == prior_summary["mapped_state_path"]
    assert cfg["x24_state_sha256"] == prior_summary["mapped_state_sha256"]
    assert cfg["x23_global_original_operator_residual"] == prior_summary[
        "fresh_input_global_original_operator_residual"
    ]
    assert cfg["candidate_output_path"] == cfg["x23_state_path"]
    assert cfg["fresh_map_output_path"] == cfg["x24_state_path"]
    assert payload["execution_plan"]["additional_full_state_count"] == 0
    assert payload["execution_plan"]["dry_maps_count_as_fresh_residuals"] is False
    assert cfg["maximum_concurrent_processes"] == 2
    assert payload["fresh_map_gates"]["full_map_wall_time_strictly_below_s"] == 1800.0
    assert all(
        not source["path"].endswith(".dat")
        for source in payload["sources"].values()
    )


def test_builder_pins_all_six_prior_artifacts_and_remains_consumable(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    payload = repeat.build_repeat_streaming_protocol(tmp_path, _spec(paths))
    expected = {
        "prior_streaming_protocol": paths["protocol"],
        "prior_pass1_manifest": paths["pass1"],
        "prior_pass2_manifest": paths["pass2"],
        "prior_candidate_commit_manifest": paths["commit"],
        "prior_fresh_manifest": paths["fresh"],
        "prior_fresh_summary": paths["summary"],
    }
    for key, relative in expected.items():
        assert payload["sources"][key] == _source(tmp_path, relative)
    assert payload["sources"]["repeat_cycle_preregister_builder"] == _source(
        tmp_path, repeat.BUILDER_RELATIVE_PATH
    )
    protocol_path = tmp_path / "outputs/next_protocol.json"
    _write(protocol_path, payload)
    digest = streaming._sha256(protocol_path)
    assert dry_parent._load_protocol(tmp_path, protocol_path, digest) == payload
    assert orchestrator._load_protocol(tmp_path, protocol_path, digest) == payload


def test_cli_writes_only_the_new_small_protocol(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    output = "outputs/phase7b9dn_protocol.json"
    digest = repeat.main(
        [
            "--prior-protocol",
            paths["protocol"],
            "--prior-pass1-manifest",
            paths["pass1"],
            "--prior-pass2-manifest",
            paths["pass2"],
            "--prior-candidate-commit-manifest",
            paths["commit"],
            "--prior-fresh-manifest",
            paths["fresh"],
            "--prior-fresh-summary",
            paths["summary"],
            "--protocol-output",
            output,
            "--phase-index",
            "1434",
        ],
        root=tmp_path,
    )
    assert digest == streaming._sha256(tmp_path / output)
    assert not (tmp_path / f"{output}.tmp").exists()
    assert not list((tmp_path / "outputs/checkpoints").rglob("*next*"))


def test_builder_rejects_dry_reproducibility_or_algebraic_gate_failure(
    tmp_path: Path,
) -> None:
    for mode in ("mapped_sha", "algebraic"):
        root = tmp_path / mode
        paths = _fixture(root)
        path = root / paths["pass2"]
        manifest = json.loads(path.read_text())
        if mode == "mapped_sha":
            manifest["reports"][34]["mapped_block_sha256"] = "f" * 64
            report_claim = manifest["report_files"][34]
            report_path = root / report_claim["path"]
            _write(report_path, manifest["reports"][34])
            manifest["report_files"][34] = _report_claim(
                root, report_claim["path"], 34
            )
        else:
            manifest["gate_checks"]["boundary_improvement_pass"] = False
        _write(path, manifest)
        with pytest.raises(RuntimeError, match="reproducible|algebraic gate"):
            repeat.build_repeat_streaming_protocol(root, _spec(paths))


def test_builder_rejects_incomplete_commit_or_broken_fresh_lineage(
    tmp_path: Path,
) -> None:
    for mode in ("commit", "lineage", "prediction_flag"):
        root = tmp_path / mode
        paths = _fixture(root)
        if mode == "commit":
            path = root / paths["commit"]
            payload = json.loads(path.read_text())
            payload["completed_blocks"].pop()
        elif mode == "lineage":
            path = root / paths["fresh"]
            payload = json.loads(path.read_text())
            payload["candidate_state_sha256"] = "e" * 64
        else:
            path = root / paths["summary"]
            payload = json.loads(path.read_text())
            payload["decision"]["prediction_used_as_fresh_residual"] = True
        _write(path, payload)
        with pytest.raises(RuntimeError, match="candidate|fresh"):
            repeat.build_repeat_streaming_protocol(root, _spec(paths))


def test_builder_rejects_source_pin_change_collision_and_dat_source(
    tmp_path: Path,
) -> None:
    changed = tmp_path / "changed"
    paths = _fixture(changed)
    _write(changed / streaming.RUNNER_RELATIVE_PATH, b"changed worker")
    with pytest.raises(RuntimeError, match="source changed"):
        repeat.build_repeat_streaming_protocol(changed, _spec(paths))

    collision = tmp_path / "collision"
    paths = _fixture(collision, source_collision=True)
    with pytest.raises(RuntimeError, match="source-key collision"):
        repeat.build_repeat_streaming_protocol(collision, _spec(paths))

    forbidden = tmp_path / "dat"
    paths = _fixture(forbidden, dat_source=True)
    with pytest.raises(RuntimeError, match=r"\.dat source"):
        repeat.build_repeat_streaming_protocol(forbidden, _spec(paths))


def test_cli_rejects_dat_artifact_without_opening_it(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="JSON under outputs"):
        repeat.preregister(
            tmp_path,
            prior_protocol_path="outputs/missing.dat",
            prior_pass1_manifest_path="outputs/missing.json",
            prior_pass2_manifest_path="outputs/missing.json",
            prior_candidate_commit_manifest_path="outputs/missing.json",
            prior_fresh_manifest_path="outputs/missing.json",
            prior_fresh_summary_path="outputs/missing.json",
            protocol_output_path="outputs/new.json",
            phase_index=1434,
            phase="test",
            classification="test",
        )
