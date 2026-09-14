"""Phase 7B9ab：冻结混合 trial 的全局原始算子和边界审计。"""

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
    return {"path": relative, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def main() -> None:
    repair = json.loads(
        (OUTPUT / "phase7b9aa_hybrid_candidate_repair_summary.json").read_text(
            encoding="utf-8"
        )
    )
    aa_protocol = json.loads(
        (OUTPUT / "phase7b9aa_preregistered_hybrid_candidate_repair.json").read_text(
            encoding="utf-8"
        )
    )
    finite = json.loads(
        (OUTPUT / "phase7b9i_preregistered_finite_trial_radiation.json").read_text(
            encoding="utf-8"
        )
    )
    checks = repair["gate_checks"]
    if (
        repair["decision"]["hybrid_candidate_repair_passed"] is not False
        or checks["repair_block_count_pass"] is not True
        or checks["seed_restarts_pass"] is not True
        or checks["positive_histories_and_candidates_pass"] is not True
        or checks["fresh_original_operator_residuals_pass"] is not True
        or checks["worker_resources_pass"] is not True
        or checks["boundaries_do_not_worsen"] is not False
    ):
        raise RuntimeError("Phase 7B9ab requires the isolated local-boundary failure")
    block67 = next(row for row in repair["repair_reports"] if row["block_index"] == 67)
    if block67["final_to_map6_raw_boundary_ratio"] <= 1.0:
        raise RuntimeError("Phase 7B9ab block-67 local boundary failure changed")
    sources = {
        "phase7b9aa_protocol": _source(
            "outputs/phase7b9aa_preregistered_hybrid_candidate_repair.json"
        ),
        "phase7b9aa_repair_summary": _source(
            "outputs/phase7b9aa_hybrid_candidate_repair_summary.json"
        ),
        "phase7b9z_roundoff_summary": _source(
            "outputs/phase7b9z_roundoff_affine_audit_summary.json"
        ),
        "phase7b9t_partial_candidate_state": _source(
            aa_protocol["sources"]["phase7b9t_partial_candidate_state"]["path"]
        ),
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
        "phase7b7i_worker": _source(
            "scripts/phase7b7i_second_radiation_map.py"
        ),
        "phase7b9r_worker_helpers": _source(
            "scripts/phase7b9r_full_source_krylov_line_search.py"
        ),
    }
    for row in repair["repair_reports"]:
        sources[f"repair_candidate_block{int(row['block_index']):02d}"] = _source(
            row["candidate_path"]
        )
    state_size = int(
        aa_protocol["configuration"]["raw_float64_checkpoint_size_bytes"]
    )
    global_target = float(finite["gates"]["global_source_map_residual_below"])
    payload = {
        "phase": "7B9ab candidate-self-guard global original-operator audit",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] assemble all validated repair block artifacts into a "
            "new uncommitted trial state, evaluate one fresh original source map for "
            "all 76 natural frequency blocks using trial-self neighbor guards, and "
            "judge the local block-67 boundary failure only through full-spectrum "
            "boundary integrals; [V] ownership, positivity, global residual, spectral "
            "and bolometric boundary audits; [O] confirmation map remains separate"
        ),
        "sources": sources,
        "configuration": {
            "phase_index": 1375,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "maximum_concurrent_processes": 2,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "trial_state_path": (
                "outputs/checkpoints/phase7b9ab_global_trial/state_trial.dat"
            ),
            "raw_float64_checkpoint_size_bytes": state_size,
            "minimum_free_bytes_before_trial_copy": state_size + 1024**3,
            "trial_state_is_uncommitted_before_global_gate": True,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "each_frequency_group_owned_exactly_once": True,
            "minimum_intensity_at_least": 0.0,
            "global_original_operator_residual_below": global_target,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 7168.0,
            "each_worker_wall_time_strictly_below_s": 120.0,
        },
        "authorization": {
            "promote_trial_to_committed_candidate_if_all_global_gates_pass": True,
            "override_local_block67_boundary_gate_only_if_global_gates_pass": True,
            "confirmation_source_map_if_promoted": True,
            "formal_trial_h_he_feedback": False,
            "trial_true_residual": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9ab_preregistered_global_trial_residual_audit.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
