"""Phase 7B7b：冻结一次实际相位时长的物质响应与信赖域门。"""

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
    resource = json.loads(
        (OUTPUT / "phase7b7ar_resource_closure_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if resource["decision"]["phase7b7ar_gate_passed"] is not True:
        raise RuntimeError("Phase 7B7b requires passed Phase 7B7a-r")
    coefficient = json.loads(
        (OUTPUT / "phase7b7a_feedback_coefficients_summary.json").read_text(
            encoding="utf-8"
        )
    )
    payload = {
        "phase": "7B7b one frozen-radiation material response",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] one radiation-only Picard response over the actual "
            "phase duration with a ten-percent trust region; [V] charge, particles "
            "and material-energy closure; [O] no radiation remap in this phase"
        ),
        "sources": {
            "phase7b7a_summary": _source(
                "outputs/phase7b7a_feedback_coefficients_summary.json"
            ),
            "phase7b7ar_summary": _source(
                "outputs/phase7b7ar_resource_closure_summary.json"
            ),
            "phase7b7ar_protocol": _source(
                "outputs/phase7b7ar_preregistered_resource_closure.json"
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
            "orbital_kinetics": _source(
                "src/eccentric_tde_observer/orbital_kinetics.py"
            ),
        },
        "upstream_coefficient_sha256": coefficient["coefficient_sha256"],
        "configuration": {
            "half_depth_cell_count": 128,
            "phase_index_from_coefficient_artifact": True,
            "duration_from_coefficient_artifact": True,
            "heating_measure": "Milne rate-integral material heating",
            "population_integrator": "charge-neutral backward Euler",
            "bisection_iterations": 96,
            "collisional_ionization": False,
            "three_body_recombination": False,
            "density_and_geometry_frozen": True,
            "material_energy": "ideal-gas thermal plus H/He ground-state ionization",
            "explicit_radiation_energy_added_to_material": False,
            "radiation_remap": False,
            "cellwise_clipping": False,
            "temperature_floor": False,
            "population_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "cell_count_exactly": 128,
            "maximum_relative_charge_residual_below": 1.0e-12,
            "maximum_particle_conservation_residual_below": 1.0e-12,
            "maximum_relative_material_energy_residual_below": 1.0e-12,
            "minimum_population_fraction_at_least": 0.0,
            "maximum_population_fraction_change_below": 0.1,
            "maximum_relative_temperature_change_below": 0.1,
            "maximum_absolute_local_material_energy_increment_fraction_below": 0.1,
            "wall_time_strictly_below_s": 60.0,
        },
        "authorization": {
            "radiation_remap_with_updated_matter_if_all_gates_pass": True,
            "timescale_diagnosis_only_if_trust_region_fails": True,
            "repeat_same_full_duration_response": False,
            "arbitrary_duration_reduction": False,
            "fully_coupled_iteration": False,
            "full_orbit": False,
            "phase4_replacement": False,
        },
    }
    path = OUTPUT / "phase7b7b_preregistered_material_response.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
