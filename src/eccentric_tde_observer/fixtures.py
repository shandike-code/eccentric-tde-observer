"""Analytic fixtures for verification; these are not TDE predictions."""

from __future__ import annotations

import numpy as np

from .source import ZOSourceGrid


def constant_temperature_circular_annulus(
    inner_radius_cm: float,
    outer_radius_cm: float,
    temperature_k: float,
    radial_points: int = 65,
    anomaly_points: int = 128,
) -> ZOSourceGrid:
    """Return an ``e=0, j=1`` annulus with a known analytic spectrum."""
    a = np.linspace(inner_radius_cm, outer_radius_cm, radial_points)
    anomaly = np.linspace(0.0, 2.0 * np.pi, anomaly_points, endpoint=False)
    shape = (radial_points, anomaly_points)
    height = 0.01 * np.broadcast_to(a[:, None], shape)
    return ZOSourceGrid(
        semimajor_axis_cm=a,
        eccentric_anomaly_rad=anomaly,
        eccentricity=np.zeros(radial_points),
        jacobian=np.ones(shape),
        surface_density_g_cm2=np.full(shape, 1.0e4),
        scale_height_cm=height,
        effective_temperature_k=np.full(shape, temperature_k),
        apsidal_angle_rad=0.0,
        eccentricity_gradient_per_cm=np.zeros(radial_points),
        label="constant-temperature circular annulus",
        provenance="analytic verification fixture [A/V]",
    )


def power_law_temperature_circular_annulus(
    inner_radius_cm: float,
    outer_radius_cm: float,
    inner_temperature_k: float,
    temperature_index: float = 0.75,
    radial_points: int = 65,
    anomaly_points: int = 64,
) -> ZOSourceGrid:
    """Return a circular annulus with ``T_eff = T_in*(a/a_in)^(-p)``."""
    a = np.linspace(inner_radius_cm, outer_radius_cm, radial_points)
    anomaly = np.linspace(0.0, 2.0 * np.pi, anomaly_points, endpoint=False)
    shape = (radial_points, anomaly_points)
    radial_temperature = inner_temperature_k * (
        a / inner_radius_cm
    ) ** (-temperature_index)
    return ZOSourceGrid(
        semimajor_axis_cm=a,
        eccentric_anomaly_rad=anomaly,
        eccentricity=np.zeros(radial_points),
        jacobian=np.ones(shape),
        surface_density_g_cm2=np.full(shape, 1.0e4),
        scale_height_cm=0.01 * np.broadcast_to(a[:, None], shape),
        effective_temperature_k=np.broadcast_to(radial_temperature[:, None], shape),
        apsidal_angle_rad=0.0,
        eccentricity_gradient_per_cm=np.zeros(radial_points),
        label="power-law-temperature circular annulus",
        provenance="analytic convergence fixture [A/V]",
    )


def constant_temperature_eccentric_annulus(
    inner_semimajor_axis_cm: float,
    outer_semimajor_axis_cm: float,
    eccentricity: float,
    temperature_k: float,
    radial_points: int = 33,
    anomaly_points: int = 128,
    apsidal_angle_rad: float = 0.0,
) -> ZOSourceGrid:
    """Return aligned, similar ellipses with constant ``e`` and temperature.

    For ``de/da = dvarpi/da = 0``, the ZO canonical Jacobian is
    ``j = sqrt(1-e^2)``.  The Cartesian ``(a, E)`` area additionally contains
    ``1-e*cos(E)``.
    """
    if not np.isfinite(eccentricity) or eccentricity < 0.0 or eccentricity >= 1.0:
        raise ValueError("eccentricity must satisfy 0 <= e < 1")
    a = np.linspace(
        inner_semimajor_axis_cm, outer_semimajor_axis_cm, radial_points
    )
    anomaly = np.linspace(0.0, 2.0 * np.pi, anomaly_points, endpoint=False)
    shape = (radial_points, anomaly_points)
    radius = a[:, None] * (
        1.0 - eccentricity * np.cos(anomaly)[None, :]
    )
    return ZOSourceGrid(
        semimajor_axis_cm=a,
        eccentric_anomaly_rad=anomaly,
        eccentricity=np.full(radial_points, eccentricity),
        jacobian=np.full(shape, np.sqrt(1.0 - eccentricity**2)),
        surface_density_g_cm2=np.full(shape, 1.0e4),
        scale_height_cm=0.01 * radius,
        effective_temperature_k=np.full(shape, temperature_k),
        apsidal_angle_rad=apsidal_angle_rad,
        eccentricity_gradient_per_cm=np.zeros(radial_points),
        apsidal_gradient_per_cm=np.zeros(radial_points),
        label="constant-temperature eccentric annulus",
        provenance="analytic Cartesian-geometry fixture [A/V]",
    )


def radius_power_law_temperature_eccentric_annulus(
    inner_semimajor_axis_cm: float,
    outer_semimajor_axis_cm: float,
    eccentricity: float,
    inner_pericentre_temperature_k: float,
    temperature_index: float = 0.75,
    radial_points: int = 33,
    anomaly_points: int = 256,
    apsidal_angle_rad: float = 0.0,
) -> ZOSourceGrid:
    """Return an eccentric spectral stress-test fixture.

    The imposed ``T_eff proportional to r**(-temperature_index)`` law is not a
    Zanazzi--Ogilvie prediction.  It exists only to verify that occulting a hot
    or cool part of a non-axisymmetric surface reshapes the ray-traced SED.
    """
    base = constant_temperature_eccentric_annulus(
        inner_semimajor_axis_cm,
        outer_semimajor_axis_cm,
        eccentricity,
        inner_pericentre_temperature_k,
        radial_points=radial_points,
        anomaly_points=anomaly_points,
        apsidal_angle_rad=apsidal_angle_rad,
    )
    radius = base.semimajor_axis_cm[:, None] * (
        1.0
        - base.eccentricity[:, None]
        * np.cos(base.eccentric_anomaly_rad)[None, :]
    )
    reference_radius = inner_semimajor_axis_cm * (1.0 - eccentricity)
    temperature = inner_pericentre_temperature_k * (
        radius / reference_radius
    ) ** (-temperature_index)
    return ZOSourceGrid(
        semimajor_axis_cm=base.semimajor_axis_cm,
        eccentric_anomaly_rad=base.eccentric_anomaly_rad,
        eccentricity=base.eccentricity,
        jacobian=base.jacobian,
        surface_density_g_cm2=base.surface_density_g_cm2,
        scale_height_cm=base.scale_height_cm,
        effective_temperature_k=temperature,
        apsidal_angle_rad=base.apsidal_angle_rad,
        eccentricity_gradient_per_cm=base.eccentricity_gradient_per_cm,
        apsidal_gradient_per_cm=base.apsidal_gradient_per_cm,
        label="radius-power-law-temperature eccentric annulus",
        provenance="spectral ray-tracing stress-test fixture [A/V], not ZO output",
    )
