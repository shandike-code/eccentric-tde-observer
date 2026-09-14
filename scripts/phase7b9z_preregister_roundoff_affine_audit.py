"""Phase 7B9z：冻结极小物理残差下的仿射相对指标审计。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SELECTED = [4, 9, 10, 52, 53, 54]


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
    manifest = json.loads(
        (OUTPUT / "checkpoints/phase7b9t_full_frequency_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    finite = json.loads(
        (OUTPUT / "phase7b9i_preregistered_finite_trial_radiation.json").read_text(
            encoding="utf-8"
        )
    )
    reports = {int(row["block_index"]): row for row in manifest["completed_blocks"]}
    failed_prediction = sorted(
        index
        for index, row in reports.items()
        if row["affine_prediction_to_fresh_residual_linf"] >= 2.0e-8
        and row["fresh_line_candidate_to_raw_residual_ratio"] < 0.5
        and row["fresh_line_candidate_to_raw_boundary_ratio"] <= 1.0
        and row["endpoint_exact_nonnegative_step"] >= 0.1
        and row["line_selected_fraction"] >= 0.02
    )
    if failed_prediction != SELECTED:
        raise RuntimeError("Phase 7B9z affine-only failure set changed")
    global_target = float(finite["gates"]["global_source_map_residual_below"])
    payload = {
        "phase": "7B9z roundoff-resolution audit for affine prediction diagnostics",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] retain an affine-diagnostic failure only when the "
            "fresh original-operator residual is below one-thousandth of the frozen "
            "global convergence target and the candidate improves by more than "
            "ten-thousand-fold; [V] positivity, boundary and direct residual audit; "
            "the original Phase 7B9t failure status is not rewritten"
        ),
        "sources": {
            "phase7b9t_protocol": _source(
                "outputs/phase7b9t_preregistered_full_frequency_krylov_map.json"
            ),
            "phase7b9t_stopped_manifest": _source(
                "outputs/checkpoints/phase7b9t_full_frequency_manifest.json"
            ),
            "finite_trial_protocol": _source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
        },
        "configuration": {
            "phase_index": 1373,
            "selected_blocks": SELECTED,
            "frozen_global_source_residual_target": global_target,
            "original_phase7b9t_status_preserved": True,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "selected_block_count_exactly": len(SELECTED),
            "fresh_original_operator_residual_below": 1.0e-3 * global_target,
            "fresh_candidate_to_raw_residual_ratio_below": 1.0e-4,
            "endpoint_exact_nonnegative_step_at_least": 0.99,
            "line_selected_fraction_at_least": 0.99,
            "fresh_candidate_boundary_ratio_at_most": 1.0,
            "minimum_line_candidate_intensity_at_least": 0.0,
        },
        "authorization": {
            "retain_selected_candidate_blocks_if_all_gates_pass": True,
            "rewrite_phase7b9t_as_passed": False,
            "global_candidate_residual": False,
            "formal_trial_h_he_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9z_preregistered_roundoff_affine_audit.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
