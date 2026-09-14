"""Phase 7B9bl：预注册目标块候选的全局阻尼线。"""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from scripts import phase7b9av_preregister_candidate_picard_map as helper
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9av_preregister_candidate_picard_map as helper  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def main() -> None:
    base_audit = json.loads(
        (OUTPUT / "phase7b9be_third_candidate_audit_summary.json").read_text(
            encoding="utf-8"
        )
    )
    base_map = json.loads(
        (OUTPUT / "phase7b9bf_candidate_affine_map_summary.json").read_text(
            encoding="utf-8"
        )
    )
    trial_audit = json.loads(
        (OUTPUT / "phase7b9bj_targeted_candidate_audit_summary.json").read_text(
            encoding="utf-8"
        )
    )
    trial_map = json.loads(
        (OUTPUT / "phase7b9bk_targeted_candidate_map_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        base_audit["decision"]["continue_positive_iteration_authorized"] is not True
        or trial_audit["decision"]["positive_picard_contraction_audit_passed"] is not False
        or trial_map["decision"]["global_positive_picard_map_passed"] is not True
        or base_map["input_state_sha256"] != base_audit["input_state_sha256"]
        or trial_map["input_state_sha256"] != trial_audit["input_state_sha256"]
    ):
        raise RuntimeError("Phase 7B9bl endpoint lineage is incompatible")
    paths = {
        "base_state": str(base_audit["input_state_path"]),
        "base_map": str(base_map["output_state_path"]),
        "trial_state": str(trial_audit["input_state_path"]),
        "trial_map": str(trial_map["output_state_path"]),
    }
    payload = {
        "phase": "7B9bl preregistered global damped affine line",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] frozen convex eta grid and fixed-matter affine-map "
            "prediction; [V] full-state positivity and modeled original residual; "
            "[O] a fresh original-operator map remains mandatory"
        ),
        "sources": {
            "phase7b9be_summary": helper._source(
                "outputs/phase7b9be_third_candidate_audit_summary.json"
            ),
            "phase7b9bf_summary": helper._source(
                "outputs/phase7b9bf_candidate_affine_map_summary.json"
            ),
            "phase7b9bj_summary": helper._source(
                "outputs/phase7b9bj_targeted_candidate_audit_summary.json"
            ),
            "phase7b9bk_summary": helper._source(
                "outputs/phase7b9bk_targeted_candidate_map_summary.json"
            ),
            **{name: helper._source(path) for name, path in paths.items()},
        },
        "configuration": {
            "phase_index": 1385,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "frequency_chunk": 8,
            "base_state_path": paths["base_state"],
            "base_map_path": paths["base_map"],
            "trial_state_path": paths["trial_state"],
            "trial_map_path": paths["trial_map"],
            "candidate_output_path": paths["trial_state"],
            "candidate_output_previous_sha256": trial_audit["input_state_sha256"],
            "eta_grid_exact": [index / 64.0 for index in range(17)],
            "selection_rule": (
                "minimum full-state modeled global original-operator residual; "
                "ties choose the smaller eta"
            ),
            "affine_model": (
                "F[(1-eta)y+eta*z]=(1-eta)F[y]+eta*F[z] is a prediction "
                "only and requires a fresh-map audit"
            ),
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback": False,
            "summary_path": "outputs/phase7b9bl_global_damped_line_summary.json",
            "figure_path": "outputs/phase7b9bl_global_damped_line.png",
        },
        "gates": {
            "minimum_candidate_and_modeled_map_intensity_at_least": 0.0,
            "selected_eta_strictly_above": 0.0,
            "modeled_residual_contraction_ratio_below": 0.8,
            "fresh_original_operator_audit_required": True,
            "fixed_matter_convergence_target": 1.0e-4,
        },
        "authorization": {
            "overwrite_only_rejected_trial_state_with_selected_convex_candidate": True,
            "fresh_global_original_operator_audit_if_gates_pass": True,
            "material_feedback": False,
        },
    }
    path = OUTPUT / "phase7b9bl_preregistered_global_damped_line.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
