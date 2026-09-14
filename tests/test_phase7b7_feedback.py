import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def _load(name: str):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def test_phase7b7a_science_coefficients_pass_but_original_resources_fail():
    protocol = OUTPUT / "phase7b7a_preregistered_feedback_coefficients.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "27b358cd763cab3f41db50f204fc3d39330fb58903393c99daecd4b753d6b90c"
    )
    report = _load("phase7b7a_feedback_coefficients_summary.json")
    assert report["block_count"] == 76
    assert report["owned_frequency_group_count"] == 9632
    assert report["ownership_minimum"] == report["ownership_maximum"] == 1
    assert report["rate_heating_vs_inverse_four_force_volume_l1"] < 1.0e-3
    assert report["rate_heating_vs_inverse_four_force_global_fraction"] < 1.0e-3
    assert report["maximum_parent_mirror_residual"] < 1.0e-3
    assert report["decision"]["resource_and_runtime_gates_passed"] is False
    assert report["decision"]["phase7b7a_gate_passed"] is False


def test_phase7b7ar_bitwise_isolated_resource_closure_passes():
    protocol = OUTPUT / "phase7b7ar_preregistered_resource_closure.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "a59cf7c39f56f66bcb73ce50ed7163c382c011d593fcda7061eceb50b0b418fb"
    )
    report = _load("phase7b7ar_resource_closure_summary.json")
    assert report["target_block_count"] == 38
    assert all(value == 0.0 for value in report["owner_maximum_absolute_differences"].values())
    assert report["maximum_process_peak_rss_mib"] < 6144.0
    assert report["decision"]["phase7b7ar_gate_passed"] is True
    assert report["decision"]["one_frozen_radiation_matter_update_authorized"] is True


def test_phase7b7b_conserves_but_rejects_full_duration_candidate():
    protocol = OUTPUT / "phase7b7b_preregistered_material_response.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "36a070257f684cd7bbbf05b9378b317f325886610f0b81d40f9759e630e371ac"
    )
    report = _load("phase7b7b_material_response_summary.json")
    assert report["maximum_relative_charge_residual"] < 1.0e-12
    assert report["maximum_particle_conservation_residual"] < 1.0e-12
    assert report["maximum_relative_material_energy_residual"] < 1.0e-12
    assert report["maximum_population_fraction_change"] < 0.1
    assert report["maximum_relative_temperature_change"] > 0.1
    assert report["maximum_absolute_local_material_energy_increment_fraction"] > 0.1
    assert report["decision"]["frozen_radiation_trust_region_passed"] is False
    assert report["decision"]["radiation_remap_with_updated_matter_authorized"] is False
    assert report["decision"]["timescale_diagnosis_only_authorized"] is True


def test_phase7b7c_localizes_fast_surface_response_without_applying_it():
    protocol = OUTPUT / "phase7b7c_preregistered_timescale_diagnosis.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "338e514cf65b6e4677c5f9225b07c68b468733bcf5e7e08ea92e1c36d2e523c6"
    )
    report = _load("phase7b7c_timescale_diagnosis_summary.json")
    assert report["minimum_ten_percent_material_energy_response_time_s"] < 10.0
    assert report["minimum_energy_trust_substep_count_lower_bound"] == 95
    assert report["mass_fraction_with_ten_percent_response_faster_than_phase_step"] < 0.2
    assert report["heating_identity_global_scaled_residual"] < 1.0e-12
    assert report["decision"]["phase7b7c_gate_passed"] is True
    assert report["decision"]["shortened_frozen_radiation_update_authorized"] is False


def test_phase7b7d_accepts_only_a_damped_solver_direction():
    protocol = OUTPUT / "phase7b7d_preregistered_trust_region_picard.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "3015077d122f7a598400eeb66ba7d29e897f360fcdd93783537142714bd208e4"
    )
    report = _load("phase7b7d_trust_region_picard_summary.json")
    assert report["physical_step_duration_changed"] is False
    assert 0.0 < report["solver_relaxation"] < 1.0
    assert report["maximum_relative_temperature_change"] <= 0.05
    assert report["maximum_absolute_material_energy_increment_fraction"] < 0.05
    assert report["maximum_relative_material_energy_residual"] < 1.0e-12
    assert report["maximum_particle_conservation_residual"] < 1.0e-12
    assert report["decision"]["phase7b7d_gate_passed"] is True
    assert report["decision"]["accepted_as_coupled_fixed_point"] is False
    assert report["decision"]["one_full_duration_radiation_directional_map_authorized"] is True


def test_phase7b7e_rejects_direction_on_frame_source_consistency():
    protocol = OUTPUT / "phase7b7e_preregistered_radiation_direction.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "b1878b60a10d939a903373c343985429da2cae2df8857068142c6bd5a461149b"
    )
    report = _load("phase7b7e_radiation_direction_summary.json")
    assert report["block_count"] == 76
    assert report["owned_frequency_group_count"] == 9632
    assert report["one_map_raw_radiation_residual"] < 0.1
    assert report["matter_residual_volume_l1_contraction_fraction"] < 1.0
    assert report["limiting_cell_matter_residual_contraction_fraction"] < 1.0
    assert report["rate_heating_vs_inverse_four_force_volume_l1"] > 1.0e-3
    assert report["rate_heating_vs_inverse_four_force_global_fraction"] > 1.0e-3
    assert report["maximum_process_peak_rss_mib"] < 6144.0
    assert report["decision"]["frame_source_consistency_passed"] is False
    assert report["decision"]["phase7b7e_gate_passed"] is False
    assert report["decision"]["second_material_update_authorized"] is False
    assert report["decision"]["bounded_radiation_continuation_design_authorized"] is False


def test_phase7b7f_identifies_lagged_halo_after_assembled_science_passes():
    protocol = OUTPUT / "phase7b7f_preregistered_assembled_diagnostics.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "40b4dc0440e8db39fd7d8e09b5d33ad120336ea8360b1001f2d2fb4fefbadeba"
    )
    report = _load("phase7b7f_assembled_diagnostics_summary.json")
    assert report["postprocessing_reassembled_without_transport"] is True
    assert report["lagged_rate_vs_inverse_four_force_volume_l1"] > 1.0e-3
    assert report["lagged_volume_l1_reproduction_relative_error"] < 1.0e-12
    assert report["assembled_rate_vs_direct_comoving_source_volume_l1"] < 1.0e-8
    assert report["assembled_rate_vs_inverse_four_force_volume_l1"] < 1.0e-3
    assert report["assembled_rate_vs_inverse_four_force_global_fraction"] < 1.0e-3
    assert report["decision"]["lagged_halo_diagnostic_timing_identified"] is True
    assert report["decision"]["assembled_frame_source_consistency_passed"] is True
    assert report["decision"]["resource_and_runtime_gates_passed"] is False
    assert report["decision"]["phase7b7f_gate_passed"] is False


def test_phase7b7fr_bitwise_resource_closure_passes():
    protocol = OUTPUT / "phase7b7fr_preregistered_resource_closure.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "ed513d0840b6d76139a0a34b82a537f70472d51501c605666cabf45146a63a07"
    )
    report = _load("phase7b7fr_resource_closure_summary.json")
    assert report["block_count"] == 76
    assert report["owned_frequency_group_count"] == 9632
    assert all(
        value == 0.0
        for value in report["maximum_absolute_reference_differences"].values()
    )
    assert report["assembled_rate_vs_direct_comoving_source_volume_l1"] < 1.0e-8
    assert report["assembled_rate_vs_inverse_four_force_volume_l1"] < 1.0e-3
    assert report["assembled_rate_vs_inverse_four_force_global_fraction"] < 1.0e-3
    assert report["maximum_process_peak_rss_mib"] < 6144.0
    assert report["decision"]["phase7b7fr_gate_passed"] is True
    assert report["decision"]["bounded_coupled_continuation_design_authorized"] is True
    assert report["decision"]["second_material_update_authorized"] is False


def test_phase7b7g_assembled_atomic_rates_close_heating_and_resources():
    protocol = OUTPUT / "phase7b7g_preregistered_assembled_atomic_rates.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "df4cf89fd7711c23fc2eafe1d98939631cdec0b739447e0766cf9b335f95d195"
    )
    report = _load("phase7b7g_assembled_atomic_rates_summary.json")
    assert report["block_count"] == 76
    assert report["owned_frequency_group_count"] == 9632
    assert report["heating_reference_volume_l1"] < 1.0e-10
    assert report["maximum_parent_mirror_residual"] < 1.0e-8
    assert report["maximum_process_peak_rss_mib"] < 6144.0
    assert report["decision"]["phase7b7g_gate_passed"] is True
    assert (
        report["decision"][
            "one_second_physical_time_level_picard_direction_authorized"
        ]
        is True
    )


def test_phase7b7h_uses_one_fixed_physical_time_level():
    protocol = OUTPUT / "phase7b7h_preregistered_second_picard_direction.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "8c47eaa33e1016a3479f5b564e61464a70b83e7799816d5d488ddf114a11cad9"
    )
    report = _load("phase7b7h_second_picard_direction_summary.json")
    assert report["physical_step_duration_changed"] is False
    assert report["physical_step_accumulated_again"] is False
    assert report["physical_old_energy_base_relative_residual"] < 1.0e-12
    assert report["fixed_time_level_target_energy_relative_residual"] < 1.0e-12
    assert 0.0 < report["solver_relaxation"] < 1.0
    assert report["maximum_relative_temperature_change"] <= 0.05
    assert report["maximum_absolute_material_energy_increment_fraction"] <= 0.05
    assert report["maximum_relative_material_energy_residual"] < 1.0e-12
    assert report["maximum_particle_conservation_residual"] < 1.0e-12
    assert report["decision"]["phase7b7h_gate_passed"] is True
    assert report["decision"]["accepted_as_coupled_fixed_point"] is False


def test_phase7b7i_second_full_frequency_direction_passes_bounded_map():
    protocol = OUTPUT / "phase7b7i_preregistered_second_radiation_map.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "f9078188430b3672f84a234ea1411c07a428a8045e126528a55b24ed3158d1ea"
    )
    report = _load("phase7b7i_second_radiation_map_summary.json")
    assert report["block_count"] == 76
    assert report["owned_frequency_group_count"] == 9632
    assert report["minimum_mapped_intensity"] >= 0.0
    assert report["one_map_raw_radiation_residual"] < 0.1
    assert report["maximum_process_peak_rss_mib"] < 6144.0
    assert report["decision"]["phase7b7i_gate_passed"] is True
    assert report["decision"]["assembled_source_and_atomic_rates_evaluated"] is False
    assert (
        report["decision"][
            "assembled_source_and_atomic_rate_diagnostics_authorized"
        ]
        is True
    )


def test_phase7b7j_formal_feedback_passes_but_fixed_point_does_not():
    protocol = OUTPUT / "phase7b7j_preregistered_second_assembled_feedback.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "86a93126df0d370c5f8db59468fd2a58c8cd4dc189b4dbc5bcc392b2e028b1f7"
    )
    report = _load("phase7b7j_second_assembled_feedback_summary.json")
    assert report["block_count"] == 76
    assert report["owned_frequency_group_count"] == 9632
    assert report["atomic_rate_vs_direct_comoving_heating_volume_l1"] < 1.0e-10
    assert report["atomic_rate_vs_inverse_four_force_volume_l1"] < 1.0e-3
    assert report["atomic_rate_vs_inverse_four_force_global_fraction"] < 1.0e-3
    assert report["maximum_parent_mirror_residual"] < 1.0e-8
    assert report["fixed_point_residual_volume_l1_contraction_fraction"] < 1.0
    assert report["current_mass_weighted_fixed_point_residual"] > 1.0e-3
    assert report["maximum_current_cell_fixed_point_residual"] > 1.0e-3
    assert report["maximum_process_peak_rss_mib"] < 6144.0
    assert report["decision"]["phase7b7j_measurement_gate_passed"] is True
    assert report["decision"]["fixed_point_residual_contracted"] is True
    assert report["decision"]["accepted_as_coupled_fixed_point"] is False


def test_phase7b7k_rejects_naive_picard_cost_without_claiming_convergence():
    report = _load("phase7b7k_nonlinear_cost_decision_summary.json")
    extrapolation = report["stationary_contraction_extrapolation"]
    assert report["current_weighted_residual"] > report["fixed_point_target"]
    assert report["current_maximum_cell_residual"] > report["fixed_point_target"]
    assert extrapolation["weighted_remaining_cycles"] > 20
    assert extrapolation["limiting_remaining_cycles"] > 20
    assert extrapolation["is_convergence_theorem"] is False
    assert extrapolation["is_runtime_guarantee"] is False
    assert report["decision"]["naive_picard_continuation_authorized"] is False
    assert report["decision"]["third_material_update_authorized"] is False
    assert report["decision"]["accelerated_nonlinear_solver_design_required"] is True


def test_phase7b7_figures_and_artifacts_exist():
    for name in (
        "phase7b7a_feedback_coefficients.png",
        "phase7b7ar_resource_closure.png",
        "phase7b7b_material_response.png",
        "phase7b7c_timescale_diagnosis.png",
        "phase7b7d_trust_region_picard.png",
        "phase7b7e_radiation_direction.png",
        "phase7b7f_assembled_diagnostics.png",
        "phase7b7fr_resource_closure.png",
        "phase7b7g_assembled_atomic_rates.png",
        "phase7b7h_second_picard_direction.png",
        "phase7b7i_second_radiation_map.png",
        "phase7b7j_second_assembled_feedback.png",
        "phase7b7k_nonlinear_cost_decision.png",
        "phase7b7a_feedback_coefficients.npz",
        "phase7b7b_unaccepted_material_candidate.npz",
        "phase7b7d_damped_material_state.npz",
        "phase7b7e_directional_feedback_coefficients.npz",
        "phase7b7f_assembled_diagnostics.npz",
        "phase7b7f_frequency_block_diagnostics.csv",
        "phase7b7g_assembled_atomic_rates.npz",
        "phase7b7h_second_material_iterate.npz",
        "phase7b7j_second_assembled_feedback.npz",
    ):
        path = OUTPUT / name
        assert path.exists() and path.stat().st_size > 0

    checkpoint = OUTPUT / "checkpoints/phase7b7e_damped_matter_radiation_map.dat"
    assert checkpoint.stat().st_size == 9632 * 32 * 4096 * 8
    second_checkpoint = OUTPUT / "checkpoints/phase7b7i_second_radiation_map.dat"
    assert second_checkpoint.stat().st_size == 9632 * 32 * 4096 * 8
