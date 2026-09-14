from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.atomic_continuum import EV_ERG, ground_state_saha_factor_cm3
from eccentric_tde_observer.continuum_emission import (
    IONIZATION_ENERGIES_EV,
    ContinuumPopulationInversionError,
    EmissiveSlabConvergenceError,
    edge_resolved_milne_energy_grid_ev,
    ground_state_milne_continuum,
    ground_state_milne_radiative_rates,
    solve_emissive_ground_state_slab,
)
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.atmosphere import (
    PROTON_MASS_G,
    SOLAR_FULLY_IONIZED_H_HE,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S, planck_nu
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_half_range_mu_weights,
)
from eccentric_tde_observer.source import PhysicalDomainError


TEMPERATURE_K = 4.0e4
DENSITY_G_CM3 = 1.0e-10


def _grid(base_points: int = 129):
    energy = edge_resolved_milne_energy_grid_ev(0.1, 5000.0, base_points)
    return energy, energy * EV_ERG / PLANCK_ERG_S


def test_milne_grid_resolves_both_sides_of_each_cross_section_edge() -> None:
    energy, _ = _grid(65)
    for threshold in (13.60, 24.59, 54.42):
        index = int(np.flatnonzero(energy == threshold)[0])
        assert energy[index - 1] < threshold
        assert (
            energy[index - 1] * EV_ERG / PLANCK_ERG_S
            < threshold * EV_ERG / PLANCK_ERG_S
        )
    assert np.all(np.diff(energy) > 0.0)
    assert not energy.flags.writeable


def _lte_fractions():
    state = lte_hydrogen_helium_ionization(DENSITY_G_CM3, TEMPERATURE_K)
    electron = float(state.electron_density_cm3)
    saha = np.array(
        [ground_state_saha_factor_cm3(TEMPERATURE_K, energy) for energy in IONIZATION_ENERGIES_EV]
    )
    hydrogen_denominator = electron + saha[0]
    hydrogen = [electron / hydrogen_denominator, saha[0] / hydrogen_denominator]
    helium_ratio_1 = saha[1] / electron
    helium_ratio_2 = saha[2] / electron
    helium_denominator = 1.0 + helium_ratio_1 + helium_ratio_1 * helium_ratio_2
    helium = [
        1.0 / helium_denominator,
        helium_ratio_1 / helium_denominator,
        helium_ratio_1 * helium_ratio_2 / helium_denominator,
    ]
    return state, hydrogen, helium


def _isotropic_boundaries(intensity: np.ndarray, mu: np.ndarray):
    top = np.zeros((intensity.size, mu.size))
    bottom = np.zeros_like(top)
    top[:, mu > 0.0] = intensity[:, None]
    bottom[:, mu < 0.0] = intensity[:, None]
    return top, bottom


def test_lte_milne_continuum_recovers_kirchhoff_source() -> None:
    _, frequency = _grid(257)
    _, hydrogen, helium = _lte_fractions()
    continuum = ground_state_milne_continuum(
        DENSITY_G_CM3,
        TEMPERATURE_K,
        frequency,
        hydrogen[0],
        hydrogen[1],
        helium[0],
        helium[1],
        helium[2],
    )
    planck = planck_nu(frequency, TEMPERATURE_K)
    source_error = np.max(
        np.abs(continuum.thermal_source_intensity[:, 0] - planck)
    ) / np.max(planck)
    assert source_error < 2.0e-15
    assert np.allclose(
        continuum.free_free_emissivity_cgs,
        continuum.free_free_absorption_per_cm * planck[:, None],
        rtol=0.0,
        atol=0.0,
    )
    assert not continuum.thermal_emissivity_total_cgs.flags.writeable


def test_depth_resolved_density_is_preserved_in_continuum_coefficients() -> None:
    _, frequency = _grid(65)
    density = np.array([0.5, 1.0, 2.0]) * DENSITY_G_CM3
    state = lte_hydrogen_helium_ionization(density, TEMPERATURE_K)
    continuum = ground_state_milne_continuum(
        density,
        TEMPERATURE_K,
        frequency,
        state.hydrogen_neutral_fraction,
        state.hydrogen_ionized_fraction,
        state.helium_neutral_fraction,
        state.helium_singly_ionized_fraction,
        state.helium_doubly_ionized_fraction,
    )
    hydrogen_nuclei = (
        SOLAR_FULLY_IONIZED_H_HE.hydrogen_mass_fraction
        * density
        / PROTON_MASS_G
    )
    helium_nuclei = (
        SOLAR_FULLY_IONIZED_H_HE.helium_mass_fraction
        * density
        / (4.0 * PROTON_MASS_G)
    )
    expected_electron = (
        hydrogen_nuclei * state.hydrogen_ionized_fraction
        + helium_nuclei
        * (
            state.helium_singly_ionized_fraction
            + 2.0 * state.helium_doubly_ionized_fraction
        )
    )
    assert np.allclose(
        continuum.electron_density_cm3,
        expected_electron,
        rtol=2.0e-16,
    )
    assert np.allclose(
        continuum.electron_scattering_per_cm[:, 2]
        / continuum.electron_scattering_per_cm[:, 0],
        expected_electron[2] / expected_electron[0],
        rtol=2.0e-14,
    )


def test_planck_milne_rates_obey_detailed_balance() -> None:
    _, frequency = _grid(513)
    planck = planck_nu(frequency, TEMPERATURE_K)
    rates = ground_state_milne_radiative_rates(
        TEMPERATURE_K, frequency, planck[:, None]
    )
    saha = np.array(
        [ground_state_saha_factor_cm3(TEMPERATURE_K, energy) for energy in IONIZATION_ENERGIES_EV]
    )
    expected = rates.photoionization_s1[0] / saha
    assert np.allclose(
        rates.total_recombination_cm3_s[0], expected, rtol=5.0e-15, atol=0.0
    )
    assert np.allclose(
        rates.total_recombination_cm3_s,
        rates.spontaneous_recombination_cm3_s[None, :]
        + rates.stimulated_recombination_cm3_s,
        rtol=0.0,
        atol=0.0,
    )


def test_population_inversion_is_rejected_instead_of_clipped() -> None:
    _, frequency = _grid(65)
    with pytest.raises(ContinuumPopulationInversionError, match="negative"):
        ground_state_milne_continuum(
            DENSITY_G_CM3,
            TEMPERATURE_K,
            frequency,
            0.0,
            1.0,
            0.0,
            0.0,
            1.0,
        )


def test_planck_slab_is_an_lte_radiative_and_energy_fixed_point() -> None:
    _, frequency = _grid(129)
    mu, weight = gauss_legendre_half_range_mu_weights(4)
    planck = planck_nu(frequency, TEMPERATURE_K)
    top, bottom = _isotropic_boundaries(planck, mu)
    lte, hydrogen, helium = _lte_fractions()
    result = solve_emissive_ground_state_slab(
        frequency,
        np.linspace(0.0, 1.0e6, 5),
        mu,
        weight,
        DENSITY_G_CM3,
        TEMPERATURE_K,
        top,
        bottom,
        hydrogen,
        helium,
        relaxation=1.0,
        tolerance=1.0e-12,
    )
    assert result.iteration_count == 1
    assert np.max(np.abs(result.transfer.mean_intensity - planck[:, None])) / np.max(planck) < 2.0e-15
    assert np.max(np.abs(result.radiative_heating_erg_s_cm3)) / (
        4.0
        * np.pi
        * np.max(
            np.trapezoid(
                result.continuum.true_absorption_total_per_cm * planck[:, None],
                frequency,
                axis=0,
            )
        )
    ) < 2.0e-15
    assert result.relative_boundary_energy_balance_residual < 2.0e-19
    assert result.maximum_relative_photon_rate_identity_residual < 2.0e-15
    assert np.allclose(
        result.population.hydrogen_ionized_fraction,
        lte.hydrogen_ionized_fraction,
        rtol=0.0,
        atol=3.0e-15,
    )


def test_illuminated_emissive_slab_is_initial_state_independent() -> None:
    _, frequency = _grid(65)
    mu, weight = gauss_legendre_half_range_mu_weights(4)
    top = np.zeros((frequency.size, mu.size))
    top[:, mu > 0.0] = 1.0e-6 * planck_nu(frequency, 1.5e5)[:, None]
    bottom = np.zeros_like(top)
    _, lte_hydrogen, lte_helium = _lte_fractions()
    common = (
        frequency,
        np.linspace(0.0, 1.0e6, 5),
        mu,
        weight,
        DENSITY_G_CM3,
        TEMPERATURE_K,
        top,
        bottom,
    )
    neutral = solve_emissive_ground_state_slab(
        *common,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        relaxation=1.0,
        tolerance=1.0e-9,
    )
    lte = solve_emissive_ground_state_slab(
        *common,
        lte_hydrogen,
        lte_helium,
        relaxation=1.0,
        tolerance=1.0e-9,
    )
    for name in (
        "hydrogen_neutral_fraction",
        "hydrogen_ionized_fraction",
        "helium_neutral_fraction",
        "helium_singly_ionized_fraction",
        "helium_doubly_ionized_fraction",
    ):
        assert np.allclose(
            getattr(neutral.population, name),
            getattr(lte.population, name),
            rtol=0.0,
            atol=2.0e-9,
        )
    assert neutral.relative_boundary_energy_balance_residual < 2.0e-14
    assert neutral.maximum_relative_photon_rate_identity_residual < 2.0e-14
    assert np.array_equal(
        neutral.required_thermostat_heating_erg_s_cm3,
        -neutral.radiative_heating_erg_s_cm3,
    )


def test_collisional_milne_slab_escapes_the_vacuum_dark_solution() -> None:
    _, frequency = _grid(33)
    mu, weight = gauss_legendre_half_range_mu_weights(2)
    vacuum = np.zeros((frequency.size, mu.size))
    result = solve_emissive_ground_state_slab(
        frequency,
        np.linspace(0.0, 1.0e8, 5),
        mu,
        weight,
        DENSITY_G_CM3,
        8.0e4,
        vacuum,
        vacuum,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        include_collisional_kinetics=True,
        initialize_collisional_population_from_lte=True,
        relaxation=1.0,
        tolerance=3.0e-8,
        maximum_iterations=1024,
    )
    assert result.includes_collisional_kinetics
    assert np.all(result.population.electron_density_cm3 > 0.0)
    assert np.max(result.transfer.top_boundary_intensity) > 0.0
    assert np.trapezoid(result.transfer.top_net_flux, frequency) < 0.0


def test_lte_collisional_initialization_requires_the_collision_network() -> None:
    _, frequency = _grid(33)
    mu, weight = gauss_legendre_half_range_mu_weights(2)
    vacuum = np.zeros((frequency.size, mu.size))
    with pytest.raises(PhysicalDomainError, match="requires collisional"):
        solve_emissive_ground_state_slab(
            frequency,
            np.linspace(0.0, 1.0e6, 3),
            mu,
            weight,
            DENSITY_G_CM3,
            8.0e4,
            vacuum,
            vacuum,
            [1.0, 0.0],
            [1.0, 0.0, 0.0],
            initialize_collisional_population_from_lte=True,
        )


def test_unconverged_emissive_slab_is_reported() -> None:
    _, frequency = _grid(65)
    mu, weight = gauss_legendre_half_range_mu_weights(4)
    top = np.zeros((frequency.size, mu.size))
    top[:, mu > 0.0] = 1.0e-6 * planck_nu(frequency, 1.5e5)[:, None]
    with pytest.raises(EmissiveSlabConvergenceError, match="did not reach"):
        solve_emissive_ground_state_slab(
            frequency,
            np.linspace(0.0, 1.0e6, 5),
            mu,
            weight,
            DENSITY_G_CM3,
            TEMPERATURE_K,
            top,
            np.zeros_like(top),
            [1.0, 0.0],
            [1.0, 0.0, 0.0],
            maximum_iterations=1,
            tolerance=1.0e-14,
        )


def test_continuum_emission_uses_no_forbidden_repairs_or_total_rr_mix() -> None:
    source = Path("src/eccentric_tde_observer/continuum_emission.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "nan_to_num",
        "np.clip",
        "numpy.clip",
        "H_I_RECOMBINATION_FIT",
        "HE_I_RECOMBINATION_FIT",
        "HE_II_RECOMBINATION_FIT",
    )
    assert all(token not in source for token in forbidden)
