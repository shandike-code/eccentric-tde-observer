from pathlib import Path

import numpy as np

from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil_from_active_edges,
    solve_mixed_frame_ale_group_step,
)
from eccentric_tde_observer.mixed_frame_streaming import (
    plan_mixed_frame_frequency_blocks,
    stream_mixed_frame_ale_source_iteration,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
)


def _streaming_case():
    active_edge = np.geomspace(1.0, 100.0, 42)
    stencil = mixed_frame_frequency_stencil_from_active_edges(active_edge, 0.08)
    mu, weight = gauss_legendre_mu_weights(4)
    old_edge = np.array([0.0, 0.8, 1.9, 3.0])
    face_velocity = np.array([-0.08, -0.01, 0.03, 0.09])
    new_edge = old_edge + face_velocity
    depth = old_edge.size - 1
    outer_coordinate = np.linspace(0.0, 1.0, stencil.outer_lab_group_count)
    outer = (
        0.8
        + 0.2 * outer_coordinate[:, None, None]
        + 0.03 * mu[None, :, None]
        + 0.04 * np.arange(depth)[None, None, :]
    )
    active_slice = slice(
        stencil.active_outer_group_start, stencil.active_outer_group_stop
    )
    initial = np.array(outer[active_slice], copy=True)
    current = initial * (
        0.91
        + 0.04
        * np.sin(np.linspace(0.0, 3.0, stencil.physical_group_count))[:, None, None]
    )
    collision_coordinate = np.linspace(
        0.0, 1.0, stencil.comoving_collision_group_count
    )
    depth_coordinate = np.arange(depth)[None, :]
    absorption = 0.25 + 0.08 * collision_coordinate[:, None] + 0.03 * depth_coordinate
    scattering = 0.18 + 0.02 * collision_coordinate[:, None] + 0.01 * depth_coordinate
    emissivity = absorption * (
        1.1 + 0.15 * collision_coordinate[:, None] + 0.02 * depth_coordinate
    )
    beta = np.array([-0.05, 0.01, 0.06])
    left = 0.5 + 0.03 * np.arange(stencil.physical_group_count)[:, None] / stencil.physical_group_count
    left = left + 0.01 * mu[None, :]
    right = 0.7 + 0.02 * np.arange(stencil.physical_group_count)[:, None] / stencil.physical_group_count
    right = right - 0.015 * mu[None, :]
    return {
        "stencil": stencil,
        "mu": mu,
        "weight": weight,
        "old_edge": old_edge,
        "new_edge": new_edge,
        "initial": initial,
        "outer": outer,
        "current": current,
        "absorption": absorption,
        "emissivity": emissivity,
        "scattering": scattering,
        "beta": beta,
        "left": left,
        "right": right,
    }


def test_frequency_blocks_preserve_global_edges_and_cover_every_core_group():
    case = _streaming_case()
    blocks = plan_mixed_frame_frequency_blocks(
        case["stencil"], case["mu"], case["weight"], case["beta"], 7
    )
    assert blocks[0].core_group_start == 0
    assert blocks[-1].core_group_stop == case["stencil"].physical_group_count
    for first, second in zip(blocks[:-1], blocks[1:], strict=True):
        assert first.core_group_stop == second.core_group_start
    for block in blocks:
        expected = case["stencil"].active_lab_edge_hz[
            block.core_group_start : block.core_group_stop + 1
        ]
        assert np.array_equal(block.local_stencil.active_lab_edge_hz, expected)
        assert block.local_stencil.comoving_collision_group_count >= (
            block.local_stencil.physical_group_count
        )
        assert block.local_stencil.outer_lab_group_count >= (
            block.local_stencil.comoving_collision_group_count
        )


def test_one_streamed_source_iteration_matches_monolithic_jacobi_map():
    case = _streaming_case()
    common = dict(
        left_exterior_intensity=case["left"],
        right_exterior_intensity=case["right"],
        propagation_speed_cm_s=1.0,
        spatial_scheme="hybrid_step_turning_upwind",
    )
    monolithic = solve_mixed_frame_ale_group_step(
        case["stencil"],
        case["old_edge"],
        case["new_edge"],
        case["mu"],
        case["weight"],
        case["initial"],
        case["outer"],
        case["absorption"],
        case["emissivity"],
        case["scattering"],
        case["beta"],
        1.0,
        source_iteration_initial_guess=case["current"],
        diagnostic_fixed_iteration_count=1,
        **common,
    )
    blocks = plan_mixed_frame_frequency_blocks(
        case["stencil"], case["mu"], case["weight"], case["beta"], 7
    )
    output = np.empty_like(case["current"])
    streamed = stream_mixed_frame_ale_source_iteration(
        case["stencil"],
        blocks,
        case["old_edge"],
        case["new_edge"],
        case["mu"],
        case["weight"],
        case["initial"],
        case["outer"],
        case["absorption"],
        case["emissivity"],
        case["scattering"],
        case["beta"],
        1.0,
        case["current"],
        output,
        **common,
    )
    scale = np.max(np.abs(monolithic.final_lab_intensity_density))
    error = np.max(np.abs(output - monolithic.final_lab_intensity_density)) / scale
    assert error < 2.0e-14
    expected_change = np.max(
        np.abs(monolithic.final_lab_intensity_density - case["current"])
    )
    expected_scale = max(
        np.max(np.abs(monolithic.final_lab_intensity_density)),
        np.max(np.abs(case["current"])),
    )
    assert np.isclose(streamed.maximum_absolute_change, expected_change, rtol=2.0e-14)
    assert np.isclose(
        streamed.maximum_relative_change,
        expected_change / expected_scale,
        rtol=2.0e-14,
    )
    assert streamed.block_count == 6
    assert streamed.minimum_intensity > 0.0
    assert streamed.block_diagnostics_computed is True
    assert streamed.maximum_block_coupled_residual is not None
    assert streamed.maximum_block_energy_ledger_residual is not None

    lean_output = np.empty_like(case["current"])
    lean = stream_mixed_frame_ale_source_iteration(
        case["stencil"],
        blocks,
        case["old_edge"],
        case["new_edge"],
        case["mu"],
        case["weight"],
        case["initial"],
        case["outer"],
        case["absorption"],
        case["emissivity"],
        case["scattering"],
        case["beta"],
        1.0,
        case["current"],
        lean_output,
        compute_block_diagnostics=False,
        **common,
    )
    assert np.array_equal(lean_output, output)
    assert lean.maximum_absolute_change == streamed.maximum_absolute_change
    assert lean.maximum_relative_change == streamed.maximum_relative_change
    assert lean.minimum_intensity == streamed.minimum_intensity
    assert lean.block_diagnostics_computed is False
    assert lean.maximum_block_coupled_residual is None
    assert lean.maximum_block_energy_ledger_residual is None


def test_streamed_source_iteration_writes_float64_memmap(tmp_path: Path):
    case = _streaming_case()
    blocks = plan_mixed_frame_frequency_blocks(
        case["stencil"], case["mu"], case["weight"], case["beta"], 11
    )
    path = tmp_path / "next_intensity.dat"
    output = np.memmap(path, mode="w+", dtype=np.float64, shape=case["current"].shape)
    stream_mixed_frame_ale_source_iteration(
        case["stencil"],
        blocks,
        case["old_edge"],
        case["new_edge"],
        case["mu"],
        case["weight"],
        case["initial"],
        case["outer"],
        case["absorption"],
        case["emissivity"],
        case["scattering"],
        case["beta"],
        1.0,
        case["current"],
        output,
        left_exterior_intensity=case["left"],
        right_exterior_intensity=case["right"],
        propagation_speed_cm_s=1.0,
    )
    output.flush()
    restored = np.memmap(
        path, mode="r", dtype=np.float64, shape=case["current"].shape
    )
    assert np.all(np.isfinite(restored))
    assert np.min(restored) > 0.0
