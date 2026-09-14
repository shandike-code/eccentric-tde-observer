"""Phase 2B：严格域裸盘的连续谱 opacity 与热化深度审计。"""

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

from eccentric_tde_observer.atmosphere import (
    SOLAR_FULLY_IONIZED_H_HE,
    effective_optical_depth_to_midplane,
    solve_peak_thermalization_closure,
)
from eccentric_tde_observer.quadrature import corrected_zo_area_weights
from eccentric_tde_observer.reference_case import (
    STRICT_CIRCULARIZATION_EFFICIENCY,
    STRICT_ECCENTRICITY,
    build_strict_domain_reference_model,
)


PROBE_FREQUENCY_HZ = np.array(
    [5.0e14, 1.0e15, 2.0e15, 5.0e15, 1.0e16, 7.254e16, 2.418e18]
)


def _weighted_quantile(
    values: np.ndarray, weights: np.ndarray, quantile: float
) -> float:
    order = np.argsort(values)
    sorted_values = values[order]
    sorted_weights = weights[order]
    cumulative = np.cumsum(sorted_weights)
    target = float(quantile) * float(cumulative[-1])
    index = int(np.searchsorted(cumulative, target, side="left"))
    return float(sorted_values[index])


def _write_records(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    model = build_strict_domain_reference_model(65, 1024)
    source = model.source
    frequency = np.unique(
        np.concatenate((np.geomspace(1.0e14, 2.5e18, 81), PROBE_FREQUENCY_HZ))
    )
    audit = effective_optical_depth_to_midplane(
        source,
        frequency,
        electron_scattering_opacity_cm2_g=model.parameters.opacity_cm2_g,
        target_effective_optical_depth=1.0,
        vertical_points=129,
    )
    thermalization = solve_peak_thermalization_closure(
        source,
        electron_scattering_opacity_cm2_g=model.parameters.opacity_cm2_g,
        target_effective_optical_depth=1.0,
        vertical_points=257,
    )
    area_weight = corrected_zo_area_weights(source).reshape(-1)
    normalized_area_weight = area_weight / np.sum(area_weight)

    frequency_records: list[dict[str, object]] = []
    quantile_10 = []
    quantile_50 = []
    quantile_90 = []
    thick_fraction = []
    for index, nu in enumerate(frequency):
        values = audit.midplane_effective_optical_depth[..., index].reshape(-1)
        q10 = _weighted_quantile(values, area_weight, 0.10)
        q50 = _weighted_quantile(values, area_weight, 0.50)
        q90 = _weighted_quantile(values, area_weight, 0.90)
        fraction = float(np.sum(normalized_area_weight[values >= 1.0]))
        quantile_10.append(q10)
        quantile_50.append(q50)
        quantile_90.append(q90)
        thick_fraction.append(fraction)
        frequency_records.append(
            {
                "frequency_hz": float(nu),
                "tau_eff_min": float(np.min(values)),
                "tau_eff_area_q10": q10,
                "tau_eff_area_q50": q50,
                "tau_eff_area_q90": q90,
                "tau_eff_max": float(np.max(values)),
                "corrected_area_fraction_tau_eff_ge_1": fraction,
            }
        )
    _write_records(args.output_dir / "phase2b_frequency_opacity_audit.csv", frequency_records)

    semimajor_axis = np.broadcast_to(
        source.semimajor_axis_cm[:, None], source.shape
    )
    anomaly = np.broadcast_to(
        source.eccentric_anomaly_rad[None, :], source.shape
    )
    cell_columns = np.column_stack(
        (
            semimajor_axis.reshape(-1),
            anomaly.reshape(-1),
            source.surface_density_g_cm2.reshape(-1),
            source.scale_height_cm.reshape(-1),
            source.effective_temperature_k.reshape(-1),
            thermalization.peak_frequency_hz.reshape(-1),
            thermalization.midplane_effective_optical_depth.reshape(-1),
            thermalization.thermalization_scaled_height.reshape(-1),
            thermalization.thermalization_scattering_optical_depth.reshape(-1),
            thermalization.thermalization_temperature_k.reshape(-1),
            thermalization.spectral_hardening_factor.reshape(-1),
        )
    )
    np.savetxt(
        args.output_dir / "phase2b_thermalization_cells.csv",
        cell_columns,
        delimiter=",",
        header=(
            "semimajor_axis_cm,eccentric_anomaly_rad,surface_density_g_cm2,"
            "scale_height_cm,effective_temperature_k,peak_frequency_hz,"
            "peak_midplane_tau_eff,thermalization_scaled_height,"
            "thermalization_tau_es,thermalization_temperature_k,"
            "spectral_hardening_factor"
        ),
        comments="",
    )

    # 中文：分别改变垂向积分点数和 tau_eff 阈值，不能把二者混成一个误差。
    closure_129 = solve_peak_thermalization_closure(source, vertical_points=129)
    closure_513 = solve_peak_thermalization_closure(source, vertical_points=513)
    closure_target_two_thirds = solve_peak_thermalization_closure(
        source, target_effective_optical_depth=2.0 / 3.0, vertical_points=257
    )
    probe_129 = effective_optical_depth_to_midplane(
        source, PROBE_FREQUENCY_HZ, vertical_points=129
    )
    probe_257 = effective_optical_depth_to_midplane(
        source, PROBE_FREQUENCY_HZ, vertical_points=257
    )
    fcol_257 = thermalization.spectral_hardening_factor
    fcol_grid_change = np.abs(
        closure_513.spectral_hardening_factor / fcol_257 - 1.0
    )
    tau_grid_change = np.abs(
        probe_257.midplane_effective_optical_depth
        / probe_129.midplane_effective_optical_depth
        - 1.0
    )
    target_change = np.abs(
        closure_target_two_thirds.spectral_hardening_factor / fcol_257 - 1.0
    )

    figure, axes = plt.subplots(2, 2, figsize=(13.5, 10.0), constrained_layout=True)
    figure.suptitle("Phase 2B: bare-disc continuum thermalization audit", fontsize=16)
    axis = axes[0, 0]
    axis.loglog(frequency, quantile_10, label="corrected ZO-area q10")
    axis.loglog(frequency, quantile_50, label="corrected ZO-area median")
    axis.loglog(frequency, quantile_90, label="corrected ZO-area q90")
    axis.axhline(1.0, color="black", linestyle="--", linewidth=1.0)
    axis.set_xlabel(r"$\nu$ [Hz]")
    axis.set_ylabel(r"midplane $\tau_{\rm eff,\nu}$")
    axis.set_title("Free-free absorption + electron scattering")
    axis.legend(fontsize=8)

    axis = axes[0, 1]
    axis.semilogx(frequency, thick_fraction)
    axis.axhline(0.99, color="black", linestyle="--", linewidth=1.0)
    axis.axvline(7.254e16, color="tab:red", linestyle=":", label="0.3 keV")
    axis.set_ylim(-0.03, 1.03)
    axis.set_xlabel(r"$\nu$ [Hz]")
    axis.set_ylabel(r"corrected ZO-area fraction with $\tau_{eff}\geq1$")
    axis.set_title("Frequency domain where a thermalized continuum exists")
    axis.legend(fontsize=8)

    axis = axes[1, 0]
    image = axis.pcolormesh(
        np.rad2deg(source.eccentric_anomaly_rad),
        source.semimajor_axis_cm / source.semimajor_axis_cm[0],
        fcol_257,
        shading="auto",
        cmap="viridis",
    )
    figure.colorbar(image, ax=axis, label=r"$f_{col}$")
    axis.set_xlabel(r"eccentric anomaly $E$ [deg]")
    axis.set_ylabel(r"$a/a_{in}$")
    axis.set_title(r"Peak-thermalization hardening map")

    axis = axes[1, 1]
    plot = axis.hexbin(
        source.effective_temperature_k.reshape(-1),
        fcol_257.reshape(-1),
        C=np.log10(source.surface_density_g_cm2.reshape(-1)),
        reduce_C_function=np.mean,
        gridsize=45,
        mincnt=1,
        cmap="plasma",
    )
    figure.colorbar(plot, ax=axis, label=r"mean $\log_{10}\Sigma$ [g cm$^{-2}$]")
    axis.set_xlabel(r"$T_{eff}$ [K]")
    axis.set_ylabel(r"$f_{col}$")
    axis.set_title("Hardening is derived, not fitted")
    figure.savefig(args.output_dir / "phase2b_atmosphere_audit.png", dpi=180)
    plt.close(figure)

    probe_records = []
    for probe_index, nu in enumerate(PROBE_FREQUENCY_HZ):
        values = probe_257.midplane_effective_optical_depth[..., probe_index]
        probe_records.append(
            {
                "frequency_hz": float(nu),
                "tau_eff_min": float(np.min(values)),
                "tau_eff_max": float(np.max(values)),
                "corrected_area_fraction_tau_eff_ge_1": float(
                    np.sum(normalized_area_weight[values.reshape(-1) >= 1.0])
                ),
                "vertical_129_to_257_max_fractional_change": float(
                    np.max(tau_grid_change[..., probe_index])
                ),
            }
        )
    _write_records(args.output_dir / "phase2b_probe_opacity_audit.csv", probe_records)

    report = {
        "classification": (
            "Phase 2B bare-disc continuum opacity and thermalization audit [A/V]; "
            "not an NLTE atmosphere"
        ),
        "source": {
            "eccentricity": STRICT_ECCENTRICITY,
            "circularization_efficiency": STRICT_CIRCULARIZATION_EFFICIENCY,
            "grid": [65, 1024],
        },
        "opacity_closure": {
            "electron_scattering_cm2_g": model.parameters.opacity_cm2_g,
            "free_free_formula": (
                "Rybicki-Lightman thermal free-free with stimulated emission"
            ),
            "hydrogen_mass_fraction": SOLAR_FULLY_IONIZED_H_HE.hydrogen_mass_fraction,
            "helium_mass_fraction": SOLAR_FULLY_IONIZED_H_HE.helium_mass_fraction,
            "gaunt_factor": SOLAR_FULLY_IONIZED_H_HE.free_free_gaunt_factor,
            "effective_depth_integrand": "rho*sqrt(3*kabs*(kabs+kes))",
            "gray_temperature_profile": "T^4=(3/4)*Teff^4*(tau_es+2/3)",
        },
        "peak_thermalization": {
            "all_cells_effectively_thick": True,
            "midplane_tau_eff_range": [
                float(np.min(thermalization.midplane_effective_optical_depth)),
                float(np.max(thermalization.midplane_effective_optical_depth)),
            ],
            "thermalization_zeta_range": [
                float(np.min(thermalization.thermalization_scaled_height)),
                float(np.max(thermalization.thermalization_scaled_height)),
            ],
            "thermalization_tau_es_range": [
                float(np.min(thermalization.thermalization_scattering_optical_depth)),
                float(np.max(thermalization.thermalization_scattering_optical_depth)),
            ],
            "f_col_range": [float(np.min(fcol_257)), float(np.max(fcol_257))],
        },
        "probe_frequency_audit": probe_records,
        "numerical_validation": {
            "f_col_vertical_257_to_513_max_fractional_change": float(
                np.max(fcol_grid_change)
            ),
            "tau_eff_vertical_129_to_257_max_fractional_change": float(
                np.max(tau_grid_change)
            ),
            "target_tau_eff_1_to_2over3_fcol_max_fractional_change": float(
                np.max(target_change)
            ),
        },
        "observable_domain_statement": (
            "The derived hardening closure is anchored where each local Bnu peak "
            "thermalizes. Frequencies with tau_eff<1 are audit failures and the "
            "diluted-blackbody tail there is not a physical prediction."
        ),
        "not_included": [
            "bound-free and bound-bound opacity",
            "LTE or NLTE ionization balance",
            "Compton energy exchange",
            "non-gray radiative-equilibrium temperature iteration",
            "limb darkening or polarization",
            "disc wind or external reprocessing layer",
        ],
        "wall_time_seconds": time.perf_counter() - start,
    }
    (args.output_dir / "phase2b_atmosphere_audit_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["peak_thermalization"], indent=2), flush=True)


if __name__ == "__main__":
    main()
