"""Phase 7B9：复用 provisional previous artifact 的正式 H/He feedback pair。"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath

try:
    from scripts import phase7b9_formal_feedback_pair_adapter as adapter
    from scripts import phase7b9_consecutive_after_provisional as consecutive
    from scripts import phase7b9_protocol_builders as common
    from scripts import phase7b9_provisional_feedback as provisional
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_formal_feedback_pair_adapter as adapter  # type: ignore[no-redef]
    import phase7b9_consecutive_after_provisional as consecutive  # type: ignore[no-redef]
    import phase7b9_protocol_builders as common  # type: ignore[no-redef]
    import phase7b9_provisional_feedback as provisional  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
RUNNER_RELATIVE_PATH = "scripts/phase7b9_formal_pair_from_provisional.py"
PAUSED_PREREGISTER_RELATIVE_PATH = (
    "scripts/phase7b9ds_preregister_formal_pair_from_provisional.py"
)
PAUSED_ADAPTER_RELATIVE_PATH = "scripts/phase7b9ds_formal_pair_adapter.py"
MATERIAL_RELAXATION = 0.0625
PAUSED_DIRECT_SOURCE_KEYS = {
    "passed_consecutive_protocol",
    "passed_consecutive_summary",
    "cached_provisional_protocol",
    "cached_provisional_summary",
    "previous_feedback_manifest",
    "previous_feedback_artifact",
    "trial_residual_acceptance",
    "trial_material_protocol",
    "trial_material_summary",
    "trial_material",
    "base_feedback_summary",
    "base_residual",
    "physical_old_time_level",
    "phase7b7j_protocol",
    "adapter_runner",
    "pair_runner",
    "pair_preregister",
}


@dataclass(frozen=True)
class FormalPairFromProvisionalSpec:
    phase: str
    phase_index: int
    classification: str
    confirmation_protocol_path: str
    confirmation_summary_path: str
    provisional_protocol_path: str
    provisional_summary_path: str
    trial_acceptance_path: str
    material_protocol_path: str
    material_summary_path: str
    material_path: str
    base_feedback_summary_path: str
    base_residual_path: str
    physical_old_time_level_path: str
    phase7b7j_protocol_path: str
    adapter_runner_path: str
    pair_runner_path: str
    feedback_work_directory: str
    final_feedback_output: str
    target_material_output: str
    encoded_residual_output: str
    summary_path: str
    figure_path: str


@dataclass(frozen=True)
class PausedFormalPairFromProvisionalSpec:
    phase: str
    phase_index: int
    classification: str
    confirmation_protocol_path: str
    confirmation_summary_path: str
    provisional_protocol_path: str
    provisional_summary_path: str
    provisional_manifest_path: str
    provisional_artifact_path: str
    trial_acceptance_path: str
    base_feedback_summary_path: str
    base_residual_path: str
    adapter_runner_path: str
    pair_runner_path: str
    preregister_runner_path: str
    feedback_work_directory: str
    final_feedback_output: str
    target_material_output: str
    encoded_residual_output: str
    summary_path: str
    figure_path: str


def _read(root: Path, relative: str) -> dict[str, object]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _source(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": adapter.sha256(path),
    }


def _safe_small_source(root: Path, relative: str) -> dict[str, object]:
    return provisional._safe_small_source(root, relative)


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _confirmation(
    root: Path,
    protocol_path: str,
    summary_path: str,
) -> tuple[dict[str, object], dict[str, object]]:
    protocol = _read(root, protocol_path)
    summary = _read(root, summary_path)
    decision = summary.get("decision", {})
    checks = summary.get("gate_checks", {})
    if (
        summary.get("protocol_sha256") != adapter.sha256(root / protocol_path)
        or summary.get("status") != "complete"
        or not checks
        or any(value is not True for value in checks.values())
        or summary.get("previous_state_bytes_retained") is not False
        or decision.get("two_consecutive_fixed_matter_states_converged") is not True
        or decision.get("provisional_previous_feedback_valid_for_pair") is not True
        or decision.get("final_feedback_extraction_authorized") is not True
        or decision.get("formal_h_he_feedback_pair_authorized") is not True
        or decision.get("material_feedback_evaluated") is not False
    ):
        raise RuntimeError("formal pair requires a passed fresh consecutive audit")
    return protocol, summary


def _provisional(
    root: Path,
    protocol_path: str,
    summary_path: str,
    confirmation: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    protocol = _read(root, protocol_path)
    summary = _read(root, summary_path)
    decision = summary.get("decision", {})
    manifest_path = str(summary.get("feedback_manifest_path"))
    artifact_path = str(summary.get("feedback_artifact_path"))
    if (
        summary.get("protocol_sha256") != adapter.sha256(root / protocol_path)
        or summary.get("status") != "complete"
        or summary.get("radiation_state_path")
        != confirmation.get("previous_converged_state_path")
        or summary.get("radiation_state_sha256")
        != confirmation.get("previous_converged_state_sha256")
        or summary.get("formal_state_gate_passed") is not True
        or decision.get("provisional_feedback_extraction_complete") is not True
        or decision.get("provisional_feedback_is_acceptance_authority") is not False
        or decision.get("formal_h_he_feedback_pair_authorized") is not False
        or adapter.sha256(root / artifact_path)
        != summary.get("feedback_artifact_sha256")
    ):
        raise RuntimeError("cached provisional feedback evidence changed")
    manifest = _read(root, manifest_path)
    if (
        manifest.get("status") != "complete"
        or manifest.get("state_gate_passed") is not True
        or manifest.get("state_path") != summary.get("radiation_state_path")
        or manifest.get("state_sha256") != summary.get("radiation_state_sha256")
        or manifest.get("feedback_artifact_path") != artifact_path
        or manifest.get("feedback_artifact_sha256")
        != summary.get("feedback_artifact_sha256")
    ):
        raise RuntimeError("cached provisional feedback manifest changed")
    return protocol, summary, manifest


def _material(
    root: Path,
    protocol_path: str,
    summary_path: str,
    material_path: str,
) -> dict[str, object]:
    protocol = _read(root, protocol_path)
    summary = _read(root, summary_path)
    source = _source(root, material_path)
    decision = summary.get("decision", {})
    if (
        summary.get("protocol_sha256") != adapter.sha256(root / protocol_path)
        or protocol.get("configuration", {}).get("candidate_absolute_relaxation")
        != MATERIAL_RELAXATION
        or summary.get("candidate_absolute_relaxation") != MATERIAL_RELAXATION
        or summary.get("candidate_path") != material_path
        or summary.get("candidate_sha256") != source["sha256"]
        or decision.get("material_candidate_gate_passed") is not True
        or decision.get("candidate_accepted_as_nonlinear_step") is not False
    ):
        raise RuntimeError("formal pair 0.0625 material lineage changed")
    return source


def _passed_claim_only_confirmation(
    root: Path,
    protocol_path: str,
    summary_path: str,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, dict[str, object]],
    dict[str, object],
]:
    protocol = provisional._read_small_json(root, protocol_path)
    summary = provisional._read_small_json(root, summary_path)
    protocol_hash = adapter.sha256(root / protocol_path)
    if summary.get("protocol_sha256") != protocol_hash:
        raise RuntimeError("passed 7B9dr protocol SHA changed")
    inherited = provisional._validate_small_source_pins(root, protocol)
    if any(str(source["path"]).lower().endswith(".dat") for source in inherited.values()):
        raise RuntimeError("passed 7B9dr protocol contains a .dat source")

    cfg = protocol.get("configuration", {})
    gates = protocol.get("gates", {})
    authorization = protocol.get("authorization", {})
    checks = summary.get("gate_checks", {})
    decision = summary.get("decision", {})
    if (
        gates != common.memory_safe_seeded_two_map_gates()
        or int(cfg.get("maximum_concurrent_processes", -1)) != 2
        or int(cfg.get("natural_frequency_block_count", -1)) != 76
        or int(cfg.get("owned_frequency_group_count", -1)) != 9632
        or cfg.get("execute_exactly_one_fresh_map") is not True
        or authorization.get("execute_exactly_one_fresh_map") is not True
        or authorization.get("material_feedback_during_confirmation") is not False
        or authorization.get("formal_pair_authorized_before_fresh_map") is not False
        or any(
            bool(cfg.get(name))
            for name in (
                "cellwise_clipping",
                "nan_to_num",
                "intensity_floor",
                "point_deletion",
                "posthoc_renormalization",
            )
        )
    ):
        raise RuntimeError("passed 7B9dr execution gates changed")
    if (
        summary.get("status") != "complete"
        or summary.get("executed_fresh_map_count") != 1
        or summary.get("fresh_map_iteration") != cfg.get("fresh_map_iteration")
        or not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
        or summary.get("previous_state_bytes_retained") is not False
        or decision.get("two_consecutive_fixed_matter_states_converged") is not True
        or decision.get("provisional_previous_feedback_valid_for_pair") is not True
        or decision.get("final_feedback_extraction_authorized") is not True
        or decision.get("formal_h_he_feedback_pair_authorized") is not True
        or decision.get("material_feedback_evaluated") is not False
        or decision.get("dynamic_nlte_solution_accepted") is not False
    ):
        raise RuntimeError("formal pair requires one passed 7B9dr fresh map")
    metric_limits = (
        (summary.get("previous_global_original_operator_residual"), 1.0e-4),
        (summary.get("previous_boundary_spectrum_l1"), 1.0e-3),
        (summary.get("previous_boundary_bolometric_fraction"), 1.0e-3),
        (summary.get("input_global_original_operator_residual"), 1.0e-4),
        (summary.get("input_boundary_spectrum_l1"), 1.0e-3),
        (summary.get("input_boundary_bolometric_fraction"), 1.0e-3),
    )
    if any(value is None or float(value) >= limit for value, limit in metric_limits):
        raise RuntimeError("two consecutive residual or boundary thresholds changed")

    previous_identity = (
        summary.get("previous_converged_state_path"),
        summary.get("previous_converged_state_sha256"),
    )
    final_identity = (
        summary.get("input_state_path"),
        summary.get("input_state_sha256"),
    )
    output_identity = (
        summary.get("output_state_path"),
        summary.get("output_state_sha256"),
    )
    if (
        previous_identity
        != (cfg.get("previous_audited_input_path"), cfg.get("previous_audited_input_sha256"))
        or final_identity != (cfg.get("current_input_path"), cfg.get("current_input_sha256"))
        or output_identity[0] != cfg.get("output_path")
        or previous_identity[0] == final_identity[0]
    ):
        raise RuntimeError("7B9dr previous/final/output lineage changed")
    claims = protocol.get("full_state_claims", {})
    previous_claim = claims.get("previous_audited_input")
    final_claim = claims.get("current_next_consecutive_input")
    if (
        not isinstance(previous_claim, dict)
        or not isinstance(final_claim, dict)
        or previous_claim.get("path") != previous_identity[0]
        or previous_claim.get("sha256") != previous_identity[1]
        or previous_claim.get("provisional_feedback_cached_before_overwrite")
        is not True
        or final_claim.get("path") != final_identity[0]
        or final_claim.get("sha256") != final_identity[1]
    ):
        raise RuntimeError("7B9dr full-state claims changed")
    final = provisional._full_state_claim(
        final_claim["path"], final_claim["sha256"], int(final_claim["size_bytes"])
    )
    return protocol, summary, inherited, final


def build_formal_pair_from_provisional_protocol(
    root: Path,
    spec: FormalPairFromProvisionalSpec,
) -> dict[str, object]:
    """Build the formal pair without requiring the overwritten previous full state."""
    _, confirmation = _confirmation(
        root, spec.confirmation_protocol_path, spec.confirmation_summary_path
    )
    _, provisional_summary, _ = _provisional(
        root,
        spec.provisional_protocol_path,
        spec.provisional_summary_path,
        confirmation,
    )
    material = _material(
        root,
        spec.material_protocol_path,
        spec.material_summary_path,
        spec.material_path,
    )
    acceptance = _read(root, spec.trial_acceptance_path)
    adapter._require_exact_acceptance_gates(acceptance)
    acceptance_gates = dict(acceptance["gates"])
    acceptance_gates.pop("candidate_state_must_match_frozen_phase7b9i_bytes")
    acceptance_gates["candidate_state_must_match_frozen_phase7b9de_bytes"] = True
    base = _read(root, spec.base_feedback_summary_path)
    if (
        base.get("decision", {}).get("phase7b9f_gate_passed") is not True
        or base.get("encoded_residual_path") != spec.base_residual_path
        or base.get("encoded_residual_sha256")
        != adapter.sha256(root / spec.base_residual_path)
    ):
        raise RuntimeError("formal pair base residual lineage changed")
    final_path = str(confirmation["input_state_path"])
    final = _source(root, final_path)
    if final["sha256"] != confirmation["input_state_sha256"]:
        raise RuntimeError("final audited radiation bytes changed")
    if spec.pair_runner_path != RUNNER_RELATIVE_PATH:
        raise RuntimeError("formal-pair provisional runner changed")
    previous_manifest = str(provisional_summary["feedback_manifest_path"])
    previous_artifact = str(provisional_summary["feedback_artifact_path"])
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            "consecutive_confirmation_protocol": _source(
                root, spec.confirmation_protocol_path
            ),
            "consecutive_confirmation_summary": _source(
                root, spec.confirmation_summary_path
            ),
            "provisional_protocol": _source(root, spec.provisional_protocol_path),
            "provisional_summary": _source(root, spec.provisional_summary_path),
            "previous_feedback_manifest": _source(root, previous_manifest),
            "previous_feedback_artifact": _source(root, previous_artifact),
            "trial_residual_acceptance": _source(
                root, spec.trial_acceptance_path
            ),
            "trial_material_protocol": _source(root, spec.material_protocol_path),
            "trial_material_summary": _source(root, spec.material_summary_path),
            "trial_material": material,
            "base_feedback_summary": _source(
                root, spec.base_feedback_summary_path
            ),
            "base_residual": _source(root, spec.base_residual_path),
            "physical_old_time_level": _source(
                root, spec.physical_old_time_level_path
            ),
            "phase7b7j_protocol": _source(root, spec.phase7b7j_protocol_path),
            "adapter_runner": _source(root, spec.adapter_runner_path),
            "pair_runner": _source(root, spec.pair_runner_path),
            "final_radiation": final,
        },
        "overwritten_previous_radiation_claim": {
            "path": confirmation["previous_converged_state_path"],
            "sha256": confirmation["previous_converged_state_sha256"],
            "full_state_retained": False,
            "formal_feedback_cached_and_state_gate_passed": True,
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": adapter.PHYSICAL_FREQUENCY_GROUPS,
            "core_frequency_groups": adapter.CORE_FREQUENCY_GROUPS,
            "block_count": adapter.BLOCK_COUNT,
            "angular_direction_count": adapter.ANGULAR_DIRECTION_COUNT,
            "radiation_depth_cell_count": adapter.RADIATION_DEPTH_CELL_COUNT,
            "material_cell_count": adapter.MATERIAL_CELL_COUNT,
            "rate_quadrature_order_per_group": (
                adapter.RATE_QUADRATURE_ORDER_PER_GROUP
            ),
            "maximum_concurrent_processes": 2,
            "feedback_work_directory": spec.feedback_work_directory,
            "final_feedback_output": spec.final_feedback_output,
            "target_material_output": spec.target_material_output,
            "encoded_residual_output": spec.encoded_residual_output,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "reuse_completed_feedback_manifests": True,
            "reuse_provisional_previous_feedback": True,
            "previous_global_original_operator_residual": confirmation[
                "previous_global_original_operator_residual"
            ],
            "previous_boundary_spectrum_l1": confirmation[
                "previous_boundary_spectrum_l1"
            ],
            "previous_boundary_bolometric_fraction": confirmation[
                "previous_boundary_bolometric_fraction"
            ],
            "final_global_original_operator_residual": confirmation[
                "input_global_original_operator_residual"
            ],
            "final_boundary_spectrum_l1": confirmation[
                "input_boundary_spectrum_l1"
            ],
            "final_boundary_bolometric_fraction": confirmation[
                "input_boundary_bolometric_fraction"
            ],
            "transport_or_source_iteration": False,
            "material_update": False,
            "radiation_update": False,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "formal_state_gates": adapter._formal_state_gates(),
        "acceptance_gates": acceptance_gates,
        "authorization": {
            "reuse_previous_only_after_provisional_state_gate": True,
            "evaluate_exactly_one_new_final_feedback_state": True,
            "evaluate_pair_only_after_two_consecutive_residuals": True,
            "accept_candidate_only_if_all_acceptance_gates_pass": True,
            "reject_candidate_if_any_gate_fails": True,
            "material_update_during_pair": False,
            "radiation_update_during_pair": False,
            "accept_dynamic_nlte_solution": False,
        },
    }


def build_paused_formal_pair_from_provisional_protocol(
    root: Path,
    spec: PausedFormalPairFromProvisionalSpec,
) -> dict[str, object]:
    """Freeze cached-previous plus one fresh final feedback using no full-state I/O."""
    json_inputs = (
        spec.confirmation_protocol_path,
        spec.confirmation_summary_path,
        spec.provisional_protocol_path,
        spec.provisional_summary_path,
        spec.provisional_manifest_path,
        spec.trial_acceptance_path,
        spec.base_feedback_summary_path,
    )
    if any(PurePosixPath(path).suffix.lower() != ".json" for path in json_inputs):
        raise RuntimeError("7B9ds builder accepts JSON lineage evidence only")
    if spec.pair_runner_path != RUNNER_RELATIVE_PATH:
        raise RuntimeError("7B9ds formal-pair runner changed")
    if spec.adapter_runner_path != PAUSED_ADAPTER_RELATIVE_PATH:
        raise RuntimeError("7B9ds claim-only adapter changed")
    if spec.preregister_runner_path != PAUSED_PREREGISTER_RELATIVE_PATH:
        raise RuntimeError("7B9ds preregister runner changed")

    (
        confirmation_protocol,
        confirmation,
        inherited,
        final_claim,
    ) = _passed_claim_only_confirmation(
        root, spec.confirmation_protocol_path, spec.confirmation_summary_path
    )
    first = {
        "input_state_path": confirmation["previous_converged_state_path"],
        "input_state_sha256": confirmation["previous_converged_state_sha256"],
        "mapped_state_path": confirmation["input_state_path"],
        "mapped_state_sha256": confirmation["input_state_sha256"],
    }
    provisional_protocol, provisional_summary = (
        consecutive._validated_completed_claim_only_provisional(
            root,
            spec.provisional_protocol_path,
            spec.provisional_manifest_path,
            spec.provisional_summary_path,
            spec.provisional_artifact_path,
            first,
        )
    )
    required_material_sources = (
        "trial_material_protocol",
        "trial_material_summary",
        "trial_material",
        "physical_old_time_level",
        "phase7b7j_protocol",
    )
    if any(name not in provisional_protocol["sources"] for name in required_material_sources):
        raise RuntimeError("7B9ds provisional material/template sources are missing")
    trial_protocol = provisional_protocol["sources"]["trial_material_protocol"]
    trial_summary = provisional_protocol["sources"]["trial_material_summary"]
    trial_material = provisional_protocol["sources"]["trial_material"]
    provisional._validated_small_material(
        root,
        str(trial_protocol["path"]),
        str(trial_summary["path"]),
        str(trial_material["path"]),
    )

    acceptance = provisional._read_small_json(root, spec.trial_acceptance_path)
    adapter._require_exact_acceptance_gates(acceptance)
    acceptance_gates = dict(acceptance["gates"])
    acceptance_gates.pop("candidate_state_must_match_frozen_phase7b9i_bytes")
    acceptance_gates["candidate_state_must_match_frozen_phase7b9de_bytes"] = True
    base = provisional._read_small_json(root, spec.base_feedback_summary_path)
    base_residual = _safe_small_source(root, spec.base_residual_path)
    if (
        base.get("decision", {}).get("phase7b9f_gate_passed") is not True
        or base.get("encoded_residual_path") != spec.base_residual_path
        or base.get("encoded_residual_sha256") != base_residual["sha256"]
    ):
        raise RuntimeError("7B9ds base residual lineage changed")

    direct = {
        "passed_consecutive_protocol": _safe_small_source(
            root, spec.confirmation_protocol_path
        ),
        "passed_consecutive_summary": _safe_small_source(
            root, spec.confirmation_summary_path
        ),
        "cached_provisional_protocol": _safe_small_source(
            root, spec.provisional_protocol_path
        ),
        "cached_provisional_summary": _safe_small_source(
            root, spec.provisional_summary_path
        ),
        "previous_feedback_manifest": _safe_small_source(
            root, spec.provisional_manifest_path
        ),
        "previous_feedback_artifact": _safe_small_source(
            root, spec.provisional_artifact_path
        ),
        "trial_residual_acceptance": _safe_small_source(
            root, spec.trial_acceptance_path
        ),
        "trial_material_protocol": _safe_small_source(
            root, str(trial_protocol["path"])
        ),
        "trial_material_summary": _safe_small_source(
            root, str(trial_summary["path"])
        ),
        "trial_material": _safe_small_source(root, str(trial_material["path"])),
        "base_feedback_summary": _safe_small_source(
            root, spec.base_feedback_summary_path
        ),
        "base_residual": base_residual,
        "physical_old_time_level": _safe_small_source(
            root,
            str(provisional_protocol["sources"]["physical_old_time_level"]["path"]),
        ),
        "phase7b7j_protocol": _safe_small_source(
            root, str(provisional_protocol["sources"]["phase7b7j_protocol"]["path"])
        ),
        "adapter_runner": _safe_small_source(root, spec.adapter_runner_path),
        "pair_runner": _safe_small_source(root, spec.pair_runner_path),
        "pair_preregister": _safe_small_source(root, spec.preregister_runner_path),
    }
    if set(direct) != PAUSED_DIRECT_SOURCE_KEYS:
        raise RuntimeError("7B9ds direct source set changed")
    collisions = set(direct).intersection(inherited)
    if collisions:
        raise RuntimeError(f"7B9ds source-key collision: {sorted(collisions)}")
    sources = dict(direct)
    sources.update(deepcopy(inherited))
    if any(str(source["path"]).lower().endswith(".dat") for source in sources.values()):
        raise RuntimeError("7B9ds source set contains a .dat file")

    protocol = {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": sources,
        "full_state_claims": {"final_radiation": final_claim},
        "overwritten_previous_radiation_claim": {
            "path": confirmation["previous_converged_state_path"],
            "sha256": confirmation["previous_converged_state_sha256"],
            "full_state_retained": False,
            "formal_feedback_cached_and_state_gate_passed": True,
        },
        "upstream_lineage": {
            "passed_consecutive_protocol_sha256": adapter.sha256(
                root / spec.confirmation_protocol_path
            ),
            "executed_fresh_map_count": 1,
            "previous_feedback_reused_from_cache": True,
            "final_feedback_recomputed": True,
            "full_state_bytes_read_by_builder": False,
            "full_state_bytes_hashed_by_builder": False,
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": adapter.PHYSICAL_FREQUENCY_GROUPS,
            "core_frequency_groups": adapter.CORE_FREQUENCY_GROUPS,
            "block_count": adapter.BLOCK_COUNT,
            "angular_direction_count": adapter.ANGULAR_DIRECTION_COUNT,
            "radiation_depth_cell_count": adapter.RADIATION_DEPTH_CELL_COUNT,
            "material_cell_count": adapter.MATERIAL_CELL_COUNT,
            "rate_quadrature_order_per_group": adapter.RATE_QUADRATURE_ORDER_PER_GROUP,
            "maximum_concurrent_processes": 2,
            "feedback_work_directory": spec.feedback_work_directory,
            "final_feedback_output": spec.final_feedback_output,
            "target_material_output": spec.target_material_output,
            "encoded_residual_output": spec.encoded_residual_output,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "reuse_completed_feedback_manifests": True,
            "reuse_provisional_previous_feedback": True,
            "previous_global_original_operator_residual": confirmation[
                "previous_global_original_operator_residual"
            ],
            "previous_boundary_spectrum_l1": confirmation[
                "previous_boundary_spectrum_l1"
            ],
            "previous_boundary_bolometric_fraction": confirmation[
                "previous_boundary_bolometric_fraction"
            ],
            "final_global_original_operator_residual": confirmation[
                "input_global_original_operator_residual"
            ],
            "final_boundary_spectrum_l1": confirmation[
                "input_boundary_spectrum_l1"
            ],
            "final_boundary_bolometric_fraction": confirmation[
                "input_boundary_bolometric_fraction"
            ],
            "transport_or_source_iteration": False,
            "material_update": False,
            "radiation_update": False,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "formal_state_gates": adapter._formal_state_gates(),
        "acceptance_gates": acceptance_gates,
        "authorization": {
            "reuse_previous_only_after_provisional_state_gate": True,
            "evaluate_exactly_one_new_final_feedback_state": True,
            "evaluate_pair_only_after_two_consecutive_residuals": True,
            "accept_candidate_only_if_all_acceptance_gates_pass": True,
            "reject_candidate_if_any_gate_fails": True,
            "material_update_during_pair": False,
            "radiation_update_during_pair": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    if (
        protocol["configuration"]["maximum_concurrent_processes"] != 2
        or protocol["formal_state_gates"] != adapter._formal_state_gates()
        or provisional_summary["formal_state_gate_passed"] is not True
    ):
        raise RuntimeError("7B9ds formal gates or resources changed")
    return protocol


def write_paused_formal_pair_from_provisional_protocol(
    root: Path,
    spec: PausedFormalPairFromProvisionalSpec,
    output_path: Path,
) -> tuple[dict[str, object], str]:
    protocol = build_paused_formal_pair_from_provisional_protocol(root, spec)
    _write_json_atomic(output_path, protocol)
    return protocol, adapter.sha256(output_path)


def _load_protocol(path: Path, expected_hash: str) -> dict[str, object]:
    if adapter.sha256(path) != expected_hash:
        raise RuntimeError("frozen formal pair from provisional changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        current = ROOT / source["path"]
        if (
            current.stat().st_size != int(source["size_bytes"])
            or adapter.sha256(current) != source["sha256"]
        ):
            raise RuntimeError(f"formal-pair source changed: {source['path']}")
    return protocol


def _previous_manifest(protocol: dict[str, object]) -> dict[str, object]:
    source = protocol["sources"]["previous_feedback_manifest"]
    artifact = protocol["sources"]["previous_feedback_artifact"]
    claim = protocol["overwritten_previous_radiation_claim"]
    manifest = json.loads((ROOT / source["path"]).read_text(encoding="utf-8"))
    if (
        manifest.get("status") != "complete"
        or manifest.get("state_gate_passed") is not True
        or manifest.get("state_path") != claim["path"]
        or manifest.get("state_sha256") != claim["sha256"]
        or manifest.get("feedback_artifact_path") != artifact["path"]
        or manifest.get("feedback_artifact_sha256") != artifact["sha256"]
    ):
        raise RuntimeError("provisional previous feedback reuse changed")
    return manifest


def _runtime_protocol_with_validated_final_claim(
    protocol: dict[str, object],
) -> dict[str, object]:
    if "final_radiation" in protocol.get("sources", {}):
        return protocol
    claim = protocol.get("full_state_claims", {}).get("final_radiation")
    if not isinstance(claim, dict):
        raise RuntimeError("7B9ds final-radiation claim is missing")
    path = ROOT / str(claim["path"])
    if (
        path.stat().st_size != int(claim["size_bytes"])
        or adapter.sha256(path) != claim["sha256"]
    ):
        raise RuntimeError("7B9ds final-radiation claim bytes changed")
    runtime = deepcopy(protocol)
    runtime["sources"]["final_radiation"] = dict(claim)
    return runtime


def run_formal_pair(protocol_path: Path, expected_hash: str) -> dict[str, object]:
    """Run only final feedback, then reuse the cached previous artifact in pair gates."""
    protocol = _load_protocol(protocol_path, expected_hash)
    protocol = _runtime_protocol_with_validated_final_claim(protocol)
    adapter._validate_worker_template_sources(protocol)
    previous = _previous_manifest(protocol)
    final = adapter._run_feedback_state(
        protocol, protocol_path, expected_hash, "final"
    )
    if final.get("status") != "complete" or final.get("state_gate_passed") is not True:
        raise RuntimeError("final formal feedback state gate failed")
    original_protocol_loader = adapter.load_frozen_pair_protocol
    original_manifest_loader = adapter._load_reused_feedback_manifest
    try:
        adapter.load_frozen_pair_protocol = (
            lambda _path, _sha, validate_sources=True: protocol
        )
        adapter._load_reused_feedback_manifest = (
            lambda _protocol, label, root=ROOT: previous if label == "previous" else final
        )
        return adapter.run_pair(protocol_path, expected_hash)
    finally:
        adapter.load_frozen_pair_protocol = original_protocol_loader
        adapter._load_reused_feedback_manifest = original_manifest_loader


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expected-protocol-sha256", required=True)
    args = parser.parse_args()
    run_formal_pair(args.protocol, args.expected_protocol_sha256)


if __name__ == "__main__":
    main()
