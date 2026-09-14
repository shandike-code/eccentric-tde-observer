"""Phase 7B6l：冻结最坏全深度块的 Anderson(2) 最终局部门。"""

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
    baseline = json.loads(
        (OUTPUT / "phase7b6g_vector_aitken_summary.json").read_text(encoding="utf-8")
    )
    depth_one = json.loads(
        (OUTPUT / "phase7b6k_anderson1_summary.json").read_text(encoding="utf-8")
    )
    if baseline["decision"]["phase7b6g_gate_passed"] is not True:
        raise RuntimeError("Phase 7B6l requires the accepted vector-Aitken reference")
    if depth_one["decision"]["phase7b6k_gate_passed"] is not False:
        raise RuntimeError("Phase 7B6l is only the declared branch after depth-one failure")
    payload = {
        "phase": "7B6l full-depth positivity-preserving Anderson(2) final local gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] unweighted Anderson with at most two residual differences "
            "and a whole-state positivity line; [V] fixed-cost worst-block comparison; "
            "[O] no further Anderson depth tuning on this reference"
        ),
        "sources": {
            "phase7b6g_summary": _source(
                "outputs/phase7b6g_vector_aitken_summary.json"
            ),
            "phase7b6k_summary": _source(
                "outputs/phase7b6k_anderson1_summary.json"
            ),
            "phase7b6k_runner": _source("scripts/phase7b6k_anderson1.py"),
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
            "multigroup_continuum": _source(
                "src/eccentric_tde_observer/multigroup_continuum.py"
            ),
        },
        "reference": {
            "method": "phase7b6g vector Aitken",
            "source_map_count": baseline["source_map_count"],
            "final_raw_fixed_point_residual": baseline[
                "final_raw_fixed_point_residual"
            ],
            "first_source_map_sha256": baseline["first_source_map_sha256"],
        },
        "configuration": {
            "phase_index": baseline["phase_index"],
            "block_index": baseline["block_index"],
            "source_map_count_exactly": 16,
            "maximum_history_depth": 2,
            "history_rule": "use depth one at map 2 and depth two from map 3 onward",
            "least_squares": (
                "solve (Delta F)^T(Delta F) gamma = (Delta F)^T f_n "
                "with unweighted Euclidean inner products"
            ),
            "anderson_proposal": "I_AA = G(I_n) - Delta G gamma",
            "safe_base_weights": [1.8, 1.5, 1.2, 1.0],
            "positivity_line": "same exact whole-state scalar line as Phase 7B6k",
            "coefficient_clipping": False,
            "regularization": False,
            "cellwise_clipping": False,
            "intensity_floor": False,
            "point_deletion": False,
            "stop_early": False,
            "matter_feedback": False,
        },
        "gates": {
            "first_source_map_sha256_exactly": baseline["first_source_map_sha256"],
            "source_map_count_exactly": 16,
            "minimum_intensity_at_least": 0.0,
            "all_residuals_coefficients_lines_and_diagnostics_finite": True,
            "depth_two_step_count_at_least": 8,
            "final_raw_residual_strictly_below_vector_aitken_fraction": 0.5,
            "worker_peak_rss_strictly_below_mib": 6144.0,
            "worker_runtime_strictly_below_s": 900.0,
        },
        "authorization": {
            "full_depth_anderson2_gate_authorized": True,
            "full_frequency_anderson2_pilot_authorized_if_passes": True,
            "further_anderson_depth_tuning_authorized": False,
            "full_column_fixed_point_authorized": False,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6l_preregistered_anderson2.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
