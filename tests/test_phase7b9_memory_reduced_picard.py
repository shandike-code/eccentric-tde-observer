"""低内存 Picard runner 的 completed-only 播种回归。"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builders = load_module(
    "phase7b9_memory_reduced_runner_builders",
    ROOT / "scripts/phase7b9_protocol_builders.py",
)
runner = load_module(
    "phase7b9_memory_reduced_runner",
    ROOT / "scripts/phase7b9_memory_reduced_picard.py",
)


def write_json(path: Path, payload: dict[str, object]) -> None:
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
    memory_runner = root / builders.MEMORY_REDUCED_PICARD_RUNNER
    memory_runner.parent.mkdir(parents=True, exist_ok=True)
    memory_runner.write_text("# frozen memory-reduced runner\n", encoding="utf-8")
    sources["immutable_mapped_anchor"] = {
        "path": "outputs/checkpoints/immutable.dat",
        "size_bytes": 10_099_884_032,
        "sha256": "f" * 64,
    }
    return sources


def make_frozen_protocol(root: Path) -> tuple[Path, str, Path]:
    source_protocol_relative = "outputs/source_protocol.json"
    source_manifest_relative = "outputs/checkpoints/source/manifest.json"
    state_paths = (
        "outputs/checkpoints/state_a.dat",
        "outputs/checkpoints/state_b.dat",
    )
    state_hashes = [f"{index:064x}" for index in range(19)]
    source_protocol = {
        "phase": "three-worker interrupted Picard",
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
            "immutable_anchor_sha256": "f" * 64,
            "initial_state_path": state_paths[1],
            "initial_state_sha256": state_hashes[3],
            "raw_float64_checkpoint_size_bytes": 800,
            "manifest_path": source_manifest_relative,
            "report_directory": "outputs/checkpoints/source/reports",
            "summary_path": "outputs/source_summary.json",
            "figure_path": "outputs/source.png",
            "runner_path": "scripts/source_runner.py",
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
    source_protocol_path = root / source_protocol_relative
    write_json(source_protocol_path, source_protocol)
    source_protocol_hash = builders.sha256(source_protocol_path)
    iterations = []
    for index in range(18):
        iterations.append(
            {
                "iteration": index,
                "input_state_path": state_paths[index % 2],
                "input_state_sha256": state_hashes[index],
                "mapped_state_path": state_paths[(index + 1) % 2],
                "mapped_state_sha256": state_hashes[index + 1],
                "global_original_operator_residual": 2.0e-4 - index * 3.0e-6,
                "boundary_spectrum_l1": 1.0e-6,
                "boundary_bolometric_fraction": 8.0e-7,
                "map_passed": True,
                "reports": [{"committed_report": index}],
            }
        )
    active_blocks = [
        {
            "protocol_sha256": source_protocol_hash,
            "picard_iteration": 18,
            "block_index": index,
            "core_group_start": index * 128,
            "core_group_stop": min((index + 1) * 128, 9632),
            "input_state_path": state_paths[0],
            "input_state_sha256": state_hashes[18],
            "output_state_path": state_paths[1],
            "legacy_active_report": True,
        }
        for index in range(63)
    ]
    source_manifest_path = root / source_manifest_relative
    write_json(
        source_manifest_path,
        {
            "phase": source_protocol["phase"],
            "protocol_sha256": source_protocol_hash,
            "status": "running",
            "current_input_path": state_paths[0],
            "current_input_sha256": state_hashes[18],
            "next_output_path": state_paths[1],
            "iterations": iterations,
            "active_iteration": {
                "iteration": 18,
                "input_state_path": state_paths[0],
                "input_state_sha256": state_hashes[18],
                "output_state_path": state_paths[1],
                "completed_blocks": active_blocks,
            },
        },
    )
    payload = builders.build_memory_reduced_picard_continuation_protocol(
        root,
        builders.MemoryReducedPicardContinuationProtocolSpec(
            phase="two-worker memory-reduced continuation",
            phase_index=1800,
            classification="[A-preregistered]+[V]+[O]",
            interrupted_protocol_path=source_protocol_relative,
            interrupted_manifest_path=source_manifest_relative,
            manifest_path="outputs/checkpoints/restart/manifest.json",
            report_directory="outputs/checkpoints/restart/reports",
            summary_path="outputs/restart_summary.json",
            figure_path="outputs/restart.png",
            runner_path=builders.MEMORY_REDUCED_PICARD_RUNNER,
        ),
    )
    protocol_path = root / "outputs/restart_protocol.json"
    write_json(protocol_path, payload)
    return protocol_path, builders.sha256(protocol_path), source_manifest_path


def reject_dat_hash(original):
    def checked(path: Path) -> str:
        if path.suffix == ".dat":
            raise AssertionError("runner seed must not hash checkpoint data")
        return original(path)

    return checked


def test_seed_copies_18_completed_maps_but_discards_old_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol_path, protocol_hash, source_manifest_path = make_frozen_protocol(tmp_path)
    source_bytes = source_manifest_path.read_bytes()
    monkeypatch.setattr(
        runner.engine.base,
        "_sha256",
        reject_dat_hash(runner.engine.base._sha256),
    )
    manifest = runner._seed_manifest(protocol_path, protocol_hash, root=tmp_path)
    frozen = json.loads(protocol_path.read_text())
    # 模拟 generic._run_worker 当前直接索引的两个 source key。
    assert frozen["sources"]["finite_trial_protocol"]["path"]
    assert frozen["sources"]["phase7b5p_master_input"]["path"]
    assert frozen["sources"]["memory_reduced_picard_runner"] == builders.source_entry(
        tmp_path, builders.MEMORY_REDUCED_PICARD_RUNNER
    )
    assert "immutable_mapped_anchor" not in frozen["sources"]
    assert len(manifest["iterations"]) == 18
    assert manifest["active_iteration"] is None
    assert manifest["current_input_path"].endswith("state_a.dat")
    assert manifest["next_output_path"].endswith("state_b.dat")
    assert manifest["restart_audit"] == {
        "interrupted_active_iteration_imported": False,
        "interrupted_completed_blocks_imported": 0,
        "restart_from_block_index": 0,
        "scratch_initial_sha256_required": False,
        "full_scratch_block_overwrite_required": True,
    }
    assert "legacy_active_report" not in json.dumps(manifest)
    assert source_manifest_path.read_bytes() == source_bytes
    assert list(tmp_path.rglob("*.dat")) == []


def test_run_hands_engine_an_empty_active_map_and_two_worker_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol_path, protocol_hash, _ = make_frozen_protocol(tmp_path)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    original_hash = runner.engine.base._sha256
    monkeypatch.setattr(runner.engine.base, "_sha256", reject_dat_hash(original_hash))
    observed: dict[str, object] = {}

    def fake_run(path: Path, *, stop_after_iteration: int | None = None):
        protocol = json.loads(path.read_text())
        manifest = json.loads(
            (tmp_path / protocol["configuration"]["manifest_path"]).read_text()
        )
        observed["workers"] = protocol["configuration"][
            "maximum_concurrent_processes"
        ]
        observed["iteration_count"] = len(manifest["iterations"])
        observed["active"] = manifest["active_iteration"]
        observed["restart_block"] = manifest["restart_audit"][
            "restart_from_block_index"
        ]
        observed["stop"] = stop_after_iteration
        return {"status": "mocked"}

    monkeypatch.setattr(runner.engine, "run", fake_run)
    result = runner.run(protocol_hash, protocol_path, stop_after_iteration=18)
    assert result == {"status": "mocked"}
    assert observed == {
        "workers": 2,
        "iteration_count": 18,
        "active": None,
        "restart_block": 0,
        "stop": 18,
    }


def test_seed_refuses_imported_old_protocol_partial_reports(
    tmp_path: Path,
) -> None:
    protocol_path, protocol_hash, source_manifest_path = make_frozen_protocol(tmp_path)
    manifest = runner._seed_manifest(protocol_path, protocol_hash, root=tmp_path)
    source = json.loads(source_manifest_path.read_text())
    manifest["active_iteration"] = source["active_iteration"]
    protocol = json.loads(protocol_path.read_text())
    write_json(tmp_path / protocol["configuration"]["manifest_path"], manifest)
    with pytest.raises(RuntimeError, match="partial block recovery"):
        runner._seed_manifest(protocol_path, protocol_hash, root=tmp_path)


def test_seed_rejects_missing_generic_worker_source(tmp_path: Path) -> None:
    protocol_path, _, _ = make_frozen_protocol(tmp_path)
    protocol = json.loads(protocol_path.read_text())
    del protocol["sources"]["finite_trial_protocol"]
    write_json(protocol_path, protocol)
    changed_hash = builders.sha256(protocol_path)
    with pytest.raises(RuntimeError, match="frozen sources"):
        runner._seed_manifest(protocol_path, changed_hash, root=tmp_path)


def test_worker_dispatch_forwards_one_of_two_concurrent_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol_path, protocol_hash, _ = make_frozen_protocol(tmp_path)
    captured: list[object] = []
    monkeypatch.setattr(
        runner.engine,
        "_run_worker",
        lambda *args: captured.extend(args),
    )
    args = argparse.Namespace(
        protocol=protocol_path,
        worker=True,
        iteration=18,
        block_index=7,
        input_state=tmp_path / "input.dat",
        input_sha256="a" * 64,
        output_state=tmp_path / "output.dat",
        worker_report=tmp_path / "report.json",
        stop_after_iteration=None,
    )
    runner._dispatch(args, protocol_hash)
    assert captured[0] == protocol_path
    assert captured[1:3] == [18, 7]
    assert runner.engine.EXPECTED_PROTOCOL_SHA256 == protocol_hash
