"""Phase 7B5w：执行频率切片平移不变的局域交叠积分门。"""

from __future__ import annotations

import argparse
import csv
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

from eccentric_tde_observer.mixed_frame_ale import (
    solve_mixed_frame_ale_group_step,
)
from eccentric_tde_observer.mixed_frame_frequency import (
    _piecewise_constant_overlap_integral_columns,
)
from eccentric_tde_observer.mixed_frame_streaming import (
    plan_mixed_frame_frequency_blocks,
    stream_mixed_frame_ale_source_iteration,
)
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S

try:
    from scripts.phase7b5i_partition_representation_split import ITERATIVE_TOLERANCE
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
    from scripts.phase7b5v_streaming_turning_gate import (
        _diagnostics,
        _formal_context,
        _scale_error,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5i_partition_representation_split import (  # type: ignore[no-redef]
        ITERATIVE_TOLERANCE,
    )
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
    "8bc2abc306eee0797934395d42b4b23a4fa1ff18ac4674acd4b05c79afdec6cb"
)
MIB = 1024**2


def _sha256_file(path: Path) -> str:
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


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256_file(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B5w protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    previous = protocol["sources"]["phase7b5v_summary"]
    if _sha256_file(ROOT / previous["path"]) != previous["sha256"]:
        raise RuntimeError("frozen Phase 7B5v failure record changed")
    if _sha256_file(
        ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]
    ) != protocol["sources"]["phase7b5p_master_input"]["sha256"]:
        raise RuntimeError("frozen master input changed")
    return protocol


def _synthetic_slice_invariance() -> dict[str, object]:
    edge = np.geomspace(1.0, 100.0, 81)
    width = np.diff(edge)
    density = 0.3 + np.arange(80 * 5, dtype=np.float64).reshape(80, 5) / 300.0
    lower = np.geomspace(edge[24], edge[45], 13)[:, None] * np.ones((1, 5))
    upper = np.geomspace(edge[25], edge[48], 13)[:, None] * np.ones((1, 5))
    full = _piecewise_constant_overlap_integral_columns(
        density, edge, width, lower, upper
    )
    start, stop = 20, 52
    local = _piecewise_constant_overlap_integral_columns(
        density[start:stop],
        edge[start : stop + 1],
        width[start:stop],
        lower,
        upper,
    )
    scale = max(float(np.max(np.abs(full))), float(np.max(np.abs(local))))
    difference = float(np.max(np.abs(full - local)))
    return {
        "maximum_relative_error": difference / scale if scale > 0.0 else difference,
        "bitwise_equal": bool(np.array_equal(full, local)),
        "source_group_count_full": 80,
        "source_group_count_local": stop - start,
    }


def _one_iteration_error(input_path: Path) -> float:
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
    reference = solve_mixed_frame_ale_group_step(
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
        source_iteration_initial_guess=initial,
        diagnostic_fixed_iteration_count=1,
        spatial_scheme="step_characteristics",
    )
    blocks = plan_mixed_frame_frequency_blocks(
        stencil, mu, weight, state["beta"], 256
    )
    output = np.empty_like(initial)
    stream_mixed_frame_ale_source_iteration(
        stencil,
        blocks,
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
        initial,
        output,
        propagation_speed_cm_s=LIGHT_SPEED_CM_S,
        spatial_scheme="hybrid_step_turning_upwind",
    )
    scale = max(
        float(np.max(np.abs(output))),
        float(np.max(np.abs(reference.final_lab_intensity_density))),
    )
    difference = float(
        np.max(np.abs(output - reference.final_lab_intensity_density))
    )
    return difference / scale if scale > 0.0 else difference


def run_worker(protocol_path: Path, mode: str, output_dir: Path) -> None:
    protocol = _load_protocol(protocol_path)
    input_path = ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]
    (
        _loaded,
        state,
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        split_mu,
        initial,
        outer,
        continuum,
    ) = _formal_context(input_path)
    baseline = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    iteration_rows = []
    if mode == "monolithic":
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
            iterative_tolerance=ITERATIVE_TOLERANCE,
            iterative_maximum_iterations=8192,
            spatial_scheme="step_characteristics",
        )
        final = np.array(result.final_lab_intensity_density, copy=True)
        iterations = result.fixed_point_iterations
        final_change = result.final_fixed_point_change
        converged = result.fixed_point_converged
        block_count = 1
    else:
        blocks = plan_mixed_frame_frequency_blocks(
            stencil, mu, weight, state["beta"], 256
        )
        current = np.array(initial, copy=True)
        following = np.empty_like(current)
        converged = False
        for iteration in range(1, 8193):
            diagnostic = stream_mixed_frame_ale_source_iteration(
                stencil,
                blocks,
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
                current,
                following,
                propagation_speed_cm_s=LIGHT_SPEED_CM_S,
                spatial_scheme="hybrid_step_turning_upwind",
            )
            iteration_rows.append(
                {
                    "iteration": iteration,
                    "maximum_relative_change": diagnostic.maximum_relative_change,
                }
            )
            current, following = following, current
            if diagnostic.maximum_relative_change <= ITERATIVE_TOLERANCE:
                converged = True
                break
        if not converged:
            raise ArithmeticError("Phase 7B5w streamed fixed point did not converge")
        final = current
        iterations = iteration
        final_change = diagnostic.maximum_relative_change
        block_count = len(blocks)
    runtime = time.perf_counter() - started
    peak = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    scalars, volume_mean = _diagnostics(
        stencil, mu, weight, state["beta"], final, outer, new_edge
    )
    state_path = output_dir / f"phase7b5w_{mode}_state.npz"
    np.savez_compressed(
        state_path,
        final_lab_intensity_density=final,
        volume_mean_comoving_intensity=volume_mean,
        active_edge_hz=stencil.active_lab_edge_hz,
    )
    report = {
        "configuration": mode,
        "pid": os.getpid(),
        "physical_group_count": stencil.physical_group_count,
        "active_edge_sha256": hashlib.sha256(
            np.ascontiguousarray(stencil.active_lab_edge_hz).tobytes()
        ).hexdigest(),
        "angular_direction_count": mu.size,
        "radiation_subcells": np.diff(new_edge).size,
        "angular_split_mu": split_mu,
        "block_count": block_count,
        "fixed_point_iterations": iterations,
        "final_fixed_point_change": final_change,
        "fixed_point_converged": converged,
        "minimum_intensity": float(np.min(final)),
        "runtime_s": runtime,
        "baseline_highwater_rss_mib": baseline / MIB,
        "peak_process_rss_mib": peak / MIB,
        "operator_highwater_increase_mib": max(0, peak - baseline) / MIB,
        "final_intensity_sha256": _sha256_array(final),
        "state_path": str(state_path.relative_to(ROOT)),
        **scalars,
    }
    _write_json_atomic(output_dir / f"phase7b5w_{mode}.json", report)
    if iteration_rows:
        _write_csv(output_dir / "phase7b5w_stream256_iterations.csv", iteration_rows)
    print(json.dumps(report, indent=2), flush=True)


def _plot(path, old_error, one_error, comparison, reports, scalar_history):
    fig, axes = plt.subplots(2, 2, figsize=(12.0, 8.2), constrained_layout=True)
    axes[0, 0].bar(
        ["Phase 7B5v\nprefix sum", "Phase 7B5w\nlocal overlap"],
        [old_error / 1.0e-12, one_error / 1.0e-12],
        color=["C3", "C2"],
    )
    axes[0, 0].axhline(1.0, color="0.25", ls="--", label="Gate")
    axes[0, 0].set_ylabel("One-map error / gate")
    axes[0, 0].set_title("(a) Frequency-slice invariance repair")
    axes[0, 0].legend(frameon=False)

    axes[0, 1].bar(
        ["Intensity max", "Spectrum L1", "Worst scalar"],
        [
            comparison["errors"]["final_lab_intensity_maximum"] / 1.0e-10,
            comparison["errors"]["volume_mean_comoving_spectrum_l1"] / 1.0e-10,
            comparison["maximum_scalar_error"] / 1.0e-10,
        ],
        color=["C0", "C1", "C4"],
    )
    axes[0, 1].axhline(1.0, color="0.25", ls="--")
    axes[0, 1].set_ylabel("Error / pre-registered gate")
    axes[0, 1].set_title("(b) Streamed fixed-point equivalence")

    modes = ("monolithic", "stream256")
    x = np.arange(2)
    width = 0.38
    runtime_bars = axes[1, 0].bar(
        x - width / 2,
        [reports[mode]["runtime_s"] for mode in modes],
        width,
        label="Runtime",
    )
    second = axes[1, 0].twinx()
    rss_bars = second.bar(
        x + width / 2,
        [reports[mode]["peak_process_rss_mib"] for mode in modes],
        width,
        color="C3",
        label="Peak RSS",
    )
    axes[1, 0].set_xticks(x, ["Monolithic", "Stream 256"])
    axes[1, 0].set_ylabel("Runtime (s)")
    second.set_ylabel("Peak RSS (MiB)")
    axes[1, 0].set_title("(c) Recomputed one-cell cost")
    axes[1, 0].legend(
        (runtime_bars[0], rss_bars[0]),
        ("Runtime", "Peak RSS"),
        frameon=False,
    )

    names = list(scalar_history)
    axes[1, 1].bar(
        np.arange(len(names)),
        [scalar_history[name] / 5.0e-9 for name in names],
        color="C5",
    )
    axes[1, 1].axhline(1.0, color="0.25", ls="--")
    axes[1, 1].set_xticks(
        np.arange(len(names)),
        ["Integrated J", "H I", "He I", "He II", "Radiation energy"],
        rotation=20,
        ha="right",
    )
    axes[1, 1].set_ylabel("Change / historical gate")
    axes[1, 1].set_title("(d) New monolithic vs Phase 7B5v")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run(protocol_path: Path, output_dir: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    for mode in ("monolithic", "stream256"):
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--protocol",
            str(protocol_path),
            "--output-dir",
            str(output_dir),
            "--worker",
            mode,
        ]
        completed = subprocess.run(command, cwd=ROOT, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"Phase 7B5w worker failed: {mode}")
    reports = {
        mode: json.loads(
            (output_dir / f"phase7b5w_{mode}.json").read_text(encoding="utf-8")
        )
        for mode in ("monolithic", "stream256")
    }
    states = {}
    spectra = {}
    edge = None
    for mode in reports:
        with np.load(output_dir / f"phase7b5w_{mode}_state.npz") as data:
            states[mode] = np.array(data["final_lab_intensity_density"], copy=True)
            spectra[mode] = np.array(data["volume_mean_comoving_intensity"], copy=True)
            candidate_edge = np.array(data["active_edge_hz"], copy=True)
        if edge is None:
            edge = candidate_edge
        elif not np.array_equal(edge, candidate_edge):
            raise RuntimeError("Phase 7B5w worker edges differ")
    frequency_width = np.diff(edge)
    intensity_scale = max(
        float(np.max(np.abs(states["stream256"]))),
        float(np.max(np.abs(states["monolithic"]))),
    )
    intensity_error = float(
        np.max(np.abs(states["stream256"] - states["monolithic"]))
        / intensity_scale
    )
    spectrum_numerator = float(
        np.sum(
            frequency_width
            * np.abs(spectra["stream256"] - spectra["monolithic"])
        )
    )
    spectrum_scale = max(
        float(np.sum(frequency_width * np.abs(spectra["stream256"]))),
        float(np.sum(frequency_width * np.abs(spectra["monolithic"]))),
    )
    spectrum_error = spectrum_numerator / spectrum_scale
    scalar_names = (
        "frequency_integrated_volume_mean_comoving_intensity",
        "h_i_photoionization_rate_s1",
        "he_i_photoionization_rate_s1",
        "he_ii_photoionization_rate_s1",
        "final_radiation_energy_erg_cm2",
    )
    scalar_errors = {
        name: _scale_error(reports["stream256"][name], reports["monolithic"][name])
        for name in scalar_names
    }
    comparison = {
        "candidate": "stream256",
        "reference": "monolithic",
        "errors": {
            "final_lab_intensity_maximum": intensity_error,
            "volume_mean_comoving_spectrum_l1": spectrum_error,
            **scalar_errors,
        },
        "maximum_scalar_error": max(scalar_errors.values()),
    }
    comparison["maximum_error"] = max(comparison["errors"].values())
    comparison["worst_observable"] = max(
        comparison["errors"], key=comparison["errors"].get
    )
    previous = json.loads(
        (ROOT / protocol["sources"]["phase7b5v_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    previous_monolithic = previous["runs"]["monolithic"]
    historical_errors = {
        name: _scale_error(reports["monolithic"][name], previous_monolithic[name])
        for name in scalar_names
    }
    input_path = ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]
    one_error = _one_iteration_error(input_path)
    synthetic = _synthetic_slice_invariance()
    old_error = previous["one_iteration_streaming_control"][
        "maximum_relative_intensity_error"
    ]
    _plot(
        output_dir / "phase7b5w_translation_invariant_remap_gate.png",
        old_error,
        one_error,
        comparison,
        reports,
        historical_errors,
    )
    gates = protocol["gates"]
    decision = {
        "frozen_protocol_hash_passed": True,
        "retained_phase7b5v_failure_hash_passed": True,
        "synthetic_slice_invariance_passed": synthetic["maximum_relative_error"]
        < gates["synthetic_slice_invariance_strictly_below"],
        "actual_one_iteration_equivalence_passed": one_error
        < gates["actual_one_iteration_stream_vs_monolithic_strictly_below"],
        "all_fixed_points_converged": all(
            report["fixed_point_converged"] for report in reports.values()
        ),
        "all_fixed_point_changes_passed": all(
            report["final_fixed_point_change"]
            <= gates["actual_fixed_point_tolerance"]
            for report in reports.values()
        ),
        "fixed_point_intensity_equivalence_passed": intensity_error
        < gates["actual_fixed_point_intensity_error_strictly_below"],
        "fixed_point_spectrum_equivalence_passed": spectrum_error
        < gates["actual_fixed_point_spectrum_l1_strictly_below"],
        "fixed_point_scalar_equivalence_passed": max(scalar_errors.values())
        < gates["actual_scalar_error_strictly_below"],
        "historical_monolithic_science_unchanged": max(historical_errors.values())
        < gates["new_monolithic_vs_phase7b5v_scalar_error_strictly_below"],
        "resource_gate_passed": all(
            report["peak_process_rss_mib"]
            < gates["worker_peak_rss_strictly_below_mib"]
            for report in reports.values()
        ),
        "all_intensities_nonnegative": all(
            report["minimum_intensity"] >= gates["minimum_intensity_at_least"]
            for report in reports.values()
        ),
        "physical_group_count_exact": all(
            report["physical_group_count"]
            == gates["physical_group_count_exactly"]
            for report in reports.values()
        ),
        "active_edge_hash_unchanged": len(
            {report["active_edge_sha256"] for report in reports.values()}
        )
        == 1,
    }
    decision["phase7b5w_gate_passed"] = bool(all(decision.values()))
    decision["full_depth_block_resource_probe_authorized"] = decision[
        "phase7b5w_gate_passed"
    ]
    decision["full_orbit_authorized"] = False
    decision["matter_feedback_authorized"] = False
    decision["phase4_replacement_authorized"] = False
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_path": str(protocol_path),
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "candidate_source_hashes": {
            "mixed_frame_frequency": _sha256_file(
                ROOT / "src/eccentric_tde_observer/mixed_frame_frequency.py"
            ),
            "mixed_frame_streaming": _sha256_file(
                ROOT / "src/eccentric_tde_observer/mixed_frame_streaming.py"
            ),
            "mixed_frame_ale": _sha256_file(
                ROOT / "src/eccentric_tde_observer/mixed_frame_ale.py"
            ),
        },
        "retained_phase7b5v_one_iteration_error": old_error,
        "synthetic_slice_invariance": synthetic,
        "actual_one_iteration_error": one_error,
        "runs": reports,
        "streamed_fixed_point_comparison": comparison,
        "new_monolithic_vs_phase7b5v_scalar_errors": historical_errors,
        "decision": decision,
        "accepted_for_next_resource_probe": {
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 256,
            "frequency_integral": "translation-invariant local overlap",
            "spatial_scheme": "hybrid_step_turning_upwind",
        }
        if decision["phase7b5w_gate_passed"]
        else None,
        "figures": ["phase7b5w_translation_invariant_remap_gate.png"],
    }
    _write_json_atomic(
        output_dir / "phase7b5w_translation_invariant_remap_summary.json",
        summary,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b5w_preregistered_translation_invariant_remap.json",
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--worker", choices=("monolithic", "stream256"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.worker is not None:
        run_worker(args.protocol, args.worker, args.output_dir)
        return
    summary_path = (
        args.output_dir / "phase7b5w_translation_invariant_remap_summary.json"
    )
    if summary_path.exists() and not args.force:
        raise FileExistsError(f"refusing to overwrite {summary_path}; pass --force")
    summary = run(args.protocol, args.output_dir)
    print(json.dumps(summary["decision"], indent=2), flush=True)


if __name__ == "__main__":
    main()
