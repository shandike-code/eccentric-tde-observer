"""Phase 7B9q：全深度静态频率 ALI 两块可行性复核。"""

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

from eccentric_tde_observer.affine_krylov import exact_nonnegative_affine_step
from eccentric_tde_observer.mixed_frame_ali import (
    static_frequency_spatial_ali_residual_correction,
)
from eccentric_tde_observer.mixed_frame_frequency import (
    lorentz_ray_transform,
    lorentz_remap_comoving_group_extinction_to_lab,
)

try:
    from scripts import phase7b9p_doppler_coupled_ali_pilot as prior
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9p_doppler_coupled_ali_pilot as prior  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "b80241177121c75f25c611c4d72638996f46417deb5591afc5851f46b985f0db"
)
MIB = 1024**2
base = prior.base


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9q protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9q source changed: {source['path']}"
                )
    return protocol


def _run_worker(protocol_path: Path, block_index: int, report_path: Path) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    selected = {
        int(row["block_index"]): row["role"]
        for row in protocol["configuration"]["selected_blocks"]
    }
    if block_index not in selected:
        raise ValueError("Phase 7B9q worker block is not preregistered")
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
    residual = mapped - initial
    raw_residual = base._relative_update(initial, mapped)
    raw_flux = base._block_flux(initial, mu, weight, frequency_width)
    raw_mapped_flux = base._block_flux(mapped, mu, weight, frequency_width)
    raw_boundary = base._spectral_l1(raw_flux, raw_mapped_flux)
    del mapped

    precondition_started = time.perf_counter()
    transform = lorentz_ray_transform(mu, weight, context["beta"])
    collision_groups = block.local_stencil.comoving_collision_group_count
    angle_points = mu.size
    depth_points = context["beta"].size
    extinction_comoving_angle = np.broadcast_to(
        (fields["true_absorption"] + fields["scattering"])[:, None, :],
        (collision_groups, angle_points, depth_points),
    )
    lab_extinction = lorentz_remap_comoving_group_extinction_to_lab(
        extinction_comoving_angle,
        block.local_stencil.comoving_collision_edge_hz,
        block.local_stencil.active_lab_edge_hz,
        transform.doppler_lab_to_comoving,
    )
    # 中文：近似逆保留全深度传播，但暂时把散射源限制为同一实验室频率。
    static_scattering = lorentz_remap_comoving_group_extinction_to_lab(
        np.broadcast_to(
            fields["scattering"][:, None, :],
            (collision_groups, angle_points, depth_points),
        ),
        block.local_stencil.comoving_collision_edge_hz,
        block.local_stencil.active_lab_edge_hz,
        np.ones_like(transform.doppler_lab_to_comoving),
    )
    failure: str | None = None
    try:
        ali = static_frequency_spatial_ali_residual_correction(
            residual,
            fields["old_edge"],
            fields["new_edge"],
            mu,
            weight,
            lab_extinction,
            static_scattering,
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
        )
    except ArithmeticError as error:
        ali = None
        failure = str(error)
    spatial_converged = ali is not None
    if ali is not None:
        direction = np.array(ali.correction, copy=True)
        exact_step = exact_nonnegative_affine_step(initial, direction)
        candidate = initial + exact_step * direction
        spatial_iterations = ali.gmres_iteration_count
        spatial_info = ali.gmres_reported_info
        spatial_residual = ali.final_scaled_linf_linear_residual
        mean_consistency = ali.final_mean_consistency_linf
        minimum_denominator = ali.minimum_local_preconditioner_denominator
        maximum_feedback = ali.maximum_local_preconditioner_feedback
        del ali, direction
    else:
        candidate = None
        exact_step = None
        spatial_iterations = None
        spatial_info = None
        spatial_residual = None
        mean_consistency = None
        minimum_denominator = None
        maximum_feedback = None
    precondition_runtime = time.perf_counter() - precondition_started
    del transform, extinction_comoving_angle, lab_extinction, static_scattering

    if candidate is not None:
        fresh_started = time.perf_counter()
        mapped_candidate = source_map(candidate)
        fresh_validation_runtime = time.perf_counter() - fresh_started
        fresh_residual = base._relative_update(candidate, mapped_candidate)
        fresh_ratio = fresh_residual / raw_residual
        candidate_flux = base._block_flux(candidate, mu, weight, frequency_width)
        mapped_candidate_flux = base._block_flux(
            mapped_candidate, mu, weight, frequency_width
        )
        candidate_boundary = base._spectral_l1(
            candidate_flux, mapped_candidate_flux
        )
        boundary_ratio = (
            candidate_boundary / raw_boundary
            if raw_boundary > 0.0
            else (0.0 if candidate_boundary == 0.0 else math.inf)
        )
        minimum_candidate = float(np.min(candidate))
        del candidate, mapped_candidate
    else:
        fresh_validation_runtime = 0.0
        fresh_residual = None
        fresh_ratio = None
        candidate_boundary = None
        boundary_ratio = None
        minimum_candidate = None
    wall_runtime = time.perf_counter() - started
    application_runtime = raw_map_runtime + precondition_runtime
    del residual
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
        "spatial_inverse_converged": spatial_converged,
        "spatial_inverse_failure": failure,
        "gmres_iteration_count": spatial_iterations,
        "gmres_reported_info": spatial_info,
        "spatial_inverse_scaled_linf_residual": spatial_residual,
        "spatial_inverse_mean_consistency_linf": mean_consistency,
        "minimum_local_preconditioner_denominator": minimum_denominator,
        "maximum_local_preconditioner_feedback": maximum_feedback,
        "exact_nonnegative_step": exact_step,
        "minimum_candidate_intensity": minimum_candidate,
        "fresh_candidate_original_operator_residual": fresh_residual,
        "fresh_candidate_to_raw_residual_ratio": fresh_ratio,
        "fresh_candidate_boundary_spectrum_l1": candidate_boundary,
        "fresh_candidate_to_raw_boundary_ratio": boundary_ratio,
        "raw_map_runtime_s": raw_map_runtime,
        "preconditioner_runtime_s": precondition_runtime,
        "fresh_validation_runtime_s": fresh_validation_runtime,
        "wall_runtime_s": wall_runtime,
        "ali_application_runtime_s": application_runtime,
        "historical_one_update_runtime_s": historical_runtime,
        "ali_application_runtime_multiplier_over_one_update": (
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
    valid = [row for row in reports if row["spatial_inverse_converged"]]
    axes[0].bar(
        [row["block_index"] for row in valid],
        [row["fresh_candidate_to_raw_residual_ratio"] for row in valid],
        color="tab:blue",
    )
    axes[0].axhline(
        gates["each_fresh_candidate_to_raw_residual_ratio_below"],
        color="0.25",
        ls="--",
        label="Interior gate",
    )
    axes[0].set(
        xlabel="Natural frequency block",
        ylabel="Spatial-ALI candidate / raw residual",
        title="(a) Original-operator validation",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].semilogy(
        [row["block_index"] for row in valid],
        [row["spatial_inverse_scaled_linf_residual"] for row in valid],
        "o-",
        label="Scaled linear residual",
    )
    axes[1].axhline(
        gates["each_spatial_inverse_scaled_linf_residual_at_most"],
        color="0.25",
        ls="--",
        label="Linear gate",
    )
    axes[1].set(
        xlabel="Natural frequency block",
        ylabel="Static spatial inverse residual",
        title="(b) Matrix-free solve audit",
    )
    axes[1].legend(frameon=False, fontsize=8)
    axes[2].axis("off")
    axes[2].text(
        0.03,
        0.95,
        "(c) Spatial-ALI feasibility\n\n"
        f"Converged blocks = {len(valid)}/{len(reports)}\n"
        f"GMRES iterations = "
        f"{[row['gmres_iteration_count'] for row in valid]}\n"
        f"Application cost = "
        f"{[round(row['ali_application_runtime_multiplier_over_one_update'], 2) for row in reports]}\n\n"
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
        OUTPUT / f"phase7b9q_block{index:02d}_spatial_ali.json"
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
                f"Phase 7B9q worker {block_index} failed: {process.returncode}"
            )
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    reports.sort(key=lambda row: int(row["block_index"]))
    gates = protocol["gates"]
    valid = [row for row in reports if row["spatial_inverse_converged"]]
    fresh = np.asarray(
        [row["fresh_candidate_to_raw_residual_ratio"] for row in valid]
    )
    boundary = np.asarray(
        [row["fresh_candidate_to_raw_boundary_ratio"] for row in valid]
    )
    application_multiplier = float(
        sum(row["ali_application_runtime_s"] for row in reports)
        / sum(row["historical_one_update_runtime_s"] for row in reports)
    )
    map6_wall = json.loads(
        (OUTPUT / "phase7b9k_block_aitken_pilot_summary.json").read_text(
            encoding="utf-8"
        )
    )["history"][-1]["wall_runtime_s"]
    projected_wall = float(map6_wall) * application_multiplier
    checks = {
        "representative_coverage_complete": len(reports)
        == gates["selected_block_count_exactly"],
        "every_spatial_inverse_passes": len(valid) == len(reports)
        and all(
            row["spatial_inverse_scaled_linf_residual"]
            <= gates["each_spatial_inverse_scaled_linf_residual_at_most"]
            and row["spatial_inverse_mean_consistency_linf"]
            <= gates["each_spatial_inverse_mean_consistency_at_most"]
            and row["gmres_iteration_count"]
            <= gates["each_gmres_iteration_count_at_most"]
            for row in valid
        ),
        "every_exact_nonnegative_step_passes": len(valid) == len(reports)
        and all(
            row["exact_nonnegative_step"]
            >= gates["each_exact_nonnegative_step_at_least"]
            for row in valid
        ),
        "every_fresh_original_residual_improves_enough": len(valid) == len(reports)
        and bool(
            np.all(
                fresh
                < gates["each_fresh_candidate_to_raw_residual_ratio_below"]
            )
        ),
        "median_fresh_original_residual_improves_enough": len(valid) == len(reports)
        and float(np.median(fresh))
        < gates["median_fresh_candidate_to_raw_residual_ratio_below"],
        "boundary_residuals_do_not_worsen": len(valid) == len(reports)
        and bool(
            np.all(
                boundary
                <= gates["each_candidate_boundary_residual_ratio_at_most"]
            )
        ),
        "candidates_finite_nonnegative_and_within_memory": len(valid)
        == len(reports)
        and all(
            row["minimum_candidate_intensity"]
            >= gates["minimum_candidate_intensity_at_least"]
            and row["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            for row in valid
        ),
        "selected_runtime_multiplier_passes": application_multiplier
        < gates["selected_runtime_multiplier_over_one_map_below"],
        "projected_full_map_cost_passes": projected_wall
        < gates["projected_full_map_wall_time_strictly_below_s"],
    }
    passed = all(checks.values())
    decision = {
        "spatial_ali_two_block_feasibility_passed": passed,
        "four_block_spatial_ali_gate_authorized": passed,
        "one_full_frequency_spatial_ali_map_authorized": False,
        "full_frequency_accelerated_map_evaluated": False,
        "trial_formal_feedback_evaluated": False,
        "trial_true_residual_evaluated": False,
        "accepted_as_dynamic_nlte_solution": False,
        "phase7b9q_gate_passed": passed,
    }
    figure = OUTPUT / "phase7b9q_spatial_ali_feasibility.png"
    _plot(figure, reports, gates, extended_gate_authorized=passed)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "reports": reports,
        "maximum_fresh_candidate_to_raw_residual_ratio": (
            float(np.max(fresh)) if fresh.size else None
        ),
        "median_fresh_candidate_to_raw_residual_ratio": (
            float(np.median(fresh)) if fresh.size else None
        ),
        "selected_ali_application_runtime_multiplier_over_one_update": (
            application_multiplier
        ),
        "projected_full_map_wall_time_s": projected_wall,
        "gate_checks": checks,
        "decision": decision,
        "figures": [figure.name],
    }
    base._write_json_atomic(
        OUTPUT / "phase7b9q_spatial_ali_feasibility_summary.json", summary
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9q_preregistered_spatial_ali_feasibility.json",
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
