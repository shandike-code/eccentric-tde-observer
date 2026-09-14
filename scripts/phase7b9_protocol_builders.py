"""Phase 7B9：固定门槛的候选映射、锚点与两步 Picard 协议 builder。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path


PHYSICAL_FREQUENCY_GROUPS = 9632
ANGULAR_DIRECTION_COUNT = 32
RADIATION_DEPTH_CELL_COUNT = 4096
NATURAL_FREQUENCY_BLOCK_COUNT = 76
MAXIMUM_CONCURRENT_PROCESSES = 3
# 后续高内存全频率映射固定留出更大的系统内存余量。
MEMORY_SAFE_HEAVY_MAXIMUM_CONCURRENT_PROCESSES = 2

FINITE_TRIAL_PROTOCOL = "outputs/phase7b9i_preregistered_finite_trial_radiation.json"
FINITE_TRIAL_MATERIAL = "outputs/phase7b9i_finite_trial_material_state.npz"
MASTER_INPUT = "outputs/phase7b5p_master_worker_input.npz"
GENERIC_MAP_RUNNER = "scripts/phase7b9ac_global_positive_picard_map.py"
POSITIVE_SEQUENCE_ENGINE = "scripts/phase7b9al_positive_picard_convergence.py"
SEEDED_PICARD_RUNNER = "scripts/phase7b9_seeded_picard.py"
MEMORY_REDUCED_PICARD_RUNNER = "scripts/phase7b9_memory_reduced_picard.py"
MAP_WORKER = "scripts/phase7b7i_second_radiation_map.py"
WORKER_HELPERS = "scripts/phase7b9d_inner_converged_base_radiation.py"
MIXED_FRAME_OPERATOR = "src/eccentric_tde_observer/mixed_frame_ale.py"
MIXED_FRAME_FREQUENCY = "src/eccentric_tde_observer/mixed_frame_frequency.py"
CHECKPOINT_COPY_RUNNER = "scripts/phase7b9_checkpoint_copy.py"
NEW_CHECKPOINT_COPY_RUNNER = "scripts/phase7b9_new_checkpoint_copy.py"
SLOW_MODE_RUNNER = "scripts/phase7b9bx_slow_mode_anderson.py"
SLOW_MODE_PROTOCOL_BUILDER = "scripts/phase7b9_preregister_slow_mode_anderson.py"
RADIATIVE_TRANSFER_QUADRATURE = (
    "src/eccentric_tde_observer/radiative_transfer_1d.py"
)

MEMORY_REDUCED_WORKER_SOURCE_KEYS = (
    "finite_trial_protocol",
    "finite_trial_material",
    "phase7b5p_master_input",
    "generic_positive_picard_runner",
    "positive_sequence_engine",
    "phase7b7i_worker",
    "phase7b9d_worker_helpers",
    "mixed_frame_operator",
    "mixed_frame_frequency",
)


@dataclass(frozen=True)
class CandidateMapProtocolSpec:
    phase: str
    phase_index: int
    classification: str
    candidate_summary_path: str
    candidate_protocol_path: str
    candidate_summary_source_key: str
    candidate_protocol_source_key: str
    output_state_path: str
    manifest_path: str
    report_directory: str
    summary_path: str
    figure_path: str
    block_report_prefix: str
    runner_path: str


@dataclass(frozen=True)
class MemorySafeCandidateMapProtocolSpec(CandidateMapProtocolSpec):
    """未来2-worker候选整图协议；与历史3-worker协议类型分离。"""


@dataclass(frozen=True)
class AnchorCopyProtocolSpec:
    phase: str
    phase_index: int
    classification: str
    mapped_summary_path: str
    mapped_protocol_path: str
    mapped_summary_source_key: str
    mapped_protocol_source_key: str
    mapped_source_state_key: str
    target_state_path: str
    summary_path: str
    postcopy_authorization_key: str


@dataclass(frozen=True)
class SeededTwoMapPicardProtocolSpec:
    phase: str
    phase_index: int
    classification: str
    mapped_summary_path: str
    mapped_protocol_path: str
    mapped_summary_source_key: str
    mapped_protocol_source_key: str
    anchor_summary_path: str
    anchor_protocol_path: str
    anchor_summary_source_key: str
    anchor_protocol_source_key: str
    anchor_continuation_decision_key: str
    scratch_state_path: str
    manifest_path: str
    report_directory: str
    summary_path: str
    figure_path: str
    runner_path: str
    slow_mode_after_pause_authorization_key: str


@dataclass(frozen=True)
class SequencePicardContinuationProtocolSpec:
    phase: str
    phase_index: int
    classification: str
    sequence_summary_path: str
    sequence_protocol_path: str
    rejected_anderson_summary_path: str
    rejected_anderson_protocol_path: str
    scratch_state_path: str
    maximum_total_picard_maps: int
    manifest_path: str
    report_directory: str
    summary_path: str
    figure_path: str
    runner_path: str


@dataclass(frozen=True)
class ConsecutiveConvergenceConfirmationProtocolSpec:
    phase: str
    phase_index: int
    classification: str
    sequence_summary_path: str
    sequence_manifest_path: str
    sequence_protocol_path: str
    trial_residual_acceptance_path: str
    output_state_path: str
    manifest_path: str
    report_directory: str
    summary_path: str
    figure_path: str
    block_report_prefix: str
    runner_path: str


@dataclass(frozen=True)
class SequenceTailAnchorProtocolSpec:
    phase: str
    phase_index: int
    classification: str
    sequence_summary_path: str
    sequence_protocol_path: str
    target_state_path: str
    summary_path: str
    postcopy_authorization_key: str


@dataclass(frozen=True)
class TailTwoMapPicardProtocolSpec:
    phase: str
    phase_index: int
    classification: str
    sequence_summary_path: str
    sequence_protocol_path: str
    anchor_summary_path: str
    anchor_protocol_path: str
    anchor_continuation_decision_key: str
    scratch_state_path: str
    manifest_path: str
    report_directory: str
    summary_path: str
    figure_path: str
    runner_path: str
    tail_anderson_authorization_key: str


@dataclass(frozen=True)
class ProtectedAndersonTailProtocolSpec:
    phase: str
    phase_index: int
    classification: str
    continuation_summary_path: str
    continuation_protocol_path: str
    anchor_summary_path: str
    anchor_protocol_path: str
    anchor_continuation_decision_key: str
    candidate_output_path: str
    summary_path: str
    figure_path: str


@dataclass(frozen=True)
class MemoryReducedPicardContinuationProtocolSpec:
    phase: str
    phase_index: int
    classification: str
    interrupted_protocol_path: str
    interrupted_manifest_path: str
    manifest_path: str
    report_directory: str
    summary_path: str
    figure_path: str
    runner_path: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def source_entry(root: Path, relative_path: str) -> dict[str, object]:
    path = root / relative_path
    return {
        "path": relative_path,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def read_json(root: Path, relative_path: str) -> dict[str, object]:
    return json.loads((root / relative_path).read_text(encoding="utf-8"))


def numerical_repair_prohibitions(*, sequence: bool) -> dict[str, bool]:
    prohibitions = {
        "cellwise_clipping": False,
        "nan_to_num": False,
        "intensity_floor": False,
        "point_deletion": False,
        "posthoc_renormalization": False,
    }
    prohibitions[
        "matter_feedback_during_sequence" if sequence else "matter_feedback_during_map"
    ] = False
    return prohibitions


def candidate_map_gates() -> dict[str, object]:
    return {
        "block_count_exactly": 76,
        "owned_frequency_group_count_exactly": 9632,
        "each_frequency_group_owned_exactly_once": True,
        "minimum_input_and_mapped_intensity_at_least": 0.0,
        "input_global_residual_matches_phase7b9ab_absolute_tolerance": 2.0e-12,
        "input_boundary_metrics_match_phase7b9ab_absolute_tolerance": 2.0e-12,
        "each_process_peak_rss_strictly_below_mib": 6144.0,
        "full_map_wall_time_strictly_below_s": 1200.0,
    }


def memory_safe_candidate_map_gates() -> dict[str, object]:
    """只按固定 worker 数比例放宽 wall-time 资源门。"""

    gates = candidate_map_gates()
    gates["full_map_wall_time_strictly_below_s"] = 1200.0 * (3.0 / 2.0)
    return gates


def anchor_copy_gates() -> dict[str, bool]:
    return {
        "target_sha256_must_equal_source_sha256": True,
        "source_and_target_size_equal": True,
    }


def seeded_two_map_gates() -> dict[str, object]:
    return {
        "block_count_exactly": 76,
        "owned_frequency_group_count_exactly": 9632,
        "minimum_input_and_mapped_intensity_at_least": 0.0,
        "initial_audit_absolute_tolerance": 2.0e-12,
        "global_original_operator_residual_below": 1.0e-4,
        "subsequent_residual_contraction_ratio_below": 1.01,
        "global_boundary_spectrum_l1_below": 1.0e-3,
        "global_boundary_bolometric_fraction_below": 1.0e-3,
        "each_process_peak_rss_strictly_below_mib": 6144.0,
        "each_worker_wall_time_strictly_below_s": 60.0,
        "each_full_map_wall_time_strictly_below_s": 1200.0,
    }


def memory_safe_seeded_two_map_gates() -> dict[str, object]:
    """保持全部科学门，仅按3/2缩放整图 wall-time 资源门。"""

    gates = seeded_two_map_gates()
    gates["each_full_map_wall_time_strictly_below_s"] = 1200.0 * (3.0 / 2.0)
    return gates


def memory_safe_resource_provenance() -> dict[str, object]:
    return {
        "classification": "[A-resource]",
        "baseline_maximum_concurrent_processes": 3,
        "memory_safe_maximum_concurrent_processes": 2,
        "baseline_full_map_wall_time_strictly_below_s": 1200.0,
        "worker_count_scale_factor": 3.0 / 2.0,
        "memory_safe_full_map_wall_time_strictly_below_s": 1800.0,
        "threshold_from_observed": False,
        "scientific_gate_changed": False,
    }


def consecutive_confirmation_gates() -> dict[str, object]:
    return {
        "block_count_exactly": 76,
        "owned_frequency_group_count_exactly": 9632,
        "minimum_input_and_mapped_intensity_at_least": 0.0,
        "both_global_original_operator_residuals_below": 1.0e-4,
        "both_boundary_spectrum_l1_below": 1.0e-3,
        "both_boundary_bolometric_fraction_below": 1.0e-3,
        "each_process_peak_rss_strictly_below_mib": 6144.0,
        "full_map_wall_time_strictly_below_s": 1200.0,
    }


def protected_anderson_tail_gates() -> dict[str, object]:
    """保持既有 protected Anderson(1) 的冻结门槛。"""

    return {
        "difference_norm_squared_to_x9_residual_norm_squared_above": 1.0e-12,
        "selected_forward_picard_fraction_strictly_above": 1.0,
        "coefficient_l1_norm_strictly_below": 192.0,
        "predicted_global_residual_ratio_to_x10_below": 0.99,
        "global_boundary_spectrum_l1_below": 1.0e-3,
        "global_boundary_bolometric_fraction_below": 1.0e-3,
        "minimum_candidate_and_predicted_map_intensity_at_least": 0.0,
        "write_wall_time_strictly_below_s": 900.0,
    }


def _passed_unconverged_sequence(
    root: Path,
    summary_path: str,
    protocol_path: str,
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    """验证耗尽、全通过但尚未达标的 sequence 及其完整链。"""

    sequence = read_json(root, summary_path)
    protocol = read_json(root, protocol_path)
    decision = sequence.get("decision", {})
    if (
        sequence.get("status") != "maximum_maps_exhausted"
        or decision.get("positive_picard_sequence_converged") is not False
        or decision.get("audited_radiation_state_accepted") is not False
        or decision.get("material_feedback_authorized") is not False
        or decision.get("dynamic_nlte_solution_accepted") is not False
        or sequence.get("protocol_sha256") != sha256(root / protocol_path)
    ):
        raise RuntimeError("tail preparation requires an exhausted unconverged sequence")
    iterations = sequence.get("iterations")
    if not isinstance(iterations, list) or not iterations:
        raise RuntimeError("tail preparation requires a non-empty sequence")
    if (
        int(sequence.get("completed_picard_maps", -1)) != len(iterations)
        or int(protocol.get("configuration", {}).get("maximum_picard_maps", -1))
        != len(iterations)
        or any(record.get("map_passed") is not True for record in iterations)
    ):
        raise RuntimeError("tail sequence length or map gates changed")
    for index, record in enumerate(iterations):
        if int(record.get("iteration", -1)) != index:
            raise RuntimeError("tail sequence iteration numbering changed")
        if index and (
            record.get("input_state_path")
            != iterations[index - 1].get("mapped_state_path")
            or record.get("input_state_sha256")
            != iterations[index - 1].get("mapped_state_sha256")
        ):
            raise RuntimeError("tail sequence mapped/input chain changed")
    final = iterations[-1]
    if float(final["global_original_operator_residual"]) < 1.0e-4:
        raise RuntimeError("sequence is already below the fixed residual target")
    final_path = root / str(final["mapped_state_path"])
    if sha256(final_path) != final.get("mapped_state_sha256"):
        raise RuntimeError("tail sequence last mapped state hash changed")
    return sequence, protocol, iterations


def build_candidate_map_protocol(
    root: Path, spec: CandidateMapProtocolSpec
) -> dict[str, object]:
    """构造单次受保护候选的完整原算子映射协议，不执行映射。"""
    candidate = read_json(root, spec.candidate_summary_path)
    decision = candidate["decision"]
    if (
        decision["protected_slow_mode_candidate_passed"] is not True
        or decision["fresh_original_operator_map_authorized"] is not True
        or decision["material_feedback_authorized"] is not False
    ):
        raise RuntimeError("candidate map requires a passed protected slow-mode state")
    input_relative = str(candidate["candidate_state_path"])
    input_state = root / input_relative
    output_state = root / spec.output_state_path
    if sha256(input_state) != candidate["candidate_state_sha256"]:
        raise RuntimeError("candidate checkpoint hash changed")
    if output_state.stat().st_size != input_state.stat().st_size:
        raise RuntimeError("candidate-map output scratch size is invalid")
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            spec.candidate_summary_source_key: source_entry(
                root, spec.candidate_summary_path
            ),
            spec.candidate_protocol_source_key: source_entry(
                root, spec.candidate_protocol_path
            ),
            "input_state": source_entry(root, input_relative),
            "finite_trial_protocol": source_entry(root, FINITE_TRIAL_PROTOCOL),
            "finite_trial_material": source_entry(root, FINITE_TRIAL_MATERIAL),
            "phase7b5p_master_input": source_entry(root, MASTER_INPUT),
            "generic_map_runner": source_entry(root, GENERIC_MAP_RUNNER),
            "phase7b7i_worker": source_entry(root, MAP_WORKER),
            "phase7b9d_worker_helpers": source_entry(root, WORKER_HELPERS),
            "mixed_frame_operator": source_entry(root, MIXED_FRAME_OPERATOR),
            "mixed_frame_frequency": source_entry(root, MIXED_FRAME_FREQUENCY),
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": PHYSICAL_FREQUENCY_GROUPS,
            "angular_direction_count": ANGULAR_DIRECTION_COUNT,
            "radiation_depth_cell_count": RADIATION_DEPTH_CELL_COUNT,
            "natural_frequency_block_count": NATURAL_FREQUENCY_BLOCK_COUNT,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "accepted_source_relaxation_exactly": 1.0,
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "maximum_concurrent_processes": MAXIMUM_CONCURRENT_PROCESSES,
            "input_state_path": input_relative,
            "input_state_sha256": candidate["candidate_state_sha256"],
            "output_state_path": spec.output_state_path,
            "output_state_previous_sha256": sha256(output_state),
            "raw_float64_checkpoint_size_bytes": input_state.stat().st_size,
            "manifest_path": spec.manifest_path,
            "report_directory": spec.report_directory,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "block_report_prefix": spec.block_report_prefix,
            "runner_path": spec.runner_path,
            "input_audit_source_key": spec.candidate_summary_source_key,
            "input_audit_residual_key": "predicted_global_original_operator_residual",
            "input_audit_boundary_l1_key": "predicted_boundary_spectrum_l1",
            "input_audit_bolometric_key": "predicted_boundary_bolometric_fraction",
            **numerical_repair_prohibitions(sequence=False),
        },
        "gates": candidate_map_gates(),
        "authorization": {
            "overwrite_only_named_superseded_checkpoint": True,
            "commit_recoverable_mapped_state_if_all_map_gates_pass": True,
            "continue_accelerated_iteration_if_above_target": True,
            "second_consecutive_original_residual_required_if_below_target": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }


def build_memory_safe_candidate_map_protocol(
    root: Path, spec: MemorySafeCandidateMapProtocolSpec
) -> dict[str, object]:
    """构造未来2-worker候选整图协议，不改变历史候选 builder。"""

    payload = build_candidate_map_protocol(root, spec)
    payload["configuration"]["maximum_concurrent_processes"] = (
        MEMORY_SAFE_HEAVY_MAXIMUM_CONCURRENT_PROCESSES
    )
    payload["gates"] = memory_safe_candidate_map_gates()
    payload["resource_gate_provenance"] = memory_safe_resource_provenance()
    return payload


def build_anchor_copy_protocol(
    root: Path, spec: AnchorCopyProtocolSpec
) -> dict[str, object]:
    """构造字节等同锚点副本协议，不执行复制。"""
    mapped = read_json(root, spec.mapped_summary_path)
    if mapped["decision"]["global_positive_picard_map_passed"] is not True:
        raise RuntimeError("anchor copy requires an audited candidate map")
    source_relative = str(mapped["output_state_path"])
    source = root / source_relative
    target = root / spec.target_state_path
    if sha256(source) != mapped["output_state_sha256"]:
        raise RuntimeError("mapped source checkpoint hash changed")
    if source.stat().st_size != target.stat().st_size:
        raise RuntimeError("anchor source/target size changed")
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            spec.mapped_summary_source_key: source_entry(
                root, spec.mapped_summary_path
            ),
            spec.mapped_protocol_source_key: source_entry(
                root, spec.mapped_protocol_path
            ),
            spec.mapped_source_state_key: source_entry(root, source_relative),
            "checkpoint_copy_runner": source_entry(root, CHECKPOINT_COPY_RUNNER),
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "shape": [
                PHYSICAL_FREQUENCY_GROUPS,
                ANGULAR_DIRECTION_COUNT,
                RADIATION_DEPTH_CELL_COUNT,
            ],
            "copy_frequency_chunk": 32,
            "source_state_path": source_relative,
            "source_state_sha256": mapped["output_state_sha256"],
            "target_state_path": spec.target_state_path,
            "target_state_previous_sha256": sha256(target),
            "summary_path": spec.summary_path,
            "postcopy_authorization_key": spec.postcopy_authorization_key,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": anchor_copy_gates(),
        "authorization": {
            "overwrite_only_named_superseded_checkpoint": True,
            "run_exactly_two_new_picard_maps": True,
            "material_feedback": False,
        },
    }


def build_seeded_two_map_picard_protocol(
    root: Path, spec: SeededTwoMapPicardProtocolSpec
) -> dict[str, object]:
    """构造映射态播种的两步 Picard 协议，不执行 Picard 映射。"""
    mapped = read_json(root, spec.mapped_summary_path)
    anchor = read_json(root, spec.anchor_summary_path)
    if (
        mapped["decision"]["global_positive_picard_map_passed"] is not True
        or anchor["decision"][spec.anchor_continuation_decision_key] is not True
        or anchor["anchor_state_sha256"] != mapped["output_state_sha256"]
    ):
        raise RuntimeError("seeded Picard requires an audited map and matching anchor")
    immutable_relative = str(anchor["anchor_state_path"])
    initial_relative = str(mapped["output_state_path"])
    immutable = root / immutable_relative
    initial = root / initial_relative
    scratch = root / spec.scratch_state_path
    if (
        sha256(immutable) != anchor["anchor_state_sha256"]
        or sha256(initial) != mapped["output_state_sha256"]
        or immutable.stat().st_size != initial.stat().st_size
        or immutable.stat().st_size != scratch.stat().st_size
    ):
        raise RuntimeError("seeded Picard checkpoint chain changed")
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            spec.mapped_summary_source_key: source_entry(
                root, spec.mapped_summary_path
            ),
            spec.mapped_protocol_source_key: source_entry(
                root, spec.mapped_protocol_path
            ),
            spec.anchor_summary_source_key: source_entry(
                root, spec.anchor_summary_path
            ),
            spec.anchor_protocol_source_key: source_entry(
                root, spec.anchor_protocol_path
            ),
            "immutable_mapped_anchor": source_entry(root, immutable_relative),
            "finite_trial_protocol": source_entry(root, FINITE_TRIAL_PROTOCOL),
            "finite_trial_material": source_entry(root, FINITE_TRIAL_MATERIAL),
            "phase7b5p_master_input": source_entry(root, MASTER_INPUT),
            "generic_positive_picard_runner": source_entry(
                root, GENERIC_MAP_RUNNER
            ),
            "positive_sequence_engine": source_entry(
                root, POSITIVE_SEQUENCE_ENGINE
            ),
            "seeded_picard_runner": source_entry(root, SEEDED_PICARD_RUNNER),
            "phase7b7i_worker": source_entry(root, MAP_WORKER),
            "phase7b9d_worker_helpers": source_entry(root, WORKER_HELPERS),
            "mixed_frame_operator": source_entry(root, MIXED_FRAME_OPERATOR),
            "mixed_frame_frequency": source_entry(root, MIXED_FRAME_FREQUENCY),
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": PHYSICAL_FREQUENCY_GROUPS,
            "angular_direction_count": ANGULAR_DIRECTION_COUNT,
            "radiation_depth_cell_count": RADIATION_DEPTH_CELL_COUNT,
            "natural_frequency_block_count": NATURAL_FREQUENCY_BLOCK_COUNT,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_picard_maps": 3,
            "maximum_concurrent_processes": MAXIMUM_CONCURRENT_PROCESSES,
            "stop_after_iteration": 2,
            "seed_summary_source_key": spec.mapped_summary_source_key,
            "seed_summary_format": "global_map",
            "seed_iteration_count": 1,
            "immutable_anchor_path": immutable_relative,
            "immutable_anchor_sha256": anchor["anchor_state_sha256"],
            "initial_state_path": initial_relative,
            "initial_state_sha256": mapped["output_state_sha256"],
            "scratch_state_path": spec.scratch_state_path,
            "scratch_state_initial_sha256": sha256(scratch),
            "raw_float64_checkpoint_size_bytes": initial.stat().st_size,
            "manifest_path": spec.manifest_path,
            "report_directory": spec.report_directory,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "runner_path": spec.runner_path,
            **numerical_repair_prohibitions(sequence=True),
        },
        "reference": {
            "initial_global_residual": mapped[
                "input_global_original_operator_residual"
            ],
            "initial_boundary_spectrum_l1": mapped["input_boundary_spectrum_l1"],
            "initial_boundary_bolometric_fraction": mapped[
                "input_boundary_bolometric_fraction"
            ],
        },
        "gates": seeded_two_map_gates(),
        "authorization": {
            "seed_manifest_from_independently_audited_map": True,
            "alternate_only_named_generated_buffers": True,
            "run_exactly_two_new_picard_maps": True,
            spec.slow_mode_after_pause_authorization_key: True,
            "material_feedback_only_after_convergence": True,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
    }


def build_sequence_picard_continuation_protocol(
    root: Path, spec: SequencePicardContinuationProtocolSpec
) -> dict[str, object]:
    """从已审计 sequence 的末态构造纯 Picard 延拓协议，不执行映射。"""
    sequence = read_json(root, spec.sequence_summary_path)
    sequence_protocol = read_json(root, spec.sequence_protocol_path)
    rejected = read_json(root, spec.rejected_anderson_summary_path)
    if sequence.get("status") != "maximum_maps_exhausted":
        raise RuntimeError("sequence continuation requires maximum_maps_exhausted")
    iterations = sequence.get("iterations")
    if not isinstance(iterations, list) or not iterations:
        raise RuntimeError("sequence continuation requires a non-empty map history")
    if any(record.get("map_passed") is not True for record in iterations):
        raise RuntimeError("sequence continuation requires every prior map to pass")
    if int(sequence.get("completed_picard_maps", -1)) != len(iterations):
        raise RuntimeError("sequence completed-map count changed")
    if int(sequence_protocol["configuration"]["maximum_picard_maps"]) != len(
        iterations
    ):
        raise RuntimeError("maximum_maps_exhausted sequence length changed")
    if sequence.get("protocol_sha256") != sha256(root / spec.sequence_protocol_path):
        raise RuntimeError("sequence protocol hash changed")
    for index, record in enumerate(iterations):
        if int(record.get("iteration", -1)) != index:
            raise RuntimeError("sequence iteration numbering changed")
        if index and (
            record.get("input_state_path")
            != iterations[index - 1].get("mapped_state_path")
            or record.get("input_state_sha256")
            != iterations[index - 1].get("mapped_state_sha256")
        ):
            raise RuntimeError("sequence mapped/input chain changed")
    rejected_decision = rejected.get("decision", {})
    if (
        rejected_decision.get("protected_slow_mode_candidate_passed") is not False
        or rejected_decision.get("fresh_original_operator_map_authorized") is not False
        or rejected_decision.get("resume_phase7b9bt_authorized") is not True
        or rejected_decision.get("material_feedback_authorized") is not False
        or rejected.get("protocol_sha256")
        != sha256(root / spec.rejected_anderson_protocol_path)
    ):
        raise RuntimeError("rejected Anderson evidence does not authorize pure Picard")
    if spec.maximum_total_picard_maps <= len(iterations):
        raise ValueError("maximum total Picard maps must exceed the seeded map count")

    last = iterations[-1]
    initial_relative = str(last["mapped_state_path"])
    initial = root / initial_relative
    if sha256(initial) != last["mapped_state_sha256"]:
        raise RuntimeError("last mapped state hash changed")
    prior_configuration = sequence_protocol["configuration"]
    immutable_relative = str(prior_configuration["immutable_anchor_path"])
    immutable = root / immutable_relative
    if immutable_relative == initial_relative:
        raise RuntimeError("immutable sequence anchor must differ from the last mapped state")
    if sha256(immutable) != prior_configuration["immutable_anchor_sha256"]:
        raise RuntimeError("immutable sequence anchor hash changed")
    scratch = root / spec.scratch_state_path
    if (
        immutable.stat().st_size != initial.stat().st_size
        or immutable.stat().st_size != scratch.stat().st_size
    ):
        raise RuntimeError("sequence continuation state sizes changed")
    if spec.scratch_state_path in {immutable_relative, initial_relative}:
        raise RuntimeError("sequence continuation scratch must be a distinct buffer")
    scratch_hash = sha256(scratch)

    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            "sequence_summary": source_entry(root, spec.sequence_summary_path),
            "sequence_protocol": source_entry(root, spec.sequence_protocol_path),
            "rejected_anderson_summary": source_entry(
                root, spec.rejected_anderson_summary_path
            ),
            "rejected_anderson_protocol": source_entry(
                root, spec.rejected_anderson_protocol_path
            ),
            "immutable_mapped_anchor": source_entry(root, immutable_relative),
            "finite_trial_protocol": source_entry(root, FINITE_TRIAL_PROTOCOL),
            "finite_trial_material": source_entry(root, FINITE_TRIAL_MATERIAL),
            "phase7b5p_master_input": source_entry(root, MASTER_INPUT),
            "generic_positive_picard_runner": source_entry(
                root, GENERIC_MAP_RUNNER
            ),
            "positive_sequence_engine": source_entry(
                root, POSITIVE_SEQUENCE_ENGINE
            ),
            "seeded_picard_runner": source_entry(root, SEEDED_PICARD_RUNNER),
            "phase7b7i_worker": source_entry(root, MAP_WORKER),
            "phase7b9d_worker_helpers": source_entry(root, WORKER_HELPERS),
            "mixed_frame_operator": source_entry(root, MIXED_FRAME_OPERATOR),
            "mixed_frame_frequency": source_entry(root, MIXED_FRAME_FREQUENCY),
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": PHYSICAL_FREQUENCY_GROUPS,
            "angular_direction_count": ANGULAR_DIRECTION_COUNT,
            "radiation_depth_cell_count": RADIATION_DEPTH_CELL_COUNT,
            "natural_frequency_block_count": NATURAL_FREQUENCY_BLOCK_COUNT,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_picard_maps": spec.maximum_total_picard_maps,
            "maximum_concurrent_processes": MAXIMUM_CONCURRENT_PROCESSES,
            "stop_after_iteration": spec.maximum_total_picard_maps - 1,
            "seed_summary_source_key": "sequence_summary",
            "seed_summary_format": "sequence",
            "seed_iteration_count": len(iterations),
            "immutable_anchor_path": immutable_relative,
            "immutable_anchor_sha256": prior_configuration[
                "immutable_anchor_sha256"
            ],
            "initial_state_path": initial_relative,
            "initial_state_sha256": last["mapped_state_sha256"],
            "scratch_state_path": spec.scratch_state_path,
            "scratch_state_initial_sha256": scratch_hash,
            "raw_float64_checkpoint_size_bytes": initial.stat().st_size,
            "manifest_path": spec.manifest_path,
            "report_directory": spec.report_directory,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "runner_path": spec.runner_path,
            **numerical_repair_prohibitions(sequence=True),
        },
        "reference": {
            "initial_global_residual": last["global_original_operator_residual"],
            "initial_boundary_spectrum_l1": last["boundary_spectrum_l1"],
            "initial_boundary_bolometric_fraction": last[
                "boundary_bolometric_fraction"
            ],
        },
        "gates": seeded_two_map_gates(),
        "authorization": {
            "seed_manifest_from_audited_sequence": True,
            "resume_pure_picard_after_rejected_anderson": True,
            "rejected_anderson_candidate_used": False,
            "alternate_only_named_generated_buffers": True,
            "material_feedback_only_after_convergence": True,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
    }


def build_consecutive_convergence_confirmation_protocol(
    root: Path, spec: ConsecutiveConvergenceConfirmationProtocolSpec
) -> dict[str, object]:
    """构造第二个连续低残差态的确认协议，不执行原算子映射。"""
    summary = read_json(root, spec.sequence_summary_path)
    manifest = read_json(root, spec.sequence_manifest_path)
    acceptance = read_json(root, spec.trial_residual_acceptance_path)
    protocol_hash = sha256(root / spec.sequence_protocol_path)
    if (
        summary.get("status") != "complete"
        or summary.get("protocol_sha256") != protocol_hash
        or summary.get("decision", {}).get("positive_picard_sequence_converged")
        is not True
        or summary.get("decision", {}).get("material_feedback_authorized")
        is not True
        or manifest.get("status") != "complete"
        or manifest.get("protocol_sha256") != protocol_hash
    ):
        raise RuntimeError("confirmation requires one completed fixed-matter sequence")
    iterations = manifest.get("iterations")
    if not isinstance(iterations, list) or not iterations:
        raise RuntimeError("confirmation requires a non-empty audited map history")
    if any(record.get("map_passed") is not True for record in iterations):
        raise RuntimeError("confirmation requires every prior map to pass")
    summary_iterations = summary.get("iterations")
    if (
        not isinstance(summary_iterations, list)
        or summary_iterations != iterations
    ):
        raise RuntimeError("sequence summary/manifest lineage changed")

    acceptance_gates = acceptance.get("gates", {})
    acceptance_authorization = acceptance.get("authorization", {})
    if (
        acceptance_authorization.get(
            "accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass"
        )
        is not True
        or acceptance_authorization.get("accept_dynamic_nlte_solution") is not False
        or int(
            acceptance_gates.get(
                "consecutive_inner_radiation_state_count_at_least", -1
            )
        )
        != 2
        or acceptance_gates.get(
            "each_global_original_operator_residual_below"
        )
        != 1.0e-4
        or acceptance_gates.get("each_boundary_spectrum_l1_below") != 1.0e-3
        or acceptance_gates.get("each_boundary_bolometric_fraction_below")
        != 1.0e-3
        or acceptance_gates.get("each_formal_feedback_state_gate_passed")
        is not True
    ):
        raise RuntimeError("trial residual acceptance is incompatible with confirmation")

    final_record = iterations[-1]
    if (
        final_record.get("input_state_path") != manifest.get("accepted_state_path")
        or final_record.get("input_state_sha256")
        != manifest.get("accepted_state_sha256")
        or float(final_record["global_original_operator_residual"]) >= 1.0e-4
        or float(final_record["boundary_spectrum_l1"]) >= 1.0e-3
        or float(final_record["boundary_bolometric_fraction"]) >= 1.0e-3
        or final_record.get("map_passed") is not True
    ):
        raise RuntimeError("first converged fixed-matter state lineage changed")
    input_relative = str(final_record["mapped_state_path"])
    input_state = root / input_relative
    output_state = root / spec.output_state_path
    if sha256(input_state) != final_record["mapped_state_sha256"]:
        raise RuntimeError("mapped successor hash changed")
    if input_state.stat().st_size != output_state.stat().st_size:
        raise RuntimeError("confirmation input/output buffer size changed")
    if input_relative == spec.output_state_path:
        raise RuntimeError("confirmation output must be distinct from its input")

    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            "sequence_summary": source_entry(root, spec.sequence_summary_path),
            "sequence_manifest": source_entry(root, spec.sequence_manifest_path),
            "sequence_protocol": source_entry(root, spec.sequence_protocol_path),
            "trial_residual_acceptance": source_entry(
                root, spec.trial_residual_acceptance_path
            ),
            "input_state": source_entry(root, input_relative),
            "finite_trial_protocol": source_entry(root, FINITE_TRIAL_PROTOCOL),
            "finite_trial_material": source_entry(root, FINITE_TRIAL_MATERIAL),
            "phase7b5p_master_input": source_entry(root, MASTER_INPUT),
            "generic_map_runner": source_entry(root, GENERIC_MAP_RUNNER),
            "phase7b7i_worker": source_entry(root, MAP_WORKER),
            "phase7b9d_worker_helpers": source_entry(root, WORKER_HELPERS),
            "mixed_frame_operator": source_entry(root, MIXED_FRAME_OPERATOR),
            "mixed_frame_frequency": source_entry(root, MIXED_FRAME_FREQUENCY),
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": PHYSICAL_FREQUENCY_GROUPS,
            "angular_direction_count": ANGULAR_DIRECTION_COUNT,
            "radiation_depth_cell_count": RADIATION_DEPTH_CELL_COUNT,
            "natural_frequency_block_count": NATURAL_FREQUENCY_BLOCK_COUNT,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "accepted_source_relaxation_exactly": 1.0,
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "maximum_concurrent_processes": (
                MEMORY_SAFE_HEAVY_MAXIMUM_CONCURRENT_PROCESSES
            ),
            "previous_converged_state_path": final_record["input_state_path"],
            "previous_converged_state_sha256": final_record["input_state_sha256"],
            "previous_global_original_operator_residual": final_record[
                "global_original_operator_residual"
            ],
            "previous_boundary_spectrum_l1": final_record[
                "boundary_spectrum_l1"
            ],
            "previous_boundary_bolometric_fraction": final_record[
                "boundary_bolometric_fraction"
            ],
            "input_state_path": input_relative,
            "input_state_sha256": final_record["mapped_state_sha256"],
            "output_state_path": spec.output_state_path,
            "output_state_previous_sha256": sha256(output_state),
            "raw_float64_checkpoint_size_bytes": input_state.stat().st_size,
            "manifest_path": spec.manifest_path,
            "report_directory": spec.report_directory,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "block_report_prefix": spec.block_report_prefix,
            "runner_path": spec.runner_path,
            **numerical_repair_prohibitions(sequence=False),
        },
        "gates": consecutive_confirmation_gates(),
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


def build_memory_reduced_picard_continuation_protocol(
    root: Path, spec: MemoryReducedPicardContinuationProtocolSpec
) -> dict[str, object]:
    """从未提交的 active map 前重启低内存 Picard，不读取检查点内容。"""

    protocol = read_json(root, spec.interrupted_protocol_path)
    manifest = read_json(root, spec.interrupted_manifest_path)
    protocol_hash = sha256(root / spec.interrupted_protocol_path)
    configuration = protocol.get("configuration", {})
    authorization = protocol.get("authorization", {})
    if (
        manifest.get("protocol_sha256") != protocol_hash
        or manifest.get("phase") != protocol.get("phase")
        or manifest.get("status") != "running"
    ):
        raise RuntimeError("memory-reduced continuation requires its running manifest")
    if (
        int(configuration.get("maximum_picard_maps", -1)) != 24
        or int(configuration.get("stop_after_iteration", -1)) != 23
        or int(configuration.get("maximum_concurrent_processes", -1)) != 3
        or configuration.get("seed_summary_format") != "sequence"
        or configuration.get("accepted_source_relaxation_exactly") != 1.0
        or configuration.get("diagnostic_fixed_iteration_count") != 1
        or configuration.get("source_map_only") is not True
        or protocol.get("gates") != seeded_two_map_gates()
        or any(
            configuration.get(name) != value
            for name, value in numerical_repair_prohibitions(sequence=True).items()
        )
    ):
        raise RuntimeError("interrupted Picard protocol physics or gates changed")
    if (
        authorization.get("seed_manifest_from_audited_sequence") is not True
        or authorization.get("resume_pure_picard_after_rejected_anderson") is not True
        or authorization.get("rejected_anderson_candidate_used") is not False
        or authorization.get("alternate_only_named_generated_buffers") is not True
        or authorization.get("material_feedback_only_after_convergence") is not True
        or authorization.get("accept_dynamic_nlte_solution") is not False
        or authorization.get("phase4_replacement") is not False
        or authorization.get("real_line_formation") is not False
    ):
        raise RuntimeError("interrupted Picard authorization changed")

    iterations = manifest.get("iterations")
    active = manifest.get("active_iteration")
    if not isinstance(iterations, list) or not iterations:
        raise RuntimeError("memory-reduced continuation needs completed iterations")
    if not isinstance(active, dict):
        raise RuntimeError("memory-reduced continuation needs one active iteration")
    if len(iterations) >= int(configuration["maximum_picard_maps"]):
        raise RuntimeError("interrupted sequence has no remaining map horizon")
    for index, record in enumerate(iterations):
        if (
            int(record.get("iteration", -1)) != index
            or record.get("map_passed") is not True
        ):
            raise RuntimeError("completed interrupted iterations are not all valid")
        if index and (
            record.get("input_state_path")
            != iterations[index - 1].get("mapped_state_path")
            or record.get("input_state_sha256")
            != iterations[index - 1].get("mapped_state_sha256")
        ):
            raise RuntimeError("completed interrupted iteration chain changed")

    seed_count = int(configuration.get("seed_iteration_count", -1))
    if seed_count <= 0 or seed_count > len(iterations):
        raise RuntimeError("interrupted Picard seed boundary changed")
    seed_tail = iterations[seed_count - 1]
    if (
        seed_tail.get("mapped_state_path")
        != configuration.get("initial_state_path")
        or seed_tail.get("mapped_state_sha256")
        != configuration.get("initial_state_sha256")
    ):
        raise RuntimeError("interrupted Picard seed lineage changed")

    final = iterations[-1]
    current_path = manifest.get("current_input_path")
    current_hash = manifest.get("current_input_sha256")
    next_output_path = manifest.get("next_output_path")
    if (
        current_path != final.get("mapped_state_path")
        or current_hash != final.get("mapped_state_sha256")
        or int(active.get("iteration", -1)) != len(iterations)
        or active.get("input_state_path") != current_path
        or active.get("input_state_sha256") != current_hash
        or active.get("output_state_path") != next_output_path
        or next_output_path != final.get("input_state_path")
        or current_path == next_output_path
        or active.get("committed") not in (None, False)
    ):
        raise RuntimeError("active map is not the uncommitted successor of the last map")

    completed_blocks = active.get("completed_blocks")
    if (
        not isinstance(completed_blocks, list)
        or not completed_blocks
        or len(completed_blocks) >= NATURAL_FREQUENCY_BLOCK_COUNT
    ):
        raise RuntimeError("active map must contain only an incomplete block prefix")
    expected_indices = list(range(len(completed_blocks)))
    if [record.get("block_index") for record in completed_blocks] != expected_indices:
        raise RuntimeError("active partial blocks must be one contiguous prefix")
    for index, record in enumerate(completed_blocks):
        expected_start = index * 128
        expected_stop = min((index + 1) * 128, PHYSICAL_FREQUENCY_GROUPS)
        if (
            record.get("protocol_sha256") != protocol_hash
            or int(record.get("picard_iteration", -1)) != len(iterations)
            or record.get("input_state_path") != current_path
            or record.get("input_state_sha256") != current_hash
            or record.get("output_state_path") != next_output_path
            or int(record.get("core_group_start", -1)) != expected_start
            or int(record.get("core_group_stop", -1)) != expected_stop
        ):
            raise RuntimeError("active partial block lineage changed")

    old_outputs = {
        str(configuration.get("manifest_path")),
        str(configuration.get("report_directory")),
        str(configuration.get("summary_path")),
        str(configuration.get("figure_path")),
    }
    new_outputs = {
        spec.manifest_path,
        spec.report_directory,
        spec.summary_path,
        spec.figure_path,
    }
    if old_outputs & new_outputs or len(new_outputs) != 4:
        raise RuntimeError("memory-reduced continuation outputs must be new paths")
    if spec.runner_path == configuration.get("runner_path"):
        raise RuntimeError("memory-reduced continuation requires a new frozen runner")

    inherited_sources: dict[str, dict[str, object]] = {}
    interrupted_sources = protocol.get("sources", {})
    for key in MEMORY_REDUCED_WORKER_SOURCE_KEYS:
        entry = interrupted_sources.get(key)
        if not isinstance(entry, dict):
            raise RuntimeError(f"interrupted Picard worker source is missing: {key}")
        relative_path = str(entry.get("path", ""))
        # 中文：只继承 worker 的小型科学输入与代码。
        # 10 GB 锚点不进入启动 source 校验。
        if relative_path.startswith("outputs/checkpoints/"):
            raise RuntimeError(
                f"worker source unexpectedly names a checkpoint: {key}"
            )
        current = source_entry(root, relative_path)
        if current != entry:
            raise RuntimeError(f"interrupted Picard worker source changed: {key}")
        inherited_sources[key] = dict(entry)

    runner_source = source_entry(root, MEMORY_REDUCED_PICARD_RUNNER)

    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            **inherited_sources,
            "interrupted_protocol": source_entry(
                root, spec.interrupted_protocol_path
            ),
            "interrupted_manifest": source_entry(
                root, spec.interrupted_manifest_path
            ),
            "memory_reduced_picard_runner": runner_source,
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": PHYSICAL_FREQUENCY_GROUPS,
            "angular_direction_count": ANGULAR_DIRECTION_COUNT,
            "radiation_depth_cell_count": RADIATION_DEPTH_CELL_COUNT,
            "natural_frequency_block_count": NATURAL_FREQUENCY_BLOCK_COUNT,
            "spatial_scheme": configuration["spatial_scheme"],
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_picard_maps": 24,
            "maximum_concurrent_processes": (
                MEMORY_SAFE_HEAVY_MAXIMUM_CONCURRENT_PROCESSES
            ),
            "stop_after_iteration": 23,
            "seed_summary_source_key": "interrupted_manifest",
            "seed_summary_format": "running_sequence_completed_only",
            "seed_iteration_count": len(iterations),
            "restart_picard_iteration": len(iterations),
            "immutable_anchor_path": configuration["immutable_anchor_path"],
            "immutable_anchor_sha256": configuration["immutable_anchor_sha256"],
            "initial_state_path": current_path,
            "initial_state_sha256": current_hash,
            "scratch_state_path": next_output_path,
            "scratch_state_initial_sha256": None,
            "scratch_state_is_uncommitted_partial": True,
            "scratch_state_content_hash_intentionally_not_read": True,
            "discard_interrupted_active_block_reports": True,
            "interrupted_partial_completed_block_count": len(completed_blocks),
            "restart_active_iteration_from_block_index": 0,
            "reuse_interrupted_partial_blocks": False,
            "overwrite_all_natural_frequency_blocks": True,
            "raw_float64_checkpoint_size_bytes": configuration[
                "raw_float64_checkpoint_size_bytes"
            ],
            "manifest_path": spec.manifest_path,
            "report_directory": spec.report_directory,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "runner_path": spec.runner_path,
            **numerical_repair_prohibitions(sequence=True),
        },
        "reference": {
            "interrupted_protocol_sha256": protocol_hash,
            "completed_picard_map_count": len(iterations),
            "last_completed_iteration": final["iteration"],
            "last_global_original_operator_residual": final[
                "global_original_operator_residual"
            ],
            "last_boundary_spectrum_l1": final["boundary_spectrum_l1"],
            "last_boundary_bolometric_fraction": final[
                "boundary_bolometric_fraction"
            ],
            "discarded_uncommitted_active_iteration": active["iteration"],
            "discarded_uncommitted_block_indices": expected_indices,
        },
        "gates": seeded_two_map_gates(),
        "authorization": {
            "seed_only_completed_iterations_from_interrupted_manifest": True,
            "discard_uncommitted_active_partial": True,
            "rerun_interrupted_iteration_from_first_block": True,
            "overwrite_only_declared_partial_scratch": True,
            "alternate_only_named_generated_buffers": True,
            "resume_original_total_map_horizon": True,
            "material_feedback_only_after_convergence": True,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
        "io_audit": {
            "checkpoint_dat_opened_by_builder": False,
            "checkpoint_dat_hashed_by_builder": False,
            "checkpoint_dat_modified_by_builder": False,
            "interrupted_manifest_modified_by_builder": False,
        },
    }


def build_sequence_tail_anchor_protocol(
    root: Path, spec: SequenceTailAnchorProtocolSpec
) -> dict[str, object]:
    """从未收敛 sequence 的末端 mapped state 构造 APFS 字节锚点协议。"""

    _, _, iterations = _passed_unconverged_sequence(
        root, spec.sequence_summary_path, spec.sequence_protocol_path
    )
    final = iterations[-1]
    source_relative = str(final["mapped_state_path"])
    source = root / source_relative
    target = root / spec.target_state_path
    if source_relative == spec.target_state_path:
        raise RuntimeError("tail anchor target must differ from its sequence source")
    target_previous_exists = target.exists()
    if target_previous_exists and (
        not target.is_file() or source.stat().st_size != target.stat().st_size
    ):
        raise RuntimeError("tail anchor source/target size changed")
    target_previous_sha256 = sha256(target) if target_previous_exists else None
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            "sequence_summary": source_entry(root, spec.sequence_summary_path),
            "sequence_protocol": source_entry(root, spec.sequence_protocol_path),
            "sequence_tail_mapped_state": source_entry(root, source_relative),
            "new_checkpoint_copy_runner": source_entry(
                root, NEW_CHECKPOINT_COPY_RUNNER
            ),
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "shape": [
                PHYSICAL_FREQUENCY_GROUPS,
                ANGULAR_DIRECTION_COUNT,
                RADIATION_DEPTH_CELL_COUNT,
            ],
            "copy_frequency_chunk": 32,
            "copy_strategy": "apfs_clone_then_sha256_verify",
            "source_state_path": source_relative,
            "source_state_sha256": final["mapped_state_sha256"],
            "target_state_path": spec.target_state_path,
            "target_previous_exists": target_previous_exists,
            "target_state_previous_sha256": target_previous_sha256,
            "raw_float64_checkpoint_size_bytes": source.stat().st_size,
            "source_sequence_iteration": final["iteration"],
            "summary_path": spec.summary_path,
            "postcopy_authorization_key": spec.postcopy_authorization_key,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": anchor_copy_gates(),
        "authorization": {
            "overwrite_only_named_superseded_checkpoint": True,
            "run_exactly_two_new_picard_maps": True,
            "material_feedback": False,
        },
    }


def build_tail_two_map_picard_protocol(
    root: Path, spec: TailTwoMapPicardProtocolSpec
) -> dict[str, object]:
    """以新锚点保护原末态，构造恰好两次纯 Picard 延拓协议。"""

    sequence, _, iterations = _passed_unconverged_sequence(
        root, spec.sequence_summary_path, spec.sequence_protocol_path
    )
    anchor = read_json(root, spec.anchor_summary_path)
    anchor_protocol_hash = sha256(root / spec.anchor_protocol_path)
    final = iterations[-1]
    if (
        anchor.get("protocol_sha256") != anchor_protocol_hash
        or anchor.get("source_state_path") != final.get("mapped_state_path")
        or anchor.get("source_state_sha256") != final.get("mapped_state_sha256")
        or anchor.get("anchor_state_sha256") != final.get("mapped_state_sha256")
        or anchor.get("decision", {}).get(spec.anchor_continuation_decision_key)
        is not True
        or anchor.get("decision", {}).get("material_feedback_authorized") is not False
    ):
        raise RuntimeError("two-map tail requires its matching byte-identical anchor")

    immutable_relative = str(anchor["anchor_state_path"])
    initial_relative = str(final["mapped_state_path"])
    immutable = root / immutable_relative
    initial = root / initial_relative
    scratch = root / spec.scratch_state_path
    if immutable_relative == initial_relative:
        raise RuntimeError("tail immutable anchor and initial state must be distinct files")
    if spec.scratch_state_path in {immutable_relative, initial_relative}:
        raise RuntimeError("tail scratch must be an independent third buffer")
    if (
        sha256(immutable) != anchor["anchor_state_sha256"]
        or sha256(initial) != final["mapped_state_sha256"]
        or immutable.stat().st_size != initial.stat().st_size
        or immutable.stat().st_size != scratch.stat().st_size
    ):
        raise RuntimeError("two-map tail checkpoint chain changed")

    maximum_maps = len(iterations) + 2
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            "sequence_summary": source_entry(root, spec.sequence_summary_path),
            "sequence_protocol": source_entry(root, spec.sequence_protocol_path),
            "tail_anchor_summary": source_entry(root, spec.anchor_summary_path),
            "tail_anchor_protocol": source_entry(root, spec.anchor_protocol_path),
            "immutable_tail_anchor": source_entry(root, immutable_relative),
            "initial_sequence_tail_state": source_entry(root, initial_relative),
            "finite_trial_protocol": source_entry(root, FINITE_TRIAL_PROTOCOL),
            "finite_trial_material": source_entry(root, FINITE_TRIAL_MATERIAL),
            "phase7b5p_master_input": source_entry(root, MASTER_INPUT),
            "generic_positive_picard_runner": source_entry(root, GENERIC_MAP_RUNNER),
            "positive_sequence_engine": source_entry(root, POSITIVE_SEQUENCE_ENGINE),
            "seeded_picard_runner": source_entry(root, SEEDED_PICARD_RUNNER),
            "phase7b7i_worker": source_entry(root, MAP_WORKER),
            "phase7b9d_worker_helpers": source_entry(root, WORKER_HELPERS),
            "mixed_frame_operator": source_entry(root, MIXED_FRAME_OPERATOR),
            "mixed_frame_frequency": source_entry(root, MIXED_FRAME_FREQUENCY),
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": PHYSICAL_FREQUENCY_GROUPS,
            "angular_direction_count": ANGULAR_DIRECTION_COUNT,
            "radiation_depth_cell_count": RADIATION_DEPTH_CELL_COUNT,
            "natural_frequency_block_count": NATURAL_FREQUENCY_BLOCK_COUNT,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_picard_maps": maximum_maps,
            "maximum_concurrent_processes": (
                MEMORY_SAFE_HEAVY_MAXIMUM_CONCURRENT_PROCESSES
            ),
            "stop_after_iteration": maximum_maps - 1,
            "seed_summary_source_key": "sequence_summary",
            "seed_summary_format": "sequence",
            "seed_iteration_count": len(iterations),
            "new_picard_map_count_exactly": 2,
            "immutable_anchor_path": immutable_relative,
            "immutable_anchor_sha256": anchor["anchor_state_sha256"],
            "initial_state_path": initial_relative,
            "initial_state_sha256": final["mapped_state_sha256"],
            "scratch_state_path": spec.scratch_state_path,
            "scratch_state_initial_sha256": sha256(scratch),
            "raw_float64_checkpoint_size_bytes": initial.stat().st_size,
            "manifest_path": spec.manifest_path,
            "report_directory": spec.report_directory,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "runner_path": spec.runner_path,
            **numerical_repair_prohibitions(sequence=True),
        },
        "reference": {
            "initial_global_residual": final["global_original_operator_residual"],
            "initial_boundary_spectrum_l1": final["boundary_spectrum_l1"],
            "initial_boundary_bolometric_fraction": final[
                "boundary_bolometric_fraction"
            ],
            "source_sequence_protocol_sha256": sequence["protocol_sha256"],
        },
        "gates": memory_safe_seeded_two_map_gates(),
        "resource_gate_provenance": memory_safe_resource_provenance(),
        "authorization": {
            "seed_manifest_from_audited_sequence": True,
            "alternate_only_named_generated_buffers": True,
            "run_exactly_two_new_picard_maps": True,
            spec.tail_anderson_authorization_key: True,
            "material_feedback_only_after_convergence": True,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
    }


def build_protected_anderson_tail_protocol(
    root: Path, spec: ProtectedAndersonTailProtocolSpec
) -> dict[str, object]:
    """从锚点和恰好两次新 map 构造冻结的 protected Anderson(1) 协议。"""

    continuation, protocol, iterations = _passed_unconverged_sequence(
        root, spec.continuation_summary_path, spec.continuation_protocol_path
    )
    anchor = read_json(root, spec.anchor_summary_path)
    configuration = protocol.get("configuration", {})
    authorization = protocol.get("authorization", {})
    seed_count = int(configuration.get("seed_iteration_count", -1))
    if (
        int(configuration.get("new_picard_map_count_exactly", -1)) != 2
        or int(configuration.get("maximum_picard_maps", -1)) != seed_count + 2
        or len(iterations) != seed_count + 2
        or int(configuration.get("stop_after_iteration", -1)) != len(iterations) - 1
        or authorization.get("run_exactly_two_new_picard_maps") is not True
    ):
        raise RuntimeError("protected tail Anderson requires exactly two new maps")
    if (
        anchor.get("protocol_sha256") != sha256(root / spec.anchor_protocol_path)
        or anchor.get("decision", {}).get(spec.anchor_continuation_decision_key)
        is not True
        or anchor.get("decision", {}).get("material_feedback_authorized") is not False
        or configuration.get("immutable_anchor_path") != anchor.get("anchor_state_path")
        or configuration.get("immutable_anchor_sha256")
        != anchor.get("anchor_state_sha256")
        or configuration.get("initial_state_sha256")
        != anchor.get("anchor_state_sha256")
        or configuration.get("initial_state_path")
        != anchor.get("source_state_path")
        or configuration.get("initial_state_sha256")
        != anchor.get("source_state_sha256")
        or configuration.get("immutable_anchor_path")
        == configuration.get("initial_state_path")
    ):
        raise RuntimeError("protected tail Anderson anchor lineage changed")

    first_new = iterations[-2]
    second_new = iterations[-1]
    basis = {
        "x9": {
            "path": str(anchor["anchor_state_path"]),
            "sha256": str(anchor["anchor_state_sha256"]),
        },
        "x10": {
            "path": str(first_new["mapped_state_path"]),
            "sha256": str(first_new["mapped_state_sha256"]),
        },
        "x11": {
            "path": str(second_new["mapped_state_path"]),
            "sha256": str(second_new["mapped_state_sha256"]),
        },
    }
    if (
        int(first_new.get("iteration", -1)) != seed_count
        or int(second_new.get("iteration", -1)) != seed_count + 1
        or first_new.get("input_state_path")
        != configuration.get("initial_state_path")
        or first_new.get("input_state_sha256") != basis["x9"]["sha256"]
        or second_new.get("input_state_path") != basis["x10"]["path"]
        or second_new.get("input_state_sha256") != basis["x10"]["sha256"]
        or len({row["path"] for row in basis.values()}) != 3
    ):
        raise RuntimeError("protected tail Anderson states are not consecutive")
    for label, row in basis.items():
        if sha256(root / row["path"]) != row["sha256"]:
            raise RuntimeError(f"protected tail Anderson {label} hash changed")
    candidate = root / spec.candidate_output_path
    expected_size = (root / basis["x9"]["path"]).stat().st_size
    if (
        spec.candidate_output_path in {row["path"] for row in basis.values()}
        or candidate.stat().st_size != expected_size
        or any((root / row["path"]).stat().st_size != expected_size for row in basis.values())
    ):
        raise RuntimeError("protected tail Anderson candidate scratch is invalid")

    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            "continuation_summary": source_entry(
                root, spec.continuation_summary_path
            ),
            "continuation_protocol": source_entry(
                root, spec.continuation_protocol_path
            ),
            "tail_anchor_summary": source_entry(root, spec.anchor_summary_path),
            "tail_anchor_protocol": source_entry(root, spec.anchor_protocol_path),
            "x9_state": source_entry(root, basis["x9"]["path"]),
            "x10_state": source_entry(root, basis["x10"]["path"]),
            "x11_state": source_entry(root, basis["x11"]["path"]),
            "phase7b5p_master_input": source_entry(root, MASTER_INPUT),
            "slow_mode_runner": source_entry(root, SLOW_MODE_RUNNER),
            "protected_anderson_builder": source_entry(
                root, SLOW_MODE_PROTOCOL_BUILDER
            ),
            "radiative_transfer_quadrature": source_entry(
                root, RADIATIVE_TRANSFER_QUADRATURE
            ),
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": PHYSICAL_FREQUENCY_GROUPS,
            "angular_direction_count": ANGULAR_DIRECTION_COUNT,
            "radiation_depth_cell_count": RADIATION_DEPTH_CELL_COUNT,
            "x9_state_path": basis["x9"]["path"],
            "x9_state_sha256": basis["x9"]["sha256"],
            "x10_state_path": basis["x10"]["path"],
            "x10_state_sha256": basis["x10"]["sha256"],
            "x11_state_path": basis["x11"]["path"],
            "x11_state_sha256": basis["x11"]["sha256"],
            "x9_original_operator_residual": first_new[
                "global_original_operator_residual"
            ],
            "x10_original_operator_residual": second_new[
                "global_original_operator_residual"
            ],
            "scan_frequency_chunk": 16,
            "diagnostic_frequency_block": 128,
            "minimum_forward_picard_fraction": 1.0,
            "maximum_forward_picard_fraction": 96.0,
            "candidate_output_path": spec.candidate_output_path,
            "candidate_output_previous_sha256": sha256(candidate),
            "raw_float64_checkpoint_size_bytes": expected_size,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "kkt_regularization": False,
            "matter_feedback": False,
        },
        "gates": protected_anderson_tail_gates(),
        "authorization": {
            "overwrite_only_named_superseded_checkpoint": True,
            "write_candidate_only_if_all_algebraic_gates_pass": True,
            "fresh_full_original_operator_map_required": True,
            "continue_unrelaxed_picard_if_candidate_fails": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
        "lineage": {
            "continuation_protocol_sha256": continuation["protocol_sha256"],
            "seed_iteration_count": seed_count,
            "new_picard_iteration_indices": [
                first_new["iteration"],
                second_new["iteration"],
            ],
        },
    }


def freeze_protocol(root: Path, relative_path: str, payload: dict[str, object]) -> str:
    """仅原子写入 JSON 协议；拒绝把目标放进 checkpoint tree。"""
    path = root / relative_path
    output_root = (root / "outputs").resolve()
    checkpoint_root = (root / "outputs/checkpoints").resolve()
    resolved = path.resolve()
    if (
        path.suffix.lower() != ".json"
        or not resolved.is_relative_to(output_root)
        or resolved.is_relative_to(checkpoint_root)
    ):
        raise ValueError("frozen protocol target must be an outputs JSON outside checkpoints")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    return sha256(path)
