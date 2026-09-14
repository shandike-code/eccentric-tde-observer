"""Phase 7B6a：两进程完成正式 9632 组、4096 深度的一次源映射。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.mixed_frame_ale import solve_mixed_frame_ale_group_step
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S

try:
    from scripts import phase7b5x_full_depth_block_probe as phase7b5x
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b5x_full_depth_block_probe as phase7b5x  # type: ignore[no-redef]
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "0db832f868d56e8c4495a5e59e979b7bd5f4195b241003f6ff5797788d25ffaa"
)
MIB = 1024**2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B6a protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6a source changed: {source['path']}")
    return protocol


def run_worker(
    protocol_path: Path,
    worker_index: int,
    memmap_path: Path,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    process_count = int(configuration["process_count"])
    if worker_index < 0 or worker_index >= process_count:
        raise ValueError("worker index left the frozen process assignment")
    context = phase7b5x._context(protocol)
    full = context["full"]
    phase = int(context["phase"])
    following = int(context["following"])
    temperature = full["temperature_k"][phase]
    density = full["density_g_cm3"][phase]
    hydrogen = full["hydrogen_fraction"][phase]
    helium = full["helium_fraction"][phase]
    old_edge = phase7b5x._subdivide_column_edge(full["edge_cm"][phase], 16)
    new_edge = phase7b5x._subdivide_column_edge(full["edge_cm"][following], 16)
    shape = (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )
    output = np.memmap(memmap_path, mode="r+", dtype=np.float64, shape=shape)
    rows = []
    started = time.perf_counter()
    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    assigned = [
        (index, block)
        for index, block in enumerate(context["blocks"])
        if index % process_count == worker_index
    ]
    for local_index, (block_index, block) in enumerate(assigned, start=1):
        local = block.local_stencil
        block_started = time.perf_counter()
        parent_planck = phase7b5x._parent_group_planck(
            local.comoving_collision_edge_hz, temperature
        )
        parent_microphysics = phase7b5x.ground_state_milne_multigroup(
            density,
            temperature,
            local.comoving_collision_edge_hz,
            parent_planck,
            hydrogen[:, 0],
            hydrogen[:, 1],
            helium[:, 0],
            helium[:, 1],
            helium[:, 2],
            order_per_group=16,
        ).continuum
        true_absorption = np.repeat(
            parent_microphysics.true_absorption_total_per_cm, 16, axis=1
        )
        thermal_emissivity = np.repeat(
            parent_microphysics.thermal_emissivity_total_cgs, 16, axis=1
        )
        scattering = np.repeat(
            parent_microphysics.electron_scattering_per_cm, 16, axis=1
        )
        parent_outer = phase7b5x._parent_boosted_planck_outer(
            local.outer_lab_edge_hz,
            context["mu"],
            context["weight"],
            context["parent_beta"],
            temperature,
        )
        outer = np.repeat(parent_outer, 16, axis=2)
        active = slice(local.active_outer_group_start, local.active_outer_group_stop)
        initial = np.array(outer[active], copy=True)
        operator_started = time.perf_counter()
        result = solve_mixed_frame_ale_group_step(
            local,
            old_edge,
            new_edge,
            context["mu"],
            context["weight"],
            initial,
            outer,
            true_absorption,
            thermal_emissivity,
            scattering,
            context["beta"],
            context["duration_s"],
            propagation_speed_cm_s=LIGHT_SPEED_CM_S,
            source_iteration_initial_guess=initial,
            diagnostic_fixed_iteration_count=1,
            spatial_scheme="hybrid_step_turning_upwind",
            source_map_only=True,
        )
        operator_runtime = time.perf_counter() - operator_started
        core = slice(block.core_group_start, block.core_group_stop)
        output[core] = result.final_lab_intensity_density
        block_runtime = time.perf_counter() - block_started
        row = {
            "worker_index": worker_index,
            "block_index": block_index,
            "core_group_start": block.core_group_start,
            "core_group_stop": block.core_group_stop,
            "collision_group_count": local.comoving_collision_group_count,
            "outer_group_count": local.outer_lab_group_count,
            "block_runtime_s": block_runtime,
            "operator_runtime_s": operator_runtime,
            "minimum_intensity": result.minimum_intensity,
            "maximum_relative_change": result.final_fixed_point_change,
            "diagnostics_finite": bool(
                np.all(
                    np.isfinite(
                        [
                            block_runtime,
                            operator_runtime,
                            result.minimum_intensity,
                            result.final_fixed_point_change,
                        ]
                    )
                )
            ),
        }
        rows.append(row)
        if local_index == 1 or local_index % 5 == 0 or local_index == len(assigned):
            print(
                json.dumps(
                    {
                        "worker": worker_index + 1,
                        "completed": local_index,
                        "assigned": len(assigned),
                        "block": block_index,
                        "block_runtime_s": block_runtime,
                    }
                ),
                flush=True,
            )
    output.flush()
    peak = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "worker_index": worker_index,
        "pid": os.getpid(),
        "assigned_block_count": len(assigned),
        "runtime_s": time.perf_counter() - started,
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak / MIB,
        "rows": rows,
    }
    _write_json_atomic(report_path, report)


def _plot(
    path: Path,
    rows: list[dict[str, object]],
    reports: list[dict[str, object]],
    wall_s: float,
) -> None:
    block = np.array([row["block_index"] for row in rows])
    runtime = np.array([row["block_runtime_s"] for row in rows])
    operator = np.array([row["operator_runtime_s"] for row in rows])
    figure, axes = plt.subplots(2, 2, figsize=(13, 8))
    axes[0, 0].plot(block, runtime, ".", label="Total block")
    axes[0, 0].plot(block, operator, ".", label="Source map")
    axes[0, 0].set(
        xlabel="Block index", ylabel="Runtime (s)", title="(a) All 76 frequency blocks"
    )
    axes[0, 0].legend()
    axes[0, 1].bar(
        ["Worker 1", "Worker 2"],
        [report["runtime_s"] for report in reports],
        color=["#4c78a8", "#f58518"],
    )
    axes[0, 1].set(ylabel="Runtime (s)", title="(b) Two-process load balance")
    axes[1, 0].bar(
        ["Worker 1", "Worker 2", "Process gate"],
        [
            reports[0]["peak_process_rss_mib"],
            reports[1]["peak_process_rss_mib"],
            6144.0,
        ],
        color=["#4c78a8", "#f58518", "#555555"],
    )
    axes[1, 0].set(ylabel="Peak RSS (MiB)", title="(c) Per-process memory")
    axes[1, 1].bar(
        ["Measured wall", "Wall-time gate"],
        [wall_s, 900.0],
        color=["#54a24b", "#555555"],
    )
    axes[1, 1].set(ylabel="Runtime (s)", title="(d) Full-frequency source iteration")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6a_preregistered_full_frequency_source_iteration.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--worker-index", type=int)
    parser.add_argument("--memmap", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.worker_index is None or args.memmap is None or args.worker_report is None:
            raise ValueError("worker mode requires index, memmap and report paths")
        run_worker(args.protocol, args.worker_index, args.memmap, args.worker_report)
        return

    protocol = _load_protocol(args.protocol)
    configuration = protocol["configuration"]
    shape = (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )
    expected_bytes = int(np.prod(shape, dtype=np.int64) * np.dtype(np.float64).itemsize)
    process_count = int(configuration["process_count"])
    reports = []
    started = time.perf_counter()
    temporary_path = None
    output_hash = None
    output_size = None
    with tempfile.TemporaryDirectory(prefix="phase7b6a_") as temporary_name:
        directory = Path(temporary_name)
        temporary_path = directory / "full_frequency_source_map.dat"
        output = np.memmap(temporary_path, mode="w+", dtype=np.float64, shape=shape)
        output.flush()
        del output
        processes = []
        report_paths = []
        for worker in range(process_count):
            report_path = OUTPUT / f"phase7b6a_worker{worker + 1}.json"
            report_paths.append(report_path)
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                "--protocol",
                str(args.protocol),
                "--worker-index",
                str(worker),
                "--memmap",
                str(temporary_path),
                "--worker-report",
                str(report_path),
            ]
            processes.append(subprocess.Popen(command, cwd=ROOT))
        return_codes = [process.wait() for process in processes]
        if any(code != 0 for code in return_codes):
            raise RuntimeError(f"Phase 7B6a worker failed: {return_codes}")
        reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
        output_size = temporary_path.stat().st_size
        if output_size != expected_bytes:
            raise RuntimeError("temporary full-frequency memmap size changed")
        output_hash = _sha256(temporary_path)
    wall_s = time.perf_counter() - started
    temporary_removed = temporary_path is not None and not temporary_path.exists()
    rows = sorted(
        [row for report in reports for row in report["rows"]],
        key=lambda row: row["core_group_start"],
    )
    unique_coverage = bool(
        rows
        and rows[0]["core_group_start"] == 0
        and rows[-1]["core_group_stop"]
        == configuration["physical_frequency_groups"]
        and all(
            first["core_group_stop"] == second["core_group_start"]
            for first, second in zip(rows[:-1], rows[1:], strict=True)
        )
    )
    gates = protocol["gates"]
    minimum = min(row["minimum_intensity"] for row in rows)
    maximum_change = max(row["maximum_relative_change"] for row in rows)
    decision = {
        "frozen_protocol_hash_passed": True,
        "source_hashes_passed": True,
        "completed_block_count_passed": len(rows)
        == gates["completed_block_count_exactly"],
        "unique_core_coverage_passed": bool(
            unique_coverage
            and rows[-1]["core_group_stop"]
            == gates["unique_core_group_count_exactly"]
        ),
        "output_file_size_passed": output_size
        == gates["output_file_size_bytes_exactly"],
        "resource_gate_passed": all(
            report["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            for report in reports
        ),
        "wall_time_gate_passed": wall_s < gates["total_wall_time_strictly_below_s"],
        "nonnegative_intensity_passed": minimum >= gates["minimum_intensity_at_least"],
        "finite_diagnostics_passed": bool(
            np.isfinite(maximum_change)
            and all(row["diagnostics_finite"] for row in rows)
        ),
        "temporary_output_removed": temporary_removed,
        "full_column_fixed_point_authorized": False,
        "full_orbit_authorized": False,
        "matter_feedback_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b6a_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "source_hashes_passed",
            "completed_block_count_passed",
            "unique_core_coverage_passed",
            "output_file_size_passed",
            "resource_gate_passed",
            "wall_time_gate_passed",
            "nonnegative_intensity_passed",
            "finite_diagnostics_passed",
            "temporary_output_removed",
        )
    )
    decision["convergence_architecture_decision_authorized"] = bool(
        decision["phase7b6a_gate_passed"]
    )
    summary = {
        "phase": "7B6a measured full-frequency single source iteration",
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "workers": reports,
        "all_block_rows": rows,
        "full_frequency_output_sha256": output_hash,
        "temporary_output_file_size_bytes": output_size,
        "temporary_output_removed": temporary_removed,
        "wall_runtime_s": wall_s,
        "minimum_intensity": minimum,
        "maximum_relative_change": maximum_change,
        "sum_block_runtime_s": float(sum(row["block_runtime_s"] for row in rows)),
        "sum_operator_runtime_s": float(sum(row["operator_runtime_s"] for row in rows)),
        "decision": decision,
        "figures": ["phase7b6a_full_frequency_source_iteration.png"],
    }
    _write_json_atomic(
        OUTPUT / "phase7b6a_full_frequency_source_iteration_summary.json", summary
    )
    _plot(
        OUTPUT / "phase7b6a_full_frequency_source_iteration.png",
        rows,
        reports,
        wall_s,
    )
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
