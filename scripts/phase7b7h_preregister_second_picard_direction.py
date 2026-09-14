"""Phase 7B7h：冻结第二条固定物理时间层物质 Picard 方向。"""

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
    rates = json.loads(
        (OUTPUT / "phase7b7g_assembled_atomic_rates_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if rates["decision"]["phase7b7g_gate_passed"] is not True:
        raise RuntimeError("Phase 7B7h requires passed Phase 7B7g")
    if (
        rates["decision"][
            "one_second_physical_time_level_picard_direction_authorized"
        ]
        is not True
    ):
        raise RuntimeError("Phase 7B7h lacks second-direction authorization")
    payload = {
        "phase": "7B7h second fixed-time-level material Picard direction",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] full backward-Euler candidate from the unchanged "
            "physical old time level and assembled-state rates, then a trust-region "
            "solver step from the current iterate; [V] no repeated physical-time "
            "accumulation, simplex and material energy; [O] radiation not remapped yet"
        ),
        "sources": {
            "phase7b7g_summary": _source(
                "outputs/phase7b7g_assembled_atomic_rates_summary.json"
            ),
            "phase7b7g_protocol": _source(
                "outputs/phase7b7g_preregistered_assembled_atomic_rates.json"
            ),
            "phase7b7g_rates": _source(
                "outputs/phase7b7g_assembled_atomic_rates.npz"
            ),
            "phase7b7g_runner": _source(
                "scripts/phase7b7g_assembled_atomic_rates.py"
            ),
            "current_material_iterate": _source(
                "outputs/phase7b7d_damped_material_state.npz"
            ),
            "physical_old_time_level": _source(
                "outputs/phase7b4r_depth128_phase2048.npz"
            ),
            "radiation_matter_feedback": _source(
                "src/eccentric_tde_observer/radiation_matter_feedback.py"
            ),
            "coupled_material_iteration": _source(
                "src/eccentric_tde_observer/coupled_material_iteration.py"
            ),
        },
        "configuration": {
            "maximum_relative_temperature_change": 0.05,
            "maximum_absolute_material_energy_increment_fraction": 0.05,
            "bisection_iterations": 96,
            "candidate_time_base": "unchanged physical old time level",
            "solver_direction_origin": "current damped nonlinear iterate",
            "physical_step_duration_changed": False,
            "physical_step_accumulated_again": False,
            "density_and_geometry_changed": False,
            "radiation_map": False,
            "cellwise_clipping": False,
            "temperature_floor": False,
            "population_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "cell_count_exactly": 128,
            "physical_old_energy_base_relative_residual_below": 1.0e-12,
            "fixed_time_level_target_energy_relative_residual_below": 1.0e-12,
            "relaxation_strictly_above": 1.0e-5,
            "relaxation_at_most": 1.0,
            "maximum_relative_temperature_change_at_most": 0.05,
            "maximum_absolute_material_energy_increment_fraction_at_most": 0.05,
            "maximum_trust_boundary_utilization_at_least": 0.999,
            "maximum_population_fraction_change_at_most": 0.05,
            "maximum_relative_energy_residual_below": 1.0e-12,
            "maximum_particle_conservation_residual_below": 1.0e-12,
            "minimum_population_fraction_at_least": 0.0,
            "wall_time_strictly_below_s": 60.0,
        },
        "authorization": {
            "one_full_frequency_radiation_directional_map_if_passes": True,
            "accept_as_coupled_fixed_point": False,
            "repeat_material_update_without_radiation_map": False,
            "full_orbit": False,
            "phase4_replacement": False,
        },
    }
    path = OUTPUT / "phase7b7h_preregistered_second_picard_direction.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
