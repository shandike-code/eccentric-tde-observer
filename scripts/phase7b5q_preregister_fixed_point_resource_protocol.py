"""Phase 7B5q：冻结完整固定点单单元资源审计协议。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SOURCES = {
    "phase7b5p_summary": OUTPUT / "phase7b5p_resource_profile_summary.json",
    "candidate_input": OUTPUT / "phase7b5p_candidate_worker_input.npz",
    "master_input": OUTPUT / "phase7b5p_master_worker_input.npz",
}
EXPECTED_SHA256 = {
    "phase7b5p_summary": (
        "d75b441c1528cd7f5dfef79eda9ec2220e44bf88d3a0b8cbce7dc8b4fc263316"
    ),
    "candidate_input": (
        "3575aacdd3bb9223b9efdca99ea12a33235035a1c2b983d566b2ec252e75f18b"
    ),
    "master_input": (
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
        raise RuntimeError(f"frozen Phase 7B5p sources changed: {hashes}")
    phase7b5p = json.loads(SOURCES["phase7b5p_summary"].read_text())
    if phase7b5p["decision"]["frequency_budget_changed"] is not False:
        raise RuntimeError("Phase 7B5p unexpectedly changed the frequency budget")
    run_order = [
        ("candidate", "projected_converged"),
        ("master", "projected_converged"),
        ("master", "default_initial"),
        ("candidate", "default_initial"),
        ("master", "default_initial"),
        ("candidate", "default_initial"),
        ("candidate", "projected_converged"),
        ("master", "projected_converged"),
        ("candidate", "default_initial"),
        ("master", "default_initial"),
        ("master", "projected_converged"),
        ("candidate", "projected_converged"),
        ("master", "projected_converged"),
        ("candidate", "projected_converged"),
        ("candidate", "default_initial"),
        ("master", "default_initial"),
        ("candidate", "projected_converged"),
        ("candidate", "default_initial"),
        ("master", "projected_converged"),
        ("master", "default_initial"),
    ]
    return {
        "phase": "7B5q converged fixed-point resource envelope",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] exposed one-cell stress and two prescribed starts; "
            "[V] converged fixed-point runtime/RSS; [O] frequency budget"
        ),
        "sources": {
            name: {
                "path": str(path.relative_to(ROOT)),
                "sha256": hashes[name],
            }
            for name, path in SOURCES.items()
        },
        "stress_state": phase7b5p["stress_state"],
        "representations": {
            "candidate": {
                "physical_group_count": 4816,
                "input_source": "candidate_input",
                "active_edge_sha256": phase7b5p["aggregate"]["candidate"][
                    "active_edge_sha256"
                ],
            },
            "master": {
                "physical_group_count": 9632,
                "input_source": "master_input",
                "active_edge_sha256": phase7b5p["aggregate"]["master"][
                    "active_edge_sha256"
                ],
            },
        },
        "start_modes": {
            "projected_converged": (
                "projection of the separately converged high-resolution source"
            ),
            "default_initial": (
                "operator default initial radiation field; no source warm start"
            ),
        },
        "measurement": {
            "fresh_process_per_run": True,
            "repeat_count_per_representation_and_start": 5,
            "worker_order": [
                {"representation": representation, "start_mode": start_mode}
                for representation, start_mode in run_order
            ],
            "operator": "full fixed point with tolerance 1e-10",
            "peak_metric": "ru_maxrss converted by operating-system convention",
            "maximum_iterations": 8192,
        },
        "gates": {
            "all_workers_exit_zero": True,
            "fresh_worker_pid_each_run": True,
            "all_fixed_points_converged": True,
            "global_coupled_residual_strictly_below": 1.0e-9,
            "energy_ledger_residual_strictly_below": 1.0e-9,
            "minimum_intensity_at_least": 0.0,
            "cross_start_final_intensity_relative_difference_strictly_below": (
                1.0e-8
            ),
            "deterministic_result_hash_within_configuration": True,
            "edge_hashes_unchanged": True,
        },
        "authorization": {
            "frequency_budget_changed": False,
            "angle_or_radiation_subgrid_gate_authorized": False,
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
        default=OUTPUT / "phase7b5q_preregistered_fixed_point_resource_protocol.json",
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
