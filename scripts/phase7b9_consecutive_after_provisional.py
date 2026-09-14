"""Phase 7B9：provisional feedback 后的一张 fresh consecutive map。"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath

try:
    from scripts import phase7b9_half_trial_positive_sequence_engine as engine
    from scripts import phase7b9_half_trial_radiation_continuation as continuation
    from scripts import phase7b9_protocol_builders as common
    from scripts import phase7b9_provisional_feedback as provisional
    from scripts import phase7b9dp_post_streaming_picard as dp
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_half_trial_positive_sequence_engine as engine  # type: ignore[no-redef]
    import phase7b9_half_trial_radiation_continuation as continuation  # type: ignore[no-redef]
    import phase7b9_protocol_builders as common  # type: ignore[no-redef]
    import phase7b9_provisional_feedback as provisional  # type: ignore[no-redef]
    import phase7b9dp_post_streaming_picard as dp  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
RUNNER_RELATIVE_PATH = "scripts/phase7b9_consecutive_after_provisional.py"
PAUSED_PREREGISTER_RELATIVE_PATH = (
    "scripts/phase7b9dr_preregister_consecutive_after_provisional.py"
)
PAUSED_DIRECT_SOURCE_KEYS = {
    "paused_continuation_protocol",
    "provisional_protocol",
    "provisional_summary",
    "provisional_feedback_manifest",
    "provisional_feedback_artifact",
    "consecutive_runner",
    "consecutive_preregister",
}


@dataclass(frozen=True)
class ConsecutiveAfterProvisionalSpec:
    phase: str
    phase_index: int
    classification: str
    continuation_protocol_path: str
    continuation_summary_path: str
    provisional_protocol_path: str
    provisional_summary_path: str
    runner_path: str
    transition_receipt_path: str
    summary_path: str


@dataclass(frozen=True)
class PausedConsecutiveAfterProvisionalSpec:
    phase: str
    phase_index: int
    classification: str
    continuation_protocol_path: str
    continuation_manifest_path: str
    continuation_summary_path: str
    provisional_protocol_path: str
    provisional_manifest_path: str
    provisional_summary_path: str
    provisional_artifact_path: str
    runner_path: str
    preregister_runner_path: str
    transition_receipt_path: str
    summary_path: str


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _source(root: Path, relative_path: str) -> dict[str, object]:
    return common.source_entry(root, relative_path)


def _load_json(root: Path, relative_path: str) -> dict[str, object]:
    return json.loads((root / relative_path).read_text(encoding="utf-8"))


def _safe_small_source(root: Path, relative_path: str) -> dict[str, object]:
    return provisional._safe_small_source(root, relative_path)


def _validated_completed_claim_only_provisional(
    root: Path,
    protocol_path: str,
    manifest_path: str,
    summary_path: str,
    artifact_path: str,
    first: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    protocol = provisional._read_small_json(root, protocol_path)
    manifest = provisional._read_small_json(root, manifest_path)
    summary = provisional._read_small_json(root, summary_path)
    protocol_hash = common.sha256(root / protocol_path)
    if (
        manifest.get("protocol_sha256") != protocol_hash
        or summary.get("protocol_sha256") != protocol_hash
    ):
        raise RuntimeError("completed provisional protocol SHA changed")
    provisional._validate_small_source_pins(root, protocol)
    if any(
        str(source["path"]).lower().endswith(".dat")
        for source in protocol["sources"].values()
    ):
        raise RuntimeError("completed provisional protocol contains a .dat source")

    previous = protocol.get("full_state_claims", {}).get("previous_radiation")
    next_consecutive = protocol.get("full_state_claims", {}).get(
        "next_consecutive_radiation"
    )
    expected_previous = {
        "path": first["input_state_path"],
        "sha256": first["input_state_sha256"],
    }
    expected_next = {
        "path": first["mapped_state_path"],
        "sha256": first["mapped_state_sha256"],
    }
    if (
        not isinstance(previous, dict)
        or not isinstance(next_consecutive, dict)
        or any(previous.get(key) != value for key, value in expected_previous.items())
        or any(
            next_consecutive.get(key) != value
            for key, value in expected_next.items()
        )
    ):
        raise RuntimeError("provisional full-state claims changed")
    cfg = protocol.get("configuration", {})
    authorization = protocol.get("authorization", {})
    if (
        int(cfg.get("maximum_concurrent_processes", -1)) != 2
        or protocol.get("formal_state_gates")
        != provisional.feedback._formal_state_gates()
        or protocol.get("radiation_gates")
        != {
            "global_original_operator_residual_below": 1.0e-4,
            "boundary_spectrum_l1_below": 1.0e-3,
            "boundary_bolometric_fraction_below": 1.0e-3,
        }
        or authorization.get("evaluate_exactly_one_provisional_feedback_state")
        is not True
        or authorization.get("provisional_feedback_is_acceptance_authority")
        is not False
        or authorization.get("next_consecutive_fresh_residual_required") is not True
        or authorization.get("formal_pair_authorized") is not False
        or authorization.get("material_update") is not False
        or authorization.get("radiation_update") is not False
    ):
        raise RuntimeError("completed provisional protocol authorization changed")

    decision = summary.get("decision", {})
    artifact = _safe_small_source(root, artifact_path)
    if (
        summary.get("status") != "complete"
        or manifest.get("status") != "complete"
        or summary.get("radiation_state_path") != first.get("input_state_path")
        or summary.get("radiation_state_sha256") != first.get("input_state_sha256")
        or summary.get("formal_state_gate_passed") is not True
        or summary.get("feedback_manifest_path") != manifest_path
        or summary.get("feedback_artifact_path") != artifact_path
        or summary.get("feedback_artifact_sha256") != artifact["sha256"]
        or decision.get("provisional_feedback_extraction_complete") is not True
        or decision.get("provisional_feedback_is_acceptance_authority") is not False
        or decision.get("next_consecutive_fresh_residual_authorized") is not True
        or decision.get("formal_h_he_feedback_pair_authorized") is not False
        or decision.get("material_feedback_authorized") is not False
        or decision.get("dynamic_nlte_solution_accepted") is not False
    ):
        raise RuntimeError("completed provisional summary authorization changed")
    if (
        manifest.get("state_gate_passed") is not True
        or manifest.get("state_path") != first.get("input_state_path")
        or manifest.get("state_sha256") != first.get("input_state_sha256")
        or manifest.get("feedback_artifact_path") != artifact_path
        or manifest.get("feedback_artifact_sha256") != artifact["sha256"]
    ):
        raise RuntimeError("completed provisional manifest lineage changed")
    return protocol, summary


def _validated_paused_continuation(
    root: Path,
    protocol_path: str,
    summary_path: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    protocol = _load_json(root, protocol_path)
    summary = _load_json(root, summary_path)
    iterations = summary.get("iterations")
    decision = summary.get("decision", {})
    if (
        summary.get("protocol_sha256") != common.sha256(root / protocol_path)
        or summary.get("status") != "complete"
        or not isinstance(iterations, list)
        or not iterations
        or decision.get("first_low_residual_and_boundary_input_audited") is not True
        or decision.get("provisional_feedback_extraction_authorized") is not True
        or decision.get("formal_h_he_feedback_pair_authorized") is not False
    ):
        raise RuntimeError("consecutive map requires a paused first low-residual state")
    first = iterations[-1]
    gates = protocol["gates"]
    if (
        first.get("map_passed") is not True
        or float(first.get("global_original_operator_residual", float("inf")))
        >= float(gates["global_original_operator_residual_below"])
        or float(first.get("boundary_spectrum_l1", float("inf")))
        >= float(gates["global_boundary_spectrum_l1_below"])
        or float(first.get("boundary_bolometric_fraction", float("inf")))
        >= float(gates["global_boundary_bolometric_fraction_below"])
        or summary.get("first_low_residual_input_path")
        != first.get("input_state_path")
        or summary.get("next_consecutive_input_path")
        != first.get("mapped_state_path")
    ):
        raise RuntimeError("first low-residual map lineage changed")
    return protocol, summary, first


def _validated_provisional(
    root: Path,
    protocol_path: str,
    summary_path: str,
    first: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    protocol = _load_json(root, protocol_path)
    summary = _load_json(root, summary_path)
    decision = summary.get("decision", {})
    artifact_path = summary.get("feedback_artifact_path")
    manifest_path = summary.get("feedback_manifest_path")
    if (
        summary.get("protocol_sha256") != common.sha256(root / protocol_path)
        or summary.get("status") != "complete"
        or summary.get("radiation_state_path") != first.get("input_state_path")
        or summary.get("radiation_state_sha256") != first.get("input_state_sha256")
        or summary.get("formal_state_gate_passed") is not True
        or decision.get("provisional_feedback_extraction_complete") is not True
        or decision.get("provisional_feedback_is_acceptance_authority") is not False
        or decision.get("next_consecutive_fresh_residual_authorized") is not True
        or decision.get("formal_h_he_feedback_pair_authorized") is not False
        or not isinstance(artifact_path, str)
        or not isinstance(manifest_path, str)
        or common.sha256(root / artifact_path)
        != summary.get("feedback_artifact_sha256")
    ):
        raise RuntimeError("provisional feedback evidence changed")
    manifest = _load_json(root, manifest_path)
    if (
        manifest.get("status") != "complete"
        or manifest.get("state_gate_passed") is not True
        or manifest.get("state_path") != first.get("input_state_path")
        or manifest.get("state_sha256") != first.get("input_state_sha256")
        or manifest.get("feedback_artifact_path") != artifact_path
        or manifest.get("feedback_artifact_sha256")
        != summary.get("feedback_artifact_sha256")
    ):
        raise RuntimeError("provisional feedback manifest lineage changed")
    return protocol, summary


def build_consecutive_after_provisional_protocol(
    root: Path,
    spec: ConsecutiveAfterProvisionalSpec,
) -> dict[str, object]:
    """Freeze exactly one fresh map without retaining a third full state."""
    continuation_protocol, _, first = _validated_paused_continuation(
        root, spec.continuation_protocol_path, spec.continuation_summary_path
    )
    _, provisional_summary = _validated_provisional(
        root,
        spec.provisional_protocol_path,
        spec.provisional_summary_path,
        first,
    )
    if spec.runner_path != RUNNER_RELATIVE_PATH:
        raise RuntimeError("consecutive-after-provisional runner changed")
    previous = root / str(first["input_state_path"])
    current = root / str(first["mapped_state_path"])
    if (
        previous.stat().st_size != current.stat().st_size
        or common.sha256(previous) != first["input_state_sha256"]
        or common.sha256(current) != first["mapped_state_sha256"]
    ):
        raise RuntimeError("consecutive-map full-state bytes changed before freeze")
    gates = dict(continuation_protocol["gates"])
    if gates != common.memory_safe_seeded_two_map_gates():
        raise RuntimeError("consecutive-map science or resource gates changed")
    provisional_artifact = str(provisional_summary["feedback_artifact_path"])
    provisional_manifest = str(provisional_summary["feedback_manifest_path"])
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            "continuation_protocol": _source(
                root, spec.continuation_protocol_path
            ),
            "continuation_summary": _source(root, spec.continuation_summary_path),
            "provisional_protocol": _source(root, spec.provisional_protocol_path),
            "provisional_summary": _source(root, spec.provisional_summary_path),
            "provisional_feedback_manifest": _source(root, provisional_manifest),
            "provisional_feedback_artifact": _source(root, provisional_artifact),
            "consecutive_runner": _source(root, spec.runner_path),
            "current_input_radiation": _source(
                root, str(first["mapped_state_path"])
            ),
        },
        "overwritten_full_state_claim": {
            "path": first["input_state_path"],
            "size_bytes": previous.stat().st_size,
            "sha256": first["input_state_sha256"],
            "feedback_cached_before_overwrite": True,
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "continuation_protocol_path": spec.continuation_protocol_path,
            "continuation_protocol_sha256": common.sha256(
                root / spec.continuation_protocol_path
            ),
            "continuation_manifest_path": continuation_protocol["configuration"][
                "manifest_path"
            ],
            "continuation_summary_path": spec.continuation_summary_path,
            "fresh_map_iteration": int(first["iteration"]) + 1,
            "previous_audited_input_path": first["input_state_path"],
            "previous_audited_input_sha256": first["input_state_sha256"],
            "current_input_path": first["mapped_state_path"],
            "current_input_sha256": first["mapped_state_sha256"],
            "output_path": first["input_state_path"],
            "transition_receipt_path": spec.transition_receipt_path,
            "summary_path": spec.summary_path,
            "maximum_concurrent_processes": 2,
            "execute_exactly_one_fresh_map": True,
            **common.numerical_repair_prohibitions(sequence=True),
        },
        "gates": gates,
        "authorization": {
            "overwrite_previous_audited_input_only_after_feedback_cached": True,
            "execute_exactly_one_fresh_map": True,
            "formal_pair_only_if_both_consecutive_residuals_pass": True,
            "continue_fixed_material_iteration_if_second_residual_fails": True,
            "material_feedback_during_confirmation": False,
            "accept_dynamic_nlte_solution": False,
        },
    }


def build_paused_consecutive_after_provisional_protocol(
    root: Path,
    spec: PausedConsecutiveAfterProvisionalSpec,
) -> dict[str, object]:
    """Freeze exactly one dp fresh map without opening either full-state claim."""
    json_inputs = (
        spec.continuation_protocol_path,
        spec.continuation_manifest_path,
        spec.continuation_summary_path,
        spec.provisional_protocol_path,
        spec.provisional_manifest_path,
        spec.provisional_summary_path,
    )
    if any(PurePosixPath(path).suffix.lower() != ".json" for path in json_inputs):
        raise RuntimeError("7B9dr builder accepts JSON lineage evidence only")
    if spec.runner_path != RUNNER_RELATIVE_PATH:
        raise RuntimeError("consecutive-after-provisional runner changed")
    if spec.preregister_runner_path != PAUSED_PREREGISTER_RELATIVE_PATH:
        raise RuntimeError("consecutive preregister path changed")

    (
        continuation_protocol,
        _,
        _,
        first,
        inherited,
        continuation_hash,
    ) = provisional._validated_provisional_pause(
        root,
        spec.continuation_protocol_path,
        spec.continuation_manifest_path,
        spec.continuation_summary_path,
    )
    if continuation_protocol["configuration"].get("manifest_path") != (
        spec.continuation_manifest_path
    ):
        raise RuntimeError("paused continuation manifest path changed")
    gates = dict(continuation_protocol["gates"])
    cfg = continuation_protocol["configuration"]
    if (
        gates != common.memory_safe_seeded_two_map_gates()
        or int(cfg.get("maximum_concurrent_processes", -1)) != 2
        or int(cfg.get("natural_frequency_block_count", -1)) != 76
        or int(cfg.get("physical_frequency_groups", -1)) != 9632
    ):
        raise RuntimeError("7B9dr science, ownership, or resource gates changed")

    _, provisional_summary = _validated_completed_claim_only_provisional(
        root,
        spec.provisional_protocol_path,
        spec.provisional_manifest_path,
        spec.provisional_summary_path,
        spec.provisional_artifact_path,
        first,
    )
    direct = {
        "paused_continuation_protocol": _safe_small_source(
            root, spec.continuation_protocol_path
        ),
        "provisional_protocol": _safe_small_source(
            root, spec.provisional_protocol_path
        ),
        "provisional_summary": _safe_small_source(
            root, spec.provisional_summary_path
        ),
        "provisional_feedback_manifest": _safe_small_source(
            root, spec.provisional_manifest_path
        ),
        "provisional_feedback_artifact": _safe_small_source(
            root, spec.provisional_artifact_path
        ),
        "consecutive_runner": _safe_small_source(root, spec.runner_path),
        "consecutive_preregister": _safe_small_source(
            root, spec.preregister_runner_path
        ),
    }
    if set(direct) != PAUSED_DIRECT_SOURCE_KEYS:
        raise RuntimeError("7B9dr direct source set changed")
    collisions = set(direct).intersection(inherited)
    if collisions:
        raise RuntimeError(f"7B9dr source-key collision: {sorted(collisions)}")
    sources = dict(direct)
    sources.update(deepcopy(inherited))
    if any(str(source["path"]).lower().endswith(".dat") for source in sources.values()):
        raise RuntimeError("7B9dr source set contains a .dat file")

    size_bytes = int(cfg["raw_float64_checkpoint_size_bytes"])
    previous = provisional._full_state_claim(
        first["input_state_path"], first["input_state_sha256"], size_bytes
    )
    current = provisional._full_state_claim(
        first["mapped_state_path"], first["mapped_state_sha256"], size_bytes
    )
    protocol = {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": sources,
        "pretransition_small_file_claims": {
            "paused_continuation_manifest": _safe_small_source(
                root, spec.continuation_manifest_path
            ),
            "paused_continuation_summary": _safe_small_source(
                root, spec.continuation_summary_path
            ),
        },
        "full_state_claims": {
            "previous_audited_input": {
                **previous,
                "provisional_feedback_cached_before_overwrite": True,
            },
            "current_next_consecutive_input": current,
        },
        "upstream_lineage": {
            "continuation_schema": "7B9dp_provisional_pause",
            "continuation_protocol_sha256": continuation_hash,
            "summary_iterations_equal_manifest_iterations": True,
            "previous_audited_input_has_cached_provisional_feedback": True,
            "provisional_feedback_is_formal_pair_authority": False,
            "full_state_bytes_read_by_builder": False,
            "full_state_bytes_hashed_by_builder": False,
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "continuation_protocol_path": spec.continuation_protocol_path,
            "continuation_protocol_sha256": continuation_hash,
            "continuation_manifest_path": spec.continuation_manifest_path,
            "continuation_summary_path": spec.continuation_summary_path,
            "fresh_map_iteration": int(first["iteration"]) + 1,
            "previous_audited_input_path": first["input_state_path"],
            "previous_audited_input_sha256": first["input_state_sha256"],
            "current_input_path": first["mapped_state_path"],
            "current_input_sha256": first["mapped_state_sha256"],
            "output_path": first["input_state_path"],
            "transition_receipt_path": spec.transition_receipt_path,
            "summary_path": spec.summary_path,
            "maximum_concurrent_processes": 2,
            "natural_frequency_block_count": 76,
            "owned_frequency_group_count": 9632,
            "execute_exactly_one_fresh_map": True,
            **common.numerical_repair_prohibitions(sequence=True),
        },
        "gates": gates,
        "authorization": {
            "previous_input_feedback_cached_before_overwrite": True,
            "overwrite_previous_audited_input_only_after_feedback_cached": True,
            "read_current_next_consecutive_input": True,
            "write_only_previous_audited_buffer": True,
            "execute_exactly_one_fresh_map": True,
            "formal_pair_only_if_both_consecutive_residuals_pass": True,
            "continue_fixed_material_iteration_if_second_residual_fails": True,
            "material_feedback_during_confirmation": False,
            "formal_pair_authorized_before_fresh_map": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    if (
        provisional_summary["decision"][
            "provisional_feedback_is_acceptance_authority"
        ]
        is not False
        or protocol["configuration"]["maximum_concurrent_processes"] != 2
        or protocol["gates"]["each_full_map_wall_time_strictly_below_s"]
        != 1800.0
        or protocol["gates"]["block_count_exactly"] != 76
        or any(
            bool(protocol["configuration"].get(name))
            for name in (
                "cellwise_clipping",
                "nan_to_num",
                "intensity_floor",
                "point_deletion",
                "posthoc_renormalization",
            )
        )
    ):
        raise RuntimeError("7B9dr execution authority changed")
    return protocol


def write_paused_consecutive_after_provisional_protocol(
    root: Path,
    spec: PausedConsecutiveAfterProvisionalSpec,
    output_path: Path,
) -> tuple[dict[str, object], str]:
    protocol = build_paused_consecutive_after_provisional_protocol(root, spec)
    _write_json_atomic(output_path, protocol)
    return protocol, common.sha256(output_path)


def _load_protocol(
    root: Path,
    protocol_path: Path,
    expected_hash: str,
) -> dict[str, object]:
    if common.sha256(protocol_path) != expected_hash:
        raise RuntimeError("frozen consecutive-after-provisional protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["sources"]["consecutive_runner"]["path"] != RUNNER_RELATIVE_PATH:
        raise RuntimeError("consecutive runner source changed")
    for source in protocol["sources"].values():
        path = root / str(source["path"])
        if (
            path.stat().st_size != int(source["size_bytes"])
            or common.sha256(path) != source["sha256"]
        ):
            raise RuntimeError(f"frozen consecutive source changed: {source['path']}")
    return protocol


def _validate_pretransition_small_claims(
    root: Path, protocol: dict[str, object]
) -> None:
    claims = protocol.get("pretransition_small_file_claims", {})
    for name, claim in claims.items():
        if not isinstance(claim, dict) or _safe_small_source(
            root, str(claim.get("path", ""))
        ) != claim:
            raise RuntimeError(f"7B9dr pretransition small-file claim changed: {name}")


def _validate_full_state_claims_before_overwrite(
    root: Path, protocol: dict[str, object]
) -> None:
    claims = protocol.get("full_state_claims")
    if not isinstance(claims, dict):
        return
    cfg = protocol["configuration"]
    pairs = (
        (
            "previous_audited_input",
            cfg["previous_audited_input_path"],
            cfg["previous_audited_input_sha256"],
        ),
        (
            "current_next_consecutive_input",
            cfg["current_input_path"],
            cfg["current_input_sha256"],
        ),
    )
    for name, expected_path, expected_sha in pairs:
        claim = claims.get(name)
        if (
            not isinstance(claim, dict)
            or claim.get("path") != expected_path
            or claim.get("sha256") != expected_sha
        ):
            raise RuntimeError(f"7B9dr full-state claim lineage changed: {name}")
        path = root / str(claim["path"])
        if (
            path.stat().st_size != int(claim["size_bytes"])
            or common.sha256(path) != claim["sha256"]
        ):
            raise RuntimeError(f"7B9dr full-state claim bytes changed: {name}")


def prepare_transition(
    root: Path,
    protocol_path: Path,
    expected_hash: str,
) -> dict[str, object]:
    """Switch X/Y to Y→X only after the provisional artifact is frozen."""
    protocol = _load_protocol(root, protocol_path, expected_hash)
    cfg = protocol["configuration"]
    manifest_path = root / cfg["continuation_manifest_path"]
    receipt_path = root / cfg["transition_receipt_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (
            receipt.get("protocol_sha256") != expected_hash
            or receipt.get("status") != "complete"
            or manifest.get("pending_consecutive_confirmation_protocol_sha256")
            != expected_hash
        ):
            raise RuntimeError("consecutive transition receipt changed")
        return manifest
    _validate_pretransition_small_claims(root, protocol)
    iterations = manifest.get("iterations")
    paused_status = (
        "provisional_pause"
        if protocol.get("upstream_lineage", {}).get("continuation_schema")
        == "7B9dp_provisional_pause"
        else "complete"
    )
    if (
        manifest.get("status") != paused_status
        or not isinstance(iterations, list)
        or not iterations
        or iterations[-1].get("input_state_path")
        != cfg["previous_audited_input_path"]
        or iterations[-1].get("mapped_state_path") != cfg["current_input_path"]
        or manifest.get("accepted_state_path") != cfg["previous_audited_input_path"]
    ):
        raise RuntimeError("paused continuation manifest changed")
    previous = root / cfg["previous_audited_input_path"]
    current = root / cfg["current_input_path"]
    if "full_state_claims" in protocol:
        _validate_full_state_claims_before_overwrite(root, protocol)
    elif (
        common.sha256(previous) != cfg["previous_audited_input_sha256"]
        or common.sha256(current) != cfg["current_input_sha256"]
    ):
        raise RuntimeError("consecutive transition full states changed")
    manifest["status"] = "running"
    manifest["current_input_path"] = cfg["current_input_path"]
    manifest["current_input_sha256"] = cfg["current_input_sha256"]
    manifest["next_output_path"] = cfg["output_path"]
    manifest["next_output_sha256"] = cfg["previous_audited_input_sha256"]
    manifest.pop("accepted_state_path", None)
    manifest.pop("accepted_state_sha256", None)
    manifest["pending_consecutive_confirmation_protocol_sha256"] = expected_hash
    continuation._write_json_atomic(manifest_path, manifest)
    receipt = {
        "phase": protocol["phase"],
        "protocol_sha256": expected_hash,
        "status": "complete",
        "previous_input_feedback_cached": True,
        "previous_input_path": cfg["previous_audited_input_path"],
        "previous_input_sha256_before_overwrite": cfg[
            "previous_audited_input_sha256"
        ],
        "fresh_input_path": cfg["current_input_path"],
        "fresh_input_sha256": cfg["current_input_sha256"],
        "output_path": cfg["output_path"],
    }
    _write_json_atomic(receipt_path, receipt)
    return manifest


def _confirmation_summary(
    protocol: dict[str, object],
    continuation_manifest: dict[str, object],
    expected_hash: str,
) -> dict[str, object]:
    cfg = protocol["configuration"]
    gates = protocol["gates"]
    iterations = continuation_manifest["iterations"]
    previous = iterations[-2]
    fresh = iterations[-1]
    consecutive_checks = {
        "first_residual_pass": float(previous["global_original_operator_residual"])
        < gates["global_original_operator_residual_below"],
        "fresh_residual_pass": float(fresh["global_original_operator_residual"])
        < gates["global_original_operator_residual_below"],
        "first_boundary_pass": float(previous["boundary_spectrum_l1"])
        < gates["global_boundary_spectrum_l1_below"]
        and float(previous["boundary_bolometric_fraction"])
        < gates["global_boundary_bolometric_fraction_below"],
        "fresh_boundary_pass": float(fresh["boundary_spectrum_l1"])
        < gates["global_boundary_spectrum_l1_below"]
        and float(fresh["boundary_bolometric_fraction"])
        < gates["global_boundary_bolometric_fraction_below"],
        "fresh_map_gates_pass": fresh.get("map_passed") is True,
        "provisional_feedback_cached_pass": True,
    }
    passed = all(consecutive_checks.values())
    return {
        "phase": protocol["phase"],
        "classification": "[V-consecutive]+[V-provisional-feedback]+[O]",
        "protocol_sha256": expected_hash,
        "status": "complete" if passed else "continue_required",
        "executed_fresh_map_count": 1,
        "fresh_map_iteration": cfg["fresh_map_iteration"],
        "previous_converged_state_path": cfg["previous_audited_input_path"],
        "previous_converged_state_sha256": cfg["previous_audited_input_sha256"],
        "previous_state_bytes_retained": False,
        "previous_global_original_operator_residual": previous[
            "global_original_operator_residual"
        ],
        "previous_boundary_spectrum_l1": previous["boundary_spectrum_l1"],
        "previous_boundary_bolometric_fraction": previous[
            "boundary_bolometric_fraction"
        ],
        "input_state_path": fresh["input_state_path"],
        "input_state_sha256": fresh["input_state_sha256"],
        "input_global_original_operator_residual": fresh[
            "global_original_operator_residual"
        ],
        "input_boundary_spectrum_l1": fresh["boundary_spectrum_l1"],
        "input_boundary_bolometric_fraction": fresh[
            "boundary_bolometric_fraction"
        ],
        "output_state_path": fresh["mapped_state_path"],
        "output_state_sha256": fresh["mapped_state_sha256"],
        "gate_checks": consecutive_checks,
        "decision": {
            "two_consecutive_fixed_matter_states_converged": passed,
            "provisional_previous_feedback_valid_for_pair": passed,
            "final_feedback_extraction_authorized": passed,
            "formal_h_he_feedback_pair_authorized": passed,
            "continue_fixed_material_radiation": not passed
            and fresh.get("map_passed") is True,
            "material_feedback_evaluated": False,
            "dynamic_nlte_solution_accepted": False,
        },
    }


def run_one_fresh_map(protocol_path: Path, expected_hash: str) -> dict[str, object]:
    protocol = _load_protocol(ROOT, protocol_path, expected_hash)
    cfg = protocol["configuration"]
    prepare_transition(ROOT, protocol_path, expected_hash)
    continuation_protocol_path = ROOT / cfg["continuation_protocol_path"]
    engine.EXPECTED_PROTOCOL_SHA256 = cfg["continuation_protocol_sha256"]
    os.environ[continuation.EXPECTED_HASH_ENV] = cfg[
        "continuation_protocol_sha256"
    ]
    manifest_path = ROOT / cfg["continuation_manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    before = len(manifest["iterations"])
    if (
        protocol.get("upstream_lineage", {}).get("continuation_schema")
        == "7B9dp_provisional_pause"
    ):
        dp.run_continuation(
            ROOT,
            continuation_protocol_path,
            cfg["continuation_protocol_sha256"],
            stop_after_iteration=before,
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        engine.run(continuation_protocol_path, stop_after_iteration=before)
        continuation_protocol = json.loads(
            continuation_protocol_path.read_text(encoding="utf-8")
        )
        manifest = continuation.compact_committed_reports(
            ROOT, continuation_protocol, cfg["continuation_protocol_sha256"]
        )
    if len(manifest["iterations"]) != before + 1:
        raise RuntimeError("consecutive confirmation did not execute exactly one map")
    summary = _confirmation_summary(protocol, manifest, expected_hash)
    _write_json_atomic(ROOT / cfg["summary_path"], summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expected-protocol-sha256", required=True)
    args = parser.parse_args()
    run_one_fresh_map(args.protocol, args.expected_protocol_sha256)


if __name__ == "__main__":
    main()
