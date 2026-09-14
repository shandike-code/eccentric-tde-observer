"""Phase 7B9 冻结协议 builder 的小文件回归。"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SCRIPT = ROOT / "scripts/phase7b9_protocol_builders.py"
SPEC = importlib.util.spec_from_file_location("phase7b9_protocol_builders", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load Phase 7B9 protocol builders")
builders = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builders
SPEC.loader.exec_module(builders)


def write_bytes(root: Path, relative_path: str, content: bytes) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def write_json(root: Path, relative_path: str, payload: dict[str, object]) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_common_sources(root: Path) -> None:
    for index, relative_path in enumerate(
        (
            builders.FINITE_TRIAL_PROTOCOL,
            builders.FINITE_TRIAL_MATERIAL,
            builders.MASTER_INPUT,
            builders.GENERIC_MAP_RUNNER,
            builders.POSITIVE_SEQUENCE_ENGINE,
            builders.SEEDED_PICARD_RUNNER,
            builders.MAP_WORKER,
            builders.WORKER_HELPERS,
            builders.MIXED_FRAME_OPERATOR,
            builders.MIXED_FRAME_FREQUENCY,
            builders.CHECKPOINT_COPY_RUNNER,
        )
    ):
        write_bytes(root, relative_path, f"source-{index}".encode())


def candidate_fixture(root: Path) -> builders.CandidateMapProtocolSpec:
    write_common_sources(root)
    input_path = "outputs/checkpoints/phase7b6h_full_frequency_residual8.dat"
    output_path = "outputs/checkpoints/phase7b6h_full_frequency_iteration8.dat"
    write_bytes(root, input_path, b"candidate")
    write_bytes(root, output_path, b"previousx")
    summary_path = "outputs/phase7b9cg_third_slow_mode_anderson_summary.json"
    protocol_path = "outputs/phase7b9cg_preregistered_third_slow_mode_anderson.json"
    write_json(
        root,
        summary_path,
        {
            "candidate_state_path": input_path,
            "candidate_state_sha256": builders.sha256(root / input_path),
            "decision": {
                "protected_slow_mode_candidate_passed": True,
                "fresh_original_operator_map_authorized": True,
                "material_feedback_authorized": False,
            },
        },
    )
    write_json(root, protocol_path, {"protocol": "candidate"})
    reference = json.loads(
        (OUTPUT / "phase7b9ch_preregistered_third_candidate_map.json").read_text()
    )
    return builders.CandidateMapProtocolSpec(
        phase=reference["phase"],
        phase_index=reference["configuration"]["phase_index"],
        classification=reference["classification"],
        candidate_summary_path=summary_path,
        candidate_protocol_path=protocol_path,
        candidate_summary_source_key="phase7b9cg_summary",
        candidate_protocol_source_key="phase7b9cg_protocol",
        output_state_path=output_path,
        manifest_path=reference["configuration"]["manifest_path"],
        report_directory=reference["configuration"]["report_directory"],
        summary_path=reference["configuration"]["summary_path"],
        figure_path=reference["configuration"]["figure_path"],
        block_report_prefix=reference["configuration"]["block_report_prefix"],
        runner_path=reference["configuration"]["runner_path"],
    )


def mapped_fixture(root: Path) -> tuple[str, str, str]:
    state_path = "outputs/checkpoints/phase7b6h_full_frequency_iteration8.dat"
    write_bytes(root, state_path, b"mapped123")
    summary_path = "outputs/phase7b9ch_third_candidate_map_summary.json"
    protocol_path = "outputs/phase7b9ch_preregistered_third_candidate_map.json"
    write_json(
        root,
        summary_path,
        {
            "output_state_path": state_path,
            "output_state_sha256": builders.sha256(root / state_path),
            "input_global_original_operator_residual": 1.805e-4,
            "input_boundary_spectrum_l1": 2.52e-6,
            "input_boundary_bolometric_fraction": 7.53e-7,
            "decision": {"global_positive_picard_map_passed": True},
        },
    )
    write_json(root, protocol_path, {"protocol": "mapped"})
    return summary_path, protocol_path, state_path


def anchor_fixture(
    root: Path, mapped_hash: str
) -> tuple[str, str, str, str]:
    anchor_path = "outputs/checkpoints/phase7b6f_full_frequency_iteration4.dat"
    write_bytes(root, anchor_path, b"mapped123")
    summary_path = "outputs/phase7b9ci_third_map_anchor_summary.json"
    protocol_path = "outputs/phase7b9ci_preregistered_third_map_anchor.json"
    authorization_key = "fourth_accelerated_picard_continuation_authorized"
    write_json(
        root,
        summary_path,
        {
            "anchor_state_path": anchor_path,
            "anchor_state_sha256": mapped_hash,
            "decision": {authorization_key: True},
        },
    )
    write_json(root, protocol_path, {"protocol": "anchor"})
    return summary_path, protocol_path, anchor_path, authorization_key


def sequence_continuation_fixture(
    root: Path,
) -> builders.SequencePicardContinuationProtocolSpec:
    write_common_sources(root)
    immutable_path = "outputs/checkpoints/anchor.dat"
    first_mapped_path = "outputs/checkpoints/state_1.dat"
    last_mapped_path = "outputs/checkpoints/state_2.dat"
    scratch_path = "outputs/checkpoints/scratch.dat"
    for path, content in (
        (immutable_path, b"anchor00"),
        (first_mapped_path, b"state001"),
        (last_mapped_path, b"state002"),
        (scratch_path, b"scratch0"),
    ):
        write_bytes(root, path, content)

    sequence_protocol_path = "outputs/prior_sequence_protocol.json"
    write_json(
        root,
        sequence_protocol_path,
        {
            "configuration": {
                "maximum_picard_maps": 2,
                "immutable_anchor_path": immutable_path,
                "immutable_anchor_sha256": builders.sha256(root / immutable_path),
            }
        },
    )
    sequence_summary_path = "outputs/prior_sequence_summary.json"
    write_json(
        root,
        sequence_summary_path,
        {
            "status": "maximum_maps_exhausted",
            "completed_picard_maps": 2,
            "protocol_sha256": builders.sha256(root / sequence_protocol_path),
            "iterations": [
                {
                    "iteration": 0,
                    "input_state_path": "outputs/checkpoints/state_0.dat",
                    "input_state_sha256": "input-zero",
                    "mapped_state_path": first_mapped_path,
                    "mapped_state_sha256": builders.sha256(
                        root / first_mapped_path
                    ),
                    "global_original_operator_residual": 2.0e-4,
                    "boundary_spectrum_l1": 2.0e-6,
                    "boundary_bolometric_fraction": 1.0e-6,
                    "map_passed": True,
                },
                {
                    "iteration": 1,
                    "input_state_path": first_mapped_path,
                    "input_state_sha256": builders.sha256(
                        root / first_mapped_path
                    ),
                    "mapped_state_path": last_mapped_path,
                    "mapped_state_sha256": builders.sha256(root / last_mapped_path),
                    "global_original_operator_residual": 1.8e-4,
                    "boundary_spectrum_l1": 1.8e-6,
                    "boundary_bolometric_fraction": 8.0e-7,
                    "map_passed": True,
                },
            ],
        },
    )

    rejected_protocol_path = "outputs/rejected_anderson_protocol.json"
    write_json(root, rejected_protocol_path, {"protocol": "anderson"})
    rejected_summary_path = "outputs/rejected_anderson_summary.json"
    write_json(
        root,
        rejected_summary_path,
        {
            "protocol_sha256": builders.sha256(root / rejected_protocol_path),
            "decision": {
                "protected_slow_mode_candidate_passed": False,
                "fresh_original_operator_map_authorized": False,
                "resume_phase7b9bt_authorized": True,
                "material_feedback_authorized": False,
            },
        },
    )
    return builders.SequencePicardContinuationProtocolSpec(
        phase="7B9 test sequence continuation",
        phase_index=1500,
        classification="[A-preregistered] pure Picard after rejected Anderson",
        sequence_summary_path=sequence_summary_path,
        sequence_protocol_path=sequence_protocol_path,
        rejected_anderson_summary_path=rejected_summary_path,
        rejected_anderson_protocol_path=rejected_protocol_path,
        scratch_state_path=scratch_path,
        maximum_total_picard_maps=5,
        manifest_path="outputs/checkpoints/test_sequence/manifest.json",
        report_directory="outputs/checkpoints/test_sequence/reports",
        summary_path="outputs/test_sequence_summary.json",
        figure_path="outputs/test_sequence.png",
        runner_path="scripts/test_sequence_runner.py",
    )


def consecutive_confirmation_fixture(
    root: Path,
) -> builders.ConsecutiveConvergenceConfirmationProtocolSpec:
    write_common_sources(root)
    previous_path = "outputs/checkpoints/previous_converged.dat"
    successor_path = "outputs/checkpoints/mapped_successor.dat"
    output_path = "outputs/checkpoints/confirmation_output.dat"
    write_bytes(root, previous_path, b"previous")
    write_bytes(root, successor_path, b"successr")
    write_bytes(root, output_path, b"oldbuffr")

    sequence_protocol_path = "outputs/converged_sequence_protocol.json"
    write_json(
        root,
        sequence_protocol_path,
        {"authorization": {"material_feedback_only_after_convergence": True}},
    )
    protocol_hash = builders.sha256(root / sequence_protocol_path)
    final_record = {
        "iteration": 4,
        "input_state_path": previous_path,
        "input_state_sha256": builders.sha256(root / previous_path),
        "mapped_state_path": successor_path,
        "mapped_state_sha256": builders.sha256(root / successor_path),
        "global_original_operator_residual": 9.0e-5,
        "boundary_spectrum_l1": 8.0e-4,
        "boundary_bolometric_fraction": 7.0e-4,
        "map_passed": True,
    }
    sequence_manifest_path = (
        "outputs/checkpoints/converged_sequence/manifest.json"
    )
    write_json(
        root,
        sequence_manifest_path,
        {
            "status": "complete",
            "protocol_sha256": protocol_hash,
            "accepted_state_path": previous_path,
            "accepted_state_sha256": builders.sha256(root / previous_path),
            "iterations": [final_record],
        },
    )
    sequence_summary_path = "outputs/converged_sequence_summary.json"
    write_json(
        root,
        sequence_summary_path,
        {
            "status": "complete",
            "protocol_sha256": protocol_hash,
            "iterations": [final_record],
            "decision": {
                "positive_picard_sequence_converged": True,
                "material_feedback_authorized": True,
                "dynamic_nlte_solution_accepted": False,
            },
        },
    )
    acceptance_path = "outputs/trial_residual_acceptance.json"
    acceptance = json.loads(
        (OUTPUT / "phase7b9bu_preregistered_trial_residual_acceptance.json").read_text()
    )
    write_json(root, acceptance_path, acceptance)
    return builders.ConsecutiveConvergenceConfirmationProtocolSpec(
        phase="7B9 test consecutive convergence confirmation",
        phase_index=1501,
        classification="[A-preregistered] second consecutive below-1e-4 state",
        sequence_summary_path=sequence_summary_path,
        sequence_manifest_path=sequence_manifest_path,
        sequence_protocol_path=sequence_protocol_path,
        trial_residual_acceptance_path=acceptance_path,
        output_state_path=output_path,
        manifest_path="outputs/checkpoints/confirmation/manifest.json",
        report_directory="outputs/checkpoints/confirmation/reports",
        summary_path="outputs/confirmation_summary.json",
        figure_path="outputs/confirmation.png",
        block_report_prefix="confirmation",
        runner_path="scripts/confirmation_runner.py",
    )


def assert_static_protocol_parity(
    generated: dict[str, object], reference_filename: str
) -> None:
    reference = json.loads((OUTPUT / reference_filename).read_text())
    assert generated["phase"] == reference["phase"]
    assert generated["protocol_version"] == reference["protocol_version"]
    assert generated["classification"] == reference["classification"]
    assert generated["gates"] == reference["gates"]
    assert generated["authorization"] == reference["authorization"]
    assert set(generated["sources"]) == set(reference["sources"])
    assert set(generated["configuration"]) == set(reference["configuration"])


def test_candidate_map_builder_preserves_ch_fields_and_hashes(tmp_path: Path) -> None:
    spec = candidate_fixture(tmp_path)
    payload = builders.build_candidate_map_protocol(tmp_path, spec)
    assert_static_protocol_parity(
        payload, "phase7b9ch_preregistered_third_candidate_map.json"
    )
    configuration = payload["configuration"]
    assert configuration["input_state_sha256"] == builders.sha256(
        tmp_path / configuration["input_state_path"]
    )
    assert configuration["output_state_previous_sha256"] == builders.sha256(
        tmp_path / configuration["output_state_path"]
    )
    assert payload["sources"]["input_state"]["sha256"] == configuration[
        "input_state_sha256"
    ]
    assert all(
        configuration[key] is False
        for key in (
            "cellwise_clipping",
            "nan_to_num",
            "intensity_floor",
            "point_deletion",
            "posthoc_renormalization",
            "matter_feedback_during_map",
        )
    )


def test_anchor_builder_preserves_ci_fields_and_hashes(tmp_path: Path) -> None:
    write_common_sources(tmp_path)
    mapped_summary, mapped_protocol, state_path = mapped_fixture(tmp_path)
    target_path = "outputs/checkpoints/phase7b6f_full_frequency_iteration4.dat"
    write_bytes(tmp_path, target_path, b"oldstate1")
    reference = json.loads(
        (OUTPUT / "phase7b9ci_preregistered_third_map_anchor.json").read_text()
    )
    spec = builders.AnchorCopyProtocolSpec(
        phase=reference["phase"],
        phase_index=reference["configuration"]["phase_index"],
        classification=reference["classification"],
        mapped_summary_path=mapped_summary,
        mapped_protocol_path=mapped_protocol,
        mapped_summary_source_key="phase7b9ch_summary",
        mapped_protocol_source_key="phase7b9ch_protocol",
        mapped_source_state_key="mapped_source_state",
        target_state_path=target_path,
        summary_path=reference["configuration"]["summary_path"],
        postcopy_authorization_key=reference["configuration"][
            "postcopy_authorization_key"
        ],
    )
    payload = builders.build_anchor_copy_protocol(tmp_path, spec)
    assert_static_protocol_parity(
        payload, "phase7b9ci_preregistered_third_map_anchor.json"
    )
    configuration = payload["configuration"]
    assert configuration["source_state_path"] == state_path
    assert configuration["source_state_sha256"] == builders.sha256(
        tmp_path / state_path
    )
    assert configuration["target_state_previous_sha256"] == builders.sha256(
        tmp_path / target_path
    )
    assert configuration["floor"] is False


def test_seeded_builder_preserves_cj_fields_and_hashes(tmp_path: Path) -> None:
    write_common_sources(tmp_path)
    mapped_summary, mapped_protocol, state_path = mapped_fixture(tmp_path)
    mapped_hash = builders.sha256(tmp_path / state_path)
    anchor_summary, anchor_protocol, anchor_path, decision_key = anchor_fixture(
        tmp_path, mapped_hash
    )
    scratch_path = "outputs/checkpoints/phase7b6j_line_search_iteration14.dat"
    write_bytes(tmp_path, scratch_path, b"scratch99")
    reference = json.loads(
        (OUTPUT / "phase7b9cj_preregistered_fourth_accelerated_picard.json").read_text()
    )
    spec = builders.SeededTwoMapPicardProtocolSpec(
        phase=reference["phase"],
        phase_index=reference["configuration"]["phase_index"],
        classification=reference["classification"],
        mapped_summary_path=mapped_summary,
        mapped_protocol_path=mapped_protocol,
        mapped_summary_source_key="phase7b9ch_summary",
        mapped_protocol_source_key="phase7b9ch_protocol",
        anchor_summary_path=anchor_summary,
        anchor_protocol_path=anchor_protocol,
        anchor_summary_source_key="phase7b9ci_summary",
        anchor_protocol_source_key="phase7b9ci_protocol",
        anchor_continuation_decision_key=decision_key,
        scratch_state_path=scratch_path,
        manifest_path=reference["configuration"]["manifest_path"],
        report_directory=reference["configuration"]["report_directory"],
        summary_path=reference["configuration"]["summary_path"],
        figure_path=reference["configuration"]["figure_path"],
        runner_path=reference["configuration"]["runner_path"],
        slow_mode_after_pause_authorization_key=(
            "fourth_slow_mode_test_after_pause"
        ),
    )
    payload = builders.build_seeded_two_map_picard_protocol(tmp_path, spec)
    assert_static_protocol_parity(
        payload, "phase7b9cj_preregistered_fourth_accelerated_picard.json"
    )
    configuration = payload["configuration"]
    assert configuration["immutable_anchor_path"] == anchor_path
    assert configuration["immutable_anchor_sha256"] == mapped_hash
    assert configuration["initial_state_sha256"] == mapped_hash
    assert configuration["scratch_state_initial_sha256"] == builders.sha256(
        tmp_path / scratch_path
    )
    assert payload["reference"] == {
        "initial_global_residual": 1.805e-4,
        "initial_boundary_spectrum_l1": 2.52e-6,
        "initial_boundary_bolometric_fraction": 7.53e-7,
    }
    assert all(
        configuration[key] is False
        for key in (
            "cellwise_clipping",
            "nan_to_num",
            "intensity_floor",
            "point_deletion",
            "posthoc_renormalization",
            "matter_feedback_during_sequence",
        )
    )


def test_sequence_continuation_uses_last_mapped_state_and_fixed_gates(
    tmp_path: Path,
) -> None:
    spec = sequence_continuation_fixture(tmp_path)
    payload = builders.build_sequence_picard_continuation_protocol(tmp_path, spec)
    configuration = payload["configuration"]
    assert configuration["seed_summary_source_key"] == "sequence_summary"
    assert configuration["seed_summary_format"] == "sequence"
    assert configuration["seed_iteration_count"] == 2
    assert configuration["maximum_picard_maps"] == 5
    assert configuration["stop_after_iteration"] == 4
    assert configuration["maximum_concurrent_processes"] == 3
    assert configuration["initial_state_path"] == (
        "outputs/checkpoints/state_2.dat"
    )
    assert configuration["initial_state_sha256"] == builders.sha256(
        tmp_path / configuration["initial_state_path"]
    )
    assert configuration["immutable_anchor_sha256"] == builders.sha256(
        tmp_path / configuration["immutable_anchor_path"]
    )
    assert configuration["scratch_state_initial_sha256"] == builders.sha256(
        tmp_path / configuration["scratch_state_path"]
    )
    assert payload["gates"] == builders.seeded_two_map_gates()
    assert payload["gates"]["global_original_operator_residual_below"] == 1.0e-4
    assert payload["gates"][
        "subsequent_residual_contraction_ratio_below"
    ] == 1.01
    assert {
        "rejected_anderson_summary",
        "rejected_anderson_protocol",
    } <= set(payload["sources"])
    assert payload["authorization"]["resume_pure_picard_after_rejected_anderson"]
    assert not payload["authorization"]["rejected_anderson_candidate_used"]
    assert all(
        configuration[key] is False
        for key in (
            "cellwise_clipping",
            "nan_to_num",
            "intensity_floor",
            "point_deletion",
            "posthoc_renormalization",
            "matter_feedback_during_sequence",
        )
    )


def test_sequence_continuation_rejects_broken_audit_chains(
    tmp_path: Path,
) -> None:
    cases = (
        "status",
        "map_failed",
        "last_state_hash",
        "immutable_hash",
        "scratch_size",
        "anderson_not_rejected",
    )
    for case in cases:
        root = tmp_path / case
        spec = sequence_continuation_fixture(root)
        if case in {"status", "map_failed"}:
            summary = json.loads((root / spec.sequence_summary_path).read_text())
            if case == "status":
                summary["status"] = "complete"
            else:
                summary["iterations"][0]["map_passed"] = False
            write_json(root, spec.sequence_summary_path, summary)
        elif case == "last_state_hash":
            write_bytes(root, "outputs/checkpoints/state_2.dat", b"tampered")
        elif case == "immutable_hash":
            write_bytes(root, "outputs/checkpoints/anchor.dat", b"tampered")
        elif case == "scratch_size":
            write_bytes(root, spec.scratch_state_path, b"short")
        else:
            rejected = json.loads(
                (root / spec.rejected_anderson_summary_path).read_text()
            )
            rejected["decision"]["protected_slow_mode_candidate_passed"] = True
            write_json(root, spec.rejected_anderson_summary_path, rejected)
        with pytest.raises(RuntimeError):
            builders.build_sequence_picard_continuation_protocol(root, spec)


def test_sequence_continuation_rejects_nonincreasing_map_horizon(
    tmp_path: Path,
) -> None:
    spec = sequence_continuation_fixture(tmp_path)
    invalid = builders.SequencePicardContinuationProtocolSpec(
        **{
            **spec.__dict__,
            "maximum_total_picard_maps": 2,
        }
    )
    with pytest.raises(ValueError):
        builders.build_sequence_picard_continuation_protocol(tmp_path, invalid)


def test_consecutive_confirmation_preserves_bu_bv_fields_and_hashes(
    tmp_path: Path,
) -> None:
    spec = consecutive_confirmation_fixture(tmp_path)
    payload = builders.build_consecutive_convergence_confirmation_protocol(
        tmp_path, spec
    )
    configuration = payload["configuration"]
    assert configuration["maximum_concurrent_processes"] == 2
    assert configuration["previous_global_original_operator_residual"] == 9.0e-5
    assert configuration["previous_boundary_spectrum_l1"] == 8.0e-4
    assert configuration["previous_boundary_bolometric_fraction"] == 7.0e-4
    assert configuration["input_state_path"] == (
        "outputs/checkpoints/mapped_successor.dat"
    )
    assert configuration["input_state_sha256"] == builders.sha256(
        tmp_path / configuration["input_state_path"]
    )
    assert configuration["output_state_previous_sha256"] == builders.sha256(
        tmp_path / configuration["output_state_path"]
    )
    assert set(configuration) == {
        "phase_index",
        "physical_frequency_groups",
        "angular_direction_count",
        "radiation_depth_cell_count",
        "natural_frequency_block_count",
        "spatial_scheme",
        "accepted_source_relaxation_exactly",
        "diagnostic_fixed_iteration_count",
        "source_map_only",
        "maximum_concurrent_processes",
        "previous_converged_state_path",
        "previous_converged_state_sha256",
        "previous_global_original_operator_residual",
        "previous_boundary_spectrum_l1",
        "previous_boundary_bolometric_fraction",
        "input_state_path",
        "input_state_sha256",
        "output_state_path",
        "output_state_previous_sha256",
        "raw_float64_checkpoint_size_bytes",
        "manifest_path",
        "report_directory",
        "summary_path",
        "figure_path",
        "block_report_prefix",
        "runner_path",
        "cellwise_clipping",
        "nan_to_num",
        "intensity_floor",
        "point_deletion",
        "posthoc_renormalization",
        "matter_feedback_during_map",
    }
    assert payload["gates"] == builders.consecutive_confirmation_gates()
    assert payload["gates"] == {
        "block_count_exactly": 76,
        "owned_frequency_group_count_exactly": 9632,
        "minimum_input_and_mapped_intensity_at_least": 0.0,
        "both_global_original_operator_residuals_below": 1.0e-4,
        "both_boundary_spectrum_l1_below": 1.0e-3,
        "both_boundary_bolometric_fraction_below": 1.0e-3,
        "each_process_peak_rss_strictly_below_mib": 6144.0,
        "full_map_wall_time_strictly_below_s": 1200.0,
    }
    assert payload["authorization"] == {
        "assemble_formal_h_he_feedback_pair_only_if_all_gates_pass": True,
        "accept_finite_trial_as_nonlinear_step": False,
        "accept_dynamic_nlte_solution": False,
        "full_orbit": False,
        "phase4_replacement": False,
        "uvot": False,
        "real_line_formation": False,
    }
    acceptance = json.loads(
        (tmp_path / spec.trial_residual_acceptance_path).read_text()
    )
    assert payload["gates"][
        "both_global_original_operator_residuals_below"
    ] == acceptance["gates"]["each_global_original_operator_residual_below"]
    assert payload["gates"]["both_boundary_spectrum_l1_below"] == acceptance[
        "gates"
    ]["each_boundary_spectrum_l1_below"]
    assert all(
        configuration[key] is False
        for key in (
            "cellwise_clipping",
            "nan_to_num",
            "intensity_floor",
            "point_deletion",
            "posthoc_renormalization",
            "matter_feedback_during_map",
        )
    )


def test_consecutive_confirmation_rejects_broken_prerequisites(
    tmp_path: Path,
) -> None:
    cases = (
        "summary_status",
        "sequence_decision",
        "map_failed",
        "first_residual",
        "first_boundary",
        "successor_hash",
        "output_size",
        "acceptance_threshold",
    )
    for case in cases:
        root = tmp_path / case
        spec = consecutive_confirmation_fixture(root)
        if case in {"summary_status", "sequence_decision"}:
            summary = json.loads((root / spec.sequence_summary_path).read_text())
            if case == "summary_status":
                summary["status"] = "maximum_maps_exhausted"
            else:
                summary["decision"]["material_feedback_authorized"] = False
            write_json(root, spec.sequence_summary_path, summary)
        elif case in {"map_failed", "first_residual", "first_boundary"}:
            manifest = json.loads((root / spec.sequence_manifest_path).read_text())
            if case == "map_failed":
                manifest["iterations"][-1]["map_passed"] = False
            elif case == "first_residual":
                manifest["iterations"][-1][
                    "global_original_operator_residual"
                ] = 1.0e-4
            else:
                manifest["iterations"][-1]["boundary_spectrum_l1"] = 1.0e-3
            write_json(root, spec.sequence_manifest_path, manifest)
        elif case == "successor_hash":
            write_bytes(
                root,
                "outputs/checkpoints/mapped_successor.dat",
                b"tampered",
            )
        elif case == "output_size":
            write_bytes(root, spec.output_state_path, b"short")
        else:
            acceptance = json.loads(
                (root / spec.trial_residual_acceptance_path).read_text()
            )
            acceptance["gates"][
                "each_global_original_operator_residual_below"
            ] = 2.0e-4
            write_json(root, spec.trial_residual_acceptance_path, acceptance)
        with pytest.raises(RuntimeError):
            builders.build_consecutive_convergence_confirmation_protocol(
                root, spec
            )


def test_freeze_protocol_hash_is_exact_and_checkpoint_target_is_rejected(
    tmp_path: Path,
) -> None:
    payload = {"phase": "test", "gates": builders.seeded_two_map_gates()}
    relative_path = "outputs/test_preregistered_protocol.json"
    digest = builders.freeze_protocol(tmp_path, relative_path, payload)
    frozen = tmp_path / relative_path
    assert json.loads(frozen.read_text()) == payload
    assert digest == hashlib.sha256(frozen.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        builders.freeze_protocol(
            tmp_path, "outputs/checkpoints/forbidden.json", payload
        )
    assert not (tmp_path / "outputs/checkpoints/forbidden.json").exists()
    with pytest.raises(ValueError):
        builders.freeze_protocol(tmp_path, "../outside.json", payload)


def test_builders_import_no_physics_or_process_execution_modules() -> None:
    tree = ast.parse(
        (ROOT / "scripts/phase7b9_protocol_builders.py").read_text()
    )
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert {"numpy", "scipy", "subprocess", "multiprocessing"}.isdisjoint(
        imported | imported_from
    )
    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert {"unlink", "remove", "rmdir"}.isdisjoint(attributes)
