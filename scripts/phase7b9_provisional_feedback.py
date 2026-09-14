"""Phase 7B9：首个低残差 audited input 的 provisional H/He feedback。"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath

try:
    from scripts import phase7b9_formal_feedback_pair_adapter as feedback
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_formal_feedback_pair_adapter as feedback  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
RUNNER_RELATIVE_PATH = "scripts/phase7b9_provisional_feedback.py"
PAUSED_PREREGISTER_RELATIVE_PATH = (
    "scripts/phase7b9dq_preregister_provisional_feedback.py"
)
PAUSED_ADAPTER_RELATIVE_PATH = (
    "scripts/phase7b9dq_provisional_feedback_adapter.py"
)
MATERIAL_RELAXATION = 0.0625
MAXIMUM_SMALL_SOURCE_BYTES = 64 * 1024 * 1024


PAUSED_DIRECT_SOURCE_KEYS = {
    "paused_continuation_protocol",
    "paused_continuation_manifest",
    "paused_continuation_summary",
    "trial_material_protocol",
    "trial_material_summary",
    "trial_material",
    "physical_old_time_level",
    "phase7b7j_protocol",
    "adapter_runner",
    "provisional_runner",
    "provisional_preregister",
}


@dataclass(frozen=True)
class ProvisionalFeedbackProtocolSpec:
    phase: str
    phase_index: int
    classification: str
    continuation_protocol_path: str
    continuation_summary_path: str
    material_protocol_path: str
    material_summary_path: str
    material_path: str
    physical_old_time_level_path: str
    phase7b7j_protocol_path: str
    adapter_runner_path: str
    provisional_runner_path: str
    feedback_work_directory: str
    feedback_output: str
    summary_path: str


@dataclass(frozen=True)
class PausedProvisionalFeedbackProtocolSpec:
    """Small-file-only preregistration after a ``provisional_pause``."""

    phase: str
    phase_index: int
    classification: str
    continuation_protocol_path: str
    continuation_manifest_path: str
    continuation_summary_path: str
    material_protocol_path: str
    material_summary_path: str
    material_path: str
    physical_old_time_level_path: str
    phase7b7j_protocol_path: str
    adapter_runner_path: str
    provisional_runner_path: str
    preregister_runner_path: str
    feedback_work_directory: str
    feedback_output: str
    summary_path: str


def _source(root: Path, relative_path: str) -> dict[str, object]:
    path = root / relative_path
    return {
        "path": relative_path,
        "size_bytes": path.stat().st_size,
        "sha256": feedback.sha256(path),
    }


def _safe_small_source(root: Path, relative_path: str) -> dict[str, object]:
    """冻结小源；完整辐射态只能作为不落盘验证的 claim。"""
    logical = PurePosixPath(relative_path)
    if logical.is_absolute() or ".." in logical.parts or not logical.parts:
        raise RuntimeError("provisional source escaped the repository")
    path = root / relative_path
    if path.suffix.lower() == ".dat":
        raise RuntimeError("provisional preregistration refuses any .dat source")
    size = path.stat().st_size
    if size > MAXIMUM_SMALL_SOURCE_BYTES:
        raise RuntimeError("provisional preregistration source is not small")
    return {
        "path": relative_path,
        "size_bytes": size,
        "sha256": feedback.sha256(path),
    }


def _read_small_json(root: Path, relative_path: str) -> dict[str, object]:
    if PurePosixPath(relative_path).suffix.lower() != ".json":
        raise RuntimeError("provisional preregistration accepts JSON evidence only")
    _safe_small_source(root, relative_path)
    value = json.loads((root / relative_path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("provisional JSON root must be an object")
    return value


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _full_state_claim(
    path: object, digest: object, size_bytes: int
) -> dict[str, object]:
    if not isinstance(path, str) or not _valid_sha256(digest):
        raise RuntimeError("paused full-state identity is malformed")
    logical = PurePosixPath(path)
    if (
        logical.is_absolute()
        or ".." in logical.parts
        or logical.parts[:2] != ("outputs", "checkpoints")
        or logical.suffix.lower() != ".dat"
        or size_bytes <= 0
    ):
        raise RuntimeError("paused full-state claim is not a repository checkpoint")
    # 中文：只冻结上游给出的路径、尺寸和哈希，不 stat、读取或重哈希全态。
    return {"path": path, "size_bytes": size_bytes, "sha256": digest}


def _validate_small_source_pins(
    root: Path, protocol: dict[str, object]
) -> dict[str, dict[str, object]]:
    sources = protocol.get("sources")
    if not isinstance(sources, dict):
        raise RuntimeError("paused continuation sources are missing")
    validated: dict[str, dict[str, object]] = {}
    for name, claim in sources.items():
        if not isinstance(name, str) or not isinstance(claim, dict):
            raise RuntimeError("paused continuation source pin is malformed")
        relative = claim.get("path")
        if not isinstance(relative, str) or _safe_small_source(root, relative) != claim:
            raise RuntimeError(f"paused continuation source pin changed: {name}")
        validated[name] = dict(claim)
    return validated


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _validated_provisional_pause(
    root: Path,
    protocol_path: str,
    manifest_path: str,
    summary_path: str,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, dict[str, object]],
    str,
]:
    protocol = _read_small_json(root, protocol_path)
    manifest = _read_small_json(root, manifest_path)
    summary = _read_small_json(root, summary_path)
    protocol_sha = feedback.sha256(root / protocol_path)
    if (
        manifest.get("protocol_sha256") != protocol_sha
        or summary.get("protocol_sha256") != protocol_sha
    ):
        raise RuntimeError("paused continuation protocol SHA changed")
    inherited_sources = _validate_small_source_pins(root, protocol)

    cfg = protocol.get("configuration", {})
    gates = protocol.get("gates", {})
    authorization = protocol.get("authorization", {})
    expected_gates = {
        "global_original_operator_residual_below": 1.0e-4,
        "global_boundary_spectrum_l1_below": 1.0e-3,
        "global_boundary_bolometric_fraction_below": 1.0e-3,
    }
    if (
        any(gates.get(key) != value for key, value in expected_gates.items())
        or int(cfg.get("maximum_concurrent_processes", -1)) != 2
        or authorization.get("pause_at_first_low_residual_and_boundary_input")
        is not True
        or authorization.get("provisional_feedback_extraction_at_pause") is not True
        or authorization.get("formal_pair_requires_next_consecutive_fresh_residual")
        is not True
    ):
        raise RuntimeError("paused continuation gates or authorization changed")

    manifest_iterations = manifest.get("iterations")
    summary_iterations = summary.get("iterations")
    if (
        manifest.get("status") != "provisional_pause"
        or summary.get("status") != "provisional_pause"
        or manifest.get("active_iteration") is not None
        or not isinstance(manifest_iterations, list)
        or not manifest_iterations
        or summary_iterations != manifest_iterations
    ):
        raise RuntimeError("provisional feedback requires an atomic provisional_pause")
    try:
        indices = [int(row["iteration"]) for row in manifest_iterations]
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("paused continuation iteration sequence is malformed") from error
    if indices != list(range(indices[0], indices[0] + len(indices))):
        raise RuntimeError("paused continuation iterations are not contiguous")

    passed = [
        index
        for index, row in enumerate(manifest_iterations)
        if row.get("convergence_passed") is True
    ]
    last = manifest_iterations[-1]
    if passed != [len(manifest_iterations) - 1] or last.get("map_passed") is not True:
        raise RuntimeError("the first and only converged map must be the final iteration")
    if (
        float(last.get("global_original_operator_residual", float("inf"))) >= 1.0e-4
        or float(last.get("boundary_spectrum_l1", float("inf"))) >= 1.0e-3
        or float(last.get("boundary_bolometric_fraction", float("inf"))) >= 1.0e-3
    ):
        raise RuntimeError("paused continuation threshold evidence changed")

    decision = summary.get("decision", {})
    if (
        decision.get("first_low_residual_and_boundary_input_audited") is not True
        or decision.get("provisional_feedback_extraction_authorized") is not True
        or decision.get("provisional_feedback_is_formal_pair_authority") is not False
        or decision.get("next_consecutive_fresh_residual_required") is not True
        or decision.get("formal_h_he_feedback_pair_authorized") is not False
        or decision.get("material_feedback_authorized") is not False
        or decision.get("dynamic_nlte_solution_accepted") is not False
    ):
        raise RuntimeError("paused continuation feedback decision changed")

    accepted_identity = (
        last.get("input_state_path"),
        last.get("input_state_sha256"),
    )
    next_identity = (
        last.get("mapped_state_path"),
        last.get("mapped_state_sha256"),
    )
    accepted_claims = (
        (manifest.get("accepted_state_path"), manifest.get("accepted_state_sha256")),
        (manifest.get("current_input_path"), manifest.get("current_input_sha256")),
        (summary.get("accepted_state_path"), summary.get("accepted_state_sha256")),
        (
            summary.get("first_low_residual_input_path"),
            summary.get("first_low_residual_input_sha256"),
        ),
    )
    next_claims = (
        (manifest.get("next_output_path"), manifest.get("next_output_sha256")),
        (
            summary.get("next_consecutive_input_path"),
            summary.get("next_consecutive_input_sha256"),
        ),
    )
    if any(identity != accepted_identity for identity in accepted_claims):
        raise RuntimeError("accepted paused full-state lineage changed")
    if any(identity != next_identity for identity in next_claims):
        raise RuntimeError("next-consecutive full-state lineage changed")
    if accepted_identity[0] == next_identity[0]:
        raise RuntimeError("paused accepted and next-consecutive buffers must differ")
    size_bytes = int(cfg.get("raw_float64_checkpoint_size_bytes", 0))
    _full_state_claim(*accepted_identity, size_bytes)
    _full_state_claim(*next_identity, size_bytes)
    return protocol, manifest, summary, last, inherited_sources, protocol_sha


def _validated_small_material(
    root: Path,
    protocol_path: str,
    summary_path: str,
    material_path: str,
) -> dict[str, object]:
    protocol = _read_small_json(root, protocol_path)
    summary = _read_small_json(root, summary_path)
    material = _safe_small_source(root, material_path)
    if (
        summary.get("protocol_sha256") != feedback.sha256(root / protocol_path)
        or protocol.get("configuration", {}).get("candidate_absolute_relaxation")
        != MATERIAL_RELAXATION
        or summary.get("candidate_absolute_relaxation") != MATERIAL_RELAXATION
        or summary.get("candidate_path") != material_path
        or summary.get("candidate_sha256") != material["sha256"]
        or summary.get("decision", {}).get("material_candidate_gate_passed") is not True
        or summary.get("decision", {}).get("candidate_accepted_as_nonlinear_step")
        is not False
    ):
        raise RuntimeError("provisional feedback material lineage changed")
    _validate_small_source_pins(root, protocol)
    return material


def _validated_first_low_state(
    root: Path,
    protocol_path: str,
    summary_path: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    protocol = json.loads((root / protocol_path).read_text(encoding="utf-8"))
    summary = json.loads((root / summary_path).read_text(encoding="utf-8"))
    decision = summary.get("decision", {})
    iterations = summary.get("iterations")
    gates = protocol.get("gates", {})
    if (
        summary.get("protocol_sha256") != feedback.sha256(root / protocol_path)
        or summary.get("status") != "complete"
        or not isinstance(iterations, list)
        or not iterations
        or decision.get("first_low_residual_and_boundary_input_audited") is not True
        or decision.get("provisional_feedback_extraction_authorized") is not True
        or decision.get("provisional_feedback_is_formal_pair_authority") is not False
        or decision.get("formal_h_he_feedback_pair_authorized") is not False
    ):
        raise RuntimeError("provisional feedback requires one paused low-residual input")
    last = iterations[-1]
    if (
        last.get("map_passed") is not True
        or float(last.get("global_original_operator_residual", float("inf")))
        >= float(gates["global_original_operator_residual_below"])
        or float(last.get("boundary_spectrum_l1", float("inf")))
        >= float(gates["global_boundary_spectrum_l1_below"])
        or float(last.get("boundary_bolometric_fraction", float("inf")))
        >= float(gates["global_boundary_bolometric_fraction_below"])
        or summary.get("first_low_residual_input_path") != last.get("input_state_path")
        or summary.get("first_low_residual_input_sha256")
        != last.get("input_state_sha256")
    ):
        raise RuntimeError("paused radiation metrics or state lineage changed")
    state_path = root / str(last["input_state_path"])
    if feedback.sha256(state_path) != last["input_state_sha256"]:
        raise RuntimeError("first low-residual radiation bytes changed")
    return protocol, summary, last


def _validated_material(
    root: Path,
    protocol_path: str,
    summary_path: str,
    material_path: str,
) -> dict[str, object]:
    protocol = json.loads((root / protocol_path).read_text(encoding="utf-8"))
    summary = json.loads((root / summary_path).read_text(encoding="utf-8"))
    decision = summary.get("decision", {})
    source = _source(root, material_path)
    if (
        summary.get("protocol_sha256") != feedback.sha256(root / protocol_path)
        or protocol.get("configuration", {}).get("candidate_absolute_relaxation")
        != MATERIAL_RELAXATION
        or summary.get("candidate_absolute_relaxation") != MATERIAL_RELAXATION
        or summary.get("candidate_path") != material_path
        or summary.get("candidate_sha256") != source["sha256"]
        or decision.get("material_candidate_gate_passed") is not True
        or decision.get("candidate_accepted_as_nonlinear_step") is not False
    ):
        raise RuntimeError("provisional feedback material lineage changed")
    return source


def build_provisional_feedback_protocol(
    root: Path,
    spec: ProvisionalFeedbackProtocolSpec,
) -> dict[str, object]:
    """Freeze one read-only feedback extraction after the first residual gate."""
    continuation, _, last = _validated_first_low_state(
        root, spec.continuation_protocol_path, spec.continuation_summary_path
    )
    material = _validated_material(
        root,
        spec.material_protocol_path,
        spec.material_summary_path,
        spec.material_path,
    )
    if spec.provisional_runner_path != RUNNER_RELATIVE_PATH:
        raise RuntimeError("provisional feedback runner path changed")
    state = _source(root, str(last["input_state_path"]))
    gates = continuation["gates"]
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            "continuation_protocol": _source(
                root, spec.continuation_protocol_path
            ),
            "continuation_summary": _source(root, spec.continuation_summary_path),
            "trial_material_protocol": _source(root, spec.material_protocol_path),
            "trial_material_summary": _source(root, spec.material_summary_path),
            "trial_material": material,
            "physical_old_time_level": _source(
                root, spec.physical_old_time_level_path
            ),
            "phase7b7j_protocol": _source(root, spec.phase7b7j_protocol_path),
            "adapter_runner": _source(root, spec.adapter_runner_path),
            "provisional_runner": _source(root, spec.provisional_runner_path),
            "previous_radiation": state,
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": feedback.PHYSICAL_FREQUENCY_GROUPS,
            "core_frequency_groups": feedback.CORE_FREQUENCY_GROUPS,
            "block_count": feedback.BLOCK_COUNT,
            "angular_direction_count": feedback.ANGULAR_DIRECTION_COUNT,
            "radiation_depth_cell_count": feedback.RADIATION_DEPTH_CELL_COUNT,
            "material_cell_count": feedback.MATERIAL_CELL_COUNT,
            "rate_quadrature_order_per_group": (
                feedback.RATE_QUADRATURE_ORDER_PER_GROUP
            ),
            "maximum_concurrent_processes": 2,
            "feedback_work_directory": spec.feedback_work_directory,
            "previous_feedback_output": spec.feedback_output,
            "summary_path": spec.summary_path,
            "material_candidate_absolute_relaxation": MATERIAL_RELAXATION,
            "previous_global_original_operator_residual": last[
                "global_original_operator_residual"
            ],
            "previous_boundary_spectrum_l1": last["boundary_spectrum_l1"],
            "previous_boundary_bolometric_fraction": last[
                "boundary_bolometric_fraction"
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
        "formal_state_gates": feedback._formal_state_gates(),
        "radiation_gates": {
            "global_original_operator_residual_below": gates[
                "global_original_operator_residual_below"
            ],
            "boundary_spectrum_l1_below": gates[
                "global_boundary_spectrum_l1_below"
            ],
            "boundary_bolometric_fraction_below": gates[
                "global_boundary_bolometric_fraction_below"
            ],
        },
        "authorization": {
            "evaluate_exactly_one_provisional_feedback_state": True,
            "cache_only_small_assembled_feedback_artifact": True,
            "provisional_feedback_is_acceptance_authority": False,
            "next_consecutive_fresh_residual_required": True,
            "formal_pair_authorized": False,
            "material_update": False,
            "radiation_update": False,
            "accept_dynamic_nlte_solution": False,
        },
    }


def build_paused_provisional_feedback_protocol(
    root: Path,
    spec: PausedProvisionalFeedbackProtocolSpec,
) -> dict[str, object]:
    """Freeze a 7B9dp-style pause using small evidence and full-state claims only."""
    artifacts = (
        spec.continuation_protocol_path,
        spec.continuation_manifest_path,
        spec.continuation_summary_path,
        spec.material_protocol_path,
        spec.material_summary_path,
    )
    if any(PurePosixPath(path).suffix.lower() != ".json" for path in artifacts):
        raise RuntimeError("paused provisional builder accepts JSON evidence only")
    if spec.provisional_runner_path != RUNNER_RELATIVE_PATH:
        raise RuntimeError("provisional feedback runner path changed")
    if spec.preregister_runner_path != PAUSED_PREREGISTER_RELATIVE_PATH:
        raise RuntimeError("provisional feedback preregister path changed")
    if spec.adapter_runner_path != PAUSED_ADAPTER_RELATIVE_PATH:
        raise RuntimeError("claim-only provisional adapter path changed")

    (
        continuation,
        _,
        _,
        last,
        inherited,
        continuation_sha,
    ) = _validated_provisional_pause(
        root,
        spec.continuation_protocol_path,
        spec.continuation_manifest_path,
        spec.continuation_summary_path,
    )
    material = _validated_small_material(
        root,
        spec.material_protocol_path,
        spec.material_summary_path,
        spec.material_path,
    )
    direct = {
        "paused_continuation_protocol": _safe_small_source(
            root, spec.continuation_protocol_path
        ),
        "paused_continuation_manifest": _safe_small_source(
            root, spec.continuation_manifest_path
        ),
        "paused_continuation_summary": _safe_small_source(
            root, spec.continuation_summary_path
        ),
        "trial_material_protocol": _safe_small_source(
            root, spec.material_protocol_path
        ),
        "trial_material_summary": _safe_small_source(
            root, spec.material_summary_path
        ),
        "trial_material": material,
        "physical_old_time_level": _safe_small_source(
            root, spec.physical_old_time_level_path
        ),
        "phase7b7j_protocol": _safe_small_source(
            root, spec.phase7b7j_protocol_path
        ),
        "adapter_runner": _safe_small_source(root, spec.adapter_runner_path),
        "provisional_runner": _safe_small_source(
            root, spec.provisional_runner_path
        ),
        "provisional_preregister": _safe_small_source(
            root, spec.preregister_runner_path
        ),
    }
    if set(direct) != PAUSED_DIRECT_SOURCE_KEYS:
        raise RuntimeError("paused provisional direct source set changed")
    collisions = set(direct).intersection(inherited)
    if collisions:
        raise RuntimeError(
            f"paused provisional source-key collision: {sorted(collisions)}"
        )
    sources = dict(direct)
    sources.update(deepcopy(inherited))
    if any(str(claim["path"]).lower().endswith(".dat") for claim in sources.values()):
        raise RuntimeError("paused provisional source set contains a .dat file")

    cfg = continuation["configuration"]
    gates = continuation["gates"]
    size_bytes = int(cfg["raw_float64_checkpoint_size_bytes"])
    accepted = _full_state_claim(
        last["input_state_path"], last["input_state_sha256"], size_bytes
    )
    next_consecutive = _full_state_claim(
        last["mapped_state_path"], last["mapped_state_sha256"], size_bytes
    )
    protocol = {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": sources,
        "full_state_claims": {
            "previous_radiation": accepted,
            "next_consecutive_radiation": next_consecutive,
        },
        "upstream_lineage": {
            "paused_continuation_protocol_sha256": continuation_sha,
            "summary_iterations_equal_manifest_iterations": True,
            "first_and_only_converged_map_is_last": True,
            "accepted_state_is_last_map_input": True,
            "next_consecutive_state_is_last_map_output": True,
            "full_state_bytes_read_by_builder": False,
            "full_state_bytes_hashed_by_builder": False,
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": feedback.PHYSICAL_FREQUENCY_GROUPS,
            "core_frequency_groups": feedback.CORE_FREQUENCY_GROUPS,
            "block_count": feedback.BLOCK_COUNT,
            "angular_direction_count": feedback.ANGULAR_DIRECTION_COUNT,
            "radiation_depth_cell_count": feedback.RADIATION_DEPTH_CELL_COUNT,
            "material_cell_count": feedback.MATERIAL_CELL_COUNT,
            "rate_quadrature_order_per_group": (
                feedback.RATE_QUADRATURE_ORDER_PER_GROUP
            ),
            "maximum_concurrent_processes": 2,
            "feedback_work_directory": spec.feedback_work_directory,
            "previous_feedback_output": spec.feedback_output,
            "summary_path": spec.summary_path,
            "material_candidate_absolute_relaxation": MATERIAL_RELAXATION,
            "previous_global_original_operator_residual": last[
                "global_original_operator_residual"
            ],
            "previous_boundary_spectrum_l1": last["boundary_spectrum_l1"],
            "previous_boundary_bolometric_fraction": last[
                "boundary_bolometric_fraction"
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
        "formal_state_gates": feedback._formal_state_gates(),
        "radiation_gates": {
            "global_original_operator_residual_below": gates[
                "global_original_operator_residual_below"
            ],
            "boundary_spectrum_l1_below": gates[
                "global_boundary_spectrum_l1_below"
            ],
            "boundary_bolometric_fraction_below": gates[
                "global_boundary_bolometric_fraction_below"
            ],
        },
        "authorization": {
            "evaluate_exactly_one_provisional_feedback_state": True,
            "cache_only_small_assembled_feedback_artifact": True,
            "provisional_feedback_is_acceptance_authority": False,
            "next_consecutive_fresh_residual_required": True,
            "formal_pair_authorized": False,
            "material_update": False,
            "radiation_update": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    if (
        protocol["configuration"]["maximum_concurrent_processes"] != 2
        or protocol["formal_state_gates"] != feedback._formal_state_gates()
    ):
        raise RuntimeError("provisional feedback resources or formal gates changed")
    return protocol


def write_paused_provisional_feedback_protocol(
    root: Path,
    spec: PausedProvisionalFeedbackProtocolSpec,
    output_path: Path,
) -> tuple[dict[str, object], str]:
    protocol = build_paused_provisional_feedback_protocol(root, spec)
    _write_json_atomic(output_path, protocol)
    return protocol, feedback.sha256(output_path)


def _clean_completed_partials(protocol: dict[str, object], expected_hash: str) -> None:
    work = (
        ROOT
        / protocol["configuration"]["feedback_work_directory"]
        / "previous"
    ).resolve()
    allowed = (ROOT / "outputs/checkpoints").resolve()
    if not work.is_relative_to(allowed) or "provisional" not in str(work):
        raise RuntimeError("refusing unsafe provisional partial cleanup")
    marker = work / ".phase7b9_provisional_owner.json"
    if marker.exists():
        if json.loads(marker.read_text()).get("protocol_sha256") != expected_hash:
            raise RuntimeError("provisional work directory belongs to another protocol")
    else:
        _write_json_atomic(marker, {"protocol_sha256": expected_hash})
    for child in work.iterdir():
        if child == marker:
            continue
        if child.is_symlink() or not child.is_file():
            raise RuntimeError("unexpected provisional partial entry")
        child.unlink()


def _runtime_protocol_with_validated_claim(
    protocol: dict[str, object],
) -> dict[str, object]:
    """Validate a claim-only full state once, immediately before real feedback."""
    if "previous_radiation" in protocol.get("sources", {}):
        return protocol
    claim = protocol.get("full_state_claims", {}).get("previous_radiation")
    if not isinstance(claim, dict):
        raise RuntimeError("claim-only provisional radiation identity is missing")
    path = ROOT / str(claim["path"])
    if (
        path.stat().st_size != int(claim["size_bytes"])
        or feedback.sha256(path) != claim["sha256"]
    ):
        raise RuntimeError("claim-only provisional radiation state changed")
    runtime = deepcopy(protocol)
    runtime["sources"]["previous_radiation"] = dict(claim)
    return runtime


def run_provisional_feedback(
    protocol_path: Path,
    expected_hash: str,
) -> dict[str, object]:
    """Evaluate one state, cache its assembled artifact, and keep it unauthorized."""
    protocol = feedback.load_frozen_pair_protocol(
        protocol_path, expected_hash, validate_sources=True
    )
    protocol = _runtime_protocol_with_validated_claim(protocol)
    feedback._validate_worker_template_sources(protocol)
    summary_path = ROOT / protocol["configuration"]["summary_path"]
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("protocol_sha256") != expected_hash:
            raise RuntimeError("provisional feedback summary lineage changed")
        return summary
    manifest = feedback._run_feedback_state(
        protocol, protocol_path, expected_hash, "previous"
    )
    passed = bool(
        manifest.get("status") == "complete"
        and manifest.get("state_gate_passed") is True
    )
    if passed:
        _clean_completed_partials(protocol, expected_hash)
    summary = {
        "phase": protocol["phase"],
        "classification": "[V-formal-state]+[A-provisional]+[O]",
        "protocol_sha256": expected_hash,
        "status": "complete" if passed else "gate_failed",
        "radiation_state_path": manifest["state_path"],
        "radiation_state_sha256": manifest["state_sha256"],
        "global_original_operator_residual": protocol["configuration"][
            "previous_global_original_operator_residual"
        ],
        "boundary_spectrum_l1": protocol["configuration"][
            "previous_boundary_spectrum_l1"
        ],
        "boundary_bolometric_fraction": protocol["configuration"][
            "previous_boundary_bolometric_fraction"
        ],
        "feedback_manifest_path": str(
            feedback._feedback_manifest_path(protocol, "previous").relative_to(ROOT)
        ),
        "feedback_artifact_path": manifest.get("feedback_artifact_path"),
        "feedback_artifact_sha256": manifest.get("feedback_artifact_sha256"),
        "formal_state_gate_passed": manifest.get("state_gate_passed", False),
        "decision": {
            "provisional_feedback_extraction_complete": passed,
            "provisional_feedback_is_acceptance_authority": False,
            "next_consecutive_fresh_residual_authorized": passed,
            "formal_h_he_feedback_pair_authorized": False,
            "material_feedback_authorized": False,
            "dynamic_nlte_solution_accepted": False,
        },
    }
    _write_json_atomic(summary_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expected-protocol-sha256", required=True)
    args = parser.parse_args()
    run_provisional_feedback(args.protocol, args.expected_protocol_sha256)


if __name__ == "__main__":
    main()
