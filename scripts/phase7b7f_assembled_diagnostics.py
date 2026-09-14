"""Phase 7B7f：在拼接后的同一个全局辐射态上重做正式源项诊断。"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.mixed_frame_frequency import (
    comoving_group_radiation,
    lorentz_ray_transform,
    lorentz_remap_comoving_group_emissivity_to_lab,
    lorentz_remap_comoving_group_extinction_to_lab,
)
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S, PLANCK_ERG_S

try:
    from scripts import phase7b7e_radiation_direction as phase7b7e
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b7e_radiation_direction as phase7b7e  # type: ignore[no-redef]
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "40b4dc0440e8db39fd7d8e09b5d33ad120336ea8360b1001f2d2fb4fefbadeba"
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
        raise RuntimeError(f"frozen Phase 7B7f protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B7f source changed: {source['path']}")
    for source in protocol["block_partials"]:
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B7f partial changed: {source['path']}")
    return protocol


def _relative_error(value: float, reference: float) -> float:
    scale = abs(reference)
    return abs(value - reference) / scale if scale > 0.0 else abs(value - reference)


def _source_metrics(
    rate: np.ndarray,
    formal: np.ndarray,
    width: np.ndarray,
) -> tuple[float, float, float, float]:
    rate_l1 = float(np.sum(width * np.abs(rate)))
    formal_l1 = float(np.sum(width * np.abs(formal)))
    volume_l1 = float(np.sum(width * np.abs(rate - formal))) / max(
        rate_l1, formal_l1
    )
    integrated_rate = float(np.sum(width * rate))
    integrated_formal = float(np.sum(width * formal))
    global_fraction = abs(integrated_rate - integrated_formal) / max(
        abs(integrated_rate), abs(integrated_formal)
    )
    return volume_l1, global_fraction, integrated_rate, integrated_formal


def _plot(
    path: Path,
    energy_centre_ev: np.ndarray,
    lagged_block_difference: np.ndarray,
    assembled_block_difference: np.ndarray,
    scale: float,
    mass_centre: np.ndarray,
    assembled_rate_parent: np.ndarray,
    assembled_formal_parent: np.ndarray,
    diagnostics: dict[str, float],
) -> None:
    cumulative_lagged = np.cumsum(lagged_block_difference) / scale
    cumulative_assembled = np.cumsum(assembled_block_difference) / scale
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.2), constrained_layout=True)
    axes[0, 0].plot(
        energy_centre_ev,
        lagged_block_difference / scale,
        label="Lagged block halo",
    )
    axes[0, 0].plot(
        energy_centre_ev,
        assembled_block_difference / scale,
        ls="--",
        label="Assembled global halo",
    )
    axes[0, 0].set_xscale("log")
    axes[0, 0].set_yscale("symlog", linthresh=1.0e-6)
    axes[0, 0].set(
        xlabel="Block-centre photon energy (eV)",
        ylabel="Signed source difference / column scale",
        title="(a) Frequency-block source mismatch",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].plot(energy_centre_ev, cumulative_lagged, label="Lagged block halo")
    axes[0, 1].plot(
        energy_centre_ev,
        cumulative_assembled,
        ls="--",
        label="Assembled global halo",
    )
    axes[0, 1].set_xscale("log")
    axes[0, 1].set(
        xlabel="Upper cumulative photon energy (eV)",
        ylabel="Cumulative signed difference / column scale",
        title="(b) Cancellation across the full band",
    )
    axes[0, 1].legend(frameon=False)
    axes[1, 0].plot(mass_centre, assembled_rate_parent, label="Comoving group rate")
    axes[1, 0].plot(
        mass_centre,
        assembled_formal_parent,
        ls="--",
        label="Inverse lab four-force",
    )
    heating_scale = max(
        float(np.max(np.abs(assembled_rate_parent))),
        float(np.max(np.abs(assembled_formal_parent))),
    )
    axes[1, 0].set_yscale(
        "symlog", linthresh=max(heating_scale * 1.0e-5, np.finfo(float).tiny)
    )
    axes[1, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Material heating (erg s$^{-1}$ cm$^{-3}$)",
        title="(c) Assembled-state depth profile",
    )
    axes[1, 0].legend(frameon=False)
    names = ["Rate/direct", "Volume L1", "Column total"]
    values = [
        diagnostics["direct_rate_l1"],
        diagnostics["assembled_volume_l1"],
        diagnostics["assembled_global"],
    ]
    axes[1, 1].bar(names, values, color=["#4c78a8", "#f58518", "#54a24b"])
    axes[1, 1].axhline(1.0e-3, color="0.25", ls="--", label="Frame/source gate")
    axes[1, 1].set_yscale("log")
    axes[1, 1].set(
        ylabel="Relative discrepancy",
        title="(d) Formal diagnostic gates",
    )
    axes[1, 1].tick_params(axis="x", rotation=12)
    axes[1, 1].legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def assembled_block_diagnostics(
    protocol: dict[str, object],
    context: dict[str, object],
    updated: dict[str, np.ndarray],
    mapped: np.ndarray,
    block_index: int,
) -> dict[str, object]:
    """在全局拼接 halo 上计算一个核心块的三条源项路径。"""
    block = context["blocks"][block_index]
    local = block.local_stencil
    fields = phase7b7e._local_fields(context, block, updated)
    full_active_start = int(context["stencil"].active_outer_group_start)
    full_active_stop = int(context["stencil"].active_outer_group_stop)
    physical_start = max(block.outer_group_start, full_active_start)
    physical_stop = min(block.outer_group_stop, full_active_stop)
    if physical_stop > physical_start:
        # 中文：正式诊断必须让核心块与所有 halo 同时读取拼接后的全局新态。
        fields["outer"][
            physical_start - block.outer_group_start : physical_stop
            - block.outer_group_start
        ] = mapped[
            physical_start - full_active_start : physical_stop
            - full_active_start
        ]
    beta = np.asarray(context["beta"])
    gamma = 1.0 / np.sqrt(1.0 - beta**2)
    transform = lorentz_ray_transform(
        context["mu"], context["weight"], beta
    )
    comoving = comoving_group_radiation(
        fields["outer"],
        local.outer_lab_edge_hz,
        local.comoving_collision_edge_hz,
        context["mu"],
        context["weight"],
        beta,
    )
    extinction = fields["true_absorption"] + fields["scattering"]
    emissivity = (
        fields["thermal_emissivity"]
        + fields["scattering"] * comoving.mean_intensity_density
    )
    collision_shape = (
        extinction.shape[0],
        len(context["mu"]),
        extinction.shape[1],
    )
    lab_extinction = lorentz_remap_comoving_group_extinction_to_lab(
        np.broadcast_to(extinction[:, None, :], collision_shape),
        local.comoving_collision_edge_hz,
        local.active_lab_edge_hz,
        transform.doppler_lab_to_comoving,
    )
    lab_emissivity = lorentz_remap_comoving_group_emissivity_to_lab(
        np.broadcast_to(emissivity[:, None, :], collision_shape),
        local.comoving_collision_edge_hz,
        local.active_lab_edge_hz,
        transform.doppler_lab_to_comoving,
    )
    current = np.asarray(mapped[block.core_group_start : block.core_group_stop])
    lab_collision = lab_emissivity - lab_extinction * current
    active_width = np.diff(local.active_lab_edge_hz)
    lab_energy = 2.0 * np.pi * np.einsum(
        "f,m,fmd->d", active_width, context["weight"], lab_collision
    )
    lab_momentum = 2.0 * np.pi / LIGHT_SPEED_CM_S * np.einsum(
        "f,m,m,fmd->d",
        active_width,
        context["weight"],
        context["mu"],
        lab_collision,
    )
    formal = -gamma * (lab_energy - beta * LIGHT_SPEED_CM_S * lab_momentum)
    comoving_collision = (
        emissivity[:, None, :]
        - extinction[:, None, :] * comoving.angle_intensity_density
    )
    collision_width = np.diff(local.comoving_collision_edge_hz)
    direct_group = 2.0 * np.pi * collision_width[:, None] * np.einsum(
        "md,fmd->fd", transform.comoving_angular_weight, comoving_collision
    )
    global_edge = np.asarray(context["stencil"].active_lab_edge_hz)
    left = np.flatnonzero(
        local.comoving_collision_edge_hz == global_edge[block.core_group_start]
    )
    right = np.flatnonzero(
        local.comoving_collision_edge_hz == global_edge[block.core_group_stop]
    )
    if left.size != 1 or right.size != 1:
        raise ArithmeticError("Phase 7B7f-r lost exact collision ownership")
    collision_start = int(left[0])
    collision_stop = int(right[0])
    direct = -np.sum(direct_group[collision_start:collision_stop], axis=0)
    core_width = np.diff(
        global_edge[block.core_group_start : block.core_group_stop + 1]
    )[:, None]
    rate = 4.0 * np.pi * np.sum(
        core_width
        * (
            fields["true_absorption"][collision_start:collision_stop]
            * comoving.mean_intensity_density[collision_start:collision_stop]
            - fields["thermal_emissivity"][collision_start:collision_stop]
        ),
        axis=0,
    )
    return {
        "block_index": block_index,
        "core_group_start": int(block.core_group_start),
        "core_group_stop": int(block.core_group_stop),
        "rate_material_heating_erg_s_cm3": np.array(rate, copy=True),
        "direct_comoving_material_heating_erg_s_cm3": np.array(
            direct, copy=True
        ),
        "inverse_lab_four_force_material_heating_erg_s_cm3": np.array(
            formal, copy=True
        ),
    }


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    context = phase7b7e.phase7b5x._context(protocol)
    updated = phase7b7e._updated_full_material(protocol)
    shape = phase7b7e._shape(protocol)
    mapped_path = ROOT / protocol["sources"]["mapped_radiation_state"]["path"]
    mapped = np.memmap(mapped_path, mode="r", dtype=np.float64, shape=shape)
    if float(np.min(mapped)) < gates["minimum_assembled_intensity_at_least"]:
        raise ArithmeticError("Phase 7B7f assembled radiation became negative")
    full_active_start = int(context["stencil"].active_outer_group_start)
    full_active_stop = int(context["stencil"].active_outer_group_stop)
    global_edge = np.asarray(context["stencil"].active_lab_edge_hz)
    beta = np.asarray(context["beta"])
    gamma = 1.0 / np.sqrt(1.0 - beta**2)
    transform = lorentz_ray_transform(
        context["mu"], context["weight"], beta
    )
    following = int(context["following"])
    subedge = phase7b7e.phase7b5x._subdivide_column_edge(
        context["full"]["edge_cm"][following], 16
    )
    subwidth = np.diff(subedge)
    assembled_rate = np.zeros(shape[2])
    assembled_direct = np.zeros(shape[2])
    assembled_formal = np.zeros(shape[2])
    lagged_rate_total = np.zeros(shape[2])
    lagged_formal_total = np.zeros(shape[2])
    ownership = np.zeros(shape[0], dtype=np.int64)
    rows: list[dict[str, float | int]] = []
    lagged_block_difference = []
    assembled_block_difference = []
    energy_centre_ev = []
    started = time.perf_counter()
    for block_index, block in enumerate(context["blocks"]):
        local = block.local_stencil
        fields = phase7b7e._local_fields(context, block, updated)
        physical_start = max(block.outer_group_start, full_active_start)
        physical_stop = min(block.outer_group_stop, full_active_stop)
        if physical_stop > physical_start:
            fields["outer"][
                physical_start - block.outer_group_start : physical_stop
                - block.outer_group_start
            ] = mapped[
                physical_start - full_active_start : physical_stop
                - full_active_start
            ]
        comoving = comoving_group_radiation(
            fields["outer"],
            local.outer_lab_edge_hz,
            local.comoving_collision_edge_hz,
            context["mu"],
            context["weight"],
            beta,
        )
        extinction = fields["true_absorption"] + fields["scattering"]
        emissivity = (
            fields["thermal_emissivity"]
            + fields["scattering"] * comoving.mean_intensity_density
        )
        collision_shape = (
            extinction.shape[0],
            len(context["mu"]),
            extinction.shape[1],
        )
        lab_extinction = lorentz_remap_comoving_group_extinction_to_lab(
            np.broadcast_to(extinction[:, None, :], collision_shape),
            local.comoving_collision_edge_hz,
            local.active_lab_edge_hz,
            transform.doppler_lab_to_comoving,
        )
        lab_emissivity = lorentz_remap_comoving_group_emissivity_to_lab(
            np.broadcast_to(emissivity[:, None, :], collision_shape),
            local.comoving_collision_edge_hz,
            local.active_lab_edge_hz,
            transform.doppler_lab_to_comoving,
        )
        current = np.asarray(
            mapped[block.core_group_start : block.core_group_stop]
        )
        lab_collision = lab_emissivity - lab_extinction * current
        active_width = np.diff(local.active_lab_edge_hz)
        lab_energy = 2.0 * np.pi * np.einsum(
            "f,m,fmd->d", active_width, context["weight"], lab_collision
        )
        lab_momentum = 2.0 * np.pi / LIGHT_SPEED_CM_S * np.einsum(
            "f,m,m,fmd->d",
            active_width,
            context["weight"],
            context["mu"],
            lab_collision,
        )
        formal = -gamma * (
            lab_energy - beta * LIGHT_SPEED_CM_S * lab_momentum
        )
        comoving_collision = (
            emissivity[:, None, :]
            - extinction[:, None, :] * comoving.angle_intensity_density
        )
        collision_width = np.diff(local.comoving_collision_edge_hz)
        direct_group = 2.0 * np.pi * collision_width[:, None] * np.einsum(
            "md,fmd->fd",
            transform.comoving_angular_weight,
            comoving_collision,
        )
        left = np.flatnonzero(
            local.comoving_collision_edge_hz
            == global_edge[block.core_group_start]
        )
        right = np.flatnonzero(
            local.comoving_collision_edge_hz
            == global_edge[block.core_group_stop]
        )
        if left.size != 1 or right.size != 1:
            raise ArithmeticError("Phase 7B7f lost exact collision ownership")
        collision_start = int(left[0])
        collision_stop = int(right[0])
        direct = -np.sum(
            direct_group[collision_start:collision_stop], axis=0
        )
        core_width = np.diff(
            global_edge[block.core_group_start : block.core_group_stop + 1]
        )[:, None]
        rate = 4.0 * np.pi * np.sum(
            core_width
            * (
                fields["true_absorption"][collision_start:collision_stop]
                * comoving.mean_intensity_density[
                    collision_start:collision_stop
                ]
                - fields["thermal_emissivity"][
                    collision_start:collision_stop
                ]
            ),
            axis=0,
        )
        ownership[block.core_group_start : block.core_group_stop] += 1
        assembled_rate += rate
        assembled_direct += direct
        assembled_formal += formal
        rate_column = float(np.sum(subwidth * rate))
        formal_column = float(np.sum(subwidth * formal))
        assembled_difference = rate_column - formal_column
        partial_path = OUTPUT / f"phase7b7e_block{block_index:02d}_partial.npz"
        with np.load(partial_path) as partial:
            lagged_rate = np.asarray(
                partial["rate_material_heating_erg_s_cm3"]
            )
            lagged_formal = -gamma * (
                np.asarray(partial["radiation_source_energy_lab_erg_s_cm3"])
                - beta
                * LIGHT_SPEED_CM_S
                * np.asarray(
                    partial["radiation_source_momentum_lab_dyn_cm3"]
                )
            )
        lagged_difference = float(
            np.sum(subwidth * (lagged_rate - lagged_formal))
        )
        lagged_rate_total += lagged_rate
        lagged_formal_total += lagged_formal
        lower_ev = float(
            global_edge[block.core_group_start] * PLANCK_ERG_S / EV_ERG
        )
        upper_ev = float(
            global_edge[block.core_group_stop] * PLANCK_ERG_S / EV_ERG
        )
        rows.append(
            {
                "block_index": block_index,
                "core_group_start": int(block.core_group_start),
                "core_group_stop": int(block.core_group_stop),
                "lower_energy_ev": lower_ev,
                "upper_energy_ev": upper_ev,
                "assembled_rate_column_erg_s_cm2": rate_column,
                "assembled_formal_column_erg_s_cm2": formal_column,
                "assembled_signed_difference_erg_s_cm2": assembled_difference,
                "lagged_signed_difference_erg_s_cm2": lagged_difference,
            }
        )
        energy_centre_ev.append(np.sqrt(lower_ev * upper_ev))
        lagged_block_difference.append(lagged_difference)
        assembled_block_difference.append(assembled_difference)
        del (
            fields,
            comoving,
            extinction,
            emissivity,
            lab_extinction,
            lab_emissivity,
            current,
            lab_collision,
            lab_energy,
            lab_momentum,
            formal,
            comoving_collision,
            direct_group,
            direct,
            rate,
            lagged_rate,
            lagged_formal,
        )
        gc.collect()
        if (block_index + 1) % 10 == 0 or block_index + 1 == len(context["blocks"]):
            print(
                json.dumps(
                    {
                        "completed_blocks": block_index + 1,
                        "total_blocks": len(context["blocks"]),
                    }
                ),
                flush=True,
            )
    wall_runtime = time.perf_counter() - started
    assembled_metrics = _source_metrics(
        assembled_rate, assembled_formal, subwidth
    )
    direct_metrics = _source_metrics(
        assembled_rate, assembled_direct, subwidth
    )
    # 中文：旧失败门在 4096 子格上先取绝对值，不能用 256 父格平均量替代。
    lagged_rate = lagged_rate_total
    lagged_formal = lagged_formal_total
    lagged_metrics = _source_metrics(lagged_rate, lagged_formal, subwidth)
    phase7b7e_summary = json.loads(
        (ROOT / protocol["sources"]["phase7b7e_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    lagged_l1_reproduction = _relative_error(
        lagged_metrics[0],
        float(
            phase7b7e_summary[
                "rate_heating_vs_inverse_four_force_volume_l1"
            ]
        ),
    )
    lagged_global_reproduction = _relative_error(
        lagged_metrics[1],
        float(
            phase7b7e_summary[
                "rate_heating_vs_inverse_four_force_global_fraction"
            ]
        ),
    )
    arrays_finite = all(
        np.all(np.isfinite(value))
        for value in (assembled_rate, assembled_direct, assembled_formal)
    )
    peak_rss_mib = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    ) / MIB
    decision = {
        "frozen_protocol_sources_partials_and_state_passed": True,
        "assembled_global_state_and_ownership_passed": bool(
            len(rows) == gates["block_count_exactly"]
            and int(np.sum(ownership))
            == gates["owned_frequency_group_count_exactly"]
            and np.all(ownership == 1)
            and float(np.min(mapped))
            >= gates["minimum_assembled_intensity_at_least"]
            and arrays_finite
        ),
        "stored_lagged_failure_reproduced": bool(
            lagged_l1_reproduction
            < gates[
                "stored_lagged_volume_l1_reproduction_relative_error_below"
            ]
            and lagged_global_reproduction
            < gates[
                "stored_lagged_global_reproduction_relative_error_below"
            ]
        ),
        "direct_comoving_source_rate_identity_passed": bool(
            direct_metrics[0]
            < gates["direct_comoving_source_vs_group_rate_volume_l1_below"]
        ),
        "assembled_frame_source_consistency_passed": bool(
            assembled_metrics[0]
            < gates["assembled_rate_vs_inverse_four_force_volume_l1_below"]
            and assembled_metrics[1]
            < gates[
                "assembled_rate_vs_inverse_four_force_global_fraction_below"
            ]
        ),
        "resource_and_runtime_gates_passed": bool(
            peak_rss_mib < gates["peak_rss_strictly_below_mib"]
            and wall_runtime < gates["wall_time_strictly_below_s"]
        ),
        "accepted_as_radiation_or_coupled_fixed_point": False,
        "second_material_update_authorized": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b7f_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_sources_partials_and_state_passed",
            "assembled_global_state_and_ownership_passed",
            "stored_lagged_failure_reproduced",
            "direct_comoving_source_rate_identity_passed",
            "assembled_frame_source_consistency_passed",
            "resource_and_runtime_gates_passed",
        )
    )
    decision["lagged_halo_diagnostic_timing_identified"] = bool(
        decision["stored_lagged_failure_reproduced"]
        and decision["direct_comoving_source_rate_identity_passed"]
        and decision["assembled_frame_source_consistency_passed"]
        and phase7b7e_summary["decision"]["frame_source_consistency_passed"]
        is False
    )
    decision["bounded_coupled_continuation_design_authorized"] = bool(
        decision["phase7b7f_gate_passed"]
    )
    array_path = OUTPUT / "phase7b7f_assembled_diagnostics.npz"
    _write_npz_atomic(
        array_path,
        assembled_rate_material_heating_erg_s_cm3=assembled_rate,
        assembled_direct_comoving_material_heating_erg_s_cm3=assembled_direct,
        assembled_inverse_lab_four_force_material_heating_erg_s_cm3=assembled_formal,
        lagged_rate_material_heating_erg_s_cm3=lagged_rate,
        lagged_inverse_lab_four_force_material_heating_erg_s_cm3=lagged_formal,
        energy_centre_ev=np.asarray(energy_centre_ev),
        lagged_block_signed_difference_erg_s_cm2=np.asarray(
            lagged_block_difference
        ),
        assembled_block_signed_difference_erg_s_cm2=np.asarray(
            assembled_block_difference
        ),
    )
    csv_path = OUTPUT / "phase7b7f_frequency_block_diagnostics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with np.load(
        ROOT / protocol["sources"]["phase7b4r_material"]["path"]
    ) as material:
        mass_edge = np.asarray(material["mass_fraction_edges"])
    rate_parent = np.mean(assembled_rate.reshape(256, 16), axis=1)[:128]
    formal_parent = np.mean(assembled_formal.reshape(256, 16), axis=1)[:128]
    column_scale = max(
        abs(assembled_metrics[2]),
        abs(assembled_metrics[3]),
        abs(lagged_metrics[2]),
        abs(lagged_metrics[3]),
    )
    figure_path = OUTPUT / "phase7b7f_assembled_diagnostics.png"
    _plot(
        figure_path,
        np.asarray(energy_centre_ev),
        np.asarray(lagged_block_difference),
        np.asarray(assembled_block_difference),
        column_scale,
        0.5 * (mass_edge[:-1] + mass_edge[1:]),
        rate_parent,
        formal_parent,
        {
            "direct_rate_l1": direct_metrics[0],
            "assembled_volume_l1": assembled_metrics[0],
            "assembled_global": assembled_metrics[1],
        },
    )
    report: dict[str, object] = {
        "phase": "7B7f assembled-state formal source diagnostics",
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": _sha256(protocol_path),
        "block_count": len(rows),
        "owned_frequency_group_count": int(np.sum(ownership)),
        "minimum_assembled_intensity": float(np.min(mapped)),
        "lagged_rate_vs_inverse_four_force_volume_l1": lagged_metrics[0],
        "lagged_rate_vs_inverse_four_force_global_fraction": lagged_metrics[1],
        "lagged_volume_l1_reproduction_relative_error": lagged_l1_reproduction,
        "lagged_global_reproduction_relative_error": lagged_global_reproduction,
        "assembled_rate_vs_direct_comoving_source_volume_l1": direct_metrics[0],
        "assembled_rate_vs_inverse_four_force_volume_l1": assembled_metrics[0],
        "assembled_rate_vs_inverse_four_force_global_fraction": assembled_metrics[1],
        "assembled_integrated_rate_heating_erg_s_cm2": assembled_metrics[2],
        "assembled_integrated_formal_heating_erg_s_cm2": assembled_metrics[3],
        "peak_rss_mib": peak_rss_mib,
        "wall_runtime_s": wall_runtime,
        "array_path": str(array_path.relative_to(ROOT)),
        "array_sha256": _sha256(array_path),
        "block_csv_path": str(csv_path.relative_to(ROOT)),
        "block_csv_sha256": _sha256(csv_path),
        "decision": decision,
        "figures": [figure_path.name],
    }
    summary_path = OUTPUT / "phase7b7f_assembled_diagnostics_summary.json"
    _write_json_atomic(summary_path, report)
    return report


def reassemble_retained(protocol_path: Path) -> dict[str, object]:
    """不重算辐射变换，只修复已完成运行的子格旧门汇总。"""
    protocol = _load_protocol(protocol_path)
    gates = protocol["gates"]
    context = phase7b7e.phase7b5x._context(protocol)
    shape = phase7b7e._shape(protocol)
    mapped = np.memmap(
        ROOT / protocol["sources"]["mapped_radiation_state"]["path"],
        mode="r",
        dtype=np.float64,
        shape=shape,
    )
    following = int(context["following"])
    subedge = phase7b7e.phase7b5x._subdivide_column_edge(
        context["full"]["edge_cm"][following], 16
    )
    subwidth = np.diff(subedge)
    beta = np.asarray(context["beta"])
    gamma = 1.0 / np.sqrt(1.0 - beta**2)
    lagged_rate = np.zeros(shape[2])
    lagged_formal = np.zeros(shape[2])
    for block_index in range(int(protocol["configuration"]["block_count"])):
        with np.load(OUTPUT / f"phase7b7e_block{block_index:02d}_partial.npz") as partial:
            lagged_rate += np.asarray(
                partial["rate_material_heating_erg_s_cm3"]
            )
            lagged_formal += -gamma * (
                np.asarray(partial["radiation_source_energy_lab_erg_s_cm3"])
                - beta
                * LIGHT_SPEED_CM_S
                * np.asarray(
                    partial["radiation_source_momentum_lab_dyn_cm3"]
                )
            )
    array_path = OUTPUT / "phase7b7f_assembled_diagnostics.npz"
    with np.load(array_path) as retained:
        assembled_rate = np.array(
            retained["assembled_rate_material_heating_erg_s_cm3"], copy=True
        )
        assembled_direct = np.array(
            retained[
                "assembled_direct_comoving_material_heating_erg_s_cm3"
            ],
            copy=True,
        )
        assembled_formal = np.array(
            retained[
                "assembled_inverse_lab_four_force_material_heating_erg_s_cm3"
            ],
            copy=True,
        )
        energy_centre_ev = np.array(retained["energy_centre_ev"], copy=True)
        lagged_block_difference = np.array(
            retained["lagged_block_signed_difference_erg_s_cm2"], copy=True
        )
        assembled_block_difference = np.array(
            retained["assembled_block_signed_difference_erg_s_cm2"], copy=True
        )
    assembled_metrics = _source_metrics(
        assembled_rate, assembled_formal, subwidth
    )
    direct_metrics = _source_metrics(
        assembled_rate, assembled_direct, subwidth
    )
    lagged_metrics = _source_metrics(lagged_rate, lagged_formal, subwidth)
    phase7b7e_summary = json.loads(
        (ROOT / protocol["sources"]["phase7b7e_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    lagged_l1_reproduction = _relative_error(
        lagged_metrics[0],
        float(
            phase7b7e_summary[
                "rate_heating_vs_inverse_four_force_volume_l1"
            ]
        ),
    )
    lagged_global_reproduction = _relative_error(
        lagged_metrics[1],
        float(
            phase7b7e_summary[
                "rate_heating_vs_inverse_four_force_global_fraction"
            ]
        ),
    )
    previous = json.loads(
        (OUTPUT / "phase7b7f_assembled_diagnostics_summary.json").read_text(
            encoding="utf-8"
        )
    )
    peak_rss_mib = float(previous["peak_rss_mib"])
    wall_runtime = float(previous["wall_runtime_s"])
    arrays_finite = all(
        np.all(np.isfinite(value))
        for value in (
            assembled_rate,
            assembled_direct,
            assembled_formal,
            lagged_rate,
            lagged_formal,
        )
    )
    decision = {
        "frozen_protocol_sources_partials_and_state_passed": True,
        "assembled_global_state_and_ownership_passed": bool(
            energy_centre_ev.size == gates["block_count_exactly"]
            and shape[0] == gates["owned_frequency_group_count_exactly"]
            and float(np.min(mapped))
            >= gates["minimum_assembled_intensity_at_least"]
            and arrays_finite
        ),
        "stored_lagged_failure_reproduced": bool(
            lagged_l1_reproduction
            < gates[
                "stored_lagged_volume_l1_reproduction_relative_error_below"
            ]
            and lagged_global_reproduction
            < gates[
                "stored_lagged_global_reproduction_relative_error_below"
            ]
        ),
        "direct_comoving_source_rate_identity_passed": bool(
            direct_metrics[0]
            < gates["direct_comoving_source_vs_group_rate_volume_l1_below"]
        ),
        "assembled_frame_source_consistency_passed": bool(
            assembled_metrics[0]
            < gates["assembled_rate_vs_inverse_four_force_volume_l1_below"]
            and assembled_metrics[1]
            < gates[
                "assembled_rate_vs_inverse_four_force_global_fraction_below"
            ]
        ),
        "resource_and_runtime_gates_passed": bool(
            peak_rss_mib < gates["peak_rss_strictly_below_mib"]
            and wall_runtime < gates["wall_time_strictly_below_s"]
        ),
        "accepted_as_radiation_or_coupled_fixed_point": False,
        "second_material_update_authorized": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b7f_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_sources_partials_and_state_passed",
            "assembled_global_state_and_ownership_passed",
            "stored_lagged_failure_reproduced",
            "direct_comoving_source_rate_identity_passed",
            "assembled_frame_source_consistency_passed",
            "resource_and_runtime_gates_passed",
        )
    )
    decision["lagged_halo_diagnostic_timing_identified"] = bool(
        decision["stored_lagged_failure_reproduced"]
        and decision["direct_comoving_source_rate_identity_passed"]
        and decision["assembled_frame_source_consistency_passed"]
        and phase7b7e_summary["decision"]["frame_source_consistency_passed"]
        is False
    )
    decision["bounded_coupled_continuation_design_authorized"] = bool(
        decision["phase7b7f_gate_passed"]
    )
    _write_npz_atomic(
        array_path,
        assembled_rate_material_heating_erg_s_cm3=assembled_rate,
        assembled_direct_comoving_material_heating_erg_s_cm3=assembled_direct,
        assembled_inverse_lab_four_force_material_heating_erg_s_cm3=assembled_formal,
        lagged_rate_material_heating_erg_s_cm3=lagged_rate,
        lagged_inverse_lab_four_force_material_heating_erg_s_cm3=lagged_formal,
        energy_centre_ev=energy_centre_ev,
        lagged_block_signed_difference_erg_s_cm2=lagged_block_difference,
        assembled_block_signed_difference_erg_s_cm2=assembled_block_difference,
    )
    with np.load(
        ROOT / protocol["sources"]["phase7b4r_material"]["path"]
    ) as material:
        mass_edge = np.asarray(material["mass_fraction_edges"])
    rate_parent = np.mean(assembled_rate.reshape(256, 16), axis=1)[:128]
    formal_parent = np.mean(assembled_formal.reshape(256, 16), axis=1)[:128]
    column_scale = max(
        abs(assembled_metrics[2]),
        abs(assembled_metrics[3]),
        abs(lagged_metrics[2]),
        abs(lagged_metrics[3]),
    )
    figure_path = OUTPUT / "phase7b7f_assembled_diagnostics.png"
    _plot(
        figure_path,
        energy_centre_ev,
        lagged_block_difference,
        assembled_block_difference,
        column_scale,
        0.5 * (mass_edge[:-1] + mass_edge[1:]),
        rate_parent,
        formal_parent,
        {
            "direct_rate_l1": direct_metrics[0],
            "assembled_volume_l1": assembled_metrics[0],
            "assembled_global": assembled_metrics[1],
        },
    )
    csv_path = OUTPUT / "phase7b7f_frequency_block_diagnostics.csv"
    report: dict[str, object] = {
        "phase": "7B7f assembled-state formal source diagnostics",
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": _sha256(protocol_path),
        "postprocessing_reassembled_without_transport": True,
        "block_count": int(energy_centre_ev.size),
        "owned_frequency_group_count": shape[0],
        "minimum_assembled_intensity": float(np.min(mapped)),
        "lagged_rate_vs_inverse_four_force_volume_l1": lagged_metrics[0],
        "lagged_rate_vs_inverse_four_force_global_fraction": lagged_metrics[1],
        "lagged_volume_l1_reproduction_relative_error": lagged_l1_reproduction,
        "lagged_global_reproduction_relative_error": lagged_global_reproduction,
        "assembled_rate_vs_direct_comoving_source_volume_l1": direct_metrics[0],
        "assembled_rate_vs_inverse_four_force_volume_l1": assembled_metrics[0],
        "assembled_rate_vs_inverse_four_force_global_fraction": assembled_metrics[1],
        "assembled_integrated_rate_heating_erg_s_cm2": assembled_metrics[2],
        "assembled_integrated_formal_heating_erg_s_cm2": assembled_metrics[3],
        "peak_rss_mib": peak_rss_mib,
        "wall_runtime_s": wall_runtime,
        "array_path": str(array_path.relative_to(ROOT)),
        "array_sha256": _sha256(array_path),
        "block_csv_path": str(csv_path.relative_to(ROOT)),
        "block_csv_sha256": _sha256(csv_path),
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b7f_assembled_diagnostics_summary.json", report
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b7f_preregistered_assembled_diagnostics.json",
    )
    parser.add_argument("--reassemble-retained", action="store_true")
    args = parser.parse_args()
    report = (
        reassemble_retained(args.protocol)
        if args.reassemble_retained
        else run(args.protocol)
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
