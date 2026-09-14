"""Phase 7B9m：逐块精确正性主模外推及原算子残差审计。"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
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

try:
    from scripts import phase7b7i_second_radiation_map as phase7b7i
    from scripts import phase7b9d_inner_converged_base_radiation as phase7b9d
    from scripts import phase7b9i_finite_trial_radiation as phase7b9i
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b7i_second_radiation_map as phase7b7i  # type: ignore[no-redef]
    import phase7b9d_inner_converged_base_radiation as phase7b9d  # type: ignore[no-redef]
    import phase7b9i_finite_trial_radiation as phase7b9i  # type: ignore[no-redef]
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "287bb4e0959ac360bfc367b275282acf4b54a5ea331e8f6eda5acb5cd955944b"
)
MIB = 1024**2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if _sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9m protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or _sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9m source changed: {source['path']}"
                )
    return protocol


def _block_flux(
    intensity: np.ndarray,
    mu: np.ndarray,
    weight: np.ndarray,
    frequency_width: np.ndarray,
) -> np.ndarray:
    left = mu < 0.0
    right = mu > 0.0
    flux = 2.0 * np.pi * (
        np.einsum(
            "m,fm->f",
            weight[left] * np.abs(mu[left]),
            intensity[:, left, 0],
        )
        + np.einsum(
            "m,fm->f",
            weight[right] * mu[right],
            intensity[:, right, -1],
        )
    )
    return frequency_width * flux


def _relative_update(first: np.ndarray, second: np.ndarray) -> float:
    scale = max(float(np.max(np.abs(first))), float(np.max(np.abs(second))))
    change = float(np.max(np.abs(second - first)))
    return change / scale if scale > 0.0 else change


def _spectral_l1(first: np.ndarray, second: np.ndarray) -> float:
    scale = max(float(np.sum(np.abs(first))), float(np.sum(np.abs(second))))
    change = float(np.sum(np.abs(second - first)))
    return change / scale if scale > 0.0 else change


def _positivity_upper_bound(state: np.ndarray, direction: np.ndarray) -> float:
    bound = math.inf
    for start in range(0, state.shape[0], 8):
        stop = min(start + 8, state.shape[0])
        local_state = state[start:stop]
        local_direction = direction[start:stop]
        negative = local_direction < 0.0
        if np.any(negative):
            candidate = float(
                np.min(local_state[negative] / (-local_direction[negative]))
            )
            bound = min(bound, candidate)
    return bound


def _run_worker(protocol_path: Path, block_index: int, report_path: Path) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    selected = {
        int(row["block_index"]): row["role"]
        for row in protocol["configuration"]["selected_blocks"]
    }
    if block_index not in selected:
        raise ValueError("Phase 7B9m worker block is not preregistered")
    manifest = json.loads(
        (ROOT / protocol["sources"]["phase7b9k_manifest"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    current_path = ROOT / protocol["sources"]["current_map6_state"]["path"]
    residual_path = ROOT / protocol["sources"]["previous_raw_residual"]["path"]
    finite_protocol_path = ROOT / protocol["sources"]["finite_trial_protocol"]["path"]
    finite_protocol = phase7b9i._load_protocol(
        finite_protocol_path, validate_sources=False
    )
    phase7b9d._configure_worker(finite_protocol, current_path)
    template = phase7b7i._load_protocol(protocol_path, validate_sources=False)
    context = phase7b7i.phase7b7e.phase7b5x._context(template)
    if int(context["phase"]) != int(protocol["configuration"]["phase_index"]):
        raise RuntimeError("Phase 7B9m selected phase changed")
    block = context["blocks"][block_index]
    updated_material = phase7b7i._second_full_material(template)
    fields = phase7b7i.phase7b7e._local_fields(
        context, block, updated_material
    )
    shape = (
        int(protocol["configuration"]["physical_frequency_groups"]),
        int(protocol["configuration"]["angular_direction_count"]),
        int(protocol["configuration"]["radiation_depth_cell_count"]),
    )
    current_global = np.memmap(
        current_path, mode="r", dtype=np.float64, shape=shape
    )
    previous_residual_global = np.memmap(
        residual_path, mode="r", dtype=np.float64, shape=shape
    )
    full_active_start = int(context["stencil"].active_outer_group_start)
    full_active_stop = int(context["stencil"].active_outer_group_stop)
    physical_start = max(block.outer_group_start, full_active_start)
    physical_stop = min(block.outer_group_stop, full_active_stop)
    if physical_stop > physical_start:
        source_slice = slice(
            physical_start - full_active_start,
            physical_stop - full_active_start,
        )
        fields["outer"][
            physical_start - block.outer_group_start : physical_stop
            - block.outer_group_start
        ] = current_global[source_slice]
    core = slice(block.core_group_start, block.core_group_stop)
    current = np.array(current_global[core], copy=True)
    previous_residual = np.array(previous_residual_global[core], copy=True)
    del current_global, previous_residual_global
    mu = np.asarray(context["mu"])
    weight = np.asarray(context["weight"])
    global_edge = np.asarray(context["stencil"].active_lab_edge_hz)
    frequency_width = np.diff(global_edge)[core]

    def source_map(guess: np.ndarray) -> np.ndarray:
        result = phase7b7i.phase7b7e.solve_mixed_frame_ale_group_step(
            block.local_stencil,
            fields["old_edge"],
            fields["new_edge"],
            mu,
            weight,
            fields["initial"],
            fields["outer"],
            fields["true_absorption"],
            fields["thermal_emissivity"],
            fields["scattering"],
            context["beta"],
            context["duration_s"],
            propagation_speed_cm_s=phase7b7i.phase7b7e.LIGHT_SPEED_CM_S,
            source_iteration_initial_guess=guess,
            diagnostic_fixed_iteration_count=1,
            spatial_scheme=protocol["configuration"]["spatial_scheme"],
            source_map_only=True,
        )
        mapped = np.array(result.final_lab_intensity_density, copy=True)
        del result
        return mapped

    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    mapped = source_map(current)
    new_residual = mapped - current
    change = new_residual - previous_residual
    numerator = float(np.einsum("fmd,fmd->", previous_residual, change))
    denominator = float(np.einsum("fmd,fmd->", change, change))
    previous_weight = float(manifest["previous_weights_by_block"][block_index])
    if denominator <= 0.0:
        raise ArithmeticError("Phase 7B9m Aitken denominator is not positive")
    unconstrained_weight = -previous_weight * numerator / denominator
    if not np.isfinite(unconstrained_weight) or unconstrained_weight <= 0.0:
        raise ArithmeticError("Phase 7B9m Aitken weight is not positive finite")
    positivity_bound = _positivity_upper_bound(current, new_residual)
    if positivity_bound <= 0.0:
        raise ArithmeticError("Phase 7B9m positivity boundary is not positive")
    if unconstrained_weight < positivity_bound:
        accepted_weight = unconstrained_weight
        accepted_method = "unconstrained vector Aitken"
    else:
        accepted_weight = float(np.nextafter(positivity_bound, 0.0))
        accepted_method = "exact positivity boundary"
    candidate = current + accepted_weight * new_residual
    if not np.all(np.isfinite(candidate)) or np.any(candidate < 0.0):
        raise ArithmeticError("Phase 7B9m candidate left the physical intensity domain")
    mapped_candidate = source_map(candidate)
    candidate_residual = mapped_candidate - candidate
    wall_runtime = time.perf_counter() - started
    if not np.all(np.isfinite(candidate_residual)):
        raise ArithmeticError("Phase 7B9m candidate residual became invalid")
    raw_residual = _relative_update(current, mapped)
    accelerated_residual = _relative_update(candidate, mapped_candidate)
    current_flux = _block_flux(current, mu, weight, frequency_width)
    mapped_flux = _block_flux(mapped, mu, weight, frequency_width)
    candidate_flux = _block_flux(candidate, mu, weight, frequency_width)
    mapped_candidate_flux = _block_flux(
        mapped_candidate, mu, weight, frequency_width
    )
    raw_boundary = _spectral_l1(current_flux, mapped_flux)
    accelerated_boundary = _spectral_l1(candidate_flux, mapped_candidate_flux)
    boundary_ratio = (
        accelerated_boundary / raw_boundary
        if raw_boundary > 0.0
        else (0.0 if accelerated_boundary == 0.0 else math.inf)
    )
    gc.collect()
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    historical = json.loads(
        (
            ROOT
            / protocol["sources"][f"map6_worker_block{block_index:02d}"]["path"]
        ).read_text(encoding="utf-8")
    )
    report = {
        "block_index": block_index,
        "role": selected[block_index],
        "core_group_start": int(block.core_group_start),
        "core_group_stop": int(block.core_group_stop),
        "minimum_energy_ev": float(
            global_edge[block.core_group_start] * 4.135667696e-15
        ),
        "maximum_energy_ev": float(
            global_edge[block.core_group_stop] * 4.135667696e-15
        ),
        "previous_accepted_weight": previous_weight,
        "aitken_numerator": numerator,
        "aitken_denominator": denominator,
        "unconstrained_weight": unconstrained_weight,
        "positivity_upper_bound": positivity_bound,
        "accepted_weight": accepted_weight,
        "accepted_method": accepted_method,
        "minimum_candidate_intensity": float(np.min(candidate)),
        "raw_original_operator_residual": raw_residual,
        "candidate_original_operator_residual": accelerated_residual,
        "candidate_to_raw_residual_ratio": accelerated_residual / raw_residual,
        "raw_boundary_spectrum_l1": raw_boundary,
        "candidate_boundary_spectrum_l1": accelerated_boundary,
        "candidate_to_raw_boundary_ratio": boundary_ratio,
        "wall_runtime_s": wall_runtime,
        "historical_one_update_runtime_s": float(historical["runtime_s"]),
        "runtime_multiplier_over_one_update": float(
            wall_runtime / float(historical["runtime_s"])
        ),
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak_rss / MIB,
    }
    _write_json_atomic(report_path, report)


def _plot(
    path: Path,
    reports: list[dict[str, object]],
    gates: dict[str, object],
    *,
    full_map_authorized: bool,
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(13.0, 8.2), constrained_layout=True)
    block = np.asarray([row["block_index"] for row in reports])
    weight = np.asarray([row["unconstrained_weight"] for row in reports])
    bound = np.asarray([row["positivity_upper_bound"] for row in reports])
    accepted = np.asarray([row["accepted_weight"] for row in reports])
    axes[0, 0].semilogy(block, weight, "o-", label="Unconstrained Aitken")
    finite = np.isfinite(bound)
    axes[0, 0].semilogy(block[finite], bound[finite], "s", label="Positivity bound")
    axes[0, 0].semilogy(block, accepted, "x", ms=8, label="Accepted")
    axes[0, 0].axhline(5.870950407503697, color="0.25", ls="--", label="Old cap")
    axes[0, 0].set(
        xlabel="Natural frequency block",
        ylabel="Mode-extrapolation weight",
        title="(a) Exact block positivity",
    )
    axes[0, 0].legend(frameon=False, fontsize=8)
    residual_ratio = np.asarray(
        [row["candidate_to_raw_residual_ratio"] for row in reports]
    )
    boundary_ratio = np.asarray(
        [row["candidate_to_raw_boundary_ratio"] for row in reports]
    )
    width = 0.36
    axes[0, 1].bar(block - width / 2, residual_ratio, width=width, label="Interior residual")
    axes[0, 1].bar(block + width / 2, boundary_ratio, width=width, label="Boundary spectrum")
    axes[0, 1].axhline(
        gates["each_candidate_original_residual_ratio_below"],
        color="0.25",
        ls="--",
        label="Interior gate",
    )
    axes[0, 1].set(
        xlabel="Natural frequency block",
        ylabel="Candidate / raw residual",
        title="(b) Fresh original-operator check",
    )
    axes[0, 1].legend(frameon=False, fontsize=8)
    runtime = np.asarray(
        [row["runtime_multiplier_over_one_update"] for row in reports]
    )
    axes[1, 0].bar(block, runtime)
    axes[1, 0].axhline(
        gates["selected_runtime_multiplier_over_one_map_below"],
        color="0.25",
        ls="--",
        label="Cost gate",
    )
    axes[1, 0].set(
        xlabel="Natural frequency block",
        ylabel="Runtime / one source update",
        title="(c) Two-map validation cost",
    )
    axes[1, 0].legend(frameon=False)
    axes[1, 1].axis("off")
    axes[1, 1].text(
        0.03,
        0.95,
        "(d) Dominant-mode decision\n\n"
        f"Worst candidate/raw = {float(np.max(residual_ratio)):.3f}\n"
        f"Median candidate/raw = {float(np.median(residual_ratio)):.3f}\n"
        f"Weights above old cap = {int(np.count_nonzero(weight > 5.870950407503697))}\n\n"
        f"Full-frequency map authorized: {full_map_authorized}\n"
        "Material feedback: not evaluated",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=11,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    selected = [
        int(row["block_index"])
        for row in protocol["configuration"]["selected_blocks"]
    ]
    report_paths = [
        OUTPUT / f"phase7b9m_block{index:02d}_exact_positive.json"
        for index in selected
    ]
    concurrency = int(protocol["configuration"]["maximum_concurrent_processes"])
    for offset in range(0, len(selected), concurrency):
        batch = selected[offset : offset + concurrency]
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker",
                    "--protocol",
                    str(protocol_path),
                    "--block-index",
                    str(block_index),
                    "--worker-report",
                    str(report_paths[selected.index(block_index)]),
                ],
                cwd=ROOT,
            )
            for block_index in batch
        ]
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"Phase 7B9m worker failure: {codes}")
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    reports.sort(key=lambda row: int(row["block_index"]))
    gates = protocol["gates"]
    residual_ratio = np.asarray(
        [row["candidate_to_raw_residual_ratio"] for row in reports]
    )
    boundary_ratio = np.asarray(
        [row["candidate_to_raw_boundary_ratio"] for row in reports]
    )
    weights = np.asarray([row["unconstrained_weight"] for row in reports])
    runtime_multiplier = float(
        sum(row["wall_runtime_s"] for row in reports)
        / sum(row["historical_one_update_runtime_s"] for row in reports)
    )
    prior = json.loads(
        (ROOT / protocol["sources"]["phase7b9k_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    projected_wall = float(prior["history"][-1]["wall_runtime_s"]) * runtime_multiplier
    checks = {
        "representative_coverage_complete": len(reports)
        == gates["selected_block_count_exactly"],
        "large_unconstrained_modes_observed": int(
            np.count_nonzero(weights > 5.870950407503697)
        )
        >= gates["raw_unconstrained_weights_above_historical_5p87095_at_least"],
        "every_candidate_original_residual_improves_enough": bool(
            np.all(
                residual_ratio
                < gates["each_candidate_original_residual_ratio_below"]
            )
        ),
        "median_candidate_original_residual_improves_enough": bool(
            np.median(residual_ratio)
            < gates["median_candidate_original_residual_ratio_below"]
        ),
        "worst_map6_block_improves_enough": bool(
            next(
                row["candidate_to_raw_residual_ratio"]
                for row in reports
                if int(row["block_index"]) == 25
            )
            < gates["worst_map6_block25_candidate_residual_ratio_below"]
        ),
        "boundary_residuals_do_not_worsen": bool(
            np.all(
                boundary_ratio
                <= gates["each_candidate_boundary_residual_ratio_at_most"]
            )
        ),
        "candidates_finite_nonnegative_and_within_memory": all(
            row["minimum_candidate_intensity"]
            >= gates["minimum_candidate_intensity_at_least"]
            and row["peak_process_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            for row in reports
        ),
        "selected_runtime_multiplier_passes": runtime_multiplier
        < gates["selected_runtime_multiplier_over_one_map_below"],
        "projected_full_map_cost_passes": projected_wall
        < gates["projected_full_map_wall_time_strictly_below_s"],
    }
    passed = all(checks.values())
    decision = {
        "exact_positive_dominant_mode_pilot_passed": passed,
        "one_full_frequency_exact_positive_mode_map_authorized": passed,
        "bounded_block_aitken_continuation_authorized": False,
        "block_internal_picard_continuation_authorized": False,
        "plain_omega1_resume_authorized": False,
        "full_frequency_accelerated_map_evaluated": False,
        "trial_inner_radiation_converged": False,
        "trial_formal_feedback_evaluated": False,
        "trial_true_residual_evaluated": False,
        "trial_rejected_by_physical_residual": False,
        "accepted_as_dynamic_nlte_solution": False,
        "phase7b9m_gate_passed": passed,
    }
    figure = OUTPUT / "phase7b9m_exact_positive_mode_pilot.png"
    _plot(figure, reports, gates, full_map_authorized=passed)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "reports": reports,
        "unconstrained_weights_above_old_cap": int(
            np.count_nonzero(weights > 5.870950407503697)
        ),
        "maximum_candidate_to_raw_residual_ratio": float(np.max(residual_ratio)),
        "median_candidate_to_raw_residual_ratio": float(np.median(residual_ratio)),
        "maximum_candidate_to_raw_boundary_ratio": float(np.max(boundary_ratio)),
        "selected_runtime_multiplier_over_one_update": runtime_multiplier,
        "projected_full_map_wall_time_s": projected_wall,
        "gate_checks": checks,
        "decision": decision,
        "figures": [figure.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9m_exact_positive_mode_pilot_summary.json", summary
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9m_preregistered_exact_positive_mode_pilot.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.block_index is None or args.worker_report is None:
            raise ValueError("worker mode requires block index and report path")
        _run_worker(args.protocol, args.block_index, args.worker_report)
        return
    summary = run(args.protocol)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
