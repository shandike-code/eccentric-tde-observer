"""Phase 7B9du：从耗尽的 7B9dp 双缓冲继续纯 Picard 映射。"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Callable

try:
    from scripts import phase7b9_half_trial_positive_sequence_engine as engine
    from scripts import phase7b9_half_trial_radiation_continuation as storage
    from scripts import phase7b9di_progression_continuation as progression
    from scripts import phase7b9dp_post_streaming_picard as dp
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_half_trial_positive_sequence_engine as engine  # type: ignore[no-redef]
    import phase7b9_half_trial_radiation_continuation as storage  # type: ignore[no-redef]
    import phase7b9di_progression_continuation as progression  # type: ignore[no-redef]
    import phase7b9dp_post_streaming_picard as dp  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
RUNNER_RELATIVE_PATH = "scripts/phase7b9du_exhausted_dp_picard_continuation.py"
PREREGISTER_RELATIVE_PATH = (
    "scripts/phase7b9du_preregister_exhausted_dp_picard_continuation.py"
)
DP_ADDITIONAL_MAPS = 40
SEED_COMPLETED_MAPS = 1
MAXIMUM_SMALL_SOURCE_BYTES = 64 * 1024 * 1024
DIRECT_SOURCE_KEYS = {
    "exhausted_dp_protocol",
    "exhausted_dp_manifest",
    "exhausted_dp_summary",
    "exhausted_dp_continuation_runner",
    "exhausted_dp_continuation_preregister",
}


@dataclass(frozen=True)
class ExhaustedDpPicardContinuationSpec:
    phase: str
    phase_index: int
    classification: str
    dp_protocol_path: str
    dp_manifest_path: str
    dp_summary_path: str
    additional_map_horizon: int
    runner_path: str
    preregister_path: str
    manifest_path: str
    transient_report_directory: str
    summary_path: str
    figure_path: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _read_json(root: Path, relative: str) -> dict[str, object]:
    payload = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("7B9du JSON evidence must contain an object")
    return payload


def _safe_relative(relative: str, *, dat_claim: bool = False) -> str:
    logical = PurePosixPath(relative)
    if logical.is_absolute() or ".." in logical.parts or not logical.parts:
        raise RuntimeError("7B9du path must be repository-relative")
    if dat_claim:
        if logical.suffix.lower() != ".dat":
            raise RuntimeError("7B9du full-state claim must be a .dat path")
    elif logical.suffix.lower() == ".dat":
        raise RuntimeError("7B9du small sources cannot contain .dat files")
    return str(logical)


def _small_source(root: Path, relative: str) -> dict[str, object]:
    relative = _safe_relative(relative)
    path = root / relative
    size = path.stat().st_size
    if not path.is_file() or size > MAXIMUM_SMALL_SOURCE_BYTES:
        raise RuntimeError(f"7B9du source is not a small regular file: {relative}")
    return {"path": relative, "size_bytes": size, "sha256": _sha256(path)}


def _validate_source(root: Path, claim: object) -> dict[str, object]:
    if not isinstance(claim, dict):
        raise RuntimeError("7B9du upstream source claim is malformed")
    current = _small_source(root, str(claim.get("path", "")))
    if current != claim:
        raise RuntimeError(f"7B9du upstream source changed: {current['path']}")
    return current


def _full_state_claim(path: object, digest: object, size: int) -> dict[str, object]:
    relative = _safe_relative(str(path), dat_claim=True)
    fingerprint = str(digest)
    if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
        raise RuntimeError("7B9du full-state claim has an invalid SHA-256")
    if size <= 0:
        raise RuntimeError("7B9du full-state claim has an invalid size")
    return {"path": relative, "size_bytes": int(size), "sha256": fingerprint}


def _expected_progression_definition(gates: dict[str, object]) -> dict[str, object]:
    return {
        "frequency_ownership_exact": True,
        "minimum_input_and_mapped_intensity_at_least": gates[
            "minimum_input_and_mapped_intensity_at_least"
        ],
        "subsequent_residual_contraction_ratio_below": gates[
            "subsequent_residual_contraction_ratio_below"
        ],
        "each_process_peak_rss_strictly_below_mib": gates[
            "each_process_peak_rss_strictly_below_mib"
        ],
        "each_worker_wall_time_strictly_below_s": gates[
            "each_worker_wall_time_strictly_below_s"
        ],
        "each_full_map_wall_time_strictly_below_s": gates[
            "each_full_map_wall_time_strictly_below_s"
        ],
    }


def _expected_convergence_definition(gates: dict[str, object]) -> dict[str, object]:
    return {
        "global_original_operator_residual_below": gates[
            "global_original_operator_residual_below"
        ],
        "global_boundary_spectrum_l1_below": gates[
            "global_boundary_spectrum_l1_below"
        ],
        "global_boundary_bolometric_fraction_below": gates[
            "global_boundary_bolometric_fraction_below"
        ],
    }


def _recomputed_row_gates(
    gates: dict[str, object], row: dict[str, object]
) -> tuple[dict[str, bool], dict[str, bool]]:
    metrics = {
        key: row[key]
        for key in (
            "block_report_count",
            "frequency_ownership_count",
            "frequency_ownership_exact",
            "minimum_input_intensity",
            "minimum_mapped_intensity",
            "maximum_process_peak_rss_mib",
            "maximum_worker_wall_runtime_s",
            "full_map_wall_runtime_s",
            "global_original_operator_residual",
            "boundary_spectrum_l1",
            "boundary_bolometric_fraction",
        )
    }
    return (
        progression._progression_checks(
            gates, metrics, float(row["contraction_ratio"])
        ),
        progression._convergence_checks(gates, metrics),
    )


def _validate_exhausted_dp(
    root: Path, spec: ExhaustedDpPicardContinuationSpec
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    protocol = _read_json(root, spec.dp_protocol_path)
    manifest = _read_json(root, spec.dp_manifest_path)
    summary = _read_json(root, spec.dp_summary_path)
    protocol_hash = _sha256(root / spec.dp_protocol_path)
    if (
        manifest.get("protocol_sha256") != protocol_hash
        or summary.get("protocol_sha256") != protocol_hash
    ):
        raise RuntimeError("7B9du exhausted dp protocol SHA lineage changed")
    sources = protocol.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise RuntimeError("7B9du exhausted dp source set is missing")
    for source in sources.values():
        _validate_source(root, source)

    cfg = protocol.get("configuration", {})
    gates = protocol.get("gates", {})
    expected_gates = storage.common.memory_safe_seeded_two_map_gates()
    authorization = protocol.get("authorization", {})
    if (
        cfg.get("runner_path") != dp.RUNNER_RELATIVE_PATH
        or int(cfg.get("maximum_additional_picard_maps", -1)) != DP_ADDITIONAL_MAPS
        or int(cfg.get("maximum_picard_maps", -1)) != DP_ADDITIONAL_MAPS + 1
        or int(cfg.get("seed_completed_picard_maps", -1)) != 1
        or int(cfg.get("first_runtime_iteration", -1)) != 1
        or int(cfg.get("last_runtime_iteration", -1)) != DP_ADDITIONAL_MAPS
        or int(cfg.get("maximum_concurrent_processes", -1)) != 2
        or gates != expected_gates
        or gates.get("each_full_map_wall_time_strictly_below_s") != 1800.0
        or protocol.get("progression_gate_definition")
        != _expected_progression_definition(gates)
        or protocol.get("convergence_gate_definition")
        != _expected_convergence_definition(gates)
        or authorization.get("pure_picard_only") is not True
        or authorization.get("anderson_after_seed") is not False
        or authorization.get("continue_only_if_progression_gate_passes") is not True
        or authorization.get("overwrite_only_two_claimed_buffers") is not True
        or authorization.get("start_every_map_from_block_zero") is not True
        or authorization.get("material_feedback_authorized") is not False
        or authorization.get("accept_dynamic_nlte_solution") is not False
        or any(
            authorization.get(name) is not False
            for name in (
                "cellwise_clipping",
                "nan_to_num",
                "intensity_floor",
                "point_deletion",
                "posthoc_renormalization",
            )
        )
    ):
        raise RuntimeError("7B9du exhausted dp science or resource gates changed")

    rows = manifest.get("iterations")
    decision = summary.get("decision", {})
    if (
        manifest.get("status") != "maximum_maps_exhausted"
        or summary.get("status") != "maximum_maps_exhausted"
        or manifest.get("active_iteration") is not None
        or not isinstance(rows, list)
        or len(rows) != DP_ADDITIONAL_MAPS + 1
        or summary.get("iterations") != rows
        or summary.get("completed_picard_maps") != DP_ADDITIONAL_MAPS + 1
        or summary.get("completed_additional_picard_maps") != DP_ADDITIONAL_MAPS
        or decision.get("positive_picard_sequence_reached_first_low_residual")
        is not False
        or decision.get("provisional_feedback_extraction_authorized") is not False
        or decision.get("formal_h_he_feedback_pair_authorized") is not False
        or decision.get("material_feedback_authorized") is not False
        or decision.get("anderson_used_after_seed") is not False
        or decision.get("dynamic_nlte_solution_accepted") is not False
    ):
        raise RuntimeError("7B9du requires an atomic exhausted 40-map dp sequence")
    if [int(row.get("iteration", -1)) for row in rows] != list(
        range(DP_ADDITIONAL_MAPS + 1)
    ):
        raise RuntimeError("7B9du dp iteration numbering changed")
    for previous, current in zip(rows, rows[1:], strict=False):
        if (
            current.get("input_state_path") != previous.get("mapped_state_path")
            or current.get("input_state_sha256")
            != previous.get("mapped_state_sha256")
        ):
            raise RuntimeError("7B9du dp Picard chain is discontinuous")
    for row in rows[1:]:
        if "reports" in row:
            raise RuntimeError("7B9du dp transient block reports were not compacted")
        audit = row.get("block_report_audit", {})
        try:
            recomputed_progression, recomputed_convergence = _recomputed_row_gates(
                gates, row
            )
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("7B9du dp gate metrics are malformed") from error
        boundary_pass = bool(
            recomputed_convergence["boundary_spectrum_pass"]
            and recomputed_convergence["boundary_bolometric_pass"]
        )
        expected_public_checks = {
            "frequency_ownership_pass": recomputed_progression[
                "frequency_ownership_pass"
            ],
            "positive_map_pass": recomputed_progression["positive_map_pass"],
            "initial_reproduction_pass": True,
            "contraction_pass": recomputed_progression["contraction_pass"],
            "boundary_pass": boundary_pass,
            "resources_pass": recomputed_progression["resources_pass"],
        }
        if (
            row.get("progression_gate_checks") != recomputed_progression
            or not all(recomputed_progression.values())
            or row.get("progression_passed") is not True
            or row.get("convergence_gate_checks") != recomputed_convergence
            or all(recomputed_convergence.values())
            or row.get("convergence_passed") is not False
            or row.get("map_passed") is not False
            or row.get("gate_checks") != expected_public_checks
            or row.get("original_map_passed") is not boundary_pass
            or audit.get("record_count") != 76
            or audit.get("block_indices") != list(range(76))
        ):
            raise RuntimeError(
                "7B9du dp additional maps must all pass progression and remain unconverged"
            )
    last = rows[-1]
    if (
        (manifest.get("current_input_path"), manifest.get("current_input_sha256"))
        != (last.get("input_state_path"), last.get("input_state_sha256"))
        or (manifest.get("next_output_path"), manifest.get("next_output_sha256"))
        != (last.get("mapped_state_path"), last.get("mapped_state_sha256"))
    ):
        raise RuntimeError("7B9du exhausted dp terminal buffers changed")
    return protocol, manifest, summary, last


def _compact_seed(last: dict[str, object]) -> dict[str, object]:
    keep = (
        "input_state_path",
        "input_state_sha256",
        "mapped_state_path",
        "mapped_state_sha256",
        "global_original_operator_residual",
        "boundary_spectrum_l1",
        "boundary_bolometric_fraction",
        "minimum_input_intensity",
        "minimum_mapped_intensity",
        "progression_gate_checks",
        "convergence_gate_checks",
        "progression_passed",
        "convergence_passed",
        "map_passed",
    )
    return {
        "iteration": 0,
        "upstream_dp_iteration": int(last["iteration"]),
        **{name: deepcopy(last[name]) for name in keep},
        "contraction_ratio": None,
        "contraction_applicable": False,
        "initial_reproduction_applicable": False,
        "seed_classification": "last_exhausted_dp_progression_passed_map",
        "failed_upstream_points_retained": False,
    }


def _validate_stage_paths(spec: ExhaustedDpPicardContinuationSpec) -> None:
    manifest = PurePosixPath(spec.manifest_path)
    transient = PurePosixPath(spec.transient_report_directory)
    summary = PurePosixPath(spec.summary_path)
    figure = PurePosixPath(spec.figure_path)
    for path in (manifest, transient, summary, figure):
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise RuntimeError("7B9du stage path must be repository-relative")
    if (
        manifest.parts[:2] != ("outputs", "checkpoints")
        or manifest.suffix.lower() != ".json"
        or "du" not in str(manifest).lower()
        or manifest == PurePosixPath(spec.dp_manifest_path)
    ):
        raise RuntimeError("7B9du manifest must be a new stage-owned checkpoint JSON")
    if (
        transient.parts[:2] != ("outputs", "checkpoints")
        or "transient" not in transient.name.lower()
        or "du" not in transient.name.lower()
    ):
        raise RuntimeError("7B9du transient directory must be stage-owned")
    if (
        summary.parts[0] != "outputs"
        or (len(summary.parts) > 1 and summary.parts[1] == "checkpoints")
        or summary.suffix.lower() != ".json"
        or summary == PurePosixPath(spec.dp_summary_path)
        or figure.parts[0] != "outputs"
        or (len(figure.parts) > 1 and figure.parts[1] == "checkpoints")
        or figure.suffix.lower() != ".png"
    ):
        raise RuntimeError("7B9du summary and figure must be new small outputs")


def build_exhausted_dp_picard_continuation_protocol(
    root: Path, spec: ExhaustedDpPicardContinuationSpec
) -> dict[str, object]:
    """Build a new two-buffer continuation without opening either full state."""
    if type(spec.additional_map_horizon) is not int or spec.additional_map_horizon <= 0:
        raise RuntimeError("7B9du additional map horizon must be a positive integer")
    if spec.runner_path != RUNNER_RELATIVE_PATH:
        raise RuntimeError("7B9du runner path changed")
    if spec.preregister_path != PREREGISTER_RELATIVE_PATH:
        raise RuntimeError("7B9du preregister path changed")
    _validate_stage_paths(spec)
    protocol, manifest, _, last = _validate_exhausted_dp(root, spec)
    cfg = deepcopy(protocol["configuration"])
    size = int(cfg["raw_float64_checkpoint_size_bytes"])
    current = _full_state_claim(
        last["mapped_state_path"], last["mapped_state_sha256"], size
    )
    scratch = _full_state_claim(
        last["input_state_path"], last["input_state_sha256"], size
    )
    if current["path"] == scratch["path"]:
        raise RuntimeError("7B9du requires two distinct dp buffers")

    direct = {
        "exhausted_dp_protocol": _small_source(root, spec.dp_protocol_path),
        "exhausted_dp_manifest": _small_source(root, spec.dp_manifest_path),
        "exhausted_dp_summary": _small_source(root, spec.dp_summary_path),
        "exhausted_dp_continuation_runner": _small_source(root, spec.runner_path),
        "exhausted_dp_continuation_preregister": _small_source(
            root, spec.preregister_path
        ),
    }
    if set(direct) != DIRECT_SOURCE_KEYS:
        raise RuntimeError("7B9du direct source set changed")
    collisions = set(direct).intersection(protocol["sources"])
    if collisions:
        raise RuntimeError(f"7B9du source-key collision: {sorted(collisions)}")
    sources = dict(direct)
    for name, source in protocol["sources"].items():
        sources[name] = _validate_source(root, source)
    if any(str(source["path"]).lower().endswith(".dat") for source in sources.values()):
        raise RuntimeError("7B9du source set contains a full-state file")

    cfg.update(
        {
            "phase_index": spec.phase_index,
            "maximum_picard_maps": SEED_COMPLETED_MAPS
            + spec.additional_map_horizon,
            "maximum_additional_picard_maps": spec.additional_map_horizon,
            "seed_completed_picard_maps": SEED_COMPLETED_MAPS,
            "first_runtime_iteration": 1,
            "last_runtime_iteration": spec.additional_map_horizon,
            "maximum_concurrent_processes": 2,
            "initial_state_path": current["path"],
            "initial_state_sha256": current["sha256"],
            "scratch_state_path": scratch["path"],
            "scratch_state_initial_sha256": scratch["sha256"],
            "manifest_path": spec.manifest_path,
            "report_directory": spec.transient_report_directory,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "runner_path": spec.runner_path,
            "initial_reference_mode": "continued_after_exhausted_phase7b9dp",
            "copy_or_initialize_full_state": False,
        }
    )
    gates = deepcopy(protocol["gates"])
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": sources,
        "full_state_claims": {
            "current_initial_is_dp_terminal_mapped": current,
            "scratch_initial_is_dp_terminal_input": scratch,
        },
        "configuration": cfg,
        "reference": {
            "upstream_dp_status": manifest["status"],
            "upstream_dp_additional_maps": DP_ADDITIONAL_MAPS,
            "upstream_dp_terminal_iteration": last["iteration"],
            "upstream_dp_terminal_global_original_operator_residual": last[
                "global_original_operator_residual"
            ],
            "upstream_dp_terminal_boundary_spectrum_l1": last[
                "boundary_spectrum_l1"
            ],
            "upstream_dp_terminal_boundary_bolometric_fraction": last[
                "boundary_bolometric_fraction"
            ],
        },
        "gates": gates,
        "progression_gate_definition": deepcopy(
            protocol["progression_gate_definition"]
        ),
        "convergence_gate_definition": deepcopy(
            protocol["convergence_gate_definition"]
        ),
        "seed_iteration": _compact_seed(last),
        "storage_plan": {
            "reuse_exactly_two_dp_buffers": True,
            "additional_full_state_allocation_count": 0,
            "copy_initial_source": False,
            "failed_upstream_points_retained": False,
            "single_stage_owned_transient_report_directory": True,
            "block_reports_compacted_after_each_committed_map": True,
        },
        "resource_provenance": storage.common.memory_safe_resource_provenance(),
        "authorization": deepcopy(protocol["authorization"]),
        "builder_audit": {
            "upstream_additional_map_count_exactly": DP_ADDITIONAL_MAPS,
            "all_upstream_additional_progression_gates_passed": True,
            "all_upstream_additional_convergence_decisions_false": True,
            "full_state_bytes_read": False,
            "full_state_bytes_hashed": False,
            "additional_map_horizon_selected_by_builder": False,
        },
    }


def write_protocol(
    root: Path,
    spec: ExhaustedDpPicardContinuationSpec,
    output_path: Path,
) -> tuple[dict[str, object], str]:
    protocol = build_exhausted_dp_picard_continuation_protocol(root, spec)
    _write_json_atomic(output_path, protocol)
    return protocol, _sha256(output_path)


def _load_runtime_protocol(
    root: Path, protocol_path: Path, expected_hash: str
) -> dict[str, object]:
    if len(expected_hash) != 64 or _sha256(protocol_path) != expected_hash:
        raise RuntimeError("frozen 7B9du continuation protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    cfg = protocol.get("configuration", {})
    horizon = cfg.get("maximum_additional_picard_maps")
    gates = protocol.get("gates", {})
    authorization = protocol.get("authorization", {})
    if (
        type(horizon) is not int
        or horizon <= 0
        or cfg.get("runner_path") != RUNNER_RELATIVE_PATH
        or cfg.get("maximum_picard_maps") != horizon + 1
        or cfg.get("last_runtime_iteration") != horizon
        or cfg.get("first_runtime_iteration") != 1
        or cfg.get("seed_completed_picard_maps") != 1
        or cfg.get("maximum_concurrent_processes") != 2
        or gates != storage.common.memory_safe_seeded_two_map_gates()
        or protocol.get("progression_gate_definition")
        != _expected_progression_definition(gates)
        or protocol.get("convergence_gate_definition")
        != _expected_convergence_definition(gates)
        or authorization.get("pure_picard_only") is not True
        or authorization.get("anderson_after_seed") is not False
        or authorization.get("continue_only_if_progression_gate_passes") is not True
        or authorization.get("overwrite_only_two_claimed_buffers") is not True
        or authorization.get("start_every_map_from_block_zero") is not True
        or authorization.get("material_feedback_authorized") is not False
        or authorization.get("accept_dynamic_nlte_solution") is not False
        or any(
            authorization.get(name) is not False
            for name in (
                "cellwise_clipping",
                "nan_to_num",
                "intensity_floor",
                "point_deletion",
                "posthoc_renormalization",
            )
        )
    ):
        raise RuntimeError("7B9du runtime science, resource, or horizon gates changed")
    claims = protocol.get("full_state_claims", {})
    current_claim = claims.get("current_initial_is_dp_terminal_mapped", {})
    scratch_claim = claims.get("scratch_initial_is_dp_terminal_input", {})
    if (
        (cfg.get("initial_state_path"), cfg.get("initial_state_sha256"))
        != (current_claim.get("path"), current_claim.get("sha256"))
        or (cfg.get("scratch_state_path"), cfg.get("scratch_state_initial_sha256"))
        != (scratch_claim.get("path"), scratch_claim.get("sha256"))
    ):
        raise RuntimeError("7B9du runtime full-state claims changed")
    for source in protocol.get("sources", {}).values():
        _validate_source(root, source)
    return protocol


def initialize_manifest(
    root: Path, protocol_path: Path, expected_hash: str
) -> dict[str, object]:
    protocol = _load_runtime_protocol(root, protocol_path, expected_hash)
    cfg = protocol["configuration"]
    manifest_path = root / cfg["manifest_path"]
    expected_size = int(cfg["raw_float64_checkpoint_size_bytes"])
    if manifest_path.exists():
        manifest = _read_json(root, str(cfg["manifest_path"]))
        if manifest.get("protocol_sha256") != expected_hash:
            raise RuntimeError("7B9du recovery manifest belongs to another protocol")
        current = root / manifest["current_input_path"]
        scratch = root / manifest["next_output_path"]
        claimed_paths = {cfg["initial_state_path"], cfg["scratch_state_path"]}
        if {
            manifest.get("current_input_path"),
            manifest.get("next_output_path"),
        } != claimed_paths:
            raise RuntimeError("7B9du recovery escaped the two claimed buffers")
        if current.stat().st_size != expected_size or scratch.stat().st_size != expected_size:
            raise RuntimeError("7B9du recovery buffer size changed")
        if _sha256(current) != manifest["current_input_sha256"]:
            raise RuntimeError("7B9du recovery current input changed")
        if manifest.get("active_iteration") is None and _sha256(scratch) != manifest[
            "next_output_sha256"
        ]:
            raise RuntimeError("7B9du recovery scratch changed")
        return manifest
    current = root / cfg["initial_state_path"]
    scratch = root / cfg["scratch_state_path"]
    if (
        current.resolve() == scratch.resolve()
        or current.stat().st_size != expected_size
        or scratch.stat().st_size != expected_size
        or _sha256(current) != cfg["initial_state_sha256"]
        or _sha256(scratch) != cfg["scratch_state_initial_sha256"]
    ):
        raise RuntimeError("7B9du initial double-buffer claims changed")
    manifest = {
        "phase": protocol["phase"],
        "protocol_sha256": expected_hash,
        "status": "running",
        "current_input_path": cfg["initial_state_path"],
        "current_input_sha256": cfg["initial_state_sha256"],
        "next_output_path": cfg["scratch_state_path"],
        "next_output_sha256": cfg["scratch_state_initial_sha256"],
        "iterations": [deepcopy(protocol["seed_iteration"])],
        "active_iteration": None,
    }
    _write_json_atomic(manifest_path, manifest)
    return manifest


def _run_worker(
    protocol_path: Path,
    expected_hash: str,
    iteration: int,
    block_index: int,
    input_state: Path,
    input_sha256: str,
    output_state: Path,
    report_path: Path,
) -> None:
    protocol = _load_runtime_protocol(ROOT, protocol_path, expected_hash)
    fixed = _read_json(ROOT, protocol["sources"]["finite_trial_protocol"]["path"])
    if fixed.get("sources", {}).get("current_material_state") != protocol[
        "sources"
    ]["finite_trial_material"]:
        raise RuntimeError("7B9du fixed material changed")
    generic = engine.generic
    original = generic.base.phase7b9i._load_protocol
    try:
        generic.base.phase7b9i._load_protocol = lambda _path, validate_sources=False: fixed
        engine.EXPECTED_PROTOCOL_SHA256 = expected_hash
        generic.EXPECTED_PROTOCOL_SHA256 = expected_hash
        engine._run_worker(
            protocol_path,
            iteration,
            block_index,
            input_state,
            input_sha256,
            output_state,
            report_path,
        )
    finally:
        generic.base.phase7b9i._load_protocol = original


BatchExecutor = Callable[
    [int, list[int], Path, str, Path, list[Path]], list[dict[str, object]]
]


def _default_batch_executor(
    root: Path, protocol_path: Path, expected_hash: str
) -> BatchExecutor:
    def execute(
        iteration: int,
        indices: list[int],
        input_path: Path,
        input_hash: str,
        output_path: Path,
        report_paths: list[Path],
    ) -> list[dict[str, object]]:
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    str(root / RUNNER_RELATIVE_PATH),
                    "--worker",
                    "--protocol",
                    str(protocol_path),
                    "--expected-protocol-sha256",
                    expected_hash,
                    "--iteration",
                    str(iteration),
                    "--block-index",
                    str(index),
                    "--input-state",
                    str(input_path),
                    "--input-sha256",
                    input_hash,
                    "--output-state",
                    str(output_path),
                    "--worker-report",
                    str(report_path),
                ],
                cwd=root,
            )
            for index, report_path in zip(indices, report_paths, strict=True)
        ]
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"7B9du worker batch failed: {codes}")
        return [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]

    return execute


def _summary(
    root: Path,
    protocol: dict[str, object],
    manifest: dict[str, object],
    expected_hash: str,
) -> dict[str, object]:
    cfg = protocol["configuration"]
    records = manifest["iterations"]
    figure = root / cfg["figure_path"]
    if records:
        engine._plot(figure, records)
    paused = manifest["status"] == "provisional_pause"
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V-exhausted-dp-pure-Picard]+[O]",
        "protocol_sha256": expected_hash,
        "status": manifest["status"],
        "upstream_dp_additional_picard_maps": DP_ADDITIONAL_MAPS,
        "completed_picard_maps_including_compact_seed": len(records),
        "completed_additional_picard_maps": len(records) - 1,
        "requested_additional_map_horizon": cfg["maximum_additional_picard_maps"],
        "residual_history": [row["global_original_operator_residual"] for row in records],
        "contraction_ratio_history": [row["contraction_ratio"] for row in records],
        "boundary_spectrum_l1_history": [row["boundary_spectrum_l1"] for row in records],
        "iterations": records,
        "decision": {
            "positive_picard_sequence_reached_first_low_residual": paused,
            "first_low_residual_and_boundary_input_audited": paused,
            "provisional_feedback_extraction_authorized": paused,
            "provisional_feedback_is_formal_pair_authority": False,
            "next_consecutive_fresh_residual_required": paused,
            "formal_h_he_feedback_pair_authorized": False,
            "material_feedback_authorized": False,
            "anderson_used_after_seed": False,
            "dynamic_nlte_solution_accepted": False,
        },
        "figures": [figure.name] if records else [],
    }
    if paused:
        final = records[-1]
        summary.update(
            {
                "first_low_residual_input_path": final["input_state_path"],
                "first_low_residual_input_sha256": final["input_state_sha256"],
                "next_consecutive_input_path": final["mapped_state_path"],
                "next_consecutive_input_sha256": final["mapped_state_sha256"],
            }
        )
    _write_json_atomic(root / cfg["summary_path"], summary)
    return summary


def run_continuation(
    root: Path,
    protocol_path: Path,
    expected_hash: str,
    *,
    batch_executor: BatchExecutor | None = None,
    stop_after_iteration: int | None = None,
) -> dict[str, object]:
    protocol = _load_runtime_protocol(root, protocol_path, expected_hash)
    manifest = initialize_manifest(root, protocol_path, expected_hash)
    storage._transient_root(root, protocol, expected_hash)
    executor = batch_executor or _default_batch_executor(root, protocol_path, expected_hash)
    while manifest["status"] == "running":
        manifest = dp._run_one_map(
            root, protocol_path, protocol, expected_hash, manifest, executor
        )
        manifest = storage.compact_committed_reports(root, protocol, expected_hash)
        summary = _summary(root, protocol, manifest, expected_hash)
        if stop_after_iteration is not None and len(manifest["iterations"]) - 1 >= (
            stop_after_iteration
        ):
            return summary
    return _summary(root, protocol, manifest, expected_hash)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--stop-after-iteration", type=int)
    args = parser.parse_args()
    if args.worker:
        required = (
            args.iteration,
            args.block_index,
            args.input_state,
            args.input_sha256,
            args.output_state,
            args.worker_report,
        )
        if any(value is None for value in required):
            raise ValueError("7B9du worker mode requires iteration, block and both states")
        _run_worker(
            args.protocol,
            args.expected_protocol_sha256,
            int(args.iteration),
            int(args.block_index),
            args.input_state,
            str(args.input_sha256),
            args.output_state,
            args.worker_report,
        )
        return
    run_continuation(
        ROOT,
        args.protocol,
        args.expected_protocol_sha256,
        stop_after_iteration=args.stop_after_iteration,
    )


if __name__ == "__main__":
    main()
