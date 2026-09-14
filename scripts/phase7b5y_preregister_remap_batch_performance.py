"""Phase 7B5y：冻结频率搬移列批次性能门。"""

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
    payload = {
        "phase": "7B5y remap independent-column batch performance gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] performance-only candidate; [V] exact-output and "
            "isolated resource comparison; [O] full-column source iteration"
        ),
        "sources": {
            "phase7b5x_summary": _source(
                "outputs/phase7b5x_full_depth_block_probe_summary.json"
            ),
            "phase7b4r_material": _source(
                "outputs/phase7b4r_depth128_phase2048.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "mixed_frame_ale": _source(
                "src/eccentric_tde_observer/mixed_frame_ale.py"
            ),
            "mixed_frame_frequency_baseline": _source(
                "src/eccentric_tde_observer/mixed_frame_frequency.py"
            ),
            "mixed_frame_streaming": _source(
                "src/eccentric_tde_observer/mixed_frame_streaming.py"
            ),
            "multigroup_continuum": _source(
                "src/eccentric_tde_observer/multigroup_continuum.py"
            ),
        },
        "baseline": {
            "final_intensity_sha256": baseline["final_intensity_sha256"],
            "minimum_intensity": baseline["minimum_intensity"],
            "one_iteration_fixed_point_change": baseline[
                "one_iteration_fixed_point_change"
            ],
            "one_iteration_global_coupled_residual": baseline[
                "one_iteration_global_coupled_residual"
            ],
            "one_iteration_energy_ledger_residual": baseline[
                "one_iteration_energy_ledger_residual"
            ],
            "operator_runtime_s": baseline["operator_runtime_s"],
            "total_runtime_s": baseline["total_runtime_s"],
            "peak_process_rss_mib": baseline["peak_process_rss_mib"],
        },
        "candidate": {
            "old_independent_column_element_budget": 2_000_000,
            "new_independent_column_element_budget": 16_000_000,
            "frequency_sum_order_changed": False,
            "column_results_share_state": False,
            "physical_grid_changed": False,
            "repeat_count": 2,
        },
        "gates": {
            "each_final_intensity_sha256_exactly": baseline[
                "final_intensity_sha256"
            ],
            "each_scalar_relative_error_strictly_below": 2.0e-14,
            "median_operator_runtime_strictly_below_s": (
                0.95 * baseline["operator_runtime_s"]
            ),
            "each_peak_rss_strictly_below_mib": 6144.0,
            "each_minimum_intensity_at_least": 0.0,
            "each_diagnostics_finite": True,
        },
        "authorization": {
            "candidate_source_change_authorized": True,
            "candidate_accepted_if_all_gates_pass": True,
            "full_column_source_iteration_authorized": False,
            "full_column_fixed_point_authorized": False,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
        },
    }
    path = OUTPUT / "phase7b5y_preregistered_remap_batch_performance.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
