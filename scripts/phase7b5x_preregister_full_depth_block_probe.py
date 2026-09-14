"""Phase 7B5x：冻结正式整深度最坏单块资源探针。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _source(path: str) -> dict[str, str]:
    return {"path": path, "sha256": _sha256(ROOT / path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT / "phase7b5x_preregistered_full_depth_block_probe.json",
    )
    args = parser.parse_args()
    payload = {
        "phase": "7B5x full-depth worst-block resource probe",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] resource protocol; [V] actual isolated-process "
            "measurement; [O] full-column fixed point and orbit"
        ),
        "sources": {
            "phase7b5w_summary": _source(
                "outputs/phase7b5w_translation_invariant_remap_summary.json"
            ),
            "phase7b4r_material": _source(
                "outputs/phase7b4r_depth128_phase2048.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "mixed_frame_ale": _source(
                "src/eccentric_tde_observer/mixed_frame_ale.py"
            ),
            "mixed_frame_frequency": _source(
                "src/eccentric_tde_observer/mixed_frame_frequency.py"
            ),
            "mixed_frame_streaming": _source(
                "src/eccentric_tde_observer/mixed_frame_streaming.py"
            ),
            "multigroup_continuum": _source(
                "src/eccentric_tde_observer/multigroup_continuum.py"
            ),
        },
        "configuration": {
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "angular_direction_count": 32,
            "material_cell_count": 256,
            "radiation_subcells_per_material_cell": 16,
            "radiation_depth_cell_count": 4096,
            "group_quadrature_order": 16,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "frequency_integral": "translation-invariant local overlap",
            "phase_selection": "maximum absolute full-column ALE face beta",
            "block_selection": (
                "maximum identified live-array bytes among all 128-core blocks"
            ),
            "source_iterations": 1,
            "matter_state": "frozen Phase 7B4r N128x2048 H/He state",
            "parent_microphysics_replication": (
                "compute exact parent-cell coefficients then repeat each over 16 "
                "radiation subcells because matter is piecewise constant there"
            ),
        },
        "gates": {
            "selected_phase_exactly": 1367,
            "selected_core_start_exactly": 3456,
            "selected_core_stop_exactly": 3584,
            "collision_group_count_exactly": 263,
            "outer_group_count_exactly": 397,
            "radiation_depth_cell_count_exactly": 4096,
            "parent_replication_maximum_relative_error_strictly_below": 2.0e-13,
            "minimum_intensity_at_least": 0.0,
            "all_reported_diagnostics_finite": True,
            "worker_peak_rss_strictly_below_mib": 6144.0,
            "worker_runtime_strictly_below_s": 900.0,
            "global_frequency_edges_changed": False,
            "direction_deletion": False,
            "angular_weight_renormalization": False,
        },
        "record_only_not_acceptance_gates": {
            "one_iteration_coupled_residual": (
                "one block-Jacobi map is not a converged scattering fixed point"
            ),
            "one_iteration_energy_ledger_residual": (
                "the returned diagnostic recomputes scattering from the updated field"
            ),
            "estimated_full_source_iteration_runtime": (
                "extrapolation from one worst block, not a measured full iteration"
            ),
        },
        "authorization": {
            "full_depth_block_probe_authorized": True,
            "full_column_fixed_point_authorized_if_gate_passes": False,
            "performance_architecture_decision_authorized_if_gate_passes": True,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f"{args.output.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, args.output)
    print(_sha256(args.output))


if __name__ == "__main__":
    main()
