"""Phase 7B5r：冻结 9632 组单单元角度--辐射子网格联合门。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SOURCES = {
    "phase7b5q_summary": OUTPUT / "phase7b5q_fixed_point_resource_summary.json",
    "phase7b5p_master_input": OUTPUT / "phase7b5p_master_worker_input.npz",
    "phase7b5o_summary": OUTPUT / "phase7b5o_summary.json",
    "phase7b5o_protocol": OUTPUT / "phase7b5o_preregistered_protocol.json",
}
EXPECTED_SHA256 = {
    "phase7b5q_summary": (
        "02e3dc37ae5c186d494d28ebaf26450cbdeb59698316837c242643dc4884e53d"
    ),
    "phase7b5p_master_input": (
        "c55d52b15fb01387c7c349262f06da58f1051d38b8a3c7edf284ae2bc3fcec70"
    ),
    "phase7b5o_summary": (
        "369ed77391cf746758f24906ba0c7d5d58838415e52ca2befed97efa35ae3790"
    ),
    "phase7b5o_protocol": (
        "ff63f6f46cd71c96089c714a600f8ef7a31d71bf92afd306aec743a89e94a176"
    ),
}


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


def build_protocol() -> dict[str, object]:
    hashes = {name: _sha256_file(path) for name, path in SOURCES.items()}
    if hashes != EXPECTED_SHA256:
        raise RuntimeError(f"frozen Phase 7B5r sources changed: {hashes}")
    phase7b5q = json.loads(SOURCES["phase7b5q_summary"].read_text())
    phase7b5o = json.loads(SOURCES["phase7b5o_summary"].read_text())
    if not phase7b5o["decision"][
        "nested_master_joint_energy_and_H_He_rate_gate_passed"
    ]:
        raise RuntimeError("9632-group master did not pass the Phase 7B5o science gate")
    if not all(
        phase7b5q["decision"][key]
        for key in (
            "all_workers_exit_zero",
            "all_fixed_points_converged",
            "all_global_coupled_residuals_passed",
            "all_energy_ledger_residuals_passed",
            "all_intensities_nonnegative",
            "cross_start_final_intensity_passed",
            "edge_hashes_unchanged",
        )
    ):
        raise RuntimeError("Phase 7B5q fixed-point resource gate is incomplete")
    configurations = (
        ("angle8_subcell1", 8, 1),
        ("angle16_subcell1", 16, 1),
        ("angle24_subcell1", 24, 1),
        ("angle16_subcell8", 16, 8),
        ("angle16_subcell16", 16, 16),
        ("angle16_subcell32", 16, 32),
        ("angle24_subcell32", 24, 32),
    )
    return {
        "phase": "7B5r 9632-group one-cell angle-radiation-subgrid gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] exposed one-cell stress and prescribed numerical "
            "paths; [V] converged fixed-point observables; [O] full column/orbit "
            "and matter feedback"
        ),
        "sources": {
            name: {
                "path": str(path.relative_to(ROOT)),
                "sha256": hashes[name],
            }
            for name, path in SOURCES.items()
        },
        "stress_state": phase7b5q["stress_state"],
        "frequency_representation": {
            "physical_group_count": 9632,
            "input_source": "phase7b5p_master_input",
            "active_edge_sha256": phase7b5q["aggregate"]["master"]
            ["default_initial"]["active_edge_sha256"],
            "budget_status": "adopted by explicit user authorization",
        },
        "configurations": [
            {
                "key": key,
                "angular_direction_count": angle,
                "radiation_subcells_per_parent": subcells,
            }
            for key, angle, subcells in configurations
        ],
        "paths": {
            "angle": {
                "candidate": "angle16_subcell1",
                "coarse_control": "angle8_subcell1",
                "reference": "angle24_subcell1",
            },
            "radiation_subgrid": {
                "candidate": "angle16_subcell16",
                "coarse_control": "angle16_subcell8",
                "reference": "angle16_subcell32",
            },
            "joint": {
                "candidate": "angle16_subcell16",
                "reference": "angle24_subcell32",
            },
        },
        "initialization": {
            "source_iteration_initial_guess": None,
            "description": (
                "operator default initial radiation field for every angle/depth "
                "configuration; no angular or depth interpolation warm start"
            ),
        },
        "radiation_subgrid_construction": {
            "old_and_new_edges": "affine subdivision of the frozen parent cell",
            "material_velocity": "repeat the frozen parent beta in every subcell",
            "material_state": (
                "repeat the frozen parent temperature, density and H/He fractions; "
                "only radiation depth degrees of freedom are added"
            ),
        },
        "comparison_observables": (
            "frequency-integrated volume-mean comoving intensity",
            "H I photoionization rate",
            "He I photoionization rate",
            "He II photoionization rate",
            "final radiation energy per area",
            "two-sided emergent radiative flux",
            "integrated material heating",
            "volume-mean comoving spectrum L1 distance",
        ),
        "gates": {
            "production_relative_error_strictly_below": 1.0e-3,
            "fixed_point_tolerance": 1.0e-10,
            "maximum_fixed_point_iterations": 8192,
            "global_coupled_residual_strictly_below": 1.0e-9,
            "energy_ledger_residual_strictly_below": 1.0e-9,
            "minimum_intensity_at_least": 0.0,
            "all_workers_exit_zero": True,
            "physical_group_count_exactly": 9632,
            "edge_hash_unchanged": True,
            "angle_candidate_vs_reference_all_observables": True,
            "subgrid_candidate_vs_reference_all_observables": True,
            "joint_candidate_vs_reference_all_observables": True,
        },
        "authorization": {
            "frequency_budget_changed": True,
            "frequency_group_budget": 9632,
            "frequency_budget_authorized_by_user": True,
            "angle_or_radiation_subgrid_gate_authorized": True,
            "full_column_authorized": False,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
            "phase4_replacement_authorized": False,
            "uvot_authorized": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            OUTPUT / "phase7b5r_preregistered_joint_convergence_protocol.json"
        ),
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.force:
        raise FileExistsError(f"refusing to overwrite {args.output}; pass --force")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(args.output, build_protocol())
    print(_sha256_file(args.output))


if __name__ == "__main__":
    main()
