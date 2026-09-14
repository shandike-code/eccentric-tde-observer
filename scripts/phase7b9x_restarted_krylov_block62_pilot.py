"""Phase 7B9x：块 62 的两段物理重启完整源 Krylov 试验。"""

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

from eccentric_tde_observer.affine_krylov import (
    constrained_affine_residual_line_minimum,
    exact_nonnegative_affine_step,
)
from eccentric_tde_observer.mixed_frame_ali import (
    mixed_frame_spatial_source_residual_correction,
)
from eccentric_tde_observer.mixed_frame_frequency import (
    lorentz_ray_transform,
    lorentz_remap_comoving_group_extinction_to_lab,
)

try:
    from scripts import phase7b9r_full_source_krylov_line_search as previous
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9r_full_source_krylov_line_search as previous  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "ede987f3d1f70b8864f746f7eca685cbd56be4d7f6b810c916392852c6655186"
)
MIB = 1024**2
base = previous.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9x protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9x source changed: {source['path']}"
                )
    return protocol


def _run_worker(protocol_path: Path, report_path: Path) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    block_index = 62
    current_path = ROOT / protocol["sources"]["current_map6_state"]["path"]
    finite_protocol = base.phase7b9i._load_protocol(
        ROOT / protocol["sources"]["finite_trial_protocol"]["path"],
        validate_sources=False,
    )
    base.phase7b9d._configure_worker(finite_protocol, current_path)
    template_protocol = base.phase7b7i._load_protocol(
        protocol_path, validate_sources=False
    )
    context = base.phase7b7i.phase7b7e.phase7b5x._context(template_protocol)
    block = context["blocks"][block_index]
    material = base.phase7b7i._second_full_material(template_protocol)
    fields = base.phase7b7i.phase7b7e._local_fields(context, block, material)
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
    initial = np.array(current_global[core], copy=True)
    del current_global
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
            spatial_scheme=protocol["configuration"]["spatial_scheme"],
            source_map_only=True,
        )
        mapped = np.array(result.final_lab_intensity_density, copy=True)
        del result
        return mapped

    transform = lorentz_ray_transform(mu, weight, context["beta"])
    collision_groups = block.local_stencil.comoving_collision_group_count
    angle_points = mu.size
    depth_points = context["beta"].size
    lab_extinction = lorentz_remap_comoving_group_extinction_to_lab(
        np.broadcast_to(
            (fields["true_absorption"] + fields["scattering"])[:, None, :],
            (collision_groups, angle_points, depth_points),
        ),
        block.local_stencil.comoving_collision_edge_hz,
        block.local_stencil.active_lab_edge_hz,
        transform.doppler_lab_to_comoving,
    )

    def one_stage(current: np.ndarray, stage: int) -> tuple[np.ndarray, dict[str, object]]:
        mapped = source_map(current)
        raw_vector = mapped - current
        raw_residual = base._relative_update(current, mapped)
        raw_flux = base._block_flux(current, mu, weight, frequency_width)
        mapped_flux = base._block_flux(mapped, mu, weight, frequency_width)
        raw_boundary = base._spectral_l1(raw_flux, mapped_flux)
        del mapped
        krylov = mixed_frame_spatial_source_residual_correction(
            raw_vector,
            fields["old_edge"],
            fields["new_edge"],
            block.local_stencil.outer_lab_edge_hz,
            block.local_stencil.comoving_collision_edge_hz,
            block.local_stencil.active_lab_edge_hz,
            block.local_stencil.active_outer_group_start,
            block.local_stencil.active_outer_group_stop,
            mu,
            weight,
            context["beta"],
            lab_extinction,
            fields["scattering"],
            context["duration_s"],
            propagation_speed_cm_s=base.phase7b7i.phase7b7e.LIGHT_SPEED_CM_S,
            gmres_relative_tolerance=protocol["configuration"][
                "gmres_relative_tolerance"
            ],
            gmres_restart=protocol["configuration"]["gmres_restart"],
            gmres_maximum_restart_cycles=protocol["configuration"][
                "gmres_maximum_restart_cycles_per_stage"
            ],
            allow_turning_ray_upwind=True,
            allow_incomplete_krylov=True,
        )
        direction = np.array(krylov.correction, copy=True)
        positive_step = exact_nonnegative_affine_step(current, direction)
        endpoint = current + positive_step * direction
        mapped_endpoint = source_map(endpoint)
        endpoint_vector = mapped_endpoint - endpoint
        line = constrained_affine_residual_line_minimum(raw_vector, endpoint_vector)
        candidate = current + line.selected_fraction * positive_step * direction
        predicted = raw_vector + line.selected_fraction * (
            endpoint_vector - raw_vector
        )
        mapped_candidate = source_map(candidate)
        fresh_vector = mapped_candidate - candidate
        fresh_residual = base._relative_update(candidate, mapped_candidate)
        candidate_flux = base._block_flux(candidate, mu, weight, frequency_width)
        mapped_candidate_flux = base._block_flux(
            mapped_candidate, mu, weight, frequency_width
        )
        fresh_boundary = base._spectral_l1(candidate_flux, mapped_candidate_flux)
        residual_scale = max(
            float(np.max(np.abs(fresh_vector))),
            float(np.max(np.abs(predicted))),
        )
        prediction_error = float(np.max(np.abs(fresh_vector - predicted)))
        row = {
            "stage": stage,
            "raw_original_operator_residual": raw_residual,
            "fresh_candidate_original_operator_residual": fresh_residual,
            "fresh_candidate_to_stage_raw_residual_ratio": (
                fresh_residual / raw_residual
            ),
            "raw_boundary_spectrum_l1": raw_boundary,
            "fresh_candidate_boundary_spectrum_l1": fresh_boundary,
            "fresh_candidate_to_stage_raw_boundary_ratio": (
                fresh_boundary / raw_boundary
                if raw_boundary > 0.0
                else (0.0 if fresh_boundary == 0.0 else float("inf"))
            ),
            "gmres_iteration_count": krylov.gmres_iteration_count,
            "gmres_reported_info": krylov.gmres_reported_info,
            "krylov_scaled_linf_residual": (
                krylov.final_scaled_linf_linear_residual
            ),
            "krylov_comoving_mean_consistency_linf": (
                krylov.final_comoving_mean_consistency_linf
            ),
            "endpoint_exact_nonnegative_step": positive_step,
            "line_selected_fraction": line.selected_fraction,
            "line_unconstrained_fraction": line.unconstrained_fraction,
            "minimum_candidate_intensity": float(np.min(candidate)),
            "affine_prediction_to_fresh_residual_linf": (
                prediction_error / residual_scale
                if residual_scale > 0.0
                else prediction_error
            ),
        }
        del (
            raw_vector,
            direction,
            endpoint,
            mapped_endpoint,
            endpoint_vector,
            predicted,
            mapped_candidate,
            fresh_vector,
            krylov,
        )
        gc.collect()
        return candidate, row

    baseline_rss = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    stage_rows: list[dict[str, object]] = []
    current = initial
    for stage in range(1, int(protocol["configuration"]["physical_restart_count"]) + 1):
        following, row = one_stage(current, stage)
        if stage > 1:
            prior = float(stage_rows[-1]["fresh_candidate_original_operator_residual"])
            row["restart_raw_to_previous_fresh_relative_difference"] = abs(
                float(row["raw_original_operator_residual"]) - prior
            ) / max(abs(prior), abs(float(row["raw_original_operator_residual"])))
        else:
            row["restart_raw_to_previous_fresh_relative_difference"] = 0.0
        stage_rows.append(row)
        current = following
    peak_rss = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    first_raw = float(stage_rows[0]["raw_original_operator_residual"])
    final_residual = float(
        stage_rows[-1]["fresh_candidate_original_operator_residual"]
    )
    first_boundary = float(stage_rows[0]["raw_boundary_spectrum_l1"])
    final_boundary = float(
        stage_rows[-1]["fresh_candidate_boundary_spectrum_l1"]
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
        "physical_restart_count": len(stage_rows),
        "final_to_initial_raw_residual_ratio": final_residual / first_raw,
        "final_to_initial_raw_boundary_ratio": (
            final_boundary / first_boundary
            if first_boundary > 0.0
            else (0.0 if final_boundary == 0.0 else float("inf"))
        ),
        "minimum_final_candidate_intensity": float(np.min(current)),
        "maximum_restart_consistency_error": max(
            float(row["restart_raw_to_previous_fresh_relative_difference"])
            for row in stage_rows
        ),
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
        "wall_runtime_s": time.perf_counter() - started,
        "stages": stage_rows,
    }
    _write_json_atomic(report_path, report)


def _plot(path: Path, report: dict[str, object], gates: dict[str, object]) -> None:
    stages = report["stages"]
    figure, axes = plt.subplots(1, 2, figsize=(10.8, 4.4), constrained_layout=True)
    axes[0].plot(
        [0, 1, 2],
        [
            1.0,
            stages[0]["fresh_candidate_to_stage_raw_residual_ratio"],
            report["final_to_initial_raw_residual_ratio"],
        ],
        "o-",
    )
    axes[0].axhline(
        gates["final_to_initial_raw_residual_ratio_below"],
        color="0.25",
        ls="--",
        label="Residual gate",
    )
    axes[0].set(
        xticks=[0, 1, 2],
        xlabel="Accepted physical restart",
        ylabel="Residual / initial raw residual",
        title="(a) Restarted full-source Krylov",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].axis("off")
    axes[1].text(
        0.04,
        0.95,
        "(b) Block 62 decision\n\n"
        f"Stage 1 positive step = "
        f"{stages[0]['endpoint_exact_nonnegative_step']:.4f}\n"
        f"Stage 2 positive step = "
        f"{stages[1]['endpoint_exact_nonnegative_step']:.4f}\n"
        f"Final residual ratio = "
        f"{report['final_to_initial_raw_residual_ratio']:.4f}\n"
        f"Restart consistency = "
        f"{report['maximum_restart_consistency_error']:.2e}\n"
        f"Peak RSS = {report['peak_process_rss_mib']:.1f} MiB",
        transform=axes[1].transAxes,
        va="top",
        fontsize=10.5,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    report_path = OUTPUT / "checkpoints/phase7b9i_work/phase7b9x_block62.json"
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
        raise RuntimeError(f"Phase 7B9x worker failed: {process.returncode}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    gates = protocol["gates"]
    checks = {
        "two_physical_restarts_complete": report["physical_restart_count"]
        == gates["physical_restart_count_exactly"],
        "each_stage_finite_work_pass": all(
            row["gmres_iteration_count"]
            <= gates["each_stage_gmres_iteration_count_at_most"]
            for row in report["stages"]
        ),
        "each_stage_positive_step_pass": all(
            row["endpoint_exact_nonnegative_step"]
            >= gates["each_stage_endpoint_nonnegative_step_at_least"]
            for row in report["stages"]
        ),
        "each_stage_line_step_pass": all(
            row["line_selected_fraction"]
            >= gates["each_stage_line_fraction_at_least"]
            for row in report["stages"]
        ),
        "each_stage_original_residual_descends": all(
            row["fresh_candidate_to_stage_raw_residual_ratio"] < 1.0
            for row in report["stages"]
        ),
        "final_original_residual_pass": report[
            "final_to_initial_raw_residual_ratio"
        ]
        < gates["final_to_initial_raw_residual_ratio_below"],
        "final_boundary_does_not_worsen": report[
            "final_to_initial_raw_boundary_ratio"
        ]
        <= gates["final_to_initial_raw_boundary_ratio_at_most"],
        "restart_is_deterministic": report["maximum_restart_consistency_error"]
        < gates["restart_consistency_error_below"],
        "affine_predictions_pass": all(
            row["affine_prediction_to_fresh_residual_linf"]
            < gates["each_affine_prediction_to_fresh_residual_linf_below"]
            for row in report["stages"]
        ),
        "physical_domain_and_resources_pass": report[
            "minimum_final_candidate_intensity"
        ]
        >= gates["minimum_final_candidate_intensity_at_least"]
        and report["peak_process_rss_mib"]
        < gates["process_peak_rss_strictly_below_mib"]
        and report["wall_runtime_s"]
        < gates["worker_wall_time_strictly_below_s"],
    }
    passed = all(checks.values())
    figure = OUTPUT / "phase7b9x_restarted_krylov_block62_pilot.png"
    _plot(figure, report, gates)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "report": report,
        "gate_checks": checks,
        "decision": {
            "restarted_krylov_block62_pilot_passed": passed,
            "hybrid_frequency_solver_repair_authorized": passed,
            "global_candidate_residual_authorized": False,
            "material_feedback_authorized": False,
        },
        "figures": [figure.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9x_restarted_krylov_block62_pilot_summary.json", summary
    )
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9x_preregistered_restarted_krylov_block62_pilot.json",
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
