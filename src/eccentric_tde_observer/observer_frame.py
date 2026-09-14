"""第五阶段：把参考距离处的 ``F_nu`` 映射到真实观察者的 ``F_lambda``。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.integrate import quad
from scipy.interpolate import CubicSpline

from .radiation import LIGHT_SPEED_CM_S
from .source import PhysicalDomainError


ANGSTROM_CM = 1.0e-8
MPC_CM = 3.0856775814913673e24
F98_MIN_WAVELENGTH_ANGSTROM = 1.0e3
F98_MAX_WAVELENGTH_ANGSTROM = 6.0e4


def _readonly(values: NDArray[np.float64]) -> NDArray[np.float64]:
    values.setflags(write=False)
    return values


def _positive_scalar(name: str, value: float) -> float:
    parsed = float(value)
    if not np.isfinite(parsed) or parsed <= 0.0:
        raise PhysicalDomainError(f"{name} must be finite and positive")
    return parsed


def _validate_fnu_spectrum(
    frequency_hz: ArrayLike,
    flux_density_erg_s_cm2_hz: ArrayLike,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    frequency = np.array(frequency_hz, dtype=np.float64, copy=True)
    flux = np.array(flux_density_erg_s_cm2_hz, dtype=np.float64, copy=True)
    if frequency.ndim != 1 or frequency.size < 2 or flux.shape != frequency.shape:
        raise PhysicalDomainError(
            "frequency and F_nu must be matching one-dimensional arrays"
        )
    if not np.all(np.isfinite(frequency)) or np.any(frequency <= 0.0):
        raise PhysicalDomainError("frequency must contain finite, positive values")
    if np.any(np.diff(frequency) <= 0.0):
        raise PhysicalDomainError("frequency must be strictly increasing")
    if not np.all(np.isfinite(flux)) or np.any(flux < 0.0):
        raise PhysicalDomainError("F_nu must be finite and non-negative")
    return frequency, flux


def flat_lcdm_luminosity_distance_cm(
    redshift: float,
    *,
    hubble_km_s_mpc: float = 70.0,
    omega_matter: float = 0.3,
) -> float:
    """Flat-LambdaCDM luminosity distance following the Hogg distance integral."""
    z = float(redshift)
    hubble = _positive_scalar("hubble_km_s_mpc", hubble_km_s_mpc)
    omega_m = float(omega_matter)
    if not np.isfinite(z) or z < 0.0:
        raise PhysicalDomainError("redshift must be finite and non-negative")
    if not np.isfinite(omega_m) or omega_m < 0.0 or omega_m > 1.0:
        raise PhysicalDomainError("omega_matter must satisfy 0 <= Omega_m <= 1")
    if z == 0.0:
        return 0.0

    def inverse_expansion(query_redshift: float) -> float:
        return 1.0 / np.sqrt(
            omega_m * (1.0 + query_redshift) ** 3 + (1.0 - omega_m)
        )

    integral, error = quad(
        inverse_expansion,
        0.0,
        z,
        epsabs=0.0,
        epsrel=2.0e-12,
        limit=100,
    )
    if not np.isfinite(integral) or not np.isfinite(error) or integral <= 0.0:
        raise ArithmeticError("luminosity-distance quadrature failed")
    light_speed_km_s = LIGHT_SPEED_CM_S / 1.0e5
    return float((1.0 + z) * light_speed_km_s * integral / hubble * MPC_CM)


def redshift_reference_fnu(
    emitted_frequency_hz: ArrayLike,
    reference_fnu_erg_s_cm2_hz: ArrayLike,
    *,
    reference_distance_cm: float,
    redshift: float,
    luminosity_distance_cm: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Map a directional reference ``F_nu`` to an observer at ``D_L``.

    The reference spectrum already contains inclination and transfer effects.
    It is scaled as a directional luminosity rather than made isotropic.
    """
    frequency, flux = _validate_fnu_spectrum(
        emitted_frequency_hz, reference_fnu_erg_s_cm2_hz
    )
    distance_reference = _positive_scalar(
        "reference_distance_cm", reference_distance_cm
    )
    distance_luminosity = _positive_scalar(
        "luminosity_distance_cm", luminosity_distance_cm
    )
    z = float(redshift)
    if not np.isfinite(z) or z < 0.0:
        raise PhysicalDomainError("redshift must be finite and non-negative")

    # 中文：Hogg Eq. 22 的 (1+z) 保证频率积分后回到 bolometric D_L 定义。
    observed_frequency = frequency / (1.0 + z)
    observed_flux = (
        (1.0 + z)
        * (distance_reference / distance_luminosity) ** 2
        * flux
    )
    if not np.all(np.isfinite(observed_flux)) or np.any(observed_flux < 0.0):
        raise ArithmeticError("redshifted F_nu became invalid")
    return _readonly(observed_frequency), _readonly(observed_flux)


def frequency_fnu_to_wavelength_flambda(
    frequency_hz: ArrayLike,
    flux_density_erg_s_cm2_hz: ArrayLike,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Convert ``F_nu`` to ``F_lambda`` per Angstrom on increasing wavelength."""
    frequency, flux = _validate_fnu_spectrum(
        frequency_hz, flux_density_erg_s_cm2_hz
    )
    wavelength_cm = LIGHT_SPEED_CM_S / frequency
    # 中文：先按每 cm 做 Jacobian，再乘 1e-8 变成每 Angstrom；最后反序。
    flux_lambda_per_angstrom = (
        flux * LIGHT_SPEED_CM_S / wavelength_cm**2 * ANGSTROM_CM
    )
    wavelength_angstrom = wavelength_cm / ANGSTROM_CM
    wavelength_angstrom = wavelength_angstrom[::-1].copy()
    flux_lambda_per_angstrom = flux_lambda_per_angstrom[::-1].copy()
    if np.any(np.diff(wavelength_angstrom) <= 0.0):
        raise ArithmeticError("wavelength conversion did not produce an increasing grid")
    if not np.all(np.isfinite(flux_lambda_per_angstrom)) or np.any(
        flux_lambda_per_angstrom < 0.0
    ):
        raise ArithmeticError("F_lambda conversion became invalid")
    return _readonly(wavelength_angstrom), _readonly(flux_lambda_per_angstrom)


def _fitzpatrick_uv_a_over_ebv(
    inverse_micron: NDArray[np.float64], r_v: float
) -> NDArray[np.float64]:
    c2 = -0.824 + 4.717 / r_v
    c1 = 2.030 - 3.007 * c2
    x0 = 4.596
    gamma = 0.99
    c3 = 3.23
    c4 = 0.41
    x = inverse_micron
    drude = x**2 / ((x**2 - x0**2) ** 2 + x**2 * gamma**2)
    far_uv = np.zeros_like(x)
    active = x > 5.9
    delta = x[active] - 5.9
    far_uv[active] = 0.5392 * delta**2 + 0.05644 * delta**3
    return r_v + c1 + c2 * x + c3 * drude + c4 * far_uv


def fitzpatrick_1998_a_over_ebv(
    wavelength_angstrom: ArrayLike,
    *,
    r_v: float = 3.1,
) -> NDArray[np.float64]:
    """Fitzpatrick (1998) mean Galactic ``A(lambda)/E(B-V)`` curve.

    The implementation follows Appendix A: the FM UV function below 2700 A
    and a natural cubic spline through the published IR/optical anchors above
    2700 A.  The paper states the curve is only approximate beyond 6 micron,
    so this function rejects values outside 1000--60000 A.
    """
    wavelength = np.array(wavelength_angstrom, dtype=np.float64, copy=True)
    rv = float(r_v)
    if wavelength.ndim == 0:
        wavelength = wavelength.reshape(1)
    if not np.all(np.isfinite(wavelength)) or np.any(wavelength <= 0.0):
        raise PhysicalDomainError("wavelength must contain finite, positive values")
    if np.any(wavelength < F98_MIN_WAVELENGTH_ANGSTROM) or np.any(
        wavelength > F98_MAX_WAVELENGTH_ANGSTROM
    ):
        raise PhysicalDomainError(
            "Fitzpatrick 1998 curve is restricted here to 1000--60000 Angstrom"
        )
    if not np.isfinite(rv) or rv < 2.0 or rv > 6.0:
        raise PhysicalDomainError("Fitzpatrick 1998 R_V must satisfy 2 <= R_V <= 6")

    inverse_micron = 1.0e4 / wavelength
    result = np.empty_like(wavelength)
    ultraviolet = wavelength <= 2700.0
    if np.any(ultraviolet):
        result[ultraviolet] = _fitzpatrick_uv_a_over_ebv(
            inverse_micron[ultraviolet], rv
        )

    if np.any(~ultraviolet):
        anchor_wavelength = np.array(
            [np.inf, 26500.0, 12200.0, 6000.0, 5470.0, 4670.0, 4110.0, 2700.0, 2600.0]
        )
        anchor_x = np.zeros(anchor_wavelength.size)
        anchor_x[1:] = 1.0e4 / anchor_wavelength[1:]
        anchor_value = np.empty(anchor_wavelength.size)
        anchor_value[0] = 0.0
        anchor_value[1] = 0.265 * rv / 3.1
        anchor_value[2] = 0.829 * rv / 3.1
        anchor_value[3] = -0.426 + 1.0044 * rv
        anchor_value[4] = -0.050 + 1.0016 * rv
        anchor_value[5] = 0.701 + 1.0016 * rv
        anchor_value[6] = 1.208 + 1.0032 * rv - 0.00033 * rv**2
        anchor_value[7:] = _fitzpatrick_uv_a_over_ebv(anchor_x[7:], rv)
        spline = CubicSpline(anchor_x, anchor_value, bc_type="natural")
        result[~ultraviolet] = spline(inverse_micron[~ultraviolet])

    if not np.all(np.isfinite(result)) or np.any(result < 0.0):
        raise ArithmeticError("Fitzpatrick extinction curve became invalid")
    return _readonly(result)


def attenuate_flux_by_extinction(
    flux: ArrayLike,
    extinction_magnitude: ArrayLike,
) -> NDArray[np.float64]:
    values, extinction = np.broadcast_arrays(
        np.asarray(flux, dtype=np.float64),
        np.asarray(extinction_magnitude, dtype=np.float64),
    )
    if not np.all(np.isfinite(values)) or np.any(values < 0.0):
        raise PhysicalDomainError("flux must be finite and non-negative")
    if not np.all(np.isfinite(extinction)) or np.any(extinction < 0.0):
        raise PhysicalDomainError("extinction magnitudes must be finite and non-negative")
    transmission = 10.0 ** (-0.4 * extinction)
    result = np.array(values * transmission, dtype=np.float64, copy=True)
    if not np.all(np.isfinite(result)) or np.any(result < 0.0):
        raise ArithmeticError("extinction attenuation became invalid")
    return _readonly(result)


@dataclass(frozen=True)
class ObserverFrameSpectrum:
    wavelength_obs_angstrom: NDArray[np.float64]
    frequency_obs_hz: NDArray[np.float64]
    frequency_emitted_hz: NDArray[np.float64]
    flux_nu_obs_erg_s_cm2_hz: NDArray[np.float64]
    flux_lambda_unextinguished_erg_s_cm2_angstrom: NDArray[np.float64]
    extinction_a_lambda_mag: NDArray[np.float64]
    flux_lambda_attenuated_erg_s_cm2_angstrom: NDArray[np.float64]
    redshift: float
    luminosity_distance_cm: float
    reference_distance_cm: float
    ebv_magnitude: float
    r_v: float


def reference_fnu_to_observer_flambda(
    emitted_frequency_hz: ArrayLike,
    reference_fnu_erg_s_cm2_hz: ArrayLike,
    *,
    reference_distance_cm: float,
    redshift: float,
    luminosity_distance_cm: float,
    wavelength_min_angstrom: float,
    wavelength_max_angstrom: float,
    ebv_magnitude: float = 0.0,
    r_v: float = 3.1,
) -> ObserverFrameSpectrum:
    """Construct a cropped observer-frame spectrum with optional MW extinction."""
    observed_frequency, observed_fnu = redshift_reference_fnu(
        emitted_frequency_hz,
        reference_fnu_erg_s_cm2_hz,
        reference_distance_cm=reference_distance_cm,
        redshift=redshift,
        luminosity_distance_cm=luminosity_distance_cm,
    )
    wavelength, flux_lambda = frequency_fnu_to_wavelength_flambda(
        observed_frequency, observed_fnu
    )
    lower = _positive_scalar("wavelength_min_angstrom", wavelength_min_angstrom)
    upper = _positive_scalar("wavelength_max_angstrom", wavelength_max_angstrom)
    if upper <= lower:
        raise PhysicalDomainError("wavelength bounds must be increasing")
    selected = (wavelength >= lower) & (wavelength <= upper)
    if np.count_nonzero(selected) < 2:
        raise PhysicalDomainError("wavelength window must contain at least two samples")
    selected_wavelength = np.array(wavelength[selected], copy=True)
    selected_flambda = np.array(flux_lambda[selected], copy=True)
    selected_frequency = LIGHT_SPEED_CM_S / (
        selected_wavelength * ANGSTROM_CM
    )
    selected_fnu = selected_flambda * (
        selected_wavelength * ANGSTROM_CM
    ) ** 2 / LIGHT_SPEED_CM_S / ANGSTROM_CM
    selected_emitted_frequency = (1.0 + float(redshift)) * selected_frequency

    ebv = float(ebv_magnitude)
    if not np.isfinite(ebv) or ebv < 0.0:
        raise PhysicalDomainError("E(B-V) must be finite and non-negative")
    rv = float(r_v)
    if ebv == 0.0:
        extinction = np.zeros_like(selected_wavelength)
    else:
        extinction = ebv * fitzpatrick_1998_a_over_ebv(
            selected_wavelength, r_v=rv
        )
    attenuated = attenuate_flux_by_extinction(selected_flambda, extinction)
    arrays = (
        selected_wavelength,
        selected_frequency,
        selected_emitted_frequency,
        selected_fnu,
        selected_flambda,
        np.array(extinction, copy=True),
    )
    for array in arrays:
        _readonly(array)
    return ObserverFrameSpectrum(
        wavelength_obs_angstrom=arrays[0],
        frequency_obs_hz=arrays[1],
        frequency_emitted_hz=arrays[2],
        flux_nu_obs_erg_s_cm2_hz=arrays[3],
        flux_lambda_unextinguished_erg_s_cm2_angstrom=arrays[4],
        extinction_a_lambda_mag=arrays[5],
        flux_lambda_attenuated_erg_s_cm2_angstrom=attenuated,
        redshift=float(redshift),
        luminosity_distance_cm=float(luminosity_distance_cm),
        reference_distance_cm=float(reference_distance_cm),
        ebv_magnitude=ebv,
        r_v=rv,
    )
