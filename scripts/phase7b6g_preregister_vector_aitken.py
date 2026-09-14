"""Phase 7B6g：冻结最坏全深度块的向量 Aitken 松弛门。"""

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
    local = json.loads(
        (OUTPUT / "phase7b6d_full_depth_contraction_summary.json").read_text(
            encoding="utf-8"
        )
    )
    global_pilot = json.loads(
        (OUTPUT / "phase7b6f_full_frequency_contraction_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if local["decision"]["phase7b6d_gate_passed"] is not True:
        raise RuntimeError("Phase 7B6g requires the accepted 1.8 local pilot")
    if global_pilot["decision"]["phase7b6f_gate_passed"] is not True:
        raise RuntimeError("Phase 7B6g requires the accepted full-frequency pilot")
    reference = local["runs"]["guarded_1p8"]
    payload = {
        "phase": "7B6g full-depth vector-Aitken relaxation gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] Euclidean vector Aitken and guarded fallback; "
            "[V] fixed-cost full-depth contraction; [O] full-frequency Aitken"
        ),
        "sources": {
            "phase7b6d_summary": _source(
                "outputs/phase7b6d_full_depth_contraction_summary.json"
            ),
            "phase7b6f_summary": _source(
                "outputs/phase7b6f_full_frequency_contraction_summary.json"
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
            "source_map_count_exactly": 16,
            "first_weight": 1.0,
            "aitken_formula": (
                "omega_n = -omega_(n-1) <r_(n-1), r_n-r_(n-1)> "
                "/ ||r_n-r_(n-1)||^2"
            ),
            "residual_vector": "r_n = G(I_n) - I_n",
            "inner_product": "unweighted Euclidean over all local (frequency, mu, depth) cells",
            "aitken_trial_acceptance": (
                "finite positive omega and entire trial intensity finite and nonnegative"
            ),
            "fallback_weights": [1.8, 1.5, 1.2, 1.0],
            "fallback_rule": "first entire finite nonnegative trial in listed order",
            "weight_clipping": False,
            "cellwise_clipping": False,
            "stop_early": False,
            "matter_feedback": False,
        },
        "gates": {
            "first_source_map_sha256_exactly": reference[
                "first_source_map_sha256"
            ],
            "source_map_count_exactly": 16,
            "minimum_intensity_at_least": 0.0,
            "all_residuals_weights_and_diagnostics_finite": True,
            "aitken_step_count_at_least": 2,
            "final_raw_residual_strictly_below_1p8_fraction": 0.5,
            "worker_peak_rss_strictly_below_mib": 6144.0,
            "worker_runtime_strictly_below_s": 900.0,
        },
        "authorization": {
            "local_vector_aitken_gate_authorized": True,
            "full_frequency_aitken_pilot_authorized_if_passes": True,
            "full_column_fixed_point_authorized": False,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6g_preregistered_vector_aitken.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
