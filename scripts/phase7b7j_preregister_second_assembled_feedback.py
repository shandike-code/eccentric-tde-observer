"""Phase 7B7j：冻结第二全局辐射态的正式源项、原子率和耦合残差诊断。"""

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
    mapped = json.loads(
        (OUTPUT / "phase7b7i_second_radiation_map_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if mapped["decision"]["phase7b7i_gate_passed"] is not True:
        raise RuntimeError("Phase 7B7j requires passed Phase 7B7i")
    if (
        mapped["decision"][
            "assembled_source_and_atomic_rate_diagnostics_authorized"
        ]
        is not True
    ):
        raise RuntimeError("Phase 7B7j lacks assembled-diagnostic authorization")
    payload = {
        "phase": "7B7j second assembled feedback and fixed-point diagnosis",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] one read-only assembled-state feedback extraction; "
            "[V] formal source identity, H/He rates, symmetry, fixed-time-level "
            "residual and resources; [O] no third material update"
        ),
        "sources": {
            "phase7b7i_summary": _source(
                "outputs/phase7b7i_second_radiation_map_summary.json"
            ),
            "phase7b7i_protocol": _source(
                "outputs/phase7b7i_preregistered_second_radiation_map.json"
            ),
            "phase7b7i_runner": _source(
                "scripts/phase7b7i_second_radiation_map.py"
            ),
            "mapped_radiation_state": _source(
                "outputs/checkpoints/phase7b7i_second_radiation_map.dat"
            ),
            "second_material_iterate": _source(
                "outputs/phase7b7h_second_material_iterate.npz"
            ),
            "previous_material_iterate": _source(
                "outputs/phase7b7d_damped_material_state.npz"
            ),
            "previous_assembled_rates": _source(
                "outputs/phase7b7g_assembled_atomic_rates.npz"
            ),
            "physical_old_time_level": _source(
                "outputs/phase7b4r_depth128_phase2048.npz"
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
            "phase7b4r_material": _source(
                "outputs/phase7b4r_depth128_phase2048.npz"
            ),
            "phase7b5p_master_input": _source(
                "outputs/phase7b5p_master_worker_input.npz"
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
        },
        "configuration": {
            "physical_frequency_groups": 9632,
            "core_frequency_groups": 128,
            "block_count": 76,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "rate_quadrature_order_per_group": 16,
            "short_lived_process_count": 76,
            "blocks_per_process": 1,
            "maximum_concurrent_processes": 2,
            "halo_state": "globally assembled Phase 7B7i mapped state",
            "fixed_point_residual_time_base": (
                "unchanged physical old material time level"
            ),
            "transport_or_source_iteration": False,
            "material_update": False,
            "radiation_update": False,
            "cellwise_clipping": False,
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
            "fixed_point_residual_volume_l1_contraction_fraction_below": 1.0,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "total_wall_time_strictly_below_s": 900.0,
        },
        "fixed_point_acceptance": {
            "mass_weighted_relative_residual_below": 1.0e-3,
            "maximum_cell_relative_residual_below": 1.0e-3,
        },
        "authorization": {
            "bounded_nonlinear_algorithm_decision_if_diagnostics_pass": True,
            "third_material_update": False,
            "accept_as_coupled_fixed_point": False,
            "full_orbit": False,
            "phase4_replacement": False,
        },
    }
    path = OUTPUT / "phase7b7j_preregistered_second_assembled_feedback.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
