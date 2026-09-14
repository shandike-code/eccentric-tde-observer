"""Phase 7B9bp：并行执行互不相邻的奇数块 Krylov 半扫。"""

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
    from scripts import phase7b9bi_targeted_full_source_krylov as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9bi_targeted_full_source_krylov as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = "370ea3b40b13e718265687a41aec59ec05bf938b2c0cbf1982ebbe26687819a0"
base = generic.base


def _load(path: Path, validate: bool) -> dict[str, object]:
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    return generic._load_protocol(path, validate_sources=validate)


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _worker(protocol_path: Path, block_index: int, report_path: Path, output_path: Path) -> None:
    protocol = _load(protocol_path, False)
    generic._run_worker(protocol_path, protocol, block_index, report_path, output_path)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load(protocol_path, True)
    cfg = protocol["configuration"]
    shape = generic._shape(cfg)
    selected = [int(row["block_index"]) for row in cfg["selected_blocks"]]
    manifest_path = ROOT / cfg["manifest_path"]
    if not manifest_path.exists():
        manifest = generic._initialize_output(protocol, shape)
        _write(manifest_path, manifest)
    else:
        manifest = generic._load_manifest(protocol, shape)
    output_path = ROOT / cfg["output_state_path"]
    completed = {int(row["block_index"]): row for row in manifest["completed_blocks"]}
    report_directory = ROOT / cfg["report_directory"]
    report_directory.mkdir(parents=True, exist_ok=True)
    pending = [index for index in selected if index not in completed]
    concurrency = int(cfg["maximum_concurrent_processes"])
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset:offset + concurrency]
        started = time.perf_counter()
        paths = [report_directory / f"phase7b9bp_block{index:02d}.json" for index in batch]
        processes = [subprocess.Popen([sys.executable, str(ROOT / cfg["runner_path"]), "--worker", "--protocol", str(protocol_path), "--block-index", str(index), "--worker-report", str(path), "--output-state", str(output_path)], cwd=ROOT) for index, path in zip(batch, paths, strict=True)]
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"Phase 7B9bp worker batch failed: {codes}")
        for index, path in zip(batch, paths, strict=True):
            row = json.loads(path.read_text(encoding="utf-8"))
            row["output_block_sha256"] = base.phase7b9d._block_sha256(output_path, shape, int(row["core_group_start"]), int(row["core_group_stop"]))
            manifest["completed_blocks"].append(row)
        manifest["completed_blocks"].sort(key=lambda row: int(row["block_index"]))
        manifest["accumulated_wall_runtime_s"] += time.perf_counter() - started
        _write(manifest_path, manifest)
        print(json.dumps({"completed_odd_blocks": len(manifest["completed_blocks"]), "total_odd_blocks": len(selected), "latest_blocks": batch}), flush=True)
    reports = sorted(manifest["completed_blocks"], key=lambda row: int(row["block_index"]))
    gates = protocol["gates"]
    ratio = np.asarray([row["fresh_line_candidate_to_raw_residual_ratio"] for row in reports])
    boundary = np.asarray([row["fresh_line_candidate_to_raw_boundary_ratio"] for row in reports])
    checks = {
        "selected_block_identity_pass": [int(row["block_index"]) for row in reports] == selected,
        "finite_krylov_budget_pass": all(row["gmres_iteration_count"] <= gates["each_gmres_iteration_count_at_most"] for row in reports),
        "positive_endpoint_and_candidate_pass": all(row["endpoint_exact_nonnegative_step"] >= gates["each_endpoint_exact_nonnegative_step_at_least"] and row["minimum_line_candidate_intensity"] >= gates["minimum_line_candidate_intensity_at_least"] for row in reports),
        "useful_line_steps_pass": all(row["line_selected_fraction"] >= gates["each_selected_line_fraction_at_least"] for row in reports),
        "local_residual_improvement_pass": bool(np.all(ratio < gates["each_fresh_line_candidate_to_raw_residual_ratio_below"])),
        "local_boundary_pass": bool(np.all(boundary <= gates["each_fresh_line_candidate_boundary_ratio_at_most"])),
        "affine_prediction_pass": all(row["affine_prediction_to_fresh_residual_linf"] < gates["each_affine_prediction_to_fresh_residual_linf_below"] for row in reports),
        "resources_pass": all(row["peak_process_rss_mib"] < gates["each_process_peak_rss_strictly_below_mib"] for row in reports) and manifest["accumulated_wall_runtime_s"] < gates["targeted_map_wall_time_strictly_below_s"],
    }
    passed = len(reports) == len(selected) and all(checks.values())
    candidate_sha = generic._sha256(output_path) if passed else None
    manifest["status"] = "candidate_passed" if passed else "candidate_failed"
    manifest["candidate_state_sha256"] = candidate_sha
    _write(manifest_path, manifest)
    figure_path = ROOT / cfg["figure_path"]
    generic._plot(figure_path, reports, len(selected))
    summary = {
        "phase": protocol["phase"], "classification": "[A-solver]+[A-preregistered]+[V]+[O]", "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "selected_blocks": cfg["selected_blocks"], "candidate_state_path": cfg["output_state_path"] if passed else None, "candidate_state_sha256": candidate_sha,
        "completed_target_block_count": len(reports), "maximum_local_candidate_to_raw_residual_ratio": float(np.max(ratio)), "median_local_candidate_to_raw_residual_ratio": float(np.median(ratio)),
        "minimum_selected_line_fraction": float(min(row["line_selected_fraction"] for row in reports)), "maximum_peak_process_rss_mib": float(max(row["peak_process_rss_mib"] for row in reports)), "wall_runtime_s": manifest["accumulated_wall_runtime_s"],
        "gate_checks": checks,
        "decision": {"odd_half_sweep_candidate_passed": passed, "full_red_black_cycle_global_audit_authorized": passed, "material_feedback_authorized": False},
        "reports": reports, "figures": [figure_path.name],
    }
    _write(ROOT / cfg["summary_path"], summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=OUTPUT / "phase7b9bp_preregistered_odd_block_krylov.json")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--output-state", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.block_index is None or args.worker_report is None or args.output_state is None:
            raise ValueError("worker mode requires block, report and output state")
        _worker(args.protocol, args.block_index, args.worker_report, args.output_state)
    else:
        run(args.protocol)


if __name__ == "__main__":
    main()
