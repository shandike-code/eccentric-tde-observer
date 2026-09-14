from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.fixtures import constant_temperature_circular_annulus
from eccentric_tde_observer.non_gray import (
    HELIUM_II_IONIZATION_ERG,
    HYDROGEN_IONIZATION_ERG,
    lte_hydrogen_helium_ionization,
    lte_non_gray_continuum_opacity_cm2_g,
    lte_non_gray_effective_optical_depth_to_midplane,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.source import PhysicalDomainError


def test_saha_solution_is_charge_neutral_and_fraction_normalized() -> None:
    state = lte_hydrogen_helium_ionization(
        np.array([1.0e-11, 1.0e-9]), np.array([1.0e4, 1.0e5])
    )
    assert np.allclose(
        state.hydrogen_neutral_fraction + state.hydrogen_ionized_fraction,
        1.0,
        rtol=0.0,
        atol=2.0e-15,
    )
    assert np.allclose(
        state.helium_neutral_fraction
        + state.helium_singly_ionized_fraction
        + state.helium_doubly_ionized_fraction,
        1.0,
        rtol=0.0,
        atol=2.0e-15,
    )
    assert state.electron_density_cm3[1] > state.electron_density_cm3[0]


def test_bound_free_edges_are_explicit_and_not_smoothed_or_clipped() -> None:
    hydrogen_edge = HYDROGEN_IONIZATION_ERG / PLANCK_ERG_S
    helium_edge = HELIUM_II_IONIZATION_ERG / PLANCK_ERG_S
    frequency = np.array(
        [0.99 * hydrogen_edge, 1.01 * hydrogen_edge, 0.99 * helium_edge, 1.01 * helium_edge]
    )
    opacity = lte_non_gray_continuum_opacity_cm2_g(
        1.0e-10, 1.2e4, frequency
    )
    assert opacity.hydrogen_i_bound_free_cm2_g[0] == 0.0
    assert opacity.hydrogen_i_bound_free_cm2_g[1] > 0.0
    assert opacity.helium_ii_bound_free_cm2_g[2] == 0.0
    assert opacity.helium_i_bound_free_approx_cm2_g.max() == 0.0


def test_helium_i_approximation_is_opt_in_and_increases_absorption() -> None:
    frequency = 1.1 * 24.587389 * 1.602176634e-12 / PLANCK_ERG_S
    baseline = lte_non_gray_continuum_opacity_cm2_g(1.0e-9, 1.0e4, frequency)
    sensitivity = lte_non_gray_continuum_opacity_cm2_g(
        1.0e-9, 1.0e4, frequency, include_helium_i_approximation=True
    )
    assert sensitivity.helium_i_bound_free_approx_cm2_g > 0.0
    assert sensitivity.absorption_total_cm2_g > baseline.absorption_total_cm2_g


def test_non_gray_optical_depth_is_finite_and_bf_edge_changes_frequency_trend() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 1.2e4, radial_points=3, anomaly_points=8
    )
    edge = HYDROGEN_IONIZATION_ERG / PLANCK_ERG_S
    frequency = np.array([0.8 * edge, 1.01 * edge, 2.0 * edge])
    audit = lte_non_gray_effective_optical_depth_to_midplane(
        source, frequency, vertical_points=65
    )
    assert np.all(np.isfinite(audit.midplane_effective_optical_depth))
    assert np.all(audit.midplane_effective_optical_depth[..., 1] > audit.midplane_effective_optical_depth[..., 0])


@pytest.mark.parametrize(
    ("density", "temperature", "frequency"),
    [(0.0, 1.0e4, 1.0e15), (1.0e-10, -1.0, 1.0e15), (1.0e-10, 1.0e4, np.nan)],
)
def test_invalid_non_gray_inputs_are_rejected(density, temperature, frequency) -> None:
    with pytest.raises(PhysicalDomainError):
        lte_non_gray_continuum_opacity_cm2_g(density, temperature, frequency)


def test_non_gray_source_does_not_use_forbidden_masking_helpers() -> None:
    from eccentric_tde_observer import non_gray

    source_text = open(non_gray.__file__, encoding="utf-8").read()
    assert "nan_to_num" not in source_text
    assert "np.clip" not in source_text
