"""Phase 7B9f：冻结最后两辐射态的 H/He 反馈与基准残差评估。"""

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


def _source(path: str) -> dict[str, object]:
    absolute = ROOT / path
    return {
        "path": path,
        "size_bytes": absolute.stat().st_size,
        "sha256": _sha256(absolute),
    }


def main() -> None:
    upstream_path = OUTPUT / "phase7b9e2_science_functional_extension_summary.json"
    upstream = json.loads(upstream_path.read_text(encoding="utf-8"))
    if (
        upstream["decision"]["phase7b9e2_gate_passed"] is not True
        or upstream["decision"][
            "formal_h_he_rate_and_heating_comparison_authorized"
        ]
        is not True
        or int(upstream["final_additional_map"]) != 10
        or int(upstream["consecutive_converged_maps"]) < 2
    ):
        raise RuntimeError("Phase 7B9f requires passed Phase 7B9e2")
    payload = {
        "phase": "7B9f converged H/He feedback pair and base Newton residual",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] 1e-3 last-two-state H/He science-functional gate; "
            "[V] formal rates, heating identities, symmetry, physical response and "
            "recoverable inner-converged residual; [O] no full-frequency Jv"
        ),
        "sources": {
            "phase7b9e2_summary": _source(
                "outputs/phase7b9e2_science_functional_extension_summary.json"
            ),
            "phase7b9e2_protocol": _source(
                "outputs/phase7b9e2_preregistered_science_functional_extension.json"
            ),
            "phase7b9e2_runner": _source(
                "scripts/phase7b9e2_science_functional_extension.py"
            ),
            "previous_radiation": _source(str(upstream["previous_radiation_path"])),
            "final_radiation": _source(str(upstream["final_radiation_path"])),
            "current_material_state": _source(
                "outputs/phase7b7h_second_material_iterate.npz"
            ),
            "encoded_material_state": _source(
                "outputs/phase7b9d_encoded_base_material_state.npy"
            ),
            "physical_old_time_level": _source(
                "outputs/phase7b4r_depth128_phase2048.npz"
            ),
            "phase7b7j_protocol": _source(
                "outputs/phase7b7j_preregistered_second_assembled_feedback.json"
            ),
            "phase7b7j_runner": _source(
                "scripts/phase7b7j_second_assembled_feedback.py"
            ),
            "phase7b7f_runner": _source(
                "scripts/phase7b7f_assembled_diagnostics.py"
            ),
            "phase7b7g_runner": _source(
                "scripts/phase7b7g_assembled_atomic_rates.py"
            ),
            "phase7b7e_runner": _source(
                "scripts/phase7b7e_radiation_direction.py"
            ),
            "phase7b5x_context": _source(
                "scripts/phase7b5x_full_depth_block_probe.py"
            ),
            "mixed_frame_frequency": _source(
                "src/eccentric_tde_observer/mixed_frame_frequency.py"
            ),
            "multigroup_continuum": _source(
                "src/eccentric_tde_observer/multigroup_continuum.py"
            ),
            "continuum_emission": _source(
                "src/eccentric_tde_observer/continuum_emission.py"
            ),
            "radiation_matter_feedback": _source(
                "src/eccentric_tde_observer/radiation_matter_feedback.py"
            ),
            "material_newton_krylov": _source(
                "src/eccentric_tde_observer/coupled_material_newton_krylov.py"
            ),
            "recoverable_residual": _source(
                "src/eccentric_tde_observer/full_frequency_residual_evaluation.py"
            ),
        },
        "configuration": {
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "material_cell_count": 128,
            "encoded_unknown_count": 512,
            "rate_quadrature_order_per_group": 16,
            "maximum_concurrent_processes": 2,
            "feedback_work_directory": "outputs/checkpoints/phase7b9f_feedback",
            "recoverable_residual_manifest": (
                "outputs/checkpoints/phase7b9f_base_residual_manifest.json"
            ),
            "previous_feedback_output": "outputs/phase7b9f_previous_feedback.npz",
            "final_feedback_output": "outputs/phase7b9f_final_feedback.npz",
            "target_material_output": "outputs/phase7b9f_target_material_state.npz",
            "encoded_residual_output": "outputs/phase7b9f_base_material_residual.npy",
            "transport_or_source_iteration": False,
            "material_update": False,
            "radiation_update": False,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "minimum_comoving_mean_intensity_at_least": 0.0,
            "all_rates_and_arrays_finite": True,
            "all_atomic_rates_at_least": 0.0,
            "atomic_rate_vs_direct_comoving_heating_volume_l1_below": 1.0e-10,
            "atomic_rate_vs_inverse_four_force_volume_l1_below": 1.0e-3,
            "atomic_rate_vs_inverse_four_force_global_fraction_below": 1.0e-3,
            "maximum_parent_mirror_residual_below": 1.0e-8,
            "last_two_photoionization_volume_l1_below": 1.0e-3,
            "last_two_total_recombination_volume_l1_below": 1.0e-3,
            "last_two_atomic_heating_volume_l1_below": 1.0e-3,
            "last_two_direct_heating_volume_l1_below": 1.0e-3,
            "last_two_formal_heating_volume_l1_below": 1.0e-3,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "each_state_wall_time_strictly_below_s": 900.0,
            "encoded_residual_all_finite": True,
        },
        "authorization": {
            "complete_recoverable_base_newton_residual_if_all_gates_pass": True,
            "decide_one_preconditioned_full_frequency_jv_if_residual_is_physical": True,
            "full_frequency_jv": False,
            "newton_step": False,
            "accept_dynamic_NLTE_solution": False,
            "full_orbit": False,
            "phase4_replacement": False,
            "uvot": False,
        },
    }
    path = OUTPUT / "phase7b9f_preregistered_converged_feedback_residual.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
