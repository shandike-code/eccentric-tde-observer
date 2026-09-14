"""Phase 5B3：ZO 三维非线性拱点模与原文 Fig. 6/7 基准门。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from eccentric_tde_observer import (
    ZOConstantEParameters,
    build_zo_hamiltonian_spline_table,
    finite_difference_zo_hamiltonian_derivatives,
    solve_zo_linear_apsidal_modes,
    solve_zo_nonlinear_apsidal_mode_bvp,
    zo_precession_scales,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


PUBLISHED_FIGURE_6 = {
    1.3: {
        "frequency": -0.71,
        "path": np.array(
            [
                (1.0, 0.191833002038),
                (1.10122026924, 0.179398002610),
                (1.19609729144, 0.166500998851),
                (1.27718061007, 0.154382002300),
                (1.29999965698, 0.150779000035),
            ]
        ),
    },
    3.0: {
        "frequency": 0.13,
        "path": np.array(
            [
                (1.0, 0.191833002038),
                (1.09186691308, 0.181669001809),
                (1.19217336636, 0.171750000390),
                (1.30169466153, 0.162055000314),
                (1.42518552734, 0.152270000368),
                (1.56039345215, 0.142674998478),
                (1.71312639492, 0.132960001766),
                (1.88598267604, 0.123103001925),
                (2.08198965600, 0.113071001505),
                (2.30468728380, 0.102810000583),
                (2.56526041079, 0.091962001350),
                (2.87102755728, 0.080382103264),
                (2.99999312820, 0.075773699625),
            ]
        ),
    },
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


def two_dimensional_linear_control(
    radius_ratio: float,
    inner_eccentricity: float,
    delta_gr: float,
) -> tuple[float, np.ndarray, np.ndarray]:
    """独立求解 OL Eq. (41) 的二维线性自由边界控制。"""
    gamma = 4.0 / 3.0
    coefficient_e2 = gamma / 4.0
    coefficient_ef = (1.0 - gamma) / 2.0
    coefficient_f2 = gamma / 4.0
    boundary_slope = -1.0 / gamma

    def integrate(frequency: float, *, output: bool):
        grid = np.linspace(1.0, radius_ratio, 512) if output else None

        def equation(x_value: float, state: np.ndarray) -> tuple[float, float]:
            eccentricity, derivative = state
            f_value = eccentricity + x_value * derivative
            eccentricity_gradient = f_value - eccentricity
            derivative_e = (
                2.0 * coefficient_e2 * eccentricity
                + coefficient_ef * f_value
            )
            derivative_f = (
                coefficient_ef * eccentricity
                + 2.0 * coefficient_f2 * f_value
            )
            second_ef = coefficient_ef
            second_ff = 2.0 * coefficient_f2
            f_gradient = (
                derivative_e
                - eccentricity_gradient * second_ef
                + 3.0 * derivative_f
                - delta_gr / x_value * eccentricity
                + frequency * x_value**1.5 * eccentricity
            ) / (x_value * second_ff)
            second_derivative = (f_gradient - 2.0 * derivative) / x_value
            return derivative, second_derivative

        return solve_ivp(
            equation,
            (1.0, radius_ratio),
            (inner_eccentricity, boundary_slope * inner_eccentricity),
            method="DOP853",
            t_eval=grid,
            rtol=2.0e-11,
            atol=2.0e-13,
            max_step=(radius_ratio - 1.0) / 128.0,
        )

    def residual(frequency: float) -> float:
        solution = integrate(frequency, output=False)
        eccentricity = float(solution.y[0, -1])
        derivative = float(solution.y[1, -1])
        f_value = eccentricity + radius_ratio * derivative
        return coefficient_ef * eccentricity + 2.0 * coefficient_f2 * f_value

    frequency = float(brentq(residual, -1.5, 0.5))
    solution = integrate(frequency, output=True)
    return frequency, solution.t, solution.y[0]


def write_csv(path: Path, rows: list[dict[str, float | int | str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    inner_eccentricity = 0.2 * np.sqrt(0.92)
    delta_gr = zo_precession_scales(parameters(1.3)).delta_gr
    table_specs = (
        (17, 33, 128),
        (25, 49, 192),
    )
    convergence_rows: list[dict[str, float | int | str]] = []
    fine_modes = {}
    fine_table = None
    for eccentricity_points, nonlinearity_points, anomaly_points in table_specs:
        table = build_zo_hamiltonian_spline_table(
            np.linspace(0.0, 0.30, eccentricity_points),
            np.linspace(-0.50, 0.15, nonlinearity_points),
            anomaly_points=anomaly_points,
        )
        for radius_ratio, frequency_guess in ((1.3, 1.73), (3.0, 1.48)):
            mode = solve_zo_nonlinear_apsidal_mode_bvp(
                table,
                inner_eccentricity=inner_eccentricity,
                outer_to_inner_semimajor_axis=radius_ratio,
                delta_gr=delta_gr,
                frequency_guess=frequency_guess,
                radial_points=192,
                relative_tolerance=5.0e-6,
            )
            convergence_rows.append(
                {
                    "eccentricity_points": eccentricity_points,
                    "nonlinearity_points": nonlinearity_points,
                    "anomaly_points": anomaly_points,
                    "radius_ratio": radius_ratio,
                    "dimensionless_frequency": mode.dimensionless_frequency,
                    "outer_eccentricity": float(mode.eccentricity[-1]),
                    "outer_boundary_residual": mode.outer_boundary_residual,
                }
            )
            if eccentricity_points == table_specs[-1][0]:
                fine_modes[radius_ratio] = mode
                fine_table = table

    if fine_table is None:
        raise RuntimeError("fine Hamiltonian table was not constructed")
    derivative_rows: list[dict[str, float | int | str]] = []
    derivative_errors: list[float] = []
    for radius_ratio, mode in fine_modes.items():
        for location, index in (
            ("inner", 0),
            ("middle", mode.eccentricity.size // 2),
            ("outer", mode.eccentricity.size - 1),
        ):
            eccentricity_value = float(mode.eccentricity[index])
            f_value = float(mode.eccentricity_plus_gradient[index])
            interpolated = fine_table.evaluate_e_f(eccentricity_value, f_value)
            direct = finite_difference_zo_hamiltonian_derivatives(
                eccentricity_value,
                f_value,
                eccentricity_step=2.0e-4,
                eccentricity_plus_gradient_step=2.0e-4,
                anomaly_points=192,
            )
            interpolated_vector = np.array(
                (
                    interpolated.derivative_e_at_fixed_f,
                    interpolated.derivative_f_at_fixed_e,
                    interpolated.second_derivative_ef,
                    interpolated.second_derivative_ff,
                )
            )
            direct_vector = np.array(
                (
                    direct.derivative_e_at_fixed_f,
                    direct.derivative_f_at_fixed_e,
                    direct.second_derivative_ef,
                    direct.second_derivative_ff,
                )
            )
            relative_vector_error = float(
                np.linalg.norm(interpolated_vector - direct_vector)
                / np.linalg.norm(direct_vector)
            )
            derivative_errors.append(relative_vector_error)
            derivative_rows.append(
                {
                    "radius_ratio": radius_ratio,
                    "location": location,
                    "eccentricity": eccentricity_value,
                    "eccentricity_plus_gradient": f_value,
                    "relative_derivative_vector_error": relative_vector_error,
                }
            )

    comparison_rows: list[dict[str, float | int | str]] = []
    linear_modes = {}
    planar_controls = {}
    for radius_ratio in (1.3, 3.0):
        linear = solve_zo_linear_apsidal_modes(
            parameters(radius_ratio),
            radial_points=512,
            mode_count=8,
        ).fundamental
        linear_modes[radius_ratio] = linear
        planar_controls[radius_ratio] = two_dimensional_linear_control(
            radius_ratio, inner_eccentricity, delta_gr
        )
        nonlinear = fine_modes[radius_ratio]
        published = PUBLISHED_FIGURE_6[radius_ratio]
        comparison_rows.append(
            {
                "radius_ratio": radius_ratio,
                "published_frequency": published["frequency"],
                "three_dimensional_nonlinear_frequency": nonlinear.dimensionless_frequency,
                "three_dimensional_linear_frequency": linear.dimensionless_frequency,
                "two_dimensional_linear_frequency": planar_controls[radius_ratio][0],
                "published_outer_eccentricity": float(published["path"][-1, 1]),
                "three_dimensional_outer_eccentricity": float(nonlinear.eccentricity[-1]),
                "two_dimensional_outer_eccentricity": float(planar_controls[radius_ratio][2][-1]),
            }
        )

    write_csv(OUTPUT / "phase5b3_nonlinear_apsidal_convergence.csv", convergence_rows)
    write_csv(OUTPUT / "phase5b3_hamiltonian_derivative_holdout.csv", derivative_rows)
    write_csv(OUTPUT / "phase5b3_zo2020_fig6_comparison.csv", comparison_rows)

    coarse_by_ratio = {
        float(row["radius_ratio"]): row
        for row in convergence_rows
        if row["eccentricity_points"] == table_specs[0][0]
    }
    fine_by_ratio = {
        float(row["radius_ratio"]): row
        for row in convergence_rows
        if row["eccentricity_points"] == table_specs[-1][0]
    }
    max_frequency_change = max(
        abs(
            float(fine_by_ratio[ratio]["dimensionless_frequency"])
            / float(coarse_by_ratio[ratio]["dimensionless_frequency"])
            - 1.0
        )
        for ratio in (1.3, 3.0)
    )
    max_outer_eccentricity_change = max(
        abs(
            float(fine_by_ratio[ratio]["outer_eccentricity"])
            / float(coarse_by_ratio[ratio]["outer_eccentricity"])
            - 1.0
        )
        for ratio in (1.3, 3.0)
    )
    max_boundary_residual = max(
        abs(float(row["outer_boundary_residual"])) for row in convergence_rows
    )
    max_derivative_holdout_error = max(derivative_errors)
    report = {
        "phase": "5B3",
        "evidence": "[V]",
        "inner_eccentricity": inner_eccentricity,
        "delta_gr": delta_gr,
        "max_relative_frequency_table_change": max_frequency_change,
        "max_relative_outer_eccentricity_table_change": max_outer_eccentricity_change,
        "max_absolute_outer_boundary_residual": max_boundary_residual,
        "max_relative_derivative_holdout_error": max_derivative_holdout_error,
        "equation_internal_gate": bool(
            max_frequency_change < 1.0e-5
            and max_outer_eccentricity_change < 1.0e-5
            and max_boundary_residual < 1.0e-8
            and max_derivative_holdout_error < 1.0e-3
        ),
        "published_fig6_frequency_gate": False,
        "published_fig6_profile_gate": False,
        "published_fig7_circular_continuity_gate": False,
        "phase5b3_literature_benchmark_gate": False,
        "interpretation": (
            "The independent 3D Eq. (34)/(38) branch is converged and continuous with "
            "linear theory, but it does not reproduce the published Fig. 6/7 numerical "
            "curves; phase-to-time mapping remains blocked."
        ),
    }
    (OUTPUT / "phase5b3_nonlinear_apsidal_report.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )

    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.4), constrained_layout=True)
    for axis, radius_ratio in zip(axes, (1.3, 3.0), strict=True):
        published_path = PUBLISHED_FIGURE_6[radius_ratio]["path"]
        nonlinear = fine_modes[radius_ratio]
        planar_frequency, planar_radius, planar_eccentricity = planar_controls[
            radius_ratio
        ]
        axis.plot(
            published_path[:, 0],
            published_path[:, 1],
            color="black",
            linewidth=2.3,
            label="ZO 2020 Fig. 6 (digitized)",
        )
        axis.plot(
            nonlinear.dimensionless_semimajor_axis,
            nonlinear.eccentricity,
            color="#0072B2",
            linewidth=2.0,
            label="3D Eq. (34)/(38)",
        )
        axis.plot(
            planar_radius,
            planar_eccentricity,
            color="#D55E00",
            linestyle="--",
            linewidth=1.8,
            label="2D linear control",
        )
        axis.set_xlabel("Semimajor axis  a / a_in")
        axis.set_ylabel("Eccentricity  e")
        axis.set_title(f"Outer radius = {radius_ratio:g} a_in")
        axis.grid(alpha=0.22)
        axis.legend(frameon=False, fontsize=8.5)
    figure.savefig(OUTPUT / "phase5b3_fig6_profile_audit.png", dpi=220)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8.2, 4.8), constrained_layout=True)
    x_values = np.arange(2)
    width = 0.19
    series = (
        ("ZO 2020 Fig. 6", [row["published_frequency"] for row in comparison_rows]),
        (
            "3D nonlinear",
            [row["three_dimensional_nonlinear_frequency"] for row in comparison_rows],
        ),
        (
            "3D linear limit",
            [row["three_dimensional_linear_frequency"] for row in comparison_rows],
        ),
        (
            "2D linear control",
            [row["two_dimensional_linear_frequency"] for row in comparison_rows],
        ),
    )
    colors = ("black", "#0072B2", "#009E73", "#D55E00")
    for index, ((label, values), color) in enumerate(zip(series, colors, strict=True)):
        axis.bar(
            x_values + (index - 1.5) * width,
            values,
            width,
            label=label,
            color=color,
        )
    axis.axhline(0.0, color="0.35", linewidth=0.8)
    axis.set_xticks(x_values, ("a_out / a_in = 1.3", "a_out / a_in = 3"))
    axis.set_ylabel("Dimensionless precession frequency")
    axis.set_title("Low-amplitude apsidal benchmark")
    axis.legend(frameon=False, ncol=2, fontsize=8.5)
    axis.grid(axis="y", alpha=0.22)
    figure.savefig(OUTPUT / "phase5b3_frequency_benchmark.png", dpi=220)
    plt.close(figure)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
