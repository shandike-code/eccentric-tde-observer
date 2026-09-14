"""Phase 7B8b：冻结受保护割线物质提案上的全频辐射验证映射。"""

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
    proposal = json.loads(
        (OUTPUT / "phase7b8a_protected_secant_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if proposal["decision"]["phase7b8a_gate_passed"] is not True:
        raise RuntimeError("Phase 7B8b requires passed Phase 7B8a")
    if (
        proposal["decision"]["one_full_frequency_radiation_validation_map_authorized"]
        is not True
    ):
        raise RuntimeError("Phase 7B8b lacks radiation validation authorization")
    payload = {
        "phase": "7B8b secant-trial full-frequency radiation validation map",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] one block-Jacobi radiation map at the protected "
            "diagonal-secant material trial; [V] exact ownership, positivity and "
            "resources; [O] assembled physical feedback deferred to Phase 7B8c"
        ),
        "sources": {
            "phase7b8a_summary": _source(
                "outputs/phase7b8a_protected_secant_summary.json"
            ),
            "phase7b8a_protocol": _source(
                "outputs/phase7b8a_preregistered_protected_secant.json"
            ),
            "phase7b8a_runner": _source("scripts/phase7b8a_protected_secant.py"),
            "accelerated_material_trial": _source(
                "outputs/phase7b8a_protected_secant_material_trial.npz"
            ),
            "initial_radiation_state": _source(
                "outputs/checkpoints/phase7b7i_second_radiation_map.dat"
            ),
            "phase7b7i_summary": _source(
                "outputs/phase7b7i_second_radiation_map_summary.json"
            ),
            "phase7b7i_runner": _source(
                "scripts/phase7b7i_second_radiation_map.py"
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
        "configuration": {
            "phase_index": 1367,
            "physical_step_duration_s": 889.419892762322,
            "physical_step_duration_changed": False,
            "physical_step_accumulated_again": False,
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
            "initial_radiation_state": "globally assembled Phase 7B7i mapped state",
            "initial_ALE_storage_term": (
                "unchanged original physical-time-level material Planck state"
            ),
            "collision_coefficients": "Phase 7B8a protected secant material trial",
            "assembled_formal_source_or_atomic_rates": False,
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
            "minimum_mapped_intensity_at_least": 0.0,
            "all_reported_values_finite": True,
            "one_map_raw_radiation_residual_below": 0.1,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "total_wall_time_strictly_below_s": 900.0,
        },
        "authorization": {
            "assembled_feedback_and_true_residual_diagnosis_if_passes": True,
            "accept_as_radiation_or_coupled_fixed_point": False,
            "another_material_update": False,
            "full_orbit": False,
            "phase4_replacement": False,
        },
    }
    path = OUTPUT / "phase7b8b_preregistered_secant_radiation_map.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
