"""Phase 7B9l：测量代表频率块的块内多次散射收缩与成本。"""

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
    from scripts import phase7b7i_second_radiation_map as phase7b7i
    from scripts import phase7b9d_inner_converged_base_radiation as phase7b9d
    from scripts import phase7b9i_finite_trial_radiation as phase7b9i
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b7i_second_radiation_map as phase7b7i  # type: ignore[no-redef]
    import phase7b9d_inner_converged_base_radiation as phase7b9d  # type: ignore[no-redef]
    import phase7b9i_finite_trial_radiation as phase7b9i  # type: ignore[no-redef]
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "653e3ca389836e3017b1284f36ea61cc6a6b5c73861ee424f854c88aa6bbe063"
)
MIB = 1024**2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if _sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9l protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or _sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9l source changed: {source['path']}"
                )
    return protocol


def _block_flux(
    intensity: np.ndarray,
    mu: np.ndarray,
    weight: np.ndarray,
    frequency_width: np.ndarray,
) -> np.ndarray:
    left = mu < 0.0
    right = mu > 0.0
    flux = 2.0 * np.pi * (
        np.einsum(
            "m,fm->f",
            weight[left] * np.abs(mu[left]),
            intensity[:, left, 0],
        )
        + np.einsum(
            "m,fm->f",
            weight[right] * mu[right],
            intensity[:, right, -1],
        )
    )
    return frequency_width * flux


def _run_worker(protocol_path: Path, block_index: int, report_path: Path) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    selected = {
        int(row["block_index"]): row["role"]
        for row in protocol["configuration"]["selected_blocks"]
    }
    if block_index not in selected:
        raise ValueError("Phase 7B9l worker block is not preregistered")
    current_path = ROOT / protocol["sources"]["current_map6_state"]["path"]
    finite_protocol_path = (
        ROOT / protocol["sources"]["finite_trial_protocol"]["path"]
    )
    finite_protocol = phase7b9i._load_protocol(
        finite_protocol_path, validate_sources=False
    )
    phase7b9d._configure_worker(finite_protocol, current_path)
    template = phase7b7i._load_protocol(protocol_path, validate_sources=False)
    context = phase7b7i.phase7b7e.phase7b5x._context(template)
    if int(context["phase"]) != int(protocol["configuration"]["phase_index"]):
        raise RuntimeError("Phase 7B9l selected phase changed")
    block = context["blocks"][block_index]
    updated = phase7b7i._second_full_material(template)
    fields = phase7b7i.phase7b7e._local_fields(context, block, updated)
    shape = (
        int(protocol["configuration"]["physical_frequency_groups"]),
        int(protocol["configuration"]["angular_direction_count"]),
        int(protocol["configuration"]["radiation_depth_cell_count"]),
    )
    current_global = np.memmap(
        current_path, mode="r", dtype=np.float64, shape=shape
    )
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
    del current_global
    mu = np.asarray(context["mu"])
    weight = np.asarray(context["weight"])
    global_edge = np.asarray(context["stencil"].active_lab_edge_hz)
    frequency_width = np.diff(global_edge)[core]
    previous = np.empty_like(current_core)
    previous_flux = np.empty(current_core.shape[0], dtype=np.float64)
    rows: list[dict[str, object]] = []
    started = time.perf_counter()

    def observe(iteration: int, value: np.ndarray) -> None:
        nonlocal previous_flux
        flux = _block_flux(value, mu, weight, frequency_width)
        if iteration == 0:
            previous[...] = value
            previous_flux[...] = flux
            return
        difference = np.asarray(value) - previous
        scale = max(float(np.max(np.abs(value))), float(np.max(np.abs(previous))))
        update = float(np.max(np.abs(difference)))
        flux_scale = max(
            float(np.sum(np.abs(flux))), float(np.sum(np.abs(previous_flux)))
        )
        spectrum_change = float(np.sum(np.abs(flux - previous_flux)))
        rows.append(
            {
                "iteration": iteration,
                "local_update_residual": update / scale if scale > 0.0 else update,
                "boundary_spectrum_l1": (
                    spectrum_change / flux_scale
                    if flux_scale > 0.0
                    else spectrum_change
                ),
                "minimum_intensity": float(np.min(value)),
                "elapsed_runtime_s": time.perf_counter() - started,
            }
        )
        previous[...] = value
        previous_flux[...] = flux

    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    result = phase7b7i.phase7b7e.solve_mixed_frame_ale_group_step(
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
        propagation_speed_cm_s=phase7b7i.phase7b7e.LIGHT_SPEED_CM_S,
        source_iteration_initial_guess=current_core,
        diagnostic_fixed_iteration_count=int(
            protocol["configuration"]["block_internal_source_updates_exactly"]
        ),
        spatial_scheme=protocol["configuration"]["spatial_scheme"],
        source_map_only=True,
        iteration_observer=observe,
    )
    wall_runtime = time.perf_counter() - started
    final = np.asarray(result.final_lab_intensity_density)
    if not np.all(np.isfinite(final)) or np.any(final < 0.0):
        raise ArithmeticError("Phase 7B9l block solve produced invalid intensity")
    gc.collect()
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    historical = json.loads(
        (
            ROOT
            / protocol["sources"][f"map6_worker_block{block_index:02d}"]["path"]
        ).read_text(encoding="utf-8")
    )
    report = {
        "block_index": block_index,
        "role": selected[block_index],
        "core_group_start": int(block.core_group_start),
        "core_group_stop": int(block.core_group_stop),
        "minimum_energy_ev": float(
            global_edge[block.core_group_start] * 4.135667696e-15
        ),
        "maximum_energy_ev": float(
            global_edge[block.core_group_stop] * 4.135667696e-15
        ),
        "iterations": rows,
        "final_to_first_local_update_ratio": float(
            rows[-1]["local_update_residual"] / rows[0]["local_update_residual"]
        ),
        "final_to_first_boundary_spectrum_ratio": float(
            rows[-1]["boundary_spectrum_l1"] / rows[0]["boundary_spectrum_l1"]
        ),
        "fixed_point_converged_to_transport_tolerance": bool(
            result.fixed_point_converged
        ),
        "minimum_final_intensity": float(np.min(final)),
        "wall_runtime_s": wall_runtime,
        "historical_one_update_runtime_s": float(historical["runtime_s"]),
        "runtime_multiplier_over_one_update": float(
            wall_runtime / float(historical["runtime_s"])
        ),
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
    }
    _write_json_atomic(report_path, report)


def _plot(
    path: Path,
    reports: list[dict[str, object]],
    gate: dict[str, object],
    *,
    full_map_authorized: bool,
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(13.0, 8.2), constrained_layout=True)
    for report in reports:
        rows = report["iterations"]
        iteration = [row["iteration"] for row in rows]
        label = f"B{report['block_index']}: {report['role']}"
        axes[0, 0].semilogy(
            iteration,
            [row["local_update_residual"] for row in rows],
            marker="o",
            ms=3,
            label=label,
        )
        axes[0, 1].semilogy(
            iteration,
            [row["boundary_spectrum_l1"] for row in rows],
            marker="o",
            ms=3,
            label=f"B{report['block_index']}",
        )
    axes[0, 0].set(
        xlabel="Block-internal source update",
        ylabel="Local update residual",
        title="(a) Block-internal contraction",
    )
    axes[0, 0].legend(frameon=False, fontsize=7)
    axes[0, 1].set(
        xlabel="Block-internal source update",
        ylabel="Boundary spectral L1 change",
        title="(b) Local boundary stabilization",
    )
    axes[0, 1].legend(frameon=False, fontsize=8)
    block = np.asarray([report["block_index"] for report in reports])
    residual_ratio = np.asarray(
        [report["final_to_first_local_update_ratio"] for report in reports]
    )
    runtime_ratio = np.asarray(
        [report["runtime_multiplier_over_one_update"] for report in reports]
    )
    axes[1, 0].bar(block - 0.18, residual_ratio, width=0.36, label="Residual ratio")
    axes[1, 0].bar(block + 0.18, runtime_ratio / 10.0, width=0.36, label="Runtime ratio / 10")
    axes[1, 0].axhline(
        gate["each_final_to_first_local_update_ratio_below"],
        color="0.25",
        ls="--",
        label="Worst residual gate",
    )
    axes[1, 0].set(
        xlabel="Natural frequency block",
        ylabel="Dimensionless ratio",
        title="(c) Contraction versus cost",
    )
    axes[1, 0].legend(frameon=False, fontsize=8)
    axes[1, 1].axis("off")
    median = float(np.median(residual_ratio))
    projected = float(np.median(runtime_ratio))
    axes[1, 1].text(
        0.03,
        0.95,
        "(d) Representative-block decision\n\n"
        f"Worst final/first residual = {float(np.max(residual_ratio)):.3f}\n"
        f"Median final/first residual = {median:.3f}\n"
        f"Median runtime multiplier = {projected:.2f}\n\n"
        f"Full-frequency map authorized: {full_map_authorized}\n"
        "Material feedback: not evaluated",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=11,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    selected = [
        int(row["block_index"])
        for row in protocol["configuration"]["selected_blocks"]
    ]
    report_paths = [
        OUTPUT / f"phase7b9l_block{index:02d}_implicit.json" for index in selected
    ]
    concurrency = int(protocol["configuration"]["maximum_concurrent_processes"])
    for offset in range(0, len(selected), concurrency):
        batch = selected[offset : offset + concurrency]
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
                    "--worker-report",
                    str(report_paths[selected.index(block_index)]),
                ],
                cwd=ROOT,
            )
            for block_index in batch
        ]
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"Phase 7B9l worker failure: {codes}")
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    reports.sort(key=lambda row: int(row["block_index"]))
    gates = protocol["gates"]
    residual_ratios = np.asarray(
        [row["final_to_first_local_update_ratio"] for row in reports]
    )
    boundary_ratios = np.asarray(
        [row["final_to_first_boundary_spectrum_ratio"] for row in reports]
    )
    runtime_multiplier = float(
        sum(row["wall_runtime_s"] for row in reports)
        / sum(row["historical_one_update_runtime_s"] for row in reports)
    )
    prior = json.loads(
        (ROOT / protocol["sources"]["phase7b9k_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    projected_wall = float(prior["history"][-1]["wall_runtime_s"]) * runtime_multiplier
    checks = {
        "representative_coverage_complete": len(reports)
        == gates["selected_block_count_exactly"],
        "iteration_counts_exact": all(
            len(row["iterations"]) == gates["each_iteration_count_exactly"]
            for row in reports
        ),
        "every_local_residual_contracts_enough": bool(
            np.all(
                residual_ratios
                < gates["each_final_to_first_local_update_ratio_below"]
            )
        ),
        "median_local_residual_contracts_enough": bool(
            np.median(residual_ratios)
            < gates["median_final_to_first_local_update_ratio_below"]
        ),
        "worst_map6_block_contracts_enough": bool(
            next(
                row["final_to_first_local_update_ratio"]
                for row in reports
                if int(row["block_index"]) == 25
            )
            < gates["worst_map6_block25_final_to_first_ratio_below"]
        ),
        "boundary_spectra_contract": bool(
            np.all(
                boundary_ratios
                < gates["each_final_to_first_boundary_spectrum_ratio_below"]
            )
        ),
        "finite_nonnegative_and_within_memory": all(
            min(item["minimum_intensity"] for item in row["iterations"])
            >= gates["minimum_intensity_at_least"]
            and row["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            for row in reports
        ),
        "selected_runtime_multiplier_passes": runtime_multiplier
        < gates["selected_runtime_multiplier_over_one_map_below"],
        "projected_full_map_cost_passes": projected_wall
        < gates["projected_full_map_wall_time_strictly_below_s"],
    }
    passed = all(checks.values())
    decision = {
        "representative_block_implicit_pilot_passed": passed,
        "one_full_frequency_block_implicit_map_authorized": passed,
        "natural_block_aitken_continuation_authorized": False,
        "plain_omega1_resume_authorized": False,
        "full_frequency_accelerated_map_evaluated": False,
        "trial_inner_radiation_converged": False,
        "trial_formal_feedback_evaluated": False,
        "trial_true_residual_evaluated": False,
        "trial_rejected_by_physical_residual": False,
        "accepted_as_dynamic_nlte_solution": False,
        "phase7b9l_gate_passed": passed,
    }
    figure = OUTPUT / "phase7b9l_block_implicit_pilot.png"
    _plot(figure, reports, gates, full_map_authorized=passed)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "reports": reports,
        "maximum_final_to_first_local_update_ratio": float(np.max(residual_ratios)),
        "median_final_to_first_local_update_ratio": float(np.median(residual_ratios)),
        "maximum_final_to_first_boundary_spectrum_ratio": float(
            np.max(boundary_ratios)
        ),
        "selected_runtime_multiplier_over_one_update": runtime_multiplier,
        "projected_full_map_wall_time_s": projected_wall,
        "gate_checks": checks,
        "decision": decision,
        "figures": [figure.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9l_block_implicit_pilot_summary.json", summary
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9l_preregistered_block_implicit_pilot.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.block_index is None or args.worker_report is None:
            raise ValueError("worker mode requires block index and report path")
        _run_worker(args.protocol, args.block_index, args.worker_report)
        return
    summary = run(args.protocol)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
