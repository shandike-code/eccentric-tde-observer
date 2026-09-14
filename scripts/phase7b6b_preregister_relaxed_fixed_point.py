"""Phase 7B6b：冻结数值超松弛固定点候选门。"""

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
    previous = json.loads(
        (OUTPUT / "phase7b5w_translation_invariant_remap_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if previous["decision"]["phase7b5w_gate_passed"] is not True:
        raise RuntimeError("Phase 7B6b requires the accepted Phase 7B5w fixed point")
    reference = previous["runs"]["monolithic"]
    payload = {
        "phase": "7B6b pre-registered numerical over-relaxation gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] numerical relaxation weights; [V] raw fixed-point "
            "residual and retained-reference comparison; [O] full-depth contraction"
        ),
        "sources": {
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
            "mixed_frame_streaming": _source(
                "src/eccentric_tde_observer/mixed_frame_streaming.py"
            ),
        },
        "reference": {
            "physical_frequency_groups": 9632,
            "fixed_point_iterations": reference["fixed_point_iterations"],
            "fixed_point_tolerance": 1.0e-10,
            "final_intensity_sha256": reference["final_intensity_sha256"],
            "minimum_intensity": reference["minimum_intensity"],
        },
        "candidate": {
            "relaxation_weights": [1.0, 1.2, 1.5, 1.8],
            "update": "I_(n+1) = I_n + omega * (G(I_n) - I_n)",
            "convergence_measure": (
                "unrelaxed raw residual max|G(I)-I| / max(max|G(I)|, max|I|)"
            ),
            "maximum_iterations": 256,
            "source_map_only_during_iteration": True,
            "full_diagnostics_after_convergence": True,
            "invalid_candidate_policy": (
                "reject the entire weight on any non-finite or negative trial; "
                "never clip, floor, delete, or renormalize"
            ),
            "selection_rule": (
                "among eligible accelerated weights choose the fewest iterations; "
                "ties choose the smaller weight"
            ),
            "physical_equations_changed": False,
            "posthoc_tolerance_change": False,
        },
        "gates": {
            "baseline_final_hash_exactly": reference["final_intensity_sha256"],
            "all_converged_raw_residual_at_most": 1.0e-10,
            "all_audited_raw_residual_at_most": 1.0e-10,
            "all_final_intensity_maximum_relative_error_strictly_below": 1.0e-9,
            "all_final_spectrum_l1_relative_error_strictly_below": 1.0e-9,
            "all_final_scalar_relative_error_strictly_below": 1.0e-9,
            "minimum_intensity_at_least": 0.0,
            "at_least_two_adjacent_accelerated_weights_improve": True,
            "selected_iterations_at_most": 28,
            "each_worker_peak_rss_strictly_below_mib": 6144.0,
        },
        "authorization": {
            "one_cell_relaxation_gate_authorized": True,
            "short_full_depth_contraction_pilot_authorized_if_passes": True,
            "full_column_fixed_point_authorized": False,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6b_preregistered_relaxed_fixed_point.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
