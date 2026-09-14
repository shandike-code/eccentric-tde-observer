import inspect

import numpy as np
import pytest

from eccentric_tde_observer.mixed_frame_frequency import (
    comoving_group_radiation,
    frequency_group_p1_gauss_node_values,
    frequency_group_p1_from_gauss_node_values,
    frequency_group_p2_from_gauss_node_values,
    frequency_group_p2_gauss_node_values,
    frequency_group_p2_values_at_normalized_nodes,
    limit_nonnegative_frequency_group_p1,
    limit_nonnegative_frequency_group_p2,
    lorentz_ray_transform,
    lorentz_remap_comoving_group_emissivity_to_lab,
    lorentz_remap_signed_comoving_group_emissivity_perturbation_to_lab,
    lorentz_remap_comoving_group_extinction_to_lab,
    lorentz_remap_group_intensity,
    lorentz_remap_signed_group_intensity_perturbation,
    lorentz_remap_group_p1_density,
    lorentz_remap_group_p1_intensity,
    lorentz_remap_group_p2_intensity,
    threshold_log_frequency_groups,
)
from eccentric_tde_observer.mixed_frame_frequency import (
    _piecewise_constant_integral,
    _piecewise_constant_integral_columns,
    _piecewise_constant_overlap_integral_columns,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
)
from eccentric_tde_observer.source import PhysicalDomainError


def test_lorentz_ray_transform_recovers_radiation_tensor_boost():
    mu, weight = gauss_legendre_mu_weights(24)
    beta = 0.17
    transform = lorentz_ray_transform(mu, weight, beta)
    doppler = transform.doppler_lab_to_comoving
    comoving_intensity = 2.7
    lab_intensity = comoving_intensity / doppler**4
    lab_energy_ratio = 0.5 * np.sum(weight * lab_intensity) / comoving_intensity
    lab_flux_ratio = (
        0.5 * np.sum(weight * mu * lab_intensity) / comoving_intensity
    )
    lab_pressure_ratio = (
        0.5 * np.sum(weight * mu**2 * lab_intensity) / comoving_intensity
    )
    gamma2 = 1.0 / (1.0 - beta**2)
    assert lab_energy_ratio == pytest.approx(
        gamma2 * (1.0 + beta**2 / 3.0), rel=2.0e-13
    )
    assert lab_flux_ratio == pytest.approx(4.0 * gamma2 * beta / 3.0, rel=2.0e-13)
    assert lab_pressure_ratio == pytest.approx(
        gamma2 * (1.0 / 3.0 + beta**2), rel=2.0e-13
    )
    assert transform.angular_measure_relative_error < 2.0e-13


def test_group_remap_is_exact_for_constant_spectral_density():
    source_edge = np.geomspace(0.5, 4.0, 65)
    target_edge = np.geomspace(0.8, 2.5, 31)
    doppler = np.array([[0.91, 1.08], [1.04, 0.96]])
    source = np.broadcast_to(
        3.5, (source_edge.size - 1, *doppler.shape)
    ).copy()
    comoving = lorentz_remap_group_intensity(
        source,
        source_edge,
        target_edge,
        doppler,
        direction="lab_to_comoving",
    )
    assert np.allclose(comoving, 3.5 * doppler[None, ...] ** 3, rtol=3.0e-15)


def test_material_coefficient_remaps_use_their_own_lorentz_invariants():
    source_edge = np.geomspace(0.4, 5.0, 81)
    target_edge = np.geomspace(0.8, 2.5, 33)
    doppler = np.array([[0.91, 1.08], [1.04, 0.96]])
    emissivity = np.broadcast_to(
        2.3, (source_edge.size - 1, *doppler.shape)
    ).copy()
    extinction = np.broadcast_to(
        0.7, (source_edge.size - 1, *doppler.shape)
    ).copy()
    lab_emissivity = lorentz_remap_comoving_group_emissivity_to_lab(
        emissivity, source_edge, target_edge, doppler
    )
    lab_extinction = lorentz_remap_comoving_group_extinction_to_lab(
        extinction, source_edge, target_edge, doppler
    )
    np.testing.assert_allclose(
        lab_emissivity,
        np.broadcast_to(2.3 * doppler[None, ...] ** -2, lab_emissivity.shape),
        rtol=2.0e-14,
    )
    np.testing.assert_allclose(
        lab_extinction,
        np.broadcast_to(0.7 * doppler[None, ...], lab_extinction.shape),
        rtol=2.0e-14,
    )


def test_rigidly_boosted_isotropic_spectrum_recovers_comoving_mean():
    mu, weight = gauss_legendre_mu_weights(16)
    beta = np.array([0.08, -0.03])
    transform = lorentz_ray_transform(mu, weight, beta)
    source_edge = np.geomspace(0.5, 4.0, 129)
    target_edge = np.geomspace(0.8, 2.5, 65)
    comoving_constant = 4.2
    lab = np.broadcast_to(
        comoving_constant / transform.doppler_lab_to_comoving**3,
        (source_edge.size - 1, mu.size, beta.size),
    ).copy()
    result = comoving_group_radiation(
        lab,
        source_edge,
        target_edge,
        mu,
        weight,
        beta,
    )
    expected = comoving_constant * result.comoving_angular_measure[None, :]
    assert np.allclose(result.mean_intensity_density, expected, rtol=4.0e-15)
    assert np.max(np.abs(result.comoving_angular_measure - 1.0)) < 2.0e-13


def test_zero_velocity_group_remap_preserves_every_group():
    edge = np.geomspace(1.0, 100.0, 81)
    rng = np.random.default_rng(20260829)
    source = rng.random((edge.size - 1, 3, 4))
    remapped = lorentz_remap_group_intensity(
        source,
        edge,
        edge,
        np.ones((3, 4)),
        direction="lab_to_comoving",
    )
    assert np.array_equal(remapped, source)


def test_p1_gauss_projection_recovers_realizable_mean_and_moment():
    mean = np.array([[2.0, 3.0], [1.5, 0.7]])
    moment = np.array([[0.2, -0.4], [0.1, 0.05]])
    node = frequency_group_p1_gauss_node_values(mean, moment)
    recovered = frequency_group_p1_from_gauss_node_values(node)
    np.testing.assert_allclose(recovered.mean_density, mean, rtol=2.0e-16)
    np.testing.assert_allclose(recovered.first_moment_density, moment, rtol=5.0e-16)
    assert recovered.limited_group_count == 0


def test_p1_realizability_limiter_preserves_group_integral_not_point_values():
    mean = np.array([1.0, 2.0, 0.0])
    moment = np.array([0.6, -0.2, 0.0])
    result = limit_nonnegative_frequency_group_p1(mean, moment)
    assert np.array_equal(result.mean_density, mean)
    assert result.first_moment_density[0] == pytest.approx(1.0 / 3.0)
    assert result.first_moment_density[1] == -0.2
    assert result.first_moment_density[2] == 0.0
    assert result.limited_group_count == 1
    endpoint = np.stack(
        (
            result.mean_density - 3.0 * result.first_moment_density,
            result.mean_density + 3.0 * result.first_moment_density,
        )
    )
    assert np.all(endpoint >= 0.0)


def test_p2_gauss_projection_recovers_quadratic_legendre_moments():
    mean = np.array([2.0, 1.5])
    first = np.array([0.1, -0.08])
    second = np.array([0.04, 0.02])
    node = frequency_group_p2_gauss_node_values(mean, first, second)
    recovered = frequency_group_p2_from_gauss_node_values(node)
    np.testing.assert_allclose(recovered.mean_density, mean, rtol=4.0e-16)
    np.testing.assert_allclose(recovered.first_moment_density, first, rtol=8.0e-16)
    np.testing.assert_allclose(recovered.second_moment_density, second, rtol=2.0e-14)
    assert recovered.limited_group_count == 0


def test_p2_realizability_limiter_preserves_mean_and_removes_negative_vertex():
    mean = np.array([1.0, 2.0])
    first = np.array([0.0, 0.1])
    second = np.array([1.0, 0.02])
    result = limit_nonnegative_frequency_group_p2(mean, first, second)
    dense_node = np.linspace(-1.0, 1.0, 1001)
    values = (
        result.mean_density[:, None]
        + 3.0 * result.first_moment_density[:, None] * dense_node[None, :]
        + 2.5
        * result.second_moment_density[:, None]
        * (3.0 * dense_node[None, :] ** 2 - 1.0)
    )
    assert np.array_equal(result.mean_density, mean)
    assert result.limited_group_count == 1
    assert np.min(values) >= 0.0


def test_p2_limiter_handles_subnormal_wien_tail_without_a_floor():
    quantum = np.nextafter(0.0, 1.0)
    mean = np.array([4.0 * quantum])
    first = np.array([-3.0 * quantum])
    second = np.array([quantum])
    result = limit_nonnegative_frequency_group_p2(mean, first, second)
    values = frequency_group_p2_values_at_normalized_nodes(
        result.mean_density,
        result.first_moment_density,
        result.second_moment_density,
        np.polynomial.legendre.leggauss(8)[0],
    )
    assert np.array_equal(result.mean_density, mean)
    assert result.limited_group_count == 1
    assert np.all(values >= 0.0)


def test_p2_lorentz_remap_is_exact_for_global_quadratic_density():
    source_edge = np.linspace(0.5, 4.0, 49)
    target_edge = np.linspace(0.8, 2.5, 31)
    factor = np.array(0.93)

    def density(frequency):
        return 1.7 + 0.2 * frequency + 0.03 * frequency**2

    def project(edge, function):
        node, weight = np.polynomial.legendre.leggauss(8)
        centre = 0.5 * (edge[:-1] + edge[1:])
        half = 0.5 * np.diff(edge)
        frequency = centre[:, None] + half[:, None] * node[None, :]
        value = function(frequency)
        normalized_weight = 0.5 * weight[None, :]
        mean = np.sum(normalized_weight * value, axis=1)
        first = np.sum(normalized_weight * value * node[None, :], axis=1)
        second = np.sum(
            normalized_weight
            * value
            * 0.5
            * (3.0 * node[None, :] ** 2 - 1.0),
            axis=1,
        )
        return mean, first, second

    source = project(source_edge, density)
    result = lorentz_remap_group_p2_intensity(
        *source,
        source_edge,
        target_edge,
        factor,
        direction="lab_to_comoving",
    )
    expected = project(
        target_edge,
        lambda frequency: factor**3 * density(frequency / factor),
    )
    np.testing.assert_allclose(result.mean_density, expected[0], rtol=2.0e-13)
    np.testing.assert_allclose(
        result.first_moment_density, expected[1], rtol=1.0e-11, atol=2.0e-15
    )
    np.testing.assert_allclose(
        result.second_moment_density, expected[2], rtol=1.0e-8, atol=3.0e-14
    )
    assert result.limited_group_count == 0


def test_p1_lorentz_remap_is_exact_for_global_linear_density():
    source_edge = np.linspace(0.5, 5.0, 101)
    target_edge = np.linspace(1.0, 2.5, 41)
    doppler = np.array([0.92, 1.07])
    centre = 0.5 * (source_edge[:-1] + source_edge[1:])
    width = np.diff(source_edge)
    intercept = 2.0
    slope = 0.3
    mean = np.broadcast_to(
        intercept + slope * centre[:, None],
        (centre.size, doppler.size),
    ).copy()
    moment = np.broadcast_to(
        slope * width[:, None] / 6.0,
        mean.shape,
    ).copy()
    result = lorentz_remap_group_p1_density(
        mean,
        moment,
        source_edge,
        target_edge,
        doppler,
        direction="lab_to_comoving",
        invariant_frequency_power=0.0,
    )
    target_centre = 0.5 * (target_edge[:-1] + target_edge[1:])[:, None]
    target_width = np.diff(target_edge)[:, None]
    expected_mean = intercept + slope * target_centre / doppler[None, :]
    expected_moment = slope * target_width / (6.0 * doppler[None, :])
    np.testing.assert_allclose(result.mean_density, expected_mean, rtol=3.0e-14)
    np.testing.assert_allclose(
        result.first_moment_density,
        expected_moment,
        rtol=3.0e-11,
        atol=5.0e-14,
    )
    assert result.limited_group_count == 0


def test_zero_velocity_p1_intensity_remap_preserves_both_moments():
    edge = np.geomspace(1.0, 100.0, 81)
    rng = np.random.default_rng(20260829)
    mean = 1.0 + rng.random((edge.size - 1, 3, 2))
    moment = 0.1 * (rng.random(mean.shape) - 0.5) * mean
    remapped = lorentz_remap_group_p1_intensity(
        mean,
        moment,
        edge,
        edge,
        np.ones((3, 2)),
        direction="lab_to_comoving",
    )
    assert np.array_equal(remapped.mean_density, mean)
    assert np.array_equal(remapped.first_moment_density, moment)
    assert remapped.limited_group_count == 0


def test_threshold_group_grid_has_explicit_edges_and_guard_band():
    grid = threshold_log_frequency_groups(
        0.1,
        5000.0,
        32,
        maximum_velocity_beta=0.0081,
        guard_transform_count=2,
    )
    assert grid.extended_minimum_energy_ev < 0.1
    assert grid.extended_maximum_energy_ev > 5000.0
    assert np.count_nonzero(grid.physical_group_mask) > 150
    assert np.all(grid.width_hz > 0.0)


def test_out_of_band_remap_is_rejected_without_endpoint_repair():
    edge = np.geomspace(1.0, 10.0, 17)
    with pytest.raises(PhysicalDomainError):
        lorentz_remap_group_intensity(
            np.ones((16, 1)),
            edge,
            edge,
            np.array([1.01]),
            direction="lab_to_comoving",
        )
    source = inspect.getsource(lorentz_remap_group_intensity)
    assert "nan_to_num" not in source
    assert "np.clip" not in source
def test_batched_piecewise_constant_integral_matches_scalar_columns():
    edge = np.geomspace(1.0, 30.0, 19)
    width = np.diff(edge)
    density = 0.2 + np.arange(18 * 7, dtype=np.float64).reshape(18, 7) / 200.0
    lower = np.geomspace(1.0, 12.0, 11)[:, None] * np.ones((1, 7))
    upper = np.geomspace(2.0, 30.0, 11)[:, None] * np.ones((1, 7))
    upper[-1] = edge[-1]
    batched = _piecewise_constant_integral_columns(
        density, edge, width, lower, upper
    )
    expected = np.column_stack(
        [
            _piecewise_constant_integral(
                density[:, column], edge, lower[:, column], upper[:, column]
            )
            for column in range(density.shape[1])
        ]
    )
    assert np.array_equal(batched, expected)


def test_local_overlap_integral_is_invariant_to_source_slice_origin():
    edge = np.geomspace(1.0, 100.0, 81)
    width = np.diff(edge)
    density = 0.3 + np.arange(80 * 5, dtype=np.float64).reshape(80, 5) / 300.0
    lower = np.geomspace(edge[24], edge[45], 13)[:, None] * np.ones((1, 5))
    upper = np.geomspace(edge[25], edge[48], 13)[:, None] * np.ones((1, 5))
    full = _piecewise_constant_overlap_integral_columns(
        density, edge, width, lower, upper
    )
    start = 20
    stop = 52
    local = _piecewise_constant_overlap_integral_columns(
        density[start:stop],
        edge[start : stop + 1],
        width[start:stop],
        lower,
        upper,
    )
    assert np.array_equal(local, full)


def test_signed_intensity_perturbation_remap_is_linear_but_physical_path_rejects_it():
    source_edge = np.geomspace(0.5, 4.0, 65)
    target_edge = np.geomspace(0.8, 2.5, 31)
    doppler = np.array([[0.91, 1.08], [1.04, 0.96]])
    coordinate = np.linspace(-1.0, 1.0, 64)[:, None, None]
    first = coordinate * np.ones((1, *doppler.shape))
    second = (0.2 - 0.3 * coordinate**2) * np.ones((1, *doppler.shape))
    combined = lorentz_remap_signed_group_intensity_perturbation(
        first + second,
        source_edge,
        target_edge,
        doppler,
        direction="lab_to_comoving",
    )
    separate = lorentz_remap_signed_group_intensity_perturbation(
        first,
        source_edge,
        target_edge,
        doppler,
        direction="lab_to_comoving",
    ) + lorentz_remap_signed_group_intensity_perturbation(
        second,
        source_edge,
        target_edge,
        doppler,
        direction="lab_to_comoving",
    )
    assert np.allclose(combined, separate, rtol=3.0e-15, atol=3.0e-15)
    with pytest.raises(PhysicalDomainError, match="non-negative"):
        lorentz_remap_group_intensity(
            first,
            source_edge,
            target_edge,
            doppler,
            direction="lab_to_comoving",
        )


def test_signed_emissivity_perturbation_remap_accepts_negative_linear_response():
    edge = np.array([1.0, 2.0, 4.0])
    doppler = np.ones((2, 1))
    perturbation = np.array([[[-2.0], [1.0]], [[0.5], [-0.25]]])
    remapped = lorentz_remap_signed_comoving_group_emissivity_perturbation_to_lab(
        perturbation, edge, edge, doppler
    )
    assert np.array_equal(remapped, perturbation)
    with pytest.raises(PhysicalDomainError, match="non-negative"):
        lorentz_remap_comoving_group_emissivity_to_lab(
            perturbation, edge, edge, doppler
        )
