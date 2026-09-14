"""Phase 7B9r：完整固定物质源 Krylov 方向与仿射残差线搜索。"""

from __future__ import annotations

import argparse
import gc
import json
import math
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
    from scripts import phase7b9q_spatial_ali_feasibility as previous
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9q_spatial_ali_feasibility as previous  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "f87a32c5458556c4677303c489247498b6857b8d4f4b5f0abf0cce77cd12fee8"
)
MIB = 1024**2
base = previous.base


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9r protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9r source changed: {source['path']}"
                )
    return protocol


def _run_worker(
    protocol_path: Path,
    block_index: int,
    report_path: Path,
    *,
    protocol_override: dict[str, object] | None = None,
    output_state_path: Path | None = None,
) -> None:
    """运行一个冻结块；后续扩展门可显式传入已校验的同构协议。"""
    protocol = (
        _load_protocol(protocol_path, validate_sources=False)
        if protocol_override is None
        else protocol_override
    )
    selected = {
        int(row["block_index"]): row["role"]
        for row in protocol["configuration"]["selected_blocks"]
    }
    if block_index not in selected:
        raise ValueError("Phase 7B9r worker block is not preregistered")
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

    baseline_rss = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    raw_started = time.perf_counter()
    mapped = source_map(initial)
    raw_map_runtime = time.perf_counter() - raw_started
    raw_vector = mapped - initial
    raw_residual = base._relative_update(initial, mapped)
    raw_flux = base._block_flux(initial, mu, weight, frequency_width)
    raw_mapped_flux = base._block_flux(mapped, mu, weight, frequency_width)
    raw_boundary = base._spectral_l1(raw_flux, raw_mapped_flux)
    del mapped

    krylov_started = time.perf_counter()
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
            "gmres_maximum_restart_cycles"
        ],
        allow_turning_ray_upwind=True,
        allow_incomplete_krylov=True,
    )
    direction = np.array(krylov.correction, copy=True)
    endpoint_positive_step = exact_nonnegative_affine_step(initial, direction)
    endpoint = initial + endpoint_positive_step * direction
    krylov_runtime = time.perf_counter() - krylov_started
    krylov_converged = krylov.fixed_point_converged
    krylov_iterations = krylov.gmres_iteration_count
    krylov_info = krylov.gmres_reported_info
    krylov_residual = krylov.final_scaled_linf_linear_residual
    krylov_consistency = krylov.final_comoving_mean_consistency_linf
    del transform, lab_extinction, krylov

    endpoint_started = time.perf_counter()
    mapped_endpoint = source_map(endpoint)
    endpoint_validation_runtime = time.perf_counter() - endpoint_started
    endpoint_vector = mapped_endpoint - endpoint
    endpoint_residual = base._relative_update(endpoint, mapped_endpoint)
    endpoint_to_raw = endpoint_residual / raw_residual
    line = constrained_affine_residual_line_minimum(raw_vector, endpoint_vector)
    line_fraction = line.selected_fraction
    line_candidate = initial + line_fraction * endpoint_positive_step * direction
    predicted_vector = raw_vector + line_fraction * (endpoint_vector - raw_vector)
    del endpoint, mapped_endpoint, direction

    fresh_started = time.perf_counter()
    mapped_line = source_map(line_candidate)
    fresh_validation_runtime = time.perf_counter() - fresh_started
    fresh_vector = mapped_line - line_candidate
    fresh_residual = base._relative_update(line_candidate, mapped_line)
    fresh_ratio = fresh_residual / raw_residual
    prediction_error = float(
        np.max(np.abs(fresh_vector - predicted_vector))
        / max(
            float(np.max(np.abs(fresh_vector))),
            float(np.max(np.abs(predicted_vector))),
        )
    )
    line_flux = base._block_flux(line_candidate, mu, weight, frequency_width)
    mapped_line_flux = base._block_flux(mapped_line, mu, weight, frequency_width)
    line_boundary = base._spectral_l1(line_flux, mapped_line_flux)
    boundary_ratio = (
        line_boundary / raw_boundary
        if raw_boundary > 0.0
        else (0.0 if line_boundary == 0.0 else math.inf)
    )
    minimum_candidate = float(np.min(line_candidate))
    if output_state_path is not None:
        output_global = np.memmap(
            output_state_path, mode="r+", dtype=np.float64, shape=shape
        )
        output_global[core] = line_candidate
        output_global.flush()
        del output_global
    wall_runtime = time.perf_counter() - started
    application_runtime = (
        raw_map_runtime + krylov_runtime + endpoint_validation_runtime
        + fresh_validation_runtime
    )
    del (
        raw_vector,
        endpoint_vector,
        predicted_vector,
        fresh_vector,
        line_candidate,
        mapped_line,
    )
    gc.collect()
    peak_rss = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    historical = json.loads(
        (
            ROOT
            / protocol["sources"][f"map6_worker_block{block_index:02d}"]["path"]
        ).read_text(encoding="utf-8")
    )
    historical_runtime = float(historical["runtime_s"])
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
        "raw_original_operator_residual": raw_residual,
        "raw_boundary_spectrum_l1": raw_boundary,
        "krylov_converged": krylov_converged,
        "gmres_iteration_count": krylov_iterations,
        "gmres_reported_info": krylov_info,
        "krylov_scaled_linf_residual": krylov_residual,
        "krylov_comoving_mean_consistency_linf": krylov_consistency,
        "endpoint_exact_nonnegative_step": endpoint_positive_step,
        "endpoint_original_operator_residual": endpoint_residual,
        "endpoint_to_raw_residual_ratio": endpoint_to_raw,
        "line_unconstrained_fraction": line.unconstrained_fraction,
        "line_selected_fraction": line_fraction,
        "line_selected_lower_boundary": line.selected_lower_boundary,
        "line_selected_upper_boundary": line.selected_upper_boundary,
        "line_predicted_squared_residual_norm": line.predicted_squared_norm,
        "minimum_line_candidate_intensity": minimum_candidate,
        "fresh_line_candidate_original_operator_residual": fresh_residual,
        "fresh_line_candidate_to_raw_residual_ratio": fresh_ratio,
        "affine_prediction_to_fresh_residual_linf": prediction_error,
        "fresh_line_candidate_boundary_spectrum_l1": line_boundary,
        "fresh_line_candidate_to_raw_boundary_ratio": boundary_ratio,
        "raw_map_runtime_s": raw_map_runtime,
        "krylov_runtime_s": krylov_runtime,
        "endpoint_validation_runtime_s": endpoint_validation_runtime,
        "fresh_validation_runtime_s": fresh_validation_runtime,
        "wall_runtime_s": wall_runtime,
        "application_runtime_s": application_runtime,
        "historical_one_update_runtime_s": historical_runtime,
        "application_runtime_multiplier_over_one_update": (
            application_runtime / historical_runtime
        ),
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
    }
    base._write_json_atomic(report_path, report)


def _plot(
    path: Path,
    reports: list[dict[str, object]],
    gates: dict[str, object],
    *,
    extended_gate_authorized: bool,
) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(14.0, 4.4), constrained_layout=True)
    block = np.asarray([row["block_index"] for row in reports])
    endpoint = np.asarray([row["endpoint_to_raw_residual_ratio"] for row in reports])
    line = np.asarray(
        [row["fresh_line_candidate_to_raw_residual_ratio"] for row in reports]
    )
    prediction_labels = [
        f"{row['affine_prediction_to_fresh_residual_linf']:.1e}"
        for row in reports
    ]
    width = 0.34
    axes[0].bar(block - width / 2, endpoint, width, label="Krylov endpoint")
    axes[0].bar(block + width / 2, line, width, label="Affine line minimum")
    axes[0].axhline(
        gates["each_fresh_line_candidate_to_raw_residual_ratio_below"],
        color="0.25",
        ls="--",
        label="Line gate",
    )
    axes[0].set(
        xlabel="Natural frequency block",
        ylabel="Candidate / raw residual",
        title="(a) Original-operator validation",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].bar(
        block,
        [row["line_selected_fraction"] for row in reports],
        color="tab:green",
    )
    axes[1].axhline(
        gates["each_selected_line_fraction_at_least"],
        color="0.25",
        ls="--",
        label="Useful-step gate",
    )
    axes[1].set(
        xlabel="Natural frequency block",
        ylabel="Selected endpoint fraction",
        title="(b) Exact affine line search",
    )
    axes[1].legend(frameon=False, fontsize=8)
    axes[2].axis("off")
    axes[2].text(
        0.03,
        0.95,
        "(c) Full-source Krylov decision\n\n"
        f"Krylov converged = "
        f"{[row['krylov_converged'] for row in reports]}\n"
        f"GMRES iterations = "
        f"{[row['gmres_iteration_count'] for row in reports]}\n"
        f"Prediction errors = {prediction_labels}\n\n"
        f"Four-block gate authorized: {extended_gate_authorized}\n"
        "Full-frequency map authorized: False",
        transform=axes[2].transAxes,
        va="top",
        fontsize=10.5,
    )
    axes[0].set_xticks(block)
    axes[1].set_xticks(block)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    selected = [
        int(row["block_index"])
        for row in protocol["configuration"]["selected_blocks"]
    ]
    report_paths = [
        OUTPUT / f"phase7b9r_block{index:02d}_full_source_krylov.json"
        for index in selected
    ]
    for block_index, report_path in zip(selected, report_paths, strict=True):
        process = subprocess.run(
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
            ],
            cwd=ROOT,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"Phase 7B9r worker {block_index} failed: {process.returncode}"
            )
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    reports.sort(key=lambda row: int(row["block_index"]))
    gates = protocol["gates"]
    fresh = np.asarray(
        [row["fresh_line_candidate_to_raw_residual_ratio"] for row in reports]
    )
    boundary = np.asarray(
        [row["fresh_line_candidate_to_raw_boundary_ratio"] for row in reports]
    )
    runtime_multiplier = float(
        sum(row["application_runtime_s"] for row in reports)
        / sum(row["historical_one_update_runtime_s"] for row in reports)
    )
    map6_wall = json.loads(
        (OUTPUT / "phase7b9k_block_aitken_pilot_summary.json").read_text(
            encoding="utf-8"
        )
    )["history"][-1]["wall_runtime_s"]
    projected_wall = float(map6_wall) * runtime_multiplier
    checks = {
        "representative_coverage_complete": len(reports)
        == gates["selected_block_count_exactly"],
        "finite_work_krylov_budget_passes": all(
            row["gmres_iteration_count"]
            <= gates["each_gmres_iteration_count_at_most"]
            for row in reports
        ),
        "endpoint_positive_steps_pass": all(
            row["endpoint_exact_nonnegative_step"]
            >= gates["each_endpoint_exact_nonnegative_step_at_least"]
            for row in reports
        ),
        "line_search_steps_are_useful": all(
            row["line_selected_fraction"]
            >= gates["each_selected_line_fraction_at_least"]
            for row in reports
        ),
        "every_fresh_line_residual_improves_enough": bool(
            np.all(
                fresh
                < gates[
                    "each_fresh_line_candidate_to_raw_residual_ratio_below"
                ]
            )
        ),
        "median_fresh_line_residual_improves_enough": float(np.median(fresh))
        < gates["median_fresh_line_candidate_to_raw_residual_ratio_below"],
        "boundary_residuals_do_not_worsen": bool(
            np.all(
                boundary
                <= gates["each_fresh_line_candidate_boundary_ratio_at_most"]
            )
        ),
        "affine_prediction_is_faithful": all(
            row["affine_prediction_to_fresh_residual_linf"]
            < gates["each_affine_prediction_to_fresh_residual_linf_below"]
            for row in reports
        ),
        "candidates_finite_nonnegative_and_within_memory": all(
            row["minimum_line_candidate_intensity"]
            >= gates["minimum_line_candidate_intensity_at_least"]
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
        "full_source_krylov_line_search_feasibility_passed": passed,
        "four_block_full_source_krylov_gate_authorized": passed,
        "one_full_frequency_accelerated_map_authorized": False,
        "full_frequency_accelerated_map_evaluated": False,
        "trial_formal_feedback_evaluated": False,
        "trial_true_residual_evaluated": False,
        "accepted_as_dynamic_nlte_solution": False,
        "phase7b9r_gate_passed": passed,
    }
    figure = OUTPUT / "phase7b9r_full_source_krylov_line_search.png"
    _plot(figure, reports, gates, extended_gate_authorized=passed)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "reports": reports,
        "maximum_fresh_line_candidate_to_raw_residual_ratio": float(np.max(fresh)),
        "median_fresh_line_candidate_to_raw_residual_ratio": float(np.median(fresh)),
        "selected_application_runtime_multiplier_over_one_update": runtime_multiplier,
        "projected_full_map_wall_time_s": projected_wall,
        "gate_checks": checks,
        "decision": decision,
        "figures": [figure.name],
    }
    base._write_json_atomic(
        OUTPUT / "phase7b9r_full_source_krylov_line_search_summary.json", summary
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9r_preregistered_full_source_krylov_line_search.json",
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
