"""Phase 7B6g：在最坏全深度块上验证向量 Aitken 松弛。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
    "31445ab9dc671e6a2a9a64b5ed9450e8e027de06960a0e352374d9a2fdb1d106"
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
        raise RuntimeError(f"frozen Phase 7B6g protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6g source changed: {source['path']}")
    return protocol


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    fields = _block_fields(protocol)
    context = fields["context"]
    current = np.array(fields["initial"], copy=True)
    previous_residual = None
    previous_weight = float(configuration["first_weight"])
    history: list[dict[str, object]] = []
    first_source_map_hash = None
    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    map_count = int(configuration["source_map_count_exactly"])
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
        residual_vector = mapped - current
        scale = max(float(np.max(np.abs(mapped))), float(np.max(np.abs(current))))
        raw_residual = (
            float(np.max(np.abs(residual_vector))) / scale
            if scale > 0.0
            else float(np.max(np.abs(residual_vector)))
        )
        aitken_weight = None
        aitken_denominator = None
        accepted_method = None
        accepted_weight = None
        accepted_trial = None
        if previous_residual is not None:
            residual_change = residual_vector - previous_residual
            aitken_denominator = float(
                np.einsum("fmd,fmd->", residual_change, residual_change)
            )
            numerator = float(
                np.einsum("fmd,fmd->", previous_residual, residual_change)
            )
            if aitken_denominator > 0.0:
                aitken_weight = -previous_weight * numerator / aitken_denominator
            if aitken_weight is not None and np.isfinite(aitken_weight) and aitken_weight > 0.0:
                trial = current + aitken_weight * residual_vector
                if np.all(np.isfinite(trial)) and float(np.min(trial)) >= 0.0:
                    accepted_method = "vector Aitken"
                    accepted_weight = float(aitken_weight)
                    accepted_trial = trial
        fallback_checks = []
        if accepted_trial is None:
            fallback_weights = (
                (float(configuration["first_weight"]),)
                if iteration == 1
                else tuple(float(value) for value in configuration["fallback_weights"])
            )
            for omega in fallback_weights:
                trial = mapped if omega == 1.0 else current + omega * residual_vector
                finite = bool(np.all(np.isfinite(trial)))
                minimum = float(np.min(trial)) if finite else float("nan")
                accepted = bool(finite and minimum >= 0.0)
                fallback_checks.append(
                    {
                        "weight": omega,
                        "finite": finite,
                        "minimum_intensity": minimum,
                        "accepted": accepted,
                    }
                )
                if accepted:
                    accepted_method = "guarded fallback"
                    accepted_weight = omega
                    accepted_trial = np.array(trial, copy=True)
                    break
        if accepted_trial is None or accepted_weight is None or accepted_method is None:
            raise ArithmeticError("Aitken and unmodified fallback states were invalid")
        history.append(
            {
                "iteration": iteration,
                "raw_fixed_point_residual": raw_residual,
                "aitken_candidate_weight": aitken_weight,
                "aitken_denominator": aitken_denominator,
                "accepted_method": accepted_method,
                "accepted_weight": accepted_weight,
                "minimum_intensity": float(np.min(accepted_trial)),
                "fallback_checks": fallback_checks,
                "map_runtime_s": time.perf_counter() - map_started,
            }
        )
        previous_residual = np.array(residual_vector, copy=True)
        previous_weight = accepted_weight
        current = accepted_trial

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
    audit_difference = float(np.max(np.abs(audit_map - current)))
    audit_raw_residual = (
        audit_difference / audit_scale if audit_scale > 0.0 else audit_difference
    )
    diagnostics = np.asarray(
        [
            audit_raw_residual,
            audit.global_scale_normalized_coupled_residual,
            audit.total_relative_energy_ledger_residual,
            *[row["accepted_weight"] for row in history],
        ]
    )
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    reference = json.loads(
        (ROOT / protocol["sources"]["phase7b6d_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )["runs"]["guarded_1p8"]
    final_fraction = (
        history[-1]["raw_fixed_point_residual"]
        / reference["final_raw_fixed_point_residual"]
    )
    gates = protocol["gates"]
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
        "audit_raw_fixed_point_residual": audit_raw_residual,
        "audit_coupled_residual": audit.global_scale_normalized_coupled_residual,
        "audit_energy_ledger_residual": audit.total_relative_energy_ledger_residual,
        "final_to_guarded_1p8_residual_fraction": final_fraction,
        "aitken_step_count": sum(
            row["accepted_method"] == "vector Aitken" for row in history
        ),
        "fallback_step_count": sum(
            row["accepted_method"] == "guarded fallback" for row in history
        ),
        "all_reported_diagnostics_finite": bool(np.all(np.isfinite(diagnostics))),
        "source_map_runtime_s": sum(row["map_runtime_s"] for row in history),
        "total_runtime_s": time.perf_counter() - started,
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
        "history": history,
    }
    decision = {
        "frozen_protocol_hash_passed": True,
        "source_hashes_passed": True,
        "configuration_and_first_map_exact": bool(
            report["source_map_count"] == gates["source_map_count_exactly"]
            and report["first_source_map_sha256"]
            == gates["first_source_map_sha256_exactly"]
        ),
        "nonnegative_finite_and_aitken_used": bool(
            report["minimum_intensity"] >= gates["minimum_intensity_at_least"]
            and report["all_reported_diagnostics_finite"]
            and report["aitken_step_count"] >= gates["aitken_step_count_at_least"]
            and all(np.isfinite(row["raw_fixed_point_residual"]) for row in history)
        ),
        "contraction_gate_passed": final_fraction
        < gates["final_raw_residual_strictly_below_1p8_fraction"],
        "resource_and_runtime_gates_passed": bool(
            report["peak_process_rss_mib"]
            < gates["worker_peak_rss_strictly_below_mib"]
            and report["total_runtime_s"]
            < gates["worker_runtime_strictly_below_s"]
        ),
        "full_column_fixed_point_authorized": False,
        "full_orbit_authorized": False,
        "matter_feedback_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b6g_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "source_hashes_passed",
            "configuration_and_first_map_exact",
            "nonnegative_finite_and_aitken_used",
            "contraction_gate_passed",
            "resource_and_runtime_gates_passed",
        )
    )
    decision["full_frequency_aitken_pilot_authorized"] = bool(
        decision["phase7b6g_gate_passed"]
    )
    report["decision"] = decision
    report["reference_guarded_1p8"] = reference
    report["figures"] = ["phase7b6g_vector_aitken.png"]
    _write_json_atomic(OUTPUT / "phase7b6g_vector_aitken_summary.json", report)
    _plot(OUTPUT / "phase7b6g_vector_aitken.png", reference, report)
    return report


def _plot(path: Path, reference: dict[str, object], report: dict[str, object]) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].semilogy(
        [row["iteration"] for row in reference["history"]],
        [row["raw_fixed_point_residual"] for row in reference["history"]],
        label="Guarded 1.8",
    )
    axes[0, 0].semilogy(
        [row["iteration"] for row in report["history"]],
        [row["raw_fixed_point_residual"] for row in report["history"]],
        label="Vector Aitken",
    )
    axes[0, 0].set(
        xlabel="Source-map count",
        ylabel="Raw fixed-point residual",
        title="(a) Full-depth convergence",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].plot(
        [row["iteration"] for row in report["history"]],
        [row["accepted_weight"] for row in report["history"]],
        "o-",
        color="#f58518",
    )
    axes[0, 1].set(
        xlabel="Source-map count",
        ylabel="Accepted weight",
        title="(b) Dynamic relaxation",
    )
    axes[1, 0].bar(
        ["Aitken steps", "Fallback steps"],
        [report["aitken_step_count"], report["fallback_step_count"]],
        color=["#54a24b", "#777777"],
    )
    axes[1, 0].set(ylabel="Count", title="(c) Accepted update type")
    axes[1, 1].bar(
        ["Measured fraction", "Gate"],
        [report["final_to_guarded_1p8_residual_fraction"], 0.5],
        color=["#4c78a8", "#555555"],
    )
    axes[1, 1].set(
        ylabel="Final residual / guarded 1.8",
        title="(d) Fixed-cost improvement",
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6g_preregistered_vector_aitken.json",
    )
    args = parser.parse_args()
    report = run(args.protocol)
    print(json.dumps(report["decision"], indent=2))


if __name__ == "__main__":
    main()
