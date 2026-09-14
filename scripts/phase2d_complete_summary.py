"""Phase 2D：只读取既有输出，生成第二阶段综合图与结论报告。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PROBE_FREQUENCY_HZ = np.array([5.0e14, 1.0e15, 2.0e15, 5.0e15, 1.0e16])
PHASE_DEG = tuple(int(value) for value in np.arange(0, 360, 30))


def _records(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _phase_modulation(
    table: np.ndarray, prefix: str, selected: np.ndarray
) -> np.ndarray:
    values = np.stack(
        [
            table[f"{prefix}_i75_phi{phase:03d}_Fnu_cgs"][selected]
            for phase in PHASE_DEG
        ]
    )
    if np.any(values <= 0.0) or not np.all(np.isfinite(values)):
        raise ArithmeticError("phase modulation requires finite positive flux")
    return np.max(values, axis=0) / np.min(values, axis=0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    blackbody_path = args.output_dir / "phase2a_weakfield_spectra.csv"
    opacity_path = args.output_dir / "phase2b_frequency_opacity_audit.csv"
    modified_path = args.output_dir / "phase2c_modified_blackbody_spectra.csv"
    diagnostics_path = args.output_dir / "phase2c_orientation_diagnostics.csv"
    for path in (blackbody_path, opacity_path, modified_path, diagnostics_path):
        if not path.exists():
            raise FileNotFoundError(f"required Phase 2 output is missing: {path}")

    blackbody = np.genfromtxt(blackbody_path, delimiter=",", names=True)
    opacity = np.genfromtxt(opacity_path, delimiter=",", names=True)
    modified = np.genfromtxt(modified_path, delimiter=",", names=True)
    diagnostics = _records(diagnostics_path)
    if not np.array_equal(blackbody["frequency_hz"], modified["frequency_hz"]):
        raise RuntimeError("Phase 2A and 2C frequency grids do not match")
    frequency = modified["frequency_hz"]

    blackbody_fnu = blackbody["full_shift_i75_phi090_Fnu_cgs"]
    modified_fnu = modified["modified_i75_phi090_Fnu_cgs"]
    modulation_selected = frequency <= 1.0e16
    blackbody_modulation = _phase_modulation(
        blackbody, "full_shift", modulation_selected
    )
    modified_modulation = _phase_modulation(
        modified, "modified", modulation_selected
    )
    phase75 = [
        record for record in diagnostics if float(record["inclination_deg"]) == 75.0
    ]

    figure, axes = plt.subplots(2, 2, figsize=(13.8, 10.0), constrained_layout=True)
    figure.suptitle("Phase 2 complete: what the bare eccentric disc can predict", fontsize=16)
    axis = axes[0, 0]
    axis.loglog(frequency, frequency * blackbody_fnu, label="Phase 2A local blackbody")
    axis.loglog(frequency, frequency * modified_fnu, label="Phase 2C modified blackbody")
    axis.axvline(1.0e15, color="black", linestyle=":", label="conservative full-thermalization limit")
    axis.axvspan(1.0e15, 2.0e16, color="tab:orange", alpha=0.10)
    axis.set_xlim(1.0e14, 2.0e16)
    axis.set_ylim(1.0e-16, 3.0e-12)
    axis.set_xlabel(r"$\nu_{obs}$ [Hz]")
    axis.set_ylabel(r"$\nu F_\nu$ [erg s$^{-1}$ cm$^{-2}$]")
    axis.set_title(r"Actual flux at 100 Mpc: $i=75$ deg, phase 90 deg")
    axis.legend(fontsize=8)

    axis = axes[0, 1]
    axis.semilogx(
        opacity["frequency_hz"],
        opacity["corrected_area_fraction_tau_eff_ge_1"],
    )
    axis.axhline(0.99, color="black", linestyle="--", linewidth=1.0)
    axis.axvline(7.254e16, color="tab:red", linestyle=":", label="0.3 keV")
    axis.set_ylim(-0.03, 1.03)
    axis.set_xlabel(r"$\nu$ [Hz]")
    axis.set_ylabel(r"corrected ZO-area fraction with $\tau_{eff}\geq1$")
    axis.set_title("Physical applicability of the continuum closure")
    axis.legend(fontsize=8)

    axis = axes[1, 0]
    axis.semilogx(
        frequency[modulation_selected], blackbody_modulation, label="Phase 2A"
    )
    axis.semilogx(
        frequency[modulation_selected], modified_modulation, label="Phase 2C"
    )
    axis.axvline(1.0e15, color="black", linestyle=":")
    axis.set_xlabel(r"$\nu_{obs}$ [Hz]")
    axis.set_ylabel(r"phase max/min at $i=75$ deg")
    axis.set_title("Falsifiable chromatic precession modulation")
    axis.legend(fontsize=8)

    axis = axes[1, 1]
    phase = [float(record["relative_phase_deg"]) for record in phase75]
    axis.plot(
        phase,
        [float(record["thermalized_optical_T_bb_k"]) for record in phase75],
        marker="o",
        color="tab:red",
    )
    axis.set_xlabel(r"relative phase $\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel(r"conservative $T_{bb}$ [K]", color="tab:red")
    axis.tick_params(axis="y", labelcolor="tab:red")
    twin = axis.twinx()
    twin.plot(
        phase,
        [float(record["thermalized_optical_R_bb_cm"]) for record in phase75],
        marker="s",
        color="tab:blue",
    )
    twin.set_ylabel(r"conservative $R_{bb}$ [cm]", color="tab:blue")
    twin.tick_params(axis="y", labelcolor="tab:blue")
    axis.set_title(r"Observable fit in fully thermalized $5e14--1e15$ Hz band")
    figure.savefig(args.output_dir / "phase2_complete_summary.png", dpi=180)
    plt.close(figure)

    phase2a_report = json.loads(
        (args.output_dir / "phase2a_weakfield_spectra_report.json").read_text()
    )
    phase2b_report = json.loads(
        (args.output_dir / "phase2b_atmosphere_audit_report.json").read_text()
    )
    phase2c_report = json.loads(
        (args.output_dir / "phase2c_modified_blackbody_report.json").read_text()
    )
    report = {
        "phase_2_status": "complete_within_declared_bare_disc_scope",
        "scope_completed": [
            "2A weak-field Doppler plus gravitational frequency shift",
            "2B free-free plus electron-scattering thermalization audit",
            "2C locally energy-conserving modified-blackbody observer spectra",
            "2D synthesis, applicability mask, and falsifiable observables",
        ],
        "source_model_preserved": True,
        "disc_wind_or_free_reprocessing_added": False,
        "main_verified_results": {
            "weak_field_g_range": phase2a_report["observer_ranges_full_shift"]["full_g_min"]
            + phase2a_report["observer_ranges_full_shift"]["full_g_max"],
            "peak_thermalization_f_col_range": phase2b_report["peak_thermalization"]["f_col_range"],
            "conservative_T_bb_k": phase2c_report["observer_ranges"]["conservative_T_bb_k"],
            "conservative_R_bb_cm": phase2c_report["observer_ranges"]["conservative_R_bb_cm"],
            "i75_phase_max_to_min": phase2c_report["i75_phase_max_to_min"],
        },
        "bare_disc_answer": {
            "optical_continuum_and_phase_modulation": (
                "conditional prediction below the conservative full-thermalization limit"
            ),
            "partly_thin_uv_tail": "closure-sensitive diagnostic, not a robust prediction",
            "xray": (
                "not predicted by this atmosphere closure because the entire source is "
                "effectively thin already at 0.3 keV"
            ),
            "xray_failure_may_be_repaired_by_tuning_wind_here": False,
        },
        "validation_passed": {
            "phase2a": phase2a_report["numerical_validation"]["all_listed_changes_below_1e_minus_3"],
            "phase2c": phase2c_report["numerical_validation"]["all_geometric_and_grid_probe_changes_below_2e_minus_3"],
            "phase2b_vertical_tau_max_change": phase2b_report["numerical_validation"]["tau_eff_vertical_129_to_257_max_fractional_change"],
        },
        "not_claimed_complete": [
            "non-gray radiative-equilibrium or NLTE annulus atmosphere",
            "bound-free/line opacity and ionization balance",
            "Compton redistribution and polarization",
            "full GR ray tracing or relativistic moving-surface area",
            "disc wind or external reprocessing",
        ],
        "recommended_phase_3_order": [
            "NLTE/non-gray annulus atmosphere or validated atmosphere table",
            "angle-dependent local intensity and polarization",
            "Cunningham-style GR image-plane transfer",
            "only after a quantified bare-disc failure, constrained reprocessing layer",
        ],
    }
    (args.output_dir / "phase2_complete_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["bare_disc_answer"], indent=2), flush=True)


if __name__ == "__main__":
    main()
