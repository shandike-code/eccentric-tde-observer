"""Phase 5B2：ZO 三维非线性局域 Hamiltonian 与导数门槛。"""

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

from eccentric_tde_observer import (
    finite_difference_zo_hamiltonian_derivatives,
    solve_zo_untwisted_hamiltonian,
    zo_linearized_dimensionless_hamiltonian,
    zo_untwisted_dimensionless_hamiltonian,
)
from eccentric_tde_observer.zo_reference import (
    solve_constant_e_vertical_breathing,
)


ECCENTRICITY_GRID = tuple(np.linspace(0.0, 0.9, 10))
NONLINEARITY_GRID = tuple(np.linspace(-0.75, 0.75, 13))
DERIVATIVE_STEPS = (4.0e-3, 2.0e-3, 1.0e-3, 5.0e-4)
DERIVATIVE_STATES = (
    ("moderate", 0.3, -0.3),
    ("strong", 0.7, -0.4),
    ("high-e", 0.9, -0.5),
)
TOLERANCE_STATES = (
    (0.5, 0.2),
    (0.8, 0.8),
    (0.9, 0.4),
    (0.95, 0.5),
)
DERIVATIVE_RELATIVE_TARGET = 1.0e-5
HAMILTONIAN_TOLERANCE_TARGET = 2.0e-9
LINEAR_REMAINDER_SLOPE_TARGET = 3.9


def _f_from_e_and_q(eccentricity: float, nonlinearity: float) -> float:
    denominator = 1.0 + eccentricity * nonlinearity
    if denominator <= 0.0:
        raise ValueError("e-q coordinate transformation has invalid denominator")
    return float((eccentricity + nonlinearity) / denominator)


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


def _derivative_vector(derivatives) -> np.ndarray:
    return np.array(
        (
            derivatives.derivative_e_at_fixed_f,
            derivatives.derivative_f_at_fixed_e,
            derivatives.second_derivative_ee,
            derivatives.second_derivative_ef,
            derivatives.second_derivative_ff,
        ),
        dtype=np.float64,
    )


def _plot_hamiltonian_surface(
    output_path: Path,
    rows: list[dict[str, object]],
) -> None:
    value = np.empty((len(NONLINEARITY_GRID), len(ECCENTRICITY_GRID)))
    for q_index, nonlinearity in enumerate(NONLINEARITY_GRID):
        for e_index, eccentricity in enumerate(ECCENTRICITY_GRID):
            row = next(
                item
                for item in rows
                if item["eccentricity"] == eccentricity
                and item["orbital_nonlinearity"] == nonlinearity
            )
            value[q_index, e_index] = float(
                row["dimensionless_hamiltonian"]
            )
    figure, axis = plt.subplots(figsize=(8.2, 5.4))
    image = axis.pcolormesh(
        ECCENTRICITY_GRID,
        NONLINEARITY_GRID,
        value,
        shading="nearest",
        cmap="viridis",
    )
    colorbar = figure.colorbar(image, ax=axis)
    colorbar.set_label(r"Dimensionless Hamiltonian $F(e,f)$")
    axis.set_xlabel("Eccentricity e")
    axis.set_ylabel("Orbital nonlinearity q")
    axis.set_title("ZO three-dimensional nonlinear Hamiltonian")
    figure.tight_layout()
    figure.savefig(output_path, dpi=190)
    plt.close(figure)


def _plot_breathing_profiles(output_path: Path) -> None:
    cases = (
        ("Circular", 0.0, 0.0),
        ("Constant e=0.6", 0.6, 0.0),
        ("High e, q=-0.5", 0.9, -0.5),
        ("High e, q=+0.5", 0.9, 0.5),
    )
    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.5))
    for label, eccentricity, nonlinearity in cases:
        f_value = _f_from_e_and_q(eccentricity, nonlinearity)
        state = solve_zo_untwisted_hamiltonian(
            eccentricity,
            f_value,
            anomaly_points=1024,
        )
        phase = state.eccentric_anomaly_rad / np.pi
        axes[0].semilogy(
            phase,
            state.dimensionless_height,
            linewidth=1.8,
            label=label,
        )
        jacobian = (
            1.0
            - eccentricity * f_value
            - (f_value - eccentricity)
            * np.cos(state.eccentric_anomaly_rad)
        ) / np.sqrt(1.0 - eccentricity**2)
        axes[1].plot(phase, jacobian, linewidth=1.8, label=label)
    axes[0].set_xlabel(r"Eccentric anomaly $E/\pi$")
    axes[0].set_ylabel(r"Dimensionless height $h$")
    axes[0].set_title("Periodic vertical breathing")
    axes[1].set_xlabel(r"Eccentric anomaly $E/\pi$")
    axes[1].set_ylabel(r"Orbital Jacobian $j$")
    axes[1].set_title("Non-intersecting coordinate Jacobian")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    figure.tight_layout()
    figure.savefig(output_path, dpi=190)
    plt.close(figure)


def _plot_local_controls(
    output_path: Path,
    linear_rows: list[dict[str, float]],
    derivative_rows: list[dict[str, object]],
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.5))
    axes[0].loglog(
        [row["amplitude"] for row in linear_rows],
        [row["absolute_remainder"] for row in linear_rows],
        "o-",
        linewidth=1.8,
        label="Nonlinear minus quadratic",
    )
    reference_amplitude = np.array(
        [row["amplitude"] for row in linear_rows], dtype=np.float64
    )
    reference = (
        linear_rows[-1]["absolute_remainder"]
        * (reference_amplitude / reference_amplitude[-1]) ** 4
    )
    axes[0].loglog(
        reference_amplitude,
        reference,
        "--",
        color="black",
        label="Fourth-order reference",
    )
    axes[0].set_xlabel("Common small-amplitude scale")
    axes[0].set_ylabel("Absolute Hamiltonian remainder")
    axes[0].set_title("Recovery of the linear Hamiltonian")
    for name, _, _ in DERIVATIVE_STATES:
        selected = [row for row in derivative_rows if row["state"] == name]
        axes[1].loglog(
            [row["step"] for row in selected[1:]],
            [row["relative_to_previous_step"] for row in selected[1:]],
            "o-",
            linewidth=1.8,
            label=name,
        )
    axes[1].axhline(
        DERIVATIVE_RELATIVE_TARGET,
        color="black",
        linestyle="--",
        label="Acceptance target",
    )
    axes[1].invert_xaxis()
    axes[1].set_xlabel("Finite-difference step")
    axes[1].set_ylabel("Relative derivative-vector change")
    axes[1].set_title("Five-point derivative stability")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    figure.tight_layout()
    figure.savefig(output_path, dpi=190)
    plt.close(figure)


def run(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    surface_rows: list[dict[str, object]] = []
    for eccentricity in ECCENTRICITY_GRID:
        for nonlinearity in NONLINEARITY_GRID:
            f_value = _f_from_e_and_q(eccentricity, nonlinearity)
            state = solve_zo_untwisted_hamiltonian(
                eccentricity,
                f_value,
                anomaly_points=256,
            )
            surface_rows.append(
                {
                    "eccentricity": float(eccentricity),
                    "orbital_nonlinearity": float(nonlinearity),
                    "eccentricity_plus_gradient": f_value,
                    "dimensionless_hamiltonian": (
                        state.dimensionless_hamiltonian
                    ),
                    "log_pericentre_height": state.log_pericentre_height,
                    "minimum_dimensionless_height": float(
                        np.min(state.dimensionless_height)
                    ),
                    "maximum_dimensionless_height": float(
                        np.max(state.dimensionless_height)
                    ),
                    "apoapsis_boundary_residual": (
                        state.apoapsis_boundary_residual
                    ),
                    "ivp_function_evaluations": state.ivp_function_evaluations,
                }
            )

    constant_e_rows = []
    for eccentricity in (0.2, 0.6, 0.8):
        control = solve_constant_e_vertical_breathing(eccentricity, 512)
        nonlinear = solve_zo_untwisted_hamiltonian(
            eccentricity,
            eccentricity,
            anomaly_points=512,
        )
        constant_e_rows.append(
            {
                "eccentricity": eccentricity,
                "log_pericentre_height_absolute_difference": abs(
                    nonlinear.log_pericentre_height
                    - control.log_pericentre_height
                ),
                "maximum_height_relative_difference": float(
                    np.max(
                        np.abs(
                            nonlinear.dimensionless_height
                            / control.dimensionless_height
                            - 1.0
                        )
                    )
                ),
                "maximum_log_height_derivative_absolute_difference": float(
                    np.max(
                        np.abs(
                            nonlinear.log_height_derivative_per_rad
                            - control.log_height_derivative_per_rad
                        )
                    )
                ),
            }
        )

    symmetry_rows = []
    for eccentricity, f_value in ((0.2, -0.2), (0.5, 0.1), (0.8, 0.6)):
        positive = zo_untwisted_dimensionless_hamiltonian(
            eccentricity, f_value, anomaly_points=128
        )
        negative = zo_untwisted_dimensionless_hamiltonian(
            -eccentricity, -f_value, anomaly_points=128
        )
        symmetry_rows.append(
            {
                "eccentricity": eccentricity,
                "eccentricity_plus_gradient": f_value,
                "positive_hamiltonian": positive,
                "negative_hamiltonian": negative,
                "relative_difference": abs(positive / negative - 1.0),
            }
        )

    linear_rows: list[dict[str, float]] = []
    for amplitude in (0.08, 0.04, 0.02, 0.01):
        nonlinear = zo_untwisted_dimensionless_hamiltonian(
            amplitude, 0.7 * amplitude, anomaly_points=64
        )
        quadratic = zo_linearized_dimensionless_hamiltonian(
            amplitude, 0.7 * amplitude
        )
        linear_rows.append(
            {
                "amplitude": amplitude,
                "nonlinear_hamiltonian": nonlinear,
                "quadratic_hamiltonian": quadratic,
                "absolute_remainder": abs(nonlinear - quadratic),
            }
        )
    logarithmic_slope = float(
        np.polyfit(
            np.log([row["amplitude"] for row in linear_rows]),
            np.log([row["absolute_remainder"] for row in linear_rows]),
            1,
        )[0]
    )

    derivative_rows: list[dict[str, object]] = []
    derivative_pair_errors: list[float] = []
    for name, eccentricity, nonlinearity in DERIVATIVE_STATES:
        f_value = _f_from_e_and_q(eccentricity, nonlinearity)
        previous_vector: np.ndarray | None = None
        for step in DERIVATIVE_STEPS:
            derivatives = finite_difference_zo_hamiltonian_derivatives(
                eccentricity,
                f_value,
                eccentricity_step=step,
                eccentricity_plus_gradient_step=step,
                anomaly_points=64,
            )
            vector = _derivative_vector(derivatives)
            if previous_vector is None:
                relative_change: float | None = None
            else:
                denominator = np.linalg.norm(vector)
                if denominator == 0.0:
                    raise ArithmeticError("derivative vector has zero norm")
                relative_change = float(
                    np.linalg.norm(vector - previous_vector) / denominator
                )
                derivative_pair_errors.append(relative_change)
            derivative_rows.append(
                {
                    "state": name,
                    "eccentricity": eccentricity,
                    "orbital_nonlinearity": nonlinearity,
                    "eccentricity_plus_gradient": f_value,
                    "step": step,
                    "derivative_e_at_fixed_f": (
                        derivatives.derivative_e_at_fixed_f
                    ),
                    "derivative_f_at_fixed_e": (
                        derivatives.derivative_f_at_fixed_e
                    ),
                    "second_derivative_ee": derivatives.second_derivative_ee,
                    "second_derivative_ef": derivatives.second_derivative_ef,
                    "second_derivative_ff": derivatives.second_derivative_ff,
                    "relative_to_previous_step": relative_change,
                    "evaluated_state_count": derivatives.evaluated_state_count,
                }
            )
            previous_vector = vector

    tolerance_rows = []
    for eccentricity, f_value in TOLERANCE_STATES:
        coarse = solve_zo_untwisted_hamiltonian(
            eccentricity,
            f_value,
            anomaly_points=128,
            relative_tolerance=1.0e-9,
            absolute_tolerance=1.0e-11,
        )
        fine = solve_zo_untwisted_hamiltonian(
            eccentricity,
            f_value,
            anomaly_points=128,
            relative_tolerance=2.0e-11,
            absolute_tolerance=2.0e-13,
        )
        tolerance_rows.append(
            {
                "eccentricity": eccentricity,
                "eccentricity_plus_gradient": f_value,
                "coarse_hamiltonian": coarse.dimensionless_hamiltonian,
                "fine_hamiltonian": fine.dimensionless_hamiltonian,
                "relative_hamiltonian_difference": abs(
                    coarse.dimensionless_hamiltonian
                    / fine.dimensionless_hamiltonian
                    - 1.0
                ),
                "log_pericentre_height_absolute_difference": abs(
                    coarse.log_pericentre_height
                    - fine.log_pericentre_height
                ),
            }
        )

    maximum_constant_height_error = max(
        row["maximum_height_relative_difference"] for row in constant_e_rows
    )
    maximum_symmetry_error = max(
        row["relative_difference"] for row in symmetry_rows
    )
    maximum_derivative_change = max(derivative_pair_errors)
    maximum_tolerance_error = max(
        row["relative_hamiltonian_difference"] for row in tolerance_rows
    )
    maximum_boundary_residual = max(
        abs(float(row["apoapsis_boundary_residual"])) for row in surface_rows
    )
    minimum_height = min(
        float(row["minimum_dimensionless_height"]) for row in surface_rows
    )
    decision = {
        "circular_limit_passed": (
            bool(np.isclose(
                zo_untwisted_dimensionless_hamiltonian(0.0, 0.0),
                3.5,
                rtol=2.0e-15,
            ))
        ),
        "constant_e_existing_solver_regression_passed": (
            maximum_constant_height_error < 2.0e-10
        ),
        "signed_state_symmetry_passed": maximum_symmetry_error < 1.0e-11,
        "corrected_linear_hamiltonian_limit_passed": (
            logarithmic_slope > LINEAR_REMAINDER_SLOPE_TARGET
        ),
        "five_point_derivative_stability_passed": (
            maximum_derivative_change < DERIVATIVE_RELATIVE_TARGET
        ),
        "vertical_tolerance_gate_passed": (
            maximum_tolerance_error < HAMILTONIAN_TOLERANCE_TARGET
        ),
        "periodic_vertical_boundary_gate_passed": (
            maximum_boundary_residual < 1.0e-8
        ),
        "all_surface_states_positive_without_repairs": minimum_height > 0.0,
    }
    decision["nonlinear_local_hamiltonian_verified"] = all(decision.values())
    decision["phase5b3_nonlinear_bvp_authorized"] = decision[
        "nonlinear_local_hamiltonian_verified"
    ]
    decision["published_high_e_mode_reproduced"] = False
    decision["strict_domain_phase_to_time_mapping_authorized"] = False

    report: dict[str, object] = {
        "phase": "5B2",
        "scope": (
            "local nonlinear three-dimensional untwisted ZO Hamiltonian and "
            "derivatives; not yet the global high-e eigenmode"
        ),
        "configuration": {
            "adiabatic_index": 4.0 / 3.0,
            "eccentricity_grid": list(ECCENTRICITY_GRID),
            "orbital_nonlinearity_grid": list(NONLINEARITY_GRID),
            "derivative_steps": list(DERIVATIVE_STEPS),
            "hamiltonian_definition": "Zanazzi & Ogilvie 2020 Eqs. (31), (34)-(35)",
            "linear_control": "Ogilvie & Lynch 2019 Eq. (44)-consistent expansion",
        },
        "constant_e_regression": constant_e_rows,
        "signed_symmetry": symmetry_rows,
        "linear_limit": linear_rows,
        "derivative_convergence": derivative_rows,
        "vertical_tolerance_convergence": tolerance_rows,
        "aggregate": {
            "surface_state_count": len(surface_rows),
            "minimum_surface_height": minimum_height,
            "maximum_surface_apoapsis_boundary_residual": (
                maximum_boundary_residual
            ),
            "maximum_constant_e_height_relative_difference": (
                maximum_constant_height_error
            ),
            "maximum_signed_symmetry_relative_difference": (
                maximum_symmetry_error
            ),
            "linear_remainder_logarithmic_slope": logarithmic_slope,
            "maximum_derivative_vector_relative_change": (
                maximum_derivative_change
            ),
            "maximum_vertical_tolerance_relative_hamiltonian_difference": (
                maximum_tolerance_error
            ),
        },
        "decision": decision,
        "open_items": [
            (
                "The local Hamiltonian grid is a validation surface, not yet an "
                "interpolation table for the global nonlinear boundary-value problem."
            ),
            (
                "ZO Figures 6-7 and their published dimensionless eigenfrequencies "
                "have not yet been reproduced."
            ),
            (
                "No high-e observer phase has been converted to days, and the "
                "printed Eq. (48) normalization discrepancy remains open."
            ),
        ],
    }

    _write_csv(output_dir / "phase5b2_hamiltonian_surface.csv", surface_rows)
    _write_csv(
        output_dir / "phase5b2_derivative_convergence.csv", derivative_rows
    )
    _write_json_atomic(
        output_dir / "phase5b2_nonlinear_hamiltonian_report.json", report
    )
    _plot_hamiltonian_surface(
        output_dir / "phase5b2_hamiltonian_surface.png", surface_rows
    )
    _plot_breathing_profiles(
        output_dir / "phase5b2_vertical_breathing_profiles.png"
    )
    _plot_local_controls(
        output_dir / "phase5b2_local_hamiltonian_controls.png",
        linear_rows,
        derivative_rows,
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    report = run(args.output_dir)
    print(
        "Phase 5B2 complete: "
        f"local_verified={report['decision']['nonlinear_local_hamiltonian_verified']}, "
        f"surface_states={report['aggregate']['surface_state_count']}, "
        "global_high_e_mode=False"
    )


if __name__ == "__main__":
    main()
