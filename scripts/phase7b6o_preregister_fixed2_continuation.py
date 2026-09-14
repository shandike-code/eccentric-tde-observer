"""Phase 7B6o：冻结从 I14 开始的 16 次可恢复 omega=2 续算。"""

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
        (OUTPUT / "phase7b6n_formal_face_flux_summary.json").read_text(encoding="utf-8")
    )
    line = json.loads(
        (OUTPUT / "phase7b6j_positivity_line_search_summary.json").read_text(
            encoding="utf-8"
        )
    )
    science = json.loads(
        (OUTPUT / "phase7b6m_science_functionals_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if formal["decision"]["phase7b6n_gate_passed"] is not False:
        raise RuntimeError("Phase 7B6o is only the declared continuation after formal failure")
    payload = {
        "phase": "7B6o recoverable sixteen-map omega-two continuation",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] fixed omega=2 selected by the Phase 7B6j positivity "
            "boundary and 16 maps estimated from measured boundary contraction; "
            "[V] recoverable full-frequency maps; [O] final formal face-flux gate"
        ),
        "sources": {
            "phase7b6j_summary": _source(
                "outputs/phase7b6j_positivity_line_search_summary.json"
            ),
            "phase7b6m_summary": _source(
                "outputs/phase7b6m_science_functionals_summary.json"
            ),
            "phase7b6n_summary": _source(
                "outputs/phase7b6n_formal_face_flux_summary.json"
            ),
            "phase7b6h_worker": _source(
                "scripts/phase7b6h_full_frequency_aitken.py"
            ),
            "phase7b6h_protocol": _source(
                "outputs/phase7b6h_preregistered_full_frequency_aitken.json"
            ),
        },
        "initial_checkpoint": {
            "completed_source_maps": 14,
            "state_path": line["line_checkpoint_path"],
            "state_sha256": line["line_checkpoint_sha256"],
            "residual_path": line["line_residual_checkpoint_path"],
            "residual_sha256": line["line_residual_checkpoint_sha256"],
            "size_bytes_each": 10099884032,
        },
        "configuration": {
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "process_count": 2,
            "additional_source_maps_exactly": 16,
            "accepted_weight_exactly": 2.0,
            "stop_early": False,
            "work_directory": "outputs/checkpoints/phase7b6o_work",
            "atomic_manifest": "outputs/checkpoints/phase7b6o_work/manifest.json",
            "final_state_path": "outputs/checkpoints/phase7b6o_full_frequency_iteration30.dat",
            "final_residual_path": "outputs/checkpoints/phase7b6o_full_frequency_residual30.dat",
            "boundary_proxy": science["metrics"]["boundary_cell_flux_spectrum_l1"],
            "cellwise_clipping": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "matter_feedback": False,
        },
        "gates": {
            "each_iteration_block_count_exactly": 76,
            "each_iteration_unique_group_count_exactly": 9632,
            "all_states_nonnegative_and_finite": True,
            "final_boundary_cell_flux_spectrum_l1_below": 1.0e-3,
            "final_boundary_cell_bolometric_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_iteration_wall_time_strictly_below_s": 900.0,
            "each_final_checkpoint_size_bytes_exactly": 10099884032,
        },
        "authorization": {
            "recoverable_fixed2_continuation_authorized": True,
            "final_formal_face_flux_audit_if_passes": True,
            "fixed_material_science_functional_convergence": False,
            "matter_feedback_authorized": False,
            "full_orbit_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6o_preregistered_fixed2_continuation.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
