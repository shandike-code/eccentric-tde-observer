"""Phase 7B9bu：在未知真残差前冻结有限物质试步的接受规则。"""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from scripts import phase7b9al_preregister_positive_picard_convergence as helper
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9al_preregister_positive_picard_convergence as helper  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def main() -> None:
    trial = json.loads(
        (OUTPUT / "phase7b9i_finite_trial_material_summary.json").read_text(
            encoding="utf-8"
        )
    )
    fidelity = json.loads(
        (OUTPUT / "phase7b9g_jv_fidelity_decision_summary.json").read_text(
            encoding="utf-8"
        )
    )
    base = json.loads(
        (OUTPUT / "phase7b9f_converged_feedback_residual_summary.json").read_text(
            encoding="utf-8"
        )
    )
    long_protocol = json.loads(
        (OUTPUT / "phase7b9bt_preregistered_long_positive_picard.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        trial["decision"]["phase7b9i_material_gate_passed"] is not True
        or trial["decision"]["accepted_as_nonlinear_step"] is not False
        or fidelity["decision"]["finite_protected_quasi_newton_trial_authorized"]
        is not True
        or fidelity["decision"]["strict_full_frequency_jv_evaluated"] is not False
        or base["decision"]["phase7b9f_gate_passed"] is not True
        or long_protocol["authorization"]["material_feedback_only_after_convergence"]
        is not True
    ):
        raise RuntimeError("Phase 7B9bu requires the unresolved finite trial")

    payload = {
        "phase": "7B9bu preregistered finite-trial true-residual acceptance",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] freeze acceptance before the finite-trial true "
            "residual is known; [V] require two consecutive inner-radiation states, "
            "formal H/He source identities, resolved residual signal, and strict "
            "contraction in three residual norms; [O] one accepted nonlinear step "
            "is not a dynamic NLTE solution"
        ),
        "sources": {
            "phase7b9i_trial_summary": helper._source(
                "outputs/phase7b9i_finite_trial_material_summary.json"
            ),
            "phase7b9i_trial_material": helper._source(
                "outputs/phase7b9i_finite_trial_material_state.npz"
            ),
            "phase7b9g_fidelity_summary": helper._source(
                "outputs/phase7b9g_jv_fidelity_decision_summary.json"
            ),
            "phase7b9f_base_summary": helper._source(
                "outputs/phase7b9f_converged_feedback_residual_summary.json"
            ),
            "phase7b9f_base_residual": helper._source(
                "outputs/phase7b9f_base_material_residual.npy"
            ),
            "phase7b9bt_long_protocol": helper._source(
                "outputs/phase7b9bt_preregistered_long_positive_picard.json"
            ),
            "phase7b9bt_long_runner": helper._source(
                "scripts/phase7b9bt_long_positive_picard.py"
            ),
            "physical_old_time_level": helper._source(
                "outputs/phase7b4r_depth128_phase2048.npz"
            ),
            "material_codec": helper._source(
                "src/eccentric_tde_observer/coupled_material_newton_krylov.py"
            ),
            "material_feedback": helper._source(
                "src/eccentric_tde_observer/radiation_matter_feedback.py"
            ),
        },
        "configuration": {
            "phase_index": 1394,
            "material_cell_count": 128,
            "encoded_component_count_per_cell": 4,
            "inner_radiation_operator": "unrelaxed original full-frequency source map",
            "candidate_residual_definition": (
                "encode(full-duration material target from final formal H/He rates) "
                "minus encode(finite-trial material state)"
            ),
            "inner_noise_definition": (
                "candidate residual from final feedback minus candidate residual "
                "from previous consecutive feedback"
            ),
            "trial_signal_definition": (
                "final candidate residual minus frozen base material residual"
            ),
            "mass_weighted_norm_definition": (
                "sqrt(sum(cell_mass * sum(encoded_cell_residual**2)) / "
                "sum(cell_mass))"
            ),
            "maximum_cell_norm_definition": (
                "max(sqrt(sum(encoded_cell_residual**2)))"
            ),
            "cellwise_clipping": False,
            "nan_to_num": False,
            "floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "consecutive_inner_radiation_state_count_at_least": 2,
            "each_global_original_operator_residual_below": 1.0e-4,
            "each_boundary_spectrum_l1_below": 1.0e-3,
            "each_boundary_bolometric_fraction_below": 1.0e-3,
            "each_formal_feedback_state_gate_passed": True,
            "maximum_last_two_photoionization_volume_l1_below": 1.0e-3,
            "maximum_last_two_total_recombination_volume_l1_below": 1.0e-3,
            "last_two_atomic_heating_volume_l1_below": 1.0e-3,
            "last_two_direct_heating_volume_l1_below": 1.0e-3,
            "last_two_formal_heating_volume_l1_below": 1.0e-3,
            "inner_noise_to_trial_signal_l2_ratio_below": 0.1,
            "candidate_to_base_residual_l2_ratio_below": 1.0,
            "candidate_to_base_mass_weighted_norm_ratio_below": 1.0,
            "candidate_to_base_maximum_cell_norm_ratio_below": 1.0,
            "candidate_state_must_match_frozen_phase7b9i_bytes": True,
            "minimum_population_fraction_at_least": 0.0,
            "all_residual_components_finite": True,
        },
        "authorization": {
            "accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass": True,
            "reject_this_trial_if_any_gate_fails": True,
            "reject_static_approximation_from_one_failed_trial": False,
            "accept_dynamic_nlte_solution": False,
            "full_orbit": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
    }
    path = OUTPUT / "phase7b9bu_preregistered_trial_residual_acceptance.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
