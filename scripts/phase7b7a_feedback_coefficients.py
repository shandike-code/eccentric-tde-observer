"""Phase 7B7a：从收敛 I30 正式映射提取共动系物质反馈系数。"""

from __future__ import annotations

import argparse
import gc
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

from eccentric_tde_observer.multigroup_continuum import (
    ground_state_milne_multigroup,
)
from eccentric_tde_observer.mixed_frame_ale import solve_mixed_frame_ale_group_step
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S

try:
    from scripts import phase7b5x_full_depth_block_probe as phase7b5x
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
    from scripts.phase7b6f_full_frequency_contraction import _local_fields
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b5x_full_depth_block_probe as phase7b5x  # type: ignore[no-redef]
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )
    from phase7b6f_full_frequency_contraction import (  # type: ignore[no-redef]
        _local_fields,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "27b358cd763cab3f41db50f204fc3d39330fb58903393c99daecd4b753d6b90c"
)
MIB = 1024**2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_npz_atomic(path: Path, **arrays: np.ndarray) -> None:
    temporary = path.with_name(f"{path.stem}.tmp.npz")
    np.savez(temporary, **arrays)
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B7a protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B7a source changed: {source['path']}")
    return protocol


def _shape(protocol: dict[str, object]) -> tuple[int, int, int]:
    configuration = protocol["configuration"]
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _zero_partials(depth: int) -> dict[str, np.ndarray]:
    return {
        "photoionization_s1": np.zeros((depth, 3)),
        "spontaneous_recombination_cm3_s": np.zeros((depth, 3)),
        "stimulated_recombination_cm3_s": np.zeros((depth, 3)),
        "total_recombination_cm3_s": np.zeros((depth, 3)),
        "absorbed_power_erg_s_cm3": np.zeros(depth),
        "emitted_power_erg_s_cm3": np.zeros(depth),
        "rate_material_heating_erg_s_cm3": np.zeros(depth),
        "radiation_source_energy_lab_erg_s_cm3": np.zeros(depth),
        "radiation_source_momentum_lab_dyn_cm3": np.zeros(depth),
    }


def run_worker(
    protocol_path: Path,
    worker_index: int,
    partial_path: Path,
    report_path: Path,
    block_indices: tuple[int, ...] | None = None,
) -> None:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    worker_count = int(configuration["logical_worker_count"])
    if worker_index < 0 or worker_index >= worker_count:
        raise ValueError("worker index left the frozen Phase 7B7a assignment")
    context = phase7b5x._context(protocol)
    if int(context["phase"]) != int(configuration["phase_index"]):
        raise RuntimeError("Phase 7B7a selected phase changed")
    shape = _shape(protocol)
    state_global = np.memmap(
        ROOT / protocol["retained_arrays"]["iteration30_state_path"],
        mode="r",
        dtype=np.float64,
        shape=shape,
    )
    full_active_start = int(context["stencil"].active_outer_group_start)
    full_active_stop = int(context["stencil"].active_outer_group_stop)
    global_edge = np.asarray(context["stencil"].active_lab_edge_hz)
    full = context["full"]
    phase = int(context["phase"])
    density = np.repeat(full["density_g_cm3"][phase], 16)
    temperature = np.repeat(full["temperature_k"][phase], 16)
    hydrogen = np.repeat(full["hydrogen_fraction"][phase], 16, axis=0)
    helium = np.repeat(full["helium_fraction"][phase], 16, axis=0)
    partials = _zero_partials(shape[2])
    if block_indices is None:
        assigned = [
            (index, block)
            for index, block in enumerate(context["blocks"])
            if index % worker_count == worker_index
        ]
    else:
        if (
            len(block_indices) == 0
            or len(set(block_indices)) != len(block_indices)
            or any(
                index < 0
                or index >= len(context["blocks"])
                or index % worker_count != worker_index
                for index in block_indices
            )
        ):
            raise ValueError("isolated block assignment left its frozen owner")
        assigned = [(index, context["blocks"][index]) for index in block_indices]
    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    minimum_mean = float("inf")
    rows: list[dict[str, object]] = []
    started = time.perf_counter()
    for local_index, (block_index, block) in enumerate(assigned, start=1):
        block_started = time.perf_counter()
        fields = _local_fields(context, block)
        physical_start = max(block.outer_group_start, full_active_start)
        physical_stop = min(block.outer_group_stop, full_active_stop)
        if physical_stop > physical_start:
            source_slice = slice(
                physical_start - full_active_start,
                physical_stop - full_active_start,
            )
            fields["outer"][
                physical_start - block.outer_group_start : physical_stop
                - block.outer_group_start
            ] = state_global[source_slice]
        core = slice(block.core_group_start, block.core_group_stop)
        current_core = np.array(state_global[core], copy=True)
        result = solve_mixed_frame_ale_group_step(
            block.local_stencil,
            fields["old_edge"],
            fields["new_edge"],
            context["mu"],
            context["weight"],
            fields["initial"],
            fields["outer"],
            fields["true_absorption"],
            fields["thermal_emissivity"],
            fields["scattering"],
            context["beta"],
            context["duration_s"],
            propagation_speed_cm_s=LIGHT_SPEED_CM_S,
            source_iteration_initial_guess=current_core,
            diagnostic_fixed_iteration_count=1,
            spatial_scheme="hybrid_step_turning_upwind",
            source_map_only=False,
        )
        local_edge = np.asarray(block.local_stencil.comoving_collision_edge_hz)
        left_match = np.flatnonzero(
            local_edge == global_edge[block.core_group_start]
        )
        right_match = np.flatnonzero(
            local_edge == global_edge[block.core_group_stop]
        )
        if left_match.size != 1 or right_match.size != 1:
            raise ArithmeticError("Phase 7B7a lost exact collision-edge ownership")
        collision_start = int(left_match[0])
        collision_stop = int(right_match[0])
        if collision_stop - collision_start != block.core_group_stop - block.core_group_start:
            raise ArithmeticError("Phase 7B7a collision ownership size changed")
        owned_mean = np.array(
            result.final_comoving_mean_intensity_density[
                collision_start:collision_stop
            ],
            copy=True,
        )
        if not np.all(np.isfinite(owned_mean)) or np.any(owned_mean < 0.0):
            raise ArithmeticError("Phase 7B7a comoving mean intensity is invalid")
        minimum_mean = min(minimum_mean, float(np.min(owned_mean)))
        partials["radiation_source_energy_lab_erg_s_cm3"] += (
            result.radiation_source_energy_lab_erg_s_cm3
        )
        partials["radiation_source_momentum_lab_dyn_cm3"] += (
            result.radiation_source_momentum_lab_dyn_cm3
        )
        coupled_residual = float(result.global_scale_normalized_coupled_residual)
        energy_residual = float(result.total_relative_energy_ledger_residual)
        mapped_minimum = float(result.minimum_intensity)
        del result, fields, current_core
        gc.collect()
        # 中文：只在本块唯一拥有的共动频带上积分原子率，避免守护组重计数。
        microphysics = ground_state_milne_multigroup(
            density,
            temperature,
            global_edge[block.core_group_start : block.core_group_stop + 1],
            owned_mean,
            hydrogen[:, 0],
            hydrogen[:, 1],
            helium[:, 0],
            helium[:, 1],
            helium[:, 2],
            order_per_group=int(configuration["rate_quadrature_order_per_group"]),
        )
        rates = microphysics.radiative_rates
        partials["photoionization_s1"] += rates.photoionization_s1
        partials["spontaneous_recombination_cm3_s"] += (
            rates.spontaneous_recombination_cm3_s
        )
        partials["stimulated_recombination_cm3_s"] += (
            rates.stimulated_recombination_cm3_s
        )
        partials["total_recombination_cm3_s"] += (
            rates.total_recombination_cm3_s
        )
        partials["absorbed_power_erg_s_cm3"] += (
            microphysics.absorbed_power_erg_s_cm3
        )
        partials["emitted_power_erg_s_cm3"] += (
            microphysics.emitted_power_erg_s_cm3
        )
        partials["rate_material_heating_erg_s_cm3"] += (
            microphysics.radiative_heating_erg_s_cm3
        )
        rows.append(
            {
                "worker_index": worker_index,
                "block_index": block_index,
                "core_group_start": block.core_group_start,
                "core_group_stop": block.core_group_stop,
                "collision_group_start": collision_start,
                "collision_group_stop": collision_stop,
                "minimum_owned_comoving_mean_intensity": float(np.min(owned_mean)),
                "maximum_owned_comoving_mean_intensity": float(np.max(owned_mean)),
                "mapped_minimum_intensity": mapped_minimum,
                "global_coupled_residual": coupled_residual,
                "total_energy_ledger_residual": energy_residual,
                "block_runtime_s": time.perf_counter() - block_started,
            }
        )
        del microphysics, rates, owned_mean
        gc.collect()
        if local_index == 1 or local_index % 10 == 0 or local_index == len(assigned):
            print(
                json.dumps(
                    {
                        "worker": worker_index + 1,
                        "completed": local_index,
                        "assigned": len(assigned),
                    }
                ),
                flush=True,
            )
    _write_npz_atomic(partial_path, **partials)
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    _write_json_atomic(
        report_path,
        {
            "worker_index": worker_index,
            "assigned_block_count": len(assigned),
            "runtime_s": time.perf_counter() - started,
            "baseline_highwater_rss_mib": baseline_rss / MIB,
            "peak_process_rss_mib": peak_rss / MIB,
            "minimum_owned_comoving_mean_intensity": minimum_mean,
            "partial_path": str(partial_path.relative_to(ROOT)),
            "partial_sha256": _sha256(partial_path),
            "rows": rows,
        },
    )


def _fraction(numerator: float, first: float, second: float) -> float:
    scale = max(abs(first), abs(second))
    return abs(numerator) / scale if scale > 0.0 else abs(numerator)


def _mirror_residual(array: np.ndarray) -> float:
    if array.shape[0] != 256:
        raise ValueError("mirror diagnostic requires 256 parent cells")
    difference = array[:128] - array[128:][::-1]
    scale = float(np.max(np.abs(array)))
    maximum = float(np.max(np.abs(difference)))
    return maximum / scale if scale > 0.0 else maximum


def _plot(
    path: Path,
    coefficient: dict[str, np.ndarray],
    mirror: dict[str, float],
    rss: list[float],
    source_l1: float,
    source_global: float,
) -> None:
    cell = np.arange(256)
    rate_heating = coefficient["rate_material_heating_erg_s_cm3"]
    four_heating = coefficient["formal_material_heating_erg_s_cm3"]
    heating_scale = max(
        float(np.max(np.abs(rate_heating))), float(np.max(np.abs(four_heating)))
    )
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].plot(cell, rate_heating, label="Milne rate integral")
    axes[0, 0].plot(cell, four_heating, ls="--", label="Inverse four-force")
    axes[0, 0].set_yscale(
        "symlog", linthresh=max(heating_scale * 1.0e-12, np.finfo(float).tiny)
    )
    axes[0, 0].set(
        xlabel="Full-column parent cell",
        ylabel="Material heating (erg s$^{-1}$ cm$^{-3}$)",
        title="(a) Independent comoving heating measures",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].plot(
        cell,
        np.abs(rate_heating - four_heating) / heating_scale,
        color="#e45756",
    )
    axes[0, 1].set_yscale("log")
    axes[0, 1].set(
        xlabel="Full-column parent cell",
        ylabel="Absolute difference / global scale",
        title="(b) Frame/source consistency",
    )
    photo = coefficient["photoionization_s1"]
    for species, label in enumerate(("H I", "He I", "He II")):
        axes[1, 0].semilogy(cell, photo[:, species], label=label)
    axes[1, 0].set(
        xlabel="Full-column parent cell",
        ylabel="Photoionization rate (s$^{-1}$)",
        title="(c) Extracted comoving rates",
    )
    axes[1, 0].legend(frameon=False)
    labels = ["Heating", "Photo", "Recomb.", "Absorbed", "Emitted"]
    values = [
        mirror["rate_material_heating_erg_s_cm3"],
        mirror["photoionization_s1"],
        mirror["total_recombination_cm3_s"],
        mirror["absorbed_power_erg_s_cm3"],
        mirror["emitted_power_erg_s_cm3"],
    ]
    axes[1, 1].bar(labels, values, color="#72b7b2", label="Mirror residual")
    axes[1, 1].axhline(1.0e-3, color="0.25", ls="--", label="Frozen gate")
    axes[1, 1].set_yscale("log")
    axes[1, 1].tick_params(axis="x", rotation=18)
    axes[1, 1].set(
        ylabel="Relative residual",
        title=(
            f"(d) Symmetry; source L1={source_l1:.2e}, "
            f"global={source_global:.2e}; max RSS={max(rss):.0f} MiB"
        ),
    )
    axes[1, 1].legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    retained = protocol["retained_arrays"]
    state_path = ROOT / retained["iteration30_state_path"]
    expected_size = int(np.prod(_shape(protocol), dtype=np.int64) * 8)
    if state_path.stat().st_size != expected_size:
        raise RuntimeError("Phase 7B7a retained I30 size changed")
    if _sha256(state_path) != retained["iteration30_state_sha256"]:
        raise RuntimeError("Phase 7B7a retained I30 hash changed")
    worker_count = int(configuration["logical_worker_count"])
    partial_paths = [OUTPUT / f"phase7b7a_worker{index + 1}_partial.npz" for index in range(worker_count)]
    report_paths = [OUTPUT / f"phase7b7a_worker{index + 1}.json" for index in range(worker_count)]
    started = time.perf_counter()
    for batch in configuration["worker_batches"]:
        if len(batch) > int(configuration["maximum_concurrent_processes"]):
            raise RuntimeError("Phase 7B7a batch exceeds frozen concurrency")
        processes = []
        for worker_index in batch:
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--worker",
                        "--protocol",
                        str(protocol_path),
                        "--worker-index",
                        str(worker_index),
                        "--partial",
                        str(partial_paths[worker_index]),
                        "--worker-report",
                        str(report_paths[worker_index]),
                    ],
                    cwd=ROOT,
                )
            )
        return_codes = [process.wait() for process in processes]
        if any(code != 0 for code in return_codes):
            raise RuntimeError(f"Phase 7B7a worker batch failed: {return_codes}")
    wall_runtime = time.perf_counter() - started
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    rows = sorted(
        [row for report in reports for row in report["rows"]],
        key=lambda row: row["core_group_start"],
    )
    combined = _zero_partials(int(configuration["radiation_depth_cell_count"]))
    for path, report in zip(partial_paths, reports, strict=True):
        if _sha256(path) != report["partial_sha256"]:
            raise RuntimeError("Phase 7B7a worker partial hash changed")
        with np.load(path) as archive:
            for name in combined:
                combined[name] += np.asarray(archive[name])
    ownership = np.zeros(int(configuration["physical_frequency_groups"]), dtype=np.int64)
    for row in rows:
        ownership[row["core_group_start"] : row["core_group_stop"]] += 1
    context = phase7b5x._context(protocol)
    beta = np.asarray(context["beta"])
    gamma = 1.0 / np.sqrt(1.0 - beta**2)
    # 中文：先合并唯一实验室频带，再用四矢量逆变换得到独立共动系净加热。
    formal_material_heating = -gamma * (
        combined["radiation_source_energy_lab_erg_s_cm3"]
        - beta
        * LIGHT_SPEED_CM_S
        * combined["radiation_source_momentum_lab_dyn_cm3"]
    )
    following = int(context["following"])
    subedge = phase7b5x._subdivide_column_edge(
        context["full"]["edge_cm"][following], 16
    )
    subwidth = np.diff(subedge)
    rate_heating = combined["rate_material_heating_erg_s_cm3"]
    difference = rate_heating - formal_material_heating
    source_l1_denominator = max(
        float(np.sum(subwidth * np.abs(rate_heating))),
        float(np.sum(subwidth * np.abs(formal_material_heating))),
    )
    source_l1 = (
        float(np.sum(subwidth * np.abs(difference))) / source_l1_denominator
        if source_l1_denominator > 0.0
        else float(np.sum(subwidth * np.abs(difference)))
    )
    integrated_rate = float(np.sum(subwidth * rate_heating))
    integrated_formal = float(np.sum(subwidth * formal_material_heating))
    source_global = _fraction(
        integrated_rate - integrated_formal, integrated_rate, integrated_formal
    )
    parent: dict[str, np.ndarray] = {}
    for name, array in combined.items():
        parent[name] = np.mean(array.reshape(256, 16, *array.shape[1:]), axis=1)
    parent["formal_material_heating_erg_s_cm3"] = np.mean(
        formal_material_heating.reshape(256, 16), axis=1
    )
    mirror_names = (
        "photoionization_s1",
        "spontaneous_recombination_cm3_s",
        "stimulated_recombination_cm3_s",
        "total_recombination_cm3_s",
        "absorbed_power_erg_s_cm3",
        "emitted_power_erg_s_cm3",
        "rate_material_heating_erg_s_cm3",
        "formal_material_heating_erg_s_cm3",
    )
    mirror = {name: _mirror_residual(parent[name]) for name in mirror_names}
    gates = protocol["gates"]
    arrays_finite = all(np.all(np.isfinite(value)) for value in combined.values()) and all(
        np.all(np.isfinite(value)) for value in parent.values()
    )
    nonnegative_names = (
        "photoionization_s1",
        "spontaneous_recombination_cm3_s",
        "stimulated_recombination_cm3_s",
        "total_recombination_cm3_s",
        "absorbed_power_erg_s_cm3",
        "emitted_power_erg_s_cm3",
    )
    nonnegative = all(np.all(combined[name] >= 0.0) for name in nonnegative_names)
    rss = [float(report["peak_process_rss_mib"]) for report in reports]
    decision = {
        "frozen_protocol_source_and_state_hashes_passed": True,
        "worker_block_and_frequency_ownership_passed": bool(
            len(rows) == gates["block_count_exactly"]
            and int(np.sum(ownership)) == gates["owned_frequency_group_count_exactly"]
            and np.all(ownership == 1)
            and worker_count == gates["logical_worker_count_exactly"]
            and int(configuration["maximum_concurrent_processes"])
            == gates["maximum_concurrent_processes_exactly"]
        ),
        "comoving_intensity_rates_and_arrays_valid": bool(
            min(report["minimum_owned_comoving_mean_intensity"] for report in reports)
            >= gates["minimum_comoving_mean_intensity_at_least"]
            and arrays_finite
            and nonnegative
        ),
        "rate_heating_vs_inverse_four_force_passed": bool(
            source_l1
            < gates["rate_heating_vs_inverse_four_force_volume_l1_below"]
            and source_global
            < gates["rate_heating_vs_inverse_four_force_global_fraction_below"]
        ),
        "parent_mirror_symmetry_passed": bool(
            max(mirror.values()) < gates["maximum_parent_mirror_residual_below"]
        ),
        "resource_and_runtime_gates_passed": bool(
            all(value < gates["each_process_peak_rss_strictly_below_mib"] for value in rss)
            and wall_runtime < gates["total_wall_time_strictly_below_s"]
        ),
        "fully_coupled_iteration_authorized": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b7a_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_source_and_state_hashes_passed",
            "worker_block_and_frequency_ownership_passed",
            "comoving_intensity_rates_and_arrays_valid",
            "rate_heating_vs_inverse_four_force_passed",
            "parent_mirror_symmetry_passed",
            "resource_and_runtime_gates_passed",
        )
    )
    decision["one_frozen_radiation_matter_update_authorized"] = bool(
        decision["phase7b7a_gate_passed"]
    )
    coefficient_path = OUTPUT / "phase7b7a_feedback_coefficients.npz"
    coefficient_arrays = {
        "phase_index": np.array(int(context["phase"])),
        "following_phase_index": np.array(int(context["following"])),
        "step_duration_s": np.array(float(context["duration_s"])),
        "parent_edge_cm": np.asarray(context["full"]["edge_cm"][int(context["phase"])]),
        "following_parent_edge_cm": np.asarray(context["full"]["edge_cm"][following]),
        **{name: np.asarray(value) for name, value in parent.items()},
        **{f"half_{name}": np.asarray(value[:128]) for name, value in parent.items()},
    }
    _write_npz_atomic(coefficient_path, **coefficient_arrays)
    _plot(
        OUTPUT / "phase7b7a_feedback_coefficients.png",
        parent,
        mirror,
        rss,
        source_l1,
        source_global,
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "coefficient_path": str(coefficient_path.relative_to(ROOT)),
        "coefficient_sha256": _sha256(coefficient_path),
        "worker_reports": [str(path.relative_to(ROOT)) for path in report_paths],
        "worker_partials": [str(path.relative_to(ROOT)) for path in partial_paths],
        "block_count": len(rows),
        "owned_frequency_group_count": int(np.sum(ownership)),
        "ownership_minimum": int(np.min(ownership)),
        "ownership_maximum": int(np.max(ownership)),
        "minimum_comoving_mean_intensity": min(
            report["minimum_owned_comoving_mean_intensity"] for report in reports
        ),
        "rate_heating_vs_inverse_four_force_volume_l1": source_l1,
        "rate_heating_vs_inverse_four_force_global_fraction": source_global,
        "integrated_rate_material_heating_erg_s_cm2": integrated_rate,
        "integrated_formal_material_heating_erg_s_cm2": integrated_formal,
        "parent_mirror_residuals": mirror,
        "maximum_parent_mirror_residual": max(mirror.values()),
        "worker_peak_rss_mib": rss,
        "total_wall_runtime_s": wall_runtime,
        "decision": decision,
        "figures": ["phase7b7a_feedback_coefficients.png"],
    }
    _write_json_atomic(OUTPUT / "phase7b7a_feedback_coefficients_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b7a_preregistered_feedback_coefficients.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--worker-index", type=int)
    parser.add_argument("--partial", type=Path)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--block-index", type=int, action="append")
    args = parser.parse_args()
    if args.worker:
        if args.worker_index is None or args.partial is None or args.worker_report is None:
            raise ValueError("worker mode requires index, partial and report")
        block_indices = (
            tuple(args.block_index) if args.block_index is not None else None
        )
        run_worker(
            args.protocol,
            args.worker_index,
            args.partial,
            args.worker_report,
            block_indices,
        )
        return
    summary = run(args.protocol)
    print(json.dumps(summary["decision"], indent=2))


if __name__ == "__main__":
    main()
