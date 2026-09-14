"""Phase 7B4y：阈值局域网格与 P1 频率矩的联合准入门。"""

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

from eccentric_tde_observer.mixed_frame_ale_p1 import (
    solve_mixed_frame_ale_p1_group_step,
)
from eccentric_tde_observer.mixed_frame_frequency import lorentz_ray_transform
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
)

try:
    from scripts.phase7b4s_implicit_ale_radiation import (
        _load_material_reference,
        centred_full_column_trajectory,
    )
    from scripts.phase7b4t_mixed_frame_group_gate import (
        _trajectory_velocity_audit,
    )
    from scripts.phase7b4v_mixed_frame_ale_gate import (
        _actual_case_definitions,
        _active_slice,
        _actual_one_cell_run as _p0_actual_one_cell_run,
        _relative_component_errors,
    )
    from scripts.phase7b4w_threshold_frequency_groups import (
        _grid_control_rows,
        _threshold_stencil,
    )
    from scripts.phase7b4x_p1_frequency_moments import (
        ACTUAL_FREQUENCY_TARGET,
        CONTROL_ANGULAR_ORDER,
        COUPLED_RESIDUAL_TARGET,
        ENERGY_LEDGER_TARGET,
        GROUP_QUADRATURE_ORDER,
        P1_GROUP_LIMIT,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        SPECTRAL_DOF_LIMIT,
        _actual_one_cell_run_p1,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b4s_implicit_ale_radiation import (  # type: ignore[no-redef]
        _load_material_reference,
        centred_full_column_trajectory,
    )
    from phase7b4t_mixed_frame_group_gate import (  # type: ignore[no-redef]
        _trajectory_velocity_audit,
    )
    from phase7b4v_mixed_frame_ale_gate import (  # type: ignore[no-redef]
        _actual_case_definitions,
        _active_slice,
        _actual_one_cell_run as _p0_actual_one_cell_run,
        _relative_component_errors,
    )
    from phase7b4w_threshold_frequency_groups import (  # type: ignore[no-redef]
        _grid_control_rows,
        _threshold_stencil,
    )
    from phase7b4x_p1_frequency_moments import (  # type: ignore[no-redef]
        ACTUAL_FREQUENCY_TARGET,
        CONTROL_ANGULAR_ORDER,
        COUPLED_RESIDUAL_TARGET,
        ENERGY_LEDGER_TARGET,
        GROUP_QUADRATURE_ORDER,
        P1_GROUP_LIMIT,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        SPECTRAL_DOF_LIMIT,
        _actual_one_cell_run_p1,
    )


THRESHOLD_P1_PANELS_PER_DECADE = (16, 32, 64, 128, 256)


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    temporary = path.with_name(f"{path.name}.tmp")
    fieldnames = list(rows[0])
    for row in rows[1:]:
        fieldnames.extend(name for name in row if name not in fieldnames)
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _threshold_p1_moving_equilibrium(maximum_beta: float) -> dict[str, object]:
    beta = np.array([0.05])
    panels = 64
    stencil = _threshold_stencil(panels, max(maximum_beta, float(beta[0])))
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    transform = lorentz_ray_transform(mu, weight, beta)
    value = 1.7
    outer_mean = np.broadcast_to(
        value * transform.doppler_lab_to_comoving[None, ...] ** -3.0,
        (stencil.outer_lab_group_count, mu.size, 1),
    ).copy()
    outer_moment = np.zeros_like(outer_mean)
    active = outer_mean[_active_slice(stencil)]
    collision_shape = (stencil.comoving_collision_group_count, 1)
    absorption = np.full(collision_shape, 0.6)
    scattering = np.full(collision_shape, 0.4)
    result = solve_mixed_frame_ale_p1_group_step(
        stencil,
        [0.0, 1.0],
        [0.005, 1.005],
        mu,
        weight,
        active,
        0.0,
        outer_mean,
        outer_moment,
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
        np.max(np.abs(result.final_lab_mean_intensity_density - active))
        / np.max(active)
    )
    return {
        "control": "threshold-local P1 moving equilibrium",
        "panels_per_transformed_decade": panels,
        "physical_frequency_groups": stencil.physical_group_count,
        "equilibrium_error": error,
        "global_coupled_residual": result.global_scale_normalized_coupled_residual,
        "total_energy_ledger_residual": result.total_relative_energy_ledger_residual,
        "minimum_reconstructed_intensity": result.minimum_reconstructed_intensity,
        "final_limiter_count": result.final_limiter_activation_count,
        "passed": bool(
            error < ACTUAL_FREQUENCY_TARGET
            and result.global_scale_normalized_coupled_residual
            < COUPLED_RESIDUAL_TARGET
            and result.total_relative_energy_ledger_residual
            < ENERGY_LEDGER_TARGET
            and result.minimum_reconstructed_intensity >= 0.0
        ),
    }


def _actual_state_convergence(material, full, audit):
    definitions = _actual_case_definitions(material, full, audit)
    raw_rows: list[dict[str, object]] = []
    convergence: list[dict[str, object]] = []
    references: dict[str, dict[str, float]] = {}
    maximum_beta = float(audit["maximum_velocity_beta"])
    for definition in definitions:
        case = str(definition["case"])
        _, reference, _ = _p0_actual_one_cell_run(
            material,
            full,
            audit,
            definition,
            REFERENCE_P0_GROUPS_PER_DECADE,
        )
        references[case] = reference
        for panels in THRESHOLD_P1_PANELS_PER_DECADE:
            stencil = _threshold_stencil(panels, maximum_beta)
            row, diagnostics = _actual_one_cell_run_p1(
                material,
                full,
                audit,
                definition,
                panels,
                stencil_override=stencil,
                representation="threshold-local P1",
            )
            raw_rows.append(row)
            errors = _relative_component_errors(diagnostics, reference)
            convergence.append(
                {
                    "case": case,
                    "representation": "threshold-local P1",
                    "panels_per_transformed_decade": panels,
                    "physical_frequency_groups": row["physical_frequency_groups"],
                    "spectral_degrees_of_freedom": row[
                        "spectral_degrees_of_freedom"
                    ],
                    **{f"{name}_error": value for name, value in errors.items()},
                    "maximum_error": max(errors.values()),
                    "reference": False,
                }
            )
    return raw_rows, convergence, references


def _plot_convergence(path: Path, convergence, selected_groups) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.0), constrained_layout=True)
    cases = sorted({str(row["case"]) for row in convergence})
    for case in cases:
        rows = sorted(
            (row for row in convergence if row["case"] == case),
            key=lambda row: int(row["physical_frequency_groups"]),
        )
        axes[0].loglog(
            [row["physical_frequency_groups"] for row in rows],
            [row["maximum_error"] for row in rows],
            marker="o",
            label=case,
        )
    axes[0].axhline(
        ACTUAL_FREQUENCY_TARGET, color="black", linestyle=":", label="precision gate"
    )
    if selected_groups is not None:
        axes[0].axvline(
            selected_groups, color="tab:green", linestyle="--", label="selected"
        )
    axes[0].set_xlabel("Physical frequency groups")
    axes[0].set_ylabel("Maximum relative error")
    axes[0].set_title("Threshold-local P1 accuracy")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.25, which="both")

    best_groups = selected_groups or max(
        int(row["physical_frequency_groups"]) for row in convergence
    )
    labels = ("energy", "left flux", "right flux", "H I", "He I", "He II", "heating")
    fields = (
        "radiation_energy_error",
        "left_outward_flux_error",
        "right_outward_flux_error",
        "photoionization_H_I_error",
        "photoionization_He_I_error",
        "photoionization_He_II_error",
        "heating_ledger_error",
    )
    width = 0.8 / len(cases)
    x = np.arange(len(labels))
    for index, case in enumerate(cases):
        row = next(
            row
            for row in convergence
            if row["case"] == case
            and int(row["physical_frequency_groups"]) == best_groups
        )
        axes[1].bar(
            x + (index - (len(cases) - 1) / 2.0) * width,
            [row[field] for field in fields],
            width=width,
            label=case,
        )
    axes[1].axhline(ACTUAL_FREQUENCY_TARGET, color="black", linestyle=":")
    axes[1].set_yscale("log")
    axes[1].set_xticks(x, labels, rotation=30, ha="right")
    axes[1].set_ylabel("Relative error")
    axes[1].set_title(f"Component errors at {best_groups} P1 groups")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.25, axis="y", which="both")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_cost(path: Path, raw_rows) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8), constrained_layout=True)
    cases = sorted({str(row["case"]) for row in raw_rows})
    for case in cases:
        rows = sorted(
            (row for row in raw_rows if row["case"] == case),
            key=lambda row: int(row["physical_frequency_groups"]),
        )
        count = [row["physical_frequency_groups"] for row in rows]
        axes[0].loglog(
            count, [row["runtime_s"] for row in rows], marker="o", label=case
        )
        axes[1].plot(
            count,
            [row["solver_final_limiter_count"] for row in rows],
            marker="o",
            label=case,
        )
    axes[0].set_xlabel("Physical frequency groups")
    axes[0].set_ylabel("Runtime (s)")
    axes[0].set_title("One-cell runtime")
    axes[1].set_xscale("log")
    axes[1].set_xlabel("Physical frequency groups")
    axes[1].set_ylabel("Final limiter activations")
    axes[1].set_title("Reported realizability limiting")
    for axis in axes:
        axis.grid(alpha=0.25, which="both")
    axes[0].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b4y_summary.json",
        "controls": output_dir / "phase7b4y_controls.csv",
        "states": output_dir / "phase7b4y_actual_states.csv",
        "convergence": output_dir / "phase7b4y_state_convergence.csv",
        "convergence_plot": output_dir / "phase7b4y_threshold_p1_convergence.png",
        "cost_plot": output_dir / "phase7b4y_threshold_p1_cost.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    audit = _trajectory_velocity_audit(material, full)
    grid_controls = _grid_control_rows(
        float(audit["maximum_velocity_beta"]),
        THRESHOLD_P1_PANELS_PER_DECADE,
    )
    moving_control = _threshold_p1_moving_equilibrium(
        float(audit["maximum_velocity_beta"])
    )
    raw_rows, convergence, references = _actual_state_convergence(
        material, full, audit
    )
    candidate_groups = sorted(
        {int(row["physical_frequency_groups"]) for row in convergence}
    )
    passing_groups = [
        groups
        for groups in candidate_groups
        if max(
            float(row["maximum_error"])
            for row in convergence
            if int(row["physical_frequency_groups"]) == groups
        )
        < ACTUAL_FREQUENCY_TARGET
    ]
    selected_groups = min(passing_groups) if passing_groups else None
    selected_dof = 2 * selected_groups if selected_groups is not None else None
    operator_gate = bool(
        all(bool(row["passed"]) for row in grid_controls)
        and bool(moving_control["passed"])
        and all(
            float(row["global_coupled_residual"]) < COUPLED_RESIDUAL_TARGET
            and float(row["total_energy_ledger_residual"])
            < ENERGY_LEDGER_TARGET
            and float(row["minimum_reconstructed_intensity"]) >= 0.0
            for row in raw_rows
        )
    )
    frequency_gate = selected_groups is not None
    efficiency_gate = bool(
        selected_groups is not None
        and selected_groups <= P1_GROUP_LIMIT
        and selected_dof is not None
        and selected_dof <= SPECTRAL_DOF_LIMIT
    )
    component_gate = bool(operator_gate and frequency_gate and efficiency_gate)
    selected_panels = None
    if component_gate:
        selected_panels = int(
            next(
                row["panels_per_transformed_decade"]
                for row in convergence
                if int(row["physical_frequency_groups"]) == selected_groups
            )
        )
    decision = {
        "threshold_grid_geometry_gate_passed": bool(
            all(bool(row["passed"]) for row in grid_controls)
        ),
        "threshold_p1_moving_equilibrium_passed": bool(moving_control["passed"]),
        "threshold_p1_operator_gate_passed": operator_gate,
        "three_actual_state_frequency_gate_passed": frequency_gate,
        "minimum_passing_physical_frequency_groups": selected_groups,
        "minimum_passing_spectral_degrees_of_freedom": selected_dof,
        "efficiency_gate_passed": efficiency_gate,
        "threshold_p1_component_gate_passed": component_gate,
        "selected_panels_per_transformed_decade": selected_panels,
        "selected_dynamic_physical_frequency_groups": (
            selected_groups if component_gate else None
        ),
        "selected_dynamic_spectral_degrees_of_freedom": (
            selected_dof if component_gate else None
        ),
        "angular_radiation_subgrid_time_gate_authorized": component_gate,
        "full_dynamic_orbit_authorized": False,
        "matter_temperature_population_feedback_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }
    _write_csv(paths["controls"], grid_controls + [moving_control])
    _write_csv(paths["states"], raw_rows)
    _write_csv(paths["convergence"], convergence)
    _plot_convergence(paths["convergence_plot"], convergence, selected_groups)
    _plot_cost(paths["cost_plot"], raw_rows)
    report = {
        "phase": "7B4y",
        "classification": (
            "[A/V] threshold-local conservative P1 frequency representation; "
            "[V] finite three-state component gate; [O] restored convergence axes"
        ),
        "configuration": {
            "physical_energy_range_ev": list(PHYSICAL_ENERGY_RANGE_EV),
            "threshold_p1_panels_per_transformed_decade": list(
                THRESHOLD_P1_PANELS_PER_DECADE
            ),
            "reference_p0_groups_per_decade": REFERENCE_P0_GROUPS_PER_DECADE,
            "reference_p0_physical_frequency_groups": 38496,
            "control_angular_order": CONTROL_ANGULAR_ORDER,
            "group_quadrature_order": GROUP_QUADRATURE_ORDER,
            "actual_frequency_target": ACTUAL_FREQUENCY_TARGET,
            "p1_group_limit": P1_GROUP_LIMIT,
            "spectral_dof_limit": SPECTRAL_DOF_LIMIT,
        },
        "grid_controls": grid_controls,
        "moving_equilibrium_control": moving_control,
        "actual_states": raw_rows,
        "state_convergence": convergence,
        "finite_reference_values": references,
        "decision": decision,
        "open_items": [
            "the 38496-group P0 comparison is finite and not continuum truth",
            "limiter activations preserve group means but alter unresolved slopes",
            "angular, radiation-subgrid and time convergence remain separate gates",
            "matter temperature and populations remain prescribed",
        ],
        "figures": {
            "frequency_convergence": paths["convergence_plot"].name,
            "cost_and_limiter": paths["cost_plot"].name,
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
