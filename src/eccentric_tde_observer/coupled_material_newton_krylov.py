"""动态 H/He 物质固定点的物理域参数化与矩阵自由 Newton--Krylov 核。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.sparse.linalg import LinearOperator, gmres

from .atmosphere import (
    PROTON_MASS_G,
    SOLAR_FULLY_IONIZED_H_HE,
    FullyIonizedHydrogenHeliumComposition,
)
from .radiation import BOLTZMANN_ERG_K
from .radiation_matter_feedback import (
    ground_state_material_specific_energy_erg_g,
)
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class GroundStateMaterialState:
    """逐层温度、H/He 基态布居与相应物质比能。"""

    temperature_k: NDArray[np.float64]
    hydrogen_fraction: NDArray[np.float64]
    helium_fraction: NDArray[np.float64]
    specific_material_energy_erg_g: NDArray[np.float64]


@dataclass(frozen=True)
class GroundStateLogSimplexCodec:
    """以对数热能和三个 log-ratio 表示每个物质层。"""

    cell_count: int
    composition: FullyIonizedHydrogenHeliumComposition = (
        SOLAR_FULLY_IONIZED_H_HE
    )

    def __post_init__(self) -> None:
        if not isinstance(self.cell_count, (int, np.integer)) or self.cell_count < 1:
            raise PhysicalDomainError("material codec cell count must be positive")

    @property
    def vector_size(self) -> int:
        return 4 * int(self.cell_count)

    def _thermal_coefficient_erg_g_k(
        self,
        hydrogen: NDArray[np.float64],
        helium: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        hydrogen_per_gram = self.composition.hydrogen_mass_fraction / PROTON_MASS_G
        helium_per_gram = self.composition.helium_mass_fraction / (4.0 * PROTON_MASS_G)
        nuclei_per_gram = hydrogen_per_gram + helium_per_gram
        electron_per_gram = hydrogen_per_gram * hydrogen[:, 1] + helium_per_gram * (
            helium[:, 1] + 2.0 * helium[:, 2]
        )
        return 1.5 * BOLTZMANN_ERG_K * (nuclei_per_gram + electron_per_gram)

    def encode(
        self,
        temperature_k: ArrayLike,
        hydrogen_fraction: ArrayLike,
        helium_fraction: ArrayLike,
    ) -> NDArray[np.float64]:
        """将严格位于物理域内部的状态编码为无约束实向量。"""
        cells = int(self.cell_count)
        temperature = np.asarray(temperature_k, dtype=np.float64)
        hydrogen = np.asarray(hydrogen_fraction, dtype=np.float64)
        helium = np.asarray(helium_fraction, dtype=np.float64)
        tolerance = 128.0 * np.finfo(np.float64).eps
        if (
            temperature.shape != (cells,)
            or hydrogen.shape != (cells, 2)
            or helium.shape != (cells, 3)
            or not np.all(np.isfinite(temperature))
            or not np.all(np.isfinite(hydrogen))
            or not np.all(np.isfinite(helium))
            or np.any(temperature <= 0.0)
            or np.any(hydrogen <= 0.0)
            or np.any(helium <= 0.0)
            or np.any(np.abs(np.sum(hydrogen, axis=1) - 1.0) > tolerance)
            or np.any(np.abs(np.sum(helium, axis=1) - 1.0) > tolerance)
        ):
            # 中文：log-ratio 不用 floor 伪造严格为零的布居，边界态直接拒绝。
            raise PhysicalDomainError(
                "material codec requires positive interior H/He simplex states"
            )
        thermal = self._thermal_coefficient_erg_g_k(hydrogen, helium) * temperature
        if not np.all(np.isfinite(thermal)) or np.any(thermal <= 0.0):
            raise ArithmeticError("material thermal energy became invalid")
        encoded = np.empty((cells, 4), dtype=np.float64)
        encoded[:, 0] = np.log(thermal)
        encoded[:, 1] = np.log(hydrogen[:, 1] / hydrogen[:, 0])
        encoded[:, 2] = np.log(helium[:, 1] / helium[:, 0])
        encoded[:, 3] = np.log(helium[:, 2] / helium[:, 0])
        if not np.all(np.isfinite(encoded)):
            raise ArithmeticError("encoded material state became non-finite")
        return _readonly(encoded.reshape(-1))

    def decode(self, encoded_state: ArrayLike) -> GroundStateMaterialState:
        """从无约束向量恢复正温度和严格 H/He simplex。"""
        vector = np.asarray(encoded_state, dtype=np.float64)
        if vector.shape != (self.vector_size,) or not np.all(np.isfinite(vector)):
            raise PhysicalDomainError("encoded material vector is invalid")
        values = vector.reshape(int(self.cell_count), 4)
        thermal = np.exp(values[:, 0])
        hydrogen_ionized = np.empty(int(self.cell_count), dtype=np.float64)
        positive = values[:, 1] >= 0.0
        exp_negative = np.exp(-values[positive, 1])
        hydrogen_ionized[positive] = 1.0 / (1.0 + exp_negative)
        exp_positive = np.exp(values[~positive, 1])
        hydrogen_ionized[~positive] = exp_positive / (1.0 + exp_positive)
        hydrogen = np.column_stack((1.0 - hydrogen_ionized, hydrogen_ionized))
        helium_score = np.column_stack(
            (
                np.zeros(int(self.cell_count), dtype=np.float64),
                values[:, 2],
                values[:, 3],
            )
        )
        helium_shift = np.max(helium_score, axis=1)
        helium_weight = np.exp(helium_score - helium_shift[:, None])
        helium = helium_weight / np.sum(helium_weight, axis=1)[:, None]
        if (
            not np.all(np.isfinite(thermal))
            or np.any(thermal <= 0.0)
            or not np.all(np.isfinite(hydrogen))
            or not np.all(np.isfinite(helium))
            or np.any(hydrogen <= 0.0)
            or np.any(helium <= 0.0)
        ):
            raise PhysicalDomainError("decoded material state reached the domain boundary")
        coefficient = self._thermal_coefficient_erg_g_k(hydrogen, helium)
        temperature = thermal / coefficient
        energy = ground_state_material_specific_energy_erg_g(
            temperature,
            hydrogen,
            helium,
            composition=self.composition,
        )
        if not np.all(np.isfinite(temperature)) or np.any(temperature <= 0.0):
            raise ArithmeticError("decoded material temperature became invalid")
        return GroundStateMaterialState(
            temperature_k=_readonly(np.array(temperature, copy=True)),
            hydrogen_fraction=_readonly(np.array(hydrogen, copy=True)),
            helium_fraction=_readonly(np.array(helium, copy=True)),
            specific_material_energy_erg_g=_readonly(np.array(energy, copy=True)),
        )


class EncodedMaterialFixedPointResidual:
    """把物理态固定点映射转成能量与 H/He 同时闭合的无约束残差。"""

    def __init__(
        self,
        codec: GroundStateLogSimplexCodec,
        response_operator: Callable[[GroundStateMaterialState], GroundStateMaterialState],
    ) -> None:
        if not isinstance(codec, GroundStateLogSimplexCodec) or not callable(
            response_operator
        ):
            raise TypeError("encoded material residual inputs are invalid")
        self.codec = codec
        self.response_operator = response_operator
        self.evaluation_count = 0

    def __call__(self, encoded_state: ArrayLike) -> NDArray[np.float64]:
        current = np.asarray(encoded_state, dtype=np.float64)
        state = self.codec.decode(current)
        image = self.response_operator(state)
        if not isinstance(image, GroundStateMaterialState):
            raise TypeError("material response operator returned the wrong state type")
        encoded_image = self.codec.encode(
            image.temperature_k,
            image.hydrogen_fraction,
            image.helium_fraction,
        )
        residual = np.asarray(encoded_image) - current
        if not np.all(np.isfinite(residual)):
            raise ArithmeticError("encoded material fixed-point residual became non-finite")
        self.evaluation_count += 1
        return _readonly(np.array(residual, copy=True))


def ground_state_material_trial_within_trust_region(
    codec: GroundStateLogSimplexCodec,
    current_encoded_state: ArrayLike,
    trial_encoded_state: ArrayLike,
    *,
    maximum_relative_temperature_change: float,
    maximum_absolute_material_energy_increment_fraction: float,
    maximum_population_fraction_change: float,
) -> bool:
    """检查一次编码 Newton 试步是否位于物质物理信赖域内。"""
    if not isinstance(codec, GroundStateLogSimplexCodec):
        raise TypeError("material trust region requires a GroundStateLogSimplexCodec")
    temperature_limit = float(maximum_relative_temperature_change)
    energy_limit = float(maximum_absolute_material_energy_increment_fraction)
    population_limit = float(maximum_population_fraction_change)
    if (
        not all(
            np.isfinite(value)
            for value in (temperature_limit, energy_limit, population_limit)
        )
        or not 0.0 < temperature_limit < 1.0
        or not 0.0 < energy_limit < 1.0
        or not 0.0 < population_limit < 1.0
    ):
        raise PhysicalDomainError("material trust-region limits are invalid")
    current = codec.decode(current_encoded_state)
    trial = codec.decode(trial_encoded_state)
    temperature_change = float(
        np.max(
            np.abs(trial.temperature_k - current.temperature_k)
            / current.temperature_k
        )
    )
    energy_change = float(
        np.max(
            np.abs(
                trial.specific_material_energy_erg_g
                - current.specific_material_energy_erg_g
            )
            / current.specific_material_energy_erg_g
        )
    )
    population_change = max(
        float(
            np.max(
                np.abs(trial.hydrogen_fraction - current.hydrogen_fraction)
            )
        ),
        float(np.max(np.abs(trial.helium_fraction - current.helium_fraction))),
    )
    return bool(
        temperature_change <= temperature_limit
        and energy_change <= energy_limit
        and population_change <= population_limit
    )


def matrix_free_jacobian_vector_product(
    residual_function: Callable[[NDArray[np.float64]], ArrayLike],
    state: ArrayLike,
    residual_at_state: ArrayLike,
    direction: ArrayLike,
    *,
    relative_step: float,
) -> NDArray[np.float64]:
    """以前向差分计算一个矩阵自由 Jacobian--向量积。"""
    state_vector = np.asarray(state, dtype=np.float64)
    residual = np.asarray(residual_at_state, dtype=np.float64)
    vector = np.asarray(direction, dtype=np.float64)
    step_scale = float(relative_step)
    if (
        state_vector.ndim != 1
        or residual.shape != state_vector.shape
        or vector.shape != state_vector.shape
        or not all(np.all(np.isfinite(value)) for value in (state_vector, residual, vector))
        or not np.isfinite(step_scale)
        or step_scale <= 0.0
    ):
        raise PhysicalDomainError("matrix-free Jacobian-vector inputs are invalid")
    direction_norm = float(np.linalg.norm(vector))
    if direction_norm == 0.0:
        # 线性算子必须满足 J·0=0；这是精确代数恒等式，不是 floor。
        return np.zeros_like(vector)
    # 中文：无量纲编码中的 1 是零态尺度，不是物理变量 floor。
    epsilon = step_scale * (1.0 + float(np.linalg.norm(state_vector))) / direction_norm
    perturbed = np.asarray(residual_function(state_vector + epsilon * vector), dtype=np.float64)
    if perturbed.shape != residual.shape or not np.all(np.isfinite(perturbed)):
        raise ArithmeticError("perturbed residual became invalid")
    product = (perturbed - residual) / epsilon
    # Krylov 实现会原地正交化返回向量，因此这里必须返回独立、可写的工作数组。
    return np.array(product, copy=True)


@dataclass(frozen=True)
class MatrixFreeNewtonKrylovResult:
    """受保护矩阵自由 Newton--Krylov 的收敛历史。"""

    state: NDArray[np.float64]
    residual: NDArray[np.float64]
    residual_norm_history: NDArray[np.float64]
    accepted_relaxations: NDArray[np.float64]
    gmres_iteration_counts: NDArray[np.int64]
    nonlinear_iteration_count: int
    residual_evaluation_count: int
    jacobian_vector_evaluation_count: int
    converged: bool


def solve_matrix_free_newton_krylov(
    residual_function: Callable[[NDArray[np.float64]], ArrayLike],
    initial_state: ArrayLike,
    *,
    residual_norm_tolerance: float,
    maximum_newton_iterations: int,
    gmres_relative_tolerance: float,
    maximum_gmres_iterations: int,
    jacobian_relative_step: float,
    armijo_coefficient: float,
    maximum_backtracking_steps: int,
    trial_acceptance: Callable[[NDArray[np.float64], NDArray[np.float64]], bool]
    | None = None,
) -> MatrixFreeNewtonKrylovResult:
    """用实际残差回溯保护矩阵自由 Newton--Krylov 更新。"""
    state = np.asarray(initial_state, dtype=np.float64)
    tolerance = float(residual_norm_tolerance)
    gmres_tolerance = float(gmres_relative_tolerance)
    relative_step = float(jacobian_relative_step)
    armijo = float(armijo_coefficient)
    if (
        state.ndim != 1
        or not np.all(np.isfinite(state))
        or not isinstance(maximum_newton_iterations, (int, np.integer))
        or int(maximum_newton_iterations) < 1
        or not isinstance(maximum_gmres_iterations, (int, np.integer))
        or int(maximum_gmres_iterations) < 1
        or not isinstance(maximum_backtracking_steps, (int, np.integer))
        or int(maximum_backtracking_steps) < 0
        or not np.isfinite(tolerance)
        or tolerance <= 0.0
        or not np.isfinite(gmres_tolerance)
        or not 0.0 < gmres_tolerance < 1.0
        or not np.isfinite(relative_step)
        or relative_step <= 0.0
        or not np.isfinite(armijo)
        or not 0.0 < armijo < 1.0
        or (trial_acceptance is not None and not callable(trial_acceptance))
    ):
        raise PhysicalDomainError("Newton--Krylov configuration is invalid")
    residual_evaluations = 0
    jacobian_evaluations = 0

    def evaluate(value: NDArray[np.float64]) -> NDArray[np.float64]:
        nonlocal residual_evaluations
        result = np.asarray(residual_function(value), dtype=np.float64)
        residual_evaluations += 1
        if result.shape != state.shape or not np.all(np.isfinite(result)):
            raise ArithmeticError("Newton--Krylov residual became invalid")
        return result

    residual = evaluate(np.array(state, copy=True))
    norm = float(np.linalg.norm(residual))
    history = [norm]
    relaxations: list[float] = []
    gmres_counts: list[int] = []
    if norm <= tolerance:
        return MatrixFreeNewtonKrylovResult(
            state=_readonly(np.array(state, copy=True)),
            residual=_readonly(np.array(residual, copy=True)),
            residual_norm_history=_readonly(np.asarray(history)),
            accepted_relaxations=_readonly(np.asarray(relaxations)),
            gmres_iteration_counts=_readonly(np.asarray(gmres_counts, dtype=np.int64)),
            nonlinear_iteration_count=0,
            residual_evaluation_count=residual_evaluations,
            jacobian_vector_evaluation_count=jacobian_evaluations,
            converged=True,
        )
    for iteration in range(int(maximum_newton_iterations)):
        base_state = np.array(state, copy=True)
        base_residual = np.array(residual, copy=True)

        def product(direction: NDArray[np.float64]) -> NDArray[np.float64]:
            nonlocal jacobian_evaluations
            jacobian_evaluations += 1
            return np.asarray(
                matrix_free_jacobian_vector_product(
                    evaluate,
                    base_state,
                    base_residual,
                    direction,
                    relative_step=relative_step,
                )
            )

        operator = LinearOperator(
            (state.size, state.size), matvec=product, dtype=np.float64
        )
        gmres_count = 0

        def count_iteration(_residual_norm: float) -> None:
            nonlocal gmres_count
            gmres_count += 1

        direction, information = gmres(
            operator,
            -base_residual,
            rtol=gmres_tolerance,
            atol=0.0,
            restart=min(int(maximum_gmres_iterations), state.size),
            maxiter=1,
            callback=count_iteration,
            callback_type="pr_norm",
        )
        gmres_counts.append(gmres_count)
        if information != 0 or not np.all(np.isfinite(direction)):
            raise ArithmeticError(
                f"matrix-free GMRES failed at Newton iteration {iteration}: {information}"
            )
        accepted = False
        relaxation = 1.0
        for _ in range(int(maximum_backtracking_steps) + 1):
            trial = base_state + relaxation * direction
            if trial_acceptance is not None and not trial_acceptance(base_state, trial):
                relaxation *= 0.5
                continue
            trial_residual = evaluate(trial)
            trial_norm = float(np.linalg.norm(trial_residual))
            if trial_norm <= (1.0 - armijo * relaxation) * norm:
                state = trial
                residual = trial_residual
                norm = trial_norm
                history.append(norm)
                relaxations.append(relaxation)
                accepted = True
                break
            relaxation *= 0.5
        if not accepted:
            raise ArithmeticError(
                f"Newton line search failed at iteration {iteration} without clipping"
            )
        if norm <= tolerance:
            return MatrixFreeNewtonKrylovResult(
                state=_readonly(np.array(state, copy=True)),
                residual=_readonly(np.array(residual, copy=True)),
                residual_norm_history=_readonly(np.asarray(history)),
                accepted_relaxations=_readonly(np.asarray(relaxations)),
                gmres_iteration_counts=_readonly(
                    np.asarray(gmres_counts, dtype=np.int64)
                ),
                nonlinear_iteration_count=iteration + 1,
                residual_evaluation_count=residual_evaluations,
                jacobian_vector_evaluation_count=jacobian_evaluations,
                converged=True,
            )
    return MatrixFreeNewtonKrylovResult(
        state=_readonly(np.array(state, copy=True)),
        residual=_readonly(np.array(residual, copy=True)),
        residual_norm_history=_readonly(np.asarray(history)),
        accepted_relaxations=_readonly(np.asarray(relaxations)),
        gmres_iteration_counts=_readonly(np.asarray(gmres_counts, dtype=np.int64)),
        nonlinear_iteration_count=int(maximum_newton_iterations),
        residual_evaluation_count=residual_evaluations,
        jacobian_vector_evaluation_count=jacobian_evaluations,
        converged=False,
    )
