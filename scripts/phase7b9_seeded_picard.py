"""Phase 7B9：从已审计映射或序列播种可恢复 Picard 延拓。"""

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


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _map_record(mapped: dict[str, object]) -> dict[str, object]:
    reports = mapped["reports"]
    return {
        "iteration": 0,
        "input_state_path": mapped["input_state_path"],
        "input_state_sha256": mapped["input_state_sha256"],
        "mapped_state_path": mapped["output_state_path"],
        "mapped_state_sha256": mapped["output_state_sha256"],
        "frequency_ownership_count": sum(
            int(row["core_group_stop"]) - int(row["core_group_start"])
            for row in reports
        ),
        "frequency_ownership_exact": True,
        "global_original_operator_residual": mapped[
            "input_global_original_operator_residual"
        ],
        "boundary_spectrum_l1": mapped["input_boundary_spectrum_l1"],
        "boundary_bolometric_fraction": mapped[
            "input_boundary_bolometric_fraction"
        ],
        "minimum_input_intensity": min(
            float(row["minimum_input_intensity"]) for row in reports
        ),
        "minimum_mapped_intensity": min(
            float(row["minimum_mapped_intensity"]) for row in reports
        ),
        "maximum_process_peak_rss_mib": mapped["maximum_process_peak_rss_mib"],
        "maximum_worker_wall_runtime_s": max(
            float(row["wall_runtime_s"]) for row in reports
        ),
        "contraction_ratio": None,
        "full_map_wall_runtime_s": mapped["wall_runtime_s"],
        "gate_checks": mapped["gate_checks"],
        "map_passed": True,
        "imported_audited_map": True,
        "reports": reports,
    }


def _seed_manifest(protocol_path: Path, expected_hash: str) -> None:
    if engine.base._sha256(protocol_path) != expected_hash:
        raise RuntimeError("frozen seeded-Picard protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    cfg = protocol["configuration"]
    manifest_path = ROOT / cfg["manifest_path"]
    if manifest_path.exists():
        return
    seed = json.loads(
        (ROOT / protocol["sources"][cfg["seed_summary_source_key"]]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if cfg["seed_summary_format"] == "global_map":
        iterations = [_map_record(seed)]
    elif cfg["seed_summary_format"] == "sequence":
        iterations = seed["iterations"]
    else:
        raise RuntimeError("unsupported seeded-Picard summary format")
    if len(iterations) != int(cfg["seed_iteration_count"]):
        raise RuntimeError("seeded-Picard iteration count changed")
    immutable = ROOT / cfg["immutable_anchor_path"]
    initial = ROOT / cfg["initial_state_path"]
    scratch = ROOT / cfg["scratch_state_path"]
    if (
        engine.base._sha256(immutable) != cfg["immutable_anchor_sha256"]
        or engine.base._sha256(initial) != cfg["initial_state_sha256"]
        or engine.base._sha256(scratch) != cfg["scratch_state_initial_sha256"]
    ):
        raise RuntimeError("seeded-Picard initial checkpoint changed")
    manifest = {
        "phase": protocol["phase"],
        "protocol_sha256": expected_hash,
        "status": "running",
        "current_input_path": cfg["initial_state_path"],
        "current_input_sha256": cfg["initial_state_sha256"],
        "next_output_path": cfg["scratch_state_path"],
        "iterations": iterations,
        "active_iteration": None,
    }
    _write_json_atomic(manifest_path, manifest)


def run_cli(expected_hash: str, default_protocol: Path) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=default_protocol)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
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
    _seed_manifest(args.protocol, expected_hash)
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    engine.run(
        args.protocol,
        stop_after_iteration=int(protocol["configuration"]["stop_after_iteration"]),
    )
