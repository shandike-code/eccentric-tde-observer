"""生成 Phase 7B4n 联合 64 深度、1024 相位周期动态参考。"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.continuum_emission import (
    edge_resolved_milne_energy_grid_ev,
)
from eccentric_tde_observer.dynamic_column import (
    build_zo_periodic_column_background,
)
from eccentric_tde_observer.hydrostatic_atmosphere import (
    build_zo_constrained_n3_column,
    solve_lte_rosseland_diffusion_column,
    symmetric_dissipation_profile,
)
from eccentric_tde_observer.joint_dynamic_reference import (
    DynamicReferenceFields,
    JointDynamicError,
    compare_nested_depth_resolution,
    compare_periodic_time_resolution,
    dynamic_reference_fields,
    joint_dynamic_error_meets_target,
    resample_periodic_dynamic_fields,
)
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.periodic_dynamic_atmosphere import (
    PeriodicDynamicColumnSolution,
    PeriodicDynamicCycleCheckpoint,
    build_periodic_dynamic_half_column,
    diffusion_outward_flux_edges_erg_s_cm2,
    solve_periodic_dynamic_column,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.reference_case import (
    build_strict_domain_reference_model,
)
from eccentric_tde_observer.subcell_reconstruction import (
    ConservativeCoarsenedGroundState,
    ConservativeGroundStateSubcells,
    coarsen_ground_state_subcells,
    conservative_ground_state_subcells,
    nested_mass_cell_offsets,
    restrict_periodic_dynamic_variable_subcells,
)


RADIAL_POINTS = 65
RADIAL_INDEX = 8
PARENT_DEPTH_POINTS = 16
MASTER_DEPTH_POINTS = 64
SPATIAL_CANDIDATE_DEPTH_POINTS = 62
CONTROL_PHASE_POINTS = 64
TIME_CANDIDATE_PHASE_POINTS = 512
PRODUCTION_PHASE_POINTS = 1024
ENERGY_RANGE_EV = (0.1, 5000.0)
FREQUENCY_BASE_POINTS = 65
MINIMUM_TEMPERATURE_K = 5000.0
MAXIMUM_TEMPERATURE_K = 2.0e6
CYCLE_TOLERANCE = 2.0e-7
PRODUCTION_TOLERANCE = 1.0e-3
COLORED_JACOBIAN_EQUIVALENCE_TOLERANCE = 1.0e-6
CONSERVATION_TOLERANCE = 2.0e-12
MAXIMUM_TOTAL_CYCLES = 16


@dataclass(frozen=True)
class CaseSpec:
    name: str
    phase_points: int
    depth_points: int
    output_phase: str = "phase7b4n"


CONTROL_CASE = CaseSpec("colored_depth64_phase64", CONTROL_PHASE_POINTS, 64)
FORMAL_CASES = (
    CaseSpec("depth64_phase512", TIME_CANDIDATE_PHASE_POINTS, 64),
    CaseSpec("depth62_phase1024", PRODUCTION_PHASE_POINTS, 62),
    CaseSpec("depth64_phase1024", PRODUCTION_PHASE_POINTS, 64),
)
ALL_CASES = {case.name: case for case in (CONTROL_CASE, *FORMAL_CASES)}


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


def _frequency() -> np.ndarray:
    energy = edge_resolved_milne_energy_grid_ev(
        ENERGY_RANGE_EV[0], ENERGY_RANGE_EV[1], FREQUENCY_BASE_POINTS
    )
    return energy * EV_ERG / PLANCK_ERG_S


def _background(phase_points: int):
    model = build_strict_domain_reference_model(RADIAL_POINTS, phase_points)
    return build_zo_periodic_column_background(model, RADIAL_INDEX)


def _phase(background) -> np.ndarray:
    return background.time_since_pericentre_s / background.orbital_period_s


def _saved_master_edges(path: Path) -> dict[int, np.ndarray]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    grouped: dict[int, list[tuple[int, float]]] = {}
    for row in rows:
        count = int(row["effective_depth_points"])
        grouped.setdefault(count, []).append(
            (int(row["edge_index"]), float(row["mass_fraction_edge"]))
        )
    edges = {
        count: np.array([value for _, value in sorted(values)])
        for count, values in grouped.items()
    }
    if set(edges) != {16, 32, 64}:
        raise ValueError("Phase 7B4l edge table must contain 16, 32 and 64 cells")
    if (
        not np.array_equal(edges[64][::2], edges[32])
        or not np.array_equal(edges[64][::4], edges[16])
    ):
        raise ValueError("Phase 7B4l saved grids are no longer strictly nested")
    return edges


def _saved_variable_edges(path: Path, master_edges: np.ndarray) -> np.ndarray:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = [
            row
            for row in csv.DictReader(stream)
            if int(row["effective_depth_points"])
            == SPATIAL_CANDIDATE_DEPTH_POINTS
        ]
    if len(rows) != SPATIAL_CANDIDATE_DEPTH_POINTS + 1:
        raise ValueError("Phase 7B4m variable edge table lacks the N=62 grid")
    rows.sort(key=lambda row: int(row["edge_index"]))
    edges = np.array([float(row["mass_fraction_edge"]) for row in rows])
    nested_mass_cell_offsets(edges, master_edges)
    return edges


def _initial_state(background, grid, frequency: np.ndarray):
    column = build_zo_constrained_n3_column(
        float(background.one_sided_column_mass_g_cm2[0]),
        float(background.scale_height_cm[0]),
        float(background.pressure_gravity_coefficient_s2[0]),
        grid.half_depth_points,
        mass_fraction_edges=grid.mass_fraction_edges,
    )
    dissipation = symmetric_dissipation_profile(
        column,
        float(background.one_face_surface_flux_erg_s_cm2[0]),
        "uniform_specific",
    )
    static = solve_lte_rosseland_diffusion_column(
        column,
        dissipation,
        float(background.effective_temperature_k[0]),
        frequency,
        relative_tolerance=1.0e-6,
    )
    temperature = np.array(
        static.full_temperature_k[: grid.half_depth_points], copy=True
    )
    ionization = lte_hydrogen_helium_ionization(
        grid.density_g_cm3[0], temperature
    )
    hydrogen = np.column_stack(
        (
            ionization.hydrogen_neutral_fraction,
            ionization.hydrogen_ionized_fraction,
        )
    )
    helium = np.column_stack(
        (
            ionization.helium_neutral_fraction,
            ionization.helium_singly_ionized_fraction,
            ionization.helium_doubly_ionized_fraction,
        )
    )
    return temperature, hydrogen, helium


def _case_grid_and_initial(
    spec: CaseSpec,
    frequency: np.ndarray,
    master_edges: dict[int, np.ndarray],
    variable_edges: np.ndarray,
):
    background = _background(spec.phase_points)
    parent = build_periodic_dynamic_half_column(
        background,
        PARENT_DEPTH_POINTS,
        "uniform_specific",
        mass_fraction_edges=master_edges[16],
    )
    master = build_periodic_dynamic_half_column(
        background,
        MASTER_DEPTH_POINTS,
        "uniform_specific",
        mass_fraction_edges=master_edges[64],
    )
    parent_initial = _initial_state(background, parent, frequency)
    master_initial = conservative_ground_state_subcells(
        parent, master, *parent_initial, 4
    )
    if spec.depth_points == MASTER_DEPTH_POINTS:
        return background, parent, master, master_initial
    if spec.depth_points != SPATIAL_CANDIDATE_DEPTH_POINTS:
        raise ValueError("unsupported Phase 7B4n depth count")
    variable = build_periodic_dynamic_half_column(
        background,
        SPATIAL_CANDIDATE_DEPTH_POINTS,
        "uniform_specific",
        mass_fraction_edges=variable_edges,
    )
    initial = coarsen_ground_state_subcells(master, variable, master_initial)
    return background, parent, variable, initial


def _initial_residuals(
    state: ConservativeGroundStateSubcells | ConservativeCoarsenedGroundState,
) -> dict[str, float]:
    if isinstance(state, ConservativeGroundStateSubcells):
        return {
            "initial_mass_residual": state.maximum_parent_mass_residual,
            "initial_hydrogen_particle_residual": (
                state.maximum_hydrogen_particle_residual
            ),
            "initial_helium_particle_residual": (
                state.maximum_helium_particle_residual
            ),
            "initial_hydrogen_stage_absolute_residual": (
                state.maximum_hydrogen_stage_absolute_residual
            ),
            "initial_helium_stage_absolute_residual": (
                state.maximum_helium_stage_absolute_residual
            ),
            "initial_charge_residual": state.maximum_charge_residual,
            "initial_energy_residual": state.maximum_specific_energy_residual,
        }
    return {
        "initial_mass_residual": state.maximum_mass_residual,
        "initial_hydrogen_particle_residual": (
            state.maximum_hydrogen_particle_residual
        ),
        "initial_helium_particle_residual": state.maximum_helium_particle_residual,
        "initial_hydrogen_stage_absolute_residual": (
            state.maximum_hydrogen_stage_absolute_residual
        ),
        "initial_helium_stage_absolute_residual": (
            state.maximum_helium_stage_absolute_residual
        ),
        "initial_charge_residual": state.maximum_charge_residual,
        "initial_energy_residual": state.maximum_specific_energy_residual,
    }


def _restriction_residuals(parent, solution) -> dict[str, float]:
    restricted = restrict_periodic_dynamic_variable_subcells(parent, solution)
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


def case_paths(output_dir: Path, spec: CaseSpec) -> tuple[Path, Path, Path]:
    """返回独立周期算例的结果、报告和整周期检查点路径。"""
    stem = f"{spec.output_phase}_{spec.name}"
    return (
        output_dir / f"{stem}.npz",
        output_dir / f"{stem}.json",
        output_dir / f"{stem}.checkpoint.npz",
    )


def case_phase_label(spec: CaseSpec) -> str:
    """把小写文件前缀映射为文档采用的阶段标签。"""
    label = spec.output_phase.removeprefix("phase").replace("7b", "7B", 1)
    return f"{label}-case"


def _save_checkpoint_atomic(
    path: Path,
    spec: CaseSpec,
    frequency: np.ndarray,
    edges: np.ndarray,
    checkpoint: PeriodicDynamicCycleCheckpoint,
    completed_cycle_offset: int,
    accumulated_runtime_before_s: float,
    current_started: float,
) -> None:
    temporary = path.with_name(f"{path.stem}.tmp.npz")
    np.savez_compressed(
        temporary,
        case_name=np.array(spec.name),
        phase_points=np.array(spec.phase_points),
        depth_points=np.array(spec.depth_points),
        frequency_hz=frequency,
        mass_fraction_edges=edges,
        completed_cycle_count=np.array(
            completed_cycle_offset + checkpoint.cycle_count
        ),
        cycle_residual=np.array(checkpoint.cycle_residual),
        accumulated_runtime_s=np.array(
            accumulated_runtime_before_s + time.perf_counter() - current_started
        ),
        temperature_k=checkpoint.temperature_k,
        hydrogen_fraction=checkpoint.hydrogen_fraction,
        helium_fraction=checkpoint.helium_fraction,
    )
    os.replace(temporary, path)


def _load_checkpoint(
    path: Path,
    spec: CaseSpec,
    frequency: np.ndarray,
    edges: np.ndarray,
) -> tuple[int, float, np.ndarray, np.ndarray, np.ndarray]:
    with np.load(path) as data:
        if str(data["case_name"].item()) != spec.name:
            raise ValueError("checkpoint case name does not match the request")
        if (
            int(data["phase_points"]) != spec.phase_points
            or int(data["depth_points"]) != spec.depth_points
            or not np.array_equal(data["frequency_hz"], frequency)
            or not np.array_equal(data["mass_fraction_edges"], edges)
        ):
            raise ValueError("checkpoint grid or frequency no longer matches")
        completed = int(data["completed_cycle_count"])
        runtime = float(data["accumulated_runtime_s"])
        temperature = np.array(data["temperature_k"], copy=True)
        hydrogen = np.array(data["hydrogen_fraction"], copy=True)
        helium = np.array(data["helium_fraction"], copy=True)
    if completed < 1 or completed >= MAXIMUM_TOTAL_CYCLES:
        raise ValueError("checkpoint has no valid remaining cycle budget")
    if not np.isfinite(runtime) or runtime <= 0.0:
        raise ValueError("checkpoint runtime must be finite and positive")
    return completed, runtime, temperature, hydrogen, helium


def _save_solution_atomic(
    path: Path,
    spec: CaseSpec,
    solution: PeriodicDynamicColumnSolution,
) -> None:
    temporary = path.with_name(f"{path.stem}.tmp.npz")
    background = solution.grid.background
    np.savez_compressed(
        temporary,
        case_name=np.array(spec.name),
        orbital_phase=_phase(background),
        time_since_pericentre_s=background.time_since_pericentre_s,
        step_duration_s=background.step_duration_s,
        mass_fraction_edges=solution.grid.mass_fraction_edges,
        cell_mass_g_cm2=solution.grid.cell_mass_g_cm2,
        density_g_cm3=solution.grid.density_g_cm3,
        target_surface_flux_erg_s_cm2=(
            solution.grid.one_face_target_flux_erg_s_cm2
        ),
        temperature_k=solution.temperature_k,
        hydrogen_fraction=solution.hydrogen_fraction,
        helium_fraction=solution.helium_fraction,
        electron_density_cm3=solution.electron_density_cm3,
        rosseland_opacity_cm2_g=solution.rosseland_opacity_cm2_g,
        outward_flux_edges_erg_s_cm2=(
            solution.outward_flux_edges_erg_s_cm2
        ),
        interval_compression_work_erg_cm2=(
            solution.interval_compression_work_erg_cm2
        ),
        interval_dissipation_energy_erg_cm2=(
            solution.interval_dissipation_energy_erg_cm2
        ),
        interval_emergent_energy_erg_cm2=(
            solution.interval_emergent_energy_erg_cm2
        ),
    )
    os.replace(temporary, path)


def run_case(
    output_dir: Path,
    spec: CaseSpec,
    master_edges_path: Path,
    variable_edges_path: Path,
    *,
    force: bool,
) -> None:
    npz_path, report_path, checkpoint_path = case_paths(output_dir, spec)
    if force:
        for path in (npz_path, report_path, checkpoint_path):
            path.unlink(missing_ok=True)
    if npz_path.exists() or report_path.exists():
        if not npz_path.exists() or not report_path.exists():
            raise FileExistsError("a partial completed Phase 7B4n case exists")
        load_case(output_dir, spec)
        print(f"reusing {report_path.name}", flush=True)
        return
    master_edges = _saved_master_edges(master_edges_path)
    variable_edges = _saved_variable_edges(variable_edges_path, master_edges[64])
    frequency = _frequency()
    background, parent, grid, initial = _case_grid_and_initial(
        spec, frequency, master_edges, variable_edges
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
    restriction_residuals = _restriction_residuals(parent, solution)
    conservation = {**initial_residuals, **restriction_residuals}
    conservation_passed = bool(
        max(conservation.values()) < CONSERVATION_TOLERANCE
    )
    _save_solution_atomic(npz_path, spec, solution)
    report = {
        "phase": case_phase_label(spec),
        "classification": "[A/V] independent joint depth-time dynamic case",
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
            "master_edges": master_edges_path.name,
            "variable_edges": variable_edges_path.name,
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
            "case_is_not_a_joint_gate_by_itself": True,
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
    print(
        json.dumps(
            {
                "case": spec.name,
                "runtime_s": runtime,
                "total_cycle_count": total_cycles,
                "cycle_residual": solution.cycle_residual,
                "conservation_passed": conservation_passed,
            },
            indent=2,
        ),
        flush=True,
    )


def load_case(
    output_dir: Path, spec: CaseSpec
) -> tuple[DynamicReferenceFields, dict[str, object], dict[str, np.ndarray]]:
    """读取并核验一个已完成的独立周期算例。"""
    npz_path, report_path, _ = case_paths(output_dir, spec)
    if not npz_path.exists() or not report_path.exists():
        raise FileNotFoundError(
            f"{spec.output_phase} case {spec.name} is incomplete"
        )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    configuration = report["configuration"]
    if (
        configuration["case"] != spec.name
        or int(configuration["phase_points"]) != spec.phase_points
        or int(configuration["depth_points"]) != spec.depth_points
    ):
        raise ValueError(f"saved case metadata no longer matches {spec.name}")
    with np.load(npz_path) as data:
        arrays = {name: np.array(data[name], copy=True) for name in data.files}
    fields = dynamic_reference_fields(
        arrays["orbital_phase"],
        arrays["mass_fraction_edges"],
        arrays["cell_mass_g_cm2"],
        arrays["temperature_k"],
        arrays["rosseland_opacity_cm2_g"],
        arrays["hydrogen_fraction"][:, :, 1],
        arrays["helium_fraction"][:, :, 2],
        arrays["outward_flux_edges_erg_s_cm2"][:, 0],
    )
    return fields, report, arrays


def _saved_dense_control_fields(
    profiles_path: Path,
    master_edges_path: Path,
) -> DynamicReferenceFields:
    edges = _saved_master_edges(master_edges_path)[64]
    background = _background(CONTROL_PHASE_POINTS)
    grid = build_periodic_dynamic_half_column(
        background,
        MASTER_DEPTH_POINTS,
        "uniform_specific",
        mass_fraction_edges=edges,
    )
    with profiles_path.open(newline="", encoding="utf-8") as stream:
        rows = [
            row
            for row in csv.DictReader(stream)
            if int(row["effective_depth_points"]) == MASTER_DEPTH_POINTS
        ]
    rows.sort(key=lambda row: (int(row["phase_index"]), int(row["depth_index"])))
    expected = CONTROL_PHASE_POINTS * MASTER_DEPTH_POINTS
    if len(rows) != expected:
        raise ValueError("Phase 7B4l dense control profile is incomplete")

    def field(name: str) -> np.ndarray:
        values = np.array([float(row[name]) for row in rows]).reshape(
            CONTROL_PHASE_POINTS, MASTER_DEPTH_POINTS
        )
        if not np.all(np.isfinite(values)):
            raise ValueError(f"saved dense control field {name} became non-finite")
        return values

    temperature = field("temperature_k")
    opacity = field("rosseland_opacity_cm2_g")
    flux = np.array(
        [
            diffusion_outward_flux_edges_erg_s_cm2(
                temperature[index], opacity[index], grid.cell_mass_g_cm2
            )[0]
            for index in range(CONTROL_PHASE_POINTS)
        ]
    )
    return dynamic_reference_fields(
        _phase(background),
        edges,
        grid.cell_mass_g_cm2,
        temperature,
        opacity,
        field("hydrogen_ionized_fraction"),
        field("helium_doubly_ionized_fraction"),
        flux,
    )


def _maximum_error_value(error: JointDynamicError) -> float:
    values = [
        error.surface_flux_relative_error,
        error.maximum_pointwise_temperature_or_opacity_relative_error,
        error.maximum_pointwise_population_absolute_error,
        error.maximum_column_mean_temperature_or_opacity_relative_error,
        error.maximum_column_mean_population_absolute_error,
    ]
    if error.maximum_he_iii_half_front_mass_fraction_error is not None:
        values.append(error.maximum_he_iii_half_front_mass_fraction_error)
    return max(values)


def _dense_reference_runtime(path: Path) -> float:
    report = json.loads(path.read_text(encoding="utf-8"))
    rows = [
        row
        for row in report["depth_convergence"]
        if bool(row["is_reference"])
        and int(row["effective_depth_points"]) == MASTER_DEPTH_POINTS
    ]
    if len(rows) != 1:
        raise ValueError("Phase 7B4l must contain one dense N=64 reference")
    return float(rows[0]["runtime_s"])


def _plot_colored_control(
    path: Path,
    colored: DynamicReferenceFields,
    dense: DynamicReferenceFields,
    error: JointDynamicError,
    colored_runtime: float,
    dense_runtime: float,
) -> None:
    phase = dense.orbital_phase
    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.4), constrained_layout=True)
    axes[0, 0].plot(
        phase, dense.surface_flux_erg_s_cm2, color="black", label="dense"
    )
    axes[0, 0].plot(
        phase,
        colored.surface_flux_erg_s_cm2,
        linestyle="--",
        label="three-color tridiagonal",
    )
    axes[0, 0].set(
        xlabel="Orbital time phase",
        ylabel="Surface flux (erg s$^{-1}$ cm$^{-2}$)",
        title="(a) Independent N=64, phase=64 solutions",
    )
    axes[0, 0].legend(fontsize=8)

    centres = 0.5 * (
        dense.mass_fraction_edges[:-1] + dense.mass_fraction_edges[1:]
    )
    selected = int(
        np.argmax(
            np.max(
                np.abs(
                    colored.helium_doubly_ionized_fraction
                    - dense.helium_doubly_ionized_fraction
                ),
                axis=1,
            )
        )
    )
    axes[0, 1].plot(
        centres,
        dense.helium_doubly_ionized_fraction[selected],
        color="black",
        label="dense",
    )
    axes[0, 1].plot(
        centres,
        colored.helium_doubly_ionized_fraction[selected],
        linestyle="--",
        label="three-color tridiagonal",
    )
    axes[0, 1].set(
        xlabel="Mass fraction from surface",
        ylabel="He III fraction",
        title=f"(b) Largest profile difference at phase index {selected}",
    )
    axes[0, 1].legend(fontsize=8)

    labels = (
        "Flux",
        "Point T/opacity",
        "Point population",
        "Column T/opacity",
        "Column population",
        "He III front",
    )
    values = (
        error.surface_flux_relative_error,
        error.maximum_pointwise_temperature_or_opacity_relative_error,
        error.maximum_pointwise_population_absolute_error,
        error.maximum_column_mean_temperature_or_opacity_relative_error,
        error.maximum_column_mean_population_absolute_error,
        error.maximum_he_iii_half_front_mass_fraction_error or 0.0,
    )
    axes[1, 0].semilogy(np.arange(len(labels)), values, marker="o")
    axes[1, 0].axhline(
        COLORED_JACOBIAN_EQUIVALENCE_TOLERANCE,
        color="black",
        linestyle=":",
        label="equivalence target",
    )
    axes[1, 0].set(
        ylabel="Maximum error",
        xticks=np.arange(len(labels)),
        xticklabels=labels,
        title="(c) Dense-colored numerical equivalence",
    )
    axes[1, 0].tick_params(axis="x", rotation=30, labelsize=7)
    axes[1, 0].legend(fontsize=8)

    axes[1, 1].bar(
        ["Dense", "Colored"],
        [dense_runtime, colored_runtime],
        color=["0.4", "C0"],
    )
    axes[1, 1].set(
        ylabel="Runtime (s)",
        title=f"(d) Speed ratio = {dense_runtime / colored_runtime:.2f}",
    )
    figure.suptitle(
        "Phase 7B4n: colored-Jacobian equivalence control", fontsize=14
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_control(
    output_dir: Path,
    master_edges_path: Path,
    variable_edges_path: Path,
    dense_profiles_path: Path,
    dense_report_path: Path,
    *,
    force: bool,
) -> None:
    run_case(
        output_dir,
        CONTROL_CASE,
        master_edges_path,
        variable_edges_path,
        force=force,
    )
    colored, colored_report, _ = load_case(output_dir, CONTROL_CASE)
    dense = _saved_dense_control_fields(dense_profiles_path, master_edges_path)
    error = compare_periodic_time_resolution(colored, dense)
    colored_runtime = float(colored_report["runtime_s"])
    dense_runtime = _dense_reference_runtime(dense_report_path)
    equivalence = bool(
        joint_dynamic_error_meets_target(
            error, COLORED_JACOBIAN_EQUIVALENCE_TOLERANCE
        )
        and error.front_status_mismatch_phase_count == 0
    )
    _plot_colored_control(
        output_dir / "phase7b4n_colored_jacobian_control.png",
        colored,
        dense,
        error,
        colored_runtime,
        dense_runtime,
    )
    report = {
        "phase": "7B4n-control",
        "classification": "[A-control/V] dense-colored numerical equivalence",
        "configuration": {
            "depth_points": MASTER_DEPTH_POINTS,
            "phase_points": CONTROL_PHASE_POINTS,
            "colored_jacobian_equivalence_tolerance": (
                COLORED_JACOBIAN_EQUIVALENCE_TOLERANCE
            ),
            "production_tolerance": PRODUCTION_TOLERANCE,
        },
        "comparison": asdict(error),
        "maximum_reported_error": _maximum_error_value(error),
        "runtime": {
            "dense_runtime_s": dense_runtime,
            "colored_runtime_s": colored_runtime,
            "dense_over_colored": dense_runtime / colored_runtime,
        },
        "decision": {
            "colored_tridiagonal_jacobian_equivalent_to_dense": equivalence,
            "colored_path_authorized_for_formal_joint_cases": equivalence,
            "formal_joint_cases_completed": False,
        },
    }
    _write_json_atomic(output_dir / "phase7b4n_control_report.json", report)
    print(json.dumps(report["decision"], indent=2), flush=True)


def _require_control(output_dir: Path) -> dict[str, object]:
    path = output_dir / "phase7b4n_control_report.json"
    if not path.exists():
        raise FileNotFoundError("Phase 7B4n colored control must run first")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not bool(
        report["decision"][
            "colored_tridiagonal_jacobian_equivalent_to_dense"
        ]
    ):
        raise RuntimeError("colored Jacobian control failed; formal cases are blocked")
    return report


def _energy_rows(
    cases: list[tuple[CaseSpec, dict[str, object]]]
) -> list[dict[str, object]]:
    rows = []
    for spec, report in cases:
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


def _comparison_row(
    axis: str,
    candidate: CaseSpec,
    reference: CaseSpec,
    error: JointDynamicError,
) -> dict[str, object]:
    return {
        "axis": axis,
        "candidate_case": candidate.name,
        "reference_case": reference.name,
        "candidate_depth_points": candidate.depth_points,
        "reference_depth_points": reference.depth_points,
        "candidate_phase_points": candidate.phase_points,
        "reference_phase_points": reference.phase_points,
        **asdict(error),
        "meets_production_target": joint_dynamic_error_meets_target(
            error, PRODUCTION_TOLERANCE
        ),
    }


def _time_population_error_locations(
    candidate: DynamicReferenceFields,
    reference: DynamicReferenceFields,
) -> list[dict[str, object]]:
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


def _column_mean(values: np.ndarray, mass: np.ndarray) -> np.ndarray:
    weight = mass / np.sum(mass)
    return np.sum(values * weight[None, :], axis=1)


def _phase_rows(
    reference: DynamicReferenceFields,
    arrays: dict[str, np.ndarray],
) -> list[dict[str, object]]:
    target = arrays["target_surface_flux_erg_s_cm2"]
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
            "column_mean_temperature_k": float(
                _column_mean(reference.temperature_k, reference.cell_mass_g_cm2)[
                    index
                ]
            ),
            "column_mean_hydrogen_ionized_fraction": float(
                _column_mean(
                    reference.hydrogen_ionized_fraction,
                    reference.cell_mass_g_cm2,
                )[index]
            ),
            "column_mean_helium_doubly_ionized_fraction": float(
                _column_mean(
                    reference.helium_doubly_ionized_fraction,
                    reference.cell_mass_g_cm2,
                )[index]
            ),
        }
        for index in range(reference.phase_points)
    ]


def _profile_rows(
    reference: DynamicReferenceFields, selected_phases: np.ndarray
) -> list[dict[str, object]]:
    centres = 0.5 * (
        reference.mass_fraction_edges[:-1] + reference.mass_fraction_edges[1:]
    )
    rows = []
    for phase_index in selected_phases:
        for depth_index, mass in enumerate(centres):
            rows.append(
                {
                    "phase_index": int(phase_index),
                    "orbital_phase": float(reference.orbital_phase[phase_index]),
                    "depth_index": depth_index,
                    "mass_fraction_centre": float(mass),
                    "temperature_k": float(
                        reference.temperature_k[phase_index, depth_index]
                    ),
                    "rosseland_opacity_cm2_g": float(
                        reference.rosseland_opacity_cm2_g[
                            phase_index, depth_index
                        ]
                    ),
                    "hydrogen_ionized_fraction": float(
                        reference.hydrogen_ionized_fraction[
                            phase_index, depth_index
                        ]
                    ),
                    "helium_doubly_ionized_fraction": float(
                        reference.helium_doubly_ionized_fraction[
                            phase_index, depth_index
                        ]
                    ),
                }
            )
    return rows


def _plot_joint_convergence(
    path: Path,
    time_candidate: DynamicReferenceFields,
    spatial_candidate: DynamicReferenceFields,
    reference: DynamicReferenceFields,
    reference_arrays: dict[str, np.ndarray],
    comparison_rows: list[dict[str, object]],
    energy_rows: list[dict[str, object]],
) -> int:
    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.4), constrained_layout=True)
    target = reference_arrays["target_surface_flux_erg_s_cm2"]
    axes[0, 0].plot(
        reference.orbital_phase,
        reference.surface_flux_erg_s_cm2 / target,
        color="black",
        label="N=64, phase=1024",
    )
    candidate_target = np.interp(
        time_candidate.orbital_phase,
        reference.orbital_phase,
        target,
        period=1.0,
    )
    axes[0, 0].plot(
        time_candidate.orbital_phase,
        time_candidate.surface_flux_erg_s_cm2 / candidate_target,
        linestyle="--",
        label="N=64, phase=512",
    )
    axes[0, 0].set(
        xlabel="Orbital time phase",
        ylabel="Emergent / instantaneous ZO flux",
        title="(a) Coupled high-depth time response",
    )
    axes[0, 0].legend(fontsize=8)

    reference_mass = 0.5 * (
        reference.mass_fraction_edges[:-1] + reference.mass_fraction_edges[1:]
    )
    spatial_mass = 0.5 * (
        spatial_candidate.mass_fraction_edges[:-1]
        + spatial_candidate.mass_fraction_edges[1:]
    )
    gradient = np.max(
        np.abs(
            np.gradient(
                reference.helium_doubly_ionized_fraction,
                reference_mass,
                axis=1,
            )
        ),
        axis=1,
    )
    selected = int(np.argmax(gradient))
    axes[0, 1].plot(
        reference_mass,
        reference.helium_doubly_ionized_fraction[selected],
        color="black",
        label="N=64",
    )
    axes[0, 1].plot(
        spatial_mass,
        spatial_candidate.helium_doubly_ionized_fraction[selected],
        marker="o",
        markersize=2.2,
        linestyle="--",
        label="N=62",
    )
    axes[0, 1].axhline(0.5, color="0.5", linestyle=":")
    axes[0, 1].set(
        xlabel="Mass fraction from surface",
        ylabel="He III fraction",
        title=f"(b) Strongest front at phase index {selected}",
    )
    axes[0, 1].legend(fontsize=8)

    metrics = (
        "surface_flux_relative_error",
        "maximum_pointwise_temperature_or_opacity_relative_error",
        "maximum_pointwise_population_absolute_error",
        "maximum_column_mean_temperature_or_opacity_relative_error",
        "maximum_column_mean_population_absolute_error",
        "maximum_he_iii_half_front_mass_fraction_error",
    )
    labels = ("Flux", "Point T/kappa", "Point pop.", "Column T/kappa", "Column pop.", "Front")
    x = np.arange(len(metrics))
    width = 0.36
    for offset, row, label in (
        (-width / 2.0, comparison_rows[0], "Time: 512 vs 1024"),
        (width / 2.0, comparison_rows[1], "Depth: 62 vs 64"),
    ):
        axes[1, 0].bar(
            x + offset,
            [0.0 if row[key] is None else row[key] for key in metrics],
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
        xticklabels=labels,
        title="(c) Predeclared coupled convergence metrics",
    )
    axes[1, 0].tick_params(axis="x", rotation=30, labelsize=7)
    axes[1, 0].legend(fontsize=7)

    case_labels = [
        f"{row['depth_points']}x{row['phase_points']}" for row in energy_rows
    ]
    axes[1, 1].semilogy(
        case_labels,
        [row["cycle_residual"] for row in energy_rows],
        marker="o",
        label="Cycle residual",
    )
    axes[1, 1].semilogy(
        case_labels,
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
        "Phase 7B4n: joint depth-time dynamic reference", fontsize=14
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)
    return selected


def _plot_reference_map(
    path: Path,
    reference: DynamicReferenceFields,
    arrays: dict[str, np.ndarray],
) -> None:
    phase = reference.orbital_phase
    mass = 0.5 * (
        reference.mass_fraction_edges[:-1] + reference.mass_fraction_edges[1:]
    )
    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.4), constrained_layout=True)
    temperature_image = axes[0, 0].pcolormesh(
        phase,
        mass,
        np.log10(reference.temperature_k).T,
        shading="nearest",
    )
    figure.colorbar(temperature_image, ax=axes[0, 0], label="log10 Temperature (K)")
    axes[0, 0].set(
        xlabel="Orbital time phase",
        ylabel="Mass fraction from surface",
        title="(a) Dynamic temperature",
    )

    helium_image = axes[0, 1].pcolormesh(
        phase,
        mass,
        reference.helium_doubly_ionized_fraction.T,
        shading="nearest",
        vmin=0.0,
        vmax=1.0,
    )
    figure.colorbar(helium_image, ax=axes[0, 1], label="He III fraction")
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
        title="(c) Thermal-memory response",
    )

    axes[1, 1].plot(
        phase,
        _column_mean(
            reference.hydrogen_ionized_fraction, reference.cell_mass_g_cm2
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
        "Phase 7B4n: N=64, 1024-phase periodic dynamic column", fontsize=14
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_summary(output_dir: Path, inherited_time_report_path: Path) -> None:
    control = _require_control(output_dir)
    loaded = {spec.name: load_case(output_dir, spec) for spec in FORMAL_CASES}
    time_spec, spatial_spec, reference_spec = FORMAL_CASES
    time_fields, time_report, _ = loaded[time_spec.name]
    spatial_fields, spatial_report, _ = loaded[spatial_spec.name]
    reference_fields, reference_report, reference_arrays = loaded[
        reference_spec.name
    ]
    time_error = compare_periodic_time_resolution(time_fields, reference_fields)
    spatial_error = compare_nested_depth_resolution(
        spatial_fields, reference_fields
    )
    population_error_locations = _time_population_error_locations(
        time_fields, reference_fields
    )
    comparison_rows = [
        _comparison_row("time", time_spec, reference_spec, time_error),
        _comparison_row("depth", spatial_spec, reference_spec, spatial_error),
    ]
    reports = [
        (time_spec, time_report),
        (spatial_spec, spatial_report),
        (reference_spec, reference_report),
    ]
    energy_rows = _energy_rows(reports)
    inherited = json.loads(inherited_time_report_path.read_text(encoding="utf-8"))
    inherited_time_pass = bool(
        inherited["decision"][
            "time_1024_production_converged_against_2048"
        ]
    )
    all_cases_conserve = all(
        bool(report["decision"]["initial_and_restriction_conservation_passed"])
        for _, report in reports
    )
    all_cases_cycle = all(
        bool(report["decision"]["cycle_converged"])
        for _, report in reports
    )
    high_depth_time_pass = bool(
        comparison_rows[0]["meets_production_target"]
    )
    high_time_depth_pass = bool(
        comparison_rows[1]["meets_production_target"]
    )
    colored_pass = bool(
        control["decision"][
            "colored_tridiagonal_jacobian_equivalent_to_dense"
        ]
    )
    joint_pass = bool(
        colored_pass
        and inherited_time_pass
        and high_depth_time_pass
        and high_time_depth_pass
        and all_cases_conserve
        and all_cases_cycle
    )
    _write_csv(output_dir / "phase7b4n_joint_convergence.csv", comparison_rows)
    _write_csv(
        output_dir / "phase7b4n_time_population_error_locations.csv",
        population_error_locations,
    )
    _write_csv(output_dir / "phase7b4n_energy_ledger.csv", energy_rows)
    _write_csv(
        output_dir / "phase7b4n_reference_phase.csv",
        _phase_rows(reference_fields, reference_arrays),
    )
    selected = _plot_joint_convergence(
        output_dir / "phase7b4n_joint_convergence.png",
        time_fields,
        spatial_fields,
        reference_fields,
        reference_arrays,
        comparison_rows,
        energy_rows,
    )
    selected_phases = np.unique(
        np.array(
            [
                0,
                selected,
                reference_fields.phase_points // 4,
                reference_fields.phase_points // 2,
                3 * reference_fields.phase_points // 4,
            ],
            dtype=np.int64,
        )
    )
    _write_csv(
        output_dir / "phase7b4n_reference_profiles.csv",
        _profile_rows(reference_fields, selected_phases),
    )
    _plot_reference_map(
        output_dir / "phase7b4n_joint_reference_map.png",
        reference_fields,
        reference_arrays,
    )
    report = {
        "phase": "7B4n-complete",
        "classification": "[A/V/O] joint finite depth-time dynamic reference",
        "provenance": {
            "colored_control_report": "phase7b4n_control_report.json",
            "inherited_direct_1024_vs_2048_time_report": (
                inherited_time_report_path.name
            ),
            "formal_case_reports": [
                case_paths(output_dir, spec)[1].name for spec in FORMAL_CASES
            ],
        },
        "configuration": {
            "production_depth_points": MASTER_DEPTH_POINTS,
            "production_phase_points": PRODUCTION_PHASE_POINTS,
            "spatial_candidate_depth_points": (
                SPATIAL_CANDIDATE_DEPTH_POINTS
            ),
            "time_candidate_phase_points": TIME_CANDIDATE_PHASE_POINTS,
            "production_tolerance": PRODUCTION_TOLERANCE,
            "conservation_tolerance": CONSERVATION_TOLERANCE,
            "frequency_points": int(_frequency().size),
            "selected_front_phase_index": selected,
        },
        "comparison": {
            "high_depth_time_512_against_1024": asdict(time_error),
            "high_time_depth_62_against_64": asdict(spatial_error),
            "inherited_low_depth_1024_against_2048": next(
                row
                for row in inherited["time_convergence"]
                if int(row["phase_points"]) == 1024
            ),
            "high_depth_time_population_error_locations": (
                population_error_locations
            ),
        },
        "energy_ledger": energy_rows,
        "decision": {
            "colored_jacobian_numerical_control_passed": colored_pass,
            "inherited_low_depth_1024_vs_2048_time_gate_passed": (
                inherited_time_pass
            ),
            "high_depth_512_vs_1024_time_difference_below_target": (
                high_depth_time_pass
            ),
            "high_time_62_vs_64_spatial_difference_below_target": (
                high_time_depth_pass
            ),
            "all_formal_cases_conserve": all_cases_conserve,
            "all_formal_cases_close_periodically": all_cases_cycle,
            "joint_64_depth_1024_phase_reference_completed": True,
            "joint_depth_time_gate_passed": joint_pass,
            "nonlocal_frequency_dependent_dynamic_transfer_authorized": (
                joint_pass
            ),
            "phase4_atmosphere_replacement_authorized": False,
            "uvot_authorized": False,
            "next_microphase_if_joint_passes": (
                "nonlocal frequency-dependent transfer on the completed periodic "
                "dynamic reference; retain ground-state/local-closure boundaries"
            ),
            "next_microphase_if_joint_fails_time": (
                "run the N=64, 2048-phase joint reference before nonlocal transfer"
            ),
            "next_microphase_if_joint_fails_depth": (
                "raise the finite depth reference above N=64 before nonlocal transfer"
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
    _write_json_atomic(
        output_dir / "phase7b4n_complete_report.json", report
    )
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
        "--dense-profiles",
        type=Path,
        default=Path("outputs/phase7b4l_subcell_profiles.csv"),
    )
    parser.add_argument(
        "--dense-report",
        type=Path,
        default=Path("outputs/phase7b4l_subcell_report.json"),
    )
    parser.add_argument(
        "--inherited-time-report",
        type=Path,
        default=Path("outputs/phase7b4k_time_report.json"),
    )
    parser.add_argument(
        "--stage", choices=("control", "case", "summary", "all"), default="all"
    )
    parser.add_argument("--case", choices=tuple(ALL_CASES))
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if arguments.stage == "case" and arguments.case is None:
        parser.error("--stage case requires --case")
    if arguments.stage != "case" and arguments.case is not None:
        parser.error("--case is only valid with --stage case")
    if arguments.stage in ("control", "all"):
        run_control(
            arguments.output_dir,
            arguments.master_edges,
            arguments.variable_edges,
            arguments.dense_profiles,
            arguments.dense_report,
            force=arguments.force,
        )
    if arguments.stage == "case":
        _require_control(arguments.output_dir)
        run_case(
            arguments.output_dir,
            ALL_CASES[arguments.case],
            arguments.master_edges,
            arguments.variable_edges,
            force=arguments.force,
        )
    if arguments.stage == "all":
        _require_control(arguments.output_dir)
        for spec in FORMAL_CASES:
            run_case(
                arguments.output_dir,
                spec,
                arguments.master_edges,
                arguments.variable_edges,
                force=arguments.force,
            )
    if arguments.stage in ("summary", "all"):
        run_summary(arguments.output_dir, arguments.inherited_time_report)


if __name__ == "__main__":
    main()
