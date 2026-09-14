#!/usr/bin/env python3
"""Phase 7B9 固定物质 Picard 慢模的只读诊断。

本脚本只读取 ce--cp 的小型 JSON summary/manifest；不会打开、哈希或改写
任何辐射场 ``.dat`` 检查点。Anderson 量始终标为 predicted，只有原算子
Picard map 给出的残差才标为 fresh-map actual。
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


SUMMARY_SPECS = (
    ("7B9ce", "anchor", "outputs/phase7b9ce_second_map_anchor_summary.json"),
    ("7B9cf", "picard_sequence", "outputs/phase7b9cf_third_accelerated_picard_summary.json"),
    ("7B9cg", "anderson_prediction", "outputs/phase7b9cg_third_slow_mode_anderson_summary.json"),
    ("7B9ch", "fresh_candidate_map", "outputs/phase7b9ch_third_candidate_map_summary.json"),
    ("7B9ci", "anchor", "outputs/phase7b9ci_third_map_anchor_summary.json"),
    ("7B9cj", "picard_sequence", "outputs/phase7b9cj_fourth_accelerated_picard_summary.json"),
    ("7B9ck", "anderson_prediction", "outputs/phase7b9ck_fourth_slow_mode_anderson_summary.json"),
    ("7B9cl", "fresh_candidate_map", "outputs/phase7b9cl_fourth_candidate_map_summary.json"),
    ("7B9cm", "anchor", "outputs/phase7b9cm_fourth_map_anchor_summary.json"),
    ("7B9cn", "picard_sequence", "outputs/phase7b9cn_fifth_accelerated_picard_summary.json"),
    ("7B9co", "anderson_prediction", "outputs/phase7b9co_fifth_slow_mode_anderson_summary.json"),
    ("7B9cp", "picard_sequence", "outputs/phase7b9cp_long_positive_picard_summary.json"),
)

SEQUENCE_MANIFESTS = {
    "7B9cf": "outputs/checkpoints/phase7b9cf_third_accelerated_picard/manifest.json",
    "7B9cj": "outputs/checkpoints/phase7b9cj_fourth_accelerated_picard/manifest.json",
    "7B9cn": "outputs/checkpoints/phase7b9cn_fifth_accelerated_picard/manifest.json",
    "7B9cp": "outputs/checkpoints/phase7b9cp_long_positive_picard/manifest.json",
}

ANDERSON_ACTUAL_PAIRS = {"7B9cg": "7B9ch", "7B9ck": "7B9cl"}
TARGET_RESIDUAL = 1.0e-4
MAXIMUM_JSON_BYTES = 16 * 1024 * 1024


def read_small_json(path: Path) -> dict[str, Any]:
    """读取受限大小 JSON；路径层面禁止把检查点数据误当输入。"""

    if path.suffix.lower() != ".json":
        raise ValueError(f"only JSON inputs are permitted: {path}")
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > MAXIMUM_JSON_BYTES:
        raise ValueError(f"JSON input exceeds {MAXIMUM_JSON_BYTES} bytes: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"top-level JSON must be an object: {path}")
    return value


def conservative_picard_forecast(
    residuals: Sequence[float],
    wall_runtimes_s: Sequence[float],
    *,
    target: float = TARGET_RESIDUAL,
    recent_point_count: int = 7,
) -> dict[str, Any]:
    """用最近实测 Picard 点给出保守的常比率外推。

    拟合 ``log(residual)`` 的线性斜率，并取“拟合斜率的一侧 1.645 标准误”
    与最近最慢实测收缩二者中更慢者。这个经验外推不是收敛证明。
    """

    if target <= 0.0 or not math.isfinite(target):
        raise ValueError("target must be finite and positive")
    if len(residuals) != len(wall_runtimes_s):
        raise ValueError("residual and wall-runtime sequences must have equal length")
    if len(residuals) < 3:
        return {
            "available": False,
            "reason": "fewer_than_three_fresh_map_actual_points",
            "prediction_is_convergence_proof": False,
        }

    residual_array = np.asarray(residuals, dtype=float)
    wall_array = np.asarray(wall_runtimes_s, dtype=float)
    if not np.all(np.isfinite(residual_array)) or np.any(residual_array <= 0.0):
        raise ValueError("residuals must be finite and positive")
    if not np.all(np.isfinite(wall_array)) or np.any(wall_array <= 0.0):
        raise ValueError("wall runtimes must be finite and positive")

    count = min(int(recent_point_count), residual_array.size)
    if count < 3:
        raise ValueError("recent_point_count must be at least three")
    recent_residual = residual_array[-count:]
    recent_wall = wall_array[-count:]
    ratios = recent_residual[1:] / recent_residual[:-1]
    base = {
        "method": "recent_log_linear_fit_with_slowest_observed_contraction_guard",
        "target_residual_linf": float(target),
        "recent_point_count": int(count),
        "recent_transition_count": int(count - 1),
        "recent_residuals": recent_residual.tolist(),
        "recent_contraction_ratios": ratios.tolist(),
        "latest_fresh_map_actual_residual_linf": float(recent_residual[-1]),
        "prediction_is_convergence_proof": False,
        "requires_fresh_map_confirmation": True,
    }
    if recent_residual[-1] <= target:
        return {
            **base,
            "available": True,
            "reason": "target_already_reached_in_latest_actual",
            "estimated_additional_maps": 0,
            "estimated_additional_wall_runtime_s": 0.0,
            "plateau_warning": False,
        }
    if np.any(ratios >= 1.0):
        return {
            **base,
            "available": False,
            "reason": "recent_segment_contains_non_contraction",
            "plateau_warning": True,
        }

    x = np.arange(count, dtype=float)
    y = np.log(recent_residual)
    x_centered = x - np.mean(x)
    slope = float(np.sum(x_centered * (y - np.mean(y))) / np.sum(x_centered**2))
    intercept = float(np.mean(y) - slope * np.mean(x))
    fitted = intercept + slope * x
    degrees_of_freedom = count - 2
    if degrees_of_freedom > 0:
        residual_variance = float(np.sum((y - fitted) ** 2) / degrees_of_freedom)
        slope_standard_error = math.sqrt(residual_variance / float(np.sum(x_centered**2)))
    else:
        slope_standard_error = 0.0

    one_sided_upper_log_slope = slope + 1.645 * slope_standard_error
    slowest_observed_log_ratio = float(np.max(np.log(ratios)))
    conservative_log_ratio = max(one_sided_upper_log_slope, slowest_observed_log_ratio)
    base.update(
        {
            "log_linear_fit_slope_per_map": slope,
            "log_linear_fit_slope_standard_error": slope_standard_error,
            "one_sided_95_percent_upper_log_slope": one_sided_upper_log_slope,
            "slowest_observed_log_contraction": slowest_observed_log_ratio,
            "conservative_log_contraction": conservative_log_ratio,
        }
    )
    if conservative_log_ratio >= 0.0:
        return {
            **base,
            "available": False,
            "reason": "conservative_fit_is_non_contracting",
            "plateau_warning": True,
        }

    conservative_ratio = math.exp(conservative_log_ratio)
    maps_float = math.log(target / float(recent_residual[-1])) / conservative_log_ratio
    maps = max(0, math.ceil(maps_float))
    conservative_wall = float(np.max(recent_wall))
    return {
        **base,
        "available": True,
        "reason": "empirical_constant_rate_extrapolation",
        "conservative_contraction_ratio_per_map": conservative_ratio,
        "estimated_additional_maps": int(maps),
        "estimated_additional_wall_runtime_s": float(maps * conservative_wall),
        "wall_runtime_per_map_guard_s": conservative_wall,
        "plateau_warning": bool(conservative_ratio >= 0.995),
        "limitations": [
            "The contraction ratio may continue drifting toward unity.",
            "The estimate assumes the recent fixed-matter pure-Picard regime persists.",
            "Only fresh operator maps can establish the threshold and consecutive-state gates.",
        ],
    }


def _manifest_comparison(summary: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    summary_iterations = summary.get("iterations", [])
    manifest_iterations = manifest.get("iterations", [])
    fields = (
        "iteration",
        "input_state_sha256",
        "global_original_operator_residual",
        "contraction_ratio",
        "full_map_wall_runtime_s",
        "map_passed",
    )
    comparable_count = min(len(summary_iterations), len(manifest_iterations))
    equal_prefix = all(
        all(summary_iterations[index].get(field) == manifest_iterations[index].get(field) for field in fields)
        for index in range(comparable_count)
    )
    return {
        "summary_status": summary.get("status"),
        "manifest_status": manifest.get("status"),
        "summary_iteration_count": len(summary_iterations),
        "manifest_iteration_count": len(manifest_iterations),
        "status_equal": summary.get("status") == manifest.get("status"),
        "iteration_count_equal": len(summary_iterations) == len(manifest_iterations),
        "comparable_prefix_equal": equal_prefix,
        "snapshot_consistent": bool(
            summary.get("status") == manifest.get("status")
            and len(summary_iterations) == len(manifest_iterations)
            and equal_prefix
        ),
    }


def build_diagnostic(root: Path) -> dict[str, Any]:
    """从固定的小型 JSON 清单构造去重后的诊断时间线。"""

    sources: dict[str, dict[str, Any]] = {}
    payloads: dict[str, dict[str, Any]] = {}
    for stage, kind, relative in SUMMARY_SPECS:
        path = root / relative
        payloads[stage] = read_small_json(path)
        sources[relative] = {"kind": f"{kind}_summary", "size_bytes": path.stat().st_size}

    manifest_checks: dict[str, dict[str, Any]] = {}
    for stage, relative in SEQUENCE_MANIFESTS.items():
        path = root / relative
        manifest = read_small_json(path)
        sources[relative] = {"kind": "sequence_manifest", "size_bytes": path.stat().st_size}
        manifest_checks[stage] = _manifest_comparison(payloads[stage], manifest)

    events: list[dict[str, Any]] = []
    actual_states: list[dict[str, Any]] = []
    actual_by_sha: dict[str, dict[str, Any]] = {}
    anderson_predictions: list[dict[str, Any]] = []

    def add_actual(
        stage: str,
        source_path: str,
        residual: float,
        wall: float,
        state_sha: str,
        *,
        source_iteration: int | None,
        reported_ratio: float | None,
        map_passed: bool,
        origin: str,
    ) -> None:
        if state_sha in actual_by_sha:
            canonical = actual_by_sha[state_sha]
            alias = {"stage": stage, "source_path": source_path, "source_iteration": source_iteration}
            canonical["duplicate_source_references"].append(alias)
            events.append(
                {
                    "event_index": len(events),
                    "stage": stage,
                    "stage_kind": origin,
                    "measurement_kind": "duplicate_actual_reference",
                    "actual_state_index": canonical["actual_state_index"],
                    "residual_linf": residual,
                    "source_path": source_path,
                    "source_iteration": source_iteration,
                }
            )
            return
        previous = actual_states[-1]["residual_linf"] if actual_states else None
        derived_ratio = residual / previous if previous is not None else None
        record = {
            "actual_state_index": len(actual_states),
            "stage": stage,
            "stage_kind": origin,
            "measurement_kind": "fresh_map_actual",
            "source_path": source_path,
            "source_iteration": source_iteration,
            "input_state_sha256_from_json": state_sha,
            "residual_linf": residual,
            "reported_contraction_ratio": reported_ratio,
            "derived_ratio_to_previous_unique_actual": derived_ratio,
            "wall_runtime_s": wall,
            "map_passed": map_passed,
            "duplicate_source_references": [],
        }
        actual_states.append(record)
        actual_by_sha[state_sha] = record
        events.append({"event_index": len(events), **record})

    for stage, kind, relative in SUMMARY_SPECS:
        summary = payloads[stage]
        if kind == "anchor":
            events.append(
                {
                    "event_index": len(events),
                    "stage": stage,
                    "stage_kind": kind,
                    "measurement_kind": "not_applicable",
                    "residual_linf": None,
                    "source_path": relative,
                }
            )
        elif kind == "picard_sequence":
            for iteration in summary.get("iterations", []):
                if not isinstance(iteration, dict):
                    raise ValueError(f"non-object iteration in {relative}")
                add_actual(
                    stage,
                    relative,
                    float(iteration["global_original_operator_residual"]),
                    float(iteration["full_map_wall_runtime_s"]),
                    str(iteration["input_state_sha256"]),
                    source_iteration=int(iteration["iteration"]),
                    reported_ratio=(
                        None
                        if iteration.get("contraction_ratio") is None
                        else float(iteration["contraction_ratio"])
                    ),
                    map_passed=bool(iteration["map_passed"]),
                    origin=kind,
                )
        elif kind == "fresh_candidate_map":
            add_actual(
                stage,
                relative,
                float(summary["input_global_original_operator_residual"]),
                float(summary["wall_runtime_s"]),
                str(summary["input_state_sha256"]),
                source_iteration=None,
                reported_ratio=None,
                map_passed=bool(summary["decision"]["global_positive_picard_map_passed"]),
                origin=kind,
            )
        elif kind == "anderson_prediction":
            decision = summary["decision"]
            passed = bool(decision["protected_slow_mode_candidate_passed"])
            fresh_authorized = bool(decision["fresh_original_operator_map_authorized"])
            prediction = {
                "stage": stage,
                "stage_kind": kind,
                "measurement_kind": "predicted",
                "source_path": relative,
                "plot_actual_state_coordinate": len(actual_states) - 0.5,
                "baseline_actual_state_index": len(actual_states) - 1,
                "predicted_residual_linf": float(summary["predicted_global_original_operator_residual"]),
                "predicted_ratio_to_baseline": float(summary["predicted_residual_ratio_to_x10"]),
                "evaluation_wall_runtime_s": float(summary["total_wall_runtime_s"]),
                "protected_candidate_passed": passed,
                "fresh_map_authorized": fresh_authorized,
                "disposition": "accepted_for_fresh_map" if passed and fresh_authorized else "rejected",
                "fresh_map_actual_available": stage in ANDERSON_ACTUAL_PAIRS,
            }
            anderson_predictions.append(prediction)
            events.append({"event_index": len(events), **prediction})

    actual_checks: list[dict[str, Any]] = []
    for predicted_stage, actual_stage in ANDERSON_ACTUAL_PAIRS.items():
        predicted = next(item for item in anderson_predictions if item["stage"] == predicted_stage)
        actual = next(item for item in actual_states if item["stage"] == actual_stage)
        predicted_value = predicted["predicted_residual_linf"]
        actual_value = actual["residual_linf"]
        actual_checks.append(
            {
                "predicted_stage": predicted_stage,
                "fresh_map_actual_stage": actual_stage,
                "predicted_residual_linf": predicted_value,
                "fresh_map_actual_residual_linf": actual_value,
                "relative_difference": abs(actual_value / predicted_value - 1.0),
            }
        )

    cp = payloads["7B9cp"]
    cp_iterations = cp.get("iterations", [])
    cp_residuals = [float(item["global_original_operator_residual"]) for item in cp_iterations]
    cp_walls = [float(item["full_map_wall_runtime_s"]) for item in cp_iterations]
    forecast = conservative_picard_forecast(cp_residuals, cp_walls)
    forecast["fit_source_stage"] = "7B9cp"
    forecast["fit_source_status"] = cp.get("status")
    forecast["all_fit_source_maps_passed"] = all(bool(item["map_passed"]) for item in cp_iterations)

    actual_walls = [float(item["wall_runtime_s"]) for item in actual_states]
    rejected = [item["stage"] for item in anderson_predictions if item["disposition"] == "rejected"]
    return {
        "phase": "7B9 fixed-matter residual slow-mode diagnostic",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "classification": ["[V] JSON-record audit", "[A-diagnostic] conservative forecast", "[O] convergence pending"],
        "scope": {
            "stage_range": "7B9ce--7B9cp",
            "input_types": ["small summary JSON", "small manifest JSON"],
            "checkpoint_dat_opened": False,
            "checkpoint_dat_hashed": False,
            "checkpoint_dat_modified": False,
            "forecast_is_convergence_proof": False,
        },
        "sources": sources,
        "manifest_consistency": manifest_checks,
        "events": events,
        "actual_states": actual_states,
        "anderson_predictions": anderson_predictions,
        "prediction_vs_fresh_map_actual": actual_checks,
        "runtime_summary": {
            "unique_fresh_map_actual_count": len(actual_states),
            "total_unique_fresh_map_wall_runtime_s": float(sum(actual_walls)),
            "median_unique_fresh_map_wall_runtime_s": float(np.median(actual_walls)),
            "maximum_unique_fresh_map_wall_runtime_s": float(max(actual_walls)),
        },
        "slow_mode_forecast": forecast,
        "decision": {
            "latest_actual_below_target": bool(actual_states[-1]["residual_linf"] < TARGET_RESIDUAL),
            "formal_convergence_demonstrated": False,
            "rejected_anderson_stages_retained": rejected,
            "fresh_maps_remain_required": True,
        },
        "interpretation": [
            "Predicted Anderson points are not fresh-map actual residuals.",
            "The rejected 7B9co point remains in the audit timeline and has no fresh-map actual.",
            "The forecast is an empirical planning estimate, not evidence that the threshold will be reached.",
        ],
        "figure": "outputs/phase7b9_slow_mode_diagnostic.png",
    }


def write_figure(payload: dict[str, Any], output_path: Path) -> None:
    """绘制全英文、区分 predicted 与 actual 的三联诊断图。"""

    actual = payload["actual_states"]
    predictions = payload["anderson_predictions"]
    x = np.asarray([item["actual_state_index"] for item in actual], dtype=float)
    residual = np.asarray([item["residual_linf"] for item in actual], dtype=float)
    walls = np.asarray([item["wall_runtime_s"] for item in actual], dtype=float)
    ratios = residual[1:] / residual[:-1]

    fig, axes = plt.subplots(3, 1, figsize=(10.5, 10.5), constrained_layout=True)
    ax = axes[0]
    ax.semilogy(x, residual, "o-", color="#1f77b4", label="Fresh-map actual")
    for item in predictions:
        accepted = item["disposition"] != "rejected"
        marker = "D" if accepted else "X"
        color = "#2ca02c" if accepted else "#d62728"
        label = "Anderson predicted (accepted)" if accepted else "Anderson predicted (rejected)"
        ax.semilogy(
            item["plot_actual_state_coordinate"],
            item["predicted_residual_linf"],
            marker=marker,
            linestyle="none",
            color=color,
            markersize=8,
            label=label,
        )
        ax.annotate(item["stage"], (item["plot_actual_state_coordinate"], item["predicted_residual_linf"]), xytext=(4, 5), textcoords="offset points", fontsize=8)
    ax.axhline(TARGET_RESIDUAL, color="black", linestyle="--", linewidth=1.2, label="Target 1e-4")
    forecast = payload["slow_mode_forecast"]
    if forecast.get("available") and forecast.get("estimated_additional_maps", 0) > 0:
        map_count = int(forecast["estimated_additional_maps"])
        shown = min(map_count, 64)
        q = float(forecast["conservative_contraction_ratio_per_map"])
        fx = x[-1] + np.arange(shown + 1)
        fy = residual[-1] * q ** np.arange(shown + 1)
        ax.semilogy(fx, fy, ":", color="#9467bd", linewidth=1.6, label="Conservative forecast")
        ax.annotate(f"Estimate: {map_count} more maps (not proof)", (fx[-1], fy[-1]), xytext=(5, 0), textcoords="offset points", fontsize=8, color="#9467bd")
    handles, labels = ax.get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    ax.legend(unique.values(), unique.keys(), fontsize=8)
    ax.set_ylabel("Global residual (L-inf)")
    ax.set_title("Phase 7B9 Fixed-Matter Residual History")
    ax.grid(alpha=0.25, which="both")

    axes[1].plot(x[1:], ratios, "o-", color="#ff7f0e", label="Actual contraction")
    axes[1].axhline(1.0, color="black", linestyle="--", linewidth=1.0, label="No contraction")
    axes[1].set_ylabel("Residual ratio")
    axes[1].set_title("Fresh-Map Contraction Ratios")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.25)

    axes[2].plot(x, walls, "o-", color="#17becf")
    axes[2].set_xlabel("Unique fresh-map actual state index")
    axes[2].set_ylabel("Wall runtime (s)")
    axes[2].set_title("Fresh-Map Wall Runtime")
    axes[2].grid(alpha=0.25)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-json", type=Path, default=Path("outputs/phase7b9_slow_mode_diagnostic.json"))
    parser.add_argument("--output-figure", type=Path, default=Path("outputs/phase7b9_slow_mode_diagnostic.png"))
    args = parser.parse_args()
    root = args.root.resolve()
    output_json = args.output_json if args.output_json.is_absolute() else root / args.output_json
    output_figure = args.output_figure if args.output_figure.is_absolute() else root / args.output_figure
    payload = build_diagnostic(root)
    payload["figure"] = str(output_figure.relative_to(root))
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_figure(payload, output_figure)
    print(json.dumps({"output_json": str(output_json), "output_figure": str(output_figure), "forecast": payload["slow_mode_forecast"]}, indent=2))


if __name__ == "__main__":
    main()
