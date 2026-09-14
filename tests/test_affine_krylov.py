import numpy as np
import pytest

from eccentric_tde_observer.affine_krylov import (
    constrained_affine_residual_line_minimum,
    constrained_minimum_residual_coefficients,
    exact_nonnegative_affine_step,
    positive_simplex_minimum_residual_coefficients,
)
from eccentric_tde_observer.source import PhysicalDomainError


def test_constrained_combination_recovers_exact_two_residual_cancellation():
    residual = np.array([[1.0, 0.0], [-1.0, 0.0]])
    gram = residual @ residual.T
    # 精确反平行向量使 Gram 奇异；加入独立的第三控制分量检验可解子空间。
    residual = np.array([[1.0, 0.0, 0.0], [-0.8, 0.2, 0.0], [0.0, 0.0, 1.0]])
    gram = residual @ residual.T
    result = constrained_minimum_residual_coefficients(
        gram, maximum_normalized_condition=1.0e8
    )
    combined = result.coefficients @ residual
    assert abs(np.sum(result.coefficients) - 1.0) < 1.0e-12
    assert np.linalg.norm(combined) < min(np.linalg.norm(row) for row in residual)
    assert result.predicted_squared_norm == pytest.approx(combined @ combined)


def test_constrained_combination_rejects_frozen_condition_gate_without_regularizing():
    residual = np.array([[1.0, 0.0], [1.0, 1.0e-12]])
    with pytest.raises(PhysicalDomainError, match="condition gate"):
        constrained_minimum_residual_coefficients(
            residual @ residual.T,
            maximum_normalized_condition=1.0e10,
        )


def test_positive_simplex_combination_recovers_convex_residual_cancellation():
    residual = np.array([[1.0, 0.0], [-1.0, 0.0], [0.0, 2.0]])
    result = positive_simplex_minimum_residual_coefficients(
        residual @ residual.T
    )
    combined = result.coefficients @ residual
    assert result.coefficients == pytest.approx([0.5, 0.5, 0.0], abs=2.0e-7)
    assert np.all(result.coefficients >= 0.0)
    assert np.sum(result.coefficients) == pytest.approx(1.0, abs=2.0e-13)
    assert np.linalg.norm(combined) < 2.0e-7
    assert result.predicted_squared_norm == pytest.approx(combined @ combined)


def test_positive_simplex_combination_selects_best_endpoint_without_extrapolation():
    residual = np.array([[2.0, 0.0], [1.0, 0.0], [3.0, 0.0]])
    result = positive_simplex_minimum_residual_coefficients(
        residual @ residual.T
    )
    assert result.coefficients == pytest.approx([0.0, 1.0, 0.0], abs=2.0e-7)
    assert result.predicted_squared_norm == pytest.approx(1.0, abs=2.0e-7)


def test_positive_simplex_state_combination_preserves_nonnegative_physical_domain():
    states = np.array(
        [
            [[0.0, 2.0], [4.0, 1.0]],
            [[3.0, 0.0], [1.0, 5.0]],
            [[2.0, 1.0], [0.0, 3.0]],
        ]
    )
    residual = np.array([[1.0, -1.0], [-0.5, 0.5], [2.0, 1.0]])
    result = positive_simplex_minimum_residual_coefficients(
        residual @ residual.T
    )
    candidate = np.einsum("k,kij->ij", result.coefficients, states)
    assert np.all(candidate >= 0.0)
    assert np.max(candidate) <= np.max(states)


def test_exact_nonnegative_step_uses_one_scalar_and_no_cell_repair():
    state = np.array([2.0, 1.0, 4.0])
    direction = np.array([1.0, -4.0, -1.0])
    step = exact_nonnegative_affine_step(state, direction)
    assert step < 0.25
    assert np.nextafter(step, np.inf) == 0.25
    candidate = state + step * direction
    assert np.all(candidate >= 0.0)
    assert exact_nonnegative_affine_step(state, np.ones(3)) == 1.0


def test_exact_nonnegative_step_rejects_direction_leaving_zero_state():
    with pytest.raises(PhysicalDomainError, match="no positive affine step"):
        exact_nonnegative_affine_step(np.array([0.0, 1.0]), np.array([-1.0, 0.0]))


def test_affine_residual_line_minimum_recovers_interior_exact_solution():
    raw = np.array([2.0, -1.0])
    endpoint = np.array([-1.0, 0.5])
    result = constrained_affine_residual_line_minimum(raw, endpoint)
    assert result.selected_fraction == pytest.approx(2.0 / 3.0)
    assert result.predicted_squared_norm == pytest.approx(0.0, abs=2.0e-30)
    assert result.selected_lower_boundary is False
    assert result.selected_upper_boundary is False


def test_affine_residual_line_minimum_reports_non_descent_lower_boundary():
    result = constrained_affine_residual_line_minimum(
        np.array([1.0, 0.0]), np.array([2.0, 0.0])
    )
    assert result.unconstrained_fraction < 0.0
    assert result.selected_fraction == 0.0
    assert result.selected_lower_boundary is True


def test_affine_residual_line_minimum_reports_upper_trust_boundary():
    result = constrained_affine_residual_line_minimum(
        np.array([1.0, 0.0]), np.array([0.5, 0.0])
    )
    assert result.unconstrained_fraction > 1.0
    assert result.selected_fraction == 1.0
    assert result.selected_upper_boundary is True
