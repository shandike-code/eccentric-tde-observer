"""Phase 7B9ak：全局凸 Krylov 线搜索。"""

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
    from scripts import phase7b9ab_global_trial_residual_audit as previous
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ab_global_trial_residual_audit as previous  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "79e0bbab3dd683d1625d8dfd1cac48b26e7435333ac24552d77df230e65e3b36"
)
MIB = 1024**2
base = previous.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9ak protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9ak source changed: {source['path']}"
                )
    return protocol


def _evaluate_state(
    state_path: Path,
    shape: tuple[int, int, int],
    context: dict[str, object],
    block: object,
    material: dict[str, np.ndarray],
    spatial_scheme: str,
) -> tuple[np.ndarray, np.ndarray]:
    fields = base.phase7b7i.phase7b7e._local_fields(context, block, material)
    state = np.memmap(state_path, mode="r", dtype=np.float64, shape=shape)
    full_start = int(context["stencil"].active_outer_group_start)
    full_stop = int(context["stencil"].active_outer_group_stop)
    physical_start = max(block.outer_group_start, full_start)
    physical_stop = min(block.outer_group_stop, full_stop)
    if physical_stop > physical_start:
        fields["outer"][
            physical_start - block.outer_group_start : physical_stop
            - block.outer_group_start
        ] = state[physical_start - full_start : physical_stop - full_start]
    core = slice(block.core_group_start, block.core_group_stop)
    initial = np.array(state[core], copy=True)
    del state
    result = base.phase7b7i.phase7b7e.solve_mixed_frame_ale_group_step(
        block.local_stencil,
        fields["old_edge"],
        fields["new_edge"],
        context["mu"],
        context["weight"],
        fields["initial"],
        fields["outer"],
        fields["true_absorption"],
        fields["thermal_emissivity"],
        fields["scattering"],
        context["beta"],
        context["duration_s"],
        propagation_speed_cm_s=base.phase7b7i.phase7b7e.LIGHT_SPEED_CM_S,
        source_iteration_initial_guess=initial,
        diagnostic_fixed_iteration_count=1,
        spatial_scheme=spatial_scheme,
        source_map_only=True,
    )
    mapped = np.array(result.final_lab_intensity_density, copy=True)
    del result, fields
    return initial, mapped


def _run_worker(protocol_path: Path, block_index: int, report_path: Path) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    configuration = protocol["configuration"]
    finite = base.phase7b9i._load_protocol(
        ROOT / protocol["sources"]["finite_trial_protocol"]["path"],
        validate_sources=False,
    )
    stable_path = ROOT / configuration["stable_state_path"]
    base.phase7b9d._configure_worker(finite, stable_path)
    template = base.phase7b7i._load_protocol(protocol_path, validate_sources=False)
    context = base.phase7b7i.phase7b7e.phase7b5x._context(template)
    block = context["blocks"][block_index]
    material = base.phase7b7i._second_full_material(template)
    shape = (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )
    baseline_rss = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    stable, stable_mapped = _evaluate_state(
        stable_path, shape, context, block, material, configuration["spatial_scheme"]
    )
    candidate, candidate_mapped = _evaluate_state(
        ROOT / configuration["candidate_state_path"],
        shape,
        context,
        block,
        material,
        configuration["spatial_scheme"],
    )
    if (
        np.any(stable < 0.0)
        or np.any(candidate < 0.0)
        or np.any(stable_mapped < 0.0)
        or np.any(candidate_mapped < 0.0)
    ):
        raise ArithmeticError("Phase 7B9ak endpoint state is negative")
    core = slice(block.core_group_start, block.core_group_stop)
    global_edge = np.asarray(context["stencil"].active_lab_edge_hz)
    width = np.diff(global_edge)[core]
    mu = np.asarray(context["mu"])
    weight = np.asarray(context["weight"])
    stable_flux = base._block_flux(stable, mu, weight, width)
    stable_mapped_flux = base._block_flux(stable_mapped, mu, weight, width)
    candidate_flux = base._block_flux(candidate, mu, weight, width)
    candidate_mapped_flux = base._block_flux(candidate_mapped, mu, weight, width)
    grid = []
    for theta in configuration["theta_grid"]:
        theta = float(theta)
        current = (1.0 - theta) * stable + theta * candidate
        mapped = (1.0 - theta) * stable_mapped + theta * candidate_mapped
        flux = (1.0 - theta) * stable_flux + theta * candidate_flux
        mapped_flux = (
            (1.0 - theta) * stable_mapped_flux + theta * candidate_mapped_flux
        )
        grid.append(
            {
                "theta": theta,
                "maximum_absolute_change": float(np.max(np.abs(mapped - current))),
                "maximum_scale": max(
                    float(np.max(np.abs(current))), float(np.max(np.abs(mapped)))
                ),
                "boundary_spectrum_l1_numerator": float(
                    np.sum(np.abs(mapped_flux - flux))
                ),
                "current_boundary_absolute_scale": float(np.sum(np.abs(flux))),
                "mapped_boundary_absolute_scale": float(
                    np.sum(np.abs(mapped_flux))
                ),
                "current_boundary_bolometric": float(np.sum(flux)),
                "mapped_boundary_bolometric": float(np.sum(mapped_flux)),
                "minimum_current_intensity": float(np.min(current)),
                "minimum_mapped_intensity": float(np.min(mapped)),
            }
        )
    peak_rss = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "block_index": block_index,
        "core_group_start": int(block.core_group_start),
        "core_group_stop": int(block.core_group_stop),
        "grid": grid,
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
        "wall_runtime_s": time.perf_counter() - started,
    }
    del stable, stable_mapped, candidate, candidate_mapped, material
    gc.collect()
    _write_json_atomic(report_path, report)


def _plot(path: Path, rows: list[dict[str, float]], selected: dict[str, float]) -> None:
    theta = np.asarray([row["theta"] for row in rows])
    residual = np.asarray([row["global_residual"] for row in rows])
    boundary = np.asarray([row["boundary_spectrum_l1"] for row in rows])
    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.5), constrained_layout=True)
    axes[0].semilogy(theta, residual, "o-", ms=3)
    axes[0].axvline(selected["theta"], color="tab:red", ls="--", label="Selected")
    axes[0].axhline(1.0e-4, color="0.25", ls=":", label="Global target")
    axes[0].set(
        xlabel="Global convex fraction",
        ylabel="Predicted global original residual",
        title="(a) Convex Krylov line search",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].semilogy(theta, boundary, "s-", ms=3, label="Boundary spectral L1")
    axes[1].axhline(1.0e-3, color="0.25", ls="--", label="Boundary gate")
    axes[1].set(
        xlabel="Global convex fraction",
        ylabel="Predicted boundary change",
        title="(b) Boundary-functional guard",
    )
    axes[1].legend(frameon=False, fontsize=8)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    reports_dir = ROOT / configuration["report_directory"]
    reports_dir.mkdir(parents=True, exist_ok=True)
    reports: dict[int, dict[str, object]] = {}
    pending = []
    for block_index in configuration["fresh_affine_blocks"]:
        path = reports_dir / f"phase7b9ak_block{int(block_index):02d}.json"
        if path.exists():
            row = json.loads(path.read_text(encoding="utf-8"))
            if row.get("protocol_sha256") == EXPECTED_PROTOCOL_SHA256:
                reports[int(block_index)] = row
                continue
        pending.append((int(block_index), path))
    concurrency = int(configuration["maximum_concurrent_processes"])
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
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
            for index, path in batch
        ]
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"Phase 7B9ak worker batch failed: {codes}")
        for index, path in batch:
            row = json.loads(path.read_text(encoding="utf-8"))
            if row.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
                raise RuntimeError("Phase 7B9ak worker report changed")
            reports[index] = row
        print(
            json.dumps(
                {
                    "completed_blocks": len(reports),
                    "total_blocks": len(configuration["fresh_affine_blocks"]),
                    "latest_blocks": [index for index, _ in batch],
                }
            ),
            flush=True,
        )
    stable_summary = json.loads(
        (ROOT / protocol["sources"]["phase7b9af_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    candidate_summary = json.loads(
        (ROOT / protocol["sources"]["phase7b9aj_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    stable_by_block = {
        int(row["block_index"]): row for row in stable_summary["reports"]
    }
    candidate_by_block = {
        int(row["block_index"]): row for row in candidate_summary["reports"]
    }
    unchanged = [int(index) for index in configuration["unchanged_blocks"]]
    endpoint_report_keys = (
        "maximum_absolute_original_operator_change",
        "maximum_original_operator_scale",
        "boundary_spectrum_l1_numerator",
        "current_boundary_absolute_scale",
        "mapped_boundary_absolute_scale",
        "current_boundary_bolometric",
        "mapped_boundary_bolometric",
        "minimum_trial_intensity",
        "minimum_mapped_intensity",
    )
    unchanged_endpoint_maximum_difference = max(
        abs(
            float(stable_by_block[index][key])
            - float(candidate_by_block[index][key])
        )
        for index in unchanged
        for key in endpoint_report_keys
    )
    # 中文：未替换的远端块及其邻频守卫完全相同，残差不随 theta 变化。
    rows = []
    for grid_index, theta in enumerate(configuration["theta_grid"]):
        fresh = [reports[index]["grid"][grid_index] for index in reports]
        fixed = [stable_by_block[index] for index in unchanged]
        maximum_change = max(
            [float(row["maximum_absolute_change"]) for row in fresh]
            + [float(row["maximum_absolute_original_operator_change"]) for row in fixed]
        )
        maximum_scale = max(
            [float(row["maximum_scale"]) for row in fresh]
            + [float(row["maximum_original_operator_scale"]) for row in fixed]
        )
        boundary_numerator = sum(
            float(row["boundary_spectrum_l1_numerator"]) for row in fresh
        ) + sum(float(row["boundary_spectrum_l1_numerator"]) for row in fixed)
        current_scale = sum(float(row["current_boundary_absolute_scale"]) for row in fresh) + sum(
            float(row["current_boundary_absolute_scale"]) for row in fixed
        )
        mapped_scale = sum(float(row["mapped_boundary_absolute_scale"]) for row in fresh) + sum(
            float(row["mapped_boundary_absolute_scale"]) for row in fixed
        )
        current_bolometric = sum(float(row["current_boundary_bolometric"]) for row in fresh) + sum(
            float(row["current_boundary_bolometric"]) for row in fixed
        )
        mapped_bolometric = sum(float(row["mapped_boundary_bolometric"]) for row in fresh) + sum(
            float(row["mapped_boundary_bolometric"]) for row in fixed
        )
        rows.append(
            {
                "theta": float(theta),
                "global_residual": maximum_change / maximum_scale,
                "boundary_spectrum_l1": boundary_numerator
                / max(current_scale, mapped_scale),
                "boundary_bolometric_fraction": abs(
                    mapped_bolometric - current_bolometric
                )
                / max(abs(current_bolometric), abs(mapped_bolometric)),
                "minimum_current_intensity": min(
                    [float(row["minimum_current_intensity"]) for row in fresh]
                    + [
                        float(stable_by_block[index]["minimum_trial_intensity"])
                        for index in unchanged
                    ]
                ),
                "minimum_mapped_intensity": min(
                    [float(row["minimum_mapped_intensity"]) for row in fresh]
                    + [
                        float(stable_by_block[index]["minimum_mapped_intensity"])
                        for index in unchanged
                    ]
                ),
            }
        )
    selected = min(rows, key=lambda row: (row["global_residual"], row["theta"]))
    theta_zero = rows[0]
    theta_one = rows[-1]
    gates = protocol["gates"]
    checks = {
        "block_partition_pass": len(reports)
        == gates["fresh_affine_block_count_exactly"]
        and len(unchanged) == gates["unchanged_block_count_exactly"],
        "unchanged_endpoint_reports_match_pass": (
            unchanged_endpoint_maximum_difference
            <= gates["unchanged_endpoint_report_absolute_tolerance"]
        ),
        "endpoint_reproduction_pass": abs(
            theta_zero["global_residual"]
            - stable_summary["mapped_state_global_original_operator_residual"]
        ) <= gates["theta_zero_endpoint_absolute_tolerance"]
        and abs(
            theta_one["global_residual"]
            - candidate_summary["mapped_state_global_original_operator_residual"]
        ) <= gates["theta_one_endpoint_absolute_tolerance"],
        "positivity_pass": all(
            row["minimum_current_intensity"]
            >= gates["minimum_stable_candidate_and_mapped_intensity_at_least"]
            and row["minimum_mapped_intensity"]
            >= gates["minimum_stable_candidate_and_mapped_intensity_at_least"]
            for row in rows
        ),
        "selected_residual_improvement_pass": selected["global_residual"]
        / stable_summary["mapped_state_global_original_operator_residual"]
        < gates["selected_predicted_residual_ratio_below"],
        "selected_boundary_pass": selected["boundary_spectrum_l1"]
        < gates["selected_boundary_spectrum_l1_below"]
        and selected["boundary_bolometric_fraction"]
        < gates["selected_boundary_bolometric_fraction_below"],
        "resources_pass": all(
            row["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and row["wall_runtime_s"]
            < gates["each_worker_wall_time_strictly_below_s"]
            for row in reports.values()
        ),
    }
    passed = all(checks.values())
    figure = OUTPUT / "phase7b9ak_global_convex_krylov_line.png"
    _plot(figure, rows, selected)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "selected_theta": selected["theta"],
        "selected_predicted_global_residual": selected["global_residual"],
        "selected_residual_ratio_to_stable": selected["global_residual"]
        / stable_summary["mapped_state_global_original_operator_residual"],
        "selected_boundary_spectrum_l1": selected["boundary_spectrum_l1"],
        "selected_boundary_bolometric_fraction": selected[
            "boundary_bolometric_fraction"
        ],
        "unchanged_endpoint_maximum_report_difference": (
            unchanged_endpoint_maximum_difference
        ),
        "gate_checks": checks,
        "decision": {
            "global_convex_line_search_passed": passed,
            "write_selected_blend_authorized": passed,
            "fresh_global_blend_audit_authorized": passed,
            "material_feedback_authorized": False,
        },
        "grid": rows,
        "reports": [reports[index] for index in sorted(reports)],
        "figures": [figure.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9ak_global_convex_krylov_line_summary.json", summary
    )
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9ak_preregistered_global_convex_krylov_line.json",
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
