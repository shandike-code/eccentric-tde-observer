"""Phase 7B9s：复用两块证据并补齐 H I/软 X 的完整源 Krylov 门。"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from scripts import phase7b9r_full_source_krylov_line_search as prior
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9r_full_source_krylov_line_search as prior  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "24155871acbc4796253ecab5f9d0b4b0a4b04a5a2bd4f797c47555206e07c67d"
)
base = prior.base


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9s protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9s source changed: {source['path']}"
                )
    return protocol


def _worker_protocol(protocol: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(protocol)
    result["configuration"]["selected_blocks"] = [
        *result["configuration"]["retained_blocks"],
        *result["configuration"]["new_blocks"],
    ]
    return result


def _run_worker(protocol_path: Path, block_index: int, report_path: Path) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    new = {
        int(row["block_index"])
        for row in protocol["configuration"]["new_blocks"]
    }
    if block_index not in new:
        raise ValueError("Phase 7B9s worker must be one of the new frozen blocks")
    prior._run_worker(
        protocol_path,
        block_index,
        report_path,
        protocol_override=_worker_protocol(protocol),
    )


def _plot(
    path: Path,
    reports: list[dict[str, object]],
    gates: dict[str, object],
    *,
    full_map_authorized: bool,
) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(14.0, 4.4), constrained_layout=True)
    block = np.asarray([row["block_index"] for row in reports])
    residual = np.asarray(
        [row["fresh_line_candidate_to_raw_residual_ratio"] for row in reports]
    )
    boundary = np.asarray(
        [row["fresh_line_candidate_to_raw_boundary_ratio"] for row in reports]
    )
    width = 0.34
    axes[0].bar(block - width / 2, residual, width, label="Interior residual")
    axes[0].bar(block + width / 2, boundary, width, label="Boundary spectrum")
    axes[0].axhline(
        gates["each_fresh_line_candidate_to_raw_residual_ratio_below"],
        color="0.25",
        ls="--",
        label="Interior gate",
    )
    axes[0].set(
        xlabel="Natural frequency block",
        ylabel="Line candidate / raw residual",
        title="(a) Four-block original-operator gate",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].bar(
        block,
        [row["line_selected_fraction"] for row in reports],
        color="tab:green",
    )
    axes[1].axhline(
        gates["each_selected_line_fraction_at_least"],
        color="0.25",
        ls="--",
        label="Useful-step gate",
    )
    axes[1].set(
        xlabel="Natural frequency block",
        ylabel="Selected endpoint fraction",
        title="(b) Exact affine line search",
    )
    axes[1].legend(frameon=False, fontsize=8)
    axes[2].axis("off")
    axes[2].text(
        0.03,
        0.95,
        "(c) Full-source four-block decision\n\n"
        f"Residual ratios = {[round(value, 4) for value in residual]}\n"
        f"Boundary ratios = {[round(value, 4) for value in boundary]}\n"
        f"GMRES iterations = "
        f"{[row['gmres_iteration_count'] for row in reports]}\n\n"
        f"One full-frequency map authorized: {full_map_authorized}\n"
        "Material feedback: not evaluated",
        transform=axes[2].transAxes,
        va="top",
        fontsize=10.5,
    )
    axes[0].set_xticks(block)
    axes[1].set_xticks(block)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    retained_paths = [
        ROOT / protocol["sources"][f"retained_phase7b9r_block{int(row['block_index']):02d}"]["path"]
        for row in protocol["configuration"]["retained_blocks"]
    ]
    new_indices = [
        int(row["block_index"]) for row in protocol["configuration"]["new_blocks"]
    ]
    new_paths = [
        OUTPUT / f"phase7b9s_block{index:02d}_full_source_krylov.json"
        for index in new_indices
    ]
    for block_index, report_path in zip(new_indices, new_paths, strict=True):
        process = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                "--protocol",
                str(protocol_path),
                "--block-index",
                str(block_index),
                "--worker-report",
                str(report_path),
            ],
            cwd=ROOT,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"Phase 7B9s worker {block_index} failed: {process.returncode}"
            )
    reports = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (*retained_paths, *new_paths)
    ]
    reports.sort(key=lambda row: int(row["block_index"]))
    gates = protocol["gates"]
    fresh = np.asarray(
        [row["fresh_line_candidate_to_raw_residual_ratio"] for row in reports]
    )
    boundary = np.asarray(
        [row["fresh_line_candidate_to_raw_boundary_ratio"] for row in reports]
    )
    runtime_multiplier = float(
        sum(row["application_runtime_s"] for row in reports)
        / sum(row["historical_one_update_runtime_s"] for row in reports)
    )
    map6_wall = json.loads(
        (OUTPUT / "phase7b9k_block_aitken_pilot_summary.json").read_text(
            encoding="utf-8"
        )
    )["history"][-1]["wall_runtime_s"]
    projected_wall = float(map6_wall) * runtime_multiplier
    checks = {
        "representative_coverage_complete": len(reports)
        == gates["selected_block_count_exactly"],
        "finite_work_krylov_budget_passes": all(
            row["gmres_iteration_count"]
            <= gates["each_gmres_iteration_count_at_most"]
            for row in reports
        ),
        "endpoint_positive_steps_pass": all(
            row["endpoint_exact_nonnegative_step"]
            >= gates["each_endpoint_exact_nonnegative_step_at_least"]
            for row in reports
        ),
        "line_search_steps_are_useful": all(
            row["line_selected_fraction"]
            >= gates["each_selected_line_fraction_at_least"]
            for row in reports
        ),
        "every_fresh_line_residual_improves_enough": bool(
            np.all(
                fresh
                < gates[
                    "each_fresh_line_candidate_to_raw_residual_ratio_below"
                ]
            )
        ),
        "median_fresh_line_residual_improves_enough": float(np.median(fresh))
        < gates["median_fresh_line_candidate_to_raw_residual_ratio_below"],
        "boundary_residuals_do_not_worsen": bool(
            np.all(
                boundary
                <= gates["each_fresh_line_candidate_boundary_ratio_at_most"]
            )
        ),
        "affine_prediction_is_faithful": all(
            row["affine_prediction_to_fresh_residual_linf"]
            < gates["each_affine_prediction_to_fresh_residual_linf_below"]
            for row in reports
        ),
        "candidates_finite_nonnegative_and_within_memory": all(
            row["minimum_line_candidate_intensity"]
            >= gates["minimum_line_candidate_intensity_at_least"]
            and row["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            for row in reports
        ),
        "selected_runtime_multiplier_passes": runtime_multiplier
        < gates["selected_runtime_multiplier_over_one_map_below"],
        "projected_full_map_cost_passes": projected_wall
        < gates["projected_full_map_wall_time_strictly_below_s"],
    }
    passed = all(checks.values())
    decision = {
        "full_source_krylov_four_block_gate_passed": passed,
        "one_full_frequency_full_source_krylov_map_authorized": passed,
        "full_frequency_accelerated_map_evaluated": False,
        "trial_formal_feedback_evaluated": False,
        "trial_true_residual_evaluated": False,
        "accepted_as_dynamic_nlte_solution": False,
        "phase7b9s_gate_passed": passed,
    }
    figure = OUTPUT / "phase7b9s_four_block_full_source_gate.png"
    _plot(figure, reports, gates, full_map_authorized=passed)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "reports": reports,
        "maximum_fresh_line_candidate_to_raw_residual_ratio": float(np.max(fresh)),
        "median_fresh_line_candidate_to_raw_residual_ratio": float(np.median(fresh)),
        "selected_application_runtime_multiplier_over_one_update": runtime_multiplier,
        "projected_full_map_wall_time_s": projected_wall,
        "gate_checks": checks,
        "decision": decision,
        "figures": [figure.name],
    }
    base._write_json_atomic(
        OUTPUT / "phase7b9s_four_block_full_source_gate_summary.json", summary
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9s_preregistered_four_block_full_source_gate.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.block_index is None or args.worker_report is None:
            raise ValueError("worker mode requires block index and report path")
        _run_worker(args.protocol, args.block_index, args.worker_report)
        return
    summary = run(args.protocol)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
