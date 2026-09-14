"""Phase 7B9j：以三轮完整映射判定有限试步的朴素内迭代成本。"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _maps_to_gate(current: float, target: float, contraction: float) -> int:
    if not 0.0 < target < current or not 0.0 < contraction < 1.0:
        raise ValueError("Phase 7B9j contraction projection inputs are invalid")
    return int(math.ceil(math.log(target / current) / math.log(contraction)))


def run() -> dict[str, object]:
    manifest_path = OUTPUT / "checkpoints/phase7b9i_work/manifest.json"
    protocol_path = OUTPUT / "phase7b9i_preregistered_finite_trial_radiation.json"
    trial_path = OUTPUT / "phase7b9i_finite_trial_material_summary.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    trial = json.loads(trial_path.read_text(encoding="utf-8"))
    history = manifest["history"]
    if (
        manifest["status"] != "running"
        or int(manifest["current_additional_map"]) != 3
        or len(history) != 3
        or int(manifest["uncommitted_iteration"]["additional_map"]) != 4
        or trial["decision"]["phase7b9i_material_gate_passed"] is not True
    ):
        raise RuntimeError("Phase 7B9j requires three complete trial maps and paused map 4")
    residual = np.asarray([row["raw_source_map_residual"] for row in history])
    contraction = residual[1:] / residual[:-1]
    best_contraction = float(np.min(contraction))
    latest_contraction = float(contraction[-1])
    target = float(protocol["gates"]["global_source_map_residual_below"])
    maximum_map = int(protocol["configuration"]["maximum_total_additional_maps"])
    remaining_budget = maximum_map - int(manifest["current_additional_map"])
    projected_at_budget_best = float(
        residual[-1] * best_contraction**remaining_budget
    )
    projected_at_budget_latest = float(
        residual[-1] * latest_contraction**remaining_budget
    )
    maps_best = _maps_to_gate(float(residual[-1]), target, best_contraction)
    maps_latest = _maps_to_gate(float(residual[-1]), target, latest_contraction)
    first_pass_map_best = int(manifest["current_additional_map"]) + maps_best
    first_pass_map_latest = int(manifest["current_additional_map"]) + maps_latest
    # 中文：还需第二个连续通过点，并保留偶数编号停止规则。
    stop_map_best = first_pass_map_best + 1
    if stop_map_best % 2 == 1:
        stop_map_best += 1
    stop_map_latest = first_pass_map_latest + 1
    if stop_map_latest % 2 == 1:
        stop_map_latest += 1
    representative_wall = float(np.median([row["wall_runtime_s"] for row in history]))
    projected_hours_best = (
        stop_map_best - int(manifest["current_additional_map"])
    ) * representative_wall / 3600.0
    projected_hours_latest = (
        stop_map_latest - int(manifest["current_additional_map"])
    ) * representative_wall / 3600.0
    budget_cannot_pass = bool(projected_at_budget_best >= target)
    partial = manifest["uncommitted_iteration"]
    completed_partial_blocks = len(partial["completed_blocks"])
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    maps = np.arange(1, maximum_map + 1)
    best_curve = residual[-1] * best_contraction ** np.maximum(maps - 3, 0)
    latest_curve = residual[-1] * latest_contraction ** np.maximum(maps - 3, 0)
    axes[0, 0].semilogy((1, 2, 3), residual, "o-", label="Measured")
    axes[0, 0].semilogy(maps[2:], best_curve[2:], "--", label="Best observed q")
    axes[0, 0].semilogy(maps[2:], latest_curve[2:], ":", label="Latest q")
    axes[0, 0].axhline(target, color="0.25", ls="-.", label="Source gate")
    axes[0, 0].set(
        xlabel="Source map at finite material trial",
        ylabel="Global-scale radiation change",
        title="(a) Frozen budget cannot reach the source gate",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].semilogy(
        (1, 2, 3),
        [row["boundary_flux_spectrum_l1"] for row in history],
        "o-",
        label="Spectral L1",
    )
    axes[0, 1].semilogy(
        (1, 2, 3),
        [row["boundary_flux_bolometric_fraction"] for row in history],
        "s-",
        label="Bolometric",
    )
    axes[0, 1].axhline(1.0e-3, color="0.25", ls="--", label="Boundary gate")
    axes[0, 1].set(
        xlabel="Source map at finite material trial",
        ylabel="Successive boundary-flux change",
        title="(b) Boundary functionals are also unconverged",
    )
    axes[0, 1].legend(frameon=False)
    axes[1, 0].bar(
        ("Frozen\nmap 12", "Best-q\ncompletion", "Latest-q\ncompletion"),
        (maximum_map, stop_map_best, stop_map_latest),
        color=("#4f7cac", "#8f6f45", "#a45a52"),
    )
    axes[1, 0].set(
        ylabel="Required final source-map index",
        title="(c) Resource projection, not a convergence theorem",
    )
    axes[1, 1].axis("off")
    axes[1, 1].text(
        0.03,
        0.96,
        "(d) Decision\n\n"
        f"Measured q = {contraction[0]:.3f}, {contraction[1]:.3f}\n"
        f"Best projected map-12 residual = {projected_at_budget_best:.3e}\n"
        f"Best projected completion = map {stop_map_best}\n"
        f"Best projected extra wall time = {projected_hours_best:.1f} h\n"
        f"Paused map-4 blocks = {completed_partial_blocks}/76\n\n"
        "Current omega=1 trial continuation: rejected\n"
        "Trial physical residual: not evaluated",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=10.1,
    )
    figure_path = OUTPUT / "phase7b9j_finite_trial_cost_decision.png"
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)
    snapshot_path = OUTPUT / "phase7b9j_finite_trial_pause_snapshot.json"
    _write_json_atomic(snapshot_path, manifest)
    report = {
        "phase": "7B9j finite-trial inner-radiation cost decision",
        "classification": "[A-resource-projection]+[V]+[O]",
        "sources": {
            "paused_manifest": {
                "path": str(manifest_path.relative_to(ROOT)),
                "sha256": _sha256(manifest_path),
            },
            "frozen_protocol": {
                "path": str(protocol_path.relative_to(ROOT)),
                "sha256": _sha256(protocol_path),
            },
            "finite_trial_material": {
                "path": str(trial_path.relative_to(ROOT)),
                "sha256": _sha256(trial_path),
            },
        },
        "complete_map_count": len(history),
        "paused_map": int(partial["additional_map"]),
        "paused_map_completed_blocks": completed_partial_blocks,
        "measured_source_residuals": residual.tolist(),
        "measured_contractions": contraction.tolist(),
        "best_observed_contraction": best_contraction,
        "latest_observed_contraction": latest_contraction,
        "frozen_maximum_map": maximum_map,
        "projected_map12_residual_best_observed_q": projected_at_budget_best,
        "projected_map12_residual_latest_q": projected_at_budget_latest,
        "projected_stop_map_best_observed_q": stop_map_best,
        "projected_stop_map_latest_q": stop_map_latest,
        "projected_additional_wall_time_h_best_observed_q": projected_hours_best,
        "projected_additional_wall_time_h_latest_q": projected_hours_latest,
        "pause_snapshot_path": str(snapshot_path.relative_to(ROOT)),
        "pause_snapshot_sha256": _sha256(snapshot_path),
        "decision": {
            "three_complete_maps_and_hashes_preserved": True,
            "frozen_map_budget_provably_insufficient_under_best_observed_q": (
                budget_cannot_pass
            ),
            "resume_current_omega1_trial": False,
            "trial_inner_radiation_converged": False,
            "trial_formal_feedback_evaluated": False,
            "trial_true_residual_evaluated": False,
            "trial_accepted_as_nonlinear_step": False,
            "trial_rejected_by_physical_residual": False,
            "finite_trial_may_be_called_jv": False,
            "static_approximation_rejected_by_this_stage": False,
            "redesign_inner_radiation_acceleration_authorized": True,
            "phase7b9j_cost_gate_passed": budget_cannot_pass,
        },
        "figures": [figure_path.name],
    }
    summary_path = OUTPUT / "phase7b9j_finite_trial_cost_decision_summary.json"
    _write_json_atomic(summary_path, report)
    return report


def main() -> None:
    print(json.dumps(run(), indent=2))


if __name__ == "__main__":
    main()
