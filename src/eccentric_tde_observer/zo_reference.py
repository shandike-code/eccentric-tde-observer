"""Traceable constant-e source model from Zanazzi & Ogilvie (2020)."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from .source import PhysicalDomainError, ZOSourceGrid


SOLAR_MASS_G = 1.98847e33
SOLAR_RADIUS_CM = 6.957e10
ADIABATIC_INDEX = 4.0 / 3.0
EQ55_TEMPERATURE_NORMALIZATION_K = 2.65e4


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


class VerticalBreathingConvergenceError(RuntimeError):
    """Raised when the periodic ZO Eq. (35) shooting problem fails."""


@dataclass(frozen=True)
class ZOConstantEParameters:
    """Physical parameters for the paper's constant-e emission example."""

    black_hole_mass_msun: float
    stellar_mass_msun: float
    stellar_radius_rsun: float
    circularization_efficiency: float
    outer_to_inner_semimajor_axis: float
    eccentricity: float
    opacity_cm2_g: float
    apsidal_angle_rad: float = 0.0

    def __post_init__(self) -> None:
        for name in (
            "black_hole_mass_msun",
            "stellar_mass_msun",
            "stellar_radius_rsun",
            "circularization_efficiency",
            "outer_to_inner_semimajor_axis",
            "opacity_cm2_g",
        ):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value <= 0.0:
                raise PhysicalDomainError(f"{name} must be finite and positive")
            object.__setattr__(self, name, value)
        if self.outer_to_inner_semimajor_axis <= 1.0:
            raise PhysicalDomainError(
                "outer_to_inner_semimajor_axis must be greater than one"
            )
        eccentricity = float(self.eccentricity)
        if (
            not np.isfinite(eccentricity)
            or eccentricity < 0.0
            or eccentricity > 0.99
        ):
            raise PhysicalDomainError(
                "constant-e reference solver requires 0 <= eccentricity <= 0.99"
            )
        apsidal_angle = float(self.apsidal_angle_rad)
        if not np.isfinite(apsidal_angle):
            raise PhysicalDomainError("apsidal_angle_rad must be finite")
        object.__setattr__(self, "eccentricity", eccentricity)
        object.__setattr__(self, "apsidal_angle_rad", apsidal_angle)


@dataclass(frozen=True)
class VerticalBreathingSolution:
    """Positive, even, periodic solution of ZO Eq. (35)."""

    eccentric_anomaly_rad: NDArray[np.float64]
    dimensionless_height: NDArray[np.float64]
    log_height_derivative_per_rad: NDArray[np.float64]
    log_pericentre_height: float
    apoapsis_boundary_residual: float
    ivp_function_evaluations: int


@dataclass(frozen=True)
class ZOConstantEReferenceModel:
    """A source grid plus the intermediate quantities used to build it."""

    source: ZOSourceGrid
    parameters: ZOConstantEParameters
    breathing: VerticalBreathingSolution
    inner_semimajor_axis_cm: float
    circular_scale_height_aspect_ratio: float


def symmetric_pericentre_clustered_anomaly_grid(
    anomaly_points: int, clustering_power: float = 4.0
) -> NDArray[np.float64]:
    """Return an endpoint-free grid clustered symmetrically around ``E=0``.

    On the first half orbit ``E=pi*u**p``; the second half is its reflection.
    This is a numerical quadrature coordinate, not a change to the orbit.
    """
    if not isinstance(anomaly_points, (int, np.integer)) or isinstance(
        anomaly_points, (bool, np.bool_)
    ):
        raise PhysicalDomainError("anomaly_points must be an integer")
    anomaly_points = int(anomaly_points)
    if anomaly_points < 16 or anomaly_points % 2 != 0:
        raise PhysicalDomainError(
            "clustered anomaly grid requires an even anomaly_points >= 16"
        )
    clustering_power = float(clustering_power)
    if not np.isfinite(clustering_power) or clustering_power < 1.0:
        raise PhysicalDomainError(
            "clustering_power must be finite and at least one"
        )
    half_points = anomaly_points // 2
    first_half = np.pi * (
        np.arange(half_points + 1, dtype=np.float64) / half_points
    ) ** clustering_power
    second_half = 2.0 * np.pi - first_half[-2:0:-1]
    anomaly = np.concatenate((first_half, second_half))
    if anomaly.size != anomaly_points or np.any(np.diff(anomaly) <= 0.0):
        raise ArithmeticError("clustered anomaly grid construction failed")
    return _readonly(anomaly)


def solve_constant_e_vertical_breathing(
    eccentricity: float,
    anomaly_points: int | ArrayLike,
    *,
    relative_tolerance: float = 2.0e-11,
    absolute_tolerance: float = 2.0e-13,
) -> VerticalBreathingSolution:
    """Solve the even periodic Eq. (35) by shooting in ``q=ln(h)``.

    The paper fixes ``gamma=4/3``.  Solving for log-height makes positivity an
    exact variable transformation rather than a post-hoc clipping operation.
    """
    eccentricity = float(eccentricity)
    if (
        not np.isfinite(eccentricity)
        or eccentricity < 0.0
        or eccentricity > 0.99
    ):
        raise PhysicalDomainError(
            "vertical breathing solver requires 0 <= eccentricity <= 0.99"
        )
    if isinstance(anomaly_points, (int, np.integer)) and not isinstance(
        anomaly_points, (bool, np.bool_)
    ):
        anomaly_count = int(anomaly_points)
        if anomaly_count < 16:
            raise PhysicalDomainError("anomaly_points must be at least 16")
        anomaly = np.linspace(0.0, 2.0 * np.pi, anomaly_count, endpoint=False)
    else:
        anomaly = np.array(anomaly_points, dtype=np.float64, copy=True)
        if anomaly.ndim != 1 or anomaly.size < 16:
            raise PhysicalDomainError(
                "eccentric anomaly grid must be one-dimensional with at least 16 points"
            )
        if not np.all(np.isfinite(anomaly)) or np.any(np.diff(anomaly) <= 0.0):
            raise PhysicalDomainError(
                "eccentric anomaly grid must be finite and strictly increasing"
            )
        if anomaly[0] < 0.0 or anomaly[-1] >= 2.0 * np.pi:
            raise PhysicalDomainError(
                "eccentric anomaly grid must lie in [0, 2*pi)"
            )
        anomaly_count = int(anomaly.size)
    for name, value in (
        ("relative_tolerance", relative_tolerance),
        ("absolute_tolerance", absolute_tolerance),
    ):
        if not np.isfinite(value) or value <= 0.0:
            raise PhysicalDomainError(f"{name} must be finite and positive")

    if eccentricity == 0.0:
        height = np.ones(anomaly_count, dtype=np.float64)
        derivative = np.zeros(anomaly_count, dtype=np.float64)
        return VerticalBreathingSolution(
            eccentric_anomaly_rad=_readonly(anomaly),
            dimensionless_height=_readonly(height),
            log_height_derivative_per_rad=_readonly(derivative),
            log_pericentre_height=0.0,
            apoapsis_boundary_residual=0.0,
            ivp_function_evaluations=0,
        )

    gamma = ADIABATIC_INDEX
    jacobian = np.sqrt(1.0 - eccentricity**2)

    def differential_equation(
        eccentric_anomaly: float, state: NDArray[np.float64]
    ) -> tuple[float, float]:
        log_height, log_height_derivative = state
        orbital_factor = 1.0 - eccentricity * np.cos(eccentric_anomaly)
        second_derivative = (
            eccentricity
            * np.sin(eccentric_anomaly)
            / orbital_factor
            * log_height_derivative
            - log_height_derivative**2
            - 1.0 / orbital_factor
            + orbital_factor**2
            * jacobian ** (-(gamma - 1.0))
            * np.exp(-(gamma + 1.0) * log_height)
        )
        return log_height_derivative, second_derivative

    def integrate(log_pericentre_height: float, *, dense_output: bool):
        solution = solve_ivp(
            differential_equation,
            (0.0, np.pi),
            (log_pericentre_height, 0.0),
            method="DOP853",
            rtol=relative_tolerance,
            atol=absolute_tolerance,
            dense_output=dense_output,
            max_step=np.pi / 64.0,
        )
        if not solution.success:
            raise VerticalBreathingConvergenceError(solution.message)
        if not np.all(np.isfinite(solution.y)):
            raise VerticalBreathingConvergenceError(
                "Eq. (35) integration produced a non-finite state"
            )
        return solution

    upper_log_height = 0.0
    upper_residual = float(
        integrate(upper_log_height, dense_output=False).y[1, -1]
    )
    if not np.isfinite(upper_residual) or upper_residual <= 0.0:
        raise VerticalBreathingConvergenceError(
            "failed to establish the upper shooting bracket"
        )
    lower_log_height = -1.0
    while lower_log_height >= -64.0:
        lower_solution = integrate(lower_log_height, dense_output=False)
        lower_residual = float(lower_solution.y[1, -1])
        if not np.isfinite(lower_residual):
            raise VerticalBreathingConvergenceError(
                "shooting residual became non-finite"
            )
        if lower_residual < 0.0:
            break
        lower_log_height -= 1.0
    else:
        raise VerticalBreathingConvergenceError(
            "failed to bracket the positive periodic Eq. (35) solution"
        )

    def boundary_residual(log_pericentre_height: float) -> float:
        return float(
            integrate(log_pericentre_height, dense_output=False).y[1, -1]
        )

    log_pericentre_height = float(
        brentq(
            boundary_residual,
            lower_log_height,
            upper_log_height,
            xtol=1.0e-12,
            rtol=1.0e-14,
        )
    )
    solution = integrate(log_pericentre_height, dense_output=True)
    if solution.sol is None:
        raise VerticalBreathingConvergenceError(
            "Eq. (35) dense solution was not constructed"
        )
    reflected_anomaly = np.where(anomaly <= np.pi, anomaly, 2.0 * np.pi - anomaly)
    half_orbit_state = solution.sol(reflected_anomaly)
    log_height = half_orbit_state[0]
    derivative_sign = np.where(anomaly <= np.pi, 1.0, -1.0)
    log_height_derivative = derivative_sign * half_orbit_state[1]
    height = np.exp(log_height)
    if not np.all(np.isfinite(height)) or np.any(height <= 0.0):
        raise VerticalBreathingConvergenceError(
            "Eq. (35) solution produced an invalid positive height"
        )
    boundary_residual_value = float(solution.y[1, -1])
    if abs(boundary_residual_value) > 1.0e-8:
        raise VerticalBreathingConvergenceError(
            "Eq. (35) apoapsis boundary residual exceeds tolerance"
        )
    return VerticalBreathingSolution(
        eccentric_anomaly_rad=_readonly(anomaly),
        dimensionless_height=_readonly(height),
        log_height_derivative_per_rad=_readonly(log_height_derivative),
        log_pericentre_height=log_pericentre_height,
        apoapsis_boundary_residual=boundary_residual_value,
        ivp_function_evaluations=int(solution.nfev),
    )


def build_zo_constant_e_reference_model(
    parameters: ZOConstantEParameters,
    *,
    radial_points: int = 33,
    anomaly_points: int = 256,
    anomaly_sampling: str = "uniform",
    pericentre_clustering_power: float = 4.0,
) -> ZOConstantEReferenceModel:
    """Construct source fields using ZO Eqs. (10, 16, 18, 31, 35, 55)."""
    if not isinstance(parameters, ZOConstantEParameters):
        raise TypeError("parameters must be a ZOConstantEParameters instance")
    for name, value, minimum in (
        ("radial_points", radial_points, 2),
        ("anomaly_points", anomaly_points, 16),
    ):
        if not isinstance(value, (int, np.integer)) or isinstance(
            value, (bool, np.bool_)
        ):
            raise PhysicalDomainError(f"{name} must be an integer")
        if int(value) < minimum:
            raise PhysicalDomainError(f"{name} must be at least {minimum}")
    radial_points = int(radial_points)
    anomaly_points = int(anomaly_points)

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
    outer_semimajor_axis_cm = (
        parameters.outer_to_inner_semimajor_axis * inner_semimajor_axis_cm
    )
    semimajor_axis = np.linspace(
        inner_semimajor_axis_cm, outer_semimajor_axis_cm, radial_points
    )
    scaled_semimajor_axis = semimajor_axis / inner_semimajor_axis_cm

    if anomaly_sampling == "uniform":
        anomaly_grid: int | NDArray[np.float64] = anomaly_points
    elif anomaly_sampling == "pericentre_clustered":
        anomaly_grid = symmetric_pericentre_clustered_anomaly_grid(
            anomaly_points, pericentre_clustering_power
        )
    else:
        raise PhysicalDomainError(
            "anomaly_sampling must be 'uniform' or 'pericentre_clustered'"
        )
    breathing = solve_constant_e_vertical_breathing(
        parameters.eccentricity, anomaly_grid
    )
    jacobian_value = np.sqrt(1.0 - parameters.eccentricity**2)
    field_shape = (radial_points, anomaly_points)
    jacobian = np.full(field_shape, jacobian_value)
    circular_surface_density = (
        stellar_mass_g
        / (4.0 * np.pi * inner_semimajor_axis_cm**2)
        * scaled_semimajor_axis ** (-3.0)
    )
    surface_density = np.broadcast_to(
        (circular_surface_density / jacobian_value)[:, None], field_shape
    )
    circular_scale_height_aspect_ratio = np.sqrt(
        (ADIABATIC_INDEX - 1.0)
        * parameters.circularization_efficiency
        / (1.0 + parameters.circularization_efficiency)
    )
    scale_height = (
        semimajor_axis[:, None]
        * circular_scale_height_aspect_ratio
        * breathing.dimensionless_height[None, :]
    )
    temperature_normalization = (
        EQ55_TEMPERATURE_NORMALIZATION_K
        * parameters.stellar_mass_msun ** (1.0 / 3.0)
        / (
            (parameters.black_hole_mass_msun / 1.0e6) ** (1.0 / 12.0)
            * parameters.stellar_radius_rsun ** 0.5
        )
        * parameters.circularization_efficiency ** (1.0 / 8.0)
        * (1.0 + parameters.circularization_efficiency) ** (3.0 / 8.0)
        * (parameters.opacity_cm2_g / 0.34) ** (-0.25)
    )
    effective_temperature = (
        temperature_normalization
        * scaled_semimajor_axis[:, None] ** (-0.5)
        * jacobian_value ** (-1.0 / 12.0)
        * breathing.dimensionless_height[None, :] ** (-1.0 / 3.0)
    )
    source = ZOSourceGrid(
        semimajor_axis_cm=semimajor_axis,
        eccentric_anomaly_rad=breathing.eccentric_anomaly_rad,
        eccentricity=np.full(radial_points, parameters.eccentricity),
        jacobian=jacobian,
        surface_density_g_cm2=surface_density,
        scale_height_cm=scale_height,
        effective_temperature_k=effective_temperature,
        apsidal_angle_rad=parameters.apsidal_angle_rad,
        eccentricity_gradient_per_cm=np.zeros(radial_points),
        apsidal_gradient_per_cm=np.zeros(radial_points),
        label="ZO 2020 constant-e reference model",
        provenance=(
            "Zanazzi & Ogilvie 2020 Eqs. 10,16,18,31,35,55 [L]; "
            f"constant e, {anomaly_sampling} E grid, and numerical Eq.35 shooting [V]"
        ),
    )
    return ZOConstantEReferenceModel(
        source=source,
        parameters=parameters,
        breathing=breathing,
        inner_semimajor_axis_cm=float(inner_semimajor_axis_cm),
        circular_scale_height_aspect_ratio=float(
            circular_scale_height_aspect_ratio
        ),
    )


def rescale_constant_e_circularization_efficiency(
    model: ZOConstantEReferenceModel,
    circularization_efficiency: float,
) -> ZOConstantEReferenceModel:
    """Exactly rescale a constant-``e`` ZO model to a new ``mathcal V``.

    ZO Eqs. (10), (16), (18), and (55) give all required powers of
    ``mathcal V``.  Equation (35) is unchanged because its dimensionless
    breathing solution depends on eccentricity, not on the circularization
    efficiency.  Reusing it avoids solving the identical shooting problem at
    every point of an ``(e, mathcal V)`` audit.
    """
    if not isinstance(model, ZOConstantEReferenceModel):
        raise TypeError("model must be a ZOConstantEReferenceModel")
    new_efficiency = float(circularization_efficiency)
    if not np.isfinite(new_efficiency) or new_efficiency <= 0.0:
        raise PhysicalDomainError(
            "circularization_efficiency must be finite and positive"
        )

    old_efficiency = model.parameters.circularization_efficiency
    semimajor_axis_scale = (1.0 + old_efficiency) / (1.0 + new_efficiency)
    surface_density_scale = semimajor_axis_scale ** (-2.0)
    new_aspect_ratio = np.sqrt(
        (ADIABATIC_INDEX - 1.0)
        * new_efficiency
        / (1.0 + new_efficiency)
    )
    scale_height_scale = (
        semimajor_axis_scale
        * new_aspect_ratio
        / model.circular_scale_height_aspect_ratio
    )
    temperature_scale = (
        (new_efficiency / old_efficiency) ** (1.0 / 8.0)
        * ((1.0 + new_efficiency) / (1.0 + old_efficiency)) ** (3.0 / 8.0)
    )
    for name, value in (
        ("semimajor_axis_scale", semimajor_axis_scale),
        ("surface_density_scale", surface_density_scale),
        ("scale_height_scale", scale_height_scale),
        ("temperature_scale", temperature_scale),
    ):
        if not np.isfinite(value) or value <= 0.0:
            raise ArithmeticError(f"{name} is invalid during ZO rescaling")

    parameters = replace(
        model.parameters,
        circularization_efficiency=new_efficiency,
    )
    source = ZOSourceGrid(
        semimajor_axis_cm=(
            model.source.semimajor_axis_cm * semimajor_axis_scale
        ),
        eccentric_anomaly_rad=model.source.eccentric_anomaly_rad,
        eccentricity=model.source.eccentricity,
        jacobian=model.source.jacobian,
        surface_density_g_cm2=(
            model.source.surface_density_g_cm2 * surface_density_scale
        ),
        scale_height_cm=(
            model.source.scale_height_cm * scale_height_scale
        ),
        effective_temperature_k=(
            model.source.effective_temperature_k * temperature_scale
        ),
        apsidal_angle_rad=model.source.apsidal_angle_rad,
        eccentricity_gradient_per_cm=(
            model.source.eccentricity_gradient_per_cm
        ),
        apsidal_gradient_per_cm=model.source.apsidal_gradient_per_cm,
        label=model.source.label,
        provenance=(
            f"{model.source.provenance}; exact circularization-efficiency "
            "rescaling from ZO Eqs. 10,16,18,55 [L/V]"
        ),
    )
    return ZOConstantEReferenceModel(
        source=source,
        parameters=parameters,
        breathing=model.breathing,
        inner_semimajor_axis_cm=(
            model.inner_semimajor_axis_cm * semimajor_axis_scale
        ),
        circular_scale_height_aspect_ratio=float(new_aspect_ratio),
    )
