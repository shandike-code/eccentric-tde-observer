"""Phase 7B9bt：执行可恢复的长正 Picard 收敛序列。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np

try:
    from scripts import phase7b9al_positive_picard_convergence as engine
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9al_positive_picard_convergence as engine  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "ff8ca16849fac74e4b4c3cebba15ccb9e0b28b7fffc83734960602d04c4a1b9e"


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _prepare_initial_buffer(protocol_path: Path) -> None:
    if engine.base._sha256(protocol_path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9bt protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    cfg = protocol["configuration"]
    manifest = ROOT / cfg["manifest_path"]
    if manifest.exists():
        return
    source = ROOT / cfg["preparation_source_path"]
    target = ROOT / cfg["initial_state_path"]
    status_path = ROOT / cfg["preparation_status_path"]
    source_sha = engine.base._sha256(source)
    if source_sha != cfg["preparation_source_sha256"]:
        raise RuntimeError("Phase 7B9bt preparation source changed")
    target_sha = engine.base._sha256(target)
    if target_sha == source_sha:
        _write_json_atomic(
            status_path,
            {
                "phase": protocol["phase"],
                "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
                "status": "complete",
                "source_path": cfg["preparation_source_path"],
                "source_sha256": source_sha,
                "target_path": cfg["initial_state_path"],
                "target_sha256": target_sha,
            },
        )
        return
    resumable = False
    if status_path.exists():
        status = json.loads(status_path.read_text(encoding="utf-8"))
        resumable = (
            status.get("protocol_sha256") == EXPECTED_PROTOCOL_SHA256
            and status.get("status") == "copying"
        )
    if target_sha != cfg["initial_state_previous_sha256"] and not resumable:
        raise RuntimeError("Phase 7B9bt named initial buffer changed")
    _write_json_atomic(
        status_path,
        {
            "phase": protocol["phase"],
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "status": "copying",
            "source_path": cfg["preparation_source_path"],
            "source_sha256": source_sha,
            "target_path": cfg["initial_state_path"],
            "target_sha256_before_copy": target_sha,
        },
    )
    shape = (
        int(cfg["physical_frequency_groups"]),
        int(cfg["angular_direction_count"]),
        int(cfg["radiation_depth_cell_count"]),
    )
    source_map = np.memmap(source, mode="r", dtype=np.float64, shape=shape)
    target_map = np.memmap(target, mode="r+", dtype=np.float64, shape=shape)
    # 中文：只覆盖协议点名的淘汰缓冲区，原始最佳态保持只读留档。
    for start in range(0, shape[0], 32):
        stop = min(start + 32, shape[0])
        target_map[start:stop] = source_map[start:stop]
    target_map.flush()
    del source_map, target_map
    copied_sha = engine.base._sha256(target)
    if copied_sha != source_sha:
        raise RuntimeError("Phase 7B9bt initial buffer copy changed bytes")
    _write_json_atomic(
        status_path,
        {
            "phase": protocol["phase"],
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "status": "complete",
            "source_path": cfg["preparation_source_path"],
            "source_sha256": source_sha,
            "target_path": cfg["initial_state_path"],
            "target_sha256": copied_sha,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            ROOT / "outputs/phase7b9bt_preregistered_long_positive_picard.json"
        ),
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--stop-after-iteration", type=int)
    args = parser.parse_args()
    engine.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
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
    _prepare_initial_buffer(args.protocol)
    engine.run(args.protocol, stop_after_iteration=args.stop_after_iteration)


if __name__ == "__main__":
    main()
