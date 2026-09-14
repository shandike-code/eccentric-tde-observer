"""Phase 7B5z：冻结无重复末态诊断的单次源映射性能门。"""

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
    baseline = json.loads(
        (OUTPUT / "phase7b5x_full_depth_block_probe_summary.json").read_text()
    )["worker"]
    failed_batch = json.loads(
        (OUTPUT / "phase7b5y_remap_batch_performance_summary.json").read_text()
    )
    payload = {
        "phase": "7B5z lean single-source-map performance gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] diagnostics scheduling only; [V] exact map and "
            "resource comparison; [O] measured full-frequency source iteration"
        ),
        "sources": {
            "phase7b5x_summary": _source(
                "outputs/phase7b5x_full_depth_block_probe_summary.json"
            ),
            "phase7b5y_failed_summary": _source(
                "outputs/phase7b5y_remap_batch_performance_summary.json"
            ),
            "phase7b4r_material": _source(
                "outputs/phase7b4r_depth128_phase2048.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "mixed_frame_ale_baseline": _source(
                "src/eccentric_tde_observer/mixed_frame_ale.py"
            ),
            "mixed_frame_frequency": _source(
                "src/eccentric_tde_observer/mixed_frame_frequency.py"
            ),
            "mixed_frame_streaming": _source(
                "src/eccentric_tde_observer/mixed_frame_streaming.py"
            ),
            "multigroup_continuum": _source(
                "src/eccentric_tde_observer/multigroup_continuum.py"
            ),
        },
        "retained_failed_candidate": {
            "phase7b5y_gate_passed": failed_batch["decision"][
                "phase7b5y_gate_passed"
            ],
            "candidate_accepted": failed_batch["decision"]["candidate_accepted"],
            "median_operator_runtime_s": failed_batch["median_operator_runtime_s"],
        },
        "baseline": {
            "final_intensity_sha256": baseline["final_intensity_sha256"],
            "minimum_intensity": baseline["minimum_intensity"],
            "one_iteration_fixed_point_change": baseline[
                "one_iteration_fixed_point_change"
            ],
            "operator_runtime_s": baseline["operator_runtime_s"],
            "peak_process_rss_mib": baseline["peak_process_rss_mib"],
        },
        "candidate": {
            "map_equation_changed": False,
            "frequency_sum_order_changed": False,
            "spatial_sweep_changed": False,
            "skip_after_map_recomputed_comoving_diagnostics": True,
            "skip_after_map_recomputed_emissivity_diagnostics": True,
            "skip_after_map_residual_and_energy_ledger": True,
            "full_diagnostics_required_after_global_convergence": True,
            "repeat_count": 2,
        },
        "gates": {
            "each_final_intensity_sha256_exactly": baseline[
                "final_intensity_sha256"
            ],
            "each_minimum_intensity_relative_error_strictly_below": 2.0e-14,
            "each_fixed_point_change_relative_error_strictly_below": 2.0e-14,
            "median_operator_runtime_strictly_below_s": (
                0.80 * baseline["operator_runtime_s"]
            ),
            "each_peak_rss_strictly_below_mib": 6144.0,
            "each_diagnostics_finite": True,
        },
        "authorization": {
            "lean_source_map_source_change_authorized": True,
            "candidate_accepted_if_all_gates_pass": True,
            "streaming_integration_authorized_if_passes": True,
            "measured_full_frequency_source_iteration_authorized_if_passes": True,
            "full_column_fixed_point_authorized": False,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
        },
    }
    path = OUTPUT / "phase7b5z_preregistered_lean_source_map.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
