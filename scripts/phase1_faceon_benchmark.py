"""Generate the Phase-1 face-on analytic benchmark and diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eccentric_tde_observer.faceon import (
    face_on_blackbody_sed,
    face_on_bolometric_luminosities,
)
from eccentric_tde_observer.fixtures import constant_temperature_circular_annulus
from eccentric_tde_observer.quadrature import corrected_zo_area_cm2
from eccentric_tde_observer.radiation import planck_nu


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    inner_radius = 1.0e14
    outer_radius = 2.0e14
    temperature = 5.0e4
    source = constant_temperature_circular_annulus(
        inner_radius,
        outer_radius,
        temperature,
        radial_points=129,
        anomaly_points=256,
    )
    # The upper bound covers 10 keV.  For this 5e4 K fixture, part of that Wien
    # tail is below floating-point range, so local relative errors are reported
    # only where the analytic intensity is representable.
    frequency = np.geomspace(1.0e12, 3.0e18, 3001)
    sed = face_on_blackbody_sed(source, frequency)

    analytic_area = np.pi * (outer_radius**2 - inner_radius**2)
    analytic_lnu = 4.0 * np.pi * analytic_area * planck_nu(frequency, temperature)
    representable = analytic_lnu > 0.0
    if not np.any(representable):
        raise ArithmeticError("analytic benchmark is zero throughout the frequency grid")
    if np.any(sed.isotropic_equivalent_lnu_erg_s_hz[~representable] != 0.0):
        raise ArithmeticError(
            "numerical and analytic Wien-tail underflow boundaries disagree"
        )
    relative_error = (
        sed.isotropic_equivalent_lnu_erg_s_hz[representable]
        / analytic_lnu[representable]
        - 1.0
    )
    peak_normalized_difference = (
        sed.isotropic_equivalent_lnu_erg_s_hz - analytic_lnu
    ) / np.max(analytic_lnu)
    numerical_bolometric = np.trapezoid(
        sed.isotropic_equivalent_lnu_erg_s_hz, frequency
    )
    analytic_bolometric, true_bolometric = face_on_bolometric_luminosities(source)

    report = {
        "classification": "analytic verification fixture [A/V], not a TDE prediction",
        "area_formula": (
            "ZO 2022 Erratum: dA_corrected = "
            "a*j*(1-e*cos(E))*da*dE"
        ),
        "cartesian_area_note": (
            "For an (a,E) surface, dA_xy = a*j*(1-e*cos(E))*da*dE"
        ),
        "isotropic_equivalent_formula": "Lnu_iso = 4*pi*integral(Bnu*dA)",
        "inner_radius_cm": inner_radius,
        "outer_radius_cm": outer_radius,
        "temperature_k": temperature,
        "numerical_area_cm2": corrected_zo_area_cm2(source),
        "analytic_area_cm2": analytic_area,
        "relative_area_error": corrected_zo_area_cm2(source) / analytic_area - 1.0,
        "max_absolute_spectral_relative_error": float(np.max(np.abs(relative_error))),
        "relative_error_max_frequency_hz": float(frequency[representable][-1]),
        "joint_wien_underflow_points": int(np.count_nonzero(~representable)),
        "max_peak_normalized_spectral_difference": float(
            np.max(np.abs(peak_normalized_difference))
        ),
        "frequency_integrated_liso_erg_s": float(numerical_bolometric),
        "stefan_boltzmann_liso_erg_s": float(analytic_bolometric),
        "relative_bolometric_error": float(
            numerical_bolometric / analytic_bolometric - 1.0
        ),
        "intrinsic_two_sided_bolometric_erg_s": float(true_bolometric),
    }

    csv_data = np.column_stack(
        (
            frequency,
            sed.nu_lnu_isotropic_erg_s,
            frequency * analytic_lnu,
            peak_normalized_difference,
        )
    )
    np.savetxt(
        args.output_dir / "phase1_faceon_sed.csv",
        csv_data,
        delimiter=",",
        header=(
            "frequency_hz,numerical_nu_lnu_iso_erg_s,"
            "analytic_nu_lnu_iso_erg_s,lnu_difference_over_peak_lnu"
        ),
        comments="",
    )
    (args.output_dir / "phase1_faceon_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )

    figure, (spectrum_axis, error_axis) = plt.subplots(
        2,
        1,
        figsize=(8.0, 6.5),
        sharex=True,
        gridspec_kw={"height_ratios": [3.2, 1.0], "hspace": 0.08},
    )
    spectrum_axis.loglog(
        frequency,
        sed.nu_lnu_isotropic_erg_s,
        color="#1f4e79",
        linewidth=2.1,
        label="numerical area integral",
    )
    spectrum_axis.loglog(
        frequency,
        frequency * analytic_lnu,
        color="#d97706",
        linestyle="--",
        linewidth=1.5,
        label="analytic isothermal annulus",
    )
    spectral_peak = float(np.max(sed.nu_lnu_isotropic_erg_s))
    spectrum_axis.set_ylim(spectral_peak * 1.0e-8, spectral_peak * 3.0)
    optical_uv = (0.002 * 2.417989242e17, 0.1 * 2.417989242e17)
    x_ray = (0.3 * 2.417989242e17, 10.0 * 2.417989242e17)
    spectrum_axis.axvspan(*optical_uv, color="#5fb49c", alpha=0.12, label="0.002--0.1 keV")
    spectrum_axis.axvspan(*x_ray, color="#c94c4c", alpha=0.10, label="0.3--10 keV")
    spectrum_axis.set_ylabel(r"$\nu L_{\nu,\rm iso}$  [erg s$^{-1}$]")
    spectrum_axis.set_title("Phase 1: face-on circular-annulus benchmark")
    spectrum_axis.text(
        0.02,
        0.05,
        "analytic verification only — not an eccentric-TDE prediction",
        transform=spectrum_axis.transAxes,
        fontsize=9,
        color="#4b5563",
    )
    spectrum_axis.legend(loc="upper left", frameon=False, fontsize=8.5, ncols=2)
    spectrum_axis.grid(which="both", alpha=0.18)

    error_axis.semilogx(
        frequency[representable], relative_error, color="#374151", linewidth=1.0
    )
    error_axis.axhline(0.0, color="black", linewidth=0.7)
    error_axis.set_xlabel(r"frequency $\nu$ [Hz]")
    error_axis.set_ylabel("relative\nerror")
    error_axis.grid(which="both", alpha=0.18)
    error_axis.ticklabel_format(axis="y", style="sci", scilimits=(-2, 2))

    figure.savefig(args.output_dir / "phase1_faceon_sed.png", dpi=180, bbox_inches="tight")
    plt.close(figure)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
