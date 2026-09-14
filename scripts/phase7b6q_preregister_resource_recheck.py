"""Phase 7B6q：冻结一次 I29 正式面通量资源复验。"""

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
    formal = json.loads(
        (OUTPUT / "phase7b6p_final_formal_flux_summary.json").read_text(
            encoding="utf-8"
        )
    )
    decision = formal["decision"]
    required_true = (
        "frozen_protocol_and_source_hashes_passed",
        "retained_array_hashes_and_sizes_passed",
        "map_count_and_group_coverage_passed",
        "mapped_states_and_diagnostics_valid",
        "formal_face_flux_spectrum_gate_passed",
        "formal_face_bolometric_gate_passed",
    )
    if not all(decision[name] is True for name in required_true):
        raise RuntimeError("Phase 7B6q requires only the resource gate to have failed")
    if decision["resource_and_runtime_gates_passed"] is not False:
        raise RuntimeError("Phase 7B6q is only the declared resource-recheck branch")
    p_protocol = json.loads(
        (OUTPUT / "phase7b6p_preregistered_final_formal_flux.json").read_text(
            encoding="utf-8"
        )
    )
    payload = {
        "phase": "7B6q iteration-29 formal-flux resource recheck",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] one exact repeat of the I29 formal diagnostic after "
            "the Phase 7B6p resource-only failure; [V] deterministic flux and RSS; "
            "[O] matter feedback"
        ),
        "sources": {
            "phase7b6p_summary": _source(
                "outputs/phase7b6p_final_formal_flux_summary.json"
            ),
            "phase7b6p_protocol": _source(
                "outputs/phase7b6p_preregistered_final_formal_flux.json"
            ),
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
            "states": ["iteration29", "iteration30"],
            "rerun_states": ["iteration29"],
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
            "repeat_formal_flux_maximum_absolute_difference_exactly": 0.0,
            "formal_face_flux_spectrum_l1_below": 1.0e-3,
            "formal_face_bolometric_flux_fraction_below": 1.0e-3,
            "each_repeat_process_peak_rss_strictly_below_mib": 6144.0,
            "repeat_state_wall_time_strictly_below_s": 900.0,
            "retained_iteration30_resources_must_have_passed": True,
        },
        "authorization": {
            "fixed_material_science_functional_convergence_if_passes": True,
            "single_bounded_matter_feedback_pilot_if_passes": True,
            "algebraic_fixed_point_at_1e-10": False,
            "full_orbit_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6q_preregistered_resource_recheck.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
