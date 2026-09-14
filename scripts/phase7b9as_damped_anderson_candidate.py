"""Phase 7B9as：审计并写入阻尼全局 Anderson 候选。"""

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
EXPECTED_PROTOCOL_SHA256 = "b8caa8ccf6884ee6e29e346176aa6b1e3d4ec0c3a337b176e63c56ed0816425c"
MIB = 1024**2
base = affine.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9as protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9as source changed: {source['path']}"
                )
    return protocol


def _shape(configuration: dict[str, object]) -> tuple[int, int, int]:
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _context(
    protocol: dict[str, object], x4_path: Path
) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    finite = base.phase7b9i._load_protocol(
        ROOT / protocol["sources"]["finite_trial_protocol"]["path"],
        validate_sources=False,
    )
    base.phase7b9d._configure_worker(finite, x4_path)
    template = base.phase7b7i._load_protocol(
        ROOT / protocol["sources"]["finite_trial_protocol"]["path"],
        validate_sources=False,
    )
    return (
        base.phase7b7i.phase7b7e.phase7b5x._context(template),
        base.phase7b7i._second_full_material(template),
    )


def _run_worker(
    protocol_path: Path, block_index: int, report_path: Path
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    configuration = protocol["configuration"]
    shape = _shape(configuration)
    x4_path = ROOT / configuration["x4_state_path"]
    context, material = _context(protocol, x4_path)
    block = context["blocks"][block_index]
    baseline = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    x4, x5 = affine._evaluate_state(
        x4_path,
        shape,
        context,
        block,
        material,
        configuration["spatial_scheme"],
    )
    core = slice(block.core_group_start, block.core_group_stop)
    x2_global = np.memmap(
        ROOT / configuration["x2_state_path"], mode="r", dtype=np.float64, shape=shape
    )
    x3_global = np.memmap(
        ROOT / configuration["x3_state_path"], mode="r", dtype=np.float64, shape=shape
    )
    x2 = np.array(x2_global[core], copy=True)
    x3 = np.array(x3_global[core], copy=True)
    del x2_global, x3_global, material
    alpha = np.asarray(configuration["anderson_alpha"], dtype=np.float64)
    edge = np.asarray(context["stencil"].active_lab_edge_hz)
    width = np.diff(edge)[core]
    mu = np.asarray(context["mu"])
    weight = np.asarray(context["weight"])
    flux = [
        base._block_flux(value, mu, weight, width)
        for value in (x2, x3, x4, x5)
    ]
    rows = []
    for eta in configuration["eta_grid"]:
        eta = float(eta)
        coefficient = np.array(
            [eta * alpha[0], eta * alpha[1], 1.0 - eta + eta * alpha[2]]
        )
        current = coefficient[0] * x2 + coefficient[1] * x3 + coefficient[2] * x4
        mapped = coefficient[0] * x3 + coefficient[1] * x4 + coefficient[2] * x5
        current_flux = (
            coefficient[0] * flux[0]
            + coefficient[1] * flux[1]
            + coefficient[2] * flux[2]
        )
        mapped_flux = (
            coefficient[0] * flux[1]
            + coefficient[1] * flux[2]
            + coefficient[2] * flux[3]
        )
        rows.append(
            {
                "eta": eta,
                "state_coefficients_x2_x3_x4": coefficient.tolist(),
                "coefficient_sum_absolute_error": abs(
                    float(np.sum(coefficient)) - 1.0
                ),
                "maximum_absolute_change": float(np.max(np.abs(mapped - current))),
                "maximum_scale": max(
                    float(np.max(np.abs(current))), float(np.max(np.abs(mapped)))
                ),
                "boundary_spectrum_l1_numerator": float(
                    np.sum(np.abs(mapped_flux - current_flux))
                ),
                "current_boundary_absolute_scale": float(
                    np.sum(np.abs(current_flux))
                ),
                "mapped_boundary_absolute_scale": float(
                    np.sum(np.abs(mapped_flux))
                ),
                "current_boundary_bolometric": float(np.sum(current_flux)),
                "mapped_boundary_bolometric": float(np.sum(mapped_flux)),
                "minimum_current_intensity": float(np.min(current)),
                "minimum_mapped_intensity": float(np.min(mapped)),
            }
        )
    peak = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "block_index": block_index,
        "core_group_start": int(block.core_group_start),
        "core_group_stop": int(block.core_group_stop),
        "rows": rows,
        "baseline_highwater_rss_mib": baseline / MIB,
        "peak_process_rss_mib": peak / MIB,
        "wall_runtime_s": time.perf_counter() - started,
    }
    del x2, x3, x4, x5
    gc.collect()
    _write_json_atomic(report_path, report)


def _aggregate(
    reports: list[dict[str, object]], eta_grid: list[float]
) -> list[dict[str, float]]:
    rows = []
    for grid_index, eta in enumerate(eta_grid):
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
                "eta": float(eta),
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
                "maximum_coefficient_sum_absolute_error": max(
                    float(row["coefficient_sum_absolute_error"]) for row in local
                ),
            }
        )
    return rows


def _plot(path: Path, rows: list[dict[str, float]], selected: dict[str, float]) -> None:
    eta = np.asarray([row["eta"] for row in rows])
    residual = np.asarray([row["global_residual"] for row in rows])
    minimum_current = np.asarray(
        [row["minimum_current_intensity"] for row in rows]
    )
    minimum_mapped = np.asarray(
        [row["minimum_mapped_intensity"] for row in rows]
    )
    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.5), constrained_layout=True)
    axes[0].semilogy(eta, residual, "o-")
    axes[0].axvline(selected["eta"], color="tab:red", ls="--", label="Selected")
    axes[0].axhline(1.0e-4, color="0.25", ls=":", label="Global target")
    axes[0].set(
        xlabel="Anderson blend fraction",
        ylabel="Global original-operator residual",
        title="(a) Damped depth-two Anderson audit",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].plot(eta, minimum_current, "s-", label="Candidate")
    axes[1].plot(eta, minimum_mapped, "^-", label="Mapped candidate")
    axes[1].axhline(0.0, color="0.25", ls="--", label="Positivity boundary")
    axes[1].set(
        xlabel="Anderson blend fraction",
        ylabel="Minimum intensity",
        title="(b) Global positivity guard",
    )
    axes[1].legend(frameon=False, fontsize=8)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    shape = _shape(configuration)
    manifest_path = ROOT / configuration["manifest_path"]
    output = ROOT / configuration["candidate_output_path"]
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
            raise RuntimeError("Phase 7B9as manifest belongs to another protocol")
    else:
        if base._sha256(output) != configuration["x2_state_sha256"]:
            raise RuntimeError("Phase 7B9as x2 output buffer changed")
        manifest = {
            "phase": protocol["phase"],
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "status": "audit",
            "audit_reports": [],
            "audit_wall_runtime_s": 0.0,
            "write_completed_blocks": [],
            "write_wall_runtime_s": 0.0,
        }
        _write_json_atomic(manifest_path, manifest)
    reports_by_block = {
        int(row["block_index"]): row for row in manifest["audit_reports"]
    }
    pending = [index for index in range(76) if index not in reports_by_block]
    report_dir = ROOT / configuration["audit_report_directory"]
    report_dir.mkdir(parents=True, exist_ok=True)
    concurrency = int(configuration["maximum_concurrent_processes"])
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        started = time.perf_counter()
        paths = [report_dir / f"phase7b9as_block{index:02d}.json" for index in batch]
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
                    "--worker-report",
                    str(path),
                ],
                cwd=ROOT,
            )
            for index, path in zip(batch, paths, strict=True)
        ]
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"Phase 7B9as audit batch failed: {codes}")
        for index, path in zip(batch, paths, strict=True):
            row = json.loads(path.read_text(encoding="utf-8"))
            if (
                row.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256
                or int(row.get("block_index", -1)) != index
            ):
                raise RuntimeError("Phase 7B9as worker report changed")
            manifest["audit_reports"].append(row)
        manifest["audit_reports"].sort(key=lambda value: int(value["block_index"]))
        manifest["audit_wall_runtime_s"] = float(
            manifest["audit_wall_runtime_s"]
        ) + (time.perf_counter() - started)
        _write_json_atomic(manifest_path, manifest)
        print(
            json.dumps(
                {
                    "completed_blocks": len(manifest["audit_reports"]),
                    "total_blocks": 76,
                    "latest_blocks": batch,
                }
            ),
            flush=True,
        )
    reports = list(manifest["audit_reports"])
    rows = _aggregate(reports, configuration["eta_grid"])
    valid = [
        row
        for row in rows
        if row["minimum_current_intensity"]
        >= gates["minimum_candidate_and_mapped_intensity_at_least"]
        and row["minimum_mapped_intensity"]
        >= gates["minimum_candidate_and_mapped_intensity_at_least"]
    ]
    if not valid:
        raise RuntimeError("Phase 7B9as has no nonnegative candidate")
    selected = min(valid, key=lambda row: (row["global_residual"], row["eta"]))
    x4_control = next(row for row in rows if row["eta"] == 0.0)
    ownership = np.zeros(shape[0], dtype=np.int8)
    for report in reports:
        ownership[int(report["core_group_start"]) : int(report["core_group_stop"])] += 1
    checks = {
        "frequency_ownership_pass": len(reports) == gates["block_count_exactly"]
        and int(np.sum(ownership)) == gates["owned_frequency_group_count_exactly"]
        and bool(np.all(ownership == 1)),
        "coefficient_sum_pass": all(
            row["maximum_coefficient_sum_absolute_error"]
            < gates["coefficient_sum_absolute_error_below"]
            for row in rows
        ),
        "selected_positive_pass": selected["minimum_current_intensity"]
        >= gates["minimum_candidate_and_mapped_intensity_at_least"]
        and selected["minimum_mapped_intensity"]
        >= gates["minimum_candidate_and_mapped_intensity_at_least"],
        "selected_improvement_pass": selected["global_residual"]
        / x4_control["global_residual"]
        < gates["selected_residual_ratio_to_x4_below"],
        "selected_boundary_pass": selected["boundary_spectrum_l1"]
        < gates["global_boundary_spectrum_l1_below"]
        and selected["boundary_bolometric_fraction"]
        < gates["global_boundary_bolometric_fraction_below"],
        "resources_pass": all(
            float(report["peak_process_rss_mib"])
            < gates["each_process_peak_rss_strictly_below_mib"]
            and float(report["wall_runtime_s"])
            < gates["each_worker_wall_time_strictly_below_s"]
            for report in reports
        )
        and manifest["audit_wall_runtime_s"]
        < gates["audit_wall_time_strictly_below_s"],
    }
    figure = ROOT / configuration["figure_path"]
    _plot(figure, rows, selected)
    passed = all(checks.values())
    if passed and manifest["status"] != "complete":
        manifest["status"] = "write"
        completed = {
            int(row["block_index"]): row
            for row in manifest["write_completed_blocks"]
        }
        for index, row in completed.items():
            start = index * 128
            stop = min((index + 1) * 128, shape[0])
            if (
                base.phase7b9d._block_sha256(output, shape, start, stop)
                != row["candidate_block_sha256"]
            ):
                raise RuntimeError("Phase 7B9as completed candidate block changed")
        x2 = np.memmap(output, mode="r+", dtype=np.float64, shape=shape)
        x3 = np.memmap(
            ROOT / configuration["x3_state_path"], mode="r", dtype=np.float64, shape=shape
        )
        x4 = np.memmap(
            ROOT / configuration["x4_state_path"], mode="r", dtype=np.float64, shape=shape
        )
        alpha = np.asarray(configuration["anderson_alpha"], dtype=np.float64)
        eta = float(selected["eta"])
        coefficient = np.array(
            [eta * alpha[0], eta * alpha[1], 1.0 - eta + eta * alpha[2]]
        )
        started = time.perf_counter()
        for index in range(76):
            if index in completed:
                continue
            start = index * 128
            stop = min((index + 1) * 128, shape[0])
            if (
                base.phase7b9d._block_sha256(output, shape, start, stop)
                != configuration["x2_old_block_sha256"][index]
            ):
                raise RuntimeError("Phase 7B9as unwritten x2 block changed")
            old_x2 = np.array(x2[start:stop], copy=True)
            candidate = (
                coefficient[0] * old_x2
                + coefficient[1] * np.asarray(x3[start:stop])
                + coefficient[2] * np.asarray(x4[start:stop])
            )
            if not np.all(np.isfinite(candidate)) or np.any(candidate < 0.0):
                raise ArithmeticError("Phase 7B9as selected candidate became invalid")
            x2[start:stop] = candidate
            x2.flush()
            row = {
                "block_index": index,
                "candidate_block_sha256": base.phase7b9d._block_sha256(
                    output, shape, start, stop
                ),
                "minimum_candidate_intensity": float(np.min(candidate)),
            }
            manifest["write_completed_blocks"].append(row)
            manifest["write_completed_blocks"].sort(
                key=lambda value: int(value["block_index"])
            )
            manifest["write_wall_runtime_s"] = float(
                manifest["write_wall_runtime_s"]
            ) + (time.perf_counter() - started)
            started = time.perf_counter()
            _write_json_atomic(manifest_path, manifest)
        del x2, x3, x4
        if manifest["write_wall_runtime_s"] >= gates["write_wall_time_strictly_below_s"]:
            passed = False
            checks["write_resources_pass"] = False
            manifest["status"] = "write_resource_gate_failed"
        else:
            checks["write_resources_pass"] = True
            manifest["status"] = "complete"
        _write_json_atomic(manifest_path, manifest)
    elif not passed:
        manifest["status"] = "audit_gate_failed"
        _write_json_atomic(manifest_path, manifest)
    candidate_sha = base._sha256(output) if manifest["status"] == "complete" else None
    selected_index = configuration["eta_grid"].index(selected["eta"])
    selected_block_reports = []
    for report in reports:
        row = report["rows"][selected_index]
        # 空频率块中候选与映射可同时严格为零，此时相对残差定义为零。
        block_scale = float(row["maximum_scale"])
        selected_block_reports.append(
            {
                "block_index": int(report["block_index"]),
                "core_group_start": int(report["core_group_start"]),
                "core_group_stop": int(report["core_group_stop"]),
                "block_relative_selected_prediction": float(
                    0.0
                    if block_scale == 0.0
                    else row["maximum_absolute_change"] / block_scale
                ),
            }
        )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "anderson_alpha": configuration["anderson_alpha"],
        "selected_eta": selected["eta"],
        "selected_state_coefficients_x2_x3_x4": next(
            row["state_coefficients_x2_x3_x4"]
            for row in reports[0]["rows"]
            if row["eta"] == selected["eta"]
        ),
        "x4_control_global_residual": x4_control["global_residual"],
        "selected_predicted_global_residual": selected["global_residual"],
        "predicted_global_original_operator_residual": selected[
            "global_residual"
        ],
        "selected_residual_ratio_to_x4": selected["global_residual"]
        / x4_control["global_residual"],
        "selected_boundary_spectrum_l1": selected["boundary_spectrum_l1"],
        "selected_boundary_bolometric_fraction": selected[
            "boundary_bolometric_fraction"
        ],
        "candidate_state_path": configuration["candidate_output_path"]
        if candidate_sha is not None
        else None,
        "candidate_state_sha256": candidate_sha,
        "gate_checks": checks,
        "decision": {
            "damped_anderson_candidate_passed": passed,
            "candidate_written": candidate_sha is not None,
            "fresh_global_self_audit_authorized": candidate_sha is not None,
            "material_feedback_authorized": False,
        },
        "grid": rows,
        "reports": selected_block_reports,
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
        default=OUTPUT / "phase7b9as_preregistered_damped_anderson_candidate.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.block_index is None or args.worker_report is None:
            raise ValueError("worker mode requires block and report")
        _run_worker(args.protocol, args.block_index, args.worker_report)
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
