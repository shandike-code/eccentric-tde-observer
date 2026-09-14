"""Phase 7B5v：执行流式频率块与守恒 turning-ray 算子门。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil_from_active_edges,
    solve_mixed_frame_ale_group_step,
)
from eccentric_tde_observer.mixed_frame_frequency import (
    comoving_group_radiation,
)
from eccentric_tde_observer.mixed_frame_streaming import (
    plan_mixed_frame_frequency_blocks,
    stream_mixed_frame_ale_source_iteration,
)
from eccentric_tde_observer.multiresolution_frequency import (
    piecewise_constant_photoionization_rates_s1,
)
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
    gauss_legendre_split_mu_weights,
)

try:
    from scripts.phase7b4s_implicit_ale_radiation import (
        _load_material_reference,
        centred_full_column_trajectory,
    )
    from scripts.phase7b5i_partition_representation_split import (
        ITERATIVE_TOLERANCE,
        _p0_operator_context,
    )
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
    from scripts.phase7b5r_joint_convergence import (
        _collision_physical_slice,
        _subdivide_parent_edge,
    )
    from scripts.phase7b5t_characteristic_transport_gate import (
        _characteristic_quadrature,
        _load_worker_state,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b4s_implicit_ale_radiation import (  # type: ignore[no-redef]
        _load_material_reference,
        centred_full_column_trajectory,
    )
    from phase7b5i_partition_representation_split import (  # type: ignore[no-redef]
        ITERATIVE_TOLERANCE,
        _p0_operator_context,
    )
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )
    from phase7b5r_joint_convergence import (  # type: ignore[no-redef]
        _collision_physical_slice,
        _subdivide_parent_edge,
    )
    from phase7b5t_characteristic_transport_gate import (  # type: ignore[no-redef]
        _characteristic_quadrature,
        _load_worker_state,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "3eb84c561d28ad9bfd9867b11ceb05ebbc33e7b1479eadda3053e02c09c81b92"
)
MIB = 1024**2


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _sha256_array(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    fields: list[str] = []
    for row in rows:
        fields.extend(key for key in row if key not in fields)
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256_file(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B5v protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        source_path = ROOT / source["path"]
        if _sha256_file(source_path) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B5v source changed: {source_path}")
    return protocol


def _formal_context(input_path: Path):
    loaded = _load_worker_state(input_path)
    subcells = 16
    old_edge = _subdivide_parent_edge(loaded["parent_old_edge"], subcells)
    new_edge = _subdivide_parent_edge(loaded["parent_new_edge"], subcells)
    mu, weight, split_mu = _characteristic_quadrature(
        32,
        loaded["parent_old_edge"],
        loaded["parent_new_edge"],
        loaded["duration_s"],
    )
    stencil = mixed_frame_frequency_stencil_from_active_edges(
        loaded["active_edge"], loaded["maximum_beta"]
    )
    state = {
        "temperature_k": loaded["temperature_k"],
        "density_g_cm3": loaded["density_g_cm3"],
        "hydrogen_fraction": loaded["hydrogen_fraction"],
        "helium_fraction": loaded["helium_fraction"],
        "duration_s": loaded["duration_s"],
        "beta": np.repeat(loaded["parent_beta"], subcells),
    }
    initial, outer, continuum = _p0_operator_context(stencil, mu, weight, state)
    return loaded, state, stencil, old_edge, new_edge, mu, weight, split_mu, initial, outer, continuum


def _diagnostics(stencil, mu, weight, beta, intensity, outer, new_edge):
    outer_final = np.array(outer, copy=True)
    active = slice(stencil.active_outer_group_start, stencil.active_outer_group_stop)
    outer_final[active] = intensity
    comoving = comoving_group_radiation(
        outer_final,
        stencil.outer_lab_edge_hz,
        stencil.comoving_collision_edge_hz,
        mu,
        weight,
        beta,
    )
    physical = _collision_physical_slice(stencil)
    depth_width = np.diff(new_edge)
    volume_mean = np.sum(
        comoving.mean_intensity_density[physical] * depth_width[None, :], axis=1
    ) / np.sum(depth_width)
    frequency_width = np.diff(stencil.active_lab_edge_hz)
    rates = piecewise_constant_photoionization_rates_s1(
        stencil.active_lab_edge_hz,
        volume_mean,
        quadrature_order_per_group=16,
    )
    lab_mean = 0.5 * np.einsum("m,fmd->fd", weight, intensity)
    energy_group = 4.0 * np.pi / LIGHT_SPEED_CM_S * np.sum(
        lab_mean * depth_width[None, :], axis=1
    )
    scalars = {
        "frequency_integrated_volume_mean_comoving_intensity": float(
            np.sum(frequency_width * volume_mean)
        ),
        "h_i_photoionization_rate_s1": float(rates[0]),
        "he_i_photoionization_rate_s1": float(rates[1]),
        "he_ii_photoionization_rate_s1": float(rates[2]),
        "final_radiation_energy_erg_cm2": float(
            np.sum(frequency_width * energy_group)
        ),
    }
    return scalars, volume_mean


def run_worker(protocol_path: Path, mode: str, output_dir: Path) -> None:
    protocol = _load_protocol(protocol_path)
    input_path = ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]
    (
        loaded,
        state,
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        split_mu,
        initial,
        outer,
        continuum,
    ) = _formal_context(input_path)
    baseline = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    iteration_rows = []
    if mode == "monolithic":
        result = solve_mixed_frame_ale_group_step(
            stencil,
            old_edge,
            new_edge,
            mu,
            weight,
            initial,
            outer,
            continuum.true_absorption_total_per_cm,
            continuum.thermal_emissivity_total_cgs,
            continuum.electron_scattering_per_cm,
            state["beta"],
            state["duration_s"],
            iterative_tolerance=ITERATIVE_TOLERANCE,
            iterative_maximum_iterations=8192,
            spatial_scheme="step_characteristics",
        )
        final = np.array(result.final_lab_intensity_density, copy=True)
        iterations = result.fixed_point_iterations
        final_change = result.final_fixed_point_change
        converged = result.fixed_point_converged
        maximum_block_residual = result.global_scale_normalized_coupled_residual
        maximum_block_ledger = result.total_relative_energy_ledger_residual
        block_count = 1
        maximum_collision_groups = stencil.comoving_collision_group_count
        maximum_outer_groups = stencil.outer_lab_group_count
    else:
        core_groups = int(mode.removeprefix("stream"))
        blocks = plan_mixed_frame_frequency_blocks(
            stencil, mu, weight, state["beta"], core_groups
        )
        current = np.array(initial, copy=True)
        following = np.empty_like(current)
        converged = False
        maximum_block_residual = 0.0
        maximum_block_ledger = 0.0
        for iteration in range(1, 8193):
            diagnostic = stream_mixed_frame_ale_source_iteration(
                stencil,
                blocks,
                old_edge,
                new_edge,
                mu,
                weight,
                initial,
                outer,
                continuum.true_absorption_total_per_cm,
                continuum.thermal_emissivity_total_cgs,
                continuum.electron_scattering_per_cm,
                state["beta"],
                state["duration_s"],
                current,
                following,
                propagation_speed_cm_s=LIGHT_SPEED_CM_S,
                spatial_scheme="hybrid_step_turning_upwind",
            )
            iteration_rows.append(
                {
                    "configuration": mode,
                    "iteration": iteration,
                    "maximum_relative_change": diagnostic.maximum_relative_change,
                }
            )
            maximum_block_residual = max(
                maximum_block_residual,
                diagnostic.maximum_block_coupled_residual,
            )
            maximum_block_ledger = max(
                maximum_block_ledger,
                diagnostic.maximum_block_energy_ledger_residual,
            )
            current, following = following, current
            if diagnostic.maximum_relative_change <= ITERATIVE_TOLERANCE:
                converged = True
                break
        if not converged:
            raise ArithmeticError(f"{mode} global block Jacobi did not converge")
        final = current
        iterations = iteration
        final_change = diagnostic.maximum_relative_change
        block_count = len(blocks)
        maximum_collision_groups = max(
            block.local_stencil.comoving_collision_group_count for block in blocks
        )
        maximum_outer_groups = max(
            block.local_stencil.outer_lab_group_count for block in blocks
        )
    runtime = time.perf_counter() - started
    peak = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    scalars, volume_mean = _diagnostics(
        stencil, mu, weight, state["beta"], final, outer, new_edge
    )
    state_path = output_dir / f"phase7b5v_{mode}_state.npz"
    np.savez_compressed(
        state_path,
        final_lab_intensity_density=final,
        volume_mean_comoving_intensity=volume_mean,
        active_edge_hz=stencil.active_lab_edge_hz,
    )
    report = {
        "configuration": mode,
        "pid": os.getpid(),
        "physical_group_count": stencil.physical_group_count,
        "active_edge_sha256": hashlib.sha256(
            np.ascontiguousarray(stencil.active_lab_edge_hz).tobytes()
        ).hexdigest(),
        "angular_direction_count": mu.size,
        "radiation_subcells": np.diff(new_edge).size,
        "angular_split_mu": split_mu,
        "block_count": block_count,
        "maximum_collision_groups_per_block": maximum_collision_groups,
        "maximum_outer_groups_per_block": maximum_outer_groups,
        "fixed_point_iterations": iterations,
        "final_fixed_point_change": final_change,
        "fixed_point_converged": converged,
        "maximum_block_coupled_residual": maximum_block_residual,
        "maximum_block_energy_ledger_residual": maximum_block_ledger,
        "minimum_intensity": float(np.min(final)),
        "runtime_s": runtime,
        "baseline_highwater_rss_mib": baseline / MIB,
        "peak_process_rss_mib": peak / MIB,
        "operator_highwater_increase_mib": max(0, peak - baseline) / MIB,
        "final_intensity_sha256": _sha256_array(final),
        "state_path": str(state_path.relative_to(ROOT)),
        **scalars,
    }
    _write_json_atomic(output_dir / f"phase7b5v_{mode}.json", report)
    if iteration_rows:
        _write_csv(output_dir / f"phase7b5v_{mode}_iterations.csv", iteration_rows)
    print(json.dumps(report, indent=2), flush=True)


def _turning_controls() -> dict[str, object]:
    stencil = mixed_frame_frequency_stencil_from_active_edges([1.0, 2.0], 0.0)
    mu, weight = gauss_legendre_mu_weights(2)
    old_edge = np.array([0.0, 1.0, 2.0, 3.0])
    face_velocity = np.array([-0.8, -0.25, 0.25, 0.8])
    new_edge = old_edge + face_velocity
    initial = np.array([[[0.3, 0.4, 0.5], [0.6, 0.5, 0.4]]])
    absorption = np.array([[0.2, 0.4, 0.6]])
    emissivity = np.array([[0.7, 0.8, 0.9]])
    left = np.array([[0.25, 0.35]])
    right = np.array([[0.45, 0.55]])
    result = solve_mixed_frame_ale_group_step(
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        initial,
        initial,
        absorption,
        emissivity,
        0.0,
        np.zeros(3),
        1.0,
        left_exterior_intensity=left,
        right_exterior_intensity=right,
        propagation_speed_cm_s=1.0,
        spatial_scheme="hybrid_step_turning_upwind",
        iterative_tolerance=2.0e-13,
    )
    expected = np.empty_like(initial)
    old_width = np.diff(old_edge)
    new_width = np.diff(new_edge)
    for angle, cosine in enumerate(mu):
        speed = cosine - face_velocity
        matrix = np.zeros((3, 3))
        rhs = old_width * initial[0, angle] + new_width * emissivity[0]
        for depth in range(3):
            matrix[depth, depth] = (
                new_width[depth]
                + new_width[depth] * absorption[0, depth]
                + max(speed[depth + 1], 0.0)
                - min(speed[depth], 0.0)
            )
            if depth > 0:
                matrix[depth, depth - 1] = -max(speed[depth], 0.0)
            if depth < 2:
                matrix[depth, depth + 1] = min(speed[depth + 1], 0.0)
        if speed[0] > 0.0:
            rhs[0] += speed[0] * left[0, angle]
        if speed[-1] < 0.0:
            rhs[-1] -= speed[-1] * right[0, angle]
        expected[0, angle] = np.linalg.solve(matrix, rhs)
    dense_error = float(
        np.max(np.abs(result.final_lab_intensity_density - expected))
    )

    mu4, weight4 = gauss_legendre_mu_weights(4)
    edge = np.linspace(0.0, 1.0, 6)
    initial4 = np.full((1, mu4.size, 5), 0.4)
    absorption4 = np.full((1, 5), 0.7)
    common = dict(
        left_exterior_intensity=0.2,
        right_exterior_intensity=0.8,
        propagation_speed_cm_s=1.0,
        iterative_tolerance=2.0e-13,
    )
    step = solve_mixed_frame_ale_group_step(
        stencil,
        edge,
        edge,
        mu4,
        weight4,
        initial4,
        initial4,
        absorption4,
        1.3 * absorption4,
        0.0,
        np.zeros(5),
        0.5,
        spatial_scheme="step_characteristics",
        **common,
    )
    hybrid = solve_mixed_frame_ale_group_step(
        stencil,
        edge,
        edge,
        mu4,
        weight4,
        initial4,
        initial4,
        absorption4,
        1.3 * absorption4,
        0.0,
        np.zeros(5),
        0.5,
        spatial_scheme="hybrid_step_turning_upwind",
        **common,
    )
    return {
        "turning_dense_system_maximum_absolute_error": dense_error,
        "turning_global_coupled_residual": (
            result.global_scale_normalized_coupled_residual
        ),
        "turning_energy_ledger_residual": (
            result.total_relative_energy_ledger_residual
        ),
        "turning_minimum_intensity": result.minimum_intensity,
        "nonturning_hybrid_equals_step_exactly": bool(
            np.array_equal(
                hybrid.final_lab_intensity_density,
                step.final_lab_intensity_density,
            )
        ),
    }


def _one_iteration_streaming_control(protocol: dict[str, object]) -> float:
    input_path = ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]
    (
        _loaded,
        state,
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        _split_mu,
        initial,
        outer,
        continuum,
    ) = _formal_context(input_path)
    reference = solve_mixed_frame_ale_group_step(
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        initial,
        outer,
        continuum.true_absorption_total_per_cm,
        continuum.thermal_emissivity_total_cgs,
        continuum.electron_scattering_per_cm,
        state["beta"],
        state["duration_s"],
        propagation_speed_cm_s=LIGHT_SPEED_CM_S,
        source_iteration_initial_guess=initial,
        diagnostic_fixed_iteration_count=1,
        spatial_scheme="step_characteristics",
    )
    blocks = plan_mixed_frame_frequency_blocks(
        stencil, mu, weight, state["beta"], 256
    )
    output = np.empty_like(initial)
    stream_mixed_frame_ale_source_iteration(
        stencil,
        blocks,
        old_edge,
        new_edge,
        mu,
        weight,
        initial,
        outer,
        continuum.true_absorption_total_per_cm,
        continuum.thermal_emissivity_total_cgs,
        continuum.electron_scattering_per_cm,
        state["beta"],
        state["duration_s"],
        initial,
        output,
        propagation_speed_cm_s=LIGHT_SPEED_CM_S,
        spatial_scheme="hybrid_step_turning_upwind",
    )
    scale = max(
        float(np.max(np.abs(output))),
        float(np.max(np.abs(reference.final_lab_intensity_density))),
    )
    difference = float(
        np.max(np.abs(output - reference.final_lab_intensity_density))
    )
    return difference / scale if scale > 0.0 else difference


def _full_column_block_plan(protocol: dict[str, object], stencil):
    material = _load_material_reference(
        ROOT / protocol["sources"]["phase7b4r_material"]["path"]
    )
    full = centred_full_column_trajectory(material)
    face_beta = (
        np.roll(full["edges_cm"], -1, axis=0) - full["edges_cm"]
    ) / (material["step_duration_s"][:, None] * LIGHT_SPEED_CM_S)
    phase = int(np.unravel_index(np.argmax(np.abs(face_beta)), face_beta.shape)[0])
    parent_beta = 0.5 * (face_beta[phase, :-1] + face_beta[phase, 1:])
    beta = np.repeat(parent_beta, 16)
    mu, weight = gauss_legendre_split_mu_weights(32, 0.0)
    rows = []
    for core in (128, 256, 512):
        blocks = plan_mixed_frame_frequency_blocks(
            stencil, mu, weight, beta, core
        )
        maximum_collision = max(
            block.local_stencil.comoving_collision_group_count for block in blocks
        )
        maximum_outer = max(
            block.local_stencil.outer_lab_group_count for block in blocks
        )
        depth = 4096
        angle = 32
        active = min(core, stencil.physical_group_count)
        identified_bytes = 8 * angle * (
            5 * active * depth
            + 2 * maximum_outer * depth
            + maximum_collision * depth
            + active * (depth + 1)
        )
        rows.append(
            {
                "core_frequency_groups": core,
                "block_count": len(blocks),
                "maximum_collision_groups": maximum_collision,
                "maximum_outer_groups": maximum_outer,
                "identified_live_array_gib": identified_bytes / 1024**3,
            }
        )
    return phase, rows


def _scale_error(candidate: float, reference: float) -> float:
    scale = max(abs(candidate), abs(reference))
    return abs(candidate - reference) / scale if scale > 0.0 else abs(candidate - reference)


def _plot(
    path: Path,
    comparisons,
    reports,
    spectra,
    block_rows,
    edge,
    one_iteration_error: float,
    gates: dict[str, object],
):
    fig, axes = plt.subplots(2, 2, figsize=(12.2, 8.4), constrained_layout=True)
    keys = ["stream256", "stream512"]
    axes[0, 0].bar(
        ["One map\nstream256", "Fixed point\nstream256", "Fixed point\nstream512"],
        [
            one_iteration_error
            / gates["small_one_iteration_stream_vs_monolithic_strictly_below"],
            comparisons["stream256"]["maximum_error"]
            / gates["actual_lab_intensity_maximum_error_strictly_below"],
            comparisons["stream512"]["maximum_error"]
            / gates["actual_lab_intensity_maximum_error_strictly_below"],
        ],
        color=["C3", "C0", "C1"],
    )
    axes[0, 0].axhline(1.0, color="0.25", ls="--", label="Gate")
    axes[0, 0].set_yscale("log")
    axes[0, 0].set_ylabel("Error / pre-registered gate")
    axes[0, 0].set_title("(a) Pre-registered equivalence gates")
    axes[0, 0].legend(frameon=False)

    centre = np.sqrt(edge[:-1] * edge[1:])
    reference = spectra["monolithic"]
    for key, color in zip(keys, ("C0", "C1"), strict=True):
        axes[0, 1].plot(
            centre,
            (spectra[key] - reference) / np.max(reference),
            color=color,
            lw=0.9,
            label=key,
        )
    axes[0, 1].set_xscale("log")
    axes[0, 1].set_xlabel("Frequency (Hz)")
    axes[0, 1].set_ylabel("Signed difference / reference peak")
    axes[0, 1].set_title("(b) Volume-mean comoving spectrum")
    axes[0, 1].legend(frameon=False)

    x = np.arange(3)
    labels = ["Monolithic", "Stream 256", "Stream 512"]
    modes = ["monolithic", "stream256", "stream512"]
    width = 0.38
    runtime_bars = axes[1, 0].bar(
        x - width / 2,
        [reports[key]["runtime_s"] for key in modes],
        width,
        label="Runtime (s)",
    )
    second = axes[1, 0].twinx()
    rss_bars = second.bar(
        x + width / 2,
        [reports[key]["peak_process_rss_mib"] for key in modes],
        width,
        color="C3",
        label="Peak RSS (MiB)",
    )
    axes[1, 0].set_xticks(x, labels)
    axes[1, 0].set_ylabel("Runtime (s)")
    second.set_ylabel("Peak RSS (MiB)")
    axes[1, 0].set_title("(c) Actual one-cell cost")
    axes[1, 0].legend(
        (runtime_bars[0], rss_bars[0]),
        ("Runtime", "Peak RSS"),
        frameon=False,
        loc="upper center",
    )

    core = np.array([row["core_frequency_groups"] for row in block_rows])
    collision = np.array([row["maximum_collision_groups"] for row in block_rows])
    outer = np.array([row["maximum_outer_groups"] for row in block_rows])
    axes[1, 1].plot(core, core, marker="o", label="Core")
    axes[1, 1].plot(core, collision, marker="s", label="Collision halo")
    axes[1, 1].plot(core, outer, marker="^", label="Outer halo")
    axes[1, 1].set_xlabel("Core frequency groups")
    axes[1, 1].set_ylabel("Maximum local group count")
    axes[1, 1].set_title("(d) Exact full-column Doppler halos")
    axes[1, 1].legend(frameon=False)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run(
    protocol_path: Path, output_dir: Path, *, reuse_workers: bool = False
) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    modes = ("monolithic", "stream256", "stream512")
    for mode in modes:
        report_path = output_dir / f"phase7b5v_{mode}.json"
        state_path = output_dir / f"phase7b5v_{mode}_state.npz"
        if reuse_workers and report_path.exists() and state_path.exists():
            continue
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--protocol",
            str(protocol_path),
            "--output-dir",
            str(output_dir),
            "--worker",
            mode,
        ]
        completed = subprocess.run(command, cwd=ROOT, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"Phase 7B5v worker failed: {mode}")
    reports = {
        mode: json.loads(
            (output_dir / f"phase7b5v_{mode}.json").read_text(encoding="utf-8")
        )
        for mode in modes
    }
    states = {}
    spectra = {}
    edge = None
    for mode in modes:
        with np.load(output_dir / f"phase7b5v_{mode}_state.npz") as data:
            states[mode] = np.array(data["final_lab_intensity_density"], copy=True)
            spectra[mode] = np.array(data["volume_mean_comoving_intensity"], copy=True)
            candidate_edge = np.array(data["active_edge_hz"], copy=True)
        if edge is None:
            edge = candidate_edge
        elif not np.array_equal(edge, candidate_edge):
            raise RuntimeError("Phase 7B5v worker frequency edges differ")
    frequency_width = np.diff(edge)
    comparisons = {}
    scalar_names = (
        "frequency_integrated_volume_mean_comoving_intensity",
        "h_i_photoionization_rate_s1",
        "he_i_photoionization_rate_s1",
        "he_ii_photoionization_rate_s1",
        "final_radiation_energy_erg_cm2",
    )
    error_rows = []
    for mode in modes[1:]:
        intensity_scale = max(
            float(np.max(np.abs(states[mode]))),
            float(np.max(np.abs(states["monolithic"]))),
        )
        intensity_error = float(
            np.max(np.abs(states[mode] - states["monolithic"])) / intensity_scale
        )
        spectrum_numerator = float(
            np.sum(frequency_width * np.abs(spectra[mode] - spectra["monolithic"]))
        )
        spectrum_scale = max(
            float(np.sum(frequency_width * np.abs(spectra[mode]))),
            float(np.sum(frequency_width * np.abs(spectra["monolithic"]))),
        )
        spectrum_error = spectrum_numerator / spectrum_scale
        errors = {
            "final_lab_intensity_maximum": intensity_error,
            "volume_mean_comoving_spectrum_l1": spectrum_error,
            **{
                name: _scale_error(reports[mode][name], reports["monolithic"][name])
                for name in scalar_names
            },
        }
        comparisons[mode] = {
            "candidate": mode,
            "reference": "monolithic",
            "errors": errors,
            "maximum_error": max(errors.values()),
            "worst_observable": max(errors, key=errors.get),
        }
        error_rows.extend(
            {
                "candidate": mode,
                "reference": "monolithic",
                "observable": name,
                "relative_error": value,
            }
            for name, value in errors.items()
        )
    turning = _turning_controls()
    one_iteration_error = _one_iteration_streaming_control(protocol)
    master = _load_worker_state(
        ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]
    )
    stencil = mixed_frame_frequency_stencil_from_active_edges(
        master["active_edge"], master["maximum_beta"]
    )
    planning_phase, block_rows = _full_column_block_plan(protocol, stencil)
    _write_csv(output_dir / "phase7b5v_equivalence_errors.csv", error_rows)
    _write_csv(output_dir / "phase7b5v_full_column_block_plan.csv", block_rows)
    gates = protocol["gates"]
    _plot(
        output_dir / "phase7b5v_streaming_turning_gate.png",
        comparisons,
        reports,
        spectra,
        block_rows,
        edge,
        one_iteration_error,
        gates,
    )
    active_hashes = {report["active_edge_sha256"] for report in reports.values()}
    expected_active_hash = hashlib.sha256(np.ascontiguousarray(edge).tobytes()).hexdigest()
    decision = {
        "frozen_protocol_hash_passed": True,
        "frozen_source_hashes_passed": True,
        "all_fixed_points_converged": all(
            report["fixed_point_converged"] for report in reports.values()
        ),
        "all_fixed_point_changes_passed": all(
            report["final_fixed_point_change"]
            <= gates["actual_fixed_point_tolerance"]
            for report in reports.values()
        ),
        "all_intensities_nonnegative": all(
            report["minimum_intensity"] >= gates["minimum_intensity_at_least"]
            for report in reports.values()
        ),
        "turning_dense_system_passed": turning[
            "turning_dense_system_maximum_absolute_error"
        ]
        < gates["turning_dense_system_maximum_error_strictly_below"],
        "turning_residual_passed": turning["turning_global_coupled_residual"]
        < gates["turning_coupled_residual_strictly_below"],
        "turning_ledger_passed": turning["turning_energy_ledger_residual"]
        < gates["turning_energy_ledger_strictly_below"],
        "nonturning_exact_passed": turning[
            "nonturning_hybrid_equals_step_exactly"
        ],
        "small_one_iteration_equivalence_passed": one_iteration_error
        < gates["small_one_iteration_stream_vs_monolithic_strictly_below"],
        "actual_intensity_equivalence_passed": all(
            comparison["errors"]["final_lab_intensity_maximum"]
            < gates["actual_lab_intensity_maximum_error_strictly_below"]
            for comparison in comparisons.values()
        ),
        "actual_spectrum_equivalence_passed": all(
            comparison["errors"]["volume_mean_comoving_spectrum_l1"]
            < gates["actual_volume_spectrum_l1_strictly_below"]
            for comparison in comparisons.values()
        ),
        "actual_scalar_equivalence_passed": all(
            error < gates["actual_scalar_observable_error_strictly_below"]
            for comparison in comparisons.values()
            for name, error in comparison["errors"].items()
            if name not in (
                "final_lab_intensity_maximum",
                "volume_mean_comoving_spectrum_l1",
            )
        ),
        "resource_gate_passed": all(
            report["peak_process_rss_mib"]
            < gates["actual_worker_peak_rss_strictly_below_mib"]
            for report in reports.values()
        ),
        "physical_group_count_exact": all(
            report["physical_group_count"]
            == gates["physical_group_count_exactly"]
            for report in reports.values()
        ),
        "global_active_edge_hash_unchanged": active_hashes
        == {expected_active_hash},
    }
    decision["phase7b5v_gate_passed"] = bool(all(decision.values()))
    decision["full_depth_block_resource_probe_authorized"] = decision[
        "phase7b5v_gate_passed"
    ]
    decision["full_orbit_authorized"] = False
    decision["matter_feedback_authorized"] = False
    decision["phase4_replacement_authorized"] = False
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_path": str(protocol_path),
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "turning_controls": turning,
        "one_iteration_streaming_control": {
            "core_frequency_groups": 256,
            "maximum_relative_intensity_error": one_iteration_error,
        },
        "runs": reports,
        "comparisons": comparisons,
        "full_column_block_planning": {
            "worst_mesh_velocity_phase_index": planning_phase,
            "rows": block_rows,
            "status": "planning only; no full-depth allocation in Phase 7B5v",
        },
        "decision": decision,
        "interpretation": {
            "verified": (
                "turning directions are retained by a conservative implicit solve; "
                "streaming preserves the full 9632-group fixed point"
            ),
            "not_yet_verified": (
                "actual full-depth peak RSS, full-column convergence and orbit"
            ),
            "iteration_residual_note": (
                "worker maximum_block residual fields are envelopes over all "
                "unconverged global iterations and are not final-solution gates"
            ),
        },
        "figures": ["phase7b5v_streaming_turning_gate.png"],
    }
    _write_json_atomic(output_dir / "phase7b5v_streaming_turning_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b5v_preregistered_streaming_turning_protocol.json",
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--worker", choices=("monolithic", "stream256", "stream512"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--reuse-workers", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.worker is not None:
        run_worker(args.protocol, args.worker, args.output_dir)
        return
    summary_path = args.output_dir / "phase7b5v_streaming_turning_summary.json"
    if summary_path.exists() and not args.force:
        raise FileExistsError(f"refusing to overwrite {summary_path}; pass --force")
    summary = run(
        args.protocol, args.output_dir, reuse_workers=bool(args.reuse_workers)
    )
    print(json.dumps(summary["decision"], indent=2), flush=True)


if __name__ == "__main__":
    main()
