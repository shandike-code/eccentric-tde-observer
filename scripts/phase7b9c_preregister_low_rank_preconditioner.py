"""冻结 Phase 7B9c 单真实割线低秩预条件器门。"""

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
    sources = {
        "preconditioner_module": "src/eccentric_tde_observer/low_rank_secant_preconditioner.py",
        "newton_krylov_module": "src/eccentric_tde_observer/coupled_material_newton_krylov.py",
        "physical_old_time_level": "outputs/phase7b4r_depth128_phase2048.npz",
        "first_feedback": "outputs/phase7b7a_feedback_coefficients.npz",
        "current_material_state": "outputs/phase7b7h_second_material_iterate.npz",
        "current_feedback": "outputs/phase7b7j_second_assembled_feedback.npz",
        "secant_material_trial": "outputs/phase7b8a_protected_secant_material_trial.npz",
        "secant_feedback": "outputs/phase7b8c_secant_assembled_feedback.npz",
        "backtracked_material_trial": "outputs/phase7b8d_feedback_line_search_material_trial.npz",
        "backtracked_feedback": "outputs/phase7b8f_backtracked_assembled_feedback.npz",
        "phase7b9b_summary": "outputs/phase7b9b_recoverable_residual_interface_summary.json",
    }
    protocol = {
        "phase": "7B9c one-observed-secant low-rank inverse preconditioner gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] H0=-I minimal-Frobenius inverse secant update; "
            "[V] one actual directional-map secant plus manufactured low-rank controls; "
            "[O] no inner-converged radiation residual and no full-frequency Jv"
        ),
        "sources": {name: _source(path) for name, path in sources.items()},
        "configuration": {
            "phase_index": 1367,
            "cell_count": 128,
            "encoded_unknown_count": 512,
            "base_inverse_scale": -1.0,
            "maximum_residual_gram_condition_number": 100000000.0,
            "actual_observed_secant_count": 1,
            "maximum_relative_temperature_change_per_trial": 0.5,
            "maximum_absolute_material_energy_increment_fraction_per_trial": 0.25,
            "maximum_population_fraction_change_per_trial": 0.05,
            "candidate_relaxations": [2.0 ** (-index) for index in range(25)],
            "manufactured_dimension": 48,
            "manufactured_rank": 4,
            "manufactured_random_seed": 29,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "actual_secant_identity_relative_residual_below": 1.0e-12,
            "actual_secant_count_exactly": 1,
            "actual_secant_gram_condition_number_below": 1.0e8,
            "secant_and_backtracked_later_responses_physically_rejected": True,
            "manufactured_maximum_inverse_error_below": 1.0e-12,
            "manufactured_preconditioned_gmres_iterations_at_most": 1,
            "manufactured_unpreconditioned_iterations_strictly_above": 1,
            "wall_runtime_strictly_below_s": 60.0,
        },
        "authorization": {
            "design_one_recoverable_inner_converged_base_residual_if_passes": True,
            "use_preconditioner_as_residual_substitute": False,
            "run_full_frequency_jv": False,
            "run_newton_step": False,
            "accept_dynamic_NLTE_solution": False,
            "full_orbit": False,
            "phase4_replacement": False,
            "uvot": False,
        },
    }
    path = OUTPUT / "phase7b9c_preregistered_low_rank_preconditioner.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(json.dumps({"path": str(path), "sha256": _sha256(path)}, indent=2))


if __name__ == "__main__":
    main()
