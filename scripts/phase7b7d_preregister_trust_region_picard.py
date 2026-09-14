"""Phase 7B7d：冻结完整相位非线性方程的一次物质 Picard 阻尼。"""

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
    diagnosis = json.loads(
        (OUTPUT / "phase7b7c_timescale_diagnosis_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if diagnosis["decision"]["phase7b7c_gate_passed"] is not True:
        raise RuntimeError("Phase 7B7d requires passed Phase 7B7c")
    if (
        diagnosis["decision"]["one_trust_region_coupled_pilot_design_authorized"]
        is not True
    ):
        raise RuntimeError("Phase 7B7d lacks trust-region pilot authorization")
    payload = {
        "phase": "7B7d damped material Picard direction",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] solver under-relaxation of the full 889 s implicit "
            "matter residual, not a shortened physical time step; [V] simplex, "
            "material energy and trust boundaries; [O] no radiation map yet"
        ),
        "sources": {
            "phase7b7c_summary": _source(
                "outputs/phase7b7c_timescale_diagnosis_summary.json"
            ),
            "phase7b7b_summary": _source(
                "outputs/phase7b7b_material_response_summary.json"
            ),
            "phase7b7b_candidate": _source(
                "outputs/phase7b7b_unaccepted_material_candidate.npz"
            ),
            "feedback_coefficients": _source(
                "outputs/phase7b7a_feedback_coefficients.npz"
            ),
            "phase7b4r_material": _source(
                "outputs/phase7b4r_depth128_phase2048.npz"
            ),
            "radiation_matter_feedback": _source(
                "src/eccentric_tde_observer/radiation_matter_feedback.py"
            ),
            "material_trust_region": _source(
                "src/eccentric_tde_observer/material_trust_region.py"
            ),
        },
        "configuration": {
            "maximum_relative_temperature_change": 0.05,
            "maximum_absolute_material_energy_increment_fraction": 0.05,
            "bisection_iterations": 96,
            "population_update": "convex combination of old and full candidate",
            "energy_update": "same relaxation times the full material-energy residual",
            "physical_step_duration_changed": False,
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
            "relaxation_strictly_above": 1.0e-4,
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
            "one_full_duration_radiation_directional_map_if_passes": True,
            "accept_as_coupled_fixed_point": False,
            "repeat_material_update_without_radiation_map": False,
            "full_orbit": False,
            "phase4_replacement": False,
        },
    }
    path = OUTPUT / "phase7b7d_preregistered_trust_region_picard.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
