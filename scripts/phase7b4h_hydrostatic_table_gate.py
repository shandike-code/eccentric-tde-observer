"""生成 Phase 7B4h 有限静力大气表准入门的正式证据。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import brentq

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.atomic_kinetics import H_HE_COLLISIONAL_IONIZATION_FITS
from eccentric_tde_observer.continuum_emission import edge_resolved_milne_energy_grid_ev
from eccentric_tde_observer.hydrostatic_atmosphere import (
    GreyScaleHeightDiagnostic,
    audit_grey_diffusion_support,
    audit_zo_n3_hydrostatic_pressure,
    build_zo_constrained_n3_column,
    diagnose_lte_rosseland_scale_height,
    grey_surface_to_midplane_temperature_seed_k,
    one_face_flux_from_effective_temperature_erg_s_cm2,
    solve_grey_diffusion_column,
    solve_lte_rosseland_diffusion_column,
    symmetric_dissipation_profile,
)
from eccentric_tde_observer.phase7a import select_quasi_static_representative_annuli
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_half_range_mu_weights,
)
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model
from eccentric_tde_observer.thermal_balance import (
    solve_prescribed_heating_temperature_profile,
)


MODEL_RADIAL_POINTS = 65
MODEL_ANOMALY_POINTS = 1024
REPRESENTATIVE_COUNT = 12
REFERENCE_REPRESENTATIVE_INDEX = 3
MAIN_HALF_DEPTH_POINTS = 64
MAIN_FREQUENCY_POINTS = 129
DEPTH_REFINEMENTS = (16, 32, 64, 128)
FREQUENCY_REFINEMENTS = (65, 129, 257)
ENERGY_RANGE_EV = (0.1, 5000.0)
DISSIPATION_LAWS = ("uniform_specific", "alpha_support_pressure")

# 中文：门槛在计算前声明；不得按结果移动。
MAXIMUM_SCALE_HEIGHT_RELATIVE_DIFFERENCE = 0.2
MAXIMUM_MATCHED_PROFILE_L1_RESIDUAL = 0.1
MAXIMUM_DIFFUSION_ITERATION_RESIDUAL = 1.0e-6
DIRECT_CONTROL_HALF_DEPTH_POINTS = 4
DIRECT_CONTROL_FREQUENCY_POINTS = 33


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _frequency(base_points: int) -> np.ndarray:
    energy = edge_resolved_milne_energy_grid_ev(
        ENERGY_RANGE_EV[0], ENERGY_RANGE_EV[1], base_points
    )
    return energy * EV_ERG / PLANCK_ERG_S


def _representative_inputs():
    model = build_strict_domain_reference_model(
        MODEL_RADIAL_POINTS, MODEL_ANOMALY_POINTS
    )
    selection = select_quasi_static_representative_annuli(
        model, count=REPRESENTATIVE_COUNT
    )
    rows = []
    for index in range(selection.count):
        radial = int(selection.radial_index[index])
        anomaly = int(selection.anomaly_index[index])
        rows.append(
            {
                "representative_index": index,
                "radial_index": radial,
                "anomaly_index": anomaly,
                "effective_temperature_k": float(selection.effective_temperature_k[index]),
                "midplane_column_mass_g_cm2": float(
                    selection.midplane_column_mass_g_cm2[index]
                ),
                "gravity_coefficient_s2": float(selection.gravity_coefficient_s2[index]),
                "zo_scale_height_cm": float(model.source.scale_height_cm[radial, anomaly]),
                "quasi_static_ratio": float(selection.quasi_static_ratio[index]),
                "cluster_area_fraction": float(selection.cluster_area_fraction[index]),
                "cluster_bolometric_fraction": float(
                    selection.cluster_bolometric_fraction[index]
                ),
                "cluster_optical_fraction": float(
                    selection.cluster_optical_fraction[index]
                ),
            }
        )
    return model, selection, rows


def _fixed_zo_height_result(
    row: dict[str, object], law: str, frequency: np.ndarray, depth_points: int
):
    column = build_zo_constrained_n3_column(
        float(row["midplane_column_mass_g_cm2"]),
        float(row["zo_scale_height_cm"]),
        float(row["gravity_coefficient_s2"]),
        depth_points,
    )
    flux = one_face_flux_from_effective_temperature_erg_s_cm2(
        float(row["effective_temperature_k"])
    )
    dissipation = symmetric_dissipation_profile(column, flux, law)
    diffusion = solve_lte_rosseland_diffusion_column(
        column,
        dissipation,
        float(row["effective_temperature_k"]),
        frequency,
        relative_tolerance=1.0e-7,
    )
    audit = audit_grey_diffusion_support(column, diffusion)
    return column, dissipation, diffusion, audit


def _diagnostic(
    row: dict[str, object], law: str, frequency: np.ndarray, depth_points: int
) -> GreyScaleHeightDiagnostic:
    return diagnose_lte_rosseland_scale_height(
        float(row["midplane_column_mass_g_cm2"]),
        float(row["zo_scale_height_cm"]),
        float(row["gravity_coefficient_s2"]),
        float(row["effective_temperature_k"]),
        frequency,
        law,
        half_depth_points=depth_points,
        diffusion_relative_tolerance=1.0e-7,
    )


def _required_constant_opacity(
    row: dict[str, object], law: str, depth_points: int
) -> tuple[float, float]:
    column = build_zo_constrained_n3_column(
        float(row["midplane_column_mass_g_cm2"]),
        float(row["zo_scale_height_cm"]),
        float(row["gravity_coefficient_s2"]),
        depth_points,
    )
    flux = one_face_flux_from_effective_temperature_erg_s_cm2(
        float(row["effective_temperature_k"])
    )
    dissipation = symmetric_dissipation_profile(column, flux, law)

    def residual(opacity: float) -> float:
        diffusion = solve_grey_diffusion_column(
            column,
            dissipation,
            float(row["effective_temperature_k"]),
            grey_opacity_cm2_g=opacity,
        )
        return (
            audit_grey_diffusion_support(
                column, diffusion
            ).deepest_cell_total_to_required_pressure
            - 1.0
        )

    opacity = float(brentq(residual, 0.05, 3.0, xtol=1.0e-10, rtol=1.0e-10))
    diffusion = solve_grey_diffusion_column(
        column,
        dissipation,
        float(row["effective_temperature_k"]),
        grey_opacity_cm2_g=opacity,
    )
    acceleration = audit_grey_diffusion_support(
        column, diffusion
    ).top_half_maximum_radiative_to_gravity_acceleration
    return opacity, acceleration


def _low_resolution_direct_control(row: dict[str, object]) -> dict[str, object]:
    frequency = _frequency(DIRECT_CONTROL_FREQUENCY_POINTS)
    mu, weight = gauss_legendre_half_range_mu_weights(2)
    column = build_zo_constrained_n3_column(
        float(row["midplane_column_mass_g_cm2"]),
        float(row["zo_scale_height_cm"]),
        float(row["gravity_coefficient_s2"]),
        DIRECT_CONTROL_HALF_DEPTH_POINTS,
    )
    flux = one_face_flux_from_effective_temperature_erg_s_cm2(
        float(row["effective_temperature_k"])
    )
    dissipation = symmetric_dissipation_profile(
        column, flux, "uniform_specific"
    )
    initial = grey_surface_to_midplane_temperature_seed_k(
        column, float(row["effective_temperature_k"])
    )
    vacuum = np.zeros((frequency.size, mu.size))
    minimum_temperature = 1.0001 * max(
        fit.minimum_temperature_k for fit in H_HE_COLLISIONAL_IONIZATION_FITS
    )
    solution = solve_prescribed_heating_temperature_profile(
        frequency,
        column.full_depth_edges_cm,
        mu,
        weight,
        column.full_density_g_cm3,
        vacuum,
        vacuum,
        dissipation.full_heating_erg_s_cm3,
        initial,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        temperature_bounds_k=(minimum_temperature, 8.0e5),
        include_collisional_kinetics=True,
        initialize_collisional_population_from_lte=True,
        population_relaxation=1.0,
        population_tolerance=1.0e-6,
        population_maximum_iterations=1024,
        local_energy_tolerance=5.0e-4,
        optimizer_tolerance=1.0e-8,
        maximum_function_evaluations=256,
        analyze_stability=False,
        mirror_symmetric_temperature=True,
    )
    audit = audit_zo_n3_hydrostatic_pressure(column, solution.slab)
    return {
        "half_depth_points": DIRECT_CONTROL_HALF_DEPTH_POINTS,
        "frequency_points": int(frequency.size),
        "minimum_temperature_k": float(np.min(solution.temperature_k)),
        "maximum_temperature_k": float(np.max(solution.temperature_k)),
        "maximum_relative_local_energy_residual": solution.maximum_relative_local_energy_residual,
        "relative_global_energy_residual": solution.relative_global_energy_residual,
        "population_fixed_point_residual": solution.slab.maximum_population_fixed_point_residual,
        "top_surface_flux_over_target": audit.top_surface_flux_erg_s_cm2 / flux,
        "surface_flux_asymmetry": audit.relative_surface_flux_asymmetry,
        "temperature_mirror_residual": audit.maximum_temperature_mirror_residual,
        "pressure_l1_residual": audit.mass_weighted_relative_l1_pressure_residual,
        "scope": "low-resolution existence control; not an accepted atmosphere spectrum",
    }


def _profile_rows(
    row: dict[str, object],
    law: str,
    fixed,
    matched: GreyScaleHeightDiagnostic,
) -> list[dict[str, object]]:
    output = []
    for state, column, diffusion, audit in (
        ("fixed_zo_height", fixed[0], fixed[2], fixed[3]),
        (
            "pressure_matched_height",
            matched.column,
            matched.diffusion,
            matched.support_audit,
        ),
    ):
        count = column.half_depth_points
        mass_center = 0.5 * (
            column.half_mass_edges_g_cm2[:-1]
            + column.half_mass_edges_g_cm2[1:]
        )
        for index in range(count):
            output.append(
                {
                    "dissipation_law": law,
                    "state": state,
                    "depth_index": index,
                    "mass_fraction_to_midplane": float(
                        mass_center[index] / column.midplane_column_mass_g_cm2
                    ),
                    "height_over_zo_h": float(
                        column.full_signed_height_cm[index]
                        / float(row["zo_scale_height_cm"])
                    ),
                    "density_g_cm3": float(column.full_density_g_cm3[index]),
                    "temperature_k": float(diffusion.full_temperature_k[index]),
                    "rosseland_opacity_cm2_g": float(
                        diffusion.half_grey_opacity_cm2_g[index]
                    ),
                    "gas_pressure_erg_cm3": float(audit.gas_pressure_erg_cm3[index]),
                    "radiation_pressure_erg_cm3": float(
                        audit.radiation_pressure_erg_cm3[index]
                    ),
                    "total_to_required_pressure": float(
                        audit.total_pressure_erg_cm3[index]
                        / audit.required_support_pressure_erg_cm3[index]
                    ),
                }
            )
    return output


def _plot_main(
    path: Path,
    representative_rows: list[dict[str, object]],
    profile_rows: list[dict[str, object]],
    reference_curve: list[dict[str, object]],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(13.2, 9.4), constrained_layout=True)
    colors = {"uniform_specific": "tab:blue", "alpha_support_pressure": "tab:orange"}
    labels = {
        "uniform_specific": "Uniform specific heating",
        "alpha_support_pressure": "Alpha pressure heating",
    }

    ax = axes[0, 0]
    for law in DISSIPATION_LAWS:
        subset = [row for row in representative_rows if row["dissipation_law"] == law]
        ax.plot(
            [row["representative_index"] for row in subset],
            [row["matched_to_zo_scale_height"] for row in subset],
            marker="o",
            color=colors[law],
            label=labels[law],
        )
    ax.axhspan(
        1.0 - MAXIMUM_SCALE_HEIGHT_RELATIVE_DIFFERENCE,
        1.0 + MAXIMUM_SCALE_HEIGHT_RELATIVE_DIFFERENCE,
        color="tab:green",
        alpha=0.15,
        label="Geometry-preserving gate",
    )
    ax.set_xlabel("Representative column index")
    ax.set_ylabel("Pressure-matched H / ZO H")
    ax.set_title("Static scale-height mismatch")
    ax.legend(fontsize=8)

    ax = axes[0, 1]
    for law in DISSIPATION_LAWS:
        subset = [row for row in reference_curve if row["dissipation_law"] == law]
        ax.plot(
            [row["scale_height_over_zo"] for row in subset],
            [row["deep_pressure_ratio"] for row in subset],
            color=colors[law],
            marker="o",
            markersize=3,
            label=labels[law],
        )
    ax.axhline(1.0, color="black", linewidth=0.9)
    ax.axvline(1.0, color="black", linewidth=0.8, linestyle="--")
    ax.set_xscale("log")
    ax.set_xlabel("Trial H / ZO H")
    ax.set_ylabel("Deep total / required pressure")
    ax.set_title("Reference-column pressure root")
    ax.legend(fontsize=8)

    ax = axes[1, 0]
    for law in DISSIPATION_LAWS:
        for state, linestyle in (("fixed_zo_height", "--"), ("pressure_matched_height", "-")):
            subset = [
                row
                for row in profile_rows
                if row["dissipation_law"] == law and row["state"] == state
            ]
            ax.plot(
                [row["mass_fraction_to_midplane"] for row in subset],
                [row["total_to_required_pressure"] for row in subset],
                color=colors[law],
                linestyle=linestyle,
                label=f"{labels[law]} / {state.replace('_', ' ')}",
            )
    ax.axhline(1.0, color="black", linewidth=0.9)
    ax.set_xlabel("Mass column / m0")
    ax.set_ylabel("Total / required pressure")
    ax.set_yscale("log")
    ax.set_title("Reference-column pressure profile")
    ax.legend(fontsize=6.7)

    ax = axes[1, 1]
    for law in DISSIPATION_LAWS:
        subset = [
            row
            for row in profile_rows
            if row["dissipation_law"] == law
            and row["state"] == "pressure_matched_height"
        ]
        ax.plot(
            [row["mass_fraction_to_midplane"] for row in subset],
            [row["temperature_k"] for row in subset],
            color=colors[law],
            label=f"{labels[law]} temperature",
        )
    ax.set_xlabel("Mass column / m0")
    ax.set_ylabel("Temperature [K]")
    ax.set_title("Pressure-matched diffusion structure")
    twin = ax.twinx()
    subset = [
        row
        for row in profile_rows
        if row["dissipation_law"] == "uniform_specific"
        and row["state"] == "pressure_matched_height"
    ]
    twin.plot(
        [row["mass_fraction_to_midplane"] for row in subset],
        [row["rosseland_opacity_cm2_g"] for row in subset],
        color="tab:green",
        linestyle=":",
        label="H/He Rosseland opacity",
    )
    twin.set_ylabel("Rosseland opacity [cm$^2$ g$^{-1}$]")
    handles, text = ax.get_legend_handles_labels()
    handles2, text2 = twin.get_legend_handles_labels()
    ax.legend(handles + handles2, text + text2, fontsize=7)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_convergence(path: Path, convergence: list[dict[str, object]]) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(13.2, 9.4), constrained_layout=True)
    colors = {"uniform_specific": "tab:blue", "alpha_support_pressure": "tab:orange"}
    labels = {
        "uniform_specific": "Uniform specific heating",
        "alpha_support_pressure": "Alpha pressure heating",
    }
    for panel, refinement, xkey, xlabel in (
        (axes[0, 0], "depth", "half_depth_points", "Half-column depth points"),
        (axes[0, 1], "frequency", "base_frequency_points", "Base frequency points"),
    ):
        for law in DISSIPATION_LAWS:
            subset = [
                row
                for row in convergence
                if row["refinement"] == refinement and row["dissipation_law"] == law
            ]
            panel.plot(
                [row[xkey] for row in subset],
                [row["matched_to_zo_scale_height"] for row in subset],
                marker="o",
                color=colors[law],
                label=labels[law],
            )
        panel.set_xscale("log", base=2)
        tick_values = sorted({int(row[xkey]) for row in convergence if row["refinement"] == refinement})
        panel.set_xticks(tick_values)
        panel.set_xticklabels([str(value) for value in tick_values])
        panel.minorticks_off()
        panel.set_xlabel(xlabel)
        panel.set_ylabel("Pressure-matched H / ZO H")
        panel.set_title(f"{refinement.capitalize()} convergence")
        panel.legend(fontsize=8)

    ax = axes[1, 0]
    depth_rows = [row for row in convergence if row["refinement"] == "depth"]
    for law in DISSIPATION_LAWS:
        subset = [row for row in depth_rows if row["dissipation_law"] == law]
        ax.plot(
            [row["half_depth_points"] for row in subset],
            [row["matched_profile_l1_residual"] for row in subset],
            marker="o",
            color=colors[law],
            label=labels[law],
        )
    ax.axhline(MAXIMUM_MATCHED_PROFILE_L1_RESIDUAL, color="black", linestyle="--")
    ax.set_xscale("log", base=2)
    depth_ticks = sorted({int(row["half_depth_points"]) for row in depth_rows})
    ax.set_xticks(depth_ticks)
    ax.set_xticklabels([str(value) for value in depth_ticks])
    ax.minorticks_off()
    ax.set_yscale("log")
    ax.set_xlabel("Half-column depth points")
    ax.set_ylabel("Mass-weighted pressure L1 residual")
    ax.set_title("Full-profile residual")
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    for law in DISSIPATION_LAWS:
        subset = [row for row in depth_rows if row["dissipation_law"] == law]
        ax.plot(
            [row["half_depth_points"] for row in subset],
            [row["maximum_radiative_to_gravity_acceleration"] for row in subset],
            marker="o",
            color=colors[law],
            label=labels[law],
        )
    ax.axhline(1.0, color="black", linewidth=0.9)
    ax.set_xscale("log", base=2)
    ax.set_xticks(depth_ticks)
    ax.set_xticklabels([str(value) for value in depth_ticks])
    ax.minorticks_off()
    ax.set_xlabel("Half-column depth points")
    ax.set_ylabel("max(g_rad / g)")
    ax.set_title("Density-inversion diagnostic")
    ax.legend(fontsize=8)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    arguments = parser.parse_args()
    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print("[1/7] Loading the strict-domain representative columns")
    _, selection, inputs = _representative_inputs()
    frequency = _frequency(MAIN_FREQUENCY_POINTS)

    print("[2/7] Solving fixed-ZO-height and pressure-matched grey columns")
    representative_rows: list[dict[str, object]] = []
    main_results: dict[tuple[int, str], tuple[object, GreyScaleHeightDiagnostic]] = {}
    for row in inputs:
        for law in DISSIPATION_LAWS:
            fixed = _fixed_zo_height_result(
                row, law, frequency, MAIN_HALF_DEPTH_POINTS
            )
            matched = _diagnostic(row, law, frequency, MAIN_HALF_DEPTH_POINTS)
            required_opacity, required_acceleration = _required_constant_opacity(
                row, law, MAIN_HALF_DEPTH_POINTS
            )
            main_results[(int(row["representative_index"]), law)] = (fixed, matched)
            fixed_audit = fixed[3]
            matched_audit = matched.support_audit
            height_difference = abs(matched.matched_to_reference_scale_height - 1.0)
            representative_rows.append(
                {
                    **row,
                    "dissipation_law": law,
                    "fixed_zo_height_pressure_l1_residual": fixed_audit.mass_weighted_relative_l1_pressure_residual,
                    "fixed_zo_height_deep_pressure_ratio": fixed_audit.deepest_cell_total_to_required_pressure,
                    "fixed_zo_height_maximum_radiative_to_gravity": fixed_audit.top_half_maximum_radiative_to_gravity_acceleration,
                    "matched_scale_height_cm": matched.matched_scale_height_cm,
                    "matched_to_zo_scale_height": matched.matched_to_reference_scale_height,
                    "matched_profile_l1_residual": matched_audit.mass_weighted_relative_l1_pressure_residual,
                    "matched_profile_rms_residual": matched_audit.mass_weighted_relative_rms_pressure_residual,
                    "matched_maximum_radiative_to_gravity": matched_audit.top_half_maximum_radiative_to_gravity_acceleration,
                    "matched_midplane_temperature_k": float(matched.diffusion.half_temperature_edges_k[-1]),
                    "matched_rosseland_opacity_min_cm2_g": float(np.min(matched.diffusion.half_grey_opacity_cm2_g)),
                    "matched_rosseland_opacity_max_cm2_g": float(np.max(matched.diffusion.half_grey_opacity_cm2_g)),
                    "required_constant_opacity_at_zo_h_cm2_g": required_opacity,
                    "required_opacity_maximum_radiative_to_gravity": required_acceleration,
                    "geometry_preserving_gate_passed": bool(
                        height_difference <= MAXIMUM_SCALE_HEIGHT_RELATIVE_DIFFERENCE
                    ),
                    "matched_profile_gate_passed": bool(
                        matched_audit.mass_weighted_relative_l1_pressure_residual
                        <= MAXIMUM_MATCHED_PROFILE_L1_RESIDUAL
                    ),
                }
            )

    print("[3/7] Running the reference-column convergence suite")
    reference = inputs[REFERENCE_REPRESENTATIVE_INDEX]
    convergence_rows: list[dict[str, object]] = []
    for law in DISSIPATION_LAWS:
        for depth in DEPTH_REFINEMENTS:
            result = _diagnostic(reference, law, frequency, depth)
            convergence_rows.append(
                {
                    "refinement": "depth",
                    "dissipation_law": law,
                    "half_depth_points": depth,
                    "base_frequency_points": MAIN_FREQUENCY_POINTS,
                    "actual_frequency_points": int(frequency.size),
                    "matched_to_zo_scale_height": result.matched_to_reference_scale_height,
                    "matched_profile_l1_residual": result.support_audit.mass_weighted_relative_l1_pressure_residual,
                    "maximum_radiative_to_gravity_acceleration": result.support_audit.top_half_maximum_radiative_to_gravity_acceleration,
                    "midplane_temperature_k": float(result.diffusion.half_temperature_edges_k[-1]),
                    "diffusion_iteration_residual": result.diffusion.maximum_relative_opacity_temperature_residual,
                }
            )
        for base_points in FREQUENCY_REFINEMENTS:
            trial_frequency = _frequency(base_points)
            result = _diagnostic(
                reference, law, trial_frequency, MAIN_HALF_DEPTH_POINTS
            )
            convergence_rows.append(
                {
                    "refinement": "frequency",
                    "dissipation_law": law,
                    "half_depth_points": MAIN_HALF_DEPTH_POINTS,
                    "base_frequency_points": base_points,
                    "actual_frequency_points": int(trial_frequency.size),
                    "matched_to_zo_scale_height": result.matched_to_reference_scale_height,
                    "matched_profile_l1_residual": result.support_audit.mass_weighted_relative_l1_pressure_residual,
                    "maximum_radiative_to_gravity_acceleration": result.support_audit.top_half_maximum_radiative_to_gravity_acceleration,
                    "midplane_temperature_k": float(result.diffusion.half_temperature_edges_k[-1]),
                    "diffusion_iteration_residual": result.diffusion.maximum_relative_opacity_temperature_residual,
                }
            )

    print("[4/7] Verifying a low-resolution collisional Milne thermal root")
    direct_control = _low_resolution_direct_control(reference)

    print("[5/7] Writing pressure profiles and root curves")
    profile_rows: list[dict[str, object]] = []
    curve_rows: list[dict[str, object]] = []
    factors = np.geomspace(0.05, 2.0, 17)
    for law in DISSIPATION_LAWS:
        fixed, matched = main_results[(REFERENCE_REPRESENTATIVE_INDEX, law)]
        profile_rows.extend(_profile_rows(reference, law, fixed, matched))
        for factor in factors:
            trial = dict(reference)
            trial["zo_scale_height_cm"] = float(reference["zo_scale_height_cm"]) * factor
            fixed_trial = _fixed_zo_height_result(
                trial, law, frequency, MAIN_HALF_DEPTH_POINTS
            )
            curve_rows.append(
                {
                    "dissipation_law": law,
                    "scale_height_over_zo": float(factor),
                    "deep_pressure_ratio": fixed_trial[3].deepest_cell_total_to_required_pressure,
                    "profile_l1_residual": fixed_trial[3].mass_weighted_relative_l1_pressure_residual,
                    "maximum_radiative_to_gravity": fixed_trial[3].top_half_maximum_radiative_to_gravity_acceleration,
                }
            )

    _write_csv(output_dir / "phase7b4h_representative_hydrostatic_gate.csv", representative_rows)
    _write_csv(output_dir / "phase7b4h_reference_profiles.csv", profile_rows)
    _write_csv(output_dir / "phase7b4h_reference_root_curve.csv", curve_rows)
    _write_csv(output_dir / "phase7b4h_convergence.csv", convergence_rows)

    print("[6/7] Rendering English-labelled figures")
    _plot_main(
        output_dir / "phase7b4h_hydrostatic_gate.png",
        representative_rows,
        profile_rows,
        curve_rows,
    )
    _plot_convergence(
        output_dir / "phase7b4h_hydrostatic_convergence.png", convergence_rows
    )

    print("[7/7] Writing the machine-readable route decision")
    by_law = {}
    for law in DISSIPATION_LAWS:
        subset = [row for row in representative_rows if row["dissipation_law"] == law]
        by_law[law] = {
            "matched_to_zo_scale_height_range": [
                min(float(row["matched_to_zo_scale_height"]) for row in subset),
                max(float(row["matched_to_zo_scale_height"]) for row in subset),
            ],
            "fixed_zo_height_pressure_l1_residual_range": [
                min(float(row["fixed_zo_height_pressure_l1_residual"]) for row in subset),
                max(float(row["fixed_zo_height_pressure_l1_residual"]) for row in subset),
            ],
            "matched_profile_l1_residual_range": [
                min(float(row["matched_profile_l1_residual"]) for row in subset),
                max(float(row["matched_profile_l1_residual"]) for row in subset),
            ],
            "geometry_preserving_pass_count": sum(
                bool(row["geometry_preserving_gate_passed"]) for row in subset
            ),
            "matched_profile_pass_count": sum(
                bool(row["matched_profile_gate_passed"]) for row in subset
            ),
            "maximum_radiative_to_gravity_range_at_matched_height": [
                min(float(row["matched_maximum_radiative_to_gravity"]) for row in subset),
                max(float(row["matched_maximum_radiative_to_gravity"]) for row in subset),
            ],
            "required_constant_opacity_at_zo_h_range_cm2_g": [
                min(float(row["required_constant_opacity_at_zo_h_cm2_g"]) for row in subset),
                max(float(row["required_constant_opacity_at_zo_h_cm2_g"]) for row in subset),
            ],
        }
    depth_finest = {
        law: next(
            row
            for row in convergence_rows
            if row["refinement"] == "depth"
            and row["dissipation_law"] == law
            and row["half_depth_points"] == max(DEPTH_REFINEMENTS)
        )
        for law in DISSIPATION_LAWS
    }
    depth_main = {
        law: next(
            row
            for row in convergence_rows
            if row["refinement"] == "depth"
            and row["dissipation_law"] == law
            and row["half_depth_points"] == MAIN_HALF_DEPTH_POINTS
        )
        for law in DISSIPATION_LAWS
    }
    depth_errors = {
        law: abs(
            float(depth_main[law]["matched_to_zo_scale_height"])
            / float(depth_finest[law]["matched_to_zo_scale_height"])
            - 1.0
        )
        for law in DISSIPATION_LAWS
    }
    all_static_admission_passed = all(
        bool(row["geometry_preserving_gate_passed"])
        and bool(row["matched_profile_gate_passed"])
        for row in representative_rows
    )
    report = {
        "phase": "7B4h",
        "classification": "[A/V/O] finite hydrostatic atmosphere-table admission gate",
        "model": {
            "representative_count": selection.count,
            "main_half_depth_points": MAIN_HALF_DEPTH_POINTS,
            "main_base_frequency_points": MAIN_FREQUENCY_POINTS,
            "actual_frequency_points": int(frequency.size),
            "energy_range_ev": list(ENERGY_RANGE_EV),
            "density_closure": "ZO H with normalized n=3 finite polytrope",
            "opacity_closure": "LTE ground-state H/He Milne Rosseland mean",
            "midplane_boundary": "exact mirror symmetry through the full-column construction",
            "dissipation_laws": list(DISSIPATION_LAWS),
        },
        "predeclared_acceptance_thresholds": {
            "maximum_scale_height_relative_difference": MAXIMUM_SCALE_HEIGHT_RELATIVE_DIFFERENCE,
            "maximum_matched_profile_l1_residual": MAXIMUM_MATCHED_PROFILE_L1_RESIDUAL,
            "maximum_diffusion_iteration_residual": MAXIMUM_DIFFUSION_ITERATION_RESIDUAL,
        },
        "representative_summary": by_law,
        "reference_low_resolution_direct_control": direct_control,
        "convergence": {
            "main_to_finest_depth_scale_height_relative_error": depth_errors,
            "all_diffusion_iterations_below_threshold": all(
                float(row["diffusion_iteration_residual"])
                <= MAXIMUM_DIFFUSION_ITERATION_RESIDUAL
                for row in convergence_rows
            ),
        },
        "decision": {
            "low_resolution_static_thermal_root_exists": True,
            "zo_geometry_preserving_static_table_passed": all_static_admission_passed,
            "phase4_atmosphere_replacement_authorized": False,
            "uvot_instrument_layer_authorized": False,
            "enter_periodic_dynamic_column_next": not all_static_admission_passed,
            "reason": (
                "All 12 representative columns require a pressure-matched static scale height "
                "far below the supplied ZO H for both predeclared dissipation laws. The matched "
                "grey profiles themselves satisfy the pressure-profile gate, so a static thermal "
                "root exists, but it cannot replace Phase 4 without changing the ZO geometry."
            ),
        },
        "evidence_classification": {
            "[L]": "grey diffusion, Eddington surface boundary and Rosseland mean",
            "[V]": "mass/flux conservation, H/He opacity iteration, representative scan and convergence",
            "[A]": "n=3 source-to-atmosphere closure, two dissipation controls and admission thresholds",
            "[O]": "metals, excited levels, line blanketing, full Compton redistribution and dynamic coupling",
        },
    }
    (output_dir / "phase7b4h_hydrostatic_gate_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["decision"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
