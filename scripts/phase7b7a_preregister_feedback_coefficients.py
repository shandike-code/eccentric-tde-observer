"""Phase 7B7a：冻结收敛共动辐射场的物质反馈系数提取协议。"""

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


def _source(path: str) -> dict[str, str]:
    return {"path": path, "sha256": _sha256(ROOT / path)}


def main() -> None:
    upstream = json.loads(
        (OUTPUT / "phase7b6r_worker_recycling_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if upstream["decision"]["phase7b6r_gate_passed"] is not True:
        raise RuntimeError("Phase 7B7a requires the passed Phase 7B6r gate")
    if (
        upstream["decision"]["single_bounded_matter_feedback_pilot_authorized"]
        is not True
    ):
        raise RuntimeError("Phase 7B7a lacks upstream feedback-pilot authorization")
    retained_protocol = json.loads(
        (OUTPUT / "phase7b6r_preregistered_worker_recycling.json").read_text(
            encoding="utf-8"
        )
    )
    payload = {
        "phase": "7B7a converged comoving-radiation feedback coefficients",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] one fixed-material coefficient extraction from I30; "
            "[V] exact frequency ownership, frame/source consistency, symmetry and "
            "resources; [O] no matter update in this phase"
        ),
        "sources": {
            "phase7b6r_summary": _source(
                "outputs/phase7b6r_worker_recycling_summary.json"
            ),
            "phase7b6r_protocol": _source(
                "outputs/phase7b6r_preregistered_worker_recycling.json"
            ),
            "phase7b6r_runner": _source("scripts/phase7b6r_worker_recycling.py"),
            "phase7b6n_formal_worker": _source(
                "scripts/phase7b6n_formal_face_flux.py"
            ),
            "phase7b6f_runner": _source(
                "scripts/phase7b6f_full_frequency_contraction.py"
            ),
            "phase7b5x_context": _source(
                "scripts/phase7b5x_full_depth_block_probe.py"
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
            "mixed_frame_frequency": _source(
                "src/eccentric_tde_observer/mixed_frame_frequency.py"
            ),
            "mixed_frame_streaming": _source(
                "src/eccentric_tde_observer/mixed_frame_streaming.py"
            ),
            "multigroup_continuum": _source(
                "src/eccentric_tde_observer/multigroup_continuum.py"
            ),
            "continuum_emission": _source(
                "src/eccentric_tde_observer/continuum_emission.py"
            ),
        },
        "retained_arrays": retained_protocol["retained_arrays"],
        "configuration": {
            "state_label": "iteration30",
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "parent_depth_cell_count": 256,
            "half_depth_cell_count": 128,
            "radiation_subcells_per_parent": 16,
            "radiation_depth_cell_count": 4096,
            "logical_worker_count": 4,
            "maximum_concurrent_processes": 2,
            "worker_batches": [[0, 1], [2, 3]],
            "block_assignment": "block_index modulo four",
            "frequency_ownership": (
                "each block owns the exact contiguous global physical edges from "
                "core_group_start through core_group_stop"
            ),
            "mean_intensity_frame": "matter comoving frame",
            "rate_quadrature_order_per_group": 16,
            "parent_reduction": "arithmetic mean of sixteen equal-width subcells",
            "formal_material_heating": (
                "minus gamma times (summed lab radiation energy source minus beta c "
                "times summed lab radiation momentum source)"
            ),
            "matter_update": False,
            "cellwise_clipping": False,
            "intensity_or_rate_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "each_frequency_group_owned_exactly_once": True,
            "logical_worker_count_exactly": 4,
            "maximum_concurrent_processes_exactly": 2,
            "minimum_comoving_mean_intensity_at_least": 0.0,
            "rates_and_absorbed_emitted_power_nonnegative": True,
            "all_arrays_finite": True,
            "rate_heating_vs_inverse_four_force_volume_l1_below": 1.0e-3,
            "rate_heating_vs_inverse_four_force_global_fraction_below": 1.0e-3,
            "maximum_parent_mirror_residual_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "total_wall_time_strictly_below_s": 900.0,
        },
        "authorization": {
            "one_frozen_radiation_matter_update_if_passes": True,
            "repeat_coefficient_extraction_if_fails": False,
            "fully_coupled_iteration": False,
            "full_orbit": False,
            "phase4_replacement": False,
        },
    }
    path = OUTPUT / "phase7b7a_preregistered_feedback_coefficients.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
