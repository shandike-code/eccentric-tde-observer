"""Phase 7B9aj：冻结主导能段 Krylov 候选的全局审计。"""

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
    candidate = json.loads(
        (OUTPUT / "phase7b9ai_dominant_band_krylov_candidate_summary.json").read_text(
            encoding="utf-8"
        )
    )
    prior = json.loads(
        (OUTPUT / "phase7b9af_second_picard_contraction_audit_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if candidate["decision"]["candidate_self_guard_residual_audit_authorized"] is not True:
        raise RuntimeError("Phase 7B9aj requires the passed Phase 7B9ai candidate")
    state_relative = str(candidate["candidate_state_path"])
    state = ROOT / state_relative
    if _sha256(state) != candidate["candidate_state_sha256"]:
        raise RuntimeError("Phase 7B9ai candidate state changed")
    payload = {
        "phase": "7B9aj dominant-band Krylov candidate global self-guard audit",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] evaluate the complete Phase 7B9ai candidate with one "
            "fresh original source map using the candidate itself for all neighboring "
            "frequency guards; [V] global residual, contraction, boundary, positivity "
            "and resource audit; [O] no material feedback unless the global 1e-4 gate passes"
        ),
        "sources": {
            "phase7b9ai_summary": _source(
                "outputs/phase7b9ai_dominant_band_krylov_candidate_summary.json"
            ),
            "phase7b9ai_protocol": _source(
                "outputs/phase7b9ai_preregistered_dominant_band_krylov_candidate.json"
            ),
            "phase7b9af_summary": _source(
                "outputs/phase7b9af_second_picard_contraction_audit_summary.json"
            ),
            "mapped_state": _source(state_relative),
            "finite_trial_protocol": _source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": _source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "generic_contraction_audit_runner": _source(
                "scripts/phase7b9ad_picard_contraction_audit.py"
            ),
            "phase7b9ab_audit_worker": _source(
                "scripts/phase7b9ab_global_trial_residual_audit.py"
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
            "spatial_scheme": "hybrid_step_turning_upwind",
            "maximum_concurrent_processes": 2,
            "input_state_path": state_relative,
            "input_state_sha256": candidate["candidate_state_sha256"],
            "report_directory": (
                "outputs/checkpoints/phase7b9aj_krylov_candidate_audit/reports"
            ),
            "summary_path": (
                "outputs/phase7b9aj_krylov_candidate_global_audit_summary.json"
            ),
            "figure_path": (
                "outputs/phase7b9aj_krylov_candidate_global_audit.png"
            ),
            "block_report_prefix": "phase7b9aj",
            "runner_path": "scripts/phase7b9aj_krylov_candidate_global_audit.py",
            "prior_map_summary_source_key": "phase7b9af_summary",
            "prior_global_residual_key": (
                "mapped_state_global_original_operator_residual"
            ),
            "prior_report_residual_key": (
                "block_relative_original_operator_residual"
            ),
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "minimum_intensity_at_least": 0.0,
            "global_original_operator_residual_below": 1.0e-4,
            "residual_contraction_ratio_below": 0.95,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_worker_wall_time_strictly_below_s": 30.0,
        },
        "authorization": {
            "material_feedback_only_if_global_residual_gate_passes": True,
            "accept_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9aj_preregistered_krylov_candidate_global_audit.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
