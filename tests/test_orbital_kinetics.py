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
    collisional_photoionization_equilibrium,
    detailed_balance_three_body_recombination_coefficient_cm6_s,
)
from eccentric_tde_observer.orbital_kinetics import (
    HHeRateOrbit,
    charge_neutral_backward_euler_step,
    solve_periodic_h_he_kinetics,
)
from eccentric_tde_observer.source import PhysicalDomainError


IONIZATION_ENERGIES_EV = (13.59843449, 24.587389, 54.417765)


def _physical_coefficients(temperature_k: float):
    collision = np.array(
        [fit.coefficient_cm3_s(temperature_k) for fit in H_HE_COLLISIONAL_IONIZATION_FITS]
    )
    saha = np.array(
        [
            ground_state_saha_factor_cm3(temperature_k, energy)
            for energy in IONIZATION_ENERGIES_EV
        ]
    )
    three_body = np.array(
        [
            detailed_balance_three_body_recombination_coefficient_cm6_s(rate, factor)
            for rate, factor in zip(collision, saha, strict=True)
        ]
    )
    radiative = np.array(
        [
            H_I_RECOMBINATION_FIT.coefficient_cm3_s(temperature_k),
            HE_I_RECOMBINATION_FIT.coefficient_cm3_s(temperature_k),
            HE_II_RECOMBINATION_FIT.coefficient_cm3_s(temperature_k),
        ]
    )
    return collision, radiative, three_body


def _hydrogen_photo_rr_analytic(
    time_s: float, initial_ionized: float, gamma_s1: float, nuclei_cm3: float, alpha_cm3_s: float
) -> float:
    coefficient = nuclei_cm3 * alpha_cm3_s
    discriminant = np.sqrt(gamma_s1**2 + 4.0 * coefficient * gamma_s1)
    positive_root = (-gamma_s1 + discriminant) / (2.0 * coefficient)
    negative_root = (-gamma_s1 - discriminant) / (2.0 * coefficient)
    ratio = (initial_ionized - positive_root) / (initial_ionized - negative_root)
    evolved_ratio = ratio * np.exp(
        -coefficient * (positive_root - negative_root) * time_s
    )
    return float(
        (positive_root - evolved_ratio * negative_root) / (1.0 - evolved_ratio)
    )


def test_rate_orbit_rejects_invalid_shapes_and_negative_rates() -> None:
    with pytest.raises(PhysicalDomainError, match="shape"):
        HHeRateOrbit(
            np.ones(4),
            np.ones(4),
            np.ones(4),
            np.zeros((4, 2)),
            np.zeros((4, 3)),
            np.zeros((4, 3)),
            np.zeros((4, 3)),
        )
    with pytest.raises(PhysicalDomainError, match="non-negative"):
        HHeRateOrbit(
            np.ones(4),
            np.ones(4),
            np.ones(4),
            np.zeros((4, 3)),
            -np.ones((4, 3)),
            np.zeros((4, 3)),
            np.zeros((4, 3)),
        )


def test_backward_euler_hydrogen_riccati_control_is_first_order_convergent() -> None:
    gamma = 1.0
    hydrogen = 2.0
    alpha = 1.0
    total_time = 2.0
    initial_h = np.array([0.8, 0.2])
    initial_he = np.array([1.0, 0.0, 0.0])
    analytic = _hydrogen_photo_rr_analytic(
        total_time, initial_h[1], gamma, hydrogen, alpha
    )
    errors = []
    for steps in (32, 64, 128, 256):
        state_h = initial_h.copy()
        state_he = initial_he.copy()
        for _ in range(steps):
            result = charge_neutral_backward_euler_step(
                state_h,
                state_he,
                hydrogen,
                0.0,
                total_time / steps,
                np.array([gamma, 0.0, 0.0]),
                np.zeros(3),
                np.array([alpha, 0.0, 0.0]),
                np.zeros(3),
            )
            state_h = np.array(result.hydrogen_fraction)
            state_he = np.array(result.helium_fraction)
        errors.append(abs(state_h[1] - analytic))
        assert result.relative_charge_residual < 3.0e-16
        assert result.particle_conservation_residual < 3.0e-15
    assert errors[0] / errors[1] > 1.9
    assert errors[1] / errors[2] > 1.9
    assert errors[2] / errors[3] > 1.9


def test_collision_three_body_equilibrium_is_an_implicit_fixed_point() -> None:
    temperature = 1.0e5
    hydrogen = 1.0e12
    helium = 1.0e11
    collision, radiative, three_body = _physical_coefficients(temperature)
    equilibrium = collisional_photoionization_equilibrium(
        hydrogen,
        helium,
        0.0,
        0.0,
        0.0,
        *collision,
        *radiative,
        *three_body,
    )
    hydrogen_fraction = np.array(
        [equilibrium.hydrogen_neutral_fraction, equilibrium.hydrogen_ionized_fraction]
    )
    helium_fraction = np.array(
        [
            equilibrium.helium_neutral_fraction,
            equilibrium.helium_singly_ionized_fraction,
            equilibrium.helium_doubly_ionized_fraction,
        ]
    )
    result = charge_neutral_backward_euler_step(
        hydrogen_fraction,
        helium_fraction,
        hydrogen,
        helium,
        1.0e5,
        np.zeros(3),
        collision,
        radiative,
        three_body,
    )
    assert np.allclose(result.hydrogen_fraction, hydrogen_fraction, rtol=0.0, atol=3.0e-15)
    assert np.allclose(result.helium_fraction, helium_fraction, rtol=0.0, atol=3.0e-15)


def test_exactly_neutral_collision_only_state_is_an_absorbing_kinetic_branch() -> None:
    collision, radiative, three_body = _physical_coefficients(1.0e5)
    result = charge_neutral_backward_euler_step(
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        1.0e12,
        1.0e11,
        1.0,
        np.zeros(3),
        collision,
        radiative,
        three_body,
    )
    assert np.array_equal(result.hydrogen_fraction, np.array([1.0, 0.0]))
    assert np.array_equal(result.helium_fraction, np.array([1.0, 0.0, 0.0]))
    assert result.electron_density_cm3 == 0.0


def test_periodic_solution_loses_positive_initial_condition_memory() -> None:
    points = 64
    phase = np.linspace(0.0, 2.0 * np.pi, points, endpoint=False)
    duration = np.full(points, 10.0 / points)
    photo = np.column_stack(
        (
            1.0 + 0.4 * np.sin(phase),
            0.7 + 0.2 * np.cos(phase),
            0.4 + 0.1 * np.sin(phase),
        )
    )
    orbit = HHeRateOrbit(
        np.full(points, 2.0),
        np.full(points, 0.2),
        duration,
        photo,
        np.zeros((points, 3)),
        np.tile(np.array([1.0, 1.2, 0.8]), (points, 1)),
        np.zeros((points, 3)),
    )
    first = solve_periodic_h_he_kinetics(
        orbit, [0.8, 0.2], [0.6, 0.3, 0.1], cycle_tolerance=2.0e-12
    )
    second = solve_periodic_h_he_kinetics(
        orbit, [0.2, 0.8], [0.1, 0.3, 0.6], cycle_tolerance=2.0e-12
    )
    assert np.allclose(first.hydrogen_fraction, second.hydrogen_fraction, atol=4.0e-12, rtol=0.0)
    assert np.allclose(first.helium_fraction, second.helium_fraction, atol=4.0e-12, rtol=0.0)
    assert first.maximum_relative_charge_residual < 3.0e-16
    assert first.maximum_particle_conservation_residual < 2.0e-14


def test_constant_orbit_preserves_the_self_consistent_equilibrium() -> None:
    temperature = 1.0e5
    hydrogen = 1.0e12
    helium = 1.0e11
    collision, radiative, three_body = _physical_coefficients(temperature)
    equilibrium = collisional_photoionization_equilibrium(
        hydrogen, helium, 0.0, 0.0, 0.0, *collision, *radiative, *three_body
    )
    initial_h = np.array(
        [equilibrium.hydrogen_neutral_fraction, equilibrium.hydrogen_ionized_fraction]
    )
    initial_he = np.array(
        [
            equilibrium.helium_neutral_fraction,
            equilibrium.helium_singly_ionized_fraction,
            equilibrium.helium_doubly_ionized_fraction,
        ]
    )
    points = 8
    orbit = HHeRateOrbit(
        np.full(points, hydrogen),
        np.full(points, helium),
        np.full(points, 1.0e3),
        np.zeros((points, 3)),
        np.tile(collision, (points, 1)),
        np.tile(radiative, (points, 1)),
        np.tile(three_body, (points, 1)),
    )
    solution = solve_periodic_h_he_kinetics(orbit, initial_h, initial_he)
    assert solution.cycles == 1
    assert solution.cycle_residual < 4.0e-15
    assert np.allclose(solution.hydrogen_fraction, initial_h[None, :], atol=4.0e-15, rtol=0.0)
    assert np.allclose(solution.helium_fraction, initial_he[None, :], atol=4.0e-15, rtol=0.0)


def test_orbital_kinetics_contains_no_forbidden_repairs() -> None:
    source = Path("src/eccentric_tde_observer/orbital_kinetics.py").read_text(
        encoding="utf-8"
    )
    forbidden = ("nan_to_num", "np.clip", "numpy.clip")
    assert all(token not in source for token in forbidden)
