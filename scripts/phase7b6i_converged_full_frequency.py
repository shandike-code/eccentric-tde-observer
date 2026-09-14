"""Phase 7B6i：可逐轮恢复的完整全频 Aitken 固定点与末态审计。"""

from __future__ import annotations

import argparse
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
    from scripts.phase7b6h_full_frequency_aitken import (
        _apply_weight,
        _fallback_weight,
        _trial_minimum,
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
    from phase7b6h_full_frequency_aitken import (  # type: ignore[no-redef]
        _apply_weight,
        _fallback_weight,
        _trial_minimum,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "5939aa002f56c75867ed154733d2eb0a90af4f6d06743032d4c5aa7ab6aa4c2c"
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
        raise RuntimeError(f"frozen Phase 7B6i protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6i source changed: {source['path']}")
    return protocol


def _allocate_state(path: Path, shape: tuple[int, int, int]) -> None:
    array = np.memmap(path, mode="w+", dtype=np.float64, shape=shape)
    array.flush()
    del array


def _initialize_or_resume_manifest(
    protocol: dict[str, object], shape: tuple[int, int, int]
) -> tuple[Path, dict[str, object]]:
    configuration = protocol["configuration"]
    work_directory = ROOT / configuration["work_directory"]
    manifest_path = ROOT / configuration["atomic_manifest"]
    work_directory.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["protocol_sha256"] != EXPECTED_PROTOCOL_SHA256:
            raise RuntimeError("Phase 7B6i work manifest belongs to another protocol")
        if manifest["status"] not in ("running", "converged"):
            raise RuntimeError("Phase 7B6i work manifest has an invalid status")
        return manifest_path, manifest

    initial = protocol["initial_checkpoint"]
    state_path = ROOT / initial["state_path"]
    residual_path = ROOT / initial["residual_path"]
    if _sha256(state_path) != initial["state_sha256"]:
        raise RuntimeError("Phase 7B6i initial state hash changed")
    if _sha256(residual_path) != initial["residual_sha256"]:
        raise RuntimeError("Phase 7B6i initial residual hash changed")
    state_paths = [work_directory / "state_a.dat", work_directory / "state_b.dat"]
    residual_paths = [
        work_directory / "residual_a.dat",
        work_directory / "residual_b.dat",
    ]
    for path in (*state_paths, *residual_paths):
        if path.exists():
            raise FileExistsError(f"untracked Phase 7B6i work state exists: {path}")
        _allocate_state(path, shape)
    manifest = {
        "phase": protocol["phase"],
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "status": "running",
        "current_global_iteration": int(initial["completed_source_maps"]),
        "current_state_path": str(state_path),
        "previous_residual_path": str(residual_path),
        "previous_accepted_weight": float(initial["previous_accepted_weight"]),
        "output_state_path": str(state_paths[0]),
        "residual_output_path": str(residual_paths[0]),
        "state_work_paths": [str(path) for path in state_paths],
        "residual_work_paths": [str(path) for path in residual_paths],
        "initial_hashes_passed": True,
        "history": [],
    }
    _write_json_atomic(manifest_path, manifest)
    return manifest_path, manifest


def _worker_rows(
    protocol: dict[str, object], global_iteration: int, manifest: dict[str, object]
) -> tuple[list[dict[str, object]], list[dict[str, object]], float]:
    configuration = protocol["configuration"]
    process_count = int(configuration["process_count"])
    reports = []
    report_paths = []
    processes = []
    started = time.perf_counter()
    worker_script = ROOT / protocol["sources"]["phase7b6h_worker"]["path"]
    worker_protocol = ROOT / protocol["sources"]["phase7b6h_protocol"]["path"]
    for worker_index in range(process_count):
        report_path = OUTPUT / (
            f"phase7b6i_iteration{global_iteration}_worker{worker_index + 1}.json"
        )
        report_paths.append(report_path)
        command = [
            sys.executable,
            str(worker_script),
            "--worker",
            "--protocol",
            str(worker_protocol),
            "--global-iteration",
            str(global_iteration),
            "--worker-index",
            str(worker_index),
            "--current-state",
            manifest["current_state_path"],
            "--output-state",
            manifest["output_state_path"],
            "--residual-output",
            manifest["residual_output_path"],
            "--previous-residual",
            manifest["previous_residual_path"],
            "--worker-report",
            str(report_path),
        ]
        processes.append(subprocess.Popen(command, cwd=ROOT))
    return_codes = [process.wait() for process in processes]
    if any(code != 0 for code in return_codes):
        raise RuntimeError(
            f"Phase 7B6i iteration {global_iteration} failed: {return_codes}"
        )
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    rows = sorted(
        [row for report in reports for row in report["rows"]],
        key=lambda row: row["core_group_start"],
    )
    return rows, reports, time.perf_counter() - started


def _coverage(rows: list[dict[str, object]], shape: tuple[int, int, int]) -> bool:
    return bool(
        rows
        and rows[0]["core_group_start"] == 0
        and rows[-1]["core_group_stop"] == shape[0]
        and all(
            first["core_group_stop"] == second["core_group_start"]
            for first, second in zip(rows[:-1], rows[1:], strict=True)
        )
    )


def _advance_manifest(
    manifest_path: Path,
    manifest: dict[str, object],
    record: dict[str, object],
) -> dict[str, object]:
    old_current = Path(manifest["current_state_path"])
    old_residual = Path(manifest["previous_residual_path"])
    new_current = Path(manifest["output_state_path"])
    new_residual = Path(manifest["residual_output_path"])
    state_work_paths = [Path(path) for path in manifest["state_work_paths"]]
    residual_work_paths = [Path(path) for path in manifest["residual_work_paths"]]
    next_state = state_work_paths[1] if new_current == state_work_paths[0] else state_work_paths[0]
    next_residual = (
        residual_work_paths[1]
        if new_residual == residual_work_paths[0]
        else residual_work_paths[0]
    )
    if old_current in state_work_paths and next_state != old_current:
        raise ArithmeticError("recoverable state alternation lost the old current file")
    if old_residual in residual_work_paths and next_residual != old_residual:
        raise ArithmeticError("recoverable residual alternation lost the old residual file")
    updated = dict(manifest)
    updated["current_global_iteration"] = record["global_iteration"]
    updated["current_state_path"] = str(new_current)
    updated["previous_residual_path"] = str(new_residual)
    updated["previous_accepted_weight"] = record["accepted_weight"]
    updated["output_state_path"] = str(next_state)
    updated["residual_output_path"] = str(next_residual)
    updated["history"] = [*manifest["history"], record]
    _write_json_atomic(manifest_path, updated)
    return updated


def run_diagnostic_worker(
    protocol_path: Path,
    worker_index: int,
    state_path: Path,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    process_count = int(configuration["process_count"])
    if worker_index < 0 or worker_index >= process_count:
        raise ValueError("diagnostic worker index left the frozen assignment")
    context = phase7b5x._context(protocol)
    shape = _shape(protocol)
    current_global = np.memmap(state_path, mode="r", dtype=np.float64, shape=shape)
    full_active_start = context["stencil"].active_outer_group_start
    full_active_stop = context["stencil"].active_outer_group_stop
    assigned = [
        (index, block)
        for index, block in enumerate(context["blocks"])
        if index % process_count == worker_index
    ]
    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    rows = []
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
        )
        mapped = result.final_lab_intensity_density
        rows.append(
            {
                "worker_index": worker_index,
                "block_index": block_index,
                "core_group_start": block.core_group_start,
                "core_group_stop": block.core_group_stop,
                "maximum_absolute_change": float(np.max(np.abs(mapped - current_core))),
                "maximum_scale": max(
                    float(np.max(np.abs(mapped))), float(np.max(np.abs(current_core)))
                ),
                "minimum_intensity": result.minimum_intensity,
                "coupled_residual": result.global_scale_normalized_coupled_residual,
                "energy_ledger_residual": result.total_relative_energy_ledger_residual,
                "block_runtime_s": time.perf_counter() - block_started,
            }
        )
        if local_index == 1 or local_index % 10 == 0 or local_index == len(assigned):
            print(
                json.dumps(
                    {
                        "final_diagnostic_worker": worker_index + 1,
                        "completed": local_index,
                        "assigned": len(assigned),
                    }
                ),
                flush=True,
            )
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "worker_index": worker_index,
        "runtime_s": time.perf_counter() - started,
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
        "rows": rows,
    }
    _write_json_atomic(report_path, report)


def _final_diagnostics(
    protocol_path: Path, protocol: dict[str, object], state_path: Path
) -> tuple[dict[str, object], list[dict[str, object]]]:
    process_count = int(protocol["configuration"]["process_count"])
    report_paths = []
    processes = []
    started = time.perf_counter()
    for worker_index in range(process_count):
        report_path = OUTPUT / f"phase7b6i_final_diagnostic_worker{worker_index + 1}.json"
        report_paths.append(report_path)
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--diagnostic-worker",
            "--protocol",
            str(protocol_path),
            "--worker-index",
            str(worker_index),
            "--state",
            str(state_path),
            "--worker-report",
            str(report_path),
        ]
        processes.append(subprocess.Popen(command, cwd=ROOT))
    return_codes = [process.wait() for process in processes]
    if any(code != 0 for code in return_codes):
        raise RuntimeError(f"Phase 7B6i final diagnostic workers failed: {return_codes}")
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    rows = sorted(
        [row for report in reports for row in report["rows"]],
        key=lambda row: row["core_group_start"],
    )
    maximum_absolute = max(row["maximum_absolute_change"] for row in rows)
    maximum_scale = max(row["maximum_scale"] for row in rows)
    diagnostics = {
        "wall_runtime_s": time.perf_counter() - started,
        "raw_fixed_point_residual": (
            maximum_absolute / maximum_scale
            if maximum_scale > 0.0
            else maximum_absolute
        ),
        "maximum_block_coupled_residual": max(
            row["coupled_residual"] for row in rows
        ),
        "maximum_block_energy_ledger_residual": max(
            row["energy_ledger_residual"] for row in rows
        ),
        "minimum_intensity": min(row["minimum_intensity"] for row in rows),
        "maximum_worker_peak_rss_mib": max(
            report["peak_process_rss_mib"] for report in reports
        ),
        "block_count": len(rows),
        "unique_full_group_coverage": _coverage(rows, _shape(protocol)),
    }
    return diagnostics, reports


def _plot(
    path: Path,
    earlier: list[dict[str, object]],
    current: list[dict[str, object]],
    diagnostics: dict[str, object],
) -> None:
    combined = [*earlier, *current]
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].semilogy(
        [row["global_iteration"] for row in combined],
        [row["raw_fixed_point_residual"] for row in combined],
        "o-",
        color="#4c78a8",
    )
    axes[0, 0].axhline(1.0e-10, color="0.25", ls="--", label="Tolerance")
    axes[0, 0].set(
        xlabel="Global source-map count",
        ylabel="Raw fixed-point residual",
        title="(a) Recoverable convergence",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].plot(
        [row["global_iteration"] for row in current],
        [row["accepted_weight"] for row in current],
        "o-",
        color="#f58518",
    )
    axes[0, 1].set(
        xlabel="Global source-map count",
        ylabel="Accepted weight",
        title="(b) Continued Aitken weights",
    )
    axes[1, 0].bar(
        [str(row["global_iteration"]) for row in current],
        [row["wall_runtime_s"] for row in current],
        color="#54a24b",
    )
    axes[1, 0].set(
        xlabel="Global source-map count",
        ylabel="Wall runtime (s)",
        title="(c) Checkpointed iteration cost",
    )
    values = [
        diagnostics["raw_fixed_point_residual"] / 1.0e-10,
        diagnostics["maximum_block_coupled_residual"] / 1.0e-8,
        diagnostics["maximum_block_energy_ledger_residual"] / 1.0e-8,
    ]
    axes[1, 1].bar(
        ["Raw residual", "Coupled", "Energy ledger"],
        values,
        color=["#4c78a8", "#e45756", "#72b7b2"],
    )
    axes[1, 1].axhline(1.0, color="0.25", ls="--", label="Gate")
    axes[1, 1].set(
        ylabel="Final diagnostic / gate",
        title="(d) Independent final audit",
    )
    axes[1, 1].legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    shape = _shape(protocol)
    manifest_path, manifest = _initialize_or_resume_manifest(protocol, shape)
    tolerance = float(configuration["fixed_point_tolerance"])
    maximum_additional = int(configuration["maximum_additional_source_maps"])
    initial_iteration = int(protocol["initial_checkpoint"]["completed_source_maps"])
    fallback_weights = tuple(float(value) for value in configuration["fallback_weights"])
    while (
        int(manifest["current_global_iteration"]) - initial_iteration
        < maximum_additional
    ):
        global_iteration = int(manifest["current_global_iteration"]) + 1
        iteration_started = time.perf_counter()
        rows, reports, worker_wall = _worker_rows(
            protocol, global_iteration, manifest
        )
        if len(rows) != int(configuration["block_count"]) or not _coverage(rows, shape):
            raise ArithmeticError("Phase 7B6i worker rows lost global frequency coverage")
        maximum_absolute = max(row["maximum_absolute_change"] for row in rows)
        maximum_scale = max(row["maximum_scale"] for row in rows)
        raw_residual = (
            maximum_absolute / maximum_scale
            if maximum_scale > 0.0
            else maximum_absolute
        )
        numerator = sum(row["aitken_numerator"] for row in rows)
        denominator = sum(row["aitken_denominator"] for row in rows)
        aitken_weight = (
            -float(manifest["previous_accepted_weight"]) * numerator / denominator
            if denominator > 0.0
            else float("nan")
        )
        if raw_residual <= tolerance:
            accepted_weight = float(configuration["converged_closure_weight"])
            accepted_method = "converged Jacobi closure"
        else:
            valid, _minimum = _trial_minimum(
                Path(manifest["current_state_path"]),
                Path(manifest["output_state_path"]),
                shape,
                aitken_weight,
                int(configuration["core_frequency_groups"]),
            )
            if valid:
                accepted_weight = float(aitken_weight)
                accepted_method = "vector Aitken"
            else:
                accepted_weight, _minimum, _checks = _fallback_weight(
                    rows, fallback_weights
                )
                accepted_method = "guarded fallback"
        minimum = _apply_weight(
            Path(manifest["current_state_path"]),
            Path(manifest["output_state_path"]),
            shape,
            accepted_weight,
            int(configuration["core_frequency_groups"]),
        )
        record = {
            "global_iteration": global_iteration,
            "block_count": len(rows),
            "unique_full_group_coverage": True,
            "raw_fixed_point_residual": raw_residual,
            "aitken_candidate_weight": aitken_weight,
            "aitken_numerator": numerator,
            "aitken_denominator": denominator,
            "accepted_method": accepted_method,
            "accepted_weight": accepted_weight,
            "minimum_intensity": minimum,
            "worker_wall_runtime_s": worker_wall,
            "wall_runtime_s": time.perf_counter() - iteration_started,
            "maximum_worker_peak_rss_mib": max(
                report["peak_process_rss_mib"] for report in reports
            ),
        }
        manifest = _advance_manifest(manifest_path, manifest, record)
        print(json.dumps(record, indent=2), flush=True)
        if raw_residual <= tolerance:
            manifest = dict(manifest)
            manifest["status"] = "converged"
            _write_json_atomic(manifest_path, manifest)
            break
    if manifest["status"] != "converged":
        raise ArithmeticError(
            "Phase 7B6i exhausted its frozen iteration budget without convergence"
        )

    current_state = Path(manifest["current_state_path"])
    current_residual = Path(manifest["previous_residual_path"])
    diagnostics, diagnostic_reports = _final_diagnostics(
        protocol_path, protocol, current_state
    )
    final_state = ROOT / configuration["final_state_path"]
    final_residual = ROOT / configuration["final_residual_path"]
    for path in (final_state, final_residual):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite final Phase 7B6i state: {path}")
    final_state_hash = _sha256(current_state)
    final_residual_hash = _sha256(current_residual)
    os.replace(current_state, final_state)
    os.replace(current_residual, final_residual)
    removed = []
    for raw_path in (*manifest["state_work_paths"], *manifest["residual_work_paths"]):
        path = Path(raw_path)
        if path.exists():
            path.unlink()
            removed.append(str(path))
    unused_removed = all(
        not Path(path).exists()
        for path in (*manifest["state_work_paths"], *manifest["residual_work_paths"])
    )
    manifest = dict(manifest)
    manifest.update(
        {
            "status": "complete",
            "current_state_path": str(final_state),
            "previous_residual_path": str(final_residual),
            "final_state_sha256": final_state_hash,
            "final_residual_sha256": final_residual_hash,
            "unused_work_files_removed": removed,
        }
    )
    _write_json_atomic(manifest_path, manifest)

    current_history = manifest["history"]
    finite_values = [
        value
        for row in current_history
        for value in (
            row["raw_fixed_point_residual"],
            row["accepted_weight"],
            row["aitken_numerator"],
            row["aitken_denominator"],
        )
    ]
    decision = {
        "frozen_protocol_hash_passed": True,
        "source_and_initial_checkpoint_hashes_passed": manifest[
            "initial_hashes_passed"
        ],
        "converged_within_iteration_budget": bool(
            len(current_history) <= maximum_additional
            and current_history[-1]["raw_fixed_point_residual"]
            <= gates["converged_raw_fixed_point_residual_at_most"]
        ),
        "all_iterations_nonnegative_finite_and_complete": bool(
            all(row["block_count"] == gates["each_iteration_block_count_exactly"] for row in current_history)
            and all(row["unique_full_group_coverage"] for row in current_history)
            and all(row["minimum_intensity"] >= gates["minimum_intensity_at_least"] for row in current_history)
            and all(np.isfinite(value) for value in finite_values)
        ),
        "iteration_resource_and_runtime_gates_passed": all(
            row["maximum_worker_peak_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and row["wall_runtime_s"]
            < gates["each_iteration_wall_time_strictly_below_s"]
            for row in current_history
        ),
        "final_diagnostic_gates_passed": bool(
            diagnostics["raw_fixed_point_residual"]
            <= gates["final_audit_raw_fixed_point_residual_at_most"]
            and diagnostics["maximum_block_coupled_residual"]
            < gates["maximum_block_coupled_residual_strictly_below"]
            and diagnostics["maximum_block_energy_ledger_residual"]
            < gates["maximum_block_energy_ledger_residual_strictly_below"]
            and diagnostics["minimum_intensity"]
            >= gates["minimum_intensity_at_least"]
            and diagnostics["unique_full_group_coverage"]
        ),
        "final_checkpoint_integrity_passed": bool(
            final_state.stat().st_size
            == gates["each_final_checkpoint_size_bytes_exactly"]
            and final_residual.stat().st_size
            == gates["each_final_checkpoint_size_bytes_exactly"]
            and unused_removed
        ),
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b6i_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "source_and_initial_checkpoint_hashes_passed",
            "converged_within_iteration_budget",
            "all_iterations_nonnegative_finite_and_complete",
            "iteration_resource_and_runtime_gates_passed",
            "final_diagnostic_gates_passed",
            "final_checkpoint_integrity_passed",
        )
    )
    decision["full_column_radiation_fixed_point_accepted"] = bool(
        decision["phase7b6i_gate_passed"]
    )
    decision["matter_feedback_authorized"] = bool(decision["phase7b6i_gate_passed"])
    previous_history = json.loads(
        (ROOT / protocol["sources"]["phase7b6h_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )["history"]
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "initial_global_iteration": initial_iteration,
        "final_global_iteration": manifest["current_global_iteration"],
        "continuation_history": current_history,
        "final_diagnostics": diagnostics,
        "diagnostic_worker_reports": diagnostic_reports,
        "final_state_path": str(final_state.relative_to(ROOT)),
        "final_state_sha256": final_state_hash,
        "final_residual_path": str(final_residual.relative_to(ROOT)),
        "final_residual_sha256": final_residual_hash,
        "manifest_path": str(manifest_path.relative_to(ROOT)),
        "unused_work_files_removed": removed,
        "decision": decision,
        "figures": ["phase7b6i_converged_full_frequency.png"],
    }
    _write_json_atomic(
        OUTPUT / "phase7b6i_converged_full_frequency_summary.json", summary
    )
    _plot(
        OUTPUT / "phase7b6i_converged_full_frequency.png",
        previous_history,
        current_history,
        diagnostics,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6i_preregistered_converged_full_frequency.json",
    )
    parser.add_argument("--diagnostic-worker", action="store_true")
    parser.add_argument("--worker-index", type=int)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.diagnostic_worker:
        if args.worker_index is None or args.state is None or args.worker_report is None:
            raise ValueError("diagnostic worker requires index, state and report")
        run_diagnostic_worker(
            args.protocol, args.worker_index, args.state, args.worker_report
        )
        return
    summary = run(args.protocol)
    print(json.dumps(summary["decision"], indent=2))


if __name__ == "__main__":
    main()
