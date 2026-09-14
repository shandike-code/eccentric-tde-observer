"""混合系 ALE 频率块规划与有界内存单次源迭代。

块边界只切分计算，不改变正式全局频率控制体。每个核心块从全局网格取得足够的
Doppler 守护组；块间 halo 使用同一次全局 Jacobi 迭代的旧强度。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .mixed_frame_ale import (
    MixedFrameFrequencyStencil,
    solve_mixed_frame_ale_group_step,
)
from .mixed_frame_frequency import lorentz_ray_transform
from .source import PhysicalDomainError


@dataclass(frozen=True)
class MixedFrameFrequencyBlock:
    """一个全局频率网格上的核心块及精确 Doppler halo。"""

    core_group_start: int
    core_group_stop: int
    collision_group_start: int
    collision_group_stop: int
    outer_group_start: int
    outer_group_stop: int
    local_stencil: MixedFrameFrequencyStencil


@dataclass(frozen=True)
class StreamedSourceIteration:
    """一次全局块 Jacobi 源迭代的标量诊断。"""

    block_count: int
    maximum_core_group_count: int
    maximum_collision_group_count: int
    maximum_outer_group_count: int
    maximum_absolute_change: float
    maximum_relative_change: float
    minimum_intensity: float
    block_diagnostics_computed: bool
    maximum_block_coupled_residual: float | None
    maximum_block_energy_ledger_residual: float | None


def _covering_group_slice(
    edge: NDArray[np.float64], lower: float, upper: float
) -> tuple[int, int]:
    if (
        not np.isfinite(lower)
        or not np.isfinite(upper)
        or lower < edge[0]
        or upper > edge[-1]
        or upper <= lower
    ):
        raise PhysicalDomainError("frequency-block query left the global guard grid")
    start = int(np.searchsorted(edge, lower, side="right") - 1)
    stop = int(np.searchsorted(edge, upper, side="left"))
    start = max(start, 0)
    stop = min(stop, edge.size - 1)
    if stop <= start:
        raise ArithmeticError("frequency-block covering slice became empty")
    return start, stop


def plan_mixed_frame_frequency_blocks(
    stencil: MixedFrameFrequencyStencil,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    material_velocity_beta: ArrayLike,
    core_group_count: int,
) -> tuple[MixedFrameFrequencyBlock, ...]:
    """在不改全局频率边界的条件下构造精确一次搬移块。"""
    if (
        not isinstance(core_group_count, (int, np.integer))
        or isinstance(core_group_count, (bool, np.bool_))
        or int(core_group_count) < 1
    ):
        raise PhysicalDomainError("core_group_count must be a positive integer")
    core_size = int(core_group_count)
    transform = lorentz_ray_transform(
        direction_cosine, angular_weight, material_velocity_beta
    )
    doppler = transform.doppler_lab_to_comoving
    minimum_doppler = float(np.min(doppler))
    maximum_doppler = float(np.max(doppler))
    active_edge = stencil.active_lab_edge_hz
    collision_edge = stencil.comoving_collision_edge_hz
    outer_edge = stencil.outer_lab_edge_hz
    full_active_outer_start = stencil.active_outer_group_start
    blocks = []
    for core_start in range(0, stencil.physical_group_count, core_size):
        core_stop = min(core_start + core_size, stencil.physical_group_count)
        collision_start, collision_stop = _covering_group_slice(
            collision_edge,
            float(active_edge[core_start] * minimum_doppler),
            float(active_edge[core_stop] * maximum_doppler),
        )
        outer_start, outer_stop = _covering_group_slice(
            outer_edge,
            float(collision_edge[collision_start] / maximum_doppler),
            float(collision_edge[collision_stop] / minimum_doppler),
        )
        active_global_start = full_active_outer_start + core_start
        active_global_stop = full_active_outer_start + core_stop
        if not (
            outer_start <= active_global_start
            and outer_stop >= active_global_stop
        ):
            raise ArithmeticError("frequency block lost its active core inside the halo")
        local = MixedFrameFrequencyStencil(
            outer_lab_edge_hz=np.array(
                outer_edge[outer_start : outer_stop + 1], copy=True
            ),
            comoving_collision_edge_hz=np.array(
                collision_edge[collision_start : collision_stop + 1], copy=True
            ),
            active_lab_edge_hz=np.array(
                active_edge[core_start : core_stop + 1], copy=True
            ),
            active_outer_group_start=active_global_start - outer_start,
            active_outer_group_stop=active_global_stop - outer_start,
            physical_group_count=core_stop - core_start,
            comoving_collision_group_count=collision_stop - collision_start,
            outer_lab_group_count=outer_stop - outer_start,
            groups_per_decade=stencil.groups_per_decade,
            maximum_velocity_beta=stencil.maximum_velocity_beta,
        )
        for array in (
            local.outer_lab_edge_hz,
            local.comoving_collision_edge_hz,
            local.active_lab_edge_hz,
        ):
            array.setflags(write=False)
        blocks.append(
            MixedFrameFrequencyBlock(
                core_group_start=core_start,
                core_group_stop=core_stop,
                collision_group_start=collision_start,
                collision_group_stop=collision_stop,
                outer_group_start=outer_start,
                outer_group_stop=outer_stop,
                local_stencil=local,
            )
        )
    return tuple(blocks)


def stream_mixed_frame_ale_source_iteration(
    stencil: MixedFrameFrequencyStencil,
    blocks: tuple[MixedFrameFrequencyBlock, ...],
    old_depth_edges_cm: ArrayLike,
    new_depth_edges_cm: ArrayLike,
    direction_cosine: ArrayLike,
    angular_weight: ArrayLike,
    initial_active_lab_intensity_density: ArrayLike,
    full_outer_lab_guard_intensity_density: ArrayLike,
    comoving_true_absorption_per_cm: ArrayLike,
    comoving_thermal_emissivity_cgs: ArrayLike,
    comoving_scattering_per_cm: ArrayLike,
    material_velocity_beta: ArrayLike,
    duration_s: float,
    current_active_lab_intensity_density: ArrayLike,
    output_active_lab_intensity_density: NDArray[np.float64],
    *,
    left_exterior_intensity: ArrayLike = 0.0,
    right_exterior_intensity: ArrayLike = 0.0,
    propagation_speed_cm_s: float,
    spatial_scheme: str = "hybrid_step_turning_upwind",
    compute_block_diagnostics: bool = True,
) -> StreamedSourceIteration:
    """用全局旧迭代 halo 逐块执行一次与整体 Jacobi 等价的源迭代。

    中间固定点迭代可令 ``compute_block_diagnostics=False``，只省略不会反馈到强度更新的
    末态残差与能量账本；全局收敛后的正式结果仍必须另跑完整诊断。
    """
    mu = np.asarray(direction_cosine, dtype=np.float64)
    initial = np.asarray(initial_active_lab_intensity_density, dtype=np.float64)
    outer_full = np.asarray(
        full_outer_lab_guard_intensity_density, dtype=np.float64
    )
    true_absorption = np.asarray(comoving_true_absorption_per_cm, dtype=np.float64)
    thermal = np.asarray(comoving_thermal_emissivity_cgs, dtype=np.float64)
    scattering = np.asarray(comoving_scattering_per_cm, dtype=np.float64)
    current = np.asarray(current_active_lab_intensity_density, dtype=np.float64)
    output = np.asarray(output_active_lab_intensity_density, dtype=np.float64)
    depth_count = np.asarray(material_velocity_beta).size
    active_shape = (stencil.physical_group_count, mu.size, depth_count)
    collision_shape = (stencil.comoving_collision_group_count, depth_count)
    outer_shape = (stencil.outer_lab_group_count, mu.size, depth_count)
    if initial.shape != active_shape or current.shape != active_shape:
        raise PhysicalDomainError("streamed active intensities do not match the grid")
    if output.shape != active_shape or not output.flags.writeable:
        raise PhysicalDomainError("streamed output must be writeable and match the grid")
    if outer_full.shape != outer_shape:
        raise PhysicalDomainError("streamed outer template does not match the grid")
    if any(
        array.ndim != 2
        or array.shape[0] != collision_shape[0]
        or array.shape[1] not in (1, collision_shape[1])
        for array in (true_absorption, thermal, scattering)
    ):
        raise PhysicalDomainError("streamed collision fields do not match the grid")
    left = np.broadcast_to(
        np.asarray(left_exterior_intensity, dtype=np.float64),
        (stencil.physical_group_count, mu.size),
    )
    right = np.broadcast_to(
        np.asarray(right_exterior_intensity, dtype=np.float64),
        (stencil.physical_group_count, mu.size),
    )
    if not blocks:
        raise PhysicalDomainError("streamed source iteration requires blocks")
    if not isinstance(compute_block_diagnostics, (bool, np.bool_)):
        raise PhysicalDomainError("compute_block_diagnostics must be boolean")
    expected_start = 0
    maximum_absolute = 0.0
    maximum_scale = 0.0
    minimum_intensity = np.inf
    maximum_residual = 0.0
    maximum_ledger = 0.0
    maximum_core = 0
    maximum_collision = 0
    maximum_outer = 0
    full_active_outer_start = stencil.active_outer_group_start
    full_active_outer_stop = stencil.active_outer_group_stop
    for block in blocks:
        if block.core_group_start != expected_start:
            raise PhysicalDomainError("streamed blocks are not contiguous and ordered")
        expected_start = block.core_group_stop
        local_outer = np.array(
            outer_full[block.outer_group_start : block.outer_group_stop],
            copy=True,
        )
        physical_start = max(block.outer_group_start, full_active_outer_start)
        physical_stop = min(block.outer_group_stop, full_active_outer_stop)
        if physical_stop > physical_start:
            local_outer[
                physical_start - block.outer_group_start : physical_stop
                - block.outer_group_start
            ] = current[
                physical_start - full_active_outer_start : physical_stop
                - full_active_outer_start
            ]
        core = slice(block.core_group_start, block.core_group_stop)
        collision = slice(
            block.collision_group_start, block.collision_group_stop
        )
        result = solve_mixed_frame_ale_group_step(
            block.local_stencil,
            old_depth_edges_cm,
            new_depth_edges_cm,
            mu,
            angular_weight,
            initial[core],
            local_outer,
            true_absorption[collision],
            thermal[collision],
            scattering[collision],
            material_velocity_beta,
            duration_s,
            left_exterior_intensity=left[core],
            right_exterior_intensity=right[core],
            propagation_speed_cm_s=propagation_speed_cm_s,
            source_iteration_initial_guess=current[core],
            diagnostic_fixed_iteration_count=1,
            spatial_scheme=spatial_scheme,
            source_map_only=not bool(compute_block_diagnostics),
        )
        updated = result.final_lab_intensity_density
        output[core] = updated
        maximum_absolute = max(
            maximum_absolute, float(np.max(np.abs(updated - current[core])))
        )
        maximum_scale = max(
            maximum_scale,
            float(np.max(np.abs(updated))),
            float(np.max(np.abs(current[core]))),
        )
        minimum_intensity = min(minimum_intensity, result.minimum_intensity)
        if bool(compute_block_diagnostics):
            maximum_residual = max(
                maximum_residual, result.global_scale_normalized_coupled_residual
            )
            maximum_ledger = max(
                maximum_ledger, result.total_relative_energy_ledger_residual
            )
        maximum_core = max(maximum_core, block.local_stencil.physical_group_count)
        maximum_collision = max(
            maximum_collision,
            block.local_stencil.comoving_collision_group_count,
        )
        maximum_outer = max(
            maximum_outer, block.local_stencil.outer_lab_group_count
        )
    if expected_start != stencil.physical_group_count:
        raise PhysicalDomainError("streamed blocks do not cover all physical groups")
    relative = maximum_absolute / maximum_scale if maximum_scale > 0.0 else maximum_absolute
    return StreamedSourceIteration(
        block_count=len(blocks),
        maximum_core_group_count=maximum_core,
        maximum_collision_group_count=maximum_collision,
        maximum_outer_group_count=maximum_outer,
        maximum_absolute_change=maximum_absolute,
        maximum_relative_change=relative,
        minimum_intensity=float(minimum_intensity),
        block_diagnostics_computed=bool(compute_block_diagnostics),
        maximum_block_coupled_residual=(
            maximum_residual if bool(compute_block_diagnostics) else None
        ),
        maximum_block_energy_ledger_residual=(
            maximum_ledger if bool(compute_block_diagnostics) else None
        ),
    )
