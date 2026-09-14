"""Phase 5B1：ZO/OL 线性拱点本征模与物理时标门槛。"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import matplotlib
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer import (
    ZOConstantEParameters,
    solve_zo_linear_apsidal_modes,
    zo_local_gr_apsidal_precession_s1,
    zo_precession_scales,
)


RADIAL_RATIOS = (1.3, 2.0, 3.0, 4.0)
RADIAL_POINT_COUNTS = (64, 128, 256, 512)
STRONG_WEAK_RELATIVE_TARGET = 3.0e-6
FINE_GRID_RELATIVE_TARGET = 1.0e-5
BOUNDARY_RESIDUAL_TARGET = 2.0e-5
UNIFORM_SHIFT_S1 = 2.5e-8
UNIFORM_SHIFT_ABSOLUTE_TARGET_S1 = 3.0e-18
NORMALIZED_DIMENSIONLESS_FREQUENCY = 0.1
PRINTED_EQ48_COEFFICIENT_CYCLES_PER_DAY = 4.07e-3


def _parameters(
    outer_to_inner_semimajor_axis: float,
) -> ZOConstantEParameters:
    return ZOConstantEParameters(
        black_hole_mass_msun=1.0e6,
        stellar_mass_msun=1.0,
        stellar_radius_rsun=1.0,
        circularization_efficiency=1.0,
        outer_to_inner_semimajor_axis=outer_to_inner_semimajor_axis,
        eccentricity=0.0,
        opacity_cm2_g=0.34,
    )


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


def _strong_form_fundamental_frequency(
    radius_ratio: float,
    delta_gr: float,
) -> tuple[float, float, int]:
    """独立积分 OL Eq. (44) 强形式并施加两端自由 Robin 边界。"""
    gamma = 4.0 / 3.0
    boundary_ratio = (4.0 * gamma - 3.0) / (2.0 * gamma - 1.0)
    second_derivative_coefficient = (2.0 * gamma - 1.0) / (2.0 * gamma)
    eccentricity_coefficient = (9.0 - 5.0 * gamma) / (2.0 * gamma)

    def integrate(dimensionless_frequency: float, dense: bool):
        def equation(x: float, state: np.ndarray) -> tuple[float, float]:
            eccentricity, derivative = state
            second_derivative = (
                dimensionless_frequency * x**1.5 * eccentricity
                + eccentricity_coefficient * eccentricity
                + second_derivative_coefficient * x * derivative
                - delta_gr / x * eccentricity
            ) / (second_derivative_coefficient * x**2)
            return derivative, second_derivative

        solution = solve_ivp(
            equation,
            (1.0, radius_ratio),
            (1.0, -boundary_ratio),
            method="DOP853",
            rtol=2.0e-12,
            atol=2.0e-14,
            max_step=(radius_ratio - 1.0) / 256.0,
            dense_output=dense,
        )
        if not solution.success:
            raise RuntimeError("independent strong-form integration failed")
        return solution

    def residual(dimensionless_frequency: float) -> float:
        solution = integrate(dimensionless_frequency, False)
        return float(
            radius_ratio * solution.y[1, -1]
            + boundary_ratio * solution.y[0, -1]
        )

    left_residual = residual(0.0)
    right_residual = residual(4.0)
    if left_residual * right_residual >= 0.0:
        raise RuntimeError("predeclared strong-form bracket does not contain a root")
    frequency = float(brentq(residual, 0.0, 4.0, xtol=2.0e-13, rtol=2.0e-13))
    solution = integrate(frequency, True)
    sample_radius = np.geomspace(1.0, radius_ratio, 4097)
    sample_eccentricity = solution.sol(sample_radius)[0]
    node_count = int(
        np.count_nonzero(sample_eccentricity[:-1] * sample_eccentricity[1:] < 0.0)
    )
    return frequency, abs(residual(frequency)), node_count


def _piecewise_boundary_residuals(
    radius: np.ndarray,
    eccentricity: np.ndarray,
) -> tuple[float, float]:
    """用首末有限元单元斜率审计线性化 ZO Eq. (43)。"""
    gamma = 4.0 / 3.0
    boundary_ratio = (4.0 * gamma - 3.0) / (2.0 * gamma - 1.0)
    inner_derivative = (eccentricity[1] - eccentricity[0]) / (
        radius[1] - radius[0]
    )
    outer_derivative = (eccentricity[-1] - eccentricity[-2]) / (
        radius[-1] - radius[-2]
    )
    inner = radius[0] * inner_derivative + boundary_ratio * eccentricity[0]
    outer = radius[-1] * outer_derivative + boundary_ratio * eccentricity[-1]
    return float(inner), float(outer)


def _quadratic_boundary_residuals(
    radius: np.ndarray,
    eccentricity: np.ndarray,
) -> tuple[float, float]:
    """由三个边界节点二阶外推光滑解导数，避免把 P1 单元斜率误当精确导数。"""
    gamma = 4.0 / 3.0
    boundary_ratio = (4.0 * gamma - 3.0) / (2.0 * gamma - 1.0)
    inner_coefficient = np.polynomial.polynomial.polyfit(
        radius[:3] - radius[0], eccentricity[:3], 2
    )
    outer_coefficient = np.polynomial.polynomial.polyfit(
        radius[-3:] - radius[-1], eccentricity[-3:], 2
    )
    inner = (
        radius[0] * inner_coefficient[1]
        + boundary_ratio * eccentricity[0]
    )
    outer = (
        radius[-1] * outer_coefficient[1]
        + boundary_ratio * eccentricity[-1]
    )
    return float(inner), float(outer)


def _scale_audit(parameters: ZOConstantEParameters) -> dict[str, float]:
    scales = zo_precession_scales(parameters)
    direct_cycles_per_day = (
        NORMALIZED_DIMENSIONLESS_FREQUENCY
        * scales.dimensionless_to_cycles_per_day
    )
    mass_bh_bar = parameters.black_hole_mass_msun / 1.0e6
    mass_star_bar = parameters.stellar_mass_msun
    radius_star_bar = parameters.stellar_radius_rsun
    efficiency = parameters.circularization_efficiency
    printed_cycles_per_day = (
        PRINTED_EQ48_COEFFICIENT_CYCLES_PER_DAY
        * efficiency
        * np.sqrt(1.0 + efficiency)
        * mass_star_bar
        / (radius_star_bar**1.5 * np.sqrt(mass_bh_bar))
    )
    printed_eq40_delta_gr = (
        7.64e-3
        * (1.0 + efficiency) ** 2
        / efficiency
        * mass_bh_bar ** (1.0 / 3.0)
        * mass_star_bar ** (2.0 / 3.0)
        / radius_star_bar
    )
    return {
        "inner_semimajor_axis_cm": scales.inner_semimajor_axis_cm,
        "inner_mean_motion_s1": scales.inner_mean_motion_s1,
        "inner_specific_internal_energy_erg_g": (
            scales.inner_specific_internal_energy_erg_g
        ),
        "eq39_communication_time_days": (
            scales.eccentric_communication_time_s / 86400.0
        ),
        "delta_gr_direct": scales.delta_gr,
        "delta_gr_printed_eq40": float(printed_eq40_delta_gr),
        "delta_gr_relative_difference": float(
            abs(scales.delta_gr / printed_eq40_delta_gr - 1.0)
        ),
        "direct_eq39_cycles_per_day_at_tilde_omega_0p1": float(
            direct_cycles_per_day
        ),
        "printed_eq48_cycles_per_day_at_tilde_omega_0p1": float(
            printed_cycles_per_day
        ),
        "printed_to_direct_frequency_ratio": float(
            printed_cycles_per_day / direct_cycles_per_day
        ),
        "direct_eq39_period_days_at_tilde_omega_0p1": float(
            1.0 / direct_cycles_per_day
        ),
        "printed_eq48_period_days_at_tilde_omega_0p1": float(
            1.0 / printed_cycles_per_day
        ),
    }


def _plot_eigenfunctions(
    output_path: Path,
    shape_rows: list[dict[str, object]],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(11.2, 7.7), sharey=True)
    for axis, ratio in zip(axes.flat, RADIAL_RATIOS, strict=True):
        for include_gr, style, label in (
            (False, "--", "Pressure only"),
            (True, "-", "Pressure + GR"),
        ):
            row = next(
                item
                for item in shape_rows
                if item["outer_to_inner_ratio"] == ratio
                and item["include_gr"] is include_gr
            )
            axis.plot(
                row["scaled_radius"],
                row["eccentricity_shape"],
                style,
                linewidth=2.0,
                label=(
                    f"{label}, "
                    rf"$\widetilde{{\omega}}={row['dimensionless_frequency']:.4f}$"
                ),
            )
        axis.set_title(rf"$a_{{\rm out}}/a_{{\rm in}}={ratio:g}$")
        axis.set_xlabel(r"$a/a_{\rm in}$")
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    axes[0, 0].set_ylabel(r"$e(a)/e(a_{\rm in})$")
    axes[1, 0].set_ylabel(r"$e(a)/e(a_{\rm in})$")
    figure.suptitle("Linear node-free apsidal modes: free-boundary control")
    figure.tight_layout()
    figure.savefig(output_path, dpi=190)
    plt.close(figure)


def _plot_convergence(output_path: Path, rows: list[dict[str, object]]) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(11.4, 4.5))
    for include_gr, marker, label in (
        (False, "o", "Pressure only"),
        (True, "s", "Pressure + GR"),
    ):
        for ratio in RADIAL_RATIOS:
            selected = [
                row
                for row in rows
                if row["outer_to_inner_ratio"] == ratio
                and row["include_gr"] is include_gr
            ]
            axes[0].plot(
                [row["radial_points"] for row in selected],
                [row["dimensionless_frequency"] for row in selected],
                marker=marker,
                linewidth=1.3,
                markersize=4,
                label=f"{label}, R={ratio:g}",
            )
            axes[1].loglog(
                [row["radial_points"] for row in selected],
                [row["relative_to_strong_form"] for row in selected],
                marker=marker,
                linewidth=1.3,
                markersize=4,
                label=f"{label}, R={ratio:g}",
            )
    axes[0].set_xlabel("Radial nodes")
    axes[0].set_ylabel(r"Dimensionless frequency $\widetilde{\omega}$")
    axes[0].set_title("Weak-form radial convergence")
    axes[1].axhline(
        STRONG_WEAK_RELATIVE_TARGET,
        color="black",
        linestyle=":",
        linewidth=1.2,
        label="Acceptance target",
    )
    axes[1].set_xlabel("Radial nodes")
    axes[1].set_ylabel("Relative error vs strong form")
    axes[1].set_title("Independent strong/weak comparison")
    for axis in axes:
        axis.grid(alpha=0.25)
    axes[0].legend(fontsize=7, ncol=2)
    axes[1].legend(fontsize=7, ncol=2)
    figure.tight_layout()
    figure.savefig(output_path, dpi=190)
    plt.close(figure)


def _plot_scale_audit(
    output_path: Path,
    scale_audit: dict[str, float],
    gr_rows: list[dict[str, float]],
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.5))
    labels = ["Direct Eqs. 9–12, 39", "Printed Eq. 48"]
    values = [
        scale_audit["direct_eq39_cycles_per_day_at_tilde_omega_0p1"],
        scale_audit["printed_eq48_cycles_per_day_at_tilde_omega_0p1"],
    ]
    axes[0].bar(labels, values, color=("#3569a8", "#d46a38"))
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Cycles per day at dimensionless frequency 0.1")
    axes[0].set_title("ZO physical-normalization audit")
    axes[0].tick_params(axis="x", rotation=10)
    radius = [row["scaled_radius"] for row in gr_rows]
    local_gr = [row["dimensionless_local_gr_rate"] for row in gr_rows]
    axes[1].plot(radius, local_gr, color="#714f9a", linewidth=2.0)
    axes[1].set_xlabel(r"$a/a_{\rm in}$")
    axes[1].set_ylabel(r"Local $\widetilde{\omega}_{\rm GR}$")
    axes[1].set_title("Differential local GR precession")
    axes[1].grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_path, dpi=190)
    plt.close(figure)


def run(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    canonical_parameters = _parameters(2.0)
    canonical_scales = zo_precession_scales(canonical_parameters)
    strong_references: dict[tuple[float, bool], dict[str, float | int]] = {}
    for ratio in RADIAL_RATIOS:
        for include_gr in (False, True):
            delta_gr = canonical_scales.delta_gr if include_gr else 0.0
            frequency, residual, nodes = _strong_form_fundamental_frequency(
                ratio, delta_gr
            )
            strong_references[(ratio, include_gr)] = {
                "dimensionless_frequency": frequency,
                "outer_boundary_residual": residual,
                "radial_node_count": nodes,
            }

    rows: list[dict[str, object]] = []
    shape_rows: list[dict[str, object]] = []
    for ratio in RADIAL_RATIOS:
        parameters = _parameters(ratio)
        for include_gr in (False, True):
            strong = strong_references[(ratio, include_gr)]
            for radial_points in RADIAL_POINT_COUNTS:
                spectrum = solve_zo_linear_apsidal_modes(
                    parameters,
                    radial_points=radial_points,
                    include_gr=include_gr,
                    mode_count=1,
                )
                mode = spectrum.fundamental
                scaled_radius = (
                    spectrum.semimajor_axis_cm
                    / spectrum.scales.inner_semimajor_axis_cm
                )
                inner_boundary, outer_boundary = _piecewise_boundary_residuals(
                    scaled_radius, mode.eccentricity_shape
                )
                inner_extrapolated, outer_extrapolated = (
                    _quadratic_boundary_residuals(
                        scaled_radius, mode.eccentricity_shape
                    )
                )
                rows.append(
                    {
                        "outer_to_inner_ratio": ratio,
                        "include_gr": include_gr,
                        "radial_points": radial_points,
                        "dimensionless_frequency": mode.dimensionless_frequency,
                        "angular_frequency_s1": mode.angular_frequency_s1,
                        "period_days": mode.period_days,
                        "strong_form_dimensionless_frequency": strong[
                            "dimensionless_frequency"
                        ],
                        "relative_to_strong_form": abs(
                            mode.dimensionless_frequency
                            / float(strong["dimensionless_frequency"])
                            - 1.0
                        ),
                        "generalized_residual": mode.generalized_residual,
                        "radial_node_count": mode.radial_node_count,
                        "inner_robin_residual": inner_boundary,
                        "outer_robin_residual": outer_boundary,
                        "inner_extrapolated_robin_residual": (
                            inner_extrapolated
                        ),
                        "outer_extrapolated_robin_residual": (
                            outer_extrapolated
                        ),
                        "stiffness_symmetry_error": (
                            spectrum.stiffness_symmetry_error
                        ),
                        "mass_symmetry_error": spectrum.mass_symmetry_error,
                        "minimum_mass_eigenvalue": (
                            spectrum.minimum_mass_eigenvalue
                        ),
                    }
                )
                if radial_points == RADIAL_POINT_COUNTS[-1]:
                    shape_rows.append(
                        {
                            "outer_to_inner_ratio": ratio,
                            "include_gr": include_gr,
                            "scaled_radius": scaled_radius.tolist(),
                            "eccentricity_shape": mode.eccentricity_shape.tolist(),
                            "dimensionless_frequency": (
                                mode.dimensionless_frequency
                            ),
                        }
                    )

    baseline = solve_zo_linear_apsidal_modes(
        canonical_parameters,
        radial_points=128,
        include_gr=False,
        mode_count=3,
    )
    shifted = solve_zo_linear_apsidal_modes(
        canonical_parameters,
        radial_points=128,
        include_gr=False,
        uniform_external_precession_s1=UNIFORM_SHIFT_S1,
        mode_count=3,
    )
    shift_rows = []
    for original, translated in zip(baseline.modes, shifted.modes, strict=True):
        shift_rows.append(
            {
                "radial_node_count": original.radial_node_count,
                "measured_shift_s1": (
                    translated.angular_frequency_s1
                    - original.angular_frequency_s1
                ),
                "absolute_shift_error_s1": abs(
                    translated.angular_frequency_s1
                    - original.angular_frequency_s1
                    - UNIFORM_SHIFT_S1
                ),
                "maximum_shape_absolute_difference": float(
                    np.max(
                        np.abs(
                            translated.eccentricity_shape
                            - original.eccentricity_shape
                        )
                    )
                ),
            }
        )

    maximum_ratio = max(RADIAL_RATIOS)
    gr_radius = np.geomspace(1.0, maximum_ratio, 240)
    local_gr_s1 = zo_local_gr_apsidal_precession_s1(
        gr_radius * canonical_scales.inner_semimajor_axis_cm,
        canonical_parameters.black_hole_mass_msun,
    )
    gr_rows = [
        {
            "scaled_radius": float(radius),
            "local_gr_rate_s1": float(rate),
            "dimensionless_local_gr_rate": float(
                rate * canonical_scales.eccentric_communication_time_s
            ),
        }
        for radius, rate in zip(gr_radius, local_gr_s1, strict=True)
    ]
    scale_audit = _scale_audit(canonical_parameters)

    finest_rows = [
        row for row in rows if row["radial_points"] == RADIAL_POINT_COUNTS[-1]
    ]
    penultimate_rows = [
        row for row in rows if row["radial_points"] == RADIAL_POINT_COUNTS[-2]
    ]
    fine_grid_errors = []
    for fine in finest_rows:
        coarse = next(
            row
            for row in penultimate_rows
            if row["outer_to_inner_ratio"] == fine["outer_to_inner_ratio"]
            and row["include_gr"] is fine["include_gr"]
        )
        fine_grid_errors.append(
            abs(
                float(coarse["dimensionless_frequency"])
                / float(fine["dimensionless_frequency"])
                - 1.0
            )
        )

    maximum_strong_weak_error = max(
        float(row["relative_to_strong_form"]) for row in finest_rows
    )
    maximum_fine_grid_error = max(fine_grid_errors)
    maximum_piecewise_boundary_residual = max(
        max(
            abs(float(row["inner_robin_residual"])),
            abs(float(row["outer_robin_residual"])),
        )
        for row in finest_rows
    )
    maximum_extrapolated_boundary_residual = max(
        max(
            abs(float(row["inner_extrapolated_robin_residual"])),
            abs(float(row["outer_extrapolated_robin_residual"])),
        )
        for row in finest_rows
    )
    maximum_shift_error = max(
        float(row["absolute_shift_error_s1"]) for row in shift_rows
    )
    maximum_shape_shift = max(
        float(row["maximum_shape_absolute_difference"]) for row in shift_rows
    )
    decision = {
        "all_strong_form_modes_are_node_free": all(
            reference["radial_node_count"] == 0
            for reference in strong_references.values()
        ),
        "strong_weak_gate_passed": (
            maximum_strong_weak_error < STRONG_WEAK_RELATIVE_TARGET
        ),
        "radial_convergence_gate_passed": (
            maximum_fine_grid_error < FINE_GRID_RELATIVE_TARGET
        ),
        "free_boundary_gate_passed": (
            maximum_extrapolated_boundary_residual
            < BOUNDARY_RESIDUAL_TARGET
        ),
        "symmetric_positive_mass_gate_passed": all(
            float(row["stiffness_symmetry_error"]) == 0.0
            and float(row["mass_symmetry_error"]) == 0.0
            and float(row["minimum_mass_eigenvalue"]) > 0.0
            for row in rows
        ),
        "uniform_external_precession_shift_gate_passed": (
            maximum_shift_error < UNIFORM_SHIFT_ABSOLUTE_TARGET_S1
            and maximum_shape_shift < 3.0e-10
        ),
        "eq40_dimensionless_gr_scale_reproduced": (
            scale_audit["delta_gr_relative_difference"] < 5.0e-4
        ),
        "printed_eq48_normalization_matches_direct_eq39_ledger": (
            abs(scale_audit["printed_to_direct_frequency_ratio"] - 1.0)
            < 5.0e-3
        ),
    }
    decision["linear_small_e_solver_verified"] = all(
        value
        for key, value in decision.items()
        if key != "printed_eq48_normalization_matches_direct_eq39_ledger"
    )
    decision["phase5b2_nonlinear_kernel_authorized"] = decision[
        "linear_small_e_solver_verified"
    ]
    decision["high_e_zo_mode_reproduced"] = False
    decision["strict_domain_phase_to_time_mapping_authorized"] = False

    report: dict[str, object] = {
        "phase": "5B1",
        "scope": (
            "linear small-e three-dimensional free-boundary apsidal mode; "
            "not the nonlinear high-e ZO source solution"
        ),
        "configuration": {
            "black_hole_mass_msun": canonical_parameters.black_hole_mass_msun,
            "stellar_mass_msun": canonical_parameters.stellar_mass_msun,
            "stellar_radius_rsun": canonical_parameters.stellar_radius_rsun,
            "circularization_efficiency": (
                canonical_parameters.circularization_efficiency
            ),
            "radial_ratios": list(RADIAL_RATIOS),
            "radial_point_counts": list(RADIAL_POINT_COUNTS),
            "adiabatic_index": 4.0 / 3.0,
            "boundary_condition": (
                "(2 gamma - 1) a de/da + (4 gamma - 3) e = 0"
            ),
            "uniform_external_precession_shift_s1": UNIFORM_SHIFT_S1,
        },
        "literature_equations": {
            "dynamics": "Ogilvie & Lynch 2019 Eq. (44)",
            "zo_profiles_and_gr": "Zanazzi & Ogilvie 2020 Eqs. (9)-(12), (39)-(40)",
            "free_boundary": "linearized Zanazzi & Ogilvie 2020 Eq. (43)",
            "ol_eq43_literal_e2_coefficient_compatible_with_eq44": False,
            "ol_eq43_audit_note": (
                "The primary arXiv TeX literally contains (5 gamma - 9 gamma)e^2; "
                "the independently verified Eq. (44) corresponds to (5 gamma - 9)e^2."
            ),
        },
        "scale_audit": scale_audit,
        "strong_form_references": [
            {
                "outer_to_inner_ratio": ratio,
                "include_gr": include_gr,
                **reference,
            }
            for (ratio, include_gr), reference in strong_references.items()
        ],
        "convergence_rows": rows,
        "uniform_shift_control": shift_rows,
        "aggregate": {
            "maximum_finest_grid_strong_weak_relative_error": (
                maximum_strong_weak_error
            ),
            "maximum_256_to_512_relative_frequency_change": (
                maximum_fine_grid_error
            ),
            "maximum_512_point_piecewise_robin_residual": (
                maximum_piecewise_boundary_residual
            ),
            "maximum_512_point_extrapolated_robin_residual": (
                maximum_extrapolated_boundary_residual
            ),
            "maximum_uniform_shift_absolute_error_s1": maximum_shift_error,
            "maximum_uniform_shift_shape_absolute_difference": (
                maximum_shape_shift
            ),
            "local_gr_dimensionless_inner": gr_rows[0][
                "dimensionless_local_gr_rate"
            ],
            "local_gr_dimensionless_at_4ain": gr_rows[-1][
                "dimensionless_local_gr_rate"
            ],
        },
        "decision": decision,
        "open_items": [
            (
                "The printed Eq. (48) normalization is about ten times the direct "
                "Eqs. (9)-(12), (39) ledger and is not adopted silently."
            ),
            (
                "This linear e -> 0 calculation does not reproduce the nonlinear "
                "high-e modes in ZO Figures 6-7."
            ),
            (
                "The strict-domain e=0.6 source cannot yet be assigned an absolute "
                "precession period; Phase 5B2 must first reproduce the nonlinear mode."
            ),
            (
                "Local GR-only differential precession is not a coherent global "
                "eigenmode without pressure communication."
            ),
        ],
    }

    _write_csv(output_dir / "phase5b1_linear_apsidal_convergence.csv", rows)
    _write_csv(output_dir / "phase5b1_local_gr_profile.csv", gr_rows)
    _write_json_atomic(output_dir / "phase5b1_linear_apsidal_report.json", report)
    _plot_eigenfunctions(
        output_dir / "phase5b1_linear_eigenfunctions.png", shape_rows
    )
    _plot_convergence(
        output_dir / "phase5b1_linear_convergence.png", rows
    )
    _plot_scale_audit(
        output_dir / "phase5b1_precession_scale_audit.png", scale_audit, gr_rows
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    report = run(args.output_dir)
    decision = report["decision"]
    scale = report["scale_audit"]
    print(
        "Phase 5B1 complete: "
        f"linear_verified={decision['linear_small_e_solver_verified']}, "
        f"Eq48/direct={scale['printed_to_direct_frequency_ratio']:.6f}, "
        "high_e_time_mapping=False"
    )


if __name__ == "__main__":
    main()
