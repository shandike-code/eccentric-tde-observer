"""Phase 7B9ay：冻结融合存储与正性约束的第二轮 Anderson。"""

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
                raise RuntimeError("Phase 7B9ay state ended inside a block")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


def main() -> None:
    first = json.loads(
        (OUTPUT / "phase7b9av_candidate_picard_map_summary.json").read_text(
            encoding="utf-8"
        )
    )
    second = json.loads(
        (OUTPUT / "phase7b9ax_second_candidate_picard_map_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        first["decision"]["global_positive_picard_map_passed"] is not True
        or second["decision"]["global_positive_picard_map_passed"] is not True
        or first["output_state_sha256"] != second["input_state_sha256"]
        or second["decision"]["material_feedback_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9ay requires three consecutive positive states")
    x1_relative = str(first["input_state_path"])
    x2_relative = str(first["output_state_path"])
    x3_relative = str(second["output_state_path"])
    expected = {
        x1_relative: first["input_state_sha256"],
        x2_relative: first["output_state_sha256"],
        x3_relative: second["output_state_sha256"],
    }
    for relative, digest in expected.items():
        if _sha256(ROOT / relative) != digest:
            raise RuntimeError(f"Phase 7B9ay state changed: {relative}")
    x1 = ROOT / x1_relative
    old_blocks = [
        _block_sha256(x1, start, min(start + 128, SHAPE[0]))
        for start in range(0, SHAPE[0], 128)
    ]
    payload = {
        "phase": "7B9ay fused second constrained depth-two Anderson",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] evaluate and store x4=F(x3) while accumulating the "
            "unweighted global residual Gram matrix for x1,x2,x3; solve the raw KKT "
            "system, then use at most ten normalized cutting-plane scans to minimize "
            "the same quadratic subject to pointwise nonnegative alpha1*x2+alpha2*x3"
            "+alpha3*x4 and sum(alpha)=1; [V] recoverable storage, positivity, boundary, "
            "ownership and resources; [O] mapped-candidate positivity and maximum-norm "
            "residual require a fresh stage"
        ),
        "sources": {
            "phase7b9av_summary": _source(
                "outputs/phase7b9av_candidate_picard_map_summary.json"
            ),
            "phase7b9ax_summary": _source(
                "outputs/phase7b9ax_second_candidate_picard_map_summary.json"
            ),
            "phase7b9ax_protocol": _source(
                "outputs/phase7b9ax_preregistered_second_candidate_picard_map.json"
            ),
            "x2_state": _source(x2_relative),
            "x3_state": _source(x3_relative),
            "finite_trial_protocol": _source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": _source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "anderson_engine": _source(
                "scripts/phase7b9ar_global_anderson_coefficients.py"
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
            "phase_index": 1373,
            "physical_frequency_groups": SHAPE[0],
            "angular_direction_count": SHAPE[1],
            "radiation_depth_cell_count": SHAPE[2],
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "maximum_concurrent_processes": 2,
            "x1_state_path": x1_relative,
            "x1_state_sha256": first["input_state_sha256"],
            "x1_old_block_sha256": old_blocks,
            "x2_state_path": x2_relative,
            "x2_state_sha256": first["output_state_sha256"],
            "x3_state_path": x3_relative,
            "x3_state_sha256": second["output_state_sha256"],
            "x4_output_path": x1_relative,
            "raw_float64_checkpoint_size_bytes": x1.stat().st_size,
            "report_directory": (
                "outputs/checkpoints/phase7b9ay_fused_anderson/reports"
            ),
            "manifest_path": (
                "outputs/checkpoints/phase7b9ay_fused_anderson/manifest.json"
            ),
            "summary_path": (
                "outputs/phase7b9ay_fused_constrained_anderson_summary.json"
            ),
            "runner_path": "scripts/phase7b9ay_fused_constrained_anderson.py",
            "maximum_cutting_plane_iterations": 10,
            "constraint_direction_duplicate_tolerance": 1.0e-12,
            "slsqp_function_tolerance": 1.0e-18,
            "slsqp_maximum_iterations": 2000,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "kkt_regularization": False,
            "matter_feedback": False,
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": SHAPE[0],
            "gram_condition_number_below": 1.0e12,
            "coefficient_sum_absolute_error_below": 1.0e-10,
            "minimum_x3_and_x4_intensity_at_least": 0.0,
            "final_negative_candidate_count_exactly": 0,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "worker_wall_time_strictly_below_s": 180.0,
            "map_wall_time_strictly_below_s": 1200.0,
            "constraint_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "overwrite_obsolete_x1_with_x4": True,
            "maximum_norm_and_mapped_positivity_candidate_audit_after_x4": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9ay_preregistered_fused_constrained_anderson.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
