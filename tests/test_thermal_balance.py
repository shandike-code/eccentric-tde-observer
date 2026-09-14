from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.atomic_continuum import (
    EV_ERG,
    ground_state_saha_factor_cm3,
)
from eccentric_tde_observer.continuum_emission import (
    IONIZATION_ENERGIES_EV,
    edge_resolved_milne_energy_grid_ev,
    ground_state_milne_continuum,
    solve_emissive_ground_state_slab,
)
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.radiation import PLANCK_ERG_S, planck_nu
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_half_range_mu_weights,
)
from eccentric_tde_observer.source import PhysicalDomainError
from eccentric_tde_observer.thermal_balance import (
    TemperatureBalanceConvergenceError,
    one_face_blackbody_dissipation_flux_erg_s_cm2,
    sampled_temperature_root_intervals,
    scan_isothermal_temperature_balance,
    solve_prescribed_heating_temperature_profile,
    uniform_fixed_density_heating_erg_s_cm3,
)


DENSITY_G_CM3 = 1.0e-10


def _control_grid():
    energy = edge_resolved_milne_energy_grid_ev(0.1, 5000.0, 65)
    frequency = energy * EV_ERG / PLANCK_ERG_S
    mu, weight = gauss_legendre_half_range_mu_weights(2)
    edges = np.linspace(0.0, 1.0e6, 4)
    top = np.zeros((frequency.size, mu.size))
    top[:, mu > 0.0] = 1.0e-6 * planck_nu(frequency, 1.5e5)[:, None]
    return frequency, mu, weight, edges, top, np.zeros_like(top)


def _lte_fractions(temperature_k: np.ndarray):
    state = lte_hydrogen_helium_ionization(DENSITY_G_CM3, temperature_k)
    electron = np.asarray(state.electron_density_cm3)
    saha = np.stack(
        [
            ground_state_saha_factor_cm3(temperature_k, energy)
            for energy in IONIZATION_ENERGIES_EV
        ],
        axis=-1,
    )
    hydrogen = np.column_stack(
        (electron / (electron + saha[:, 0]), saha[:, 0] / (electron + saha[:, 0]))
    )
    ratio_1 = saha[:, 1] / electron
    ratio_2 = saha[:, 2] / electron
    denominator = 1.0 + ratio_1 + ratio_1 * ratio_2
    helium = np.column_stack(
        (
            1.0 / denominator,
            ratio_1 / denominator,
            ratio_1 * ratio_2 / denominator,
        )
    )
    return hydrogen, helium


def test_depth_resolved_temperature_recovers_local_kirchhoff_source() -> None:
    frequency, _, _, _, _, _ = _control_grid()
    temperature = np.array([1.5e4, 2.5e4, 4.0e4])
    hydrogen, helium = _lte_fractions(temperature)
    continuum = ground_state_milne_continuum(
        DENSITY_G_CM3,
        temperature,
        frequency,
        hydrogen[:, 0],
        hydrogen[:, 1],
        helium[:, 0],
        helium[:, 1],
        helium[:, 2],
    )
    expected = planck_nu(frequency[:, None], temperature[None, :])
    assert np.max(np.abs(continuum.thermal_source_intensity - expected)) / np.max(
        expected
    ) < 3.0e-15


def test_traceable_uniform_heating_integrates_to_one_face_flux() -> None:
    edges = np.array([0.0, 2.0, 5.0, 9.0])
    flux = one_face_blackbody_dissipation_flux_erg_s_cm2(4.0e4)
    heating = uniform_fixed_density_heating_erg_s_cm3(flux, edges)
    assert np.isclose(np.sum(heating * np.diff(edges)), flux, rtol=2.0e-16)
    assert not heating.flags.writeable


def test_sampled_temperature_root_intervals_report_multiple_and_exact_roots() -> None:
    assert sampled_temperature_root_intervals(
        [1.0, 2.0, 3.0, 4.0, 5.0], [1.0, -1.0, 0.0, 1.0, -1.0]
    ) == ((1.0, 2.0), (3.0, 3.0), (4.0, 5.0))


def test_isothermal_scan_finds_stable_root_and_explicit_no_root() -> None:
    frequency, mu, weight, edges, top, bottom = _control_grid()
    temperatures = np.array([2.0e4, 3.0e4, 4.0e4, 5.0e4, 7.0e4])
    common = (
        temperatures,
        frequency,
        edges,
        mu,
        weight,
        DENSITY_G_CM3,
        top,
        bottom,
    )
    radiative = scan_isothermal_temperature_balance(
        *common,
        0.0,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        population_relaxation=1.0,
        population_tolerance=1.0e-9,
    )
    assert np.all(radiative.valid_evaluation)
    assert np.all(radiative.supplemental_heating_flux_erg_s_cm2 == 0.0)
    assert len(radiative.roots) == 1
    assert 4.0e4 < radiative.roots[0].temperature_k < 5.0e4
    assert radiative.roots[0].thermally_stable
    assert radiative.roots[0].relative_energy_residual < 1.0e-9

    high_flux = one_face_blackbody_dissipation_flux_erg_s_cm2(4.0e4)
    high_heating = uniform_fixed_density_heating_erg_s_cm3(high_flux, edges)
    no_root = scan_isothermal_temperature_balance(
        *common,
        high_heating,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        population_relaxation=1.0,
        population_tolerance=1.0e-9,
    )
    assert np.all(no_root.valid_evaluation)
    assert len(no_root.roots) == 0
    assert np.all(no_root.net_heating_flux_erg_s_cm2 > 0.0)


def test_profile_solver_recovers_manufactured_depth_temperature_root() -> None:
    frequency, mu, weight, edges, top, bottom = _control_grid()
    target_temperature = np.array([5.0e4, 6.0e4, 7.0e4])
    target = solve_emissive_ground_state_slab(
        frequency,
        edges,
        mu,
        weight,
        DENSITY_G_CM3,
        target_temperature,
        top,
        bottom,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        relaxation=1.0,
        tolerance=1.0e-9,
    )
    heating = -target.radiative_heating_erg_s_cm3
    assert np.all(heating > 0.0)
    solution = solve_prescribed_heating_temperature_profile(
        frequency,
        edges,
        mu,
        weight,
        DENSITY_G_CM3,
        top,
        bottom,
        heating,
        0.9 * target_temperature,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        temperature_bounds_k=(2.0e4, 1.2e5),
        population_relaxation=1.0,
        population_tolerance=1.0e-9,
        local_energy_tolerance=2.0e-6,
        optimizer_tolerance=1.0e-9,
    )
    assert np.allclose(solution.temperature_k, target_temperature, rtol=2.0e-8)
    assert solution.maximum_relative_local_energy_residual < 2.0e-6
    assert solution.relative_global_energy_residual < 2.0e-9
    assert np.all(solution.supplemental_heating_erg_s_cm3 == 0.0)
    assert solution.integrated_supplemental_heating_flux_erg_s_cm2 == 0.0
    assert solution.thermally_stable


def test_profile_solver_accepts_a_depth_resolved_density() -> None:
    frequency, mu, weight, edges, top, bottom = _control_grid()
    density = DENSITY_G_CM3 * np.array([0.7, 1.0, 1.4])
    target_temperature = np.array([5.0e4, 6.0e4, 7.0e4])
    target = solve_emissive_ground_state_slab(
        frequency,
        edges,
        mu,
        weight,
        density,
        target_temperature,
        top,
        bottom,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        relaxation=1.0,
        tolerance=1.0e-9,
    )
    heating = -target.radiative_heating_erg_s_cm3
    assert np.all(heating > 0.0)
    solution = solve_prescribed_heating_temperature_profile(
        frequency,
        edges,
        mu,
        weight,
        density,
        top,
        bottom,
        heating,
        0.92 * target_temperature,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        temperature_bounds_k=(2.0e4, 1.0e5),
        population_relaxation=1.0,
        population_tolerance=1.0e-9,
        local_energy_tolerance=3.0e-6,
        optimizer_tolerance=1.0e-9,
        analyze_stability=False,
    )
    assert np.allclose(solution.temperature_k, target_temperature, rtol=3.0e-8)
    assert solution.maximum_relative_local_energy_residual < 3.0e-6


def test_mirror_symmetric_temperature_parameterization_recovers_a_fixture() -> None:
    frequency, mu, weight, _, original_top, _ = _control_grid()
    top = np.array(original_top, copy=True)
    bottom = np.zeros_like(top)
    bottom[:, mu < 0.0] = top[:, mu > 0.0][:, ::-1]
    edges = np.linspace(0.0, 1.0e6, 5)
    density = DENSITY_G_CM3 * np.array([0.8, 1.2, 1.2, 0.8])
    target_temperature = np.array([6.0e4, 7.5e4, 7.5e4, 6.0e4])
    target = solve_emissive_ground_state_slab(
        frequency,
        edges,
        mu,
        weight,
        density,
        target_temperature,
        top,
        bottom,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        relaxation=1.0,
        tolerance=1.0e-9,
    )
    half_heating = -target.radiative_heating_erg_s_cm3[:2]
    heating = np.concatenate((half_heating, half_heating[::-1]))
    assert np.all(heating > 0.0)
    assert np.array_equal(heating, heating[::-1])
    solution = solve_prescribed_heating_temperature_profile(
        frequency,
        edges,
        mu,
        weight,
        density,
        top,
        bottom,
        heating,
        0.9 * target_temperature,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        temperature_bounds_k=(2.0e4, 1.0e5),
        population_relaxation=1.0,
        population_tolerance=1.0e-9,
        local_energy_tolerance=3.0e-6,
        optimizer_tolerance=1.0e-9,
        analyze_stability=False,
        mirror_symmetric_temperature=True,
    )
    assert solution.mirror_symmetric_temperature
    assert np.array_equal(solution.temperature_k, solution.temperature_k[::-1])
    assert np.allclose(solution.temperature_k, target_temperature, rtol=3.0e-8)


def test_mirror_symmetric_temperature_rejects_asymmetric_heating() -> None:
    frequency, mu, weight, _, top, bottom = _control_grid()
    with pytest.raises(PhysicalDomainError, match="symmetric heating"):
        solve_prescribed_heating_temperature_profile(
            frequency,
            np.linspace(0.0, 1.0e6, 5),
            mu,
            weight,
            DENSITY_G_CM3,
            top,
            bottom,
            [1.0, 2.0, 2.0, 3.0],
            [5.0e4, 6.0e4, 6.0e4, 5.0e4],
            [1.0, 0.0],
            [1.0, 0.0, 0.0],
            temperature_bounds_k=(2.0e4, 1.0e5),
            mirror_symmetric_temperature=True,
        )


def test_profile_solver_does_not_accept_an_unconverged_minimum() -> None:
    frequency, mu, weight, edges, top, bottom = _control_grid()
    heating = uniform_fixed_density_heating_erg_s_cm3(
        one_face_blackbody_dissipation_flux_erg_s_cm2(4.0e4), edges
    )
    with pytest.raises(TemperatureBalanceConvergenceError, match="no accepted interior root"):
        solve_prescribed_heating_temperature_profile(
            frequency,
            edges,
            mu,
            weight,
            DENSITY_G_CM3,
            top,
            bottom,
            heating,
            5.0e4,
            [1.0, 0.0],
            [1.0, 0.0, 0.0],
            temperature_bounds_k=(2.0e4, 1.0e5),
            population_relaxation=1.0,
            population_tolerance=1.0e-9,
            maximum_function_evaluations=4,
        )


def test_thermal_balance_source_uses_no_forbidden_numerical_repairs() -> None:
    source = Path("src/eccentric_tde_observer/thermal_balance.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("nan_to_num", "np.clip", "numpy.clip"):
        assert forbidden not in source
