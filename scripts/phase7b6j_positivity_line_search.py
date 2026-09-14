"""Phase 7B6j：比较正性边界整步线搜索与固定 1.8 全频控制。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from scripts.phase7b6f_full_frequency_contraction import (
        _shape,
        _write_json_atomic,
    )
    from scripts.phase7b6h_full_frequency_aitken import _apply_weight
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b6f_full_frequency_contraction import (  # type: ignore[no-redef]
        _shape,
        _write_json_atomic,
    )
    from phase7b6h_full_frequency_aitken import (  # type: ignore[no-redef]
        _apply_weight,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "8d07aed42c30bb22614169aa2976bfd94532ea6b0c3686425566341fccd96ec7"
)
MIB = 1024**2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B6j protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6j source changed: {source['path']}")
    return protocol


def _allocate(path: Path, shape: tuple[int, int, int]) -> None:
    array = np.memmap(path, mode="w+", dtype=np.float64, shape=shape)
    array.flush()
    del array


def _run_map(
    protocol: dict[str, object],
    global_iteration: int,
    label: str,
    current_path: Path,
    previous_residual_path: Path,
    output_path: Path,
    residual_output_path: Path,
) -> dict[str, object]:
    configuration = protocol["configuration"]
    process_count = int(configuration["process_count"])
    worker_script = ROOT / protocol["sources"]["phase7b6h_worker"]["path"]
    worker_protocol = ROOT / protocol["sources"]["phase7b6h_protocol"]["path"]
    report_paths = []
    processes = []
    started = time.perf_counter()
    for worker_index in range(process_count):
        report_path = OUTPUT / (
            f"phase7b6j_{label}_worker{worker_index + 1}.json"
        )
        report_paths.append(report_path)
        command = [
            sys.executable,
            str(worker_script),
            "--worker",
            "--protocol",
            str(worker_protocol),
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
        raise RuntimeError(f"Phase 7B6j map {label} failed: {return_codes}")
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    rows = sorted(
        [row for report in reports for row in report["rows"]],
        key=lambda row: row["core_group_start"],
    )
    shape = _shape(protocol)
    coverage = bool(
        len(rows) == int(configuration["block_count"])
        and rows[0]["core_group_start"] == 0
        and rows[-1]["core_group_stop"] == shape[0]
        and all(
            first["core_group_stop"] == second["core_group_start"]
            for first, second in zip(rows[:-1], rows[1:], strict=True)
        )
    )
    maximum_absolute = max(row["maximum_absolute_change"] for row in rows)
    maximum_scale = max(row["maximum_scale"] for row in rows)
    return {
        "label": label,
        "global_iteration": global_iteration,
        "block_count": len(rows),
        "unique_full_group_coverage": coverage,
        "raw_fixed_point_residual": (
            maximum_absolute / maximum_scale
            if maximum_scale > 0.0
            else maximum_absolute
        ),
        "aitken_numerator": sum(row["aitken_numerator"] for row in rows),
        "aitken_denominator": sum(row["aitken_denominator"] for row in rows),
        "wall_runtime_s": time.perf_counter() - started,
        "maximum_worker_peak_rss_mib": max(
            report["peak_process_rss_mib"] for report in reports
        ),
        "worker_reports": reports,
    }


def _positivity_bound(
    current_path: Path,
    residual_path: Path,
    shape: tuple[int, int, int],
    chunk_groups: int,
) -> float:
    current = np.memmap(current_path, mode="r", dtype=np.float64, shape=shape)
    residual = np.memmap(residual_path, mode="r", dtype=np.float64, shape=shape)
    bound = np.inf
    for start in range(0, shape[0], chunk_groups):
        stop = min(start + chunk_groups, shape[0])
        local_current = np.asarray(current[start:stop])
        local_residual = np.asarray(residual[start:stop])
        decreasing = local_residual < 0.0
        if np.any(decreasing):
            ratios = local_current[decreasing] / (-local_residual[decreasing])
            if not np.all(np.isfinite(ratios)) or float(np.min(ratios)) <= 0.0:
                raise ArithmeticError("global positivity bound became non-positive")
            bound = min(bound, float(np.min(ratios)))
    return float(bound)


def _line_weight(aitken_weight: float, positivity_bound: float) -> float:
    if not np.isfinite(aitken_weight) or aitken_weight <= 0.0:
        raise ArithmeticError("Aitken weight is not positive finite")
    if np.isinf(positivity_bound) or aitken_weight < positivity_bound:
        return aitken_weight
    weight = float(np.nextafter(positivity_bound, 0.0))
    if not np.isfinite(weight) or weight <= 0.0 or not weight < positivity_bound:
        raise ArithmeticError("floating predecessor of positivity bound is invalid")
    return weight


def _write_trial(
    current_path: Path,
    residual_path: Path,
    output_path: Path,
    shape: tuple[int, int, int],
    omega: float,
    chunk_groups: int,
) -> float:
    current = np.memmap(current_path, mode="r", dtype=np.float64, shape=shape)
    residual = np.memmap(residual_path, mode="r", dtype=np.float64, shape=shape)
    output = np.memmap(output_path, mode="r+", dtype=np.float64, shape=shape)
    minimum = np.inf
    for start in range(0, shape[0], chunk_groups):
        stop = min(start + chunk_groups, shape[0])
        trial = current[start:stop] + omega * residual[start:stop]
        if not np.all(np.isfinite(trial)) or float(np.min(trial)) < 0.0:
            raise ArithmeticError("whole-state branch trial violated positivity")
        minimum = min(minimum, float(np.min(trial)))
        output[start:stop] = trial
    output.flush()
    return float(minimum)


def _plot(
    path: Path,
    common: dict[str, object],
    line: dict[str, object],
    control: dict[str, object],
    weights: tuple[float, float],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].bar(
        ["Iteration 13", "Line iteration 14", "Control iteration 14"],
        [
            common["raw_fixed_point_residual"],
            line["raw_fixed_point_residual"],
            control["raw_fixed_point_residual"],
        ],
        color=["#777777", "#4c78a8", "#f58518"],
    )
    axes[0, 0].set_yscale("log")
    axes[0, 0].set(ylabel="Raw fixed-point residual", title="(a) Branched comparison")
    axes[0, 1].bar(
        ["Line 13", "Line 14", "Fixed control"],
        [weights[0], weights[1], 1.8],
        color=["#4c78a8", "#72b7b2", "#f58518"],
    )
    axes[0, 1].set(ylabel="Accepted weight", title="(b) Positivity-boundary weights")
    axes[1, 0].bar(
        ["Line / control", "Line / iteration 13"],
        [
            line["raw_fixed_point_residual"] / control["raw_fixed_point_residual"],
            line["raw_fixed_point_residual"] / common["raw_fixed_point_residual"],
        ],
        color=["#54a24b", "#e45756"],
    )
    axes[1, 0].axhline(1.0, color="0.25", ls="--", label="No improvement")
    axes[1, 0].set(ylabel="Residual ratio", title="(c) Fixed-cost gain")
    axes[1, 0].legend(frameon=False)
    maps = [common, line, control]
    axes[1, 1].bar(
        ["Common 13", "Line 14", "Control 14"],
        [row["wall_runtime_s"] for row in maps],
        color=["#777777", "#4c78a8", "#f58518"],
    )
    axes[1, 1].set(ylabel="Wall runtime (s)", title="(d) Three-map cost")
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    shape = _shape(protocol)
    chunk_groups = int(configuration["core_frequency_groups"])
    initial = protocol["initial_checkpoint"]
    current12 = ROOT / initial["state_path"]
    residual12 = ROOT / initial["residual_path"]
    if _sha256(current12) != initial["state_sha256"]:
        raise RuntimeError("Phase 7B6j initial state hash changed")
    if _sha256(residual12) != initial["residual_sha256"]:
        raise RuntimeError("Phase 7B6j initial residual hash changed")
    original_manifest = ROOT / protocol["sources"]["phase7b6i_manifest"]["path"]
    original_manifest_hash = _sha256(original_manifest)
    line_checkpoint = ROOT / configuration["line_branch_state_checkpoint"]
    residual_checkpoint = ROOT / configuration["line_branch_residual_checkpoint"]
    for path in (line_checkpoint, residual_checkpoint):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite Phase 7B6j checkpoint: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)

    common = None
    line_map = None
    control_map = None
    line_weight13 = None
    line_weight14 = None
    minimum_values = []
    temporary_paths = []
    with tempfile.TemporaryDirectory(
        prefix="phase7b6j_", dir=line_checkpoint.parent
    ) as temporary_name:
        temporary = Path(temporary_name)
        mapped13 = temporary / "line_state13.dat"
        residual13 = temporary / "residual13.dat"
        control13 = temporary / "control_state13.dat"
        mapped_line14 = temporary / "line_state14.dat"
        residual_line14 = temporary / "line_residual14.dat"
        mapped_control14 = temporary / "control_map14.dat"
        residual_control14 = temporary / "control_residual14.dat"
        temporary_paths = [
            mapped13,
            residual13,
            control13,
            mapped_line14,
            residual_line14,
            mapped_control14,
            residual_control14,
        ]
        for path in temporary_paths:
            _allocate(path, shape)
        common = _run_map(
            protocol,
            int(configuration["common_map_iteration"]),
            "common13",
            current12,
            residual12,
            mapped13,
            residual13,
        )
        candidate13 = (
            -float(initial["previous_accepted_weight"])
            * common["aitken_numerator"]
            / common["aitken_denominator"]
        )
        bound13 = _positivity_bound(current12, residual13, shape, chunk_groups)
        line_weight13 = _line_weight(candidate13, bound13)
        minimum_values.append(
            _apply_weight(
                current12, mapped13, shape, line_weight13, chunk_groups
            )
        )
        minimum_values.append(
            _write_trial(
                current12,
                residual13,
                control13,
                shape,
                float(configuration["fixed_control_weight"]),
                chunk_groups,
            )
        )

        line_map = _run_map(
            protocol,
            int(configuration["comparison_map_iteration"]),
            "line14",
            mapped13,
            residual13,
            mapped_line14,
            residual_line14,
        )
        candidate14 = (
            -line_weight13
            * line_map["aitken_numerator"]
            / line_map["aitken_denominator"]
        )
        bound14 = _positivity_bound(
            mapped13, residual_line14, shape, chunk_groups
        )
        line_weight14 = _line_weight(candidate14, bound14)
        minimum_values.append(
            _apply_weight(
                mapped13,
                mapped_line14,
                shape,
                line_weight14,
                chunk_groups,
            )
        )

        control_map = _run_map(
            protocol,
            int(configuration["comparison_map_iteration"]),
            "control14",
            control13,
            residual13,
            mapped_control14,
            residual_control14,
        )
        line_state_hash = _sha256(mapped_line14)
        line_residual_hash = _sha256(residual_line14)
        os.replace(mapped_line14, line_checkpoint)
        os.replace(residual_line14, residual_checkpoint)
    temporary_removed = all(not path.exists() for path in temporary_paths)
    original_manifest_unchanged = _sha256(original_manifest) == original_manifest_hash
    finite_values = [
        common["raw_fixed_point_residual"],
        line_map["raw_fixed_point_residual"],
        control_map["raw_fixed_point_residual"],
        line_weight13,
        line_weight14,
        *minimum_values,
    ]
    all_maps = (common, line_map, control_map)
    decision = {
        "frozen_protocol_hash_passed": True,
        "source_initial_hashes_and_original_manifest_passed": original_manifest_unchanged,
        "all_maps_complete": all(
            row["block_count"] == gates["each_map_block_count_exactly"]
            and row["unique_full_group_coverage"]
            for row in all_maps
        ),
        "line_weights_above_control": bool(
            line_weight13 > gates["line_search_weight_strictly_above_control"]
            and line_weight14 > gates["line_search_weight_strictly_above_control"]
        ),
        "all_states_nonnegative_and_finite": bool(
            min(minimum_values) >= 0.0
            and all(np.isfinite(value) for value in finite_values)
        ),
        "line_beats_fixed_control": line_map["raw_fixed_point_residual"]
        < control_map["raw_fixed_point_residual"],
        "line_contraction_gate_passed": line_map["raw_fixed_point_residual"]
        / common["raw_fixed_point_residual"]
        < gates["line_iteration14_residual_strictly_below_iteration13_fraction"],
        "resource_and_runtime_gates_passed": all(
            row["maximum_worker_peak_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and row["wall_runtime_s"] < gates["each_map_wall_time_strictly_below_s"]
            for row in all_maps
        ),
        "checkpoint_and_cleanup_passed": bool(
            line_checkpoint.stat().st_size
            == gates["each_retained_checkpoint_size_bytes_exactly"]
            and residual_checkpoint.stat().st_size
            == gates["each_retained_checkpoint_size_bytes_exactly"]
            and temporary_removed
        ),
        "full_column_fixed_point_authorized": False,
        "matter_feedback_authorized": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b6j_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "source_initial_hashes_and_original_manifest_passed",
            "all_maps_complete",
            "line_weights_above_control",
            "all_states_nonnegative_and_finite",
            "line_beats_fixed_control",
            "line_contraction_gate_passed",
            "resource_and_runtime_gates_passed",
            "checkpoint_and_cleanup_passed",
        )
    )
    decision["line_search_fixed_point_continuation_authorized"] = bool(
        decision["phase7b6j_gate_passed"]
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "common_iteration13": common,
        "line_iteration14": line_map,
        "control_iteration14": control_map,
        "line_weight13": line_weight13,
        "line_weight14": line_weight14,
        "line_to_control_iteration14_residual_fraction": (
            line_map["raw_fixed_point_residual"]
            / control_map["raw_fixed_point_residual"]
        ),
        "line_iteration14_to_iteration13_residual_fraction": (
            line_map["raw_fixed_point_residual"]
            / common["raw_fixed_point_residual"]
        ),
        "line_checkpoint_path": str(line_checkpoint.relative_to(ROOT)),
        "line_checkpoint_sha256": line_state_hash,
        "line_residual_checkpoint_path": str(residual_checkpoint.relative_to(ROOT)),
        "line_residual_checkpoint_sha256": line_residual_hash,
        "original_phase7b6i_manifest_unchanged": original_manifest_unchanged,
        "temporary_branch_states_removed": temporary_removed,
        "decision": decision,
        "figures": ["phase7b6j_positivity_line_search.png"],
    }
    _write_json_atomic(
        OUTPUT / "phase7b6j_positivity_line_search_summary.json", summary
    )
    _plot(
        OUTPUT / "phase7b6j_positivity_line_search.png",
        common,
        line_map,
        control_map,
        (line_weight13, line_weight14),
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6j_preregistered_positivity_line_search.json",
    )
    args = parser.parse_args()
    summary = run(args.protocol)
    print(json.dumps(summary["decision"], indent=2))


if __name__ == "__main__":
    main()
