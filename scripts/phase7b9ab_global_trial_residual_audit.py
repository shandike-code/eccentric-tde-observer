"""Phase 7B9ab：候选自身邻块下的全局原始算子与边界审计。"""

from __future__ import annotations

import argparse
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
WORK = OUTPUT / "checkpoints/phase7b9ab_global_trial"
EXPECTED_PROTOCOL_SHA256 = (
    "fe5107a17256e20a2e321e325edc53347d64046d897c40721f7251f69db5b999"
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
        raise RuntimeError("frozen Phase 7B9ab protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9ab source changed: {source['path']}"
                )
    return protocol


def _assemble_trial(
    protocol: dict[str, object], shape: tuple[int, int, int]
) -> tuple[Path, str]:
    configuration = protocol["configuration"]
    source = ROOT / protocol["sources"]["phase7b9t_partial_candidate_state"]["path"]
    trial = ROOT / configuration["trial_state_path"]
    trial.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(trial.parent).free <= int(
        configuration["minimum_free_bytes_before_trial_copy"]
    ):
        raise OSError("insufficient disk space for Phase 7B9ab trial state")
    if trial.exists():
        trial.unlink()
    shutil.copyfile(source, trial)
    if base._sha256(trial) != protocol["sources"][
        "phase7b9t_partial_candidate_state"
    ]["sha256"]:
        raise RuntimeError("Phase 7B9ab trial base copy changed bytes")
    trial_map = np.memmap(trial, mode="r+", dtype=np.float64, shape=shape)
    repair = json.loads(
        (ROOT / protocol["sources"]["phase7b9aa_repair_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    for row in repair["repair_reports"]:
        start = int(row["core_group_start"])
        stop = int(row["core_group_stop"])
        candidate = np.memmap(
            ROOT / row["candidate_path"],
            mode="r",
            dtype=np.float64,
            shape=(stop - start, shape[1], shape[2]),
        )
        trial_map[start:stop] = candidate
        trial_map.flush()
        del candidate
        if (
            base.phase7b9d._block_sha256(trial, shape, start, stop)
            != row["candidate_sha256"]
        ):
            raise RuntimeError(f"Phase 7B9ab trial block {row['block_index']} changed")
    del trial_map
    return trial, base._sha256(trial)


def _run_worker(
    protocol_path: Path,
    block_index: int,
    trial_path: Path,
    trial_sha256: str,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    configuration = protocol["configuration"]
    finite_protocol = base.phase7b9i._load_protocol(
        ROOT / protocol["sources"]["finite_trial_protocol"]["path"],
        validate_sources=False,
    )
    base.phase7b9d._configure_worker(finite_protocol, trial_path)
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
    trial_global = np.memmap(trial_path, mode="r", dtype=np.float64, shape=shape)
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
        ] = trial_global[source_slice]
    core = slice(block.core_group_start, block.core_group_stop)
    initial = np.array(trial_global[core], copy=True)
    del trial_global
    mu = np.asarray(context["mu"])
    weight = np.asarray(context["weight"])
    global_edge = np.asarray(context["stencil"].active_lab_edge_hz)
    frequency_width = np.diff(global_edge)[core]
    baseline_rss = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
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
        source_iteration_initial_guess=initial,
        diagnostic_fixed_iteration_count=1,
        spatial_scheme=configuration["spatial_scheme"],
        source_map_only=True,
    )
    mapped = np.array(result.final_lab_intensity_density, copy=True)
    del result
    change = float(np.max(np.abs(mapped - initial)))
    scale = max(float(np.max(np.abs(initial))), float(np.max(np.abs(mapped))))
    current_flux = base._block_flux(initial, mu, weight, frequency_width)
    mapped_flux = base._block_flux(mapped, mu, weight, frequency_width)
    boundary_numerator = float(np.sum(np.abs(mapped_flux - current_flux)))
    current_boundary_scale = float(np.sum(np.abs(current_flux)))
    mapped_boundary_scale = float(np.sum(np.abs(mapped_flux)))
    current_bolometric = float(np.sum(current_flux))
    mapped_bolometric = float(np.sum(mapped_flux))
    peak_rss = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "trial_state_sha256": trial_sha256,
        "block_index": block_index,
        "core_group_start": int(block.core_group_start),
        "core_group_stop": int(block.core_group_stop),
        "minimum_energy_ev": float(
            global_edge[block.core_group_start] * 4.135667696e-15
        ),
        "maximum_energy_ev": float(
            global_edge[block.core_group_stop] * 4.135667696e-15
        ),
        "maximum_absolute_original_operator_change": change,
        "maximum_original_operator_scale": scale,
        "block_relative_original_operator_residual": change / scale if scale > 0.0 else change,
        "boundary_spectrum_l1_numerator": boundary_numerator,
        "current_boundary_absolute_scale": current_boundary_scale,
        "mapped_boundary_absolute_scale": mapped_boundary_scale,
        "current_boundary_bolometric": current_bolometric,
        "mapped_boundary_bolometric": mapped_bolometric,
        "minimum_trial_intensity": float(np.min(initial)),
        "minimum_mapped_intensity": float(np.min(mapped)),
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
        "wall_runtime_s": time.perf_counter() - started,
    }
    _write_json_atomic(report_path, report)


def _valid_report(
    path: Path, block_index: int, trial_sha256: str
) -> bool:
    if not path.exists():
        return False
    row = json.loads(path.read_text(encoding="utf-8"))
    return bool(
        row.get("protocol_sha256") == EXPECTED_PROTOCOL_SHA256
        and row.get("trial_state_sha256") == trial_sha256
        and int(row.get("block_index", -1)) == block_index
    )


def _plot(
    path: Path,
    reports: list[dict[str, object]],
    gates: dict[str, object],
    global_residual: float,
    boundary_l1: float,
    bolometric: float,
) -> None:
    block = np.asarray([row["block_index"] for row in reports])
    local = np.asarray([row["block_relative_original_operator_residual"] for row in reports])
    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.5), constrained_layout=True)
    axes[0].semilogy(block, local, "o-", ms=3)
    axes[0].axhline(
        gates["global_original_operator_residual_below"],
        color="0.25",
        ls="--",
        label="Global target",
    )
    axes[0].set(
        xlabel="Natural frequency block",
        ylabel="Block-relative original residual",
        title="(a) Trial-state residual distribution",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].axis("off")
    axes[1].text(
        0.04,
        0.95,
        "(b) Global original-operator audit\n\n"
        f"Global residual = {global_residual:.3e}\n"
        f"Boundary spectral L1 = {boundary_l1:.3e}\n"
        f"Boundary bolometric = {bolometric:.3e}\n"
        f"Maximum worker RSS = "
        f"{max(float(row['peak_process_rss_mib']) for row in reports):.1f} MiB",
        transform=axes[1].transAxes,
        va="top",
        fontsize=10.5,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    shape = (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )
    trial_path, trial_sha = _assemble_trial(protocol, shape)
    report_directory = WORK / "reports"
    report_directory.mkdir(parents=True, exist_ok=True)
    reports_by_block: dict[int, dict[str, object]] = {}
    pending = []
    for block_index in range(int(configuration["natural_frequency_block_count"])):
        report_path = report_directory / f"phase7b9ab_block{block_index:02d}.json"
        if _valid_report(report_path, block_index, trial_sha):
            reports_by_block[block_index] = json.loads(
                report_path.read_text(encoding="utf-8")
            )
        else:
            pending.append((block_index, report_path))
    concurrency = int(configuration["maximum_concurrent_processes"])
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        processes = []
        for block_index, report_path in batch:
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
                        "--trial-state",
                        str(trial_path),
                        "--trial-sha256",
                        trial_sha,
                        "--worker-report",
                        str(report_path),
                    ],
                    cwd=ROOT,
                )
            )
        return_codes = [process.wait() for process in processes]
        if any(code != 0 for code in return_codes):
            raise RuntimeError(f"Phase 7B9ab worker batch failed: {return_codes}")
        for block_index, report_path in batch:
            if not _valid_report(report_path, block_index, trial_sha):
                raise RuntimeError("Phase 7B9ab worker report validation failed")
            reports_by_block[block_index] = json.loads(
                report_path.read_text(encoding="utf-8")
            )
        print(
            json.dumps(
                {
                    "completed_blocks": len(reports_by_block),
                    "total_blocks": configuration["natural_frequency_block_count"],
                    "latest_blocks": [index for index, _ in batch],
                }
            ),
            flush=True,
        )
    reports = [reports_by_block[index] for index in range(76)]
    ownership = np.zeros(shape[0], dtype=np.int64)
    for row in reports:
        ownership[int(row["core_group_start"]) : int(row["core_group_stop"])] += 1
    maximum_change = max(
        float(row["maximum_absolute_original_operator_change"]) for row in reports
    )
    maximum_scale = max(float(row["maximum_original_operator_scale"]) for row in reports)
    global_residual = maximum_change / maximum_scale if maximum_scale > 0.0 else maximum_change
    boundary_numerator = sum(float(row["boundary_spectrum_l1_numerator"]) for row in reports)
    current_boundary_scale = sum(float(row["current_boundary_absolute_scale"]) for row in reports)
    mapped_boundary_scale = sum(float(row["mapped_boundary_absolute_scale"]) for row in reports)
    boundary_l1 = boundary_numerator / max(current_boundary_scale, mapped_boundary_scale)
    current_bolometric = sum(float(row["current_boundary_bolometric"]) for row in reports)
    mapped_bolometric = sum(float(row["mapped_boundary_bolometric"]) for row in reports)
    bolometric = abs(mapped_bolometric - current_bolometric) / max(
        abs(current_bolometric), abs(mapped_bolometric)
    )
    block67 = reports[67]
    block67_boundary_fraction = (
        float(block67["boundary_spectrum_l1_numerator"]) / boundary_numerator
        if boundary_numerator > 0.0
        else 0.0
    )
    gates = protocol["gates"]
    checks = {
        "frequency_ownership_pass": len(reports) == gates["block_count_exactly"]
        and int(np.sum(ownership)) == gates["owned_frequency_group_count_exactly"]
        and bool(np.all(ownership == 1)),
        "trial_and_mapped_states_are_nonnegative": all(
            row["minimum_trial_intensity"] >= gates["minimum_intensity_at_least"]
            and row["minimum_mapped_intensity"] >= gates["minimum_intensity_at_least"]
            for row in reports
        ),
        "global_original_operator_residual_pass": global_residual
        < gates["global_original_operator_residual_below"],
        "global_boundary_spectrum_pass": boundary_l1
        < gates["global_boundary_spectrum_l1_below"],
        "global_boundary_bolometric_pass": bolometric
        < gates["global_boundary_bolometric_fraction_below"],
        "worker_resources_pass": all(
            row["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and row["wall_runtime_s"]
            < gates["each_worker_wall_time_strictly_below_s"]
            for row in reports
        ),
    }
    passed = all(checks.values())
    figure = OUTPUT / "phase7b9ab_global_trial_residual_audit.png"
    _plot(figure, reports, gates, global_residual, boundary_l1, bolometric)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "trial_state_path": str(trial_path.resolve().relative_to(ROOT)),
        "trial_state_sha256": trial_sha,
        "global_original_operator_residual": global_residual,
        "global_boundary_spectrum_l1": boundary_l1,
        "global_boundary_bolometric_fraction": bolometric,
        "block67_fraction_of_global_boundary_l1_numerator": block67_boundary_fraction,
        "maximum_block_relative_original_operator_residual": max(
            row["block_relative_original_operator_residual"] for row in reports
        ),
        "maximum_block_relative_residual_index": int(
            max(reports, key=lambda row: row["block_relative_original_operator_residual"])[
                "block_index"
            ]
        ),
        "gate_checks": checks,
        "decision": {
            "global_trial_residual_audit_passed": passed,
            "trial_promoted_to_committed_candidate": passed,
            "local_block67_boundary_failure_overridden": passed,
            "confirmation_source_map_authorized": passed,
            "material_feedback_authorized": False,
        },
        "reports": reports,
        "figures": [figure.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9ab_global_trial_residual_audit_summary.json", summary
    )
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9ab_preregistered_global_trial_residual_audit.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--trial-state", type=Path)
    parser.add_argument("--trial-sha256")
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if (
            args.block_index is None
            or args.trial_state is None
            or args.trial_sha256 is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires block, trial state/hash and report")
        _run_worker(
            args.protocol,
            args.block_index,
            args.trial_state,
            args.trial_sha256,
            args.worker_report,
        )
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
