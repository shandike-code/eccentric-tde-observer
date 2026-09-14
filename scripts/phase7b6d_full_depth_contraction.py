"""Phase 7B6d：在最坏全深度频率块上比较 16 次收缩。"""

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
    from scripts import phase7b5x_full_depth_block_probe as phase7b5x
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
    from scripts.phase7b6b_relaxed_fixed_point import (
        _sha256_array,
        _write_json_atomic,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b5x_full_depth_block_probe as phase7b5x  # type: ignore[no-redef]
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )
    from phase7b6b_relaxed_fixed_point import (  # type: ignore[no-redef]
        _sha256_array,
        _write_json_atomic,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "b76d6c4df83077dc939cf532393c7b8642d498aea9ba972b00ef572c7f717846"
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
        raise RuntimeError(f"frozen Phase 7B6d protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6d source changed: {source['path']}")
    return protocol


def _block_fields(protocol: dict[str, object]) -> dict[str, object]:
    context = phase7b5x._context(protocol)
    configuration = protocol["configuration"]
    if (
        context["phase"] != configuration["phase_index"]
        or context["selected_block_index"] != configuration["block_index"]
    ):
        raise RuntimeError("Phase 7B6d worst phase or block changed")
    block = context["selected"]
    local = block.local_stencil
    full = context["full"]
    phase = int(context["phase"])
    following = int(context["following"])
    temperature = full["temperature_k"][phase]
    density = full["density_g_cm3"][phase]
    hydrogen = full["hydrogen_fraction"][phase]
    helium = full["helium_fraction"][phase]
    parent_planck = phase7b5x._parent_group_planck(
        local.comoving_collision_edge_hz, temperature
    )
    parent_microphysics = phase7b5x.ground_state_milne_multigroup(
        density,
        temperature,
        local.comoving_collision_edge_hz,
        parent_planck,
        hydrogen[:, 0],
        hydrogen[:, 1],
        helium[:, 0],
        helium[:, 1],
        helium[:, 2],
        order_per_group=16,
    ).continuum
    parent_outer = phase7b5x._parent_boosted_planck_outer(
        local.outer_lab_edge_hz,
        context["mu"],
        context["weight"],
        context["parent_beta"],
        temperature,
    )
    outer = np.repeat(parent_outer, 16, axis=2)
    active = slice(local.active_outer_group_start, local.active_outer_group_stop)
    return {
        "context": context,
        "local": local,
        "old_edge": phase7b5x._subdivide_column_edge(full["edge_cm"][phase], 16),
        "new_edge": phase7b5x._subdivide_column_edge(full["edge_cm"][following], 16),
        "initial": np.array(outer[active], copy=True),
        "outer": outer,
        "true_absorption": np.repeat(
            parent_microphysics.true_absorption_total_per_cm, 16, axis=1
        ),
        "thermal_emissivity": np.repeat(
            parent_microphysics.thermal_emissivity_total_cgs, 16, axis=1
        ),
        "scattering": np.repeat(
            parent_microphysics.electron_scattering_per_cm, 16, axis=1
        ),
    }


def run_worker(protocol_path: Path, policy_name: str, output_path: Path) -> None:
    protocol = _load_protocol(protocol_path)
    policies = protocol["configuration"]["policies"]
    if policy_name not in policies:
        raise ValueError("policy is not in the frozen full-depth pilot")
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

    audit_started = time.perf_counter()
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
    audit_runtime = time.perf_counter() - audit_started
    audit_map = audit.final_lab_intensity_density
    audit_scale = max(float(np.max(np.abs(audit_map))), float(np.max(np.abs(current))))
    audit_difference = float(np.max(np.abs(audit_map - current)))
    audit_raw_residual = (
        audit_difference / audit_scale if audit_scale > 0.0 else audit_difference
    )
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    diagnostics = np.asarray(
        [
            audit_raw_residual,
            audit.global_scale_normalized_coupled_residual,
            audit.total_relative_energy_ledger_residual,
        ]
    )
    report = {
        "policy": policy_name,
        "candidate_weights": candidate_weights,
        "phase_index": context["phase"],
        "block_index": context["selected_block_index"],
        "core_group_start": context["selected"].core_group_start,
        "core_group_stop": context["selected"].core_group_stop,
        "radiation_depth_cell_count": context["beta"].size,
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
        "audit_runtime_s": audit_runtime,
        "total_runtime_s": time.perf_counter() - started,
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
        "history": history,
    }
    _write_json_atomic(output_path, report)
    print(json.dumps({key: value for key, value in report.items() if key != "history"}, indent=2))


def _plot(
    path: Path,
    baseline: dict[str, object],
    guarded: dict[str, object],
    residual_fraction: float,
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    for report, label in ((baseline, "Jacobi"), (guarded, "Guarded 1.8")):
        axes[0, 0].semilogy(
            [row["iteration"] for row in report["history"]],
            [row["raw_fixed_point_residual"] for row in report["history"]],
            marker=".",
            label=label,
        )
    axes[0, 0].set(
        xlabel="Source-map count",
        ylabel="Raw fixed-point residual",
        title="(a) Full-depth worst block",
    )
    axes[0, 0].legend(frameon=False)

    axes[0, 1].step(
        [row["iteration"] for row in guarded["history"]],
        [row["accepted_weight"] for row in guarded["history"]],
        where="mid",
        color="#f58518",
    )
    axes[0, 1].set(
        xlabel="Source-map count",
        ylabel="Accepted weight",
        title="(b) Whole-step guard",
        ylim=(0.95, 1.85),
    )

    axes[1, 0].bar(
        ["Measured fraction", "Gate"],
        [residual_fraction, 0.8],
        color=["#54a24b", "#555555"],
    )
    axes[1, 0].set(
        ylabel="Guarded / Jacobi final residual",
        title="(c) Contraction improvement",
    )

    x = np.arange(2)
    width = 0.38
    runtime_bars = axes[1, 1].bar(
        x - width / 2,
        [baseline["total_runtime_s"], guarded["total_runtime_s"]],
        width,
        label="Runtime",
    )
    second = axes[1, 1].twinx()
    rss_bars = second.bar(
        x + width / 2,
        [baseline["peak_process_rss_mib"], guarded["peak_process_rss_mib"]],
        width,
        color="#e45756",
        label="Peak RSS",
    )
    axes[1, 1].set_xticks(x, ["Jacobi", "Guarded 1.8"])
    axes[1, 1].set_ylabel("Runtime (s)")
    second.set_ylabel("Peak RSS (MiB)")
    axes[1, 1].set_title("(d) Resource envelope")
    axes[1, 1].legend(
        (runtime_bars[0], rss_bars[0]),
        ("Runtime", "Peak RSS"),
        frameon=False,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6d_preregistered_full_depth_contraction.json",
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
    reports = {}
    for policy_name in protocol["configuration"]["policies"]:
        output = OUTPUT / f"phase7b6d_{policy_name}.json"
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
                f"Phase 7B6d {policy_name} failed:\n"
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        print(completed.stdout, end="")
        reports[policy_name] = json.loads(output.read_text(encoding="utf-8"))

    baseline = reports["jacobi"]
    guarded = reports["guarded_1p8"]
    residual_fraction = (
        guarded["final_raw_fixed_point_residual"]
        / baseline["final_raw_fixed_point_residual"]
    )
    gates = protocol["gates"]
    decision = {
        "frozen_protocol_hash_passed": True,
        "source_hashes_passed": True,
        "configuration_exact": all(
            report["phase_index"] == protocol["configuration"]["phase_index"]
            and report["block_index"] == protocol["configuration"]["block_index"]
            and report["source_map_count"] == gates["each_map_count_exactly"]
            for report in reports.values()
        ),
        "first_source_maps_exact": all(
            report["first_source_map_sha256"]
            == gates["first_map_intensity_sha256_exactly"]
            for report in reports.values()
        ),
        "all_intensities_nonnegative": all(
            report["minimum_intensity"] >= gates["minimum_intensity_at_least"]
            and all(
                row["minimum_intensity"] >= gates["minimum_intensity_at_least"]
                for row in report["history"]
            )
            for report in reports.values()
        ),
        "all_residuals_and_diagnostics_finite": all(
            report["full_diagnostics_finite"]
            and all(np.isfinite(row["raw_fixed_point_residual"]) for row in report["history"])
            for report in reports.values()
        ),
        "guarded_acceleration_used": guarded["accelerated_step_count"]
        >= gates["guarded_accelerated_step_count_at_least"],
        "guarded_contraction_gate_passed": residual_fraction
        < gates["guarded_final_raw_residual_strictly_below_baseline_fraction"],
        "resource_and_runtime_gates_passed": all(
            report["peak_process_rss_mib"]
            < gates["each_worker_peak_rss_strictly_below_mib"]
            and report["total_runtime_s"]
            < gates["each_worker_runtime_strictly_below_s"]
            for report in reports.values()
        ),
        "full_column_fixed_point_authorized": False,
        "full_orbit_authorized": False,
        "matter_feedback_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b6d_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "source_hashes_passed",
            "configuration_exact",
            "first_source_maps_exact",
            "all_intensities_nonnegative",
            "all_residuals_and_diagnostics_finite",
            "guarded_acceleration_used",
            "guarded_contraction_gate_passed",
            "resource_and_runtime_gates_passed",
        )
    )
    decision["bounded_full_frequency_convergence_pilot_authorized"] = bool(
        decision["phase7b6d_gate_passed"]
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "runs": reports,
        "guarded_to_jacobi_final_residual_fraction": residual_fraction,
        "decision": decision,
        "figures": ["phase7b6d_full_depth_contraction.png"],
    }
    _write_json_atomic(OUTPUT / "phase7b6d_full_depth_contraction_summary.json", summary)
    _plot(
        OUTPUT / "phase7b6d_full_depth_contraction.png",
        baseline,
        guarded,
        residual_fraction,
    )
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
