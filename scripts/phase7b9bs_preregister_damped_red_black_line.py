"""Phase 7B9bs：预注册完整红黑方向的全局阻尼线。"""

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
    base_audit = json.loads((OUTPUT / "phase7b9be_third_candidate_audit_summary.json").read_text(encoding="utf-8"))
    base_map = json.loads((OUTPUT / "phase7b9bf_candidate_affine_map_summary.json").read_text(encoding="utf-8"))
    cycle_audit = json.loads((OUTPUT / "phase7b9bq_red_black_cycle_audit_summary.json").read_text(encoding="utf-8"))
    cycle_map = json.loads((OUTPUT / "phase7b9br_red_black_cycle_map_summary.json").read_text(encoding="utf-8"))
    if base_audit["decision"]["continue_positive_iteration_authorized"] is not True or cycle_audit["decision"]["positive_picard_contraction_audit_passed"] is not False or cycle_map["decision"]["global_positive_picard_map_passed"] is not True:
        raise RuntimeError("Phase 7B9bs endpoint lineage is incompatible")
    paths = {
        "base_state": base_audit["input_state_path"],
        "base_map": base_map["output_state_path"],
        "cycle_state": cycle_audit["input_state_path"],
        "cycle_map": cycle_map["output_state_path"],
    }
    payload = {
        "phase": "7B9bs globally damped red-black line",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] fixed eta grid on the complete red-black correction "
            "and affine fixed-matter map prediction; [V] full-state maximum norm and "
            "positivity; [O] fresh original-operator audit remains mandatory"
        ),
        "sources": {
            "phase7b9be_summary": helper._source("outputs/phase7b9be_third_candidate_audit_summary.json"),
            "phase7b9bf_summary": helper._source("outputs/phase7b9bf_candidate_affine_map_summary.json"),
            "phase7b9bq_summary": helper._source("outputs/phase7b9bq_red_black_cycle_audit_summary.json"),
            "phase7b9br_summary": helper._source("outputs/phase7b9br_red_black_cycle_map_summary.json"),
            **{name: helper._source(path) for name, path in paths.items()},
        },
        "configuration": {
            "phase_index": 1392,
            "shape": [9632, 32, 4096],
            "frequency_chunk": 8,
            "base_state_path": paths["base_state"],
            "base_map_path": paths["base_map"],
            "cycle_state_path": paths["cycle_state"],
            "cycle_map_path": paths["cycle_map"],
            "candidate_output_path": paths["cycle_state"],
            "candidate_output_previous_sha256": cycle_audit["input_state_sha256"],
            "eta_grid_exact": [index / 128.0 for index in range(17)],
            "selection_rule": "minimum full-state modeled original-operator residual; ties choose smaller eta",
            "summary_path": "outputs/phase7b9bs_damped_red_black_line_summary.json",
            "figure_path": "outputs/phase7b9bs_damped_red_black_line.png",
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback": False,
        },
        "gates": {
            "minimum_candidate_and_modeled_map_intensity_at_least": 0.0,
            "selected_eta_strictly_above": 0.0,
            "modeled_residual_contraction_ratio_below": 0.8,
            "fixed_matter_convergence_target": 1.0e-4,
        },
        "authorization": {"write_only_if_all_modeled_gates_pass": True, "fresh_original_operator_audit_after_write": True, "material_feedback": False},
    }
    path = OUTPUT / "phase7b9bs_preregistered_damped_red_black_line.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
