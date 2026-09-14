"""Phase 7B9dt：用最后一对 Picard input/mapped 态定位最大范数慢模。"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
from typing import Iterable

import numpy as np

try:
    from scripts import phase7b9_half_trial_positive_sequence_engine as engine
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_half_trial_positive_sequence_engine as engine  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
RUNNER_RELATIVE_PATH = "scripts/phase7b9dt_two_state_slow_mode_locator.py"
PREREGISTER_RELATIVE_PATH = (
    "scripts/phase7b9dt_preregister_two_state_slow_mode_locator.py"
)
RESIDUAL_DEFINITION_RELATIVE_PATH = (
    "scripts/phase7b9_half_trial_positive_sequence_engine.py"
)
FREQUENCY_SOURCE_KEY = "phase7b5p_master_input"
MAXIMUM_SMALL_SOURCE_BYTES = 64 * 1024 * 1024
GLOBAL_RESIDUAL_TARGET = 1.0e-4
PLANCK_J_S = 6.62607015e-34
ELECTRON_VOLT_J = 1.602176634e-19
TERMINAL_STATUSES = {"maximum_maps_exhausted", "provisional_pause", "complete"}


@dataclass(frozen=True)
class TwoStateSlowModeLocatorSpec:
    phase: str
    phase_index: int
    classification: str
    ending_protocol_path: str
    ending_manifest_path: str
    ending_summary_path: str
    analyzer_runner_path: str
    preregister_runner_path: str
    block_json_path: str
    block_csv_path: str
    summary_path: str
    figure_path: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _safe_relative(relative: str, *, dat_claim: bool = False) -> str:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise RuntimeError("7B9dt path must be repository-relative")
    if dat_claim:
        if path.suffix.lower() != ".dat":
            raise RuntimeError("7B9dt full-state claim must be a .dat path")
    elif path.suffix.lower() == ".dat":
        raise RuntimeError("7B9dt small sources cannot contain .dat files")
    return str(path)


def _small_source(root: Path, relative: str) -> dict[str, object]:
    relative = _safe_relative(relative)
    path = root / relative
    size = path.stat().st_size
    if not path.is_file() or size > MAXIMUM_SMALL_SOURCE_BYTES:
        raise RuntimeError(f"7B9dt source is not a small regular file: {relative}")
    return {"path": relative, "size_bytes": size, "sha256": sha256(path)}


def _read_small_json(root: Path, relative: str) -> dict[str, object]:
    source = _small_source(root, relative)
    if PurePosixPath(relative).suffix.lower() != ".json":
        raise RuntimeError("7B9dt lineage evidence must be JSON")
    payload = json.loads((root / str(source["path"])).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("7B9dt JSON evidence must contain an object")
    return payload


def _validate_source_claim(root: Path, claim: object) -> dict[str, object]:
    if not isinstance(claim, dict):
        raise RuntimeError("7B9dt upstream source claim is malformed")
    relative = _safe_relative(str(claim.get("path", "")))
    current = _small_source(root, relative)
    if current != claim:
        raise RuntimeError(f"7B9dt upstream small source changed: {relative}")
    return current


def _full_state_claim(path: object, digest: object, size: int) -> dict[str, object]:
    relative = _safe_relative(str(path), dat_claim=True)
    fingerprint = str(digest)
    if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
        raise RuntimeError("7B9dt full-state claim has an invalid SHA-256")
    if size <= 0:
        raise RuntimeError("7B9dt full-state claim has an invalid size")
    return {"path": relative, "size_bytes": int(size), "sha256": fingerprint}


def _frequency_edges(root: Path, source: dict[str, object], groups: int) -> np.ndarray:
    with np.load(root / str(source["path"]), allow_pickle=False) as payload:
        if "active_edge_hz" not in payload:
            raise RuntimeError("7B9dt frequency source lacks active_edge_hz")
        edges = np.asarray(payload["active_edge_hz"], dtype=np.float64)
    if (
        edges.shape != (groups + 1,)
        or not np.all(np.isfinite(edges))
        or np.any(edges <= 0.0)
        or np.any(np.diff(edges) <= 0.0)
    ):
        raise RuntimeError("7B9dt active frequency edges are invalid")
    return edges


def _terminal_lineage(
    root: Path,
    protocol_path: str,
    manifest_path: str,
    summary_path: str,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    tuple[int, int, int],
    int,
    int,
]:
    protocol = _read_small_json(root, protocol_path)
    manifest = _read_small_json(root, manifest_path)
    summary = _read_small_json(root, summary_path)
    protocol_digest = sha256(root / protocol_path)
    if (
        manifest.get("protocol_sha256") != protocol_digest
        or summary.get("protocol_sha256") != protocol_digest
    ):
        raise RuntimeError("7B9dt ending protocol SHA lineage changed")
    sources = protocol.get("sources")
    if not isinstance(sources, dict) or FREQUENCY_SOURCE_KEY not in sources:
        raise RuntimeError("7B9dt ending protocol lacks the frequency source")
    for claim in sources.values():
        _validate_source_claim(root, claim)

    status = manifest.get("status")
    iterations = manifest.get("iterations")
    if (
        status not in TERMINAL_STATUSES
        or summary.get("status") != status
        or manifest.get("active_iteration") is not None
        or not isinstance(iterations, list)
        or not iterations
        or summary.get("iterations") != iterations
    ):
        raise RuntimeError("7B9dt requires one atomic terminal sequence state")
    try:
        indices = [int(row["iteration"]) for row in iterations]
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("7B9dt ending iteration sequence is malformed") from error
    if indices != list(range(indices[0], indices[0] + len(indices))):
        raise RuntimeError("7B9dt ending iterations are not contiguous")
    last = iterations[-1]
    if not isinstance(last, dict) or not any(
        last.get(name) is True
        for name in ("progression_passed", "original_map_passed", "map_passed")
    ):
        raise RuntimeError("7B9dt last original-operator map did not pass progression")
    if (
        (manifest.get("current_input_path"), manifest.get("current_input_sha256"))
        != (last.get("input_state_path"), last.get("input_state_sha256"))
        or (manifest.get("next_output_path"), manifest.get("next_output_sha256"))
        != (last.get("mapped_state_path"), last.get("mapped_state_sha256"))
    ):
        raise RuntimeError("7B9dt last input/mapped lineage changed")

    configuration = protocol.get("configuration", {})
    shape = engine._shape(protocol)
    groups, angles, depths = shape
    expected_size = groups * angles * depths * np.dtype(np.float64).itemsize
    raw_size = int(configuration.get("raw_float64_checkpoint_size_bytes", 0))
    # 不同续算器沿用同一自然频率分块，但历史字段名不同。
    block_width = int(
        configuration.get(
            "diagnostic_frequency_block",
            configuration.get("core_frequency_groups", 0),
        )
    )
    block_count = math.ceil(groups / block_width) if block_width > 0 else 0
    if (
        min(shape) <= 0
        or raw_size != expected_size
        or block_width <= 0
        or int(configuration.get("natural_frequency_block_count", block_count))
        != block_count
    ):
        raise RuntimeError("7B9dt ending state shape or natural blocks changed")
    if protocol.get("gates", {}).get("global_original_operator_residual_below") != (
        GLOBAL_RESIDUAL_TARGET
    ):
        raise RuntimeError("7B9dt original-operator threshold changed")
    reference = float(last.get("global_original_operator_residual", float("nan")))
    if not np.isfinite(reference) or reference < 0.0:
        raise RuntimeError("7B9dt ending residual is invalid")

    input_claim = _full_state_claim(
        last.get("input_state_path"), last.get("input_state_sha256"), raw_size
    )
    mapped_claim = _full_state_claim(
        last.get("mapped_state_path"), last.get("mapped_state_sha256"), raw_size
    )
    if input_claim["path"] == mapped_claim["path"]:
        raise RuntimeError("7B9dt input and mapped claims must use different buffers")
    frequency_source = _validate_source_claim(root, sources[FREQUENCY_SOURCE_KEY])
    _frequency_edges(root, frequency_source, groups)
    return (
        protocol,
        manifest,
        summary,
        input_claim,
        mapped_claim,
        shape,
        block_width,
        block_count,
    )


def build_two_state_slow_mode_locator_protocol(
    root: Path, spec: TwoStateSlowModeLocatorSpec
) -> dict[str, object]:
    """Freeze small lineage and two full-state claims without opening either state."""
    if spec.analyzer_runner_path != RUNNER_RELATIVE_PATH:
        raise RuntimeError("7B9dt analyzer runner changed")
    if spec.preregister_runner_path != PREREGISTER_RELATIVE_PATH:
        raise RuntimeError("7B9dt preregister runner changed")
    (
        ending_protocol,
        manifest,
        _,
        input_claim,
        mapped_claim,
        shape,
        block_width,
        block_count,
    ) = _terminal_lineage(
        root,
        spec.ending_protocol_path,
        spec.ending_manifest_path,
        spec.ending_summary_path,
    )
    for relative in (
        spec.block_json_path,
        spec.block_csv_path,
        spec.summary_path,
        spec.figure_path,
    ):
        path = PurePosixPath(_safe_relative(relative))
        if path.parts[0] != "outputs" or (
            len(path.parts) > 1 and path.parts[1] == "checkpoints"
        ):
            raise RuntimeError("7B9dt diagnostic outputs must be below outputs")
    frequency = ending_protocol["sources"][FREQUENCY_SOURCE_KEY]
    sources = {
        "ending_protocol": _small_source(root, spec.ending_protocol_path),
        "ending_manifest": _small_source(root, spec.ending_manifest_path),
        "ending_summary": _small_source(root, spec.ending_summary_path),
        "frequency_grid": _small_source(root, str(frequency["path"])),
        "residual_definition": _small_source(
            root, RESIDUAL_DEFINITION_RELATIVE_PATH
        ),
        "locator_runner": _small_source(root, spec.analyzer_runner_path),
        "locator_preregister": _small_source(root, spec.preregister_runner_path),
    }
    if any(str(source["path"]).lower().endswith(".dat") for source in sources.values()):
        raise RuntimeError("7B9dt protocol source set contains a full-state file")
    last = manifest["iterations"][-1]
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": sources,
        "full_state_claims": {
            "input_state": input_claim,
            "mapped_state": mapped_claim,
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": shape[0],
            "angular_direction_count": shape[1],
            "radiation_depth_cell_count": shape[2],
            "raw_float64_checkpoint_size_bytes": input_claim["size_bytes"],
            "core_frequency_groups": block_width,
            "natural_frequency_block_count": block_count,
            "reference_global_original_operator_residual": last[
                "global_original_operator_residual"
            ],
            "block_json_path": spec.block_json_path,
            "block_csv_path": spec.block_csv_path,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "stream_read_only_by_natural_frequency_block": True,
        },
        "gates": {
            "global_original_operator_residual_below": GLOBAL_RESIDUAL_TARGET,
            "residual_reproduction_absolute_tolerance": 0.0,
            "natural_frequency_block_count_exactly": block_count,
        },
        "prohibitions": {
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "nonfinite_values_fail_immediately": True,
        },
        "authorization": {
            "read_exactly_two_full_states": True,
            "validate_each_full_state_sha256_once_before_analysis": True,
            "diagnostic_only": True,
            "convergence_proof": False,
            "material_update": False,
            "radiation_update": False,
        },
        "builder_audit": {
            "ending_status": manifest["status"],
            "summary_iterations_equal_manifest_iterations": True,
            "full_state_bytes_read": False,
            "full_state_bytes_hashed": False,
            "threshold_changed": False,
        },
    }


def write_two_state_slow_mode_locator_protocol(
    root: Path,
    spec: TwoStateSlowModeLocatorSpec,
    output_path: Path,
) -> tuple[dict[str, object], str]:
    protocol = build_two_state_slow_mode_locator_protocol(root, spec)
    _write_json_atomic(output_path, protocol)
    return protocol, sha256(output_path)


def _group_coordinates(edges: np.ndarray, group: int) -> dict[str, float]:
    lower = float(edges[group])
    upper = float(edges[group + 1])
    centre = math.sqrt(lower * upper)
    return {
        "frequency_lower_hz": lower,
        "frequency_upper_hz": upper,
        "frequency_geometric_centre_hz": centre,
        "energy_geometric_centre_ev": centre * PLANCK_J_S / ELECTRON_VOLT_J,
    }


def _analyze_natural_block(
    input_state: np.ndarray,
    mapped_state: np.ndarray,
    edges: np.ndarray,
    block_index: int,
    start: int,
    stop: int,
) -> dict[str, object]:
    maximum_change = -1.0
    change_location: tuple[int, int, int] | None = None
    change_input = 0.0
    change_mapped = 0.0
    maximum_input_scale = -1.0
    input_scale_location: tuple[int, int, int] | None = None
    maximum_mapped_scale = -1.0
    mapped_scale_location: tuple[int, int, int] | None = None
    minimum_input = math.inf
    minimum_mapped = math.inf
    for group in range(start, stop):
        input_plane = np.asarray(input_state[group])
        mapped_plane = np.asarray(mapped_state[group])
        if not np.all(np.isfinite(input_plane)) or not np.all(np.isfinite(mapped_plane)):
            raise ArithmeticError("7B9dt encountered a non-finite full-state value")
        difference = np.abs(mapped_plane - input_plane)
        if not np.all(np.isfinite(difference)):
            raise ArithmeticError("7B9dt finite states produced a non-finite difference")
        local_change = float(np.max(difference))
        local_change_flat = int(np.argmax(difference))
        if local_change > maximum_change:
            angle, depth = np.unravel_index(local_change_flat, difference.shape)
            maximum_change = local_change
            change_location = (group, int(angle), int(depth))
            change_input = float(input_plane[angle, depth])
            change_mapped = float(mapped_plane[angle, depth])
        input_absolute = np.abs(input_plane)
        local_input_scale = float(np.max(input_absolute))
        if local_input_scale > maximum_input_scale:
            angle, depth = np.unravel_index(
                int(np.argmax(input_absolute)), input_absolute.shape
            )
            maximum_input_scale = local_input_scale
            input_scale_location = (group, int(angle), int(depth))
        mapped_absolute = np.abs(mapped_plane)
        local_mapped_scale = float(np.max(mapped_absolute))
        if local_mapped_scale > maximum_mapped_scale:
            angle, depth = np.unravel_index(
                int(np.argmax(mapped_absolute)), mapped_absolute.shape
            )
            maximum_mapped_scale = local_mapped_scale
            mapped_scale_location = (group, int(angle), int(depth))
        minimum_input = min(minimum_input, float(np.min(input_plane)))
        minimum_mapped = min(minimum_mapped, float(np.min(mapped_plane)))
    if change_location is None or input_scale_location is None or mapped_scale_location is None:
        raise RuntimeError("7B9dt natural frequency block is empty")
    if maximum_input_scale >= maximum_mapped_scale:
        maximum_scale = maximum_input_scale
        scale_source = "input"
        scale_location = input_scale_location
    else:
        maximum_scale = maximum_mapped_scale
        scale_source = "mapped"
        scale_location = mapped_scale_location
    group, angle, depth = change_location
    scale_group, scale_angle, scale_depth = scale_location
    return {
        "block_index": block_index,
        "core_group_start": start,
        "core_group_stop": stop,
        "maximum_absolute_radiation_change": maximum_change,
        "maximum_radiation_scale": maximum_scale,
        "block_relative_original_operator_residual": (
            maximum_change / maximum_scale if maximum_scale > 0.0 else maximum_change
        ),
        "controlling_frequency_group": group,
        "controlling_angle_index": angle,
        "controlling_depth_index": depth,
        "controlling_input_value": change_input,
        "controlling_mapped_value": change_mapped,
        **_group_coordinates(edges, group),
        "scale_source": scale_source,
        "scale_frequency_group": scale_group,
        "scale_angle_index": scale_angle,
        "scale_depth_index": scale_depth,
        "scale_value": maximum_scale,
        "maximum_input_scale": maximum_input_scale,
        "maximum_mapped_scale": maximum_mapped_scale,
        "minimum_input_intensity": minimum_input,
        "minimum_mapped_intensity": minimum_mapped,
    }


def _engine_residual(
    records: list[dict[str, object]], shape: tuple[int, int, int]
) -> tuple[float, bool]:
    # 中文：直接调用既有序列核的聚合器，避免为定位器另造残差定义。
    reports = [
        {
            "core_group_start": row["core_group_start"],
            "core_group_stop": row["core_group_stop"],
            "maximum_absolute_radiation_change": row[
                "maximum_absolute_radiation_change"
            ],
            "maximum_radiation_scale": row["maximum_radiation_scale"],
            "boundary_spectrum_l1_numerator": 0.0,
            "current_boundary_absolute_scale": 1.0,
            "mapped_boundary_absolute_scale": 1.0,
            "current_boundary_bolometric": 1.0,
            "mapped_boundary_bolometric": 1.0,
            "minimum_input_intensity": row["minimum_input_intensity"],
            "minimum_mapped_intensity": row["minimum_mapped_intensity"],
            "peak_process_rss_mib": 0.0,
            "wall_runtime_s": 0.0,
        }
        for row in records
    ]
    aggregate = engine._aggregate(reports, shape)
    return (
        float(aggregate["global_original_operator_residual"]),
        bool(aggregate["frequency_ownership_exact"]),
    )


def analyze_arrays(
    input_state: np.ndarray,
    mapped_state: np.ndarray,
    frequency_edges_hz: np.ndarray,
    natural_block_width: int,
) -> dict[str, object]:
    """Recompute the existing max-norm residual and retain its exact coordinates."""
    if input_state.shape != mapped_state.shape or input_state.ndim != 3:
        raise ValueError("7B9dt input and mapped arrays must share a three-dimensional shape")
    shape = tuple(int(value) for value in input_state.shape)
    edges = np.asarray(frequency_edges_hz, dtype=np.float64)
    if natural_block_width <= 0 or edges.shape != (shape[0] + 1,):
        raise ValueError("7B9dt natural block width or frequency edges are invalid")
    if (
        not np.all(np.isfinite(edges))
        or np.any(edges <= 0.0)
        or np.any(np.diff(edges) <= 0.0)
    ):
        raise ArithmeticError("7B9dt frequency edges must be finite and increasing")
    records = []
    for block_index, start in enumerate(range(0, shape[0], natural_block_width)):
        records.append(
            _analyze_natural_block(
                input_state,
                mapped_state,
                edges,
                block_index,
                start,
                min(start + natural_block_width, shape[0]),
            )
        )
    residual, ownership_exact = _engine_residual(records, shape)
    change_control = max(
        records, key=lambda row: float(row["maximum_absolute_radiation_change"])
    )
    input_scale_control = max(
        records, key=lambda row: float(row["maximum_input_scale"])
    )
    mapped_scale_control = max(
        records, key=lambda row: float(row["maximum_mapped_scale"])
    )
    if float(input_scale_control["maximum_input_scale"]) >= float(
        mapped_scale_control["maximum_mapped_scale"]
    ):
        scale_control = input_scale_control
        scale_source = "input"
    else:
        scale_control = mapped_scale_control
        scale_source = "mapped"
    return {
        "shape": list(shape),
        "natural_frequency_block_width": natural_block_width,
        "natural_frequency_block_count": len(records),
        "frequency_ownership_exact": ownership_exact,
        "maximum_absolute_radiation_change": change_control[
            "maximum_absolute_radiation_change"
        ],
        "maximum_radiation_scale": max(
            float(input_scale_control["maximum_input_scale"]),
            float(mapped_scale_control["maximum_mapped_scale"]),
        ),
        "global_original_operator_residual": residual,
        "numerator_control": {
            key: change_control[key]
            for key in (
                "block_index",
                "controlling_frequency_group",
                "controlling_angle_index",
                "controlling_depth_index",
                "controlling_input_value",
                "controlling_mapped_value",
                "frequency_lower_hz",
                "frequency_upper_hz",
                "frequency_geometric_centre_hz",
                "energy_geometric_centre_ev",
            )
        },
        "scale_control": {
            "source_state": scale_source,
            "block_index": scale_control["block_index"],
            "frequency_group": scale_control["scale_frequency_group"],
            "angle_index": scale_control["scale_angle_index"],
            "depth_index": scale_control["scale_depth_index"],
            "absolute_scale": (
                scale_control["maximum_input_scale"]
                if scale_source == "input"
                else scale_control["maximum_mapped_scale"]
            ),
            **_group_coordinates(edges, int(scale_control["scale_frequency_group"])),
        },
        "blocks": records,
    }


def _validate_small_sources(root: Path, protocol: dict[str, object]) -> None:
    sources = protocol.get("sources", {})
    if not isinstance(sources, dict) or not sources:
        raise RuntimeError("7B9dt frozen source set is missing")
    for source in sources.values():
        _validate_source_claim(root, source)


def _validate_full_state_once(root: Path, claim: dict[str, object]) -> Path:
    path = root / _safe_relative(str(claim["path"]), dat_claim=True)
    if path.stat().st_size != int(claim["size_bytes"]):
        raise RuntimeError(f"7B9dt full-state size changed: {claim['path']}")
    if sha256(path) != claim["sha256"]:
        raise RuntimeError(f"7B9dt full-state SHA changed: {claim['path']}")
    return path


def _write_csv_atomic(path: Path, records: Iterable[dict[str, object]]) -> None:
    rows = list(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    fields = list(rows[0])
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _plot(path: Path, result: dict[str, object], target: float) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = result["blocks"]
    block = np.asarray([int(row["block_index"]) for row in rows])
    change = np.asarray(
        [float(row["maximum_absolute_radiation_change"]) for row in rows]
    )
    scale = np.asarray([float(row["maximum_radiation_scale"]) for row in rows])
    local = np.asarray(
        [float(row["block_relative_original_operator_residual"]) for row in rows]
    )
    energy = np.asarray(
        [float(row["energy_geometric_centre_ev"]) for row in rows]
    )
    figure, axes = plt.subplots(1, 2, figsize=(12.0, 4.8), constrained_layout=True)
    axes[0].plot(block, change, marker="o", ms=3, label="Maximum absolute change")
    axes[0].plot(block, scale, marker=".", ms=3, label="Maximum state scale")
    if np.any(change > 0.0) or np.any(scale > 0.0):
        axes[0].set_yscale("log")
    axes[0].set(
        xlabel="Natural frequency block",
        ylabel="Intensity-density magnitude",
        title="(a) Blockwise numerator and scale",
    )
    axes[0].legend(frameon=False)
    axes[1].plot(energy, local, marker="o", ms=3)
    axes[1].axhline(target, color="0.35", ls="--", label="Global target (reference)")
    if np.all(energy > 0.0):
        axes[1].set_xscale("log")
    if np.any(local > 0.0):
        axes[1].set_yscale("log")
    control = result["numerator_control"]
    axes[1].scatter(
        [float(control["energy_geometric_centre_ev"])],
        [float(rows[int(control["block_index"])]["block_relative_original_operator_residual"])],
        color="tab:red",
        zorder=4,
        label="Global numerator control",
    )
    axes[1].set(
        xlabel="Controlling-group energy (eV)",
        ylabel="Block relative residual",
        title="(b) Slow-mode location by frequency",
    )
    axes[1].legend(frameon=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_locator(
    root: Path, protocol_path: Path, expected_protocol_sha256: str
) -> dict[str, object]:
    if sha256(protocol_path) != expected_protocol_sha256:
        raise RuntimeError("frozen 7B9dt locator protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    _validate_small_sources(root, protocol)
    claims = protocol["full_state_claims"]
    # 中文：父分析进程在读 memmap 前，各对两个完整态只做一次全文件 SHA 守卫。
    input_path = _validate_full_state_once(root, claims["input_state"])
    mapped_path = _validate_full_state_once(root, claims["mapped_state"])
    cfg = protocol["configuration"]
    shape = (
        int(cfg["physical_frequency_groups"]),
        int(cfg["angular_direction_count"]),
        int(cfg["radiation_depth_cell_count"]),
    )
    input_state = np.memmap(input_path, mode="r", dtype=np.float64, shape=shape)
    mapped_state = np.memmap(mapped_path, mode="r", dtype=np.float64, shape=shape)
    with np.load(root / protocol["sources"]["frequency_grid"]["path"], allow_pickle=False) as payload:
        edges = np.asarray(payload["active_edge_hz"], dtype=np.float64)
    result = analyze_arrays(
        input_state,
        mapped_state,
        edges,
        int(cfg["core_frequency_groups"]),
    )
    reference = float(cfg["reference_global_original_operator_residual"])
    tolerance = float(protocol["gates"]["residual_reproduction_absolute_tolerance"])
    reproduced = abs(float(result["global_original_operator_residual"]) - reference) <= tolerance
    block_json = root / cfg["block_json_path"]
    block_csv = root / cfg["block_csv_path"]
    figure = root / cfg["figure_path"]
    _write_json_atomic(
        block_json,
        {
            "phase": protocol["phase"],
            "protocol_sha256": expected_protocol_sha256,
            "residual_definition": "max(abs(mapped-input))/max(max(abs(input)),max(abs(mapped)))",
            "blocks": result["blocks"],
        },
    )
    _write_csv_atomic(block_csv, result["blocks"])
    _plot(figure, result, GLOBAL_RESIDUAL_TARGET)
    summary = {
        "phase": protocol["phase"],
        "classification": "[V-two-state-slow-mode-diagnostic]+[O-not-convergence-proof]",
        "protocol_sha256": expected_protocol_sha256,
        "status": "complete" if reproduced else "residual_reproduction_failed",
        "input_state": dict(claims["input_state"]),
        "mapped_state": dict(claims["mapped_state"]),
        "reference_global_original_operator_residual": reference,
        **{key: value for key, value in result.items() if key != "blocks"},
        "block_json_path": cfg["block_json_path"],
        "block_json_sha256": sha256(block_json),
        "block_csv_path": cfg["block_csv_path"],
        "block_csv_sha256": sha256(block_csv),
        "figure_path": cfg["figure_path"],
        "figure_sha256": sha256(figure),
        "gate_checks": {
            "frequency_ownership_pass": result["frequency_ownership_exact"] is True,
            "original_operator_residual_exactly_reproduced": reproduced,
            "target_unchanged_pass": protocol["gates"][
                "global_original_operator_residual_below"
            ]
            == GLOBAL_RESIDUAL_TARGET,
        },
        "decision": {
            "slow_mode_location_is_diagnostic_only": True,
            "convergence_proven": False,
            "material_feedback_authorized": False,
            "radiation_update_authorized": False,
        },
    }
    _write_json_atomic(root / cfg["summary_path"], summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expected-protocol-sha256", required=True)
    args = parser.parse_args()
    run_locator(ROOT, args.protocol, args.expected_protocol_sha256)


if __name__ == "__main__":
    main()
