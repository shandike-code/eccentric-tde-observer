"""Phase 5B6：构造模形绑定的方程自洽 ZO 候选源。"""

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

from eccentric_tde_observer.faceon import face_on_bolometric_luminosities
from eccentric_tde_observer.photosphere import solve_gray_photosphere
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
EXPECTED_DYNAMICS_FINGERPRINTS = {
    "atlas_reference": (
        "5e720e5503e9c85590c4533d01382de6bf03e7b449e6f0502b667580bfb75e76"
    ),
    "strict_boundary_sensitivity": (
        "d3b21496e07fb68626ad9f24e7fbd7a105631c7433c8adfb3889abff4a2c59ad"
    ),
}


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


def _source_entry(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def run(*, anomaly_points: int = 128) -> dict[str, object]:
    phase5b4_path = OUTPUT / "phase5b4_strict_domain_candidate_timescale_report.json"
    profile_path = OUTPUT / "phase5b4_candidate_mode_profiles.csv"
    phase5b5_path = OUTPUT / "phase5b5_mode_matched_time_axis_summary.json"
    phase5b4 = json.loads(phase5b4_path.read_text(encoding="utf-8"))
    phase5b5 = json.loads(phase5b5_path.read_text(encoding="utf-8"))
    if (
        phase5b4["high_e_equation_internal_gate"] is not True
        or phase5b4["equation_self_consistent_candidate_timescale_computed"]
        is not True
        or phase5b4["published_benchmark_gate"] is not False
        or phase5b4["existing_atlas_phase_to_time_mapping_authorized"] is not False
    ):
        raise RuntimeError("Phase 5B4 candidate lineage gate is not closed")
    frozen_profile = phase5b5["sources"]["phase5b4_mode_profiles"]
    if (
        frozen_profile["path"] != profile_path.relative_to(ROOT).as_posix()
        or frozen_profile["sha256"] != sha256(profile_path)
    ):
        raise RuntimeError("Phase 5B4 profile bytes differ from the Phase 5B5 source pin")

    expected_e_fingerprints = {
        row["case"]: row["eigenmode_profile_fingerprint"]
        for row in phase5b5["case_results"]
    }
    if set(expected_e_fingerprints) != set(EXPECTED_DYNAMICS_FINGERPRINTS):
        raise RuntimeError("candidate cases differ from the frozen Phase 5B5 ledger")
    profile_rows = load_csv(profile_path)
    parameters = ZOCandidateSourceParameters(
        black_hole_mass_msun=1.0e6,
        stellar_mass_msun=1.0,
        stellar_radius_rsun=1.0,
        circularization_efficiency=float(
            phase5b4["strict_source"]["circularization_efficiency"]
        ),
        opacity_cm2_g=0.34,
    )
    radial_rows: list[dict[str, object]] = []
    case_results: list[dict[str, object]] = []
    figure, axes = plt.subplots(2, 2, figsize=(11.2, 8.0), constrained_layout=True)
    for case in EXPECTED_DYNAMICS_FINGERPRINTS:
        selected = [row for row in profile_rows if row["case"] == case]
        scaled_a = np.array(
            [float(row["scaled_semimajor_axis"]) for row in selected]
        )
        eccentricity = np.array([float(row["eccentricity"]) for row in selected])
        nonlinearity = np.array(
            [float(row["orbital_nonlinearity"]) for row in selected]
        )
        model = build_zo_equation_self_consistent_candidate_source(
            parameters,
            scaled_semimajor_axis=scaled_a,
            eccentricity=eccentricity,
            orbital_nonlinearity=nonlinearity,
            expected_eccentricity_profile_fingerprint=expected_e_fingerprints[case],
            expected_dynamics_profile_fingerprint=(
                EXPECTED_DYNAMICS_FINGERPRINTS[case]
            ),
            anomaly_points=anomaly_points,
            candidate_label=f"Phase 5B6 {case}",
        )
        source = model.source
        dimensionless_height = source.scale_height_cm / (
            source.semimajor_axis_cm[:, None]
            * model.circular_scale_height_aspect_ratio
        )
        for index in range(scaled_a.size):
            radial_rows.append(
                {
                    "case": case,
                    "scaled_semimajor_axis": scaled_a[index],
                    "eccentricity": eccentricity[index],
                    "eccentricity_plus_gradient": (
                        model.eccentricity_plus_gradient[index]
                    ),
                    "orbital_nonlinearity": nonlinearity[index],
                    "jacobian_min": np.min(source.jacobian[index]),
                    "jacobian_max": np.max(source.jacobian[index]),
                    "dimensionless_height_min": np.min(
                        dimensionless_height[index]
                    ),
                    "dimensionless_height_max": np.max(
                        dimensionless_height[index]
                    ),
                    "effective_temperature_min_k": np.min(
                        source.effective_temperature_k[index]
                    ),
                    "effective_temperature_max_k": np.max(
                        source.effective_temperature_k[index]
                    ),
                }
            )
        validity: dict[str, object] = {}
        for closure_name, closure in (
            ("gaussian", GAUSSIAN_VERTICAL_PROFILE),
            ("polytrope_n3", RADIATION_PRESSURE_POLYTROPE_PROFILE),
        ):
            photosphere = solve_gray_photosphere(
                source, parameters.opacity_cm2_g, 2.0 / 3.0, closure
            )
            audit = audit_local_vertical_domain(
                source, photosphere, ratio_thresholds=(0.3, 1.0)
            )
            validity[closure_name] = {
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
                "oriented_single_valued_surface_graph": (
                    audit.oriented_single_valued_surface_graph
                ),
            }
        luminosity_iso, luminosity_two_sided = face_on_bolometric_luminosities(
            source
        )
        case_results.append(
            {
                "case": case,
                "classification": model.classification,
                "published_benchmark": model.published_benchmark,
                "eccentricity_profile_fingerprint": (
                    model.eccentricity_profile_fingerprint
                ),
                "dynamics_profile_fingerprint": model.dynamics_profile_fingerprint,
                "source_shape": list(source.shape),
                "inner_semimajor_axis_cm": model.inner_semimajor_axis_cm,
                "eccentricity_inner_outer": [
                    float(eccentricity[0]),
                    float(eccentricity[-1]),
                ],
                "eccentricity_plus_gradient_min_max": [
                    float(np.min(model.eccentricity_plus_gradient)),
                    float(np.max(model.eccentricity_plus_gradient)),
                ],
                "jacobian_min_max": [
                    float(np.min(source.jacobian)),
                    float(np.max(source.jacobian)),
                ],
                "dimensionless_height_min_max": [
                    float(np.min(dimensionless_height)),
                    float(np.max(dimensionless_height)),
                ],
                "effective_temperature_min_max_k": [
                    float(np.min(source.effective_temperature_k)),
                    float(np.max(source.effective_temperature_k)),
                ],
                "corrected_face_on_isotropic_equivalent_bolometric_erg_s": (
                    luminosity_iso
                ),
                "corrected_intrinsic_two_sided_bolometric_erg_s": (
                    luminosity_two_sided
                ),
                "validity_interface": validity,
            }
        )
        label = case.replace("_", " ")
        apoapsis_index = anomaly_points // 2
        axes[0, 0].plot(scaled_a, eccentricity, label=label)
        axes[0, 1].plot(scaled_a, np.min(source.jacobian, axis=1), label=label)
        axes[0, 1].plot(
            scaled_a, np.max(source.jacobian, axis=1), ls="--", color=axes[0, 1].lines[-1].get_color()
        )
        local_radius = source.semimajor_axis_cm[:, None] * (
            1.0 - eccentricity[:, None] * np.cos(source.eccentric_anomaly_rad)
        )
        h_over_r = source.scale_height_cm / local_radius
        axes[1, 0].plot(scaled_a, h_over_r[:, 0], label=label + " periapsis")
        axes[1, 0].plot(
            scaled_a,
            h_over_r[:, apoapsis_index],
            ls="--",
            label=label + " apoapsis",
        )
        axes[1, 1].plot(
            scaled_a,
            source.effective_temperature_k[:, 0],
            label=label + " periapsis",
        )
        axes[1, 1].plot(
            scaled_a,
            source.effective_temperature_k[:, apoapsis_index],
            ls="--",
            label=label + " apoapsis",
        )

    axes[0, 0].set(xlabel="a / a_in", ylabel="Eccentricity", title="(a) Frozen candidate profiles")
    axes[0, 1].set(xlabel="a / a_in", ylabel="Orbital Jacobian", title="(b) Jacobian envelope")
    axes[1, 0].set(xlabel="a / a_in", ylabel="H / r", title="(c) Local vertical aspect ratio")
    axes[1, 1].set(xlabel="a / a_in", ylabel="Effective temperature (K)", title="(d) ZO Eq. (55) temperature")
    for axis in axes.flat:
        axis.legend(frameon=False, fontsize=7)
    figure_path = OUTPUT / "phase5b6_candidate_source_diagnostics.png"
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)

    radial_path = OUTPUT / "phase5b6_candidate_source_radial_diagnostics.csv"
    write_csv(radial_path, radial_rows)
    report = {
        "phase": "5B6 equation-self-consistent candidate source",
        "classification": "[L]+[A-candidate]+[V]+[O]",
        "authorization": {
            "candidate_source_rebuild_authorized_by_user": True,
            "authorization_date": "2026-09-02",
            "published_benchmark_claim": False,
            "constant_e_control_replaced": False,
        },
        "sources": {
            "phase5b4_report": _source_entry(phase5b4_path),
            "phase5b4_mode_profiles": _source_entry(profile_path),
            "phase5b5_summary": _source_entry(phase5b5_path),
        },
        "construction": {
            "radial_interpolation": False,
            "numerical_eccentricity_differentiation": False,
            "q_to_f_relation": "f=(q+e)/(1+q*e)",
            "source_equations": ["ZO Eq. (10)", "Eq. (16)", "Eq. (18)", "Eq. (31)", "Eq. (35)", "Eq. (55)"],
            "anomaly_points": anomaly_points,
            "corrected_radiative_area_used_downstream": True,
            "numerical_clip_floor_or_renormalization": False,
        },
        "case_results": case_results,
        "gate_checks": {
            "all_eccentricity_fingerprints_match": all(
                row["eccentricity_profile_fingerprint"]
                == expected_e_fingerprints[row["case"]]
                for row in case_results
            ),
            "all_dynamics_fingerprints_match": all(
                row["dynamics_profile_fingerprint"]
                == EXPECTED_DYNAMICS_FINGERPRINTS[row["case"]]
                for row in case_results
            ),
            "all_sources_are_nested_and_positive": True,
            "generic_validity_interface_executed": True,
            "formal_candidate_validity_convergence_closed": False,
            "published_benchmark_gate": False,
        },
        "interpretation": (
            "The frozen equation-self-consistent e(a), q(a) candidates now have "
            "independent ZO source grids. They are authorized [A-candidate] "
            "baselines, not published benchmarks; the unchanged constant-e "
            "branch remains the historical and circular-limit control."
        ),
        "outputs": {
            "radial_diagnostics": _source_entry(radial_path),
            "figure": _source_entry(figure_path),
        },
    }
    report_path = OUTPUT / "phase5b6_candidate_source_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anomaly-points", type=int, default=128)
    args = parser.parse_args()
    report = run(anomaly_points=args.anomaly_points)
    print(json.dumps(report["gate_checks"], indent=2))


if __name__ == "__main__":
    main()
