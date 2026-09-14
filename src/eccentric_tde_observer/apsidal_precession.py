"""ZO/OL 线性三维偏心模与拱点进动尺度。

本模块只求 Ogilvie--Lynch 线性三维自由边界本征问题，并使用
Zanazzi--Ogilvie 的参考圆盘质量、压力和 GR 项。它不会重定义现有 ZO
源场，也不会把线性本征函数冒充高偏心非线性解。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.linalg import eigh

from .source import PhysicalDomainError
from .zo_reference import SOLAR_MASS_G, SOLAR_RADIUS_CM, ZOConstantEParameters


GRAVITATIONAL_CONSTANT_CGS = 6.67430e-8
LIGHT_SPEED_CM_S = 2.99792458e10
SECONDS_PER_DAY = 86400.0


def _readonly(values: ArrayLike) -> NDArray[np.float64]:
    array = np.array(values, dtype=np.float64, copy=True)
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class ZOPrecessionScales:
    """ZO Eq. (39)--(40) 的物理尺度与独立单位账本。"""

    inner_semimajor_axis_cm: float
    inner_mean_motion_s1: float
    inner_specific_internal_energy_erg_g: float
    eccentric_communication_time_s: float
    delta_gr: float
    dimensionless_to_angular_frequency_s1: float
    dimensionless_to_cycles_per_day: float


@dataclass(frozen=True)
class LinearApsidalMode:
    """一个按内边界偏心率归一化的线性拱点本征模。"""

    radial_node_count: int
    angular_frequency_s1: float
    dimensionless_frequency: float
    signed_cycles_per_day: float
    period_days: float | None
    eccentricity_shape: NDArray[np.float64]
    generalized_residual: float


@dataclass(frozen=True)
class LinearApsidalSpectrum:
    """线性三维自由边界本征谱及离散算子审计。"""

    semimajor_axis_cm: NDArray[np.float64]
    modes: tuple[LinearApsidalMode, ...]
    scales: ZOPrecessionScales
    stiffness_symmetry_error: float
    mass_symmetry_error: float
    minimum_mass_eigenvalue: float
    includes_gr: bool
    uniform_external_precession_s1: float

    @property
    def fundamental(self) -> LinearApsidalMode:
        for mode in self.modes:
            if mode.radial_node_count == 0:
                return mode
        raise ArithmeticError("computed spectrum does not contain a node-free mode")


def zo_precession_scales(parameters: ZOConstantEParameters) -> ZOPrecessionScales:
    """从 ZO Eq. (9)--(12)、(39)--(40) 独立构造进动尺度。"""
    if not isinstance(parameters, ZOConstantEParameters):
        raise TypeError("parameters must be a ZOConstantEParameters instance")
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
    gravitational_parameter = GRAVITATIONAL_CONSTANT_CGS * black_hole_mass_g
    mean_motion = np.sqrt(
        gravitational_parameter / inner_semimajor_axis_cm**3
    )
    specific_internal_energy = (
        parameters.circularization_efficiency
        / (1.0 + parameters.circularization_efficiency)
        * gravitational_parameter
        / (2.0 * inner_semimajor_axis_cm)
    )
    gamma_minus_one = 1.0 / 3.0
    communication_time = (
        mean_motion
        * inner_semimajor_axis_cm**2
        / (gamma_minus_one * specific_internal_energy)
    )
    gravitational_radius = gravitational_parameter / LIGHT_SPEED_CM_S**2
    inner_gr_precession = (
        3.0 * gravitational_radius * mean_motion / inner_semimajor_axis_cm
    )
    delta_gr = inner_gr_precession * communication_time
    return ZOPrecessionScales(
        inner_semimajor_axis_cm=float(inner_semimajor_axis_cm),
        inner_mean_motion_s1=float(mean_motion),
        inner_specific_internal_energy_erg_g=float(specific_internal_energy),
        eccentric_communication_time_s=float(communication_time),
        delta_gr=float(delta_gr),
        dimensionless_to_angular_frequency_s1=float(1.0 / communication_time),
        dimensionless_to_cycles_per_day=float(
            SECONDS_PER_DAY / (2.0 * np.pi * communication_time)
        ),
    )


def zo_local_gr_apsidal_precession_s1(
    semimajor_axis_cm: ArrayLike,
    black_hole_mass_msun: float,
    eccentricity: ArrayLike = 0.0,
) -> NDArray[np.float64]:
    """返回 ZO Eq. (24) 的局域 Schwarzschild 拱点进动率。"""
    semimajor_axis = np.asarray(semimajor_axis_cm, dtype=np.float64)
    eccentricity_array = np.asarray(eccentricity, dtype=np.float64)
    mass = float(black_hole_mass_msun)
    if (
        not np.all(np.isfinite(semimajor_axis))
        or np.any(semimajor_axis <= 0.0)
        or not np.all(np.isfinite(eccentricity_array))
        or np.any(np.abs(eccentricity_array) >= 1.0)
        or not np.isfinite(mass)
        or mass <= 0.0
    ):
        raise PhysicalDomainError(
            "semimajor axis and mass must be positive; eccentricity must satisfy |e| < 1"
        )
    gravitational_parameter = (
        GRAVITATIONAL_CONSTANT_CGS * mass * SOLAR_MASS_G
    )
    mean_motion = np.sqrt(gravitational_parameter / semimajor_axis**3)
    gravitational_radius = gravitational_parameter / LIGHT_SPEED_CM_S**2
    result = (
        3.0
        * gravitational_radius
        * mean_motion
        / (semimajor_axis * (1.0 - eccentricity_array**2))
    )
    return _readonly(result)


def _validate_radial_grid(
    scales: ZOPrecessionScales,
    outer_to_inner_semimajor_axis: float,
    radial_points: int,
    semimajor_axis_cm: ArrayLike | None,
) -> NDArray[np.float64]:
    if semimajor_axis_cm is None:
        ratio = float(outer_to_inner_semimajor_axis)
        if not np.isfinite(ratio) or ratio <= 1.0:
            raise PhysicalDomainError(
                "outer_to_inner_semimajor_axis must be finite and greater than one"
            )
        if (
            not isinstance(radial_points, (int, np.integer))
            or isinstance(radial_points, (bool, np.bool_))
            or int(radial_points) < 8
        ):
            raise PhysicalDomainError("radial_points must be an integer at least 8")
        grid = scales.inner_semimajor_axis_cm * np.geomspace(
            1.0, ratio, int(radial_points)
        )
    else:
        grid = np.array(semimajor_axis_cm, dtype=np.float64, copy=True)
        if (
            grid.ndim != 1
            or grid.size < 8
            or not np.all(np.isfinite(grid))
            or np.any(grid <= 0.0)
            or np.any(np.diff(grid) <= 0.0)
        ):
            raise PhysicalDomainError(
                "semimajor_axis_cm must be a finite, positive, increasing 1D grid with at least 8 points"
            )
        relative_inner_error = abs(
            grid[0] / scales.inner_semimajor_axis_cm - 1.0
        )
        if relative_inner_error > 2.0e-13:
            raise PhysicalDomainError(
                "semimajor_axis_cm must start at the ZO inner semimajor axis"
            )
    return grid


def _reference_circular_coefficients(
    semimajor_axis_cm: NDArray[np.float64],
    parameters: ZOConstantEParameters,
    scales: ZOPrecessionScales,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    black_hole_mass_g = parameters.black_hole_mass_msun * SOLAR_MASS_G
    stellar_mass_g = parameters.stellar_mass_msun * SOLAR_MASS_G
    gravitational_parameter = GRAVITATIONAL_CONSTANT_CGS * black_hole_mass_g
    scaled_radius = semimajor_axis_cm / scales.inner_semimajor_axis_cm
    surface_density = (
        stellar_mass_g
        / (4.0 * np.pi * scales.inner_semimajor_axis_cm**2)
        * scaled_radius ** (-3.0)
    )
    specific_internal_energy = (
        parameters.circularization_efficiency
        / (1.0 + parameters.circularization_efficiency)
        * gravitational_parameter
        / (2.0 * semimajor_axis_cm)
    )
    pressure = (1.0 / 3.0) * surface_density * specific_internal_energy
    mean_motion = np.sqrt(gravitational_parameter / semimajor_axis_cm**3)
    return surface_density, pressure, mean_motion


def assemble_zo_linear_apsidal_matrices(
    parameters: ZOConstantEParameters,
    *,
    outer_to_inner_semimajor_axis: float | None = None,
    radial_points: int = 128,
    semimajor_axis_cm: ArrayLike | None = None,
    include_gr: bool = True,
    uniform_external_precession_s1: float = 0.0,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    ZOPrecessionScales,
]:
    """组装 OL Eq. (44) 的 P1 Galerkin 广义本征矩阵。

    自由边界使用线性化的 ZO Eq. (43)：
    ``(2*gamma-1)*a*de/da + (4*gamma-3)*e = 0``。
    """
    if not isinstance(parameters, ZOConstantEParameters):
        raise TypeError("parameters must be a ZOConstantEParameters instance")
    ratio = (
        parameters.outer_to_inner_semimajor_axis
        if outer_to_inner_semimajor_axis is None
        else float(outer_to_inner_semimajor_axis)
    )
    external = float(uniform_external_precession_s1)
    if not np.isfinite(external):
        raise PhysicalDomainError(
            "uniform_external_precession_s1 must be finite"
        )
    scales = zo_precession_scales(parameters)
    grid = _validate_radial_grid(scales, ratio, radial_points, semimajor_axis_cm)
    count = grid.size
    stiffness = np.zeros((count, count), dtype=np.float64)
    mass = np.zeros((count, count), dtype=np.float64)
    gamma = 4.0 / 3.0
    diffusion_factor = 2.0 - 1.0 / gamma
    pressure_gradient_factor = 4.0 - 3.0 / gamma
    vertical_factor = 3.0 * (1.0 + 1.0 / gamma)
    gauss_x, gauss_w = np.polynomial.legendre.leggauss(4)

    # 中文：逐单元真实积分，不把 GR 或压力项折成节点后验修正。
    for element in range(count - 1):
        left = grid[element]
        right = grid[element + 1]
        width = right - left
        radius = 0.5 * (left + right) + 0.5 * width * gauss_x
        phi = np.vstack(((right - radius) / width, (radius - left) / width))
        derivative = np.array((-1.0 / width, 1.0 / width))
        surface_density, pressure, mean_motion = _reference_circular_coefficients(
            radius, parameters, scales
        )
        diffusion = diffusion_factor * pressure * radius**3
        pressure_derivative = -4.0 * pressure / radius
        potential = (
            pressure_gradient_factor * pressure_derivative * radius**2
            + vertical_factor * pressure * radius
        )
        weight = 2.0 * surface_density * mean_motion * radius**3
        if include_gr:
            local_gr = zo_local_gr_apsidal_precession_s1(
                radius, parameters.black_hole_mass_msun
            )
        else:
            local_gr = np.zeros_like(radius)
        local_gr = local_gr + external
        jacobian = 0.5 * width
        indices = (element, element + 1)
        for local_i, global_i in enumerate(indices):
            for local_j, global_j in enumerate(indices):
                basis_product = phi[local_i] * phi[local_j]
                stiffness[global_i, global_j] += float(
                    np.sum(
                        gauss_w
                        * jacobian
                        * (
                            -diffusion
                            * derivative[local_i]
                            * derivative[local_j]
                            + potential * basis_product
                            + weight * local_gr * basis_product
                        ),
                        dtype=np.float64,
                    )
                )
                mass[global_i, global_j] += float(
                    np.sum(
                        gauss_w * jacobian * weight * basis_product,
                        dtype=np.float64,
                    )
                )

    # 中文：自由真空边界是 Hamiltonian 的自然 Robin 边界，不设 e=0。
    _, boundary_pressure, _ = _reference_circular_coefficients(
        np.array((grid[0], grid[-1])), parameters, scales
    )
    robin_ratio = (4.0 * gamma - 3.0) / (2.0 * gamma - 1.0)
    boundary_diffusion = (
        diffusion_factor * boundary_pressure * np.array((grid[0], grid[-1])) ** 3
    )
    stiffness[0, 0] += robin_ratio * boundary_diffusion[0] / grid[0]
    stiffness[-1, -1] -= robin_ratio * boundary_diffusion[1] / grid[-1]
    return _readonly(grid), _readonly(stiffness), _readonly(mass), scales


def _radial_node_count(values: NDArray[np.float64]) -> int:
    products = values[:-1] * values[1:]
    return int(np.count_nonzero(products < 0.0))


def solve_zo_linear_apsidal_modes(
    parameters: ZOConstantEParameters,
    *,
    outer_to_inner_semimajor_axis: float | None = None,
    radial_points: int = 128,
    semimajor_axis_cm: ArrayLike | None = None,
    include_gr: bool = True,
    uniform_external_precession_s1: float = 0.0,
    mode_count: int = 4,
) -> LinearApsidalSpectrum:
    """求 OL 线性三维自由边界本征谱，按径向节点数返回低阶模。"""
    if (
        not isinstance(mode_count, (int, np.integer))
        or isinstance(mode_count, (bool, np.bool_))
        or int(mode_count) < 1
    ):
        raise PhysicalDomainError("mode_count must be a positive integer")
    grid, stiffness, mass, scales = assemble_zo_linear_apsidal_matrices(
        parameters,
        outer_to_inner_semimajor_axis=outer_to_inner_semimajor_axis,
        radial_points=radial_points,
        semimajor_axis_cm=semimajor_axis_cm,
        include_gr=include_gr,
        uniform_external_precession_s1=uniform_external_precession_s1,
    )
    eigenvalue, eigenvector = eigh(stiffness, mass, check_finite=True)
    selected: dict[int, LinearApsidalMode] = {}
    for index in range(eigenvalue.size - 1, -1, -1):
        vector = eigenvector[:, index]
        nodes = _radial_node_count(vector)
        if nodes in selected or nodes >= int(mode_count):
            continue
        if vector[0] == 0.0:
            raise ArithmeticError("free-boundary eigenvector vanishes at inner edge")
        shape = vector / vector[0]
        omega = float(eigenvalue[index])
        residual_vector = stiffness @ vector - omega * (mass @ vector)
        denominator = np.linalg.norm(stiffness @ vector) + abs(omega) * np.linalg.norm(
            mass @ vector
        )
        if denominator == 0.0:
            raise ArithmeticError("generalized eigen residual has zero scale")
        residual = float(np.linalg.norm(residual_vector) / denominator)
        dimensionless = omega * scales.eccentric_communication_time_s
        cycles_per_day = omega * SECONDS_PER_DAY / (2.0 * np.pi)
        period_days = (
            None
            if omega == 0.0
            else float(2.0 * np.pi / abs(omega) / SECONDS_PER_DAY)
        )
        selected[nodes] = LinearApsidalMode(
            radial_node_count=nodes,
            angular_frequency_s1=omega,
            dimensionless_frequency=float(dimensionless),
            signed_cycles_per_day=float(cycles_per_day),
            period_days=period_days,
            eccentricity_shape=_readonly(shape),
            generalized_residual=residual,
        )
        if len(selected) == int(mode_count):
            break
    if 0 not in selected:
        raise ArithmeticError("failed to identify the node-free fundamental mode")
    modes = tuple(selected[node] for node in sorted(selected))
    stiffness_scale = np.linalg.norm(stiffness)
    mass_scale = np.linalg.norm(mass)
    if stiffness_scale == 0.0 or mass_scale == 0.0:
        raise ArithmeticError("assembled eigenproblem has a zero matrix scale")
    minimum_mass_eigenvalue = float(np.min(np.linalg.eigvalsh(mass)))
    if minimum_mass_eigenvalue <= 0.0:
        raise ArithmeticError("assembled mass matrix is not positive definite")
    return LinearApsidalSpectrum(
        semimajor_axis_cm=grid,
        modes=modes,
        scales=scales,
        stiffness_symmetry_error=float(
            np.linalg.norm(stiffness - stiffness.T) / stiffness_scale
        ),
        mass_symmetry_error=float(np.linalg.norm(mass - mass.T) / mass_scale),
        minimum_mass_eigenvalue=minimum_mass_eigenvalue,
        includes_gr=bool(include_gr),
        uniform_external_precession_s1=float(uniform_external_precession_s1),
    )
