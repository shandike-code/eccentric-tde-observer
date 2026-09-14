"""冻结 Phase 7B9b 可恢复全频残差接口与成本门。"""

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
    phase7b9a = json.loads(
        (OUTPUT / "phase7b9a_newton_krylov_component_summary.json").read_text()
    )
    one_map_cost = float(
        phase7b9a["measured_one_full_frequency_residual_evaluation_cost_s"]
    )
    component_jv_count = int(phase7b9a["actual_frozen_feedback_jv_evaluations"])
    protocol = {
        "phase": "7B9b recoverable full-frequency residual fidelity and cost gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] file-state and fidelity semantics; "
            "[V] deterministic small-array state-machine controls and production-shape audit; "
            "[O] no new full-frequency residual or Jv"
        ),
        "sources": {
            "recoverable_residual_module": _source(
                "src/eccentric_tde_observer/full_frequency_residual_evaluation.py"
            ),
            "newton_krylov_module": _source(
                "src/eccentric_tde_observer/coupled_material_newton_krylov.py"
            ),
            "phase7b9a_summary": _source(
                "outputs/phase7b9a_newton_krylov_component_summary.json"
            ),
            "phase7b8e_summary": _source(
                "outputs/phase7b8e_backtracked_radiation_map_summary.json"
            ),
            "phase7b8f_summary": _source(
                "outputs/phase7b8f_backtracked_feedback_summary.json"
            ),
        },
        "production_layout": {
            "encoded_unknown_count": 512,
            "frequency_group_count": 9632,
            "direction_count": 32,
            "depth_count": 4096,
            "core_frequency_groups_per_block": 128,
            "frequency_block_count": 76,
            "raw_float64_checkpoint_size_bytes": 10099884032,
        },
        "fidelity_contract": {
            "one_map_diagnostic_is_newton_eligible": False,
            "inner_converged_radiation_is_newton_eligible_after_all_gates": True,
            "partial_checkpoint_is_feedback_eligible": False,
            "required_input_hashes": [
                "frozen_protocol",
                "encoded_material_state",
                "decoded_material_state",
                "physical_old_time_level",
                "initial_radiation_checkpoint",
            ],
            "completed_frequency_block_byte_hashes": True,
            "complete_checkpoint_hash": True,
            "atomic_manifest_updates": True,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "temperature_floor": False,
            "population_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "measured_costs": {
            "one_directional_full_frequency_residual_lower_bound_s": one_map_cost,
            "phase7b9a_component_jv_count": component_jv_count,
            "same_jv_count_directional_lower_bound_s": one_map_cost
            * component_jv_count,
            "radiation_inner_iterations_included": False,
        },
        "gates": {
            "production_checkpoint_size_matches_existing_artifact": True,
            "partial_checkpoint_rejected": True,
            "completed_block_tamper_rejected": True,
            "one_map_newton_load_rejected": True,
            "inner_converged_newton_load_exact": True,
            "physical_domain_failure_terminal": True,
            "manifest_tamper_rejected": True,
            "validation_wall_runtime_below_s": 10.0,
        },
        "authorization": {
            "design_block_or_low_rank_preconditioner_if_passes": True,
            "run_unpreconditioned_full_frequency_jv": False,
            "run_new_full_frequency_residual": False,
            "accept_dynamic_NLTE_solution": False,
            "full_orbit": False,
            "phase4_replacement": False,
            "uvot": False,
        },
    }
    path = OUTPUT / "phase7b9b_preregistered_recoverable_residual.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(json.dumps({"path": str(path), "sha256": _sha256(path)}, indent=2))


if __name__ == "__main__":
    main()
