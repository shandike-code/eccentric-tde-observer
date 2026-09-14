"""Phase 7B9bm：预注册加入目标块方向的全局仿射 Krylov 组合。"""

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
SHAPE = (9632, 32, 4096)
CANDIDATE_OUTPUT = "outputs/checkpoints/phase7b6j_line_search_iteration14.dat"
MAPPED_OUTPUT = "outputs/checkpoints/phase7b6j_line_search_residual14.dat"


def main() -> None:
    fused = json.loads((OUTPUT / "phase7b9bc_third_fused_anderson_summary.json").read_text(encoding="utf-8"))
    accepted = json.loads((OUTPUT / "phase7b9be_third_candidate_audit_summary.json").read_text(encoding="utf-8"))
    accepted_map = json.loads((OUTPUT / "phase7b9bf_candidate_affine_map_summary.json").read_text(encoding="utf-8"))
    targeted = json.loads((OUTPUT / "phase7b9bj_targeted_candidate_audit_summary.json").read_text(encoding="utf-8"))
    targeted_map = json.loads((OUTPUT / "phase7b9bk_targeted_candidate_map_summary.json").read_text(encoding="utf-8"))
    if (
        accepted["decision"]["continue_positive_iteration_authorized"] is not True
        or accepted_map["decision"]["global_positive_picard_map_passed"] is not True
        or targeted["decision"]["positive_picard_contraction_audit_passed"] is not False
        or targeted_map["decision"]["global_positive_picard_map_passed"] is not True
    ):
        raise RuntimeError("Phase 7B9bm requires the three frozen affine pairs")
    basis = [
        {
            "label": "I11_to_I12",
            "state_path": fused["x3_state_path"],
            "state_sha256": fused["x3_state_sha256"],
            "mapped_path": fused["x4_state_path"],
            "mapped_sha256": fused["x4_state_sha256"],
        },
        {
            "label": "accepted_candidate_to_map",
            "state_path": accepted_map["input_state_path"],
            "state_sha256": accepted_map["input_state_sha256"],
            "mapped_path": accepted_map["output_state_path"],
            "mapped_sha256": accepted_map["output_state_sha256"],
        },
        {
            "label": "targeted_candidate_to_map",
            "state_path": targeted_map["input_state_path"],
            "state_sha256": targeted_map["input_state_sha256"],
            "mapped_path": targeted_map["output_state_path"],
            "mapped_sha256": targeted_map["output_state_sha256"],
        },
    ]
    for row in basis:
        if helper._sha256(ROOT / row["state_path"]) != row["state_sha256"] or helper._sha256(ROOT / row["mapped_path"]) != row["mapped_sha256"]:
            raise RuntimeError(f"Phase 7B9bm basis changed: {row['label']}")
    expected_size = (ROOT / basis[0]["state_path"]).stat().st_size
    candidate_output = ROOT / CANDIDATE_OUTPUT
    mapped_output = ROOT / MAPPED_OUTPUT
    if candidate_output.stat().st_size != expected_size or mapped_output.stat().st_size != expected_size:
        raise RuntimeError("Phase 7B9bm scratch output has the wrong size")
    payload = {
        "phase": "7B9bm augmented positive affine Krylov minimum residual",
        "protocol_version": 1,
        "classification": (
            "[A-informed] fixed-matter affine response over three complete state/map "
            "pairs; [A-preregistered] global unweighted L2 minimum with exact affine "
            "sum and pointwise positivity; [V] maximum-norm and boundary gates; "
            "[O] fresh original-operator audit remains mandatory"
        ),
        "sources": {
            "phase7b9bc_summary": helper._source("outputs/phase7b9bc_third_fused_anderson_summary.json"),
            "phase7b9be_summary": helper._source("outputs/phase7b9be_third_candidate_audit_summary.json"),
            "phase7b9bf_summary": helper._source("outputs/phase7b9bf_candidate_affine_map_summary.json"),
            "phase7b9bj_summary": helper._source("outputs/phase7b9bj_targeted_candidate_audit_summary.json"),
            "phase7b9bk_summary": helper._source("outputs/phase7b9bk_targeted_candidate_map_summary.json"),
            "i11_state": helper._source(basis[0]["state_path"]),
            "i12_state": helper._source(basis[0]["mapped_path"]),
            "accepted_state": helper._source(basis[1]["state_path"]),
            "accepted_map": helper._source(basis[1]["mapped_path"]),
            "targeted_state": helper._source(basis[2]["state_path"]),
            "targeted_map": helper._source(basis[2]["mapped_path"]),
            "phase7b5p_master_input": helper._source("outputs/phase7b5p_master_worker_input.npz"),
            "radiative_transfer_quadrature": helper._source("src/eccentric_tde_observer/radiative_transfer_1d.py"),
        },
        "configuration": {
            "phase_index": 1386,
            "physical_frequency_groups": SHAPE[0],
            "angular_direction_count": SHAPE[1],
            "radiation_depth_cell_count": SHAPE[2],
            "basis": basis,
            "scan_frequency_chunk": 32,
            "diagnostic_frequency_block": 128,
            "maximum_cutting_plane_iterations": 12,
            "constraint_direction_duplicate_tolerance": 1.0e-12,
            "slsqp_function_tolerance": 1.0e-18,
            "slsqp_maximum_iterations": 3000,
            "candidate_output_path": CANDIDATE_OUTPUT,
            "candidate_output_previous_sha256": helper._sha256(candidate_output),
            "mapped_candidate_output_path": MAPPED_OUTPUT,
            "mapped_output_previous_sha256": helper._sha256(mapped_output),
            "raw_float64_checkpoint_size_bytes": expected_size,
            "summary_path": "outputs/phase7b9bm_augmented_affine_krylov_summary.json",
            "figure_path": "outputs/phase7b9bm_augmented_affine_krylov.png",
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "kkt_regularization": False,
            "matter_feedback": False,
        },
        "gates": {
            "gram_condition_number_below": 1.0e12,
            "coefficient_sum_absolute_error_below": 1.0e-10,
            "candidate_residual_ratio_to_best_basis_below": 0.99,
            "global_original_operator_residual_below": 1.0e-4,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "write_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "overwrite_only_named_superseded_checkpoints": True,
            "write_candidate_and_exact_affine_map_only_if_all_gates_pass": True,
            "fresh_original_operator_self_audit_if_below_target": True,
            "sequential_block_update_if_gate_fails": True,
            "material_feedback": False,
        },
    }
    path = OUTPUT / "phase7b9bm_preregistered_augmented_affine_krylov.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
