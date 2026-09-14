"""Phase 7B9v：正性保持的 Picard 历史凸组合试验。"""

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
import tempfile
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.affine_krylov import (
    positive_simplex_minimum_residual_coefficients,
)

try:
    from scripts import phase7b9r_full_source_krylov_line_search as previous
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9r_full_source_krylov_line_search as previous  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
WORK = OUTPUT / "checkpoints/phase7b9i_work"
EXPECTED_PROTOCOL_SHA256 = (
    "d01e5f5a4363fc065e02880201d41e05ca7ecb0770676e9fc8c32a8cd14d6a21"
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
        raise RuntimeError("frozen Phase 7B9v protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9v source changed: {source['path']}"
                )
    return protocol


def _temporary_memmap(
    shape: tuple[int, ...], prefix: str
) -> tuple[Path, np.memmap]:
    descriptor, name = tempfile.mkstemp(prefix=prefix, suffix=".dat", dir=WORK)
    os.close(descriptor)
    path = Path(name)
    expected = int(np.prod(shape, dtype=np.int64)) * np.dtype(np.float64).itemsize
    with path.open("r+b") as stream:
        stream.truncate(expected)
    return path, np.memmap(path, mode="r+", dtype=np.float64, shape=shape)


def _residual_gram_chunked(
    residual: np.memmap, *, chunk_size: int = 131_072
) -> tuple[np.ndarray | None, float]:
    count = residual.shape[0]
    flattened = residual.reshape(count, -1)
    common_scale = 0.0
    for start in range(0, flattened.shape[1], chunk_size):
        stop = min(start + chunk_size, flattened.shape[1])
        common_scale = max(
            common_scale, float(np.max(np.abs(flattened[:, start:stop])))
        )
    if not np.isfinite(common_scale):
        raise ArithmeticError("Picard residual history scale became non-finite")
    if common_scale == 0.0:
        return None, 0.0
    gram = np.zeros((count, count), dtype=np.float64)
    for start in range(0, flattened.shape[1], chunk_size):
        stop = min(start + chunk_size, flattened.shape[1])
        # 中文：只除以一个公共尺度，避免高能尾部平方下溢且不改变凸优化解。
        block = np.asarray(flattened[:, start:stop]) / common_scale
        gram += block @ block.T
    return 0.5 * (gram + gram.T), common_scale


def _run_worker(
    protocol_path: Path, block_index: int, report_path: Path
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    selected = {
        int(row["block_index"]): row["role"]
        for row in protocol["configuration"]["selected_blocks"]
    }
    if block_index not in selected:
        raise ValueError("Phase 7B9v worker block is not preregistered")
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

    history_count = int(protocol["configuration"]["picard_residual_history_count"])
    state_path, states = _temporary_memmap(
        (history_count + 1, *initial.shape),
        f".phase7b9v_block{block_index:02d}_state_",
    )
    residual_path, residuals = _temporary_memmap(
        (history_count, *initial.shape),
        f".phase7b9v_block{block_index:02d}_residual_",
    )
    baseline_rss = base.ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    try:
        states[0] = initial
        states.flush()
        minimum_history_intensity = float(np.min(initial))
        iteration_rows: list[dict[str, object]] = []
        for index in range(history_count):
            mapped = source_map(np.asarray(states[index]))
            if not np.all(np.isfinite(mapped)) or np.any(mapped < 0.0):
                raise ArithmeticError("positive Picard source map left its physical domain")
            residuals[index] = mapped - np.asarray(states[index])
            states[index + 1] = mapped
            minimum_history_intensity = min(
                minimum_history_intensity, float(np.min(mapped))
            )
            iteration_rows.append(
                {
                    "iteration": index + 1,
                    "source_map_residual": base._relative_update(
                        np.asarray(states[index]), mapped
                    ),
                    "minimum_mapped_intensity": float(np.min(mapped)),
                }
            )
            del mapped
        states.flush()
        residuals.flush()
        gram, residual_common_scale = _residual_gram_chunked(residuals)
        if gram is None:
            # 中文：全零残差是已解析的固定点，保持原状态，不注入人工尺度。
            coefficients = np.zeros(history_count, dtype=np.float64)
            coefficients[0] = 1.0
            predicted_squared_norm = 0.0
            best_input_squared_norm = 0.0
            active_coefficient_count = 1
            optimizer_iteration_count = 0
            maximum_active_gradient_spread = 0.0
            minimum_inactive_gradient_margin = 0.0
        else:
            combination = positive_simplex_minimum_residual_coefficients(
                gram,
                optimizer_tolerance=protocol["configuration"][
                    "simplex_optimizer_tolerance"
                ],
                maximum_iterations=protocol["configuration"][
                    "simplex_optimizer_maximum_iterations"
                ],
            )
            coefficients = combination.coefficients
            predicted_squared_norm = combination.predicted_squared_norm
            best_input_squared_norm = combination.best_input_squared_norm
            active_coefficient_count = combination.active_coefficient_count
            optimizer_iteration_count = combination.optimizer_iteration_count
            maximum_active_gradient_spread = (
                combination.maximum_active_gradient_spread
            )
            minimum_inactive_gradient_margin = (
                combination.minimum_inactive_gradient_margin
            )
        candidate = np.zeros_like(initial)
        predicted_residual = np.zeros_like(initial)
        for index, coefficient in enumerate(coefficients):
            if coefficient > 0.0:
                candidate += coefficient * np.asarray(states[index])
                predicted_residual += coefficient * np.asarray(residuals[index])
        if not np.all(np.isfinite(candidate)) or np.any(candidate < 0.0):
            raise ArithmeticError("positive convex candidate left its physical domain")
        mapped_candidate = source_map(candidate)
        fresh_vector = mapped_candidate - candidate
        raw_residual = base._relative_update(
            np.asarray(states[0]), np.asarray(states[1])
        )
        fresh_residual = base._relative_update(candidate, mapped_candidate)
        residual_ratio = (
            fresh_residual / raw_residual
            if raw_residual > 0.0
            else (0.0 if fresh_residual == 0.0 else float("inf"))
        )
        raw_flux = base._block_flux(
            np.asarray(states[0]), mu, weight, frequency_width
        )
        raw_mapped_flux = base._block_flux(
            np.asarray(states[1]), mu, weight, frequency_width
        )
        candidate_flux = base._block_flux(candidate, mu, weight, frequency_width)
        mapped_candidate_flux = base._block_flux(
            mapped_candidate, mu, weight, frequency_width
        )
        raw_boundary = base._spectral_l1(raw_flux, raw_mapped_flux)
        fresh_boundary = base._spectral_l1(candidate_flux, mapped_candidate_flux)
        residual_scale = max(
            float(np.max(np.abs(fresh_vector))),
            float(np.max(np.abs(predicted_residual))),
        )
        state_scale = max(
            float(np.max(np.abs(candidate))),
            float(np.max(np.abs(mapped_candidate))),
        )
        prediction_difference = float(
            np.max(np.abs(fresh_vector - predicted_residual))
        )
        peak_rss = base.ru_maxrss_to_bytes(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
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
            "picard_residual_history_count": history_count,
            "raw_original_operator_residual": raw_residual,
            "fresh_candidate_original_operator_residual": fresh_residual,
            "fresh_candidate_to_raw_residual_ratio": residual_ratio,
            "raw_boundary_spectrum_l1": raw_boundary,
            "fresh_candidate_boundary_spectrum_l1": fresh_boundary,
            "fresh_candidate_to_raw_boundary_ratio": (
                fresh_boundary / raw_boundary
                if raw_boundary > 0.0
                else (0.0 if fresh_boundary == 0.0 else float("inf"))
            ),
            "minimum_history_intensity": minimum_history_intensity,
            "minimum_candidate_intensity": float(np.min(candidate)),
            "minimum_simplex_coefficient": float(
                np.min(coefficients)
            ),
            "maximum_simplex_coefficient": float(
                np.max(coefficients)
            ),
            "simplex_coefficients": coefficients.tolist(),
            "simplex_coefficient_sum_error": abs(
                float(np.sum(coefficients)) - 1.0
            ),
            "simplex_active_coefficient_count": active_coefficient_count,
            "simplex_optimizer_iteration_count": optimizer_iteration_count,
            "simplex_predicted_squared_residual_norm": predicted_squared_norm,
            "simplex_best_input_squared_residual_norm": best_input_squared_norm,
            "simplex_maximum_active_gradient_spread": (
                maximum_active_gradient_spread
            ),
            "simplex_minimum_inactive_gradient_margin": (
                minimum_inactive_gradient_margin
            ),
            "residual_gram_common_scale": residual_common_scale,
            "affine_prediction_to_fresh_residual_linf": (
                prediction_difference / residual_scale
                if residual_scale > 0.0
                else prediction_difference
            ),
            "affine_prediction_defect_to_physical_state_linf": (
                prediction_difference / state_scale
                if state_scale > 0.0
                else prediction_difference
            ),
            "baseline_highwater_rss_mib": baseline_rss / MIB,
            "peak_process_rss_mib": peak_rss / MIB,
            "wall_runtime_s": time.perf_counter() - started,
            "iteration_history": iteration_rows,
        }
        _write_json_atomic(report_path, report)
    finally:
        del states, residuals
        gc.collect()
        state_path.unlink(missing_ok=True)
        residual_path.unlink(missing_ok=True)


def _plot(
    path: Path,
    reports: list[dict[str, object]],
    gates: dict[str, object],
    *,
    passed: bool,
) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(14.2, 4.5), constrained_layout=True)
    block = np.asarray([row["block_index"] for row in reports])
    ratio = np.asarray(
        [row["fresh_candidate_to_raw_residual_ratio"] for row in reports]
    )
    axes[0].bar(block, ratio, color="tab:blue")
    axes[0].axhline(
        gates["each_fresh_candidate_to_raw_residual_ratio_below"],
        color="0.25",
        ls="--",
        label="Residual gate",
    )
    axes[0].set(
        xlabel="Natural frequency block",
        ylabel="Candidate / raw residual",
        title="(a) Positive convex residual gate",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].plot(
        block,
        [row["simplex_active_coefficient_count"] for row in reports],
        "o-",
        label="Active history states",
    )
    axes[1].set(
        xlabel="Natural frequency block",
        ylabel="Count",
        title="(b) Convex history usage",
    )
    axes[1].legend(frameon=False, fontsize=8)
    axes[2].axis("off")
    axes[2].text(
        0.03,
        0.95,
        "(c) Pilot decision\n\n"
        f"Blocks = {len(reports)}\n"
        f"Worst residual ratio = {float(np.max(ratio)):.4f}\n"
        f"Minimum intensity = "
        f"{min(float(row['minimum_candidate_intensity']) for row in reports):.3e}\n"
        f"Peak RSS = "
        f"{max(float(row['peak_process_rss_mib']) for row in reports):.1f} MiB\n\n"
        f"Pilot passed: {passed}\n"
        "Cellwise clipping: false",
        transform=axes[2].transAxes,
        va="top",
        fontsize=10.5,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(
    protocol_path: Path, *, assemble_only: bool = False
) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    reports: list[dict[str, object]] = []
    report_directory = WORK / "reports_phase7b9v"
    report_directory.mkdir(parents=True, exist_ok=True)
    for selected in protocol["configuration"]["selected_blocks"]:
        block_index = int(selected["block_index"])
        report_path = report_directory / f"phase7b9v_block{block_index:02d}.json"
        if not assemble_only:
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
                    f"Phase 7B9v worker {block_index} failed: {process.returncode}"
                )
        elif not report_path.exists():
            raise RuntimeError(
                f"Phase 7B9v assemble-only report missing for block {block_index}"
            )
        row = json.loads(report_path.read_text(encoding="utf-8"))
        if (
            int(row["block_index"]) != block_index
            or int(row["picard_residual_history_count"])
            != int(protocol["configuration"]["picard_residual_history_count"])
        ):
            raise RuntimeError("Phase 7B9v worker report identity changed")
        reports.append(row)
        print(
            json.dumps(
                {
                    "completed_blocks": len(reports),
                    "total_blocks": len(protocol["configuration"]["selected_blocks"]),
                    "latest_block": block_index,
                    "latest_residual_ratio": row[
                        "fresh_candidate_to_raw_residual_ratio"
                    ],
                }
            ),
            flush=True,
        )
    gates = protocol["gates"]
    checks = {
        "selected_block_count_pass": len(reports)
        == gates["selected_block_count_exactly"],
        "all_picard_history_states_are_nonnegative": all(
            row["minimum_history_intensity"]
            >= gates["minimum_history_intensity_at_least"]
            for row in reports
        ),
        "all_convex_candidates_are_nonnegative": all(
            row["minimum_candidate_intensity"]
            >= gates["minimum_candidate_intensity_at_least"]
            for row in reports
        ),
        "simplex_constraints_pass": all(
            row["minimum_simplex_coefficient"]
            >= gates["minimum_simplex_coefficient_at_least"]
            and row["simplex_coefficient_sum_error"]
            < gates["simplex_coefficient_sum_error_below"]
            for row in reports
        ),
        "fresh_original_operator_residuals_pass": all(
            row["fresh_candidate_to_raw_residual_ratio"]
            < gates["each_fresh_candidate_to_raw_residual_ratio_below"]
            for row in reports
        ),
        "boundary_residuals_do_not_worsen": all(
            row["fresh_candidate_to_raw_boundary_ratio"]
            <= gates["each_fresh_candidate_boundary_ratio_at_most"]
            for row in reports
        ),
        "affine_prediction_is_resolved_on_physical_scale": all(
            row["affine_prediction_defect_to_physical_state_linf"]
            < gates["each_affine_prediction_defect_to_physical_state_linf_below"]
            for row in reports
        ),
        "resources_pass": all(
            row["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and row["wall_runtime_s"]
            < gates["each_worker_wall_time_strictly_below_s"]
            for row in reports
        ),
    }
    passed = all(checks.values())
    figure = OUTPUT / "phase7b9v_positive_convex_picard_pilot.png"
    _plot(figure, reports, gates, passed=passed)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "runner_sha256_at_assembly": base._sha256(Path(__file__).resolve()),
        "selected_blocks": [row["block_index"] for row in reports],
        "maximum_fresh_candidate_to_raw_residual_ratio": max(
            row["fresh_candidate_to_raw_residual_ratio"] for row in reports
        ),
        "minimum_candidate_intensity": min(
            row["minimum_candidate_intensity"] for row in reports
        ),
        "maximum_peak_process_rss_mib": max(
            row["peak_process_rss_mib"] for row in reports
        ),
        "gate_checks": checks,
        "decision": {
            "positive_convex_picard_pilot_passed": passed,
            "repair_unresolved_phase7b9t_blocks_authorized": passed,
            "global_candidate_residual_authorized": False,
            "material_feedback_authorized": False,
        },
        "reports": reports,
        "figures": [figure.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9v_positive_convex_picard_pilot_summary.json", summary
    )
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9v_preregistered_positive_convex_picard_pilot.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--assemble-only", action="store_true")
    args = parser.parse_args()
    if args.worker:
        if args.block_index is None or args.worker_report is None:
            raise ValueError("worker mode requires block index and report path")
        _run_worker(args.protocol, args.block_index, args.worker_report)
        return
    run(args.protocol, assemble_only=args.assemble_only)


if __name__ == "__main__":
    main()
