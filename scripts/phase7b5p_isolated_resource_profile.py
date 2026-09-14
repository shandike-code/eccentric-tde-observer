"""Phase 7B5p：隔离进程测量冻结 4816/9632 单单元资源。"""

from __future__ import annotations

import argparse
import csv
from dataclasses import fields
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

try:
    import resource
except ModuleNotFoundError:  # Windows 不提供 POSIX ru_maxrss；仅延迟到实际探针时报错。
    resource = None  # type: ignore[assignment]

import numpy as np

from eccentric_tde_observer.goal_oriented_frequency import (
    hydrogen_photoionization_monitor_group_grid,
)
from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil,
    mixed_frame_frequency_stencil_from_active_edges,
)
from eccentric_tde_observer.multiresolution_frequency import (
    nested_log_frequency_hierarchy,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
)

try:
    from scripts.phase7b5a_log_frequency_p1_gate import (
        CONTROL_ANGULAR_ORDER,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _load_material_reference,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from scripts.phase7b5c_signed_rate_error_localization import (
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
    )
    from scripts.phase7b5i_partition_representation_split import (
        _one_p0_map,
        _project_p0_state,
    )
    from scripts.phase7b5k_high_resolution_convergence import (
        _returned_array_bytes,
    )
    from scripts.phase7b5m_actual_multiresolution_validation import (
        _case_context,
        _edge_sha256,
    )
    from scripts.phase7b5o_initial_converged_validation import (
        _capture_initial_and_converged_states,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5a_log_frequency_p1_gate import (  # type: ignore[no-redef]
        CONTROL_ANGULAR_ORDER,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _load_material_reference,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from phase7b5c_signed_rate_error_localization import (  # type: ignore[no-redef]
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
    )
    from phase7b5i_partition_representation_split import (  # type: ignore[no-redef]
        _one_p0_map,
        _project_p0_state,
    )
    from phase7b5k_high_resolution_convergence import (  # type: ignore[no-redef]
        _returned_array_bytes,
    )
    from phase7b5m_actual_multiresolution_validation import (  # type: ignore[no-redef]
        _case_context,
        _edge_sha256,
    )
    from phase7b5o_initial_converged_validation import (  # type: ignore[no-redef]
        _capture_initial_and_converged_states,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "3ccb468e24def10262489a2c02d8124a103ec1fd2aeae035b4b05e7cb164201c"
)
MIB_BYTES = 1024**2


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError("refusing to write an empty resource table")
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def ru_maxrss_to_bytes(value: int | float, platform: str) -> int:
    """macOS 报 byte，Linux/BSD Python 报 KiB；不猜测未知平台。"""
    if platform == "darwin":
        return int(value)
    if platform.startswith("linux") or "bsd" in platform:
        return int(value) * 1024
    raise RuntimeError(f"unsupported ru_maxrss unit convention: {platform}")


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256_file(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B5p protocol changed: {digest}")
    protocol = json.loads(path.read_text())
    for source in protocol["sources"].values():
        source_path = ROOT / source["path"]
        if _sha256_file(source_path) != source["sha256"]:
            raise RuntimeError(f"frozen source changed: {source_path}")
    return protocol


def _candidate_edges_from_choices(hierarchy, choices_path: Path) -> np.ndarray:
    with choices_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != hierarchy.base_edge_hz.size - 1:
        raise RuntimeError("parent-choice row count does not match hierarchy")
    edges = [float(hierarchy.master_edge_hz[0])]
    for expected_parent, row in enumerate(rows):
        parent = int(row["base_parent_index"])
        leaves = int(row["selected_leaf_count"])
        if parent != expected_parent or leaves not in {1, 2, 4}:
            raise RuntimeError("invalid frozen parent choice")
        start = 4 * parent
        stride = 4 // leaves
        selected = hierarchy.master_edge_hz[
            start + stride : start + 4 + 1 : stride
        ]
        if selected.size != leaves:
            raise RuntimeError("hierarchy leaf reconstruction failed")
        edges.extend(float(value) for value in selected)
    candidate = np.asarray(edges, dtype=float)
    if candidate.size - 1 != 4816 or np.any(np.diff(candidate) <= 0.0):
        raise RuntimeError("frozen candidate edge ledger failed")
    return candidate


def _save_worker_input(
    path: Path,
    *,
    active_edge_hz: np.ndarray,
    maximum_beta: float,
    old_edge: np.ndarray,
    new_edge: np.ndarray,
    mu: np.ndarray,
    weight: np.ndarray,
    state: dict[str, object],
    source_guess: np.ndarray,
) -> None:
    np.savez_compressed(
        path,
        active_edge_hz=active_edge_hz,
        maximum_beta=np.asarray(maximum_beta),
        old_edge=old_edge,
        new_edge=new_edge,
        mu=mu,
        weight=weight,
        beta=state["beta"],
        temperature_k=np.asarray(state["temperature_k"]),
        density_g_cm3=np.asarray(state["density_g_cm3"]),
        hydrogen_fraction=state["hydrogen_fraction"],
        helium_fraction=state["helium_fraction"],
        duration_s=np.asarray(state["duration_s"]),
        source_guess=source_guess,
    )


def _result_sha256(result) -> str:
    digest = hashlib.sha256()
    for field in fields(result):
        value = getattr(result, field.name)
        digest.update(field.name.encode())
        if isinstance(value, np.ndarray):
            digest.update(str(value.shape).encode())
            digest.update(value.dtype.str.encode())
            digest.update(memoryview(np.ascontiguousarray(value)).cast("B"))
        else:
            digest.update(repr(value).encode())
    return digest.hexdigest()


def run_worker(input_path: Path, output_path: Path) -> None:
    if resource is None:
        raise RuntimeError(
            "Phase 7B5p isolated RSS probe requires the POSIX resource module"
        )
    with np.load(input_path) as payload:
        active_edge = np.array(payload["active_edge_hz"], copy=True)
        stencil = mixed_frame_frequency_stencil_from_active_edges(
            active_edge, float(payload["maximum_beta"])
        )
        old_edge = np.array(payload["old_edge"], copy=True)
        new_edge = np.array(payload["new_edge"], copy=True)
        mu = np.array(payload["mu"], copy=True)
        weight = np.array(payload["weight"], copy=True)
        state = {
            "beta": np.array(payload["beta"], copy=True),
            "temperature_k": float(payload["temperature_k"]),
            "density_g_cm3": float(payload["density_g_cm3"]),
            "hydrogen_fraction": np.array(
                payload["hydrogen_fraction"], copy=True
            ),
            "helium_fraction": np.array(
                payload["helium_fraction"], copy=True
            ),
            "duration_s": float(payload["duration_s"]),
        }
        source_guess = np.array(payload["source_guess"], copy=True)
    baseline = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    result = _one_p0_map(
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        state,
        source_guess,
    )
    operator_runtime = time.perf_counter() - started
    peak = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "pid": os.getpid(),
        "platform": sys.platform,
        "physical_group_count": stencil.physical_group_count,
        "active_edge_sha256": _edge_sha256(active_edge),
        "operator_runtime_s": operator_runtime,
        "baseline_highwater_rss_bytes": baseline,
        "peak_process_rss_bytes": peak,
        "operator_highwater_increase_bytes": max(0, peak - baseline),
        "returned_array_bytes": _returned_array_bytes(result),
        "fixed_point_iterations": result.fixed_point_iterations,
        "global_coupled_residual": (
            result.global_scale_normalized_coupled_residual
        ),
        "total_energy_ledger_residual": (
            result.total_relative_energy_ledger_residual
        ),
        "minimum_intensity": result.minimum_intensity,
        "result_sha256": _result_sha256(result),
    }
    _write_json_atomic(output_path, report)


def _prepare_inputs(protocol: dict[str, object], output_dir: Path):
    zo_protocol = json.loads(
        (ROOT / protocol["sources"]["phase7b5o_protocol"]["path"]).read_text()
    )
    material_path = ROOT / zo_protocol["material_reference"]["path"]
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    audit = _trajectory_velocity_audit(material, full)
    maximum_beta = float(audit["maximum_velocity_beta"])
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    reference_stencil = mixed_frame_frequency_stencil(
        *PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        maximum_beta,
    )
    base = hydrogen_photoionization_monitor_group_grid(
        *PHYSICAL_ENERGY_RANGE_EV,
        FAILED_PHYSICAL_GROUPS,
        FAILED_FOCUS_FRACTION,
    )
    hierarchy = nested_log_frequency_hierarchy(base.group_edge_hz)
    candidate_edge = _candidate_edges_from_choices(
        hierarchy,
        ROOT / protocol["sources"]["phase7b5o_parent_choices"]["path"],
    )
    expected_candidate_hash = protocol["representations"][0][
        "active_edge_sha256"
    ]
    if _edge_sha256(candidate_edge) != expected_candidate_hash:
        raise RuntimeError("reconstructed candidate edge hash changed")
    definition = next(
        definition
        for definition in zo_protocol["validation"]["cases"]
        if definition["case"] == protocol["stress_state"]["case"]
    )
    source_states, _, reference_control = _capture_initial_and_converged_states(
        material, full, audit, definition
    )
    reference_source = source_states[protocol["stress_state"]["source_state_label"]]
    state, old_edge, new_edge = _case_context(material, full, definition)
    representations = {
        "candidate": candidate_edge,
        "master": hierarchy.master_edge_hz,
    }
    prepared: dict[str, Path] = {}
    projection_errors: dict[str, float] = {}
    for key, edge in representations.items():
        source, projection_error = _project_p0_state(
            reference_stencil.active_lab_edge_hz, edge, reference_source
        )
        path = output_dir / f"phase7b5p_{key}_worker_input.npz"
        _save_worker_input(
            path,
            active_edge_hz=edge,
            maximum_beta=maximum_beta,
            old_edge=old_edge,
            new_edge=new_edge,
            mu=mu,
            weight=weight,
            state=state,
            source_guess=source,
        )
        prepared[key] = path
        projection_errors[key] = projection_error
    return prepared, projection_errors, reference_control


def _aggregate(rows: list[dict[str, object]], key: str) -> dict[str, object]:
    selected = [row for row in rows if row["representation_key"] == key]
    peak = np.asarray([row["peak_process_rss_mib"] for row in selected])
    increase = np.asarray(
        [row["operator_highwater_increase_mib"] for row in selected]
    )
    operator = np.asarray([row["operator_runtime_s"] for row in selected])
    process = np.asarray([row["fresh_process_wall_s"] for row in selected])
    return {
        "repeat_count": len(selected),
        "median_peak_process_rss_mib": float(np.median(peak)),
        "maximum_peak_process_rss_mib": float(np.max(peak)),
        "median_operator_highwater_increase_mib": float(np.median(increase)),
        "maximum_operator_highwater_increase_mib": float(np.max(increase)),
        "median_operator_runtime_s": float(np.median(operator)),
        "median_fresh_process_wall_s": float(np.median(process)),
        "returned_array_mib": float(selected[0]["returned_array_mib"]),
        "active_edge_sha256": selected[0]["active_edge_sha256"],
        "result_sha256": selected[0]["result_sha256"],
    }


def _plot(path: Path, rows: list[dict[str, object]]) -> None:
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(
        1, 2, figsize=(9.4, 4.0), layout="constrained"
    )
    labels = ("4816 candidate", "9632 master")
    colors = ("tab:blue", "tab:orange")
    for index, key in enumerate(("candidate", "master")):
        selected = [row for row in rows if row["representation_key"] == key]
        x = np.full(len(selected), index, dtype=float)
        axes[0].scatter(
            x,
            [row["peak_process_rss_mib"] for row in selected],
            color=colors[index],
        )
        axes[1].scatter(
            x,
            [row["operator_runtime_s"] for row in selected],
            color=colors[index],
        )
    axes[0].set_ylabel("Fresh-process peak RSS (MiB)")
    axes[1].set_ylabel("One-step operator time (s)")
    for axis in axes:
        axis.set_xticks((0, 1), labels)
        axis.grid(alpha=0.25, axis="y")
    axes[0].set_title("Isolated memory high-water")
    axes[1].set_title("Isolated one-cell runtime")
    figure.savefig(path, dpi=220)
    plt.close(figure)


def run_all(output_dir: Path, protocol_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5p_resource_profile_summary.json",
        "rows": output_dir / "phase7b5p_isolated_resource_runs.csv",
        "figure": output_dir / "phase7b5p_isolated_resource_profile.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    protocol = _load_protocol(protocol_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    prepared, projection_errors, reference_control = _prepare_inputs(
        protocol, output_dir
    )
    rows: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="phase7b5p-") as temporary:
        temporary_path = Path(temporary)
        for run_index, key in enumerate(
            protocol["measurement"]["worker_order"]
        ):
            worker_output = temporary_path / f"worker_{run_index}.json"
            started = time.perf_counter()
            process = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker-input",
                    str(prepared[key]),
                    "--worker-output",
                    str(worker_output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            process_wall = time.perf_counter() - started
            if process.returncode != 0:
                raise RuntimeError(
                    f"resource worker failed: {process.stderr.strip()}"
                )
            worker = json.loads(worker_output.read_text())
            rows.append(
                {
                    "run_index": run_index,
                    "representation_key": key,
                    "worker_pid": worker["pid"],
                    "physical_group_count": worker["physical_group_count"],
                    "active_edge_sha256": worker["active_edge_sha256"],
                    "operator_runtime_s": worker["operator_runtime_s"],
                    "fresh_process_wall_s": process_wall,
                    "baseline_highwater_rss_mib": (
                        worker["baseline_highwater_rss_bytes"] / MIB_BYTES
                    ),
                    "peak_process_rss_mib": (
                        worker["peak_process_rss_bytes"] / MIB_BYTES
                    ),
                    "operator_highwater_increase_mib": (
                        worker["operator_highwater_increase_bytes"] / MIB_BYTES
                    ),
                    "returned_array_mib": (
                        worker["returned_array_bytes"] / MIB_BYTES
                    ),
                    "fixed_point_iterations": worker[
                        "fixed_point_iterations"
                    ],
                    "global_coupled_residual": worker[
                        "global_coupled_residual"
                    ],
                    "total_energy_ledger_residual": worker[
                        "total_energy_ledger_residual"
                    ],
                    "minimum_intensity": worker["minimum_intensity"],
                    "result_sha256": worker["result_sha256"],
                }
            )
    candidate = _aggregate(rows, "candidate")
    master = _aggregate(rows, "master")
    summary_7b5o = json.loads(
        (ROOT / protocol["sources"]["phase7b5o_summary"]["path"]).read_text()
    )
    expected_bytes = {
        "candidate": round(
            summary_7b5o["aggregate"][
                "candidate_returned_array_footprint_mib"
            ]
            * MIB_BYTES
        ),
        "master": round(
            summary_7b5o["aggregate"]["master_returned_array_footprint_mib"]
            * MIB_BYTES
        ),
    }
    pids = [row["worker_pid"] for row in rows]
    hashes = {
        key: {
            row["result_sha256"]
            for row in rows
            if row["representation_key"] == key
        }
        for key in ("candidate", "master")
    }
    decision = {
        "frozen_protocol_hash_passed": True,
        "frozen_source_hashes_passed": True,
        "candidate_edge_hash_unchanged": (
            candidate["active_edge_sha256"]
            == protocol["representations"][0]["active_edge_sha256"]
        ),
        "all_workers_exit_zero": len(rows)
        == len(protocol["measurement"]["worker_order"]),
        "fresh_worker_pid_each_run": len(set(pids)) == len(pids),
        "deterministic_result_hash_within_representation": all(
            len(value) == 1 for value in hashes.values()
        ),
        "returned_array_bytes_match_phase7b5o": all(
            all(
                round(float(row["returned_array_mib"]) * MIB_BYTES)
                == expected_bytes[key]
                for row in rows
                if row["representation_key"] == key
            )
            for key in ("candidate", "master")
        ),
        "frequency_budget_changed": False,
        "angle_or_radiation_subgrid_gate_authorized": False,
        "full_orbit_authorized": False,
        "matter_feedback_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }
    if not all(
        decision[key]
        for key in (
            "frozen_protocol_hash_passed",
            "frozen_source_hashes_passed",
            "candidate_edge_hash_unchanged",
            "all_workers_exit_zero",
            "fresh_worker_pid_each_run",
            "deterministic_result_hash_within_representation",
            "returned_array_bytes_match_phase7b5o",
        )
    ):
        raise RuntimeError("Phase 7B5p resource integrity gate failed")
    aggregate = {
        "candidate": candidate,
        "master": master,
        "master_to_candidate_median_peak_rss_ratio": (
            master["median_peak_process_rss_mib"]
            / candidate["median_peak_process_rss_mib"]
        ),
        "master_to_candidate_maximum_peak_rss_ratio": (
            master["maximum_peak_process_rss_mib"]
            / candidate["maximum_peak_process_rss_mib"]
        ),
        "master_to_candidate_median_operator_highwater_increase_ratio": (
            master["median_operator_highwater_increase_mib"]
            / candidate["median_operator_highwater_increase_mib"]
        ),
        "master_to_candidate_maximum_operator_highwater_increase_ratio": (
            master["maximum_operator_highwater_increase_mib"]
            / candidate["maximum_operator_highwater_increase_mib"]
        ),
        "master_to_candidate_median_operator_runtime_ratio": (
            master["median_operator_runtime_s"]
            / candidate["median_operator_runtime_s"]
        ),
        "master_to_candidate_returned_array_ratio": (
            master["returned_array_mib"] / candidate["returned_array_mib"]
        ),
    }
    report = {
        "phase": "7B5p isolated-process resource profile",
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_path": str(protocol_path),
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "platform": sys.platform,
        "stress_state": protocol["stress_state"],
        "reference_source_control": reference_control,
        "projection_energy_errors": projection_errors,
        "prepared_inputs": {
            key: {
                "path": str(path),
                "sha256": _sha256_file(path),
                "file_size_bytes": path.stat().st_size,
            }
            for key, path in prepared.items()
        },
        "runs": rows,
        "aggregate": aggregate,
        "decision": decision,
        "interpretation": (
            "Fresh-process peak RSS includes Python, imported numerical modules, "
            "the prepared one-cell input, and the one-step result. It is a measured "
            "single-cell high-water mark, not a full-column peak-memory prediction. "
            "The timed operation is exactly one diagnostic fixed-point map, matching "
            "the Phase 7B5o resource accounting; its one-step residual is not a "
            "convergence gate, while the input source comes from a separately "
            "converged reference solve. "
            "The audit informs but does not change the 4816/9632 budget decision and "
            "does not authorize angle, radiation-subgrid, orbit, feedback, Phase 4, "
            "or UVOT work."
        ),
        "figure": paths["figure"].name,
    }
    _write_csv(paths["rows"], rows)
    _plot(paths["figure"], rows)
    _write_json_atomic(paths["summary"], report)
    print(json.dumps({"aggregate": aggregate, "decision": decision}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b5p_preregistered_resource_protocol.json",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--worker-input", type=Path)
    parser.add_argument("--worker-output", type=Path)
    args = parser.parse_args()
    if args.worker_input is not None or args.worker_output is not None:
        if args.worker_input is None or args.worker_output is None:
            raise ValueError("worker input and output must be provided together")
        run_worker(args.worker_input, args.worker_output)
        return
    run_all(args.output_dir, args.protocol, force=args.force)


if __name__ == "__main__":
    main()
