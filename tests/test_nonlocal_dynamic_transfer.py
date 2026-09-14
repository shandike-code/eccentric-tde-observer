from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.continuum_emission import (
    edge_resolved_milne_energy_grid_ev,
)
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.nonlocal_dynamic_transfer import (
    radiation_timescale_audit,
    solve_frozen_nonlocal_transfer_phase,
    symmetric_full_column_from_half,
)
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S, PLANCK_ERG_S
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_half_range_mu_weights,
    solve_static_slab_transfer,
)
from eccentric_tde_observer.source import PhysicalDomainError


def _lte_half_column(depth_points: int = 4):
    mass = np.geomspace(0.02, 0.2, depth_points)
    density = np.geomspace(2.0e-10, 2.0e-8, depth_points)
    temperature = np.linspace(2.0e4, 3.0e4, depth_points)
    ionization = lte_hydrogen_helium_ionization(density, temperature)
    hydrogen = np.column_stack(
        (
            ionization.hydrogen_neutral_fraction,
            ionization.hydrogen_ionized_fraction,
        )
    )
    helium = np.column_stack(
        (
            ionization.helium_neutral_fraction,
            ionization.helium_singly_ionized_fraction,
            ionization.helium_doubly_ionized_fraction,
        )
    )
    return mass, density, temperature, hydrogen, helium


def test_symmetric_full_column_preserves_mass_and_mirror_state() -> None:
    mass, density, temperature, hydrogen, helium = _lte_half_column()
    column = symmetric_full_column_from_half(
        mass, density, temperature, hydrogen, helium
    )
    assert column.half_depth_points == mass.size
    assert np.isclose(column.one_sided_column_mass_g_cm2, np.sum(mass))
    assert np.allclose(
        column.density_g_cm3 * column.cell_width_cm,
        np.concatenate((mass, mass[::-1])),
        rtol=8.0e-16,
        atol=0.0,
    )
    assert np.array_equal(column.temperature_k, column.temperature_k[::-1])
    assert column.maximum_mirror_residual < 8.0e-16


def test_frozen_lte_symmetric_transfer_closes_energy_and_mirror_gates() -> None:
    mass, density, temperature, hydrogen, helium = _lte_half_column()
    energy = edge_resolved_milne_energy_grid_ev(1.0, 200.0, 17)
    frequency = energy * EV_ERG / PLANCK_ERG_S
    result = solve_frozen_nonlocal_transfer_phase(
        frequency,
        mass,
        density,
        temperature,
        hydrogen,
        helium,
        angular_order=4,
    )
    assert result.mean_intensity_top_half_cgs.shape == (
        frequency.size,
        mass.size,
    )
    assert result.relative_integrated_energy_residual < 2.0e-12
    assert result.maximum_mean_intensity_mirror_residual < 2.0e-12
    assert result.maximum_boundary_spectrum_mirror_residual < 2.0e-12
    assert result.maximum_source_equation_residual < 2.0e-12
    assert result.minimum_intensity_cgs >= 0.0
    assert result.minimum_source_function_cgs >= 0.0


def test_transfer_subcells_match_manual_refinement_and_restrict_to_material_grid():
    mass, density, temperature, hydrogen, helium = _lte_half_column()
    energy = edge_resolved_milne_energy_grid_ev(1.0, 200.0, 17)
    frequency = energy * EV_ERG / PLANCK_ERG_S
    refined = solve_frozen_nonlocal_transfer_phase(
        frequency,
        mass,
        density,
        temperature,
        hydrogen,
        helium,
        angular_order=4,
        transfer_subcells_per_material_cell=2,
        scattering_linear_solver="sparse_interface",
    )
    manual = solve_frozen_nonlocal_transfer_phase(
        frequency,
        np.repeat(mass / 2.0, 2),
        np.repeat(density, 2),
        np.repeat(temperature, 2),
        np.repeat(hydrogen, 2, axis=0),
        np.repeat(helium, 2, axis=0),
        angular_order=4,
        scattering_linear_solver="sparse_interface",
    )

    assert np.allclose(
        refined.top_outward_flux_nu_cgs,
        manual.top_outward_flux_nu_cgs,
        rtol=3.0e-14,
        atol=0.0,
    )
    assert np.allclose(
        refined.mean_intensity_top_half_cgs,
        np.mean(
            manual.mean_intensity_top_half_cgs.reshape(frequency.size, 4, 2),
            axis=2,
        ),
        rtol=3.0e-14,
        atol=0.0,
    )
    assert np.allclose(
        refined.radiative_heating_top_half_erg_s_cm3,
        np.mean(
            manual.radiative_heating_top_half_erg_s_cm3.reshape(4, 2), axis=1
        ),
        rtol=3.0e-14,
        atol=0.0,
    )
    assert refined.material_half_depth_points == 4
    assert refined.transfer_half_depth_points == 8
    assert refined.transfer_subcells_per_material_cell == 2
    assert refined.scattering_linear_solver == "sparse_interface"


def test_transfer_subcell_count_rejects_invalid_value() -> None:
    mass, density, temperature, hydrogen, helium = _lte_half_column()
    with pytest.raises(PhysicalDomainError, match="positive integer"):
        solve_frozen_nonlocal_transfer_phase(
            np.array([1.0e14, 2.0e14]),
            mass,
            density,
            temperature,
            hydrogen,
            helium,
            transfer_subcells_per_material_cell=0,
        )


def test_optically_thick_linear_source_recovers_diffusion_flux() -> None:
    depth_points = 80
    edges = np.arange(depth_points + 1, dtype=np.float64)
    centres = 0.5 * (edges[:-1] + edges[1:])
    extinction = 5.0
    source_gradient = 2.0e-3
    source = 1.0 + source_gradient * centres
    mu, weight = gauss_legendre_half_range_mu_weights(16)
    transfer = solve_static_slab_transfer(
        np.array([1.0e15]),
        edges,
        mu,
        weight,
        np.full((1, depth_points), extinction),
        source[None, :],
        np.ones((1, depth_points)),
    )
    cell_flux = 2.0 * np.pi * np.einsum(
        "m,fmz,m->fz",
        weight,
        transfer.intensity_cell_average,
        mu,
    )[0]
    expected = -4.0 * np.pi * source_gradient / (3.0 * extinction)
    assert np.allclose(cell_flux[20:60], expected, rtol=2.0e-11, atol=0.0)


def test_radiation_timescale_audit_recovers_uniform_column_formula() -> None:
    mass = np.array([2.0, 3.0])
    density = np.array([[2.0, 1.5], [1.0, 3.0]])
    opacity = np.array([[4.0, 5.0], [2.0, 6.0]])
    period = 100.0
    result = radiation_timescale_audit(mass, density, opacity, period)
    thickness = np.sum(mass[None, :] / density, axis=1)
    optical_depth = np.sum(opacity * mass[None, :], axis=1)
    expected = 3.0 * optical_depth * thickness / LIGHT_SPEED_CM_S
    assert np.array_equal(result.half_thickness_cm, thickness)
    assert np.array_equal(result.half_rosseland_optical_depth, optical_depth)
    assert np.allclose(result.diffusion_time_s, expected, rtol=2.0e-16)


def test_nonlocal_dynamic_transfer_uses_no_forbidden_numerical_repairs() -> None:
    source = Path(
        "src/eccentric_tde_observer/nonlocal_dynamic_transfer.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("nan_to_num", "np.clip", "numpy.clip"):
        assert forbidden not in source
