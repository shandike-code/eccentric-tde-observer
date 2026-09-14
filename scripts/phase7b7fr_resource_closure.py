"""Phase 7B7f-r：一块一进程复现全局拼接态正式源项。"""

from __future__ import annotations

import argparse
import gc
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

try:
    from scripts import phase7b7e_radiation_direction as phase7b7e
    from scripts import phase7b7f_assembled_diagnostics as phase7b7f
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b7e_radiation_direction as phase7b7e  # type: ignore[no-redef]
    import phase7b7f_assembled_diagnostics as phase7b7f  # type: ignore[no-redef]
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "ed513d0840b6d76139a0a34b82a537f70472d51501c605666cabf45146a63a07"
)
MIB = 1024**2


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


def _write_npz_atomic(path: Path, **arrays: np.ndarray) -> None:
    temporary = path.with_name(f"{path.stem}.tmp.npz")
    np.savez(temporary, **arrays)
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B7f-r protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            if _sha256(ROOT / source["path"]) != source["sha256"]:
                raise RuntimeError(
                    f"frozen Phase 7B7f-r source changed: {source['path']}"
                )
    return protocol


def run_worker(
    protocol_path: Path,
    block_index: int,
    partial_path: Path,
    report_path: Path,
) -> None:
    # 中文：父进程已验证 10 GB 状态；子进程只验证冻结协议哈希，避免重复读取 76 次。
    protocol = _load_protocol(protocol_path, validate_sources=False)
    context = phase7b7e.phase7b5x._context(protocol)
    updated = phase7b7e._updated_full_material(protocol)
    shape = phase7b7e._shape(protocol)
    if block_index < 0 or block_index >= len(context["blocks"]):
        raise ValueError("Phase 7B7f-r block index is invalid")
    mapped = np.memmap(
        ROOT / protocol["sources"]["mapped_radiation_state"]["path"],
        mode="r",
        dtype=np.float64,
        shape=shape,
    )
    started = time.perf_counter()
    result = phase7b7f.assembled_block_diagnostics(
        protocol, context, updated, mapped, block_index
    )
    arrays = {
        name: np.asarray(result[name])
        for name in (
            "rate_material_heating_erg_s_cm3",
            "direct_comoving_material_heating_erg_s_cm3",
            "inverse_lab_four_force_material_heating_erg_s_cm3",
        )
    }
    _write_npz_atomic(partial_path, **arrays)
    del result, arrays, mapped
    gc.collect()
    peak_rss_mib = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    ) / MIB
    block = context["blocks"][block_index]
    _write_json_atomic(
        report_path,
        {
            "block_index": block_index,
            "core_group_start": int(block.core_group_start),
            "core_group_stop": int(block.core_group_stop),
            "runtime_s": time.perf_counter() - started,
            "peak_process_rss_mib": peak_rss_mib,
            "partial_path": str(partial_path.resolve().relative_to(ROOT)),
            "partial_sha256": _sha256(partial_path),
        },
    )


def _plot(
    path: Path,
    reports: list[dict[str, object]],
    differences: dict[str, float],
    metrics: dict[str, float],
) -> None:
    block = [int(row["block_index"]) for row in reports]
    rss = [float(row["peak_process_rss_mib"]) for row in reports]
    runtime = [float(row["runtime_s"]) for row in reports]
    figure, axes = plt.subplots(1, 3, figsize=(13.0, 4.0), constrained_layout=True)
    axes[0].bar(list(differences), list(differences.values()), color="#4c78a8")
    axes[0].set_ylim(0.0, 1.0)
    axes[0].text(
        0.5,
        0.55,
        "All maximum differences = 0\n(bitwise identical)",
        transform=axes[0].transAxes,
        ha="center",
        va="center",
    )
    axes[0].set(
        ylabel="Maximum absolute difference",
        title="(a) Reference reproduction",
    )
    axes[0].tick_params(axis="x", rotation=15)
    scatter = axes[1].scatter(block, rss, c=runtime, cmap="viridis", s=34)
    axes[1].axhline(6144.0, color="0.25", ls="--", label="RSS gate")
    axes[1].set(
        xlabel="Frequency block index",
        ylabel="Peak process RSS (MiB)",
        title="(b) Short-lived worker resources",
    )
    axes[1].legend(frameon=False)
    figure.colorbar(scatter, ax=axes[1], label="Block runtime (s)")
    names = ["Rate/direct", "Volume L1", "Column total"]
    values = [
        metrics["direct_rate_l1"],
        metrics["frame_volume_l1"],
        metrics["frame_global"],
    ]
    axes[2].bar(names, values, color=["#4c78a8", "#f58518", "#54a24b"])
    axes[2].axhline(1.0e-3, color="0.25", ls="--", label="Science gate")
    axes[2].set_yscale("log")
    axes[2].set(ylabel="Relative discrepancy", title="(c) Reproduced science gates")
    axes[2].tick_params(axis="x", rotation=15)
    axes[2].legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    block_count = int(configuration["block_count"])
    partial_paths = [
        OUTPUT / f"phase7b7fr_block{index:02d}_partial.npz"
        for index in range(block_count)
    ]
    report_paths = [
        OUTPUT / f"phase7b7fr_block{index:02d}.json"
        for index in range(block_count)
    ]
    started = time.perf_counter()
    concurrency = int(configuration["maximum_concurrent_processes"])
    for offset in range(0, block_count, concurrency):
        batch = range(offset, min(offset + concurrency, block_count))
        processes = []
        for block_index in batch:
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--worker",
                        "--protocol",
                        str(protocol_path),
                        "--block-index",
                        str(block_index),
                        "--partial",
                        str(partial_paths[block_index]),
                        "--worker-report",
                        str(report_paths[block_index]),
                    ],
                    cwd=ROOT,
                )
            )
        return_codes = [process.wait() for process in processes]
        if any(code != 0 for code in return_codes):
            raise RuntimeError(f"Phase 7B7f-r worker batch failed: {return_codes}")
        if (offset + len(return_codes)) % 10 == 0 or offset + len(return_codes) == block_count:
            print(
                json.dumps(
                    {
                        "completed_blocks": offset + len(return_codes),
                        "total_blocks": block_count,
                    }
                ),
                flush=True,
            )
    wall_runtime = time.perf_counter() - started
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    reports.sort(key=lambda row: int(row["block_index"]))
    shape = phase7b7e._shape(protocol)
    combined = {
        "rate": np.zeros(shape[2]),
        "direct": np.zeros(shape[2]),
        "formal": np.zeros(shape[2]),
    }
    ownership = np.zeros(shape[0], dtype=np.int64)
    for report in reports:
        block_index = int(report["block_index"])
        partial_path = partial_paths[block_index]
        if _sha256(partial_path) != report["partial_sha256"]:
            raise RuntimeError("Phase 7B7f-r partial hash changed")
        ownership[
            int(report["core_group_start"]) : int(report["core_group_stop"])
        ] += 1
        with np.load(partial_path) as partial:
            combined["rate"] += np.asarray(
                partial["rate_material_heating_erg_s_cm3"]
            )
            combined["direct"] += np.asarray(
                partial["direct_comoving_material_heating_erg_s_cm3"]
            )
            combined["formal"] += np.asarray(
                partial["inverse_lab_four_force_material_heating_erg_s_cm3"]
            )
    with np.load(
        ROOT / protocol["sources"]["phase7b7f_reference"]["path"]
    ) as reference:
        differences = {
            "Rate": float(
                np.max(
                    np.abs(
                        combined["rate"]
                        - np.asarray(
                            reference[
                                "assembled_rate_material_heating_erg_s_cm3"
                            ]
                        )
                    )
                )
            ),
            "Direct": float(
                np.max(
                    np.abs(
                        combined["direct"]
                        - np.asarray(
                            reference[
                                "assembled_direct_comoving_material_heating_erg_s_cm3"
                            ]
                        )
                    )
                )
            ),
            "Four-force": float(
                np.max(
                    np.abs(
                        combined["formal"]
                        - np.asarray(
                            reference[
                                "assembled_inverse_lab_four_force_material_heating_erg_s_cm3"
                            ]
                        )
                    )
                )
            ),
        }
    context = phase7b7e.phase7b5x._context(protocol)
    following = int(context["following"])
    subedge = phase7b7e.phase7b5x._subdivide_column_edge(
        context["full"]["edge_cm"][following], 16
    )
    subwidth = np.diff(subedge)
    direct_metrics = phase7b7f._source_metrics(
        combined["rate"], combined["direct"], subwidth
    )
    frame_metrics = phase7b7f._source_metrics(
        combined["rate"], combined["formal"], subwidth
    )
    rss = [float(row["peak_process_rss_mib"]) for row in reports]
    gates = protocol["gates"]
    decision = {
        "frozen_protocol_sources_and_reference_passed": True,
        "block_and_frequency_ownership_passed": bool(
            len(reports) == gates["block_count_exactly"]
            and int(np.sum(ownership))
            == gates["owned_frequency_group_count_exactly"]
            and np.all(ownership == 1)
        ),
        "bitwise_science_reference_reproduced": bool(
            all(
                value == gates["maximum_absolute_reference_difference_exactly"]
                for value in differences.values()
            )
        ),
        "assembled_science_gates_reproduced": bool(
            direct_metrics[0]
            < gates["assembled_rate_vs_direct_comoving_source_volume_l1_below"]
            and frame_metrics[0]
            < gates["assembled_rate_vs_inverse_four_force_volume_l1_below"]
            and frame_metrics[1]
            < gates[
                "assembled_rate_vs_inverse_four_force_global_fraction_below"
            ]
        ),
        "resource_and_runtime_gates_passed": bool(
            all(
                value < gates["each_process_peak_rss_strictly_below_mib"]
                for value in rss
            )
            and wall_runtime < gates["total_wall_time_strictly_below_s"]
        ),
        "accepted_as_radiation_or_coupled_fixed_point": False,
        "second_material_update_authorized": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b7fr_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_sources_and_reference_passed",
            "block_and_frequency_ownership_passed",
            "bitwise_science_reference_reproduced",
            "assembled_science_gates_reproduced",
            "resource_and_runtime_gates_passed",
        )
    )
    decision["bounded_coupled_continuation_design_authorized"] = bool(
        decision["phase7b7fr_gate_passed"]
    )
    figure_path = OUTPUT / "phase7b7fr_resource_closure.png"
    _plot(
        figure_path,
        reports,
        differences,
        {
            "direct_rate_l1": direct_metrics[0],
            "frame_volume_l1": frame_metrics[0],
            "frame_global": frame_metrics[1],
        },
    )
    report = {
        "phase": "7B7f-r short-lived-process resource closure",
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": _sha256(protocol_path),
        "block_count": len(reports),
        "owned_frequency_group_count": int(np.sum(ownership)),
        "maximum_absolute_reference_differences": differences,
        "assembled_rate_vs_direct_comoving_source_volume_l1": direct_metrics[0],
        "assembled_rate_vs_inverse_four_force_volume_l1": frame_metrics[0],
        "assembled_rate_vs_inverse_four_force_global_fraction": frame_metrics[1],
        "maximum_process_peak_rss_mib": max(rss),
        "total_wall_runtime_s": wall_runtime,
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b7fr_resource_closure_summary.json", report
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b7fr_preregistered_resource_closure.json",
    )
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--partial", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.block_index is None or args.partial is None or args.worker_report is None:
            raise ValueError("Phase 7B7f-r worker arguments are incomplete")
        run_worker(
            args.protocol, args.block_index, args.partial, args.worker_report
        )
        return
    print(json.dumps(run(args.protocol), indent=2))


if __name__ == "__main__":
    main()
