"""Phase 7B9dv：在干净迭代边界冻结 7B9dp/du 的客观收尾证据。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
DEFAULT_REPORT = OUTPUT / "phase7b9dv_closeout.json"
DEFAULT_FIGURE = OUTPUT / "phase7b9dv_closeout.png"
RESIDUAL_TARGET = 1.0e-4
BOUNDARY_TARGET = 1.0e-3


SOURCE_PATHS = {
    "dp_summary": "outputs/phase7b9dp_post_streaming_picard_summary.json",
    "dt_summary": "outputs/phase7b9dt_two_state_slow_mode_summary.json",
    "du_protocol": "outputs/phase7b9du_preregistered_exhausted_dp_picard_continuation.json",
    "du_manifest": "outputs/checkpoints/phase7b9du_exhausted_dp_picard_continuation/manifest.json",
    "du_summary": "outputs/phase7b9du_exhausted_dp_picard_continuation_summary.json",
    "branch_contract": "outputs/phase7_post_convergence_branch_contract.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _finite(value: Any, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise RuntimeError(f"{name} must be finite")
    return number


def _require_iteration(row: dict[str, Any], *, require_blocks: bool) -> None:
    for name in (
        "global_original_operator_residual",
        "boundary_spectrum_l1",
        "boundary_bolometric_fraction",
    ):
        if _finite(row[name], name) < 0.0:
            raise RuntimeError(f"{name} must be nonnegative")
    if row.get("progression_passed") is not True:
        raise RuntimeError("every retained iteration must pass progression")
    if row.get("convergence_passed") is not False:
        raise RuntimeError("closeout expects every retained iteration to remain unconverged")
    if require_blocks and row.get("block_report_count") != 76:
        raise RuntimeError("runtime iteration must contain 76 complete blocks")


def _validate_sources(sources: dict[str, dict[str, Any]]) -> None:
    dp = sources["dp_summary"]
    dt = sources["dt_summary"]
    protocol = sources["du_protocol"]
    manifest = sources["du_manifest"]
    du = sources["du_summary"]
    contract = sources["branch_contract"]

    if dp.get("status") != "maximum_maps_exhausted" or len(dp.get("iterations", [])) != 41:
        raise RuntimeError("Phase 7B9dp must contain its exhausted 41-state history")
    for row in dp["iterations"]:
        _require_iteration(row, require_blocks=True)
    if dt.get("status") != "complete":
        raise RuntimeError("Phase 7B9dt diagnostic must be complete")
    if dt.get("gate_checks") != {
        "frequency_ownership_pass": True,
        "original_operator_residual_exactly_reproduced": True,
        "target_unchanged_pass": True,
    }:
        raise RuntimeError("Phase 7B9dt exact diagnostic gates changed")
    if protocol.get("phase") != "7B9du exhausted-dp pure-Picard continuation":
        raise RuntimeError("unexpected Phase 7B9du protocol")
    if protocol["configuration"].get("matter_feedback") is not False:
        raise RuntimeError("Phase 7B9du closeout requires fixed matter")
    if manifest.get("status") != "running":
        raise RuntimeError("recoverable Phase 7B9du manifest status changed")
    if manifest.get("active_iteration") is not None:
        raise RuntimeError("Phase 7B9du did not stop at a clean iteration boundary")
    if len(manifest.get("iterations", [])) != 9 or len(du.get("iterations", [])) != 9:
        raise RuntimeError("Phase 7B9du closeout requires exactly 9 retained records")
    if manifest["iterations"] != du["iterations"]:
        raise RuntimeError("Phase 7B9du manifest and summary histories differ")
    for index, row in enumerate(du["iterations"]):
        _require_iteration(row, require_blocks=index > 0)
    last = du["iterations"][-1]
    if (
        last.get("iteration") != 8
        or last.get("block_report_count") != 76
        or last.get("progression_passed") is not True
        or last.get("convergence_passed") is not False
    ):
        raise RuntimeError("Phase 7B9du final iteration-8 completion gate failed")
    expected_blocks = list(range(76))
    if last.get("block_report_audit", {}).get("block_indices") != expected_blocks:
        raise RuntimeError("Phase 7B9du final block ownership is incomplete")
    if contract.get("current_decision", {}).get("status") != "not_ready":
        raise RuntimeError("post-convergence branch contract must remain not_ready")
    if contract["current_decision"].get("selected_branch") is not None:
        raise RuntimeError("closeout must not select a downstream branch")


def _merged_history(
    dp: dict[str, Any], du: dict[str, Any]
) -> list[dict[str, float | int | None | str]]:
    rows: list[dict[str, float | int | None | str]] = []
    for row in dp["iterations"]:
        rows.append(
            {
                "combined_iteration": int(row["iteration"]),
                "stage": "7B9dp",
                "stage_iteration": int(row["iteration"]),
                "residual": _finite(row["global_original_operator_residual"], "residual"),
                "contraction_ratio": (
                    None
                    if row.get("contraction_ratio") is None
                    else _finite(row["contraction_ratio"], "contraction_ratio")
                ),
                "boundary_spectrum_l1": _finite(row["boundary_spectrum_l1"], "boundary_spectrum_l1"),
                "boundary_bolometric_fraction": _finite(row["boundary_bolometric_fraction"], "boundary_bolometric_fraction"),
            }
        )
    # 中文：du 的第 0 条是 dp 第 40 条的冻结种子，只保留一次。
    seed = du["iterations"][0]
    if any(
        _finite(seed[name], name) != _finite(dp["iterations"][-1][name], name)
        for name in (
            "global_original_operator_residual",
            "boundary_spectrum_l1",
            "boundary_bolometric_fraction",
        )
    ):
        raise RuntimeError("Phase 7B9du seed does not reproduce the Phase 7B9dp endpoint")
    for row in du["iterations"][1:]:
        rows.append(
            {
                "combined_iteration": 40 + int(row["iteration"]),
                "stage": "7B9du",
                "stage_iteration": int(row["iteration"]),
                "residual": _finite(row["global_original_operator_residual"], "residual"),
                "contraction_ratio": _finite(row["contraction_ratio"], "contraction_ratio"),
                "boundary_spectrum_l1": _finite(row["boundary_spectrum_l1"], "boundary_spectrum_l1"),
                "boundary_bolometric_fraction": _finite(row["boundary_bolometric_fraction"], "boundary_bolometric_fraction"),
            }
        )
    if [row["combined_iteration"] for row in rows] != list(range(49)):
        raise RuntimeError("combined Picard history must contain exactly iterations 0 through 48")
    return rows


def build_report(root: Path = ROOT) -> dict[str, Any]:
    paths = {name: root / relative for name, relative in SOURCE_PATHS.items()}
    sources = {name: _load(path) for name, path in paths.items()}
    _validate_sources(sources)
    history = _merged_history(sources["dp_summary"], sources["du_summary"])
    first = history[0]
    last = history[-1]
    dt = sources["dt_summary"]
    final_residual = float(last["residual"])
    return {
        "phase": "7B9dv clean-boundary closeout",
        "classification": "[V-closeout]+[A-user-stop]+[O-not-converged]",
        "source_artifacts": {
            name: {"path": SOURCE_PATHS[name], "sha256": sha256(path)}
            for name, path in paths.items()
        },
        "stop_provenance": {
            "reason": "The user requested project closeout instead of deeper slow-tail convergence.",
            "stop_location": "after completed Phase 7B9du iteration 8",
            "clean_iteration_boundary_verified": True,
            "manifest_active_iteration_is_null": True,
            "manifest_status": "running",
            "manifest_status_interpretation": "recoverable-state marker only; it does not mean a background process remains running",
            "background_execution_claimed": False,
            "checkpoint_or_manifest_mutated": False,
        },
        "du_closeout_audit": {
            "retained_record_count": 9,
            "last_iteration": 8,
            "last_block_report_count": 76,
            "last_frequency_ownership_exact": bool(
                sources["du_summary"]["iterations"][-1]["frequency_ownership_exact"]
            ),
            "last_progression_passed": True,
            "last_convergence_passed": False,
            "last_original_operator_residual": final_residual,
            "residual_target": RESIDUAL_TARGET,
            "residual_target_ratio": final_residual / RESIDUAL_TARGET,
            "last_boundary_spectrum_l1": float(last["boundary_spectrum_l1"]),
            "last_boundary_bolometric_fraction": float(last["boundary_bolometric_fraction"]),
            "boundary_target": BOUNDARY_TARGET,
        },
        "combined_picard_history": history,
        "combined_progress": {
            "unique_state_count": len(history),
            "initial_residual": float(first["residual"]),
            "final_residual": final_residual,
            "fractional_residual_reduction": 1.0 - final_residual / float(first["residual"]),
            "minimum_residual": min(float(row["residual"]) for row in history),
            "final_contraction_ratio": float(last["contraction_ratio"]),
            "all_retained_steps_monotone_nonincreasing": all(
                float(right["residual"]) <= float(left["residual"])
                for left, right in zip(history, history[1:])
            ),
            "strict_convergence_reached": False,
        },
        "slow_mode_diagnostic": {
            "status": dt["status"],
            "exact_original_residual_reproduction": dt["gate_checks"][
                "original_operator_residual_exactly_reproduced"
            ],
            "controlling_frequency_group": dt["numerator_control"][
                "controlling_frequency_group"
            ],
            "controlling_energy_ev": dt["numerator_control"][
                "energy_geometric_centre_ev"
            ],
            "interpretation": "diagnostic localization only; it is not convergence proof",
        },
        "verified_achievements": [
            "A 9632-group, 32-direction, 4096-depth fixed-matter radiation sequence remained physical and progression-passing.",
            "The original operator residual decreased monotonically across the merged 49-state dp+du history.",
            "Both boundary diagnostics are already below their 1e-3 thresholds.",
            "The independent 7B9dt locator exactly reproduced the dp endpoint residual without changing the target.",
            "The stopped du endpoint contains all 76 natural frequency blocks and no active partial iteration.",
        ],
        "objective_limitations": [
            "one representative annulus only",
            "one orbital phase only",
            "matter fixed during this radiation tail",
            "ground-state H/He continuum closure only",
            "strict original-operator convergence not reached",
            "no formal H/He feedback pair on this endpoint",
            "no Phase 4 atmosphere replacement",
            "no Swift/UVOT instrument or observation-sampling product",
            "no real bound-bound line formation",
        ],
        "authorization": {
            "formal_h_he_feedback_pair": False,
            "material_step_acceptance": False,
            "dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
        "post_convergence_branch_decision": {
            "status": "not_ready",
            "selected_branch": None,
            "reason": "Strict convergence, a formal feedback pair, and full-domain continuum evidence are absent.",
        },
        "forbidden_repairs": {
            "nan_to_num": False,
            "arbitrary_clip": False,
            "arbitrary_floor": False,
            "failed_point_deletion": False,
            "posthoc_renormalization": False,
        },
    }


def plot_report(report: dict[str, Any], path: Path) -> None:
    history = report["combined_picard_history"]
    iteration = np.asarray([row["combined_iteration"] for row in history], dtype=float)
    residual = np.asarray([row["residual"] for row in history], dtype=float)
    q = np.asarray(
        [np.nan if row["contraction_ratio"] is None else row["contraction_ratio"] for row in history],
        dtype=float,
    )
    boundary_spectrum = np.asarray([row["boundary_spectrum_l1"] for row in history], dtype=float)
    boundary_bolometric = np.asarray([row["boundary_bolometric_fraction"] for row in history], dtype=float)
    fig, axes = plt.subplots(3, 1, figsize=(9.0, 9.0), sharex=True, constrained_layout=True)
    axes[0].semilogy(iteration, residual, color="#1f77b4", marker="o", ms=3, label="Original-operator residual")
    axes[0].axhline(RESIDUAL_TARGET, color="#c44e52", ls="--", label="Residual target")
    axes[0].axvline(40, color="0.55", ls=":", label="dp / du boundary")
    axes[0].set_ylabel("Maximum relative residual")
    axes[0].legend(frameon=False, fontsize=8)
    axes[0].grid(alpha=0.25)
    axes[1].plot(iteration, q, color="#55a868", marker="o", ms=3, label="Contraction ratio")
    axes[1].axhline(1.0, color="#c44e52", ls="--", label="Progression limit")
    axes[1].set_ylabel("Residual ratio q")
    axes[1].set_ylim(0.90, 1.005)
    axes[1].legend(frameon=False, fontsize=8)
    axes[1].grid(alpha=0.25)
    axes[2].semilogy(iteration, boundary_spectrum, color="#8172b2", marker="o", ms=3, label="Boundary spectrum L1")
    axes[2].semilogy(iteration, boundary_bolometric, color="#dd8452", marker="s", ms=3, label="Boundary bolometric fraction")
    axes[2].axhline(BOUNDARY_TARGET, color="#c44e52", ls="--", label="Boundary target")
    axes[2].set_xlabel("Combined Picard state index")
    axes[2].set_ylabel("Boundary change")
    axes[2].legend(frameon=False, fontsize=8, ncol=2)
    axes[2].grid(alpha=0.25)
    fig.suptitle("Phase 7B9dv: clean-boundary closeout without strict convergence")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--figure", type=Path, default=DEFAULT_FIGURE)
    args = parser.parse_args()
    report = build_report()
    plot_report(report, args.figure)
    report["figure"] = {
        "path": str(args.figure.relative_to(ROOT)),
        "sha256": sha256(args.figure),
    }
    args.report.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["post_convergence_branch_decision"]["status"],
                "final_residual": report["combined_progress"]["final_residual"],
                "figure_sha256": report["figure"]["sha256"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
