"""Phase 7B9al：可恢复的全频率正 Picard 收敛序列。"""

from __future__ import annotations

import argparse
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
    from scripts import phase7b9ac_global_positive_picard_map as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ac_global_positive_picard_map as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "c344204c0b8b6a4ad1131e0f60b7ed93ab33a791ba7dfda574095ee2abe153bc"
)
base = generic.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9al protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9al source changed: {source['path']}"
                )
    return protocol


def _shape(protocol: dict[str, object]) -> tuple[int, int, int]:
    configuration = protocol["configuration"]
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _run_worker(
    protocol_path: Path,
    iteration: int,
    block_index: int,
    input_state: Path,
    input_sha256: str,
    output_state: Path,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    dynamic = json.loads(json.dumps(protocol))
    configuration = dynamic["configuration"]
    configuration["input_state_path"] = _relative(input_state)
    configuration["input_state_sha256"] = input_sha256
    # 中文：数值核保持不变，只在双缓冲间切换当前全局守卫态。
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    generic._load_protocol = lambda _path, validate_sources=False: dynamic
    generic._run_worker(protocol_path, block_index, output_state, report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["picard_iteration"] = iteration
    report["input_state_path"] = _relative(input_state)
    report["output_state_path"] = _relative(output_state)
    _write_json_atomic(report_path, report)


def _aggregate(
    reports: list[dict[str, object]], shape: tuple[int, int, int]
) -> dict[str, object]:
    ownership = np.zeros(shape[0], dtype=np.int64)
    for row in reports:
        ownership[int(row["core_group_start"]) : int(row["core_group_stop"])] += 1
    maximum_change = max(
        float(row["maximum_absolute_radiation_change"]) for row in reports
    )
    maximum_scale = max(float(row["maximum_radiation_scale"]) for row in reports)
    boundary_numerator = sum(
        float(row["boundary_spectrum_l1_numerator"]) for row in reports
    )
    current_scale = sum(
        float(row["current_boundary_absolute_scale"]) for row in reports
    )
    mapped_scale = sum(
        float(row["mapped_boundary_absolute_scale"]) for row in reports
    )
    current_bolometric = sum(
        float(row["current_boundary_bolometric"]) for row in reports
    )
    mapped_bolometric = sum(
        float(row["mapped_boundary_bolometric"]) for row in reports
    )
    return {
        "frequency_ownership_count": int(np.sum(ownership)),
        "frequency_ownership_exact": bool(np.all(ownership == 1)),
        "global_original_operator_residual": (
            maximum_change / maximum_scale if maximum_scale > 0.0 else maximum_change
        ),
        "boundary_spectrum_l1": boundary_numerator
        / max(current_scale, mapped_scale),
        "boundary_bolometric_fraction": abs(
            mapped_bolometric - current_bolometric
        )
        / max(abs(current_bolometric), abs(mapped_bolometric)),
        "minimum_input_intensity": min(
            float(row["minimum_input_intensity"]) for row in reports
        ),
        "minimum_mapped_intensity": min(
            float(row["minimum_mapped_intensity"]) for row in reports
        ),
        "maximum_process_peak_rss_mib": max(
            float(row["peak_process_rss_mib"]) for row in reports
        ),
        "maximum_worker_wall_runtime_s": max(
            float(row["wall_runtime_s"]) for row in reports
        ),
    }


def _plot(path: Path, iterations: list[dict[str, object]]) -> None:
    index = np.asarray([int(row["iteration"]) for row in iterations])
    residual = np.asarray(
        [float(row["global_original_operator_residual"]) for row in iterations]
    )
    boundary = np.asarray(
        [float(row["boundary_spectrum_l1"]) for row in iterations]
    )
    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.5), constrained_layout=True)
    axes[0].semilogy(index, residual, "o-", label="Audited input residual")
    axes[0].axhline(1.0e-4, color="0.25", ls="--", label="Convergence gate")
    axes[0].set(
        xlabel="Positive Picard map index",
        ylabel="Global original-operator residual",
        title="(a) Full-frequency convergence",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].semilogy(index, boundary, "s-", label="Boundary spectral L1")
    axes[1].axhline(1.0e-3, color="0.25", ls="--", label="Boundary gate")
    axes[1].set(
        xlabel="Positive Picard map index",
        ylabel="Boundary-functional change",
        title="(b) Boundary guard",
    )
    axes[1].legend(frameon=False, fontsize=8)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _summary(
    protocol: dict[str, object], manifest: dict[str, object]
) -> dict[str, object]:
    configuration = protocol["configuration"]
    iterations = manifest["iterations"]
    figure = ROOT / configuration["figure_path"]
    if iterations:
        _plot(figure, iterations)
    converged = manifest["status"] == "complete"
    payload = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "status": manifest["status"],
        "completed_picard_maps": len(iterations),
        "residual_history": [
            float(row["global_original_operator_residual"]) for row in iterations
        ],
        "contraction_ratio_history": [row["contraction_ratio"] for row in iterations],
        "boundary_spectrum_l1_history": [
            float(row["boundary_spectrum_l1"]) for row in iterations
        ],
        "accepted_state_path": manifest.get("accepted_state_path"),
        "accepted_state_sha256": manifest.get("accepted_state_sha256"),
        "iterations": iterations,
        "decision": {
            "positive_picard_sequence_converged": converged,
            "audited_radiation_state_accepted": converged,
            "material_feedback_authorized": converged,
            "dynamic_nlte_solution_accepted": False,
        },
        "figures": [figure.name] if iterations else [],
    }
    _write_json_atomic(ROOT / configuration["summary_path"], payload)
    return payload


def run(
    protocol_path: Path, *, stop_after_iteration: int | None = None
) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    shape = _shape(protocol)
    expected_size = int(configuration["raw_float64_checkpoint_size_bytes"])
    manifest_path = ROOT / configuration["manifest_path"]
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
            raise RuntimeError("Phase 7B9al manifest belongs to another protocol")
        current = ROOT / manifest["current_input_path"]
        if current.stat().st_size != expected_size:
            raise RuntimeError("Phase 7B9al current input size changed")
        if base._sha256(current) != manifest["current_input_sha256"]:
            raise RuntimeError("Phase 7B9al current input bytes changed")
    else:
        initial = ROOT / configuration["initial_state_path"]
        scratch = ROOT / configuration["scratch_state_path"]
        if (
            initial.stat().st_size != expected_size
            or scratch.stat().st_size != expected_size
            or base._sha256(initial) != configuration["initial_state_sha256"]
            or base._sha256(scratch)
            != configuration["scratch_state_initial_sha256"]
        ):
            raise RuntimeError("Phase 7B9al initial double buffers changed")
        manifest = {
            "phase": protocol["phase"],
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "status": "running",
            "current_input_path": configuration["initial_state_path"],
            "current_input_sha256": configuration["initial_state_sha256"],
            "next_output_path": configuration["scratch_state_path"],
            "iterations": [],
            "active_iteration": None,
        }
        _write_json_atomic(manifest_path, manifest)
    if manifest["status"] != "running":
        return _summary(protocol, manifest)
    report_root = ROOT / configuration["report_directory"]
    runner_path = ROOT / configuration["runner_path"]
    while len(manifest["iterations"]) < int(configuration["maximum_picard_maps"]):
        iteration = len(manifest["iterations"])
        input_state = ROOT / manifest["current_input_path"]
        output_state = ROOT / manifest["next_output_path"]
        if output_state.stat().st_size != expected_size or input_state == output_state:
            raise RuntimeError("Phase 7B9al output buffer is invalid")
        active = manifest.get("active_iteration")
        if active is None:
            active = {
                "iteration": iteration,
                "input_state_path": _relative(input_state),
                "input_state_sha256": manifest["current_input_sha256"],
                "output_state_path": _relative(output_state),
                "completed_blocks": [],
                "accumulated_wall_runtime_s": 0.0,
            }
            manifest["active_iteration"] = active
            _write_json_atomic(manifest_path, manifest)
        if (
            int(active["iteration"]) != iteration
            or active["input_state_path"] != _relative(input_state)
            or active["input_state_sha256"] != manifest["current_input_sha256"]
            or active["output_state_path"] != _relative(output_state)
        ):
            raise RuntimeError("Phase 7B9al active iteration changed")
        completed = {
            int(row["block_index"]): row for row in active["completed_blocks"]
        }
        for row in completed.values():
            digest = base.phase7b9d._block_sha256(
                output_state,
                shape,
                int(row["core_group_start"]),
                int(row["core_group_stop"]),
            )
            if digest != row["output_block_sha256"]:
                raise RuntimeError(
                    f"Phase 7B9al completed block changed: {row['block_index']}"
                )
        pending = [index for index in range(76) if index not in completed]
        concurrency = int(configuration["maximum_concurrent_processes"])
        iteration_dir = report_root / f"iteration_{iteration:02d}"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        for offset in range(0, len(pending), concurrency):
            batch = pending[offset : offset + concurrency]
            started = time.perf_counter()
            report_paths = [
                iteration_dir / f"phase7b9al_block{index:02d}.json"
                for index in batch
            ]
            processes = [
                subprocess.Popen(
                    [
                        sys.executable,
                        str(runner_path),
                        "--worker",
                        "--protocol",
                        str(protocol_path),
                        "--iteration",
                        str(iteration),
                        "--block-index",
                        str(index),
                        "--input-state",
                        str(input_state),
                        "--input-sha256",
                        str(manifest["current_input_sha256"]),
                        "--output-state",
                        str(output_state),
                        "--worker-report",
                        str(report_path),
                    ],
                    cwd=ROOT,
                )
                for index, report_path in zip(batch, report_paths, strict=True)
            ]
            codes = [process.wait() for process in processes]
            if any(code != 0 for code in codes):
                raise RuntimeError(f"Phase 7B9al worker batch failed: {codes}")
            for index, report_path in zip(batch, report_paths, strict=True):
                row = json.loads(report_path.read_text(encoding="utf-8"))
                if (
                    row.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256
                    or int(row.get("block_index", -1)) != index
                    or int(row.get("picard_iteration", -1)) != iteration
                ):
                    raise RuntimeError("Phase 7B9al worker report changed")
                row["output_block_sha256"] = base.phase7b9d._block_sha256(
                    output_state,
                    shape,
                    int(row["core_group_start"]),
                    int(row["core_group_stop"]),
                )
                active["completed_blocks"].append(row)
            active["completed_blocks"].sort(key=lambda row: int(row["block_index"]))
            active["accumulated_wall_runtime_s"] = float(
                active["accumulated_wall_runtime_s"]
            ) + (time.perf_counter() - started)
            _write_json_atomic(manifest_path, manifest)
            print(
                json.dumps(
                    {
                        "picard_iteration": iteration,
                        "completed_blocks": len(active["completed_blocks"]),
                        "total_blocks": 76,
                        "latest_blocks": batch,
                    }
                ),
                flush=True,
            )
        reports = list(active["completed_blocks"])
        metrics = _aggregate(reports, shape)
        prior_residual = (
            float(manifest["iterations"][-1]["global_original_operator_residual"])
            if manifest["iterations"]
            else None
        )
        contraction = (
            float(metrics["global_original_operator_residual"]) / prior_residual
            if prior_residual is not None
            else None
        )
        reference = protocol["reference"]
        initial_reproduction = iteration != 0 or (
            abs(
                float(metrics["global_original_operator_residual"])
                - float(reference["initial_global_residual"])
            )
            <= gates["initial_audit_absolute_tolerance"]
            and abs(
                float(metrics["boundary_spectrum_l1"])
                - float(reference["initial_boundary_spectrum_l1"])
            )
            <= gates["initial_audit_absolute_tolerance"]
            and abs(
                float(metrics["boundary_bolometric_fraction"])
                - float(reference["initial_boundary_bolometric_fraction"])
            )
            <= gates["initial_audit_absolute_tolerance"]
        )
        checks = {
            "frequency_ownership_pass": len(reports) == gates["block_count_exactly"]
            and metrics["frequency_ownership_count"]
            == gates["owned_frequency_group_count_exactly"]
            and metrics["frequency_ownership_exact"],
            "positive_map_pass": metrics["minimum_input_intensity"]
            >= gates["minimum_input_and_mapped_intensity_at_least"]
            and metrics["minimum_mapped_intensity"]
            >= gates["minimum_input_and_mapped_intensity_at_least"],
            "initial_reproduction_pass": initial_reproduction,
            "contraction_pass": contraction is None
            or contraction < gates["subsequent_residual_contraction_ratio_below"],
            "boundary_pass": metrics["boundary_spectrum_l1"]
            < gates["global_boundary_spectrum_l1_below"]
            and metrics["boundary_bolometric_fraction"]
            < gates["global_boundary_bolometric_fraction_below"],
            "resources_pass": metrics["maximum_process_peak_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and metrics["maximum_worker_wall_runtime_s"]
            < gates["each_worker_wall_time_strictly_below_s"]
            and float(active["accumulated_wall_runtime_s"])
            < gates["each_full_map_wall_time_strictly_below_s"],
        }
        map_passed = all(checks.values())
        output_sha = base._sha256(output_state)
        record = {
            "iteration": iteration,
            "input_state_path": _relative(input_state),
            "input_state_sha256": manifest["current_input_sha256"],
            "mapped_state_path": _relative(output_state),
            "mapped_state_sha256": output_sha,
            **metrics,
            "contraction_ratio": contraction,
            "full_map_wall_runtime_s": active["accumulated_wall_runtime_s"],
            "gate_checks": checks,
            "map_passed": map_passed,
            "reports": reports,
        }
        manifest["iterations"].append(record)
        manifest["active_iteration"] = None
        converged = (
            map_passed
            and float(metrics["global_original_operator_residual"])
            < gates["global_original_operator_residual_below"]
        )
        if converged:
            manifest["status"] = "complete"
            manifest["accepted_state_path"] = _relative(input_state)
            manifest["accepted_state_sha256"] = manifest["current_input_sha256"]
        elif not map_passed:
            manifest["status"] = "gate_failed"
        elif len(manifest["iterations"]) >= int(configuration["maximum_picard_maps"]):
            manifest["status"] = "maximum_maps_exhausted"
        else:
            manifest["current_input_path"] = _relative(output_state)
            manifest["current_input_sha256"] = output_sha
            manifest["next_output_path"] = _relative(input_state)
        _write_json_atomic(manifest_path, manifest)
        current_summary = _summary(protocol, manifest)
        print(
            json.dumps(
                {
                    "picard_iteration": iteration,
                    "global_residual": metrics[
                        "global_original_operator_residual"
                    ],
                    "contraction_ratio": contraction,
                    "boundary_spectrum_l1": metrics["boundary_spectrum_l1"],
                    "status": manifest["status"],
                }
            ),
            flush=True,
        )
        if manifest["status"] != "running":
            print(json.dumps(current_summary, indent=2))
            return current_summary
        if stop_after_iteration is not None and iteration >= stop_after_iteration:
            print(
                json.dumps(
                    {
                        "status": "operator_requested_pause",
                        "next_picard_iteration": len(manifest["iterations"]),
                    }
                ),
                flush=True,
            )
            return current_summary
    return _summary(protocol, manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9al_preregistered_positive_picard_convergence.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--stop-after-iteration", type=int)
    args = parser.parse_args()
    if args.worker:
        if (
            args.iteration is None
            or args.block_index is None
            or args.input_state is None
            or args.input_sha256 is None
            or args.output_state is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires iteration, block and both states")
        _run_worker(
            args.protocol,
            args.iteration,
            args.block_index,
            args.input_state,
            args.input_sha256,
            args.output_state,
            args.worker_report,
        )
        return
    run(args.protocol, stop_after_iteration=args.stop_after_iteration)


if __name__ == "__main__":
    main()
