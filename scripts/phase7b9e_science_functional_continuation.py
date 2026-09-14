"""Phase 7B9e：按全局源变化与边界泛函续算固定物质辐射场。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from scripts import phase7b9d_inner_converged_base_radiation as phase7b9d
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9d_inner_converged_base_radiation as phase7b9d  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "469cfe102cf38a6d2d9f80ef3c4cf06810b38e54467739807287a17a1cef12d3"
)


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


def _load_protocol(path: Path) -> dict[str, object]:
    if _sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9e protocol changed")
    protocol = json.loads(path.read_text())
    for source in protocol["sources"].values():
        source_path = ROOT / source["path"]
        if (
            source_path.stat().st_size != int(source["size_bytes"])
            or _sha256(source_path) != source["sha256"]
        ):
            raise RuntimeError(f"frozen Phase 7B9e source changed: {source['path']}")
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


def _new_manifest(protocol: dict[str, object], path: Path) -> dict[str, object]:
    snapshot = json.loads(
        (ROOT / protocol["sources"]["phase7b9d_snapshot"]["path"]).read_text()
    )
    configuration = protocol["configuration"]
    if (
        int(snapshot["current_additional_map"])
        != int(configuration["starting_additional_map"])
        or snapshot["current_state_sha256"]
        != protocol["gates"]["committed_start_sha256_exactly"]
        or snapshot["current_state_sha256"]
        != protocol["sources"]["current_committed_radiation"]["sha256"]
    ):
        raise RuntimeError("Phase 7B9e starting snapshot changed")
    manifest = {
        "phase": protocol["phase"],
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "status": "running",
        "current_additional_map": snapshot["current_additional_map"],
        "current_state_path": snapshot["current_state_path"],
        "current_state_sha256": snapshot["current_state_sha256"],
        "history": snapshot["history"],
        # 中文：继承中断前已逐块验哈希的第二轮工作，不重算已提交块。
        "uncommitted_iteration": snapshot["uncommitted_iteration"],
    }
    _write_json_atomic(path, manifest)
    return manifest


def _load_or_create_manifest(
    protocol: dict[str, object], path: Path, shape: tuple[int, int, int]
) -> dict[str, object]:
    if not path.exists():
        manifest = _new_manifest(protocol, path)
    else:
        manifest = json.loads(path.read_text())
    if manifest.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("Phase 7B9e manifest belongs to another protocol")
    if manifest.get("status") not in ("running", "complete", "gate_failed"):
        raise RuntimeError("Phase 7B9e manifest status is invalid")
    current_path = ROOT / manifest["current_state_path"]
    expected_size = int(protocol["configuration"]["raw_float64_checkpoint_size_bytes"])
    if (
        current_path.stat().st_size != expected_size
        or _sha256(current_path) != manifest["current_state_sha256"]
    ):
        raise RuntimeError("Phase 7B9e committed current state changed")
    uncommitted = manifest.get("uncommitted_iteration")
    if uncommitted is not None:
        output = ROOT / uncommitted["output_state_path"]
        if output.stat().st_size != expected_size:
            raise RuntimeError("Phase 7B9e partial output size changed")
        for record in uncommitted["completed_blocks"]:
            digest = phase7b9d._block_sha256(
                output,
                shape,
                int(record["core_group_start"]),
                int(record["core_group_stop"]),
            )
            if digest != record["sha256"]:
                raise RuntimeError(
                    f"Phase 7B9e inherited block changed: {record['block_index']}"
                )
    return manifest


def _plot(path: Path, history: list[dict[str, object]], gates: dict[str, object]) -> None:
    total_maps = np.array([row["total_source_maps_at_current_material"] for row in history])
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.1), constrained_layout=True)
    axes[0, 0].semilogy(
        total_maps,
        [row["raw_source_map_residual"] for row in history],
        "o-",
    )
    axes[0, 0].axhline(
        gates["global_source_map_residual_below"],
        color="0.25",
        ls="--",
        label="Global source gate",
    )
    axes[0, 0].set(
        xlabel="Total source maps at fixed material",
        ylabel="Global-scale radiation change",
        title="(a) Fixed-material source convergence",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].semilogy(
        total_maps,
        [row["boundary_flux_spectrum_l1"] for row in history],
        "o-",
        label="Spectral L1",
    )
    axes[0, 1].semilogy(
        total_maps,
        [row["boundary_flux_bolometric_fraction"] for row in history],
        "s-",
        label="Bolometric",
    )
    axes[0, 1].axhline(1.0e-3, color="0.25", ls="--", label="Boundary gate")
    axes[0, 1].set(
        xlabel="Total source maps at fixed material",
        ylabel="Successive boundary-flux change",
        title="(b) Observer-facing science functionals",
    )
    axes[0, 1].legend(frameon=False)
    axes[1, 0].semilogy(
        total_maps,
        [row["maximum_internal_energy_ledger_residual"] for row in history],
        "o-",
        color="#9b6b5a",
    )
    axes[1, 0].set(
        xlabel="Total source maps at fixed material",
        ylabel="Recorded one-map block diagnostic",
        title="(c) Internal ledger retained but not used for admission",
    )
    axes[1, 1].plot(
        total_maps,
        [row["maximum_process_peak_rss_mib"] for row in history],
        "o-",
        label="Peak RSS",
    )
    axes[1, 1].axhline(6144.0, color="0.25", ls="--", label="Process gate")
    axes[1, 1].set(
        xlabel="Total source maps at fixed material",
        ylabel="Peak process RSS (MiB)",
        title="(d) Recoverable worker resources",
    )
    axes[1, 1].legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    runtime_protocol = json.loads(json.dumps(protocol))
    runtime_protocol["configuration"]["initial_source_maps_at_current_material"] = 1
    shape = phase7b9d._shape(runtime_protocol)
    with np.load(ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]) as master:
        frequency_width = np.diff(np.array(master["active_edge_hz"], copy=True))
    manifest_path = ROOT / configuration["corrected_manifest"]
    manifest = _load_or_create_manifest(protocol, manifest_path, shape)
    if manifest["status"] == "complete":
        return json.loads(
            (OUTPUT / "phase7b9e_science_functional_continuation_summary.json").read_text()
        )
    if manifest["status"] == "gate_failed":
        raise RuntimeError("Phase 7B9e exhausted the frozen map budget")
    old_worker_protocol = ROOT / protocol["sources"]["phase7b9d_original_protocol"]["path"]
    maximum_map = int(configuration["maximum_total_additional_maps"])
    while int(manifest["current_additional_map"]) < maximum_map:
        phase7b9d._run_one_iteration(
            runtime_protocol,
            protocol_path,
            manifest_path,
            manifest,
            shape,
            frequency_width,
            worker_protocol_path=old_worker_protocol,
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
    previous = history[-2] if len(history) >= 2 else None
    figure_path = OUTPUT / "phase7b9e_science_functional_continuation.png"
    _plot(figure_path, history, gates)
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "phase_index": int(configuration["phase_index"]),
        "starting_additional_map": int(configuration["starting_additional_map"]),
        "final_additional_map": int(manifest["current_additional_map"]),
        "total_source_maps_at_current_material": int(
            final["total_source_maps_at_current_material"]
        ),
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
        "total_new_wall_runtime_s": float(
            sum(row["wall_runtime_s"] for row in history[1:])
        ),
        "decision": {
            "frozen_sources_and_inherited_hashes_passed": True,
            "global_source_and_boundary_functionals_converged": converged,
            "two_consecutive_map_gate_passed": consecutive
            >= int(configuration["minimum_consecutive_converged_maps"]),
            "one_map_internal_ledger_used_as_admission_gate": False,
            "formal_h_he_rate_and_heating_comparison_evaluated": False,
            "accepted_as_inner_converged_newton_residual": False,
            "full_frequency_jv_evaluated": False,
            "accepted_as_dynamic_NLTE_solution": False,
            "phase7b9e_gate_passed": converged,
            "formal_h_he_rate_and_heating_comparison_authorized": converged,
        },
        "history": history,
        "figures": [figure_path.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9e_science_functional_continuation_summary.json", report
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9e_preregistered_science_functional_continuation.json",
    )
    args = parser.parse_args()
    print(json.dumps(run(args.protocol), indent=2))


if __name__ == "__main__":
    main()
