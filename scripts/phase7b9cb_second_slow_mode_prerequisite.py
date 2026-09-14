"""Phase 7B9cb：执行第二次慢模外推前的唯一补充映射。"""

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
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = "6e07cbb7a19727b4562dfbb48dbf95c5b578af53eb4d706003f9bf7fd35801b6"


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _seed_manifest(protocol_path: Path) -> None:
    if engine.base._sha256(protocol_path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9cb protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    cfg = protocol["configuration"]
    manifest_path = ROOT / cfg["manifest_path"]
    if manifest_path.exists():
        return
    prior = json.loads(
        (ROOT / protocol["sources"]["phase7b9ca_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    immutable = ROOT / cfg["immutable_first_state_path"]
    initial = ROOT / cfg["initial_state_path"]
    scratch = ROOT / cfg["scratch_state_path"]
    if (
        engine.base._sha256(immutable) != cfg["immutable_first_state_sha256"]
        or engine.base._sha256(initial) != cfg["initial_state_sha256"]
        or engine.base._sha256(scratch) != cfg["scratch_state_initial_sha256"]
    ):
        raise RuntimeError("Phase 7B9cb initial checkpoint changed")
    manifest = {
        "phase": protocol["phase"],
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "status": "running",
        "current_input_path": cfg["initial_state_path"],
        "current_input_sha256": cfg["initial_state_sha256"],
        "next_output_path": cfg["scratch_state_path"],
        "iterations": prior["iterations"],
        "active_iteration": None,
    }
    _write_json_atomic(manifest_path, manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9cb_preregistered_second_slow_mode.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
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
    _seed_manifest(args.protocol)
    engine.run(args.protocol, stop_after_iteration=2)


if __name__ == "__main__":
    main()
