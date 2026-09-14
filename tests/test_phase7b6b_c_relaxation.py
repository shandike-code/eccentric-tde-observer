import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def _load(name: str):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def test_phase7b6b_protocol_and_unprotected_failure_are_retained():
    protocol = OUTPUT / "phase7b6b_preregistered_relaxed_fixed_point.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "58c02021b1e44c712aa2beac9199be7d71a512e85600d99e21a7618cb164d443"
    )
    report = _load("phase7b6b_relaxed_fixed_point_summary.json")
    baseline = next(run for run in report["runs"] if run["relaxation_weight"] == 1.0)
    assert baseline["fixed_point_iterations"] == 35
    assert baseline["final_intensity_sha256"] == (
        "5b982f0cfda44b68bdabd371e008c586f5951aca4794fde4a7be81fbdbac383a"
    )
    assert all(
        run["candidate_valid"] is False
        for run in report["runs"]
        if run["relaxation_weight"] > 1.0
    )
    assert report["decision"]["phase7b6b_gate_passed"] is False
    assert report["decision"]["short_full_depth_contraction_pilot_authorized"] is False


def test_phase7b6c_protocol_is_frozen_and_has_no_cellwise_repair():
    protocol_path = OUTPUT / "phase7b6c_preregistered_guarded_relaxation.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "95d5294cfe3af7639b7bd2275ce3ef05844a856e63bb811e1e18cceddbc4df2e"
    )
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    candidate = protocol["candidate"]
    assert candidate["cellwise_clipping"] is False
    assert candidate["cell_deletion"] is False
    assert candidate["posthoc_renormalization"] is False
    assert candidate["fallback"] == "the unmodified G(I) whole step at omega=1.0"


def test_phase7b6c_guarded_policies_converge_to_the_reference():
    report = _load("phase7b6c_guarded_relaxation_summary.json")
    assert all(report["eligible_policies"].values())
    assert sum(report["improving_policies"].values()) >= 2
    for run in report["runs"]:
        assert run["fixed_point_converged"] is True
        assert run["final_raw_fixed_point_residual"] <= 1.0e-10
        assert run["audit_raw_fixed_point_residual"] <= 1.0e-10
        assert run["minimum_intensity"] >= 0.0
        assert run["accelerated_step_count"] > 0
        assert run["final_intensity_maximum_relative_error"] < 1.0e-9
        assert run["final_spectrum_l1_relative_error"] < 1.0e-9
        assert max(run["final_scalar_relative_errors"].values()) < 1.0e-9


def test_phase7b6c_selects_guarded_1p8_without_overauthorizing():
    report = _load("phase7b6c_guarded_relaxation_summary.json")
    assert report["selected_policy"] == "guarded_1p8"
    assert report["selected_iterations"] == 20
    decision = report["decision"]
    assert decision["phase7b6c_gate_passed"] is True
    assert decision["short_full_depth_contraction_pilot_authorized"] is True
    assert decision["full_column_fixed_point_authorized"] is False
    assert decision["matter_feedback_authorized"] is False
    assert decision["phase4_replacement_authorized"] is False


def test_phase7b6b_c_figures_and_reports_exist():
    for name in (
        "phase7b6b_relaxed_fixed_point.png",
        "phase7b6c_guarded_relaxation.png",
        "phase7b6b_relaxed_fixed_point_summary.json",
        "phase7b6c_guarded_relaxation_summary.json",
    ):
        path = OUTPUT / name
        assert path.exists() and path.stat().st_size > 0


def test_phase7b6d_full_depth_contraction_is_bounded_and_passes():
    protocol_path = OUTPUT / "phase7b6d_preregistered_full_depth_contraction.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "b76d6c4df83077dc939cf532393c7b8642d498aea9ba972b00ef572c7f717846"
    )
    report = _load("phase7b6d_full_depth_contraction_summary.json")
    baseline = report["runs"]["jacobi"]
    guarded = report["runs"]["guarded_1p8"]
    assert baseline["source_map_count"] == guarded["source_map_count"] == 16
    assert baseline["first_source_map_sha256"] == guarded["first_source_map_sha256"]
    assert guarded["accelerated_step_count"] == 15
    assert report["guarded_to_jacobi_final_residual_fraction"] < 0.8
    assert min(run["minimum_intensity"] for run in report["runs"].values()) >= 0.0
    assert report["decision"]["phase7b6d_gate_passed"] is True
    assert report["decision"]["bounded_full_frequency_convergence_pilot_authorized"] is True
    assert report["decision"]["full_column_fixed_point_authorized"] is False
    figure = OUTPUT / "phase7b6d_full_depth_contraction.png"
    assert figure.exists() and figure.stat().st_size > 0


def test_phase7b6e_extended_weights_fail_without_overauthorizing():
    protocol_path = OUTPUT / "phase7b6e_preregistered_extended_relaxation.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "a500eb713c97f1b2ce228b2f27e6f75e094c9f4eae91c5d72074b3747f5b438c"
    )
    report = _load("phase7b6e_extended_relaxation_summary.json")
    assert not any(report["improving_policies"].values())
    assert report["selected_policy"] is None
    assert report["decision"]["phase7b6e_gate_passed"] is False
    assert report["decision"]["bounded_full_frequency_convergence_pilot_authorized"] is False


def test_phase7b6f_full_frequency_contraction_and_checkpoint():
    protocol_path = OUTPUT / "phase7b6f_preregistered_full_frequency_contraction.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "5131f1c8e0dc90613eb3b981a92670512995d27ab2ad95c3cd163655926394b1"
    )
    report = _load("phase7b6f_full_frequency_contraction_summary.json")
    assert len(report["history"]) == 4
    assert report["final_to_first_raw_residual_fraction"] < 0.1
    assert report["decision"]["phase7b6f_gate_passed"] is True
    assert report["decision"]["full_frequency_fixed_point_continuation_authorized"] is True
    assert report["decision"]["full_column_fixed_point_authorized"] is False
    checkpoint = ROOT / report["final_checkpoint_path"]
    assert checkpoint.stat().st_size == report["final_checkpoint_size_bytes"]
    assert report["final_checkpoint_sha256"] == (
        "ff530568eefd0e9fd3eedb55c294ee75b9cffafe0dcb3792327148b25bfc396c"
    )


def test_phase7b6g_vector_aitken_passes_worst_block_gate():
    protocol_path = OUTPUT / "phase7b6g_preregistered_vector_aitken.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "31445ab9dc671e6a2a9a64b5ed9450e8e027de06960a0e352374d9a2fdb1d106"
    )
    report = _load("phase7b6g_vector_aitken_summary.json")
    assert report["source_map_count"] == 16
    assert report["aitken_step_count"] == 15
    assert report["minimum_intensity"] >= 0.0
    assert report["final_to_guarded_1p8_residual_fraction"] < 0.5
    assert report["decision"]["phase7b6g_gate_passed"] is True
    assert report["decision"]["full_column_fixed_point_authorized"] is False


def test_phase7b6h_full_frequency_aitken_is_recoverable_and_bounded():
    protocol_path = OUTPUT / "phase7b6h_preregistered_full_frequency_aitken.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "929bada3bf2e80f0dfd5ae2af25c1909630c41805536a5bf586fa618cf1c321f"
    )
    report = _load("phase7b6h_full_frequency_aitken_summary.json")
    assert [row["global_iteration"] for row in report["history"]] == [5, 6, 7, 8]
    assert report["final_to_first_resumed_raw_residual_fraction"] < 0.8
    assert report["decision"]["phase7b6h_gate_passed"] is True
    assert report["decision"]["full_frequency_aitken_fixed_point_continuation_authorized"] is True
    for path_key, hash_key, expected_hash in (
        (
            "state_checkpoint_path",
            "state_checkpoint_sha256",
            "2eaff5a5a56998643427e043e6675c86ab8e5d92652020b4ded9ccb004d32bb1",
        ),
        (
            "residual_checkpoint_path",
            "residual_checkpoint_sha256",
            "946d8baf884aea909090abf8f6b5010f0eace80875f7eaa8d45a0dfe548d2aa7",
        ),
    ):
        checkpoint = ROOT / report[path_key]
        assert checkpoint.stat().st_size == report["checkpoint_size_bytes"]
        assert report[hash_key] == expected_hash


def test_phase7b6j_line_search_beats_same_start_control_without_repair():
    protocol_path = OUTPUT / "phase7b6j_preregistered_positivity_line_search.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "8d07aed42c30bb22614169aa2976bfd94532ea6b0c3686425566341fccd96ec7"
    )
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    configuration = protocol["configuration"]
    assert configuration["cellwise_clipping"] is False
    assert configuration["intensity_floor"] is False
    assert configuration["point_deletion"] is False

    report = _load("phase7b6j_positivity_line_search_summary.json")
    assert report["line_weight13"] > configuration["fixed_control_weight"]
    assert report["line_weight14"] > configuration["fixed_control_weight"]
    assert report["line_to_control_iteration14_residual_fraction"] < 1.0
    assert report["line_iteration14_to_iteration13_residual_fraction"] < 0.95
    assert report["original_phase7b6i_manifest_unchanged"] is True
    assert report["temporary_branch_states_removed"] is True
    assert report["decision"]["phase7b6j_gate_passed"] is True
    assert report["decision"]["line_search_fixed_point_continuation_authorized"] is True
    assert report["decision"]["full_column_fixed_point_authorized"] is False


def test_phase7b6d_through_j_figures_exist():
    for suffix in (
        "d_full_depth_contraction",
        "e_extended_relaxation",
        "f_full_frequency_contraction",
        "g_vector_aitken",
        "h_full_frequency_aitken",
        "j_positivity_line_search",
    ):
        figure = OUTPUT / f"phase7b6{suffix}.png"
        assert figure.exists() and figure.stat().st_size > 0


def test_phase7b6k_anderson1_fails_the_frozen_improvement_gate():
    protocol_path = OUTPUT / "phase7b6k_preregistered_anderson1.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "d90a08deb64b6f6b5aada5ce393ea61ba6f028048c937a889086f77e4db3aa9e"
    )
    report = _load("phase7b6k_anderson1_summary.json")
    assert report["accelerated_step_count"] == 15
    assert report["minimum_intensity"] >= 0.0
    assert report["final_to_vector_aitken_residual_fraction"] > 1.0
    assert report["decision"]["contraction_gate_passed"] is False
    assert report["decision"]["full_frequency_anderson_pilot_authorized"] is False


def test_phase7b6l_anderson2_improves_but_strictly_fails_gate():
    protocol_path = OUTPUT / "phase7b6l_preregistered_anderson2.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "321b157aa0fb290e7f3cb2215e756756f4117199552bfe0d67982b579afec56f"
    )
    report = _load("phase7b6l_anderson2_summary.json")
    assert report["depth_two_step_count"] == 14
    assert report["positivity_line_step_count"] == 0
    assert 0.5 < report["final_to_vector_aitken_residual_fraction"] < 1.0
    assert report["decision"]["phase7b6l_gate_passed"] is False
    assert report["decision"]["further_anderson_depth_tuning_authorized"] is False


def test_phase7b6m_science_functionals_retain_boundary_failure():
    protocol_path = OUTPUT / "phase7b6m_preregistered_science_functionals.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "a55666d0b4efe0c82516e1301bf14610697b39701e3bbf5bd522e407c9df0339"
    )
    report = _load("phase7b6m_science_functionals_summary.json")
    metrics = report["metrics"]
    assert metrics["volume_mean_spectrum_l1"] < 1.0e-3
    assert metrics["integrated_radiation_energy_fraction"] < 1.0e-3
    assert metrics["boundary_cell_flux_spectrum_l1"] > 1.0e-3
    assert metrics["boundary_cell_bolometric_flux_fraction"] > 1.0e-3
    assert report["decision"]["boundary_proxy_gates_passed"] is False
    assert report["decision"]["single_bounded_matter_feedback_pilot_authorized"] is False


def test_phase7b6n_formal_flux_confirms_boundary_failure():
    protocol_path = OUTPUT / "phase7b6n_preregistered_formal_face_flux.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "30bc0d4b95c35942d6706d59c312dcd9a68006171626cd5f59c10762b123c1e7"
    )
    report = _load("phase7b6n_formal_face_flux_summary.json")
    assert len(report["states"]) == 2
    assert all(state["unique_full_group_coverage"] for state in report["states"])
    assert report["formal_face_flux_spectrum_l1"] > 1.0e-3
    assert report["formal_face_bolometric_fraction"] > 1.0e-3
    assert report["decision"]["phase7b6n_gate_passed"] is False
    assert report["decision"]["fixed_material_science_functional_convergence"] is False


def test_phase7b6k_through_n_figures_exist():
    for suffix in (
        "k_anderson1",
        "l_anderson2",
        "m_science_functionals",
        "n_formal_face_flux",
    ):
        figure = OUTPUT / f"phase7b6{suffix}.png"
        assert figure.exists() and figure.stat().st_size > 0


def test_phase7b6o_recoverable_fixed2_continuation_passes():
    protocol_path = OUTPUT / "phase7b6o_preregistered_fixed2_continuation.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "d02de16d8d1f51892e727df12215373987a55d6cf18b7887758e1ce69be26938"
    )
    report = _load("phase7b6o_fixed2_continuation_summary.json")
    assert [row["global_iteration"] for row in report["history"]] == list(
        range(15, 31)
    )
    assert all(row["accepted_weight"] == 2.0 for row in report["history"])
    assert report["history"][-1]["boundary_cell_flux_spectrum_l1"] < 1.0e-3
    assert report["history"][-1]["boundary_cell_bolometric_fraction"] < 1.0e-3
    assert report["decision"]["phase7b6o_gate_passed"] is True
    for key in ("final_state_path", "final_residual_path"):
        checkpoint = ROOT / report[key]
        assert checkpoint.stat().st_size == 10099884032


def test_phase7b6p_retains_science_pass_and_resource_failure():
    protocol_path = OUTPUT / "phase7b6p_preregistered_final_formal_flux.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "55034de58041f73e0dc971c1ea954a3598987c3cde133913a7657bad060d8fe5"
    )
    report = _load("phase7b6p_final_formal_flux_summary.json")
    assert report["formal_face_flux_spectrum_l1"] < 1.0e-3
    assert report["formal_face_bolometric_fraction"] < 1.0e-3
    assert report["decision"]["resource_and_runtime_gates_passed"] is False
    assert report["decision"]["phase7b6p_gate_passed"] is False


def test_phase7b6q_bitwise_repeat_preserves_resource_failure():
    protocol_path = OUTPUT / "phase7b6q_preregistered_resource_recheck.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "30df49fcb1a626b02d398962d90a2c2f1a8b5094b28da0716aeca1a0f37e007a"
    )
    report = _load("phase7b6q_resource_recheck_summary.json")
    assert report["maximum_formal_flux_reproduction_difference"] == 0.0
    assert min(report["repeat_worker_peak_rss_mib"]) > 6144.0
    assert report["decision"]["repeat_resource_and_runtime_gates_passed"] is False
    assert report["decision"]["phase7b6q_gate_passed"] is False


def test_phase7b6r_worker_recycling_closes_fixed_material_gate():
    protocol_path = OUTPUT / "phase7b6r_preregistered_worker_recycling.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "c95e5754a2926b6edc3855f8379ee8a8f531dac284162bfb59a2e0c767bcfce5"
    )
    report = _load("phase7b6r_worker_recycling_summary.json")
    assert report["maximum_formal_flux_reproduction_difference"] == 0.0
    assert len(report["worker_peak_rss_mib"]) == 4
    assert max(report["worker_peak_rss_mib"]) < 6144.0
    assert report["formal_face_flux_spectrum_l1"] < 1.0e-3
    assert report["formal_face_bolometric_fraction"] < 1.0e-3
    assert report["decision"]["phase7b6r_gate_passed"] is True
    assert report["decision"]["fixed_material_science_functional_convergence"] is True
    assert report["decision"]["single_bounded_matter_feedback_pilot_authorized"] is True
    assert report["decision"]["full_orbit_authorized"] is False


def test_phase7b6o_through_r_figures_exist():
    for suffix in (
        "o_fixed2_continuation",
        "p_final_formal_flux",
        "q_resource_recheck",
        "r_worker_recycling",
    ):
        figure = OUTPUT / f"phase7b6{suffix}.png"
        assert figure.exists() and figure.stat().st_size > 0
