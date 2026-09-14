"""Phase 7B9at：冻结正性约束 Anderson 候选及其验收门槛。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SHAPE = (9632, 32, 4096)


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
    plane_bytes = SHAPE[1] * SHAPE[2] * 8
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        stream.seek(start * plane_bytes)
        remaining = (stop - start) * plane_bytes
        while remaining:
            block = stream.read(min(16 * 1024 * 1024, remaining))
            if not block:
                raise RuntimeError("Phase 7B9at x2 ended inside a block")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


def main() -> None:
    source_summary = json.loads(
        (OUTPUT / "phase7b9ar_global_anderson_coefficients_summary.json").read_text(
            encoding="utf-8"
        )
    )
    failed_line = json.loads(
        (OUTPUT / "phase7b9as_damped_anderson_candidate_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        source_summary["decision"]["x4_storage_passed"] is not True
        or failed_line["decision"]["candidate_written"] is not False
        or failed_line["decision"]["material_feedback_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9at requires unchanged x2/x3/x4 inputs")
    for label in ("x2", "x3", "x4"):
        path = ROOT / source_summary[f"{label}_state_path"]
        if _sha256(path) != source_summary[f"{label}_state_sha256"]:
            raise RuntimeError(f"Phase 7B9at {label} state changed")
    x2 = ROOT / source_summary["x2_state_path"]
    old_blocks = [
        _block_sha256(x2, start, min(start + 128, SHAPE[0]))
        for start in range(0, SHAPE[0], 128)
    ]
    constrained = [
        1.0000000000000009,
        -17.778611152293248,
        17.778611152293248,
    ]
    payload = {
        "phase": "7B9at positivity-constrained global Anderson candidate",
        "protocol_version": 1,
        "classification": (
            "[A-informed] coefficients came from an exploratory cutting-plane "
            "positivity solve; [A-preregistered] the coefficient, maximum-norm "
            "improvement gate, positivity gate and boundary gates are frozen before "
            "the candidate operator audit; [V] one fresh F(x4) audits x4 and the "
            "affine candidate; [O] a written state still requires an independent map"
        ),
        "sources": {
            "phase7b9ar_summary": _source(
                "outputs/phase7b9ar_global_anderson_coefficients_summary.json"
            ),
            "phase7b9as_summary": _source(
                "outputs/phase7b9as_damped_anderson_candidate_summary.json"
            ),
            "x3_state": _source(source_summary["x3_state_path"]),
            "x4_state": _source(source_summary["x4_state_path"]),
            "finite_trial_protocol": _source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": _source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "candidate_engine": _source(
                "scripts/phase7b9as_damped_anderson_candidate.py"
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
            "phase_index": 1368,
            "physical_frequency_groups": SHAPE[0],
            "angular_direction_count": SHAPE[1],
            "radiation_depth_cell_count": SHAPE[2],
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "maximum_concurrent_processes": 2,
            "anderson_alpha": constrained,
            "eta_grid": [0.0, 1.0],
            "x2_state_path": source_summary["x2_state_path"],
            "x2_state_sha256": source_summary["x2_state_sha256"],
            "x2_old_block_sha256": old_blocks,
            "x3_state_path": source_summary["x3_state_path"],
            "x3_state_sha256": source_summary["x3_state_sha256"],
            "x4_state_path": source_summary["x4_state_path"],
            "x4_state_sha256": source_summary["x4_state_sha256"],
            "candidate_output_path": source_summary["x2_state_path"],
            "raw_float64_checkpoint_size_bytes": x2.stat().st_size,
            "audit_report_directory": (
                "outputs/checkpoints/phase7b9at_constrained_anderson/audit_reports"
            ),
            "manifest_path": (
                "outputs/checkpoints/phase7b9at_constrained_anderson/manifest.json"
            ),
            "summary_path": (
                "outputs/phase7b9at_constrained_anderson_candidate_summary.json"
            ),
            "figure_path": (
                "outputs/phase7b9at_constrained_anderson_candidate.png"
            ),
            "runner_path": (
                "scripts/phase7b9at_constrained_anderson_candidate.py"
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
            "owned_frequency_group_count_exactly": SHAPE[0],
            "coefficient_sum_absolute_error_below": 1.0e-12,
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
            "write_selected_candidate_if_all_gates_pass": True,
            "fresh_global_self_audit_after_write": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9at_preregistered_constrained_anderson_candidate.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
