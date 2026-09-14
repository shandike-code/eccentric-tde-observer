"""Phase 7B4s：隐式 ALE 辐射储能核、解析门和 N128 轨道 pilot。"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.continuum_emission import ground_state_milne_continuum
from eccentric_tde_observer.dynamic_column import build_zo_periodic_column_background
from eccentric_tde_observer.implicit_radiative_transfer_1d import (
    solve_implicit_ale_slab_step,
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
from eccentric_tde_observer.reference_case import (
    build_strict_domain_reference_model,
)
from eccentric_tde_observer.vertical import (
    RADIATION_PRESSURE_POLYTROPE_PROFILE,
)


RADIAL_POINTS = 65
RADIAL_INDEX = 8
PILOT_ENERGY_EV = np.array([10.0, 60.0])
PILOT_ANGULAR_ORDER = 4
PILOT_MAXIMUM_CYCLES = 4
PILOT_CYCLE_TOLERANCE = 2.0e-7
CONTROL_TOLERANCE = 2.0e-11
PILOT_ENERGY_LEDGER_TOLERANCE = 2.0e-8
PILOT_LINEAR_TOLERANCE = 2.0e-11
VELOCITY_NEGLECT_TOLERANCE = 1.0e-3
FORMAL_TRANSFER_SUBCELLS_PER_MATERIAL_CELL = 16


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


def _save_npz_atomic(path: Path, **arrays: np.ndarray) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, **arrays)
    os.replace(temporary, path)


def _load_material_reference(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as data:
        arrays = {name: np.array(data[name], copy=True) for name in data.files}
    expected = (2048, 128)
    if arrays["density_g_cm3"].shape != expected:
        raise ValueError("Phase 7B4s requires the N128x2048 material reference")
    if arrays["temperature_k"].shape != expected:
        raise ValueError("material temperature shape changed")
    if arrays["hydrogen_fraction"].shape != (*expected, 2):
        raise ValueError("material hydrogen shape changed")
    if arrays["helium_fraction"].shape != (*expected, 3):
        raise ValueError("material helium shape changed")
    numerical = tuple(
        value for value in arrays.values() if np.issubdtype(value.dtype, np.number)
    )
    if not all(np.all(np.isfinite(value)) for value in numerical):
        raise ValueError("material reference contains non-finite values")
    if np.any(arrays["density_g_cm3"] <= 0.0) or np.any(
        arrays["temperature_k"] <= 0.0
    ):
        raise ValueError("material reference left its positive physical domain")
    return arrays


def centred_full_column_trajectory(
    material: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """把表面到中面的 N128 拉格朗日柱镜像到中心固定的完整柱。"""
    cell_mass = material["cell_mass_g_cm2"]
    density = material["density_g_cm3"]
    half_width = cell_mass[None, :] / density
    full_width = np.concatenate((half_width, half_width[:, ::-1]), axis=1)
    half_thickness = np.sum(half_width, axis=1)
    edges = np.concatenate(
        (
            -half_thickness[:, None],
            -half_thickness[:, None] + np.cumsum(full_width, axis=1),
        ),
        axis=1,
    )
    midplane = edges[:, density.shape[1]]
    scale = np.max(half_thickness)
    if np.max(np.abs(midplane)) / scale > 2.0e-15:
        raise ArithmeticError("centred full column lost its midplane")

    def mirror(values: np.ndarray) -> np.ndarray:
        return np.concatenate((values, values[:, ::-1]), axis=1)

    return {
        "edges_cm": edges,
        "cell_width_cm": full_width,
        "half_thickness_cm": half_thickness,
        "density_g_cm3": mirror(density),
        "temperature_k": mirror(material["temperature_k"]),
        "hydrogen_fraction": np.concatenate(
            (
                material["hydrogen_fraction"],
                material["hydrogen_fraction"][:, ::-1],
            ),
            axis=1,
        ),
        "helium_fraction": np.concatenate(
            (
                material["helium_fraction"],
                material["helium_fraction"][:, ::-1],
            ),
            axis=1,
        ),
    }


def _periodic_advection_error(depth_points: int) -> float:
    mu, weight = gauss_legendre_half_range_mu_weights(4)
    edges = np.linspace(0.0, 1.0, depth_points + 1)
    centre = 0.5 * (edges[:-1] + edges[1:])
    initial = 1.0 + 0.2 * np.sin(2.0 * np.pi * centre)[None, None, :]
    duration = 0.4 / depth_points
    result = solve_implicit_ale_slab_step(
        [1.0],
        edges,
        edges,
        mu,
        weight,
        initial,
        0.0,
        0.0,
        1.0,
        duration,
        periodic_spatial_boundary=True,
        propagation_speed_cm_s=1.0,
    )
    exact = 1.0 + 0.2 * np.sin(
        2.0 * np.pi * (centre[None, :] - mu[:, None] * duration)
    )
    return float(np.max(np.abs(result.final_intensity[0] - exact)))


def _static_absorption_error(depth_points: int) -> float:
    mu, weight = gauss_legendre_half_range_mu_weights(8)
    edges = np.linspace(0.0, 1.0, depth_points + 1)
    extinction = np.full((1, depth_points), 2.0)
    thermal = np.full_like(extinction, 4.0)
    epsilon = np.ones_like(extinction)
    implicit = solve_implicit_ale_slab_step(
        [1.0],
        edges,
        edges,
        mu,
        weight,
        0.0,
        extinction,
        thermal,
        epsilon,
        1.0e7,
        propagation_speed_cm_s=1.0,
    )
    formal = solve_static_slab_transfer(
        [1.0], edges, mu, weight, extinction, thermal, epsilon
    )
    return float(np.max(np.abs(implicit.mean_intensity - formal.mean_intensity)))


def analytic_control_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    mu4, weight4 = gauss_legendre_half_range_mu_weights(4)
    edges = np.linspace(0.0, 2.0e12, 33)
    initial = 2.0
    thermal = 5.0
    extinction = 1.0e-10
    duration = 1.0e3
    speed = 2.5e10
    absorption = solve_implicit_ale_slab_step(
        [1.0e15],
        edges,
        edges,
        mu4,
        weight4,
        initial,
        extinction,
        thermal,
        1.0,
        duration,
        periodic_spatial_boundary=True,
        propagation_speed_cm_s=speed,
    )
    exact = (initial + speed * extinction * duration * thermal) / (
        1.0 + speed * extinction * duration
    )
    rows.append(
        {
            "control": "uniform absorption backward Euler",
            "resolution": 32,
            "error": float(np.max(np.abs(absorption.final_intensity - exact))),
            "target": CONTROL_TOLERANCE,
            "passed": bool(
                np.max(np.abs(absorption.final_intensity - exact))
                < CONTROL_TOLERANCE
            ),
        }
    )

    old_edges = np.linspace(-1.0, 1.0, 17)
    new_edges = np.linspace(-1.12, 1.12, 17)
    uniform = 3.0
    moving = solve_implicit_ale_slab_step(
        [1.0],
        old_edges,
        new_edges,
        mu4,
        weight4,
        uniform,
        0.0,
        0.0,
        1.0,
        1.0,
        left_exterior_intensity=uniform,
        right_exterior_intensity=uniform,
        propagation_speed_cm_s=2.0,
    )
    gcl_error = float(np.max(np.abs(moving.final_intensity - uniform)))
    rows.append(
        {
            "control": "moving-grid geometric conservation",
            "resolution": 16,
            "error": gcl_error,
            "target": CONTROL_TOLERANCE,
            "passed": bool(gcl_error < CONTROL_TOLERANCE),
        }
    )

    mu8, weight8 = gauss_legendre_half_range_mu_weights(8)
    scatter_edges = np.linspace(0.0, 1.0e12, 49)
    centre = 0.5 * (scatter_edges[:-1] + scatter_edges[1:])
    scatter_initial = (
        2.0
        + 0.2 * mu8[None, :, None]
        + 0.1
        * np.sin(2.0 * np.pi * centre / scatter_edges[-1])[None, None, :]
    )
    scattering = solve_implicit_ale_slab_step(
        [1.0e15],
        scatter_edges,
        scatter_edges,
        mu8,
        weight8,
        scatter_initial,
        3.0e-12,
        0.0,
        0.0,
        2.0e3,
        periodic_spatial_boundary=True,
    )
    scattering_error = float(
        np.max(scattering.relative_energy_ledger_residual)
    )
    rows.append(
        {
            "control": "pure-scattering radiation conservation",
            "resolution": 48,
            "error": scattering_error,
            "target": CONTROL_TOLERANCE,
            "passed": bool(scattering_error < CONTROL_TOLERANCE),
        }
    )
    for points in (32, 64, 128):
        rows.append(
            {
                "control": "periodic vacuum advection",
                "resolution": points,
                "error": _periodic_advection_error(points),
                "target": "convergence",
                "passed": True,
            }
        )
    for points in (128, 256, 512):
        rows.append(
            {
                "control": "frozen formal recovery",
                "resolution": points,
                "error": _static_absorption_error(points),
                "target": "convergence",
                "passed": True,
            }
        )
    advection = [
        float(row["error"])
        for row in rows
        if row["control"] == "periodic vacuum advection"
    ]
    frozen = [
        float(row["error"])
        for row in rows
        if row["control"] == "frozen formal recovery"
    ]
    convergence = bool(
        advection[1] < 0.55 * advection[0]
        and advection[2] < 0.55 * advection[1]
        and frozen[1] < 0.60 * frozen[0]
        and frozen[2] < 0.60 * frozen[1]
    )
    for row in rows:
        if row["target"] == "convergence":
            row["passed"] = convergence
    return rows


def mesh_audit_rows(
    material: dict[str, np.ndarray], full: dict[str, np.ndarray]
) -> tuple[list[dict[str, object]], dict[str, float]]:
    phase_points = material["orbital_phase"].size
    model = build_strict_domain_reference_model(RADIAL_POINTS, phase_points)
    background = build_zo_periodic_column_background(model, RADIAL_INDEX)
    if not np.array_equal(
        background.time_since_pericentre_s,
        material["time_since_pericentre_s"],
    ):
        raise ArithmeticError("rebuilt ZO time axis differs from N128 reference")
    edges = full["edges_cm"]
    duration = material["step_duration_s"]
    following_edges = np.roll(edges, -1, axis=0)
    discrete_velocity = (following_edges - edges) / duration[:, None]
    analytic_velocity = (
        edges * background.logarithmic_breathing_rate_s1[:, None]
    )
    maximum_speed_scale = max(
        float(np.max(np.abs(discrete_velocity))),
        float(np.max(np.abs(analytic_velocity))),
    )
    velocity_difference = float(
        np.max(np.abs(discrete_velocity - analytic_velocity))
        / maximum_speed_scale
    )
    mu16, _ = gauss_legendre_half_range_mu_weights(16)
    minimum_mu = float(np.min(np.abs(mu16)))
    maximum_mu = float(np.max(np.abs(mu16)))
    width = full["cell_width_cm"]
    relative_face_speed = LIGHT_SPEED_CM_S * maximum_mu + np.maximum(
        np.abs(discrete_velocity[:, :-1]),
        np.abs(discrete_velocity[:, 1:]),
    )
    explicit_duration = width / relative_face_speed
    minimum_explicit_duration = float(np.min(explicit_duration))
    orbital_period = float(np.sum(duration))
    explicit_steps = orbital_period / minimum_explicit_duration
    formal_explicit_duration = (
        minimum_explicit_duration / FORMAL_TRANSFER_SUBCELLS_PER_MATERIAL_CELL
    )
    formal_explicit_steps = orbital_period / formal_explicit_duration
    next_width = np.roll(width, -1, axis=0)
    maximum_width_change = np.max(np.abs(next_width / width - 1.0), axis=1)
    adjacent_width = np.empty_like(edges)
    adjacent_width[:, 0] = width[:, 0]
    adjacent_width[:, -1] = width[:, -1]
    adjacent_width[:, 1:-1] = np.minimum(width[:, :-1], width[:, 1:])
    edge_displacement_ratio = np.max(
        np.abs(following_edges - edges) / adjacent_width, axis=1
    )
    rows = []
    for index in range(phase_points):
        rows.append(
            {
                "phase_index": index,
                "orbital_phase": float(material["orbital_phase"][index]),
                "step_duration_s": float(duration[index]),
                "half_thickness_cm": float(full["half_thickness_cm"][index]),
                "analytic_surface_speed_to_c": float(
                    abs(analytic_velocity[index, 0]) / LIGHT_SPEED_CM_S
                ),
                "discrete_surface_speed_to_c": float(
                    abs(discrete_velocity[index, 0]) / LIGHT_SPEED_CM_S
                ),
                "maximum_width_change_per_step": float(
                    maximum_width_change[index]
                ),
                "maximum_edge_displacement_per_adjacent_width": float(
                    edge_displacement_ratio[index]
                ),
            }
        )
    metrics = {
        "minimum_half_thickness_cm": float(np.min(full["half_thickness_cm"])),
        "maximum_half_thickness_cm": float(np.max(full["half_thickness_cm"])),
        "maximum_analytic_mesh_speed_to_c": float(
            np.max(np.abs(analytic_velocity)) / LIGHT_SPEED_CM_S
        ),
        "maximum_discrete_mesh_speed_to_c": float(
            np.max(np.abs(discrete_velocity)) / LIGHT_SPEED_CM_S
        ),
        "maximum_discrete_to_analytic_velocity_difference": velocity_difference,
        "minimum_angle16_absolute_mu": minimum_mu,
        "maximum_mesh_to_angle16_grazing_streaming_ratio": float(
            np.max(np.abs(discrete_velocity))
            / (LIGHT_SPEED_CM_S * minimum_mu)
        ),
        "minimum_explicit_cfl_duration_s": minimum_explicit_duration,
        "explicit_cfl_steps_per_orbit": float(explicit_steps),
        "minimum_material_grid_explicit_cfl_duration_s": (
            minimum_explicit_duration
        ),
        "material_grid_explicit_cfl_steps_per_orbit": float(explicit_steps),
        "minimum_formal_subcell_explicit_cfl_duration_s": (
            formal_explicit_duration
        ),
        "formal_subcell_explicit_cfl_steps_per_orbit": float(
            formal_explicit_steps
        ),
        "minimum_actual_step_duration_s": float(np.min(duration)),
        "maximum_actual_step_duration_s": float(np.max(duration)),
        "maximum_width_change_per_step": float(np.max(maximum_width_change)),
        "maximum_edge_displacement_per_adjacent_width": float(
            np.max(edge_displacement_ratio)
        ),
        "material_cell_unknowns_per_frequency_angle16": int(256 * 16),
        "formal_subcell_unknowns_per_frequency_angle16": int(4096 * 16),
    }
    return rows, metrics


def _pilot_continuum(full: dict[str, np.ndarray]):
    frequency = PILOT_ENERGY_EV * EV_ERG / PLANCK_ERG_S
    density = full["density_g_cm3"]
    temperature = full["temperature_k"]
    hydrogen = full["hydrogen_fraction"]
    helium = full["helium_fraction"]
    shape = density.shape
    continuum = ground_state_milne_continuum(
        density.reshape(-1),
        temperature.reshape(-1),
        frequency,
        hydrogen[:, :, 0].reshape(-1),
        hydrogen[:, :, 1].reshape(-1),
        helium[:, :, 0].reshape(-1),
        helium[:, :, 1].reshape(-1),
        helium[:, :, 2].reshape(-1),
        include_electron_scattering=True,
    )
    frequency_points = frequency.size
    return (
        frequency,
        continuum.extinction_total_per_cm.reshape(frequency_points, *shape),
        continuum.thermal_source_intensity.reshape(frequency_points, *shape),
        continuum.absorption_probability.reshape(frequency_points, *shape),
    )


def run_periodic_pilot(
    material: dict[str, np.ndarray], full: dict[str, np.ndarray]
) -> tuple[dict[str, np.ndarray], list[dict[str, object]], dict[str, object]]:
    frequency, extinction, thermal_source, epsilon = _pilot_continuum(full)
    mu, weight = gauss_legendre_half_range_mu_weights(PILOT_ANGULAR_ORDER)
    phase_points, depth_points = full["density_g_cm3"].shape
    initial_planck = planck_nu(
        frequency[:, None], full["temperature_k"][0, None, :]
    )
    state = np.broadcast_to(
        initial_planck[:, None, :],
        (frequency.size, mu.size, depth_points),
    ).copy()
    mean_history = np.empty((frequency.size, phase_points, depth_points))
    left_outward = np.empty((frequency.size, phase_points))
    right_outward = np.empty_like(left_outward)
    maximum_ledger_history = np.empty(phase_points)
    cycle_rows: list[dict[str, object]] = []
    started = time.perf_counter()
    converged = False
    maximum_linear = 0.0
    maximum_energy = 0.0
    minimum_intensity = float(np.min(state))
    for cycle in range(1, PILOT_MAXIMUM_CYCLES + 1):
        cycle_start = np.array(state, copy=True)
        cycle_maximum_linear = 0.0
        cycle_maximum_energy = 0.0
        for phase in range(phase_points):
            following = (phase + 1) % phase_points
            result = solve_implicit_ale_slab_step(
                frequency,
                full["edges_cm"][phase],
                full["edges_cm"][following],
                mu,
                weight,
                state,
                extinction[:, following],
                thermal_source[:, following],
                epsilon[:, following],
                float(material["step_duration_s"][phase]),
            )
            state = np.array(result.final_intensity, copy=True)
            cycle_maximum_linear = max(
                cycle_maximum_linear,
                float(np.max(result.relative_linear_system_residual)),
            )
            cycle_maximum_energy = max(
                cycle_maximum_energy,
                float(np.max(result.relative_energy_ledger_residual)),
            )
            minimum_intensity = min(minimum_intensity, result.minimum_intensity)
            if cycle == PILOT_MAXIMUM_CYCLES or converged is False:
                mean_history[:, following] = result.mean_intensity
                maximum_ledger_history[following] = float(
                    np.max(result.relative_energy_ledger_residual)
                )
                # 中文：物理出射诊断使用实验室方向；ALE 通量只进入守恒账本。
                left_outward[:, following] = -2.0 * np.pi * np.einsum(
                    "m,fm,m->f",
                    weight[mu < 0.0],
                    state[:, mu < 0.0, 0],
                    mu[mu < 0.0],
                )
                right_outward[:, following] = 2.0 * np.pi * np.einsum(
                    "m,fm,m->f",
                    weight[mu > 0.0],
                    state[:, mu > 0.0, -1],
                    mu[mu > 0.0],
                )
        scale = max(float(np.max(np.abs(state))), float(np.max(np.abs(cycle_start))))
        cycle_residual = float(np.max(np.abs(state - cycle_start)) / scale)
        cycle_rows.append(
            {
                "cycle": cycle,
                "cycle_residual": cycle_residual,
                "maximum_linear_system_residual": cycle_maximum_linear,
                "maximum_energy_ledger_residual": cycle_maximum_energy,
                "elapsed_s": float(time.perf_counter() - started),
            }
        )
        maximum_linear = max(maximum_linear, cycle_maximum_linear)
        maximum_energy = max(maximum_energy, cycle_maximum_energy)
        if cycle_residual < PILOT_CYCLE_TOLERANCE:
            converged = True
            break
    if not converged:
        raise RuntimeError("two-frequency N128 radiation pilot did not close periodically")
    mirror_scale = np.maximum(np.abs(left_outward), np.abs(right_outward))
    mirror_difference = np.abs(left_outward - right_outward)
    mirror_relative = np.array(mirror_difference, copy=True)
    np.divide(
        mirror_difference,
        mirror_scale,
        out=mirror_relative,
        where=mirror_scale > 0.0,
    )
    mirror_residual = float(np.max(mirror_relative))
    arrays = {
        "photon_energy_ev": np.array(PILOT_ENERGY_EV, copy=True),
        "frequency_hz": frequency,
        "direction_cosine": mu,
        "angular_weight": weight,
        "orbital_phase": material["orbital_phase"],
        "mean_intensity_cgs": mean_history,
        "left_outward_flux_nu_cgs": left_outward,
        "right_outward_flux_nu_cgs": right_outward,
        "maximum_step_energy_ledger_residual": maximum_ledger_history,
        "final_phase0_intensity_cgs": state,
    }
    metrics: dict[str, object] = {
        "pilot_photon_energy_ev": PILOT_ENERGY_EV.tolist(),
        "angular_order": PILOT_ANGULAR_ORDER,
        "full_depth_points": depth_points,
        "phase_points": phase_points,
        "cycle_count": len(cycle_rows),
        "cycle_residual": float(cycle_rows[-1]["cycle_residual"]),
        "maximum_linear_system_residual": maximum_linear,
        "maximum_energy_ledger_residual": maximum_energy,
        "maximum_left_right_flux_relative_residual": mirror_residual,
        "minimum_intensity_cgs": minimum_intensity,
        "runtime_s": float(time.perf_counter() - started),
        "cycle_converged": converged,
        "energy_ledger_passed": maximum_energy < PILOT_ENERGY_LEDGER_TOLERANCE,
        "linear_system_passed": maximum_linear < PILOT_LINEAR_TOLERANCE,
    }
    return arrays, cycle_rows, metrics


def _plot_controls(
    path: Path,
    controls: list[dict[str, object]],
    cycle_rows: list[dict[str, object]],
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12.0, 8.5), constrained_layout=True)
    for axis, name, title in (
        (axes[0, 0], "periodic vacuum advection", "Vacuum advection"),
        (axes[0, 1], "frozen formal recovery", "Frozen formal recovery"),
    ):
        selected = [row for row in controls if row["control"] == name]
        axis.loglog(
            [int(row["resolution"]) for row in selected],
            [float(row["error"]) for row in selected],
            "o-",
        )
        axis.set_xlabel("Depth cells")
        axis.set_ylabel("Maximum absolute error")
        axis.set_title(title)
        axis.grid(alpha=0.25)
    finite = [
        row
        for row in controls
        if row["control"]
        in (
            "uniform absorption backward Euler",
            "moving-grid geometric conservation",
            "pure-scattering radiation conservation",
        )
    ]
    axes[1, 0].bar(
        np.arange(len(finite)),
        [float(row["error"]) for row in finite],
        color=("tab:blue", "tab:orange", "tab:green"),
    )
    axes[1, 0].set_yscale("symlog", linthresh=1.0e-16)
    axes[1, 0].set_xticks(
        np.arange(len(finite)), ("Absorption", "ALE GCL", "Scattering")
    )
    axes[1, 0].set_ylabel("Control error")
    axes[1, 0].set_title("Analytic and conservation controls")
    axes[1, 0].grid(axis="y", alpha=0.25)
    cycle_index = np.array([int(row["cycle"]) for row in cycle_rows])
    cycle_residual = np.array(
        [float(row["cycle_residual"]) for row in cycle_rows]
    )
    positive_cycle = cycle_residual > 0.0
    axes[1, 1].semilogy(
        cycle_index[positive_cycle],
        cycle_residual[positive_cycle],
        "o-",
        label="Cycle residual",
    )
    axes[1, 1].semilogy(
        cycle_index,
        [float(row["maximum_energy_ledger_residual"]) for row in cycle_rows],
        "s--",
        label="Energy ledger",
    )
    axes[1, 1].axhline(
        PILOT_CYCLE_TOLERANCE, color="black", ls=":", label="Cycle target"
    )
    axes[1, 1].set_xlabel("Radiation cycle")
    axes[1, 1].set_ylabel("Residual")
    axes[1, 1].set_title("N128 two-frequency pilot")
    if np.any(~positive_cycle):
        exact_cycles = ", ".join(str(value) for value in cycle_index[~positive_cycle])
        axes[1, 1].text(
            0.98,
            0.04,
            f"Cycle residual = 0 at cycle {exact_cycles}",
            ha="right",
            va="bottom",
            transform=axes[1, 1].transAxes,
            fontsize=8,
        )
    axes[1, 1].legend()
    axes[1, 1].grid(alpha=0.25)
    fig.suptitle("Phase 7B4s implicit ALE radiation controls")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_mesh(path: Path, rows: list[dict[str, object]], metrics: dict[str, float]) -> None:
    phase = np.array([float(row["orbital_phase"]) for row in rows])
    duration = np.array([float(row["step_duration_s"]) for row in rows])
    thickness = np.array([float(row["half_thickness_cm"]) for row in rows])
    analytic_speed = np.array(
        [float(row["analytic_surface_speed_to_c"]) for row in rows]
    )
    discrete_speed = np.array(
        [float(row["discrete_surface_speed_to_c"]) for row in rows]
    )
    displacement = np.array(
        [
            float(row["maximum_edge_displacement_per_adjacent_width"])
            for row in rows
        ]
    )
    fig, axes = plt.subplots(2, 2, figsize=(12.0, 8.5), constrained_layout=True)
    axes[0, 0].plot(phase, thickness)
    axes[0, 0].set_ylabel("Half-thickness [cm]")
    axes[0, 0].set_title("Prescribed vertical breathing")
    axes[0, 1].plot(phase, analytic_speed, label="Analytic material speed")
    axes[0, 1].plot(phase, discrete_speed, "--", label="Discrete ALE speed")
    axes[0, 1].axhline(
        metrics["minimum_angle16_absolute_mu"],
        color="black",
        ls=":",
        label="Smallest |mu|, S16",
    )
    axes[0, 1].set_ylabel("Speed / c")
    axes[0, 1].set_title("Surface mesh motion")
    axes[0, 1].legend(fontsize=8)
    axes[1, 0].semilogy(phase, duration)
    axes[1, 0].set_ylabel("Time step [s]")
    axes[1, 0].set_title("Pericentre-clustered time grid")
    axes[1, 1].semilogy(phase, displacement)
    axes[1, 1].axhline(1.0, color="black", ls=":")
    axes[1, 1].set_ylabel("Edge displacement / adjacent cell width")
    axes[1, 1].set_title("Why explicit remapping is unsafe")
    for axis in axes.flat:
        axis.set_xlabel("Orbital phase")
        axis.grid(alpha=0.25)
    fig.suptitle("Phase 7B4s ZO moving-grid audit")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_pilot(
    path: Path,
    material: dict[str, np.ndarray],
    full: dict[str, np.ndarray],
    pilot: dict[str, np.ndarray],
) -> None:
    phase = pilot["orbital_phase"]
    frequency = pilot["frequency_hz"]
    mean = pilot["mean_intensity_cgs"]
    local_planck = planck_nu(
        frequency[:, None, None], full["temperature_k"][None, :, :]
    )
    if np.any(local_planck <= 0.0):
        raise ArithmeticError("pilot Planck reference underflowed")
    surface_ratio = mean[:, :, 0] / local_planck[:, :, 0]
    midplane_ratio = mean[:, :, mean.shape[2] // 2] / local_planck[
        :, :, mean.shape[2] // 2
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12.0, 8.5), constrained_layout=True)
    colors = ("tab:blue", "tab:red")
    for index, energy in enumerate(pilot["photon_energy_ev"]):
        label = f"{energy:g} eV"
        axes[0, 0].semilogy(
            phase,
            pilot["left_outward_flux_nu_cgs"][index],
            color=colors[index],
            label=label,
        )
        axes[0, 1].semilogy(
            phase, surface_ratio[index], color=colors[index], label=label
        )
        axes[1, 0].semilogy(
            phase, midplane_ratio[index], color=colors[index], label=label
        )
    axes[0, 0].set_ylabel("Left outward Fnu [cgs]")
    axes[0, 0].set_title("Diagnostic monochromatic escape")
    axes[0, 1].set_ylabel("Jnu / Bnu")
    axes[0, 1].set_title("Surface nonlocality")
    axes[1, 0].set_ylabel("Jnu / Bnu")
    axes[1, 0].set_title("Midplane radiation memory")
    axes[1, 1].semilogy(
        phase, pilot["maximum_step_energy_ledger_residual"]
    )
    axes[1, 1].axhline(
        PILOT_ENERGY_LEDGER_TOLERANCE, color="black", ls=":"
    )
    axes[1, 1].set_ylabel("Relative energy-ledger residual")
    axes[1, 1].set_title("Stepwise conservation")
    for axis in axes.flat:
        axis.set_xlabel("Orbital phase")
        axis.grid(alpha=0.25)
    axes[0, 0].legend()
    axes[0, 1].legend()
    axes[1, 0].legend()
    fig.suptitle("Phase 7B4s prescribed-material radiation-storage pilot")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b4s_summary.json",
        "controls": output_dir / "phase7b4s_controls.csv",
        "mesh": output_dir / "phase7b4s_mesh_audit.csv",
        "cycles": output_dir / "phase7b4s_pilot_cycles.csv",
        "phase": output_dir / "phase7b4s_pilot_phase.csv",
        "npz": output_dir / "phase7b4s_two_frequency_pilot.npz",
        "control_plot": output_dir / "phase7b4s_implicit_controls.png",
        "mesh_plot": output_dir / "phase7b4s_zo_mesh_motion.png",
        "pilot_plot": output_dir / "phase7b4s_radiation_pilot.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    controls = analytic_control_rows()
    mesh_rows, mesh_metrics = mesh_audit_rows(material, full)
    pilot, cycle_rows, pilot_metrics = run_periodic_pilot(material, full)
    phase_rows: list[dict[str, object]] = []
    for phase_index, orbital_phase in enumerate(material["orbital_phase"]):
        for frequency_index, energy in enumerate(PILOT_ENERGY_EV):
            phase_rows.append(
                {
                    "phase_index": phase_index,
                    "orbital_phase": float(orbital_phase),
                    "photon_energy_ev": float(energy),
                    "left_outward_flux_nu_cgs": float(
                        pilot["left_outward_flux_nu_cgs"][
                            frequency_index, phase_index
                        ]
                    ),
                    "right_outward_flux_nu_cgs": float(
                        pilot["right_outward_flux_nu_cgs"][
                            frequency_index, phase_index
                        ]
                    ),
                    "surface_mean_intensity_cgs": float(
                        pilot["mean_intensity_cgs"][frequency_index, phase_index, 0]
                    ),
                    "midplane_mean_intensity_cgs": float(
                        pilot["mean_intensity_cgs"][
                            frequency_index,
                            phase_index,
                            pilot["mean_intensity_cgs"].shape[2] // 2,
                        ]
                    ),
                    "maximum_step_energy_ledger_residual": float(
                        pilot["maximum_step_energy_ledger_residual"][phase_index]
                    ),
                }
            )
    _write_csv(paths["controls"], controls)
    _write_csv(paths["mesh"], mesh_rows)
    _write_csv(paths["cycles"], cycle_rows)
    _write_csv(paths["phase"], phase_rows)
    _save_npz_atomic(paths["npz"], **pilot)
    _plot_controls(paths["control_plot"], controls, cycle_rows)
    _plot_mesh(paths["mesh_plot"], mesh_rows, mesh_metrics)
    _plot_pilot(paths["pilot_plot"], material, full, pilot)
    controls_passed = all(bool(row["passed"]) for row in controls)
    pilot_passed = bool(
        pilot_metrics["cycle_converged"]
        and pilot_metrics["energy_ledger_passed"]
        and pilot_metrics["linear_system_passed"]
    )
    report = {
        "phase": "7B4s",
        "classification": (
            "[V] implicit ALE transport gate; [A] two-frequency prescribed-material pilot"
        ),
        "equation_scope": {
            "included": [
                "lab-frame radiation storage",
                "implicit nonuniform-grid transport",
                "conservative ALE mesh flux",
                "true absorption and thermal emission",
                "coherent isotropic electron scattering",
                "vacuum boundaries",
            ],
            "omitted": [
                "Lorentz frequency and angle coupling",
                "radiation feedback on temperature and populations",
                "full 160-node threshold quadrature",
                "16-subcell formal depth production grid",
            ],
        },
        "controls": controls,
        "mesh_audit": mesh_metrics,
        "pilot": pilot_metrics,
        "decision": {
            "analytic_and_conservation_controls_passed": controls_passed,
            "n128_two_frequency_periodic_storage_pilot_passed": pilot_passed,
            "explicit_real_light_speed_orbit_rejected": bool(
                mesh_metrics["formal_subcell_explicit_cfl_steps_per_orbit"]
                > 1.0e6
            ),
            "ale_mesh_motion_required": bool(
                mesh_metrics["maximum_edge_displacement_per_adjacent_width"] > 1.0
            ),
            "velocity_frequency_angle_gate_required": bool(
                mesh_metrics["maximum_analytic_mesh_speed_to_c"]
                > VELOCITY_NEGLECT_TOLERANCE
            ),
            "phase7b4s_kernel_gate_passed": bool(controls_passed and pilot_passed),
            "full_dynamic_nonlocal_spectrum_authorized": False,
            "next_microphase": (
                "mixed-frame velocity terms and scalable full-frequency solver"
            ),
        },
    }
    _write_json_atomic(paths["summary"], report)
    print(json.dumps(report["decision"], indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--material-reference",
        type=Path,
        default=Path("outputs/phase7b4r_depth128_phase2048.npz"),
    )
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    run_all(
        arguments.output_dir,
        arguments.material_reference,
        force=arguments.force,
    )


if __name__ == "__main__":
    main()
