"""Phase 7B5t：执行特征分区角求积与精确单元特征输运门。"""

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
import tempfile
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil_from_active_edges,
    solve_mixed_frame_ale_group_step,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_half_range_mu_weights,
    gauss_legendre_split_mu_weights,
    linear_source_top_intensity,
)
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S

try:
    from scripts.phase7b5i_partition_representation_split import (
        ITERATIVE_TOLERANCE,
        _p0_operator_context,
    )
    from scripts.phase7b5k_high_resolution_convergence import (
        _returned_array_bytes,
    )
    from scripts.phase7b5m_actual_multiresolution_validation import (
        _edge_sha256,
    )
    from scripts.phase7b5p_isolated_resource_profile import (
        _result_sha256,
        ru_maxrss_to_bytes,
    )
    from scripts.phase7b5r_joint_convergence import (
        MIB_BYTES,
        SCALAR_OBSERVABLES,
        _comparison,
        _comparison_rows,
        _subdivide_parent_edge,
        _worker_observables,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5i_partition_representation_split import (  # type: ignore[no-redef]
        ITERATIVE_TOLERANCE,
        _p0_operator_context,
    )
    from phase7b5k_high_resolution_convergence import (  # type: ignore[no-redef]
        _returned_array_bytes,
    )
    from phase7b5m_actual_multiresolution_validation import (  # type: ignore[no-redef]
        _edge_sha256,
    )
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        _result_sha256,
        ru_maxrss_to_bytes,
    )
    from phase7b5r_joint_convergence import (  # type: ignore[no-redef]
        MIB_BYTES,
        SCALAR_OBSERVABLES,
        _comparison,
        _comparison_rows,
        _subdivide_parent_edge,
        _worker_observables,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "bd07fa6bc3007f3dd668baa2e205cb655364f6fa7e2af1959046f0c5cefc8400"
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
        raise RuntimeError(f"frozen Phase 7B5t protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        source_path = ROOT / source["path"]
        if _sha256_file(source_path) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B5t source changed: {source_path}")
    return protocol


def _characteristic_quadrature(
    order: int,
    old_parent_edge: np.ndarray,
    new_parent_edge: np.ndarray,
    duration_s: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    face_velocity = (new_parent_edge - old_parent_edge) / duration_s
    split_mu = float(np.mean(face_velocity) / LIGHT_SPEED_CM_S)
    mu, weight = gauss_legendre_split_mu_weights(order, split_mu)
    return mu, weight, split_mu


def _load_worker_state(input_path: Path) -> dict[str, object]:
    with np.load(input_path) as payload:
        return {
            "active_edge": np.array(payload["active_edge_hz"], copy=True),
            "maximum_beta": float(payload["maximum_beta"]),
            "parent_old_edge": np.array(payload["old_edge"], copy=True),
            "parent_new_edge": np.array(payload["new_edge"], copy=True),
            "parent_beta": np.array(payload["beta"], copy=True),
            "temperature_k": float(payload["temperature_k"]),
            "density_g_cm3": float(payload["density_g_cm3"]),
            "hydrogen_fraction": np.array(
                payload["hydrogen_fraction"], copy=True
            ),
            "helium_fraction": np.array(payload["helium_fraction"], copy=True),
            "duration_s": float(payload["duration_s"]),
        }


def run_worker(
    input_path: Path,
    spatial_scheme: str,
    angular_direction_count: int,
    radiation_subcells: int,
    output_path: Path,
    spectrum_path: Path,
) -> None:
    loaded = _load_worker_state(input_path)
    parent_beta = loaded["parent_beta"]
    if parent_beta.shape != (1,):
        raise RuntimeError("Phase 7B5t input must contain exactly one parent cell")
    old_edge = _subdivide_parent_edge(
        loaded["parent_old_edge"], radiation_subcells
    )
    new_edge = _subdivide_parent_edge(
        loaded["parent_new_edge"], radiation_subcells
    )
    mu, weight, split_mu = _characteristic_quadrature(
        angular_direction_count,
        loaded["parent_old_edge"],
        loaded["parent_new_edge"],
        loaded["duration_s"],
    )
    face_beta = (new_edge - old_edge) / (
        loaded["duration_s"] * LIGHT_SPEED_CM_S
    )
    minimum_characteristic_distance = float(
        np.min(np.abs(mu[:, None] - face_beta[None, :]))
    )
    if minimum_characteristic_distance <= 0.0:
        raise RuntimeError("a prescribed quadrature ray reverses on an ALE face")
    state = {
        "temperature_k": loaded["temperature_k"],
        "density_g_cm3": loaded["density_g_cm3"],
        "hydrogen_fraction": loaded["hydrogen_fraction"],
        "helium_fraction": loaded["helium_fraction"],
        "duration_s": loaded["duration_s"],
        # 中文：只复制冻结父物质状态，深度自由度属于辐射输运。
        "beta": np.repeat(parent_beta, radiation_subcells),
    }
    stencil = mixed_frame_frequency_stencil_from_active_edges(
        loaded["active_edge"], loaded["maximum_beta"]
    )
    initial, outer, continuum = _p0_operator_context(stencil, mu, weight, state)
    baseline = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    started = time.perf_counter()
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
        spatial_scheme=spatial_scheme,
    )
    operator_runtime = time.perf_counter() - started
    peak = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    observables, volume_mean = _worker_observables(stencil, result, new_edge)
    np.savez_compressed(
        spectrum_path,
        active_edge_hz=loaded["active_edge"],
        volume_mean_comoving_intensity=volume_mean,
    )
    report = {
        "pid": os.getpid(),
        "platform": sys.platform,
        "spatial_scheme": spatial_scheme,
        "angular_quadrature": "characteristic_split",
        "angular_split_mu": split_mu,
        "minimum_quadrature_distance_from_ale_reversal": (
            minimum_characteristic_distance
        ),
        "physical_group_count": stencil.physical_group_count,
        "active_edge_sha256": _edge_sha256(loaded["active_edge"]),
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
        "global_coupled_residual": result.global_scale_normalized_coupled_residual,
        "total_energy_ledger_residual": result.total_relative_energy_ledger_residual,
        "minimum_intensity": result.minimum_intensity,
        "result_sha256": _result_sha256(result),
        **observables,
    }
    _write_json_atomic(output_path, report)


def _linear_source_convergence() -> list[dict[str, object]]:
    stencil = mixed_frame_frequency_stencil_from_active_edges([1.0, 2.0], 0.0)
    mu, weight = gauss_legendre_half_range_mu_weights(8)
    outgoing = mu < 0.0
    expected = linear_source_top_intensity(
        1.0, 0.7, 2.0, np.abs(mu[outgoing])
    )
    rows: list[dict[str, object]] = []
    for scheme in ("upwind_finite_volume", "step_characteristics"):
        errors = []
        for depth_points in (16, 32, 64):
            edge = np.linspace(0.0, 1.0, depth_points + 1)
            centre = 0.5 * (edge[:-1] + edge[1:])
            absorption = np.full((1, depth_points), 2.0)
            result = solve_mixed_frame_ale_group_step(
                stencil,
                edge,
                edge,
                mu,
                weight,
                0.0,
                0.0,
                absorption,
                absorption * (1.0 + 0.7 * centre)[None, :],
                0.0,
                np.zeros(depth_points),
                1.0e12,
                propagation_speed_cm_s=1.0,
                iterative_tolerance=1.0e-12,
                spatial_scheme=scheme,
            )
            error = float(
                np.max(
                    np.abs(
                        result.left_ale_face_intensity[0, outgoing] - expected
                    )
                )
                / np.max(expected)
            )
            errors.append(error)
            rows.append(
                {
                    "control": "linear_source_absorption",
                    "spatial_scheme": scheme,
                    "depth_cells": depth_points,
                    "maximum_relative_error": error,
                    "observed_order_to_next": None,
                }
            )
        for index in range(2):
            rows[-3 + index]["observed_order_to_next"] = float(
                np.log(errors[index] / errors[index + 1]) / np.log(2.0)
            )
    return rows


def _constant_source_and_moving_grid_controls() -> dict[str, float]:
    stencil = mixed_frame_frequency_stencil_from_active_edges([1.0, 2.0], 0.0)
    mu, weight = gauss_legendre_half_range_mu_weights(4)
    depth_points = 4
    edge = np.linspace(0.0, 1.0, depth_points + 1)
    duration = 0.4
    absorption_value = 2.0
    thermal_source = 1.3
    initial_value = 0.2
    left_value = 0.7
    right_value = 0.9
    initial = np.full((1, mu.size, depth_points), initial_value)
    absorption = np.full((1, depth_points), absorption_value)
    result = solve_mixed_frame_ale_group_step(
        stencil,
        edge,
        edge,
        mu,
        weight,
        initial,
        initial,
        absorption,
        absorption * thermal_source,
        0.0,
        np.zeros(depth_points),
        duration,
        left_exterior_intensity=left_value,
        right_exterior_intensity=right_value,
        propagation_speed_cm_s=1.0,
        spatial_scheme="step_characteristics",
        iterative_tolerance=2.0e-13,
    )
    effective_extinction = absorption_value + 1.0 / duration
    effective_source = (
        initial_value / duration + absorption_value * thermal_source
    ) / effective_extinction
    expected = np.empty_like(result.final_lab_intensity_density)
    for angle, cosine in enumerate(mu):
        incoming = left_value if cosine > 0.0 else right_value
        for depth in range(depth_points):
            if cosine > 0.0:
                start, stop = edge[depth], edge[depth + 1]
            else:
                start = 1.0 - edge[depth + 1]
                stop = 1.0 - edge[depth]
            lower = effective_extinction * start / abs(cosine)
            upper = effective_extinction * stop / abs(cosine)
            average_attenuation = (
                np.exp(-lower) - np.exp(-upper)
            ) / (upper - lower)
            expected[0, angle, depth] = effective_source + (
                incoming - effective_source
            ) * average_attenuation
    constant_error = float(
        np.max(np.abs(result.final_lab_intensity_density - expected))
    )
    moving_old = np.linspace(0.0, 1.0, 6)
    moving_new = 0.01 + 1.02 * moving_old
    moving_absorption = np.full((1, 5), 1.7)
    moving = solve_mixed_frame_ale_group_step(
        stencil,
        moving_old,
        moving_new,
        mu,
        weight,
        0.3,
        0.3,
        moving_absorption,
        1.1 * moving_absorption,
        0.0,
        np.zeros(5),
        1.0,
        left_exterior_intensity=0.4,
        right_exterior_intensity=0.6,
        propagation_speed_cm_s=1.0,
        spatial_scheme="step_characteristics",
        iterative_tolerance=2.0e-13,
    )
    return {
        "constant_source_maximum_absolute_error": constant_error,
        "constant_source_global_coupled_residual": (
            result.global_scale_normalized_coupled_residual
        ),
        "constant_source_energy_ledger_residual": (
            result.total_relative_energy_ledger_residual
        ),
        "moving_grid_global_coupled_residual": (
            moving.global_scale_normalized_coupled_residual
        ),
        "moving_grid_energy_ledger_residual": (
            moving.total_relative_energy_ledger_residual
        ),
        "minimum_control_intensity": min(
            result.minimum_intensity, moving.minimum_intensity
        ),
    }


def _plot(path, analytic_rows, previous_full, comparisons, reports, target):
    labels = {
        "frequency_integrated_volume_mean_comoving_intensity": "Mean J",
        "h_i_photoionization_rate_s1": "H I rate",
        "he_i_photoionization_rate_s1": "He I rate",
        "he_ii_photoionization_rate_s1": "He II rate",
        "final_radiation_energy_erg_cm2": "Radiation energy",
        "two_sided_emergent_flux_erg_s_cm2": "Emergent flux",
        "integrated_material_heating_erg_s_cm2": "Material heating",
        "volume_mean_comoving_spectrum_l1": "Spectrum L1",
    }
    figure, axes = plt.subplots(2, 2, figsize=(13.2, 9.2), layout="constrained")
    for scheme, label, marker in (
        ("upwind_finite_volume", "Upwind finite volume", "o"),
        ("step_characteristics", "Step characteristics", "s"),
    ):
        selected = [row for row in analytic_rows if row["spatial_scheme"] == scheme]
        axes[0, 0].loglog(
            [row["depth_cells"] for row in selected],
            [row["maximum_relative_error"] for row in selected],
            marker=marker,
            label=label,
        )
    axes[0, 0].set_title("Analytic linear-source spatial convergence")
    axes[0, 0].set_xlabel("Depth cells")
    axes[0, 0].set_ylabel("Maximum relative error")
    axes[0, 0].legend(fontsize=8)
    x = np.arange(len(labels))
    angle_series = (
        ("Full-range GL", previous_full),
        ("Split GL + upwind", comparisons["split_angle_upwind"]),
        ("Split GL + step", comparisons["split_angle_step"]),
    )
    for index, (label, comparison) in enumerate(angle_series):
        axes[0, 1].bar(
            x + (index - 1) * 0.25,
            [comparison["errors"][key] for key in labels],
            width=0.25,
            label=label,
        )
    axes[0, 1].set_title("Angular-boundary treatment")
    axes[0, 1].legend(fontsize=7)
    depth_series = (
        ("Upwind 32 vs 64", comparisons["upwind_depth"]),
        ("Step 16 vs 32", comparisons["step_depth_candidate"]),
        ("Step 32 vs 64", comparisons["step_depth_confirmation"]),
    )
    for index, (label, comparison) in enumerate(depth_series):
        axes[1, 0].bar(
            x + (index - 1) * 0.25,
            [comparison["errors"][key] for key in labels],
            width=0.25,
            label=label,
        )
    axes[1, 0].set_title("Actual stress-state spatial convergence")
    axes[1, 0].legend(fontsize=7)
    colors = {
        "upwind_finite_volume": "tab:orange",
        "step_characteristics": "tab:blue",
    }
    for key, report in reports.items():
        axes[1, 1].scatter(
            report["radiation_unknown_count"],
            report["peak_process_rss_mib"],
            color=colors[report["spatial_scheme"]],
            s=42,
        )
        axes[1, 1].annotate(
            key.replace("upwind_split_", "U-").replace("step_split_", "SC-"),
            (report["radiation_unknown_count"], report["peak_process_rss_mib"]),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=6,
        )
    for axis in (axes[0, 1], axes[1, 0]):
        axis.axhline(target, color="black", linestyle=":")
        axis.set_yscale("log")
        axis.set_xticks(x, labels.values(), rotation=32, ha="right")
        axis.set_ylabel("Scale-normalized difference")
        axis.grid(alpha=0.2, axis="y")
    axes[0, 0].grid(alpha=0.2)
    axes[1, 1].set_xscale("log")
    axes[1, 1].set_xlabel("Active radiation unknowns")
    axes[1, 1].set_ylabel("Fresh-process peak RSS (MiB)")
    axes[1, 1].set_title("One-cell resource envelope")
    axes[1, 1].grid(alpha=0.2)
    figure.savefig(path, dpi=220)
    plt.close(figure)


def run_all(output_dir: Path, protocol_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5t_characteristic_transport_summary.json",
        "runs": output_dir / "phase7b5t_characteristic_transport_runs.csv",
        "comparisons": output_dir / "phase7b5t_characteristic_transport_errors.csv",
        "analytic": output_dir / "phase7b5t_analytic_spatial_convergence.csv",
        "figure": output_dir / "phase7b5t_characteristic_transport_gate.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    protocol = _load_protocol(protocol_path)
    input_path = ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]
    output_dir.mkdir(parents=True, exist_ok=True)
    analytic_rows = _linear_source_convergence()
    analytic_controls = _constant_source_and_moving_grid_controls()
    reports: dict[str, dict[str, object]] = {}
    spectra: dict[str, np.ndarray] = {}
    run_rows: list[dict[str, object]] = []
    active_edge: np.ndarray | None = None
    with tempfile.TemporaryDirectory(prefix="phase7b5t-") as temporary:
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
                    "--worker-spatial-scheme",
                    definition["spatial_scheme"],
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
                    f"Phase 7B5t worker {key} failed: {process.stderr.strip()}"
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
                raise RuntimeError("Phase 7B5t worker frequency edges diverged")
            for source, destination in (
                ("peak_process_rss_bytes", "peak_process_rss_mib"),
                ("baseline_highwater_rss_bytes", "baseline_highwater_rss_mib"),
                ("operator_highwater_increase_bytes", "operator_highwater_increase_mib"),
                ("returned_array_bytes", "returned_array_mib"),
            ):
                report[destination] = report.pop(source) / MIB_BYTES
            report["configuration_key"] = key
            reports[key] = report
            spectra[key] = spectrum
            run_rows.append(report)
    if active_edge is None:
        raise RuntimeError("Phase 7B5t produced no actual spectra")
    width = np.diff(active_edge)
    comparisons = {}
    for key, pair in protocol["comparisons"].items():
        comparisons[key] = _comparison(
            key, pair[0], pair[1], reports, spectra, width
        )
    previous = json.loads(
        (ROOT / protocol["sources"]["phase7b5s_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    previous_full = previous["comparisons"]["angle32_vs48"]
    target = protocol["gates"]["all_science_errors_strictly_below"]
    analytic_spec = protocol["analytic_controls"]
    orders = {
        row["spatial_scheme"]: [
            candidate["observed_order_to_next"]
            for candidate in analytic_rows
            if candidate["spatial_scheme"] == row["spatial_scheme"]
            and candidate["observed_order_to_next"] is not None
        ]
        for row in analytic_rows
    }
    required_comparisons = (
        "split_angle_upwind",
        "split_angle_step",
        "step_depth_candidate",
        "step_depth_confirmation",
        "joint_candidate",
    )
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
            < protocol["gates"]["global_coupled_residual_strictly_below"]
            for report in reports.values()
        ),
        "all_energy_ledger_residuals_passed": all(
            abs(report["total_energy_ledger_residual"])
            < protocol["gates"]["energy_ledger_residual_strictly_below"]
            for report in reports.values()
        ),
        "all_intensities_nonnegative": all(
            report["minimum_intensity"]
            >= protocol["gates"]["minimum_intensity_at_least"]
            for report in reports.values()
        ),
        "physical_group_count_exact": all(
            report["physical_group_count"]
            == protocol["gates"]["physical_group_count_exactly"]
            for report in reports.values()
        ),
        "edge_hash_unchanged": all(
            report["active_edge_sha256"]
            == protocol["frequency_representation"]["active_edge_sha256"]
            for report in reports.values()
        ),
        "resource_cap_passed": all(
            report["peak_process_rss_mib"]
            < protocol["gates"]["fresh_process_peak_rss_strictly_below_mib"]
            for report in reports.values()
        ),
        "characteristics_do_not_reverse_at_quadrature_nodes": all(
            report["minimum_quadrature_distance_from_ale_reversal"] > 0.0
            for report in reports.values()
        ),
        "upwind_analytic_order_passed": all(
            analytic_spec["upwind_expected_order_interval"][0]
            <= order
            <= analytic_spec["upwind_expected_order_interval"][1]
            for order in orders["upwind_finite_volume"]
        ),
        "step_analytic_order_passed": all(
            order > analytic_spec["step_expected_order_strictly_above"]
            for order in orders["step_characteristics"]
        ),
        "constant_source_analytic_passed": (
            analytic_controls["constant_source_maximum_absolute_error"]
            < analytic_spec["constant_source_maximum_error_strictly_below"]
        ),
        "moving_grid_ledger_passed": (
            analytic_controls["moving_grid_global_coupled_residual"]
            < analytic_spec["moving_grid_ledger_strictly_below"]
            and analytic_controls["moving_grid_energy_ledger_residual"]
            < analytic_spec["moving_grid_ledger_strictly_below"]
        ),
        "required_science_comparisons_passed": all(
            comparisons[key]["maximum_error"] < target
            for key in required_comparisons
        ),
        **protocol["authorization"],
    }
    required_decisions = tuple(
        key
        for key in decision
        if key.endswith("_passed")
        and key
        not in (
            "full_column_authorized",
            "full_orbit_authorized",
            "matter_feedback_authorized",
            "phase4_replacement_authorized",
            "uvot_authorized",
        )
    )
    gate_passed = all(decision[key] for key in required_decisions)
    decision["phase7b5t_gate_passed"] = gate_passed
    _write_csv(paths["runs"], run_rows)
    _write_csv(paths["comparisons"], _comparison_rows(comparisons))
    _write_csv(paths["analytic"], analytic_rows)
    _plot(
        paths["figure"],
        analytic_rows,
        previous_full,
        comparisons,
        reports,
        target,
    )
    summary = {
        "phase": "7B5t characteristic angular and spatial transport gate",
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_path": str(protocol_path),
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "stress_state": protocol["stress_state"],
        "frequency_representation": protocol["frequency_representation"],
        "angular_quadrature": protocol["angular_quadrature"],
        "analytic_spatial_convergence": analytic_rows,
        "analytic_controls": analytic_controls,
        "previous_full_range_angle_comparison": previous_full,
        "runs": reports,
        "comparisons": comparisons,
        "decision": decision,
        "accepted_one_cell_configuration": (
            protocol["candidate_if_all_gates_pass"] if gate_passed else None
        ),
        "interpretation": (
            "Characteristic-split angular quadrature and conservative step "
            "characteristics close the exposed one-cell angular, depth and joint "
            "gates. Full-column and orbit authorization remain closed."
            if gate_passed
            else "At least one preregistered characteristic transport gate failed. "
            "No one-cell production configuration is accepted."
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
                "accepted_one_cell_configuration": summary[
                    "accepted_one_cell_configuration"
                ],
            },
            indent=2,
        )
    )
    if not gate_passed:
        raise RuntimeError(
            "Phase 7B5t gate failed after preserving all diagnostic outputs"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            OUTPUT
            / "phase7b5t_preregistered_characteristic_transport_protocol.json"
        ),
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--worker-input", type=Path)
    parser.add_argument("--worker-spatial-scheme")
    parser.add_argument("--worker-angular-directions", type=int)
    parser.add_argument("--worker-radiation-subcells", type=int)
    parser.add_argument("--worker-output", type=Path)
    parser.add_argument("--worker-spectrum-output", type=Path)
    args = parser.parse_args()
    worker_arguments = (
        args.worker_input,
        args.worker_spatial_scheme,
        args.worker_angular_directions,
        args.worker_radiation_subcells,
        args.worker_output,
        args.worker_spectrum_output,
    )
    if any(value is not None for value in worker_arguments):
        if any(value is None for value in worker_arguments):
            raise ValueError("all Phase 7B5t worker arguments must be supplied")
        run_worker(*worker_arguments)
        return
    run_all(args.output_dir, args.protocol, force=args.force)


if __name__ == "__main__":
    main()
