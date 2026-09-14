"""Phase 7B9bx：冻结最近两步 Picard 慢模 Anderson 外推。"""

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


def main() -> None:
    history = json.loads(
        (OUTPUT / "phase7b9bt_long_positive_picard_summary.json").read_text(
            encoding="utf-8"
        )
    )
    anchor = json.loads(
        (OUTPUT / "phase7b9bw_picard_anchor_summary.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (
            OUTPUT
            / "checkpoints/phase7b9bt_long_positive_picard/manifest.json"
        ).read_text(encoding="utf-8")
    )
    if (
        history["status"] != "running"
        or int(history["completed_picard_maps"]) != 11
        or len(history["iterations"]) != 11
        or manifest["status"] != "running"
        or manifest["active_iteration"] is not None
        or anchor["decision"]["phase7b9bt_resume_authorized"] is not True
        or anchor["decision"]["accelerated_candidate_constructed"] is not False
    ):
        raise RuntimeError("Phase 7B9bx requires the safely paused 11-map history")
    row9 = history["iterations"][9]
    row10 = history["iterations"][10]
    basis = {
        "x9": {
            "path": anchor["anchor_state_path"],
            "sha256": anchor["anchor_state_sha256"],
        },
        "x10": {
            "path": row9["mapped_state_path"],
            "sha256": row9["mapped_state_sha256"],
        },
        "x11": {
            "path": row10["mapped_state_path"],
            "sha256": row10["mapped_state_sha256"],
        },
    }
    if (
        row9["input_state_sha256"] != basis["x9"]["sha256"]
        or row10["input_state_sha256"] != basis["x10"]["sha256"]
        or manifest["current_input_sha256"] != basis["x11"]["sha256"]
    ):
        raise RuntimeError("Phase 7B9bx states are not three consecutive iterates")
    for label, row in basis.items():
        if helper._sha256(ROOT / row["path"]) != row["sha256"]:
            raise RuntimeError(f"Phase 7B9bx {label} checkpoint changed")
    expected_size = (ROOT / basis["x9"]["path"]).stat().st_size
    if any((ROOT / row["path"]).stat().st_size != expected_size for row in basis.values()):
        raise RuntimeError("Phase 7B9bx basis checkpoint sizes differ")
    candidate = ROOT / CANDIDATE_OUTPUT
    if candidate.stat().st_size != expected_size:
        raise RuntimeError("Phase 7B9bx candidate scratch size is invalid")
    payload = {
        "phase": "7B9bx protected Anderson(1) slow-mode candidate",
        "protocol_version": 1,
        "classification": (
            "[A-informed] the last two complete fixed-matter Picard residuals define "
            "one observed slow direction; [A-preregistered] minimize its unweighted "
            "global L2 residual on a forward affine line, bounded by exact candidate "
            "and mapped-state nonnegativity and the already authorized 96-map horizon; "
            "[V] require maximum-norm improvement and boundary gates; [O] only a fresh "
            "9632-group original-operator map may validate the candidate"
        ),
        "sources": {
            "phase7b9bt_summary": helper._source(
                "outputs/phase7b9bt_long_positive_picard_summary.json"
            ),
            "phase7b9bt_protocol": helper._source(
                "outputs/phase7b9bt_preregistered_long_positive_picard.json"
            ),
            "phase7b9bt_manifest": helper._source(
                "outputs/checkpoints/phase7b9bt_long_positive_picard/manifest.json"
            ),
            "phase7b9bw_summary": helper._source(
                "outputs/phase7b9bw_picard_anchor_summary.json"
            ),
            "phase7b9bw_protocol": helper._source(
                "outputs/phase7b9bw_preregistered_picard_anchor.json"
            ),
            "x9_state": helper._source(basis["x9"]["path"]),
            "x10_state": helper._source(basis["x10"]["path"]),
            "x11_state": helper._source(basis["x11"]["path"]),
            "phase7b5p_master_input": helper._source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "radiative_transfer_quadrature": helper._source(
                "src/eccentric_tde_observer/radiative_transfer_1d.py"
            ),
        },
        "configuration": {
            "phase_index": 1399,
            "physical_frequency_groups": SHAPE[0],
            "angular_direction_count": SHAPE[1],
            "radiation_depth_cell_count": SHAPE[2],
            "x9_state_path": basis["x9"]["path"],
            "x9_state_sha256": basis["x9"]["sha256"],
            "x10_state_path": basis["x10"]["path"],
            "x10_state_sha256": basis["x10"]["sha256"],
            "x11_state_path": basis["x11"]["path"],
            "x11_state_sha256": basis["x11"]["sha256"],
            "x9_original_operator_residual": row9[
                "global_original_operator_residual"
            ],
            "x10_original_operator_residual": row10[
                "global_original_operator_residual"
            ],
            "scan_frequency_chunk": 16,
            "diagnostic_frequency_block": 128,
            "minimum_forward_picard_fraction": 1.0,
            "maximum_forward_picard_fraction": 96.0,
            "candidate_output_path": CANDIDATE_OUTPUT,
            "candidate_output_previous_sha256": helper._sha256(candidate),
            "raw_float64_checkpoint_size_bytes": expected_size,
            "summary_path": "outputs/phase7b9bx_slow_mode_anderson_summary.json",
            "figure_path": "outputs/phase7b9bx_slow_mode_anderson.png",
            "scratch_reuse_note": (
                "Only the named superseded Phase 7B6j iteration-14 generated "
                "checkpoint may be overwritten; x9, x10 and x11 remain immutable"
            ),
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
            "resume_phase7b9bt_if_candidate_fails": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9bx_preregistered_slow_mode_anderson.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
