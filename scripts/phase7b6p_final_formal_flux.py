"""Phase 7B6p：对 I29/I30 执行最终正式 ALE 面通量双映射审计。"""

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

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.radiation import PLANCK_ERG_S

try:
    from scripts.phase7b6n_formal_face_flux import (
        _run_worker_loaded,
        _shape,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b6n_formal_face_flux import (  # type: ignore[no-redef]
        _run_worker_loaded,
        _shape,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "55034de58041f73e0dc971c1ea954a3598987c3cde133913a7657bad060d8fe5"
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


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B6p protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6p source changed: {source['path']}")
    return protocol


def run_worker(
    protocol_path: Path,
    state_label: str,
    worker_index: int,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path)
    _run_worker_loaded(protocol, state_label, worker_index, report_path)


def _run_state(
    protocol_path: Path,
    protocol: dict[str, object],
    state_label: str,
) -> dict[str, object]:
    process_count = int(protocol["configuration"]["process_count"])
    report_paths = [
        OUTPUT / f"phase7b6p_{state_label}_worker{index + 1}.json"
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
        raise RuntimeError(f"Phase 7B6p {state_label} workers failed: {return_codes}")
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
        raise ArithmeticError("Phase 7B6p formal flux coverage is incomplete")
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
        "maximum_block_coupled_residual": max(
            row["global_coupled_residual"] for row in rows
        ),
        "maximum_block_energy_ledger_residual": max(
            row["total_energy_ledger_residual"] for row in rows
        ),
        "all_diagnostics_finite": all(row["diagnostics_finite"] for row in rows),
        "wall_runtime_s": time.perf_counter() - started,
        "maximum_worker_peak_rss_mib": max(
            report["peak_process_rss_mib"] for report in reports
        ),
        "worker_report_paths": [str(path.relative_to(ROOT)) for path in report_paths],
    }


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
    linear_threshold = max(plotted_scale * 1.0e-14, 1.0e-300)
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].semilogx(energy_ev, plotted_first, label="Map from iteration 29")
    axes[0, 0].semilogx(
        energy_ev, plotted_second, ls="--", label="Map from iteration 30"
    )
    axes[0, 0].set_yscale("symlog", linthresh=linear_threshold)
    axes[0, 0].set_ylim(bottom=-linear_threshold, top=1.5 * plotted_scale)
    axes[0, 0].set(
        xlabel="Photon energy (eV)",
        ylabel="nu F_nu (formal ALE faces)",
        title="(a) Final formal face flux",
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
        title="(b) Final formal flux change",
    )
    axes[1, 0].bar(
        ["Spectrum L1", "Bolometric"],
        [spectrum_l1, bolometric_fraction],
        color=["#4c78a8", "#f58518"],
    )
    axes[1, 0].axhline(1.0e-3, color="0.25", ls="--", label="Science gate")
    axes[1, 0].set_yscale("log")
    axes[1, 0].set(ylabel="Relative change", title="(c) Final face-flux gates")
    axes[1, 0].legend(frameon=False)
    axes[1, 1].bar(
        [state["state_label"] for state in states],
        [state["wall_runtime_s"] for state in states],
        color=["#777777", "#72b7b2"],
    )
    axes[1, 1].set(ylabel="Wall runtime (s)", title="(d) Formal diagnostic cost")
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    retained = protocol["retained_arrays"]
    state_path = ROOT / retained["iteration30_state_path"]
    residual_path = ROOT / retained["iteration29_residual_path"]
    shape = _shape(protocol)
    expected_size = int(np.prod(shape, dtype=np.int64) * 8)
    if state_path.stat().st_size != expected_size or residual_path.stat().st_size != expected_size:
        raise RuntimeError("Phase 7B6p retained array size changed")
    # 正式终局门在昂贵映射前重新核对两个 10 GB 检查点。
    array_hashes_passed = bool(
        _sha256(state_path) == retained["iteration30_state_sha256"]
        and _sha256(residual_path) == retained["iteration29_residual_sha256"]
    )
    if not array_hashes_passed:
        raise RuntimeError("Phase 7B6p retained array hash changed")
    states = [
        _run_state(protocol_path, protocol, state_label)
        for state_label in protocol["configuration"]["states"]
    ]
    earlier, later = states
    with np.load(ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]) as master:
        frequency_edge = np.array(master["active_edge_hz"], copy=True)
    frequency_width = np.diff(frequency_edge)
    first_flux = earlier.pop("formal_flux")
    second_flux = later.pop("formal_flux")
    spectrum_l1 = float(
        np.sum(frequency_width * np.abs(second_flux - first_flux))
        / max(
            np.sum(frequency_width * np.abs(first_flux)),
            np.sum(frequency_width * np.abs(second_flux)),
        )
    )
    first_bolometric = float(np.sum(frequency_width * first_flux))
    second_bolometric = float(np.sum(frequency_width * second_flux))
    bolometric_fraction = abs(second_bolometric - first_bolometric) / max(
        abs(first_bolometric), abs(second_bolometric)
    )
    gates = protocol["gates"]
    decision = {
        "frozen_protocol_and_source_hashes_passed": True,
        "retained_array_hashes_and_sizes_passed": array_hashes_passed,
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
            and state["wall_runtime_s"]
            < gates["each_state_wall_time_strictly_below_s"]
            for state in states
        ),
        "algebraic_fixed_point_at_1e10": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b6p_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_and_source_hashes_passed",
            "retained_array_hashes_and_sizes_passed",
            "map_count_and_group_coverage_passed",
            "mapped_states_and_diagnostics_valid",
            "formal_face_flux_spectrum_gate_passed",
            "formal_face_bolometric_gate_passed",
            "resource_and_runtime_gates_passed",
        )
    )
    decision["fixed_material_science_functional_convergence"] = bool(
        decision["phase7b6p_gate_passed"]
    )
    decision["single_bounded_matter_feedback_pilot_authorized"] = bool(
        decision["phase7b6p_gate_passed"]
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "states": states,
        "formal_face_flux_spectrum_l1": spectrum_l1,
        "formal_face_bolometric_iteration29": first_bolometric,
        "formal_face_bolometric_iteration30": second_bolometric,
        "formal_face_bolometric_fraction": bolometric_fraction,
        "decision": decision,
        "figures": ["phase7b6p_final_formal_flux.png"],
    }
    _write_json_atomic(OUTPUT / "phase7b6p_final_formal_flux_summary.json", summary)
    _plot(
        OUTPUT / "phase7b6p_final_formal_flux.png",
        frequency_edge,
        first_flux,
        second_flux,
        states,
        spectrum_l1,
        bolometric_fraction,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6p_preregistered_final_formal_flux.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--state-label")
    parser.add_argument("--worker-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if any(
            value is None
            for value in (args.state_label, args.worker_index, args.worker_report)
        ):
            raise ValueError("worker mode requires state label, index and report")
        run_worker(args.protocol, args.state_label, args.worker_index, args.worker_report)
        return
    summary = run(args.protocol)
    print(json.dumps(summary["decision"], indent=2))


if __name__ == "__main__":
    main()
