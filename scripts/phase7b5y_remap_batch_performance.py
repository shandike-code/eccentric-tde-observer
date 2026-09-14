"""Phase 7B5y：复验增大独立列批次后的精确输出、时间和内存。"""

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
    from scripts import phase7b5x_full_depth_block_probe as phase7b5x
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b5x_full_depth_block_probe as phase7b5x  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "539c6dab827e1e501e36be1ae39d4795a8c56a93e8051fdd82db169f4c6e0c85"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B5y protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    # baseline 频率文件已经由协议授权替换；其旧哈希只作为冻结对照保留。
    for name, source in protocol["sources"].items():
        if name == "mixed_frame_frequency_baseline":
            continue
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B5y source changed: {source['path']}")
    return protocol


def run_worker(protocol_path: Path, output_path: Path) -> None:
    protocol = _load_protocol(protocol_path)
    # 中文：复用已经冻结的 7B5x 物理上下文；这里只替换预先验证过的协议入口。
    original_loader = phase7b5x._load_protocol
    phase7b5x._load_protocol = lambda _path: protocol
    try:
        phase7b5x.run_worker(protocol_path, output_path)
    finally:
        phase7b5x._load_protocol = original_loader


def _relative(candidate: float, reference: float) -> float:
    scale = max(abs(candidate), abs(reference))
    return abs(candidate - reference) / scale if scale > 0.0 else abs(candidate - reference)


def _plot(path: Path, protocol: dict[str, object], runs: list[dict[str, object]]) -> None:
    baseline = protocol["baseline"]
    operator = np.array([run["operator_runtime_s"] for run in runs])
    rss = np.array([run["peak_process_rss_mib"] for run in runs])
    figure, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    axes[0].bar(
        ["Baseline", "Candidate\nmedian"],
        [baseline["operator_runtime_s"], float(np.median(operator))],
        color=["#777777", "#4c78a8"],
    )
    axes[0].axhline(
        protocol["gates"]["median_operator_runtime_strictly_below_s"],
        color="#333333",
        linestyle="--",
        label="Gate",
    )
    axes[0].set(ylabel="Operator runtime (s)", title="(a) Worst-block runtime")
    axes[0].legend()
    axes[1].bar(
        ["Baseline", "Candidate\nmaximum", "Process gate"],
        [baseline["peak_process_rss_mib"], float(np.max(rss)), 6144.0],
        color=["#777777", "#f58518", "#555555"],
    )
    axes[1].set(ylabel="Peak RSS (MiB)", title="(b) Memory trade-off")
    axes[2].bar(
        ["Run 1", "Run 2"],
        [
            float(run["final_intensity_sha256"] == baseline["final_intensity_sha256"])
            for run in runs
        ],
        color="#54a24b",
    )
    axes[2].set(ylim=(0, 1.15), ylabel="Exact hash match", title="(c) Output identity")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b5y_preregistered_remap_batch_performance.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--worker-output", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.worker_output is None:
            raise ValueError("--worker-output is required in worker mode")
        run_worker(args.protocol, args.worker_output)
        return

    protocol = _load_protocol(args.protocol)
    runs = []
    walls = []
    for repeat in range(int(protocol["candidate"]["repeat_count"])):
        output = OUTPUT / f"phase7b5y_repeat{repeat + 1}_worker.json"
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--protocol",
            str(args.protocol),
            "--worker-output",
            str(output),
        ]
        started = time.perf_counter()
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        walls.append(time.perf_counter() - started)
        if completed.returncode != 0:
            raise RuntimeError(
                f"Phase 7B5y repeat {repeat + 1} failed:\n"
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        print(completed.stdout, end="")
        runs.append(json.loads(output.read_text(encoding="utf-8")))

    baseline = protocol["baseline"]
    scalar_names = (
        "minimum_intensity",
        "one_iteration_fixed_point_change",
        "one_iteration_global_coupled_residual",
        "one_iteration_energy_ledger_residual",
    )
    scalar_errors = {
        f"repeat{index + 1}": {
            name: _relative(float(run[name]), float(baseline[name]))
            for name in scalar_names
        }
        for index, run in enumerate(runs)
    }
    gates = protocol["gates"]
    median_operator = float(np.median([run["operator_runtime_s"] for run in runs]))
    decision = {
        "frozen_protocol_hash_passed": True,
        "retained_source_hashes_passed": True,
        "all_output_hashes_exact": all(
            run["final_intensity_sha256"]
            == gates["each_final_intensity_sha256_exactly"]
            for run in runs
        ),
        "all_scalar_errors_passed": all(
            error < gates["each_scalar_relative_error_strictly_below"]
            for repeat in scalar_errors.values()
            for error in repeat.values()
        ),
        "operator_runtime_gate_passed": bool(
            median_operator < gates["median_operator_runtime_strictly_below_s"]
        ),
        "resource_gate_passed": all(
            run["peak_process_rss_mib"] < gates["each_peak_rss_strictly_below_mib"]
            for run in runs
        ),
        "nonnegative_and_finite_passed": all(
            run["minimum_intensity"] >= gates["each_minimum_intensity_at_least"]
            and run["all_reported_diagnostics_finite"]
            for run in runs
        ),
        "full_column_source_iteration_authorized": False,
        "full_column_fixed_point_authorized": False,
        "full_orbit_authorized": False,
        "matter_feedback_authorized": False,
    }
    decision["phase7b5y_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "retained_source_hashes_passed",
            "all_output_hashes_exact",
            "all_scalar_errors_passed",
            "operator_runtime_gate_passed",
            "resource_gate_passed",
            "nonnegative_and_finite_passed",
        )
    )
    decision["candidate_accepted"] = bool(decision["phase7b5y_gate_passed"])
    summary = {
        "phase": "7B5y remap independent-column batch performance gate",
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "candidate_mixed_frame_frequency_sha256": _sha256(
            ROOT / "src/eccentric_tde_observer/mixed_frame_frequency.py"
        ),
        "runs": runs,
        "fresh_process_wall_s": walls,
        "scalar_relative_errors": scalar_errors,
        "median_operator_runtime_s": median_operator,
        "operator_speedup": baseline["operator_runtime_s"] / median_operator,
        "maximum_peak_rss_mib": max(run["peak_process_rss_mib"] for run in runs),
        "decision": decision,
        "figures": ["phase7b5y_remap_batch_performance.png"],
    }
    _write_json_atomic(OUTPUT / "phase7b5y_remap_batch_performance_summary.json", summary)
    _plot(OUTPUT / "phase7b5y_remap_batch_performance.png", protocol, runs)
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
