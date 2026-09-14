"""Phase 7B6q：复验 I29 正式通量的逐位确定性与资源上界。"""

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

try:
    from scripts.phase7b6n_formal_face_flux import _run_worker_loaded, _shape
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
    "30df49fcb1a626b02d398962d90a2c2f1a8b5094b28da0716aeca1a0f37e007a"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B6q protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6q source changed: {source['path']}")
    return protocol


def _load_rows(paths: list[str]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    reports = [json.loads((ROOT / path).read_text(encoding="utf-8")) for path in paths]
    rows = sorted(
        [row for report in reports for row in report["rows"]],
        key=lambda row: row["core_group_start"],
    )
    return reports, rows


def _flux(rows: list[dict[str, object]], group_count: int) -> np.ndarray:
    result = np.concatenate(
        [np.asarray(row["formal_two_sided_face_flux_cgs"]) for row in rows]
    )
    if result.shape != (group_count,):
        raise ArithmeticError("Phase 7B6q formal flux coverage is incomplete")
    return result


def run_worker(
    protocol_path: Path, worker_index: int, report_path: Path
) -> None:
    protocol = _load_protocol(protocol_path)
    _run_worker_loaded(protocol, "iteration29", worker_index, report_path)


def _plot(path: Path, spectrum_l1: float, bolometric: float, rss: list[float], wall: float) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(13.0, 4.0), constrained_layout=True)
    axes[0].bar(
        ["Spectrum L1", "Bolometric"],
        [spectrum_l1, bolometric],
        color=["#4c78a8", "#f58518"],
    )
    axes[0].axhline(1.0e-3, color="0.25", ls="--", label="Science gate")
    axes[0].set_yscale("log")
    axes[0].set(ylabel="Relative change", title="(a) Repeated formal-flux gates")
    axes[0].legend(frameon=False)
    axes[1].bar(["Worker 1", "Worker 2"], rss, color=["#72b7b2", "#54a24b"])
    axes[1].axhline(6144.0, color="0.25", ls="--", label="Process gate")
    axes[1].set(ylabel="Peak RSS (MiB)", title="(b) Repeated resource gate")
    axes[1].legend(frameon=False)
    axes[2].bar(["I29 repeat"], [wall], color="#b279a2")
    axes[2].axhline(900.0, color="0.25", ls="--", label="Wall-time gate")
    axes[2].set(ylabel="Wall runtime (s)", title="(c) Repeat cost")
    axes[2].legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    shape = _shape(protocol)
    process_count = int(configuration["process_count"])
    report_paths = [
        OUTPUT / f"phase7b6q_iteration29_worker{index + 1}.json"
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
        raise RuntimeError(f"Phase 7B6q workers failed: {return_codes}")
    wall_runtime = time.perf_counter() - started
    repeat_reports, repeat_rows = _load_rows(
        [str(path.relative_to(ROOT)) for path in report_paths]
    )
    _, original_rows = _load_rows(
        configuration["retained_iteration29_formal_reports"]
    )
    retained_reports, retained_rows = _load_rows(
        configuration["retained_iteration30_formal_reports"]
    )
    block_count = int(configuration["block_count"])
    coverage = bool(
        len(repeat_rows) == block_count
        and repeat_rows[0]["core_group_start"] == 0
        and repeat_rows[-1]["core_group_stop"] == shape[0]
        and all(
            first["core_group_stop"] == second["core_group_start"]
            for first, second in zip(repeat_rows[:-1], repeat_rows[1:], strict=True)
        )
    )
    repeat_flux = _flux(repeat_rows, shape[0])
    original_flux = _flux(original_rows, shape[0])
    retained_flux = _flux(retained_rows, shape[0])
    maximum_reproduction_difference = float(np.max(np.abs(repeat_flux - original_flux)))
    with np.load(ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]) as master:
        width = np.diff(np.array(master["active_edge_hz"], copy=True))
    spectrum_l1 = float(
        np.sum(width * np.abs(retained_flux - repeat_flux))
        / max(np.sum(width * np.abs(repeat_flux)), np.sum(width * np.abs(retained_flux)))
    )
    repeat_bolometric = float(np.sum(width * repeat_flux))
    retained_bolometric = float(np.sum(width * retained_flux))
    bolometric_fraction = abs(retained_bolometric - repeat_bolometric) / max(
        abs(repeat_bolometric), abs(retained_bolometric)
    )
    gates = protocol["gates"]
    rss = [float(report["peak_process_rss_mib"]) for report in repeat_reports]
    retained_resource_passed = all(
        float(report["peak_process_rss_mib"])
        < gates["each_repeat_process_peak_rss_strictly_below_mib"]
        for report in retained_reports
    )
    decision = {
        "frozen_protocol_and_source_hashes_passed": True,
        "repeat_map_count_and_group_coverage_passed": bool(
            coverage and len(repeat_rows) == gates["repeat_state_block_count_exactly"]
        ),
        "formal_flux_bitwise_reproduction_passed": maximum_reproduction_difference
        == gates["repeat_formal_flux_maximum_absolute_difference_exactly"],
        "formal_face_flux_spectrum_gate_passed": spectrum_l1
        < gates["formal_face_flux_spectrum_l1_below"],
        "formal_face_bolometric_gate_passed": bolometric_fraction
        < gates["formal_face_bolometric_flux_fraction_below"],
        "repeat_resource_and_runtime_gates_passed": bool(
            all(
                value < gates["each_repeat_process_peak_rss_strictly_below_mib"]
                for value in rss
            )
            and wall_runtime < gates["repeat_state_wall_time_strictly_below_s"]
            and retained_resource_passed
        ),
        "algebraic_fixed_point_at_1e10": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b6q_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_and_source_hashes_passed",
            "repeat_map_count_and_group_coverage_passed",
            "formal_flux_bitwise_reproduction_passed",
            "formal_face_flux_spectrum_gate_passed",
            "formal_face_bolometric_gate_passed",
            "repeat_resource_and_runtime_gates_passed",
        )
    )
    decision["fixed_material_science_functional_convergence"] = bool(
        decision["phase7b6q_gate_passed"]
    )
    decision["single_bounded_matter_feedback_pilot_authorized"] = bool(
        decision["phase7b6q_gate_passed"]
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "repeat_worker_reports": [str(path.relative_to(ROOT)) for path in report_paths],
        "maximum_formal_flux_reproduction_difference": maximum_reproduction_difference,
        "formal_face_flux_spectrum_l1": spectrum_l1,
        "formal_face_bolometric_fraction": bolometric_fraction,
        "repeat_wall_runtime_s": wall_runtime,
        "repeat_worker_peak_rss_mib": rss,
        "retained_iteration30_resource_passed": retained_resource_passed,
        "decision": decision,
        "figures": ["phase7b6q_resource_recheck.png"],
    }
    _write_json_atomic(OUTPUT / "phase7b6q_resource_recheck_summary.json", summary)
    _plot(
        OUTPUT / "phase7b6q_resource_recheck.png",
        spectrum_l1,
        bolometric_fraction,
        rss,
        wall_runtime,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6q_preregistered_resource_recheck.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--worker-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.worker_index is None or args.worker_report is None:
            raise ValueError("worker mode requires index and report")
        run_worker(args.protocol, args.worker_index, args.worker_report)
        return
    summary = run(args.protocol)
    print(json.dumps(summary["decision"], indent=2))


if __name__ == "__main__":
    main()
