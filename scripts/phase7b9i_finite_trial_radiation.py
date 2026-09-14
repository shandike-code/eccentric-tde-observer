"""Phase 7B9i：有限准 Newton 物质试步上的可恢复全频辐射收敛。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
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
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b7i_second_radiation_map as phase7b7i  # type: ignore[no-redef]
    import phase7b9d_inner_converged_base_radiation as phase7b9d  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "c42352a5b61e42b6d84026103b56b1d162ac396adf81afd50e3c8c51ab34838c"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if _sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9i radiation protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or _sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(f"frozen Phase 7B9i source changed: {source['path']}")
    return protocol


def _iteration_passes(row: dict[str, object], gates: dict[str, object]) -> bool:
    return bool(
        row["raw_source_map_residual"] < gates["global_source_map_residual_below"]
        and row["boundary_flux_spectrum_l1"]
        < gates["boundary_flux_spectrum_l1_below"]
        and row["boundary_flux_bolometric_fraction"]
        < gates["boundary_flux_bolometric_fraction_below"]
        and row["minimum_mapped_intensity"] >= gates["minimum_intensity_at_least"]
        and row["block_count"] == gates["each_iteration_block_count_exactly"]
        and row["owned_frequency_group_count"]
        == gates["each_iteration_owned_frequency_groups_exactly"]
        and row["ownership_exactly_once"]
        and row["maximum_process_peak_rss_mib"]
        < gates["each_process_peak_rss_strictly_below_mib"]
        and row["wall_runtime_s"]
        < gates["each_iteration_wall_time_strictly_below_s"]
    )


def _consecutive_passes(history: list[dict[str, object]], gates: dict[str, object]) -> int:
    count = 0
    for row in reversed(history):
        if not _iteration_passes(row, gates):
            break
        count += 1
    return count


def run_worker(
    protocol_path: Path,
    current_state: Path,
    block_index: int,
    output_state: Path,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    phase7b9d._configure_worker(protocol, current_state)
    phase7b7i.run_worker(
        protocol_path,
        block_index,
        output_state,
        report_path,
    )


def _new_manifest(
    protocol: dict[str, object], path: Path, shape: tuple[int, int, int]
) -> dict[str, object]:
    configuration = protocol["configuration"]
    expected_size = int(configuration["raw_float64_checkpoint_size_bytes"])
    initial = ROOT / protocol["sources"]["initial_radiation_checkpoint"]["path"]
    if initial.stat().st_size != expected_size:
        raise RuntimeError("Phase 7B9i initial radiation size changed")
    path.parent.mkdir(parents=True, exist_ok=True)
    required = 2 * expected_size + int(
        configuration["minimum_free_bytes_after_allocations"]
    )
    if shutil.disk_usage(path.parent).free <= required:
        raise OSError("insufficient disk space for Phase 7B9i recoverable arrays")
    phase7b9d._ensure_work_arrays(
        ROOT / configuration["work_directory"],
        shape,
        expected_size,
        allow_existing=False,
    )
    manifest = {
        "phase": protocol["phase"],
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "status": "running",
        "current_additional_map": 0,
        "current_state_path": _relative(initial),
        "current_state_sha256": protocol["sources"]["initial_radiation_checkpoint"][
            "sha256"
        ],
        "history": [],
        "uncommitted_iteration": None,
    }
    _write_json_atomic(path, manifest)
    return manifest


def _load_or_create_manifest(
    protocol: dict[str, object], path: Path, shape: tuple[int, int, int]
) -> dict[str, object]:
    manifest = (
        _new_manifest(protocol, path, shape)
        if not path.exists()
        else json.loads(path.read_text(encoding="utf-8"))
    )
    if manifest["protocol_sha256"] != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("Phase 7B9i manifest belongs to another protocol")
    if manifest["status"] not in ("running", "complete", "gate_failed"):
        raise RuntimeError("Phase 7B9i manifest status is invalid")
    expected_size = int(protocol["configuration"]["raw_float64_checkpoint_size_bytes"])
    current = ROOT / manifest["current_state_path"]
    if current.stat().st_size != expected_size or _sha256(current) != manifest[
        "current_state_sha256"
    ]:
        raise RuntimeError("Phase 7B9i committed state changed")
    uncommitted = manifest.get("uncommitted_iteration")
    if uncommitted is not None:
        output = ROOT / uncommitted["output_state_path"]
        if output.stat().st_size != expected_size:
            raise RuntimeError("Phase 7B9i partial output size changed")
        for record in uncommitted["completed_blocks"]:
            digest = phase7b9d._block_sha256(
                output,
                shape,
                int(record["core_group_start"]),
                int(record["core_group_stop"]),
            )
            if digest != record["sha256"]:
                raise RuntimeError(
                    f"Phase 7B9i completed block changed: {record['block_index']}"
                )
    return manifest


def _run_one_iteration(
    protocol: dict[str, object],
    protocol_path: Path,
    manifest_path: Path,
    manifest: dict[str, object],
    shape: tuple[int, int, int],
    frequency_width: np.ndarray,
) -> dict[str, object]:
    configuration = protocol["configuration"]
    next_map = int(manifest["current_additional_map"]) + 1
    work = ROOT / configuration["work_directory"]
    output = work / ("state_a.dat" if next_map % 2 == 1 else "state_b.dat")
    current = ROOT / manifest["current_state_path"]
    uncommitted = manifest.get("uncommitted_iteration")
    if uncommitted is None:
        uncommitted = {
            "additional_map": next_map,
            "current_state_path": _relative(current),
            "current_state_sha256": manifest["current_state_sha256"],
            "output_state_path": _relative(output),
            "completed_blocks": [],
            "accumulated_wall_runtime_s": 0.0,
        }
        manifest["uncommitted_iteration"] = uncommitted
        _write_json_atomic(manifest_path, manifest)
    elif (
        int(uncommitted["additional_map"]) != next_map
        or ROOT / uncommitted["output_state_path"] != output
    ):
        raise RuntimeError("Phase 7B9i uncommitted iteration changed")
    completed = {
        int(row["block_index"]): row for row in uncommitted["completed_blocks"]
    }
    pending = [
        index for index in range(int(configuration["block_count"])) if index not in completed
    ]
    reports = work / "reports"
    reports.mkdir(exist_ok=True)
    concurrency = int(configuration["maximum_concurrent_processes"])
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        started = time.perf_counter()
        processes = []
        report_paths = []
        for block_index in batch:
            report_path = reports / f"map{next_map:02d}_block{block_index:02d}.json"
            report_paths.append(report_path)
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--worker",
                        "--protocol",
                        str(protocol_path),
                        "--current-state",
                        str(current),
                        "--block-index",
                        str(block_index),
                        "--output-state",
                        str(output),
                        "--worker-report",
                        str(report_path),
                    ],
                    cwd=ROOT,
                )
            )
        return_codes = [process.wait() for process in processes]
        if any(code != 0 for code in return_codes):
            raise RuntimeError(f"Phase 7B9i worker batch failed: {return_codes}")
        for block_index, report_path in zip(batch, report_paths, strict=True):
            row = json.loads(report_path.read_text(encoding="utf-8"))
            row["sha256"] = phase7b9d._block_sha256(
                output,
                shape,
                int(row["core_group_start"]),
                int(row["core_group_stop"]),
            )
            uncommitted["completed_blocks"].append(row)
        uncommitted["completed_blocks"].sort(key=lambda row: int(row["block_index"]))
        uncommitted["accumulated_wall_runtime_s"] = float(
            uncommitted["accumulated_wall_runtime_s"]
        ) + (time.perf_counter() - started)
        _write_json_atomic(manifest_path, manifest)
        count = len(uncommitted["completed_blocks"])
        if count % 10 == 0 or count == int(configuration["block_count"]):
            print(
                json.dumps(
                    {"additional_map": next_map, "completed_blocks": count, "total_blocks": 76}
                ),
                flush=True,
            )
    post_started = time.perf_counter()
    records = list(uncommitted["completed_blocks"])
    ownership = np.zeros(shape[0], dtype=np.int64)
    for record in records:
        ownership[
            int(record["core_group_start"]) : int(record["core_group_stop"])
        ] += 1
    maximum_change = max(
        float(record["maximum_absolute_radiation_change"]) for record in records
    )
    maximum_scale = max(float(record["maximum_radiation_scale"]) for record in records)
    raw_residual = maximum_change / maximum_scale if maximum_scale > 0.0 else maximum_change
    spectrum_l1, bolometric, current_flux, next_flux = phase7b9d._boundary_flux_change(
        current, output, shape, frequency_width
    )
    output_sha = _sha256(output)
    row = {
        "additional_map": next_map,
        "total_source_maps_at_current_material": next_map,
        "block_count": len(records),
        "owned_frequency_group_count": int(np.sum(ownership)),
        "ownership_exactly_once": bool(np.all(ownership == 1)),
        "raw_source_map_residual": float(raw_residual),
        "boundary_flux_spectrum_l1": spectrum_l1,
        "boundary_flux_bolometric_fraction": bolometric,
        "boundary_flux_bolometric_current": current_flux,
        "boundary_flux_bolometric_next": next_flux,
        "minimum_mapped_intensity": min(
            float(record["minimum_mapped_intensity"]) for record in records
        ),
        "maximum_internal_energy_ledger_residual": max(
            float(record["internal_total_energy_ledger_residual"])
            for record in records
        ),
        "maximum_process_peak_rss_mib": max(
            float(record["peak_process_rss_mib"]) for record in records
        ),
        "wall_runtime_s": float(uncommitted["accumulated_wall_runtime_s"])
        + (time.perf_counter() - post_started),
        "output_state_path": _relative(output),
        "output_state_sha256": output_sha,
    }
    manifest["current_additional_map"] = next_map
    manifest["current_state_path"] = _relative(output)
    manifest["current_state_sha256"] = output_sha
    manifest["history"].append(row)
    manifest["uncommitted_iteration"] = None
    _write_json_atomic(manifest_path, manifest)
    print(json.dumps({"committed_iteration": row}, indent=2), flush=True)
    return row


def _plot(path: Path, history: list[dict[str, object]], gates: dict[str, object]) -> None:
    maps = np.asarray([row["additional_map"] for row in history])
    figure, axes = plt.subplots(1, 2, figsize=(12.0, 4.6), constrained_layout=True)
    axes[0].semilogy(maps, [row["raw_source_map_residual"] for row in history], "o-")
    axes[0].axhline(
        gates["global_source_map_residual_below"], color="0.25", ls="--", label="Gate"
    )
    axes[0].set(
        xlabel="Source map at finite material trial",
        ylabel="Global-scale radiation change",
        title="(a) Finite-trial radiation convergence",
    )
    axes[0].legend(frameon=False)
    axes[1].semilogy(
        maps,
        [row["boundary_flux_spectrum_l1"] for row in history],
        "o-",
        label="Spectral L1",
    )
    axes[1].semilogy(
        maps,
        [row["boundary_flux_bolometric_fraction"] for row in history],
        "s-",
        label="Bolometric",
    )
    axes[1].axhline(1.0e-3, color="0.25", ls="--", label="Boundary gate")
    axes[1].set(
        xlabel="Source map at finite material trial",
        ylabel="Successive boundary-flux change",
        title="(b) Trial science functionals",
    )
    axes[1].legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    shape = phase7b9d._shape(protocol)
    with np.load(ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]) as master:
        frequency_width = np.diff(np.array(master["active_edge_hz"], copy=True))
    manifest_path = ROOT / configuration["manifest"]
    manifest = _load_or_create_manifest(protocol, manifest_path, shape)
    if manifest["status"] == "complete":
        return json.loads(
            (OUTPUT / "phase7b9i_finite_trial_radiation_summary.json").read_text(
                encoding="utf-8"
            )
        )
    if manifest["status"] == "gate_failed":
        raise RuntimeError("Phase 7B9i exhausted the frozen map budget")
    maximum = int(configuration["maximum_total_additional_maps"])
    while int(manifest["current_additional_map"]) < maximum:
        _run_one_iteration(
            protocol,
            protocol_path,
            manifest_path,
            manifest,
            shape,
            frequency_width,
        )
        consecutive = _consecutive_passes(manifest["history"], gates)
        even = int(manifest["current_additional_map"]) % 2 == 0
        if consecutive >= int(configuration["minimum_consecutive_converged_maps"]) and (
            not configuration["stop_only_after_even_additional_map"] or even
        ):
            break
    history = manifest["history"]
    consecutive = _consecutive_passes(history, gates)
    converged = bool(
        consecutive >= int(configuration["minimum_consecutive_converged_maps"])
        and int(manifest["current_additional_map"]) % 2 == 0
    )
    manifest["status"] = "complete" if converged else "gate_failed"
    _write_json_atomic(manifest_path, manifest)
    final = history[-1]
    previous = history[-2] if len(history) > 1 else None
    figure_path = OUTPUT / "phase7b9i_finite_trial_radiation.png"
    _plot(figure_path, history, gates)
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "final_additional_map": int(manifest["current_additional_map"]),
        "consecutive_converged_maps": consecutive,
        "final_global_source_map_residual": final["raw_source_map_residual"],
        "final_boundary_flux_spectrum_l1": final["boundary_flux_spectrum_l1"],
        "final_boundary_flux_bolometric_fraction": final[
            "boundary_flux_bolometric_fraction"
        ],
        "previous_radiation_path": None if previous is None else previous["output_state_path"],
        "previous_radiation_sha256": None
        if previous is None
        else previous["output_state_sha256"],
        "final_radiation_path": final["output_state_path"],
        "final_radiation_sha256": final["output_state_sha256"],
        "maximum_process_peak_rss_mib": max(
            row["maximum_process_peak_rss_mib"] for row in history
        ),
        "total_wall_runtime_s": float(sum(row["wall_runtime_s"] for row in history)),
        "decision": {
            "frozen_sources_and_trial_material_hash_passed": True,
            "global_source_and_boundary_functionals_converged": converged,
            "two_consecutive_map_gate_passed": consecutive
            >= int(configuration["minimum_consecutive_converged_maps"]),
            "one_map_internal_ledger_used_as_admission_gate": False,
            "trial_formal_feedback_evaluated": False,
            "trial_true_residual_evaluated": False,
            "finite_trial_may_be_called_jv": False,
            "accepted_as_nonlinear_step": False,
            "phase7b9i_radiation_gate_passed": converged,
            "trial_formal_h_he_feedback_authorized": converged,
        },
        "history": history,
        "figures": [figure_path.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9i_finite_trial_radiation_summary.json", report
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9i_preregistered_finite_trial_radiation.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--current-state", type=Path)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if any(
            value is None
            for value in (
                args.current_state,
                args.block_index,
                args.output_state,
                args.worker_report,
            )
        ):
            parser.error("worker mode requires state, block, output, and report")
        run_worker(
            args.protocol,
            args.current_state,
            args.block_index,
            args.output_state,
            args.worker_report,
        )
        return
    print(json.dumps(run(args.protocol), indent=2))


if __name__ == "__main__":
    main()
