"""Phase 7B9 耗尽序列末端三段冻结协议的纯小文件回归。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/phase7b9_protocol_builders.py"
SPEC = importlib.util.spec_from_file_location("phase7b9_protocol_builders_tail", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load Phase 7B9 protocol builders")
builders = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builders
SPEC.loader.exec_module(builders)


def write_bytes(root: Path, relative_path: str, content: bytes) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def write_json(root: Path, relative_path: str, payload: dict[str, object]) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_sources(root: Path) -> None:
    paths = (
        builders.FINITE_TRIAL_PROTOCOL,
        builders.FINITE_TRIAL_MATERIAL,
        builders.MASTER_INPUT,
        builders.GENERIC_MAP_RUNNER,
        builders.POSITIVE_SEQUENCE_ENGINE,
        builders.SEEDED_PICARD_RUNNER,
        builders.MAP_WORKER,
        builders.WORKER_HELPERS,
        builders.MIXED_FRAME_OPERATOR,
        builders.MIXED_FRAME_FREQUENCY,
        builders.CHECKPOINT_COPY_RUNNER,
        builders.NEW_CHECKPOINT_COPY_RUNNER,
        builders.SLOW_MODE_RUNNER,
        builders.SLOW_MODE_PROTOCOL_BUILDER,
        builders.RADIATIVE_TRANSFER_QUADRATURE,
    )
    for index, path in enumerate(paths):
        write_bytes(root, path, f"source-{index}".encode())


def unconverged_sequence_fixture(root: Path) -> tuple[str, str, str]:
    write_sources(root)
    paths = [
        "outputs/checkpoints/seed.dat",
        "outputs/checkpoints/state1.dat",
        "outputs/checkpoints/state2.dat",
        "outputs/checkpoints/tail.dat",
    ]
    contents = [b"seed0000", b"state001", b"state002", b"tail0003"]
    for path, content in zip(paths, contents, strict=True):
        write_bytes(root, path, content)
    protocol_path = "outputs/source_sequence_protocol.json"
    write_json(
        root,
        protocol_path,
        {"configuration": {"maximum_picard_maps": 3}},
    )
    iterations: list[dict[str, object]] = []
    residuals = (1.8e-4, 1.6e-4, 1.5e-4)
    for index in range(3):
        iterations.append(
            {
                "iteration": index,
                "input_state_path": paths[index],
                "input_state_sha256": builders.sha256(root / paths[index]),
                "mapped_state_path": paths[index + 1],
                "mapped_state_sha256": builders.sha256(root / paths[index + 1]),
                "global_original_operator_residual": residuals[index],
                "boundary_spectrum_l1": 8.0e-5,
                "boundary_bolometric_fraction": 7.0e-5,
                "map_passed": True,
            }
        )
    summary_path = "outputs/source_sequence_summary.json"
    write_json(
        root,
        summary_path,
        {
            "status": "maximum_maps_exhausted",
            "completed_picard_maps": 3,
            "protocol_sha256": builders.sha256(root / protocol_path),
            "iterations": iterations,
            "decision": {
                "positive_picard_sequence_converged": False,
                "audited_radiation_state_accepted": False,
                "material_feedback_authorized": False,
                "dynamic_nlte_solution_accepted": False,
            },
        },
    )
    return summary_path, protocol_path, paths[-1]


def prepare_anchor(
    root: Path,
) -> tuple[str, str, str, str, str, str]:
    sequence_summary, sequence_protocol, tail_path = unconverged_sequence_fixture(root)
    target_path = "outputs/checkpoints/tail_anchor.dat"
    protocol_path = "outputs/tail_anchor_protocol.json"
    summary_path = "outputs/tail_anchor_summary.json"
    decision_key = "tail_two_map_picard_authorized"
    spec = builders.SequenceTailAnchorProtocolSpec(
        phase="test tail anchor",
        phase_index=1600,
        classification="[A-preregistered] byte-identical APFS tail anchor",
        sequence_summary_path=sequence_summary,
        sequence_protocol_path=sequence_protocol,
        target_state_path=target_path,
        summary_path=summary_path,
        postcopy_authorization_key=decision_key,
    )
    payload = builders.build_sequence_tail_anchor_protocol(root, spec)
    protocol_sha = builders.freeze_protocol(root, protocol_path, payload)
    # 在 tmp_path 中模拟 copy runner 的成功结果，不执行真实检查点操作。
    write_bytes(root, target_path, (root / tail_path).read_bytes())
    write_json(
        root,
        summary_path,
        {
            "protocol_sha256": protocol_sha,
            "source_state_path": tail_path,
            "source_state_sha256": builders.sha256(root / tail_path),
            "anchor_state_path": target_path,
            "anchor_state_sha256": builders.sha256(root / target_path),
            "decision": {
                decision_key: True,
                "material_feedback_authorized": False,
            },
        },
    )
    return (
        sequence_summary,
        sequence_protocol,
        tail_path,
        summary_path,
        protocol_path,
        decision_key,
    )


def prepare_two_map_continuation(
    root: Path,
) -> tuple[builders.ProtectedAndersonTailProtocolSpec, dict[str, object]]:
    (
        sequence_summary,
        sequence_protocol,
        tail_path,
        anchor_summary,
        anchor_protocol,
        decision_key,
    ) = prepare_anchor(root)
    scratch_path = "outputs/checkpoints/tail_scratch.dat"
    write_bytes(root, scratch_path, b"scratch0")
    continuation_protocol_path = "outputs/tail_two_map_protocol.json"
    continuation_summary_path = "outputs/tail_two_map_summary.json"
    continuation_spec = builders.TailTwoMapPicardProtocolSpec(
        phase="test two-map tail continuation",
        phase_index=1601,
        classification="[A-preregistered] exactly two pure Picard tail maps",
        sequence_summary_path=sequence_summary,
        sequence_protocol_path=sequence_protocol,
        anchor_summary_path=anchor_summary,
        anchor_protocol_path=anchor_protocol,
        anchor_continuation_decision_key=decision_key,
        scratch_state_path=scratch_path,
        manifest_path="outputs/checkpoints/tail_two/manifest.json",
        report_directory="outputs/checkpoints/tail_two/reports",
        summary_path=continuation_summary_path,
        figure_path="outputs/tail_two_map.png",
        runner_path="scripts/tail_two_map.py",
        tail_anderson_authorization_key="protected_tail_anderson_authorized",
    )
    continuation = builders.build_tail_two_map_picard_protocol(
        root, continuation_spec
    )
    continuation_sha = builders.freeze_protocol(
        root, continuation_protocol_path, continuation
    )

    source = json.loads((root / sequence_summary).read_text())
    iterations = source["iterations"]
    x10_path = "outputs/checkpoints/tail_x10.dat"
    x11_path = "outputs/checkpoints/tail_x11.dat"
    write_bytes(root, x10_path, b"tailx010")
    write_bytes(root, x11_path, b"tailx011")
    iterations.extend(
        [
            {
                "iteration": 3,
                "input_state_path": tail_path,
                "input_state_sha256": builders.sha256(root / tail_path),
                "mapped_state_path": x10_path,
                "mapped_state_sha256": builders.sha256(root / x10_path),
                "global_original_operator_residual": 1.45e-4,
                "boundary_spectrum_l1": 7.0e-5,
                "boundary_bolometric_fraction": 6.0e-5,
                "map_passed": True,
            },
            {
                "iteration": 4,
                "input_state_path": x10_path,
                "input_state_sha256": builders.sha256(root / x10_path),
                "mapped_state_path": x11_path,
                "mapped_state_sha256": builders.sha256(root / x11_path),
                "global_original_operator_residual": 1.41e-4,
                "boundary_spectrum_l1": 6.0e-5,
                "boundary_bolometric_fraction": 5.0e-5,
                "map_passed": True,
            },
        ]
    )
    write_json(
        root,
        continuation_summary_path,
        {
            "status": "maximum_maps_exhausted",
            "completed_picard_maps": 5,
            "protocol_sha256": continuation_sha,
            "iterations": iterations,
            "decision": {
                "positive_picard_sequence_converged": False,
                "audited_radiation_state_accepted": False,
                "material_feedback_authorized": False,
                "dynamic_nlte_solution_accepted": False,
            },
        },
    )
    candidate_path = "outputs/checkpoints/tail_anderson_candidate.dat"
    write_bytes(root, candidate_path, b"cand0000")
    anderson_spec = builders.ProtectedAndersonTailProtocolSpec(
        phase="test protected Anderson tail",
        phase_index=1602,
        classification="[A-preregistered] protected Anderson(1) tail",
        continuation_summary_path=continuation_summary_path,
        continuation_protocol_path=continuation_protocol_path,
        anchor_summary_path=anchor_summary,
        anchor_protocol_path=anchor_protocol,
        anchor_continuation_decision_key=decision_key,
        candidate_output_path=candidate_path,
        summary_path="outputs/tail_anderson_summary.json",
        figure_path="outputs/tail_anderson.png",
    )
    return anderson_spec, continuation


def test_sequence_tail_anchor_uses_last_mapped_state_and_protocol_hash(
    tmp_path: Path,
) -> None:
    sequence_summary, sequence_protocol, tail_path = unconverged_sequence_fixture(
        tmp_path
    )
    target_path = "outputs/checkpoints/anchor.dat"
    write_bytes(tmp_path, target_path, b"old00000")
    spec = builders.SequenceTailAnchorProtocolSpec(
        phase="test",
        phase_index=1,
        classification="test",
        sequence_summary_path=sequence_summary,
        sequence_protocol_path=sequence_protocol,
        target_state_path=target_path,
        summary_path="outputs/anchor_summary.json",
        postcopy_authorization_key="continue_two_maps",
    )
    payload = builders.build_sequence_tail_anchor_protocol(tmp_path, spec)
    configuration = payload["configuration"]
    assert configuration["copy_strategy"] == "apfs_clone_then_sha256_verify"
    assert configuration["source_state_path"] == tail_path
    assert configuration["source_state_sha256"] == builders.sha256(
        tmp_path / tail_path
    )
    assert configuration["target_state_previous_sha256"] == builders.sha256(
        tmp_path / target_path
    )
    assert configuration["target_previous_exists"] is True
    assert payload["sources"]["sequence_protocol"]["sha256"] == builders.sha256(
        tmp_path / sequence_protocol
    )
    assert payload["sources"]["new_checkpoint_copy_runner"][
        "path"
    ] == builders.NEW_CHECKPOINT_COPY_RUNNER
    assert payload["gates"] == builders.anchor_copy_gates()
    assert payload["authorization"]["run_exactly_two_new_picard_maps"] is True


def test_sequence_tail_anchor_allows_a_new_named_target(tmp_path: Path) -> None:
    sequence_summary, sequence_protocol, _ = unconverged_sequence_fixture(tmp_path)
    target_path = "outputs/checkpoints/new_anchor.dat"
    spec = builders.SequenceTailAnchorProtocolSpec(
        phase="test new anchor",
        phase_index=1,
        classification="test",
        sequence_summary_path=sequence_summary,
        sequence_protocol_path=sequence_protocol,
        target_state_path=target_path,
        summary_path="outputs/new_anchor_summary.json",
        postcopy_authorization_key="continue_two_maps",
    )
    payload = builders.build_sequence_tail_anchor_protocol(tmp_path, spec)
    configuration = payload["configuration"]
    assert not (tmp_path / target_path).exists()
    assert configuration["target_previous_exists"] is False
    assert configuration["target_state_previous_sha256"] is None


def test_tail_anchor_rejects_status_decision_protocol_and_tail_hash_changes(
    tmp_path: Path,
) -> None:
    for case in ("status", "decision", "protocol", "tail_hash"):
        root = tmp_path / case
        summary_path, protocol_path, tail_path = unconverged_sequence_fixture(root)
        write_bytes(root, "outputs/checkpoints/anchor.dat", b"old00000")
        spec = builders.SequenceTailAnchorProtocolSpec(
            phase="test",
            phase_index=1,
            classification="test",
            sequence_summary_path=summary_path,
            sequence_protocol_path=protocol_path,
            target_state_path="outputs/checkpoints/anchor.dat",
            summary_path="outputs/anchor_summary.json",
            postcopy_authorization_key="continue_two_maps",
        )
        if case in {"status", "decision"}:
            summary = json.loads((root / summary_path).read_text())
            if case == "status":
                summary["status"] = "running"
            else:
                summary["decision"]["material_feedback_authorized"] = True
            write_json(root, summary_path, summary)
        elif case == "protocol":
            write_json(root, protocol_path, {"configuration": {"maximum_picard_maps": 4}})
        else:
            write_bytes(root, tail_path, b"tampered")
        with pytest.raises(RuntimeError):
            builders.build_sequence_tail_anchor_protocol(root, spec)


def test_two_map_tail_has_distinct_anchor_initial_scratch_and_exact_horizon(
    tmp_path: Path,
) -> None:
    (
        sequence_summary,
        sequence_protocol,
        tail_path,
        anchor_summary,
        anchor_protocol,
        decision_key,
    ) = prepare_anchor(tmp_path)
    scratch_path = "outputs/checkpoints/scratch.dat"
    write_bytes(tmp_path, scratch_path, b"scratch0")
    spec = builders.TailTwoMapPicardProtocolSpec(
        phase="test",
        phase_index=2,
        classification="test",
        sequence_summary_path=sequence_summary,
        sequence_protocol_path=sequence_protocol,
        anchor_summary_path=anchor_summary,
        anchor_protocol_path=anchor_protocol,
        anchor_continuation_decision_key=decision_key,
        scratch_state_path=scratch_path,
        manifest_path="outputs/checkpoints/two/manifest.json",
        report_directory="outputs/checkpoints/two/reports",
        summary_path="outputs/two_summary.json",
        figure_path="outputs/two.png",
        runner_path="scripts/two.py",
        tail_anderson_authorization_key="tail_anderson_authorized",
    )
    payload = builders.build_tail_two_map_picard_protocol(tmp_path, spec)
    configuration = payload["configuration"]
    assert configuration["seed_summary_format"] == "sequence"
    assert configuration["seed_iteration_count"] == 3
    assert configuration["maximum_picard_maps"] == 5
    assert configuration["stop_after_iteration"] == 4
    assert configuration["new_picard_map_count_exactly"] == 2
    assert builders.MAXIMUM_CONCURRENT_PROCESSES == 3
    assert builders.MEMORY_SAFE_HEAVY_MAXIMUM_CONCURRENT_PROCESSES == 2
    assert configuration["maximum_concurrent_processes"] == 2
    assert configuration["initial_state_path"] == tail_path
    assert len(
        {
            configuration["immutable_anchor_path"],
            configuration["initial_state_path"],
            configuration["scratch_state_path"],
        }
    ) == 3
    assert configuration["immutable_anchor_sha256"] == configuration[
        "initial_state_sha256"
    ]
    assert configuration["scratch_state_initial_sha256"] == builders.sha256(
        tmp_path / scratch_path
    )
    assert payload["gates"] == builders.memory_safe_seeded_two_map_gates()
    assert payload["gates"]["each_full_map_wall_time_strictly_below_s"] == 1800.0
    original_science = builders.seeded_two_map_gates()
    for key, value in original_science.items():
        if key != "each_full_map_wall_time_strictly_below_s":
            assert payload["gates"][key] == value
    assert payload["resource_gate_provenance"] == {
        "classification": "[A-resource]",
        "baseline_maximum_concurrent_processes": 3,
        "memory_safe_maximum_concurrent_processes": 2,
        "baseline_full_map_wall_time_strictly_below_s": 1200.0,
        "worker_count_scale_factor": 1.5,
        "memory_safe_full_map_wall_time_strictly_below_s": 1800.0,
        "threshold_from_observed": False,
        "scientific_gate_changed": False,
    }
    assert payload["authorization"]["run_exactly_two_new_picard_maps"] is True
    assert payload["authorization"]["tail_anderson_authorized"] is True
    assert payload["sources"]["tail_anchor_protocol"]["sha256"] == builders.sha256(
        tmp_path / anchor_protocol
    )


def test_protected_tail_anderson_uses_only_anchor_and_two_new_maps(
    tmp_path: Path,
) -> None:
    spec, continuation = prepare_two_map_continuation(tmp_path)
    payload = builders.build_protected_anderson_tail_protocol(tmp_path, spec)
    configuration = payload["configuration"]
    assert "maximum_concurrent_processes" not in configuration
    assert configuration["x9_state_path"] == (
        "outputs/checkpoints/tail_anchor.dat"
    )
    assert configuration["x10_state_path"] == (
        "outputs/checkpoints/tail_x10.dat"
    )
    assert configuration["x11_state_path"] == (
        "outputs/checkpoints/tail_x11.dat"
    )
    assert configuration["x9_original_operator_residual"] == 1.45e-4
    assert configuration["x10_original_operator_residual"] == 1.41e-4
    assert configuration["minimum_forward_picard_fraction"] == 1.0
    assert configuration["maximum_forward_picard_fraction"] == 96.0
    assert payload["gates"] == builders.protected_anderson_tail_gates()
    assert payload["gates"][
        "predicted_global_residual_ratio_to_x10_below"
    ] == 0.99
    assert payload["lineage"]["new_picard_iteration_indices"] == [3, 4]
    assert payload["lineage"]["seed_iteration_count"] == 3
    assert payload["authorization"]["fresh_full_original_operator_map_required"]
    assert continuation["authorization"]["run_exactly_two_new_picard_maps"]
    assert all(
        configuration[key] is False
        for key in (
            "cellwise_clipping",
            "nan_to_num",
            "intensity_floor",
            "point_deletion",
            "posthoc_renormalization",
            "kkt_regularization",
            "matter_feedback",
        )
    )


def test_protected_tail_anderson_rejects_broken_chain_hash_and_horizon(
    tmp_path: Path,
) -> None:
    for case in ("chain", "tail_hash", "status", "decision", "horizon", "protocol"):
        root = tmp_path / case
        spec, _ = prepare_two_map_continuation(root)
        if case in {"chain", "status", "decision"}:
            summary = json.loads((root / spec.continuation_summary_path).read_text())
            if case == "chain":
                summary["iterations"][-1]["input_state_sha256"] = "broken"
            elif case == "status":
                summary["status"] = "complete"
            else:
                summary["decision"]["positive_picard_sequence_converged"] = True
            write_json(root, spec.continuation_summary_path, summary)
        elif case == "tail_hash":
            write_bytes(root, "outputs/checkpoints/tail_x11.dat", b"tampered")
        elif case == "horizon":
            protocol = json.loads((root / spec.continuation_protocol_path).read_text())
            protocol["configuration"]["new_picard_map_count_exactly"] = 3
            write_json(root, spec.continuation_protocol_path, protocol)
        else:
            protocol = json.loads((root / spec.continuation_protocol_path).read_text())
            protocol["classification"] = "tampered"
            write_json(root, spec.continuation_protocol_path, protocol)
        with pytest.raises(RuntimeError):
            builders.build_protected_anderson_tail_protocol(root, spec)
