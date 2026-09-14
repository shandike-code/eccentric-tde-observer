"""Phase 7B6h：冻结从第 4 次检查点续跑的四次全频 Aitken 门。"""

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
    local = json.loads(
        (OUTPUT / "phase7b6g_vector_aitken_summary.json").read_text(
            encoding="utf-8"
        )
    )
    global_pilot = json.loads(
        (OUTPUT / "phase7b6f_full_frequency_contraction_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if local["decision"]["phase7b6g_gate_passed"] is not True:
        raise RuntimeError("Phase 7B6h requires the accepted local Aitken gate")
    if global_pilot["decision"]["phase7b6f_gate_passed"] is not True:
        raise RuntimeError("Phase 7B6h requires the accepted global checkpoint")
    checkpoint = ROOT / global_pilot["final_checkpoint_path"]
    if checkpoint.stat().st_size != global_pilot["final_checkpoint_size_bytes"]:
        raise RuntimeError("Phase 7B6f checkpoint size changed")
    payload = {
        "phase": "7B6h bounded full-frequency vector-Aitken pilot",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] four resumed maps, vector Aitken and two checkpoints; "
            "[V] global contraction, positivity and resources; "
            "[O] converged full-column fixed point"
        ),
        "sources": {
            "phase7b6f_summary": _source(
                "outputs/phase7b6f_full_frequency_contraction_summary.json"
            ),
            "phase7b6g_summary": _source(
                "outputs/phase7b6g_vector_aitken_summary.json"
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
            "path": global_pilot["final_checkpoint_path"],
            "sha256": global_pilot["final_checkpoint_sha256"],
            "size_bytes": global_pilot["final_checkpoint_size_bytes"],
            "completed_source_maps": 4,
        },
        "configuration": {
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "process_count": 2,
            "additional_source_map_count_exactly": 4,
            "output_completed_source_maps": 8,
            "first_resumed_map": "guarded fallback because no retained previous residual",
            "fallback_weights": [1.8, 1.5, 1.2, 1.0],
            "later_maps": "vector Aitken, then guarded fallback if the entire trial is invalid",
            "aitken_inner_product": "unweighted Euclidean over all global intensity cells",
            "weight_clipping": False,
            "cellwise_clipping": False,
            "state_checkpoint_path": (
                "outputs/checkpoints/phase7b6h_full_frequency_iteration8.dat"
            ),
            "residual_checkpoint_path": (
                "outputs/checkpoints/phase7b6h_full_frequency_residual8.dat"
            ),
            "matter_feedback": False,
        },
        "gates": {
            "initial_checkpoint_sha256_exactly": global_pilot[
                "final_checkpoint_sha256"
            ],
            "each_iteration_block_count_exactly": 76,
            "each_iteration_unique_group_count_exactly": 9632,
            "additional_source_map_count_exactly": 4,
            "minimum_intensity_at_least": 0.0,
            "all_residuals_weights_and_dot_products_finite": True,
            "aitken_step_count_at_least": 2,
            "final_to_first_resumed_raw_residual_strictly_below": 0.8,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_iteration_wall_time_strictly_below_s": 900.0,
            "each_checkpoint_size_bytes_exactly": global_pilot[
                "final_checkpoint_size_bytes"
            ],
            "all_secondary_temporary_states_removed": True,
        },
        "authorization": {
            "bounded_full_frequency_aitken_pilot_authorized": True,
            "full_frequency_aitken_fixed_point_continuation_authorized_if_passes": True,
            "full_column_fixed_point_authorized": False,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6h_preregistered_full_frequency_aitken.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
