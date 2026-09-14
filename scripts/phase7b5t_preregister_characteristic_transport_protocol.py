"""Phase 7B5t：冻结特征分区角求积与精确单元特征输运门。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SOURCES = {
    "phase7b5s_summary": OUTPUT / "phase7b5s_refined_joint_summary.json",
    "phase7b5p_master_input": OUTPUT / "phase7b5p_master_worker_input.npz",
    "mixed_frame_ale": ROOT / "src/eccentric_tde_observer/mixed_frame_ale.py",
    "radiative_transfer_1d": (
        ROOT / "src/eccentric_tde_observer/radiative_transfer_1d.py"
    ),
}
EXPECTED_SHA256 = {
    "phase7b5s_summary": (
        "815edfccea01c3410ba96823cdf60fce41101251e0e39b97bd6a85535337bedb"
    ),
    "phase7b5p_master_input": (
        "c55d52b15fb01387c7c349262f06da58f1051d38b8a3c7edf284ae2bc3fcec70"
    ),
    "mixed_frame_ale": (
        "f3f300af18d15b7c394a4c147854216e2ef1073990c3d5ff26d4953bad401e25"
    ),
    "radiative_transfer_1d": (
        "c5ddff693dbe455e989171861239ab3dc2dd0871c206a0487af4ab2f1f85b3e8"
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
        raise RuntimeError(f"frozen Phase 7B5t sources changed: {hashes}")
    previous = json.loads(SOURCES["phase7b5s_summary"].read_text(encoding="utf-8"))
    if previous["decision"]["phase7b5s_gate_passed"] is not False:
        raise RuntimeError("Phase 7B5t requires the retained Phase 7B5s failure")
    if previous["frequency_representation"]["physical_group_count"] != 9632:
        raise RuntimeError("Phase 7B5t requires the adopted 9632-group budget")
    configurations = (
        ("upwind_split_a32_d32", "upwind_finite_volume", 32, 32),
        ("upwind_split_a32_d64", "upwind_finite_volume", 32, 64),
        ("upwind_split_a48_d32", "upwind_finite_volume", 48, 32),
        ("step_split_a32_d16", "step_characteristics", 32, 16),
        ("step_split_a32_d32", "step_characteristics", 32, 32),
        ("step_split_a32_d64", "step_characteristics", 32, 64),
        ("step_split_a48_d32", "step_characteristics", 48, 32),
    )
    return {
        "phase": "7B5t characteristic angular and spatial transport gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] numerical transport replacement; [V] analytic, "
            "conservation and exposed stress-state tests; [O] full column and orbit"
        ),
        "sources": {
            name: {
                "path": str(path.relative_to(ROOT)),
                "sha256": hashes[name],
            }
            for name, path in SOURCES.items()
        },
        "stress_state": previous["stress_state"],
        "frequency_representation": previous["frequency_representation"],
        "angular_quadrature": {
            "family": "two-interval Gauss-Legendre",
            "split_definition": (
                "mean of the two parent ALE face velocities divided by c"
            ),
            "reason": (
                "separate the incoming-boundary characteristic discontinuity"
            ),
            "free_fit_parameter": False,
        },
        "spatial_schemes": {
            "historical_control": "upwind_finite_volume",
            "candidate": "step_characteristics",
            "candidate_definition": (
                "exact constant-source integration in each cell with linear ALE "
                "face speed and shared conservative face intensity"
            ),
        },
        "analytic_controls": {
            "depth_counts": [16, 32, 64],
            "linear_source_total_optical_depth": 2.0,
            "upwind_expected_order_interval": [0.8, 1.2],
            "step_expected_order_strictly_above": 1.8,
            "constant_source_maximum_error_strictly_below": 1.0e-11,
            "moving_grid_ledger_strictly_below": 1.0e-10,
        },
        "configurations": [
            {
                "key": key,
                "spatial_scheme": scheme,
                "angular_direction_count": angle,
                "radiation_subcells_per_parent": depth,
            }
            for key, scheme, angle, depth in configurations
        ],
        "comparisons": {
            "split_angle_upwind": [
                "upwind_split_a32_d32",
                "upwind_split_a48_d32",
            ],
            "split_angle_step": [
                "step_split_a32_d32",
                "step_split_a48_d32",
            ],
            "upwind_depth": [
                "upwind_split_a32_d32",
                "upwind_split_a32_d64",
            ],
            "step_depth_candidate": [
                "step_split_a32_d16",
                "step_split_a32_d32",
            ],
            "step_depth_confirmation": [
                "step_split_a32_d32",
                "step_split_a32_d64",
            ],
            "joint_candidate": [
                "step_split_a32_d16",
                "step_split_a48_d32",
            ],
        },
        "gates": {
            "all_science_errors_strictly_below": 1.0e-3,
            "fixed_point_tolerance": 1.0e-10,
            "global_coupled_residual_strictly_below": 1.0e-9,
            "energy_ledger_residual_strictly_below": 1.0e-9,
            "minimum_intensity_at_least": 0.0,
            "physical_group_count_exactly": 9632,
            "edge_hash_unchanged": True,
            "fresh_process_peak_rss_strictly_below_mib": 6144.0,
            "characteristics_do_not_reverse_at_quadrature_nodes": True,
        },
        "candidate_if_all_gates_pass": {
            "physical_frequency_groups": 9632,
            "angular_quadrature": "characteristic_split",
            "angular_direction_count": 32,
            "spatial_scheme": "step_characteristics",
            "radiation_subcells_per_parent": 16,
        },
        "authorization": {
            "frequency_budget_changed": True,
            "frequency_group_budget": 9632,
            "frequency_budget_authorized_by_user": True,
            "one_cell_transport_replacement_gate_authorized": True,
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
            OUTPUT
            / "phase7b5t_preregistered_characteristic_transport_protocol.json"
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
