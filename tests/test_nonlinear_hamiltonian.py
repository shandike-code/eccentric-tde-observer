from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer import (
    PhysicalDomainError,
    finite_difference_zo_hamiltonian_derivatives,
    solve_zo_untwisted_hamiltonian,
    zo_linearized_dimensionless_hamiltonian,
    zo_untwisted_dimensionless_hamiltonian,
    zo_untwisted_orbital_jacobian,
)
from eccentric_tde_observer.zo_reference import (
    solve_constant_e_vertical_breathing,
)


ROOT = Path(__file__).resolve().parents[1]


def test_circular_hamiltonian_and_height_are_exact() -> None:
    state = solve_zo_untwisted_hamiltonian(0.0, 0.0, anomaly_points=64)
    assert np.array_equal(state.dimensionless_height, np.ones(64))
    assert np.array_equal(
        state.log_height_derivative_per_rad, np.zeros(64)
    )
    assert np.isclose(state.dimensionless_hamiltonian, 3.5, rtol=2.0e-15)


def test_constant_e_branch_reproduces_existing_vertical_breathing_solver() -> None:
    eccentricity = 0.8
    control = solve_constant_e_vertical_breathing(eccentricity, 512)
    nonlinear = solve_zo_untwisted_hamiltonian(
        eccentricity, eccentricity, anomaly_points=512
    )
    assert nonlinear.orbital_nonlinearity == 0.0
    assert np.isclose(
        nonlinear.log_pericentre_height,
        control.log_pericentre_height,
        atol=2.0e-13,
    )
    assert np.max(
        np.abs(
            nonlinear.dimensionless_height
            / control.dimensionless_height
            - 1.0
        )
    ) < 2.0e-10
    assert np.max(
        np.abs(
            nonlinear.log_height_derivative_per_rad
            - control.log_height_derivative_per_rad
        )
    ) < 5.0e-9


def test_eq34_accumulator_matches_independent_periodic_quadrature() -> None:
    state = solve_zo_untwisted_hamiltonian(0.5, 0.2, anomaly_points=1024)
    jacobian = zo_untwisted_orbital_jacobian(
        0.5, 0.2, state.eccentric_anomaly_rad
    )
    integrand = (1.0 - 0.5 * np.cos(state.eccentric_anomaly_rad)) / (
        jacobian * state.dimensionless_height
    ) ** (1.0 / 3.0)
    quadrature = 7.0 / (4.0 * np.pi) * 2.0 * np.pi * np.mean(integrand)
    assert np.isclose(
        quadrature, state.dimensionless_hamiltonian, rtol=3.0e-12
    )


def test_signed_state_symmetry_and_jacobian_are_preserved() -> None:
    positive = zo_untwisted_dimensionless_hamiltonian(0.2, -0.2)
    negative = zo_untwisted_dimensionless_hamiltonian(-0.2, 0.2)
    assert np.isclose(positive, negative, rtol=3.0e-14)
    anomaly = np.linspace(0.0, 2.0 * np.pi, 129, endpoint=False)
    jacobian = zo_untwisted_orbital_jacobian(0.5, 0.2, anomaly)
    expected = (
        1.0 - 0.5 * 0.2 - (0.2 - 0.5) * np.cos(anomaly)
    ) / np.sqrt(1.0 - 0.5**2)
    assert np.allclose(jacobian, expected, rtol=2.0e-15, atol=0.0)


def test_nonlinear_hamiltonian_recovers_corrected_linear_expansion() -> None:
    differences = []
    for amplitude in (0.08, 0.04, 0.02):
        nonlinear = zo_untwisted_dimensionless_hamiltonian(
            amplitude, 0.7 * amplitude, anomaly_points=64
        )
        linearized = zo_linearized_dimensionless_hamiltonian(
            amplitude, 0.7 * amplitude
        )
        differences.append(abs(nonlinear - linearized))
    assert 15.0 < differences[0] / differences[1] < 17.5
    assert 15.0 < differences[1] / differences[2] < 17.5


def test_five_point_derivatives_recover_small_amplitude_hessian() -> None:
    eccentricity = 0.01
    eccentricity_plus_gradient = 0.008
    derivatives = finite_difference_zo_hamiltonian_derivatives(
        eccentricity,
        eccentricity_plus_gradient,
        eccentricity_step=2.0e-4,
        eccentricity_plus_gradient_step=2.0e-4,
        anomaly_points=64,
    )
    assert np.isclose(
        derivatives.derivative_e_at_fixed_f,
        -2.0 * eccentricity + 0.25 * eccentricity_plus_gradient,
        atol=3.0e-7,
    )
    assert np.isclose(
        derivatives.derivative_f_at_fixed_e,
        0.25 * eccentricity + 0.625 * eccentricity_plus_gradient,
        atol=2.0e-7,
    )
    assert np.isclose(derivatives.second_derivative_ee, -2.0, atol=2.0e-4)
    assert np.isclose(derivatives.second_derivative_ef, 0.25, atol=2.0e-4)
    assert np.isclose(derivatives.second_derivative_ff, 0.625, atol=2.0e-4)
    assert derivatives.evaluated_state_count == 25


def test_intersecting_or_out_of_range_states_are_rejected() -> None:
    with pytest.raises(PhysicalDomainError):
        solve_zo_untwisted_hamiltonian(0.99, 0.99)
    with pytest.raises(PhysicalDomainError):
        solve_zo_untwisted_hamiltonian(0.8, -1.0)
    with pytest.raises(PhysicalDomainError):
        finite_difference_zo_hamiltonian_derivatives(
            0.9,
            0.4,
            eccentricity_step=0.1,
            eccentricity_plus_gradient_step=0.1,
        )


def test_nonlinear_hamiltonian_contains_no_forbidden_numerical_repairs() -> None:
    path = ROOT / "src/eccentric_tde_observer/nonlinear_hamiltonian.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = {
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert "np.nan_to_num" not in calls
    assert "np.clip" not in calls
    assert "numpy.nan_to_num" not in calls
    assert "numpy.clip" not in calls
