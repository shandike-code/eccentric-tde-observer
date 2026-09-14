import hashlib
import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def _load(name: str):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def test_phase7b9a_frozen_protocol_and_component_artifact_pass():
    protocol_path = OUTPUT / "phase7b9a_preregistered_newton_krylov_component.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "c80f6db19ae067ac5b7b320f0de4e4de04acbe9ec3c296f1b63942b64958fb36"
    )
    protocol = _load("phase7b9a_preregistered_newton_krylov_component.json")
    for source in protocol["sources"].values():
        path = ROOT / source["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
    report = _load("phase7b9a_newton_krylov_component_summary.json")
    artifact = ROOT / report["artifact_path"]
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == report["artifact_sha256"]
    assert report["encoded_unknown_count"] == 512
    assert report["actual_frozen_feedback_final_residual_norm"] < 1.0e-9
    assert report["manufactured_nonlocal_final_residual_norm"] < 1.0e-9
    assert report["failed_backtracked_candidate_physical_rejection_preserved"] is True
    assert report["decision"]["phase7b9a_gate_passed"] is True
    assert report["decision"]["new_full_frequency_residual_evaluated"] is False
    assert report["decision"]["accepted_as_dynamic_NLTE_solution"] is False


def test_phase7b9a_figure_and_phase7b9_documents_exist():
    for relative in (
        "outputs/phase7b9a_newton_krylov_component.png",
        "docs/phase7b9a_newton_krylov_component.md",
        "docs/phase7b9b_recoverable_full_frequency_residual.md",
        "src/eccentric_tde_observer/full_frequency_residual_evaluation.py",
        "outputs/phase7b9b_recoverable_residual_interface.png",
    ):
        path = ROOT / relative
        assert path.exists() and path.stat().st_size > 0


def test_phase7b9b_frozen_protocol_and_recoverable_interface_pass():
    protocol_path = OUTPUT / "phase7b9b_preregistered_recoverable_residual.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "962aee72870cf4c2aa3f5bda607c6fe391c381dc8b7d65d37060c0472852cc0d"
    )
    protocol = _load("phase7b9b_preregistered_recoverable_residual.json")
    for source in protocol["sources"].values():
        path = ROOT / source["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
    report = _load("phase7b9b_recoverable_residual_interface_summary.json")
    assert report["production_layout"]["raw_float64_checkpoint_size_bytes"] == (
        9632 * 32 * 4096 * 8
    )
    assert all(report["control_results"].values())
    assert report["same_jv_count_directional_lower_bound_h"] > 5.0
    assert report["radiation_inner_iteration_cost_included"] is False
    assert report["decision"]["phase7b9b_gate_passed"] is True
    assert report["decision"]["unpreconditioned_full_frequency_jv_authorized"] is False
    assert report["decision"]["new_full_frequency_residual_evaluated"] is False


def test_phase7b9c_frozen_protocol_and_low_rank_preconditioner_pass():
    protocol_path = OUTPUT / "phase7b9c_preregistered_low_rank_preconditioner.json"
    assert hashlib.sha256(protocol_path.read_bytes()).hexdigest() == (
        "2b746715010a41f007d2c451543f1146605a3e4c8337a9272ceff52293943308"
    )
    protocol = _load("phase7b9c_preregistered_low_rank_preconditioner.json")
    for source in protocol["sources"].values():
        path = ROOT / source["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
    report = _load("phase7b9c_low_rank_preconditioner_summary.json")
    artifact = ROOT / report["artifact_path"]
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == report["artifact_sha256"]
    assert report["actual_observed_secant_count"] == 1
    assert report["actual_secant_identity_relative_residual"] < 1.0e-12
    assert all(report["later_response_physical_rejections"].values())
    assert report["manufactured_preconditioned_gmres_iterations"] == 1
    assert report["manufactured_unpreconditioned_gmres_iterations"] > 1
    assert report["decision"]["actual_secant_is_inner_converged"] is False
    assert report["decision"]["full_frequency_jv_evaluated"] is False
    assert report["decision"]["phase7b9c_gate_passed"] is True
    assert (
        report["decision"][
            "one_recoverable_inner_converged_base_residual_design_authorized"
        ]
        is True
    )


def _assert_protocol_hash(name: str, expected: str):
    path = OUTPUT / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected


def test_phase7b9d_to_phase7b9e2_corrected_inner_gate_chain():
    _assert_protocol_hash(
        "phase7b9d_preregistered_inner_converged_base_radiation.json",
        "812febafdc66a072c11ad00638034773bbb6c7dc39cd1e58a83551b26c0f59df",
    )
    _assert_protocol_hash(
        "phase7b9e_preregistered_science_functional_continuation.json",
        "469cfe102cf38a6d2d9f80ef3c4cf06810b38e54467739807287a17a1cef12d3",
    )
    _assert_protocol_hash(
        "phase7b9e2_preregistered_science_functional_extension.json",
        "291def7f1b292bdd16a8981bc285aaba3e5e0c3e2bb677e0cbecedb77cf0093e",
    )
    audit = _load("phase7b9d_inner_gate_audit_summary.json")
    assert audit["decision"]["original_internal_ledger_gate_valid"] is False
    assert audit["decision"]["continue_original_protocol_authorized"] is False
    original = _load("phase7b9e_science_functional_continuation_summary.json")
    assert original["final_additional_map"] == 8
    assert original["consecutive_converged_maps"] == 1
    assert original["decision"]["phase7b9e_gate_passed"] is False
    extension = _load("phase7b9e2_science_functional_extension_summary.json")
    assert extension["final_additional_map"] == 10
    assert extension["total_source_maps_at_current_material"] == 11
    assert extension["consecutive_converged_maps"] >= 2
    assert extension["final_global_source_map_residual"] < 1.0e-4
    assert extension["final_boundary_flux_spectrum_l1"] < 1.0e-3
    assert extension["final_boundary_flux_bolometric_fraction"] < 1.0e-3
    assert extension["decision"]["one_map_internal_ledger_used_as_admission_gate"] is False
    assert extension["decision"]["phase7b9e2_gate_passed"] is True


def test_phase7b9f_formal_feedback_and_recoverable_base_residual_pass():
    _assert_protocol_hash(
        "phase7b9f_preregistered_converged_feedback_residual.json",
        "0a665c8dccb1fa59c0e9939d2ded5d5d1dd0c9e7ed9430ac4c466e8b3007398e",
    )
    report = _load("phase7b9f_converged_feedback_residual_summary.json")
    assert max(report["comparison"]["photoionization_volume_l1"]) < 1.0e-3
    assert max(report["comparison"]["total_recombination_volume_l1"]) < 1.0e-3
    assert report["comparison"]["atomic_heating_volume_l1"] < 1.0e-3
    assert report["comparison"]["direct_heating_volume_l1"] < 1.0e-3
    assert report["comparison"]["formal_heating_volume_l1"] < 1.0e-3
    residual = ROOT / report["encoded_residual_path"]
    assert hashlib.sha256(residual.read_bytes()).hexdigest() == report[
        "encoded_residual_sha256"
    ]
    manifest = json.loads(
        (ROOT / report["recoverable_residual_manifest"]).read_text(encoding="utf-8")
    )
    assert manifest["status"] == "complete"
    assert report["decision"]["phase7b9f_gate_passed"] is True
    assert report["decision"]["accepted_as_dynamic_NLTE_solution"] is False


def test_phase7b9g_rejects_unresolved_jv_and_only_authorizes_finite_trial():
    report = _load("phase7b9g_jv_fidelity_decision_summary.json")
    assert report["measured_noise_to_estimated_signal_ratio"] > 100.0
    assert report["decision"]["strict_full_frequency_jv_signal_identifiable"] is False
    assert report["decision"]["strict_full_frequency_jv_evaluated"] is False
    assert report["decision"]["strict_full_frequency_jv_rejected_at_current_inner_fidelity"] is True
    assert report["decision"]["finite_protected_quasi_newton_trial_authorized"] is True
    assert report["decision"]["finite_trial_may_be_called_jv"] is False
    assert report["decision"]["accepted_as_dynamic_nlte_solution"] is False


def test_phase7b9i_material_gate_and_phase7b9j_cost_pause_are_distinct():
    _assert_protocol_hash(
        "phase7b9i_preregistered_finite_trial_radiation.json",
        "c42352a5b61e42b6d84026103b56b1d162ac396adf81afd50e3c8c51ab34838c",
    )
    material = _load("phase7b9i_finite_trial_material_summary.json")
    assert material["relaxation"] == 0.125
    assert material["decision"]["physical_trust_region_passed"] is True
    assert material["decision"]["finite_trial_may_be_called_jv"] is False
    cost = _load("phase7b9j_finite_trial_cost_decision_summary.json")
    assert cost["complete_map_count"] == 3
    assert len(cost["measured_contractions"]) == 2
    assert all(0.0 < value < 1.0 for value in cost["measured_contractions"])
    assert cost["projected_map12_residual_best_observed_q"] > 1.0e-4
    assert cost["decision"]["resume_current_omega1_trial"] is False
    assert cost["decision"]["trial_inner_radiation_converged"] is False
    assert cost["decision"]["trial_true_residual_evaluated"] is False
    assert cost["decision"]["trial_rejected_by_physical_residual"] is False
    assert cost["decision"]["redesign_inner_radiation_acceleration_authorized"] is True
    snapshot = ROOT / cost["pause_snapshot_path"]
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == cost[
        "pause_snapshot_sha256"
    ]


def test_phase7b9k_natural_block_aitken_strictly_fails_cost_gate_only():
    _assert_protocol_hash(
        "phase7b9k_preregistered_block_aitken_pilot.json",
        "af4f6c36bb9941dc1f676250c6ea911c39cf31ad655b346da8bf7d9b06f719fc",
    )
    report = _load("phase7b9k_block_aitken_pilot_summary.json")
    assert len(report["history"]) == 3
    assert [row["map"] for row in report["history"]] == [4, 5, 6]
    assert report["map5_to_map4_residual_ratio"] < 0.95
    assert report["map6_to_map5_residual_ratio"] >= 0.80
    assert report["map6_to_map4_residual_ratio"] < 0.75
    assert report["aitken_blocks_above_two"] >= 1
    assert report["projected_stop_map"] > 28
    assert report["manifest_status"] == "pilot_failed"
    assert report["decision"]["natural_block_aitken_pilot_passed"] is False
    assert report["decision"]["continue_block_aitken_authorized"] is False
    assert report["decision"]["trial_true_residual_evaluated"] is False
    assert report["decision"]["trial_rejected_by_physical_residual"] is False
    assert report["decision"]["accepted_as_dynamic_nlte_solution"] is False


def test_phase7b9l_representative_block_picard_fails_before_full_map():
    _assert_protocol_hash(
        "phase7b9l_preregistered_block_implicit_pilot.json",
        "653e3ca389836e3017b1284f36ea61cc6a6b5c73861ee424f854c88aa6bbe063",
    )
    report = _load("phase7b9l_block_implicit_pilot_summary.json")
    assert len(report["reports"]) == 6
    assert all(len(row["iterations"]) == 8 for row in report["reports"])
    assert report["maximum_final_to_first_local_update_ratio"] >= 0.55
    assert report["median_final_to_first_local_update_ratio"] >= 0.35
    assert report["selected_runtime_multiplier_over_one_update"] < 5.0
    assert report["decision"]["representative_block_implicit_pilot_passed"] is False
    assert report["decision"]["one_full_frequency_block_implicit_map_authorized"] is False
    assert report["decision"]["full_frequency_accelerated_map_evaluated"] is False
    assert report["decision"]["trial_true_residual_evaluated"] is False
    assert report["decision"]["trial_rejected_by_physical_residual"] is False


def test_phase7b9m_exact_positivity_is_not_mistaken_for_residual_improvement():
    _assert_protocol_hash(
        "phase7b9m_preregistered_exact_positive_mode_pilot.json",
        "287bb4e0959ac360bfc367b275282acf4b54a5ea331e8f6eda5acb5cd955944b",
    )
    report = _load("phase7b9m_exact_positive_mode_pilot_summary.json")
    assert len(report["reports"]) == 6
    assert report["unconstrained_weights_above_old_cap"] >= 2
    assert all(row["minimum_candidate_intensity"] >= 0.0 for row in report["reports"])
    assert report["maximum_candidate_to_raw_residual_ratio"] > 10.0
    assert report["median_candidate_to_raw_residual_ratio"] > 1.0
    assert report["decision"]["exact_positive_dominant_mode_pilot_passed"] is False
    assert report["decision"]["one_full_frequency_exact_positive_mode_map_authorized"] is False
    assert report["decision"]["full_frequency_accelerated_map_evaluated"] is False
    assert report["decision"]["trial_true_residual_evaluated"] is False
    assert report["decision"]["trial_rejected_by_physical_residual"] is False


def test_phase7b9n_unpreconditioned_multimode_gate_stops_before_full_map():
    _assert_protocol_hash(
        "phase7b9n_preregistered_multimode_krylov_pilot.json",
        "af54cccbe32a56ed41874cfbf8942a04de015b7d59e1ac7ee8d59715f59535e4",
    )
    report = _load("phase7b9n_multimode_krylov_pilot_summary.json")
    assert report["validated_candidate_count"] == 4
    assert report["maximum_fresh_candidate_to_raw_residual_ratio"] > 1.0
    assert report["median_fresh_candidate_to_raw_residual_ratio"] >= 0.25
    assert report["selected_runtime_multiplier_over_one_update"] < 6.0
    assert report["decision"]["multimode_minimum_residual_pilot_passed"] is False
    assert report["decision"]["one_full_frequency_multimode_map_authorized"] is False
    assert report["decision"]["full_frequency_accelerated_map_evaluated"] is False
    assert report["decision"]["trial_true_residual_evaluated"] is False


def test_phase7b9d_to_phase7b9n_figures_and_documents_are_present():
    for relative in (
        "outputs/phase7b9d_inner_gate_audit.png",
        "outputs/phase7b9e_science_functional_continuation.png",
        "outputs/phase7b9e2_science_functional_extension.png",
        "outputs/phase7b9f_converged_feedback_residual.png",
        "outputs/phase7b9g_jv_fidelity_decision.png",
        "outputs/phase7b9i_finite_trial_material.png",
        "outputs/phase7b9j_finite_trial_cost_decision.png",
        "outputs/phase7b9k_block_aitken_pilot.png",
        "outputs/phase7b9l_block_implicit_pilot.png",
        "outputs/phase7b9m_exact_positive_mode_pilot.png",
        "outputs/phase7b9n_multimode_krylov_pilot.png",
        "docs/phase7b9d_inner_gate_audit.md",
        "docs/phase7b9e_science_functional_continuation.md",
        "docs/phase7b9f_converged_feedback_residual.md",
        "docs/phase7b9g_jv_fidelity_decision.md",
        "docs/phase7b9i_finite_trial_material.md",
        "docs/phase7b9j_finite_trial_cost_decision.md",
        "docs/phase7b9k_block_aitken_pilot.md",
        "docs/phase7b9l_block_implicit_pilot.md",
        "docs/phase7b9m_exact_positive_mode_pilot.md",
        "docs/phase7b9n_multimode_krylov_pilot.md",
    ):
        path = ROOT / relative
        assert path.exists() and path.stat().st_size > 0
        if path.suffix == ".png":
            assert relative in (ROOT / "README.md").read_text(encoding="utf-8") or relative.replace(
                "outputs/", "../outputs/"
            ) in (ROOT / "lecture/项目整体讲义.md").read_text(encoding="utf-8")


def test_phase7b9d_to_phase7b9n_scripts_call_no_forbidden_repairs():
    scripts = (
        "phase7b9d_inner_gate_audit.py",
        "phase7b9e_science_functional_continuation.py",
        "phase7b9e2_science_functional_extension.py",
        "phase7b9f_converged_feedback_residual.py",
        "phase7b9g_jv_fidelity_decision.py",
        "phase7b9i_build_finite_trial_material.py",
        "phase7b9i_finite_trial_radiation.py",
        "phase7b9j_finite_trial_cost_decision.py",
        "phase7b9k_preregister_block_aitken_pilot.py",
        "phase7b9k_block_aitken_pilot.py",
        "phase7b9l_preregister_block_implicit_pilot.py",
        "phase7b9l_block_implicit_pilot.py",
        "phase7b9m_preregister_exact_positive_mode_pilot.py",
        "phase7b9m_exact_positive_mode_pilot.py",
        "phase7b9n_preregister_multimode_krylov_pilot.py",
        "phase7b9n_multimode_krylov_pilot.py",
    )
    forbidden = {"nan_to_num", "clip"}
    for name in scripts:
        tree = ast.parse((ROOT / "scripts" / name).read_text(encoding="utf-8"))
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert forbidden.isdisjoint(calls)
