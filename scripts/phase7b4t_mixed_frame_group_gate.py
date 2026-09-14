"""Phase 7B4t：完整 Lorentz 频率组门与正性隐式迭代压力测试。"""

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
from eccentric_tde_observer.implicit_radiative_transfer_1d import (
    solve_implicit_ale_slab_step,
)
from eccentric_tde_observer.mixed_frame_frequency import (
    comoving_group_radiation,
    lorentz_ray_transform,
    lorentz_remap_group_intensity,
    threshold_log_frequency_groups,
)
from eccentric_tde_observer.radiation import (
    LIGHT_SPEED_CM_S,
    PLANCK_ERG_S,
    planck_nu,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_half_range_mu_weights,
    gauss_legendre_mu_weights,
)

from phase7b4q_threshold_quadrature import _quadrature
from phase7b4s_implicit_ale_radiation import (
    _load_material_reference,
    centred_full_column_trajectory,
)


PHYSICAL_ENERGY_RANGE_EV = (0.1, 5000.0)
GROUPS_PER_DECADE = (8, 16, 32, 64)
POWER_LAW_INDEX = 1.3
ANGULAR_ORDERS = (4, 8, 16, 24)
PRODUCTION_ANGULAR_ORDER = 16
SOLVER_TOLERANCE = 1.0e-11
CONTROL_TOLERANCE = 1.0e-10
SOLVER_COMPARISON_TOLERANCE = 1.0e-9
ENERGY_LEDGER_TOLERANCE = 2.0e-8


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


def _power_law_group_average(
    edge_hz: np.ndarray, exponent: float, reference_hz: float
) -> np.ndarray:
    left = edge_hz[:-1] / reference_hz
    right = edge_hz[1:] / reference_hz
    integral = reference_hz * (
        right ** (exponent + 1.0) - left ** (exponent + 1.0)
    ) / (exponent + 1.0)
    return integral / np.diff(edge_hz)


def _physical_edges(grid) -> np.ndarray:
    index = np.flatnonzero(grid.physical_group_mask)
    if index.size == 0 or np.any(np.diff(index) != 1):
        raise ArithmeticError("physical frequency groups are not contiguous")
    return grid.edge_hz[index[0] : index[-1] + 2]


def _trajectory_velocity_audit(
    material: dict[str, np.ndarray], full: dict[str, np.ndarray]
) -> dict[str, object]:
    following_edges = np.roll(full["edges_cm"], -1, axis=0)
    edge_velocity = (
        following_edges - full["edges_cm"]
    ) / material["step_duration_s"][:, None]
    cell_velocity = 0.5 * (edge_velocity[:, :-1] + edge_velocity[:, 1:])
    width_change = np.max(
        np.abs(
            np.roll(full["cell_width_cm"], -1, axis=0)
            / full["cell_width_cm"]
            - 1.0
        ),
        axis=1,
    )
    stress_phase = int(np.argmax(width_change))
    maximum_cell_index = np.unravel_index(
        int(np.argmax(np.abs(cell_velocity))), cell_velocity.shape
    )
    maximum_edge_index = np.unravel_index(
        int(np.argmax(np.abs(edge_velocity))), edge_velocity.shape
    )
    return {
        "edge_velocity_cm_s": edge_velocity,
        "cell_velocity_cm_s": cell_velocity,
        "maximum_velocity_beta": float(
            np.max(np.abs(edge_velocity)) / LIGHT_SPEED_CM_S
        ),
        "maximum_edge_velocity_beta": float(
            np.max(np.abs(edge_velocity)) / LIGHT_SPEED_CM_S
        ),
        "maximum_cell_velocity_beta": float(
            np.max(np.abs(cell_velocity)) / LIGHT_SPEED_CM_S
        ),
        "maximum_velocity_phase_index": int(maximum_edge_index[0]),
        "maximum_velocity_depth_index": int(maximum_edge_index[1]),
        "maximum_cell_velocity_phase_index": int(maximum_cell_index[0]),
        "maximum_cell_velocity_depth_index": int(maximum_cell_index[1]),
        "stress_phase_index": stress_phase,
        "stress_following_phase_index": (stress_phase + 1) % cell_velocity.shape[0],
        "stress_orbital_phase": float(material["orbital_phase"][stress_phase]),
        "stress_step_duration_s": float(material["step_duration_s"][stress_phase]),
        "stress_maximum_width_change": float(width_change[stress_phase]),
    }


def angular_lorentz_controls(maximum_beta: float) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for beta_label, beta in (
        ("ZO maximum", maximum_beta),
        ("stress beta=0.17", 0.17),
    ):
        gamma2 = 1.0 / (1.0 - beta**2)
        exact = np.array(
            (
                gamma2 * (1.0 + beta**2 / 3.0),
                4.0 * gamma2 * beta / 3.0,
                gamma2 * (1.0 / 3.0 + beta**2),
            )
        )
        for order in ANGULAR_ORDERS:
            mu, weight = gauss_legendre_mu_weights(order)
            transform = lorentz_ray_transform(mu, weight, beta)
            doppler = transform.doppler_lab_to_comoving
            lab = doppler**-4
            numerical = np.array(
                (
                    0.5 * np.sum(weight * lab),
                    0.5 * np.sum(weight * mu * lab),
                    0.5 * np.sum(weight * mu**2 * lab),
                )
            )
            relative = np.abs(numerical - exact) / np.abs(exact)
            rows.append(
                {
                    "control": beta_label,
                    "velocity_beta": beta,
                    "angular_order": order,
                    "energy_moment_relative_error": float(relative[0]),
                    "flux_moment_relative_error": float(relative[1]),
                    "pressure_moment_relative_error": float(relative[2]),
                    "angular_measure_relative_error": float(
                        transform.angular_measure_relative_error
                    ),
                    "maximum_relative_error": float(
                        max(np.max(relative), transform.angular_measure_relative_error)
                    ),
                }
            )
    return rows


def frequency_group_controls(maximum_beta: float) -> list[dict[str, object]]:
    gamma = 1.0 / np.sqrt(1.0 - maximum_beta**2)
    doppler = np.array(
        (gamma * (1.0 - maximum_beta), gamma * (1.0 + maximum_beta))
    )
    reference_hz = 1.0e15
    rows: list[dict[str, object]] = []
    for groups_per_decade in GROUPS_PER_DECADE:
        grid = threshold_log_frequency_groups(
            *PHYSICAL_ENERGY_RANGE_EV,
            groups_per_decade,
            maximum_velocity_beta=maximum_beta,
            guard_transform_count=2,
        )
        target_edge = _physical_edges(grid)
        source_average = _power_law_group_average(
            grid.edge_hz, POWER_LAW_INDEX, reference_hz
        )
        source = np.broadcast_to(
            source_average[:, None], (source_average.size, doppler.size)
        ).copy()
        remapped = lorentz_remap_group_intensity(
            source,
            grid.edge_hz,
            target_edge,
            doppler,
            direction="lab_to_comoving",
        )
        target_average = _power_law_group_average(
            target_edge, POWER_LAW_INDEX, reference_hz
        )
        exact = (
            target_average[:, None]
            * doppler[None, :] ** (3.0 - POWER_LAW_INDEX)
        )
        relative = np.abs(remapped - exact) / exact
        integrated_numerical = np.sum(
            remapped * np.diff(target_edge)[:, None], axis=0
        )
        integrated_exact = np.sum(
            exact * np.diff(target_edge)[:, None], axis=0
        )
        integrated_error = np.abs(integrated_numerical - integrated_exact) / integrated_exact
        rows.append(
            {
                "groups_per_decade": groups_per_decade,
                "total_extended_groups": int(grid.centre_hz.size),
                "physical_groups": int(np.count_nonzero(grid.physical_group_mask)),
                "minimum_doppler": float(np.min(doppler)),
                "maximum_doppler": float(np.max(doppler)),
                "maximum_pointwise_relative_error": float(np.max(relative)),
                "maximum_integrated_relative_error": float(np.max(integrated_error)),
                "minimum_guard_energy_ev": grid.extended_minimum_energy_ev,
                "maximum_guard_energy_ev": grid.extended_maximum_energy_ev,
            }
        )
    return rows


def actual_breathing_frame_control(
    material: dict[str, np.ndarray],
    full: dict[str, np.ndarray],
    audit: dict[str, object],
    groups_per_decade: int,
) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    phase = int(audit["stress_phase_index"])
    following = int(audit["stress_following_phase_index"])
    beta = np.asarray(audit["cell_velocity_cm_s"])[phase] / LIGHT_SPEED_CM_S
    maximum_beta = float(audit["maximum_velocity_beta"])
    mu, weight = gauss_legendre_mu_weights(PRODUCTION_ANGULAR_ORDER)
    transform = lorentz_ray_transform(mu, weight, beta)
    grid = threshold_log_frequency_groups(
        *PHYSICAL_ENERGY_RANGE_EV,
        groups_per_decade,
        maximum_velocity_beta=maximum_beta,
        guard_transform_count=2,
    )
    target_edge = _physical_edges(grid)
    reference_hz = 1.0e15
    source_average = _power_law_group_average(
        grid.edge_hz, POWER_LAW_INDEX, reference_hz
    )
    # 中文：构造一个在每个局域共动系中各向同性的解析幂律场，再反推实验室强度。
    lab = (
        source_average[:, None, None]
        * transform.doppler_lab_to_comoving[None, :, :] ** (POWER_LAW_INDEX - 3.0)
    )
    recovered = comoving_group_radiation(
        lab,
        grid.edge_hz,
        target_edge,
        mu,
        weight,
        beta,
    )
    target_average = _power_law_group_average(
        target_edge, POWER_LAW_INDEX, reference_hz
    )
    exact = target_average[:, None] * recovered.comoving_angular_measure[None, :]
    relative = np.abs(recovered.mean_intensity_density - exact) / exact
    metrics = {
        "phase_index": phase,
        "following_phase_index": following,
        "maximum_cell_velocity_beta": float(np.max(np.abs(beta))),
        "minimum_cell_velocity_beta": float(np.min(beta)),
        "maximum_cell_velocity_signed_beta": float(np.max(beta)),
        "angular_order": PRODUCTION_ANGULAR_ORDER,
        "frequency_groups_per_decade": groups_per_decade,
        "physical_frequency_groups": int(target_edge.size - 1),
        "maximum_comoving_mean_relative_error": float(np.max(relative)),
        "maximum_angular_measure_relative_error": float(
            np.max(np.abs(recovered.comoving_angular_measure - 1.0))
        ),
    }
    arrays = {
        "stress_cell_beta": beta,
        "stress_depth_centre_cm": 0.5
        * (full["edges_cm"][following, :-1] + full["edges_cm"][following, 1:]),
        "physical_group_energy_ev": np.sqrt(target_edge[:-1] * target_edge[1:])
        * PLANCK_ERG_S
        / EV_ERG,
        "maximum_relative_error_by_group": np.max(relative, axis=1),
    }
    return metrics, arrays


def _stress_continuum(
    material: dict[str, np.ndarray],
    full: dict[str, np.ndarray],
    audit: dict[str, object],
):
    phase = int(audit["stress_phase_index"])
    following = int(audit["stress_following_phase_index"])
    quadrature = _quadrature(2)
    frequency = quadrature.frequency_hz
    continuum = ground_state_milne_continuum(
        full["density_g_cm3"][following],
        full["temperature_k"][following],
        frequency,
        full["hydrogen_fraction"][following, :, 0],
        full["hydrogen_fraction"][following, :, 1],
        full["helium_fraction"][following, :, 0],
        full["helium_fraction"][following, :, 1],
        full["helium_fraction"][following, :, 2],
        include_electron_scattering=True,
    )
    return phase, following, quadrature, continuum


def dynamic_diffusion_audit(
    material: dict[str, np.ndarray],
    full: dict[str, np.ndarray],
    audit: dict[str, object],
) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    phase, following, quadrature, continuum = _stress_continuum(
        material, full, audit
    )
    beta = np.asarray(audit["cell_velocity_cm_s"])[phase] / LIGHT_SPEED_CM_S
    cell_tau = (
        continuum.extinction_total_per_cm
        * full["cell_width_cm"][following][None, :]
    )
    total_tau = np.sum(cell_tau, axis=1)
    local_beta_tau = np.max(np.abs(beta)[None, :] * cell_tau, axis=1)
    system_beta_tau = np.max(np.abs(beta)) * total_tau
    energy = quadrature.photon_energy_ev
    maximum_index = int(np.argmax(system_beta_tau))
    metrics = {
        "maximum_total_optical_depth": float(np.max(total_tau)),
        "maximum_total_optical_depth_energy_ev": float(energy[np.argmax(total_tau)]),
        "maximum_local_beta_tau": float(np.max(local_beta_tau)),
        "maximum_local_beta_tau_energy_ev": float(energy[np.argmax(local_beta_tau)]),
        "maximum_system_beta_tau": float(system_beta_tau[maximum_index]),
        "maximum_system_beta_tau_energy_ev": float(energy[maximum_index]),
        "maximum_stress_phase_beta": float(np.max(np.abs(beta))),
        "first_order_velocity_expansion_asymptotically_safe": bool(
            np.max(system_beta_tau) < 1.0
        ),
    }
    arrays = {
        "photon_energy_ev": energy,
        "total_optical_depth": total_tau,
        "maximum_local_beta_tau": local_beta_tau,
        "system_beta_tau": system_beta_tau,
    }
    return metrics, arrays


def full_frequency_solver_stress(
    material: dict[str, np.ndarray],
    full: dict[str, np.ndarray],
    audit: dict[str, object],
) -> tuple[list[dict[str, object]], dict[str, object], dict[str, np.ndarray]]:
    phase, following, quadrature, continuum = _stress_continuum(
        material, full, audit
    )
    frequency = quadrature.frequency_hz
    mu, weight = gauss_legendre_half_range_mu_weights(PRODUCTION_ANGULAR_ORDER)
    initial_planck = planck_nu(
        frequency[:, None], full["temperature_k"][phase, None, :]
    )
    initial = np.broadcast_to(
        initial_planck[:, None, :],
        (frequency.size, mu.size, initial_planck.shape[1]),
    ).copy()
    common = dict(
        frequency_hz=frequency,
        old_depth_edges_cm=full["edges_cm"][phase],
        new_depth_edges_cm=full["edges_cm"][following],
        direction_cosine=mu,
        angular_weight=weight,
        initial_intensity=initial,
        extinction_per_cm=continuum.extinction_total_per_cm,
        thermal_source_intensity=continuum.thermal_source_intensity,
        absorption_probability=continuum.absorption_probability,
        duration_s=float(material["step_duration_s"][phase]),
    )
    results = {}
    rows: list[dict[str, object]] = []
    for solver in ("source_iteration", "sparse_lu"):
        started = time.perf_counter()
        result = solve_implicit_ale_slab_step(
            **common,
            linear_solver=solver,
            iterative_tolerance=SOLVER_TOLERANCE,
            iterative_maximum_iterations=4096,
        )
        elapsed = time.perf_counter() - started
        results[solver] = result
        rows.append(
            {
                "solver": solver,
                "runtime_s": elapsed,
                "minimum_iterations": int(np.min(result.linear_iterations)),
                "median_iterations": float(np.median(result.linear_iterations)),
                "maximum_iterations": int(np.max(result.linear_iterations)),
                "maximum_linear_residual": float(
                    np.max(result.relative_linear_system_residual)
                ),
                "maximum_energy_ledger_residual": float(
                    np.max(result.relative_energy_ledger_residual)
                ),
                "minimum_intensity": result.minimum_intensity,
                "maximum_matrix_nonzeros_per_frequency": result.maximum_matrix_nonzeros,
            }
        )
    direct = results["sparse_lu"]
    iterative = results["source_iteration"]
    scale = float(np.max(np.abs(direct.final_intensity)))
    difference = float(
        np.max(np.abs(iterative.final_intensity - direct.final_intensity)) / scale
    )
    metrics = {
        "phase_index": phase,
        "following_phase_index": following,
        "frequency_points": int(frequency.size),
        "angular_order": PRODUCTION_ANGULAR_ORDER,
        "full_column_depth_points": int(initial.shape[2]),
        "unknowns": int(initial.size),
        "source_iteration_vs_sparse_lu_scale_normalized_error": difference,
        "source_iteration_passed": bool(
            difference < SOLVER_COMPARISON_TOLERANCE
            and np.max(iterative.relative_energy_ledger_residual)
            < ENERGY_LEDGER_TOLERANCE
            and iterative.minimum_intensity >= 0.0
        ),
        "formal_16_subcell_unknowns": int(
            frequency.size
            * PRODUCTION_ANGULAR_ORDER
            * initial.shape[2]
            * 16
        ),
        "formal_full_orbit_runtime_authorized": False,
    }
    arrays = {
        "frequency_energy_ev": quadrature.photon_energy_ev,
        "iterative_mean_intensity": iterative.mean_intensity,
        "direct_mean_intensity": direct.mean_intensity,
        "relative_difference_by_frequency": np.max(
            np.abs(iterative.final_intensity - direct.final_intensity), axis=(1, 2)
        )
        / scale,
        "source_iteration_count": iterative.linear_iterations,
    }
    return rows, metrics, arrays


def _plot_lorentz_controls(
    path: Path,
    angular_rows: list[dict[str, object]],
    frequency_rows: list[dict[str, object]],
    breathing_arrays: dict[str, np.ndarray],
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.6), constrained_layout=True)
    for label in sorted({str(row["control"]) for row in angular_rows}):
        subset = [row for row in angular_rows if row["control"] == label]
        axes[0].semilogy(
            [row["angular_order"] for row in subset],
            [row["maximum_relative_error"] for row in subset],
            marker="o",
            label=label,
        )
    axes[0].axhline(CONTROL_TOLERANCE, color="black", ls=":", label="control target")
    axes[0].set_xlabel("Angular order")
    axes[0].set_ylabel("Maximum relative error")
    axes[0].set_title("Lorentz moment recovery")
    axes[0].legend(fontsize=8)

    axes[1].loglog(
        [row["physical_groups"] for row in frequency_rows],
        [row["maximum_pointwise_relative_error"] for row in frequency_rows],
        marker="o",
        label="pointwise group density",
    )
    axes[1].loglog(
        [row["physical_groups"] for row in frequency_rows],
        [row["maximum_integrated_relative_error"] for row in frequency_rows],
        marker="s",
        label="integrated energy",
    )
    axes[1].axhline(1.0e-3, color="black", ls=":", label="dynamic target")
    axes[1].set_xlabel("Physical frequency groups")
    axes[1].set_ylabel("Maximum relative error")
    axes[1].set_title("Conservative Doppler remap")
    axes[1].legend(fontsize=8)

    depth = breathing_arrays["stress_depth_centre_cm"]
    axes[2].plot(depth, breathing_arrays["stress_cell_beta"])
    axes[2].axhline(0.0, color="black", lw=0.8)
    axes[2].set_xlabel("Vertical coordinate (cm)")
    axes[2].set_ylabel("Cell velocity / c")
    axes[2].set_title("N128 homologous breathing snapshot")
    for axis in axes:
        axis.grid(alpha=0.25)
    fig.suptitle("Phase 7B4t full Lorentz transformation controls")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_solver_gate(
    path: Path,
    solver_rows: list[dict[str, object]],
    solver_arrays: dict[str, np.ndarray],
    diffusion_arrays: dict[str, np.ndarray],
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.6), constrained_layout=True)
    labels = [str(row["solver"]) for row in solver_rows]
    runtime = [float(row["runtime_s"]) for row in solver_rows]
    axes[0].bar(labels, runtime, color=("tab:blue", "tab:orange"))
    axes[0].set_ylabel("Runtime (s)")
    axes[0].set_title("N128 x 160 x S16 stress step")

    iterative_row = next(
        row for row in solver_rows if row["solver"] == "source_iteration"
    )
    agreement_ratios = np.array(
        [
            np.max(solver_arrays["relative_difference_by_frequency"])
            / SOLVER_COMPARISON_TOLERANCE,
            float(iterative_row["maximum_linear_residual"])
            / SOLVER_COMPARISON_TOLERANCE,
            float(iterative_row["maximum_energy_ledger_residual"])
            / ENERGY_LEDGER_TOLERANCE,
        ]
    )
    agreement_labels = ("solution\ndifference", "linear\nresidual", "energy\nledger")
    axes[1].bar(
        agreement_labels,
        agreement_ratios,
        color=("tab:blue", "tab:purple", "tab:green"),
    )
    axes[1].set_yscale("log")
    axes[1].axhline(1.0, color="black", ls=":", label="acceptance gate")
    axes[1].set_ylabel("Diagnostic / acceptance gate")
    axes[1].set_title("Solver agreement")
    axes[1].legend(fontsize=8)

    energy = diffusion_arrays["photon_energy_ev"]
    axes[2].loglog(energy, diffusion_arrays["total_optical_depth"], label="total optical depth")
    axes[2].loglog(energy, diffusion_arrays["system_beta_tau"], label="system beta tau")
    axes[2].loglog(energy, diffusion_arrays["maximum_local_beta_tau"], label="max local beta tau")
    axes[2].axhline(1.0, color="black", ls=":")
    axes[2].set_xlabel("Photon energy (eV)")
    axes[2].set_ylabel("Dimensionless diagnostic")
    axes[2].set_title("Dynamic-diffusion velocity gate")
    axes[2].legend(fontsize=8)
    for axis in axes:
        axis.grid(alpha=0.25)
    fig.suptitle("Phase 7B4t scalable solver and velocity-coupling gate")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_frequency_grid_gate(
    path: Path,
    maximum_beta: float,
    breathing_arrays: dict[str, np.ndarray],
) -> None:
    quadrature = _quadrature(2)
    group_grid = threshold_log_frequency_groups(
        *PHYSICAL_ENERGY_RANGE_EV,
        64,
        maximum_velocity_beta=maximum_beta,
        guard_transform_count=2,
    )
    group_energy = group_grid.centre_hz * PLANCK_ERG_S / EV_ERG
    group_width_energy = group_grid.width_hz * PLANCK_ERG_S / EV_ERG
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.6), constrained_layout=True)
    axes[0].loglog(
        quadrature.photon_energy_ev,
        quadrature.energy_weight_ev,
        ".",
        label="Gauss quadrature weight",
    )
    axes[0].loglog(
        group_energy,
        group_width_energy,
        ".",
        label="finite-volume group width",
    )
    axes[0].set_xlabel("Photon energy (eV)")
    axes[0].set_ylabel("Weight or group width (eV)")
    axes[0].set_title("Quadrature nodes are not group cells")
    axes[0].legend(fontsize=8)

    physical = group_grid.physical_group_mask
    axes[1].semilogx(group_energy, physical.astype(float), drawstyle="steps-mid")
    axes[1].set_ylim(-0.1, 1.1)
    axes[1].set_xlabel("Photon energy (eV)")
    axes[1].set_ylabel("Physical-band group mask")
    axes[1].set_title("Explicit Doppler guard bands")

    axes[2].loglog(
        breathing_arrays["physical_group_energy_ev"],
        breathing_arrays["maximum_relative_error_by_group"],
    )
    axes[2].axhline(1.0e-3, color="black", ls=":")
    axes[2].set_xlabel("Photon energy (eV)")
    axes[2].set_ylabel("Maximum relative error")
    axes[2].set_title("Actual breathing frequency-angle recovery")
    for axis in axes:
        axis.grid(alpha=0.25)
    fig.suptitle("Phase 7B4t frequency-grid compatibility gate")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b4t_summary.json",
        "angular": output_dir / "phase7b4t_angular_controls.csv",
        "frequency": output_dir / "phase7b4t_frequency_group_controls.csv",
        "solver": output_dir / "phase7b4t_solver_stress.csv",
        "npz": output_dir / "phase7b4t_diagnostics.npz",
        "lorentz_plot": output_dir / "phase7b4t_lorentz_controls.png",
        "solver_plot": output_dir / "phase7b4t_solver_and_dynamic_diffusion.png",
        "grid_plot": output_dir / "phase7b4t_frequency_grid_gate.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    trajectory = _trajectory_velocity_audit(material, full)
    maximum_beta = float(trajectory["maximum_velocity_beta"])
    angular_rows = angular_lorentz_controls(maximum_beta)
    frequency_rows = frequency_group_controls(maximum_beta)
    breathing_32_metrics, _ = actual_breathing_frame_control(
        material, full, trajectory, 32
    )
    breathing_metrics, breathing_arrays = actual_breathing_frame_control(
        material, full, trajectory, 64
    )
    diffusion_metrics, diffusion_arrays = dynamic_diffusion_audit(
        material, full, trajectory
    )
    solver_rows, solver_metrics, solver_arrays = full_frequency_solver_stress(
        material, full, trajectory
    )

    _write_csv(paths["angular"], angular_rows)
    _write_csv(paths["frequency"], frequency_rows)
    _write_csv(paths["solver"], solver_rows)
    _save_npz_atomic(
        paths["npz"],
        **breathing_arrays,
        **diffusion_arrays,
        **solver_arrays,
    )
    _plot_lorentz_controls(
        paths["lorentz_plot"], angular_rows, frequency_rows, breathing_arrays
    )
    _plot_solver_gate(
        paths["solver_plot"], solver_rows, solver_arrays, diffusion_arrays
    )
    _plot_frequency_grid_gate(paths["grid_plot"], maximum_beta, breathing_arrays)

    angular_production = [
        row
        for row in angular_rows
        if row["control"] == "ZO maximum"
        and row["angular_order"] == PRODUCTION_ANGULAR_ORDER
    ][0]
    group_32 = [row for row in frequency_rows if row["groups_per_decade"] == 32][0]
    group_64 = [row for row in frequency_rows if row["groups_per_decade"] == 64][0]
    transform_controls_passed = bool(
        angular_production["maximum_relative_error"] < CONTROL_TOLERANCE
        and group_64["maximum_integrated_relative_error"] < 1.0e-3
        and breathing_metrics["maximum_comoving_mean_relative_error"] < 1.0e-3
    )
    # 中文：Gauss 节点没有控制体边界；即使节点数相近，也不能充当守恒 Doppler 组。
    quadrature_compatible = False
    report = {
        "phase": "7B4t",
        "classification": (
            "[V] Lorentz/group-remap and positive iterative-solver gate; "
            "[O] coupled multigroup orbit"
        ),
        "literature_basis": {
            "jiang_2021": "lab-frame transport with exact Lorentz source transformation in grey discrete ordinates",
            "jiang_stone_davis_2014": "mixed-frame velocity terms and dynamic-diffusion caution",
        },
        "trajectory": {
            key: value
            for key, value in trajectory.items()
            if not isinstance(value, np.ndarray)
        },
        "angular_control": angular_production,
        "frequency_group_controls": {
            "153_group_candidate": group_32,
            "303_group_selected": group_64,
        },
        "actual_breathing_controls": {
            "153_group_candidate": breathing_32_metrics,
            "303_group_selected": breathing_metrics,
        },
        "dynamic_diffusion": diffusion_metrics,
        "solver_stress": solver_metrics,
        "solver_rows": solver_rows,
        "frequency_grid_gate": {
            "phase7b4q_gauss_nodes": 160,
            "gauss_nodes_have_finite_volume_edges": False,
            "gauss_quadrature_directly_compatible_with_conservative_doppler_remap": quadrature_compatible,
            "threshold_aligned_group_grid_required": True,
        },
        "decision": {
            "exact_lorentz_angle_transform_passed": bool(
                angular_production["maximum_relative_error"] < CONTROL_TOLERANCE
            ),
            "conservative_frequency_group_remap_passed": bool(
                group_64["maximum_integrated_relative_error"] < 1.0e-3
            ),
            "actual_breathing_frequency_angle_control_passed": bool(
                breathing_metrics["maximum_comoving_mean_relative_error"] < 1.0e-3
            ),
            "positive_batch_source_iteration_passed": bool(
                solver_metrics["source_iteration_passed"]
            ),
            "first_order_velocity_expansion_rejected_by_beta_tau": bool(
                not diffusion_metrics[
                    "first_order_velocity_expansion_asymptotically_safe"
                ]
            ),
            "phase7b4t_component_gates_passed": transform_controls_passed
            and bool(solver_metrics["source_iteration_passed"]),
            "phase7b4q_160_node_grid_reusable_for_doppler_remap": False,
            "153_physical_group_dynamic_candidate_accepted": False,
            "303_physical_group_dynamic_candidate_accepted": bool(
                breathing_metrics["maximum_comoving_mean_relative_error"] < 1.0e-3
            ),
            "full_160_frequency_dynamic_orbit_authorized": False,
            "next_microphase": (
                "threshold-aligned multigroup opacity/emissivity convergence and "
                "fully coupled mixed-frame ALE operator"
            ),
        },
        "open_items": [
            "The exact Lorentz frequency-angle operator is not yet coupled into the implicit ALE solve.",
            "The threshold-aligned finite-volume group grid must be converged against the accepted 160/304-node static quadratures.",
            "The 16-subcell, 2048-phase full dynamic orbit has not been run.",
            "Radiation feedback on temperature and H/He populations remains disabled.",
        ],
        "figures": [path.name for key, path in paths.items() if key.endswith("plot")],
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
