"""Phase 7B9ar：冻结全局 Anderson 深度 2 系数与 x4 存储协议。"""

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


def main() -> None:
    triple = json.loads(
        (OUTPUT / "phase7b9aq_anderson_triple_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        triple["decision"]["anderson_triple_preparation_passed"] is not True
        or triple["decision"]["global_anderson_depth_two_authorized"] is not True
        or triple["decision"]["material_feedback_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9ar requires the passed three-state basis")
    for label in ("x1", "x2", "x3"):
        path = ROOT / triple[f"{label}_state_path"]
        if _sha256(path) != triple[f"{label}_state_sha256"]:
            raise RuntimeError(f"Phase 7B9ar {label} state changed")
    payload = {
        "phase": "7B9ar global depth-two Anderson coefficients and x4 map",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] minimize the unweighted global L2 norm of alpha1*f1 "
            "+alpha2*f2+alpha3*f3 subject to sum(alpha)=1, where f1=x2-x1, "
            "f2=x3-x2 and f3=F(x3)-x3; [V] direct 4x4 KKT solve without "
            "regularization, condition-number gate, repeated x4=F(x3) storage, "
            "positivity, boundary, ownership and resources; [O] coefficients remain "
            "diagnostic until a maximum-norm candidate audit"
        ),
        "sources": {
            "phase7b9aq_summary": _source(
                "outputs/phase7b9aq_anderson_triple_summary.json"
            ),
            "phase7b9aq_protocol": _source(
                "outputs/phase7b9aq_preregistered_anderson_triple.json"
            ),
            "x2_state": _source(str(triple["x2_state_path"])),
            "x3_state": _source(str(triple["x3_state_path"])),
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
            "generic_positive_picard_runner": _source(
                "scripts/phase7b9ac_global_positive_picard_map.py"
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
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "maximum_concurrent_processes": 2,
            "x1_state_path": triple["x1_state_path"],
            "x1_state_sha256": triple["x1_state_sha256"],
            "x2_state_path": triple["x2_state_path"],
            "x2_state_sha256": triple["x2_state_sha256"],
            "x3_state_path": triple["x3_state_path"],
            "x3_state_sha256": triple["x3_state_sha256"],
            "x4_output_path": triple["x1_state_path"],
            "raw_float64_checkpoint_size_bytes": (
                ROOT / triple["x1_state_path"]
            ).stat().st_size,
            "coefficient_report_directory": (
                "outputs/checkpoints/phase7b9ar_anderson/coefficient_reports"
            ),
            "x4_report_directory": (
                "outputs/checkpoints/phase7b9ar_anderson/x4_reports"
            ),
            "coefficient_path": (
                "outputs/checkpoints/phase7b9ar_anderson/coefficients.json"
            ),
            "manifest_path": (
                "outputs/checkpoints/phase7b9ar_anderson/manifest.json"
            ),
            "summary_path": (
                "outputs/phase7b9ar_global_anderson_coefficients_summary.json"
            ),
            "runner_path": (
                "scripts/phase7b9ar_global_anderson_coefficients.py"
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
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "gram_condition_number_below": 1.0e12,
            "coefficient_sum_absolute_error_below": 1.0e-10,
            "minimum_x3_and_x4_intensity_at_least": 0.0,
            "x3_residual_reproduction_absolute_tolerance": 2.0e-12,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "coefficient_worker_wall_time_strictly_below_s": 60.0,
            "x4_worker_wall_time_strictly_below_s": 30.0,
            "each_stage_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "solve_unregularized_global_anderson_coefficients": True,
            "overwrite_obsolete_x1_with_x4_if_coefficient_gates_pass": True,
            "maximum_norm_and_positivity_candidate_audit_after_x4": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9ar_preregistered_global_anderson_coefficients.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
