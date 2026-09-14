"""H/He 碰撞电离、详细平衡三体复合与最小率方程控制。

碰撞电离采用 Voronov（1997）的总率系数拟合。三体复合仅由同一温度下的
Saha 因子按详细平衡构造，用来验证 LTE 极限；它不是独立的三体复合数据集。
本模块仍不含激发态、bound--bound 跃迁或气体能量方程。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.linalg import expm

from .dynamic_column import validate_rate_generators
from .source import PhysicalDomainError


# 中文：沿用 Voronov 作者发布的 cfit.f 常数，以便逐项回收原拟合实现。
VORONOV_BOLTZMANN_EV_K = 8.617385e-5


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class VoronovCollisionalIonizationFit:
    """Voronov（1997）电子碰撞电离总率系数拟合参数。"""

    ion_label: str
    atomic_number: int
    electron_number: int
    ionization_energy_ev: float
    parameter_p: float
    coefficient_a_cm3_s: float
    parameter_x: float
    exponent_k: float
    minimum_electron_temperature_ev: float
    maximum_electron_temperature_kev: float

    @property
    def minimum_temperature_k(self) -> float:
        return self.minimum_electron_temperature_ev / VORONOV_BOLTZMANN_EV_K

    @property
    def maximum_temperature_k(self) -> float:
        return 1.0e3 * self.maximum_electron_temperature_kev / VORONOV_BOLTZMANN_EV_K

    def coefficient_cm3_s(self, temperature_k: ArrayLike) -> NDArray[np.float64]:
        """返回拟合有效温度域内的电子碰撞电离率系数。"""
        temperature = np.asarray(temperature_k, dtype=np.float64)
        if not np.all(np.isfinite(temperature)) or np.any(temperature <= 0.0):
            raise PhysicalDomainError(
                "temperature_k must be finite and strictly positive"
            )
        electron_temperature_ev = VORONOV_BOLTZMANN_EV_K * temperature
        maximum_ev = 1.0e3 * self.maximum_electron_temperature_kev
        if np.any(electron_temperature_ev < self.minimum_electron_temperature_ev) or np.any(
            electron_temperature_ev > maximum_ev
        ):
            raise PhysicalDomainError(
                f"{self.ion_label} Voronov fit is valid only for kT in "
                f"[{self.minimum_electron_temperature_ev:g} eV, {maximum_ev:g} eV]"
            )
        u = self.ionization_energy_ev / electron_temperature_ev
        # 中文：有效域内直接计算原拟合，不采用 cfit.f 中 U>80 的硬置零下溢保护。
        coefficient = (
            self.coefficient_a_cm3_s
            * (1.0 + self.parameter_p * np.sqrt(u))
            / (self.parameter_x + u)
            * u**self.exponent_k
            * np.exp(-u)
        )
        if not np.all(np.isfinite(coefficient)) or np.any(coefficient <= 0.0):
            raise ArithmeticError(
                f"{self.ion_label} collisional-ionization coefficient became invalid"
            )
        return _readonly(np.array(coefficient, copy=True))


# 中文：参数逐项抄录自作者发布的 cfit.dat 前三条 H/He 记录。
H_I_VORONOV_FIT = VoronovCollisionalIonizationFit(
    "H I", 1, 1, 13.6, 0.0, 2.91e-8, 0.2320, 0.39, 1.0, 20.0
)
HE_I_VORONOV_FIT = VoronovCollisionalIonizationFit(
    "He I", 2, 2, 24.6, 0.0, 1.75e-8, 0.1800, 0.35, 1.0, 20.0
)
HE_II_VORONOV_FIT = VoronovCollisionalIonizationFit(
    "He II", 2, 1, 54.4, 1.0, 2.05e-9, 0.2650, 0.25, 3.0, 20.0
)
H_HE_COLLISIONAL_IONIZATION_FITS = (
    H_I_VORONOV_FIT,
    HE_I_VORONOV_FIT,
    HE_II_VORONOV_FIT,
)


def detailed_balance_three_body_recombination_coefficient_cm6_s(
    collisional_ionization_cm3_s: ArrayLike,
    saha_factor_cm3: ArrayLike,
) -> NDArray[np.float64]:
    """由 ``C/S(T)`` 构造 LTE 控制所需的三体复合系数。"""
    collision, saha = np.broadcast_arrays(
        np.asarray(collisional_ionization_cm3_s, dtype=np.float64),
        np.asarray(saha_factor_cm3, dtype=np.float64),
    )
    if not np.all(np.isfinite(collision)) or np.any(collision < 0.0):
        raise PhysicalDomainError(
            "collisional_ionization_cm3_s must be finite and non-negative"
        )
    if not np.all(np.isfinite(saha)) or np.any(saha <= 0.0):
        raise PhysicalDomainError(
            "saha_factor_cm3 must be finite and strictly positive"
        )
    coefficient = collision / saha
    if not np.all(np.isfinite(coefficient)) or np.any(coefficient < 0.0):
        raise ArithmeticError("three-body recombination coefficient became invalid")
    return _readonly(np.array(coefficient, copy=True))


@dataclass(frozen=True)
class CollisionalPhotoionizationEquilibriumState:
    """光致/碰撞电离与辐射/三体复合共同作用的 H/He 稳态。"""

    electron_density_cm3: NDArray[np.float64]
    hydrogen_neutral_fraction: NDArray[np.float64]
    hydrogen_ionized_fraction: NDArray[np.float64]
    helium_neutral_fraction: NDArray[np.float64]
    helium_singly_ionized_fraction: NDArray[np.float64]
    helium_doubly_ionized_fraction: NDArray[np.float64]
    maximum_charge_residual_cm3: float
    maximum_relative_charge_residual: float


def collisional_photoionization_equilibrium(
    hydrogen_nuclei_cm3: ArrayLike,
    helium_nuclei_cm3: ArrayLike,
    hydrogen_i_photoionization_rate_s1: ArrayLike,
    helium_i_photoionization_rate_s1: ArrayLike,
    helium_ii_photoionization_rate_s1: ArrayLike,
    hydrogen_i_collisional_ionization_cm3_s: ArrayLike,
    helium_i_collisional_ionization_cm3_s: ArrayLike,
    helium_ii_collisional_ionization_cm3_s: ArrayLike,
    hydrogen_i_radiative_recombination_cm3_s: ArrayLike,
    helium_i_radiative_recombination_cm3_s: ArrayLike,
    helium_ii_radiative_recombination_cm3_s: ArrayLike,
    hydrogen_i_three_body_recombination_cm6_s: ArrayLike,
    helium_i_three_body_recombination_cm6_s: ArrayLike,
    helium_ii_three_body_recombination_cm6_s: ArrayLike,
    *,
    bisection_iterations: int = 128,
) -> CollisionalPhotoionizationEquilibriumState:
    """解带电荷中性的最小 H I/H II 与 He I/He II/He III 稳态。"""
    values = (
        hydrogen_nuclei_cm3,
        helium_nuclei_cm3,
        hydrogen_i_photoionization_rate_s1,
        helium_i_photoionization_rate_s1,
        helium_ii_photoionization_rate_s1,
        hydrogen_i_collisional_ionization_cm3_s,
        helium_i_collisional_ionization_cm3_s,
        helium_ii_collisional_ionization_cm3_s,
        hydrogen_i_radiative_recombination_cm3_s,
        helium_i_radiative_recombination_cm3_s,
        helium_ii_radiative_recombination_cm3_s,
        hydrogen_i_three_body_recombination_cm6_s,
        helium_i_three_body_recombination_cm6_s,
        helium_ii_three_body_recombination_cm6_s,
    )
    arrays = np.broadcast_arrays(
        *(np.asarray(value, dtype=np.float64) for value in values)
    )
    (
        hydrogen,
        helium,
        gamma_h,
        gamma_he1,
        gamma_he2,
        collision_h,
        collision_he1,
        collision_he2,
        alpha_h,
        alpha_he1,
        alpha_he2,
        beta_h,
        beta_he1,
        beta_he2,
    ) = arrays
    if any(not np.all(np.isfinite(value)) for value in arrays):
        raise PhysicalDomainError("collisional-equilibrium inputs must be finite")
    if np.any(hydrogen < 0.0) or np.any(helium < 0.0) or np.any(hydrogen + helium <= 0.0):
        raise PhysicalDomainError(
            "H/He nuclei densities must be non-negative with positive total"
        )
    rates = arrays[2:]
    if any(np.any(value < 0.0) for value in rates):
        raise PhysicalDomainError("all ionization and recombination rates must be non-negative")
    if not isinstance(bisection_iterations, (int, np.integer)) or int(bisection_iterations) < 1:
        raise PhysicalDomainError("bisection_iterations must be a positive integer")

    maximum_electrons = hydrogen + 2.0 * helium
    no_hydrogen_source = (hydrogen == 0.0) | ((gamma_h == 0.0) & (collision_h == 0.0))
    no_helium_source = (helium == 0.0) | (
        (gamma_he1 == 0.0) & (collision_he1 == 0.0)
    )
    all_neutral = no_hydrogen_source & no_helium_source
    lower = np.zeros_like(maximum_electrons)
    upper = np.array(maximum_electrons, copy=True)

    def fractions(electron: NDArray[np.float64]):
        upward_h = gamma_h + electron * collision_h
        downward_h = electron * alpha_h + electron**2 * beta_h
        h_scale = np.maximum(upward_h, downward_h)
        safe_h_scale = np.where(h_scale == 0.0, 1.0, h_scale)
        h_up = upward_h / safe_h_scale
        h_down = downward_h / safe_h_scale
        h_denominator = h_up + h_down
        safe_h_denominator = np.where(h_denominator == 0.0, 1.0, h_denominator)
        h_neutral = np.where(
            h_denominator == 0.0, 1.0, h_down / safe_h_denominator
        )
        h_ionized = np.where(
            h_denominator == 0.0, 0.0, h_up / safe_h_denominator
        )

        upward_he1 = gamma_he1 + electron * collision_he1
        upward_he2 = gamma_he2 + electron * collision_he2
        downward_he1 = electron * alpha_he1 + electron**2 * beta_he1
        downward_he2 = electron * alpha_he2 + electron**2 * beta_he2
        he_scale = np.maximum.reduce(
            (upward_he1, upward_he2, downward_he1, downward_he2)
        )
        safe_he_scale = np.where(he_scale == 0.0, 1.0, he_scale)
        u1 = upward_he1 / safe_he_scale
        u2 = upward_he2 / safe_he_scale
        d1 = downward_he1 / safe_he_scale
        d2 = downward_he2 / safe_he_scale
        neutral_weight = d1 * d2
        singly_weight = u1 * d2
        doubly_weight = u1 * u2
        denominator = neutral_weight + singly_weight + doubly_weight
        safe_denominator = np.where(denominator == 0.0, 1.0, denominator)
        he_neutral = neutral_weight / safe_denominator
        he_singly = singly_weight / safe_denominator
        he_doubly = doubly_weight / safe_denominator
        neutral_branch = denominator == 0.0
        he_neutral = np.where(neutral_branch, 1.0, he_neutral)
        he_singly = np.where(neutral_branch, 0.0, he_singly)
        he_doubly = np.where(neutral_branch, 0.0, he_doubly)
        return h_neutral, h_ionized, he_neutral, he_singly, he_doubly

    # 中文：电荷残差在物理解区间内单调，用固定次数二分，不修补失败解。
    for _ in range(int(bisection_iterations)):
        electron = 0.5 * (lower + upper)
        _, h_ionized, _, he_singly, he_doubly = fractions(electron)
        charge = hydrogen * h_ionized + helium * (he_singly + 2.0 * he_doubly)
        positive = electron > charge
        upper = np.where(positive, electron, upper)
        lower = np.where(positive, lower, electron)

    electron = np.where(all_neutral, 0.0, 0.5 * (lower + upper))
    safe_electron = np.where(all_neutral, 1.0, electron)
    h_neutral, h_ionized, he_neutral, he_singly, he_doubly = fractions(safe_electron)
    h_neutral = np.where(all_neutral, 1.0, h_neutral)
    h_ionized = np.where(all_neutral, 0.0, h_ionized)
    he_neutral = np.where(all_neutral, 1.0, he_neutral)
    he_singly = np.where(all_neutral, 0.0, he_singly)
    he_doubly = np.where(all_neutral, 0.0, he_doubly)
    charge = hydrogen * h_ionized + helium * (he_singly + 2.0 * he_doubly)
    absolute_residual = np.abs(electron - charge)
    relative_residual = absolute_residual / maximum_electrons
    output = (electron, h_neutral, h_ionized, he_neutral, he_singly, he_doubly)
    if not all(np.all(np.isfinite(value)) for value in output):
        raise ArithmeticError("collisional equilibrium became non-finite")
    if any(np.any(value < 0.0) or np.any(value > 1.0) for value in output[1:]):
        raise ArithmeticError("collisional equilibrium produced invalid fractions")
    return CollisionalPhotoionizationEquilibriumState(
        *(_readonly(np.array(value, copy=True)) for value in output),
        maximum_charge_residual_cm3=float(np.max(absolute_residual)),
        maximum_relative_charge_residual=float(np.max(relative_residual)),
    )


@dataclass(frozen=True)
class HHeRateGenerators:
    """固定局域状态下的 H 与 He 守恒率矩阵。"""

    hydrogen_s1: NDArray[np.float64]
    helium_s1: NDArray[np.float64]


def h_he_rate_generators_s1(
    electron_density_cm3: ArrayLike,
    hydrogen_i_photoionization_rate_s1: ArrayLike,
    helium_i_photoionization_rate_s1: ArrayLike,
    helium_ii_photoionization_rate_s1: ArrayLike,
    hydrogen_i_collisional_ionization_cm3_s: ArrayLike,
    helium_i_collisional_ionization_cm3_s: ArrayLike,
    helium_ii_collisional_ionization_cm3_s: ArrayLike,
    hydrogen_i_radiative_recombination_cm3_s: ArrayLike,
    helium_i_radiative_recombination_cm3_s: ArrayLike,
    helium_ii_radiative_recombination_cm3_s: ArrayLike,
    hydrogen_i_three_body_recombination_cm6_s: ArrayLike,
    helium_i_three_body_recombination_cm6_s: ArrayLike,
    helium_ii_three_body_recombination_cm6_s: ArrayLike,
) -> HHeRateGenerators:
    """按列向量约定 ``dn/dt=R@n`` 构造相邻电离态率矩阵。"""
    values = (
        electron_density_cm3,
        hydrogen_i_photoionization_rate_s1,
        helium_i_photoionization_rate_s1,
        helium_ii_photoionization_rate_s1,
        hydrogen_i_collisional_ionization_cm3_s,
        helium_i_collisional_ionization_cm3_s,
        helium_ii_collisional_ionization_cm3_s,
        hydrogen_i_radiative_recombination_cm3_s,
        helium_i_radiative_recombination_cm3_s,
        helium_ii_radiative_recombination_cm3_s,
        hydrogen_i_three_body_recombination_cm6_s,
        helium_i_three_body_recombination_cm6_s,
        helium_ii_three_body_recombination_cm6_s,
    )
    arrays = np.broadcast_arrays(
        *(np.asarray(value, dtype=np.float64) for value in values)
    )
    if any(not np.all(np.isfinite(value)) or np.any(value < 0.0) for value in arrays):
        raise PhysicalDomainError("rate-generator inputs must be finite and non-negative")
    (
        electron,
        gamma_h,
        gamma_he1,
        gamma_he2,
        collision_h,
        collision_he1,
        collision_he2,
        alpha_h,
        alpha_he1,
        alpha_he2,
        beta_h,
        beta_he1,
        beta_he2,
    ) = arrays
    upward_h = gamma_h + electron * collision_h
    downward_h = electron * alpha_h + electron**2 * beta_h
    upward_he1 = gamma_he1 + electron * collision_he1
    upward_he2 = gamma_he2 + electron * collision_he2
    downward_he1 = electron * alpha_he1 + electron**2 * beta_he1
    downward_he2 = electron * alpha_he2 + electron**2 * beta_he2

    shape = electron.shape
    hydrogen = np.zeros(shape + (2, 2), dtype=np.float64)
    hydrogen[..., 0, 0] = -upward_h
    hydrogen[..., 1, 0] = upward_h
    hydrogen[..., 0, 1] = downward_h
    hydrogen[..., 1, 1] = -downward_h
    helium = np.zeros(shape + (3, 3), dtype=np.float64)
    helium[..., 0, 0] = -upward_he1
    helium[..., 1, 0] = upward_he1
    helium[..., 0, 1] = downward_he1
    helium[..., 1, 1] = -(downward_he1 + upward_he2)
    helium[..., 2, 1] = upward_he2
    helium[..., 1, 2] = downward_he2
    helium[..., 2, 2] = -downward_he2
    return HHeRateGenerators(
        hydrogen_s1=validate_rate_generators(hydrogen),
        helium_s1=validate_rate_generators(helium),
    )


@dataclass(frozen=True)
class ConstantRateSolution:
    """固定率矩阵的矩阵指数松弛解。"""

    time_s: NDArray[np.float64]
    population: NDArray[np.float64]
    maximum_particle_conservation_residual: float
    minimum_population: float


def solve_constant_rate_network(
    rate_matrix_s1: ArrayLike,
    time_s: ArrayLike,
    initial_population: ArrayLike,
) -> ConstantRateSolution:
    """用矩阵指数求固定生成元下的松弛，不裁剪或重归一化。"""
    rates = validate_rate_generators(rate_matrix_s1)
    if rates.ndim != 2:
        raise PhysicalDomainError("constant rate solve requires one 2D generator")
    time = np.array(time_s, dtype=np.float64, copy=True)
    if time.ndim != 1 or time.size < 1:
        raise PhysicalDomainError("time_s must be a non-empty 1D array")
    if not np.all(np.isfinite(time)) or np.any(time < 0.0) or np.any(np.diff(time) <= 0.0):
        raise PhysicalDomainError(
            "time_s must be finite, non-negative and strictly increasing"
        )
    initial = np.array(initial_population, dtype=np.float64, copy=True)
    if initial.ndim != 1 or initial.shape[0] != rates.shape[0]:
        raise PhysicalDomainError("initial_population must match the species axis")
    if not np.all(np.isfinite(initial)) or np.any(initial < 0.0):
        raise PhysicalDomainError("initial_population must be finite and non-negative")
    total = float(np.sum(initial))
    if total <= 0.0:
        raise PhysicalDomainError("initial_population must have positive total abundance")

    population = np.empty((time.size, initial.size), dtype=np.float64)
    for index, elapsed in enumerate(time):
        population[index] = expm(elapsed * rates) @ initial
    if not np.all(np.isfinite(population)):
        raise ArithmeticError("constant-rate population became non-finite")
    if np.any(population < 0.0):
        raise ArithmeticError("constant-rate population became negative")
    conservation = np.max(np.abs(np.sum(population, axis=1) - total)) / total
    return ConstantRateSolution(
        time_s=_readonly(time),
        population=_readonly(population),
        maximum_particle_conservation_residual=float(conservation),
        minimum_population=float(np.min(population)),
    )
