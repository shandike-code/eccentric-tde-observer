"""Phase 7B7e：冻结阻尼物质态上的一次全频辐射方向映射。"""

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
    damped = json.loads(
        (OUTPUT / "phase7b7d_trust_region_picard_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if damped["decision"]["phase7b7d_gate_passed"] is not True:
        raise RuntimeError("Phase 7B7e requires passed Phase 7B7d")
    if (
        damped["decision"]["one_full_duration_radiation_directional_map_authorized"]
        is not True
    ):
        raise RuntimeError("Phase 7B7e lacks radiation-direction authorization")
    upstream_protocol = json.loads(
        (OUTPUT / "phase7b7a_preregistered_feedback_coefficients.json").read_text(
            encoding="utf-8"
        )
    )
    payload = {
        "phase": "7B7e one full-frequency radiation directional map",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] one block-Jacobi radiation map at the damped matter "
            "state over the unchanged 889 s ALE step; [V] positivity, frame/source "
            "consistency and matter-residual direction; [O] not a radiation fixed point"
        ),
        "sources": {
            "phase7b7d_summary": _source(
                "outputs/phase7b7d_trust_region_picard_summary.json"
            ),
            "phase7b7d_protocol": _source(
                "outputs/phase7b7d_preregistered_trust_region_picard.json"
            ),
            "damped_material_state": _source(
                "outputs/phase7b7d_damped_material_state.npz"
            ),
            "phase7b7a_summary": _source(
                "outputs/phase7b7a_feedback_coefficients_summary.json"
            ),
            "old_feedback_coefficients": _source(
                "outputs/phase7b7a_feedback_coefficients.npz"
            ),
            "phase7b5x_context": _source(
                "scripts/phase7b5x_full_depth_block_probe.py"
            ),
            "phase7b6f_runner": _source(
                "scripts/phase7b6f_full_frequency_contraction.py"
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
        "retained_arrays": upstream_protocol["retained_arrays"],
        "configuration": {
            "phase_index": 1367,
            "physical_step_duration_changed": False,
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "parent_depth_cell_count": 256,
            "radiation_subcells_per_parent": 16,
            "radiation_depth_cell_count": 4096,
            "one_source_map_per_block": True,
            "short_lived_process_count": 76,
            "blocks_per_process": 1,
            "maximum_concurrent_processes": 2,
            "rate_quadrature_order_per_group": 16,
            "initial_radiation_state": "retained converged I30",
            "initial_ALE_storage_term": "unchanged original phase material Planck state",
            "collision_coefficients": "damped full-column material state",
            "density_and_geometry_changed": False,
            "cellwise_clipping": False,
            "floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "each_frequency_group_owned_exactly_once": True,
            "minimum_mapped_and_comoving_intensity_at_least": 0.0,
            "all_rates_and_arrays_finite": True,
            "rate_heating_vs_inverse_four_force_volume_l1_below": 1.0e-3,
            "rate_heating_vs_inverse_four_force_global_fraction_below": 1.0e-3,
            "one_map_raw_radiation_residual_below": 0.1,
            "matter_residual_volume_l1_contraction_fraction_below": 1.0,
            "limiting_cell_matter_residual_contraction_fraction_below": 1.0,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "total_wall_time_strictly_below_s": 900.0,
        },
        "authorization": {
            "bounded_radiation_continuation_design_if_passes": True,
            "accept_as_radiation_or_coupled_fixed_point": False,
            "second_material_update": False,
            "full_orbit": False,
            "phase4_replacement": False,
        },
    }
    path = OUTPUT / "phase7b7e_preregistered_radiation_direction.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
