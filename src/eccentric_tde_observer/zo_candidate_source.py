"""Build a profile-bound ZO source for an equation-self-consistent candidate.

This module deliberately lives beside, rather than inside, ``zo_reference``:
the published constant-e reference remains an unchanged historical control.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .apsidal_time_mapping import apsidal_mode_profile_fingerprint
from .nonlinear_hamiltonian import (
    UntwistedHamiltonianState,
    solve_zo_untwisted_hamiltonian,
    zo_untwisted_orbital_jacobian,
)
from .source import PhysicalDomainError, ZOSourceGrid
from .zo_reference import (
    ADIABATIC_INDEX,
    EQ55_TEMPERATURE_NORMALIZATION_K,
    SOLAR_MASS_G,
    SOLAR_RADIUS_CM,
)


_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def _readonly(values: ArrayLike) -> NDArray[np.float64]:
    array = np.array(values, dtype=np.float64, copy=True)
    array.setflags(write=False)
    return array


def _require_sha256(name: str, value: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise PhysicalDomainError(f"{name} must be a lowercase SHA-256 digest")
    return value


def candidate_dynamics_profile_fingerprint(
    scaled_semimajor_axis: ArrayLike,
    eccentricity: ArrayLike,
    orbital_nonlinearity: ArrayLike,
) -> str:
    """Return the exact binary64 fingerprint of one ``(a/e/q)`` profile.

    The existing Phase 5B5 fingerprint intentionally binds ``(a,e)``.  The
    extra digest here also protects ``q``, because ``q`` fixes ``f=e+a de/da``
    and therefore the local Jacobian and vertical breathing solution.
    """
    semimajor = np.asarray(scaled_semimajor_axis, dtype=np.float64)
    eccentricity_array = np.asarray(eccentricity, dtype=np.float64)
    nonlinearity = np.asarray(orbital_nonlinearity, dtype=np.float64)
    # 中文：先复用既有 e(a) 契约，再单独验证决定 j 与 H 的 q(a)。
    apsidal_mode_profile_fingerprint(semimajor, eccentricity_array)
    if (
        nonlinearity.ndim != 1
        or nonlinearity.shape != semimajor.shape
        or np.any(~np.isfinite(nonlinearity))
        or np.any(np.abs(nonlinearity) >= 1.0)
    ):
        raise PhysicalDomainError(
            "candidate orbital nonlinearity must be finite with |q| < 1"
        )
    digest = hashlib.sha256()
    digest.update(np.asarray([semimajor.size], dtype="<i8").tobytes())
    for values in (semimajor, eccentricity_array, nonlinearity):
        digest.update(np.asarray(values, dtype="<f8").tobytes())
    return digest.hexdigest()


@dataclass(frozen=True)
class ZOCandidateSourceParameters:
    """Physical normalization shared with the ZO source equations."""

    black_hole_mass_msun: float
    stellar_mass_msun: float
    stellar_radius_rsun: float
    circularization_efficiency: float
    opacity_cm2_g: float
    apsidal_angle_rad: float = 0.0

    def __post_init__(self) -> None:
        for name in (
            "black_hole_mass_msun",
            "stellar_mass_msun",
            "stellar_radius_rsun",
            "circularization_efficiency",
            "opacity_cm2_g",
        ):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value <= 0.0:
                raise PhysicalDomainError(f"{name} must be finite and positive")
            object.__setattr__(self, name, value)
        apsidal_angle = float(self.apsidal_angle_rad)
        if not np.isfinite(apsidal_angle):
            raise PhysicalDomainError("apsidal_angle_rad must be finite")
        object.__setattr__(self, "apsidal_angle_rad", apsidal_angle)


@dataclass(frozen=True)
class ZOEquationSelfConsistentCandidateSource:
    """A profile-bound candidate source, never a published benchmark."""

    source: ZOSourceGrid
    parameters: ZOCandidateSourceParameters
    scaled_semimajor_axis: NDArray[np.float64]
    eccentricity_plus_gradient: NDArray[np.float64]
    orbital_nonlinearity: NDArray[np.float64]
    vertical_states: tuple[UntwistedHamiltonianState, ...]
    inner_semimajor_axis_cm: float
    circular_scale_height_aspect_ratio: float
    eccentricity_profile_fingerprint: str
    dynamics_profile_fingerprint: str
    classification: str = "[A-candidate]+[V]+[O]"
    published_benchmark: bool = False


def build_zo_equation_self_consistent_candidate_source(
    parameters: ZOCandidateSourceParameters,
    *,
    scaled_semimajor_axis: ArrayLike,
    eccentricity: ArrayLike,
    orbital_nonlinearity: ArrayLike,
    expected_eccentricity_profile_fingerprint: str,
    expected_dynamics_profile_fingerprint: str,
    anomaly_points: int = 256,
    candidate_label: str = "equation-self-consistent ZO candidate",
) -> ZOEquationSelfConsistentCandidateSource:
    """Construct ZO Eqs. (10,16,18,31,35,55) on one frozen mode profile.

    No interpolation or numerical differentiation is performed.  The radial
    source grid is exactly the supplied mode grid, and ``f=e+a de/da`` is
    recovered algebraically from the supplied ZO nonlinearity ``q``.
    """
    if not isinstance(parameters, ZOCandidateSourceParameters):
        raise TypeError("parameters must be a ZOCandidateSourceParameters instance")
    if (
        not isinstance(anomaly_points, (int, np.integer))
        or isinstance(anomaly_points, (bool, np.bool_))
        or int(anomaly_points) < 16
        or int(anomaly_points) % 2 != 0
    ):
        raise PhysicalDomainError(
            "anomaly_points must be an even integer at least 16"
        )
    if not isinstance(candidate_label, str) or not candidate_label.strip():
        raise PhysicalDomainError("candidate_label must be a non-empty string")
    expected_e_fingerprint = _require_sha256(
        "expected_eccentricity_profile_fingerprint",
        expected_eccentricity_profile_fingerprint,
    )
    expected_dynamics_fingerprint = _require_sha256(
        "expected_dynamics_profile_fingerprint",
        expected_dynamics_profile_fingerprint,
    )

    scaled_a = np.asarray(scaled_semimajor_axis, dtype=np.float64)
    eccentricity_array = np.asarray(eccentricity, dtype=np.float64)
    nonlinearity = np.asarray(orbital_nonlinearity, dtype=np.float64)
    e_fingerprint = apsidal_mode_profile_fingerprint(scaled_a, eccentricity_array)
    if e_fingerprint != expected_e_fingerprint:
        raise PhysicalDomainError(
            "candidate eccentricity profile does not match its frozen fingerprint"
        )
    dynamics_fingerprint = candidate_dynamics_profile_fingerprint(
        scaled_a, eccentricity_array, nonlinearity
    )
    if dynamics_fingerprint != expected_dynamics_fingerprint:
        raise PhysicalDomainError(
            "candidate dynamics profile does not match its frozen fingerprint"
        )
    if scaled_a[0] != 1.0:
        raise PhysicalDomainError(
            "candidate scaled semimajor-axis grid must start exactly at a/a_in=1"
        )

    # 中文：由 q=(f-e)/(1-ef) 精确反解 f，避免另设数值微分处方。
    denominator = 1.0 + nonlinearity * eccentricity_array
    if np.any(denominator <= 0.0):
        raise PhysicalDomainError("candidate q-to-f transform has invalid denominator")
    eccentricity_plus_gradient = (
        nonlinearity + eccentricity_array
    ) / denominator
    if np.any(~np.isfinite(eccentricity_plus_gradient)) or np.any(
        np.abs(eccentricity_plus_gradient) >= 1.0
    ):
        raise PhysicalDomainError(
            "candidate nested-orbit condition requires |e+a*de/da| < 1"
        )

    states = tuple(
        solve_zo_untwisted_hamiltonian(
            float(local_e),
            float(local_f),
            anomaly_points=int(anomaly_points),
        )
        for local_e, local_f in zip(
            eccentricity_array, eccentricity_plus_gradient, strict=True
        )
    )
    anomaly = states[0].eccentric_anomaly_rad
    if any(not np.array_equal(state.eccentric_anomaly_rad, anomaly) for state in states):
        raise RuntimeError("local vertical states do not share one anomaly grid")
    height = np.stack([state.dimensionless_height for state in states])
    jacobian = np.stack(
        [
            zo_untwisted_orbital_jacobian(local_e, local_f, anomaly)
            for local_e, local_f in zip(
                eccentricity_array, eccentricity_plus_gradient, strict=True
            )
        ]
    )

    black_hole_mass_g = parameters.black_hole_mass_msun * SOLAR_MASS_G
    stellar_mass_g = parameters.stellar_mass_msun * SOLAR_MASS_G
    stellar_radius_cm = parameters.stellar_radius_rsun * SOLAR_RADIUS_CM
    tidal_radius_cm = stellar_radius_cm * (
        black_hole_mass_g / stellar_mass_g
    ) ** (1.0 / 3.0)
    inner_semimajor_axis_cm = (
        tidal_radius_cm**2
        / (2.0 * stellar_radius_cm)
        / (1.0 + parameters.circularization_efficiency)
    )
    semimajor_axis_cm = scaled_a * inner_semimajor_axis_cm
    circular_surface_density = (
        stellar_mass_g
        / (4.0 * np.pi * inner_semimajor_axis_cm**2)
        * scaled_a ** (-3.0)
    )
    surface_density = circular_surface_density[:, None] / jacobian
    circular_aspect_ratio = np.sqrt(
        (ADIABATIC_INDEX - 1.0)
        * parameters.circularization_efficiency
        / (1.0 + parameters.circularization_efficiency)
    )
    scale_height = (
        semimajor_axis_cm[:, None] * circular_aspect_ratio * height
    )
    temperature_normalization = (
        EQ55_TEMPERATURE_NORMALIZATION_K
        * parameters.stellar_mass_msun ** (1.0 / 3.0)
        / (
            (parameters.black_hole_mass_msun / 1.0e6) ** (1.0 / 12.0)
            * parameters.stellar_radius_rsun**0.5
        )
        * parameters.circularization_efficiency ** (1.0 / 8.0)
        * (1.0 + parameters.circularization_efficiency) ** (3.0 / 8.0)
        * (parameters.opacity_cm2_g / 0.34) ** (-0.25)
    )
    # 中文：沿用 ZO Eq. (55)，不改写候选动力学给出的 j(a,E) 与 h(a,E)。
    effective_temperature = (
        temperature_normalization
        * scaled_a[:, None] ** (-0.5)
        * jacobian ** (-1.0 / 12.0)
        * height ** (-1.0 / 3.0)
    )
    eccentricity_gradient = (
        eccentricity_plus_gradient - eccentricity_array
    ) / semimajor_axis_cm
    source = ZOSourceGrid(
        semimajor_axis_cm=semimajor_axis_cm,
        eccentric_anomaly_rad=anomaly,
        eccentricity=eccentricity_array,
        jacobian=jacobian,
        surface_density_g_cm2=surface_density,
        scale_height_cm=scale_height,
        effective_temperature_k=effective_temperature,
        apsidal_angle_rad=parameters.apsidal_angle_rad,
        eccentricity_gradient_per_cm=eccentricity_gradient,
        apsidal_gradient_per_cm=np.zeros_like(eccentricity_gradient),
        label=f"[A-candidate] {candidate_label}",
        provenance=(
            "ZO 2020 Eqs. 10,16,18,31,35,55 [L]; exact (a,e) and "
            "(a,e,q) binary64 fingerprints, q-to-f transform, and local "
            "Hamiltonian shooting [V]; equation-self-consistent candidate "
            "authorized as [A-candidate], not a published benchmark [O]"
        ),
    )
    return ZOEquationSelfConsistentCandidateSource(
        source=source,
        parameters=parameters,
        scaled_semimajor_axis=_readonly(scaled_a),
        eccentricity_plus_gradient=_readonly(eccentricity_plus_gradient),
        orbital_nonlinearity=_readonly(nonlinearity),
        vertical_states=states,
        inner_semimajor_axis_cm=float(inner_semimajor_axis_cm),
        circular_scale_height_aspect_ratio=float(circular_aspect_ratio),
        eccentricity_profile_fingerprint=e_fingerprint,
        dynamics_profile_fingerprint=dynamics_fingerprint,
    )
