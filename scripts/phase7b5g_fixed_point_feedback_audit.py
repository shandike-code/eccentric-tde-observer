"""Phase 7B5g：真实碰撞固定点迭代中的 H I 率误差累积审计。"""

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

from eccentric_tde_observer.log_frequency_moments import (
    comoving_log_frequency_group_p1_radiation,
)
from eccentric_tde_observer.mixed_frame_ale import mixed_frame_frequency_stencil
from eccentric_tde_observer.mixed_frame_frequency import comoving_group_radiation
from eccentric_tde_observer.rate_error_localization import (
    localize_hydrogen_photoionization_rate_error,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
)

try:
    from scripts.phase7b4v_mixed_frame_ale_gate import _boosted_planck_outer
    from scripts.phase7b5a_log_frequency_p1_gate import (
        CONTROL_ANGULAR_ORDER,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _active_slice,
        _actual_case_definitions,
        _actual_one_cell_run_log_p1,
        _boosted_planck_outer_log_p1,
        _collision_physical_slice,
        _load_material_reference,
        _p0_actual_one_cell_run,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from scripts.phase7b5b_rate_kernel_grid_gate import _stencil
    from scripts.phase7b5c_signed_rate_error_localization import (
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
        LOCALIZATION_QUADRATURE_TARGET,
        RATE_RECONCILIATION_TARGET,
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
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _active_slice,
        _actual_case_definitions,
        _actual_one_cell_run_log_p1,
        _boosted_planck_outer_log_p1,
        _collision_physical_slice,
        _load_material_reference,
        _p0_actual_one_cell_run,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from phase7b5b_rate_kernel_grid_gate import _stencil  # type: ignore[no-redef]
    from phase7b5c_signed_rate_error_localization import (  # type: ignore[no-redef]
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
        LOCALIZATION_QUADRATURE_TARGET,
        RATE_RECONCILIATION_TARGET,
        _analysis_edges,
        _regions,
    )
    from phase7b5f_single_pass_intensity_transform import (  # type: ignore[no-redef]
        _state_parameters,
    )


CHECKPOINT_ITERATIONS = (0, 1, 2, 4, 8)
LOCALIZATION_QUADRATURE_ORDERS = (8, 16)
BASELINE_REPRODUCTION_TARGET = 2.0e-12
FINAL_DOMINANCE_FRACTION = 0.5


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


def _saturated_group_count(mean, moment) -> int:
    return int(
        np.count_nonzero(
            (mean > 0.0)
            & (np.abs(moment) == np.nextafter(mean / 3.0, 0.0))
        )
    )


def _region_rows(case: str, checkpoint: str, localization, regions):
    rows = []
    edge = localization.analysis_edge_ev
    absolute_total = float(
        np.sum(localization.absolute_integrand_difference_bin_s1)
    )
    for label, left, right in regions:
        selected = (edge[:-1] >= left) & (edge[1:] <= right)
        signed = float(np.sum(localization.signed_error_bin_s1[selected]))
        absolute = float(
            np.sum(localization.absolute_integrand_difference_bin_s1[selected])
        )
        rows.append(
            {
                "case": case,
                "checkpoint": checkpoint,
                "region": label,
                "minimum_energy_ev": left,
                "maximum_energy_ev": right,
                "signed_rate_error_over_reference": (
                    signed / localization.reference_total_rate_s1
                ),
                "absolute_integrand_difference_fraction": (
                    absolute / absolute_total if absolute_total > 0.0 else 0.0
                ),
            }
        )
    return rows


def _plot_error_growth(path: Path, rows) -> None:
    cases = tuple(dict.fromkeys(row["case"] for row in rows))
    checkpoints = tuple(
        dict.fromkeys(row["checkpoint"] for row in rows if row["case"] == cases[0])
    )
    x = np.arange(len(checkpoints))
    fig, axes = plt.subplots(2, 3, figsize=(15.0, 8.0), constrained_layout=True)
    for column, case in enumerate(cases):
        selected = [row for row in rows if row["case"] == case]
        absolute = [row["absolute_relative_error"] for row in selected]
        signed = [row["signed_relative_error"] for row in selected]
        fraction = [row["absolute_error_fraction_of_converged"] for row in selected]
        axes[0, column].plot(x, absolute, marker="o", label="absolute error")
        axes[0, column].axhline(1.0e-3, color="black", linestyle=":", label="rate gate")
        axes[0, column].set_yscale("log")
        axes[0, column].set_ylabel("Absolute H I rate error")
        axes[0, column].set_title(case)
        axes[0, column].grid(alpha=0.25)
        axes[1, column].plot(x, signed, marker="o", label="signed error")
        axes[1, column].plot(x, fraction, marker="s", label="absolute / converged")
        axes[1, column].axhline(0.0, color="black", linewidth=0.8)
        axes[1, column].axhline(
            FINAL_DOMINANCE_FRACTION, color="tab:green", linestyle="--"
        )
        axes[1, column].set_yscale("symlog", linthresh=1.0e-8)
        axes[1, column].set_ylabel("Signed error or converged fraction")
        axes[1, column].grid(alpha=0.25)
        for axis in (axes[0, column], axes[1, column]):
            axis.set_xticks(x, checkpoints)
            axis.set_xlabel("Source-iteration checkpoint")
    axes[0, 0].legend(fontsize=8)
    axes[1, 0].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_region_evolution(path: Path, region_rows) -> None:
    cases = tuple(dict.fromkeys(row["case"] for row in region_rows))
    checkpoints = tuple(
        dict.fromkeys(
            row["checkpoint"] for row in region_rows if row["case"] == cases[0]
        )
    )
    regions = (
        "H I Doppler band",
        "H I shoulder to He I",
        "He I to He II",
        "above He II",
    )
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 5.0), constrained_layout=True)
    for axis, case in zip(axes, cases, strict=True):
        matrix = np.array(
            [
                [
                    next(
                        row
                        for row in region_rows
                        if row["case"] == case
                        and row["checkpoint"] == checkpoint
                        and row["region"] == region
                    )["absolute_integrand_difference_fraction"]
                    for region in regions
                ]
                for checkpoint in checkpoints
            ]
        )
        image = axis.imshow(matrix, vmin=0.0, vmax=1.0, aspect="auto", cmap="viridis")
        axis.set_xticks(np.arange(len(regions)), regions, rotation=28, ha="right")
        axis.set_yticks(np.arange(len(checkpoints)), checkpoints)
        axis.set_ylabel("Source-iteration checkpoint")
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
    fig.colorbar(image, ax=axes, label="Fraction of absolute H I difference")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5g_summary.json",
        "iterations": output_dir / "phase7b5g_iteration_history.csv",
        "regions": output_dir / "phase7b5g_region_evolution.csv",
        "growth_plot": output_dir / "phase7b5g_fixed_point_error_growth.png",
        "region_plot": output_dir / "phase7b5g_region_evolution.png",
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
    previous_initial = json.loads(
        (output_dir / "phase7b5f_summary.json").read_text(encoding="utf-8")
    )
    initial_by_case = {row["case"]: row for row in previous_initial["states"]}
    previous_final = json.loads(
        (output_dir / "phase7b5e_summary.json").read_text(encoding="utf-8")
    )
    final_by_case = {
        row["case"]: row
        for row in previous_final["component_controls"]
        if row["control"] == "full Lorentz operator"
    }
    rows: list[dict[str, object]] = []
    region_rows: list[dict[str, object]] = []
    definitions = _actual_case_definitions(material, full, audit)
    for definition in definitions:
        case = str(definition["case"])
        p0_selected: dict[int, np.ndarray] = {}
        p0_last: list[np.ndarray] = []

        def observe_p0(iteration, intensity):
            if p0_last:
                p0_last[0] = intensity
            else:
                p0_last.append(intensity)
            if iteration in CHECKPOINT_ITERATIONS:
                p0_selected[iteration] = np.array(intensity, copy=True)

        p1_selected: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        p1_last: list[tuple[np.ndarray, np.ndarray]] = []

        def observe_p1(iteration, mean, moment):
            if p1_last:
                p1_last[0] = (mean, moment)
            else:
                p1_last.append((mean, moment))
            if iteration in CHECKPOINT_ITERATIONS:
                p1_selected[iteration] = (
                    np.array(mean, copy=True),
                    np.array(moment, copy=True),
                )

        reference_row, _, _ = _p0_actual_one_cell_run(
            material,
            full,
            audit,
            definition,
            REFERENCE_P0_GROUPS_PER_DECADE,
            iteration_observer=observe_p0,
        )
        candidate_row, _ = _actual_one_cell_run_log_p1(
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
        candidate_outer = _boosted_planck_outer_log_p1(
            candidate_stencil, mu, weight, beta, temperature
        )
        reference_outer = _boosted_planck_outer(
            reference_stencil, mu, weight, beta, temperature
        )
        checkpoints: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]] = []
        for iteration in CHECKPOINT_ITERATIONS:
            candidate_mean, candidate_moment = p1_selected[iteration]
            checkpoints.append(
                (
                    str(iteration),
                    candidate_mean,
                    candidate_moment,
                    p0_selected[iteration],
                )
            )
        checkpoints.append(
            (
                "converged",
                np.asarray(p1_last[0][0]),
                np.asarray(p1_last[0][1]),
                np.asarray(p0_last[0]),
            )
        )
        case_rows = []
        for checkpoint, lab_mean, lab_moment, lab_reference in checkpoints:
            candidate_outer_mean = np.array(candidate_outer.mean_density, copy=True)
            candidate_outer_moment = np.array(
                candidate_outer.first_moment_density, copy=True
            )
            candidate_outer_mean[_active_slice(candidate_stencil)] = lab_mean
            candidate_outer_moment[_active_slice(candidate_stencil)] = lab_moment
            candidate_comoving = comoving_log_frequency_group_p1_radiation(
                candidate_outer_mean,
                candidate_outer_moment,
                candidate_stencil.outer_lab_edge_hz,
                candidate_stencil.comoving_collision_edge_hz,
                mu,
                weight,
                beta,
            )
            reference_outer_state = np.array(reference_outer, copy=True)
            reference_outer_state[_active_slice(reference_stencil)] = lab_reference
            reference_comoving = comoving_group_radiation(
                reference_outer_state,
                reference_stencil.outer_lab_edge_hz,
                reference_stencil.comoving_collision_edge_hz,
                mu,
                weight,
                beta,
            )
            candidate_physical = _collision_physical_slice(candidate_stencil)
            reference_physical = _collision_physical_slice(reference_stencil)
            candidate_mean = candidate_comoving.mean_intensity_density[
                candidate_physical, 0
            ]
            candidate_moment = (
                candidate_comoving.mean_intensity_first_moment_density[
                    candidate_physical, 0
                ]
            )
            reference_mean = reference_comoving.mean_intensity_density[
                reference_physical, 0
            ]
            localizations = [
                localize_hydrogen_photoionization_rate_error(
                    candidate_stencil.active_lab_edge_hz,
                    candidate_mean,
                    candidate_moment,
                    reference_stencil.active_lab_edge_hz,
                    reference_mean,
                    analysis_edge,
                    quadrature_order_per_native_overlap=order,
                )
                for order in LOCALIZATION_QUADRATURE_ORDERS
            ]
            localization = localizations[-1]
            quadrature_error = max(
                _relative_difference(
                    localizations[0].candidate_total_rate_s1,
                    localization.candidate_total_rate_s1,
                ),
                _relative_difference(
                    localizations[0].reference_total_rate_s1,
                    localization.reference_total_rate_s1,
                ),
            )
            candidate_energy = float(
                np.sum(
                    np.diff(np.log(candidate_stencil.active_lab_edge_hz))
                    * candidate_mean
                )
            )
            reference_energy = float(
                np.sum(
                    np.diff(reference_stencil.active_lab_edge_hz)
                    * reference_mean
                )
            )
            row = {
                "case": case,
                "checkpoint": checkpoint,
                "candidate_fixed_point_iterations": candidate_row[
                    "fixed_point_iterations"
                ],
                "reference_fixed_point_iterations": reference_row[
                    "fixed_point_iterations"
                ],
                "signed_relative_error": localization.signed_relative_error,
                "absolute_relative_error": abs(
                    localization.signed_relative_error
                ),
                "absolute_integrand_difference_relative": (
                    localization.absolute_integrand_difference_relative
                ),
                "candidate_rate_s1": localization.candidate_total_rate_s1,
                "reference_rate_s1": localization.reference_total_rate_s1,
                "candidate_reference_energy_relative_error": (
                    _relative_difference(candidate_energy, reference_energy)
                ),
                "localization_quadrature_relative_error": quadrature_error,
                "candidate_lab_saturated_group_count": _saturated_group_count(
                    lab_mean, lab_moment
                ),
                "candidate_comoving_saturated_group_count": (
                    _saturated_group_count(candidate_mean, candidate_moment)
                ),
                "candidate_comoving_transform_limiter_count": (
                    candidate_comoving.limited_group_count
                ),
            }
            case_rows.append(row)
            region_rows.extend(
                _region_rows(case, checkpoint, localization, regions)
            )
        converged_error = case_rows[-1]["absolute_relative_error"]
        for row in case_rows:
            row["absolute_error_fraction_of_converged"] = (
                row["absolute_relative_error"] / converged_error
                if converged_error > 0.0
                else 0.0
            )
            row["absolute_error_amplification_from_iteration_zero"] = (
                row["absolute_relative_error"]
                / case_rows[0]["absolute_relative_error"]
                if case_rows[0]["absolute_relative_error"] > 0.0
                else 0.0
            )
        rows.extend(case_rows)

    initial_reproduction = max(
        _relative_difference(
            row["signed_relative_error"],
            initial_by_case[row["case"]][
                "candidate_reference_signed_rate_error"
            ],
        )
        for row in rows
        if row["checkpoint"] == "0"
    )
    final_reproduction = max(
        _relative_difference(
            row["signed_relative_error"],
            final_by_case[row["case"]]["signed_relative_error"],
        )
        for row in rows
        if row["checkpoint"] == "converged"
    )
    all_localization_controls_passed = all(
        row["localization_quadrature_relative_error"]
        < LOCALIZATION_QUADRATURE_TARGET
        and np.isfinite(row["candidate_reference_energy_relative_error"])
        for row in rows
    )
    moving_cases = ("maximum cell speed", "maximum width change")
    earliest_dominant: dict[str, str | None] = {}
    for case in moving_cases:
        earliest_dominant[case] = next(
            (
                str(row["checkpoint"])
                for row in rows
                if row["case"] == case
                and row["absolute_error_fraction_of_converged"]
                >= FINAL_DOMINANCE_FRACTION
            ),
            None,
        )
    first_update_dominant = all(
        checkpoint == "1" for checkpoint in earliest_dominant.values()
    )
    valid_reproduction = bool(
        initial_reproduction < BASELINE_REPRODUCTION_TARGET
        and final_reproduction < BASELINE_REPRODUCTION_TARGET
    )
    decision = {
        "iteration_zero_reproduces_phase7b5f": (
            initial_reproduction < BASELINE_REPRODUCTION_TARGET
        ),
        "converged_reproduces_phase7b5e": (
            final_reproduction < BASELINE_REPRODUCTION_TARGET
        ),
        "all_localization_controls_passed": all_localization_controls_passed,
        "earliest_half_final_error_checkpoint_by_moving_case": earliest_dominant,
        "first_collision_update_dominates_both_moving_cases": first_update_dominant,
        "first_update_collision_split_audit_authorized": bool(
            valid_reproduction
            and all_localization_controls_passed
            and first_update_dominant
        ),
        "iterative_recurrence_amplification_audit_authorized": bool(
            valid_reproduction
            and all_localization_controls_passed
            and not first_update_dominant
        ),
        "targeted_operator_remediation_authorized": False,
        "production_frequency_representation_selected": False,
        "angular_radiation_subgrid_time_gate_authorized": False,
        "full_dynamic_orbit_authorized": False,
        "matter_temperature_population_feedback_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }
    _write_csv(paths["iterations"], rows)
    _write_csv(paths["regions"], region_rows)
    _plot_error_growth(paths["growth_plot"], rows)
    _plot_region_evolution(paths["region_plot"], region_rows)
    report = {
        "phase": "7B5g",
        "classification": (
            "[A] checkpoints 0,1,2,4,8,converged and 50% final-error onset; "
            "[V] read-only P1/P0 fixed-point observations, independent comoving "
            "transforms and H I localization; [O] collision-update or recurrence cause"
        ),
        "configuration": {
            "checkpoint_iterations": list(CHECKPOINT_ITERATIONS),
            "localization_quadrature_orders": list(
                LOCALIZATION_QUADRATURE_ORDERS
            ),
            "baseline_reproduction_target": BASELINE_REPRODUCTION_TARGET,
            "final_dominance_fraction": FINAL_DOMINANCE_FRACTION,
            "candidate_focus_fraction": FAILED_FOCUS_FRACTION,
            "candidate_physical_groups": FAILED_PHYSICAL_GROUPS,
            "reference_p0_groups_per_decade": REFERENCE_P0_GROUPS_PER_DECADE,
            "maximum_velocity_beta": maximum_beta,
            "maximum_doppler_factor": doppler_factor,
        },
        "iteration_zero_reproduction_relative": initial_reproduction,
        "converged_reproduction_relative": final_reproduction,
        "iteration_history": rows,
        "region_evolution": region_rows,
        "decision": decision,
        "open_items": [
            "checkpoint observations do not alter the solver fixed point",
            "the 50% onset rule is a diagnostic classification rather than a physical threshold",
            "a first-update result still requires a matched collision-term decomposition",
            "a recurrence result requires a linearized or manufactured amplification audit",
            "no checkpoint authorizes a production frequency representation",
        ],
        "figures": {
            "fixed_point_error_growth": paths["growth_plot"].name,
            "region_evolution": paths["region_plot"].name,
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
