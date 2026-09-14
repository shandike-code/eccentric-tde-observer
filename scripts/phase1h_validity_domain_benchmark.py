"""Map the local-column validity domain of the constant-e ZO source."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eccentric_tde_observer.faceon import face_on_bolometric_luminosities
from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.validity import audit_local_vertical_domain
from eccentric_tde_observer.vertical import (
    GAUSSIAN_VERTICAL_PROFILE,
    RADIATION_PRESSURE_POLYTROPE_PROFILE,
)
from eccentric_tde_observer.zo_reference import (
    ZOConstantEParameters,
    build_zo_constant_e_reference_model,
    rescale_constant_e_circularization_efficiency,
)


ECCENTRICITY_GRID = np.linspace(0.0, 0.9, 19)
CIRCULARIZATION_GRID = np.geomspace(1.0e-2, 1.0e1, 37)
RATIO_THRESHOLDS = np.array([0.1, 0.3, 1.0, 2.0])
PROFILE_SPECS = (
    ("gaussian", GAUSSIAN_VERTICAL_PROFILE),
    ("polytrope_n3", RADIATION_PRESSURE_POLYTROPE_PROFILE),
)
CLUSTERING_POWER = 5.0
STRICT_MAX_FAILURE_FRACTION = 0.01
LITERATURE_EFFICIENCY_MIN = 0.1
LITERATURE_EFFICIENCY_MAX = 10.0


def _parameters(eccentricity: float) -> ZOConstantEParameters:
    return ZOConstantEParameters(
        black_hole_mass_msun=1.0e6,
        stellar_mass_msun=1.0,
        stellar_radius_rsun=1.0,
        circularization_efficiency=1.0,
        outer_to_inner_semimajor_axis=2.0,
        eccentricity=eccentricity,
        opacity_cm2_g=0.34,
    )


def _base_model(eccentricity: float, radial_points: int, anomaly_points: int):
    return build_zo_constant_e_reference_model(
        _parameters(eccentricity),
        radial_points=radial_points,
        anomaly_points=anomaly_points,
        anomaly_sampling="pericentre_clustered",
        pericentre_clustering_power=CLUSTERING_POWER,
    )


def _metric_arrays() -> dict[str, np.ndarray]:
    profile_shape = (
        len(PROFILE_SPECS),
        ECCENTRICITY_GRID.size,
        CIRCULARIZATION_GRID.size,
    )
    source_shape = (ECCENTRICITY_GRID.size, CIRCULARIZATION_GRID.size)
    return {
        "z_fraction_ge_0p3": np.empty(profile_shape),
        "z_fraction_ge_1": np.empty(profile_shape),
        "surface_area_ratio": np.empty(profile_shape),
        "steep_area_fraction": np.empty(profile_shape),
        "h_fraction_ge_0p3": np.empty(source_shape),
        "lbol_iso_erg_s": np.empty(source_shape),
        "temperature_max_k": np.empty(source_shape),
        "minimum_total_optical_depth": np.empty(source_shape),
    }


def _write_records(path: Path, records: list[dict[str, object]]) -> None:
    if not records:
        raise RuntimeError("validity scan produced no records")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def _scan(radial_points: int, anomaly_points: int):
    arrays = _metric_arrays()
    records: list[dict[str, object]] = []
    threshold_index = {
        float(threshold): index
        for index, threshold in enumerate(RATIO_THRESHOLDS)
    }
    for eccentricity_index, eccentricity in enumerate(ECCENTRICITY_GRID):
        base = _base_model(float(eccentricity), radial_points, anomaly_points)
        for efficiency_index, efficiency in enumerate(CIRCULARIZATION_GRID):
            model = rescale_constant_e_circularization_efficiency(
                base, float(efficiency)
            )
            lbol_iso, _ = face_on_bolometric_luminosities(model.source)
            arrays["lbol_iso_erg_s"][eccentricity_index, efficiency_index] = (
                lbol_iso
            )
            arrays["temperature_max_k"][eccentricity_index, efficiency_index] = (
                np.max(model.source.effective_temperature_k)
            )
            for profile_index, (profile_key, profile) in enumerate(PROFILE_SPECS):
                photosphere = solve_gray_photosphere(
                    model.source,
                    model.parameters.opacity_cm2_g,
                    2.0 / 3.0,
                    profile,
                )
                audit = audit_local_vertical_domain(
                    model.source, photosphere, RATIO_THRESHOLDS
                )
                if profile_index == 0:
                    arrays["h_fraction_ge_0p3"][
                        eccentricity_index, efficiency_index
                    ] = audit.corrected_h_over_radius_fraction_above[
                        threshold_index[0.3]
                    ]
                    arrays["minimum_total_optical_depth"][
                        eccentricity_index, efficiency_index
                    ] = audit.minimum_total_vertical_optical_depth
                z_fraction_ge_0p3 = (
                    audit.corrected_photosphere_over_radius_fraction_above[
                        threshold_index[0.3]
                    ]
                )
                z_fraction_ge_1 = (
                    audit.corrected_photosphere_over_radius_fraction_above[
                        threshold_index[1.0]
                    ]
                )
                arrays["z_fraction_ge_0p3"][
                    profile_index, eccentricity_index, efficiency_index
                ] = z_fraction_ge_0p3
                arrays["z_fraction_ge_1"][
                    profile_index, eccentricity_index, efficiency_index
                ] = z_fraction_ge_1
                arrays["surface_area_ratio"][
                    profile_index, eccentricity_index, efficiency_index
                ] = audit.surface_area_to_projected_mesh_area
                arrays["steep_area_fraction"][
                    profile_index, eccentricity_index, efficiency_index
                ] = audit.projected_area_fraction_with_surface_slope_ge_1

                record: dict[str, object] = {
                    "eccentricity": float(eccentricity),
                    "circularization_efficiency": float(efficiency),
                    "closure": profile_key,
                    "inner_semimajor_axis_cm": model.inner_semimajor_axis_cm,
                    "circular_scale_height_aspect_ratio": (
                        model.circular_scale_height_aspect_ratio
                    ),
                    "temperature_min_k": float(
                        np.min(model.source.effective_temperature_k)
                    ),
                    "temperature_max_k": float(
                        np.max(model.source.effective_temperature_k)
                    ),
                    "corrected_lbol_iso_erg_s": lbol_iso,
                    "minimum_total_vertical_optical_depth": (
                        audit.minimum_total_vertical_optical_depth
                    ),
                    "h_over_radius_min": audit.h_over_radius_min_max[0],
                    "h_over_radius_max": audit.h_over_radius_min_max[1],
                    "zph_over_radius_min": (
                        audit.photosphere_over_radius_min_max[0]
                    ),
                    "zph_over_radius_max": (
                        audit.photosphere_over_radius_min_max[1]
                    ),
                    "corrected_mean_h_over_radius": audit.corrected_mean_h_over_radius,
                    "corrected_mean_zph_over_radius": (
                        audit.corrected_mean_photosphere_over_radius
                    ),
                    "surface_area_to_projected_mesh_area": (
                        audit.surface_area_to_projected_mesh_area
                    ),
                    "projected_mesh_to_cartesian_quadrature_area": (
                        audit.projected_mesh_to_cartesian_quadrature_area
                    ),
                    "projected_area_fraction_surface_slope_ge_1": (
                        audit.projected_area_fraction_with_surface_slope_ge_1
                    ),
                    "maximum_surface_slope": audit.maximum_surface_slope,
                    "minimum_face_normal_z": audit.minimum_face_normal_z,
                    "oriented_single_valued_surface_graph": int(
                        audit.oriented_single_valued_surface_graph
                    ),
                }
                for threshold, h_corrected, z_corrected, h_cartesian, z_cartesian in zip(
                    audit.ratio_thresholds,
                    audit.corrected_h_over_radius_fraction_above,
                    audit.corrected_photosphere_over_radius_fraction_above,
                    audit.cartesian_h_over_radius_fraction_above,
                    audit.cartesian_photosphere_over_radius_fraction_above,
                    strict=True,
                ):
                    label = str(float(threshold)).replace(".", "p")
                    record[f"corrected_area_fraction_H_over_r_ge_{label}"] = float(
                        h_corrected
                    )
                    record[f"corrected_area_fraction_zph_over_r_ge_{label}"] = float(
                        z_corrected
                    )
                    record[f"cartesian_area_fraction_H_over_r_ge_{label}"] = (
                        float(h_cartesian)
                    )
                    record[
                        f"cartesian_area_fraction_zph_over_r_ge_{label}"
                    ] = float(z_cartesian)
                records.append(record)
        print(
            f"e={eccentricity:.2f} completed on "
            f"{radial_points}x{anomaly_points}",
            flush=True,
        )
    for name, values in arrays.items():
        if not np.all(np.isfinite(values)):
            raise RuntimeError(f"scan metric {name} contains a non-finite value")
    return arrays, records


def _selected_grid_convergence(
    fine_arrays: dict[str, np.ndarray],
) -> tuple[list[dict[str, object]], dict[str, float]]:
    selected = (
        (0.0, 0.01),
        (0.0, 0.1),
        (0.4, 0.1),
        (0.8, 0.01),
        (0.8, 0.1),
        (0.8, 1.0),
        (0.9, 10.0),
    )
    records: list[dict[str, object]] = []
    maximum_fraction_change = 0.0
    maximum_surface_ratio_change = 0.0
    maximum_projected_area_error = 0.0
    bases: dict[float, object] = {}
    for eccentricity, efficiency in selected:
        if eccentricity not in bases:
            bases[eccentricity] = _base_model(eccentricity, 129, 2048)
        model = rescale_constant_e_circularization_efficiency(
            bases[eccentricity], efficiency
        )
        eccentricity_index = int(
            np.flatnonzero(np.isclose(ECCENTRICITY_GRID, eccentricity))[0]
        )
        efficiency_index = int(
            np.flatnonzero(np.isclose(CIRCULARIZATION_GRID, efficiency))[0]
        )
        for profile_index, (profile_key, profile) in enumerate(PROFILE_SPECS):
            photosphere = solve_gray_photosphere(
                model.source,
                model.parameters.opacity_cm2_g,
                2.0 / 3.0,
                profile,
            )
            audit = audit_local_vertical_domain(
                model.source, photosphere, RATIO_THRESHOLDS
            )
            reference_fraction_0p3 = float(
                audit.corrected_photosphere_over_radius_fraction_above[1]
            )
            reference_fraction_1 = float(
                audit.corrected_photosphere_over_radius_fraction_above[2]
            )
            fine_fraction_0p3 = fine_arrays["z_fraction_ge_0p3"][
                profile_index, eccentricity_index, efficiency_index
            ]
            fine_fraction_1 = fine_arrays["z_fraction_ge_1"][
                profile_index, eccentricity_index, efficiency_index
            ]
            fraction_change_0p3 = abs(
                reference_fraction_0p3 - fine_fraction_0p3
            )
            fraction_change_1 = abs(reference_fraction_1 - fine_fraction_1)
            fine_surface_ratio = fine_arrays["surface_area_ratio"][
                profile_index, eccentricity_index, efficiency_index
            ]
            surface_ratio_change = abs(
                audit.surface_area_to_projected_mesh_area / fine_surface_ratio
                - 1.0
            )
            projected_area_error = abs(
                audit.projected_mesh_to_cartesian_quadrature_area - 1.0
            )
            maximum_fraction_change = max(
                maximum_fraction_change,
                fraction_change_0p3,
                fraction_change_1,
            )
            maximum_surface_ratio_change = max(
                maximum_surface_ratio_change, surface_ratio_change
            )
            maximum_projected_area_error = max(
                maximum_projected_area_error, projected_area_error
            )
            records.append(
                {
                    "eccentricity": eccentricity,
                    "circularization_efficiency": efficiency,
                    "closure": profile_key,
                    "fine_65x1024_fraction_zph_ge_0p3": fine_fraction_0p3,
                    "reference_129x2048_fraction_zph_ge_0p3": (
                        reference_fraction_0p3
                    ),
                    "absolute_change_fraction_zph_ge_0p3": (
                        fraction_change_0p3
                    ),
                    "fine_65x1024_fraction_zph_ge_1": fine_fraction_1,
                    "reference_129x2048_fraction_zph_ge_1": (
                        reference_fraction_1
                    ),
                    "absolute_change_fraction_zph_ge_1": fraction_change_1,
                    "fine_65x1024_surface_area_ratio": fine_surface_ratio,
                    "reference_129x2048_surface_area_ratio": (
                        audit.surface_area_to_projected_mesh_area
                    ),
                    "fractional_change_surface_area_ratio": surface_ratio_change,
                    "reference_projected_mesh_to_quadrature_area": (
                        audit.projected_mesh_to_cartesian_quadrature_area
                    ),
                }
            )
    summary = {
        "maximum_absolute_area_fraction_change": maximum_fraction_change,
        "maximum_fractional_surface_area_ratio_change": (
            maximum_surface_ratio_change
        ),
        "maximum_reference_projected_area_fractional_error": (
            maximum_projected_area_error
        ),
    }
    return records, summary


def _plot_domain(arrays: dict[str, np.ndarray], output_path: Path) -> None:
    gaussian_0p3 = arrays["z_fraction_ge_0p3"][0]
    polytrope_0p3 = arrays["z_fraction_ge_0p3"][1]
    gaussian_1 = arrays["z_fraction_ge_1"][0]
    polytrope_1 = arrays["z_fraction_ge_1"][1]
    panels = (
        (gaussian_0p3, r"Gaussian: corrected area with $z_{ph}/r\geq0.3$", "viridis", 0.0, 1.0),
        (polytrope_0p3, r"$n=3$: corrected area with $z_{ph}/r\geq0.3$", "viridis", 0.0, 1.0),
        (polytrope_0p3 - gaussian_0p3, r"$n=3$ minus Gaussian", "coolwarm", -0.25, 0.25),
        (gaussian_1, r"Gaussian: corrected area with $z_{ph}/r\geq1$", "viridis", 0.0, 1.0),
        (polytrope_1, r"$n=3$: corrected area with $z_{ph}/r\geq1$", "viridis", 0.0, 1.0),
        (arrays["h_fraction_ge_0p3"], r"ZO source: corrected area with $H/r\geq0.3$", "viridis", 0.0, 1.0),
    )
    figure, axes = plt.subplots(2, 3, figsize=(16.2, 9.5), constrained_layout=True)
    figure.suptitle(
        "Phase 1H: local-column validity domain of the constant-e ZO source",
        fontsize=16,
    )
    for axis, (values, title, cmap, vmin, vmax) in zip(
        axes.flat, panels, strict=True
    ):
        image = axis.pcolormesh(
            ECCENTRICITY_GRID,
            CIRCULARIZATION_GRID,
            values.T,
            shading="nearest",
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
        )
        axis.set_yscale("log")
        axis.axhline(
            LITERATURE_EFFICIENCY_MIN,
            color="white",
            linestyle="--",
            linewidth=1.2,
        )
        axis.text(
            0.01,
            0.115,
            r"ZO expected $\mathcal{V}\geq0.1$",
            color="white",
            fontsize=8,
            transform=axis.get_yaxis_transform(),
        )
        if np.min(values) <= STRICT_MAX_FAILURE_FRACTION <= np.max(values):
            axis.contour(
                ECCENTRICITY_GRID,
                CIRCULARIZATION_GRID,
                values.T,
                levels=[STRICT_MAX_FAILURE_FRACTION],
                colors="black",
                linewidths=1.2,
            )
        axis.set_title(title)
        axis.set_xlabel("constant eccentricity e")
        axis.set_ylabel(r"circularization efficiency $\mathcal{V}$")
        figure.colorbar(image, ax=axis, pad=0.01)
    figure.savefig(output_path, dpi=180)
    plt.close(figure)


def _plot_source_scalings(arrays: dict[str, np.ndarray], output_path: Path) -> None:
    panels = (
        (np.log10(arrays["lbol_iso_erg_s"]), r"$\log_{10} L_{bol,iso}^{corrected ZO}$ [erg s$^{-1}$]", "magma"),
        (np.log10(arrays["temperature_max_k"]), r"$\log_{10} T_{eff,max}$ [K]", "inferno"),
        (np.log10(arrays["minimum_total_optical_depth"]), r"$\log_{10}\min(\kappa\Sigma)$", "cividis"),
        (arrays["surface_area_ratio"][1], r"$n=3$ surface area / projected area", "plasma"),
    )
    figure, axes = plt.subplots(2, 2, figsize=(11.5, 9.3), constrained_layout=True)
    figure.suptitle("Phase 1H: source scalings and explicit-surface geometry", fontsize=16)
    for axis, (values, title, cmap) in zip(axes.flat, panels, strict=True):
        image = axis.pcolormesh(
            ECCENTRICITY_GRID,
            CIRCULARIZATION_GRID,
            values.T,
            shading="nearest",
            cmap=cmap,
        )
        axis.set_yscale("log")
        axis.axhline(0.1, color="white", linestyle="--", linewidth=1.2)
        axis.set_title(title)
        axis.set_xlabel("constant eccentricity e")
        axis.set_ylabel(r"circularization efficiency $\mathcal{V}$")
        figure.colorbar(image, ax=axis, pad=0.01)
    figure.savefig(output_path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    arrays, records = _scan(65, 1024)
    _write_records(args.output_dir / "phase1h_validity_domain.csv", records)
    convergence_records, convergence_summary = _selected_grid_convergence(arrays)
    _write_records(
        args.output_dir / "phase1h_validity_grid_convergence.csv",
        convergence_records,
    )
    _plot_domain(arrays, args.output_dir / "phase1h_validity_domain.png")
    _plot_source_scalings(
        arrays, args.output_dir / "phase1h_source_scalings.png"
    )

    literature_mask = CIRCULARIZATION_GRID >= LITERATURE_EFFICIENCY_MIN
    strict_pass = arrays["z_fraction_ge_0p3"] <= STRICT_MAX_FAILURE_FRACTION
    necessary_pass = arrays["z_fraction_ge_1"] <= STRICT_MAX_FAILURE_FRACTION
    both_strict = np.all(strict_pass, axis=0)
    both_necessary = np.all(necessary_pass, axis=0)

    maximum_strict_efficiency_by_e: dict[str, float | None] = {}
    maximum_necessary_efficiency_by_e: dict[str, float | None] = {}
    for eccentricity_index, eccentricity in enumerate(ECCENTRICITY_GRID):
        strict_values = CIRCULARIZATION_GRID[both_strict[eccentricity_index]]
        necessary_values = CIRCULARIZATION_GRID[
            both_necessary[eccentricity_index]
        ]
        maximum_strict_efficiency_by_e[f"{eccentricity:.2f}"] = (
            float(strict_values[-1]) if strict_values.size else None
        )
        maximum_necessary_efficiency_by_e[f"{eccentricity:.2f}"] = (
            float(necessary_values[-1]) if necessary_values.size else None
        )

    report = {
        "classification": (
            "ZO source parameter-domain audit [L/V]; local-column thresholds "
            "are explicit working criteria [A-domain]"
        ),
        "fixed_parameters": {
            "black_hole_mass_msun": 1.0e6,
            "stellar_mass_msun": 1.0,
            "stellar_radius_rsun": 1.0,
            "outer_to_inner_semimajor_axis": 2.0,
            "opacity_cm2_g": 0.34,
        },
        "scan": {
            "eccentricity": ECCENTRICITY_GRID.tolist(),
            "circularization_efficiency": CIRCULARIZATION_GRID.tolist(),
            "source_grid": [65, 1024],
            "anomaly_sampling": "pericentre clustered",
            "clustering_power": CLUSTERING_POWER,
            "profiles": [key for key, _ in PROFILE_SPECS],
        },
        "literature_scope": {
            "source": "ZO 2020 Section 2.2",
            "expected_circularization_efficiency_range": [
                LITERATURE_EFFICIENCY_MIN,
                LITERATURE_EFFICIENCY_MAX,
            ],
            "below_0p1_included_only_to_locate_validity_boundary": True,
        },
        "working_criteria": {
            "strict_thin_column": (
                "both closures have <=1% corrected ZO area with z_ph/r >= 0.3"
            ),
            "necessary_not_sufficient": (
                "both closures have <=1% corrected ZO area with z_ph/r >= 1"
            ),
            "thresholds_are_literature_theorems": False,
        },
        "domain_counts": {
            "grid_points": int(both_strict.size),
            "strict_both_closures": int(np.count_nonzero(both_strict)),
            "strict_both_closures_in_expected_V_range": int(
                np.count_nonzero(both_strict[:, literature_mask])
            ),
            "necessary_both_closures": int(
                np.count_nonzero(both_necessary)
            ),
            "necessary_both_closures_in_expected_V_range": int(
                np.count_nonzero(both_necessary[:, literature_mask])
            ),
        },
        "maximum_V_passing_strict_both_closures_by_e": (
            maximum_strict_efficiency_by_e
        ),
        "maximum_V_passing_necessary_both_closures_by_e": (
            maximum_necessary_efficiency_by_e
        ),
        "selected_grid_convergence": convergence_summary,
        "all_scan_values_finite": True,
        "all_triangulated_surfaces_oriented_single_valued_graphs": bool(
            all(
                int(record["oriented_single_valued_surface_graph"]) == 1
                for record in records
            )
        ),
        "disc_wind_applied": False,
        "frequency_shift_applied": False,
        "wall_time_seconds": time.perf_counter() - start,
    }
    (args.output_dir / "phase1h_validity_domain_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["domain_counts"], indent=2), flush=True)


if __name__ == "__main__":
    main()
