"""Phase 7B5k：高分辨率相邻收敛与返回数组资源审计。"""

from __future__ import annotations

import argparse
import csv
from dataclasses import fields, is_dataclass
import json
import os
from pathlib import Path
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.mixed_frame_ale import mixed_frame_frequency_stencil
from eccentric_tde_observer.radiative_transfer_1d import gauss_legendre_mu_weights

try:
    from scripts.phase7b5a_log_frequency_p1_gate import (
        CONTROL_ANGULAR_ORDER,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _actual_case_definitions,
        _collision_physical_slice,
        _load_material_reference,
        _p0_actual_one_cell_run,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from scripts.phase7b5c_signed_rate_error_localization import (
        LOCALIZATION_QUADRATURE_TARGET,
        _analysis_edges,
    )
    from scripts.phase7b5f_single_pass_intensity_transform import (
        _state_parameters,
    )
    from scripts.phase7b5i_partition_representation_split import (
        CAPTURE_ITERATIONS,
        INPUT_ITERATIONS,
        PROJECTION_ENERGY_TARGET,
        _one_p0_map,
        _project_p0_state,
        _relative_difference,
    )
    from scripts.phase7b5j_prescribed_partition_audit import (
        EFFICIENCY_GROUP_LIMIT,
        H_I_RATE_TARGET,
        LOCALIZATION_QUADRATURE_ORDERS,
        _p0_rate_comparison,
        _strategy_stencil,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5a_log_frequency_p1_gate import (  # type: ignore[no-redef]
        CONTROL_ANGULAR_ORDER,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _actual_case_definitions,
        _collision_physical_slice,
        _load_material_reference,
        _p0_actual_one_cell_run,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from phase7b5c_signed_rate_error_localization import (  # type: ignore[no-redef]
        LOCALIZATION_QUADRATURE_TARGET,
        _analysis_edges,
    )
    from phase7b5f_single_pass_intensity_transform import (  # type: ignore[no-redef]
        _state_parameters,
    )
    from phase7b5i_partition_representation_split import (  # type: ignore[no-redef]
        CAPTURE_ITERATIONS,
        INPUT_ITERATIONS,
        PROJECTION_ENERGY_TARGET,
        _one_p0_map,
        _project_p0_state,
        _relative_difference,
    )
    from phase7b5j_prescribed_partition_audit import (  # type: ignore[no-redef]
        EFFICIENCY_GROUP_LIMIT,
        H_I_RATE_TARGET,
        LOCALIZATION_QUADRATURE_ORDERS,
        _p0_rate_comparison,
        _strategy_stencil,
    )


GROUP_COUNTS = (9632, 19264)
STRATEGIES = ("rate_kernel", "doppler_image_anchors")
N128_DEPTH_CELLS = 128
MIB_BYTES = 1024**2
GIB_BYTES = 1024**3


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    fields_out: list[str] = []
    for row in rows:
        fields_out.extend(key for key in row if key not in fields_out)
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields_out)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _returned_array_bytes(result) -> int:
    """统计返回 dataclass 直接持有的唯一数组；不估计内部瞬时峰值。"""
    if not is_dataclass(result):
        raise TypeError("result must be a dataclass instance")
    seen: set[int] = set()
    total = 0
    for field in fields(result):
        value = getattr(result, field.name)
        if isinstance(value, np.ndarray) and id(value) not in seen:
            seen.add(id(value))
            total += int(value.nbytes)
    return total


def _plot_high_resolution_convergence(path: Path, rows) -> None:
    cases = ("maximum cell speed", "maximum width change")
    checkpoints = (0, 8)
    colors = {
        "rate_kernel": "tab:orange",
        "doppler_image_anchors": "tab:green",
    }
    labels = {
        "rate_kernel": "fixed rate-kernel",
        "doppler_image_anchors": "Doppler-image anchors",
    }
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.4), constrained_layout=True)
    for row_index, case in enumerate(cases):
        for column, iteration in enumerate(checkpoints):
            axis = axes[row_index, column]
            for strategy in STRATEGIES:
                selected = sorted(
                    (
                        row
                        for row in rows
                        if row["case"] == case
                        and row["input_iteration"] == iteration
                        and row["strategy"] == strategy
                    ),
                    key=lambda row: row["physical_frequency_groups"],
                )
                axis.semilogy(
                    [row["physical_frequency_groups"] for row in selected],
                    [row["absolute_H_I_rate_error"] for row in selected],
                    marker="o",
                    color=colors[strategy],
                    label=labels[strategy],
                )
            axis.axhline(H_I_RATE_TARGET, color="black", linestyle=":")
            axis.set_xticks(GROUP_COUNTS, [str(value) for value in GROUP_COUNTS])
            axis.set_xlabel("P0 physical frequency groups")
            axis.set_ylabel("Absolute H I rate error")
            axis.set_title(f"{case}\ninput iteration {iteration}")
            axis.grid(alpha=0.25, which="both")
    axes[0, 0].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_checkpoint_errors(path: Path, rows) -> None:
    cases = tuple(dict.fromkeys(row["case"] for row in rows))
    x = np.arange(len(INPUT_ITERATIONS))
    colors = {
        "rate_kernel": "tab:orange",
        "doppler_image_anchors": "tab:green",
    }
    markers = {9632: "o", 19264: "s"}
    labels = {
        "rate_kernel": "fixed rate-kernel",
        "doppler_image_anchors": "Doppler-image anchors",
    }
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.8), constrained_layout=True)
    for axis, case in zip(axes, cases, strict=True):
        for strategy in STRATEGIES:
            for groups in GROUP_COUNTS:
                selected = [
                    row
                    for row in rows
                    if row["case"] == case
                    and row["strategy"] == strategy
                    and row["physical_frequency_groups"] == groups
                ]
                axis.plot(
                    x,
                    [row["absolute_H_I_rate_error"] for row in selected],
                    color=colors[strategy],
                    marker=markers[groups],
                    linestyle="-" if groups == 19264 else "--",
                    label=(
                        f"{labels[strategy]}, {groups}"
                        if case == cases[0]
                        else None
                    ),
                )
        axis.axhline(H_I_RATE_TARGET, color="black", linestyle=":")
        axis.set_yscale("log")
        axis.set_xticks(x, INPUT_ITERATIONS)
        axis.set_xlabel("Input source-iteration index")
        axis.set_ylabel("Absolute H I rate error")
        axis.set_title(case)
        axis.grid(alpha=0.25, which="both")
    axes[0].legend(fontsize=7)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_resources(path: Path, aggregate_rows) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.8), constrained_layout=True)
    colors = {
        "rate_kernel": "tab:orange",
        "doppler_image_anchors": "tab:green",
    }
    labels = {
        "rate_kernel": "fixed rate-kernel",
        "doppler_image_anchors": "Doppler-image anchors",
    }
    for strategy in STRATEGIES:
        selected = sorted(
            (row for row in aggregate_rows if row["strategy"] == strategy),
            key=lambda row: row["physical_frequency_groups"],
        )
        axes[0].plot(
            [row["physical_frequency_groups"] for row in selected],
            [row["median_solve_runtime_s"] for row in selected],
            marker="o",
            color=colors[strategy],
            label=labels[strategy],
        )
        axes[1].plot(
            [row["physical_frequency_groups"] for row in selected],
            [row["returned_array_footprint_mib"] for row in selected],
            marker="o",
            color=colors[strategy],
            label=labels[strategy],
        )
    for axis in axes:
        axis.set_xticks(GROUP_COUNTS, [str(value) for value in GROUP_COUNTS])
        axis.set_xlabel("P0 physical frequency groups")
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("Median one-cell solve time (s)")
    axes[0].set_title("Measured one-cell runtime")
    axes[1].set_ylabel("Returned-array footprint (MiB)")
    axes[1].set_title("Direct result arrays, not peak memory")
    axes[0].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5k_summary.json",
        "states": output_dir / "phase7b5k_high_resolution_states.csv",
        "resources": output_dir / "phase7b5k_resource_costs.csv",
        "convergence_plot": output_dir / "phase7b5k_high_resolution_convergence.png",
        "checkpoint_plot": output_dir / "phase7b5k_checkpoint_errors.png",
        "resource_plot": output_dir / "phase7b5k_resource_scaling.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    audit = _trajectory_velocity_audit(material, full)
    maximum_beta = float(audit["maximum_velocity_beta"])
    analysis_edge, doppler_factor = _analysis_edges(maximum_beta)
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    reference_stencil = mixed_frame_frequency_stencil(
        *PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        maximum_beta,
    )
    stencils = {
        (strategy, groups): _strategy_stencil(
            strategy, groups, maximum_beta, mu
        )[0]
        for strategy in STRATEGIES
        for groups in GROUP_COUNTS
    }
    rows: list[dict[str, object]] = []
    resource_rows: list[dict[str, object]] = []

    for definition in _actual_case_definitions(material, full, audit):
        case = str(definition["case"])
        reference_states: dict[int, np.ndarray] = {}

        def observe_reference(iteration, intensity):
            if iteration in CAPTURE_ITERATIONS:
                reference_states[iteration] = np.array(intensity, copy=True)

        _p0_actual_one_cell_run(
            material,
            full,
            audit,
            definition,
            REFERENCE_P0_GROUPS_PER_DECADE,
            iteration_observer=observe_reference,
        )
        state = _state_parameters(material, full, definition)
        phase = int(definition["phase_index"])
        following = int(definition["following_phase_index"])
        depth = int(definition["full_depth_index"])
        state["duration_s"] = float(material["step_duration_s"][phase])
        old_edge = full["edges_cm"][phase, depth : depth + 2]
        new_edge = full["edges_cm"][following, depth : depth + 2]
        reference_next = {
            iteration: _one_p0_map(
                reference_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                state,
                reference_states[iteration],
            )
            for iteration in INPUT_ITERATIONS
        }

        for strategy in STRATEGIES:
            for groups in GROUP_COUNTS:
                stencil = stencils[(strategy, groups)]
                for iteration in INPUT_ITERATIONS:
                    projection_started = time.perf_counter()
                    source, projection_error = _project_p0_state(
                        reference_stencil.active_lab_edge_hz,
                        stencil.active_lab_edge_hz,
                        reference_states[iteration],
                    )
                    projection_runtime = time.perf_counter() - projection_started
                    solve_started = time.perf_counter()
                    candidate_next = _one_p0_map(
                        stencil,
                        old_edge,
                        new_edge,
                        mu,
                        weight,
                        state,
                        source,
                    )
                    solve_runtime = time.perf_counter() - solve_started
                    candidate_physical = _collision_physical_slice(stencil)
                    reference_physical = _collision_physical_slice(reference_stencil)
                    comparisons = [
                        _p0_rate_comparison(
                            stencil.active_lab_edge_hz,
                            candidate_next.final_comoving_mean_intensity_density[
                                candidate_physical, 0
                            ],
                            reference_stencil.active_lab_edge_hz,
                            reference_next[
                                iteration
                            ].final_comoving_mean_intensity_density[
                                reference_physical, 0
                            ],
                            analysis_edge,
                            order,
                        )
                        for order in LOCALIZATION_QUADRATURE_ORDERS
                    ]
                    low, high = comparisons
                    quadrature_error = max(
                        _relative_difference(low[name], high[name])
                        for name in (
                            "candidate_total_rate_s1",
                            "reference_total_rate_s1",
                        )
                    )
                    returned_bytes = _returned_array_bytes(candidate_next)
                    rows.append(
                        {
                            "case": case,
                            "input_iteration": iteration,
                            "output_iteration": iteration + 1,
                            "strategy": strategy,
                            "physical_frequency_groups": groups,
                            "signed_H_I_rate_error": high["signed_relative_error"],
                            "absolute_H_I_rate_error": abs(
                                high["signed_relative_error"]
                            ),
                            "projection_energy_error": projection_error,
                            "localization_quadrature_relative_error": quadrature_error,
                            "reference_one_step_reproduced_exactly": np.array_equal(
                                reference_next[
                                    iteration
                                ].final_lab_intensity_density,
                                reference_states[iteration + 1],
                            ),
                            "fixed_point_converged": (
                                candidate_next.fixed_point_converged
                            ),
                        }
                    )
                    resource_rows.append(
                        {
                            "case": case,
                            "input_iteration": iteration,
                            "strategy": strategy,
                            "physical_frequency_groups": groups,
                            "projection_runtime_s": projection_runtime,
                            "one_cell_solve_runtime_s": solve_runtime,
                            "projection_plus_solve_runtime_s": (
                                projection_runtime + solve_runtime
                            ),
                            "returned_array_footprint_bytes": returned_bytes,
                            "returned_array_footprint_mib": (
                                returned_bytes / MIB_BYTES
                            ),
                            "N128_linear_returned_array_estimate_gib": (
                                returned_bytes * N128_DEPTH_CELLS / GIB_BYTES
                            ),
                        }
                    )

    all_controls_passed = bool(
        all(
            row["projection_energy_error"] < PROJECTION_ENERGY_TARGET
            and row["localization_quadrature_relative_error"]
            < LOCALIZATION_QUADRATURE_TARGET
            and row["reference_one_step_reproduced_exactly"]
            and row["fixed_point_converged"] is False
            for row in rows
        )
    )
    convergence = []
    for strategy in STRATEGIES:
        for groups in GROUP_COUNTS:
            selected = [
                row
                for row in rows
                if row["strategy"] == strategy
                and row["physical_frequency_groups"] == groups
            ]
            moving = [
                row for row in selected if row["case"] != "cold coefficient surface"
            ]
            convergence.append(
                {
                    "strategy": strategy,
                    "physical_frequency_groups": groups,
                    "maximum_all_state_checkpoint_error": max(
                        row["absolute_H_I_rate_error"] for row in selected
                    ),
                    "maximum_moving_state_checkpoint_error": max(
                        row["absolute_H_I_rate_error"] for row in moving
                    ),
                    "all_state_checkpoint_rate_gate_passed": all(
                        row["absolute_H_I_rate_error"] < H_I_RATE_TARGET
                        for row in selected
                    ),
                }
            )
    adjacent_pass = {
        strategy: all(
            next(
                row["all_state_checkpoint_rate_gate_passed"]
                for row in convergence
                if row["strategy"] == strategy
                and row["physical_frequency_groups"] == groups
            )
            for groups in GROUP_COUNTS
        )
        for strategy in STRATEGIES
    }

    aggregate_resources = []
    for strategy in STRATEGIES:
        for groups in GROUP_COUNTS:
            selected = [
                row
                for row in resource_rows
                if row["strategy"] == strategy
                and row["physical_frequency_groups"] == groups
            ]
            footprints = {
                int(row["returned_array_footprint_bytes"]) for row in selected
            }
            if len(footprints) != 1:
                raise ArithmeticError("returned-array footprint changed at fixed grid")
            returned_bytes = footprints.pop()
            aggregate_resources.append(
                {
                    "strategy": strategy,
                    "physical_frequency_groups": groups,
                    "sample_count": len(selected),
                    "median_projection_runtime_s": float(
                        np.median([row["projection_runtime_s"] for row in selected])
                    ),
                    "maximum_projection_runtime_s": max(
                        row["projection_runtime_s"] for row in selected
                    ),
                    "median_solve_runtime_s": float(
                        np.median(
                            [row["one_cell_solve_runtime_s"] for row in selected]
                        )
                    ),
                    "maximum_solve_runtime_s": max(
                        row["one_cell_solve_runtime_s"] for row in selected
                    ),
                    "returned_array_footprint_bytes": returned_bytes,
                    "returned_array_footprint_mib": returned_bytes / MIB_BYTES,
                    "N128_linear_returned_array_estimate_gib": (
                        returned_bytes * N128_DEPTH_CELLS / GIB_BYTES
                    ),
                }
            )
    scaling = []
    for strategy in STRATEGIES:
        low = next(
            row
            for row in aggregate_resources
            if row["strategy"] == strategy
            and row["physical_frequency_groups"] == GROUP_COUNTS[0]
        )
        high = next(
            row
            for row in aggregate_resources
            if row["strategy"] == strategy
            and row["physical_frequency_groups"] == GROUP_COUNTS[1]
        )
        scaling.append(
            {
                "strategy": strategy,
                "group_count_ratio": GROUP_COUNTS[1] / GROUP_COUNTS[0],
                "median_solve_runtime_ratio": (
                    high["median_solve_runtime_s"]
                    / low["median_solve_runtime_s"]
                ),
                "returned_array_footprint_ratio": (
                    high["returned_array_footprint_bytes"]
                    / low["returned_array_footprint_bytes"]
                ),
            }
        )

    previous = json.loads(
        (output_dir / "phase7b5j_summary.json").read_text(encoding="utf-8")
    )
    reproduction_differences = []
    for row in rows:
        if row["physical_frequency_groups"] != GROUP_COUNTS[0]:
            continue
        old = next(
            candidate
            for candidate in previous["state_checkpoint_errors"]
            if candidate["case"] == row["case"]
            and candidate["input_iteration"] == row["input_iteration"]
            and candidate["strategy"] == row["strategy"]
            and candidate["physical_frequency_groups"] == GROUP_COUNTS[0]
        )
        reproduction_differences.append(
            abs(row["signed_H_I_rate_error"] - old["signed_H_I_rate_error"])
        )
    reproduction_maximum = max(reproduction_differences)
    finite_reference_confirmed = bool(
        all_controls_passed and any(adjacent_pass.values())
    )
    decision = {
        "all_projection_mapping_and_rate_controls_passed": all_controls_passed,
        "phase7b5j_9632_reproduced": reproduction_maximum < 5.0e-14,
        "adjacent_passing_levels_by_strategy": adjacent_pass,
        "high_resolution_finite_reference_confirmed": finite_reference_confirmed,
        "original_4816_efficiency_gate_passed": False,
        "efficiency_budget_revision_authorized": False,
        "closed_frequency_compression_design_authorized": (
            finite_reference_confirmed
        ),
        "production_frequency_representation_selected": False,
        "targeted_operator_remediation_authorized": False,
        "angular_radiation_subgrid_time_gate_authorized": False,
        "full_dynamic_orbit_authorized": False,
        "matter_temperature_population_feedback_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }
    _write_csv(paths["states"], rows)
    _write_csv(paths["resources"], resource_rows)
    _plot_high_resolution_convergence(paths["convergence_plot"], rows)
    _plot_checkpoint_errors(paths["checkpoint_plot"], rows)
    _plot_resources(paths["resource_plot"], aggregate_resources)
    report = {
        "phase": "7B5k",
        "classification": (
            "[V] adjacent high-resolution P0 H I rate convergence and measured "
            "one-cell runtime; [A] linear N=128 returned-array estimate; "
            "[O] peak memory and production frequency compression"
        ),
        "configuration": {
            "group_counts": list(GROUP_COUNTS),
            "strategies": list(STRATEGIES),
            "input_iterations": list(INPUT_ITERATIONS),
            "control_angular_order": CONTROL_ANGULAR_ORDER,
            "H_I_rate_target": H_I_RATE_TARGET,
            "efficiency_group_limit": EFFICIENCY_GROUP_LIMIT,
            "maximum_velocity_beta": maximum_beta,
            "maximum_doppler_factor": doppler_factor,
            "localization_quadrature_orders": list(
                LOCALIZATION_QUADRATURE_ORDERS
            ),
            "resource_scope": (
                "one-cell elapsed time and direct unique arrays retained by the "
                "returned result dataclass; excludes transient and process peak memory"
            ),
            "N128_linear_estimate_depth_cells": N128_DEPTH_CELLS,
        },
        "state_checkpoint_errors": rows,
        "convergence": convergence,
        "resource_samples": resource_rows,
        "resource_aggregate": aggregate_resources,
        "resource_scaling": scaling,
        "phase7b5j_9632_reproduction_maximum_absolute_difference": (
            reproduction_maximum
        ),
        "decision": decision,
        "open_items": [
            "returned-array footprint is not process peak memory",
            "the N=128 footprint is a linear storage estimate, not a measured column run",
            "no elapsed-time or memory ceiling was added to the original efficiency gate",
            "a finite high-resolution reference does not select a production representation",
            "angle, radiation-subgrid, orbit and matter-feedback gates remain closed",
        ],
        "figures": {
            "high_resolution_convergence": paths["convergence_plot"].name,
            "checkpoint_errors": paths["checkpoint_plot"].name,
            "resource_scaling": paths["resource_plot"].name,
        },
    }
    _write_json_atomic(paths["summary"], report)
    print(json.dumps(decision, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--material-reference",
        type=Path,
        default=Path("outputs/phase7b4r_depth128_phase2048.npz"),
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run_all(args.output_dir, args.material_reference, force=args.force)


if __name__ == "__main__":
    main()
