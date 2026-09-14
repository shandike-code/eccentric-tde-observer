"""Phase 7B5s：执行更细 9632 组单单元联合参考。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from scripts.phase7b5r_joint_convergence import (
        MIB_BYTES,
        SCALAR_OBSERVABLES,
        _comparison,
        _comparison_rows,
        run_worker,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5r_joint_convergence import (  # type: ignore[no-redef]
        MIB_BYTES,
        SCALAR_OBSERVABLES,
        _comparison,
        _comparison_rows,
        run_worker,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "ac1d65d0d7b66b03545dd7cfc3e93e6e43bd3aa9fe66af71f9853eae7cbd75a2"
)


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
        raise ValueError(f"refusing to write an empty table: {path}")
    fields: list[str] = []
    for row in rows:
        fields.extend(key for key in row if key not in fields)
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256_file(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B5s protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        source_path = ROOT / source["path"]
        if _sha256_file(source_path) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B5s source changed: {source_path}")
    return protocol


def _plot(path, reports, comparisons, target):
    label_map = {
        "frequency_integrated_volume_mean_comoving_intensity": "Mean J",
        "h_i_photoionization_rate_s1": "H I rate",
        "he_i_photoionization_rate_s1": "He I rate",
        "he_ii_photoionization_rate_s1": "He II rate",
        "final_radiation_energy_erg_cm2": "Radiation energy",
        "two_sided_emergent_flux_erg_s_cm2": "Emergent flux",
        "integrated_material_heating_erg_s_cm2": "Material heating",
        "volume_mean_comoving_spectrum_l1": "Spectrum L1",
    }
    figure, axes = plt.subplots(
        2, 2, figsize=(13.0, 9.0), layout="constrained"
    )
    angle_keys = ("angle24_vs48", "angle32_vs48")
    x = np.arange(len(label_map))
    for index, key in enumerate(angle_keys):
        values = [comparisons[key]["errors"][name] for name in label_map]
        axes[0, 0].bar(
            x + (index - 0.5) * 0.36,
            values,
            width=0.36,
            label=key.replace("_", " "),
        )
    axes[0, 0].set_title("Refined angular convergence at 32 subcells")
    axes[0, 0].legend(fontsize=8)
    subgrid = comparisons["subcell32_vs64"]
    axes[0, 1].bar(
        x,
        [subgrid["errors"][name] for name in label_map],
        color="tab:orange",
    )
    axes[0, 1].set_title("Refined radiation-subgrid convergence at 32 angles")
    joint = comparisons["joint32x32_vs48x64"]
    axes[1, 0].bar(
        x,
        [joint["errors"][name] for name in label_map],
        color="tab:green",
    )
    axes[1, 0].set_title("Joint production candidate: 32 angles x 32 subcells")
    for axis in (axes[0, 0], axes[0, 1], axes[1, 0]):
        axis.axhline(target, color="black", linestyle=":")
        axis.set_yscale("symlog", linthresh=1.0e-15)
        axis.set_xticks(x, label_map.values(), rotation=32, ha="right")
        axis.set_ylabel("Scale-normalized difference")
        axis.grid(alpha=0.22, axis="y")
    for key, report in reports.items():
        axes[1, 1].scatter(
            report["radiation_unknown_count"],
            report["peak_process_rss_mib"],
            s=42,
        )
        axes[1, 1].annotate(
            key.replace("angle", "A").replace("_subcell", "xD"),
            (
                report["radiation_unknown_count"],
                report["peak_process_rss_mib"],
            ),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=7,
        )
    axes[1, 1].set_xscale("log")
    axes[1, 1].set_xlabel("Active radiation unknowns")
    axes[1, 1].set_ylabel("Fresh-process peak RSS (MiB)")
    axes[1, 1].set_title("Refined one-cell resource envelope")
    axes[1, 1].grid(alpha=0.22)
    figure.savefig(path, dpi=220)
    plt.close(figure)


def run_all(output_dir: Path, protocol_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5s_refined_joint_summary.json",
        "runs": output_dir / "phase7b5s_refined_joint_runs.csv",
        "comparisons": output_dir / "phase7b5s_refined_joint_errors.csv",
        "figure": output_dir / "phase7b5s_refined_joint_convergence.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    protocol = _load_protocol(protocol_path)
    input_path = ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]
    output_dir.mkdir(parents=True, exist_ok=True)
    reports: dict[str, dict[str, object]] = {}
    spectra: dict[str, np.ndarray] = {}
    rows: list[dict[str, object]] = []
    active_edge: np.ndarray | None = None
    with tempfile.TemporaryDirectory(prefix="phase7b5s-") as temporary:
        temporary_path = Path(temporary)
        for index, definition in enumerate(protocol["configurations"]):
            key = definition["key"]
            worker_output = temporary_path / f"worker_{index}.json"
            spectrum_output = temporary_path / f"spectrum_{index}.npz"
            process = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker-input",
                    str(input_path),
                    "--worker-angular-directions",
                    str(definition["angular_direction_count"]),
                    "--worker-radiation-subcells",
                    str(definition["radiation_subcells_per_parent"]),
                    "--worker-output",
                    str(worker_output),
                    "--worker-spectrum-output",
                    str(spectrum_output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if process.returncode != 0:
                raise RuntimeError(
                    f"Phase 7B5s worker {key} failed: {process.stderr.strip()}"
                )
            report = json.loads(worker_output.read_text(encoding="utf-8"))
            with np.load(spectrum_output) as payload:
                edge = np.array(payload["active_edge_hz"], copy=True)
                spectrum = np.array(
                    payload["volume_mean_comoving_intensity"], copy=True
                )
            if active_edge is None:
                active_edge = edge
            elif not np.array_equal(active_edge, edge):
                raise RuntimeError("Phase 7B5s worker frequency edges diverged")
            report["configuration_key"] = key
            report["peak_process_rss_mib"] = (
                report.pop("peak_process_rss_bytes") / MIB_BYTES
            )
            report["baseline_highwater_rss_mib"] = (
                report.pop("baseline_highwater_rss_bytes") / MIB_BYTES
            )
            report["operator_highwater_increase_mib"] = (
                report.pop("operator_highwater_increase_bytes") / MIB_BYTES
            )
            report["returned_array_mib"] = (
                report.pop("returned_array_bytes") / MIB_BYTES
            )
            reports[key] = report
            spectra[key] = spectrum
            rows.append(report)
    if active_edge is None:
        raise RuntimeError("Phase 7B5s produced no spectra")
    width = np.diff(active_edge)
    path_spec = protocol["paths"]
    comparisons = {
        "angle24_vs48": _comparison(
            "angle24_vs48",
            path_spec["angle"]["coarse_control"],
            path_spec["angle"]["reference"],
            reports,
            spectra,
            width,
        ),
        "angle32_vs48": _comparison(
            "angle32_vs48",
            path_spec["angle"]["candidate"],
            path_spec["angle"]["reference"],
            reports,
            spectra,
            width,
        ),
        "subcell32_vs64": _comparison(
            "subcell32_vs64",
            path_spec["radiation_subgrid"]["candidate"],
            path_spec["radiation_subgrid"]["reference"],
            reports,
            spectra,
            width,
        ),
        "joint32x32_vs48x64": _comparison(
            "joint32x32_vs48x64",
            path_spec["joint"]["candidate"],
            path_spec["joint"]["reference"],
            reports,
            spectra,
            width,
        ),
    }
    gates = protocol["gates"]
    target = gates["production_relative_error_strictly_below"]
    resource_limit = gates["fresh_process_peak_rss_strictly_below_mib"]
    decision = {
        "frozen_protocol_hash_passed": True,
        "frozen_source_hashes_passed": True,
        "all_workers_exit_zero": len(reports) == len(protocol["configurations"]),
        "fresh_worker_pid_each_configuration": (
            len({report["pid"] for report in reports.values()}) == len(reports)
        ),
        "all_fixed_points_converged": all(
            report["fixed_point_converged"] for report in reports.values()
        ),
        "all_global_coupled_residuals_passed": all(
            report["global_coupled_residual"]
            < gates["global_coupled_residual_strictly_below"]
            for report in reports.values()
        ),
        "all_energy_ledger_residuals_passed": all(
            abs(report["total_energy_ledger_residual"])
            < gates["energy_ledger_residual_strictly_below"]
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
        "edge_hash_unchanged": all(
            report["active_edge_sha256"]
            == protocol["frequency_representation"]["active_edge_sha256"]
            for report in reports.values()
        ),
        "resource_cap_passed": all(
            report["peak_process_rss_mib"] < resource_limit
            for report in reports.values()
        ),
        "angle_candidate_vs_reference_all_observables_passed": all(
            error < target
            for error in comparisons["angle32_vs48"]["errors"].values()
        ),
        "subgrid_candidate_vs_reference_all_observables_passed": all(
            error < target
            for error in comparisons["subcell32_vs64"]["errors"].values()
        ),
        "joint_candidate_vs_reference_all_observables_passed": all(
            error < target
            for error in comparisons["joint32x32_vs48x64"]["errors"].values()
        ),
        **protocol["authorization"],
    }
    required = (
        "frozen_protocol_hash_passed",
        "frozen_source_hashes_passed",
        "all_workers_exit_zero",
        "fresh_worker_pid_each_configuration",
        "all_fixed_points_converged",
        "all_global_coupled_residuals_passed",
        "all_energy_ledger_residuals_passed",
        "all_intensities_nonnegative",
        "physical_group_count_exact",
        "edge_hash_unchanged",
        "resource_cap_passed",
        "angle_candidate_vs_reference_all_observables_passed",
        "subgrid_candidate_vs_reference_all_observables_passed",
        "joint_candidate_vs_reference_all_observables_passed",
    )
    gate_passed = all(decision[key] for key in required)
    decision["phase7b5s_gate_passed"] = gate_passed
    _write_csv(paths["runs"], rows)
    _write_csv(paths["comparisons"], _comparison_rows(comparisons))
    _plot(paths["figure"], reports, comparisons, target)
    summary = {
        "phase": "7B5s refined 9632-group one-cell joint reference",
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_path": str(protocol_path),
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "stress_state": protocol["stress_state"],
        "frequency_representation": protocol["frequency_representation"],
        "host_resource_preflight": protocol["host_resource_preflight"],
        "runs": reports,
        "comparisons": comparisons,
        "decision": decision,
        "accepted_one_cell_configuration": (
            {
                "physical_frequency_groups": 9632,
                "angular_direction_count": 32,
                "radiation_subcells_per_parent": 32,
            }
            if gate_passed
            else None
        ),
        "interpretation": (
            "The 32-angle x 32-subcell candidate passes the refined one-cell "
            "angular, subgrid, joint and resource gates. Downstream authorization "
            "remains unchanged."
            if gate_passed
            else "The refined fixed points remain valid, but the 32-angle x "
            "32-subcell candidate fails at least one prescribed science or resource "
            "gate. No production configuration or downstream phase is authorized."
        ),
        "figures": [paths["figure"].name],
    }
    _write_json_atomic(paths["summary"], summary)
    print(
        json.dumps(
            {
                "comparisons": {
                    key: {
                        "maximum_error": value["maximum_error"],
                        "worst_observable": value["worst_observable"],
                    }
                    for key, value in comparisons.items()
                },
                "maximum_peak_process_rss_mib": max(
                    report["peak_process_rss_mib"] for report in reports.values()
                ),
                "decision": decision,
            },
            indent=2,
        )
    )
    if not gate_passed:
        raise RuntimeError(
            "Phase 7B5s refined joint gate failed after preserving all outputs"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(OUTPUT / "phase7b5s_preregistered_refined_joint_protocol.json"),
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--worker-input", type=Path)
    parser.add_argument("--worker-angular-directions", type=int)
    parser.add_argument("--worker-radiation-subcells", type=int)
    parser.add_argument("--worker-output", type=Path)
    parser.add_argument("--worker-spectrum-output", type=Path)
    args = parser.parse_args()
    worker_arguments = (
        args.worker_input,
        args.worker_angular_directions,
        args.worker_radiation_subcells,
        args.worker_output,
        args.worker_spectrum_output,
    )
    if any(value is not None for value in worker_arguments):
        if any(value is None for value in worker_arguments):
            raise ValueError("all Phase 7B5s worker arguments must be supplied")
        run_worker(
            args.worker_input,
            args.worker_angular_directions,
            args.worker_radiation_subcells,
            args.worker_output,
            args.worker_spectrum_output,
        )
        return
    run_all(args.output_dir, args.protocol, force=args.force)


if __name__ == "__main__":
    main()
