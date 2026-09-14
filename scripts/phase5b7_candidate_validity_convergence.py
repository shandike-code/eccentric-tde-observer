"""Phase 5B7：方程自洽候选源的有效域收敛门。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.source import ZOSourceGrid
from eccentric_tde_observer.validity import audit_local_vertical_domain
from eccentric_tde_observer.vertical import (
    GAUSSIAN_VERTICAL_PROFILE,
    RADIATION_PRESSURE_POLYTROPE_PROFILE,
)
from eccentric_tde_observer.zo_candidate_source import (
    ZOCandidateSourceParameters,
    build_zo_equation_self_consistent_candidate_source,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
WORKING_FAILURE_FRACTION = 0.01
RADIAL_RESOLUTIONS = (33, 65, 129, 256)
ANOMALY_RESOLUTIONS = (64, 128, 256, 512)
EXPECTED_DYNAMICS_FINGERPRINTS = {
    "atlas_reference": (
        "5e720e5503e9c85590c4533d01382de6bf03e7b449e6f0502b667580bfb75e76"
    ),
    "strict_boundary_sensitivity": (
        "d3b21496e07fb68626ad9f24e7fbd7a105631c7433c8adfb3889abff4a2c59ad"
    ),
}
PROFILES = (
    ("gaussian", GAUSSIAN_VERTICAL_PROFILE),
    ("polytrope_n3", RADIATION_PRESSURE_POLYTROPE_PROFILE),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def source_entry(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def native_radial_indices(total_points: int, requested_points: int) -> np.ndarray:
    """Select original frozen-profile nodes without radial interpolation."""
    if requested_points < 2 or requested_points > total_points:
        raise ValueError("requested radial resolution is outside the native grid")
    indices = np.rint(
        np.linspace(0.0, total_points - 1.0, requested_points)
    ).astype(np.int64)
    if (
        indices.size != requested_points
        or np.unique(indices).size != requested_points
        or indices[0] != 0
        or indices[-1] != total_points - 1
    ):
        raise RuntimeError("native radial subsample is not unique and endpoint-complete")
    return indices


def subsample_radial_source(
    source: ZOSourceGrid, indices: np.ndarray, *, label: str
) -> ZOSourceGrid:
    """Return an exact-node convergence source; this is not a new candidate."""
    return ZOSourceGrid(
        semimajor_axis_cm=source.semimajor_axis_cm[indices],
        eccentric_anomaly_rad=source.eccentric_anomaly_rad,
        eccentricity=source.eccentricity[indices],
        jacobian=source.jacobian[indices],
        surface_density_g_cm2=source.surface_density_g_cm2[indices],
        scale_height_cm=source.scale_height_cm[indices],
        effective_temperature_k=source.effective_temperature_k[indices],
        apsidal_angle_rad=source.apsidal_angle_rad,
        eccentricity_gradient_per_cm=(
            source.eccentricity_gradient_per_cm[indices]
        ),
        apsidal_gradient_per_cm=source.apsidal_gradient_per_cm[indices],
        label=f"[A-convergence] {label}",
        provenance=(
            "Exact native-node subset of one frozen Phase 5B6 candidate; "
            "quadrature/mesh convergence diagnostic only, no interpolation [V]"
        ),
    )


def _metric_row(
    *,
    case: str,
    scan_axis: str,
    source: ZOSourceGrid,
    closure_name: str,
    closure,
    circular_aspect_ratio: float,
) -> dict[str, object]:
    photosphere = solve_gray_photosphere(source, 0.34, 2.0 / 3.0, closure)
    audit = audit_local_vertical_domain(
        source, photosphere, ratio_thresholds=(0.3, 1.0)
    )
    dimensionless_height = source.scale_height_cm / (
        source.semimajor_axis_cm[:, None] * circular_aspect_ratio
    )
    anomaly_points = source.eccentric_anomaly_rad.size
    return {
        "case": case,
        "scan_axis": scan_axis,
        "closure": closure_name,
        "radial_points": source.semimajor_axis_cm.size,
        "anomaly_points": anomaly_points,
        "surface_triangle_count": 2
        * (source.semimajor_axis_cm.size - 1)
        * anomaly_points,
        "uniform_anomaly_spacing_rad": 2.0 * np.pi / anomaly_points,
        "pericentre_cells_within_abs_E_le_0p2": int(
            np.count_nonzero(
                np.minimum(
                    source.eccentric_anomaly_rad,
                    2.0 * np.pi - source.eccentric_anomaly_rad,
                )
                <= 0.2
            )
        ),
        "corrected_area_fraction_zph_over_r_ge_0p3": float(
            audit.corrected_photosphere_over_radius_fraction_above[0]
        ),
        "corrected_area_fraction_zph_over_r_ge_1p0": float(
            audit.corrected_photosphere_over_radius_fraction_above[1]
        ),
        "minimum_total_vertical_optical_depth": (
            audit.minimum_total_vertical_optical_depth
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
        "jacobian_min": float(np.min(source.jacobian)),
        "jacobian_max": float(np.max(source.jacobian)),
        "dimensionless_height_min": float(np.min(dimensionless_height)),
        "dimensionless_height_max": float(np.max(dimensionless_height)),
        "working_fraction_gate_passed": bool(
            audit.corrected_photosphere_over_radius_fraction_above[0]
            <= WORKING_FAILURE_FRACTION
        ),
    }


def _absolute_or_relative_change(
    coarse: dict[str, object], fine: dict[str, object], metric: str
) -> dict[str, object]:
    coarse_value = float(coarse[metric])
    fine_value = float(fine[metric])
    absolute = abs(fine_value - coarse_value)
    scale = max(abs(fine_value), abs(coarse_value))
    relative = absolute / scale if scale > 0.0 else 0.0
    return {
        "metric": metric,
        "coarse": coarse_value,
        "fine": fine_value,
        "absolute_change": absolute,
        "relative_change": relative,
    }


def _last_pair_changes(
    rows: list[dict[str, object]], case: str, scan_axis: str, closure: str
) -> list[dict[str, object]]:
    selected = [
        row
        for row in rows
        if row["case"] == case
        and row["scan_axis"] == scan_axis
        and row["closure"] == closure
    ]
    resolution_key = "radial_points" if scan_axis == "radial" else "anomaly_points"
    selected.sort(key=lambda row: int(row[resolution_key]))
    if len(selected) < 2:
        raise RuntimeError("convergence axis needs at least two resolutions")
    coarse, fine = selected[-2:]
    metrics = (
        "corrected_area_fraction_zph_over_r_ge_0p3",
        "corrected_area_fraction_zph_over_r_ge_1p0",
        "minimum_total_vertical_optical_depth",
        "surface_area_to_projected_mesh_area",
        "projected_mesh_to_cartesian_quadrature_area",
        "projected_area_fraction_surface_slope_ge_1",
        "maximum_surface_slope",
        "jacobian_min",
        "jacobian_max",
        "dimensionless_height_min",
        "dimensionless_height_max",
    )
    return [
        {
            "case": case,
            "scan_axis": scan_axis,
            "closure": closure,
            "coarse_resolution": int(coarse[resolution_key]),
            "fine_resolution": int(fine[resolution_key]),
            **_absolute_or_relative_change(coarse, fine, metric),
        }
        for metric in metrics
    ]


def _plot(rows: list[dict[str, object]], output_path: Path) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(11.5, 8.2), constrained_layout=True)
    colors = {
        "atlas_reference": "tab:blue",
        "strict_boundary_sensitivity": "tab:orange",
    }
    markers = {"gaussian": "o", "polytrope_n3": "s"}
    for case in colors:
        for closure in markers:
            for scan_axis, linestyle in (("radial", "-"), ("anomaly_surface", "--")):
                selected = [
                    row
                    for row in rows
                    if row["case"] == case
                    and row["closure"] == closure
                    and row["scan_axis"] == scan_axis
                ]
                key = "radial_points" if scan_axis == "radial" else "anomaly_points"
                selected.sort(key=lambda row: int(row[key]))
                x = [int(row[key]) for row in selected]
                label = (
                    case.replace("_", " ")
                    + ", "
                    + closure.replace("_", " ")
                    + ", "
                    + ("radial" if scan_axis == "radial" else "anomaly/mesh")
                )
                axes[0, 0].plot(
                    x,
                    [row["corrected_area_fraction_zph_over_r_ge_0p3"] for row in selected],
                    color=colors[case],
                    marker=markers[closure],
                    ls=linestyle,
                    label=label,
                )
                axes[0, 1].plot(
                    x,
                    [row["surface_area_to_projected_mesh_area"] for row in selected],
                    color=colors[case],
                    marker=markers[closure],
                    ls=linestyle,
                )
                axes[1, 0].plot(
                    x,
                    [row["minimum_total_vertical_optical_depth"] for row in selected],
                    color=colors[case],
                    marker=markers[closure],
                    ls=linestyle,
                )
                axes[1, 1].plot(
                    x,
                    [row["maximum_surface_slope"] for row in selected],
                    color=colors[case],
                    marker=markers[closure],
                    ls=linestyle,
                )
    axes[0, 0].axhline(
        WORKING_FAILURE_FRACTION,
        color="black",
        lw=1.0,
        ls=":",
        label="1% working threshold",
    )
    axes[0, 0].set(
        xlabel="Resolution points",
        ylabel="Corrected area fraction",
        title="(a) z_ph / r >= 0.3",
    )
    axes[0, 0].legend(frameon=False, fontsize=6, ncol=2)
    axes[0, 1].set(
        xlabel="Resolution points",
        ylabel="Surface / projected area",
        title="(b) Triangular surface geometry",
    )
    axes[1, 0].set(
        xlabel="Resolution points",
        ylabel="Minimum optical depth",
        title="(c) Vertical optical-depth floor",
    )
    axes[1, 1].set(
        xlabel="Resolution points",
        ylabel="Maximum surface slope",
        title="(d) Photosphere slope",
    )
    for axis in axes.flat:
        axis.set_xscale("log", base=2)
    figure.savefig(output_path, dpi=180)
    plt.close(figure)


def run() -> dict[str, object]:
    phase5b4_path = OUTPUT / "phase5b4_strict_domain_candidate_timescale_report.json"
    profile_path = OUTPUT / "phase5b4_candidate_mode_profiles.csv"
    phase5b5_path = OUTPUT / "phase5b5_mode_matched_time_axis_summary.json"
    phase5b6_path = OUTPUT / "phase5b6_candidate_source_report.json"
    phase5b4 = json.loads(phase5b4_path.read_text(encoding="utf-8"))
    phase5b5 = json.loads(phase5b5_path.read_text(encoding="utf-8"))
    phase5b6 = json.loads(phase5b6_path.read_text(encoding="utf-8"))
    if (
        phase5b4["high_e_equation_internal_gate"] is not True
        or phase5b6["authorization"][
            "candidate_source_rebuild_authorized_by_user"
        ]
        is not True
        or phase5b6["authorization"]["published_benchmark_claim"] is not False
    ):
        raise RuntimeError("candidate source authorization or lineage is not closed")
    expected_e_fingerprints = {
        row["case"]: row["eigenmode_profile_fingerprint"]
        for row in phase5b5["case_results"]
    }
    profile_rows = load_csv(profile_path)
    parameters = ZOCandidateSourceParameters(
        black_hole_mass_msun=1.0e6,
        stellar_mass_msun=1.0,
        stellar_radius_rsun=1.0,
        circularization_efficiency=0.01,
        opacity_cm2_g=0.34,
    )
    rows: list[dict[str, object]] = []
    for case in EXPECTED_DYNAMICS_FINGERPRINTS:
        selected = [row for row in profile_rows if row["case"] == case]
        scaled_a = np.array(
            [float(row["scaled_semimajor_axis"]) for row in selected]
        )
        eccentricity = np.array([float(row["eccentricity"]) for row in selected])
        nonlinearity = np.array(
            [float(row["orbital_nonlinearity"]) for row in selected]
        )
        finest_model = None
        for anomaly_points in ANOMALY_RESOLUTIONS:
            model = build_zo_equation_self_consistent_candidate_source(
                parameters,
                scaled_semimajor_axis=scaled_a,
                eccentricity=eccentricity,
                orbital_nonlinearity=nonlinearity,
                expected_eccentricity_profile_fingerprint=(
                    expected_e_fingerprints[case]
                ),
                expected_dynamics_profile_fingerprint=(
                    EXPECTED_DYNAMICS_FINGERPRINTS[case]
                ),
                anomaly_points=anomaly_points,
                candidate_label=f"Phase 5B7 {case}",
            )
            for closure_name, closure in PROFILES:
                rows.append(
                    _metric_row(
                        case=case,
                        scan_axis="anomaly_surface",
                        source=model.source,
                        closure_name=closure_name,
                        closure=closure,
                        circular_aspect_ratio=(
                            model.circular_scale_height_aspect_ratio
                        ),
                    )
                )
            if anomaly_points == ANOMALY_RESOLUTIONS[-1]:
                finest_model = model
        if finest_model is None:
            raise RuntimeError("finest anomaly source was not built")
        for radial_points in RADIAL_RESOLUTIONS:
            indices = native_radial_indices(scaled_a.size, radial_points)
            radial_source = subsample_radial_source(
                finest_model.source,
                indices,
                label=f"Phase 5B7 {case} {radial_points} radial nodes",
            )
            for closure_name, closure in PROFILES:
                rows.append(
                    _metric_row(
                        case=case,
                        scan_axis="radial",
                        source=radial_source,
                        closure_name=closure_name,
                        closure=closure,
                        circular_aspect_ratio=(
                            finest_model.circular_scale_height_aspect_ratio
                        ),
                    )
                )

    csv_path = OUTPUT / "phase5b7_candidate_validity_convergence.csv"
    write_csv(csv_path, rows)
    figure_path = OUTPUT / "phase5b7_candidate_validity_convergence.png"
    _plot(rows, figure_path)
    changes: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    for case in EXPECTED_DYNAMICS_FINGERPRINTS:
        for closure_name, _ in PROFILES:
            for scan_axis in ("radial", "anomaly_surface"):
                changes.extend(
                    _last_pair_changes(rows, case, scan_axis, closure_name)
                )
            finest = next(
                row
                for row in rows
                if row["case"] == case
                and row["scan_axis"] == "anomaly_surface"
                and row["closure"] == closure_name
                and row["anomaly_points"] == ANOMALY_RESOLUTIONS[-1]
            )
            fraction_changes = [
                row
                for row in changes
                if row["case"] == case
                and row["closure"] == closure_name
                and row["metric"]
                == "corrected_area_fraction_zph_over_r_ge_0p3"
            ]
            maximum_last_pair_change = max(
                float(row["absolute_change"]) for row in fraction_changes
            )
            finest_fraction = float(
                finest["corrected_area_fraction_zph_over_r_ge_0p3"]
            )
            decisions.append(
                {
                    "case": case,
                    "closure": closure_name,
                    "finest_corrected_area_fraction_zph_over_r_ge_0p3": (
                        finest_fraction
                    ),
                    "maximum_radial_or_anomaly_last_pair_absolute_change": (
                        maximum_last_pair_change
                    ),
                    "conservative_fraction_plus_change": (
                        finest_fraction + maximum_last_pair_change
                    ),
                    "finest_working_threshold_passed": (
                        finest_fraction <= WORKING_FAILURE_FRACTION
                    ),
                    "conservative_stability_gate_passed": (
                        finest_fraction + maximum_last_pair_change
                        <= WORKING_FAILURE_FRACTION
                    ),
                }
            )

    report = {
        "phase": "5B7 candidate validity convergence gate",
        "classification": "[A-candidate]+[A-domain]+[V]+[O]",
        "sources": {
            "phase5b4_report": source_entry(phase5b4_path),
            "phase5b4_mode_profiles": source_entry(profile_path),
            "phase5b5_summary": source_entry(phase5b5_path),
            "phase5b6_report": source_entry(phase5b6_path),
        },
        "scan": {
            "radial_points": list(RADIAL_RESOLUTIONS),
            "anomaly_points": list(ANOMALY_RESOLUTIONS),
            "finest_surface_triangle_count": 2
            * (RADIAL_RESOLUTIONS[-1] - 1)
            * ANOMALY_RESOLUTIONS[-1],
            "finest_uniform_anomaly_spacing_rad": (
                2.0 * np.pi / ANOMALY_RESOLUTIONS[-1]
            ),
            "closures": [name for name, _ in PROFILES],
            "radial_interpolation": False,
            "radial_scan_uses_exact_frozen_native_nodes": True,
            "anomaly_refinement_also_refines_pericentre_and_surface_triangles": True,
            "separate_adaptive_triangle_subdivision": False,
        },
        "working_criterion": {
            "maximum_corrected_area_fraction_zph_over_r_ge_0p3": (
                WORKING_FAILURE_FRACTION
            ),
            "both_vertical_closures_required": True,
            "literature_theorem": False,
        },
        "last_pair_changes": changes,
        "case_closure_decisions": decisions,
        "gate_checks": {
            "all_finest_working_thresholds_passed": all(
                row["finest_working_threshold_passed"] for row in decisions
            ),
            "all_conservative_stability_gates_passed": all(
                row["conservative_stability_gate_passed"] for row in decisions
            ),
            "all_zph_over_r_ge_1_fractions_zero_at_finest": all(
                float(row["corrected_area_fraction_zph_over_r_ge_1p0"])
                == 0.0
                for row in rows
                if row["radial_points"] == RADIAL_RESOLUTIONS[-1]
                and row["anomaly_points"] == ANOMALY_RESOLUTIONS[-1]
            ),
            "all_jacobian_and_height_extrema_positive": all(
                float(row["jacobian_min"]) > 0.0
                and float(row["dimensionless_height_min"]) > 0.0
                for row in rows
            ),
            "candidate_validity_convergence_closed": all(
                row["conservative_stability_gate_passed"] for row in decisions
            ),
            "published_benchmark_gate": False,
        },
        "interpretation": (
            "The Phase 5B6 candidates are tested as [A-candidate] sources. "
            "Passing the explicit 1% local-column working criterion does not "
            "turn either profile into a published ZO benchmark."
        ),
        "outputs": {
            "convergence_csv": source_entry(csv_path),
            "figure": source_entry(figure_path),
        },
    }
    report_path = OUTPUT / "phase5b7_candidate_validity_convergence_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    report = run()
    print(json.dumps(report["gate_checks"], indent=2))


if __name__ == "__main__":
    main()
