"""Phase 7B4w：阈值局域有限体积频率组准入门。"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.atomic_continuum import (
    EV_ERG,
    H_HE_GROUND_STATE_PHOTOIONIZATION_FITS,
)
from eccentric_tde_observer.frequency_quadrature import (
    threshold_excess_frequency_group_edges_ev,
)
from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil,
    mixed_frame_frequency_stencil_from_active_edges,
    solve_mixed_frame_ale_group_step,
)
from eccentric_tde_observer.mixed_frame_frequency import lorentz_ray_transform
from eccentric_tde_observer.multigroup_continuum import (
    gauss_legendre_frequency_group_quadrature,
    ground_state_milne_multigroup,
    group_average_from_quadrature_nodes,
)
from eccentric_tde_observer.radiation import (
    BOLTZMANN_ERG_K,
    LIGHT_SPEED_CM_S,
    PLANCK_ERG_S,
    planck_nu,
)
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
        _boosted_planck_outer,
        _collision_physical_slice,
        _relative_component_errors,
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
        _boosted_planck_outer,
        _collision_physical_slice,
        _relative_component_errors,
    )


PHYSICAL_ENERGY_RANGE_EV = (0.1, 5000.0)
MINIMUM_TEMPERATURE_K = 5000.0
THRESHOLD_PANELS_PER_DECADE = (64, 128, 256, 512, 1024, 2048)
UNIFORM_BASELINE_GROUPS_PER_DECADE = 256
REFERENCE_GROUPS_PER_DECADE = 8192
CONTROL_ANGULAR_ORDER = 8
GROUP_QUADRATURE_ORDER = 16
ACTUAL_FREQUENCY_TARGET = 1.0e-3
EFFICIENCY_GROUP_LIMIT = 4814
COUPLED_RESIDUAL_TARGET = 2.0e-8
ENERGY_LEDGER_TARGET = 2.0e-8
ITERATIVE_TOLERANCE = 1.0e-10


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


def _threshold_scale_ev() -> float:
    return BOLTZMANN_ERG_K * MINIMUM_TEMPERATURE_K / EV_ERG


def _threshold_edges_ev(panels_per_decade: int) -> np.ndarray:
    return threshold_excess_frequency_group_edges_ev(
        *PHYSICAL_ENERGY_RANGE_EV,
        panels_per_decade,
        threshold_scale_ev=_threshold_scale_ev(),
    )


def _threshold_stencil(panels_per_decade: int, maximum_beta: float):
    edge_hz = _threshold_edges_ev(panels_per_decade) * EV_ERG / PLANCK_ERG_S
    return mixed_frame_frequency_stencil_from_active_edges(edge_hz, maximum_beta)


def _grid_control_rows(
    maximum_beta: float,
    resolutions: tuple[int, ...] = THRESHOLD_PANELS_PER_DECADE,
) -> list[dict[str, object]]:
    thresholds = np.array(
        [fit.threshold_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS]
    )
    temperatures = np.array([5.0e3, 2.0e4, 2.0e5])
    rows: list[dict[str, object]] = []
    for panels in resolutions:
        edge_ev = _threshold_edges_ev(panels)
        edge_hz = edge_ev * EV_ERG / PLANCK_ERG_S
        stencil = mixed_frame_frequency_stencil_from_active_edges(
            edge_hz, maximum_beta
        )
        quadrature = gauss_legendre_frequency_group_quadrature(
            edge_hz, order_per_group=GROUP_QUADRATURE_ORDER
        )
        node_planck = planck_nu(
            quadrature.node_hz[:, :, None], temperatures[None, None, :]
        )
        group_planck = group_average_from_quadrature_nodes(
            node_planck, quadrature
        )
        integrated = np.sum(
            quadrature.group_width_hz[:, None] * group_planck, axis=0
        )
        expected = np.array(
            [
                np.sum(
                    quadrature.node_weight_hz
                    * planck_nu(quadrature.node_hz, temperature)
                )
                for temperature in temperatures
            ]
        )
        planck_error = float(
            np.max(np.abs(integrated - expected) / np.abs(expected))
        )
        roundtrip_threshold = np.array(
            [edge_ev[np.argmin(np.abs(edge_ev - value))] for value in thresholds]
        )
        threshold_error = float(
            np.max(np.abs(roundtrip_threshold - thresholds) / thresholds)
        )
        rows.append(
            {
                "representation": "threshold excess P0",
                "panels_per_transformed_decade": panels,
                "physical_frequency_groups": stencil.physical_group_count,
                "comoving_collision_groups": stencil.comoving_collision_group_count,
                "outer_guard_groups": stencil.outer_lab_group_count,
                "minimum_group_width_ev": float(np.min(np.diff(edge_ev))),
                "median_group_width_ev": float(np.median(np.diff(edge_ev))),
                "maximum_group_width_ev": float(np.max(np.diff(edge_ev))),
                "maximum_threshold_relative_error": threshold_error,
                "maximum_planck_integral_identity_error": planck_error,
                "strictly_positive_widths": bool(np.all(np.diff(edge_ev) > 0.0)),
                "all_thresholds_explicit": bool(np.all(np.isin(thresholds, edge_ev))),
                "passed": bool(
                    threshold_error == 0.0
                    and planck_error < 5.0e-13
                    and np.all(np.diff(edge_ev) > 0.0)
                    and np.all(np.isin(thresholds, edge_ev))
                ),
            }
        )
    return rows


def _irregular_moving_equilibrium_control(maximum_beta: float) -> dict[str, object]:
    panels = 256
    beta = np.array([0.05])
    stencil = _threshold_stencil(panels, max(maximum_beta, float(beta[0])))
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    transform = lorentz_ray_transform(mu, weight, beta)
    comoving_value = 1.7
    outer = np.broadcast_to(
        comoving_value * transform.doppler_lab_to_comoving[None, ...] ** -3.0,
        (stencil.outer_lab_group_count, mu.size, 1),
    ).copy()
    active = outer[_active_slice(stencil)]
    collision_shape = (stencil.comoving_collision_group_count, 1)
    absorption = np.full(collision_shape, 0.6)
    scattering = np.full(collision_shape, 0.4)
    result = solve_mixed_frame_ale_group_step(
        stencil,
        np.array([0.0, 1.0]),
        np.array([0.005, 1.005]),
        mu,
        weight,
        active,
        outer,
        absorption,
        absorption * comoving_value,
        scattering,
        beta,
        0.1,
        propagation_speed_cm_s=1.0,
        periodic_spatial_boundary=True,
        iterative_tolerance=2.0e-12,
    )
    scale = float(np.max(np.abs(active)))
    error = float(
        np.max(np.abs(result.final_lab_intensity_density - active)) / scale
    )
    return {
        "control": "irregular threshold-grid moving equilibrium",
        "panels_per_transformed_decade": panels,
        "physical_frequency_groups": stencil.physical_group_count,
        "equilibrium_error": error,
        "global_coupled_residual": result.global_scale_normalized_coupled_residual,
        "total_energy_ledger_residual": result.total_relative_energy_ledger_residual,
        "minimum_intensity": result.minimum_intensity,
        "passed": bool(
            error < 1.0e-10
            and result.global_scale_normalized_coupled_residual
            < COUPLED_RESIDUAL_TARGET
            and result.total_relative_energy_ledger_residual
            < ENERGY_LEDGER_TARGET
            and result.minimum_intensity >= 0.0
        ),
    }


def _representation_stencil(
    representation: str,
    resolution: int,
    maximum_beta: float,
):
    if representation == "uniform logarithmic P0":
        return mixed_frame_frequency_stencil(
            *PHYSICAL_ENERGY_RANGE_EV, resolution, maximum_beta
        )
    if representation == "threshold excess P0":
        return _threshold_stencil(resolution, maximum_beta)
    raise ValueError(f"unknown frequency representation: {representation}")


def _actual_one_cell_run(
    material: dict[str, np.ndarray],
    full: dict[str, np.ndarray],
    audit: dict[str, object],
    definition: dict[str, object],
    representation: str,
    resolution: int,
) -> tuple[dict[str, object], dict[str, float]]:
    phase = int(definition["phase_index"])
    following = int(definition["following_phase_index"])
    depth = int(definition["full_depth_index"])
    duration = float(material["step_duration_s"][phase])
    old_edge = full["edges_cm"][phase, depth : depth + 2]
    new_edge = full["edges_cm"][following, depth : depth + 2]
    edge_velocity = (new_edge - old_edge) / duration
    beta = np.array([np.mean(edge_velocity) / LIGHT_SPEED_CM_S])
    stencil = _representation_stencil(
        representation,
        resolution,
        float(audit["maximum_velocity_beta"]),
    )
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    temperature = float(full["temperature_k"][following, depth])
    density = float(full["density_g_cm3"][following, depth])
    hydrogen = full["hydrogen_fraction"][following, depth]
    helium = full["helium_fraction"][following, depth]
    outer = _boosted_planck_outer(stencil, mu, weight, beta, temperature)
    active = outer[_active_slice(stencil)]
    quadrature = gauss_legendre_frequency_group_quadrature(
        stencil.comoving_collision_edge_hz,
        order_per_group=GROUP_QUADRATURE_ORDER,
    )
    group_planck = group_average_from_quadrature_nodes(
        planck_nu(quadrature.node_hz, temperature), quadrature
    )[:, None]
    continuum = ground_state_milne_multigroup(
        density,
        temperature,
        stencil.comoving_collision_edge_hz,
        group_planck,
        hydrogen[0],
        hydrogen[1],
        helium[0],
        helium[1],
        helium[2],
        order_per_group=GROUP_QUADRATURE_ORDER,
    ).continuum
    started = time.perf_counter()
    result = solve_mixed_frame_ale_group_step(
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        active,
        outer,
        continuum.true_absorption_total_per_cm,
        continuum.thermal_emissivity_total_cgs,
        continuum.electron_scattering_per_cm,
        beta,
        duration,
        iterative_tolerance=ITERATIVE_TOLERANCE,
        iterative_maximum_iterations=8192,
    )
    physical = _collision_physical_slice(stencil)
    physical_mean = result.final_comoving_mean_intensity_density[physical]
    microphysics = ground_state_milne_multigroup(
        density,
        temperature,
        stencil.active_lab_edge_hz,
        physical_mean,
        hydrogen[0],
        hydrogen[1],
        helium[0],
        helium[1],
        helium[2],
        order_per_group=GROUP_QUADRATURE_ORDER,
    )
    width = np.diff(stencil.active_lab_edge_hz)
    left_outward = -2.0 * np.pi * np.sum(
        width[:, None]
        * weight[None, mu < 0.0]
        * mu[None, mu < 0.0]
        * result.left_ale_face_intensity[:, mu < 0.0]
    )
    right_outward = 2.0 * np.pi * np.sum(
        width[:, None]
        * weight[None, mu > 0.0]
        * mu[None, mu > 0.0]
        * result.right_ale_face_intensity[:, mu > 0.0]
    )
    diagnostics = {
        "radiation_energy": float(
            np.sum(width * result.final_radiation_energy_group_erg_cm2_hz)
        ),
        "left_outward_flux": float(left_outward),
        "right_outward_flux": float(right_outward),
        "absorbed_power": float(microphysics.absorbed_power_erg_s_cm3[0]),
        "emitted_power": float(microphysics.emitted_power_erg_s_cm3[0]),
        "radiative_heating": float(microphysics.radiative_heating_erg_s_cm3[0]),
    }
    for ion, value in zip(
        ("H_I", "He_I", "He_II"),
        microphysics.radiative_rates.photoionization_s1[0],
        strict=True,
    ):
        diagnostics[f"photoionization_{ion}"] = float(value)
    for ion, value in zip(
        ("H_II", "He_II", "He_III"),
        microphysics.radiative_rates.total_recombination_cm3_s[0],
        strict=True,
    ):
        diagnostics[f"total_recombination_{ion}"] = float(value)
    row = {
        **definition,
        "representation": representation,
        "resolution_parameter": resolution,
        "physical_frequency_groups": stencil.physical_group_count,
        "comoving_collision_groups": stencil.comoving_collision_group_count,
        "outer_guard_groups": stencil.outer_lab_group_count,
        "orbital_phase": float(material["orbital_phase"][following]),
        "temperature_k": temperature,
        "density_g_cm3": density,
        "cell_velocity_beta": float(beta[0]),
        "maximum_optical_depth": float(
            np.max(continuum.extinction_total_per_cm * np.diff(new_edge)[0])
        ),
        "fixed_point_iterations": result.fixed_point_iterations,
        "global_coupled_residual": result.global_scale_normalized_coupled_residual,
        "total_energy_ledger_residual": result.total_relative_energy_ledger_residual,
        "minimum_intensity": result.minimum_intensity,
        "runtime_s": float(time.perf_counter() - started),
    }
    return row, diagnostics


def _actual_state_convergence(material, full, audit):
    definitions = _actual_case_definitions(material, full, audit)
    representations = [
        ("uniform logarithmic P0", UNIFORM_BASELINE_GROUPS_PER_DECADE),
        *(("threshold excess P0", value) for value in THRESHOLD_PANELS_PER_DECADE),
        ("uniform logarithmic P0", REFERENCE_GROUPS_PER_DECADE),
    ]
    raw_rows: list[dict[str, object]] = []
    diagnostics: dict[tuple[str, str, int], dict[str, float]] = {}
    for definition in definitions:
        case = str(definition["case"])
        for representation, resolution in representations:
            row, values = _actual_one_cell_run(
                material,
                full,
                audit,
                definition,
                representation,
                resolution,
            )
            raw_rows.append(row)
            diagnostics[(case, representation, resolution)] = values
    convergence: list[dict[str, object]] = []
    for definition in definitions:
        case = str(definition["case"])
        reference = diagnostics[
            (case, "uniform logarithmic P0", REFERENCE_GROUPS_PER_DECADE)
        ]
        for representation, resolution in representations:
            candidate = diagnostics[(case, representation, resolution)]
            errors = _relative_component_errors(candidate, reference)
            raw = next(
                row
                for row in raw_rows
                if row["case"] == case
                and row["representation"] == representation
                and row["resolution_parameter"] == resolution
            )
            convergence.append(
                {
                    "case": case,
                    "representation": representation,
                    "resolution_parameter": resolution,
                    "physical_frequency_groups": raw["physical_frequency_groups"],
                    **{f"{name}_error": value for name, value in errors.items()},
                    "maximum_error": max(errors.values()),
                    "reference": bool(
                        representation == "uniform logarithmic P0"
                        and resolution == REFERENCE_GROUPS_PER_DECADE
                    ),
                }
            )
    return raw_rows, convergence


def _plot_group_geometry(path: Path, controls: list[dict[str, object]]) -> None:
    thresholds = np.array(
        [fit.threshold_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS]
    )
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 4.8), constrained_layout=True)
    for panels in (64, 256, 1024):
        edge = _threshold_edges_ev(panels)
        centre = np.sqrt(edge[:-1] * edge[1:])
        axes[0].loglog(
            centre,
            np.diff(edge),
            label=f"{panels} panels/transformed decade",
        )
    for threshold in thresholds:
        axes[0].axvline(threshold, color="black", linestyle=":", linewidth=0.8)
    axes[0].set_xlabel("Photon energy (eV)")
    axes[0].set_ylabel("Local group width (eV)")
    axes[0].set_title("Threshold-local finite-volume geometry")
    axes[0].legend(fontsize=8)

    count = np.array([row["physical_frequency_groups"] for row in controls])
    minimum = np.array([row["minimum_group_width_ev"] for row in controls])
    median = np.array([row["median_group_width_ev"] for row in controls])
    maximum = np.array([row["maximum_group_width_ev"] for row in controls])
    axes[1].loglog(count, minimum, marker="o", label="minimum width")
    axes[1].loglog(count, median, marker="s", label="median width")
    axes[1].loglog(count, maximum, marker="^", label="maximum width")
    axes[1].set_xlabel("Physical frequency groups")
    axes[1].set_ylabel("Group width (eV)")
    axes[1].set_title("Local resolution and global cost")
    axes[1].legend()
    fig.suptitle("Phase 7B4w threshold-excess frequency groups")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_actual_convergence(
    path: Path,
    raw_rows: list[dict[str, object]],
    convergence: list[dict[str, object]],
    selected_resolution: int | None,
) -> None:
    cases = list(dict.fromkeys(str(row["case"]) for row in convergence))
    components = (
        "radiation_energy_error",
        "photoionization_H_I_error",
        "photoionization_He_I_error",
        "photoionization_He_II_error",
        "heating_ledger_error",
    )
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8), constrained_layout=True)
    for case in cases:
        selected = [
            row
            for row in convergence
            if row["case"] == case
            and row["representation"] == "threshold excess P0"
        ]
        axes[0].loglog(
            [row["physical_frequency_groups"] for row in selected],
            [row["maximum_error"] for row in selected],
            marker="o",
            label=case,
        )
    baseline = [
        row
        for row in convergence
        if row["representation"] == "uniform logarithmic P0"
        and row["resolution_parameter"] == UNIFORM_BASELINE_GROUPS_PER_DECADE
    ]
    axes[0].scatter(
        [row["physical_frequency_groups"] for row in baseline],
        [row["maximum_error"] for row in baseline],
        marker="x",
        color="black",
        label="uniform 1205 baseline",
    )
    axes[0].axhline(ACTUAL_FREQUENCY_TARGET, color="black", linestyle=":", label="gate")
    axes[0].axvline(EFFICIENCY_GROUP_LIMIT, color="grey", linestyle="--", label="cost limit")
    axes[0].set_xlabel("Physical frequency groups")
    axes[0].set_ylabel("Maximum error vs 38496-group reference")
    axes[0].set_title("Actual one-cell convergence")
    axes[0].legend(fontsize=7)

    heat_resolution = selected_resolution or THRESHOLD_PANELS_PER_DECADE[-1]
    heat_rows = [
        row
        for row in convergence
        if row["representation"] == "threshold excess P0"
        and row["resolution_parameter"] == heat_resolution
    ]
    image = axes[1].imshow(
        np.asarray([[row[name] for name in components] for row in heat_rows]),
        aspect="auto",
        origin="lower",
    )
    axes[1].set_xticks(range(len(components)))
    axes[1].set_xticklabels(
        ["radiation E", "H I rate", "He I rate", "He II rate", "heating"],
        rotation=25,
        ha="right",
    )
    axes[1].set_yticks(range(len(cases)))
    axes[1].set_yticklabels(cases)
    heat_title = (
        "First frequency-pass components"
        if selected_resolution is not None
        else "Finest tested-grid components"
    )
    axes[1].set_title(f"{heat_title} ({heat_resolution})")
    fig.colorbar(image, ax=axes[1], label="Relative error")

    for case in cases:
        selected = [
            row
            for row in raw_rows
            if row["case"] == case
            and row["representation"] == "threshold excess P0"
        ]
        axes[2].loglog(
            [row["physical_frequency_groups"] for row in selected],
            [row["runtime_s"] for row in selected],
            marker="o",
            label=case,
        )
    axes[2].axvline(EFFICIENCY_GROUP_LIMIT, color="grey", linestyle="--")
    axes[2].set_xlabel("Physical frequency groups")
    axes[2].set_ylabel("One-cell runtime (s)")
    axes[2].set_title("Component cost")
    axes[2].legend(fontsize=8)
    fig.suptitle("Phase 7B4w threshold-local dynamic frequency gate")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b4w_summary.json",
        "controls": output_dir / "phase7b4w_controls.csv",
        "states": output_dir / "phase7b4w_actual_states.csv",
        "convergence": output_dir / "phase7b4w_state_convergence.csv",
        "diagnostics": output_dir / "phase7b4w_diagnostics.npz",
        "geometry_plot": output_dir / "phase7b4w_threshold_group_geometry.png",
        "convergence_plot": output_dir / "phase7b4w_actual_state_convergence.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    audit = _trajectory_velocity_audit(material, full)
    controls = _grid_control_rows(float(audit["maximum_velocity_beta"]))
    moving_control = _irregular_moving_equilibrium_control(
        float(audit["maximum_velocity_beta"])
    )
    raw_rows, convergence = _actual_state_convergence(material, full, audit)
    candidate_resolutions = []
    for resolution in THRESHOLD_PANELS_PER_DECADE:
        rows = [
            row
            for row in convergence
            if row["representation"] == "threshold excess P0"
            and row["resolution_parameter"] == resolution
        ]
        if max(float(row["maximum_error"]) for row in rows) < ACTUAL_FREQUENCY_TARGET:
            candidate_resolutions.append(resolution)
    selected_resolution = min(candidate_resolutions) if candidate_resolutions else None
    selected_groups = None
    if selected_resolution is not None:
        selected_groups = int(
            next(
                row["physical_frequency_groups"]
                for row in convergence
                if row["representation"] == "threshold excess P0"
                and row["resolution_parameter"] == selected_resolution
            )
        )
    operator_gate = bool(
        all(bool(row["passed"]) for row in controls)
        and bool(moving_control["passed"])
        and all(
            float(row["global_coupled_residual"]) < COUPLED_RESIDUAL_TARGET
            and float(row["total_energy_ledger_residual"]) < ENERGY_LEDGER_TARGET
            and float(row["minimum_intensity"]) >= 0.0
            for row in raw_rows
            if row["representation"] == "threshold excess P0"
        )
    )
    frequency_gate = selected_groups is not None
    efficiency_gate = bool(
        selected_groups is not None and selected_groups <= EFFICIENCY_GROUP_LIMIT
    )
    component_gate = bool(operator_gate and frequency_gate and efficiency_gate)
    decision = {
        "threshold_group_geometry_gate_passed": bool(
            all(bool(row["passed"]) for row in controls)
        ),
        "irregular_grid_moving_equilibrium_passed": bool(moving_control["passed"]),
        "threshold_excess_operator_gate_passed": operator_gate,
        "three_actual_state_frequency_gate_passed": frequency_gate,
        "minimum_frequency_passing_panels_per_transformed_decade": (
            selected_resolution if frequency_gate else None
        ),
        "minimum_frequency_passing_physical_frequency_groups": (
            selected_groups if frequency_gate else None
        ),
        "efficiency_gate_passed": efficiency_gate,
        "threshold_local_component_gate_passed": component_gate,
        "selected_panels_per_transformed_decade": (
            selected_resolution if component_gate else None
        ),
        "selected_candidate_physical_frequency_groups": (
            selected_groups if component_gate else None
        ),
        "p1_frequency_moment_required": not component_gate,
        "angular_radiation_subgrid_time_gate_authorized": component_gate,
        "full_dynamic_orbit_authorized": False,
        "matter_temperature_population_feedback_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }
    _write_csv(paths["controls"], controls)
    _write_csv(paths["states"], raw_rows)
    _write_csv(paths["convergence"], convergence)
    _save_npz_atomic(
        paths["diagnostics"],
        candidate_group_counts=np.array(
            [row["physical_frequency_groups"] for row in controls], dtype=int
        ),
        candidate_panels_per_decade=np.array(
            THRESHOLD_PANELS_PER_DECADE, dtype=int
        ),
        threshold_energy_ev=np.array(
            [fit.threshold_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS]
        ),
    )
    _plot_group_geometry(paths["geometry_plot"], controls)
    _plot_actual_convergence(
        paths["convergence_plot"], raw_rows, convergence, selected_resolution
    )
    report = {
        "phase": "7B4w",
        "classification": (
            "[A/V] threshold-excess P0 finite-volume frequency representation; "
            "[O] angular/radiation-subgrid/time orbit and matter feedback"
        ),
        "configuration": {
            "physical_energy_range_ev": list(PHYSICAL_ENERGY_RANGE_EV),
            "minimum_temperature_scale_k": MINIMUM_TEMPERATURE_K,
            "threshold_scale_ev": _threshold_scale_ev(),
            "threshold_panels_per_transformed_decade": list(
                THRESHOLD_PANELS_PER_DECADE
            ),
            "uniform_baseline_groups_per_decade": UNIFORM_BASELINE_GROUPS_PER_DECADE,
            "uniform_reference_groups_per_decade": REFERENCE_GROUPS_PER_DECADE,
            "actual_frequency_target": ACTUAL_FREQUENCY_TARGET,
            "efficiency_group_limit": EFFICIENCY_GROUP_LIMIT,
            "group_quadrature_order": GROUP_QUADRATURE_ORDER,
            "angular_order": CONTROL_ANGULAR_ORDER,
        },
        "controls": controls,
        "moving_equilibrium_control": moving_control,
        "actual_states": raw_rows,
        "state_convergence": convergence,
        "decision": decision,
        "open_items": [
            "the 18105-group frequency pass exceeds the predeclared 4814-group efficiency limit",
            "the finite 38496-group comparison is not a continuum truth",
            "independent orbital-state coverage has not yet been restored",
            "the S16/S24 angular and 16/32 radiation-subcell gates remain unrun",
            "the 2048-phase full radiation orbit remains unauthorized",
            "temperature and H/He populations still do not respond to the radiation field",
            "excited levels, cascades, Compton redistribution, and line transfer remain open",
        ],
        "figures": {
            "threshold_group_geometry": paths["geometry_plot"].name,
            "actual_state_convergence": paths["convergence_plot"].name,
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
