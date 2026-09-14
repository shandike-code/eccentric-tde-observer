"""Phase 7B8e：回溽物质态上的一次全频辐射验证映射。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from scripts import phase7b8b_secant_radiation_map as phase7b8b
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b8b_secant_radiation_map as phase7b8b  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
CHECKPOINT = OUTPUT / "checkpoints"
EXPECTED_PROTOCOL_SHA256 = (
    "deec904004113072698dba71651762c778a5c685a2cce3ca48cdd85540ae7934"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B8e protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            if _sha256(ROOT / source["path"]) != source["sha256"]:
                raise RuntimeError(f"frozen Phase 7B8e source changed: {source['path']}")
    return protocol


def _shape(protocol: dict[str, object]) -> tuple[int, int, int]:
    configuration = protocol["configuration"]
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _full_material(protocol: dict[str, object]) -> dict[str, np.ndarray]:
    with np.load(ROOT / protocol["sources"]["accelerated_material_trial"]["path"]) as state:
        density_half = np.array(state["density_g_cm3"], copy=True)
        temperature_half = np.array(state["temperature_k"], copy=True)
        hydrogen_half = np.array(state["hydrogen_fraction"], copy=True)
        helium_half = np.array(state["helium_fraction"], copy=True)

    def mirror(value: np.ndarray) -> np.ndarray:
        return np.concatenate((value, value[::-1]), axis=0)

    return {
        "density_parent": mirror(density_half),
        "temperature_parent": mirror(temperature_half),
        "hydrogen_parent": mirror(hydrogen_half),
        "helium_parent": mirror(helium_half),
    }


def _configure_reused_worker() -> None:
    # 中文：复用已验证的单块输运实现，仅替换冻结协议和物质态读取器。
    phase7b8b._load_protocol = _load_protocol
    phase7b8b._shape = _shape
    phase7b8b._accelerated_full_material = _full_material


def _plot(path: Path, reports: list[dict[str, object]], raw_residual: float, wall_runtime: float) -> None:
    block = np.array([int(row["block_index"]) for row in reports])
    global_scale = max(float(row["maximum_radiation_scale"]) for row in reports)
    raw = np.array([float(row["maximum_absolute_radiation_change"]) for row in reports]) / global_scale
    rss = np.array([float(row["peak_process_rss_mib"]) for row in reports])
    runtime = np.array([float(row["runtime_s"]) for row in reports])
    figure, axes = plt.subplots(1, 3, figsize=(13.0, 4.0), constrained_layout=True)
    gate = 0.1
    axes[0].plot(block, raw / gate, marker="o", ms=3, lw=1)
    axes[0].set_yscale("symlog", linthresh=1.0e-8)
    axes[0].set_ylim(0.0, 1.5)
    axes[0].axhline(1.0, color="0.25", ls="--", label="Trust gate")
    axes[0].set(
        xlabel="Frequency block index",
        ylabel="Fraction of radiation trust gate",
        title="(a) Backtracked-trial radiation direction",
    )
    axes[0].legend(frameon=False)
    scatter = axes[1].scatter(block, rss, c=runtime, cmap="viridis", s=34)
    axes[1].axhline(6144.0, color="0.25", ls="--", label="RSS gate")
    axes[1].set(
        xlabel="Frequency block index",
        ylabel="Peak process RSS (MiB)",
        title="(b) Short-lived worker resources",
    )
    axes[1].legend(frameon=False)
    figure.colorbar(scatter, ax=axes[1], label="Block runtime (s)")
    axes[2].axis("off")
    axes[2].text(
        0.05,
        0.88,
        "(c) Validation scope\n\n"
        f"Global raw residual = {raw_residual:.3e}\n"
        f"Minimum mapped intensity = {min(float(row['minimum_mapped_intensity']) for row in reports):.3e}\n"
        f"Maximum process RSS = {float(np.max(rss)):.1f} MiB\n"
        f"Total wall time = {wall_runtime:.1f} s\n\n"
        "Assembled physical feedback: deferred\n"
        "True residual improvement: not claimed",
        transform=axes[2].transAxes,
        va="top",
        fontsize=11,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    shape = _shape(protocol)
    initial_path = ROOT / protocol["sources"]["initial_radiation_state"]["path"]
    expected_size = int(np.prod(shape, dtype=np.int64) * 8)
    if initial_path.stat().st_size != expected_size:
        raise RuntimeError("Phase 7B8e initial radiation state size changed")
    block_count = int(configuration["block_count"])
    CHECKPOINT.mkdir(parents=True, exist_ok=True)
    output_path = CHECKPOINT / "phase7b8e_backtracked_radiation_map.dat"
    report_paths = [OUTPUT / f"phase7b8e_block{index:02d}.json" for index in range(block_count)]
    output = np.memmap(output_path, mode="w+", dtype=np.float64, shape=shape)
    output[:] = 0.0
    output.flush()
    del output
    started = time.perf_counter()
    concurrency = int(configuration["maximum_concurrent_processes"])
    for offset in range(0, block_count, concurrency):
        batch = range(offset, min(offset + concurrency, block_count))
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
                    "--output-state",
                    str(output_path),
                    "--worker-report",
                    str(report_paths[block_index]),
                ],
                cwd=ROOT,
            )
            for block_index in batch
        ]
        return_codes = [process.wait() for process in processes]
        if any(code != 0 for code in return_codes):
            raise RuntimeError(f"Phase 7B8e worker batch failed: {return_codes}")
        completed = offset + len(return_codes)
        if completed % 10 == 0 or completed == block_count:
            print(json.dumps({"completed_blocks": completed, "total_blocks": block_count}), flush=True)
    wall_runtime = time.perf_counter() - started
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    reports.sort(key=lambda row: int(row["block_index"]))
    ownership = np.zeros(shape[0], dtype=np.int64)
    for report in reports:
        ownership[int(report["core_group_start"]):int(report["core_group_stop"])] += 1
    maximum_change = max(float(row["maximum_absolute_radiation_change"]) for row in reports)
    maximum_scale = max(float(row["maximum_radiation_scale"]) for row in reports)
    raw_residual = maximum_change / maximum_scale if maximum_scale > 0.0 else maximum_change
    numeric_values = [
        float(value)
        for report in reports
        for key, value in report.items()
        if key not in {"block_index", "core_group_start", "core_group_stop"}
    ]
    rss = [float(row["peak_process_rss_mib"]) for row in reports]
    gates = protocol["gates"]
    decision = {
        "frozen_protocol_and_source_hashes_passed": True,
        "block_and_frequency_ownership_passed": bool(
            len(reports) == gates["block_count_exactly"]
            and int(np.sum(ownership)) == gates["owned_frequency_group_count_exactly"]
            and np.all(ownership == 1)
        ),
        "mapped_state_valid": bool(
            min(float(row["minimum_mapped_intensity"]) for row in reports)
            >= gates["minimum_mapped_intensity_at_least"]
            and min(float(row["minimum_local_comoving_mean_intensity"]) for row in reports)
            >= gates["minimum_mapped_intensity_at_least"]
            and np.all(np.isfinite(numeric_values))
        ),
        "radiation_direction_trust_passed": bool(
            raw_residual < gates["one_map_raw_radiation_residual_below"]
        ),
        "resource_and_runtime_gates_passed": bool(
            all(value < gates["each_process_peak_rss_strictly_below_mib"] for value in rss)
            and wall_runtime < gates["total_wall_time_strictly_below_s"]
        ),
        "assembled_feedback_evaluated": False,
        "true_residual_improvement_claimed": False,
        "accepted_as_radiation_or_coupled_fixed_point": False,
        "another_material_update_authorized": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b8e_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_and_source_hashes_passed",
            "block_and_frequency_ownership_passed",
            "mapped_state_valid",
            "radiation_direction_trust_passed",
            "resource_and_runtime_gates_passed",
        )
    )
    decision["assembled_feedback_and_true_residual_diagnosis_authorized"] = bool(
        decision["phase7b8e_gate_passed"]
    )
    figure_path = OUTPUT / "phase7b8e_backtracked_radiation_map.png"
    _plot(figure_path, reports, raw_residual, wall_runtime)
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "block_count": len(reports),
        "owned_frequency_group_count": int(np.sum(ownership)),
        "minimum_mapped_intensity": min(float(row["minimum_mapped_intensity"]) for row in reports),
        "one_map_raw_radiation_residual": raw_residual,
        "maximum_process_peak_rss_mib": max(rss),
        "total_wall_runtime_s": wall_runtime,
        "initial_state_path": str(initial_path.relative_to(ROOT)),
        "initial_state_sha256": protocol["sources"]["initial_radiation_state"]["sha256"],
        "mapped_state_path": str(output_path.relative_to(ROOT)),
        "mapped_state_sha256": _sha256(output_path),
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(OUTPUT / "phase7b8e_backtracked_radiation_map_summary.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b8e_preregistered_backtracked_radiation_map.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.block_index is None or args.output_state is None or args.worker_report is None:
            raise ValueError("Phase 7B8e worker arguments are incomplete")
        _configure_reused_worker()
        phase7b8b.run_worker(
            args.protocol, args.block_index, args.output_state, args.worker_report
        )
        return
    print(json.dumps(run(args.protocol), indent=2))


if __name__ == "__main__":
    main()
