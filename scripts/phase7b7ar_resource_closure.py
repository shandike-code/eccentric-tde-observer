"""Phase 7B7a-r：以一块一进程逐位复现超限工作组的反馈系数。"""

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
    from scripts.phase7b7a_feedback_coefficients import _zero_partials
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b7a_feedback_coefficients import _zero_partials  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "a59cf7c39f56f66bcb73ce50ed7163c382c011d593fcda7061eceb50b0b418fb"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B7a-r protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B7a-r source changed: {source['path']}")
    return protocol


def _plot(
    path: Path,
    owner_difference: dict[str, float],
    reports: list[dict[str, object]],
    wall_runtime: float,
) -> None:
    rss = [float(report["peak_process_rss_mib"]) for report in reports]
    runtime = [float(report["runtime_s"]) for report in reports]
    block = [int(report["rows"][0]["block_index"]) for report in reports]
    figure, axes = plt.subplots(1, 3, figsize=(13.5, 4.0), constrained_layout=True)
    axes[0].bar(
        [f"Owner {int(owner) + 1}" for owner in owner_difference],
        list(owner_difference.values()),
        color="#4c78a8",
    )
    axes[0].set(
        ylabel="Maximum absolute difference",
        title="(a) Reaggregated partial reproduction",
    )
    if all(value == 0.0 for value in owner_difference.values()):
        axes[0].text(
            0.5,
            0.5,
            "Bitwise identical\n(maximum difference = 0)",
            transform=axes[0].transAxes,
            ha="center",
            va="center",
        )
    axes[1].scatter(block, rss, s=28, color="#72b7b2")
    axes[1].axhline(6144.0, color="0.25", ls="--", label="Frozen process gate")
    axes[1].set(
        xlabel="Frequency block index",
        ylabel="Peak RSS (MiB)",
        title="(b) Isolated-block memory",
    )
    axes[1].legend(frameon=False)
    axes[2].scatter(block, runtime, s=28, color="#f58518")
    axes[2].set(
        xlabel="Frequency block index",
        ylabel="Process runtime (s)",
        title=f"(c) Isolated cost; total wall={wall_runtime:.0f} s",
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    original_protocol = OUTPUT / "phase7b7a_preregistered_feedback_coefficients.json"
    target_rows = [
        (int(owner), int(block))
        for owner, blocks in configuration["target_blocks_by_owner"].items()
        for block in blocks
    ]
    output_pairs = {
        (owner, block): (
            OUTPUT / f"phase7b7ar_owner{owner + 1}_block{block:02d}_partial.npz",
            OUTPUT / f"phase7b7ar_owner{owner + 1}_block{block:02d}.json",
        )
        for owner, block in target_rows
    }
    started = time.perf_counter()
    maximum_concurrency = int(configuration["maximum_concurrent_processes"])
    for offset in range(0, len(target_rows), maximum_concurrency):
        batch = target_rows[offset : offset + maximum_concurrency]
        processes = []
        for owner, block in batch:
            partial, report = output_pairs[(owner, block)]
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(ROOT / "scripts/phase7b7a_feedback_coefficients.py"),
                        "--worker",
                        "--protocol",
                        str(original_protocol),
                        "--worker-index",
                        str(owner),
                        "--block-index",
                        str(block),
                        "--partial",
                        str(partial),
                        "--worker-report",
                        str(report),
                    ],
                    cwd=ROOT,
                )
            )
        return_codes = [process.wait() for process in processes]
        if any(code != 0 for code in return_codes):
            raise RuntimeError(f"Phase 7B7a-r isolated batch failed: {return_codes}")
    wall_runtime = time.perf_counter() - started
    reports = [
        json.loads(output_pairs[row][1].read_text(encoding="utf-8"))
        for row in target_rows
    ]
    owner_difference: dict[str, float] = {}
    array_difference: dict[str, dict[str, float]] = {}
    for owner_string, blocks in configuration["target_blocks_by_owner"].items():
        owner = int(owner_string)
        reaggregated = _zero_partials(4096)
        for block in sorted(int(value) for value in blocks):
            partial_path, report_path = output_pairs[(owner, block)]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if _sha256(partial_path) != report["partial_sha256"]:
                raise RuntimeError("Phase 7B7a-r isolated partial hash changed")
            with np.load(partial_path) as archive:
                for name in reaggregated:
                    reaggregated[name] += np.asarray(archive[name])
        original_path = OUTPUT / f"phase7b7a_worker{owner + 1}_partial.npz"
        with np.load(original_path) as original:
            differences = {
                name: float(np.max(np.abs(reaggregated[name] - original[name])))
                for name in reaggregated
            }
        array_difference[owner_string] = differences
        owner_difference[owner_string] = max(differences.values())
    rss = [float(report["peak_process_rss_mib"]) for report in reports]
    completed_blocks = [int(report["rows"][0]["block_index"]) for report in reports]
    gates = protocol["gates"]
    upstream = json.loads(
        (OUTPUT / "phase7b7a_feedback_coefficients_summary.json").read_text(
            encoding="utf-8"
        )
    )
    upstream_science_passed = all(
        upstream["decision"][name]
        for name in (
            "frozen_protocol_source_and_state_hashes_passed",
            "worker_block_and_frequency_ownership_passed",
            "comoving_intensity_rates_and_arrays_valid",
            "rate_heating_vs_inverse_four_force_passed",
            "parent_mirror_symmetry_passed",
        )
    )
    decision = {
        "frozen_protocol_and_source_hashes_passed": True,
        "retained_phase7b7a_science_gates_passed": bool(upstream_science_passed),
        "target_block_coverage_passed": bool(
            len(configuration["failed_owner_indices"])
            == gates["failed_owner_count_exactly"]
            and len(completed_blocks) == gates["target_block_count_exactly"]
            and sorted(completed_blocks) == sorted(block for _, block in target_rows)
            and all(report["assigned_block_count"] == 1 for report in reports)
        ),
        "bitwise_partial_reproduction_passed": all(
            value
            == gates["each_reaggregated_partial_maximum_absolute_difference_exactly"]
            for value in owner_difference.values()
        ),
        "isolated_resource_and_runtime_gates_passed": bool(
            all(value < gates["each_process_peak_rss_strictly_below_mib"] for value in rss)
            and wall_runtime < gates["total_wall_time_strictly_below_s"]
        ),
        "fully_coupled_iteration_authorized": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b7ar_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_and_source_hashes_passed",
            "retained_phase7b7a_science_gates_passed",
            "target_block_coverage_passed",
            "bitwise_partial_reproduction_passed",
            "isolated_resource_and_runtime_gates_passed",
        )
    )
    decision["one_frozen_radiation_matter_update_authorized"] = bool(
        decision["phase7b7ar_gate_passed"]
    )
    figure_path = OUTPUT / "phase7b7ar_resource_closure.png"
    _plot(figure_path, owner_difference, reports, wall_runtime)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "target_block_count": len(completed_blocks),
        "completed_blocks": completed_blocks,
        "owner_maximum_absolute_differences": owner_difference,
        "array_maximum_absolute_differences": array_difference,
        "process_peak_rss_mib": rss,
        "maximum_process_peak_rss_mib": max(rss),
        "total_wall_runtime_s": wall_runtime,
        "reports": [
            str(output_pairs[row][1].relative_to(ROOT)) for row in target_rows
        ],
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(OUTPUT / "phase7b7ar_resource_closure_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b7ar_preregistered_resource_closure.json",
    )
    args = parser.parse_args()
    summary = run(args.protocol)
    print(json.dumps(summary["decision"], indent=2))


if __name__ == "__main__":
    main()
