"""生成 Phase 7B4o 的 N=64、2048 相位周期动态时间参考。"""

from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import asdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eccentric_tde_observer.joint_dynamic_reference import (
    DynamicReferenceFields,
    JointDynamicError,
    compare_periodic_time_resolution,
    joint_dynamic_error_meets_target,
    resample_periodic_dynamic_fields,
)
try:
    from scripts.phase7b4n_joint_depth_time_reference import (
        CONSERVATION_TOLERANCE,
        CYCLE_TOLERANCE,
        MASTER_DEPTH_POINTS,
        PRODUCTION_TOLERANCE,
        CaseSpec,
        case_paths,
        load_case,
        run_case,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b4n_joint_depth_time_reference import (
        CONSERVATION_TOLERANCE,
        CYCLE_TOLERANCE,
        MASTER_DEPTH_POINTS,
        PRODUCTION_TOLERANCE,
        CaseSpec,
        case_paths,
        load_case,
        run_case,
    )


COARSE_CASE = CaseSpec("depth64_phase512", 512, MASTER_DEPTH_POINTS)
INTERMEDIATE_CASE = CaseSpec("depth64_phase1024", 1024, MASTER_DEPTH_POINTS)
REFERENCE_CASE = CaseSpec(
    "depth64_phase2048", 2048, MASTER_DEPTH_POINTS, "phase7b4o"
)
TIME_CASES = (COARSE_CASE, INTERMEDIATE_CASE, REFERENCE_CASE)

CONTINUOUS_METRICS = (
    "surface_flux_relative_error",
    "maximum_pointwise_temperature_or_opacity_relative_error",
    "maximum_pointwise_population_absolute_error",
    "maximum_column_mean_temperature_or_opacity_relative_error",
    "maximum_column_mean_population_absolute_error",
    "maximum_he_iii_half_front_mass_fraction_error",
)
METRIC_LABELS = (
    "Flux",
    "Point T/kappa",
    "Point population",
    "Column T/kappa",
    "Column population",
    "He III front",
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _metric_value(error: JointDynamicError, name: str) -> float | None:
    value = getattr(error, name)
    return None if value is None else float(value)


def time_convergence_rows(
    comparisons: list[
        tuple[CaseSpec, CaseSpec, JointDynamicError]
    ],
) -> list[dict[str, object]]:
    """把独立时间解的成对误差写成统一、可测试的准入表。"""
    rows: list[dict[str, object]] = []
    previous: JointDynamicError | None = None
    for candidate, reference, error in comparisons:
        row: dict[str, object] = {
            "candidate_case": candidate.name,
            "reference_case": reference.name,
            "candidate_phase_points": candidate.phase_points,
            "reference_phase_points": reference.phase_points,
            **asdict(error),
            "meets_production_target": joint_dynamic_error_meets_target(
                error, PRODUCTION_TOLERANCE
            ),
        }
        for name in CONTINUOUS_METRICS:
            if previous is None:
                row[f"previous_over_current_{name}"] = ""
                continue
            old = _metric_value(previous, name)
            new = _metric_value(error, name)
            row[f"previous_over_current_{name}"] = (
                "" if old is None or new is None or new == 0.0 else old / new
            )
        rows.append(row)
        previous = error
    return rows


def population_error_locations(
    candidate: DynamicReferenceFields,
    reference: DynamicReferenceFields,
    candidate_case: CaseSpec,
    reference_case: CaseSpec,
) -> list[dict[str, object]]:
    """定位 H II 与 He III 的最大时间离散误差，不删除失败相位。"""
    aligned = resample_periodic_dynamic_fields(
        candidate, reference.orbital_phase
    )
    centres = 0.5 * (
        reference.mass_fraction_edges[:-1]
        + reference.mass_fraction_edges[1:]
    )
    rows: list[dict[str, object]] = []
    for name, values, targets in (
        (
            "H II",
            aligned.hydrogen_ionized_fraction,
            reference.hydrogen_ionized_fraction,
        ),
        (
            "He III",
            aligned.helium_doubly_ionized_fraction,
            reference.helium_doubly_ionized_fraction,
        ),
    ):
        error = np.abs(values - targets)
        phase_index, depth_index = np.unravel_index(
            np.argmax(error), error.shape
        )
        rows.append(
            {
                "candidate_case": candidate_case.name,
                "reference_case": reference_case.name,
                "population": name,
                "maximum_absolute_error": float(
                    error[phase_index, depth_index]
                ),
                "phase_index": int(phase_index),
                "orbital_phase": float(reference.orbital_phase[phase_index]),
                "depth_index": int(depth_index),
                "mass_fraction_centre": float(centres[depth_index]),
                "candidate_fraction": float(values[phase_index, depth_index]),
                "reference_fraction": float(targets[phase_index, depth_index]),
            }
        )
    return rows


def _energy_rows(
    loaded: list[tuple[CaseSpec, dict[str, object]]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec, report in loaded:
        solver = report["solver"]
        rows.append(
            {
                "case": spec.name,
                "depth_points": spec.depth_points,
                "phase_points": spec.phase_points,
                "runtime_s": report["runtime_s"],
                "total_cycle_count": solver["total_cycle_count"],
                "cycle_residual": solver["cycle_residual"],
                "cycle_internal_energy_change_erg_cm2": solver[
                    "cycle_internal_energy_change_erg_cm2"
                ],
                "cycle_compression_work_erg_cm2": solver[
                    "cycle_compression_work_erg_cm2"
                ],
                "cycle_dissipation_energy_erg_cm2": solver[
                    "cycle_dissipation_energy_erg_cm2"
                ],
                "cycle_emergent_energy_erg_cm2": solver[
                    "cycle_emergent_energy_erg_cm2"
                ],
                "relative_cycle_energy_ledger_residual": solver[
                    "relative_cycle_energy_ledger_residual"
                ],
                "conservation_passed": report["decision"][
                    "initial_and_restriction_conservation_passed"
                ],
            }
        )
    return rows


def _column_mean(values: np.ndarray, mass: np.ndarray) -> np.ndarray:
    weight = mass / np.sum(mass)
    return np.sum(values * weight[None, :], axis=1)


def _reference_phase_rows(
    reference: DynamicReferenceFields, arrays: dict[str, np.ndarray]
) -> list[dict[str, object]]:
    target = arrays["target_surface_flux_erg_s_cm2"]
    temperature = _column_mean(reference.temperature_k, reference.cell_mass_g_cm2)
    h_ii = _column_mean(
        reference.hydrogen_ionized_fraction, reference.cell_mass_g_cm2
    )
    he_iii = _column_mean(
        reference.helium_doubly_ionized_fraction, reference.cell_mass_g_cm2
    )
    return [
        {
            "phase_index": index,
            "orbital_phase": float(reference.orbital_phase[index]),
            "target_surface_flux_erg_s_cm2": float(target[index]),
            "emergent_surface_flux_erg_s_cm2": float(
                reference.surface_flux_erg_s_cm2[index]
            ),
            "emergent_over_target": float(
                reference.surface_flux_erg_s_cm2[index] / target[index]
            ),
            "column_mean_temperature_k": float(temperature[index]),
            "column_mean_hydrogen_ionized_fraction": float(h_ii[index]),
            "column_mean_helium_doubly_ionized_fraction": float(he_iii[index]),
        }
        for index in range(reference.phase_points)
    ]


def _plot_time_convergence(
    path: Path,
    coarse: DynamicReferenceFields,
    intermediate: DynamicReferenceFields,
    reference: DynamicReferenceFields,
    reference_arrays: dict[str, np.ndarray],
    errors: tuple[JointDynamicError, JointDynamicError],
    energy_rows: list[dict[str, object]],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.2, 8.5), constrained_layout=True)
    target = reference_arrays["target_surface_flux_erg_s_cm2"]
    for fields, label, style in (
        (coarse, "512 phases", ":"),
        (intermediate, "1024 phases", "--"),
        (reference, "2048 phases", "-"),
    ):
        local_target = np.interp(
            fields.orbital_phase,
            reference.orbital_phase,
            target,
            period=1.0,
        )
        axes[0, 0].plot(
            fields.orbital_phase,
            fields.surface_flux_erg_s_cm2 / local_target,
            linestyle=style,
            label=label,
        )
    axes[0, 0].set(
        xlabel="Orbital time phase",
        ylabel="Emergent / instantaneous ZO flux",
        title="(a) Independent high-depth solutions",
    )
    axes[0, 0].legend(fontsize=8)

    aligned = resample_periodic_dynamic_fields(
        intermediate, reference.orbital_phase
    )
    surface = 0
    axes[0, 1].plot(
        reference.orbital_phase,
        reference.helium_doubly_ionized_fraction[:, surface],
        color="black",
        label="2048 phases",
    )
    axes[0, 1].plot(
        reference.orbital_phase,
        aligned.helium_doubly_ionized_fraction[:, surface],
        linestyle="--",
        label="1024 phases (periodically aligned)",
    )
    axes[0, 1].set(
        xlabel="Orbital time phase",
        ylabel="Surface-cell He III fraction",
        title="(b) Fast pre-pericentre ionization response",
        xlim=(0.94, 1.0),
    )
    axes[0, 1].legend(fontsize=8)

    x = np.arange(len(CONTINUOUS_METRICS))
    width = 0.36
    for offset, error, label in (
        (-width / 2.0, errors[0], "512 vs 1024"),
        (width / 2.0, errors[1], "1024 vs 2048"),
    ):
        axes[1, 0].bar(
            x + offset,
            [
                0.0 if _metric_value(error, name) is None else _metric_value(error, name)
                for name in CONTINUOUS_METRICS
            ],
            width,
            label=label,
        )
    axes[1, 0].set_yscale("log")
    axes[1, 0].axhline(
        PRODUCTION_TOLERANCE, color="black", linestyle=":", label="target"
    )
    axes[1, 0].set(
        ylabel="Maximum error",
        xticks=x,
        xticklabels=METRIC_LABELS,
        title="(c) Predeclared time-convergence metrics",
    )
    axes[1, 0].tick_params(axis="x", rotation=30, labelsize=7)
    axes[1, 0].legend(fontsize=7)

    labels = [f"64x{row['phase_points']}" for row in energy_rows]
    axes[1, 1].semilogy(
        labels,
        [row["cycle_residual"] for row in energy_rows],
        marker="o",
        label="Cycle residual",
    )
    axes[1, 1].semilogy(
        labels,
        [row["relative_cycle_energy_ledger_residual"] for row in energy_rows],
        marker="s",
        label="Energy ledger",
    )
    axes[1, 1].axhline(
        CYCLE_TOLERANCE, color="black", linestyle=":", label="cycle target"
    )
    axes[1, 1].set(
        xlabel="Depth x phase points",
        ylabel="Residual",
        title="(d) Periodic closure and energy conservation",
    )
    axes[1, 1].legend(fontsize=8)
    figure.suptitle(
        "Phase 7B4o: N=64 time-resolution closure", fontsize=14
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_reference_map(
    path: Path,
    reference: DynamicReferenceFields,
    arrays: dict[str, np.ndarray],
) -> None:
    phase = reference.orbital_phase
    mass = 0.5 * (
        reference.mass_fraction_edges[:-1] + reference.mass_fraction_edges[1:]
    )
    figure, axes = plt.subplots(2, 2, figsize=(12.2, 8.5), constrained_layout=True)
    image = axes[0, 0].pcolormesh(
        phase,
        mass,
        np.log10(reference.temperature_k).T,
        shading="nearest",
    )
    figure.colorbar(image, ax=axes[0, 0], label="log10 Temperature (K)")
    axes[0, 0].set(
        xlabel="Orbital time phase",
        ylabel="Mass fraction from surface",
        title="(a) Dynamic temperature",
    )

    image = axes[0, 1].pcolormesh(
        phase,
        mass,
        reference.helium_doubly_ionized_fraction.T,
        shading="nearest",
        vmin=0.0,
        vmax=1.0,
    )
    figure.colorbar(image, ax=axes[0, 1], label="He III fraction")
    axes[0, 1].set(
        xlabel="Orbital time phase",
        ylabel="Mass fraction from surface",
        title="(b) Moving He III front",
    )

    target = arrays["target_surface_flux_erg_s_cm2"]
    axes[1, 0].plot(
        phase, reference.surface_flux_erg_s_cm2 / target, color="C3"
    )
    axes[1, 0].axhline(1.0, color="black", linestyle=":")
    axes[1, 0].set(
        xlabel="Orbital time phase",
        ylabel="Emergent / instantaneous ZO flux",
        title="(c) Thermal-memory response",
    )

    axes[1, 1].plot(
        phase,
        _column_mean(
            reference.hydrogen_ionized_fraction,
            reference.cell_mass_g_cm2,
        ),
        label="H II",
    )
    axes[1, 1].plot(
        phase,
        _column_mean(
            reference.helium_doubly_ionized_fraction,
            reference.cell_mass_g_cm2,
        ),
        label="He III",
    )
    axes[1, 1].set(
        xlabel="Orbital time phase",
        ylabel="Column-mean ion fraction",
        title="(d) Periodic ionization memory",
    )
    axes[1, 1].legend(fontsize=8)
    figure.suptitle(
        "Phase 7B4o: N=64, 2048-phase finite dynamic reference", fontsize=14
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _require_inherited_gates(output_dir: Path) -> dict[str, object]:
    path = output_dir / "phase7b4n_complete_report.json"
    if not path.exists():
        raise FileNotFoundError("Phase 7B4n complete report is required")
    report = json.loads(path.read_text(encoding="utf-8"))
    decision = report["decision"]
    if not bool(decision["colored_jacobian_numerical_control_passed"]):
        raise RuntimeError("Phase 7B4n colored-Jacobian control failed")
    if not bool(decision["high_time_62_vs_64_spatial_difference_below_target"]):
        raise RuntimeError("Phase 7B4n high-time spatial gate failed")
    if not bool(decision["all_formal_cases_conserve"]):
        raise RuntimeError("Phase 7B4n formal conservation gate failed")
    return report


def run_summary(output_dir: Path) -> None:
    inherited = _require_inherited_gates(output_dir)
    loaded = [
        (spec, *load_case(output_dir, spec)) for spec in TIME_CASES
    ]
    coarse = loaded[0][1]
    intermediate = loaded[1][1]
    reference = loaded[2][1]
    reference_arrays = loaded[2][3]
    coarse_error = compare_periodic_time_resolution(coarse, intermediate)
    reference_error = compare_periodic_time_resolution(intermediate, reference)
    comparisons = [
        (COARSE_CASE, INTERMEDIATE_CASE, coarse_error),
        (INTERMEDIATE_CASE, REFERENCE_CASE, reference_error),
    ]
    convergence_rows = time_convergence_rows(comparisons)
    location_rows = population_error_locations(
        coarse, intermediate, COARSE_CASE, INTERMEDIATE_CASE
    ) + population_error_locations(
        intermediate, reference, INTERMEDIATE_CASE, REFERENCE_CASE
    )
    energy_rows = _energy_rows(
        [(spec, report) for spec, _, report, _ in loaded]
    )
    all_cycle = all(
        bool(report["decision"]["cycle_converged"])
        for _, _, report, _ in loaded
    )
    all_conserve = all(
        bool(
            report["decision"][
                "initial_and_restriction_conservation_passed"
            ]
        )
        for _, _, report, _ in loaded
    )
    direct_time_pass = bool(
        joint_dynamic_error_meets_target(
            reference_error, PRODUCTION_TOLERANCE
        )
    )
    inherited_spatial_pass = bool(
        inherited["decision"][
            "high_time_62_vs_64_spatial_difference_below_target"
        ]
    )
    joint_gate = bool(
        direct_time_pass
        and inherited_spatial_pass
        and all_cycle
        and all_conserve
    )

    _write_csv(
        output_dir / "phase7b4o_time_convergence.csv", convergence_rows
    )
    _write_csv(
        output_dir / "phase7b4o_population_error_locations.csv",
        location_rows,
    )
    _write_csv(output_dir / "phase7b4o_energy_ledger.csv", energy_rows)
    _write_csv(
        output_dir / "phase7b4o_reference_phase.csv",
        _reference_phase_rows(reference, reference_arrays),
    )
    _plot_time_convergence(
        output_dir / "phase7b4o_time_convergence.png",
        coarse,
        intermediate,
        reference,
        reference_arrays,
        (coarse_error, reference_error),
        energy_rows,
    )
    _plot_reference_map(
        output_dir / "phase7b4o_reference_map.png",
        reference,
        reference_arrays,
    )

    report = {
        "phase": "7B4o-complete",
        "classification": "[A/V/O] high-depth finite time reference",
        "provenance": {
            "inherited_joint_report": "phase7b4n_complete_report.json",
            "case_reports": [
                case_paths(output_dir, spec)[1].name for spec in TIME_CASES
            ],
            "independent_2048_phase_solution": True,
            "warm_started_from_1024_solution": False,
        },
        "configuration": {
            "depth_points": MASTER_DEPTH_POINTS,
            "reference_phase_points": REFERENCE_CASE.phase_points,
            "production_tolerance": PRODUCTION_TOLERANCE,
            "conservation_tolerance": CONSERVATION_TOLERANCE,
            "cycle_tolerance": CYCLE_TOLERANCE,
            "frequency_points": int(
                loaded[2][2]["configuration"]["frequency_points"]
            ),
        },
        "comparison": {
            "high_depth_time_512_against_1024": asdict(coarse_error),
            "high_depth_time_1024_against_2048": asdict(reference_error),
            "population_error_locations": location_rows,
            "finite_refinement_reduction_factors": {
                name: convergence_rows[1][f"previous_over_current_{name}"]
                for name in CONTINUOUS_METRICS
            },
        },
        "energy_ledger": energy_rows,
        "decision": {
            "high_depth_1024_vs_2048_time_difference_below_target": (
                direct_time_pass
            ),
            "inherited_high_time_62_vs_64_spatial_gate_passed": (
                inherited_spatial_pass
            ),
            "all_time_reference_cases_close_periodically": all_cycle,
            "all_time_reference_cases_conserve": all_conserve,
            "joint_depth_time_gate_passed": joint_gate,
            "nonlocal_frequency_dependent_dynamic_transfer_authorized": (
                joint_gate
            ),
            "phase4_atmosphere_replacement_authorized": False,
            "uvot_authorized": False,
            "next_microphase_if_passed": (
                "nonlocal frequency-dependent dynamic transfer on the finite "
                "N=64, phase=2048 reference"
            ),
            "next_microphase_if_failed": (
                "raise the time reference or validate a higher-order time integrator"
            ),
        },
        "boundaries": {
            "finite_reference_not_continuous_limit": True,
            "local_planck_milne_closure_retained": True,
            "ground_state_h_he_only": True,
            "nonlocal_transfer_implemented": False,
            "observer_spectrum_generated": False,
        },
        "forbidden_repairs": {
            "nan_to_num": False,
            "arbitrary_clip": False,
            "arbitrary_floor": False,
            "failed_phase_deletion": False,
            "post_hoc_physical_renormalization": False,
        },
    }
    _write_json_atomic(output_dir / "phase7b4o_complete_report.json", report)
    print(json.dumps(report["decision"], indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--master-edges",
        type=Path,
        default=Path("outputs/phase7b4l_subcell_edges.csv"),
    )
    parser.add_argument(
        "--variable-edges",
        type=Path,
        default=Path("outputs/phase7b4m_variable_edges.csv"),
    )
    parser.add_argument(
        "--stage", choices=("case", "summary", "all"), default="all"
    )
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    _require_inherited_gates(arguments.output_dir)
    if arguments.stage in ("case", "all"):
        run_case(
            arguments.output_dir,
            REFERENCE_CASE,
            arguments.master_edges,
            arguments.variable_edges,
            force=arguments.force,
        )
    if arguments.stage in ("summary", "all"):
        run_summary(arguments.output_dir)


if __name__ == "__main__":
    main()
