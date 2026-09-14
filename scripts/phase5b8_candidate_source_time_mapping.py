"""Phase 5B8：把通过有效域门的方程自洽候选相位映射到相对物理时间。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.apsidal_precession import zo_precession_scales
from eccentric_tde_observer.apsidal_time_mapping import (
    SECONDS_PER_DAY,
    apsidal_mode_profile_fingerprint,
)
from eccentric_tde_observer.candidate_apsidal_ephemeris import (
    build_validated_candidate_apsidal_ephemeris,
)
from eccentric_tde_observer.zo_candidate_source import (
    candidate_dynamics_profile_fingerprint,
)
from eccentric_tde_observer.zo_reference import ZOConstantEParameters


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
CASES = ("atlas_reference", "strict_boundary_sensitivity")
PHYSICAL_NORMALIZATION = {
    "black_hole_mass_msun": 1.0e6,
    "stellar_mass_msun": 1.0,
    "stellar_radius_rsun": 1.0,
    "circularization_efficiency": 0.01,
    "outer_to_inner_semimajor_axis": 2.0,
    "opacity_cm2_g": 0.34,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_entry(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def require_source_pin(
    *, owner: str, pin: dict[str, object], expected_path: Path
) -> None:
    relative_path = expected_path.relative_to(ROOT).as_posix()
    if pin.get("path") != relative_path or pin.get("sha256") != sha256(expected_path):
        raise RuntimeError(f"{owner} source pin differs from {relative_path}")


def run() -> dict[str, object]:
    paths = {
        "phase5b4_report": OUTPUT
        / "phase5b4_strict_domain_candidate_timescale_report.json",
        "phase5b4_profiles": OUTPUT / "phase5b4_candidate_mode_profiles.csv",
        "phase5b4_timescales": OUTPUT / "phase5b4_candidate_timescales.csv",
        "phase5b5_summary": OUTPUT / "phase5b5_mode_matched_time_axis_summary.json",
        "phase5b6_report": OUTPUT / "phase5b6_candidate_source_report.json",
        "phase5b7_report": OUTPUT
        / "phase5b7_candidate_validity_convergence_report.json",
    }
    phase5b4 = json.loads(paths["phase5b4_report"].read_text(encoding="utf-8"))
    phase5b5 = json.loads(paths["phase5b5_summary"].read_text(encoding="utf-8"))
    phase5b6 = json.loads(paths["phase5b6_report"].read_text(encoding="utf-8"))
    phase5b7 = json.loads(paths["phase5b7_report"].read_text(encoding="utf-8"))

    # 中文：先核对各阶段冻结的字节来源，拒绝把旧频率贴到被改动的候选源。
    require_source_pin(
        owner="Phase 5B5",
        pin=phase5b5["sources"]["phase5b4_report"],
        expected_path=paths["phase5b4_report"],
    )
    require_source_pin(
        owner="Phase 5B5",
        pin=phase5b5["sources"]["phase5b4_mode_profiles"],
        expected_path=paths["phase5b4_profiles"],
    )
    require_source_pin(
        owner="Phase 5B5",
        pin=phase5b5["sources"]["phase5b4_timescales"],
        expected_path=paths["phase5b4_timescales"],
    )
    require_source_pin(
        owner="Phase 5B6",
        pin=phase5b6["sources"]["phase5b5_summary"],
        expected_path=paths["phase5b5_summary"],
    )
    require_source_pin(
        owner="Phase 5B7",
        pin=phase5b7["sources"]["phase5b6_report"],
        expected_path=paths["phase5b6_report"],
    )
    if (
        phase5b4["high_e_equation_internal_gate"] is not True
        or phase5b4["equation_self_consistent_candidate_timescale_computed"]
        is not True
        or phase5b4["published_benchmark_gate"] is not False
        or phase5b6["authorization"]["candidate_source_rebuild_authorized_by_user"]
        is not True
        or phase5b6["authorization"]["published_benchmark_claim"] is not False
        or phase5b7["gate_checks"]["candidate_validity_convergence_closed"]
        is not True
        or phase5b7["gate_checks"]["published_benchmark_gate"] is not False
    ):
        raise RuntimeError("Phase 5B4--5B7 candidate authorization chain is not closed")

    parameters = ZOConstantEParameters(
        eccentricity=float(
            phase5b4["strict_source"]["constant_e_atlas_reference"]
        ),
        **PHYSICAL_NORMALIZATION,
    )
    scales = zo_precession_scales(parameters)
    reported_communication_s = (
        float(phase5b4["direct_eq39_scale"]["communication_time_days"])
        * SECONDS_PER_DAY
    )
    communication_relative_error = abs(
        scales.eccentric_communication_time_s / reported_communication_s - 1.0
    )
    delta_gr_relative_error = abs(
        scales.delta_gr / float(phase5b4["direct_eq39_scale"]["delta_gr"])
        - 1.0
    )
    scale_inner_errors = [
        abs(
            float(row["inner_semimajor_axis_cm"])
            / scales.inner_semimajor_axis_cm
            - 1.0
        )
        for row in phase5b6["case_results"]
    ]
    if max(communication_relative_error, delta_gr_relative_error, *scale_inner_errors) > 2.0e-13:
        raise RuntimeError("independent Eq. (39) normalization does not match source scale")

    profile_rows = load_csv(paths["phase5b4_profiles"])
    timescale_rows = {row["case"]: row for row in load_csv(paths["phase5b4_timescales"])}
    phase5b5_rows = {row["case"]: row for row in phase5b5["case_results"]}
    phase5b6_rows = {row["case"]: row for row in phase5b6["case_results"]}
    if set(timescale_rows) != set(CASES) or set(phase5b6_rows) != set(CASES):
        raise RuntimeError("candidate case set differs across Phase 5B4--5B7")

    validity_by_case = {
        case: all(
            row["finest_working_threshold_passed"] is True
            and row["conservative_stability_gate_passed"] is True
            for row in phase5b7["case_closure_decisions"]
            if row["case"] == case
        )
        and sum(
            row["case"] == case for row in phase5b7["case_closure_decisions"]
        )
        == 2
        for case in CASES
    }

    phases_deg = np.arange(0.0, 360.0, 15.0)
    phases_rad = np.deg2rad(phases_deg)
    schedule_rows: list[dict[str, object]] = []
    case_results: list[dict[str, object]] = []
    ephemerides = {}
    for case in CASES:
        selected = [row for row in profile_rows if row["case"] == case]
        scaled_a = np.array([float(row["scaled_semimajor_axis"]) for row in selected])
        eccentricity = np.array([float(row["eccentricity"]) for row in selected])
        nonlinearity = np.array(
            [float(row["orbital_nonlinearity"]) for row in selected]
        )
        e_fingerprint = apsidal_mode_profile_fingerprint(scaled_a, eccentricity)
        dynamics_fingerprint = candidate_dynamics_profile_fingerprint(
            scaled_a, eccentricity, nonlinearity
        )
        source_row = phase5b6_rows[case]
        clock_row = phase5b5_rows[case]
        if (
            e_fingerprint != source_row["eccentricity_profile_fingerprint"]
            or e_fingerprint != clock_row["eigenmode_profile_fingerprint"]
            or dynamics_fingerprint != source_row["dynamics_profile_fingerprint"]
        ):
            raise RuntimeError(f"{case} candidate profile lineage differs")
        frequency = float(timescale_rows[case]["dimensionless_frequency"])
        if frequency != float(clock_row["dimensionless_angular_frequency"]):
            raise RuntimeError(f"{case} candidate frequency lineage differs")
        ephemeris = build_validated_candidate_apsidal_ephemeris(
            dimensionless_angular_frequency=frequency,
            communication_time_s=scales.eccentric_communication_time_s,
            eigenmode_eccentricity_profile_fingerprint=e_fingerprint,
            source_eccentricity_profile_fingerprint=(
                source_row["eccentricity_profile_fingerprint"]
            ),
            eigenmode_dynamics_profile_fingerprint=dynamics_fingerprint,
            source_dynamics_profile_fingerprint=(
                source_row["dynamics_profile_fingerprint"]
            ),
            candidate_validity_convergence_closed=validity_by_case[case],
            published_benchmark_claim=False,
            reference_time_s=0.0,
            reference_phase_rad=0.0,
        )
        ephemerides[case] = ephemeris
        relative_days = ephemeris.relative_time_days_for_unwrapped_phase(phases_rad)
        recovered_phase = ephemeris.unwrapped_phase_rad_for_relative_time_days(
            relative_days
        )
        roundtrip_error = float(np.max(np.abs(recovered_phase - phases_rad)))
        direct_period = float(timescale_rows[case]["direct_eq39_period_days"])
        period_relative_error = abs(ephemeris.period_days / direct_period - 1.0)
        for degree, radians, days in zip(
            phases_deg, phases_rad, relative_days, strict=True
        ):
            schedule_rows.append(
                {
                    "case": case,
                    "phase_deg": degree,
                    "phase_rad": radians,
                    "candidate_relative_time_days": days,
                    "candidate_relative_time_years_365p25d": days / 365.25,
                    "signed_degrees_per_day": ephemeris.signed_degrees_per_day,
                    "eccentricity_profile_fingerprint": e_fingerprint,
                    "dynamics_profile_fingerprint": dynamics_fingerprint,
                    "candidate_validity_convergence_closed": True,
                    "published_benchmark": False,
                    "absolute_calendar_epoch_supplied": False,
                }
            )
        case_results.append(
            {
                "case": case,
                "classification": "[A-candidate]+[V]+[O]",
                "eccentricity_profile_fingerprint": e_fingerprint,
                "dynamics_profile_fingerprint": dynamics_fingerprint,
                "dimensionless_angular_frequency": frequency,
                "angular_frequency_s1": ephemeris.clock.angular_frequency_s1,
                "signed_cycles_per_day": ephemeris.signed_cycles_per_day,
                "signed_degrees_per_day": ephemeris.signed_degrees_per_day,
                "candidate_period_days": ephemeris.period_days,
                "candidate_period_years_365p25d": ephemeris.period_days / 365.25,
                "time_per_15_deg_days": ephemeris.period_days / 24.0,
                "phase_advance_365p25d_deg": (
                    ephemeris.signed_degrees_per_day * 365.25
                ),
                "maximum_phase_roundtrip_error_rad": roundtrip_error,
                "relative_difference_from_phase5b4_direct_period": (
                    period_relative_error
                ),
                "candidate_validity_convergence_closed": validity_by_case[case],
                "candidate_source_phase_to_relative_time_authorized": True,
                "existing_constant_e_atlas_phase_to_time_authorized": False,
                "published_benchmark": False,
            }
        )

    schedule_path = OUTPUT / "phase5b8_candidate_source_phase_schedule.csv"
    write_csv(schedule_path, schedule_rows)

    figure, axes = plt.subplots(1, 2, figsize=(12.2, 4.6), constrained_layout=True)
    colors = {"atlas_reference": "#2864dc", "strict_boundary_sensitivity": "#d95f02"}
    labels = {
        "atlas_reference": "Candidate inner e = 0.60",
        "strict_boundary_sensitivity": "Candidate inner e = 0.65",
    }
    elapsed_years = np.linspace(0.0, 10.0, 401)
    for result in case_results:
        case = result["case"]
        ephemeris = ephemerides[case]
        relative_days = ephemeris.relative_time_days_for_unwrapped_phase(phases_rad)
        axes[0].plot(
            phases_deg,
            relative_days / 365.25,
            color=colors[case],
            label=labels[case],
        )
        phase = ephemeris.unwrapped_phase_rad_for_relative_time_days(
            elapsed_years * 365.25
        )
        axes[1].plot(
            elapsed_years,
            np.rad2deg(phase),
            color=colors[case],
            label=labels[case],
        )
    axes[0].set(
        xlabel="Apsidal phase (deg)",
        ylabel="Relative time (yr)",
        title="(a) Candidate phase-to-time mapping",
        xlim=(0.0, 345.0),
    )
    axes[1].set(
        xlabel="Elapsed time (yr)",
        ylabel="Accumulated apsidal phase (deg)",
        title="(b) Ten-year phase drift",
        xlim=(0.0, 10.0),
    )
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend(frameon=False)
    figure.suptitle("Equation-consistent ZO candidate clocks (relative epoch)")
    figure_path = OUTPUT / "phase5b8_candidate_source_time_mapping.png"
    figure.savefig(figure_path, dpi=200)
    plt.close(figure)

    report = {
        "phase": "5B8 validated candidate-source apsidal time mapping",
        "classification": "[L]+[A-candidate]+[A-origin]+[V]+[O]",
        "sources": {name: source_entry(path) for name, path in paths.items()},
        "physical_normalization": {
            **PHYSICAL_NORMALIZATION,
            "classification": "[A-scale] inherited from the Phase 5B4/5B6 candidate",
            "inner_semimajor_axis_cm": scales.inner_semimajor_axis_cm,
            "inner_mean_motion_s1": scales.inner_mean_motion_s1,
            "inner_specific_internal_energy_erg_g": (
                scales.inner_specific_internal_energy_erg_g
            ),
            "eccentric_communication_time_s": (
                scales.eccentric_communication_time_s
            ),
            "eccentric_communication_time_days": (
                scales.eccentric_communication_time_s / SECONDS_PER_DAY
            ),
            "delta_gr": scales.delta_gr,
            "dimensionless_angular_frequency_unit_s1": (
                scales.dimensionless_to_angular_frequency_s1
            ),
            "dimensionless_frequency_unit_cycles_per_day": (
                scales.dimensionless_to_cycles_per_day
            ),
            "normalization_equations": "ZO Eqs. (9)--(12), (39)--(40)",
        },
        "time_origin": {
            "reference_relative_time_days": 0.0,
            "reference_phase_rad": 0.0,
            "absolute_calendar_epoch": None,
            "interpretation": (
                "Phi=0 at Delta t=0 is a coordinate origin, not a fitted MJD."
            ),
        },
        "case_results": case_results,
        "gate_checks": {
            "all_upstream_source_hashes_match": True,
            "phase5b4_equation_internal_gate_closed": True,
            "phase5b6_candidate_source_authorized": True,
            "phase5b7_candidate_validity_convergence_closed": True,
            "all_eccentricity_profile_fingerprints_match": True,
            "all_dynamics_profile_fingerprints_match": True,
            "independent_eq39_communication_time_relative_error_below_2e_minus_13": (
                communication_relative_error < 2.0e-13
            ),
            "independent_delta_gr_relative_error_below_2e_minus_13": (
                delta_gr_relative_error < 2.0e-13
            ),
            "independent_inner_semimajor_axis_relative_error_below_2e_minus_13": (
                max(scale_inner_errors) < 2.0e-13
            ),
            "maximum_phase_roundtrip_error_below_1e_minus_12_rad": max(
                row["maximum_phase_roundtrip_error_rad"] for row in case_results
            )
            < 1.0e-12,
            "maximum_direct_period_reproduction_error_below_1e_minus_12": max(
                row["relative_difference_from_phase5b4_direct_period"]
                for row in case_results
            )
            < 1.0e-12,
            "published_benchmark_gate": False,
        },
        "decision": {
            "candidate_source_phi_to_relative_physical_time_authorized": True,
            "existing_constant_e_atlas_phi_to_time_authorized": False,
            "absolute_calendar_time_authorized": False,
            "published_zo_benchmark_claim_authorized": False,
            "printed_eq48_normalization_adopted": False,
            "candidate_clock_can_label_future_observer_outputs_only_if_same_dynamics_fingerprint": True,
        },
        "open_issues": [
            "Published ZO Fig. 6/7 and the printed Eq. (48) normalization remain unresolved.",
            "No absolute epoch t0 or event MJD has been supplied.",
            "Current constant-e Phase 4/5/6 atlases remain outside this clock lineage.",
        ],
        "outputs": {
            "schedule": source_entry(schedule_path),
            "figure": source_entry(figure_path),
        },
    }
    if not all(
        value is True
        for key, value in report["gate_checks"].items()
        if key != "published_benchmark_gate"
    ) or report["gate_checks"]["published_benchmark_gate"] is not False:
        raise RuntimeError("Phase 5B8 candidate time-mapping gate failed")
    report_path = OUTPUT / "phase5b8_candidate_source_time_mapping_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    report = run()
    print(json.dumps(report["gate_checks"], indent=2))
    for row in report["case_results"]:
        print(
            row["case"],
            f"period_days={row['candidate_period_days']:.9f}",
            f"deg_per_year={row['phase_advance_365p25d_deg']:.9f}",
        )


if __name__ == "__main__":
    main()
