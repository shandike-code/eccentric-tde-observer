"""Phase 7B5l：守恒局域多分辨率频率表示的组件准入门。"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.atomic_continuum import (
    EV_ERG,
    H_HE_GROUND_STATE_PHOTOIONIZATION_FITS,
)
from eccentric_tde_observer.goal_oriented_frequency import (
    hydrogen_photoionization_monitor_group_grid,
)
from eccentric_tde_observer.mixed_frame_frequency import lorentz_ray_transform
from eccentric_tde_observer.multigroup_continuum import (
    gauss_legendre_frequency_group_quadrature,
    group_average_from_quadrature_nodes,
)
from eccentric_tde_observer.multiresolution_frequency import (
    budgeted_variable_frequency_grid,
    embedded_p0_frequency_error,
    nested_log_frequency_hierarchy,
    prolong_piecewise_constant_frequency,
    restrict_piecewise_constant_frequency,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S, planck_nu
from eccentric_tde_observer.radiative_transfer_1d import gauss_legendre_mu_weights

try:
    from scripts.phase7b5a_log_frequency_p1_gate import (
        CONTROL_ANGULAR_ORDER,
        PHYSICAL_ENERGY_RANGE_EV,
        _actual_case_definitions,
        _load_material_reference,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from scripts.phase7b5c_signed_rate_error_localization import (
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
    )
    from scripts.phase7b5f_single_pass_intensity_transform import (
        _state_parameters,
    )
    from scripts.phase7b5j_prescribed_partition_audit import (
        EFFICIENCY_GROUP_LIMIT,
        H_I_RATE_TARGET,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5a_log_frequency_p1_gate import (  # type: ignore[no-redef]
        CONTROL_ANGULAR_ORDER,
        PHYSICAL_ENERGY_RANGE_EV,
        _actual_case_definitions,
        _load_material_reference,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from phase7b5c_signed_rate_error_localization import (  # type: ignore[no-redef]
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
    )
    from phase7b5f_single_pass_intensity_transform import (  # type: ignore[no-redef]
        _state_parameters,
    )
    from phase7b5j_prescribed_partition_audit import (  # type: ignore[no-redef]
        EFFICIENCY_GROUP_LIMIT,
        H_I_RATE_TARGET,
    )


GROUP_QUADRATURE_ORDER = 16
INDICATOR_QUADRATURE_ORDERS = (8, 16)
TRANSFER_TARGET = 2.0e-13
INDICATOR_QUADRATURE_TARGET = 2.0e-10


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    fields: list[str] = []
    for row in rows:
        fields.extend(key for key in row if key not in fields)
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _boosted_planck_control_spectra(hierarchy, states, mu, weight):
    quadrature = gauss_legendre_frequency_group_quadrature(
        hierarchy.master_edge_hz,
        order_per_group=GROUP_QUADRATURE_ORDER,
    )
    spectra = []
    metadata = []
    for case, state in states:
        transform = lorentz_ray_transform(mu, weight, state["beta"])
        temperature = float(state["temperature_k"])
        for angle, factor in enumerate(
            transform.doppler_lab_to_comoving[:, 0]
        ):
            node = quadrature.node_hz
            # 中文：只构造已解析受控的 boosted Planck 输入，不充当动态大气谱。
            intensity = factor**-3 * planck_nu(factor * node, temperature)
            spectra.append(
                group_average_from_quadrature_nodes(intensity, quadrature)
            )
            metadata.append(
                {
                    "case": case,
                    "angle_index": angle,
                    "mu": float(mu[angle]),
                    "temperature_k": temperature,
                    "material_velocity_beta": float(state["beta"][0]),
                    "lab_to_comoving_doppler_factor": float(factor),
                }
            )
    return np.column_stack(spectra), metadata


def _maximum_relative_difference(left, right) -> float:
    left_array = np.asarray(left)
    right_array = np.asarray(right)
    scale = float(max(np.max(np.abs(left_array)), np.max(np.abs(right_array))))
    difference = float(np.max(np.abs(left_array - right_array)))
    return difference / scale if scale > 0.0 else difference


def _plot_hierarchy(path: Path, hierarchy, variable) -> None:
    fig, axis = plt.subplots(figsize=(11.0, 5.4), constrained_layout=True)
    for edge, label, color, alpha in (
        (hierarchy.base_edge_hz, "base: 2408", "tab:blue", 0.85),
        (hierarchy.pilot_edge_hz, "pilot: 4816", "tab:orange", 0.70),
        (hierarchy.master_edge_hz, "master: 9632", "tab:green", 0.55),
        (variable.group_edge_hz, "budgeted variable: 4814", "tab:red", 0.85),
    ):
        centre_ev = np.sqrt(edge[:-1] * edge[1:]) * PLANCK_ERG_S / EV_ERG
        axis.plot(
            centre_ev,
            np.diff(np.log(edge)),
            color=color,
            alpha=alpha,
            linewidth=1.0,
            label=label,
        )
    for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS:
        axis.axvline(fit.threshold_energy_ev, color="black", linestyle=":", alpha=0.5)
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set_xlabel("Photon energy (eV)")
    axis.set_ylabel("Leaf width in log frequency")
    axis.set_title("Strictly nested 1-2-4 frequency hierarchy")
    axis.grid(alpha=0.2, which="both")
    axis.legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_indicator(path: Path, hierarchy, indicator, variable) -> None:
    centre_ev = (
        np.sqrt(hierarchy.base_edge_hz[:-1] * hierarchy.base_edge_hz[1:])
        * PLANCK_ERG_S
        / EV_ERG
    )
    fig, axis = plt.subplots(figsize=(11.0, 5.4), constrained_layout=True)
    axis.plot(
        centre_ev,
        indicator.normalized_indicator,
        color="0.45",
        linewidth=0.9,
        label="embedded max indicator",
    )
    selected = variable.refined_parent_mask
    axis.scatter(
        centre_ev[selected],
        indicator.normalized_indicator[selected],
        s=9,
        color="tab:red",
        label="selected four-child parents",
        zorder=3,
    )
    for fit, label in zip(
        H_HE_GROUND_STATE_PHOTOIONIZATION_FITS,
        ("H I", "He I", "He II"),
        strict=True,
    ):
        axis.axvline(
            fit.threshold_energy_ev,
            color="black",
            linestyle=":",
            alpha=0.5,
        )
        axis.text(
            fit.threshold_energy_ev,
            0.98,
            label,
            transform=axis.get_xaxis_transform(),
            ha="left",
            va="top",
            fontsize=8,
        )
    axis.axhline(1.0, color="black", linestyle="--", label="unit target contribution")
    axis.set_xscale("log")
    axis.set_yscale("symlog", linthresh=1.0e-12)
    axis.set_ylim(0.0, 1.2)
    axis.set_xlabel("Photon energy (eV)")
    axis.set_ylabel("Normalized embedded defect")
    axis.set_title("Deterministic energy and H/He rate ranking")
    axis.grid(alpha=0.2, which="both")
    axis.legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_controls(path: Path, controls) -> None:
    labels = [row["control"] for row in controls]
    values = [row["value"] for row in controls]
    fig, axis = plt.subplots(figsize=(10.0, 5.0), constrained_layout=True)
    axis.bar(np.arange(len(labels)), values, color="tab:blue")
    axis.axhline(TRANSFER_TARGET, color="black", linestyle=":", label="transfer target")
    axis.set_yscale("symlog", linthresh=1.0e-16)
    axis.set_ylim(0.0, 4.0e-13)
    axis.set_xticks(np.arange(len(labels)), labels, rotation=24, ha="right")
    axis.set_ylabel("Relative residual")
    axis.set_title("Conservative transfer and embedded-quadrature controls")
    axis.grid(alpha=0.2, axis="y", which="both")
    axis.legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5l_summary.json",
        "parents": output_dir / "phase7b5l_parent_indicators.csv",
        "spectra": output_dir / "phase7b5l_control_spectra.csv",
        "hierarchy_plot": output_dir / "phase7b5l_frequency_hierarchy.png",
        "indicator_plot": output_dir / "phase7b5l_embedded_indicator.png",
        "control_plot": output_dir / "phase7b5l_transfer_controls.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    trajectory_audit = _trajectory_velocity_audit(material, full)
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    states = [
        (
            str(definition["case"]),
            _state_parameters(material, full, definition),
        )
        for definition in _actual_case_definitions(
            material, full, trajectory_audit
        )
    ]
    base_grid = hydrogen_photoionization_monitor_group_grid(
        *PHYSICAL_ENERGY_RANGE_EV,
        FAILED_PHYSICAL_GROUPS,
        FAILED_FOCUS_FRACTION,
    )
    hierarchy = nested_log_frequency_hierarchy(base_grid.group_edge_hz)
    spectra, spectrum_metadata = _boosted_planck_control_spectra(
        hierarchy, states, mu, weight
    )
    indicators = [
        embedded_p0_frequency_error(
            hierarchy.base_edge_hz,
            hierarchy.master_edge_hz,
            spectra,
            production_tolerance=H_I_RATE_TARGET,
            quadrature_order_per_fine_group=order,
        )
        for order in INDICATOR_QUADRATURE_ORDERS
    ]
    low, high = indicators
    indicator_quadrature_error = max(
        _maximum_relative_difference(
            low.rate_defect_fraction_by_species,
            high.rate_defect_fraction_by_species,
        ),
        _maximum_relative_difference(
            low.energy_l1_defect_fraction,
            high.energy_l1_defect_fraction,
        ),
    )
    variable = budgeted_variable_frequency_grid(
        high,
        hierarchy.master_edge_hz,
        EFFICIENCY_GROUP_LIMIT,
    )

    base_restriction = restrict_piecewise_constant_frequency(
        hierarchy.master_edge_hz, hierarchy.base_edge_hz, spectra
    )
    base_prolongation = prolong_piecewise_constant_frequency(
        hierarchy.base_edge_hz,
        hierarchy.master_edge_hz,
        base_restriction.mean_intensity_density,
    )
    variable_restriction = restrict_piecewise_constant_frequency(
        hierarchy.master_edge_hz, variable.group_edge_hz, spectra
    )
    variable_prolongation = prolong_piecewise_constant_frequency(
        variable.group_edge_hz,
        hierarchy.master_edge_hz,
        variable_restriction.mean_intensity_density,
    )
    constant = np.ones((hierarchy.base_edge_hz.size - 1, 3))
    constant_prolongation = prolong_piecewise_constant_frequency(
        hierarchy.base_edge_hz, hierarchy.master_edge_hz, constant
    )
    constant_restriction = restrict_piecewise_constant_frequency(
        hierarchy.master_edge_hz,
        hierarchy.base_edge_hz,
        constant_prolongation.mean_intensity_density,
    )
    constant_roundtrip = float(
        np.max(np.abs(constant_restriction.mean_intensity_density - constant))
    )
    controls = [
        {
            "control": "base restriction integral",
            "value": base_restriction.maximum_relative_integral_residual,
        },
        {
            "control": "base prolongation integral",
            "value": base_prolongation.maximum_relative_integral_residual,
        },
        {
            "control": "variable restriction integral",
            "value": variable_restriction.maximum_relative_integral_residual,
        },
        {
            "control": "variable prolongation integral",
            "value": variable_prolongation.maximum_relative_integral_residual,
        },
        {
            "control": "constant roundtrip",
            "value": constant_roundtrip,
        },
        {
            "control": "8/16 indicator quadrature",
            "value": indicator_quadrature_error,
        },
    ]
    transfer_passed = all(
        row["value"] < TRANSFER_TARGET for row in controls[:-1]
    )
    quadrature_passed = indicator_quadrature_error < INDICATOR_QUADRATURE_TARGET
    hierarchy_passed = bool(
        np.array_equal(hierarchy.pilot_edge_hz[::2], hierarchy.base_edge_hz)
        and np.array_equal(
            hierarchy.master_edge_hz[::2], hierarchy.pilot_edge_hz
        )
        and np.all(np.diff(hierarchy.master_edge_hz) > 0.0)
        and all(
            np.count_nonzero(
                hierarchy.master_edge_hz
                == fit.threshold_energy_ev * EV_ERG / PLANCK_ERG_S
            )
            == 1
            for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
        )
    )
    budget_passed = bool(
        variable.leaf_group_count <= EFFICIENCY_GROUP_LIMIT
        and variable.leaf_group_count
        == int(np.sum(variable.child_groups_per_base))
        and np.all(
            (variable.child_groups_per_base == 1)
            | (variable.child_groups_per_base == 4)
        )
    )
    component_gate = bool(
        hierarchy_passed
        and transfer_passed
        and quadrature_passed
        and budget_passed
    )
    decision = {
        "strict_nested_hierarchy_passed": hierarchy_passed,
        "conservative_transfer_controls_passed": transfer_passed,
        "embedded_indicator_quadrature_passed": quadrature_passed,
        "leaf_budget_bookkeeping_passed": budget_passed,
        "multiresolution_component_gate_passed": component_gate,
        "actual_state_multiresolution_audit_authorized": component_gate,
        "production_frequency_representation_selected": False,
        "angular_radiation_subgrid_time_gate_authorized": False,
        "full_dynamic_orbit_authorized": False,
        "matter_temperature_population_feedback_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }

    parent_rows = []
    centre_ev = (
        np.sqrt(hierarchy.base_edge_hz[:-1] * hierarchy.base_edge_hz[1:])
        * PLANCK_ERG_S
        / EV_ERG
    )
    species_labels = ("H I", "He I", "He II")
    for parent in range(hierarchy.base_edge_hz.size - 1):
        row: dict[str, object] = {
            "base_parent_index": parent,
            "centre_energy_ev": centre_ev[parent],
            "left_energy_ev": hierarchy.base_edge_hz[parent]
            * PLANCK_ERG_S
            / EV_ERG,
            "right_energy_ev": hierarchy.base_edge_hz[parent + 1]
            * PLANCK_ERG_S
            / EV_ERG,
            "normalized_indicator": high.normalized_indicator[parent],
            "energy_l1_defect_fraction": high.energy_l1_defect_fraction[parent],
            "selected_for_four_children": bool(variable.refined_parent_mask[parent]),
            "variable_child_count": int(variable.child_groups_per_base[parent]),
        }
        for species, label in enumerate(species_labels):
            row[f"{label}_rate_defect_fraction"] = (
                high.rate_defect_fraction_by_species[species, parent]
            )
        parent_rows.append(row)
    _write_csv(paths["parents"], parent_rows)
    _write_csv(paths["spectra"], spectrum_metadata)
    _plot_hierarchy(paths["hierarchy_plot"], hierarchy, variable)
    _plot_indicator(paths["indicator_plot"], hierarchy, high, variable)
    _plot_controls(paths["control_plot"], controls)
    report = {
        "phase": "7B5l",
        "classification": (
            "[A/V] fixed f=0.25 base hierarchy and boosted-Planck component "
            "controls; [V] conservative transfers and deterministic ranking; "
            "[O] actual dynamic-state accuracy and production selection"
        ),
        "configuration": {
            "physical_energy_range_ev": list(PHYSICAL_ENERGY_RANGE_EV),
            "base_group_count": hierarchy.base_edge_hz.size - 1,
            "pilot_group_count": hierarchy.pilot_edge_hz.size - 1,
            "master_group_count": hierarchy.master_edge_hz.size - 1,
            "leaf_group_budget": EFFICIENCY_GROUP_LIMIT,
            "fixed_rate_kernel_focus_fraction": FAILED_FOCUS_FRACTION,
            "control_angular_order": CONTROL_ANGULAR_ORDER,
            "control_spectrum_count": spectra.shape[1],
            "group_quadrature_order": GROUP_QUADRATURE_ORDER,
            "indicator_quadrature_orders": list(INDICATOR_QUADRATURE_ORDERS),
            "production_tolerance": H_I_RATE_TARGET,
            "variable_grid_rule": (
                "stable descending embedded energy/H/He defect; each base parent "
                "retains one leaf or all four master children; no fitted bandwidth"
            ),
        },
        "state_controls": spectrum_metadata,
        "transfer_and_quadrature_controls": controls,
        "indicator": {
            "maximum_normalized_indicator": float(
                np.max(high.normalized_indicator)
            ),
            "median_normalized_indicator": float(
                np.median(high.normalized_indicator)
            ),
            "indicator_quadrature_relative_difference": (
                indicator_quadrature_error
            ),
            "maximum_restriction_integral_residual": (
                high.maximum_restriction_integral_residual
            ),
        },
        "budgeted_grid": {
            "refined_parent_count": variable.refined_parent_count,
            "leaf_group_count": variable.leaf_group_count,
            "leaf_group_budget": variable.leaf_group_budget,
            "unused_leaf_budget": variable.unused_leaf_budget,
            "maximum_unrefined_indicator": variable.maximum_unrefined_indicator,
            "minimum_refined_indicator": variable.minimum_refined_indicator,
        },
        "decision": decision,
        "open_items": [
            "boosted-Planck controls are analytic component inputs, not dynamic spectra",
            "the embedded ranking has not yet been trained/validated on disjoint actual checkpoints",
            "passing transfer and budget controls does not imply the H I rate gate passes",
            "production frequency representation remains unselected",
            "angle, radiation-subgrid, orbit and matter-feedback gates remain closed",
        ],
        "figures": {
            "frequency_hierarchy": paths["hierarchy_plot"].name,
            "embedded_indicator": paths["indicator_plot"].name,
            "transfer_controls": paths["control_plot"].name,
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
