"""Phase 5A：把 Phase 4 图谱变为红移、距离和前景消光后的 F_lambda。"""

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

from eccentric_tde_observer.observer_frame import (
    MPC_CM,
    flat_lcdm_luminosity_distance_cm,
    redshift_reference_fnu,
    reference_fnu_to_observer_flambda,
)


REFERENCE_DISTANCE_CM = 100.0 * MPC_CM
ORIENTATIONS = (
    (0.0, 0.0, r"$i=0^\circ$"),
    (45.0, 0.0, r"$i=45^\circ,\ \Phi=0^\circ$"),
    (45.0, 180.0, r"$i=45^\circ,\ \Phi=180^\circ$"),
    (75.0, 90.0, r"$i=75^\circ,\ \Phi=90^\circ$"),
    (75.0, 270.0, r"$i=75^\circ,\ \Phi=270^\circ$"),
)


def _load_phase4_spectrum(
    path: Path, inclination_deg: float, phase_deg: float
) -> tuple[np.ndarray, np.ndarray]:
    frequency: list[float] = []
    flux: list[float] = []
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if (
                float(row["inclination_deg"]) == inclination_deg
                and float(row["relative_phase_deg"]) == phase_deg
            ):
                frequency.append(float(row["frequency_hz"]))
                flux.append(float(row["GR_Fnu_cgs"]))
    if len(frequency) < 2:
        raise RuntimeError(
            f"Phase 4 atlas has no complete spectrum at i={inclination_deg}, phase={phase_deg}"
        )
    order = np.argsort(frequency)
    return np.asarray(frequency)[order], np.asarray(flux)[order]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--atlas",
        type=Path,
        default=Path("outputs/phase4_atlas_spectra.csv"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--redshift", type=float, default=0.05)
    parser.add_argument("--ebv", type=float, default=0.03)
    parser.add_argument("--rv", type=float, default=3.1)
    parser.add_argument("--hubble", type=float, default=70.0)
    parser.add_argument("--omega-matter", type=float, default=0.3)
    args = parser.parse_args()
    started = time.perf_counter()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    luminosity_distance = flat_lcdm_luminosity_distance_cm(
        args.redshift,
        hubble_km_s_mpc=args.hubble,
        omega_matter=args.omega_matter,
    )
    if luminosity_distance <= 0.0:
        raise ValueError("the demonstration requires redshift > 0")

    spectra = []
    records: list[dict[str, object]] = []
    bolometric_residuals = []
    invariant_residuals = []
    zero_extinction_residuals = []
    for inclination, phase, label in ORIENTATIONS:
        frequency, reference_fnu = _load_phase4_spectrum(
            args.atlas, inclination, phase
        )
        spectrum = reference_fnu_to_observer_flambda(
            frequency,
            reference_fnu,
            reference_distance_cm=REFERENCE_DISTANCE_CM,
            redshift=args.redshift,
            luminosity_distance_cm=luminosity_distance,
            wavelength_min_angstrom=1000.0,
            wavelength_max_angstrom=20000.0,
            ebv_magnitude=args.ebv,
            r_v=args.rv,
        )
        zero_extinction = reference_fnu_to_observer_flambda(
            frequency,
            reference_fnu,
            reference_distance_cm=REFERENCE_DISTANCE_CM,
            redshift=args.redshift,
            luminosity_distance_cm=luminosity_distance,
            wavelength_min_angstrom=1000.0,
            wavelength_max_angstrom=20000.0,
            ebv_magnitude=0.0,
            r_v=args.rv,
        )
        observed_frequency, observed_fnu = redshift_reference_fnu(
            frequency,
            reference_fnu,
            reference_distance_cm=REFERENCE_DISTANCE_CM,
            redshift=args.redshift,
            luminosity_distance_cm=luminosity_distance,
        )
        expected_bolometric_scale = (
            REFERENCE_DISTANCE_CM / luminosity_distance
        ) ** 2
        bolometric_residuals.append(
            abs(
                np.trapezoid(observed_fnu, observed_frequency)
                / np.trapezoid(reference_fnu, frequency)
                / expected_bolometric_scale
                - 1.0
            )
        )
        invariant_residuals.append(
            float(
                np.max(
                    np.abs(
                        spectrum.wavelength_obs_angstrom
                        * spectrum.flux_lambda_unextinguished_erg_s_cm2_angstrom
                        / (
                            spectrum.frequency_obs_hz
                            * spectrum.flux_nu_obs_erg_s_cm2_hz
                        )
                        - 1.0
                    )
                )
            )
        )
        zero_extinction_residuals.append(
            float(
                np.max(
                    np.abs(
                        zero_extinction.flux_lambda_attenuated_erg_s_cm2_angstrom
                        / zero_extinction.flux_lambda_unextinguished_erg_s_cm2_angstrom
                        - 1.0
                    )
                )
            )
        )
        spectra.append((inclination, phase, label, spectrum))
        for index, wavelength in enumerate(spectrum.wavelength_obs_angstrom):
            records.append(
                {
                    "inclination_deg": inclination,
                    "relative_phase_deg": phase,
                    "redshift": args.redshift,
                    "luminosity_distance_mpc": luminosity_distance / MPC_CM,
                    "wavelength_obs_angstrom": float(wavelength),
                    "frequency_obs_hz": float(spectrum.frequency_obs_hz[index]),
                    "frequency_emitted_hz": float(
                        spectrum.frequency_emitted_hz[index]
                    ),
                    "Fnu_obs_erg_s_cm2_hz": float(
                        spectrum.flux_nu_obs_erg_s_cm2_hz[index]
                    ),
                    "Flambda_unextinguished_erg_s_cm2_angstrom": float(
                        spectrum.flux_lambda_unextinguished_erg_s_cm2_angstrom[index]
                    ),
                    "A_lambda_mag": float(spectrum.extinction_a_lambda_mag[index]),
                    "Flambda_attenuated_erg_s_cm2_angstrom": float(
                        spectrum.flux_lambda_attenuated_erg_s_cm2_angstrom[index]
                    ),
                }
            )

    _write_csv(args.output_dir / "phase5a_observer_flambda_spectra.csv", records)

    figure, axes = plt.subplots(1, 2, figsize=(14.5, 5.7), constrained_layout=True)
    colors = plt.colormaps["viridis"](np.linspace(0.08, 0.92, len(spectra)))
    for color, (_, _, label, spectrum) in zip(colors, spectra, strict=True):
        wavelength = spectrum.wavelength_obs_angstrom
        axes[0].loglog(
            wavelength,
            spectrum.flux_lambda_unextinguished_erg_s_cm2_angstrom,
            color=color,
            linewidth=1.8,
            label=label,
        )
        axes[1].loglog(
            wavelength,
            spectrum.flux_lambda_attenuated_erg_s_cm2_angstrom,
            color=color,
            linewidth=1.8,
            label=label,
        )
    for axis in axes:
        axis.set_xlim(1000.0, 20000.0)
        axis.set_xlabel(r"observer wavelength $\lambda_{obs}$ [$\AA$]")
        axis.set_ylabel(
            r"$F_{\lambda,obs}$ [erg s$^{-1}$ cm$^{-2}$ $\AA^{-1}$]"
        )
        axis.grid(alpha=0.22, which="both")
        axis.legend(fontsize=8)
    axes[0].set_title("Observer-frame bare-disc spectra: no foreground extinction")
    axes[1].set_title(
        rf"Fitzpatrick foreground: $E(B-V)={args.ebv:g}$, $R_V={args.rv:g}$"
    )
    figure.suptitle(
        rf"Phase 5A $F_\lambda$ demonstration: $z={args.redshift:g}$, "
        rf"$D_L={luminosity_distance / MPC_CM:.2f}$ Mpc (not an event fit)"
    )
    figure.savefig(args.output_dir / "phase5a_observer_flambda_spectra.png", dpi=190)
    plt.close(figure)

    report = {
        "classification_legend": {
            "L": "literature relation",
            "A": "adopted demonstration setting or new observer mapping",
            "V": "verified by tests or numerical output",
            "O": "open problem",
        },
        "classification": (
            "[L/A/V] Hogg redshift-distance mapping plus the Fitzpatrick 1998 "
            "mean Galactic extinction curve applied to the Phase-4 bare-disc atlas"
        ),
        "input": {
            "phase4_atlas": str(args.atlas),
            "reference_distance_mpc": REFERENCE_DISTANCE_CM / MPC_CM,
            "orientations_inclination_phase_deg": [
                [row[0], row[1]] for row in ORIENTATIONS
            ],
        },
        "demonstration_assumptions": {
            "redshift": args.redshift,
            "hubble_km_s_mpc": args.hubble,
            "omega_matter": args.omega_matter,
            "luminosity_distance_mpc": luminosity_distance / MPC_CM,
            "foreground_ebv_mag": args.ebv,
            "foreground_rv": args.rv,
            "host_extinction": "zero; no independent host prior supplied",
            "event_fit": False,
        },
        "output_domain": {
            "requested_wavelength_obs_angstrom": [1000.0, 20000.0],
            "sampled_wavelength_obs_angstrom": [
                float(min(row[3].wavelength_obs_angstrom[0] for row in spectra)),
                float(max(row[3].wavelength_obs_angstrom[-1] for row in spectra)),
            ],
            "unextinguished_Flambda_erg_s_cm2_angstrom": [
                float(
                    min(
                        np.min(row[3].flux_lambda_unextinguished_erg_s_cm2_angstrom)
                        for row in spectra
                    )
                ),
                float(
                    max(
                        np.max(row[3].flux_lambda_unextinguished_erg_s_cm2_angstrom)
                        for row in spectra
                    )
                ),
            ],
            "attenuated_Flambda_erg_s_cm2_angstrom": [
                float(
                    min(
                        np.min(row[3].flux_lambda_attenuated_erg_s_cm2_angstrom)
                        for row in spectra
                    )
                ),
                float(
                    max(
                        np.max(row[3].flux_lambda_attenuated_erg_s_cm2_angstrom)
                        for row in spectra
                    )
                ),
            ],
            "spectral_density": "F_lambda per Angstrom",
            "physical_scope": "conditional optical/UV bare-disc spectrum; no physical X-ray claim",
        },
        "numerical_closure": {
            "extinction_spline": (
                "Fitzpatrick 1998 supplies the anchors and cubic-spline construction; "
                "the natural endpoint boundary condition is an explicit implementation choice"
            )
        },
        "validation": {
            "max_bolometric_redshift_distance_relative_residual": float(
                max(bolometric_residuals)
            ),
            "max_lambda_Flambda_to_nu_Fnu_relative_residual": float(
                max(invariant_residuals)
            ),
            "max_zero_extinction_identity_relative_residual": float(
                max(zero_extinction_residuals)
            ),
            "phase4_inherited_max_source_grid_relative_change": 9.052133018270236e-4,
        },
        "open_problems": [
            "real Swift/UVOT effective-area and date-dependent sensitivity folding",
            "host extinction prior and covariance with viewing angle",
            "absolute apsidal-precession solution varpi(t)",
            "physical X-ray atmosphere; the formal high-frequency tail is not used",
        ],
        "runtime_seconds": time.perf_counter() - started,
    }
    (args.output_dir / "phase5a_observer_flambda_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(
        "Phase 5A F_lambda complete: "
        f"D_L={luminosity_distance / MPC_CM:.3f} Mpc, "
        f"max invariant residual={max(invariant_residuals):.3e}",
        flush=True,
    )


if __name__ == "__main__":
    main()
