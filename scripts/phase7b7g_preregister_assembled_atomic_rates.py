"""Phase 7B7g：冻结全局拼接辐射态上的 H/He 原子率提取。"""

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
    closure = json.loads(
        (OUTPUT / "phase7b7fr_resource_closure_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if closure["decision"]["phase7b7fr_gate_passed"] is not True:
        raise RuntimeError("Phase 7B7g requires passed Phase 7B7f-r")
    if (
        closure["decision"]["bounded_coupled_continuation_design_authorized"]
        is not True
    ):
        raise RuntimeError("Phase 7B7g lacks bounded-continuation authorization")
    payload = {
        "phase": "7B7g assembled-state H/He atomic rates",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] read-only H/He ground-state rates from the globally "
            "assembled Phase 7B7e radiation state; [V] unique frequency ownership, "
            "heating identity, mirror symmetry and resources; [O] no material update"
        ),
        "sources": {
            "phase7b7fr_summary": _source(
                "outputs/phase7b7fr_resource_closure_summary.json"
            ),
            "phase7b7fr_protocol": _source(
                "outputs/phase7b7fr_preregistered_resource_closure.json"
            ),
            "assembled_heating_reference": _source(
                "outputs/phase7b7f_assembled_diagnostics.npz"
            ),
            "mapped_radiation_state": _source(
                "outputs/checkpoints/phase7b7e_damped_matter_radiation_map.dat"
            ),
            "damped_material_state": _source(
                "outputs/phase7b7d_damped_material_state.npz"
            ),
            "phase7b7e_runner": _source(
                "scripts/phase7b7e_radiation_direction.py"
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
        "configuration": {
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "rate_quadrature_order_per_group": 16,
            "short_lived_process_count": 76,
            "blocks_per_process": 1,
            "maximum_concurrent_processes": 2,
            "halo_state": "globally assembled mapped radiation state",
            "transport_or_source_iteration": False,
            "matter_update": False,
            "cellwise_clipping": False,
            "floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "minimum_comoving_mean_intensity_at_least": 0.0,
            "all_rates_and_arrays_finite": True,
            "all_atomic_rates_at_least": 0.0,
            "heating_reference_volume_l1_below": 1.0e-10,
            "maximum_parent_mirror_residual_below": 1.0e-8,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "total_wall_time_strictly_below_s": 600.0,
        },
        "authorization": {
            "one_second_physical_time_level_picard_direction_if_passes": True,
            "material_update": False,
            "radiation_update": False,
            "full_orbit": False,
            "phase4_replacement": False,
        },
    }
    path = OUTPUT / "phase7b7g_preregistered_assembled_atomic_rates.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
