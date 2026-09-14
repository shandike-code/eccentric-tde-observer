"""Phase 7B6m：冻结第 13--14 次全频状态的科学泛函收敛审计。"""

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
    line = json.loads(
        (OUTPUT / "phase7b6j_positivity_line_search_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if line["decision"]["phase7b6j_gate_passed"] is not True:
        raise RuntimeError("Phase 7B6m requires the accepted Phase 7B6j branch")
    payload = {
        "phase": "7B6m iteration-13-to-14 fixed-material science-functional gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] 1e-3 science-functional tolerance on the retained "
            "fixed-material states; [V] all groups, angles, and depths; "
            "[O] algebraic 1e-10 fixed point and matter feedback"
        ),
        "sources": {
            "phase7b6j_summary": _source(
                "outputs/phase7b6j_positivity_line_search_summary.json"
            ),
            "phase7b6j_protocol": _source(
                "outputs/phase7b6j_preregistered_positivity_line_search.json"
            ),
            "phase7b4r_material": _source(
                "outputs/phase7b4r_depth128_phase2048.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
            ),
            "multiresolution_frequency": _source(
                "src/eccentric_tde_observer/multiresolution_frequency.py"
            ),
        },
        "retained_arrays": {
            "iteration14_state": {
                "path": line["line_checkpoint_path"],
                "sha256": line["line_checkpoint_sha256"],
            },
            "iteration13_residual": {
                "path": line["line_residual_checkpoint_path"],
                "sha256": line["line_residual_checkpoint_sha256"],
            },
            "size_bytes_each": 10099884032,
            "shape": [9632, 32, 4096],
            "dtype": "float64",
            "reconstruction": "I13 = I14 - omega14 * r13",
            "omega14": line["line_weight14"],
        },
        "configuration": {
            "frequency_chunk_groups": 8,
            "all_frequency_groups_used": True,
            "all_angular_directions_used": True,
            "all_depth_cells_used": True,
            "angular_mean": "J_nu = 0.5 sum_m w_m I_nu,m",
            "two_sided_boundary_cell_flux_proxy": (
                "2 pi [sum_(mu<0) w |mu| I_left + sum_(mu>0) w mu I_right]"
            ),
            "photoionization_proxy": (
                "H I, He I, He II P0 rate integrals evaluated from lab-frame J_nu; "
                "a convergence diagnostic, not a replacement for the comoving rate"
            ),
            "frequency_quadrature_order_per_group": 16,
            "cellwise_clipping": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "all_array_hashes_and_sizes_exact": True,
            "reconstructed_iteration13_nonnegative": True,
            "maximum_global_state_update_fraction_below": 1.0e-3,
            "maximum_global_angular_mean_update_fraction_below": 1.0e-3,
            "frequency_depth_weighted_angular_mean_l1_below": 1.0e-3,
            "volume_mean_spectrum_l1_below": 1.0e-3,
            "integrated_radiation_energy_fraction_below": 1.0e-3,
            "boundary_cell_flux_spectrum_l1_below": 1.0e-3,
            "boundary_cell_bolometric_flux_fraction_below": 1.0e-3,
            "each_photoionization_depth_profile_global_fraction_below": 1.0e-3,
            "each_volume_mean_photoionization_fraction_below": 1.0e-3,
        },
        "authorization": {
            "fixed_material_science_functional_convergence_if_passes": True,
            "single_bounded_matter_feedback_pilot_if_passes": True,
            "algebraic_fixed_point_at_1e-10": False,
            "full_orbit_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }
    path = OUTPUT / "phase7b6m_preregistered_science_functionals.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
