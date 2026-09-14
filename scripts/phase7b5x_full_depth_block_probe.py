"""Phase 7B5x：实测正式 4096 深度最坏频率块的资源与数值状态。"""

from __future__ import annotations

import argparse
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
from eccentric_tde_observer.mixed_frame_frequency import lorentz_ray_transform
from eccentric_tde_observer.mixed_frame_streaming import (
    plan_mixed_frame_frequency_blocks,
)
from eccentric_tde_observer.multigroup_continuum import (
    gauss_legendre_frequency_group_quadrature,
    ground_state_milne_multigroup,
    group_average_from_quadrature_nodes,
)
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S, planck_nu
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_split_mu_weights,
)

try:
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "6343427638c3109463ab6b92218848636675207147f186fb895bedf1f64919bb"
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


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256_file(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B5x protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256_file(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B5x source changed: {source['path']}")
    return protocol


def _load_material(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as archive:
        material = {name: np.array(archive[name], copy=True) for name in archive.files}
    expected = (2048, 128)
    if material["density_g_cm3"].shape != expected:
        raise RuntimeError("Phase 7B5x requires the frozen N128x2048 material state")
    if material["temperature_k"].shape != expected:
        raise RuntimeError("frozen temperature shape changed")
    if material["hydrogen_fraction"].shape != (*expected, 2):
        raise RuntimeError("frozen hydrogen shape changed")
    if material["helium_fraction"].shape != (*expected, 3):
        raise RuntimeError("frozen helium shape changed")
    if not all(
        np.all(np.isfinite(value))
        for value in material.values()
        if np.issubdtype(value.dtype, np.number)
    ):
        raise RuntimeError("frozen material contains non-finite values")
    return material


def _full_column(material: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    half_width = material["cell_mass_g_cm2"][None, :] / material["density_g_cm3"]
    full_width = np.concatenate((half_width, half_width[:, ::-1]), axis=1)
    half_thickness = np.sum(half_width, axis=1)
    edge = np.concatenate(
        (
            -half_thickness[:, None],
            -half_thickness[:, None] + np.cumsum(full_width, axis=1),
        ),
        axis=1,
    )

    def mirror(value: np.ndarray) -> np.ndarray:
        return np.concatenate((value, value[:, ::-1]), axis=1)

    scale = float(np.max(half_thickness))
    if float(np.max(np.abs(edge[:, 128]))) / scale > 2.0e-15:
        raise ArithmeticError("centred full column lost its midplane")
    return {
        "edge_cm": edge,
        "density_g_cm3": mirror(material["density_g_cm3"]),
        "temperature_k": mirror(material["temperature_k"]),
        "hydrogen_fraction": np.concatenate(
            (
                material["hydrogen_fraction"],
                material["hydrogen_fraction"][:, ::-1],
            ),
            axis=1,
        ),
        "helium_fraction": np.concatenate(
            (
                material["helium_fraction"],
                material["helium_fraction"][:, ::-1],
            ),
            axis=1,
        ),
    }


def _subdivide_column_edge(parent_edge: np.ndarray, subcells: int) -> np.ndarray:
    fraction = np.linspace(0.0, 1.0, int(subcells) + 1)
    cell_edge = parent_edge[:-1, None] + np.diff(parent_edge)[:, None] * fraction
    return np.concatenate((cell_edge[:, :-1].reshape(-1), parent_edge[-1:]))


def _parent_group_planck(edge: np.ndarray, temperature: np.ndarray) -> np.ndarray:
    quadrature = gauss_legendre_frequency_group_quadrature(
        edge, order_per_group=16
    )
    node = planck_nu(
        quadrature.node_hz[:, :, None], temperature[None, None, :]
    )
    return np.asarray(group_average_from_quadrature_nodes(node, quadrature))


def _parent_boosted_planck_outer(
    edge: np.ndarray,
    mu: np.ndarray,
    weight: np.ndarray,
    parent_beta: np.ndarray,
    parent_temperature: np.ndarray,
) -> np.ndarray:
    quadrature = gauss_legendre_frequency_group_quadrature(
        edge, order_per_group=16
    )
    transform = lorentz_ray_transform(mu, weight, parent_beta)
    outer = np.empty((edge.size - 1, mu.size, parent_beta.size))
    # 中文：物质状态在每个父单元内恒定，先在 256 个父单元精确求积再复制到辐射子格。
    for angle in range(mu.size):
        doppler = transform.doppler_lab_to_comoving[angle]
        node = doppler[None, None, :] ** -3 * planck_nu(
            quadrature.node_hz[:, :, None] * doppler[None, None, :],
            parent_temperature[None, None, :],
        )
        outer[:, angle] = group_average_from_quadrature_nodes(node, quadrature)
    return outer


def _context(protocol: dict[str, object]) -> dict[str, object]:
    material = _load_material(ROOT / protocol["sources"]["phase7b4r_material"]["path"])
    full = _full_column(material)
    following_edge = np.roll(full["edge_cm"], -1, axis=0)
    face_beta = (following_edge - full["edge_cm"]) / (
        material["step_duration_s"][:, None] * LIGHT_SPEED_CM_S
    )
    phase = int(np.unravel_index(np.argmax(np.abs(face_beta)), face_beta.shape)[0])
    following = (phase + 1) % face_beta.shape[0]
    duration = float(material["step_duration_s"][phase])
    parent_beta = 0.5 * (face_beta[phase, :-1] + face_beta[phase, 1:])
    beta = np.repeat(parent_beta, 16)
    mu, weight = gauss_legendre_split_mu_weights(32, 0.0)
    with np.load(ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]) as data:
        active_edge = np.array(data["active_edge_hz"], copy=True)
        maximum_beta = float(data["maximum_beta"])
    stencil = mixed_frame_frequency_stencil_from_active_edges(
        active_edge, maximum_beta
    )
    blocks = plan_mixed_frame_frequency_blocks(stencil, mu, weight, beta, 128)
    rows = []
    for index, block in enumerate(blocks):
        active = block.local_stencil.physical_group_count
        collision = block.local_stencil.comoving_collision_group_count
        outer = block.local_stencil.outer_lab_group_count
        identified = 8 * mu.size * (
            5 * active * beta.size
            + 2 * outer * beta.size
            + collision * beta.size
            + active * (beta.size + 1)
        )
        rows.append((identified, index, block))
    identified_bytes, block_index, selected = max(rows, key=lambda row: row[0])
    return {
        "material": material,
        "full": full,
        "face_beta": face_beta,
        "phase": phase,
        "following": following,
        "duration_s": duration,
        "parent_beta": parent_beta,
        "beta": beta,
        "mu": mu,
        "weight": weight,
        "stencil": stencil,
        "blocks": blocks,
        "selected": selected,
        "selected_block_index": block_index,
        "identified_live_bytes": identified_bytes,
    }


def _parent_replication_control(context: dict[str, object]) -> dict[str, object]:
    full = context["full"]
    phase = int(context["phase"])
    block = context["selected"]
    edge = block.local_stencil.comoving_collision_edge_hz[:9]
    indices = np.array([0, 127, 255])
    density = full["density_g_cm3"][phase, indices]
    temperature = full["temperature_k"][phase, indices]
    hydrogen = full["hydrogen_fraction"][phase, indices]
    helium = full["helium_fraction"][phase, indices]
    parent_mean = _parent_group_planck(edge, temperature)
    parent = ground_state_milne_multigroup(
        density,
        temperature,
        edge,
        parent_mean,
        hydrogen[:, 0],
        hydrogen[:, 1],
        helium[:, 0],
        helium[:, 1],
        helium[:, 2],
        order_per_group=16,
    ).continuum
    repeat = 2
    direct = ground_state_milne_multigroup(
        np.repeat(density, repeat),
        np.repeat(temperature, repeat),
        edge,
        np.repeat(parent_mean, repeat, axis=1),
        np.repeat(hydrogen[:, 0], repeat),
        np.repeat(hydrogen[:, 1], repeat),
        np.repeat(helium[:, 0], repeat),
        np.repeat(helium[:, 1], repeat),
        np.repeat(helium[:, 2], repeat),
        order_per_group=16,
    ).continuum
    errors = {}
    for name in (
        "true_absorption_total_per_cm",
        "thermal_emissivity_total_cgs",
        "electron_scattering_per_cm",
    ):
        expected = np.repeat(np.asarray(getattr(parent, name)), repeat, axis=1)
        actual = np.asarray(getattr(direct, name))
        scale = max(float(np.max(np.abs(expected))), float(np.max(np.abs(actual))))
        difference = float(np.max(np.abs(expected - actual)))
        errors[name] = difference / scale if scale > 0.0 else difference
    return {
        "depth_indices": indices.tolist(),
        "frequency_group_count": 8,
        "repeat_count": repeat,
        "relative_errors": errors,
        "maximum_relative_error": max(errors.values()),
    }


def run_worker(protocol_path: Path, output_path: Path) -> None:
    protocol = _load_protocol(protocol_path)
    baseline = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    total_started = time.perf_counter()
    context = _context(protocol)
    block = context["selected"]
    local = block.local_stencil
    full = context["full"]
    phase = int(context["phase"])
    following = int(context["following"])
    parent_temperature = full["temperature_k"][phase]
    parent_density = full["density_g_cm3"][phase]
    parent_hydrogen = full["hydrogen_fraction"][phase]
    parent_helium = full["helium_fraction"][phase]

    microphysics_started = time.perf_counter()
    parent_planck = _parent_group_planck(
        local.comoving_collision_edge_hz, parent_temperature
    )
    parent_microphysics = ground_state_milne_multigroup(
        parent_density,
        parent_temperature,
        local.comoving_collision_edge_hz,
        parent_planck,
        parent_hydrogen[:, 0],
        parent_hydrogen[:, 1],
        parent_helium[:, 0],
        parent_helium[:, 1],
        parent_helium[:, 2],
        order_per_group=16,
    ).continuum
    true_absorption = np.repeat(
        parent_microphysics.true_absorption_total_per_cm, 16, axis=1
    )
    thermal_emissivity = np.repeat(
        parent_microphysics.thermal_emissivity_total_cgs, 16, axis=1
    )
    scattering = np.repeat(
        parent_microphysics.electron_scattering_per_cm, 16, axis=1
    )
    microphysics_runtime = time.perf_counter() - microphysics_started
    after_microphysics = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )

    field_started = time.perf_counter()
    parent_outer = _parent_boosted_planck_outer(
        local.outer_lab_edge_hz,
        context["mu"],
        context["weight"],
        context["parent_beta"],
        parent_temperature,
    )
    outer = np.repeat(parent_outer, 16, axis=2)
    active = slice(local.active_outer_group_start, local.active_outer_group_stop)
    initial = np.array(outer[active], copy=True)
    old_edge = _subdivide_column_edge(full["edge_cm"][phase], 16)
    new_edge = _subdivide_column_edge(full["edge_cm"][following], 16)
    field_runtime = time.perf_counter() - field_started
    after_fields = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )

    operator_started = time.perf_counter()
    result = solve_mixed_frame_ale_group_step(
        local,
        old_edge,
        new_edge,
        context["mu"],
        context["weight"],
        initial,
        outer,
        true_absorption,
        thermal_emissivity,
        scattering,
        context["beta"],
        context["duration_s"],
        propagation_speed_cm_s=LIGHT_SPEED_CM_S,
        source_iteration_initial_guess=initial,
        diagnostic_fixed_iteration_count=1,
        spatial_scheme="hybrid_step_turning_upwind",
    )
    operator_runtime = time.perf_counter() - operator_started
    peak = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    mesh_velocity = (new_edge - old_edge) / context["duration_s"]
    relative_characteristic = (
        LIGHT_SPEED_CM_S * context["mu"][:, None] - mesh_velocity[None, :]
    )
    turning = np.min(relative_characteristic, axis=1) < 0.0
    turning &= np.max(relative_characteristic, axis=1) > 0.0
    diagnostics = np.array(
        [
            result.minimum_intensity,
            result.global_scale_normalized_coupled_residual,
            result.total_relative_energy_ledger_residual,
            result.final_fixed_point_change,
        ]
    )
    report = {
        "pid": os.getpid(),
        "platform": sys.platform,
        "phase_index": phase,
        "following_phase_index": following,
        "duration_s": context["duration_s"],
        "maximum_face_velocity_beta": float(
            np.max(np.abs(context["face_beta"][phase]))
        ),
        "maximum_parent_material_velocity_beta": float(
            np.max(np.abs(context["parent_beta"]))
        ),
        "physical_frequency_groups": context["stencil"].physical_group_count,
        "active_edge_sha256": _sha256_array(context["stencil"].active_lab_edge_hz),
        "core_frequency_groups": local.physical_group_count,
        "core_group_start": block.core_group_start,
        "core_group_stop": block.core_group_stop,
        "collision_group_count": local.comoving_collision_group_count,
        "outer_group_count": local.outer_lab_group_count,
        "block_index": context["selected_block_index"],
        "block_count": len(context["blocks"]),
        "angular_direction_count": context["mu"].size,
        "material_cell_count": parent_temperature.size,
        "radiation_depth_cell_count": context["beta"].size,
        "turning_direction_count": int(np.count_nonzero(turning)),
        "identified_live_array_gib": context["identified_live_bytes"] / 1024**3,
        "microphysics_runtime_s": microphysics_runtime,
        "radiation_field_runtime_s": field_runtime,
        "operator_runtime_s": operator_runtime,
        "total_runtime_s": time.perf_counter() - total_started,
        "baseline_highwater_rss_mib": baseline / MIB,
        "after_microphysics_highwater_rss_mib": after_microphysics / MIB,
        "after_radiation_fields_highwater_rss_mib": after_fields / MIB,
        "peak_process_rss_mib": peak / MIB,
        "operator_highwater_increase_mib": max(0, peak - after_fields) / MIB,
        "minimum_intensity": result.minimum_intensity,
        "one_iteration_fixed_point_change": result.final_fixed_point_change,
        "one_iteration_fixed_point_converged": result.fixed_point_converged,
        "one_iteration_global_coupled_residual": (
            result.global_scale_normalized_coupled_residual
        ),
        "one_iteration_energy_ledger_residual": (
            result.total_relative_energy_ledger_residual
        ),
        "all_reported_diagnostics_finite": bool(np.all(np.isfinite(diagnostics))),
        "final_intensity_sha256": _sha256_array(
            result.final_lab_intensity_density
        ),
        "input_array_bytes": int(
            initial.nbytes
            + outer.nbytes
            + true_absorption.nbytes
            + thermal_emissivity.nbytes
            + scattering.nbytes
        ),
    }
    _write_json_atomic(output_path, report)
    print(json.dumps(report, indent=2), flush=True)


def _plot(path: Path, report: dict[str, object], decision: dict[str, bool]) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(13, 8))
    axes[0, 0].bar(
        ["Identified\nlive arrays", "Measured\npeak RSS", "Process gate"],
        [report["identified_live_array_gib"], report["peak_process_rss_mib"] / 1024, 6.0],
        color=["#4c78a8", "#f58518", "#555555"],
    )
    axes[0, 0].set(ylabel="Memory (GiB)", title="(a) Worst full-depth block memory")
    axes[0, 1].bar(
        ["Microphysics", "Radiation fields", "One source map"],
        [
            report["microphysics_runtime_s"],
            report["radiation_field_runtime_s"],
            report["operator_runtime_s"],
        ],
        color=["#54a24b", "#eeca3b", "#b279a2"],
    )
    axes[0, 1].set(ylabel="Runtime (s)", title="(b) Measured cost by component")
    axes[1, 0].bar(
        ["Core", "Collision halo", "Outer halo"],
        [
            report["core_frequency_groups"],
            report["collision_group_count"],
            report["outer_group_count"],
        ],
        color=["#4c78a8", "#f58518", "#e45756"],
    )
    axes[1, 0].set(ylabel="Frequency groups", title="(c) Selected block geometry")
    axes[1, 1].bar(
        ["Memory", "Runtime", "Finite", "Non-negative"],
        [
            float(decision["resource_gate_passed"]),
            float(decision["runtime_gate_passed"]),
            float(decision["finite_diagnostics_passed"]),
            float(decision["nonnegative_intensity_passed"]),
        ],
        color=["#54a24b" if value else "#e45756" for value in (
            decision["resource_gate_passed"],
            decision["runtime_gate_passed"],
            decision["finite_diagnostics_passed"],
            decision["nonnegative_intensity_passed"],
        )],
    )
    axes[1, 1].set(ylim=(0, 1.15), ylabel="Pass flag", title="(d) Pre-registered gates")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b5x_preregistered_full_depth_block_probe.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument(
        "--worker-output",
        type=Path,
        default=OUTPUT / "phase7b5x_full_depth_block_worker.json",
    )
    args = parser.parse_args()
    if args.worker:
        run_worker(args.protocol, args.worker_output)
        return

    protocol = _load_protocol(args.protocol)
    context = _context(protocol)
    replication = _parent_replication_control(context)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--protocol",
        str(args.protocol),
        "--worker-output",
        str(args.worker_output),
    ]
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    wall = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(
            "Phase 7B5x isolated worker failed:\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    print(completed.stdout, end="")
    report = json.loads(args.worker_output.read_text(encoding="utf-8"))
    gates = protocol["gates"]
    selection = (
        report["phase_index"] == gates["selected_phase_exactly"]
        and report["core_group_start"] == gates["selected_core_start_exactly"]
        and report["core_group_stop"] == gates["selected_core_stop_exactly"]
        and report["collision_group_count"] == gates["collision_group_count_exactly"]
        and report["outer_group_count"] == gates["outer_group_count_exactly"]
        and report["radiation_depth_cell_count"]
        == gates["radiation_depth_cell_count_exactly"]
    )
    decision = {
        "frozen_protocol_hash_passed": True,
        "source_hashes_passed": True,
        "worst_phase_and_block_selection_passed": bool(selection),
        "parent_replication_passed": bool(
            replication["maximum_relative_error"]
            < gates["parent_replication_maximum_relative_error_strictly_below"]
        ),
        "nonnegative_intensity_passed": bool(
            report["minimum_intensity"] >= gates["minimum_intensity_at_least"]
        ),
        "finite_diagnostics_passed": bool(report["all_reported_diagnostics_finite"]),
        "resource_gate_passed": bool(
            report["peak_process_rss_mib"]
            < gates["worker_peak_rss_strictly_below_mib"]
        ),
        "runtime_gate_passed": bool(
            report["total_runtime_s"] < gates["worker_runtime_strictly_below_s"]
        ),
        "frequency_grid_unchanged": bool(
            report["physical_frequency_groups"]
            == protocol["configuration"]["physical_frequency_groups"]
        ),
        "full_column_fixed_point_authorized": False,
        "full_orbit_authorized": False,
        "matter_feedback_authorized": False,
        "phase4_replacement_authorized": False,
    }
    required = (
        "frozen_protocol_hash_passed",
        "source_hashes_passed",
        "worst_phase_and_block_selection_passed",
        "parent_replication_passed",
        "nonnegative_intensity_passed",
        "finite_diagnostics_passed",
        "resource_gate_passed",
        "runtime_gate_passed",
        "frequency_grid_unchanged",
    )
    decision["phase7b5x_gate_passed"] = all(decision[name] for name in required)
    decision["performance_architecture_decision_authorized"] = bool(
        decision["phase7b5x_gate_passed"]
    )
    summary = {
        "phase": "7B5x full-depth worst-block resource probe",
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_path": str(args.protocol),
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "parent_microphysics_replication_control": replication,
        "worker": report,
        "fresh_process_wall_s": wall,
        "record_only_extrapolation": {
            "worst_block_times_all_blocks_s": (
                report["total_runtime_s"] * report["block_count"]
            ),
            "operator_only_times_all_blocks_s": (
                report["operator_runtime_s"] * report["block_count"]
            ),
            "interpretation": (
                "upper-cost proxy from one worst block; not a measured full source iteration"
            ),
        },
        "decision": decision,
        "figures": ["phase7b5x_full_depth_block_probe.png"],
    }
    _write_json_atomic(
        OUTPUT / "phase7b5x_full_depth_block_probe_summary.json", summary
    )
    _plot(OUTPUT / "phase7b5x_full_depth_block_probe.png", report, decision)
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
