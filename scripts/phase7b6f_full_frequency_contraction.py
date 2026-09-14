"""Phase 7B6f：用双 memmap 执行四次完整全频率保护源映射。"""

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
    "5131f1c8e0dc90613eb3b981a92670512995d27ab2ad95c3cd163655926394b1"
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
        raise RuntimeError(f"frozen Phase 7B6f protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6f source changed: {source['path']}")
    return protocol


def _shape(protocol: dict[str, object]) -> tuple[int, int, int]:
    configuration = protocol["configuration"]
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _local_fields(
    context: dict[str, object], block: object
) -> dict[str, np.ndarray]:
    local = block.local_stencil
    full = context["full"]
    phase = int(context["phase"])
    following = int(context["following"])
    temperature = full["temperature_k"][phase]
    density = full["density_g_cm3"][phase]
    hydrogen = full["hydrogen_fraction"][phase]
    helium = full["helium_fraction"][phase]
    parent_planck = phase7b5x._parent_group_planck(
        local.comoving_collision_edge_hz, temperature
    )
    microphysics = phase7b5x.ground_state_milne_multigroup(
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
    parent_outer = phase7b5x._parent_boosted_planck_outer(
        local.outer_lab_edge_hz,
        context["mu"],
        context["weight"],
        context["parent_beta"],
        temperature,
    )
    outer = np.repeat(parent_outer, 16, axis=2)
    active = slice(local.active_outer_group_start, local.active_outer_group_stop)
    return {
        "initial": np.array(outer[active], copy=True),
        "outer": outer,
        "true_absorption": np.repeat(
            microphysics.true_absorption_total_per_cm, 16, axis=1
        ),
        "thermal_emissivity": np.repeat(
            microphysics.thermal_emissivity_total_cgs, 16, axis=1
        ),
        "scattering": np.repeat(
            microphysics.electron_scattering_per_cm, 16, axis=1
        ),
        "old_edge": phase7b5x._subdivide_column_edge(full["edge_cm"][phase], 16),
        "new_edge": phase7b5x._subdivide_column_edge(
            full["edge_cm"][following], 16
        ),
    }


def run_worker(
    protocol_path: Path,
    iteration: int,
    worker_index: int,
    current_path: Path | None,
    output_path: Path,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    process_count = int(configuration["process_count"])
    if worker_index < 0 or worker_index >= process_count:
        raise ValueError("worker index left the frozen process assignment")
    if iteration == 1 and current_path is not None:
        raise ValueError("first full-frequency map must start from reconstructed initial state")
    if iteration > 1 and current_path is None:
        raise ValueError("later full-frequency maps require the retained current state")
    context = phase7b5x._context(protocol)
    if int(context["phase"]) != int(configuration["phase_index"]):
        raise RuntimeError("Phase 7B6f selected phase changed")
    shape = _shape(protocol)
    current_global = (
        np.memmap(current_path, mode="r", dtype=np.float64, shape=shape)
        if current_path is not None
        else None
    )
    output_global = np.memmap(
        output_path, mode="r+", dtype=np.float64, shape=shape
    )
    candidate_weights = (
        (float(configuration["first_map_forced_weight"]),)
        if iteration == 1
        else tuple(float(value) for value in configuration["later_candidate_weights"])
    )
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
        core = slice(block.core_group_start, block.core_group_stop)
        if current_global is None:
            current_core = fields["initial"]
        else:
            physical_start = max(block.outer_group_start, full_active_start)
            physical_stop = min(block.outer_group_stop, full_active_stop)
            if physical_stop > physical_start:
                fields["outer"][
                    physical_start - block.outer_group_start : physical_stop
                    - block.outer_group_start
                ] = current_global[
                    physical_start - full_active_start : physical_stop
                    - full_active_start
                ]
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
        output_global[core] = mapped
        delta = mapped - current_core
        maximum_absolute = float(np.max(np.abs(delta)))
        maximum_scale = max(
            float(np.max(np.abs(mapped))), float(np.max(np.abs(current_core)))
        )
        trial_checks = {}
        for omega in candidate_weights:
            trial = mapped if omega == 1.0 else current_core + omega * delta
            finite = bool(np.all(np.isfinite(trial)))
            trial_checks[str(omega)] = {
                "finite": finite,
                "minimum_intensity": (
                    float(np.min(trial)) if finite else float("nan")
                ),
            }
        rows.append(
            {
                "iteration": iteration,
                "worker_index": worker_index,
                "block_index": block_index,
                "core_group_start": block.core_group_start,
                "core_group_stop": block.core_group_stop,
                "maximum_absolute_change": maximum_absolute,
                "maximum_scale": maximum_scale,
                "mapped_minimum_intensity": float(np.min(mapped)),
                "operator_runtime_s": operator_runtime,
                "block_runtime_s": time.perf_counter() - block_started,
                "trial_checks": trial_checks,
            }
        )
        if local_index == 1 or local_index % 10 == 0 or local_index == len(assigned):
            print(
                json.dumps(
                    {
                        "iteration": iteration,
                        "worker": worker_index + 1,
                        "completed": local_index,
                        "assigned": len(assigned),
                    }
                ),
                flush=True,
            )
    output_global.flush()
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "iteration": iteration,
        "worker_index": worker_index,
        "assigned_block_count": len(assigned),
        "runtime_s": time.perf_counter() - started,
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
        "rows": rows,
    }
    _write_json_atomic(report_path, report)


def _choose_weight(
    rows: list[dict[str, object]], candidate_weights: tuple[float, ...]
) -> tuple[float, float, dict[str, object]]:
    checks = {}
    for omega in candidate_weights:
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
    raise ArithmeticError("even the unmodified global source-map state became invalid")


def _apply_relaxation_in_place(
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
            raise ArithmeticError("accepted global relaxation failed its in-place audit")
        minimum = min(minimum, float(np.min(trial)))
        mapped[start:stop] = trial
    mapped.flush()
    return float(minimum)


def _plot(path: Path, history: list[dict[str, object]]) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    iteration = [row["iteration"] for row in history]
    residual = [row["raw_fixed_point_residual"] for row in history]
    axes[0, 0].semilogy(iteration, residual, "o-", color="#4c78a8")
    axes[0, 0].set(
        xlabel="Full-frequency source-map count",
        ylabel="Raw fixed-point residual",
        title="(a) Global contraction",
    )
    axes[0, 1].step(
        iteration,
        [row["accepted_weight"] for row in history],
        where="mid",
        color="#f58518",
    )
    axes[0, 1].set(
        xlabel="Full-frequency source-map count",
        ylabel="Accepted weight",
        title="(b) Global whole-step guard",
        ylim=(0.95, 1.85),
    )
    axes[1, 0].bar(
        [str(value) for value in iteration],
        [row["wall_runtime_s"] for row in history],
        color="#54a24b",
    )
    axes[1, 0].set(
        xlabel="Full-frequency source-map count",
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
        xlabel="Full-frequency source-map count",
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
    checkpoint_path = ROOT / configuration["checkpoint_path"]
    if checkpoint_path.exists():
        raise FileExistsError(f"refusing to overwrite retained checkpoint: {checkpoint_path}")
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    process_count = int(configuration["process_count"])
    history = []
    all_worker_reports = []
    first_map_hash = None
    final_hash = None
    secondary_path = None
    with tempfile.TemporaryDirectory(
        prefix="phase7b6f_", dir=checkpoint_path.parent
    ) as temporary_name:
        temporary = Path(temporary_name)
        paths = [temporary / "state_a.dat", temporary / "state_b.dat"]
        for path in paths:
            array = np.memmap(path, mode="w+", dtype=np.float64, shape=shape)
            array.flush()
            del array
        current_path = None
        output_path = paths[0]
        map_count = int(configuration["source_map_count_exactly"])
        for iteration in range(1, map_count + 1):
            iteration_started = time.perf_counter()
            report_paths = []
            processes = []
            for worker_index in range(process_count):
                report_path = OUTPUT / (
                    f"phase7b6f_iteration{iteration}_worker{worker_index + 1}.json"
                )
                report_paths.append(report_path)
                command = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker",
                    "--protocol",
                    str(protocol_path),
                    "--iteration",
                    str(iteration),
                    "--worker-index",
                    str(worker_index),
                    "--output-state",
                    str(output_path),
                    "--worker-report",
                    str(report_path),
                ]
                if current_path is not None:
                    command.extend(["--current-state", str(current_path)])
                processes.append(subprocess.Popen(command, cwd=ROOT))
            return_codes = [process.wait() for process in processes]
            if any(code != 0 for code in return_codes):
                raise RuntimeError(
                    f"Phase 7B6f iteration {iteration} workers failed: {return_codes}"
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
            residual = (
                maximum_absolute / maximum_scale
                if maximum_scale > 0.0
                else maximum_absolute
            )
            candidate_weights = (
                (float(configuration["first_map_forced_weight"]),)
                if iteration == 1
                else tuple(
                    float(value) for value in configuration["later_candidate_weights"]
                )
            )
            accepted_weight, minimum, trial_checks = _choose_weight(
                rows, candidate_weights
            )
            if iteration == 1:
                first_map_hash = _sha256(output_path)
            if accepted_weight > 1.0:
                if current_path is None:
                    raise ArithmeticError("accelerated first map was not pre-registered")
                minimum = _apply_relaxation_in_place(
                    current_path,
                    output_path,
                    shape,
                    accepted_weight,
                    int(configuration["core_frequency_groups"]),
                )
            history.append(
                {
                    "iteration": iteration,
                    "block_count": len(rows),
                    "unique_full_group_coverage": unique_coverage,
                    "raw_fixed_point_residual": residual,
                    "accepted_weight": accepted_weight,
                    "minimum_intensity": minimum,
                    "trial_checks": trial_checks,
                    "wall_runtime_s": time.perf_counter() - iteration_started,
                    "maximum_worker_peak_rss_mib": max(
                        report["peak_process_rss_mib"] for report in worker_reports
                    ),
                    "worker_runtimes_s": [
                        report["runtime_s"] for report in worker_reports
                    ],
                }
            )
            previous_path = current_path
            current_path = output_path
            output_path = paths[1] if current_path == paths[0] else paths[0]
            if previous_path is not None and output_path != previous_path:
                raise ArithmeticError("alternating memmap state lost its previous path")
        if current_path is None:
            raise ArithmeticError("full-frequency pilot produced no state")
        final_hash = _sha256(current_path)
        os.replace(current_path, checkpoint_path)
        secondary_path = output_path
    secondary_removed = secondary_path is not None and not secondary_path.exists()
    gates = protocol["gates"]
    residuals = [row["raw_fixed_point_residual"] for row in history]
    decision = {
        "frozen_protocol_hash_passed": True,
        "source_hashes_passed": True,
        "first_source_map_hash_exact": first_map_hash
        == gates["first_source_map_sha256_exactly"],
        "map_count_and_coverage_passed": bool(
            len(history) == gates["source_map_count_exactly"]
            and all(
                row["block_count"] == gates["each_iteration_block_count_exactly"]
                and row["unique_full_group_coverage"]
                for row in history
            )
        ),
        "residual_contraction_gate_passed": bool(
            all(np.isfinite(value) for value in residuals)
            and all(second < first for first, second in zip(residuals[:-1], residuals[1:], strict=True))
            and residuals[-1] / residuals[0]
            < gates["final_to_first_raw_residual_strictly_below"]
        ),
        "all_intensities_nonnegative": all(
            row["minimum_intensity"] >= gates["minimum_intensity_at_least"]
            for row in history
        ),
        "resource_and_runtime_gates_passed": all(
            row["maximum_worker_peak_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and row["wall_runtime_s"]
            < gates["each_iteration_wall_time_strictly_below_s"]
            for row in history
        ),
        "checkpoint_integrity_passed": bool(
            checkpoint_path.exists()
            and checkpoint_path.stat().st_size
            == gates["checkpoint_size_bytes_exactly"]
            and secondary_removed
        ),
        "full_column_fixed_point_authorized": False,
        "full_orbit_authorized": False,
        "matter_feedback_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b6f_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "source_hashes_passed",
            "first_source_map_hash_exact",
            "map_count_and_coverage_passed",
            "residual_contraction_gate_passed",
            "all_intensities_nonnegative",
            "resource_and_runtime_gates_passed",
            "checkpoint_integrity_passed",
        )
    )
    decision["full_frequency_fixed_point_continuation_authorized"] = bool(
        decision["phase7b6f_gate_passed"]
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "history": history,
        "worker_reports": all_worker_reports,
        "first_source_map_sha256": first_map_hash,
        "final_checkpoint_path": str(checkpoint_path.relative_to(ROOT)),
        "final_checkpoint_sha256": final_hash,
        "final_checkpoint_size_bytes": checkpoint_path.stat().st_size,
        "secondary_temporary_state_removed": secondary_removed,
        "final_to_first_raw_residual_fraction": residuals[-1] / residuals[0],
        "decision": decision,
        "figures": ["phase7b6f_full_frequency_contraction.png"],
    }
    _write_json_atomic(
        OUTPUT / "phase7b6f_full_frequency_contraction_summary.json", summary
    )
    _plot(OUTPUT / "phase7b6f_full_frequency_contraction.png", history)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6f_preregistered_full_frequency_contraction.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--worker-index", type=int)
    parser.add_argument("--current-state", type=Path)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if (
            args.iteration is None
            or args.worker_index is None
            or args.output_state is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires iteration, index, output and report")
        run_worker(
            args.protocol,
            args.iteration,
            args.worker_index,
            args.current_state,
            args.output_state,
            args.worker_report,
        )
        return
    summary = run(args.protocol)
    print(json.dumps(summary["decision"], indent=2))


if __name__ == "__main__":
    main()
