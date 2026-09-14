"""Phase 7B9n：代表块多模最小残差组合及新原算子审计。"""

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

from eccentric_tde_observer.affine_krylov import (
    constrained_minimum_residual_coefficients,
    exact_nonnegative_affine_step,
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
    "af54cccbe32a56ed41874cfbf8942a04de015b7d59e1ac7ee8d59715f59535e4"
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
        raise RuntimeError("frozen Phase 7B9n protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or _sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9n source changed: {source['path']}"
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


def _relative_update(first: np.ndarray, second: np.ndarray) -> float:
    scale = max(float(np.max(np.abs(first))), float(np.max(np.abs(second))))
    change = float(np.max(np.abs(second - first)))
    return change / scale if scale > 0.0 else change


def _spectral_l1(first: np.ndarray, second: np.ndarray) -> float:
    scale = max(float(np.sum(np.abs(first))), float(np.sum(np.abs(second))))
    change = float(np.sum(np.abs(second - first)))
    return change / scale if scale > 0.0 else change


def _gram(residuals: list[np.ndarray]) -> np.ndarray:
    size = len(residuals)
    result = np.empty((size, size), dtype=np.float64)
    for row in range(size):
        for column in range(row + 1):
            value = float(
                np.einsum("fmd,fmd->", residuals[row], residuals[column])
            )
            result[row, column] = value
            result[column, row] = value
    return result


def _candidate_direction(
    coefficients: np.ndarray,
    residuals: list[np.ndarray],
    template: np.ndarray,
) -> np.ndarray:
    direction = np.zeros_like(template)
    # 中文：x_i=x_0+sum_{j<i} r_j，故只需保留残差历史而不保留全部状态。
    for index in range(coefficients.size - 1):
        beta = float(np.sum(coefficients[index + 1 :]))
        direction += beta * residuals[index]
    return direction


def _run_worker(protocol_path: Path, block_index: int, report_path: Path) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    selected = {
        int(row["block_index"]): row["role"]
        for row in protocol["configuration"]["selected_blocks"]
    }
    if block_index not in selected:
        raise ValueError("Phase 7B9n worker block is not preregistered")
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
    residuals: list[np.ndarray] = []
    iterate = np.array(initial, copy=True)
    for _ in range(
        int(protocol["configuration"]["source_residual_history_count_exactly"])
    ):
        mapped = source_map(iterate)
        residuals.append(mapped - iterate)
        iterate = mapped
    raw_residual = _relative_update(initial, initial + residuals[0])
    raw_flux = _block_flux(initial, mu, weight, frequency_width)
    raw_mapped_flux = _block_flux(
        initial + residuals[0], mu, weight, frequency_width
    )
    raw_boundary = _spectral_l1(raw_flux, raw_mapped_flux)
    full_gram = _gram(residuals)
    candidate_rows: list[dict[str, object]] = []
    candidate_cache: dict[int, tuple[np.ndarray, np.ndarray, float]] = {}
    for size_value in protocol["configuration"]["candidate_subspace_sizes"]:
        size = int(size_value)
        row: dict[str, object] = {"subspace_size": size}
        try:
            combination = constrained_minimum_residual_coefficients(
                full_gram[:size, :size],
                maximum_normalized_condition=float(
                    protocol["configuration"]["maximum_normalized_gram_condition"]
                ),
            )
            direction = _candidate_direction(
                combination.coefficients, residuals[:size], initial
            )
            step = exact_nonnegative_affine_step(initial, direction)
            candidate = initial + step * direction
            combined_residual = np.zeros_like(initial)
            for coefficient, residual in zip(
                combination.coefficients, residuals[:size], strict=True
            ):
                combined_residual += float(coefficient) * residual
            predicted = (1.0 - step) * residuals[0] + step * combined_residual
            predicted_ratio = float(
                np.max(np.abs(predicted)) / np.max(np.abs(residuals[0]))
            )
            row.update(
                {
                    "feasible": True,
                    "normalized_gram_condition": combination.normalized_gram_condition,
                    "coefficient_sum_error": combination.coefficient_sum_error,
                    "coefficients": combination.coefficients.tolist(),
                    "exact_nonnegative_step": step,
                    "minimum_candidate_intensity": float(np.min(candidate)),
                    "predicted_candidate_to_raw_linf_ratio": predicted_ratio,
                    "failure": None,
                }
            )
            candidate_cache[size] = (candidate, predicted, step)
            del direction, combined_residual
        except (PhysicalDomainError, ArithmeticError, np.linalg.LinAlgError) as error:
            row.update(
                {
                    "feasible": False,
                    "failure": str(error),
                }
            )
        candidate_rows.append(row)
    feasible = [row for row in candidate_rows if row["feasible"]]
    if feasible:
        selected_row = min(
            feasible,
            key=lambda row: (
                float(row["predicted_candidate_to_raw_linf_ratio"]),
                int(row["subspace_size"]),
            ),
        )
        selected_size = int(selected_row["subspace_size"])
        candidate, predicted, selected_step = candidate_cache[selected_size]
        mapped_candidate = source_map(candidate)
        fresh = mapped_candidate - candidate
        fresh_residual = _relative_update(candidate, mapped_candidate)
        fresh_ratio = fresh_residual / raw_residual
        prediction_error = float(
            np.max(np.abs(fresh - predicted))
            / max(float(np.max(np.abs(fresh))), float(np.max(np.abs(predicted))))
        )
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
    else:
        selected_size = None
        selected_step = None
        fresh_residual = None
        fresh_ratio = None
        prediction_error = None
        candidate_boundary = None
        boundary_ratio = None
        minimum_candidate = None
    wall_runtime = time.perf_counter() - started
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
        "raw_original_operator_residual": raw_residual,
        "raw_boundary_spectrum_l1": raw_boundary,
        "candidate_subspaces": candidate_rows,
        "selected_subspace_size": selected_size,
        "selected_exact_nonnegative_step": selected_step,
        "minimum_selected_candidate_intensity": minimum_candidate,
        "fresh_candidate_original_operator_residual": fresh_residual,
        "fresh_candidate_to_raw_residual_ratio": fresh_ratio,
        "prediction_to_fresh_residual_linf": prediction_error,
        "fresh_candidate_boundary_spectrum_l1": candidate_boundary,
        "fresh_candidate_to_raw_boundary_ratio": boundary_ratio,
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
    gates: dict[str, object],
    *,
    full_map_authorized: bool,
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(13.0, 8.2), constrained_layout=True)
    for report in reports:
        rows = report["candidate_subspaces"]
        feasible = [row for row in rows if row["feasible"]]
        axes[0, 0].semilogy(
            [row["subspace_size"] for row in feasible],
            [row["normalized_gram_condition"] for row in feasible],
            "o-",
            label=f"B{report['block_index']}",
        )
        axes[0, 1].semilogy(
            [row["subspace_size"] for row in feasible],
            [row["predicted_candidate_to_raw_linf_ratio"] for row in feasible],
            "o-",
            label=f"B{report['block_index']}",
        )
    axes[0, 0].axhline(
        1.0e12, color="0.25", ls="--", label="Condition gate"
    )
    axes[0, 0].set(
        xlabel="Residual subspace size",
        ylabel="Normalized Gram condition",
        title="(a) Multimode subspace conditioning",
    )
    axes[0, 0].set_xticks([3, 5, 7])
    axes[0, 0].legend(frameon=False)
    axes[0, 1].set(
        xlabel="Residual subspace size",
        ylabel="Predicted candidate / raw residual",
        title="(b) Reduced-model prediction",
    )
    axes[0, 1].set_xticks([3, 5, 7])
    axes[0, 1].legend(frameon=False)
    block = np.asarray([row["block_index"] for row in reports])
    fresh = np.asarray(
        [
            np.nan
            if row["fresh_candidate_to_raw_residual_ratio"] is None
            else row["fresh_candidate_to_raw_residual_ratio"]
            for row in reports
        ]
    )
    boundary = np.asarray(
        [
            np.nan
            if row["fresh_candidate_to_raw_boundary_ratio"] is None
            else row["fresh_candidate_to_raw_boundary_ratio"]
            for row in reports
        ]
    )
    width = 0.36
    axes[1, 0].bar(block - width / 2, fresh, width=width, label="Interior residual")
    axes[1, 0].bar(block + width / 2, boundary, width=width, label="Boundary spectrum")
    axes[1, 0].axhline(
        gates["each_fresh_candidate_to_raw_residual_ratio_below"],
        color="0.25",
        ls="--",
        label="Interior gate",
    )
    axes[1, 0].set(
        xlabel="Natural frequency block",
        ylabel="Fresh candidate / raw residual",
        title="(c) Original-operator validation",
    )
    axes[1, 0].legend(frameon=False, fontsize=8)
    axes[1, 1].axis("off")
    finite = fresh[np.isfinite(fresh)]
    axes[1, 1].text(
        0.03,
        0.95,
        "(d) Multimode decision\n\n"
        f"Validated candidates = {finite.size}/{len(reports)}\n"
        f"Worst candidate/raw = {float(np.max(finite)) if finite.size else math.nan:.3f}\n"
        f"Median candidate/raw = {float(np.median(finite)) if finite.size else math.nan:.3f}\n\n"
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
        OUTPUT / f"phase7b9n_block{index:02d}_multimode.json" for index in selected
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
                f"Phase 7B9n worker {block_index} failed: {process.returncode}"
            )
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    reports.sort(key=lambda row: int(row["block_index"]))
    gates = protocol["gates"]
    selected_reports = [
        row for row in reports if row["selected_subspace_size"] is not None
    ]
    fresh = np.asarray(
        [row["fresh_candidate_to_raw_residual_ratio"] for row in selected_reports]
    )
    boundary = np.asarray(
        [row["fresh_candidate_to_raw_boundary_ratio"] for row in selected_reports]
    )
    runtime_multiplier = float(
        sum(row["wall_runtime_s"] for row in reports)
        / sum(row["historical_one_update_runtime_s"] for row in reports)
    )
    prior = json.loads(
        (ROOT / protocol["sources"]["phase7b9m_summary"]["path"]).read_text(
            encoding="utf-8"
        )
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
        "every_selected_subspace_exists": len(selected_reports) == len(reports),
        "every_exact_nonnegative_step_passes": len(selected_reports) == len(reports)
        and all(
            row["selected_exact_nonnegative_step"]
            >= gates["each_exact_nonnegative_step_at_least"]
            for row in selected_reports
        ),
        "every_fresh_original_residual_improves_enough": len(fresh) == len(reports)
        and bool(
            np.all(
                fresh
                < gates["each_fresh_candidate_to_raw_residual_ratio_below"]
            )
        ),
        "median_fresh_original_residual_improves_enough": len(fresh) == len(reports)
        and float(np.median(fresh))
        < gates["median_fresh_candidate_to_raw_residual_ratio_below"],
        "affine_prediction_is_faithful": len(selected_reports) == len(reports)
        and all(
            row["prediction_to_fresh_residual_linf"]
            < gates["each_prediction_to_fresh_residual_linf_below"]
            for row in selected_reports
        ),
        "boundary_residuals_do_not_worsen": len(boundary) == len(reports)
        and bool(
            np.all(
                boundary
                <= gates["each_candidate_boundary_residual_ratio_at_most"]
            )
        ),
        "candidates_finite_nonnegative_and_within_memory": len(selected_reports)
        == len(reports)
        and all(
            row["minimum_selected_candidate_intensity"]
            >= gates["minimum_candidate_intensity_at_least"]
            and row["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            for row in selected_reports
        ),
        "selected_runtime_multiplier_passes": runtime_multiplier
        < gates["selected_runtime_multiplier_over_one_map_below"],
        "projected_full_map_cost_passes": projected_wall
        < gates["projected_full_map_wall_time_strictly_below_s"],
    }
    passed = all(checks.values())
    decision = {
        "multimode_minimum_residual_pilot_passed": passed,
        "one_full_frequency_multimode_map_authorized": passed,
        "any_scalar_acceleration_authorized": False,
        "full_frequency_accelerated_map_evaluated": False,
        "trial_inner_radiation_converged": False,
        "trial_formal_feedback_evaluated": False,
        "trial_true_residual_evaluated": False,
        "trial_rejected_by_physical_residual": False,
        "accepted_as_dynamic_nlte_solution": False,
        "phase7b9n_gate_passed": passed,
    }
    figure = OUTPUT / "phase7b9n_multimode_krylov_pilot.png"
    _plot(figure, reports, gates, full_map_authorized=passed)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "reports": reports,
        "validated_candidate_count": len(selected_reports),
        "maximum_fresh_candidate_to_raw_residual_ratio": (
            float(np.max(fresh)) if fresh.size else None
        ),
        "median_fresh_candidate_to_raw_residual_ratio": (
            float(np.median(fresh)) if fresh.size else None
        ),
        "selected_runtime_multiplier_over_one_update": runtime_multiplier,
        "projected_full_map_wall_time_s": projected_wall,
        "gate_checks": checks,
        "decision": decision,
        "figures": [figure.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9n_multimode_krylov_pilot_summary.json", summary
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9n_preregistered_multimode_krylov_pilot.json",
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
