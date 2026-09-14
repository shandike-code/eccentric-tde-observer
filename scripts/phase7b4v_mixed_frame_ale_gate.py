"""Phase 7B4v：1205 组完整 Lorentz 物质源与 ALE 联立组件门。"""

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
from eccentric_tde_observer.implicit_radiative_transfer_1d import (
    solve_implicit_ale_slab_step,
)
from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil,
    solve_mixed_frame_ale_group_step,
)
from eccentric_tde_observer.mixed_frame_frequency import lorentz_ray_transform
from eccentric_tde_observer.multigroup_continuum import (
    gauss_legendre_frequency_group_quadrature,
    ground_state_milne_multigroup,
    group_average_from_quadrature_nodes,
)
from eccentric_tde_observer.radiation import (
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


PHYSICAL_ENERGY_RANGE_EV = (0.1, 5000.0)
PRODUCTION_GROUPS_PER_DECADE = 256
ACTUAL_GROUPS_PER_DECADE = (64, 128, 256, 512, 1024, 2048, 4096, 8192)
CONTROL_ANGULAR_ORDER = 8
DYNAMIC_DIFFUSION_ANGULAR_ORDERS = (4, 8, 16)
GROUP_QUADRATURE_ORDER = 16
MAXIMUM_VELOCITY_BETA = 0.008028600886554787
CONTROL_TARGET = 1.0e-3
COUPLED_RESIDUAL_TARGET = 2.0e-8
ENERGY_LEDGER_TARGET = 2.0e-8
FOUR_FORCE_TARGET = 1.0e-8
ACTUAL_FREQUENCY_TARGET = 1.0e-3
ITERATIVE_TOLERANCE = 1.0e-10
REFERENCE_GROUPS_PER_DECADE = 8192


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


def _active_slice(stencil) -> slice:
    return slice(
        stencil.active_outer_group_start,
        stencil.active_outer_group_stop,
    )


def _boosted_constant_outer(stencil, mu, weight, beta, value: float) -> np.ndarray:
    transform = lorentz_ray_transform(mu, weight, beta)
    lab = value * transform.doppler_lab_to_comoving[None, ...] ** -3.0
    return np.broadcast_to(
        lab, (stencil.outer_lab_group_count, *lab.shape[1:])
    ).copy()


def _zero_velocity_control() -> dict[str, object]:
    stencil = mixed_frame_frequency_stencil(
        *PHYSICAL_ENERGY_RANGE_EV, PRODUCTION_GROUPS_PER_DECADE, 0.0
    )
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    depth_points = 3
    frequency_points = stencil.physical_group_count
    edge = np.linspace(0.0, 1.0, depth_points + 1)
    f = np.linspace(0.0, 1.0, frequency_points)[:, None]
    d = np.linspace(0.0, 1.0, depth_points)[None, :]
    absorption = 0.3 + 0.1 * f + 0.05 * d
    scattering = 0.4 + 0.03 * d + 0.0 * f
    source = 1.2 + 0.15 * f + 0.08 * d
    emissivity = absorption * source
    initial = np.broadcast_to(
        source[:, None, :] * (1.0 + 0.04 * mu[None, :, None]),
        (frequency_points, mu.size, depth_points),
    ).copy()
    left = 0.9 + 0.02 * mu[None, :] + np.zeros((frequency_points, 1))
    right = 1.1 - 0.03 * mu[None, :] + np.zeros((frequency_points, 1))
    started = time.perf_counter()
    mixed = solve_mixed_frame_ale_group_step(
        stencil,
        edge,
        edge,
        mu,
        weight,
        initial,
        initial,
        absorption,
        emissivity,
        scattering,
        np.zeros(depth_points),
        0.2,
        left_exterior_intensity=left,
        right_exterior_intensity=right,
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-12,
    )
    stationary = solve_implicit_ale_slab_step(
        0.5 * (
            stencil.active_lab_edge_hz[:-1]
            + stencil.active_lab_edge_hz[1:]
        ),
        edge,
        edge,
        mu,
        weight,
        initial,
        absorption + scattering,
        source,
        absorption / (absorption + scattering),
        0.2,
        left_exterior_intensity=left,
        right_exterior_intensity=right,
        propagation_speed_cm_s=1.0,
        linear_solver="source_iteration",
        iterative_tolerance=2.0e-12,
    )
    scale = max(
        float(np.max(np.abs(stationary.final_intensity))),
        float(np.max(np.abs(mixed.final_lab_intensity_density))),
    )
    difference = float(
        np.max(
            np.abs(
                mixed.final_lab_intensity_density
                - stationary.final_intensity
            )
        )
        / scale
    )
    return {
        "control": "zero velocity stationary recovery",
        "physical_frequency_groups": stencil.physical_group_count,
        "angular_order": CONTROL_ANGULAR_ORDER,
        "equilibrium_or_reference_error": difference,
        "global_coupled_residual": mixed.global_scale_normalized_coupled_residual,
        "total_energy_ledger_residual": mixed.total_relative_energy_ledger_residual,
        "fixed_point_iterations": mixed.fixed_point_iterations,
        "minimum_intensity": mixed.minimum_intensity,
        "runtime_s": float(time.perf_counter() - started),
        "passed": bool(
            difference < CONTROL_TARGET
            and mixed.global_scale_normalized_coupled_residual
            < COUPLED_RESIDUAL_TARGET
            and mixed.total_relative_energy_ledger_residual
            < ENERGY_LEDGER_TARGET
        ),
    }


def _moving_equilibrium_control(*, homologous: bool) -> dict[str, object]:
    maximum_beta = 0.06 if homologous else 0.05
    stencil = mixed_frame_frequency_stencil(
        *PHYSICAL_ENERGY_RANGE_EV,
        PRODUCTION_GROUPS_PER_DECADE,
        maximum_beta,
    )
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    if homologous:
        old_edge = np.array([1.0, 2.0])
        new_edge = np.array([1.02, 2.04])
        duration = 1.0
        beta = np.array([0.03])
        value = 1.7
    else:
        old_edge = np.linspace(0.0, 2.0, 3)
        duration = 0.1
        beta = np.full(2, 0.05)
        new_edge = old_edge + beta[0] * duration
        value = 2.0
    outer = _boosted_constant_outer(stencil, mu, weight, beta, value)
    active = outer[_active_slice(stencil)]
    shape = (stencil.comoving_collision_group_count, beta.size)
    absorption = np.full(shape, 0.5 if homologous else 0.7)
    scattering = np.full(shape, 0.2 if homologous else 0.4)
    started = time.perf_counter()
    result = solve_mixed_frame_ale_group_step(
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        active,
        outer,
        absorption,
        value * absorption,
        scattering,
        beta,
        duration,
        left_exterior_intensity=active[:, :, 0],
        right_exterior_intensity=active[:, :, -1],
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-12,
    )
    scale = max(
        float(np.max(np.abs(active))),
        float(np.max(np.abs(result.final_lab_intensity_density))),
    )
    error = float(
        np.max(np.abs(result.final_lab_intensity_density - active)) / scale
    )
    label = (
        "one-cell homologous breathing equilibrium"
        if homologous
        else "rigid translation equilibrium"
    )
    return {
        "control": label,
        "physical_frequency_groups": stencil.physical_group_count,
        "angular_order": CONTROL_ANGULAR_ORDER,
        "equilibrium_or_reference_error": error,
        "global_coupled_residual": result.global_scale_normalized_coupled_residual,
        "total_energy_ledger_residual": result.total_relative_energy_ledger_residual,
        "fixed_point_iterations": result.fixed_point_iterations,
        "minimum_intensity": result.minimum_intensity,
        "runtime_s": float(time.perf_counter() - started),
        "passed": bool(
            error < CONTROL_TARGET
            and result.global_scale_normalized_coupled_residual
            < COUPLED_RESIDUAL_TARGET
            and result.total_relative_energy_ledger_residual
            < ENERGY_LEDGER_TARGET
        ),
    }


def _compact_scattering_outer(stencil, mu, weight, beta: float):
    transform = lorentz_ray_transform(mu, weight, np.array([beta]))
    doppler = transform.doppler_lab_to_comoving[:, 0]
    comoving_edge = stencil.comoving_collision_edge_hz
    energy_edge = comoving_edge * PLANCK_ERG_S / EV_ERG
    lower_index = int(np.searchsorted(energy_edge, 10.0, side="right") - 1)
    upper_index = int(np.searchsorted(energy_edge, 100.0, side="left"))
    support_lower = comoving_edge[lower_index]
    support_upper = comoving_edge[upper_index]
    comoving_angle = 1.0 + 0.6 * transform.comoving_direction_cosine[:, 0]
    outer_edge = stencil.outer_lab_edge_hz
    outer_width = np.diff(outer_edge)
    outer = np.empty((stencil.outer_lab_group_count, mu.size, 1))
    for angle, factor in enumerate(doppler):
        query_left = factor * outer_edge[:-1]
        query_right = factor * outer_edge[1:]
        # 中文：紧支撑谱的几何交叠长度保留精确零，不设显示或计算 floor。
        overlap = np.maximum(
            0.0,
            np.minimum(query_right, support_upper)
            - np.maximum(query_left, support_lower),
        )
        outer[:, angle, 0] = (
            factor**-4 * comoving_angle[angle] * overlap / outer_width
        )
    support = (comoving_edge[:-1] >= support_lower) & (
        comoving_edge[1:] <= support_upper
    )
    return outer, support, support_lower, support_upper


def dynamic_diffusion_controls() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    beta = 0.05
    scattering_depth = 40.0
    for angular_order in DYNAMIC_DIFFUSION_ANGULAR_ORDERS:
        stencil = mixed_frame_frequency_stencil(
            *PHYSICAL_ENERGY_RANGE_EV,
            PRODUCTION_GROUPS_PER_DECADE,
            beta,
        )
        mu, weight = gauss_legendre_mu_weights(angular_order)
        outer, support, support_lower, support_upper = _compact_scattering_outer(
            stencil, mu, weight, beta
        )
        active = outer[_active_slice(stencil)]
        scattering = np.zeros((stencil.comoving_collision_group_count, 1))
        scattering[support, 0] = scattering_depth
        started = time.perf_counter()
        result = solve_mixed_frame_ale_group_step(
            stencil,
            [0.0, 1.0],
            [0.0, 1.0],
            mu,
            weight,
            active,
            outer,
            0.0,
            0.0,
            scattering,
            [beta],
            1.0,
            periodic_spatial_boundary=True,
            propagation_speed_cm_s=1.0,
            iterative_tolerance=ITERATIVE_TOLERANCE,
            iterative_maximum_iterations=8192,
        )
        gamma = 1.0 / np.sqrt(1.0 - beta**2)
        expected_energy = gamma * (
            result.radiation_source_energy_comoving_erg_s_cm3
            + beta * result.radiation_source_momentum_comoving_dyn_cm3
        )
        expected_momentum = gamma * (
            result.radiation_source_momentum_comoving_dyn_cm3
            + beta * result.radiation_source_energy_comoving_erg_s_cm3
        )
        energy_scale = max(
            float(np.max(np.abs(result.radiation_source_energy_lab_erg_s_cm3))),
            float(np.max(np.abs(expected_energy))),
        )
        momentum_scale = max(
            float(
                np.max(np.abs(result.radiation_source_momentum_lab_dyn_cm3))
            ),
            float(np.max(np.abs(expected_momentum))),
        )
        energy_error = float(
            np.max(np.abs(result.four_force_energy_residual_erg_s_cm3))
            / energy_scale
        )
        momentum_error = float(
            np.max(np.abs(result.four_force_momentum_residual_dyn_cm3))
            / momentum_scale
        )
        rows.append(
            {
                "angular_order": angular_order,
                "physical_frequency_groups": stencil.physical_group_count,
                "velocity_beta": beta,
                "scattering_optical_depth": scattering_depth,
                "beta_tau": beta * scattering_depth,
                "support_minimum_energy_ev": support_lower
                * PLANCK_ERG_S
                / EV_ERG,
                "support_maximum_energy_ev": support_upper
                * PLANCK_ERG_S
                / EV_ERG,
                "four_force_energy_relative_error": energy_error,
                "four_force_momentum_relative_error": momentum_error,
                "global_coupled_residual": result.global_scale_normalized_coupled_residual,
                "total_energy_ledger_residual": result.total_relative_energy_ledger_residual,
                "fixed_point_iterations": result.fixed_point_iterations,
                "minimum_intensity": result.minimum_intensity,
                "runtime_s": float(time.perf_counter() - started),
                "passed": bool(
                    beta * scattering_depth > 1.0
                    and energy_error < FOUR_FORCE_TARGET
                    and momentum_error < FOUR_FORCE_TARGET
                    and result.global_scale_normalized_coupled_residual
                    < COUPLED_RESIDUAL_TARGET
                    and result.total_relative_energy_ledger_residual
                    < ENERGY_LEDGER_TARGET
                    and result.minimum_intensity >= 0.0
                ),
            }
        )
    return rows


def analytic_control_rows() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    controls = [
        _zero_velocity_control(),
        _moving_equilibrium_control(homologous=False),
        _moving_equilibrium_control(homologous=True),
    ]
    return controls, dynamic_diffusion_controls()


def _actual_case_definitions(
    material: dict[str, np.ndarray],
    full: dict[str, np.ndarray],
    audit: dict[str, object],
) -> list[dict[str, object]]:
    phase_points, depth_points = full["density_g_cm3"].shape
    stress_phase = int(audit["stress_phase_index"])
    stress_following = (stress_phase + 1) % phase_points
    stress_width_change = np.abs(
        full["cell_width_cm"][stress_following]
        / full["cell_width_cm"][stress_phase]
        - 1.0
    )
    return [
        {
            "case": "cold coefficient surface",
            "phase_index": 1024,
            "following_phase_index": 1025,
            "full_depth_index": 0,
        },
        {
            "case": "maximum cell speed",
            "phase_index": int(audit["maximum_cell_velocity_phase_index"]),
            "following_phase_index": (
                int(audit["maximum_cell_velocity_phase_index"]) + 1
            )
            % phase_points,
            "full_depth_index": int(audit["maximum_cell_velocity_depth_index"]),
        },
        {
            "case": "maximum width change",
            "phase_index": stress_phase,
            "following_phase_index": stress_following,
            "full_depth_index": int(np.argmax(stress_width_change)),
        },
    ]


def _boosted_planck_outer(stencil, mu, weight, beta: np.ndarray, temperature: float):
    transform = lorentz_ray_transform(mu, weight, beta)
    quadrature = gauss_legendre_frequency_group_quadrature(
        stencil.outer_lab_edge_hz,
        order_per_group=GROUP_QUADRATURE_ORDER,
    )
    outer = np.empty((stencil.outer_lab_group_count, mu.size, beta.size))
    for angle in range(mu.size):
        for depth, factor in enumerate(
            transform.doppler_lab_to_comoving[angle]
        ):
            node_intensity = factor**-3 * planck_nu(
                factor * quadrature.node_hz, temperature
            )
            outer[:, angle, depth] = group_average_from_quadrature_nodes(
                node_intensity, quadrature
            )
    return outer


def _collision_physical_slice(stencil) -> slice:
    edge = stencil.comoving_collision_edge_hz
    active = (edge[:-1] >= stencil.active_lab_edge_hz[0]) & (
        edge[1:] <= stencil.active_lab_edge_hz[-1]
    )
    index = np.flatnonzero(active)
    if index.size != stencil.physical_group_count or np.any(np.diff(index) != 1):
        raise ArithmeticError("comoving physical collision groups lost contiguity")
    result = slice(int(index[0]), int(index[-1] + 1))
    if not np.array_equal(
        edge[result.start : result.stop + 1], stencil.active_lab_edge_hz
    ):
        raise ArithmeticError("lab and comoving physical group edges diverged")
    return result


def _actual_one_cell_run(
    material: dict[str, np.ndarray],
    full: dict[str, np.ndarray],
    audit: dict[str, object],
    definition: dict[str, object],
    groups_per_decade: int,
    *,
    material_velocity_beta_override: float | None = None,
    rigid_mesh_control: bool = False,
    include_true_absorption_emission: bool = True,
    include_scattering: bool = True,
    apply_intensity_lorentz: bool = True,
    apply_extinction_lorentz: bool = True,
    apply_emissivity_lorentz: bool = True,
    iterative_tolerance_override: float | None = None,
    iteration_observer=None,
) -> tuple[dict[str, object], dict[str, float], dict[str, np.ndarray]]:
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
    stencil = mixed_frame_frequency_stencil(
        *PHYSICAL_ENERGY_RANGE_EV,
        groups_per_decade,
        float(audit["maximum_velocity_beta"]),
    )
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    temperature = float(full["temperature_k"][following, depth])
    density = float(full["density_g_cm3"][following, depth])
    hydrogen = full["hydrogen_fraction"][following, depth]
    helium = full["helium_fraction"][following, depth]
    outer_beta = beta if apply_intensity_lorentz else np.zeros_like(beta)
    outer = _boosted_planck_outer(
        stencil, mu, weight, outer_beta, temperature
    )
    active = outer[_active_slice(stencil)]
    comoving_quadrature = gauss_legendre_frequency_group_quadrature(
        stencil.comoving_collision_edge_hz,
        order_per_group=GROUP_QUADRATURE_ORDER,
    )
    group_planck = group_average_from_quadrature_nodes(
        planck_nu(comoving_quadrature.node_hz, temperature),
        comoving_quadrature,
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
        (
            continuum.true_absorption_total_per_cm
            if include_true_absorption_emission
            else np.zeros_like(continuum.true_absorption_total_per_cm)
        ),
        (
            continuum.thermal_emissivity_total_cgs
            if include_true_absorption_emission
            else np.zeros_like(continuum.thermal_emissivity_total_cgs)
        ),
        (
            continuum.electron_scattering_per_cm
            if include_scattering
            else np.zeros_like(continuum.electron_scattering_per_cm)
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
    physical = _collision_physical_slice(stencil)
    physical_mean = result.final_comoving_mean_intensity_density[physical]
    final_microphysics = ground_state_milne_multigroup(
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
    row = {
        **definition,
        "groups_per_decade": groups_per_decade,
        "physical_frequency_groups": stencil.physical_group_count,
        "comoving_collision_groups": stencil.comoving_collision_group_count,
        "outer_guard_groups": stencil.outer_lab_group_count,
        "orbital_phase": float(material["orbital_phase"][following]),
        "duration_s": duration,
        "temperature_k": temperature,
        "density_g_cm3": density,
        "cell_velocity_beta": float(beta[0]),
        "left_edge_velocity_beta": float(edge_velocity[0] / LIGHT_SPEED_CM_S),
        "right_edge_velocity_beta": float(edge_velocity[1] / LIGHT_SPEED_CM_S),
        "maximum_optical_depth": float(
            np.max(continuum.extinction_total_per_cm * np.diff(new_edge)[0])
        ),
        "fixed_point_iterations": result.fixed_point_iterations,
        "fixed_point_converged": result.fixed_point_converged,
        "final_fixed_point_change": result.final_fixed_point_change,
        "global_coupled_residual": result.global_scale_normalized_coupled_residual,
        "maximum_group_relative_residual": result.maximum_group_relative_coupled_residual,
        "total_energy_ledger_residual": result.total_relative_energy_ledger_residual,
        "maximum_group_relative_energy_ledger": float(
            np.max(result.relative_energy_ledger_residual_group)
        ),
        "minimum_intensity": result.minimum_intensity,
        "runtime_s": float(time.perf_counter() - started),
    }
    arrays = {
        "photon_energy_ev": np.sqrt(
            stencil.active_lab_edge_hz[:-1] * stencil.active_lab_edge_hz[1:]
        )
        * PLANCK_ERG_S
        / EV_ERG,
        "group_relative_residual": result.relative_coupled_residual_group,
        "group_energy_ledger_residual": result.relative_energy_ledger_residual_group,
        "mean_intensity": result.final_lab_mean_intensity_density[:, 0],
        # 中文：保留共动末态谱，供后续原子率的有符号频段误差定位。
        "physical_group_edge_hz": np.array(
            stencil.active_lab_edge_hz, copy=True
        ),
        "final_comoving_mean_intensity": np.array(
            physical_mean[:, 0], copy=True
        ),
    }
    return row, diagnostics, arrays


def _relative_component_errors(
    candidate: dict[str, float], reference: dict[str, float]
) -> dict[str, float]:
    errors: dict[str, float] = {}
    for name in (
        "radiation_energy",
        "left_outward_flux",
        "right_outward_flux",
        "photoionization_H_I",
        "photoionization_He_I",
        "photoionization_He_II",
        "total_recombination_H_II",
        "total_recombination_He_II",
        "total_recombination_He_III",
    ):
        difference = abs(candidate[name] - reference[name])
        scale = abs(reference[name])
        errors[name] = difference / scale if scale > 0.0 else difference
    heating_difference = abs(
        candidate["radiative_heating"] - reference["radiative_heating"]
    )
    heating_scale = max(
        abs(candidate["absorbed_power"]),
        abs(candidate["emitted_power"]),
        abs(reference["absorbed_power"]),
        abs(reference["emitted_power"]),
    )
    errors["heating_ledger"] = (
        heating_difference / heating_scale
        if heating_scale > 0.0
        else heating_difference
    )
    return errors


def actual_state_convergence(
    material: dict[str, np.ndarray],
    full: dict[str, np.ndarray],
    audit: dict[str, object],
):
    definitions = _actual_case_definitions(material, full, audit)
    raw_rows: list[dict[str, object]] = []
    values: dict[tuple[str, int], dict[str, float]] = {}
    diagnostic_arrays: dict[str, np.ndarray] = {}
    for definition in definitions:
        for groups_per_decade in ACTUAL_GROUPS_PER_DECADE:
            row, diagnostics, arrays = _actual_one_cell_run(
                material,
                full,
                audit,
                definition,
                groups_per_decade,
            )
            raw_rows.append(row)
            values[(str(definition["case"]), groups_per_decade)] = diagnostics
            if (
                definition["case"] == "cold coefficient surface"
                and groups_per_decade == PRODUCTION_GROUPS_PER_DECADE
            ):
                diagnostic_arrays = arrays
    convergence_rows: list[dict[str, object]] = []
    for definition in definitions:
        case = str(definition["case"])
        reference = values[(case, REFERENCE_GROUPS_PER_DECADE)]
        for groups_per_decade in ACTUAL_GROUPS_PER_DECADE:
            candidate = values[(case, groups_per_decade)]
            errors = _relative_component_errors(candidate, reference)
            convergence_rows.append(
                {
                    "case": case,
                    "groups_per_decade": groups_per_decade,
                    "physical_frequency_groups": next(
                        int(row["physical_frequency_groups"])
                        for row in raw_rows
                        if row["case"] == case
                        and row["groups_per_decade"] == groups_per_decade
                    ),
                    **{f"{name}_error": value for name, value in errors.items()},
                    "maximum_error": max(errors.values()),
                    "reference": groups_per_decade
                    == REFERENCE_GROUPS_PER_DECADE,
                }
            )
    return raw_rows, convergence_rows, diagnostic_arrays


def _plot_controls(
    path: Path,
    controls: list[dict[str, object]],
    diffusion: list[dict[str, object]],
    cold_row: dict[str, object],
    cold_arrays: dict[str, np.ndarray],
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14.0, 9.0), constrained_layout=True)
    labels = [
        "zero velocity",
        "rigid translation",
        "homologous breathing",
    ]
    equilibrium = np.asarray(
        [row["equilibrium_or_reference_error"] for row in controls], dtype=float
    )
    axes[0, 0].bar(labels, equilibrium)
    axes[0, 0].axhline(CONTROL_TARGET, color="black", linestyle=":", label="gate")
    axes[0, 0].set_yscale("log")
    axes[0, 0].set_ylabel("Scale-normalized error")
    axes[0, 0].set_title("Manufactured mixed-frame equilibria")
    axes[0, 0].tick_params(axis="x", rotation=18)
    axes[0, 0].legend()

    order = np.asarray([row["angular_order"] for row in diffusion], dtype=int)
    axes[0, 1].semilogy(
        order,
        [row["four_force_energy_relative_error"] for row in diffusion],
        marker="o",
        label="energy four-force",
    )
    axes[0, 1].semilogy(
        order,
        [row["four_force_momentum_relative_error"] for row in diffusion],
        marker="s",
        label="momentum four-force",
    )
    axes[0, 1].axhline(FOUR_FORCE_TARGET, color="black", linestyle=":", label="gate")
    axes[0, 1].set_xlabel("Angular order")
    axes[0, 1].set_ylabel("Relative covariance error")
    axes[0, 1].set_title("Dynamic-diffusion four-force covariance")
    axes[0, 1].legend()

    gate_labels = ["coupled residual", "energy ledger", "fixed-point change"]
    gate_values = [
        float(cold_row["global_coupled_residual"]),
        float(cold_row["total_energy_ledger_residual"]),
        float(cold_row["final_fixed_point_change"]),
    ]
    axes[1, 0].bar(gate_labels, gate_values, color="tab:blue")
    axes[1, 0].axhline(
        COUPLED_RESIDUAL_TARGET, color="black", linestyle=":", label="component gate"
    )
    axes[1, 0].set_yscale("log")
    axes[1, 0].set_ylabel("Scale-normalized residual")
    axes[1, 0].set_title("Actual cold-surface 1205-group step")
    axes[1, 0].tick_params(axis="x", rotation=18)
    axes[1, 0].legend()

    energy = cold_arrays["photon_energy_ev"]
    axes[1, 1].loglog(
        energy,
        cold_arrays["group_relative_residual"],
        label="per-group equation residual",
    )
    axes[1, 1].loglog(
        energy,
        cold_arrays["group_energy_ledger_residual"],
        label="per-group energy ledger",
    )
    axes[1, 1].axhline(
        COUPLED_RESIDUAL_TARGET, color="black", linestyle=":", label="global gate"
    )
    axes[1, 1].set_xlabel("Photon energy (eV)")
    axes[1, 1].set_ylabel("Relative residual")
    axes[1, 1].set_title("Unfloored high-energy residual audit")
    axes[1, 1].legend()
    fig.suptitle("Phase 7B4v full Lorentz material source plus ALE gate")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_actual_convergence(
    path: Path,
    raw_rows: list[dict[str, object]],
    convergence_rows: list[dict[str, object]],
) -> None:
    cases = list(dict.fromkeys(str(row["case"]) for row in convergence_rows))
    components = [
        "radiation_energy_error",
        "photoionization_H_I_error",
        "photoionization_He_I_error",
        "photoionization_He_II_error",
        "heating_ledger_error",
    ]
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8), constrained_layout=True)
    for case in cases:
        selected = [
            row
            for row in convergence_rows
            if row["case"] == case and not row["reference"]
        ]
        axes[0].loglog(
            [row["physical_frequency_groups"] for row in selected],
            [row["maximum_error"] for row in selected],
            marker="o",
            label=case,
        )
    axes[0].axhline(ACTUAL_FREQUENCY_TARGET, color="black", linestyle=":", label="gate")
    axes[0].set_xlabel("Physical frequency groups")
    reference_groups = max(
        int(row["physical_frequency_groups"])
        for row in convergence_rows
        if row["reference"]
    )
    axes[0].set_ylabel(
        f"Maximum error versus {reference_groups}-group reference"
    )
    axes[0].set_title("Actual one-cell frequency convergence")
    axes[0].legend(fontsize=8)

    production_rows = [
        row
        for row in convergence_rows
        if row["groups_per_decade"] == PRODUCTION_GROUPS_PER_DECADE
    ]
    image = axes[1].imshow(
        np.asarray(
            [[row[name] for name in components] for row in production_rows],
            dtype=float,
        ),
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
    axes[1].set_title("1205-group component errors")
    fig.colorbar(image, ax=axes[1], label="Relative error")

    for case in cases:
        selected = [row for row in raw_rows if row["case"] == case]
        axes[2].plot(
            [row["physical_frequency_groups"] for row in selected],
            [row["runtime_s"] for row in selected],
            marker="o",
            label=case,
        )
    axes[2].set_xscale("log")
    axes[2].set_yscale("log")
    axes[2].set_xlabel("Physical frequency groups")
    axes[2].set_ylabel("Runtime (s)")
    axes[2].set_title("One-cell component cost")
    axes[2].legend(fontsize=8)
    fig.suptitle("Phase 7B4v actual H/He mixed-frame ALE convergence")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b4v_summary.json",
        "controls": output_dir / "phase7b4v_controls.csv",
        "diffusion": output_dir / "phase7b4v_dynamic_diffusion.csv",
        "actual": output_dir / "phase7b4v_actual_states.csv",
        "convergence": output_dir / "phase7b4v_actual_state_convergence.csv",
        "diagnostics": output_dir / "phase7b4v_diagnostics.npz",
        "control_plot": output_dir / "phase7b4v_mixed_frame_ale_controls.png",
        "convergence_plot": output_dir / "phase7b4v_actual_state_convergence.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    controls, diffusion = analytic_control_rows()
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    audit = _trajectory_velocity_audit(material, full)
    actual_rows, convergence_rows, diagnostic_arrays = actual_state_convergence(
        material, full, audit
    )
    _write_csv(paths["controls"], controls)
    _write_csv(paths["diffusion"], diffusion)
    _write_csv(paths["actual"], actual_rows)
    _write_csv(paths["convergence"], convergence_rows)
    _save_npz_atomic(paths["diagnostics"], **diagnostic_arrays)
    cold_row = next(
        row
        for row in actual_rows
        if row["case"] == "cold coefficient surface"
        and row["groups_per_decade"] == PRODUCTION_GROUPS_PER_DECADE
    )
    _plot_controls(
        paths["control_plot"], controls, diffusion, cold_row, diagnostic_arrays
    )
    _plot_actual_convergence(
        paths["convergence_plot"], actual_rows, convergence_rows
    )

    production_errors = [
        float(row["maximum_error"])
        for row in convergence_rows
        if row["groups_per_decade"] == PRODUCTION_GROUPS_PER_DECADE
    ]
    maximum_actual_error = max(production_errors)
    operator_gate = bool(
        all(bool(row["passed"]) for row in controls)
        and all(bool(row["passed"]) for row in diffusion)
        and all(
            float(row["global_coupled_residual"])
            < COUPLED_RESIDUAL_TARGET
            and float(row["total_energy_ledger_residual"])
            < ENERGY_LEDGER_TARGET
            and float(row["minimum_intensity"]) >= 0.0
            for row in actual_rows
            if row["groups_per_decade"] == PRODUCTION_GROUPS_PER_DECADE
        )
    )
    candidate_groups = sorted(
        {
            int(row["physical_frequency_groups"])
            for row in convergence_rows
            if not row["reference"]
        }
    )
    passing_groups = [
        groups
        for groups in candidate_groups
        if max(
            float(row["maximum_error"])
            for row in convergence_rows
            if int(row["physical_frequency_groups"]) == groups
        )
        < ACTUAL_FREQUENCY_TARGET
    ]
    minimum_passing_groups = min(passing_groups) if passing_groups else None
    component_gate = bool(
        operator_gate and maximum_actual_error < ACTUAL_FREQUENCY_TARGET
    )
    decision = {
        "zero_velocity_recovery_passed": bool(controls[0]["passed"]),
        "rigid_translation_passed": bool(controls[1]["passed"]),
        "homologous_breathing_passed": bool(controls[2]["passed"]),
        "dynamic_diffusion_four_force_passed": bool(
            all(bool(row["passed"]) for row in diffusion)
        ),
        "full_lorentz_ale_operator_gate_passed": operator_gate,
        "actual_1205_vs_38496_frequency_gate_passed": bool(
            maximum_actual_error < ACTUAL_FREQUENCY_TARGET
        ),
        "minimum_one_cell_passing_physical_frequency_groups": (
            minimum_passing_groups
        ),
        "1205_group_mixed_frame_ale_component_gate_passed": component_gate,
        "mixed_frame_ale_component_gate_passed": component_gate,
        "selected_dynamic_physical_frequency_groups": None,
        "frequency_representation_refinement_required": not component_gate,
        "angular_radiation_subgrid_time_gate_authorized": component_gate,
        "full_dynamic_orbit_authorized": False,
        "matter_temperature_population_feedback_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }
    report = {
        "phase": "7B4v",
        "classification": (
            "[V] full-Lorentz prescribed-material collision source in the ALE residual; "
            "[O] angular/radiation-subgrid/time orbit and matter feedback"
        ),
        "configuration": {
            "physical_energy_range_ev": list(PHYSICAL_ENERGY_RANGE_EV),
            "production_groups_per_decade": PRODUCTION_GROUPS_PER_DECADE,
            "production_physical_frequency_groups": 1205,
            "production_comoving_collision_groups": 1207,
            "production_outer_guard_groups": 1209,
            "control_angular_order": CONTROL_ANGULAR_ORDER,
            "dynamic_diffusion_angular_orders": list(
                DYNAMIC_DIFFUSION_ANGULAR_ORDERS
            ),
            "group_quadrature_order": GROUP_QUADRATURE_ORDER,
            "actual_frequency_candidates_groups_per_decade": list(
                ACTUAL_GROUPS_PER_DECADE
            ),
            "actual_frequency_reference_groups_per_decade": (
                REFERENCE_GROUPS_PER_DECADE
            ),
            "control_target": CONTROL_TARGET,
            "coupled_residual_target": COUPLED_RESIDUAL_TARGET,
            "energy_ledger_target": ENERGY_LEDGER_TARGET,
            "four_force_target": FOUR_FORCE_TARGET,
            "actual_frequency_target": ACTUAL_FREQUENCY_TARGET,
        },
        "controls": controls,
        "dynamic_diffusion": diffusion,
        "actual_states": actual_rows,
        "actual_state_convergence": convergence_rows,
        "maximum_1205_vs_38496_actual_error": maximum_actual_error,
        "decision": decision,
        "open_items": [
            "1205 piecewise-constant groups fail the actual dynamic photoionization-rate gate",
            "the 19249-group one-cell pass is only relative to a finite 38496-group reference and is not a production selection",
            "the S16/S24 angular and 16/32 radiation-subcell gates are not yet restored",
            "the 2048-phase full radiation orbit has not been run",
            "guard-band intensities remain prescribed in this component gate",
            "temperature and H/He populations do not yet respond to the dynamic radiation field",
            "excited levels, cascades, Compton redistribution, and line transfer remain open",
        ],
        "figures": {
            "mixed_frame_ale_controls": paths["control_plot"].name,
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
