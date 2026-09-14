"""Phase 7B5u：冻结完整动态柱的资源与特征线准入门。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SOURCES = {
    "phase7b5t_summary": OUTPUT / "phase7b5t_characteristic_transport_summary.json",
    "phase7b4r_material": OUTPUT / "phase7b4r_depth128_phase2048.npz",
    "phase7b5p_master_input": OUTPUT / "phase7b5p_master_worker_input.npz",
    "mixed_frame_ale": ROOT / "src/eccentric_tde_observer/mixed_frame_ale.py",
    "radiative_transfer_1d": (
        ROOT / "src/eccentric_tde_observer/radiative_transfer_1d.py"
    ),
}
EXPECTED_SHA256 = {
    "phase7b5t_summary": (
        "5c29b4563913fd9c7eddfba9f7d7f20f53604d0cba6042243a8d2358563bf61f"
    ),
    "phase7b4r_material": (
        "33f248d5cf35ac07fffd139e1cd99d4edefa590debf7e109f67f2dbc57adf455"
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
        raise RuntimeError(f"frozen Phase 7B5u sources changed: {hashes}")
    previous = json.loads(SOURCES["phase7b5t_summary"].read_text(encoding="utf-8"))
    accepted = previous["accepted_one_cell_configuration"]
    expected = {
        "physical_frequency_groups": 9632,
        "angular_quadrature": "characteristic_split",
        "angular_direction_count": 32,
        "spatial_scheme": "step_characteristics",
        "radiation_subcells_per_parent": 16,
    }
    if accepted != expected:
        raise RuntimeError("Phase 7B5u requires the accepted Phase 7B5t configuration")
    return {
        "phase": "7B5u full-column resource and characteristic admission",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] machine admission; [V] all-phase resource and "
            "characteristic audit; [O] streamed full-column solver"
        ),
        "sources": {
            name: {
                "path": str(path.relative_to(ROOT)),
                "sha256": hashes[name],
            }
            for name, path in SOURCES.items()
        },
        "accepted_single_cell_configuration": accepted,
        "full_column_shape": {
            "orbital_phase_count": 2048,
            "material_cell_count": 256,
            "radiation_depth_cell_count": 4096,
        },
        "angular_split_mu": 0.0,
        "memory_accounting": {
            "dtype": "float64",
            "identified_simultaneous_frequency_angle_depth_arrays": [
                "initial_active",
                "outer_guard_template",
                "lab_extinction",
                "current_active",
                "outer_work",
                "comoving_angle_intensity",
                "lab_emissivity",
                "updated_active",
                "transport_face_intensity",
            ],
            "excluded_from_lower_bound": (
                "two-dimensional material arrays, remap temporaries and returned "
                "diagnostic arrays"
            ),
            "monolithic_admission_fraction_of_physical_memory": 0.75,
        },
        "gates": {
            "source_hashes_unchanged": True,
            "phase_count_exactly": 2048,
            "all_step_durations_finite_and_positive": True,
            "centred_full_column_mirror_residual_at_most": 2.0e-15,
            "current_monolithic_identified_live_bytes_below_memory_fraction": 0.75,
            "pure_step_characteristics_reversing_phase_count_exactly": 0,
        },
        "decision_rules": {
            "if_monolithic_memory_fails": (
                "require bounded-memory frequency streaming with the global "
                "frequency grid retained"
            ),
            "if_characteristic_reversal_fails": (
                "require a separately gated conservative turning-ray treatment; "
                "do not delete grazing directions"
            ),
            "production_full_column_requires_both_repairs": True,
        },
        "bounded_memory_probe": {
            "initial_core_frequency_groups": 256,
            "status": "[A-computational] probe only; halo and convergence not yet accepted",
        },
        "authorization": {
            "read_only_all_phase_audit_authorized": True,
            "monolithic_full_column_run_authorized": False,
            "streamed_solver_implementation_authorized": True,
            "matter_feedback_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT / "phase7b5u_preregistered_full_column_admission.json",
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
