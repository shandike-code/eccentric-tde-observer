"""Phase 7B8d：冻结两个全频反馈端点之间的受保护离散回溯。"""

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
        (OUTPUT / "phase7b8c_secant_feedback_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        feedback["decision"]["phase7b8c_measurement_gate_passed"] is not True
        or feedback["decision"]["protected_secant_acceleration_accepted"] is not False
    ):
        raise RuntimeError("Phase 7B8d requires the measured 7B8c secant rejection")
    payload = {
        "phase": "7B8d protected feedback-informed residual line search",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] discrete convex backtracking between two complete "
            "radiation-feedback endpoints; [V] affine endpoint predictor, material "
            "domain and conservation; [O] no intermediate radiation map yet"
        ),
        "sources": {
            "current_material_iterate": _source(
                "outputs/phase7b7h_second_material_iterate.npz"
            ),
            "current_assembled_feedback": _source(
                "outputs/phase7b7j_second_assembled_feedback.npz"
            ),
            "secant_material_endpoint": _source(
                "outputs/phase7b8a_protected_secant_material_trial.npz"
            ),
            "secant_assembled_feedback": _source(
                "outputs/phase7b8c_secant_assembled_feedback.npz"
            ),
            "secant_feedback_summary": _source(
                "outputs/phase7b8c_secant_feedback_summary.json"
            ),
            "physical_old_time_level": _source(
                "outputs/phase7b4r_depth128_phase2048.npz"
            ),
            "radiation_matter_feedback": _source(
                "src/eccentric_tde_observer/radiation_matter_feedback.py"
            ),
            "coupled_material_line_search": _source(
                "src/eccentric_tde_observer/coupled_material_line_search.py"
            ),
        },
        "configuration": {
            "candidate_relaxations": [0.25, 0.5, 0.75],
            "selection_objective": (
                "minimum affine-predicted mass-weighted residual among candidates "
                "passing all predicted contraction gates"
            ),
            "state_interpolation": "convex in material specific energy and H/He fractions",
            "residual_interpolation": "affine between two complete radiation-feedback endpoints",
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
            "maximum_predicted_mass_weighted_contraction_below": 0.5,
            "maximum_predicted_limiting_cell_contraction_below": 0.8,
            "maximum_predicted_maximum_cell_contraction_below": 0.995,
            "maximum_relative_temperature_change_at_most": 0.4,
            "maximum_absolute_material_energy_increment_fraction_at_most": 0.15,
            "maximum_population_fraction_change_at_most": 1.0e-5,
            "maximum_relative_energy_residual_below": 1.0e-12,
            "maximum_particle_conservation_residual_below": 1.0e-12,
            "minimum_population_fraction_at_least": 0.0,
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
    path = OUTPUT / "phase7b8d_preregistered_feedback_line_search.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()

