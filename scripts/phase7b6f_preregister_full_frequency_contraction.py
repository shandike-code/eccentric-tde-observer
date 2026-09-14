"""Phase 7B6f：冻结四次全频率保护收缩试验。"""

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
    accepted = json.loads(
        (OUTPUT / "phase7b6d_full_depth_contraction_summary.json").read_text(
            encoding="utf-8"
        )
    )
    rejected = json.loads(
        (OUTPUT / "phase7b6e_extended_relaxation_summary.json").read_text(
            encoding="utf-8"
        )
    )
    initial = json.loads(
        (OUTPUT / "phase7b6a_full_frequency_source_iteration_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if accepted["decision"]["phase7b6d_gate_passed"] is not True:
        raise RuntimeError("Phase 7B6f requires the accepted 1.8 full-depth pilot")
    if rejected["decision"]["phase7b6e_gate_passed"] is not False:
        raise RuntimeError("Phase 7B6f requires the retained extended-weight failure")
    payload = {
        "phase": "7B6f bounded full-frequency guarded-contraction pilot",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] four-map full-frequency pilot and checkpoint; "
            "[V] global raw residual, positivity and resources; "
            "[O] converged full-column fixed point"
        ),
        "sources": {
            "phase7b6a_summary": _source(
                "outputs/phase7b6a_full_frequency_source_iteration_summary.json"
            ),
            "phase7b6d_summary": _source(
                "outputs/phase7b6d_full_depth_contraction_summary.json"
            ),
            "phase7b6e_failed_summary": _source(
                "outputs/phase7b6e_extended_relaxation_summary.json"
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
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "process_count": 2,
            "source_map_count_exactly": 4,
            "first_map_forced_weight": 1.0,
            "later_candidate_weights": [1.8, 1.5, 1.2, 1.0],
            "whole_step_global_positivity_guard": True,
            "cellwise_clipping": False,
            "cell_deletion": False,
            "posthoc_renormalization": False,
            "state_storage": "two alternating float64 memmaps",
            "checkpoint_path": (
                "outputs/checkpoints/phase7b6f_full_frequency_iteration4.dat"
            ),
            "checkpoint_retained_for_authorized_continuation": True,
            "matter_feedback": False,
        },
        "reference": {
            "first_source_map_sha256": initial["full_frequency_output_sha256"],
            "first_raw_fixed_point_residual": initial["maximum_relative_change"],
            "state_size_bytes": initial["temporary_output_file_size_bytes"],
        },
        "gates": {
            "first_source_map_sha256_exactly": initial[
                "full_frequency_output_sha256"
            ],
            "each_iteration_block_count_exactly": 76,
            "each_iteration_unique_group_count_exactly": 9632,
            "source_map_count_exactly": 4,
            "all_raw_residuals_finite_and_strictly_decreasing": True,
            "final_to_first_raw_residual_strictly_below": 0.95,
            "minimum_intensity_at_least": 0.0,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_iteration_wall_time_strictly_below_s": 900.0,
            "checkpoint_size_bytes_exactly": initial[
                "temporary_output_file_size_bytes"
            ],
            "secondary_temporary_state_removed": True,
        },
        "authorization": {
            "bounded_full_frequency_contraction_pilot_authorized": True,
            "full_frequency_fixed_point_continuation_authorized_if_passes": True,
            "full_column_fixed_point_authorized": False,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6f_preregistered_full_frequency_contraction.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
