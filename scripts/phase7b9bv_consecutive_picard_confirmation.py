"""Phase 7B9bv：执行第二个连续 fixed-matter 收敛态确认。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

try:
    from scripts import phase7b9ac_global_positive_picard_map as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ac_global_positive_picard_map as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL_SHA256 = "TO_BE_FROZEN_AFTER_PHASE7B9BT"


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    return generic._load_protocol(path, validate_sources=validate_sources)


def _aggregate(reports: list[dict[str, object]], groups: int) -> dict[str, object]:
    ownership = np.zeros(groups, dtype=np.int64)
    for row in reports:
        ownership[int(row["core_group_start"]) : int(row["core_group_stop"])] += 1
    maximum_change = max(float(row["maximum_absolute_radiation_change"]) for row in reports)
    maximum_scale = max(float(row["maximum_radiation_scale"]) for row in reports)
    current_scale = sum(float(row["current_boundary_absolute_scale"]) for row in reports)
    mapped_scale = sum(float(row["mapped_boundary_absolute_scale"]) for row in reports)
    current_bolometric = sum(float(row["current_boundary_bolometric"]) for row in reports)
    mapped_bolometric = sum(float(row["mapped_boundary_bolometric"]) for row in reports)
    return {
        "frequency_ownership_count": int(np.sum(ownership)),
        "frequency_ownership_exact": bool(np.all(ownership == 1)),
        "input_global_original_operator_residual": (
            maximum_change / maximum_scale if maximum_scale > 0.0 else maximum_change
        ),
        "input_boundary_spectrum_l1": sum(
            float(row["boundary_spectrum_l1_numerator"]) for row in reports
        )
        / max(current_scale, mapped_scale),
        "input_boundary_bolometric_fraction": abs(
            mapped_bolometric - current_bolometric
        )
        / max(abs(current_bolometric), abs(mapped_bolometric)),
        "minimum_input_intensity": min(float(row["minimum_input_intensity"]) for row in reports),
        "minimum_mapped_intensity": min(float(row["minimum_mapped_intensity"]) for row in reports),
        "maximum_process_peak_rss_mib": max(float(row["peak_process_rss_mib"]) for row in reports),
    }


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    cfg = protocol["configuration"]
    gates = protocol["gates"]
    shape = generic._shape(protocol)
    input_state = ROOT / cfg["input_state_path"]
    output_state = ROOT / cfg["output_state_path"]
    manifest_path = ROOT / cfg["manifest_path"]
    summary_path = ROOT / cfg["summary_path"]
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256
            or manifest.get("input_state_sha256") != cfg["input_state_sha256"]
        ):
            raise RuntimeError("Phase 7B9bv manifest changed")
        for row in manifest["completed_blocks"]:
            if generic.base.phase7b9d._block_sha256(
                output_state,
                shape,
                int(row["core_group_start"]),
                int(row["core_group_stop"]),
            ) != row["output_block_sha256"]:
                raise RuntimeError("Phase 7B9bv completed output block changed")
    else:
        if (
            input_state.stat().st_size != int(cfg["raw_float64_checkpoint_size_bytes"])
            or output_state.stat().st_size != int(cfg["raw_float64_checkpoint_size_bytes"])
            or generic.base._sha256(input_state) != cfg["input_state_sha256"]
            or generic.base._sha256(output_state) != cfg["output_state_previous_sha256"]
        ):
            raise RuntimeError("Phase 7B9bv frozen buffers changed")
        manifest = {
            "phase": protocol["phase"],
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "status": "running",
            "input_state_path": cfg["input_state_path"],
            "input_state_sha256": cfg["input_state_sha256"],
            "output_state_path": cfg["output_state_path"],
            "completed_blocks": [],
            "accumulated_wall_runtime_s": 0.0,
        }
        generic._write_json_atomic(manifest_path, manifest)
    if manifest["status"] != "running":
        return json.loads(summary_path.read_text(encoding="utf-8"))
    completed = {int(row["block_index"]): row for row in manifest["completed_blocks"]}
    pending = [index for index in range(76) if index not in completed]
    report_root = ROOT / cfg["report_directory"]
    report_root.mkdir(parents=True, exist_ok=True)
    runner = ROOT / cfg["runner_path"]
    concurrency = int(cfg["maximum_concurrent_processes"])
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        started = time.perf_counter()
        reports = [report_root / f"phase7b9bv_block{index:02d}.json" for index in batch]
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    str(runner),
                    "--worker",
                    "--protocol",
                    str(protocol_path),
                    "--block-index",
                    str(index),
                    "--output-state",
                    str(output_state),
                    "--worker-report",
                    str(report),
                ],
                cwd=ROOT,
            )
            for index, report in zip(batch, reports, strict=True)
        ]
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"Phase 7B9bv worker batch failed: {codes}")
        for index, report_path in zip(batch, reports, strict=True):
            row = json.loads(report_path.read_text(encoding="utf-8"))
            if (
                row.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256
                or int(row.get("block_index", -1)) != index
            ):
                raise RuntimeError("Phase 7B9bv worker report changed")
            row["output_block_sha256"] = generic.base.phase7b9d._block_sha256(
                output_state,
                shape,
                int(row["core_group_start"]),
                int(row["core_group_stop"]),
            )
            manifest["completed_blocks"].append(row)
        manifest["completed_blocks"].sort(key=lambda row: int(row["block_index"]))
        manifest["accumulated_wall_runtime_s"] = float(
            manifest["accumulated_wall_runtime_s"]
        ) + (time.perf_counter() - started)
        generic._write_json_atomic(manifest_path, manifest)
        print(
            json.dumps(
                {
                    "completed_blocks": len(manifest["completed_blocks"]),
                    "total_blocks": 76,
                    "latest_blocks": batch,
                }
            ),
            flush=True,
        )
    reports = list(manifest["completed_blocks"])
    metrics = _aggregate(reports, shape[0])
    previous_residual = float(cfg["previous_global_original_operator_residual"])
    previous_boundary = float(cfg["previous_boundary_spectrum_l1"])
    previous_bolometric = float(cfg["previous_boundary_bolometric_fraction"])
    checks = {
        "frequency_ownership_pass": len(reports) == gates["block_count_exactly"]
        and metrics["frequency_ownership_count"]
        == gates["owned_frequency_group_count_exactly"]
        and metrics["frequency_ownership_exact"],
        "positive_map_pass": metrics["minimum_input_intensity"]
        >= gates["minimum_input_and_mapped_intensity_at_least"]
        and metrics["minimum_mapped_intensity"]
        >= gates["minimum_input_and_mapped_intensity_at_least"],
        "two_consecutive_residuals_pass": max(
            previous_residual, metrics["input_global_original_operator_residual"]
        )
        < gates["both_global_original_operator_residuals_below"],
        "two_consecutive_boundary_spectra_pass": max(
            previous_boundary, metrics["input_boundary_spectrum_l1"]
        )
        < gates["both_boundary_spectrum_l1_below"],
        "two_consecutive_boundary_bolometric_pass": max(
            previous_bolometric, metrics["input_boundary_bolometric_fraction"]
        )
        < gates["both_boundary_bolometric_fraction_below"],
        "resources_pass": metrics["maximum_process_peak_rss_mib"]
        < gates["each_process_peak_rss_strictly_below_mib"]
        and float(manifest["accumulated_wall_runtime_s"])
        < gates["full_map_wall_time_strictly_below_s"],
    }
    passed = all(checks.values())
    output_sha = generic.base._sha256(output_state)
    generic._plot(
        ROOT / cfg["figure_path"],
        reports,
        float(metrics["input_global_original_operator_residual"]),
        float(metrics["input_boundary_spectrum_l1"]),
        float(metrics["input_boundary_bolometric_fraction"]),
    )
    manifest["status"] = "complete" if passed else "gate_failed"
    manifest["output_state_sha256"] = output_sha
    generic._write_json_atomic(manifest_path, manifest)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "previous_converged_state_path": cfg["previous_converged_state_path"],
        "previous_converged_state_sha256": cfg["previous_converged_state_sha256"],
        "previous_global_original_operator_residual": previous_residual,
        "input_state_path": cfg["input_state_path"],
        "input_state_sha256": cfg["input_state_sha256"],
        "output_state_path": cfg["output_state_path"],
        "output_state_sha256": output_sha,
        **metrics,
        "wall_runtime_s": manifest["accumulated_wall_runtime_s"],
        "gate_checks": checks,
        "decision": {
            "two_consecutive_fixed_matter_states_converged": passed,
            "formal_h_he_feedback_pair_authorized": passed,
            "finite_trial_accepted_as_nonlinear_step": False,
            "material_feedback_evaluated": False,
            "dynamic_nlte_solution_accepted": False,
        },
        "reports": reports,
        "figures": [Path(cfg["figure_path"]).name],
    }
    generic._write_json_atomic(summary_path, summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            ROOT
            / "outputs/phase7b9bv_preregistered_consecutive_picard_confirmation.json"
        ),
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    if args.worker:
        if args.block_index is None or args.output_state is None or args.worker_report is None:
            raise ValueError("worker mode requires block, output state and report")
        generic._run_worker(
            args.protocol, args.block_index, args.output_state, args.worker_report
        )
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
