"""Phase 7B8f：回溯提案的全局正式反馈与三重真残差门。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.radiation_matter_feedback import (
    ground_state_material_specific_energy_erg_g,
)

try:
    from scripts import phase7b7f_assembled_diagnostics as phase7b7f
    from scripts import phase7b7j_second_assembled_feedback as phase7b7j
    from scripts import phase7b8c_secant_feedback as phase7b8c
    from scripts import phase7b8e_backtracked_radiation_map as phase7b8e
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b7f_assembled_diagnostics as phase7b7f  # type: ignore[no-redef]
    import phase7b7j_second_assembled_feedback as phase7b7j  # type: ignore[no-redef]
    import phase7b8c_secant_feedback as phase7b8c  # type: ignore[no-redef]
    import phase7b8e_backtracked_radiation_map as phase7b8e  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "b607c40741ef02d09ea4fc7bc3d217137c2e3fb18c6e43adbfea1d49c849ffd2"
)


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
        raise RuntimeError(f"frozen Phase 7B8f protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            if _sha256(ROOT / source["path"]) != source["sha256"]:
                raise RuntimeError(f"frozen Phase 7B8f source changed: {source['path']}")
    return protocol


def _configure_reused_worker() -> None:
    # 中文：正式源项仍复用已验证的一块一进程实现，只替换协议、物质态与映射态。
    phase7b8c._load_protocol = _load_protocol
    phase7b8c.phase7b8b._shape = phase7b8e._shape
    phase7b8c.phase7b8b._accelerated_full_material = phase7b8e._full_material


def _plot(
    path: Path,
    mass_centre: np.ndarray,
    parent: dict[str, np.ndarray],
    previous_relative: np.ndarray,
    current_relative: np.ndarray,
    diagnostics: dict[str, float],
    maximum_rss: float,
    wall_runtime: float,
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    for name, label, style in (
        ("atomic_rate_heating_erg_s_cm3", "Atomic-rate heating", "-"),
        ("source_direct_heating_erg_s_cm3", "Direct comoving source", "--"),
        ("source_formal_heating_erg_s_cm3", "Inverse lab four-force", ":"),
    ):
        axes[0, 0].plot(mass_centre, parent[name][:128], ls=style, label=label)
    scale = max(
        float(np.max(np.abs(parent[name][:128])))
        for name in (
            "atomic_rate_heating_erg_s_cm3",
            "source_direct_heating_erg_s_cm3",
            "source_formal_heating_erg_s_cm3",
        )
    )
    axes[0, 0].set_yscale("symlog", linthresh=max(scale * 1.0e-2, np.finfo(float).tiny))
    axes[0, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Material heating (erg s$^{-1}$ cm$^{-3}$)",
        title="(a) Backtracked assembled source identity",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].semilogy(mass_centre, previous_relative, label="Second Picard iterate")
    axes[0, 1].semilogy(mass_centre, current_relative, ls="--", label="Backtracked trial")
    axes[0, 1].axhline(1.0e-3, color="0.25", ls=":", label="Fixed-point target")
    axes[0, 1].set(
        xlabel="Mass fraction from surface",
        ylabel="Cellwise fixed-time-level residual",
        title="(b) True residual after backtracked validation",
    )
    axes[0, 1].legend(frameon=False)
    photo = parent["photoionization_s1"][:128]
    for index, label in enumerate(("H I", "He I", "He II")):
        axes[1, 0].semilogy(mass_centre, photo[:, index], label=label)
    axes[1, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Photoionization rate (s$^{-1}$)",
        title="(c) Backtracked-trial H/He rates",
    )
    axes[1, 0].legend(frameon=False)
    axes[1, 1].axis("off")
    axes[1, 1].text(
        0.04,
        0.94,
        "(d) Triple residual gate\n\n"
        f"Rate/direct volume L1 = {diagnostics['rate_direct_l1']:.3e}\n"
        f"Rate/four-force volume L1 = {diagnostics['frame_volume_l1']:.3e}\n"
        f"Rate/four-force column total = {diagnostics['frame_global']:.3e}\n"
        f"Weighted contraction = {diagnostics['weighted_contraction']:.6f}\n"
        f"Previous limiting-cell contraction = {diagnostics['limiting_contraction']:.6f}\n"
        f"Maximum-cell contraction = {diagnostics['maximum_contraction']:.6f}\n"
        f"Current weighted residual = {diagnostics['current_weighted']:.3e}\n"
        f"Current maximum residual = {diagnostics['current_maximum']:.3e}\n"
        f"Maximum process RSS = {maximum_rss:.1f} MiB\n"
        f"Total wall time = {wall_runtime:.1f} s",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=9.8,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    block_count = int(configuration["block_count"])
    partial_paths = [OUTPUT / f"phase7b8f_block{index:02d}_partial.npz" for index in range(block_count)]
    report_paths = [OUTPUT / f"phase7b8f_block{index:02d}.json" for index in range(block_count)]
    started = time.perf_counter()
    concurrency = int(configuration["maximum_concurrent_processes"])
    for offset in range(0, block_count, concurrency):
        batch = range(offset, min(offset + concurrency, block_count))
        processes = [
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
            for block_index in batch
        ]
        return_codes = [process.wait() for process in processes]
        if any(code != 0 for code in return_codes):
            raise RuntimeError(f"Phase 7B8f worker batch failed: {return_codes}")
        completed = offset + len(return_codes)
        if completed % 10 == 0 or completed == block_count:
            print(json.dumps({"completed_blocks": completed, "total_blocks": block_count}), flush=True)
    wall_runtime = time.perf_counter() - started
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    reports.sort(key=lambda row: int(row["block_index"]))
    shape = phase7b8e._shape(protocol)
    combined = phase7b7j._zero(shape[2])
    ownership = np.zeros(shape[0], dtype=np.int64)
    for report in reports:
        block_index = int(report["block_index"])
        partial_path = partial_paths[block_index]
        if _sha256(partial_path) != report["partial_sha256"]:
            raise RuntimeError("Phase 7B8f partial hash changed")
        ownership[int(report["core_group_start"]):int(report["core_group_stop"])] += 1
        with np.load(partial_path) as partial:
            for name in combined:
                combined[name] += np.asarray(partial[name])
    context = phase7b7f.phase7b7e.phase7b5x._context(protocol)
    following = int(context["following"])
    subedge = phase7b7f.phase7b7e.phase7b5x._subdivide_column_edge(
        context["full"]["edge_cm"][following], 16
    )
    subwidth = np.diff(subedge)
    rate = combined["atomic_rate_heating_erg_s_cm3"]
    direct = combined["source_direct_heating_erg_s_cm3"]
    formal = combined["source_formal_heating_erg_s_cm3"]
    rate_direct_l1, _, _, _ = phase7b7f._source_metrics(rate, direct, subwidth)
    frame_volume_l1, frame_global, integrated_rate, integrated_formal = phase7b7f._source_metrics(
        rate, formal, subwidth
    )
    parent = {
        name: np.mean(array.reshape(256, 16, *array.shape[1:]), axis=1)
        for name, array in combined.items()
    }
    mirror = {name: phase7b7j._mirror_residual(array) for name, array in parent.items()}
    maximum_mirror = max(mirror.values())
    with np.load(ROOT / protocol["sources"]["physical_old_time_level"]["path"]) as old:
        with np.load(ROOT / protocol["sources"]["previous_material_iterate"]["path"]) as previous:
            phase = int(previous["phase_index"])
            duration = float(previous["step_duration_s"])
            density = np.array(previous["density_g_cm3"], copy=True)
            old_energy = ground_state_material_specific_energy_erg_g(
                old["temperature_k"][phase],
                old["hydrogen_fraction"][phase],
                old["helium_fraction"][phase],
            )
            previous_energy = ground_state_material_specific_energy_erg_g(
                previous["temperature_k"],
                previous["hydrogen_fraction"],
                previous["helium_fraction"],
            )
            cell_mass = np.array(old["cell_mass_g_cm2"], copy=True)
            mass_edge = np.array(old["mass_fraction_edges"], copy=True)
    with np.load(ROOT / protocol["sources"]["accelerated_material_trial"]["path"]) as current:
        if (
            int(current["phase_index"]) != phase
            or float(current["step_duration_s"]) != duration
            or not np.array_equal(current["density_g_cm3"], density)
        ):
            raise RuntimeError("Phase 7B8f fixed physical time base changed")
        current_energy = ground_state_material_specific_energy_erg_g(
            current["temperature_k"], current["hydrogen_fraction"], current["helium_fraction"]
        )
    with np.load(ROOT / protocol["sources"]["previous_assembled_feedback"]["path"]) as previous_rates:
        previous_heating = np.array(
            previous_rates["half_atomic_rate_heating_erg_s_cm3"], copy=True
        )
    current_heating = parent["atomic_rate_heating_erg_s_cm3"][:128]
    previous_relative, previous_weighted, previous_maximum = phase7b7j._fixed_point_residual(
        np.asarray(old_energy), np.asarray(previous_energy), duration, previous_heating, density, cell_mass
    )
    current_relative, current_weighted, current_maximum = phase7b7j._fixed_point_residual(
        np.asarray(old_energy), np.asarray(current_energy), duration, current_heating, density, cell_mass
    )
    weighted_contraction = current_weighted / previous_weighted
    previous_limiting_cell = int(np.argmax(previous_relative))
    limiting_contraction = (
        float(current_relative[previous_limiting_cell])
        / float(previous_relative[previous_limiting_cell])
    )
    maximum_contraction = current_maximum / previous_maximum
    all_finite = all(np.all(np.isfinite(array)) for array in combined.values())
    atomic_names = (
        "photoionization_s1",
        "spontaneous_recombination_cm3_s",
        "stimulated_recombination_cm3_s",
        "total_recombination_cm3_s",
    )
    all_atomic_nonnegative = all(np.all(combined[name] >= 0.0) for name in atomic_names)
    minimum_mean = min(float(row["minimum_owned_comoving_mean_intensity"]) for row in reports)
    rss = [float(row["peak_process_rss_mib"]) for row in reports]
    gates = protocol["gates"]
    measurement = {
        "frozen_protocol_sources_and_state_passed": True,
        "block_and_frequency_ownership_passed": bool(
            len(reports) == gates["block_count_exactly"]
            and int(np.sum(ownership)) == gates["owned_frequency_group_count_exactly"]
            and np.all(ownership == 1)
        ),
        "assembled_rates_and_arrays_valid": bool(
            minimum_mean >= gates["minimum_comoving_mean_intensity_at_least"]
            and all_finite
            and all_atomic_nonnegative
        ),
        "formal_source_consistency_passed": bool(
            rate_direct_l1 < gates["atomic_rate_vs_direct_comoving_heating_volume_l1_below"]
            and frame_volume_l1 < gates["atomic_rate_vs_inverse_four_force_volume_l1_below"]
            and frame_global < gates["atomic_rate_vs_inverse_four_force_global_fraction_below"]
        ),
        "parent_mirror_symmetry_passed": bool(
            maximum_mirror < gates["maximum_parent_mirror_residual_below"]
        ),
        "resource_and_runtime_gates_passed": bool(
            all(value < gates["each_process_peak_rss_strictly_below_mib"] for value in rss)
            and wall_runtime < gates["total_wall_time_strictly_below_s"]
        ),
    }
    true_residual_passed = bool(
        weighted_contraction < gates["mass_weighted_true_residual_contraction_below"]
        and limiting_contraction < gates["previous_limiting_cell_true_residual_contraction_below"]
        and maximum_contraction < gates["maximum_cell_true_residual_contraction_below"]
    )
    acceptance = protocol["fixed_point_acceptance"]
    fixed_point = bool(
        current_weighted < acceptance["mass_weighted_relative_residual_below"]
        and current_maximum < acceptance["maximum_cell_relative_residual_below"]
    )
    decision = {
        **measurement,
        "backtracked_triple_true_residual_gate_passed": true_residual_passed,
        "accepted_as_coupled_fixed_point": fixed_point,
        "material_update_performed": False,
        "radiation_update_performed": False,
        "another_material_update_authorized": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b8f_measurement_gate_passed"] = all(measurement.values())
    decision["feedback_informed_backtracking_accepted"] = bool(
        decision["phase7b8f_measurement_gate_passed"] and true_residual_passed
    )
    decision["bounded_continuation_design_authorized"] = bool(
        decision["feedback_informed_backtracking_accepted"]
    )
    coefficient_path = OUTPUT / "phase7b8f_backtracked_assembled_feedback.npz"
    _write_npz_atomic(
        coefficient_path,
        **{name: np.asarray(value) for name, value in combined.items()},
        **{f"parent_{name}": np.asarray(value) for name, value in parent.items()},
        **{f"half_{name}": np.asarray(value[:128]) for name, value in parent.items()},
        previous_fixed_point_relative_residual=previous_relative,
        backtracked_fixed_point_relative_residual=current_relative,
    )
    diagnostics = {
        "rate_direct_l1": rate_direct_l1,
        "frame_volume_l1": frame_volume_l1,
        "frame_global": frame_global,
        "weighted_contraction": weighted_contraction,
        "limiting_contraction": limiting_contraction,
        "maximum_contraction": maximum_contraction,
        "current_weighted": current_weighted,
        "current_maximum": current_maximum,
    }
    figure_path = OUTPUT / "phase7b8f_backtracked_feedback.png"
    _plot(
        figure_path,
        0.5 * (mass_edge[:-1] + mass_edge[1:]),
        parent,
        previous_relative,
        current_relative,
        diagnostics,
        max(rss),
        wall_runtime,
    )
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "block_count": len(reports),
        "owned_frequency_group_count": int(np.sum(ownership)),
        "minimum_owned_comoving_mean_intensity": minimum_mean,
        "atomic_rate_vs_direct_comoving_heating_volume_l1": rate_direct_l1,
        "atomic_rate_vs_inverse_four_force_volume_l1": frame_volume_l1,
        "atomic_rate_vs_inverse_four_force_global_fraction": frame_global,
        "integrated_atomic_rate_heating_erg_s_cm2": integrated_rate,
        "integrated_inverse_four_force_heating_erg_s_cm2": integrated_formal,
        "maximum_parent_mirror_residual": maximum_mirror,
        "parent_mirror_residuals": mirror,
        "previous_mass_weighted_fixed_point_residual": previous_weighted,
        "backtracked_mass_weighted_fixed_point_residual": current_weighted,
        "backtracked_maximum_cell_fixed_point_residual": current_maximum,
        "mass_weighted_true_residual_contraction_fraction": weighted_contraction,
        "previous_limiting_cell": previous_limiting_cell,
        "previous_limiting_cell_true_residual_contraction_fraction": limiting_contraction,
        "maximum_cell_true_residual_contraction_fraction": maximum_contraction,
        "maximum_process_peak_rss_mib": max(rss),
        "total_wall_runtime_s": wall_runtime,
        "coefficient_path": str(coefficient_path.relative_to(ROOT)),
        "coefficient_sha256": _sha256(coefficient_path),
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(OUTPUT / "phase7b8f_backtracked_feedback_summary.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b8f_preregistered_backtracked_feedback.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--partial", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.block_index is None or args.partial is None or args.worker_report is None:
            raise ValueError("Phase 7B8f worker arguments are incomplete")
        _configure_reused_worker()
        phase7b8c.run_worker(
            args.protocol, args.block_index, args.partial, args.worker_report
        )
        return
    print(json.dumps(run(args.protocol), indent=2))


if __name__ == "__main__":
    main()
