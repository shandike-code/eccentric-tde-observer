"""Phase 7B6l：最坏全深度块的整态正性 Anderson(2) 最终局部门。"""

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
    from phase7b6k_anderson1 import _positivity_line_alpha, _safe_base
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
    from scripts.phase7b6b_relaxed_fixed_point import _sha256_array, _write_json_atomic
    from scripts.phase7b6d_full_depth_contraction import _block_fields
except ModuleNotFoundError as error:
    if error.name not in {"phase7b6k_anderson1", "scripts"}:
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
    from phase7b6k_anderson1 import (  # type: ignore[no-redef]
        _positivity_line_alpha,
        _safe_base,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "321b157aa0fb290e7f3cb2215e756756f4117199552bfe0d67982b579afec56f"
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
        raise RuntimeError(f"frozen Phase 7B6l protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6l source changed: {source['path']}")
    return protocol


def _anderson_coefficients(
    residuals: list[np.ndarray], current_residual: np.ndarray
) -> tuple[np.ndarray, float]:
    sequence = [*residuals, current_residual]
    differences = [
        sequence[index + 1] - sequence[index]
        for index in range(len(sequence) - 1)
    ]
    size = len(differences)
    gram = np.empty((size, size), dtype=float)
    right = np.empty(size, dtype=float)
    for row, first in enumerate(differences):
        right[row] = np.einsum("fmd,fmd->", first, current_residual)
        for column, second in enumerate(differences):
            gram[row, column] = np.einsum("fmd,fmd->", first, second)
    condition = float(np.linalg.cond(gram))
    coefficients = np.linalg.solve(gram, right)
    del differences
    return coefficients, condition


def _anderson_proposal(
    mapped_history: list[np.ndarray],
    mapped: np.ndarray,
    coefficients: np.ndarray,
) -> np.ndarray:
    sequence = [*mapped_history, mapped]
    proposal = np.array(mapped, copy=True)
    temporary = np.empty_like(mapped)
    for index, coefficient in enumerate(coefficients):
        np.subtract(sequence[index + 1], sequence[index], out=temporary)
        temporary *= float(coefficient)
        proposal -= temporary
    del temporary
    return proposal


def _positive_trial(
    base: np.ndarray, proposal: np.ndarray
) -> tuple[np.ndarray, float, float]:
    if not np.all(np.isfinite(proposal)):
        raise ArithmeticError("Anderson(2) proposal became non-finite")
    minimum = float(np.min(proposal))
    if minimum >= 0.0:
        return proposal, 1.0, minimum
    # 只缩短一个全局方向，不修补任何局域强度。
    proposal -= base
    alpha = _positivity_line_alpha(base, proposal)
    if alpha == 0.0:
        return np.array(base, copy=True), 0.0, float(np.min(base))
    proposal *= alpha
    proposal += base
    minimum = float(np.min(proposal))
    if not np.all(np.isfinite(proposal)) or minimum < 0.0:
        raise ArithmeticError("Anderson(2) positivity-line state is invalid")
    return proposal, alpha, minimum


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    fields = _block_fields(protocol)
    context = fields["context"]
    current = np.array(fields["initial"], copy=True)
    residual_history: list[np.ndarray] = []
    mapped_history: list[np.ndarray] = []
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

        coefficients = None
        condition = None
        alpha = None
        method = "safe base"
        accepted = base
        minimum = float(np.min(base))
        used_depth = min(len(residual_history), 2)
        if used_depth > 0:
            coefficients, condition = _anderson_coefficients(
                residual_history[-used_depth:], residual
            )
            if np.all(np.isfinite(coefficients)) and np.isfinite(condition):
                proposal = _anderson_proposal(
                    mapped_history[-used_depth:], mapped, coefficients
                )
                trial, alpha, minimum = _positive_trial(base, proposal)
                if alpha > 0.0:
                    accepted = trial
                    method = (
                        f"Anderson({used_depth})"
                        if alpha == 1.0
                        else f"positivity-line Anderson({used_depth})"
                    )
                else:
                    del trial

        history.append(
            {
                "iteration": iteration,
                "raw_fixed_point_residual": raw_residual,
                "history_depth": used_depth,
                "anderson_coefficients": (
                    None if coefficients is None else coefficients.tolist()
                ),
                "gram_condition_number": condition,
                "positivity_line_alpha": alpha,
                "safe_base_weight": base_weight,
                "accepted_method": method,
                "minimum_intensity": minimum,
                "safe_base_checks": base_checks,
                "map_runtime_s": time.perf_counter() - map_started,
            }
        )
        residual_history.append(residual)
        mapped_history.append(mapped)
        if len(residual_history) > 2:
            del residual_history[0]
            del mapped_history[0]
        current = accepted
        del result

    del residual_history, mapped_history
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
                row["gram_condition_number"],
                row["positivity_line_alpha"],
                row["safe_base_weight"],
            )
            if value is not None
        ],
        *[
            coefficient
            for row in history
            for coefficient in (row["anderson_coefficients"] or [])
        ],
    ]
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    depth_two_count = sum(row["history_depth"] == 2 for row in history)
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
        "depth_two_step_count": depth_two_count,
        "positivity_line_step_count": sum(
            str(row["accepted_method"]).startswith("positivity-line") for row in history
        ),
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
        "nonnegative_finite_and_depth_two_used": bool(
            report["minimum_intensity"] >= gates["minimum_intensity_at_least"]
            and report["all_reported_diagnostics_finite"]
            and depth_two_count >= gates["depth_two_step_count_at_least"]
        ),
        "contraction_gate_passed": final_fraction
        < gates["final_raw_residual_strictly_below_vector_aitken_fraction"],
        "resource_and_runtime_gates_passed": bool(
            report["peak_process_rss_mib"]
            < gates["worker_peak_rss_strictly_below_mib"]
            and report["total_runtime_s"] < gates["worker_runtime_strictly_below_s"]
        ),
        "further_anderson_depth_tuning_authorized": False,
        "full_column_fixed_point_authorized": False,
        "full_orbit_authorized": False,
        "matter_feedback_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b6l_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "source_hashes_passed",
            "configuration_and_first_map_exact",
            "nonnegative_finite_and_depth_two_used",
            "contraction_gate_passed",
            "resource_and_runtime_gates_passed",
        )
    )
    decision["full_frequency_anderson2_pilot_authorized"] = bool(
        decision["phase7b6l_gate_passed"]
    )
    report["decision"] = decision
    report["figures"] = ["phase7b6l_anderson2.png"]
    _write_json_atomic(OUTPUT / "phase7b6l_anderson2_summary.json", report)
    _plot(OUTPUT / "phase7b6l_anderson2.png", reference, report)
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
        label="Anderson(2)",
    )
    axes[0, 0].set(
        xlabel="Source-map count",
        ylabel="Raw fixed-point residual",
        title="(a) Fixed-cost convergence",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].semilogy(
        [row["iteration"] for row in report["history"] if row["gram_condition_number"]],
        [row["gram_condition_number"] for row in report["history"] if row["gram_condition_number"]],
        "o-",
        color="#f58518",
    )
    axes[0, 1].set(
        xlabel="Source-map count",
        ylabel="Gram condition number",
        title="(b) Unregularized history system",
    )
    axes[1, 0].plot(
        [row["iteration"] for row in report["history"]],
        [
            np.nan if row["positivity_line_alpha"] is None else row["positivity_line_alpha"]
            for row in report["history"]
        ],
        "o-",
        color="#54a24b",
    )
    axes[1, 0].set(
        xlabel="Source-map count",
        ylabel="Positivity-line fraction",
        title="(c) Proposal acceptance",
    )
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
        default=OUTPUT / "phase7b6l_preregistered_anderson2.json",
    )
    args = parser.parse_args()
    report = run(args.protocol)
    print(json.dumps(report["decision"], indent=2))


if __name__ == "__main__":
    main()
