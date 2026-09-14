"""Phase 7B6e：执行最坏全深度块的扩展保护权重门。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
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
    "a500eb713c97f1b2ce228b2f27e6f75e094c9f4eae91c5d72074b3747f5b438c"
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
        raise RuntimeError(f"frozen Phase 7B6e protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6e source changed: {source['path']}")
    return protocol


def run_worker(protocol_path: Path, policy_name: str, output_path: Path) -> None:
    protocol = _load_protocol(protocol_path)
    policies = protocol["configuration"]["policies"]
    if policy_name not in policies:
        raise ValueError("policy is not in the frozen extended set")
    candidate_weights = tuple(float(value) for value in policies[policy_name])
    fields = _block_fields(protocol)
    context = fields["context"]
    current = np.array(fields["initial"], copy=True)
    history: list[dict[str, object]] = []
    first_source_map_hash = None
    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    map_count = int(protocol["configuration"]["source_map_count_exactly"])
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
        delta = mapped - current
        scale = max(float(np.max(np.abs(mapped))), float(np.max(np.abs(current))))
        residual = (
            float(np.max(np.abs(delta))) / scale
            if scale > 0.0
            else float(np.max(np.abs(delta)))
        )
        tested = []
        accepted_trial = None
        accepted_weight = None
        for omega in candidate_weights:
            trial = np.array(mapped, copy=True) if omega == 1.0 else current + omega * delta
            finite = bool(np.all(np.isfinite(trial)))
            minimum = float(np.min(trial)) if finite else float("nan")
            accepted = bool(finite and minimum >= 0.0)
            tested.append(
                {
                    "weight": omega,
                    "finite": finite,
                    "minimum_intensity": minimum,
                    "accepted": accepted,
                }
            )
            if accepted:
                accepted_trial = trial
                accepted_weight = omega
                break
        if accepted_trial is None or accepted_weight is None:
            raise ArithmeticError("even the unmodified full-depth map became invalid")
        current = accepted_trial
        history.append(
            {
                "iteration": iteration,
                "raw_fixed_point_residual": residual,
                "accepted_weight": accepted_weight,
                "minimum_intensity": float(np.min(current)),
                "map_runtime_s": time.perf_counter() - map_started,
                "tested_weights": tested,
            }
        )

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
        ]
    )
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "policy": policy_name,
        "candidate_weights": candidate_weights,
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
        "full_diagnostics_finite": bool(np.all(np.isfinite(diagnostics))),
        "accepted_weight_counts": {
            str(omega): sum(row["accepted_weight"] == omega for row in history)
            for omega in candidate_weights
        },
        "accelerated_step_count": sum(
            row["accepted_weight"] > 1.0 for row in history
        ),
        "source_map_runtime_s": sum(row["map_runtime_s"] for row in history),
        "total_runtime_s": time.perf_counter() - started,
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
        "history": history,
    }
    _write_json_atomic(output_path, report)
    print(json.dumps({key: value for key, value in report.items() if key != "history"}, indent=2))


def _plot(
    path: Path,
    reference: dict[str, object],
    reports: list[dict[str, object]],
    selected_policy: str | None,
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].semilogy(
        [row["iteration"] for row in reference["history"]],
        [row["raw_fixed_point_residual"] for row in reference["history"]],
        label="Guarded 1.8",
        lw=2.2,
    )
    for report in reports:
        axes[0, 0].semilogy(
            [row["iteration"] for row in report["history"]],
            [row["raw_fixed_point_residual"] for row in report["history"]],
            label=report["policy"].replace("_", " "),
        )
    axes[0, 0].set(
        xlabel="Source-map count",
        ylabel="Raw fixed-point residual",
        title="(a) Extended guarded weights",
    )
    axes[0, 0].legend(frameon=False)

    labels = [report["policy"].removeprefix("guarded_") for report in reports]
    final_fraction = [
        report["final_raw_fixed_point_residual"]
        / reference["final_raw_fixed_point_residual"]
        for report in reports
    ]
    axes[0, 1].bar(labels, final_fraction, color="#4c78a8")
    axes[0, 1].axhline(0.8, color="0.25", ls="--", label="Selection gate")
    axes[0, 1].set(
        ylabel="Final residual / guarded 1.8",
        title=f"(b) Fixed-cost selection: {selected_policy}",
    )
    axes[0, 1].legend(frameon=False)

    for report in reports:
        axes[1, 0].step(
            [row["iteration"] for row in report["history"]],
            [row["accepted_weight"] for row in report["history"]],
            where="mid",
            label=report["policy"].replace("_", " "),
        )
    axes[1, 0].set(
        xlabel="Source-map count",
        ylabel="Accepted weight",
        title="(c) Whole-step positivity guard",
        ylim=(0.95, 2.45),
    )
    axes[1, 0].legend(frameon=False)

    runtime = [report["total_runtime_s"] for report in reports]
    rss = [report["peak_process_rss_mib"] for report in reports]
    x = np.arange(len(reports))
    width = 0.38
    first = axes[1, 1].bar(x - width / 2, runtime, width, label="Runtime")
    second_axis = axes[1, 1].twinx()
    second = second_axis.bar(x + width / 2, rss, width, color="#e45756", label="Peak RSS")
    axes[1, 1].set_xticks(x, labels)
    axes[1, 1].set_ylabel("Runtime (s)")
    second_axis.set_ylabel("Peak RSS (MiB)")
    axes[1, 1].set_title("(d) Resource envelope")
    axes[1, 1].legend((first[0], second[0]), ("Runtime", "Peak RSS"), frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6e_preregistered_extended_relaxation.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--policy")
    parser.add_argument("--worker-output", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.policy is None or args.worker_output is None:
            raise ValueError("worker mode requires policy and output")
        run_worker(args.protocol, args.policy, args.worker_output)
        return

    protocol = _load_protocol(args.protocol)
    reports = []
    for policy_name in protocol["configuration"]["policies"]:
        output = OUTPUT / f"phase7b6e_{policy_name}.json"
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--protocol",
            str(args.protocol),
            "--policy",
            policy_name,
            "--worker-output",
            str(output),
        ]
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        if completed.returncode != 0:
            raise RuntimeError(
                f"Phase 7B6e {policy_name} failed:\n"
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        print(completed.stdout, end="")
        reports.append(json.loads(output.read_text(encoding="utf-8")))

    reference = json.loads(
        (ROOT / protocol["sources"]["phase7b6d_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )["runs"]["guarded_1p8"]
    gates = protocol["gates"]
    improving = {
        report["policy"]: bool(
            report["final_raw_fixed_point_residual"]
            < reference["final_raw_fixed_point_residual"]
        )
        for report in reports
    }
    selectable = [report for report in reports if improving[report["policy"]]]
    selected = min(
        selectable,
        key=lambda report: (
            report["final_raw_fixed_point_residual"],
            max(report["candidate_weights"]),
        ),
    ) if selectable else None
    selected_fraction = (
        selected["final_raw_fixed_point_residual"]
        / reference["final_raw_fixed_point_residual"]
        if selected is not None
        else None
    )
    decision = {
        "frozen_protocol_hash_passed": True,
        "source_hashes_passed": True,
        "configuration_and_first_map_exact": all(
            report["phase_index"] == protocol["configuration"]["phase_index"]
            and report["block_index"] == protocol["configuration"]["block_index"]
            and report["source_map_count"] == gates["each_map_count_exactly"]
            and report["first_source_map_sha256"]
            == gates["first_source_map_sha256_exactly"]
            for report in reports
        ),
        "all_nonnegative_finite_and_accelerated": all(
            report["minimum_intensity"] >= gates["minimum_intensity_at_least"]
            and report["full_diagnostics_finite"]
            and all(np.isfinite(row["raw_fixed_point_residual"]) for row in report["history"])
            and report["accelerated_step_count"]
            >= gates["each_policy_accelerated_step_count_at_least"]
            for report in reports
        ),
        "at_least_two_improve_over_1p8": sum(improving.values()) >= 2,
        "selected_residual_gate_passed": bool(
            selected_fraction is not None
            and selected_fraction
            < gates["selected_final_residual_strictly_below_1p8_fraction"]
        ),
        "resource_and_runtime_gates_passed": all(
            report["peak_process_rss_mib"]
            < gates["each_worker_peak_rss_strictly_below_mib"]
            and report["total_runtime_s"]
            < gates["each_worker_runtime_strictly_below_s"]
            for report in reports
        ),
        "full_column_fixed_point_authorized": False,
        "full_orbit_authorized": False,
        "matter_feedback_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b6e_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "source_hashes_passed",
            "configuration_and_first_map_exact",
            "all_nonnegative_finite_and_accelerated",
            "at_least_two_improve_over_1p8",
            "selected_residual_gate_passed",
            "resource_and_runtime_gates_passed",
        )
    )
    decision["bounded_full_frequency_convergence_pilot_authorized"] = bool(
        decision["phase7b6e_gate_passed"]
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "reference_guarded_1p8": reference,
        "runs": reports,
        "improving_policies": improving,
        "selected_policy": selected["policy"] if selected is not None else None,
        "selected_maximum_weight": (
            max(selected["candidate_weights"]) if selected is not None else None
        ),
        "selected_to_1p8_final_residual_fraction": selected_fraction,
        "decision": decision,
        "figures": ["phase7b6e_extended_relaxation.png"],
    }
    _write_json_atomic(OUTPUT / "phase7b6e_extended_relaxation_summary.json", summary)
    _plot(
        OUTPUT / "phase7b6e_extended_relaxation.png",
        reference,
        reports,
        summary["selected_policy"],
    )
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
