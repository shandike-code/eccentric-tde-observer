#!/usr/bin/env python3
"""Phase 7B9do: derive a small-file audit of the iteration-20 reproduction.

This script intentionally reads only JSON summaries and retained per-block JSON
reports.  Full-state ``.dat`` files are evidence identifiers, never inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


MAX_SMALL_JSON_BYTES = 2 * 1024 * 1024
EXPECTED_BLOCK_COUNT = 76
RESIDUAL_TARGET = 1.0e-4
CONTRACTION_LIMIT = 1.01
BOUNDARY_LIMIT = 1.0e-3


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _read_small_json(path: Path) -> dict[str, Any]:
    """读取小型 JSON；显式拒绝任何全态 ``.dat`` 输入。"""
    _require(path.suffix.lower() == ".json", f"refusing non-JSON input: {path}")
    size = path.stat().st_size
    _require(size <= MAX_SMALL_JSON_BYTES, f"small-file limit exceeded: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _source_entry(path: Path, root: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    _require(len(payload) <= MAX_SMALL_JSON_BYTES, f"small-file limit exceeded: {path}")
    return {
        "path": path.relative_to(root).as_posix(),
        "size_bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _iteration(rows: Iterable[dict[str, Any]], index: int) -> dict[str, Any]:
    matches = [row for row in rows if int(row["iteration"]) == index]
    _require(len(matches) == 1, f"expected exactly one iteration {index}")
    return matches[0]


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _report_manifest_entry(path: Path, report: dict[str, Any], root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256_bytes(path.read_bytes()),
        "block_index": int(report["block_index"]),
        "core_group_start": int(report["core_group_start"]),
        "core_group_stop": int(report["core_group_stop"]),
        "previous_block_sha256": report["previous_block_sha256"],
        "new_block_sha256": report["new_block_sha256"],
        "changed_from_failed_output": (
            report["previous_block_sha256"] != report["new_block_sha256"]
        ),
        "block_relative_radiation_change": float(
            report["block_relative_radiation_change"]
        ),
    }


def _validate_reports(
    root: Path,
    reports_dir: Path,
    dk: dict[str, Any],
    memory_rerun_sha: str,
) -> tuple[list[dict[str, Any]], str]:
    paths = sorted(reports_dir.glob("phase7b9dk_block*.json"))
    _require(len(paths) == EXPECTED_BLOCK_COUNT, "expected exactly 76 retained reports")

    entries: list[dict[str, Any]] = []
    expected_start = 0
    for expected_index, path in enumerate(paths):
        report = _read_small_json(path)
        _require(int(report["block_index"]) == expected_index, "non-contiguous block index")
        _require(
            report["protocol_sha256"] == dk["protocol_sha256"],
            f"protocol SHA mismatch in block {expected_index}",
        )
        _require(
            report["input_state_sha256"] == dk["immutable_input_sha256"],
            f"input SHA mismatch in block {expected_index}",
        )
        _require(
            int(report["core_group_start"]) == expected_start,
            f"frequency ownership gap/overlap before block {expected_index}",
        )
        expected_start = int(report["core_group_stop"])
        entries.append(_report_manifest_entry(path, report, root))

    _require(expected_start == 9632, "retained reports do not cover all 9632 groups")
    differing = [entry["block_index"] for entry in entries if entry["changed_from_failed_output"]]
    _require(differing == [34], f"expected only block 34 to differ, found {differing}")
    _require(
        entries[34]["new_block_sha256"] == memory_rerun_sha,
        "full-map block 34 does not match the memory-only reruns",
    )
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return entries, _sha256_bytes(canonical)


def build_audit(
    root: Path,
    *,
    di_path: Path,
    dj_audit_path: Path,
    dj_memory_path: Path,
    dk_path: Path,
    dl_path: Path,
    reports_dir: Path,
) -> dict[str, Any]:
    """Build and validate the audit entirely from small JSON evidence."""
    di = _read_small_json(di_path)
    dj_audit = _read_small_json(dj_audit_path)
    dj_memory = _read_small_json(dj_memory_path)
    dk = _read_small_json(dk_path)
    dl = _read_small_json(dl_path)

    _require(di["status"] == "gate_failed", "7B9di must be the rejected gate failure")
    original = _iteration(di["iterations"], 20)
    iteration19 = _iteration(di["iterations"], 19)
    _require(not original["progression_passed"], "original iteration 20 was not rejected")
    _require(not original["progression_gate_checks"]["contraction_pass"], "missing contraction failure")
    _require(original["frequency_ownership_exact"], "original ownership was not exact")
    _require(int(original["block_report_count"]) == EXPECTED_BLOCK_COUNT, "original report count mismatch")
    # 真实 7B9dj 审计把全态身份冻结在 frozen_state_claims；合成测试可用
    # failed_map 的同名字段，二者都只比较既有 SHA 字符串，不读取全态。
    audited_failed_sha = dj_audit.get("frozen_state_claims", {}).get(
        "failed_output_sha256",
        dj_audit["failed_map"].get("mapped_state_sha256"),
    )
    _require(
        audited_failed_sha == original["mapped_state_sha256"],
        "failure audit does not identify the original failed output",
    )
    _require(
        dj_audit["decision"]["unreproducible_block_index"] == 34,
        "failure audit did not localize block 34",
    )

    reruns = dj_memory["independent_memory_only_reruns"]
    _require(len(reruns) == 2, "expected two independent memory-only reruns")
    rerun_shas = [row["in_memory_rerun_block_sha256"] for row in reruns]
    _require(len(set(rerun_shas)) == 1, "memory-only reruns are not byte-identical")
    _require(all(not row["output_persisted"] for row in reruns), "memory-only rerun persisted output")
    _require(all(not row["input_modified"] for row in reruns), "memory-only rerun modified input")
    _require(
        rerun_shas[0] != dj_memory["failed_persisted_block_sha256"],
        "memory-only rerun unexpectedly matches failed persisted block",
    )
    _require(not dj_memory["decision"]["single_block_repair_authorized"], "single-block repair was authorized")

    _require(dk["status"] == "reproduction_passed", "fresh full-map reproduction did not pass")
    _require(int(dk["block_report_count"]) == EXPECTED_BLOCK_COUNT, "fresh report count mismatch")
    _require(dk["block_reports_retained"], "fresh per-block reports were not retained")
    _require(dk["decision"]["full_76_block_reproduction_passed"], "full reproduction decision is false")
    _require(not dk["decision"]["single_block_repair_used"], "fresh reproduction used a single-block repair")
    _require(
        dk["immutable_input_sha256"] == original["input_state_sha256"],
        "fresh reproduction did not use the original iteration-20 input",
    )
    _require(
        dk["failed_output_previous_sha256"] == original["mapped_state_sha256"],
        "fresh reproduction does not identify the rejected output",
    )
    metrics = dk["metrics"]
    _require(metrics["frequency_ownership_exact"], "fresh ownership is not exact")
    _require(int(metrics["frequency_ownership_count"]) == 9632, "fresh ownership count mismatch")
    _require(dk["progression_gate_checks"]["contraction_pass"], "fresh contraction gate failed")
    _require(dk["progression_gate_checks"]["positive_map_pass"], "fresh positivity gate failed")
    _require(dk["progression_gate_checks"]["resources_pass"], "fresh resource gate failed")
    _require(dk["convergence_gate_checks"]["boundary_spectrum_pass"], "fresh spectral boundary gate failed")
    _require(dk["convergence_gate_checks"]["boundary_bolometric_pass"], "fresh bolometric boundary gate failed")
    _require(not dk["convergence_gate_checks"]["residual_pass"], "fresh map was unexpectedly converged")

    report_entries, report_manifest_sha = _validate_reports(
        root, reports_dir, dk, rerun_shas[0]
    )

    _require(dl["status"] == "maximum_maps_exhausted", "7B9dl status must be maximum_maps_exhausted")
    dl20 = _iteration(dl["iterations"], 20)
    for key in (
        "global_original_operator_residual",
        "contraction_ratio",
        "boundary_spectrum_l1",
        "boundary_bolometric_fraction",
    ):
        _require(float(dl20[key]) == float(metrics[key]), f"7B9dl iteration 20 differs for {key}")
    _require(dl20["mapped_state_sha256"] == dk["fresh_output_sha256"], "7B9dl did not use fresh state")
    rejected = dl["rejected_evidence"]
    _require(not rejected["may_enter_valid_history"], "rejected di map entered valid history")
    _require(
        rejected["record"]["mapped_state_sha256"] == original["mapped_state_sha256"],
        "7B9dl rejected evidence differs from original anomaly",
    )
    _require(dl["decision"]["fresh_dk_reproduction_used_as_iteration20"], "7B9dl fresh-state decision false")
    _require(not dl["decision"]["failed_di_iteration20_used_as_valid_history"], "bad iteration entered history")
    tail = [_iteration(dl["iterations"], index) for index in range(20, 24)]
    tail_residuals = [float(row["global_original_operator_residual"]) for row in tail]
    _require(all(b < a for a, b in zip(tail_residuals, tail_residuals[1:])), "7B9dl residual tail is not decreasing")
    _require(all(float(row["contraction_ratio"]) < 1.0 for row in tail), "7B9dl tail is not contractive")

    sources = {
        "di_progression": _source_entry(di_path, root),
        "dj_failure_audit": _source_entry(dj_audit_path, root),
        "dj_memory_only": _source_entry(dj_memory_path, root),
        "dk_full_map": _source_entry(dk_path, root),
        "dl_continuation": _source_entry(dl_path, root),
    }
    differing = [entry["block_index"] for entry in report_entries if entry["changed_from_failed_output"]]
    return {
        "phase": "7B9do iteration20 reproduction evidence audit",
        "classification": "[V-small-file-audit]+[O]",
        "scope": {
            "full_state_bytes_read": False,
            "dat_files_opened": 0,
            "small_json_sources_only": True,
        },
        "sources": sources,
        "original_anomalous_iteration20": {
            "input_state_sha256": original["input_state_sha256"],
            "mapped_state_sha256": original["mapped_state_sha256"],
            "global_original_operator_residual": float(original["global_original_operator_residual"]),
            "contraction_ratio": float(original["contraction_ratio"]),
            "boundary_spectrum_l1": float(original["boundary_spectrum_l1"]),
            "boundary_bolometric_fraction": float(original["boundary_bolometric_fraction"]),
            "frequency_ownership_exact": bool(original["frequency_ownership_exact"]),
            "block_report_count": int(original["block_report_count"]),
            "may_enter_valid_history": False,
        },
        "memory_only_block34": {
            "attempt_count": len(reruns),
            "rerun_block_sha256": rerun_shas[0],
            "failed_persisted_block_sha256": dj_memory["failed_persisted_block_sha256"],
            "two_attempts_byte_identical": True,
            "differs_from_failed_persisted_block": True,
            "output_persisted": False,
            "input_modified": False,
        },
        "fresh_full_76_block_reproduction": {
            "input_state_sha256": dk["immutable_input_sha256"],
            "mapped_state_sha256": dk["fresh_output_sha256"],
            "metrics": metrics,
            "progression_gate_checks": dk["progression_gate_checks"],
            "convergence_gate_checks": dk["convergence_gate_checks"],
            "reports": {
                "count": len(report_entries),
                "frequency_group_count": 9632,
                "manifest_sha256": report_manifest_sha,
                "differing_block_indices": differing,
                "unchanged_block_count": len(report_entries) - len(differing),
                "entries": report_entries,
            },
        },
        "valid_dl_continuation": {
            "status": dl["status"],
            "iterations": [
                {
                    "iteration": int(row["iteration"]),
                    "global_original_operator_residual": float(row["global_original_operator_residual"]),
                    "contraction_ratio": _optional_float(row["contraction_ratio"]),
                    "boundary_spectrum_l1": float(row["boundary_spectrum_l1"]),
                    "boundary_bolometric_fraction": float(row["boundary_bolometric_fraction"]),
                }
                for row in dl["iterations"]
            ],
            "iteration20_is_fresh_reproduction": True,
            "last_residual": tail_residuals[-1],
        },
        "comparisons": {
            "original_to_reproduced_residual_ratio": (
                float(original["global_original_operator_residual"])
                / float(metrics["global_original_operator_residual"])
            ),
            "reproduced_contraction_from_iteration19": (
                float(metrics["global_original_operator_residual"])
                / float(iteration19["global_original_operator_residual"])
            ),
            "memory_only_block34_matches_fresh_full_map_block34": True,
        },
        "decision": {
            "original_iteration20_rejected": True,
            "only_block34_differs_between_rejected_and_fresh_outputs": differing == [34],
            "fresh_full_76_block_reproduction_required_and_completed": True,
            "single_block_repair_authorized": False,
            "single_block_repair_used": False,
            "dl_continuation_uses_reproduced_history": True,
            "positive_picard_sequence_converged": False,
            "material_feedback_authorized": False,
            "dynamic_nlte_solution_accepted": False,
        },
    }


def make_figure(audit: dict[str, Any], output: Path) -> None:
    """Render a four-panel English-only evidence figure."""
    original = audit["original_anomalous_iteration20"]
    fresh = audit["fresh_full_76_block_reproduction"]
    rows = audit["valid_dl_continuation"]["iterations"]
    reports = fresh["reports"]["entries"]

    fig, axes = plt.subplots(2, 2, figsize=(13.2, 9.0), constrained_layout=True)

    ax = axes[0, 0]
    iterations = np.asarray([row["iteration"] for row in rows], dtype=int)
    residuals = np.asarray([row["global_original_operator_residual"] for row in rows])
    ax.semilogy(iterations, residuals, "o-", color="#1769aa", lw=1.8, ms=4, label="Valid reproduced history")
    ax.semilogy(20, original["global_original_operator_residual"], "x", color="#c62828", ms=11, mew=2.5, label="Rejected original iteration 20")
    ax.semilogy(20, fresh["metrics"]["global_original_operator_residual"], "o", color="#2e7d32", ms=8, label="Fresh 76-block reproduction")
    ax.axhline(RESIDUAL_TARGET, color="0.35", ls="--", lw=1.2, label="Residual target")
    ax.set_xlabel("Picard iteration")
    ax.set_ylabel("Global operator residual")
    ax.set_title("(a) Rejected anomaly and valid continuation")
    ax.grid(alpha=0.25, which="both")
    ax.legend(fontsize=8)

    ax = axes[0, 1]
    block_indices = np.asarray([row["block_index"] for row in reports])
    changed = np.asarray([int(row["changed_from_failed_output"]) for row in reports])
    colors = np.where(changed == 1, "#c62828", "#90a4ae")
    ax.scatter(block_indices, changed, c=colors, s=np.where(changed == 1, 72, 22), zorder=3)
    ax.set_ylim(-0.18, 1.28)
    ax.set_yticks([0, 1], ["Byte-identical", "Different"])
    ax.set_xlabel("Frequency block index")
    ax.set_title("(b) Rejected vs fresh full-map block hashes")
    ax.annotate("Only block 34 differs", xy=(34, 1), xytext=(45, 1.13), arrowprops={"arrowstyle": "->", "color": "#c62828"}, color="#c62828", fontsize=9)
    ax.grid(alpha=0.2, axis="x")

    ax = axes[1, 0]
    evidence_labels = [
        "Rerun 1 vs\nrerun 2",
        "Memory rerun vs\nfailed block 34",
        "Memory rerun vs\nfresh block 34",
        "Changed blocks\nin full map",
    ]
    values = [1.0, 0.0, 1.0, 1.0 / EXPECTED_BLOCK_COUNT]
    bars = ax.bar(range(4), values, color=["#2e7d32", "#c62828", "#2e7d32", "#ef6c00"])
    ax.set_ylim(0, 1.18)
    ax.set_xticks(range(4), evidence_labels)
    ax.set_ylabel("Agreement fraction")
    ax.set_title("(c) Memory-only localization evidence")
    labels = ["Match", "Different", "Match", "1 / 76"]
    for bar, label in zip(bars, labels):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.04, label, ha="center", va="bottom", fontsize=9)
    ax.text(0.02, 0.96, "No state was written", transform=ax.transAxes, va="top", fontsize=9, color="0.25")
    ax.grid(alpha=0.2, axis="y")

    ax = axes[1, 1]
    metrics = fresh["metrics"]
    gate_ratios = np.asarray([
        metrics["global_original_operator_residual"] / RESIDUAL_TARGET,
        metrics["contraction_ratio"] / CONTRACTION_LIMIT,
        metrics["boundary_spectrum_l1"] / BOUNDARY_LIMIT,
        metrics["boundary_bolometric_fraction"] / BOUNDARY_LIMIT,
    ])
    labels = ["Residual", "Contraction q", "Boundary L1", "Boundary bolometric"]
    colors = ["#c62828", "#2e7d32", "#2e7d32", "#2e7d32"]
    bars = ax.bar(range(4), gate_ratios, color=colors)
    ax.axhline(1.0, color="0.25", ls="--", lw=1.2, label="Gate threshold")
    ax.set_yscale("log")
    ax.set_xticks(range(4), labels, rotation=18, ha="right")
    ax.set_ylabel("Metric / gate threshold")
    ax.set_title("(d) Fresh full-map gate diagnostics")
    raw = [
        f"{metrics['global_original_operator_residual']:.4g}",
        f"{metrics['contraction_ratio']:.6f}",
        f"{metrics['boundary_spectrum_l1']:.4g}",
        f"{metrics['boundary_bolometric_fraction']:.4g}",
    ]
    for bar, text_value in zip(bars, raw):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.08, text_value, ha="center", va="bottom", fontsize=8)
    ax.grid(alpha=0.2, axis="y", which="both")
    ax.legend(fontsize=8)

    fig.suptitle("Phase 7B9do: Iteration 20 Reproduction Evidence", fontsize=15)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def write_audit(audit: dict[str, Any], json_path: Path, figure_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    make_figure(audit, figure_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-json", default="outputs/phase7b9do_iteration20_reproduction_audit.json")
    parser.add_argument("--output-figure", default="outputs/phase7b9do_iteration20_reproduction_audit.png")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = args.root.resolve()
    audit = build_audit(
        root,
        di_path=root / "outputs/phase7b9di_progression_continuation_summary.json",
        dj_audit_path=root / "outputs/phase7b9dj_iteration20_failure_audit.json",
        dj_memory_path=root / "outputs/phase7b9dj_memory_only_block34_rerun_summary.json",
        dk_path=root / "outputs/phase7b9dk_full_map_reproduction_summary.json",
        dl_path=root / "outputs/phase7b9dl_reproduced_tail_continuation_summary.json",
        reports_dir=root / "outputs/checkpoints/phase7b9dk_full_map_reproduction/reports",
    )
    write_audit(audit, root / args.output_json, root / args.output_figure)
    print(json.dumps({"status": "ok", "decision": audit["decision"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
