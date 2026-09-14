"""Weak-field frequency-shift spectra for the strict-domain bare ZO disc."""

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

from eccentric_tde_observer.adaptive import (
    build_orthographic_triangle_index,
    render_adaptive_source_surface_quadrature,
    render_source_surface_quadrature,
    source_surface_blackbody_sed,
)
from eccentric_tde_observer.diagnostics import fit_isotropic_blackbody_lnu
from eccentric_tde_observer.geometry import build_orbital_surface_mesh
from eccentric_tde_observer.observer import Observer, unobscured_projected_area_cm2
from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.relativity import (
    homologous_vertical_velocity_cm_s,
    straight_ray_frequency_shift,
)
from eccentric_tde_observer.vertical import RADIATION_PRESSURE_POLYTROPE_PROFILE
from eccentric_tde_observer.zo_reference import (
    ZOConstantEParameters,
    build_zo_constant_e_reference_model,
    rescale_constant_e_circularization_efficiency,
)


PARSEC_CM = 3.0856775814913673e18
EV_ERG = 1.602176634e-12
DISTANCE_CM = 100.0e6 * PARSEC_CM
ECCENTRICITY = 0.6
CIRCULARIZATION_EFFICIENCY = 0.01
CLUSTERING_POWER = 5.0
INCLINATION_DEG = (0.0, 30.0, 60.0, 75.0)
PHASE_DEG = tuple(float(value) for value in np.arange(0.0, 360.0, 30.0))
PROBE_FREQUENCY_HZ = np.array([5.0e14, 1.0e15, 2.0e15, 5.0e15, 1.0e16])
COMPARISON_CASES = ((0.0, 0.0), (75.0, 0.0), (75.0, 60.0), (75.0, 90.0),
                    (75.0, 120.0), (75.0, 180.0), (75.0, 270.0))


def _energy_kev_to_frequency_hz(energy_kev: float) -> float:
    return energy_kev * 1.0e3 * EV_ERG / PLANCK_ERG_S


def _integrate_band(
    frequency_hz: np.ndarray,
    luminosity_density: np.ndarray,
    lower_hz: float,
    upper_hz: float,
) -> float:
    selected = (frequency_hz >= lower_hz) & (frequency_hz <= upper_hz)
    if np.count_nonzero(selected) < 2:
        raise RuntimeError("frequency grid does not resolve a diagnostic band")
    value = float(np.trapezoid(luminosity_density[selected], frequency_hz[selected]))
    if not np.isfinite(value) or value < 0.0:
        raise ArithmeticError("band luminosity is invalid")
    return value


def _parameters(eccentricity: float = ECCENTRICITY) -> ZOConstantEParameters:
    return ZOConstantEParameters(
        black_hole_mass_msun=1.0e6,
        stellar_mass_msun=1.0,
        stellar_radius_rsun=1.0,
        circularization_efficiency=1.0,
        outer_to_inner_semimajor_axis=2.0,
        eccentricity=eccentricity,
        opacity_cm2_g=0.34,
    )


def _model(radial_points: int, anomaly_points: int, eccentricity: float = ECCENTRICITY):
    base = build_zo_constant_e_reference_model(
        _parameters(eccentricity),
        radial_points=radial_points,
        anomaly_points=anomaly_points,
        anomaly_sampling="pericentre_clustered",
        pericentre_clustering_power=CLUSTERING_POWER,
    )
    return rescale_constant_e_circularization_efficiency(
        base, CIRCULARIZATION_EFFICIENCY
    )


def _orientation_cases() -> tuple[tuple[float, float], ...]:
    cases: list[tuple[float, float]] = [(0.0, 0.0)]
    for inclination in INCLINATION_DEG[1:]:
        cases.extend((inclination, phase) for phase in PHASE_DEG)
    return tuple(cases)


def _case_label(inclination_deg: float, phase_deg: float) -> str:
    return f"i{int(inclination_deg):02d}_phi{int(phase_deg):03d}"


def _write_dict_rows(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def _shift_fields(model, photosphere, observer):
    vertical_velocity = homologous_vertical_velocity_cm_s(
        model.source,
        photosphere.height_cm,
        model.breathing.log_height_derivative_per_rad,
        model.parameters.black_hole_mass_msun,
    )
    orbital = straight_ray_frequency_shift(
        model.source, observer, model.parameters.black_hole_mass_msun
    )
    full = straight_ray_frequency_shift(
        model.source,
        observer,
        model.parameters.black_hole_mass_msun,
        vertical_velocity_cm_s=vertical_velocity,
    )
    return vertical_velocity, orbital, full


def _one_case(model, photosphere, mesh, frequency, inclination_deg, phase_deg):
    observer = Observer(
        DISTANCE_CM, np.deg2rad(inclination_deg), np.deg2rad(phase_deg)
    )
    triangle_index = build_orthographic_triangle_index(
        mesh, observer, bins_long_axis=256
    )
    quadrature = render_source_surface_quadrature(
        mesh,
        observer,
        subdivision_level=0,
        triangle_index=triangle_index,
    )
    vertical_velocity, orbital_shift, full_shift = _shift_fields(
        model, photosphere, observer
    )
    full_spectrum = source_surface_blackbody_sed(
        model.source,
        mesh,
        observer,
        quadrature,
        frequency,
        frequency_shift_factor=full_shift.frequency_shift_factor,
    )
    unshifted_probe = source_surface_blackbody_sed(
        model.source, mesh, observer, quadrature, PROBE_FREQUENCY_HZ
    )
    orbital_probe = source_surface_blackbody_sed(
        model.source,
        mesh,
        observer,
        quadrature,
        PROBE_FREQUENCY_HZ,
        frequency_shift_factor=orbital_shift.frequency_shift_factor,
    )
    full_probe = source_surface_blackbody_sed(
        model.source,
        mesh,
        observer,
        quadrature,
        PROBE_FREQUENCY_HZ,
        frequency_shift_factor=full_shift.frequency_shift_factor,
    )
    return (
        observer,
        quadrature,
        vertical_velocity,
        orbital_shift,
        full_shift,
        full_spectrum,
        unshifted_probe,
        orbital_probe,
        full_probe,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    uvopt_lower = _energy_kev_to_frequency_hz(0.002)
    uvopt_upper = _energy_kev_to_frequency_hz(0.1)
    xray_lower = _energy_kev_to_frequency_hz(0.3)
    xray_upper = _energy_kev_to_frequency_hz(10.0)
    frequency = np.unique(
        np.concatenate(
            (
                np.geomspace(1.0e14, 2.5e18, 401),
                [uvopt_lower, uvopt_upper, xray_lower, xray_upper],
                PROBE_FREQUENCY_HZ,
            )
        )
    )
    probe_indices = np.searchsorted(frequency, PROBE_FREQUENCY_HZ)
    if not np.array_equal(frequency[probe_indices], PROBE_FREQUENCY_HZ):
        raise RuntimeError("probe frequencies are missing from the SED grid")

    model = _model(65, 1024)
    photosphere = solve_gray_photosphere(
        model.source,
        model.parameters.opacity_cm2_g,
        2.0 / 3.0,
        RADIATION_PRESSURE_POLYTROPE_PROFILE,
    )
    mesh = build_orbital_surface_mesh(model.source, photosphere.height_cm)
    cases = _orientation_cases()
    full_spectra: dict[tuple[float, float], object] = {}
    comparison_spectra: dict[tuple[str, float, float], object] = {}
    diagnostics: list[dict[str, object]] = []
    g_metrics: dict[tuple[float, float], dict[str, float]] = {}

    for inclination_deg, phase_deg in cases:
        (
            observer,
            quadrature,
            vertical_velocity,
            orbital_shift,
            full_shift,
            full_spectrum,
            unshifted_probe,
            orbital_probe,
            full_probe,
        ) = _one_case(
            model,
            photosphere,
            mesh,
            frequency,
            inclination_deg,
            phase_deg,
        )
        full_spectra[(inclination_deg, phase_deg)] = full_spectrum
        weights = quadrature.vertex_projected_area_weights_cm2
        emitting = weights > 0.0
        if not np.any(emitting):
            raise RuntimeError("observer quadrature contains no emitting vertex")
        normalized_weight = weights[emitting] / np.sum(weights[emitting])
        orbital_g = orbital_shift.frequency_shift_factor.reshape(-1)[emitting]
        full_g = full_shift.frequency_shift_factor.reshape(-1)[emitting]
        g_metrics[(inclination_deg, phase_deg)] = {
            "orbital_g_min": float(np.min(orbital_g)),
            "orbital_g_weighted_mean": float(np.sum(normalized_weight * orbital_g)),
            "orbital_g_max": float(np.max(orbital_g)),
            "full_g_min": float(np.min(full_g)),
            "full_g_weighted_mean": float(np.sum(normalized_weight * full_g)),
            "full_g_max": float(np.max(full_g)),
        }
        uvopt = _integrate_band(
            frequency,
            full_spectrum.isotropic_equivalent_lnu_erg_s_hz,
            uvopt_lower,
            uvopt_upper,
        )
        xray = _integrate_band(
            frequency,
            full_spectrum.isotropic_equivalent_lnu_erg_s_hz,
            xray_lower,
            xray_upper,
        )
        blackbody_fit = fit_isotropic_blackbody_lnu(
            frequency,
            full_spectrum.isotropic_equivalent_lnu_erg_s_hz,
            uvopt_lower,
            uvopt_upper,
        )
        visible_fraction = (
            quadrature.visible_projected_area_cm2
            / unobscured_projected_area_cm2(mesh, observer)
        )
        record: dict[str, object] = {
            "inclination_deg": inclination_deg,
            "relative_phase_deg": phase_deg,
            "visible_to_unobscured_projected_area": visible_fraction,
            "uvopt_0p002_0p1keV_erg_s": uvopt,
            "xray_0p3_10keV_erg_s": xray,
            "xray_to_uvopt": xray / uvopt,
            "T_bb_k": blackbody_fit.temperature_k,
            "R_bb_cm": blackbody_fit.radius_cm,
            "blackbody_fit_rms_dex": blackbody_fit.rms_log10_residual_dex,
            "maximum_orbital_beta": float(np.sqrt(np.max(orbital_shift.beta_squared))),
            "maximum_orbital_plus_vertical_beta": float(
                np.sqrt(np.max(full_shift.beta_squared))
            ),
            "maximum_abs_vertical_velocity_cm_s": float(
                np.max(np.abs(vertical_velocity))
            ),
            **g_metrics[(inclination_deg, phase_deg)],
        }
        unshifted_values = unshifted_probe.flux_density_erg_s_cm2_hz
        orbital_values = orbital_probe.flux_density_erg_s_cm2_hz
        full_values = full_probe.flux_density_erg_s_cm2_hz
        for probe_frequency, orbital_ratio, full_ratio, vertical_ratio in zip(
            PROBE_FREQUENCY_HZ,
            orbital_values / unshifted_values,
            full_values / unshifted_values,
            full_values / orbital_values,
            strict=True,
        ):
            suffix = f"{probe_frequency:.1e}_Hz"
            record[f"orbital_shift_to_unshifted_Fnu_at_{suffix}"] = float(orbital_ratio)
            record[f"full_shift_to_unshifted_Fnu_at_{suffix}"] = float(full_ratio)
            record[f"vertical_to_orbital_shift_Fnu_at_{suffix}"] = float(vertical_ratio)
        diagnostics.append(record)

        if (inclination_deg, phase_deg) in COMPARISON_CASES:
            unshifted = source_surface_blackbody_sed(
                model.source, mesh, observer, quadrature, frequency
            )
            orbital = source_surface_blackbody_sed(
                model.source,
                mesh,
                observer,
                quadrature,
                frequency,
                frequency_shift_factor=orbital_shift.frequency_shift_factor,
            )
            comparison_spectra[("unshifted", inclination_deg, phase_deg)] = unshifted
            comparison_spectra[("orbital", inclination_deg, phase_deg)] = orbital
        print(f"Phase2A {_case_label(inclination_deg, phase_deg)} complete", flush=True)

    spectrum_columns = [frequency]
    spectrum_header = ["frequency_hz"]
    for inclination_deg, phase_deg in cases:
        spectrum = full_spectra[(inclination_deg, phase_deg)]
        label = _case_label(inclination_deg, phase_deg)
        spectrum_columns.extend(
            (spectrum.flux_density_erg_s_cm2_hz,
             spectrum.isotropic_equivalent_lnu_erg_s_hz)
        )
        spectrum_header.extend(
            (f"full_shift_{label}_Fnu_cgs", f"full_shift_{label}_Lnu_iso_erg_s_hz")
        )
    for mode in ("unshifted", "orbital"):
        for inclination_deg, phase_deg in COMPARISON_CASES:
            spectrum = comparison_spectra[(mode, inclination_deg, phase_deg)]
            label = _case_label(inclination_deg, phase_deg)
            spectrum_columns.append(spectrum.flux_density_erg_s_cm2_hz)
            spectrum_header.append(f"{mode}_{label}_Fnu_cgs")
    np.savetxt(
        args.output_dir / "phase2a_weakfield_spectra.csv",
        np.column_stack(spectrum_columns),
        delimiter=",",
        header=",".join(spectrum_header),
        comments="",
    )
    _write_dict_rows(
        args.output_dir / "phase2a_orientation_diagnostics.csv", diagnostics
    )

    audit_inclination = 75.0
    audit_phase = 90.0
    audit_observer = Observer(
        DISTANCE_CM, np.deg2rad(audit_inclination), np.deg2rad(audit_phase)
    )
    audit_index = build_orthographic_triangle_index(
        mesh, audit_observer, bins_long_axis=256
    )
    _, _, audit_shift = _shift_fields(model, photosphere, audit_observer)
    convergence_records: list[dict[str, object]] = []
    depth_values: list[np.ndarray] = []
    for depth in (2, 4):
        quadrature = render_adaptive_source_surface_quadrature(
            mesh,
            audit_observer,
            maximum_subdivision_depth=depth,
            triangle_index=audit_index,
            interior_vertex_fraction=0.01,
        )
        spectrum = source_surface_blackbody_sed(
            model.source,
            mesh,
            audit_observer,
            quadrature,
            PROBE_FREQUENCY_HZ,
            frequency_shift_factor=audit_shift.frequency_shift_factor,
        )
        values = spectrum.flux_density_erg_s_cm2_hz
        depth_values.append(values)
        record: dict[str, object] = {
            "audit_type": "adaptive_depth",
            "grid_radial_points": 65,
            "grid_anomaly_points": 1024,
            "maximum_subdivision_depth": depth,
            "ray_count": quadrature.ray_count,
        }
        for probe_frequency, value in zip(PROBE_FREQUENCY_HZ, values, strict=True):
            record[f"Fnu_at_{probe_frequency:.1e}_Hz"] = float(value)
        convergence_records.append(record)
    depth_change = np.abs(depth_values[-1] / depth_values[-2] - 1.0)

    grid_values: list[np.ndarray] = []
    for radial_points, anomaly_points in ((33, 512), (65, 1024), (129, 2048)):
        grid_model = model if radial_points == 65 else _model(radial_points, anomaly_points)
        grid_photosphere = photosphere if radial_points == 65 else solve_gray_photosphere(
            grid_model.source,
            grid_model.parameters.opacity_cm2_g,
            2.0 / 3.0,
            RADIATION_PRESSURE_POLYTROPE_PROFILE,
        )
        grid_mesh = mesh if radial_points == 65 else build_orbital_surface_mesh(
            grid_model.source, grid_photosphere.height_cm
        )
        grid_index = build_orthographic_triangle_index(
            grid_mesh,
            audit_observer,
            bins_long_axis=512 if anomaly_points >= 2048 else 256,
        )
        grid_quadrature = render_source_surface_quadrature(
            grid_mesh,
            audit_observer,
            subdivision_level=0,
            triangle_index=grid_index,
        )
        _, _, grid_shift = _shift_fields(grid_model, grid_photosphere, audit_observer)
        grid_spectrum = source_surface_blackbody_sed(
            grid_model.source,
            grid_mesh,
            audit_observer,
            grid_quadrature,
            PROBE_FREQUENCY_HZ,
            frequency_shift_factor=grid_shift.frequency_shift_factor,
        )
        values = grid_spectrum.flux_density_erg_s_cm2_hz
        grid_values.append(values)
        record = {
            "audit_type": "source_grid",
            "grid_radial_points": radial_points,
            "grid_anomaly_points": anomaly_points,
            "maximum_subdivision_depth": 0,
            "ray_count": grid_quadrature.ray_count,
        }
        for probe_frequency, value in zip(PROBE_FREQUENCY_HZ, values, strict=True):
            record[f"Fnu_at_{probe_frequency:.1e}_Hz"] = float(value)
        convergence_records.append(record)
    grid_change = np.abs(grid_values[-1] / grid_values[-2] - 1.0)
    _write_dict_rows(
        args.output_dir / "phase2a_numerical_convergence.csv", convergence_records
    )

    circular_model = _model(33, 512, eccentricity=0.0)
    circular_photosphere = solve_gray_photosphere(
        circular_model.source,
        circular_model.parameters.opacity_cm2_g,
        2.0 / 3.0,
        RADIATION_PRESSURE_POLYTROPE_PROFILE,
    )
    circular_mesh = build_orbital_surface_mesh(
        circular_model.source, circular_photosphere.height_cm
    )
    circular_values = []
    for phase_deg in (0.0, 90.0):
        observer = Observer(DISTANCE_CM, np.deg2rad(60.0), np.deg2rad(phase_deg))
        index = build_orthographic_triangle_index(circular_mesh, observer, bins_long_axis=128)
        quadrature = render_source_surface_quadrature(
            circular_mesh, observer, subdivision_level=0, triangle_index=index
        )
        _, _, shift = _shift_fields(circular_model, circular_photosphere, observer)
        spectrum = source_surface_blackbody_sed(
            circular_model.source,
            circular_mesh,
            observer,
            quadrature,
            PROBE_FREQUENCY_HZ,
            frequency_shift_factor=shift.frequency_shift_factor,
        )
        circular_values.append(spectrum.flux_density_erg_s_cm2_hz)
    circular_phase_change = np.abs(circular_values[1] / circular_values[0] - 1.0)

    phase75 = [
        record for record in diagnostics if float(record["inclination_deg"]) == 75.0
    ]
    faceon = full_spectra[(0.0, 0.0)].flux_density_erg_s_cm2_hz[probe_indices]
    figure, axes = plt.subplots(2, 3, figsize=(16.2, 9.5), constrained_layout=True)
    figure.suptitle(
        r"Phase 2A: weak-field shifted $F_\nu$ of the strict-domain bare disc",
        fontsize=16,
    )
    axis = axes[0, 0]
    for inclination_deg in INCLINATION_DEG:
        spectrum = full_spectra[(inclination_deg, 0.0)]
        axis.loglog(
            frequency,
            frequency * spectrum.flux_density_erg_s_cm2_hz,
            label=f"i={inclination_deg:.0f} deg",
        )
    axis.set_xlim(1.0e14, 3.0e16)
    axis.set_ylim(1.0e-16, 2.0e-11)
    axis.set_title(r"Actual shifted $\nu F_\nu$ at 100 Mpc, phase 0")
    axis.set_xlabel(r"$\nu_{obs}$ [Hz]")
    axis.set_ylabel(r"$\nu F_\nu$ [erg s$^{-1}$ cm$^{-2}$]")
    axis.legend(fontsize=8)

    axis = axes[0, 1]
    for phase_deg in (0.0, 60.0, 120.0, 180.0):
        spectrum = full_spectra[(75.0, phase_deg)]
        axis.loglog(
            frequency,
            frequency * spectrum.flux_density_erg_s_cm2_hz,
            label=f"phase={phase_deg:.0f} deg",
        )
    axis.set_xlim(1.0e14, 3.0e16)
    axis.set_ylim(1.0e-16, 2.0e-11)
    axis.set_title(r"Shifted precession-phase spectra at $i=75$ deg")
    axis.set_xlabel(r"$\nu_{obs}$ [Hz]")
    axis.set_ylabel(r"$\nu F_\nu$ [erg s$^{-1}$ cm$^{-2}$]")
    axis.legend(fontsize=8)

    axis = axes[0, 2]
    for phase_deg in (0.0, 60.0, 120.0, 180.0):
        full = full_spectra[(75.0, phase_deg)].flux_density_erg_s_cm2_hz
        baseline = comparison_spectra[("unshifted", 75.0, phase_deg)].flux_density_erg_s_cm2_hz
        positive = (baseline > 0.0) & (frequency <= 1.0e16)
        axis.semilogx(
            frequency[positive], full[positive] / baseline[positive],
            label=f"phase={phase_deg:.0f} deg",
        )
    axis.axhline(1.0, color="black", linestyle="--", linewidth=1.0)
    axis.set_xlim(1.0e14, 1.05e16)
    axis.set_ylim(0.5, 1.7)
    axis.set_title(r"Weak-field transfer / unshifted $F_\nu$")
    axis.set_xlabel(r"$\nu_{obs}$ [Hz]")
    axis.set_ylabel("flux ratio")
    axis.legend(fontsize=8)

    axis = axes[1, 0]
    phase_values = np.array([float(record["relative_phase_deg"]) for record in phase75])
    axis.fill_between(
        phase_values,
        [float(record["full_g_min"]) for record in phase75],
        [float(record["full_g_max"]) for record in phase75],
        alpha=0.25,
        label="visible min--max",
    )
    axis.plot(
        phase_values,
        [float(record["full_g_weighted_mean"]) for record in phase75],
        marker="o",
        label="projected-area weighted mean",
    )
    axis.axhline(1.0, color="black", linestyle="--", linewidth=1.0)
    axis.set_title(r"Frequency-shift factor $g$ at $i=75$ deg")
    axis.set_xlabel(r"relative phase $\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel(r"$g=\nu_{obs}/\nu_{em}$")
    axis.legend(fontsize=8)

    axis = axes[1, 1]
    for frequency_index, probe_frequency in enumerate(PROBE_FREQUENCY_HZ[:4]):
        values = np.array([
            full_spectra[(75.0, phase)].flux_density_erg_s_cm2_hz[probe_indices[frequency_index]]
            for phase in PHASE_DEG
        ])
        axis.plot(
            PHASE_DEG, values / faceon[frequency_index], marker="o",
            label=f"{probe_frequency:.1e} Hz",
        )
    axis.set_title(r"Shifted phase response at $i=75$ deg")
    axis.set_xlabel(r"relative phase $\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel(r"$F_\nu/F_{\nu,face-on}$")
    axis.legend(fontsize=8)

    axis = axes[1, 2]
    axis.plot(
        phase_values,
        [float(record["T_bb_k"]) for record in phase75],
        marker="o",
        color="tab:red",
        label=r"$T_{bb}$",
    )
    axis.set_title("UV/opt blackbody diagnostics after weak-field shift")
    axis.set_xlabel(r"relative phase $\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel(r"$T_{bb}$ [K]", color="tab:red")
    axis.tick_params(axis="y", labelcolor="tab:red")
    twin = axis.twinx()
    twin.plot(
        phase_values,
        [float(record["R_bb_cm"]) for record in phase75],
        marker="s",
        color="tab:blue",
        label=r"$R_{bb}$",
    )
    twin.set_ylabel(r"$R_{bb}$ [cm]", color="tab:blue")
    twin.tick_params(axis="y", labelcolor="tab:blue")
    figure.savefig(args.output_dir / "phase2a_weakfield_spectra.png", dpi=180)
    plt.close(figure)

    def _range(key: str) -> list[float]:
        values = np.array([float(record[key]) for record in diagnostics])
        return [float(np.min(values)), float(np.max(values))]

    shift_ratios = []
    vertical_ratios = []
    for record in diagnostics:
        for probe_frequency in PROBE_FREQUENCY_HZ:
            suffix = f"{probe_frequency:.1e}_Hz"
            shift_ratios.append(float(record[f"full_shift_to_unshifted_Fnu_at_{suffix}"]))
            vertical_ratios.append(float(record[f"vertical_to_orbital_shift_Fnu_at_{suffix}"]))
    report = {
        "classification": (
            "Phase 2A weak-field straight-ray transfer [A/V] on the strict-domain "
            "ZO bare-disc source [L]; no wind and no source-field retuning"
        ),
        "model": {
            "eccentricity": ECCENTRICITY,
            "circularization_efficiency": CIRCULARIZATION_EFFICIENCY,
            "black_hole_mass_msun": 1.0e6,
            "source_grid": [65, 1024],
            "distance_mpc": 100.0,
            "vertical_closure": RADIATION_PRESSURE_POLYTROPE_PROFILE.name,
        },
        "transfer_formula": (
            "g=sqrt(1-2GM/(r*c^2))/(gamma*(1-beta_dot_n)); "
            "Iobs_nu=g^3*Iem_(nu/g)=Bnu(nu,g*T_eff)"
        ),
        "observer_ranges_full_shift": {
            "uvopt_erg_s": _range("uvopt_0p002_0p1keV_erg_s"),
            "xray_erg_s": _range("xray_0p3_10keV_erg_s"),
            "xray_to_uvopt": _range("xray_to_uvopt"),
            "T_bb_k": _range("T_bb_k"),
            "R_bb_cm": _range("R_bb_cm"),
            "blackbody_fit_rms_dex": _range("blackbody_fit_rms_dex"),
            "full_g_min": _range("full_g_min"),
            "full_g_weighted_mean": _range("full_g_weighted_mean"),
            "full_g_max": _range("full_g_max"),
        },
        "probe_transfer_ratio_range": [float(np.min(shift_ratios)), float(np.max(shift_ratios))],
        "probe_vertical_increment_ratio_range": [
            float(np.min(vertical_ratios)), float(np.max(vertical_ratios))
        ],
        "maximum_orbital_beta": float(max(record["maximum_orbital_beta"] for record in diagnostics)),
        "maximum_orbital_plus_vertical_beta": float(
            max(record["maximum_orbital_plus_vertical_beta"] for record in diagnostics)
        ),
        "maximum_abs_vertical_velocity_cm_s": float(
            max(record["maximum_abs_vertical_velocity_cm_s"] for record in diagnostics)
        ),
        "self_occultation_detected_to_1e_minus_12_in_projected_area": bool(
            any(float(record["visible_to_unobscured_projected_area"]) < 1.0 - 1.0e-12
                for record in diagnostics)
        ),
        "numerical_validation": {
            "probe_frequency_hz": PROBE_FREQUENCY_HZ.tolist(),
            "adaptive_depth_2_to_4_fractional_change": depth_change.tolist(),
            "source_grid_65x1024_to_129x2048_fractional_change": grid_change.tolist(),
            "circular_e0_phase_0_to_90_fractional_change": circular_phase_change.tolist(),
            "all_listed_changes_below_1e_minus_3": bool(
                np.all(depth_change < 1.0e-3)
                and np.all(grid_change < 1.0e-3)
                and np.all(circular_phase_change < 1.0e-3)
            ),
        },
        "included": [
            "Newtonian eccentric Kepler velocity [A]",
            "ZO homologous vertical breathing velocity [L/A]",
            "special-relativistic longitudinal and transverse Doppler [L/A]",
            "Schwarzschild lapse evaluated on the Newtonian orbit [A]",
            "straight orthographic rays and existing self-occultation test [A/V]",
        ],
        "not_included": [
            "light bending and a Cunningham-style relativistic image-plane Jacobian",
            "light-travel-time delays",
            "black-hole spin and frame dragging",
            "post-Newtonian correction to the eccentric orbit",
            "relativistic moving-surface apparent-area correction",
            "frequency-dependent opacity, absorption, or scattering atmosphere",
            "disc wind or any free reprocessing layer",
        ],
        "disc_wind_applied": False,
        "source_effective_temperature_modified": False,
        "wall_time_seconds": time.perf_counter() - start,
    }
    (args.output_dir / "phase2a_weakfield_spectra_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["numerical_validation"], indent=2), flush=True)


if __name__ == "__main__":
    main()
