from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.atomic_continuum import (
    EV_ERG,
    HE_I_RECOMBINATION_FIT,
    HE_I_VERNER_FIT,
    HE_II_RECOMBINATION_FIT,
    HE_II_VERNER_FIT,
    H_I_RECOMBINATION_FIT,
    H_I_VERNER_FIT,
    detailed_balance_recombination_coefficient_cm3_s,
    ground_state_saha_factor_cm3,
    integrate_photoionization_rate_s1,
    photoionization_rate_from_fit_s1,
    photoionization_recombination_equilibrium,
    traceable_lte_h_he_continuum_opacity_cm2_g,
)
from eccentric_tde_observer.atmosphere import PROTON_MASS_G, SOLAR_FULLY_IONIZED_H_HE
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.radiation import PLANCK_ERG_S, planck_nu
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
    isothermal_absorption_top_flux,
    solve_static_slab_transfer,
)
from eccentric_tde_observer.source import PhysicalDomainError


def test_verner_h_he_cross_sections_match_fixed_formula_values() -> None:
    cases = (
        (H_I_VERNER_FIT, 13.60, 6.346296358990504e-18),
        (HE_I_VERNER_FIT, 24.59, 7.434698687722296e-18),
        (HE_II_VERNER_FIT, 54.42, 1.587280263027646e-18),
    )
    for fit, energy, expected in cases:
        assert fit.cross_section_cm2(0.999 * energy) == 0.0
        assert fit.cross_section_cm2(energy) == pytest.approx(expected, rel=2.0e-14)


def test_verner_fit_rejects_extrapolation_beyond_published_limit() -> None:
    with pytest.raises(PhysicalDomainError):
        H_I_VERNER_FIT.cross_section_cm2(5.0001e4)


def test_verner_ferland_recombination_values_and_hei_validity() -> None:
    assert H_I_RECOMBINATION_FIT.coefficient_cm3_s(1.0e4) == pytest.approx(
        4.192322735308633e-13, rel=2.0e-14
    )
    assert HE_I_RECOMBINATION_FIT.coefficient_cm3_s(1.0e4) == pytest.approx(
        4.595426947329959e-13, rel=2.0e-14
    )
    assert HE_II_RECOMBINATION_FIT.coefficient_cm3_s(1.0e4) == pytest.approx(
        2.1879891060937634e-12, rel=2.0e-14
    )
    with pytest.raises(PhysicalDomainError):
        HE_I_RECOMBINATION_FIT.coefficient_cm3_s(1.01e6)


def test_photoionization_integral_recovers_power_law_analytic_limit() -> None:
    threshold = 3.0e15
    sigma_0 = 2.0e-18
    intensity_0 = 7.0e-6
    spectral_index = 1.25
    frequency = np.geomspace(threshold, 1.0e5 * threshold, 131073)
    cross_section = sigma_0 * (threshold / frequency) ** 3
    intensity = intensity_0 * (threshold / frequency) ** spectral_index
    numerical = integrate_photoionization_rate_s1(frequency, intensity, cross_section)
    analytic = (
        4.0
        * np.pi
        * sigma_0
        * intensity_0
        / (PLANCK_ERG_S * (3.0 + spectral_index))
    )
    assert numerical == pytest.approx(analytic, rel=3.0e-8)


def test_verner_rate_integral_splits_at_the_ionization_edge() -> None:
    threshold = H_I_VERNER_FIT.threshold_energy_ev * EV_ERG / PLANCK_ERG_S

    def rate(points: int) -> float:
        frequency = np.unique(
            np.concatenate(
                (
                    np.geomspace(0.5 * threshold, 100.0 * threshold, points),
                    [threshold],
                )
            )
        )
        intensity = planck_nu(frequency, 6.0e4)
        return photoionization_rate_from_fit_s1(
            frequency, intensity, H_I_VERNER_FIT
        )

    reference = rate(8193)
    assert rate(1025) == pytest.approx(reference, rel=2.0e-4)


def test_detailed_balance_control_recovers_h_he_saha_solution() -> None:
    density = 1.0e-10
    temperature = 1.5e4
    composition = SOLAR_FULLY_IONIZED_H_HE
    hydrogen = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium = composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    gamma_h, gamma_he1, gamma_he2 = 0.7, 1.1, 0.9
    saha_h = ground_state_saha_factor_cm3(temperature, 13.59843449)
    saha_he1 = ground_state_saha_factor_cm3(temperature, 24.587389)
    saha_he2 = ground_state_saha_factor_cm3(temperature, 54.417765)
    state = photoionization_recombination_equilibrium(
        hydrogen,
        helium,
        gamma_h,
        gamma_he1,
        gamma_he2,
        detailed_balance_recombination_coefficient_cm3_s(gamma_h, saha_h),
        detailed_balance_recombination_coefficient_cm3_s(gamma_he1, saha_he1),
        detailed_balance_recombination_coefficient_cm3_s(gamma_he2, saha_he2),
    )
    saha = lte_hydrogen_helium_ionization(density, temperature, composition)
    assert state.electron_density_cm3 == pytest.approx(
        saha.electron_density_cm3, rel=3.0e-14
    )
    assert state.hydrogen_ionized_fraction == pytest.approx(
        saha.hydrogen_ionized_fraction, rel=3.0e-14
    )
    assert state.helium_singly_ionized_fraction == pytest.approx(
        saha.helium_singly_ionized_fraction, rel=3.0e-14, abs=1.0e-18
    )


def test_photoionization_equilibrium_conserves_particles_and_charge() -> None:
    hydrogen = np.array([1.0e10, 2.0e12])
    helium = np.array([1.0e9, 2.0e11])
    state = photoionization_recombination_equilibrium(
        hydrogen,
        helium,
        [1.0e-3, 2.0],
        [4.0e-4, 1.0],
        [2.0e-4, 0.5],
        H_I_RECOMBINATION_FIT.coefficient_cm3_s([1.0e4, 5.0e4]),
        HE_I_RECOMBINATION_FIT.coefficient_cm3_s([1.0e4, 5.0e4]),
        HE_II_RECOMBINATION_FIT.coefficient_cm3_s([1.0e4, 5.0e4]),
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
    charge = hydrogen * state.hydrogen_ionized_fraction + helium * (
        state.helium_singly_ionized_fraction
        + 2.0 * state.helium_doubly_ionized_fraction
    )
    assert np.allclose(state.electron_density_cm3, charge, rtol=3.0e-15)


def test_traceable_opacity_contains_explicit_hei_edge() -> None:
    energy = np.array([0.9999, 1.0001, 1.001]) * HE_I_VERNER_FIT.threshold_energy_ev
    frequency = energy * EV_ERG / PLANCK_ERG_S
    opacity = traceable_lte_h_he_continuum_opacity_cm2_g(
        1.0e-9, 1.0e4, frequency
    )
    assert opacity.helium_i_bound_free_cm2_g[0] == 0.0
    assert opacity.helium_i_bound_free_cm2_g[1] > 0.0
    assert np.all(opacity.absorption_total_cm2_g >= opacity.free_free_cm2_g)


def test_traceable_opacity_couples_to_static_absorption_transfer() -> None:
    temperature = 1.2e4
    density = 1.0e-10
    energy = np.array([10.0, 14.0, 25.0, 60.0])
    frequency = energy * EV_ERG / PLANCK_ERG_S
    opacity = traceable_lte_h_he_continuum_opacity_cm2_g(
        density, temperature, frequency
    )
    thickness = 2.0e8
    extinction = density * opacity.absorption_total_cm2_g
    source = planck_nu(frequency, temperature)
    mu, weight = gauss_legendre_mu_weights(64)
    result = solve_static_slab_transfer(
        frequency,
        np.linspace(0.0, thickness, 17),
        mu,
        weight,
        extinction[:, None],
        source[:, None],
        1.0,
    )
    numerical = -result.top_net_flux
    analytic = np.array(
        [
            isothermal_absorption_top_flux(source[index], extinction[index] * thickness)
            for index in range(frequency.size)
        ]
    )
    assert np.allclose(numerical, analytic, rtol=3.0e-4)
    assert np.max(result.relative_energy_balance_residual) < 1.0e-12


@pytest.mark.parametrize(
    "bad_energy",
    [0.0, -1.0, np.nan],
)
def test_invalid_atomic_inputs_are_rejected(bad_energy: float) -> None:
    with pytest.raises(PhysicalDomainError):
        H_I_VERNER_FIT.cross_section_cm2(bad_energy)


def test_atomic_continuum_source_avoids_forbidden_masking_helpers() -> None:
    from eccentric_tde_observer import atomic_continuum

    source_text = open(atomic_continuum.__file__, encoding="utf-8").read()
    assert "nan_to_num" not in source_text
    assert "np.clip" not in source_text
