"""Phase 7B9ar：计算全局 Anderson 深度 2 系数并存储 x4。"""

from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

import numpy as np

try:
    from scripts import phase7b9ak_global_convex_krylov_line as affine
    from scripts import phase7b9ac_global_positive_picard_map as map_generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ak_global_convex_krylov_line as affine  # type: ignore[no-redef]
    import phase7b9ac_global_positive_picard_map as map_generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "0b5e5461a1b0e45b711d349823a3ae42aa5a06988f863759e09c289871b86083"
)
MIB = 1024**2
base = affine.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9ar protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9ar source changed: {source['path']}"
                )
    return protocol


def _shape(configuration: dict[str, object]) -> tuple[int, int, int]:
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _context(
    protocol: dict[str, object], x3_path: Path
) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    finite = base.phase7b9i._load_protocol(
        ROOT / protocol["sources"]["finite_trial_protocol"]["path"],
        validate_sources=False,
    )
    base.phase7b9d._configure_worker(finite, x3_path)
    template = base.phase7b7i._load_protocol(
        ROOT / protocol["sources"]["finite_trial_protocol"]["path"],
        validate_sources=False,
    )
    return (
        base.phase7b7i.phase7b7e.phase7b5x._context(template),
        base.phase7b7i._second_full_material(template),
    )


def _run_coefficient_worker(
    protocol_path: Path, block_index: int, report_path: Path
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    configuration = protocol["configuration"]
    shape = _shape(configuration)
    x3_path = ROOT / configuration["x3_state_path"]
    context, material = _context(protocol, x3_path)
    block = context["blocks"][block_index]
    baseline = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    x3, x4 = affine._evaluate_state(
        x3_path,
        shape,
        context,
        block,
        material,
        configuration["spatial_scheme"],
    )
    core = slice(block.core_group_start, block.core_group_stop)
    x1_global = np.memmap(
        ROOT / configuration["x1_state_path"], mode="r", dtype=np.float64, shape=shape
    )
    x2_global = np.memmap(
        ROOT / configuration["x2_state_path"], mode="r", dtype=np.float64, shape=shape
    )
    x1 = np.array(x1_global[core], copy=True)
    x2 = np.array(x2_global[core], copy=True)
    del x1_global, x2_global, material
    residual = [x2 - x1, x3 - x2, x4 - x3]
    gram = np.empty((3, 3), dtype=np.float64)
    for i in range(3):
        for j in range(i, 3):
            value = float(np.sum(residual[i] * residual[j], dtype=np.float64))
            gram[i, j] = value
            gram[j, i] = value
    edge = np.asarray(context["stencil"].active_lab_edge_hz)
    width = np.diff(edge)[core]
    mu = np.asarray(context["mu"])
    weight = np.asarray(context["weight"])
    x3_flux = base._block_flux(x3, mu, weight, width)
    x4_flux = base._block_flux(x4, mu, weight, width)
    peak = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "stage": "coefficient",
        "block_index": block_index,
        "core_group_start": int(block.core_group_start),
        "core_group_stop": int(block.core_group_stop),
        "gram_matrix": gram.tolist(),
        "x3_maximum_absolute_change": float(np.max(np.abs(x4 - x3))),
        "x3_maximum_scale": max(
            float(np.max(np.abs(x3))), float(np.max(np.abs(x4)))
        ),
        "boundary_spectrum_l1_numerator": float(
            np.sum(np.abs(x4_flux - x3_flux))
        ),
        "current_boundary_absolute_scale": float(np.sum(np.abs(x3_flux))),
        "mapped_boundary_absolute_scale": float(np.sum(np.abs(x4_flux))),
        "current_boundary_bolometric": float(np.sum(x3_flux)),
        "mapped_boundary_bolometric": float(np.sum(x4_flux)),
        "minimum_x3_intensity": float(np.min(x3)),
        "minimum_x4_intensity": float(np.min(x4)),
        "baseline_highwater_rss_mib": baseline / MIB,
        "peak_process_rss_mib": peak / MIB,
        "wall_runtime_s": time.perf_counter() - started,
    }
    del x1, x2, x3, x4, residual
    gc.collect()
    _write_json_atomic(report_path, report)


def _run_x4_worker(
    protocol_path: Path,
    block_index: int,
    output_state: Path,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    dynamic = json.loads(json.dumps(protocol))
    configuration = dynamic["configuration"]
    configuration["input_state_path"] = configuration["x3_state_path"]
    configuration["input_state_sha256"] = configuration["x3_state_sha256"]
    map_generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    map_generic._load_protocol = lambda _path, validate_sources=False: dynamic
    map_generic._run_worker(protocol_path, block_index, output_state, report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["stage"] = "x4_map"
    _write_json_atomic(report_path, report)


def _aggregate_map(
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
        "x3_global_original_operator_residual": maximum_change / maximum_scale,
        "x3_boundary_spectrum_l1": numerator / max(current_scale, mapped_scale),
        "x3_boundary_bolometric_fraction": abs(
            mapped_bolometric - current_bolometric
        )
        / max(abs(current_bolometric), abs(mapped_bolometric)),
        "minimum_x3_intensity": min(
            float(row["minimum_input_intensity"]) for row in reports
        ),
        "minimum_x4_intensity": min(
            float(row["minimum_mapped_intensity"]) for row in reports
        ),
        "maximum_process_peak_rss_mib": max(
            float(row["peak_process_rss_mib"]) for row in reports
        ),
        "maximum_worker_wall_runtime_s": max(
            float(row["wall_runtime_s"]) for row in reports
        ),
    }


def _coefficient_metrics(reports: list[dict[str, object]]) -> dict[str, object]:
    gram = sum(
        (np.asarray(row["gram_matrix"], dtype=np.float64) for row in reports),
        start=np.zeros((3, 3), dtype=np.float64),
    )
    condition = float(np.linalg.cond(gram))
    kkt = np.zeros((4, 4), dtype=np.float64)
    kkt[:3, :3] = 2.0 * gram
    kkt[:3, 3] = 1.0
    kkt[3, :3] = 1.0
    rhs = np.array([0.0, 0.0, 0.0, 1.0])
    solution = np.linalg.solve(kkt, rhs)
    alpha = solution[:3]
    maximum_change = max(float(row["x3_maximum_absolute_change"]) for row in reports)
    maximum_scale = max(float(row["x3_maximum_scale"]) for row in reports)
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
        "gram_matrix": gram.tolist(),
        "gram_condition_number": condition,
        "anderson_alpha": alpha.tolist(),
        "alpha_sum_absolute_error": abs(float(np.sum(alpha)) - 1.0),
        "predicted_unweighted_l2_residual_squared": float(alpha @ gram @ alpha),
        "coefficient_pass_x3_global_residual": maximum_change / maximum_scale,
        "coefficient_pass_x3_boundary_spectrum_l1": numerator
        / max(current_scale, mapped_scale),
        "coefficient_pass_x3_boundary_bolometric_fraction": abs(
            mapped_bolometric - current_bolometric
        )
        / max(abs(current_bolometric), abs(mapped_bolometric)),
        "minimum_x3_intensity": min(
            float(row["minimum_x3_intensity"]) for row in reports
        ),
        "minimum_x4_intensity": min(
            float(row["minimum_x4_intensity"]) for row in reports
        ),
    }


def _run_parallel(
    protocol_path: Path,
    protocol: dict[str, object],
    manifest: dict[str, object],
    *,
    stage: str,
    output_state: Path | None,
) -> list[dict[str, object]]:
    configuration = protocol["configuration"]
    reports_by_block = {
        int(row["block_index"]): row for row in manifest[f"{stage}_reports"]
    }
    shape = _shape(configuration)
    if output_state is not None:
        for row in reports_by_block.values():
            if (
                base.phase7b9d._block_sha256(
                    output_state,
                    shape,
                    int(row["core_group_start"]),
                    int(row["core_group_stop"]),
                )
                != row["output_block_sha256"]
            ):
                raise RuntimeError("Phase 7B9ar completed x4 block changed")
    pending = [index for index in range(76) if index not in reports_by_block]
    directory = ROOT / configuration[f"{stage}_report_directory"]
    directory.mkdir(parents=True, exist_ok=True)
    concurrency = int(configuration["maximum_concurrent_processes"])
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        started = time.perf_counter()
        paths = [directory / f"phase7b9ar_{stage}_block{index:02d}.json" for index in batch]
        processes = []
        for index, path in zip(batch, paths, strict=True):
            command = [
                sys.executable,
                str(ROOT / configuration["runner_path"]),
                f"--{stage}-worker",
                "--protocol",
                str(protocol_path),
                "--block-index",
                str(index),
                "--worker-report",
                str(path),
            ]
            if output_state is not None:
                command.extend(["--output-state", str(output_state)])
            processes.append(subprocess.Popen(command, cwd=ROOT))
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"Phase 7B9ar {stage} batch failed: {codes}")
        for index, path in zip(batch, paths, strict=True):
            row = json.loads(path.read_text(encoding="utf-8"))
            if (
                row.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256
                or int(row.get("block_index", -1)) != index
                or row.get("stage") != ("coefficient" if stage == "coefficient" else "x4_map")
            ):
                raise RuntimeError("Phase 7B9ar worker report changed")
            if output_state is not None:
                row["output_block_sha256"] = base.phase7b9d._block_sha256(
                    output_state,
                    shape,
                    int(row["core_group_start"]),
                    int(row["core_group_stop"]),
                )
            manifest[f"{stage}_reports"].append(row)
        manifest[f"{stage}_reports"].sort(key=lambda value: int(value["block_index"]))
        manifest[f"{stage}_wall_runtime_s"] = float(
            manifest[f"{stage}_wall_runtime_s"]
        ) + (time.perf_counter() - started)
        _write_json_atomic(ROOT / configuration["manifest_path"], manifest)
        print(
            json.dumps(
                {
                    "stage": stage,
                    "completed_blocks": len(manifest[f"{stage}_reports"]),
                    "total_blocks": 76,
                    "latest_blocks": batch,
                }
            ),
            flush=True,
        )
    return list(manifest[f"{stage}_reports"])


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    manifest_path = ROOT / configuration["manifest_path"]
    x4_path = ROOT / configuration["x4_output_path"]
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
            raise RuntimeError("Phase 7B9ar manifest belongs to another protocol")
    else:
        if base._sha256(x4_path) != configuration["x1_state_sha256"]:
            raise RuntimeError("Phase 7B9ar x4 reuse buffer changed")
        manifest = {
            "phase": protocol["phase"],
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "status": "coefficient",
            "coefficient_reports": [],
            "coefficient_wall_runtime_s": 0.0,
            "x4_reports": [],
            "x4_wall_runtime_s": 0.0,
        }
        _write_json_atomic(manifest_path, manifest)
    coefficient_reports = _run_parallel(
        protocol_path,
        protocol,
        manifest,
        stage="coefficient",
        output_state=None,
    )
    coefficients = _coefficient_metrics(coefficient_reports)
    coefficient_ownership = np.zeros(
        int(configuration["physical_frequency_groups"]), dtype=np.int8
    )
    for report in coefficient_reports:
        coefficient_ownership[
            int(report["core_group_start"]) : int(report["core_group_stop"])
        ] += 1
    coefficient_checks = {
        "frequency_ownership_pass": len(coefficient_reports)
        == gates["block_count_exactly"]
        and int(np.sum(coefficient_ownership))
        == gates["owned_frequency_group_count_exactly"]
        and bool(np.all(coefficient_ownership == 1)),
        "gram_condition_pass": coefficients["gram_condition_number"]
        < gates["gram_condition_number_below"],
        "finite_coefficients_pass": bool(
            np.all(np.isfinite(coefficients["anderson_alpha"]))
        ),
        "coefficient_sum_pass": coefficients["alpha_sum_absolute_error"]
        < gates["coefficient_sum_absolute_error_below"],
        "positive_endpoint_pass": coefficients["minimum_x3_intensity"]
        >= gates["minimum_x3_and_x4_intensity_at_least"]
        and coefficients["minimum_x4_intensity"]
        >= gates["minimum_x3_and_x4_intensity_at_least"],
        "resources_pass": all(
            float(row["peak_process_rss_mib"])
            < gates["each_process_peak_rss_strictly_below_mib"]
            and float(row["wall_runtime_s"])
            < gates["coefficient_worker_wall_time_strictly_below_s"]
            for row in coefficient_reports
        )
        and manifest["coefficient_wall_runtime_s"]
        < gates["each_stage_wall_time_strictly_below_s"],
    }
    _write_json_atomic(
        ROOT / configuration["coefficient_path"],
        {
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            **coefficients,
            "gate_checks": coefficient_checks,
        },
    )
    if not all(coefficient_checks.values()):
        manifest["status"] = "coefficient_gate_failed"
        _write_json_atomic(manifest_path, manifest)
        raise RuntimeError("Phase 7B9ar coefficient gate failed")
    manifest["status"] = "x4_map"
    _write_json_atomic(manifest_path, manifest)
    x4_reports = _run_parallel(
        protocol_path,
        protocol,
        manifest,
        stage="x4",
        output_state=x4_path,
    )
    map_metrics = _aggregate_map(x4_reports, _shape(configuration))
    map_checks = {
        "frequency_ownership_pass": len(x4_reports) == gates["block_count_exactly"]
        and map_metrics["frequency_ownership_count"]
        == gates["owned_frequency_group_count_exactly"]
        and map_metrics["frequency_ownership_exact"],
        "positive_states_pass": map_metrics["minimum_x3_intensity"]
        >= gates["minimum_x3_and_x4_intensity_at_least"]
        and map_metrics["minimum_x4_intensity"]
        >= gates["minimum_x3_and_x4_intensity_at_least"],
        "coefficient_pass_reproduction_pass": abs(
            map_metrics["x3_global_original_operator_residual"]
            - coefficients["coefficient_pass_x3_global_residual"]
        )
        <= gates["x3_residual_reproduction_absolute_tolerance"]
        and abs(
            map_metrics["x3_boundary_spectrum_l1"]
            - coefficients["coefficient_pass_x3_boundary_spectrum_l1"]
        )
        <= gates["x3_residual_reproduction_absolute_tolerance"]
        and abs(
            map_metrics["x3_boundary_bolometric_fraction"]
            - coefficients["coefficient_pass_x3_boundary_bolometric_fraction"]
        )
        <= gates["x3_residual_reproduction_absolute_tolerance"],
        "boundary_pass": map_metrics["x3_boundary_spectrum_l1"]
        < gates["global_boundary_spectrum_l1_below"]
        and map_metrics["x3_boundary_bolometric_fraction"]
        < gates["global_boundary_bolometric_fraction_below"],
        "resources_pass": all(
            float(row["peak_process_rss_mib"])
            < gates["each_process_peak_rss_strictly_below_mib"]
            and float(row["wall_runtime_s"])
            < gates["x4_worker_wall_time_strictly_below_s"]
            for row in x4_reports
        )
        and manifest["x4_wall_runtime_s"]
        < gates["each_stage_wall_time_strictly_below_s"],
    }
    passed = all(map_checks.values())
    x4_sha = base._sha256(x4_path)
    manifest["status"] = "complete" if passed else "x4_gate_failed"
    manifest["x4_state_sha256"] = x4_sha
    _write_json_atomic(manifest_path, manifest)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "x2_state_path": configuration["x2_state_path"],
        "x2_state_sha256": configuration["x2_state_sha256"],
        "x3_state_path": configuration["x3_state_path"],
        "x3_state_sha256": configuration["x3_state_sha256"],
        "x4_state_path": configuration["x4_output_path"],
        "x4_state_sha256": x4_sha,
        **coefficients,
        **map_metrics,
        "coefficient_gate_checks": coefficient_checks,
        "x4_map_gate_checks": map_checks,
        "decision": {
            "global_anderson_coefficients_passed": all(
                coefficient_checks.values()
            ),
            "x4_storage_passed": passed,
            "maximum_norm_and_positivity_candidate_audit_authorized": passed,
            "material_feedback_authorized": False,
        },
    }
    _write_json_atomic(ROOT / configuration["summary_path"], summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9ar_preregistered_global_anderson_coefficients.json",
    )
    parser.add_argument("--coefficient-worker", action="store_true")
    parser.add_argument("--x4-worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.coefficient_worker:
        if args.block_index is None or args.worker_report is None:
            raise ValueError("coefficient worker requires block and report")
        _run_coefficient_worker(args.protocol, args.block_index, args.worker_report)
        return
    if args.x4_worker:
        if (
            args.block_index is None
            or args.output_state is None
            or args.worker_report is None
        ):
            raise ValueError("x4 worker requires block, output and report")
        _run_x4_worker(
            args.protocol, args.block_index, args.output_state, args.worker_report
        )
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
