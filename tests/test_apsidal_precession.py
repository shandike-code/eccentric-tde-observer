from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from eccentric_tde_observer import (
    ZOConstantEParameters,
    assemble_zo_linear_apsidal_matrices,
    solve_zo_linear_apsidal_modes,
    zo_local_gr_apsidal_precession_s1,
    zo_precession_scales,
)


ROOT = Path(__file__).resolve().parents[1]


def _parameters() -> ZOConstantEParameters:
    return ZOConstantEParameters(
        black_hole_mass_msun=1.0e6,
        stellar_mass_msun=1.0,
        stellar_radius_rsun=1.0,
        circularization_efficiency=1.0,
        outer_to_inner_semimajor_axis=2.0,
        eccentricity=0.0,
        opacity_cm2_g=0.34,
    )


def _shooting_fundamental_dimensionless_frequency(
    radius_ratio: float, delta_gr: float
) -> float:
    """独立积分 OL Eq. (44) 的强形式，作为 Galerkin 对照。"""
    gamma = 4.0 / 3.0
    boundary_ratio = (4.0 * gamma - 3.0) / (2.0 * gamma - 1.0)
    second_derivative_coefficient = (2.0 * gamma - 1.0) / (2.0 * gamma)
    eccentricity_coefficient = (9.0 - 5.0 * gamma) / (2.0 * gamma)

    def outer_boundary_residual(dimensionless_frequency: float) -> float:
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
            max_step=(radius_ratio - 1.0) / 128.0,
        )
        assert solution.success
        return float(
            radius_ratio * solution.y[1, -1]
            + boundary_ratio * solution.y[0, -1]
        )

    return float(brentq(outer_boundary_residual, 0.0, 4.0))


def test_zo_precession_scales_close_eq39_and_eq40() -> None:
    scales = zo_precession_scales(_parameters())
    inner_gr = float(
        zo_local_gr_apsidal_precession_s1(
            scales.inner_semimajor_axis_cm, 1.0e6
        )
    )
    assert np.isclose(
        inner_gr * scales.eccentric_communication_time_s,
        scales.delta_gr,
        rtol=2.0e-15,
    )
    assert np.isclose(scales.delta_gr, 0.030564961263305362, rtol=2.0e-14)
    assert np.isclose(
        scales.dimensionless_to_angular_frequency_s1
        * scales.eccentric_communication_time_s,
        1.0,
        rtol=2.0e-15,
    )


def test_linear_apsidal_matrices_are_symmetric_with_positive_mass() -> None:
    _, stiffness, mass, _ = assemble_zo_linear_apsidal_matrices(
        _parameters(), radial_points=64
    )
    assert np.array_equal(stiffness, stiffness.T)
    assert np.array_equal(mass, mass.T)
    assert np.min(np.linalg.eigvalsh(mass)) > 0.0


def test_linear_fundamental_matches_independent_strong_form_shooting() -> None:
    parameters = _parameters()
    scales = zo_precession_scales(parameters)
    shooting = _shooting_fundamental_dimensionless_frequency(
        2.0, scales.delta_gr
    )
    galerkin = solve_zo_linear_apsidal_modes(
        parameters,
        radial_points=256,
        mode_count=3,
    )
    assert galerkin.fundamental.radial_node_count == 0
    assert np.all(galerkin.fundamental.eccentricity_shape > 0.0)
    assert np.isclose(
        galerkin.fundamental.dimensionless_frequency,
        shooting,
        rtol=3.0e-5,
    )
    assert galerkin.fundamental.generalized_residual < 2.0e-8


def test_linear_fundamental_radial_convergence() -> None:
    parameters = _parameters()
    values = [
        solve_zo_linear_apsidal_modes(
            parameters, radial_points=points, mode_count=1
        ).fundamental.dimensionless_frequency
        for points in (64, 128, 256)
    ]
    coarse_error = abs(values[0] / values[2] - 1.0)
    fine_error = abs(values[1] / values[2] - 1.0)
    assert fine_error < coarse_error
    assert fine_error < 1.0e-5


def test_uniform_external_precession_shifts_all_modes_without_shape_change() -> None:
    parameters = _parameters()
    baseline = solve_zo_linear_apsidal_modes(
        parameters,
        radial_points=96,
        include_gr=False,
        mode_count=3,
    )
    shift = 2.5e-8
    shifted = solve_zo_linear_apsidal_modes(
        parameters,
        radial_points=96,
        include_gr=False,
        uniform_external_precession_s1=shift,
        mode_count=3,
    )
    for original, translated in zip(baseline.modes, shifted.modes, strict=True):
        assert np.isclose(
            translated.angular_frequency_s1 - original.angular_frequency_s1,
            shift,
            rtol=1.0e-10,
            atol=3.0e-18,
        )
        assert np.allclose(
            translated.eccentricity_shape,
            original.eccentricity_shape,
            rtol=2.0e-10,
            atol=2.0e-12,
        )


def test_signed_frequency_and_period_are_not_conflated() -> None:
    mode = solve_zo_linear_apsidal_modes(
        _parameters(), radial_points=96, mode_count=1
    ).fundamental
    assert mode.angular_frequency_s1 > 0.0
    assert mode.signed_cycles_per_day > 0.0
    assert mode.period_days is not None
    assert np.isclose(
        mode.period_days,
        1.0 / mode.signed_cycles_per_day,
        rtol=2.0e-15,
    )


def test_apsidal_module_contains_no_forbidden_numerical_repairs() -> None:
    path = ROOT / "src/eccentric_tde_observer/apsidal_precession.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    assert "nan_to_num" not in calls
    assert "clip" not in calls
