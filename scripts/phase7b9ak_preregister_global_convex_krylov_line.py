"""Phase 7B9ak：冻结稳定态与 Krylov 过冲态的全局凸线搜索。"""

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


def _source(relative: str) -> dict[str, object]:
    path = ROOT / relative
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def main() -> None:
    stable = json.loads(
        (OUTPUT / "phase7b9af_second_picard_contraction_audit_summary.json").read_text(
            encoding="utf-8"
        )
    )
    candidate = json.loads(
        (OUTPUT / "phase7b9ai_dominant_band_krylov_candidate_summary.json").read_text(
            encoding="utf-8"
        )
    )
    audit = json.loads(
        (OUTPUT / "phase7b9aj_krylov_candidate_global_audit_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        stable["decision"]["continue_positive_picard_maps_authorized"] is not True
        or candidate["decision"]["dominant_band_krylov_candidate_passed"] is not True
        or audit["decision"]["positive_picard_contraction_audit_passed"] is not False
        or audit["residual_contraction_ratio"] <= 1.0
    ):
        raise RuntimeError("Phase 7B9ak requires the stable state and audited Krylov overstep")
    stable_relative = str(stable["input_state_path"])
    candidate_relative = str(candidate["candidate_state_path"])
    if _sha256(ROOT / stable_relative) != stable["input_state_sha256"]:
        raise RuntimeError("Phase 7B9af stable state changed")
    if _sha256(ROOT / candidate_relative) != candidate["candidate_state_sha256"]:
        raise RuntimeError("Phase 7B9ai candidate state changed")
    theta = [index / 128.0 for index in range(65)] + [1.0]
    payload = {
        "phase": "7B9ak global convex Krylov line search",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] evaluate the fixed theta grid from 0 to 0.5 in "
            "increments of 1/128 plus theta=1 between the stable second-Picard state "
            "and the globally overstepped Krylov candidate; [V] exact affine residual "
            "combination at frozen matter, endpoint reproduction, positivity, boundary "
            "and resource gates; [O] a selected blend still requires a fresh global audit"
        ),
        "sources": {
            "phase7b9af_summary": _source(
                "outputs/phase7b9af_second_picard_contraction_audit_summary.json"
            ),
            "phase7b9ai_summary": _source(
                "outputs/phase7b9ai_dominant_band_krylov_candidate_summary.json"
            ),
            "phase7b9aj_summary": _source(
                "outputs/phase7b9aj_krylov_candidate_global_audit_summary.json"
            ),
            "stable_state": _source(stable_relative),
            "krylov_candidate_state": _source(candidate_relative),
            "finite_trial_protocol": _source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": _source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "mixed_frame_operator": _source(
                "src/eccentric_tde_observer/mixed_frame_ale.py"
            ),
            "mixed_frame_frequency": _source(
                "src/eccentric_tde_observer/mixed_frame_frequency.py"
            ),
        },
        "configuration": {
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "fresh_affine_blocks": list(range(12, 52)),
            "unchanged_blocks": list(range(0, 12)) + list(range(52, 76)),
            "theta_grid": theta,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "maximum_concurrent_processes": 2,
            "stable_state_path": stable_relative,
            "stable_state_sha256": stable["input_state_sha256"],
            "candidate_state_path": candidate_relative,
            "candidate_state_sha256": candidate["candidate_state_sha256"],
            "report_directory": (
                "outputs/checkpoints/phase7b9ak_global_convex_line/reports"
            ),
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "fresh_affine_block_count_exactly": 40,
            "unchanged_block_count_exactly": 36,
            "unchanged_endpoint_report_absolute_tolerance": 0.0,
            "minimum_stable_candidate_and_mapped_intensity_at_least": 0.0,
            "theta_zero_endpoint_absolute_tolerance": 2.0e-12,
            "theta_one_endpoint_absolute_tolerance": 2.0e-12,
            "selected_predicted_residual_ratio_below": 0.50,
            "selected_boundary_spectrum_l1_below": 1.0e-3,
            "selected_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_worker_wall_time_strictly_below_s": 60.0,
        },
        "authorization": {
            "write_selected_convex_blend_if_all_gates_pass": True,
            "fresh_global_audit_after_blend": True,
            "material_feedback": False,
            "accept_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9ak_preregistered_global_convex_krylov_line.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
