"""Phase 7B7c：冻结失败物质响应的局域时间尺度与深度诊断。"""

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
    response = json.loads(
        (OUTPUT / "phase7b7b_material_response_summary.json").read_text(
            encoding="utf-8"
        )
    )
    decision = response["decision"]
    if decision["charge_particle_and_material_energy_closure_passed"] is not True:
        raise RuntimeError("Phase 7B7c requires a conservative failed response")
    if decision["frozen_radiation_trust_region_passed"] is not False:
        raise RuntimeError("Phase 7B7c is only the trust-region failure branch")
    if decision["timescale_diagnosis_only_authorized"] is not True:
        raise RuntimeError("Phase 7B7c lacks upstream diagnosis authorization")
    payload = {
        "phase": "7B7c material-response timescale and depth diagnosis",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] ten-percent material-energy response time; [V] "
            "heating identity, failed-response reproduction and mass localization; "
            "[O] no shortened update is applied"
        ),
        "sources": {
            "phase7b7b_summary": _source(
                "outputs/phase7b7b_material_response_summary.json"
            ),
            "phase7b7b_protocol": _source(
                "outputs/phase7b7b_preregistered_material_response.json"
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
        },
        "configuration": {
            "response_fraction": 0.1,
            "depth_coordinate": "half-column mass fraction from surface",
            "power_measure": "absolute local net material heating times cell volume",
            "candidate_is_accepted_state": False,
            "shortened_update_applied": False,
            "cellwise_clipping": False,
            "floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "heating_equals_absorbed_minus_emitted_global_scaled_residual_below": 1.0e-12,
            "reproduced_maximum_energy_increment_fraction_relative_error_below": 1.0e-12,
            "reproduced_ten_percent_time_relative_error_below": 1.0e-12,
            "mass_and_absolute_power_fractions_between_zero_and_one": True,
            "all_nonzero_heating_timescales_finite_and_positive": True,
            "wall_time_strictly_below_s": 60.0,
        },
        "authorization": {
            "design_one_trust_region_coupled_pilot_if_passes": True,
            "apply_shortened_frozen_radiation_update": False,
            "repeat_full_duration_frozen_response": False,
            "full_orbit": False,
            "phase4_replacement": False,
        },
    }
    path = OUTPUT / "phase7b7c_preregistered_timescale_diagnosis.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
