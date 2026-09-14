"""Phase 7B9y：块 62 的 Krylov 非负种子加 Picard 微循环。"""

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
    from scripts import phase7b9r_full_source_krylov_line_search as previous
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9r_full_source_krylov_line_search as previous  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "2fde40c9e97d53bde36df4d7cb0c9cc4253f1715945b575dd0db5bcf4fe7685f"
)
MIB = 1024**2
base = previous.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9y protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9y source changed: {source['path']}"
                )
    return protocol


def _run_worker(protocol_path: Path, report_path: Path) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    configuration = protocol["configuration"]
    block_index = 62
    guard_path = ROOT / protocol["sources"]["current_map6_state"]["path"]
    seed_path = ROOT / protocol["sources"]["phase7b9t_partial_candidate_state"]["path"]
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
    seed = np.array(seed_global[core], copy=True)
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
    current = seed
    minimum_intensity = float(np.min(seed))
    history: list[dict[str, object]] = []
    update_count = int(configuration["positive_picard_update_count"])
    for update in range(update_count + 1):
        mapped = source_map(current)
        if not np.all(np.isfinite(mapped)) or np.any(mapped < 0.0):
            raise ArithmeticError("Krylov-seeded Picard map left its physical domain")
        residual = base._relative_update(current, mapped)
        flux = base._block_flux(current, mu, weight, frequency_width)
        mapped_flux = base._block_flux(mapped, mu, weight, frequency_width)
        boundary = base._spectral_l1(flux, mapped_flux)
        minimum_intensity = min(minimum_intensity, float(np.min(mapped)))
        history.append(
            {
                "source_state_index": update,
                "original_operator_residual": residual,
                "boundary_spectrum_l1": boundary,
                "minimum_mapped_intensity": float(np.min(mapped)),
            }
        )
        if update < update_count:
            current = mapped
        else:
            del mapped
        gc.collect()
    historical = json.loads(
        (
            ROOT / protocol["sources"]["phase7b9t_block62_report"]["path"]
        ).read_text(encoding="utf-8")
    )
    raw_residual = float(historical["raw_original_operator_residual"])
    raw_boundary = float(historical["raw_boundary_spectrum_l1"])
    seed_expected = float(
        historical["fresh_line_candidate_original_operator_residual"]
    )
    seed_measured = float(history[0]["original_operator_residual"])
    final_residual = float(history[-1]["original_operator_residual"])
    final_boundary = float(history[-1]["boundary_spectrum_l1"])
    peak_rss = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "block_index": block_index,
        "core_group_start": int(block.core_group_start),
        "core_group_stop": int(block.core_group_stop),
        "minimum_energy_ev": float(
            global_edge[block.core_group_start] * 4.135667696e-15
        ),
        "maximum_energy_ev": float(
            global_edge[block.core_group_stop] * 4.135667696e-15
        ),
        "positive_picard_update_count": update_count,
        "seed_residual_expected": seed_expected,
        "seed_residual_measured": seed_measured,
        "seed_restart_relative_difference": abs(seed_measured - seed_expected)
        / max(abs(seed_measured), abs(seed_expected)),
        "final_original_operator_residual": final_residual,
        "final_to_map6_raw_residual_ratio": final_residual / raw_residual,
        "final_to_seed_residual_ratio": final_residual / seed_measured,
        "final_boundary_spectrum_l1": final_boundary,
        "final_to_map6_raw_boundary_ratio": (
            final_boundary / raw_boundary
            if raw_boundary > 0.0
            else (0.0 if final_boundary == 0.0 else float("inf"))
        ),
        "minimum_history_intensity": minimum_intensity,
        "minimum_final_candidate_intensity": float(np.min(current)),
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
        "wall_runtime_s": time.perf_counter() - started,
        "history": history,
    }
    _write_json_atomic(report_path, report)


def _plot(path: Path, report: dict[str, object], gates: dict[str, object]) -> None:
    history = report["history"]
    index = [row["source_state_index"] for row in history]
    map6_raw = report["final_original_operator_residual"] / report[
        "final_to_map6_raw_residual_ratio"
    ]
    residual = [row["original_operator_residual"] / map6_raw for row in history]
    figure, axes = plt.subplots(1, 2, figsize=(10.8, 4.4), constrained_layout=True)
    axes[0].semilogy(index, residual, "o-", ms=3)
    axes[0].axhline(
        gates["final_to_map6_raw_residual_ratio_below"],
        color="0.25",
        ls="--",
        label="Residual gate",
    )
    axes[0].set(
        xlabel="Positive Picard updates after Krylov seed",
        ylabel="Residual / map-6 raw residual",
        title="(a) Block 62 positive microcycle",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].axis("off")
    axes[1].text(
        0.04,
        0.95,
        "(b) Hybrid decision\n\n"
        f"Picard updates = {report['positive_picard_update_count']}\n"
        f"Seed residual ratio = "
        f"{report['seed_residual_measured'] / map6_raw:.4f}\n"
        f"Final residual ratio = "
        f"{report['final_to_map6_raw_residual_ratio']:.4f}\n"
        f"Minimum intensity = "
        f"{report['minimum_final_candidate_intensity']:.3e}\n"
        f"Peak RSS = {report['peak_process_rss_mib']:.1f} MiB",
        transform=axes[1].transAxes,
        va="top",
        fontsize=10.5,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    report_path = OUTPUT / "checkpoints/phase7b9i_work/phase7b9y_block62.json"
    process = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--protocol",
            str(protocol_path),
            "--worker-report",
            str(report_path),
        ],
        cwd=ROOT,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(f"Phase 7B9y worker failed: {process.returncode}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    gates = protocol["gates"]
    checks = {
        "exact_update_budget_pass": report["positive_picard_update_count"]
        == gates["positive_picard_update_count_exactly"],
        "krylov_seed_reproduced": report["seed_restart_relative_difference"]
        < gates["seed_restart_relative_difference_below"],
        "all_picard_states_are_nonnegative": report["minimum_history_intensity"]
        >= gates["minimum_history_intensity_at_least"],
        "final_candidate_is_nonnegative": report[
            "minimum_final_candidate_intensity"
        ]
        >= gates["minimum_final_candidate_intensity_at_least"],
        "final_original_operator_residual_pass": report[
            "final_to_map6_raw_residual_ratio"
        ]
        < gates["final_to_map6_raw_residual_ratio_below"],
        "boundary_does_not_worsen": report["final_to_map6_raw_boundary_ratio"]
        <= gates["final_to_map6_raw_boundary_ratio_at_most"],
        "resources_pass": report["peak_process_rss_mib"]
        < gates["process_peak_rss_strictly_below_mib"]
        and report["wall_runtime_s"]
        < gates["worker_wall_time_strictly_below_s"],
    }
    passed = all(checks.values())
    figure = OUTPUT / "phase7b9y_krylov_seeded_picard_block62_pilot.png"
    _plot(figure, report, gates)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "report": report,
        "gate_checks": checks,
        "decision": {
            "krylov_seeded_positive_picard_block62_pilot_passed": passed,
            "hybrid_frequency_solver_repair_authorized": passed,
            "global_candidate_residual_authorized": False,
            "material_feedback_authorized": False,
        },
        "figures": [figure.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9y_krylov_seeded_picard_block62_pilot_summary.json",
        summary,
    )
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT
        / "phase7b9y_preregistered_krylov_seeded_picard_block62_pilot.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.worker_report is None:
            raise ValueError("worker mode requires report path")
        _run_worker(args.protocol, args.worker_report)
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
