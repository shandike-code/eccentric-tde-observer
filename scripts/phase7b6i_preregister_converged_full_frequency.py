"""Phase 7B6i：冻结可恢复的正式全频 Aitken 固定点。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _source(path: str) -> dict[str, str]:
    return {"path": path, "sha256": _sha256(ROOT / path)}


def main() -> None:
    previous = json.loads(
        (OUTPUT / "phase7b6h_full_frequency_aitken_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if previous["decision"]["phase7b6h_gate_passed"] is not True:
        raise RuntimeError("Phase 7B6i requires the accepted Phase 7B6h pilot")
    payload = {
        "phase": "7B6i recoverable converged full-frequency Aitken fixed point",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] recoverable continuation and final diagnostics; "
            "[V] converged full-frequency radiation fixed point; "
            "[O] matter feedback and orbit"
        ),
        "sources": {
            "phase7b6h_summary": _source(
                "outputs/phase7b6h_full_frequency_aitken_summary.json"
            ),
            "phase7b6h_protocol": _source(
                "outputs/phase7b6h_preregistered_full_frequency_aitken.json"
            ),
            "phase7b6h_worker": _source(
                "scripts/phase7b6h_full_frequency_aitken.py"
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
        "initial_checkpoint": {
            "state_path": previous["state_checkpoint_path"],
            "state_sha256": previous["state_checkpoint_sha256"],
            "residual_path": previous["residual_checkpoint_path"],
            "residual_sha256": previous["residual_checkpoint_sha256"],
            "size_bytes_each": previous["checkpoint_size_bytes"],
            "completed_source_maps": 8,
            "previous_accepted_weight": previous["final_accepted_weight"],
        },
        "configuration": {
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "process_count": 2,
            "fixed_point_tolerance": 1.0e-10,
            "maximum_additional_source_maps": 32,
            "aitken_inner_product": "unweighted Euclidean over all global intensity cells",
            "fallback_weights": [1.8, 1.5, 1.2, 1.0],
            "converged_closure_weight": 1.0,
            "work_directory": "outputs/checkpoints/phase7b6i_work",
            "atomic_manifest": "outputs/checkpoints/phase7b6i_work/manifest.json",
            "manifest_updated_only_after_complete_valid_iteration": True,
            "weight_clipping": False,
            "cellwise_clipping": False,
            "final_state_path": "outputs/checkpoints/phase7b6i_converged_state.dat",
            "final_residual_path": "outputs/checkpoints/phase7b6i_converged_residual.dat",
            "full_block_diagnostics_after_convergence": True,
            "matter_feedback": False,
        },
        "gates": {
            "initial_state_sha256_exactly": previous["state_checkpoint_sha256"],
            "initial_residual_sha256_exactly": previous[
                "residual_checkpoint_sha256"
            ],
            "each_iteration_block_count_exactly": 76,
            "each_iteration_unique_group_count_exactly": 9632,
            "converged_raw_fixed_point_residual_at_most": 1.0e-10,
            "final_audit_raw_fixed_point_residual_at_most": 1.0e-10,
            "maximum_block_coupled_residual_strictly_below": 1.0e-8,
            "maximum_block_energy_ledger_residual_strictly_below": 1.0e-8,
            "minimum_intensity_at_least": 0.0,
            "all_residuals_weights_dot_products_and_diagnostics_finite": True,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_iteration_wall_time_strictly_below_s": 900.0,
            "each_final_checkpoint_size_bytes_exactly": previous[
                "checkpoint_size_bytes"
            ],
            "unused_work_states_removed_after_success": True,
        },
        "authorization": {
            "recoverable_full_frequency_fixed_point_authorized": True,
            "full_column_radiation_fixed_point_accepted_if_all_gates_pass": True,
            "matter_feedback_authorized_if_all_gates_pass": True,
            "full_orbit_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6i_preregistered_converged_full_frequency.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
