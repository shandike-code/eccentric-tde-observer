"""Phase 7B9dk：从同一 immutable A 重做完整 76 块 original map。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
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
    from scripts import phase7b9_half_trial_positive_sequence_engine as engine
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_half_trial_positive_sequence_engine as engine  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
RUNNER_RELATIVE_PATH = "scripts/phase7b9dk_full_map_reproduction.py"
IMMUTABLE_INPUT_SHA256 = (
    "e2d718bd509e28a30f488babcb3ecff6adc612bfa0509f7161073400ffd4bf6f"
)
AUTHORIZED_OUTPUT_PREVIOUS_SHA256 = (
    "65f7307cffb3e52d7d8492ddfdc55fa47074dc565aa9fe466e643f74e1bc2608"
)


@dataclass(frozen=True)
class FullMapReproductionSpec:
    phase: str
    classification: str
    di_protocol_path: str
    di_manifest_path: str
    di_summary_path: str
    failure_audit_path: str
    runner_path: str
    manifest_path: str
    report_directory: str
    summary_path: str
    immutable_input_sha256: str = IMMUTABLE_INPUT_SHA256
    authorized_output_previous_sha256: str = AUTHORIZED_OUTPUT_PREVIOUS_SHA256
    natural_frequency_block_width: int = 128


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _small_source(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    if path.suffix == ".dat":
        raise RuntimeError("7B9dk builder refuses to read or hash full-state .dat")
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _block_layout(groups: int, width: int) -> list[dict[str, int]]:
    if width <= 0:
        raise RuntimeError("7B9dk natural block width must be positive")
    rows = []
    for start in range(0, groups, width):
        rows.append(
            {
                "block_index": len(rows),
                "core_group_start": start,
                "core_group_stop": min(start + width, groups),
            }
        )
    if len(rows) != 76:
        raise RuntimeError("7B9dk requires exactly 76 natural-frequency blocks")
    return rows


def build_reproduction_protocol(
    root: Path, spec: FullMapReproductionSpec
) -> dict[str, object]:
    """Builder 只冻结小文件与全态声明，不触碰 A/B 的字节。"""
    di_protocol = _read_json(root / spec.di_protocol_path)
    di_manifest = _read_json(root / spec.di_manifest_path)
    di_summary = _read_json(root / spec.di_summary_path)
    audit = _read_json(root / spec.failure_audit_path)
    di_hash = _sha256(root / spec.di_protocol_path)
    if (
        di_manifest.get("protocol_sha256") != di_hash
        or di_summary.get("protocol_sha256") != di_hash
        or di_manifest.get("status") != "gate_failed"
        or di_summary.get("status") != "gate_failed"
        or di_manifest.get("active_iteration") is not None
        or di_manifest.get("iterations") != di_summary.get("iterations")
    ):
        raise RuntimeError("7B9dk 7B9di small-file lineage changed")
    records = di_manifest.get("iterations", [])
    if len(records) != 21 or records[-1].get("iteration") != 20:
        raise RuntimeError("7B9dk requires the audited iteration-20 failure")
    failed = records[-1]
    prior = records[-2]
    claims = audit.get("frozen_state_claims", {})
    decision = audit.get("decision", {})
    if (
        failed.get("input_state_sha256") != spec.immutable_input_sha256
        or failed.get("mapped_state_sha256")
        != spec.authorized_output_previous_sha256
        or claims.get("immutable_input_sha256") != spec.immutable_input_sha256
        or claims.get("failed_output_sha256")
        != spec.authorized_output_previous_sha256
        or decision.get("unreproducible_block_index") != 34
        or decision.get("single_block_repair_authorized") is not False
        or decision.get("fresh_full_76_block_reproduction_required") is not True
    ):
        raise RuntimeError("7B9dk failure audit does not authorize the full reproduction")
    cfg = di_protocol["configuration"]
    if (
        cfg.get("maximum_concurrent_processes") != 2
        or float(di_protocol["gates"]["each_full_map_wall_time_strictly_below_s"])
        != 1800.0
    ):
        raise RuntimeError("7B9dk requires the frozen 2-worker/1800-s resource gate")
    groups = int(cfg["physical_frequency_groups"])
    layout = _block_layout(groups, spec.natural_frequency_block_width)
    sources = dict(di_protocol["sources"])
    if any(Path(str(source["path"])).suffix == ".dat" for source in sources.values()):
        raise RuntimeError("7B9dk inherited source pins must not include full-state dat")
    sources.update(
        {
            "di_protocol": _small_source(root, spec.di_protocol_path),
            "di_manifest": _small_source(root, spec.di_manifest_path),
            "di_summary": _small_source(root, spec.di_summary_path),
            "iteration20_failure_audit": _small_source(root, spec.failure_audit_path),
            "full_map_reproduction_runner": _small_source(root, spec.runner_path),
        }
    )
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": sources,
        "configuration": {
            "physical_frequency_groups": groups,
            "angular_direction_count": int(cfg["angular_direction_count"]),
            "radiation_depth_cell_count": int(cfg["radiation_depth_cell_count"]),
            "raw_float64_checkpoint_size_bytes": int(
                cfg["raw_float64_checkpoint_size_bytes"]
            ),
            "diagnostic_fixed_iteration_count": int(
                cfg["diagnostic_fixed_iteration_count"]
            ),
            "spatial_scheme": cfg["spatial_scheme"],
            "source_map_only": bool(cfg["source_map_only"]),
            "material_candidate_absolute_relaxation": float(
                cfg["material_candidate_absolute_relaxation"]
            ),
            "immutable_input_path": failed["input_state_path"],
            "immutable_input_sha256": spec.immutable_input_sha256,
            "authorized_output_path": failed["mapped_state_path"],
            "authorized_output_previous_sha256": (
                spec.authorized_output_previous_sha256
            ),
            "failed_iteration": 20,
            "previous_valid_residual": float(
                prior["global_original_operator_residual"]
            ),
            "maximum_concurrent_processes": 2,
            "natural_frequency_block_count": 76,
            "natural_frequency_block_width": spec.natural_frequency_block_width,
            "block_layout": layout,
            "runner_path": spec.runner_path,
            "manifest_path": spec.manifest_path,
            "report_directory": spec.report_directory,
            "summary_path": spec.summary_path,
        },
        "gates": dict(di_protocol["gates"]),
        "authorization": {
            "overwrite_only_failed_output_buffer": True,
            "immutable_input_may_be_modified": False,
            "single_block_repair_authorized": False,
            "all_76_blocks_must_be_freshly_written": True,
            "start_from_block_zero": True,
            "retain_all_block_reports": True,
            "compact_or_delete_reports": False,
            "failed_di_manifest_may_be_modified": False,
            "continuation_only_after_full_reproduction_passes": True,
        },
    }


def write_protocol(
    root: Path, spec: FullMapReproductionSpec, output_path: Path
) -> tuple[dict[str, object], str]:
    protocol = build_reproduction_protocol(root, spec)
    _write_json_atomic(output_path, protocol)
    return protocol, _sha256(output_path)


def _load_runtime_protocol(
    root: Path, protocol_path: Path, expected_hash: str
) -> dict[str, object]:
    if len(expected_hash) != 64 or _sha256(protocol_path) != expected_hash:
        raise RuntimeError("frozen 7B9dk protocol changed")
    protocol = _read_json(protocol_path)
    if protocol["configuration"].get("runner_path") != RUNNER_RELATIVE_PATH:
        raise RuntimeError("7B9dk runtime runner changed")
    for source in protocol["sources"].values():
        path = root / source["path"]
        if (
            path.stat().st_size != int(source["size_bytes"])
            or _sha256(path) != source["sha256"]
        ):
            raise RuntimeError(f"7B9dk source changed: {source['path']}")
    return protocol


def _shape(protocol: dict[str, object]) -> tuple[int, int, int]:
    cfg = protocol["configuration"]
    return (
        int(cfg["physical_frequency_groups"]),
        int(cfg["angular_direction_count"]),
        int(cfg["radiation_depth_cell_count"]),
    )


def _block_sha256(
    path: Path, shape: tuple[int, int, int], start: int, stop: int
) -> str:
    array = np.memmap(path, mode="r", dtype=np.float64, shape=shape)
    digest = hashlib.sha256(np.asarray(array[start:stop]).tobytes()).hexdigest()
    del array
    return digest


def initialize_manifest(
    root: Path, protocol_path: Path, expected_hash: str
) -> dict[str, object]:
    protocol = _load_runtime_protocol(root, protocol_path, expected_hash)
    cfg = protocol["configuration"]
    manifest_path = root / cfg["manifest_path"]
    input_path = root / cfg["immutable_input_path"]
    output_path = root / cfg["authorized_output_path"]
    expected_size = int(cfg["raw_float64_checkpoint_size_bytes"])
    if manifest_path.exists():
        manifest = _read_json(manifest_path)
        if manifest.get("protocol_sha256") != expected_hash:
            raise RuntimeError("7B9dk manifest belongs to another protocol")
        _validate_runtime_lineage(root, protocol, manifest)
        return manifest
    if input_path.resolve() == output_path.resolve() or os.path.samefile(input_path, output_path):
        raise RuntimeError("7B9dk A/B buffers alias")
    if input_path.stat().st_size != expected_size or output_path.stat().st_size != expected_size:
        raise RuntimeError("7B9dk A/B checkpoint size changed")
    if _sha256(input_path) != cfg["immutable_input_sha256"]:
        raise RuntimeError("7B9dk immutable A changed")
    if _sha256(output_path) != cfg["authorized_output_previous_sha256"]:
        raise RuntimeError("7B9dk authorized B changed before full reproduction")
    shape = _shape(protocol)
    previous_blocks = [
        {
            **row,
            "previous_block_sha256": _block_sha256(
                output_path,
                shape,
                int(row["core_group_start"]),
                int(row["core_group_stop"]),
            ),
        }
        for row in cfg["block_layout"]
    ]
    manifest = {
        "phase": protocol["phase"],
        "protocol_sha256": expected_hash,
        "status": "running",
        "immutable_input_path": cfg["immutable_input_path"],
        "immutable_input_sha256": cfg["immutable_input_sha256"],
        "authorized_output_path": cfg["authorized_output_path"],
        "authorized_output_previous_sha256": cfg[
            "authorized_output_previous_sha256"
        ],
        "previous_output_blocks": previous_blocks,
        "completed_blocks": [],
        "inflight_blocks": [],
        "accumulated_wall_runtime_s": 0.0,
    }
    _write_json_atomic(manifest_path, manifest)
    return manifest


def _validate_runtime_lineage(
    root: Path, protocol: dict[str, object], manifest: dict[str, object]
) -> None:
    cfg = protocol["configuration"]
    shape = _shape(protocol)
    input_path = root / manifest["immutable_input_path"]
    output_path = root / manifest["authorized_output_path"]
    if _sha256(input_path) != manifest["immutable_input_sha256"]:
        raise RuntimeError("7B9dk immutable A changed during recovery")
    previous = {
        int(row["block_index"]): row for row in manifest["previous_output_blocks"]
    }
    completed = {int(row["block_index"]): row for row in manifest["completed_blocks"]}
    for layout in cfg["block_layout"]:
        index = int(layout["block_index"])
        actual = _block_sha256(
            output_path,
            shape,
            int(layout["core_group_start"]),
            int(layout["core_group_stop"]),
        )
        expected = (
            completed[index]["new_block_sha256"]
            if index in completed
            else previous[index]["previous_block_sha256"]
        )
        if actual != expected:
            raise RuntimeError(f"7B9dk output block {index} has uncommitted bytes")


def _worker(
    protocol_path: Path,
    expected_hash: str,
    block_index: int,
    input_state: Path,
    input_sha256: str,
    output_state: Path,
    report_path: Path,
) -> None:
    protocol = _load_runtime_protocol(ROOT, protocol_path, expected_hash)
    fixed = _read_json(ROOT / protocol["sources"]["finite_trial_protocol"]["path"])
    if fixed["sources"]["current_material_state"] != protocol["sources"]["finite_trial_material"]:
        raise RuntimeError("7B9dk fixed material changed")
    generic = engine.generic
    original = generic.base.phase7b9i._load_protocol
    try:
        generic.base.phase7b9i._load_protocol = lambda _path, validate_sources=False: fixed
        engine.EXPECTED_PROTOCOL_SHA256 = expected_hash
        generic.EXPECTED_PROTOCOL_SHA256 = expected_hash
        engine._run_worker(
            protocol_path,
            20,
            block_index,
            input_state,
            input_sha256,
            output_state,
            report_path,
        )
    finally:
        generic.base.phase7b9i._load_protocol = original


BatchExecutor = Callable[
    [list[int], Path, str, Path, list[Path]], list[dict[str, object]]
]


def _default_batch_executor(
    protocol_path: Path, expected_hash: str
) -> BatchExecutor:
    def execute(
        indices: list[int],
        input_path: Path,
        input_sha: str,
        output_path: Path,
        report_paths: list[Path],
    ) -> list[dict[str, object]]:
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT / RUNNER_RELATIVE_PATH),
                    "--worker",
                    "--protocol",
                    str(protocol_path),
                    "--expected-protocol-sha256",
                    expected_hash,
                    "--block-index",
                    str(index),
                    "--input-state",
                    str(input_path),
                    "--input-sha256",
                    input_sha,
                    "--output-state",
                    str(output_path),
                    "--worker-report",
                    str(report_path),
                ],
                cwd=ROOT,
            )
            for index, report_path in zip(indices, report_paths, strict=True)
        ]
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"7B9dk worker batch failed: {codes}")
        return [_read_json(path) for path in report_paths]

    return execute


def _aggregate_and_decide(
    protocol: dict[str, object], reports: list[dict[str, object]], wall: float
) -> tuple[dict[str, object], dict[str, bool], dict[str, bool]]:
    metrics = engine._aggregate(reports, _shape(protocol))
    metrics["block_report_count"] = len(reports)
    metrics["full_map_wall_runtime_s"] = wall
    cfg = protocol["configuration"]
    gates = protocol["gates"]
    contraction = float(metrics["global_original_operator_residual"]) / float(
        cfg["previous_valid_residual"]
    )
    metrics["contraction_ratio"] = contraction
    progression = {
        "frequency_ownership_pass": bool(
            len(reports) == 76
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
        "contraction_pass": contraction
        < gates["subsequent_residual_contraction_ratio_below"],
        "resources_pass": bool(
            metrics["maximum_process_peak_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and metrics["maximum_worker_wall_runtime_s"]
            < gates["each_worker_wall_time_strictly_below_s"]
            and wall < gates["each_full_map_wall_time_strictly_below_s"]
        ),
    }
    convergence = {
        "residual_pass": metrics["global_original_operator_residual"]
        < gates["global_original_operator_residual_below"],
        "boundary_spectrum_pass": metrics["boundary_spectrum_l1"]
        < gates["global_boundary_spectrum_l1_below"],
        "boundary_bolometric_pass": metrics["boundary_bolometric_fraction"]
        < gates["global_boundary_bolometric_fraction_below"],
    }
    return metrics, progression, convergence


def run_reproduction(
    root: Path,
    protocol_path: Path,
    expected_hash: str,
    *,
    batch_executor: BatchExecutor | None = None,
) -> dict[str, object]:
    protocol = _load_runtime_protocol(root, protocol_path, expected_hash)
    cfg = protocol["configuration"]
    manifest_path = root / cfg["manifest_path"]
    manifest = initialize_manifest(root, protocol_path, expected_hash)
    if manifest["status"] != "running":
        return _read_json(root / cfg["summary_path"])
    if manifest.get("inflight_blocks"):
        raise RuntimeError("7B9dk stopped with an uncommitted worker batch")
    input_path = root / cfg["immutable_input_path"]
    output_path = root / cfg["authorized_output_path"]
    report_dir = root / cfg["report_directory"]
    report_dir.mkdir(parents=True, exist_ok=True)
    shape = _shape(protocol)
    previous = {
        int(row["block_index"]): row for row in manifest["previous_output_blocks"]
    }
    execute = batch_executor or _default_batch_executor(protocol_path, expected_hash)
    completed = {int(row["block_index"]) for row in manifest["completed_blocks"]}
    pending = [index for index in range(76) if index not in completed]
    for offset in range(0, len(pending), 2):
        batch = pending[offset : offset + 2]
        manifest["inflight_blocks"] = batch
        _write_json_atomic(manifest_path, manifest)
        paths = [report_dir / f"phase7b9dk_block{index:02d}.json" for index in batch]
        started = time.perf_counter()
        rows = execute(
            batch,
            input_path,
            str(cfg["immutable_input_sha256"]),
            output_path,
            paths,
        )
        manifest["accumulated_wall_runtime_s"] += time.perf_counter() - started
        if len(rows) != len(batch):
            raise RuntimeError("7B9dk worker batch report count changed")
        for index, path, row in zip(batch, paths, rows, strict=True):
            layout = cfg["block_layout"][index]
            if (
                int(row.get("block_index", -1)) != index
                or int(row.get("picard_iteration", -1)) != 20
                or row.get("protocol_sha256") != expected_hash
                or int(row.get("core_group_start", -1))
                != int(layout["core_group_start"])
                or int(row.get("core_group_stop", -1))
                != int(layout["core_group_stop"])
            ):
                raise RuntimeError("7B9dk worker report lineage changed")
            enriched = dict(row)
            enriched["previous_block_sha256"] = previous[index][
                "previous_block_sha256"
            ]
            enriched["new_block_sha256"] = _block_sha256(
                output_path,
                shape,
                int(layout["core_group_start"]),
                int(layout["core_group_stop"]),
            )
            _write_json_atomic(path, enriched)
            manifest["completed_blocks"].append(enriched)
        manifest["completed_blocks"].sort(key=lambda row: int(row["block_index"]))
        manifest["inflight_blocks"] = []
        _write_json_atomic(manifest_path, manifest)
    reports = list(manifest["completed_blocks"])
    metrics, progression, convergence = _aggregate_and_decide(
        protocol, reports, float(manifest["accumulated_wall_runtime_s"])
    )
    fresh_hash = _sha256(output_path)
    block_comparison_pass = bool(
        [int(row["block_index"]) for row in reports] == list(range(76))
        and all(
            row["previous_block_sha256"]
            == previous[int(row["block_index"])]["previous_block_sha256"]
            and row["new_block_sha256"]
            == _block_sha256(
                output_path,
                shape,
                int(row["core_group_start"]),
                int(row["core_group_stop"]),
            )
            for row in reports
        )
    )
    fresh_differs_failed = fresh_hash != cfg["authorized_output_previous_sha256"]
    boundary_pass = bool(
        convergence["boundary_spectrum_pass"]
        and convergence["boundary_bolometric_pass"]
    )
    reproduction_passed = bool(
        all(progression.values())
        and boundary_pass
        and block_comparison_pass
        and fresh_differs_failed
    )
    convergence_passed = reproduction_passed and convergence["residual_pass"]
    manifest.update(
        {
            "status": "reproduction_passed" if reproduction_passed else "gate_failed",
            "fresh_output_sha256": fresh_hash,
            "metrics": metrics,
            "progression_gate_checks": progression,
            "convergence_gate_checks": convergence,
            "block_comparison_passed": block_comparison_pass,
            "fresh_output_differs_failed_output": fresh_differs_failed,
            "reproduction_passed": reproduction_passed,
            "convergence_passed": convergence_passed,
        }
    )
    _write_json_atomic(manifest_path, manifest)
    summary = {
        "phase": protocol["phase"],
        "protocol_sha256": expected_hash,
        "status": manifest["status"],
        "immutable_input_path": cfg["immutable_input_path"],
        "immutable_input_sha256": cfg["immutable_input_sha256"],
        "fresh_output_path": cfg["authorized_output_path"],
        "fresh_output_sha256": fresh_hash,
        "failed_output_previous_sha256": cfg["authorized_output_previous_sha256"],
        "block_report_count": len(reports),
        "block_reports_retained": True,
        "metrics": metrics,
        "progression_gate_checks": progression,
        "convergence_gate_checks": convergence,
        "decision": {
            "full_76_block_reproduction_passed": reproduction_passed,
            "fresh_state_authorized_as_continuation_input": reproduction_passed,
            "already_converged": convergence_passed,
            "single_block_repair_used": False,
            "failed_di_manifest_modified": False,
        },
    }
    _write_json_atomic(root / cfg["summary_path"], summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    protocol_path = Path(args.protocol).resolve()
    if args.worker:
        if None in (
            args.block_index,
            args.input_state,
            args.input_sha256,
            args.output_state,
            args.worker_report,
        ):
            raise RuntimeError("7B9dk worker arguments are incomplete")
        _worker(
            protocol_path,
            args.expected_protocol_sha256,
            int(args.block_index),
            args.input_state,
            str(args.input_sha256),
            args.output_state,
            args.worker_report,
        )
    else:
        summary = run_reproduction(
            ROOT, protocol_path, args.expected_protocol_sha256
        )
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
