"""汇总 Phase 7A 的静态环带可行性证据；不会把失败模型伪装成大气谱。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eccentric_tde_observer.annulus_bridge import zo_annulus_atmosphere_coordinates
from eccentric_tde_observer.phase7a import select_quasi_static_representative_annuli
from eccentric_tde_observer.reference_case import (
    STRICT_CIRCULARIZATION_EFFICIENCY,
    STRICT_ECCENTRICITY,
    build_strict_domain_reference_model,
)
from eccentric_tde_observer.tlusty import (
    parse_direct_annulus_input,
    parse_disk_scale_heights,
    parse_final_relative_change,
    parse_unit13,
)


CONVERGENCE_THRESHOLD = 1.0e-3
ENERGY_RESIDUAL_THRESHOLD = 1.0e-2


def _write_csv(path: Path, records: list[dict[str, object]]) -> None:
    if not records:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def _same(value: float, target: float) -> bool:
    return bool(np.isclose(value, target, rtol=2.0e-12, atol=0.0))


def _representative_records(selection, run_root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for representative in range(selection.count):
        grey_directory = run_root / "tlusty208_grey_diagnostics" / f"rep_{representative:02d}"
        direct_directory = run_root / "tlusty208_direct_lte_audit" / f"rep_{representative:02d}"
        grey_parameters = parse_direct_annulus_input(grey_directory / "annulus.5")
        direct_parameters = parse_direct_annulus_input(direct_directory / "annulus.5")
        expected = (
            selection.effective_temperature_k[representative],
            selection.gravity_coefficient_s2[representative],
            selection.midplane_column_mass_g_cm2[representative],
        )
        observed_grey = (
            grey_parameters.effective_temperature_k,
            grey_parameters.gravity_coefficient_s2,
            grey_parameters.midplane_column_mass_g_cm2,
        )
        observed_direct = (
            direct_parameters.effective_temperature_k,
            direct_parameters.gravity_coefficient_s2,
            direct_parameters.midplane_column_mass_g_cm2,
        )
        if not all(_same(value, target) for value, target in zip(observed_grey, expected, strict=True)):
            raise ArithmeticError(f"grey input does not match representative {representative}")
        if not all(_same(value, target) for value, target in zip(observed_direct, expected, strict=True)):
            raise ArithmeticError(f"direct LTE input does not match representative {representative}")

        scale_heights = parse_disk_scale_heights(grey_directory / "annulus.6")
        grey_spectrum = parse_unit13(
            grey_directory / "fort.13", grey_parameters.effective_temperature_k
        )
        final_iteration, maximum_change = parse_final_relative_change(
            direct_directory / "fort.9"
        )
        direct_spectrum_exists = (direct_directory / "fort.13").is_file()
        records.append(
            {
                "representative": representative,
                "radial_index": int(selection.radial_index[representative]),
                "anomaly_index": int(selection.anomaly_index[representative]),
                "semimajor_axis_cm": float(selection.semimajor_axis_cm[representative]),
                "eccentric_anomaly_rad": float(selection.eccentric_anomaly_rad[representative]),
                "effective_temperature_k": float(expected[0]),
                "midplane_column_mass_g_cm2": float(expected[2]),
                "gravity_coefficient_s2": float(expected[1]),
                "quasi_static_ratio": float(selection.quasi_static_ratio[representative]),
                "cluster_area_fraction": float(selection.cluster_area_fraction[representative]),
                "cluster_bolometric_fraction": float(selection.cluster_bolometric_fraction[representative]),
                "cluster_optical_fraction": float(selection.cluster_optical_fraction[representative]),
                "cluster_mixture_fraction": float(selection.cluster_mixture_fraction[representative]),
                "cluster_covering_radius": float(selection.cluster_covering_radius[representative]),
                "grey_radiation_to_gas_scale_height": scale_heights.radiation_to_gas_ratio,
                "grey_energy_residual": grey_spectrum.fractional_energy_residual,
                "grey_is_diagnostic_only": True,
                "direct_lte_final_iteration": final_iteration,
                "direct_lte_maximum_relative_change": maximum_change,
                "direct_lte_spectrum_exists": direct_spectrum_exists,
                "direct_lte_accepted": bool(
                    direct_spectrum_exists and maximum_change < CONVERGENCE_THRESHOLD
                ),
                "grey_evidence_path": str(grey_directory),
                "direct_lte_evidence_path": str(direct_directory),
            }
        )
    return records


def _continuation_records(
    run_root: Path,
    target_temperature_k: float,
    target_column_mass_g_cm2: float,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    input_paths = sorted(run_root.glob("tlusty208_rep03*/**/annulus.5"))
    input_paths.extend(sorted(run_root.glob("tlusty208_rep03*/annulus.5")))
    for input_path in sorted(set(input_paths)):
        directory = input_path.parent
        parameters = parse_direct_annulus_input(input_path)
        if not _same(parameters.effective_temperature_k, target_temperature_k):
            continue
        if not _same(parameters.midplane_column_mass_g_cm2, target_column_mass_g_cm2):
            continue
        iteration_path = directory / "fort.9"
        if not iteration_path.is_file():
            continue
        final_iteration, maximum_change = parse_final_relative_change(iteration_path)
        spectrum_path = directory / "fort.13"
        spectrum_exists = spectrum_path.is_file()
        energy_residual: float | None = None
        if spectrum_exists:
            energy_residual = parse_unit13(
                spectrum_path, parameters.effective_temperature_k
            ).fractional_energy_residual
        accepted = bool(
            spectrum_exists
            and maximum_change < CONVERGENCE_THRESHOLD
            and energy_residual is not None
            and abs(energy_residual) < ENERGY_RESIDUAL_THRESHOLD
        )
        records.append(
            {
                "evidence_path": str(directory),
                "gravity_coefficient_s2": parameters.gravity_coefficient_s2,
                "gravity_over_target": 0.0,
                "final_iteration": final_iteration,
                "maximum_relative_change": maximum_change,
                "spectrum_exists": spectrum_exists,
                "fractional_energy_residual": energy_residual if energy_residual is not None else "",
                "accepted": accepted,
            }
        )
    if not records:
        raise ValueError("no rep03 continuation evidence found")
    target_gravity = min(
        float(record["gravity_coefficient_s2"]) for record in records
    )
    for record in records:
        record["gravity_over_target"] = (
            float(record["gravity_coefficient_s2"]) / target_gravity
        )
    records.sort(key=lambda record: float(record["gravity_coefficient_s2"]), reverse=True)
    return records


def _benchmark_record(directory: Path) -> dict[str, object]:
    output_path = directory / ("output.6" if (directory / "output.6").is_file() else "d1lt.6")
    match = re.search(r"TEFF\s*=\s*([+\-0-9.DEde]+)", output_path.read_text())
    if match is None:
        raise ValueError(f"{output_path}: missing TEFF")
    temperature_k = float(match.group(1).replace("D", "E").replace("d", "e"))
    final_iteration, maximum_change = parse_final_relative_change(directory / "fort.9")
    spectrum = parse_unit13(directory / "fort.13", temperature_k)
    return {
        "evidence_path": str(directory),
        "effective_temperature_k": temperature_k,
        "final_iteration": final_iteration,
        "maximum_relative_change": maximum_change,
        "fractional_energy_residual": spectrum.fractional_energy_residual,
        "accepted": bool(
            maximum_change < CONVERGENCE_THRESHOLD
            and abs(spectrum.fractional_energy_residual) < ENERGY_RESIDUAL_THRESHOLD
        ),
    }


def _plot_audit(
    path: Path,
    model,
    selection,
    representative_records: list[dict[str, object]],
    continuation_records: list[dict[str, object]],
) -> None:
    coordinates = zo_annulus_atmosphere_coordinates(model)
    valid = coordinates.quasi_static_ratio < selection.quasi_static_threshold
    figure, axes = plt.subplots(2, 2, figsize=(13.2, 9.2), constrained_layout=True)

    scatter = axes[0, 0].scatter(
        np.log10(coordinates.effective_temperature_k[valid]),
        np.log10(coordinates.comoving_pressure_gravity_coefficient_s2[valid]),
        c=np.log10(coordinates.midplane_column_mass_g_cm2[valid]),
        s=5,
        alpha=0.22,
        linewidths=0,
        rasterized=True,
    )
    axes[0, 0].scatter(
        np.log10(selection.effective_temperature_k),
        np.log10(selection.gravity_coefficient_s2),
        c=np.log10(selection.midplane_column_mass_g_cm2),
        marker="*",
        s=125,
        edgecolors="black",
        linewidths=0.7,
    )
    axes[0, 0].set_xlabel(r"$\log_{10}(T_{\rm eff}/{\rm K})$")
    axes[0, 0].set_ylabel(r"$\log_{10}(Q/{\rm s}^{-2})$")
    axes[0, 0].set_title("(a) Strict quasi-static cells and 12 medoids")
    colorbar = figure.colorbar(scatter, ax=axes[0, 0])
    colorbar.set_label(r"$\log_{10}(m_0/{\rm g\,cm}^{-2})$")

    representative = np.arange(selection.count)
    width = 0.25
    axes[0, 1].bar(
        representative - width,
        selection.cluster_area_fraction,
        width,
        label="corrected area",
    )
    axes[0, 1].bar(
        representative,
        selection.cluster_bolometric_fraction,
        width,
        label="bolometric",
    )
    axes[0, 1].bar(
        representative + width,
        selection.cluster_optical_fraction,
        width,
        label="optical control",
    )
    axes[0, 1].set_xlabel("Representative index")
    axes[0, 1].set_ylabel("Fraction within strict subset")
    axes[0, 1].set_title("(b) Coverage carried by each representative")
    axes[0, 1].legend(frameon=False, fontsize=9)

    scale_ratio = np.asarray(
        [record["grey_radiation_to_gas_scale_height"] for record in representative_records]
    )
    maximum_change = np.asarray(
        [record["direct_lte_maximum_relative_change"] for record in representative_records]
    )
    axes[1, 0].plot(representative, scale_ratio, "o-", color="tab:blue", label="grey Hrad/Hgas")
    axes[1, 0].axhline(1.0, color="0.4", linestyle="--", linewidth=1)
    axes[1, 0].set_ylim(0.0, max(10.0, 1.1 * np.max(scale_ratio)))
    axes[1, 0].set_xlabel("Representative index")
    axes[1, 0].set_ylabel("Grey radiation/gas scale-height ratio", color="tab:blue")
    twin = axes[1, 0].twinx()
    twin.semilogy(representative, maximum_change, "s--", color="tab:red", label="direct LTE change")
    twin.axhline(CONVERGENCE_THRESHOLD, color="tab:red", linestyle=":", linewidth=1)
    twin.set_ylabel("Final maximum relative change", color="tab:red")
    axes[1, 0].set_title("(c) Radiation-pressure regime and direct failures")

    gravity_ratio = np.asarray(
        [record["gravity_over_target"] for record in continuation_records]
    )
    changes = np.asarray(
        [record["maximum_relative_change"] for record in continuation_records]
    )
    accepted = np.asarray([record["accepted"] for record in continuation_records], dtype=bool)
    axes[1, 1].loglog(
        gravity_ratio[accepted],
        changes[accepted],
        ".",
        color="tab:green",
        label="accepted restart",
    )
    axes[1, 1].loglog(
        gravity_ratio[~accepted],
        changes[~accepted],
        "x",
        color="tab:red",
        label="rejected/failed",
    )
    axes[1, 1].axhline(CONVERGENCE_THRESHOLD, color="0.3", linestyle="--", linewidth=1)
    axes[1, 1].axvline(1.0, color="0.3", linestyle=":", linewidth=1)
    axes[1, 1].set_xlabel(r"$Q/Q_{\rm target}$")
    axes[1, 1].set_ylabel("Final maximum relative change")
    axes[1, 1].set_title("(d) Representative 03 gravity continuation")
    axes[1, 1].legend(frameon=False, fontsize=9)

    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--benchmark-root", type=Path)
    parser.add_argument(
        "--build-manifest",
        type=Path,
        default=Path(".phase7a_tools/tlusty208_hhe/manifest.json"),
    )
    parser.add_argument("--radial-points", type=int, default=65)
    parser.add_argument("--anomaly-points", type=int, default=1024)
    arguments = parser.parse_args()

    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_root = (
        arguments.run_root.resolve()
        if arguments.run_root is not None
        else output_dir / "phase7a_tlusty_runs"
    )
    benchmark_root = (
        arguments.benchmark_root.resolve()
        if arguments.benchmark_root is not None
        else output_dir / "phase7a_tlusty208_rebuild_validation"
    )
    model = build_strict_domain_reference_model(
        arguments.radial_points, arguments.anomaly_points
    )
    selection = select_quasi_static_representative_annuli(model, count=12)
    representatives = _representative_records(selection, run_root)
    continuation = _continuation_records(
        run_root,
        float(selection.effective_temperature_k[3]),
        float(selection.midplane_column_mass_g_cm2[3]),
    )
    target_gravity = float(selection.gravity_coefficient_s2[3])
    for record in continuation:
        record["gravity_over_target"] = (
            float(record["gravity_coefficient_s2"]) / target_gravity
        )
    accepted_continuation = [record for record in continuation if record["accepted"]]
    if not accepted_continuation:
        raise ArithmeticError("rep03 continuation contains no accepted checkpoint")
    minimum_accepted = min(
        accepted_continuation,
        key=lambda record: float(record["gravity_coefficient_s2"]),
    )
    lower_rejections = [
        record
        for record in continuation
        if not record["accepted"]
        and float(record["gravity_coefficient_s2"])
        < float(minimum_accepted["gravity_coefficient_s2"])
    ]
    nearest_lower_rejection = (
        max(lower_rejections, key=lambda record: float(record["gravity_coefficient_s2"]))
        if lower_rejections
        else None
    )

    if arguments.benchmark_root is None:
        lte_benchmark_directory = benchmark_root / "lte_hhe_disk"
        nlte_benchmark_directory = benchmark_root / "nlte_hhe_continuum_disk"
    else:
        lte_benchmark_directory = benchmark_root / "disk_hhe"
        nlte_benchmark_directory = benchmark_root / "disk_hhe_nlte_continuum"
    lte_benchmark = _benchmark_record(lte_benchmark_directory)
    nlte_benchmark = _benchmark_record(nlte_benchmark_directory)
    rejected_setup_directory = (
        output_dir / "phase7a_tlusty208_rebuild_validation" / "lte_hhe"
    )
    rejected_validation_setups: list[dict[str, object]] = []
    if rejected_setup_directory.is_dir():
        output_path = rejected_setup_directory / "output.6"
        stderr_path = rejected_setup_directory / "stderr.txt"
        rejected_validation_setups.append(
            {
                "evidence_path": str(rejected_setup_directory),
                "reason": "unit 1 disk selector was omitted; run entered stellar-atmosphere mode",
                "spectrum_exists": (rejected_setup_directory / "fort.13").is_file(),
                "disk_model_marker_present": bool(
                    output_path.is_file()
                    and "FINAL DISK RING MODEL" in output_path.read_text()
                ),
                "fortran_stop_marker_present": bool(
                    stderr_path.is_file() and "STOP partf" in stderr_path.read_text()
                ),
                "accepted": False,
            }
        )
    build_manifest = json.loads(arguments.build_manifest.read_text())
    direct_accepted_count = sum(bool(record["direct_lte_accepted"]) for record in representatives)
    report = {
        "phase": "7A",
        "classification": "[L/A/V/O] static H/He annulus feasibility audit",
        "model": {
            "eccentricity": STRICT_ECCENTRICITY,
            "circularization_efficiency": STRICT_CIRCULARIZATION_EFFICIENCY,
            "radial_points": arguments.radial_points,
            "anomaly_points": arguments.anomaly_points,
            "corrected_area_is_sampling_measure": True,
        },
        "representative_selection": {
            "count": selection.count,
            "quasi_static_threshold": selection.quasi_static_threshold,
            "valid_cell_count": selection.valid_cell_count,
            "excluded_cell_count": selection.excluded_cell_count,
            "valid_corrected_area_fraction": selection.valid_area_fraction,
            "valid_bolometric_fraction": selection.valid_bolometric_fraction,
            "valid_optical_fraction": selection.valid_optical_fraction,
            "weighted_rms_distance": selection.weighted_rms_distance,
            "maximum_distance": selection.maximum_distance,
        },
        "solver_build": build_manifest,
        "official_solver_benchmarks": {
            "lte_h_he": lte_benchmark,
            "nlte_h_he_continuum_restart": nlte_benchmark,
        },
        "rejected_validation_setups": rejected_validation_setups,
        "actual_columns": {
            "grey_initialization_is_diagnostic_only": True,
            "radiation_to_gas_scale_height_range": [
                min(float(record["grey_radiation_to_gas_scale_height"]) for record in representatives),
                max(float(record["grey_radiation_to_gas_scale_height"]) for record in representatives),
            ],
            "direct_lte_attempts": len(representatives),
            "direct_lte_accepted": direct_accepted_count,
            "converged_actual_atmosphere_spectra": direct_accepted_count,
        },
        "representative_03_continuation": {
            "target_gravity_coefficient_s2": target_gravity,
            "minimum_accepted_gravity_coefficient_s2": float(
                minimum_accepted["gravity_coefficient_s2"]
            ),
            "minimum_accepted_gravity_over_target": float(
                minimum_accepted["gravity_coefficient_s2"]
            )
            / target_gravity,
            "minimum_accepted_evidence_path": minimum_accepted["evidence_path"],
            "nearest_lower_rejection": nearest_lower_rejection,
            "target_reached": bool(
                _same(
                    float(minimum_accepted["gravity_coefficient_s2"]),
                    target_gravity,
                )
            ),
        },
        "acceptance_thresholds": {
            "maximum_relative_change": CONVERGENCE_THRESHOLD,
            "absolute_fractional_energy_residual": ENERGY_RESIDUAL_THRESHOLD,
            "spectrum_file_required": True,
        },
        "comparison_status": {
            "blackbody_vs_modified_blackbody_vs_atmosphere": "blocked",
            "reason": (
                "zero actual representative columns produced an accepted atmosphere spectrum; "
                "grey initializations are not promoted to physical spectra"
            ),
        },
        "decision": (
            "[V] TLUSTY 208 and the LTE-to-NLTE restart path pass official H/He controls, "
            "but direct LTE solves fail for all 12 actual strict-subset representatives. "
            "[O] A different static solution may exist, yet the tested continuation does not "
            "reach the target gravity. Phase 7B is therefore not authorized."
        ),
    }

    _write_csv(output_dir / "phase7a_representative_annuli.csv", representatives)
    _write_csv(output_dir / "phase7a_rep03_continuation.csv", continuation)
    (output_dir / "phase7a_static_annulus_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    _plot_audit(
        output_dir / "phase7a_static_annulus_audit.png",
        model,
        selection,
        representatives,
        continuation,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
