"""Phase 7B5d：Lorentz、ALE 与碰撞动态余项的一因子控制。"""

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

from eccentric_tde_observer.rate_error_localization import (
    localize_hydrogen_photoionization_rate_error,
)

try:
    from scripts.phase7b5a_log_frequency_p1_gate import (
        COUPLED_RESIDUAL_TARGET,
        ENERGY_LEDGER_TARGET,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _actual_case_definitions,
        _actual_one_cell_run_log_p1,
        _load_material_reference,
        _p0_actual_one_cell_run,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from scripts.phase7b5b_rate_kernel_grid_gate import _stencil
    from scripts.phase7b5c_signed_rate_error_localization import (
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
        RATE_RECONCILIATION_TARGET,
        _analysis_edges,
        _regions,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5a_log_frequency_p1_gate import (  # type: ignore[no-redef]
        COUPLED_RESIDUAL_TARGET,
        ENERGY_LEDGER_TARGET,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _actual_case_definitions,
        _actual_one_cell_run_log_p1,
        _load_material_reference,
        _p0_actual_one_cell_run,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from phase7b5b_rate_kernel_grid_gate import _stencil  # type: ignore[no-redef]
    from phase7b5c_signed_rate_error_localization import (  # type: ignore[no-redef]
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
        RATE_RECONCILIATION_TARGET,
        _analysis_edges,
        _regions,
    )


CONTROL_DEFINITIONS = (
    ("full operator", {}),
    ("D = 1 control", {"material_velocity_beta_override": 0.0}),
    ("rigid ALE width control", {"rigid_mesh_control": True}),
    ("no scattering control", {"include_scattering": False}),
    (
        "no true absorption/emission control",
        {"include_true_absorption_emission": False},
    ),
)
LOCALIZATION_QUADRATURE_ORDER = 16
STABLE_MOVING_ERROR_REDUCTION = 0.5
BASELINE_REPRODUCTION_TARGET = 2.0e-12


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


def _region_rows(case: str, control: str, localization, regions):
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
                "control": control,
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


def _plot_control_errors(path: Path, rows) -> None:
    cases = (
        "cold coefficient surface",
        "maximum cell speed",
        "maximum width change",
    )
    controls = [name for name, _ in CONTROL_DEFINITIONS]
    fig, axes = plt.subplots(2, 2, figsize=(14.0, 8.5), constrained_layout=True)
    x = np.arange(len(controls))
    width = 0.8 / len(cases)
    for index, case in enumerate(cases):
        selected = [
            next(row for row in rows if row["case"] == case and row["control"] == control)
            for control in controls
        ]
        position = x + (index - 1) * width
        axes[0, 0].bar(
            position,
            [row["absolute_relative_error"] for row in selected],
            width=width,
            label=case,
        )
        axes[0, 1].bar(
            position,
            [row["signed_relative_error"] for row in selected],
            width=width,
            label=case,
        )
        axes[1, 0].bar(
            position,
            [row["error_ratio_to_full_operator"] for row in selected],
            width=width,
            label=case,
        )
        axes[1, 1].bar(
            position,
            [row["candidate_global_coupled_residual"] for row in selected],
            width=width,
            label=case,
        )
    for axis in axes.flat:
        axis.set_xticks(x, controls, rotation=28, ha="right")
        axis.grid(alpha=0.25, axis="y")
    axes[0, 0].set_yscale("log")
    axes[0, 0].set_ylabel("Absolute H I rate error")
    axes[0, 0].set_title("Controlled candidate-reference errors")
    axes[0, 0].legend(fontsize=8)
    axes[0, 1].axhline(0.0, color="black", linewidth=0.8)
    axes[0, 1].set_yscale("symlog", linthresh=1.0e-8)
    axes[0, 1].set_ylabel("Signed H I rate error")
    axes[0, 1].set_title("Signed response to one-factor controls")
    axes[1, 0].axhline(1.0, color="black", linestyle=":")
    axes[1, 0].axhline(
        1.0 - STABLE_MOVING_ERROR_REDUCTION,
        color="tab:green",
        linestyle="--",
    )
    axes[1, 0].set_yscale("log")
    axes[1, 0].set_ylabel("Absolute error / full-operator error")
    axes[1, 0].set_title("Error-change factor")
    axes[1, 1].axhline(
        COUPLED_RESIDUAL_TARGET, color="black", linestyle=":"
    )
    axes[1, 1].set_yscale("log")
    axes[1, 1].set_ylabel("Candidate coupled residual")
    axes[1, 1].set_title("Controlled operator residual")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_region_response(path: Path, region_rows) -> None:
    cases = (
        "cold coefficient surface",
        "maximum cell speed",
        "maximum width change",
    )
    controls = [name for name, _ in CONTROL_DEFINITIONS]
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
                        and row["control"] == control
                        and row["region"] == region
                    )["absolute_integrand_difference_fraction"]
                    for region in regions
                ]
                for control in controls
            ]
        )
        image = axis.imshow(matrix, vmin=0.0, vmax=1.0, aspect="auto", cmap="viridis")
        axis.set_xticks(np.arange(len(regions)), regions, rotation=30, ha="right")
        axis.set_yticks(np.arange(len(controls)), controls)
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
    fig.colorbar(image, ax=axes, label="Fraction of absolute H I integrand difference")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5d_summary.json",
        "controls": output_dir / "phase7b5d_operator_controls.csv",
        "regions": output_dir / "phase7b5d_region_response.csv",
        "control_plot": output_dir / "phase7b5d_dynamic_operator_controls.png",
        "region_plot": output_dir / "phase7b5d_threshold_region_response.png",
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
    _, stencil = _stencil(
        FAILED_PHYSICAL_GROUPS, FAILED_FOCUS_FRACTION, maximum_beta
    )
    definitions = _actual_case_definitions(material, full, audit)
    rows: list[dict[str, object]] = []
    region_rows: list[dict[str, object]] = []
    for definition in definitions:
        case = str(definition["case"])
        for control_name, control_kwargs in CONTROL_DEFINITIONS:
            reference_row, reference_diagnostics, reference_arrays = (
                _p0_actual_one_cell_run(
                    material,
                    full,
                    audit,
                    definition,
                    REFERENCE_P0_GROUPS_PER_DECADE,
                    **control_kwargs,
                )
            )
            candidate_arrays: dict[str, np.ndarray] = {}
            candidate_row, candidate_diagnostics = _actual_one_cell_run_log_p1(
                material,
                full,
                audit,
                definition,
                FAILED_PHYSICAL_GROUPS,
                stencil_override=stencil,
                diagnostic_arrays=candidate_arrays,
                **control_kwargs,
            )
            localization = localize_hydrogen_photoionization_rate_error(
                candidate_arrays["physical_group_edge_hz"],
                candidate_arrays["final_comoving_mean_intensity_energy"],
                candidate_arrays[
                    "final_comoving_first_moment_intensity_energy"
                ],
                reference_arrays["physical_group_edge_hz"],
                reference_arrays["final_comoving_mean_intensity"],
                analysis_edge,
                quadrature_order_per_native_overlap=(
                    LOCALIZATION_QUADRATURE_ORDER
                ),
            )
            candidate_reconciliation = _relative_difference(
                localization.candidate_total_rate_s1,
                float(candidate_diagnostics["photoionization_H_I"]),
            )
            reference_reconciliation = _relative_difference(
                localization.reference_total_rate_s1,
                float(reference_diagnostics["photoionization_H_I"]),
            )
            rows.append(
                {
                    "case": case,
                    "control": control_name,
                    "focus_fraction": FAILED_FOCUS_FRACTION,
                    "physical_frequency_groups": FAILED_PHYSICAL_GROUPS,
                    "reference_rate_s1": localization.reference_total_rate_s1,
                    "candidate_rate_s1": localization.candidate_total_rate_s1,
                    "signed_relative_error": localization.signed_relative_error,
                    "absolute_relative_error": abs(
                        localization.signed_relative_error
                    ),
                    "absolute_integrand_difference_relative": (
                        localization.absolute_integrand_difference_relative
                    ),
                    "candidate_rate_reconciliation_relative": (
                        candidate_reconciliation
                    ),
                    "reference_rate_reconciliation_relative": (
                        reference_reconciliation
                    ),
                    "candidate_global_coupled_residual": candidate_row[
                        "global_coupled_residual"
                    ],
                    "candidate_energy_ledger_residual": candidate_row[
                        "total_energy_ledger_residual"
                    ],
                    "reference_global_coupled_residual": reference_row[
                        "global_coupled_residual"
                    ],
                    "reference_energy_ledger_residual": reference_row[
                        "total_energy_ledger_residual"
                    ],
                    "candidate_minimum_intensity": candidate_row[
                        "minimum_reconstructed_intensity"
                    ],
                    "reference_minimum_intensity": reference_row[
                        "minimum_intensity"
                    ],
                    "candidate_final_limiter_count": candidate_row[
                        "solver_final_limiter_count"
                    ],
                    "effective_material_velocity_beta": candidate_row[
                        "cell_velocity_beta"
                    ],
                }
            )
            region_rows.extend(
                _region_rows(case, control_name, localization, regions)
            )

    for case in {row["case"] for row in rows}:
        full_error = next(
            row["absolute_relative_error"]
            for row in rows
            if row["case"] == case and row["control"] == "full operator"
        )
        for row in rows:
            if row["case"] == case:
                row["error_ratio_to_full_operator"] = (
                    row["absolute_relative_error"] / full_error
                )
                row["error_reduction_relative_to_full"] = 1.0 - row[
                    "error_ratio_to_full_operator"
                ]

    previous = json.loads(
        (output_dir / "phase7b5c_summary.json").read_text(encoding="utf-8")
    )
    previous_by_case = {
        row["case"]: row for row in previous["case_decomposition"]
    }
    baseline_reproduction = max(
        _relative_difference(
            row["absolute_relative_error"],
            previous_by_case[row["case"]]["total_absolute_relative"],
        )
        for row in rows
        if row["control"] == "full operator"
    )
    all_control_operators_passed = bool(
        all(
            row["candidate_rate_reconciliation_relative"]
            < RATE_RECONCILIATION_TARGET
            and row["reference_rate_reconciliation_relative"]
            < RATE_RECONCILIATION_TARGET
            and row["candidate_global_coupled_residual"]
            < COUPLED_RESIDUAL_TARGET
            and row["candidate_energy_ledger_residual"] < ENERGY_LEDGER_TARGET
            and row["reference_global_coupled_residual"]
            < COUPLED_RESIDUAL_TARGET
            and row["reference_energy_ledger_residual"] < ENERGY_LEDGER_TARGET
            and row["candidate_minimum_intensity"] >= 0.0
            and row["reference_minimum_intensity"] >= 0.0
            for row in rows
        )
    )
    moving_cases = ("maximum cell speed", "maximum width change")
    stable_controls = []
    for control_name, _ in CONTROL_DEFINITIONS[1:]:
        selected = [
            row
            for row in rows
            if row["control"] == control_name and row["case"] in moving_cases
        ]
        if all(
            row["error_reduction_relative_to_full"]
            >= STABLE_MOVING_ERROR_REDUCTION
            for row in selected
        ):
            stable_controls.append(control_name)
    unique_stable = len(stable_controls) == 1
    decision = {
        "baseline_reproduction_passed": baseline_reproduction
        < BASELINE_REPRODUCTION_TARGET,
        "all_control_operators_passed": all_control_operators_passed,
        "stable_moving_error_reduction_controls": stable_controls,
        "unique_stable_dynamic_operator_identified": unique_stable,
        "targeted_operator_remediation_authorized": bool(
            baseline_reproduction < BASELINE_REPRODUCTION_TARGET
            and all_control_operators_passed
            and unique_stable
        ),
        "production_frequency_representation_selected": False,
        "angular_radiation_subgrid_time_gate_authorized": False,
        "full_dynamic_orbit_authorized": False,
        "matter_temperature_population_feedback_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }
    _write_csv(paths["controls"], rows)
    _write_csv(paths["regions"], region_rows)
    _plot_control_errors(paths["control_plot"], rows)
    _plot_region_response(paths["region_plot"], region_rows)
    report = {
        "phase": "7B5d",
        "classification": (
            "[A] one-factor unphysical diagnostic controls and 50% moving-state "
            "reduction criterion; [V] matched candidate/reference recomputation, "
            "operator residuals and threshold-region response; [O] interaction-aware "
            "causal attribution and production remediation"
        ),
        "configuration": {
            "failed_focus_fraction": FAILED_FOCUS_FRACTION,
            "failed_physical_frequency_groups": FAILED_PHYSICAL_GROUPS,
            "reference_p0_groups_per_decade": REFERENCE_P0_GROUPS_PER_DECADE,
            "controls": [name for name, _ in CONTROL_DEFINITIONS],
            "localization_quadrature_order": LOCALIZATION_QUADRATURE_ORDER,
            "stable_moving_error_reduction": STABLE_MOVING_ERROR_REDUCTION,
            "baseline_reproduction_target": BASELINE_REPRODUCTION_TARGET,
            "maximum_velocity_beta": maximum_beta,
            "maximum_doppler_factor": doppler_factor,
        },
        "control_semantics": {
            "D = 1 control": "zero material Lorentz beta with the actual moving ALE mesh",
            "rigid ALE width control": "preserve mean mesh translation and material beta while setting old and new widths equal",
            "no scattering control": "set electron-scattering extinction/source to zero in both candidate and reference",
            "no true absorption/emission control": "set true absorption and thermal emissivity to zero in both candidate and reference",
            "warning": "controls are unphysical localization experiments and their effects are not additive",
        },
        "baseline_reproduction_relative": baseline_reproduction,
        "operator_controls": rows,
        "region_response": region_rows,
        "decision": decision,
        "open_items": [
            "one-factor removal experiments include nonlinear operator interactions",
            "a unique stable reduction is required before targeted remediation",
            "the 38496-group result remains a finite controlled reference",
            "no control is a physical production spectrum",
            "angle, radiation-subgrid, orbit and matter-feedback gates remain closed",
        ],
        "figures": {
            "dynamic_operator_controls": paths["control_plot"].name,
            "threshold_region_response": paths["region_plot"].name,
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
