"""Phase 7B9di：streaming Anderson 候选提交及 fresh-map 可恢复编排。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable

import numpy as np

try:
    from scripts import phase7b9di_streaming_anderson_tail as streaming
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9di_streaming_anderson_tail as streaming  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
FailureHook = Callable[[str, int], None]


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(
    root: Path, protocol_path: Path, expected_hash: str
) -> dict[str, object]:
    if len(expected_hash) != 64 or streaming._sha256(protocol_path) != expected_hash:
        raise RuntimeError("frozen streaming-Anderson protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if (
        protocol.get("configuration", {}).get("orchestrator_path")
        != streaming.ORCHESTRATOR_RELATIVE_PATH
    ):
        raise RuntimeError("streaming-Anderson orchestrator changed")
    for source in protocol["sources"].values():
        current = root / source["path"]
        if (
            current.stat().st_size != int(source["size_bytes"])
            or streaming._sha256(current) != source["sha256"]
        ):
            raise RuntimeError(f"streaming-Anderson source changed: {source['path']}")
    return protocol


def _expected_ranges(protocol: dict[str, object]) -> list[tuple[int, int]]:
    cfg = protocol["configuration"]
    group_count = int(cfg["physical_frequency_groups"])
    block_count = int(cfg["natural_frequency_block_count"])
    width = int(cfg["diagnostic_frequency_block"])
    ranges = [
        (index * width, min((index + 1) * width, group_count))
        for index in range(block_count)
    ]
    if ranges[-1][1] != group_count or any(stop <= start for start, stop in ranges):
        raise RuntimeError("streaming-Anderson block partition changed")
    return ranges


def _validate_reports(
    protocol: dict[str, object],
    expected_hash: str,
    manifest: dict[str, object],
    pass_index: int,
) -> list[dict[str, object]]:
    reports = manifest.get("reports")
    ranges = _expected_ranges(protocol)
    gates = protocol["algebraic_gates"]
    if (
        manifest.get("protocol_sha256") != expected_hash
        or manifest.get("status") != "complete"
        or manifest.get("pass_index") != pass_index
        or manifest.get("full_state_write_performed") is not False
        or not isinstance(reports, list)
        or len(reports) != len(ranges)
        or float(manifest.get("full_map_wall_runtime_s", float("inf")))
        >= gates["each_dry_full_map_wall_time_strictly_below_s"]
    ):
        raise RuntimeError(f"streaming-Anderson dry pass {pass_index} is incomplete")
    ordered = sorted(reports, key=lambda row: int(row["block_index"]))
    cfg = protocol["configuration"]
    for index, (report, expected_range) in enumerate(
        zip(ordered, ranges, strict=True)
    ):
        if (
            int(report.get("block_index", -1)) != index
            or report.get("pass_index") != pass_index
            or report.get("protocol_sha256") != expected_hash
            or (report.get("core_group_start"), report.get("core_group_stop"))
            != expected_range
            or report.get("x23_state_sha256") != cfg["x23_state_sha256"]
            or report.get("x24_state_sha256") != cfg["x24_state_sha256"]
            or report.get("full_state_write_performed") is not False
            or float(report.get("peak_process_rss_mib", float("inf")))
            >= gates["each_dry_process_peak_rss_strictly_below_mib"]
            or float(report.get("wall_runtime_s", float("inf")))
            >= gates["each_dry_worker_wall_time_strictly_below_s"]
        ):
            raise RuntimeError(f"streaming-Anderson dry pass {pass_index} block failed")
    return ordered


def validate_dry_evidence(
    root: Path, protocol: dict[str, object], expected_hash: str
) -> tuple[dict[str, object], dict[str, object], dict[str, bool]]:
    """Independently reconstruct both dry-pass aggregates before any state write."""
    cfg = protocol["configuration"]
    coefficient_path = root / cfg["coefficient_manifest_path"]
    evaluation_path = root / cfg["evaluation_manifest_path"]
    coefficient_manifest = json.loads(coefficient_path.read_text(encoding="utf-8"))
    evaluation_manifest = json.loads(evaluation_path.read_text(encoding="utf-8"))
    pass1 = _validate_reports(protocol, expected_hash, coefficient_manifest, 1)
    pass2 = _validate_reports(protocol, expected_hash, evaluation_manifest, 2)
    if evaluation_manifest.get("coefficient_manifest_sha256") != streaming._sha256(
        coefficient_path
    ):
        raise RuntimeError("pass2 does not consume the frozen pass1 coefficient")
    coefficient = streaming.aggregate_coefficient_statistics(
        pass1,
        minimum_fraction=float(cfg["minimum_forward_picard_fraction"]),
        maximum_fraction=float(cfg["maximum_forward_picard_fraction"]),
    )
    if coefficient_manifest.get("aggregate") != coefficient:
        raise RuntimeError("pass1 aggregate changed")
    if evaluation_manifest.get("selected_forward_fraction") != coefficient[
        "selected_forward_fraction"
    ]:
        raise RuntimeError("pass2 used another Anderson coefficient")
    evaluation = streaming.aggregate_evaluation_statistics(pass2, pass1)
    if evaluation_manifest.get("aggregate") != evaluation:
        raise RuntimeError("pass2 aggregate changed")
    checks = streaming.algebraic_gate_checks(protocol, coefficient, evaluation)
    checks.update(
        {
            "pass1_resources_pass": True,
            "pass2_resources_pass": True,
            "block_ownership_pass": True,
        }
    )
    if evaluation_manifest.get("gate_checks") != checks or not all(checks.values()):
        raise RuntimeError("streaming-Anderson algebraic gate failed")
    return coefficient, evaluation, checks


def _plane_bytes(protocol: dict[str, object]) -> int:
    cfg = protocol["configuration"]
    return (
        int(cfg["angular_direction_count"])
        * int(cfg["radiation_depth_cell_count"])
        * np.dtype(np.float64).itemsize
    )


def _read_block(
    path: Path, start: int, stop: int, plane_bytes: int
) -> bytes:
    count = (stop - start) * plane_bytes
    with path.open("rb") as stream:
        stream.seek(start * plane_bytes)
        payload = stream.read(count)
    if len(payload) != count:
        raise RuntimeError("full-state checkpoint ended inside a guarded block")
    return payload


def _block_sha(path: Path, start: int, stop: int, plane_bytes: int) -> str:
    return hashlib.sha256(_read_block(path, start, stop, plane_bytes)).hexdigest()


def _write_block(
    path: Path, start: int, stop: int, plane_bytes: int, payload: bytes
) -> None:
    if len(payload) != (stop - start) * plane_bytes:
        raise RuntimeError("refusing out-of-range candidate block write")
    with path.open("r+b") as stream:
        stream.seek(start * plane_bytes)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _backup_path(root: Path, protocol: dict[str, object]) -> Path:
    path = (root / protocol["configuration"]["candidate_transient_backup_path"]).resolve()
    allowed = (root / "outputs/checkpoints").resolve()
    if not path.is_relative_to(allowed) or "transient" not in path.name:
        raise RuntimeError("unsafe streaming-Anderson transient backup path")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _candidate_bytes(original_x23: bytes, x24: bytes, selected: float) -> bytes:
    a = np.frombuffer(original_x23, dtype=np.float64)
    b = np.frombuffer(x24, dtype=np.float64)
    if a.size != b.size:
        raise RuntimeError("candidate block element counts differ")
    # 中文：只作冻结的全局仿射组合，不裁剪、不加 floor、不重归一化。
    candidate = b + (selected - 1.0) * (b - a)
    if not np.all(np.isfinite(candidate)) or np.any(candidate < 0.0):
        raise ArithmeticError("candidate block violates the pre-audited positivity gate")
    return np.ascontiguousarray(candidate).tobytes()


def _initial_block_hashes(
    protocol: dict[str, object], x23: Path, x24: Path
) -> tuple[list[str], list[str]]:
    plane = _plane_bytes(protocol)
    ranges = _expected_ranges(protocol)
    return (
        [_block_sha(x23, start, stop, plane) for start, stop in ranges],
        [_block_sha(x24, start, stop, plane) for start, stop in ranges],
    )


def commit_candidate(
    root: Path,
    protocol_path: Path,
    expected_hash: str,
    *,
    failure_hook: FailureHook | None = None,
) -> dict[str, object]:
    """Commit candidate blockwise with one recoverable block backup."""
    protocol = _load_protocol(root, protocol_path, expected_hash)
    coefficient, evaluation, checks = validate_dry_evidence(
        root, protocol, expected_hash
    )
    cfg = protocol["configuration"]
    x23 = root / cfg["x23_state_path"]
    x24 = root / cfg["x24_state_path"]
    expected_size = int(cfg["raw_float64_checkpoint_size_bytes"])
    manifest_path = root / cfg["candidate_commit_manifest_path"]
    backup = _backup_path(root, protocol)
    selected = float(coefficient["selected_forward_fraction"])
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest.get("protocol_sha256") != expected_hash
            or manifest.get("selected_forward_fraction") != selected
            or manifest.get("algebraic_gate_checks") != checks
        ):
            raise RuntimeError("candidate commit manifest changed")
    else:
        if (
            x23.stat().st_size != expected_size
            or x24.stat().st_size != expected_size
            or streaming._sha256(x23) != cfg["x23_state_sha256"]
            or streaming._sha256(x24) != cfg["x24_state_sha256"]
        ):
            raise RuntimeError("candidate input buffers changed before commit")
        x23_hashes, x24_hashes = _initial_block_hashes(protocol, x23, x24)
        manifest = {
            "phase": protocol["phase"],
            "protocol_sha256": expected_hash,
            "status": "writing_candidate",
            "selected_forward_fraction": selected,
            "algebraic_prediction": evaluation,
            "algebraic_gate_checks": checks,
            "original_x23_block_sha256": x23_hashes,
            "frozen_x24_block_sha256": x24_hashes,
            "completed_blocks": [],
            "active_block": None,
            "accumulated_write_wall_runtime_s": 0.0,
        }
        _write_json_atomic(manifest_path, manifest)
    if manifest["status"] in {"complete", "gate_failed"}:
        return manifest
    if manifest.get("active_block") is None and backup.exists():
        # 中文：只清理由本阶段精确命名、且已无 active owner 的单块备份。
        backup.unlink()
    ranges = _expected_ranges(protocol)
    plane = _plane_bytes(protocol)
    completed = {
        int(row["block_index"]): row for row in manifest["completed_blocks"]
    }
    for index, row in completed.items():
        start, stop = ranges[index]
        if _block_sha(x23, start, stop, plane) != row["candidate_block_sha256"]:
            raise RuntimeError("completed candidate block changed")
    for index, (start, stop) in enumerate(ranges):
        if index in completed:
            continue
        active = manifest.get("active_block")
        if active is None:
            if _block_sha(x23, start, stop, plane) != manifest[
                "original_x23_block_sha256"
            ][index]:
                raise RuntimeError("uncommitted x23 block changed")
            manifest["active_block"] = {
                "block_index": index,
                "core_group_start": start,
                "core_group_stop": stop,
                "stage": "backup_pending",
            }
            _write_json_atomic(manifest_path, manifest)
            active = manifest["active_block"]
        if (
            active.get("block_index") != index
            or active.get("core_group_start") != start
            or active.get("core_group_stop") != stop
        ):
            raise RuntimeError("candidate active block escaped its frozen range")
        if active["stage"] == "backup_pending":
            original = _read_block(x23, start, stop, plane)
            if hashlib.sha256(original).hexdigest() != manifest[
                "original_x23_block_sha256"
            ][index]:
                raise RuntimeError("candidate backup source changed")
            temporary = backup.with_name(f"{backup.name}.tmp")
            temporary.write_bytes(original)
            os.replace(temporary, backup)
            active.update(
                {
                    "stage": "write_pending",
                    "backup_sha256": hashlib.sha256(original).hexdigest(),
                }
            )
            _write_json_atomic(manifest_path, manifest)
            if failure_hook is not None:
                failure_hook("after_backup", index)
        original = backup.read_bytes()
        if hashlib.sha256(original).hexdigest() != active["backup_sha256"]:
            raise RuntimeError("candidate transient backup changed")
        x24_block = _read_block(x24, start, stop, plane)
        if hashlib.sha256(x24_block).hexdigest() != manifest[
            "frozen_x24_block_sha256"
        ][index]:
            raise RuntimeError("x24 changed during candidate commit")
        candidate = _candidate_bytes(original, x24_block, selected)
        started = time.perf_counter()
        _write_block(x23, start, stop, plane, candidate)
        manifest["accumulated_write_wall_runtime_s"] += time.perf_counter() - started
        candidate_sha = hashlib.sha256(candidate).hexdigest()
        if _block_sha(x23, start, stop, plane) != candidate_sha:
            raise RuntimeError("candidate block write verification failed")
        if failure_hook is not None:
            failure_hook("after_write_before_commit", index)
        manifest["completed_blocks"].append(
            {
                "block_index": index,
                "core_group_start": start,
                "core_group_stop": stop,
                "candidate_block_sha256": candidate_sha,
            }
        )
        manifest["completed_blocks"].sort(key=lambda row: row["block_index"])
        manifest["active_block"] = None
        _write_json_atomic(manifest_path, manifest)
        backup.unlink(missing_ok=True)
        completed[index] = manifest["completed_blocks"][-1]
    candidate_sha = streaming._sha256(x23)
    write_passed = (
        float(manifest["accumulated_write_wall_runtime_s"])
        < protocol["algebraic_gates"]["write_wall_time_strictly_below_s"]
    )
    manifest.update(
        {
            "status": "complete" if write_passed else "gate_failed",
            "candidate_state_path": cfg["x23_state_path"],
            "candidate_state_sha256": candidate_sha,
            "candidate_write_resources_pass": write_passed,
            "fresh_original_operator_map_authorized": write_passed,
            "prediction_used_as_fresh_residual": False,
        }
    )
    _write_json_atomic(manifest_path, manifest)
    return manifest


def _run_fresh_worker(
    protocol_path: Path,
    expected_hash: str,
    block_index: int,
    output_state: Path,
    report_path: Path,
) -> None:
    protocol = _load_protocol(ROOT, protocol_path, expected_hash)
    cfg = protocol["configuration"]
    commit = json.loads(
        (ROOT / cfg["candidate_commit_manifest_path"]).read_text(encoding="utf-8")
    )
    if (
        commit.get("status") != "complete"
        or commit.get("fresh_original_operator_map_authorized") is not True
    ):
        raise RuntimeError("fresh worker requires committed candidate")
    generic = streaming.sequence.generic
    dynamic = json.loads(json.dumps(protocol))
    dynamic_cfg = dynamic["configuration"]
    dynamic_cfg.update(
        {
            "input_state_path": cfg["candidate_output_path"],
            "input_state_sha256": commit["candidate_state_sha256"],
            "output_state_path": cfg["fresh_map_output_path"],
        }
    )
    fixed = json.loads(
        (ROOT / protocol["sources"]["finite_trial_protocol"]["path"]).read_text()
    )
    original_loader = generic.base.phase7b9i._load_protocol
    original_protocol_loader = generic._load_protocol
    try:
        generic.base.phase7b9i._load_protocol = (
            lambda _path, validate_sources=False: fixed
        )
        generic._load_protocol = lambda _path, validate_sources=False: dynamic
        generic.EXPECTED_PROTOCOL_SHA256 = expected_hash
        generic._run_worker(protocol_path, block_index, output_state, report_path)
    finally:
        generic.base.phase7b9i._load_protocol = original_loader
        generic._load_protocol = original_protocol_loader


def _launch_fresh_workers(
    root: Path,
    protocol_path: Path,
    expected_hash: str,
    batch: list[int],
    output_state: Path,
    report_paths: list[Path],
) -> None:
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                str(root / streaming.ORCHESTRATOR_RELATIVE_PATH),
                "--protocol",
                str(protocol_path),
                "--expected-protocol-sha256",
                expected_hash,
                "--fresh-worker",
                "--block-index",
                str(index),
                "--output-state",
                str(output_state),
                "--report",
                str(report),
            ],
            cwd=root,
        )
        for index, report in zip(batch, report_paths, strict=True)
    ]
    codes = [process.wait() for process in processes]
    if any(code != 0 for code in codes):
        raise RuntimeError(f"streaming-Anderson fresh worker failed: {codes}")


def run_fresh_map(
    root: Path,
    protocol_path: Path,
    expected_hash: str,
) -> dict[str, object]:
    """Map the committed candidate once; only these measurements are fresh."""
    protocol = _load_protocol(root, protocol_path, expected_hash)
    cfg = protocol["configuration"]
    gates = protocol["fresh_map_gates"]
    commit_path = root / cfg["candidate_commit_manifest_path"]
    commit = json.loads(commit_path.read_text(encoding="utf-8"))
    candidate = root / cfg["candidate_output_path"]
    output = root / cfg["fresh_map_output_path"]
    manifest_path = root / cfg["fresh_map_manifest_path"]
    expected_size = int(cfg["raw_float64_checkpoint_size_bytes"])
    if (
        commit.get("status") != "complete"
        or commit.get("fresh_original_operator_map_authorized") is not True
        or commit.get("prediction_used_as_fresh_residual") is not False
        or streaming._sha256(candidate) != commit.get("candidate_state_sha256")
    ):
        raise RuntimeError("fresh map candidate lineage changed")
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest.get("protocol_sha256") != expected_hash
            or manifest.get("candidate_state_sha256")
            != commit["candidate_state_sha256"]
        ):
            raise RuntimeError("fresh-map recovery manifest changed")
    else:
        if (
            output.stat().st_size != expected_size
            or streaming._sha256(output) != cfg["x24_state_sha256"]
        ):
            raise RuntimeError("fresh-map output buffer changed before first write")
        manifest = {
            "phase": protocol["phase"],
            "protocol_sha256": expected_hash,
            "status": "running",
            "candidate_state_path": cfg["candidate_output_path"],
            "candidate_state_sha256": commit["candidate_state_sha256"],
            "output_state_path": cfg["fresh_map_output_path"],
            "completed_blocks": [],
            "accumulated_wall_runtime_s": 0.0,
        }
        _write_json_atomic(manifest_path, manifest)
    if manifest["status"] != "running":
        return json.loads(
            (root / cfg["fresh_map_summary_path"]).read_text(encoding="utf-8")
        )
    plane = _plane_bytes(protocol)
    ranges = _expected_ranges(protocol)
    completed = {
        int(row["block_index"]): row for row in manifest["completed_blocks"]
    }
    for index, row in completed.items():
        start, stop = ranges[index]
        if _block_sha(output, start, stop, plane) != row["output_block_sha256"]:
            raise RuntimeError("fresh-map completed block changed")
    pending = [index for index in range(len(ranges)) if index not in completed]
    report_root = root / cfg["fresh_map_report_directory"]
    report_root.mkdir(parents=True, exist_ok=True)
    concurrency = int(cfg["maximum_concurrent_processes"])
    if concurrency != 2:
        raise RuntimeError("fresh-map worker count changed")
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        reports = [report_root / f"fresh_block{index:02d}.json" for index in batch]
        started = time.perf_counter()
        _launch_fresh_workers(
            root, protocol_path, expected_hash, batch, output, reports
        )
        manifest["accumulated_wall_runtime_s"] += time.perf_counter() - started
        for index, report_path in zip(batch, reports, strict=True):
            row = json.loads(report_path.read_text(encoding="utf-8"))
            start, stop = ranges[index]
            if (
                row.get("protocol_sha256") != expected_hash
                or row.get("block_index") != index
                or (row.get("core_group_start"), row.get("core_group_stop"))
                != (start, stop)
            ):
                raise RuntimeError("fresh-map worker report changed")
            row["output_block_sha256"] = _block_sha(
                output, start, stop, plane
            )
            manifest["completed_blocks"].append(row)
        manifest["completed_blocks"].sort(key=lambda row: row["block_index"])
        _write_json_atomic(manifest_path, manifest)
    reports = manifest["completed_blocks"]
    metrics = streaming.sequence._aggregate(
        reports,
        (
            int(cfg["physical_frequency_groups"]),
            int(cfg["angular_direction_count"]),
            int(cfg["radiation_depth_cell_count"]),
        ),
    )
    checks = {
        "frequency_ownership_pass": bool(
            len(reports) == gates["block_count_exactly"]
            and metrics["frequency_ownership_count"]
            == gates["owned_frequency_group_count_exactly"]
            and metrics["frequency_ownership_exact"]
        ),
        "positive_map_pass": bool(
            metrics["minimum_input_intensity"]
            >= gates["minimum_input_and_mapped_intensity_at_least"]
            and metrics["minimum_mapped_intensity"]
            >= gates["minimum_input_and_mapped_intensity_at_least"]
        ),
        "resources_pass": bool(
            metrics["maximum_process_peak_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and metrics["maximum_worker_wall_runtime_s"]
            < gates["each_worker_wall_time_strictly_below_s"]
            and manifest["accumulated_wall_runtime_s"]
            < gates["full_map_wall_time_strictly_below_s"]
        ),
        "prediction_reproduction_pass": bool(
            abs(
                metrics["global_original_operator_residual"]
                - commit["algebraic_prediction"][
                    "predicted_global_original_operator_residual"
                ]
            )
            <= gates[
                "input_global_residual_matches_phase7b9ab_absolute_tolerance"
            ]
            and abs(
                metrics["boundary_spectrum_l1"]
                - commit["algebraic_prediction"][
                    "predicted_boundary_spectrum_l1"
                ]
            )
            <= gates["input_boundary_metrics_match_phase7b9ab_absolute_tolerance"]
            and abs(
                metrics["boundary_bolometric_fraction"]
                - commit["algebraic_prediction"][
                    "predicted_boundary_bolometric_fraction"
                ]
            )
            <= gates["input_boundary_metrics_match_phase7b9ab_absolute_tolerance"]
        ),
    }
    passed = all(checks.values())
    output_sha = streaming._sha256(output)
    manifest.update(
        {
            "status": "complete" if passed else "gate_failed",
            "output_state_sha256": output_sha,
            "fresh_gate_checks": checks,
        }
    )
    _write_json_atomic(manifest_path, manifest)
    prediction = commit["algebraic_prediction"]
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V-fresh-map]+[O]",
        "protocol_sha256": expected_hash,
        "status": manifest["status"],
        "candidate_state_path": cfg["candidate_output_path"],
        "candidate_state_sha256": commit["candidate_state_sha256"],
        "mapped_state_path": cfg["fresh_map_output_path"],
        "mapped_state_sha256": output_sha,
        "algebraic_prediction": prediction,
        "fresh_input_global_original_operator_residual": metrics[
            "global_original_operator_residual"
        ],
        "fresh_input_boundary_spectrum_l1": metrics["boundary_spectrum_l1"],
        "fresh_input_boundary_bolometric_fraction": metrics[
            "boundary_bolometric_fraction"
        ],
        "maximum_process_peak_rss_mib": metrics["maximum_process_peak_rss_mib"],
        "maximum_worker_wall_runtime_s": metrics["maximum_worker_wall_runtime_s"],
        "full_map_wall_runtime_s": manifest["accumulated_wall_runtime_s"],
        "gate_checks": checks,
        "decision": {
            "fresh_original_operator_map_completed": passed,
            "prediction_used_as_fresh_residual": False,
            "fresh_residual_measured_from_candidate_map": True,
            "material_feedback_authorized": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    _write_json_atomic(root / cfg["fresh_map_summary_path"], summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--fresh-worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.fresh_worker:
        if args.block_index is None or args.output_state is None or args.report is None:
            raise ValueError("fresh worker requires block, output and report")
        _run_fresh_worker(
            args.protocol,
            args.expected_protocol_sha256,
            args.block_index,
            args.output_state,
            args.report,
        )
        return
    commit_candidate(ROOT, args.protocol, args.expected_protocol_sha256)
    run_fresh_map(ROOT, args.protocol, args.expected_protocol_sha256)


if __name__ == "__main__":
    main()
