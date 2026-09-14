"""Phase 7B5o：冻结全新病例及初始态/收敛态独立验证协议。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np

from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S

try:
    from scripts.phase7b5a_log_frequency_p1_gate import (
        _actual_case_definitions,
        _load_material_reference,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from scripts.phase7b5i_partition_representation_split import INPUT_ITERATIONS
    from scripts.phase7b5j_prescribed_partition_audit import (
        EFFICIENCY_GROUP_LIMIT,
        H_I_RATE_TARGET,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5a_log_frequency_p1_gate import (  # type: ignore[no-redef]
        _actual_case_definitions,
        _load_material_reference,
        _trajectory_velocity_audit,
        centred_full_column_trajectory,
    )
    from phase7b5i_partition_representation_split import (  # type: ignore[no-redef]
        INPUT_ITERATIONS,
    )
    from phase7b5j_prescribed_partition_audit import (  # type: ignore[no-redef]
        EFFICIENCY_GROUP_LIMIT,
        H_I_RATE_TARGET,
    )


PROTOCOL_VERSION = 1
PHASE7B5N_PROTOCOL_SHA256 = (
    "e8d76f9603f0bbd153f0630abebade84da821d9eb79096e57d949306e19cef91"
)
SURFACE_TEMPERATURE_QUANTILES = (0.40, 0.60)
SIGNED_CELL_VELOCITY_QUANTILES = (0.20, 0.80)
SIGNED_WIDTH_CHANGE_QUANTILES = (0.20, 0.80)
VALIDATION_STATE_LABELS = ("initial", "converged")
RATE_SPECIES = ("H_I", "He_I", "He_II")
ENERGY_TARGET = 1.0e-3
RATE_TARGET = H_I_RATE_TARGET
PROJECTION_ENERGY_TARGET = 2.0e-13
RATE_QUADRATURE_TARGET = 2.0e-6


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _nearest_unused_flat_index(field, quantile, used):
    target = float(np.quantile(field, quantile))
    candidates = [
        (abs(float(field[index]) - target), index, float(field[index]))
        for index in np.ndindex(field.shape)
        if index not in used
    ]
    _, index, value = min(candidates)
    return int(index[0]), int(index[1]), value, target


def _nearest_unused_surface_phase(field, quantile, used):
    target = float(np.quantile(field, quantile))
    candidates = [
        (abs(float(value) - target), phase, float(value))
        for phase, value in enumerate(field)
        if (phase, 0) not in used
    ]
    _, phase, value = min(candidates)
    return int(phase), value, target


def _validation_cases(material, full, excluded_cases):
    phase_count = full["temperature_k"].shape[0]
    following = (np.arange(phase_count) + 1) % phase_count
    duration = material["step_duration_s"][:, None]
    old_edge = full["edges_cm"]
    new_edge = full["edges_cm"][following]
    cell_velocity_beta = 0.5 * (
        (new_edge[:, :-1] - old_edge[:, :-1])
        + (new_edge[:, 1:] - old_edge[:, 1:])
    ) / (duration * LIGHT_SPEED_CM_S)
    signed_width_change = (
        full["cell_width_cm"][following] / full["cell_width_cm"] - 1.0
    )
    following_surface_temperature = full["temperature_k"][following, 0]
    used = {
        (int(case["phase_index"]), int(case["full_depth_index"]))
        for case in excluded_cases
    }
    initial_used_count = len(used)
    cases: list[dict[str, object]] = []
    for quantile in SURFACE_TEMPERATURE_QUANTILES:
        phase, value, target = _nearest_unused_surface_phase(
            following_surface_temperature, quantile, used
        )
        used.add((phase, 0))
        cases.append(
            {
                "case": f"surface temperature q{int(100 * quantile):02d}",
                "selector": "following-state surface temperature quantile",
                "quantile": quantile,
                "selector_value": value,
                "quantile_value": target,
                "phase_index": phase,
                "following_phase_index": (phase + 1) % phase_count,
                "full_depth_index": 0,
            }
        )
    for quantile in SIGNED_CELL_VELOCITY_QUANTILES:
        phase, depth, value, target = _nearest_unused_flat_index(
            cell_velocity_beta, quantile, used
        )
        used.add((phase, depth))
        cases.append(
            {
                "case": f"signed cell velocity q{int(100 * quantile):02d}",
                "selector": "signed one-step cell-centre velocity quantile",
                "quantile": quantile,
                "selector_value": value,
                "quantile_value": target,
                "phase_index": phase,
                "following_phase_index": (phase + 1) % phase_count,
                "full_depth_index": depth,
            }
        )
    for quantile in SIGNED_WIDTH_CHANGE_QUANTILES:
        phase, depth, value, target = _nearest_unused_flat_index(
            signed_width_change, quantile, used
        )
        used.add((phase, depth))
        cases.append(
            {
                "case": f"signed width change q{int(100 * quantile):02d}",
                "selector": "signed one-step cell-width change quantile",
                "quantile": quantile,
                "selector_value": value,
                "quantile_value": target,
                "phase_index": phase,
                "following_phase_index": (phase + 1) % phase_count,
                "full_depth_index": depth,
            }
        )
    if len(cases) != 6 or len(used) != initial_used_count + len(cases):
        raise ArithmeticError("Phase 7B5o validation cases lost uniqueness")
    return cases


def build_protocol(material_path: Path, phase7b5n_protocol_path: Path):
    phase7b5n_payload = phase7b5n_protocol_path.read_bytes()
    if hashlib.sha256(phase7b5n_payload).hexdigest() != PHASE7B5N_PROTOCOL_SHA256:
        raise RuntimeError("Phase 7B5n exclusion protocol hash changed")
    phase7b5n = json.loads(phase7b5n_payload)
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    audit = _trajectory_velocity_audit(material, full)
    development_cases = _actual_case_definitions(material, full, audit)
    excluded_cases = development_cases + phase7b5n["validation"]["cases"]
    validation_cases = _validation_cases(material, full, excluded_cases)
    return {
        "phase": "7B5o preregistered protocol",
        "protocol_version": PROTOCOL_VERSION,
        "classification": (
            "[A-preregistered] same 1-2-4 representation and 4816 budget; "
            "new geometry-only cases with guaranteed initial/converged states"
        ),
        "material_reference": {
            "path": str(material_path),
            "sha256": _sha256_file(material_path),
            "phase_count": int(full["temperature_k"].shape[0]),
            "full_depth_cell_count": int(full["temperature_k"].shape[1]),
        },
        "excluded_prior_holdout": {
            "phase7b5n_protocol_path": str(phase7b5n_protocol_path),
            "phase7b5n_protocol_sha256": PHASE7B5N_PROTOCOL_SHA256,
            "excluded_case_count": len(phase7b5n["validation"]["cases"]),
        },
        "candidate": {
            "family": "strict nested 1-2-4 piecewise-constant frequency leaves",
            "leaf_group_budget": EFFICIENCY_GROUP_LIMIT,
            "parent_options": [1, 2, 4],
            "training_objective": (
                "minimize the sum over parents of the worst normalized local "
                "energy/H_I/He_I/He_II defect using exact integer dynamic programming"
            ),
            "tie_break": "retain the first lower-cost option on exact objective ties",
            "validation_feedback_allowed": False,
        },
        "development": {
            "status": "previously exposed states; not reused as validation",
            "cases": development_cases,
            "source_iterations": list(INPUT_ITERATIONS),
            "state_count": len(development_cases) * len(INPUT_ITERATIONS),
        },
        "validation": {
            "status": "new spectra selected only from material/geometric fields",
            "selection_axes": [
                "following-state surface temperature",
                "signed one-step cell-centre velocity",
                "signed one-step cell-width change",
            ],
            "cases": validation_cases,
            "source_state_labels": list(VALIDATION_STATE_LABELS),
            "state_definition": {
                "initial": "observer state n=0 before the first source update",
                "converged": "last observer state returned by the converged reference solve",
            },
            "state_count": len(validation_cases) * len(VALIDATION_STATE_LABELS),
        },
        "gates": {
            "candidate_physical_group_count": EFFICIENCY_GROUP_LIMIT,
            "candidate_and_master_energy_relative_error_strictly_below": (
                ENERGY_TARGET
            ),
            "candidate_and_master_rate_relative_error_strictly_below": RATE_TARGET,
            "rate_species": list(RATE_SPECIES),
            "projection_energy_relative_error_below": PROJECTION_ENERGY_TARGET,
            "rate_quadrature_relative_error_below": RATE_QUADRATURE_TARGET,
            "reference_source_solve_must_converge": True,
            "frozen_grid_hash_must_remain_unchanged": True,
            "converged_operator_controls_required": True,
            "no_failed_state_may_be_removed": True,
        },
        "downstream_boundary": {
            "passing_authorizes": (
                "the next angular and radiation-subgrid one-cell gate only"
            ),
            "passing_does_not_authorize": [
                "full dynamic orbit",
                "matter-temperature or population feedback",
                "Phase 4 replacement",
                "UVOT",
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--material-reference",
        type=Path,
        default=Path("outputs/phase7b4r_depth128_phase2048.npz"),
    )
    parser.add_argument(
        "--phase7b5n-protocol",
        type=Path,
        default=Path("outputs/phase7b5n_preregistered_protocol.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/phase7b5o_preregistered_protocol.json"),
    )
    args = parser.parse_args()
    protocol = build_protocol(args.material_reference, args.phase7b5n_protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(args.output, protocol)
    print(json.dumps(protocol, indent=2))


if __name__ == "__main__":
    main()
