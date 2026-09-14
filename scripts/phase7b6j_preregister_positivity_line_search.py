"""Phase 7B6j：冻结从第 12 次状态分叉的正性边界线搜索门。"""

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
    manifest_path = OUTPUT / "checkpoints/phase7b6i_work/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"] != "running" or manifest["current_global_iteration"] != 12:
        raise RuntimeError("Phase 7B6j requires the paused complete iteration-12 manifest")
    state_path = Path(manifest["current_state_path"])
    residual_path = Path(manifest["previous_residual_path"])
    state_hash = _sha256(state_path)
    residual_hash = _sha256(residual_path)
    payload = {
        "phase": "7B6j positivity-boundary global line-search gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] scalar positivity-boundary line search and 1.8 control; "
            "[V] branched full-frequency residual comparison; "
            "[O] converged full-column fixed point"
        ),
        "sources": {
            "phase7b6i_protocol": _source(
                "outputs/phase7b6i_preregistered_converged_full_frequency.json"
            ),
            "phase7b6h_protocol": _source(
                "outputs/phase7b6h_preregistered_full_frequency_aitken.json"
            ),
            "phase7b6h_worker": _source(
                "scripts/phase7b6h_full_frequency_aitken.py"
            ),
            "phase7b6i_manifest": {
                "path": str(manifest_path.relative_to(ROOT)),
                "sha256": _sha256(manifest_path),
            },
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
            "global_iteration": 12,
            "state_path": str(state_path.relative_to(ROOT)),
            "state_sha256": state_hash,
            "residual_path": str(residual_path.relative_to(ROOT)),
            "residual_sha256": residual_hash,
            "previous_accepted_weight": manifest["previous_accepted_weight"],
            "size_bytes_each": state_path.stat().st_size,
        },
        "configuration": {
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "process_count": 2,
            "common_map_iteration": 13,
            "comparison_map_iteration": 14,
            "aitken_formula_unchanged": True,
            "positivity_bound": (
                "omega_pos = min I/(-r) over every cell with r<0; infinity if none"
            ),
            "line_search_weight": (
                "Aitken weight if it is below omega_pos; otherwise the largest "
                "floating-point number strictly below omega_pos"
            ),
            "floating_predecessor": "numpy.nextafter(omega_pos, 0.0)",
            "fixed_control_weight": 1.8,
            "cellwise_clipping": False,
            "intensity_floor": False,
            "point_deletion": False,
            "line_branch_state_checkpoint": (
                "outputs/checkpoints/phase7b6j_line_search_iteration14.dat"
            ),
            "line_branch_residual_checkpoint": (
                "outputs/checkpoints/phase7b6j_line_search_residual14.dat"
            ),
            "original_phase7b6i_manifest_modified": False,
            "matter_feedback": False,
        },
        "gates": {
            "initial_state_sha256_exactly": state_hash,
            "initial_residual_sha256_exactly": residual_hash,
            "each_map_block_count_exactly": 76,
            "each_map_unique_group_count_exactly": 9632,
            "line_search_weight_strictly_above_control": 1.8,
            "all_states_nonnegative": True,
            "all_residuals_weights_bounds_and_dot_products_finite": True,
            "line_iteration14_residual_strictly_below_control_iteration14": True,
            "line_iteration14_residual_strictly_below_iteration13_fraction": 0.95,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_map_wall_time_strictly_below_s": 900.0,
            "each_retained_checkpoint_size_bytes_exactly": state_path.stat().st_size,
            "temporary_branch_states_removed": True,
        },
        "authorization": {
            "positivity_boundary_branch_gate_authorized": True,
            "line_search_fixed_point_continuation_authorized_if_passes": True,
            "full_column_fixed_point_authorized": False,
            "matter_feedback_authorized": False,
            "full_orbit_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6j_preregistered_positivity_line_search.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
