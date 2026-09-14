"""Phase 7B9aq：可恢复地准备 x1、x2、x3 三个全局连续辐射态。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

try:
    from scripts import phase7b9ac_global_positive_picard_map as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ac_global_positive_picard_map as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "2119ae87aaf9157ad663e98a5563371f0732cec1b07495a23ea98831e25becf9"
)
base = generic.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9aq protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9aq source changed: {source['path']}"
                )
    return protocol


def _shape(configuration: dict[str, object]) -> tuple[int, int, int]:
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _run_worker(
    protocol_path: Path,
    block_index: int,
    input_state: Path,
    input_sha256: str,
    output_state: Path,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    dynamic = json.loads(json.dumps(protocol))
    dynamic["configuration"]["input_state_path"] = str(
        input_state.resolve().relative_to(ROOT)
    )
    dynamic["configuration"]["input_state_sha256"] = input_sha256
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    generic._load_protocol = lambda _path, validate_sources=False: dynamic
    generic._run_worker(protocol_path, block_index, output_state, report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["stage"] = "x2_to_x3_map"
    _write_json_atomic(report_path, report)


def _aggregate(
    reports: list[dict[str, object]], shape: tuple[int, int, int]
) -> dict[str, object]:
    ownership = np.zeros(shape[0], dtype=np.int8)
    for row in reports:
        ownership[int(row["core_group_start"]) : int(row["core_group_stop"])] += 1
    maximum_change = max(
        float(row["maximum_absolute_radiation_change"]) for row in reports
    )
    maximum_scale = max(float(row["maximum_radiation_scale"]) for row in reports)
    numerator = sum(
        float(row["boundary_spectrum_l1_numerator"]) for row in reports
    )
    current_scale = sum(
        float(row["current_boundary_absolute_scale"]) for row in reports
    )
    mapped_scale = sum(
        float(row["mapped_boundary_absolute_scale"]) for row in reports
    )
    current_bolometric = sum(
        float(row["current_boundary_bolometric"]) for row in reports
    )
    mapped_bolometric = sum(
        float(row["mapped_boundary_bolometric"]) for row in reports
    )
    return {
        "frequency_ownership_count": int(np.sum(ownership)),
        "frequency_ownership_exact": bool(np.all(ownership == 1)),
        "x2_global_original_operator_residual": maximum_change / maximum_scale,
        "x2_boundary_spectrum_l1": numerator / max(current_scale, mapped_scale),
        "x2_boundary_bolometric_fraction": abs(
            mapped_bolometric - current_bolometric
        )
        / max(abs(current_bolometric), abs(mapped_bolometric)),
        "minimum_x2_intensity": min(
            float(row["minimum_input_intensity"]) for row in reports
        ),
        "minimum_x3_intensity": min(
            float(row["minimum_mapped_intensity"]) for row in reports
        ),
        "maximum_process_peak_rss_mib": max(
            float(row["peak_process_rss_mib"]) for row in reports
        ),
        "maximum_worker_wall_runtime_s": max(
            float(row["wall_runtime_s"]) for row in reports
        ),
    }


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    shape = _shape(configuration)
    source = ROOT / configuration["x1_source_path"]
    preserved = ROOT / configuration["x1_preserved_path"]
    x2 = ROOT / configuration["x2_state_path"]
    x3 = ROOT / configuration["x3_output_path"]
    manifest_path = ROOT / configuration["manifest_path"]
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
            raise RuntimeError("Phase 7B9aq manifest belongs to another protocol")
    else:
        if (
            base._sha256(source) != configuration["x1_source_sha256"]
            or base._sha256(preserved)
            != configuration["x1_preserved_previous_sha256"]
        ):
            raise RuntimeError("Phase 7B9aq initial copy buffers changed")
        manifest = {
            "phase": protocol["phase"],
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "status": "copying_x1",
            "copy_completed_blocks": [],
            "copy_wall_runtime_s": 0.0,
            "map_completed_blocks": [],
            "map_wall_runtime_s": 0.0,
        }
        _write_json_atomic(manifest_path, manifest)
    copy_completed = {
        int(row["block_index"]): row for row in manifest["copy_completed_blocks"]
    }
    for index, row in copy_completed.items():
        start = index * 128
        stop = min((index + 1) * 128, shape[0])
        if (
            base.phase7b9d._block_sha256(preserved, shape, start, stop)
            != row["preserved_block_sha256"]
        ):
            raise RuntimeError("Phase 7B9aq preserved x1 block changed")
    if manifest["status"] == "copying_x1":
        source_map = np.memmap(source, mode="r", dtype=np.float64, shape=shape)
        preserved_map = np.memmap(preserved, mode="r+", dtype=np.float64, shape=shape)
        started = time.perf_counter()
        for index in range(76):
            if index in copy_completed:
                continue
            start = index * 128
            stop = min((index + 1) * 128, shape[0])
            if (
                base.phase7b9d._block_sha256(preserved, shape, start, stop)
                != configuration["x1_preserved_previous_block_sha256"][index]
            ):
                raise RuntimeError("Phase 7B9aq uncopied reuse block changed")
            preserved_map[start:stop] = source_map[start:stop]
            preserved_map.flush()
            row = {
                "block_index": index,
                "preserved_block_sha256": base.phase7b9d._block_sha256(
                    preserved, shape, start, stop
                ),
            }
            manifest["copy_completed_blocks"].append(row)
            manifest["copy_completed_blocks"].sort(
                key=lambda value: int(value["block_index"])
            )
            manifest["copy_wall_runtime_s"] = float(
                manifest["copy_wall_runtime_s"]
            ) + (time.perf_counter() - started)
            started = time.perf_counter()
            _write_json_atomic(manifest_path, manifest)
        del source_map, preserved_map
        if base._sha256(preserved) != configuration["x1_source_sha256"]:
            raise RuntimeError("Phase 7B9aq preserved x1 full hash differs")
        manifest["status"] = "mapping_x2_to_x3"
        _write_json_atomic(manifest_path, manifest)
    if manifest["status"] == "mapping_x2_to_x3":
        reports_by_block = {
            int(row["block_index"]): row for row in manifest["map_completed_blocks"]
        }
        for row in reports_by_block.values():
            if (
                base.phase7b9d._block_sha256(
                    x3,
                    shape,
                    int(row["core_group_start"]),
                    int(row["core_group_stop"]),
                )
                != row["output_block_sha256"]
            ):
                raise RuntimeError("Phase 7B9aq completed x3 block changed")
        report_dir = ROOT / configuration["report_directory"]
        report_dir.mkdir(parents=True, exist_ok=True)
        pending = [index for index in range(76) if index not in reports_by_block]
        concurrency = int(configuration["maximum_concurrent_processes"])
        for offset in range(0, len(pending), concurrency):
            batch = pending[offset : offset + concurrency]
            started = time.perf_counter()
            paths = [report_dir / f"phase7b9aq_block{index:02d}.json" for index in batch]
            processes = [
                subprocess.Popen(
                    [
                        sys.executable,
                        str(ROOT / configuration["runner_path"]),
                        "--worker",
                        "--protocol",
                        str(protocol_path),
                        "--block-index",
                        str(index),
                        "--input-state",
                        str(x2),
                        "--input-sha256",
                        configuration["x2_state_sha256"],
                        "--output-state",
                        str(x3),
                        "--worker-report",
                        str(path),
                    ],
                    cwd=ROOT,
                )
                for index, path in zip(batch, paths, strict=True)
            ]
            codes = [process.wait() for process in processes]
            if any(code != 0 for code in codes):
                raise RuntimeError(f"Phase 7B9aq map batch failed: {codes}")
            for index, path in zip(batch, paths, strict=True):
                row = json.loads(path.read_text(encoding="utf-8"))
                if (
                    row.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256
                    or int(row.get("block_index", -1)) != index
                    or row.get("stage") != "x2_to_x3_map"
                ):
                    raise RuntimeError("Phase 7B9aq worker report changed")
                row["output_block_sha256"] = base.phase7b9d._block_sha256(
                    x3,
                    shape,
                    int(row["core_group_start"]),
                    int(row["core_group_stop"]),
                )
                manifest["map_completed_blocks"].append(row)
            manifest["map_completed_blocks"].sort(
                key=lambda value: int(value["block_index"])
            )
            manifest["map_wall_runtime_s"] = float(
                manifest["map_wall_runtime_s"]
            ) + (time.perf_counter() - started)
            _write_json_atomic(manifest_path, manifest)
            print(
                json.dumps(
                    {
                        "completed_blocks": len(manifest["map_completed_blocks"]),
                        "total_blocks": 76,
                        "latest_blocks": batch,
                    }
                ),
                flush=True,
            )
        reports = list(manifest["map_completed_blocks"])
        metrics = _aggregate(reports, shape)
        checks = {
            "frequency_ownership_pass": len(reports) == gates["block_count_exactly"]
            and metrics["frequency_ownership_count"]
            == gates["owned_frequency_group_count_exactly"]
            and metrics["frequency_ownership_exact"],
            "positive_states_pass": metrics["minimum_x2_intensity"]
            >= gates["minimum_intensity_at_least"]
            and metrics["minimum_x3_intensity"]
            >= gates["minimum_intensity_at_least"],
            "boundary_pass": metrics["x2_boundary_spectrum_l1"]
            < gates["global_boundary_spectrum_l1_below"]
            and metrics["x2_boundary_bolometric_fraction"]
            < gates["global_boundary_bolometric_fraction_below"],
            "resources_pass": metrics["maximum_process_peak_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and metrics["maximum_worker_wall_runtime_s"]
            < gates["each_worker_wall_time_strictly_below_s"]
            and manifest["map_wall_runtime_s"]
            < gates["map_wall_time_strictly_below_s"]
            and manifest["copy_wall_runtime_s"]
            < gates["copy_wall_time_strictly_below_s"],
        }
        passed = all(checks.values())
        x3_sha = base._sha256(x3)
        manifest["status"] = "complete" if passed else "gate_failed"
        manifest["x3_state_sha256"] = x3_sha
        _write_json_atomic(manifest_path, manifest)
        summary = {
            "phase": protocol["phase"],
            "classification": "[A-preregistered]+[V]+[O]",
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "x1_state_path": configuration["x1_preserved_path"],
            "x1_state_sha256": configuration["x1_source_sha256"],
            "x2_state_path": configuration["x2_state_path"],
            "x2_state_sha256": configuration["x2_state_sha256"],
            "x3_state_path": configuration["x3_output_path"],
            "x3_state_sha256": x3_sha,
            "x1_global_original_operator_residual": protocol["reference"][
                "x1_global_residual"
            ],
            **metrics,
            "gate_checks": checks,
            "decision": {
                "anderson_triple_preparation_passed": passed,
                "global_anderson_depth_two_authorized": passed,
                "material_feedback_authorized": False,
            },
        }
        _write_json_atomic(ROOT / configuration["summary_path"], summary)
        print(json.dumps(summary, indent=2))
        return summary
    return json.loads((ROOT / configuration["summary_path"]).read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9aq_preregistered_anderson_triple.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if (
            args.block_index is None
            or args.input_state is None
            or args.input_sha256 is None
            or args.output_state is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires block, states and report")
        _run_worker(
            args.protocol,
            args.block_index,
            args.input_state,
            args.input_sha256,
            args.output_state,
            args.worker_report,
        )
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
