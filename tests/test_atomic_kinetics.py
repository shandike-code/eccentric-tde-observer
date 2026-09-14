from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.atomic_continuum import (
    HE_I_RECOMBINATION_FIT,
    HE_II_RECOMBINATION_FIT,
    H_I_RECOMBINATION_FIT,
    ground_state_saha_factor_cm3,
)
from eccentric_tde_observer.atomic_kinetics import (
    H_HE_COLLISIONAL_IONIZATION_FITS,
    HE_I_VORONOV_FIT,
    HE_II_VORONOV_FIT,
    H_I_VORONOV_FIT,
    collisional_photoionization_equilibrium,
    detailed_balance_three_body_recombination_coefficient_cm6_s,
    h_he_rate_generators_s1,
    solve_constant_rate_network,
)
from eccentric_tde_observer.source import PhysicalDomainError


IONIZATION_ENERGIES_EV = (13.59843449, 24.587389, 54.417765)


def _coefficients(temperature_k: float):
    collision = tuple(
        fit.coefficient_cm3_s(temperature_k)
        for fit in H_HE_COLLISIONAL_IONIZATION_FITS
    )
    saha = tuple(
        ground_state_saha_factor_cm3(temperature_k, energy)
        for energy in IONIZATION_ENERGIES_EV
    )
    three_body = tuple(
        detailed_balance_three_body_recombination_coefficient_cm6_s(rate, factor)
        for rate, factor in zip(collision, saha, strict=True)
    )
    return collision, saha, three_body


def test_voronov_h_he_parameters_and_reference_values() -> None:
    assert H_I_VORONOV_FIT.ionization_energy_ev == 13.6
    assert H_I_VORONOV_FIT.coefficient_a_cm3_s == 2.91e-8
    assert HE_I_VORONOV_FIT.ionization_energy_ev == 24.6
    assert HE_I_VORONOV_FIT.coefficient_a_cm3_s == 1.75e-8
    assert HE_II_VORONOV_FIT.ionization_energy_ev == 54.4
    assert HE_II_VORONOV_FIT.parameter_p == 1.0
    actual = np.array(
        [fit.coefficient_cm3_s(1.0e5) for fit in H_HE_COLLISIONAL_IONIZATION_FITS]
    )
    expected = np.array(
        [3.963174948583245e-9, 4.792818365785041e-10, 3.145757338505608e-12]
    )
    assert np.allclose(actual, expected, rtol=2.0e-15, atol=0.0)


@pytest.mark.parametrize("fit", H_HE_COLLISIONAL_IONIZATION_FITS)
def test_voronov_fit_rejects_temperature_extrapolation(fit) -> None:
    with pytest.raises(PhysicalDomainError, match="valid only"):
        fit.coefficient_cm3_s(0.999 * fit.minimum_temperature_k)
    with pytest.raises(PhysicalDomainError, match="valid only"):
        fit.coefficient_cm3_s(1.001 * fit.maximum_temperature_k)


def test_three_body_inverse_rate_obeys_detailed_balance() -> None:
    collision, saha, three_body = _coefficients(1.0e5)
    for rate, factor, inverse in zip(collision, saha, three_body, strict=True):
        assert np.isclose(rate / inverse, factor, rtol=2.0e-16, atol=0.0)


def test_collision_three_body_only_equilibrium_recovers_saha_ratios() -> None:
    temperature_k = 1.0e5
    hydrogen = 8.0e17
    helium = 7.0e16
    collision, saha, three_body = _coefficients(temperature_k)
    state = collisional_photoionization_equilibrium(
        hydrogen,
        helium,
        0.0,
        0.0,
        0.0,
        *collision,
        0.0,
        0.0,
        0.0,
        *three_body,
    )
    electron = float(state.electron_density_cm3)
    ratio_h = float(state.hydrogen_ionized_fraction / state.hydrogen_neutral_fraction)
    ratio_he1 = float(
        state.helium_singly_ionized_fraction / state.helium_neutral_fraction
    )
    ratio_he2 = float(
        state.helium_doubly_ionized_fraction
        / state.helium_singly_ionized_fraction
    )
    actual = np.array([ratio_h, ratio_he1, ratio_he2]) * electron
    assert np.allclose(actual, np.asarray(saha, dtype=float), rtol=2.0e-15, atol=0.0)
    assert state.maximum_relative_charge_residual < 1.0e-15


def test_radiative_recombination_becomes_negligible_in_high_density_lte_limit() -> None:
    temperature_k = 1.0e5
    collision, _, three_body = _coefficients(temperature_k)
    radiative = (
        H_I_RECOMBINATION_FIT.coefficient_cm3_s(temperature_k),
        HE_I_RECOMBINATION_FIT.coefficient_cm3_s(temperature_k),
        HE_II_RECOMBINATION_FIT.coefficient_cm3_s(temperature_k),
    )
    errors = []
    for hydrogen in (1.0e17, 1.0e29):
        helium = 0.1 * hydrogen
        reference = collisional_photoionization_equilibrium(
            hydrogen, helium, 0.0, 0.0, 0.0, *collision, 0.0, 0.0, 0.0, *three_body
        )
        physical = collisional_photoionization_equilibrium(
            hydrogen, helium, 0.0, 0.0, 0.0, *collision, *radiative, *three_body
        )
        reference_fractions = np.array(
            [
                reference.hydrogen_ionized_fraction,
                reference.helium_neutral_fraction,
                reference.helium_singly_ionized_fraction,
                reference.helium_doubly_ionized_fraction,
            ],
            dtype=float,
        )
        physical_fractions = np.array(
            [
                physical.hydrogen_ionized_fraction,
                physical.helium_neutral_fraction,
                physical.helium_singly_ionized_fraction,
                physical.helium_doubly_ionized_fraction,
            ],
            dtype=float,
        )
        errors.append(float(np.max(np.abs(physical_fractions - reference_fractions))))
    assert errors[1] < 1.0e-8 * errors[0]


def test_self_consistent_equilibrium_conserves_particles_and_charge() -> None:
    collision, _, three_body = _coefficients(8.0e4)
    state = collisional_photoionization_equilibrium(
        np.logspace(8.0, 18.0, 31),
        np.logspace(7.0, 17.0, 31),
        2.0e-3,
        7.0e-4,
        1.0e-4,
        *collision,
        2.0e-13,
        4.0e-13,
        1.5e-12,
        *three_body,
    )
    assert np.allclose(
        state.hydrogen_neutral_fraction + state.hydrogen_ionized_fraction,
        1.0,
        rtol=0.0,
        atol=3.0e-16,
    )
    assert np.allclose(
        state.helium_neutral_fraction
        + state.helium_singly_ionized_fraction
        + state.helium_doubly_ionized_fraction,
        1.0,
        rtol=0.0,
        atol=3.0e-16,
    )
    assert state.maximum_relative_charge_residual < 5.0e-16


def test_bisection_charge_residual_converges() -> None:
    collision, _, three_body = _coefficients(1.0e5)
    residuals = []
    for iterations in (16, 32, 48, 64):
        state = collisional_photoionization_equilibrium(
            1.0e15,
            1.0e14,
            1.0e-3,
            3.0e-4,
            8.0e-5,
            *collision,
            1.0e-13,
            2.0e-13,
            8.0e-13,
            *three_body,
            bisection_iterations=iterations,
        )
        residuals.append(state.maximum_relative_charge_residual)
    assert residuals[1] < residuals[0]
    assert residuals[2] < residuals[1]
    assert residuals[-1] < 1.0e-15


def test_h_he_rate_generators_are_conservative() -> None:
    collision, _, three_body = _coefficients(1.0e5)
    generators = h_he_rate_generators_s1(
        np.array([1.0e8, 1.0e12]),
        2.0e-3,
        7.0e-4,
        1.0e-4,
        *collision,
        1.0e-13,
        2.0e-13,
        8.0e-13,
        *three_body,
    )
    assert generators.hydrogen_s1.shape == (2, 2, 2)
    assert generators.helium_s1.shape == (2, 3, 3)
    assert np.allclose(np.sum(generators.hydrogen_s1, axis=-2), 0.0, atol=1.0e-14)
    assert np.allclose(np.sum(generators.helium_s1, axis=-2), 0.0, atol=1.0e-14)


def test_constant_hydrogen_relaxation_matches_analytic_solution() -> None:
    upward = 3.0
    downward = 2.0
    generators = h_he_rate_generators_s1(
        1.0,
        upward,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        downward,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    )
    time = np.linspace(0.0, 4.0, 65)
    solution = solve_constant_rate_network(
        generators.hydrogen_s1, time, np.array([1.0, 0.0])
    )
    equilibrium_ionized = upward / (upward + downward)
    expected = equilibrium_ionized * (1.0 - np.exp(-(upward + downward) * time))
    assert np.allclose(solution.population[:, 1], expected, rtol=2.0e-14, atol=2.0e-15)
    assert solution.maximum_particle_conservation_residual < 2.0e-15


def test_constant_helium_stationary_state_remains_stationary() -> None:
    generators = h_he_rate_generators_s1(
        1.0,
        0.0,
        4.0,
        3.0,
        0.0,
        0.0,
        0.0,
        0.0,
        2.0,
        5.0,
        0.0,
        0.0,
        0.0,
    )
    weights = np.array([2.0 * 5.0, 4.0 * 5.0, 4.0 * 3.0])
    stationary = weights / np.sum(weights)
    solution = solve_constant_rate_network(
        generators.helium_s1, np.linspace(0.0, 10.0, 17), stationary
    )
    assert np.allclose(solution.population, stationary[None, :], rtol=2.0e-14, atol=2.0e-15)
    assert solution.minimum_population > 0.0


def test_atomic_kinetics_contains_no_forbidden_repairs() -> None:
    source = Path(
        "src/eccentric_tde_observer/atomic_kinetics.py"
    ).read_text(encoding="utf-8")
    forbidden = ("nan_to_num", "np.clip", "numpy.clip")
    assert all(token not in source for token in forbidden)
