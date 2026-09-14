"""Phase 7B9aq：冻结全局 Anderson 深度 2 所需的三连续态准备。"""

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
                raise RuntimeError("Phase 7B9aq buffer ended inside a block")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


def main() -> None:
    ap_summary = json.loads(
        (OUTPUT / "phase7b9ap_accelerated_positive_iteration_summary.json").read_text(
            encoding="utf-8"
        )
    )
    ap_manifest_relative = (
        "outputs/checkpoints/phase7b9ap_accelerated_positive/manifest.json"
    )
    ap_manifest = json.loads((ROOT / ap_manifest_relative).read_text(encoding="utf-8"))
    active = ap_manifest["active_stage"]
    if (
        ap_summary["status"] != "running"
        or len(ap_manifest["cycles"]) != 1
        or active["stage"] != "line"
        or active["cycle"] != 1
        or len(active["reports"]) != 0
    ):
        raise RuntimeError("Phase 7B9aq requires Phase 7B9ap paused after cycle-1 map")
    x1_relative = str(ap_manifest["current_state_path"])
    x2_relative = str(ap_manifest["scratch_state_path"])
    x1 = ROOT / x1_relative
    x2 = ROOT / x2_relative
    x1_sha = _sha256(x1)
    x2_sha = _sha256(x2)
    if (
        x1_sha != ap_manifest["current_state_sha256"]
        or x2_sha != active["scratch_state_sha256"]
    ):
        raise RuntimeError("Phase 7B9aq x1/x2 state changed")
    preserved_relative = (
        "outputs/checkpoints/phase7b9ab_global_trial/state_trial.dat"
    )
    preserved = ROOT / preserved_relative
    preserved_old_sha = _sha256(preserved)
    if preserved_old_sha != (
        "639173040883288fdf2341f1b6df1b662e20d1aa78cffcbe6aebb9f6472a976e"
    ):
        raise RuntimeError("Phase 7B9aq rejected trial reuse buffer changed")
    old_blocks = []
    for index in range(76):
        start = index * 128
        stop = min((index + 1) * 128, 9632)
        old_blocks.append(_block_sha256(preserved, start, stop))
    payload = {
        "phase": "7B9aq recoverable preparation of three global Anderson states",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] preserve x1 by overwriting only the rejected and "
            "reconstructible Phase 7B9ab trial buffer, then compute x3=F(x2) into "
            "the former x1 buffer; [V] block hashes, full hashes, positivity, boundary, "
            "ownership and resources; [O] no Anderson candidate is formed here"
        ),
        "sources": {
            "phase7b9ap_summary": _source(
                "outputs/phase7b9ap_accelerated_positive_iteration_summary.json"
            ),
            "phase7b9ap_manifest": _source(ap_manifest_relative),
            "x2_state": _source(x2_relative),
            "finite_trial_protocol": _source(
                "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
            ),
            "finite_trial_material": _source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
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
            "x1_source_path": x1_relative,
            "x1_source_sha256": x1_sha,
            "x1_preserved_path": preserved_relative,
            "x1_preserved_previous_sha256": preserved_old_sha,
            "x1_preserved_previous_block_sha256": old_blocks,
            "x2_state_path": x2_relative,
            "x2_state_sha256": x2_sha,
            "x3_output_path": x1_relative,
            "raw_float64_checkpoint_size_bytes": x1.stat().st_size,
            "manifest_path": (
                "outputs/checkpoints/phase7b9aq_anderson_triple/manifest.json"
            ),
            "report_directory": (
                "outputs/checkpoints/phase7b9aq_anderson_triple/reports"
            ),
            "summary_path": "outputs/phase7b9aq_anderson_triple_summary.json",
            "runner_path": "scripts/phase7b9aq_prepare_anderson_triple.py",
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback": False,
        },
        "reference": {
            "x1_global_residual": active["map_metrics"]["global_residual"],
            "x1_boundary_spectrum_l1": active["map_metrics"][
                "boundary_spectrum_l1"
            ],
            "x1_boundary_bolometric_fraction": active["map_metrics"][
                "boundary_bolometric_fraction"
            ],
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "minimum_intensity_at_least": 0.0,
            "global_boundary_spectrum_l1_below": 1.0e-3,
            "global_boundary_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_worker_wall_time_strictly_below_s": 30.0,
            "map_wall_time_strictly_below_s": 1200.0,
            "copy_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "reuse_rejected_trial_buffer": True,
            "prepare_three_state_anderson_basis": True,
            "form_anderson_candidate": False,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9aq_preregistered_anderson_triple.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
