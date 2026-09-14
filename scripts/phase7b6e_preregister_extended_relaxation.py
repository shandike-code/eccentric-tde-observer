"""Phase 7B6e：冻结最坏全深度块的扩展保护权重门。"""

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
    previous = json.loads(
        (OUTPUT / "phase7b6d_full_depth_contraction_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if previous["decision"]["phase7b6d_gate_passed"] is not True:
        raise RuntimeError("Phase 7B6e requires the accepted Phase 7B6d pilot")
    reference = previous["runs"]["guarded_1p8"]
    payload = {
        "phase": "7B6e extended full-depth guarded-relaxation gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] extended numerical weights; [V] fixed-cost "
            "full-depth contraction; [O] full-frequency fixed point"
        ),
        "sources": {
            "phase7b6d_summary": _source(
                "outputs/phase7b6d_full_depth_contraction_summary.json"
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
        "reference": {
            "policy": "guarded_1p8",
            "source_map_count": reference["source_map_count"],
            "final_raw_fixed_point_residual": reference[
                "final_raw_fixed_point_residual"
            ],
            "first_source_map_sha256": reference["first_source_map_sha256"],
        },
        "configuration": {
            "phase_index": reference["phase_index"],
            "block_index": reference["block_index"],
            "core_group_start": reference["core_group_start"],
            "core_group_stop": reference["core_group_stop"],
            "source_map_count_exactly": 16,
            "stop_early": False,
            "policies": {
                "guarded_2p0": [2.0, 1.8, 1.5, 1.2, 1.0],
                "guarded_2p2": [2.2, 2.0, 1.8, 1.5, 1.2, 1.0],
                "guarded_2p4": [2.4, 2.2, 2.0, 1.8, 1.5, 1.2, 1.0],
            },
            "whole_step_positivity_guard": True,
            "cellwise_clipping": False,
            "matter_feedback": False,
        },
        "gates": {
            "first_source_map_sha256_exactly": reference[
                "first_source_map_sha256"
            ],
            "each_map_count_exactly": 16,
            "minimum_intensity_at_least": 0.0,
            "all_residuals_and_full_diagnostics_finite": True,
            "each_policy_accelerated_step_count_at_least": 1,
            "at_least_two_policies_improve_over_1p8": True,
            "selected_final_residual_strictly_below_1p8_fraction": 0.8,
            "each_worker_peak_rss_strictly_below_mib": 6144.0,
            "each_worker_runtime_strictly_below_s": 900.0,
        },
        "authorization": {
            "extended_full_depth_weight_gate_authorized": True,
            "bounded_full_frequency_convergence_pilot_authorized_if_passes": True,
            "full_column_fixed_point_authorized": False,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6e_preregistered_extended_relaxation.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
