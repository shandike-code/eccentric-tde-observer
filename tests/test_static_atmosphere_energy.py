from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.continuum_emission import (
    edge_resolved_milne_energy_grid_ev,
    solve_emissive_ground_state_slab,
)
from eccentric_tde_observer.radiation import (
    BOLTZMANN_ERG_K,
    PLANCK_ERG_S,
    planck_nu,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_half_range_mu_weights,
)
from eccentric_tde_observer.source import PhysicalDomainError
from eccentric_tde_observer.static_atmosphere_energy import (
    SupplementalEnergyControls,
    full_escape_hydrogen_helium_line_cooling_erg_s_cm3,
    supplemental_static_energy_terms,
    thomson_compton_heating_erg_s_cm3,
    top_hat_mass_column_heating_erg_s_cm3,
)
from eccentric_tde_observer.thermal_balance import (
    solve_prescribed_heating_temperature_profile,
)


DENSITY_G_CM3 = 1.0e-10


def _control_slab(temperature_k: float = 5.0e4):
    energy = edge_resolved_milne_energy_grid_ev(0.1, 5000.0, 65)
    frequency = energy * EV_ERG / PLANCK_ERG_S
    mu, weight = gauss_legendre_half_range_mu_weights(2)
    edges = np.linspace(0.0, 1.0e6, 4)
    top = np.zeros((frequency.size, mu.size))
    top[:, mu > 0.0] = 1.0e-6 * planck_nu(frequency, 1.5e5)[:, None]
    slab = solve_emissive_ground_state_slab(
        frequency,
        edges,
        mu,
        weight,
        DENSITY_G_CM3,
        temperature_k,
        top,
        np.zeros_like(top),
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        relaxation=1.0,
        tolerance=1.0e-9,
    )
    return frequency, mu, weight, edges, top, slab


def test_top_hat_deposition_integrates_exactly_across_partial_cell() -> None:
    edges = np.array([2.0, 5.0, 9.0, 14.0])
    density = 2.0
    flux = 37.0
    deposition = 11.0
    heating = top_hat_mass_column_heating_erg_s_cm3(
        flux, density, edges, deposition
    )
    assert np.isclose(np.sum(heating * np.diff(edges)), flux, rtol=2.0e-16)
    assert heating[0] == pytest.approx(density * flux / deposition)
    assert 0.0 < heating[1] < heating[0]
    assert heating[2] == 0.0
    assert not heating.flags.writeable


def test_top_hat_deposition_rejects_column_beyond_slab() -> None:
    with pytest.raises(PhysicalDomainError, match="total slab column"):
        top_hat_mass_column_heating_erg_s_cm3(
            1.0, 2.0, [0.0, 1.0, 2.0], 4.1
        )


def test_thomson_compton_exchange_has_analytic_zero_and_sign() -> None:
    frequency = np.array([1.0e15, 2.0e15, 4.0e15])
    mean = np.array([[1.0, 2.0], [0.7, 1.4], [0.2, 0.4]])
    numerator = np.trapezoid(
        mean * (PLANCK_ERG_S * frequency[:, None]), frequency, axis=0
    )
    denominator = 4.0 * BOLTZMANN_ERG_K * np.trapezoid(
        mean, frequency, axis=0
    )
    compton_temperature = numerator / denominator
    zero = thomson_compton_heating_erg_s_cm3(
        frequency, mean, [1.0e8, 2.0e8], compton_temperature
    )
    cooler = thomson_compton_heating_erg_s_cm3(
        frequency, mean, [1.0e8, 2.0e8], 0.5 * compton_temperature
    )
    hotter = thomson_compton_heating_erg_s_cm3(
        frequency, mean, [1.0e8, 2.0e8], 2.0 * compton_temperature
    )
    assert np.max(np.abs(zero)) / np.max(np.abs(cooler)) < 2.0e-15
    assert np.all(cooler > 0.0)
    assert np.all(hotter < 0.0)


def test_full_escape_line_cooling_is_positive_and_population_resolved() -> None:
    temperature = np.array([2.0e4, 8.0e4])
    hydrogen_only = full_escape_hydrogen_helium_line_cooling_erg_s_cm3(
        DENSITY_G_CM3,
        temperature,
        [1.0e13, 1.0e13],
        [0.5, 0.0],
        [0.0, 0.0],
    )
    helium_only = full_escape_hydrogen_helium_line_cooling_erg_s_cm3(
        DENSITY_G_CM3,
        temperature,
        [1.0e13, 1.0e13],
        [0.0, 0.0],
        [0.0, 0.5],
    )
    assert hydrogen_only[0] > 0.0
    assert hydrogen_only[1] == 0.0
    assert helium_only[0] == 0.0
    assert helium_only[1] > 0.0


def test_supplemental_process_controls_are_independent() -> None:
    _, _, _, _, _, slab = _control_slab()
    disabled = supplemental_static_energy_terms(
        slab,
        DENSITY_G_CM3,
        slab.temperature_k,
        SupplementalEnergyControls(),
    )
    compton = supplemental_static_energy_terms(
        slab,
        DENSITY_G_CM3,
        slab.temperature_k,
        SupplementalEnergyControls(include_compton_exchange=True),
    )
    line = supplemental_static_energy_terms(
        slab,
        DENSITY_G_CM3,
        slab.temperature_k,
        SupplementalEnergyControls(line_cooling_boundary="full_escape"),
    )
    assert np.all(disabled.net_heating_erg_s_cm3 == 0.0)
    assert np.all(compton.line_cooling_erg_s_cm3 == 0.0)
    assert np.any(compton.compton_heating_erg_s_cm3 != 0.0)
    assert np.all(line.compton_heating_erg_s_cm3 == 0.0)
    assert np.all(line.net_heating_erg_s_cm3 <= 0.0)
    assert line.maximum_photon_energy_over_electron_rest_energy < 0.01


def test_temperature_solver_includes_supplemental_energy_in_local_ledger() -> None:
    frequency, mu, weight, edges, top, target = _control_slab(6.0e4)
    supplemental = np.array([1.0e-3, 2.0e-3, 3.0e-3])
    heating = -target.radiative_heating_erg_s_cm3 - supplemental
    assert np.all(heating > 0.0)

    def evaluator(_, __):
        return supplemental

    result = solve_prescribed_heating_temperature_profile(
        frequency,
        edges,
        mu,
        weight,
        DENSITY_G_CM3,
        top,
        np.zeros_like(top),
        heating,
        5.5e4,
        [1.0, 0.0],
        [1.0, 0.0, 0.0],
        temperature_bounds_k=(2.0e4, 1.2e5),
        population_relaxation=1.0,
        population_tolerance=1.0e-9,
        local_energy_tolerance=2.0e-6,
        optimizer_tolerance=1.0e-9,
        supplemental_heating_evaluator=evaluator,
    )
    assert np.allclose(result.temperature_k, 6.0e4, rtol=2.0e-8)
    assert np.array_equal(result.supplemental_heating_erg_s_cm3, supplemental)
    assert result.relative_global_energy_residual < 2.0e-9


def test_static_atmosphere_energy_source_has_no_forbidden_repairs() -> None:
    source = Path(
        "src/eccentric_tde_observer/static_atmosphere_energy.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("nan_to_num", "np.clip", "numpy.clip"):
        assert forbidden not in source
