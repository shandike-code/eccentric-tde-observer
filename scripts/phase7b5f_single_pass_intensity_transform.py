"""Phase 7B5f：单次实验室系到共动系强度 Lorentz 搬移审计。"""

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

from eccentric_tde_observer.atomic_continuum import EV_ERG, H_I_VERNER_FIT
from eccentric_tde_observer.log_frequency_moments import (
    comoving_log_frequency_group_p1_radiation,
)
from eccentric_tde_observer.log_multigroup_continuum import (
    gauss_legendre_log_frequency_group_quadrature,
    ground_state_milne_log_p1_multigroup,
    log_group_average_from_quadrature_nodes,
)
from eccentric_tde_observer.mixed_frame_ale import mixed_frame_frequency_stencil
from eccentric_tde_observer.mixed_frame_frequency import comoving_group_radiation
from eccentric_tde_observer.multigroup_continuum import (
    gauss_legendre_frequency_group_quadrature,
    ground_state_milne_multigroup,
    group_average_from_quadrature_nodes,
)
from eccentric_tde_observer.prescribed_radiation import (
    edge_resolved_photoionization_energy_grid_ev,
    prescribed_planck_photoionization_rates_s1,
)
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S, PLANCK_ERG_S, planck_nu
from eccentric_tde_observer.rate_error_localization import (
    localize_hydrogen_photoionization_rate_error,
)
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_mu_weights,
)

try:
    from scripts.phase7b4v_mixed_frame_ale_gate import _boosted_planck_outer
    from scripts.phase7b5a_log_frequency_p1_gate import (
        CONTROL_ANGULAR_ORDER,
        GROUP_QUADRATURE_ORDER,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _active_slice,
        _actual_case_definitions,
        _boosted_planck_outer_log_p1,
        _collision_physical_slice,
        _load_material_reference,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from scripts.phase7b5b_rate_kernel_grid_gate import _stencil
    from scripts.phase7b5c_signed_rate_error_localization import (
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
        RATE_RECONCILIATION_TARGET,
        _analysis_edges,
        _regions,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b4v_mixed_frame_ale_gate import (  # type: ignore[no-redef]
        _boosted_planck_outer,
    )
    from phase7b5a_log_frequency_p1_gate import (  # type: ignore[no-redef]
        CONTROL_ANGULAR_ORDER,
        GROUP_QUADRATURE_ORDER,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _active_slice,
        _actual_case_definitions,
        _boosted_planck_outer_log_p1,
        _collision_physical_slice,
        _load_material_reference,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from phase7b5b_rate_kernel_grid_gate import _stencil  # type: ignore[no-redef]
    from phase7b5c_signed_rate_error_localization import (  # type: ignore[no-redef]
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
        RATE_RECONCILIATION_TARGET,
        _analysis_edges,
        _regions,
    )


LOCALIZATION_QUADRATURE_ORDER = 16
EXACT_RATE_BASE_POINTS = (524288, 1048576)
SINGLE_PASS_TARGET = 1.0e-3
REFERENCE_ANALYTIC_TARGET = 2.0e-5
INPUT_ENERGY_AGREEMENT_TARGET = 1.0e-4
EXACT_RATE_CONVERGENCE_TARGET = 2.0e-8
SPECTRUM_MINIMUM_ENERGY_EV = 12.0
SPECTRUM_MAXIMUM_ENERGY_EV = 16.5


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


def _relative_difference(value: float, reference: float) -> float:
    difference = abs(value - reference)
    return difference / abs(reference) if reference != 0.0 else difference


def _state_parameters(material, full, definition):
    phase = int(definition["phase_index"])
    following = int(definition["following_phase_index"])
    depth = int(definition["full_depth_index"])
    duration = float(material["step_duration_s"][phase])
    old_edge = full["edges_cm"][phase, depth : depth + 2]
    new_edge = full["edges_cm"][following, depth : depth + 2]
    beta = np.array(
        [float(np.mean((new_edge - old_edge) / duration) / LIGHT_SPEED_CM_S)]
    )
    return {
        "beta": beta,
        "temperature_k": float(full["temperature_k"][following, depth]),
        "density_g_cm3": float(full["density_g_cm3"][following, depth]),
        "hydrogen_fraction": full["hydrogen_fraction"][following, depth],
        "helium_fraction": full["helium_fraction"][following, depth],
    }


def _exact_planck_hydrogen_rate(temperature: float):
    rates = []
    for points in EXACT_RATE_BASE_POINTS:
        energy = edge_resolved_photoionization_energy_grid_ev(
            *PHYSICAL_ENERGY_RANGE_EV, points
        )
        result = prescribed_planck_photoionization_rates_s1(
            np.array([temperature]), np.array([1.0]), energy
        )
        rates.append(float(result.photoionization_s1[0, 0]))
    return rates[-1], _relative_difference(rates[-2], rates[-1])


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
                "signed_rate_error_over_reference": (
                    signed / localization.reference_total_rate_s1
                ),
                "absolute_integrand_difference_fraction": (
                    absolute / absolute_total if absolute_total > 0.0 else 0.0
                ),
            }
        )
    return rows


def _plot_single_pass_gate(path: Path, rows, region_rows) -> None:
    cases = [row["case"] for row in rows]
    metrics = (
        ("input_energy_relative_difference", "Input energy"),
        ("output_energy_relative_difference", "Output energy"),
        ("candidate_reference_rate_error", "H I rate"),
        ("candidate_analytic_rate_error", "Candidate / analytic"),
        ("reference_analytic_rate_error", "Reference / analytic"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(16.0, 4.8), constrained_layout=True)
    x = np.arange(len(metrics))
    width = 0.8 / len(rows)
    for index, row in enumerate(rows):
        axes[0].bar(
            x + (index - 1) * width,
            [row[field] for field, _ in metrics],
            width=width,
            label=row["case"],
        )
    axes[0].set_xticks(x, [label for _, label in metrics], rotation=28, ha="right")
    axes[0].set_yscale("log")
    axes[0].axhline(SINGLE_PASS_TARGET, color="black", linestyle=":")
    axes[0].set_ylabel("Relative error")
    axes[0].set_title("Single-pass intensity-transform gate")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.25, axis="y")

    axes[1].bar(
        np.arange(len(rows)),
        [row["candidate_reference_signed_rate_error"] for row in rows],
    )
    axes[1].axhline(0.0, color="black", linewidth=0.8)
    axes[1].set_yscale("symlog", linthresh=1.0e-10)
    axes[1].set_xticks(np.arange(len(rows)), cases, rotation=25, ha="right")
    axes[1].set_ylabel("Signed H I rate error")
    axes[1].set_title("Signed candidate-reference response")
    axes[1].grid(alpha=0.25, axis="y")

    regions = (
        "H I Doppler band",
        "H I shoulder to He I",
        "He I to He II",
        "above He II",
    )
    matrix = np.array(
        [
            [
                next(
                    item
                    for item in region_rows
                    if item["case"] == case and item["region"] == region
                )["absolute_integrand_difference_fraction"]
                for region in regions
            ]
            for case in cases
        ]
    )
    image = axes[2].imshow(matrix, vmin=0.0, vmax=1.0, aspect="auto", cmap="viridis")
    axes[2].set_xticks(np.arange(len(regions)), regions, rotation=28, ha="right")
    axes[2].set_yticks(np.arange(len(cases)), cases)
    axes[2].set_title("Absolute H I rate-error localization")
    for row_index in range(matrix.shape[0]):
        for column_index in range(matrix.shape[1]):
            axes[2].text(
                column_index,
                row_index,
                f"{matrix[row_index, column_index]:.2f}",
                ha="center",
                va="center",
                color="white" if matrix[row_index, column_index] < 0.35 else "black",
                fontsize=8,
            )
    fig.colorbar(image, ax=axes[2], label="Fraction of absolute difference")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_threshold_spectra(path: Path, spectra_rows, doppler_factor: float) -> None:
    cases = tuple(dict.fromkeys(row["case"] for row in spectra_rows))
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.6), constrained_layout=True)
    for axis, case in zip(axes, cases, strict=True):
        selected = [row for row in spectra_rows if row["case"] == case]
        for representation, label in (
            ("log-P1 candidate", "log-P1 candidate"),
            ("P0 reference", "P0 reference"),
        ):
            state = [
                row for row in selected if row["representation"] == representation
            ]
            axis.plot(
                [row["energy_ev"] for row in state],
                [row["relative_to_planck_group_mean"] for row in state],
                label=label,
                alpha=0.85,
            )
        axis.axhline(0.0, color="black", linewidth=0.8)
        axis.axvline(
            H_I_VERNER_FIT.threshold_energy_ev,
            color="black",
            linestyle=":",
            label="H I edge",
        )
        axis.axvline(
            H_I_VERNER_FIT.threshold_energy_ev * doppler_factor,
            color="tab:red",
            linestyle="--",
            label="maximum Doppler edge",
        )
        axis.set_yscale("symlog", linthresh=1.0e-7)
        axis.set_xlabel("Photon energy (eV)")
        axis.set_ylabel("Group mean / analytic group mean - 1")
        axis.set_title(case)
        axis.grid(alpha=0.25)
    axes[0].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(output_dir: Path, material_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5f_summary.json",
        "states": output_dir / "phase7b5f_single_pass_states.csv",
        "regions": output_dir / "phase7b5f_region_response.csv",
        "profiles": output_dir / "phase7b5f_threshold_spectra.csv",
        "gate_plot": output_dir / "phase7b5f_single_pass_gate.png",
        "spectrum_plot": output_dir / "phase7b5f_threshold_spectra.png",
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
    _, candidate_stencil = _stencil(
        FAILED_PHYSICAL_GROUPS, FAILED_FOCUS_FRACTION, maximum_beta
    )
    reference_stencil = mixed_frame_frequency_stencil(
        *PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        maximum_beta,
    )
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    rows: list[dict[str, object]] = []
    region_rows: list[dict[str, object]] = []
    spectra_rows: list[dict[str, object]] = []
    for definition in _actual_case_definitions(material, full, audit):
        case = str(definition["case"])
        state = _state_parameters(material, full, definition)
        beta = state["beta"]
        temperature = float(state["temperature_k"])
        candidate_outer = _boosted_planck_outer_log_p1(
            candidate_stencil, mu, weight, beta, temperature
        )
        reference_outer = _boosted_planck_outer(
            reference_stencil, mu, weight, beta, temperature
        )
        candidate = comoving_log_frequency_group_p1_radiation(
            candidate_outer.mean_density,
            candidate_outer.first_moment_density,
            candidate_stencil.outer_lab_edge_hz,
            candidate_stencil.comoving_collision_edge_hz,
            mu,
            weight,
            beta,
        )
        reference = comoving_group_radiation(
            reference_outer,
            reference_stencil.outer_lab_edge_hz,
            reference_stencil.comoving_collision_edge_hz,
            mu,
            weight,
            beta,
        )
        candidate_physical = _collision_physical_slice(candidate_stencil)
        reference_physical = _collision_physical_slice(reference_stencil)
        candidate_mean = candidate.mean_intensity_density[candidate_physical, 0]
        candidate_moment = candidate.mean_intensity_first_moment_density[
            candidate_physical, 0
        ]
        reference_mean = reference.mean_intensity_density[reference_physical, 0]
        localization = localize_hydrogen_photoionization_rate_error(
            candidate_stencil.active_lab_edge_hz,
            candidate_mean,
            candidate_moment,
            reference_stencil.active_lab_edge_hz,
            reference_mean,
            analysis_edge,
            quadrature_order_per_native_overlap=LOCALIZATION_QUADRATURE_ORDER,
        )
        density = float(state["density_g_cm3"])
        hydrogen = state["hydrogen_fraction"]
        helium = state["helium_fraction"]
        candidate_native = ground_state_milne_log_p1_multigroup(
            density,
            temperature,
            candidate_stencil.active_lab_edge_hz,
            candidate_mean[:, None],
            candidate_moment[:, None],
            hydrogen[0],
            hydrogen[1],
            helium[0],
            helium[1],
            helium[2],
            order_per_group=GROUP_QUADRATURE_ORDER,
        ).radiative_rates.photoionization_s1[0, 0]
        reference_native = ground_state_milne_multigroup(
            density,
            temperature,
            reference_stencil.active_lab_edge_hz,
            reference_mean[:, None],
            hydrogen[0],
            hydrogen[1],
            helium[0],
            helium[1],
            helium[2],
            order_per_group=GROUP_QUADRATURE_ORDER,
        ).radiative_rates.photoionization_s1[0, 0]
        analytic_rate, analytic_convergence = _exact_planck_hydrogen_rate(
            temperature
        )
        candidate_input_energy = np.sum(
            np.diff(np.log(candidate_stencil.active_lab_edge_hz))[:, None]
            * candidate_outer.mean_density[_active_slice(candidate_stencil), :, 0],
            axis=0,
        )
        reference_input_energy = np.sum(
            np.diff(reference_stencil.active_lab_edge_hz)[:, None]
            * reference_outer[_active_slice(reference_stencil), :, 0],
            axis=0,
        )
        input_energy_error = float(
            np.max(
                np.abs(candidate_input_energy - reference_input_energy)
                / reference_input_energy
            )
        )
        candidate_output_energy = float(
            np.sum(
                np.diff(np.log(candidate_stencil.active_lab_edge_hz))
                * candidate_mean
            )
        )
        reference_output_energy = float(
            np.sum(np.diff(reference_stencil.active_lab_edge_hz) * reference_mean)
        )
        row = {
            "case": case,
            "temperature_k": temperature,
            "material_velocity_beta": float(beta[0]),
            "candidate_physical_groups": candidate_stencil.physical_group_count,
            "candidate_spectral_degrees_of_freedom": (
                2 * candidate_stencil.physical_group_count
            ),
            "reference_physical_groups": reference_stencil.physical_group_count,
            "input_energy_relative_difference": input_energy_error,
            "output_energy_relative_difference": _relative_difference(
                candidate_output_energy, reference_output_energy
            ),
            "candidate_reference_signed_rate_error": (
                localization.signed_relative_error
            ),
            "candidate_reference_rate_error": abs(
                localization.signed_relative_error
            ),
            "absolute_integrand_difference_relative": (
                localization.absolute_integrand_difference_relative
            ),
            "candidate_analytic_rate_error": _relative_difference(
                localization.candidate_total_rate_s1, analytic_rate
            ),
            "reference_analytic_rate_error": _relative_difference(
                localization.reference_total_rate_s1, analytic_rate
            ),
            "candidate_native_rate_reconciliation_relative": (
                _relative_difference(
                    localization.candidate_total_rate_s1,
                    float(candidate_native),
                )
            ),
            "reference_native_rate_reconciliation_relative": (
                _relative_difference(
                    localization.reference_total_rate_s1,
                    float(reference_native),
                )
            ),
            "analytic_rate_quadrature_convergence": analytic_convergence,
            "outer_limiter_count": candidate_outer.limited_group_count,
            "transform_limiter_count": candidate.limited_group_count,
            "transform_maximum_prelimit_realizability_ratio": (
                candidate.maximum_prelimit_realizability_ratio
            ),
        }
        row["passed"] = bool(
            row["input_energy_relative_difference"]
            < INPUT_ENERGY_AGREEMENT_TARGET
            and row["output_energy_relative_difference"] < SINGLE_PASS_TARGET
            and row["candidate_reference_rate_error"] < SINGLE_PASS_TARGET
            and row["reference_analytic_rate_error"] < REFERENCE_ANALYTIC_TARGET
            and row["candidate_native_rate_reconciliation_relative"]
            < RATE_RECONCILIATION_TARGET
            and row["reference_native_rate_reconciliation_relative"]
            < RATE_RECONCILIATION_TARGET
            and row["analytic_rate_quadrature_convergence"]
            < EXACT_RATE_CONVERGENCE_TARGET
        )
        rows.append(row)
        region_rows.extend(_region_rows(case, localization, regions))

        candidate_quadrature = gauss_legendre_log_frequency_group_quadrature(
            candidate_stencil.active_lab_edge_hz,
            order_per_group=GROUP_QUADRATURE_ORDER,
        )
        candidate_planck_mean = log_group_average_from_quadrature_nodes(
            candidate_quadrature.node_hz
            * planck_nu(candidate_quadrature.node_hz, temperature),
            candidate_quadrature,
        )
        reference_quadrature = gauss_legendre_frequency_group_quadrature(
            reference_stencil.active_lab_edge_hz,
            order_per_group=GROUP_QUADRATURE_ORDER,
        )
        reference_planck_mean = group_average_from_quadrature_nodes(
            planck_nu(reference_quadrature.node_hz, temperature),
            reference_quadrature,
        )
        for representation, edge_hz, values, analytic_values in (
            (
                "log-P1 candidate",
                candidate_stencil.active_lab_edge_hz,
                candidate_mean,
                candidate_planck_mean,
            ),
            (
                "P0 reference",
                reference_stencil.active_lab_edge_hz,
                reference_mean,
                reference_planck_mean,
            ),
        ):
            centre_energy = (
                np.sqrt(edge_hz[:-1] * edge_hz[1:])
                * PLANCK_ERG_S
                / EV_ERG
            )
            selected = (
                (centre_energy >= SPECTRUM_MINIMUM_ENERGY_EV)
                & (centre_energy <= SPECTRUM_MAXIMUM_ENERGY_EV)
            )
            for energy_value, value, analytic_value in zip(
                centre_energy[selected],
                values[selected],
                analytic_values[selected],
                strict=True,
            ):
                spectra_rows.append(
                    {
                        "case": case,
                        "representation": representation,
                        "energy_ev": energy_value,
                        "relative_to_planck_group_mean": (
                            value / analytic_value - 1.0
                        ),
                    }
                )

    all_states_passed = all(row["passed"] for row in rows)
    decision = {
        "single_pass_intensity_transform_passed": all_states_passed,
        "intensity_transform_discretization_identified_as_primary": False,
        "implicit_collision_feedback_accumulation_audit_authorized": (
            all_states_passed
        ),
        "targeted_operator_remediation_authorized": False,
        "production_frequency_representation_selected": False,
        "angular_radiation_subgrid_time_gate_authorized": False,
        "full_dynamic_orbit_authorized": False,
        "matter_temperature_population_feedback_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }
    _write_csv(paths["states"], rows)
    _write_csv(paths["regions"], region_rows)
    _write_csv(paths["profiles"], spectra_rows)
    _plot_single_pass_gate(paths["gate_plot"], rows, region_rows)
    _plot_threshold_spectra(paths["spectrum_plot"], spectra_rows, doppler_factor)
    report = {
        "phase": "7B5f",
        "classification": (
            "[A] one-pass frozen analytic Planck input and 1e-3 target; [V] matched "
            "log-P1/P0 lab-to-comoving intensity transforms, energy and H I rate "
            "audits; [O] source-iteration feedback accumulation"
        ),
        "configuration": {
            "candidate_focus_fraction": FAILED_FOCUS_FRACTION,
            "candidate_physical_groups": FAILED_PHYSICAL_GROUPS,
            "candidate_spectral_degrees_of_freedom": 2
            * FAILED_PHYSICAL_GROUPS,
            "reference_p0_groups_per_decade": REFERENCE_P0_GROUPS_PER_DECADE,
            "angular_order": CONTROL_ANGULAR_ORDER,
            "group_quadrature_order": GROUP_QUADRATURE_ORDER,
            "localization_quadrature_order": LOCALIZATION_QUADRATURE_ORDER,
            "exact_rate_base_points": list(EXACT_RATE_BASE_POINTS),
            "single_pass_target": SINGLE_PASS_TARGET,
            "reference_analytic_target": REFERENCE_ANALYTIC_TARGET,
            "input_energy_agreement_target": INPUT_ENERGY_AGREEMENT_TARGET,
            "exact_rate_convergence_target": EXACT_RATE_CONVERGENCE_TARGET,
            "maximum_velocity_beta": maximum_beta,
            "maximum_doppler_factor": doppler_factor,
        },
        "states": rows,
        "region_response": region_rows,
        "decision": decision,
        "open_items": [
            "the one-pass audit does not include extinction, emissivity, ALE or source iteration",
            "a passing one-pass transform does not select a production representation",
            "the next audit must localize candidate-reference divergence by source-iteration depth",
            "the 38496-group P0 result remains a finite controlled reference",
            "angle, radiation-subgrid, orbit and matter-feedback gates remain closed",
        ],
        "figures": {
            "single_pass_gate": paths["gate_plot"].name,
            "threshold_spectra": paths["spectrum_plot"].name,
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
