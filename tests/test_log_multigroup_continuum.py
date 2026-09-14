from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

from eccentric_tde_observer.atomic_continuum import ground_state_saha_factor_cm3
from eccentric_tde_observer.continuum_emission import IONIZATION_ENERGIES_EV
from eccentric_tde_observer.log_frequency_moments import (
    limit_nonnegative_log_frequency_group_p1,
)
from eccentric_tde_observer.log_multigroup_continuum import (
    gauss_legendre_log_frequency_group_quadrature,
    ground_state_milne_log_p1_multigroup,
    log_group_average_from_quadrature_nodes,
    log_group_p1_moment_from_quadrature_nodes,
    log_group_p1_values_at_quadrature_nodes,
)
from eccentric_tde_observer.mixed_frame_frequency import (
    threshold_log_frequency_groups,
)
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.radiation import planck_nu


DENSITY_G_CM3 = 1.0e-9
TEMPERATURE_K = 3.0e4


def test_log_frequency_quadrature_recovers_linear_energy_density():
    edge = np.geomspace(1.0e14, 1.0e18, 19)
    quadrature = gauss_legendre_log_frequency_group_quadrature(
        edge, order_per_group=6
    )
    node = 2.0 + 0.2 * quadrature.node_log_hz
    mean = log_group_average_from_quadrature_nodes(node, quadrature)
    first = log_group_p1_moment_from_quadrature_nodes(node, quadrature)
    reconstructed = log_group_p1_values_at_quadrature_nodes(
        mean, first, quadrature
    )
    np.testing.assert_allclose(reconstructed, node, rtol=2.0e-14)
    physical_width = np.diff(edge)
    integrated_width = np.sum(quadrature.node_weight_hz, axis=1)
    np.testing.assert_allclose(integrated_width, physical_width, rtol=2.0e-13)


def test_log_p1_planck_lte_closes_rates_and_energy_on_coarse_grid():
    grid = threshold_log_frequency_groups(0.1, 5000.0, 32)
    quadrature = gauss_legendre_log_frequency_group_quadrature(
        grid.edge_hz, order_per_group=16
    )
    node_energy = quadrature.node_hz * planck_nu(
        quadrature.node_hz, TEMPERATURE_K
    )
    radiation = limit_nonnegative_log_frequency_group_p1(
        log_group_average_from_quadrature_nodes(node_energy, quadrature)[:, None],
        log_group_p1_moment_from_quadrature_nodes(node_energy, quadrature)[:, None],
    )
    ion = lte_hydrogen_helium_ionization(DENSITY_G_CM3, TEMPERATURE_K)
    result = ground_state_milne_log_p1_multigroup(
        DENSITY_G_CM3,
        TEMPERATURE_K,
        grid.edge_hz,
        radiation.mean_density,
        radiation.first_moment_density,
        ion.hydrogen_neutral_fraction,
        ion.hydrogen_ionized_fraction,
        ion.helium_neutral_fraction,
        ion.helium_singly_ionized_fraction,
        ion.helium_doubly_ionized_fraction,
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
    heating_error = (
        abs(float(result.radiative_heating_erg_s_cm3[0])) / energy_scale
    )
    assert rate_error < 2.0e-4
    assert heating_error < 5.0e-6
    assert radiation.limited_group_count > 0


def test_log_multigroup_uses_no_forbidden_repairs():
    path = Path("src/eccentric_tde_observer/log_multigroup_continuum.py")
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
