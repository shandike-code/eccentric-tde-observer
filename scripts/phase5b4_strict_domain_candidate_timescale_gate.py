"""Phase 5B4：严格域源的方程自洽候选进动时标与模形兼容门。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from eccentric_tde_observer import (
    ZOConstantEParameters,
    ZOHamiltonianSplineTable,
    build_zo_hamiltonian_spline_table,
    finite_difference_zo_hamiltonian_derivatives,
    solve_zo_linear_apsidal_modes,
    solve_zo_nonlinear_apsidal_mode,
    solve_zo_nonlinear_apsidal_mode_bvp,
    zo_precession_scales,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
CASES = (
    ("atlas_reference", 0.60),
    ("strict_boundary_sensitivity", 0.65),
)
TABLE_SPECS = (
    (21, 41, 128),
    (31, 61, 192),
    (41, 81, 192),
)
SHAPE_COMPATIBILITY_THRESHOLDS = (0.02, 0.05, 0.10)


def parameters(eccentricity: float) -> ZOConstantEParameters:
    return ZOConstantEParameters(
        black_hole_mass_msun=1.0e6,
        stellar_mass_msun=1.0,
        stellar_radius_rsun=1.0,
        circularization_efficiency=0.01,
        outer_to_inner_semimajor_axis=2.0,
        eccentricity=eccentricity,
        opacity_cm2_g=0.34,
    )


def write_csv(path: Path, rows: list[dict[str, float | int | str]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table: {path}")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def printed_eq48_cycles_per_day(
    mode_frequency: float,
    model_parameters: ZOConstantEParameters,
) -> float:
    """返回论文 Eq. (48) 印刷归一化；仅作审计，不作为正式换算。"""
    efficiency = model_parameters.circularization_efficiency
    normalized_coefficient = (
        4.07e-3
        * efficiency
        * np.sqrt(1.0 + efficiency)
        * model_parameters.stellar_mass_msun
        / (
            model_parameters.stellar_radius_rsun**1.5
            * np.sqrt(model_parameters.black_hole_mass_msun / 1.0e6)
        )
    )
    return float(
        normalized_coefficient * mode_frequency / 0.1
    )


def derivative_vector(derivatives: object) -> np.ndarray:
    return np.array(
        (
            derivatives.derivative_e_at_fixed_f,
            derivatives.derivative_f_at_fixed_e,
            derivatives.second_derivative_ef,
            derivatives.second_derivative_ff,
        )
    )


def build_or_load_table(
    eccentricity_points: int,
    nonlinearity_points: int,
    anomaly_points: int,
) -> ZOHamiltonianSplineTable:
    """复用坐标完全一致的原始表值；不插值旧表或接受不匹配缓存。"""
    eccentricity_nodes = np.linspace(0.0, 0.75, eccentricity_points)
    nonlinearity_nodes = np.linspace(-0.75, 0.25, nonlinearity_points)
    cache_path = OUTPUT / (
        f"phase5b4_hamiltonian_table_{eccentricity_points}x"
        f"{nonlinearity_points}_a{anomaly_points}.npz"
    )
    if cache_path.exists():
        with np.load(cache_path) as cache:
            cached_eccentricity = cache["eccentricity_nodes"]
            cached_nonlinearity = cache["nonlinearity_nodes"]
            cached_values = cache["dimensionless_hamiltonian"]
        if (
            not np.array_equal(cached_eccentricity, eccentricity_nodes)
            or not np.array_equal(cached_nonlinearity, nonlinearity_nodes)
            or cached_values.shape
            != (eccentricity_points, nonlinearity_points)
            or not np.all(np.isfinite(cached_values))
        ):
            raise RuntimeError("Phase 5B4 Hamiltonian cache does not match its declared grid")
        return ZOHamiltonianSplineTable(
            eccentricity_nodes,
            nonlinearity_nodes,
            cached_values,
        )
    table = build_zo_hamiltonian_spline_table(
        eccentricity_nodes,
        nonlinearity_nodes,
        anomaly_points=anomaly_points,
    )
    np.savez(
        cache_path,
        eccentricity_nodes=table.eccentricity_nodes,
        nonlinearity_nodes=table.nonlinearity_nodes,
        dimensionless_hamiltonian=table.dimensionless_hamiltonian,
    )
    return table


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    scales = zo_precession_scales(parameters(CASES[0][1]))
    table_rows: list[dict[str, float | int | str]] = []
    fine_modes = {}
    fine_table = None
    tables_by_spec = {}
    modes_by_spec_and_case = {}

    for eccentricity_points, nonlinearity_points, anomaly_points in TABLE_SPECS:
        table = build_or_load_table(
            eccentricity_points,
            nonlinearity_points,
            anomaly_points,
        )
        table_spec = (eccentricity_points, nonlinearity_points, anomaly_points)
        tables_by_spec[table_spec] = table
        for case_name, inner_eccentricity in CASES:
            linear_frequency = solve_zo_linear_apsidal_modes(
                parameters(0.0),
                radial_points=512,
                mode_count=1,
            ).fundamental.dimensionless_frequency
            mode = solve_zo_nonlinear_apsidal_mode_bvp(
                table,
                inner_eccentricity=inner_eccentricity,
                outer_to_inner_semimajor_axis=2.0,
                delta_gr=scales.delta_gr,
                frequency_guess=linear_frequency,
                radial_points=256,
                relative_tolerance=3.0e-6,
            )
            table_rows.append(
                {
                    "case": case_name,
                    "inner_eccentricity": inner_eccentricity,
                    "eccentricity_points": eccentricity_points,
                    "nonlinearity_points": nonlinearity_points,
                    "anomaly_points": anomaly_points,
                    "dimensionless_frequency": mode.dimensionless_frequency,
                    "outer_eccentricity": float(mode.eccentricity[-1]),
                    "outer_boundary_residual": mode.outer_boundary_residual,
                    "minimum_orbital_nonlinearity": float(
                        np.min(mode.orbital_nonlinearity)
                    ),
                    "maximum_orbital_nonlinearity": float(
                        np.max(mode.orbital_nonlinearity)
                    ),
                }
            )
            modes_by_spec_and_case[(table_spec, case_name)] = mode
            if eccentricity_points == TABLE_SPECS[-1][0]:
                fine_modes[case_name] = mode
                fine_table = table

    if fine_table is None:
        raise RuntimeError("fine high-e Hamiltonian table was not constructed")

    shooting_rows: list[dict[str, float | int | str]] = []
    for case_name, inner_eccentricity in CASES:
        collocation = fine_modes[case_name]
        shooting = solve_zo_nonlinear_apsidal_mode(
            fine_table,
            inner_eccentricity=inner_eccentricity,
            outer_to_inner_semimajor_axis=2.0,
            delta_gr=scales.delta_gr,
            frequency_bracket=(
                0.95 * collocation.dimensionless_frequency,
                1.05 * collocation.dimensionless_frequency,
            ),
            radial_points=256,
            relative_tolerance=2.0e-9,
            absolute_tolerance=2.0e-11,
        )
        shooting_rows.append(
            {
                "case": case_name,
                "inner_eccentricity": inner_eccentricity,
                "shooting_frequency": shooting.dimensionless_frequency,
                "collocation_frequency": collocation.dimensionless_frequency,
                "relative_frequency_difference": abs(
                    shooting.dimensionless_frequency
                    / collocation.dimensionless_frequency
                    - 1.0
                ),
                "shooting_outer_eccentricity": float(shooting.eccentricity[-1]),
                "collocation_outer_eccentricity": float(
                    collocation.eccentricity[-1]
                ),
                "relative_outer_eccentricity_difference": abs(
                    float(shooting.eccentricity[-1])
                    / float(collocation.eccentricity[-1])
                    - 1.0
                ),
                "shooting_outer_boundary_residual": shooting.outer_boundary_residual,
                "collocation_outer_boundary_residual": collocation.outer_boundary_residual,
            }
        )

    derivative_rows: list[dict[str, float | int | str]] = []
    derivative_errors: list[float] = []
    for case_name, mode in fine_modes.items():
        for location, index in (
            ("inner", 0),
            ("middle", mode.eccentricity.size // 2),
            ("outer", mode.eccentricity.size - 1),
        ):
            eccentricity = float(mode.eccentricity[index])
            f_value = float(mode.eccentricity_plus_gradient[index])
            interpolated = fine_table.evaluate_e_f(eccentricity, f_value)
            direct = finite_difference_zo_hamiltonian_derivatives(
                eccentricity,
                f_value,
                eccentricity_step=2.0e-4,
                eccentricity_plus_gradient_step=2.0e-4,
                anomaly_points=192,
            )
            relative_error = float(
                np.linalg.norm(
                    derivative_vector(interpolated) - derivative_vector(direct)
                )
                / np.linalg.norm(derivative_vector(direct))
            )
            derivative_errors.append(relative_error)
            derivative_rows.append(
                {
                    "case": case_name,
                    "location": location,
                    "eccentricity": eccentricity,
                    "eccentricity_plus_gradient": f_value,
                    "orbital_nonlinearity": interpolated.orbital_nonlinearity,
                    "relative_derivative_vector_error": relative_error,
                }
            )

    derivative_resolution_rows: list[dict[str, float | int | str]] = []
    for table_spec in TABLE_SPECS:
        table = tables_by_spec[table_spec]
        mode = modes_by_spec_and_case[
            (table_spec, "strict_boundary_sensitivity")
        ]
        eccentricity = float(mode.eccentricity[0])
        f_value = float(mode.eccentricity_plus_gradient[0])
        interpolated = table.evaluate_e_f(eccentricity, f_value)
        direct = finite_difference_zo_hamiltonian_derivatives(
            eccentricity,
            f_value,
            eccentricity_step=2.0e-4,
            eccentricity_plus_gradient_step=2.0e-4,
            anomaly_points=192,
        )
        relative_error = float(
            np.linalg.norm(
                derivative_vector(interpolated) - derivative_vector(direct)
            )
            / np.linalg.norm(derivative_vector(direct))
        )
        derivative_resolution_rows.append(
            {
                "eccentricity_points": table_spec[0],
                "nonlinearity_points": table_spec[1],
                "table_anomaly_points": table_spec[2],
                "holdout_anomaly_points": 192,
                "case": "strict_boundary_sensitivity",
                "location": "inner",
                "eccentricity": eccentricity,
                "eccentricity_plus_gradient": f_value,
                "relative_derivative_vector_error": relative_error,
                "derivative_gate_passed": int(relative_error < 1.0e-3),
            }
        )

    mode_rows: list[dict[str, float | int | str]] = []
    profile_rows: list[dict[str, float | int | str]] = []
    threshold_rows: list[dict[str, float | int | str]] = []
    for case_name, inner_eccentricity in CASES:
        mode = fine_modes[case_name]
        direct_cycles_per_day = (
            mode.dimensionless_frequency
            * scales.dimensionless_to_cycles_per_day
        )
        printed_cycles_per_day = printed_eq48_cycles_per_day(
            mode.dimensionless_frequency,
            parameters(inner_eccentricity),
        )
        normalized_shape = mode.eccentricity / inner_eccentricity
        maximum_shape_difference = float(
            np.max(np.abs(normalized_shape - 1.0))
        )
        rms_shape_difference = float(
            np.sqrt(np.mean((normalized_shape - 1.0) ** 2))
        )
        mode_rows.append(
            {
                "case": case_name,
                "inner_eccentricity": inner_eccentricity,
                "outer_eccentricity": float(mode.eccentricity[-1]),
                "outer_to_inner_eccentricity_ratio": float(normalized_shape[-1]),
                "dimensionless_frequency": mode.dimensionless_frequency,
                "direct_eq39_cycles_per_day": direct_cycles_per_day,
                "direct_eq39_period_days": 1.0 / direct_cycles_per_day,
                "printed_eq48_cycles_per_day": printed_cycles_per_day,
                "printed_eq48_period_days": 1.0 / printed_cycles_per_day,
                "printed_to_direct_frequency_ratio": (
                    printed_cycles_per_day / direct_cycles_per_day
                ),
                "maximum_relative_shape_difference_from_constant_e": maximum_shape_difference,
                "rms_relative_shape_difference_from_constant_e": rms_shape_difference,
                "minimum_orbital_nonlinearity": float(
                    np.min(mode.orbital_nonlinearity)
                ),
                "maximum_orbital_nonlinearity": float(
                    np.max(mode.orbital_nonlinearity)
                ),
            }
        )
        for threshold in SHAPE_COMPATIBILITY_THRESHOLDS:
            threshold_rows.append(
                {
                    "case": case_name,
                    "relative_shape_threshold": threshold,
                    "maximum_relative_shape_difference": maximum_shape_difference,
                    "constant_e_atlas_shape_compatible": int(
                        maximum_shape_difference <= threshold
                    ),
                }
            )
        for radius, eccentricity, nonlinearity in zip(
            mode.dimensionless_semimajor_axis,
            mode.eccentricity,
            mode.orbital_nonlinearity,
            strict=True,
        ):
            profile_rows.append(
                {
                    "case": case_name,
                    "scaled_semimajor_axis": radius,
                    "eccentricity": eccentricity,
                    "eccentricity_over_inner": eccentricity
                    / inner_eccentricity,
                    "orbital_nonlinearity": nonlinearity,
                }
            )

    write_csv(OUTPUT / "phase5b4_high_e_table_convergence.csv", table_rows)
    write_csv(OUTPUT / "phase5b4_shooting_collocation.csv", shooting_rows)
    write_csv(OUTPUT / "phase5b4_high_e_derivative_holdout.csv", derivative_rows)
    write_csv(
        OUTPUT / "phase5b4_derivative_resolution_audit.csv",
        derivative_resolution_rows,
    )
    write_csv(OUTPUT / "phase5b4_candidate_timescales.csv", mode_rows)
    write_csv(OUTPUT / "phase5b4_candidate_mode_profiles.csv", profile_rows)
    write_csv(OUTPUT / "phase5b4_shape_threshold_sensitivity.csv", threshold_rows)

    coarse = {
        row["case"]: row
        for row in table_rows
        if row["eccentricity_points"] == TABLE_SPECS[0][0]
    }
    fine = {
        row["case"]: row
        for row in table_rows
        if row["eccentricity_points"] == TABLE_SPECS[-1][0]
    }
    maximum_frequency_change = max(
        abs(
            float(fine[case_name]["dimensionless_frequency"])
            / float(coarse[case_name]["dimensionless_frequency"])
            - 1.0
        )
        for case_name, _ in CASES
    )
    maximum_outer_eccentricity_change = max(
        abs(
            float(fine[case_name]["outer_eccentricity"])
            / float(coarse[case_name]["outer_eccentricity"])
            - 1.0
        )
        for case_name, _ in CASES
    )
    maximum_solver_frequency_difference = max(
        float(row["relative_frequency_difference"]) for row in shooting_rows
    )
    maximum_solver_profile_difference = max(
        float(row["relative_outer_eccentricity_difference"])
        for row in shooting_rows
    )
    maximum_derivative_error = max(derivative_errors)
    maximum_boundary_residual = max(
        abs(float(row["outer_boundary_residual"])) for row in table_rows
    )
    maximum_shape_difference = max(
        float(row["maximum_relative_shape_difference_from_constant_e"])
        for row in mode_rows
    )
    equation_internal_gate = bool(
        maximum_frequency_change < 1.0e-4
        and maximum_outer_eccentricity_change < 1.0e-4
        and maximum_solver_frequency_difference < 1.0e-5
        and maximum_solver_profile_difference < 1.0e-5
        and maximum_derivative_error < 1.0e-3
        and maximum_boundary_residual < 1.0e-8
    )
    report = {
        "phase": "5B4",
        "evidence": "[L/A/V/O]",
        "strict_source": {
            "circularization_efficiency": 0.01,
            "outer_to_inner_semimajor_axis": 2.0,
            "constant_e_atlas_reference": 0.60,
            "strict_boundary_sensitivity": 0.65,
        },
        "direct_eq39_scale": {
            "communication_time_days": scales.eccentric_communication_time_s
            / 86400.0,
            "delta_gr": scales.delta_gr,
            "dimensionless_to_cycles_per_day": scales.dimensionless_to_cycles_per_day,
        },
        "maximum_relative_frequency_table_change": maximum_frequency_change,
        "maximum_relative_outer_eccentricity_table_change": maximum_outer_eccentricity_change,
        "maximum_relative_shooting_collocation_frequency_difference": maximum_solver_frequency_difference,
        "maximum_relative_shooting_collocation_outer_eccentricity_difference": maximum_solver_profile_difference,
        "maximum_relative_derivative_holdout_error": maximum_derivative_error,
        "intermediate_31x61_derivative_gate_passed": bool(
            next(
                row["derivative_gate_passed"]
                for row in derivative_resolution_rows
                if row["eccentricity_points"] == 31
            )
        ),
        "final_41x81_derivative_gate_passed": bool(
            next(
                row["derivative_gate_passed"]
                for row in derivative_resolution_rows
                if row["eccentricity_points"] == 41
            )
        ),
        "maximum_absolute_outer_boundary_residual": maximum_boundary_residual,
        "maximum_relative_shape_difference_from_constant_e": maximum_shape_difference,
        "high_e_equation_internal_gate": equation_internal_gate,
        "equation_self_consistent_candidate_timescale_computed": equation_internal_gate,
        "published_benchmark_gate": False,
        "constant_e_atlas_shape_compatibility_gate": False,
        "existing_atlas_phase_to_time_mapping_authorized": False,
        "interpretation": (
            "A converged equation-self-consistent high-e candidate period can be "
            "computed with the direct Eq. (39) ledger, but its eccentricity profile "
            "is strongly non-constant and the published Fig. 6/7 benchmark remains "
            "open. It cannot be attached to the existing constant-e observer atlas."
        ),
    }
    (
        OUTPUT / "phase5b4_strict_domain_candidate_timescale_report.json"
    ).write_text(json.dumps(report, indent=2) + "\n")

    colors = {"atlas_reference": "#0072B2", "strict_boundary_sensitivity": "#D55E00"}
    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.4), constrained_layout=True)
    for case_name, inner_eccentricity in CASES:
        mode = fine_modes[case_name]
        label = f"e_in={inner_eccentricity:.2f}"
        axes[0].plot(
            mode.dimensionless_semimajor_axis,
            mode.eccentricity / inner_eccentricity,
            color=colors[case_name],
            linewidth=2.0,
            label=label,
        )
        axes[1].plot(
            mode.dimensionless_semimajor_axis,
            mode.orbital_nonlinearity,
            color=colors[case_name],
            linewidth=2.0,
            label=label,
        )
    axes[0].axhline(1.0, color="black", linestyle="--", label="Constant-e atlas")
    axes[0].set_xlabel("Semimajor axis  a / a_in")
    axes[0].set_ylabel("Eccentricity  e / e_in")
    axes[0].set_title("Mode-shape compatibility")
    axes[1].set_xlabel("Semimajor axis  a / a_in")
    axes[1].set_ylabel("Orbital nonlinearity  q")
    axes[1].set_title("Nonlinear radial compression")
    for axis in axes:
        axis.grid(alpha=0.22)
        axis.legend(frameon=False)
    figure.savefig(OUTPUT / "phase5b4_mode_shape_compatibility.png", dpi=220)
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(10.8, 4.4), constrained_layout=True)
    positions = np.arange(len(mode_rows))
    labels = [f"e_in={float(row['inner_eccentricity']):.2f}" for row in mode_rows]
    axes[0].bar(
        positions,
        [float(row["dimensionless_frequency"]) for row in mode_rows],
        color=[colors[str(row["case"])] for row in mode_rows],
    )
    axes[0].set_xticks(positions, labels)
    axes[0].set_ylabel("Dimensionless frequency")
    axes[0].set_title("Equation-self-consistent candidates")
    width = 0.34
    axes[1].bar(
        positions - width / 2.0,
        [float(row["direct_eq39_period_days"]) for row in mode_rows],
        width,
        color="#0072B2",
        label="Direct Eqs. (9)–(12), (39)",
    )
    axes[1].bar(
        positions + width / 2.0,
        [float(row["printed_eq48_period_days"]) for row in mode_rows],
        width,
        color="#D55E00",
        label="Printed Eq. (48)",
    )
    axes[1].set_xticks(positions, labels)
    axes[1].set_ylabel("Candidate period  days")
    axes[1].set_title("Normalization is not interchangeable")
    axes[1].legend(frameon=False, fontsize=8.5)
    for axis in axes:
        axis.grid(axis="y", alpha=0.22)
    figure.savefig(OUTPUT / "phase5b4_candidate_timescale_ledger.png", dpi=220)
    plt.close(figure)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
