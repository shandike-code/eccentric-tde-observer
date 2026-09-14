from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.continuum_emission import (
    edge_resolved_milne_energy_grid_ev,
    solve_emissive_ground_state_slab,
)
from eccentric_tde_observer.hydrostatic_atmosphere import (
    audit_grey_diffusion_support,
    diagnose_lte_rosseland_scale_height,
    audit_zo_n3_hydrostatic_pressure,
    build_zo_constrained_n3_column,
    grey_surface_to_midplane_temperature_seed_k,
    fully_ionized_electron_scattering_opacity_cm2_g,
    solve_grey_diffusion_column,
    symmetric_dissipation_profile,
)
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.radiation import PLANCK_ERG_S, planck_nu
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_half_range_mu_weights,
)
from eccentric_tde_observer.source import PhysicalDomainError


def _column(half_depth_points: int = 6):
    return build_zo_constrained_n3_column(
        5.0, 2.0e8, 3.0e-6, half_depth_points
    )


def test_n3_column_recovers_mass_and_exact_mirror_symmetry() -> None:
    column = _column(8)
    assert column.relative_mass_reconstruction_residual < 3.0e-16
    assert np.isclose(
        np.sum(column.full_cell_mass_g_cm2),
        2.0 * column.midplane_column_mass_g_cm2,
        rtol=3.0e-16,
    )
    assert np.array_equal(
        column.full_density_g_cm3,
        column.full_density_g_cm3[::-1],
    )
    assert np.array_equal(
        column.required_support_pressure_erg_cm3,
        column.required_support_pressure_erg_cm3[::-1],
    )
    assert column.half_height_edges_cm[0] == column.surface_height_cm
    assert column.half_height_edges_cm[-1] == 0.0
    assert np.all(np.diff(column.full_depth_edges_cm) > 0.0)


def test_n3_column_accepts_an_explicit_lagrangian_mass_grid() -> None:
    edges = np.array([0.0, 0.01, 0.06, 0.2, 0.55, 1.0])
    column = build_zo_constrained_n3_column(
        5.0,
        2.0e8,
        3.0e-6,
        5,
        mass_fraction_edges=edges,
    )
    assert np.array_equal(column.half_mass_edges_g_cm2 / 5.0, edges)
    assert np.isclose(
        np.sum(column.full_cell_mass_g_cm2), 10.0, rtol=3.0e-16
    )
    assert np.array_equal(
        column.full_density_g_cm3, column.full_density_g_cm3[::-1]
    )


@pytest.mark.parametrize(
    "edges",
    (
        np.array([0.0, 0.1, 0.4, 1.0]),
        np.array([0.01, 0.1, 0.4, 0.7, 1.0]),
        np.array([0.0, 0.2, 0.2, 0.7, 1.0]),
    ),
)
def test_n3_column_rejects_invalid_explicit_mass_edges(edges: np.ndarray) -> None:
    with pytest.raises(PhysicalDomainError, match="mass_fraction_edges"):
        build_zo_constrained_n3_column(
            5.0,
            2.0e8,
            3.0e-6,
            4,
            mass_fraction_edges=edges,
        )


@pytest.mark.parametrize("law", ["uniform_specific", "alpha_support_pressure"])
def test_both_symmetric_dissipation_laws_preserve_each_face_flux(law: str) -> None:
    column = _column(9)
    profile = symmetric_dissipation_profile(column, 2.5e12, law)
    width = np.diff(column.full_depth_edges_cm)
    assert profile.relative_flux_residual < 4.0e-16
    assert np.isclose(
        np.sum(profile.full_heating_erg_s_cm3 * width),
        5.0e12,
        rtol=4.0e-16,
    )
    assert np.array_equal(
        profile.full_heating_erg_s_cm3,
        profile.full_heating_erg_s_cm3[::-1],
    )


def test_dissipation_controls_are_physically_distinct() -> None:
    column = _column(8)
    uniform = symmetric_dissipation_profile(column, 1.0e12, "uniform_specific")
    alpha = symmetric_dissipation_profile(
        column, 1.0e12, "alpha_support_pressure"
    )
    assert np.all(uniform.half_specific_heating_erg_s_g == 2.0e11)
    assert not np.allclose(
        alpha.half_specific_heating_erg_s_g,
        uniform.half_specific_heating_erg_s_g,
    )
    with pytest.raises(PhysicalDomainError, match="unknown"):
        symmetric_dissipation_profile(column, 1.0e12, "pretty_spectrum")  # type: ignore[arg-type]


def test_grey_seed_is_positive_symmetric_and_increases_toward_midplane() -> None:
    column = _column(7)
    seed = grey_surface_to_midplane_temperature_seed_k(column, 4.0e4)
    assert np.all(seed > 0.0)
    assert np.array_equal(seed, seed[::-1])
    assert np.all(np.diff(seed[: column.half_depth_points]) > 0.0)


def test_uniform_specific_grey_diffusion_recovers_analytic_flux_and_midplane_temperature() -> None:
    column = _column(16)
    effective_temperature = 4.0e4
    flux = 2.5e12
    dissipation = symmetric_dissipation_profile(
        column, flux, "uniform_specific"
    )
    opacity = fully_ionized_electron_scattering_opacity_cm2_g()
    diffusion = solve_grey_diffusion_column(
        column,
        dissipation,
        effective_temperature,
        grey_opacity_cm2_g=opacity,
    )
    expected_flux = flux * (
        1.0
        - column.half_mass_edges_g_cm2
        / column.midplane_column_mass_g_cm2
    )
    assert np.allclose(
        diffusion.half_flux_edges_erg_s_cm2,
        expected_flux,
        rtol=8.0e-16,
        atol=2.0e-3,
    )
    from eccentric_tde_observer.radiation import STEFAN_BOLTZMANN_ERG_S_CM2_K4

    expected_midplane_fourth = (
        0.5 * effective_temperature**4
        + 3.0
        * opacity
        * flux
        * column.midplane_column_mass_g_cm2
        / (8.0 * STEFAN_BOLTZMANN_ERG_S_CM2_K4)
    )
    assert np.isclose(
        diffusion.half_temperature_edges_k[-1] ** 4,
        expected_midplane_fourth,
        rtol=8.0e-16,
    )
    assert diffusion.midplane_flux_residual_over_one_face_flux < 2.0e-15
    assert np.array_equal(
        diffusion.full_temperature_k,
        diffusion.full_temperature_k[::-1],
    )


def test_grey_diffusion_support_audit_is_finite_for_both_dissipation_laws() -> None:
    column = _column(12)
    for law in ("uniform_specific", "alpha_support_pressure"):
        dissipation = symmetric_dissipation_profile(column, 2.5e12, law)
        diffusion = solve_grey_diffusion_column(column, dissipation, 4.0e4)
        audit = audit_grey_diffusion_support(column, diffusion)
        assert np.isfinite(audit.mass_weighted_relative_l1_pressure_residual)
        assert np.isfinite(audit.mass_weighted_relative_rms_pressure_residual)
        assert audit.deepest_cell_total_to_required_pressure > 0.0
        assert 0.0 < audit.deepest_cell_radiation_pressure_fraction < 1.0


def test_scale_height_diagnostic_matches_deep_pressure_without_hiding_profile_residual() -> None:
    energy = edge_resolved_milne_energy_grid_ev(0.1, 5000.0, 33)
    frequency = energy * EV_ERG / PLANCK_ERG_S
    diagnostic = diagnose_lte_rosseland_scale_height(
        585.5855633139084,
        1.3578775592291016e12,
        1.6777278269843894e-9,
        3.649609283469975e4,
        frequency,
        "uniform_specific",
        half_depth_points=16,
        diffusion_relative_tolerance=1.0e-6,
    )
    assert np.isclose(
        diagnostic.support_audit.deepest_cell_total_to_required_pressure,
        1.0,
        rtol=2.0e-8,
    )
    assert diagnostic.root_function_evaluations >= 3
    assert diagnostic.support_audit.mass_weighted_relative_l1_pressure_residual > 0.0
    assert diagnostic.matched_scale_height_cm == (
        diagnostic.reference_scale_height_cm
        * diagnostic.matched_to_reference_scale_height
    )


def test_scale_height_diagnostic_rejects_a_non_bracketing_interval() -> None:
    energy = edge_resolved_milne_energy_grid_ev(0.1, 5000.0, 33)
    frequency = energy * EV_ERG / PLANCK_ERG_S
    with pytest.raises(PhysicalDomainError, match="does not contain"):
        diagnose_lte_rosseland_scale_height(
            585.5855633139084,
            1.3578775592291016e12,
            1.6777278269843894e-9,
            3.649609283469975e4,
            frequency,
            "uniform_specific",
            half_depth_points=8,
            scale_height_factor_bracket=(1.0, 3.0),
            diffusion_relative_tolerance=1.0e-6,
        )


def test_pressure_audit_recovers_mirror_symmetry_for_an_lte_fixture() -> None:
    column = build_zo_constrained_n3_column(1.0e-4, 1.0e6, 1.0e-4, 2)
    temperature = np.full(column.full_depth_points, 4.0e4)
    state = lte_hydrogen_helium_ionization(
        column.full_density_g_cm3, temperature
    )
    energy = edge_resolved_milne_energy_grid_ev(0.1, 5000.0, 33)
    frequency = energy * EV_ERG / PLANCK_ERG_S
    mu, weight = gauss_legendre_half_range_mu_weights(2)
    boundary = planck_nu(frequency, 4.0e4)
    top = np.zeros((frequency.size, mu.size))
    bottom = np.zeros_like(top)
    top[:, mu > 0.0] = boundary[:, None]
    bottom[:, mu < 0.0] = boundary[:, None]
    slab = solve_emissive_ground_state_slab(
        frequency,
        column.full_depth_edges_cm,
        mu,
        weight,
        column.full_density_g_cm3,
        temperature,
        top,
        bottom,
        np.column_stack(
            (
                state.hydrogen_neutral_fraction,
                state.hydrogen_ionized_fraction,
            )
        ),
        np.column_stack(
            (
                state.helium_neutral_fraction,
                state.helium_singly_ionized_fraction,
                state.helium_doubly_ionized_fraction,
            )
        ),
        relaxation=1.0,
        tolerance=1.0e-10,
    )
    audit = audit_zo_n3_hydrostatic_pressure(column, slab)
    assert audit.maximum_temperature_mirror_residual == 0.0
    assert audit.maximum_density_mirror_residual == 0.0
    assert audit.relative_surface_flux_asymmetry < 2.0e-15
    assert np.all(audit.gas_pressure_erg_cm3 > 0.0)
    assert np.all(audit.radiation_pressure_erg_cm3 > 0.0)


def test_hydrostatic_module_uses_no_forbidden_numerical_repairs() -> None:
    source = Path("src/eccentric_tde_observer/hydrostatic_atmosphere.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("nan_to_num", "np.clip", "numpy.clip"):
        assert forbidden not in source
