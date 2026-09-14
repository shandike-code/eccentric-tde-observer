"""Phase 7B5i：同输入单步注入的频率分区与组内表示拆分。"""

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

from eccentric_tde_observer.atomic_continuum import EV_ERG, H_I_VERNER_FIT
from eccentric_tde_observer.mixed_frame_ale import (
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
from eccentric_tde_observer.radiation import PLANCK_ERG_S, planck_nu
from eccentric_tde_observer.rate_error_localization import (
    project_piecewise_constant_intensity,
    project_piecewise_constant_intensity_to_log_p1,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
)

try:
    from scripts.phase7b5a_log_frequency_p1_gate import (
        CONTROL_ANGULAR_ORDER,
        GROUP_QUADRATURE_ORDER,
        ITERATIVE_TOLERANCE,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _active_slice,
        _actual_case_definitions,
        _boosted_planck_outer_log_p1,
        _collision_physical_slice,
        _load_material_reference,
        _p0_actual_one_cell_run,
        _planck_material_log_p1,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from scripts.phase7b4v_mixed_frame_ale_gate import _boosted_planck_outer
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
    from phase7b5a_log_frequency_p1_gate import (  # type: ignore[no-redef]
        CONTROL_ANGULAR_ORDER,
        GROUP_QUADRATURE_ORDER,
        ITERATIVE_TOLERANCE,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _active_slice,
        _actual_case_definitions,
        _boosted_planck_outer_log_p1,
        _collision_physical_slice,
        _load_material_reference,
        _p0_actual_one_cell_run,
        _planck_material_log_p1,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from phase7b4v_mixed_frame_ale_gate import (  # type: ignore[no-redef]
        _boosted_planck_outer,
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
SAME_COST_P0_GROUPS = 2 * FAILED_PHYSICAL_GROUPS
LOCALIZATION_QUADRATURE_ORDERS = (8, 16)
PROJECTION_ENERGY_TARGET = 2.0e-13
DECOMPOSITION_LEDGER_TARGET = 2.0e-12
DOMINANCE_FRACTION = 0.5
H_I_RATE_TARGET = 1.0e-3


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


def _relative_difference(value: float, reference: float) -> float:
    difference = abs(value - reference)
    return difference / abs(reference) if reference != 0.0 else difference


def _project_p0_state(source_edge, target_edge, intensity):
    projected = np.empty((target_edge.size - 1, *intensity.shape[1:]))
    maximum_energy_error = 0.0
    for angle in range(intensity.shape[1]):
        for depth in range(intensity.shape[2]):
            audit = project_piecewise_constant_intensity(
                source_edge,
                intensity[:, angle, depth],
                target_edge,
            )
            projected[:, angle, depth] = audit.mean_intensity_density
            maximum_energy_error = max(
                maximum_energy_error,
                audit.relative_energy_integral_error,
            )
    return projected, maximum_energy_error


def _project_log_p1_state(source_edge, target_edge, intensity):
    mean = np.empty((target_edge.size - 1, *intensity.shape[1:]))
    moment = np.empty_like(mean)
    limiter_count = 0
    maximum_energy_error = 0.0
    for angle in range(intensity.shape[1]):
        for depth in range(intensity.shape[2]):
            audit = project_piecewise_constant_intensity_to_log_p1(
                source_edge,
                intensity[:, angle, depth],
                target_edge,
            )
            mean[:, angle, depth] = audit.mean_energy_density
            moment[:, angle, depth] = (
                audit.realizable_first_moment_energy_density
            )
            limiter_count += audit.limited_group_count
            maximum_energy_error = max(
                maximum_energy_error,
                audit.relative_energy_integral_error,
            )
    return mean, moment, limiter_count, maximum_energy_error


def _p0_operator_context(stencil, mu, weight, state):
    beta = state["beta"]
    temperature = float(state["temperature_k"])
    density = float(state["density_g_cm3"])
    hydrogen = state["hydrogen_fraction"]
    helium = state["helium_fraction"]
    outer = _boosted_planck_outer(stencil, mu, weight, beta, temperature)
    initial = outer[_active_slice(stencil)]
    quadrature = gauss_legendre_frequency_group_quadrature(
        stencil.comoving_collision_edge_hz,
        order_per_group=GROUP_QUADRATURE_ORDER,
    )
    group_planck = group_average_from_quadrature_nodes(
        planck_nu(quadrature.node_hz, temperature),
        quadrature,
    )[:, None]
    continuum = ground_state_milne_multigroup(
        density,
        temperature,
        stencil.comoving_collision_edge_hz,
        group_planck,
        hydrogen[0],
        hydrogen[1],
        helium[0],
        helium[1],
        helium[2],
        order_per_group=GROUP_QUADRATURE_ORDER,
    ).continuum
    return initial, outer, continuum


def _one_p0_map(stencil, old_edge, new_edge, mu, weight, state, source_guess):
    initial, outer, continuum = _p0_operator_context(
        stencil, mu, weight, state
    )
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
        diagnostic_fixed_iteration_count=1,
    )


def _one_log_p1_map(
    stencil,
    old_edge,
    new_edge,
    mu,
    weight,
    state,
    source_mean,
    source_moment,
):
    temperature = float(state["temperature_k"])
    density = float(state["density_g_cm3"])
    hydrogen = state["hydrogen_fraction"]
    helium = state["helium_fraction"]
    outer = _boosted_planck_outer_log_p1(
        stencil, mu, weight, state["beta"], temperature
    )
    initial_mean = outer.mean_density[_active_slice(stencil)]
    initial_moment = outer.first_moment_density[_active_slice(stencil)]
    _, continuum = _planck_material_log_p1(
        stencil,
        density,
        temperature,
        hydrogen,
        helium,
    )
    return solve_mixed_frame_ale_log_p1_group_step(
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        initial_mean,
        initial_moment,
        outer.mean_density,
        outer.first_moment_density,
        continuum.true_absorption_mean_per_cm,
        continuum.true_absorption_first_moment_per_cm,
        continuum.thermal_emissivity_energy_mean_cgs,
        continuum.thermal_emissivity_energy_first_moment_cgs,
        continuum.electron_scattering_mean_per_cm,
        continuum.electron_scattering_first_moment_per_cm,
        state["beta"],
        state["duration_s"],
        iterative_tolerance=ITERATIVE_TOLERANCE,
        iterative_maximum_iterations=8192,
        source_iteration_initial_mean_guess=source_mean,
        source_iteration_initial_first_moment_guess=source_moment,
        diagnostic_fixed_iteration_count=1,
    )


def _rate_components(
    candidate_edge,
    candidate_mean,
    candidate_moment,
    partition_p0,
    same_cost_edge,
    same_cost_p0,
    reference_edge,
    reference_p0,
    analysis_edge_ev,
    quadrature_order,
):
    analysis_hz = analysis_edge_ev * EV_ERG / PLANCK_ERG_S
    integration_edge = np.unique(
        np.concatenate(
            (candidate_edge, same_cost_edge, reference_edge, analysis_hz)
        )
    )
    integration_y = np.log(integration_edge)
    centre_y = 0.5 * (integration_y[:-1] + integration_y[1:])
    half_width_y = 0.5 * np.diff(integration_y)
    node, weight = np.polynomial.legendre.leggauss(int(quadrature_order))
    node_y = centre_y[:, None] + half_width_y[:, None] * node[None, :]
    node_hz = np.exp(node_y)
    node_weight_y = half_width_y[:, None] * weight[None, :]

    candidate_index = np.searchsorted(candidate_edge, node_hz, side="right") - 1
    same_cost_index = np.searchsorted(same_cost_edge, node_hz, side="right") - 1
    reference_index = np.searchsorted(reference_edge, node_hz, side="right") - 1
    candidate_y = np.log(candidate_edge)
    candidate_width_y = np.diff(candidate_y)
    candidate_centre_y = 0.5 * (candidate_y[:-1] + candidate_y[1:])
    coordinate = 2.0 * (
        node_y - candidate_centre_y[candidate_index]
    ) / candidate_width_y[candidate_index]
    q_log_p1 = (
        candidate_mean[candidate_index]
        + 3.0 * candidate_moment[candidate_index] * coordinate
    )
    q_partition_p0 = node_hz * partition_p0[candidate_index]
    q_same_cost_p0 = node_hz * same_cost_p0[same_cost_index]
    q_reference = node_hz * reference_p0[reference_index]
    spectra = {
        "log_p1": q_log_p1,
        "same_partition_p0": q_partition_p0,
        "same_cost_p0": q_same_cost_p0,
        "reference_p0": q_reference,
    }
    if any(
        not np.all(np.isfinite(spectrum)) or np.any(spectrum < 0.0)
        for spectrum in spectra.values()
    ):
        raise ArithmeticError("Phase 7B5i rate spectra became invalid")

    energy_ev = node_hz * PLANCK_ERG_S / EV_ERG
    cross_section = H_I_VERNER_FIT.cross_section_cm2(energy_ev)
    kernel = 4.0 * np.pi * cross_section / (PLANCK_ERG_S * node_hz)
    integrands = {name: spectrum * kernel for name, spectrum in spectra.items()}
    segment_rates = {
        name: np.sum(node_weight_y * integrand, axis=1)
        for name, integrand in integrands.items()
    }
    segment_mid_ev = np.sqrt(integration_edge[:-1] * integration_edge[1:])
    segment_mid_ev *= PLANCK_ERG_S / EV_ERG
    analysis_index = np.searchsorted(
        analysis_edge_ev, segment_mid_ev, side="right"
    ) - 1
    bin_count = analysis_edge_ev.size - 1

    def bin_sum(values):
        result = np.zeros(bin_count, dtype=np.float64)
        np.add.at(result, analysis_index, values)
        return result

    rate_bins = {name: bin_sum(values) for name, values in segment_rates.items()}
    differences = {
        "total_log_p1": integrands["log_p1"] - integrands["reference_p0"],
        "fine_to_partition_p0": (
            integrands["same_partition_p0"] - integrands["reference_p0"]
        ),
        "partition_p0_to_log_p1": (
            integrands["log_p1"] - integrands["same_partition_p0"]
        ),
        "fine_to_same_cost_p0": (
            integrands["same_cost_p0"] - integrands["reference_p0"]
        ),
    }
    signed_bins = {
        name: bin_sum(np.sum(node_weight_y * value, axis=1))
        for name, value in differences.items()
    }
    absolute_bins = {
        name: bin_sum(np.sum(node_weight_y * np.abs(value), axis=1))
        for name, value in differences.items()
    }
    totals = {name: float(np.sum(value)) for name, value in rate_bins.items()}
    if not all(np.isfinite(value) for value in totals.values()):
        raise ArithmeticError("Phase 7B5i rate totals became non-finite")
    return {
        "rate_bins": rate_bins,
        "signed_difference_bins": signed_bins,
        "absolute_difference_bins": absolute_bins,
        "totals": totals,
    }


def _region_rows(case, iteration, components, regions):
    rows = []
    for component, values in components["absolute_difference_bins"].items():
        total = float(np.sum(values))
        for label, left, right in regions:
            edge = components["analysis_edge_ev"]
            selected = (edge[:-1] >= left) & (edge[1:] <= right)
            contribution = float(np.sum(values[selected]))
            rows.append(
                {
                    "case": case,
                    "input_iteration": iteration,
                    "component": component,
                    "region": label,
                    "absolute_difference_fraction": (
                        contribution / total if total > 0.0 else 0.0
                    ),
                }
            )
    return rows


def _plot_decomposition(path: Path, rows) -> None:
    cases = tuple(dict.fromkeys(row["case"] for row in rows))
    x = np.arange(len(INPUT_ITERATIONS))
    fig, axes = plt.subplots(2, 3, figsize=(15.0, 9.2), constrained_layout=True)
    for column, case in enumerate(cases):
        selected = [row for row in rows if row["case"] == case]
        for field, marker, label in (
            ("total_log_p1_signed_error", "o", "total log-P1 injection"),
            ("fine_to_partition_p0_signed", "s", "frequency partition"),
            ("partition_p0_to_log_p1_signed", "^", "within-partition P1-P0"),
        ):
            axes[0, column].plot(
                x,
                [row[field] for row in selected],
                marker=marker,
                label=label,
            )
        axes[0, column].axhline(0.0, color="black", linewidth=0.8)
        axes[0, column].set_yscale("symlog", linthresh=1.0e-8)
        axes[0, column].set_ylabel("Signed H I rate contribution")
        axes[0, column].set_title(case)
        axes[0, column].grid(alpha=0.25)
        axes[1, column].plot(
            x,
            [row["absolute_partition_fraction"] for row in selected],
            marker="s",
            label="partition fraction",
        )
        axes[1, column].plot(
            x,
            [row["absolute_representation_fraction"] for row in selected],
            marker="^",
            label="within-partition fraction",
        )
        axes[1, column].axhline(
            DOMINANCE_FRACTION, color="tab:green", linestyle="--"
        )
        axes[1, column].set_ylim(-0.03, 1.03)
        axes[1, column].set_ylabel("Fraction of absolute component sum")
        axes[1, column].grid(alpha=0.25)
        for axis in axes[:, column]:
            axis.set_xticks(x, INPUT_ITERATIONS)
        axes[1, column].set_xlabel("Input source-iteration index")
    axes[0, 0].legend(fontsize=8)
    axes[1, 0].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_same_cost(path: Path, rows) -> None:
    cases = tuple(dict.fromkeys(row["case"] for row in rows))
    x = np.arange(len(INPUT_ITERATIONS))
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.8), constrained_layout=True)
    for axis, case in zip(axes, cases, strict=True):
        selected = [row for row in rows if row["case"] == case]
        for field, marker, label in (
            ("total_log_p1_signed_error", "o", "2408-group log-P1"),
            ("fine_to_partition_p0_signed", "s", "2408-group P0"),
            ("same_cost_p0_signed_error", "^", "4816-group P0"),
        ):
            axis.plot(
                x,
                [abs(row[field]) for row in selected],
                marker=marker,
                label=label,
            )
        axis.axhline(H_I_RATE_TARGET, color="black", linestyle=":", label="rate gate")
        axis.set_yscale("log")
        axis.set_xticks(x, INPUT_ITERATIONS)
        axis.set_xlabel("Input source-iteration index")
        axis.set_ylabel("Absolute H I rate error")
        axis.set_title(case)
        axis.grid(alpha=0.25, which="both")
    axes[0].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_regions(path: Path, region_rows) -> None:
    cases = tuple(dict.fromkeys(row["case"] for row in region_rows))
    components = ("fine_to_partition_p0", "partition_p0_to_log_p1")
    labels = ("frequency partition", "within-partition P1-P0")
    regions = (
        "H I Doppler band",
        "H I shoulder to He I",
        "He I to He II",
        "above He II",
    )
    fig, axes = plt.subplots(2, 3, figsize=(15.0, 8.2), constrained_layout=True)
    for row_index, (component, component_label) in enumerate(
        zip(components, labels, strict=True)
    ):
        for column, case in enumerate(cases):
            matrix = np.array(
                [
                    [
                        next(
                            row
                            for row in region_rows
                            if row["case"] == case
                            and row["input_iteration"] == iteration
                            and row["component"] == component
                            and row["region"] == region
                        )["absolute_difference_fraction"]
                        for region in regions
                    ]
                    for iteration in INPUT_ITERATIONS
                ]
            )
            image = axes[row_index, column].imshow(
                matrix, vmin=0.0, vmax=1.0, aspect="auto", cmap="viridis"
            )
            axes[row_index, column].set_xticks(
                np.arange(len(regions)), regions, rotation=28, ha="right"
            )
            axes[row_index, column].set_yticks(
                np.arange(len(INPUT_ITERATIONS)), INPUT_ITERATIONS
            )
            axes[row_index, column].set_ylabel("Input source-iteration index")
            axes[row_index, column].set_title(f"{case}\n{component_label}")
            for i in range(matrix.shape[0]):
                for j in range(matrix.shape[1]):
                    axes[row_index, column].text(
                        j,
                        i,
                        f"{matrix[i, j]:.2f}",
                        ha="center",
                        va="center",
                        color="white" if matrix[i, j] < 0.35 else "black",
                        fontsize=8,
                    )
    fig.colorbar(image, ax=axes, label="Fraction of absolute component difference")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5i_summary.json",
        "decomposition": output_dir / "phase7b5i_partition_representation.csv",
        "regions": output_dir / "phase7b5i_component_regions.csv",
        "decomposition_plot": output_dir
        / "phase7b5i_partition_representation_decomposition.png",
        "same_cost_plot": output_dir / "phase7b5i_same_cost_p0_comparison.png",
        "region_plot": output_dir / "phase7b5i_component_region_evolution.png",
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
        FAILED_PHYSICAL_GROUPS,
        FAILED_FOCUS_FRACTION,
        maximum_beta,
    )
    _, same_cost_stencil = _stencil(
        SAME_COST_P0_GROUPS,
        FAILED_FOCUS_FRACTION,
        maximum_beta,
    )
    from eccentric_tde_observer.mixed_frame_ale import mixed_frame_frequency_stencil

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

        for iteration in INPUT_ITERATIONS:
            reference_input = reference_states[iteration]
            partition_input, partition_projection_error = _project_p0_state(
                reference_stencil.active_lab_edge_hz,
                candidate_stencil.active_lab_edge_hz,
                reference_input,
            )
            same_cost_input, same_cost_projection_error = _project_p0_state(
                reference_stencil.active_lab_edge_hz,
                same_cost_stencil.active_lab_edge_hz,
                reference_input,
            )
            p1_mean, p1_moment, p1_limiter, p1_projection_error = (
                _project_log_p1_state(
                    reference_stencil.active_lab_edge_hz,
                    candidate_stencil.active_lab_edge_hz,
                    reference_input,
                )
            )
            reference_next = _one_p0_map(
                reference_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                state,
                reference_input,
            )
            partition_next = _one_p0_map(
                candidate_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                state,
                partition_input,
            )
            same_cost_next = _one_p0_map(
                same_cost_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                state,
                same_cost_input,
            )
            p1_next = _one_log_p1_map(
                candidate_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                state,
                p1_mean,
                p1_moment,
            )
            reference_reproduced = np.array_equal(
                reference_next.final_lab_intensity_density,
                reference_states[iteration + 1],
            )
            reference_physical = _collision_physical_slice(reference_stencil)
            candidate_physical = _collision_physical_slice(candidate_stencil)
            same_cost_physical = _collision_physical_slice(same_cost_stencil)

            localizations = []
            for quadrature_order in LOCALIZATION_QUADRATURE_ORDERS:
                component = _rate_components(
                    candidate_stencil.active_lab_edge_hz,
                    p1_next.final_comoving_mean_intensity_energy_density[
                        candidate_physical, 0
                    ],
                    p1_next.final_comoving_mean_first_moment_intensity_energy_density[
                        candidate_physical, 0
                    ],
                    partition_next.final_comoving_mean_intensity_density[
                        candidate_physical, 0
                    ],
                    same_cost_stencil.active_lab_edge_hz,
                    same_cost_next.final_comoving_mean_intensity_density[
                        same_cost_physical, 0
                    ],
                    reference_stencil.active_lab_edge_hz,
                    reference_next.final_comoving_mean_intensity_density[
                        reference_physical, 0
                    ],
                    analysis_edge,
                    quadrature_order,
                )
                component["analysis_edge_ev"] = analysis_edge
                localizations.append(component)
            low, high = localizations
            totals = high["totals"]
            reference_rate = totals["reference_p0"]
            total_injection = (totals["log_p1"] - reference_rate) / reference_rate
            partition_component = (
                totals["same_partition_p0"] - reference_rate
            ) / reference_rate
            representation_component = (
                totals["log_p1"] - totals["same_partition_p0"]
            ) / reference_rate
            same_cost_error = (
                totals["same_cost_p0"] - reference_rate
            ) / reference_rate
            ledger = total_injection - partition_component - representation_component
            component_scale = abs(partition_component) + abs(representation_component)
            quadrature_error = max(
                _relative_difference(low["totals"][name], totals[name])
                for name in totals
            )
            rows.append(
                {
                    "case": case,
                    "input_iteration": iteration,
                    "output_iteration": iteration + 1,
                    "total_log_p1_signed_error": total_injection,
                    "fine_to_partition_p0_signed": partition_component,
                    "partition_p0_to_log_p1_signed": representation_component,
                    "same_cost_p0_signed_error": same_cost_error,
                    "decomposition_ledger": ledger,
                    "decomposition_ledger_relative": (
                        abs(ledger) / abs(total_injection)
                        if total_injection != 0.0
                        else abs(ledger)
                    ),
                    "absolute_partition_fraction": (
                        abs(partition_component) / component_scale
                        if component_scale > 0.0
                        else 0.0
                    ),
                    "absolute_representation_fraction": (
                        abs(representation_component) / component_scale
                        if component_scale > 0.0
                        else 0.0
                    ),
                    "reference_one_step_reproduced_exactly": reference_reproduced,
                    "partition_p0_projection_energy_error": partition_projection_error,
                    "same_cost_p0_projection_energy_error": same_cost_projection_error,
                    "log_p1_projection_energy_error": p1_projection_error,
                    "log_p1_projection_limiter_count": p1_limiter,
                    "localization_quadrature_relative_error": quadrature_error,
                    "reference_fixed_point_converged": (
                        reference_next.fixed_point_converged
                    ),
                    "partition_p0_fixed_point_converged": (
                        partition_next.fixed_point_converged
                    ),
                    "same_cost_p0_fixed_point_converged": (
                        same_cost_next.fixed_point_converged
                    ),
                    "log_p1_fixed_point_converged": p1_next.fixed_point_converged,
                }
            )
            region_rows.extend(_region_rows(case, iteration, high, regions))

    all_controls_passed = all(
        row["reference_one_step_reproduced_exactly"]
        and row["decomposition_ledger_relative"] < DECOMPOSITION_LEDGER_TARGET
        and row["partition_p0_projection_energy_error"] < PROJECTION_ENERGY_TARGET
        and row["same_cost_p0_projection_energy_error"] < PROJECTION_ENERGY_TARGET
        and row["log_p1_projection_energy_error"] < PROJECTION_ENERGY_TARGET
        and row["localization_quadrature_relative_error"]
        < LOCALIZATION_QUADRATURE_TARGET
        for row in rows
    )
    moving_cases = ("maximum cell speed", "maximum width change")
    dominance_by_case = {}
    for case in moving_cases:
        selected = [row for row in rows if row["case"] == case]
        partition_dominant = all(
            row["absolute_partition_fraction"] > DOMINANCE_FRACTION
            for row in selected
        )
        representation_dominant = all(
            row["absolute_representation_fraction"] > DOMINANCE_FRACTION
            for row in selected
        )
        dominance_by_case[case] = (
            "frequency_partition"
            if partition_dominant
            else "within_partition_p1_minus_p0"
            if representation_dominant
            else "mixed"
        )
    shared_dominance = len(set(dominance_by_case.values())) == 1
    same_cost_p0_rate_gate = all(
        abs(row["same_cost_p0_signed_error"]) < H_I_RATE_TARGET
        for row in rows
    )
    dominant = next(iter(dominance_by_case.values()))
    decision = {
        "all_projection_mapping_and_ledger_controls_passed": all_controls_passed,
        "dominant_component_by_moving_case": dominance_by_case,
        "same_dominant_component_in_both_moving_cases": shared_dominance,
        "same_cost_p0_one_step_rate_gate_passed": same_cost_p0_rate_gate,
        "frequency_partition_audit_authorized": bool(
            all_controls_passed and shared_dominance and dominant == "frequency_partition"
        ),
        "within_partition_representation_audit_authorized": bool(
            all_controls_passed
            and shared_dominance
            and dominant == "within_partition_p1_minus_p0"
        ),
        "joint_partition_representation_audit_required": bool(
            all_controls_passed and not shared_dominance
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
    _plot_same_cost(paths["same_cost_plot"], rows)
    _plot_regions(paths["region_plot"], region_rows)
    report = {
        "phase": "7B5i",
        "classification": (
            "[A] same-input one-step 2408-group P0 and 4816-group same-cost P0 controls; "
            "[V] exact scalar H I partition-representation ledger; "
            "[O] invariant-level mechanism and production frequency representation"
        ),
        "configuration": {
            "input_iterations": list(INPUT_ITERATIONS),
            "candidate_focus_fraction": FAILED_FOCUS_FRACTION,
            "candidate_log_p1_groups": FAILED_PHYSICAL_GROUPS,
            "candidate_log_p1_spectral_dof": 2 * FAILED_PHYSICAL_GROUPS,
            "same_partition_p0_groups": FAILED_PHYSICAL_GROUPS,
            "same_cost_p0_groups": SAME_COST_P0_GROUPS,
            "reference_p0_groups_per_decade": REFERENCE_P0_GROUPS_PER_DECADE,
            "localization_quadrature_orders": list(
                LOCALIZATION_QUADRATURE_ORDERS
            ),
            "projection_energy_target": PROJECTION_ENERGY_TARGET,
            "decomposition_ledger_target": DECOMPOSITION_LEDGER_TARGET,
            "dominance_fraction": DOMINANCE_FRACTION,
            "H_I_rate_target": H_I_RATE_TARGET,
            "maximum_velocity_beta": maximum_beta,
            "maximum_doppler_factor": doppler_factor,
        },
        "partition_representation_decomposition": rows,
        "component_region_evolution": region_rows,
        "decision": decision,
        "open_items": [
            "the split is exact for the scalar H I rate, not a unique invariant-level operator split",
            "the within-partition term includes P1 reconstruction and P1 coefficient/operator differences",
            "the same-cost P0 control is a one-step diagnostic, not a selected production grid",
            "all fixed-count outputs are intentionally unconverged source-iteration maps",
            "angle, radiation-subgrid, orbit and matter-feedback gates remain closed",
        ],
        "figures": {
            "partition_representation_decomposition": paths[
                "decomposition_plot"
            ].name,
            "same_cost_p0_comparison": paths["same_cost_plot"].name,
            "component_region_evolution": paths["region_plot"].name,
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
