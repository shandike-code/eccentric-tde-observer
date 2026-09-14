"""生成 Phase 7B4r 的 N128、2048 相位独立周期物质参考。"""

from __future__ import annotations

import argparse
import json
import time
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
from eccentric_tde_observer.periodic_dynamic_atmosphere import (
    PeriodicDynamicCycleCheckpoint,
    solve_periodic_dynamic_column,
)

try:
    from scripts.phase7b4n_joint_depth_time_reference import (
        CONSERVATION_TOLERANCE,
        CYCLE_TOLERANCE,
        MAXIMUM_TEMPERATURE_K,
        MAXIMUM_TOTAL_CYCLES,
        MINIMUM_TEMPERATURE_K,
        PRODUCTION_TOLERANCE,
        CaseSpec,
        _initial_residuals,
        _load_checkpoint,
        _save_checkpoint_atomic,
        _save_solution_atomic,
        case_paths,
        load_case,
    )
    from scripts.phase7b4o_high_depth_time_reference import (
        CONTINUOUS_METRICS,
        METRIC_LABELS,
        _reference_phase_rows,
        _write_csv,
        population_error_locations,
        time_convergence_rows,
    )
    from scripts.phase7b4q_threshold_quadrature import (
        DEPTH_REFERENCE_CASE,
        DEPTH_REFERENCE_POINTS,
        _depth128_grid_and_initial,
        _uniform_restriction_residuals,
        _write_json_atomic,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b4n_joint_depth_time_reference import (
        CONSERVATION_TOLERANCE,
        CYCLE_TOLERANCE,
        MAXIMUM_TEMPERATURE_K,
        MAXIMUM_TOTAL_CYCLES,
        MINIMUM_TEMPERATURE_K,
        PRODUCTION_TOLERANCE,
        CaseSpec,
        _initial_residuals,
        _load_checkpoint,
        _save_checkpoint_atomic,
        _save_solution_atomic,
        case_paths,
        load_case,
    )
    from phase7b4o_high_depth_time_reference import (
        CONTINUOUS_METRICS,
        METRIC_LABELS,
        _reference_phase_rows,
        _write_csv,
        population_error_locations,
        time_convergence_rows,
    )
    from phase7b4q_threshold_quadrature import (
        DEPTH_REFERENCE_CASE,
        DEPTH_REFERENCE_POINTS,
        _depth128_grid_and_initial,
        _uniform_restriction_residuals,
        _write_json_atomic,
    )


REFERENCE_PHASE_POINTS = 2048
REFERENCE_CASE = CaseSpec(
    "depth128_phase2048",
    REFERENCE_PHASE_POINTS,
    DEPTH_REFERENCE_POINTS,
    output_phase="phase7b4r",
)


def _require_phase7b4q(output_dir: Path) -> dict[str, object]:
    """只在 7B4q 冻结形式数值底座已通过后继续。"""
    path = output_dir / "phase7b4q_summary.json"
    if not path.exists():
        raise FileNotFoundError("Phase 7B4q summary is required")
    report = json.loads(path.read_text(encoding="utf-8"))
    decision = report["decision"]
    if not bool(decision["independent_n128_dynamic_reference_converged"]):
        raise RuntimeError("Phase 7B4q N128 material reference did not converge")
    if not bool(decision["phase7b4q_selected_formal_configuration_passed"]):
        raise RuntimeError("Phase 7B4q selected frozen formal configuration failed")
    return report


def run_reference_case(
    output_dir: Path,
    master_edges_path: Path,
    *,
    force: bool,
) -> None:
    """独立推进 N128、2048 相位周期解，不从 1024 相位成品热启动。"""
    spec = REFERENCE_CASE
    npz_path, report_path, checkpoint_path = case_paths(output_dir, spec)
    if force:
        for path in (npz_path, report_path, checkpoint_path):
            path.unlink(missing_ok=True)
    if npz_path.exists() or report_path.exists():
        if not npz_path.exists() or not report_path.exists():
            raise FileExistsError("a partial completed Phase 7B4r case exists")
        load_case(output_dir, spec)
        print(f"reusing {report_path.name}", flush=True)
        return

    frequency, _, parent, grid, initial = _depth128_grid_and_initial(
        master_edges_path,
        phase_points=spec.phase_points,
    )
    initial_residuals = _initial_residuals(initial)
    completed_offset = 0
    accumulated_runtime = 0.0
    temperature = np.array(initial.temperature_k, copy=True)
    hydrogen = np.array(initial.hydrogen_fraction, copy=True)
    helium = np.array(initial.helium_fraction, copy=True)
    if checkpoint_path.exists():
        (
            completed_offset,
            accumulated_runtime,
            temperature,
            hydrogen,
            helium,
        ) = _load_checkpoint(
            checkpoint_path,
            spec,
            frequency,
            grid.mass_fraction_edges,
        )
        print(
            f"resuming {spec.name} after {completed_offset} complete cycles",
            flush=True,
        )
    remaining_cycles = MAXIMUM_TOTAL_CYCLES - completed_offset
    started = time.perf_counter()

    def save_cycle(checkpoint: PeriodicDynamicCycleCheckpoint) -> None:
        _save_checkpoint_atomic(
            checkpoint_path,
            spec,
            frequency,
            grid.mass_fraction_edges,
            checkpoint,
            completed_offset,
            accumulated_runtime,
            started,
        )
        print(
            json.dumps(
                {
                    "case": spec.name,
                    "completed_cycle_count": (
                        completed_offset + checkpoint.cycle_count
                    ),
                    "cycle_residual": checkpoint.cycle_residual,
                    "checkpoint": checkpoint_path.name,
                }
            ),
            flush=True,
        )

    solution = solve_periodic_dynamic_column(
        grid,
        frequency,
        temperature,
        hydrogen,
        helium,
        include_collisional_kinetics=False,
        minimum_temperature_k=MINIMUM_TEMPERATURE_K,
        maximum_temperature_k=MAXIMUM_TEMPERATURE_K,
        cycle_tolerance=CYCLE_TOLERANCE,
        local_energy_tolerance=2.0e-8,
        optimizer_tolerance=1.0e-10,
        maximum_function_evaluations=96,
        maximum_cycles=remaining_cycles,
        use_colored_tridiagonal_jacobian=True,
        cycle_callback=save_cycle,
    )
    runtime = accumulated_runtime + time.perf_counter() - started
    total_cycles = completed_offset + solution.cycle_count
    conservation = {
        **initial_residuals,
        **_uniform_restriction_residuals(parent, solution),
    }
    conservation_passed = bool(
        max(conservation.values()) < CONSERVATION_TOLERANCE
    )
    _save_solution_atomic(npz_path, spec, solution)
    report = {
        "phase": "7B4r-reference-case",
        "classification": (
            "[A/V] independent N128 2048-phase local-closure material reference"
        ),
        "configuration": {
            "case": spec.name,
            "phase_points": spec.phase_points,
            "depth_points": spec.depth_points,
            "frequency_points": int(frequency.size),
            "uses_colored_tridiagonal_jacobian": True,
            "cycle_tolerance": CYCLE_TOLERANCE,
            "production_tolerance": PRODUCTION_TOLERANCE,
        },
        "provenance": {
            "parent_depth_points": 16,
            "subcells_per_parent": 8,
            "independent_from_completed_n128_phase1024_solution": True,
            "warm_started_from_phase1024_solution": False,
            "legacy_local_dynamic_frequency_closure_retained_for_time_isolation": (
                True
            ),
            "master_edges": master_edges_path.name,
            "resumed_from_completed_cycles": completed_offset,
            "complete_cycle_checkpointing": True,
        },
        "runtime_s": runtime,
        "conservation": conservation,
        "solver": {
            "total_cycle_count": total_cycles,
            "cycles_in_final_invocation": solution.cycle_count,
            "cycle_residual": solution.cycle_residual,
            "maximum_relative_local_energy_residual": (
                solution.maximum_relative_local_energy_residual
            ),
            "maximum_relative_charge_residual": (
                solution.maximum_relative_charge_residual
            ),
            "maximum_particle_conservation_residual": (
                solution.maximum_particle_conservation_residual
            ),
            "minimum_population_fraction": solution.minimum_population_fraction,
            "minimum_temperature_k": solution.minimum_temperature_k,
            "maximum_temperature_k": solution.maximum_temperature_k,
            "cycle_internal_energy_change_erg_cm2": (
                solution.cycle_internal_energy_change_erg_cm2
            ),
            "cycle_compression_work_erg_cm2": (
                solution.cycle_compression_work_erg_cm2
            ),
            "cycle_dissipation_energy_erg_cm2": (
                solution.cycle_dissipation_energy_erg_cm2
            ),
            "cycle_emergent_energy_erg_cm2": (
                solution.cycle_emergent_energy_erg_cm2
            ),
            "relative_cycle_energy_ledger_residual": (
                solution.relative_cycle_energy_ledger_residual
            ),
        },
        "decision": {
            "cycle_converged": bool(solution.cycle_residual <= CYCLE_TOLERANCE),
            "initial_and_restriction_conservation_passed": conservation_passed,
            "case_is_an_independent_time_reference": True,
            "case_is_not_a_nonlocal_dynamic_radiation_solution": True,
        },
        "forbidden_repairs": {
            "nan_to_num": False,
            "arbitrary_clip": False,
            "arbitrary_floor": False,
            "failed_phase_deletion": False,
            "post_hoc_physical_renormalization": False,
        },
    }
    _write_json_atomic(report_path, report)
    checkpoint_path.unlink(missing_ok=True)
    print(json.dumps(report["decision"], indent=2), flush=True)


def _metric_value(error: JointDynamicError, name: str) -> float | None:
    value = getattr(error, name)
    return None if value is None else float(value)


def _case_rows(
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
                "maximum_relative_local_energy_residual": solver[
                    "maximum_relative_local_energy_residual"
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


def n128_time_gate_decision(
    error: JointDynamicError,
    candidate_report: dict[str, object],
    reference_report: dict[str, object],
    inherited_report: dict[str, object],
) -> dict[str, bool]:
    """汇总预声明时间误差、周期闭合、守恒和继承形式门。"""
    time_passed = bool(
        joint_dynamic_error_meets_target(error, PRODUCTION_TOLERANCE)
    )
    cycle_passed = all(
        bool(report["decision"]["cycle_converged"])
        for report in (candidate_report, reference_report)
    )
    conservation_passed = all(
        bool(
            report["decision"][
                "initial_and_restriction_conservation_passed"
            ]
        )
        for report in (candidate_report, reference_report)
    )
    inherited_formal_passed = bool(
        inherited_report["decision"][
            "phase7b4q_selected_formal_configuration_passed"
        ]
    )
    return {
        "n128_phase1024_vs_phase2048_time_difference_below_target": time_passed,
        "both_n128_cases_close_periodically": cycle_passed,
        "both_n128_cases_conserve": conservation_passed,
        "inherited_phase7b4q_formal_gate_passed": inherited_formal_passed,
        "n128_material_depth_time_gate_passed": bool(
            time_passed
            and cycle_passed
            and conservation_passed
            and inherited_formal_passed
        ),
    }


def _column_mean(values: np.ndarray, mass: np.ndarray) -> np.ndarray:
    weight = mass / np.sum(mass)
    return np.sum(values * weight[None, :], axis=1)


def diagnostic_error_locations(
    candidate: DynamicReferenceFields,
    reference: DynamicReferenceFields,
) -> list[dict[str, object]]:
    """定位每个预声明连续场的最大时间离散误差。"""
    aligned = resample_periodic_dynamic_fields(
        candidate, reference.orbital_phase
    )
    centres = 0.5 * (
        reference.mass_fraction_edges[:-1]
        + reference.mass_fraction_edges[1:]
    )
    rows: list[dict[str, object]] = []

    flux_error = np.abs(
        aligned.surface_flux_erg_s_cm2 - reference.surface_flux_erg_s_cm2
    ) / np.abs(reference.surface_flux_erg_s_cm2)
    phase_index = int(np.argmax(flux_error))
    rows.append(
        {
            "metric": "surface flux",
            "error_kind": "relative",
            "maximum_error": float(flux_error[phase_index]),
            "phase_index": phase_index,
            "orbital_phase": float(reference.orbital_phase[phase_index]),
            "depth_index": "",
            "mass_fraction_centre": "",
            "candidate_value": float(
                aligned.surface_flux_erg_s_cm2[phase_index]
            ),
            "reference_value": float(
                reference.surface_flux_erg_s_cm2[phase_index]
            ),
        }
    )

    for name, values, targets, error_kind in (
        (
            "temperature",
            aligned.temperature_k,
            reference.temperature_k,
            "relative",
        ),
        (
            "Rosseland opacity",
            aligned.rosseland_opacity_cm2_g,
            reference.rosseland_opacity_cm2_g,
            "relative",
        ),
        (
            "H II fraction",
            aligned.hydrogen_ionized_fraction,
            reference.hydrogen_ionized_fraction,
            "absolute",
        ),
        (
            "He III fraction",
            aligned.helium_doubly_ionized_fraction,
            reference.helium_doubly_ionized_fraction,
            "absolute",
        ),
    ):
        error = np.abs(values - targets)
        if error_kind == "relative":
            error = error / np.abs(targets)
        phase_index, depth_index = np.unravel_index(
            np.argmax(error), error.shape
        )
        rows.append(
            {
                "metric": name,
                "error_kind": error_kind,
                "maximum_error": float(error[phase_index, depth_index]),
                "phase_index": int(phase_index),
                "orbital_phase": float(reference.orbital_phase[phase_index]),
                "depth_index": int(depth_index),
                "mass_fraction_centre": float(centres[depth_index]),
                "candidate_value": float(values[phase_index, depth_index]),
                "reference_value": float(targets[phase_index, depth_index]),
            }
        )

    for name, values, targets, error_kind in (
        (
            "column-mean temperature",
            _column_mean(aligned.temperature_k, aligned.cell_mass_g_cm2),
            _column_mean(reference.temperature_k, reference.cell_mass_g_cm2),
            "relative",
        ),
        (
            "column-mean Rosseland opacity",
            _column_mean(
                aligned.rosseland_opacity_cm2_g, aligned.cell_mass_g_cm2
            ),
            _column_mean(
                reference.rosseland_opacity_cm2_g,
                reference.cell_mass_g_cm2,
            ),
            "relative",
        ),
        (
            "column-mean H II fraction",
            _column_mean(
                aligned.hydrogen_ionized_fraction, aligned.cell_mass_g_cm2
            ),
            _column_mean(
                reference.hydrogen_ionized_fraction,
                reference.cell_mass_g_cm2,
            ),
            "absolute",
        ),
        (
            "column-mean He III fraction",
            _column_mean(
                aligned.helium_doubly_ionized_fraction,
                aligned.cell_mass_g_cm2,
            ),
            _column_mean(
                reference.helium_doubly_ionized_fraction,
                reference.cell_mass_g_cm2,
            ),
            "absolute",
        ),
    ):
        error = np.abs(values - targets)
        if error_kind == "relative":
            error = error / np.abs(targets)
        phase_index = int(np.argmax(error))
        rows.append(
            {
                "metric": name,
                "error_kind": error_kind,
                "maximum_error": float(error[phase_index]),
                "phase_index": phase_index,
                "orbital_phase": float(reference.orbital_phase[phase_index]),
                "depth_index": "",
                "mass_fraction_centre": "",
                "candidate_value": float(values[phase_index]),
                "reference_value": float(targets[phase_index]),
            }
        )
    return rows


def _plot_time_gate(
    path: Path,
    candidate: DynamicReferenceFields,
    reference: DynamicReferenceFields,
    reference_arrays: dict[str, np.ndarray],
    error: JointDynamicError,
    case_rows: list[dict[str, object]],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.2, 8.5), constrained_layout=True)
    target = reference_arrays["target_surface_flux_erg_s_cm2"]
    candidate_target = np.interp(
        candidate.orbital_phase,
        reference.orbital_phase,
        target,
        period=1.0,
    )
    axes[0, 0].plot(
        candidate.orbital_phase,
        candidate.surface_flux_erg_s_cm2 / candidate_target,
        linestyle="--",
        label="1024 phases",
    )
    axes[0, 0].plot(
        reference.orbital_phase,
        reference.surface_flux_erg_s_cm2 / target,
        color="black",
        label="2048 phases",
    )
    axes[0, 0].set(
        xlabel="Orbital time phase",
        ylabel="Emergent / instantaneous ZO flux",
        title="(a) Independent N128 solutions",
    )
    axes[0, 0].legend(fontsize=8)

    aligned = resample_periodic_dynamic_fields(
        candidate, reference.orbital_phase
    )
    axes[0, 1].plot(
        reference.orbital_phase,
        reference.helium_doubly_ionized_fraction[:, 0],
        color="black",
        label="2048 phases",
    )
    axes[0, 1].plot(
        reference.orbital_phase,
        aligned.helium_doubly_ionized_fraction[:, 0],
        linestyle="--",
        label="1024 phases (periodically aligned)",
    )
    axes[0, 1].set(
        xlabel="Orbital time phase",
        ylabel="Surface-cell He III fraction",
        title="(b) Fast pre-pericentre response",
        xlim=(0.94, 1.0),
    )
    axes[0, 1].legend(fontsize=8)

    metric_pairs = [
        (label, _metric_value(error, name))
        for name, label in zip(CONTINUOUS_METRICS, METRIC_LABELS, strict=True)
    ]
    metric_pairs = [(label, value) for label, value in metric_pairs if value is not None]
    axes[1, 0].bar(
        np.arange(len(metric_pairs)),
        [value for _, value in metric_pairs],
        color="C0",
    )
    axes[1, 0].axhline(
        PRODUCTION_TOLERANCE,
        color="black",
        linestyle=":",
        label="target",
    )
    axes[1, 0].set_yscale("log")
    axes[1, 0].set(
        ylabel="Maximum error",
        xticks=np.arange(len(metric_pairs)),
        xticklabels=[label for label, _ in metric_pairs],
        title="(c) Predeclared time-convergence metrics",
    )
    axes[1, 0].tick_params(axis="x", rotation=30, labelsize=7)
    axes[1, 0].legend(fontsize=8)

    labels = [f"128x{row['phase_points']}" for row in case_rows]
    axes[1, 1].semilogy(
        labels,
        [row["cycle_residual"] for row in case_rows],
        marker="o",
        label="Cycle residual",
    )
    axes[1, 1].semilogy(
        labels,
        [row["relative_cycle_energy_ledger_residual"] for row in case_rows],
        marker="s",
        label="Energy ledger",
    )
    axes[1, 1].axhline(
        CYCLE_TOLERANCE,
        color="black",
        linestyle=":",
        label="cycle target",
    )
    axes[1, 1].set(
        xlabel="Depth x phase points",
        ylabel="Residual",
        title="(d) Periodic closure and conservation",
    )
    axes[1, 1].legend(fontsize=8)
    figure.suptitle("Phase 7B4r: N128 time-resolution gate", fontsize=14)
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
        phase,
        reference.surface_flux_erg_s_cm2 / target,
        color="C3",
    )
    axes[1, 0].axhline(1.0, color="black", linestyle=":")
    axes[1, 0].set(
        xlabel="Orbital time phase",
        ylabel="Emergent / instantaneous ZO flux",
        title="(c) Local-closure thermal memory",
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
        "Phase 7B4r: N128, 2048-phase material reference",
        fontsize=14,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_summary(output_dir: Path, *, force: bool) -> None:
    summary_path = output_dir / "phase7b4r_summary.json"
    if summary_path.exists() and not force:
        print(f"reusing {summary_path.name}", flush=True)
        return
    inherited = _require_phase7b4q(output_dir)
    candidate, candidate_report, _ = load_case(
        output_dir, DEPTH_REFERENCE_CASE
    )
    reference, reference_report, reference_arrays = load_case(
        output_dir, REFERENCE_CASE
    )
    if not np.array_equal(
        candidate.mass_fraction_edges, reference.mass_fraction_edges
    ):
        raise ArithmeticError("N128 time references no longer share exact depth edges")
    error = compare_periodic_time_resolution(candidate, reference)
    convergence_rows = time_convergence_rows(
        [(DEPTH_REFERENCE_CASE, REFERENCE_CASE, error)]
    )
    location_rows = population_error_locations(
        candidate,
        reference,
        DEPTH_REFERENCE_CASE,
        REFERENCE_CASE,
    )
    diagnostic_locations = diagnostic_error_locations(candidate, reference)
    case_rows = _case_rows(
        [
            (DEPTH_REFERENCE_CASE, candidate_report),
            (REFERENCE_CASE, reference_report),
        ]
    )
    gate_decision = n128_time_gate_decision(
        error,
        candidate_report,
        reference_report,
        inherited,
    )

    _write_csv(output_dir / "phase7b4r_time_convergence.csv", convergence_rows)
    _write_csv(
        output_dir / "phase7b4r_population_error_locations.csv",
        location_rows,
    )
    _write_csv(
        output_dir / "phase7b4r_error_locations.csv",
        diagnostic_locations,
    )
    _write_csv(output_dir / "phase7b4r_case_diagnostics.csv", case_rows)
    _write_csv(
        output_dir / "phase7b4r_reference_phase.csv",
        _reference_phase_rows(reference, reference_arrays),
    )
    gate_figure = output_dir / "phase7b4r_time_convergence.png"
    reference_figure = output_dir / "phase7b4r_reference_map.png"
    _plot_time_gate(
        gate_figure,
        candidate,
        reference,
        reference_arrays,
        error,
        case_rows,
    )
    _plot_reference_map(reference_figure, reference, reference_arrays)

    report = {
        "phase": "7B4r-summary",
        "classification": "[A/V/O] N128 finite time-resolution gate",
        "provenance": {
            "candidate_report": case_paths(
                output_dir, DEPTH_REFERENCE_CASE
            )[1].name,
            "reference_report": case_paths(output_dir, REFERENCE_CASE)[1].name,
            "inherited_formal_report": "phase7b4q_summary.json",
            "independent_2048_phase_solution": True,
            "warm_started_from_1024_solution": False,
            "identical_n128_depth_edges": True,
        },
        "configuration": {
            "depth_points": DEPTH_REFERENCE_POINTS,
            "candidate_phase_points": DEPTH_REFERENCE_CASE.phase_points,
            "reference_phase_points": REFERENCE_CASE.phase_points,
            "production_tolerance": PRODUCTION_TOLERANCE,
            "conservation_tolerance": CONSERVATION_TOLERANCE,
            "cycle_tolerance": CYCLE_TOLERANCE,
        },
        "comparison": {
            "n128_phase1024_against_phase2048": asdict(error),
            "population_error_locations": location_rows,
            "diagnostic_error_locations": diagnostic_locations,
        },
        "case_diagnostics": case_rows,
        "decision": {
            **gate_decision,
            "time_dependent_radiation_storage_required": True,
            "dynamic_nonlocal_radiation_microphase_authorized": gate_decision[
                "n128_material_depth_time_gate_passed"
            ],
            "phase4_atmosphere_replacement_authorized": False,
            "uvot_authorized": False,
        },
        "boundaries": {
            "finite_reference_not_continuous_limit": True,
            "local_planck_milne_closure_retained_for_time_isolation": True,
            "ground_state_h_he_only": True,
            "radiation_storage_evolved": False,
            "nonlocal_dynamic_nlte_spectrum_generated": False,
            "observer_spectrum_generated": False,
        },
        "open_items": [
            (
                "The local-closure material time gate does not evolve radiation "
                "energy or frequency-dependent J_nu."
            ),
            (
                "The failed stationary diffusion-time gate requires a coupled "
                "time-dependent nonlocal radiation solver."
            ),
        ],
        "figures": [gate_figure.name, reference_figure.name],
        "forbidden_repairs": {
            "nan_to_num": False,
            "arbitrary_clip": False,
            "arbitrary_floor": False,
            "failed_phase_deletion": False,
            "post_hoc_physical_renormalization": False,
        },
    }
    _write_json_atomic(summary_path, report)
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
        "--stage",
        choices=("case", "summary", "all"),
        default="all",
    )
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    _require_phase7b4q(arguments.output_dir)
    if arguments.stage in ("case", "all"):
        run_reference_case(
            arguments.output_dir,
            arguments.master_edges,
            force=arguments.force,
        )
    if arguments.stage in ("summary", "all"):
        run_summary(arguments.output_dir, force=arguments.force)


if __name__ == "__main__":
    main()
