from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

from eccentric_tde_observer.atomic_continuum import (
    EV_ERG,
    H_HE_GROUND_STATE_PHOTOIONIZATION_FITS,
    ground_state_saha_factor_cm3,
)
from eccentric_tde_observer.continuum_emission import (
    IONIZATION_ENERGIES_EV,
    ground_state_milne_radiative_rates,
)
from eccentric_tde_observer.frequency_quadrature import (
    integrate_frequency,
    threshold_excess_frequency_group_edges_ev,
    threshold_excess_gauss_legendre_quadrature,
    threshold_log_gauss_legendre_quadrature,
    trapezoid_frequency_weights_hz,
)
from eccentric_tde_observer.radiation import (
    BOLTZMANN_ERG_K,
    planck_nu,
)


def _thermal_scale_ev() -> float:
    return BOLTZMANN_ERG_K * 5000.0 / EV_ERG


def test_explicit_trapezoid_weights_match_numpy_for_any_trailing_shape() -> None:
    frequency = np.array([1.0, 1.5, 3.0, 8.0])
    values = np.arange(24, dtype=np.float64).reshape(4, 2, 3)
    weight = trapezoid_frequency_weights_hz(frequency)
    assert np.array_equal(
        integrate_frequency(values, weight, axis=0),
        np.trapezoid(values, frequency, axis=0),
    )


def test_threshold_quadratures_have_positive_sorted_nodes_and_weights() -> None:
    quadratures = (
        threshold_log_gauss_legendre_quadrature(0.1, 5000.0, 2),
        threshold_excess_gauss_legendre_quadrature(
            0.1,
            5000.0,
            2,
            threshold_scale_ev=_thermal_scale_ev(),
        ),
    )
    thresholds = np.array(
        [fit.threshold_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS]
    )
    for quadrature in quadratures:
        assert np.all(np.diff(quadrature.photon_energy_ev) > 0.0)
        assert np.all(quadrature.energy_weight_ev > 0.0)
        assert not np.any(
            quadrature.photon_energy_ev[:, None] == thresholds[None, :]
        )


def test_threshold_excess_group_edges_preserve_bounds_and_ionization_edges() -> None:
    edge = threshold_excess_frequency_group_edges_ev(
        0.1,
        5000.0,
        64,
        threshold_scale_ev=_thermal_scale_ev(),
    )
    thresholds = np.array(
        [fit.threshold_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS]
    )
    assert edge[0] == 0.1
    assert edge[-1] == 5000.0
    assert np.all(np.diff(edge) > 0.0)
    assert np.all(np.isin(thresholds, edge))
    assert edge.size - 1 == 568


def test_threshold_segments_integrate_constant_and_discontinuous_steps() -> None:
    quadrature = threshold_excess_gauss_legendre_quadrature(
        0.1,
        5000.0,
        2,
        threshold_scale_ev=_thermal_scale_ev(),
    )
    assert np.isclose(
        np.sum(quadrature.energy_weight_ev),
        5000.0 - 0.1,
        rtol=3.0e-15,
        atol=0.0,
    )
    for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS:
        active = quadrature.photon_energy_ev > fit.threshold_energy_ev
        assert np.isclose(
            np.sum(quadrature.energy_weight_ev[active]),
            5000.0 - fit.threshold_energy_ev,
            rtol=3.0e-15,
            atol=0.0,
        )


def test_threshold_excess_coordinate_resolves_milne_boundary_layer() -> None:
    scale = _thermal_scale_ev()
    quadrature = threshold_excess_gauss_legendre_quadrature(
        0.1,
        5000.0,
        2,
        threshold_scale_ev=scale,
    )
    for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS:
        excess = quadrature.photon_energy_ev - fit.threshold_energy_ev
        active = excess > 0.0
        numerical = np.sum(
            quadrature.energy_weight_ev[active] * np.exp(-excess[active] / scale)
        )
        expected = scale * (
            1.0 - np.exp(-(5000.0 - fit.threshold_energy_ev) / scale)
        )
        assert np.isclose(numerical, expected, rtol=2.0e-12, atol=0.0)


def test_weighted_milne_rates_recover_lte_detailed_balance() -> None:
    quadrature = threshold_excess_gauss_legendre_quadrature(
        0.1,
        5000.0,
        2,
        threshold_scale_ev=_thermal_scale_ev(),
    )
    temperature = np.array([5000.0, 2.0e4, 2.0e5])
    mean = planck_nu(
        quadrature.frequency_hz[:, None], temperature[None, :]
    )
    rates = ground_state_milne_radiative_rates(
        temperature,
        quadrature.frequency_hz,
        mean,
        frequency_weight_hz=quadrature.frequency_weight_hz,
    )
    saha = np.stack(
        [
            ground_state_saha_factor_cm3(temperature, energy)
            for energy in IONIZATION_ENERGIES_EV
        ],
        axis=1,
    )
    assert np.allclose(
        rates.photoionization_s1 / saha,
        rates.total_recombination_cm3_s,
        rtol=2.0e-13,
        atol=0.0,
    )


def test_default_milne_rate_path_equals_explicit_trapezoid_weights() -> None:
    frequency = np.geomspace(1.0e14, 2.0e17, 41)
    temperature = np.array([2.0e4, 5.0e4])
    mean = planck_nu(frequency[:, None], temperature[None, :])
    default = ground_state_milne_radiative_rates(temperature, frequency, mean)
    explicit = ground_state_milne_radiative_rates(
        temperature,
        frequency,
        mean,
        frequency_weight_hz=trapezoid_frequency_weights_hz(frequency),
    )
    assert np.array_equal(default.photoionization_s1, explicit.photoionization_s1)
    assert np.array_equal(
        default.total_recombination_cm3_s,
        explicit.total_recombination_cm3_s,
    )


def test_frequency_quadrature_calls_no_forbidden_numerical_repairs() -> None:
    path = Path("src/eccentric_tde_observer/frequency_quadrature.py")
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
