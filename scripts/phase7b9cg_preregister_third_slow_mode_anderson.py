"""Phase 7B9cg：冻结第三次 Anderson(1) 慢模外推。"""

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
CANDIDATE_OUTPUT = "outputs/checkpoints/phase7b6h_full_frequency_residual8.dat"


def main() -> None:
    sequence = json.loads(
        (OUTPUT / "phase7b9cf_third_accelerated_picard_summary.json").read_text(
            encoding="utf-8"
        )
    )
    anchor = json.loads(
        (OUTPUT / "phase7b9ce_second_map_anchor_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        sequence["status"] != "maximum_maps_exhausted"
        or sequence["completed_picard_maps"] != 3
        or len(sequence["iterations"]) != 3
        or not all(row["map_passed"] for row in sequence["iterations"])
    ):
        raise RuntimeError("Phase 7B9cg requires three audited accelerated records")
    row1 = sequence["iterations"][1]
    row2 = sequence["iterations"][2]
    basis = {
        "x9": {
            "path": anchor["anchor_state_path"],
            "sha256": anchor["anchor_state_sha256"],
        },
        "x10": {
            "path": row1["mapped_state_path"],
            "sha256": row1["mapped_state_sha256"],
        },
        "x11": {
            "path": row2["mapped_state_path"],
            "sha256": row2["mapped_state_sha256"],
        },
    }
    if (
        row1["input_state_sha256"] != basis["x9"]["sha256"]
        or row2["input_state_sha256"] != basis["x10"]["sha256"]
    ):
        raise RuntimeError("Phase 7B9cg states are not consecutive")
    for label, row in basis.items():
        if helper._sha256(ROOT / row["path"]) != row["sha256"]:
            raise RuntimeError(f"Phase 7B9cg {label} checkpoint changed")
    candidate = ROOT / CANDIDATE_OUTPUT
    expected_size = (ROOT / basis["x9"]["path"]).stat().st_size
    if candidate.stat().st_size != expected_size:
        raise RuntimeError("Phase 7B9cg candidate scratch size is invalid")
    payload = {
        "phase": "7B9cg third protected Anderson(1) slow-mode candidate",
        "protocol_version": 1,
        "classification": (
            "[A-informed] two fresh consecutive original-map residual vectors "
            "measure the post-second-jump slow mode; [A-preregistered] reuse the "
            "same global L2 minimum, exact positivity and 96-map horizon guards "
            "without threshold retuning; [V] require maximum-norm and boundary "
            "improvement; [O] one fresh complete operator map remains mandatory"
        ),
        "sources": {
            "phase7b9cf_summary": helper._source(
                "outputs/phase7b9cf_third_accelerated_picard_summary.json"
            ),
            "phase7b9cf_protocol": helper._source(
                "outputs/phase7b9cf_preregistered_third_accelerated_picard.json"
            ),
            "phase7b9ce_summary": helper._source(
                "outputs/phase7b9ce_second_map_anchor_summary.json"
            ),
            "phase7b9ce_protocol": helper._source(
                "outputs/phase7b9ce_preregistered_second_map_anchor.json"
            ),
            "x9_state": helper._source(basis["x9"]["path"]),
            "x10_state": helper._source(basis["x10"]["path"]),
            "x11_state": helper._source(basis["x11"]["path"]),
            "phase7b5p_master_input": helper._source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "slow_mode_runner": helper._source(
                "scripts/phase7b9bx_slow_mode_anderson.py"
            ),
            "radiative_transfer_quadrature": helper._source(
                "src/eccentric_tde_observer/radiative_transfer_1d.py"
            ),
        },
        "configuration": {
            "phase_index": 1408,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "x9_state_path": basis["x9"]["path"],
            "x9_state_sha256": basis["x9"]["sha256"],
            "x10_state_path": basis["x10"]["path"],
            "x10_state_sha256": basis["x10"]["sha256"],
            "x11_state_path": basis["x11"]["path"],
            "x11_state_sha256": basis["x11"]["sha256"],
            "x9_original_operator_residual": row1[
                "global_original_operator_residual"
            ],
            "x10_original_operator_residual": row2[
                "global_original_operator_residual"
            ],
            "scan_frequency_chunk": 16,
            "diagnostic_frequency_block": 128,
            "minimum_forward_picard_fraction": 1.0,
            "maximum_forward_picard_fraction": 96.0,
            "candidate_output_path": CANDIDATE_OUTPUT,
            "candidate_output_previous_sha256": helper._sha256(candidate),
            "raw_float64_checkpoint_size_bytes": expected_size,
            "summary_path": "outputs/phase7b9cg_third_slow_mode_anderson_summary.json",
            "figure_path": "outputs/phase7b9cg_third_slow_mode_anderson.png",
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "kkt_regularization": False,
            "matter_feedback": False,
        },
        "gates": {
            "difference_norm_squared_to_x9_residual_norm_squared_above": 1.0e-12,
            "selected_forward_picard_fraction_strictly_above": 1.0,
            "coefficient_l1_norm_strictly_below": 192.0,
            "predicted_global_residual_ratio_to_x10_below": 0.99,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "minimum_candidate_and_predicted_map_intensity_at_least": 0.0,
            "write_wall_time_strictly_below_s": 900.0,
        },
        "authorization": {
            "overwrite_only_named_superseded_checkpoint": True,
            "write_candidate_only_if_all_algebraic_gates_pass": True,
            "fresh_full_original_operator_map_required": True,
            "continue_accelerated_picard_if_candidate_fails": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9cg_preregistered_third_slow_mode_anderson.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
