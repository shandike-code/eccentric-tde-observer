"""Phase 7B9ac：可恢复的全频率正 Picard 映射。"""

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
    "5f3185e19907df888ac820e29cab02e020a6eecafe85e489122d2ed1fca0f83d"
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
        raise RuntimeError("frozen Phase 7B9ac protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9ac source changed: {source['path']}"
                )
    return protocol


def _shape(protocol: dict[str, object]) -> tuple[int, int, int]:
    configuration = protocol["configuration"]
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _run_worker(
    protocol_path: Path,
    block_index: int,
    output_state: Path,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    configuration = protocol["configuration"]
    input_state = ROOT / configuration["input_state_path"]
    finite_protocol = base.phase7b9i._load_protocol(
        ROOT / protocol["sources"]["finite_trial_protocol"]["path"],
        validate_sources=False,
    )
    base.phase7b9d._configure_worker(finite_protocol, input_state)
    template_protocol = base.phase7b7i._load_protocol(
        protocol_path, validate_sources=False
    )
    context = base.phase7b7i.phase7b7e.phase7b5x._context(template_protocol)
    block = context["blocks"][block_index]
    material = base.phase7b7i._second_full_material(template_protocol)
    fields = base.phase7b7i.phase7b7e._local_fields(context, block, material)
    shape = _shape(protocol)
    input_global = np.memmap(input_state, mode="r", dtype=np.float64, shape=shape)
    output_global = np.memmap(output_state, mode="r+", dtype=np.float64, shape=shape)
    full_active_start = int(context["stencil"].active_outer_group_start)
    full_active_stop = int(context["stencil"].active_outer_group_stop)
    physical_start = max(block.outer_group_start, full_active_start)
    physical_stop = min(block.outer_group_stop, full_active_stop)
    if physical_stop > physical_start:
        source_slice = slice(
            physical_start - full_active_start,
            physical_stop - full_active_start,
        )
        fields["outer"][
            physical_start - block.outer_group_start : physical_stop
            - block.outer_group_start
        ] = input_global[source_slice]
    core = slice(block.core_group_start, block.core_group_stop)
    initial = np.array(input_global[core], copy=True)
    baseline_rss = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
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
        diagnostic_fixed_iteration_count=int(
            configuration["diagnostic_fixed_iteration_count"]
        ),
        spatial_scheme=configuration["spatial_scheme"],
        source_map_only=bool(configuration["source_map_only"]),
    )
    mapped = np.array(result.final_lab_intensity_density, copy=True)
    if not np.all(np.isfinite(mapped)) or np.any(mapped < 0.0):
        raise ArithmeticError("Phase 7B9ac mapped state is not finite and nonnegative")
    output_global[core] = mapped
    output_global.flush()
    with np.load(ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]) as master:
        frequency_width = np.diff(np.asarray(master["active_edge_hz"]))[core]
    current_flux = base._block_flux(
        initial, np.asarray(context["mu"]), np.asarray(context["weight"]), frequency_width
    )
    mapped_flux = base._block_flux(
        mapped, np.asarray(context["mu"]), np.asarray(context["weight"]), frequency_width
    )
    change = float(np.max(np.abs(mapped - initial)))
    scale = max(float(np.max(np.abs(initial))), float(np.max(np.abs(mapped))))
    peak_rss = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "input_state_sha256": configuration["input_state_sha256"],
        "block_index": block_index,
        "core_group_start": int(block.core_group_start),
        "core_group_stop": int(block.core_group_stop),
        "maximum_absolute_radiation_change": change,
        "maximum_radiation_scale": scale,
        "block_relative_radiation_change": change / scale if scale > 0.0 else change,
        "boundary_spectrum_l1_numerator": float(
            np.sum(np.abs(mapped_flux - current_flux))
        ),
        "current_boundary_absolute_scale": float(np.sum(np.abs(current_flux))),
        "mapped_boundary_absolute_scale": float(np.sum(np.abs(mapped_flux))),
        "current_boundary_bolometric": float(np.sum(current_flux)),
        "mapped_boundary_bolometric": float(np.sum(mapped_flux)),
        "minimum_input_intensity": float(np.min(initial)),
        "minimum_mapped_intensity": float(np.min(mapped)),
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
        "wall_runtime_s": time.perf_counter() - started,
    }
    del result, mapped, initial, fields, material, input_global, output_global
    gc.collect()
    _write_json_atomic(report_path, report)


def _plot(
    path: Path,
    reports: list[dict[str, object]],
    input_residual: float,
    boundary_l1: float,
    bolometric: float,
) -> None:
    block = np.asarray([row["block_index"] for row in reports])
    local = np.asarray([row["block_relative_radiation_change"] for row in reports])
    rss = np.asarray([row["peak_process_rss_mib"] for row in reports])
    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.5), constrained_layout=True)
    axes[0].semilogy(block, local, "o-", ms=3)
    axes[0].set(
        xlabel="Natural frequency block",
        ylabel="Block-relative Picard change",
        title="(a) Globally guarded positive Picard map",
    )
    axes[1].axis("off")
    axes[1].text(
        0.04,
        0.95,
        "(b) Recoverable full-map audit\n\n"
        f"Input global residual = {input_residual:.3e}\n"
        f"Boundary spectral L1 = {boundary_l1:.3e}\n"
        f"Boundary bolometric = {bolometric:.3e}\n"
        f"Maximum worker RSS = {float(np.max(rss)):.1f} MiB",
        transform=axes[1].transAxes,
        va="top",
        fontsize=10.5,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    shape = _shape(protocol)
    input_state = ROOT / configuration["input_state_path"]
    output_state = ROOT / configuration["output_state_path"]
    expected_size = int(configuration["raw_float64_checkpoint_size_bytes"])
    manifest_path = ROOT / configuration["manifest_path"]
    summary_path = ROOT / configuration.get(
        "summary_path", "outputs/phase7b9ac_global_positive_picard_map_summary.json"
    )
    figure_path = ROOT / configuration.get(
        "figure_path", "outputs/phase7b9ac_global_positive_picard_map.png"
    )
    report_prefix = str(configuration.get("block_report_prefix", "phase7b9ac"))
    runner_path = ROOT / configuration.get(
        "runner_path", "scripts/phase7b9ac_global_positive_picard_map.py"
    )
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
            raise RuntimeError("Phase 7B9ac manifest belongs to another protocol")
        if manifest.get("input_state_sha256") != configuration["input_state_sha256"]:
            raise RuntimeError("Phase 7B9ac manifest input changed")
        for row in manifest["completed_blocks"]:
            digest = base.phase7b9d._block_sha256(
                output_state,
                shape,
                int(row["core_group_start"]),
                int(row["core_group_stop"]),
            )
            if digest != row["output_block_sha256"]:
                raise RuntimeError(
                    f"Phase 7B9ac completed block changed: {row['block_index']}"
                )
    else:
        if (
            output_state.stat().st_size != expected_size
            or base._sha256(output_state)
            != configuration["output_state_previous_sha256"]
        ):
            raise RuntimeError("Phase 7B9ac reusable output buffer changed")
        manifest = {
            "phase": protocol["phase"],
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "status": "running",
            "input_state_path": configuration["input_state_path"],
            "input_state_sha256": configuration["input_state_sha256"],
            "output_state_path": configuration["output_state_path"],
            "completed_blocks": [],
            "accumulated_wall_runtime_s": 0.0,
        }
        _write_json_atomic(manifest_path, manifest)
    if manifest["status"] == "complete":
        return json.loads(summary_path.read_text(encoding="utf-8"))
    completed = {int(row["block_index"]): row for row in manifest["completed_blocks"]}
    report_directory = ROOT / configuration["report_directory"]
    report_directory.mkdir(parents=True, exist_ok=True)
    pending = [index for index in range(76) if index not in completed]
    concurrency = int(configuration["maximum_concurrent_processes"])
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        started = time.perf_counter()
        processes = []
        report_paths = []
        for block_index in batch:
            report_path = report_directory / f"{report_prefix}_block{block_index:02d}.json"
            report_paths.append(report_path)
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(runner_path),
                        "--worker",
                        "--protocol",
                        str(protocol_path),
                        "--block-index",
                        str(block_index),
                        "--output-state",
                        str(output_state),
                        "--worker-report",
                        str(report_path),
                    ],
                    cwd=ROOT,
                )
            )
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"Phase 7B9ac worker batch failed: {codes}")
        for block_index, report_path in zip(batch, report_paths, strict=True):
            row = json.loads(report_path.read_text(encoding="utf-8"))
            if (
                row.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256
                or int(row.get("block_index", -1)) != block_index
            ):
                raise RuntimeError("Phase 7B9ac worker report validation failed")
            row["output_block_sha256"] = base.phase7b9d._block_sha256(
                output_state,
                shape,
                int(row["core_group_start"]),
                int(row["core_group_stop"]),
            )
            manifest["completed_blocks"].append(row)
        manifest["completed_blocks"].sort(key=lambda row: int(row["block_index"]))
        manifest["accumulated_wall_runtime_s"] = float(
            manifest["accumulated_wall_runtime_s"]
        ) + (time.perf_counter() - started)
        _write_json_atomic(manifest_path, manifest)
        print(
            json.dumps(
                {
                    "completed_blocks": len(manifest["completed_blocks"]),
                    "total_blocks": 76,
                    "latest_blocks": batch,
                }
            ),
            flush=True,
        )
    reports = list(manifest["completed_blocks"])
    ownership = np.zeros(shape[0], dtype=np.int64)
    for row in reports:
        ownership[int(row["core_group_start"]) : int(row["core_group_stop"])] += 1
    maximum_change = max(float(row["maximum_absolute_radiation_change"]) for row in reports)
    maximum_scale = max(float(row["maximum_radiation_scale"]) for row in reports)
    input_residual = maximum_change / maximum_scale if maximum_scale > 0.0 else maximum_change
    boundary_numerator = sum(float(row["boundary_spectrum_l1_numerator"]) for row in reports)
    current_scale = sum(float(row["current_boundary_absolute_scale"]) for row in reports)
    mapped_scale = sum(float(row["mapped_boundary_absolute_scale"]) for row in reports)
    boundary_l1 = boundary_numerator / max(current_scale, mapped_scale)
    current_bolometric = sum(float(row["current_boundary_bolometric"]) for row in reports)
    mapped_bolometric = sum(float(row["mapped_boundary_bolometric"]) for row in reports)
    bolometric = abs(mapped_bolometric - current_bolometric) / max(
        abs(current_bolometric), abs(mapped_bolometric)
    )
    audit_source_key = str(
        configuration.get("input_audit_source_key", "phase7b9ab_summary")
    )
    audit_residual_key = str(
        configuration.get(
            "input_audit_residual_key", "global_original_operator_residual"
        )
    )
    audit_boundary_l1_key = str(
        configuration.get("input_audit_boundary_l1_key", "global_boundary_spectrum_l1")
    )
    audit_bolometric_key = str(
        configuration.get(
            "input_audit_bolometric_key", "global_boundary_bolometric_fraction"
        )
    )
    audit = json.loads(
        (ROOT / protocol["sources"][audit_source_key]["path"]).read_text(
            encoding="utf-8"
        )
    )
    checks = {
        "frequency_ownership_pass": len(reports) == gates["block_count_exactly"]
        and int(np.sum(ownership)) == gates["owned_frequency_group_count_exactly"]
        and bool(np.all(ownership == 1)),
        "positive_map_pass": all(
            row["minimum_input_intensity"]
            >= gates["minimum_input_and_mapped_intensity_at_least"]
            and row["minimum_mapped_intensity"]
            >= gates["minimum_input_and_mapped_intensity_at_least"]
            for row in reports
        ),
        "input_residual_reproduction_pass": abs(
            input_residual - audit[audit_residual_key]
        ) <= gates["input_global_residual_matches_phase7b9ab_absolute_tolerance"],
        "input_boundary_reproduction_pass": abs(
            boundary_l1 - audit[audit_boundary_l1_key]
        ) <= gates["input_boundary_metrics_match_phase7b9ab_absolute_tolerance"]
        and abs(bolometric - audit[audit_bolometric_key])
        <= gates["input_boundary_metrics_match_phase7b9ab_absolute_tolerance"],
        "worker_resources_pass": all(
            row["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            for row in reports
        )
        and float(manifest["accumulated_wall_runtime_s"])
        < gates["full_map_wall_time_strictly_below_s"],
    }
    passed = all(checks.values())
    output_sha = base._sha256(output_state)
    _plot(figure_path, reports, input_residual, boundary_l1, bolometric)
    manifest["status"] = "complete" if passed else "gate_failed"
    manifest["output_state_sha256"] = output_sha
    _write_json_atomic(manifest_path, manifest)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "input_state_path": configuration["input_state_path"],
        "input_state_sha256": configuration["input_state_sha256"],
        "output_state_path": configuration["output_state_path"],
        "output_state_sha256": output_sha,
        "input_global_original_operator_residual": input_residual,
        "input_boundary_spectrum_l1": boundary_l1,
        "input_boundary_bolometric_fraction": bolometric,
        "maximum_process_peak_rss_mib": max(
            float(row["peak_process_rss_mib"]) for row in reports
        ),
        "wall_runtime_s": manifest["accumulated_wall_runtime_s"],
        "gate_checks": checks,
        "decision": {
            "global_positive_picard_map_passed": passed,
            "mapped_state_committed_as_diagnostic_candidate": passed,
            "mapped_state_self_guard_residual_audit_authorized": passed,
            "material_feedback_authorized": False,
        },
        "reports": reports,
        "figures": [figure_path.name],
    }
    _write_json_atomic(summary_path, summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9ac_preregistered_global_positive_picard_map.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if (
            args.block_index is None
            or args.output_state is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires block, output state and report")
        _run_worker(
            args.protocol, args.block_index, args.output_state, args.worker_report
        )
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
