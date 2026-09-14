"""Phase 7B6r：冻结四逻辑工作进程、两并发的 I29 资源终局门。"""

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
    recheck = json.loads(
        (OUTPUT / "phase7b6q_resource_recheck_summary.json").read_text(
            encoding="utf-8"
        )
    )
    decision = recheck["decision"]
    for gate in (
        "repeat_map_count_and_group_coverage_passed",
        "formal_flux_bitwise_reproduction_passed",
        "formal_face_flux_spectrum_gate_passed",
        "formal_face_bolometric_gate_passed",
    ):
        if decision[gate] is not True:
            raise RuntimeError(f"Phase 7B6r requires the passed upstream gate: {gate}")
    if decision["repeat_resource_and_runtime_gates_passed"] is not False:
        raise RuntimeError("Phase 7B6r is only the declared worker-recycling branch")
    p_protocol = json.loads(
        (OUTPUT / "phase7b6p_preregistered_final_formal_flux.json").read_text(
            encoding="utf-8"
        )
    )
    payload = {
        "phase": "7B6r iteration-29 formal-flux worker-recycling gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] four logical workers in two sequential batches after two "
            "resource-only failures; [V] bitwise formal flux and per-process RSS; "
            "[O] matter feedback"
        ),
        "sources": {
            "phase7b6q_summary": _source(
                "outputs/phase7b6q_resource_recheck_summary.json"
            ),
            "phase7b6q_protocol": _source(
                "outputs/phase7b6q_preregistered_resource_recheck.json"
            ),
            "phase7b6q_runner": _source("scripts/phase7b6q_resource_recheck.py"),
            "phase7b6p_iteration29_worker1": _source(
                "outputs/phase7b6p_iteration29_worker1.json"
            ),
            "phase7b6p_iteration29_worker2": _source(
                "outputs/phase7b6p_iteration29_worker2.json"
            ),
            "phase7b6p_iteration30_worker1": _source(
                "outputs/phase7b6p_iteration30_worker1.json"
            ),
            "phase7b6p_iteration30_worker2": _source(
                "outputs/phase7b6p_iteration30_worker2.json"
            ),
            "phase7b6n_formal_worker": _source(
                "scripts/phase7b6n_formal_face_flux.py"
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
        },
        "retained_arrays": p_protocol["retained_arrays"],
        "configuration": {
            **p_protocol["configuration"],
            "process_count": 4,
            "maximum_concurrent_processes": 2,
            "worker_batches": [[0, 1], [2, 3]],
            "states": ["iteration29", "iteration30"],
            "rerun_states": ["iteration29"],
            "block_assignment": "block_index modulo four",
            "retained_iteration30_formal_reports": [
                "outputs/phase7b6p_iteration30_worker1.json",
                "outputs/phase7b6p_iteration30_worker2.json",
            ],
            "retained_iteration29_formal_reports": [
                "outputs/phase7b6p_iteration29_worker1.json",
                "outputs/phase7b6p_iteration29_worker2.json",
            ],
        },
        "gates": {
            "repeat_state_block_count_exactly": 76,
            "repeat_state_unique_group_count_exactly": 9632,
            "logical_worker_count_exactly": 4,
            "maximum_concurrent_processes_exactly": 2,
            "repeat_formal_flux_maximum_absolute_difference_exactly": 0.0,
            "formal_face_flux_spectrum_l1_below": 1.0e-3,
            "formal_face_bolometric_flux_fraction_below": 1.0e-3,
            "each_repeat_process_peak_rss_strictly_below_mib": 6144.0,
            "total_repeat_wall_time_strictly_below_s": 900.0,
            "retained_iteration30_resources_must_have_passed": True,
        },
        "authorization": {
            "fixed_material_science_functional_convergence_if_passes": True,
            "single_bounded_matter_feedback_pilot_if_passes": True,
            "further_resource_recheck_if_fails": False,
            "algebraic_fixed_point_at_1e-10": False,
            "full_orbit_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6r_preregistered_worker_recycling.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
