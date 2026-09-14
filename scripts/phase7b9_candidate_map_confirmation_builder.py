"""Phase 7B9：从通过的 global candidate map 构造第二连续态确认协议。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from scripts import phase7b9_protocol_builders as common
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_protocol_builders as common  # type: ignore[no-redef]


@dataclass(frozen=True)
class CandidateMapConsecutiveConfirmationSpec:
    phase: str
    phase_index: int
    classification: str
    candidate_map_summary_path: str
    candidate_map_protocol_path: str
    trial_residual_acceptance_path: str
    output_state_path: str
    manifest_path: str
    report_directory: str
    summary_path: str
    figure_path: str
    block_report_prefix: str
    runner_path: str


def _validate_acceptance(acceptance: dict[str, object]) -> None:
    gates = acceptance.get("gates", {})
    authorization = acceptance.get("authorization", {})
    if (
        int(gates.get("consecutive_inner_radiation_state_count_at_least", -1))
        != 2
        or gates.get("each_global_original_operator_residual_below") != 1.0e-4
        or gates.get("each_boundary_spectrum_l1_below") != 1.0e-3
        or gates.get("each_boundary_bolometric_fraction_below") != 1.0e-3
        or gates.get("each_formal_feedback_state_gate_passed") is not True
        or authorization.get(
            "accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass"
        )
        is not True
        or authorization.get("accept_dynamic_nlte_solution") is not False
    ):
        raise RuntimeError("trial-residual acceptance is incompatible with confirmation")


def _validate_candidate_map(
    root: Path,
    summary: dict[str, object],
    protocol: dict[str, object],
    protocol_path: str,
) -> None:
    protocol_hash = common.sha256(root / protocol_path)
    decision = summary.get("decision", {})
    checks = summary.get("gate_checks", {})
    configuration = protocol.get("configuration", {})
    gates = protocol.get("gates", {})
    authorization = protocol.get("authorization", {})
    required_checks = (
        "frequency_ownership_pass",
        "positive_map_pass",
        "input_residual_reproduction_pass",
        "input_boundary_reproduction_pass",
        "worker_resources_pass",
    )
    if (
        summary.get("protocol_sha256") != protocol_hash
        or decision.get("global_positive_picard_map_passed") is not True
        or decision.get("mapped_state_committed_as_diagnostic_candidate") is not True
        or decision.get("mapped_state_self_guard_residual_audit_authorized")
        is not True
        or decision.get("material_feedback_authorized") is not False
        or any(checks.get(name) is not True for name in required_checks)
        or authorization.get("commit_recoverable_mapped_state_if_all_map_gates_pass")
        is not True
        or authorization.get(
            "second_consecutive_original_residual_required_if_below_target"
        )
        is not True
        or authorization.get("material_feedback") is not False
        or authorization.get("accept_dynamic_nlte_solution") is not False
    ):
        raise RuntimeError("candidate map does not authorize a consecutive audit")
    if (
        summary.get("input_state_path") != configuration.get("input_state_path")
        or summary.get("input_state_sha256")
        != configuration.get("input_state_sha256")
        or summary.get("output_state_path") != configuration.get("output_state_path")
        or int(configuration.get("diagnostic_fixed_iteration_count", -1)) != 1
        or configuration.get("accepted_source_relaxation_exactly") != 1.0
        or configuration.get("source_map_only") is not True
    ):
        raise RuntimeError("candidate-map protocol/summary lineage changed")
    prohibitions = common.numerical_repair_prohibitions(sequence=False)
    if any(configuration.get(name) != value for name, value in prohibitions.items()):
        raise RuntimeError("candidate map used an unauthorized numerical repair")
    metrics = (
        (
            summary.get("input_global_original_operator_residual"),
            1.0e-4,
        ),
        (summary.get("input_boundary_spectrum_l1"), 1.0e-3),
        (summary.get("input_boundary_bolometric_fraction"), 1.0e-3),
        (
            summary.get("maximum_process_peak_rss_mib"),
            gates.get("each_process_peak_rss_strictly_below_mib"),
        ),
        (
            summary.get("wall_runtime_s"),
            gates.get("full_map_wall_time_strictly_below_s"),
        ),
    )
    if any(
        value is None or limit is None or float(value) >= float(limit)
        for value, limit in metrics
    ):
        raise RuntimeError("candidate-map residual, boundary, or resource gate failed")
    for path_key, hash_key in (
        ("input_state_path", "input_state_sha256"),
        ("output_state_path", "output_state_sha256"),
    ):
        state = root / str(summary[path_key])
        if common.sha256(state) != summary[hash_key]:
            raise RuntimeError("candidate-map checkpoint hash changed")


def build_candidate_map_consecutive_confirmation_protocol(
    root: Path,
    spec: CandidateMapConsecutiveConfirmationSpec,
) -> dict[str, object]:
    """Build one confirmation protocol without executing the original operator."""
    summary = common.read_json(root, spec.candidate_map_summary_path)
    candidate_protocol = common.read_json(root, spec.candidate_map_protocol_path)
    acceptance = common.read_json(root, spec.trial_residual_acceptance_path)
    _validate_acceptance(acceptance)
    _validate_candidate_map(
        root,
        summary,
        candidate_protocol,
        spec.candidate_map_protocol_path,
    )
    previous_relative = str(summary["input_state_path"])
    input_relative = str(summary["output_state_path"])
    previous = root / previous_relative
    input_state = root / input_relative
    output_state = root / spec.output_state_path
    if spec.output_state_path in {previous_relative, input_relative}:
        raise RuntimeError("confirmation output must be independent of both pair states")
    if (
        previous.stat().st_size != input_state.stat().st_size
        or input_state.stat().st_size != output_state.stat().st_size
    ):
        raise RuntimeError("candidate confirmation buffer sizes changed")
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            "candidate_map_summary": common.source_entry(
                root, spec.candidate_map_summary_path
            ),
            "candidate_map_protocol": common.source_entry(
                root, spec.candidate_map_protocol_path
            ),
            "trial_residual_acceptance": common.source_entry(
                root, spec.trial_residual_acceptance_path
            ),
            "previous_converged_state": common.source_entry(root, previous_relative),
            "input_state": common.source_entry(root, input_relative),
            "finite_trial_protocol": common.source_entry(
                root, common.FINITE_TRIAL_PROTOCOL
            ),
            "finite_trial_material": common.source_entry(
                root, common.FINITE_TRIAL_MATERIAL
            ),
            "phase7b5p_master_input": common.source_entry(root, common.MASTER_INPUT),
            "generic_map_runner": common.source_entry(root, common.GENERIC_MAP_RUNNER),
            "phase7b7i_worker": common.source_entry(root, common.MAP_WORKER),
            "phase7b9d_worker_helpers": common.source_entry(root, common.WORKER_HELPERS),
            "mixed_frame_operator": common.source_entry(root, common.MIXED_FRAME_OPERATOR),
            "mixed_frame_frequency": common.source_entry(root, common.MIXED_FRAME_FREQUENCY),
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": common.PHYSICAL_FREQUENCY_GROUPS,
            "angular_direction_count": common.ANGULAR_DIRECTION_COUNT,
            "radiation_depth_cell_count": common.RADIATION_DEPTH_CELL_COUNT,
            "natural_frequency_block_count": common.NATURAL_FREQUENCY_BLOCK_COUNT,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "accepted_source_relaxation_exactly": 1.0,
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "maximum_concurrent_processes": 2,
            "previous_converged_state_path": previous_relative,
            "previous_converged_state_sha256": summary["input_state_sha256"],
            "previous_global_original_operator_residual": summary[
                "input_global_original_operator_residual"
            ],
            "previous_boundary_spectrum_l1": summary["input_boundary_spectrum_l1"],
            "previous_boundary_bolometric_fraction": summary[
                "input_boundary_bolometric_fraction"
            ],
            "input_state_path": input_relative,
            "input_state_sha256": summary["output_state_sha256"],
            "output_state_path": spec.output_state_path,
            "output_state_previous_sha256": common.sha256(output_state),
            "raw_float64_checkpoint_size_bytes": input_state.stat().st_size,
            "manifest_path": spec.manifest_path,
            "report_directory": spec.report_directory,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "block_report_prefix": spec.block_report_prefix,
            "runner_path": spec.runner_path,
            **common.numerical_repair_prohibitions(sequence=False),
        },
        "gates": common.consecutive_confirmation_gates(),
        "authorization": {
            "assemble_formal_h_he_feedback_pair_only_if_all_gates_pass": True,
            "accept_finite_trial_as_nonlinear_step": False,
            "accept_dynamic_nlte_solution": False,
            "full_orbit": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
    }
