"""Phase 5B3b：完整二维非线性 Hamiltonian 的已发表分支诊断。"""

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
    build_ol_2d_hamiltonian_spline_table,
    ol_untwisted_2d_dimensionless_hamiltonian,
    solve_zo_nonlinear_apsidal_mode_bvp,
    zo_precession_scales,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"

# 中文：频率来自 ZO 2020 Fig. 7 矢量曲线；R=3 点来自 Fig. 6 标注。
PUBLISHED_REFERENCE_FREQUENCIES = {
    1.3: -0.717061649,
    2.0: 0.054825944,
    3.0: 0.13,
    4.0: 0.133727689,
}

# 中文：模形点来自 ZO 2020 Fig. 6 矢量路径，不是本脚本拟合值。
PUBLISHED_MODE_PROFILES = {
    1.3: np.array(
        (
            (1.0, 0.191833002038),
            (1.10122026924, 0.179398002610),
            (1.19609729144, 0.166500998851),
            (1.27718061007, 0.154382002300),
            (1.29999965698, 0.150779000035),
        )
    ),
    3.0: np.array(
        (
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


def solve_two_dimensional_linear_control(
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
            f_gradient = (
                derivative_e
                - eccentricity_gradient * coefficient_ef
                + 3.0 * derivative_f
                - delta_gr / x_value * eccentricity
                + frequency * x_value**1.5 * eccentricity
            ) / (x_value * 2.0 * coefficient_f2)
            second_derivative = (f_gradient - 2.0 * derivative) / x_value
            return derivative, second_derivative

        solution = solve_ivp(
            equation,
            (1.0, radius_ratio),
            (inner_eccentricity, boundary_slope * inner_eccentricity),
            method="DOP853",
            t_eval=grid,
            rtol=2.0e-11,
            atol=2.0e-13,
            max_step=(radius_ratio - 1.0) / 128.0,
        )
        if not solution.success or not np.all(np.isfinite(solution.y)):
            raise RuntimeError("2D linear control integration failed")
        return solution

    def residual(frequency: float) -> float:
        solution = integrate(frequency, output=False)
        eccentricity = float(solution.y[0, -1])
        derivative = float(solution.y[1, -1])
        f_value = eccentricity + radius_ratio * derivative
        return coefficient_ef * eccentricity + 2.0 * coefficient_f2 * f_value

    # 中文：宽盘可含多个有节点根。
    # 中文：逐段找根后只保留正无节点支。
    scan = np.linspace(-1.5, 0.5, 401)
    scan_residual = np.array([residual(value) for value in scan])
    roots = []
    for index in range(scan.size - 1):
        if scan_residual[index] == 0.0:
            roots.append(float(scan[index]))
        elif scan_residual[index] * scan_residual[index + 1] < 0.0:
            roots.append(
                float(
                    brentq(
                        residual,
                        float(scan[index]),
                        float(scan[index + 1]),
                        xtol=2.0e-13,
                        rtol=2.0e-13,
                    )
                )
            )
    for frequency in sorted(roots, reverse=True):
        solution = integrate(frequency, output=True)
        if np.all(solution.y[0] > 0.0):
            return frequency, solution.t, solution.y[0]
    raise RuntimeError("2D linear control scan found no node-free root")


def direct_derivative_vector(
    eccentricity: float,
    f_value: float,
    *,
    step: float = 2.0e-4,
    anomaly_points: int = 1024,
) -> np.ndarray:
    """用五点中心模板直接复算 ``(F_e,F_f,F_ef,F_ff)``。"""
    values: dict[tuple[int, int], float] = {}

    def evaluate(offset_e: int, offset_f: int) -> float:
        key = (offset_e, offset_f)
        if key not in values:
            values[key] = ol_untwisted_2d_dimensionless_hamiltonian(
                eccentricity + offset_e * step,
                f_value + offset_f * step,
                anomaly_points=anomaly_points,
            )
        return values[key]

    weights = dict(zip((-2, -1, 1, 2), (1.0, -8.0, 8.0, -1.0), strict=True))
    derivative_e = sum(
        weight * evaluate(offset, 0) for offset, weight in weights.items()
    ) / (12.0 * step)
    derivative_f = sum(
        weight * evaluate(0, offset) for offset, weight in weights.items()
    ) / (12.0 * step)
    mixed = sum(
        weight_e * weight_f * evaluate(offset_e, offset_f)
        for offset_e, weight_e in weights.items()
        for offset_f, weight_f in weights.items()
    ) / (144.0 * step**2)
    second_f = (
        -evaluate(0, 2)
        + 16.0 * evaluate(0, 1)
        - 30.0 * evaluate(0, 0)
        + 16.0 * evaluate(0, -1)
        - evaluate(0, -2)
    ) / (12.0 * step**2)
    return np.array((derivative_e, derivative_f, mixed, second_f))


def three_dimensional_reference_frequency() -> dict[float, float]:
    rows: dict[float, float] = {}
    with (
        OUTPUT / "phase5b3a_published_frequency_continuation.csv"
    ).open(newline="") as handle:
        for row in csv.DictReader(handle):
            eccentricity = float(row["inner_eccentricity"])
            if abs(eccentricity - 0.1918332609) < 1.0e-10:
                rows[float(row["radius_ratio"])] = float(
                    row["three_dimensional_nonlinear_frequency"]
                )
    return rows


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    inner_eccentricity = 0.2 * np.sqrt(0.92)
    delta_gr = zo_precession_scales(parameters(1.3)).delta_gr

    quadratic_rows: list[dict[str, float | int | str]] = []
    expected_hessian = np.array((2.0 / 3.0, -1.0 / 6.0, 2.0 / 3.0))
    for step in (1.0e-2, 3.0e-3, 1.0e-3, 3.0e-4):
        central = ol_untwisted_2d_dimensionless_hamiltonian(0.0, 0.0)
        second_e = (
            ol_untwisted_2d_dimensionless_hamiltonian(step, 0.0)
            - 2.0 * central
            + ol_untwisted_2d_dimensionless_hamiltonian(-step, 0.0)
        ) / step**2
        second_f = (
            ol_untwisted_2d_dimensionless_hamiltonian(0.0, step)
            - 2.0 * central
            + ol_untwisted_2d_dimensionless_hamiltonian(0.0, -step)
        ) / step**2
        mixed = (
            ol_untwisted_2d_dimensionless_hamiltonian(step, step)
            - ol_untwisted_2d_dimensionless_hamiltonian(step, -step)
            - ol_untwisted_2d_dimensionless_hamiltonian(-step, step)
            + ol_untwisted_2d_dimensionless_hamiltonian(-step, -step)
        ) / (4.0 * step**2)
        measured = np.array((second_e, mixed, second_f))
        relative_error = float(
            np.linalg.norm(measured - expected_hessian)
            / np.linalg.norm(expected_hessian)
        )
        quadratic_rows.append(
            {
                "finite_difference_step": step,
                "second_derivative_ee": second_e,
                "second_derivative_ef": mixed,
                "second_derivative_ff": second_f,
                "relative_hessian_error": relative_error,
            }
        )

    quadrature_rows: list[dict[str, float | int | str]] = []
    quadrature_states = ((0.191833, 0.08), (0.30, -0.10), (0.65, 0.25))
    for eccentricity, f_value in quadrature_states:
        previous = None
        for anomaly_points in (64, 128, 256, 512):
            value = ol_untwisted_2d_dimensionless_hamiltonian(
                eccentricity, f_value, anomaly_points=anomaly_points
            )
            relative_change = (
                "" if previous is None else abs(value / previous - 1.0)
            )
            quadrature_rows.append(
                {
                    "eccentricity": eccentricity,
                    "eccentricity_plus_gradient": f_value,
                    "anomaly_points": anomaly_points,
                    "dimensionless_hamiltonian": value,
                    "relative_change_from_previous": relative_change,
                }
            )
            previous = value

    table_specs = ((21, 41, 256), (29, 65, 512))
    convergence_rows: list[dict[str, float | int | str]] = []
    fine_modes = {}
    fine_table = None
    linear_controls = {
        ratio: solve_two_dimensional_linear_control(
            ratio, inner_eccentricity, delta_gr
        )
        for ratio in (1.3, 2.0, 3.0, 4.0)
    }
    for eccentricity_points, nonlinearity_points, anomaly_points in table_specs:
        table = build_ol_2d_hamiltonian_spline_table(
            np.linspace(0.0, 0.30, eccentricity_points),
            np.linspace(-0.50, 0.15, nonlinearity_points),
            anomaly_points=anomaly_points,
        )
        for radius_ratio in (1.3, 2.0, 3.0, 4.0):
            mode = solve_zo_nonlinear_apsidal_mode_bvp(
                table,
                inner_eccentricity=inner_eccentricity,
                outer_to_inner_semimajor_axis=radius_ratio,
                delta_gr=delta_gr,
                frequency_guess=linear_controls[radius_ratio][0],
                radial_points=192,
                relative_tolerance=3.0e-7,
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
        raise RuntimeError("fine 2D Hamiltonian table was not constructed")

    derivative_rows: list[dict[str, float | int | str]] = []
    derivative_errors = []
    for radius_ratio in (1.3, 3.0):
        mode = fine_modes[radius_ratio]
        for location, index in (
            ("inner", 0),
            ("middle", mode.eccentricity.size // 2),
            ("outer", mode.eccentricity.size - 1),
        ):
            eccentricity = float(mode.eccentricity[index])
            f_value = float(mode.eccentricity_plus_gradient[index])
            interpolated = fine_table.evaluate_e_f(eccentricity, f_value)
            interpolated_vector = np.array(
                (
                    interpolated.derivative_e_at_fixed_f,
                    interpolated.derivative_f_at_fixed_e,
                    interpolated.second_derivative_ef,
                    interpolated.second_derivative_ff,
                )
            )
            direct_vector = direct_derivative_vector(eccentricity, f_value)
            relative_error = float(
                np.linalg.norm(interpolated_vector - direct_vector)
                / np.linalg.norm(direct_vector)
            )
            derivative_errors.append(relative_error)
            derivative_rows.append(
                {
                    "radius_ratio": radius_ratio,
                    "location": location,
                    "eccentricity": eccentricity,
                    "eccentricity_plus_gradient": f_value,
                    "relative_derivative_vector_error": relative_error,
                }
            )

    benchmark_rows: list[dict[str, float | int | str]] = []
    profile_errors = []
    frequency_errors = []
    for radius_ratio, mode in fine_modes.items():
        published_frequency = PUBLISHED_REFERENCE_FREQUENCIES[radius_ratio]
        frequency_error = abs(mode.dimensionless_frequency - published_frequency)
        frequency_errors.append(frequency_error)
        profile_max_error = ""
        profile_rms_error = ""
        if radius_ratio in PUBLISHED_MODE_PROFILES:
            published_profile = PUBLISHED_MODE_PROFILES[radius_ratio]
            numerical_at_published = np.interp(
                published_profile[:, 0],
                mode.dimensionless_semimajor_axis,
                mode.eccentricity,
            )
            residual = numerical_at_published - published_profile[:, 1]
            profile_max_error = float(
                np.max(np.abs(residual)) / inner_eccentricity
            )
            profile_rms_error = float(
                np.sqrt(np.mean(residual**2)) / inner_eccentricity
            )
            profile_errors.append(profile_max_error)
        benchmark_rows.append(
            {
                "radius_ratio": radius_ratio,
                "published_frequency": published_frequency,
                "two_dimensional_linear_frequency": linear_controls[radius_ratio][0],
                "two_dimensional_nonlinear_frequency": mode.dimensionless_frequency,
                "nonlinear_minus_linear_frequency": (
                    mode.dimensionless_frequency
                    - linear_controls[radius_ratio][0]
                ),
                "absolute_published_frequency_error": frequency_error,
                "outer_eccentricity": float(mode.eccentricity[-1]),
                "profile_max_error_over_inner_e": profile_max_error,
                "profile_rms_error_over_inner_e": profile_rms_error,
            }
        )

    coarse = {
        float(row["radius_ratio"]): row
        for row in convergence_rows
        if row["eccentricity_points"] == table_specs[0][0]
    }
    fine = {
        float(row["radius_ratio"]): row
        for row in convergence_rows
        if row["eccentricity_points"] == table_specs[-1][0]
    }
    maximum_frequency_change = max(
        abs(
            float(fine[ratio]["dimensionless_frequency"])
            / float(coarse[ratio]["dimensionless_frequency"])
            - 1.0
        )
        for ratio in fine
    )
    maximum_outer_change = max(
        abs(
            float(fine[ratio]["outer_eccentricity"])
            / float(coarse[ratio]["outer_eccentricity"])
            - 1.0
        )
        for ratio in fine
    )
    maximum_boundary_residual = max(
        abs(float(row["outer_boundary_residual"]))
        for row in convergence_rows
    )
    final_quadratic_error = float(quadratic_rows[-1]["relative_hessian_error"])
    quadrature_changes = [
        float(row["relative_change_from_previous"])
        for row in quadrature_rows
        if row["relative_change_from_previous"] != ""
    ]
    maximum_quadrature_change = max(quadrature_changes)
    maximum_derivative_error = max(derivative_errors)
    maximum_frequency_error = max(frequency_errors)
    maximum_profile_error = max(profile_errors)
    equation_internal_gate = bool(
        final_quadratic_error < 1.0e-5
        and maximum_quadrature_change < 1.0e-10
        and maximum_frequency_change < 1.0e-4
        and maximum_outer_change < 1.0e-4
        and maximum_derivative_error < 1.0e-3
        and maximum_boundary_residual < 1.0e-8
    )
    published_frequency_gate = maximum_frequency_error < 0.05
    published_profile_gate = maximum_profile_error < 0.05
    nonlinear_explanation_gate = bool(
        equation_internal_gate
        and published_frequency_gate
        and published_profile_gate
    )

    write_csv(OUTPUT / "phase5b3b_quadratic_limit.csv", quadratic_rows)
    write_csv(OUTPUT / "phase5b3b_orbit_quadrature.csv", quadrature_rows)
    write_csv(OUTPUT / "phase5b3b_2d_table_convergence.csv", convergence_rows)
    write_csv(OUTPUT / "phase5b3b_2d_derivative_holdout.csv", derivative_rows)
    write_csv(OUTPUT / "phase5b3b_published_comparison.csv", benchmark_rows)

    report = {
        "phase": "5B3b full 2D nonlinear Hamiltonian diagnostic",
        "evidence": "[L]+[V]+[A-diagnostic]",
        "inner_eccentricity": inner_eccentricity,
        "delta_gr": delta_gr,
        "source_formula": "Ogilvie & Lynch 2019 Eqs. (33), (B4), and (40)",
        "maximum_relative_quadratic_hessian_error": final_quadratic_error,
        "maximum_relative_orbit_quadrature_change": maximum_quadrature_change,
        "maximum_relative_frequency_table_change": maximum_frequency_change,
        "maximum_relative_outer_eccentricity_table_change": maximum_outer_change,
        "maximum_relative_derivative_holdout_error": maximum_derivative_error,
        "maximum_absolute_outer_boundary_residual": maximum_boundary_residual,
        "maximum_absolute_published_frequency_error": maximum_frequency_error,
        "maximum_profile_error_over_inner_e": maximum_profile_error,
        "equation_internal_gate": equation_internal_gate,
        "published_frequency_gate": published_frequency_gate,
        "published_profile_gate": published_profile_gate,
        "full_2d_nonlinearity_explains_published_branch": nonlinear_explanation_gate,
        "formal_zo_source_model_changed": False,
        "phase_to_time_mapping_authorized": False,
        "interpretation": (
            "The recovered full 2D Hamiltonian passes its internal limits, but its "
            "node-free frequencies remain close to the 2D linear control and do not "
            "recover the published ZO branch. Two-dimensional nonlinear pressure "
            "therefore does not explain the benchmark discrepancy."
        ),
    }
    (OUTPUT / "phase5b3b_full_2d_nonlinear_report.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )

    three_dimensional = three_dimensional_reference_frequency()
    figure, axes = plt.subplots(2, 2, figsize=(11.2, 8.0))
    ratios = np.array((1.3, 2.0, 4.0))
    axes[0, 0].plot(
        ratios,
        [PUBLISHED_REFERENCE_FREQUENCIES[ratio] for ratio in ratios],
        "o-",
        label="Published ZO 2020",
    )
    axes[0, 0].plot(
        ratios,
        [linear_controls[ratio][0] for ratio in ratios],
        "s--",
        label="2D linear",
    )
    axes[0, 0].plot(
        ratios,
        [fine_modes[ratio].dimensionless_frequency for ratio in ratios],
        "D-.",
        label="2D full nonlinear",
    )
    axes[0, 0].plot(
        ratios,
        [three_dimensional[ratio] for ratio in ratios],
        "^-",
        label="3D full nonlinear",
    )
    axes[0, 0].axhline(0.0, color="0.45", linewidth=0.8)
    axes[0, 0].set_xlabel("Outer-to-inner semimajor-axis ratio")
    axes[0, 0].set_ylabel("Dimensionless precession frequency")
    axes[0, 0].set_title("Reference-amplitude frequency")
    axes[0, 0].legend(fontsize=8)

    for column, radius_ratio in enumerate((1.3, 3.0)):
        axis = axes[0 if column == 0 else 1, 1]
        if column == 0:
            axis = axes[0, 1]
        else:
            axis = axes[1, 0]
        published = PUBLISHED_MODE_PROFILES[radius_ratio]
        mode = fine_modes[radius_ratio]
        linear = linear_controls[radius_ratio]
        axis.plot(
            published[:, 0],
            published[:, 1] / inner_eccentricity,
            "o",
            label="Published ZO 2020",
        )
        axis.plot(
            linear[1],
            linear[2] / inner_eccentricity,
            "--",
            label="2D linear",
        )
        axis.plot(
            mode.dimensionless_semimajor_axis,
            mode.eccentricity / inner_eccentricity,
            "-",
            label="2D full nonlinear",
        )
        axis.set_xlabel("Scaled semimajor axis")
        axis.set_ylabel("Normalized eccentricity")
        axis.set_title(f"Mode shape: radius ratio {radius_ratio:g}")
        axis.legend(fontsize=8)

    benchmark_ratio = np.array((1.3, 2.0, 3.0, 4.0))
    nonlinear_correction = np.array(
        [
            fine_modes[ratio].dimensionless_frequency
            - linear_controls[ratio][0]
            for ratio in benchmark_ratio
        ]
    )
    axes[1, 1].plot(benchmark_ratio, nonlinear_correction, "o-")
    axes[1, 1].axhline(0.0, color="0.45", linewidth=0.8)
    axes[1, 1].set_xlabel("Outer-to-inner semimajor-axis ratio")
    axes[1, 1].set_ylabel("Full 2D minus linear frequency")
    axes[1, 1].set_title("Size of the 2D nonlinear correction")
    figure.suptitle("Phase 5B3b: full 2D nonlinear branch diagnostic")
    figure.tight_layout()
    figure.savefig(
        OUTPUT / "phase5b3b_full_2d_nonlinear_diagnostic.png", dpi=180
    )
    plt.close(figure)


if __name__ == "__main__":
    main()
