"""Phase 7B5n：冻结 1--2--4 分层 P0 网格后的全新实际态验证。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.goal_oriented_frequency import (
    hydrogen_photoionization_monitor_group_grid,
)
from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil,
    mixed_frame_frequency_stencil_from_active_edges,
)
from eccentric_tde_observer.multiresolution_frequency import (
    budgeted_hierarchical_p0_grid,
    hierarchical_p0_option_error,
    nested_log_frequency_hierarchy,
    piecewise_constant_photoionization_rates_s1,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.radiative_transfer_1d import gauss_legendre_mu_weights

try:
    from scripts.phase7b5a_log_frequency_p1_gate import (
        CONTROL_ANGULAR_ORDER,
        COUPLED_RESIDUAL_TARGET,
        ENERGY_LEDGER_TARGET,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _collision_physical_slice,
        _load_material_reference,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from scripts.phase7b5c_signed_rate_error_localization import (
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
    )
    from scripts.phase7b5i_partition_representation_split import (
        _one_p0_map,
        _project_p0_state,
        _relative_difference,
    )
    from scripts.phase7b5k_high_resolution_convergence import (
        _returned_array_bytes,
    )
    from scripts.phase7b5m_actual_multiresolution_validation import (
        _capture_reference_states,
        _case_context,
        _converged_p0_map,
        _edge_sha256,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5a_log_frequency_p1_gate import (  # type: ignore[no-redef]
        CONTROL_ANGULAR_ORDER,
        COUPLED_RESIDUAL_TARGET,
        ENERGY_LEDGER_TARGET,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _collision_physical_slice,
        _load_material_reference,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from phase7b5c_signed_rate_error_localization import (  # type: ignore[no-redef]
        FAILED_FOCUS_FRACTION,
        FAILED_PHYSICAL_GROUPS,
    )
    from phase7b5i_partition_representation_split import (  # type: ignore[no-redef]
        _one_p0_map,
        _project_p0_state,
        _relative_difference,
    )
    from phase7b5k_high_resolution_convergence import (  # type: ignore[no-redef]
        _returned_array_bytes,
    )
    from phase7b5m_actual_multiresolution_validation import (  # type: ignore[no-redef]
        _capture_reference_states,
        _case_context,
        _converged_p0_map,
        _edge_sha256,
    )


EXPECTED_PROTOCOL_SHA256 = (
    "e8d76f9603f0bbd153f0630abebade84da821d9eb79096e57d949306e19cef91"
)
RATE_QUADRATURE_ORDERS = (8, 16)
RATE_NAMES = ("H_I", "He_I", "He_II")
MIB_BYTES = 1024**2
GIB_BYTES = 1024**3


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    fields: list[str] = []
    for row in rows:
        fields.extend(key for key in row if key not in fields)
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _load_frozen_protocol(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    digest = _sha256_bytes(payload)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(
            f"frozen Phase 7B5n protocol hash changed: {digest}"
        )
    protocol = json.loads(payload)
    if protocol["candidate"]["validation_feedback_allowed"] is not False:
        raise RuntimeError("frozen protocol unexpectedly permits validation feedback")
    return protocol


def _p0_spectrum(stencil, result) -> np.ndarray:
    physical = _collision_physical_slice(stencil)
    return np.asarray(
        result.final_comoving_mean_intensity_density[physical, 0],
        dtype=np.float64,
    )


def _spectral_metrics(
    candidate_stencil,
    candidate_result,
    reference_stencil,
    reference_result,
) -> dict[str, float]:
    candidate = _p0_spectrum(candidate_stencil, candidate_result)
    reference = _p0_spectrum(reference_stencil, reference_result)
    candidate_edge = candidate_stencil.active_lab_edge_hz
    reference_edge = reference_stencil.active_lab_edge_hz
    candidate_energy = float(np.sum(candidate * np.diff(candidate_edge)))
    reference_energy = float(np.sum(reference * np.diff(reference_edge)))
    output = {
        "energy_signed_relative_error": (
            (candidate_energy - reference_energy) / reference_energy
            if reference_energy != 0.0
            else candidate_energy - reference_energy
        ),
        "energy_absolute_relative_error": _relative_difference(
            candidate_energy, reference_energy
        ),
    }
    rate_by_order: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for order in RATE_QUADRATURE_ORDERS:
        candidate_rate = piecewise_constant_photoionization_rates_s1(
            candidate_edge,
            candidate,
            quadrature_order_per_group=order,
        )
        reference_rate = piecewise_constant_photoionization_rates_s1(
            reference_edge,
            reference,
            quadrature_order_per_group=order,
        )
        rate_by_order[order] = (candidate_rate, reference_rate)
    low_candidate, low_reference = rate_by_order[RATE_QUADRATURE_ORDERS[0]]
    high_candidate, high_reference = rate_by_order[RATE_QUADRATURE_ORDERS[1]]
    quadrature_error = 0.0
    for species, name in enumerate(RATE_NAMES):
        candidate_rate = float(high_candidate[species])
        reference_rate = float(high_reference[species])
        signed = (
            (candidate_rate - reference_rate) / reference_rate
            if reference_rate != 0.0
            else candidate_rate - reference_rate
        )
        output[f"{name}_signed_relative_error"] = signed
        output[f"{name}_absolute_relative_error"] = abs(signed)
        quadrature_error = max(
            quadrature_error,
            _relative_difference(float(low_candidate[species]), candidate_rate),
            _relative_difference(float(low_reference[species]), reference_rate),
        )
    output["maximum_rate_quadrature_relative_error"] = quadrature_error
    return output


def _development_matrix(
    material,
    full,
    audit,
    definitions,
    iterations,
    reference_stencil,
    master_stencil,
    mu,
    weight,
) -> tuple[np.ndarray, list[dict[str, object]]]:
    spectra: list[np.ndarray] = []
    rows: list[dict[str, object]] = []
    for definition in definitions:
        reference_states = _capture_reference_states(
            material, full, audit, definition, iterations
        )
        state, old_edge, new_edge = _case_context(
            material, full, definition
        )
        for iteration in iterations:
            source, projection_error = _project_p0_state(
                reference_stencil.active_lab_edge_hz,
                master_stencil.active_lab_edge_hz,
                reference_states[iteration],
            )
            started = time.perf_counter()
            result = _one_p0_map(
                master_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                state,
                source,
            )
            runtime = time.perf_counter() - started
            spectra.append(np.array(_p0_spectrum(master_stencil, result), copy=True))
            rows.append(
                {
                    "case": definition["case"],
                    "input_iteration": iteration,
                    "master_projection_energy_error": projection_error,
                    "master_one_cell_runtime_s": runtime,
                }
            )
    return np.column_stack(spectra), rows


def _operator_control(
    case,
    representation,
    stencil,
    old_edge,
    new_edge,
    mu,
    weight,
    state,
    source,
) -> dict[str, object]:
    started = time.perf_counter()
    result = _converged_p0_map(
        stencil, old_edge, new_edge, mu, weight, state, source
    )
    return {
        "case": case,
        "representation": representation,
        "source_iteration_seed": 3,
        "fixed_point_converged": result.fixed_point_converged,
        "fixed_point_iterations": result.fixed_point_iterations,
        "final_fixed_point_change": result.final_fixed_point_change,
        "global_coupled_residual": result.global_scale_normalized_coupled_residual,
        "total_relative_energy_ledger_residual": (
            result.total_relative_energy_ledger_residual
        ),
        "minimum_intensity": result.minimum_intensity,
        "runtime_s": time.perf_counter() - started,
    }


def _plot_validation_errors(path: Path, rows: list[dict[str, object]]) -> None:
    labels = [
        (
            f"{row['case']} {row['source_state_label']}"
            if "source_state_label" in row
            else f"{row['case']} n={row['input_iteration']}"
        )
        for row in rows
    ]
    x = np.arange(len(rows))
    panels = (
        ("energy_absolute_relative_error", "Energy"),
        ("H_I_absolute_relative_error", "H I"),
        ("He_I_absolute_relative_error", "He I"),
        ("He_II_absolute_relative_error", "He II"),
    )
    fig, axes = plt.subplots(2, 2, figsize=(16.0, 9.0), constrained_layout=True)
    for axis, (suffix, title) in zip(axes.flat, panels, strict=True):
        candidate_values = [row[f"candidate_{suffix}"] for row in rows]
        axis.plot(
            x,
            candidate_values,
            color="tab:red",
            marker="o",
            label="hierarchical P0, 4816",
        )
        axis.plot(
            x,
            [row[f"master_{suffix}"] for row in rows],
            color="tab:green",
            marker="s",
            label="nested master, 9632",
        )
        axis.axhline(1.0e-3, color="black", linestyle=":", label="target")
        axis.set_yscale("log")
        axis.set_title(f"{title} validation error")
        axis.set_ylabel("Absolute relative error")
        axis.set_xticks(x, labels, rotation=70, ha="right", fontsize=6)
        axis.grid(alpha=0.2, which="both")
        for index, value in enumerate(candidate_values):
            if value >= 1.0e-3:
                axis.scatter(
                    [index],
                    [value],
                    marker="x",
                    s=70,
                    color="black",
                    zorder=5,
                )
                axis.annotate(
                    f"FAIL {value:.6e}",
                    (index, value),
                    xytext=(-8, -20),
                    textcoords="offset points",
                    ha="right",
                    fontsize=7,
                )
    axes.flat[0].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_allocation(path: Path, error, grid) -> None:
    centre_ev = np.sqrt(
        error.base_edge_hz[:-1] * error.base_edge_hz[1:]
    ) * PLANCK_ERG_S / EV_ERG
    selected = error.normalized_score_by_option[
        np.arange(grid.leaf_count_by_parent.size), grid.option_index_by_parent
    ]
    fig, axes = plt.subplots(2, 1, figsize=(13.0, 8.0), constrained_layout=True)
    axes[0].step(
        centre_ev,
        grid.leaf_count_by_parent,
        where="mid",
        color="tab:blue",
    )
    axes[0].set_xscale("log")
    axes[0].set_yticks((1, 2, 4))
    axes[0].set_ylabel("Leaves per parent")
    axes[0].set_title("Frozen 1-2-4 hierarchy allocation")
    axes[0].grid(alpha=0.2, which="both")
    axes[1].plot(centre_ev, selected, color="tab:purple", linewidth=0.8)
    axes[1].set_xscale("log")
    axes[1].set_yscale("log")
    axes[1].set_xlabel("Photon energy (eV)")
    axes[1].set_ylabel("Selected normalized local score")
    axes[1].set_title("Development objective retained by selected leaves")
    axes[1].grid(alpha=0.2, which="both")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_resources(path: Path, rows: list[dict[str, object]]) -> None:
    candidate_runtime = [float(row["candidate_runtime_s"]) for row in rows]
    master_runtime = [float(row["master_runtime_s"]) for row in rows]
    candidate_footprint = float(rows[0]["candidate_returned_array_footprint_mib"])
    master_footprint = float(rows[0]["master_returned_array_footprint_mib"])
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), constrained_layout=True)
    axes[0].bar(
        ("hierarchical 4816", "master 9632"),
        (np.median(candidate_runtime), np.median(master_runtime)),
        color=("tab:red", "tab:green"),
    )
    axes[0].set_ylabel("Median one-cell runtime (s)")
    axes[0].set_title("Validation solve time")
    axes[0].grid(alpha=0.2, axis="y")
    axes[1].bar(
        ("hierarchical 4816", "master 9632"),
        (candidate_footprint, master_footprint),
        color=("tab:red", "tab:green"),
    )
    axes[1].set_ylabel("Returned-array footprint (MiB)")
    axes[1].set_title("One-cell direct arrays")
    axes[1].grid(alpha=0.2, axis="y")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_all(
    output_dir: Path,
    protocol_path: Path,
    *,
    force: bool,
) -> None:
    paths = {
        "summary": output_dir / "phase7b5n_summary.json",
        "states": output_dir / "phase7b5n_validation_states.csv",
        "parents": output_dir / "phase7b5n_parent_choices.csv",
        "development": output_dir / "phase7b5n_development_states.csv",
        "errors": output_dir / "phase7b5n_validation_errors.png",
        "allocation": output_dir / "phase7b5n_hierarchy_allocation.png",
        "resources": output_dir / "phase7b5n_resource_costs.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    protocol = _load_frozen_protocol(protocol_path)
    material_path = Path(protocol["material_reference"]["path"])
    if _sha256_file(material_path) != protocol["material_reference"]["sha256"]:
        raise RuntimeError("material reference hash differs from frozen protocol")
    output_dir.mkdir(parents=True, exist_ok=True)
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    audit = _trajectory_velocity_audit(material, full)
    maximum_beta = float(audit["maximum_velocity_beta"])
    mu, weight = gauss_legendre_mu_weights(CONTROL_ANGULAR_ORDER)
    reference_stencil = mixed_frame_frequency_stencil(
        *PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        maximum_beta,
    )
    base = hydrogen_photoionization_monitor_group_grid(
        *PHYSICAL_ENERGY_RANGE_EV,
        FAILED_PHYSICAL_GROUPS,
        FAILED_FOCUS_FRACTION,
    )
    hierarchy = nested_log_frequency_hierarchy(base.group_edge_hz)
    master_stencil = mixed_frame_frequency_stencil_from_active_edges(
        hierarchy.master_edge_hz, maximum_beta
    )
    development_matrix, development_rows = _development_matrix(
        material,
        full,
        audit,
        protocol["development"]["cases"],
        tuple(protocol["development"]["source_iterations"]),
        reference_stencil,
        master_stencil,
        mu,
        weight,
    )
    option_error = hierarchical_p0_option_error(
        hierarchy,
        development_matrix,
        production_tolerance=protocol["gates"][
            "candidate_and_master_rate_relative_error_strictly_below"
        ],
        quadrature_order_per_master_group=RATE_QUADRATURE_ORDERS[-1],
    )
    candidate_grid = budgeted_hierarchical_p0_grid(
        option_error,
        protocol["candidate"]["leaf_group_budget"],
    )
    candidate_stencil = mixed_frame_frequency_stencil_from_active_edges(
        candidate_grid.group_edge_hz, maximum_beta
    )
    frozen_hash_before = _edge_sha256(candidate_grid.group_edge_hz)

    rows: list[dict[str, object]] = []
    operator_controls: list[dict[str, object]] = []
    validation_iterations = tuple(protocol["validation"]["source_iterations"])
    capture_iterations = tuple(
        sorted(set(validation_iterations) | {value + 1 for value in validation_iterations})
    )
    for definition in protocol["validation"]["cases"]:
        case = str(definition["case"])
        reference_states = _capture_reference_states(
            material, full, audit, definition, capture_iterations
        )
        state, old_edge, new_edge = _case_context(material, full, definition)
        sources: dict[str, np.ndarray] = {}
        for iteration in validation_iterations:
            reference_next = _one_p0_map(
                reference_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                state,
                reference_states[iteration],
            )
            candidate_source, candidate_projection = _project_p0_state(
                reference_stencil.active_lab_edge_hz,
                candidate_stencil.active_lab_edge_hz,
                reference_states[iteration],
            )
            master_source, master_projection = _project_p0_state(
                reference_stencil.active_lab_edge_hz,
                master_stencil.active_lab_edge_hz,
                reference_states[iteration],
            )
            if iteration == validation_iterations[0]:
                sources["hierarchical P0, 4816"] = candidate_source
                sources["nested master, 9632"] = master_source
            started = time.perf_counter()
            candidate_next = _one_p0_map(
                candidate_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                state,
                candidate_source,
            )
            candidate_runtime = time.perf_counter() - started
            started = time.perf_counter()
            master_next = _one_p0_map(
                master_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                state,
                master_source,
            )
            master_runtime = time.perf_counter() - started
            candidate_metrics = _spectral_metrics(
                candidate_stencil,
                candidate_next,
                reference_stencil,
                reference_next,
            )
            master_metrics = _spectral_metrics(
                master_stencil,
                master_next,
                reference_stencil,
                reference_next,
            )
            candidate_bytes = _returned_array_bytes(candidate_next)
            master_bytes = _returned_array_bytes(master_next)
            row: dict[str, object] = {
                "case": case,
                "selector": definition["selector"],
                "quantile": definition["quantile"],
                "phase_index": definition["phase_index"],
                "full_depth_index": definition["full_depth_index"],
                "input_iteration": iteration,
                "output_iteration": iteration + 1,
                "candidate_physical_frequency_groups": (
                    candidate_grid.leaf_group_count
                ),
                "master_physical_frequency_groups": (
                    hierarchy.master_edge_hz.size - 1
                ),
                "candidate_projection_energy_error": candidate_projection,
                "master_projection_energy_error": master_projection,
                "candidate_runtime_s": candidate_runtime,
                "master_runtime_s": master_runtime,
                "candidate_returned_array_footprint_mib": (
                    candidate_bytes / MIB_BYTES
                ),
                "master_returned_array_footprint_mib": master_bytes / MIB_BYTES,
                "candidate_full_depth_linear_footprint_gib": (
                    candidate_bytes * full["temperature_k"].shape[1] / GIB_BYTES
                ),
                "master_full_depth_linear_footprint_gib": (
                    master_bytes * full["temperature_k"].shape[1] / GIB_BYTES
                ),
                "reference_next_state_reproduced_exactly": np.array_equal(
                    reference_next.final_lab_intensity_density,
                    reference_states[iteration + 1],
                ),
                "candidate_one_step_fixed_point_converged": (
                    candidate_next.fixed_point_converged
                ),
                "master_one_step_fixed_point_converged": (
                    master_next.fixed_point_converged
                ),
            }
            row.update(
                {f"candidate_{key}": value for key, value in candidate_metrics.items()}
            )
            row.update(
                {f"master_{key}": value for key, value in master_metrics.items()}
            )
            rows.append(row)
        for representation, stencil in (
            ("hierarchical P0, 4816", candidate_stencil),
            ("nested master, 9632", master_stencil),
        ):
            operator_controls.append(
                _operator_control(
                    case,
                    representation,
                    stencil,
                    old_edge,
                    new_edge,
                    mu,
                    weight,
                    state,
                    sources[representation],
                )
            )
    frozen_hash_after = _edge_sha256(candidate_grid.group_edge_hz)

    energy_target = protocol["gates"][
        "candidate_and_master_energy_relative_error_strictly_below"
    ]
    rate_target = protocol["gates"][
        "candidate_and_master_rate_relative_error_strictly_below"
    ]
    projection_target = protocol["gates"][
        "projection_energy_relative_error_below"
    ]
    quadrature_target = protocol["gates"][
        "rate_quadrature_relative_error_below"
    ]

    def representation_gate(prefix: str) -> bool:
        return bool(
            all(
                row[f"{prefix}_energy_absolute_relative_error"] < energy_target
                and all(
                    row[f"{prefix}_{name}_absolute_relative_error"] < rate_target
                    for name in RATE_NAMES
                )
                for row in rows
            )
        )

    mapping_controls = bool(
        all(
            row["reference_next_state_reproduced_exactly"]
            and row["candidate_projection_energy_error"] < projection_target
            and row["master_projection_energy_error"] < projection_target
            and row["candidate_maximum_rate_quadrature_relative_error"]
            < quadrature_target
            and row["master_maximum_rate_quadrature_relative_error"]
            < quadrature_target
            and row["candidate_one_step_fixed_point_converged"] is False
            and row["master_one_step_fixed_point_converged"] is False
            for row in rows
        )
    )
    operator_gate = bool(
        all(
            row["fixed_point_converged"]
            and row["global_coupled_residual"] < COUPLED_RESIDUAL_TARGET
            and row["total_relative_energy_ledger_residual"]
            < ENERGY_LEDGER_TARGET
            and row["minimum_intensity"] >= 0.0
            for row in operator_controls
        )
    )
    protocol_gate = (
        _sha256_bytes(protocol_path.read_bytes()) == EXPECTED_PROTOCOL_SHA256
    )
    material_gate = (
        _sha256_file(material_path) == protocol["material_reference"]["sha256"]
    )
    hash_gate = frozen_hash_before == frozen_hash_after
    budget_gate = (
        candidate_grid.leaf_group_count
        == protocol["gates"]["candidate_physical_group_count"]
    )
    master_gate = representation_gate("master")
    candidate_gate = representation_gate("candidate")
    selected = bool(
        protocol_gate
        and material_gate
        and hash_gate
        and budget_gate
        and mapping_controls
        and operator_gate
        and master_gate
        and candidate_gate
    )
    decision = {
        "frozen_protocol_hash_passed": protocol_gate,
        "frozen_material_hash_passed": material_gate,
        "validation_spectra_used_for_grid_construction": False,
        "frozen_grid_hash_unchanged_through_validation": hash_gate,
        "exact_4816_leaf_budget_passed": budget_gate,
        "all_mapping_projection_and_quadrature_controls_passed": mapping_controls,
        "all_converged_operator_controls_passed": operator_gate,
        "nested_master_joint_energy_and_H_He_rate_gate_passed": master_gate,
        "hierarchical_candidate_joint_energy_and_H_He_rate_gate_passed": (
            candidate_gate
        ),
        "one_cell_production_frequency_candidate_selected": selected,
        "angular_radiation_subgrid_one_cell_gate_authorized": selected,
        "full_dynamic_orbit_authorized": False,
        "matter_temperature_population_feedback_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }

    parent_rows: list[dict[str, object]] = []
    for parent in range(candidate_grid.leaf_count_by_parent.size):
        option = int(candidate_grid.option_index_by_parent[parent])
        parent_rows.append(
            {
                "base_parent_index": parent,
                "left_frequency_hz": hierarchy.base_edge_hz[parent],
                "right_frequency_hz": hierarchy.base_edge_hz[parent + 1],
                "selected_leaf_count": int(
                    candidate_grid.leaf_count_by_parent[parent]
                ),
                "selected_normalized_local_score": (
                    option_error.normalized_score_by_option[parent, option]
                ),
                "base_normalized_local_score": (
                    option_error.normalized_score_by_option[parent, 0]
                ),
                "pilot_normalized_local_score": (
                    option_error.normalized_score_by_option[parent, 1]
                ),
                "master_normalized_local_score": (
                    option_error.normalized_score_by_option[parent, 2]
                ),
                "selected_energy_defect_fraction": (
                    option_error.energy_defect_fraction_by_option[parent, option]
                ),
                "selected_H_I_rate_defect_fraction": (
                    option_error.rate_defect_fraction_by_species_and_option[
                        0, parent, option
                    ]
                ),
                "selected_He_I_rate_defect_fraction": (
                    option_error.rate_defect_fraction_by_species_and_option[
                        1, parent, option
                    ]
                ),
                "selected_He_II_rate_defect_fraction": (
                    option_error.rate_defect_fraction_by_species_and_option[
                        2, parent, option
                    ]
                ),
            }
        )
    _write_csv(paths["states"], rows)
    _write_csv(paths["parents"], parent_rows)
    _write_csv(paths["development"], development_rows)
    _plot_validation_errors(paths["errors"], rows)
    _plot_allocation(paths["allocation"], option_error, candidate_grid)
    _plot_resources(paths["resources"], rows)

    metric_keys = ("energy", "H_I", "He_I", "He_II")
    aggregate: dict[str, object] = {}
    for prefix in ("candidate", "master"):
        for metric in metric_keys:
            aggregate[f"maximum_{prefix}_{metric}_absolute_relative_error"] = max(
                row[f"{prefix}_{metric}_absolute_relative_error"] for row in rows
            )
    aggregate.update(
        {
            "maximum_candidate_projection_energy_error": max(
                row["candidate_projection_energy_error"] for row in rows
            ),
            "maximum_master_projection_energy_error": max(
                row["master_projection_energy_error"] for row in rows
            ),
            "maximum_candidate_rate_quadrature_relative_error": max(
                row["candidate_maximum_rate_quadrature_relative_error"]
                for row in rows
            ),
            "maximum_master_rate_quadrature_relative_error": max(
                row["master_maximum_rate_quadrature_relative_error"]
                for row in rows
            ),
            "median_candidate_runtime_s": float(
                np.median([row["candidate_runtime_s"] for row in rows])
            ),
            "median_master_runtime_s": float(
                np.median([row["master_runtime_s"] for row in rows])
            ),
            "candidate_returned_array_footprint_mib": rows[0][
                "candidate_returned_array_footprint_mib"
            ],
            "master_returned_array_footprint_mib": rows[0][
                "master_returned_array_footprint_mib"
            ],
        }
    )
    report = {
        "phase": "7B5n",
        "classification": (
            "[A-preregistered] frozen 1-2-4 P0 family, 4816 budget and new "
            "geometry-only holdouts; [V] joint energy/H/He validation; "
            "[O] angle/subgrid/orbit and matter feedback"
        ),
        "protocol": {
            "path": str(protocol_path),
            "sha256": EXPECTED_PROTOCOL_SHA256,
            "material_sha256": protocol["material_reference"]["sha256"],
            "development_state_count": protocol["development"]["state_count"],
            "validation_state_count": protocol["validation"]["state_count"],
            "validation_source_iterations": validation_iterations,
        },
        "grid": {
            "base_parent_count": hierarchy.base_edge_hz.size - 1,
            "pilot_group_count": hierarchy.pilot_edge_hz.size - 1,
            "master_group_count": hierarchy.master_edge_hz.size - 1,
            "candidate_leaf_group_count": candidate_grid.leaf_group_count,
            "option_parent_counts_1_2_4": (
                candidate_grid.option_parent_counts.tolist()
            ),
            "objective_sum_normalized_local_defect": (
                candidate_grid.objective_sum_normalized_local_defect
            ),
            "maximum_selected_parent_score": (
                candidate_grid.maximum_selected_parent_score
            ),
            "sha256_before_validation": frozen_hash_before,
            "sha256_after_validation": frozen_hash_after,
        },
        "validation_results": rows,
        "converged_operator_controls": operator_controls,
        "aggregate": aggregate,
        "decision": decision,
        "open_items": [
            "passing selects only a one-cell frequency representation",
            "angle and radiation-subgrid convergence remain a separate gate",
            "full orbit and matter-temperature/population feedback remain disabled",
            "returned-array footprint is not process peak memory",
        ],
        "figures": {
            "validation_errors": paths["errors"].name,
            "hierarchy_allocation": paths["allocation"].name,
            "resource_costs": paths["resources"].name,
        },
    }
    _write_json_atomic(paths["summary"], report)
    print(json.dumps(decision, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("outputs/phase7b5n_preregistered_protocol.json"),
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run_all(args.output_dir, args.protocol, force=args.force)


if __name__ == "__main__":
    main()
