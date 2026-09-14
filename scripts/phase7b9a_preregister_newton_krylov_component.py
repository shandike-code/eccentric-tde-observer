"""Phase 7B9a：冻结物理域矩阵自由 Newton--Krylov 组件门。"""

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
    feedback = json.loads(
        (OUTPUT / "phase7b8f_backtracked_feedback_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        feedback["decision"]["phase7b8f_measurement_gate_passed"] is not True
        or feedback["decision"]["feedback_informed_backtracking_accepted"] is not False
    ):
        raise RuntimeError("Phase 7B9a requires the measured 7B8f local-residual failure")
    payload = {
        "phase": "7B9a physical-domain matrix-free Newton-Krylov component gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] log thermal-energy and H/He log-ratio state, "
            "matrix-free finite-difference Jv and Armijo globalization; [V] actual "
            "128-cell frozen-feedback state plus manufactured nonlocal system; "
            "[O] no new full-frequency residual evaluation"
        ),
        "sources": {
            "phase7b8f_summary": _source(
                "outputs/phase7b8f_backtracked_feedback_summary.json"
            ),
            "failed_backtracked_feedback": _source(
                "outputs/phase7b8f_backtracked_assembled_feedback.npz"
            ),
            "current_assembled_feedback": _source(
                "outputs/phase7b7j_second_assembled_feedback.npz"
            ),
            "current_material_state": _source(
                "outputs/phase7b7h_second_material_iterate.npz"
            ),
            "physical_old_time_level": _source(
                "outputs/phase7b4r_depth128_phase2048.npz"
            ),
            "newton_krylov_module": _source(
                "src/eccentric_tde_observer/coupled_material_newton_krylov.py"
            ),
            "radiation_matter_feedback": _source(
                "src/eccentric_tde_observer/radiation_matter_feedback.py"
            ),
        },
        "configuration": {
            "cell_count": 128,
            "unknowns_per_cell": 4,
            "encoded_unknowns": [
                "log thermal specific energy",
                "log H II/H I",
                "log He II/He I",
                "log He III/He I",
            ],
            "finite_difference_jacobian_relative_step": 1.0e-7,
            "gmres_relative_tolerance": 1.0e-6,
            "maximum_gmres_iterations": 32,
            "maximum_newton_iterations": 64,
            "armijo_coefficient": 1.0e-4,
            "maximum_backtracking_steps": 24,
            "maximum_relative_temperature_change_per_step": 0.5,
            "maximum_absolute_material_energy_increment_fraction_per_step": 0.25,
            "maximum_population_fraction_change_per_step": 0.05,
            "cellwise_clipping": False,
            "population_floor": False,
            "temperature_floor": False,
            "posthoc_renormalization": False,
            "new_full_frequency_radiation_map": False,
        },
        "gates": {
            "codec_maximum_relative_temperature_roundtrip_below": 1.0e-12,
            "codec_maximum_population_roundtrip_below": 1.0e-12,
            "codec_maximum_relative_energy_roundtrip_below": 1.0e-12,
            "actual_encoded_residual_all_finite": True,
            "actual_frozen_feedback_newton_residual_norm_below": 1.0e-9,
            "actual_frozen_feedback_maximum_temperature_difference_below": 1.0e-9,
            "actual_frozen_feedback_maximum_population_difference_below": 1.0e-9,
            "manufactured_nonlocal_residual_norm_below": 1.0e-9,
            "manufactured_nonlocal_state_error_below": 1.0e-8,
            "all_accepted_relaxations_positive_at_most_one": True,
            "wall_time_strictly_below_s": 60.0,
        },
        "authorization": {
            "design_recoverable_full_frequency_residual_interface_if_passes": True,
            "run_full_frequency_jacobian_vector_product": False,
            "accept_as_dynamic_NLTE_solution": False,
            "full_orbit": False,
            "phase4_replacement": False,
        },
    }
    path = OUTPUT / "phase7b9a_preregistered_newton_krylov_component.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
