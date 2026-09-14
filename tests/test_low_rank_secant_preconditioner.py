import numpy as np
import pytest
from scipy.sparse.linalg import LinearOperator, gmres

from eccentric_tde_observer.low_rank_secant_preconditioner import (
    LowRankInverseSecantPreconditioner,
)
from eccentric_tde_observer.source import PhysicalDomainError


def test_rank_one_inverse_update_satisfies_dense_secant_identity():
    residual_secant = np.array([[1.0], [-2.0], [0.5], [3.0]])
    state_secant = np.array([[0.2], [1.5], [-0.8], [0.4]])
    preconditioner = LowRankInverseSecantPreconditioner.from_secants(
        state_secant,
        residual_secant,
        base_inverse_scale=-1.0,
        maximum_gram_condition_number=1.0e8,
    )
    np.testing.assert_allclose(
        preconditioner.apply(residual_secant[:, 0]),
        state_secant[:, 0],
        rtol=2.0e-15,
        atol=2.0e-15,
    )
    assert preconditioner.secant_count == 1
    assert preconditioner.maximum_relative_secant_residual < 2.0e-15


def test_multisecant_update_satisfies_each_independent_direction():
    rng = np.random.default_rng(17)
    residual_secants = rng.normal(size=(16, 3))
    state_secants = rng.normal(size=(16, 3))
    preconditioner = LowRankInverseSecantPreconditioner.from_secants(
        state_secants,
        residual_secants,
        base_inverse_scale=-1.0,
        maximum_gram_condition_number=1.0e8,
    )
    recovered = np.column_stack(
        [preconditioner.apply(residual_secants[:, index]) for index in range(3)]
    )
    np.testing.assert_allclose(recovered, state_secants, rtol=2.0e-14, atol=2.0e-14)


def test_rank_deficient_or_zero_residual_secants_are_rejected_without_floor():
    with pytest.raises(PhysicalDomainError, match="direction is zero"):
        LowRankInverseSecantPreconditioner.from_secants(
            np.ones((4, 1)),
            np.zeros((4, 1)),
            base_inverse_scale=-1.0,
            maximum_gram_condition_number=1.0e8,
        )
    repeated = np.column_stack((np.arange(1.0, 6.0), np.arange(1.0, 6.0)))
    with pytest.raises(PhysicalDomainError, match="rank deficient"):
        LowRankInverseSecantPreconditioner.from_secants(
            np.ones((5, 2)),
            repeated,
            base_inverse_scale=-1.0,
            maximum_gram_condition_number=1.0e8,
        )


def test_known_low_rank_inverse_reduces_manufactured_gmres_to_one_iteration():
    rng = np.random.default_rng(23)
    dimension = 24
    rank = 4
    residual_secants, _ = np.linalg.qr(rng.normal(size=(dimension, rank)))
    correction = 0.15 * rng.normal(size=(dimension, rank))
    true_inverse = -np.eye(dimension) + correction @ residual_secants.T
    jacobian = np.linalg.inv(true_inverse)
    state_secants = true_inverse @ residual_secants
    preconditioner = LowRankInverseSecantPreconditioner.from_secants(
        state_secants,
        residual_secants,
        base_inverse_scale=-1.0,
        maximum_gram_condition_number=1.0e8,
    )
    right_hand_side = rng.normal(size=dimension)
    unpreconditioned_history = []
    _, unpreconditioned_info = gmres(
        jacobian,
        right_hand_side,
        rtol=1.0e-11,
        atol=0.0,
        restart=dimension,
        maxiter=dimension,
        callback=unpreconditioned_history.append,
        callback_type="pr_norm",
    )
    preconditioned_history = []
    solution, preconditioned_info = gmres(
        LinearOperator((dimension, dimension), matvec=lambda value: jacobian @ value),
        right_hand_side,
        M=preconditioner.as_linear_operator(),
        rtol=1.0e-11,
        atol=0.0,
        restart=dimension,
        maxiter=dimension,
        callback=preconditioned_history.append,
        callback_type="pr_norm",
    )
    assert unpreconditioned_info == 0
    assert preconditioned_info == 0
    assert len(unpreconditioned_history) > 1
    assert len(preconditioned_history) == 1
    np.testing.assert_allclose(jacobian @ solution, right_hand_side, rtol=1.0e-11)


def test_linear_operator_returns_independent_writable_arrays():
    preconditioner = LowRankInverseSecantPreconditioner.from_secants(
        np.array([[1.0], [2.0]]),
        np.array([[2.0], [1.0]]),
        base_inverse_scale=-1.0,
        maximum_gram_condition_number=1.0e8,
    )
    result = preconditioner.as_linear_operator().matvec(np.array([0.5, -0.3]))
    assert result.flags.writeable
    result[0] += 1.0
