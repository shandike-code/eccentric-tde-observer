from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.atomic_continuum import ground_state_saha_factor_cm3
from eccentric_tde_observer.continuum_emission import IONIZATION_ENERGIES_EV
from eccentric_tde_observer.mixed_frame_frequency import (
    limit_nonnegative_frequency_group_p1,
    limit_nonnegative_frequency_group_p2,
    threshold_log_frequency_groups,
)
from eccentric_tde_observer.multigroup_continuum import (
    gauss_legendre_frequency_group_quadrature,
    ground_state_milne_multigroup,
    ground_state_milne_p1_multigroup,
    ground_state_milne_p2_multigroup,
    group_average_from_quadrature_nodes,
    group_p1_moment_from_quadrature_nodes,
    group_p1_values_at_quadrature_nodes,
    group_p2_second_moment_from_quadrature_nodes,
    group_p2_values_at_quadrature_nodes,
)
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.radiation import planck_nu
from eccentric_tde_observer.source import PhysicalDomainError


TEMPERATURE_K = 4.0e4
DENSITY_G_CM3 = 1.0e-10


def test_group_quadrature_integrates_constant_and_linear_frequency_exactly():
    edge = np.geomspace(1.0e14, 1.0e18, 19)
    quadrature = gauss_legendre_frequency_group_quadrature(
        edge, order_per_group=4
    )
    constant = group_average_from_quadrature_nodes(
        np.ones_like(quadrature.node_hz), quadrature
    )
    linear = group_average_from_quadrature_nodes(
        quadrature.node_hz, quadrature
    )
    np.testing.assert_allclose(constant, 1.0, rtol=4.0e-16, atol=0.0)
    np.testing.assert_allclose(
        linear, quadrature.group_centre_hz, rtol=4.0e-16, atol=0.0
    )
    assert np.all(quadrature.node_weight_hz > 0.0)
    assert not quadrature.node_hz.flags.writeable


def test_group_p1_projection_recovers_linear_frequency_density_exactly():
    edge = np.geomspace(1.0e14, 1.0e18, 19)
    quadrature = gauss_legendre_frequency_group_quadrature(
        edge, order_per_group=4
    )
    scale = 1.0e18
    node = 2.0 + 0.3 * quadrature.node_hz / scale
    mean = group_average_from_quadrature_nodes(node, quadrature)
    moment = group_p1_moment_from_quadrature_nodes(node, quadrature)
    expected_moment = 0.3 * quadrature.group_width_hz / (6.0 * scale)
    np.testing.assert_allclose(
        mean,
        2.0 + 0.3 * quadrature.group_centre_hz / scale,
        rtol=4.0e-16,
    )
    np.testing.assert_allclose(moment, expected_moment, rtol=4.0e-11, atol=4.0e-16)
    reconstructed = group_p1_values_at_quadrature_nodes(
        mean, moment, quadrature
    )
    np.testing.assert_allclose(reconstructed, node, rtol=5.0e-16)


def _lte_multigroup(groups_per_decade: int):
    grid = threshold_log_frequency_groups(0.1, 5000.0, groups_per_decade)
    quadrature = gauss_legendre_frequency_group_quadrature(
        grid.edge_hz, order_per_group=16
    )
    group_planck = group_average_from_quadrature_nodes(
        planck_nu(quadrature.node_hz, TEMPERATURE_K), quadrature
    )[:, None]
    state = lte_hydrogen_helium_ionization(DENSITY_G_CM3, TEMPERATURE_K)
    result = ground_state_milne_multigroup(
        DENSITY_G_CM3,
        TEMPERATURE_K,
        grid.edge_hz,
        group_planck,
        state.hydrogen_neutral_fraction,
        state.hydrogen_ionized_fraction,
        state.helium_neutral_fraction,
        state.helium_singly_ionized_fraction,
        state.helium_doubly_ionized_fraction,
        order_per_group=16,
    )
    saha = np.array(
        [
            ground_state_saha_factor_cm3(TEMPERATURE_K, energy)
            for energy in IONIZATION_ENERGIES_EV
        ]
    )
    recombination = result.radiative_rates.total_recombination_cm3_s[0]
    rate_error = np.max(
        np.abs(result.radiative_rates.photoionization_s1[0] / saha - recombination)
        / recombination
    )
    energy_scale = max(
        float(result.absorbed_power_erg_s_cm3[0]),
        float(result.emitted_power_erg_s_cm3[0]),
    )
    heating_error = float(
        np.abs(result.radiative_heating_erg_s_cm3[0]) / energy_scale
    )
    return result, rate_error, heating_error


def test_multigroup_lte_error_decreases_without_posthoc_balance_repair():
    coarse, coarse_rate, coarse_heating = _lte_multigroup(32)
    fine, fine_rate, fine_heating = _lte_multigroup(128)
    assert fine_rate < coarse_rate
    assert fine_heating < coarse_heating
    assert fine_rate < 2.0e-3
    assert fine_heating < 1.0e-3
    assert np.all(fine.continuum.extinction_total_per_cm >= 0.0)
    assert np.all(fine.mean_intensity_cgs >= 0.0)
    assert not fine.radiative_heating_erg_s_cm3.flags.writeable


def test_p1_multigroup_improves_coarse_planck_lte_rate_and_energy_balance():
    grid = threshold_log_frequency_groups(0.1, 5000.0, 32)
    quadrature = gauss_legendre_frequency_group_quadrature(
        grid.edge_hz, order_per_group=16
    )
    node_planck = planck_nu(quadrature.node_hz, TEMPERATURE_K)
    mean = group_average_from_quadrature_nodes(node_planck, quadrature)[:, None]
    moment = group_p1_moment_from_quadrature_nodes(
        node_planck, quadrature
    )[:, None]
    # Wien 尾的正函数投影未必是端点非负的线性函数；只限制一次矩并保留组平均。
    radiation_state = limit_nonnegative_frequency_group_p1(mean, moment)
    state = lte_hydrogen_helium_ionization(DENSITY_G_CM3, TEMPERATURE_K)
    p1 = ground_state_milne_p1_multigroup(
        DENSITY_G_CM3,
        TEMPERATURE_K,
        grid.edge_hz,
        mean,
        radiation_state.first_moment_density,
        state.hydrogen_neutral_fraction,
        state.hydrogen_ionized_fraction,
        state.helium_neutral_fraction,
        state.helium_singly_ionized_fraction,
        state.helium_doubly_ionized_fraction,
        order_per_group=16,
    )
    p0, p0_rate_error, p0_heating_error = _lte_multigroup(32)
    saha = np.array(
        [
            ground_state_saha_factor_cm3(TEMPERATURE_K, energy)
            for energy in IONIZATION_ENERGIES_EV
        ]
    )
    recombination = p1.radiative_rates.total_recombination_cm3_s[0]
    p1_rate_error = np.max(
        np.abs(p1.radiative_rates.photoionization_s1[0] / saha - recombination)
        / recombination
    )
    energy_scale = max(
        float(p1.absorbed_power_erg_s_cm3[0]),
        float(p1.emitted_power_erg_s_cm3[0]),
    )
    p1_heating_error = abs(float(p1.radiative_heating_erg_s_cm3[0])) / energy_scale
    assert p1_rate_error < p0_rate_error
    assert p1_heating_error < p0_heating_error
    assert p1_rate_error < 5.0e-4
    assert p1_heating_error < 5.0e-4
    assert p1.continuum_limited_group_count >= 0
    assert radiation_state.limited_group_count > 0
    assert np.array_equal(p0.mean_intensity_cgs, mean)


def test_p2_projection_recovers_quadratic_frequency_density_exactly():
    edge = np.geomspace(1.0e14, 1.0e18, 19)
    quadrature = gauss_legendre_frequency_group_quadrature(
        edge, order_per_group=6
    )
    scale = 1.0e18
    node = 2.0 + 0.2 * quadrature.node_hz / scale + 0.04 * (
        quadrature.node_hz / scale
    ) ** 2
    mean = group_average_from_quadrature_nodes(node, quadrature)
    first = group_p1_moment_from_quadrature_nodes(node, quadrature)
    second = group_p2_second_moment_from_quadrature_nodes(node, quadrature)
    reconstructed = group_p2_values_at_quadrature_nodes(
        mean, first, second, quadrature
    )
    np.testing.assert_allclose(reconstructed, node, rtol=8.0e-15, atol=5.0e-16)


def test_p2_multigroup_improves_coarse_planck_lte_over_p1():
    grid = threshold_log_frequency_groups(0.1, 5000.0, 32)
    quadrature = gauss_legendre_frequency_group_quadrature(
        grid.edge_hz, order_per_group=16
    )
    node_planck = planck_nu(quadrature.node_hz, TEMPERATURE_K)
    mean = group_average_from_quadrature_nodes(node_planck, quadrature)[:, None]
    first = group_p1_moment_from_quadrature_nodes(
        node_planck, quadrature
    )[:, None]
    second = group_p2_second_moment_from_quadrature_nodes(
        node_planck, quadrature
    )[:, None]
    p2_input = limit_nonnegative_frequency_group_p2(mean, first, second)
    p1_input = limit_nonnegative_frequency_group_p1(mean, first)
    ion = lte_hydrogen_helium_ionization(DENSITY_G_CM3, TEMPERATURE_K)
    common = (
        DENSITY_G_CM3,
        TEMPERATURE_K,
        grid.edge_hz,
        mean,
    )
    fractions = (
        ion.hydrogen_neutral_fraction,
        ion.hydrogen_ionized_fraction,
        ion.helium_neutral_fraction,
        ion.helium_singly_ionized_fraction,
        ion.helium_doubly_ionized_fraction,
    )
    p1 = ground_state_milne_p1_multigroup(
        *common,
        p1_input.first_moment_density,
        *fractions,
        order_per_group=16,
    )
    p2 = ground_state_milne_p2_multigroup(
        *common,
        p2_input.first_moment_density,
        p2_input.second_moment_density,
        *fractions,
        order_per_group=16,
    )
    saha = np.array(
        [
            ground_state_saha_factor_cm3(TEMPERATURE_K, energy)
            for energy in IONIZATION_ENERGIES_EV
        ]
    )

    def errors(result):
        recombination = result.radiative_rates.total_recombination_cm3_s[0]
        rate = np.max(
            np.abs(result.radiative_rates.photoionization_s1[0] / saha - recombination)
            / recombination
        )
        scale = max(
            float(result.absorbed_power_erg_s_cm3[0]),
            float(result.emitted_power_erg_s_cm3[0]),
        )
        heating = abs(float(result.radiative_heating_erg_s_cm3[0])) / scale
        return rate, heating

    p1_error = errors(p1)
    p2_error = errors(p2)
    assert p2_error[0] < p1_error[0]
    assert p2_error[1] < p1_error[1]
    assert p2_input.limited_group_count > 0


def test_multigroup_rejects_negative_group_intensity():
    grid = threshold_log_frequency_groups(0.1, 5000.0, 8)
    state = lte_hydrogen_helium_ionization(DENSITY_G_CM3, TEMPERATURE_K)
    mean = np.ones((grid.centre_hz.size, 1))
    mean[3, 0] = -1.0
    with pytest.raises(PhysicalDomainError, match="non-negative"):
        ground_state_milne_multigroup(
            DENSITY_G_CM3,
            TEMPERATURE_K,
            grid.edge_hz,
            mean,
            state.hydrogen_neutral_fraction,
            state.hydrogen_ionized_fraction,
            state.helium_neutral_fraction,
            state.helium_singly_ionized_fraction,
            state.helium_doubly_ionized_fraction,
        )


def test_multigroup_continuum_uses_no_forbidden_numerical_repairs():
    path = Path("src/eccentric_tde_observer/multigroup_continuum.py")
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
