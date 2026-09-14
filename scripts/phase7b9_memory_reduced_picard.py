"""Phase 7B9：从未提交的 Picard map 之前低内存重启。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

try:
    from scripts import phase7b9al_positive_picard_convergence as engine
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9al_positive_picard_convergence as engine  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HASH_ENV = "PHASE7B9_MEMORY_REDUCED_PROTOCOL_SHA256"
RUNNER_RELATIVE_PATH = "scripts/phase7b9_memory_reduced_picard.py"
WORKER_SOURCE_KEYS = {
    "finite_trial_protocol",
    "finite_trial_material",
    "phase7b5p_master_input",
    "generic_positive_picard_runner",
    "positive_sequence_engine",
    "phase7b7i_worker",
    "phase7b9d_worker_helpers",
    "mixed_frame_operator",
    "mixed_frame_frequency",
}


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _validate_expected_hash(value: str) -> str:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError("expected protocol SHA256 must be 64 lowercase hex characters")
    return value


def _frozen_source_path(root: Path, source: dict[str, object]) -> Path:
    path = (root / str(source["path"])).resolve()
    if not path.is_relative_to(root.resolve()):
        raise RuntimeError("frozen memory-reduced source escaped the project root")
    if (
        path.stat().st_size != int(source["size_bytes"])
        or engine.base._sha256(path) != source["sha256"]
    ):
        raise RuntimeError(f"frozen memory-reduced source changed: {source['path']}")
    return path


def _load_protocol(
    root: Path, protocol_path: Path, expected_hash: str
) -> dict[str, object]:
    if engine.base._sha256(protocol_path) != expected_hash:
        raise RuntimeError("frozen memory-reduced Picard protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    required_sources = WORKER_SOURCE_KEYS | {
        "interrupted_protocol",
        "interrupted_manifest",
        "memory_reduced_picard_runner",
    }
    if not required_sources.issubset(protocol.get("sources", {})):
        raise RuntimeError("memory-reduced Picard frozen sources changed")
    if (
        protocol["sources"]["memory_reduced_picard_runner"].get("path")
        != RUNNER_RELATIVE_PATH
    ):
        raise RuntimeError("memory-reduced Picard runner source changed")
    for source in protocol["sources"].values():
        _frozen_source_path(root, source)
    return protocol


def _restart_contract(protocol: dict[str, object]) -> None:
    cfg = protocol["configuration"]
    authorization = protocol["authorization"]
    if (
        cfg.get("seed_summary_source_key") != "interrupted_manifest"
        or cfg.get("seed_summary_format") != "running_sequence_completed_only"
        or int(cfg.get("maximum_picard_maps", -1)) != 24
        or int(cfg.get("stop_after_iteration", -1)) != 23
        or int(cfg.get("maximum_concurrent_processes", -1)) != 2
        or int(cfg.get("restart_active_iteration_from_block_index", -1)) != 0
        or cfg.get("scratch_state_initial_sha256") is not None
        or cfg.get("scratch_state_is_uncommitted_partial") is not True
        or cfg.get("scratch_state_content_hash_intentionally_not_read") is not True
        or cfg.get("discard_interrupted_active_block_reports") is not True
        or cfg.get("reuse_interrupted_partial_blocks") is not False
        or cfg.get("overwrite_all_natural_frequency_blocks") is not True
        or authorization.get("seed_only_completed_iterations_from_interrupted_manifest")
        is not True
        or authorization.get("discard_uncommitted_active_partial") is not True
        or authorization.get("rerun_interrupted_iteration_from_first_block") is not True
        or authorization.get("overwrite_only_declared_partial_scratch") is not True
    ):
        raise RuntimeError("memory-reduced Picard restart contract changed")


def _completed_source_iterations(
    root: Path, protocol: dict[str, object]
) -> list[dict[str, object]]:
    cfg = protocol["configuration"]
    sources = protocol["sources"]
    source_protocol = json.loads(
        _frozen_source_path(root, sources["interrupted_protocol"]).read_text(
            encoding="utf-8"
        )
    )
    source_manifest = json.loads(
        _frozen_source_path(root, sources["interrupted_manifest"]).read_text(
            encoding="utf-8"
        )
    )
    iterations = source_manifest.get("iterations")
    active = source_manifest.get("active_iteration")
    seed_count = int(cfg["seed_iteration_count"])
    if (
        source_manifest.get("protocol_sha256")
        != sources["interrupted_protocol"]["sha256"]
        or source_manifest.get("phase") != source_protocol.get("phase")
        or source_manifest.get("status") != "running"
        or not isinstance(iterations, list)
        or len(iterations) != seed_count
        or not isinstance(active, dict)
    ):
        raise RuntimeError("interrupted Picard source manifest changed")
    for index, record in enumerate(iterations):
        if (
            int(record.get("iteration", -1)) != index
            or record.get("map_passed") is not True
        ):
            raise RuntimeError("interrupted completed Picard sequence changed")
        if index and (
            record.get("input_state_path")
            != iterations[index - 1].get("mapped_state_path")
            or record.get("input_state_sha256")
            != iterations[index - 1].get("mapped_state_sha256")
        ):
            raise RuntimeError("interrupted completed Picard chain changed")
    final = iterations[-1]
    completed = active.get("completed_blocks")
    discarded_indices = protocol["reference"]["discarded_uncommitted_block_indices"]
    if (
        source_manifest.get("current_input_path") != cfg["initial_state_path"]
        or source_manifest.get("current_input_sha256") != cfg["initial_state_sha256"]
        or source_manifest.get("next_output_path") != cfg["scratch_state_path"]
        or final.get("mapped_state_path") != cfg["initial_state_path"]
        or final.get("mapped_state_sha256") != cfg["initial_state_sha256"]
        or int(active.get("iteration", -1)) != int(cfg["restart_picard_iteration"])
        or active.get("input_state_path") != cfg["initial_state_path"]
        or active.get("input_state_sha256") != cfg["initial_state_sha256"]
        or active.get("output_state_path") != cfg["scratch_state_path"]
        or not isinstance(completed, list)
        or len(completed) != int(cfg["interrupted_partial_completed_block_count"])
        or [row.get("block_index") for row in completed] != discarded_indices
    ):
        raise RuntimeError("interrupted active Picard map lineage changed")
    # 中文：只复制已经提交的完整 map；旧 active 的块报告全部丢弃。
    return json.loads(json.dumps(iterations))


def _validate_new_manifest(
    manifest: dict[str, object],
    protocol: dict[str, object],
    expected_hash: str,
    source_iterations: list[dict[str, object]],
) -> None:
    cfg = protocol["configuration"]
    iterations = manifest.get("iterations")
    if (
        manifest.get("phase") != protocol.get("phase")
        or manifest.get("protocol_sha256") != expected_hash
        or manifest.get("status") not in {
            "running",
            "complete",
            "gate_failed",
            "maximum_maps_exhausted",
        }
        or not isinstance(iterations, list)
        or len(iterations) < len(source_iterations)
        or iterations[: len(source_iterations)] != source_iterations
    ):
        raise RuntimeError("memory-reduced Picard manifest lineage changed")
    active = manifest.get("active_iteration")
    if active is not None:
        if not isinstance(active, dict):
            raise RuntimeError("memory-reduced active iteration changed")
        completed = active.get("completed_blocks")
        if not isinstance(completed, list) or any(
            row.get("protocol_sha256") != expected_hash for row in completed
        ):
            # 中文：旧协议的 partial block 即使仍在 scratch 中也绝不恢复。
            raise RuntimeError("refusing interrupted-protocol partial block recovery")
    if len(iterations) == len(source_iterations) and active is None and (
        manifest.get("current_input_path") != cfg["initial_state_path"]
        or manifest.get("current_input_sha256") != cfg["initial_state_sha256"]
        or manifest.get("next_output_path") != cfg["scratch_state_path"]
    ):
        raise RuntimeError("memory-reduced initial double-buffer order changed")


def _seed_manifest(
    protocol_path: Path, expected_hash: str, *, root: Path | None = None
) -> dict[str, object]:
    root = ROOT if root is None else root
    expected_hash = _validate_expected_hash(expected_hash)
    protocol = _load_protocol(root, protocol_path, expected_hash)
    _restart_contract(protocol)
    source_iterations = _completed_source_iterations(root, protocol)
    cfg = protocol["configuration"]
    manifest_path = root / cfg["manifest_path"]
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _validate_new_manifest(manifest, protocol, expected_hash, source_iterations)
        return manifest
    manifest = {
        "phase": protocol["phase"],
        "protocol_sha256": expected_hash,
        "status": "running",
        "current_input_path": cfg["initial_state_path"],
        "current_input_sha256": cfg["initial_state_sha256"],
        "next_output_path": cfg["scratch_state_path"],
        "iterations": source_iterations,
        "active_iteration": None,
        "restart_audit": {
            "interrupted_active_iteration_imported": False,
            "interrupted_completed_blocks_imported": 0,
            "restart_from_block_index": 0,
            "scratch_initial_sha256_required": False,
            "full_scratch_block_overwrite_required": True,
        },
    }
    _write_json_atomic(manifest_path, manifest)
    return manifest


def run(
    expected_hash: str,
    protocol_path: Path,
    *,
    stop_after_iteration: int | None = None,
) -> dict[str, object]:
    expected_hash = _validate_expected_hash(expected_hash)
    engine.EXPECTED_PROTOCOL_SHA256 = expected_hash
    _seed_manifest(protocol_path, expected_hash)
    return engine.run(protocol_path, stop_after_iteration=stop_after_iteration)


def _parser(default_protocol: Path | None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=default_protocol,
        required=default_protocol is None,
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--stop-after-iteration", type=int)
    return parser


def _dispatch(args: argparse.Namespace, expected_hash: str) -> None:
    expected_hash = _validate_expected_hash(expected_hash)
    engine.EXPECTED_PROTOCOL_SHA256 = expected_hash
    if args.worker:
        if (
            args.iteration is None
            or args.block_index is None
            or args.input_state is None
            or args.input_sha256 is None
            or args.output_state is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires iteration, block and both states")
        engine._run_worker(
            args.protocol,
            args.iteration,
            args.block_index,
            args.input_state,
            args.input_sha256,
            args.output_state,
            args.worker_report,
        )
        return
    run(
        expected_hash,
        args.protocol,
        stop_after_iteration=args.stop_after_iteration,
    )


def run_cli(expected_hash: str, default_protocol: Path) -> None:
    """供阶段 wrapper 以代码内常量固定协议 SHA。"""

    expected_hash = _validate_expected_hash(expected_hash)
    os.environ[EXPECTED_HASH_ENV] = expected_hash
    _dispatch(_parser(default_protocol).parse_args(), expected_hash)


def main() -> None:
    """直接执行时显式给 SHA；worker 子进程从父进程继承该 SHA。"""

    parser = _parser(None)
    parser.add_argument(
        "--expected-protocol-sha256",
        default=os.environ.get(EXPECTED_HASH_ENV),
    )
    args = parser.parse_args()
    if args.expected_protocol_sha256 is None:
        raise ValueError("direct runner requires --expected-protocol-sha256")
    expected_hash = _validate_expected_hash(args.expected_protocol_sha256)
    os.environ[EXPECTED_HASH_ENV] = expected_hash
    _dispatch(args, expected_hash)


if __name__ == "__main__":
    main()
