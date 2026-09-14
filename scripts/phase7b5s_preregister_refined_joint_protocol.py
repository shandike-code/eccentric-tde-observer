"""Phase 7B5s：冻结更细 9632 组单单元联合参考。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SOURCES = {
    "phase7b5r_summary": OUTPUT / "phase7b5r_joint_convergence_summary.json",
    "phase7b5r_protocol": (
        OUTPUT / "phase7b5r_preregistered_joint_convergence_protocol.json"
    ),
    "phase7b5p_master_input": OUTPUT / "phase7b5p_master_worker_input.npz",
}
EXPECTED_SHA256 = {
    "phase7b5r_summary": (
        "da380192ea70b7375fd573d83b740e1aff9b5034d2153f8d27c506c51027a846"
    ),
    "phase7b5r_protocol": (
        "ff7a39925d5819d0267594a4221467ed211a634f3e5761b0575698d2c6675c0f"
    ),
    "phase7b5p_master_input": (
        "c55d52b15fb01387c7c349262f06da58f1051d38b8a3c7edf284ae2bc3fcec70"
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
        raise RuntimeError(f"frozen Phase 7B5s sources changed: {hashes}")
    phase7b5r = json.loads(SOURCES["phase7b5r_summary"].read_text())
    if phase7b5r["decision"]["phase7b5r_gate_passed"] is not False:
        raise RuntimeError("Phase 7B5s requires the retained Phase 7B5r failure")
    if phase7b5r["frequency_representation"]["physical_group_count"] != 9632:
        raise RuntimeError("Phase 7B5s requires the adopted 9632-group budget")
    configurations = (
        ("angle24_subcell32", 24, 32),
        ("angle32_subcell32", 32, 32),
        ("angle48_subcell32", 48, 32),
        ("angle32_subcell64", 32, 64),
        ("angle48_subcell64", 48, 64),
    )
    return {
        "phase": "7B5s refined 9632-group one-cell joint reference",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] refined exposed one-cell numerical reference; "
            "[V] converged fixed-point observables and resources; [O] full column, "
            "orbit and matter feedback"
        ),
        "sources": {
            name: {
                "path": str(path.relative_to(ROOT)),
                "sha256": hashes[name],
            }
            for name, path in SOURCES.items()
        },
        "stress_state": phase7b5r["stress_state"],
        "frequency_representation": phase7b5r["frequency_representation"],
        "host_resource_preflight": {
            "physical_memory_gib": 16.0,
            "memory_pressure_free_percent": 59,
            "maximum_fresh_process_peak_rss_mib": 6144.0,
            "basis": (
                "Phase 7B5r measured 1046.47 MiB at 24x32; the largest 48x64 "
                "configuration has four times as many active unknowns"
            ),
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
                "coarse_control": "angle24_subcell32",
                "candidate": "angle32_subcell32",
                "reference": "angle48_subcell32",
            },
            "radiation_subgrid": {
                "candidate": "angle32_subcell32",
                "reference": "angle32_subcell64",
            },
            "joint": {
                "candidate": "angle32_subcell32",
                "reference": "angle48_subcell64",
            },
        },
        "initialization": {
            "source_iteration_initial_guess": None,
            "description": "operator default initial radiation field for every run",
        },
        "comparison_observables": tuple(
            phase7b5r["comparisons"]["joint16x16_vs24x32"]["errors"]
        ),
        "gates": {
            "production_relative_error_strictly_below": 1.0e-3,
            "fixed_point_tolerance": 1.0e-10,
            "maximum_fixed_point_iterations": 8192,
            "global_coupled_residual_strictly_below": 1.0e-9,
            "energy_ledger_residual_strictly_below": 1.0e-9,
            "minimum_intensity_at_least": 0.0,
            "physical_group_count_exactly": 9632,
            "edge_hash_unchanged": True,
            "fresh_process_peak_rss_strictly_below_mib": 6144.0,
            "angle_candidate_vs_reference_all_observables": True,
            "subgrid_candidate_vs_reference_all_observables": True,
            "joint_candidate_vs_reference_all_observables": True,
        },
        "authorization": {
            "frequency_budget_changed": True,
            "frequency_group_budget": 9632,
            "frequency_budget_authorized_by_user": True,
            "refined_angle_or_radiation_subgrid_gate_authorized": True,
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
        default=(OUTPUT / "phase7b5s_preregistered_refined_joint_protocol.json"),
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
