"""Phase 7B9ad：映射态自身守卫下的全局收缩审计。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from scripts import phase7b9ab_global_trial_residual_audit as previous
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ab_global_trial_residual_audit as previous  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "e3e4869a2a8835d9c4ba5b9e741de380f9b67d45657a19a03321f3df71bc37b8"
)
base = previous.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9ad protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9ad source changed: {source['path']}"
                )
    return protocol


def _run_worker(
    protocol_path: Path,
    block_index: int,
    state_path: Path,
    state_sha256: str,
    report_path: Path,
) -> None:
    original_loader = previous._load_protocol
    try:
        previous._load_protocol = _load_protocol
        previous._run_worker(
            protocol_path, block_index, state_path, state_sha256, report_path
        )
    finally:
        previous._load_protocol = original_loader
    row = json.loads(report_path.read_text(encoding="utf-8"))
    row["protocol_sha256"] = EXPECTED_PROTOCOL_SHA256
    row["input_state_sha256"] = row.pop("trial_state_sha256")
    _write_json_atomic(report_path, row)


def _valid_report(path: Path, block_index: int, state_sha256: str) -> bool:
    if not path.exists():
        return False
    row = json.loads(path.read_text(encoding="utf-8"))
    return bool(
        row.get("protocol_sha256") == EXPECTED_PROTOCOL_SHA256
        and row.get("input_state_sha256") == state_sha256
        and int(row.get("block_index", -1)) == block_index
    )


def _plot(
    path: Path,
    prior_reports: list[dict[str, object]],
    reports: list[dict[str, object]],
    residual: float,
    contraction: float,
    boundary_l1: float,
    *,
    prior_report_residual_key: str = "block_relative_radiation_change",
) -> None:
    block = np.asarray([row["block_index"] for row in reports])
    prior = np.asarray(
        [row[prior_report_residual_key] for row in prior_reports]
    )
    current = np.asarray(
        [row["block_relative_original_operator_residual"] for row in reports]
    )
    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.5), constrained_layout=True)
    axes[0].semilogy(block, prior, "o-", ms=3, label="Before map")
    axes[0].semilogy(block, current, "s-", ms=3, label="After map")
    axes[0].set(
        xlabel="Natural frequency block",
        ylabel="Block-relative original residual",
        title="(a) Positive Picard contraction",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].axis("off")
    axes[1].text(
        0.04,
        0.95,
        "(b) Self-guard residual audit\n\n"
        f"Mapped-state residual = {residual:.3e}\n"
        f"Residual contraction ratio = {contraction:.3e}\n"
        f"Boundary spectral L1 = {boundary_l1:.3e}\n"
        f"Maximum worker RSS = "
        f"{max(float(row['peak_process_rss_mib']) for row in reports):.1f} MiB",
        transform=axes[1].transAxes,
        va="top",
        fontsize=10.5,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    summary_path = ROOT / configuration.get(
        "summary_path", "outputs/phase7b9ad_picard_contraction_audit_summary.json"
    )
    figure_path = ROOT / configuration.get(
        "figure_path", "outputs/phase7b9ad_picard_contraction_audit.png"
    )
    report_prefix = str(configuration.get("block_report_prefix", "phase7b9ad"))
    runner_path = ROOT / configuration.get(
        "runner_path", "scripts/phase7b9ad_picard_contraction_audit.py"
    )
    state_path = ROOT / configuration["input_state_path"]
    state_sha = str(configuration["input_state_sha256"])
    report_directory = ROOT / configuration["report_directory"]
    report_directory.mkdir(parents=True, exist_ok=True)
    reports_by_block: dict[int, dict[str, object]] = {}
    pending = []
    for block_index in range(int(configuration["natural_frequency_block_count"])):
        report_path = report_directory / f"{report_prefix}_block{block_index:02d}.json"
        if _valid_report(report_path, block_index, state_sha):
            reports_by_block[block_index] = json.loads(
                report_path.read_text(encoding="utf-8")
            )
        else:
            pending.append((block_index, report_path))
    concurrency = int(configuration["maximum_concurrent_processes"])
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    str(runner_path),
                    "--worker",
                    "--protocol",
                    str(protocol_path),
                    "--block-index",
                    str(block_index),
                    "--input-state",
                    str(state_path),
                    "--input-sha256",
                    state_sha,
                    "--worker-report",
                    str(report_path),
                ],
                cwd=ROOT,
            )
            for block_index, report_path in batch
        ]
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"Phase 7B9ad worker batch failed: {codes}")
        for block_index, report_path in batch:
            if not _valid_report(report_path, block_index, state_sha):
                raise RuntimeError("Phase 7B9ad worker report validation failed")
            reports_by_block[block_index] = json.loads(
                report_path.read_text(encoding="utf-8")
            )
        print(
            json.dumps(
                {
                    "completed_blocks": len(reports_by_block),
                    "total_blocks": 76,
                    "latest_blocks": [index for index, _ in batch],
                }
            ),
            flush=True,
        )
    reports = [reports_by_block[index] for index in range(76)]
    ownership = np.zeros(int(configuration["physical_frequency_groups"]), dtype=np.int64)
    for row in reports:
        ownership[int(row["core_group_start"]) : int(row["core_group_stop"])] += 1
    maximum_change = max(
        float(row["maximum_absolute_original_operator_change"]) for row in reports
    )
    maximum_scale = max(float(row["maximum_original_operator_scale"]) for row in reports)
    residual = maximum_change / maximum_scale if maximum_scale > 0.0 else maximum_change
    prior_source_key = str(
        configuration.get("prior_map_summary_source_key", "phase7b9ac_summary")
    )
    prior_residual_key = str(
        configuration.get(
            "prior_global_residual_key", "input_global_original_operator_residual"
        )
    )
    prior_report_residual_key = str(
        configuration.get(
            "prior_report_residual_key", "block_relative_radiation_change"
        )
    )
    prior_summary = json.loads(
        (ROOT / protocol["sources"][prior_source_key]["path"]).read_text(
            encoding="utf-8"
        )
    )
    contraction = residual / float(prior_summary[prior_residual_key])
    boundary_numerator = sum(float(row["boundary_spectrum_l1_numerator"]) for row in reports)
    current_scale = sum(float(row["current_boundary_absolute_scale"]) for row in reports)
    mapped_scale = sum(float(row["mapped_boundary_absolute_scale"]) for row in reports)
    boundary_l1 = boundary_numerator / max(current_scale, mapped_scale)
    current_bolometric = sum(float(row["current_boundary_bolometric"]) for row in reports)
    mapped_bolometric = sum(float(row["mapped_boundary_bolometric"]) for row in reports)
    bolometric = abs(mapped_bolometric - current_bolometric) / max(
        abs(current_bolometric), abs(mapped_bolometric)
    )
    checks = {
        "frequency_ownership_pass": len(reports) == gates["block_count_exactly"]
        and int(np.sum(ownership)) == gates["owned_frequency_group_count_exactly"]
        and bool(np.all(ownership == 1)),
        "positive_states_pass": all(
            row["minimum_trial_intensity"] >= gates["minimum_intensity_at_least"]
            and row["minimum_mapped_intensity"] >= gates["minimum_intensity_at_least"]
            for row in reports
        ),
        "global_residual_pass": residual
        < gates["global_original_operator_residual_below"],
        "contraction_pass": contraction < gates["residual_contraction_ratio_below"],
        "boundary_spectrum_pass": boundary_l1
        < gates["global_boundary_spectrum_l1_below"],
        "boundary_bolometric_pass": bolometric
        < gates["global_boundary_bolometric_fraction_below"],
        "resources_pass": all(
            row["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and row["wall_runtime_s"]
            < gates["each_worker_wall_time_strictly_below_s"]
            for row in reports
        ),
    }
    mapping_valid = all(
        checks[key]
        for key in (
            "frequency_ownership_pass",
            "positive_states_pass",
            "contraction_pass",
            "boundary_spectrum_pass",
            "boundary_bolometric_pass",
            "resources_pass",
        )
    )
    converged = checks["global_residual_pass"] and mapping_valid
    _plot(
        figure_path,
        prior_summary["reports"],
        reports,
        residual,
        contraction,
        boundary_l1,
        prior_report_residual_key=prior_report_residual_key,
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "input_state_path": configuration["input_state_path"],
        "input_state_sha256": state_sha,
        "prior_global_residual": prior_summary[prior_residual_key],
        "mapped_state_global_original_operator_residual": residual,
        "residual_contraction_ratio": contraction,
        "mapped_state_boundary_spectrum_l1": boundary_l1,
        "mapped_state_boundary_bolometric_fraction": bolometric,
        "maximum_process_peak_rss_mib": max(
            float(row["peak_process_rss_mib"]) for row in reports
        ),
        "gate_checks": checks,
        "decision": {
            "positive_picard_contraction_audit_passed": mapping_valid,
            "mapped_state_globally_converged": converged,
            "continue_positive_picard_maps_authorized": mapping_valid and not converged,
            "material_feedback_authorized": converged,
        },
        "reports": reports,
        "figures": [figure_path.name],
    }
    _write_json_atomic(summary_path, summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9ad_preregistered_picard_contraction_audit.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if (
            args.block_index is None
            or args.input_state is None
            or args.input_sha256 is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires block, input state/hash and report")
        _run_worker(
            args.protocol,
            args.block_index,
            args.input_state,
            args.input_sha256,
            args.worker_report,
        )
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
