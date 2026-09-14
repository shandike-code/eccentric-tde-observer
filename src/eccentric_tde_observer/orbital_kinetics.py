"""规定周期背景上的电荷自洽 H/He 基态率方程。

本模块用后向 Euler 处理刚性局域率，并在每个时间步内用电荷中性标量根同时更新
电子密度。H/He 粒子数由守恒率矩阵保持，不做裁剪或事后重归一化。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


def _fraction_vector(name: str, values: ArrayLike, species: int) -> NDArray[np.float64]:
    fractions = np.array(values, dtype=np.float64, copy=True)
    if fractions.shape != (species,):
        raise PhysicalDomainError(f"{name} must have shape ({species},)")
    if not np.all(np.isfinite(fractions)) or np.any(fractions < 0.0):
        raise PhysicalDomainError(f"{name} must be finite and non-negative")
    if not np.isclose(np.sum(fractions), 1.0, rtol=0.0, atol=2.0e-14):
        raise PhysicalDomainError(f"{name} must sum to one")
    return fractions


@dataclass(frozen=True)
class HHeRateOrbit:
    """一个周期上 H I、He I、He II 三条相邻过渡的局域率输入。"""

    hydrogen_nuclei_cm3: ArrayLike
    helium_nuclei_cm3: ArrayLike
    step_duration_s: ArrayLike
    photoionization_s1: ArrayLike
    collisional_ionization_cm3_s: ArrayLike
    radiative_recombination_cm3_s: ArrayLike
    three_body_recombination_cm6_s: ArrayLike

    def __post_init__(self) -> None:
        hydrogen = np.array(self.hydrogen_nuclei_cm3, dtype=np.float64, copy=True)
        helium = np.array(self.helium_nuclei_cm3, dtype=np.float64, copy=True)
        duration = np.array(self.step_duration_s, dtype=np.float64, copy=True)
        if hydrogen.ndim != 1 or hydrogen.size < 2:
            raise PhysicalDomainError("rate orbit requires at least two phase points")
        if helium.shape != hydrogen.shape or duration.shape != hydrogen.shape:
            raise PhysicalDomainError("nuclei densities and step durations must share one phase axis")
        if (
            not np.all(np.isfinite(hydrogen))
            or not np.all(np.isfinite(helium))
            or np.any(hydrogen < 0.0)
            or np.any(helium < 0.0)
            or np.any(hydrogen + helium <= 0.0)
        ):
            raise PhysicalDomainError("H/He nuclei densities must be finite and physical")
        if not np.all(np.isfinite(duration)) or np.any(duration <= 0.0):
            raise PhysicalDomainError("step durations must be finite and strictly positive")
        rate_arrays = []
        for name in (
            "photoionization_s1",
            "collisional_ionization_cm3_s",
            "radiative_recombination_cm3_s",
            "three_body_recombination_cm6_s",
        ):
            values = np.array(getattr(self, name), dtype=np.float64, copy=True)
            if values.shape != (hydrogen.size, 3):
                raise PhysicalDomainError(f"{name} must have shape (phase, 3)")
            if not np.all(np.isfinite(values)) or np.any(values < 0.0):
                raise PhysicalDomainError(f"{name} must be finite and non-negative")
            rate_arrays.append(values)
        object.__setattr__(self, "hydrogen_nuclei_cm3", _readonly(hydrogen))
        object.__setattr__(self, "helium_nuclei_cm3", _readonly(helium))
        object.__setattr__(self, "step_duration_s", _readonly(duration))
        for name, values in zip(
            (
                "photoionization_s1",
                "collisional_ionization_cm3_s",
                "radiative_recombination_cm3_s",
                "three_body_recombination_cm6_s",
            ),
            rate_arrays,
            strict=True,
        ):
            object.__setattr__(self, name, _readonly(values))

    @property
    def phase_points(self) -> int:
        return int(self.hydrogen_nuclei_cm3.size)


@dataclass(frozen=True)
class ChargeNeutralBackwardEulerStep:
    """一个电荷自洽后向 Euler 步的结果。"""

    hydrogen_fraction: NDArray[np.float64]
    helium_fraction: NDArray[np.float64]
    electron_density_cm3: float
    relative_charge_residual: float
    particle_conservation_residual: float
    minimum_fraction: float


def charge_neutral_backward_euler_step(
    previous_hydrogen_fraction: ArrayLike,
    previous_helium_fraction: ArrayLike,
    hydrogen_nuclei_cm3: float,
    helium_nuclei_cm3: float,
    step_duration_s: float,
    photoionization_s1: ArrayLike,
    collisional_ionization_cm3_s: ArrayLike,
    radiative_recombination_cm3_s: ArrayLike,
    three_body_recombination_cm6_s: ArrayLike,
    *,
    bisection_iterations: int = 96,
) -> ChargeNeutralBackwardEulerStep:
    """推进一个隐式步，并在新时刻联立求解电子密度。"""
    previous_h = _fraction_vector(
        "previous_hydrogen_fraction", previous_hydrogen_fraction, 2
    )
    previous_he = _fraction_vector(
        "previous_helium_fraction", previous_helium_fraction, 3
    )
    hydrogen = float(hydrogen_nuclei_cm3)
    helium = float(helium_nuclei_cm3)
    duration = float(step_duration_s)
    if (
        not np.isfinite(hydrogen)
        or not np.isfinite(helium)
        or hydrogen < 0.0
        or helium < 0.0
        or hydrogen + helium <= 0.0
    ):
        raise PhysicalDomainError("H/He nuclei densities must be finite and physical")
    if not np.isfinite(duration) or duration <= 0.0:
        raise PhysicalDomainError("step_duration_s must be finite and strictly positive")
    rates = []
    for name, values in (
        ("photoionization_s1", photoionization_s1),
        ("collisional_ionization_cm3_s", collisional_ionization_cm3_s),
        ("radiative_recombination_cm3_s", radiative_recombination_cm3_s),
        ("three_body_recombination_cm6_s", three_body_recombination_cm6_s),
    ):
        array = np.array(values, dtype=np.float64, copy=True)
        if array.shape != (3,) or not np.all(np.isfinite(array)) or np.any(array < 0.0):
            raise PhysicalDomainError(f"{name} must be a finite non-negative 3-vector")
        rates.append(array)
    gamma, collision, radiative, three_body = rates
    if not isinstance(bisection_iterations, (int, np.integer)) or int(bisection_iterations) < 1:
        raise PhysicalDomainError("bisection_iterations must be a positive integer")

    def implicit_populations(electron: float) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        upward = gamma + electron * collision
        downward = electron * radiative + electron**2 * three_body
        h_denominator = 1.0 + duration * (upward[0] + downward[0])
        hydrogen_fraction = np.array(
            [
                (previous_h[0] + duration * downward[0]) / h_denominator,
                (previous_h[1] + duration * upward[0]) / h_denominator,
            ]
        )
        # 中文：消去 He II 后解二维守恒系统，避免大时间步下三维零本征模造成病态矩阵。
        helium_reduced = np.array(
            [
                [
                    1.0 + duration * (upward[1] + downward[1]),
                    duration * downward[1],
                ],
                [
                    duration * upward[2],
                    1.0 + duration * (upward[2] + downward[2]),
                ],
            ]
        )
        helium_neutral_doubly = np.linalg.solve(
            helium_reduced,
            np.array(
                [
                    previous_he[0] + duration * downward[1],
                    previous_he[2] + duration * upward[2],
                ]
            ),
        )
        helium_fraction = np.array(
            [
                helium_neutral_doubly[0],
                1.0 - helium_neutral_doubly[0] - helium_neutral_doubly[1],
                helium_neutral_doubly[1],
            ]
        )
        return hydrogen_fraction, helium_fraction

    maximum_electrons = hydrogen + 2.0 * helium

    def charge_residual(electron: float):
        hydrogen_fraction, helium_fraction = implicit_populations(electron)
        charge = hydrogen * hydrogen_fraction[1] + helium * (
            helium_fraction[1] + 2.0 * helium_fraction[2]
        )
        return electron - charge, hydrogen_fraction, helium_fraction

    lower = 0.0
    upper = maximum_electrons
    lower_residual, lower_h, lower_he = charge_residual(lower)
    upper_residual, _, _ = charge_residual(upper)
    scale = maximum_electrons
    tolerance = 64.0 * np.finfo(np.float64).eps * scale
    if lower_residual > tolerance or upper_residual < -tolerance:
        raise ArithmeticError("charge-neutral backward-Euler root is not bracketed")
    if abs(lower_residual) <= tolerance:
        electron = lower
        hydrogen_fraction = lower_h
        helium_fraction = lower_he
    else:
        for _ in range(int(bisection_iterations)):
            electron = 0.5 * (lower + upper)
            residual, _, _ = charge_residual(electron)
            if residual > 0.0:
                upper = electron
            else:
                lower = electron
        electron = 0.5 * (lower + upper)
        _, hydrogen_fraction, helium_fraction = charge_residual(electron)

    charge = hydrogen * hydrogen_fraction[1] + helium * (
        helium_fraction[1] + 2.0 * helium_fraction[2]
    )
    relative_charge_residual = abs(electron - charge) / maximum_electrons
    particle_residual = max(
        abs(float(np.sum(hydrogen_fraction)) - 1.0),
        abs(float(np.sum(helium_fraction)) - 1.0),
    )
    outputs = (hydrogen_fraction, helium_fraction)
    if not all(np.all(np.isfinite(values)) for values in outputs) or not np.isfinite(electron):
        raise ArithmeticError("backward-Euler kinetic state became non-finite")
    if any(np.any(values < 0.0) or np.any(values > 1.0) for values in outputs):
        raise ArithmeticError("backward-Euler kinetic state left the physical simplex")
    return ChargeNeutralBackwardEulerStep(
        hydrogen_fraction=_readonly(hydrogen_fraction),
        helium_fraction=_readonly(helium_fraction),
        electron_density_cm3=float(electron),
        relative_charge_residual=float(relative_charge_residual),
        particle_conservation_residual=float(particle_residual),
        minimum_fraction=float(min(np.min(hydrogen_fraction), np.min(helium_fraction))),
    )


@dataclass(frozen=True)
class PeriodicHHeKineticSolution:
    """规定率轨道上的 H/He 周期稳定态。"""

    hydrogen_fraction: NDArray[np.float64]
    helium_fraction: NDArray[np.float64]
    electron_density_cm3: NDArray[np.float64]
    end_hydrogen_fraction: NDArray[np.float64]
    end_helium_fraction: NDArray[np.float64]
    cycles: int
    cycle_residual: float
    maximum_relative_charge_residual: float
    maximum_particle_conservation_residual: float
    minimum_fraction: float


def solve_periodic_h_he_kinetics(
    rate_orbit: HHeRateOrbit,
    initial_hydrogen_fraction: ArrayLike,
    initial_helium_fraction: ArrayLike,
    *,
    cycle_tolerance: float = 1.0e-11,
    maximum_cycles: int = 100,
    bisection_iterations: int = 96,
) -> PeriodicHHeKineticSolution:
    """迭代整轨道后向 Euler 映射，求 H/He 周期稳定态。"""
    if not isinstance(rate_orbit, HHeRateOrbit):
        raise TypeError("rate_orbit must be an HHeRateOrbit")
    start_h = _fraction_vector(
        "initial_hydrogen_fraction", initial_hydrogen_fraction, 2
    )
    start_he = _fraction_vector(
        "initial_helium_fraction", initial_helium_fraction, 3
    )
    tolerance = float(cycle_tolerance)
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise PhysicalDomainError("cycle_tolerance must be finite and positive")
    if not isinstance(maximum_cycles, (int, np.integer)) or int(maximum_cycles) < 1:
        raise PhysicalDomainError("maximum_cycles must be a positive integer")

    phase_points = rate_orbit.phase_points
    maximum_charge = 0.0
    maximum_particle = 0.0
    minimum_fraction = float(min(np.min(start_h), np.min(start_he)))
    for cycle in range(1, int(maximum_cycles) + 1):
        hydrogen_trajectory = np.empty((phase_points, 2), dtype=np.float64)
        helium_trajectory = np.empty((phase_points, 3), dtype=np.float64)
        electron_trajectory = np.empty(phase_points, dtype=np.float64)
        state_h = start_h.copy()
        state_he = start_he.copy()
        for phase in range(phase_points):
            hydrogen_trajectory[phase] = state_h
            helium_trajectory[phase] = state_he
            electron_trajectory[phase] = (
                rate_orbit.hydrogen_nuclei_cm3[phase] * state_h[1]
                + rate_orbit.helium_nuclei_cm3[phase]
                * (state_he[1] + 2.0 * state_he[2])
            )
            following = (phase + 1) % phase_points
            step = charge_neutral_backward_euler_step(
                state_h,
                state_he,
                rate_orbit.hydrogen_nuclei_cm3[following],
                rate_orbit.helium_nuclei_cm3[following],
                rate_orbit.step_duration_s[phase],
                rate_orbit.photoionization_s1[following],
                rate_orbit.collisional_ionization_cm3_s[following],
                rate_orbit.radiative_recombination_cm3_s[following],
                rate_orbit.three_body_recombination_cm6_s[following],
                bisection_iterations=bisection_iterations,
            )
            state_h = np.array(step.hydrogen_fraction, copy=True)
            state_he = np.array(step.helium_fraction, copy=True)
            maximum_charge = max(maximum_charge, step.relative_charge_residual)
            maximum_particle = max(
                maximum_particle, step.particle_conservation_residual
            )
            minimum_fraction = min(minimum_fraction, step.minimum_fraction)
        residual = float(
            max(
                np.max(np.abs(state_h - start_h)),
                np.max(np.abs(state_he - start_he)),
            )
        )
        if residual < tolerance:
            return PeriodicHHeKineticSolution(
                hydrogen_fraction=_readonly(hydrogen_trajectory),
                helium_fraction=_readonly(helium_trajectory),
                electron_density_cm3=_readonly(electron_trajectory),
                end_hydrogen_fraction=_readonly(state_h),
                end_helium_fraction=_readonly(state_he),
                cycles=cycle,
                cycle_residual=residual,
                maximum_relative_charge_residual=maximum_charge,
                maximum_particle_conservation_residual=maximum_particle,
                minimum_fraction=minimum_fraction,
            )
        start_h = state_h
        start_he = state_he
    raise ArithmeticError("periodic H/He kinetics did not converge within maximum_cycles")
