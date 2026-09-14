"""Observer spectra for a strict local-column point of the ZO source."""

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
from eccentric_tde_observer.faceon import face_on_blackbody_sed
from eccentric_tde_observer.geometry import build_orbital_surface_mesh
from eccentric_tde_observer.observer import (
    Observer,
    unobscured_projected_area_cm2,
)
from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.validity import audit_local_vertical_domain
from eccentric_tde_observer.vertical import (
    GAUSSIAN_VERTICAL_PROFILE,
    RADIATION_PRESSURE_POLYTROPE_PROFILE,
)
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
PROFILE_SPECS = (
    ("gaussian", GAUSSIAN_VERTICAL_PROFILE),
    ("polytrope_n3", RADIATION_PRESSURE_POLYTROPE_PROFILE),
)
PROBE_FREQUENCY_HZ = np.array([5.0e14, 1.0e15, 2.0e15, 5.0e15, 1.0e16])


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
    value = float(
        np.trapezoid(luminosity_density[selected], frequency_hz[selected])
    )
    if not np.isfinite(value) or value < 0.0:
        raise ArithmeticError("band luminosity is invalid")
    return value


def _parameters() -> ZOConstantEParameters:
    return ZOConstantEParameters(
        black_hole_mass_msun=1.0e6,
        stellar_mass_msun=1.0,
        stellar_radius_rsun=1.0,
        circularization_efficiency=1.0,
        outer_to_inner_semimajor_axis=2.0,
        eccentricity=ECCENTRICITY,
        opacity_cm2_g=0.34,
    )


def _model(radial_points: int, anomaly_points: int):
    base = build_zo_constant_e_reference_model(
        _parameters(),
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
    if not records:
        raise RuntimeError("no records were supplied")
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
    model = _model(65, 1024)
    corrected = face_on_blackbody_sed(model.source, frequency)
    corrected_probe = face_on_blackbody_sed(
        model.source, PROBE_FREQUENCY_HZ
    ).isotropic_equivalent_lnu_erg_s_hz
    corrected_uvopt = _integrate_band(
        frequency,
        corrected.isotropic_equivalent_lnu_erg_s_hz,
        uvopt_lower,
        uvopt_upper,
    )
    corrected_xray = _integrate_band(
        frequency,
        corrected.isotropic_equivalent_lnu_erg_s_hz,
        xray_lower,
        xray_upper,
    )

    cases = _orientation_cases()
    spectra: dict[tuple[str, float, float], object] = {}
    diagnostics: list[dict[str, object]] = []
    validity: dict[str, dict[str, object]] = {}
    meshes: dict[str, object] = {}
    quadrature_metrics: dict[tuple[str, float, float], dict[str, float]] = {}
    for profile_key, profile in PROFILE_SPECS:
        photosphere = solve_gray_photosphere(
            model.source,
            model.parameters.opacity_cm2_g,
            2.0 / 3.0,
            profile,
        )
        audit = audit_local_vertical_domain(model.source, photosphere)
        validity[profile_key] = {
            "zph_over_radius_min_max": list(
                audit.photosphere_over_radius_min_max
            ),
            "corrected_area_fraction_zph_over_radius_ge_0p3": float(
                audit.corrected_photosphere_over_radius_fraction_above[1]
            ),
            "corrected_area_fraction_zph_over_radius_ge_1": float(
                audit.corrected_photosphere_over_radius_fraction_above[2]
            ),
            "surface_area_to_projected_area": (
                audit.surface_area_to_projected_mesh_area
            ),
            "projected_area_fraction_surface_slope_ge_1": (
                audit.projected_area_fraction_with_surface_slope_ge_1
            ),
        }
        mesh = build_orbital_surface_mesh(model.source, photosphere.height_cm)
        meshes[profile_key] = mesh
        for inclination_deg, phase_deg in cases:
            observer = Observer(
                DISTANCE_CM,
                np.deg2rad(inclination_deg),
                np.deg2rad(phase_deg),
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
            spectrum = source_surface_blackbody_sed(
                model.source,
                mesh,
                observer,
                quadrature,
                frequency,
            )
            spectra[(profile_key, inclination_deg, phase_deg)] = spectrum
            unobscured_area = unobscured_projected_area_cm2(mesh, observer)
            visible_fraction = quadrature.visible_projected_area_cm2 / unobscured_area
            quadrature_metrics[(profile_key, inclination_deg, phase_deg)] = {
                "ray_count": float(quadrature.ray_count),
                "visible_to_unobscured_projected_area": visible_fraction,
            }
            uvopt = _integrate_band(
                frequency,
                spectrum.isotropic_equivalent_lnu_erg_s_hz,
                uvopt_lower,
                uvopt_upper,
            )
            xray = _integrate_band(
                frequency,
                spectrum.isotropic_equivalent_lnu_erg_s_hz,
                xray_lower,
                xray_upper,
            )
            blackbody_fit = fit_isotropic_blackbody_lnu(
                frequency,
                spectrum.isotropic_equivalent_lnu_erg_s_hz,
                uvopt_lower,
                uvopt_upper,
            )
            probe = source_surface_blackbody_sed(
                model.source,
                mesh,
                observer,
                quadrature,
                PROBE_FREQUENCY_HZ,
            )
            record: dict[str, object] = {
                "closure": profile_key,
                "inclination_deg": inclination_deg,
                "relative_phase_deg": phase_deg,
                "visible_to_unobscured_projected_area": visible_fraction,
                "uvopt_0p002_0p1keV_erg_s": uvopt,
                "xray_0p3_10keV_erg_s": xray,
                "xray_to_uvopt": xray / uvopt,
                "T_bb_k": blackbody_fit.temperature_k,
                "R_bb_cm": blackbody_fit.radius_cm,
                "L_bb_bolometric_erg_s": (
                    blackbody_fit.bolometric_luminosity_erg_s
                ),
                "blackbody_fit_rms_dex": (
                    blackbody_fit.rms_log10_residual_dex
                ),
                "quadrature_ray_count": quadrature.ray_count,
            }
            for probe_frequency, ratio in zip(
                PROBE_FREQUENCY_HZ,
                probe.isotropic_equivalent_lnu_erg_s_hz / corrected_probe,
                strict=True,
            ):
                record[f"Lnu_to_corrected ZO_at_{probe_frequency:.1e}_Hz"] = float(
                    ratio
                )
            diagnostics.append(record)
            print(
                f"{profile_key} {_case_label(inclination_deg, phase_deg)} complete",
                flush=True,
            )

    spectrum_columns = [frequency, corrected.isotropic_equivalent_lnu_erg_s_hz]
    spectrum_header = ["frequency_hz", "corrected_Lnu_iso_erg_s_hz"]
    for profile_key, _ in PROFILE_SPECS:
        for inclination_deg, phase_deg in cases:
            spectrum = spectra[(profile_key, inclination_deg, phase_deg)]
            label = f"{profile_key}_{_case_label(inclination_deg, phase_deg)}"
            spectrum_columns.extend(
                (
                    spectrum.flux_density_erg_s_cm2_hz,
                    spectrum.isotropic_equivalent_lnu_erg_s_hz,
                )
            )
            spectrum_header.extend(
                (f"{label}_Fnu_cgs", f"{label}_Lnu_iso_erg_s_hz")
            )
    np.savetxt(
        args.output_dir / "phase1i_observer_spectra.csv",
        np.column_stack(spectrum_columns),
        delimiter=",",
        header=",".join(spectrum_header),
        comments="",
    )
    _write_dict_rows(
        args.output_dir / "phase1i_orientation_diagnostics.csv", diagnostics
    )

    polytrope_cases = [
        record for record in diagnostics if record["closure"] == "polytrope_n3"
    ]
    worst_record = min(
        polytrope_cases,
        key=lambda record: (
            float(record["visible_to_unobscured_projected_area"]),
            -float(record["inclination_deg"]),
            float(record["relative_phase_deg"]),
        ),
    )
    worst_inclination = float(worst_record["inclination_deg"])
    worst_phase = float(worst_record["relative_phase_deg"])
    worst_observer = Observer(
        DISTANCE_CM,
        np.deg2rad(worst_inclination),
        np.deg2rad(worst_phase),
    )
    worst_mesh = meshes["polytrope_n3"]
    worst_index = build_orthographic_triangle_index(
        worst_mesh, worst_observer, bins_long_axis=256
    )
    depth_records: list[dict[str, object]] = []
    depth_ratios: list[np.ndarray] = []
    for depth in (2, 4):
        quadrature = render_adaptive_source_surface_quadrature(
            worst_mesh,
            worst_observer,
            maximum_subdivision_depth=depth,
            triangle_index=worst_index,
            interior_vertex_fraction=0.01,
        )
        spectrum = source_surface_blackbody_sed(
            model.source,
            worst_mesh,
            worst_observer,
            quadrature,
            PROBE_FREQUENCY_HZ,
        )
        ratio = spectrum.isotropic_equivalent_lnu_erg_s_hz / corrected_probe
        depth_ratios.append(ratio)
        record = {
            "audit_type": "adaptive_depth",
            "grid_radial_points": 65,
            "grid_anomaly_points": 1024,
            "maximum_subdivision_depth": depth,
            "inclination_deg": worst_inclination,
            "relative_phase_deg": worst_phase,
            "ray_count": quadrature.ray_count,
        }
        for probe_frequency, value in zip(
            PROBE_FREQUENCY_HZ, ratio, strict=True
        ):
            record[f"Lnu_to_corrected ZO_at_{probe_frequency:.1e}_Hz"] = float(value)
        depth_records.append(record)
    depth_fractional_change = np.abs(depth_ratios[-1] / depth_ratios[-2] - 1.0)

    grid_records: list[dict[str, object]] = []
    grid_ratios: list[np.ndarray] = []
    for radial_points, anomaly_points in ((33, 512), (65, 1024), (129, 2048)):
        grid_model = model if radial_points == 65 else _model(
            radial_points, anomaly_points
        )
        grid_photosphere = solve_gray_photosphere(
            grid_model.source,
            grid_model.parameters.opacity_cm2_g,
            2.0 / 3.0,
            RADIATION_PRESSURE_POLYTROPE_PROFILE,
        )
        grid_mesh = build_orbital_surface_mesh(
            grid_model.source, grid_photosphere.height_cm
        )
        grid_observer = Observer(
            DISTANCE_CM,
            np.deg2rad(worst_inclination),
            np.deg2rad(worst_phase),
        )
        grid_index = build_orthographic_triangle_index(
            grid_mesh,
            grid_observer,
            bins_long_axis=512 if anomaly_points >= 2048 else 256,
        )
        grid_quadrature = render_source_surface_quadrature(
            grid_mesh,
            grid_observer,
            subdivision_level=0,
            triangle_index=grid_index,
        )
        grid_spectrum = source_surface_blackbody_sed(
            grid_model.source,
            grid_mesh,
            grid_observer,
            grid_quadrature,
            PROBE_FREQUENCY_HZ,
        )
        grid_corrected = face_on_blackbody_sed(
            grid_model.source, PROBE_FREQUENCY_HZ
        ).isotropic_equivalent_lnu_erg_s_hz
        ratio = grid_spectrum.isotropic_equivalent_lnu_erg_s_hz / grid_corrected
        grid_ratios.append(ratio)
        record = {
            "audit_type": "source_grid",
            "grid_radial_points": radial_points,
            "grid_anomaly_points": anomaly_points,
            "maximum_subdivision_depth": 0,
            "inclination_deg": worst_inclination,
            "relative_phase_deg": worst_phase,
            "ray_count": grid_quadrature.ray_count,
        }
        for probe_frequency, value in zip(
            PROBE_FREQUENCY_HZ, ratio, strict=True
        ):
            record[f"Lnu_to_corrected ZO_at_{probe_frequency:.1e}_Hz"] = float(value)
        grid_records.append(record)
    grid_fractional_change = np.abs(grid_ratios[-1] / grid_ratios[-2] - 1.0)
    _write_dict_rows(
        args.output_dir / "phase1i_numerical_convergence.csv",
        depth_records + grid_records,
    )

    faceon_polytrope = spectra[("polytrope_n3", 0.0, 0.0)]
    phase_probe_ratio: dict[float, np.ndarray] = {}
    for inclination_deg in INCLINATION_DEG[1:]:
        values = []
        for phase_deg in PHASE_DEG:
            spectrum = spectra[("polytrope_n3", inclination_deg, phase_deg)]
            indices = np.searchsorted(frequency, PROBE_FREQUENCY_HZ)
            if not np.array_equal(frequency[indices], PROBE_FREQUENCY_HZ):
                raise RuntimeError("probe frequencies are missing from the SED grid")
            values.append(
                spectrum.flux_density_erg_s_cm2_hz[indices]
                / faceon_polytrope.flux_density_erg_s_cm2_hz[indices]
            )
        phase_probe_ratio[inclination_deg] = np.asarray(values)

    figure, axes = plt.subplots(2, 3, figsize=(16.2, 9.4), constrained_layout=True)
    figure.suptitle(
        r"Phase 1I: observer spectra at strict-domain $e=0.6,\ \mathcal{V}=0.01$",
        fontsize=16,
    )
    axis = axes[0, 0]
    for inclination_deg in INCLINATION_DEG:
        phase_deg = 0.0
        spectrum = spectra[("polytrope_n3", inclination_deg, phase_deg)]
        axis.loglog(
            frequency,
            frequency * spectrum.flux_density_erg_s_cm2_hz,
            label=f"i={inclination_deg:.0f} deg",
        )
    axis.set_xlim(1.0e14, 3.0e16)
    axis.set_ylim(1.0e-16, 2.0e-11)
    axis.set_title(r"Actual $\nu F_\nu$ at 100 Mpc, phase 0")
    axis.set_xlabel(r"$\nu$ [Hz]")
    axis.set_ylabel(r"$\nu F_\nu$ [erg s$^{-1}$ cm$^{-2}$]")
    axis.legend(fontsize=8)

    axis = axes[0, 1]
    for phase_deg in (0.0, 60.0, 120.0, 180.0):
        spectrum = spectra[("polytrope_n3", 75.0, phase_deg)]
        axis.loglog(
            frequency,
            frequency * spectrum.flux_density_erg_s_cm2_hz,
            label=f"phase={phase_deg:.0f} deg",
        )
    axis.set_xlim(1.0e14, 3.0e16)
    axis.set_ylim(1.0e-16, 2.0e-11)
    axis.set_title(r"Precession-phase spectra at $i=75$ deg")
    axis.set_xlabel(r"$\nu$ [Hz]")
    axis.set_ylabel(r"$\nu F_\nu$ [erg s$^{-1}$ cm$^{-2}$]")
    axis.legend(fontsize=8)

    axis = axes[0, 2]
    comparison_case = (worst_inclination, worst_phase)
    gaussian_spectrum = spectra[("gaussian", *comparison_case)]
    polytrope_spectrum = spectra[("polytrope_n3", *comparison_case)]
    positive = gaussian_spectrum.flux_density_erg_s_cm2_hz > 0.0
    axis.semilogx(
        frequency[positive],
        (
            polytrope_spectrum.flux_density_erg_s_cm2_hz[positive]
            / gaussian_spectrum.flux_density_erg_s_cm2_hz[positive]
        ),
    )
    axis.axhline(1.0, color="black", linestyle="--", linewidth=1.0)
    axis.set_xlim(1.0e14, 3.0e16)
    axis.set_title(
        f"Closure ratio at i={worst_inclination:.0f}, phase={worst_phase:.0f} deg"
    )
    axis.set_xlabel(r"$\nu$ [Hz]")
    axis.set_ylabel(r"$F_{\nu,n=3}/F_{\nu,G}$")

    axis = axes[1, 0]
    for frequency_index, probe_frequency in enumerate(PROBE_FREQUENCY_HZ[:4]):
        axis.plot(
            PHASE_DEG,
            phase_probe_ratio[75.0][:, frequency_index],
            marker="o",
            label=f"{probe_frequency:.1e} Hz",
        )
    axis.set_title(r"Phase response at $i=75$ deg")
    axis.set_xlabel(r"relative phase $\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel(r"$F_\nu/F_{\nu,face-on}$")
    axis.legend(fontsize=8)

    axis = axes[1, 1]
    for inclination_deg in INCLINATION_DEG[1:]:
        selected_records = [
            record
            for record in polytrope_cases
            if float(record["inclination_deg"]) == inclination_deg
        ]
        axis.plot(
            [float(record["relative_phase_deg"]) for record in selected_records],
            [float(record["T_bb_k"]) for record in selected_records],
            marker="o",
            label=f"i={inclination_deg:.0f} deg",
        )
    axis.set_title("UV/opt single-blackbody temperature [A-fit]")
    axis.set_xlabel(r"relative phase $\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel(r"$T_{bb}$ [K]")
    axis.legend(fontsize=8)

    axis = axes[1, 2]
    for inclination_deg in INCLINATION_DEG[1:]:
        selected_records = [
            record
            for record in polytrope_cases
            if float(record["inclination_deg"]) == inclination_deg
        ]
        axis.plot(
            [float(record["relative_phase_deg"]) for record in selected_records],
            [float(record["R_bb_cm"]) for record in selected_records],
            marker="o",
            label=f"i={inclination_deg:.0f} deg",
        )
    axis.set_title("UV/opt single-blackbody radius [A-fit]")
    axis.set_xlabel(r"relative phase $\phi_{obs}-\varpi$ [deg]")
    axis.set_ylabel(r"$R_{bb}$ [cm]")
    axis.legend(fontsize=8)
    figure.savefig(args.output_dir / "phase1i_observer_spectra.png", dpi=180)
    plt.close(figure)

    symmetry_changes = []
    for profile_key, _ in PROFILE_SPECS:
        for inclination_deg in INCLINATION_DEG[1:]:
            for phase_deg in PHASE_DEG[1:6]:
                forward = spectra[(profile_key, inclination_deg, phase_deg)]
                reflected = spectra[
                    (profile_key, inclination_deg, 360.0 - phase_deg)
                ]
                selected = (
                    (frequency <= 1.0e16)
                    & (forward.flux_density_erg_s_cm2_hz > 0.0)
                )
                symmetry_changes.append(
                    np.max(
                        np.abs(
                            reflected.flux_density_erg_s_cm2_hz[selected]
                            / forward.flux_density_erg_s_cm2_hz[selected]
                            - 1.0
                        )
                    )
                )

    def _range(records: list[dict[str, object]], key: str) -> list[float]:
        values = np.array([float(record[key]) for record in records])
        return [float(np.min(values)), float(np.max(values))]

    closure_probe_change = []
    for inclination_deg, phase_deg in cases:
        gaussian_record = next(
            record
            for record in diagnostics
            if record["closure"] == "gaussian"
            and float(record["inclination_deg"]) == inclination_deg
            and float(record["relative_phase_deg"]) == phase_deg
        )
        polytrope_record = next(
            record
            for record in diagnostics
            if record["closure"] == "polytrope_n3"
            and float(record["inclination_deg"]) == inclination_deg
            and float(record["relative_phase_deg"]) == phase_deg
        )
        for probe_frequency in PROBE_FREQUENCY_HZ:
            key = f"Lnu_to_corrected ZO_at_{probe_frequency:.1e}_Hz"
            closure_probe_change.append(
                abs(float(polytrope_record[key]) / float(gaussian_record[key]) - 1.0)
            )

    report = {
        "classification": (
            "frequency-resolved observer spectrum at a strict local-column "
            "point [A/V]; point lies below the ZO expected V range [O]"
        ),
        "model": {
            "eccentricity": ECCENTRICITY,
            "circularization_efficiency": CIRCULARIZATION_EFFICIENCY,
            "black_hole_mass_msun": 1.0e6,
            "stellar_mass_msun": 1.0,
            "stellar_radius_rsun": 1.0,
            "outer_to_inner_semimajor_axis": 2.0,
            "opacity_cm2_g": 0.34,
            "source_grid": [65, 1024],
            "distance_mpc": 100.0,
        },
        "validity": validity,
        "source_corrected_bands": {
            "uvopt_0p002_0p1keV_erg_s": corrected_uvopt,
            "xray_0p3_10keV_erg_s": corrected_xray,
            "xray_to_uvopt": corrected_xray / corrected_uvopt,
        },
        "polytrope_observer_ranges": {
            "uvopt_erg_s": _range(polytrope_cases, "uvopt_0p002_0p1keV_erg_s"),
            "xray_erg_s": _range(polytrope_cases, "xray_0p3_10keV_erg_s"),
            "xray_to_uvopt": _range(polytrope_cases, "xray_to_uvopt"),
            "T_bb_k": _range(polytrope_cases, "T_bb_k"),
            "R_bb_cm": _range(polytrope_cases, "R_bb_cm"),
            "blackbody_fit_rms_dex": _range(
                polytrope_cases, "blackbody_fit_rms_dex"
            ),
            "visible_to_unobscured_projected_area": _range(
                polytrope_cases, "visible_to_unobscured_projected_area"
            ),
        },
        "worst_occultation_case": {
            "inclination_deg": worst_inclination,
            "relative_phase_deg": worst_phase,
            "visible_to_unobscured_projected_area": float(
                worst_record["visible_to_unobscured_projected_area"]
            ),
        },
        "self_occultation_detected_to_1e_minus_12_in_projected_area": bool(
            any(
                float(record["visible_to_unobscured_projected_area"])
                < 1.0 - 1.0e-12
                for record in polytrope_cases
            )
        ),
        "numerical_convergence": {
            "probe_frequency_hz": PROBE_FREQUENCY_HZ.tolist(),
            "adaptive_depth_2_to_4_fractional_change": (
                depth_fractional_change.tolist()
            ),
            "source_grid_65x1024_to_129x2048_fractional_change": (
                grid_fractional_change.tolist()
            ),
            "all_probe_changes_below_1e_minus_3": bool(
                np.all(depth_fractional_change < 1.0e-3)
                and np.all(grid_fractional_change < 1.0e-3)
            ),
            "maximum_reflection_symmetry_fractional_difference_to_1e16Hz": (
                float(np.max(symmetry_changes))
            ),
        },
        "maximum_gaussian_to_polytrope_probe_fractional_change": float(
            np.max(closure_probe_change)
        ),
        "relative_phase_definition": "phi_obs - varpi(t)",
        "precession_time_scale_supplied_by_constant_e_source": False,
        "blackbody_fit_convention": (
            "equal weight in log Lnu over 0.002-0.1 keV; "
            "Lnu=4*pi^2*Rbb^2*Bnu(Tbb) [A-fit]"
        ),
        "upper_surface_sidewall_included": False,
        "disc_wind_applied": False,
        "frequency_shift_applied": False,
        "observer_spectrum_publishable_as_typical_TDE_prediction": False,
        "observer_spectrum_publishable_as_conditional_strict_domain_result": True,
        "wall_time_seconds": time.perf_counter() - start,
    }
    (args.output_dir / "phase1i_observer_spectra_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["numerical_convergence"], indent=2), flush=True)


if __name__ == "__main__":
    main()
