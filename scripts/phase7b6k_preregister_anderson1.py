"""Phase 7B6k：冻结最坏全深度块的低存储 Anderson(1) 门。"""

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
        (OUTPUT / "phase7b6g_vector_aitken_summary.json").read_text(encoding="utf-8")
    )
    line = json.loads(
        (OUTPUT / "phase7b6j_positivity_line_search_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if local["decision"]["phase7b6g_gate_passed"] is not True:
        raise RuntimeError("Phase 7B6k requires the accepted full-depth Aitken gate")
    if line["decision"]["phase7b6j_gate_passed"] is not True:
        raise RuntimeError("Phase 7B6k requires the accepted global positivity line gate")
    payload = {
        "phase": "7B6k full-depth positivity-preserving Anderson(1) gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] unweighted depth-one Anderson residual mixing with "
            "a whole-state positivity line; [V] fixed-cost worst-block comparison; "
            "[O] full-frequency continuation"
        ),
        "sources": {
            "phase7b6g_summary": _source(
                "outputs/phase7b6g_vector_aitken_summary.json"
            ),
            "phase7b6j_summary": _source(
                "outputs/phase7b6j_positivity_line_search_summary.json"
            ),
            "phase7b6d_protocol": _source(
                "outputs/phase7b6d_preregistered_full_depth_contraction.json"
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
            "method": "phase7b6g vector Aitken",
            "source_map_count": local["source_map_count"],
            "final_raw_fixed_point_residual": local["final_raw_fixed_point_residual"],
            "first_source_map_sha256": local["first_source_map_sha256"],
        },
        "configuration": {
            "phase_index": local["phase_index"],
            "block_index": local["block_index"],
            "source_map_count_exactly": 16,
            "history_depth": 1,
            "residual_vector": "f_n = G(I_n) - I_n",
            "anderson_coefficient": (
                "gamma_n = <Delta f_(n-1), f_n> / ||Delta f_(n-1)||^2"
            ),
            "anderson_proposal": (
                "I_AA = G(I_n) - gamma_n [G(I_n)-G(I_(n-1))]"
            ),
            "inner_product": (
                "unweighted Euclidean over all local frequency, angle, and depth cells"
            ),
            "safe_base_weights": [1.8, 1.5, 1.2, 1.0],
            "safe_base_rule": "first entire finite nonnegative state in listed order",
            "positivity_line": (
                "I_next = I_base + alpha (I_AA-I_base); alpha=1 for a finite "
                "nonnegative proposal, otherwise the largest floating number strictly "
                "below min I_base/[-(I_AA-I_base)] over decreasing cells"
            ),
            "floating_predecessor": "numpy.nextafter(alpha_pos, 0.0)",
            "coefficient_clipping": False,
            "cellwise_clipping": False,
            "intensity_floor": False,
            "point_deletion": False,
            "stop_early": False,
            "matter_feedback": False,
        },
        "gates": {
            "first_source_map_sha256_exactly": local["first_source_map_sha256"],
            "source_map_count_exactly": 16,
            "minimum_intensity_at_least": 0.0,
            "all_residuals_coefficients_lines_and_diagnostics_finite": True,
            "anderson_or_line_step_count_at_least": 4,
            "final_raw_residual_strictly_below_vector_aitken_fraction": 0.5,
            "worker_peak_rss_strictly_below_mib": 6144.0,
            "worker_runtime_strictly_below_s": 900.0,
        },
        "authorization": {
            "full_depth_anderson_gate_authorized": True,
            "full_frequency_anderson_pilot_authorized_if_passes": True,
            "full_column_fixed_point_authorized": False,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6k_preregistered_anderson1.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
