"""Phase 7B7f：冻结拼接后全局辐射态的正式源项诊断。"""

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
    failed = json.loads(
        (OUTPUT / "phase7b7e_radiation_direction_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if failed["decision"]["phase7b7e_gate_passed"] is not False:
        raise RuntimeError("Phase 7B7f requires the retained Phase 7B7e failure")
    if failed["decision"]["frame_source_consistency_passed"] is not False:
        raise RuntimeError("Phase 7B7f requires the retained frame/source failure")
    block_partials = [
        _source(f"outputs/phase7b7e_block{index:02d}_partial.npz")
        for index in range(76)
    ]
    payload = {
        "phase": "7B7f assembled-state formal source diagnostics",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] read-only formal diagnostics on the globally "
            "assembled Phase 7B7e mapped state; [V] direct comoving source, "
            "Milne group rate and inverse lab four-force; [O] not another "
            "radiation or matter update"
        ),
        "sources": {
            "phase7b7e_summary": _source(
                "outputs/phase7b7e_radiation_direction_summary.json"
            ),
            "phase7b7e_protocol": _source(
                "outputs/phase7b7e_preregistered_radiation_direction.json"
            ),
            "phase7b7e_runner": _source(
                "scripts/phase7b7e_radiation_direction.py"
            ),
            "lagged_feedback_coefficients": _source(
                "outputs/phase7b7e_directional_feedback_coefficients.npz"
            ),
            "mapped_radiation_state": _source(
                "outputs/checkpoints/phase7b7e_damped_matter_radiation_map.dat"
            ),
            "damped_material_state": _source(
                "outputs/phase7b7d_damped_material_state.npz"
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
            "mixed_frame_frequency": _source(
                "src/eccentric_tde_observer/mixed_frame_frequency.py"
            ),
            "multigroup_continuum": _source(
                "src/eccentric_tde_observer/multigroup_continuum.py"
            ),
            "continuum_emission": _source(
                "src/eccentric_tde_observer/continuum_emission.py"
            ),
        },
        "block_partials": block_partials,
        "configuration": {
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "halo_state_for_formal_diagnostics": (
                "globally assembled Phase 7B7e mapped state"
            ),
            "transport_or_source_iteration": False,
            "matter_update": False,
            "geometry_or_duration_change": False,
            "cellwise_clipping": False,
            "floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "each_frequency_group_owned_exactly_once": True,
            "minimum_assembled_intensity_at_least": 0.0,
            "all_arrays_finite": True,
            "stored_lagged_volume_l1_reproduction_relative_error_below": 1.0e-12,
            "stored_lagged_global_reproduction_relative_error_below": 1.0e-12,
            "direct_comoving_source_vs_group_rate_volume_l1_below": 1.0e-8,
            "assembled_rate_vs_inverse_four_force_volume_l1_below": 1.0e-3,
            "assembled_rate_vs_inverse_four_force_global_fraction_below": 1.0e-3,
            "peak_rss_strictly_below_mib": 6144.0,
            "wall_time_strictly_below_s": 600.0,
        },
        "authorization": {
            "accept_as_radiation_or_coupled_fixed_point": False,
            "second_material_update": False,
            "bounded_coupled_continuation_design_if_passes": True,
            "full_orbit": False,
            "phase4_replacement": False,
        },
    }
    path = OUTPUT / "phase7b7f_preregistered_assembled_diagnostics.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
