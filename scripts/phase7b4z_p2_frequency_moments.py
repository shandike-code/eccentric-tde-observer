"""Phase 7B4z：组内 P2 频率矩的同成本三状态准入门。"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.mixed_frame_ale import mixed_frame_frequency_stencil
from eccentric_tde_observer.mixed_frame_ale_p2 import (
    solve_mixed_frame_ale_p2_group_step,
)
from eccentric_tde_observer.mixed_frame_frequency import (
    limit_nonnegative_frequency_group_p2,
    lorentz_ray_transform,
)
from eccentric_tde_observer.multigroup_continuum import (
    gauss_legendre_frequency_group_quadrature,
    ground_state_milne_p2_multigroup,
    group_average_from_quadrature_nodes,
    group_p1_moment_from_quadrature_nodes,
    group_p2_second_moment_from_quadrature_nodes,
)
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S, planck_nu
from eccentric_tde_observer.radiative_transfer_1d import gauss_legendre_mu_weights

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

try:
    from scripts.phase7b4s_implicit_ale_radiation import (
        _load_material_reference,
        centred_full_column_trajectory,
    )
    from scripts.phase7b4t_mixed_frame_group_gate import _trajectory_velocity_audit
    from scripts.phase7b4v_mixed_frame_ale_gate import (
        _actual_case_definitions,
        _active_slice,
        _actual_one_cell_run as _p0_actual_one_cell_run,
        _collision_physical_slice,
        _relative_component_errors,
    )
    from scripts.phase7b4x_p1_frequency_moments import (
        ACTUAL_FREQUENCY_TARGET,
        CONTROL_ANGULAR_ORDER,
        COUPLED_RESIDUAL_TARGET,
        ENERGY_LEDGER_TARGET,
        GROUP_QUADRATURE_ORDER,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        SPECTRAL_DOF_LIMIT,
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
        _actual_one_cell_run as _p0_actual_one_cell_run,
        _collision_physical_slice,
        _relative_component_errors,
    )
    from phase7b4x_p1_frequency_moments import (  # type: ignore[no-redef]
        ACTUAL_FREQUENCY_TARGET,
        CONTROL_ANGULAR_ORDER,
        COUPLED_RESIDUAL_TARGET,
        ENERGY_LEDGER_TARGET,
        GROUP_QUADRATURE_ORDER,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        SPECTRAL_DOF_LIMIT,
    )


P2_GROUPS_PER_DECADE = (32, 64, 128, 256, 341)
P2_GROUP_LIMIT = SPECTRAL_DOF_LIMIT // 3
ITERATIVE_TOLERANCE = 1.0e-10


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    fieldnames = list(rows[0])
    for row in rows[1:]:
        fieldnames.extend(name for name in row if name not in fieldnames)
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _boosted_planck_outer_p2(stencil, mu, angular_weight, beta, temperature):
    transform = lorentz_ray_transform(mu, angular_weight, beta)
    quadrature = gauss_legendre_frequency_group_quadrature(
        stencil.outer_lab_edge_hz,
        order_per_group=GROUP_QUADRATURE_ORDER,
    )
    shape = (stencil.outer_lab_group_count, mu.size, beta.size)
    mean = np.empty(shape)
    first = np.empty(shape)
    second = np.empty(shape)
    for angle in range(mu.size):
        for depth, factor in enumerate(transform.doppler_lab_to_comoving[angle]):
            node_intensity = factor**-3 * planck_nu(
                factor * quadrature.node_hz, temperature
            )
            mean[:, angle, depth] = group_average_from_quadrature_nodes(
                node_intensity, quadrature
            )
            first[:, angle, depth] = group_p1_moment_from_quadrature_nodes(
                node_intensity, quadrature
            )
            second[:, angle, depth] = group_p2_second_moment_from_quadrature_nodes(
                node_intensity, quadrature
            )
    # 中文：只缩放未解析高阶矩，严格保持每组 Planck 能量。
    return limit_nonnegative_frequency_group_p2(mean, first, second)


def _planck_material_p2(stencil, density, temperature, hydrogen, helium):
    quadrature = gauss_legendre_frequency_group_quadrature(
        stencil.comoving_collision_edge_hz,
        order_per_group=GROUP_QUADRATURE_ORDER,
    )
    node_planck = planck_nu(quadrature.node_hz, temperature)
    planck_state = limit_nonnegative_frequency_group_p2(
        group_average_from_quadrature_nodes(node_planck, quadrature)[:, None],
        group_p1_moment_from_quadrature_nodes(node_planck, quadrature)[:, None],
        group_p2_second_moment_from_quadrature_nodes(node_planck, quadrature)[:, None],
    )
    microphysics = ground_state_milne_p2_multigroup(
        density,
        temperature,
        stencil.comoving_collision_edge_hz,
        planck_state.mean_density,
        planck_state.first_moment_density,
        planck_state.second_moment_density,
        hydrogen[0],
        hydrogen[1],
        helium[0],
        helium[1],
        helium[2],
        order_per_group=GROUP_QUADRATURE_ORDER,
    )
    return planck_state, microphysics


def _actual_one_cell_run_p2(
    material: dict[str, np.ndarray],
    full: dict[str, np.ndarray],
    audit: dict[str, object],
    definition: dict[str, object],
    groups_per_decade: int,
) -> tuple[dict[str, object], dict[str, float]]:
    phase = int(definition["phase_index"])
    following = int(definition["following_phase_index"])
    depth = int(definition["full_depth_index"])
    duration = float(material["step_duration_s"][phase])
    old_edge = full["edges_cm"][phase, depth : depth + 2]
    new_edge = full["edges_cm"][following, depth : depth + 2]
    edge_velocity = (new_edge - old_edge) / duration
    beta = np.array([np.mean(edge_velocity) / LIGHT_SPEED_CM_S])
    stencil = mixed_frame_frequency_stencil(
        *PHYSICAL_ENERGY_RANGE_EV,
        groups_per_decade,
        float(audit["maximum_velocity_beta"]),
    )
    mu, angular_weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    temperature = float(full["temperature_k"][following, depth])
    density = float(full["density_g_cm3"][following, depth])
    hydrogen = full["hydrogen_fraction"][following, depth]
    helium = full["helium_fraction"][following, depth]
    outer = _boosted_planck_outer_p2(
        stencil, mu, angular_weight, beta, temperature
    )
    active = _active_slice(stencil)
    planck_state, material_state = _planck_material_p2(
        stencil, density, temperature, hydrogen, helium
    )
    continuum = material_state.continuum
    started = time.perf_counter()
    result = solve_mixed_frame_ale_p2_group_step(
        stencil,
        old_edge,
        new_edge,
        mu,
        angular_weight,
        outer.mean_density[active],
        outer.first_moment_density[active],
        outer.second_moment_density[active],
        outer.mean_density,
        outer.first_moment_density,
        outer.second_moment_density,
        continuum.true_absorption_total_per_cm,
        material_state.true_absorption_first_moment_per_cm,
        material_state.true_absorption_second_moment_per_cm,
        continuum.thermal_emissivity_total_cgs,
        material_state.thermal_emissivity_first_moment_cgs,
        material_state.thermal_emissivity_second_moment_cgs,
        continuum.electron_scattering_per_cm,
        material_state.electron_scattering_first_moment_per_cm,
        material_state.electron_scattering_second_moment_per_cm,
        beta,
        duration,
        iterative_tolerance=ITERATIVE_TOLERANCE,
        iterative_maximum_iterations=8192,
    )
    runtime = float(time.perf_counter() - started)
    physical = _collision_physical_slice(stencil)
    final_microphysics = ground_state_milne_p2_multigroup(
        density,
        temperature,
        stencil.active_lab_edge_hz,
        result.final_comoving_mean_intensity_density[physical],
        result.final_comoving_mean_first_moment_intensity_density[physical],
        result.final_comoving_mean_second_moment_intensity_density[physical],
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
        * angular_weight[None, mu < 0.0]
        * mu[None, mu < 0.0]
        * result.left_ale_face_mean_intensity[:, mu < 0.0]
    )
    right_outward = 2.0 * np.pi * np.sum(
        width[:, None]
        * angular_weight[None, mu > 0.0]
        * mu[None, mu > 0.0]
        * result.right_ale_face_mean_intensity[:, mu > 0.0]
    )
    diagnostics = {
        "radiation_energy": float(
            np.sum(width * result.final_radiation_energy_group_erg_cm2_hz)
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
    ratios = (
        outer.maximum_prelimit_negativity_ratio,
        planck_state.maximum_prelimit_negativity_ratio,
        material_state.maximum_continuum_prelimit_negativity_ratio,
        final_microphysics.maximum_continuum_prelimit_negativity_ratio,
        result.maximum_prelimit_negativity_ratio,
    )
    finite_ratios = [value for value in ratios if np.isfinite(value)]
    row = {
        **definition,
        "representation": "uniform logarithmic P2",
        "groups_per_decade": groups_per_decade,
        "resolution_parameter": groups_per_decade,
        "physical_frequency_groups": stencil.physical_group_count,
        "spectral_degrees_of_freedom": 3 * stencil.physical_group_count,
        "comoving_collision_groups": stencil.comoving_collision_group_count,
        "outer_guard_groups": stencil.outer_lab_group_count,
        "orbital_phase": float(material["orbital_phase"][following]),
        "duration_s": duration,
        "temperature_k": temperature,
        "density_g_cm3": density,
        "cell_velocity_beta": float(beta[0]),
        "maximum_optical_depth": float(
            np.max(continuum.extinction_total_per_cm * np.diff(new_edge)[0])
        ),
        "fixed_point_iterations": result.fixed_point_iterations,
        "final_fixed_point_change": result.final_fixed_point_change,
        "global_coupled_residual": result.global_scale_normalized_coupled_residual,
        "maximum_group_relative_residual": result.maximum_group_relative_coupled_residual,
        "total_energy_ledger_residual": result.total_relative_energy_ledger_residual,
        "maximum_group_relative_energy_ledger": float(
            np.max(result.relative_energy_ledger_residual_group)
        ),
        "minimum_reconstructed_intensity": result.minimum_reconstructed_intensity,
        "outer_radiation_limiter_count": outer.limited_group_count,
        "material_planck_limiter_count": planck_state.limited_group_count,
        "material_continuum_limiter_count": material_state.continuum_limited_group_count,
        "final_continuum_limiter_count": final_microphysics.continuum_limited_group_count,
        "solver_cumulative_limiter_count": result.cumulative_limiter_activation_count,
        "solver_final_limiter_count": result.final_limiter_activation_count,
        "maximum_finite_prelimit_negativity_ratio": max(finite_ratios, default=0.0),
        "zero_mean_negative_reconstruction_encountered": bool(
            len(finite_ratios) != len(ratios)
        ),
        "runtime_s": runtime,
    }
    return row, diagnostics


def _moving_equilibrium_control(maximum_beta: float) -> dict[str, object]:
    beta = np.array([0.05])
    stencil = mixed_frame_frequency_stencil(
        *PHYSICAL_ENERGY_RANGE_EV, 64, max(maximum_beta, float(beta[0]))
    )
    mu, angular_weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    transform = lorentz_ray_transform(mu, angular_weight, beta)
    value = 1.7
    outer_mean = np.broadcast_to(
        value * transform.doppler_lab_to_comoving[None, ...] ** -3.0,
        (stencil.outer_lab_group_count, mu.size, 1),
    ).copy()
    active = outer_mean[_active_slice(stencil)]
    collision_shape = (stencil.comoving_collision_group_count, 1)
    absorption = np.full(collision_shape, 0.6)
    scattering = np.full(collision_shape, 0.4)
    result = solve_mixed_frame_ale_p2_group_step(
        stencil,
        [0.0, 1.0],
        [0.005, 1.005],
        mu,
        angular_weight,
        active,
        0.0,
        0.0,
        outer_mean,
        0.0,
        0.0,
        absorption,
        0.0,
        0.0,
        value * absorption,
        0.0,
        0.0,
        scattering,
        0.0,
        0.0,
        beta,
        0.1,
        periodic_spatial_boundary=True,
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-12,
    )
    error = float(
        np.max(np.abs(result.final_lab_mean_intensity_density - active))
        / np.max(active)
    )
    return {
        "control": "P2 moving frequency-constant equilibrium",
        "physical_frequency_groups": stencil.physical_group_count,
        "spectral_degrees_of_freedom": 3 * stencil.physical_group_count,
        "equilibrium_error": error,
        "global_coupled_residual": result.global_scale_normalized_coupled_residual,
        "total_energy_ledger_residual": result.total_relative_energy_ledger_residual,
        "minimum_reconstructed_intensity": result.minimum_reconstructed_intensity,
        "final_limiter_count": result.final_limiter_activation_count,
        "passed": bool(
            error < ACTUAL_FREQUENCY_TARGET
            and result.global_scale_normalized_coupled_residual < COUPLED_RESIDUAL_TARGET
            and result.total_relative_energy_ledger_residual < ENERGY_LEDGER_TARGET
            and result.minimum_reconstructed_intensity >= 0.0
        ),
    }


def _actual_state_convergence(material, full, audit):
    definitions = _actual_case_definitions(material, full, audit)
    raw_rows: list[dict[str, object]] = []
    convergence: list[dict[str, object]] = []
    references: dict[str, dict[str, float]] = {}
    for definition in definitions:
        case = str(definition["case"])
        _, reference, _ = _p0_actual_one_cell_run(
            material,
            full,
            audit,
            definition,
            REFERENCE_P0_GROUPS_PER_DECADE,
        )
        references[case] = reference
        for groups_per_decade in P2_GROUPS_PER_DECADE:
            row, diagnostics = _actual_one_cell_run_p2(
                material, full, audit, definition, groups_per_decade
            )
            raw_rows.append(row)
            errors = _relative_component_errors(diagnostics, reference)
            convergence.append(
                {
                    "case": case,
                    "representation": "uniform logarithmic P2",
                    "groups_per_decade": groups_per_decade,
                    "physical_frequency_groups": row["physical_frequency_groups"],
                    "spectral_degrees_of_freedom": row["spectral_degrees_of_freedom"],
                    **{f"{name}_error": value for name, value in errors.items()},
                    "maximum_error": max(errors.values()),
                    "reference": False,
                }
            )
    return raw_rows, convergence, references


def _plot_convergence(path: Path, convergence, selected_groups) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.0), constrained_layout=True)
    cases = sorted({str(row["case"]) for row in convergence})
    for case in cases:
        rows = sorted(
            (row for row in convergence if row["case"] == case),
            key=lambda row: int(row["spectral_degrees_of_freedom"]),
        )
        axes[0].loglog(
            [row["spectral_degrees_of_freedom"] for row in rows],
            [row["maximum_error"] for row in rows],
            marker="o",
            label=case,
        )
    axes[0].axhline(
        ACTUAL_FREQUENCY_TARGET, color="black", linestyle=":", label="precision gate"
    )
    axes[0].axvline(
        SPECTRAL_DOF_LIMIT, color="tab:red", linestyle="--", label="DOF budget"
    )
    axes[0].set_xlabel("Spectral degrees of freedom")
    axes[0].set_ylabel("Maximum relative error")
    axes[0].set_title("P2 accuracy against the 38496-group P0 reference")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.25, which="both")

    target = selected_groups or max(
        int(row["physical_frequency_groups"]) for row in convergence
    )
    labels = ("energy", "left flux", "right flux", "H I", "He I", "He II", "heating")
    fields = (
        "radiation_energy_error",
        "left_outward_flux_error",
        "right_outward_flux_error",
        "photoionization_H_I_error",
        "photoionization_He_I_error",
        "photoionization_He_II_error",
        "heating_ledger_error",
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
            [row[field] for field in fields],
            width=width,
            label=case,
        )
    axes[1].axhline(ACTUAL_FREQUENCY_TARGET, color="black", linestyle=":")
    axes[1].set_yscale("log")
    axes[1].set_xticks(x, labels, rotation=30, ha="right")
    axes[1].set_ylabel("Relative error")
    axes[1].set_title(f"Component errors at {target} P2 groups")
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
                key=lambda row: int(row["spectral_degrees_of_freedom"]),
            )
            axis.plot(
                [row["spectral_degrees_of_freedom"] for row in rows],
                [row[field] for row in rows],
                marker="o",
                label=case,
            )
        axis.set_xscale("log")
        if field != "solver_final_limiter_count":
            axis.set_yscale("log")
        axis.set_xlabel("Spectral degrees of freedom")
        axis.set_ylabel(label)
        axis.set_title(label)
        axis.grid(alpha=0.25, which="both")
    axes[0, 0].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b4z_summary.json",
        "controls": output_dir / "phase7b4z_controls.csv",
        "states": output_dir / "phase7b4z_actual_states.csv",
        "convergence": output_dir / "phase7b4z_state_convergence.csv",
        "convergence_plot": output_dir / "phase7b4z_p2_frequency_convergence.png",
        "operator_plot": output_dir / "phase7b4z_p2_operator_diagnostics.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    audit = _trajectory_velocity_audit(material, full)
    control = _moving_equilibrium_control(float(audit["maximum_velocity_beta"]))
    raw_rows, convergence, references = _actual_state_convergence(material, full, audit)
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
    selected_dof = 3 * selected_groups if selected_groups is not None else None
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
        and selected_groups <= P2_GROUP_LIMIT
        and selected_dof is not None
        and selected_dof <= SPECTRAL_DOF_LIMIT
    )
    component_gate = bool(operator_gate and frequency_gate and efficiency_gate)
    decision = {
        "p2_moving_equilibrium_passed": bool(control["passed"]),
        "p2_operator_gate_passed": operator_gate,
        "three_actual_state_frequency_gate_passed": frequency_gate,
        "minimum_passing_physical_frequency_groups": selected_groups,
        "minimum_passing_spectral_degrees_of_freedom": selected_dof,
        "efficiency_gate_passed": efficiency_gate,
        "p2_frequency_component_gate_passed": component_gate,
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
        "phase": "7B4z",
        "classification": (
            "[A/V] conservative realizable P2 frequency moments; "
            "[V] finite three-state component gate; "
            "[O] angular, radiation-subgrid, time and matter feedback"
        ),
        "configuration": {
            "physical_energy_range_ev": list(PHYSICAL_ENERGY_RANGE_EV),
            "p2_groups_per_decade": list(P2_GROUPS_PER_DECADE),
            "reference_p0_groups_per_decade": REFERENCE_P0_GROUPS_PER_DECADE,
            "reference_p0_physical_frequency_groups": 38496,
            "control_angular_order": CONTROL_ANGULAR_ORDER,
            "group_quadrature_order": GROUP_QUADRATURE_ORDER,
            "actual_frequency_target": ACTUAL_FREQUENCY_TARGET,
            "p2_group_limit": P2_GROUP_LIMIT,
            "spectral_dof_limit": SPECTRAL_DOF_LIMIT,
            "coupled_residual_target": COUPLED_RESIDUAL_TARGET,
            "energy_ledger_target": ENERGY_LEDGER_TARGET,
        },
        "p2_definition": {
            "normalized_coordinate": "x = 2 (nu - nu_c) / Delta nu",
            "reconstruction": "q(x) = q_bar + 3 m1 x + 5 m2 P2(x)",
            "moments": "mk = Delta nu^-1 integral q Pk(x) dnu",
            "realizability": "quadratic reconstruction is non-negative on [-1,1]",
            "limiter": "preserve q_bar and scale m1,m2 by one common factor",
        },
        "control": control,
        "actual_states": raw_rows,
        "state_convergence": convergence,
        "finite_reference_values": references,
        "decision": decision,
        "open_items": [
            "the 38496-group P0 comparison remains a finite reference, not continuum truth",
            "limiter activations preserve group means but alter unresolved curvature",
            "angular and radiation-subgrid convergence is authorized only if this gate passes",
            "the 2048-phase radiation orbit remains unauthorized at this component gate",
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
