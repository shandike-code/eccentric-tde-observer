"""Phase 7B5j：固定 P0 下的预声明非拟合频率分区审计。"""

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

from eccentric_tde_observer.atomic_continuum import (
    EV_ERG,
    H_HE_GROUND_STATE_PHOTOIONIZATION_FITS,
    H_I_VERNER_FIT,
)
from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil,
    mixed_frame_frequency_stencil_from_active_edges,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
)

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
    from scripts.phase7b5b_rate_kernel_grid_gate import _stencil
    from scripts.phase7b5c_signed_rate_error_localization import (
        FAILED_FOCUS_FRACTION,
        LOCALIZATION_QUADRATURE_TARGET,
        _analysis_edges,
        _regions,
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
    from phase7b5b_rate_kernel_grid_gate import _stencil  # type: ignore[no-redef]
    from phase7b5c_signed_rate_error_localization import (  # type: ignore[no-redef]
        FAILED_FOCUS_FRACTION,
        LOCALIZATION_QUADRATURE_TARGET,
        _analysis_edges,
        _regions,
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


GROUP_COUNTS = (2408, 4816, 9632)
STRATEGIES = ("uniform_log", "rate_kernel", "doppler_image_anchors")
LOCALIZATION_QUADRATURE_ORDERS = (8, 16)
H_I_RATE_TARGET = 1.0e-3
EFFICIENCY_GROUP_LIMIT = 4816


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


def _anchored_log_edges(group_count: int, anchor_energy_ev) -> np.ndarray:
    minimum, maximum = PHYSICAL_ENERGY_RANGE_EV
    anchor = np.unique(
        np.concatenate(([minimum], np.asarray(anchor_energy_ev), [maximum]))
    )
    if (
        anchor[0] != minimum
        or anchor[-1] != maximum
        or np.any(np.diff(anchor) <= 0.0)
        or group_count < anchor.size - 1
    ):
        raise ValueError("invalid prescribed log-grid anchors")
    log_width = np.diff(np.log(anchor))
    segment_count = np.ones(log_width.size, dtype=np.int64)
    remaining = int(group_count) - int(segment_count.size)
    raw = remaining * log_width / np.sum(log_width)
    extra = np.floor(raw).astype(np.int64)
    segment_count += extra
    leftover = int(group_count) - int(np.sum(segment_count))
    order = np.argsort(-(raw - extra), kind="stable")
    segment_count[order[:leftover]] += 1
    edges = [float(anchor[0])]
    for left, right, count in zip(
        anchor[:-1], anchor[1:], segment_count, strict=True
    ):
        segment = np.geomspace(left, right, int(count) + 1)
        edges.extend(float(value) for value in segment[1:])
    result = np.asarray(edges)
    result[np.cumsum(segment_count)] = anchor[1:]
    if result.size != group_count + 1 or np.any(np.diff(result) <= 0.0):
        raise ArithmeticError("prescribed anchored log grid became invalid")
    return result


def _doppler_image_anchors(maximum_beta: float, mu: np.ndarray) -> np.ndarray:
    gamma = 1.0 / np.sqrt(1.0 - maximum_beta**2)
    hydrogen = H_I_VERNER_FIT.threshold_energy_ev
    factors = np.unique(
        np.concatenate(
            (
                [1.0, gamma * (1.0 + maximum_beta)],
                gamma * (1.0 + maximum_beta * np.abs(mu)),
            )
        )
    )
    thresholds = np.array(
        [fit.threshold_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS]
    )
    return np.unique(np.concatenate((hydrogen * factors, thresholds)))


def _strategy_stencil(strategy, groups, maximum_beta, mu):
    if strategy == "rate_kernel":
        _, stencil = _stencil(groups, FAILED_FOCUS_FRACTION, maximum_beta)
        edge_ev = stencil.active_lab_edge_hz * PLANCK_ERG_S / EV_ERG
        anchor_count = 3
    else:
        anchors = (
            np.array(
                [
                    fit.threshold_energy_ev
                    for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
                ]
            )
            if strategy == "uniform_log"
            else _doppler_image_anchors(maximum_beta, mu)
        )
        edge_ev = _anchored_log_edges(groups, anchors)
        stencil = mixed_frame_frequency_stencil_from_active_edges(
            edge_ev * EV_ERG / PLANCK_ERG_S,
            maximum_beta,
        )
        anchor_count = int(anchors.size)
    return stencil, edge_ev, anchor_count


def _p0_rate_comparison(
    candidate_edge,
    candidate,
    reference_edge,
    reference,
    analysis_edge_ev,
    quadrature_order,
):
    analysis_hz = analysis_edge_ev * EV_ERG / PLANCK_ERG_S
    integration_edge = np.unique(
        np.concatenate((candidate_edge, reference_edge, analysis_hz))
    )
    integration_y = np.log(integration_edge)
    centre_y = 0.5 * (integration_y[:-1] + integration_y[1:])
    half_width_y = 0.5 * np.diff(integration_y)
    node, weight = np.polynomial.legendre.leggauss(int(quadrature_order))
    node_y = centre_y[:, None] + half_width_y[:, None] * node[None, :]
    node_hz = np.exp(node_y)
    node_weight_y = half_width_y[:, None] * weight[None, :]
    candidate_index = np.searchsorted(candidate_edge, node_hz, side="right") - 1
    reference_index = np.searchsorted(reference_edge, node_hz, side="right") - 1
    candidate_q = node_hz * candidate[candidate_index]
    reference_q = node_hz * reference[reference_index]
    if (
        not np.all(np.isfinite(candidate_q))
        or not np.all(np.isfinite(reference_q))
        or np.any(candidate_q < 0.0)
        or np.any(reference_q < 0.0)
    ):
        raise ArithmeticError("Phase 7B5j P0 rate spectra became invalid")
    energy_ev = node_hz * PLANCK_ERG_S / EV_ERG
    kernel = (
        4.0
        * np.pi
        * H_I_VERNER_FIT.cross_section_cm2(energy_ev)
        / (PLANCK_ERG_S * node_hz)
    )
    candidate_integrand = candidate_q * kernel
    reference_integrand = reference_q * kernel
    candidate_segment = np.sum(node_weight_y * candidate_integrand, axis=1)
    reference_segment = np.sum(node_weight_y * reference_integrand, axis=1)
    absolute_segment = np.sum(
        node_weight_y * np.abs(candidate_integrand - reference_integrand), axis=1
    )
    segment_mid_ev = np.sqrt(integration_edge[:-1] * integration_edge[1:])
    segment_mid_ev *= PLANCK_ERG_S / EV_ERG
    analysis_index = np.searchsorted(
        analysis_edge_ev, segment_mid_ev, side="right"
    ) - 1
    bin_count = analysis_edge_ev.size - 1

    def bin_sum(value):
        result = np.zeros(bin_count)
        np.add.at(result, analysis_index, value)
        return result

    candidate_bin = bin_sum(candidate_segment)
    reference_bin = bin_sum(reference_segment)
    absolute_bin = bin_sum(absolute_segment)
    candidate_total = float(np.sum(candidate_bin))
    reference_total = float(np.sum(reference_bin))
    return {
        "candidate_total_rate_s1": candidate_total,
        "reference_total_rate_s1": reference_total,
        "signed_relative_error": (
            candidate_total - reference_total
        ) / reference_total,
        "signed_error_bin_s1": candidate_bin - reference_bin,
        "absolute_difference_bin_s1": absolute_bin,
    }


def _region_rows(case, iteration, strategy, groups, comparison, analysis_edge, regions):
    rows = []
    total_absolute = float(np.sum(comparison["absolute_difference_bin_s1"]))
    for label, left, right in regions:
        selected = (analysis_edge[:-1] >= left) & (analysis_edge[1:] <= right)
        signed = float(np.sum(comparison["signed_error_bin_s1"][selected]))
        absolute = float(
            np.sum(comparison["absolute_difference_bin_s1"][selected])
        )
        rows.append(
            {
                "case": case,
                "input_iteration": iteration,
                "strategy": strategy,
                "physical_frequency_groups": groups,
                "region": label,
                "signed_rate_error_over_reference": (
                    signed / comparison["reference_total_rate_s1"]
                ),
                "absolute_difference_fraction": (
                    absolute / total_absolute if total_absolute > 0.0 else 0.0
                ),
            }
        )
    return rows


def _plot_convergence(path: Path, rows) -> None:
    cases = ("maximum cell speed", "maximum width change")
    checkpoints = (0, 8)
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.0), constrained_layout=True)
    colors = {
        "uniform_log": "tab:blue",
        "rate_kernel": "tab:orange",
        "doppler_image_anchors": "tab:green",
    }
    labels = {
        "uniform_log": "uniform log",
        "rate_kernel": "fixed rate-kernel",
        "doppler_image_anchors": "Doppler-image anchors",
    }
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
                axis.loglog(
                    [row["physical_frequency_groups"] for row in selected],
                    [abs(row["signed_H_I_rate_error"]) for row in selected],
                    marker="o",
                    color=colors[strategy],
                    label=labels[strategy],
                )
            axis.axhline(H_I_RATE_TARGET, color="black", linestyle=":")
            axis.axvline(EFFICIENCY_GROUP_LIMIT, color="grey", linestyle="--")
            axis.set_xlabel("P0 physical frequency groups")
            axis.set_ylabel("Absolute H I rate error")
            axis.set_title(f"{case}\ninput iteration {iteration}")
            axis.grid(alpha=0.25, which="both")
    axes[0, 0].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_all_checkpoints(path: Path, rows) -> None:
    cases = tuple(dict.fromkeys(row["case"] for row in rows))
    x = np.arange(len(INPUT_ITERATIONS))
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.8), constrained_layout=True)
    markers = {2408: "o", 4816: "s", 9632: "^"}
    colors = {
        "uniform_log": "tab:blue",
        "rate_kernel": "tab:orange",
        "doppler_image_anchors": "tab:green",
    }
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
                    [abs(row["signed_H_I_rate_error"]) for row in selected],
                    color=colors[strategy],
                    marker=markers[groups],
                    linestyle="-" if groups == 4816 else "--",
                    alpha=1.0 if groups == 4816 else 0.65,
                    label=f"{strategy}, {groups}" if case == cases[0] else None,
                )
        axis.axhline(H_I_RATE_TARGET, color="black", linestyle=":")
        axis.set_yscale("log")
        axis.set_xticks(x, INPUT_ITERATIONS)
        axis.set_xlabel("Input source-iteration index")
        axis.set_ylabel("Absolute H I rate error")
        axis.set_title(case)
        axis.grid(alpha=0.25, which="both")
    axes[0].legend(fontsize=7, ncol=2)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_doppler_regions(path: Path, region_rows) -> None:
    cases = tuple(dict.fromkeys(row["case"] for row in region_rows))
    strategies = STRATEGIES
    matrix = np.empty((len(cases), len(strategies)))
    for i, case in enumerate(cases):
        for j, strategy in enumerate(strategies):
            selected = [
                row
                for row in region_rows
                if row["case"] == case
                and row["strategy"] == strategy
                and row["physical_frequency_groups"] == EFFICIENCY_GROUP_LIMIT
                and row["input_iteration"] == 8
                and row["region"] == "H I Doppler band"
            ]
            matrix[i, j] = selected[0]["absolute_difference_fraction"]
    fig, axis = plt.subplots(figsize=(9.0, 5.0), constrained_layout=True)
    image = axis.imshow(matrix, vmin=0.0, vmax=1.0, cmap="viridis", aspect="auto")
    axis.set_xticks(
        np.arange(len(strategies)),
        ("uniform log", "fixed rate-kernel", "Doppler-image anchors"),
        rotation=20,
        ha="right",
    )
    axis.set_yticks(np.arange(len(cases)), cases)
    axis.set_title("H I Doppler-band error fraction at 4816 groups, iteration 8")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            axis.text(
                j,
                i,
                f"{matrix[i, j]:.3f}",
                ha="center",
                va="center",
                color="white" if matrix[i, j] < 0.35 else "black",
            )
    fig.colorbar(image, ax=axis, label="Fraction of absolute H I rate difference")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5j_summary.json",
        "states": output_dir / "phase7b5j_partition_states.csv",
        "regions": output_dir / "phase7b5j_partition_regions.csv",
        "grid": output_dir / "phase7b5j_grid_audit.csv",
        "convergence_plot": output_dir / "phase7b5j_partition_convergence.png",
        "checkpoint_plot": output_dir / "phase7b5j_checkpoint_sensitivity.png",
        "region_plot": output_dir / "phase7b5j_doppler_region_comparison.png",
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
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    reference_stencil = mixed_frame_frequency_stencil(
        *PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        maximum_beta,
    )
    stencils = {}
    grid_rows = []
    hydrogen = H_I_VERNER_FIT.threshold_energy_ev
    doppler_upper = hydrogen * doppler_factor
    for strategy in STRATEGIES:
        for groups in GROUP_COUNTS:
            stencil, edge_ev, anchor_count = _strategy_stencil(
                strategy, groups, maximum_beta, mu
            )
            stencils[(strategy, groups)] = stencil
            in_band = (edge_ev[:-1] >= hydrogen) & (
                edge_ev[1:] <= doppler_upper
            )
            grid_rows.append(
                {
                    "strategy": strategy,
                    "physical_frequency_groups": groups,
                    "prescribed_internal_anchor_count": anchor_count,
                    "H_I_doppler_band_groups": int(np.count_nonzero(in_band)),
                    "minimum_H_I_doppler_band_width_ev": float(
                        np.min(np.diff(edge_ev)[in_band])
                    ),
                    "minimum_global_width_ev": float(np.min(np.diff(edge_ev))),
                    "maximum_global_width_ev": float(np.max(np.diff(edge_ev))),
                    "H_I_threshold_exact": bool(np.count_nonzero(edge_ev == hydrogen) == 1),
                    "H_I_doppler_upper_exact": bool(
                        np.count_nonzero(edge_ev == doppler_upper) == 1
                    ),
                    "strictly_increasing": bool(np.all(np.diff(edge_ev) > 0.0)),
                }
            )

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
                    source, projection_error = _project_p0_state(
                        reference_stencil.active_lab_edge_hz,
                        stencil.active_lab_edge_hz,
                        reference_states[iteration],
                    )
                    candidate_next = _one_p0_map(
                        stencil,
                        old_edge,
                        new_edge,
                        mu,
                        weight,
                        state,
                        source,
                    )
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
                        _relative_difference(
                            low[name], high[name]
                        )
                        for name in (
                            "candidate_total_rate_s1",
                            "reference_total_rate_s1",
                        )
                    )
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
                            "fixed_point_converged": candidate_next.fixed_point_converged,
                        }
                    )
                    region_rows.extend(
                        _region_rows(
                            case,
                            iteration,
                            strategy,
                            groups,
                            high,
                            analysis_edge,
                            regions,
                        )
                    )

    all_controls_passed = bool(
        all(row["strictly_increasing"] and row["H_I_threshold_exact"] for row in grid_rows)
        and all(
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
            moving = [row for row in selected if row["case"] != "cold coefficient surface"]
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
                    "efficiency_gate_passed": groups <= EFFICIENCY_GROUP_LIMIT,
                }
            )
    passing_by_strategy = {
        strategy: [
            row["physical_frequency_groups"]
            for row in convergence
            if row["strategy"] == strategy
            and row["all_state_checkpoint_rate_gate_passed"]
        ]
        for strategy in STRATEGIES
    }
    adjacent_pass_by_strategy = {
        strategy: any(
            left in passing_by_strategy[strategy]
            and right in passing_by_strategy[strategy]
            for left, right in zip(GROUP_COUNTS[:-1], GROUP_COUNTS[1:], strict=True)
        )
        for strategy in STRATEGIES
    }
    budget_pass_by_strategy = {
        strategy: any(
            row["strategy"] == strategy
            and row["physical_frequency_groups"] <= EFFICIENCY_GROUP_LIMIT
            and row["all_state_checkpoint_rate_gate_passed"]
            for row in convergence
        )
        for strategy in STRATEGIES
    }
    moving_budget_rows = [
        row
        for row in rows
        if row["case"] != "cold coefficient surface"
        and row["physical_frequency_groups"] <= EFFICIENCY_GROUP_LIMIT
    ]
    doppler_anchor_robustly_preferred = all(
        next(
            candidate["absolute_H_I_rate_error"]
            for candidate in moving_budget_rows
            if candidate["case"] == row["case"]
            and candidate["input_iteration"] == row["input_iteration"]
            and candidate["physical_frequency_groups"]
            == row["physical_frequency_groups"]
            and candidate["strategy"] == "doppler_image_anchors"
        )
        < row["absolute_H_I_rate_error"]
        for row in moving_budget_rows
        if row["strategy"] in {"uniform_log", "rate_kernel"}
    )
    any_above_budget_pass = any(
        row["physical_frequency_groups"] > EFFICIENCY_GROUP_LIMIT
        and row["all_state_checkpoint_rate_gate_passed"]
        for row in convergence
    )
    no_budget_pass = not any(budget_pass_by_strategy.values())
    decision = {
        "all_grid_projection_and_rate_controls_passed": all_controls_passed,
        "passing_group_levels_by_strategy": passing_by_strategy,
        "adjacent_passing_levels_by_strategy": adjacent_pass_by_strategy,
        "budget_passing_level_by_strategy": budget_pass_by_strategy,
        "doppler_anchor_partition_robustly_preferred": (
            doppler_anchor_robustly_preferred
        ),
        "no_partition_passes_within_efficiency_budget": no_budget_pass,
        "at_least_one_partition_passes_above_budget": any_above_budget_pass,
        "frequency_compression_audit_authorized": bool(
            all_controls_passed and no_budget_pass and any_above_budget_pass
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
    _write_csv(paths["regions"], region_rows)
    _write_csv(paths["grid"], grid_rows)
    _plot_convergence(paths["convergence_plot"], rows)
    _plot_all_checkpoints(paths["checkpoint_plot"], rows)
    _plot_doppler_regions(paths["region_plot"], region_rows)
    report = {
        "phase": "7B5j",
        "classification": (
            "[A] fixed P0, predeclared uniform/rate-kernel/Doppler-image partitions; "
            "[V] common-input H I rate convergence and threshold localization; "
            "[O] production frequency representation"
        ),
        "configuration": {
            "group_counts": list(GROUP_COUNTS),
            "strategies": list(STRATEGIES),
            "input_iterations": list(INPUT_ITERATIONS),
            "fixed_rate_kernel_focus_fraction": FAILED_FOCUS_FRACTION,
            "control_angular_order": CONTROL_ANGULAR_ORDER,
            "H_I_rate_target": H_I_RATE_TARGET,
            "efficiency_group_limit": EFFICIENCY_GROUP_LIMIT,
            "maximum_velocity_beta": maximum_beta,
            "maximum_doppler_factor": doppler_factor,
            "localization_quadrature_orders": list(
                LOCALIZATION_QUADRATURE_ORDERS
            ),
        },
        "grid_audit": grid_rows,
        "state_checkpoint_errors": rows,
        "convergence": convergence,
        "region_evolution": region_rows,
        "decision": decision,
        "open_items": [
            "Doppler-image anchors test exact transform breakpoints but do not fit a free band width",
            "all outputs are one-step P0 diagnostics, not converged production spectra",
            "no strategy is selected until the measured cross-state convergence rule is interpreted",
            "angle, radiation-subgrid, orbit and matter-feedback gates remain closed",
        ],
        "figures": {
            "partition_convergence": paths["convergence_plot"].name,
            "checkpoint_sensitivity": paths["checkpoint_plot"].name,
            "doppler_region_comparison": paths["region_plot"].name,
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
