"""Phase 7B5r：执行 9632 组单单元角度--辐射子网格联合门。"""

from __future__ import annotations

import argparse
import csv
from dataclasses import fields
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil_from_active_edges,
)
from eccentric_tde_observer.multiresolution_frequency import (
    piecewise_constant_photoionization_rates_s1,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
)

try:
    from scripts.phase7b5a_log_frequency_p1_gate import (
        _collision_physical_slice,
    )
    from scripts.phase7b5k_high_resolution_convergence import (
        _returned_array_bytes,
    )
    from scripts.phase7b5m_actual_multiresolution_validation import (
        _converged_p0_map,
        _edge_sha256,
    )
    from scripts.phase7b5p_isolated_resource_profile import (
        _result_sha256,
        ru_maxrss_to_bytes,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5a_log_frequency_p1_gate import (  # type: ignore[no-redef]
        _collision_physical_slice,
    )
    from phase7b5k_high_resolution_convergence import (  # type: ignore[no-redef]
        _returned_array_bytes,
    )
    from phase7b5m_actual_multiresolution_validation import (  # type: ignore[no-redef]
        _converged_p0_map,
        _edge_sha256,
    )
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        _result_sha256,
        ru_maxrss_to_bytes,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "ff7a39925d5819d0267594a4221467ed211a634f3e5761b0575698d2c6675c0f"
)
MIB_BYTES = 1024**2
SCALAR_OBSERVABLES = (
    "frequency_integrated_volume_mean_comoving_intensity",
    "h_i_photoionization_rate_s1",
    "he_i_photoionization_rate_s1",
    "he_ii_photoionization_rate_s1",
    "final_radiation_energy_erg_cm2",
    "two_sided_emergent_flux_erg_s_cm2",
    "integrated_material_heating_erg_s_cm2",
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
    fields_out: list[str] = []
    for row in rows:
        fields_out.extend(key for key in row if key not in fields_out)
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields_out)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256_file(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B5r protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        source_path = ROOT / source["path"]
        if _sha256_file(source_path) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B5r source changed: {source_path}")
    return protocol


def _subdivide_parent_edge(parent_edge: np.ndarray, count: int) -> np.ndarray:
    fraction = np.linspace(0.0, 1.0, int(count) + 1)
    return parent_edge[0] + fraction * (parent_edge[1] - parent_edge[0])


def _scale_normalized_difference(value: float, reference: float) -> float:
    scale = max(abs(value), abs(reference))
    difference = abs(value - reference)
    return difference / scale if scale > 0.0 else difference


def _spectrum_l1_difference(
    candidate: np.ndarray, reference: np.ndarray, width: np.ndarray
) -> float:
    numerator = float(np.sum(width * np.abs(candidate - reference)))
    scale = max(
        float(np.sum(width * np.abs(candidate))),
        float(np.sum(width * np.abs(reference))),
    )
    return numerator / scale if scale > 0.0 else numerator


def _worker_observables(stencil, result, new_edge: np.ndarray) -> tuple[dict, np.ndarray]:
    physical = _collision_physical_slice(stencil)
    depth_width = np.diff(new_edge)
    total_depth = float(np.sum(depth_width))
    volume_mean = np.sum(
        result.final_comoving_mean_intensity_density[physical]
        * depth_width[None, :],
        axis=1,
    ) / total_depth
    frequency_width = np.diff(stencil.active_lab_edge_hz)
    rates = piecewise_constant_photoionization_rates_s1(
        stencil.active_lab_edge_hz,
        volume_mean,
        quadrature_order_per_group=16,
    )
    observables = {
        "frequency_integrated_volume_mean_comoving_intensity": float(
            np.sum(frequency_width * volume_mean)
        ),
        "h_i_photoionization_rate_s1": float(rates[0]),
        "he_i_photoionization_rate_s1": float(rates[1]),
        "he_ii_photoionization_rate_s1": float(rates[2]),
        "final_radiation_energy_erg_cm2": float(
            np.sum(
                frequency_width
                * result.final_radiation_energy_group_erg_cm2_hz
            )
        ),
        "two_sided_emergent_flux_erg_s_cm2": float(
            np.sum(
                frequency_width
                * (
                    result.right_ale_energy_flux_group_cgs
                    - result.left_ale_energy_flux_group_cgs
                )
            )
        ),
        "integrated_material_heating_erg_s_cm2": float(
            np.sum(
                frequency_width
                * result.material_heating_group_erg_s_cm2_hz
            )
        ),
    }
    values = np.asarray(tuple(observables.values()))
    if (
        not np.all(np.isfinite(values))
        or not np.all(np.isfinite(volume_mean))
        or np.any(volume_mean < 0.0)
    ):
        raise ArithmeticError("Phase 7B5r observables became invalid")
    return observables, volume_mean


def run_worker(
    input_path: Path,
    angular_direction_count: int,
    radiation_subcells: int,
    output_path: Path,
    spectrum_path: Path,
) -> None:
    with np.load(input_path) as payload:
        active_edge = np.array(payload["active_edge_hz"], copy=True)
        maximum_beta = float(payload["maximum_beta"])
        parent_old_edge = np.array(payload["old_edge"], copy=True)
        parent_new_edge = np.array(payload["new_edge"], copy=True)
        parent_beta = np.array(payload["beta"], copy=True)
        if parent_beta.shape != (1,):
            raise RuntimeError("Phase 7B5r input must contain exactly one parent cell")
        state = {
            "temperature_k": float(payload["temperature_k"]),
            "density_g_cm3": float(payload["density_g_cm3"]),
            "hydrogen_fraction": np.array(
                payload["hydrogen_fraction"], copy=True
            ),
            "helium_fraction": np.array(payload["helium_fraction"], copy=True),
            "duration_s": float(payload["duration_s"]),
        }
    stencil = mixed_frame_frequency_stencil_from_active_edges(
        active_edge, maximum_beta
    )
    mu, weight = gauss_legendre_mu_weights(angular_direction_count)
    old_edge = _subdivide_parent_edge(parent_old_edge, radiation_subcells)
    new_edge = _subdivide_parent_edge(parent_new_edge, radiation_subcells)
    # 中文：只增加辐射深度自由度；父物质速度和热力学状态不被插值或重定义。
    state["beta"] = np.repeat(parent_beta, radiation_subcells)
    baseline = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
    result = _converged_p0_map(
        stencil,
        old_edge,
        new_edge,
        mu,
        weight,
        state,
        None,
    )
    operator_runtime = time.perf_counter() - started
    peak = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    observables, volume_mean = _worker_observables(stencil, result, new_edge)
    np.savez_compressed(
        spectrum_path,
        active_edge_hz=active_edge,
        volume_mean_comoving_intensity=volume_mean,
    )
    report = {
        "pid": os.getpid(),
        "platform": sys.platform,
        "physical_group_count": stencil.physical_group_count,
        "active_edge_sha256": _edge_sha256(active_edge),
        "angular_direction_count": int(angular_direction_count),
        "radiation_subcells_per_parent": int(radiation_subcells),
        "radiation_unknown_count": int(
            stencil.physical_group_count
            * angular_direction_count
            * radiation_subcells
        ),
        "operator_runtime_s": operator_runtime,
        "baseline_highwater_rss_bytes": baseline,
        "peak_process_rss_bytes": peak,
        "operator_highwater_increase_bytes": max(0, peak - baseline),
        "returned_array_bytes": _returned_array_bytes(result),
        "fixed_point_iterations": result.fixed_point_iterations,
        "final_fixed_point_change": result.final_fixed_point_change,
        "fixed_point_converged": result.fixed_point_converged,
        "global_coupled_residual": (
            result.global_scale_normalized_coupled_residual
        ),
        "total_energy_ledger_residual": (
            result.total_relative_energy_ledger_residual
        ),
        "minimum_intensity": result.minimum_intensity,
        "result_sha256": _result_sha256(result),
        **observables,
    }
    _write_json_atomic(output_path, report)


def _comparison(
    key: str,
    candidate_key: str,
    reference_key: str,
    reports: dict[str, dict[str, object]],
    spectra: dict[str, np.ndarray],
    frequency_width: np.ndarray,
) -> dict[str, object]:
    candidate = reports[candidate_key]
    reference = reports[reference_key]
    errors = {
        name: _scale_normalized_difference(
            float(candidate[name]), float(reference[name])
        )
        for name in SCALAR_OBSERVABLES
    }
    errors["volume_mean_comoving_spectrum_l1"] = _spectrum_l1_difference(
        spectra[candidate_key], spectra[reference_key], frequency_width
    )
    return {
        "comparison": key,
        "candidate": candidate_key,
        "reference": reference_key,
        "errors": errors,
        "maximum_error": max(errors.values()),
        "worst_observable": max(errors, key=errors.get),
    }


def _comparison_rows(comparisons: dict[str, dict[str, object]]) -> list[dict]:
    rows = []
    for key, comparison in comparisons.items():
        for observable, error in comparison["errors"].items():
            rows.append(
                {
                    "comparison": key,
                    "candidate": comparison["candidate"],
                    "reference": comparison["reference"],
                    "observable": observable,
                    "relative_error": error,
                }
            )
    return rows


def _plot(
    path: Path,
    reports: dict[str, dict[str, object]],
    comparisons: dict[str, dict[str, object]],
    target: float,
) -> None:
    label_map = {
        "frequency_integrated_volume_mean_comoving_intensity": "Integrated mean J",
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
    angle_keys = ("angle8_vs24", "angle16_vs24")
    subgrid_keys = ("subcell8_vs32", "subcell16_vs32")
    for axis, keys, title in (
        (axes[0, 0], angle_keys, "Angular convergence at one cell"),
        (axes[0, 1], subgrid_keys, "Radiation-subgrid convergence at 16 angles"),
    ):
        x = np.arange(len(label_map))
        width = 0.36
        for index, key in enumerate(keys):
            values = [comparisons[key]["errors"][name] for name in label_map]
            axis.bar(
                x + (index - 0.5) * width,
                values,
                width=width,
                label=key.replace("_", " "),
            )
        axis.axhline(target, color="black", linestyle=":", label="1e-3 gate")
        axis.set_yscale("symlog", linthresh=1.0e-15)
        axis.set_xticks(x, label_map.values(), rotation=32, ha="right")
        axis.set_ylabel("Scale-normalized difference")
        axis.set_title(title)
        axis.grid(alpha=0.22, axis="y")
        axis.legend(fontsize=8)
    joint = comparisons["joint16x16_vs24x32"]
    joint_names = tuple(label_map)
    axes[1, 0].bar(
        np.arange(len(joint_names)),
        [joint["errors"][name] for name in joint_names],
        color="tab:green",
    )
    axes[1, 0].axhline(target, color="black", linestyle=":")
    axes[1, 0].set_yscale("symlog", linthresh=1.0e-15)
    axes[1, 0].set_xticks(
        np.arange(len(joint_names)),
        [label_map[name] for name in joint_names],
        rotation=32,
        ha="right",
    )
    axes[1, 0].set_ylabel("Scale-normalized difference")
    axes[1, 0].set_title("Joint production candidate: 16 angles x 16 subcells")
    axes[1, 0].grid(alpha=0.22, axis="y")
    for key, report in reports.items():
        axes[1, 1].scatter(
            report["radiation_unknown_count"],
            report["peak_process_rss_mib"],
            s=38,
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
    axes[1, 1].set_title("One-cell resource envelope")
    axes[1, 1].grid(alpha=0.22)
    figure.savefig(path, dpi=220)
    plt.close(figure)


def run_all(output_dir: Path, protocol_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5r_joint_convergence_summary.json",
        "runs": output_dir / "phase7b5r_joint_convergence_runs.csv",
        "comparisons": output_dir / "phase7b5r_joint_convergence_errors.csv",
        "figure": output_dir / "phase7b5r_joint_convergence.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    protocol = _load_protocol(protocol_path)
    input_path = ROOT / protocol["sources"][
        protocol["frequency_representation"]["input_source"]
    ]["path"]
    output_dir.mkdir(parents=True, exist_ok=True)
    reports: dict[str, dict[str, object]] = {}
    spectra: dict[str, np.ndarray] = {}
    rows: list[dict[str, object]] = []
    active_edge: np.ndarray | None = None
    with tempfile.TemporaryDirectory(prefix="phase7b5r-") as temporary:
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
                    f"Phase 7B5r worker {key} failed: {process.stderr.strip()}"
                )
            report = json.loads(worker_output.read_text(encoding="utf-8"))
            with np.load(spectrum_output) as spectrum_payload:
                edge = np.array(spectrum_payload["active_edge_hz"], copy=True)
                spectrum = np.array(
                    spectrum_payload["volume_mean_comoving_intensity"],
                    copy=True,
                )
            if active_edge is None:
                active_edge = edge
            elif not np.array_equal(active_edge, edge):
                raise RuntimeError("Phase 7B5r worker frequency edges diverged")
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
        raise RuntimeError("Phase 7B5r produced no worker spectra")
    frequency_width = np.diff(active_edge)
    paths_spec = protocol["paths"]
    comparisons = {
        "angle8_vs24": _comparison(
            "angle8_vs24",
            paths_spec["angle"]["coarse_control"],
            paths_spec["angle"]["reference"],
            reports,
            spectra,
            frequency_width,
        ),
        "angle16_vs24": _comparison(
            "angle16_vs24",
            paths_spec["angle"]["candidate"],
            paths_spec["angle"]["reference"],
            reports,
            spectra,
            frequency_width,
        ),
        "subcell8_vs32": _comparison(
            "subcell8_vs32",
            paths_spec["radiation_subgrid"]["coarse_control"],
            paths_spec["radiation_subgrid"]["reference"],
            reports,
            spectra,
            frequency_width,
        ),
        "subcell16_vs32": _comparison(
            "subcell16_vs32",
            paths_spec["radiation_subgrid"]["candidate"],
            paths_spec["radiation_subgrid"]["reference"],
            reports,
            spectra,
            frequency_width,
        ),
        "joint16x16_vs24x32": _comparison(
            "joint16x16_vs24x32",
            paths_spec["joint"]["candidate"],
            paths_spec["joint"]["reference"],
            reports,
            spectra,
            frequency_width,
        ),
    }
    gates = protocol["gates"]
    target = gates["production_relative_error_strictly_below"]
    pids = [report["pid"] for report in reports.values()]
    decision = {
        "frozen_protocol_hash_passed": True,
        "frozen_source_hashes_passed": True,
        "all_workers_exit_zero": len(reports) == len(protocol["configurations"]),
        "fresh_worker_pid_each_configuration": len(set(pids)) == len(pids),
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
        "angle_candidate_vs_reference_all_observables_passed": all(
            error < target
            for error in comparisons["angle16_vs24"]["errors"].values()
        ),
        "subgrid_candidate_vs_reference_all_observables_passed": all(
            error < target
            for error in comparisons["subcell16_vs32"]["errors"].values()
        ),
        "joint_candidate_vs_reference_all_observables_passed": all(
            error < target
            for error in comparisons["joint16x16_vs24x32"]["errors"].values()
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
        "angle_candidate_vs_reference_all_observables_passed",
        "subgrid_candidate_vs_reference_all_observables_passed",
        "joint_candidate_vs_reference_all_observables_passed",
        "frequency_budget_changed",
        "frequency_budget_authorized_by_user",
        "angle_or_radiation_subgrid_gate_authorized",
    )
    gate_passed = all(decision[key] for key in required)
    decision["phase7b5r_gate_passed"] = gate_passed
    _write_csv(paths["runs"], rows)
    _write_csv(paths["comparisons"], _comparison_rows(comparisons))
    _plot(paths["figure"], reports, comparisons, target)
    summary = {
        "phase": "7B5r 9632-group one-cell angle-radiation-subgrid gate",
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_path": str(protocol_path),
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "stress_state": protocol["stress_state"],
        "frequency_representation": protocol["frequency_representation"],
        "runs": reports,
        "comparisons": comparisons,
        "decision": decision,
        "accepted_one_cell_configuration": (
            {
                "physical_frequency_groups": 9632,
                "angular_direction_count": 16,
                "radiation_subcells_per_parent": 16,
            }
            if gate_passed
            else None
        ),
        "interpretation": (
            "The 9632-group one-cell production candidate passes prescribed "
            "angular, radiation-subgrid and joint fixed-point convergence. This "
            "does not authorize a full column, orbit, matter feedback, Phase 4 "
            "replacement or UVOT calculation."
            if gate_passed
            else "The converged 9632-group fixed points remain valid, but the "
            "prescribed 16-angle x 16-subcell production candidate fails at least "
            "one angular, radiation-subgrid or joint observable. No one-cell "
            "production configuration is accepted and no downstream phase is "
            "authorized."
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
            "Phase 7B5r joint convergence gate failed after preserving all outputs"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            OUTPUT / "phase7b5r_preregistered_joint_convergence_protocol.json"
        ),
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
            raise ValueError("all Phase 7B5r worker arguments must be supplied")
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
