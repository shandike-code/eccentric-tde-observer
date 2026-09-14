"""Phase 7B9aa：用混合正性求解器非破坏地修复全频率候选。"""

from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from scripts import phase7b9r_full_source_krylov_line_search as previous
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9r_full_source_krylov_line_search as previous  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
WORK = OUTPUT / "checkpoints/phase7b9aa_hybrid_repair"
EXPECTED_PROTOCOL_SHA256 = (
    "f96fb03f0bfbd31fefbe658cfde0796b7adc9bea4f46fdcf9e81b4d18a96e5de"
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
        raise RuntimeError("frozen Phase 7B9aa protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9aa source changed: {source['path']}"
                )
    return protocol


def _run_worker(
    protocol_path: Path,
    block_index: int,
    report_path: Path,
    candidate_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    configuration = protocol["configuration"]
    repair = {
        int(row["block_index"]): row for row in configuration["repair_blocks"]
    }
    if block_index not in repair:
        raise ValueError("Phase 7B9aa worker block is not preregistered")
    rule = repair[block_index]
    guard_path = ROOT / protocol["sources"]["current_map6_state"]["path"]
    seed_path = ROOT / protocol["sources"][rule["seed_source_key"]]["path"]
    finite_protocol = base.phase7b9i._load_protocol(
        ROOT / protocol["sources"]["finite_trial_protocol"]["path"],
        validate_sources=False,
    )
    base.phase7b9d._configure_worker(finite_protocol, guard_path)
    template_protocol = base.phase7b7i._load_protocol(
        protocol_path, validate_sources=False
    )
    context = base.phase7b7i.phase7b7e.phase7b5x._context(template_protocol)
    block = context["blocks"][block_index]
    material = base.phase7b7i._second_full_material(template_protocol)
    fields = base.phase7b7i.phase7b7e._local_fields(context, block, material)
    shape = (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )
    guard_global = np.memmap(guard_path, mode="r", dtype=np.float64, shape=shape)
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
        ] = guard_global[source_slice]
    core = slice(block.core_group_start, block.core_group_stop)
    seed_global = np.memmap(seed_path, mode="r", dtype=np.float64, shape=shape)
    current = np.array(seed_global[core], copy=True)
    del guard_global, seed_global
    mu = np.asarray(context["mu"])
    weight = np.asarray(context["weight"])
    global_edge = np.asarray(context["stencil"].active_lab_edge_hz)
    frequency_width = np.diff(global_edge)[core]

    def source_map(guess: np.ndarray) -> np.ndarray:
        result = base.phase7b7i.phase7b7e.solve_mixed_frame_ale_group_step(
            block.local_stencil,
            fields["old_edge"],
            fields["new_edge"],
            mu,
            weight,
            fields["initial"],
            fields["outer"],
            fields["true_absorption"],
            fields["thermal_emissivity"],
            fields["scattering"],
            context["beta"],
            context["duration_s"],
            propagation_speed_cm_s=base.phase7b7i.phase7b7e.LIGHT_SPEED_CM_S,
            source_iteration_initial_guess=guess,
            diagnostic_fixed_iteration_count=1,
            spatial_scheme=configuration["spatial_scheme"],
            source_map_only=True,
        )
        mapped = np.array(result.final_lab_intensity_density, copy=True)
        del result
        return mapped

    baseline_rss = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    minimum_intensity = float(np.min(current))
    residual_history: list[float] = []
    boundary_history: list[float] = []
    update_count = int(rule["positive_picard_update_count"])
    for update in range(update_count + 1):
        mapped = source_map(current)
        if not np.all(np.isfinite(mapped)) or np.any(mapped < 0.0):
            raise ArithmeticError("hybrid repair Picard map left its physical domain")
        residual_history.append(base._relative_update(current, mapped))
        flux = base._block_flux(current, mu, weight, frequency_width)
        mapped_flux = base._block_flux(mapped, mu, weight, frequency_width)
        boundary_history.append(base._spectral_l1(flux, mapped_flux))
        minimum_intensity = min(minimum_intensity, float(np.min(mapped)))
        if update < update_count:
            current = mapped
        else:
            del mapped
        gc.collect()
    raw_residual = (
        float(rule["map6_raw_original_operator_residual"])
        if rule["map6_raw_original_operator_residual"] is not None
        else float(residual_history[0])
    )
    raw_boundary = (
        float(rule["map6_raw_boundary_spectrum_l1"])
        if rule["map6_raw_boundary_spectrum_l1"] is not None
        else float(boundary_history[0])
    )
    expected_seed = rule["seed_original_operator_residual"]
    seed_consistency = (
        abs(float(residual_history[0]) - float(expected_seed))
        / max(abs(float(residual_history[0])), abs(float(expected_seed)))
        if expected_seed is not None
        else 0.0
    )
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate = np.memmap(
        candidate_path,
        mode="w+",
        dtype=np.float64,
        shape=current.shape,
    )
    candidate[:] = current
    candidate.flush()
    del candidate
    candidate_sha = base._sha256(candidate_path)
    peak_rss = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    final_residual = float(residual_history[-1])
    final_boundary = float(boundary_history[-1])
    report = {
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "block_index": block_index,
        "role": rule["role"],
        "core_group_start": int(block.core_group_start),
        "core_group_stop": int(block.core_group_stop),
        "minimum_energy_ev": float(
            global_edge[block.core_group_start] * 4.135667696e-15
        ),
        "maximum_energy_ev": float(
            global_edge[block.core_group_stop] * 4.135667696e-15
        ),
        "seed_source_key": rule["seed_source_key"],
        "positive_picard_update_count": update_count,
        "seed_restart_relative_difference": seed_consistency,
        "map6_raw_original_operator_residual": raw_residual,
        "final_original_operator_residual": final_residual,
        "final_to_map6_raw_residual_ratio": (
            final_residual / raw_residual
            if raw_residual > 0.0
            else (0.0 if final_residual == 0.0 else float("inf"))
        ),
        "map6_raw_boundary_spectrum_l1": raw_boundary,
        "final_boundary_spectrum_l1": final_boundary,
        "final_to_map6_raw_boundary_ratio": (
            final_boundary / raw_boundary
            if raw_boundary > 0.0
            else (0.0 if final_boundary == 0.0 else float("inf"))
        ),
        "minimum_history_intensity": minimum_intensity,
        "minimum_candidate_intensity": float(np.min(current)),
        "candidate_path": str(candidate_path.resolve().relative_to(ROOT)),
        "candidate_sha256": candidate_sha,
        "candidate_size_bytes": candidate_path.stat().st_size,
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
        "wall_runtime_s": time.perf_counter() - started,
        "residual_history": residual_history,
        "boundary_history": boundary_history,
    }
    _write_json_atomic(report_path, report)


def _valid_existing_report(
    report_path: Path, candidate_path: Path, block_index: int
) -> bool:
    if not report_path.exists() or not candidate_path.exists():
        return False
    row = json.loads(report_path.read_text(encoding="utf-8"))
    return bool(
        row.get("protocol_sha256") == EXPECTED_PROTOCOL_SHA256
        and int(row.get("block_index", -1)) == block_index
        and candidate_path.stat().st_size == int(row["candidate_size_bytes"])
        and base._sha256(candidate_path) == row["candidate_sha256"]
    )


def _plot(
    path: Path,
    reports: list[dict[str, object]],
    gates: dict[str, object],
    *,
    passed: bool,
) -> None:
    block = np.asarray([row["block_index"] for row in reports])
    ratio = np.asarray([row["final_to_map6_raw_residual_ratio"] for row in reports])
    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.5), constrained_layout=True)
    axes[0].bar(block, ratio, color="tab:blue")
    axes[0].axhline(
        gates["each_final_to_map6_raw_residual_ratio_below"],
        color="0.25",
        ls="--",
        label="Residual gate",
    )
    axes[0].set(
        xlabel="Repaired natural frequency block",
        ylabel="Candidate / map-6 raw residual",
        title="(a) Hybrid repair gate",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].axis("off")
    axes[1].text(
        0.04,
        0.95,
        "(b) Non-destructive transaction\n\n"
        f"Repaired blocks = {len(reports)}\n"
        f"Worst residual ratio = {float(np.max(ratio)):.4f}\n"
        f"Minimum intensity = "
        f"{min(float(row['minimum_candidate_intensity']) for row in reports):.3e}\n"
        f"Peak worker RSS = "
        f"{max(float(row['peak_process_rss_mib']) for row in reports):.1f} MiB\n\n"
        f"Repair passed: {passed}\n"
        "Source state preserved: true",
        transform=axes[1].transAxes,
        va="top",
        fontsize=10.5,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    final_summary = OUTPUT / "phase7b9aa_hybrid_candidate_repair_summary.json"
    if final_summary.exists():
        summary = json.loads(final_summary.read_text(encoding="utf-8"))
        output = ROOT / summary["repaired_candidate_state_path"]
        if output.exists() and base._sha256(output) == summary["repaired_candidate_state_sha256"]:
            return summary
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    WORK.mkdir(parents=True, exist_ok=True)
    report_directory = WORK / "reports"
    candidate_directory = WORK / "candidates"
    report_directory.mkdir(exist_ok=True)
    candidate_directory.mkdir(exist_ok=True)
    pending: list[tuple[int, Path, Path]] = []
    reports_by_block: dict[int, dict[str, object]] = {}
    for rule in configuration["repair_blocks"]:
        block_index = int(rule["block_index"])
        report_path = report_directory / f"phase7b9aa_block{block_index:02d}.json"
        candidate_path = candidate_directory / f"phase7b9aa_block{block_index:02d}.dat"
        if _valid_existing_report(report_path, candidate_path, block_index):
            reports_by_block[block_index] = json.loads(
                report_path.read_text(encoding="utf-8")
            )
        else:
            pending.append((block_index, report_path, candidate_path))
    concurrency = int(configuration["maximum_concurrent_processes"])
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        processes = []
        for block_index, report_path, candidate_path in batch:
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--worker",
                        "--protocol",
                        str(protocol_path),
                        "--block-index",
                        str(block_index),
                        "--worker-report",
                        str(report_path),
                        "--candidate-output",
                        str(candidate_path),
                    ],
                    cwd=ROOT,
                )
            )
        return_codes = [process.wait() for process in processes]
        if any(code != 0 for code in return_codes):
            raise RuntimeError(f"Phase 7B9aa worker batch failed: {return_codes}")
        for block_index, report_path, candidate_path in batch:
            if not _valid_existing_report(report_path, candidate_path, block_index):
                raise RuntimeError("Phase 7B9aa worker artifact validation failed")
            reports_by_block[block_index] = json.loads(
                report_path.read_text(encoding="utf-8")
            )
            print(
                json.dumps(
                    {
                        "completed_repair_blocks": len(reports_by_block),
                        "total_repair_blocks": len(configuration["repair_blocks"]),
                        "latest_block": block_index,
                        "latest_residual_ratio": reports_by_block[block_index][
                            "final_to_map6_raw_residual_ratio"
                        ],
                    }
                ),
                flush=True,
            )
    reports = [
        reports_by_block[int(rule["block_index"])]
        for rule in configuration["repair_blocks"]
    ]
    gates = protocol["gates"]
    checks = {
        "repair_block_count_pass": len(reports)
        == gates["repair_block_count_exactly"],
        "seed_restarts_pass": all(
            row["seed_restart_relative_difference"]
            < gates["each_seed_restart_relative_difference_below"]
            for row in reports
        ),
        "positive_histories_and_candidates_pass": all(
            row["minimum_history_intensity"]
            >= gates["minimum_history_intensity_at_least"]
            and row["minimum_candidate_intensity"]
            >= gates["minimum_candidate_intensity_at_least"]
            for row in reports
        ),
        "fresh_original_operator_residuals_pass": all(
            row["final_to_map6_raw_residual_ratio"]
            < gates["each_final_to_map6_raw_residual_ratio_below"]
            for row in reports
        ),
        "boundaries_do_not_worsen": all(
            row["final_to_map6_raw_boundary_ratio"]
            <= gates["each_final_to_map6_raw_boundary_ratio_at_most"]
            for row in reports
        ),
        "worker_resources_pass": all(
            row["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and row["wall_runtime_s"]
            < gates["each_worker_wall_time_strictly_below_s"]
            for row in reports
        ),
    }
    passed = all(checks.values())
    output_path = ROOT / configuration["repaired_candidate_state_path"]
    output_sha: str | None = None
    applied: list[dict[str, object]] = []
    if passed:
        source = ROOT / protocol["sources"]["phase7b9t_partial_candidate_state"]["path"]
        if shutil.disk_usage(output_path.parent).free <= int(
            configuration["minimum_free_bytes_before_full_copy"]
        ):
            raise OSError("insufficient disk space for non-destructive repaired state")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()
        shutil.copyfile(source, output_path)
        if base._sha256(output_path) != protocol["sources"][
            "phase7b9t_partial_candidate_state"
        ]["sha256"]:
            raise RuntimeError("Phase 7B9aa full-state copy changed bytes")
        shape = (
            int(configuration["physical_frequency_groups"]),
            int(configuration["angular_direction_count"]),
            int(configuration["radiation_depth_cell_count"]),
        )
        output = np.memmap(output_path, mode="r+", dtype=np.float64, shape=shape)
        for row in reports:
            start = int(row["core_group_start"])
            stop = int(row["core_group_stop"])
            candidate = np.memmap(
                ROOT / row["candidate_path"],
                mode="r",
                dtype=np.float64,
                shape=(stop - start, shape[1], shape[2]),
            )
            output[start:stop] = candidate
            output.flush()
            del candidate
            digest = base.phase7b9d._block_sha256(output_path, shape, start, stop)
            if digest != row["candidate_sha256"]:
                raise RuntimeError(f"Phase 7B9aa applied block {row['block_index']} changed")
            applied.append(
                {
                    "block_index": row["block_index"],
                    "core_group_start": start,
                    "core_group_stop": stop,
                    "sha256": digest,
                }
            )
        del output
        output_sha = base._sha256(output_path)
    figure = OUTPUT / "phase7b9aa_hybrid_candidate_repair.png"
    _plot(figure, reports, gates, passed=passed)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "source_partial_candidate_state_path": protocol["sources"][
            "phase7b9t_partial_candidate_state"
        ]["path"],
        "source_partial_candidate_state_sha256": protocol["sources"][
            "phase7b9t_partial_candidate_state"
        ]["sha256"],
        "repaired_candidate_state_path": (
            configuration["repaired_candidate_state_path"] if passed else None
        ),
        "repaired_candidate_state_sha256": output_sha,
        "repair_reports": reports,
        "applied_blocks": applied,
        "gate_checks": checks,
        "decision": {
            "hybrid_candidate_repair_passed": passed,
            "non_destructive_repaired_state_committed": passed,
            "source_partial_candidate_preserved": True,
            "global_candidate_residual_authorized": passed,
            "material_feedback_authorized": False,
        },
        "figures": [figure.name],
    }
    _write_json_atomic(final_summary, summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9aa_preregistered_hybrid_candidate_repair.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--candidate-output", type=Path)
    args = parser.parse_args()
    if args.worker:
        if (
            args.block_index is None
            or args.worker_report is None
            or args.candidate_output is None
        ):
            raise ValueError("worker mode requires block, report and candidate output")
        _run_worker(
            args.protocol,
            args.block_index,
            args.worker_report,
            args.candidate_output,
        )
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
