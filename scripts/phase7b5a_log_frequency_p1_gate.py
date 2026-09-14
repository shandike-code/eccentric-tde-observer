"""Phase 7B5a：对数频率守恒 P1 表示的同预算准入门。"""

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

from eccentric_tde_observer.log_frequency_moments import (
    limit_nonnegative_log_frequency_group_p1,
)
from eccentric_tde_observer.log_multigroup_continuum import (
    gauss_legendre_log_frequency_group_quadrature,
    ground_state_milne_log_p1_multigroup,
    log_group_average_from_quadrature_nodes,
    log_group_p1_moment_from_quadrature_nodes,
)
from eccentric_tde_observer.mixed_frame_ale import mixed_frame_frequency_stencil
from eccentric_tde_observer.mixed_frame_ale_log_p1 import (
    solve_mixed_frame_ale_log_p1_group_step,
)
from eccentric_tde_observer.mixed_frame_frequency import lorentz_ray_transform
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S, planck_nu
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
        _active_slice,
        _actual_case_definitions,
        _actual_one_cell_run as _p0_actual_one_cell_run,
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
        _active_slice,
        _actual_case_definitions,
        _actual_one_cell_run as _p0_actual_one_cell_run,
        _collision_physical_slice,
        _relative_component_errors,
    )


PHYSICAL_ENERGY_RANGE_EV = (0.1, 5000.0)
LOG_P1_GROUPS_PER_DECADE = (32, 64, 128, 256, 512)
REFERENCE_P0_GROUPS_PER_DECADE = 8192
CONTROL_ANGULAR_ORDER = 8
GROUP_QUADRATURE_ORDER = 16
ACTUAL_FREQUENCY_TARGET = 1.0e-3
P1_GROUP_LIMIT = 2408
SPECTRAL_DOF_LIMIT = 4816
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


def _boosted_planck_outer_log_p1(stencil, mu, weight, beta, temperature):
    transform = lorentz_ray_transform(mu, weight, beta)
    quadrature = gauss_legendre_log_frequency_group_quadrature(
        stencil.outer_lab_edge_hz,
        order_per_group=GROUP_QUADRATURE_ORDER,
    )
    mean = np.empty((stencil.outer_lab_group_count, mu.size, beta.size))
    moment = np.empty_like(mean)
    for angle in range(mu.size):
        for depth, factor in enumerate(transform.doppler_lab_to_comoving[angle]):
            frequency = quadrature.node_hz
            # 中文：保存 Q=nu*I_nu；共动黑体到实验室系使用 I_nu=D^-3 B_nu(D nu)。
            node_energy = frequency * factor**-3 * planck_nu(
                factor * frequency, temperature
            )
            mean[:, angle, depth] = log_group_average_from_quadrature_nodes(
                node_energy, quadrature
            )
            moment[:, angle, depth] = log_group_p1_moment_from_quadrature_nodes(
                node_energy, quadrature
            )
    return limit_nonnegative_log_frequency_group_p1(mean, moment)


def _planck_material_log_p1(stencil, density, temperature, hydrogen, helium):
    quadrature = gauss_legendre_log_frequency_group_quadrature(
        stencil.comoving_collision_edge_hz,
        order_per_group=GROUP_QUADRATURE_ORDER,
    )
    node_energy = quadrature.node_hz * planck_nu(
        quadrature.node_hz, temperature
    )
    planck_mean = log_group_average_from_quadrature_nodes(
        node_energy, quadrature
    )[:, None]
    planck_moment = log_group_p1_moment_from_quadrature_nodes(
        node_energy, quadrature
    )[:, None]
    planck_state = limit_nonnegative_log_frequency_group_p1(
        planck_mean, planck_moment
    )
    microphysics = ground_state_milne_log_p1_multigroup(
        density,
        temperature,
        stencil.comoving_collision_edge_hz,
        planck_state.mean_density,
        planck_state.first_moment_density,
        hydrogen[0],
        hydrogen[1],
        helium[0],
        helium[1],
        helium[2],
        order_per_group=GROUP_QUADRATURE_ORDER,
    )
    return planck_state, microphysics


def _actual_one_cell_run_log_p1(
    material: dict[str, np.ndarray],
    full: dict[str, np.ndarray],
    audit: dict[str, object],
    definition: dict[str, object],
    groups_per_decade: int,
    *,
    stencil_override=None,
    diagnostic_arrays: dict[str, np.ndarray] | None = None,
    material_velocity_beta_override: float | None = None,
    rigid_mesh_control: bool = False,
    include_true_absorption_emission: bool = True,
    include_scattering: bool = True,
    apply_intensity_lorentz: bool = True,
    apply_extinction_lorentz: bool = True,
    apply_emissivity_lorentz: bool = True,
    iterative_tolerance_override: float | None = None,
    iteration_observer=None,
) -> tuple[dict[str, object], dict[str, float]]:
    phase = int(definition["phase_index"])
    following = int(definition["following_phase_index"])
    depth = int(definition["full_depth_index"])
    duration = float(material["step_duration_s"][phase])
    old_edge = full["edges_cm"][phase, depth : depth + 2]
    new_edge = full["edges_cm"][following, depth : depth + 2]
    edge_velocity = (new_edge - old_edge) / duration
    if rigid_mesh_control:
        # 中文：保留平均平移速度，只去除一步中的单元宽度变化。
        mean_edge_velocity = float(np.mean(edge_velocity))
        old_edge = new_edge - mean_edge_velocity * duration
        edge_velocity = (new_edge - old_edge) / duration
    actual_beta = float(np.mean(edge_velocity) / LIGHT_SPEED_CM_S)
    beta = np.array(
        [
            actual_beta
            if material_velocity_beta_override is None
            else float(material_velocity_beta_override)
        ]
    )
    stencil = (
        mixed_frame_frequency_stencil(
            *PHYSICAL_ENERGY_RANGE_EV,
            groups_per_decade,
            float(audit["maximum_velocity_beta"]),
        )
        if stencil_override is None
        else stencil_override
    )
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    temperature = float(full["temperature_k"][following, depth])
    density = float(full["density_g_cm3"][following, depth])
    hydrogen = full["hydrogen_fraction"][following, depth]
    helium = full["helium_fraction"][following, depth]
    outer_beta = beta if apply_intensity_lorentz else np.zeros_like(beta)
    outer = _boosted_planck_outer_log_p1(
        stencil, mu, weight, outer_beta, temperature
    )
    active_mean = outer.mean_density[_active_slice(stencil)]
    active_moment = outer.first_moment_density[_active_slice(stencil)]
    planck_state, material_state = _planck_material_log_p1(
        stencil, density, temperature, hydrogen, helium
    )
    started = time.perf_counter()
    result = solve_mixed_frame_ale_log_p1_group_step(
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        active_mean,
        active_moment,
        outer.mean_density,
        outer.first_moment_density,
        (
            material_state.true_absorption_mean_per_cm
            if include_true_absorption_emission
            else np.zeros_like(material_state.true_absorption_mean_per_cm)
        ),
        (
            material_state.true_absorption_first_moment_per_cm
            if include_true_absorption_emission
            else np.zeros_like(material_state.true_absorption_first_moment_per_cm)
        ),
        (
            material_state.thermal_emissivity_energy_mean_cgs
            if include_true_absorption_emission
            else np.zeros_like(material_state.thermal_emissivity_energy_mean_cgs)
        ),
        (
            material_state.thermal_emissivity_energy_first_moment_cgs
            if include_true_absorption_emission
            else np.zeros_like(
                material_state.thermal_emissivity_energy_first_moment_cgs
            )
        ),
        (
            material_state.electron_scattering_mean_per_cm
            if include_scattering
            else np.zeros_like(material_state.electron_scattering_mean_per_cm)
        ),
        (
            material_state.electron_scattering_first_moment_per_cm
            if include_scattering
            else np.zeros_like(
                material_state.electron_scattering_first_moment_per_cm
            )
        ),
        beta,
        duration,
        iterative_tolerance=(
            ITERATIVE_TOLERANCE
            if iterative_tolerance_override is None
            else float(iterative_tolerance_override)
        ),
        iterative_maximum_iterations=8192,
        apply_intensity_lorentz=apply_intensity_lorentz,
        apply_extinction_lorentz=apply_extinction_lorentz,
        apply_emissivity_lorentz=apply_emissivity_lorentz,
        iteration_observer=iteration_observer,
    )
    runtime = float(time.perf_counter() - started)
    physical = _collision_physical_slice(stencil)
    physical_mean = result.final_comoving_mean_intensity_energy_density[physical]
    physical_moment = (
        result.final_comoving_mean_first_moment_intensity_energy_density[physical]
    )
    final_microphysics = ground_state_milne_log_p1_multigroup(
        density,
        temperature,
        stencil.active_lab_edge_hz,
        physical_mean,
        physical_moment,
        hydrogen[0],
        hydrogen[1],
        helium[0],
        helium[1],
        helium[2],
        order_per_group=GROUP_QUADRATURE_ORDER,
    )
    if diagnostic_arrays is not None:
        # 中文：只暴露共动末态物理频带；不改变求解器或事后重归一化。
        diagnostic_arrays.update(
            {
                "physical_group_edge_hz": np.array(
                    stencil.active_lab_edge_hz, copy=True
                ),
                "final_comoving_mean_intensity_energy": np.array(
                    physical_mean[:, 0], copy=True
                ),
                "final_comoving_first_moment_intensity_energy": np.array(
                    physical_moment[:, 0], copy=True
                ),
            }
        )
    log_width = np.diff(np.log(stencil.active_lab_edge_hz))
    negative = mu < 0.0
    positive = mu > 0.0
    left_outward = -2.0 * np.pi * np.sum(
        log_width[:, None]
        * weight[None, negative]
        * mu[None, negative]
        * result.left_ale_face_mean_intensity_energy[:, negative]
    )
    right_outward = 2.0 * np.pi * np.sum(
        log_width[:, None]
        * weight[None, positive]
        * mu[None, positive]
        * result.right_ale_face_mean_intensity_energy[:, positive]
    )
    diagnostics = {
        "radiation_energy": float(
            np.sum(
                log_width * result.final_radiation_energy_group_erg_cm2
            )
        ),
        "left_outward_flux": float(left_outward),
        "right_outward_flux": float(right_outward),
        "absorbed_power": float(final_microphysics.absorbed_power_erg_s_cm3[0]),
        "emitted_power": float(final_microphysics.emitted_power_erg_s_cm3[0]),
        "radiative_heating": float(
            final_microphysics.radiative_heating_erg_s_cm3[0]
        ),
    }
    for ion, value in zip(
        ("H_I", "He_I", "He_II"),
        final_microphysics.radiative_rates.photoionization_s1[0],
        strict=True,
    ):
        diagnostics[f"photoionization_{ion}"] = float(value)
    for ion, value in zip(
        ("H_II", "He_II", "He_III"),
        final_microphysics.radiative_rates.total_recombination_cm3_s[0],
        strict=True,
    ):
        diagnostics[f"total_recombination_{ion}"] = float(value)
    prelimit_ratios = (
        outer.maximum_prelimit_realizability_ratio,
        planck_state.maximum_prelimit_realizability_ratio,
        material_state.maximum_continuum_prelimit_realizability_ratio,
        final_microphysics.maximum_continuum_prelimit_realizability_ratio,
        result.maximum_prelimit_realizability_ratio,
    )
    finite_prelimit_ratios = [
        value for value in prelimit_ratios if np.isfinite(value)
    ]
    row = {
        **definition,
        "representation": "log-frequency conservative P1 in Q=nu*I_nu",
        "groups_per_decade": groups_per_decade,
        "resolution_parameter": groups_per_decade,
        "physical_frequency_groups": stencil.physical_group_count,
        "spectral_degrees_of_freedom": 2 * stencil.physical_group_count,
        "comoving_collision_groups": stencil.comoving_collision_group_count,
        "outer_guard_groups": stencil.outer_lab_group_count,
        "orbital_phase": float(material["orbital_phase"][following]),
        "duration_s": duration,
        "temperature_k": temperature,
        "density_g_cm3": density,
        "cell_velocity_beta": float(beta[0]),
        "maximum_optical_depth": float(
            np.max(
                material_state.extinction_mean_per_cm * np.diff(new_edge)[0]
            )
        ),
        "fixed_point_iterations": result.fixed_point_iterations,
        "fixed_point_converged": result.fixed_point_converged,
        "final_fixed_point_change": result.final_fixed_point_change,
        "global_coupled_residual": result.global_scale_normalized_coupled_residual,
        "maximum_group_relative_residual": (
            result.maximum_group_relative_coupled_residual
        ),
        "total_energy_ledger_residual": (
            result.total_relative_energy_ledger_residual
        ),
        "maximum_group_relative_energy_ledger": float(
            np.max(result.relative_energy_ledger_residual_group)
        ),
        "minimum_reconstructed_intensity": (
            result.minimum_reconstructed_intensity_energy_density
        ),
        "outer_radiation_limiter_count": outer.limited_group_count,
        "material_planck_limiter_count": planck_state.limited_group_count,
        "material_continuum_limiter_count": (
            material_state.continuum_limited_group_count
        ),
        "final_continuum_limiter_count": (
            final_microphysics.continuum_limited_group_count
        ),
        "solver_cumulative_limiter_count": (
            result.cumulative_limiter_activation_count
        ),
        "solver_final_limiter_count": result.final_limiter_activation_count,
        "maximum_finite_prelimit_realizability_ratio": max(
            finite_prelimit_ratios, default=0.0
        ),
        "zero_mean_nonzero_moment_encountered": bool(
            len(finite_prelimit_ratios) != len(prelimit_ratios)
        ),
        "runtime_s": runtime,
    }
    return row, diagnostics


def _moving_equilibrium_control(maximum_beta: float) -> dict[str, object]:
    beta = np.array([0.05])
    stencil = mixed_frame_frequency_stencil(
        *PHYSICAL_ENERGY_RANGE_EV, 64, max(maximum_beta, float(beta[0]))
    )
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    transform = lorentz_ray_transform(mu, weight, beta)
    value = 1.7
    outer_mean = np.broadcast_to(
        value * transform.doppler_lab_to_comoving[None, ...] ** -4.0,
        (stencil.outer_lab_group_count, mu.size, 1),
    ).copy()
    outer_moment = np.zeros_like(outer_mean)
    active = outer_mean[_active_slice(stencil)]
    collision_shape = (stencil.comoving_collision_group_count, 1)
    absorption = np.full(collision_shape, 0.6)
    scattering = np.full(collision_shape, 0.4)
    result = solve_mixed_frame_ale_log_p1_group_step(
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
        np.max(np.abs(result.final_lab_mean_intensity_energy_density - active))
        / np.max(active)
    )
    return {
        "control": "log-P1 moving constant-comoving-Q equilibrium",
        "physical_frequency_groups": stencil.physical_group_count,
        "equilibrium_error": error,
        "global_coupled_residual": result.global_scale_normalized_coupled_residual,
        "total_energy_ledger_residual": result.total_relative_energy_ledger_residual,
        "minimum_reconstructed_intensity": (
            result.minimum_reconstructed_intensity_energy_density
        ),
        "final_limiter_count": result.final_limiter_activation_count,
        "passed": bool(
            error < ACTUAL_FREQUENCY_TARGET
            and result.global_scale_normalized_coupled_residual
            < COUPLED_RESIDUAL_TARGET
            and result.total_relative_energy_ledger_residual
            < ENERGY_LEDGER_TARGET
            and result.minimum_reconstructed_intensity_energy_density >= 0.0
        ),
    }


def _actual_state_convergence(material, full, audit):
    definitions = _actual_case_definitions(material, full, audit)
    raw_rows: list[dict[str, object]] = []
    convergence: list[dict[str, object]] = []
    reference_values: dict[str, dict[str, float]] = {}
    for definition in definitions:
        case = str(definition["case"])
        _, reference, _ = _p0_actual_one_cell_run(
            material,
            full,
            audit,
            definition,
            REFERENCE_P0_GROUPS_PER_DECADE,
        )
        reference_values[case] = reference
        for groups_per_decade in LOG_P1_GROUPS_PER_DECADE:
            row, diagnostics = _actual_one_cell_run_log_p1(
                material,
                full,
                audit,
                definition,
                groups_per_decade,
            )
            raw_rows.append(row)
            errors = _relative_component_errors(diagnostics, reference)
            convergence.append(
                {
                    "case": case,
                    "representation": "log-frequency conservative P1",
                    "groups_per_decade": groups_per_decade,
                    "physical_frequency_groups": row["physical_frequency_groups"],
                    "spectral_degrees_of_freedom": row[
                        "spectral_degrees_of_freedom"
                    ],
                    **{f"{name}_error": value for name, value in errors.items()},
                    "maximum_error": max(errors.values()),
                    "reference": False,
                }
            )
    return raw_rows, convergence, reference_values


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
    axes[0].set_title("Log-P1 accuracy vs. 38496-group P0 reference")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.25, which="both")

    component_names = (
        "radiation_energy_error",
        "left_outward_flux_error",
        "right_outward_flux_error",
        "photoionization_H_I_error",
        "photoionization_He_I_error",
        "photoionization_He_II_error",
        "heating_ledger_error",
    )
    labels = ("energy", "left flux", "right flux", "H I", "He I", "He II", "heating")
    target = selected_groups or max(
        int(row["physical_frequency_groups"]) for row in convergence
    )
    width = 0.8 / len(cases)
    x = np.arange(len(labels))
    for index, case in enumerate(cases):
        row = next(
            row
            for row in convergence
            if row["case"] == case
            and int(row["physical_frequency_groups"]) == target
        )
        axes[1].bar(
            x + (index - (len(cases) - 1) / 2.0) * width,
            [row[name] for name in component_names],
            width=width,
            label=case,
        )
    axes[1].axhline(ACTUAL_FREQUENCY_TARGET, color="black", linestyle=":")
    axes[1].set_yscale("log")
    axes[1].set_xticks(x, labels, rotation=35, ha="right")
    axes[1].set_ylabel("Relative error")
    axes[1].set_title(f"Component errors at {target} log-P1 groups")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.25, axis="y", which="both")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_operator(path: Path, raw_rows) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13.0, 8.0), constrained_layout=True)
    cases = sorted({str(row["case"]) for row in raw_rows})
    fields = (
        ("global_coupled_residual", "Coupled residual"),
        ("total_energy_ledger_residual", "Energy-ledger residual"),
        ("solver_final_limiter_count", "Final limiter activations"),
        ("runtime_s", "Runtime (s)"),
    )
    for axis, (field, label) in zip(axes.flat, fields, strict=True):
        for case in cases:
            rows = sorted(
                (row for row in raw_rows if row["case"] == case),
                key=lambda row: int(row["physical_frequency_groups"]),
            )
            axis.plot(
                [row["physical_frequency_groups"] for row in rows],
                [row[field] for row in rows],
                marker="o",
                label=case,
            )
        axis.set_xscale("log")
        if field != "solver_final_limiter_count":
            axis.set_yscale("log")
        axis.set_xlabel("Physical frequency groups")
        axis.set_ylabel(label)
        axis.set_title(label)
        axis.grid(alpha=0.25, which="both")
    axes[0, 0].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5a_summary.json",
        "controls": output_dir / "phase7b5a_controls.csv",
        "states": output_dir / "phase7b5a_actual_states.csv",
        "convergence": output_dir / "phase7b5a_state_convergence.csv",
        "convergence_plot": output_dir / "phase7b5a_log_p1_frequency_convergence.png",
        "operator_plot": output_dir / "phase7b5a_log_p1_operator_diagnostics.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    audit = _trajectory_velocity_audit(material, full)
    control = _moving_equilibrium_control(float(audit["maximum_velocity_beta"]))
    raw_rows, convergence, reference_values = _actual_state_convergence(
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
        control["passed"]
        and all(
            float(row["global_coupled_residual"]) < COUPLED_RESIDUAL_TARGET
            and float(row["total_energy_ledger_residual"]) < ENERGY_LEDGER_TARGET
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
    decision = {
        "log_p1_moving_equilibrium_passed": bool(control["passed"]),
        "log_p1_operator_gate_passed": operator_gate,
        "three_actual_state_frequency_gate_passed": frequency_gate,
        "minimum_passing_physical_frequency_groups": selected_groups,
        "minimum_passing_spectral_degrees_of_freedom": selected_dof,
        "efficiency_gate_passed": efficiency_gate,
        "log_p1_frequency_component_gate_passed": component_gate,
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
    _write_csv(paths["controls"], [control])
    _write_csv(paths["states"], raw_rows)
    _write_csv(paths["convergence"], convergence)
    _plot_convergence(paths["convergence_plot"], convergence, selected_groups)
    _plot_operator(paths["operator_plot"], raw_rows)
    report = {
        "phase": "7B5a",
        "classification": (
            "[A/V] conservative realizable P1 moments in y=ln(nu); "
            "[V] three prescribed-material one-cell states; "
            "[O] angular, radiation-subgrid, time and matter feedback"
        ),
        "configuration": {
            "physical_energy_range_ev": list(PHYSICAL_ENERGY_RANGE_EV),
            "log_p1_groups_per_decade": list(LOG_P1_GROUPS_PER_DECADE),
            "reference_p0_groups_per_decade": REFERENCE_P0_GROUPS_PER_DECADE,
            "reference_p0_physical_frequency_groups": 38496,
            "control_angular_order": CONTROL_ANGULAR_ORDER,
            "group_quadrature_order": GROUP_QUADRATURE_ORDER,
            "actual_frequency_target": ACTUAL_FREQUENCY_TARGET,
            "p1_group_limit": P1_GROUP_LIMIT,
            "spectral_dof_limit": SPECTRAL_DOF_LIMIT,
            "coupled_residual_target": COUPLED_RESIDUAL_TARGET,
            "energy_ledger_target": ENERGY_LEDGER_TARGET,
        },
        "log_p1_definition": {
            "coordinate": "y = ln(nu)",
            "conserved_density": "Q = nu q_nu",
            "physical_integral": "integral q_nu dnu = integral Q dy",
            "normalized_coordinate": "x = 2 (y-y_c) / Delta y",
            "reconstruction": "Q(x) = Q_bar + 3 m x",
            "first_moment": "m = Delta y^-1 integral Q x dy",
            "realizability": "3 abs(m) <= Q_bar",
            "doppler_translation": "y_0 = y + ln(D)",
            "intensity_amplitude": "Q_0 = D^4 Q",
            "emissivity_amplitude": "Q_eta,0 = D^3 Q_eta",
            "extinction_amplitude": "chi_0 = chi / D",
        },
        "control": control,
        "actual_states": raw_rows,
        "state_convergence": convergence,
        "finite_reference_values": reference_values,
        "decision": decision,
        "open_items": [
            "the 38496-group P0 comparison remains a finite reference, not continuum truth",
            "limiter activations preserve group integrals but alter unresolved slopes",
            "independent angular and radiation-subgrid convergence is not part of this gate",
            "the 2048-phase radiation orbit remains unauthorized until later gates pass",
            "temperature and H/He populations remain prescribed",
            "excited levels, cascades, Compton redistribution, and line transfer remain open",
        ],
        "figures": {
            "frequency_convergence": paths["convergence_plot"].name,
            "operator_diagnostics": paths["operator_plot"].name,
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
