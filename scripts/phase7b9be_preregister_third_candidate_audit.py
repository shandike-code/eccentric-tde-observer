"""Phase 7B9be：冻结第三轮 Anderson 写后态的独立全局审计。"""

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
    written = json.loads(
        (
            OUTPUT / "phase7b9bd_third_constrained_candidate_summary.json"
        ).read_text(encoding="utf-8")
    )
    if (
        written["decision"]["candidate_written"] is not True
        or written["decision"]["fresh_global_self_audit_authorized"] is not True
        or written["decision"]["material_feedback_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9be requires the passed written candidate")
    state_relative = str(written["candidate_state_path"])
    if _sha256(ROOT / state_relative) != written["candidate_state_sha256"]:
        raise RuntimeError("Phase 7B9bd written state changed")
    payload = {
        "phase": "7B9be third constrained Anderson candidate global self audit",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] apply one fresh original source map to the written "
            "third positivity-constrained Anderson state; [V] reproduce its predicted "
            "maximum-norm and boundary residuals and audit positivity; [O] fixed "
            "matter residual below 1e-4 remains required before feedback"
        ),
        "sources": {
            "phase7b9bd_summary": _source(
                "outputs/phase7b9bd_third_constrained_candidate_summary.json"
            ),
            "phase7b9bd_protocol": _source(
                "outputs/phase7b9bd_preregistered_third_constrained_candidate.json"
            ),
            "candidate_state": _source(state_relative),
            "finite_trial_protocol": _source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": _source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "generic_audit_runner": _source(
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
            "phase_index": 1378,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "maximum_concurrent_processes": 2,
            "input_state_path": state_relative,
            "input_state_sha256": written["candidate_state_sha256"],
            "report_directory": (
                "outputs/checkpoints/phase7b9be_third_candidate_audit/reports"
            ),
            "summary_path": (
                "outputs/phase7b9be_third_candidate_audit_summary.json"
            ),
            "figure_path": "outputs/phase7b9be_third_candidate_audit.png",
            "block_report_prefix": "phase7b9be",
            "runner_path": "scripts/phase7b9be_third_candidate_audit.py",
            "prior_map_summary_source_key": "phase7b9bd_summary",
            "prior_global_residual_key": (
                "predicted_global_original_operator_residual"
            ),
            "prior_report_residual_key": "block_relative_selected_prediction",
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
            "residual_contraction_ratio_below": 1.01,
            "prediction_reproduction_absolute_tolerance": 2.0e-12,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_worker_wall_time_strictly_below_s": 30.0,
        },
        "authorization": {
            "continue_from_candidate_if_reproduction_passes": True,
            "material_feedback_only_if_global_residual_gate_passes": True,
            "accept_dynamic_nlte_solution": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9be_preregistered_third_candidate_audit.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
