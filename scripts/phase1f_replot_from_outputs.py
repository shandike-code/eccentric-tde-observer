"""Replot the Phase-1F audit from saved numerical tables without retracing."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


AZIMUTH_DEG = (0, 90, 180)
PROBE_LABELS = ("5e14", "1e16", "5e16", "1e17")
PROBE_FREQUENCY_HZ = np.array([5.0e14, 1.0e16, 5.0e16, 1.0e17])
COLORS = {0: "tab:blue", 90: "tab:orange", 180: "tab:green"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    spectra = np.genfromtxt(
        args.output_dir / "phase1f_adaptive_spectra.csv",
        delimiter=",",
        names=True,
    )
    depth = np.genfromtxt(
        args.output_dir / "phase1f_adaptive_depth_convergence.csv",
        delimiter=",",
        names=True,
    )
    grid = np.genfromtxt(
        args.output_dir / "phase1f_surface_grid_convergence.csv",
        delimiter=",",
        names=True,
    )
    uniform = np.genfromtxt(
        args.output_dir / "phase1e_ray_failure_convergence.csv",
        delimiter=",",
        names=True,
    )

    frequency = spectra["frequency_hz"]
    corrected = spectra["corrected_Lnu_erg_s_hz"]
    depth_ratio = np.column_stack(
        [depth[f"ratio_{label}Hz"] for label in PROBE_LABELS]
    )
    depth_change = np.column_stack(
        [depth[f"step_{label}Hz"] for label in PROBE_LABELS]
    )
    source_grids = np.unique(
        np.column_stack((grid["radial_points"], grid["anomaly_points"])), axis=0
    )
    grid_ratio_phi90 = np.empty((source_grids.shape[0], len(PROBE_LABELS)))
    adaptive_probe = np.empty((len(AZIMUTH_DEG), len(PROBE_LABELS)))
    for grid_index, (radial_points, anomaly_points) in enumerate(source_grids):
        selected = (
            (grid["radial_points"] == radial_points)
            & (grid["anomaly_points"] == anomaly_points)
            & (grid["relative_azimuth_deg"] == 90)
        )
        grid_ratio_phi90[grid_index] = np.array(
            [grid[f"ratio_{label}Hz"][selected][0] for label in PROBE_LABELS]
        )
    for azimuth_index, azimuth_deg in enumerate(AZIMUTH_DEG):
        selected = (
            (grid["radial_points"] == 65)
            & (grid["anomaly_points"] == 1024)
            & (grid["relative_azimuth_deg"] == azimuth_deg)
        )
        adaptive_probe[azimuth_index] = np.array(
            [grid[f"ratio_{label}Hz"][selected][0] for label in PROBE_LABELS]
        )
    adaptive_probe[1] = depth_ratio[-1]

    uniform_probe = np.empty_like(adaptive_probe)
    for azimuth_index, azimuth_deg in enumerate(AZIMUTH_DEG):
        selected = (uniform["relative_azimuth_deg"] == azimuth_deg) & (
            uniform["pixels_long_axis"] == 4096
        )
        uniform_probe[azimuth_index] = np.array(
            [
                uniform[f"ray_to_corrected_{label}Hz"][selected][0]
                for label in PROBE_LABELS
            ]
        )

    figure, axes = plt.subplots(2, 3, figsize=(15.5, 9.0), constrained_layout=True)
    axis = axes[0, 0]
    axis.loglog(frequency, frequency * corrected, color="black", linewidth=2, label="ZO corrected ZO 2022 source")
    for azimuth_deg in AZIMUTH_DEG:
        luminosity = spectra[f"phi{azimuth_deg}_Lnu_iso_erg_s_hz"]
        label = rf"$\phi_{{\rm obs}}-\varpi={azimuth_deg}^\circ$"
        if azimuth_deg == 90:
            axis.loglog(
                frequency,
                frequency * luminosity,
                color=COLORS[azimuth_deg],
                linestyle=":",
                linewidth=2,
                label=label + " (high-$\\nu$ unresolved)",
            )
            resolved = frequency <= 1.0e16
            axis.loglog(
                frequency[resolved],
                frequency[resolved] * luminosity[resolved],
                color=COLORS[azimuth_deg],
                linewidth=2,
            )
        else:
            axis.loglog(
                frequency,
                frequency * luminosity,
                color=COLORS[azimuth_deg],
                linewidth=1.7,
                label=label,
            )
    axis.axvspan(1.0e16, frequency[-1], color="tab:red", alpha=0.06)
    axis.set(
        xlim=(1.0e14, 2.5e18),
        ylim=(1.0e34, 3.0e45),
        xlabel=r"$\nu\ [{\rm Hz}]$",
        ylabel=r"$\nu L_\nu\ [{\rm erg\ s^{-1}}]$",
        title="Conditional observer spectra",
    )
    axis.legend(fontsize=8)

    axis = axes[0, 1]
    for azimuth_deg in AZIMUTH_DEG:
        axis.loglog(
            frequency,
            spectra[f"phi{azimuth_deg}_Lnu_iso_erg_s_hz"] / corrected,
            color=COLORS[azimuth_deg],
            label=f"{azimuth_deg} deg",
        )
    axis.axvspan(1.0e16, frequency[-1], color="tab:red", alpha=0.06)
    axis.set(
        xlim=(1.0e14, 2.5e18),
        ylim=(1.0e-12, 2.0),
        xlabel=r"$\nu\ [{\rm Hz}]$",
        ylabel="observer / corrected ZO 2022",
        title="Orientation transfer",
    )
    axis.legend(fontsize=8)

    axis = axes[0, 2]
    for frequency_index, probe in enumerate(PROBE_FREQUENCY_HZ):
        axis.semilogy(
            depth["maximum_depth"],
            depth_ratio[:, frequency_index],
            marker="o",
            label=f"{probe:.1e} Hz",
        )
    axis.set(xlabel="maximum subdivision depth", ylabel="ray / corrected ZO 2022", title="phi=90 deg adaptive depth")
    axis.legend(fontsize=8)

    axis = axes[1, 0]
    for frequency_index, probe in enumerate(PROBE_FREQUENCY_HZ):
        axis.semilogy(
            depth["maximum_depth"][1:],
            depth_change[1:, frequency_index],
            marker="o",
            label=f"{probe:.1e} Hz",
        )
    axis.axhline(1.0e-2, color="black", linestyle="--", linewidth=1)
    axis.axhline(1.0e-3, color="black", linestyle=":", linewidth=1)
    axis.set(xlabel="maximum subdivision depth", ylabel="fractional step change", title="Depth convergence")
    axis.legend(fontsize=8)

    axis = axes[1, 1]
    grid_labels = [f"{int(radial)}x{int(anomaly)}" for radial, anomaly in source_grids]
    for frequency_index, probe in enumerate(PROBE_FREQUENCY_HZ):
        axis.semilogy(
            grid_labels,
            grid_ratio_phi90[:, frequency_index],
            marker="o",
            label=f"{probe:.1e} Hz",
        )
    axis.set(xlabel="source surface grid", ylabel="ray / corrected ZO 2022", title="phi=90 deg source-grid audit")
    axis.legend(fontsize=8)

    axis = axes[1, 2]
    x = np.arange(PROBE_FREQUENCY_HZ.size)
    width = 0.12
    for azimuth_index, azimuth_deg in enumerate(AZIMUTH_DEG):
        positions = x + (azimuth_index - 1.5) * width
        axis.bar(
            positions,
            adaptive_probe[azimuth_index],
            width,
            color=COLORS[azimuth_deg],
            label=f"adaptive {azimuth_deg} deg",
        )
        axis.scatter(positions, uniform_probe[azimuth_index], color="black", marker="x", s=24)
    axis.set_yscale("log")
    axis.set_xticks(x, PROBE_LABELS)
    axis.set(xlabel=r"$\nu\ [{\rm Hz}]$", ylabel="ray / corrected ZO 2022", title="Adaptive bars; 4096-pixel crosses")
    axis.legend(fontsize=7)

    figure.suptitle(
        "Phase 1F: source-space adaptive occultation (no wind, no frequency shift)",
        fontsize=14,
    )
    figure.savefig(args.output_dir / "phase1f_adaptive_spectrum_audit.png", dpi=180)
    plt.close(figure)


if __name__ == "__main__":
    main()
