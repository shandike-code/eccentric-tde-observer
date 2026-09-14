from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S
from eccentric_tde_observer.radiative_transfer_1d import (
    evolve_time_dependent_slab,
    gauss_legendre_half_range_mu_weights,
    gauss_legendre_mu_weights,
    gauss_legendre_split_mu_weights,
    isothermal_absorption_top_flux,
    isothermal_absorption_top_intensity,
    linear_source_top_intensity,
    solve_static_slab_transfer,
)
from eccentric_tde_observer.source import PhysicalDomainError


def test_half_range_quadrature_recovers_each_hemisphere_moments():
    mu, weight = gauss_legendre_half_range_mu_weights(8)
    positive = mu > 0.0
    negative = mu < 0.0
    assert np.isclose(np.sum(weight[positive]), 1.0, rtol=0.0, atol=2.0e-15)
    assert np.isclose(np.sum(weight[negative]), 1.0, rtol=0.0, atol=2.0e-15)
    assert np.isclose(
        np.sum(weight[positive] * mu[positive]), 0.5, rtol=0.0, atol=2.0e-15
    )
    assert np.isclose(
        np.sum(weight[negative] * mu[negative]), -0.5, rtol=0.0, atol=2.0e-15
    )
    assert np.array_equal(mu, -mu[::-1])
    assert np.array_equal(weight, weight[::-1])


def test_split_quadrature_recovers_moments_on_both_characteristic_intervals():
    split = -0.17
    mu, weight = gauss_legendre_split_mu_weights(8, split)
    left = mu < split
    right = mu > split
    assert np.count_nonzero(left) == np.count_nonzero(right) == 4
    assert np.isclose(np.sum(weight[left]), split + 1.0, atol=2.0e-15)
    assert np.isclose(np.sum(weight[right]), 1.0 - split, atol=2.0e-15)
    assert np.isclose(
        np.sum(weight[left] * mu[left]),
        0.5 * (split**2 - 1.0),
        atol=2.0e-15,
    )
    assert np.isclose(
        np.sum(weight[right] * mu[right]),
        0.5 * (1.0 - split**2),
        atol=2.0e-15,
    )
    assert np.isclose(np.sum(weight), 2.0, atol=2.0e-15)


def test_vacuum_formal_solution_preserves_incident_intensity():
    mu, weight = gauss_legendre_mu_weights(8)
    top = np.zeros((1, mu.size))
    bottom = np.zeros((1, mu.size))
    top[:, mu > 0.0] = 2.0
    bottom[:, mu < 0.0] = 3.0
    result = solve_static_slab_transfer(
        [1.0e15],
        np.linspace(0.0, 4.0, 17),
        mu,
        weight,
        extinction_per_cm=0.0,
        thermal_source_intensity=0.0,
        absorption_probability=1.0,
        top_incoming_intensity=top,
        bottom_incoming_intensity=bottom,
    )

    assert np.all(result.intensity_cell_average[0, mu > 0.0] == 2.0)
    assert np.all(result.intensity_cell_average[0, mu < 0.0] == 3.0)
    assert np.all(result.source_equation_residual == 0.0)
    assert np.all(result.relative_energy_balance_residual < 2.0e-15)


def test_isothermal_absorption_recovers_angle_resolved_analytic_solution():
    mu, weight = gauss_legendre_mu_weights(12)
    source = np.array([1.5, 3.0])
    result = solve_static_slab_transfer(
        [5.0e14, 1.0e15],
        np.linspace(0.0, 1.0, 33),
        mu,
        weight,
        extinction_per_cm=2.0,
        thermal_source_intensity=source[:, None],
        absorption_probability=1.0,
    )
    outgoing = mu < 0.0
    expected = isothermal_absorption_top_intensity(
        source[:, None], 2.0, np.abs(mu[outgoing])[None, :]
    )

    assert np.allclose(
        result.top_boundary_intensity[:, outgoing], expected, rtol=3.0e-15, atol=0.0
    )
    assert np.all(result.source_equation_residual == 0.0)
    assert np.all(result.relative_energy_balance_residual < 2.0e-14)


def test_angle_quadrature_converges_to_isothermal_analytic_flux():
    analytic = float(isothermal_absorption_top_flux(2.0, 1.0))
    errors = []
    for angular_order in (8, 16, 32, 64):
        mu, weight = gauss_legendre_mu_weights(angular_order)
        result = solve_static_slab_transfer(
            [1.0e15], [0.0, 1.0], mu, weight, 1.0, 2.0, 1.0
        )
        errors.append(abs(-float(result.top_net_flux[0]) / analytic - 1.0))

    assert errors[0] > errors[1] > errors[2] > errors[3]
    assert errors[-1] < 2.6e-4


def test_piecewise_constant_formal_solution_is_second_order_for_linear_source():
    mu, weight = gauss_legendre_mu_weights(8)
    outgoing = mu < 0.0
    expected = linear_source_top_intensity(1.0, 0.7, 2.0, np.abs(mu[outgoing]))
    errors = []
    for depth_points in (16, 32, 64):
        edges = np.linspace(0.0, 1.0, depth_points + 1)
        centers = 0.5 * (edges[:-1] + edges[1:])
        result = solve_static_slab_transfer(
            [1.0e15], edges, mu, weight, 2.0, 1.0 + 0.7 * centers, 1.0
        )
        errors.append(
            float(
                np.max(
                    np.abs(result.top_boundary_intensity[0, outgoing] - expected)
                )
            )
        )

    assert errors[0] / errors[1] > 3.9
    assert errors[1] / errors[2] > 3.9


@pytest.mark.parametrize("total_optical_depth", [0.1, 1.0, 10.0, 199.1])
def test_pure_scattering_conserves_one_sided_incident_flux(total_optical_depth):
    mu, weight = gauss_legendre_mu_weights(12)
    top = np.zeros((1, mu.size))
    top[:, mu > 0.0] = 1.0
    result = solve_static_slab_transfer(
        [1.0e15],
        np.linspace(0.0, 1.0, 65),
        mu,
        weight,
        total_optical_depth,
        0.0,
        0.0,
        top_incoming_intensity=top,
    )
    incident = 2.0 * np.pi * np.sum(weight[mu > 0.0] * mu[mu > 0.0])
    reflected = 2.0 * np.pi * np.sum(
        weight[mu < 0.0]
        * (-mu[mu < 0.0])
        * result.top_boundary_intensity[0, mu < 0.0]
    )
    transmitted = 2.0 * np.pi * np.sum(
        weight[mu > 0.0]
        * mu[mu > 0.0]
        * result.bottom_boundary_intensity[0, mu > 0.0]
    )

    assert np.isclose((reflected + transmitted) / incident, 1.0, rtol=3.0e-12)
    assert result.source_equation_residual[0] < 2.0e-13
    assert result.relative_energy_balance_residual[0] < 3.0e-12
    assert np.min(result.intensity_cell_average) >= 0.0


def test_sparse_interface_solver_matches_dense_lambda_on_inhomogeneous_slab():
    mu, weight = gauss_legendre_half_range_mu_weights(8)
    edges = np.linspace(0.0, 1.0, 13) ** 1.4
    centres = 0.5 * (edges[:-1] + edges[1:])
    extinction = 0.3 + 7.0 * centres**2
    thermal_source = 0.7 + 0.4 * np.sin(np.pi * centres) ** 2
    epsilon = 0.02 + 0.7 * centres
    top = np.zeros((1, mu.size))
    bottom = np.zeros((1, mu.size))
    top[:, mu > 0.0] = 0.13
    bottom[:, mu < 0.0] = 0.07
    dense = solve_static_slab_transfer(
        [1.0e15],
        edges,
        mu,
        weight,
        extinction,
        thermal_source,
        epsilon,
        top_incoming_intensity=top,
        bottom_incoming_intensity=bottom,
        scattering_linear_solver="dense_lambda",
    )
    sparse = solve_static_slab_transfer(
        [1.0e15],
        edges,
        mu,
        weight,
        extinction,
        thermal_source,
        epsilon,
        top_incoming_intensity=top,
        bottom_incoming_intensity=bottom,
        scattering_linear_solver="sparse_interface",
    )

    for candidate, reference in (
        (sparse.intensity_cell_average, dense.intensity_cell_average),
        (sparse.source_function, dense.source_function),
        (sparse.mean_intensity, dense.mean_intensity),
        (sparse.top_boundary_intensity, dense.top_boundary_intensity),
        (sparse.bottom_boundary_intensity, dense.bottom_boundary_intensity),
        (sparse.top_net_flux, dense.top_net_flux),
        (sparse.bottom_net_flux, dense.bottom_net_flux),
    ):
        assert np.allclose(candidate, reference, rtol=2.0e-12, atol=2.0e-14)
    assert sparse.scattering_linear_solver == "sparse_interface"
    assert np.max(sparse.source_equation_residual) < 2.0e-13
    assert np.max(sparse.relative_energy_balance_residual) < 2.0e-13


def test_time_dependent_vacuum_advection_translates_exactly_at_unit_cfl():
    mu = np.array([-0.5, 0.5])
    weight = np.array([1.0, 1.0])
    edges = np.arange(17, dtype=np.float64) * LIGHT_SPEED_CM_S
    initial = np.zeros((1, 2, 16))
    initial[0, 1, 2:5] = 1.0
    initial[0, 0, 9:12] = 2.0
    result = evolve_time_dependent_slab(
        [1.0e15],
        edges,
        mu,
        weight,
        initial,
        0.0,
        0.0,
        1.0,
        6.0,
        periodic_spatial_boundary=True,
        maximum_cfl=1.0,
    )
    expected = initial.copy()
    expected[0, 1] = np.roll(expected[0, 1], 3)
    expected[0, 0] = np.roll(expected[0, 0], -3)

    assert np.array_equal(result.final_intensity, expected)
    assert result.time_steps == 3
    assert result.maximum_transport_cfl == 1.0
    assert np.array_equal(result.initial_radiation_content, result.final_radiation_content)


def test_time_dependent_absorption_decay_is_exact_for_uniform_periodic_field():
    mu = np.array([-0.5, 0.5])
    weight = np.array([1.0, 1.0])
    edges = np.arange(17, dtype=np.float64) * LIGHT_SPEED_CM_S
    initial = np.full((1, 2, 16), 2.0)
    extinction = 1.0 / LIGHT_SPEED_CM_S
    result = evolve_time_dependent_slab(
        [1.0e15],
        edges,
        mu,
        weight,
        initial,
        extinction,
        0.0,
        1.0,
        1.3,
        periodic_spatial_boundary=True,
    )

    assert np.allclose(result.final_intensity, 2.0 * np.exp(-1.3), rtol=2.0e-15)


def test_time_dependent_pure_scattering_preserves_mean_and_relaxes_anisotropy():
    mu = np.array([-0.5, 0.5])
    weight = np.array([1.0, 1.0])
    edges = np.arange(17, dtype=np.float64) * LIGHT_SPEED_CM_S
    initial = np.empty((1, 2, 16))
    initial[:, 0] = 1.0
    initial[:, 1] = 3.0
    extinction = 1.0 / LIGHT_SPEED_CM_S
    result = evolve_time_dependent_slab(
        [1.0e15],
        edges,
        mu,
        weight,
        initial,
        extinction,
        0.0,
        0.0,
        1.3,
        periodic_spatial_boundary=True,
    )
    expected = 2.0 + np.array([-1.0, 1.0]) * np.exp(-1.3)

    assert np.allclose(result.final_intensity[0, :, 0], expected, rtol=2.0e-15)
    assert np.allclose(
        result.final_radiation_content,
        result.initial_radiation_content,
        rtol=2.0e-15,
    )


def test_time_dependent_absorption_approaches_static_limit_with_depth_refinement():
    mu, weight = gauss_legendre_mu_weights(4)
    errors = []
    for depth_points in (16, 32, 64):
        edges = np.linspace(0.0, LIGHT_SPEED_CM_S, depth_points + 1)
        static = solve_static_slab_transfer(
            [1.0e15], edges, mu, weight, 1.0 / LIGHT_SPEED_CM_S, 1.0, 1.0
        )
        time_dependent = evolve_time_dependent_slab(
            [1.0e15],
            edges,
            mu,
            weight,
            0.0,
            1.0 / LIGHT_SPEED_CM_S,
            1.0,
            1.0,
            10.0,
        )
        errors.append(
            float(
                np.max(
                    np.abs(
                        time_dependent.final_intensity
                        - static.intensity_cell_average
                    )
                )
            )
        )

    assert errors[0] > errors[1] > errors[2]
    assert errors[1] / errors[2] > 1.8


def test_transfer_inputs_reject_invalid_boundaries_and_cfl():
    mu, weight = gauss_legendre_mu_weights(4)
    invalid_top = np.zeros((1, mu.size))
    invalid_top[:, mu < 0.0] = 1.0
    with pytest.raises(PhysicalDomainError, match="top boundary"):
        solve_static_slab_transfer(
            [1.0e15], [0.0, 1.0], mu, weight, 1.0, 1.0, 1.0,
            top_incoming_intensity=invalid_top,
        )
    with pytest.raises(PhysicalDomainError, match="maximum_cfl"):
        evolve_time_dependent_slab(
            [1.0e15], [0.0, 1.0], mu, weight, 0.0, 0.0, 0.0, 1.0, 1.0,
            maximum_cfl=1.1,
        )
    with pytest.raises(PhysicalDomainError, match="scattering linear solver"):
        solve_static_slab_transfer(
            [1.0e15],
            [0.0, 1.0],
            mu,
            weight,
            1.0,
            1.0,
            0.5,
            scattering_linear_solver="invalid",
        )


def test_transfer_source_does_not_use_forbidden_masking_helpers():
    from eccentric_tde_observer import radiative_transfer_1d

    source_text = open(radiative_transfer_1d.__file__, encoding="utf-8").read()
    assert "nan_to_num" not in source_text
    assert "np.clip" not in source_text
