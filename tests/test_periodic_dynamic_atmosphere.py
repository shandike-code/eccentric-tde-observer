from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.continuum_emission import edge_resolved_milne_energy_grid_ev
from eccentric_tde_observer.dynamic_column import build_zo_periodic_column_background
from eccentric_tde_observer.hydrostatic_atmosphere import (
    build_zo_constrained_n3_column,
    solve_lte_rosseland_diffusion_column,
    symmetric_dissipation_profile,
)
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.periodic_dynamic_atmosphere import (
    PeriodicDynamicCycleCheckpoint,
    adaptive_lagrangian_mass_grid,
    build_periodic_dynamic_half_column,
    cyclic_log_density_increments,
    diffusion_outward_flux_edges_erg_s_cm2,
    ground_state_thermodynamics,
    ideal_gas_adiabatic_temperature_k,
    nested_mass_fraction_edges,
    solve_periodic_dynamic_column,
    two_grid_error_lagrangian_mass_grid,
)
from eccentric_tde_observer.radiation import (
    PLANCK_ERG_S,
    STEFAN_BOLTZMANN_ERG_S_CM2_K4,
)
from eccentric_tde_observer.reference_case import build_strict_domain_reference_model
from eccentric_tde_observer.source import PhysicalDomainError


def test_cyclic_density_increment_closes_without_derivative_quadrature() -> None:
    density = np.array(
        [[1.0, 3.0], [2.0, 1.5], [4.0, 6.0], [0.5, 2.0]]
    )
    increment = cyclic_log_density_increments(density)
    assert np.allclose(np.sum(increment, axis=0), 0.0, atol=8.0e-16)
    assert np.allclose(increment[0], np.log(density[1] / density[0]))
    assert np.allclose(increment[-1], np.log(density[0] / density[-1]))


def test_ideal_gas_adiabatic_control_recovers_gamma_law_and_cycle() -> None:
    density = np.array([2.0, 8.0, 16.0, 4.0, 2.0])
    temperature = ideal_gas_adiabatic_temperature_k(
        density, 3.0e4, adiabatic_index=5.0 / 3.0
    )
    expected = 3.0e4 * (density / density[0]) ** (2.0 / 3.0)
    assert np.allclose(temperature, expected, rtol=3.0e-16)
    assert temperature[-1] == temperature[0]


def test_ground_state_thermodynamics_includes_ionization_and_radiation() -> None:
    density = np.array([1.0e-9, 2.0e-9])
    temperature = np.array([4.0e4, 8.0e4])
    hydrogen = np.array([[1.0, 0.0], [0.0, 1.0]])
    helium = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    state = ground_state_thermodynamics(
        density, temperature, hydrogen, helium
    )
    assert state.specific_ionization_energy_erg_g[0] == 0.0
    assert state.specific_ionization_energy_erg_g[1] > 0.0
    assert state.electron_density_cm3[0] == 0.0
    assert state.electron_density_cm3[1] > 0.0
    assert np.allclose(
        state.specific_total_energy_erg_g,
        state.specific_gas_energy_erg_g
        + state.specific_radiation_energy_erg_g
        + state.specific_ionization_energy_erg_g,
    )
    assert np.allclose(
        state.total_pressure_erg_cm3,
        state.gas_pressure_erg_cm3 + state.radiation_pressure_erg_cm3,
    )


def test_dynamic_diffusion_flux_recovers_a_discrete_static_solution() -> None:
    count = 7
    cell_mass = np.full(count, 2.0)
    opacity = np.full(count, 0.4)
    specific_heating = 3.0e10
    target_flux = specific_heating * np.sum(cell_mass)
    expected_flux = np.empty(count + 1)
    expected_flux[0] = target_flux
    expected_flux[1:] = target_flux - specific_heating * np.cumsum(cell_mass)
    temperature_fourth = np.empty(count)
    surface_tau = 0.5 * opacity[0] * cell_mass[0]
    temperature_fourth[0] = (
        expected_flux[0]
        / STEFAN_BOLTZMANN_ERG_S_CM2_K4
        * (0.5 + 0.75 * surface_tau)
    )
    for depth in range(1, count):
        optical_separation = 0.5 * (
            opacity[depth - 1] * cell_mass[depth - 1]
            + opacity[depth] * cell_mass[depth]
        )
        temperature_fourth[depth] = temperature_fourth[depth - 1] + (
            3.0
            * expected_flux[depth]
            * optical_separation
            / (4.0 * STEFAN_BOLTZMANN_ERG_S_CM2_K4)
        )
    recovered = diffusion_outward_flux_edges_erg_s_cm2(
        temperature_fourth**0.25, opacity, cell_mass
    )
    assert np.allclose(recovered, expected_flux, rtol=3.0e-15, atol=3.0e-3)
    assert recovered[-1] == 0.0


def test_small_periodic_dynamic_column_closes_energy_and_loses_initial_memory() -> None:
    model = build_strict_domain_reference_model(17, 32)
    background = build_zo_periodic_column_background(model, 2)
    depth_points = 3
    grid = build_periodic_dynamic_half_column(
        background, depth_points, "uniform_specific"
    )
    energy = edge_resolved_milne_energy_grid_ev(0.1, 5000.0, 17)
    frequency = energy * EV_ERG / PLANCK_ERG_S
    column = build_zo_constrained_n3_column(
        float(background.one_sided_column_mass_g_cm2[0]),
        float(background.scale_height_cm[0]),
        float(background.pressure_gravity_coefficient_s2[0]),
        depth_points,
    )
    dissipation = symmetric_dissipation_profile(
        column,
        float(background.one_face_surface_flux_erg_s_cm2[0]),
        "uniform_specific",
    )
    static = solve_lte_rosseland_diffusion_column(
        column,
        dissipation,
        float(background.effective_temperature_k[0]),
        frequency,
        relative_tolerance=1.0e-5,
    )
    temperature = np.array(static.full_temperature_k[:depth_points])
    lte = lte_hydrogen_helium_ionization(
        grid.density_g_cm3[0], temperature
    )
    hydrogen = np.column_stack(
        (lte.hydrogen_neutral_fraction, lte.hydrogen_ionized_fraction)
    )
    helium = np.column_stack(
        (
            lte.helium_neutral_fraction,
            lte.helium_singly_ionized_fraction,
            lte.helium_doubly_ionized_fraction,
        )
    )
    first = solve_periodic_dynamic_column(
        grid,
        frequency,
        temperature,
        hydrogen,
        helium,
        minimum_temperature_k=2000.0,
        maximum_temperature_k=2.0e6,
        cycle_tolerance=5.0e-7,
        local_energy_tolerance=1.0e-6,
        maximum_cycles=8,
    )
    checkpoints: list[PeriodicDynamicCycleCheckpoint] = []
    colored = solve_periodic_dynamic_column(
        grid,
        frequency,
        temperature,
        hydrogen,
        helium,
        minimum_temperature_k=2000.0,
        maximum_temperature_k=2.0e6,
        cycle_tolerance=5.0e-7,
        local_energy_tolerance=1.0e-6,
        maximum_cycles=8,
        use_colored_tridiagonal_jacobian=True,
        cycle_callback=checkpoints.append,
    )
    second = solve_periodic_dynamic_column(
        grid,
        frequency,
        1.1 * temperature,
        np.broadcast_to(np.array([0.4, 0.6]), hydrogen.shape),
        np.broadcast_to(np.array([0.3, 0.4, 0.3]), helium.shape),
        minimum_temperature_k=2000.0,
        maximum_temperature_k=2.0e6,
        cycle_tolerance=5.0e-7,
        local_energy_tolerance=1.0e-6,
        maximum_cycles=8,
    )
    assert first.relative_cycle_energy_ledger_residual < 2.0e-10
    assert first.maximum_relative_local_energy_residual < 1.0e-8
    assert first.maximum_relative_charge_residual < 2.0e-14
    assert first.maximum_particle_conservation_residual < 2.0e-14
    assert first.minimum_population_fraction >= 0.0
    assert not first.used_colored_tridiagonal_jacobian
    assert colored.used_colored_tridiagonal_jacobian
    assert len(checkpoints) == colored.cycle_count
    assert checkpoints[-1].cycle_count == colored.cycle_count
    assert checkpoints[-1].cycle_residual == colored.cycle_residual
    assert np.all(np.isfinite(checkpoints[-1].temperature_k))
    assert np.max(
        np.abs(first.temperature_k - colored.temperature_k) / first.temperature_k
    ) < 2.0e-8
    assert np.max(
        np.abs(first.hydrogen_fraction - colored.hydrogen_fraction)
    ) < 2.0e-8
    assert np.max(np.abs(first.helium_fraction - colored.helium_fraction)) < 2.0e-8
    assert np.max(
        np.abs(first.temperature_k - second.temperature_k) / first.temperature_k
    ) < 2.0e-6
    assert np.max(
        np.abs(first.hydrogen_fraction - second.hydrogen_fraction)
    ) < 2.0e-6
    assert np.max(np.abs(first.helium_fraction - second.helium_fraction)) < 2.0e-6
    adaptive = adaptive_lagrangian_mass_grid(
        first, 6, monitor_sample_points=513
    )
    assert adaptive.mass_fraction_edges[0] == 0.0
    assert adaptive.mass_fraction_edges[-1] == 1.0
    assert np.all(np.diff(adaptive.mass_fraction_edges) > 0.0)
    assert adaptive.maximum_equidistribution_residual < 2.0e-6
    assert np.isclose(
        np.trapezoid(
            adaptive.normalized_monitor, adaptive.sampled_mass_fraction
        ),
        1.0,
        rtol=3.0e-15,
    )
    for component in (
        adaptive.log_temperature_component,
        adaptive.log_opacity_component,
        adaptive.helium_iii_component,
    ):
        assert np.isclose(
            np.trapezoid(component, adaptive.sampled_mass_fraction),
            1.0,
            rtol=3.0e-15,
        )
    adaptive_grid = build_periodic_dynamic_half_column(
        background,
        6,
        "uniform_specific",
        mass_fraction_edges=adaptive.mass_fraction_edges,
    )
    assert np.allclose(
        adaptive_grid.mass_fraction_edges,
        adaptive.mass_fraction_edges,
        rtol=2.0e-16,
        atol=0.0,
    )

    refined_grid = build_periodic_dynamic_half_column(
        background, 6, "uniform_specific"
    )
    refined_column = build_zo_constrained_n3_column(
        float(background.one_sided_column_mass_g_cm2[0]),
        float(background.scale_height_cm[0]),
        float(background.pressure_gravity_coefficient_s2[0]),
        6,
    )
    refined_dissipation = symmetric_dissipation_profile(
        refined_column,
        float(background.one_face_surface_flux_erg_s_cm2[0]),
        "uniform_specific",
    )
    refined_static = solve_lte_rosseland_diffusion_column(
        refined_column,
        refined_dissipation,
        float(background.effective_temperature_k[0]),
        frequency,
        relative_tolerance=1.0e-5,
    )
    refined_temperature = np.array(refined_static.full_temperature_k[:6])
    refined_lte = lte_hydrogen_helium_ionization(
        refined_grid.density_g_cm3[0], refined_temperature
    )
    refined_hydrogen = np.column_stack(
        (
            refined_lte.hydrogen_neutral_fraction,
            refined_lte.hydrogen_ionized_fraction,
        )
    )
    refined_helium = np.column_stack(
        (
            refined_lte.helium_neutral_fraction,
            refined_lte.helium_singly_ionized_fraction,
            refined_lte.helium_doubly_ionized_fraction,
        )
    )
    refined = solve_periodic_dynamic_column(
        refined_grid,
        frequency,
        refined_temperature,
        refined_hydrogen,
        refined_helium,
        minimum_temperature_k=2000.0,
        maximum_temperature_k=2.0e6,
        cycle_tolerance=5.0e-7,
        local_energy_tolerance=1.0e-6,
        maximum_cycles=8,
    )
    error_grid = two_grid_error_lagrangian_mass_grid(first, refined, 12)
    coarse_width = np.diff(error_grid.coarse_mass_fraction_edges)
    assert error_grid.component_names == (
        "pointwise_thermodynamic",
        "pointwise_population",
        "cell_average_thermodynamic",
        "cell_average_population",
    )
    assert np.allclose(
        np.sum(
            error_grid.normalized_error_components * coarse_width[None, :],
            axis=1,
        ),
        1.0,
        rtol=3.0e-15,
    )
    assert np.isclose(
        np.sum(error_grid.normalized_monitor_density * coarse_width),
        1.0,
        rtol=3.0e-15,
    )
    assert np.isclose(
        np.sum(error_grid.normalized_baseline_density * coarse_width),
        1.0,
        rtol=3.0e-15,
    )
    assert error_grid.baseline_monitor_fraction == 0.5
    assert error_grid.baseline_mass_spacing_power == 2.0
    assert error_grid.maximum_equidistribution_residual < 3.0e-15
    nested_six = nested_mass_fraction_edges(error_grid, 6)
    nested_three = nested_mass_fraction_edges(error_grid, 3)
    assert np.array_equal(nested_six, error_grid.master_mass_fraction_edges[::2])
    assert np.array_equal(nested_three, nested_six[::2])
    with pytest.raises(PhysicalDomainError, match="divide"):
        nested_mass_fraction_edges(error_grid, 5)


def test_periodic_dynamic_module_uses_no_forbidden_numerical_repairs() -> None:
    source = Path(
        "src/eccentric_tde_observer/periodic_dynamic_atmosphere.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("nan_to_num", "np.clip", "numpy.clip"):
        assert forbidden not in source
