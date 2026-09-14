"""Phase 7B6c：验证逐次整步拒绝的非负性保护超松弛。"""

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
    from scripts.phase7b5v_streaming_turning_gate import (
        _diagnostics,
        _formal_context,
        _scale_error,
    )
    from scripts.phase7b6b_relaxed_fixed_point import (
        _relative_array_maximum,
        _sha256_array,
        _spectrum_l1_error,
        _write_json_atomic,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )
    from phase7b5v_streaming_turning_gate import (  # type: ignore[no-redef]
        _diagnostics,
        _formal_context,
        _scale_error,
    )
    from phase7b6b_relaxed_fixed_point import (  # type: ignore[no-redef]
        _relative_array_maximum,
        _sha256_array,
        _spectrum_l1_error,
        _write_json_atomic,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "95d5294cfe3af7639b7bd2275ce3ef05844a856e63bb811e1e18cceddbc4df2e"
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
        raise RuntimeError(f"frozen Phase 7B6c protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6c source changed: {source['path']}")
    return protocol


def run_worker(protocol_path: Path, policy_name: str, output_path: Path) -> None:
    protocol = _load_protocol(protocol_path)
    policies = protocol["candidate"]["policies"]
    if policy_name not in policies:
        raise ValueError("policy is not in the frozen candidate set")
    candidate_weights = tuple(float(value) for value in policies[policy_name])
    input_path = ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]
    (
        _loaded,
        state,
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        _split_mu,
        initial,
        outer,
        continuum,
    ) = _formal_context(input_path)
    with np.load(
        ROOT / protocol["sources"]["phase7b5w_reference_state"]["path"]
    ) as saved:
        reference_intensity = np.array(saved["final_lab_intensity_density"], copy=True)
        reference_spectrum = np.array(saved["volume_mean_comoving_intensity"], copy=True)
        reference_edge = np.array(saved["active_edge_hz"], copy=True)
    if not np.array_equal(reference_edge, stencil.active_lab_edge_hz):
        raise RuntimeError("Phase 7B6c reference frequency edges changed")
    previous = json.loads(
        (ROOT / protocol["sources"]["phase7b5w_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )["runs"]["monolithic"]
    scalar_names = (
        "frequency_integrated_volume_mean_comoving_intensity",
        "h_i_photoionization_rate_s1",
        "he_i_photoionization_rate_s1",
        "he_ii_photoionization_rate_s1",
        "final_radiation_energy_erg_cm2",
    )
    tolerance = float(protocol["reference"]["fixed_point_tolerance"])
    maximum_iterations = int(protocol["candidate"]["maximum_iterations"])
    current = np.array(initial, copy=True)
    history: list[dict[str, object]] = []
    converged = False
    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    final_raw_residual = float("inf")
    for iteration in range(1, maximum_iterations + 1):
        result = solve_mixed_frame_ale_group_step(
            stencil,
            old_edge,
            new_edge,
            mu,
            weight,
            initial,
            outer,
            continuum.true_absorption_total_per_cm,
            continuum.thermal_emissivity_total_cgs,
            continuum.electron_scattering_per_cm,
            state["beta"],
            state["duration_s"],
            propagation_speed_cm_s=LIGHT_SPEED_CM_S,
            source_iteration_initial_guess=current,
            diagnostic_fixed_iteration_count=1,
            spatial_scheme="step_characteristics",
            source_map_only=True,
        )
        mapped = result.final_lab_intensity_density
        delta = mapped - current
        scale = max(float(np.max(np.abs(mapped))), float(np.max(np.abs(current))))
        final_raw_residual = (
            float(np.max(np.abs(delta))) / scale
            if scale > 0.0
            else float(np.max(np.abs(delta)))
        )
        tested = []
        accepted_weight = None
        accepted_trial = None
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
                accepted_weight = omega
                accepted_trial = trial
                break
        if accepted_trial is None or accepted_weight is None:
            raise ArithmeticError("even the unmodified source-map step became invalid")
        current = accepted_trial
        history.append(
            {
                "iteration": iteration,
                "raw_fixed_point_residual": final_raw_residual,
                "accepted_weight": accepted_weight,
                "tested_weights": tested,
            }
        )
        if final_raw_residual <= tolerance:
            converged = True
            break
    if not converged:
        raise ArithmeticError(f"Phase 7B6c policy {policy_name} did not converge")

    audit = solve_mixed_frame_ale_group_step(
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        initial,
        outer,
        continuum.true_absorption_total_per_cm,
        continuum.thermal_emissivity_total_cgs,
        continuum.electron_scattering_per_cm,
        state["beta"],
        state["duration_s"],
        propagation_speed_cm_s=LIGHT_SPEED_CM_S,
        source_iteration_initial_guess=current,
        diagnostic_fixed_iteration_count=1,
        spatial_scheme="step_characteristics",
    )
    audit_mapped = audit.final_lab_intensity_density
    audit_scale = max(float(np.max(np.abs(audit_mapped))), float(np.max(np.abs(current))))
    audit_difference = float(np.max(np.abs(audit_mapped - current)))
    audit_raw_residual = (
        audit_difference / audit_scale if audit_scale > 0.0 else audit_difference
    )
    scalars, spectrum = _diagnostics(
        stencil, mu, weight, state["beta"], current, outer, new_edge
    )
    scalar_errors = {
        name: _scale_error(scalars[name], previous[name]) for name in scalar_names
    }
    accepted_counts = {
        str(omega): sum(row["accepted_weight"] == omega for row in history)
        for omega in candidate_weights
    }
    rejected_counts = {
        str(omega): sum(
            any(
                trial["weight"] == omega and not trial["accepted"]
                for trial in row["tested_weights"]
            )
            for row in history
        )
        for omega in candidate_weights
        if omega > 1.0
    }
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "policy": policy_name,
        "candidate_weights": candidate_weights,
        "fixed_point_converged": True,
        "fixed_point_iterations": len(history),
        "final_raw_fixed_point_residual": final_raw_residual,
        "audit_raw_fixed_point_residual": audit_raw_residual,
        "audit_coupled_residual": audit.global_scale_normalized_coupled_residual,
        "audit_energy_ledger_residual": audit.total_relative_energy_ledger_residual,
        "minimum_intensity": float(np.min(current)),
        "final_intensity_sha256": _sha256_array(current),
        "final_intensity_maximum_relative_error": _relative_array_maximum(
            current, reference_intensity
        ),
        "final_spectrum_l1_relative_error": _spectrum_l1_error(
            reference_edge, spectrum, reference_spectrum
        ),
        "final_scalar_relative_errors": scalar_errors,
        "final_scalars": scalars,
        "accepted_weight_counts": accepted_counts,
        "rejected_weight_counts": rejected_counts,
        "accelerated_step_count": sum(
            row["accepted_weight"] > 1.0 for row in history
        ),
        "runtime_s": time.perf_counter() - started,
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
        "history": history,
    }
    _write_json_atomic(output_path, report)
    print(json.dumps({key: value for key, value in report.items() if key != "history"}, indent=2))


def _plot(
    path: Path,
    baseline: dict[str, object],
    reports: list[dict[str, object]],
    selected_policy: str | None,
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    baseline_history = baseline["history"]
    axes[0, 0].semilogy(
        [row["iteration"] for row in baseline_history],
        [row["raw_fixed_point_residual"] for row in baseline_history],
        label="Jacobi baseline",
    )
    for report in reports:
        axes[0, 0].semilogy(
            [row["iteration"] for row in report["history"]],
            [row["raw_fixed_point_residual"] for row in report["history"]],
            label=report["policy"].replace("_", " "),
        )
    axes[0, 0].axhline(1.0e-10, color="0.25", ls="--", label="Tolerance")
    axes[0, 0].set(
        xlabel="Iteration",
        ylabel="Raw fixed-point residual",
        title="(a) Guarded residual histories",
    )
    axes[0, 0].legend(frameon=False)

    names = ["baseline", *[report["policy"].removeprefix("guarded_") for report in reports]]
    iterations = [
        baseline["fixed_point_iterations"],
        *[report["fixed_point_iterations"] for report in reports],
    ]
    colors = ["#777777", *["#4c78a8" for _ in reports]]
    axes[0, 1].bar(names, iterations, color=colors)
    axes[0, 1].axhline(28, color="0.25", ls="--", label="Selection gate")
    axes[0, 1].set(ylabel="Iterations", title="(b) Iteration reduction")
    axes[0, 1].legend(frameon=False)

    for report in reports:
        axes[1, 0].step(
            [row["iteration"] for row in report["history"]],
            [row["accepted_weight"] for row in report["history"]],
            where="mid",
            label=report["policy"].replace("_", " "),
        )
    axes[1, 0].set(
        xlabel="Iteration",
        ylabel="Accepted weight",
        title="(c) Whole-step positivity guard",
        ylim=(0.95, 1.85),
    )
    axes[1, 0].legend(frameon=False)

    maximum_errors = [
        max(
            report["final_intensity_maximum_relative_error"],
            report["final_spectrum_l1_relative_error"],
            max(report["final_scalar_relative_errors"].values()),
        )
        for report in reports
    ]
    axes[1, 1].bar(names[1:], np.asarray(maximum_errors) / 1.0e-9, color="#54a24b")
    axes[1, 1].axhline(1.0, color="0.25", ls="--", label="Science gate")
    axes[1, 1].set(
        ylabel="Maximum reference error / gate",
        title=f"(d) Fixed-point identity; selected: {selected_policy}",
    )
    axes[1, 1].legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6c_preregistered_guarded_relaxation.json",
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
    for policy_name in protocol["candidate"]["policies"]:
        output = OUTPUT / f"phase7b6c_{policy_name}.json"
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
                f"Phase 7B6c {policy_name} failed:\n"
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        print(completed.stdout, end="")
        reports.append(json.loads(output.read_text(encoding="utf-8")))

    baseline = json.loads(
        (ROOT / protocol["sources"]["phase7b6b_baseline"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    gates = protocol["gates"]
    eligible = {
        report["policy"]: bool(
            report["fixed_point_converged"]
            and report["final_raw_fixed_point_residual"]
            <= gates["all_final_raw_residual_at_most"]
            and report["audit_raw_fixed_point_residual"]
            <= gates["all_audited_raw_residual_at_most"]
            and report["final_intensity_maximum_relative_error"]
            < gates["all_final_intensity_maximum_relative_error_strictly_below"]
            and report["final_spectrum_l1_relative_error"]
            < gates["all_final_spectrum_l1_relative_error_strictly_below"]
            and max(report["final_scalar_relative_errors"].values())
            < gates["all_final_scalar_relative_error_strictly_below"]
            and report["minimum_intensity"] >= gates["minimum_intensity_at_least"]
            and report["accelerated_step_count"] > 0
            and report["peak_process_rss_mib"]
            < gates["each_worker_peak_rss_strictly_below_mib"]
        )
        for report in reports
    }
    improving = {
        report["policy"]: bool(
            eligible[report["policy"]]
            and report["fixed_point_iterations"] < baseline["fixed_point_iterations"]
        )
        for report in reports
    }
    selectable = [report for report in reports if improving[report["policy"]]]
    selected = min(
        selectable,
        key=lambda report: (
            report["fixed_point_iterations"],
            max(report["candidate_weights"]),
        ),
    ) if selectable else None
    decision = {
        "frozen_protocol_hash_passed": True,
        "source_hashes_passed": True,
        "retained_phase7b6b_failure_passed": True,
        "all_policies_converged_and_passed": all(eligible.values()),
        "at_least_two_policies_improve": sum(improving.values()) >= 2,
        "selected_iteration_gate_passed": bool(
            selected is not None
            and selected["fixed_point_iterations"]
            <= gates["selected_iterations_at_most"]
        ),
        "full_column_fixed_point_authorized": False,
        "full_orbit_authorized": False,
        "matter_feedback_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b6c_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "source_hashes_passed",
            "retained_phase7b6b_failure_passed",
            "all_policies_converged_and_passed",
            "at_least_two_policies_improve",
            "selected_iteration_gate_passed",
        )
    )
    decision["short_full_depth_contraction_pilot_authorized"] = bool(
        decision["phase7b6c_gate_passed"]
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "retained_baseline": {
            key: baseline[key]
            for key in (
                "fixed_point_iterations",
                "final_raw_fixed_point_residual",
                "final_intensity_sha256",
            )
        },
        "runs": reports,
        "eligible_policies": eligible,
        "improving_policies": improving,
        "selected_policy": selected["policy"] if selected is not None else None,
        "selected_maximum_weight": (
            max(selected["candidate_weights"]) if selected is not None else None
        ),
        "selected_iterations": (
            selected["fixed_point_iterations"] if selected is not None else None
        ),
        "decision": decision,
        "figures": ["phase7b6c_guarded_relaxation.png"],
    }
    _write_json_atomic(OUTPUT / "phase7b6c_guarded_relaxation_summary.json", summary)
    _plot(
        OUTPUT / "phase7b6c_guarded_relaxation.png",
        baseline,
        reports,
        summary["selected_policy"],
    )
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
