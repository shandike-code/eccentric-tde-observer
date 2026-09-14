"""生成 Phase 7B4p 冻结动态柱的全轨道非局域转移审计。"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.continuum_emission import (
    edge_resolved_milne_energy_grid_ev,
    ground_state_milne_continuum,
)
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.nonlocal_dynamic_transfer import (
    FrozenNonlocalTransferPhase,
    radiation_timescale_audit,
    solve_frozen_nonlocal_transfer_phase,
)
from eccentric_tde_observer.radiation import (
    LIGHT_SPEED_CM_S,
    PLANCK_ERG_S,
    planck_nu,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_half_range_mu_weights,
    solve_static_slab_transfer,
)


ENERGY_RANGE_EV = (0.1, 5000.0)
FREQUENCY_BASE_POINTS = 65
ANGULAR_ORDER = 4
CHECKPOINT_PHASES = 64
DEFAULT_WORKERS = 8
CONTROL_TOLERANCE = 2.0e-8
PRODUCTION_TOLERANCE = 1.0e-3
QUASISTATIC_DIFFUSION_TO_ORBIT_TARGET = 0.1
REPRESENTATIVE_PHASES = np.array(
    (0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 0.97, 0.985, 0.99, 0.995),
    dtype=np.float64,
)
ANGULAR_ORDERS = (4, 8, 12)
FREQUENCY_BASE_REFINEMENT = (33, 65, 129)
SPECIES_LABELS = ("H I", "He I", "He II")


@dataclass(frozen=True)
class OrbitSpec:
    name: str
    phase_points: int
    input_npz: str
    input_report: str


TIME_CASES = (
    OrbitSpec(
        "depth64_phase1024",
        1024,
        "phase7b4n_depth64_phase1024.npz",
        "phase7b4n_depth64_phase1024.json",
    ),
    OrbitSpec(
        "depth64_phase2048",
        2048,
        "phase7b4o_depth64_phase2048.npz",
        "phase7b4o_depth64_phase2048.json",
    ),
)
ALL_CASES = {case.name: case for case in TIME_CASES}

_WORKER_FREQUENCY: np.ndarray | None = None
_WORKER_CELL_MASS: np.ndarray | None = None
_WORKER_ANGULAR_ORDER: int | None = None


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


def _frequency(base_points: int = FREQUENCY_BASE_POINTS) -> np.ndarray:
    energy = edge_resolved_milne_energy_grid_ev(
        ENERGY_RANGE_EV[0], ENERGY_RANGE_EV[1], base_points
    )
    return energy * EV_ERG / PLANCK_ERG_S


def _initialize_worker(
    frequency_hz: np.ndarray, cell_mass_g_cm2: np.ndarray, angular_order: int
) -> None:
    global _WORKER_FREQUENCY, _WORKER_CELL_MASS, _WORKER_ANGULAR_ORDER
    _WORKER_FREQUENCY = frequency_hz
    _WORKER_CELL_MASS = cell_mass_g_cm2
    _WORKER_ANGULAR_ORDER = angular_order


def _reduced_phase_result(
    result: FrozenNonlocalTransferPhase,
    density_g_cm3: np.ndarray,
) -> dict[str, np.ndarray | float]:
    return {
        "mean_intensity_cgs": np.array(
            result.mean_intensity_top_half_cgs, copy=True
        ),
        "top_outward_flux_nu_cgs": np.array(
            result.top_outward_flux_nu_cgs, copy=True
        ),
        "radiative_heating_erg_s_g": np.array(
            result.radiative_heating_top_half_erg_s_cm3 / density_g_cm3,
            copy=True,
        ),
        "nonlocal_photoionization_s1": np.array(
            result.nonlocal_rates.photoionization_s1, copy=True
        ),
        "local_photoionization_s1": np.array(
            result.local_planck_rates.photoionization_s1, copy=True
        ),
        "nonlocal_total_recombination_cm3_s": np.array(
            result.nonlocal_rates.total_recombination_cm3_s, copy=True
        ),
        "local_total_recombination_cm3_s": np.array(
            result.local_planck_rates.total_recombination_cm3_s, copy=True
        ),
        "extinction_optical_depth_full": np.array(
            result.extinction_optical_depth_full, copy=True
        ),
        "true_absorption_optical_depth_full": np.array(
            result.true_absorption_optical_depth_full, copy=True
        ),
        "top_outward_bolometric_flux_erg_s_cm2": (
            result.top_outward_bolometric_flux_erg_s_cm2
        ),
        "relative_integrated_energy_residual": (
            result.relative_integrated_energy_residual
        ),
        "maximum_source_equation_residual": (
            result.maximum_source_equation_residual
        ),
        "maximum_lambda_system_condition_number": (
            result.maximum_lambda_system_condition_number
        ),
        "maximum_mean_intensity_mirror_residual": (
            result.maximum_mean_intensity_mirror_residual
        ),
        "maximum_boundary_spectrum_mirror_residual": (
            result.maximum_boundary_spectrum_mirror_residual
        ),
        "minimum_intensity_cgs": result.minimum_intensity_cgs,
        "minimum_source_function_cgs": result.minimum_source_function_cgs,
    }


def _phase_worker(
    payload: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]
) -> dict[str, np.ndarray | float]:
    if (
        _WORKER_FREQUENCY is None
        or _WORKER_CELL_MASS is None
        or _WORKER_ANGULAR_ORDER is None
    ):
        raise RuntimeError("nonlocal transfer worker was not initialized")
    density, temperature, hydrogen, helium = payload
    result = solve_frozen_nonlocal_transfer_phase(
        _WORKER_FREQUENCY,
        _WORKER_CELL_MASS,
        density,
        temperature,
        hydrogen,
        helium,
        angular_order=_WORKER_ANGULAR_ORDER,
    )
    return _reduced_phase_result(result, density)


ARRAY_KEYS = (
    "mean_intensity_cgs",
    "top_outward_flux_nu_cgs",
    "radiative_heating_erg_s_g",
    "nonlocal_photoionization_s1",
    "local_photoionization_s1",
    "nonlocal_total_recombination_cm3_s",
    "local_total_recombination_cm3_s",
    "extinction_optical_depth_full",
    "true_absorption_optical_depth_full",
    "top_outward_bolometric_flux_erg_s_cm2",
    "relative_integrated_energy_residual",
    "maximum_source_equation_residual",
    "maximum_lambda_system_condition_number",
    "maximum_mean_intensity_mirror_residual",
    "maximum_boundary_spectrum_mirror_residual",
    "minimum_intensity_cgs",
    "minimum_source_function_cgs",
)


def _case_paths(output_dir: Path, spec: OrbitSpec) -> tuple[Path, Path, Path]:
    stem = f"phase7b4p_{spec.name}_frozen_nonlocal"
    return (
        output_dir / f"{stem}.npz",
        output_dir / f"{stem}.json",
        output_dir / f"{stem}.checkpoint.npz",
    )


def _load_dynamic_input(
    output_dir: Path, spec: OrbitSpec
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    npz_path = output_dir / spec.input_npz
    report_path = output_dir / spec.input_report
    if not npz_path.exists() or not report_path.exists():
        raise FileNotFoundError(f"dynamic input for {spec.name} is incomplete")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    configuration = report["configuration"]
    if (
        int(configuration["phase_points"]) != spec.phase_points
        or int(configuration["depth_points"]) != 64
        or int(configuration["frequency_points"]) != _frequency().size
    ):
        raise ValueError(f"dynamic input metadata does not match {spec.name}")
    with np.load(npz_path) as data:
        arrays = {name: np.array(data[name], copy=True) for name in data.files}
    expected = (spec.phase_points, 64)
    if (
        arrays["density_g_cm3"].shape != expected
        or arrays["temperature_k"].shape != expected
        or arrays["hydrogen_fraction"].shape != (*expected, 2)
        or arrays["helium_fraction"].shape != (*expected, 3)
    ):
        raise ValueError(f"dynamic input arrays do not match {spec.name}")
    numeric = tuple(
        value for value in arrays.values() if value.dtype.kind in "fiu"
    )
    if not all(np.all(np.isfinite(value)) for value in numeric):
        raise ValueError(f"dynamic input {spec.name} contains a non-finite value")
    return arrays, report


def _save_orbit_atomic(
    path: Path,
    spec: OrbitSpec,
    frequency_hz: np.ndarray,
    dynamic: dict[str, np.ndarray],
    result_arrays: dict[str, np.ndarray],
    completed_phase_count: int,
    accumulated_runtime_s: float,
) -> None:
    temporary = path.with_name(f"{path.stem}.tmp.npz")
    np.savez_compressed(
        temporary,
        case_name=np.array(spec.name),
        completed_phase_count=np.array(completed_phase_count),
        phase_points=np.array(spec.phase_points),
        depth_points=np.array(64),
        angular_order=np.array(ANGULAR_ORDER),
        frequency_hz=frequency_hz,
        orbital_phase=dynamic["orbital_phase"][:completed_phase_count],
        time_since_pericentre_s=dynamic["time_since_pericentre_s"][
            :completed_phase_count
        ],
        cell_mass_g_cm2=dynamic["cell_mass_g_cm2"],
        accumulated_runtime_s=np.array(accumulated_runtime_s),
        **result_arrays,
    )
    os.replace(temporary, path)


def _load_checkpoint(
    path: Path,
    spec: OrbitSpec,
    frequency_hz: np.ndarray,
    cell_mass_g_cm2: np.ndarray,
) -> tuple[int, float, dict[str, list[np.ndarray | float]]]:
    with np.load(path) as data:
        if (
            str(data["case_name"].item()) != spec.name
            or int(data["phase_points"]) != spec.phase_points
            or int(data["depth_points"]) != 64
            or int(data["angular_order"]) != ANGULAR_ORDER
            or not np.array_equal(data["frequency_hz"], frequency_hz)
            or not np.array_equal(data["cell_mass_g_cm2"], cell_mass_g_cm2)
        ):
            raise ValueError("frozen nonlocal checkpoint metadata no longer matches")
        completed = int(data["completed_phase_count"])
        runtime = float(data["accumulated_runtime_s"])
        values = {
            key: [np.array(value, copy=True) for value in data[key]]
            for key in ARRAY_KEYS
        }
    if completed < 1 or completed >= spec.phase_points:
        raise ValueError("frozen nonlocal checkpoint has no valid remaining work")
    if not np.isfinite(runtime) or runtime <= 0.0:
        raise ValueError("frozen nonlocal checkpoint runtime is invalid")
    if any(len(value) != completed for value in values.values()):
        raise ValueError("frozen nonlocal checkpoint arrays are incomplete")
    return completed, runtime, values


def _stack_results(
    values: dict[str, list[np.ndarray | float]]
) -> dict[str, np.ndarray]:
    result = {key: np.asarray(values[key], dtype=np.float64) for key in ARRAY_KEYS}
    if not all(np.all(np.isfinite(value)) for value in result.values()):
        raise ArithmeticError("frozen nonlocal orbit result became non-finite")
    return result


def run_orbit_case(
    output_dir: Path,
    spec: OrbitSpec,
    *,
    workers: int,
    force: bool,
) -> None:
    npz_path, report_path, checkpoint_path = _case_paths(output_dir, spec)
    if force:
        for path in (npz_path, report_path, checkpoint_path):
            path.unlink(missing_ok=True)
    if npz_path.exists() or report_path.exists():
        if not npz_path.exists() or not report_path.exists():
            raise FileExistsError("partial completed frozen nonlocal case exists")
        print(f"reusing {report_path.name}", flush=True)
        return
    dynamic, input_report = _load_dynamic_input(output_dir, spec)
    frequency = _frequency()
    completed = 0
    accumulated_runtime = 0.0
    values: dict[str, list[np.ndarray | float]] = {
        key: [] for key in ARRAY_KEYS
    }
    if checkpoint_path.exists():
        completed, accumulated_runtime, values = _load_checkpoint(
            checkpoint_path,
            spec,
            frequency,
            dynamic["cell_mass_g_cm2"],
        )
        print(f"resuming {spec.name} after {completed} phases", flush=True)
    started = time.perf_counter()
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=context,
        initializer=_initialize_worker,
        initargs=(frequency, dynamic["cell_mass_g_cm2"], ANGULAR_ORDER),
    ) as executor:
        for batch_start in range(completed, spec.phase_points, CHECKPOINT_PHASES):
            batch_end = min(batch_start + CHECKPOINT_PHASES, spec.phase_points)
            payloads = [
                (
                    dynamic["density_g_cm3"][index],
                    dynamic["temperature_k"][index],
                    dynamic["hydrogen_fraction"][index],
                    dynamic["helium_fraction"][index],
                )
                for index in range(batch_start, batch_end)
            ]
            for reduced in executor.map(_phase_worker, payloads, chunksize=1):
                for key in ARRAY_KEYS:
                    values[key].append(reduced[key])
            result_arrays = _stack_results(values)
            elapsed = accumulated_runtime + time.perf_counter() - started
            _save_orbit_atomic(
                checkpoint_path,
                spec,
                frequency,
                dynamic,
                result_arrays,
                batch_end,
                elapsed,
            )
            print(
                json.dumps(
                    {
                        "case": spec.name,
                        "completed_phase_count": batch_end,
                        "runtime_s": elapsed,
                        "maximum_energy_residual": float(
                            np.max(
                                result_arrays[
                                    "relative_integrated_energy_residual"
                                ]
                            )
                        ),
                    }
                ),
                flush=True,
            )
    runtime = accumulated_runtime + time.perf_counter() - started
    result_arrays = _stack_results(values)
    _save_orbit_atomic(
        npz_path,
        spec,
        frequency,
        dynamic,
        result_arrays,
        spec.phase_points,
        runtime,
    )
    period = float(
        dynamic["time_since_pericentre_s"][-1]
        + dynamic["step_duration_s"][-1]
    )
    timescale = radiation_timescale_audit(
        dynamic["cell_mass_g_cm2"],
        dynamic["density_g_cm3"],
        dynamic["rosseland_opacity_cm2_g"],
        period,
    )
    report = {
        "phase": "7B4p-case",
        "classification": "[A/V/O] frozen-state nonlocal transfer orbit",
        "configuration": {
            "case": spec.name,
            "phase_points": spec.phase_points,
            "depth_points": 64,
            "full_mirrored_depth_points": 128,
            "frequency_points": int(frequency.size),
            "angular_order": ANGULAR_ORDER,
            "energy_range_ev": list(ENERGY_RANGE_EV),
            "electron_scattering": True,
            "top_and_bottom_boundary": "vacuum",
        },
        "provenance": {
            "dynamic_input_npz": spec.input_npz,
            "dynamic_input_report": spec.input_report,
            "dynamic_input_radiation_closure": "local_planck_milne",
            "independent_dynamic_case_runtime_s": input_report["runtime_s"],
            "checkpoint_phase_batch": CHECKPOINT_PHASES,
            "worker_processes": workers,
        },
        "runtime_s": runtime,
        "transfer_diagnostics": {
            "maximum_relative_integrated_energy_residual": float(
                np.max(result_arrays["relative_integrated_energy_residual"])
            ),
            "maximum_source_equation_residual": float(
                np.max(result_arrays["maximum_source_equation_residual"])
            ),
            "maximum_lambda_system_condition_number": float(
                np.max(
                    result_arrays["maximum_lambda_system_condition_number"]
                )
            ),
            "maximum_mean_intensity_mirror_residual": float(
                np.max(
                    result_arrays["maximum_mean_intensity_mirror_residual"]
                )
            ),
            "maximum_boundary_spectrum_mirror_residual": float(
                np.max(
                    result_arrays["maximum_boundary_spectrum_mirror_residual"]
                )
            ),
            "minimum_intensity_cgs": float(
                np.min(result_arrays["minimum_intensity_cgs"])
            ),
            "minimum_source_function_cgs": float(
                np.min(result_arrays["minimum_source_function_cgs"])
            ),
        },
        "radiation_timescale": {
            "orbital_period_s": timescale.orbital_period_s,
            "minimum_half_thickness_cm": float(
                np.min(timescale.half_thickness_cm)
            ),
            "maximum_half_thickness_cm": float(
                np.max(timescale.half_thickness_cm)
            ),
            "minimum_half_rosseland_optical_depth": float(
                np.min(timescale.half_rosseland_optical_depth)
            ),
            "maximum_half_rosseland_optical_depth": float(
                np.max(timescale.half_rosseland_optical_depth)
            ),
            "minimum_diffusion_time_s": float(
                np.min(timescale.diffusion_time_s)
            ),
            "maximum_diffusion_time_s": float(
                np.max(timescale.diffusion_time_s)
            ),
            "maximum_light_crossing_to_orbit": (
                timescale.maximum_light_crossing_to_orbit
            ),
            "maximum_diffusion_to_orbit": (
                timescale.maximum_diffusion_to_orbit
            ),
            "phase_fraction_diffusion_to_orbit_above_003": (
                timescale.phase_fraction_diffusion_to_orbit_above_003
            ),
            "phase_fraction_diffusion_to_orbit_above_01": (
                timescale.phase_fraction_diffusion_to_orbit_above_01
            ),
            "phase_fraction_diffusion_to_orbit_above_03": (
                timescale.phase_fraction_diffusion_to_orbit_above_03
            ),
            "quasistatic_target": QUASISTATIC_DIFFUSION_TO_ORBIT_TARGET,
        },
        "decision": {
            "all_phase_transfer_controls_passed": bool(
                np.max(result_arrays["relative_integrated_energy_residual"])
                < CONTROL_TOLERANCE
                and np.max(result_arrays["maximum_source_equation_residual"])
                < CONTROL_TOLERANCE
                and np.max(
                    result_arrays["maximum_mean_intensity_mirror_residual"]
                )
                < CONTROL_TOLERANCE
                and np.max(
                    result_arrays["maximum_boundary_spectrum_mirror_residual"]
                )
                < CONTROL_TOLERANCE
            ),
            "quasistatic_radiation_gate_passed": bool(
                timescale.maximum_diffusion_to_orbit
                < QUASISTATIC_DIFFUSION_TO_ORBIT_TARGET
            ),
            "frozen_transfer_is_not_coupled_solution": True,
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


def _load_npz_arrays(path: Path) -> dict[str, np.ndarray]:
    if not path.exists():
        raise FileNotFoundError(path)
    with np.load(path) as data:
        arrays = {name: np.array(data[name], copy=True) for name in data.files}
    numeric = tuple(value for value in arrays.values() if value.dtype.kind in "fiu")
    if not all(np.all(np.isfinite(value)) for value in numeric):
        raise ValueError(f"{path.name} contains a non-finite value")
    return arrays


def periodic_interpolate(
    source_phase: np.ndarray,
    values: np.ndarray,
    target_phase: np.ndarray,
) -> np.ndarray:
    """沿轨道相位周期插值任意尾随维数的数组。"""
    source = np.asarray(source_phase, dtype=np.float64)
    target = np.asarray(target_phase, dtype=np.float64)
    array = np.asarray(values, dtype=np.float64)
    if (
        source.ndim != 1
        or target.ndim != 1
        or array.ndim < 1
        or array.shape[0] != source.size
        or np.any(np.diff(source) <= 0.0)
        or not np.all(np.isfinite(source))
        or not np.all(np.isfinite(target))
        or not np.all(np.isfinite(array))
    ):
        raise ValueError("periodic interpolation inputs are inconsistent")
    flattened = array.reshape(source.size, -1)
    interpolated = np.empty((target.size, flattened.shape[1]), dtype=np.float64)
    for column in range(flattened.shape[1]):
        interpolated[:, column] = np.interp(
            target, source, flattened[:, column], period=1.0
        )
    return interpolated.reshape((target.size, *array.shape[1:]))


def scale_normalized_maximum_error(
    candidate: np.ndarray | float,
    reference: np.ndarray | float,
) -> float:
    """以参考量全局最大绝对值归一化最大绝对差。"""
    first = np.asarray(candidate, dtype=np.float64)
    second = np.asarray(reference, dtype=np.float64)
    if first.shape != second.shape:
        raise ValueError("error comparison requires matching shapes")
    if not np.all(np.isfinite(first)) or not np.all(np.isfinite(second)):
        raise ValueError("error comparison requires finite values")
    scale = float(np.max(np.abs(second)))
    difference = float(np.max(np.abs(first - second)))
    return difference / scale if scale > 0.0 else difference


def _lte_half_column(
    depth_points: int = 6,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mass = np.geomspace(0.02, 0.3, depth_points)
    density = np.geomspace(2.0e-10, 3.0e-8, depth_points)
    temperature = np.linspace(1.8e4, 3.2e4, depth_points)
    ionization = lte_hydrogen_helium_ionization(density, temperature)
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
    return mass, density, temperature, hydrogen, helium


def run_controls(output_dir: Path, *, force: bool) -> None:
    csv_path = output_dir / "phase7b4p_controls.csv"
    report_path = output_dir / "phase7b4p_controls.json"
    if not force and csv_path.exists() and report_path.exists():
        print(f"reusing {report_path.name}", flush=True)
        return

    frequency = _frequency()
    mass, density, temperature, hydrogen, helium = _lte_half_column()
    continuum = ground_state_milne_continuum(
        density,
        temperature,
        frequency,
        hydrogen[:, 0],
        hydrogen[:, 1],
        helium[:, 0],
        helium[:, 1],
        helium[:, 2],
        include_electron_scattering=False,
    )
    planck = planck_nu(frequency[:, None], temperature[None, :])
    kirchhoff_error = scale_normalized_maximum_error(
        continuum.thermal_source_intensity, planck
    )

    symmetric = solve_frozen_nonlocal_transfer_phase(
        frequency,
        mass,
        density,
        temperature,
        hydrogen,
        helium,
        angular_order=8,
    )

    mu, weight = gauss_legendre_half_range_mu_weights(8)
    top_incoming = np.zeros((1, mu.size), dtype=np.float64)
    top_incoming[:, mu > 0.0] = 2.0
    scattering = solve_static_slab_transfer(
        np.array([1.0e15]),
        np.linspace(0.0, 4.0, 17),
        mu,
        weight,
        np.full((1, 16), 0.7),
        np.zeros((1, 16)),
        np.zeros((1, 16)),
        top_incoming_intensity=top_incoming,
    )
    scattering_error = scale_normalized_maximum_error(
        scattering.top_net_flux, scattering.bottom_net_flux
    )

    depth_points = 80
    edges = np.arange(depth_points + 1, dtype=np.float64)
    centres = 0.5 * (edges[:-1] + edges[1:])
    extinction = 5.0
    source_gradient = 2.0e-3
    source = 1.0 + source_gradient * centres
    diffusion_mu, diffusion_weight = gauss_legendre_half_range_mu_weights(16)
    diffusion = solve_static_slab_transfer(
        np.array([1.0e15]),
        edges,
        diffusion_mu,
        diffusion_weight,
        np.full((1, depth_points), extinction),
        source[None, :],
        np.ones((1, depth_points)),
    )
    cell_flux = 2.0 * np.pi * np.einsum(
        "m,fmz,m->fz",
        diffusion_weight,
        diffusion.intensity_cell_average,
        diffusion_mu,
    )[0]
    expected_flux = -4.0 * np.pi * source_gradient / (3.0 * extinction)
    diffusion_error = scale_normalized_maximum_error(
        cell_flux[20:60], np.full(40, expected_flux)
    )

    rows = [
        {
            "control": "LTE Kirchhoff source equals Planck intensity",
            "error": kirchhoff_error,
            "target": CONTROL_TOLERANCE,
            "passed": kirchhoff_error < CONTROL_TOLERANCE,
        },
        {
            "control": "symmetric full-column integrated energy",
            "error": symmetric.relative_integrated_energy_residual,
            "target": CONTROL_TOLERANCE,
            "passed": symmetric.relative_integrated_energy_residual
            < CONTROL_TOLERANCE,
        },
        {
            "control": "symmetric full-column mean-intensity mirror",
            "error": symmetric.maximum_mean_intensity_mirror_residual,
            "target": CONTROL_TOLERANCE,
            "passed": symmetric.maximum_mean_intensity_mirror_residual
            < CONTROL_TOLERANCE,
        },
        {
            "control": "pure coherent-scattering flux conservation",
            "error": scattering_error,
            "target": CONTROL_TOLERANCE,
            "passed": scattering_error < CONTROL_TOLERANCE,
        },
        {
            "control": "optically thick linear-source diffusion flux",
            "error": diffusion_error,
            "target": CONTROL_TOLERANCE,
            "passed": diffusion_error < CONTROL_TOLERANCE,
        },
    ]
    _write_csv(csv_path, rows)
    report = {
        "phase": "7B4p-controls",
        "classification": "[V] analytic and thermodynamic controls",
        "controls": rows,
        "decision": {"all_controls_passed": all(row["passed"] for row in rows)},
    }
    _write_json_atomic(report_path, report)
    print(json.dumps(report["decision"], indent=2), flush=True)


def _phase_transfer_fields(
    result: FrozenNonlocalTransferPhase,
    density_g_cm3: np.ndarray,
) -> dict[str, np.ndarray]:
    frequency = result.frequency_hz
    return {
        "bolometric_flux": np.array(
            [result.top_outward_bolometric_flux_erg_s_cm2]
        ),
        "radiation_energy_density": 4.0
        * np.pi
        / LIGHT_SPEED_CM_S
        * np.trapezoid(result.mean_intensity_top_half_cgs, frequency, axis=0),
        "radiative_heating": (
            result.radiative_heating_top_half_erg_s_cm3 / density_g_cm3
        ),
        "photoionization": result.nonlocal_rates.photoionization_s1,
        "recombination": result.nonlocal_rates.total_recombination_cm3_s,
    }


def _mass_reduce_fields(
    fields: dict[str, np.ndarray], cell_mass_g_cm2: np.ndarray
) -> dict[str, np.ndarray]:
    mass = np.asarray(cell_mass_g_cm2, dtype=np.float64)
    total = float(np.sum(mass))
    return {
        "bolometric_flux": fields["bolometric_flux"],
        "radiation_energy_density": np.array(
            [np.sum(fields["radiation_energy_density"] * mass) / total]
        ),
        # 中文：比辐射加热按柱质量积分，得到单面柱的净能量交换率。
        "radiative_heating": np.array(
            [np.sum(fields["radiative_heating"] * mass)]
        ),
        "photoionization": np.sum(
            fields["photoionization"] * mass[:, None], axis=0
        )
        / total,
        "recombination": np.sum(
            fields["recombination"] * mass[:, None], axis=0
        )
        / total,
    }


def _comparison_metric_rows(
    axis: str,
    candidate_label: str,
    reference_label: str,
    orbital_phase: float,
    candidate: dict[str, np.ndarray],
    reference: dict[str, np.ndarray],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name in ("bolometric_flux", "radiation_energy_density", "radiative_heating"):
        error = scale_normalized_maximum_error(candidate[name], reference[name])
        rows.append(
            {
                "axis": axis,
                "candidate": candidate_label,
                "reference": reference_label,
                "orbital_phase": orbital_phase,
                "metric": name,
                "error": error,
                "target": PRODUCTION_TOLERANCE,
                "passed": error < PRODUCTION_TOLERANCE,
            }
        )
    for field, prefix in (
        ("photoionization", "photoionization"),
        ("recombination", "recombination"),
    ):
        for species, label in enumerate(SPECIES_LABELS):
            error = scale_normalized_maximum_error(
                candidate[field][..., species], reference[field][..., species]
            )
            rows.append(
                {
                    "axis": axis,
                    "candidate": candidate_label,
                    "reference": reference_label,
                    "orbital_phase": orbital_phase,
                    "metric": f"{prefix}_{label.replace(' ', '_')}",
                    "error": error,
                    "target": PRODUCTION_TOLERANCE,
                    "passed": error < PRODUCTION_TOLERANCE,
                }
            )
    return rows


def _nearest_phase_index(phase: np.ndarray, target: float) -> int:
    distance = np.abs(phase - target)
    distance = np.minimum(distance, 1.0 - distance)
    return int(np.argmin(distance))


def _solve_selected_phase(
    dynamic: dict[str, np.ndarray],
    phase_index: int,
    *,
    frequency_base_points: int,
    angular_order: int,
) -> dict[str, np.ndarray]:
    result = solve_frozen_nonlocal_transfer_phase(
        _frequency(frequency_base_points),
        dynamic["cell_mass_g_cm2"],
        dynamic["density_g_cm3"][phase_index],
        dynamic["temperature_k"][phase_index],
        dynamic["hydrogen_fraction"][phase_index],
        dynamic["helium_fraction"][phase_index],
        angular_order=angular_order,
    )
    return _phase_transfer_fields(result, dynamic["density_g_cm3"][phase_index])


def _full_orbit_time_rows(
    coarse: dict[str, np.ndarray], reference: dict[str, np.ndarray]
) -> list[dict[str, object]]:
    frequency = reference["frequency_hz"]
    coarse_fields = {
        "bolometric_flux": coarse["top_outward_bolometric_flux_erg_s_cm2"],
        "radiation_energy_density": 4.0
        * np.pi
        / LIGHT_SPEED_CM_S
        * np.trapezoid(coarse["mean_intensity_cgs"], frequency, axis=1),
        "radiative_heating": coarse["radiative_heating_erg_s_g"],
        "photoionization": coarse["nonlocal_photoionization_s1"],
        "recombination": coarse["nonlocal_total_recombination_cm3_s"],
    }
    reference_fields = {
        "bolometric_flux": reference[
            "top_outward_bolometric_flux_erg_s_cm2"
        ],
        "radiation_energy_density": 4.0
        * np.pi
        / LIGHT_SPEED_CM_S
        * np.trapezoid(reference["mean_intensity_cgs"], frequency, axis=1),
        "radiative_heating": reference["radiative_heating_erg_s_g"],
        "photoionization": reference["nonlocal_photoionization_s1"],
        "recombination": reference["nonlocal_total_recombination_cm3_s"],
    }
    aligned = {
        name: periodic_interpolate(
            coarse["orbital_phase"], value, reference["orbital_phase"]
        )
        for name, value in coarse_fields.items()
    }
    return _comparison_metric_rows(
        "time",
        "1024 phases",
        "2048 phases",
        -1.0,
        aligned,
        reference_fields,
    )


def run_convergence(output_dir: Path, *, force: bool) -> None:
    csv_path = output_dir / "phase7b4p_convergence.csv"
    report_path = output_dir / "phase7b4p_convergence.json"
    if not force and csv_path.exists() and report_path.exists():
        print(f"reusing {report_path.name}", flush=True)
        return
    coarse = _load_npz_arrays(
        output_dir / "phase7b4p_depth64_phase1024_frozen_nonlocal.npz"
    )
    reference = _load_npz_arrays(
        output_dir / "phase7b4p_depth64_phase2048_frozen_nonlocal.npz"
    )
    dynamic64 = _load_npz_arrays(output_dir / "phase7b4o_depth64_phase2048.npz")
    dynamic62 = _load_npz_arrays(output_dir / "phase7b4n_depth62_phase1024.npz")
    dynamic64_1024 = _load_npz_arrays(
        output_dir / "phase7b4n_depth64_phase1024.npz"
    )
    rows = _full_orbit_time_rows(coarse, reference)
    cache: dict[tuple[str, int, int, int], dict[str, np.ndarray]] = {}

    def solve_cached(
        label: str,
        dynamic: dict[str, np.ndarray],
        index: int,
        base: int,
        order: int,
    ) -> dict[str, np.ndarray]:
        key = (label, index, base, order)
        if key not in cache:
            cache[key] = _solve_selected_phase(
                dynamic,
                index,
                frequency_base_points=base,
                angular_order=order,
            )
        return cache[key]

    for target in REPRESENTATIVE_PHASES:
        index64 = _nearest_phase_index(dynamic64["orbital_phase"], float(target))
        actual = float(dynamic64["orbital_phase"][index64])
        angular_reference = solve_cached("N64-2048", dynamic64, index64, 65, 12)
        for order in ANGULAR_ORDERS[:-1]:
            candidate = solve_cached("N64-2048", dynamic64, index64, 65, order)
            rows.extend(
                _comparison_metric_rows(
                    "angle",
                    f"order {order}",
                    "order 12",
                    actual,
                    candidate,
                    angular_reference,
                )
            )

        frequency_reference = solve_cached("N64-2048", dynamic64, index64, 129, 4)
        for base in FREQUENCY_BASE_REFINEMENT[:-1]:
            candidate = solve_cached("N64-2048", dynamic64, index64, base, 4)
            rows.extend(
                _comparison_metric_rows(
                    "frequency",
                    f"base {base} ({_frequency(base).size} actual)",
                    f"base 129 ({_frequency(129).size} actual)",
                    actual,
                    candidate,
                    frequency_reference,
                )
            )

        index62 = _nearest_phase_index(dynamic62["orbital_phase"], float(target))
        index64_1024 = _nearest_phase_index(
            dynamic64_1024["orbital_phase"], float(target)
        )
        depth62 = _mass_reduce_fields(
            solve_cached("N62-1024", dynamic62, index62, 65, 4),
            dynamic62["cell_mass_g_cm2"],
        )
        depth64 = _mass_reduce_fields(
            solve_cached("N64-1024", dynamic64_1024, index64_1024, 65, 4),
            dynamic64_1024["cell_mass_g_cm2"],
        )
        rows.extend(
            _comparison_metric_rows(
                "depth",
                "62 cells",
                "64 cells",
                float(dynamic64_1024["orbital_phase"][index64_1024]),
                depth62,
                depth64,
            )
        )
        print(
            json.dumps(
                {
                    "convergence_phase_target": float(target),
                    "completed_transfer_solves": len(cache),
                }
            ),
            flush=True,
        )
    _write_csv(csv_path, rows)
    summaries: list[dict[str, object]] = []
    comparisons = sorted(
        {(str(row["axis"]), str(row["candidate"]), str(row["reference"])) for row in rows}
    )
    for axis, candidate, reference_label in comparisons:
        selected = [
            row
            for row in rows
            if row["axis"] == axis
            and row["candidate"] == candidate
            and row["reference"] == reference_label
        ]
        maximum = max(float(row["error"]) for row in selected)
        summaries.append(
            {
                "axis": axis,
                "candidate": candidate,
                "reference": reference_label,
                "maximum_error": maximum,
                "target": PRODUCTION_TOLERANCE,
                "passed": maximum < PRODUCTION_TOLERANCE,
            }
        )
    report = {
        "phase": "7B4p-convergence",
        "classification": "[V] frozen nonlocal numerical convergence",
        "configuration": {
            "representative_orbital_phases": REPRESENTATIVE_PHASES.tolist(),
            "angular_orders": list(ANGULAR_ORDERS),
            "frequency_base_points": list(FREQUENCY_BASE_REFINEMENT),
            "frequency_actual_points": [
                int(_frequency(base).size) for base in FREQUENCY_BASE_REFINEMENT
            ],
            "depth_comparison": [62, 64],
            "production_tolerance": PRODUCTION_TOLERANCE,
        },
        "summary": summaries,
        "decision": {
            "time_1024_vs_2048_passed": all(
                bool(row["passed"])
                for row in summaries
                if row["axis"] == "time"
            ),
            "production_angle4_vs_angle12_passed": all(
                bool(row["passed"])
                for row in summaries
                if row["axis"] == "angle" and row["candidate"] == "order 4"
            ),
            "production_frequency65_vs_frequency129_passed": all(
                bool(row["passed"])
                for row in summaries
                if row["axis"] == "frequency"
                and row["candidate"].startswith("base 65")
            ),
            "selected_phase_depth62_vs_depth64_passed": all(
                bool(row["passed"])
                for row in summaries
                if row["axis"] == "depth"
            ),
        },
    }
    _write_json_atomic(report_path, report)
    print(json.dumps(report["decision"], indent=2), flush=True)


def run_extended_convergence(output_dir: Path, *, force: bool) -> None:
    """在最敏感相位延长频率与角度序列，避免把有限参考当极限。"""
    csv_path = output_dir / "phase7b4p_extended_convergence.csv"
    report_path = output_dir / "phase7b4p_extended_convergence.json"
    if not force and csv_path.exists() and report_path.exists():
        print(f"reusing {report_path.name}", flush=True)
        return
    dynamic = _load_npz_arrays(output_dir / "phase7b4o_depth64_phase2048.npz")
    rows: list[dict[str, object]] = []

    frequency_index = _nearest_phase_index(dynamic["orbital_phase"], 0.5)
    frequency_phase = float(dynamic["orbital_phase"][frequency_index])
    frequency_bases = (65, 129, 257, 513)
    frequency_fields = {
        base: _solve_selected_phase(
            dynamic,
            frequency_index,
            frequency_base_points=base,
            angular_order=12,
        )
        for base in frequency_bases
    }
    for candidate_base, reference_base in zip(
        frequency_bases[:-1], frequency_bases[1:], strict=True
    ):
        rows.extend(
            _comparison_metric_rows(
                "extended_frequency",
                f"base {candidate_base} ({_frequency(candidate_base).size} actual)",
                f"base {reference_base} ({_frequency(reference_base).size} actual)",
                frequency_phase,
                frequency_fields[candidate_base],
                frequency_fields[reference_base],
            )
        )
        print(
            json.dumps(
                {
                    "extended_frequency_completed": [
                        candidate_base,
                        reference_base,
                    ]
                }
            ),
            flush=True,
        )

    angular_index = _nearest_phase_index(dynamic["orbital_phase"], 0.0)
    angular_phase = float(dynamic["orbital_phase"][angular_index])
    angular_orders = (4, 8, 12, 16, 24)
    angular_fields = {
        order: _solve_selected_phase(
            dynamic,
            angular_index,
            frequency_base_points=65,
            angular_order=order,
        )
        for order in angular_orders
    }
    for candidate_order, reference_order in zip(
        angular_orders[:-1], angular_orders[1:], strict=True
    ):
        rows.extend(
            _comparison_metric_rows(
                "extended_angle",
                f"order {candidate_order}",
                f"order {reference_order}",
                angular_phase,
                angular_fields[candidate_order],
                angular_fields[reference_order],
            )
        )
    _write_csv(csv_path, rows)
    summaries: list[dict[str, object]] = []
    comparisons = []
    for row in rows:
        key = (str(row["axis"]), str(row["candidate"]), str(row["reference"]))
        if key not in comparisons:
            comparisons.append(key)
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
                "target": PRODUCTION_TOLERANCE,
                "passed": bool(worst["passed"]),
            }
        )
    final_frequency = next(
        row
        for row in summaries
        if row["axis"] == "extended_frequency"
        and row["candidate"].startswith("base 257")
    )
    final_angle = next(
        row
        for row in summaries
        if row["axis"] == "extended_angle"
        and row["candidate"] == "order 16"
    )
    report = {
        "phase": "7B4p-extended-convergence",
        "classification": "[V/O] extended finite refinement audit",
        "configuration": {
            "frequency_phase": frequency_phase,
            "frequency_base_points": list(frequency_bases),
            "frequency_actual_points": [
                int(_frequency(base).size) for base in frequency_bases
            ],
            "frequency_angular_order": 12,
            "angular_phase": angular_phase,
            "angular_orders": list(angular_orders),
            "angular_frequency_base_points": 65,
        },
        "summary": summaries,
        "decision": {
            "frequency_257_vs_513_passed": bool(final_frequency["passed"]),
            "angle16_vs_angle24_passed": bool(final_angle["passed"]),
            "frequency_quadrature_redesign_required": not bool(
                final_frequency["passed"]
            ),
        },
    }
    _write_json_atomic(report_path, report)
    print(json.dumps(report["decision"], indent=2), flush=True)


def _local_closure_row(
    metric: str,
    nonlocal_values: np.ndarray,
    local_values: np.ndarray,
    cell_mass_g_cm2: np.ndarray,
) -> dict[str, object]:
    nonlocal_array = np.asarray(nonlocal_values, dtype=np.float64)
    local_array = np.asarray(local_values, dtype=np.float64)
    if (
        nonlocal_array.shape != local_array.shape
        or nonlocal_array.ndim != 2
        or np.any(nonlocal_array < 0.0)
        or np.any(local_array <= 0.0)
    ):
        raise ValueError("local-closure comparison requires positive phase-depth fields")
    ratio = nonlocal_array / local_array
    mass = np.asarray(cell_mass_g_cm2, dtype=np.float64)
    nonlocal_mass = np.sum(nonlocal_array * mass[None, :], axis=1)
    local_mass = np.sum(local_array * mass[None, :], axis=1)
    mass_ratio = nonlocal_mass / local_mass
    return {
        "metric": metric,
        "global_scale_normalized_maximum_error": scale_normalized_maximum_error(
            nonlocal_array, local_array
        ),
        "maximum_pointwise_relative_error": float(np.max(np.abs(ratio - 1.0))),
        "minimum_pointwise_nonlocal_over_local": float(np.min(ratio)),
        "maximum_pointwise_nonlocal_over_local": float(np.max(ratio)),
        "minimum_mass_weighted_nonlocal_over_local": float(np.min(mass_ratio)),
        "maximum_mass_weighted_nonlocal_over_local": float(np.max(mass_ratio)),
    }


def _plot_orbit_audit(
    path: Path,
    phase: np.ndarray,
    frozen_flux: np.ndarray,
    dynamic_flux: np.ndarray,
    target_flux: np.ndarray,
    diffusion_ratio: np.ndarray,
    energy_mass_ratio: np.ndarray,
    maximum_heating_ratio: np.ndarray,
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.2, 8.5), constrained_layout=True)
    axes[0, 0].plot(phase, frozen_flux / target_flux, label="Frozen non-local")
    axes[0, 0].plot(
        phase, dynamic_flux / target_flux, linestyle="--", label="Dynamic diffusion"
    )
    axes[0, 0].axhline(1.0, color="black", linestyle=":")
    axes[0, 0].set(
        xlabel="Orbital time phase",
        ylabel="Emergent / instantaneous ZO flux",
        title="(a) Frozen transfer is not the dynamic closure",
    )
    axes[0, 0].legend(fontsize=8)

    axes[0, 1].plot(phase, diffusion_ratio, color="C3")
    for value, label in ((0.03, "0.03"), (0.1, "0.1"), (0.3, "0.3")):
        axes[0, 1].axhline(value, color="black", linestyle=":", linewidth=0.8)
        axes[0, 1].text(0.01, value * 1.05, label, fontsize=7)
    axes[0, 1].set_yscale("log")
    axes[0, 1].set(
        xlabel="Orbital time phase",
        ylabel="Diffusion time / orbital period",
        title="(b) Radiation-storage timescale audit",
    )

    axes[1, 0].plot(phase, energy_mass_ratio, color="C2")
    axes[1, 0].axhline(1.0, color="black", linestyle=":")
    axes[1, 0].set(
        xlabel="Orbital time phase",
        ylabel="Mass-weighted non-local / local energy",
        title="(c) Breakdown of the local Jnu = Bnu closure",
    )

    axes[1, 1].semilogy(phase, maximum_heating_ratio, color="C4")
    axes[1, 1].axhline(1.0, color="black", linestyle=":")
    axes[1, 1].set(
        xlabel="Orbital time phase",
        ylabel="max |radiative heating| / mechanical heating",
        title="(d) Frozen-state radiative imbalance",
    )
    figure.suptitle(
        "Phase 7B4p: full-orbit frozen non-local transfer audit", fontsize=14
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_spectral_audit(
    path: Path,
    phase: np.ndarray,
    frequency_hz: np.ndarray,
    outward_flux_nu: np.ndarray,
    bolometric_flux: np.ndarray,
    extinction_depth: np.ndarray,
    absorption_depth: np.ndarray,
    photo_mass_ratio: np.ndarray,
) -> None:
    energy_ev = frequency_hz * PLANCK_ERG_S / EV_ERG
    shape_density = (
        frequency_hz[None, :] * outward_flux_nu / bolometric_flux[:, None]
    )
    figure, axes = plt.subplots(2, 2, figsize=(12.2, 8.5), constrained_layout=True)
    image = axes[0, 0].pcolormesh(
        phase,
        energy_ev,
        shape_density.T,
        shading="auto",
    )
    axes[0, 0].set_yscale("log")
    figure.colorbar(image, ax=axes[0, 0], label="nu Fnu / bolometric flux")
    axes[0, 0].set(
        xlabel="Orbital time phase",
        ylabel="Photon energy (eV)",
        title="(a) Normalized diagnostic spectral shape",
    )

    for target in (0.0, 0.25, 0.5, 0.75, 0.99):
        index = _nearest_phase_index(phase, target)
        positive = outward_flux_nu[index] > 0.0
        axes[0, 1].loglog(
            energy_ev[positive],
            (frequency_hz * outward_flux_nu[index])[positive],
            label=f"phase {phase[index]:.3f}",
        )
    axes[0, 1].set(
        xlabel="Photon energy (eV)",
        ylabel="nu Fnu (erg s-1 cm-2)",
        title="(b) Absolute frozen emergent spectra",
    )
    axes[0, 1].legend(fontsize=7)

    optical_index = _nearest_phase_index(phase, 0.99)
    axes[1, 0].loglog(
        energy_ev,
        extinction_depth[optical_index],
        label="Total extinction",
    )
    axes[1, 0].loglog(
        energy_ev,
        absorption_depth[optical_index],
        linestyle="--",
        label="True absorption",
    )
    axes[1, 0].set(
        xlabel="Photon energy (eV)",
        ylabel="Full-column optical depth",
        title=f"(c) Optical depth at phase {phase[optical_index]:.3f}",
    )
    axes[1, 0].legend(fontsize=8)

    for species, label in enumerate(SPECIES_LABELS):
        axes[1, 1].plot(phase, photo_mass_ratio[:, species], label=label)
    axes[1, 1].axhline(1.0, color="black", linestyle=":")
    axes[1, 1].set(
        xlabel="Orbital time phase",
        ylabel="Mass-weighted non-local / local photo-rate",
        title="(d) Ground-state photoionization response",
    )
    axes[1, 1].legend(fontsize=8)
    figure.suptitle(
        "Phase 7B4p: exploratory frozen spectra and rate response", fontsize=14
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_convergence_audit(
    path: Path,
    convergence_rows: list[dict[str, str]],
    extended_rows: list[dict[str, str]],
) -> None:
    labels = {
        "bolometric_flux": "Flux",
        "radiation_energy_density": "Urad",
        "radiative_heating": "Qrad",
        "photoionization_H_I": "PI H I",
        "photoionization_He_I": "PI He I",
        "photoionization_He_II": "PI He II",
        "recombination_H_I": "Rec H I",
        "recombination_He_I": "Rec He I",
        "recombination_He_II": "Rec He II",
    }
    metric_order = tuple(labels)
    figure, axes = plt.subplots(2, 2, figsize=(13.0, 8.8), constrained_layout=True)

    time_rows = [row for row in convergence_rows if row["axis"] == "time"]
    axes[0, 0].bar(
        np.arange(len(metric_order)),
        [float(next(row["error"] for row in time_rows if row["metric"] == name)) for name in metric_order],
    )
    axes[0, 0].set_title("(a) Full-orbit 1024 vs 2048 phases")

    angle_comparisons = (("order 4", "order 8"), ("order 8", "order 12"), ("order 12", "order 16"), ("order 16", "order 24"))
    for candidate, reference in angle_comparisons:
        selected = [
            row
            for row in extended_rows
            if row["axis"] == "extended_angle"
            and row["candidate"] == candidate
            and row["reference"] == reference
        ]
        axes[0, 1].plot(
            np.arange(len(metric_order)),
            [float(next(row["error"] for row in selected if row["metric"] == name)) for name in metric_order],
            marker="o",
            label=f"{candidate} vs {reference}",
        )
    axes[0, 1].set_title("(b) Angular quadrature at worst phase")
    axes[0, 1].legend(fontsize=6)

    frequency_comparisons = (
        ("base 65 (71 actual)", "base 129 (135 actual)"),
        ("base 129 (135 actual)", "base 257 (263 actual)"),
        ("base 257 (263 actual)", "base 513 (519 actual)"),
    )
    for candidate, reference in frequency_comparisons:
        selected = [
            row
            for row in extended_rows
            if row["axis"] == "extended_frequency"
            and row["candidate"] == candidate
            and row["reference"] == reference
        ]
        axes[1, 0].plot(
            np.arange(len(metric_order)),
            [float(next(row["error"] for row in selected if row["metric"] == name)) for name in metric_order],
            marker="o",
            label=f"{candidate.split()[1]} vs {reference.split()[1]}",
        )
    axes[1, 0].set_title("(c) Extended frequency refinement at phase 0.5")
    axes[1, 0].legend(fontsize=7)

    depth_rows = [row for row in convergence_rows if row["axis"] == "depth"]
    axes[1, 1].bar(
        np.arange(len(metric_order)),
        [
            max(
                float(row["error"])
                for row in depth_rows
                if row["metric"] == name
            )
            for name in metric_order
        ],
    )
    axes[1, 1].set_title("(d) Maximum selected-phase 62 vs 64-cell error")

    for axis in axes.flat:
        axis.set_yscale("log")
        axis.axhline(PRODUCTION_TOLERANCE, color="black", linestyle=":")
        axis.set_ylabel("Scale-normalized maximum error")
        axis.set_xticks(np.arange(len(metric_order)), [labels[name] for name in metric_order])
        axis.tick_params(axis="x", rotation=35, labelsize=7)
    figure.suptitle(
        "Phase 7B4p: frozen non-local numerical convergence", fontsize=14
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def run_summary(output_dir: Path) -> None:
    required_reports = {
        "controls": output_dir / "phase7b4p_controls.json",
        "convergence": output_dir / "phase7b4p_convergence.json",
        "extended": output_dir / "phase7b4p_extended_convergence.json",
        "case1024": output_dir
        / "phase7b4p_depth64_phase1024_frozen_nonlocal.json",
        "case2048": output_dir
        / "phase7b4p_depth64_phase2048_frozen_nonlocal.json",
    }
    if any(not path.exists() for path in required_reports.values()):
        missing = [path.name for path in required_reports.values() if not path.exists()]
        raise FileNotFoundError(f"Phase 7B4p summary inputs are missing: {missing}")
    reports = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in required_reports.items()
    }
    frozen = _load_npz_arrays(
        output_dir / "phase7b4p_depth64_phase2048_frozen_nonlocal.npz"
    )
    dynamic = _load_npz_arrays(output_dir / "phase7b4o_depth64_phase2048.npz")
    frequency = frozen["frequency_hz"]
    phase = frozen["orbital_phase"]
    mass = frozen["cell_mass_g_cm2"]
    planck = planck_nu(
        frequency[None, :, None], dynamic["temperature_k"][:, None, :]
    )
    energy_nonlocal = 4.0 * np.pi / LIGHT_SPEED_CM_S * np.trapezoid(
        frozen["mean_intensity_cgs"], frequency, axis=1
    )
    energy_local = 4.0 * np.pi / LIGHT_SPEED_CM_S * np.trapezoid(
        planck, frequency, axis=1
    )
    closure_rows = [
        _local_closure_row("band_radiation_energy", energy_nonlocal, energy_local, mass)
    ]
    for species, label in enumerate(SPECIES_LABELS):
        closure_rows.append(
            _local_closure_row(
                f"photoionization_{label.replace(' ', '_')}",
                frozen["nonlocal_photoionization_s1"][:, :, species],
                frozen["local_photoionization_s1"][:, :, species],
                mass,
            )
        )
        closure_rows.append(
            _local_closure_row(
                f"recombination_{label.replace(' ', '_')}",
                frozen["nonlocal_total_recombination_cm3_s"][:, :, species],
                frozen["local_total_recombination_cm3_s"][:, :, species],
                mass,
            )
        )
    _write_csv(output_dir / "phase7b4p_local_closure.csv", closure_rows)

    period = float(
        dynamic["time_since_pericentre_s"][-1] + dynamic["step_duration_s"][-1]
    )
    timescale = radiation_timescale_audit(
        mass,
        dynamic["density_g_cm3"],
        dynamic["rosseland_opacity_cm2_g"],
        period,
    )
    diffusion_ratio = timescale.diffusion_time_s / period
    frozen_flux = frozen["top_outward_bolometric_flux_erg_s_cm2"]
    target_flux = dynamic["target_surface_flux_erg_s_cm2"]
    dynamic_flux = dynamic["outward_flux_edges_erg_s_cm2"][:, 0]
    mass_energy_ratio = np.sum(energy_nonlocal * mass[None, :], axis=1) / np.sum(
        energy_local * mass[None, :], axis=1
    )
    mechanical_heating = target_flux / np.sum(mass)
    maximum_heating_ratio = np.max(
        np.abs(
            frozen["radiative_heating_erg_s_g"]
            / mechanical_heating[:, None]
        ),
        axis=1,
    )
    photo_nonlocal_mass = np.sum(
        frozen["nonlocal_photoionization_s1"] * mass[None, :, None], axis=1
    )
    photo_local_mass = np.sum(
        frozen["local_photoionization_s1"] * mass[None, :, None], axis=1
    )
    photo_mass_ratio = photo_nonlocal_mass / photo_local_mass
    phase_rows = [
        {
            "phase_index": index,
            "orbital_phase": float(phase[index]),
            "frozen_flux_erg_s_cm2": float(frozen_flux[index]),
            "dynamic_diffusion_flux_erg_s_cm2": float(dynamic_flux[index]),
            "instantaneous_target_flux_erg_s_cm2": float(target_flux[index]),
            "frozen_over_target": float(frozen_flux[index] / target_flux[index]),
            "dynamic_over_target": float(dynamic_flux[index] / target_flux[index]),
            "diffusion_time_over_orbit": float(diffusion_ratio[index]),
            "mass_weighted_nonlocal_over_local_radiation_energy": float(
                mass_energy_ratio[index]
            ),
            "maximum_abs_radiative_over_mechanical_heating": float(
                maximum_heating_ratio[index]
            ),
        }
        for index in range(phase.size)
    ]
    _write_csv(output_dir / "phase7b4p_reference_phase.csv", phase_rows)

    convergence_rows = _read_csv_rows(output_dir / "phase7b4p_convergence.csv")
    extended_rows = _read_csv_rows(
        output_dir / "phase7b4p_extended_convergence.csv"
    )
    _plot_orbit_audit(
        output_dir / "phase7b4p_frozen_nonlocal_orbit.png",
        phase,
        frozen_flux,
        dynamic_flux,
        target_flux,
        diffusion_ratio,
        mass_energy_ratio,
        maximum_heating_ratio,
    )
    _plot_spectral_audit(
        output_dir / "phase7b4p_nonlocal_spectra.png",
        phase,
        frequency,
        frozen["top_outward_flux_nu_cgs"],
        frozen_flux,
        frozen["extinction_optical_depth_full"],
        frozen["true_absorption_optical_depth_full"],
        photo_mass_ratio,
    )
    _plot_convergence_audit(
        output_dir / "phase7b4p_convergence.png",
        convergence_rows,
        extended_rows,
    )

    convergence_decision = reports["convergence"]["decision"]
    extended_decision = reports["extended"]["decision"]
    controls_passed = bool(reports["controls"]["decision"]["all_controls_passed"])
    formal_orbits_passed = bool(
        reports["case1024"]["decision"]["all_phase_transfer_controls_passed"]
        and reports["case2048"]["decision"]["all_phase_transfer_controls_passed"]
    )
    quasistatic_passed = bool(
        reports["case2048"]["decision"]["quasistatic_radiation_gate_passed"]
    )
    numerical_passed = bool(
        controls_passed
        and formal_orbits_passed
        and convergence_decision["time_1024_vs_2048_passed"]
        and convergence_decision["production_angle4_vs_angle12_passed"]
        and convergence_decision[
            "production_frequency65_vs_frequency129_passed"
        ]
        and convergence_decision["selected_phase_depth62_vs_depth64_passed"]
        and extended_decision["frequency_257_vs_513_passed"]
    )
    report = {
        "phase": "7B4p-complete",
        "classification": "[A/V/O] frozen-state nonlocal transfer audit",
        "provenance": {
            "dynamic_reference": "phase7b4o_depth64_phase2048.npz",
            "frozen_orbit_cases": [
                required_reports["case1024"].name,
                required_reports["case2048"].name,
            ],
            "control_report": required_reports["controls"].name,
            "convergence_report": required_reports["convergence"].name,
            "extended_convergence_report": required_reports["extended"].name,
        },
        "configuration": {
            "production_depth_points": 64,
            "production_phase_points": 2048,
            "production_frequency_points": int(frequency.size),
            "production_angular_order": int(frozen["angular_order"]),
            "energy_range_ev": list(ENERGY_RANGE_EV),
            "production_tolerance": PRODUCTION_TOLERANCE,
            "quasistatic_diffusion_to_orbit_target": (
                QUASISTATIC_DIFFUSION_TO_ORBIT_TARGET
            ),
        },
        "formal_transfer": reports["case2048"]["transfer_diagnostics"],
        "radiation_timescale": reports["case2048"]["radiation_timescale"],
        "full_orbit_flux_audit": {
            "minimum_frozen_over_target": float(np.min(frozen_flux / target_flux)),
            "maximum_frozen_over_target": float(np.max(frozen_flux / target_flux)),
            "minimum_dynamic_over_target": float(np.min(dynamic_flux / target_flux)),
            "maximum_dynamic_over_target": float(np.max(dynamic_flux / target_flux)),
            "maximum_abs_radiative_over_mechanical_heating": float(
                np.max(maximum_heating_ratio)
            ),
        },
        "local_planck_closure": closure_rows,
        "convergence": {
            "finite_selected_phase_summary": reports["convergence"]["summary"],
            "extended_summary": reports["extended"]["summary"],
        },
        "decision": {
            "analytic_and_thermodynamic_controls_passed": controls_passed,
            "full_orbit_formal_transfer_controls_passed": formal_orbits_passed,
            "time_1024_vs_2048_passed": bool(
                convergence_decision["time_1024_vs_2048_passed"]
            ),
            "production_angle_quadrature_passed": bool(
                convergence_decision["production_angle4_vs_angle12_passed"]
            ),
            "extended_angle16_vs_angle24_passed": bool(
                extended_decision["angle16_vs_angle24_passed"]
            ),
            "production_frequency_quadrature_passed": bool(
                convergence_decision[
                    "production_frequency65_vs_frequency129_passed"
                ]
            ),
            "extended_frequency257_vs_frequency513_passed": bool(
                extended_decision["frequency_257_vs_513_passed"]
            ),
            "selected_phase_depth62_vs_depth64_passed": bool(
                convergence_decision["selected_phase_depth62_vs_depth64_passed"]
            ),
            "all_frozen_transfer_numerical_gates_passed": numerical_passed,
            "quasistatic_radiation_gate_passed": quasistatic_passed,
            "frozen_nonlocal_diagnostic_completed": True,
            "phase_by_phase_stationary_nonlocal_closure_authorized": bool(
                numerical_passed and quasistatic_passed
            ),
            "time_dependent_nonlocal_radiation_storage_physically_required": (
                not quasistatic_passed
            ),
            "time_dependent_nonlocal_solver_numerically_authorized": numerical_passed,
            "phase4_atmosphere_replacement_authorized": False,
            "uvot_authorized": False,
            "next_microphase": (
                "redesign threshold-aware frequency quadrature and extend the "
                "independent depth reference before adding time-dependent "
                "nonlocal radiation storage"
            ),
        },
        "boundaries": {
            "frozen_material_states_only": True,
            "radiation_storage_omitted": True,
            "ground_state_h_he_only": True,
            "excited_levels_and_line_blanketing_omitted": True,
            "observer_spectrum_generated": False,
            "exploratory_71_point_spectra_are_not_converged_products": True,
        },
        "forbidden_repairs": {
            "nan_to_num": False,
            "arbitrary_clip": False,
            "arbitrary_floor": False,
            "failed_phase_deletion": False,
            "post_hoc_physical_renormalization": False,
        },
    }
    _write_json_atomic(output_dir / "phase7b4p_complete_report.json", report)
    print(json.dumps(report["decision"], indent=2), flush=True)


def main() -> None:
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--stage",
        choices=(
            "case",
            "controls",
            "convergence",
            "extended",
            "summary",
            "all",
        ),
        default="all",
    )
    parser.add_argument("--case", choices=tuple(ALL_CASES))
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    if arguments.workers < 1:
        parser.error("--workers must be positive")
    if arguments.stage == "case" and arguments.case is None:
        parser.error("--stage case requires --case")
    if arguments.stage != "case" and arguments.case is not None:
        parser.error("--case is only valid with --stage case")
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if arguments.stage in ("case", "all"):
        cases = (
            (ALL_CASES[arguments.case],)
            if arguments.stage == "case"
            else TIME_CASES
        )
        for spec in cases:
            run_orbit_case(
                arguments.output_dir,
                spec,
                workers=arguments.workers,
                force=arguments.force,
            )
    if arguments.stage in ("controls", "all"):
        run_controls(arguments.output_dir, force=arguments.force)
    if arguments.stage in ("convergence", "all"):
        run_convergence(arguments.output_dir, force=arguments.force)
    if arguments.stage in ("extended", "all"):
        run_extended_convergence(arguments.output_dir, force=arguments.force)
    if arguments.stage in ("summary", "all"):
        run_summary(arguments.output_dir)


if __name__ == "__main__":
    main()
