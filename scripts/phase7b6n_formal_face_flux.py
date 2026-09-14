"""Phase 7B6n：比较冻结 I13/I14 各一次形式映射后的 ALE 面通量。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S, PLANCK_ERG_S
from eccentric_tde_observer.mixed_frame_ale import solve_mixed_frame_ale_group_step

try:
    from scripts import phase7b5x_full_depth_block_probe as phase7b5x
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
    from scripts.phase7b6b_relaxed_fixed_point import _write_json_atomic
    from scripts.phase7b6f_full_frequency_contraction import _local_fields
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b5x_full_depth_block_probe as phase7b5x  # type: ignore[no-redef]
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )
    from phase7b6b_relaxed_fixed_point import (  # type: ignore[no-redef]
        _write_json_atomic,
    )
    from phase7b6f_full_frequency_contraction import (  # type: ignore[no-redef]
        _local_fields,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "30bc0d4b95c35942d6706d59c312dcd9a68006171626cd5f59c10762b123c1e7"
)
MIB = 1024**2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B6n protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6n source changed: {source['path']}")
    return protocol


def _shape(protocol: dict[str, object]) -> tuple[int, int, int]:
    configuration = protocol["configuration"]
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _run_worker_loaded(
    protocol: dict[str, object],
    state_label: str,
    worker_index: int,
    report_path: Path,
) -> None:
    configuration = protocol["configuration"]
    if state_label not in configuration["states"]:
        raise ValueError("state label left the frozen Phase 7B6n pair")
    process_count = int(configuration["process_count"])
    if worker_index < 0 or worker_index >= process_count:
        raise ValueError("worker index left the frozen process assignment")
    context = phase7b5x._context(protocol)
    if int(context["phase"]) != int(configuration["phase_index"]):
        raise RuntimeError("Phase 7B6n selected phase changed")
    shape = _shape(protocol)
    retained = protocol["retained_arrays"]
    if "iteration14_state_path" in retained:
        later_state_path = retained["iteration14_state_path"]
        earlier_residual_path = retained["iteration13_residual_path"]
        omega = float(retained["omega14"])
    elif "iteration30_state_path" in retained:
        later_state_path = retained["iteration30_state_path"]
        earlier_residual_path = retained["iteration29_residual_path"]
        omega = float(retained["omega30"])
    else:
        raise KeyError("formal-flux protocol lacks a recognized retained state pair")
    earlier_label = configuration["states"][0]
    later_global = np.memmap(
        ROOT / later_state_path,
        mode="r",
        dtype=np.float64,
        shape=shape,
    )
    residual_global = np.memmap(
        ROOT / earlier_residual_path,
        mode="r",
        dtype=np.float64,
        shape=shape,
    )
    full_active_start = context["stencil"].active_outer_group_start
    full_active_stop = context["stencil"].active_outer_group_stop
    assigned = [
        (index, block)
        for index, block in enumerate(context["blocks"])
        if index % process_count == worker_index
    ]
    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    rows = []
    for local_index, (block_index, block) in enumerate(assigned, start=1):
        block_started = time.perf_counter()
        fields = _local_fields(context, block)
        core = slice(block.core_group_start, block.core_group_stop)
        physical_start = max(block.outer_group_start, full_active_start)
        physical_stop = min(block.outer_group_stop, full_active_stop)
        if physical_stop > physical_start:
            source_slice = slice(
                physical_start - full_active_start,
                physical_stop - full_active_start,
            )
            halo = np.array(later_global[source_slice], copy=True)
            if state_label == earlier_label:
                halo -= omega * residual_global[source_slice]
            if not np.all(np.isfinite(halo)) or float(np.min(halo)) < 0.0:
                raise ArithmeticError("reconstructed Phase 7B6n halo is invalid")
            fields["outer"][
                physical_start - block.outer_group_start : physical_stop
                - block.outer_group_start
            ] = halo
        current_core = np.array(later_global[core], copy=True)
        if state_label == earlier_label:
            current_core -= omega * residual_global[core]
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
        mapped = result.final_lab_intensity_density
        difference = mapped - current_core
        scale = max(float(np.max(np.abs(mapped))), float(np.max(np.abs(current_core))))
        formal_flux = (
            result.right_ale_energy_flux_group_cgs
            - result.left_ale_energy_flux_group_cgs
        )
        diagnostics = np.asarray(
            [
                result.global_scale_normalized_coupled_residual,
                result.total_relative_energy_ledger_residual,
                result.maximum_group_relative_coupled_residual,
                *formal_flux,
            ]
        )
        rows.append(
            {
                "state_label": state_label,
                "worker_index": worker_index,
                "block_index": block_index,
                "core_group_start": block.core_group_start,
                "core_group_stop": block.core_group_stop,
                "formal_two_sided_face_flux_cgs": formal_flux.tolist(),
                "maximum_absolute_change": float(np.max(np.abs(difference))),
                "maximum_scale": scale,
                "mapped_minimum_intensity": float(np.min(mapped)),
                "global_coupled_residual": result.global_scale_normalized_coupled_residual,
                "total_energy_ledger_residual": result.total_relative_energy_ledger_residual,
                "diagnostics_finite": bool(np.all(np.isfinite(diagnostics))),
                "block_runtime_s": time.perf_counter() - block_started,
            }
        )
        del result, mapped, difference, current_core, fields
        if local_index == 1 or local_index % 10 == 0 or local_index == len(assigned):
            print(
                json.dumps(
                    {
                        "state": state_label,
                        "worker": worker_index + 1,
                        "completed": local_index,
                        "assigned": len(assigned),
                    }
                ),
                flush=True,
            )
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    _write_json_atomic(
        report_path,
        {
            "state_label": state_label,
            "worker_index": worker_index,
            "assigned_block_count": len(assigned),
            "runtime_s": time.perf_counter() - started,
            "baseline_highwater_rss_mib": baseline_rss / MIB,
            "peak_process_rss_mib": peak_rss / MIB,
            "rows": rows,
        },
    )


def run_worker(
    protocol_path: Path,
    state_label: str,
    worker_index: int,
    report_path: Path,
) -> None:
    _run_worker_loaded(
        _load_protocol(protocol_path),
        state_label,
        worker_index,
        report_path,
    )


def _run_state(
    protocol_path: Path, protocol: dict[str, object], state_label: str
) -> dict[str, object]:
    process_count = int(protocol["configuration"]["process_count"])
    report_paths = [
        OUTPUT / f"phase7b6n_{state_label}_worker{index + 1}.json"
        for index in range(process_count)
    ]
    processes = []
    started = time.perf_counter()
    for worker_index, report_path in enumerate(report_paths):
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker",
                    "--protocol",
                    str(protocol_path),
                    "--state-label",
                    state_label,
                    "--worker-index",
                    str(worker_index),
                    "--worker-report",
                    str(report_path),
                ],
                cwd=ROOT,
            )
        )
    return_codes = [process.wait() for process in processes]
    if any(code != 0 for code in return_codes):
        raise RuntimeError(f"Phase 7B6n {state_label} workers failed: {return_codes}")
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    rows = sorted(
        [row for report in reports for row in report["rows"]],
        key=lambda row: row["core_group_start"],
    )
    shape = _shape(protocol)
    coverage = bool(
        len(rows) == int(protocol["configuration"]["block_count"])
        and rows[0]["core_group_start"] == 0
        and rows[-1]["core_group_stop"] == shape[0]
        and all(
            first["core_group_stop"] == second["core_group_start"]
            for first, second in zip(rows[:-1], rows[1:], strict=True)
        )
    )
    flux = np.concatenate(
        [np.asarray(row["formal_two_sided_face_flux_cgs"]) for row in rows]
    )
    if flux.shape != (shape[0],):
        raise ArithmeticError("Phase 7B6n formal flux coverage is incomplete")
    maximum_absolute = max(row["maximum_absolute_change"] for row in rows)
    maximum_scale = max(row["maximum_scale"] for row in rows)
    return {
        "state_label": state_label,
        "block_count": len(rows),
        "unique_full_group_coverage": coverage,
        "formal_flux": flux,
        "raw_fixed_point_residual": (
            maximum_absolute / maximum_scale
            if maximum_scale > 0.0
            else maximum_absolute
        ),
        "minimum_mapped_intensity": min(row["mapped_minimum_intensity"] for row in rows),
        "maximum_block_coupled_residual": max(row["global_coupled_residual"] for row in rows),
        "maximum_block_energy_ledger_residual": max(
            row["total_energy_ledger_residual"] for row in rows
        ),
        "all_diagnostics_finite": all(row["diagnostics_finite"] for row in rows),
        "wall_runtime_s": time.perf_counter() - started,
        "maximum_worker_peak_rss_mib": max(
            report["peak_process_rss_mib"] for report in reports
        ),
        "worker_reports": reports,
    }


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    states = [
        _run_state(protocol_path, protocol, state_label)
        for state_label in protocol["configuration"]["states"]
    ]
    earlier, later = states
    with np.load(
        ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]
    ) as master:
        frequency_edge = np.array(master["active_edge_hz"], copy=True)
    width = np.diff(frequency_edge)
    first_flux = earlier.pop("formal_flux")
    second_flux = later.pop("formal_flux")
    spectrum_l1 = float(
        np.sum(width * np.abs(second_flux - first_flux))
        / max(np.sum(width * np.abs(first_flux)), np.sum(width * np.abs(second_flux)))
    )
    first_bolometric = float(np.sum(width * first_flux))
    second_bolometric = float(np.sum(width * second_flux))
    bolometric_fraction = abs(second_bolometric - first_bolometric) / max(
        abs(first_bolometric), abs(second_bolometric)
    )
    gates = protocol["gates"]
    decision = {
        "frozen_protocol_hash_passed": True,
        "source_hashes_and_upstream_array_hashes_passed": True,
        "map_count_and_group_coverage_passed": all(
            state["block_count"] == gates["each_state_block_count_exactly"]
            and state["unique_full_group_coverage"]
            for state in states
        ),
        "mapped_states_and_diagnostics_valid": all(
            state["minimum_mapped_intensity"] >= 0.0
            and state["all_diagnostics_finite"]
            for state in states
        ),
        "formal_face_flux_spectrum_gate_passed": spectrum_l1
        < gates["formal_face_flux_spectrum_l1_below"],
        "formal_face_bolometric_gate_passed": bolometric_fraction
        < gates["formal_face_bolometric_flux_fraction_below"],
        "resource_and_runtime_gates_passed": all(
            state["maximum_worker_peak_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and state["wall_runtime_s"] < gates["each_state_wall_time_strictly_below_s"]
            for state in states
        ),
        "algebraic_fixed_point_at_1e10": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b6n_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "source_hashes_and_upstream_array_hashes_passed",
            "map_count_and_group_coverage_passed",
            "mapped_states_and_diagnostics_valid",
            "formal_face_flux_spectrum_gate_passed",
            "formal_face_bolometric_gate_passed",
            "resource_and_runtime_gates_passed",
        )
    )
    decision["fixed_material_science_functional_convergence"] = bool(
        decision["phase7b6n_gate_passed"]
    )
    decision["single_bounded_matter_feedback_pilot_authorized"] = bool(
        decision["phase7b6n_gate_passed"]
    )
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "states": states,
        "formal_face_flux_spectrum_l1": spectrum_l1,
        "formal_face_bolometric_iteration13": first_bolometric,
        "formal_face_bolometric_iteration14": second_bolometric,
        "formal_face_bolometric_fraction": bolometric_fraction,
        "decision": decision,
        "figures": ["phase7b6n_formal_face_flux.png"],
    }
    _write_json_atomic(OUTPUT / "phase7b6n_formal_face_flux_summary.json", report)
    _plot(
        OUTPUT / "phase7b6n_formal_face_flux.png",
        frequency_edge,
        first_flux,
        second_flux,
        states,
        spectrum_l1,
        bolometric_fraction,
    )
    return report


def _plot(
    path: Path,
    frequency_edge: np.ndarray,
    first_flux: np.ndarray,
    second_flux: np.ndarray,
    states: list[dict[str, object]],
    spectrum_l1: float,
    bolometric_fraction: float,
) -> None:
    centre = np.sqrt(frequency_edge[:-1] * frequency_edge[1:])
    energy_ev = PLANCK_ERG_S * centre / EV_ERG
    scale = max(float(np.max(np.abs(first_flux))), float(np.max(np.abs(second_flux))))
    plotted_first = centre * first_flux
    plotted_second = centre * second_flux
    plotted_scale = max(
        float(np.max(np.abs(plotted_first))),
        float(np.max(np.abs(plotted_second))),
    )
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].semilogx(energy_ev, plotted_first, label="Map from iteration 13")
    axes[0, 0].semilogx(
        energy_ev, plotted_second, ls="--", label="Map from iteration 14"
    )
    # 高频负尾远低于主谱；线性过渡按实际绘制的 nu F_nu 标度设置，避免刻度重叠。
    linear_threshold = max(plotted_scale * 1.0e-14, 1.0e-300)
    axes[0, 0].set_yscale("symlog", linthresh=linear_threshold)
    axes[0, 0].set_ylim(bottom=-linear_threshold, top=1.5 * plotted_scale)
    axes[0, 0].set(
        xlabel="Photon energy (eV)",
        ylabel="nu F_nu (formal ALE faces)",
        title="(a) Two-sided formal face flux",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].semilogx(
        energy_ev,
        np.abs(second_flux - first_flux) / scale,
        color="#e45756",
    )
    axes[0, 1].set_yscale("log")
    axes[0, 1].set(
        xlabel="Photon energy (eV)",
        ylabel="Absolute change / global scale",
        title="(b) Formal flux change",
    )
    axes[1, 0].bar(
        ["Spectrum L1", "Bolometric"],
        [spectrum_l1, bolometric_fraction],
        color=["#4c78a8", "#f58518"],
    )
    axes[1, 0].axhline(1.0e-3, color="0.25", ls="--", label="Science gate")
    axes[1, 0].set_yscale("log")
    axes[1, 0].set(ylabel="Relative change", title="(c) Preregistered face-flux gates")
    axes[1, 0].legend(frameon=False)
    axes[1, 1].bar(
        [state["state_label"] for state in states],
        [state["wall_runtime_s"] for state in states],
        color=["#777777", "#72b7b2"],
    )
    axes[1, 1].set(ylabel="Wall runtime (s)", title="(d) Formal diagnostic cost")
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6n_preregistered_formal_face_flux.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--state-label")
    parser.add_argument("--worker-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if (
            args.state_label is None
            or args.worker_index is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires state, index, and report")
        run_worker(
            args.protocol,
            args.state_label,
            args.worker_index,
            args.worker_report,
        )
        return
    report = run(args.protocol)
    print(json.dumps(report["decision"], indent=2))


if __name__ == "__main__":
    main()
