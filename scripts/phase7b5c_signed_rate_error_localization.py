"""Phase 7B5c：H I 光致电离率有符号频段误差定位。"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.atomic_continuum import (
    H_HE_GROUND_STATE_PHOTOIONIZATION_FITS,
    H_I_VERNER_FIT,
)
from eccentric_tde_observer.rate_error_localization import (
    localize_hydrogen_photoionization_rate_error,
    project_piecewise_constant_intensity_to_log_p1,
)

try:
    from scripts.phase7b5a_log_frequency_p1_gate import (
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _actual_case_definitions,
        _actual_one_cell_run_log_p1,
        _load_material_reference,
        _p0_actual_one_cell_run,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from scripts.phase7b5b_rate_kernel_grid_gate import _stencil
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5a_log_frequency_p1_gate import (  # type: ignore[no-redef]
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _actual_case_definitions,
        _actual_one_cell_run_log_p1,
        _load_material_reference,
        _p0_actual_one_cell_run,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from phase7b5b_rate_kernel_grid_gate import _stencil  # type: ignore[no-redef]


FAILED_FOCUS_FRACTION = 0.25
FAILED_PHYSICAL_GROUPS = 2408
ANALYSIS_LOG_BINS = 256
LOCALIZATION_QUADRATURE_ORDERS = (8, 16)
RATE_RECONCILIATION_TARGET = 2.0e-8
LOCALIZATION_QUADRATURE_TARGET = 2.0e-10
DECOMPOSITION_LEDGER_TARGET = 2.0e-12
STABLE_REGION_ABSOLUTE_FRACTION = 0.5


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _analysis_edges(maximum_beta: float) -> tuple[np.ndarray, float]:
    hydrogen_threshold = H_I_VERNER_FIT.threshold_energy_ev
    doppler_factor = float(
        np.sqrt((1.0 + maximum_beta) / (1.0 - maximum_beta))
    )
    thresholds = [
        fit.threshold_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
    ]
    edge = np.unique(
        np.concatenate(
            (
                np.geomspace(
                    PHYSICAL_ENERGY_RANGE_EV[0],
                    PHYSICAL_ENERGY_RANGE_EV[1],
                    ANALYSIS_LOG_BINS + 1,
                ),
                [
                    PHYSICAL_ENERGY_RANGE_EV[0],
                    hydrogen_threshold,
                    hydrogen_threshold * doppler_factor,
                    *thresholds[1:],
                    PHYSICAL_ENERGY_RANGE_EV[1],
                ],
            )
        )
    )
    edge[0] = PHYSICAL_ENERGY_RANGE_EV[0]
    edge[-1] = PHYSICAL_ENERGY_RANGE_EV[1]
    return edge, doppler_factor


def _regions(doppler_factor: float):
    h_i, he_i, he_ii = [
        fit.threshold_energy_ev for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
    ]
    return (
        ("below H I", PHYSICAL_ENERGY_RANGE_EV[0], h_i),
        ("H I Doppler band", h_i, h_i * doppler_factor),
        ("H I shoulder to He I", h_i * doppler_factor, he_i),
        ("He I to He II", he_i, he_ii),
        ("above He II", he_ii, PHYSICAL_ENERGY_RANGE_EV[1]),
    )


def _relative_difference(value: float, reference: float) -> float:
    difference = abs(value - reference)
    return difference / abs(reference) if reference != 0.0 else difference


def _region_rows(case: str, localization, regions):
    rows = []
    edge = localization.analysis_edge_ev
    absolute_total = float(
        np.sum(localization.absolute_integrand_difference_bin_s1)
    )
    for label, left, right in regions:
        selected = (edge[:-1] >= left) & (edge[1:] <= right)
        signed = float(np.sum(localization.signed_error_bin_s1[selected]))
        absolute = float(
            np.sum(localization.absolute_integrand_difference_bin_s1[selected])
        )
        rows.append(
            {
                "case": case,
                "region": label,
                "minimum_energy_ev": left,
                "maximum_energy_ev": right,
                "signed_rate_error_s1": signed,
                "signed_rate_error_over_reference": (
                    signed / localization.reference_total_rate_s1
                ),
                "absolute_integrand_difference_s1": absolute,
                "absolute_integrand_difference_fraction": (
                    absolute / absolute_total if absolute_total > 0.0 else 0.0
                ),
            }
        )
    return rows


def _profile_rows(case: str, localization):
    edge = localization.analysis_edge_ev
    reference = localization.reference_total_rate_s1
    cumulative_signed = np.cumsum(localization.signed_error_bin_s1)
    cumulative_absolute = np.cumsum(
        localization.absolute_integrand_difference_bin_s1
    )
    rows = []
    for index in range(edge.size - 1):
        rows.append(
            {
                "case": case,
                "minimum_energy_ev": edge[index],
                "maximum_energy_ev": edge[index + 1],
                "geometric_centre_energy_ev": np.sqrt(
                    edge[index] * edge[index + 1]
                ),
                "candidate_rate_bin_s1": localization.candidate_rate_bin_s1[
                    index
                ],
                "reference_rate_bin_s1": localization.reference_rate_bin_s1[
                    index
                ],
                "signed_rate_error_bin_s1": localization.signed_error_bin_s1[
                    index
                ],
                "absolute_integrand_difference_bin_s1": (
                    localization.absolute_integrand_difference_bin_s1[index]
                ),
                "signed_error_per_log10_energy_over_reference": (
                    localization.signed_error_bin_s1[index]
                    / np.log10(edge[index + 1] / edge[index])
                    / reference
                ),
                "cumulative_signed_error_over_reference": (
                    cumulative_signed[index] / reference
                ),
                "cumulative_absolute_difference_over_reference": (
                    cumulative_absolute[index] / abs(reference)
                ),
            }
        )
    return rows


def _plot_localization(path: Path, profile_rows, region_rows, regions) -> None:
    cases = (
        "cold coefficient surface",
        "maximum cell speed",
        "maximum width change",
    )
    fig, axes = plt.subplots(2, 2, figsize=(14.0, 8.5), constrained_layout=True)
    for case in cases:
        rows = [row for row in profile_rows if row["case"] == case]
        energy = [row["geometric_centre_energy_ev"] for row in rows]
        axes[0, 0].plot(
            energy,
            [row["signed_error_per_log10_energy_over_reference"] for row in rows],
            label=case,
        )
        axes[0, 1].plot(
            energy,
            [row["cumulative_signed_error_over_reference"] for row in rows],
            label=case,
        )
        axes[1, 0].plot(
            energy,
            [row["cumulative_absolute_difference_over_reference"] for row in rows],
            label=case,
        )
    for axis in axes.flat[:3]:
        axis.set_xscale("log")
        axis.axhline(0.0, color="black", linewidth=0.8)
        for _, left, _ in regions[1:]:
            axis.axvline(left, color="0.6", linewidth=0.7, linestyle=":")
        axis.grid(alpha=0.25, which="both")
        axis.set_xlabel("Photon energy (eV)")
    axes[0, 0].set_ylabel("Signed rate error per dex / reference rate")
    axes[0, 0].set_title("Signed H I rate-error density")
    axes[0, 0].set_yscale("symlog", linthresh=1.0e-5)
    axes[0, 1].set_ylabel("Cumulative signed error / reference rate")
    axes[0, 1].set_title("Cumulative signed H I rate error")
    axes[1, 0].set_ylabel("Cumulative absolute difference / reference rate")
    axes[1, 0].set_title("Cancellation-aware absolute discrepancy")
    axes[0, 0].legend(fontsize=8)

    labels = [label for label, _, _ in regions]
    x = np.arange(len(labels))
    width = 0.8 / len(cases)
    for index, case in enumerate(cases):
        rows = [row for row in region_rows if row["case"] == case]
        axes[1, 1].bar(
            x + (index - 1) * width,
            [row["absolute_integrand_difference_fraction"] for row in rows],
            width=width,
            label=case,
        )
    axes[1, 1].set_xticks(x, labels, rotation=30, ha="right")
    axes[1, 1].set_ylabel("Fraction of absolute integrand difference")
    axes[1, 1].set_title("Error localization by physical energy region")
    axes[1, 1].grid(alpha=0.25, axis="y")
    axes[1, 1].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_decomposition(path: Path, case_rows, projection_rows) -> None:
    cases = [row["case"] for row in case_rows]
    x = np.arange(len(cases))
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8), constrained_layout=True)
    width = 0.24
    for offset, field, label in (
        (-width, "compression_limiter_signed_relative", "compressed reference"),
        (0.0, "dynamic_remainder_signed_relative", "dynamic remainder"),
        (width, "total_signed_relative", "total"),
    ):
        axes[0].bar(
            x + offset,
            [row[field] for row in case_rows],
            width=width,
            label=label,
        )
    axes[0].axhline(0.0, color="black", linewidth=0.8)
    axes[0].set_yscale("symlog", linthresh=1.0e-10)
    axes[0].set_xticks(x, cases, rotation=25, ha="right")
    axes[0].set_ylabel("Signed H I rate error / reference rate")
    axes[0].set_title("Algebraic error decomposition")
    axes[0].grid(alpha=0.25, axis="y")
    axes[0].legend(fontsize=8)

    width = 0.36
    axes[1].bar(
        x - width / 2.0,
        [row["projection_limiter_rate_change_relative"] for row in projection_rows],
        width=width,
        label="projection limiter rate change",
    )
    axes[1].bar(
        x + width / 2.0,
        [row["final_saturated_error_fraction"] for row in case_rows],
        width=width,
        label="absolute error in saturated final groups",
    )
    axes[1].set_xticks(x, cases, rotation=25, ha="right")
    axes[1].set_ylabel("Relative diagnostic")
    axes[1].set_title("Realizability involvement")
    axes[1].grid(alpha=0.25, axis="y")
    axes[1].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5c_summary.json",
        "cases": output_dir / "phase7b5c_case_decomposition.csv",
        "regions": output_dir / "phase7b5c_region_contributions.csv",
        "profiles": output_dir / "phase7b5c_signed_rate_profiles.csv",
        "projections": output_dir / "phase7b5c_projection_audit.csv",
        "localization_plot": output_dir
        / "phase7b5c_signed_rate_error_localization.png",
        "decomposition_plot": output_dir
        / "phase7b5c_projection_dynamic_decomposition.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    audit = _trajectory_velocity_audit(material, full)
    maximum_beta = float(audit["maximum_velocity_beta"])
    analysis_edge, doppler_factor = _analysis_edges(maximum_beta)
    regions = _regions(doppler_factor)
    _, stencil = _stencil(
        FAILED_PHYSICAL_GROUPS, FAILED_FOCUS_FRACTION, maximum_beta
    )

    case_rows: list[dict[str, object]] = []
    region_rows: list[dict[str, object]] = []
    profile_rows: list[dict[str, object]] = []
    projection_rows: list[dict[str, object]] = []
    definitions = _actual_case_definitions(material, full, audit)
    for definition in definitions:
        case = str(definition["case"])
        _, reference_diagnostics, reference_arrays = _p0_actual_one_cell_run(
            material,
            full,
            audit,
            definition,
            REFERENCE_P0_GROUPS_PER_DECADE,
        )
        candidate_arrays: dict[str, np.ndarray] = {}
        candidate_row, candidate_diagnostics = _actual_one_cell_run_log_p1(
            material,
            full,
            audit,
            definition,
            FAILED_PHYSICAL_GROUPS,
            stencil_override=stencil,
            diagnostic_arrays=candidate_arrays,
        )
        projection = project_piecewise_constant_intensity_to_log_p1(
            reference_arrays["physical_group_edge_hz"],
            reference_arrays["final_comoving_mean_intensity"],
            candidate_arrays["physical_group_edge_hz"],
        )
        localizations = {
            order: localize_hydrogen_photoionization_rate_error(
                candidate_arrays["physical_group_edge_hz"],
                candidate_arrays["final_comoving_mean_intensity_energy"],
                candidate_arrays[
                    "final_comoving_first_moment_intensity_energy"
                ],
                reference_arrays["physical_group_edge_hz"],
                reference_arrays["final_comoving_mean_intensity"],
                analysis_edge,
                quadrature_order_per_native_overlap=order,
            )
            for order in LOCALIZATION_QUADRATURE_ORDERS
        }
        localization = localizations[max(LOCALIZATION_QUADRATURE_ORDERS)]
        projected = localize_hydrogen_photoionization_rate_error(
            projection.group_edge_hz,
            projection.mean_energy_density,
            projection.realizable_first_moment_energy_density,
            reference_arrays["physical_group_edge_hz"],
            reference_arrays["final_comoving_mean_intensity"],
            analysis_edge,
            quadrature_order_per_native_overlap=max(
                LOCALIZATION_QUADRATURE_ORDERS
            ),
        )
        prelimit = localize_hydrogen_photoionization_rate_error(
            projection.group_edge_hz,
            projection.mean_energy_density,
            projection.prelimit_first_moment_energy_density,
            reference_arrays["physical_group_edge_hz"],
            reference_arrays["final_comoving_mean_intensity"],
            analysis_edge,
            quadrature_order_per_native_overlap=max(
                LOCALIZATION_QUADRATURE_ORDERS
            ),
            require_nonnegative_candidate=False,
        )
        reference_rate = localization.reference_total_rate_s1
        compression = projected.candidate_total_rate_s1 - reference_rate
        dynamic = (
            localization.candidate_total_rate_s1
            - projected.candidate_total_rate_s1
        )
        total = localization.candidate_total_rate_s1 - reference_rate
        decomposition_residual = total - compression - dynamic
        quadrature_relative = max(
            _relative_difference(
                localizations[LOCALIZATION_QUADRATURE_ORDERS[0]].candidate_total_rate_s1,
                localization.candidate_total_rate_s1,
            ),
            _relative_difference(
                localizations[LOCALIZATION_QUADRATURE_ORDERS[0]].reference_total_rate_s1,
                localization.reference_total_rate_s1,
            ),
        )
        candidate_reconciliation = _relative_difference(
            localization.candidate_total_rate_s1,
            float(candidate_diagnostics["photoionization_H_I"]),
        )
        reference_reconciliation = _relative_difference(
            localization.reference_total_rate_s1,
            float(reference_diagnostics["photoionization_H_I"]),
        )
        case_rows.append(
            {
                "case": case,
                "focus_fraction": FAILED_FOCUS_FRACTION,
                "physical_frequency_groups": FAILED_PHYSICAL_GROUPS,
                "spectral_degrees_of_freedom": 2 * FAILED_PHYSICAL_GROUPS,
                "reference_rate_s1": reference_rate,
                "candidate_rate_s1": localization.candidate_total_rate_s1,
                "total_signed_relative": total / reference_rate,
                "total_absolute_relative": abs(total) / abs(reference_rate),
                "compression_limiter_signed_relative": compression / reference_rate,
                "dynamic_remainder_signed_relative": dynamic / reference_rate,
                "decomposition_ledger_relative": abs(decomposition_residual)
                / abs(reference_rate),
                "absolute_integrand_difference_relative": (
                    localization.absolute_integrand_difference_relative
                ),
                "signed_cancellation_fraction": 1.0
                - abs(total)
                / float(
                    np.sum(localization.absolute_integrand_difference_bin_s1)
                ),
                "final_saturated_group_count": (
                    localization.saturated_candidate_group_count
                ),
                "final_saturated_error_fraction": (
                    localization.saturated_candidate_absolute_difference_fraction
                ),
                "candidate_native_rate_reconciliation_relative": (
                    candidate_reconciliation
                ),
                "reference_native_rate_reconciliation_relative": (
                    reference_reconciliation
                ),
                "localization_quadrature_relative": quadrature_relative,
                "solver_final_limiter_count": candidate_row[
                    "solver_final_limiter_count"
                ],
            }
        )
        projection_rows.append(
            {
                "case": case,
                "projection_limited_group_count": projection.limited_group_count,
                "projection_maximum_prelimit_realizability_ratio": (
                    projection.maximum_prelimit_realizability_ratio
                ),
                "projection_minimum_prelimit_endpoint_energy_density": (
                    projection.minimum_prelimit_endpoint_energy_density
                ),
                "projection_energy_integral_relative_error": (
                    projection.relative_energy_integral_error
                ),
                "prelimit_projection_signed_rate_relative": (
                    prelimit.signed_relative_error
                ),
                "limited_projection_signed_rate_relative": (
                    projected.signed_relative_error
                ),
                "projection_limiter_rate_change_relative": abs(
                    projected.candidate_total_rate_s1
                    - prelimit.candidate_total_rate_s1
                )
                / abs(reference_rate),
            }
        )
        region_rows.extend(_region_rows(case, localization, regions))
        profile_rows.extend(_profile_rows(case, localization))

    localization_controls_passed = bool(
        all(
            row["candidate_native_rate_reconciliation_relative"]
            < RATE_RECONCILIATION_TARGET
            and row["reference_native_rate_reconciliation_relative"]
            < RATE_RECONCILIATION_TARGET
            and row["localization_quadrature_relative"]
            < LOCALIZATION_QUADRATURE_TARGET
            and row["decomposition_ledger_relative"]
            < DECOMPOSITION_LEDGER_TARGET
            for row in case_rows
        )
        and all(
            row["projection_energy_integral_relative_error"]
            < DECOMPOSITION_LEDGER_TARGET
            for row in projection_rows
        )
    )
    dominant_by_case = {}
    for case in (row["case"] for row in case_rows):
        rows = [row for row in region_rows if row["case"] == case]
        dominant = max(
            rows, key=lambda row: row["absolute_integrand_difference_fraction"]
        )
        dominant_by_case[case] = {
            "region": dominant["region"],
            "absolute_integrand_difference_fraction": dominant[
                "absolute_integrand_difference_fraction"
            ],
        }
    dominant_regions = {
        value["region"] for value in dominant_by_case.values()
    }
    stable_single_region = bool(
        len(dominant_regions) == 1
        and all(
            value["absolute_integrand_difference_fraction"]
            >= STABLE_REGION_ABSOLUTE_FRACTION
            for value in dominant_by_case.values()
        )
    )
    decision = {
        "localization_controls_passed": localization_controls_passed,
        "same_dominant_region_in_all_states": len(dominant_regions) == 1,
        "stable_single_region_localization_passed": stable_single_region,
        "dominant_region_by_case": dominant_by_case,
        "new_frequency_basis_design_authorized": bool(
            localization_controls_passed and stable_single_region
        ),
        "production_frequency_representation_selected": False,
        "angular_radiation_subgrid_time_gate_authorized": False,
        "full_dynamic_orbit_authorized": False,
        "matter_temperature_population_feedback_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }
    _write_csv(paths["cases"], case_rows)
    _write_csv(paths["regions"], region_rows)
    _write_csv(paths["profiles"], profile_rows)
    _write_csv(paths["projections"], projection_rows)
    _plot_localization(paths["localization_plot"], profile_rows, region_rows, regions)
    _plot_decomposition(paths["decomposition_plot"], case_rows, projection_rows)
    report = {
        "phase": "7B5c",
        "classification": (
            "[A] fixed failed f=0.25 candidate and localization regions; "
            "[V] native-rate reconciliation, signed energy profiles and algebraic "
            "projection/dynamic decomposition; [O] a closed production basis"
        ),
        "configuration": {
            "physical_energy_range_ev": list(PHYSICAL_ENERGY_RANGE_EV),
            "failed_focus_fraction": FAILED_FOCUS_FRACTION,
            "failed_physical_frequency_groups": FAILED_PHYSICAL_GROUPS,
            "failed_spectral_degrees_of_freedom": 2 * FAILED_PHYSICAL_GROUPS,
            "reference_p0_groups_per_decade": REFERENCE_P0_GROUPS_PER_DECADE,
            "reference_p0_physical_frequency_groups": 38496,
            "analysis_log_bins_before_anchors": ANALYSIS_LOG_BINS,
            "localization_quadrature_orders": list(
                LOCALIZATION_QUADRATURE_ORDERS
            ),
            "rate_reconciliation_target": RATE_RECONCILIATION_TARGET,
            "localization_quadrature_target": LOCALIZATION_QUADRATURE_TARGET,
            "decomposition_ledger_target": DECOMPOSITION_LEDGER_TARGET,
            "stable_region_absolute_fraction": (
                STABLE_REGION_ABSOLUTE_FRACTION
            ),
            "maximum_velocity_beta": maximum_beta,
            "maximum_doppler_factor": doppler_factor,
        },
        "method": {
            "candidate": "the already-failed f=0.25, 2408-group rate-monitor log-P1 state",
            "reference": "38496-group P0 finite reference",
            "integration": "Gauss quadrature on the union of candidate, reference and analysis edges",
            "compression_control": "exact energy projection of final P0 J_nu to candidate Q=nu*J_nu P1 moments",
            "decomposition": "candidate-reference = (limited projection-reference) + (candidate-limited projection)",
            "causality_warning": "the algebraic decomposition localizes error but is not a unique causal adjoint decomposition",
        },
        "regions": [
            {"name": label, "minimum_energy_ev": left, "maximum_energy_ev": right}
            for label, left, right in regions
        ],
        "case_decomposition": case_rows,
        "projection_audit": projection_rows,
        "region_contributions": region_rows,
        "decision": decision,
        "open_items": [
            "the 38496-group P0 result remains a finite reference",
            "signed localization is diagnostic and not a new transport closure",
            "projection/dynamic separation is algebraic rather than a unique causal adjoint",
            "a new basis is not authorized unless localization is stable across states",
            "angle, radiation-subgrid, orbit and matter-feedback gates remain closed",
        ],
        "figures": {
            "signed_rate_error_localization": paths["localization_plot"].name,
            "projection_dynamic_decomposition": paths[
                "decomposition_plot"
            ].name,
        },
    }
    _write_json_atomic(paths["summary"], report)
    print(json.dumps(decision, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--material-reference",
        type=Path,
        default=Path("outputs/phase7b4r_depth128_phase2048.npz"),
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run_all(args.output_dir, args.material_reference, force=args.force)


if __name__ == "__main__":
    main()
