"""Phase 7B9o：静态同频对角 ALI 代表块及原算子复核。"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
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

from eccentric_tde_observer.affine_krylov import exact_nonnegative_affine_step
from eccentric_tde_observer.mixed_frame_ali import (
    static_diagonal_ali_residual_correction,
    step_characteristic_local_lambda_diagonal,
)
from eccentric_tde_observer.mixed_frame_frequency import (
    lorentz_ray_transform,
    lorentz_remap_comoving_group_extinction_to_lab,
)
from eccentric_tde_observer.source import PhysicalDomainError

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
    "df089fd1837a755f5e0104595382e0d3cb935c57fd15598839292401c1f8acd8"
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
        raise RuntimeError("frozen Phase 7B9o protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or _sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9o source changed: {source['path']}"
                )
    return protocol


def _relative_update(first: np.ndarray, second: np.ndarray) -> float:
    scale = max(float(np.max(np.abs(first))), float(np.max(np.abs(second))))
    change = float(np.max(np.abs(second - first)))
    return change / scale if scale > 0.0 else change


def _spectral_l1(first: np.ndarray, second: np.ndarray) -> float:
    scale = max(float(np.sum(np.abs(first))), float(np.sum(np.abs(second))))
    change = float(np.sum(np.abs(second - first)))
    return change / scale if scale > 0.0 else change


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
        raise ValueError("Phase 7B9o worker block is not preregistered")
    current_path = ROOT / protocol["sources"]["current_map6_state"]["path"]
    finite_protocol_path = ROOT / protocol["sources"]["finite_trial_protocol"]["path"]
    finite_protocol = phase7b9i._load_protocol(
        finite_protocol_path, validate_sources=False
    )
    phase7b9d._configure_worker(finite_protocol, current_path)
    template_protocol = phase7b7i._load_protocol(
        protocol_path, validate_sources=False
    )
    context = phase7b7i.phase7b7e.phase7b5x._context(template_protocol)
    block = context["blocks"][block_index]
    material = phase7b7i._second_full_material(template_protocol)
    fields = phase7b7i.phase7b7e._local_fields(context, block, material)
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
            source_iteration_initial_guess=guess,
            diagnostic_fixed_iteration_count=1,
            spatial_scheme=protocol["configuration"]["spatial_scheme"],
            source_map_only=True,
        )
        mapped = np.array(result.final_lab_intensity_density, copy=True)
        del result
        return mapped

    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    raw_started = time.perf_counter()
    mapped = source_map(initial)
    raw_map_runtime = time.perf_counter() - raw_started
    residual = mapped - initial
    raw_residual = _relative_update(initial, mapped)
    raw_flux = _block_flux(initial, mu, weight, frequency_width)
    raw_mapped_flux = _block_flux(mapped, mu, weight, frequency_width)
    raw_boundary = _spectral_l1(raw_flux, raw_mapped_flux)
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
    # 中文：只在预条件器内关闭 Doppler 串扰；正式残差仍使用完整混合系算子。
    static_scattering = lorentz_remap_comoving_group_extinction_to_lab(
        np.broadcast_to(
            fields["scattering"][:, None, :],
            (collision_groups, angle_points, depth_points),
        ),
        block.local_stencil.comoving_collision_edge_hz,
        block.local_stencil.active_lab_edge_hz,
        np.ones_like(transform.doppler_lab_to_comoving),
    )
    lambda_diagonal = step_characteristic_local_lambda_diagonal(
        fields["old_edge"],
        fields["new_edge"],
        mu,
        lab_extinction,
        context["duration_s"],
        propagation_speed_cm_s=phase7b7i.phase7b7e.LIGHT_SPEED_CM_S,
        allow_turning_ray_upwind=True,
    )
    ali = static_diagonal_ali_residual_correction(
        residual,
        mu,
        weight,
        lambda_diagonal.response_cm,
        static_scattering,
        turning_angle_count=lambda_diagonal.turning_angle_count,
        turning_ray_uses_raw_upwind_diagonal=(
            lambda_diagonal.turning_ray_uses_raw_upwind_diagonal
        ),
    )
    direction = np.array(ali.correction, copy=True)
    exact_step = exact_nonnegative_affine_step(initial, direction)
    candidate = initial + exact_step * direction
    precondition_runtime = time.perf_counter() - precondition_started
    minimum_denominator = ali.minimum_scattering_denominator
    maximum_feedback = ali.maximum_scattering_feedback_fraction
    turning_count = ali.turning_angle_count
    lambda_minimum = lambda_diagonal.minimum_response_cm
    lambda_maximum = lambda_diagonal.maximum_response_cm
    del (
        transform,
        extinction_comoving_angle,
        lab_extinction,
        static_scattering,
        lambda_diagonal,
        ali,
        direction,
    )

    fresh_started = time.perf_counter()
    mapped_candidate = source_map(candidate)
    fresh_validation_runtime = time.perf_counter() - fresh_started
    fresh_residual = _relative_update(candidate, mapped_candidate)
    fresh_ratio = fresh_residual / raw_residual
    candidate_flux = _block_flux(candidate, mu, weight, frequency_width)
    mapped_candidate_flux = _block_flux(
        mapped_candidate, mu, weight, frequency_width
    )
    candidate_boundary = _spectral_l1(candidate_flux, mapped_candidate_flux)
    boundary_ratio = (
        candidate_boundary / raw_boundary
        if raw_boundary > 0.0
        else (0.0 if candidate_boundary == 0.0 else math.inf)
    )
    minimum_candidate = float(np.min(candidate))
    wall_runtime = time.perf_counter() - started
    application_runtime = raw_map_runtime + precondition_runtime
    del candidate, mapped_candidate, residual
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
        "minimum_scattering_denominator": minimum_denominator,
        "maximum_scattering_feedback_fraction": maximum_feedback,
        "minimum_lambda_response_cm": lambda_minimum,
        "maximum_lambda_response_cm": lambda_maximum,
        "turning_angle_count": turning_count,
        "turning_ray_uses_raw_upwind_diagonal": turning_count > 0,
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
    _write_json_atomic(report_path, report)


def _plot(
    path: Path,
    reports: list[dict[str, object]],
    gates: dict[str, object],
    *,
    full_map_authorized: bool,
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(13.0, 8.2), constrained_layout=True)
    block = np.asarray([row["block_index"] for row in reports])
    fresh = np.asarray(
        [row["fresh_candidate_to_raw_residual_ratio"] for row in reports]
    )
    boundary = np.asarray(
        [row["fresh_candidate_to_raw_boundary_ratio"] for row in reports]
    )
    width = 0.36
    axes[0, 0].bar(block - width / 2, fresh, width, label="Interior residual")
    axes[0, 0].bar(block + width / 2, boundary, width, label="Boundary spectrum")
    axes[0, 0].axhline(
        gates["each_fresh_candidate_to_raw_residual_ratio_below"],
        color="0.25",
        ls="--",
        label="Interior gate",
    )
    axes[0, 0].set(
        xlabel="Natural frequency block",
        ylabel="ALI candidate / raw residual",
        title="(a) Fresh original-operator validation",
    )
    axes[0, 0].legend(frameon=False, fontsize=8)
    axes[0, 1].semilogy(
        block,
        [row["minimum_scattering_denominator"] for row in reports],
        "o-",
        label="Minimum denominator",
    )
    axes[0, 1].axhline(
        gates["each_minimum_scattering_denominator_strictly_above"],
        color="0.25",
        ls="--",
        label="Positivity gate",
    )
    axes[0, 1].set(
        xlabel="Natural frequency block",
        ylabel="Minimum local scattering denominator",
        title="(b) ALI physical-domain margin",
    )
    axes[0, 1].legend(frameon=False, fontsize=8)
    axes[1, 0].bar(
        block,
        [row["ali_application_runtime_multiplier_over_one_update"] for row in reports],
        color="tab:purple",
    )
    axes[1, 0].axhline(
        gates["selected_runtime_multiplier_over_one_map_below"],
        color="0.25",
        ls="--",
        label="Runtime gate",
    )
    axes[1, 0].set(
        xlabel="Natural frequency block",
        ylabel="ALI application / one Picard update",
        title="(c) Preconditioner cost",
    )
    axes[1, 0].legend(frameon=False, fontsize=8)
    axes[1, 1].axis("off")
    axes[1, 1].text(
        0.03,
        0.95,
        "(d) Static-diagonal ALI decision\n\n"
        f"Worst candidate/raw = {float(np.max(fresh)):.3f}\n"
        f"Median candidate/raw = {float(np.median(fresh)):.3f}\n"
        f"Minimum exact-positive step = "
        f"{min(float(row['exact_nonnegative_step']) for row in reports):.3f}\n\n"
        f"Full-frequency map authorized: {full_map_authorized}\n"
        "Doppler frequency coupling: original operator only\n"
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
        OUTPUT / f"phase7b9o_block{index:02d}_static_diagonal_ali.json"
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
                f"Phase 7B9o worker {block_index} failed: {process.returncode}"
            )
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    reports.sort(key=lambda row: int(row["block_index"]))
    gates = protocol["gates"]
    fresh = np.asarray(
        [row["fresh_candidate_to_raw_residual_ratio"] for row in reports]
    )
    boundary = np.asarray(
        [row["fresh_candidate_to_raw_boundary_ratio"] for row in reports]
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
        "every_exact_nonnegative_step_passes": all(
            row["exact_nonnegative_step"]
            >= gates["each_exact_nonnegative_step_at_least"]
            for row in reports
        ),
        "every_scattering_denominator_passes": all(
            row["minimum_scattering_denominator"]
            > gates["each_minimum_scattering_denominator_strictly_above"]
            for row in reports
        ),
        "every_fresh_original_residual_improves_enough": bool(
            np.all(
                fresh
                < gates["each_fresh_candidate_to_raw_residual_ratio_below"]
            )
        ),
        "median_fresh_original_residual_improves_enough": float(np.median(fresh))
        < gates["median_fresh_candidate_to_raw_residual_ratio_below"],
        "boundary_residuals_do_not_worsen": bool(
            np.all(
                boundary
                <= gates["each_candidate_boundary_residual_ratio_at_most"]
            )
        ),
        "candidates_finite_nonnegative_and_within_memory": all(
            row["minimum_candidate_intensity"]
            >= gates["minimum_candidate_intensity_at_least"]
            and row["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            for row in reports
        ),
        "selected_runtime_multiplier_passes": application_multiplier
        < gates["selected_runtime_multiplier_over_one_map_below"],
        "projected_full_map_cost_passes": projected_wall
        < gates["projected_full_map_wall_time_strictly_below_s"],
    }
    passed = all(checks.values())
    decision = {
        "static_diagonal_ali_pilot_passed": passed,
        "one_full_frequency_static_diagonal_ali_map_authorized": passed,
        "doppler_frequency_coupled_preconditioner_required": not passed,
        "full_frequency_accelerated_map_evaluated": False,
        "trial_formal_feedback_evaluated": False,
        "trial_true_residual_evaluated": False,
        "accepted_as_dynamic_nlte_solution": False,
        "phase7b9o_gate_passed": passed,
    }
    figure = OUTPUT / "phase7b9o_static_diagonal_ali_pilot.png"
    _plot(figure, reports, gates, full_map_authorized=passed)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "reports": reports,
        "maximum_fresh_candidate_to_raw_residual_ratio": float(np.max(fresh)),
        "median_fresh_candidate_to_raw_residual_ratio": float(np.median(fresh)),
        "selected_ali_application_runtime_multiplier_over_one_update": (
            application_multiplier
        ),
        "projected_full_map_wall_time_s": projected_wall,
        "gate_checks": checks,
        "decision": decision,
        "figures": [figure.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9o_static_diagonal_ali_pilot_summary.json", summary
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9o_preregistered_static_diagonal_ali_pilot.json",
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
