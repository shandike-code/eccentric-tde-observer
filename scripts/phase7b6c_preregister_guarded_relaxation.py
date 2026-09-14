"""Phase 7B6c：冻结整步拒绝的非负性保护超松弛门。"""

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
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _source(path: str) -> dict[str, str]:
    return {"path": path, "sha256": _sha256(ROOT / path)}


def main() -> None:
    failed = json.loads(
        (OUTPUT / "phase7b6b_relaxed_fixed_point_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if failed["decision"]["phase7b6b_gate_passed"] is not False:
        raise RuntimeError("Phase 7B6c requires the retained 7B6b failure")
    baseline = next(
        report for report in failed["runs"] if report["relaxation_weight"] == 1.0
    )
    if baseline["final_intensity_sha256"] != (
        "5b982f0cfda44b68bdabd371e008c586f5951aca4794fde4a7be81fbdbac383a"
    ):
        raise RuntimeError("Phase 7B6b baseline no longer reproduces the reference")
    payload = {
        "phase": "7B6c positivity-guarded whole-step relaxation gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] finite candidate policies and whole-step rejection; "
            "[V] raw residual, positivity and reference identity; "
            "[O] full-depth contraction"
        ),
        "sources": {
            "phase7b6b_failed_summary": _source(
                "outputs/phase7b6b_relaxed_fixed_point_summary.json"
            ),
            "phase7b6b_baseline": _source("outputs/phase7b6b_omega1p0.json"),
            "phase7b5w_summary": _source(
                "outputs/phase7b5w_translation_invariant_remap_summary.json"
            ),
            "phase7b5w_reference_state": _source(
                "outputs/phase7b5w_monolithic_state.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "mixed_frame_ale": _source(
                "src/eccentric_tde_observer/mixed_frame_ale.py"
            ),
            "mixed_frame_frequency": _source(
                "src/eccentric_tde_observer/mixed_frame_frequency.py"
            ),
        },
        "reference": {
            "baseline_iterations": baseline["fixed_point_iterations"],
            "fixed_point_tolerance": 1.0e-10,
            "final_intensity_sha256": baseline["final_intensity_sha256"],
        },
        "candidate": {
            "policies": {
                "guarded_1p2": [1.2, 1.0],
                "guarded_1p5": [1.5, 1.2, 1.0],
                "guarded_1p8": [1.8, 1.5, 1.2, 1.0],
            },
            "per_iteration_rule": (
                "compute G(I) once; test weights in listed descending order; "
                "accept the first entire trial that is finite and nonnegative"
            ),
            "fallback": "the unmodified G(I) whole step at omega=1.0",
            "cellwise_clipping": False,
            "cell_deletion": False,
            "posthoc_renormalization": False,
            "convergence_measure": "unrelaxed raw fixed-point residual",
            "maximum_iterations": 256,
            "full_diagnostics_after_convergence": True,
            "selection_rule": (
                "fewest iterations among eligible policies; ties choose lower "
                "maximum weight"
            ),
        },
        "gates": {
            "all_final_raw_residual_at_most": 1.0e-10,
            "all_audited_raw_residual_at_most": 1.0e-10,
            "all_final_intensity_maximum_relative_error_strictly_below": 1.0e-9,
            "all_final_spectrum_l1_relative_error_strictly_below": 1.0e-9,
            "all_final_scalar_relative_error_strictly_below": 1.0e-9,
            "minimum_intensity_at_least": 0.0,
            "at_least_two_policies_improve": True,
            "selected_iterations_at_most": 28,
            "each_policy_uses_accelerated_step_at_least_once": True,
            "each_worker_peak_rss_strictly_below_mib": 6144.0,
        },
        "authorization": {
            "guarded_relaxation_gate_authorized": True,
            "short_full_depth_contraction_pilot_authorized_if_passes": True,
            "full_column_fixed_point_authorized": False,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6c_preregistered_guarded_relaxation.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
