"""Phase 7B5q：隔离进程测量完整固定点的单单元资源包络。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

import numpy as np

from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil_from_active_edges,
)

try:
    from scripts.phase7b5k_high_resolution_convergence import (
        _returned_array_bytes,
    )
    from scripts.phase7b5m_actual_multiresolution_validation import (
        _converged_p0_map,
    )
    from scripts.phase7b5m_actual_multiresolution_validation import (
        _edge_sha256,
    )
    from scripts.phase7b5p_isolated_resource_profile import (
        _result_sha256,
        ru_maxrss_to_bytes,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5k_high_resolution_convergence import (  # type: ignore[no-redef]
        _returned_array_bytes,
    )
    from phase7b5m_actual_multiresolution_validation import (  # type: ignore[no-redef]
        _converged_p0_map,
        _edge_sha256,
    )
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        _result_sha256,
        ru_maxrss_to_bytes,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "055005e2d3285744be531c06a0f08cea02f22de6af9979fce3dbc2d754b04143"
)
MIB_BYTES = 1024**2


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError("refusing to write an empty fixed-point resource table")
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256_file(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B5q protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        source_path = ROOT / source["path"]
        if _sha256_file(source_path) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B5q source changed: {source_path}")
    return protocol


def run_worker(
    input_path: Path,
    start_mode: str,
    output_path: Path,
    final_intensity_path: Path,
) -> None:
    with np.load(input_path) as payload:
        active_edge = np.array(payload["active_edge_hz"], copy=True)
        stencil = mixed_frame_frequency_stencil_from_active_edges(
            active_edge, float(payload["maximum_beta"])
        )
        old_edge = np.array(payload["old_edge"], copy=True)
        new_edge = np.array(payload["new_edge"], copy=True)
        mu = np.array(payload["mu"], copy=True)
        weight = np.array(payload["weight"], copy=True)
        state = {
            "beta": np.array(payload["beta"], copy=True),
            "temperature_k": float(payload["temperature_k"]),
            "density_g_cm3": float(payload["density_g_cm3"]),
            "hydrogen_fraction": np.array(
                payload["hydrogen_fraction"], copy=True
            ),
            "helium_fraction": np.array(payload["helium_fraction"], copy=True),
            "duration_s": float(payload["duration_s"]),
        }
        projected_source = np.array(payload["source_guess"], copy=True)
    if start_mode == "projected_converged":
        source_guess = projected_source
    elif start_mode == "default_initial":
        source_guess = None
    else:
        raise ValueError(f"unsupported start mode: {start_mode}")
    baseline = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    result = _converged_p0_map(
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        state,
        source_guess,
    )
    operator_runtime = time.perf_counter() - started
    peak = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "pid": os.getpid(),
        "platform": sys.platform,
        "start_mode": start_mode,
        "physical_group_count": stencil.physical_group_count,
        "active_edge_sha256": _edge_sha256(active_edge),
        "operator_runtime_s": operator_runtime,
        "baseline_highwater_rss_bytes": baseline,
        "peak_process_rss_bytes": peak,
        "operator_highwater_increase_bytes": max(0, peak - baseline),
        "returned_array_bytes": _returned_array_bytes(result),
        "fixed_point_iterations": result.fixed_point_iterations,
        "final_fixed_point_change": result.final_fixed_point_change,
        "fixed_point_converged": result.fixed_point_converged,
        "global_coupled_residual": (
            result.global_scale_normalized_coupled_residual
        ),
        "total_energy_ledger_residual": (
            result.total_relative_energy_ledger_residual
        ),
        "minimum_intensity": result.minimum_intensity,
        "result_sha256": _result_sha256(result),
    }
    np.save(final_intensity_path, result.final_lab_intensity_density)
    _write_json_atomic(output_path, report)


def _aggregate(
    rows: list[dict[str, object]], representation: str, start_mode: str
) -> dict[str, object]:
    selected = [
        row
        for row in rows
        if row["representation_key"] == representation
        and row["start_mode"] == start_mode
    ]
    peak = np.asarray([row["peak_process_rss_mib"] for row in selected])
    increase = np.asarray(
        [row["operator_highwater_increase_mib"] for row in selected]
    )
    runtime = np.asarray([row["operator_runtime_s"] for row in selected])
    iterations = np.asarray([row["fixed_point_iterations"] for row in selected])
    return {
        "repeat_count": len(selected),
        "median_peak_process_rss_mib": float(np.median(peak)),
        "maximum_peak_process_rss_mib": float(np.max(peak)),
        "median_operator_highwater_increase_mib": float(np.median(increase)),
        "maximum_operator_highwater_increase_mib": float(np.max(increase)),
        "median_operator_runtime_s": float(np.median(runtime)),
        "maximum_operator_runtime_s": float(np.max(runtime)),
        "fixed_point_iterations": sorted({int(value) for value in iterations}),
        "maximum_final_fixed_point_change": float(
            max(row["final_fixed_point_change"] for row in selected)
        ),
        "maximum_global_coupled_residual": float(
            max(row["global_coupled_residual"] for row in selected)
        ),
        "maximum_absolute_energy_ledger_residual": float(
            max(abs(row["total_energy_ledger_residual"]) for row in selected)
        ),
        "minimum_intensity": float(
            min(row["minimum_intensity"] for row in selected)
        ),
        "returned_array_mib": float(selected[0]["returned_array_mib"]),
        "active_edge_sha256": selected[0]["active_edge_sha256"],
        "result_sha256": selected[0]["result_sha256"],
    }


def _relative_array_difference(first: np.ndarray, second: np.ndarray) -> float:
    scale = max(float(np.max(np.abs(first))), float(np.max(np.abs(second))))
    difference = float(np.max(np.abs(first - second)))
    return difference / scale if scale > 0.0 else difference


def _plot(path: Path, rows: list[dict[str, object]]) -> None:
    import matplotlib.pyplot as plt

    configurations = (
        ("candidate", "projected_converged", "4816\nprojected"),
        ("candidate", "default_initial", "4816\ndefault"),
        ("master", "projected_converged", "9632\nprojected"),
        ("master", "default_initial", "9632\ndefault"),
    )
    colors = {"candidate": "tab:blue", "master": "tab:orange"}
    figure, axes = plt.subplots(
        1, 2, figsize=(10.0, 4.2), layout="constrained"
    )
    for index, (representation, start_mode, _) in enumerate(configurations):
        selected = [
            row
            for row in rows
            if row["representation_key"] == representation
            and row["start_mode"] == start_mode
        ]
        x = np.full(len(selected), index, dtype=float)
        axes[0].scatter(
            x,
            [row["peak_process_rss_mib"] for row in selected],
            color=colors[representation],
        )
        axes[1].scatter(
            x,
            [row["operator_runtime_s"] for row in selected],
            color=colors[representation],
        )
    labels = [configuration[2] for configuration in configurations]
    axes[0].set_ylabel("Converged-process peak RSS (MiB)")
    axes[1].set_ylabel("Full fixed-point time (s)")
    axes[0].set_title("Converged one-cell memory")
    axes[1].set_title("Converged one-cell runtime")
    for axis in axes:
        axis.set_xticks(range(len(labels)), labels)
        axis.grid(alpha=0.25, axis="y")
    figure.savefig(path, dpi=220)
    plt.close(figure)


def run_all(output_dir: Path, protocol_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5q_fixed_point_resource_summary.json",
        "rows": output_dir / "phase7b5q_fixed_point_resource_runs.csv",
        "figure": output_dir / "phase7b5q_fixed_point_resource.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    protocol = _load_protocol(protocol_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    representative_intensities: dict[tuple[str, str], np.ndarray] = {}
    with tempfile.TemporaryDirectory(prefix="phase7b5q-") as temporary:
        temporary_path = Path(temporary)
        for run_index, definition in enumerate(
            protocol["measurement"]["worker_order"]
        ):
            representation = definition["representation"]
            start_mode = definition["start_mode"]
            source_key = protocol["representations"][representation][
                "input_source"
            ]
            input_path = ROOT / protocol["sources"][source_key]["path"]
            worker_output = temporary_path / f"worker_{run_index}.json"
            intensity_output = temporary_path / f"intensity_{run_index}.npy"
            process = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker-input",
                    str(input_path),
                    "--worker-start-mode",
                    start_mode,
                    "--worker-output",
                    str(worker_output),
                    "--worker-intensity-output",
                    str(intensity_output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if process.returncode != 0:
                raise RuntimeError(
                    f"fixed-point resource worker failed: {process.stderr.strip()}"
                )
            worker = json.loads(worker_output.read_text(encoding="utf-8"))
            configuration = (representation, start_mode)
            final_intensity = np.load(intensity_output)
            if configuration not in representative_intensities:
                representative_intensities[configuration] = np.array(
                    final_intensity, copy=True
                )
            rows.append(
                {
                    "run_index": run_index,
                    "representation_key": representation,
                    "start_mode": start_mode,
                    "worker_pid": worker["pid"],
                    "physical_group_count": worker["physical_group_count"],
                    "active_edge_sha256": worker["active_edge_sha256"],
                    "operator_runtime_s": worker["operator_runtime_s"],
                    "baseline_highwater_rss_mib": (
                        worker["baseline_highwater_rss_bytes"] / MIB_BYTES
                    ),
                    "peak_process_rss_mib": (
                        worker["peak_process_rss_bytes"] / MIB_BYTES
                    ),
                    "operator_highwater_increase_mib": (
                        worker["operator_highwater_increase_bytes"] / MIB_BYTES
                    ),
                    "returned_array_mib": (
                        worker["returned_array_bytes"] / MIB_BYTES
                    ),
                    "fixed_point_iterations": worker["fixed_point_iterations"],
                    "final_fixed_point_change": worker[
                        "final_fixed_point_change"
                    ],
                    "fixed_point_converged": worker["fixed_point_converged"],
                    "global_coupled_residual": worker[
                        "global_coupled_residual"
                    ],
                    "total_energy_ledger_residual": worker[
                        "total_energy_ledger_residual"
                    ],
                    "minimum_intensity": worker["minimum_intensity"],
                    "result_sha256": worker["result_sha256"],
                }
            )
    aggregates = {
        representation: {
            start_mode: _aggregate(rows, representation, start_mode)
            for start_mode in protocol["start_modes"]
        }
        for representation in protocol["representations"]
    }
    cross_start = {
        representation: _relative_array_difference(
            representative_intensities[(representation, "projected_converged")],
            representative_intensities[(representation, "default_initial")],
        )
        for representation in protocol["representations"]
    }
    pids = [row["worker_pid"] for row in rows]
    result_hashes = {
        (representation, start_mode): {
            row["result_sha256"]
            for row in rows
            if row["representation_key"] == representation
            and row["start_mode"] == start_mode
        }
        for representation in protocol["representations"]
        for start_mode in protocol["start_modes"]
    }
    gates = protocol["gates"]
    decision = {
        "frozen_protocol_hash_passed": True,
        "frozen_source_hashes_passed": True,
        "all_workers_exit_zero": len(rows)
        == len(protocol["measurement"]["worker_order"]),
        "fresh_worker_pid_each_run": len(set(pids)) == len(pids),
        "all_fixed_points_converged": all(
            row["fixed_point_converged"] for row in rows
        ),
        "all_global_coupled_residuals_passed": all(
            row["global_coupled_residual"]
            < gates["global_coupled_residual_strictly_below"]
            for row in rows
        ),
        "all_energy_ledger_residuals_passed": all(
            abs(row["total_energy_ledger_residual"])
            < gates["energy_ledger_residual_strictly_below"]
            for row in rows
        ),
        "all_intensities_nonnegative": all(
            row["minimum_intensity"] >= gates["minimum_intensity_at_least"]
            for row in rows
        ),
        "cross_start_final_intensity_passed": all(
            value
            < gates[
                "cross_start_final_intensity_relative_difference_strictly_below"
            ]
            for value in cross_start.values()
        ),
        "deterministic_result_hash_within_configuration": all(
            len(value) == 1 for value in result_hashes.values()
        ),
        "edge_hashes_unchanged": all(
            row["active_edge_sha256"]
            == protocol["representations"][row["representation_key"]][
                "active_edge_sha256"
            ]
            for row in rows
        ),
        **protocol["authorization"],
    }
    required = (
        "frozen_protocol_hash_passed",
        "frozen_source_hashes_passed",
        "all_workers_exit_zero",
        "fresh_worker_pid_each_run",
        "all_fixed_points_converged",
        "all_global_coupled_residuals_passed",
        "all_energy_ledger_residuals_passed",
        "all_intensities_nonnegative",
        "cross_start_final_intensity_passed",
        "deterministic_result_hash_within_configuration",
        "edge_hashes_unchanged",
    )
    if not all(decision[key] for key in required):
        raise RuntimeError(f"Phase 7B5q fixed-point resource gate failed: {decision}")
    ratios = {
        start_mode: {
            "master_to_candidate_median_peak_rss_ratio": (
                aggregates["master"][start_mode][
                    "median_peak_process_rss_mib"
                ]
                / aggregates["candidate"][start_mode][
                    "median_peak_process_rss_mib"
                ]
            ),
            "master_to_candidate_median_highwater_increase_ratio": (
                aggregates["master"][start_mode][
                    "median_operator_highwater_increase_mib"
                ]
                / aggregates["candidate"][start_mode][
                    "median_operator_highwater_increase_mib"
                ]
            ),
            "master_to_candidate_median_runtime_ratio": (
                aggregates["master"][start_mode]["median_operator_runtime_s"]
                / aggregates["candidate"][start_mode][
                    "median_operator_runtime_s"
                ]
            ),
        }
        for start_mode in protocol["start_modes"]
    }
    report = {
        "phase": "7B5q converged fixed-point resource envelope",
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_path": str(protocol_path),
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "platform": sys.platform,
        "stress_state": protocol["stress_state"],
        "runs": rows,
        "aggregate": aggregates,
        "cross_start_final_intensity_relative_difference": cross_start,
        "ratios": ratios,
        "decision": decision,
        "interpretation": (
            "Each worker measures a fully converged one-cell fixed point at frozen "
            "8-direction angular order and the Phase 7B5o exposed stress state. "
            "The audit "
            "brackets a projected-converged warm start and the operator default "
            "initial field. It is not a full-column, angular, radiation-subgrid, "
            "orbit, or matter-feedback gate and does not change the frequency budget."
        ),
        "figure": paths["figure"].name,
    }
    _write_csv(paths["rows"], rows)
    _plot(paths["figure"], rows)
    _write_json_atomic(paths["summary"], report)
    print(
        json.dumps(
            {
                "aggregate": aggregates,
                "cross_start": cross_start,
                "ratios": ratios,
                "decision": decision,
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            OUTPUT / "phase7b5q_preregistered_fixed_point_resource_protocol.json"
        ),
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--worker-input", type=Path)
    parser.add_argument("--worker-start-mode")
    parser.add_argument("--worker-output", type=Path)
    parser.add_argument("--worker-intensity-output", type=Path)
    args = parser.parse_args()
    worker_arguments = (
        args.worker_input,
        args.worker_start_mode,
        args.worker_output,
        args.worker_intensity_output,
    )
    if any(value is not None for value in worker_arguments):
        if any(value is None for value in worker_arguments):
            raise ValueError("all fixed-point worker arguments must be supplied")
        run_worker(
            args.worker_input,
            args.worker_start_mode,
            args.worker_output,
            args.worker_intensity_output,
        )
        return
    run_all(args.output_dir, args.protocol, force=args.force)


if __name__ == "__main__":
    main()
