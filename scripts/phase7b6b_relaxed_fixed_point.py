"""Phase 7B6b：在严格单单元参考上验证数值超松弛。"""

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


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "58c02021b1e44c712aa2beac9199be7d71a512e85600d99e21a7618cb164d443"
)
MIB = 1024**2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _sha256_array(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B6b protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6b source changed: {source['path']}")
    return protocol


def _relative_array_maximum(candidate: np.ndarray, reference: np.ndarray) -> float:
    scale = max(float(np.max(np.abs(candidate))), float(np.max(np.abs(reference))))
    difference = float(np.max(np.abs(candidate - reference)))
    return difference / scale if scale > 0.0 else difference


def _spectrum_l1_error(
    edge: np.ndarray, candidate: np.ndarray, reference: np.ndarray
) -> float:
    width = np.diff(edge)
    numerator = float(np.sum(width * np.abs(candidate - reference)))
    scale = max(
        float(np.sum(width * np.abs(candidate))),
        float(np.sum(width * np.abs(reference))),
    )
    return numerator / scale if scale > 0.0 else numerator


def run_worker(protocol_path: Path, omega: float, output_path: Path) -> None:
    protocol = _load_protocol(protocol_path)
    weights = tuple(float(value) for value in protocol["candidate"]["relaxation_weights"])
    if omega not in weights:
        raise ValueError("relaxation weight is not in the frozen candidate set")
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
        raise RuntimeError("Phase 7B6b reference frequency edges changed")

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
    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    history: list[dict[str, object]] = []
    converged = False
    valid = True
    failure_reason = None
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
        # omega=1 是逐位参考；加速候选只改迭代路径，不改固定点方程。
        trial = np.array(mapped, copy=True) if omega == 1.0 else current + omega * delta
        trial_finite = bool(np.all(np.isfinite(trial)))
        trial_minimum = float(np.min(trial)) if trial_finite else float("nan")
        history.append(
            {
                "iteration": iteration,
                "raw_fixed_point_residual": final_raw_residual,
                "trial_minimum_intensity": trial_minimum,
                "trial_finite": trial_finite,
            }
        )
        if not trial_finite or trial_minimum < 0.0:
            valid = False
            failure_reason = "non-finite or negative relaxed trial"
            break
        current = trial
        if final_raw_residual <= tolerance:
            converged = True
            break

    audit_raw_residual = None
    audit_coupled_residual = None
    audit_energy_ledger_residual = None
    intensity_error = None
    spectrum_error = None
    scalar_errors = None
    scalars = None
    final_hash = None
    minimum_intensity = None
    if valid and converged:
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
        audit_scale = max(
            float(np.max(np.abs(audit_mapped))), float(np.max(np.abs(current)))
        )
        audit_difference = float(np.max(np.abs(audit_mapped - current)))
        audit_raw_residual = (
            audit_difference / audit_scale if audit_scale > 0.0 else audit_difference
        )
        audit_coupled_residual = audit.global_scale_normalized_coupled_residual
        audit_energy_ledger_residual = audit.total_relative_energy_ledger_residual
        scalars, spectrum = _diagnostics(
            stencil, mu, weight, state["beta"], current, outer, new_edge
        )
        intensity_error = _relative_array_maximum(current, reference_intensity)
        spectrum_error = _spectrum_l1_error(reference_edge, spectrum, reference_spectrum)
        scalar_errors = {
            name: _scale_error(scalars[name], previous[name]) for name in scalar_names
        }
        final_hash = _sha256_array(current)
        minimum_intensity = float(np.min(current))

    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "relaxation_weight": omega,
        "candidate_valid": valid,
        "failure_reason": failure_reason,
        "fixed_point_converged": converged,
        "fixed_point_iterations": len(history),
        "final_raw_fixed_point_residual": final_raw_residual,
        "audit_raw_fixed_point_residual": audit_raw_residual,
        "audit_coupled_residual": audit_coupled_residual,
        "audit_energy_ledger_residual": audit_energy_ledger_residual,
        "minimum_intensity": minimum_intensity,
        "final_intensity_sha256": final_hash,
        "final_intensity_maximum_relative_error": intensity_error,
        "final_spectrum_l1_relative_error": spectrum_error,
        "final_scalar_relative_errors": scalar_errors,
        "final_scalars": scalars,
        "runtime_s": time.perf_counter() - started,
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
        "history": history,
    }
    _write_json_atomic(output_path, report)
    print(json.dumps({key: value for key, value in report.items() if key != "history"}, indent=2))


def _plot(path: Path, reports: list[dict[str, object]], protocol: dict[str, object]) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    for report in reports:
        history = report["history"]
        axes[0, 0].semilogy(
            [row["iteration"] for row in history],
            [row["raw_fixed_point_residual"] for row in history],
            marker=".",
            label=f"omega = {report['relaxation_weight']:.1f}",
        )
    axes[0, 0].axhline(1.0e-10, color="0.25", ls="--", label="Tolerance")
    axes[0, 0].set(
        xlabel="Iteration",
        ylabel="Raw fixed-point residual",
        title="(a) Residual histories",
    )
    axes[0, 0].legend(frameon=False)

    labels = [f"{report['relaxation_weight']:.1f}" for report in reports]
    iterations = [report["fixed_point_iterations"] for report in reports]
    axes[0, 1].bar(labels, iterations, color="#4c78a8")
    axes[0, 1].axhline(
        protocol["gates"]["selected_iterations_at_most"],
        color="0.25",
        ls="--",
        label="Selection gate",
    )
    axes[0, 1].set(
        xlabel="Relaxation weight",
        ylabel="Iterations",
        title="(b) Iteration cost",
    )
    axes[0, 1].legend(frameon=False)

    valid_and_converged = [
        float(report["candidate_valid"] and report["fixed_point_converged"])
        for report in reports
    ]
    axes[1, 0].bar(labels, valid_and_converged, color="#f58518")
    axes[1, 0].set_ylim(0.0, 1.15)
    axes[1, 0].set(
        xlabel="Relaxation weight",
        ylabel="Valid and converged",
        title="(c) Positivity gate",
    )

    contraction = []
    for report in reports:
        residual = np.asarray(
            [row["raw_fixed_point_residual"] for row in report["history"]],
            dtype=np.float64,
        )
        ratios = residual[1:] / residual[:-1]
        usable = ratios[np.isfinite(ratios)]
        contraction.append(float(np.median(usable[-5:])) if usable.size else np.nan)
    axes[1, 1].plot(labels, contraction, "o-", color="#54a24b")
    axes[1, 1].set(
        xlabel="Relaxation weight",
        ylabel="Median final residual ratio",
        title="(d) Asymptotic contraction",
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6b_preregistered_relaxed_fixed_point.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--weight", type=float)
    parser.add_argument("--worker-output", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.weight is None or args.worker_output is None:
            raise ValueError("worker mode requires weight and output")
        run_worker(args.protocol, args.weight, args.worker_output)
        return

    protocol = _load_protocol(args.protocol)
    reports = []
    for omega in protocol["candidate"]["relaxation_weights"]:
        output = OUTPUT / f"phase7b6b_omega{str(omega).replace('.', 'p')}.json"
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--protocol",
            str(args.protocol),
            "--weight",
            str(omega),
            "--worker-output",
            str(output),
        ]
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        if completed.returncode != 0:
            raise RuntimeError(
                f"Phase 7B6b omega={omega} failed:\n"
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        print(completed.stdout, end="")
        reports.append(json.loads(output.read_text(encoding="utf-8")))

    gates = protocol["gates"]
    baseline = next(report for report in reports if report["relaxation_weight"] == 1.0)
    eligible = {}
    for report in reports:
        scalar_errors = report["final_scalar_relative_errors"]
        eligible[report["relaxation_weight"]] = bool(
            report["candidate_valid"]
            and report["fixed_point_converged"]
            and report["final_raw_fixed_point_residual"]
            <= gates["all_converged_raw_residual_at_most"]
            and report["audit_raw_fixed_point_residual"]
            <= gates["all_audited_raw_residual_at_most"]
            and report["final_intensity_maximum_relative_error"]
            < gates["all_final_intensity_maximum_relative_error_strictly_below"]
            and report["final_spectrum_l1_relative_error"]
            < gates["all_final_spectrum_l1_relative_error_strictly_below"]
            and max(scalar_errors.values())
            < gates["all_final_scalar_relative_error_strictly_below"]
            and report["minimum_intensity"] >= gates["minimum_intensity_at_least"]
            and report["peak_process_rss_mib"]
            < gates["each_worker_peak_rss_strictly_below_mib"]
        )
    accelerated = [report for report in reports if report["relaxation_weight"] > 1.0]
    improving = {
        report["relaxation_weight"]: bool(
            eligible[report["relaxation_weight"]]
            and report["fixed_point_iterations"] < baseline["fixed_point_iterations"]
        )
        for report in accelerated
    }
    adjacent_pairs = [
        [first["relaxation_weight"], second["relaxation_weight"]]
        for first, second in zip(accelerated[:-1], accelerated[1:], strict=True)
        if improving[first["relaxation_weight"]]
        and improving[second["relaxation_weight"]]
    ]
    selectable = [report for report in accelerated if improving[report["relaxation_weight"]]]
    selected = min(
        selectable,
        key=lambda report: (
            report["fixed_point_iterations"],
            report["relaxation_weight"],
        ),
    ) if selectable else None
    decision = {
        "frozen_protocol_hash_passed": True,
        "source_hashes_passed": True,
        "baseline_hash_exact": baseline["final_intensity_sha256"]
        == gates["baseline_final_hash_exactly"],
        "baseline_converged": eligible[1.0],
        "all_valid_runs_pass_science_and_resource_gates": all(
            eligible[report["relaxation_weight"]]
            for report in reports
            if report["candidate_valid"] and report["fixed_point_converged"]
        ),
        "two_adjacent_accelerated_weights_improve": len(adjacent_pairs) > 0,
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
    decision["phase7b6b_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "source_hashes_passed",
            "baseline_hash_exact",
            "baseline_converged",
            "all_valid_runs_pass_science_and_resource_gates",
            "two_adjacent_accelerated_weights_improve",
            "selected_iteration_gate_passed",
        )
    )
    decision["short_full_depth_contraction_pilot_authorized"] = bool(
        decision["phase7b6b_gate_passed"]
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "runs": reports,
        "eligible_weights": eligible,
        "improving_accelerated_weights": improving,
        "adjacent_improving_pairs": adjacent_pairs,
        "selected_relaxation_weight": (
            selected["relaxation_weight"] if selected is not None else None
        ),
        "selected_iterations": (
            selected["fixed_point_iterations"] if selected is not None else None
        ),
        "decision": decision,
        "figures": ["phase7b6b_relaxed_fixed_point.png"],
    }
    _write_json_atomic(OUTPUT / "phase7b6b_relaxed_fixed_point_summary.json", summary)
    _plot(OUTPUT / "phase7b6b_relaxed_fixed_point.png", reports, protocol)
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
