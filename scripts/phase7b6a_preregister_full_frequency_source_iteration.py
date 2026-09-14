"""Phase 7B6a：冻结完整 9632 组单次源迭代资源协议。"""

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
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _source(path: str) -> dict[str, str]:
    return {"path": path, "sha256": _sha256(ROOT / path)}


def main() -> None:
    payload = {
        "phase": "7B6a measured full-frequency single source iteration",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] two-process execution and temporary memmap; "
            "[V] all-block resource measurement; [O] converged full column"
        ),
        "sources": {
            "phase7b5z_summary": _source(
                "outputs/phase7b5z_lean_source_map_summary.json"
            ),
            "phase7b5y_failed_summary": _source(
                "outputs/phase7b5y_remap_batch_performance_summary.json"
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
            "assignment": "block_index modulo process_count",
            "source_iterations": 1,
            "source_map_only": True,
            "temporary_output_storage": "float64 memmap",
            "temporary_output_removed_after_hash": True,
            "initial_state": "local boosted Planck field on frozen material state",
            "matter_feedback": False,
        },
        "gates": {
            "completed_block_count_exactly": 76,
            "unique_core_group_count_exactly": 9632,
            "output_file_size_bytes_exactly": 10_099_884_032,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "total_wall_time_strictly_below_s": 900.0,
            "minimum_intensity_at_least": 0.0,
            "maximum_relative_change_finite": True,
            "all_block_diagnostics_finite": True,
            "temporary_output_removed": True,
            "frequency_edges_changed": False,
            "direction_deletion": False,
        },
        "authorization": {
            "full_frequency_source_iteration_authorized": True,
            "convergence_architecture_decision_authorized_if_passes": True,
            "full_column_fixed_point_authorized": False,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6a_preregistered_full_frequency_source_iteration.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
