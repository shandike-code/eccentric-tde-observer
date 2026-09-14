"""Phase 7B5b：H I 光致电离率核目标导向固定网格门。"""

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
from matplotlib.ticker import FixedFormatter, FixedLocator, NullFormatter

from eccentric_tde_observer.goal_oriented_frequency import (
    hydrogen_photoionization_monitor_group_grid,
)
from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil_from_active_edges,
)
from eccentric_tde_observer.mixed_frame_ale_log_p1 import (
    solve_mixed_frame_ale_log_p1_group_step,
)
from eccentric_tde_observer.mixed_frame_frequency import lorentz_ray_transform
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
)

try:
    from scripts.phase7b5a_log_frequency_p1_gate import (
        ACTUAL_FREQUENCY_TARGET,
        CONTROL_ANGULAR_ORDER,
        COUPLED_RESIDUAL_TARGET,
        ENERGY_LEDGER_TARGET,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        SPECTRAL_DOF_LIMIT,
        _active_slice,
        _actual_case_definitions,
        _actual_one_cell_run_log_p1,
        _load_material_reference,
        _p0_actual_one_cell_run,
        _relative_component_errors,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5a_log_frequency_p1_gate import (  # type: ignore[no-redef]
        ACTUAL_FREQUENCY_TARGET,
        CONTROL_ANGULAR_ORDER,
        COUPLED_RESIDUAL_TARGET,
        ENERGY_LEDGER_TARGET,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        SPECTRAL_DOF_LIMIT,
        _active_slice,
        _actual_case_definitions,
        _actual_one_cell_run_log_p1,
        _load_material_reference,
        _p0_actual_one_cell_run,
        _relative_component_errors,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )


FOCUS_FRACTIONS = (0.25, 0.50, 0.75)
PHYSICAL_GROUP_COUNTS = (153, 303, 604, 1205, 2408)
MONITOR_INTEGRATION_PANELS = 32768
MONITOR_EDGE_CONVERGENCE_TARGET = 5.0e-9
P1_GROUP_LIMIT = 2408


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


def _stencil(group_count: int, fraction: float, maximum_beta: float):
    grid = hydrogen_photoionization_monitor_group_grid(
        *PHYSICAL_ENERGY_RANGE_EV,
        group_count,
        fraction,
        integration_panels_per_segment=MONITOR_INTEGRATION_PANELS,
    )
    return grid, mixed_frame_frequency_stencil_from_active_edges(
        grid.group_edge_hz, maximum_beta
    )


def _grid_controls(maximum_beta: float) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for fraction in FOCUS_FRACTIONS:
        for group_count in PHYSICAL_GROUP_COUNTS:
            grid, stencil = _stencil(group_count, fraction, maximum_beta)
            row: dict[str, object] = {
                "focus_fraction": fraction,
                "requested_physical_groups": group_count,
                "physical_frequency_groups": stencil.physical_group_count,
                "spectral_degrees_of_freedom": 2 * stencil.physical_group_count,
                "segment_below_H_I": int(grid.segment_group_count[0]),
                "segment_H_I_to_He_I": int(grid.segment_group_count[1]),
                "segment_He_I_to_He_II": int(grid.segment_group_count[2]),
                "segment_above_He_II": int(grid.segment_group_count[3]),
                "minimum_group_width_ev": float(np.min(np.diff(grid.group_edge_ev))),
                "maximum_group_width_ev": float(np.max(np.diff(grid.group_edge_ev))),
                "all_thresholds_exact": bool(
                    all(
                        np.count_nonzero(grid.group_edge_ev == threshold) == 1
                        for threshold in (13.60, 24.59, 54.42)
                    )
                ),
                "strictly_positive_widths": bool(
                    np.all(np.diff(grid.group_edge_ev) > 0.0)
                ),
            }
            if group_count == max(PHYSICAL_GROUP_COUNTS):
                fine = hydrogen_photoionization_monitor_group_grid(
                    *PHYSICAL_ENERGY_RANGE_EV,
                    group_count,
                    fraction,
                    integration_panels_per_segment=2
                    * MONITOR_INTEGRATION_PANELS,
                )
                row["monitor_edge_convergence_relative"] = float(
                    np.max(
                        np.abs(grid.group_edge_ev - fine.group_edge_ev)
                        / fine.group_edge_ev
                    )
                )
                row["monitor_segment_count_stable"] = bool(
                    np.array_equal(
                        grid.segment_group_count, fine.segment_group_count
                    )
                )
            rows.append(row)
    return rows


def _moving_equilibrium_control(
    fraction: float, maximum_beta: float
) -> dict[str, object]:
    beta = np.array([0.05])
    grid, stencil = _stencil(604, fraction, max(maximum_beta, float(beta[0])))
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    transform = lorentz_ray_transform(mu, weight, beta)
    value = 1.7
    outer_mean = np.broadcast_to(
        value * transform.doppler_lab_to_comoving[None, ...] ** -4.0,
        (stencil.outer_lab_group_count, mu.size, 1),
    ).copy()
    active = outer_mean[_active_slice(stencil)]
    collision_shape = (stencil.comoving_collision_group_count, 1)
    absorption = np.full(collision_shape, 0.6)
    scattering = np.full(collision_shape, 0.4)
    result = solve_mixed_frame_ale_log_p1_group_step(
        stencil,
        [0.0, 1.0],
        [0.005, 1.005],
        mu,
        weight,
        active,
        0.0,
        outer_mean,
        0.0,
        absorption,
        0.0,
        value * absorption,
        0.0,
        scattering,
        0.0,
        beta,
        0.1,
        periodic_spatial_boundary=True,
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-12,
    )
    error = float(
        np.max(np.abs(result.final_lab_mean_intensity_energy_density - active))
        / np.max(active)
    )
    return {
        "control": "rate-monitor log-P1 moving equilibrium",
        "focus_fraction": fraction,
        "physical_frequency_groups": stencil.physical_group_count,
        "segment_group_count": grid.segment_group_count.tolist(),
        "equilibrium_error": error,
        "global_coupled_residual": result.global_scale_normalized_coupled_residual,
        "total_energy_ledger_residual": result.total_relative_energy_ledger_residual,
        "minimum_reconstructed_intensity": (
            result.minimum_reconstructed_intensity_energy_density
        ),
        "final_limiter_count": result.final_limiter_activation_count,
        "passed": bool(
            error < ACTUAL_FREQUENCY_TARGET
            and result.global_scale_normalized_coupled_residual
            < COUPLED_RESIDUAL_TARGET
            and result.total_relative_energy_ledger_residual
            < ENERGY_LEDGER_TARGET
            and result.minimum_reconstructed_intensity_energy_density >= 0.0
        ),
    }


def _actual_state_convergence(material, full, audit):
    definitions = _actual_case_definitions(material, full, audit)
    references: dict[str, dict[str, float]] = {}
    for definition in definitions:
        _, reference, _ = _p0_actual_one_cell_run(
            material,
            full,
            audit,
            definition,
            REFERENCE_P0_GROUPS_PER_DECADE,
        )
        references[str(definition["case"])] = reference
    raw_rows: list[dict[str, object]] = []
    convergence: list[dict[str, object]] = []
    maximum_beta = float(audit["maximum_velocity_beta"])
    for fraction in FOCUS_FRACTIONS:
        for group_count in PHYSICAL_GROUP_COUNTS:
            grid, stencil = _stencil(group_count, fraction, maximum_beta)
            for definition in definitions:
                case = str(definition["case"])
                row, diagnostics = _actual_one_cell_run_log_p1(
                    material,
                    full,
                    audit,
                    definition,
                    group_count,
                    stencil_override=stencil,
                )
                row["representation"] = "H I rate-monitor log-P1"
                row["groups_per_decade"] = ""
                row["resolution_parameter"] = group_count
                row["requested_physical_groups"] = group_count
                row["focus_fraction"] = fraction
                row["segment_group_count"] = ";".join(
                    str(value) for value in grid.segment_group_count
                )
                raw_rows.append(row)
                errors = _relative_component_errors(
                    diagnostics, references[case]
                )
                convergence.append(
                    {
                        "case": case,
                        "representation": "H I rate-monitor log-P1",
                        "focus_fraction": fraction,
                        "physical_frequency_groups": stencil.physical_group_count,
                        "spectral_degrees_of_freedom": 2
                        * stencil.physical_group_count,
                        **{
                            f"{name}_error": value
                            for name, value in errors.items()
                        },
                        "maximum_error": max(errors.values()),
                        "reference": False,
                    }
                )
    return raw_rows, convergence, references


def _plot_convergence(path: Path, convergence) -> None:
    cases = (
        "cold coefficient surface",
        "maximum cell speed",
        "maximum width change",
    )
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8), constrained_layout=True)
    for axis, case in zip(axes, cases, strict=True):
        for fraction in FOCUS_FRACTIONS:
            rows = sorted(
                (
                    row
                    for row in convergence
                    if row["case"] == case
                    and row["focus_fraction"] == fraction
                ),
                key=lambda row: int(row["physical_frequency_groups"]),
            )
            axis.loglog(
                [row["physical_frequency_groups"] for row in rows],
                [row["maximum_error"] for row in rows],
                marker="o",
                label=f"focus={fraction:.2f}",
            )
        axis.axhline(
            ACTUAL_FREQUENCY_TARGET,
            color="black",
            linestyle=":",
            label="precision gate",
        )
        axis.set_xlabel("Physical frequency groups")
        axis.set_ylabel("Maximum relative error")
        axis.set_title(case)
        axis.xaxis.set_major_locator(FixedLocator(PHYSICAL_GROUP_COUNTS))
        axis.xaxis.set_major_formatter(
            FixedFormatter([str(value) for value in PHYSICAL_GROUP_COUNTS])
        )
        axis.xaxis.set_minor_formatter(NullFormatter())
        axis.tick_params(axis="x", labelrotation=30)
        axis.grid(alpha=0.25, which="both")
    axes[0].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_sensitivity(path: Path, convergence, raw_rows, grid_controls) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13.0, 8.0), constrained_layout=True)
    cases = (
        "cold coefficient surface",
        "maximum cell speed",
        "maximum width change",
    )
    for case in cases:
        rows = sorted(
            (
                row
                for row in convergence
                if row["case"] == case
                and row["physical_frequency_groups"] == 2408
            ),
            key=lambda row: float(row["focus_fraction"]),
        )
        axes[0, 0].plot(
            [row["focus_fraction"] for row in rows],
            [row["maximum_error"] for row in rows],
            marker="o",
            label=case,
        )
    axes[0, 0].axhline(ACTUAL_FREQUENCY_TARGET, color="black", linestyle=":")
    axes[0, 0].set_yscale("log")
    axes[0, 0].set_xlabel("H I kernel focus fraction")
    axes[0, 0].set_ylabel("Maximum relative error")
    axes[0, 0].set_title("Highest-budget focus sensitivity")
    axes[0, 0].grid(alpha=0.25, which="both")
    axes[0, 0].legend(fontsize=8)

    highest_grid = sorted(
        (
            row
            for row in grid_controls
            if row["physical_frequency_groups"] == 2408
        ),
        key=lambda row: float(row["focus_fraction"]),
    )
    fractions = np.array([row["focus_fraction"] for row in highest_grid])
    bottom = np.zeros(fractions.size)
    for field, label in (
        ("segment_below_H_I", "below H I"),
        ("segment_H_I_to_He_I", "H I to He I"),
        ("segment_He_I_to_He_II", "He I to He II"),
        ("segment_above_He_II", "above He II"),
    ):
        values = np.array([row[field] for row in highest_grid])
        axes[0, 1].bar(fractions, values, bottom=bottom, width=0.12, label=label)
        bottom += values
    axes[0, 1].set_xlabel("H I kernel focus fraction")
    axes[0, 1].set_ylabel("Frequency groups")
    axes[0, 1].set_title("2408-group allocation")
    axes[0, 1].legend(fontsize=8)
    axes[0, 1].grid(alpha=0.25, axis="y")

    for case in cases:
        rows = sorted(
            (row for row in raw_rows if row["case"] == case),
            key=lambda row: (float(row["focus_fraction"]), int(row["physical_frequency_groups"])),
        )
        selected = [row for row in rows if row["physical_frequency_groups"] == 2408]
        axes[1, 0].plot(
            [row["focus_fraction"] for row in selected],
            [row["global_coupled_residual"] for row in selected],
            marker="o",
            label=case,
        )
        axes[1, 1].plot(
            [row["focus_fraction"] for row in selected],
            [row["solver_final_limiter_count"] for row in selected],
            marker="o",
            label=case,
        )
    axes[1, 0].axhline(COUPLED_RESIDUAL_TARGET, color="black", linestyle=":")
    axes[1, 0].set_yscale("log")
    axes[1, 0].set_xlabel("H I kernel focus fraction")
    axes[1, 0].set_ylabel("Coupled residual")
    axes[1, 0].set_title("Highest-budget operator residual")
    axes[1, 0].grid(alpha=0.25, which="both")
    axes[1, 0].legend(fontsize=8)
    axes[1, 1].set_xlabel("H I kernel focus fraction")
    axes[1, 1].set_ylabel("Final limiter activations")
    axes[1, 1].set_title("Highest-budget realizability cost")
    axes[1, 1].grid(alpha=0.25)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5b_summary.json",
        "controls": output_dir / "phase7b5b_controls.csv",
        "states": output_dir / "phase7b5b_actual_states.csv",
        "convergence": output_dir / "phase7b5b_state_convergence.csv",
        "convergence_plot": output_dir / "phase7b5b_rate_kernel_convergence.png",
        "sensitivity_plot": output_dir / "phase7b5b_rate_kernel_sensitivity.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    audit = _trajectory_velocity_audit(material, full)
    maximum_beta = float(audit["maximum_velocity_beta"])
    grid_controls = _grid_controls(maximum_beta)
    equilibrium_controls = [
        _moving_equilibrium_control(fraction, maximum_beta)
        for fraction in FOCUS_FRACTIONS
    ]
    raw_rows, convergence, references = _actual_state_convergence(
        material, full, audit
    )
    highest = [
        row for row in convergence if row["physical_frequency_groups"] == 2408
    ]
    fraction_worst_error = {
        str(fraction): max(
            float(row["maximum_error"])
            for row in highest
            if row["focus_fraction"] == fraction
        )
        for fraction in FOCUS_FRACTIONS
    }
    best_fraction = min(
        FOCUS_FRACTIONS, key=lambda value: fraction_worst_error[str(value)]
    )
    passing_fraction = [
        fraction
        for fraction in FOCUS_FRACTIONS
        if fraction_worst_error[str(fraction)] < ACTUAL_FREQUENCY_TARGET
    ]
    robust_frequency_gate = any(
        left in passing_fraction and right in passing_fraction
        for left, right in zip(FOCUS_FRACTIONS[:-1], FOCUS_FRACTIONS[1:], strict=True)
    )
    edge_gate = all(
        float(row["monitor_edge_convergence_relative"])
        < MONITOR_EDGE_CONVERGENCE_TARGET
        and bool(row["monitor_segment_count_stable"])
        for row in grid_controls
        if row["physical_frequency_groups"] == 2408
    )
    operator_gate = bool(
        all(control["passed"] for control in equilibrium_controls)
        and all(
            float(row["global_coupled_residual"]) < COUPLED_RESIDUAL_TARGET
            and float(row["total_energy_ledger_residual"]) < ENERGY_LEDGER_TARGET
            and float(row["minimum_reconstructed_intensity"]) >= 0.0
            for row in raw_rows
        )
    )
    efficiency_gate = bool(
        robust_frequency_gate
        and max(PHYSICAL_GROUP_COUNTS) <= P1_GROUP_LIMIT
        and 2 * max(PHYSICAL_GROUP_COUNTS) <= SPECTRAL_DOF_LIMIT
    )
    component_gate = bool(edge_gate and operator_gate and efficiency_gate)
    decision = {
        "monitor_grid_convergence_passed": edge_gate,
        "all_moving_equilibria_passed": bool(
            all(control["passed"] for control in equilibrium_controls)
        ),
        "all_candidate_operator_gate_passed": operator_gate,
        "highest_budget_worst_error_by_focus": fraction_worst_error,
        "best_observed_focus_fraction_not_selected": best_fraction,
        "passing_focus_fractions": passing_fraction,
        "adjacent_focus_robust_frequency_gate_passed": robust_frequency_gate,
        "efficiency_gate_passed": efficiency_gate,
        "rate_kernel_grid_component_gate_passed": component_gate,
        "selected_dynamic_physical_frequency_groups": None,
        "selected_dynamic_spectral_degrees_of_freedom": None,
        "angular_radiation_subgrid_time_gate_authorized": component_gate,
        "full_dynamic_orbit_authorized": False,
        "matter_temperature_population_feedback_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }
    controls = grid_controls + equilibrium_controls
    _write_csv(paths["controls"], controls)
    _write_csv(paths["states"], raw_rows)
    _write_csv(paths["convergence"], convergence)
    _plot_convergence(paths["convergence_plot"], convergence)
    _plot_sensitivity(
        paths["sensitivity_plot"], convergence, raw_rows, grid_controls
    )
    report = {
        "phase": "7B5b",
        "classification": (
            "[A] H I rate-kernel monitor fractions; "
            "[V] fixed-grid geometry, moving equilibria and three actual states; "
            "[O] closed rate-functional moments and full dynamic feedback"
        ),
        "configuration": {
            "physical_energy_range_ev": list(PHYSICAL_ENERGY_RANGE_EV),
            "focus_fractions": list(FOCUS_FRACTIONS),
            "physical_group_counts": list(PHYSICAL_GROUP_COUNTS),
            "spectral_dof_limit": SPECTRAL_DOF_LIMIT,
            "monitor_integration_panels_per_segment": MONITOR_INTEGRATION_PANELS,
            "monitor_edge_convergence_target": MONITOR_EDGE_CONVERGENCE_TARGET,
            "reference_p0_groups_per_decade": REFERENCE_P0_GROUPS_PER_DECADE,
            "reference_p0_physical_frequency_groups": 38496,
            "actual_frequency_target": ACTUAL_FREQUENCY_TARGET,
            "coupled_residual_target": COUPLED_RESIDUAL_TARGET,
            "energy_ledger_target": ENERGY_LEDGER_TARGET,
        },
        "closure_audit": {
            "rejected_shortcut": (
                "a single global H I rate moment is not closed under frequency-dependent "
                "extinction, emissivity, scattering, Lorentz shifts and ALE transport"
            ),
            "implemented_minimum": (
                "retain transportable log-P1 Q=nu*I_nu fields and change only the fixed grid"
            ),
            "hydrogen_rate_kernel": "k_H(y)=sigma_H(nu)/(h nu)",
            "normalized_monitor": (
                "M_f(y)=(1-f)+f*k_H(y)/mean_y(k_H)"
            ),
            "threshold_rule": "13.60, 24.59 and 54.42 eV remain exact group edges",
            "robust_selection_rule": (
                "at least two adjacent predeclared focus fractions must pass all three states"
            ),
        },
        "grid_controls": grid_controls,
        "moving_equilibrium_controls": equilibrium_controls,
        "actual_states": raw_rows,
        "state_convergence": convergence,
        "finite_reference_values": references,
        "decision": decision,
        "open_items": [
            "the 38496-group P0 comparison is a finite reference, not continuum truth",
            "focus fractions are numerical assumptions and are reported as a sensitivity family",
            "the best observed focus fraction is not promoted unless the adjacent-fraction rule passes",
            "an exact extra H I rate moment would require a separately closed transport representation",
            "angular, radiation-subgrid, orbit-time and matter-feedback gates remain closed",
            "excited levels, cascades, Compton redistribution and line transfer remain open",
        ],
        "figures": {
            "rate_kernel_convergence": paths["convergence_plot"].name,
            "rate_kernel_sensitivity": paths["sensitivity_plot"].name,
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
