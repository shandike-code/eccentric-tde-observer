"""Phase 7B9bo：执行并审计偶数红黑候选的一次全局原算子映射。"""

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
    from scripts import phase7b9ac_global_positive_picard_map as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ac_global_positive_picard_map as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = "31fcfd2a88141dc32b76235d9ce7b4bfc2f736c76bf601032d2325b64d847666"
base = generic.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9bo protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if source_path.stat().st_size != source["size_bytes"] or base._sha256(source_path) != source["sha256"]:
                raise RuntimeError(f"Phase 7B9bo source changed: {source['path']}")
    return protocol


def _worker(protocol_path: Path, block_index: int, output_state: Path, report_path: Path) -> None:
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    generic._run_worker(protocol_path, block_index, output_state, report_path)


def _plot(path: Path, reports: list[dict[str, object]], residual: float, prior: float) -> None:
    block = np.asarray([row["block_index"] for row in reports])
    local = np.asarray([row["block_relative_radiation_change"] for row in reports])
    figure, axis = plt.subplots(figsize=(7.4, 4.5), constrained_layout=True)
    axis.semilogy(block, local, "o-", ms=3)
    axis.axhline(residual, color="black", ls="--", label="Current global residual")
    axis.axhline(prior, color="tab:red", ls=":", label="Prior best residual")
    axis.set(xlabel="Natural frequency block", ylabel="Block-relative original residual", title="Even red-black half-sweep audit")
    axis.legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, True)
    cfg = protocol["configuration"]
    gates = protocol["gates"]
    shape = (int(cfg["physical_frequency_groups"]), int(cfg["angular_direction_count"]), int(cfg["radiation_depth_cell_count"]))
    output_state = ROOT / cfg["output_state_path"]
    manifest_path = ROOT / cfg["manifest_path"]
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
            raise RuntimeError("Phase 7B9bo manifest belongs to another protocol")
        for row in manifest["completed_blocks"]:
            if base.phase7b9d._block_sha256(output_state, shape, int(row["core_group_start"]), int(row["core_group_stop"])) != row["output_block_sha256"]:
                raise RuntimeError("Phase 7B9bo completed block changed")
    else:
        if output_state.stat().st_size != cfg["raw_float64_checkpoint_size_bytes"] or base._sha256(output_state) != cfg["output_state_previous_sha256"]:
            raise RuntimeError("Phase 7B9bo output scratch changed")
        manifest = {"phase": protocol["phase"], "protocol_sha256": EXPECTED_PROTOCOL_SHA256, "status": "running", "completed_blocks": [], "accumulated_wall_runtime_s": 0.0}
        _write_json_atomic(manifest_path, manifest)
    completed = {int(row["block_index"]): row for row in manifest["completed_blocks"]}
    report_directory = ROOT / cfg["report_directory"]
    report_directory.mkdir(parents=True, exist_ok=True)
    pending = [index for index in range(76) if index not in completed]
    concurrency = int(cfg["maximum_concurrent_processes"])
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset:offset + concurrency]
        started = time.perf_counter()
        paths = [report_directory / f"phase7b9bo_block{index:02d}.json" for index in batch]
        processes = [subprocess.Popen([sys.executable, str(ROOT / cfg["runner_path"]), "--worker", "--protocol", str(protocol_path), "--block-index", str(index), "--output-state", str(output_state), "--worker-report", str(path)], cwd=ROOT) for index, path in zip(batch, paths, strict=True)]
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"Phase 7B9bo worker batch failed: {codes}")
        for index, path in zip(batch, paths, strict=True):
            row = json.loads(path.read_text(encoding="utf-8"))
            row["output_block_sha256"] = base.phase7b9d._block_sha256(output_state, shape, int(row["core_group_start"]), int(row["core_group_stop"]))
            manifest["completed_blocks"].append(row)
        manifest["completed_blocks"].sort(key=lambda row: int(row["block_index"]))
        manifest["accumulated_wall_runtime_s"] += time.perf_counter() - started
        _write_json_atomic(manifest_path, manifest)
        print(json.dumps({"completed_blocks": len(manifest["completed_blocks"]), "total_blocks": 76, "latest_blocks": batch}), flush=True)
    reports = manifest["completed_blocks"]
    ownership = np.zeros(shape[0], dtype=np.int64)
    for row in reports:
        ownership[int(row["core_group_start"]):int(row["core_group_stop"])] += 1
    maximum_change = max(float(row["maximum_absolute_radiation_change"]) for row in reports)
    maximum_scale = max(float(row["maximum_radiation_scale"]) for row in reports)
    residual = maximum_change / maximum_scale
    boundary_num = sum(float(row["boundary_spectrum_l1_numerator"]) for row in reports)
    current_scale = sum(float(row["current_boundary_absolute_scale"]) for row in reports)
    mapped_scale = sum(float(row["mapped_boundary_absolute_scale"]) for row in reports)
    boundary_l1 = boundary_num / max(current_scale, mapped_scale)
    current_bol = sum(float(row["current_boundary_bolometric"]) for row in reports)
    mapped_bol = sum(float(row["mapped_boundary_bolometric"]) for row in reports)
    bolometric = abs(mapped_bol - current_bol) / max(abs(current_bol), abs(mapped_bol))
    prior = float(cfg["prior_best_global_residual"])
    checks = {
        "frequency_ownership_pass": len(reports) == gates["block_count_exactly"] and int(np.sum(ownership)) == gates["owned_frequency_group_count_exactly"] and bool(np.all(ownership == 1)),
        "positive_map_pass": all(row["minimum_input_intensity"] >= gates["minimum_input_and_mapped_intensity_at_least"] and row["minimum_mapped_intensity"] >= gates["minimum_input_and_mapped_intensity_at_least"] for row in reports),
        "strict_global_contraction_pass": residual < gates["global_residual_strictly_below_prior_best"],
        "boundary_pass": boundary_l1 < gates["global_boundary_spectrum_l1_below"] and bolometric < gates["global_boundary_bolometric_fraction_below"],
        "resources_pass": all(row["peak_process_rss_mib"] < gates["each_process_peak_rss_strictly_below_mib"] for row in reports) and manifest["accumulated_wall_runtime_s"] < gates["full_map_wall_time_strictly_below_s"],
    }
    passed = all(checks.values())
    target = residual < gates["fixed_matter_convergence_target"]
    output_sha = base._sha256(output_state)
    manifest["status"] = "accepted" if passed else "rejected"
    manifest["output_state_sha256"] = output_sha
    _write_json_atomic(manifest_path, manifest)
    figure_path = ROOT / cfg["figure_path"]
    _plot(figure_path, reports, residual, prior)
    summary = {
        "phase": protocol["phase"], "classification": "[A-preregistered]+[V]+[O]", "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "input_state_path": cfg["input_state_path"], "input_state_sha256": cfg["input_state_sha256"], "mapped_state_path": cfg["output_state_path"], "mapped_state_sha256": output_sha,
        "prior_best_global_residual": prior, "input_global_original_operator_residual": residual, "residual_ratio_to_prior_best": residual / prior,
        "boundary_spectrum_l1": boundary_l1, "boundary_bolometric_fraction": bolometric, "maximum_process_peak_rss_mib": max(float(row["peak_process_rss_mib"]) for row in reports), "wall_runtime_s": manifest["accumulated_wall_runtime_s"],
        "gate_checks": checks,
        "decision": {"even_half_sweep_accepted": passed, "fixed_matter_target_reached": passed and target, "construct_odd_half_sweep_authorized": passed and not target, "material_feedback_authorized": passed and target},
        "reports": reports, "figures": [figure_path.name],
    }
    _write_json_atomic(ROOT / cfg["summary_path"], summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=OUTPUT / "phase7b9bo_preregistered_even_block_map.json")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.block_index is None or args.output_state is None or args.worker_report is None:
            raise ValueError("worker mode requires block, output state and report")
        _worker(args.protocol, args.block_index, args.output_state, args.worker_report)
    else:
        run(args.protocol)


if __name__ == "__main__":
    main()
