"""Phase 7B9de：预注册失败物质候选的第一次二分回溯。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "outputs/phase7b9de_preregistered_half_trial_material.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def source(relative: str) -> dict[str, object]:
    path = ROOT / relative
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def build_payload() -> dict[str, object]:
    dd_summary = json.loads(
        (ROOT / "outputs/phase7b9dd_material_trial_rejection_summary.json").read_text()
    )
    trial_summary = json.loads(
        (ROOT / "outputs/phase7b9i_finite_trial_material_summary.json").read_text()
    )
    if (
        dd_summary["decision"]["finite_trial_rejected"] is not True
        or dd_summary["decision"]["static_approximation_rejected_from_one_failed_trial"]
        is not False
        or float(trial_summary["relaxation"]) != 0.125
    ):
        raise RuntimeError("Phase 7B9de requires the rejected 0.125 finite trial")
    sources = {
        "phase7b9dd_summary": source(
            "outputs/phase7b9dd_material_trial_rejection_summary.json"
        ),
        "phase7b9dd_protocol": source(
            "outputs/phase7b9dd_preregistered_material_trial_rejection.json"
        ),
        "phase7b9i_summary": source(
            "outputs/phase7b9i_finite_trial_material_summary.json"
        ),
        "phase7b9i_trial": source(
            "outputs/phase7b9i_finite_trial_material_state.npz"
        ),
        "phase7b9g_direction": source(
            "outputs/phase7b9g_jv_fidelity_decision.npz"
        ),
        "base_material": source(
            "outputs/phase7b7h_second_material_iterate.npz"
        ),
        "physical_old_time_level": source(
            "outputs/phase7b4r_depth128_phase2048.npz"
        ),
        "material_codec": source(
            "src/eccentric_tde_observer/coupled_material_newton_krylov.py"
        ),
        "builder_runner": source(
            "scripts/phase7b9de_build_half_trial_material.py"
        ),
    }
    return {
        "phase": "7B9de preregistered first dyadic material backtrack",
        "classification": "[A-preregistered]+[V-lineage]+[O]",
        "sources": sources,
        "configuration": {
            "failed_absolute_relaxation": 0.125,
            "backtrack_factor": 0.5,
            "candidate_absolute_relaxation": 0.0625,
            "candidate_definition": (
                "encoded_base + candidate_absolute_relaxation * frozen_direction"
            ),
            "candidate_output": "outputs/phase7b9de_half_trial_material_state.npz",
            "summary_output": "outputs/phase7b9de_half_trial_material_summary.json",
            "figure_output": "outputs/phase7b9de_half_trial_material.png",
        },
        "gates": {
            "maximum_relative_temperature_change": 0.5,
            "maximum_absolute_material_energy_increment_fraction": 0.25,
            "maximum_population_fraction_change": 0.05,
            "minimum_temperature_strictly_above_k": 0.0,
            "minimum_specific_material_energy_strictly_above_erg_g": 0.0,
            "minimum_population_fraction_at_least": 0.0,
            "maximum_simplex_closure_absolute_error_below": (
                4.0 * sys.float_info.epsilon
            ),
            "simplex_roundoff_basis": (
                "four binary64 epsilons bound the two additions in a three-state sum"
            ),
            "all_candidate_arrays_finite": True,
            "candidate_bytes_must_follow_frozen_encoded_definition": True,
        },
        "authorization": {
            "build_exactly_one_material_candidate": True,
            "evaluate_radiation_in_this_stage": False,
            "evaluate_formal_feedback_in_this_stage": False,
            "authorize_full_frequency_radiation_only_if_all_material_gates_pass": True,
            "accept_candidate_as_nonlinear_step": False,
            "reject_static_approximation": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
            "prohibitions": {
                "nan_to_num": True,
                "clipping": True,
                "floors": True,
                "failed_point_deletion": True,
                "posthoc_renormalization": True,
            },
        },
    }


def main() -> None:
    payload = build_payload()
    PROTOCOL_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(sha256(PROTOCOL_PATH))


if __name__ == "__main__":
    main()
