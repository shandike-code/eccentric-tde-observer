"""Phase 7B6n：冻结 I13/I14 的正式 ALE 面通量双映射审计。"""

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
    science = json.loads(
        (OUTPUT / "phase7b6m_science_functionals_summary.json").read_text(
            encoding="utf-8"
        )
    )
    line = json.loads(
        (OUTPUT / "phase7b6j_positivity_line_search_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if science["decision"]["boundary_proxy_gates_passed"] is not False:
        raise RuntimeError("Phase 7B6n is only the declared branch after proxy failure")
    for gate in (
        "state_and_mean_global_gates_passed",
        "integrated_field_gates_passed",
        "photoionization_proxy_gates_passed",
    ):
        if science["decision"][gate] is not True:
            raise RuntimeError(f"Phase 7B6n requires the passed upstream gate: {gate}")
    payload = {
        "phase": "7B6n iteration-13-to-14 formal ALE face-flux gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] two one-map formal-diagnostic evaluations from frozen I13 "
            "and I14; [V] all 9632 groups and both ALE faces; [O] algebraic fixed point"
        ),
        "sources": {
            "phase7b6j_summary": _source(
                "outputs/phase7b6j_positivity_line_search_summary.json"
            ),
            "phase7b6j_protocol": _source(
                "outputs/phase7b6j_preregistered_positivity_line_search.json"
            ),
            "phase7b6m_summary": _source(
                "outputs/phase7b6m_science_functionals_summary.json"
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
        "retained_arrays": {
            "iteration14_state_path": line["line_checkpoint_path"],
            "iteration14_state_sha256": line["line_checkpoint_sha256"],
            "iteration13_residual_path": line["line_residual_checkpoint_path"],
            "iteration13_residual_sha256": line["line_residual_checkpoint_sha256"],
            "shape": [9632, 32, 4096],
            "dtype": "float64",
            "iteration13_reconstruction": "I13 = I14 - omega14 r13",
            "omega14": line["line_weight14"],
        },
        "configuration": {
            "phase_index": 1367,
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "process_count": 2,
            "diagnostic_source_maps_per_state": 1,
            "states": ["iteration13", "iteration14"],
            "formal_flux": "right ALE energy flux minus left ALE energy flux",
            "source_map_only": False,
            "cellwise_clipping": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "each_state_block_count_exactly": 76,
            "each_state_unique_group_count_exactly": 9632,
            "all_mapped_states_nonnegative_and_diagnostics_finite": True,
            "formal_face_flux_spectrum_l1_below": 1.0e-3,
            "formal_face_bolometric_flux_fraction_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_state_wall_time_strictly_below_s": 900.0,
        },
        "authorization": {
            "fixed_material_science_functional_convergence_if_passes": True,
            "single_bounded_matter_feedback_pilot_if_passes": True,
            "algebraic_fixed_point_at_1e-10": False,
            "full_orbit_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6n_preregistered_formal_face_flux.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
