"""Phase 7B5z：验证只返回中间源映射、末态诊断延后计算的性能路径。"""

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
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b5x_full_depth_block_probe as phase7b5x  # type: ignore[no-redef]
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "32a819d7dbc6d2b9dce296bca62ed5e250e549b496ff388fe9619ca38c5a7655"
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
        raise RuntimeError(f"frozen Phase 7B5z protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    # ALE 文件是本阶段授权修改的候选；冻结哈希仅描述修改前基线。
    for name, source in protocol["sources"].items():
        if name == "mixed_frame_ale_baseline":
            continue
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B5z source changed: {source['path']}")
    return protocol


def _relative(candidate: float, reference: float) -> float:
    scale = max(abs(candidate), abs(reference))
    return abs(candidate - reference) / scale if scale > 0.0 else abs(candidate - reference)


def run_worker(protocol_path: Path, output_path: Path) -> None:
    protocol = _load_protocol(protocol_path)
    baseline_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    total_started = time.perf_counter()
    context = phase7b5x._context(protocol)
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
    true_absorption = np.repeat(
        parent_microphysics.true_absorption_total_per_cm, 16, axis=1
    )
    thermal_emissivity = np.repeat(
        parent_microphysics.thermal_emissivity_total_cgs, 16, axis=1
    )
    scattering = np.repeat(
        parent_microphysics.electron_scattering_per_cm, 16, axis=1
    )
    parent_outer = phase7b5x._parent_boosted_planck_outer(
        local.outer_lab_edge_hz,
        context["mu"],
        context["weight"],
        context["parent_beta"],
        temperature,
    )
    outer = np.repeat(parent_outer, 16, axis=2)
    active = slice(local.active_outer_group_start, local.active_outer_group_stop)
    initial = np.array(outer[active], copy=True)
    old_edge = phase7b5x._subdivide_column_edge(full["edge_cm"][phase], 16)
    new_edge = phase7b5x._subdivide_column_edge(full["edge_cm"][following], 16)

    operator_started = time.perf_counter()
    result = solve_mixed_frame_ale_group_step(
        local,
        old_edge,
        new_edge,
        context["mu"],
        context["weight"],
        initial,
        outer,
        true_absorption,
        thermal_emissivity,
        scattering,
        context["beta"],
        context["duration_s"],
        propagation_speed_cm_s=LIGHT_SPEED_CM_S,
        source_iteration_initial_guess=initial,
        diagnostic_fixed_iteration_count=1,
        spatial_scheme="hybrid_step_turning_upwind",
        source_map_only=True,
    )
    operator_runtime = time.perf_counter() - operator_started
    peak = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    diagnostics = np.array(
        [result.minimum_intensity, result.final_fixed_point_change]
    )
    report = {
        "pid": os.getpid(),
        "phase_index": phase,
        "core_group_start": block.core_group_start,
        "core_group_stop": block.core_group_stop,
        "radiation_depth_cell_count": context["beta"].size,
        "operator_runtime_s": operator_runtime,
        "total_runtime_s": time.perf_counter() - total_started,
        "baseline_highwater_rss_mib": baseline_rss / MIB,
        "peak_process_rss_mib": peak / MIB,
        "minimum_intensity": result.minimum_intensity,
        "one_iteration_fixed_point_change": result.final_fixed_point_change,
        "one_iteration_fixed_point_converged": result.fixed_point_converged,
        "all_reported_diagnostics_finite": bool(np.all(np.isfinite(diagnostics))),
        "final_intensity_sha256": _sha256_array(
            result.final_lab_intensity_density
        ),
    }
    _write_json_atomic(output_path, report)
    print(json.dumps(report, indent=2), flush=True)


def _plot(path: Path, protocol: dict[str, object], runs: list[dict[str, object]]) -> None:
    baseline = protocol["baseline"]
    median_runtime = float(np.median([run["operator_runtime_s"] for run in runs]))
    maximum_rss = max(run["peak_process_rss_mib"] for run in runs)
    figure, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    axes[0].bar(
        ["Full diagnostics", "Lean map\nmedian"],
        [baseline["operator_runtime_s"], median_runtime],
        color=["#777777", "#4c78a8"],
    )
    axes[0].axhline(
        protocol["gates"]["median_operator_runtime_strictly_below_s"],
        color="#333333",
        linestyle="--",
        label="Gate",
    )
    axes[0].set(ylabel="Operator runtime (s)", title="(a) Diagnostics scheduling")
    axes[0].legend()
    axes[1].bar(
        ["Full diagnostics", "Lean map\nmaximum", "Process gate"],
        [baseline["peak_process_rss_mib"], maximum_rss, 6144.0],
        color=["#777777", "#f58518", "#555555"],
    )
    axes[1].set(ylabel="Peak RSS (MiB)", title="(b) Memory")
    axes[2].bar(
        ["Run 1", "Run 2"],
        [
            float(run["final_intensity_sha256"] == baseline["final_intensity_sha256"])
            for run in runs
        ],
        color="#54a24b",
    )
    axes[2].set(ylim=(0, 1.15), ylabel="Exact hash match", title="(c) Source-map identity")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b5z_preregistered_lean_source_map.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--worker-output", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.worker_output is None:
            raise ValueError("--worker-output is required in worker mode")
        run_worker(args.protocol, args.worker_output)
        return

    protocol = _load_protocol(args.protocol)
    runs = []
    walls = []
    for repeat in range(int(protocol["candidate"]["repeat_count"])):
        output = OUTPUT / f"phase7b5z_repeat{repeat + 1}_worker.json"
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--protocol",
            str(args.protocol),
            "--worker-output",
            str(output),
        ]
        started = time.perf_counter()
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        walls.append(time.perf_counter() - started)
        if completed.returncode != 0:
            raise RuntimeError(
                f"Phase 7B5z repeat {repeat + 1} failed:\n"
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        print(completed.stdout, end="")
        runs.append(json.loads(output.read_text(encoding="utf-8")))

    baseline = protocol["baseline"]
    minimum_errors = [
        _relative(run["minimum_intensity"], baseline["minimum_intensity"])
        for run in runs
    ]
    change_errors = [
        _relative(
            run["one_iteration_fixed_point_change"],
            baseline["one_iteration_fixed_point_change"],
        )
        for run in runs
    ]
    median_operator = float(np.median([run["operator_runtime_s"] for run in runs]))
    gates = protocol["gates"]
    decision = {
        "frozen_protocol_hash_passed": True,
        "retained_source_hashes_passed": True,
        "retained_phase7b5y_failure_passed": bool(
            protocol["retained_failed_candidate"]["phase7b5y_gate_passed"] is False
            and protocol["retained_failed_candidate"]["candidate_accepted"] is False
        ),
        "all_output_hashes_exact": all(
            run["final_intensity_sha256"]
            == gates["each_final_intensity_sha256_exactly"]
            for run in runs
        ),
        "all_scalar_errors_passed": bool(
            max(minimum_errors)
            < gates["each_minimum_intensity_relative_error_strictly_below"]
            and max(change_errors)
            < gates["each_fixed_point_change_relative_error_strictly_below"]
        ),
        "operator_runtime_gate_passed": bool(
            median_operator < gates["median_operator_runtime_strictly_below_s"]
        ),
        "resource_gate_passed": all(
            run["peak_process_rss_mib"] < gates["each_peak_rss_strictly_below_mib"]
            for run in runs
        ),
        "nonnegative_and_finite_passed": all(
            run["minimum_intensity"] >= 0.0
            and run["all_reported_diagnostics_finite"]
            for run in runs
        ),
        "full_column_fixed_point_authorized": False,
        "full_orbit_authorized": False,
        "matter_feedback_authorized": False,
    }
    decision["phase7b5z_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "retained_source_hashes_passed",
            "retained_phase7b5y_failure_passed",
            "all_output_hashes_exact",
            "all_scalar_errors_passed",
            "operator_runtime_gate_passed",
            "resource_gate_passed",
            "nonnegative_and_finite_passed",
        )
    )
    decision["candidate_accepted"] = bool(decision["phase7b5z_gate_passed"])
    decision["streaming_integration_authorized"] = bool(
        decision["phase7b5z_gate_passed"]
    )
    decision["measured_full_frequency_source_iteration_authorized"] = bool(
        decision["phase7b5z_gate_passed"]
    )
    summary = {
        "phase": "7B5z lean single-source-map performance gate",
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "candidate_mixed_frame_ale_sha256": _sha256(
            ROOT / "src/eccentric_tde_observer/mixed_frame_ale.py"
        ),
        "runs": runs,
        "fresh_process_wall_s": walls,
        "minimum_intensity_relative_errors": minimum_errors,
        "fixed_point_change_relative_errors": change_errors,
        "median_operator_runtime_s": median_operator,
        "operator_speedup": baseline["operator_runtime_s"] / median_operator,
        "maximum_peak_rss_mib": max(run["peak_process_rss_mib"] for run in runs),
        "decision": decision,
        "figures": ["phase7b5z_lean_source_map.png"],
    }
    _write_json_atomic(OUTPUT / "phase7b5z_lean_source_map_summary.json", summary)
    _plot(OUTPUT / "phase7b5z_lean_source_map.png", protocol, runs)
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
