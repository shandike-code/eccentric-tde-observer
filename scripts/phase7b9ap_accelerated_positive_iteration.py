"""Phase 7B9ap：全局正 Picard 方向超松弛的可恢复收敛循环。"""

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
    from scripts import phase7b9ac_global_positive_picard_map as map_generic
    from scripts import phase7b9am_global_picard_overrelaxation as line_generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ac_global_positive_picard_map as map_generic  # type: ignore[no-redef]
    import phase7b9am_global_picard_overrelaxation as line_generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "a541976e05132bd1fba57e2d3fb87a30ee7cf8e24cfa71d48fb123450986b907"
)
base = map_generic.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9ap protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9ap source changed: {source['path']}"
                )
    return protocol


def _shape(configuration: dict[str, object]) -> tuple[int, int, int]:
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _dynamic_protocol(
    protocol: dict[str, object], current: Path, current_sha: str, scratch: Path
) -> dict[str, object]:
    dynamic = json.loads(json.dumps(protocol))
    configuration = dynamic["configuration"]
    configuration["input_state_path"] = _relative(current)
    configuration["input_state_sha256"] = current_sha
    configuration["lower_state_path"] = _relative(current)
    configuration["upper_state_path"] = _relative(scratch)
    return dynamic


def _run_map_worker(
    protocol_path: Path,
    cycle: int,
    block_index: int,
    current: Path,
    current_sha: str,
    scratch: Path,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    dynamic = _dynamic_protocol(protocol, current, current_sha, scratch)
    map_generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    map_generic._load_protocol = lambda _path, validate_sources=False: dynamic
    map_generic._run_worker(protocol_path, block_index, scratch, report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["cycle"] = cycle
    report["stage"] = "map"
    _write_json_atomic(report_path, report)


def _run_line_worker(
    protocol_path: Path,
    cycle: int,
    block_index: int,
    current: Path,
    current_sha: str,
    scratch: Path,
    grid_path: Path,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    dynamic = _dynamic_protocol(protocol, current, current_sha, scratch)
    line_generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    line_generic._load_protocol = lambda _path, validate_sources=False: dynamic
    line_generic._run_candidate_worker(
        protocol_path, block_index, grid_path, report_path
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["cycle"] = cycle
    report["stage"] = "line"
    _write_json_atomic(report_path, report)


def _aggregate_map(
    reports: list[dict[str, object]], shape: tuple[int, int, int]
) -> dict[str, object]:
    ownership = np.zeros(shape[0], dtype=np.int8)
    for row in reports:
        ownership[int(row["core_group_start"]) : int(row["core_group_stop"])] += 1
    maximum_change = max(
        float(row["maximum_absolute_radiation_change"]) for row in reports
    )
    maximum_scale = max(float(row["maximum_radiation_scale"]) for row in reports)
    numerator = sum(
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
        "global_residual": maximum_change / maximum_scale,
        "boundary_spectrum_l1": numerator / max(current_scale, mapped_scale),
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


def _plot(path: Path, cycles: list[dict[str, object]]) -> None:
    index = np.asarray([int(row["cycle"]) for row in cycles])
    audited = np.asarray([float(row["audited_input_residual"]) for row in cycles])
    selected = np.asarray([float(row["selected_predicted_residual"]) for row in cycles])
    theta = np.asarray([float(row["selected_theta"]) for row in cycles])
    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.5), constrained_layout=True)
    axes[0].semilogy(index, audited, "o-", label="Fresh input audit")
    axes[0].semilogy(index, selected, "s--", label="Selected affine prediction")
    axes[0].axhline(1.0e-4, color="0.25", ls=":", label="Convergence gate")
    axes[0].set(
        xlabel="Accelerated cycle",
        ylabel="Global original-operator residual",
        title="(a) Positive accelerated convergence",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].plot(index, theta, "o-")
    axes[1].set(
        xlabel="Accelerated cycle",
        ylabel="Selected global theta",
        title="(b) Accepted overrelaxation factor",
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _summary(
    protocol: dict[str, object], manifest: dict[str, object]
) -> dict[str, object]:
    configuration = protocol["configuration"]
    figure = ROOT / configuration["figure_path"]
    if manifest["cycles"]:
        _plot(figure, manifest["cycles"])
    converged = manifest["status"] == "complete"
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "status": manifest["status"],
        "completed_cycles": len(manifest["cycles"]),
        "current_state_path": manifest["current_state_path"],
        "current_state_sha256": manifest["current_state_sha256"],
        "current_predicted_residual": manifest["expected_residual"],
        "cycles": manifest["cycles"],
        "accepted_state_path": manifest.get("accepted_state_path"),
        "accepted_state_sha256": manifest.get("accepted_state_sha256"),
        "final_audit": manifest.get("final_audit"),
        "decision": {
            "accelerated_positive_iteration_converged": converged,
            "freshly_audited_radiation_state_accepted": converged,
            "material_feedback_authorized": converged,
            "dynamic_nlte_solution_accepted": False,
        },
        "figures": [figure.name] if manifest["cycles"] else [],
    }
    _write_json_atomic(ROOT / configuration["summary_path"], summary)
    return summary


def _launch_stage(
    protocol_path: Path,
    protocol: dict[str, object],
    manifest: dict[str, object],
    *,
    stage: str,
    current: Path,
    scratch: Path,
    grid_path: Path,
    shape: tuple[int, int, int],
) -> list[dict[str, object]]:
    configuration = protocol["configuration"]
    cycle = len(manifest["cycles"])
    active = manifest["active_stage"]
    reports_by_block = {
        int(row["block_index"]): row for row in active["reports"]
    }
    if stage == "map":
        for row in reports_by_block.values():
            digest = base.phase7b9d._block_sha256(
                scratch,
                shape,
                int(row["core_group_start"]),
                int(row["core_group_stop"]),
            )
            if digest != row["output_block_sha256"]:
                raise RuntimeError("Phase 7B9ap completed map block changed")
    pending = [index for index in range(76) if index not in reports_by_block]
    directory = ROOT / configuration["report_directory"] / f"cycle_{cycle:02d}" / stage
    directory.mkdir(parents=True, exist_ok=True)
    runner = ROOT / configuration["runner_path"]
    concurrency = int(configuration["maximum_concurrent_processes"])
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        started = time.perf_counter()
        paths = [directory / f"phase7b9ap_{stage}_block{index:02d}.json" for index in batch]
        processes = []
        for index, path in zip(batch, paths, strict=True):
            command = [
                sys.executable,
                str(runner),
                f"--{stage}-worker",
                "--protocol",
                str(protocol_path),
                "--cycle",
                str(cycle),
                "--block-index",
                str(index),
                "--current-state",
                str(current),
                "--current-sha256",
                manifest["current_state_sha256"],
                "--scratch-state",
                str(scratch),
                "--worker-report",
                str(path),
            ]
            if stage == "line":
                command.extend(["--grid", str(grid_path)])
            processes.append(subprocess.Popen(command, cwd=ROOT))
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"Phase 7B9ap {stage} batch failed: {codes}")
        for index, path in zip(batch, paths, strict=True):
            row = json.loads(path.read_text(encoding="utf-8"))
            if (
                row.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256
                or int(row.get("block_index", -1)) != index
                or int(row.get("cycle", -1)) != cycle
                or row.get("stage") != stage
            ):
                raise RuntimeError("Phase 7B9ap worker report changed")
            if stage == "map":
                row["output_block_sha256"] = base.phase7b9d._block_sha256(
                    scratch,
                    shape,
                    int(row["core_group_start"]),
                    int(row["core_group_stop"]),
                )
            active["reports"].append(row)
        active["reports"].sort(key=lambda row: int(row["block_index"]))
        active["wall_runtime_s"] = float(active["wall_runtime_s"]) + (
            time.perf_counter() - started
        )
        _write_json_atomic(ROOT / configuration["manifest_path"], manifest)
        print(
            json.dumps(
                {
                    "cycle": cycle,
                    "stage": stage,
                    "completed_blocks": len(active["reports"]),
                    "total_blocks": 76,
                    "latest_blocks": batch,
                }
            ),
            flush=True,
        )
    return list(active["reports"])


def run(
    protocol_path: Path, *, stop_after_map_cycle: int | None = None
) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    shape = _shape(configuration)
    manifest_path = ROOT / configuration["manifest_path"]
    grid_path = ROOT / configuration["grid_path"]
    if not grid_path.exists():
        _write_json_atomic(
            grid_path,
            {
                "phase": "7B9ap fixed positive global theta grid",
                "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
                "theta_candidates": configuration["theta_candidates"],
            },
        )
    grid = json.loads(grid_path.read_text(encoding="utf-8"))
    if grid["protocol_sha256"] != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("Phase 7B9ap fixed grid changed")
    current = ROOT / configuration["initial_current_state_path"]
    scratch = ROOT / configuration["scratch_state_path"]
    expected_size = int(configuration["raw_float64_checkpoint_size_bytes"])
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
            raise RuntimeError("Phase 7B9ap manifest belongs to another protocol")
        current = ROOT / manifest["current_state_path"]
        scratch = ROOT / manifest["scratch_state_path"]
        active = manifest.get("active_stage")
        if active is None or active.get("stage") != "write":
            if base._sha256(current) != manifest["current_state_sha256"]:
                raise RuntimeError("Phase 7B9ap current state changed")
    else:
        if (
            current.stat().st_size != expected_size
            or scratch.stat().st_size != expected_size
            or base._sha256(current)
            != configuration["initial_current_state_sha256"]
            or base._sha256(scratch)
            != configuration["scratch_state_initial_sha256"]
        ):
            raise RuntimeError("Phase 7B9ap initial buffers changed")
        reference = protocol["reference"]
        manifest = {
            "phase": protocol["phase"],
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "status": "running",
            "current_state_path": _relative(current),
            "current_state_sha256": configuration["initial_current_state_sha256"],
            "scratch_state_path": _relative(scratch),
            "expected_residual": reference["initial_global_residual"],
            "expected_boundary_spectrum_l1": reference[
                "initial_boundary_spectrum_l1"
            ],
            "expected_boundary_bolometric_fraction": reference[
                "initial_boundary_bolometric_fraction"
            ],
            "cycles": [],
            "active_stage": None,
        }
        _write_json_atomic(manifest_path, manifest)
    if manifest["status"] != "running":
        return _summary(protocol, manifest)
    while len(manifest["cycles"]) < int(configuration["maximum_cycles"]):
        cycle = len(manifest["cycles"])
        current = ROOT / manifest["current_state_path"]
        scratch = ROOT / manifest["scratch_state_path"]
        if manifest["active_stage"] is None:
            manifest["active_stage"] = {
                "cycle": cycle,
                "stage": "map",
                "reports": [],
                "wall_runtime_s": 0.0,
            }
            _write_json_atomic(manifest_path, manifest)
        active = manifest["active_stage"]
        if int(active["cycle"]) != cycle:
            raise RuntimeError("Phase 7B9ap active cycle changed")
        if active["stage"] == "map":
            map_reports = _launch_stage(
                protocol_path,
                protocol,
                manifest,
                stage="map",
                current=current,
                scratch=scratch,
                grid_path=grid_path,
                shape=shape,
            )
            metrics = _aggregate_map(map_reports, shape)
            reproduction = (
                abs(metrics["global_residual"] - manifest["expected_residual"])
                <= gates["prediction_reproduction_absolute_tolerance"]
                and abs(
                    metrics["boundary_spectrum_l1"]
                    - manifest["expected_boundary_spectrum_l1"]
                )
                <= gates["prediction_reproduction_absolute_tolerance"]
                and abs(
                    metrics["boundary_bolometric_fraction"]
                    - manifest["expected_boundary_bolometric_fraction"]
                )
                <= gates["prediction_reproduction_absolute_tolerance"]
            )
            map_checks = {
                "frequency_ownership_pass": len(map_reports)
                == gates["block_count_exactly"]
                and metrics["frequency_ownership_count"]
                == gates["owned_frequency_group_count_exactly"]
                and metrics["frequency_ownership_exact"],
                "positive_map_pass": metrics["minimum_input_intensity"]
                >= gates["minimum_intensity_at_least"]
                and metrics["minimum_mapped_intensity"]
                >= gates["minimum_intensity_at_least"],
                "prediction_reproduction_pass": reproduction,
                "boundary_pass": metrics["boundary_spectrum_l1"]
                < gates["global_boundary_spectrum_l1_below"]
                and metrics["boundary_bolometric_fraction"]
                < gates["global_boundary_bolometric_fraction_below"],
                "resources_pass": metrics["maximum_process_peak_rss_mib"]
                < gates["each_process_peak_rss_strictly_below_mib"]
                and metrics["maximum_worker_wall_runtime_s"]
                < gates["map_worker_wall_time_strictly_below_s"]
                and active["wall_runtime_s"]
                < gates["each_stage_wall_time_strictly_below_s"],
            }
            if not all(map_checks.values()):
                manifest["status"] = "map_gate_failed"
                manifest["failure_checks"] = map_checks
                _write_json_atomic(manifest_path, manifest)
                return _summary(protocol, manifest)
            scratch_sha = base._sha256(scratch)
            if metrics["global_residual"] < gates[
                "global_original_operator_residual_below"
            ]:
                manifest["status"] = "complete"
                manifest["accepted_state_path"] = _relative(current)
                manifest["accepted_state_sha256"] = manifest[
                    "current_state_sha256"
                ]
                manifest["final_audit"] = {**metrics, "gate_checks": map_checks}
                manifest["active_stage"] = None
                _write_json_atomic(manifest_path, manifest)
                return _summary(protocol, manifest)
            manifest["active_stage"] = {
                "cycle": cycle,
                "stage": "line",
                "reports": [],
                "wall_runtime_s": 0.0,
                "map_metrics": metrics,
                "map_checks": map_checks,
                "scratch_state_sha256": scratch_sha,
            }
            _write_json_atomic(manifest_path, manifest)
            active = manifest["active_stage"]
            if stop_after_map_cycle is not None and cycle >= stop_after_map_cycle:
                print(
                    json.dumps(
                        {
                            "status": "operator_requested_pause_after_map",
                            "cycle": cycle,
                            "audited_input_residual": metrics["global_residual"],
                            "scratch_state_sha256": scratch_sha,
                        }
                    ),
                    flush=True,
                )
                return _summary(protocol, manifest)
        if active["stage"] == "line":
            if base._sha256(scratch) != active["scratch_state_sha256"]:
                raise RuntimeError("Phase 7B9ap scratch map changed")
            line_reports = _launch_stage(
                protocol_path,
                protocol,
                manifest,
                stage="line",
                current=current,
                scratch=scratch,
                grid_path=grid_path,
                shape=shape,
            )
            rows = line_generic._aggregate_candidate(line_reports, grid)
            valid = [
                row
                for row in rows
                if row["minimum_current_intensity"]
                >= gates["minimum_intensity_at_least"]
                and row["minimum_mapped_intensity"]
                >= gates["minimum_intensity_at_least"]
            ]
            if not valid:
                raise RuntimeError("Phase 7B9ap fixed grid has no positive candidate")
            selected = min(valid, key=lambda row: (row["global_residual"], row["theta"]))
            theta_zero = next(row for row in rows if row["theta"] == 0.0)
            line_ownership = np.zeros(shape[0], dtype=np.int8)
            for report in line_reports:
                line_ownership[
                    int(report["core_group_start"]) : int(report["core_group_stop"])
                ] += 1
            line_checks = {
                "frequency_ownership_pass": len(line_reports)
                == gates["block_count_exactly"]
                and int(np.sum(line_ownership))
                == gates["owned_frequency_group_count_exactly"]
                and bool(np.all(line_ownership == 1)),
                "theta_zero_reproduction_pass": abs(
                    theta_zero["global_residual"]
                    - active["map_metrics"]["global_residual"]
                )
                <= gates["prediction_reproduction_absolute_tolerance"]
                and abs(
                    theta_zero["boundary_spectrum_l1"]
                    - active["map_metrics"]["boundary_spectrum_l1"]
                )
                <= gates["prediction_reproduction_absolute_tolerance"]
                and abs(
                    theta_zero["boundary_bolometric_fraction"]
                    - active["map_metrics"]["boundary_bolometric_fraction"]
                )
                <= gates["prediction_reproduction_absolute_tolerance"],
                "selected_improvement_pass": selected["global_residual"]
                / theta_zero["global_residual"]
                < gates["selected_residual_ratio_to_current_below"],
                "selected_positive_pass": selected["minimum_current_intensity"]
                >= gates["minimum_intensity_at_least"]
                and selected["minimum_mapped_intensity"]
                >= gates["minimum_intensity_at_least"],
                "selected_boundary_pass": selected["boundary_spectrum_l1"]
                < gates["global_boundary_spectrum_l1_below"]
                and selected["boundary_bolometric_fraction"]
                < gates["global_boundary_bolometric_fraction_below"],
                "resources_pass": all(
                    float(row["peak_process_rss_mib"])
                    < gates["each_process_peak_rss_strictly_below_mib"]
                    and float(row["wall_runtime_s"])
                    < gates["line_worker_wall_time_strictly_below_s"]
                    for row in line_reports
                )
                and active["wall_runtime_s"]
                < gates["each_stage_wall_time_strictly_below_s"],
            }
            if not all(line_checks.values()):
                manifest["status"] = "line_gate_failed"
                manifest["failure_checks"] = line_checks
                _write_json_atomic(manifest_path, manifest)
                return _summary(protocol, manifest)
            old_hashes = []
            for index in range(76):
                start = index * 128
                stop = min((index + 1) * 128, shape[0])
                old_hashes.append(
                    base.phase7b9d._block_sha256(current, shape, start, stop)
                )
            manifest["active_stage"] = {
                "cycle": cycle,
                "stage": "write",
                "map_metrics": active["map_metrics"],
                "map_checks": active["map_checks"],
                "line_rows": rows,
                "line_checks": line_checks,
                "selected": selected,
                "scratch_state_sha256": active["scratch_state_sha256"],
                "old_current_block_sha256": old_hashes,
                "completed_blocks": [],
                "wall_runtime_s": 0.0,
            }
            _write_json_atomic(manifest_path, manifest)
            active = manifest["active_stage"]
        if active["stage"] == "write":
            if base._sha256(scratch) != active["scratch_state_sha256"]:
                raise RuntimeError("Phase 7B9ap write-stage scratch state changed")
            completed = {
                int(row["block_index"]): row for row in active["completed_blocks"]
            }
            for index, row in completed.items():
                start = index * 128
                stop = min((index + 1) * 128, shape[0])
                if (
                    base.phase7b9d._block_sha256(current, shape, start, stop)
                    != row["candidate_block_sha256"]
                ):
                    raise RuntimeError("Phase 7B9ap written candidate block changed")
            current_map = np.memmap(current, mode="r+", dtype=np.float64, shape=shape)
            scratch_map = np.memmap(scratch, mode="r", dtype=np.float64, shape=shape)
            theta = float(active["selected"]["theta"])
            started = time.perf_counter()
            for index in range(76):
                if index in completed:
                    continue
                start = index * 128
                stop = min((index + 1) * 128, shape[0])
                if (
                    base.phase7b9d._block_sha256(current, shape, start, stop)
                    != active["old_current_block_sha256"][index]
                ):
                    raise RuntimeError("Phase 7B9ap unwritten current block changed")
                old = np.array(current_map[start:stop], copy=True)
                candidate = old + theta * (np.asarray(scratch_map[start:stop]) - old)
                if not np.all(np.isfinite(candidate)) or np.any(candidate < 0.0):
                    raise ArithmeticError("Phase 7B9ap selected candidate became invalid")
                current_map[start:stop] = candidate
                current_map.flush()
                row = {
                    "block_index": index,
                    "candidate_block_sha256": base.phase7b9d._block_sha256(
                        current, shape, start, stop
                    ),
                    "minimum_candidate_intensity": float(np.min(candidate)),
                }
                active["completed_blocks"].append(row)
                active["completed_blocks"].sort(
                    key=lambda value: int(value["block_index"])
                )
                active["wall_runtime_s"] = float(active["wall_runtime_s"]) + (
                    time.perf_counter() - started
                )
                started = time.perf_counter()
                _write_json_atomic(manifest_path, manifest)
            del current_map, scratch_map
            if active["wall_runtime_s"] >= gates["write_wall_time_strictly_below_s"]:
                manifest["status"] = "write_resource_gate_failed"
                _write_json_atomic(manifest_path, manifest)
                return _summary(protocol, manifest)
            current_sha = base._sha256(current)
            record = {
                "cycle": cycle,
                "audited_input_residual": active["map_metrics"]["global_residual"],
                "audited_boundary_spectrum_l1": active["map_metrics"][
                    "boundary_spectrum_l1"
                ],
                "selected_theta": active["selected"]["theta"],
                "selected_predicted_residual": active["selected"]["global_residual"],
                "selected_residual_ratio": active["selected"]["global_residual"]
                / active["map_metrics"]["global_residual"],
                "selected_boundary_spectrum_l1": active["selected"][
                    "boundary_spectrum_l1"
                ],
                "selected_boundary_bolometric_fraction": active["selected"][
                    "boundary_bolometric_fraction"
                ],
                "map_gate_checks": active["map_checks"],
                "line_gate_checks": active["line_checks"],
                "candidate_state_sha256": current_sha,
                "write_wall_runtime_s": active["wall_runtime_s"],
            }
            manifest["cycles"].append(record)
            manifest["current_state_sha256"] = current_sha
            manifest["expected_residual"] = active["selected"]["global_residual"]
            manifest["expected_boundary_spectrum_l1"] = active["selected"][
                "boundary_spectrum_l1"
            ]
            manifest["expected_boundary_bolometric_fraction"] = active["selected"][
                "boundary_bolometric_fraction"
            ]
            manifest["active_stage"] = None
            _write_json_atomic(manifest_path, manifest)
            _summary(protocol, manifest)
            print(
                json.dumps(
                    {
                        "cycle": cycle,
                        "audited_input_residual": record["audited_input_residual"],
                        "selected_theta": record["selected_theta"],
                        "selected_predicted_residual": record[
                            "selected_predicted_residual"
                        ],
                        "selected_residual_ratio": record[
                            "selected_residual_ratio"
                        ],
                    }
                ),
                flush=True,
            )
    manifest["status"] = "maximum_cycles_exhausted"
    _write_json_atomic(manifest_path, manifest)
    return _summary(protocol, manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9ap_preregistered_accelerated_positive_iteration.json",
    )
    parser.add_argument("--map-worker", action="store_true")
    parser.add_argument("--line-worker", action="store_true")
    parser.add_argument("--cycle", type=int)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--current-state", type=Path)
    parser.add_argument("--current-sha256")
    parser.add_argument("--scratch-state", type=Path)
    parser.add_argument("--grid", type=Path)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--stop-after-map-cycle", type=int)
    args = parser.parse_args()
    if args.map_worker or args.line_worker:
        if (
            args.cycle is None
            or args.block_index is None
            or args.current_state is None
            or args.current_sha256 is None
            or args.scratch_state is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires cycle, block and both states")
        if args.map_worker:
            _run_map_worker(
                args.protocol,
                args.cycle,
                args.block_index,
                args.current_state,
                args.current_sha256,
                args.scratch_state,
                args.worker_report,
            )
        else:
            if args.grid is None:
                raise ValueError("line worker requires fixed grid")
            _run_line_worker(
                args.protocol,
                args.cycle,
                args.block_index,
                args.current_state,
                args.current_sha256,
                args.scratch_state,
                args.grid,
                args.worker_report,
            )
        return
    run(args.protocol, stop_after_map_cycle=args.stop_after_map_cycle)


if __name__ == "__main__":
    main()
