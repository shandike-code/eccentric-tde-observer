"""Corrected ZO 曲面上的条件性窄线响应与运动学诊断。

本模块只消费既有几何、可见性和弱场频移，不提供 NLTE 能级布居、线源函数、
自吸收或电子散射线翼。因此输出是运动学线核，不是真实 Halpha 光度预言。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.signal import find_peaks
from scipy.special import ndtr

from .adaptive import SourceSurfaceRayQuadrature
from .atmosphere import (
    FullyIonizedHydrogenHeliumComposition,
    SOLAR_FULLY_IONIZED_H_HE,
)
from .geometry import SurfaceMesh
from .radiation import (
    BOLTZMANN_ERG_K,
    LIGHT_SPEED_CM_S,
    STEFAN_BOLTZMANN_ERG_S_CM2_K4,
)
from .raytrace import _mesh_fingerprint
from .source import PhysicalDomainError, ZOSourceGrid
from .vertical import (
    RADIATION_PRESSURE_POLYTROPE_PROFILE,
    VerticalDensityProfile,
)


ANGSTROM_CM = 1.0e-8
HALPHA_REST_WAVELENGTH_ANGSTROM = 6562.8
PROTON_MASS_G = 1.67262192369e-24


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


def _positive_source_field(
    name: str, values: ArrayLike, source: ZOSourceGrid
) -> NDArray[np.float64]:
    field = np.array(values, dtype=np.float64, copy=True)
    if field.shape != source.shape:
        raise PhysicalDomainError(f"{name} must have shape {source.shape}")
    invalid = (~np.isfinite(field)) | (field <= 0.0)
    if np.any(invalid):
        index = tuple(int(i) for i in np.argwhere(invalid)[0])
        raise PhysicalDomainError(
            f"{name} must be finite and positive; failed at index {index}"
        )
    return field


def geometric_uniform_line_weight(source: ZOSourceGrid) -> NDArray[np.float64]:
    """Return the constant [A-control] line-intensity weight."""
    return _readonly(np.ones(source.shape, dtype=np.float64))


def zo_thermal_power_line_weight(source: ZOSourceGrid) -> NDArray[np.float64]:
    """Return sigma_SB*T_eff**4 as the [A-proxy] dissipation weight."""
    weight = STEFAN_BOLTZMANN_ERG_S_CM2_K4 * source.effective_temperature_k**4
    if not np.all(np.isfinite(weight)) or np.any(weight <= 0.0):
        raise ArithmeticError("ZO thermal-power proxy became invalid")
    return _readonly(weight)


def fully_ionized_emission_measure_line_weight(
    source: ZOSourceGrid,
    *,
    profile: VerticalDensityProfile = RADIATION_PRESSURE_POLYTROPE_PROFILE,
    composition: FullyIonizedHydrogenHeliumComposition = (
        SOLAR_FULLY_IONIZED_H_HE
    ),
    vertical_quadrature_points: int = 256,
) -> NDArray[np.float64]:
    """Return integral(n_e*n_i dz) in the fully ionized [A-proxy] limit.

    With rho=Sigma/H*f(z/H), integral(rho**2 dz) equals
    Sigma**2/H*integral(f**2 dzeta).  No recombination coefficient or level
    population is supplied, so this is only a normalized-shape proxy.
    """
    if (
        not isinstance(vertical_quadrature_points, (int, np.integer))
        or isinstance(vertical_quadrature_points, (bool, np.bool_))
        or int(vertical_quadrature_points) < 32
    ):
        raise PhysicalDomainError(
            "vertical_quadrature_points must be an integer >= 32"
        )
    points, weights = np.polynomial.legendre.leggauss(
        int(vertical_quadrature_points)
    )
    support = getattr(profile, "surface_scaled_height", None)
    lower, upper = (
        (-12.0, 12.0)
        if support is None
        else (-float(support), float(support))
    )
    zeta = 0.5 * (upper - lower) * points + 0.5 * (upper + lower)
    shape_integral = 0.5 * (upper - lower) * float(
        np.sum(weights * profile.density_shape(zeta) ** 2, dtype=np.float64)
    )
    if not np.isfinite(shape_integral) or shape_integral <= 0.0:
        raise ArithmeticError("vertical emission-measure integral is invalid")
    electron_per_mass = composition.electrons_per_baryon_mass / PROTON_MASS_G
    ion_per_mass = (
        composition.hydrogen_mass_fraction
        + 0.25 * composition.helium_mass_fraction
    ) / PROTON_MASS_G
    result = (
        source.surface_density_g_cm2**2
        / source.scale_height_cm
        * shape_integral
        * electron_per_mass
        * ion_per_mass
    )
    if not np.all(np.isfinite(result)) or np.any(result <= 0.0):
        raise ArithmeticError("fully ionized emission-measure proxy became invalid")
    return _readonly(result)


def hydrogen_thermal_velocity_dispersion_cm_s(
    gas_temperature_k: ArrayLike,
) -> NDArray[np.float64]:
    """Return one-dimensional hydrogen thermal sigma; T_gas is [A]."""
    temperature = np.asarray(gas_temperature_k, dtype=np.float64)
    invalid = (~np.isfinite(temperature)) | (temperature <= 0.0)
    if np.any(invalid):
        index = tuple(int(i) for i in np.argwhere(invalid)[0])
        raise PhysicalDomainError(
            f"gas temperature must be finite and positive at index {index}"
        )
    sigma = np.sqrt(BOLTZMANN_ERG_K * temperature / PROTON_MASS_G)
    if not np.all(np.isfinite(sigma)) or np.any(sigma <= 0.0):
        raise ArithmeticError("hydrogen thermal broadening became invalid")
    return sigma


@dataclass(frozen=True)
class LineProfile:
    velocity_cm_s: NDArray[np.float64]
    wavelength_angstrom: NDArray[np.float64]
    frequency_hz: NDArray[np.float64]
    flux_density_fnu_erg_s_cm2_hz: NDArray[np.float64]
    flux_density_flambda_erg_s_cm2_angstrom: NDArray[np.float64]
    normalized_flambda: NDArray[np.float64]
    normalized_flux_per_velocity: NDArray[np.float64]
    bin_integrated_flux_erg_s_cm2: NDArray[np.float64]
    direct_g4_integrated_flux_erg_s_cm2: float
    frequency_integrated_flux_erg_s_cm2: float
    energy_relative_residual: float
    rest_wavelength_angstrom: float
    broadening_label: str


@dataclass(frozen=True)
class LineDiagnostics:
    blue_peak_velocity_cm_s: float | None
    red_peak_velocity_cm_s: float | None
    peak_separation_cm_s: float | None
    red_to_blue_peak_ratio: float | None
    centroid_cm_s: float
    width_cm_s: float
    skewness: float
    trough_depth: float | None
    trough_velocity_cm_s: float | None
    is_double_peaked: bool
    classification_trough_threshold: float
    spectral_resolution_cm_s: float


def velocity_grid_cm_s(
    minimum_km_s: float = -80_000.0,
    maximum_km_s: float = 80_000.0,
    points: int = 3201,
) -> NDArray[np.float64]:
    lower = float(minimum_km_s) * 1.0e5
    upper = float(maximum_km_s) * 1.0e5
    if (
        not np.isfinite(lower)
        or not np.isfinite(upper)
        or lower >= upper
        or lower <= -LIGHT_SPEED_CM_S
    ):
        raise PhysicalDomainError("velocity limits are invalid")
    if (
        not isinstance(points, (int, np.integer))
        or isinstance(points, (bool, np.bool_))
        or int(points) < 5
    ):
        raise PhysicalDomainError("velocity points must be an integer >= 5")
    return _readonly(np.linspace(lower, upper, int(points), dtype=np.float64))


def _velocity_edges(velocity: NDArray[np.float64]) -> NDArray[np.float64]:
    if velocity.ndim != 1 or velocity.size < 5 or not np.all(np.isfinite(velocity)):
        raise PhysicalDomainError("velocity grid must be a finite 1D array")
    spacing = np.diff(velocity)
    if not np.allclose(spacing, spacing[0], rtol=2.0e-13, atol=0.0):
        raise PhysicalDomainError("velocity grid must be uniform")
    edges = np.empty(velocity.size + 1, dtype=np.float64)
    edges[1:-1] = 0.5 * (velocity[:-1] + velocity[1:])
    edges[0] = velocity[0] - 0.5 * spacing[0]
    edges[-1] = velocity[-1] + 0.5 * spacing[0]
    if edges[0] <= -LIGHT_SPEED_CM_S:
        raise PhysicalDomainError("velocity grid maps to a non-positive wavelength")
    return edges


def _validate_surface_quadrature(
    source: ZOSourceGrid,
    mesh: SurfaceMesh,
    quadrature: SourceSurfaceRayQuadrature,
) -> NDArray[np.float64]:
    if mesh.vertex_grid_shape != source.shape:
        raise PhysicalDomainError("mesh vertex grid does not match source")
    if quadrature.mesh_face_count != mesh.faces.shape[0]:
        raise PhysicalDomainError("visibility topology does not match mesh")
    if quadrature.mesh_fingerprint != _mesh_fingerprint(mesh):
        raise PhysicalDomainError("visibility geometry does not match mesh")
    area = quadrature.vertex_projected_area_weights_cm2
    if area.shape != (source.shape[0] * source.shape[1],):
        raise PhysicalDomainError("visibility weights do not match source")
    if not np.all(np.isfinite(area)) or np.any(area < 0.0):
        raise PhysicalDomainError("visibility weights are invalid")
    return area


def _deposit_local_gaussians(
    sample_velocity: NDArray[np.float64],
    sample_energy: NDArray[np.float64],
    sigma_velocity: NDArray[np.float64],
    velocity: NDArray[np.float64],
    edges: NDArray[np.float64],
) -> NDArray[np.float64]:
    spacing = velocity[1] - velocity[0]
    maximum_offset = int(np.ceil(8.0 * float(np.max(sigma_velocity)) / spacing))
    offsets = np.arange(-maximum_offset, maximum_offset + 1, dtype=np.int64)
    central = np.floor((sample_velocity - edges[0]) / spacing).astype(np.int64)
    bins = central[:, None] + offsets[None, :]
    if np.any((bins < 0) | (bins >= velocity.size)):
        raise PhysicalDomainError(
            "velocity grid lacks the eight-sigma local-broadening margin"
        )
    probability = ndtr(
        (edges[bins + 1] - sample_velocity[:, None]) / sigma_velocity[:, None]
    ) - ndtr(
        (edges[bins] - sample_velocity[:, None]) / sigma_velocity[:, None]
    )
    if not np.all(np.isfinite(probability)) or np.any(probability < 0.0):
        raise ArithmeticError("local Gaussian integration became invalid")
    deposited = np.bincount(
        bins.reshape(-1),
        weights=(sample_energy[:, None] * probability).reshape(-1),
        minlength=velocity.size,
    )
    return deposited.astype(np.float64, copy=False)


def observer_line_profile(
    source: ZOSourceGrid,
    mesh: SurfaceMesh,
    quadrature: SourceSurfaceRayQuadrature,
    frequency_shift_factor: ArrayLike,
    local_integrated_line_intensity: ArrayLike,
    velocity_cm_s: ArrayLike,
    *,
    observer_distance_cm: float,
    rest_wavelength_angstrom: float = HALPHA_REST_WAVELENGTH_ANGSTROM,
    local_sigma_velocity_cm_s: float | ArrayLike = 0.0,
) -> LineProfile:
    """Integrate a normalized narrow line with the required g**4 energy.

    The frequency-density transfer is g**3*I_nu(nu/g).  Integration over
    observed frequency contributes one additional g from the delta/Gaussian
    variable transformation, so each visible surface weight carries g**4.
    """
    area = _validate_surface_quadrature(source, mesh, quadrature)
    distance = float(observer_distance_cm)
    rest_wavelength = float(rest_wavelength_angstrom)
    if not np.isfinite(distance) or distance <= 0.0:
        raise PhysicalDomainError("observer_distance_cm must be finite and positive")
    if not np.isfinite(rest_wavelength) or rest_wavelength <= 0.0:
        raise PhysicalDomainError("rest wavelength must be finite and positive")
    velocity = np.array(velocity_cm_s, dtype=np.float64, copy=True)
    edges = _velocity_edges(velocity)
    shift = _positive_source_field(
        "frequency_shift_factor", frequency_shift_factor, source
    ).reshape(-1)
    intensity = _positive_source_field(
        "local_integrated_line_intensity",
        local_integrated_line_intensity,
        source,
    ).reshape(-1)
    active = area > 0.0
    if not np.any(active):
        raise PhysicalDomainError("visibility quadrature contains no emitting area")
    sample_velocity = LIGHT_SPEED_CM_S * (1.0 / shift[active] - 1.0)
    # delta 线从发射频率变换到观测频率时再带来一个 g，故总能流权重为 g**4。
    sample_energy = (
        shift[active] ** 4 * intensity[active] * area[active] / distance**2
    )
    if not np.all(np.isfinite(sample_energy)) or np.any(sample_energy <= 0.0):
        raise ArithmeticError("line energy weights became invalid")
    direct_energy = float(np.sum(sample_energy, dtype=np.float64))

    sigma_input = np.asarray(local_sigma_velocity_cm_s, dtype=np.float64)
    if sigma_input.ndim == 0:
        sigma_value = float(sigma_input)
        if not np.isfinite(sigma_value) or sigma_value < 0.0:
            raise PhysicalDomainError("local sigma must be finite and non-negative")
        indices = np.floor(
            (sample_velocity - edges[0]) / (velocity[1] - velocity[0])
        ).astype(np.int64)
        if np.any((indices < 0) | (indices >= velocity.size)):
            raise PhysicalDomainError(
                "velocity grid does not contain every shifted line sample"
            )
        delta_energy = np.bincount(
            indices, weights=sample_energy, minlength=velocity.size
        ).astype(np.float64, copy=False)
        if sigma_value == 0.0:
            bin_energy = delta_energy
            broadening_label = "delta-line numerical kernel"
        else:
            spacing = velocity[1] - velocity[0]
            half_width = int(np.ceil(8.0 * sigma_value / spacing))
            active_bins = np.flatnonzero(delta_energy > 0.0)
            if (
                active_bins[0] < half_width
                or active_bins[-1] >= velocity.size - half_width
            ):
                raise PhysicalDomainError(
                    "velocity grid lacks the eight-sigma broadening margin"
                )
            offsets = np.arange(-half_width, half_width + 1)
            kernel = ndtr((offsets + 0.5) * spacing / sigma_value) - ndtr(
                (offsets - 0.5) * spacing / sigma_value
            )
            bin_energy = np.convolve(delta_energy, kernel, mode="same")
            broadening_label = (
                f"uniform Gaussian sigma_v={sigma_value:.8g} cm/s"
            )
    else:
        if sigma_input.shape != source.shape:
            raise PhysicalDomainError("array local sigma must match source")
        invalid_sigma = (~np.isfinite(sigma_input)) | (sigma_input <= 0.0)
        if np.any(invalid_sigma):
            index = tuple(int(i) for i in np.argwhere(invalid_sigma)[0])
            raise PhysicalDomainError(
                f"local sigma must be finite and positive at index {index}"
            )
        # 局域热宽定义在发射系；映射到当前波长速度坐标后宽度为 sigma_em/g。
        bin_energy = _deposit_local_gaussians(
            sample_velocity,
            sample_energy,
            sigma_input.reshape(-1)[active] / shift[active],
            velocity,
            edges,
        )
        broadening_label = "emitter-frame local Gaussian sigma_v field"

    wavelength_edges_cm = (
        rest_wavelength * ANGSTROM_CM
        * (1.0 + edges / LIGHT_SPEED_CM_S)
    )
    frequency_edges = LIGHT_SPEED_CM_S / wavelength_edges_cm
    frequency_width = frequency_edges[:-1] - frequency_edges[1:]
    if np.any(frequency_width <= 0.0):
        raise ArithmeticError("frequency bins are not positive")
    wavelength_cm = (
        rest_wavelength * ANGSTROM_CM
        * (1.0 + velocity / LIGHT_SPEED_CM_S)
    )
    frequency = LIGHT_SPEED_CM_S / wavelength_cm
    fnu = bin_energy / frequency_width
    # 这里保留频率密度到波长密度的 Jacobian，不能只替换横轴。
    flambda_per_cm = fnu * LIGHT_SPEED_CM_S / wavelength_cm**2
    flambda_per_angstrom = flambda_per_cm * ANGSTROM_CM
    peak_flambda = float(np.max(flambda_per_angstrom))
    if not np.isfinite(peak_flambda) or peak_flambda <= 0.0:
        raise ArithmeticError("line profile has no positive finite peak")
    normalized_flambda = flambda_per_angstrom / peak_flambda
    flux_per_velocity = bin_energy / (edges[1] - edges[0])
    normalized_velocity = flux_per_velocity / np.max(flux_per_velocity)
    integrated = float(np.sum(bin_energy, dtype=np.float64))
    residual = integrated / direct_energy - 1.0
    arrays = (
        velocity,
        wavelength_cm / ANGSTROM_CM,
        frequency,
        fnu,
        flambda_per_angstrom,
        normalized_flambda,
        normalized_velocity,
        bin_energy,
    )
    return LineProfile(
        *(_readonly(array) for array in arrays),
        direct_g4_integrated_flux_erg_s_cm2=direct_energy,
        frequency_integrated_flux_erg_s_cm2=integrated,
        energy_relative_residual=residual,
        rest_wavelength_angstrom=rest_wavelength,
        broadening_label=broadening_label,
    )


def line_diagnostics(
    profile: LineProfile,
    *,
    classification_trough_threshold: float = 0.1,
) -> LineDiagnostics:
    """Measure peaks and moments with an explicit [A-classification] gate."""
    threshold = float(classification_trough_threshold)
    if not np.isfinite(threshold) or threshold < 0.0 or threshold >= 1.0:
        raise PhysicalDomainError(
            "classification_trough_threshold must lie in [0, 1)"
        )
    velocity = profile.velocity_cm_s
    shape = profile.normalized_flambda
    energy = profile.bin_integrated_flux_erg_s_cm2
    spacing = float(velocity[1] - velocity[0])
    total = float(np.sum(energy, dtype=np.float64))
    centroid = float(np.sum(energy * velocity, dtype=np.float64) / total)
    variance = float(
        np.sum(energy * (velocity - centroid) ** 2, dtype=np.float64) / total
    )
    width = float(np.sqrt(variance))
    skewness = (
        0.0
        if width == 0.0
        else float(
            np.sum(
                energy * ((velocity - centroid) / width) ** 3,
                dtype=np.float64,
            )
            / total
        )
    )
    peaks, _ = find_peaks(shape)
    blue_candidates = peaks[velocity[peaks] < 0.0]
    red_candidates = peaks[velocity[peaks] > 0.0]
    if blue_candidates.size == 0 or red_candidates.size == 0:
        return LineDiagnostics(
            None, None, None, None, centroid, width, skewness, None, None,
            False, threshold, spacing
        )
    blue = int(blue_candidates[np.argmax(shape[blue_candidates])])
    red = int(red_candidates[np.argmax(shape[red_candidates])])
    if blue >= red:
        raise ArithmeticError("blue and red peak ordering is invalid")
    trough = blue + int(np.argmin(shape[blue : red + 1]))
    lower = max(blue + 1, trough - 1)
    upper = min(red, trough + 2)
    trough_flux = float(np.median(shape[lower:upper]))
    weaker_peak = float(min(shape[blue], shape[red]))
    trough_depth = 1.0 - trough_flux / weaker_peak
    separation = float(velocity[red] - velocity[blue])
    ratio = float(shape[red] / shape[blue])
    double = bool(
        separation > spacing
        and trough > blue
        and trough < red
        and trough_depth >= threshold
    )
    return LineDiagnostics(
        float(velocity[blue]),
        float(velocity[red]),
        separation,
        ratio,
        centroid,
        width,
        skewness,
        trough_depth,
        float(velocity[trough]),
        double,
        threshold,
        spacing,
    )


def arcsine_ring_bin_probabilities(
    velocity_cm_s: ArrayLike,
    projected_orbital_speed_cm_s: float,
) -> NDArray[np.float64]:
    """Return the exact Newtonian thin-ring probability in finite bins."""
    velocity = np.asarray(velocity_cm_s, dtype=np.float64)
    edges = _velocity_edges(velocity)
    amplitude = float(projected_orbital_speed_cm_s)
    if not np.isfinite(amplitude) or amplitude <= 0.0:
        raise PhysicalDomainError("projected orbital speed must be positive")
    lower = np.maximum(edges[:-1], -amplitude)
    upper = np.minimum(edges[1:], amplitude)
    probability = np.zeros(velocity.size, dtype=np.float64)
    inside = upper > lower
    probability[inside] = (
        np.arcsin(upper[inside] / amplitude)
        - np.arcsin(lower[inside] / amplitude)
    ) / np.pi
    if not np.isclose(np.sum(probability), 1.0, rtol=2.0e-13, atol=0.0):
        raise PhysicalDomainError(
            "velocity grid does not contain the full analytic ring kernel"
        )
    return _readonly(probability)


def numerical_newtonian_ring_bin_probabilities(
    velocity_cm_s: ArrayLike,
    orbital_speed_cm_s: float,
    inclination_rad: float,
    *,
    azimuth_points: int = 1_000_000,
) -> NDArray[np.float64]:
    """Histogram the controlled ring v_los=v_K*sin(i)*cos(phi)."""
    velocity = np.asarray(velocity_cm_s, dtype=np.float64)
    edges = _velocity_edges(velocity)
    speed = float(orbital_speed_cm_s)
    inclination = float(inclination_rad)
    if not np.isfinite(speed) or speed <= 0.0:
        raise PhysicalDomainError("orbital speed must be finite and positive")
    if (
        not np.isfinite(inclination)
        or inclination < 0.0
        or inclination >= 0.5 * np.pi
    ):
        raise PhysicalDomainError("ring inclination must lie in [0, pi/2)")
    if (
        not isinstance(azimuth_points, (int, np.integer))
        or isinstance(azimuth_points, (bool, np.bool_))
        or int(azimuth_points) < 16
    ):
        raise PhysicalDomainError("azimuth_points must be an integer >= 16")
    phi = 2.0 * np.pi * np.arange(int(azimuth_points)) / int(azimuth_points)
    sample = speed * np.sin(inclination) * np.cos(phi)
    counts, _ = np.histogram(sample, bins=edges)
    if np.sum(counts) != int(azimuth_points):
        raise PhysicalDomainError("velocity grid does not contain the ring kernel")
    probability = counts.astype(np.float64) / int(azimuth_points)
    return _readonly(probability)
