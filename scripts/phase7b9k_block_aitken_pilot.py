"""Phase 7B9k：在自然频率块上执行可恢复的有限 Aitken 加速试验。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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
    from scripts import phase7b9d_inner_converged_base_radiation as phase7b9d
    from scripts import phase7b9i_finite_trial_radiation as phase7b9i
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9d_inner_converged_base_radiation as phase7b9d  # type: ignore[no-redef]
    import phase7b9i_finite_trial_radiation as phase7b9i  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "af4f6c36bb9941dc1f676250c6ea911c39cf31ad655b346da8bf7d9b06f719fc"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if _sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9k protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or _sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(f"frozen Phase 7B9k source changed: {source['path']}")
    return protocol


def _block_slice(record: dict[str, object]) -> slice:
    return slice(int(record["core_group_start"]), int(record["core_group_stop"]))


def _allocate_residual(
    path: Path, shape: tuple[int, int, int], configuration: dict[str, object]
) -> None:
    expected = int(configuration["raw_float64_checkpoint_size_bytes"])
    if path.exists():
        if path.stat().st_size != expected:
            raise RuntimeError("Phase 7B9k residual buffer size changed")
        return
    required = expected + int(configuration["minimum_free_bytes_after_residual_allocation"])
    if shutil.disk_usage(path.parent).free <= required:
        raise OSError("insufficient disk space for Phase 7B9k residual buffer")
    array = np.memmap(path, mode="w+", dtype=np.float64, shape=shape)
    array.flush()
    del array


def _initial_manifest(
    protocol: dict[str, object], manifest_path: Path, shape: tuple[int, int, int]
) -> dict[str, object]:
    configuration = protocol["configuration"]
    pause = json.loads(
        (ROOT / protocol["sources"]["pause_snapshot"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    retained = ROOT / protocol["sources"]["retained_trial_map3"]["path"]
    output = ROOT / configuration["work_directory"] / "state_b.dat"
    residual = ROOT / configuration["single_previous_residual_buffer"]
    _allocate_residual(residual, shape, configuration)
    partial = pause["uncommitted_iteration"]
    manifest = {
        "phase": protocol["phase"],
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "status": "running",
        "current_map": 3,
        "current_state_path": _relative(retained),
        "current_state_sha256": _sha256(retained),
        "context_history": pause["history"],
        "history": [],
        "previous_weights_by_block": None,
        "residual_buffer_path": _relative(residual),
        "uncommitted_iteration": {
            "map": 4,
            "stage": "mapping",
            "current_state_path": _relative(retained),
            "current_state_sha256": _sha256(retained),
            "output_state_path": _relative(output),
            "mapping_completed_blocks": partial["completed_blocks"],
            "mapping_wall_runtime_s": partial["accumulated_wall_runtime_s"],
            "raw_metrics": None,
            "weight_rows": [],
            "residual_updated_blocks": [],
            "state_applied_blocks": [],
            "pending_state_transaction": None,
        },
    }
    _write_json_atomic(manifest_path, manifest)
    return manifest


def _load_manifest(
    protocol: dict[str, object], manifest_path: Path, shape: tuple[int, int, int]
) -> dict[str, object]:
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else _initial_manifest(protocol, manifest_path, shape)
    )
    if (
        manifest["protocol_sha256"] != EXPECTED_PROTOCOL_SHA256
        or manifest["status"] not in ("running", "pilot_passed", "pilot_failed")
    ):
        raise RuntimeError("Phase 7B9k manifest is incompatible")
    expected = int(protocol["configuration"]["raw_float64_checkpoint_size_bytes"])
    current = ROOT / manifest["current_state_path"]
    if current.stat().st_size != expected or _sha256(current) != manifest[
        "current_state_sha256"
    ]:
        raise RuntimeError("Phase 7B9k committed current state changed")
    residual = ROOT / manifest["residual_buffer_path"]
    if residual.stat().st_size != expected:
        raise RuntimeError("Phase 7B9k residual buffer changed")
    uncommitted = manifest.get("uncommitted_iteration")
    if uncommitted is not None and uncommitted["stage"] == "mapping":
        output = ROOT / uncommitted["output_state_path"]
        for record in uncommitted["mapping_completed_blocks"]:
            if phase7b9d._block_sha256(
                output,
                shape,
                int(record["core_group_start"]),
                int(record["core_group_stop"]),
            ) != record["sha256"]:
                raise RuntimeError(
                    f"Phase 7B9k mapped block changed: {record['block_index']}"
                )
    return manifest


def _new_uncommitted(
    protocol: dict[str, object], manifest: dict[str, object]
) -> dict[str, object]:
    next_map = int(manifest["current_map"]) + 1
    work = ROOT / protocol["configuration"]["work_directory"]
    output = work / ("state_a.dat" if next_map % 2 == 1 else "state_b.dat")
    return {
        "map": next_map,
        "stage": "mapping",
        "current_state_path": manifest["current_state_path"],
        "current_state_sha256": manifest["current_state_sha256"],
        "output_state_path": _relative(output),
        "mapping_completed_blocks": [],
        "mapping_wall_runtime_s": 0.0,
        "raw_metrics": None,
        "weight_rows": [],
        "residual_updated_blocks": [],
        "state_applied_blocks": [],
        "pending_state_transaction": None,
    }


def _finish_mapping(
    protocol: dict[str, object],
    protocol_path: Path,
    manifest: dict[str, object],
    manifest_path: Path,
    shape: tuple[int, int, int],
) -> None:
    configuration = protocol["configuration"]
    uncommitted = manifest["uncommitted_iteration"]
    if uncommitted["stage"] != "mapping":
        return
    map_index = int(uncommitted["map"])
    current = ROOT / uncommitted["current_state_path"]
    output = ROOT / uncommitted["output_state_path"]
    completed = {
        int(row["block_index"]): row
        for row in uncommitted["mapping_completed_blocks"]
    }
    pending = [index for index in range(76) if index not in completed]
    reports = ROOT / configuration["work_directory"] / "reports"
    reports.mkdir(exist_ok=True)
    concurrency = int(configuration["maximum_concurrent_processes"])
    worker_protocol = ROOT / protocol["sources"]["finite_trial_protocol"]["path"]
    worker_script = ROOT / protocol["sources"]["finite_trial_worker"]["path"]
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        started = time.perf_counter()
        processes = []
        report_paths = []
        for block_index in batch:
            report = reports / f"block_aitken_map{map_index:02d}_block{block_index:02d}.json"
            report_paths.append(report)
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(worker_script),
                        "--worker",
                        "--protocol",
                        str(worker_protocol),
                        "--current-state",
                        str(current),
                        "--block-index",
                        str(block_index),
                        "--output-state",
                        str(output),
                        "--worker-report",
                        str(report),
                    ],
                    cwd=ROOT,
                )
            )
        return_codes = [process.wait() for process in processes]
        if any(code != 0 for code in return_codes):
            raise RuntimeError(f"Phase 7B9k map {map_index} worker failure: {return_codes}")
        for block_index, report_path in zip(batch, report_paths, strict=True):
            row = json.loads(report_path.read_text(encoding="utf-8"))
            if int(row["block_index"]) != block_index:
                raise RuntimeError("Phase 7B9k worker block identity changed")
            row["sha256"] = phase7b9d._block_sha256(
                output,
                shape,
                int(row["core_group_start"]),
                int(row["core_group_stop"]),
            )
            uncommitted["mapping_completed_blocks"].append(row)
        uncommitted["mapping_completed_blocks"].sort(
            key=lambda row: int(row["block_index"])
        )
        uncommitted["mapping_wall_runtime_s"] = float(
            uncommitted["mapping_wall_runtime_s"]
        ) + (time.perf_counter() - started)
        _write_json_atomic(manifest_path, manifest)
        count = len(uncommitted["mapping_completed_blocks"])
        if count % 10 == 0 or count == 76:
            print(
                json.dumps(
                    {"map": map_index, "mapped_blocks": count, "total_blocks": 76}
                ),
                flush=True,
            )


def _trial_valid(
    current: np.memmap,
    mapped: np.memmap,
    core_start: int,
    core_stop: int,
    weight: float,
    chunk_groups: int = 8,
) -> tuple[bool, float]:
    if not np.isfinite(weight) or weight <= 0.0:
        return False, float("nan")
    minimum = np.inf
    for start in range(core_start, core_stop, chunk_groups):
        stop = min(start + chunk_groups, core_stop)
        trial = np.asarray(current[start:stop]) + weight * (
            np.asarray(mapped[start:stop]) - np.asarray(current[start:stop])
        )
        if not np.all(np.isfinite(trial)):
            return False, float("nan")
        minimum = min(minimum, float(np.min(trial)))
    return bool(minimum >= 0.0), float(minimum)


def _dot_terms(
    current: np.memmap,
    mapped: np.memmap,
    previous_residual: np.memmap,
    core_start: int,
    core_stop: int,
    chunk_groups: int = 8,
) -> tuple[float, float]:
    numerator = 0.0
    denominator = 0.0
    for start in range(core_start, core_stop, chunk_groups):
        stop = min(start + chunk_groups, core_stop)
        new = np.asarray(mapped[start:stop]) - np.asarray(current[start:stop])
        previous = np.asarray(previous_residual[start:stop])
        change = new - previous
        numerator += float(np.einsum("fmd,fmd->", previous, change))
        denominator += float(np.einsum("fmd,fmd->", change, change))
    return numerator, denominator


def _prepare_weights_and_metrics(
    protocol: dict[str, object],
    manifest: dict[str, object],
    manifest_path: Path,
    shape: tuple[int, int, int],
    frequency_width: np.ndarray,
) -> None:
    uncommitted = manifest["uncommitted_iteration"]
    if uncommitted["stage"] != "mapping":
        return
    records = uncommitted["mapping_completed_blocks"]
    if len(records) != 76:
        raise RuntimeError("Phase 7B9k cannot prepare weights before full coverage")
    current_path = ROOT / uncommitted["current_state_path"]
    output_path = ROOT / uncommitted["output_state_path"]
    current = np.memmap(current_path, mode="r", dtype=np.float64, shape=shape)
    mapped = np.memmap(output_path, mode="r", dtype=np.float64, shape=shape)
    previous_residual = None
    previous_weights = manifest["previous_weights_by_block"]
    if previous_weights is not None:
        previous_residual = np.memmap(
            ROOT / manifest["residual_buffer_path"],
            mode="r",
            dtype=np.float64,
            shape=shape,
        )
    configuration = protocol["configuration"]
    maximum_aitken = float(
        configuration["maximum_aitken_weight_from_historical_accepted_full_map"]
    )
    fallback = tuple(float(value) for value in configuration["fallback_weights_in_order"])
    weight_rows = []
    for record in records:
        block_index = int(record["block_index"])
        start = int(record["core_group_start"])
        stop = int(record["core_group_stop"])
        numerator = None
        denominator = None
        candidate = None
        rejection = "first accelerated map uses frozen fallback"
        if previous_residual is not None:
            numerator, denominator = _dot_terms(
                current, mapped, previous_residual, start, stop
            )
            if denominator > 0.0:
                candidate = (
                    -float(previous_weights[block_index]) * numerator / denominator
                )
            if candidate is None or not np.isfinite(candidate) or candidate <= 0.0:
                rejection = "candidate is not positive finite"
            elif candidate > maximum_aitken:
                rejection = "candidate exceeds historical accepted bound"
            else:
                valid, minimum = _trial_valid(current, mapped, start, stop, candidate)
                if valid:
                    weight_rows.append(
                        {
                            "block_index": block_index,
                            "core_group_start": start,
                            "core_group_stop": stop,
                            "aitken_numerator": numerator,
                            "aitken_denominator": denominator,
                            "aitken_candidate_weight": candidate,
                            "accepted_method": "block Aitken",
                            "accepted_weight": candidate,
                            "minimum_trial_intensity": minimum,
                            "candidate_rejection": None,
                        }
                    )
                    continue
                rejection = "candidate violates whole-block finite nonnegative gate"
        accepted = None
        accepted_minimum = None
        for weight in fallback:
            valid, minimum = _trial_valid(current, mapped, start, stop, weight)
            if valid:
                accepted = weight
                accepted_minimum = minimum
                break
        if accepted is None:
            raise ArithmeticError(f"Phase 7B9k block {block_index} has no safe fallback")
        weight_rows.append(
            {
                "block_index": block_index,
                "core_group_start": start,
                "core_group_stop": stop,
                "aitken_numerator": numerator,
                "aitken_denominator": denominator,
                "aitken_candidate_weight": candidate,
                "accepted_method": "guarded fallback",
                "accepted_weight": accepted,
                "minimum_trial_intensity": accepted_minimum,
                "candidate_rejection": rejection,
            }
        )
    ownership = np.zeros(shape[0], dtype=np.int64)
    for record in records:
        ownership[_block_slice(record)] += 1
    maximum_change = max(
        float(record["maximum_absolute_radiation_change"]) for record in records
    )
    maximum_scale = max(float(record["maximum_radiation_scale"]) for record in records)
    spectrum, bolometric, current_flux, mapped_flux = phase7b9d._boundary_flux_change(
        current_path, output_path, shape, frequency_width
    )
    uncommitted["raw_metrics"] = {
        "block_count": len(records),
        "owned_frequency_group_count": int(np.sum(ownership)),
        "ownership_exactly_once": bool(np.all(ownership == 1)),
        "raw_source_map_residual": (
            maximum_change / maximum_scale if maximum_scale > 0.0 else maximum_change
        ),
        "boundary_flux_spectrum_l1": spectrum,
        "boundary_flux_bolometric_fraction": bolometric,
        "boundary_flux_bolometric_current": current_flux,
        "boundary_flux_bolometric_mapped": mapped_flux,
        "minimum_mapped_intensity": min(
            float(record["minimum_mapped_intensity"]) for record in records
        ),
        "maximum_internal_energy_ledger_residual": max(
            float(record["internal_total_energy_ledger_residual"])
            for record in records
        ),
        "maximum_process_peak_rss_mib": max(
            float(record["peak_process_rss_mib"]) for record in records
        ),
    }
    uncommitted["weight_rows"] = weight_rows
    uncommitted["stage"] = "weights_ready"
    _write_json_atomic(manifest_path, manifest)


def _update_residual(
    manifest: dict[str, object],
    manifest_path: Path,
    shape: tuple[int, int, int],
) -> None:
    uncommitted = manifest["uncommitted_iteration"]
    if uncommitted["stage"] not in ("weights_ready", "residual_updating"):
        return
    uncommitted["stage"] = "residual_updating"
    _write_json_atomic(manifest_path, manifest)
    current = np.memmap(
        ROOT / uncommitted["current_state_path"], mode="r", dtype=np.float64, shape=shape
    )
    mapped = np.memmap(
        ROOT / uncommitted["output_state_path"], mode="r", dtype=np.float64, shape=shape
    )
    residual_path = ROOT / manifest["residual_buffer_path"]
    residual = np.memmap(residual_path, mode="r+", dtype=np.float64, shape=shape)
    completed = {
        int(row["block_index"]): row
        for row in uncommitted["residual_updated_blocks"]
    }
    for row in uncommitted["weight_rows"]:
        block_index = int(row["block_index"])
        if block_index in completed:
            continue
        start = int(row["core_group_start"])
        stop = int(row["core_group_stop"])
        for chunk_start in range(start, stop, 8):
            chunk_stop = min(chunk_start + 8, stop)
            residual[chunk_start:chunk_stop] = (
                np.asarray(mapped[chunk_start:chunk_stop])
                - np.asarray(current[chunk_start:chunk_stop])
            )
        residual.flush()
        digest = phase7b9d._block_sha256(residual_path, shape, start, stop)
        uncommitted["residual_updated_blocks"].append(
            {"block_index": block_index, "sha256": digest}
        )
        _write_json_atomic(manifest_path, manifest)
    uncommitted["stage"] = "residual_updated"
    _write_json_atomic(manifest_path, manifest)


def _restore_pending_transaction(
    manifest: dict[str, object],
    manifest_path: Path,
    shape: tuple[int, int, int],
) -> None:
    uncommitted = manifest["uncommitted_iteration"]
    pending = uncommitted.get("pending_state_transaction")
    if pending is None:
        return
    backup_path = ROOT / pending["backup_path"]
    if _sha256(backup_path) != pending["backup_sha256"]:
        raise RuntimeError("Phase 7B9k state transaction backup changed")
    start = int(pending["core_group_start"])
    stop = int(pending["core_group_stop"])
    output = np.memmap(
        ROOT / uncommitted["output_state_path"], mode="r+", dtype=np.float64, shape=shape
    )
    backup = np.memmap(
        backup_path,
        mode="r",
        dtype=np.float64,
        shape=(stop - start, shape[1], shape[2]),
    )
    for offset in range(0, stop - start, 8):
        width = min(8, stop - start - offset)
        output[start + offset : start + offset + width] = backup[offset : offset + width]
    output.flush()
    del backup
    backup_path.unlink()
    uncommitted["pending_state_transaction"] = None
    _write_json_atomic(manifest_path, manifest)


def _apply_state(
    manifest: dict[str, object],
    manifest_path: Path,
    shape: tuple[int, int, int],
) -> None:
    uncommitted = manifest["uncommitted_iteration"]
    if uncommitted["stage"] not in ("residual_updated", "state_applying"):
        return
    uncommitted["stage"] = "state_applying"
    _write_json_atomic(manifest_path, manifest)
    _restore_pending_transaction(manifest, manifest_path, shape)
    current = np.memmap(
        ROOT / uncommitted["current_state_path"], mode="r", dtype=np.float64, shape=shape
    )
    output_path = ROOT / uncommitted["output_state_path"]
    output = np.memmap(output_path, mode="r+", dtype=np.float64, shape=shape)
    applied = {
        int(row["block_index"]): row for row in uncommitted["state_applied_blocks"]
    }
    work = output_path.parent
    for row in uncommitted["weight_rows"]:
        block_index = int(row["block_index"])
        if block_index in applied:
            continue
        start = int(row["core_group_start"])
        stop = int(row["core_group_stop"])
        backup_path = work / f"block_aitken_transaction_block{block_index:02d}.dat"
        backup = np.memmap(
            backup_path,
            mode="w+",
            dtype=np.float64,
            shape=(stop - start, shape[1], shape[2]),
        )
        for offset in range(0, stop - start, 8):
            width = min(8, stop - start - offset)
            backup[offset : offset + width] = output[
                start + offset : start + offset + width
            ]
        backup.flush()
        del backup
        uncommitted["pending_state_transaction"] = {
            "block_index": block_index,
            "core_group_start": start,
            "core_group_stop": stop,
            "backup_path": _relative(backup_path),
            "backup_sha256": _sha256(backup_path),
        }
        _write_json_atomic(manifest_path, manifest)
        weight = float(row["accepted_weight"])
        minimum = np.inf
        for chunk_start in range(start, stop, 8):
            chunk_stop = min(chunk_start + 8, stop)
            trial = np.asarray(current[chunk_start:chunk_stop]) + weight * (
                np.asarray(output[chunk_start:chunk_stop])
                - np.asarray(current[chunk_start:chunk_stop])
            )
            if not np.all(np.isfinite(trial)) or float(np.min(trial)) < 0.0:
                raise ArithmeticError("Phase 7B9k accepted block failed write audit")
            minimum = min(minimum, float(np.min(trial)))
            output[chunk_start:chunk_stop] = trial
        output.flush()
        digest = phase7b9d._block_sha256(output_path, shape, start, stop)
        uncommitted["state_applied_blocks"].append(
            {
                "block_index": block_index,
                "accepted_weight": weight,
                "minimum_accepted_intensity": float(minimum),
                "sha256": digest,
            }
        )
        uncommitted["pending_state_transaction"] = None
        _write_json_atomic(manifest_path, manifest)
        backup_path.unlink()
    uncommitted["stage"] = "state_applied"
    _write_json_atomic(manifest_path, manifest)


def _commit_iteration(
    manifest: dict[str, object], manifest_path: Path
) -> dict[str, object]:
    uncommitted = manifest["uncommitted_iteration"]
    if uncommitted["stage"] != "state_applied":
        raise RuntimeError("Phase 7B9k iteration is not ready to commit")
    output = ROOT / uncommitted["output_state_path"]
    weights = [float(row["accepted_weight"]) for row in uncommitted["weight_rows"]]
    applied = uncommitted["state_applied_blocks"]
    raw = uncommitted["raw_metrics"]
    row = {
        "map": int(uncommitted["map"]),
        **raw,
        "block_aitken_count": sum(
            item["accepted_method"] == "block Aitken"
            for item in uncommitted["weight_rows"]
        ),
        "fallback_count": sum(
            item["accepted_method"] == "guarded fallback"
            for item in uncommitted["weight_rows"]
        ),
        "minimum_accepted_weight": min(weights),
        "median_accepted_weight": float(np.median(weights)),
        "maximum_accepted_weight": max(weights),
        "minimum_accepted_intensity": min(
            float(item["minimum_accepted_intensity"]) for item in applied
        ),
        "wall_runtime_s": float(uncommitted["mapping_wall_runtime_s"]),
        "accepted_state_path": _relative(output),
        "accepted_state_sha256": _sha256(output),
        "weight_rows": uncommitted["weight_rows"],
    }
    manifest["current_map"] = row["map"]
    manifest["current_state_path"] = row["accepted_state_path"]
    manifest["current_state_sha256"] = row["accepted_state_sha256"]
    manifest["previous_weights_by_block"] = weights
    manifest["history"].append(row)
    manifest["uncommitted_iteration"] = None
    _write_json_atomic(manifest_path, manifest)
    print(
        json.dumps(
            {
                "committed_accelerated_map": row["map"],
                "raw_source_map_residual": row["raw_source_map_residual"],
                "boundary_flux_spectrum_l1": row["boundary_flux_spectrum_l1"],
                "boundary_flux_bolometric_fraction": row[
                    "boundary_flux_bolometric_fraction"
                ],
                "block_aitken_count": row["block_aitken_count"],
                "accepted_weight_range": [
                    row["minimum_accepted_weight"],
                    row["maximum_accepted_weight"],
                ],
            },
            indent=2,
        ),
        flush=True,
    )
    return row


def _project_stop_map(current_map: int, residual: float, target: float, q: float) -> int:
    if not 0.0 < q < 1.0 or not 0.0 < target < residual:
        return 10**9
    first = current_map + int(math.ceil(math.log(target / residual) / math.log(q)))
    stop = first + 1
    if stop % 2 == 1:
        stop += 1
    return stop


def _plot(
    path: Path,
    context: list[dict[str, object]],
    history: list[dict[str, object]],
    decision: dict[str, object],
) -> None:
    all_maps = [int(row["additional_map"]) for row in context] + [
        int(row["map"]) for row in history
    ]
    residual = [float(row["raw_source_map_residual"]) for row in context] + [
        float(row["raw_source_map_residual"]) for row in history
    ]
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].semilogy(all_maps, residual, "o-")
    axes[0, 0].axvline(3.5, color="0.5", ls=":", label="Acceleration starts")
    axes[0, 0].axhline(1.0e-4, color="0.25", ls="--", label="Source gate")
    axes[0, 0].set(
        xlabel="Finite-trial source map",
        ylabel="Raw fixed-point residual",
        title="(a) True full-map response",
    )
    axes[0, 0].legend(frameon=False)
    maps = [int(row["map"]) for row in history]
    axes[0, 1].fill_between(
        maps,
        [float(row["minimum_accepted_weight"]) for row in history],
        [float(row["maximum_accepted_weight"]) for row in history],
        alpha=0.25,
        label="Block range",
    )
    axes[0, 1].plot(
        maps,
        [float(row["median_accepted_weight"]) for row in history],
        "o-",
        label="Median",
    )
    axes[0, 1].set(
        xlabel="Accelerated source map",
        ylabel="Accepted block weight",
        title="(b) Natural-block relaxation",
    )
    axes[0, 1].legend(frameon=False)
    axes[1, 0].semilogy(
        maps,
        [float(row["boundary_flux_spectrum_l1"]) for row in history],
        "o-",
        label="Spectral L1",
    )
    axes[1, 0].semilogy(
        maps,
        [float(row["boundary_flux_bolometric_fraction"]) for row in history],
        "s-",
        label="Bolometric",
    )
    axes[1, 0].axhline(1.0e-3, color="0.25", ls="--", label="Boundary gate")
    axes[1, 0].set(
        xlabel="Accelerated source map",
        ylabel="Raw boundary-flux change",
        title="(c) Observer-facing functionals",
    )
    axes[1, 0].legend(frameon=False)
    axes[1, 1].axis("off")
    axes[1, 1].text(
        0.03,
        0.96,
        "(d) Pilot decision\n\n"
        f"Map-5 / map-4 residual = {decision['map5_to_map4_residual_ratio']:.3f}\n"
        f"Map-6 / map-5 residual = {decision['map6_to_map5_residual_ratio']:.3f}\n"
        f"Aitken blocks above 2 = {decision['aitken_blocks_above_two']}\n"
        f"Projected stop map = {decision['projected_stop_map']}\n\n"
        f"Block-Aitken continuation: {decision['continue_block_aitken']}\n"
        "Trial physical residual: not evaluated",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=10.1,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    worker_protocol = json.loads(
        (ROOT / protocol["sources"]["finite_trial_protocol"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    shape = phase7b9d._shape(worker_protocol)
    with np.load(ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]) as master:
        frequency_width = np.diff(np.array(master["active_edge_hz"], copy=True))
    manifest_path = ROOT / configuration["acceleration_manifest"]
    manifest = _load_manifest(protocol, manifest_path, shape)
    if manifest["status"] in ("pilot_passed", "pilot_failed"):
        return json.loads(
            (OUTPUT / "phase7b9k_block_aitken_pilot_summary.json").read_text(
                encoding="utf-8"
            )
        )
    target_maps = [int(value) for value in configuration["pilot_map_indices_exactly"]]
    while int(manifest["current_map"]) < target_maps[-1]:
        if manifest["uncommitted_iteration"] is None:
            manifest["uncommitted_iteration"] = _new_uncommitted(protocol, manifest)
            _write_json_atomic(manifest_path, manifest)
        _finish_mapping(protocol, protocol_path, manifest, manifest_path, shape)
        _prepare_weights_and_metrics(
            protocol, manifest, manifest_path, shape, frequency_width
        )
        _update_residual(manifest, manifest_path, shape)
        _apply_state(manifest, manifest_path, shape)
        _commit_iteration(manifest, manifest_path)
    history = manifest["history"]
    if [int(row["map"]) for row in history] != target_maps:
        raise RuntimeError("Phase 7B9k pilot map identity changed")
    map4, map5, map6 = history
    q54 = float(map5["raw_source_map_residual"] / map4["raw_source_map_residual"])
    q65 = float(map6["raw_source_map_residual"] / map5["raw_source_map_residual"])
    q64 = float(map6["raw_source_map_residual"] / map4["raw_source_map_residual"])
    spectrum_ratio = float(
        map6["boundary_flux_spectrum_l1"] / map4["boundary_flux_spectrum_l1"]
    )
    bolometric_ratio = float(
        map6["boundary_flux_bolometric_fraction"]
        / map4["boundary_flux_bolometric_fraction"]
    )
    aitken_above_two = sum(
        row["accepted_method"] == "block Aitken"
        and float(row["accepted_weight"]) > 2.0
        for iteration in (map5, map6)
        for row in iteration["weight_rows"]
    )
    projected_stop = _project_stop_map(
        6, float(map6["raw_source_map_residual"]), 1.0e-4, q65
    )
    gate_checks = {
        "map5_contracts_from_map4": q54
        < gates["map5_to_map4_raw_residual_ratio_below"],
        "map6_accelerated_contraction": q65
        < gates["map6_to_map5_raw_residual_ratio_below"],
        "two_map_contraction": q64
        < gates["map6_to_map4_raw_residual_ratio_below"],
        "boundary_spectrum_improves": spectrum_ratio
        < gates["map6_to_map4_boundary_spectrum_ratio_below"],
        "boundary_bolometric_improves": bolometric_ratio
        < gates["map6_to_map4_boundary_bolometric_ratio_below"],
        "block_aitken_used_above_two": aitken_above_two
        >= gates["block_aitken_weights_above_two_at_least"],
        "all_maps_complete_nonnegative_and_within_resources": all(
            int(row["block_count"]) == gates["each_map_block_count_exactly"]
            and int(row["owned_frequency_group_count"])
            == gates["each_map_owned_frequency_groups_exactly"]
            and row["ownership_exactly_once"]
            and float(row["minimum_accepted_intensity"])
            >= gates["minimum_accepted_intensity_at_least"]
            and float(row["maximum_process_peak_rss_mib"])
            < gates["each_process_peak_rss_strictly_below_mib"]
            and float(row["wall_runtime_s"])
            < gates["each_map_wall_time_strictly_below_s"]
            for row in history
        ),
        "projected_budget_is_bounded": projected_stop
        <= gates["projected_stop_map_at_most_if_constant_latest_contraction"],
    }
    passed = all(gate_checks.values())
    decision_metrics = {
        "map5_to_map4_residual_ratio": q54,
        "map6_to_map5_residual_ratio": q65,
        "map6_to_map4_residual_ratio": q64,
        "map6_to_map4_boundary_spectrum_ratio": spectrum_ratio,
        "map6_to_map4_boundary_bolometric_ratio": bolometric_ratio,
        "aitken_blocks_above_two": aitken_above_two,
        "projected_stop_map": projected_stop,
        "continue_block_aitken": passed,
    }
    manifest["status"] = "pilot_passed" if passed else "pilot_failed"
    _write_json_atomic(manifest_path, manifest)
    figure_path = OUTPUT / "phase7b9k_block_aitken_pilot.png"
    _plot(figure_path, manifest["context_history"], history, decision_metrics)
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "history": history,
        "gate_checks": gate_checks,
        **decision_metrics,
        "manifest_path": _relative(manifest_path),
        "manifest_status": manifest["status"],
        "retained_trial_map3_path": protocol["sources"]["retained_trial_map3"]["path"],
        "retained_trial_map3_sha256": protocol["sources"]["retained_trial_map3"]["sha256"],
        "final_accelerated_state_path": manifest["current_state_path"],
        "final_accelerated_state_sha256": manifest["current_state_sha256"],
        "decision": {
            "frozen_sources_and_pause_hashes_passed": True,
            "three_full_acceleration_maps_complete": True,
            "natural_block_aitken_pilot_passed": passed,
            "continue_block_aitken_authorized": passed,
            "plain_omega1_resume_authorized": False,
            "trial_inner_radiation_converged": False,
            "trial_formal_feedback_evaluated": False,
            "trial_true_residual_evaluated": False,
            "trial_accepted_as_nonlinear_step": False,
            "trial_rejected_by_physical_residual": False,
            "static_approximation_rejected_by_this_stage": False,
            "accepted_as_dynamic_nlte_solution": False,
            "phase7b9k_gate_passed": passed,
        },
        "figures": [figure_path.name],
    }
    _write_json_atomic(OUTPUT / "phase7b9k_block_aitken_pilot_summary.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9k_preregistered_block_aitken_pilot.json",
    )
    args = parser.parse_args()
    report = run(args.protocol)
    print(
        json.dumps(
            {
                "phase": report["phase"],
                "manifest_status": report["manifest_status"],
                "map5_to_map4_residual_ratio": report[
                    "map5_to_map4_residual_ratio"
                ],
                "map6_to_map5_residual_ratio": report[
                    "map6_to_map5_residual_ratio"
                ],
                "projected_stop_map": report["projected_stop_map"],
                "decision": report["decision"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
