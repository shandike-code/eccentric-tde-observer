import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def _load(name: str):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def test_phase7b8a_protected_secant_preserves_domain_and_time_base():
    protocol = OUTPUT / "phase7b8a_preregistered_protected_secant.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "9a2ad8fb0b5612191998033bfcd273dba4c223a153ae559ce373d5552e967bf2"
    )
    report = _load("phase7b8a_protected_secant_summary.json")
    assert report["physical_step_duration_changed"] is False
    assert report["physical_step_accumulated_again"] is False
    assert 0.0 < report["solver_relaxation"] < 1.0
    assert report["maximum_relative_temperature_change"] <= 0.5
    assert report["maximum_relative_material_energy_residual"] < 1.0e-12
    assert report["maximum_particle_conservation_residual"] < 1.0e-12
    assert report["minimum_population_fraction"] >= 0.0
    assert report["maximum_secant_identity_relative_residual"] < 1.0e-12
    assert report["decision"]["phase7b8a_gate_passed"] is True
    assert report["decision"]["accepted_as_coupled_fixed_point"] is False


def test_phase7b8b_full_frequency_map_passes_only_validation_scope():
    protocol = OUTPUT / "phase7b8b_preregistered_secant_radiation_map.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "2b2129e7f6ba14e5aabd606039da15cdac45c36a92cfe63b7e38e4d23d9cad34"
    )
    report = _load("phase7b8b_secant_radiation_map_summary.json")
    assert report["block_count"] == 76
    assert report["owned_frequency_group_count"] == 9632
    assert report["minimum_mapped_intensity"] >= 0.0
    assert report["one_map_raw_radiation_residual"] < 0.1
    assert report["maximum_process_peak_rss_mib"] < 6144.0
    assert report["decision"]["phase7b8b_gate_passed"] is True
    assert report["decision"]["accelerated_residual_improvement_claimed"] is False
    assert report["decision"]["accepted_as_radiation_or_coupled_fixed_point"] is False


def test_phase7b8c_rejects_secant_on_preregistered_limiting_cell_gate():
    protocol = OUTPUT / "phase7b8c_preregistered_secant_feedback.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "dfd95dd5e499a847fe643750a440201493d2e7dfc46a25b38883fd438962701e"
    )
    report = _load("phase7b8c_secant_feedback_summary.json")
    assert report["atomic_rate_vs_direct_comoving_heating_volume_l1"] < 1.0e-10
    assert report["atomic_rate_vs_inverse_four_force_volume_l1"] < 1.0e-3
    assert report["atomic_rate_vs_inverse_four_force_global_fraction"] < 1.0e-3
    assert report["maximum_parent_mirror_residual"] < 1.0e-8
    assert report["mass_weighted_true_residual_contraction_fraction"] < 0.9
    assert report["previous_limiting_cell_true_residual_contraction_fraction"] > 0.99
    assert report["accelerated_mass_weighted_fixed_point_residual"] > 1.0e-3
    assert report["accelerated_maximum_cell_fixed_point_residual"] > 1.0e-3
    assert report["maximum_process_peak_rss_mib"] < 6144.0
    assert report["decision"]["phase7b8c_measurement_gate_passed"] is True
    assert report["decision"]["accelerated_true_residual_gate_passed"] is False
    assert report["decision"]["protected_secant_acceleration_accepted"] is False
    assert report["decision"]["another_material_update_authorized"] is False


def test_phase7b8_figures_states_and_checkpoint_exist():
    for name in (
        "phase7b8a_protected_secant.png",
        "phase7b8a_protected_secant_material_trial.npz",
        "phase7b8b_secant_radiation_map.png",
        "phase7b8c_secant_feedback.png",
        "phase7b8c_secant_assembled_feedback.npz",
    ):
        path = OUTPUT / name
        assert path.exists() and path.stat().st_size > 0
    checkpoint = OUTPUT / "checkpoints/phase7b8b_secant_radiation_map.dat"
    assert checkpoint.stat().st_size == 9632 * 32 * 4096 * 8


def test_phase7b8d_feedback_line_search_passes_only_prediction_gate():
    protocol = OUTPUT / "phase7b8d_preregistered_feedback_line_search.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "8443043bdf3c51279ad6d29ed4ff7b5113fff8575096bf2ed82174ee938b8399"
    )
    report = _load("phase7b8d_feedback_line_search_summary.json")
    assert report["candidate_relaxations"] == [0.25, 0.5, 0.75]
    assert report["selected_relaxation"] == 0.75
    assert report["predicted_mass_weighted_contraction_fraction"] < 0.5
    assert report["predicted_limiting_cell_contraction_fraction"] < 0.8
    assert report["predicted_maximum_cell_contraction_fraction"] < 0.995
    assert report["maximum_relative_material_energy_residual"] < 1.0e-12
    assert report["maximum_particle_conservation_residual"] < 1.0e-12
    assert report["decision"]["phase7b8d_gate_passed"] is True
    assert report["decision"]["accepted_as_coupled_fixed_point"] is False


def test_phase7b8e_backtracked_full_frequency_map_passes():
    protocol = OUTPUT / "phase7b8e_preregistered_backtracked_radiation_map.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "deec904004113072698dba71651762c778a5c685a2cce3ca48cdd85540ae7934"
    )
    report = _load("phase7b8e_backtracked_radiation_map_summary.json")
    assert report["block_count"] == 76
    assert report["owned_frequency_group_count"] == 9632
    assert report["minimum_mapped_intensity"] >= 0.0
    assert report["one_map_raw_radiation_residual"] < 0.1
    assert report["maximum_process_peak_rss_mib"] < 6144.0
    assert report["decision"]["phase7b8e_gate_passed"] is True
    assert report["decision"]["true_residual_improvement_claimed"] is False


def test_phase7b8f_rejects_backtracking_on_both_local_residual_gates():
    protocol = OUTPUT / "phase7b8f_preregistered_backtracked_feedback.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "b607c40741ef02d09ea4fc7bc3d217137c2e3fb18c6e43adbfea1d49c849ffd2"
    )
    report = _load("phase7b8f_backtracked_feedback_summary.json")
    assert report["atomic_rate_vs_direct_comoving_heating_volume_l1"] < 1.0e-10
    assert report["atomic_rate_vs_inverse_four_force_volume_l1"] < 1.0e-3
    assert report["atomic_rate_vs_inverse_four_force_global_fraction"] < 1.0e-3
    assert report["maximum_parent_mirror_residual"] < 1.0e-8
    assert report["mass_weighted_true_residual_contraction_fraction"] < 0.5
    assert report["previous_limiting_cell_true_residual_contraction_fraction"] > 0.8
    assert report["maximum_cell_true_residual_contraction_fraction"] > 0.995
    assert report["backtracked_mass_weighted_fixed_point_residual"] > 1.0e-3
    assert report["backtracked_maximum_cell_fixed_point_residual"] > 1.0e-3
    assert report["decision"]["phase7b8f_measurement_gate_passed"] is True
    assert report["decision"]["backtracked_triple_true_residual_gate_passed"] is False
    assert report["decision"]["feedback_informed_backtracking_accepted"] is False
    assert report["decision"]["another_material_update_authorized"] is False


def test_phase7b8_backtracking_artifacts_exist():
    for name in (
        "phase7b8d_feedback_line_search.png",
        "phase7b8d_feedback_line_search_material_trial.npz",
        "phase7b8e_backtracked_radiation_map.png",
        "phase7b8f_backtracked_feedback.png",
        "phase7b8f_backtracked_assembled_feedback.npz",
    ):
        path = OUTPUT / name
        assert path.exists() and path.stat().st_size > 0
    checkpoint = OUTPUT / "checkpoints/phase7b8e_backtracked_radiation_map.dat"
    assert checkpoint.stat().st_size == 9632 * 32 * 4096 * 8
