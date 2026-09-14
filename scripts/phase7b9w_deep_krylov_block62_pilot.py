"""Phase 7B9w：块 62 的 32 步完整源 Krylov 试验。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import matplotlib

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
EXPECTED_PROTOCOL_SHA256 = (
    "bdbd31e72e2d4e50ab779359f3afdcb6148cb0f52c001ec6396e0477d9f11c78"
)
base = worker.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9w protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9w source changed: {source['path']}"
                )
    return protocol


def _plot(path: Path, report: dict[str, object], gates: dict[str, object]) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(10.8, 4.4), constrained_layout=True)
    axes[0].bar(
        ["16-step\nPhase 7B9t", "32-step\nPhase 7B9w"],
        [
            report["phase7b9t_sixteen_step_residual_ratio"],
            report["fresh_line_candidate_to_raw_residual_ratio"],
        ],
        color=["0.55", "tab:blue"],
    )
    axes[0].axhline(
        gates["fresh_line_candidate_to_raw_residual_ratio_below"],
        color="0.25",
        ls="--",
        label="Residual gate",
    )
    axes[0].set(
        ylabel="Candidate / raw residual",
        title="(a) Block 62 finite-work comparison",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].axis("off")
    axes[1].text(
        0.04,
        0.95,
        "(b) Deep-Krylov decision\n\n"
        f"GMRES steps = {report['gmres_iteration_count']}\n"
        f"Positive step = {report['endpoint_exact_nonnegative_step']:.4f}\n"
        f"Line fraction = {report['line_selected_fraction']:.4f}\n"
        f"Residual ratio = "
        f"{report['fresh_line_candidate_to_raw_residual_ratio']:.4f}\n"
        f"Peak RSS = {report['peak_process_rss_mib']:.1f} MiB\n\n"
        f"Pilot passed: {report['phase7b9w_gate_passed']}",
        transform=axes[1].transAxes,
        va="top",
        fontsize=10.5,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    report_path = OUTPUT / "checkpoints/phase7b9i_work/phase7b9w_block62.json"
    process = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--protocol",
            str(protocol_path),
            "--worker-report",
            str(report_path),
        ],
        cwd=ROOT,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(f"Phase 7B9w worker failed: {process.returncode}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    historical = json.loads(
        (
            ROOT
            / protocol["sources"]["phase7b9t_block62_report"]["path"]
        ).read_text(encoding="utf-8")
    )
    gates = protocol["gates"]
    checks = {
        "exact_block_identity_pass": int(report["block_index"]) == 62,
        "finite_work_budget_pass": report["gmres_iteration_count"]
        <= gates["gmres_iteration_count_at_most"],
        "positive_step_pass": report["endpoint_exact_nonnegative_step"]
        >= gates["endpoint_exact_nonnegative_step_at_least"],
        "useful_line_step_pass": report["line_selected_fraction"]
        >= gates["selected_line_fraction_at_least"],
        "fresh_original_operator_residual_pass": report[
            "fresh_line_candidate_to_raw_residual_ratio"
        ]
        < gates["fresh_line_candidate_to_raw_residual_ratio_below"],
        "boundary_does_not_worsen": report[
            "fresh_line_candidate_to_raw_boundary_ratio"
        ]
        <= gates["fresh_line_candidate_boundary_ratio_at_most"],
        "affine_prediction_pass": report[
            "affine_prediction_to_fresh_residual_linf"
        ]
        < gates["affine_prediction_to_fresh_residual_linf_below"],
        "physical_domain_and_memory_pass": report[
            "minimum_line_candidate_intensity"
        ]
        >= gates["minimum_line_candidate_intensity_at_least"]
        and report["peak_process_rss_mib"]
        < gates["process_peak_rss_strictly_below_mib"],
        "strictly_better_than_sixteen_steps": report[
            "fresh_line_candidate_to_raw_residual_ratio"
        ]
        < historical["fresh_line_candidate_to_raw_residual_ratio"],
    }
    passed = all(checks.values())
    report["phase7b9t_sixteen_step_residual_ratio"] = historical[
        "fresh_line_candidate_to_raw_residual_ratio"
    ]
    report["phase7b9w_gate_checks"] = checks
    report["phase7b9w_gate_passed"] = passed
    figure = OUTPUT / "phase7b9w_deep_krylov_block62_pilot.png"
    _plot(figure, report, gates)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "report": report,
        "gate_checks": checks,
        "decision": {
            "deep_krylov_block62_pilot_passed": passed,
            "hybrid_frequency_solver_repair_authorized": passed,
            "global_candidate_residual_authorized": False,
            "material_feedback_authorized": False,
        },
        "figures": [figure.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9w_deep_krylov_block62_pilot_summary.json", summary
    )
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9w_preregistered_deep_krylov_block62_pilot.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.worker_report is None:
            raise ValueError("worker mode requires report path")
        protocol = _load_protocol(args.protocol, validate_sources=False)
        worker._run_worker(
            args.protocol,
            62,
            args.worker_report,
            protocol_override=protocol,
        )
        return
    run(args.protocol)


if __name__ == "__main__":
    main()
