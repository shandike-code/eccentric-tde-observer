"""Phase 7B7e：阻尼物质态上的一次全频辐射方向映射。"""

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

from eccentric_tde_observer.multigroup_continuum import ground_state_milne_multigroup
from eccentric_tde_observer.mixed_frame_ale import solve_mixed_frame_ale_group_step
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S
from eccentric_tde_observer.radiation_matter_feedback import (
    ground_state_material_specific_energy_erg_g,
)

try:
    from scripts import phase7b5x_full_depth_block_probe as phase7b5x
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b5x_full_depth_block_probe as phase7b5x  # type: ignore[no-redef]
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
CHECKPOINT = OUTPUT / "checkpoints"
EXPECTED_PROTOCOL_SHA256 = (
    "b1878b60a10d939a903373c343985429da2cae2df8857068142c6bd5a461149b"
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
        raise RuntimeError(f"frozen Phase 7B7e protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B7e source changed: {source['path']}")
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


def _updated_full_material(protocol: dict[str, object]):
    with np.load(ROOT / protocol["sources"]["damped_material_state"]["path"]) as state:
        density_half = np.array(state["density_g_cm3"], copy=True)
        temperature_half = np.array(state["temperature_k"], copy=True)
        hydrogen_half = np.array(state["hydrogen_fraction"], copy=True)
        helium_half = np.array(state["helium_fraction"], copy=True)

    def mirror(value: np.ndarray) -> np.ndarray:
        return np.concatenate((value, value[::-1]), axis=0)

    return {
        "density_parent": mirror(density_half),
        "temperature_parent": mirror(temperature_half),
        "hydrogen_parent": mirror(hydrogen_half),
        "helium_parent": mirror(helium_half),
    }


def _local_fields(
    context: dict[str, object],
    block: object,
    updated: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    local = block.local_stencil
    full = context["full"]
    phase = int(context["phase"])
    following = int(context["following"])
    initial_temperature = full["temperature_k"][phase]
    parent_outer = phase7b5x._parent_boosted_planck_outer(
        local.outer_lab_edge_hz,
        context["mu"],
        context["weight"],
        context["parent_beta"],
        initial_temperature,
    )
    outer = np.repeat(parent_outer, 16, axis=2)
    active = slice(local.active_outer_group_start, local.active_outer_group_stop)
    parent_planck = phase7b5x._parent_group_planck(
        local.comoving_collision_edge_hz,
        updated["temperature_parent"],
    )
    continuum = ground_state_milne_multigroup(
        updated["density_parent"],
        updated["temperature_parent"],
        local.comoving_collision_edge_hz,
        parent_planck,
        updated["hydrogen_parent"][:, 0],
        updated["hydrogen_parent"][:, 1],
        updated["helium_parent"][:, 0],
        updated["helium_parent"][:, 1],
        updated["helium_parent"][:, 2],
        order_per_group=16,
    ).continuum
    return {
        "initial": np.array(outer[active], copy=True),
        "outer": outer,
        "true_absorption": np.repeat(
            continuum.true_absorption_total_per_cm, 16, axis=1
        ),
        "thermal_emissivity": np.repeat(
            continuum.thermal_emissivity_total_cgs, 16, axis=1
        ),
        "scattering": np.repeat(
            continuum.electron_scattering_per_cm, 16, axis=1
        ),
        "old_edge": phase7b5x._subdivide_column_edge(full["edge_cm"][phase], 16),
        "new_edge": phase7b5x._subdivide_column_edge(full["edge_cm"][following], 16),
    }


def run_worker(
    protocol_path: Path,
    block_index: int,
    output_state_path: Path,
    partial_path: Path,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    context = phase7b5x._context(protocol)
    if int(context["phase"]) != int(configuration["phase_index"]):
        raise RuntimeError("Phase 7B7e selected phase changed")
    if block_index < 0 or block_index >= len(context["blocks"]):
        raise ValueError("Phase 7B7e block index is invalid")
    shape = _shape(protocol)
    state_global = np.memmap(
        ROOT / protocol["retained_arrays"]["iteration30_state_path"],
        mode="r",
        dtype=np.float64,
        shape=shape,
    )
    output_global = np.memmap(
        output_state_path, mode="r+", dtype=np.float64, shape=shape
    )
    updated = _updated_full_material(protocol)
    density = np.repeat(updated["density_parent"], 16)
    temperature = np.repeat(updated["temperature_parent"], 16)
    hydrogen = np.repeat(updated["hydrogen_parent"], 16, axis=0)
    helium = np.repeat(updated["helium_parent"], 16, axis=0)
    block = context["blocks"][block_index]
    fields = _local_fields(context, block, updated)
    full_active_start = int(context["stencil"].active_outer_group_start)
    full_active_stop = int(context["stencil"].active_outer_group_stop)
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
    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
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
    mapped = np.asarray(result.final_lab_intensity_density)
    output_global[core] = mapped
    output_global.flush()
    difference = mapped - current_core
    scale = max(float(np.max(np.abs(mapped))), float(np.max(np.abs(current_core))))
    global_edge = np.asarray(context["stencil"].active_lab_edge_hz)
    local_edge = np.asarray(block.local_stencil.comoving_collision_edge_hz)
    left_match = np.flatnonzero(local_edge == global_edge[block.core_group_start])
    right_match = np.flatnonzero(local_edge == global_edge[block.core_group_stop])
    if left_match.size != 1 or right_match.size != 1:
        raise ArithmeticError("Phase 7B7e lost exact collision-edge ownership")
    collision_start = int(left_match[0])
    collision_stop = int(right_match[0])
    owned_mean = np.array(
        result.final_comoving_mean_intensity_density[
            collision_start:collision_stop
        ],
        copy=True,
    )
    if not np.all(np.isfinite(owned_mean)) or np.any(owned_mean < 0.0):
        raise ArithmeticError("Phase 7B7e comoving mean intensity is invalid")
    partials = _zero_partials(shape[2])
    partials["radiation_source_energy_lab_erg_s_cm3"] += (
        result.radiation_source_energy_lab_erg_s_cm3
    )
    partials["radiation_source_momentum_lab_dyn_cm3"] += (
        result.radiation_source_momentum_lab_dyn_cm3
    )
    mapped_minimum = float(result.minimum_intensity)
    coupled_residual = float(result.global_scale_normalized_coupled_residual)
    energy_residual = float(result.total_relative_energy_ledger_residual)
    del result, fields, current_core, mapped, difference
    gc.collect()
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
    partials["total_recombination_cm3_s"] += rates.total_recombination_cm3_s
    partials["absorbed_power_erg_s_cm3"] += microphysics.absorbed_power_erg_s_cm3
    partials["emitted_power_erg_s_cm3"] += microphysics.emitted_power_erg_s_cm3
    partials["rate_material_heating_erg_s_cm3"] += (
        microphysics.radiative_heating_erg_s_cm3
    )
    _write_npz_atomic(partial_path, **partials)
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    _write_json_atomic(
        report_path,
        {
            "block_index": block_index,
            "core_group_start": block.core_group_start,
            "core_group_stop": block.core_group_stop,
            "collision_group_start": collision_start,
            "collision_group_stop": collision_stop,
            "minimum_owned_comoving_mean_intensity": float(np.min(owned_mean)),
            "maximum_owned_comoving_mean_intensity": float(np.max(owned_mean)),
            "mapped_minimum_intensity": mapped_minimum,
            "maximum_absolute_radiation_change": float(np.max(np.abs(output_global[core] - state_global[core]))),
            "maximum_radiation_scale": scale,
            "global_coupled_residual": coupled_residual,
            "total_energy_ledger_residual": energy_residual,
            "runtime_s": time.perf_counter() - started,
            "baseline_highwater_rss_mib": baseline_rss / MIB,
            "peak_process_rss_mib": peak_rss / MIB,
            "partial_path": str(partial_path.relative_to(ROOT)),
            "partial_sha256": _sha256(partial_path),
        },
    )


def _plot(
    path: Path,
    mass_centre: np.ndarray,
    old_residual: np.ndarray,
    new_residual: np.ndarray,
    old_heating: np.ndarray,
    new_heating: np.ndarray,
    reports: list[dict[str, object]],
    volume_contraction: float,
    limiting_contraction: float,
) -> None:
    block = [int(report["block_index"]) for report in reports]
    rss = [float(report["peak_process_rss_mib"]) for report in reports]
    global_radiation_scale = max(
        float(report["maximum_radiation_scale"]) for report in reports
    )
    raw = [
        (
            float(report["maximum_absolute_radiation_change"])
            / global_radiation_scale
            if global_radiation_scale > 0.0
            else float(report["maximum_absolute_radiation_change"])
        )
        for report in reports
    ]
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].semilogy(
        mass_centre, np.abs(old_residual), label="Before matter damping"
    )
    axes[0, 0].semilogy(
        mass_centre,
        np.abs(new_residual),
        ls="--",
        label="After one radiation map",
    )
    axes[0, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="|Full-step material-energy residual|",
        title="(a) Coupled residual direction",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].plot(mass_centre, old_heating, label="Original matter")
    axes[0, 1].plot(mass_centre, new_heating, ls="--", label="Damped matter, one map")
    axes[0, 1].set(
        xlabel="Mass fraction from surface",
        ylabel="Material heating (erg s$^{-1}$ cm$^{-3}$)",
        title="(b) Heating feedback",
    )
    axes[0, 1].legend(frameon=False)
    axes[1, 0].bar(
        ["Volume L1", "Limiting cell"],
        [volume_contraction, limiting_contraction],
        color=["#4c78a8", "#f58518"],
    )
    axes[1, 0].axhline(1.0, color="0.25", ls="--", label="Contraction gate")
    axes[1, 0].set(ylabel="New / old residual", title="(c) Matter-direction contraction")
    axes[1, 0].legend(frameon=False)
    scatter = axes[1, 1].scatter(block, raw, c=rss, cmap="viridis", s=34)
    axes[1, 1].axhline(0.1, color="0.25", ls="--", label="Radiation trust gate")
    axes[1, 1].set_yscale("log")
    axes[1, 1].set(
        xlabel="Frequency block index",
        ylabel="One-map raw radiation residual",
        title="(d) Radiation direction and process RSS",
    )
    axes[1, 1].legend(frameon=False)
    figure.colorbar(scatter, ax=axes[1, 1], label="Peak RSS (MiB)")
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path, *, assemble_only: bool = False) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    shape = _shape(protocol)
    retained_state_path = ROOT / protocol["retained_arrays"]["iteration30_state_path"]
    if _sha256(retained_state_path) != protocol["retained_arrays"]["iteration30_state_sha256"]:
        raise RuntimeError("Phase 7B7e retained I30 hash changed")
    block_count = int(configuration["block_count"])
    CHECKPOINT.mkdir(parents=True, exist_ok=True)
    output_state_path = CHECKPOINT / "phase7b7e_damped_matter_radiation_map.dat"
    partial_paths = [OUTPUT / f"phase7b7e_block{index:02d}_partial.npz" for index in range(block_count)]
    report_paths = [OUTPUT / f"phase7b7e_block{index:02d}.json" for index in range(block_count)]
    expected_state_size = int(np.prod(shape, dtype=np.int64) * 8)
    if assemble_only:
        if (
            not all(path.exists() for path in (*partial_paths, *report_paths))
            or not output_state_path.exists()
            or output_state_path.stat().st_size != expected_state_size
        ):
            raise RuntimeError("Phase 7B7e assemble-only artifacts are incomplete")
    else:
        output_state = np.memmap(
            output_state_path, mode="w+", dtype=np.float64, shape=shape
        )
        output_state[:] = 0.0
        output_state.flush()
        del output_state
        started = time.perf_counter()
        concurrency = int(configuration["maximum_concurrent_processes"])
        for offset in range(0, block_count, concurrency):
            batch = range(offset, min(offset + concurrency, block_count))
            processes = []
            for block_index in batch:
                processes.append(
                    subprocess.Popen(
                        [
                            sys.executable,
                            str(Path(__file__).resolve()),
                            "--worker",
                            "--protocol",
                            str(protocol_path),
                            "--block-index",
                            str(block_index),
                            "--output-state",
                            str(output_state_path),
                            "--partial",
                            str(partial_paths[block_index]),
                            "--worker-report",
                            str(report_paths[block_index]),
                        ],
                        cwd=ROOT,
                    )
                )
            return_codes = [process.wait() for process in processes]
            if any(code != 0 for code in return_codes):
                raise RuntimeError(
                    f"Phase 7B7e worker batch failed: {return_codes}"
                )
        wall_runtime = time.perf_counter() - started
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    if assemble_only:
        earliest_start = min(
            path.stat().st_mtime - float(report["runtime_s"])
            for path, report in zip(report_paths, reports, strict=True)
        )
        latest_finish = max(path.stat().st_mtime for path in report_paths)
        wall_runtime = latest_finish - earliest_start
    rows = sorted(reports, key=lambda row: row["core_group_start"])
    ownership = np.zeros(shape[0], dtype=np.int64)
    combined = _zero_partials(shape[2])
    for report, partial_path in zip(reports, partial_paths, strict=True):
        ownership[report["core_group_start"] : report["core_group_stop"]] += 1
        if _sha256(partial_path) != report["partial_sha256"]:
            raise RuntimeError("Phase 7B7e partial hash changed")
        with np.load(partial_path) as archive:
            for name in combined:
                combined[name] += np.asarray(archive[name])
    context = phase7b5x._context(protocol)
    beta = np.asarray(context["beta"])
    gamma = 1.0 / np.sqrt(1.0 - beta**2)
    formal_heating = -gamma * (
        combined["radiation_source_energy_lab_erg_s_cm3"]
        - beta
        * LIGHT_SPEED_CM_S
        * combined["radiation_source_momentum_lab_dyn_cm3"]
    )
    following = int(context["following"])
    subedge = phase7b5x._subdivide_column_edge(context["full"]["edge_cm"][following], 16)
    subwidth = np.diff(subedge)
    rate_heating = combined["rate_material_heating_erg_s_cm3"]
    source_difference = rate_heating - formal_heating
    source_l1 = float(np.sum(subwidth * np.abs(source_difference))) / max(
        float(np.sum(subwidth * np.abs(rate_heating))),
        float(np.sum(subwidth * np.abs(formal_heating))),
    )
    integrated_rate = float(np.sum(subwidth * rate_heating))
    integrated_formal = float(np.sum(subwidth * formal_heating))
    source_global = abs(integrated_rate - integrated_formal) / max(
        abs(integrated_rate), abs(integrated_formal)
    )
    parent = {
        name: np.mean(array.reshape(256, 16, *array.shape[1:]), axis=1)
        for name, array in combined.items()
    }
    parent["formal_material_heating_erg_s_cm3"] = np.mean(
        formal_heating.reshape(256, 16), axis=1
    )
    with np.load(ROOT / protocol["sources"]["old_feedback_coefficients"]["path"]) as old_coefficient:
        old_heating = np.array(
            old_coefficient["half_rate_material_heating_erg_s_cm3"], copy=True
        )
    with np.load(ROOT / protocol["sources"]["damped_material_state"]["path"]) as damped:
        density = np.array(damped["density_g_cm3"], copy=True)
        new_temperature = np.array(damped["temperature_k"], copy=True)
        new_hydrogen = np.array(damped["hydrogen_fraction"], copy=True)
        new_helium = np.array(damped["helium_fraction"], copy=True)
    with np.load(ROOT / protocol["sources"]["phase7b4r_material"]["path"]) as material:
        phase = int(context["phase"])
        old_temperature = np.array(material["temperature_k"][phase], copy=True)
        old_hydrogen = np.array(material["hydrogen_fraction"][phase], copy=True)
        old_helium = np.array(material["helium_fraction"][phase], copy=True)
        cell_mass = np.array(material["cell_mass_g_cm2"], copy=True)
        mass_edge = np.array(material["mass_fraction_edges"], copy=True)
    old_energy = ground_state_material_specific_energy_erg_g(
        old_temperature, old_hydrogen, old_helium
    )
    new_energy = ground_state_material_specific_energy_erg_g(
        new_temperature, new_hydrogen, new_helium
    )
    duration = float(context["duration_s"])
    old_residual = duration * old_heating / (density * old_energy)
    new_heating = parent["rate_material_heating_erg_s_cm3"][:128]
    new_residual = duration * new_heating / (density * new_energy)
    volume_contraction = float(np.sum(cell_mass * np.abs(new_residual))) / float(
        np.sum(cell_mass * np.abs(old_residual))
    )
    diagnosis = json.loads(
        (OUTPUT / "phase7b7c_timescale_diagnosis_summary.json").read_text(
            encoding="utf-8"
        )
    )
    limiting_cell = int(diagnosis["limiting_half_column_cell"])
    limiting_contraction = abs(float(new_residual[limiting_cell])) / abs(
        float(old_residual[limiting_cell])
    )
    maximum_absolute = max(float(report["maximum_absolute_radiation_change"]) for report in reports)
    maximum_scale = max(float(report["maximum_radiation_scale"]) for report in reports)
    raw_radiation_residual = maximum_absolute / maximum_scale
    rss = [float(report["peak_process_rss_mib"]) for report in reports]
    gates = protocol["gates"]
    arrays_finite = all(np.all(np.isfinite(array)) for array in combined.values())
    decision = {
        "frozen_protocol_source_and_state_hashes_passed": True,
        "block_and_frequency_ownership_passed": bool(
            len(rows) == gates["block_count_exactly"]
            and int(np.sum(ownership)) == gates["owned_frequency_group_count_exactly"]
            and np.all(ownership == 1)
        ),
        "mapped_comoving_rates_and_arrays_valid": bool(
            min(report["mapped_minimum_intensity"] for report in reports)
            >= gates["minimum_mapped_and_comoving_intensity_at_least"]
            and min(report["minimum_owned_comoving_mean_intensity"] for report in reports)
            >= gates["minimum_mapped_and_comoving_intensity_at_least"]
            and arrays_finite
        ),
        "frame_source_consistency_passed": bool(
            source_l1 < gates["rate_heating_vs_inverse_four_force_volume_l1_below"]
            and source_global
            < gates["rate_heating_vs_inverse_four_force_global_fraction_below"]
        ),
        "radiation_direction_trust_passed": raw_radiation_residual
        < gates["one_map_raw_radiation_residual_below"],
        "matter_residual_direction_contracted": bool(
            volume_contraction
            < gates["matter_residual_volume_l1_contraction_fraction_below"]
            and limiting_contraction
            < gates["limiting_cell_matter_residual_contraction_fraction_below"]
        ),
        "resource_and_runtime_gates_passed": bool(
            all(value < gates["each_process_peak_rss_strictly_below_mib"] for value in rss)
            and wall_runtime < gates["total_wall_time_strictly_below_s"]
        ),
        "accepted_as_radiation_or_coupled_fixed_point": False,
        "second_material_update_authorized": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b7e_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_source_and_state_hashes_passed",
            "block_and_frequency_ownership_passed",
            "mapped_comoving_rates_and_arrays_valid",
            "frame_source_consistency_passed",
            "radiation_direction_trust_passed",
            "matter_residual_direction_contracted",
            "resource_and_runtime_gates_passed",
        )
    )
    decision["bounded_radiation_continuation_design_authorized"] = bool(
        decision["phase7b7e_gate_passed"]
    )
    coefficient_path = OUTPUT / "phase7b7e_directional_feedback_coefficients.npz"
    _write_npz_atomic(
        coefficient_path,
        **{name: np.asarray(value) for name, value in parent.items()},
        **{f"half_{name}": np.asarray(value[:128]) for name, value in parent.items()},
        old_material_residual=old_residual,
        new_directional_material_residual=new_residual,
    )
    figure_path = OUTPUT / "phase7b7e_radiation_direction.png"
    _plot(
        figure_path,
        0.5 * (mass_edge[:-1] + mass_edge[1:]),
        old_residual,
        new_residual,
        old_heating,
        new_heating,
        reports,
        volume_contraction,
        limiting_contraction,
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "block_count": len(rows),
        "owned_frequency_group_count": int(np.sum(ownership)),
        "minimum_mapped_intensity": min(report["mapped_minimum_intensity"] for report in reports),
        "one_map_raw_radiation_residual": raw_radiation_residual,
        "rate_heating_vs_inverse_four_force_volume_l1": source_l1,
        "rate_heating_vs_inverse_four_force_global_fraction": source_global,
        "matter_residual_volume_l1_contraction_fraction": volume_contraction,
        "limiting_cell_matter_residual_contraction_fraction": limiting_contraction,
        "limiting_half_column_cell": limiting_cell,
        "old_limiting_cell_heating_erg_s_cm3": float(old_heating[limiting_cell]),
        "new_limiting_cell_heating_erg_s_cm3": float(new_heating[limiting_cell]),
        "maximum_process_peak_rss_mib": max(rss),
        "total_wall_runtime_s": wall_runtime,
        "mapped_state_path": str(output_state_path.relative_to(ROOT)),
        "mapped_state_sha256": _sha256(output_state_path),
        "coefficient_path": str(coefficient_path.relative_to(ROOT)),
        "coefficient_sha256": _sha256(coefficient_path),
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(OUTPUT / "phase7b7e_radiation_direction_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b7e_preregistered_radiation_direction.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--partial", type=Path)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--assemble-only", action="store_true")
    args = parser.parse_args()
    if args.worker:
        if (
            args.block_index is None
            or args.output_state is None
            or args.partial is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires block, state, partial and report")
        run_worker(
            args.protocol,
            args.block_index,
            args.output_state,
            args.partial,
            args.worker_report,
        )
        return
    summary = run(args.protocol, assemble_only=args.assemble_only)
    print(json.dumps(summary["decision"], indent=2))


if __name__ == "__main__":
    main()
