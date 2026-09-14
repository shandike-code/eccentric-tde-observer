"""Phase 7B9aa：冻结非破坏的混合全频率候选修复。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
REPAIR_BLOCKS = [62, *range(65, 76)]


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
    t_protocol = json.loads(
        (OUTPUT / "phase7b9t_preregistered_full_frequency_krylov_map.json").read_text(
            encoding="utf-8"
        )
    )
    t_manifest = json.loads(
        (OUTPUT / "checkpoints/phase7b9t_full_frequency_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    t_report62 = json.loads(
        (
            OUTPUT
            / "checkpoints/phase7b9i_work/reports_phase7b9t/phase7b9t_block62.json"
        ).read_text(encoding="utf-8")
    )
    positive = json.loads(
        (OUTPUT / "phase7b9v_positive_convex_picard_pilot_summary.json").read_text(
            encoding="utf-8"
        )
    )
    seeded = json.loads(
        (OUTPUT / "phase7b9y_krylov_seeded_picard_block62_pilot_summary.json").read_text(
            encoding="utf-8"
        )
    )
    roundoff = json.loads(
        (OUTPUT / "phase7b9z_roundoff_affine_audit_summary.json").read_text(
            encoding="utf-8"
        )
    )
    positive_by_block = {int(row["block_index"]): row for row in positive["reports"]}
    if (
        seeded["decision"]["krylov_seeded_positive_picard_block62_pilot_passed"]
        is not True
        or roundoff["decision"]["roundoff_resolution_audit_passed"] is not True
        or any(
            positive_by_block[index]["fresh_candidate_to_raw_residual_ratio"] >= 0.5
            for index in (65, 66, 73, 75)
        )
        or t_manifest["status"] != "running"
        or len(t_manifest["completed_blocks"]) != 73
    ):
        raise RuntimeError("Phase 7B9aa requires the completed hybrid pilot evidence")
    current_source = t_protocol["sources"]["current_map6_state"]
    current = ROOT / current_source["path"]
    partial = OUTPUT / "checkpoints/phase7b9i_work/state_a.dat"
    if (
        current.stat().st_size != int(current_source["size_bytes"])
        or _sha256(current) != current_source["sha256"]
    ):
        raise RuntimeError("Phase 7B9aa current map-6 state changed")
    rules = []
    for block_index in REPAIR_BLOCKS:
        if block_index == 62:
            rules.append(
                {
                    "block_index": block_index,
                    "role": "Krylov-seeded 32-update positive microcycle",
                    "seed_source_key": "phase7b9t_partial_candidate_state",
                    "positive_picard_update_count": 32,
                    "seed_original_operator_residual": t_report62[
                        "fresh_line_candidate_original_operator_residual"
                    ],
                    "map6_raw_original_operator_residual": t_report62[
                        "raw_original_operator_residual"
                    ],
                    "map6_raw_boundary_spectrum_l1": t_report62[
                        "raw_boundary_spectrum_l1"
                    ],
                }
            )
        else:
            rules.append(
                {
                    "block_index": block_index,
                    "role": "15-update positive high-energy Picard repair",
                    "seed_source_key": "current_map6_state",
                    "positive_picard_update_count": 15,
                    "seed_original_operator_residual": None,
                    "map6_raw_original_operator_residual": None,
                    "map6_raw_boundary_spectrum_l1": None,
                }
            )
    payload = {
        "phase": "7B9aa non-destructive hybrid full-frequency candidate repair",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] repair block 62 with the validated Krylov-seeded "
            "thirty-two-update positive microcycle and blocks 65--75 with fifteen "
            "positive map-6 Picard updates; compute independent block artifacts first, "
            "then copy the stopped candidate into a new full state only if every gate "
            "passes; [V] source hashes, fresh residual, boundary, positivity, ownership "
            "and final full-state hash; [O] next global residual remains separate"
        ),
        "sources": {
            "phase7b9t_protocol": _source(
                "outputs/phase7b9t_preregistered_full_frequency_krylov_map.json"
            ),
            "phase7b9t_stopped_manifest": _source(
                "outputs/checkpoints/phase7b9t_full_frequency_manifest.json"
            ),
            "phase7b9t_block62_report": _source(
                "outputs/checkpoints/phase7b9i_work/reports_phase7b9t/phase7b9t_block62.json"
            ),
            "phase7b9v_summary": _source(
                "outputs/phase7b9v_positive_convex_picard_pilot_summary.json"
            ),
            "phase7b9y_summary": _source(
                "outputs/phase7b9y_krylov_seeded_picard_block62_pilot_summary.json"
            ),
            "phase7b9z_summary": _source(
                "outputs/phase7b9z_roundoff_affine_audit_summary.json"
            ),
            "current_map6_state": _source(current_source["path"]),
            "phase7b9t_partial_candidate_state": _source(
                "outputs/checkpoints/phase7b9i_work/state_a.dat"
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
        },
        "configuration": {
            "phase_index": 1374,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "repair_blocks": rules,
            "maximum_concurrent_processes": 2,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "repaired_candidate_state_path": (
                "outputs/checkpoints/phase7b9aa_hybrid_repair/state_c.dat"
            ),
            "raw_float64_checkpoint_size_bytes": partial.stat().st_size,
            "minimum_free_bytes_before_full_copy": partial.stat().st_size
            + 2 * 1024**3,
            "source_partial_candidate_preserved": True,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "repair_block_count_exactly": len(REPAIR_BLOCKS),
            "each_seed_restart_relative_difference_below": 2.0e-12,
            "minimum_history_intensity_at_least": 0.0,
            "minimum_candidate_intensity_at_least": 0.0,
            "each_final_to_map6_raw_residual_ratio_below": 0.5,
            "each_final_to_map6_raw_boundary_ratio_at_most": 1.0,
            "each_process_peak_rss_strictly_below_mib": 7168.0,
            "each_worker_wall_time_strictly_below_s": 600.0,
        },
        "authorization": {
            "commit_new_full_candidate_if_all_gates_pass": True,
            "overwrite_map6_state": False,
            "overwrite_stopped_phase7b9t_candidate": False,
            "global_candidate_residual_if_committed": True,
            "formal_trial_h_he_feedback": False,
            "trial_true_residual": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9aa_preregistered_hybrid_candidate_repair.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
