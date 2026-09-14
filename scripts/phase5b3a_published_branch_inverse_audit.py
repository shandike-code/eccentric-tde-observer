"""Phase 5B3a：反演审计 ZO 2020 Fig. 6/7 的已发表分支。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from eccentric_tde_observer import (
    PhysicalDomainError,
    ZOConstantEParameters,
    build_zo_hamiltonian_spline_table,
    solve_zo_linear_apsidal_modes,
    solve_zo_nonlinear_apsidal_mode_bvp,
    zo_precession_scales,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"

# 中文：这些点来自 arXiv 源包 Fig. 7 左图的矢量路径，不是方程解或拟合数据。
PUBLISHED_FIGURE_7 = {
    1.3: np.array(
        (
            (0.10, -2.082780000),
            (0.15, -1.150136876),
            (0.1918332609, -0.717061649),
            (0.20, -0.649766679),
            (0.25, -0.333038092),
            (0.30, -0.115162425),
        )
    ),
    2.0: np.array(
        (
            (0.10, -0.612580000),
            (0.15, -0.172793026),
            (0.1918332609, 0.054825944),
            (0.20, 0.087521070),
            (0.25, 0.255119960),
            (0.30, 0.371165042),
        )
    ),
    4.0: np.array(
        (
            (0.10, -0.308883004),
            (0.15, -0.032613319),
            (0.1918332609, 0.133727689),
            (0.20, 0.161251916),
            (0.25, 0.297269383),
            (0.30, 0.394539805),
        )
    ),
}


def parameters(radius_ratio: float) -> ZOConstantEParameters:
    return ZOConstantEParameters(
        black_hole_mass_msun=1.0e6,
        stellar_mass_msun=1.0,
        stellar_radius_rsun=1.0,
        circularization_efficiency=1.0,
        outer_to_inner_semimajor_axis=radius_ratio,
        eccentricity=0.0,
        opacity_cm2_g=0.34,
    )


def write_csv(path: Path, rows: list[dict[str, float | int | str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def coefficient_of_variation(values: np.ndarray) -> float:
    mean = float(np.mean(values))
    if mean == 0.0:
        raise ArithmeticError("coefficient of variation has a zero mean")
    return float(np.std(values, ddof=1) / abs(mean))


def strong_form_node_free_frequency(
    radius_ratio: float,
    delta_gr: float,
) -> tuple[float, float]:
    """独立积分线性 Eq. (44)，避免用病态窄环矩阵判断无节点极限。"""
    gamma = 4.0 / 3.0
    boundary_ratio = (4.0 * gamma - 3.0) / (2.0 * gamma - 1.0)
    second_derivative_coefficient = (2.0 * gamma - 1.0) / (2.0 * gamma)
    eccentricity_coefficient = (9.0 - 5.0 * gamma) / (2.0 * gamma)

    def integrate(frequency: float):
        def equation(x_value: float, state: np.ndarray) -> tuple[float, float]:
            eccentricity, derivative = state
            second_derivative = (
                frequency * x_value**1.5 * eccentricity
                + eccentricity_coefficient * eccentricity
                + second_derivative_coefficient * x_value * derivative
                - delta_gr / x_value * eccentricity
            ) / (second_derivative_coefficient * x_value**2)
            return derivative, second_derivative

        solution = solve_ivp(
            equation,
            (1.0, radius_ratio),
            (1.0, -boundary_ratio),
            method="DOP853",
            rtol=2.0e-12,
            atol=2.0e-14,
            max_step=(radius_ratio - 1.0) / 256.0,
        )
        if not solution.success:
            raise RuntimeError("strong-form node-free integration failed")
        return solution

    def residual(frequency: float) -> float:
        solution = integrate(frequency)
        return float(
            radius_ratio * solution.y[1, -1]
            + boundary_ratio * solution.y[0, -1]
        )

    frequency = float(brentq(residual, 0.0, 4.0, xtol=2.0e-13, rtol=2.0e-13))
    return frequency, abs(residual(frequency))


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    delta_gr = zo_precession_scales(parameters(1.3)).delta_gr
    eccentricity_nodes = np.linspace(0.0, 0.34, 29)
    nonlinearity_nodes = np.linspace(-0.50, 0.15, 49)
    table = build_zo_hamiltonian_spline_table(
        eccentricity_nodes,
        nonlinearity_nodes,
        anomaly_points=192,
    )

    continuation_rows: list[dict[str, float | int | str]] = []
    nonlinear_frequency: dict[float, np.ndarray] = {}
    for radius_ratio, published_points in PUBLISHED_FIGURE_7.items():
        frequencies = []
        frequency_guess = solve_zo_linear_apsidal_modes(
            parameters(radius_ratio),
            radial_points=512,
            mode_count=1,
        ).fundamental.dimensionless_frequency
        for inner_eccentricity, published_frequency in published_points:
            mode = solve_zo_nonlinear_apsidal_mode_bvp(
                table,
                inner_eccentricity=float(inner_eccentricity),
                outer_to_inner_semimajor_axis=radius_ratio,
                delta_gr=delta_gr,
                frequency_guess=frequency_guess,
                radial_points=192,
                relative_tolerance=3.0e-6,
            )
            frequency_guess = mode.dimensionless_frequency
            frequencies.append(mode.dimensionless_frequency)
            discrepancy = published_frequency - mode.dimensionless_frequency
            continuation_rows.append(
                {
                    "radius_ratio": radius_ratio,
                    "inner_eccentricity": inner_eccentricity,
                    "published_frequency_digitized": published_frequency,
                    "three_dimensional_nonlinear_frequency": mode.dimensionless_frequency,
                    "published_minus_three_dimensional": discrepancy,
                    "eccentricity_scaled_discrepancy": inner_eccentricity
                    * discrepancy,
                    "outer_eccentricity": float(mode.eccentricity[-1]),
                    "outer_boundary_residual": mode.outer_boundary_residual,
                    "radial_node_count": mode.radial_node_count,
                }
            )
        nonlinear_frequency[radius_ratio] = np.array(frequencies)

    bias_fit_rows: list[dict[str, float | int | str]] = []
    for radius_ratio, published_points in PUBLISHED_FIGURE_7.items():
        eccentricity = published_points[:, 0]
        discrepancy = (
            published_points[:, 1] - nonlinear_frequency[radius_ratio]
        )
        design = np.column_stack((1.0 / eccentricity, np.ones_like(eccentricity)))
        coefficient, _, _, _ = np.linalg.lstsq(design, discrepancy, rcond=None)
        fitted = design @ coefficient
        residual_sum = float(np.sum((discrepancy - fitted) ** 2))
        total_sum = float(np.sum((discrepancy - np.mean(discrepancy)) ** 2))
        r_squared = 1.0 - residual_sum / total_sum
        scaled = eccentricity * discrepancy
        bias_fit_rows.append(
            {
                "radius_ratio": radius_ratio,
                "inverse_e_coefficient": float(coefficient[0]),
                "constant_coefficient": float(coefficient[1]),
                "r_squared": r_squared,
                "mean_eccentricity_scaled_discrepancy": float(np.mean(scaled)),
                "scaled_discrepancy_coefficient_of_variation": coefficient_of_variation(
                    scaled
                ),
            }
        )

    # 中文：同一正无节点初形配以宽频率猜测，检验配点法是否被初值锁在伪支上。
    initial_guess_rows: list[dict[str, float | int | str]] = []
    reference_eccentricity = 0.2 * np.sqrt(0.92)
    for radius_ratio in (1.3, 4.0):
        for frequency_guess in (-3.0, -0.7, 0.0, 2.0, 5.0):
            try:
                mode = solve_zo_nonlinear_apsidal_mode_bvp(
                    table,
                    inner_eccentricity=reference_eccentricity,
                    outer_to_inner_semimajor_axis=radius_ratio,
                    delta_gr=delta_gr,
                    frequency_guess=frequency_guess,
                    radial_points=192,
                    relative_tolerance=3.0e-6,
                )
            except PhysicalDomainError as error:
                initial_guess_rows.append(
                    {
                        "radius_ratio": radius_ratio,
                        "input_frequency_guess": frequency_guess,
                        "status": "rejected",
                        "converged_frequency": "",
                        "outer_eccentricity": "",
                        "outer_boundary_residual": "",
                        "radial_node_count": "",
                        "rejection_reason": str(error),
                    }
                )
            else:
                initial_guess_rows.append(
                    {
                        "radius_ratio": radius_ratio,
                        "input_frequency_guess": frequency_guess,
                        "status": "converged",
                        "converged_frequency": mode.dimensionless_frequency,
                        "outer_eccentricity": float(mode.eccentricity[-1]),
                        "outer_boundary_residual": mode.outer_boundary_residual,
                        "radial_node_count": mode.radial_node_count,
                        "rejection_reason": "",
                    }
                )

    narrow_ratio = np.array((1.001, 1.003, 1.01, 1.03, 1.10, 1.30, 2.0, 4.0))
    spectrum_rows: list[dict[str, float | int | str]] = []
    for radius_ratio in narrow_ratio:
        strong_frequency, strong_residual = strong_form_node_free_frequency(
            float(radius_ratio), delta_gr
        )
        spectrum_rows.append(
            {
                "radius_ratio": radius_ratio,
                "annulus_fractional_width": radius_ratio - 1.0,
                "method": "strong_form",
                "radial_node_count": 0,
                "dimensionless_frequency": strong_frequency,
                "residual": strong_residual,
            }
        )
        spectrum = solve_zo_linear_apsidal_modes(
            parameters(float(radius_ratio)),
            radial_points=512,
            mode_count=3,
        )
        for mode in spectrum.modes:
            spectrum_rows.append(
                {
                    "radius_ratio": radius_ratio,
                    "annulus_fractional_width": radius_ratio - 1.0,
                    "method": "galerkin",
                    "radial_node_count": mode.radial_node_count,
                    "dimensionless_frequency": mode.dimensionless_frequency,
                    "residual": mode.generalized_residual,
                }
            )

    write_csv(
        OUTPUT / "phase5b3a_published_frequency_continuation.csv",
        continuation_rows,
    )
    write_csv(OUTPUT / "phase5b3a_inverse_bias_fit.csv", bias_fit_rows)
    write_csv(
        OUTPUT / "phase5b3a_frequency_guess_robustness.csv",
        initial_guess_rows,
    )
    write_csv(OUTPUT / "phase5b3a_linear_branch_spectrum.csv", spectrum_rows)

    converged_by_ratio: dict[float, list[float]] = {}
    for row in initial_guess_rows:
        if row["status"] != "converged":
            continue
        converged_by_ratio.setdefault(float(row["radius_ratio"]), []).append(
            float(row["converged_frequency"])
        )
    maximum_guess_spread = max(
        max(values) - min(values) for values in converged_by_ratio.values()
    )
    maximum_boundary_residual = max(
        abs(float(row["outer_boundary_residual"])) for row in continuation_rows
    )
    maximum_boundary_residual = max(
        maximum_boundary_residual,
        max(
            abs(float(row["outer_boundary_residual"]))
            for row in initial_guess_rows
            if row["status"] == "converged"
        ),
    )
    rejected_initial_guess_count = sum(
        row["status"] == "rejected" for row in initial_guess_rows
    )
    minimum_nonlinear_frequency = min(
        float(row["three_dimensional_nonlinear_frequency"])
        for row in continuation_rows
    )
    maximum_bias_r_squared = max(
        float(row["r_squared"]) for row in bias_fit_rows
    )
    minimum_bias_r_squared = min(
        float(row["r_squared"]) for row in bias_fit_rows
    )
    maximum_strong_galerkin_difference = max(
        abs(
            next(
                float(row["dimensionless_frequency"])
                for row in spectrum_rows
                if row["radius_ratio"] == radius_ratio
                and row["method"] == "strong_form"
            )
            / next(
                float(row["dimensionless_frequency"])
                for row in spectrum_rows
                if row["radius_ratio"] == radius_ratio
                and row["method"] == "galerkin"
                and row["radial_node_count"] == 0
            )
            - 1.0
        )
        for radius_ratio in narrow_ratio
    )
    report = {
        "phase": "5B3a",
        "evidence": "[L/V/A/O]",
        "published_source": "ZO 2020 Fig. 7 vector paths from the arXiv source bundle",
        "delta_gr": delta_gr,
        "continuation_state_count": len(continuation_rows),
        "minimum_three_dimensional_nonlinear_frequency": minimum_nonlinear_frequency,
        "maximum_absolute_outer_boundary_residual": maximum_boundary_residual,
        "maximum_frequency_spread_across_initial_guesses": maximum_guess_spread,
        "rejected_initial_frequency_guess_count": rejected_initial_guess_count,
        "minimum_inverse_e_fit_r_squared": minimum_bias_r_squared,
        "maximum_inverse_e_fit_r_squared": maximum_bias_r_squared,
        "maximum_strong_galerkin_node_free_relative_difference": maximum_strong_galerkin_difference,
        "node_free_branch_stays_finite_and_positive": bool(
            minimum_nonlinear_frequency > 0.0
        ),
        "published_branch_reproduced": False,
        "inverse_e_like_discrepancy_is_diagnostic_only": True,
        "branch_tracking_explains_published_curve": False,
        "phase_to_time_mapping_authorized": False,
        "interpretation": (
            "The converged 3D node-free branch remains finite and positive over the "
            "digitized Fig. 7 range. Published-minus-computed discrepancies can look "
            "approximately affine in 1/e, but this does not identify which Hamiltonian "
            "derivative or unpublished implementation detail produced them."
        ),
    }
    (OUTPUT / "phase5b3a_published_branch_inverse_audit_report.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )

    colors = {1.3: "#0072B2", 2.0: "#009E73", 4.0: "#D55E00"}
    figure, axes = plt.subplots(1, 2, figsize=(11.4, 4.5), constrained_layout=True)
    for radius_ratio, published_points in PUBLISHED_FIGURE_7.items():
        color = colors[radius_ratio]
        axes[0].plot(
            published_points[:, 0],
            published_points[:, 1],
            marker="o",
            color=color,
            linestyle="--",
            label=f"Published R={radius_ratio:g}",
        )
        axes[0].plot(
            published_points[:, 0],
            nonlinear_frequency[radius_ratio],
            marker="s",
            color=color,
            linestyle="-",
            label=f"3D Eq. (38) R={radius_ratio:g}",
        )
        discrepancy = (
            published_points[:, 1] - nonlinear_frequency[radius_ratio]
        )
        axes[1].plot(
            published_points[:, 0],
            published_points[:, 0] * discrepancy,
            marker="o",
            color=color,
            label=f"R={radius_ratio:g}",
        )
    axes[0].axhline(0.0, color="0.35", linewidth=0.8)
    axes[0].set_xlabel("Inner eccentricity")
    axes[0].set_ylabel("Dimensionless precession frequency")
    axes[0].set_title("Published curve versus 3D continuation")
    axes[0].legend(frameon=False, fontsize=7.8, ncol=2)
    axes[1].axhline(0.0, color="0.35", linewidth=0.8)
    axes[1].set_xlabel("Inner eccentricity")
    axes[1].set_ylabel("e_in × (published − 3D)")
    axes[1].set_title("Inverse-e bias diagnostic")
    axes[1].legend(frameon=False)
    for axis in axes:
        axis.grid(alpha=0.22)
    figure.savefig(OUTPUT / "phase5b3a_published_branch_inverse_audit.png", dpi=220)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8.2, 4.8), constrained_layout=True)
    for node_count, marker, color in (
        (0, "o", "#0072B2"),
        (1, "s", "#D55E00"),
        (2, "^", "#CC79A7"),
    ):
        selected = [
            row
            for row in spectrum_rows
            if row["radial_node_count"] == node_count
            and (
                row["method"] == "strong_form"
                if node_count == 0
                else row["method"] == "galerkin"
            )
        ]
        width = np.array([float(row["annulus_fractional_width"]) for row in selected])
        frequency = np.array([float(row["dimensionless_frequency"]) for row in selected])
        axis.plot(
            width,
            np.abs(frequency),
            marker=marker,
            color=color,
            label=f"{node_count} radial node" + ("" if node_count == 1 else "s"),
        )
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set_xlabel("Fractional annulus width  a_out / a_in − 1")
    axis.set_ylabel("Absolute dimensionless frequency")
    axis.set_title("Narrow-annulus linear branch topology")
    axis.grid(alpha=0.22, which="both")
    axis.legend(frameon=False)
    figure.savefig(OUTPUT / "phase5b3a_linear_branch_topology.png", dpi=220)
    plt.close(figure)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
