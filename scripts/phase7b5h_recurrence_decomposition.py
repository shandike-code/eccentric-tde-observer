"""Phase 7B5h：固定点每步离散注入与已有误差传播的标量率分解。"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil,
    solve_mixed_frame_ale_group_step,
)
from eccentric_tde_observer.mixed_frame_ale_log_p1 import (
    solve_mixed_frame_ale_log_p1_group_step,
)
from eccentric_tde_observer.multigroup_continuum import (
    gauss_legendre_frequency_group_quadrature,
    ground_state_milne_multigroup,
    group_average_from_quadrature_nodes,
)
from eccentric_tde_observer.radiation import planck_nu
from eccentric_tde_observer.rate_error_localization import (
    localize_hydrogen_photoionization_rate_error,
    project_piecewise_constant_intensity_to_log_p1,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
)

try:
    from scripts.phase7b4v_mixed_frame_ale_gate import _boosted_planck_outer
    from scripts.phase7b5a_log_frequency_p1_gate import (
        CONTROL_ANGULAR_ORDER,
        GROUP_QUADRATURE_ORDER,
        ITERATIVE_TOLERANCE,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _active_slice,
        _actual_case_definitions,
        _actual_one_cell_run_log_p1,
        _boosted_planck_outer_log_p1,
        _collision_physical_slice,
        _load_material_reference,
        _p0_actual_one_cell_run,
        _planck_material_log_p1,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from scripts.phase7b5b_rate_kernel_grid_gate import _stencil
    from scripts.phase7b5c_signed_rate_error_localization import (
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
        LOCALIZATION_QUADRATURE_TARGET,
        _analysis_edges,
        _regions,
    )
    from scripts.phase7b5f_single_pass_intensity_transform import (
        _state_parameters,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b4v_mixed_frame_ale_gate import (  # type: ignore[no-redef]
        _boosted_planck_outer,
    )
    from phase7b5a_log_frequency_p1_gate import (  # type: ignore[no-redef]
        CONTROL_ANGULAR_ORDER,
        GROUP_QUADRATURE_ORDER,
        ITERATIVE_TOLERANCE,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _active_slice,
        _actual_case_definitions,
        _actual_one_cell_run_log_p1,
        _boosted_planck_outer_log_p1,
        _collision_physical_slice,
        _load_material_reference,
        _p0_actual_one_cell_run,
        _planck_material_log_p1,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from phase7b5b_rate_kernel_grid_gate import _stencil  # type: ignore[no-redef]
    from phase7b5c_signed_rate_error_localization import (  # type: ignore[no-redef]
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
        LOCALIZATION_QUADRATURE_TARGET,
        _analysis_edges,
        _regions,
    )
    from phase7b5f_single_pass_intensity_transform import (  # type: ignore[no-redef]
        _state_parameters,
    )


INPUT_ITERATIONS = (0, 1, 2, 4, 8)
CAPTURE_ITERATIONS = tuple(sorted(set(INPUT_ITERATIONS) | {n + 1 for n in INPUT_ITERATIONS}))
LOCALIZATION_QUADRATURE_ORDERS = (8, 16)
ONE_STEP_REPRODUCTION_TARGET = 2.0e-13
DECOMPOSITION_LEDGER_TARGET = 2.0e-12
STABLE_DOMINANCE_FRACTION = 0.5


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _relative_difference(value: float, reference: float) -> float:
    difference = abs(value - reference)
    return difference / abs(reference) if reference != 0.0 else difference


def _project_reference_to_log_p1(reference_edge, candidate_edge, intensity):
    groups = candidate_edge.size - 1
    mean = np.empty((groups, intensity.shape[1], intensity.shape[2]))
    moment = np.empty_like(mean)
    limiter_count = 0
    energy_error = 0.0
    for angle in range(intensity.shape[1]):
        for depth in range(intensity.shape[2]):
            projection = project_piecewise_constant_intensity_to_log_p1(
                reference_edge,
                intensity[:, angle, depth],
                candidate_edge,
            )
            mean[:, angle, depth] = projection.mean_energy_density
            moment[:, angle, depth] = (
                projection.realizable_first_moment_energy_density
            )
            limiter_count += projection.limited_group_count
            energy_error = max(
                energy_error, projection.relative_energy_integral_error
            )
    return mean, moment, limiter_count, energy_error


def _localizations(candidate_stencil, candidate_result, reference_stencil, reference_result, analysis_edge):
    candidate_physical = _collision_physical_slice(candidate_stencil)
    reference_physical = _collision_physical_slice(reference_stencil)
    mean = candidate_result.final_comoving_mean_intensity_energy_density[
        candidate_physical, 0
    ]
    moment = (
        candidate_result.final_comoving_mean_first_moment_intensity_energy_density[
            candidate_physical, 0
        ]
    )
    reference = reference_result.final_comoving_mean_intensity_density[
        reference_physical, 0
    ]
    return [
        localize_hydrogen_photoionization_rate_error(
            candidate_stencil.active_lab_edge_hz,
            mean,
            moment,
            reference_stencil.active_lab_edge_hz,
            reference,
            analysis_edge,
            quadrature_order_per_native_overlap=order,
        )
        for order in LOCALIZATION_QUADRATURE_ORDERS
    ]


def _region_rows(case: str, iteration: int, localization, regions):
    rows = []
    edge = localization.analysis_edge_ev
    absolute_total = float(
        np.sum(localization.absolute_integrand_difference_bin_s1)
    )
    for label, left, right in regions:
        selected = (edge[:-1] >= left) & (edge[1:] <= right)
        absolute = float(
            np.sum(localization.absolute_integrand_difference_bin_s1[selected])
        )
        rows.append(
            {
                "case": case,
                "input_iteration": iteration,
                "region": label,
                "absolute_injection_difference_fraction": (
                    absolute / absolute_total if absolute_total > 0.0 else 0.0
                ),
            }
        )
    return rows


def _plot_decomposition(path: Path, rows) -> None:
    cases = tuple(dict.fromkeys(row["case"] for row in rows))
    x = np.arange(len(INPUT_ITERATIONS))
    fig, axes = plt.subplots(2, 3, figsize=(15.0, 8.0), constrained_layout=True)
    for column, case in enumerate(cases):
        selected = [row for row in rows if row["case"] == case]
        axes[0, column].plot(
            x,
            [row["actual_next_signed_rate_error"] for row in selected],
            marker="o",
            label="actual next error",
        )
        axes[0, column].plot(
            x,
            [row["common_input_injection_signed"] for row in selected],
            marker="s",
            label="common-input injection",
        )
        axes[0, column].plot(
            x,
            [row["existing_error_propagation_signed"] for row in selected],
            marker="^",
            label="existing-error propagation",
        )
        axes[0, column].axhline(0.0, color="black", linewidth=0.8)
        axes[0, column].set_yscale("symlog", linthresh=1.0e-8)
        axes[0, column].set_ylabel("Signed H I rate contribution")
        axes[0, column].set_title(case)
        axes[0, column].grid(alpha=0.25)
        axes[1, column].plot(
            x,
            [
                row["absolute_injection_fraction_of_component_sum"]
                for row in selected
            ],
            marker="s",
            label="injection fraction",
        )
        axes[1, column].plot(
            x,
            [
                row["absolute_propagation_fraction_of_component_sum"]
                for row in selected
            ],
            marker="^",
            label="propagation fraction",
        )
        axes[1, column].axhline(
            STABLE_DOMINANCE_FRACTION, color="tab:green", linestyle="--"
        )
        axes[1, column].set_ylim(-0.03, 1.03)
        axes[1, column].set_ylabel("Fraction of absolute component sum")
        axes[1, column].grid(alpha=0.25)
        for axis in (axes[0, column], axes[1, column]):
            axis.set_xticks(x, INPUT_ITERATIONS)
            axis.set_xlabel("Input source-iteration index")
    axes[0, 0].legend(fontsize=8)
    axes[1, 0].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_injection_regions(path: Path, region_rows) -> None:
    cases = tuple(dict.fromkeys(row["case"] for row in region_rows))
    regions = (
        "H I Doppler band",
        "H I shoulder to He I",
        "He I to He II",
        "above He II",
    )
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.8), constrained_layout=True)
    for axis, case in zip(axes, cases, strict=True):
        matrix = np.array(
            [
                [
                    next(
                        row
                        for row in region_rows
                        if row["case"] == case
                        and row["input_iteration"] == iteration
                        and row["region"] == region
                    )["absolute_injection_difference_fraction"]
                    for region in regions
                ]
                for iteration in INPUT_ITERATIONS
            ]
        )
        image = axis.imshow(matrix, vmin=0.0, vmax=1.0, aspect="auto", cmap="viridis")
        axis.set_xticks(np.arange(len(regions)), regions, rotation=28, ha="right")
        axis.set_yticks(np.arange(len(INPUT_ITERATIONS)), INPUT_ITERATIONS)
        axis.set_ylabel("Input source-iteration index")
        axis.set_title(case)
        for row_index in range(matrix.shape[0]):
            for column_index in range(matrix.shape[1]):
                axis.text(
                    column_index,
                    row_index,
                    f"{matrix[row_index, column_index]:.2f}",
                    ha="center",
                    va="center",
                    color="white" if matrix[row_index, column_index] < 0.35 else "black",
                    fontsize=8,
                )
    fig.colorbar(image, ax=axes, label="Fraction of absolute injection difference")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5h_summary.json",
        "decomposition": output_dir / "phase7b5h_recurrence_decomposition.csv",
        "regions": output_dir / "phase7b5h_injection_regions.csv",
        "decomposition_plot": output_dir / "phase7b5h_recurrence_decomposition.png",
        "region_plot": output_dir / "phase7b5h_injection_region_evolution.png",
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
    regions = _regions(doppler_factor)
    _, candidate_stencil = _stencil(
        FAILED_PHYSICAL_GROUPS, FAILED_FOCUS_FRACTION, maximum_beta
    )
    reference_stencil = mixed_frame_frequency_stencil(
        *PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        maximum_beta,
    )
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    rows: list[dict[str, object]] = []
    region_rows: list[dict[str, object]] = []
    for definition in _actual_case_definitions(material, full, audit):
        case = str(definition["case"])
        p0_states: dict[int, np.ndarray] = {}
        p1_states: dict[int, tuple[np.ndarray, np.ndarray]] = {}

        def observe_p0(iteration, intensity):
            if iteration in CAPTURE_ITERATIONS:
                p0_states[iteration] = np.array(intensity, copy=True)

        def observe_p1(iteration, mean, moment):
            if iteration in CAPTURE_ITERATIONS:
                p1_states[iteration] = (
                    np.array(mean, copy=True),
                    np.array(moment, copy=True),
                )

        _p0_actual_one_cell_run(
            material,
            full,
            audit,
            definition,
            REFERENCE_P0_GROUPS_PER_DECADE,
            iteration_observer=observe_p0,
        )
        _actual_one_cell_run_log_p1(
            material,
            full,
            audit,
            definition,
            FAILED_PHYSICAL_GROUPS,
            stencil_override=candidate_stencil,
            iteration_observer=observe_p1,
        )
        state = _state_parameters(material, full, definition)
        beta = state["beta"]
        temperature = float(state["temperature_k"])
        density = float(state["density_g_cm3"])
        hydrogen = state["hydrogen_fraction"]
        helium = state["helium_fraction"]
        phase = int(definition["phase_index"])
        following = int(definition["following_phase_index"])
        depth = int(definition["full_depth_index"])
        duration = float(material["step_duration_s"][phase])
        old_edge = full["edges_cm"][phase, depth : depth + 2]
        new_edge = full["edges_cm"][following, depth : depth + 2]

        reference_outer = _boosted_planck_outer(
            reference_stencil, mu, weight, beta, temperature
        )
        reference_initial = reference_outer[_active_slice(reference_stencil)]
        reference_quadrature = gauss_legendre_frequency_group_quadrature(
            reference_stencil.comoving_collision_edge_hz,
            order_per_group=GROUP_QUADRATURE_ORDER,
        )
        reference_planck = group_average_from_quadrature_nodes(
            planck_nu(reference_quadrature.node_hz, temperature),
            reference_quadrature,
        )[:, None]
        reference_material = ground_state_milne_multigroup(
            density,
            temperature,
            reference_stencil.comoving_collision_edge_hz,
            reference_planck,
            hydrogen[0],
            hydrogen[1],
            helium[0],
            helium[1],
            helium[2],
            order_per_group=GROUP_QUADRATURE_ORDER,
        ).continuum

        candidate_outer = _boosted_planck_outer_log_p1(
            candidate_stencil, mu, weight, beta, temperature
        )
        candidate_initial_mean = candidate_outer.mean_density[
            _active_slice(candidate_stencil)
        ]
        candidate_initial_moment = candidate_outer.first_moment_density[
            _active_slice(candidate_stencil)
        ]
        _, candidate_material = _planck_material_log_p1(
            candidate_stencil,
            density,
            temperature,
            hydrogen,
            helium,
        )

        for iteration in INPUT_ITERATIONS:
            projected_mean, projected_moment, projection_limiter, projection_energy_error = (
                _project_reference_to_log_p1(
                    reference_stencil.active_lab_edge_hz,
                    candidate_stencil.active_lab_edge_hz,
                    p0_states[iteration],
                )
            )
            reference_next = solve_mixed_frame_ale_group_step(
                reference_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                reference_initial,
                reference_outer,
                reference_material.true_absorption_total_per_cm,
                reference_material.thermal_emissivity_total_cgs,
                reference_material.electron_scattering_per_cm,
                beta,
                duration,
                iterative_tolerance=ITERATIVE_TOLERANCE,
                iterative_maximum_iterations=8192,
                source_iteration_initial_guess=p0_states[iteration],
                diagnostic_fixed_iteration_count=1,
            )
            common_candidate_next = solve_mixed_frame_ale_log_p1_group_step(
                candidate_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                candidate_initial_mean,
                candidate_initial_moment,
                candidate_outer.mean_density,
                candidate_outer.first_moment_density,
                candidate_material.true_absorption_mean_per_cm,
                candidate_material.true_absorption_first_moment_per_cm,
                candidate_material.thermal_emissivity_energy_mean_cgs,
                candidate_material.thermal_emissivity_energy_first_moment_cgs,
                candidate_material.electron_scattering_mean_per_cm,
                candidate_material.electron_scattering_first_moment_per_cm,
                beta,
                duration,
                iterative_tolerance=ITERATIVE_TOLERANCE,
                iterative_maximum_iterations=8192,
                source_iteration_initial_mean_guess=projected_mean,
                source_iteration_initial_first_moment_guess=projected_moment,
                diagnostic_fixed_iteration_count=1,
            )
            actual_mean, actual_moment = p1_states[iteration]
            actual_candidate_next = solve_mixed_frame_ale_log_p1_group_step(
                candidate_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                candidate_initial_mean,
                candidate_initial_moment,
                candidate_outer.mean_density,
                candidate_outer.first_moment_density,
                candidate_material.true_absorption_mean_per_cm,
                candidate_material.true_absorption_first_moment_per_cm,
                candidate_material.thermal_emissivity_energy_mean_cgs,
                candidate_material.thermal_emissivity_energy_first_moment_cgs,
                candidate_material.electron_scattering_mean_per_cm,
                candidate_material.electron_scattering_first_moment_per_cm,
                beta,
                duration,
                iterative_tolerance=ITERATIVE_TOLERANCE,
                iterative_maximum_iterations=8192,
                source_iteration_initial_mean_guess=actual_mean,
                source_iteration_initial_first_moment_guess=actual_moment,
                diagnostic_fixed_iteration_count=1,
            )
            reference_reproduced = np.array_equal(
                reference_next.final_lab_intensity_density,
                p0_states[iteration + 1],
            )
            candidate_reproduced = bool(
                np.array_equal(
                    actual_candidate_next.final_lab_mean_intensity_energy_density,
                    p1_states[iteration + 1][0],
                )
                and np.array_equal(
                    actual_candidate_next.final_lab_first_moment_intensity_energy_density,
                    p1_states[iteration + 1][1],
                )
            )
            actual_localizations = _localizations(
                candidate_stencil,
                actual_candidate_next,
                reference_stencil,
                reference_next,
                analysis_edge,
            )
            common_localizations = _localizations(
                candidate_stencil,
                common_candidate_next,
                reference_stencil,
                reference_next,
                analysis_edge,
            )
            actual_localization = actual_localizations[-1]
            common_localization = common_localizations[-1]
            reference_rate = actual_localization.reference_total_rate_s1
            injection = common_localization.signed_relative_error
            propagation = (
                actual_localization.candidate_total_rate_s1
                - common_localization.candidate_total_rate_s1
            ) / reference_rate
            actual = actual_localization.signed_relative_error
            ledger = actual - injection - propagation
            actual_scale = abs(actual)
            component_scale = abs(injection) + abs(propagation)
            quadrature_error = max(
                _relative_difference(
                    actual_localizations[0].candidate_total_rate_s1,
                    actual_localization.candidate_total_rate_s1,
                ),
                _relative_difference(
                    actual_localizations[0].reference_total_rate_s1,
                    actual_localization.reference_total_rate_s1,
                ),
                _relative_difference(
                    common_localizations[0].candidate_total_rate_s1,
                    common_localization.candidate_total_rate_s1,
                ),
            )
            rows.append(
                {
                    "case": case,
                    "input_iteration": iteration,
                    "output_iteration": iteration + 1,
                    "actual_next_signed_rate_error": actual,
                    "common_input_injection_signed": injection,
                    "existing_error_propagation_signed": propagation,
                    "decomposition_ledger": ledger,
                    "decomposition_ledger_relative": (
                        abs(ledger) / actual_scale if actual_scale > 0.0 else abs(ledger)
                    ),
                    "absolute_injection_over_actual": (
                        abs(injection) / actual_scale if actual_scale > 0.0 else 0.0
                    ),
                    "absolute_propagation_over_actual": (
                        abs(propagation) / actual_scale if actual_scale > 0.0 else 0.0
                    ),
                    "absolute_injection_fraction_of_component_sum": (
                        abs(injection) / component_scale
                        if component_scale > 0.0
                        else 0.0
                    ),
                    "absolute_propagation_fraction_of_component_sum": (
                        abs(propagation) / component_scale
                        if component_scale > 0.0
                        else 0.0
                    ),
                    "reference_one_step_reproduced_exactly": reference_reproduced,
                    "candidate_one_step_reproduced_exactly": candidate_reproduced,
                    "common_input_projection_limiter_count": projection_limiter,
                    "common_input_projection_energy_error": projection_energy_error,
                    "localization_quadrature_relative_error": quadrature_error,
                    "common_candidate_fixed_point_converged": (
                        common_candidate_next.fixed_point_converged
                    ),
                    "actual_candidate_fixed_point_converged": (
                        actual_candidate_next.fixed_point_converged
                    ),
                    "reference_fixed_point_converged": (
                        reference_next.fixed_point_converged
                    ),
                }
            )
            region_rows.extend(
                _region_rows(case, iteration, common_localization, regions)
            )

    all_one_step_reproduced = all(
        row["reference_one_step_reproduced_exactly"]
        and row["candidate_one_step_reproduced_exactly"]
        for row in rows
    )
    all_decompositions_close = all(
        row["decomposition_ledger_relative"] < DECOMPOSITION_LEDGER_TARGET
        and row["common_input_projection_energy_error"]
        < ONE_STEP_REPRODUCTION_TARGET
        and row["localization_quadrature_relative_error"]
        < LOCALIZATION_QUADRATURE_TARGET
        for row in rows
    )
    moving_cases = ("maximum cell speed", "maximum width change")
    dominance_by_case = {}
    for case in moving_cases:
        selected = [row for row in rows if row["case"] == case]
        injection_dominant = all(
            row["absolute_injection_fraction_of_component_sum"]
            > STABLE_DOMINANCE_FRACTION
            for row in selected[1:]
        )
        propagation_dominant = all(
            row["absolute_propagation_fraction_of_component_sum"]
            > STABLE_DOMINANCE_FRACTION
            for row in selected[1:]
        )
        dominance_by_case[case] = (
            "injection"
            if injection_dominant
            else "propagation"
            if propagation_dominant
            else "mixed"
        )
    stable_dominance = len(set(dominance_by_case.values())) == 1
    decision = {
        "all_one_step_maps_reproduced_exactly": all_one_step_reproduced,
        "all_scalar_decompositions_closed": all_decompositions_close,
        "dominant_contribution_by_moving_case": dominance_by_case,
        "same_dominant_contribution_in_both_moving_cases": stable_dominance,
        "common_input_injection_audit_authorized": bool(
            all_one_step_reproduced
            and all_decompositions_close
            and stable_dominance
            and next(iter(dominance_by_case.values())) == "injection"
        ),
        "propagation_jacobian_vector_audit_authorized": bool(
            all_one_step_reproduced
            and all_decompositions_close
            and stable_dominance
            and next(iter(dominance_by_case.values())) == "propagation"
        ),
        "mixed_recurrence_audit_required": bool(
            all_one_step_reproduced
            and all_decompositions_close
            and not stable_dominance
        ),
        "targeted_operator_remediation_authorized": False,
        "production_frequency_representation_selected": False,
        "angular_radiation_subgrid_time_gate_authorized": False,
        "full_dynamic_orbit_authorized": False,
        "matter_temperature_population_feedback_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }
    _write_csv(paths["decomposition"], rows)
    _write_csv(paths["regions"], region_rows)
    _plot_decomposition(paths["decomposition_plot"], rows)
    _plot_injection_regions(paths["region_plot"], region_rows)
    report = {
        "phase": "7B5h",
        "classification": (
            "[A] P0-reference common input projected conservatively to log-P1 and "
            "50% stable dominance rule; [V] exact one-step map reproduction and scalar "
            "H I rate decomposition; [O] spectrum-space Jacobian-vector mechanism"
        ),
        "configuration": {
            "input_iterations": list(INPUT_ITERATIONS),
            "capture_iterations": list(CAPTURE_ITERATIONS),
            "localization_quadrature_orders": list(
                LOCALIZATION_QUADRATURE_ORDERS
            ),
            "one_step_reproduction_target": ONE_STEP_REPRODUCTION_TARGET,
            "decomposition_ledger_target": DECOMPOSITION_LEDGER_TARGET,
            "stable_dominance_fraction": STABLE_DOMINANCE_FRACTION,
            "candidate_focus_fraction": FAILED_FOCUS_FRACTION,
            "candidate_physical_groups": FAILED_PHYSICAL_GROUPS,
            "reference_p0_groups_per_decade": REFERENCE_P0_GROUPS_PER_DECADE,
            "maximum_velocity_beta": maximum_beta,
            "maximum_doppler_factor": doppler_factor,
        },
        "recurrence_decomposition": rows,
        "injection_region_evolution": region_rows,
        "decision": decision,
        "open_items": [
            "the decomposition is exact for the scalar H I rate, not the full spectrum vector",
            "the common input uses a conservative realizability-limited P0-to-log-P1 projection",
            "dominance does not by itself identify a defective invariant or coefficient",
            "no one-step diagnostic result is a converged production spectrum",
            "angle, radiation-subgrid, orbit and matter-feedback gates remain closed",
        ],
        "figures": {
            "recurrence_decomposition": paths["decomposition_plot"].name,
            "injection_region_evolution": paths["region_plot"].name,
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
