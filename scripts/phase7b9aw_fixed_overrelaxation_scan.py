"""Phase 7B9aw：执行一遍式固定网格超松弛扫描。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import sys

import numpy as np

try:
    from scripts import phase7b9am_global_picard_overrelaxation as engine
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9am_global_picard_overrelaxation as engine  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = "d605d3c9658c919ea3408aa0b094e92752c6447386a5ff1ed4b02acb609d25ca"
base = engine.base


def run(protocol_path: Path) -> dict[str, object]:
    engine.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    protocol = engine._load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    grid = {
        "phase": "7B9aw fixed positive overrelaxation candidates",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "theta_candidates": configuration["fixed_theta_candidates"],
    }
    grid_path = ROOT / configuration["derived_grid_path"]
    engine._write_json_atomic(grid_path, grid)
    reports = engine._run_pass(
        protocol_path,
        protocol,
        mode="candidate",
        directory=ROOT / configuration["candidate_report_directory"],
        grid_path=grid_path,
    )
    rows = engine._aggregate_candidate(reports, grid)
    valid = [
        row
        for row in rows
        if row["minimum_current_intensity"]
        >= gates["minimum_current_and_mapped_intensity_at_least"]
        and row["minimum_mapped_intensity"]
        >= gates["minimum_current_and_mapped_intensity_at_least"]
    ]
    if not valid:
        raise RuntimeError("Phase 7B9aw has no nonnegative candidate")
    selected = min(valid, key=lambda row: (row["global_residual"], row["theta"]))
    theta_zero = next(row for row in rows if row["theta"] == 0.0)
    reference = protocol["reference"]
    ownership = np.zeros(configuration["physical_frequency_groups"], dtype=np.int8)
    for report in reports:
        ownership[
            int(report["core_group_start"]) : int(report["core_group_stop"])
        ] += 1
    checks = {
        "frequency_ownership_pass": len(reports) == gates["block_count_exactly"]
        and int(np.sum(ownership)) == gates["owned_frequency_group_count_exactly"]
        and bool(np.all(ownership == 1)),
        "theta_zero_reproduction_pass": abs(
            theta_zero["global_residual"]
            - reference["theta_zero_global_residual"]
        )
        <= gates["theta_zero_endpoint_absolute_tolerance"]
        and abs(
            theta_zero["boundary_spectrum_l1"]
            - reference["theta_zero_boundary_spectrum_l1"]
        )
        <= gates["theta_zero_endpoint_absolute_tolerance"]
        and abs(
            theta_zero["boundary_bolometric_fraction"]
            - reference["theta_zero_boundary_bolometric_fraction"]
        )
        <= gates["theta_zero_endpoint_absolute_tolerance"],
        "selected_positive_pass": selected in valid,
        "selected_residual_improvement_pass": selected["global_residual"]
        / theta_zero["global_residual"]
        < gates["selected_residual_ratio_to_theta_zero_below"],
        "selected_boundary_pass": selected["boundary_spectrum_l1"]
        < gates["selected_boundary_spectrum_l1_below"]
        and selected["boundary_bolometric_fraction"]
        < gates["selected_boundary_bolometric_fraction_below"],
        "resources_pass": all(
            float(row["peak_process_rss_mib"])
            < gates["each_process_peak_rss_strictly_below_mib"]
            and float(row["wall_runtime_s"])
            < gates["candidate_worker_wall_time_strictly_below_s"]
            for row in reports
        ),
    }
    passed = all(checks.values())
    figure = ROOT / configuration["figure_path"]
    engine._plot(figure, rows, selected)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "lower_state_path": configuration["lower_state_path"],
        "lower_state_sha256": configuration["lower_state_sha256"],
        "upper_state_path": configuration["upper_state_path"],
        "upper_state_sha256": configuration["upper_state_sha256"],
        "selected_theta": selected["theta"],
        "selected_global_residual": selected["global_residual"],
        "selected_residual_ratio_to_theta_zero": selected["global_residual"]
        / theta_zero["global_residual"],
        "selected_boundary_spectrum_l1": selected["boundary_spectrum_l1"],
        "selected_boundary_bolometric_fraction": selected[
            "boundary_bolometric_fraction"
        ],
        "selected_minimum_current_intensity": selected[
            "minimum_current_intensity"
        ],
        "selected_minimum_mapped_intensity": selected["minimum_mapped_intensity"],
        "valid_theta_count": len(valid),
        "invalid_theta": [row["theta"] for row in rows if row not in valid],
        "maximum_process_peak_rss_mib": max(
            float(row["peak_process_rss_mib"]) for row in reports
        ),
        "driver_peak_rss_mib": engine.base.ru_maxrss_to_bytes(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
        )
        / engine.MIB,
        "derived_grid_sha256": base._sha256(grid_path),
        "gate_checks": checks,
        "decision": {
            "fixed_overrelaxation_scan_passed": passed,
            "write_selected_candidate_authorized": passed,
            "fresh_global_candidate_audit_authorized": passed,
            "resume_positive_picard_authorized": not passed,
            "material_feedback_authorized": False,
        },
        "grid": rows,
        "candidate_reports": reports,
        "figures": [figure.name],
    }
    engine._write_json_atomic(ROOT / configuration["summary_path"], summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9aw_preregistered_fixed_overrelaxation_scan.json",
    )
    parser.add_argument("--candidate-worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--derived-grid", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    engine.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    if args.candidate_worker:
        if (
            args.block_index is None
            or args.derived_grid is None
            or args.worker_report is None
        ):
            raise ValueError("candidate worker requires block, grid and report")
        engine._run_candidate_worker(
            args.protocol, args.block_index, args.derived_grid, args.worker_report
        )
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
