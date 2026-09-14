"""Phase 7B7i：第二物质迭代态上的一次全频辐射映射。"""

from __future__ import annotations

import argparse
import gc
import hashlib
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
    from scripts import phase7b7e_radiation_direction as phase7b7e
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b7e_radiation_direction as phase7b7e  # type: ignore[no-redef]
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
CHECKPOINT = OUTPUT / "checkpoints"
EXPECTED_PROTOCOL_SHA256 = (
    "f9078188430b3672f84a234ea1411c07a428a8045e126528a55b24ed3158d1ea"
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


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B7i protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            if _sha256(ROOT / source["path"]) != source["sha256"]:
                raise RuntimeError(
                    f"frozen Phase 7B7i source changed: {source['path']}"
                )
    return protocol


def _shape(protocol: dict[str, object]) -> tuple[int, int, int]:
    configuration = protocol["configuration"]
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _second_full_material(protocol: dict[str, object]) -> dict[str, np.ndarray]:
    with np.load(
        ROOT / protocol["sources"]["second_material_iterate"]["path"]
    ) as state:
        density_half = np.array(state["density_g_cm3"], copy=True)
        temperature_half = np.array(state["temperature_k"], copy=True)
        hydrogen_half = np.array(state["hydrogen_fraction"], copy=True)
        helium_half = np.array(state["helium_fraction"], copy=True)

    def mirror(value: np.ndarray) -> np.ndarray:
        return np.concatenate((value, value[::-1]), axis=0)

    return {
        "density_parent": mirror(density_half),
        "temperature_parent": mirror(temperature_half),
        "hydrogen_parent": mirror(hydrogen_half),
        "helium_parent": mirror(helium_half),
    }


def run_worker(
    protocol_path: Path,
    block_index: int,
    output_state_path: Path,
    report_path: Path,
) -> None:
    # 中文：父进程已验证 10 GB 输入；子进程只验证冻结协议。
    protocol = _load_protocol(protocol_path, validate_sources=False)
    configuration = protocol["configuration"]
    context = phase7b7e.phase7b5x._context(protocol)
    if int(context["phase"]) != int(configuration["phase_index"]):
        raise RuntimeError("Phase 7B7i selected phase changed")
    if block_index < 0 or block_index >= len(context["blocks"]):
        raise ValueError("Phase 7B7i block index is invalid")
    shape = _shape(protocol)
    current_global = np.memmap(
        ROOT / protocol["sources"]["initial_radiation_state"]["path"],
        mode="r",
        dtype=np.float64,
        shape=shape,
    )
    output_global = np.memmap(
        output_state_path, mode="r+", dtype=np.float64, shape=shape
    )
    updated = _second_full_material(protocol)
    block = context["blocks"][block_index]
    fields = phase7b7e._local_fields(context, block, updated)
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
        ] = current_global[source_slice]
    core = slice(block.core_group_start, block.core_group_stop)
    current_core = np.array(current_global[core], copy=True)
    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    result = phase7b7e.solve_mixed_frame_ale_group_step(
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
        propagation_speed_cm_s=phase7b7e.LIGHT_SPEED_CM_S,
        source_iteration_initial_guess=current_core,
        diagnostic_fixed_iteration_count=1,
        spatial_scheme="hybrid_step_turning_upwind",
        source_map_only=False,
    )
    mapped = np.asarray(result.final_lab_intensity_density)
    if not np.all(np.isfinite(mapped)) or np.any(mapped < 0.0):
        raise ArithmeticError("Phase 7B7i mapped radiation state is invalid")
    output_global[core] = mapped
    output_global.flush()
    maximum_change = float(np.max(np.abs(mapped - current_core)))
    maximum_scale = max(
        float(np.max(np.abs(mapped))), float(np.max(np.abs(current_core)))
    )
    report = {
        "block_index": block_index,
        "core_group_start": int(block.core_group_start),
        "core_group_stop": int(block.core_group_stop),
        "minimum_mapped_intensity": float(np.min(mapped)),
        "minimum_local_comoving_mean_intensity": float(
            np.min(result.final_comoving_mean_intensity_density)
        ),
        "maximum_absolute_radiation_change": maximum_change,
        "maximum_radiation_scale": maximum_scale,
        "internal_global_coupled_residual": float(
            result.global_scale_normalized_coupled_residual
        ),
        "internal_total_energy_ledger_residual": float(
            result.total_relative_energy_ledger_residual
        ),
    }
    del result, mapped, current_core, fields, current_global, output_global
    gc.collect()
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report.update(
        {
            "runtime_s": time.perf_counter() - started,
            "baseline_highwater_rss_mib": baseline_rss / MIB,
            "peak_process_rss_mib": peak_rss / MIB,
        }
    )
    _write_json_atomic(report_path, report)


def _plot(
    path: Path,
    reports: list[dict[str, object]],
    raw_residual: float,
    wall_runtime: float,
) -> None:
    block = np.array([int(row["block_index"]) for row in reports])
    global_scale = max(float(row["maximum_radiation_scale"]) for row in reports)
    raw = np.array(
        [float(row["maximum_absolute_radiation_change"]) for row in reports]
    ) / global_scale
    rss = np.array([float(row["peak_process_rss_mib"]) for row in reports])
    runtime = np.array([float(row["runtime_s"]) for row in reports])
    figure, axes = plt.subplots(1, 3, figsize=(13.0, 4.0), constrained_layout=True)
    gate = 0.1
    axes[0].plot(block, raw / gate, marker="o", ms=3, lw=1)
    # 中文：symlog 原样保留精确零，不对诊断数据加 floor。
    axes[0].set_yscale("symlog", linthresh=1.0e-8)
    axes[0].set_ylim(0.0, 1.5)
    axes[0].axhline(1.0, color="0.25", ls="--", label="Trust gate")
    axes[0].set(
        xlabel="Frequency block index",
        ylabel="Fraction of radiation trust gate",
        title="(a) Second radiation direction",
    )
    axes[0].legend(frameon=False)
    scatter = axes[1].scatter(block, rss, c=runtime, cmap="viridis", s=34)
    axes[1].axhline(6144.0, color="0.25", ls="--", label="RSS gate")
    axes[1].set(
        xlabel="Frequency block index",
        ylabel="Peak process RSS (MiB)",
        title="(b) Short-lived worker resources",
    )
    axes[1].legend(frameon=False)
    figure.colorbar(scatter, ax=axes[1], label="Block runtime (s)")
    axes[2].axis("off")
    axes[2].text(
        0.05,
        0.88,
        "(c) Scope and validation\n\n"
        f"Global raw residual = {raw_residual:.3e}\n"
        f"Minimum mapped intensity = "
        f"{min(float(row['minimum_mapped_intensity']) for row in reports):.3e}\n"
        f"Maximum process RSS = {float(np.max(rss)):.1f} MiB\n"
        f"Total wall time = {wall_runtime:.1f} s\n\n"
        "Formal source and atomic rates: deferred\n"
        "Coupled fixed point: not claimed",
        transform=axes[2].transAxes,
        va="top",
        fontsize=11,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path, *, assemble_only: bool = False) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    shape = _shape(protocol)
    initial_state_path = (
        ROOT / protocol["sources"]["initial_radiation_state"]["path"]
    )
    expected_size = int(np.prod(shape, dtype=np.int64) * 8)
    if initial_state_path.stat().st_size != expected_size:
        raise RuntimeError("Phase 7B7i initial radiation-state size changed")
    block_count = int(configuration["block_count"])
    CHECKPOINT.mkdir(parents=True, exist_ok=True)
    output_state_path = CHECKPOINT / "phase7b7i_second_radiation_map.dat"
    report_paths = [
        OUTPUT / f"phase7b7i_block{index:02d}.json" for index in range(block_count)
    ]
    if assemble_only:
        if (
            not all(path.exists() for path in report_paths)
            or not output_state_path.exists()
            or output_state_path.stat().st_size != expected_size
        ):
            raise RuntimeError("Phase 7B7i assemble-only artifacts are incomplete")
    else:
        output = np.memmap(
            output_state_path, mode="w+", dtype=np.float64, shape=shape
        )
        output[:] = 0.0
        output.flush()
        del output
        started = time.perf_counter()
        concurrency = int(configuration["maximum_concurrent_processes"])
        for offset in range(0, block_count, concurrency):
            batch = range(offset, min(offset + concurrency, block_count))
            processes = [
                subprocess.Popen(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--worker",
                        "--protocol",
                        str(protocol_path),
                        "--block-index",
                        str(block_index),
                        "--output-state",
                        str(output_state_path),
                        "--worker-report",
                        str(report_paths[block_index]),
                    ],
                    cwd=ROOT,
                )
                for block_index in batch
            ]
            return_codes = [process.wait() for process in processes]
            if any(code != 0 for code in return_codes):
                raise RuntimeError(f"Phase 7B7i worker batch failed: {return_codes}")
            completed = offset + len(return_codes)
            if completed % 10 == 0 or completed == block_count:
                print(
                    json.dumps(
                        {"completed_blocks": completed, "total_blocks": block_count}
                    ),
                    flush=True,
                )
        wall_runtime = time.perf_counter() - started
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    reports.sort(key=lambda row: int(row["block_index"]))
    if assemble_only:
        earliest_start = min(
            path.stat().st_mtime - float(report["runtime_s"])
            for path, report in zip(report_paths, reports, strict=True)
        )
        latest_finish = max(path.stat().st_mtime for path in report_paths)
        wall_runtime = latest_finish - earliest_start
    ownership = np.zeros(shape[0], dtype=np.int64)
    for report in reports:
        ownership[
            int(report["core_group_start"]) : int(report["core_group_stop"])
        ] += 1
    maximum_change = max(
        float(report["maximum_absolute_radiation_change"]) for report in reports
    )
    maximum_scale = max(
        float(report["maximum_radiation_scale"]) for report in reports
    )
    raw_residual = maximum_change / maximum_scale if maximum_scale > 0.0 else maximum_change
    numeric_values = [
        float(value)
        for report in reports
        for key, value in report.items()
        if key not in {"block_index", "core_group_start", "core_group_stop"}
    ]
    rss = [float(report["peak_process_rss_mib"]) for report in reports]
    gates = protocol["gates"]
    decision = {
        "frozen_protocol_and_source_hashes_passed": True,
        "block_and_frequency_ownership_passed": bool(
            len(reports) == gates["block_count_exactly"]
            and int(np.sum(ownership))
            == gates["owned_frequency_group_count_exactly"]
            and np.all(ownership == 1)
        ),
        "mapped_state_valid": bool(
            min(float(row["minimum_mapped_intensity"]) for row in reports)
            >= gates["minimum_mapped_intensity_at_least"]
            and min(
                float(row["minimum_local_comoving_mean_intensity"])
                for row in reports
            )
            >= gates["minimum_mapped_intensity_at_least"]
            and np.all(np.isfinite(numeric_values))
        ),
        "radiation_direction_trust_passed": bool(
            raw_residual < gates["one_map_raw_radiation_residual_below"]
        ),
        "resource_and_runtime_gates_passed": bool(
            all(
                value < gates["each_process_peak_rss_strictly_below_mib"]
                for value in rss
            )
            and wall_runtime < gates["total_wall_time_strictly_below_s"]
        ),
        "assembled_source_and_atomic_rates_evaluated": False,
        "accepted_as_radiation_or_coupled_fixed_point": False,
        "third_material_update_authorized": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b7i_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_and_source_hashes_passed",
            "block_and_frequency_ownership_passed",
            "mapped_state_valid",
            "radiation_direction_trust_passed",
            "resource_and_runtime_gates_passed",
        )
    )
    decision["assembled_source_and_atomic_rate_diagnostics_authorized"] = bool(
        decision["phase7b7i_gate_passed"]
    )
    figure_path = OUTPUT / "phase7b7i_second_radiation_map.png"
    _plot(figure_path, reports, raw_residual, wall_runtime)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "block_count": len(reports),
        "owned_frequency_group_count": int(np.sum(ownership)),
        "minimum_mapped_intensity": min(
            float(row["minimum_mapped_intensity"]) for row in reports
        ),
        "one_map_raw_radiation_residual": raw_residual,
        "maximum_process_peak_rss_mib": max(rss),
        "total_wall_runtime_s": wall_runtime,
        "initial_state_path": str(initial_state_path.relative_to(ROOT)),
        "initial_state_sha256": protocol["sources"]["initial_radiation_state"][
            "sha256"
        ],
        "mapped_state_path": str(output_state_path.relative_to(ROOT)),
        "mapped_state_sha256": _sha256(output_state_path),
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b7i_second_radiation_map_summary.json", summary
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b7i_preregistered_second_radiation_map.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--assemble-only", action="store_true")
    args = parser.parse_args()
    if args.worker:
        if (
            args.block_index is None
            or args.output_state is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires block, state and report paths")
        run_worker(
            args.protocol,
            args.block_index,
            args.output_state,
            args.worker_report,
        )
        return
    summary = run(args.protocol, assemble_only=args.assemble_only)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
