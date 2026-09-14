from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.faceon import face_on_blackbody_sed
from eccentric_tde_observer.quadrature import pre_erratum_zo2020_area_weights
from eccentric_tde_observer.source import PhysicalDomainError
from eccentric_tde_observer.zo_reference import (
    ADIABATIC_INDEX,
    EQ55_TEMPERATURE_NORMALIZATION_K,
    SOLAR_MASS_G,
    SOLAR_RADIUS_CM,
    ZOConstantEParameters,
    build_zo_constant_e_reference_model,
    rescale_constant_e_circularization_efficiency,
    solve_constant_e_vertical_breathing,
    symmetric_pericentre_clustered_anomaly_grid,
)


def _parameters(eccentricity: float) -> ZOConstantEParameters:
    return ZOConstantEParameters(
        black_hole_mass_msun=1.0e6,
        stellar_mass_msun=1.0,
        stellar_radius_rsun=1.0,
        circularization_efficiency=1.0,
        outer_to_inner_semimajor_axis=2.0,
        eccentricity=eccentricity,
        opacity_cm2_g=0.34,
    )


def test_circular_eq35_solution_is_exactly_unity() -> None:
    solution = solve_constant_e_vertical_breathing(0.0, 64)
    assert np.array_equal(solution.dimensionless_height, np.ones(64))
    assert np.array_equal(
        solution.log_height_derivative_per_rad, np.zeros(64)
    )
    assert solution.apoapsis_boundary_residual == 0.0


def test_eccentric_eq35_solution_is_positive_even_and_periodic() -> None:
    solution = solve_constant_e_vertical_breathing(0.8, 256)
    height = solution.dimensionless_height
    derivative = solution.log_height_derivative_per_rad
    assert np.all(np.isfinite(height))
    assert np.all(height > 0.0)
    assert np.allclose(height[1:128], height[:128:-1], rtol=2.0e-14)
    assert np.allclose(derivative[1:128], -derivative[:128:-1], rtol=2.0e-14)
    assert abs(solution.apoapsis_boundary_residual) < 1.0e-8
    assert height[0] < height[128]


def test_eq35_solution_is_stable_to_tighter_ivp_tolerances() -> None:
    standard = solve_constant_e_vertical_breathing(
        0.8, 128, relative_tolerance=1.0e-9, absolute_tolerance=1.0e-11
    )
    tight = solve_constant_e_vertical_breathing(
        0.8, 128, relative_tolerance=2.0e-11, absolute_tolerance=2.0e-13
    )
    assert np.allclose(
        standard.dimensionless_height,
        tight.dimensionless_height,
        rtol=2.0e-8,
    )


def test_cluster_power_one_recovers_uniform_endpoint_free_grid() -> None:
    clustered = symmetric_pericentre_clustered_anomaly_grid(64, 1.0)
    uniform = np.linspace(0.0, 2.0 * np.pi, 64, endpoint=False)
    assert np.allclose(clustered, uniform, rtol=0.0, atol=9.0e-16)
    assert clustered[-1] < 2.0 * np.pi


def test_clustered_corrected_high_frequency_quadrature_converges() -> None:
    parameters = _parameters(0.8)
    frequency = np.array([5.0e14, 1.0e16, 5.0e16, 1.0e17])
    spectra = []
    for anomaly_points in (1024, 2048):
        model = build_zo_constant_e_reference_model(
            parameters,
            radial_points=65,
            anomaly_points=anomaly_points,
            anomaly_sampling="pericentre_clustered",
            pericentre_clustering_power=5.0,
        )
        spectra.append(
            face_on_blackbody_sed(
                model.source, frequency
            ).isotropic_equivalent_lnu_erg_s_hz
        )
    fractional_change = np.abs(spectra[1] / spectra[0] - 1.0)
    assert np.all(fractional_change < 3.0e-4)


def test_circular_reference_source_recovers_paper_scalings() -> None:
    parameters = _parameters(0.0)
    model = build_zo_constant_e_reference_model(
        parameters, radial_points=17, anomaly_points=64
    )
    source = model.source
    black_hole_mass_g = parameters.black_hole_mass_msun * SOLAR_MASS_G
    stellar_mass_g = parameters.stellar_mass_msun * SOLAR_MASS_G
    stellar_radius_cm = parameters.stellar_radius_rsun * SOLAR_RADIUS_CM
    tidal_radius = stellar_radius_cm * (
        black_hole_mass_g / stellar_mass_g
    ) ** (1.0 / 3.0)
    expected_inner = tidal_radius**2 / (2.0 * stellar_radius_cm) / 2.0
    expected_aspect = np.sqrt((ADIABATIC_INDEX - 1.0) / 2.0)
    expected_inner_sigma = stellar_mass_g / (4.0 * np.pi * expected_inner**2)
    expected_inner_temperature = (
        EQ55_TEMPERATURE_NORMALIZATION_K * 2.0 ** (3.0 / 8.0)
    )
    assert np.isclose(model.inner_semimajor_axis_cm, expected_inner, rtol=2.0e-15)
    assert np.isclose(
        model.circular_scale_height_aspect_ratio,
        expected_aspect,
        rtol=2.0e-15,
    )
    assert np.all(source.jacobian == 1.0)
    assert np.isclose(
        source.surface_density_g_cm2[0, 0], expected_inner_sigma, rtol=2.0e-15
    )
    assert np.isclose(
        source.scale_height_cm[0, 0] / source.semimajor_axis_cm[0],
        expected_aspect,
        rtol=2.0e-15,
    )
    assert np.isclose(
        source.effective_temperature_k[0, 0],
        expected_inner_temperature,
        rtol=2.0e-15,
    )
    assert np.allclose(
        source.surface_density_g_cm2[-1]
        / source.surface_density_g_cm2[0],
        parameters.outer_to_inner_semimajor_axis ** (-3.0),
        rtol=2.0e-15,
    )
    assert np.allclose(
        source.effective_temperature_k[-1]
        / source.effective_temperature_k[0],
        parameters.outer_to_inner_semimajor_axis ** (-0.5),
        rtol=2.0e-15,
    )


def test_pre_erratum_canonical_mass_measure_recovers_source_profile() -> None:
    parameters = _parameters(0.8)
    model = build_zo_constant_e_reference_model(
        parameters, radial_points=1025, anomaly_points=64
    )
    numerical_mass = float(
        np.sum(
            model.source.surface_density_g_cm2
            * pre_erratum_zo2020_area_weights(model.source),
            dtype=np.float64,
        )
    )
    expected_mass = (
        0.5
        * parameters.stellar_mass_msun
        * SOLAR_MASS_G
        * (1.0 - 1.0 / parameters.outer_to_inner_semimajor_axis)
    )
    assert np.isclose(numerical_mass, expected_mass, rtol=3.0e-7)


def test_constant_e_reference_runs_through_corrected_sed() -> None:
    model = build_zo_constant_e_reference_model(
        _parameters(0.8), radial_points=33, anomaly_points=128
    )
    frequency = np.geomspace(1.0e14, 1.0e18, 101)
    spectrum = face_on_blackbody_sed(model.source, frequency)
    assert np.all(np.isfinite(spectrum.isotropic_equivalent_lnu_erg_s_hz))
    assert np.all(spectrum.isotropic_equivalent_lnu_erg_s_hz > 0.0)
    assert np.array_equal(
        spectrum.isotropic_equivalent_lnu_erg_s_hz,
        2.0 * spectrum.intrinsic_two_sided_lnu_erg_s_hz,
    )


@pytest.mark.parametrize("new_efficiency", [0.1, 10.0])
def test_exact_circularization_efficiency_rescaling_matches_direct_build(
    new_efficiency: float,
) -> None:
    base = build_zo_constant_e_reference_model(
        _parameters(0.8), radial_points=17, anomaly_points=128
    )
    rescaled = rescale_constant_e_circularization_efficiency(
        base, new_efficiency
    )
    direct_parameters = ZOConstantEParameters(
        black_hole_mass_msun=1.0e6,
        stellar_mass_msun=1.0,
        stellar_radius_rsun=1.0,
        circularization_efficiency=new_efficiency,
        outer_to_inner_semimajor_axis=2.0,
        eccentricity=0.8,
        opacity_cm2_g=0.34,
    )
    direct = build_zo_constant_e_reference_model(
        direct_parameters, radial_points=17, anomaly_points=128
    )
    assert rescaled.breathing is base.breathing
    assert rescaled.parameters.circularization_efficiency == new_efficiency
    assert np.isclose(
        rescaled.inner_semimajor_axis_cm,
        direct.inner_semimajor_axis_cm,
        rtol=2.0e-15,
    )
    assert np.isclose(
        rescaled.circular_scale_height_aspect_ratio,
        direct.circular_scale_height_aspect_ratio,
        rtol=2.0e-15,
    )
    for rescaled_field, direct_field in (
        (rescaled.source.semimajor_axis_cm, direct.source.semimajor_axis_cm),
        (
            rescaled.source.surface_density_g_cm2,
            direct.source.surface_density_g_cm2,
        ),
        (rescaled.source.scale_height_cm, direct.source.scale_height_cm),
        (
            rescaled.source.effective_temperature_k,
            direct.source.effective_temperature_k,
        ),
    ):
        assert np.allclose(rescaled_field, direct_field, rtol=4.0e-15)


@pytest.mark.parametrize("bad_efficiency", [0.0, -1.0, np.nan, np.inf])
def test_invalid_circularization_efficiency_rescaling_is_rejected(
    bad_efficiency: float,
) -> None:
    base = build_zo_constant_e_reference_model(
        _parameters(0.4), radial_points=5, anomaly_points=32
    )
    with pytest.raises(PhysicalDomainError, match="finite and positive"):
        rescale_constant_e_circularization_efficiency(base, bad_efficiency)


@pytest.mark.parametrize("eccentricity", [-0.1, 0.991, np.nan])
def test_unvalidated_breathing_domain_is_rejected(eccentricity: float) -> None:
    with pytest.raises(PhysicalDomainError, match="0 <= eccentricity <= 0.99"):
        solve_constant_e_vertical_breathing(eccentricity, 64)
