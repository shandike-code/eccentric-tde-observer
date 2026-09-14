import inspect

import numpy as np
import pytest

from eccentric_tde_observer.implicit_radiative_transfer_1d import (
    solve_implicit_ale_slab_step,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_half_range_mu_weights,
    solve_static_slab_transfer,
)
from eccentric_tde_observer.source import PhysicalDomainError


def _angles(order: int = 4):
    return gauss_legendre_half_range_mu_weights(order)


def test_periodic_uniform_absorption_recovers_backward_euler_relaxation():
    mu, weight = _angles(4)
    edges = np.linspace(0.0, 2.0e12, 33)
    initial = 2.0
    thermal = 5.0
    extinction = 1.0e-10
    duration = 1.0e3
    speed = 2.5e10
    result = solve_implicit_ale_slab_step(
        [1.0e15],
        edges,
        edges,
        mu,
        weight,
        initial,
        extinction,
        thermal,
        1.0,
        duration,
        periodic_spatial_boundary=True,
        propagation_speed_cm_s=speed,
    )
    exact = (
        initial + speed * extinction * duration * thermal
    ) / (1.0 + speed * extinction * duration)
    np.testing.assert_allclose(result.final_intensity, exact, rtol=2.0e-13)
    assert np.max(result.relative_linear_system_residual) < 2.0e-14
    assert np.max(result.relative_energy_ledger_residual) < 2.0e-11


def test_pure_scattering_periodic_column_conserves_radiation_energy():
    mu, weight = _angles(8)
    edges = np.linspace(0.0, 1.0e12, 49)
    centre = 0.5 * (edges[:-1] + edges[1:])
    initial = (
        2.0
        + 0.2 * mu[None, :, None]
        + 0.1 * np.sin(2.0 * np.pi * centre / edges[-1])[None, None, :]
    )
    result = solve_implicit_ale_slab_step(
        [1.0e15],
        edges,
        edges,
        mu,
        weight,
        initial,
        3.0e-12,
        0.0,
        0.0,
        2.0e3,
        periodic_spatial_boundary=True,
    )
    np.testing.assert_allclose(
        result.final_radiation_energy_nu_erg_cm2_hz,
        result.initial_radiation_energy_nu_erg_cm2_hz,
        rtol=3.0e-13,
    )
    assert np.max(np.abs(result.material_heating_nu_erg_s_cm2_hz)) == 0.0
    assert np.max(result.relative_energy_ledger_residual) < 2.0e-13


def test_expanding_ale_grid_preserves_uniform_vacuum_field():
    mu, weight = _angles(4)
    old_edges = np.linspace(-1.0, 1.0, 17)
    new_edges = np.linspace(-1.12, 1.12, 17)
    uniform = 3.0
    result = solve_implicit_ale_slab_step(
        [1.0],
        old_edges,
        new_edges,
        mu,
        weight,
        uniform,
        0.0,
        0.0,
        1.0,
        1.0,
        left_exterior_intensity=uniform,
        right_exterior_intensity=uniform,
        propagation_speed_cm_s=2.0,
    )
    np.testing.assert_allclose(result.final_intensity, uniform, rtol=3.0e-15)
    assert result.maximum_mesh_speed_to_light == pytest.approx(0.06)
    assert np.max(result.relative_energy_ledger_residual) < 2.0e-14


def _periodic_advection_error(depth_points: int) -> float:
    mu, weight = _angles(4)
    length = 1.0
    edges = np.linspace(0.0, length, depth_points + 1)
    centre = 0.5 * (edges[:-1] + edges[1:])
    initial = 1.0 + 0.2 * np.sin(2.0 * np.pi * centre)[None, None, :]
    duration = 0.4 / depth_points
    result = solve_implicit_ale_slab_step(
        [1.0],
        edges,
        edges,
        mu,
        weight,
        initial,
        0.0,
        0.0,
        1.0,
        duration,
        periodic_spatial_boundary=True,
        propagation_speed_cm_s=1.0,
    )
    exact = 1.0 + 0.2 * np.sin(
        2.0 * np.pi * (centre[None, :] - mu[:, None] * duration)
    )
    return float(np.max(np.abs(result.final_intensity[0] - exact)))


def test_periodic_vacuum_advection_converges_without_cfl_restriction():
    errors = [_periodic_advection_error(points) for points in (32, 64, 128)]
    assert errors[1] < 0.55 * errors[0]
    assert errors[2] < 0.55 * errors[1]


def _static_absorption_error(depth_points: int) -> float:
    mu, weight = _angles(8)
    edges = np.linspace(0.0, 1.0, depth_points + 1)
    extinction = np.full((1, depth_points), 2.0)
    thermal = np.full_like(extinction, 4.0)
    epsilon = np.ones_like(extinction)
    implicit = solve_implicit_ale_slab_step(
        [1.0],
        edges,
        edges,
        mu,
        weight,
        0.0,
        extinction,
        thermal,
        epsilon,
        1.0e7,
        propagation_speed_cm_s=1.0,
    )
    formal = solve_static_slab_transfer(
        [1.0], edges, mu, weight, extinction, thermal, epsilon
    )
    return float(
        np.max(
            np.abs(
                implicit.mean_intensity - formal.mean_intensity
            )
        )
    )


def test_long_implicit_step_converges_to_frozen_formal_solution_with_depth():
    errors = [_static_absorption_error(points) for points in (128, 256, 512)]
    assert errors[1] < 0.60 * errors[0]
    assert errors[2] < 0.60 * errors[1]


def test_open_emitting_slab_closes_discrete_radiation_energy_ledger():
    mu, weight = _angles(8)
    old_edges = np.linspace(-2.0e11, 2.0e11, 41)
    new_edges = 1.003 * old_edges
    depth_points = old_edges.size - 1
    depth = np.arange(depth_points, dtype=np.float64)
    extinction = (1.0e-11 + 4.0e-11 * (depth + 1.0) / depth_points)[None, :]
    thermal = (2.0 + 0.5 * np.cos(2.0 * np.pi * (depth + 0.5) / depth_points))[None, :]
    result = solve_implicit_ale_slab_step(
        [1.0e15],
        old_edges,
        new_edges,
        mu,
        weight,
        0.4,
        extinction,
        thermal,
        0.35,
        300.0,
    )
    assert result.minimum_intensity >= 0.0
    assert np.max(result.relative_linear_system_residual) < 2.0e-14
    assert np.max(result.relative_energy_ledger_residual) < 2.0e-12


def test_invalid_periodic_motion_and_forbidden_repairs_are_rejected():
    mu, weight = _angles(4)
    old_edges = np.linspace(0.0, 1.0, 5)
    new_edges = np.array([0.0, 0.2, 0.5, 0.8, 1.1])
    with pytest.raises(PhysicalDomainError):
        solve_implicit_ale_slab_step(
            [1.0],
            old_edges,
            new_edges,
            mu,
            weight,
            1.0,
            0.0,
            0.0,
            1.0,
            1.0,
            periodic_spatial_boundary=True,
            propagation_speed_cm_s=1.0,
        )
    source = inspect.getsource(solve_implicit_ale_slab_step)
    assert "nan_to_num" not in source
    assert "np.clip" not in source


def test_bicgstab_matches_sparse_lu_without_fill_factorization():
    mu, weight = _angles(8)
    old_edges = np.linspace(-3.0, 3.0, 65)
    new_edges = 1.001 * old_edges
    depth = 0.5 * (new_edges[:-1] + new_edges[1:])
    extinction = (0.4 + 0.2 * np.cos(depth))[None, :]
    thermal = (1.1 + 0.15 * np.sin(depth))[None, :]
    initial = np.broadcast_to(
        (0.8 + 0.05 * mu[:, None] + 0.03 * depth[None, :])[None, ...],
        (1, mu.size, depth.size),
    ).copy()
    common = dict(
        frequency_hz=[1.0e15],
        old_depth_edges_cm=old_edges,
        new_depth_edges_cm=new_edges,
        direction_cosine=mu,
        angular_weight=weight,
        initial_intensity=initial,
        extinction_per_cm=extinction,
        thermal_source_intensity=thermal,
        absorption_probability=0.25,
        duration_s=0.4,
        propagation_speed_cm_s=1.0,
    )
    direct = solve_implicit_ale_slab_step(**common, linear_solver="sparse_lu")
    iterative = solve_implicit_ale_slab_step(
        **common,
        linear_solver="bicgstab",
        iterative_tolerance=2.0e-13,
    )
    scale = np.max(np.abs(direct.final_intensity))
    error = np.max(np.abs(iterative.final_intensity - direct.final_intensity)) / scale
    assert error < 2.0e-11
    assert iterative.linear_solver == "bicgstab"
    assert np.max(iterative.linear_iterations) < 512
    assert np.max(iterative.relative_energy_ledger_residual) < 2.0e-11


def test_positive_source_iteration_matches_sparse_lu():
    mu, weight = _angles(8)
    old_edges = np.linspace(-2.0, 2.0, 49)
    new_edges = 1.002 * old_edges
    depth = 0.5 * (new_edges[:-1] + new_edges[1:])
    common = dict(
        frequency_hz=[7.0e14, 2.0e15],
        old_depth_edges_cm=old_edges,
        new_depth_edges_cm=new_edges,
        direction_cosine=mu,
        angular_weight=weight,
        initial_intensity=0.7 + 0.03 * mu[None, :, None],
        extinction_per_cm=np.vstack(
            (0.2 + 0.03 * np.cos(depth), 0.5 + 0.04 * np.sin(depth))
        ),
        thermal_source_intensity=np.vstack(
            (1.0 + 0.05 * np.sin(depth), 0.9 + 0.08 * np.cos(depth))
        ),
        absorption_probability=np.array([[0.3], [0.08]]),
        duration_s=0.3,
        propagation_speed_cm_s=1.0,
    )
    direct = solve_implicit_ale_slab_step(**common, linear_solver="sparse_lu")
    iterative = solve_implicit_ale_slab_step(
        **common,
        linear_solver="source_iteration",
        iterative_tolerance=1.0e-12,
    )
    difference = np.max(np.abs(iterative.final_intensity - direct.final_intensity))
    scale = np.max(np.abs(direct.final_intensity))
    assert difference / scale < 2.0e-11
    assert iterative.minimum_intensity >= 0.0
    assert np.max(iterative.relative_energy_ledger_residual) < 2.0e-10
