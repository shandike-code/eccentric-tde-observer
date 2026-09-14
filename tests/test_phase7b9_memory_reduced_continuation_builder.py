"""低内存 Picard 中断续跑 builder 的纯 JSON/tmp_path 回归。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/phase7b9_protocol_builders.py"
SPEC = importlib.util.spec_from_file_location("phase7b9_memory_reduced_builder", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load Phase 7B9 protocol builders")
builders = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builders
SPEC.loader.exec_module(builders)


def write_json(root: Path, relative_path: str, payload: dict[str, object]) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def worker_sources(root: Path) -> dict[str, dict[str, object]]:
    sources: dict[str, dict[str, object]] = {}
    for key in builders.MEMORY_REDUCED_WORKER_SOURCE_KEYS:
        relative_path = f"small_sources/{key}.txt"
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"frozen {key}\n", encoding="utf-8")
        sources[key] = builders.source_entry(root, relative_path)
    runner = root / builders.MEMORY_REDUCED_PICARD_RUNNER
    runner.parent.mkdir(parents=True, exist_ok=True)
    runner.write_text("# frozen memory-reduced runner\n", encoding="utf-8")
    # 不创建这个 .dat；builder 必须显式排除原协议的巨大 immutable source。
    sources["immutable_mapped_anchor"] = {
        "path": "outputs/checkpoints/immutable.dat",
        "size_bytes": 10_099_884_032,
        "sha256": "a" * 64,
    }
    return sources


def fixture(
    root: Path,
) -> builders.MemoryReducedPicardContinuationProtocolSpec:
    protocol_path = "outputs/interrupted_protocol.json"
    manifest_path = "outputs/checkpoints/interrupted/manifest.json"
    paths = ("outputs/checkpoints/a.dat", "outputs/checkpoints/b.dat")
    hashes = ("1" * 64, "2" * 64, "3" * 64, "4" * 64)
    protocol = {
        "phase": "interrupted Picard",
        "sources": worker_sources(root),
        "configuration": {
            "spatial_scheme": "hybrid_step_turning_upwind",
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_picard_maps": 24,
            "maximum_concurrent_processes": 3,
            "stop_after_iteration": 23,
            "seed_summary_format": "sequence",
            "seed_iteration_count": 3,
            "immutable_anchor_path": "outputs/checkpoints/immutable.dat",
            "immutable_anchor_sha256": "a" * 64,
            "initial_state_path": paths[1],
            "initial_state_sha256": hashes[3],
            "raw_float64_checkpoint_size_bytes": 800,
            "manifest_path": manifest_path,
            "report_directory": "outputs/checkpoints/interrupted/reports",
            "summary_path": "outputs/interrupted_summary.json",
            "figure_path": "outputs/interrupted.png",
            "runner_path": "scripts/interrupted_runner.py",
            **builders.numerical_repair_prohibitions(sequence=True),
        },
        "gates": builders.seeded_two_map_gates(),
        "authorization": {
            "seed_manifest_from_audited_sequence": True,
            "resume_pure_picard_after_rejected_anderson": True,
            "rejected_anderson_candidate_used": False,
            "alternate_only_named_generated_buffers": True,
            "material_feedback_only_after_convergence": True,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
    }
    write_json(root, protocol_path, protocol)
    protocol_sha = builders.sha256(root / protocol_path)
    iterations = [
        {
            "iteration": 0,
            "input_state_path": paths[0],
            "input_state_sha256": hashes[0],
            "mapped_state_path": paths[1],
            "mapped_state_sha256": hashes[1],
            "global_original_operator_residual": 1.8e-4,
            "boundary_spectrum_l1": 8.0e-6,
            "boundary_bolometric_fraction": 7.0e-7,
            "map_passed": True,
        },
        {
            "iteration": 1,
            "input_state_path": paths[1],
            "input_state_sha256": hashes[1],
            "mapped_state_path": paths[0],
            "mapped_state_sha256": hashes[2],
            "global_original_operator_residual": 1.6e-4,
            "boundary_spectrum_l1": 7.0e-6,
            "boundary_bolometric_fraction": 6.0e-7,
            "map_passed": True,
        },
        {
            "iteration": 2,
            "input_state_path": paths[0],
            "input_state_sha256": hashes[2],
            "mapped_state_path": paths[1],
            "mapped_state_sha256": hashes[3],
            "global_original_operator_residual": 1.5e-4,
            "boundary_spectrum_l1": 6.0e-6,
            "boundary_bolometric_fraction": 5.0e-7,
            "map_passed": True,
        },
    ]
    blocks = [
        {
            "protocol_sha256": protocol_sha,
            "picard_iteration": 3,
            "block_index": index,
            "core_group_start": index * 128,
            "core_group_stop": (index + 1) * 128,
            "input_state_path": paths[1],
            "input_state_sha256": hashes[3],
            "output_state_path": paths[0],
        }
        for index in range(2)
    ]
    write_json(
        root,
        manifest_path,
        {
            "phase": protocol["phase"],
            "protocol_sha256": protocol_sha,
            "status": "running",
            "current_input_path": paths[1],
            "current_input_sha256": hashes[3],
            "next_output_path": paths[0],
            "iterations": iterations,
            "active_iteration": {
                "iteration": 3,
                "input_state_path": paths[1],
                "input_state_sha256": hashes[3],
                "output_state_path": paths[0],
                "completed_blocks": blocks,
                "accumulated_wall_runtime_s": 10.0,
            },
        },
    )
    return builders.MemoryReducedPicardContinuationProtocolSpec(
        phase="memory-reduced continuation",
        phase_index=1700,
        classification="[A-preregistered]+[V]+[O]",
        interrupted_protocol_path=protocol_path,
        interrupted_manifest_path=manifest_path,
        manifest_path="outputs/checkpoints/memory_reduced/manifest.json",
        report_directory="outputs/checkpoints/memory_reduced/reports",
        summary_path="outputs/memory_reduced_summary.json",
        figure_path="outputs/memory_reduced.png",
        runner_path=builders.MEMORY_REDUCED_PICARD_RUNNER,
    )


def test_builder_restarts_uncommitted_active_map_with_two_workers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = fixture(tmp_path)
    interrupted_manifest = tmp_path / spec.interrupted_manifest_path
    manifest_bytes_before = interrupted_manifest.read_bytes()
    original_sha256 = builders.sha256

    def json_only_sha256(path: Path) -> str:
        if path.suffix == ".dat":
            raise AssertionError("builder must not hash checkpoint data")
        return original_sha256(path)

    monkeypatch.setattr(builders, "sha256", json_only_sha256)
    payload = builders.build_memory_reduced_picard_continuation_protocol(
        tmp_path, spec
    )
    configuration = payload["configuration"]
    assert set(payload["sources"]) == {
        *builders.MEMORY_REDUCED_WORKER_SOURCE_KEYS,
        "interrupted_protocol",
        "interrupted_manifest",
        "memory_reduced_picard_runner",
    }
    assert "immutable_mapped_anchor" not in payload["sources"]
    interrupted = json.loads(
        (tmp_path / spec.interrupted_protocol_path).read_text(encoding="utf-8")
    )
    for key in builders.MEMORY_REDUCED_WORKER_SOURCE_KEYS:
        assert payload["sources"][key] == interrupted["sources"][key]
    assert payload["sources"]["memory_reduced_picard_runner"] == builders.source_entry(
        tmp_path, builders.MEMORY_REDUCED_PICARD_RUNNER
    )
    assert configuration["maximum_picard_maps"] == 24
    assert configuration["stop_after_iteration"] == 23
    assert configuration["maximum_concurrent_processes"] == 2
    assert configuration["seed_iteration_count"] == 3
    assert configuration["restart_picard_iteration"] == 3
    assert configuration["initial_state_path"].endswith("b.dat")
    assert configuration["initial_state_sha256"] == "4" * 64
    assert configuration["scratch_state_path"].endswith("a.dat")
    assert configuration["scratch_state_initial_sha256"] is None
    assert configuration["scratch_state_content_hash_intentionally_not_read"]
    assert configuration["interrupted_partial_completed_block_count"] == 2
    assert configuration["restart_active_iteration_from_block_index"] == 0
    assert configuration["reuse_interrupted_partial_blocks"] is False
    assert configuration["overwrite_all_natural_frequency_blocks"] is True
    assert payload["reference"]["discarded_uncommitted_block_indices"] == [0, 1]
    assert payload["gates"] == builders.seeded_two_map_gates()
    assert payload["io_audit"] == {
        "checkpoint_dat_opened_by_builder": False,
        "checkpoint_dat_hashed_by_builder": False,
        "checkpoint_dat_modified_by_builder": False,
        "interrupted_manifest_modified_by_builder": False,
    }
    assert interrupted_manifest.read_bytes() == manifest_bytes_before
    assert list(tmp_path.rglob("*.dat")) == []


@pytest.mark.parametrize(
    "failure",
    (
        "status",
        "no_active",
        "map_failed",
        "chain",
        "active_input",
        "active_output",
        "block_prefix",
        "complete_blocks",
        "protocol_hash",
        "gate",
        "old_output",
    ),
)
def test_builder_rejects_broken_interrupted_state(
    tmp_path: Path, failure: str
) -> None:
    root = tmp_path / failure
    spec = fixture(root)
    protocol_path = root / spec.interrupted_protocol_path
    manifest_path = root / spec.interrupted_manifest_path
    protocol = json.loads(protocol_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    if failure == "status":
        manifest["status"] = "maximum_maps_exhausted"
    elif failure == "no_active":
        manifest["active_iteration"] = None
    elif failure == "map_failed":
        manifest["iterations"][1]["map_passed"] = False
    elif failure == "chain":
        manifest["iterations"][2]["input_state_sha256"] = "broken"
    elif failure == "active_input":
        manifest["active_iteration"]["input_state_sha256"] = "broken"
    elif failure == "active_output":
        manifest["active_iteration"]["output_state_path"] = "wrong.dat"
    elif failure == "block_prefix":
        manifest["active_iteration"]["completed_blocks"][1]["block_index"] = 2
    elif failure == "complete_blocks":
        template = manifest["active_iteration"]["completed_blocks"][0]
        manifest["active_iteration"]["completed_blocks"] = [
            {
                **template,
                "block_index": index,
                "core_group_start": index * 128,
                "core_group_stop": min((index + 1) * 128, 9632),
            }
            for index in range(76)
        ]
    elif failure == "protocol_hash":
        manifest["protocol_sha256"] = "0" * 64
    elif failure == "gate":
        protocol["gates"]["subsequent_residual_contraction_ratio_below"] = 1.02
        write_json(root, spec.interrupted_protocol_path, protocol)
    else:
        spec = builders.MemoryReducedPicardContinuationProtocolSpec(
            **{
                **spec.__dict__,
                "manifest_path": protocol["configuration"]["manifest_path"],
            }
        )
    write_json(root, spec.interrupted_manifest_path, manifest)
    with pytest.raises(RuntimeError):
        builders.build_memory_reduced_picard_continuation_protocol(root, spec)
