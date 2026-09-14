"""Phase 7B9ag：执行当前全局态的五块 Krylov 小样。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from scripts import phase7b9r_full_source_krylov_line_search as prior
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9r_full_source_krylov_line_search as prior  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "e493f91e90642f322f72eb526fd8a76012abd7f26a0a66778eb366b82c858a9d"
)
base = prior.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9ag protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9ag source changed: {source['path']}"
                )
    return protocol


def _run_worker(protocol_path: Path, block_index: int, report_path: Path) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    prior._run_worker(
        protocol_path,
        block_index,
        report_path,
        protocol_override=protocol,
    )
    row = json.loads(report_path.read_text(encoding="utf-8"))
    row["protocol_sha256"] = EXPECTED_PROTOCOL_SHA256
    _write_json_atomic(report_path, row)


def _plot(
    path: Path,
    reports: list[dict[str, object]],
    gates: dict[str, object],
    passed: bool,
) -> None:
    block = np.asarray([row["block_index"] for row in reports])
    residual = np.asarray(
        [row["fresh_line_candidate_to_raw_residual_ratio"] for row in reports]
    )
    boundary = np.asarray(
        [row["fresh_line_candidate_to_raw_boundary_ratio"] for row in reports]
    )
    figure, axes = plt.subplots(1, 2, figsize=(10.8, 4.4), constrained_layout=True)
    width = 0.34
    axes[0].bar(block - width / 2, residual, width, label="Interior residual")
    axes[0].bar(block + width / 2, boundary, width, label="Boundary spectrum")
    axes[0].axhline(
        gates["each_fresh_line_candidate_to_raw_residual_ratio_below"],
        color="0.25",
        ls="--",
        label="Interior gate",
    )
    axes[0].set(
        xlabel="Natural frequency block",
        ylabel="Accelerated / raw residual",
        title="(a) Current-state Krylov pilot",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].axis("off")
    axes[1].text(
        0.04,
        0.95,
        "(b) Dominant-block decision\n\n"
        f"Residual ratios = {[round(value, 4) for value in residual]}\n"
        f"Boundary ratios = {[round(value, 4) for value in boundary]}\n"
        f"GMRES iterations = {[row['gmres_iteration_count'] for row in reports]}\n\n"
        f"Dominant-block candidate authorized: {passed}",
        transform=axes[1].transAxes,
        va="top",
        fontsize=10.5,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    report_prefix = str(configuration.get("report_prefix", "phase7b9ag"))
    runner_path = ROOT / configuration.get(
        "runner_path", "scripts/phase7b9ag_current_state_krylov_pilot.py"
    )
    figure_path = ROOT / configuration.get(
        "figure_path", "outputs/phase7b9ag_current_state_krylov_pilot.png"
    )
    summary_path = ROOT / configuration.get(
        "summary_path", "outputs/phase7b9ag_current_state_krylov_pilot_summary.json"
    )
    indices = [
        int(row["block_index"]) for row in configuration["selected_blocks"]
    ]
    reports = []
    for block_index in indices:
        report_path = OUTPUT / f"{report_prefix}_block{block_index:02d}_krylov.json"
        process = subprocess.run(
            [
                sys.executable,
                str(runner_path),
                "--worker",
                "--protocol",
                str(protocol_path),
                "--block-index",
                str(block_index),
                "--worker-report",
                str(report_path),
            ],
            cwd=ROOT,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"Phase 7B9ag worker {block_index} failed: {process.returncode}"
            )
        row = json.loads(report_path.read_text(encoding="utf-8"))
        if row.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
            raise RuntimeError("Phase 7B9ag worker report changed")
        reports.append(row)
        print(
            json.dumps(
                {
                    "completed_blocks": len(reports),
                    "total_blocks": len(indices),
                    "latest_block": block_index,
                }
            ),
            flush=True,
        )
    gates = protocol["gates"]
    fresh = np.asarray(
        [row["fresh_line_candidate_to_raw_residual_ratio"] for row in reports]
    )
    checks = {
        "selected_block_count_pass": len(reports)
        == gates["selected_block_count_exactly"],
        "krylov_budget_pass": all(
            row["gmres_iteration_count"]
            <= gates["each_gmres_iteration_count_at_most"]
            for row in reports
        ),
        "positive_endpoint_pass": all(
            row["endpoint_exact_nonnegative_step"]
            >= gates["each_endpoint_exact_nonnegative_step_at_least"]
            for row in reports
        ),
        "useful_line_step_pass": all(
            row["line_selected_fraction"]
            >= gates["each_selected_line_fraction_at_least"]
            for row in reports
        ),
        "fresh_residual_pass": bool(
            np.all(
                fresh
                < gates["each_fresh_line_candidate_to_raw_residual_ratio_below"]
            )
        )
        and float(np.median(fresh))
        < gates["median_fresh_line_candidate_to_raw_residual_ratio_below"],
        "boundary_pass": all(
            row["fresh_line_candidate_to_raw_boundary_ratio"]
            <= gates["each_fresh_line_candidate_boundary_ratio_at_most"]
            for row in reports
        ),
        "affine_prediction_pass": all(
            row["affine_prediction_to_fresh_residual_linf"]
            < gates["each_affine_prediction_to_fresh_residual_linf_below"]
            for row in reports
        ),
        "positivity_and_resources_pass": all(
            row["minimum_line_candidate_intensity"]
            >= gates["minimum_line_candidate_intensity_at_least"]
            and row["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and row["wall_runtime_s"]
            < gates["each_worker_wall_time_strictly_below_s"]
            for row in reports
        ),
    }
    passed = all(checks.values())
    _plot(figure_path, reports, gates, passed)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "gate_checks": checks,
        "decision": {
            "current_state_krylov_pilot_passed": passed,
            "accelerated_dominant_block_candidate_authorized": passed,
            "candidate_state_written": False,
            "material_feedback_authorized": False,
        },
        "reports": reports,
        "figures": [figure_path.name],
    }
    _write_json_atomic(summary_path, summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9ag_preregistered_current_state_krylov_pilot.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.block_index is None or args.worker_report is None:
            raise ValueError("worker mode requires block and report")
        _run_worker(args.protocol, args.block_index, args.worker_report)
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
