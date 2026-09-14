"""Phase 7B4u：实际 H/He 多群连续系数、原子率和净加热门。"""

from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.continuum_emission import (
    GroundStateMilneContinuum,
    ground_state_milne_continuum,
    ground_state_milne_radiative_rates,
)
from eccentric_tde_observer.frequency_quadrature import integrate_frequency
from eccentric_tde_observer.mixed_frame_frequency import (
    threshold_log_frequency_groups,
)
from eccentric_tde_observer.multigroup_continuum import (
    gauss_legendre_frequency_group_quadrature,
    ground_state_milne_multigroup,
    group_average_from_quadrature_nodes,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S, planck_nu

try:
    from scripts.phase7b4q_threshold_quadrature import _quadrature
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b4q_threshold_quadrature import _quadrature


ENERGY_RANGE_EV = (0.1, 5000.0)
GROUPS_PER_DECADE = (32, 64, 128, 256)
GROUP_ORDER = 16
GROUP_ORDER_AUDIT = (8, 16, 32)
STATIC_REFERENCE_PANELS = 8
TARGET_RELATIVE_ERROR = 1.0e-3
INTERNAL_QUADRATURE_TARGET = 2.0e-7
MAXIMUM_VELOCITY_BETA = 0.008028600886554787
PHASE_SAMPLE_COUNT = 16
DEPTH_INDICES = (0, 1, 8, 24, 42, 64, 96, 127)


@dataclass(frozen=True)
class MaterialState:
    phase_index: int
    depth_index: int
    orbital_phase: float
    mass_fraction: float
    density_g_cm3: float
    temperature_k: float
    hydrogen_fraction: np.ndarray
    helium_fraction: np.ndarray


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


def _load_states(material_path: Path) -> tuple[list[MaterialState], np.ndarray, np.ndarray]:
    with np.load(material_path, allow_pickle=False) as payload:
        orbital_phase = np.array(payload["orbital_phase"], copy=True)
        mass_edges = np.array(payload["mass_fraction_edges"], copy=True)
        density = np.array(payload["density_g_cm3"], copy=True)
        temperature = np.array(payload["temperature_k"], copy=True)
        hydrogen = np.array(payload["hydrogen_fraction"], copy=True)
        helium = np.array(payload["helium_fraction"], copy=True)
    if density.shape != temperature.shape or density.shape[1] != 128:
        raise ValueError("Phase 7B4u requires the N128 material reference")
    regular_phase_indices = np.rint(
        np.linspace(0, density.shape[0] - 1, PHASE_SAMPLE_COUNT)
    ).astype(int)
    minimum_temperature_phase = int(
        np.unravel_index(np.argmin(temperature), temperature.shape)[0]
    )
    maximum_temperature_phase = int(
        np.unravel_index(np.argmax(temperature), temperature.shape)[0]
    )
    helium_front_phase = int(
        np.unravel_index(
            np.argmin(np.abs(helium[:, :, 1] - helium[:, :, 2])),
            helium[:, :, 1].shape,
        )[0]
    )
    # 中文：除均匀相位样本外，显式保留最强网格步、最大速度步和物态极值。
    phase_indices = np.unique(
        np.concatenate(
            (
                regular_phase_indices,
                [
                    628,
                    1367,
                    minimum_temperature_phase,
                    maximum_temperature_phase,
                    helium_front_phase,
                ],
            )
        )
    )
    mass_centre = 0.5 * (mass_edges[:-1] + mass_edges[1:])
    states = [
        MaterialState(
            phase_index=int(phase),
            depth_index=int(depth),
            orbital_phase=float(orbital_phase[phase]),
            mass_fraction=float(mass_centre[depth]),
            density_g_cm3=float(density[phase, depth]),
            temperature_k=float(temperature[phase, depth]),
            hydrogen_fraction=np.array(hydrogen[phase, depth], copy=True),
            helium_fraction=np.array(helium[phase, depth], copy=True),
        )
        for phase in phase_indices
        for depth in DEPTH_INDICES
    ]
    return states, phase_indices, mass_centre[np.asarray(DEPTH_INDICES)]


def _physical_group_edges(groups_per_decade: int) -> tuple[np.ndarray, int, int]:
    extended = threshold_log_frequency_groups(
        *ENERGY_RANGE_EV,
        groups_per_decade,
        maximum_velocity_beta=MAXIMUM_VELOCITY_BETA,
        guard_transform_count=2,
    )
    active = np.flatnonzero(extended.physical_group_mask)
    if active.size == 0 or np.any(np.diff(active) != 1):
        raise ArithmeticError("physical frequency groups must form one contiguous band")
    edge = np.array(extended.edge_hz[active[0] : active[-1] + 2], copy=True)
    return edge, int(active.size), int(extended.centre_hz.size)


def _state_arguments(state: MaterialState) -> tuple[object, ...]:
    return (
        state.density_g_cm3,
        state.temperature_k,
        state.hydrogen_fraction[0],
        state.hydrogen_fraction[1],
        state.helium_fraction[0],
        state.helium_fraction[1],
        state.helium_fraction[2],
    )


def _metrics(
    continuum: GroundStateMilneContinuum,
    rates,
    mean: np.ndarray,
    weight: np.ndarray,
) -> dict[str, np.ndarray]:
    absorbed = 4.0 * np.pi * integrate_frequency(
        continuum.true_absorption_total_per_cm * mean,
        weight,
        axis=0,
    )
    emitted = 4.0 * np.pi * integrate_frequency(
        continuum.thermal_emissivity_total_cgs,
        weight,
        axis=0,
    )
    return {
        "absorption_moment": np.atleast_1d(absorbed),
        "emissivity_moment": np.atleast_1d(emitted),
        "photoionization": np.asarray(rates.photoionization_s1).reshape(-1),
        "spontaneous_recombination": np.asarray(
            rates.spontaneous_recombination_cm3_s
        ).reshape(-1),
        "stimulated_recombination": np.asarray(
            rates.stimulated_recombination_cm3_s
        ).reshape(-1),
        "total_recombination": np.asarray(
            rates.total_recombination_cm3_s
        ).reshape(-1),
        "radiative_heating": np.atleast_1d(absorbed - emitted),
    }


def nodal_state_metrics(state: MaterialState, panels: int) -> dict[str, np.ndarray]:
    quadrature = _quadrature(panels)
    mean = planck_nu(quadrature.frequency_hz[:, None], state.temperature_k)
    args = _state_arguments(state)
    continuum = ground_state_milne_continuum(
        args[0],
        args[1],
        quadrature.frequency_hz,
        *args[2:],
    )
    rates = ground_state_milne_radiative_rates(
        state.temperature_k,
        quadrature.frequency_hz,
        mean,
        frequency_weight_hz=quadrature.frequency_weight_hz,
    )
    return _metrics(
        continuum,
        rates,
        mean,
        quadrature.frequency_weight_hz,
    )


def group_state_metrics(
    state: MaterialState,
    groups_per_decade: int,
    *,
    order_per_group: int = GROUP_ORDER,
) -> dict[str, np.ndarray]:
    edge, _, _ = _physical_group_edges(groups_per_decade)
    quadrature = gauss_legendre_frequency_group_quadrature(
        edge, order_per_group=order_per_group
    )
    node_planck = planck_nu(quadrature.node_hz, state.temperature_k)
    group_planck = group_average_from_quadrature_nodes(
        node_planck, quadrature
    )[:, None]
    args = _state_arguments(state)
    result = ground_state_milne_multigroup(
        args[0],
        args[1],
        edge,
        group_planck,
        *args[2:],
        order_per_group=order_per_group,
    )
    return {
        "absorption_moment": result.absorbed_power_erg_s_cm3,
        "emissivity_moment": result.emitted_power_erg_s_cm3,
        "photoionization": result.radiative_rates.photoionization_s1.reshape(-1),
        "spontaneous_recombination": (
            result.radiative_rates.spontaneous_recombination_cm3_s.reshape(-1)
        ),
        "stimulated_recombination": (
            result.radiative_rates.stimulated_recombination_cm3_s.reshape(-1)
        ),
        "total_recombination": (
            result.radiative_rates.total_recombination_cm3_s.reshape(-1)
        ),
        "radiative_heating": result.radiative_heating_erg_s_cm3,
    }


def _evaluate_configuration(
    states: list[MaterialState],
    evaluator,
) -> dict[str, np.ndarray]:
    by_metric: dict[str, list[np.ndarray]] = {}
    for state in states:
        result = evaluator(state)
        for metric, value in result.items():
            by_metric.setdefault(metric, []).append(np.asarray(value, dtype=np.float64))
    return {metric: np.stack(values) for metric, values in by_metric.items()}


def _scale_normalized_errors(
    candidate: dict[str, np.ndarray],
    reference: dict[str, np.ndarray],
) -> tuple[dict[str, float], np.ndarray]:
    errors: dict[str, float] = {}
    state_error = np.zeros(reference["absorption_moment"].shape[0])
    for metric in (
        "absorption_moment",
        "emissivity_moment",
        "photoionization",
        "spontaneous_recombination",
        "stimulated_recombination",
        "total_recombination",
    ):
        difference = np.abs(candidate[metric] - reference[metric])
        scale = np.max(np.abs(reference[metric]), axis=0)
        component = np.array(difference, copy=True)
        nonzero = scale > 0.0
        component[:, nonzero] /= scale[nonzero]
        component[:, ~nonzero] = difference[:, ~nonzero]
        errors[metric] = float(np.max(component))
        state_error = np.maximum(state_error, np.max(component, axis=1))
    heating_difference = np.abs(
        candidate["radiative_heating"] - reference["radiative_heating"]
    )[:, 0]
    heating_scale = np.maximum.reduce(
        (
            np.abs(candidate["absorption_moment"][:, 0]),
            np.abs(candidate["emissivity_moment"][:, 0]),
            np.abs(reference["absorption_moment"][:, 0]),
            np.abs(reference["emissivity_moment"][:, 0]),
        )
    )
    heating_component = np.array(heating_difference, copy=True)
    active = heating_scale > 0.0
    heating_component[active] /= heating_scale[active]
    errors["heating_ledger"] = float(np.max(heating_component))
    state_error = np.maximum(state_error, heating_component)
    return errors, state_error


def _configuration_row(
    name: str,
    representation: str,
    frequency_elements: int,
    internal_order: int,
    errors: dict[str, float],
) -> dict[str, object]:
    maximum = max(errors.values())
    return {
        "configuration": name,
        "representation": representation,
        "frequency_elements": frequency_elements,
        "internal_order": internal_order,
        **errors,
        "maximum_gate_error": maximum,
        "target": TARGET_RELATIVE_ERROR,
        "passed": bool(maximum < TARGET_RELATIVE_ERROR),
    }


def _worst_state_row(
    configuration: str,
    state: MaterialState,
    error: float,
) -> dict[str, object]:
    return {
        "configuration": configuration,
        "phase_index": state.phase_index,
        "depth_index": state.depth_index,
        "orbital_phase": state.orbital_phase,
        "mass_fraction": state.mass_fraction,
        "density_g_cm3": state.density_g_cm3,
        "temperature_k": state.temperature_k,
        "hydrogen_neutral_fraction": state.hydrogen_fraction[0],
        "helium_neutral_fraction": state.helium_fraction[0],
        "helium_singly_ionized_fraction": state.helium_fraction[1],
        "helium_doubly_ionized_fraction": state.helium_fraction[2],
        "maximum_scale_normalized_error": error,
    }


def _plot_convergence(
    path: Path,
    rows: list[dict[str, object]],
    state_errors: dict[str, np.ndarray],
    phase_indices: np.ndarray,
    sampled_mass: np.ndarray,
) -> None:
    group_rows = [row for row in rows if row["representation"] == "finite-volume group"]
    fig, axes = plt.subplots(1, 3, figsize=(16.2, 4.7), constrained_layout=True)
    for metric, label in (
        ("absorption_moment", "absorption moment"),
        ("emissivity_moment", "emissivity moment"),
        ("photoionization", "photoionization"),
        ("stimulated_recombination", "stimulated recombination"),
        ("total_recombination", "total recombination"),
        ("heating_ledger", "heating ledger"),
    ):
        axes[0].loglog(
            [row["frequency_elements"] for row in group_rows],
            [row[metric] for row in group_rows],
            marker="o",
            label=label,
        )
    axes[0].axhline(TARGET_RELATIVE_ERROR, color="black", ls=":")
    axes[0].set_xlabel("Physical frequency groups")
    axes[0].set_ylabel("Maximum scale-normalized error")
    axes[0].set_title("Finite-volume group convergence")
    axes[0].legend(fontsize=7)

    labels = [str(row["configuration"]) for row in rows]
    values = [float(row["maximum_gate_error"]) for row in rows]
    colors = ["tab:blue" if row["representation"] == "Gauss nodes" else "tab:orange" for row in rows]
    axes[1].bar(np.arange(len(rows)), values, color=colors)
    axes[1].set_yscale("log")
    axes[1].axhline(TARGET_RELATIVE_ERROR, color="black", ls=":")
    axes[1].set_xticks(np.arange(len(rows)), labels, rotation=55, ha="right")
    axes[1].set_ylabel("Maximum error")
    axes[1].set_title("Static nodes versus finite-volume groups")

    selected = "group_604"
    heatmap = state_errors[selected].reshape(phase_indices.size, sampled_mass.size).T
    image = axes[2].imshow(
        heatmap,
        origin="lower",
        aspect="auto",
        extent=(0.0, 1.0, sampled_mass[0], sampled_mass[-1]),
    )
    axes[2].set_xlabel("Orbital sample index / cycle")
    axes[2].set_ylabel("Lagrangian mass fraction")
    axes[2].set_title("604-group error across actual states")
    fig.colorbar(image, ax=axes[2], label="Maximum normalized error")
    for axis in axes[:2]:
        axis.grid(alpha=0.25)
    fig.suptitle("Phase 7B4u H/He multigroup continuum gate")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_worst_spectrum(
    path: Path,
    state: MaterialState,
) -> None:
    reference = _quadrature(STATIC_REFERENCE_PANELS)
    args = _state_arguments(state)
    reference_continuum = ground_state_milne_continuum(
        args[0], args[1], reference.frequency_hz, *args[2:]
    )
    energy = PLANCK_ERG_S * reference.frequency_hz / 1.602176634e-12
    fig, axes = plt.subplots(1, 3, figsize=(16.2, 4.7), constrained_layout=True)
    axes[0].loglog(
        energy,
        reference_continuum.true_absorption_total_per_cm[:, 0],
        color="black",
        label="584-node reference",
    )
    axes[1].loglog(
        energy,
        reference_continuum.thermal_emissivity_total_cgs[:, 0],
        color="black",
        label="584-node reference",
    )
    for groups_per_decade, color, linestyle in (
        (128, "tab:orange", "--"),
        (256, "tab:blue", ":"),
    ):
        edge, physical_count, _ = _physical_group_edges(groups_per_decade)
        quadrature = gauss_legendre_frequency_group_quadrature(edge)
        group_planck = group_average_from_quadrature_nodes(
            planck_nu(quadrature.node_hz, state.temperature_k), quadrature
        )[:, None]
        result = ground_state_milne_multigroup(
            args[0], args[1], edge, group_planck, *args[2:]
        )
        group_energy = PLANCK_ERG_S * edge / 1.602176634e-12
        axes[0].stairs(
            result.continuum.true_absorption_total_per_cm[:, 0],
            group_energy,
            color=color,
            linestyle=linestyle,
            linewidth=1.8,
            zorder=3,
            label=f"{physical_count} groups",
        )
        axes[1].stairs(
            result.continuum.thermal_emissivity_total_cgs[:, 0],
            group_energy,
            color=color,
            linestyle=linestyle,
            linewidth=1.8,
            zorder=3,
            label=f"{physical_count} groups",
        )
    for axis, title, ylabel in (
        (axes[0], "Group-averaged true absorption", "Absorption (cm$^{-1}$)"),
        (axes[1], "Group-averaged thermal emissivity", "Emissivity (cgs)"),
    ):
        axis.set_xlabel("Photon energy (eV)")
        axis.set_ylabel(ylabel)
        axis.set_title(title)
        axis.legend(fontsize=8)
        axis.grid(alpha=0.25)
    axes[2].bar(
        ("H I", "H II", "He I", "He II", "He III"),
        (
            state.hydrogen_fraction[0],
            state.hydrogen_fraction[1],
            state.helium_fraction[0],
            state.helium_fraction[1],
            state.helium_fraction[2],
        ),
    )
    axes[2].set_yscale("log")
    axes[2].set_ylabel("Ground-state fraction")
    axes[2].set_title(
        f"Worst sampled state: T={state.temperature_k:.0f} K, phase={state.orbital_phase:.3f}"
    )
    axes[2].grid(alpha=0.25)
    fig.suptitle("Phase 7B4u worst-state continuum coefficients")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b4u_summary.json",
        "convergence": output_dir / "phase7b4u_multigroup_convergence.csv",
        "worst": output_dir / "phase7b4u_worst_states.csv",
        "states": output_dir / "phase7b4u_state_sample.csv",
        "convergence_plot": output_dir / "phase7b4u_multigroup_gate.png",
        "spectrum_plot": output_dir / "phase7b4u_worst_state_coefficients.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    states, phase_indices, sampled_mass = _load_states(material_path)
    reference = _evaluate_configuration(
        states, lambda state: nodal_state_metrics(state, STATIC_REFERENCE_PANELS)
    )
    configurations: list[tuple[str, str, int, int, dict[str, np.ndarray]]] = []
    for panels in (2, 4):
        quadrature = _quadrature(panels)
        configurations.append(
            (
                f"static_{quadrature.frequency_hz.size}",
                "Gauss nodes",
                int(quadrature.frequency_hz.size),
                int(quadrature.order_per_panel),
                _evaluate_configuration(
                    states, lambda state, p=panels: nodal_state_metrics(state, p)
                ),
            )
        )
    group_metadata: dict[int, tuple[int, int]] = {}
    for groups_per_decade in GROUPS_PER_DECADE:
        _, physical_count, extended_count = _physical_group_edges(groups_per_decade)
        group_metadata[groups_per_decade] = (physical_count, extended_count)
        configurations.append(
            (
                f"group_{physical_count}",
                "finite-volume group",
                physical_count,
                GROUP_ORDER,
                _evaluate_configuration(
                    states,
                    lambda state, g=groups_per_decade: group_state_metrics(state, g),
                ),
            )
        )
    rows: list[dict[str, object]] = []
    state_errors: dict[str, np.ndarray] = {}
    worst_rows: list[dict[str, object]] = []
    for name, representation, elements, order, values in configurations:
        errors, by_state = _scale_normalized_errors(values, reference)
        state_errors[name] = by_state
        rows.append(
            _configuration_row(
                name, representation, elements, order, errors
            )
        )
        worst_index = int(np.argmax(by_state))
        worst_rows.append(
            _worst_state_row(name, states[worst_index], float(by_state[worst_index]))
        )

    order_values = {
        order: _evaluate_configuration(
            states,
            lambda state, o=order: group_state_metrics(
                state, 128, order_per_group=o
            ),
        )
        for order in GROUP_ORDER_AUDIT
    }
    order8_errors, _ = _scale_normalized_errors(order_values[8], order_values[32])
    order16_errors, _ = _scale_normalized_errors(order_values[16], order_values[32])
    maximum_order_error = max(order16_errors.values())
    state_rows = [
        {
            "phase_index": state.phase_index,
            "depth_index": state.depth_index,
            "orbital_phase": state.orbital_phase,
            "mass_fraction": state.mass_fraction,
            "density_g_cm3": state.density_g_cm3,
            "temperature_k": state.temperature_k,
            "hydrogen_neutral_fraction": state.hydrogen_fraction[0],
            "helium_neutral_fraction": state.helium_fraction[0],
            "helium_singly_ionized_fraction": state.helium_fraction[1],
            "helium_doubly_ionized_fraction": state.helium_fraction[2],
        }
        for state in states
    ]
    _write_csv(paths["convergence"], rows)
    _write_csv(paths["worst"], worst_rows)
    _write_csv(paths["states"], state_rows)
    _plot_convergence(
        paths["convergence_plot"], rows, state_errors, phase_indices, sampled_mass
    )
    worst_604 = max(
        (row for row in worst_rows if row["configuration"] == "group_604"),
        key=lambda row: float(row["maximum_scale_normalized_error"]),
    )
    worst_state = next(
        state
        for state in states
        if state.phase_index == worst_604["phase_index"]
        and state.depth_index == worst_604["depth_index"]
    )
    _plot_worst_spectrum(paths["spectrum_plot"], worst_state)

    row_by_name = {str(row["configuration"]): row for row in rows}
    accepted_groups = [
        int(row["frequency_elements"])
        for row in rows
        if row["representation"] == "finite-volume group" and row["passed"]
    ]
    decision = {
        "static_160_vs_584_passed": bool(row_by_name["static_160"]["passed"]),
        "static_304_vs_584_passed": bool(row_by_name["static_304"]["passed"]),
        "153_physical_groups_accepted": bool(row_by_name["group_153"]["passed"]),
        "303_physical_groups_accepted": bool(row_by_name["group_303"]["passed"]),
        "604_physical_groups_accepted": bool(row_by_name["group_604"]["passed"]),
        "1205_physical_groups_accepted": bool(row_by_name["group_1205"]["passed"]),
        "group_order16_vs32_passed": bool(
            maximum_order_error < INTERNAL_QUADRATURE_TARGET
        ),
        "multigroup_continuum_gate_passed": bool(
            accepted_groups and maximum_order_error < INTERNAL_QUADRATURE_TARGET
        ),
        "selected_physical_frequency_groups": (
            min(accepted_groups) if accepted_groups else None
        ),
        "fully_coupled_mixed_frame_ale_authorized": bool(
            accepted_groups and maximum_order_error < INTERNAL_QUADRATURE_TARGET
        ),
        "full_dynamic_orbit_authorized": False,
    }
    report = {
        "phase": "7B4u",
        "classification": (
            "[V] H/He multigroup coefficient/rate gate on prescribed material; "
            "[O] coupled mixed-frame ALE orbit"
        ),
        "configuration": {
            "energy_range_ev": list(ENERGY_RANGE_EV),
            "sampled_phase_points": int(phase_indices.size),
            "sampled_depth_points": len(DEPTH_INDICES),
            "sampled_material_states": len(states),
            "static_reference_frequency_points": int(
                _quadrature(STATIC_REFERENCE_PANELS).frequency_hz.size
            ),
            "group_order": GROUP_ORDER,
            "group_order_audit": list(GROUP_ORDER_AUDIT),
            "maximum_velocity_beta_for_guard": MAXIMUM_VELOCITY_BETA,
            "group_counts": {
                str(groups_per_decade): {
                    "physical": group_metadata[groups_per_decade][0],
                    "with_guard": group_metadata[groups_per_decade][1],
                }
                for groups_per_decade in GROUPS_PER_DECADE
            },
            "target_relative_error": TARGET_RELATIVE_ERROR,
            "internal_quadrature_target": INTERNAL_QUADRATURE_TARGET,
        },
        "convergence": rows,
        "internal_group_quadrature": {
            "order8_vs32_errors": order8_errors,
            "order16_vs32_errors": order16_errors,
            "maximum_error": maximum_order_error,
        },
        "worst_states": worst_rows,
        "decision": decision,
        "open_items": [
            "the selected multigroup source operator is not yet coupled to the ALE residual",
            "the material temperature and H/He populations remain prescribed",
            "radiation subgrid, time, and full-orbit convergence remain open",
            "excited levels, total recombination cascades, Compton redistribution, and line transfer remain open",
        ],
        "figures": {
            "multigroup_gate": paths["convergence_plot"].name,
            "worst_state_coefficients": paths["spectrum_plot"].name,
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
