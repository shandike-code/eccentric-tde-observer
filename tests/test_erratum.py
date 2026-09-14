"""Zanazzi--Ogilvie 2022 Erratum 的正式科学门槛。"""

from __future__ import annotations

import numpy as np

from eccentric_tde_observer.faceon import (
    face_on_blackbody_sed,
    face_on_bolometric_luminosities,
)
from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.quadrature import periodic_weights, trapezoid_weights
from eccentric_tde_observer.radiation import PLANCK_ERG_S, planck_nu
from eccentric_tde_observer.validity import audit_local_vertical_domain
from eccentric_tde_observer.vertical import (
    GAUSSIAN_VERTICAL_PROFILE,
    RADIATION_PRESSURE_POLYTROPE_PROFILE,
)
from eccentric_tde_observer.zo_reference import (
    ZOConstantEParameters,
    build_zo_constant_e_reference_model,
    rescale_constant_e_circularization_efficiency,
)


def _parameters(eccentricity: float) -> ZOConstantEParameters:
    return ZOConstantEParameters(1.0e6, 1.0, 1.0, 1.0, 2.0, eccentricity, 0.34)


def _model(eccentricity: float, radial: int = 65, anomaly: int = 1024):
    return build_zo_constant_e_reference_model(
        _parameters(eccentricity),
        radial_points=radial,
        anomaly_points=anomaly,
        anomaly_sampling="pericentre_clustered",
        pericentre_clustering_power=5.0,
    )


def _independent_area_weights(source, *, corrected: bool) -> np.ndarray:
    """不调用正式面积 API，直接从 Erratum 公式独立构造权重。"""
    weights = (
        source.semimajor_axis_cm[:, None]
        * source.jacobian
        * trapezoid_weights(source.semimajor_axis_cm)[:, None]
        * periodic_weights(source.eccentric_anomaly_rad)[None, :]
    )
    if corrected:
        weights = weights * (
            1.0
            - source.eccentricity[:, None]
            * np.cos(source.eccentric_anomaly_rad)[None, :]
        )
    return weights


def _energy_kev_to_frequency_hz(energy_kev: float) -> float:
    return energy_kev * 1.0e3 * 1.602176634e-12 / PLANCK_ERG_S


def _band_integral(frequency, spectrum, lower_kev, upper_kev) -> float:
    inside = (frequency >= _energy_kev_to_frequency_hz(lower_kev)) & (
        frequency <= _energy_kev_to_frequency_hz(upper_kev)
    )
    return float(np.trapezoid(spectrum[inside], frequency[inside]))


def test_e08_erratum_band_ratios_are_independently_recovered() -> None:
    model = _model(0.8)
    bounds = np.array(
        [
            _energy_kev_to_frequency_hz(value)
            for value in (0.002, 0.1, 0.3, 10.0)
        ]
    )
    frequency = np.unique(
        np.concatenate((np.geomspace(1.0e14, 2.5e18, 801), bounds))
    )
    corrected_weight = _independent_area_weights(model.source, corrected=True)
    historical_weight = _independent_area_weights(model.source, corrected=False)
    corrected = np.empty_like(frequency)
    historical = np.empty_like(frequency)
    for index, nu in enumerate(frequency):
        intensity = planck_nu(nu, model.source.effective_temperature_k)
        corrected[index] = 4.0 * np.pi * np.sum(intensity * corrected_weight)
        historical[index] = 4.0 * np.pi * np.sum(intensity * historical_weight)

    corrected_uv = _band_integral(frequency, corrected, 0.002, 0.1)
    historical_uv = _band_integral(frequency, historical, 0.002, 0.1)
    corrected_x = _band_integral(frequency, corrected, 0.3, 10.0)
    historical_x = _band_integral(frequency, historical, 0.3, 10.0)
    assert np.isclose(corrected_uv / historical_uv, 0.238, rtol=3.0e-3)
    assert np.isclose(corrected_x / historical_x, 0.200, rtol=3.0e-3)
    assert np.isclose(corrected_x / corrected_uv, 4.62e-3, rtol=8.0e-3)


def test_corrected_strict_reference_bolometric_luminosity() -> None:
    model = rescale_constant_e_circularization_efficiency(_model(0.6), 0.01)
    independent_weight = _independent_area_weights(model.source, corrected=True)
    independent_liso = 4.0 * 5.670374419e-5 * np.sum(
        model.source.effective_temperature_k**4 * independent_weight
    )
    api_liso, intrinsic_two_sided = face_on_bolometric_luminosities(model.source)
    assert np.isclose(api_liso, independent_liso, rtol=3.0e-15)
    assert np.isclose(api_liso, 6.93e42, rtol=1.0e-3)
    assert api_liso == 2.0 * intrinsic_two_sided


def test_corrected_spectral_and_stefan_boltzmann_integrals_agree() -> None:
    model = rescale_constant_e_circularization_efficiency(
        _model(0.6, radial=33, anomaly=512), 0.01
    )
    frequency = np.geomspace(1.0e10, 1.0e20, 4001)
    spectral = face_on_blackbody_sed(model.source, frequency)
    spectral_liso = np.trapezoid(
        spectral.isotropic_equivalent_lnu_erg_s_hz, frequency
    )
    stefan_liso, _ = face_on_bolometric_luminosities(model.source)
    assert np.isclose(spectral_liso, stefan_liso, rtol=1.0e-5)


def test_e065_v001_passes_corrected_strict_domain_gate() -> None:
    model = rescale_constant_e_circularization_efficiency(_model(0.65), 0.01)
    for profile in (
        GAUSSIAN_VERTICAL_PROFILE,
        RADIATION_PRESSURE_POLYTROPE_PROFILE,
    ):
        photosphere = solve_gray_photosphere(
            model.source, model.parameters.opacity_cm2_g, 2.0 / 3.0, profile
        )
        audit = audit_local_vertical_domain(model.source, photosphere)
        assert audit.corrected_photosphere_over_radius_fraction_above[1] <= 0.01

