"""Phase 7B5v：冻结流式频率块与守恒 turning-ray 算子门。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SOURCES = {
    "phase7b5u_summary": OUTPUT / "phase7b5u_full_column_admission.json",
    "phase7b4r_material": OUTPUT / "phase7b4r_depth128_phase2048.npz",
    "phase7b5p_master_input": OUTPUT / "phase7b5p_master_worker_input.npz",
    "mixed_frame_ale": ROOT / "src/eccentric_tde_observer/mixed_frame_ale.py",
    "mixed_frame_frequency": (
        ROOT / "src/eccentric_tde_observer/mixed_frame_frequency.py"
    ),
    "mixed_frame_streaming": (
        ROOT / "src/eccentric_tde_observer/mixed_frame_streaming.py"
    ),
    "radiative_transfer_1d": (
        ROOT / "src/eccentric_tde_observer/radiative_transfer_1d.py"
    ),
}
EXPECTED_SHA256 = {
    "phase7b5u_summary": (
        "5f074a4265b3544993c21c4d841467c12d79f1172b12e59faaeb5d722897e590"
    ),
    "phase7b4r_material": (
        "33f248d5cf35ac07fffd139e1cd99d4edefa590debf7e109f67f2dbc57adf455"
    ),
    "phase7b5p_master_input": (
        "c55d52b15fb01387c7c349262f06da58f1051d38b8a3c7edf284ae2bc3fcec70"
    ),
    "mixed_frame_ale": (
        "cbb2f816135a573963ad068f9c270ae76e7faf6825666db1d0c3b5807bb1fd3c"
    ),
    "mixed_frame_frequency": (
        "84f883966242c5e569e9cac8a65520b8163d489fc5cd5e11e5d5d93d4443aea1"
    ),
    "mixed_frame_streaming": (
        "0d3ba7c792ab0e3540f04fa2f676503e49fa8214d2d3dc2c09c7daf6ebb23c3f"
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
        raise RuntimeError(f"frozen Phase 7B5v sources changed: {hashes}")
    previous = json.loads(SOURCES["phase7b5u_summary"].read_text(encoding="utf-8"))
    if previous["decision"]["requires_frequency_streaming"] is not True:
        raise RuntimeError("Phase 7B5v requires the retained monolithic-memory failure")
    if previous["decision"]["requires_turning_ray_treatment"] is not True:
        raise RuntimeError("Phase 7B5v requires the retained turning-ray failure")
    return {
        "phase": "7B5v streamed frequency and turning-ray operator gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] numerical repair; [V] discrete, monolithic and "
            "actual-state equivalence; [O] full-depth resource probe"
        ),
        "sources": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": hashes[name]}
            for name, path in SOURCES.items()
        },
        "formal_configuration": previous["accepted_single_cell_configuration"],
        "turning_ray_method": {
            "nonturning_directions": "step_characteristics",
            "turning_directions": "implicit conservative upwind tridiagonal solve",
            "direction_deletion": False,
            "angular_weight_renormalization": False,
        },
        "streaming_method": {
            "global_iteration": "block Jacobi",
            "global_frequency_edges_changed": False,
            "halo_definition": "exact full-grid groups covering both Lorentz remaps",
            "frequency_remap": "column-batched conservative P0 integral",
            "actual_core_group_counts": [256, 512],
        },
        "gates": {
            "turning_dense_system_maximum_error_strictly_below": 1.0e-12,
            "turning_coupled_residual_strictly_below": 1.0e-12,
            "turning_energy_ledger_strictly_below": 1.0e-12,
            "minimum_intensity_at_least": 0.0,
            "nonturning_hybrid_equals_step_exactly": True,
            "small_one_iteration_stream_vs_monolithic_strictly_below": 1.0e-12,
            "actual_fixed_point_tolerance": 1.0e-10,
            "actual_lab_intensity_maximum_error_strictly_below": 5.0e-9,
            "actual_volume_spectrum_l1_strictly_below": 5.0e-9,
            "actual_scalar_observable_error_strictly_below": 5.0e-9,
            "actual_worker_peak_rss_strictly_below_mib": 6144.0,
            "physical_group_count_exactly": 9632,
            "global_active_edge_hash_unchanged": True,
        },
        "authorization": {
            "streaming_and_turning_operator_gate_authorized": True,
            "full_depth_block_resource_probe_authorized_if_gate_passes": True,
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
        default=OUTPUT / "phase7b5v_preregistered_streaming_turning_protocol.json",
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
