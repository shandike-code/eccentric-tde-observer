"""Phase 7B5o：冻结分层 P0 网格在新病例初始态/收敛态上的验证。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np

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
)
from eccentric_tde_observer.radiative_transfer_1d import gauss_legendre_mu_weights

try:
    from scripts.phase7b5a_log_frequency_p1_gate import (
        CONTROL_ANGULAR_ORDER,
        COUPLED_RESIDUAL_TARGET,
        ENERGY_LEDGER_TARGET,
        PHYSICAL_ENERGY_RANGE_EV,
        REFERENCE_P0_GROUPS_PER_DECADE,
        _load_material_reference,
        _p0_actual_one_cell_run,
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
    )
    from scripts.phase7b5k_high_resolution_convergence import (
        _returned_array_bytes,
    )
    from scripts.phase7b5m_actual_multiresolution_validation import (
        _case_context,
        _converged_p0_map,
        _edge_sha256,
    )
    from scripts.phase7b5n_hierarchical_p0_validation import (
        GIB_BYTES,
        MIB_BYTES,
        RATE_NAMES,
        _development_matrix,
        _plot_allocation,
        _plot_resources,
        _plot_validation_errors,
        _sha256_file,
        _spectral_metrics,
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
        _load_material_reference,
        _p0_actual_one_cell_run,
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
    )
    from phase7b5k_high_resolution_convergence import (  # type: ignore[no-redef]
        _returned_array_bytes,
    )
    from phase7b5m_actual_multiresolution_validation import (  # type: ignore[no-redef]
        _case_context,
        _converged_p0_map,
        _edge_sha256,
    )
    from phase7b5n_hierarchical_p0_validation import (  # type: ignore[no-redef]
        GIB_BYTES,
        MIB_BYTES,
        RATE_NAMES,
        _development_matrix,
        _plot_allocation,
        _plot_resources,
        _plot_validation_errors,
        _sha256_file,
        _spectral_metrics,
    )


EXPECTED_PROTOCOL_SHA256 = (
    "ff63f6f46cd71c96089c714a600f8ef7a31d71bf92afd306aec743a89e94a176"
)
RATE_QUADRATURE_ORDER = 16


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


def _load_protocol(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B5o protocol hash changed: {digest}")
    protocol = json.loads(payload)
    if protocol["candidate"]["validation_feedback_allowed"] is not False:
        raise RuntimeError("frozen protocol unexpectedly permits validation feedback")
    return protocol


def _capture_initial_and_converged_states(material, full, audit, definition):
    initial: np.ndarray | None = None
    first: np.ndarray | None = None
    latest: np.ndarray | None = None
    latest_iteration = -1

    def observe(iteration, intensity):
        nonlocal initial, first, latest, latest_iteration
        if iteration == 0:
            initial = np.array(intensity, copy=True)
        if iteration == 1:
            first = np.array(intensity, copy=True)
        latest = np.array(intensity, copy=True)
        latest_iteration = int(iteration)

    row, _, _ = _p0_actual_one_cell_run(
        material,
        full,
        audit,
        definition,
        REFERENCE_P0_GROUPS_PER_DECADE,
        iteration_observer=observe,
    )
    if (
        initial is None
        or first is None
        or latest is None
        or latest_iteration < 1
        or row["fixed_point_converged"] is not True
    ):
        raise RuntimeError("reference solve did not provide guaranteed validation states")
    return (
        {"initial": initial, "converged": latest},
        first,
        {
            "case": definition["case"],
            "fixed_point_converged": row["fixed_point_converged"],
            "fixed_point_iterations": row["fixed_point_iterations"],
            "last_observer_iteration": latest_iteration,
            "global_coupled_residual": row["global_coupled_residual"],
            "total_energy_ledger_residual": row["total_energy_ledger_residual"],
            "minimum_intensity": row["minimum_intensity"],
        },
    )


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
):
    started = time.perf_counter()
    result = _converged_p0_map(
        stencil, old_edge, new_edge, mu, weight, state, source
    )
    return {
        "case": case,
        "representation": representation,
        "source_state_seed": "converged reference",
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


def run_all(output_dir: Path, protocol_path: Path, *, force: bool) -> None:
    paths = {
        "summary": output_dir / "phase7b5o_summary.json",
        "states": output_dir / "phase7b5o_validation_states.csv",
        "parents": output_dir / "phase7b5o_parent_choices.csv",
        "development": output_dir / "phase7b5o_development_states.csv",
        "errors": output_dir / "phase7b5o_validation_errors.png",
        "allocation": output_dir / "phase7b5o_hierarchy_allocation.png",
        "resources": output_dir / "phase7b5o_resource_costs.png",
    }
    if not force and all(path.exists() for path in paths.values()):
        print(f"reusing {paths['summary'].name}")
        return
    protocol = _load_protocol(protocol_path)
    material_path = Path(protocol["material_reference"]["path"])
    if _sha256_file(material_path) != protocol["material_reference"]["sha256"]:
        raise RuntimeError("material reference hash differs from frozen protocol")
    prior_path = Path(
        protocol["excluded_prior_holdout"]["phase7b5n_protocol_path"]
    )
    if (
        hashlib.sha256(prior_path.read_bytes()).hexdigest()
        != protocol["excluded_prior_holdout"]["phase7b5n_protocol_sha256"]
    ):
        raise RuntimeError("excluded Phase 7B5n protocol hash changed")
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
        quadrature_order_per_master_group=RATE_QUADRATURE_ORDER,
    )
    candidate_grid = budgeted_hierarchical_p0_grid(
        option_error, protocol["candidate"]["leaf_group_budget"]
    )
    candidate_stencil = mixed_frame_frequency_stencil_from_active_edges(
        candidate_grid.group_edge_hz, maximum_beta
    )
    frozen_hash_before = _edge_sha256(candidate_grid.group_edge_hz)

    rows: list[dict[str, object]] = []
    reference_controls: list[dict[str, object]] = []
    operator_controls: list[dict[str, object]] = []
    for definition in protocol["validation"]["cases"]:
        case = str(definition["case"])
        source_states, initial_next, reference_control = (
            _capture_initial_and_converged_states(
                material, full, audit, definition
            )
        )
        reference_controls.append(reference_control)
        state, old_edge, new_edge = _case_context(material, full, definition)
        converged_projected_sources: dict[str, np.ndarray] = {}
        for label in protocol["validation"]["source_state_labels"]:
            reference_source = source_states[label]
            reference_next = _one_p0_map(
                reference_stencil,
                old_edge,
                new_edge,
                mu,
                weight,
                state,
                reference_source,
            )
            candidate_source, candidate_projection = _project_p0_state(
                reference_stencil.active_lab_edge_hz,
                candidate_stencil.active_lab_edge_hz,
                reference_source,
            )
            master_source, master_projection = _project_p0_state(
                reference_stencil.active_lab_edge_hz,
                master_stencil.active_lab_edge_hz,
                reference_source,
            )
            if label == "converged":
                converged_projected_sources = {
                    "hierarchical P0, 4816": candidate_source,
                    "nested master, 9632": master_source,
                }
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
                "source_state_label": label,
                "reference_fixed_point_iterations": reference_control[
                    "fixed_point_iterations"
                ],
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
                "initial_reference_next_state_reproduced_exactly": (
                    np.array_equal(
                        reference_next.final_lab_intensity_density, initial_next
                    )
                    if label == "initial"
                    else None
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
                    converged_projected_sources[representation],
                )
            )
    frozen_hash_after = _edge_sha256(candidate_grid.group_edge_hz)

    gates = protocol["gates"]

    def representation_gate(prefix: str) -> bool:
        return bool(
            all(
                row[f"{prefix}_energy_absolute_relative_error"]
                < gates[
                    "candidate_and_master_energy_relative_error_strictly_below"
                ]
                and all(
                    row[f"{prefix}_{name}_absolute_relative_error"]
                    < gates[
                        "candidate_and_master_rate_relative_error_strictly_below"
                    ]
                    for name in RATE_NAMES
                )
                for row in rows
            )
        )

    reference_gate = bool(
        all(
            row["fixed_point_converged"]
            and row["global_coupled_residual"] < COUPLED_RESIDUAL_TARGET
            and row["total_energy_ledger_residual"] < ENERGY_LEDGER_TARGET
            and row["minimum_intensity"] >= 0.0
            for row in reference_controls
        )
    )
    mapping_gate = bool(
        all(
            (row["source_state_label"] != "initial"
             or row["initial_reference_next_state_reproduced_exactly"])
            and row["candidate_projection_energy_error"]
            < gates["projection_energy_relative_error_below"]
            and row["master_projection_energy_error"]
            < gates["projection_energy_relative_error_below"]
            and row["candidate_maximum_rate_quadrature_relative_error"]
            < gates["rate_quadrature_relative_error_below"]
            and row["master_maximum_rate_quadrature_relative_error"]
            < gates["rate_quadrature_relative_error_below"]
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
        hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        == EXPECTED_PROTOCOL_SHA256
    )
    material_gate = (
        _sha256_file(material_path) == protocol["material_reference"]["sha256"]
    )
    hash_gate = frozen_hash_before == frozen_hash_after
    budget_gate = (
        candidate_grid.leaf_group_count
        == gates["candidate_physical_group_count"]
    )
    master_gate = representation_gate("master")
    candidate_gate = representation_gate("candidate")
    selected = bool(
        protocol_gate
        and material_gate
        and hash_gate
        and budget_gate
        and reference_gate
        and mapping_gate
        and operator_gate
        and master_gate
        and candidate_gate
    )
    decision = {
        "frozen_protocol_hash_passed": protocol_gate,
        "frozen_material_hash_passed": material_gate,
        "prior_holdout_exclusion_hash_passed": True,
        "validation_spectra_used_for_grid_construction": False,
        "all_reference_source_solves_passed": reference_gate,
        "frozen_grid_hash_unchanged_through_validation": hash_gate,
        "exact_4816_leaf_budget_passed": budget_gate,
        "all_mapping_projection_and_quadrature_controls_passed": mapping_gate,
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
        "phase": "7B5o",
        "classification": (
            "[A-preregistered] frozen 1-2-4 P0 family and guaranteed "
            "initial/converged holdouts; [V] joint energy/H/He validation; "
            "[O] angle/subgrid/orbit and matter feedback"
        ),
        "protocol": {
            "path": str(protocol_path),
            "sha256": EXPECTED_PROTOCOL_SHA256,
            "material_sha256": protocol["material_reference"]["sha256"],
            "validation_case_count": len(protocol["validation"]["cases"]),
            "validation_state_count": protocol["validation"]["state_count"],
            "source_state_labels": protocol["validation"]["source_state_labels"],
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
        "reference_source_controls": reference_controls,
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
        default=Path("outputs/phase7b5o_preregistered_protocol.json"),
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run_all(args.output_dir, args.protocol, force=args.force)


if __name__ == "__main__":
    main()
