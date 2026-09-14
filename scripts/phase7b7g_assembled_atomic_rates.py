"""Phase 7B7g：在全局拼接新辐射态上提取 H/He 原子率。"""

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

from eccentric_tde_observer.mixed_frame_frequency import comoving_group_radiation
from eccentric_tde_observer.multigroup_continuum import ground_state_milne_multigroup

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
    "df4cf89fd7711c23fc2eafe1d98939631cdec0b739447e0766cf9b335f95d195"
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


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B7g protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            if _sha256(ROOT / source["path"]) != source["sha256"]:
                raise RuntimeError(
                    f"frozen Phase 7B7g source changed: {source['path']}"
                )
    return protocol


def _zero(depth: int) -> dict[str, np.ndarray]:
    return {
        "photoionization_s1": np.zeros((depth, 3)),
        "spontaneous_recombination_cm3_s": np.zeros((depth, 3)),
        "stimulated_recombination_cm3_s": np.zeros((depth, 3)),
        "total_recombination_cm3_s": np.zeros((depth, 3)),
        "absorbed_power_erg_s_cm3": np.zeros(depth),
        "emitted_power_erg_s_cm3": np.zeros(depth),
        "rate_material_heating_erg_s_cm3": np.zeros(depth),
    }


def run_worker(
    protocol_path: Path,
    block_index: int,
    partial_path: Path,
    report_path: Path,
) -> None:
    # 中文：10 GB 状态只由父进程验哈希；短寿命子进程验证冻结协议后只读映射。
    protocol = _load_protocol(protocol_path, validate_sources=False)
    configuration = protocol["configuration"]
    context = phase7b7e.phase7b5x._context(protocol)
    updated = phase7b7e._updated_full_material(protocol)
    shape = phase7b7e._shape(protocol)
    if block_index < 0 or block_index >= len(context["blocks"]):
        raise ValueError("Phase 7B7g block index is invalid")
    mapped = np.memmap(
        ROOT / protocol["sources"]["mapped_radiation_state"]["path"],
        mode="r",
        dtype=np.float64,
        shape=shape,
    )
    block = context["blocks"][block_index]
    local = block.local_stencil
    fields = phase7b7e._local_fields(context, block, updated)
    full_active_start = int(context["stencil"].active_outer_group_start)
    full_active_stop = int(context["stencil"].active_outer_group_stop)
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
    started = time.perf_counter()
    comoving = comoving_group_radiation(
        fields["outer"],
        local.outer_lab_edge_hz,
        local.comoving_collision_edge_hz,
        context["mu"],
        context["weight"],
        context["beta"],
    )
    global_edge = np.asarray(context["stencil"].active_lab_edge_hz)
    left = np.flatnonzero(
        local.comoving_collision_edge_hz == global_edge[block.core_group_start]
    )
    right = np.flatnonzero(
        local.comoving_collision_edge_hz == global_edge[block.core_group_stop]
    )
    if left.size != 1 or right.size != 1:
        raise ArithmeticError("Phase 7B7g lost exact collision ownership")
    collision_start = int(left[0])
    collision_stop = int(right[0])
    density = np.repeat(updated["density_parent"], 16)
    temperature = np.repeat(updated["temperature_parent"], 16)
    hydrogen = np.repeat(updated["hydrogen_parent"], 16, axis=0)
    helium = np.repeat(updated["helium_parent"], 16, axis=0)
    microphysics = ground_state_milne_multigroup(
        density,
        temperature,
        global_edge[block.core_group_start : block.core_group_stop + 1],
        comoving.mean_intensity_density[collision_start:collision_stop],
        hydrogen[:, 0],
        hydrogen[:, 1],
        helium[:, 0],
        helium[:, 1],
        helium[:, 2],
        order_per_group=int(configuration["rate_quadrature_order_per_group"]),
    )
    rates = microphysics.radiative_rates
    arrays = {
        "photoionization_s1": np.asarray(rates.photoionization_s1),
        "spontaneous_recombination_cm3_s": np.asarray(
            rates.spontaneous_recombination_cm3_s
        ),
        "stimulated_recombination_cm3_s": np.asarray(
            rates.stimulated_recombination_cm3_s
        ),
        "total_recombination_cm3_s": np.asarray(
            rates.total_recombination_cm3_s
        ),
        "absorbed_power_erg_s_cm3": np.asarray(
            microphysics.absorbed_power_erg_s_cm3
        ),
        "emitted_power_erg_s_cm3": np.asarray(
            microphysics.emitted_power_erg_s_cm3
        ),
        "rate_material_heating_erg_s_cm3": np.asarray(
            microphysics.radiative_heating_erg_s_cm3
        ),
    }
    _write_npz_atomic(partial_path, **arrays)
    minimum_mean = float(
        np.min(comoving.mean_intensity_density[collision_start:collision_stop])
    )
    del fields, comoving, microphysics, rates, arrays, mapped
    gc.collect()
    peak_rss_mib = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    ) / MIB
    _write_json_atomic(
        report_path,
        {
            "block_index": block_index,
            "core_group_start": int(block.core_group_start),
            "core_group_stop": int(block.core_group_stop),
            "minimum_owned_comoving_mean_intensity": minimum_mean,
            "runtime_s": time.perf_counter() - started,
            "peak_process_rss_mib": peak_rss_mib,
            "partial_path": str(partial_path.resolve().relative_to(ROOT)),
            "partial_sha256": _sha256(partial_path),
        },
    )


def _mirror_residual(array: np.ndarray) -> float:
    difference = array[:128] - array[128:][::-1]
    scale = float(np.max(np.abs(array)))
    maximum = float(np.max(np.abs(difference)))
    return maximum / scale if scale > 0.0 else maximum


def _plot(
    path: Path,
    mass_centre: np.ndarray,
    parent: dict[str, np.ndarray],
    reference_heating: np.ndarray,
    heating_l1: float,
    mirror: float,
    maximum_rss: float,
    wall_runtime: float,
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    photo = parent["photoionization_s1"][:128]
    recombination = parent["total_recombination_cm3_s"][:128]
    for index, label in enumerate(("H I", "He I", "He II")):
        axes[0, 0].semilogy(mass_centre, photo[:, index], label=label)
        axes[0, 1].semilogy(mass_centre, recombination[:, index], label=label)
    axes[0, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Photoionization rate (s$^{-1}$)",
        title="(a) Assembled-state photoionization",
    )
    axes[0, 1].set(
        xlabel="Mass fraction from surface",
        ylabel="Recombination coefficient (cm$^3$ s$^{-1}$)",
        title="(b) Assembled-state recombination",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].legend(frameon=False)
    heating = parent["rate_material_heating_erg_s_cm3"][:128]
    scale = max(float(np.max(np.abs(heating))), float(np.max(np.abs(reference_heating))))
    axes[1, 0].plot(mass_centre, heating, label="Recomputed atomic-rate heating")
    axes[1, 0].plot(
        mass_centre,
        reference_heating,
        ls="--",
        label="Phase 7B7f reference",
    )
    axes[1, 0].set_yscale(
        "symlog", linthresh=max(scale * 1.0e-2, np.finfo(float).tiny)
    )
    axes[1, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Material heating (erg s$^{-1}$ cm$^{-3}$)",
        title="(c) Independent heating reproduction",
    )
    axes[1, 0].legend(frameon=False)
    axes[1, 1].axis("off")
    axes[1, 1].text(
        0.05,
        0.88,
        "(d) Validation summary\n\n"
        f"Heating reference volume L1 = {heating_l1:.3e}\n"
        f"Maximum parent mirror residual = {mirror:.3e}\n"
        f"Maximum process RSS = {maximum_rss:.1f} MiB\n"
        f"Total wall time = {wall_runtime:.1f} s",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=12,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    block_count = int(configuration["block_count"])
    partial_paths = [
        OUTPUT / f"phase7b7g_block{index:02d}_partial.npz"
        for index in range(block_count)
    ]
    report_paths = [
        OUTPUT / f"phase7b7g_block{index:02d}.json"
        for index in range(block_count)
    ]
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
            raise RuntimeError(f"Phase 7B7g worker batch failed: {return_codes}")
        completed = offset + len(return_codes)
        if completed % 10 == 0 or completed == block_count:
            print(
                json.dumps(
                    {"completed_blocks": completed, "total_blocks": block_count}
                ),
                flush=True,
            )
    wall_runtime = time.perf_counter() - started
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    reports.sort(key=lambda row: int(row["block_index"]))
    shape = phase7b7e._shape(protocol)
    combined = _zero(shape[2])
    ownership = np.zeros(shape[0], dtype=np.int64)
    for report in reports:
        block_index = int(report["block_index"])
        partial_path = partial_paths[block_index]
        if _sha256(partial_path) != report["partial_sha256"]:
            raise RuntimeError("Phase 7B7g partial hash changed")
        ownership[
            int(report["core_group_start"]) : int(report["core_group_stop"])
        ] += 1
        with np.load(partial_path) as partial:
            for name in combined:
                combined[name] += np.asarray(partial[name])
    context = phase7b7e.phase7b5x._context(protocol)
    following = int(context["following"])
    subedge = phase7b7e.phase7b5x._subdivide_column_edge(
        context["full"]["edge_cm"][following], 16
    )
    subwidth = np.diff(subedge)
    with np.load(
        ROOT / protocol["sources"]["assembled_heating_reference"]["path"]
    ) as reference:
        reference_heating = np.asarray(
            reference["assembled_rate_material_heating_erg_s_cm3"]
        )
    heating_difference = combined["rate_material_heating_erg_s_cm3"] - reference_heating
    heating_l1 = float(np.sum(subwidth * np.abs(heating_difference))) / max(
        float(
            np.sum(
                subwidth
                * np.abs(combined["rate_material_heating_erg_s_cm3"])
            )
        ),
        float(np.sum(subwidth * np.abs(reference_heating))),
    )
    parent = {
        name: np.mean(array.reshape(256, 16, *array.shape[1:]), axis=1)
        for name, array in combined.items()
    }
    mirror = {name: _mirror_residual(array) for name, array in parent.items()}
    maximum_mirror = max(mirror.values())
    all_finite = all(np.all(np.isfinite(array)) for array in combined.values())
    atomic_names = (
        "photoionization_s1",
        "spontaneous_recombination_cm3_s",
        "stimulated_recombination_cm3_s",
        "total_recombination_cm3_s",
    )
    all_atomic_nonnegative = all(
        np.all(combined[name] >= 0.0) for name in atomic_names
    )
    minimum_mean = min(
        float(row["minimum_owned_comoving_mean_intensity"]) for row in reports
    )
    rss = [float(row["peak_process_rss_mib"]) for row in reports]
    gates = protocol["gates"]
    decision = {
        "frozen_protocol_sources_and_state_passed": True,
        "block_and_frequency_ownership_passed": bool(
            len(reports) == gates["block_count_exactly"]
            and int(np.sum(ownership))
            == gates["owned_frequency_group_count_exactly"]
            and np.all(ownership == 1)
        ),
        "assembled_rates_and_arrays_valid": bool(
            minimum_mean >= gates["minimum_comoving_mean_intensity_at_least"]
            and all_finite
            and all_atomic_nonnegative
        ),
        "heating_reference_identity_passed": bool(
            heating_l1 < gates["heating_reference_volume_l1_below"]
        ),
        "parent_mirror_symmetry_passed": bool(
            maximum_mirror < gates["maximum_parent_mirror_residual_below"]
        ),
        "resource_and_runtime_gates_passed": bool(
            all(
                value < gates["each_process_peak_rss_strictly_below_mib"]
                for value in rss
            )
            and wall_runtime < gates["total_wall_time_strictly_below_s"]
        ),
        "material_update_performed": False,
        "radiation_update_performed": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b7g_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_sources_and_state_passed",
            "block_and_frequency_ownership_passed",
            "assembled_rates_and_arrays_valid",
            "heating_reference_identity_passed",
            "parent_mirror_symmetry_passed",
            "resource_and_runtime_gates_passed",
        )
    )
    decision["one_second_physical_time_level_picard_direction_authorized"] = bool(
        decision["phase7b7g_gate_passed"]
    )
    coefficient_path = OUTPUT / "phase7b7g_assembled_atomic_rates.npz"
    _write_npz_atomic(
        coefficient_path,
        **{name: np.asarray(value) for name, value in combined.items()},
        **{f"parent_{name}": np.asarray(value) for name, value in parent.items()},
        **{f"half_{name}": np.asarray(value[:128]) for name, value in parent.items()},
    )
    with np.load(
        ROOT / protocol["sources"]["phase7b4r_material"]["path"]
    ) as material:
        mass_edge = np.asarray(material["mass_fraction_edges"])
    figure_path = OUTPUT / "phase7b7g_assembled_atomic_rates.png"
    _plot(
        figure_path,
        0.5 * (mass_edge[:-1] + mass_edge[1:]),
        parent,
        np.mean(reference_heating.reshape(256, 16), axis=1)[:128],
        heating_l1,
        maximum_mirror,
        max(rss),
        wall_runtime,
    )
    report = {
        "phase": "7B7g assembled-state H/He atomic rates",
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": _sha256(protocol_path),
        "block_count": len(reports),
        "owned_frequency_group_count": int(np.sum(ownership)),
        "minimum_owned_comoving_mean_intensity": minimum_mean,
        "heating_reference_volume_l1": heating_l1,
        "maximum_parent_mirror_residual": maximum_mirror,
        "parent_mirror_residuals": mirror,
        "maximum_process_peak_rss_mib": max(rss),
        "total_wall_runtime_s": wall_runtime,
        "coefficient_path": str(coefficient_path.relative_to(ROOT)),
        "coefficient_sha256": _sha256(coefficient_path),
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b7g_assembled_atomic_rates_summary.json", report
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b7g_preregistered_assembled_atomic_rates.json",
    )
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--partial", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.block_index is None or args.partial is None or args.worker_report is None:
            raise ValueError("Phase 7B7g worker arguments are incomplete")
        run_worker(
            args.protocol, args.block_index, args.partial, args.worker_report
        )
        return
    print(json.dumps(run(args.protocol), indent=2))


if __name__ == "__main__":
    main()
