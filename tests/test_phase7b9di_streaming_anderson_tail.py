"""Streaming Anderson(1) builder and block algebra on tiny arrays/files only."""

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

from scripts import phase7b9di_streaming_anderson_tail as streaming
from scripts import phase7b9di_preregister_streaming_anderson_tail as preregister


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _source(root: Path, relative: str) -> dict[str, object]:
    data = (root / relative).read_bytes()
    return {"path": relative, "size_bytes": len(data), "sha256": _sha_bytes(data)}


def _fixture(root: Path) -> streaming.StreamingAndersonTailSpec:
    _write(root / streaming.RUNNER_RELATIVE_PATH, b"stream worker")
    _write(root / streaming.ORCHESTRATOR_RELATIVE_PATH, b"stream orchestrator")
    _write(root / streaming.PREREGISTER_BUILDER_RELATIVE_PATH, b"preregister")
    _write(root / streaming.DRY_PASS_PARENT_RELATIVE_PATH, b"dry pass parent")
    _write(root / "outputs/fixed.json", b"fixed")
    _write(root / "outputs/material.npz", b"material")
    sources = {
        "finite_trial_protocol": _source(root, "outputs/fixed.json"),
        "finite_trial_material": _source(root, "outputs/material.npz"),
        "phase7b5p_master_input": _source(root, "outputs/material.npz"),
    }
    gates = {
        "block_count_exactly": 76,
        "owned_frequency_group_count_exactly": 9632,
        "minimum_input_and_mapped_intensity_at_least": 0.0,
        "global_original_operator_residual_below": 1.0e-4,
        "subsequent_residual_contraction_ratio_below": 1.01,
        "global_boundary_spectrum_l1_below": 1.0e-3,
        "global_boundary_bolometric_fraction_below": 1.0e-3,
        "each_process_peak_rss_strictly_below_mib": 6144.0,
        "each_worker_wall_time_strictly_below_s": 60.0,
        "each_full_map_wall_time_strictly_below_s": 1800.0,
    }
    protocol = {
        "phase": "di",
        "sources": sources,
        "configuration": {
            "maximum_picard_maps": 24,
            "maximum_concurrent_processes": 2,
            "raw_float64_checkpoint_size_bytes": 10_099_884_032,
            "diagnostic_fixed_iteration_count": 1,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "source_map_only": True,
        },
        "gates": gates,
    }
    protocol_path = "outputs/di_protocol.json"
    _write(root / protocol_path, protocol)
    protocol_sha = _sha_bytes((root / protocol_path).read_bytes())
    paths = [
        "outputs/checkpoints/a.dat" if index % 2 == 0 else "outputs/checkpoints/b.dat"
        for index in range(25)
    ]
    hashes = [_sha_bytes(f"state-{index}".encode()) for index in range(25)]
    records = []
    for index in range(24):
        records.append(
            {
                "iteration": index,
                "input_state_path": paths[index],
                "input_state_sha256": hashes[index],
                "mapped_state_path": paths[index + 1],
                "mapped_state_sha256": hashes[index + 1],
                "global_original_operator_residual": 0.01 / (index + 1),
                "boundary_spectrum_l1": 5.0e-4,
                "boundary_bolometric_fraction": 4.0e-4,
                "progression_gate_checks": {
                    "frequency_ownership_pass": True,
                    "positive_map_pass": True,
                    "contraction_pass": True,
                    "resources_pass": True,
                },
                "progression_passed": True,
                "convergence_passed": False,
                "map_passed": False,
            }
        )
    manifest_path = "outputs/checkpoints/di/manifest.json"
    summary_path = "outputs/di_summary.json"
    manifest = {
        "protocol_sha256": protocol_sha,
        "status": "maximum_maps_exhausted",
        "iterations": records,
    }
    summary = {
        "protocol_sha256": protocol_sha,
        "status": "maximum_maps_exhausted",
        "completed_picard_maps": 24,
        "iterations": records,
        "decision": {
            "positive_picard_sequence_converged": False,
            "material_feedback_authorized": False,
            "dynamic_nlte_solution_accepted": False,
        },
    }
    _write(root / manifest_path, manifest)
    _write(root / summary_path, summary)
    return streaming.StreamingAndersonTailSpec(
        phase="streaming tail",
        phase_index=1500,
        classification="[A-preregistered]+[V]+[O]",
        di_protocol_path=protocol_path,
        di_manifest_path=manifest_path,
        di_summary_path=summary_path,
        worker_path=streaming.RUNNER_RELATIVE_PATH,
        coefficient_report_directory="outputs/checkpoints/stream/pass1",
        evaluation_report_directory="outputs/checkpoints/stream/pass2",
        coefficient_manifest_path="outputs/checkpoints/stream/coefficient.json",
        evaluation_manifest_path="outputs/checkpoints/stream/evaluation.json",
        candidate_summary_path="outputs/stream_summary.json",
        candidate_figure_path="outputs/stream.png",
    )


def test_builder_never_needs_existing_dat_and_reuses_two_buffers(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    payload = streaming.build_streaming_anderson_tail_protocol(tmp_path, spec)
    assert payload["sources"]["exhausted_tail_protocol"] == _source(
        tmp_path, spec.di_protocol_path
    )
    assert payload["sources"]["exhausted_tail_manifest"] == _source(
        tmp_path, spec.di_manifest_path
    )
    assert payload["sources"]["exhausted_tail_summary"] == _source(
        tmp_path, spec.di_summary_path
    )
    claims = payload["full_state_claims"]
    assert claims["x23_retained_until_all_algebraic_gates_pass"]["path"].endswith(
        "b.dat"
    )
    assert claims["x24_retained_through_both_dry_maps"]["path"].endswith("a.dat")
    assert all(
        not source["path"].endswith(".dat")
        for source in payload["sources"].values()
    )
    assert payload["execution_plan"]["additional_full_state_count"] == 0


def test_builder_records_exact_cost_and_dry_maps_are_not_residuals(
    tmp_path: Path,
) -> None:
    payload = streaming.build_streaming_anderson_tail_protocol(
        tmp_path, _fixture(tmp_path)
    )
    plan = payload["execution_plan"]
    assert plan["transport_equivalent_full_map_count"] == 3
    assert plan["dry_map_count"] == 2
    assert plan["fresh_residual_map_count"] == 1
    assert plan["dry_maps_count_as_fresh_residuals"] is False
    assert payload["authorization"]["pass1_may_write_full_state"] is False
    assert payload["authorization"]["pass2_may_write_full_state"] is False


def test_builder_keeps_96_fraction_prediction_and_resource_gates(
    tmp_path: Path,
) -> None:
    payload = streaming.build_streaming_anderson_tail_protocol(
        tmp_path, _fixture(tmp_path)
    )
    cfg = payload["configuration"]
    gates = payload["algebraic_gates"]
    assert cfg["maximum_forward_picard_fraction"] == 96.0
    assert gates["predicted_global_residual_ratio_to_x10_below"] == 0.99
    assert gates["minimum_candidate_and_predicted_map_intensity_at_least"] == 0.0
    assert gates["predicted_boundary_spectrum_ratio_to_x24_below"] == 1.0
    assert gates["predicted_boundary_bolometric_ratio_to_x24_below"] == 1.0
    assert payload["fresh_map_gates"]["full_map_wall_time_strictly_below_s"] == 1800.0
    assert payload["authorization"]["fresh_map_maximum_concurrent_processes"] == 2
    assert gates["each_dry_full_map_wall_time_strictly_below_s"] == 1800.0
    assert payload["authorization"]["each_dry_map_maximum_concurrent_processes"] == 2
    assert payload["authorization"]["fresh_full_original_operator_map_required"]


def test_builder_rejects_any_failed_progression_or_nonexhausted_status(
    tmp_path: Path,
) -> None:
    for case in ("progression", "status"):
        root = tmp_path / case
        spec = _fixture(root)
        manifest_path = root / spec.di_manifest_path
        summary_path = root / spec.di_summary_path
        manifest = json.loads(manifest_path.read_text())
        summary = json.loads(summary_path.read_text())
        if case == "progression":
            manifest["iterations"][-1]["progression_passed"] = False
            summary["iterations"] = manifest["iterations"]
        else:
            manifest["status"] = "running"
            summary["status"] = "running"
        _write(manifest_path, manifest)
        _write(summary_path, summary)
        with pytest.raises(RuntimeError):
            streaming.build_streaming_anderson_tail_protocol(root, spec)


def test_chunk_sums_recover_frozen_global_coefficient_formula() -> None:
    rng = np.random.default_rng(20260902)
    x23 = rng.uniform(0.5, 2.0, size=(32, 3, 5))
    x24 = x23 + rng.normal(0.01, 0.03, size=x23.shape)
    x25 = x24 + rng.normal(0.008, 0.025, size=x23.shape)
    reports = []
    for block, start in enumerate((0, 16)):
        row = streaming.coefficient_block_statistics(
            x23[start : start + 16],
            x24[start : start + 16],
            x25[start : start + 16],
            global_group_start=start,
        )
        row.update(
            {
                "block_index": block,
                "core_group_start": start,
                "core_group_stop": start + 16,
            }
        )
        reports.append(row)
    combined = streaming.aggregate_coefficient_statistics(reports)
    f0 = x24 - x23
    f1 = x25 - x24
    delta = f1 - f0
    g00 = g01 = g11 = difference = 0.0
    for start in range(0, 32, 16):
        stop = start + 16
        g00 += float(np.sum(f0[start:stop] * f0[start:stop], dtype=np.float64))
        g01 += float(np.sum(f0[start:stop] * f1[start:stop], dtype=np.float64))
        g11 += float(np.sum(f1[start:stop] * f1[start:stop], dtype=np.float64))
        difference += float(
            np.sum(delta[start:stop] * delta[start:stop], dtype=np.float64)
        )
    assert combined["gram"] == [[g00, g01], [g01, g11]]
    assert combined["difference_squared"] == difference
    assert combined["raw_forward_fraction"] == -(g01 - g00) / difference


def test_x24_x25_alone_cannot_reconstruct_frozen_candidate() -> None:
    x24 = np.asarray([[[2.0]]])
    x25 = np.asarray([[[2.2]]])
    selected = 3.0
    candidate_a = x24 + (selected - 1.0) * (x24 - np.asarray([[[1.0]]]))
    candidate_b = x24 + (selected - 1.0) * (x24 - np.asarray([[[1.5]]]))
    assert not np.array_equal(candidate_a, candidate_b)
    # x24、x25 完全相同但候选不同，故覆写 x23 后无法保持旧算法。


def test_two_pass_block_hash_and_metrics_match_direct_evaluation() -> None:
    rng = np.random.default_rng(7)
    x23 = rng.uniform(1.0, 2.0, size=(2, 4, 3))
    x24 = x23 + 0.02
    x25 = x24 + 0.015
    mu = np.asarray([-0.8, -0.2, 0.2, 0.8])
    weight = np.asarray([0.25, 0.25, 0.25, 0.25])
    width = np.asarray([1.0, 1.5])
    selected = 2.0
    pass1 = streaming.coefficient_block_statistics(
        x23, x24, x25, global_group_start=0
    )
    pass1.update({"block_index": 0, "core_group_start": 0, "core_group_stop": 2})
    pass2 = streaming.evaluation_block_statistics(
        x23, x24, x25, selected, mu, weight, width
    )
    pass2.update({"block_index": 0, "core_group_start": 0, "core_group_stop": 2})
    # Production aggregate requires all 76 blocks; duplicate disjoint metadata only.
    first_reports = []
    second_reports = []
    for index in range(76):
        first = dict(pass1)
        second = dict(pass2)
        first.update(
            {"block_index": index, "core_group_start": index, "core_group_stop": index + 1}
        )
        second.update(
            {"block_index": index, "core_group_start": index, "core_group_stop": index + 1}
        )
        first_reports.append(first)
        second_reports.append(second)
    aggregate = streaming.aggregate_evaluation_statistics(
        second_reports, first_reports
    )
    candidate = x24 + (selected - 1.0) * (x24 - x23)
    predicted = x25 + (selected - 1.0) * (x25 - x24)
    expected = np.max(np.abs(predicted - candidate)) / max(
        np.max(np.abs(candidate)), np.max(np.abs(predicted))
    )
    assert aggregate["predicted_global_original_operator_residual"] == expected
    assert aggregate["pass1_pass2_block_sha256_match"] is True


def test_pass1_pass2_mapped_hash_mismatch_is_fail_closed() -> None:
    base = {
        "core_group_start": 0,
        "core_group_stop": 1,
        "mapped_block_sha256": "a" * 64,
    }
    first = []
    second = []
    for index in range(76):
        one = dict(base, block_index=index, core_group_start=index, core_group_stop=index + 1)
        two = dict(one)
        two.update(
            {
                "maximum_absolute_change": 1.0,
                "maximum_intensity_scale": 2.0,
                "minimum_candidate_intensity": 0.0,
                "minimum_predicted_map_intensity": 0.0,
                "candidate_negative_count": 0,
                "predicted_map_negative_count": 0,
                "boundary_spectrum_l1_numerator": 1.0,
                "candidate_boundary_absolute_scale": 2.0,
                "predicted_boundary_absolute_scale": 2.0,
                "candidate_boundary_bolometric": 2.0,
                "predicted_boundary_bolometric": 2.0,
            }
        )
        first.append(one)
        second.append(two)
    second[-1]["mapped_block_sha256"] = "b" * 64
    with pytest.raises(RuntimeError, match="not blockwise reproducible"):
        streaming.aggregate_evaluation_statistics(second, first)


def test_boundary_must_improve_not_only_be_below_absolute_gate() -> None:
    protocol = {
        "algebraic_gates": {
            **streaming.frozen.protected_anderson_tail_gates(),
            "predicted_boundary_spectrum_ratio_to_x24_below": 1.0,
            "predicted_boundary_bolometric_ratio_to_x24_below": 1.0,
        }
    }
    coefficient = {
        "minimum_basis_intensities": [1.0, 1.0, 1.0],
        "difference_ratio": 0.1,
        "selected_forward_fraction": 2.0,
        "x24_global_original_operator_residual": 2.0e-4,
        "x24_boundary_spectrum_l1": 5.0e-4,
        "x24_boundary_bolometric_fraction": 4.0e-4,
    }
    evaluation = {
        "predicted_global_original_operator_residual": 1.0e-4,
        "predicted_boundary_spectrum_l1": 6.0e-4,
        "predicted_boundary_bolometric_fraction": 3.0e-4,
        "minimum_candidate_intensity": 0.0,
        "minimum_predicted_map_intensity": 0.0,
        "candidate_negative_count": 0,
        "predicted_map_negative_count": 0,
        "pass1_pass2_block_sha256_match": True,
    }
    checks = streaming.algebraic_gate_checks(protocol, coefficient, evaluation)
    assert checks["boundary_absolute_pass"] is True
    assert checks["boundary_improvement_pass"] is False


def test_worker_source_contains_no_full_state_write_or_repair_call() -> None:
    source = Path(streaming.__file__).read_text(encoding="utf-8")
    forbidden = ("mode=\"r+\"", "np.clip(", "nan_to_num(", "renormalize(")
    assert all(token not in source for token in forbidden)


def test_one_click_preregistration_pins_all_small_executables(
    tmp_path: Path,
) -> None:
    spec = _fixture(tmp_path)
    output = "outputs/future_streaming_protocol.json"
    digest = preregister.main(
        [
            "--di-protocol",
            spec.di_protocol_path,
            "--di-manifest",
            spec.di_manifest_path,
            "--di-summary",
            spec.di_summary_path,
            "--protocol-output",
            output,
            "--phase-index",
            "1501",
        ],
        root=tmp_path,
    )
    path = tmp_path / output
    payload = json.loads(path.read_text())
    assert digest == streaming._sha256(path)
    assert {
        "streaming_anderson_dry_pass_parent",
        "streaming_anderson_preregister_builder",
        "streaming_anderson_worker",
        "streaming_anderson_orchestrator",
    } <= set(payload["sources"])
    parent = payload["sources"]["streaming_anderson_dry_pass_parent"]
    assert parent == _source(tmp_path, streaming.DRY_PASS_PARENT_RELATIVE_PATH)
    assert payload["configuration"]["dry_pass_parent_path"] == (
        streaming.DRY_PASS_PARENT_RELATIVE_PATH
    )
    assert all(
        not source["path"].endswith(".dat")
        for source in payload["sources"].values()
    )
    assert set(payload["full_state_claims"]) == {
        "x23_retained_until_all_algebraic_gates_pass",
        "x24_retained_through_both_dry_maps",
    }
    assert payload["configuration"]["maximum_concurrent_processes"] == 2
    assert payload["fresh_map_gates"]["full_map_wall_time_strictly_below_s"] == 1800.0
    assert payload["execution_plan"]["dry_map_count"] == 2
    assert payload["execution_plan"]["fresh_residual_map_count"] == 1
    assert payload["execution_plan"]["candidate_algebraic_full_state_write_count"] == 1


def test_builder_rejects_inherited_source_key_collision(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    protocol_path = tmp_path / spec.di_protocol_path
    manifest_path = tmp_path / spec.di_manifest_path
    summary_path = tmp_path / spec.di_summary_path
    _write(tmp_path / "outputs/collision.json", b"collision")
    protocol = json.loads(protocol_path.read_text())
    protocol["sources"]["exhausted_tail_protocol"] = _source(
        tmp_path, "outputs/collision.json"
    )
    _write(protocol_path, protocol)
    protocol_sha = _sha_bytes(protocol_path.read_bytes())
    manifest = json.loads(manifest_path.read_text())
    summary = json.loads(summary_path.read_text())
    manifest["protocol_sha256"] = protocol_sha
    summary["protocol_sha256"] = protocol_sha
    _write(manifest_path, manifest)
    _write(summary_path, summary)
    with pytest.raises(RuntimeError, match="source-key collision"):
        streaming.build_streaming_anderson_tail_protocol(tmp_path, spec)


@pytest.mark.parametrize("case", ["status", "progression", "lineage", "converged"])
def test_one_click_preregistration_is_fail_closed_and_writes_nothing(
    tmp_path: Path, case: str
) -> None:
    root = tmp_path / case
    spec = _fixture(root)
    manifest_path = root / spec.di_manifest_path
    summary_path = root / spec.di_summary_path
    manifest = json.loads(manifest_path.read_text())
    summary = json.loads(summary_path.read_text())
    if case == "status":
        manifest["status"] = "running"
        summary["status"] = "running"
    elif case == "progression":
        manifest["iterations"][-1]["progression_passed"] = False
        summary["iterations"] = manifest["iterations"]
    elif case == "lineage":
        manifest["iterations"][-1]["input_state_sha256"] = "broken"
        summary["iterations"] = manifest["iterations"]
    else:
        summary["decision"]["positive_picard_sequence_converged"] = True
    _write(manifest_path, manifest)
    _write(summary_path, summary)
    output = root / "outputs/should_not_exist.json"
    with pytest.raises(RuntimeError):
        preregister.main(
            [
                "--di-protocol",
                spec.di_protocol_path,
                "--di-manifest",
                spec.di_manifest_path,
                "--di-summary",
                spec.di_summary_path,
                "--protocol-output",
                "outputs/should_not_exist.json",
                "--phase-index",
                "1501",
            ],
            root=root,
        )
    assert not output.exists()


def test_preregistration_refuses_protocol_inside_checkpoint_tree(
    tmp_path: Path,
) -> None:
    spec = _fixture(tmp_path)
    with pytest.raises(ValueError, match="must not be written"):
        preregister.main(
            [
                "--di-protocol",
                spec.di_protocol_path,
                "--di-manifest",
                spec.di_manifest_path,
                "--di-summary",
                spec.di_summary_path,
                "--protocol-output",
                "outputs/checkpoints/bad.json",
                "--phase-index",
                "1501",
            ],
            root=tmp_path,
        )
