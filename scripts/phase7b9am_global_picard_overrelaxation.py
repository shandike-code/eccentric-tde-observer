"""Phase 7B9am：全局 Picard 方向超松弛线搜索。"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from scripts import phase7b9ak_global_convex_krylov_line as affine
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ak_global_convex_krylov_line as affine  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "3d9b12e0aeceffe7986dacc4fd74722b3fbcbcec1196b9346dec4f5ce6c03fbb"
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
        raise RuntimeError("frozen Phase 7B9am protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9am source changed: {source['path']}"
                )
    return protocol


def _shape(configuration: dict[str, object]) -> tuple[int, int, int]:
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _context(
    protocol: dict[str, object], upper_path: Path
) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    finite = base.phase7b9i._load_protocol(
        ROOT / protocol["sources"]["finite_trial_protocol"]["path"],
        validate_sources=False,
    )
    base.phase7b9d._configure_worker(finite, upper_path)
    template = base.phase7b7i._load_protocol(
        ROOT / protocol["sources"]["finite_trial_protocol"]["path"],
        validate_sources=False,
    )
    return (
        base.phase7b7i.phase7b7e.phase7b5x._context(template),
        base.phase7b7i._second_full_material(template),
    )


def _positive_upper_bound(base_value: np.ndarray, direction: np.ndarray) -> float:
    mask = direction < 0.0
    if not np.any(mask):
        return math.inf
    return float(np.min(-base_value[mask] / direction[mask]))


def _endpoint_arrays(
    protocol: dict[str, object], block_index: int
) -> tuple[object, dict[str, object], np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    configuration = protocol["configuration"]
    upper_path = ROOT / configuration["upper_state_path"]
    context, material = _context(protocol, upper_path)
    block = context["blocks"][block_index]
    shape = _shape(configuration)
    upper, mapped_upper = affine._evaluate_state(
        upper_path,
        shape,
        context,
        block,
        material,
        configuration["spatial_scheme"],
    )
    lower_global = np.memmap(
        ROOT / configuration["lower_state_path"],
        mode="r",
        dtype=np.float64,
        shape=shape,
    )
    core = slice(block.core_group_start, block.core_group_stop)
    lower = np.array(lower_global[core], copy=True)
    del lower_global, material
    edge = np.asarray(context["stencil"].active_lab_edge_hz)
    width = np.diff(edge)[core]
    return block, context, lower, upper, mapped_upper, np.asarray(width), np.asarray(context["mu"])


def _run_coefficient_worker(
    protocol_path: Path, block_index: int, report_path: Path
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    baseline = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    block, context, lower, upper, mapped_upper, width, mu = _endpoint_arrays(
        protocol, block_index
    )
    weight = np.asarray(context["weight"])
    r0 = upper - lower
    r1 = mapped_upper - upper
    delta = r1 - r0
    lower_flux = base._block_flux(lower, mu, weight, width)
    upper_flux = base._block_flux(upper, mu, weight, width)
    mapped_flux = base._block_flux(mapped_upper, mu, weight, width)
    peak = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "pass": "coefficient",
        "block_index": block_index,
        "core_group_start": int(block.core_group_start),
        "core_group_stop": int(block.core_group_stop),
        "residual_dot_delta": float(np.sum(r0 * delta, dtype=np.float64)),
        "delta_dot_delta": float(np.sum(delta * delta, dtype=np.float64)),
        "current_positive_theta_upper_bound": _positive_upper_bound(lower, r0),
        "mapped_positive_theta_upper_bound": _positive_upper_bound(upper, r1),
        "theta_zero_maximum_absolute_change": float(np.max(np.abs(r0))),
        "theta_zero_maximum_scale": max(
            float(np.max(np.abs(lower))), float(np.max(np.abs(upper)))
        ),
        "theta_one_maximum_absolute_change": float(np.max(np.abs(r1))),
        "theta_one_maximum_scale": max(
            float(np.max(np.abs(upper))), float(np.max(np.abs(mapped_upper)))
        ),
        "lower_boundary_absolute_scale": float(np.sum(np.abs(lower_flux))),
        "upper_boundary_absolute_scale": float(np.sum(np.abs(upper_flux))),
        "mapped_boundary_absolute_scale": float(np.sum(np.abs(mapped_flux))),
        "theta_zero_boundary_l1_numerator": float(
            np.sum(np.abs(upper_flux - lower_flux))
        ),
        "theta_one_boundary_l1_numerator": float(
            np.sum(np.abs(mapped_flux - upper_flux))
        ),
        "lower_boundary_bolometric": float(np.sum(lower_flux)),
        "upper_boundary_bolometric": float(np.sum(upper_flux)),
        "mapped_boundary_bolometric": float(np.sum(mapped_flux)),
        "minimum_lower_intensity": float(np.min(lower)),
        "minimum_upper_intensity": float(np.min(upper)),
        "minimum_mapped_upper_intensity": float(np.min(mapped_upper)),
        "baseline_highwater_rss_mib": baseline / MIB,
        "peak_process_rss_mib": peak / MIB,
        "wall_runtime_s": time.perf_counter() - started,
    }
    del lower, upper, mapped_upper, r0, r1, delta
    gc.collect()
    _write_json_atomic(report_path, report)


def _run_candidate_worker(
    protocol_path: Path,
    block_index: int,
    grid_path: Path,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    grid_sha = base._sha256(grid_path)
    grid = json.loads(grid_path.read_text(encoding="utf-8"))
    if grid["protocol_sha256"] != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("Phase 7B9am derived grid changed protocol")
    baseline = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    block, context, lower, upper, mapped_upper, width, mu = _endpoint_arrays(
        protocol, block_index
    )
    weight = np.asarray(context["weight"])
    r0 = upper - lower
    r1 = mapped_upper - upper
    delta = r1 - r0
    lower_flux = base._block_flux(lower, mu, weight, width)
    upper_flux = base._block_flux(upper, mu, weight, width)
    mapped_flux = base._block_flux(mapped_upper, mu, weight, width)
    rows = []
    for theta in grid["theta_candidates"]:
        theta = float(theta)
        current = lower + theta * r0
        mapped = upper + theta * r1
        residual = r0 + theta * delta
        current_flux = lower_flux + theta * (upper_flux - lower_flux)
        trial_mapped_flux = upper_flux + theta * (mapped_flux - upper_flux)
        rows.append(
            {
                "theta": theta,
                "maximum_absolute_change": float(np.max(np.abs(residual))),
                "maximum_scale": max(
                    float(np.max(np.abs(current))), float(np.max(np.abs(mapped)))
                ),
                "boundary_spectrum_l1_numerator": float(
                    np.sum(np.abs(trial_mapped_flux - current_flux))
                ),
                "current_boundary_absolute_scale": float(
                    np.sum(np.abs(current_flux))
                ),
                "mapped_boundary_absolute_scale": float(
                    np.sum(np.abs(trial_mapped_flux))
                ),
                "current_boundary_bolometric": float(np.sum(current_flux)),
                "mapped_boundary_bolometric": float(np.sum(trial_mapped_flux)),
                "minimum_current_intensity": float(np.min(current)),
                "minimum_mapped_intensity": float(np.min(mapped)),
            }
        )
    peak = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "derived_grid_sha256": grid_sha,
        "pass": "candidate",
        "block_index": block_index,
        "core_group_start": int(block.core_group_start),
        "core_group_stop": int(block.core_group_stop),
        "rows": rows,
        "baseline_highwater_rss_mib": baseline / MIB,
        "peak_process_rss_mib": peak / MIB,
        "wall_runtime_s": time.perf_counter() - started,
    }
    del lower, upper, mapped_upper, r0, r1, delta
    gc.collect()
    _write_json_atomic(report_path, report)


def _run_pass(
    protocol_path: Path,
    protocol: dict[str, object],
    *,
    mode: str,
    directory: Path,
    grid_path: Path | None = None,
) -> list[dict[str, object]]:
    directory.mkdir(parents=True, exist_ok=True)
    configuration = protocol["configuration"]
    reports: dict[int, dict[str, object]] = {}
    pending: list[tuple[int, Path]] = []
    for index in range(76):
        path = directory / f"phase7b9am_{mode}_block{index:02d}.json"
        if path.exists():
            row = json.loads(path.read_text(encoding="utf-8"))
            expected_grid = base._sha256(grid_path) if grid_path is not None else None
            if (
                row.get("protocol_sha256") == EXPECTED_PROTOCOL_SHA256
                and row.get("pass") == mode
                and (grid_path is None or row.get("derived_grid_sha256") == expected_grid)
            ):
                reports[index] = row
                continue
        pending.append((index, path))
    concurrency = int(configuration["maximum_concurrent_processes"])
    runner = ROOT / configuration["runner_path"]
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        processes = []
        for index, path in batch:
            command = [
                sys.executable,
                str(runner),
                f"--{mode}-worker",
                "--protocol",
                str(protocol_path),
                "--block-index",
                str(index),
                "--worker-report",
                str(path),
            ]
            if grid_path is not None:
                command.extend(["--derived-grid", str(grid_path)])
            processes.append(subprocess.Popen(command, cwd=ROOT))
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"Phase 7B9am {mode} batch failed: {codes}")
        for index, path in batch:
            reports[index] = json.loads(path.read_text(encoding="utf-8"))
        print(
            json.dumps(
                {
                    "pass": mode,
                    "completed_blocks": len(reports),
                    "total_blocks": 76,
                    "latest_blocks": [index for index, _ in batch],
                }
            ),
            flush=True,
        )
    return [reports[index] for index in sorted(reports)]


def _aggregate_candidate(
    reports: list[dict[str, object]], grid: dict[str, object]
) -> list[dict[str, float]]:
    rows = []
    for grid_index, theta in enumerate(grid["theta_candidates"]):
        local = [report["rows"][grid_index] for report in reports]
        maximum_change = max(float(row["maximum_absolute_change"]) for row in local)
        maximum_scale = max(float(row["maximum_scale"]) for row in local)
        numerator = sum(float(row["boundary_spectrum_l1_numerator"]) for row in local)
        current_scale = sum(float(row["current_boundary_absolute_scale"]) for row in local)
        mapped_scale = sum(float(row["mapped_boundary_absolute_scale"]) for row in local)
        current_bolometric = sum(float(row["current_boundary_bolometric"]) for row in local)
        mapped_bolometric = sum(float(row["mapped_boundary_bolometric"]) for row in local)
        rows.append(
            {
                "theta": float(theta),
                "global_residual": maximum_change / maximum_scale,
                "boundary_spectrum_l1": numerator / max(current_scale, mapped_scale),
                "boundary_bolometric_fraction": abs(
                    mapped_bolometric - current_bolometric
                )
                / max(abs(current_bolometric), abs(mapped_bolometric)),
                "minimum_current_intensity": min(
                    float(row["minimum_current_intensity"]) for row in local
                ),
                "minimum_mapped_intensity": min(
                    float(row["minimum_mapped_intensity"]) for row in local
                ),
            }
        )
    return rows


def _plot(path: Path, rows: list[dict[str, float]], selected: dict[str, float]) -> None:
    theta = np.asarray([row["theta"] for row in rows])
    residual = np.asarray([row["global_residual"] for row in rows])
    boundary = np.asarray([row["boundary_spectrum_l1"] for row in rows])
    order = np.argsort(theta)
    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.5), constrained_layout=True)
    axes[0].semilogy(theta[order], residual[order], "o-")
    axes[0].axvline(selected["theta"], color="tab:red", ls="--", label="Selected")
    axes[0].axhline(1.0e-4, color="0.25", ls=":", label="Global target")
    axes[0].set(
        xlabel="Picard-direction overrelaxation factor",
        ylabel="Global original-operator residual",
        title="(a) Full-frequency line search",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].semilogy(theta[order], boundary[order], "s-")
    axes[1].axhline(1.0e-3, color="0.25", ls="--", label="Boundary gate")
    axes[1].set(
        xlabel="Picard-direction overrelaxation factor",
        ylabel="Boundary spectral L1",
        title="(b) Boundary-functional guard",
    )
    axes[1].legend(frameon=False, fontsize=8)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    coefficient_reports = _run_pass(
        protocol_path,
        protocol,
        mode="coefficient",
        directory=ROOT / configuration["coefficient_report_directory"],
    )
    numerator = sum(float(row["residual_dot_delta"]) for row in coefficient_reports)
    denominator = sum(float(row["delta_dot_delta"]) for row in coefficient_reports)
    theta_l2 = -numerator / denominator
    positivity_upper_bound = min(
        min(float(row["current_positive_theta_upper_bound"]) for row in coefficient_reports),
        min(float(row["mapped_positive_theta_upper_bound"]) for row in coefficient_reports),
    )
    candidates = [float(value) for value in configuration["fixed_theta_candidates"]]
    candidates.extend(
        theta_l2 * float(multiplier)
        for multiplier in configuration["l2_theta_multipliers"]
    )
    rounded_candidates = {
        round(value, 14)
        for value in candidates
        if math.isfinite(value) and value >= 0.0
    }
    candidates = sorted(
        value for value in rounded_candidates if value <= positivity_upper_bound
    )
    if 0.0 not in candidates or 1.0 not in candidates:
        raise RuntimeError("Phase 7B9am positive line excluded an endpoint")
    grid = {
        "phase": "7B9am derived positive overrelaxation candidates",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "global_unweighted_l2_theta": theta_l2,
        "global_positive_theta_upper_bound": positivity_upper_bound,
        "theta_candidates": candidates,
    }
    grid_path = ROOT / configuration["derived_grid_path"]
    _write_json_atomic(grid_path, grid)
    candidate_reports = _run_pass(
        protocol_path,
        protocol,
        mode="candidate",
        directory=ROOT / configuration["candidate_report_directory"],
        grid_path=grid_path,
    )
    rows = _aggregate_candidate(candidate_reports, grid)
    selected = min(rows, key=lambda row: (row["global_residual"], row["theta"]))
    theta_zero = next(row for row in rows if row["theta"] == 0.0)
    reference = protocol["reference"]
    ownership = np.zeros(int(configuration["physical_frequency_groups"]), dtype=np.int8)
    for report in candidate_reports:
        ownership[int(report["core_group_start"]) : int(report["core_group_stop"])] += 1
    checks = {
        "frequency_ownership_pass": len(candidate_reports) == gates["block_count_exactly"]
        and int(np.sum(ownership)) == gates["owned_frequency_group_count_exactly"]
        and bool(np.all(ownership == 1)),
        "theta_zero_reproduction_pass": abs(
            theta_zero["global_residual"] - reference["theta_zero_global_residual"]
        ) <= gates["theta_zero_endpoint_absolute_tolerance"]
        and abs(
            theta_zero["boundary_spectrum_l1"]
            - reference["theta_zero_boundary_spectrum_l1"]
        ) <= gates["theta_zero_endpoint_absolute_tolerance"]
        and abs(
            theta_zero["boundary_bolometric_fraction"]
            - reference["theta_zero_boundary_bolometric_fraction"]
        ) <= gates["theta_zero_endpoint_absolute_tolerance"],
        "positive_candidates_pass": all(
            row["minimum_current_intensity"]
            >= gates["minimum_current_and_mapped_intensity_at_least"]
            and row["minimum_mapped_intensity"]
            >= gates["minimum_current_and_mapped_intensity_at_least"]
            for row in rows
        ),
        "selected_residual_improvement_pass": selected["global_residual"]
        / theta_zero["global_residual"]
        < gates["selected_residual_ratio_to_theta_zero_below"],
        "selected_boundary_pass": selected["boundary_spectrum_l1"]
        < gates["selected_boundary_spectrum_l1_below"]
        and selected["boundary_bolometric_fraction"]
        < gates["selected_boundary_bolometric_fraction_below"],
        "resources_pass": all(
            float(row["peak_process_rss_mib"])
            < gates["each_process_peak_rss_strictly_below_mib"]
            and float(row["wall_runtime_s"])
            < gates["coefficient_worker_wall_time_strictly_below_s"]
            for row in coefficient_reports
        )
        and all(
            float(row["peak_process_rss_mib"])
            < gates["each_process_peak_rss_strictly_below_mib"]
            and float(row["wall_runtime_s"])
            < gates["candidate_worker_wall_time_strictly_below_s"]
            for row in candidate_reports
        ),
    }
    passed = all(checks.values())
    figure = ROOT / configuration["figure_path"]
    _plot(figure, rows, selected)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "lower_state_path": configuration["lower_state_path"],
        "lower_state_sha256": configuration["lower_state_sha256"],
        "upper_state_path": configuration["upper_state_path"],
        "upper_state_sha256": configuration["upper_state_sha256"],
        "global_unweighted_l2_theta": theta_l2,
        "global_positive_theta_upper_bound": positivity_upper_bound,
        "selected_theta": selected["theta"],
        "selected_global_residual": selected["global_residual"],
        "selected_residual_ratio_to_theta_zero": selected["global_residual"]
        / theta_zero["global_residual"],
        "selected_boundary_spectrum_l1": selected["boundary_spectrum_l1"],
        "selected_boundary_bolometric_fraction": selected[
            "boundary_bolometric_fraction"
        ],
        "derived_grid_sha256": base._sha256(grid_path),
        "gate_checks": checks,
        "decision": {
            "global_picard_overrelaxation_passed": passed,
            "write_selected_overrelaxed_state_authorized": passed,
            "fresh_global_candidate_audit_authorized": passed,
            "resume_positive_picard_authorized": not passed,
            "material_feedback_authorized": False,
        },
        "grid": rows,
        "coefficient_reports": coefficient_reports,
        "candidate_reports": candidate_reports,
        "figures": [figure.name],
    }
    _write_json_atomic(ROOT / configuration["summary_path"], summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9am_preregistered_global_picard_overrelaxation.json",
    )
    parser.add_argument("--coefficient-worker", action="store_true")
    parser.add_argument("--candidate-worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--derived-grid", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.coefficient_worker:
        if args.block_index is None or args.worker_report is None:
            raise ValueError("coefficient worker requires block and report")
        _run_coefficient_worker(args.protocol, args.block_index, args.worker_report)
        return
    if args.candidate_worker:
        if (
            args.block_index is None
            or args.derived_grid is None
            or args.worker_report is None
        ):
            raise ValueError("candidate worker requires block, grid and report")
        _run_candidate_worker(
            args.protocol, args.block_index, args.derived_grid, args.worker_report
        )
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
