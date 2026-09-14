"""Phase 7B9bn：预注册非相邻偶数目标块候选。"""

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
CANDIDATE = "outputs/checkpoints/phase7b6j_line_search_iteration14.dat"


def main() -> None:
    base = json.loads((OUTPUT / "phase7b9be_third_candidate_audit_summary.json").read_text(encoding="utf-8"))
    targeted = json.loads((OUTPUT / "phase7b9bi_targeted_full_source_krylov_summary.json").read_text(encoding="utf-8"))
    failed = json.loads((OUTPUT / "phase7b9bj_targeted_candidate_audit_summary.json").read_text(encoding="utf-8"))
    selected_all = [int(row["block_index"]) for row in targeted["reports"]]
    selected_even = [index for index in selected_all if index % 2 == 0]
    if (
        base["decision"]["continue_positive_iteration_authorized"] is not True
        or targeted["decision"]["fresh_global_original_operator_audit_authorized"] is not True
        or failed["decision"]["positive_picard_contraction_audit_passed"] is not False
        or selected_even != [20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 44, 46, 48]
    ):
        raise RuntimeError("Phase 7B9bn target-block lineage changed")
    candidate = ROOT / CANDIDATE
    payload = {
        "phase": "7B9bn nonadjacent even-block candidate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] red-black frequency block Gauss-Seidel, first update "
            "only nonadjacent even blocks using already gated local full-source Krylov "
            "cores; [V] byte ownership and positivity; [O] fresh global map required"
        ),
        "sources": {
            "phase7b9be_summary": helper._source("outputs/phase7b9be_third_candidate_audit_summary.json"),
            "phase7b9bi_summary": helper._source("outputs/phase7b9bi_targeted_full_source_krylov_summary.json"),
            "phase7b9bj_summary": helper._source("outputs/phase7b9bj_targeted_candidate_audit_summary.json"),
            "base_state": helper._source(base["input_state_path"]),
            "full_targeted_state": helper._source(targeted["candidate_state_path"]),
        },
        "configuration": {
            "phase_index": 1387,
            "shape": [9632, 32, 4096],
            "natural_frequency_block_size": 128,
            "selected_even_blocks": selected_even,
            "base_state_path": base["input_state_path"],
            "base_state_sha256": base["input_state_sha256"],
            "full_targeted_state_path": targeted["candidate_state_path"],
            "full_targeted_state_sha256": targeted["candidate_state_sha256"],
            "candidate_state_path": CANDIDATE,
            "candidate_state_previous_sha256": helper._sha256(candidate),
            "copy_frequency_chunk": 32,
            "summary_path": "outputs/phase7b9bn_even_block_candidate_summary.json",
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback": False,
        },
        "gates": {
            "minimum_candidate_intensity_at_least": 0.0,
            "selected_block_count_exactly": len(selected_even),
            "selected_blocks_pairwise_nonadjacent": True,
            "unselected_frequency_groups_bitwise_equal_base": True,
            "selected_frequency_groups_bitwise_equal_targeted": True,
        },
        "authorization": {
            "overwrite_only_named_superseded_checkpoint": True,
            "fresh_global_original_operator_map_if_constructor_passes": True,
            "material_feedback": False,
        },
    }
    path = OUTPUT / "phase7b9bn_preregistered_even_block_candidate.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
