"""Phase 7B6o：从 I14 可恢复地执行 16 次全频 omega=2 续算。"""

from __future__ import annotations

import argparse
import hashlib
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

from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_split_mu_weights,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "d02de16d8d1f51892e727df12215373987a55d6cf18b7887758e1ce69be26938"
)
MIB = 1024**2


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


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B6o protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        source_path = ROOT / source["path"]
        if _sha256(source_path) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6o source changed: {source['path']}")
    return protocol


def _shape(protocol: dict[str, object]) -> tuple[int, int, int]:
    configuration = protocol["configuration"]
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _initial_manifest(
    protocol: dict[str, object], protocol_path: Path, manifest_path: Path
) -> dict[str, object]:
    initial = protocol["initial_checkpoint"]
    expected_size = int(initial["size_bytes_each"])
    state_path = ROOT / initial["state_path"]
    residual_path = ROOT / initial["residual_path"]
    if state_path.stat().st_size != expected_size:
        raise RuntimeError("Phase 7B6o initial state size changed")
    if residual_path.stat().st_size != expected_size:
        raise RuntimeError("Phase 7B6o initial residual size changed")
    free_bytes = shutil.disk_usage(manifest_path.parent).free
    # 两组交替状态和残差需要四个完整工作数组。
    required_bytes = 4 * expected_size
    if free_bytes <= required_bytes + 8 * 1024**3:
        raise OSError("insufficient disk space for recoverable Phase 7B6o arrays")
    manifest = {
        "phase": protocol["phase"],
        "protocol_path": str(protocol_path.relative_to(ROOT)),
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "status": "running",
        "current_global_iteration": int(initial["completed_source_maps"]),
        "current_state_path": initial["state_path"],
        "current_residual_path": initial["residual_path"],
        "history": [],
        "uncommitted_iteration": None,
    }
    _write_json_atomic(manifest_path, manifest)
    return manifest


def _load_or_create_manifest(
    protocol: dict[str, object], protocol_path: Path, manifest_path: Path
) -> dict[str, object]:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if not manifest_path.exists():
        return _initial_manifest(protocol, protocol_path, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["protocol_sha256"] != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("Phase 7B6o manifest belongs to another protocol")
    if manifest["status"] not in ("running", "gate_failed", "complete"):
        raise RuntimeError("Phase 7B6o manifest has an invalid status")
    return manifest


def _ensure_work_arrays(
    work_dir: Path, shape: tuple[int, int, int], expected_size: int
) -> tuple[list[Path], list[Path]]:
    states = [work_dir / "state_a.dat", work_dir / "state_b.dat"]
    residuals = [work_dir / "residual_a.dat", work_dir / "residual_b.dat"]
    for path in (*states, *residuals):
        if path.exists():
            if path.stat().st_size != expected_size:
                raise RuntimeError(f"Phase 7B6o work-array size changed: {path}")
            continue
        array = np.memmap(path, mode="w+", dtype=np.float64, shape=shape)
        array.flush()
        del array
    return states, residuals


def _validate_rows(
    reports: list[dict[str, object]],
    block_count: int,
    group_count: int,
) -> tuple[list[dict[str, object]], bool, float]:
    rows = sorted(
        [row for report in reports for row in report["rows"]],
        key=lambda row: row["core_group_start"],
    )
    coverage = bool(
        len(rows) == block_count
        and rows[0]["core_group_start"] == 0
        and rows[-1]["core_group_stop"] == group_count
        and all(
            first["core_group_stop"] == second["core_group_start"]
            for first, second in zip(rows[:-1], rows[1:], strict=True)
        )
    )
    maximum_absolute = max(row["maximum_absolute_change"] for row in rows)
    maximum_scale = max(row["maximum_scale"] for row in rows)
    residual = (
        maximum_absolute / maximum_scale
        if maximum_scale > 0.0
        else maximum_absolute
    )
    return rows, coverage, float(residual)


def _apply_fixed_weight_and_boundary_audit(
    current_path: Path,
    mapped_path: Path,
    shape: tuple[int, int, int],
    frequency_width: np.ndarray,
    mu: np.ndarray,
    angular_weight: np.ndarray,
    omega: float,
    chunk_groups: int,
) -> dict[str, float | bool]:
    current_map = np.memmap(current_path, mode="r", dtype=np.float64, shape=shape)
    mapped_map = np.memmap(mapped_path, mode="r+", dtype=np.float64, shape=shape)
    left = mu < 0.0
    right = mu > 0.0
    minimum = np.inf
    l1_numerator = 0.0
    l1_scale_current = 0.0
    l1_scale_next = 0.0
    bolometric_current = 0.0
    bolometric_next = 0.0
    for start in range(0, shape[0], chunk_groups):
        stop = min(start + chunk_groups, shape[0])
        current = np.asarray(current_map[start:stop])
        mapped = np.asarray(mapped_map[start:stop])
        accepted = current + omega * (mapped - current)
        if not np.all(np.isfinite(accepted)):
            raise ArithmeticError("Phase 7B6o accepted state is non-finite")
        local_minimum = float(np.min(accepted))
        if local_minimum < 0.0:
            raise ArithmeticError("Phase 7B6o omega=2 crossed the positivity boundary")
        minimum = min(minimum, local_minimum)
        # 用两侧边界单元的出射强度跟踪尚未收敛的观测相关泛函。
        current_flux = 2.0 * np.pi * (
            np.einsum(
                "m,gm->g",
                angular_weight[left] * np.abs(mu[left]),
                current[:, left, 0],
            )
            + np.einsum(
                "m,gm->g",
                angular_weight[right] * mu[right],
                current[:, right, -1],
            )
        )
        next_flux = 2.0 * np.pi * (
            np.einsum(
                "m,gm->g",
                angular_weight[left] * np.abs(mu[left]),
                accepted[:, left, 0],
            )
            + np.einsum(
                "m,gm->g",
                angular_weight[right] * mu[right],
                accepted[:, right, -1],
            )
        )
        width = frequency_width[start:stop]
        l1_numerator += float(np.sum(width * np.abs(next_flux - current_flux)))
        l1_scale_current += float(np.sum(width * np.abs(current_flux)))
        l1_scale_next += float(np.sum(width * np.abs(next_flux)))
        bolometric_current += float(np.sum(width * current_flux))
        bolometric_next += float(np.sum(width * next_flux))
        mapped_map[start:stop] = accepted
    mapped_map.flush()
    del mapped_map, current_map
    spectrum_l1 = l1_numerator / max(l1_scale_current, l1_scale_next)
    bolometric_fraction = abs(bolometric_next - bolometric_current) / max(
        abs(bolometric_current), abs(bolometric_next)
    )
    return {
        "all_finite_and_nonnegative": True,
        "minimum_intensity": float(minimum),
        "boundary_cell_flux_spectrum_l1": float(spectrum_l1),
        "boundary_cell_bolometric_fraction": float(bolometric_fraction),
        "boundary_cell_bolometric_current": float(bolometric_current),
        "boundary_cell_bolometric_next": float(bolometric_next),
    }


def _plot(path: Path, history: list[dict[str, object]]) -> None:
    iteration = [row["global_iteration"] for row in history]
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].semilogy(
        iteration,
        [row["raw_fixed_point_residual"] for row in history],
        "o-",
        color="#4c78a8",
    )
    axes[0, 0].set(
        xlabel="Global source-map count",
        ylabel="Raw fixed-point residual",
        title="(a) Fixed-point contraction",
    )
    axes[0, 1].semilogy(
        iteration,
        [row["boundary_cell_flux_spectrum_l1"] for row in history],
        "o-",
        color="#f58518",
        label="Spectral L1",
    )
    axes[0, 1].semilogy(
        iteration,
        [row["boundary_cell_bolometric_fraction"] for row in history],
        "s-",
        color="#54a24b",
        label="Bolometric",
    )
    axes[0, 1].axhline(1.0e-3, color="0.25", ls="--", label="Gate")
    axes[0, 1].set(
        xlabel="Global source-map count",
        ylabel="Successive-state change",
        title="(b) Boundary-cell flux proxy",
    )
    axes[0, 1].legend(frameon=False)
    axes[1, 0].bar(
        [str(value) for value in iteration],
        [row["wall_runtime_s"] for row in history],
        color="#72b7b2",
    )
    axes[1, 0].set(
        xlabel="Global source-map count",
        ylabel="Wall runtime (s)",
        title="(c) Recoverable iteration cost",
    )
    axes[1, 1].plot(
        iteration,
        [row["maximum_worker_peak_rss_mib"] for row in history],
        "o-",
        color="#e45756",
        label="Measured",
    )
    axes[1, 1].axhline(6144.0, color="0.25", ls="--", label="Process gate")
    axes[1, 1].set(
        xlabel="Global source-map count",
        ylabel="Peak RSS (MiB)",
        title="(d) Per-process memory",
    )
    axes[1, 1].legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    shape = _shape(protocol)
    expected_size = int(configuration["physical_frequency_groups"]) * int(
        configuration["angular_direction_count"]
    ) * int(configuration["radiation_depth_cell_count"]) * 8
    if expected_size != int(protocol["initial_checkpoint"]["size_bytes_each"]):
        raise ArithmeticError("Phase 7B6o declared shape and byte size disagree")
    work_dir = ROOT / configuration["work_directory"]
    manifest_path = ROOT / configuration["atomic_manifest"]
    manifest = _load_or_create_manifest(protocol, protocol_path, manifest_path)
    if manifest["status"] == "complete":
        return json.loads(
            (OUTPUT / "phase7b6o_fixed2_continuation_summary.json").read_text(
                encoding="utf-8"
            )
        )
    state_paths, residual_paths = _ensure_work_arrays(work_dir, shape, expected_size)
    h_protocol_path = ROOT / protocol["sources"]["phase7b6h_protocol"]["path"]
    h_protocol = json.loads(h_protocol_path.read_text(encoding="utf-8"))
    with np.load(
        ROOT / h_protocol["sources"]["phase7b5p_master_input"]["path"]
    ) as master:
        frequency_width = np.diff(np.array(master["active_edge_hz"], copy=True))
    if frequency_width.shape != (shape[0],) or np.any(frequency_width <= 0.0):
        raise ArithmeticError("Phase 7B6o active frequency widths are invalid")
    mu, angular_weight = gauss_legendre_split_mu_weights(shape[1], 0.0)
    start_iteration = int(protocol["initial_checkpoint"]["completed_source_maps"])
    final_iteration = start_iteration + int(
        configuration["additional_source_maps_exactly"]
    )
    process_count = int(configuration["process_count"])
    omega = float(configuration["accepted_weight_exactly"])
    while int(manifest["current_global_iteration"]) < final_iteration:
        current_iteration = int(manifest["current_global_iteration"])
        global_iteration = current_iteration + 1
        slot = (global_iteration - start_iteration - 1) % 2
        output_path = state_paths[slot]
        residual_output_path = residual_paths[slot]
        current_path = ROOT / manifest["current_state_path"]
        previous_residual_path = ROOT / manifest["current_residual_path"]
        if current_path.stat().st_size != expected_size:
            raise RuntimeError("Phase 7B6o current state size changed")
        if previous_residual_path.stat().st_size != expected_size:
            raise RuntimeError("Phase 7B6o current residual size changed")
        manifest["uncommitted_iteration"] = global_iteration
        _write_json_atomic(manifest_path, manifest)
        iteration_started = time.perf_counter()
        report_paths = []
        processes = []
        for worker_index in range(process_count):
            report_path = OUTPUT / (
                f"phase7b6o_iteration{global_iteration}_worker{worker_index + 1}.json"
            )
            report_paths.append(report_path)
            command = [
                sys.executable,
                str(ROOT / protocol["sources"]["phase7b6h_worker"]["path"]),
                "--worker",
                "--protocol",
                str(h_protocol_path),
                "--global-iteration",
                str(global_iteration),
                "--worker-index",
                str(worker_index),
                "--current-state",
                str(current_path),
                "--output-state",
                str(output_path),
                "--residual-output",
                str(residual_output_path),
                "--previous-residual",
                str(previous_residual_path),
                "--worker-report",
                str(report_path),
            ]
            processes.append(subprocess.Popen(command, cwd=ROOT))
        return_codes = [process.wait() for process in processes]
        if any(code != 0 for code in return_codes):
            raise RuntimeError(
                f"Phase 7B6o iteration {global_iteration} failed: {return_codes}"
            )
        reports = [
            json.loads(path.read_text(encoding="utf-8")) for path in report_paths
        ]
        rows, coverage, raw_residual = _validate_rows(
            reports,
            int(configuration["block_count"]),
            shape[0],
        )
        boundary = _apply_fixed_weight_and_boundary_audit(
            current_path,
            output_path,
            shape,
            frequency_width,
            mu,
            angular_weight,
            omega,
            int(configuration["core_frequency_groups"]),
        )
        entry = {
            "global_iteration": global_iteration,
            "block_count": len(rows),
            "unique_full_group_coverage": coverage,
            "raw_fixed_point_residual": raw_residual,
            "accepted_weight": omega,
            **boundary,
            "wall_runtime_s": time.perf_counter() - iteration_started,
            "maximum_worker_peak_rss_mib": max(
                report["peak_process_rss_mib"] for report in reports
            ),
            "worker_runtimes_s": [report["runtime_s"] for report in reports],
            "worker_report_paths": [str(path.relative_to(ROOT)) for path in report_paths],
        }
        manifest["history"].append(entry)
        manifest["current_global_iteration"] = global_iteration
        manifest["current_state_path"] = str(output_path.relative_to(ROOT))
        manifest["current_residual_path"] = str(
            residual_output_path.relative_to(ROOT)
        )
        manifest["uncommitted_iteration"] = None
        _write_json_atomic(manifest_path, manifest)
        print(
            json.dumps(
                {
                    "phase": "7B6o",
                    "iteration": global_iteration,
                    "raw_residual": raw_residual,
                    "boundary_spectrum_l1": boundary[
                        "boundary_cell_flux_spectrum_l1"
                    ],
                    "boundary_bolometric": boundary[
                        "boundary_cell_bolometric_fraction"
                    ],
                    "wall_runtime_s": entry["wall_runtime_s"],
                }
            ),
            flush=True,
        )
    history = manifest["history"]
    if len(history) != int(configuration["additional_source_maps_exactly"]):
        raise RuntimeError("Phase 7B6o manifest does not contain exactly 16 maps")
    final = history[-1]
    coverage_passed = all(
        row["block_count"] == gates["each_iteration_block_count_exactly"]
        and row["unique_full_group_coverage"]
        for row in history
    )
    state_passed = all(
        row["all_finite_and_nonnegative"] and row["minimum_intensity"] >= 0.0
        for row in history
    )
    boundary_passed = bool(
        final["boundary_cell_flux_spectrum_l1"]
        < gates["final_boundary_cell_flux_spectrum_l1_below"]
        and final["boundary_cell_bolometric_fraction"]
        < gates["final_boundary_cell_bolometric_fraction_below"]
    )
    resources_passed = all(
        row["maximum_worker_peak_rss_mib"]
        < gates["each_process_peak_rss_strictly_below_mib"]
        and row["wall_runtime_s"]
        < gates["each_iteration_wall_time_strictly_below_s"]
        for row in history
    )
    final_state_work = ROOT / manifest["current_state_path"]
    final_residual_work = ROOT / manifest["current_residual_path"]
    sizes_passed = bool(
        final_state_work.stat().st_size
        == gates["each_final_checkpoint_size_bytes_exactly"]
        and final_residual_work.stat().st_size
        == gates["each_final_checkpoint_size_bytes_exactly"]
    )
    all_primary_gates = bool(
        coverage_passed
        and state_passed
        and boundary_passed
        and resources_passed
        and sizes_passed
    )
    final_state_hash = None
    final_residual_hash = None
    final_state_path = None
    final_residual_path = None
    if all_primary_gates:
        final_state_hash = _sha256(final_state_work)
        final_residual_hash = _sha256(final_residual_work)
        declared_state = ROOT / configuration["final_state_path"]
        declared_residual = ROOT / configuration["final_residual_path"]
        for path in (declared_state, declared_residual):
            if path.exists():
                raise FileExistsError(f"refusing to overwrite final checkpoint: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(final_state_work, declared_state)
        os.replace(final_residual_work, declared_residual)
        final_state_path = str(declared_state.relative_to(ROOT))
        final_residual_path = str(declared_residual.relative_to(ROOT))
        manifest["current_state_path"] = final_state_path
        manifest["current_residual_path"] = final_residual_path
        manifest["status"] = "complete"
    else:
        manifest["status"] = "gate_failed"
    _write_json_atomic(manifest_path, manifest)
    decision = {
        "frozen_protocol_and_sources_passed": True,
        "exact_map_count_and_group_coverage_passed": coverage_passed,
        "all_states_nonnegative_and_finite": state_passed,
        "boundary_cell_flux_proxy_gate_passed": boundary_passed,
        "resource_and_runtime_gates_passed": resources_passed,
        "checkpoint_sizes_passed": sizes_passed,
        "phase7b6o_gate_passed": all_primary_gates,
        "final_formal_face_flux_audit_authorized": all_primary_gates,
        "fixed_material_science_functional_convergence": False,
        "matter_feedback_authorized": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "history": history,
        "final_state_path": final_state_path,
        "final_state_sha256": final_state_hash,
        "final_residual_path": final_residual_path,
        "final_residual_sha256": final_residual_hash,
        "recoverable_manifest_path": str(manifest_path.relative_to(ROOT)),
        "decision": decision,
        "figures": ["phase7b6o_fixed2_continuation.png"],
    }
    _write_json_atomic(
        OUTPUT / "phase7b6o_fixed2_continuation_summary.json", summary
    )
    _plot(OUTPUT / "phase7b6o_fixed2_continuation.png", history)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6o_preregistered_fixed2_continuation.json",
    )
    args = parser.parse_args()
    summary = run(args.protocol)
    print(json.dumps(summary["decision"], indent=2))


if __name__ == "__main__":
    main()
