"""Phase 7B9as：冻结阻尼 Anderson 候选的全局审计与写入。"""

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


def _block_sha256(path: Path, start: int, stop: int) -> str:
    plane_bytes = 32 * 4096 * 8
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        stream.seek(start * plane_bytes)
        remaining = (stop - start) * plane_bytes
        while remaining:
            block = stream.read(min(16 * 1024 * 1024, remaining))
            if not block:
                raise RuntimeError("Phase 7B9as x2 ended inside a block")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


def main() -> None:
    coefficients = json.loads(
        (OUTPUT / "phase7b9ar_global_anderson_coefficients_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        coefficients["decision"]["global_anderson_coefficients_passed"] is not True
        or coefficients["decision"]["x4_storage_passed"] is not True
        or coefficients["decision"][
            "maximum_norm_and_positivity_candidate_audit_authorized"
        ]
        is not True
        or coefficients["decision"]["material_feedback_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9as requires the passed Anderson coefficients/x4")
    for label in ("x2", "x3", "x4"):
        if _sha256(ROOT / coefficients[f"{label}_state_path"]) != coefficients[
            f"{label}_state_sha256"
        ]:
            raise RuntimeError(f"Phase 7B9as {label} state changed")
    x2 = ROOT / coefficients["x2_state_path"]
    old_blocks = []
    for index in range(76):
        start = index * 128
        stop = min((index + 1) * 128, 9632)
        old_blocks.append(_block_sha256(x2, start, stop))
    payload = {
        "phase": "7B9as damped global Anderson candidate audit and write",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] blend the raw depth-two Anderson candidate toward x4 "
            "with eta in [0,1/64,1/32,1/16,1/8,1/4,1/2,3/4,1]; [V] one fresh "
            "F(x4) evaluates exact affine maximum-norm residual, boundary and positivity "
            "for every eta, followed by a recoverable write only if the selected "
            "candidate improves x4 by at least 20 percent; [O] a written candidate "
            "still requires a fresh global self audit"
        ),
        "sources": {
            "phase7b9ar_summary": _source(
                "outputs/phase7b9ar_global_anderson_coefficients_summary.json"
            ),
            "phase7b9ar_protocol": _source(
                "outputs/phase7b9ar_preregistered_global_anderson_coefficients.json"
            ),
            "x3_state": _source(str(coefficients["x3_state_path"])),
            "x4_state": _source(str(coefficients["x4_state_path"])),
            "finite_trial_protocol": _source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": _source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "affine_evaluator": _source(
                "scripts/phase7b9ak_global_convex_krylov_line.py"
            ),
            "phase7b7i_worker": _source(
                "scripts/phase7b7i_second_radiation_map.py"
            ),
            "phase7b9d_worker_helpers": _source(
                "scripts/phase7b9d_inner_converged_base_radiation.py"
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
            "anderson_alpha": coefficients["anderson_alpha"],
            "eta_grid": [0.0, 0.015625, 0.03125, 0.0625, 0.125, 0.25, 0.5, 0.75, 1.0],
            "x2_state_path": coefficients["x2_state_path"],
            "x2_state_sha256": coefficients["x2_state_sha256"],
            "x2_old_block_sha256": old_blocks,
            "x3_state_path": coefficients["x3_state_path"],
            "x3_state_sha256": coefficients["x3_state_sha256"],
            "x4_state_path": coefficients["x4_state_path"],
            "x4_state_sha256": coefficients["x4_state_sha256"],
            "candidate_output_path": coefficients["x2_state_path"],
            "raw_float64_checkpoint_size_bytes": x2.stat().st_size,
            "audit_report_directory": (
                "outputs/checkpoints/phase7b9as_damped_anderson/audit_reports"
            ),
            "manifest_path": (
                "outputs/checkpoints/phase7b9as_damped_anderson/manifest.json"
            ),
            "summary_path": (
                "outputs/phase7b9as_damped_anderson_candidate_summary.json"
            ),
            "figure_path": "outputs/phase7b9as_damped_anderson_candidate.png",
            "runner_path": (
                "scripts/phase7b9as_damped_anderson_candidate.py"
            ),
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback": False,
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "coefficient_sum_absolute_error_below": 1.0e-10,
            "minimum_candidate_and_mapped_intensity_at_least": 0.0,
            "selected_residual_ratio_to_x4_below": 0.80,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_worker_wall_time_strictly_below_s": 180.0,
            "audit_wall_time_strictly_below_s": 1200.0,
            "write_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "select_only_nonnegative_candidate": True,
            "write_selected_candidate_if_all_gates_pass": True,
            "fresh_global_self_audit_after_write": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9as_preregistered_damped_anderson_candidate.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
