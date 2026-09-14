from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.atmosphere import (
    BOLTZMANN_ERG_K,
    FREE_FREE_COEFFICIENT_CGS,
    PLANCK_ERG_S,
    PROTON_MASS_G,
    EffectiveOpticallyThinError,
    FullyIonizedHydrogenHeliumComposition,
    effective_optical_depth_to_midplane,
    free_free_absorption_opacity_cm2_g,
    solve_peak_thermalization_closure,
)
from eccentric_tde_observer.fixtures import constant_temperature_circular_annulus
from eccentric_tde_observer.radiation import (
    STEFAN_BOLTZMANN_ERG_S_CM2_K4,
    planck_nu,
)
from eccentric_tde_observer.source import PhysicalDomainError, ZOSourceGrid


def test_free_free_opacity_recovers_rayleigh_jeans_limit_for_pure_hydrogen() -> None:
    composition = FullyIonizedHydrogenHeliumComposition(
        hydrogen_mass_fraction=1.0,
        helium_mass_fraction=0.0,
        free_free_gaunt_factor=1.0,
    )
    density = 1.0e-10
    temperature = 1.0e7
    frequency = 1.0e14
    opacity = free_free_absorption_opacity_cm2_g(
        density, temperature, frequency, composition
    )
    rayleigh_jeans = (
        FREE_FREE_COEFFICIENT_CGS
        * PLANCK_ERG_S
        / BOLTZMANN_ERG_K
        * density
        / PROTON_MASS_G**2
        * temperature ** (-1.5)
        * frequency ** (-2.0)
    )
    assert np.isclose(opacity, rayleigh_jeans, rtol=2.5e-4)


def test_free_free_opacity_is_linear_in_density_and_has_vacuum_limit() -> None:
    first = free_free_absorption_opacity_cm2_g(1.0e-10, 5.0e4, 1.0e15)
    second = free_free_absorption_opacity_cm2_g(2.0e-10, 5.0e4, 1.0e15)
    vacuum = free_free_absorption_opacity_cm2_g(0.0, 5.0e4, 1.0e15)
    assert second == 2.0 * first
    assert vacuum == 0.0


def test_effective_optical_depth_decreases_with_frequency_and_converges() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=3, anomaly_points=8
    )
    frequency = np.array([5.0e14, 1.0e15, 2.0e15, 5.0e15])
    coarse = effective_optical_depth_to_midplane(
        source, frequency, vertical_points=129
    )
    fine = effective_optical_depth_to_midplane(
        source, frequency, vertical_points=257
    )
    assert np.all(np.diff(fine.midplane_effective_optical_depth, axis=-1) < 0.0)
    assert np.allclose(
        coarse.midplane_effective_optical_depth,
        fine.midplane_effective_optical_depth,
        rtol=2.0e-4,
    )


def test_peak_thermalization_closure_is_finite_and_reconstructs_gray_temperature() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=3, anomaly_points=8
    )
    closure = solve_peak_thermalization_closure(source, vertical_points=257)
    assert np.all(closure.midplane_effective_optical_depth >= 1.0)
    assert np.all(closure.spectral_hardening_factor >= 1.0)
    assert np.all(closure.thermalization_scaled_height > 0.0)
    expected_hardening = (
        0.75 * (closure.thermalization_scattering_optical_depth + 2.0 / 3.0)
    ) ** 0.25
    assert np.allclose(
        closure.spectral_hardening_factor, expected_hardening, rtol=3.0e-6
    )


def test_diluted_blackbody_preserves_local_bolometric_flux() -> None:
    frequency = np.geomspace(1.0e9, 1.0e20, 30001)[:, None]
    temperature = np.array([1.0e4, 3.0e4, 1.0e5])[None, :]
    hardening = np.array([1.2, 1.6, 2.0])[None, :]
    intensity = hardening ** (-4.0) * planck_nu(
        frequency, hardening * temperature
    )
    integrated_flux = np.pi * np.trapezoid(intensity, frequency[:, 0], axis=0)
    expected_flux = STEFAN_BOLTZMANN_ERG_S_CM2_K4 * temperature[0] ** 4
    assert np.allclose(integrated_flux, expected_flux, rtol=1.3e-7)


def test_peak_thermalization_rejects_effectively_thin_column() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=3, anomaly_points=8
    )
    thin_source = ZOSourceGrid(
        semimajor_axis_cm=source.semimajor_axis_cm,
        eccentric_anomaly_rad=source.eccentric_anomaly_rad,
        eccentricity=source.eccentricity,
        jacobian=source.jacobian,
        surface_density_g_cm2=np.full(source.shape, 1.0e-4),
        scale_height_cm=source.scale_height_cm,
        effective_temperature_k=source.effective_temperature_k,
        eccentricity_gradient_per_cm=source.eccentricity_gradient_per_cm,
        apsidal_gradient_per_cm=source.apsidal_gradient_per_cm,
    )
    with pytest.raises(EffectiveOpticallyThinError, match="no peak-frequency"):
        solve_peak_thermalization_closure(thin_source)


@pytest.mark.parametrize(
    ("density", "temperature", "frequency"),
    [(-1.0, 1.0e4, 1.0e15), (1.0, 0.0, 1.0e15), (1.0, 1.0e4, np.nan)],
)
def test_invalid_free_free_inputs_are_rejected(
    density: float, temperature: float, frequency: float
) -> None:
    with pytest.raises(PhysicalDomainError):
        free_free_absorption_opacity_cm2_g(density, temperature, frequency)


def test_atmosphere_source_does_not_use_forbidden_masking_helpers() -> None:
    from eccentric_tde_observer import atmosphere

    source_text = open(atmosphere.__file__, encoding="utf-8").read()
    assert "nan_to_num" not in source_text
    assert "np.clip" not in source_text
