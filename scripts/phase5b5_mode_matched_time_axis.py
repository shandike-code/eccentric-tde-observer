"""Phase 5B5：构造模形哈希绑定的候选拱点时间钟。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.apsidal_time_mapping import (
    SECONDS_PER_DAY,
    apsidal_mode_profile_fingerprint,
    build_mode_matched_apsidal_clock,
)
from eccentric_tde_observer.source import PhysicalDomainError


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


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


def run() -> dict[str, object]:
    report_path = OUTPUT / "phase5b4_strict_domain_candidate_timescale_report.json"
    profile_path = OUTPUT / "phase5b4_candidate_mode_profiles.csv"
    timescale_path = OUTPUT / "phase5b4_candidate_timescales.csv"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (
        report["high_e_equation_internal_gate"] is not True
        or report["equation_self_consistent_candidate_timescale_computed"] is not True
        or report["existing_atlas_phase_to_time_mapping_authorized"] is not False
    ):
        raise RuntimeError("Phase 5B5 requires the closed Phase 5B4 candidate gate")
    profile_rows = load_csv(profile_path)
    timescale_rows = load_csv(timescale_path)
    communication_time_s = (
        float(report["direct_eq39_scale"]["communication_time_days"])
        * SECONDS_PER_DAY
    )
    phases_deg = np.arange(0.0, 360.0, 15.0)
    phase_rad = np.deg2rad(phases_deg)
    schedule_rows: list[dict[str, object]] = []
    case_results: list[dict[str, object]] = []
    figure, axes = plt.subplots(1, 2, figsize=(12.8, 4.6), constrained_layout=True)
    for timescale in timescale_rows:
        case = timescale["case"]
        selected = [row for row in profile_rows if row["case"] == case]
        semimajor = np.array(
            [float(row["scaled_semimajor_axis"]) for row in selected]
        )
        eccentricity = np.array([float(row["eccentricity"]) for row in selected])
        mode_fingerprint = apsidal_mode_profile_fingerprint(semimajor, eccentricity)
        constant_e = np.full_like(eccentricity, eccentricity[0])
        atlas_fingerprint = apsidal_mode_profile_fingerprint(semimajor, constant_e)
        atlas_rejected = False
        try:
            build_mode_matched_apsidal_clock(
                dimensionless_angular_frequency=float(
                    timescale["dimensionless_frequency"]
                ),
                communication_time_s=communication_time_s,
                eigenmode_profile_fingerprint=mode_fingerprint,
                source_profile_fingerprint=atlas_fingerprint,
            )
        except PhysicalDomainError:
            atlas_rejected = True
        if not atlas_rejected:
            raise RuntimeError("constant-e atlas unexpectedly passed the mode lineage gate")
        clock = build_mode_matched_apsidal_clock(
            dimensionless_angular_frequency=float(timescale["dimensionless_frequency"]),
            communication_time_s=communication_time_s,
            eigenmode_profile_fingerprint=mode_fingerprint,
            source_profile_fingerprint=mode_fingerprint,
        )
        relative_days = clock.time_s_for_unwrapped_phase(phase_rad) / SECONDS_PER_DAY
        printed_period = float(timescale["printed_eq48_period_days"])
        for degree, radians, days in zip(
            phases_deg, phase_rad, relative_days, strict=True
        ):
            schedule_rows.append(
                {
                    "case": case,
                    "phase_deg": degree,
                    "phase_rad": radians,
                    "candidate_relative_time_days": days,
                    "printed_eq48_audit_relative_time_days": (
                        printed_period * degree / 360.0
                    ),
                    "eigenmode_profile_fingerprint": mode_fingerprint,
                    "source_profile_match_required": True,
                    "existing_constant_e_atlas_row": False,
                }
            )
        recovered_phase = clock.unwrapped_phase_rad(relative_days * SECONDS_PER_DAY)
        phase_roundtrip = float(np.max(np.abs(recovered_phase - phase_rad)))
        period_difference = abs(
            clock.period_days - float(timescale["direct_eq39_period_days"])
        ) / float(timescale["direct_eq39_period_days"])
        case_results.append(
            {
                "case": case,
                "eigenmode_profile_fingerprint": mode_fingerprint,
                "constant_e_atlas_profile_fingerprint": atlas_fingerprint,
                "constant_e_atlas_rejected_by_profile_lineage": atlas_rejected,
                "dimensionless_angular_frequency": float(
                    timescale["dimensionless_frequency"]
                ),
                "angular_frequency_s1": clock.angular_frequency_s1,
                "cycles_per_day": clock.cycles_per_day,
                "candidate_period_days": clock.period_days,
                "printed_eq48_audit_period_days": printed_period,
                "maximum_phase_roundtrip_error_rad": phase_roundtrip,
                "relative_difference_from_phase5b4_direct_period": period_difference,
            }
        )
        label = "$e_{\\rm in}=$" + f"{eccentricity[0]:.2f}"
        axes[0].plot(semimajor, eccentricity / eccentricity[0], label=label)
        axes[1].plot(phases_deg, relative_days, label=label + " direct")
        axes[1].plot(
            phases_deg,
            printed_period * phases_deg / 360.0,
            ls=":",
            alpha=0.7,
            label=label + " printed audit",
        )
    axes[0].axhline(1.0, color="black", ls="--", label="Constant-e atlas")
    axes[0].set(
        xlabel=r"Scaled semimajor axis $a/a_{\rm in}$",
        ylabel=r"$e(a)/e_{\rm in}$",
        title="(a) Profile lineage gate",
    )
    axes[0].legend(frameon=False)
    axes[1].set(
        xlabel="Apsidal phase (deg)",
        ylabel="Relative time (day)",
        title="(b) Conditional mode-matched clock",
    )
    axes[1].legend(frameon=False, fontsize=8)
    figure_path = OUTPUT / "phase5b5_mode_matched_time_axis.png"
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)
    schedule_path = OUTPUT / "phase5b5_mode_matched_phase_schedule.csv"
    write_csv(schedule_path, schedule_rows)
    summary = {
        "phase": "5B5 mode-shape-bound candidate apsidal time axis",
        "classification": "[L/A-interface]+[V]+[O]",
        "sources": {
            "phase5b4_report": {
                "path": str(report_path.relative_to(ROOT)),
                "sha256": sha256(report_path),
            },
            "phase5b4_mode_profiles": {
                "path": str(profile_path.relative_to(ROOT)),
                "sha256": sha256(profile_path),
            },
            "phase5b4_timescales": {
                "path": str(timescale_path.relative_to(ROOT)),
                "sha256": sha256(timescale_path),
            },
        },
        "communication_time_days": communication_time_s / SECONDS_PER_DAY,
        "reference_epoch": None,
        "case_results": case_results,
        "gate_checks": {
            "all_candidate_mode_profiles_self_match": True,
            "all_constant_e_atlas_profiles_rejected": all(
                row["constant_e_atlas_rejected_by_profile_lineage"]
                for row in case_results
            ),
            "maximum_phase_roundtrip_error_below_1e_minus_12_rad": max(
                row["maximum_phase_roundtrip_error_rad"] for row in case_results
            )
            < 1.0e-12,
            "maximum_direct_period_reproduction_below_1e_minus_12": max(
                row["relative_difference_from_phase5b4_direct_period"]
                for row in case_results
            )
            < 1.0e-12,
        },
        "decision": {
            "mode_matched_candidate_clock_interface_passed": True,
            "candidate_schedule_is_relative_time_only": True,
            "absolute_calendar_epoch_supplied": False,
            "printed_eq48_normalization_adopted": False,
            "existing_constant_e_atlas_phase_to_time_mapping_authorized": False,
            "candidate_mode_source_rebuild_authorized": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
        "outputs": {
            "schedule": str(schedule_path.relative_to(ROOT)),
            "figure": str(figure_path.relative_to(ROOT)),
        },
    }
    summary_path = OUTPUT / "phase5b5_mode_matched_time_axis_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    print(json.dumps(run(), indent=2))


if __name__ == "__main__":
    main()
