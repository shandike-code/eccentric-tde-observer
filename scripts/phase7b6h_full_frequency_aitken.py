"""Phase 7B6h：从第 4 次检查点续跑四次完整全频向量 Aitken。"""

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
    from scripts.phase7b6f_full_frequency_contraction import (
        _local_fields,
        _shape,
        _write_json_atomic,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b5x_full_depth_block_probe as phase7b5x  # type: ignore[no-redef]
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )
    from phase7b6f_full_frequency_contraction import (  # type: ignore[no-redef]
        _local_fields,
        _shape,
        _write_json_atomic,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "929bada3bf2e80f0dfd5ae2af25c1909630c41805536a5bf586fa618cf1c321f"
)
MIB = 1024**2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B6h protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6h source changed: {source['path']}")
    return protocol


def run_worker(
    protocol_path: Path,
    global_iteration: int,
    worker_index: int,
    current_path: Path,
    output_path: Path,
    residual_output_path: Path,
    previous_residual_path: Path | None,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    process_count = int(configuration["process_count"])
    if worker_index < 0 or worker_index >= process_count:
        raise ValueError("worker index left the frozen process assignment")
    context = phase7b5x._context(protocol)
    if int(context["phase"]) != int(configuration["phase_index"]):
        raise RuntimeError("Phase 7B6h selected phase changed")
    shape = _shape(protocol)
    current_global = np.memmap(
        current_path, mode="r", dtype=np.float64, shape=shape
    )
    output_global = np.memmap(
        output_path, mode="r+", dtype=np.float64, shape=shape
    )
    residual_output = np.memmap(
        residual_output_path, mode="r+", dtype=np.float64, shape=shape
    )
    previous_residual = (
        np.memmap(previous_residual_path, mode="r", dtype=np.float64, shape=shape)
        if previous_residual_path is not None
        else None
    )
    fallback_weights = tuple(float(value) for value in configuration["fallback_weights"])
    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    rows = []
    full_active_start = context["stencil"].active_outer_group_start
    full_active_stop = context["stencil"].active_outer_group_stop
    assigned = [
        (index, block)
        for index, block in enumerate(context["blocks"])
        if index % process_count == worker_index
    ]
    for local_index, (block_index, block) in enumerate(assigned, start=1):
        block_started = time.perf_counter()
        fields = _local_fields(context, block)
        physical_start = max(block.outer_group_start, full_active_start)
        physical_stop = min(block.outer_group_stop, full_active_stop)
        if physical_stop > physical_start:
            fields["outer"][
                physical_start - block.outer_group_start : physical_stop
                - block.outer_group_start
            ] = current_global[
                physical_start - full_active_start : physical_stop - full_active_start
            ]
        core = slice(block.core_group_start, block.core_group_stop)
        current_core = np.array(current_global[core], copy=True)
        operator_started = time.perf_counter()
        result = solve_mixed_frame_ale_group_step(
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
            propagation_speed_cm_s=LIGHT_SPEED_CM_S,
            source_iteration_initial_guess=current_core,
            diagnostic_fixed_iteration_count=1,
            spatial_scheme="hybrid_step_turning_upwind",
            source_map_only=True,
        )
        operator_runtime = time.perf_counter() - operator_started
        mapped = result.final_lab_intensity_density
        residual = mapped - current_core
        output_global[core] = mapped
        residual_output[core] = residual
        numerator = None
        denominator = None
        if previous_residual is not None:
            previous_core = np.asarray(previous_residual[core])
            residual_change = residual - previous_core
            numerator = float(
                np.einsum("fmd,fmd->", previous_core, residual_change)
            )
            denominator = float(
                np.einsum("fmd,fmd->", residual_change, residual_change)
            )
        trial_checks = {}
        for omega in fallback_weights:
            trial = mapped if omega == 1.0 else current_core + omega * residual
            finite = bool(np.all(np.isfinite(trial)))
            trial_checks[str(omega)] = {
                "finite": finite,
                "minimum_intensity": (
                    float(np.min(trial)) if finite else float("nan")
                ),
            }
        rows.append(
            {
                "global_iteration": global_iteration,
                "worker_index": worker_index,
                "block_index": block_index,
                "core_group_start": block.core_group_start,
                "core_group_stop": block.core_group_stop,
                "maximum_absolute_change": float(np.max(np.abs(residual))),
                "maximum_scale": max(
                    float(np.max(np.abs(mapped))),
                    float(np.max(np.abs(current_core))),
                ),
                "aitken_numerator": numerator,
                "aitken_denominator": denominator,
                "operator_runtime_s": operator_runtime,
                "block_runtime_s": time.perf_counter() - block_started,
                "trial_checks": trial_checks,
            }
        )
        if local_index == 1 or local_index % 10 == 0 or local_index == len(assigned):
            print(
                json.dumps(
                    {
                        "global_iteration": global_iteration,
                        "worker": worker_index + 1,
                        "completed": local_index,
                        "assigned": len(assigned),
                    }
                ),
                flush=True,
            )
    output_global.flush()
    residual_output.flush()
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "global_iteration": global_iteration,
        "worker_index": worker_index,
        "assigned_block_count": len(assigned),
        "runtime_s": time.perf_counter() - started,
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
        "rows": rows,
    }
    _write_json_atomic(report_path, report)


def _fallback_weight(
    rows: list[dict[str, object]], weights: tuple[float, ...]
) -> tuple[float, float, dict[str, object]]:
    checks = {}
    for omega in weights:
        local = [row["trial_checks"][str(omega)] for row in rows]
        finite = all(item["finite"] for item in local)
        minimum = min(item["minimum_intensity"] for item in local) if finite else float("nan")
        accepted = bool(finite and minimum >= 0.0)
        checks[str(omega)] = {
            "finite": finite,
            "minimum_intensity": minimum,
            "accepted": accepted,
        }
        if accepted:
            return omega, minimum, checks
    raise ArithmeticError("all global Aitken fallback states were invalid")


def _trial_minimum(
    current_path: Path,
    mapped_path: Path,
    shape: tuple[int, int, int],
    omega: float,
    chunk_groups: int,
) -> tuple[bool, float]:
    if not np.isfinite(omega) or omega <= 0.0:
        return False, float("nan")
    current = np.memmap(current_path, mode="r", dtype=np.float64, shape=shape)
    mapped = np.memmap(mapped_path, mode="r", dtype=np.float64, shape=shape)
    minimum = np.inf
    for start in range(0, shape[0], chunk_groups):
        stop = min(start + chunk_groups, shape[0])
        trial = current[start:stop] + omega * (mapped[start:stop] - current[start:stop])
        if not np.all(np.isfinite(trial)):
            return False, float("nan")
        minimum = min(minimum, float(np.min(trial)))
    return bool(minimum >= 0.0), float(minimum)


def _apply_weight(
    current_path: Path,
    mapped_path: Path,
    shape: tuple[int, int, int],
    omega: float,
    chunk_groups: int,
) -> float:
    current = np.memmap(current_path, mode="r", dtype=np.float64, shape=shape)
    mapped = np.memmap(mapped_path, mode="r+", dtype=np.float64, shape=shape)
    minimum = np.inf
    for start in range(0, shape[0], chunk_groups):
        stop = min(start + chunk_groups, shape[0])
        trial = current[start:stop] + omega * (mapped[start:stop] - current[start:stop])
        if not np.all(np.isfinite(trial)) or float(np.min(trial)) < 0.0:
            raise ArithmeticError("accepted global Aitken state failed write audit")
        minimum = min(minimum, float(np.min(trial)))
        mapped[start:stop] = trial
    mapped.flush()
    return float(minimum)


def _plot(path: Path, history: list[dict[str, object]]) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    iteration = [row["global_iteration"] for row in history]
    axes[0, 0].semilogy(
        iteration,
        [row["raw_fixed_point_residual"] for row in history],
        "o-",
        color="#4c78a8",
    )
    axes[0, 0].set(
        xlabel="Global source-map count",
        ylabel="Raw fixed-point residual",
        title="(a) Full-frequency Aitken pilot",
    )
    axes[0, 1].plot(
        iteration,
        [row["accepted_weight"] for row in history],
        "o-",
        color="#f58518",
    )
    axes[0, 1].set(
        xlabel="Global source-map count",
        ylabel="Accepted weight",
        title="(b) Dynamic global weight",
    )
    axes[1, 0].bar(
        [str(value) for value in iteration],
        [row["wall_runtime_s"] for row in history],
        color="#54a24b",
    )
    axes[1, 0].set(
        xlabel="Global source-map count",
        ylabel="Wall runtime (s)",
        title="(c) Iteration cost",
    )
    axes[1, 1].plot(
        iteration,
        [row["maximum_worker_peak_rss_mib"] for row in history],
        "o-",
        color="#e45756",
        label="Measured",
    )
    axes[1, 1].axhline(6144.0, color="0.25", ls="--", label="Process gate")
    axes[1, 1].set(
        xlabel="Global source-map count",
        ylabel="Peak RSS (MiB)",
        title="(d) Per-process memory",
    )
    axes[1, 1].legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    shape = _shape(protocol)
    expected_bytes = int(np.prod(shape, dtype=np.int64) * np.dtype(np.float64).itemsize)
    initial_path = ROOT / protocol["initial_checkpoint"]["path"]
    if _sha256(initial_path) != protocol["initial_checkpoint"]["sha256"]:
        raise RuntimeError("Phase 7B6h initial checkpoint hash changed")
    state_checkpoint = ROOT / configuration["state_checkpoint_path"]
    residual_checkpoint = ROOT / configuration["residual_checkpoint_path"]
    for path in (state_checkpoint, residual_checkpoint):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite retained checkpoint: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    process_count = int(configuration["process_count"])
    fallback_weights = tuple(float(value) for value in configuration["fallback_weights"])
    history = []
    all_worker_reports = []
    state_secondary = None
    residual_secondary = None
    final_state_hash = None
    final_residual_hash = None
    with tempfile.TemporaryDirectory(
        prefix="phase7b6h_", dir=state_checkpoint.parent
    ) as temporary_name:
        temporary = Path(temporary_name)
        state_paths = [temporary / "state_a.dat", temporary / "state_b.dat"]
        residual_paths = [temporary / "residual_a.dat", temporary / "residual_b.dat"]
        for path in (*state_paths, *residual_paths):
            array = np.memmap(path, mode="w+", dtype=np.float64, shape=shape)
            array.flush()
            del array
        current_path = initial_path
        output_path = state_paths[0]
        previous_residual_path = None
        residual_output_path = residual_paths[0]
        previous_weight = 1.0
        start_iteration = int(protocol["initial_checkpoint"]["completed_source_maps"])
        additional = int(configuration["additional_source_map_count_exactly"])
        for offset in range(1, additional + 1):
            global_iteration = start_iteration + offset
            iteration_started = time.perf_counter()
            report_paths = []
            processes = []
            for worker_index in range(process_count):
                report_path = OUTPUT / (
                    f"phase7b6h_iteration{global_iteration}_worker{worker_index + 1}.json"
                )
                report_paths.append(report_path)
                command = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker",
                    "--protocol",
                    str(protocol_path),
                    "--global-iteration",
                    str(global_iteration),
                    "--worker-index",
                    str(worker_index),
                    "--current-state",
                    str(current_path),
                    "--output-state",
                    str(output_path),
                    "--residual-output",
                    str(residual_output_path),
                    "--worker-report",
                    str(report_path),
                ]
                if previous_residual_path is not None:
                    command.extend(
                        ["--previous-residual", str(previous_residual_path)]
                    )
                processes.append(subprocess.Popen(command, cwd=ROOT))
            return_codes = [process.wait() for process in processes]
            if any(code != 0 for code in return_codes):
                raise RuntimeError(
                    f"Phase 7B6h iteration {global_iteration} failed: {return_codes}"
                )
            worker_reports = [
                json.loads(path.read_text(encoding="utf-8")) for path in report_paths
            ]
            all_worker_reports.extend(worker_reports)
            rows = sorted(
                [row for report in worker_reports for row in report["rows"]],
                key=lambda row: row["core_group_start"],
            )
            unique_coverage = bool(
                len(rows) == int(configuration["block_count"])
                and rows[0]["core_group_start"] == 0
                and rows[-1]["core_group_stop"] == shape[0]
                and all(
                    first["core_group_stop"] == second["core_group_start"]
                    for first, second in zip(rows[:-1], rows[1:], strict=True)
                )
            )
            maximum_absolute = max(row["maximum_absolute_change"] for row in rows)
            maximum_scale = max(row["maximum_scale"] for row in rows)
            raw_residual = (
                maximum_absolute / maximum_scale
                if maximum_scale > 0.0
                else maximum_absolute
            )
            aitken_weight = None
            numerator = None
            denominator = None
            accepted_method = None
            if previous_residual_path is not None:
                numerator = sum(row["aitken_numerator"] for row in rows)
                denominator = sum(row["aitken_denominator"] for row in rows)
                if denominator > 0.0:
                    aitken_weight = -previous_weight * numerator / denominator
                valid, minimum = _trial_minimum(
                    current_path,
                    output_path,
                    shape,
                    aitken_weight,
                    int(configuration["core_frequency_groups"]),
                )
                if valid:
                    accepted_weight = float(aitken_weight)
                    accepted_method = "vector Aitken"
                else:
                    accepted_weight, minimum, fallback_checks = _fallback_weight(
                        rows, fallback_weights
                    )
                    accepted_method = "guarded fallback"
            else:
                accepted_weight, minimum, fallback_checks = _fallback_weight(
                    rows, fallback_weights
                )
                accepted_method = "guarded fallback"
            minimum = _apply_weight(
                current_path,
                output_path,
                shape,
                accepted_weight,
                int(configuration["core_frequency_groups"]),
            )
            history.append(
                {
                    "global_iteration": global_iteration,
                    "block_count": len(rows),
                    "unique_full_group_coverage": unique_coverage,
                    "raw_fixed_point_residual": raw_residual,
                    "aitken_candidate_weight": aitken_weight,
                    "aitken_numerator": numerator,
                    "aitken_denominator": denominator,
                    "accepted_method": accepted_method,
                    "accepted_weight": accepted_weight,
                    "minimum_intensity": minimum,
                    "wall_runtime_s": time.perf_counter() - iteration_started,
                    "maximum_worker_peak_rss_mib": max(
                        report["peak_process_rss_mib"] for report in worker_reports
                    ),
                    "worker_runtimes_s": [
                        report["runtime_s"] for report in worker_reports
                    ],
                }
            )
            old_current = current_path
            old_residual = previous_residual_path
            current_path = output_path
            previous_residual_path = residual_output_path
            previous_weight = accepted_weight
            output_path = (
                state_paths[1]
                if current_path == state_paths[0]
                else state_paths[0]
            )
            residual_output_path = (
                residual_paths[1]
                if previous_residual_path == residual_paths[0]
                else residual_paths[0]
            )
            if old_current in state_paths and output_path != old_current:
                raise ArithmeticError("alternating Aitken state lost its old path")
            if old_residual in residual_paths and residual_output_path != old_residual:
                raise ArithmeticError("alternating Aitken residual lost its old path")
        final_state_hash = _sha256(current_path)
        final_residual_hash = _sha256(previous_residual_path)
        os.replace(current_path, state_checkpoint)
        os.replace(previous_residual_path, residual_checkpoint)
        state_secondary = output_path
        residual_secondary = residual_output_path
    secondary_removed = bool(
        state_secondary is not None
        and residual_secondary is not None
        and not state_secondary.exists()
        and not residual_secondary.exists()
    )
    gates = protocol["gates"]
    residuals = [row["raw_fixed_point_residual"] for row in history]
    accepted_weights = [row["accepted_weight"] for row in history]
    dot_values = [
        value
        for row in history
        for value in (row["aitken_numerator"], row["aitken_denominator"])
        if value is not None
    ]
    decision = {
        "frozen_protocol_hash_passed": True,
        "source_and_initial_checkpoint_hashes_passed": True,
        "map_count_and_coverage_passed": bool(
            len(history) == gates["additional_source_map_count_exactly"]
            and all(
                row["block_count"] == gates["each_iteration_block_count_exactly"]
                and row["unique_full_group_coverage"]
                for row in history
            )
        ),
        "nonnegative_finite_and_aitken_used": bool(
            all(row["minimum_intensity"] >= gates["minimum_intensity_at_least"] for row in history)
            and all(np.isfinite(value) for value in (*residuals, *accepted_weights, *dot_values))
            and sum(row["accepted_method"] == "vector Aitken" for row in history)
            >= gates["aitken_step_count_at_least"]
        ),
        "contraction_gate_passed": residuals[-1] / residuals[0]
        < gates["final_to_first_resumed_raw_residual_strictly_below"],
        "resource_and_runtime_gates_passed": all(
            row["maximum_worker_peak_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and row["wall_runtime_s"]
            < gates["each_iteration_wall_time_strictly_below_s"]
            for row in history
        ),
        "checkpoint_integrity_passed": bool(
            state_checkpoint.stat().st_size
            == gates["each_checkpoint_size_bytes_exactly"]
            and residual_checkpoint.stat().st_size
            == gates["each_checkpoint_size_bytes_exactly"]
            and secondary_removed
        ),
        "full_column_fixed_point_authorized": False,
        "full_orbit_authorized": False,
        "matter_feedback_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b6h_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "source_and_initial_checkpoint_hashes_passed",
            "map_count_and_coverage_passed",
            "nonnegative_finite_and_aitken_used",
            "contraction_gate_passed",
            "resource_and_runtime_gates_passed",
            "checkpoint_integrity_passed",
        )
    )
    decision["full_frequency_aitken_fixed_point_continuation_authorized"] = bool(
        decision["phase7b6h_gate_passed"]
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "history": history,
        "worker_reports": all_worker_reports,
        "state_checkpoint_path": str(state_checkpoint.relative_to(ROOT)),
        "state_checkpoint_sha256": final_state_hash,
        "residual_checkpoint_path": str(residual_checkpoint.relative_to(ROOT)),
        "residual_checkpoint_sha256": final_residual_hash,
        "checkpoint_size_bytes": expected_bytes,
        "secondary_temporary_states_removed": secondary_removed,
        "final_to_first_resumed_raw_residual_fraction": residuals[-1] / residuals[0],
        "final_accepted_weight": accepted_weights[-1],
        "decision": decision,
        "figures": ["phase7b6h_full_frequency_aitken.png"],
    }
    _write_json_atomic(
        OUTPUT / "phase7b6h_full_frequency_aitken_summary.json", summary
    )
    _plot(OUTPUT / "phase7b6h_full_frequency_aitken.png", history)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6h_preregistered_full_frequency_aitken.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--global-iteration", type=int)
    parser.add_argument("--worker-index", type=int)
    parser.add_argument("--current-state", type=Path)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--residual-output", type=Path)
    parser.add_argument("--previous-residual", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if any(
            value is None
            for value in (
                args.global_iteration,
                args.worker_index,
                args.current_state,
                args.output_state,
                args.residual_output,
                args.worker_report,
            )
        ):
            raise ValueError("worker mode requires iteration, paths, index and report")
        run_worker(
            args.protocol,
            args.global_iteration,
            args.worker_index,
            args.current_state,
            args.output_state,
            args.residual_output,
            args.previous_residual,
            args.worker_report,
        )
        return
    summary = run(args.protocol)
    print(json.dumps(summary["decision"], indent=2))


if __name__ == "__main__":
    main()
