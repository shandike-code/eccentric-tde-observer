from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.atomic_continuum import (
    ground_state_saha_factor_cm3,
)
from eccentric_tde_observer.atomic_kinetics import (
    H_HE_COLLISIONAL_IONIZATION_FITS,
    collisional_photoionization_equilibrium,
    detailed_balance_three_body_recombination_coefficient_cm6_s,
)
from eccentric_tde_observer.atmosphere import (
    PROTON_MASS_G,
    SOLAR_FULLY_IONIZED_H_HE,
)
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.orbital_kinetics import (
    charge_neutral_backward_euler_step,
)
from eccentric_tde_observer.prescribed_radiation import (
    edge_resolved_photoionization_energy_grid_ev,
    prescribed_planck_photoionization_rates_s1,
)
from eccentric_tde_observer.source import PhysicalDomainError


IONIZATION_ENERGIES_EV = (13.59843449, 24.587389, 54.417765)


def test_edge_resolved_grid_contains_all_ground_state_thresholds() -> None:
    energy = edge_resolved_photoionization_energy_grid_ev(1.0, 5000.0, 257)
    for threshold in (13.60, 24.59, 54.42):
        assert np.count_nonzero(energy == threshold) == 1
    assert np.all(np.diff(energy) > 0.0)
    assert not energy.flags.writeable


def test_edge_resolved_grid_rejects_invalid_bounds_and_fit_extrapolation() -> None:
    with pytest.raises(PhysicalDomainError, match="bounds"):
        edge_resolved_photoionization_energy_grid_ev(10.0, 1.0, 257)
    with pytest.raises(PhysicalDomainError, match="at least two"):
        edge_resolved_photoionization_energy_grid_ev(1.0, 5000.0, 1)
    with pytest.raises(PhysicalDomainError, match="Verner"):
        edge_resolved_photoionization_energy_grid_ev(1.0, 5.1e4, 257)


def test_prescribed_planck_rates_are_exactly_zero_and_linear_in_dilution() -> None:
    energy = edge_resolved_photoionization_energy_grid_ev(1.0, 5000.0, 1025)
    temperature = np.array([4.0e4, 8.0e4, 1.2e5])
    unit = prescribed_planck_photoionization_rates_s1(
        temperature, np.ones(temperature.size), energy
    )
    scale = np.array([0.0, 1.0e-4, 0.3])
    diluted = prescribed_planck_photoionization_rates_s1(
        temperature, scale, energy
    )
    assert np.array_equal(diluted.photoionization_s1[0], np.zeros(3))
    assert np.allclose(
        diluted.photoionization_s1[1:],
        scale[1:, None] * unit.photoionization_s1[1:],
        rtol=2.0e-16,
        atol=0.0,
    )
    assert not diluted.photoionization_s1.flags.writeable


def test_prescribed_planck_rates_reject_invalid_inputs() -> None:
    energy = edge_resolved_photoionization_energy_grid_ev(1.0, 5000.0, 257)
    with pytest.raises(PhysicalDomainError, match="temperature"):
        prescribed_planck_photoionization_rates_s1([-1.0], [1.0], energy)
    with pytest.raises(PhysicalDomainError, match="dilution"):
        prescribed_planck_photoionization_rates_s1([1.0e5], [-1.0], energy)
    with pytest.raises(PhysicalDomainError, match="increasing"):
        prescribed_planck_photoionization_rates_s1(
            [1.0e5], [1.0], energy[::-1]
        )


def test_thermal_detailed_balance_rates_recover_the_same_saha_state() -> None:
    density = 1.0e-10
    temperature = 1.0e5
    composition = SOLAR_FULLY_IONIZED_H_HE
    hydrogen = composition.hydrogen_mass_fraction * density / PROTON_MASS_G
    helium = composition.helium_mass_fraction * density / (4.0 * PROTON_MASS_G)
    energy = edge_resolved_photoionization_energy_grid_ev(1.0, 5000.0, 2049)
    gamma = prescribed_planck_photoionization_rates_s1(
        [temperature], [1.0], energy
    ).photoionization_s1[0]
    saha = np.array(
        [
            ground_state_saha_factor_cm3(temperature, ionization_energy)
            for ionization_energy in IONIZATION_ENERGIES_EV
        ]
    )
    collision = np.array(
        [fit.coefficient_cm3_s(temperature) for fit in H_HE_COLLISIONAL_IONIZATION_FITS]
    )
    radiative_db = gamma / saha
    three_body_db = np.array(
        [
            detailed_balance_three_body_recombination_coefficient_cm6_s(rate, factor)
            for rate, factor in zip(collision, saha, strict=True)
        ]
    )
    equilibrium = collisional_photoionization_equilibrium(
        hydrogen,
        helium,
        *gamma,
        *collision,
        *radiative_db,
        *three_body_db,
    )
    lte = lte_hydrogen_helium_ionization(density, temperature, composition)
    expected_h = np.array(
        [lte.hydrogen_neutral_fraction, lte.hydrogen_ionized_fraction]
    ).reshape(2)
    expected_he = np.array(
        [
            lte.helium_neutral_fraction,
            lte.helium_singly_ionized_fraction,
            lte.helium_doubly_ionized_fraction,
        ]
    ).reshape(3)
    actual_h = np.array(
        [equilibrium.hydrogen_neutral_fraction, equilibrium.hydrogen_ionized_fraction]
    ).reshape(2)
    actual_he = np.array(
        [
            equilibrium.helium_neutral_fraction,
            equilibrium.helium_singly_ionized_fraction,
            equilibrium.helium_doubly_ionized_fraction,
        ]
    ).reshape(3)
    assert np.allclose(actual_h, expected_h, rtol=0.0, atol=3.0e-15)
    assert np.allclose(actual_he, expected_he, rtol=0.0, atol=3.0e-15)

    step = charge_neutral_backward_euler_step(
        expected_h,
        expected_he,
        hydrogen,
        helium,
        1.0e6,
        gamma,
        collision,
        radiative_db,
        three_body_db,
    )
    assert np.allclose(step.hydrogen_fraction, expected_h, rtol=0.0, atol=4.0e-15)
    assert np.allclose(step.helium_fraction, expected_he, rtol=0.0, atol=4.0e-15)


def test_zero_prescribed_field_is_identical_to_the_existing_zero_rate_path() -> None:
    energy = edge_resolved_photoionization_energy_grid_ev(1.0, 5000.0, 257)
    gamma = prescribed_planck_photoionization_rates_s1(
        [8.0e4], [0.0], energy
    ).photoionization_s1[0]
    collision = np.array(
        [fit.coefficient_cm3_s(8.0e4) for fit in H_HE_COLLISIONAL_IONIZATION_FITS]
    )
    radiative = np.array([1.0e-13, 2.0e-13, 3.0e-13])
    three_body = np.zeros(3)
    arguments = (
        [0.8, 0.2],
        [0.6, 0.3, 0.1],
        1.0e12,
        1.0e11,
        10.0,
    )
    prescribed = charge_neutral_backward_euler_step(
        *arguments, gamma, collision, radiative, three_body
    )
    legacy_zero = charge_neutral_backward_euler_step(
        *arguments, np.zeros(3), collision, radiative, three_body
    )
    assert np.array_equal(
        prescribed.hydrogen_fraction, legacy_zero.hydrogen_fraction
    )
    assert np.array_equal(prescribed.helium_fraction, legacy_zero.helium_fraction)
    assert prescribed.electron_density_cm3 == legacy_zero.electron_density_cm3


def test_prescribed_radiation_contains_no_forbidden_repairs() -> None:
    source = Path("src/eccentric_tde_observer/prescribed_radiation.py").read_text(
        encoding="utf-8"
    )
    forbidden = ("nan_to_num", "np.clip", "numpy.clip")
    assert all(token not in source for token in forbidden)
