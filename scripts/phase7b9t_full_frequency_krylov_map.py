"""Phase 7B9t：可恢复地执行一次 76 块完整源 Krylov 映射。"""

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
    from scripts import phase7b9r_full_source_krylov_line_search as worker
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9r_full_source_krylov_line_search as worker  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
WORK = OUTPUT / "checkpoints/phase7b9i_work"
MANIFEST = OUTPUT / "checkpoints/phase7b9t_full_frequency_manifest.json"
EXPECTED_PROTOCOL_SHA256 = (
    "02c27157b13810ae4d6579331515a4da3b69e25560e5be02a58ef14f37ed6fb4"
)
base = worker.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9t protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9t source changed: {source['path']}"
                )
    return protocol


def _shape(protocol: dict[str, object]) -> tuple[int, int, int]:
    configuration = protocol["configuration"]
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _initial_manifest(
    protocol: dict[str, object], shape: tuple[int, int, int]
) -> dict[str, object]:
    configuration = protocol["configuration"]
    output = ROOT / configuration["output_state_path"]
    expected_size = int(configuration["raw_float64_checkpoint_size_bytes"])
    if output.stat().st_size != expected_size:
        raise RuntimeError("Phase 7B9t alternating output buffer size changed")
    if base._sha256(output) != configuration["output_state_previous_sha256"]:
        raise RuntimeError(
            "Phase 7B9t alternating output buffer changed before transaction start"
        )
    current = ROOT / configuration["current_state_path"]
    if current.stat().st_size != expected_size:
        raise RuntimeError("Phase 7B9t committed input state size changed")
    return {
        "phase": protocol["phase"],
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "status": "running",
        "current_state_path": configuration["current_state_path"],
        "current_state_sha256": configuration["current_state_sha256"],
        "output_state_path": configuration["output_state_path"],
        "output_previous_sha256": configuration["output_state_previous_sha256"],
        "completed_blocks": [],
        "accumulated_wall_runtime_s": 0.0,
        "candidate_state_sha256": None,
        "candidate_map_index": None,
    }


def _load_manifest(
    protocol: dict[str, object], shape: tuple[int, int, int]
) -> dict[str, object]:
    manifest = (
        json.loads(MANIFEST.read_text(encoding="utf-8"))
        if MANIFEST.exists()
        else _initial_manifest(protocol, shape)
    )
    if (
        manifest["protocol_sha256"] != EXPECTED_PROTOCOL_SHA256
        or manifest["status"] not in ("running", "candidate_passed", "candidate_failed")
        or manifest["current_state_path"]
        != protocol["configuration"]["current_state_path"]
        or manifest["current_state_sha256"]
        != protocol["configuration"]["current_state_sha256"]
    ):
        raise RuntimeError("Phase 7B9t manifest is incompatible")
    current = ROOT / manifest["current_state_path"]
    if base._sha256(current) != manifest["current_state_sha256"]:
        raise RuntimeError("Phase 7B9t committed input state changed")
    output = ROOT / manifest["output_state_path"]
    expected_size = int(protocol["configuration"]["raw_float64_checkpoint_size_bytes"])
    if output.stat().st_size != expected_size:
        raise RuntimeError("Phase 7B9t output state size changed")
    for row in manifest["completed_blocks"]:
        digest = base.phase7b9d._block_sha256(
            output,
            shape,
            int(row["core_group_start"]),
            int(row["core_group_stop"]),
        )
        if digest != row["output_block_sha256"]:
            raise RuntimeError(
                f"Phase 7B9t completed output block changed: {row['block_index']}"
            )
    if not MANIFEST.exists():
        _write_json_atomic(MANIFEST, manifest)
    return manifest


def _run_one_worker(
    protocol_path: Path,
    protocol: dict[str, object],
    block_index: int,
    report_path: Path,
    output_path: Path,
) -> None:
    worker._run_worker(
        protocol_path,
        block_index,
        report_path,
        protocol_override=protocol,
        output_state_path=output_path,
    )


def _plot(
    path: Path,
    reports: list[dict[str, object]],
    gates: dict[str, object],
    *,
    candidate_passed: bool,
    wall_runtime: float,
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(13.0, 8.0), constrained_layout=True)
    block = np.asarray([row["block_index"] for row in reports])
    residual = np.asarray(
        [row["fresh_line_candidate_to_raw_residual_ratio"] for row in reports]
    )
    boundary = np.asarray(
        [row["fresh_line_candidate_to_raw_boundary_ratio"] for row in reports]
    )
    axes[0, 0].semilogy(block, residual, "o-", ms=3, lw=1, label="Interior")
    axes[0, 0].semilogy(block, boundary, "o-", ms=3, lw=1, label="Boundary")
    axes[0, 0].axhline(
        gates["each_fresh_line_candidate_to_raw_residual_ratio_below"],
        color="0.25",
        ls="--",
        label="Interior gate",
    )
    axes[0, 0].set(
        xlabel="Natural frequency block",
        ylabel="Candidate / raw residual",
        title="(a) Full-frequency original-operator gate",
    )
    axes[0, 0].legend(frameon=False, fontsize=8)
    axes[0, 1].plot(
        block,
        [row["line_selected_fraction"] for row in reports],
        "o-",
        ms=3,
        lw=1,
        color="tab:green",
    )
    axes[0, 1].axhline(
        gates["each_selected_line_fraction_at_least"],
        color="0.25",
        ls="--",
        label="Useful-step gate",
    )
    axes[0, 1].set(
        xlabel="Natural frequency block",
        ylabel="Selected endpoint fraction",
        title="(b) Exact affine line search",
    )
    axes[0, 1].legend(frameon=False, fontsize=8)
    scatter = axes[1, 0].scatter(
        block,
        [row["peak_process_rss_mib"] for row in reports],
        c=[row["wall_runtime_s"] for row in reports],
        cmap="viridis",
        s=30,
    )
    axes[1, 0].axhline(
        gates["each_process_peak_rss_strictly_below_mib"],
        color="0.25",
        ls="--",
        label="RSS gate",
    )
    axes[1, 0].set(
        xlabel="Natural frequency block",
        ylabel="Peak process RSS (MiB)",
        title="(c) Worker resources",
    )
    axes[1, 0].legend(frameon=False, fontsize=8)
    figure.colorbar(scatter, ax=axes[1, 0], label="Block wall time (s)")
    axes[1, 1].axis("off")
    axes[1, 1].text(
        0.03,
        0.95,
        "(d) Full-frequency decision\n\n"
        f"Blocks = {len(reports)}/76\n"
        f"Worst residual ratio = {float(np.max(residual)):.4f}\n"
        f"Median residual ratio = {float(np.median(residual)):.4f}\n"
        f"Minimum line fraction = "
        f"{min(float(row['line_selected_fraction']) for row in reports):.4f}\n"
        f"Wall time = {wall_runtime:.1f} s\n\n"
        f"Candidate map passed: {candidate_passed}\n"
        "Material feedback: not evaluated",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=10.5,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path, *, assemble_only: bool = False) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    shape = _shape(protocol)
    manifest = _load_manifest(protocol, shape)
    output_path = ROOT / manifest["output_state_path"]
    report_directory = WORK / "reports_phase7b9t"
    report_directory.mkdir(parents=True, exist_ok=True)
    completed = {
        int(row["block_index"]): row for row in manifest["completed_blocks"]
    }
    pending = [index for index in range(76) if index not in completed]
    if assemble_only and pending:
        raise RuntimeError("Phase 7B9t assemble-only requested before all blocks exist")
    if not assemble_only and manifest["status"] == "running":
        for block_index in pending:
            report_path = report_directory / f"phase7b9t_block{block_index:02d}.json"
            started = time.perf_counter()
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
                    "--output-state",
                    str(output_path),
                ],
                cwd=ROOT,
                check=False,
            )
            if process.returncode != 0:
                raise RuntimeError(
                    f"Phase 7B9t worker {block_index} failed: {process.returncode}"
                )
            row = json.loads(report_path.read_text(encoding="utf-8"))
            if int(row["block_index"]) != block_index:
                raise RuntimeError("Phase 7B9t worker block identity changed")
            row["output_block_sha256"] = base.phase7b9d._block_sha256(
                output_path,
                shape,
                int(row["core_group_start"]),
                int(row["core_group_stop"]),
            )
            manifest["completed_blocks"].append(row)
            manifest["completed_blocks"].sort(
                key=lambda value: int(value["block_index"])
            )
            manifest["accumulated_wall_runtime_s"] = float(
                manifest["accumulated_wall_runtime_s"]
            ) + (time.perf_counter() - started)
            _write_json_atomic(MANIFEST, manifest)
            print(
                json.dumps(
                    {
                        "completed_blocks": len(manifest["completed_blocks"]),
                        "total_blocks": 76,
                        "latest_block": block_index,
                        "latest_residual_ratio": row[
                            "fresh_line_candidate_to_raw_residual_ratio"
                        ],
                    }
                ),
                flush=True,
            )
    reports = list(manifest["completed_blocks"])
    reports.sort(key=lambda row: int(row["block_index"]))
    if len(reports) != 76:
        raise RuntimeError("Phase 7B9t cannot assemble before all blocks complete")
    ownership = np.zeros(shape[0], dtype=np.int64)
    for row in reports:
        ownership[int(row["core_group_start"]) : int(row["core_group_stop"])] += 1
    gates = protocol["gates"]
    residual = np.asarray(
        [row["fresh_line_candidate_to_raw_residual_ratio"] for row in reports]
    )
    boundary = np.asarray(
        [row["fresh_line_candidate_to_raw_boundary_ratio"] for row in reports]
    )
    checks = {
        "block_count_and_frequency_ownership_pass": len(reports)
        == gates["block_count_exactly"]
        and int(np.sum(ownership))
        == gates["owned_frequency_group_count_exactly"]
        and bool(np.all(ownership == 1)),
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
                residual
                < gates[
                    "each_fresh_line_candidate_to_raw_residual_ratio_below"
                ]
            )
        ),
        "median_fresh_line_residual_improves_enough": float(np.median(residual))
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
        "candidate_is_finite_nonnegative_and_within_memory": all(
            row["minimum_line_candidate_intensity"]
            >= gates["minimum_line_candidate_intensity_at_least"]
            and row["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            for row in reports
        ),
        "wall_time_passes": float(manifest["accumulated_wall_runtime_s"])
        < gates["full_map_wall_time_strictly_below_s"],
    }
    passed = all(checks.values())
    if manifest["status"] == "running":
        manifest["status"] = "candidate_passed" if passed else "candidate_failed"
        if passed:
            manifest["candidate_state_sha256"] = base._sha256(output_path)
            manifest["candidate_map_index"] = 7
        _write_json_atomic(MANIFEST, manifest)
    decision = {
        "full_frequency_full_source_krylov_map_passed": passed,
        "candidate_map_committed": passed,
        "candidate_map_index": 7 if passed else None,
        "next_global_original_operator_residual_authorized": passed,
        "trial_formal_feedback_evaluated": False,
        "trial_true_residual_evaluated": False,
        "accepted_as_dynamic_nlte_solution": False,
        "phase7b9t_gate_passed": passed,
    }
    figure = OUTPUT / "phase7b9t_full_frequency_krylov_map.png"
    _plot(
        figure,
        reports,
        gates,
        candidate_passed=passed,
        wall_runtime=float(manifest["accumulated_wall_runtime_s"]),
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "candidate_state_path": manifest["output_state_path"],
        "candidate_state_sha256": manifest["candidate_state_sha256"],
        "completed_block_count": len(reports),
        "maximum_fresh_line_candidate_to_raw_residual_ratio": float(
            np.max(residual)
        ),
        "median_fresh_line_candidate_to_raw_residual_ratio": float(
            np.median(residual)
        ),
        "minimum_selected_line_fraction": min(
            float(row["line_selected_fraction"]) for row in reports
        ),
        "maximum_peak_process_rss_mib": max(
            float(row["peak_process_rss_mib"]) for row in reports
        ),
        "wall_runtime_s": float(manifest["accumulated_wall_runtime_s"]),
        "gate_checks": checks,
        "decision": decision,
        "figures": [figure.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9t_full_frequency_krylov_map_summary.json", summary
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9t_preregistered_full_frequency_krylov_map.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--assemble-only", action="store_true")
    args = parser.parse_args()
    if args.worker:
        if (
            args.block_index is None
            or args.worker_report is None
            or args.output_state is None
        ):
            raise ValueError(
                "worker mode requires block index, report path and output state"
            )
        protocol = _load_protocol(args.protocol, validate_sources=False)
        _run_one_worker(
            args.protocol,
            protocol,
            args.block_index,
            args.worker_report,
            args.output_state,
        )
        return
    summary = run(args.protocol, assemble_only=args.assemble_only)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
