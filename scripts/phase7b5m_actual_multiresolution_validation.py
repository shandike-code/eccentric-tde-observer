"""Phase 7B5m：冻结训练网格后的实际动态独立验证。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.goal_oriented_frequency import (
    hydrogen_photoionization_monitor_group_grid,
)
from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil,
    mixed_frame_frequency_stencil_from_active_edges,
    solve_mixed_frame_ale_group_step,
)
from eccentric_tde_observer.multiresolution_frequency import (
    budgeted_variable_frequency_grid,
    embedded_p0_frequency_error,
    nested_log_frequency_hierarchy,
)
from eccentric_tde_observer.radiative_transfer_1d import gauss_legendre_mu_weights

try:
    from scripts.phase7b5a_log_frequency_p1_gate import (
        CONTROL_ANGULAR_ORDER,
        COUPLED_RESIDUAL_TARGET,
        ENERGY_LEDGER_TARGET,
        ITERATIVE_TOLERANCE,
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
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
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
        _p0_operator_context,
        _project_p0_state,
        _relative_difference,
    )
    from scripts.phase7b5j_prescribed_partition_audit import (
        EFFICIENCY_GROUP_LIMIT,
        H_I_RATE_TARGET,
        LOCALIZATION_QUADRATURE_ORDERS,
        _p0_rate_comparison,
    )
    from scripts.phase7b5k_high_resolution_convergence import (
        _returned_array_bytes,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5a_log_frequency_p1_gate import (  # type: ignore[no-redef]
        CONTROL_ANGULAR_ORDER,
        COUPLED_RESIDUAL_TARGET,
        ENERGY_LEDGER_TARGET,
        ITERATIVE_TOLERANCE,
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
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
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
        _p0_operator_context,
        _project_p0_state,
        _relative_difference,
    )
    from phase7b5j_prescribed_partition_audit import (  # type: ignore[no-redef]
        EFFICIENCY_GROUP_LIMIT,
        H_I_RATE_TARGET,
        LOCALIZATION_QUADRATURE_ORDERS,
        _p0_rate_comparison,
    )
    from phase7b5k_high_resolution_convergence import (  # type: ignore[no-redef]
        _returned_array_bytes,
    )


TRAINING_ITERATIONS = (0, 2, 4)
VALIDATION_ITERATIONS = (1, 8)
if tuple(sorted(TRAINING_ITERATIONS + VALIDATION_ITERATIONS)) != INPUT_ITERATIONS:
    raise RuntimeError("training/validation split must partition all input iterations")
INDICATOR_QUADRATURE_ORDER = 16
MIB_BYTES = 1024**2
GIB_BYTES = 1024**3
N128_DEPTH_CELLS = 128


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    fields: list[str] = []
    for row in rows:
        fields.extend(key for key in row if key not in fields)
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _edge_sha256(edge: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(edge, dtype=np.float64).tobytes()).hexdigest()


def _rate_comparisons(
    candidate_stencil,
    candidate_result,
    reference_stencil,
    reference_result,
    analysis_edge,
):
    candidate_physical = _collision_physical_slice(candidate_stencil)
    reference_physical = _collision_physical_slice(reference_stencil)
    comparisons = [
        _p0_rate_comparison(
            candidate_stencil.active_lab_edge_hz,
            candidate_result.final_comoving_mean_intensity_density[
                candidate_physical, 0
            ],
            reference_stencil.active_lab_edge_hz,
            reference_result.final_comoving_mean_intensity_density[
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
        for name in ("candidate_total_rate_s1", "reference_total_rate_s1")
    )
    return high, quadrature_error


def _converged_p0_map(
    stencil, old_edge, new_edge, mu, weight, state, source_guess
):
    initial, outer, continuum = _p0_operator_context(stencil, mu, weight, state)
    return solve_mixed_frame_ale_group_step(
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        initial,
        outer,
        continuum.true_absorption_total_per_cm,
        continuum.thermal_emissivity_total_cgs,
        continuum.electron_scattering_per_cm,
        state["beta"],
        state["duration_s"],
        iterative_tolerance=ITERATIVE_TOLERANCE,
        iterative_maximum_iterations=8192,
        source_iteration_initial_guess=source_guess,
    )


def _case_context(material, full, definition):
    state = _state_parameters(material, full, definition)
    phase = int(definition["phase_index"])
    following = int(definition["following_phase_index"])
    depth = int(definition["full_depth_index"])
    state["duration_s"] = float(material["step_duration_s"][phase])
    old_edge = full["edges_cm"][phase, depth : depth + 2]
    new_edge = full["edges_cm"][following, depth : depth + 2]
    return state, old_edge, new_edge


def _capture_reference_states(
    material, full, audit, definition, capture_iterations
):
    states: dict[int, np.ndarray] = {}

    def observe(iteration, intensity):
        if iteration in capture_iterations:
            states[iteration] = np.array(intensity, copy=True)

    _p0_actual_one_cell_run(
        material,
        full,
        audit,
        definition,
        REFERENCE_P0_GROUPS_PER_DECADE,
        iteration_observer=observe,
    )
    return states


def _plot_all_errors(path: Path, rows) -> None:
    cases = tuple(dict.fromkeys(row["case"] for row in rows))
    x = np.arange(len(INPUT_ITERATIONS))
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.8), constrained_layout=True)
    for axis, case in zip(axes, cases, strict=True):
        selected = [row for row in rows if row["case"] == case]
        for key, label, color, marker in (
            (
                "variable_absolute_H_I_rate_error",
                "frozen variable, 4814",
                "tab:red",
                "o",
            ),
            (
                "master_absolute_H_I_rate_error",
                "nested master, 9632",
                "tab:green",
                "s",
            ),
            (
                "phase7b5j_fixed_4816_absolute_H_I_rate_error",
                "fixed rate-kernel, 4816",
                "tab:orange",
                "^",
            ),
        ):
            axis.plot(
                x,
                [row[key] for row in selected],
                color=color,
                marker=marker,
                label=label if case == cases[0] else None,
            )
        for index, row in enumerate(selected):
            if row["split"] == "validation":
                axis.axvspan(index - 0.12, index + 0.12, color="tab:blue", alpha=0.12)
        axis.axhline(H_I_RATE_TARGET, color="black", linestyle=":")
        axis.set_yscale("log")
        axis.set_xticks(x, INPUT_ITERATIONS)
        axis.set_xlabel("Input source-iteration index")
        axis.set_ylabel("Absolute H I rate error")
        axis.set_title(case)
        axis.grid(alpha=0.2, which="both")
    axes[0].legend(fontsize=7)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_validation(path: Path, rows) -> None:
    selected = [row for row in rows if row["split"] == "validation"]
    labels = [f"{row['case']}\nn={row['input_iteration']}" for row in selected]
    x = np.arange(len(selected))
    width = 0.26
    fig, axis = plt.subplots(figsize=(13.0, 5.5), constrained_layout=True)
    axis.bar(
        x - width,
        [row["variable_absolute_H_I_rate_error"] for row in selected],
        width,
        color="tab:red",
        label="frozen variable, 4814",
    )
    axis.bar(
        x,
        [row["master_absolute_H_I_rate_error"] for row in selected],
        width,
        color="tab:green",
        label="nested master, 9632",
    )
    axis.bar(
        x + width,
        [
            row["phase7b5j_fixed_4816_absolute_H_I_rate_error"]
            for row in selected
        ],
        width,
        color="tab:orange",
        label="fixed rate-kernel, 4816",
    )
    axis.axhline(H_I_RATE_TARGET, color="black", linestyle=":", label="rate target")
    axis.set_yscale("log")
    axis.set_xticks(x, labels, rotation=20, ha="right")
    axis.set_ylabel("Absolute H I rate error")
    axis.set_title("Frozen-grid holdout validation")
    axis.grid(alpha=0.2, axis="y", which="both")
    axis.legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_resources(path: Path, rows) -> None:
    split_names = ("training", "validation")
    medians = [
        np.median(
            [
                row["variable_one_cell_solve_runtime_s"]
                for row in rows
                if row["split"] == split
            ]
        )
        for split in split_names
    ]
    footprint = rows[0]["variable_returned_array_footprint_mib"]
    n128 = rows[0]["variable_N128_linear_returned_array_estimate_gib"]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), constrained_layout=True)
    axes[0].bar(split_names, medians, color=("tab:purple", "tab:blue"))
    axes[0].set_ylabel("Median one-cell solve time (s)")
    axes[0].set_title("Measured frozen-grid runtime")
    axes[0].grid(alpha=0.2, axis="y")
    axes[1].bar(
        ("one cell", "N=128 linear estimate"),
        (footprint, n128 * 1024.0),
        color=("tab:red", "tab:grey"),
    )
    axes[1].set_ylabel("Returned-array footprint (MiB)")
    axes[1].set_title("Direct arrays, not peak memory")
    axes[1].grid(alpha=0.2, axis="y")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5m_summary.json",
        "states": output_dir / "phase7b5m_train_validation_states.csv",
        "parents": output_dir / "phase7b5m_frozen_parent_ranking.csv",
        "error_plot": output_dir / "phase7b5m_train_validation_errors.png",
        "validation_plot": output_dir / "phase7b5m_holdout_validation.png",
        "resource_plot": output_dir / "phase7b5m_resource_costs.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    audit = _trajectory_velocity_audit(material, full)
    definitions = _actual_case_definitions(material, full, audit)
    maximum_beta = float(audit["maximum_velocity_beta"])
    analysis_edge, doppler_factor = _analysis_edges(maximum_beta)
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    reference_stencil = mixed_frame_frequency_stencil(
        *PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        maximum_beta,
    )
    base_grid = hydrogen_photoionization_monitor_group_grid(
        *PHYSICAL_ENERGY_RANGE_EV,
        FAILED_PHYSICAL_GROUPS,
        FAILED_FOCUS_FRACTION,
    )
    hierarchy = nested_log_frequency_hierarchy(base_grid.group_edge_hz)
    master_stencil = mixed_frame_frequency_stencil_from_active_edges(
        hierarchy.master_edge_hz, maximum_beta
    )

    # 中文：第一遍只读取预声明训练截面；验证截面在网格冻结前不参与排序。
    training_master_spectra: list[np.ndarray] = []
    training_master_metrics: dict[tuple[str, int], dict[str, object]] = {}
    for definition in definitions:
        case = str(definition["case"])
        reference_states = _capture_reference_states(
            material, full, audit, definition, TRAINING_ITERATIONS
        )
        state, old_edge, new_edge = _case_context(material, full, definition)
        for iteration in TRAINING_ITERATIONS:
            reference_next = _one_p0_map(
                reference_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                state,
                reference_states[iteration],
            )
            master_source, master_projection_error = _project_p0_state(
                reference_stencil.active_lab_edge_hz,
                master_stencil.active_lab_edge_hz,
                reference_states[iteration],
            )
            master_next = _one_p0_map(
                master_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                state,
                master_source,
            )
            master_rate, master_quadrature_error = _rate_comparisons(
                master_stencil,
                master_next,
                reference_stencil,
                reference_next,
                analysis_edge,
            )
            master_physical = _collision_physical_slice(master_stencil)
            training_master_spectra.append(
                np.array(
                    master_next.final_comoving_mean_intensity_density[
                        master_physical, 0
                    ],
                    copy=True,
                )
            )
            training_master_metrics[(case, iteration)] = {
                "signed_error": master_rate["signed_relative_error"],
                "absolute_error": abs(master_rate["signed_relative_error"]),
                "projection_error": master_projection_error,
                "quadrature_error": master_quadrature_error,
                "energy_ledger": master_next.total_relative_energy_ledger_residual,
                "coupled_residual": (
                    master_next.global_scale_normalized_coupled_residual
                ),
            }
    training_matrix = np.column_stack(training_master_spectra)
    indicator = embedded_p0_frequency_error(
        hierarchy.base_edge_hz,
        hierarchy.master_edge_hz,
        training_matrix,
        production_tolerance=H_I_RATE_TARGET,
        quadrature_order_per_fine_group=INDICATOR_QUADRATURE_ORDER,
    )
    variable_grid = budgeted_variable_frequency_grid(
        indicator,
        hierarchy.master_edge_hz,
        EFFICIENCY_GROUP_LIMIT,
    )
    variable_stencil = mixed_frame_frequency_stencil_from_active_edges(
        variable_grid.group_edge_hz, maximum_beta
    )
    frozen_hash_before_validation = _edge_sha256(variable_grid.group_edge_hz)

    previous = json.loads(
        (output_dir / "phase7b5j_summary.json").read_text(encoding="utf-8")
    )
    rows: list[dict[str, object]] = []
    converged_operator_controls: list[dict[str, object]] = []
    # 中文：第二遍网格只读；验证结果只用于判门，不再反馈给排序或边界。
    for definition in definitions:
        case = str(definition["case"])
        reference_states = _capture_reference_states(
            material, full, audit, definition, CAPTURE_ITERATIONS
        )
        state, old_edge, new_edge = _case_context(material, full, definition)
        for iteration in INPUT_ITERATIONS:
            split = (
                "training" if iteration in TRAINING_ITERATIONS else "validation"
            )
            reference_next = _one_p0_map(
                reference_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                state,
                reference_states[iteration],
            )
            variable_projection_started = time.perf_counter()
            variable_source, variable_projection_error = _project_p0_state(
                reference_stencil.active_lab_edge_hz,
                variable_stencil.active_lab_edge_hz,
                reference_states[iteration],
            )
            variable_projection_runtime = (
                time.perf_counter() - variable_projection_started
            )
            variable_solve_started = time.perf_counter()
            variable_next = _one_p0_map(
                variable_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                state,
                variable_source,
            )
            variable_solve_runtime = time.perf_counter() - variable_solve_started
            variable_rate, variable_quadrature_error = _rate_comparisons(
                variable_stencil,
                variable_next,
                reference_stencil,
                reference_next,
                analysis_edge,
            )

            if iteration == 0:
                master_control_source, _ = _project_p0_state(
                    reference_stencil.active_lab_edge_hz,
                    master_stencil.active_lab_edge_hz,
                    reference_states[iteration],
                )
                for representation, stencil, source in (
                    ("frozen variable 4814", variable_stencil, variable_source),
                    ("nested master 9632", master_stencil, master_control_source),
                ):
                    converged_started = time.perf_counter()
                    converged = _converged_p0_map(
                        stencil,
                        old_edge,
                        new_edge,
                        mu,
                        weight,
                        state,
                        source,
                    )
                    converged_operator_controls.append(
                        {
                            "case": case,
                            "representation": representation,
                            "fixed_point_converged": converged.fixed_point_converged,
                            "fixed_point_iterations": converged.fixed_point_iterations,
                            "final_fixed_point_change": converged.final_fixed_point_change,
                            "global_coupled_residual": (
                                converged.global_scale_normalized_coupled_residual
                            ),
                            "total_relative_energy_ledger_residual": (
                                converged.total_relative_energy_ledger_residual
                            ),
                            "minimum_intensity": converged.minimum_intensity,
                            "runtime_s": time.perf_counter() - converged_started,
                        }
                    )

            if split == "training":
                master_metric = training_master_metrics[(case, iteration)]
            else:
                master_source, master_projection_error = _project_p0_state(
                    reference_stencil.active_lab_edge_hz,
                    master_stencil.active_lab_edge_hz,
                    reference_states[iteration],
                )
                master_next = _one_p0_map(
                    master_stencil,
                    old_edge,
                    new_edge,
                    mu,
                    weight,
                    state,
                    master_source,
                )
                master_rate, master_quadrature_error = _rate_comparisons(
                    master_stencil,
                    master_next,
                    reference_stencil,
                    reference_next,
                    analysis_edge,
                )
                master_metric = {
                    "signed_error": master_rate["signed_relative_error"],
                    "absolute_error": abs(master_rate["signed_relative_error"]),
                    "projection_error": master_projection_error,
                    "quadrature_error": master_quadrature_error,
                    "energy_ledger": master_next.total_relative_energy_ledger_residual,
                    "coupled_residual": (
                        master_next.global_scale_normalized_coupled_residual
                    ),
                }
            old = next(
                candidate
                for candidate in previous["state_checkpoint_errors"]
                if candidate["case"] == case
                and candidate["input_iteration"] == iteration
                and candidate["strategy"] == "rate_kernel"
                and candidate["physical_frequency_groups"]
                == EFFICIENCY_GROUP_LIMIT
            )
            returned_bytes = _returned_array_bytes(variable_next)
            rows.append(
                {
                    "case": case,
                    "input_iteration": iteration,
                    "output_iteration": iteration + 1,
                    "split": split,
                    "variable_physical_frequency_groups": (
                        variable_grid.leaf_group_count
                    ),
                    "variable_signed_H_I_rate_error": (
                        variable_rate["signed_relative_error"]
                    ),
                    "variable_absolute_H_I_rate_error": abs(
                        variable_rate["signed_relative_error"]
                    ),
                    "master_signed_H_I_rate_error": master_metric["signed_error"],
                    "master_absolute_H_I_rate_error": master_metric[
                        "absolute_error"
                    ],
                    "phase7b5j_fixed_4816_absolute_H_I_rate_error": old[
                        "absolute_H_I_rate_error"
                    ],
                    "variable_projection_energy_error": variable_projection_error,
                    "master_projection_energy_error": master_metric[
                        "projection_error"
                    ],
                    "variable_rate_quadrature_relative_error": (
                        variable_quadrature_error
                    ),
                    "master_rate_quadrature_relative_error": master_metric[
                        "quadrature_error"
                    ],
                    "variable_total_relative_energy_ledger_residual": (
                        variable_next.total_relative_energy_ledger_residual
                    ),
                    "variable_global_coupled_residual": (
                        variable_next.global_scale_normalized_coupled_residual
                    ),
                    "master_total_relative_energy_ledger_residual": master_metric[
                        "energy_ledger"
                    ],
                    "master_global_coupled_residual": master_metric[
                        "coupled_residual"
                    ],
                    "reference_one_step_reproduced_exactly": np.array_equal(
                        reference_next.final_lab_intensity_density,
                        reference_states[iteration + 1],
                    ),
                    "master_reference_reproduced_exactly": np.array_equal(
                        reference_next.final_lab_intensity_density,
                        reference_states[iteration + 1],
                    ),
                    "variable_fixed_point_converged": (
                        variable_next.fixed_point_converged
                    ),
                    "variable_projection_runtime_s": variable_projection_runtime,
                    "variable_one_cell_solve_runtime_s": variable_solve_runtime,
                    "variable_returned_array_footprint_bytes": returned_bytes,
                    "variable_returned_array_footprint_mib": (
                        returned_bytes / MIB_BYTES
                    ),
                    "variable_N128_linear_returned_array_estimate_gib": (
                        returned_bytes * N128_DEPTH_CELLS / GIB_BYTES
                    ),
                }
            )
    frozen_hash_after_validation = _edge_sha256(variable_grid.group_edge_hz)
    grid_unchanged = frozen_hash_before_validation == frozen_hash_after_validation

    one_step_controls_passed = bool(
        grid_unchanged
        and all(
            row["reference_one_step_reproduced_exactly"]
            and row["master_reference_reproduced_exactly"]
            and row["variable_projection_energy_error"]
            < PROJECTION_ENERGY_TARGET
            and row["master_projection_energy_error"]
            < PROJECTION_ENERGY_TARGET
            and row["variable_rate_quadrature_relative_error"]
            < LOCALIZATION_QUADRATURE_TARGET
            and row["master_rate_quadrature_relative_error"]
            < LOCALIZATION_QUADRATURE_TARGET
            and row["variable_fixed_point_converged"] is False
            for row in rows
        )
    )
    converged_operator_controls_passed = all(
        row["fixed_point_converged"]
        and row["global_coupled_residual"] < COUPLED_RESIDUAL_TARGET
        and row["total_relative_energy_ledger_residual"] < ENERGY_LEDGER_TARGET
        and row["minimum_intensity"] >= 0.0
        for row in converged_operator_controls
    )
    controls_passed = bool(
        one_step_controls_passed and converged_operator_controls_passed
    )
    training_rows = [row for row in rows if row["split"] == "training"]
    validation_rows = [row for row in rows if row["split"] == "validation"]
    training_gate = all(
        row["variable_absolute_H_I_rate_error"] < H_I_RATE_TARGET
        for row in training_rows
    )
    validation_gate = all(
        row["variable_absolute_H_I_rate_error"] < H_I_RATE_TARGET
        for row in validation_rows
    )
    master_gate = all(
        row["master_absolute_H_I_rate_error"] < H_I_RATE_TARGET
        for row in rows
    )
    budget_gate = variable_grid.leaf_group_count <= EFFICIENCY_GROUP_LIMIT
    candidate_selected = bool(
        controls_passed
        and training_gate
        and validation_gate
        and master_gate
        and budget_gate
    )
    decision = {
        "training_validation_split_predeclared_and_disjoint": True,
        "validation_spectra_used_for_grid_construction": False,
        "frozen_grid_hash_unchanged_through_validation": grid_unchanged,
        "all_one_step_mapping_and_rate_controls_passed": (
            one_step_controls_passed
        ),
        "all_converged_operator_energy_and_residual_controls_passed": (
            converged_operator_controls_passed
        ),
        "all_mapping_rate_energy_and_residual_controls_passed": controls_passed,
        "nested_master_reference_gate_passed": master_gate,
        "training_H_I_rate_gate_passed": training_gate,
        "holdout_validation_H_I_rate_gate_passed": validation_gate,
        "original_4816_group_budget_satisfied": budget_gate,
        "original_4816_efficiency_gate_passed": candidate_selected,
        "one_cell_production_frequency_candidate_selected": candidate_selected,
        "production_frequency_representation_selected": candidate_selected,
        "angular_radiation_subgrid_time_gate_authorized": candidate_selected,
        "full_dynamic_orbit_authorized": False,
        "matter_temperature_population_feedback_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }

    parent_rows = []
    for parent in range(hierarchy.base_edge_hz.size - 1):
        parent_rows.append(
            {
                "base_parent_index": parent,
                "left_frequency_hz": hierarchy.base_edge_hz[parent],
                "right_frequency_hz": hierarchy.base_edge_hz[parent + 1],
                "normalized_training_indicator": indicator.normalized_indicator[
                    parent
                ],
                "energy_l1_training_defect_fraction": (
                    indicator.energy_l1_defect_fraction[parent]
                ),
                "H_I_training_rate_defect_fraction": (
                    indicator.rate_defect_fraction_by_species[0, parent]
                ),
                "He_I_training_rate_defect_fraction": (
                    indicator.rate_defect_fraction_by_species[1, parent]
                ),
                "He_II_training_rate_defect_fraction": (
                    indicator.rate_defect_fraction_by_species[2, parent]
                ),
                "selected_for_four_children": bool(
                    variable_grid.refined_parent_mask[parent]
                ),
                "variable_child_count": int(
                    variable_grid.child_groups_per_base[parent]
                ),
            }
        )
    _write_csv(paths["states"], rows)
    _write_csv(paths["parents"], parent_rows)
    _plot_all_errors(paths["error_plot"], rows)
    _plot_validation(paths["validation_plot"], rows)
    _plot_resources(paths["resource_plot"], rows)
    report = {
        "phase": "7B5m",
        "classification": (
            "[A] predeclared disjoint source-iteration split and frozen 4814-leaf "
            "grid; [V] actual one-step holdout H I rate, energy and cost audit; "
            "[O] full angle/subgrid/orbit and matter feedback"
        ),
        "configuration": {
            "training_iterations": list(TRAINING_ITERATIONS),
            "validation_iterations": list(VALIDATION_ITERATIONS),
            "all_input_iterations": list(INPUT_ITERATIONS),
            "training_state_count": len(training_rows),
            "validation_state_count": len(validation_rows),
            "base_group_count": hierarchy.base_edge_hz.size - 1,
            "nested_master_group_count": hierarchy.master_edge_hz.size - 1,
            "variable_leaf_group_count": variable_grid.leaf_group_count,
            "efficiency_group_limit": EFFICIENCY_GROUP_LIMIT,
            "fixed_rate_kernel_focus_fraction": FAILED_FOCUS_FRACTION,
            "control_angular_order": CONTROL_ANGULAR_ORDER,
            "H_I_rate_target": H_I_RATE_TARGET,
            "maximum_velocity_beta": maximum_beta,
            "maximum_doppler_factor": doppler_factor,
            "indicator_quadrature_order": INDICATOR_QUADRATURE_ORDER,
            "validation_protocol": (
                "construct indicator only from n=0,2,4 master outputs; freeze and "
                "hash the grid; evaluate n=1,8 without grid updates"
            ),
        },
        "frozen_grid": {
            "sha256_before_validation": frozen_hash_before_validation,
            "sha256_after_validation": frozen_hash_after_validation,
            "refined_parent_count": variable_grid.refined_parent_count,
            "leaf_group_count": variable_grid.leaf_group_count,
            "unused_leaf_budget": variable_grid.unused_leaf_budget,
            "maximum_unrefined_indicator": (
                variable_grid.maximum_unrefined_indicator
            ),
            "minimum_refined_indicator": variable_grid.minimum_refined_indicator,
        },
        "state_results": rows,
        "converged_operator_controls": converged_operator_controls,
        "aggregate": {
            "maximum_training_variable_error": max(
                row["variable_absolute_H_I_rate_error"] for row in training_rows
            ),
            "maximum_validation_variable_error": max(
                row["variable_absolute_H_I_rate_error"] for row in validation_rows
            ),
            "maximum_all_variable_error": max(
                row["variable_absolute_H_I_rate_error"] for row in rows
            ),
            "maximum_all_nested_master_error": max(
                row["master_absolute_H_I_rate_error"] for row in rows
            ),
            "maximum_all_phase7b5j_fixed_4816_error": max(
                row["phase7b5j_fixed_4816_absolute_H_I_rate_error"]
                for row in rows
            ),
            "median_variable_projection_runtime_s": float(
                np.median([row["variable_projection_runtime_s"] for row in rows])
            ),
            "median_variable_one_cell_solve_runtime_s": float(
                np.median(
                    [row["variable_one_cell_solve_runtime_s"] for row in rows]
                )
            ),
            "variable_returned_array_footprint_mib": rows[0][
                "variable_returned_array_footprint_mib"
            ],
            "variable_N128_linear_returned_array_estimate_gib": rows[0][
                "variable_N128_linear_returned_array_estimate_gib"
            ],
        },
        "decision": decision,
        "open_items": [
            "the frozen grid is validated only on six one-cell source-iteration holdouts",
            "returned-array footprint is not process peak memory",
            "a one-cell candidate must still pass angle, radiation-subgrid and orbit-wide gates",
            "matter temperature and H/He population feedback remain disabled",
            "Phase 4 replacement and UVOT remain unauthorized",
        ],
        "figures": {
            "train_validation_errors": paths["error_plot"].name,
            "holdout_validation": paths["validation_plot"].name,
            "resource_costs": paths["resource_plot"].name,
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
