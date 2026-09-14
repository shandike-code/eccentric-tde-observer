"""Phase 7B9d：当前物质基点上的可恢复全频辐射内迭代。"""

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

from eccentric_tde_observer.full_frequency_residual_evaluation import (
    FullFrequencyResidualFidelity,
    FullFrequencyResidualStatus,
    RecoverableFullFrequencyResidualEvaluation,
    build_full_frequency_residual_request,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_split_mu_weights,
)

try:
    from scripts import phase7b7i_second_radiation_map as phase7b7i
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b7i_second_radiation_map as phase7b7i  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "812febafdc66a072c11ad00638034773bbb6c7dc39cd1e58a83551b26c0f59df"
)


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
        raise RuntimeError("frozen Phase 7B9d protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or _sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(f"frozen Phase 7B9d source changed: {source['path']}")
    return protocol


def _shape(protocol: dict[str, object]) -> tuple[int, int, int]:
    configuration = protocol["configuration"]
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def _template_protocol(
    protocol: dict[str, object], current_state_path: Path
) -> dict[str, object]:
    template = json.loads(
        (ROOT / protocol["sources"]["phase7b7i_template_protocol"]["path"]).read_text()
    )
    template["sources"]["initial_radiation_state"]["path"] = _relative(
        current_state_path
    )
    template["sources"]["second_material_iterate"] = dict(
        protocol["sources"]["current_material_state"]
    )
    return template


def _configure_worker(
    protocol: dict[str, object], current_state_path: Path
) -> None:
    template = _template_protocol(protocol, current_state_path)
    phase7b7i._load_protocol = lambda _path, validate_sources=False: template


def _block_sha256(
    path: Path,
    shape: tuple[int, int, int],
    group_start: int,
    group_stop: int,
) -> str:
    plane_bytes = shape[1] * shape[2] * np.dtype(np.float64).itemsize
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        stream.seek(group_start * plane_bytes)
        remaining = (group_stop - group_start) * plane_bytes
        while remaining:
            block = stream.read(min(16 * 1024 * 1024, remaining))
            if not block:
                raise RuntimeError("Phase 7B9d checkpoint ended inside a block")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


def _ensure_work_arrays(
    work_directory: Path,
    shape: tuple[int, int, int],
    expected_size: int,
    *,
    allow_existing: bool,
) -> tuple[Path, Path]:
    work_directory.mkdir(parents=True, exist_ok=True)
    paths = (work_directory / "state_a.dat", work_directory / "state_b.dat")
    for path in paths:
        if path.exists():
            if not allow_existing:
                raise FileExistsError(f"refusing stale Phase 7B9d work array: {path}")
            if path.stat().st_size != expected_size:
                raise RuntimeError(f"Phase 7B9d work-array size changed: {path}")
            continue
        array = np.memmap(path, mode="w+", dtype=np.float64, shape=shape)
        array.flush()
        del array
    return paths


def _new_inner_manifest(
    protocol: dict[str, object],
    protocol_path: Path,
    manifest_path: Path,
    shape: tuple[int, int, int],
) -> dict[str, object]:
    configuration = protocol["configuration"]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    expected_size = int(configuration["raw_float64_checkpoint_size_bytes"])
    initial = ROOT / protocol["sources"]["initial_radiation_checkpoint"]["path"]
    if initial.stat().st_size != expected_size:
        raise RuntimeError("Phase 7B9d initial checkpoint size changed")
    required = 2 * expected_size + int(
        protocol["gates"]["minimum_free_bytes_after_allocations"]
    )
    if shutil.disk_usage(manifest_path.parent).free <= required:
        raise OSError("insufficient disk space for recoverable Phase 7B9d arrays")
    work_directory = ROOT / configuration["work_directory"]
    _ensure_work_arrays(
        work_directory, shape, expected_size, allow_existing=False
    )
    manifest: dict[str, object] = {
        "phase": protocol["phase"],
        "protocol_path": _relative(protocol_path),
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "status": "running",
        "current_additional_map": 0,
        "current_state_path": _relative(initial),
        "current_state_sha256": protocol["sources"]["initial_radiation_checkpoint"][
            "sha256"
        ],
        "history": [],
        "uncommitted_iteration": None,
    }
    _write_json_atomic(manifest_path, manifest)
    return manifest


def _load_or_create_inner_manifest(
    protocol: dict[str, object],
    protocol_path: Path,
    manifest_path: Path,
    shape: tuple[int, int, int],
) -> dict[str, object]:
    if not manifest_path.exists():
        return _new_inner_manifest(
            protocol, protocol_path, manifest_path, shape
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("Phase 7B9d manifest belongs to another protocol")
    if manifest.get("status") not in ("running", "complete", "gate_failed"):
        raise RuntimeError("Phase 7B9d manifest status is invalid")
    expected_size = int(protocol["configuration"]["raw_float64_checkpoint_size_bytes"])
    _ensure_work_arrays(
        ROOT / protocol["configuration"]["work_directory"],
        shape,
        expected_size,
        allow_existing=True,
    )
    current_path = ROOT / manifest["current_state_path"]
    if (
        current_path.stat().st_size != expected_size
        or _sha256(current_path) != manifest["current_state_sha256"]
    ):
        raise RuntimeError("Phase 7B9d committed current state changed")
    uncommitted = manifest.get("uncommitted_iteration")
    if uncommitted is not None:
        output_path = ROOT / uncommitted["output_state_path"]
        for record in uncommitted["completed_blocks"]:
            digest = _block_sha256(
                output_path,
                shape,
                int(record["core_group_start"]),
                int(record["core_group_stop"]),
            )
            if digest != record["sha256"]:
                raise RuntimeError(
                    f"Phase 7B9d completed block changed: {record['block_index']}"
                )
    return manifest


def _boundary_flux_change(
    current_path: Path,
    next_path: Path,
    shape: tuple[int, int, int],
    frequency_width: np.ndarray,
) -> tuple[float, float, float, float]:
    mu, weight = gauss_legendre_split_mu_weights(shape[1], 0.0)
    left = mu < 0.0
    right = mu > 0.0
    current_map = np.memmap(current_path, mode="r", dtype=np.float64, shape=shape)
    next_map = np.memmap(next_path, mode="r", dtype=np.float64, shape=shape)
    numerator = 0.0
    current_scale = 0.0
    next_scale = 0.0
    current_bolometric = 0.0
    next_bolometric = 0.0
    for start in range(0, shape[0], 64):
        stop = min(start + 64, shape[0])
        current = np.asarray(current_map[start:stop])
        following = np.asarray(next_map[start:stop])
        current_flux = 2.0 * np.pi * (
            np.einsum(
                "m,gm->g",
                weight[left] * np.abs(mu[left]),
                current[:, left, 0],
            )
            + np.einsum(
                "m,gm->g",
                weight[right] * mu[right],
                current[:, right, -1],
            )
        )
        next_flux = 2.0 * np.pi * (
            np.einsum(
                "m,gm->g",
                weight[left] * np.abs(mu[left]),
                following[:, left, 0],
            )
            + np.einsum(
                "m,gm->g",
                weight[right] * mu[right],
                following[:, right, -1],
            )
        )
        width = frequency_width[start:stop]
        numerator += float(np.sum(width * np.abs(next_flux - current_flux)))
        current_scale += float(np.sum(width * np.abs(current_flux)))
        next_scale += float(np.sum(width * np.abs(next_flux)))
        current_bolometric += float(np.sum(width * current_flux))
        next_bolometric += float(np.sum(width * next_flux))
    del current_map, next_map
    spectrum_l1 = numerator / max(current_scale, next_scale)
    bolometric_fraction = abs(next_bolometric - current_bolometric) / max(
        abs(current_bolometric), abs(next_bolometric)
    )
    return (
        float(spectrum_l1),
        float(bolometric_fraction),
        float(current_bolometric),
        float(next_bolometric),
    )


def _iteration_converged(row: dict[str, object], gates: dict[str, object]) -> bool:
    return bool(
        row["raw_source_map_residual"] < gates["raw_source_map_residual_below"]
        and row["boundary_flux_spectrum_l1"]
        < gates["boundary_flux_spectrum_l1_below"]
        and row["boundary_flux_bolometric_fraction"]
        < gates["boundary_flux_bolometric_fraction_below"]
        and row["maximum_internal_energy_ledger_residual"]
        < gates["maximum_internal_energy_ledger_residual_below"]
        and row["minimum_mapped_intensity"] >= gates["minimum_intensity_at_least"]
        and row["block_count"] == gates["each_iteration_block_count_exactly"]
        and row["owned_frequency_group_count"]
        == gates["each_iteration_owned_frequency_groups_exactly"]
        and row["maximum_process_peak_rss_mib"]
        < gates["each_process_peak_rss_strictly_below_mib"]
        and row["wall_runtime_s"]
        < gates["each_iteration_wall_time_strictly_below_s"]
    )


def _consecutive_passes(history: list[dict[str, object]], gates: dict[str, object]) -> int:
    count = 0
    for row in reversed(history):
        if not _iteration_converged(row, gates):
            break
        count += 1
    return count


def _run_one_iteration(
    protocol: dict[str, object],
    protocol_path: Path,
    manifest_path: Path,
    manifest: dict[str, object],
    shape: tuple[int, int, int],
    frequency_width: np.ndarray,
    *,
    worker_protocol_path: Path | None = None,
) -> dict[str, object]:
    configuration = protocol["configuration"]
    current_iteration = int(manifest["current_additional_map"])
    next_iteration = current_iteration + 1
    work_directory = ROOT / configuration["work_directory"]
    output_path = work_directory / ("state_a.dat" if next_iteration % 2 == 1 else "state_b.dat")
    current_path = ROOT / manifest["current_state_path"]
    uncommitted = manifest.get("uncommitted_iteration")
    if uncommitted is None:
        uncommitted = {
            "additional_map": next_iteration,
            "current_state_path": _relative(current_path),
            "current_state_sha256": manifest["current_state_sha256"],
            "output_state_path": _relative(output_path),
            "completed_blocks": [],
            "accumulated_wall_runtime_s": 0.0,
        }
        manifest["uncommitted_iteration"] = uncommitted
        _write_json_atomic(manifest_path, manifest)
    elif (
        int(uncommitted["additional_map"]) != next_iteration
        or ROOT / uncommitted["output_state_path"] != output_path
    ):
        raise RuntimeError("Phase 7B9d uncommitted iteration is inconsistent")
    completed = {
        int(record["block_index"]): record
        for record in uncommitted["completed_blocks"]
    }
    reports_directory = work_directory / "reports"
    reports_directory.mkdir(exist_ok=True)
    pending = [
        index for index in range(int(configuration["block_count"])) if index not in completed
    ]
    concurrency = int(configuration["maximum_concurrent_processes"])
    for offset in range(0, len(pending), concurrency):
        batch_started = time.perf_counter()
        batch = pending[offset : offset + concurrency]
        processes = []
        report_paths = []
        for block_index in batch:
            report_path = reports_directory / (
                f"map{next_iteration:02d}_block{block_index:02d}.json"
            )
            report_paths.append(report_path)
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--worker",
                        "--protocol",
                        str(
                            protocol_path
                            if worker_protocol_path is None
                            else worker_protocol_path
                        ),
                        "--current-state",
                        str(current_path),
                        "--block-index",
                        str(block_index),
                        "--output-state",
                        str(output_path),
                        "--worker-report",
                        str(report_path),
                    ],
                    cwd=ROOT,
                )
            )
        return_codes = [process.wait() for process in processes]
        if any(code != 0 for code in return_codes):
            raise RuntimeError(f"Phase 7B9d worker batch failed: {return_codes}")
        for block_index, report_path in zip(batch, report_paths, strict=True):
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if int(report["block_index"]) != block_index:
                raise RuntimeError("Phase 7B9d worker report block changed")
            report["sha256"] = _block_sha256(
                output_path,
                shape,
                int(report["core_group_start"]),
                int(report["core_group_stop"]),
            )
            uncommitted["completed_blocks"].append(report)
        uncommitted["completed_blocks"].sort(
            key=lambda row: int(row["block_index"])
        )
        uncommitted["accumulated_wall_runtime_s"] = float(
            uncommitted["accumulated_wall_runtime_s"]
        ) + (time.perf_counter() - batch_started)
        _write_json_atomic(manifest_path, manifest)
        completed_count = len(uncommitted["completed_blocks"])
        if completed_count % 10 == 0 or completed_count == int(
            configuration["block_count"]
        ):
            print(
                json.dumps(
                    {
                        "additional_map": next_iteration,
                        "completed_blocks": completed_count,
                        "total_blocks": int(configuration["block_count"]),
                    }
                ),
                flush=True,
            )
    postprocessing_started = time.perf_counter()
    reports = list(uncommitted["completed_blocks"])
    ownership = np.zeros(shape[0], dtype=np.int64)
    for report in reports:
        ownership[
            int(report["core_group_start"]) : int(report["core_group_stop"])
        ] += 1
    maximum_change = max(float(row["maximum_absolute_radiation_change"]) for row in reports)
    maximum_scale = max(float(row["maximum_radiation_scale"]) for row in reports)
    raw_residual = maximum_change / maximum_scale if maximum_scale > 0.0 else maximum_change
    spectrum_l1, bolometric_fraction, bolometric_current, bolometric_next = (
        _boundary_flux_change(current_path, output_path, shape, frequency_width)
    )
    output_sha = _sha256(output_path)
    row: dict[str, object] = {
        "additional_map": next_iteration,
        "total_source_maps_at_current_material": int(
            configuration["initial_source_maps_at_current_material"]
        )
        + next_iteration,
        "block_count": len(reports),
        "owned_frequency_group_count": int(np.sum(ownership)),
        "ownership_exactly_once": bool(np.all(ownership == 1)),
        "raw_source_map_residual": float(raw_residual),
        "boundary_flux_spectrum_l1": spectrum_l1,
        "boundary_flux_bolometric_fraction": bolometric_fraction,
        "boundary_flux_bolometric_current": bolometric_current,
        "boundary_flux_bolometric_next": bolometric_next,
        "minimum_mapped_intensity": min(
            float(report["minimum_mapped_intensity"]) for report in reports
        ),
        "maximum_internal_energy_ledger_residual": max(
            float(report["internal_total_energy_ledger_residual"]) for report in reports
        ),
        "maximum_process_peak_rss_mib": max(
            float(report["peak_process_rss_mib"]) for report in reports
        ),
        "wall_runtime_s": float(uncommitted["accumulated_wall_runtime_s"])
        + (time.perf_counter() - postprocessing_started),
        "output_state_path": _relative(output_path),
        "output_state_sha256": output_sha,
    }
    manifest["current_additional_map"] = next_iteration
    manifest["current_state_path"] = _relative(output_path)
    manifest["current_state_sha256"] = output_sha
    manifest["history"].append(row)
    manifest["uncommitted_iteration"] = None
    _write_json_atomic(manifest_path, manifest)
    print(json.dumps({"committed_iteration": row}, indent=2), flush=True)
    return row


def _finalize_residual_manifest(
    protocol: dict[str, object],
    protocol_path: Path,
    history: list[dict[str, object]],
) -> RecoverableFullFrequencyResidualEvaluation:
    configuration = protocol["configuration"]
    shape = _shape(protocol)
    ranges = tuple(
        (
            start,
            min(start + int(configuration["core_frequency_groups"]), shape[0]),
        )
        for start in range(0, shape[0], int(configuration["core_frequency_groups"]))
    )
    request = build_full_frequency_residual_request(
        ROOT,
        evaluation_id="phase7b9d-base-state",
        fidelity=FullFrequencyResidualFidelity.INNER_CONVERGED_RADIATION,
        encoded_unknown_count=int(configuration["encoded_unknown_count"]),
        radiation_shape=shape,
        frequency_block_ranges=ranges,
        radiation_output_path=ROOT / configuration["final_radiation_output"],
        radiation_inner_residual_tolerance=float(
            protocol["gates"]["raw_source_map_residual_below"]
        ),
        input_artifact_paths={
            "frozen_protocol": protocol_path,
            "encoded_material_state": ROOT
            / protocol["sources"]["encoded_material_state"]["path"],
            "decoded_material_state": ROOT
            / protocol["sources"]["current_material_state"]["path"],
            "physical_old_time_level": ROOT
            / protocol["sources"]["physical_old_time_level"]["path"],
            "initial_radiation_checkpoint": ROOT
            / protocol["sources"]["initial_radiation_checkpoint"]["path"],
        },
    )
    manifest_path = ROOT / configuration["residual_manifest"]
    if manifest_path.exists():
        evaluation = RecoverableFullFrequencyResidualEvaluation.resume(
            ROOT, manifest_path
        )
        if evaluation.status is not FullFrequencyResidualStatus.RADIATION_COMPLETE:
            raise RuntimeError("Phase 7B9d residual manifest has an unexpected status")
        return evaluation
    evaluation = RecoverableFullFrequencyResidualEvaluation.create(
        ROOT, manifest_path, request
    )
    evaluation.start_radiation()
    for block_index in range(len(ranges)):
        evaluation.mark_frequency_block_complete(block_index)
    final = history[-1]
    gates = protocol["gates"]
    science_passed = bool(
        _consecutive_passes(history, gates)
        >= int(configuration["minimum_consecutive_converged_maps"])
        and final["boundary_flux_spectrum_l1"]
        < gates["boundary_flux_spectrum_l1_below"]
        and final["boundary_flux_bolometric_fraction"]
        < gates["boundary_flux_bolometric_fraction_below"]
    )
    evaluation.complete_radiation(
        inner_iteration_count=int(final["total_source_maps_at_current_material"]),
        inner_residual_norm=float(final["raw_source_map_residual"]),
        inner_converged=True,
        science_functionals_passed=science_passed,
        wall_runtime_s=float(sum(row["wall_runtime_s"] for row in history)),
    )
    return evaluation


def _plot(path: Path, history: list[dict[str, object]], gates: dict[str, object]) -> None:
    iteration = np.array([row["total_source_maps_at_current_material"] for row in history])
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.1), constrained_layout=True)
    axes[0, 0].semilogy(
        iteration,
        [row["raw_source_map_residual"] for row in history],
        "o-",
    )
    axes[0, 0].axhline(
        gates["raw_source_map_residual_below"], color="0.25", ls="--", label="Inner gate"
    )
    axes[0, 0].set(
        xlabel="Total source maps at fixed material",
        ylabel="Raw radiation fixed-point residual",
        title="(a) Fixed-material inner convergence",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].semilogy(
        iteration,
        [row["boundary_flux_spectrum_l1"] for row in history],
        "o-",
        label="Spectral L1",
    )
    axes[0, 1].semilogy(
        iteration,
        [row["boundary_flux_bolometric_fraction"] for row in history],
        "s-",
        label="Bolometric",
    )
    axes[0, 1].axhline(1.0e-3, color="0.25", ls="--", label="Science gate")
    axes[0, 1].set(
        xlabel="Total source maps at fixed material",
        ylabel="Successive boundary-flux change",
        title="(b) Observer-facing science functionals",
    )
    axes[0, 1].legend(frameon=False)
    axes[1, 0].bar(
        iteration.astype(str),
        [row["wall_runtime_s"] for row in history],
        color="#6f9f91",
    )
    axes[1, 0].set(
        xlabel="Total source maps at fixed material",
        ylabel="Wall runtime (s)",
        title="(c) Recoverable full-frequency cost",
    )
    axes[1, 1].plot(
        iteration,
        [row["maximum_process_peak_rss_mib"] for row in history],
        "o-",
        label="Measured",
    )
    axes[1, 1].axhline(6144.0, color="0.25", ls="--", label="Process gate")
    axes[1, 1].set(
        xlabel="Total source maps at fixed material",
        ylabel="Peak process RSS (MiB)",
        title="(d) Short-lived worker resources",
    )
    axes[1, 1].legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    shape = _shape(protocol)
    expected_size = int(np.prod(shape, dtype=np.int64) * np.dtype(np.float64).itemsize)
    if expected_size != int(configuration["raw_float64_checkpoint_size_bytes"]):
        raise ArithmeticError("Phase 7B9d shape and checkpoint size disagree")
    with np.load(ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]) as master:
        frequency_width = np.diff(np.array(master["active_edge_hz"], copy=True))
    if frequency_width.shape != (shape[0],) or np.any(frequency_width <= 0.0):
        raise ArithmeticError("Phase 7B9d frequency widths are invalid")
    manifest_path = ROOT / configuration["inner_manifest"]
    manifest = _load_or_create_inner_manifest(
        protocol, protocol_path, manifest_path, shape
    )
    if manifest["status"] == "complete":
        return json.loads(
            (OUTPUT / "phase7b9d_inner_converged_base_radiation_summary.json").read_text()
        )
    if manifest["status"] == "gate_failed":
        raise RuntimeError("Phase 7B9d exhausted the preregistered map budget")
    maximum_maps = int(configuration["maximum_additional_source_maps"])
    while int(manifest["current_additional_map"]) < maximum_maps:
        _run_one_iteration(
            protocol,
            protocol_path,
            manifest_path,
            manifest,
            shape,
            frequency_width,
        )
        consecutive = _consecutive_passes(manifest["history"], gates)
        even = int(manifest["current_additional_map"]) % 2 == 0
        if consecutive >= int(configuration["minimum_consecutive_converged_maps"]) and (
            not configuration["stop_only_after_even_additional_map"] or even
        ):
            break
    history = manifest["history"]
    consecutive = _consecutive_passes(history, gates)
    converged = bool(
        consecutive >= int(configuration["minimum_consecutive_converged_maps"])
        and int(manifest["current_additional_map"]) % 2 == 0
    )
    if not converged:
        manifest["status"] = "gate_failed"
        _write_json_atomic(manifest_path, manifest)
    else:
        if manifest["current_state_path"] != configuration["final_radiation_output"]:
            raise RuntimeError("Phase 7B9d final state did not land in the frozen slot")
        evaluation = _finalize_residual_manifest(protocol, protocol_path, history)
        if evaluation.status is not FullFrequencyResidualStatus.RADIATION_COMPLETE:
            raise RuntimeError("Phase 7B9d recoverable residual did not reach radiation complete")
        manifest["status"] = "complete"
        _write_json_atomic(manifest_path, manifest)
    figure_path = OUTPUT / "phase7b9d_inner_converged_base_radiation.png"
    _plot(figure_path, history, gates)
    final = history[-1]
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "phase_index": int(configuration["phase_index"]),
        "additional_source_maps": int(manifest["current_additional_map"]),
        "total_source_maps_at_current_material": int(
            final["total_source_maps_at_current_material"]
        ),
        "consecutive_converged_maps": consecutive,
        "final_raw_source_map_residual": final["raw_source_map_residual"],
        "final_boundary_flux_spectrum_l1": final["boundary_flux_spectrum_l1"],
        "final_boundary_flux_bolometric_fraction": final[
            "boundary_flux_bolometric_fraction"
        ],
        "minimum_mapped_intensity": min(
            row["minimum_mapped_intensity"] for row in history
        ),
        "maximum_internal_energy_ledger_residual": max(
            row["maximum_internal_energy_ledger_residual"] for row in history
        ),
        "maximum_process_peak_rss_mib": max(
            row["maximum_process_peak_rss_mib"] for row in history
        ),
        "total_iteration_wall_runtime_s": float(
            sum(row["wall_runtime_s"] for row in history)
        ),
        "final_radiation_path": manifest["current_state_path"],
        "final_radiation_sha256": manifest["current_state_sha256"],
        "residual_manifest_path": configuration["residual_manifest"],
        "decision": {
            "frozen_sources_passed": True,
            "full_frequency_inner_radiation_converged": converged,
            "two_consecutive_map_gate_passed": consecutive
            >= int(configuration["minimum_consecutive_converged_maps"]),
            "boundary_science_functionals_passed": bool(
                final["boundary_flux_spectrum_l1"]
                < gates["boundary_flux_spectrum_l1_below"]
                and final["boundary_flux_bolometric_fraction"]
                < gates["boundary_flux_bolometric_fraction_below"]
            ),
            "recoverable_radiation_manifest_complete": converged,
            "formal_feedback_evaluated": False,
            "encoded_newton_residual_evaluated": False,
            "full_frequency_jv_evaluated": False,
            "accepted_as_dynamic_NLTE_solution": False,
            "full_orbit_authorized": False,
            "phase4_replacement_authorized": False,
            "uvot_authorized": False,
            "phase7b9d_gate_passed": converged,
            "formal_feedback_and_encoded_residual_authorized": converged,
        },
        "history": history,
        "figures": [figure_path.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9d_inner_converged_base_radiation_summary.json", report
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9d_preregistered_inner_converged_base_radiation.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--current-state", type=Path)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if any(
            value is None
            for value in (
                args.current_state,
                args.block_index,
                args.output_state,
                args.worker_report,
            )
        ):
            raise ValueError("Phase 7B9d worker arguments are incomplete")
        protocol = _load_protocol(args.protocol, validate_sources=False)
        _configure_worker(protocol, args.current_state)
        phase7b7i.run_worker(
            args.protocol,
            args.block_index,
            args.output_state,
            args.worker_report,
        )
        return
    print(json.dumps(run(args.protocol), indent=2))


if __name__ == "__main__":
    main()
