from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.atomic_continuum import (
    EV_ERG,
    HE_I_RECOMBINATION_FIT,
    HE_II_RECOMBINATION_FIT,
    H_I_RECOMBINATION_FIT,
    ground_state_saha_factor_cm3,
)
from eccentric_tde_observer.atomic_kinetics import (
    H_HE_COLLISIONAL_IONIZATION_FITS,
)
from eccentric_tde_observer.atmosphere import (
    PROTON_MASS_G,
    SOLAR_FULLY_IONIZED_H_HE,
    THOMSON_CROSS_SECTION_CM2,
)
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.prescribed_radiation import (
    edge_resolved_photoionization_energy_grid_ev,
    prescribed_planck_photoionization_rates_s1,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S, planck_nu
from eccentric_tde_observer.radiation_population_coupling import (
    CoupledSlabConvergenceError,
    ground_state_h_he_slab_opacity_per_cm,
    photoionization_rates_from_mean_intensity_s1,
    solve_coupled_radiation_population_slab,
)
from eccentric_tde_observer.radiative_transfer_1d import gauss_legendre_mu_weights
from eccentric_tde_observer.source import PhysicalDomainError


IONIZATION_ENERGIES_EV = (13.59843449, 24.587389, 54.417765)


def _grid(base_points: int = 129):
    energy = edge_resolved_photoionization_energy_grid_ev(1.0, 5000.0, base_points)
    return energy, energy * EV_ERG / PLANCK_ERG_S


def _atomic_rates(temperature_k: float):
    collision = np.array(
        [fit.coefficient_cm3_s(temperature_k) for fit in H_HE_COLLISIONAL_IONIZATION_FITS]
    )
    radiative = np.array(
        [
            H_I_RECOMBINATION_FIT.coefficient_cm3_s(temperature_k),
            HE_I_RECOMBINATION_FIT.coefficient_cm3_s(temperature_k),
            HE_II_RECOMBINATION_FIT.coefficient_cm3_s(temperature_k),
        ]
    )
    saha = np.array(
        [ground_state_saha_factor_cm3(temperature_k, value) for value in IONIZATION_ENERGIES_EV]
    )
    return collision, radiative, collision / saha, saha


def _isotropic_boundaries(intensity: np.ndarray, mu: np.ndarray):
    top = np.zeros((intensity.size, mu.size))
    bottom = np.zeros_like(top)
    top[:, mu > 0.0] = intensity[:, None]
    bottom[:, mu < 0.0] = intensity[:, None]
    return top, bottom


def test_explicit_population_opacity_uses_target_densities_and_charge() -> None:
    energy, frequency = _grid(65)
    density = 2.0e-10
    opacity = ground_state_h_he_slab_opacity_per_cm(
        density,
        frequency,
        [0.25, 0.75],
        [0.75, 0.25],
        [0.5, 0.1],
        [0.3, 0.4],
        [0.2, 0.5],
    )
    composition = SOLAR_FULLY_IONIZED_H_HE
    hydrogen = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium = composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    electron = hydrogen * np.array([0.75, 0.25]) + helium * (
        np.array([0.3, 0.4]) + 2.0 * np.array([0.2, 0.5])
    )
    assert np.allclose(
        opacity.electron_scattering_per_cm,
        THOMSON_CROSS_SECTION_CM2 * electron[None, :],
        rtol=2.0e-16,
    )
    assert np.allclose(
        opacity.extinction_total_per_cm,
        opacity.photoabsorption_total_per_cm + opacity.electron_scattering_per_cm,
        rtol=2.0e-16,
    )
    assert np.all(opacity.hydrogen_i_photoabsorption_per_cm[energy < 13.60] == 0.0)
    assert not opacity.extinction_total_per_cm.flags.writeable


def test_zero_opacity_scale_is_exact_vacuum_without_fraction_repair() -> None:
    _, frequency = _grid(65)
    opacity = ground_state_h_he_slab_opacity_per_cm(
        1.0e-10,
        frequency,
        0.7,
        0.3,
        0.2,
        0.3,
        0.5,
        opacity_scale=0.0,
    )
    assert np.array_equal(opacity.extinction_total_per_cm, np.zeros_like(opacity.extinction_total_per_cm))
    assert np.array_equal(opacity.absorption_probability, np.ones_like(opacity.absorption_probability))
    with pytest.raises(PhysicalDomainError, match="hydrogen fractions"):
        ground_state_h_he_slab_opacity_per_cm(
            1.0e-10, frequency, 0.7, 0.4, 0.2, 0.3, 0.5
        )


def test_depth_photoionization_integral_matches_prescribed_planck_field() -> None:
    energy, frequency = _grid(257)
    temperature = 9.0e4
    dilution = 3.0e-4
    mean = dilution * planck_nu(frequency, temperature)[:, None] * np.ones((1, 3))
    actual = photoionization_rates_from_mean_intensity_s1(frequency, mean)
    expected = prescribed_planck_photoionization_rates_s1(
        [temperature], [dilution], energy
    ).photoionization_s1[0]
    assert np.allclose(actual, expected[None, :], rtol=3.0e-15, atol=0.0)


def test_transparent_coupled_slab_recovers_the_prescribed_field_solution() -> None:
    temperature = 4.0e4
    energy, frequency = _grid(129)
    mu, weight = gauss_legendre_mu_weights(4)
    incident = 2.0e-5 * planck_nu(frequency, 1.2e5)
    top, bottom = _isotropic_boundaries(incident, mu)
    collision, radiative, three_body, _ = _atomic_rates(temperature)
    result = solve_coupled_radiation_population_slab(
        frequency,
        np.linspace(0.0, 1.0e7, 5),
        mu,
        weight,
        1.0e-10,
        0.0,
        top,
        bottom,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        collision,
        radiative,
        three_body,
        opacity_scale=0.0,
        tolerance=1.0e-12,
    )
    expected = prescribed_planck_photoionization_rates_s1(
        [1.2e5], [2.0e-5], energy
    ).photoionization_s1[0]
    assert np.allclose(result.transfer.mean_intensity, incident[:, None], rtol=4.0e-16)
    assert np.allclose(result.photoionization_rate_s1, expected[None, :], rtol=3.0e-15)
    assert result.maximum_population_fixed_point_residual < 2.0e-15


def test_planck_boundaries_and_detailed_balance_are_an_lte_fixed_point() -> None:
    density = 1.0e-10
    temperature = 4.0e4
    energy, frequency = _grid(257)
    mu, weight = gauss_legendre_mu_weights(4)
    planck = planck_nu(frequency, temperature)
    top, bottom = _isotropic_boundaries(planck, mu)
    collision, _, three_body, saha = _atomic_rates(temperature)
    gamma = prescribed_planck_photoionization_rates_s1(
        [temperature], [1.0], energy
    ).photoionization_s1[0]
    radiative_detailed_balance = gamma / saha
    lte = lte_hydrogen_helium_ionization(
        density, temperature, SOLAR_FULLY_IONIZED_H_HE
    )
    result = solve_coupled_radiation_population_slab(
        frequency,
        np.linspace(0.0, 1.0e7, 5),
        mu,
        weight,
        density,
        planck[:, None],
        top,
        bottom,
        [lte.hydrogen_neutral_fraction, lte.hydrogen_ionized_fraction],
        [
            lte.helium_neutral_fraction,
            lte.helium_singly_ionized_fraction,
            lte.helium_doubly_ionized_fraction,
        ],
        collision,
        radiative_detailed_balance,
        three_body,
        tolerance=1.0e-12,
    )
    assert result.iteration_count == 1
    assert np.allclose(result.transfer.mean_intensity, planck[:, None], rtol=2.0e-14, atol=0.0)
    assert np.allclose(
        result.population.hydrogen_ionized_fraction,
        lte.hydrogen_ionized_fraction,
        rtol=0.0,
        atol=3.0e-15,
    )
    assert np.allclose(
        result.population.helium_doubly_ionized_fraction,
        lte.helium_doubly_ionized_fraction,
        rtol=0.0,
        atol=3.0e-15,
    )


def test_illuminated_absorbing_slab_is_independent_of_extreme_initial_states() -> None:
    temperature = 4.0e4
    _, frequency = _grid(129)
    mu, weight = gauss_legendre_mu_weights(4)
    top = np.zeros((frequency.size, mu.size))
    top[:, mu > 0.0] = 1.0e-6 * planck_nu(frequency, 1.5e5)[:, None]
    bottom = np.zeros_like(top)
    collision, radiative, three_body, _ = _atomic_rates(temperature)
    common = (
        frequency,
        np.linspace(0.0, 1.0e7, 9),
        mu,
        weight,
        1.0e-10,
        0.0,
        top,
        bottom,
    )
    neutral = solve_coupled_radiation_population_slab(
        *common,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        collision,
        radiative,
        three_body,
        tolerance=1.0e-9,
    )
    ionized = solve_coupled_radiation_population_slab(
        *common,
        [0.0, 1.0],
        [0.0, 0.0, 1.0],
        collision,
        radiative,
        three_body,
        tolerance=1.0e-9,
    )
    for name in (
        "hydrogen_ionized_fraction",
        "helium_neutral_fraction",
        "helium_singly_ionized_fraction",
        "helium_doubly_ionized_fraction",
    ):
        assert np.allclose(
            getattr(neutral.population, name),
            getattr(ionized.population, name),
            rtol=0.0,
            atol=2.0e-9,
        )
    assert np.max(neutral.transfer.relative_energy_balance_residual) < 2.0e-14


def test_nonconvergence_is_reported_and_source_has_no_forbidden_repairs() -> None:
    temperature = 4.0e4
    _, frequency = _grid(65)
    mu, weight = gauss_legendre_mu_weights(4)
    top = np.zeros((frequency.size, mu.size))
    top[:, mu > 0.0] = 1.0e-6 * planck_nu(frequency, 1.5e5)[:, None]
    collision, radiative, three_body, _ = _atomic_rates(temperature)
    with pytest.raises(CoupledSlabConvergenceError, match="did not reach"):
        solve_coupled_radiation_population_slab(
            frequency,
            np.linspace(0.0, 1.0e7, 5),
            mu,
            weight,
            1.0e-10,
            0.0,
            top,
            np.zeros_like(top),
            [1.0, 0.0],
            [1.0, 0.0, 0.0],
            collision,
            radiative,
            three_body,
            tolerance=1.0e-14,
            maximum_iterations=1,
        )
    source = Path(
        "src/eccentric_tde_observer/radiation_population_coupling.py"
    ).read_text(encoding="utf-8")
    forbidden = ("nan_to_num", "np.clip", "numpy.clip")
    assert all(token not in source for token in forbidden)
