"""Phase 7B6k：最坏全深度块的整态正性 Anderson(1) 加速门。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.mixed_frame_ale import solve_mixed_frame_ale_group_step
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S

try:
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
    from scripts.phase7b6b_relaxed_fixed_point import _sha256_array, _write_json_atomic
    from scripts.phase7b6d_full_depth_contraction import _block_fields
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )
    from phase7b6b_relaxed_fixed_point import (  # type: ignore[no-redef]
        _sha256_array,
        _write_json_atomic,
    )
    from phase7b6d_full_depth_contraction import (  # type: ignore[no-redef]
        _block_fields,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "d90a08deb64b6f6b5aada5ce393ea61ba6f028048c937a889086f77e4db3aa9e"
)
MIB = 1024**2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B6k protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6k source changed: {source['path']}")
    return protocol


def _safe_base(
    current: np.ndarray,
    residual: np.ndarray,
    weights: tuple[float, ...],
) -> tuple[np.ndarray, float, list[dict[str, object]]]:
    checks = []
    for omega in weights:
        trial = np.array(current, copy=True)
        trial += omega * residual
        finite = bool(np.all(np.isfinite(trial)))
        minimum = float(np.min(trial)) if finite else float("nan")
        accepted = bool(finite and minimum >= 0.0)
        checks.append(
            {
                "weight": omega,
                "finite": finite,
                "minimum_intensity": minimum,
                "accepted": accepted,
            }
        )
        if accepted:
            return trial, omega, checks
        del trial
    raise ArithmeticError("no whole-state finite nonnegative safe base exists")


def _positivity_line_alpha(base: np.ndarray, direction: np.ndarray) -> float:
    """沿单一全局方向求严格正性步长；不逐点裁剪强度。"""
    bound = np.inf
    for start in range(0, base.shape[0], 8):
        stop = min(start + 8, base.shape[0])
        local_direction = direction[start:stop]
        decreasing = local_direction < 0.0
        if np.any(decreasing):
            ratios = base[start:stop][decreasing] / (-local_direction[decreasing])
            if not np.all(np.isfinite(ratios)):
                raise ArithmeticError("Anderson positivity ratios became non-finite")
            bound = min(bound, float(np.min(ratios)))
    if np.isinf(bound) or bound > 1.0:
        return 1.0
    if bound <= 0.0:
        return 0.0
    return float(np.nextafter(bound, 0.0))


def _anderson_trial(
    base: np.ndarray,
    mapped: np.ndarray,
    previous_mapped: np.ndarray,
    gamma: float,
) -> tuple[np.ndarray, float, float]:
    # 标准 depth-one Anderson 提案，再沿整态方向退到精确正性边界。
    proposal = np.array(mapped, copy=True)
    proposal *= 1.0 - gamma
    previous_term = np.array(previous_mapped, copy=True)
    previous_term *= gamma
    proposal += previous_term
    del previous_term
    if not np.all(np.isfinite(proposal)):
        raise ArithmeticError("Anderson proposal became non-finite")
    proposal_minimum = float(np.min(proposal))
    if proposal_minimum >= 0.0:
        return proposal, 1.0, proposal_minimum
    proposal -= base
    alpha = _positivity_line_alpha(base, proposal)
    if alpha == 0.0:
        return np.array(base, copy=True), 0.0, float(np.min(base))
    proposal *= alpha
    proposal += base
    if not np.all(np.isfinite(proposal)) or float(np.min(proposal)) < 0.0:
        raise ArithmeticError("scalar positivity-line state is invalid")
    return proposal, alpha, float(np.min(proposal))


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    fields = _block_fields(protocol)
    context = fields["context"]
    current = np.array(fields["initial"], copy=True)
    previous_residual = None
    previous_mapped = None
    history: list[dict[str, object]] = []
    first_source_map_hash = None
    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    map_count = int(configuration["source_map_count_exactly"])
    safe_weights = tuple(float(value) for value in configuration["safe_base_weights"])
    for iteration in range(1, map_count + 1):
        map_started = time.perf_counter()
        result = solve_mixed_frame_ale_group_step(
            fields["local"],
            fields["old_edge"],
            fields["new_edge"],
            context["mu"],
            context["weight"],
            fields["initial"],
            fields["outer"],
            fields["true_absorption"],
            fields["thermal_emissivity"],
            fields["scattering"],
            context["beta"],
            context["duration_s"],
            propagation_speed_cm_s=LIGHT_SPEED_CM_S,
            source_iteration_initial_guess=current,
            diagnostic_fixed_iteration_count=1,
            spatial_scheme="hybrid_step_turning_upwind",
            source_map_only=True,
        )
        mapped = result.final_lab_intensity_density
        if first_source_map_hash is None:
            first_source_map_hash = _sha256_array(mapped)
        residual = mapped - current
        scale = max(float(np.max(np.abs(mapped))), float(np.max(np.abs(current))))
        maximum_change = float(np.max(np.abs(residual)))
        raw_residual = maximum_change / scale if scale > 0.0 else maximum_change
        base_weights = (1.0,) if iteration == 1 else safe_weights
        base, base_weight, base_checks = _safe_base(current, residual, base_weights)

        gamma = None
        alpha = None
        method = "safe base"
        accepted = base
        minimum = float(np.min(base))
        denominator = None
        if previous_residual is not None and previous_mapped is not None:
            residual_change = residual - previous_residual
            denominator = float(
                np.einsum("fmd,fmd->", residual_change, residual_change)
            )
            if denominator > 0.0:
                gamma = float(
                    np.einsum("fmd,fmd->", residual_change, residual) / denominator
                )
            del residual_change
            if gamma is not None and np.isfinite(gamma):
                trial, alpha, minimum = _anderson_trial(
                    base, mapped, previous_mapped, gamma
                )
                if alpha > 0.0:
                    accepted = trial
                    method = "Anderson(1)" if alpha == 1.0 else "positivity-line Anderson(1)"
                else:
                    del trial

        history.append(
            {
                "iteration": iteration,
                "raw_fixed_point_residual": raw_residual,
                "anderson_gamma": gamma,
                "anderson_denominator": denominator,
                "positivity_line_alpha": alpha,
                "safe_base_weight": base_weight,
                "accepted_method": method,
                "minimum_intensity": minimum,
                "safe_base_checks": base_checks,
                "map_runtime_s": time.perf_counter() - map_started,
            }
        )
        previous_residual = residual
        previous_mapped = mapped
        current = accepted
        del result

    # 最终审计前释放多步历史，避免把历史存储误计为形式解工作集。
    del previous_residual, previous_mapped
    audit = solve_mixed_frame_ale_group_step(
        fields["local"],
        fields["old_edge"],
        fields["new_edge"],
        context["mu"],
        context["weight"],
        fields["initial"],
        fields["outer"],
        fields["true_absorption"],
        fields["thermal_emissivity"],
        fields["scattering"],
        context["beta"],
        context["duration_s"],
        propagation_speed_cm_s=LIGHT_SPEED_CM_S,
        source_iteration_initial_guess=current,
        diagnostic_fixed_iteration_count=1,
        spatial_scheme="hybrid_step_turning_upwind",
    )
    audit_map = audit.final_lab_intensity_density
    audit_scale = max(float(np.max(np.abs(audit_map))), float(np.max(np.abs(current))))
    audit_change = float(np.max(np.abs(audit_map - current)))
    audit_residual = audit_change / audit_scale if audit_scale > 0.0 else audit_change
    reference = json.loads(
        (ROOT / protocol["sources"]["phase7b6g_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    final_fraction = (
        history[-1]["raw_fixed_point_residual"]
        / reference["final_raw_fixed_point_residual"]
    )
    finite_values = [
        audit_residual,
        audit.global_scale_normalized_coupled_residual,
        audit.total_relative_energy_ledger_residual,
        *[row["raw_fixed_point_residual"] for row in history],
        *[
            value
            for row in history
            for value in (
                row["anderson_gamma"],
                row["positivity_line_alpha"],
                row["safe_base_weight"],
            )
            if value is not None
        ],
    ]
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    accelerated_count = sum(
        row["accepted_method"] != "safe base" for row in history
    )
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "phase_index": context["phase"],
        "block_index": context["selected_block_index"],
        "source_map_count": len(history),
        "first_source_map_sha256": first_source_map_hash,
        "final_intensity_sha256": _sha256_array(current),
        "minimum_intensity": float(np.min(current)),
        "final_raw_fixed_point_residual": history[-1]["raw_fixed_point_residual"],
        "audit_raw_fixed_point_residual": audit_residual,
        "audit_coupled_residual": audit.global_scale_normalized_coupled_residual,
        "audit_energy_ledger_residual": audit.total_relative_energy_ledger_residual,
        "final_to_vector_aitken_residual_fraction": final_fraction,
        "accelerated_step_count": accelerated_count,
        "safe_base_only_step_count": len(history) - accelerated_count,
        "all_reported_diagnostics_finite": bool(np.all(np.isfinite(finite_values))),
        "source_map_runtime_s": sum(row["map_runtime_s"] for row in history),
        "total_runtime_s": time.perf_counter() - started,
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
        "history": history,
        "reference_vector_aitken": reference,
    }
    gates = protocol["gates"]
    decision = {
        "frozen_protocol_hash_passed": True,
        "source_hashes_passed": True,
        "configuration_and_first_map_exact": bool(
            report["source_map_count"] == gates["source_map_count_exactly"]
            and report["first_source_map_sha256"]
            == gates["first_source_map_sha256_exactly"]
        ),
        "nonnegative_finite_and_anderson_used": bool(
            report["minimum_intensity"] >= gates["minimum_intensity_at_least"]
            and report["all_reported_diagnostics_finite"]
            and accelerated_count >= gates["anderson_or_line_step_count_at_least"]
        ),
        "contraction_gate_passed": final_fraction
        < gates["final_raw_residual_strictly_below_vector_aitken_fraction"],
        "resource_and_runtime_gates_passed": bool(
            report["peak_process_rss_mib"]
            < gates["worker_peak_rss_strictly_below_mib"]
            and report["total_runtime_s"] < gates["worker_runtime_strictly_below_s"]
        ),
        "full_column_fixed_point_authorized": False,
        "full_orbit_authorized": False,
        "matter_feedback_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b6k_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "source_hashes_passed",
            "configuration_and_first_map_exact",
            "nonnegative_finite_and_anderson_used",
            "contraction_gate_passed",
            "resource_and_runtime_gates_passed",
        )
    )
    decision["full_frequency_anderson_pilot_authorized"] = bool(
        decision["phase7b6k_gate_passed"]
    )
    report["decision"] = decision
    report["figures"] = ["phase7b6k_anderson1.png"]
    _write_json_atomic(OUTPUT / "phase7b6k_anderson1_summary.json", report)
    _plot(OUTPUT / "phase7b6k_anderson1.png", reference, report)
    return report


def _plot(path: Path, reference: dict[str, object], report: dict[str, object]) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].semilogy(
        [row["iteration"] for row in reference["history"]],
        [row["raw_fixed_point_residual"] for row in reference["history"]],
        label="Vector Aitken",
    )
    axes[0, 0].semilogy(
        [row["iteration"] for row in report["history"]],
        [row["raw_fixed_point_residual"] for row in report["history"]],
        label="Anderson(1)",
    )
    axes[0, 0].set(
        xlabel="Source-map count",
        ylabel="Raw fixed-point residual",
        title="(a) Fixed-cost convergence",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].plot(
        [row["iteration"] for row in report["history"]],
        [
            np.nan if row["positivity_line_alpha"] is None else row["positivity_line_alpha"]
            for row in report["history"]
        ],
        "o-",
        color="#f58518",
    )
    axes[0, 1].set(
        xlabel="Source-map count",
        ylabel="Positivity-line fraction",
        title="(b) Anderson proposal acceptance",
    )
    methods = ["Anderson(1)", "positivity-line Anderson(1)", "safe base"]
    axes[1, 0].bar(
        methods,
        [sum(row["accepted_method"] == method for row in report["history"]) for method in methods],
        color=["#54a24b", "#4c78a8", "#777777"],
    )
    axes[1, 0].tick_params(axis="x", rotation=12)
    axes[1, 0].set(ylabel="Count", title="(c) Accepted update type")
    axes[1, 1].bar(
        ["Measured fraction", "Gate"],
        [report["final_to_vector_aitken_residual_fraction"], 0.5],
        color=["#4c78a8", "#555555"],
    )
    axes[1, 1].set(
        ylabel="Final residual / vector Aitken",
        title="(d) Fixed-cost improvement",
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6k_preregistered_anderson1.json",
    )
    args = parser.parse_args()
    report = run(args.protocol)
    print(json.dumps(report["decision"], indent=2))


if __name__ == "__main__":
    main()
