"""Phase 7B9ay：融合计算 x4、Gram 矩阵与正性约束 Anderson 系数。"""

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
from scipy.optimize import minimize

try:
    from scripts import phase7b9ar_global_anderson_coefficients as engine
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ar_global_anderson_coefficients as engine  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = "dbf7433fa23623bf9531855871da5ebccad3d68274f7dca1a9ff6e000afdf8a1"
MIB = 1024**2
base = engine.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9ay protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(f"frozen Phase 7B9ay source changed: {source['path']}")
    return protocol


def _shape(configuration: dict[str, object]) -> tuple[int, int, int]:
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _run_worker(
    protocol_path: Path, block_index: int, output_state: Path, report_path: Path
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    configuration = protocol["configuration"]
    shape = _shape(configuration)
    x3_path = ROOT / configuration["x3_state_path"]
    context, material = engine._context(protocol, x3_path)
    block = context["blocks"][block_index]
    core = slice(block.core_group_start, block.core_group_stop)
    if (
        base.phase7b9d._block_sha256(
            output_state, shape, block.core_group_start, block.core_group_stop
        )
        != configuration["x1_old_block_sha256"][block_index]
    ):
        raise RuntimeError("Phase 7B9ay unwritten x1 block changed")
    baseline = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    x3, x4 = engine.affine._evaluate_state(
        x3_path,
        shape,
        context,
        block,
        material,
        configuration["spatial_scheme"],
    )
    x1_global = np.memmap(
        ROOT / configuration["x1_state_path"], mode="r+", dtype=np.float64, shape=shape
    )
    x2_global = np.memmap(
        ROOT / configuration["x2_state_path"], mode="r", dtype=np.float64, shape=shape
    )
    x1 = np.array(x1_global[core], copy=True)
    x2 = np.array(x2_global[core], copy=True)
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
    if not np.all(np.isfinite(x4)) or np.any(x4 < 0.0):
        raise ArithmeticError("Phase 7B9ay x4 is not finite and nonnegative")
    x1_global[core] = x4
    x1_global.flush()
    peak = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "block_index": block_index,
        "core_group_start": int(block.core_group_start),
        "core_group_stop": int(block.core_group_stop),
        "gram_matrix": gram.tolist(),
        "x3_maximum_absolute_change": float(np.max(np.abs(x4 - x3))),
        "x3_maximum_scale": max(float(np.max(np.abs(x3))), float(np.max(np.abs(x4)))),
        "boundary_spectrum_l1_numerator": float(np.sum(np.abs(x4_flux - x3_flux))),
        "current_boundary_absolute_scale": float(np.sum(np.abs(x3_flux))),
        "mapped_boundary_absolute_scale": float(np.sum(np.abs(x4_flux))),
        "current_boundary_bolometric": float(np.sum(x3_flux)),
        "mapped_boundary_bolometric": float(np.sum(x4_flux)),
        "minimum_x3_intensity": float(np.min(x3)),
        "minimum_x4_intensity": float(np.min(x4)),
        "output_block_sha256": base.phase7b9d._block_sha256(
            output_state, shape, block.core_group_start, block.core_group_stop
        ),
        "baseline_highwater_rss_mib": baseline / MIB,
        "peak_process_rss_mib": peak / MIB,
        "wall_runtime_s": time.perf_counter() - started,
    }
    del x1_global, x2_global, x1, x2, x3, x4, residual, material
    gc.collect()
    _write_json_atomic(report_path, report)


def _raw_metrics(reports: list[dict[str, object]]) -> dict[str, object]:
    gram = sum(
        (np.asarray(row["gram_matrix"], dtype=np.float64) for row in reports),
        start=np.zeros((3, 3), dtype=np.float64),
    )
    kkt = np.zeros((4, 4), dtype=np.float64)
    kkt[:3, :3] = 2.0 * gram
    kkt[:3, 3] = 1.0
    kkt[3, :3] = 1.0
    raw = np.linalg.solve(kkt, np.array([0.0, 0.0, 0.0, 1.0]))[:3]
    maximum_change = max(float(row["x3_maximum_absolute_change"]) for row in reports)
    maximum_scale = max(float(row["x3_maximum_scale"]) for row in reports)
    numerator = sum(float(row["boundary_spectrum_l1_numerator"]) for row in reports)
    current_scale = sum(float(row["current_boundary_absolute_scale"]) for row in reports)
    mapped_scale = sum(float(row["mapped_boundary_absolute_scale"]) for row in reports)
    current_bolometric = sum(float(row["current_boundary_bolometric"]) for row in reports)
    mapped_bolometric = sum(float(row["mapped_boundary_bolometric"]) for row in reports)
    return {
        "gram": gram,
        "gram_matrix": gram.tolist(),
        "gram_condition_number": float(np.linalg.cond(gram)),
        "raw_anderson_alpha": raw,
        "x3_global_residual": maximum_change / maximum_scale,
        "x3_boundary_spectrum_l1": numerator / max(current_scale, mapped_scale),
        "x3_boundary_bolometric_fraction": abs(mapped_bolometric-current_bolometric)
        / max(abs(current_bolometric), abs(mapped_bolometric)),
        "minimum_x3_intensity": min(float(row["minimum_x3_intensity"]) for row in reports),
        "minimum_x4_intensity": min(float(row["minimum_x4_intensity"]) for row in reports),
    }


def _constrain_coefficients(
    configuration: dict[str, object], gram: np.ndarray, raw: np.ndarray
) -> tuple[np.ndarray, list[dict[str, object]], int, float]:
    shape = _shape(configuration)
    paths = [
        ROOT / configuration["x2_state_path"],
        ROOT / configuration["x3_state_path"],
        ROOT / configuration["x4_output_path"],
    ]
    states = [np.memmap(path, mode="r", dtype=np.float64, shape=shape) for path in paths]
    coefficient = np.array(raw, copy=True)
    constraints: list[np.ndarray] = []
    history: list[dict[str, object]] = []
    started_all = time.perf_counter()
    final_negative = -1
    final_minimum = float("nan")
    for iteration in range(int(configuration["maximum_cutting_plane_iterations"])):
        started = time.perf_counter()
        added: list[np.ndarray] = []
        negative_count = 0
        minimum = float("inf")
        for start in range(0, shape[0], 128):
            stop = min(start + 128, shape[0])
            x2, x3, x4 = (np.asarray(state[start:stop]) for state in states)
            candidate = coefficient[0] * x2 + coefficient[1] * x3 + coefficient[2] * x4
            negative = candidate < 0.0
            count = int(np.count_nonzero(negative))
            negative_count += count
            minimum = min(minimum, float(np.min(candidate)))
            if count:
                denominator = np.maximum(np.maximum(x2, x3), x4)
                relative = np.divide(
                    candidate,
                    denominator,
                    out=np.zeros_like(candidate),
                    where=denominator > 0.0,
                )
                index = np.unravel_index(int(np.argmin(relative)), relative.shape)
                vector = np.array([x2[index], x3[index], x4[index]], dtype=np.float64)
                scale = float(np.max(vector))
                if scale > 0.0:
                    added.append(vector / scale)
        history.append(
            {
                "iteration": iteration,
                "coefficients": coefficient.tolist(),
                "negative_candidate_count": negative_count,
                "minimum_candidate_intensity": minimum,
                "new_block_constraints": len(added),
                "scan_wall_runtime_s": time.perf_counter() - started,
            }
        )
        final_negative = negative_count
        final_minimum = minimum
        if negative_count == 0:
            break
        constraints.extend(added)
        unique: list[np.ndarray] = []
        tolerance = float(configuration["constraint_direction_duplicate_tolerance"])
        for vector in constraints:
            if not any(np.max(np.abs(vector - prior)) < tolerance for prior in unique):
                unique.append(vector)
        constraints = unique
        matrix = np.asarray(constraints)
        objective = lambda value: float(value @ gram @ value)
        gradient = lambda value: 2.0 * gram @ value
        result = minimize(
            objective,
            coefficient,
            jac=gradient,
            method="SLSQP",
            constraints=[
                {
                    "type": "eq",
                    "fun": lambda value: np.sum(value) - 1.0,
                    "jac": lambda value: np.ones(3),
                },
                {
                    "type": "ineq",
                    "fun": lambda value, matrix=matrix: matrix @ value,
                    "jac": lambda value, matrix=matrix: matrix,
                },
            ],
            options={
                "ftol": float(configuration["slsqp_function_tolerance"]),
                "maxiter": int(configuration["slsqp_maximum_iterations"]),
            },
        )
        if not result.success:
            raise RuntimeError(f"Phase 7B9ay constrained solve failed: {result.message}")
        coefficient = np.asarray(result.x)
        history[-1]["constraint_count_after_solve"] = len(constraints)
        history[-1]["next_coefficients"] = coefficient.tolist()
    del states
    return coefficient, history, final_negative, time.perf_counter() - started_all


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    shape = _shape(configuration)
    output = ROOT / configuration["x4_output_path"]
    manifest_path = ROOT / configuration["manifest_path"]
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
            raise RuntimeError("Phase 7B9ay manifest belongs to another protocol")
    else:
        if base._sha256(output) != configuration["x1_state_sha256"]:
            raise RuntimeError("Phase 7B9ay x1 reuse buffer changed")
        manifest = {
            "phase": protocol["phase"],
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "status": "running",
            "reports": [],
            "wall_runtime_s": 0.0,
        }
        _write_json_atomic(manifest_path, manifest)
    completed = {int(row["block_index"]): row for row in manifest["reports"]}
    for row in completed.values():
        if base.phase7b9d._block_sha256(
            output, shape, int(row["core_group_start"]), int(row["core_group_stop"])
        ) != row["output_block_sha256"]:
            raise RuntimeError("Phase 7B9ay completed x4 block changed")
    pending = [index for index in range(76) if index not in completed]
    directory = ROOT / configuration["report_directory"]
    directory.mkdir(parents=True, exist_ok=True)
    concurrency = int(configuration["maximum_concurrent_processes"])
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        started = time.perf_counter()
        paths = [directory / f"phase7b9ay_block{index:02d}.json" for index in batch]
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
                    "--output-state",
                    str(output),
                    "--worker-report",
                    str(path),
                ],
                cwd=ROOT,
            )
            for index, path in zip(batch, paths, strict=True)
        ]
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"Phase 7B9ay batch failed: {codes}")
        for index, path in zip(batch, paths, strict=True):
            row = json.loads(path.read_text(encoding="utf-8"))
            if row.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256 or row.get("block_index") != index:
                raise RuntimeError("Phase 7B9ay worker report changed")
            manifest["reports"].append(row)
        manifest["reports"].sort(key=lambda row: int(row["block_index"]))
        manifest["wall_runtime_s"] = float(manifest["wall_runtime_s"]) + time.perf_counter() - started
        _write_json_atomic(manifest_path, manifest)
        print(json.dumps({"completed_blocks": len(manifest["reports"]), "total_blocks": 76, "latest_blocks": batch}), flush=True)
    reports = list(manifest["reports"])
    metrics = _raw_metrics(reports)
    constrained, cutting_history, final_negative, constraint_wall = _constrain_coefficients(
        configuration, metrics["gram"], metrics["raw_anderson_alpha"]
    )
    ownership = np.zeros(shape[0], dtype=np.int8)
    for row in reports:
        ownership[int(row["core_group_start"]):int(row["core_group_stop"])] += 1
    checks = {
        "frequency_ownership_pass": len(reports) == gates["block_count_exactly"]
        and int(np.sum(ownership)) == gates["owned_frequency_group_count_exactly"]
        and bool(np.all(ownership == 1)),
        "gram_condition_pass": metrics["gram_condition_number"] < gates["gram_condition_number_below"],
        "finite_coefficients_pass": bool(np.all(np.isfinite(constrained))),
        "coefficient_sum_pass": abs(float(np.sum(constrained)) - 1.0) < gates["coefficient_sum_absolute_error_below"],
        "positive_endpoints_pass": metrics["minimum_x3_intensity"] >= gates["minimum_x3_and_x4_intensity_at_least"]
        and metrics["minimum_x4_intensity"] >= gates["minimum_x3_and_x4_intensity_at_least"],
        "constrained_candidate_positive_pass": final_negative == gates["final_negative_candidate_count_exactly"],
        "boundary_pass": metrics["x3_boundary_spectrum_l1"] < gates["global_boundary_spectrum_l1_below"]
        and metrics["x3_boundary_bolometric_fraction"] < gates["global_boundary_bolometric_fraction_below"],
        "resources_pass": all(
            float(row["peak_process_rss_mib"]) < gates["each_process_peak_rss_strictly_below_mib"]
            and float(row["wall_runtime_s"]) < gates["worker_wall_time_strictly_below_s"]
            for row in reports
        )
        and manifest["wall_runtime_s"] < gates["map_wall_time_strictly_below_s"]
        and constraint_wall < gates["constraint_wall_time_strictly_below_s"],
    }
    passed = all(checks.values())
    x4_sha = base._sha256(output)
    manifest["status"] = "complete" if passed else "gate_failed"
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
        "gram_matrix": metrics["gram_matrix"],
        "gram_condition_number": metrics["gram_condition_number"],
        "raw_anderson_alpha": metrics["raw_anderson_alpha"].tolist(),
        "constrained_anderson_alpha": constrained.tolist(),
        "constrained_alpha_sum_absolute_error": abs(float(np.sum(constrained)) - 1.0),
        "raw_predicted_unweighted_l2_residual_squared": float(metrics["raw_anderson_alpha"] @ metrics["gram"] @ metrics["raw_anderson_alpha"]),
        "constrained_predicted_unweighted_l2_residual_squared": float(constrained @ metrics["gram"] @ constrained),
        "x3_global_original_operator_residual": metrics["x3_global_residual"],
        "x3_boundary_spectrum_l1": metrics["x3_boundary_spectrum_l1"],
        "x3_boundary_bolometric_fraction": metrics["x3_boundary_bolometric_fraction"],
        "minimum_x3_intensity": metrics["minimum_x3_intensity"],
        "minimum_x4_intensity": metrics["minimum_x4_intensity"],
        "final_negative_candidate_count": final_negative,
        "constraint_wall_runtime_s": constraint_wall,
        "cutting_plane_history": cutting_history,
        "maximum_process_peak_rss_mib": max(float(row["peak_process_rss_mib"]) for row in reports),
        "map_wall_runtime_s": manifest["wall_runtime_s"],
        "gate_checks": checks,
        "decision": {
            "fused_constrained_anderson_passed": passed,
            "maximum_norm_and_mapped_positivity_candidate_audit_authorized": passed,
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
        default=OUTPUT / "phase7b9ay_preregistered_fused_constrained_anderson.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.block_index is None or args.output_state is None or args.worker_report is None:
            raise ValueError("worker mode requires block, output and report")
        _run_worker(args.protocol, args.block_index, args.output_state, args.worker_report)
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
