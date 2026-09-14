"""Phase 7B8a：冻结受保护逐单元割线物质提案。"""

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
    decision = json.loads(
        (OUTPUT / "phase7b7k_nonlinear_cost_decision_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if decision["decision"]["accelerated_nonlinear_solver_design_required"] is not True:
        raise RuntimeError("Phase 7B8a requires the Phase 7B7k acceleration decision")
    payload = {
        "phase": "7B8a protected diagonal-secant material proposal",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] per-cell secant of two verified fixed-time-level "
            "material residuals, followed by one global trust relaxation; [V] "
            "energy, H/He simplex, no repeated physical time and predicted progress; "
            "[O] no new radiation map yet"
        ),
        "sources": {
            "phase7b7k_summary": _source(
                "outputs/phase7b7k_nonlinear_cost_decision_summary.json"
            ),
            "phase7b7k_runner": _source(
                "scripts/phase7b7k_nonlinear_cost_decision.py"
            ),
            "previous_material_iterate": _source(
                "outputs/phase7b7d_damped_material_state.npz"
            ),
            "current_material_iterate": _source(
                "outputs/phase7b7h_second_material_iterate.npz"
            ),
            "previous_assembled_rates": _source(
                "outputs/phase7b7g_assembled_atomic_rates.npz"
            ),
            "current_assembled_rates": _source(
                "outputs/phase7b7j_second_assembled_feedback.npz"
            ),
            "physical_old_time_level": _source(
                "outputs/phase7b4r_depth128_phase2048.npz"
            ),
            "radiation_matter_feedback": _source(
                "src/eccentric_tde_observer/radiation_matter_feedback.py"
            ),
            "coupled_material_acceleration": _source(
                "src/eccentric_tde_observer/coupled_material_acceleration.py"
            ),
        },
        "configuration": {
            "maximum_relative_temperature_change": 0.5,
            "maximum_absolute_material_energy_increment_fraction": 0.25,
            "maximum_population_fraction_change": 0.05,
            "bisection_iterations": 96,
            "secant_variable": "ground-state material specific energy per cell",
            "secant_history_depth": 2,
            "secant_target_mixing": "per cell",
            "trust_relaxation": "one global scalar",
            "candidate_time_base": "unchanged physical old time level",
            "physical_step_duration_changed": False,
            "physical_step_accumulated_again": False,
            "radiation_map": False,
            "cellwise_clipping": False,
            "denominator_floor": False,
            "temperature_floor": False,
            "population_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "cell_count_exactly": 128,
            "maximum_absolute_secant_alpha_below": 100.0,
            "minimum_secant_target_population_at_least": 0.0,
            "maximum_secant_target_particle_residual_below": 1.0e-12,
            "maximum_secant_identity_relative_residual_below": 1.0e-10,
            "relaxation_strictly_above": 0.05,
            "relaxation_at_most": 1.0,
            "maximum_relative_temperature_change_at_most": 0.5,
            "maximum_absolute_material_energy_increment_fraction_at_most": 0.25,
            "maximum_population_fraction_change_at_most": 0.05,
            "maximum_trust_boundary_utilization_at_least": 0.999,
            "maximum_relative_energy_residual_below": 1.0e-12,
            "maximum_particle_conservation_residual_below": 1.0e-12,
            "minimum_population_fraction_at_least": 0.0,
            "affine_secant_predicted_residual_contraction_below": 0.9,
            "frozen_current_radiation_residual_contraction_below": 1.0,
            "wall_time_strictly_below_s": 60.0,
        },
        "authorization": {
            "one_full_frequency_radiation_validation_map_if_passes": True,
            "accept_as_coupled_fixed_point": False,
            "repeat_material_update_without_radiation_map": False,
            "full_orbit": False,
            "phase4_replacement": False,
        },
    }
    path = OUTPUT / "phase7b8a_preregistered_protected_secant.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
