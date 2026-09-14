"""Phase 7B6d：冻结最坏全深度块的短收缩试验。"""

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
    guarded = json.loads(
        (OUTPUT / "phase7b6c_guarded_relaxation_summary.json").read_text(
            encoding="utf-8"
        )
    )
    worst = json.loads(
        (OUTPUT / "phase7b5x_full_depth_block_probe_summary.json").read_text(
            encoding="utf-8"
        )
    )["worker"]
    if guarded["decision"]["phase7b6c_gate_passed"] is not True:
        raise RuntimeError("Phase 7B6d requires the accepted 7B6c guard")
    if guarded["selected_policy"] != "guarded_1p8":
        raise RuntimeError("Phase 7B6d requires the frozen guarded_1p8 policy")
    payload = {
        "phase": "7B6d full-depth worst-block contraction pilot",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] fixed 16-map local pilot; [V] full-depth raw "
            "residual and positivity; [O] full-frequency fixed point"
        ),
        "sources": {
            "phase7b6c_summary": _source(
                "outputs/phase7b6c_guarded_relaxation_summary.json"
            ),
            "phase7b5x_summary": _source(
                "outputs/phase7b5x_full_depth_block_probe_summary.json"
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
            "phase_index": worst["phase_index"],
            "block_index": worst["block_index"],
            "core_group_start": worst["core_group_start"],
            "core_group_stop": worst["core_group_stop"],
            "collision_group_count": worst["collision_group_count"],
            "outer_group_count": worst["outer_group_count"],
            "radiation_depth_cell_count": worst["radiation_depth_cell_count"],
            "turning_direction_count": worst["turning_direction_count"],
            "policies": {
                "jacobi": [1.0],
                "guarded_1p8": [1.8, 1.5, 1.2, 1.0],
            },
            "source_map_count_exactly": 16,
            "stop_early": False,
            "initial_state": "local boosted Planck field on frozen material state",
            "halo_state": "frozen local boosted Planck field",
            "spatial_scheme": "hybrid_step_turning_upwind",
            "source_map_only_during_pilot": True,
            "full_diagnostics_after_final_map": True,
            "matter_feedback": False,
        },
        "gates": {
            "first_map_intensity_sha256_exactly": worst["final_intensity_sha256"],
            "each_map_count_exactly": 16,
            "minimum_intensity_at_least": 0.0,
            "all_raw_residuals_finite": True,
            "guarded_accelerated_step_count_at_least": 1,
            "guarded_final_raw_residual_strictly_below_baseline_fraction": 0.8,
            "each_worker_peak_rss_strictly_below_mib": 6144.0,
            "each_worker_runtime_strictly_below_s": 900.0,
            "full_diagnostics_finite": True,
        },
        "authorization": {
            "full_depth_local_contraction_pilot_authorized": True,
            "bounded_full_frequency_convergence_pilot_authorized_if_passes": True,
            "full_column_fixed_point_authorized": False,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6d_preregistered_full_depth_contraction.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
