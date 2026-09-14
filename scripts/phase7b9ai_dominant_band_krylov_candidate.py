"""Phase 7B9ai：可恢复地生成主导能段 Krylov 候选态。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

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
    "4daaf527ee9f16d12248ed5f5853e1c51a09b14adb7b60671b2368ff0c0519f3"
)
base = prior.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9ai protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9ai source changed: {source['path']}"
                )
    return protocol


def _run_worker(
    protocol_path: Path,
    block_index: int,
    output_state: Path,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    prior._run_worker(
        protocol_path,
        block_index,
        report_path,
        protocol_override=protocol,
        output_state_path=output_state,
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
    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.5), constrained_layout=True)
    axes[0].semilogy(block, residual, "o-", ms=3, label="Interior residual")
    axes[0].semilogy(block, boundary, "s-", ms=3, label="Boundary spectrum")
    axes[0].axhline(
        gates["each_fresh_line_candidate_to_raw_residual_ratio_below"],
        color="0.25",
        ls="--",
        label="Interior gate",
    )
    axes[0].set(
        xlabel="Natural frequency block",
        ylabel="Accelerated / raw residual",
        title="(a) Dominant-band Krylov candidate",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].axis("off")
    axes[1].text(
        0.04,
        0.95,
        "(b) Recoverable candidate generation\n\n"
        f"Selected blocks = {len(reports)}\n"
        f"Median residual ratio = {float(np.median(residual)):.3e}\n"
        f"Maximum boundary ratio = {float(np.max(boundary)):.3e}\n"
        f"Maximum worker RSS = "
        f"{max(float(row['peak_process_rss_mib']) for row in reports):.1f} MiB\n\n"
        f"Candidate generation passed: {passed}",
        transform=axes[1].transAxes,
        va="top",
        fontsize=10.5,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    shape = (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )
    current = ROOT / configuration["current_state_path"]
    output = ROOT / configuration["output_state_path"]
    manifest_path = ROOT / configuration["manifest_path"]
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
            raise RuntimeError("Phase 7B9ai manifest belongs to another protocol")
    else:
        if (
            output.stat().st_size
            != int(configuration["raw_float64_checkpoint_size_bytes"])
            or base._sha256(output)
            != configuration["output_state_previous_sha256"]
        ):
            raise RuntimeError("Phase 7B9ai reusable output buffer changed")
        manifest = {
            "phase": protocol["phase"],
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "status": "copying",
            "current_state_sha256": configuration["current_state_sha256"],
            "completed_blocks": [],
            "accumulated_wall_runtime_s": 0.0,
        }
        _write_json_atomic(manifest_path, manifest)
    if manifest["status"] == "copying":
        # 中文：先完整复制当前态，中断时可从源态重做，不留混合文件。
        shutil.copyfile(current, output)
        if base._sha256(output) != configuration["current_state_sha256"]:
            raise RuntimeError("Phase 7B9ai base candidate copy changed bytes")
        manifest["status"] = "running"
        _write_json_atomic(manifest_path, manifest)
    if manifest["status"] == "complete":
        return json.loads(
            (OUTPUT / "phase7b9ai_dominant_band_krylov_candidate_summary.json").read_text(
                encoding="utf-8"
            )
        )
    for row in manifest["completed_blocks"]:
        digest = base.phase7b9d._block_sha256(
            output,
            shape,
            int(row["core_group_start"]),
            int(row["core_group_stop"]),
        )
        if digest != row["output_block_sha256"]:
            raise RuntimeError(
                f"Phase 7B9ai completed block changed: {row['block_index']}"
            )
    completed = {int(row["block_index"]) for row in manifest["completed_blocks"]}
    selected = [
        int(row["block_index"]) for row in configuration["selected_blocks"]
    ]
    report_directory = ROOT / configuration["report_directory"]
    report_directory.mkdir(parents=True, exist_ok=True)
    for block_index in selected:
        if block_index in completed:
            continue
        report_path = report_directory / f"phase7b9ai_block{block_index:02d}.json"
        started = time.perf_counter()
        process = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                "--protocol",
                str(protocol_path),
                "--block-index",
                str(block_index),
                "--output-state",
                str(output),
                "--worker-report",
                str(report_path),
            ],
            cwd=ROOT,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"Phase 7B9ai worker {block_index} failed: {process.returncode}"
            )
        row = json.loads(report_path.read_text(encoding="utf-8"))
        if row.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
            raise RuntimeError("Phase 7B9ai worker report changed")
        row["output_block_sha256"] = base.phase7b9d._block_sha256(
            output,
            shape,
            int(row["core_group_start"]),
            int(row["core_group_stop"]),
        )
        manifest["completed_blocks"].append(row)
        manifest["completed_blocks"].sort(key=lambda item: int(item["block_index"]))
        manifest["accumulated_wall_runtime_s"] = float(
            manifest["accumulated_wall_runtime_s"]
        ) + (time.perf_counter() - started)
        _write_json_atomic(manifest_path, manifest)
        print(
            json.dumps(
                {
                    "completed_blocks": len(manifest["completed_blocks"]),
                    "total_blocks": len(selected),
                    "latest_block": block_index,
                }
            ),
            flush=True,
        )
    reports = list(manifest["completed_blocks"])
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
        "full_runtime_pass": float(manifest["accumulated_wall_runtime_s"])
        < gates["full_candidate_wall_time_strictly_below_s"],
    }
    passed = all(checks.values())
    output_sha = base._sha256(output)
    manifest["status"] = "complete" if passed else "gate_failed"
    manifest["output_state_sha256"] = output_sha
    _write_json_atomic(manifest_path, manifest)
    figure = OUTPUT / "phase7b9ai_dominant_band_krylov_candidate.png"
    _plot(figure, reports, gates, passed)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "source_state_path": configuration["current_state_path"],
        "source_state_sha256": configuration["current_state_sha256"],
        "candidate_state_path": configuration["output_state_path"],
        "candidate_state_sha256": output_sha,
        "selected_blocks": selected,
        "wall_runtime_s": manifest["accumulated_wall_runtime_s"],
        "gate_checks": checks,
        "decision": {
            "dominant_band_krylov_candidate_passed": passed,
            "candidate_self_guard_residual_audit_authorized": passed,
            "material_feedback_authorized": False,
        },
        "reports": reports,
        "figures": [figure.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9ai_dominant_band_krylov_candidate_summary.json", summary
    )
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            OUTPUT / "phase7b9ai_preregistered_dominant_band_krylov_candidate.json"
        ),
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if (
            args.block_index is None
            or args.output_state is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires block, output state and report")
        _run_worker(
            args.protocol, args.block_index, args.output_state, args.worker_report
        )
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
