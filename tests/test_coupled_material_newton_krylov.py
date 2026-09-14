import numpy as np
import pytest

from eccentric_tde_observer.coupled_material_newton_krylov import (
    EncodedMaterialFixedPointResidual,
    GroundStateLogSimplexCodec,
    GroundStateMaterialState,
    ground_state_material_trial_within_trust_region,
    matrix_free_jacobian_vector_product,
    solve_matrix_free_newton_krylov,
)
from eccentric_tde_observer.radiation_matter_feedback import (
    frozen_radiation_material_response,
    ground_state_material_specific_energy_erg_g,
)
from eccentric_tde_observer.source import PhysicalDomainError


def _material_state():
    temperature = np.array([1.5e4, 4.0e4])
    hydrogen = np.array([[0.8, 0.2], [0.3, 0.7]])
    helium = np.array([[0.7, 0.2, 0.1], [0.2, 0.5, 0.3]])
    energy = ground_state_material_specific_energy_erg_g(
        temperature, hydrogen, helium
    )
    return GroundStateMaterialState(temperature, hydrogen, helium, energy)


def test_log_simplex_codec_round_trip_preserves_physical_state():
    state = _material_state()
    codec = GroundStateLogSimplexCodec(2)
    encoded = codec.encode(
        state.temperature_k, state.hydrogen_fraction, state.helium_fraction
    )
    decoded = codec.decode(encoded)
    np.testing.assert_allclose(decoded.temperature_k, state.temperature_k, rtol=2.0e-15)
    np.testing.assert_allclose(decoded.hydrogen_fraction, state.hydrogen_fraction)
    np.testing.assert_allclose(decoded.helium_fraction, state.helium_fraction)
    np.testing.assert_allclose(
        decoded.specific_material_energy_erg_g,
        state.specific_material_energy_erg_g,
        rtol=2.0e-15,
    )
    np.testing.assert_allclose(np.sum(decoded.hydrogen_fraction, axis=1), 1.0)
    np.testing.assert_allclose(np.sum(decoded.helium_fraction, axis=1), 1.0)


def test_log_simplex_codec_rejects_exact_population_boundary_without_floor():
    state = _material_state()
    hydrogen = np.array(state.hydrogen_fraction, copy=True)
    hydrogen[0] = (1.0, 0.0)
    with pytest.raises(PhysicalDomainError, match="positive interior"):
        GroundStateLogSimplexCodec(2).encode(
            state.temperature_k, hydrogen, state.helium_fraction
        )


def test_encoded_fixed_point_residual_closes_energy_and_populations_together():
    target = _material_state()
    codec = GroundStateLogSimplexCodec(2)

    def constant_response(_state):
        return target

    residual = EncodedMaterialFixedPointResidual(codec, constant_response)
    target_encoded = codec.encode(
        target.temperature_k, target.hydrogen_fraction, target.helium_fraction
    )
    np.testing.assert_array_equal(residual(target_encoded), np.zeros(codec.vector_size))
    perturbed = np.array(target_encoded, copy=True)
    perturbed[[0, 1, 6]] += np.array([0.1, -0.2, 0.3])
    np.testing.assert_allclose(residual(perturbed), target_encoded - perturbed)
    assert residual.evaluation_count == 2


def test_matrix_free_jacobian_vector_product_recovers_dense_linear_coupling():
    matrix = np.array(
        [
            [3.0, -1.0, 0.5],
            [2.0, 4.0, -0.25],
            [-1.5, 0.75, 2.5],
        ]
    )
    state = np.array([0.3, -0.7, 1.2])
    direction = np.array([1.0, 2.0, -0.5])

    def residual(value):
        return matrix @ value

    product = matrix_free_jacobian_vector_product(
        residual,
        state,
        residual(state),
        direction,
        relative_step=1.0e-7,
    )
    np.testing.assert_allclose(product, matrix @ direction, rtol=1.0e-8, atol=1.0e-8)


def test_matrix_free_newton_krylov_converges_coupled_nonlinear_system():
    root = np.array([0.2, -0.4, 0.7, -0.1])
    matrix = np.array(
        [
            [3.0, -0.4, 0.2, 0.1],
            [0.5, 2.5, -0.3, 0.2],
            [-0.2, 0.4, 2.8, -0.5],
            [0.1, -0.3, 0.6, 2.2],
        ]
    )

    def residual(value):
        offset = value - root
        return matrix @ offset + 0.05 * offset**3

    result = solve_matrix_free_newton_krylov(
        residual,
        np.array([1.0, -1.0, 1.4, 0.5]),
        residual_norm_tolerance=1.0e-10,
        maximum_newton_iterations=8,
        gmres_relative_tolerance=1.0e-6,
        maximum_gmres_iterations=4,
        jacobian_relative_step=1.0e-7,
        armijo_coefficient=1.0e-4,
        maximum_backtracking_steps=8,
    )
    assert result.converged is True
    np.testing.assert_allclose(result.state, root, atol=2.0e-10)
    assert np.all(np.diff(result.residual_norm_history) < 0.0)
    assert result.jacobian_vector_evaluation_count > 0


def test_newton_trial_acceptance_can_force_backtracking_without_clipping():
    target = np.array([0.0, 0.0])

    def residual(value):
        return value - target

    def trust_region(current, trial):
        return float(np.linalg.norm(trial - current)) <= 0.75

    result = solve_matrix_free_newton_krylov(
        residual,
        np.array([1.0, 0.0]),
        residual_norm_tolerance=1.0e-10,
        maximum_newton_iterations=4,
        gmres_relative_tolerance=1.0e-10,
        maximum_gmres_iterations=2,
        jacobian_relative_step=1.0e-7,
        armijo_coefficient=1.0e-4,
        maximum_backtracking_steps=4,
        trial_acceptance=trust_region,
    )
    assert result.converged is True
    assert result.accepted_relaxations[0] == 0.5


def test_matrix_free_newton_rejects_singular_constant_residual():
    with pytest.raises(ArithmeticError, match="GMRES failed"):
        solve_matrix_free_newton_krylov(
            lambda value: np.ones_like(value),
            np.array([0.0, 0.0]),
            residual_norm_tolerance=1.0e-8,
            maximum_newton_iterations=2,
            gmres_relative_tolerance=1.0e-8,
            maximum_gmres_iterations=2,
            jacobian_relative_step=1.0e-7,
            armijo_coefficient=1.0e-4,
            maximum_backtracking_steps=2,
        )


def test_physical_frozen_radiation_response_converges_in_encoded_state():
    codec = GroundStateLogSimplexCodec(1)
    old_temperature = np.array([2.0e4])
    old_hydrogen = np.array([[0.8, 0.2]])
    old_helium = np.array([[0.7, 0.2, 0.1]])
    density = np.array([1.0e-10])
    response = frozen_radiation_material_response(
        density,
        old_temperature,
        old_hydrogen,
        old_helium,
        0.1,
        np.array([[1.0, 0.5, 0.2]]),
        np.array([[1.0e-13, 8.0e-14, 6.0e-14]]),
        np.array([1.0e4]),
    )
    target = GroundStateMaterialState(
        response.temperature_k,
        response.hydrogen_fraction,
        response.helium_fraction,
        response.recovered_specific_material_energy_erg_g,
    )
    residual = EncodedMaterialFixedPointResidual(codec, lambda _state: target)
    initial = codec.encode(old_temperature, old_hydrogen, old_helium)
    acceptance = lambda current, trial: ground_state_material_trial_within_trust_region(
        codec,
        current,
        trial,
        maximum_relative_temperature_change=0.5,
        maximum_absolute_material_energy_increment_fraction=0.5,
        maximum_population_fraction_change=0.2,
    )
    result = solve_matrix_free_newton_krylov(
        residual,
        initial,
        residual_norm_tolerance=1.0e-10,
        maximum_newton_iterations=8,
        gmres_relative_tolerance=1.0e-6,
        maximum_gmres_iterations=4,
        jacobian_relative_step=1.0e-7,
        armijo_coefficient=1.0e-4,
        maximum_backtracking_steps=8,
        trial_acceptance=acceptance,
    )
    assert result.converged is True
    decoded = codec.decode(result.state)
    np.testing.assert_allclose(decoded.temperature_k, target.temperature_k, rtol=1.0e-10)
    np.testing.assert_allclose(
        decoded.hydrogen_fraction, target.hydrogen_fraction, rtol=1.0e-10
    )
    np.testing.assert_allclose(
        decoded.helium_fraction, target.helium_fraction, rtol=1.0e-10
    )
