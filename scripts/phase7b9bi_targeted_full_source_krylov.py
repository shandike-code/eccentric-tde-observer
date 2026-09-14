"""Phase 7B9bi：仅更新控制全局残差的频率块，保留完整正强度状态。"""

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
    from scripts import phase7b9r_full_source_krylov_line_search as worker
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9r_full_source_krylov_line_search as worker  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = "a419095498cb8feb14b0f49a3863dc4b48ed642dc611224e93ecc12d4015b950"
base = worker.base


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if _sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9bi protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or _sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9bi source changed: {source['path']}"
                )
    return protocol


def _shape(configuration: dict[str, object]) -> tuple[int, int, int]:
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _initialize_output(
    protocol: dict[str, object], shape: tuple[int, int, int]
) -> dict[str, object]:
    configuration = protocol["configuration"]
    current = ROOT / configuration["current_state_path"]
    output = ROOT / configuration["output_state_path"]
    expected_size = int(configuration["raw_float64_checkpoint_size_bytes"])
    if (
        _sha256(current) != configuration["current_state_sha256"]
        or output.stat().st_size != expected_size
        or _sha256(output) != configuration["output_state_previous_sha256"]
    ):
        raise RuntimeError("Phase 7B9bi input or named scratch output changed")
    current_map = np.memmap(current, mode="r", dtype=np.float64, shape=shape)
    output_map = np.memmap(output, mode="r+", dtype=np.float64, shape=shape)
    chunk = int(configuration["copy_frequency_chunk"])
    for start in range(0, shape[0], chunk):
        stop = min(start + chunk, shape[0])
        output_map[start:stop] = current_map[start:stop]
    output_map.flush()
    del current_map, output_map
    if _sha256(output) != configuration["current_state_sha256"]:
        raise RuntimeError("Phase 7B9bi full-state initialization changed bytes")
    return {
        "phase": protocol["phase"],
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "status": "running",
        "current_state_path": configuration["current_state_path"],
        "current_state_sha256": configuration["current_state_sha256"],
        "output_state_path": configuration["output_state_path"],
        "base_copy_sha256": configuration["current_state_sha256"],
        "completed_blocks": [],
        "accumulated_wall_runtime_s": 0.0,
    }


def _load_manifest(
    protocol: dict[str, object], shape: tuple[int, int, int]
) -> dict[str, object]:
    path = ROOT / protocol["configuration"]["manifest_path"]
    if not path.exists():
        manifest = _initialize_output(protocol, shape)
        _write_json_atomic(path, manifest)
        return manifest
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (
        manifest.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256
        or manifest.get("status") not in ("running", "candidate_passed", "candidate_failed")
    ):
        raise RuntimeError("Phase 7B9bi manifest is incompatible")
    output = ROOT / manifest["output_state_path"]
    for row in manifest["completed_blocks"]:
        digest = base.phase7b9d._block_sha256(
            output,
            shape,
            int(row["core_group_start"]),
            int(row["core_group_stop"]),
        )
        if digest != row["output_block_sha256"]:
            raise RuntimeError(
                f"Phase 7B9bi completed block changed: {row['block_index']}"
            )
    return manifest


def _run_worker(
    protocol_path: Path,
    protocol: dict[str, object],
    block_index: int,
    report_path: Path,
    output_path: Path,
) -> None:
    worker._run_worker(
        protocol_path,
        block_index,
        report_path,
        protocol_override=protocol,
        output_state_path=output_path,
    )


def _plot(path: Path, reports: list[dict[str, object]], selected_count: int) -> None:
    block = np.asarray([row["block_index"] for row in reports])
    ratio = np.asarray(
        [row["fresh_line_candidate_to_raw_residual_ratio"] for row in reports]
    )
    fraction = np.asarray([row["line_selected_fraction"] for row in reports])
    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.5), constrained_layout=True)
    axes[0].semilogy(block, ratio, "o-")
    axes[0].set(
        xlabel="Natural frequency block",
        ylabel="Krylov / raw block residual",
        title="(a) Targeted full-source Krylov response",
    )
    axes[1].plot(block, fraction, "o-", color="tab:green")
    axes[1].set(
        xlabel="Natural frequency block",
        ylabel="Selected affine-line fraction",
        title=f"(b) Updated blocks ({selected_count} total)",
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    shape = _shape(configuration)
    selected = [int(row["block_index"]) for row in configuration["selected_blocks"]]
    manifest_path = ROOT / configuration["manifest_path"]
    manifest = _load_manifest(protocol, shape)
    output_path = ROOT / configuration["output_state_path"]
    completed = {int(row["block_index"]): row for row in manifest["completed_blocks"]}
    report_directory = ROOT / configuration["report_directory"]
    report_directory.mkdir(parents=True, exist_ok=True)
    if manifest["status"] == "running":
        for block_index in selected:
            if block_index in completed:
                continue
            report_path = report_directory / f"phase7b9bi_block{block_index:02d}.json"
            started = time.perf_counter()
            process = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / configuration["runner_path"]),
                    "--worker",
                    "--protocol",
                    str(protocol_path),
                    "--block-index",
                    str(block_index),
                    "--worker-report",
                    str(report_path),
                    "--output-state",
                    str(output_path),
                ],
                cwd=ROOT,
                check=False,
            )
            if process.returncode != 0:
                raise RuntimeError(
                    f"Phase 7B9bi worker {block_index} failed: {process.returncode}"
                )
            row = json.loads(report_path.read_text(encoding="utf-8"))
            if int(row["block_index"]) != block_index:
                raise RuntimeError("Phase 7B9bi worker block identity changed")
            row["output_block_sha256"] = base.phase7b9d._block_sha256(
                output_path,
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
                        "completed_target_blocks": len(manifest["completed_blocks"]),
                        "total_target_blocks": len(selected),
                        "latest_block": block_index,
                        "latest_residual_ratio": row[
                            "fresh_line_candidate_to_raw_residual_ratio"
                        ],
                    }
                ),
                flush=True,
            )
    reports = list(manifest["completed_blocks"])
    reports.sort(key=lambda row: int(row["block_index"]))
    gates = protocol["gates"]
    ratio = np.asarray(
        [row["fresh_line_candidate_to_raw_residual_ratio"] for row in reports]
    )
    boundary = np.asarray(
        [row["fresh_line_candidate_to_raw_boundary_ratio"] for row in reports]
    )
    checks = {
        "selected_block_identity_pass": [int(row["block_index"]) for row in reports]
        == selected,
        "finite_krylov_budget_pass": all(
            row["gmres_iteration_count"] <= gates["each_gmres_iteration_count_at_most"]
            for row in reports
        ),
        "positive_endpoint_and_candidate_pass": all(
            row["endpoint_exact_nonnegative_step"]
            >= gates["each_endpoint_exact_nonnegative_step_at_least"]
            and row["minimum_line_candidate_intensity"]
            >= gates["minimum_line_candidate_intensity_at_least"]
            for row in reports
        ),
        "useful_line_steps_pass": all(
            row["line_selected_fraction"] >= gates["each_selected_line_fraction_at_least"]
            for row in reports
        ),
        "local_residual_improvement_pass": bool(
            np.all(ratio < gates["each_fresh_line_candidate_to_raw_residual_ratio_below"])
        ),
        "local_boundary_pass": bool(
            np.all(boundary <= gates["each_fresh_line_candidate_boundary_ratio_at_most"])
        ),
        "affine_prediction_pass": all(
            row["affine_prediction_to_fresh_residual_linf"]
            < gates["each_affine_prediction_to_fresh_residual_linf_below"]
            for row in reports
        ),
        "resources_pass": all(
            row["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            for row in reports
        )
        and float(manifest["accumulated_wall_runtime_s"])
        < gates["targeted_map_wall_time_strictly_below_s"],
    }
    passed = len(reports) == len(selected) and all(checks.values())
    candidate_sha = _sha256(output_path) if passed else None
    manifest["status"] = "candidate_passed" if passed else "candidate_failed"
    manifest["candidate_state_sha256"] = candidate_sha
    _write_json_atomic(manifest_path, manifest)
    figure_path = ROOT / configuration["figure_path"]
    _plot(figure_path, reports, len(selected))
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-solver]+[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "selection_rule": configuration["selection_rule"],
        "selected_blocks": configuration["selected_blocks"],
        "candidate_state_path": configuration["output_state_path"] if passed else None,
        "candidate_state_sha256": candidate_sha,
        "completed_target_block_count": len(reports),
        "maximum_local_candidate_to_raw_residual_ratio": float(np.max(ratio)),
        "median_local_candidate_to_raw_residual_ratio": float(np.median(ratio)),
        "minimum_selected_line_fraction": float(
            min(row["line_selected_fraction"] for row in reports)
        ),
        "maximum_peak_process_rss_mib": float(
            max(row["peak_process_rss_mib"] for row in reports)
        ),
        "wall_runtime_s": manifest["accumulated_wall_runtime_s"],
        "gate_checks": checks,
        "decision": {
            "targeted_full_source_krylov_candidate_passed": passed,
            "candidate_preserves_unselected_current_state_blocks": passed,
            "fresh_global_original_operator_audit_authorized": passed,
            "material_feedback_authorized": False,
        },
        "reports": reports,
        "figures": [figure_path.name],
    }
    _write_json_atomic(ROOT / configuration["summary_path"], summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9bi_preregistered_targeted_full_source_krylov.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--output-state", type=Path)
    args = parser.parse_args()
    if args.worker:
        if (
            args.block_index is None
            or args.worker_report is None
            or args.output_state is None
        ):
            raise ValueError("worker mode requires block, report and output state")
        protocol = _load_protocol(args.protocol, validate_sources=False)
        _run_worker(
            args.protocol,
            protocol,
            args.block_index,
            args.worker_report,
            args.output_state,
        )
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
