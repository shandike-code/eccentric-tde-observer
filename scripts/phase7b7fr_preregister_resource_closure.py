"""Phase 7B7f-r：冻结全局拼接源项诊断的短寿命进程资源闭合。"""

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
    phase7b7f = json.loads(
        (OUTPUT / "phase7b7f_assembled_diagnostics_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if phase7b7f["decision"]["lagged_halo_diagnostic_timing_identified"] is not True:
        raise RuntimeError("Phase 7B7f-r requires identified diagnostic timing")
    if phase7b7f["decision"]["assembled_frame_source_consistency_passed"] is not True:
        raise RuntimeError("Phase 7B7f-r requires passed assembled science gate")
    if phase7b7f["decision"]["resource_and_runtime_gates_passed"] is not False:
        raise RuntimeError("Phase 7B7f-r requires the retained resource failure")
    payload = {
        "phase": "7B7f-r short-lived-process resource closure",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] rerun each assembled-state formal frequency block "
            "in one short-lived process; [V] bitwise scientific reproduction and "
            "per-process RSS; [O] no transport or matter update"
        ),
        "sources": {
            "phase7b7f_summary": _source(
                "outputs/phase7b7f_assembled_diagnostics_summary.json"
            ),
            "phase7b7f_protocol": _source(
                "outputs/phase7b7f_preregistered_assembled_diagnostics.json"
            ),
            "phase7b7f_reference": _source(
                "outputs/phase7b7f_assembled_diagnostics.npz"
            ),
            "phase7b7f_runner": _source(
                "scripts/phase7b7f_assembled_diagnostics.py"
            ),
            "phase7b7e_runner": _source(
                "scripts/phase7b7e_radiation_direction.py"
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
        "configuration": {
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "short_lived_process_count": 76,
            "blocks_per_process": 1,
            "maximum_concurrent_processes": 2,
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
            "maximum_absolute_reference_difference_exactly": 0.0,
            "assembled_rate_vs_direct_comoving_source_volume_l1_below": 1.0e-8,
            "assembled_rate_vs_inverse_four_force_volume_l1_below": 1.0e-3,
            "assembled_rate_vs_inverse_four_force_global_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "total_wall_time_strictly_below_s": 600.0,
        },
        "authorization": {
            "bounded_coupled_continuation_design_if_passes": True,
            "accept_as_radiation_or_coupled_fixed_point": False,
            "second_material_update": False,
            "full_orbit": False,
            "phase4_replacement": False,
        },
    }
    path = OUTPUT / "phase7b7fr_preregistered_resource_closure.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
