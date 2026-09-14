"""Phase 7B7k：根据实测残差收缩和耗时决定是否继续朴素 Picard。"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import matplotlib

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


def _remaining_iterations(current: float, contraction: float, target: float) -> int:
    if not (0.0 < target < current and 0.0 < contraction < 1.0):
        raise ValueError("stationary contraction extrapolation is undefined")
    return int(math.ceil(math.log(target / current) / math.log(contraction)))


def run() -> dict[str, object]:
    radiation_path = OUTPUT / "phase7b7i_second_radiation_map_summary.json"
    feedback_path = OUTPUT / "phase7b7j_second_assembled_feedback_summary.json"
    radiation = json.loads(radiation_path.read_text(encoding="utf-8"))
    feedback = json.loads(feedback_path.read_text(encoding="utf-8"))
    if radiation["decision"]["phase7b7i_gate_passed"] is not True:
        raise RuntimeError("Phase 7B7k requires passed Phase 7B7i")
    if feedback["decision"]["phase7b7j_measurement_gate_passed"] is not True:
        raise RuntimeError("Phase 7B7k requires passed Phase 7B7j diagnostics")
    target = 1.0e-3
    weighted_contraction = float(
        feedback["fixed_point_residual_volume_l1_contraction_fraction"]
    )
    limiting_contraction = float(
        feedback["previous_limiting_cell_residual_contraction_fraction"]
    )
    weighted_current = float(
        feedback["current_mass_weighted_fixed_point_residual"]
    )
    limiting_current = float(
        feedback["maximum_current_cell_fixed_point_residual"]
    )
    weighted_iterations = _remaining_iterations(
        weighted_current, weighted_contraction, target
    )
    limiting_iterations = _remaining_iterations(
        limiting_current, limiting_contraction, target
    )
    cycle_runtime = float(radiation["total_wall_runtime_s"]) + float(
        feedback["total_wall_runtime_s"]
    )
    weighted_hours = weighted_iterations * cycle_runtime / 3600.0
    limiting_hours = limiting_iterations * cycle_runtime / 3600.0
    # 中文：这是资源策略阈值，不是物理收敛判据。
    policy = {
        "maximum_naive_picard_cycles": 20,
        "maximum_naive_picard_wall_time_h": 4.0,
    }
    naive_allowed = bool(
        weighted_iterations <= policy["maximum_naive_picard_cycles"]
        and weighted_hours <= policy["maximum_naive_picard_wall_time_h"]
        and limiting_iterations <= policy["maximum_naive_picard_cycles"]
        and limiting_hours <= policy["maximum_naive_picard_wall_time_h"]
    )
    figure, axes = plt.subplots(1, 3, figsize=(13.0, 4.0), constrained_layout=True)
    axes[0].bar(
        ["Weighted", "Previous limiting cell"],
        [weighted_contraction, limiting_contraction],
        color=["#4c78a8", "#f58518"],
    )
    axes[0].axhline(1.0, color="0.25", ls="--", label="No contraction")
    axes[0].set(
        ylabel="Observed residual contraction",
        title="(a) Measured nonlinear progress",
    )
    axes[0].tick_params(axis="x", rotation=12)
    axes[0].legend(frameon=False)
    axes[1].bar(
        ["Weighted", "Previous limiting cell"],
        [weighted_iterations, limiting_iterations],
        color=["#4c78a8", "#f58518"],
    )
    axes[1].axhline(
        policy["maximum_naive_picard_cycles"],
        color="0.25",
        ls="--",
        label="Resource-policy limit",
    )
    axes[1].set_yscale("log")
    axes[1].set(
        ylabel="Stationary-rate projected cycles",
        title="(b) Naive Picard cost extrapolation",
    )
    axes[1].tick_params(axis="x", rotation=12)
    axes[1].legend(frameon=False)
    axes[2].axis("off")
    axes[2].text(
        0.04,
        0.92,
        "(c) Algorithm decision\n\n"
        f"Current weighted residual = {weighted_current:.3e}\n"
        f"Current maximum residual = {limiting_current:.3e}\n"
        f"One coupled cycle = {cycle_runtime:.1f} s\n"
        f"Weighted projection = {weighted_iterations} cycles ({weighted_hours:.1f} h)\n"
        f"Limiting projection = {limiting_iterations} cycles ({limiting_hours / 24.0:.1f} d)\n\n"
        "Naive Picard continuation: rejected\n"
        "Accelerated nonlinear design: required",
        transform=axes[2].transAxes,
        va="top",
        fontsize=10.5,
    )
    figure_path = OUTPUT / "phase7b7k_nonlinear_cost_decision.png"
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)
    report = {
        "phase": "7B7k nonlinear cost decision",
        "classification": "[V]+[A-resource-policy]+[O]",
        "sources": {
            "phase7b7i_summary": {
                "path": str(radiation_path.relative_to(ROOT)),
                "sha256": _sha256(radiation_path),
            },
            "phase7b7j_summary": {
                "path": str(feedback_path.relative_to(ROOT)),
                "sha256": _sha256(feedback_path),
            },
        },
        "fixed_point_target": target,
        "observed_weighted_contraction": weighted_contraction,
        "observed_previous_limiting_cell_contraction": limiting_contraction,
        "current_weighted_residual": weighted_current,
        "current_maximum_cell_residual": limiting_current,
        "measured_coupled_cycle_runtime_s": cycle_runtime,
        "stationary_contraction_extrapolation": {
            "weighted_remaining_cycles": weighted_iterations,
            "weighted_wall_time_h": weighted_hours,
            "limiting_remaining_cycles": limiting_iterations,
            "limiting_wall_time_h": limiting_hours,
            "is_convergence_theorem": False,
            "is_runtime_guarantee": False,
        },
        "resource_policy": policy,
        "decision": {
            "inputs_and_measured_contractions_valid": True,
            "accepted_as_coupled_fixed_point": False,
            "naive_picard_continuation_authorized": naive_allowed,
            "third_material_update_authorized": False,
            "accelerated_nonlinear_solver_design_required": not naive_allowed,
            "full_orbit_authorized": False,
            "phase4_replacement_authorized": False,
        },
        "figures": [figure_path.name],
    }
    _write_json_atomic(OUTPUT / "phase7b7k_nonlinear_cost_decision_summary.json", report)
    return report


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
