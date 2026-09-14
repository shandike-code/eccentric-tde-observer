"""Phase 2C：热化深度锚定的能量守恒 modified-blackbody 观察者谱。"""

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
from eccentric_tde_observer.atmosphere import solve_peak_thermalization_closure
from eccentric_tde_observer.diagnostics import fit_isotropic_blackbody_lnu
from eccentric_tde_observer.geometry import build_orbital_surface_mesh
from eccentric_tde_observer.observer import Observer, unobscured_projected_area_cm2
from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.reference_case import (
    STRICT_CIRCULARIZATION_EFFICIENCY,
    STRICT_ECCENTRICITY,
    build_strict_domain_reference_model,
)
from eccentric_tde_observer.relativity import (
    homologous_vertical_velocity_cm_s,
    straight_ray_frequency_shift,
)
from eccentric_tde_observer.vertical import RADIATION_PRESSURE_POLYTROPE_PROFILE


PARSEC_CM = 3.0856775814913673e18
EV_ERG = 1.602176634e-12
DISTANCE_CM = 100.0e6 * PARSEC_CM
INCLINATION_DEG = (0.0, 30.0, 60.0, 75.0)
PHASE_DEG = tuple(float(value) for value in np.arange(0.0, 360.0, 30.0))
PROBE_FREQUENCY_HZ = np.array([5.0e14, 1.0e15, 2.0e15, 5.0e15, 1.0e16])
COMPARISON_CASES = (
    (0.0, 0.0),
    (75.0, 0.0),
    (75.0, 60.0),
    (75.0, 90.0),
    (75.0, 120.0),
    (75.0, 180.0),
    (75.0, 270.0),
)


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


def _orientation_cases() -> tuple[tuple[float, float], ...]:
    cases: list[tuple[float, float]] = [(0.0, 0.0)]
    for inclination in INCLINATION_DEG[1:]:
        cases.extend((inclination, phase) for phase in PHASE_DEG)
    return tuple(cases)


def _case_label(inclination_deg: float, phase_deg: float) -> str:
    return f"i{int(inclination_deg):02d}_phi{int(phase_deg):03d}"


def _write_records(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def _photosphere_and_mesh(model):
    photosphere = solve_gray_photosphere(
        model.source,
        model.parameters.opacity_cm2_g,
        2.0 / 3.0,
        RADIATION_PRESSURE_POLYTROPE_PROFILE,
    )
    mesh = build_orbital_surface_mesh(model.source, photosphere.height_cm)
    return photosphere, mesh


def _full_shift(model, photosphere, observer):
    vertical_velocity = homologous_vertical_velocity_cm_s(
        model.source,
        photosphere.height_cm,
        model.breathing.log_height_derivative_per_rad,
        model.parameters.black_hole_mass_msun,
    )
    return straight_ray_frequency_shift(
        model.source,
        observer,
        model.parameters.black_hole_mass_msun,
        vertical_velocity_cm_s=vertical_velocity,
    )


def _surface_quadrature(mesh, observer, bins_long_axis: int = 256):
    index = build_orthographic_triangle_index(
        mesh, observer, bins_long_axis=bins_long_axis
    )
    quadrature = render_source_surface_quadrature(
        mesh, observer, subdivision_level=0, triangle_index=index
    )
    return index, quadrature


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
    conservative_optical_lower = 5.0e14
    conservative_optical_upper = 1.0e15
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

    model = build_strict_domain_reference_model(65, 1024)
    photosphere, mesh = _photosphere_and_mesh(model)
    closure = solve_peak_thermalization_closure(
        model.source,
        electron_scattering_opacity_cm2_g=model.parameters.opacity_cm2_g,
        target_effective_optical_depth=1.0,
        vertical_points=257,
    )
    closure_two_thirds = solve_peak_thermalization_closure(
        model.source,
        electron_scattering_opacity_cm2_g=model.parameters.opacity_cm2_g,
        target_effective_optical_depth=2.0 / 3.0,
        vertical_points=257,
    )

    spectra: dict[tuple[float, float], object] = {}
    comparison_spectra: dict[tuple[float, float], object] = {}
    diagnostics: list[dict[str, object]] = []
    audit_objects = None
    for inclination_deg, phase_deg in _orientation_cases():
        observer = Observer(
            DISTANCE_CM, np.deg2rad(inclination_deg), np.deg2rad(phase_deg)
        )
        index, quadrature = _surface_quadrature(mesh, observer)
        shift = _full_shift(model, photosphere, observer)
        spectrum = source_surface_blackbody_sed(
            model.source,
            mesh,
            observer,
            quadrature,
            frequency,
            frequency_shift_factor=shift.frequency_shift_factor,
            spectral_hardening_factor=closure.spectral_hardening_factor,
        )
        spectra[(inclination_deg, phase_deg)] = spectrum
        blackbody_probe = source_surface_blackbody_sed(
            model.source,
            mesh,
            observer,
            quadrature,
            PROBE_FREQUENCY_HZ,
            frequency_shift_factor=shift.frequency_shift_factor,
        )
        modified_probe = source_surface_blackbody_sed(
            model.source,
            mesh,
            observer,
            quadrature,
            PROBE_FREQUENCY_HZ,
            frequency_shift_factor=shift.frequency_shift_factor,
            spectral_hardening_factor=closure.spectral_hardening_factor,
        )
        target_probe = source_surface_blackbody_sed(
            model.source,
            mesh,
            observer,
            quadrature,
            PROBE_FREQUENCY_HZ,
            frequency_shift_factor=shift.frequency_shift_factor,
            spectral_hardening_factor=closure_two_thirds.spectral_hardening_factor,
        )

        if (inclination_deg, phase_deg) in COMPARISON_CASES:
            comparison_spectra[(inclination_deg, phase_deg)] = source_surface_blackbody_sed(
                model.source,
                mesh,
                observer,
                quadrature,
                frequency,
                frequency_shift_factor=shift.frequency_shift_factor,
            )

        luminosity = spectrum.isotropic_equivalent_lnu_erg_s_hz
        optical = _integrate_band(
            frequency,
            luminosity,
            conservative_optical_lower,
            conservative_optical_upper,
        )
        formal_uvopt = _integrate_band(
            frequency, luminosity, uvopt_lower, uvopt_upper
        )
        formal_xray = _integrate_band(
            frequency, luminosity, xray_lower, xray_upper
        )
        optical_fit = fit_isotropic_blackbody_lnu(
            frequency,
            luminosity,
            conservative_optical_lower,
            conservative_optical_upper,
        )
        formal_uvopt_fit = fit_isotropic_blackbody_lnu(
            frequency, luminosity, uvopt_lower, uvopt_upper
        )
        record: dict[str, object] = {
            "inclination_deg": inclination_deg,
            "relative_phase_deg": phase_deg,
            "visible_to_unobscured_projected_area": (
                quadrature.visible_projected_area_cm2
                / unobscured_projected_area_cm2(mesh, observer)
            ),
            "thermalized_optical_5e14_1e15_erg_s": optical,
            "formal_uvopt_0p002_0p1keV_erg_s": formal_uvopt,
            "formal_xray_0p3_10keV_erg_s": formal_xray,
            "formal_xray_to_thermalized_optical": formal_xray / optical,
            "thermalized_optical_T_bb_k": optical_fit.temperature_k,
            "thermalized_optical_R_bb_cm": optical_fit.radius_cm,
            "thermalized_optical_fit_rms_dex": optical_fit.rms_log10_residual_dex,
            "formal_uvopt_T_bb_k": formal_uvopt_fit.temperature_k,
            "formal_uvopt_R_bb_cm": formal_uvopt_fit.radius_cm,
            "formal_uvopt_fit_rms_dex": formal_uvopt_fit.rms_log10_residual_dex,
            "xray_transfer_physically_valid": False,
        }
        for nu, hardening_ratio, target_ratio in zip(
            PROBE_FREQUENCY_HZ,
            modified_probe.flux_density_erg_s_cm2_hz
            / blackbody_probe.flux_density_erg_s_cm2_hz,
            target_probe.flux_density_erg_s_cm2_hz
            / modified_probe.flux_density_erg_s_cm2_hz,
            strict=True,
        ):
            suffix = f"{nu:.1e}_Hz"
            record[f"modified_to_blackbody_Fnu_at_{suffix}"] = float(
                hardening_ratio
            )
            record[f"tau_target_2over3_to_1_Fnu_at_{suffix}"] = float(
                target_ratio
            )
        diagnostics.append(record)
        if inclination_deg == 75.0 and phase_deg == 90.0:
            audit_objects = (observer, index, quadrature, shift, spectrum)
        print(f"Phase2C {_case_label(inclination_deg, phase_deg)} complete", flush=True)

    if audit_objects is None:
        raise RuntimeError("numerical audit orientation was not generated")
    _write_records(
        args.output_dir / "phase2c_orientation_diagnostics.csv", diagnostics
    )

    spectrum_columns = [frequency]
    spectrum_header = ["frequency_hz"]
    for inclination_deg, phase_deg in _orientation_cases():
        label = _case_label(inclination_deg, phase_deg)
        spectrum = spectra[(inclination_deg, phase_deg)]
        spectrum_columns.extend(
            (
                spectrum.flux_density_erg_s_cm2_hz,
                spectrum.isotropic_equivalent_lnu_erg_s_hz,
            )
        )
        spectrum_header.extend(
            (
                f"modified_{label}_Fnu_cgs",
                f"modified_{label}_Lnu_iso_erg_s_hz",
            )
        )
    for inclination_deg, phase_deg in COMPARISON_CASES:
        label = _case_label(inclination_deg, phase_deg)
        spectrum_columns.append(
            comparison_spectra[(inclination_deg, phase_deg)].flux_density_erg_s_cm2_hz
        )
        spectrum_header.append(f"blackbody_shifted_{label}_Fnu_cgs")
    np.savetxt(
        args.output_dir / "phase2c_modified_blackbody_spectra.csv",
        np.column_stack(spectrum_columns),
        delimiter=",",
        header=",".join(spectrum_header),
        comments="",
    )

    audit_observer, audit_index, audit_quadrature, audit_shift, audit_spectrum = audit_objects
    convergence_records: list[dict[str, object]] = []

    closure_513 = solve_peak_thermalization_closure(
        model.source, vertical_points=513
    )
    vertical_spectrum = source_surface_blackbody_sed(
        model.source,
        mesh,
        audit_observer,
        audit_quadrature,
        PROBE_FREQUENCY_HZ,
        frequency_shift_factor=audit_shift.frequency_shift_factor,
        spectral_hardening_factor=closure_513.spectral_hardening_factor,
    )
    main_probe = audit_spectrum.flux_density_erg_s_cm2_hz[probe_indices]
    vertical_change = np.abs(
        vertical_spectrum.flux_density_erg_s_cm2_hz / main_probe - 1.0
    )

    depth_values = []
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
            spectral_hardening_factor=closure.spectral_hardening_factor,
        )
        values = spectrum.flux_density_erg_s_cm2_hz
        depth_values.append(values)
        record: dict[str, object] = {
            "audit_type": "adaptive_depth",
            "grid_radial_points": 65,
            "grid_anomaly_points": 1024,
            "audit_value": depth,
        }
        for nu, value in zip(PROBE_FREQUENCY_HZ, values, strict=True):
            record[f"Fnu_at_{nu:.1e}_Hz"] = float(value)
        convergence_records.append(record)
    depth_change = np.abs(depth_values[-1] / depth_values[-2] - 1.0)

    grid_values = []
    for radial_points, anomaly_points in ((33, 512), (65, 1024), (129, 2048)):
        grid_model = model if radial_points == 65 else build_strict_domain_reference_model(
            radial_points, anomaly_points
        )
        grid_photosphere, grid_mesh = (
            (photosphere, mesh)
            if radial_points == 65
            else _photosphere_and_mesh(grid_model)
        )
        grid_closure = closure if radial_points == 65 else solve_peak_thermalization_closure(
            grid_model.source, vertical_points=257
        )
        grid_observer = Observer(DISTANCE_CM, np.deg2rad(75.0), np.deg2rad(90.0))
        _, grid_quadrature = _surface_quadrature(
            grid_mesh,
            grid_observer,
            bins_long_axis=512 if anomaly_points >= 2048 else 256,
        )
        grid_shift = _full_shift(grid_model, grid_photosphere, grid_observer)
        grid_spectrum = source_surface_blackbody_sed(
            grid_model.source,
            grid_mesh,
            grid_observer,
            grid_quadrature,
            PROBE_FREQUENCY_HZ,
            frequency_shift_factor=grid_shift.frequency_shift_factor,
            spectral_hardening_factor=grid_closure.spectral_hardening_factor,
        )
        values = grid_spectrum.flux_density_erg_s_cm2_hz
        grid_values.append(values)
        record = {
            "audit_type": "source_grid",
            "grid_radial_points": radial_points,
            "grid_anomaly_points": anomaly_points,
            "audit_value": 0,
        }
        for nu, value in zip(PROBE_FREQUENCY_HZ, values, strict=True):
            record[f"Fnu_at_{nu:.1e}_Hz"] = float(value)
        convergence_records.append(record)
    grid_change = np.abs(grid_values[-1] / grid_values[-2] - 1.0)

    circular_model = build_strict_domain_reference_model(33, 512, eccentricity=0.0)
    circular_photosphere, circular_mesh = _photosphere_and_mesh(circular_model)
    circular_closure = solve_peak_thermalization_closure(circular_model.source)
    circular_values = []
    for phase_deg in (0.0, 90.0):
        observer = Observer(DISTANCE_CM, np.deg2rad(60.0), np.deg2rad(phase_deg))
        _, quadrature = _surface_quadrature(circular_mesh, observer, 128)
        shift = _full_shift(circular_model, circular_photosphere, observer)
        spectrum = source_surface_blackbody_sed(
            circular_model.source,
            circular_mesh,
            observer,
            quadrature,
            PROBE_FREQUENCY_HZ,
            frequency_shift_factor=shift.frequency_shift_factor,
            spectral_hardening_factor=circular_closure.spectral_hardening_factor,
        )
        circular_values.append(spectrum.flux_density_erg_s_cm2_hz)
    circular_change = np.abs(circular_values[1] / circular_values[0] - 1.0)
    _write_records(
        args.output_dir / "phase2c_numerical_convergence.csv", convergence_records
    )

    phase75_records = [
        record for record in diagnostics if float(record["inclination_deg"]) == 75.0
    ]
    faceon_probe = spectra[(0.0, 0.0)].flux_density_erg_s_cm2_hz[probe_indices]
    figure, axes = plt.subplots(2, 3, figsize=(16.2, 9.5), constrained_layout=True)
    figure.suptitle(
        "Phase 2C: thermalization-anchored modified-blackbody observer spectra",
        fontsize=16,
    )
    axis = axes[0, 0]
    for inclination_deg in INCLINATION_DEG:
        spectrum = spectra[(inclination_deg, 0.0)]
        axis.loglog(
            frequency,
            frequency * spectrum.flux_density_erg_s_cm2_hz,
            label=f"i={inclination_deg:.0f} deg",
        )
    axis.axvline(1.0e15, color="black", linestyle=":", linewidth=1.0)
    axis.set_xlim(1.0e14, 3.0e16)
    axis.set_ylim(1.0e-16, 2.0e-11)
    axis.set_title(r"Actual $\nu F_\nu$ at 100 Mpc; dotted = conservative limit")
    axis.set_xlabel(r"$\nu_{obs}$ [Hz]")
    axis.set_ylabel(r"$\nu F_\nu$ [erg s$^{-1}$ cm$^{-2}$]")
    axis.legend(fontsize=8)

    axis = axes[0, 1]
    for phase_deg in (0.0, 60.0, 120.0, 180.0):
        spectrum = spectra[(75.0, phase_deg)]
        axis.loglog(
            frequency,
            frequency * spectrum.flux_density_erg_s_cm2_hz,
            label=f"phase={phase_deg:.0f} deg",
        )
    axis.axvline(1.0e15, color="black", linestyle=":", linewidth=1.0)
    axis.set_xlim(1.0e14, 3.0e16)
    axis.set_ylim(1.0e-16, 2.0e-11)
    axis.set_title(r"Precession phase at $i=75$ deg")
    axis.set_xlabel(r"$\nu_{obs}$ [Hz]")
    axis.set_ylabel(r"$\nu F_\nu$ [erg s$^{-1}$ cm$^{-2}$]")
    axis.legend(fontsize=8)

    axis = axes[0, 2]
    for phase_deg in (0.0, 60.0, 120.0, 180.0):
        modified = spectra[(75.0, phase_deg)].flux_density_erg_s_cm2_hz
        blackbody = comparison_spectra[(75.0, phase_deg)].flux_density_erg_s_cm2_hz
        selected = (blackbody > 0.0) & (frequency <= 1.0e16)
        axis.semilogx(
            frequency[selected], modified[selected] / blackbody[selected],
            label=f"phase={phase_deg:.0f} deg",
        )
    axis.axhline(1.0, color="black", linestyle="--", linewidth=1.0)
    axis.axvspan(1.0e15, 1.0e16, color="tab:orange", alpha=0.12, label="partly thin")
    axis.set_xlim(1.0e14, 1.05e16)
    axis.set_ylim(0.0, 13.0)
    axis.set_title("Modified / local-blackbody flux")
    axis.set_xlabel(r"$\nu_{obs}$ [Hz]")
    axis.set_ylabel("flux ratio")
    axis.legend(fontsize=7)

    axis = axes[1, 0]
    line_styles = ("-", "-", "--", ":")
    for frequency_index, (nu, line_style) in enumerate(
        zip(PROBE_FREQUENCY_HZ[:4], line_styles, strict=True)
    ):
        values = np.array([
            spectra[(75.0, phase)].flux_density_erg_s_cm2_hz[
                probe_indices[frequency_index]
            ]
            for phase in PHASE_DEG
        ])
        axis.plot(
            PHASE_DEG,
            values / faceon_probe[frequency_index],
            marker="o",
            linestyle=line_style,
            label=f"{nu:.1e} Hz",
        )
    axis.set_title("Phase response; dashed/dotted frequencies are partly thin")
    axis.set_xlabel(r"relative phase $\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel(r"$F_\nu/F_{\nu,face-on}$")
    axis.legend(fontsize=8)

    phase_values = [float(record["relative_phase_deg"]) for record in phase75_records]
    axis = axes[1, 1]
    axis.plot(
        phase_values,
        [float(record["thermalized_optical_T_bb_k"]) for record in phase75_records],
        marker="o",
        color="tab:red",
    )
    axis.set_xlabel(r"relative phase $\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel(r"conservative $T_{bb}$ [K]", color="tab:red")
    axis.tick_params(axis="y", labelcolor="tab:red")
    twin = axis.twinx()
    twin.plot(
        phase_values,
        [float(record["thermalized_optical_R_bb_cm"]) for record in phase75_records],
        marker="s",
        color="tab:blue",
    )
    twin.set_ylabel(r"conservative $R_{bb}$ [cm]", color="tab:blue")
    twin.tick_params(axis="y", labelcolor="tab:blue")
    axis.set_title(r"Blackbody fit restricted to $5e14--1e15$ Hz")

    axis = axes[1, 2]
    axis.semilogy(
        phase_values,
        [float(record["formal_xray_to_thermalized_optical"]) for record in phase75_records],
        marker="o",
        color="tab:red",
    )
    axis.set_xlabel(r"relative phase $\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel(r"formal $L_X/L_{opt}$")
    axis.set_title(r"NOT a prediction: $\tau_{eff}<1$ throughout X-ray band")
    figure.savefig(args.output_dir / "phase2c_modified_blackbody_spectra.png", dpi=180)
    plt.close(figure)

    def _range(key: str) -> list[float]:
        values = np.array([float(record[key]) for record in diagnostics])
        return [float(np.min(values)), float(np.max(values))]

    hardening_ratios = []
    target_ratios = []
    for record in diagnostics:
        for nu in PROBE_FREQUENCY_HZ:
            suffix = f"{nu:.1e}_Hz"
            hardening_ratios.append(float(record[f"modified_to_blackbody_Fnu_at_{suffix}"]))
            target_ratios.append(float(record[f"tau_target_2over3_to_1_Fnu_at_{suffix}"]))
    phase_modulation = {}
    for frequency_index, nu in enumerate(PROBE_FREQUENCY_HZ):
        values = np.array([
            spectra[(75.0, phase)].flux_density_erg_s_cm2_hz[probe_indices[frequency_index]]
            for phase in PHASE_DEG
        ])
        phase_modulation[f"{nu:.1e}_Hz"] = float(np.max(values) / np.min(values))

    report = {
        "classification": (
            "Phase 2C conditional energy-conserving modified-blackbody observer "
            "spectrum [A/V]; X-ray tail explicitly outside the closure domain"
        ),
        "source": {
            "eccentricity": STRICT_ECCENTRICITY,
            "circularization_efficiency": STRICT_CIRCULARIZATION_EFFICIENCY,
            "grid": [65, 1024],
            "distance_mpc": 100.0,
        },
        "local_spectrum": (
            "I_nu=f_col^-4*B_nu(f_col*T_eff), with f_col derived at local Bnu "
            "peak from tau_eff=1; local bolometric flux is exactly preserved"
        ),
        "f_col_range": [
            float(np.min(closure.spectral_hardening_factor)),
            float(np.max(closure.spectral_hardening_factor)),
        ],
        "observer_ranges": {
            "thermalized_optical_5e14_1e15_erg_s": _range(
                "thermalized_optical_5e14_1e15_erg_s"
            ),
            "formal_uvopt_erg_s": _range("formal_uvopt_0p002_0p1keV_erg_s"),
            "formal_xray_erg_s_not_physical": _range("formal_xray_0p3_10keV_erg_s"),
            "formal_xray_to_optical_not_physical": _range(
                "formal_xray_to_thermalized_optical"
            ),
            "conservative_T_bb_k": _range("thermalized_optical_T_bb_k"),
            "conservative_R_bb_cm": _range("thermalized_optical_R_bb_cm"),
            "conservative_fit_rms_dex": _range("thermalized_optical_fit_rms_dex"),
        },
        "probe_modified_to_blackbody_ratio_range": [
            float(np.min(hardening_ratios)), float(np.max(hardening_ratios))
        ],
        "tau_eff_target_2over3_to_1_probe_ratio_range": [
            float(np.min(target_ratios)), float(np.max(target_ratios))
        ],
        "i75_phase_max_to_min": phase_modulation,
        "xray_conclusion": {
            "all_source_area_effectively_thick_at_0p3keV": False,
            "area_fraction_effectively_thick_at_0p3keV": 0.0,
            "formal_flux_columns_retained_for_failure_diagnosis": True,
            "formal_xray_tail_is_observable_prediction": False,
        },
        "numerical_validation": {
            "atmosphere_vertical_257_to_513_probe_max_fractional_change": float(
                np.max(vertical_change)
            ),
            "adaptive_depth_2_to_4_probe_fractional_change": depth_change.tolist(),
            "source_grid_65x1024_to_129x2048_probe_fractional_change": grid_change.tolist(),
            "circular_e0_phase_0_to_90_probe_fractional_change": circular_change.tolist(),
            "all_geometric_and_grid_probe_changes_below_2e_minus_3": bool(
                np.all(vertical_change < 2.0e-3)
                and np.all(depth_change < 2.0e-3)
                and np.all(grid_change < 2.0e-3)
                and np.all(circular_change < 2.0e-3)
            ),
        },
        "included": [
            "ZO source fields and n=3 density closure",
            "free-free/electron-scattering peak thermalization hardening",
            "local bolometric energy conservation",
            "self-occultation geometry and weak-field frequency shifts",
        ],
        "not_included": [
            "bound-free edges and line opacity",
            "NLTE ionization and radiative-equilibrium atmosphere iteration",
            "Compton redistribution, limb darkening, or polarization",
            "disc wind, external reprocessing, or GR ray tracing",
        ],
        "wall_time_seconds": time.perf_counter() - start,
    }
    (args.output_dir / "phase2c_modified_blackbody_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["numerical_validation"], indent=2), flush=True)


if __name__ == "__main__":
    main()
