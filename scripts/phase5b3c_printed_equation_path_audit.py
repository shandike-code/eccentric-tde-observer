"""Phase 5B3c：ZO 2020 印刷方程路径、边界切线与频率约定审计。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_bvp

from eccentric_tde_observer import (
    PhysicalDomainError,
    ZOHamiltonianSplineTable,
    build_ol_2d_hamiltonian_spline_table,
    zo_free_boundary_nonlinearity,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"

PUBLISHED_FREQUENCY = {1.3: -0.717061649, 3.0: 0.13}
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


def write_csv(path: Path, rows: list[dict[str, float | int | str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_hamiltonian_table(
    eccentricity_points: int,
    nonlinearity_points: int,
    anomaly_points: int,
) -> ZOHamiltonianSplineTable:
    path = OUTPUT / (
        f"phase5b4_hamiltonian_table_{eccentricity_points}x"
        f"{nonlinearity_points}_a{anomaly_points}.npz"
    )
    with np.load(path) as cache:
        eccentricity = np.array(cache["eccentricity_nodes"], copy=True)
        nonlinearity = np.array(cache["nonlinearity_nodes"], copy=True)
        hamiltonian = np.array(
            cache["dimensionless_hamiltonian"], copy=True
        )
    return ZOHamiltonianSplineTable(
        eccentricity, nonlinearity, hamiltonian
    )


def solve_printed_equation_variant(
    table: ZOHamiltonianSplineTable,
    *,
    radius_ratio: float,
    inner_eccentricity: float,
    delta_gr: float,
    frequency_guess: float,
    variant: str,
    radial_points: int = 192,
) -> tuple[float, np.ndarray, np.ndarray, np.ndarray, float]:
    """分别求解主文加号路径和附录减号字面路径。"""
    if variant not in {"main_plus", "appendix_minus"}:
        raise ValueError("variant must be main_plus or appendix_minus")
    inner_q = zo_free_boundary_nonlinearity(table, inner_eccentricity)
    inner_f = (inner_eccentricity + inner_q) / (
        1.0 + inner_eccentricity * inner_q
    )
    logarithmic_slope = (
        inner_eccentricity - inner_f
    ) / inner_eccentricity
    radius = np.linspace(1.0, radius_ratio, radial_points)
    initial_eccentricity = inner_eccentricity * radius ** (
        -logarithmic_slope
    )
    initial_f = (1.0 - logarithmic_slope) * initial_eccentricity
    initial_state = np.vstack((initial_eccentricity, initial_f))

    def equation(
        radius_values: np.ndarray,
        state: np.ndarray,
        parameter: np.ndarray,
    ) -> np.ndarray:
        frequency = float(parameter[0])
        derivative = np.empty_like(state)
        for index, radius_value in enumerate(radius_values):
            eccentricity = float(state[0, index])
            f_value = float(state[1, index])
            hamiltonian = table.evaluate_e_f(eccentricity, f_value)
            if hamiltonian.second_derivative_ff <= 0.0:
                raise PhysicalDomainError(
                    "printed-path diagnostic lost gradient convexity"
                )
            one_minus_e_squared = 1.0 - eccentricity**2
            if one_minus_e_squared <= 0.0:
                raise PhysicalDomainError(
                    "printed-path diagnostic reached |e| >= 1"
                )
            gradient = f_value - eccentricity
            relativistic_term = (
                delta_gr
                / radius_value
                * eccentricity
                / one_minus_e_squared**1.5
            )
            frequency_term = (
                frequency
                * radius_value**1.5
                * eccentricity
                / np.sqrt(one_minus_e_squared)
            )
            derivative[0, index] = gradient / radius_value
            if variant == "main_plus":
                # 中文：主文 Eq. (38) 中二阶径向项为 2ae_a+a^2e_aa。
                a_f_gradient = (
                    hamiltonian.derivative_e_at_fixed_f
                    - gradient * hamiltonian.second_derivative_ef
                    + 3.0 * hamiltonian.derivative_f_at_fixed_e
                    - relativistic_term
                    + frequency_term
                ) / hamiltonian.second_derivative_ff
            else:
                # 中文：附录减号给出另一方程。
                # 中文：它只用于诊断，不写回正式源。
                a_f_gradient = (
                    -frequency_term
                    - hamiltonian.derivative_e_at_fixed_f
                    + gradient * hamiltonian.second_derivative_ef
                    + 4.0
                    * gradient
                    * hamiltonian.second_derivative_ff
                    - 3.0 * hamiltonian.derivative_f_at_fixed_e
                    + relativistic_term
                ) / hamiltonian.second_derivative_ff
            derivative[1, index] = a_f_gradient / radius_value
        return derivative

    def boundary_residual(
        inner_state: np.ndarray,
        outer_state: np.ndarray,
        parameter: np.ndarray,
    ) -> np.ndarray:
        del parameter
        inner_hamiltonian = table.evaluate_e_f(
            float(inner_state[0]), float(inner_state[1])
        )
        outer_hamiltonian = table.evaluate_e_f(
            float(outer_state[0]), float(outer_state[1])
        )
        return np.array(
            (
                inner_state[0] - inner_eccentricity,
                inner_hamiltonian.derivative_f_at_fixed_e,
                outer_hamiltonian.derivative_f_at_fixed_e,
            )
        )

    solution = solve_bvp(
        equation,
        boundary_residual,
        radius,
        initial_state,
        p=np.array((frequency_guess,)),
        tol=3.0e-6,
        max_nodes=8192,
    )
    if not solution.success or not np.all(np.isfinite(solution.y)):
        raise PhysicalDomainError(
            f"printed equation variant failed: {solution.message}"
        )
    state = solution.sol(radius)
    eccentricity = np.asarray(state[0], dtype=np.float64)
    f_values = np.asarray(state[1], dtype=np.float64)
    if np.any(eccentricity <= 0.0):
        raise PhysicalDomainError("printed equation variant is not node-free")
    denominator = 1.0 - eccentricity * f_values
    if np.any(denominator <= 0.0):
        raise PhysicalDomainError(
            "printed equation variant reached a non-positive Jacobian"
        )
    nonlinearity = (f_values - eccentricity) / denominator
    final_boundary = boundary_residual(
        state[:, 0], state[:, -1], solution.p
    )
    return (
        float(solution.p[0]),
        radius,
        eccentricity,
        nonlinearity,
        float(np.max(np.abs(final_boundary))),
    )


def endpoint_tangent_rows(
    three_dimensional_table: ZOHamiltonianSplineTable,
    two_dimensional_table: ZOHamiltonianSplineTable,
) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for radius_ratio, profile in PUBLISHED_MODE_PROFILES.items():
        for boundary in ("inner", "outer"):
            endpoint = profile[0] if boundary == "inner" else profile[-1]
            radius_value = float(endpoint[0])
            eccentricity = float(endpoint[1])
            required_q_3d = zo_free_boundary_nonlinearity(
                three_dimensional_table, eccentricity
            )
            required_q_2d = zo_free_boundary_nonlinearity(
                two_dimensional_table, eccentricity
            )
            for fitted_points in (2, 3, 4):
                local = (
                    profile[:fitted_points]
                    if boundary == "inner"
                    else profile[-fitted_points:]
                )
                slope = float(
                    np.polyfit(local[:, 0], local[:, 1], 1)[0]
                )
                eccentricity_gradient = radius_value * slope
                f_value = eccentricity + eccentricity_gradient
                denominator = 1.0 - eccentricity * f_value
                if denominator <= 0.0:
                    raise PhysicalDomainError(
                        "digitized endpoint tangent has non-positive Jacobian"
                    )
                inferred_q = eccentricity_gradient / denominator
                hamiltonian_3d = three_dimensional_table.evaluate_e_f(
                    eccentricity, f_value
                )
                hamiltonian_2d = two_dimensional_table.evaluate_e_f(
                    eccentricity, f_value
                )
                rows.append(
                    {
                        "radius_ratio": radius_ratio,
                        "boundary": boundary,
                        "linear_fit_point_count": fitted_points,
                        "endpoint_eccentricity": eccentricity,
                        "fitted_de_da": slope,
                        "inferred_orbital_nonlinearity": inferred_q,
                        "required_three_dimensional_free_q": required_q_3d,
                        "required_two_dimensional_free_q": required_q_2d,
                        "three_dimensional_F_f_residual": (
                            hamiltonian_3d.derivative_f_at_fixed_e
                        ),
                        "two_dimensional_F_f_residual": (
                            hamiltonian_2d.derivative_f_at_fixed_e
                        ),
                    }
                )
    return rows


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    inner_eccentricity = 0.2 * np.sqrt(0.92)
    delta_gr = 0.030564961263305362
    table_specs = ((31, 61, 192), (41, 81, 192))
    convergence_rows: list[dict[str, float | int | str]] = []
    fine_modes = {}
    fine_table = None
    for eccentricity_points, nonlinearity_points, anomaly_points in table_specs:
        table = load_hamiltonian_table(
            eccentricity_points, nonlinearity_points, anomaly_points
        )
        for variant, guesses in (
            ("main_plus", {1.3: 1.73, 3.0: 1.48}),
            ("appendix_minus", {1.3: -1.64, 3.0: -1.25}),
        ):
            for radius_ratio in (1.3, 3.0):
                mode = solve_printed_equation_variant(
                    table,
                    radius_ratio=radius_ratio,
                    inner_eccentricity=inner_eccentricity,
                    delta_gr=delta_gr,
                    frequency_guess=guesses[radius_ratio],
                    variant=variant,
                )
                published = PUBLISHED_MODE_PROFILES[radius_ratio]
                at_published = np.interp(
                    published[:, 0], mode[1], mode[2]
                )
                profile_error = float(
                    np.max(np.abs(at_published - published[:, 1]))
                    / inner_eccentricity
                )
                convergence_rows.append(
                    {
                        "eccentricity_points": eccentricity_points,
                        "nonlinearity_points": nonlinearity_points,
                        "anomaly_points": anomaly_points,
                        "printed_equation_path": variant,
                        "radius_ratio": radius_ratio,
                        "dimensionless_frequency": mode[0],
                        "published_frequency": PUBLISHED_FREQUENCY[
                            radius_ratio
                        ],
                        "absolute_published_frequency_error": abs(
                            mode[0] - PUBLISHED_FREQUENCY[radius_ratio]
                        ),
                        "outer_eccentricity": float(mode[2][-1]),
                        "profile_max_error_over_inner_e": profile_error,
                        "maximum_absolute_boundary_residual": mode[4],
                    }
                )
                if eccentricity_points == table_specs[-1][0]:
                    fine_modes[(variant, radius_ratio)] = mode
                    fine_table = table
    if fine_table is None:
        raise RuntimeError("fine printed-equation Hamiltonian table is missing")

    two_dimensional_table = build_ol_2d_hamiltonian_spline_table(
        np.linspace(0.0, 0.30, 29),
        np.linspace(-0.50, 0.15, 65),
        anomaly_points=512,
    )
    tangent_rows = endpoint_tangent_rows(
        fine_table, two_dimensional_table
    )

    source_rows: list[dict[str, float | int | str]] = [
        {
            "source_location": "main Eq. (38)",
            "printed_statement": "-(2 a e_a + a^2 e_aa) F_ff",
            "audit_classification": "formal baseline",
            "numerically_tested": 1,
        },
        {
            "source_location": "Appendix free-boundary equation",
            "printed_statement": "-(2 a e_a - a^2 e_aa) F_ff",
            "audit_classification": "internal sign mismatch",
            "numerically_tested": 1,
        },
        {
            "source_location": "Fig. 6 caption opening",
            "printed_statement": "a_out = 1.3 a_in and 3 a_in",
            "audit_classification": "axis-consistent",
            "numerically_tested": 0,
        },
        {
            "source_location": "Fig. 6 caption frequency clause",
            "printed_statement": "a_in = 1.3 a_out and 3 a_out",
            "audit_classification": "reciprocal caption typo",
            "numerically_tested": 0,
        },
        {
            "source_location": "Eq. (48) physical frequency",
            "printed_statement": "printed/direct frequency ratio 10.0008615",
            "audit_classification": "normalization mismatch retained from Phase 5B4",
            "numerically_tested": 1,
        },
    ]

    coarse = {
        (row["printed_equation_path"], float(row["radius_ratio"])): row
        for row in convergence_rows
        if row["eccentricity_points"] == table_specs[0][0]
    }
    fine = {
        (row["printed_equation_path"], float(row["radius_ratio"])): row
        for row in convergence_rows
        if row["eccentricity_points"] == table_specs[-1][0]
    }
    maximum_frequency_change = max(
        abs(
            float(fine[key]["dimensionless_frequency"])
            / float(coarse[key]["dimensionless_frequency"])
            - 1.0
        )
        for key in fine
    )
    maximum_boundary_residual = max(
        float(row["maximum_absolute_boundary_residual"])
        for row in convergence_rows
    )
    appendix_frequency_error = max(
        float(row["absolute_published_frequency_error"])
        for row in fine.values()
        if row["printed_equation_path"] == "appendix_minus"
    )
    appendix_profile_error = max(
        float(row["profile_max_error_over_inner_e"])
        for row in fine.values()
        if row["printed_equation_path"] == "appendix_minus"
    )
    inner_tangent_rows = [
        row for row in tangent_rows if row["boundary"] == "inner"
    ]
    declared_inner_boundary_gate = all(
        abs(
            float(row["inferred_orbital_nonlinearity"])
            - float(row["required_three_dimensional_free_q"])
        )
        < 0.02
        for row in inner_tangent_rows
    )
    equation_internal_gate = bool(
        maximum_frequency_change < 1.0e-4
        and maximum_boundary_residual < 1.0e-8
    )
    appendix_explanation_gate = bool(
        equation_internal_gate
        and appendix_frequency_error < 0.05
        and appendix_profile_error < 0.05
    )

    write_csv(
        OUTPUT / "phase5b3c_printed_equation_ledger.csv", source_rows
    )
    write_csv(
        OUTPUT / "phase5b3c_equation_variant_convergence.csv",
        convergence_rows,
    )
    write_csv(
        OUTPUT / "phase5b3c_published_boundary_tangents.csv", tangent_rows
    )
    report = {
        "phase": "5B3c printed equation path and boundary audit",
        "evidence": "[L]+[V]+[A-diagnostic]",
        "maximum_relative_frequency_table_change": maximum_frequency_change,
        "maximum_absolute_boundary_residual": maximum_boundary_residual,
        "appendix_path_maximum_absolute_published_frequency_error": (
            appendix_frequency_error
        ),
        "appendix_path_maximum_profile_error_over_inner_e": (
            appendix_profile_error
        ),
        "equation_variant_internal_gate": equation_internal_gate,
        "printed_appendix_sign_explains_published_branch": (
            appendix_explanation_gate
        ),
        "published_vector_all_inner_tangents_satisfy_declared_3d_free_boundary": (
            declared_inner_boundary_gate
        ),
        "formal_zo_source_model_changed": False,
        "phase_to_time_mapping_authorized": False,
        "interpretation": (
            "The paper contains a literal main-text/appendix sign mismatch and a "
            "reciprocal radius typo in the Fig. 6 caption. The converged appendix-sign "
            "variant does not recover the published frequencies or profiles. Endpoint "
            "tangents digitized from the published vector paths do not jointly satisfy "
            "the declared 3D inner free-boundary condition. These findings narrow the "
            "implementation audit but do not identify the unpublished code path."
        ),
    }
    (OUTPUT / "phase5b3c_printed_equation_path_report.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )

    with (
        OUTPUT / "phase5b3b_published_comparison.csv"
    ).open(newline="") as handle:
        planar_rows = {
            float(row["radius_ratio"]): row for row in csv.DictReader(handle)
        }
    figure, axes = plt.subplots(
        2, 2, figsize=(11.2, 8.0), layout="constrained"
    )
    ratios = np.array((1.3, 3.0))
    axes[0, 0].plot(
        ratios,
        [PUBLISHED_FREQUENCY[value] for value in ratios],
        "o-",
        label="Published ZO 2020",
    )
    axes[0, 0].plot(
        ratios,
        [fine_modes[("main_plus", value)][0] for value in ratios],
        "^-",
        label="Main Eq. (38)",
    )
    axes[0, 0].plot(
        ratios,
        [fine_modes[("appendix_minus", value)][0] for value in ratios],
        "s--",
        label="Appendix-sign literal",
    )
    axes[0, 0].plot(
        ratios,
        [
            float(planar_rows[value]["two_dimensional_nonlinear_frequency"])
            for value in ratios
        ],
        "D-.",
        label="Full 2D nonlinear",
    )
    axes[0, 0].axhline(0.0, color="0.45", linewidth=0.8)
    axes[0, 0].set_xlabel("Outer-to-inner semimajor-axis ratio")
    axes[0, 0].set_ylabel("Dimensionless precession frequency")
    axes[0, 0].set_title("Printed equation paths")
    axes[0, 0].legend(fontsize=8)

    for axis, radius_ratio in zip(
        (axes[0, 1], axes[1, 0]), ratios, strict=True
    ):
        published = PUBLISHED_MODE_PROFILES[radius_ratio]
        axis.plot(
            published[:, 0],
            published[:, 1] / inner_eccentricity,
            "o",
            label="Published vector path",
        )
        for variant, style, label in (
            ("main_plus", "-", "Main Eq. (38)"),
            ("appendix_minus", "--", "Appendix-sign literal"),
        ):
            mode = fine_modes[(variant, radius_ratio)]
            axis.plot(
                mode[1], mode[2] / inner_eccentricity, style, label=label
            )
        axis.set_xlabel("Scaled semimajor axis")
        axis.set_ylabel("Normalized eccentricity")
        axis.set_title(f"Mode shape: radius ratio {radius_ratio:g}")
        axis.legend(fontsize=8)

    boundary_labels = []
    center = []
    lower = []
    upper = []
    q_3d = []
    q_2d = []
    for radius_ratio in ratios:
        for boundary in ("inner", "outer"):
            selected = [
                row
                for row in tangent_rows
                if float(row["radius_ratio"]) == radius_ratio
                and row["boundary"] == boundary
            ]
            values = np.array(
                [
                    float(row["inferred_orbital_nonlinearity"])
                    for row in selected
                ]
            )
            midpoint = 0.5 * (float(np.min(values)) + float(np.max(values)))
            boundary_labels.append(f"R={radius_ratio:g} {boundary}")
            center.append(midpoint)
            lower.append(midpoint - float(np.min(values)))
            upper.append(float(np.max(values)) - midpoint)
            q_3d.append(
                float(selected[0]["required_three_dimensional_free_q"])
            )
            q_2d.append(
                float(selected[0]["required_two_dimensional_free_q"])
            )
    positions = np.arange(len(boundary_labels))
    axes[1, 1].errorbar(
        positions,
        center,
        yerr=np.vstack((lower, upper)),
        fmt="o",
        capsize=4,
        label="Published tangent: 2-4 point fits",
    )
    axes[1, 1].plot(positions, q_3d, "^", label="Required 3D free boundary")
    axes[1, 1].plot(positions, q_2d, "s", label="Required 2D free boundary")
    axes[1, 1].set_xticks(positions, boundary_labels, rotation=18)
    axes[1, 1].set_ylabel("Orbital nonlinearity at boundary")
    axes[1, 1].set_title("Boundary tangent audit")
    axes[1, 1].legend(fontsize=8)
    figure.suptitle("Phase 5B3c: printed-equation and boundary audit")
    figure.savefig(
        OUTPUT / "phase5b3c_printed_equation_path_audit.png", dpi=180
    )
    plt.close(figure)


if __name__ == "__main__":
    main()
