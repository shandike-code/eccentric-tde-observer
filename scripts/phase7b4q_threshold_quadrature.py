"""生成 Phase 7B4q 阈值频率求积与非局域代表相位审计。"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.atomic_continuum import (
    EV_ERG,
    H_HE_GROUND_STATE_PHOTOIONIZATION_FITS,
    ground_state_saha_factor_cm3,
)
from eccentric_tde_observer.continuum_emission import (
    IONIZATION_ENERGIES_EV,
    ground_state_milne_radiative_rates,
)
from eccentric_tde_observer.joint_dynamic_reference import (
    compare_nested_depth_resolution,
    dynamic_reference_fields,
    joint_dynamic_error_meets_target,
)
from eccentric_tde_observer.frequency_quadrature import (
    integrate_frequency,
    threshold_excess_gauss_legendre_quadrature,
)
from eccentric_tde_observer.nonlocal_dynamic_transfer import (
    FrozenNonlocalTransferPhase,
    solve_frozen_nonlocal_transfer_phase,
)
from eccentric_tde_observer.periodic_dynamic_atmosphere import (
    build_periodic_dynamic_half_column,
    solve_periodic_dynamic_column,
)
from eccentric_tde_observer.radiation import (
    BOLTZMANN_ERG_K,
    LIGHT_SPEED_CM_S,
    planck_nu,
)
from eccentric_tde_observer.subcell_reconstruction import (
    conservative_ground_state_subcells,
    restrict_periodic_dynamic_subcells,
    uniform_mass_subcell_edges,
)
try:
    from scripts.phase7b4p_frozen_nonlocal_transfer import (
        REPRESENTATIVE_PHASES,
        _comparison_metric_rows,
        _load_npz_arrays,
        _mass_reduce_fields,
        _nearest_phase_index,
        _write_csv,
        _write_json_atomic,
        scale_normalized_maximum_error,
    )
    from scripts.phase7b4n_joint_depth_time_reference import (
        CaseSpec,
        CONSERVATION_TOLERANCE,
        CYCLE_TOLERANCE,
        MAXIMUM_TEMPERATURE_K,
        MAXIMUM_TOTAL_CYCLES,
        MINIMUM_TEMPERATURE_K as DYNAMIC_MINIMUM_TEMPERATURE_K,
        PARENT_DEPTH_POINTS,
        PRODUCTION_PHASE_POINTS,
        _background,
        _frequency as _legacy_dynamic_frequency,
        _initial_residuals,
        _initial_state as _legacy_initial_state,
        _load_checkpoint,
        _phase,
        _save_checkpoint_atomic,
        _save_solution_atomic,
        _saved_master_edges,
        case_paths,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b4p_frozen_nonlocal_transfer import (
        REPRESENTATIVE_PHASES,
        _comparison_metric_rows,
        _load_npz_arrays,
        _mass_reduce_fields,
        _nearest_phase_index,
        _write_csv,
        _write_json_atomic,
        scale_normalized_maximum_error,
    )
    from phase7b4n_joint_depth_time_reference import (
        CaseSpec,
        CONSERVATION_TOLERANCE,
        CYCLE_TOLERANCE,
        MAXIMUM_TEMPERATURE_K,
        MAXIMUM_TOTAL_CYCLES,
        MINIMUM_TEMPERATURE_K as DYNAMIC_MINIMUM_TEMPERATURE_K,
        PARENT_DEPTH_POINTS,
        PRODUCTION_PHASE_POINTS,
        _background,
        _frequency as _legacy_dynamic_frequency,
        _initial_residuals,
        _initial_state as _legacy_initial_state,
        _load_checkpoint,
        _phase,
        _save_checkpoint_atomic,
        _save_solution_atomic,
        _saved_master_edges,
        case_paths,
    )


ENERGY_RANGE_EV = (0.1, 5000.0)
MINIMUM_TEMPERATURE_K = 5000.0
ORDER_PER_PANEL = 8
PANELS_PER_TRANSFORMED_DECADE = (1, 2, 4)
ANGULAR_ORDERS = (8, 12, 16, 24)
PRODUCTION_PANELS_PER_TRANSFORMED_DECADE = 2
PRODUCTION_ANGULAR_ORDER = 16
PRODUCTION_TOLERANCE = 1.0e-3
CONTROL_TOLERANCE = 2.0e-8
DEFAULT_WORKERS = 8
DEPTH_REFERENCE_POINTS = 128
DEPTH_REFERENCE_CASE = CaseSpec(
    "depth128_phase1024",
    PRODUCTION_PHASE_POINTS,
    DEPTH_REFERENCE_POINTS,
    output_phase="phase7b4q",
)


def _threshold_scale_ev() -> float:
    return BOLTZMANN_ERG_K * MINIMUM_TEMPERATURE_K / EV_ERG


def _quadrature(panels_per_transformed_decade: int):
    return threshold_excess_gauss_legendre_quadrature(
        ENERGY_RANGE_EV[0],
        ENERGY_RANGE_EV[1],
        panels_per_transformed_decade,
        threshold_scale_ev=_threshold_scale_ev(),
        order_per_panel=ORDER_PER_PANEL,
    )


def run_controls(output_dir: Path, *, force: bool) -> None:
    csv_path = output_dir / "phase7b4q_controls.csv"
    report_path = output_dir / "phase7b4q_controls.json"
    if not force and csv_path.exists() and report_path.exists():
        print(f"reusing {report_path.name}", flush=True)
        return
    production = _quadrature(PRODUCTION_PANELS_PER_TRANSFORMED_DECADE)
    reference = _quadrature(4)
    scale = _threshold_scale_ev()
    rows: list[dict[str, object]] = []

    constant_error = abs(
        np.sum(production.energy_weight_ev)
        - (ENERGY_RANGE_EV[1] - ENERGY_RANGE_EV[0])
    ) / (ENERGY_RANGE_EV[1] - ENERGY_RANGE_EV[0])
    rows.append(
        {
            "control": "constant energy integral",
            "error": constant_error,
            "target": CONTROL_TOLERANCE,
            "passed": constant_error < CONTROL_TOLERANCE,
        }
    )
    step_errors = []
    boundary_errors = []
    for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS:
        active = production.photon_energy_ev > fit.threshold_energy_ev
        step_expected = ENERGY_RANGE_EV[1] - fit.threshold_energy_ev
        step_errors.append(
            abs(np.sum(production.energy_weight_ev[active]) - step_expected)
            / step_expected
        )
        excess = production.photon_energy_ev - fit.threshold_energy_ev
        numerical = np.sum(
            production.energy_weight_ev[active]
            * np.exp(-excess[active] / scale)
        )
        expected = scale * (
            1.0
            - np.exp(
                -(ENERGY_RANGE_EV[1] - fit.threshold_energy_ev) / scale
            )
        )
        boundary_errors.append(abs(numerical - expected) / expected)
    for name, error in (
        ("discontinuous threshold steps", max(step_errors)),
        ("minimum-temperature Milne boundary layers", max(boundary_errors)),
    ):
        rows.append(
            {
                "control": name,
                "error": error,
                "target": CONTROL_TOLERANCE,
                "passed": error < CONTROL_TOLERANCE,
            }
        )

    temperatures = np.array([5000.0, 2.0e4, 2.0e5])
    production_planck = planck_nu(
        production.frequency_hz[:, None], temperatures[None, :]
    )
    reference_planck = planck_nu(
        reference.frequency_hz[:, None], temperatures[None, :]
    )
    planck_error = scale_normalized_maximum_error(
        integrate_frequency(
            production_planck, production.frequency_weight_hz, axis=0
        ),
        integrate_frequency(
            reference_planck, reference.frequency_weight_hz, axis=0
        ),
    )
    rows.append(
        {
            "control": "finite-band Planck energy moment 160 vs 304 nodes",
            "error": planck_error,
            "target": CONTROL_TOLERANCE,
            "passed": planck_error < CONTROL_TOLERANCE,
        }
    )

    rates = ground_state_milne_radiative_rates(
        temperatures,
        production.frequency_hz,
        production_planck,
        frequency_weight_hz=production.frequency_weight_hz,
    )
    saha = np.stack(
        [
            ground_state_saha_factor_cm3(temperatures, energy)
            for energy in IONIZATION_ENERGIES_EV
        ],
        axis=1,
    )
    detailed_balance_error = scale_normalized_maximum_error(
        rates.photoionization_s1 / saha,
        rates.total_recombination_cm3_s,
    )
    rows.append(
        {
            "control": "weighted LTE Milne detailed balance",
            "error": detailed_balance_error,
            "target": CONTROL_TOLERANCE,
            "passed": detailed_balance_error < CONTROL_TOLERANCE,
        }
    )
    for row in rows:
        row["error"] = float(row["error"])
        row["target"] = float(row["target"])
        row["passed"] = bool(row["passed"])
    _write_csv(csv_path, rows)
    report = {
        "phase": "7B4q-controls",
        "classification": "[V] threshold quadrature analytic controls",
        "configuration": {
            "minimum_temperature_k": MINIMUM_TEMPERATURE_K,
            "threshold_scale_ev": scale,
            "production_panels_per_transformed_decade": (
                PRODUCTION_PANELS_PER_TRANSFORMED_DECADE
            ),
            "production_frequency_points": int(production.frequency_hz.size),
            "reference_frequency_points": int(reference.frequency_hz.size),
            "order_per_panel": ORDER_PER_PANEL,
        },
        "controls": rows,
        "decision": {"all_controls_passed": all(row["passed"] for row in rows)},
    }
    _write_json_atomic(report_path, report)
    print(json.dumps(report["decision"], indent=2), flush=True)


@dataclass(frozen=True)
class SelectedTransferTask:
    key: str
    cell_mass_g_cm2: np.ndarray
    density_g_cm3: np.ndarray
    temperature_k: np.ndarray
    hydrogen_fraction: np.ndarray
    helium_fraction: np.ndarray
    panels_per_transformed_decade: int
    angular_order: int
    transfer_subcells_per_material_cell: int = 1
    scattering_linear_solver: str = "dense_lambda"


def _solve_task(
    task: SelectedTransferTask,
) -> tuple[str, dict[str, np.ndarray], float]:
    quadrature = _quadrature(task.panels_per_transformed_decade)
    result = solve_frozen_nonlocal_transfer_phase(
        quadrature.frequency_hz,
        task.cell_mass_g_cm2,
        task.density_g_cm3,
        task.temperature_k,
        task.hydrogen_fraction,
        task.helium_fraction,
        angular_order=task.angular_order,
        frequency_weight_hz=quadrature.frequency_weight_hz,
        transfer_subcells_per_material_cell=(
            task.transfer_subcells_per_material_cell
        ),
        scattering_linear_solver=task.scattering_linear_solver,
    )
    fields = _phase_transfer_fields_weighted(
        result, task.density_g_cm3
    )
    return task.key, fields, result.relative_integrated_energy_residual


def _phase_transfer_fields_weighted(
    result: FrozenNonlocalTransferPhase,
    density_g_cm3: np.ndarray,
) -> dict[str, np.ndarray]:
    return {
        "bolometric_flux": np.array(
            [result.top_outward_bolometric_flux_erg_s_cm2]
        ),
        "radiation_energy_density": 4.0
        * np.pi
        / LIGHT_SPEED_CM_S
        * integrate_frequency(
            result.mean_intensity_top_half_cgs,
            result.frequency_weight_hz,
            axis=0,
        ),
        "radiative_heating": (
            result.radiative_heating_top_half_erg_s_cm3 / density_g_cm3
        ),
        "photoionization": result.nonlocal_rates.photoionization_s1,
        "recombination": result.nonlocal_rates.total_recombination_cm3_s,
    }


def _task(
    key: str,
    dynamic: dict[str, np.ndarray],
    index: int,
    panels: int,
    angle: int,
) -> SelectedTransferTask:
    return SelectedTransferTask(
        key=key,
        cell_mass_g_cm2=dynamic["cell_mass_g_cm2"],
        density_g_cm3=dynamic["density_g_cm3"][index],
        temperature_k=dynamic["temperature_k"][index],
        hydrogen_fraction=dynamic["hydrogen_fraction"][index],
        helium_fraction=dynamic["helium_fraction"][index],
        panels_per_transformed_decade=panels,
        angular_order=angle,
    )


def run_selected_convergence(
    output_dir: Path,
    *,
    workers: int,
    force: bool,
) -> None:
    csv_path = output_dir / "phase7b4q_selected_convergence.csv"
    report_path = output_dir / "phase7b4q_selected_convergence.json"
    if not force and csv_path.exists() and report_path.exists():
        print(f"reusing {report_path.name}", flush=True)
        return
    dynamic2048 = _load_npz_arrays(
        output_dir / "phase7b4o_depth64_phase2048.npz"
    )
    dynamic62 = _load_npz_arrays(output_dir / "phase7b4n_depth62_phase1024.npz")
    dynamic64 = _load_npz_arrays(output_dir / "phase7b4n_depth64_phase1024.npz")
    tasks: list[SelectedTransferTask] = []
    metadata: list[tuple[float, int, int, int]] = []
    for phase_number, target in enumerate(REPRESENTATIVE_PHASES):
        index2048 = _nearest_phase_index(
            dynamic2048["orbital_phase"], float(target)
        )
        index62 = _nearest_phase_index(dynamic62["orbital_phase"], float(target))
        index64 = _nearest_phase_index(dynamic64["orbital_phase"], float(target))
        metadata.append((float(target), index2048, index62, index64))
        configurations = {
            *(
                ("N64-2048", index2048, panels, PRODUCTION_ANGULAR_ORDER)
                for panels in PANELS_PER_TRANSFORMED_DECADE
            ),
            *(
                (
                    "N64-2048",
                    index2048,
                    PRODUCTION_PANELS_PER_TRANSFORMED_DECADE,
                    angle,
                )
                for angle in ANGULAR_ORDERS
            ),
        }
        for label, index, panels, angle in sorted(configurations):
            key = f"p{phase_number}:{label}:i{index}:q{panels}:a{angle}"
            tasks.append(
                _task(key, dynamic2048, index, panels, angle)
            )
        for label, dynamic, index in (
            ("N62-1024", dynamic62, index62),
            ("N64-1024", dynamic64, index64),
        ):
            key = (
                f"p{phase_number}:{label}:i{index}:"
                f"q{PRODUCTION_PANELS_PER_TRANSFORMED_DECADE}:"
                f"a{PRODUCTION_ANGULAR_ORDER}"
            )
            tasks.append(
                _task(
                    key,
                    dynamic,
                    index,
                    PRODUCTION_PANELS_PER_TRANSFORMED_DECADE,
                    PRODUCTION_ANGULAR_ORDER,
                )
            )
    context = multiprocessing.get_context("spawn")
    solved: dict[str, dict[str, np.ndarray]] = {}
    energy_residuals: dict[str, float] = {}
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as executor:
        for completed, (key, fields, energy_residual) in enumerate(
            executor.map(_solve_task, tasks, chunksize=1), start=1
        ):
            solved[key] = fields
            energy_residuals[key] = energy_residual
            if completed % 8 == 0 or completed == len(tasks):
                print(
                    json.dumps(
                        {
                            "completed_selected_transfer_tasks": completed,
                            "total_selected_transfer_tasks": len(tasks),
                        }
                    ),
                    flush=True,
                )

    rows: list[dict[str, object]] = []
    for phase_number, (target, index2048, index62, index64) in enumerate(metadata):
        actual = float(dynamic2048["orbital_phase"][index2048])

        def key2048(panels: int, angle: int) -> str:
            return f"p{phase_number}:N64-2048:i{index2048}:q{panels}:a{angle}"

        frequency_reference = solved[
            key2048(4, PRODUCTION_ANGULAR_ORDER)
        ]
        for panels in (1, 2):
            rows.extend(
                _comparison_metric_rows(
                    "frequency",
                    f"excess panels/decade {panels} ({_quadrature(panels).frequency_hz.size} nodes)",
                    f"excess panels/decade 4 ({_quadrature(4).frequency_hz.size} nodes)",
                    actual,
                    solved[key2048(panels, PRODUCTION_ANGULAR_ORDER)],
                    frequency_reference,
                )
            )
        angular_reference = solved[
            key2048(PRODUCTION_PANELS_PER_TRANSFORMED_DECADE, 24)
        ]
        for angle in (8, 12, 16):
            rows.extend(
                _comparison_metric_rows(
                    "angle",
                    f"order {angle}",
                    "order 24",
                    actual,
                    solved[
                        key2048(
                            PRODUCTION_PANELS_PER_TRANSFORMED_DECADE, angle
                        )
                    ],
                    angular_reference,
                )
            )
        key62 = (
            f"p{phase_number}:N62-1024:i{index62}:"
            f"q{PRODUCTION_PANELS_PER_TRANSFORMED_DECADE}:"
            f"a{PRODUCTION_ANGULAR_ORDER}"
        )
        key64 = (
            f"p{phase_number}:N64-1024:i{index64}:"
            f"q{PRODUCTION_PANELS_PER_TRANSFORMED_DECADE}:"
            f"a{PRODUCTION_ANGULAR_ORDER}"
        )
        depth62 = _mass_reduce_fields(
            solved[key62], dynamic62["cell_mass_g_cm2"]
        )
        depth64 = _mass_reduce_fields(
            solved[key64], dynamic64["cell_mass_g_cm2"]
        )
        rows.extend(
            _comparison_metric_rows(
                "depth",
                "62 cells",
                "64 cells",
                float(dynamic64["orbital_phase"][index64]),
                depth62,
                depth64,
            )
        )
    _write_csv(csv_path, rows)

    summaries: list[dict[str, object]] = []
    comparisons = sorted(
        {
            (str(row["axis"]), str(row["candidate"]), str(row["reference"]))
            for row in rows
        }
    )
    for axis, candidate, reference_label in comparisons:
        selected = [
            row
            for row in rows
            if row["axis"] == axis
            and row["candidate"] == candidate
            and row["reference"] == reference_label
        ]
        worst = max(selected, key=lambda row: float(row["error"]))
        summaries.append(
            {
                "axis": axis,
                "candidate": candidate,
                "reference": reference_label,
                "maximum_error": float(worst["error"]),
                "worst_metric": worst["metric"],
                "worst_orbital_phase": float(worst["orbital_phase"]),
                "target": PRODUCTION_TOLERANCE,
                "passed": bool(worst["passed"]),
            }
        )
    frequency_production = next(
        row
        for row in summaries
        if row["axis"] == "frequency"
        and row["candidate"].startswith("excess panels/decade 2")
    )
    angle_production = next(
        row
        for row in summaries
        if row["axis"] == "angle" and row["candidate"] == "order 16"
    )
    depth = next(row for row in summaries if row["axis"] == "depth")
    maximum_energy = max(energy_residuals.values())
    report = {
        "phase": "7B4q-selected-convergence",
        "classification": "[V/O] threshold quadrature and selected-phase convergence",
        "configuration": {
            "representative_orbital_phases": REPRESENTATIVE_PHASES.tolist(),
            "panels_per_transformed_decade": list(
                PANELS_PER_TRANSFORMED_DECADE
            ),
            "actual_frequency_points": [
                int(_quadrature(value).frequency_hz.size)
                for value in PANELS_PER_TRANSFORMED_DECADE
            ],
            "angular_orders": list(ANGULAR_ORDERS),
            "production_panels_per_transformed_decade": (
                PRODUCTION_PANELS_PER_TRANSFORMED_DECADE
            ),
            "production_angular_order": PRODUCTION_ANGULAR_ORDER,
            "production_tolerance": PRODUCTION_TOLERANCE,
            "worker_processes": workers,
        },
        "summary": summaries,
        "maximum_formal_energy_residual": maximum_energy,
        "decision": {
            "frequency_160_vs_304_selected_phase_gate_passed": bool(
                frequency_production["passed"]
            ),
            "angle16_vs_angle24_selected_phase_gate_passed": bool(
                angle_production["passed"]
            ),
            "depth62_vs_depth64_selected_phase_gate_passed": bool(
                depth["passed"]
            ),
            "all_formal_energy_ledgers_passed": maximum_energy
            < CONTROL_TOLERANCE,
            "higher_than_64_independent_depth_reference_required": not bool(
                depth["passed"]
            ),
        },
    }
    _write_json_atomic(report_path, report)
    print(json.dumps(report["decision"], indent=2), flush=True)


def _depth128_grid_and_initial(
    master_edges_path: Path,
    *,
    phase_points: int = PRODUCTION_PHASE_POINTS,
):
    """由同一 N16 父初态直接构造严格嵌套的 N128 独立算例。"""
    saved_edges = _saved_master_edges(master_edges_path)
    frequency = _legacy_dynamic_frequency()
    background = _background(phase_points)
    parent = build_periodic_dynamic_half_column(
        background,
        PARENT_DEPTH_POINTS,
        "uniform_specific",
        mass_fraction_edges=saved_edges[PARENT_DEPTH_POINTS],
    )
    refined_edges = uniform_mass_subcell_edges(saved_edges[64], 2)
    if (
        refined_edges.size != DEPTH_REFERENCE_POINTS + 1
        or not np.array_equal(refined_edges[::2], saved_edges[64])
        or not np.array_equal(refined_edges[::8], saved_edges[PARENT_DEPTH_POINTS])
    ):
        raise ArithmeticError("N128 refinement no longer preserves N64 and N16 edges")
    grid = build_periodic_dynamic_half_column(
        background,
        DEPTH_REFERENCE_POINTS,
        "uniform_specific",
        mass_fraction_edges=refined_edges,
    )
    parent_initial = _legacy_initial_state(background, parent, frequency)
    # 中文：从 N16 父态一次守恒延拓到 N128，避免使用 N64 成品热启动。
    initial = conservative_ground_state_subcells(
        parent, grid, *parent_initial, 8
    )
    return frequency, background, parent, grid, initial


def _uniform_restriction_residuals(parent, solution) -> dict[str, float]:
    restricted = restrict_periodic_dynamic_subcells(parent, solution, 8)
    return {
        "restricted_mass_residual": restricted.maximum_parent_mass_residual,
        "restricted_hydrogen_particle_residual": (
            restricted.maximum_hydrogen_particle_residual
        ),
        "restricted_helium_particle_residual": (
            restricted.maximum_helium_particle_residual
        ),
        "restricted_hydrogen_stage_absolute_residual": (
            restricted.maximum_hydrogen_stage_absolute_residual
        ),
        "restricted_helium_stage_absolute_residual": (
            restricted.maximum_helium_stage_absolute_residual
        ),
        "restricted_charge_residual": restricted.maximum_charge_residual,
        "restricted_energy_residual": (
            restricted.maximum_specific_energy_residual
        ),
        "restricted_optical_depth_residual": (
            restricted.maximum_optical_depth_residual
        ),
        "restricted_flux_divergence_residual": (
            restricted.maximum_face_flux_divergence_residual
        ),
    }


def run_depth_reference(
    output_dir: Path,
    master_edges_path: Path,
    *,
    force: bool,
) -> None:
    spec = DEPTH_REFERENCE_CASE
    npz_path, report_path, checkpoint_path = case_paths(output_dir, spec)
    if force:
        for path in (npz_path, report_path, checkpoint_path):
            path.unlink(missing_ok=True)
    if npz_path.exists() or report_path.exists():
        if not npz_path.exists() or not report_path.exists():
            raise FileExistsError("a partial completed Phase 7B4q N128 case exists")
        arrays = _load_npz_arrays(npz_path)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (
            arrays["temperature_k"].shape
            != (PRODUCTION_PHASE_POINTS, DEPTH_REFERENCE_POINTS)
            or report["configuration"]["case"] != spec.name
        ):
            raise ValueError("saved Phase 7B4q N128 case metadata is inconsistent")
        print(f"reusing {report_path.name}", flush=True)
        return

    frequency, _, parent, grid, initial = _depth128_grid_and_initial(
        master_edges_path
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
            checkpoint_path, spec, frequency, grid.mass_fraction_edges
        )
        print(
            f"resuming {spec.name} after {completed_offset} complete cycles",
            flush=True,
        )
    remaining_cycles = MAXIMUM_TOTAL_CYCLES - completed_offset
    started = time.perf_counter()

    def save_cycle(checkpoint) -> None:
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
        minimum_temperature_k=DYNAMIC_MINIMUM_TEMPERATURE_K,
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
        "phase": "7B4q-depth-reference",
        "classification": "[A/V] independent N128 periodic dynamic depth reference",
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
            "parent_depth_points": PARENT_DEPTH_POINTS,
            "subcells_per_parent": 8,
            "n64_edges_preserved_exactly": bool(
                np.array_equal(grid.mass_fraction_edges[::2], _saved_master_edges(master_edges_path)[64])
            ),
            "independent_from_completed_n64_solution": True,
            "legacy_local_dynamic_frequency_closure_retained_for_depth_isolation": True,
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
            "relative_cycle_energy_ledger_residual": (
                solution.relative_cycle_energy_ledger_residual
            ),
        },
        "decision": {
            "cycle_converged": bool(solution.cycle_residual <= CYCLE_TOLERANCE),
            "initial_and_restriction_conservation_passed": conservation_passed,
            "case_is_an_independent_depth_reference": True,
            "case_is_not_a_full_nonlocal_dynamic_solution": True,
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


def _dynamic_fields(arrays: dict[str, np.ndarray]):
    return dynamic_reference_fields(
        arrays["orbital_phase"],
        arrays["mass_fraction_edges"],
        arrays["cell_mass_g_cm2"],
        arrays["temperature_k"],
        arrays["rosseland_opacity_cm2_g"],
        arrays["hydrogen_fraction"][:, :, 1],
        arrays["helium_fraction"][:, :, 2],
        arrays["outward_flux_edges_erg_s_cm2"][:, 0],
    )


def run_depth_comparison(
    output_dir: Path,
    *,
    workers: int,
    force: bool,
) -> None:
    dynamic_csv = output_dir / "phase7b4q_depth64_vs128_dynamic.csv"
    transfer_csv = output_dir / "phase7b4q_depth64_vs128_nonlocal.csv"
    report_path = output_dir / "phase7b4q_depth64_vs128.json"
    if not force and all(
        path.exists() for path in (dynamic_csv, transfer_csv, report_path)
    ):
        print(f"reusing {report_path.name}", flush=True)
        return
    n64 = _load_npz_arrays(output_dir / "phase7b4n_depth64_phase1024.npz")
    n128_path, n128_report_path, _ = case_paths(
        output_dir, DEPTH_REFERENCE_CASE
    )
    n128 = _load_npz_arrays(n128_path)
    n128_report = json.loads(n128_report_path.read_text(encoding="utf-8"))
    dynamic_error = compare_nested_depth_resolution(
        _dynamic_fields(n64), _dynamic_fields(n128)
    )
    dynamic_rows = [
        {
            "metric": name,
            "error": float(value),
            "target": PRODUCTION_TOLERANCE,
            "passed": float(value) < PRODUCTION_TOLERANCE,
        }
        for name, value in (
            ("surface_flux_relative", dynamic_error.surface_flux_relative_error),
            (
                "maximum_pointwise_temperature_or_opacity_relative",
                dynamic_error.maximum_pointwise_temperature_or_opacity_relative_error,
            ),
            (
                "maximum_pointwise_population_absolute",
                dynamic_error.maximum_pointwise_population_absolute_error,
            ),
            (
                "maximum_column_mean_temperature_or_opacity_relative",
                dynamic_error.maximum_column_mean_temperature_or_opacity_relative_error,
            ),
            (
                "maximum_column_mean_population_absolute",
                dynamic_error.maximum_column_mean_population_absolute_error,
            ),
        )
    ]
    if dynamic_error.maximum_he_iii_half_front_mass_fraction_error is not None:
        front_error = dynamic_error.maximum_he_iii_half_front_mass_fraction_error
        dynamic_rows.append(
            {
                "metric": "maximum_he_iii_half_front_mass_fraction",
                "error": float(front_error),
                "target": PRODUCTION_TOLERANCE,
                "passed": float(front_error) < PRODUCTION_TOLERANCE,
            }
        )
    _write_csv(dynamic_csv, dynamic_rows)

    tasks: list[SelectedTransferTask] = []
    metadata: list[tuple[float, int, int]] = []
    for phase_number, target in enumerate(REPRESENTATIVE_PHASES):
        index64 = _nearest_phase_index(n64["orbital_phase"], float(target))
        index128 = _nearest_phase_index(n128["orbital_phase"], float(target))
        metadata.append((float(target), index64, index128))
        for label, dynamic, index in (
            ("N64", n64, index64),
            ("N128", n128, index128),
        ):
            tasks.append(
                _task(
                    f"p{phase_number}:{label}:i{index}",
                    dynamic,
                    index,
                    PRODUCTION_PANELS_PER_TRANSFORMED_DECADE,
                    PRODUCTION_ANGULAR_ORDER,
                )
            )
    context = multiprocessing.get_context("spawn")
    solved: dict[str, dict[str, np.ndarray]] = {}
    energy_residuals: dict[str, float] = {}
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as executor:
        for completed, (key, fields, energy_residual) in enumerate(
            executor.map(_solve_task, tasks, chunksize=1), start=1
        ):
            solved[key] = fields
            energy_residuals[key] = energy_residual
            if completed % 4 == 0 or completed == len(tasks):
                print(
                    json.dumps(
                        {
                            "completed_depth_transfer_tasks": completed,
                            "total_depth_transfer_tasks": len(tasks),
                        }
                    ),
                    flush=True,
                )
    transfer_rows: list[dict[str, object]] = []
    for phase_number, (_, index64, index128) in enumerate(metadata):
        reduced64 = _mass_reduce_fields(
            solved[f"p{phase_number}:N64:i{index64}"], n64["cell_mass_g_cm2"]
        )
        reduced128 = _mass_reduce_fields(
            solved[f"p{phase_number}:N128:i{index128}"],
            n128["cell_mass_g_cm2"],
        )
        transfer_rows.extend(
            _comparison_metric_rows(
                "depth",
                "64 cells",
                "128 cells",
                float(n128["orbital_phase"][index128]),
                reduced64,
                reduced128,
            )
        )
    _write_csv(transfer_csv, transfer_rows)
    worst_transfer = max(transfer_rows, key=lambda row: float(row["error"]))
    maximum_energy_residual = max(energy_residuals.values())
    dynamic_gate = bool(
        joint_dynamic_error_meets_target(dynamic_error, PRODUCTION_TOLERANCE)
        and dynamic_error.front_status_mismatch_phase_count == 0
    )
    transfer_gate = bool(float(worst_transfer["error"]) < PRODUCTION_TOLERANCE)
    report = {
        "phase": "7B4q-depth64-vs-depth128",
        "classification": "[V/O] independent dynamic and weighted nonlocal depth convergence",
        "configuration": {
            "candidate_depth_points": 64,
            "reference_depth_points": 128,
            "phase_points": PRODUCTION_PHASE_POINTS,
            "representative_orbital_phases": REPRESENTATIVE_PHASES.tolist(),
            "formal_frequency_points": int(
                _quadrature(PRODUCTION_PANELS_PER_TRANSFORMED_DECADE).frequency_hz.size
            ),
            "formal_angular_order": PRODUCTION_ANGULAR_ORDER,
            "production_tolerance": PRODUCTION_TOLERANCE,
            "worker_processes": workers,
        },
        "dynamic_error": asdict(dynamic_error),
        "worst_weighted_nonlocal_error": {
            "error": float(worst_transfer["error"]),
            "metric": worst_transfer["metric"],
            "orbital_phase": float(worst_transfer["orbital_phase"]),
        },
        "maximum_formal_energy_residual": maximum_energy_residual,
        "n128_reference_decision": n128_report["decision"],
        "decision": {
            "dynamic_depth64_vs128_gate_passed": dynamic_gate,
            "weighted_nonlocal_depth64_vs128_gate_passed": transfer_gate,
            "all_formal_energy_ledgers_passed": maximum_energy_residual
            < CONTROL_TOLERANCE,
            "depth64_is_accepted": dynamic_gate and transfer_gate,
        },
    }
    _write_json_atomic(report_path, report)
    print(json.dumps(report["decision"], indent=2), flush=True)


def run_transfer_subgrid_convergence(
    output_dir: Path,
    *,
    workers: int,
    force: bool,
) -> None:
    csv_path = output_dir / "phase7b4q_transfer_subgrid_convergence.csv"
    report_path = output_dir / "phase7b4q_transfer_subgrid_convergence.json"
    if not force and csv_path.exists() and report_path.exists():
        print(f"reusing {report_path.name}", flush=True)
        return
    n128_path, _, _ = case_paths(output_dir, DEPTH_REFERENCE_CASE)
    dynamic = _load_npz_arrays(n128_path)
    subcell_factors = (8, 16, 32)
    tasks: list[SelectedTransferTask] = []
    metadata: list[tuple[int, float, int]] = []
    for phase_number, target in enumerate(REPRESENTATIVE_PHASES):
        index = _nearest_phase_index(dynamic["orbital_phase"], float(target))
        metadata.append((phase_number, float(target), index))
        for factor in subcell_factors:
            tasks.append(
                SelectedTransferTask(
                    key=f"p{phase_number}:i{index}:s{factor}",
                    cell_mass_g_cm2=dynamic["cell_mass_g_cm2"],
                    density_g_cm3=dynamic["density_g_cm3"][index],
                    temperature_k=dynamic["temperature_k"][index],
                    hydrogen_fraction=dynamic["hydrogen_fraction"][index],
                    helium_fraction=dynamic["helium_fraction"][index],
                    panels_per_transformed_decade=(
                        PRODUCTION_PANELS_PER_TRANSFORMED_DECADE
                    ),
                    angular_order=PRODUCTION_ANGULAR_ORDER,
                    transfer_subcells_per_material_cell=factor,
                    scattering_linear_solver="sparse_interface",
                )
            )
    # N128x32 的稀疏形式解内存高于旧 dense-Lambda 代表相位任务。
    actual_workers = min(workers, 4)
    context = multiprocessing.get_context("spawn")
    solved: dict[str, dict[str, np.ndarray]] = {}
    energy_residuals: dict[str, float] = {}
    with ProcessPoolExecutor(
        max_workers=actual_workers, mp_context=context
    ) as executor:
        for completed, (key, fields, energy_residual) in enumerate(
            executor.map(_solve_task, tasks, chunksize=1), start=1
        ):
            solved[key] = fields
            energy_residuals[key] = energy_residual
            if completed % 4 == 0 or completed == len(tasks):
                print(
                    json.dumps(
                        {
                            "completed_transfer_subgrid_tasks": completed,
                            "total_transfer_subgrid_tasks": len(tasks),
                        }
                    ),
                    flush=True,
                )
    rows: list[dict[str, object]] = []
    for phase_number, _, index in metadata:
        reference = _mass_reduce_fields(
            solved[f"p{phase_number}:i{index}:s32"],
            dynamic["cell_mass_g_cm2"],
        )
        for factor in (8, 16):
            candidate = _mass_reduce_fields(
                solved[f"p{phase_number}:i{index}:s{factor}"],
                dynamic["cell_mass_g_cm2"],
            )
            rows.extend(
                _comparison_metric_rows(
                    "transfer_subgrid",
                    f"{factor} subcells per material cell",
                    "32 subcells per material cell",
                    float(dynamic["orbital_phase"][index]),
                    candidate,
                    reference,
                )
            )
    _write_csv(csv_path, rows)
    summaries = []
    for factor in (8, 16):
        label = f"{factor} subcells per material cell"
        selected = [row for row in rows if row["candidate"] == label]
        worst = max(selected, key=lambda row: float(row["error"]))
        summaries.append(
            {
                "candidate": label,
                "reference": "32 subcells per material cell",
                "maximum_error": float(worst["error"]),
                "worst_metric": worst["metric"],
                "worst_orbital_phase": float(worst["orbital_phase"]),
                "target": PRODUCTION_TOLERANCE,
                "passed": bool(worst["passed"]),
            }
        )
    factor16 = next(
        item for item in summaries if item["candidate"].startswith("16 ")
    )
    maximum_energy_residual = max(energy_residuals.values())
    report = {
        "phase": "7B4q-transfer-subgrid-convergence",
        "classification": "[V/O] scattering transfer depth-subgrid convergence",
        "configuration": {
            "material_depth_points": DEPTH_REFERENCE_POINTS,
            "transfer_subcells_per_material_cell": list(subcell_factors),
            "effective_transfer_half_depth_points": [
                DEPTH_REFERENCE_POINTS * factor for factor in subcell_factors
            ],
            "representative_orbital_phases": REPRESENTATIVE_PHASES.tolist(),
            "frequency_points": int(
                _quadrature(PRODUCTION_PANELS_PER_TRANSFORMED_DECADE).frequency_hz.size
            ),
            "angular_order": PRODUCTION_ANGULAR_ORDER,
            "scattering_linear_solver": "sparse_interface",
            "production_tolerance": PRODUCTION_TOLERANCE,
            "worker_processes": actual_workers,
        },
        "summary": summaries,
        "maximum_formal_energy_residual": maximum_energy_residual,
        "decision": {
            "subgrid16_vs_subgrid32_selected_phase_gate_passed": bool(
                factor16["passed"]
            ),
            "all_formal_energy_ledgers_passed": maximum_energy_residual
            < CONTROL_TOLERANCE,
            "material_and_transfer_depth_grids_are_separated": True,
        },
    }
    _write_json_atomic(report_path, report)
    print(json.dumps(report["decision"], indent=2), flush=True)


def run_production_frequency_angle_convergence(
    output_dir: Path,
    *,
    workers: int,
    force: bool,
) -> None:
    csv_path = output_dir / "phase7b4q_production_frequency_angle.csv"
    report_path = output_dir / "phase7b4q_production_frequency_angle.json"
    if not force and csv_path.exists() and report_path.exists():
        print(f"reusing {report_path.name}", flush=True)
        return
    n128_path, _, _ = case_paths(output_dir, DEPTH_REFERENCE_CASE)
    dynamic = _load_npz_arrays(n128_path)
    tasks: list[SelectedTransferTask] = []
    metadata: list[tuple[int, int]] = []
    for phase_number, target in enumerate(REPRESENTATIVE_PHASES):
        index = _nearest_phase_index(dynamic["orbital_phase"], float(target))
        metadata.append((phase_number, index))
        configurations = {
            *((panels, PRODUCTION_ANGULAR_ORDER) for panels in (1, 2, 4)),
            *((PRODUCTION_PANELS_PER_TRANSFORMED_DECADE, angle) for angle in (12, 16, 24)),
        }
        for panels, angle in sorted(configurations):
            tasks.append(
                SelectedTransferTask(
                    key=f"p{phase_number}:i{index}:q{panels}:a{angle}",
                    cell_mass_g_cm2=dynamic["cell_mass_g_cm2"],
                    density_g_cm3=dynamic["density_g_cm3"][index],
                    temperature_k=dynamic["temperature_k"][index],
                    hydrogen_fraction=dynamic["hydrogen_fraction"][index],
                    helium_fraction=dynamic["helium_fraction"][index],
                    panels_per_transformed_decade=panels,
                    angular_order=angle,
                    transfer_subcells_per_material_cell=16,
                    scattering_linear_solver="sparse_interface",
                )
            )
    actual_workers = min(workers, 4)
    context = multiprocessing.get_context("spawn")
    solved: dict[str, dict[str, np.ndarray]] = {}
    energy_residuals: dict[str, float] = {}
    with ProcessPoolExecutor(
        max_workers=actual_workers, mp_context=context
    ) as executor:
        for completed, (key, fields, energy_residual) in enumerate(
            executor.map(_solve_task, tasks, chunksize=1), start=1
        ):
            solved[key] = fields
            energy_residuals[key] = energy_residual
            if completed % 4 == 0 or completed == len(tasks):
                print(
                    json.dumps(
                        {
                            "completed_production_convergence_tasks": completed,
                            "total_production_convergence_tasks": len(tasks),
                        }
                    ),
                    flush=True,
                )
    rows: list[dict[str, object]] = []
    for phase_number, index in metadata:
        def reduced(panels: int, angle: int) -> dict[str, np.ndarray]:
            return _mass_reduce_fields(
                solved[f"p{phase_number}:i{index}:q{panels}:a{angle}"],
                dynamic["cell_mass_g_cm2"],
            )

        frequency_reference = reduced(4, PRODUCTION_ANGULAR_ORDER)
        for panels in (1, 2):
            rows.extend(
                _comparison_metric_rows(
                    "frequency_refined_transfer",
                    f"excess panels/decade {panels} ({_quadrature(panels).frequency_hz.size} nodes)",
                    f"excess panels/decade 4 ({_quadrature(4).frequency_hz.size} nodes)",
                    float(dynamic["orbital_phase"][index]),
                    reduced(panels, PRODUCTION_ANGULAR_ORDER),
                    frequency_reference,
                )
            )
        angular_reference = reduced(
            PRODUCTION_PANELS_PER_TRANSFORMED_DECADE, 24
        )
        for angle in (12, 16):
            rows.extend(
                _comparison_metric_rows(
                    "angle_refined_transfer",
                    f"order {angle}",
                    "order 24",
                    float(dynamic["orbital_phase"][index]),
                    reduced(PRODUCTION_PANELS_PER_TRANSFORMED_DECADE, angle),
                    angular_reference,
                )
            )
    _write_csv(csv_path, rows)
    summaries: list[dict[str, object]] = []
    comparisons = sorted(
        {
            (str(row["axis"]), str(row["candidate"]), str(row["reference"]))
            for row in rows
        }
    )
    for axis, candidate, reference_label in comparisons:
        selected = [
            row
            for row in rows
            if row["axis"] == axis
            and row["candidate"] == candidate
            and row["reference"] == reference_label
        ]
        worst = max(selected, key=lambda row: float(row["error"]))
        summaries.append(
            {
                "axis": axis,
                "candidate": candidate,
                "reference": reference_label,
                "maximum_error": float(worst["error"]),
                "worst_metric": worst["metric"],
                "worst_orbital_phase": float(worst["orbital_phase"]),
                "target": PRODUCTION_TOLERANCE,
                "passed": bool(worst["passed"]),
            }
        )
    frequency_production = next(
        item
        for item in summaries
        if item["axis"] == "frequency_refined_transfer"
        and item["candidate"].startswith("excess panels/decade 2")
    )
    angle_production = next(
        item
        for item in summaries
        if item["axis"] == "angle_refined_transfer"
        and item["candidate"] == "order 16"
    )
    maximum_energy_residual = max(energy_residuals.values())
    report = {
        "phase": "7B4q-production-frequency-angle",
        "classification": "[V/O] refined-transfer production convergence",
        "configuration": {
            "material_depth_points": DEPTH_REFERENCE_POINTS,
            "transfer_subcells_per_material_cell": 16,
            "effective_transfer_half_depth_points": 2048,
            "panels_per_transformed_decade": [1, 2, 4],
            "actual_frequency_points": [
                int(_quadrature(value).frequency_hz.size) for value in (1, 2, 4)
            ],
            "angular_orders": [12, 16, 24],
            "scattering_linear_solver": "sparse_interface",
            "representative_orbital_phases": REPRESENTATIVE_PHASES.tolist(),
            "production_tolerance": PRODUCTION_TOLERANCE,
            "worker_processes": actual_workers,
        },
        "summary": summaries,
        "maximum_formal_energy_residual": maximum_energy_residual,
        "decision": {
            "frequency160_vs304_refined_transfer_gate_passed": bool(
                frequency_production["passed"]
            ),
            "angle16_vs_angle24_refined_transfer_gate_passed": bool(
                angle_production["passed"]
            ),
            "all_formal_energy_ledgers_passed": maximum_energy_residual
            < CONTROL_TOLERANCE,
        },
    }
    _write_json_atomic(report_path, report)
    print(json.dumps(report["decision"], indent=2), flush=True)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def run_plots_and_summary(output_dir: Path, *, force: bool) -> None:
    threshold_plot = output_dir / "phase7b4q_threshold_quadrature.png"
    depth_plot = output_dir / "phase7b4q_depth_and_transfer_convergence.png"
    gate_plot = output_dir / "phase7b4q_production_gates.png"
    summary_path = output_dir / "phase7b4q_summary.json"
    required = (threshold_plot, depth_plot, gate_plot, summary_path)
    if not force and all(path.exists() for path in required):
        print(f"reusing {summary_path.name}", flush=True)
        return

    controls = json.loads(
        (output_dir / "phase7b4q_controls.json").read_text(encoding="utf-8")
    )
    depth_reference = json.loads(
        (output_dir / "phase7b4q_depth128_phase1024.json").read_text(
            encoding="utf-8"
        )
    )
    depth_comparison = json.loads(
        (output_dir / "phase7b4q_depth64_vs128.json").read_text(
            encoding="utf-8"
        )
    )
    transfer_subgrid = json.loads(
        (output_dir / "phase7b4q_transfer_subgrid_convergence.json").read_text(
            encoding="utf-8"
        )
    )
    production = json.loads(
        (output_dir / "phase7b4q_production_frequency_angle.json").read_text(
            encoding="utf-8"
        )
    )

    figure, axes = plt.subplots(1, 2, figsize=(12.4, 4.8), constrained_layout=True)
    for panels, color in zip((1, 2, 4), ("C0", "C1", "C2"), strict=True):
        quadrature = _quadrature(panels)
        axes[0].scatter(
            quadrature.photon_energy_ev,
            quadrature.energy_weight_ev,
            s=8,
            alpha=0.7,
            color=color,
            label=f"{quadrature.photon_energy_ev.size} nodes",
        )
    for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS:
        axes[0].axvline(
            fit.threshold_energy_ev, color="black", linestyle=":", linewidth=0.8
        )
    axes[0].set(
        xscale="log",
        yscale="log",
        xlabel="Photon energy (eV)",
        ylabel="Positive energy weight (eV)",
        title="(a) Threshold-excess quadrature",
    )
    axes[0].legend(fontsize=8)
    control_rows = controls["controls"]
    axes[1].barh(
        np.arange(len(control_rows)),
        [float(row["error"]) for row in control_rows],
        color="C0",
    )
    axes[1].axvline(CONTROL_TOLERANCE, color="black", linestyle="--")
    axes[1].set(
        xscale="log",
        xlabel="Relative error",
        yticks=np.arange(len(control_rows)),
        yticklabels=[str(row["control"]) for row in control_rows],
        title="(b) Analytic and LTE controls",
    )
    axes[1].tick_params(axis="y", labelsize=8)
    figure.suptitle("Phase 7B4q: threshold-explicit frequency integration")
    figure.savefig(threshold_plot, dpi=180)
    plt.close(figure)

    n64 = _load_npz_arrays(output_dir / "phase7b4n_depth64_phase1024.npz")
    n128_path, _, _ = case_paths(output_dir, DEPTH_REFERENCE_CASE)
    n128 = _load_npz_arrays(n128_path)
    phase = n128["orbital_phase"]
    dynamic_surface_error = np.abs(
        n64["outward_flux_edges_erg_s_cm2"][:, 0]
        - n128["outward_flux_edges_erg_s_cm2"][:, 0]
    ) / np.abs(n128["outward_flux_edges_erg_s_cm2"][:, 0])
    centres64 = 0.5 * (
        n64["mass_fraction_edges"][:-1] + n64["mass_fraction_edges"][1:]
    )
    centres128 = 0.5 * (
        n128["mass_fraction_edges"][:-1] + n128["mass_fraction_edges"][1:]
    )
    he_difference = np.empty((phase.size, centres64.size), dtype=np.float64)
    for index in range(phase.size):
        he_difference[index] = np.abs(
            n64["helium_fraction"][index, :, 2]
            - np.interp(
                centres64,
                centres128,
                n128["helium_fraction"][index, :, 2],
            )
        )
    old_transfer_rows = [
        row
        for row in _read_csv(
            output_dir / "phase7b4q_depth64_vs128_nonlocal.csv"
        )
        if row["metric"] == "bolometric_flux"
    ]
    subgrid_rows = [
        row
        for row in _read_csv(
            output_dir / "phase7b4q_transfer_subgrid_convergence.csv"
        )
        if row["metric"] == "bolometric_flux"
    ]
    figure, axes = plt.subplots(2, 2, figsize=(12.4, 8.4), constrained_layout=True)
    axes[0, 0].semilogy(phase, dynamic_surface_error)
    axes[0, 0].axhline(PRODUCTION_TOLERANCE, color="black", linestyle="--")
    axes[0, 0].set(
        xlabel="Orbital time phase",
        ylabel="Relative error",
        title="(a) N64 vs N128 dynamic surface flux",
    )
    image = axes[0, 1].pcolormesh(
        phase,
        centres64,
        he_difference.T,
        shading="auto",
    )
    axes[0, 1].set(
        xlabel="Orbital time phase",
        ylabel="Mass fraction from surface",
        title="(b) N64 vs N128 absolute He III difference",
    )
    figure.colorbar(image, ax=axes[0, 1], label="Absolute fraction difference")
    axes[1, 0].semilogy(
        [float(row["orbital_phase"]) for row in old_transfer_rows],
        [float(row["error"]) for row in old_transfer_rows],
        marker="o",
    )
    axes[1, 0].axhline(PRODUCTION_TOLERANCE, color="black", linestyle="--")
    axes[1, 0].set(
        xlabel="Orbital time phase",
        ylabel="Relative flux error",
        title="(c) Coupled material/transfer N64 vs N128",
    )
    for factor, marker in ((8, "s"), (16, "o")):
        selected = [
            row
            for row in subgrid_rows
            if row["candidate"].startswith(f"{factor} ")
        ]
        axes[1, 1].semilogy(
            [float(row["orbital_phase"]) for row in selected],
            [float(row["error"]) for row in selected],
            marker=marker,
            label=f"{factor} vs 32 subcells",
        )
    axes[1, 1].axhline(PRODUCTION_TOLERANCE, color="black", linestyle="--")
    axes[1, 1].set(
        xlabel="Orbital time phase",
        ylabel="Relative flux error",
        title="(d) Independent radiation-subgrid convergence",
    )
    axes[1, 1].legend(fontsize=8)
    figure.suptitle("Phase 7B4q: separating material and radiation depth grids")
    figure.savefig(depth_plot, dpi=180)
    plt.close(figure)

    dynamic_error = depth_comparison["dynamic_error"]
    gate_labels = [
        "Dynamic surface flux",
        "Point T/opacity",
        "Point population",
        "Column T/opacity",
        "Column population",
        "He III front",
        "Old coupled N64/N128",
        "Transfer 8/32",
        "Transfer 16/32",
        "Frequency 160/304",
        "Angle 16/24",
    ]
    gate_values = [
        dynamic_error["surface_flux_relative_error"],
        dynamic_error["maximum_pointwise_temperature_or_opacity_relative_error"],
        dynamic_error["maximum_pointwise_population_absolute_error"],
        dynamic_error["maximum_column_mean_temperature_or_opacity_relative_error"],
        dynamic_error["maximum_column_mean_population_absolute_error"],
        dynamic_error["maximum_he_iii_half_front_mass_fraction_error"],
        depth_comparison["worst_weighted_nonlocal_error"]["error"],
        transfer_subgrid["summary"][0]["maximum_error"],
        transfer_subgrid["summary"][1]["maximum_error"],
        next(
            row["maximum_error"]
            for row in production["summary"]
            if row["axis"] == "frequency_refined_transfer"
            and row["candidate"].startswith("excess panels/decade 2")
        ),
        next(
            row["maximum_error"]
            for row in production["summary"]
            if row["axis"] == "angle_refined_transfer"
            and row["candidate"] == "order 16"
        ),
    ]
    colors = ["C2" if value < PRODUCTION_TOLERANCE else "C3" for value in gate_values]
    figure, axis = plt.subplots(figsize=(12.4, 5.5), constrained_layout=True)
    axis.bar(np.arange(len(gate_labels)), gate_values, color=colors)
    axis.axhline(PRODUCTION_TOLERANCE, color="black", linestyle="--", label="Target")
    axis.set(
        yscale="log",
        ylabel="Maximum error",
        xticks=np.arange(len(gate_labels)),
        xticklabels=gate_labels,
        title="Phase 7B4q: passed and failed convergence gates",
    )
    axis.tick_params(axis="x", rotation=35, labelsize=8)
    axis.legend()
    figure.savefig(gate_plot, dpi=180)
    plt.close(figure)

    summary = {
        "phase": "7B4q-summary",
        "classification": "[V/O] threshold quadrature and separated depth-grid gate",
        "accepted_formal_configuration": {
            "dynamic_material_depth_points": 128,
            "dynamic_phase_points": 1024,
            "transfer_subcells_per_material_cell": 16,
            "effective_transfer_half_depth_points": 2048,
            "frequency_points": 160,
            "angular_order": 16,
            "scattering_linear_solver": "sparse_interface",
        },
        "decision": {
            "analytic_and_lte_controls_passed": controls["decision"]["all_controls_passed"],
            "independent_n128_dynamic_reference_converged": depth_reference["decision"]["cycle_converged"],
            "n64_material_depth_accepted": depth_comparison["decision"]["dynamic_depth64_vs128_gate_passed"],
            "n64_unrefined_transfer_accepted": depth_comparison["decision"]["weighted_nonlocal_depth64_vs128_gate_passed"],
            "transfer_subgrid16_accepted": transfer_subgrid["decision"]["subgrid16_vs_subgrid32_selected_phase_gate_passed"],
            "frequency160_accepted": production["decision"]["frequency160_vs304_refined_transfer_gate_passed"],
            "angular_order16_accepted": production["decision"]["angle16_vs_angle24_refined_transfer_gate_passed"],
            "phase7b4q_selected_formal_configuration_passed": bool(
                controls["decision"]["all_controls_passed"]
                and depth_reference["decision"]["cycle_converged"]
                and transfer_subgrid["decision"]["subgrid16_vs_subgrid32_selected_phase_gate_passed"]
                and production["decision"]["frequency160_vs304_refined_transfer_gate_passed"]
                and production["decision"]["angle16_vs_angle24_refined_transfer_gate_passed"]
            ),
            "n128_phase1024_vs_phase2048_dynamic_time_gate_resolved": False,
            "stationary_radiation_timescale_gate_resolved": False,
        },
        "open_items": [
            "An independent N128 x 2048 periodic material solution has not been run.",
            "The frozen formal solution does not resolve the previously failed radiation diffusion-time gate.",
            "This phase is not a time-dependent nonlocal NLTE atmosphere solution.",
        ],
        "figures": [path.name for path in (threshold_plot, depth_plot, gate_plot)],
    }
    _write_json_atomic(summary_path, summary)
    print(json.dumps(summary["decision"], indent=2), flush=True)


def main() -> None:
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--stage",
        choices=(
            "controls",
            "convergence",
            "depth-reference",
            "depth-comparison",
            "transfer-subgrid",
            "production-convergence",
            "plots",
            "all",
        ),
        default="all",
    )
    parser.add_argument(
        "--master-edges",
        type=Path,
        default=Path("outputs/phase7b4l_subcell_edges.csv"),
    )
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    if arguments.workers < 1:
        parser.error("--workers must be positive")
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if arguments.stage in ("controls", "all"):
        run_controls(arguments.output_dir, force=arguments.force)
    if arguments.stage in ("convergence", "all"):
        run_selected_convergence(
            arguments.output_dir,
            workers=arguments.workers,
            force=arguments.force,
        )
    if arguments.stage in ("depth-reference", "all"):
        run_depth_reference(
            arguments.output_dir,
            arguments.master_edges,
            force=arguments.force,
        )
    if arguments.stage in ("depth-comparison", "all"):
        run_depth_comparison(
            arguments.output_dir,
            workers=arguments.workers,
            force=arguments.force,
        )
    if arguments.stage in ("transfer-subgrid", "all"):
        run_transfer_subgrid_convergence(
            arguments.output_dir,
            workers=arguments.workers,
            force=arguments.force,
        )
    if arguments.stage in ("production-convergence", "all"):
        run_production_frequency_angle_convergence(
            arguments.output_dir,
            workers=arguments.workers,
            force=arguments.force,
        )
    if arguments.stage in ("plots", "all"):
        run_plots_and_summary(arguments.output_dir, force=arguments.force)


if __name__ == "__main__":
    main()
